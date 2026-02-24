"""
Panel Feedback Engine for PharmaPersonaSim.

This module provides structured persona panel feedback analysis for marketing assets.
Each persona provides independent feedback with standardized sections:
- Clean Read (initial interpretation)
- Key Themes (what resonates)
- Strengths (what works)
- Weaknesses (concerns/issues)

The engine also synthesizes a summary with aggregated themes, dissent highlights,
and actionable recommendations.
"""

import os
import json
import logging
import json
import uuid
import concurrent.futures
from typing import Dict, Any, List, Optional
from datetime import datetime

from .utils import get_openai_client, MODEL_NAME
from . import crud

# Configure logging
logger = logging.getLogger(__name__)

# Model token limit (allow overriding via env)
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


def _chat_json_panel(messages: List[Dict[str, Any]], max_completion_tokens: Optional[int] = None) -> Dict[str, Any]:
    """Call chat.completions ensuring JSON-only output. Returns parsed dict or {}."""
    
    client = get_openai_client()
    if client is None:
        logger.error("❌ OpenAI API key missing")
        return {"error": "OpenAI API key not configured"}
    
    # Compute completion budget if not provided
    if max_completion_tokens is None:
        max_completion_tokens = 2048
    
    # Inject enforcement instruction
    enforce = "\n\nReturn ONLY valid JSON. No commentary, no code fences."
    if messages and messages[-1].get("role") == "user":
        for part in messages[-1].get("content", []):
            if part.get("type") == "text":
                part["text"] += enforce
                break
        else:
            messages[-1]["content"].append({"type": "text", "text": enforce})

    try:
        logger.info(f"🚀 Sending panel feedback request to {MODEL_NAME}")
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            max_completion_tokens=max_completion_tokens,
        )
        
        raw = response.choices[0].message.content if response.choices else "{}"
        
        if not raw or len(raw) == 0:
            logger.error("❌ Empty response from OpenAI API")
            return {"error": "Empty response from OpenAI"}
        
        json_str = _extract_json(raw)
        
        try:
            parsed = json.loads(json_str)
            return parsed
        except Exception as parse_error:
            logger.error(f"❌ JSON parsing failed: {parse_error}")
            return {"error": f"JSON parsing failed: {parse_error}"}
            
    except Exception as api_error:
        logger.error(f"❌ OpenAI API call failed: {api_error}")
        return {"error": f"OpenAI API error: {api_error}"}


def create_panel_feedback_prompt(
    persona_data: Dict[str, Any],
    stimulus_text: str,
    stimulus_images: Optional[List[Dict]] = None,
    content_type: str = "text"
) -> str:
    """
    Creates a prompt for structured panel feedback analysis.
    
    The persona will analyze the marketing asset and provide feedback in
    standardized sections: Clean Read, Key Themes, Strengths, Weaknesses.
    """
    
    persona_name = persona_data.get('name', 'Unknown')
    persona_type = persona_data.get('persona_type', 'Patient')
    full_persona = persona_data.get('full_persona', {})
    
    # Extract key characteristics from persona
    segment = full_persona.get('persona_subtype', '') or full_persona.get('segment', '')
    decision_style = full_persona.get('decision_style', '')
    
    # Get role/specialty for HCPs
    role = ''
    if persona_type.lower() == 'hcp':
        role = full_persona.get('specialty') or full_persona.get('role', 'Healthcare Professional')
    else:
        role = full_persona.get('condition', 'Patient')
    
    # Extract key characteristics as list
    characteristics = []
    if decision_style:
        characteristics.append(decision_style)
    if segment:
        characteristics.append(segment)
    
    mbt = full_persona.get('core', {}).get('mbt', {})
    if mbt:
        # Add a key motivation or belief as characteristic
        motivations = mbt.get('motivations', [])
        if motivations:
            first_mot = motivations[0] if isinstance(motivations[0], str) else motivations[0].get('text', '')
            if first_mot and len(first_mot) < 50:
                characteristics.append(first_mot)
    
    characteristics_str = ', '.join(characteristics[:3]) if characteristics else 'Not specified'
    
    # Build content description
    content_description = ""
    if content_type == 'text':
        content_description = f"Marketing Message:\n\"{stimulus_text}\""
    elif content_type == 'image':
        image_count = len(stimulus_images) if stimulus_images else 0
        content_description = f"Visual Content: {image_count} image(s) provided for analysis"
    elif content_type == 'both':
        image_count = len(stimulus_images) if stimulus_images else 0
        content_description = f"Marketing Message:\n\"{stimulus_text}\"\n\nVisual Content: {image_count} image(s) provided for analysis"
    
    prompt = f"""
You are a pharmaceutical marketing analyst simulating how a specific persona would evaluate a marketing asset.

**PERSONA PROFILE:**
- Name: {persona_name}
- Type: {persona_type}
- Role/Condition: {role}
- Key Characteristics: {characteristics_str}

**DETAILED PERSONA DATA:**
{json.dumps(full_persona, indent=2)[:3000]}

**MARKETING ASSET TO ANALYZE:**
{content_description}

**YOUR TASK:**
Analyze this marketing asset from the perspective of this persona. Provide your analysis in the following structured format:

1. **Clean Read**: Your initial, gut interpretation of the asset. What does it say to you? What's the first impression?

2. **Key Themes**: What themes or messages resonate with you as this persona? What catches your attention? (2-4 themes)

3. **Strengths**: What works well about this asset from your perspective? What would make you engage positively? (2-4 points)

4. **Weaknesses**: What concerns you? What doesn't work? What's missing or confusing? (2-4 points)

**OUTPUT FORMAT (JSON only):**
{{
    "persona_header": {{
        "name": "{persona_name}",
        "role": "<role/specialty or condition>",
        "segment": "<primary segment or decision style>",
        "key_characteristics": ["<characteristic 1>", "<characteristic 2>", "<characteristic 3>"]
    }},
    "clean_read": "<1-3 sentences describing initial interpretation>",
    "key_themes": [
        "<theme 1>",
        "<theme 2>",
        "<theme 3>"
    ],
    "strengths": [
        "<strength 1>",
        "<strength 2>"
    ],
    "weaknesses": [
        "<weakness 1>",
        "<weakness 2>"
    ]
}}

Be specific and ground your analysis in the persona's unique characteristics, concerns, and perspective.
"""
    
    return prompt


