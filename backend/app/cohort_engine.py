from openai import OpenAI
import os
from dotenv import load_dotenv
import json
import random
import re
import logging
import asyncio
import concurrent.futures
from typing import Dict, Any, List, Optional
from . import crud
from datetime import datetime

# Import shared utilities
from .utils import get_openai_client, MODEL_NAME

# Load environment variables from the backend folder
backend_dir = os.path.dirname(os.path.dirname(__file__))
env_path = os.path.join(backend_dir, '.env')
load_dotenv(env_path)

# Configure logging
logger = logging.getLogger(__name__)

# Model token limit (allow overriding via env)
MODEL_MAX_TOKENS = int(os.getenv("OPENAI_MODEL_MAX_TOKENS", "32768"))


# Model token limit (allow overriding via env)
MODEL_MAX_TOKENS = int(os.getenv("OPENAI_MODEL_MAX_TOKENS", "32768"))


def _estimate_tokens_for_text(text: str) -> int:
    """Very small heuristic to estimate tokens from characters.
    Uses a chars-per-token heuristic (avg 4 chars/token) and adds small padding.
    This is conservative and intended for budgeting only.
    """
    if not text:
        return 0
    # basic heuristic: 1 token per ~4 characters
    return max(1, int(len(text) / 4) + 2)


def _validate_openai_setup():
    """Validate OpenAI configuration and provide helpful error messages."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.error("❌ OPENAI_API_KEY environment variable not set!")
        logger.error("💡 Set your OpenAI API key: export OPENAI_API_KEY='your-key-here'")
        return False
    
    if api_key.startswith("sk-"):
        logger.info("✅ OpenAI API key format appears valid")
    else:
        logger.warning("⚠️ OpenAI API key format might be invalid (should start with 'sk-')")
    
    logger.info(f"🤖 Using model: {MODEL_NAME}")
    return True


PHARMA_METRIC_DESCRIPTIONS = {
    "intent_to_action": "Action Intent (1-10): Likelihood to request this therapy (if Patient) or prescribe it (if HCP) after reviewing the stimulus.",
    "emotional_response": "Emotional Response (-1 to 1): Overall sentiment score, where -1 is very negative and +1 is very positive.",
    "brand_trust": "Brand Trust (1-10): Degree to which the message builds scientific credibility and confidence in the brand.",
    "message_clarity": "Message Clarity (1-10): How clearly the persona understands the primary clinical benefit being communicated.",
    "key_concerns": "Key Concerns (text): Most important clinical, safety, access, or cost objections raised by this persona."
}

LEGACY_METRIC_ALIASES = {
    "purchase_intent": "intent_to_action",
    "sentiment": "emotional_response",
    "trust_in_brand": "brand_trust"
}


def normalize_metric(metric: str) -> str:
    """Map legacy metric names to the current pharma metric vocabulary."""
    return LEGACY_METRIC_ALIASES.get(metric, metric)


def format_metric_guidance(metrics: List[str], metric_weights: Optional[Dict[str, float]] = None) -> str:
    """Return human-readable instructions for each requested metric."""
    if not metrics:
        return "- No metrics provided."
    
    lines = []
    for metric in metrics:
        canonical = normalize_metric(metric)
        weight_note = ""
        if metric_weights:
            # Accept either canonical or original key.
            weight = metric_weights.get(canonical)
            if weight is None:
                weight = metric_weights.get(metric)
            if weight is not None:
                weight_note = f" (weight={weight})"
        description = PHARMA_METRIC_DESCRIPTIONS.get(
            canonical,
            f"Provide an evidence-based assessment for '{canonical}'."
        )
        lines.append(f'- "{canonical}": {description}{weight_note}')
    return "\n".join(lines)


def _extract_json(text: str) -> str:
    """Attempt to extract the first JSON object from arbitrary model text."""
    if not text:
        return "{}"
    # Remove fences
    if text.startswith("```"):
        text = re.sub(r"^```(json)?", "", text.strip(), flags=re.IGNORECASE).strip()
    if text.endswith("```"):
        text = text[:-3].strip()
    # Fast path
    try:
        json.loads(text)
        return text
    except Exception:
        pass
    # Regex object match
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        candidate = match.group(0)
        try:
            json.loads(candidate)
            return candidate
        except Exception:
            return "{}"
    return "{}"


def _chat_json(messages: List[Dict[str, Any]], max_completion_tokens: Optional[int] = None) -> Dict[str, Any]:
    """Call chat.completions ensuring JSON-only output via instruction. Returns parsed dict or {}."""
    
    # Validate setup first
    if not _validate_openai_setup():
        logger.error("❌ OpenAI setup validation failed")
        return {"error": "OpenAI API not configured properly"}

    client = get_openai_client()
    if client is None:
        logger.error("❌ OpenAI API key missing; returning configuration error")
        return {"error": "OpenAI API key not configured"}
    
        # Estimate prompt tokens conservatively
    prompt_text = "".join([part.get("text", "") for m in messages for part in m.get("content", []) if part.get("type") == "text"])
    prompt_tokens = _estimate_tokens_for_text(prompt_text)
    logger.info(f"🤖 Calling GPT-4o: messages={len(messages)}, estimated_prompt_tokens={prompt_tokens}")

    # Compute completion budget if not provided
    if max_completion_tokens is None:
        # Reserve 10% of model max tokens as overhead, and allow remaining for completion
        reserved = max(256, int(MODEL_MAX_TOKENS * 0.1))
        available = max(256, MODEL_MAX_TOKENS - reserved - prompt_tokens)
        # Cap completion tokens to a reasonable ceiling
        max_completion_tokens = min(2048, available)
    logger.info(f"🧮 Using max_completion_tokens={max_completion_tokens} (model_max={MODEL_MAX_TOKENS})")
    
    # Inject enforcement instruction (append to last user message as minimal change)
    enforce = "\n\nReturn ONLY valid JSON. No commentary, no code fences."
    if messages and messages[-1].get("role") == "user":
        # Append to existing text content piece(s)
        for part in messages[-1].get("content", []):
            if part.get("type") == "text":
                part["text"] += enforce
                break
        else:
            messages[-1]["content"].append({"type": "text", "text": enforce})

    try:
        logger.info(f"🚀 Sending request to OpenAI model: {MODEL_NAME}")
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            max_completion_tokens=max_completion_tokens,
        )
        logger.info("✅ OpenAI response received")
        
        raw = response.choices[0].message.content if response.choices else "{}"
        logger.info(f"📝 Raw response length: {len(raw)} chars")
        
        if raw and len(raw) > 0:
            logger.info(f"📝 Raw response preview: {raw[:200]}...")
        else:
            logger.error("❌ Empty response from OpenAI API")
            logger.error("💡 This could indicate API key issues, model access problems, or content policy violations")
            return {"error": "Empty response from OpenAI"}
        
        json_str = _extract_json(raw)
        logger.info(f"🔍 Extracted JSON length: {len(json_str)} chars")
        
        try:
            parsed = json.loads(json_str)
            logger.info(f"✅ JSON parsed successfully, keys: {list(parsed.keys())}")
            return parsed
        except Exception as parse_error:
            logger.error(f"❌ JSON parsing failed: {parse_error}")
            logger.error(f"❌ Failed JSON: {json_str}")
            return {"error": f"JSON parsing failed: {parse_error}", "raw_content": raw[:500]}
            
    except Exception as api_error:
        logger.error(f"❌ OpenAI API call failed: {api_error}")
        if "authentication" in str(api_error).lower():
            logger.error("💡 Authentication error - check your OPENAI_API_KEY")
        elif "quota" in str(api_error).lower():
            logger.error("💡 Quota exceeded - check your OpenAI account billing")
        elif "rate" in str(api_error).lower():
            logger.error("💡 Rate limit exceeded - wait and retry")
        return {"error": f"OpenAI API error: {api_error}"}

def create_cohort_analysis_prompt(
    persona_data: Dict[str, Any],
    persona_type: str,
    stimulus_text: str,
    metrics: List[str],
    questions: Optional[List[str]] = None,
    metric_weights: Optional[Dict[str, float]] = None
) -> str:
    """Create a text-only analysis prompt that is persona and metric aware."""

    persona_label = "healthcare professional" if (persona_type or "").strip().lower() == "hcp" else "patient"
    metric_guidance = format_metric_guidance(metrics, metric_weights=metric_weights)
    persona_snapshot = json.dumps(persona_data, indent=2)

    question_block = ""
    answers_block = ""
    if questions:
        formatted_questions = "\n".join([f"- Q{idx+1}: {q}" for idx, q in enumerate(questions)])
        question_block = f"\n**Qualitative Questions:**\n{formatted_questions}\n"
        answers_block = """,
    "answers": [
        "<response to Q1>",
        "<response to Q2>",
        ...
    ]"""

    prompt = f"""
