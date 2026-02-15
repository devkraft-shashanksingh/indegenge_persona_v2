"""
Synthetic Testing Engine for PharmaPersonaSim.

This module provides "Synthetic Testing" capabilities:
1. Objective scoring (1-7 scale) of marketing assets against key metrics.
2. Structured qualitative feedback (What works, what doesn't, improvements).
3. Aggregation of results across multiple personas and assets.
"""

import os
import json
import logging
import base64
import concurrent.futures
from typing import Dict, Any, List, Optional
from datetime import datetime

from .utils import get_openai_client, MODEL_NAME
from . import crud

# Configure logging
logger = logging.getLogger(__name__)

# Model token limit
MODEL_MAX_TOKENS = int(os.getenv("OPENAI_MODEL_MAX_TOKENS", "32768"))

def _extract_json(text: str) -> str:
    """Attempt to extract the first JSON object from arbitrary model text."""
    import re
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

def _chat_json_synthetic(messages: List[Dict[str, Any]], max_completion_tokens: Optional[int] = None) -> Dict[str, Any]:
    """Call chat.completions ensuring JSON-only output."""
    client = get_openai_client()
    if client is None:
        return {"error": "OpenAI API key not configured"}
    
    if max_completion_tokens is None:
        max_completion_tokens = 2048
    
    enforce = "\n\nReturn ONLY valid JSON. No commentary."
    if messages and messages[-1].get("role") == "user":
        for part in messages[-1].get("content", []):
            if part.get("type") == "text":
                part["text"] += enforce
                break
        else:
            messages[-1]["content"].append({"type": "text", "text": enforce})

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            max_completion_tokens=max_completion_tokens,
            temperature=0.4, # Lower temperature for stable scoring
            response_format={"type": "json_object"}
        )
        
        raw = response.choices[0].message.content if response.choices else "{}"
        return json.loads(_extract_json(raw))
            
    except Exception as e:
        logger.error(f"❌ OpenAI API call failed: {e}")
        return {"error": f"Analysis failed: {str(e)}"}

def create_synthetic_prompt(
    persona: Dict[str, Any],
    asset_name: str,
    stimulus_text: str,
    has_image: bool
) -> str:
    """Creates the prompt for synthetic testing."""
    
    # Extract key persona attributes
    full_persona = persona.get('full_persona', {})
    segment = full_persona.get('persona_subtype') or full_persona.get('segment', 'Standard')
    role = full_persona.get('specialty') or persona.get('condition', 'Patient')
    
    content_desc = f"Message: \"{stimulus_text}\"" if stimulus_text else ""
    if has_image:
        content_desc += "\n(See attached image)"

    return f"""
You are simulating {persona['name']}, a {role} ({segment}), evaluating a pharmaceutical marketing asset named "{asset_name}".

**YOUR PROFILE:**
- Age: {persona['age']}
- Gender: {persona['gender']}
- Location: {persona['location']}
- Bio: {json.dumps(full_persona.get('core', {}), indent=2)}
- Additional Context: {json.dumps(persona.get('additional_context', {}), indent=2)}

**MARKETING ASSET:**
{content_desc}

**TASK:**
Evaluate this asset objectively on a 1-7 scale (1 = Poor/Low, 7 = Excellent/High) and provide specific qualitative feedback.

**GUIDELINES FOR FEEDBACK:**
- **BE CONCISE**: Use short, punchy bullet points (maximum 15 words per bullet).
- **BE DIRECT**: Go straight to the point. No fluff.
- **AVOID MARKETER ARGOT**: Speak as the patient/HCP would naturally but clearly.

**METRICS TO SCORE (1-7):**
1. **Motivation to Prescribe** (or "Ask for" if patient): How strongly does this motivate action?
2. **Connection to Story**: Does the narrative/visual connect with your reality?
3. **Differentiation**: Is this unique compared to other treatments?
4. **Believability**: Do you trust this message?
5. **Stopping Power**: Does this grab your attention immediately?

**QUALITATIVE FEEDBACK SECTIONS:**
1. **Does Well**: What this cover concept does well.
2. **Challenges**: What this cover concept does NOT do as well.
3. **Considerations**: Considerations to improve the cover concept.

**OUTPUT JSON FORMAT:**
{{
    "scores": {{
        "motivation_to_prescribe": <1-7 int>,
        "connection_to_story": <1-7 int>,
        "differentiation": <1-7 int>,
        "believability": <1-7 int>,
        "stopping_power": <1-7 int>
    }},
    "feedback": {{
        "does_well": ["<concise bullet 1>", "<concise bullet 2>"],
        "does_not_do_well": ["<concise bullet 1>", "<concise bullet 2>"],
        "considerations": ["<concise bullet 1>", "<concise bullet 2>"]
    }}
}}
"""