def analyze_single_persona_panel(
    persona_dict: Dict[str, Any],
    stimulus_text: str,
    stimulus_images: Optional[List[Dict]] = None,
    content_type: str = "text"
) -> Dict[str, Any]:
    """
    Analyze a single persona's panel feedback response.
    Designed to be called in parallel.
    """

    logger.info("This is the logger for checking data to genertae person panel")
    logger.info(stimulus_images)
    persona_id = persona_dict['id']
    persona_name = persona_dict['name']
    logger.info(f"🔄 Processing panel feedback for: {persona_name} (ID: {persona_id})")
    
    # Parse full persona JSON
    try:
        full_persona = json.loads(persona_dict.get('full_persona_json', '{}')) if persona_dict.get('full_persona_json') else {}
    except Exception as parse_error:
        logger.error(f"❌ Error parsing persona JSON for {persona_name}: {parse_error}")
        full_persona = {}
    
    # Build persona_data dict
    persona_data = {
        'id': persona_dict['id'],
        'name': persona_dict['name'],
        'persona_type': persona_dict.get('persona_type', 'Patient'),
        'age': persona_dict.get('age'),
        'gender': persona_dict.get('gender'),
        'condition': persona_dict.get('condition'),
        'location': persona_dict.get('location'),
        'avatar_url': persona_dict.get('avatar_url'),
        'full_persona': full_persona
    }
    
    # Create prompt
    prompt = create_panel_feedback_prompt(
        persona_data,
        stimulus_text,
        stimulus_images,
        content_type
    )
    
    # Prepare messages
    messages = [{"role": "user", "content": []}]
    messages[0]["content"].append({"type": "text", "text": prompt})
    
    # Add images if provided
    if stimulus_images and content_type in ['image', 'both']:
        for image_info in stimulus_images:
            data_url = f"data:{image_info['content_type']};base64,{image_info['data']}"
            messages[0]["content"].append({
                "type": "image_url",
                "image_url": {"url": data_url}
            })
    
    try:
        data = _chat_json_panel(messages)
        
        if data.get("error"):
            raise RuntimeError(data["error"])
        
        # Extract and structure the response
        header = data.get("persona_header", {})
        
        result = {
            "persona_id": persona_id,
            "persona_name": persona_name,
            "role": header.get("role", persona_dict.get('condition', '')),
            "segment": header.get("segment", full_persona.get('persona_subtype', '')),
            "key_characteristics": header.get("key_characteristics", []),
            "avatar_url": persona_dict.get('avatar_url'),
            "clean_read": data.get("clean_read", "No interpretation provided."),
            "key_themes": data.get("key_themes", []),
            "strengths": data.get("strengths", []),
            "weaknesses": data.get("weaknesses", [])
        }
        
        logger.info(f"✅ Panel feedback completed for {persona_name}")
        return result
        
    except Exception as e:
        logger.error(f"❌ Error analyzing panel feedback for {persona_id}: {e}")
        return {
            "persona_id": persona_id,
            "persona_name": persona_name,
            "role": persona_dict.get('condition', ''),
            "segment": "",
            "key_characteristics": [],
            "avatar_url": persona_dict.get('avatar_url'),
            "clean_read": f"Error in analysis: {str(e)}",
            "key_themes": [],
            "strengths": [],
            "weaknesses": [],
            "error": str(e)
        }


def synthesize_panel_summary(
    persona_cards: List[Dict[str, Any]],
    stimulus_text: str
) -> Dict[str, Any]:
    """
    Synthesize a summary from all persona panel feedback.
    
    Generates:
    - Aggregated themes ("3 of 5 personas flagged X")
    - Dissent highlights ("While 4 personas liked Y, Persona Z disagreed")
    - Actionable recommendations
    """
    
    # Prepare summary of all responses for the synthesis prompt
    cards_summary = []
    for card in persona_cards:
        cards_summary.append({
            "name": card.get("persona_name"),
            "role": card.get("role"),
            "key_themes": card.get("key_themes", []),
            "strengths": card.get("strengths", []),
            "weaknesses": card.get("weaknesses", [])
        })
    
    prompt = f"""
You are an expert pharmaceutical marketing analyst. You have collected panel feedback from {len(persona_cards)} personas analyzing a marketing asset.

**STIMULUS:**
"{stimulus_text[:1000]}"

**INDIVIDUAL PERSONA FEEDBACK:**
{json.dumps(cards_summary, indent=2)}

**YOUR TASK:**
Synthesize the feedback from all personas into a cohesive summary. Focus on:

1. **Aggregated Themes**: What patterns emerge? Use statements like "3 of 5 personas mentioned..." or "The majority flagged..."

2. **Dissent Highlights**: Where do personas disagree? Highlight cases like "While most personas liked X, [Name] found it concerning because..."

3. **Actionable Recommendations**: Based on the collective feedback, what specific changes would improve the asset?

**OUTPUT FORMAT (JSON only):**
{{
    "aggregated_themes": [
        "<pattern 1 with counts, e.g., '4 of 5 personas flagged missing safety data'>",
        "<pattern 2>",
        "<pattern 3>"
    ],
    "dissent_highlights": [
        "<disagreement 1, naming the dissenting persona>",
        "<disagreement 2>"
    ],
    "recommendations": [
        {{
            "suggestion": "<specific actionable change>",
            "reasoning": "<based on which personas' feedback>"
        }},
        {{
            "suggestion": "<another change>",
            "reasoning": "<supporting evidence>"
        }}
    ]
}}

Be specific and reference persona names when highlighting dissent. Focus on actionable insights.
"""
    
    messages = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
    
    try:
        data = _chat_json_panel(messages, max_completion_tokens=1500)
        
        if data.get("error"):
            raise RuntimeError(data["error"])
        
        return {
            "aggregated_themes": data.get("aggregated_themes", []),
            "dissent_highlights": data.get("dissent_highlights", []),
            "recommendations": data.get("recommendations", [])
        }
        
    except Exception as e:
        logger.error(f"❌ Error synthesizing panel summary: {e}")
        return {
            "aggregated_themes": ["Unable to generate aggregated themes due to error."],
            "dissent_highlights": [],
            "recommendations": [{"suggestion": "Review individual persona feedback for insights.", "reasoning": str(e)}]
        }