**Role:** You are an AI expert in pharmaceutical marketing analytics. Simulate how a {persona_label} persona responds to the provided marketing stimulus.

**Persona Profile (verbatim data from research/LLM generation):**
{persona_snapshot}

**Stimulus Text:**
"{stimulus_text}"
{question_block}

**Analysis Instructions:**
- Ground your assessment in the persona's medical condition, motivations, and behavioral context.
- For each requested metric, provide an evidence-based score that reflects how THIS persona would respond.
- Use the metric JSON keys exactly as listed below.

**Metrics to Evaluate:**
{metric_guidance}

**Output Requirements (JSON only):**
{{
    "responses": {{
        "<metric_name>": <value per metric instructions above>
    }},
    "reasoning": "2-3 sentences explaining why the persona responded this way, referencing persona traits."{answers_block}
}}

Ensure numeric scores respect the ranges provided above. For textual metrics (e.g., key_concerns), return the most salient objection in plain text. Do not include metrics that were not requested.
"""

    return prompt

def generate_tool_preamble(persona_count: int, metrics: List[str], stimulus_text: str) -> str:
    """Generates a short tool preamble; deterministic fallback only (removed extra model call for cost)."""
    steps = [
        "Validate inputs and metrics",
        "Simulate persona reactions",
        "Compute cohort statistics",
        "Derive key insights",
        "Return structured JSON",
    ]
    bullets = "\n".join([f"- {s}" for s in steps])
    return (
        f"Analyze {persona_count} persona(s) for stimulus alignment across metrics: {', '.join(metrics) if metrics else 'none'}.\n\n" + bullets
    )

def analyze_persona_response(
    persona_data: Dict[str, Any],
    persona_type: str,
    stimulus_text: str,
    metrics: List[str],
    questions: Optional[List[str]] = None,
    metric_weights: Optional[Dict[str, float]] = None
) -> Dict[str, Any]:
    """Analyzes how a single persona responds to a stimulus using chat completions."""
    normalized_metrics = [normalize_metric(metric) for metric in metrics]
    normalized_weights = None
    if metric_weights:
        # Normalize any legacy metric keys to canonical keys to keep weights aligned.
        normalized_weights = {}
        for key, weight in metric_weights.items():
            normalized_weights[normalize_metric(str(key))] = weight

    prompt = create_cohort_analysis_prompt(
        persona_data,
        persona_type,
        stimulus_text,
        normalized_metrics,
        questions,
        metric_weights=normalized_weights,
    )
    persona_role = "healthcare professional" if (persona_type or "").strip().lower() == "hcp" else "patient"
    messages = [
        {
            "role": "system",
            "content": [
                {
                    "type": "text",
                    "text": f"You are a pharmaceutical marketing analyst specializing in {persona_role} behavior simulation."
                }
            ]
        },
        {"role": "user", "content": [{"type": "text", "text": prompt}]},
    ]
    try:
        data = _chat_json(messages)
        if data.get("error"):
            raise RuntimeError(data["error"])
        filtered = {}
        for metric in normalized_metrics:
            if metric in data.get('responses', {}):
                filtered[metric] = data['responses'][metric]
        answers = data.get('answers') if questions else None
        if questions:
            # Ensure answers align with questions order and length
            normalized_answers: List[str] = []
            for idx, _ in enumerate(questions):
                if isinstance(answers, list) and idx < len(answers):
                    normalized_answers.append(str(answers[idx]))
                else:
                    normalized_answers.append("No answer provided.")
        else:
            normalized_answers = None

        return {
            'responses': filtered,
            'reasoning': data.get('reasoning', 'No reasoning provided.'),
            'answers': normalized_answers
        }
    except Exception as e:
        print(f"Error analyzing persona response: {e}")
        fallback = {}
        for metric in normalized_metrics:
            if metric == 'intent_to_action':
                fallback[metric] = random.randint(3, 8)
            elif metric == 'emotional_response':
                fallback[metric] = round(random.uniform(-0.5, 0.8), 2)
            elif metric == 'brand_trust':
                fallback[metric] = random.randint(4, 9)
            elif metric == 'message_clarity':
                fallback[metric] = random.randint(5, 9)
            elif metric == 'key_concerns':
                fallback[metric] = "Need more information about side effects and effectiveness"
        fallback_answers = ["No answer generated."] * len(questions) if questions else None
        return {
            'responses': fallback,
            'reasoning': 'Analysis failed, using fallback response.',
            'answers': fallback_answers
        }

def calculate_summary_statistics(individual_responses: List[Dict[str, Any]], metrics: List[str]) -> Dict[str, Any]:
    """Calculates summary statistics for the cohort analysis."""
    
    summary = {}
    
    for metric in metrics:
        if metric == 'key_concerns':
            # For text-based metrics, find most common concern
            # Handle both 'responses' (regular analysis) and 'metrics' (multimodal analysis) formats
            concerns = []
            for resp in individual_responses:
                if 'responses' in resp and resp['responses'].get(metric):
                    concerns.append(resp['responses'][metric])
                elif 'metrics' in resp and resp['metrics'].get(metric):
                    metric_data = resp['metrics'][metric]
                    if isinstance(metric_data, str):
                        concerns.append(metric_data)
                    elif isinstance(metric_data, dict) and 'value' in metric_data:
                        concerns.append(metric_data['value'])
            
            if concerns:
                # Simple approach: take the first non-empty concern
                summary[metric] = next((c for c in concerns if c), 'No concerns identified')
        else:
            # For numeric metrics, calculate statistics
            # Handle both 'responses' (regular analysis) and 'metrics' (multimodal analysis) formats
            values = []
            for resp in individual_responses:
                value = None
                if 'responses' in resp and resp['responses'].get(metric) is not None:
                    value = resp['responses'][metric]
                elif 'metrics' in resp and resp['metrics'].get(metric) is not None:
                    metric_data = resp['metrics'][metric]
                    if isinstance(metric_data, (int, float)):
                        value = metric_data
                    elif isinstance(metric_data, dict) and 'score' in metric_data:
                        try:
                            value = float(metric_data['score'])
                        except (ValueError, TypeError):
                            continue
                
                if value is not None:
                    values.append(value)
            
            if values:
                summary[f"{metric}_avg"] = round(sum(values) / len(values), 2)
                summary[f"{metric}_min"] = min(values)
                summary[f"{metric}_max"] = max(values)
                summary[f"{metric}_count"] = len(values)
    
    return summary


def generate_llm_powered_insights_and_suggestions(individual_responses: List[Dict[str, Any]], summary_statistics: Dict[str, Any], stimulus_text: str) -> Dict[str, Any]:
    """
    Uses an LLM to generate cumulative insights and actionable suggestions based on cohort analysis data.
    """
    logger.info("🧠 Generating LLM-powered insights and suggestions...")

    prompt = f"""
    As an expert pharmaceutical marketing analyst, your task is to synthesize the results of a patient persona simulation and provide high-level insights and actionable suggestions.

    **1. The Stimulus Material:**
    The following marketing message was tested:
    "{stimulus_text}"

    **2. Cohort Summary Statistics:**
    Here are the overall performance metrics for the cohort:
    {json.dumps(summary_statistics, indent=2)}

    **3. Individual Persona Responses:**
    Here is a summary of how each individual persona responded, including their reasoning:
    {json.dumps(individual_responses, indent=2)}

    **4. Your Task:**
    Based on all the data above, generate a JSON object with two keys: "cumulative_insights" and "actionable_suggestions".

    - `cumulative_insights`: Provide 2-3 high-level insights summarizing the overall cohort response. What are the key takeaways?
    - `actionable_suggestions`: Provide 2-3 specific, actionable suggestions to improve the ad copy. Each suggestion should be directly linked to the provided data (e.g., "Because many personas flagged 'cost' as a concern, consider adding...").

    **Output Format (JSON only):**
    {{
      "cumulative_insights": [
        "Insight 1...",
        "Insight 2..."
      ],
      "actionable_suggestions": [
        {{
          "suggestion": "Specific suggestion for the ad copy...",
          "reasoning": "This is based on the observation that..."
        }},
        {{
          "suggestion": "Another specific suggestion...",
          "reasoning": "This addresses the low score in..."
        }}
      ]
    }}
    """

    messages = [
        {"role": "system", "content": [{"type": "text", "text": "You are an expert marketing analyst providing insights on persona simulations."}]},
        {"role": "user", "content": [{"type": "text", "text": prompt}]},
    ]

    try:
        response = _chat_json(messages)
        if "error" in response:
            raise ValueError(response["error"])
        
        # Basic validation
        if "cumulative_insights" not in response or "actionable_suggestions" not in response:
            raise ValueError("LLM response missing required keys.")
            
        logger.info("✅ Successfully generated LLM-powered insights and suggestions.")
        return response
    except Exception as e:
        logger.error(f"❌ Failed to generate LLM-powered insights: {e}")
        return {
            "cumulative_insights": ["LLM-powered insight generation failed. Displaying fallback."],
            "actionable_suggestions": [{"suggestion": "Could not generate suggestions due to an error.", "reasoning": str(e)}]
        }


def _extract_metric_value(resp: Dict[str, Any], metric_name: str) -> Any:
    """
    Extract a metric value from a response dict, handling both regular cohort analysis
    ('responses' key) and multimodal analysis ('metrics' key) formats.
    """
    # Try regular cohort format first
    if 'responses' in resp:
        value = resp['responses'].get(metric_name)
        if value is not None:
            return value
    
    # Try multimodal format
    if 'metrics' in resp:
        metric_data = resp['metrics'].get(metric_name)
        if metric_data is not None:
            # Multimodal format may return dict with 'score' key or direct value
            if isinstance(metric_data, dict):
                return metric_data.get('score', metric_data.get('value'))
            return metric_data
    
    return None


def generate_cohort_insights(individual_responses: List[Dict[str, Any]], stimulus_text: str) -> List[str]:
    """Generates insights from the cohort analysis.
    
    Works with both regular cohort analysis ('responses' key) and 
    multimodal analysis ('metrics' key) response formats.
    """
    
    insights = []
    
    # Analyze intent patterns - check both canonical and legacy names
    intent_scores = []
    for resp in individual_responses:
        # Try canonical name first, then legacy alias
        value = _extract_metric_value(resp, 'intent_to_action')
        if value is None:
            value = _extract_metric_value(resp, 'purchase_intent')
        if value is not None and isinstance(value, (int, float)):
            intent_scores.append(float(value))
    
    if intent_scores:
        avg_intent = sum(intent_scores) / len(intent_scores)
        if avg_intent >= 7:
            insights.append("High request/prescribe intent detected - message resonates strongly with the audience.")
        elif avg_intent <= 4:
            insights.append("Low request/prescribe intent - consider revising the value proposition or CTA.")
        else:
            insights.append("Moderate request/prescribe intent - message shows potential but may need refinement.")
    
    # Analyze sentiment patterns
    sentiments = []
    for resp in individual_responses:
        value = _extract_metric_value(resp, 'emotional_response')
        if value is None:
            value = _extract_metric_value(resp, 'sentiment')
        if value is not None and isinstance(value, (int, float)):
            sentiments.append(float(value))
    
    if sentiments:
        avg_sentiment = sum(sentiments) / len(sentiments)
        if avg_sentiment >= 0.5:
            insights.append("Positive sentiment detected - message creates favorable emotional response.")
        elif avg_sentiment <= -0.2:
            insights.append("Negative sentiment detected - message may be causing concern or confusion.")
        else:
            insights.append("Neutral sentiment - message is well-received but may need emotional enhancement.")
    
    # Analyze trust patterns
    trust_scores = []
    for resp in individual_responses:
        value = _extract_metric_value(resp, 'brand_trust')
        if value is None:
            value = _extract_metric_value(resp, 'trust_in_brand')
        if value is not None and isinstance(value, (int, float)):
            trust_scores.append(float(value))
    
    if trust_scores:
        avg_trust = sum(trust_scores) / len(trust_scores)
        if avg_trust >= 7:
            insights.append("High brand trust impact - message effectively builds credibility.")
        elif avg_trust <= 4:
            insights.append("Low brand trust impact - consider adding more credibility elements.")
    
    # Analyze message clarity
    clarity_scores = []
    for resp in individual_responses:
        value = _extract_metric_value(resp, 'message_clarity')
        if value is not None and isinstance(value, (int, float)):
            clarity_scores.append(float(value))
    
    if clarity_scores:
        avg_clarity = sum(clarity_scores) / len(clarity_scores)
        if avg_clarity <= 6:
            insights.append("Message clarity concerns detected - consider simplifying language or adding explanations.")
    
    # Analyze common concerns
    concerns = []
    for resp in individual_responses:
        value = _extract_metric_value(resp, 'key_concerns')
        if value is not None and isinstance(value, str):
            concerns.append(value)
    
    if concerns:
        # Find most common concern patterns
        concern_text = ' '.join(concerns).lower()
        if 'side effect' in concern_text or 'safety' in concern_text:
            insights.append("Safety and side effects are primary concerns - consider addressing these more prominently.")
        if 'cost' in concern_text or 'price' in concern_text:
            insights.append("Cost concerns detected - consider addressing affordability or insurance coverage.")
        if 'effectiveness' in concern_text or 'work' in concern_text:
            insights.append("Effectiveness concerns detected - consider providing more efficacy data or testimonials.")
    
    
    if not insights:
        insights.append("Analysis complete. Consider reviewing individual responses for detailed insights.")
    
    return insights


def _process_single_cohort_persona(
    persona_info: Dict[str, Any],
    stimulus_text: str,
    metrics: List[str],
    questions: Optional[List[str]] = None,
    metric_weights: Optional[Dict[str, float]] = None
) -> Dict[str, Any]:
    """Helper function to process a single persona in a worker thread.
    
    Args:
        persona_info: Dict containing stripped persona attributes (no ORM objects)
        stimulus_text: The evaluation text
        metrics: List of metrics to evaluate
        questions: Optional list of qualitative questions
        metric_weights: Optional weights for metrics
    """
    try:
        # Extract basic info
        persona_id = persona_info['id']
        persona_name = persona_info['name']
        persona_json_str = persona_info.get('full_persona_json')
        
        # Parse JSON
        try:
            persona_data = json.loads(persona_json_str) if persona_json_str else {}
        except Exception:
            persona_data = {}
            
        # Determine type
        local_type = persona_info.get('persona_type') or persona_data.get('persona_type') or "Patient"
        
        # Run analysis (synchronous call to LLM)
        analysis_result = analyze_persona_response(
            persona_data,
            local_type,
            stimulus_text,
            metrics,
            questions,
            metric_weights=metric_weights,
        )
        
        # Return structured result
        return {
            'persona_id': persona_id,
            'persona_name': persona_name,
            'avatar_url': persona_info.get('avatar_url'),
            'persona_type': local_type,
            'responses': analysis_result['responses'],
            'reasoning': analysis_result['reasoning'],
            'answers': analysis_result.get('answers')
        }
    except Exception as e:
        logger.error(f"Error processing persona {persona_info.get('name', 'Unknown')}: {e}")
        return {
            'persona_id': persona_info.get('id'),
            'persona_name': persona_info.get('name', 'Unknown'),
            'error': str(e),
            'responses': {},
            'reasoning': f"Error during processing: {str(e)}",
            'answers': []
        }

def run_cohort_analysis(
    persona_ids: List[int],
    stimulus_text: str,
    metrics: List[str],
    db,
    questions: Optional[List[str]] = None,
    metric_weights: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """Runs a complete cohort analysis for the given personas and stimulus."""
    
    normalized_metrics: List[str] = []
    for metric in metrics:
        canonical = normalize_metric(metric)
        if canonical not in normalized_metrics:
            normalized_metrics.append(canonical)
    metrics = normalized_metrics
    
    # Get persona data from database
    personas = []
    for persona_id in persona_ids:
        persona = crud.get_persona(db, persona_id)
        if persona:
            personas.append(persona)
    
    if not personas:
        raise ValueError("No valid personas found for the provided IDs")
    
    # Optional: generate a brief tool preamble for the UI
    preamble_text = generate_tool_preamble(len(personas), metrics, stimulus_text)

    # Analyze each persona's response
    # Prepare persona data for parallel processing to avoid ORM/Threading issues
    persona_dicts = []
    for persona in personas:
        persona_dicts.append({
            "id": persona.id,
            "name": persona.name,
            "full_persona_json": persona.full_persona_json,
            "persona_type": getattr(persona, "persona_type", None),
            "avatar_url": getattr(persona, 'avatar_url', None)
        })

    # Analyze each persona's response in parallel
    individual_responses = []
    
    # Use ThreadPoolExecutor for parallel processing
    # Max workers capped at 10 to avoid hitting rate limits too hard/fast
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        future_to_persona = {
            executor.submit(
                _process_single_cohort_persona, 
                p_dict, 
                stimulus_text, 
                metrics, 
                questions, 
                metric_weights
            ): p_dict['id'] 
            for p_dict in persona_dicts
        }
        
        for future in concurrent.futures.as_completed(future_to_persona):
            try:
                result = future.result()
                individual_responses.append(result)
            except Exception as exc:
                logger.error(f"Persona processing generated an exception: {exc}")
    
    # Sort responses to match original order (optional, but good for UX)
    # We use a map of ID -> index from the original list
    id_to_index = {p.id: i for i, p in enumerate(personas)}
    individual_responses.sort(key=lambda x: id_to_index.get(x.get('persona_id'), 0))
    
    # Calculate summary statistics
    summary_stats = calculate_summary_statistics(individual_responses, metrics)
    
    # Generate insights
    llm_generated_data = generate_llm_powered_insights_and_suggestions(individual_responses, summary_stats, stimulus_text)
    
    # Combine all results into a single dictionary
    final_analysis = {
        "cohort_size": len(personas),
        "stimulus_text": stimulus_text,
        "metrics_analyzed": metrics,
        "questions": questions or [],
        "individual_responses": individual_responses,
        "summary_statistics": summary_stats,
        "insights": llm_generated_data.get("cumulative_insights", []),
        "suggestions": llm_generated_data.get("actionable_suggestions", []),
        "preamble": preamble_text,
        "created_at": datetime.now().isoformat(),
        "metric_weights": metric_weights or {}
    }
    
    return final_analysis


def create_multimodal_analysis_prompt(
    persona_data: Dict[str, Any],
    stimulus_text: str,
    stimulus_images: List[Dict],
    content_type: str,
    metrics: List[str],
    questions: Optional[List[str]] = None,
    metric_weights: Optional[Dict[str, float]] = None,
) -> str:
    """Creates a prompt for analyzing how a persona responds to multimodal stimulus (text + images)."""
    
    metric_guidance = format_metric_guidance(metrics, metric_weights=metric_weights)
    
    # Build content description
    content_description = ""
    if content_type == 'text':
        content_description = f"Text Message: {stimulus_text}"
    elif content_type == 'image':
        content_description = f"Visual Content: {len(stimulus_images)} image(s) provided"
    elif content_type == 'both':
        content_description = f"Text Message: {stimulus_text}\nVisual Content: {len(stimulus_images)} image(s) provided"
    
    question_block = ""
    if questions:
        formatted_questions = "\n".join([f"- Q{idx+1}: {q}" for idx, q in enumerate(questions)])
        question_block = f"\nQUALITATIVE QUESTIONS:\n{formatted_questions}\n"
    
    # Build metric weights instruction block
    weights_instruction = ""
    if metric_weights:
        normalized_weights = {normalize_metric(k): v for k, v in metric_weights.items()}
        weights_list = ", ".join([f"{k}={v}" for k, v in normalized_weights.items() if v])
        if weights_list:
            weights_instruction = f"""