def analyze_single_asset_persona(
    persona_dict: Dict[str, Any],
    asset: Dict[str, Any]
) -> Dict[str, Any]:
    """Analyze one asset for one persona."""
    
    asset_name = asset.get('name', 'Unnamed Asset')
    image_data = asset.get('data') 
    text_content = asset.get('text', '')
    
    prompt = create_synthetic_prompt(
        persona_dict, 
        asset_name, 
        text_content, 
        has_image=bool(image_data)
    )
    
    messages = [{"role": "user", "content": []}]
    messages[0]["content"].append({"type": "text", "text": prompt})
    
    if image_data:
        # data is base64 string
        messages[0]["content"].append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{image_data}"}
        })
        
    result = _chat_json_synthetic(messages)
    
    if "error" in result:
        return {
            "persona_id": persona_dict['id'],
            "asset_id": asset.get('id'),
            "error": result["error"]
        }
        
    # Calculate Overall Preference (Aggregate of 5 metrics)
    scores = result.get("scores", {})
    total_score = sum(scores.values()) if scores else 0
    # Normalize 5-35 sum to 0-100% preference
    # (Score - 5) / (35 - 5) * 100 roughly
    # Actually, simpler: Average score (1.0-7.0) 
    # Let's map 1->0%, 4->50%, 7->100%
    avg_score = total_score / 5.0 if scores else 0
    preference_pct = int(((avg_score - 1) / 6.0) * 100) if avg_score >= 1 else 0
    
    return {
        "persona_id": persona_dict['id'],
        "persona_name": persona_dict['name'],
        "asset_id": asset.get('id'),
        "scores": scores,
        "overall_preference_score": preference_pct,
        "feedback": result.get("feedback", {})
    }

def run_synthetic_testing(
    persona_ids: List[int],
    assets: List[Dict[str, Any]],
    db = None
) -> Dict[str, Any]:
    """
    Run synthetic testing for multiple assets and personas.
    
    Args:
        persona_ids: List of persona IDs
        assets: List of dicts {id: str, name: str, data: str|None, text: str}
    """
    
    # Fetch personas
    try:
        personas = []
        for pid in persona_ids:
            p = crud.get_persona(db, pid)
            if p:
                personas.append({
                    'id': p.id,
                    'name': p.name,
                    'age': p.age,
                    'gender': p.gender,
                    'location': p.location,
                    'condition': p.condition,
                    'condition': p.condition,
                    'full_persona': json.loads(p.full_persona_json) if getattr(p, 'full_persona_json', None) else {},
                    'additional_context': p.additional_context or {}
                })
                
        if not personas:
            return {"error": "No valid personas found"}

        results = []
        
        # Process all combinations in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = []
            for persona in personas:
                for asset in assets:
                    futures.append(
                        executor.submit(analyze_single_asset_persona, persona, asset)
                    )
                    
            for future in concurrent.futures.as_completed(futures):
                try:
                    res = future.result()
                    results.append(res)
                except Exception as e:
                    import traceback
                    logger.error(f"Analysis task failed: {e}\n{traceback.format_exc()}")

        # Aggregation
        aggregated_results = {} # asset_id -> {metrics_avg, feedback_summary}
        
        for asset in assets:
            a_id = asset['id']
            asset_responses = [r for r in results if r.get('asset_id') == a_id and 'error' not in r]
            
            if not asset_responses:
                continue
                
            # Calc averages
            count = len(asset_responses)
            avg_scores = {
                "motivation_to_prescribe": 0.0,
                "connection_to_story": 0.0,
                "differentiation": 0.0,
                "believability": 0.0,
                "stopping_power": 0.0
            }
            avg_pref = 0.0
            
            for r in asset_responses:
                s = r.get('scores', {})
                if not s: continue # Skip if scores missing
                for k in avg_scores:
                    avg_scores[k] += s.get(k, 0)
                avg_pref += r.get('overall_preference_score', 0)
                
            for k in avg_scores:
                avg_scores[k] = round(avg_scores[k] / count, 1) if count > 0 else 0
            
            aggregated_results[a_id] = {
                "asset_name": asset['name'],
                "average_scores": avg_scores,
                "average_preference": int(avg_pref / count) if count > 0 else 0,
                "respondent_count": count
            }

        return {
            "results": results,
            "aggregated": aggregated_results,
            "metadata": {
                "personas_count": len(personas),
                "assets_count": len(assets),
                "timestamp": datetime.now().isoformat()
            }
        }
    except Exception as e:
        import traceback
        logger.error(f"Global synthetic testing error: {e}\n{traceback.format_exc()}")
        raise e