def run_panel_feedback_analysis(
    persona_ids: List[int],
    stimulus_text: str,
    stimulus_images: Optional[List[Dict]] = None,
    content_type: str = "text",
    db = None
) -> Dict[str, Any]:
    """
    Run structured panel feedback analysis for the given personas.
    
    Args:
        persona_ids: List of persona IDs to include in the panel
        stimulus_text: Text content of the marketing asset
        stimulus_images: Optional list of images (base64 encoded)
        content_type: 'text', 'image', or 'both'
        db: Database session
    
    Returns:
        Dict containing persona_cards, summary, and metadata
    """
    
    if not persona_ids:
        raise ValueError("At least one persona ID is required")
    
    # Fetch personas from database
    personas = []
    for persona_id in persona_ids:
        persona = crud.get_persona(db, persona_id)
        if persona:
            # Serialize to dict to avoid DetachedInstanceError in threads
            personas.append({
                'id': persona.id,
                'name': persona.name,
                'age': persona.age,
                'gender': persona.gender,
                'condition': persona.condition,
                'location': persona.location,
                'persona_type': persona.persona_type,
                'avatar_url': getattr(persona, 'avatar_url', None),
                'full_persona_json': persona.full_persona_json
            })
    
    if not personas:
        raise ValueError("No valid personas found for the provided IDs")
    
    logger.info(f"🎯 Running panel feedback for {len(personas)} personas")
    
    # Process personas in parallel
    persona_cards = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(5, len(personas))) as executor:
        futures = {
            executor.submit(
                analyze_single_persona_panel,
                persona_dict,
                stimulus_text,
                stimulus_images,
                content_type
            ): persona_dict['id']
            for persona_dict in personas
        }
        
        for future in concurrent.futures.as_completed(futures):
            try:
                result = future.result()
                persona_cards.append(result)
            except Exception as e:
                persona_id = futures[future]
                logger.error(f"❌ Panel feedback failed for persona {persona_id}: {e}")
                persona_cards.append({
                    "persona_id": persona_id,
                    "persona_name": f"Persona {persona_id}",
                    "error": str(e)
                })
    
    # Sort by persona_id for consistent ordering
    persona_cards.sort(key=lambda x: x.get('persona_id', 0))
    
    # Synthesize summary
    logger.info("📊 Synthesizing panel summary...")
    summary = synthesize_panel_summary(persona_cards, stimulus_text)
    
    # Build final result
    result = {
        "persona_cards": persona_cards,
        "summary": summary,
        "metadata": {
            "persona_count": len(personas),
            "content_type": content_type,
            "created_at": datetime.now().isoformat()
        }
    }
    
    logger.info(f"✅ Panel feedback analysis complete for {len(personas)} personas")
    return result




# def run_panel_feedback_analysis_v2(
#     campaign_id:str,
#     task_id:str,
#     persona_ids: List[int],
#     stimulus_text: str,
#     stimulus_images: Optional[List[Dict]] = None,
#     content_type: str = "text",
#     db=None
# ) -> Dict[str, Any]:
#     """
#     Panel feedback v2 (FORCED CARTESIAN MODE):

#     ✅ If stimulus_images is a non-empty list:
#        persona_cards = (number of personas) x (number of images)
#        Example: 3 personas, 2 images => 6 cards
#        Each card analyzes exactly ONE image and includes persona_id + image_id/url.

#     ✅ If no images:
#        old behavior: 1 card per persona

#     FIXES:
#     ✅ Per-card summaries (NxM) generated concurrently (max_workers=5)
#     ✅ Output grouped by IMAGE:
#        images: [
#          { image_id, image_url, image_url_str, cards: [ {card + summary}, ... ] },
#          ...
#        ]
#     ✅ Each card includes its own summary inline (no separate summary_by_card needed for UI)
#     ✅ JSON-safe response to avoid FastAPI 500 / anyio.EndOfStream
#     ✅ card_key is UUID (generated uuid4) but returned as string in JSON (required)
#     """

#     import json
#     import uuid
#     from datetime import datetime

#     def _json_safe(x):
#         if x is None:
#             return None
#         if isinstance(x, (str, int, float, bool)):
#             return x
#         if isinstance(x, uuid.UUID):
#             return str(x)
#         if isinstance(x, datetime):
#             return x.isoformat()
#         if isinstance(x, dict):
#             return {str(_json_safe(k)): _json_safe(v) for k, v in x.items()}
#         if isinstance(x, (list, tuple, set)):
#             return [_json_safe(v) for v in list(x)]
#         return str(x)

#     if not persona_ids:
#         raise ValueError("At least one persona ID is required")

#     # -------------------------------
#     # Fetch personas from database
#     # -------------------------------
#     personas: List[Dict[str, Any]] = []
#     for persona_id in persona_ids:
#         persona = crud.get_persona(db, persona_id)
#         if persona:
#             personas.append({
#                 "id": persona.id,
#                 "name": persona.name,
#                 "age": persona.age,
#                 "gender": persona.gender,
#                 "condition": persona.condition,
#                 "location": persona.location,
#                 "persona_type": persona.persona_type,
#                 "avatar_url": getattr(persona, "avatar_url", None),
#                 "full_persona_json": persona.full_persona_json,
#             })

#     if not personas:
#         raise ValueError("No valid personas found for the provided IDs")

#     logger.info(f"🎯 Running panel feedback for {len(personas)} personas")

#     # -------------------------------
#     # Debug logs
#     # -------------------------------
#     logger.info(
#         f"[panel-feedback-v2] content_type={content_type} | "
#         f"stimulus_images_type={type(stimulus_images)} | "
#         f"stimulus_images_len={(len(stimulus_images) if isinstance(stimulus_images, list) else 'NA')} | "
#         f"stimulus_images_truthy={bool(stimulus_images)}"
#     )
#     if isinstance(stimulus_images, list) and stimulus_images:
#         first = stimulus_images[0]
#         logger.info(
#             f"[panel-feedback-v2] first_image_type={type(first)} | "
#             f"first_image_keys={list(first.keys()) if isinstance(first, dict) else 'NA'}"
#         )

#     # -------------------------------
#     # Decide NxM purely on images presence
#     # -------------------------------
#     has_images = isinstance(stimulus_images, list) and len(stimulus_images) > 0

#     # -------------------------------
#     # Build jobs (assign card_number + card_key BEFORE LLM call)
#     # Order matches final sort: image first, then persona
#     # -------------------------------
#     jobs: List[tuple] = []

#     if has_images:
#         total_cards = len(personas) * len(stimulus_images)
#         logger.info(
#             f"🧩 Running FORCED CARTESIAN panel: {len(personas)} personas x "
#             f"{len(stimulus_images)} images -> {total_cards} persona_cards"
#         )

#         for img_idx, img in enumerate(stimulus_images):
#             for persona_idx, persona_dict in enumerate(personas):
#                 card_number = (img_idx * len(personas)) + persona_idx + 1