METRIC WEIGHTS (for weighted scoring):
The following weights indicate relative importance: {weights_list}
When calculating the "weighted_composite_score", multiply each metric score by its weight and sum them.
Metrics without explicit weights should use weight=1.0.
"""

    prompt = f"""
You are analyzing how a specific pharmaceutical persona responds to marketing content. 

PERSONA PROFILE:
- Name: {persona_data.get('name', 'Unknown')}
- Age: {persona_data.get('age', 'Not specified')}
- Gender: {persona_data.get('gender', 'Not specified')}
- Health Condition: {persona_data.get('condition', 'Not specified')}
- Location: {persona_data.get('location', 'Not specified')}

DETAILED PERSONA CHARACTERISTICS:
{json.dumps(persona_data.get('full_persona', {}), indent=2)}

MARKETING CONTENT TO ANALYZE:
{content_description}
{question_block}

ANALYSIS TASK:
Analyze how this specific persona would respond to the provided content. Consider their unique characteristics, health condition, concerns, and behavioral patterns.

For each of the following metrics, provide your analysis (use the JSON keys exactly as listed):

{metric_guidance}
{weights_instruction}

RESPONSE FORMAT:
Provide a JSON response with the following structure:
{{
    "analysis_summary": "Brief overview of how this persona responds to the content",
    "metrics": {{
        // For each requested metric, provide an object with "score" and "reasoning"
        // Example: "intent_to_action": {{"score": 7, "reasoning": "The persona shows..."}}
    }},
    "weighted_composite_score": <number or null>,  // Sum of (score * weight) for all metrics, if weights provided
    "answers": [
        // If qualitative questions were provided, include one answer per question in order.
    ],
    "key_insights": [
        "List of 2-3 key insights about this persona's response"
    ],
    "behavioral_prediction": "How this persona would likely behave after seeing this content"
}}