#                 image_id = img.get("id") if isinstance(img, dict) else None
#                 image_url = img.get("url") if isinstance(img, dict) else None
#                 image_url_str = img.get("image_url_str") if isinstance(img, dict) else None

#                 image_id_safe = str(image_id) if isinstance(image_id, uuid.UUID) else image_id

#                 # ✅ card_key is UUID (store as UUID internally)
#                 card_key = uuid.uuid4()

#                 jobs.append((
#                     persona_idx,       # persona_index
#                     img_idx,           # image_index
#                     persona_dict,      # persona_dict
#                     img,               # single_img
#                     card_number,       # card_number
#                     card_key,          # card_key (UUID)
#                     image_id_safe,     # image_id
#                     image_url,         # image_url
#                     image_url_str      # image_url_str
#                 ))
#     else:
#         logger.info("🧩 Running OLD panel (no images): 1 card per persona")
#         for persona_idx, persona_dict in enumerate(personas):
#             card_number = persona_idx + 1
#             card_key = uuid.uuid4()
#             jobs.append((
#                 persona_idx,
#                 None,
#                 persona_dict,
#                 None,
#                 card_number,
#                 card_key,
#                 None,
#                 None,
#                 None
#             ))

#     # -------------------------------
#     # Execute persona_cards in parallel
#     # -------------------------------
#     persona_cards: List[Dict[str, Any]] = []
#     max_workers = min(5, len(jobs)) if jobs else 1

#     with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
#         futures = {}

#         for persona_index, image_index, persona_dict, single_img, card_number, card_key, image_id, image_url, image_url_str in jobs:
#             card_context = {
#                 "card_number": card_number,
#                 "card_key": str(card_key),  # ✅ put as string into prompt
#                 "persona_id": persona_dict["id"],
#                 "persona_name": persona_dict.get("name"),
#                 "image_id": image_id,
#                 "image_url": image_url,
#                 "image_url_str": image_url_str,
#                 "image_index": image_index,
#                 "persona_index": persona_index,
#             }

#             injected_stimulus_text = (
#                 "### CARD_CONTEXT (MUST RETURN AS-IS IN OUTPUT JSON)\n"
#                 f"{json.dumps(_json_safe(card_context), ensure_ascii=False)}\n"
#                 "### END_CARD_CONTEXT\n\n"
#                 f"{stimulus_text}"
#             )

#             if has_images:
#                 future = executor.submit(
#                     analyze_single_persona_panel,
#                     persona_dict,
#                     injected_stimulus_text,
#                     [single_img],
#                     content_type
#                 )
#             else:
#                 future = executor.submit(
#                     analyze_single_persona_panel,
#                     persona_dict,
#                     injected_stimulus_text,
#                     None,
#                     content_type
#                 )

#             futures[future] = {
#                 "persona_id": persona_dict["id"],
#                 "persona_name": persona_dict.get("name"),
#                 "persona_index": persona_index,
#                 "image_index": image_index,
#                 "image": single_img,
#                 "card_number": card_number,
#                 "card_key": card_key,  # UUID
#                 "image_id": image_id,
#                 "image_url": image_url,
#                 "image_url_str": image_url_str,
#             }

#         for future in concurrent.futures.as_completed(futures):
#             meta = futures[future]
#             try:
#                 result = future.result()

#                 # enforce mapping keys on returned card
#                 result["card_number"] = meta["card_number"]
#                 result["card_key"] = str(meta["card_key"])  # ✅ return as string in JSON

#                 result["persona_id"] = meta["persona_id"]
#                 if meta.get("persona_name"):
#                     result["persona_name"] = meta["persona_name"]
#                 result["persona_index"] = meta["persona_index"]

#                 if has_images:
#                     result["image_index"] = meta["image_index"]
#                     if meta.get("image_id") is not None:
#                         result["image_id"] = meta["image_id"]
#                     if meta.get("image_url") is not None:
#                         result["image_url"] = meta["image_url"]
#                     if meta.get("image_url_str") is not None:
#                         result["image_url_str"] = meta["image_url_str"]

#                 persona_cards.append(_json_safe(result))

#             except Exception as e:
#                 logger.error(
#                     f"❌ Panel feedback failed for persona {meta['persona_id']} "
#                     f"(image_index={meta.get('image_index')}): {e}"
#                 )

#                 err_obj = {
#                     "error": str(e),
#                     "card_number": meta["card_number"],
#                     "card_key": str(meta["card_key"]),  # ✅ string
#                     "persona_id": meta["persona_id"],
#                     "persona_name": meta.get("persona_name") or f"Persona {meta['persona_id']}",
#                     "persona_index": meta.get("persona_index"),
#                 }

#                 if has_images:
#                     err_obj["image_index"] = meta["image_index"]
#                     if meta.get("image_id") is not None:
#                         err_obj["image_id"] = meta["image_id"]
#                     if meta.get("image_url") is not None:
#                         err_obj["image_url"] = meta["image_url"]
#                     if meta.get("image_url_str") is not None:
#                         err_obj["image_url_str"] = meta["image_url_str"]

#                 persona_cards.append(_json_safe(err_obj))

#     # Ordering: image first, then persona
#     if has_images:
#         persona_cards.sort(key=lambda x: (x.get("image_index", 0), x.get("persona_index", 0)))
#     else:
#         persona_cards.sort(key=lambda x: x.get("persona_id", 0))

#     # -------------------------------
#     # PER-CARD SUMMARY (NxM) - CONCURRENT (max_workers=5)
#     # -------------------------------
#     logger.info("📊 Synthesizing PER-CARD summaries (concurrent)...")

#     # build lookup by card_key so we can attach summary into the same card
#     summary_lookup: Dict[str, Any] = {}
#     summary_workers = min(5, len(persona_cards)) if persona_cards else 1

#     with concurrent.futures.ThreadPoolExecutor(max_workers=summary_workers) as sum_executor:
#         sum_futures = {}

#         for c in persona_cards:
#             f = sum_executor.submit(synthesize_panel_summary, [c], stimulus_text)
#             sum_futures[f] = c.get("card_key")

#         for f in concurrent.futures.as_completed(sum_futures):
#             card_key_str = sum_futures[f]
#             try:
#                 summary_lookup[card_key_str] = _json_safe(f.result())
#             except Exception as e:
#                 logger.error(f"❌ Per-card summary failed for card_key={card_key_str}: {e}")
#                 summary_lookup[card_key_str] = {"summary_error": str(e)}

#     # attach summary directly to each persona card
#     for c in persona_cards:
#         ck = c.get("card_key")
#         c["summary"] = summary_lookup.get(ck)

#     # -------------------------------
#     # GROUP RESPONSE BY IMAGE
#     # images: [{image_id, image_url, image_url_str, cards:[...]}]
#     # -------------------------------
#     images_grouped: Dict[str, Dict[str, Any]] = {}

#     if has_images:
#         for card in persona_cards:
#             img_id = card.get("image_id") or "no_image"
#             if img_id not in images_grouped:
#                 images_grouped[img_id] = {
#                     "image_id": img_id,
#                     "image_url": card.get("image_url"),
#                     "image_url_str": card.get("image_url_str"),
#                     "image_index": card.get("image_index", 0),
#                     "cards": []
#                 }
#             images_grouped[img_id]["cards"].append(card)

#         images_list = list(images_grouped.values())
#         images_list.sort(key=lambda x: x.get("image_index", 0))

#         # inside each image, sort cards by persona_index (persona 1,2,3 order)
#         for img_obj in images_list:
#             img_obj["cards"].sort(key=lambda c: c.get("persona_index", 0))
#             img_obj.pop("image_index", None)  # remove internal helper field
#     else:
#         # no images => one pseudo-image bucket
#         images_list = [{
#             "image_id": None,
#             "image_url": None,
#             "image_url_str": None,
#             "cards": persona_cards
#         }]

#     result = {
#         "images": images_list,
#         "metadata": {
#             "persona_count": len(personas),
#             "content_type": content_type,
#             "created_at": datetime.now().isoformat(),
#             "cards_count": len(persona_cards),
#             "image_mapped": bool(has_images),
#             "campaign_id":campaign_id,
#             "task_id":task_id,
#             "image_count": len(stimulus_images) if has_images else 0,
#             "mapping_mode": "forced_cartesian" if has_images else "per_persona",
#         }
#     }

#     # FINAL safety: ensure JSON serializable
#     result = _json_safe(result)
#     try:
#         json.dumps(result)
#     except Exception as e:
#         logger.exception(f"❌ Final response not JSON serializable: {e}")
#         raise

#     logger.info(f"✅ Panel feedback analysis complete for {len(persona_cards)} persona_cards")
#     return result
def create_panel_feedback_prompt_v2(
    persona_data: Dict[str, Any],
    stimulus_text: str,
    stimulus_images: Optional[List[Dict]] = None,
    content_type: str = "text"
) -> str:
    """
    Creates a prompt for structured panel feedback analysis.
    
    The persona will analyze the marketing asset and provide feedback in
    standardized sections: Clean Read, Key Themes, Strengths, Weaknesses.
    """
    logger.info("in createpanelfeedback")
    logger.info(stimulus_images)
    persona_name = persona_data.get('name', 'Unknown')
    persona_type = persona_data.get('persona_type', 'Patient')
    full_persona = persona_data.get('full_persona', {})
    
    # Extract key characteristics from persona
    segment = full_persona.get('persona_subtype', '') or full_persona.get('segment', '')
    decision_style = full_persona.get('decision_style', '')
    
    # Get role/specialty for HCPs
    role = ''
    if persona_type.lower() == 'hcp':
        role = full_persona.get('specialty') or full_persona.get('role', 'Healthcare Professional')
    else:
        role = full_persona.get('condition', 'Patient')
    
    # Extract key characteristics as list
    characteristics = []
    if decision_style:
        characteristics.append(decision_style)
    if segment:
        characteristics.append(segment)
    
    mbt = full_persona.get('core', {}).get('mbt', {})
    if mbt:
        # Add a key motivation or belief as characteristic
        motivations = mbt.get('motivations', [])
        if motivations:
            first_mot = motivations[0] if isinstance(motivations[0], str) else motivations[0].get('text', '')
            if first_mot and len(first_mot) < 50:
                characteristics.append(first_mot)
    
    characteristics_str = ', '.join(characteristics[:3]) if characteristics else 'Not specified'
    
    # Build content description
    
    content_description = f"Marketing Message:\n\"{stimulus_text}\"\n\nVisual Content: {stimulus_images} image(s) provided for analysis"
    
    prompt = f"""
You are a pharmaceutical marketing analyst simulating how a specific persona would evaluate a marketing asset.

**PERSONA PROFILE:**
- Name: {persona_name}
- Type: {persona_type}
- Role/Condition: {role}
- Key Characteristics: {characteristics_str}

**DETAILED PERSONA DATA:**
{json.dumps(full_persona, indent=2)[:3000]}

**MARKETING ASSET TO ANALYZE:**
{content_description}

**YOUR TASK:**
Analyze this marketing asset from the perspective of this persona. Provide your analysis in the following structured format:


1. **Key Themes**: What themes or messages resonate with you as this persona? What catches your attention? (2-4 themes)

2. **Strengths**: What works well about this asset from your perspective? What would make you engage positively? (2-4 points)

3. **Weaknesses**: What concerns you? What doesn't work? What's missing or confusing? (2-4 points)

**OUTPUT FORMAT (JSON only):**
{{
    "persona_header": {{
        "name": "{persona_name}",
        "role": "<role/specialty or condition>",
        "segment": "<primary segment or decision style>",
        "key_characteristics": ["<characteristic 1>", "<characteristic 2>", "<characteristic 3>"]
    }},
    "clean_read": "<1-3 sentences describing initial interpretation>",
    "key_themes": [
        "<theme 1>",
        "<theme 2>",
        "<theme 3>"
    ],
    "strengths": [
        "<strength 1>",
        "<strength 2>"
    ],
    "weaknesses": [
        "<weakness 1>",
        "<weakness 2>"
    ]
}}

Be specific and ground your analysis in the persona's unique characteristics, concerns, and perspective.
"""
    
    return prompt