Be specific and consider the persona's unique characteristics in your analysis.
"""
    
    return prompt


def _process_persona_multimodal(
    persona_dict: Dict[str, Any],  # Changed from ORM object to serialized dict
    stimulus_text: str,
    stimulus_images: List[Dict],
    content_type: str,
    metrics: List[str],
    questions: Optional[List[str]] = None,
    metric_weights: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """
    Process a single persona for multimodal analysis.
    This function is designed to be called in parallel.
    
    Args:
        persona_dict: Serialized persona data dictionary (not SQLAlchemy ORM object)
                     to avoid DetachedInstanceError in worker threads
    """
    persona_id = persona_dict['id']
    persona_name = persona_dict['name']
    logger.info(f"🔄 Processing persona: {persona_name} (ID: {persona_id})")
    
    # Parse the full persona JSON to get all the detailed information
    try:
        full_persona = json.loads(persona_dict['full_persona_json']) if persona_dict.get('full_persona_json') else {}
        logger.info(f"✅ Parsed persona data for {persona_name}")
    except Exception as parse_error:
        logger.error(f"❌ Error parsing persona JSON for {persona_name}: {parse_error}")
        full_persona = {}
    
    # Build persona_data dict from serialized data
    persona_data = {
        'id': persona_dict['id'],
        'name': persona_dict['name'],
        'persona_type': persona_dict.get('persona_type'),
        'age': persona_dict.get('age'),
        'gender': persona_dict.get('gender'),
        'condition': persona_dict.get('condition'),
        'location': persona_dict.get('location'),
        'full_persona': full_persona
    }
    
    # Create multimodal prompt
    logger.info(f"🔄 Creating multimodal prompt for {persona_name}")
    prompt = create_multimodal_analysis_prompt(
        persona_data,
        stimulus_text,
        stimulus_images,
        content_type,
        metrics,
        questions=questions,
        metric_weights=metric_weights,
    )
    logger.info(f"✅ Prompt created, length: {len(prompt)} chars")
    
    # Prepare messages for GPT-5
    messages = [
        {
            "role": "user",
            "content": []
        }
    ]
    
    # Add text content
    messages[0]["content"].append({
        "type": "text",
        "text": prompt
    })
    
    # Add images if provided
    if stimulus_images and content_type in ['image', 'both']:
        logger.info(f"🖼️ Adding {len(stimulus_images)} images to analysis for {persona_name}")
        for j, image_info in enumerate(stimulus_images):
            data_url = f"data:{image_info['content_type']};base64,{image_info['data']}"
            logger.info(f"🖼️ Image {j+1}: {image_info['filename']}, type: {image_info['content_type']}, data URL length: {len(data_url)}")
            messages[0]["content"].append({
                "type": "image_url",
                "image_url": {
                    "url": data_url
                }
            })
    else:
        logger.info(f"📝 Text-only analysis for {persona_name}")
    
    try:
        logger.info(f"🚀 Calling GPT-5 for {persona_name}...")
        logger.info(f"📊 Message content parts: {len(messages[0]['content'])}")
        
        data = _chat_json(messages)
        logger.info(f"✅ GPT-5 response received for {persona_name}")
        logger.info(f"📊 Response keys: {list(data.keys())}")
        
        answers = data.get("answers")
        if questions:
            normalized_answers: List[str] = []
            for idx, _ in enumerate(questions):
                if isinstance(answers, list) and idx < len(answers):
                    normalized_answers.append(str(answers[idx]))
                else:
                    normalized_answers.append("No answer provided.")
        else:
            normalized_answers = None

        result = {
            'persona_id': persona_id,
            'persona_name': persona_data.get('name', f'Persona {persona_id}'),
            'condition': persona_data.get('condition'),
            'analysis_summary': data.get('analysis_summary', ''),
            'metrics': data.get('metrics', {}),
            'answers': normalized_answers,
            'key_insights': data.get('key_insights', []),
            'behavioral_prediction': data.get('behavioral_prediction', ''),
            'raw_response': json.dumps(data)[:500]
        }
        logger.info(f"✅ Analysis completed for {persona_name}")
        return result
        
    except Exception as e:
        logger.error(f"❌ Error analyzing persona {persona_id} ({persona_name}): {e}")
        logger.error(f"❌ Full error traceback:", exc_info=True)
        return {
            'persona_id': persona_id,
            'persona_name': f"Persona {persona_id}",
            'condition': persona_data.get('condition'),
            'analysis_summary': f"Error in analysis: {str(e)}",
            'metrics': {},
            'answers': [],
            'key_insights': [],
            'behavioral_prediction': 'Unable to generate prediction due to error',
            'error': str(e)
        }


def run_multimodal_cohort_analysis(
    persona_ids: List[int],
    stimulus_text: str,
    stimulus_images: List[Dict],
    content_type: str,
    metrics: List[str],
    db,
    metric_weights: Optional[Dict[str, float]] = None,
    questions: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Runs a multimodal cohort analysis using GPT-5's vision capabilities for image processing.
    """
    logger.info(f"🔄 Starting multimodal analysis: {len(persona_ids)} personas, content_type={content_type}")
    logger.info(f"📝 Text length: {len(stimulus_text) if stimulus_text else 0}")
    logger.info(f"🖼️ Images provided: {len(stimulus_images)}")
    logger.info(f"📊 Metrics: {metrics}")
    
    # Get personas from database
    personas = []
    for persona_id in persona_ids:
        persona = crud.get_persona(db, persona_id)
        if persona:
            personas.append(persona)
            logger.info(f"✅ Loaded persona {persona_id}: {persona.name}")
        else:
            logger.error(f"❌ Persona {persona_id} not found in database")
    
    if not personas:
        logger.error("❌ No valid personas found")
        raise ValueError("No valid personas found")
    
    logger.info(f"✅ Loaded {len(personas)} valid personas")
    
    # Serialize persona data BEFORE passing to worker threads
    # SQLAlchemy ORM objects cannot be accessed across threads (DetachedInstanceError)
    persona_data_list = []
    for persona in personas:
        try:
            # Extract all needed attributes into a plain dictionary
            persona_dict = {
                'id': persona.id,
                'name': persona.name,
                'persona_type': persona.persona_type,
                'age': persona.age,
                'gender': persona.gender,
                'condition': persona.condition,
                'location': persona.location,
                'full_persona_json': persona.full_persona_json,  # Serialize JSON string
            }
            persona_data_list.append(persona_dict)
            logger.debug(f"✅ Serialized persona {persona.id}: {persona.name}")
        except Exception as e:
            logger.error(f"❌ Error serializing persona {persona.id}: {e}")
            continue
    
    if not persona_data_list:
        logger.error("❌ No valid persona data after serialization")
        raise ValueError("No valid persona data after serialization")
    
    # Process all personas in parallel using ThreadPoolExecutor
    logger.info(f"🚀 Starting parallel processing of {len(persona_data_list)} personas...")
    individual_responses = []
    
    # Determine the optimal number of workers (max 5 to avoid overwhelming OpenAI API)
    max_workers = min(5, len(persona_data_list))
    logger.info(f"🔧 Using {max_workers} parallel workers for processing")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all persona processing tasks with serialized data
        future_to_persona_id = {
            executor.submit(
                _process_persona_multimodal,
                persona_data,  # Pass serialized dict instead of ORM object
                stimulus_text,
                stimulus_images,
                content_type,
                metrics,
                questions,
                metric_weights,
            ): persona_data['id'] 
            for persona_data in persona_data_list
        }
        
        # Collect results as they complete
        for future in concurrent.futures.as_completed(future_to_persona_id):
            persona_id = future_to_persona_id[future]
            # Find persona name for logging
            persona_name = next((p['name'] for p in persona_data_list if p['id'] == persona_id), f"ID {persona_id}")
            try:
                result = future.result()
                individual_responses.append(result)
                logger.info(f"✅ Completed processing for {persona_name}")
            except Exception as e:
                logger.error(f"❌ Exception occurred while processing {persona_name}: {e}")
                # Find persona condition from serialized data
                persona_condition = next((p.get('condition') for p in persona_data_list if p['id'] == persona_id), None)
                # Add error response for failed persona
                individual_responses.append({
                    'persona_id': persona_id,
                    'persona_name': persona_name,
                    'condition': persona_condition,
                    'analysis_summary': f"Processing error: {str(e)}",
                    'metrics': {},
                    'answers': [],
                    'key_insights': [],
                    'behavioral_prediction': 'Unable to generate prediction due to processing error',
                    'error': str(e)
                })
    
    logger.info(f"🎯 Parallel analysis complete for all personas. Successful: {len([r for r in individual_responses if 'error' not in r])}/{len(individual_responses)}")
    
    # Calculate summary statistics for multimodal analysis
    logger.info("📊 Calculating summary statistics...")
    summary_stats = calculate_summary_statistics(individual_responses, metrics)
    
    # Generate LLM-powered insights and suggestions (same as regular cohort analysis)
    logger.info("💡 Generating LLM-powered insights and suggestions...")
    llm_generated_data = generate_llm_powered_insights_and_suggestions(individual_responses, summary_stats, stimulus_text)
    
    # Create content summary
    content_summary = f"Content Type: {content_type}"
    if stimulus_text:
        content_summary += f" | Text: {stimulus_text[:100]}{'...' if len(stimulus_text) > 100 else ''}"
    if stimulus_images:
        content_summary += f" | Images: {len(stimulus_images)} uploaded"
    
    return {
        'cohort_size': len(personas),
        'content_type': content_type,
        'stimulus_text': stimulus_text,
        'stimulus_images_count': len(stimulus_images) if stimulus_images else 0,
        'content_summary': content_summary,
        'metrics_analyzed': metrics,
        'metric_weights': metric_weights or {},
        'questions': questions or [],
        'individual_responses': individual_responses,
        'summary_statistics': summary_stats,
        'insights': llm_generated_data.get("cumulative_insights", []),
        'suggestions': llm_generated_data.get("actionable_suggestions", []),
        'created_at': datetime.now().isoformat()
    }