def analyze_single_persona_panel_v2(
    persona_dict: Dict[str, Any],
    stimulus_text: str,
    stimulus_images: Optional[List[Dict]] = None,
    content_type: str = "text"
) -> Dict[str, Any]:
    """
    Analyze a single persona's panel feedback response.
    Designed to be called in parallel.
    """

    logger.info("This is the logger for checking data to genertae person panel")
    logger.info(stimulus_images)
    persona_id = persona_dict['id']
    persona_name = persona_dict['name']
    logger.info(f"🔄 Processing panel feedback for: {persona_name} (ID: {persona_id})")
    
    # Parse full persona JSON
    try:
        full_persona = json.loads(persona_dict.get('full_persona_json', '{}')) if persona_dict.get('full_persona_json') else {}
    except Exception as parse_error:
        logger.error(f"❌ Error parsing persona JSON for {persona_name}: {parse_error}")
        full_persona = {}
    
    # Build persona_data dict
    persona_data = {
        'id': persona_dict['id'],
        'name': persona_dict['name'],
        'persona_type': persona_dict.get('persona_type', 'Patient'),
        'age': persona_dict.get('age'),
        'gender': persona_dict.get('gender'),
        'condition': persona_dict.get('condition'),
        'location': persona_dict.get('location'),
        'avatar_url': persona_dict.get('avatar_url'),
        'full_persona': full_persona
    }
    
    # Create prompt
    prompt = create_panel_feedback_prompt_v2(
        persona_data,
        stimulus_text,
        stimulus_images,
        content_type
    )
    
    # Prepare messages
    messages = [{"role": "user", "content": []}]
    messages[0]["content"].append({"type": "text", "text": prompt})
    
    # Add images if provided
    if stimulus_images and content_type in ['image', 'both']:
        for image_info in stimulus_images:
            data_url = f"data:{image_info['content_type']};base64,{image_info['data']}"
            messages[0]["content"].append({
                "type": "image_url",
                "image_url": {"url": data_url}
            })
    
    try:
        data = _chat_json_panel(messages)
        
        if data.get("error"):
            raise RuntimeError(data["error"])
        
        # Extract and structure the response
        header = data.get("persona_header", {})
        
        result = {
            "persona_id": persona_id,
            "persona_name": persona_name,
            "role": header.get("role", persona_dict.get('condition', '')),
            "segment": header.get("segment", full_persona.get('persona_subtype', '')),
            "key_characteristics": header.get("key_characteristics", []),
            "avatar_url": persona_dict.get('avatar_url'),
            "clean_read": data.get("clean_read", "No interpretation provided."),
            "key_themes": data.get("key_themes", []),
            "strengths": data.get("strengths", []),
            "weaknesses": data.get("weaknesses", [])
        }
        
        logger.info(f"✅ Panel feedback completed for {persona_name}")
        return result
        
    except Exception as e:
        logger.error(f"❌ Error analyzing panel feedback for {persona_id}: {e}")
        return {
            "persona_id": persona_id,
            "persona_name": persona_name,
            "role": persona_dict.get('condition', ''),
            "segment": "",
            "key_characteristics": [],
            "avatar_url": persona_dict.get('avatar_url'),
            "clean_read": f"Error in analysis: {str(e)}",
            "key_themes": [],
            "strengths": [],
            "weaknesses": [],
            "error": str(e)
        }



def synthesize_panel_summary_v2(
    persona_cards: List[Dict[str, Any]],
    stimulus_text: str
) -> Dict[str, Any]:
    """
    Synthesize a summary from all persona panel feedback.
    
    Generates:
    - Aggregated themes ("3 of 5 personas flagged X")
    - Dissent highlights ("While 4 personas liked Y, Persona Z disagreed")
    - Actionable recommendations
    """
    
    # Prepare summary of all responses for the synthesis prompt
    cards_summary = []
    for card in persona_cards:
        cards_summary.append({
            "name": card.get("persona_name"),
            "role": card.get("role"),
            "key_themes": card.get("key_themes", []),
            "strengths": card.get("strengths", []),
            "weaknesses": card.get("weaknesses", [])
        })
    
    prompt = f"""
You are an expert pharmaceutical marketing analyst. You have collected panel feedback from {len(persona_cards)} personas analyzing a marketing asset.

**STIMULUS:**
"{stimulus_text[:1000]}"

**INDIVIDUAL PERSONA FEEDBACK:**
{json.dumps(cards_summary, indent=2)}

**YOUR TASK:**
Synthesize the feedback from all personas into a cohesive summary. Focus on:

1. **Aggregated Themes**: What patterns emerge? Use statements like "3 of 5 personas mentioned..." or "The majority flagged..."

2. **Dissent Highlights**: Where do personas disagree? Highlight cases like "While most personas liked X, [Name] found it concerning because..."

3. **Actionable Recommendations**: Based on the collective feedback, what specific changes would improve the asset?

**OUTPUT FORMAT (JSON only):**
{{
    "aggregated_themes": [
        "<pattern 1 with counts, e.g., '4 of 5 personas flagged missing safety data'>",
        "<pattern 2>",
        "<pattern 3>"
    ],
    "dissent_highlights": [
        "<disagreement 1, naming the dissenting persona>",
        "<disagreement 2>"
    ],
    "recommendations": [
        {{
            "suggestion": "<specific actionable change>",
            "reasoning": "<based on which personas' feedback>"
        }},
        {{
            "suggestion": "<another change>",
            "reasoning": "<supporting evidence>"
        }}
    ]
}}

Be specific and reference persona names when highlighting dissent. Focus on actionable insights.
"""
    
    messages = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
    
    try:
        data = _chat_json_panel(messages, max_completion_tokens=1500)
        
        if data.get("error"):
            raise RuntimeError(data["error"])
        
        return {
            "aggregated_themes": data.get("aggregated_themes", []),
            "dissent_highlights": data.get("dissent_highlights", []),
            "recommendations": data.get("recommendations", [])
        }
        
    except Exception as e:
        logger.error(f"❌ Error synthesizing panel summary: {e}")
        return {
            "aggregated_themes": ["Unable to generate aggregated themes due to error."],
            "dissent_highlights": [],
            "recommendations": [{"suggestion": "Review individual persona feedback for insights.", "reasoning": str(e)}]
        }



def run_panel_feedback_analysis_v2(
    campaign_id: str,
    task_id: str,
    persona_ids: List[int],
    stimulus_text: str,
    stimulus_images: Optional[List[Dict]] = None,
    content_type: str = "text",
    db=None
) -> Dict[str, Any]:
    import json
    import uuid
    import base64
    import mimetypes
    import requests
    import concurrent.futures
    from datetime import datetime

    def _json_safe(x):
        if x is None:
            return None
        if isinstance(x, (str, int, float, bool)):
            return x
        if isinstance(x, uuid.UUID):
            return str(x)
        if isinstance(x, datetime):
            return x.isoformat()
        if isinstance(x, dict):
            return {str(_json_safe(k)): _json_safe(v) for k, v in x.items()}
        if isinstance(x, (list, tuple, set)):
            return [_json_safe(v) for v in list(x)]
        return str(x)

    def _url_to_base64(url: str, timeout: int = 20, max_bytes: int = 8 * 1024 * 1024):
        r = requests.get(url, stream=True, timeout=timeout)
        r.raise_for_status()

        content_type = r.headers.get("Content-Type")
        if content_type:
            mime_type = content_type.split(";")[0].strip()
        else:
            mime_type = mimetypes.guess_type(url)[0] or "application/octet-stream"

        chunks = []
        total = 0
        for chunk in r.iter_content(chunk_size=1024 * 256):
            if not chunk:
                continue
            total += len(chunk)
            if total > max_bytes:
                raise ValueError(f"Image too large (> {max_bytes} bytes)")
            chunks.append(chunk)

        raw = b"".join(chunks)
        b64 = base64.b64encode(raw).decode("utf-8")
        return b64, mime_type

    if not persona_ids:
        raise ValueError("At least one persona ID is required")

    personas: List[Dict[str, Any]] = []
    for persona_id in persona_ids:
        persona = crud.get_persona(db, persona_id)
        if persona:
            personas.append({
                "id": persona.id,
                "name": persona.name,
                "age": persona.age,
                "gender": persona.gender,
                "condition": persona.condition,
                "location": persona.location,
                "persona_type": persona.persona_type,
                "avatar_url": getattr(persona, "avatar_url", None),
                "full_persona_json": persona.full_persona_json,
            })

    if not personas:
        raise ValueError("No valid personas found for the provided IDs")

    logger.info(f"🎯 Running panel feedback for {len(personas)} personas")

    if isinstance(stimulus_images, list) and stimulus_images:
        updated_images = []
        for img in stimulus_images:
            if not isinstance(img, dict):
                updated_images.append(img)
                continue

            url = img.get("url") or img.get("image_url_str")
            if not url:
                updated_images.append(img)
                continue

            if img.get("data"):
                img2 = dict(img)
                img2["url"] = url
                updated_images.append(img2)
                continue

            try:
                b64, mime_type = _url_to_base64(url)
                img2 = dict(img)
                img2["url"] = url
                img2["data"] = b64
                img2["mime_type"] = mime_type
                updated_images.append(img2)
            except Exception as e:
                img2 = dict(img)
                img2["url"] = url
                img2["data_error"] = str(e)
                updated_images.append(img2)

        stimulus_images = updated_images

        logger.info("This is stimulus")
        logger.info(stimulus_images)

    logger.info(
        f"{stimulus_images}"
        f"[panel-feedback-v2] content_type={content_type} | "
        f"stimulus_images_type={type(stimulus_images)} | "
        f"stimulus_images_len={(len(stimulus_images) if isinstance(stimulus_images, list) else 'NA')} | "
        f"stimulus_images_truthy={bool(stimulus_images)}"
    )
    if isinstance(stimulus_images, list) and stimulus_images:
        first = stimulus_images[0]
        logger.info(
            f"[panel-feedback-v2] first_image_type={type(first)} | "
            f"first_image_keys={list(first.keys()) if isinstance(first, dict) else 'NA'}"
        )

    has_images = isinstance(stimulus_images, list) and len(stimulus_images) > 0

    logger.info(
        f"[panel-feedback-v2] has_images={has_images} | "
        f"personas={len(personas)} | "
        f"stimulus_images_count={(len(stimulus_images) if isinstance(stimulus_images, list) else 0)}"
    )
    if has_images:
        ids = []
        for idx, img in enumerate(stimulus_images):
            if isinstance(img, dict):
                _id = img.get("id")
                ids.append(str(_id) if _id is not None else f"missing_id@{idx}")
            else:
                ids.append(f"non_dict@{idx}")
        logger.info(f"[panel-feedback-v2] stimulus_image_ids={ids}")
    else:
        logger.info("[panel-feedback-v2] No images provided -> per_persona mode (1 card per persona)")

    jobs: List[tuple] = []

    if has_images:
        total_cards = len(personas) * len(stimulus_images)
        logger.info(
            f"🧩 Running FORCED CARTESIAN panel: {len(personas)} personas x "
            f"{len(stimulus_images)} images -> {total_cards} persona_cards"
        )

        for img_idx, img in enumerate(stimulus_images):
            for persona_idx, persona_dict in enumerate(personas):
                card_number = (img_idx * len(personas)) + persona_idx + 1

                image_id = img.get("id") if isinstance(img, dict) else None
                image_url = img.get("url") if isinstance(img, dict) else None
                image_url_str = img.get("image_url_str") if isinstance(img, dict) else None

                image_id_safe = str(image_id) if isinstance(image_id, uuid.UUID) else image_id

                card_key = uuid.uuid4()

                jobs.append((
                    persona_idx,
                    img_idx,
                    persona_dict,
                    img,
                    card_number,
                    card_key,
                    image_id_safe,
                    image_url,
                    image_url_str
                ))
    else:
        logger.info("🧩 Running OLD panel (no images): 1 card per persona")
        for persona_idx, persona_dict in enumerate(personas):
            card_number = persona_idx + 1
            card_key = uuid.uuid4()
            jobs.append((
                persona_idx,
                None,
                persona_dict,
                None,
                card_number,
                card_key,
                None,
                None,
                None
            ))

    logger.info(
        f"[panel-feedback-v2] jobs_built={len(jobs)} | "
        f"mode={'forced_cartesian' if has_images else 'per_persona'} | "
        f"max_workers={min(5, len(jobs)) if jobs else 1}"
    )
    if has_images and jobs:
        sample = jobs[0]
        logger.info(
            "[panel-feedback-v2] first_job_sample | "
            f"persona_index={sample[0]} | image_index={sample[1]} | "
            f"persona_id={sample[2].get('id')} | image_id={sample[6]} | "
            f"card_number={sample[4]} | card_key={str(sample[5])}"
        )

    persona_cards: List[Dict[str, Any]] = []
    max_workers = min(5, len(jobs)) if jobs else 1

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}

        for persona_index, image_index, persona_dict, single_img, card_number, card_key, image_id, image_url, image_url_str in jobs:
            card_context = {
                "card_number": card_number,
                "card_key": str(card_key),
                "persona_id": persona_dict["id"],
                "persona_name": persona_dict.get("name"),
                "image_id": image_id,
                "image_url": image_url,
                "image_url_str": image_url_str,
                "image_index": image_index,
                "persona_index": persona_index,
            }

            injected_stimulus_text = (
                "### CARD_CONTEXT (MUST RETURN AS-IS IN OUTPUT JSON)\n"
                f"{json.dumps(_json_safe(card_context), ensure_ascii=False)}\n"
                "### END_CARD_CONTEXT\n\n"
                f"{stimulus_text}"
            )

            if has_images:
                future = executor.submit(
                    analyze_single_persona_panel_v2,
                    persona_dict,
                    injected_stimulus_text,
                    [single_img],
                    content_type
                )
            else:
                future = executor.submit(
                    analyze_single_persona_panel_v2,
                    persona_dict,
                    injected_stimulus_text,
                    None,
                    content_type
                )

            futures[future] = {
                "persona_id": persona_dict["id"],
                "persona_name": persona_dict.get("name"),
                "persona_index": persona_index,
                "image_index": image_index,
                "image": single_img,
                "card_number": card_number,
                "card_key": card_key,
                "image_id": image_id,
                "image_url": image_url,
                "image_url_str": image_url_str,
            }

        for future in concurrent.futures.as_completed(futures):
            meta = futures[future]
            try:
                result = future.result()

                result["card_number"] = meta["card_number"]
                result["card_key"] = str(meta["card_key"])

                result["persona_id"] = meta["persona_id"]
                if meta.get("persona_name"):
                    result["persona_name"] = meta["persona_name"]
                result["persona_index"] = meta["persona_index"]

                if has_images:
                    result["image_index"] = meta["image_index"]
                    if meta.get("image_id") is not None:
                        result["image_id"] = meta["image_id"]
                    if meta.get("image_url") is not None:
                        result["image_url"] = meta["image_url"]
                    if meta.get("image_url_str") is not None:
                        result["image_url_str"] = meta["image_url_str"]

                persona_cards.append(_json_safe(result))

            except Exception as e:
                logger.error(
                    f"❌ Panel feedback failed for persona {meta['persona_id']} "
                    f"(image_index={meta.get('image_index')}): {e}"
                )

                err_obj = {
                    "error": str(e),
                    "card_number": meta["card_number"],
                    "card_key": str(meta["card_key"]),
                    "persona_id": meta["persona_id"],
                    "persona_name": meta.get("persona_name") or f"Persona {meta['persona_id']}",
                    "persona_index": meta.get("persona_index"),
                }

                if has_images:
                    err_obj["image_index"] = meta["image_index"]
                    if meta.get("image_id") is not None:
                        err_obj["image_id"] = meta["image_id"]
                    if meta.get("image_url") is not None:
                        err_obj["image_url"] = meta["image_url"]
                    if meta.get("image_url_str") is not None:
                        err_obj["image_url_str"] = meta["image_url_str"]

                persona_cards.append(_json_safe(err_obj))

    if has_images:
        persona_cards.sort(key=lambda x: (x.get("image_index", 0), x.get("persona_index", 0)))
    else:
        persona_cards.sort(key=lambda x: x.get("persona_id", 0))

    logger.info("📊 Synthesizing PER-CARD summaries (concurrent)...")

    summary_lookup: Dict[str, Any] = {}
    summary_workers = min(5, len(persona_cards)) if persona_cards else 1

    with concurrent.futures.ThreadPoolExecutor(max_workers=summary_workers) as sum_executor:
        sum_futures = {}

        for c in persona_cards:
            if has_images:
                logger.info(
                    "[panel-feedback-v2] summary_job_submit | "
                    f"card_key={c.get('card_key')} | "
                    f"persona_id={c.get('persona_id')} | "
                    f"image_id={c.get('image_id')} | "
                    f"image_index={c.get('image_index')} | "
                    f"persona_index={c.get('persona_index')}"
                )
            else:
                logger.info(
                    "[panel-feedback-v2] summary_job_submit | "
                    f"card_key={c.get('card_key')} | persona_id={c.get('persona_id')}"
                )

            f = sum_executor.submit(synthesize_panel_summary_v2, [c], stimulus_text)
            sum_futures[f] = c.get("card_key")

        for f in concurrent.futures.as_completed(sum_futures):
            card_key_str = sum_futures[f]
            try:
                out = f.result()
                summary_lookup[card_key_str] = _json_safe(out)
                logger.info(f"[panel-feedback-v2] summary_job_done | card_key={card_key_str} | ok=True")
            except Exception as e:
                logger.error(f"[panel-feedback-v2] summary_job_done | card_key={card_key_str} | ok=False | err={e}")
                summary_lookup[card_key_str] = {"summary_error": str(e)}

    for c in persona_cards:
        ck = c.get("card_key")
        c["summary"] = summary_lookup.get(ck)

    images_grouped: Dict[str, Dict[str, Any]] = {}

    if has_images:
        for card in persona_cards:
            img_id = card.get("image_id") or "no_image"
            if img_id not in images_grouped:
                images_grouped[img_id] = {
                    "image_id": img_id,
                    "image_url": card.get("image_url"),
                    "image_url_str": card.get("image_url_str"),
                    "image_index": card.get("image_index", 0),
                    "cards": []
                }
            images_grouped[img_id]["cards"].append(card)

        images_list = list(images_grouped.values())
        images_list.sort(key=lambda x: x.get("image_index", 0))

        for img_obj in images_list:
            img_obj["cards"].sort(key=lambda c: c.get("persona_index", 0))
            img_obj.pop("image_index", None)
    else:
        images_list = [{
            "image_id": None,
            "image_url": None,
            "image_url_str": None,
            "cards": persona_cards
        }]

    if has_images:
        logger.info(f"[panel-feedback-v2] grouping_done | images_bucket_count={len(images_list)}")
        for img_obj in images_list:
            logger.info(
                "[panel-feedback-v2] image_bucket | "
                f"image_id={img_obj.get('image_id')} | cards={len(img_obj.get('cards', []))}"
            )
    else:
        logger.info(f"[panel-feedback-v2] grouping_done | no_images_bucket_cards={len(persona_cards)}")

    result = {
        "images": images_list,
        "metadata": {
            "persona_count": len(personas),
            "content_type": content_type,
            "created_at": datetime.now().isoformat(),
            "cards_count": len(persona_cards),
            "image_mapped": bool(has_images),
            "campaign_id": campaign_id,
            "task_id": task_id,
            "image_count": len(stimulus_images) if has_images else 0,
            "mapping_mode": "forced_cartesian" if has_images else "per_persona",
        }
    }

    result = _json_safe(result)
    try:
        json.dumps(result)
    except Exception as e:
        logger.exception(f"❌ Final response not JSON serializable: {e}")
        raise

    logger.info(f"✅ Panel feedback analysis complete for {len(persona_cards)} persona_cards")
    return result