def calculate_multimodal_summary_statistics(responses: List[Dict], metrics: List[str]) -> Dict[str, Any]:
    """Calculate summary statistics for multimodal analysis responses."""
    stats = {}
    
    for metric in metrics:
        values = []
        for response in responses:
            metric_data = response.get('metrics', {}).get(metric)
            if isinstance(metric_data, dict) and 'score' in metric_data:
                try:
                    values.append(float(metric_data['score']))
                except (ValueError, TypeError):
                    continue
            elif isinstance(metric_data, (int, float)):
                values.append(float(metric_data))
        
        if values:
            stats[metric] = {
                'mean': sum(values) / len(values),
                'min': min(values),
                'max': max(values),
                'count': len(values)
            }
        else:
            stats[metric] = {
                'mean': 0,
                'min': 0,
                'max': 0,
                'count': 0
            }
    
    return stats


def generate_multimodal_cohort_insights(responses: List[Dict], stimulus_text: str, stimulus_images: List[Dict], content_type: str) -> List[str]:
    """Generate insights for multimodal cohort analysis."""
    insights = []
    
    # Content type specific insights
    if content_type == 'image':
        insights.append(f"Visual-only analysis completed for {len(stimulus_images)} image(s)")
    elif content_type == 'both':
        insights.append(f"Multimodal analysis combining text and {len(stimulus_images)} image(s)")
    
    # Response consistency insights
    successful_responses = [r for r in responses if 'error' not in r]
    if len(successful_responses) < len(responses):
        insights.append(f"{len(responses) - len(successful_responses)} personas had analysis errors")
    
    # Key insights from responses
    all_insights = []
    for response in successful_responses:
        all_insights.extend(response.get('key_insights', []))
    
    if all_insights:
        insights.append(f"Generated {len(all_insights)} total insights across all personas")
    
    return insights
