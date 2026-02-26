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
import base64
import concurrent.futures
import json
import mimetypes
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import requests
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


from typing import List, Dict, Any, Optional
import json
import uuid
import concurrent.futures
from datetime import datetime

# Assumes you already have:
# - logger
# - MODEL_NAME (you said you're using 5.2)
# - get_openai_client()
# - crud.get_persona(db, persona_id)
# - _extract_json(raw)


# -------------------------------
# HELPERS
# -------------------------------
def _image_key(img: Any, img_idx: int) -> str:
    """
    Stable grouping key even when image_id is None.
    Preference: id -> url -> image_url_str -> idx
    """
    if not isinstance(img, dict):
        return f"idx_{img_idx}"
    return (
        img.get("id")
        or img.get("url")
        or img.get("image_url_str")
        or img.get("thumbnail_url")
        or img.get("thumbnail_url_str")
        or f"idx_{img_idx}"
    )


# -------------------------------
# MULTIMODAL ATTACHMENT
# -------------------------------
def _attach_images_to_message_parts(
    parts: List[Dict[str, Any]],
    stimulus_images: Optional[List[Dict[str, Any]]]
) -> None:
    """
    Attach images to a multimodal chat content parts list.

    Prefers:
    1) image_info["url"] if present
    2) data URL from image_info["content_type"] + image_info["data"] if present

    Safe: skips invalid items.
    """
    if not stimulus_images or not isinstance(stimulus_images, list):
        return

    for image_info in stimulus_images:
        if not isinstance(image_info, dict):
            continue

        url = image_info.get("url")
        if not url:
            ct = image_info.get("content_type")
            b64 = image_info.get("data")
            if ct and b64:
                url = f"data:{ct};base64,{b64}"

        if url:
            parts.append({
                "type": "image_url",
                "image_url": {"url": url}
            })


def _chat_json_panel(messages: List[Dict[str, Any]], max_completion_tokens: Optional[int] = None) -> Dict[str, Any]:
    """Call chat.completions ensuring JSON-only output. Returns parsed dict or {}."""
    client = get_openai_client()
    if client is None:
        logger.error("❌ OpenAI API key missing")
        return {"error": "OpenAI API key not configured"}

    if max_completion_tokens is None:
        max_completion_tokens = 2048

    # Inject enforcement instruction (once)
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
        if not raw:
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


# -------------------------------
# PROMPT: SINGLE CARD (persona + image)
# -------------------------------
def create_panel_feedback_prompt(
    persona_data: Dict[str, Any],
    stimulus_text: str,
    stimulus_images: Optional[List[Dict]] = None,
    content_type: str = "text"
) -> str:
    """
    Creates a prompt for structured panel feedback analysis.

    ✅ Strongly image-grounded (if images exist)
    ✅ Persona-grounded
    ✅ Output JSON format unchanged
    """
    persona_name = persona_data.get('name', 'Unknown')
    persona_type = persona_data.get('persona_type', 'Patient')
    full_persona = persona_data.get('full_persona', {}) or {}

    segment = full_persona.get('persona_subtype', '') or full_persona.get('segment', '')
    decision_style = full_persona.get('decision_style', '')

    if persona_type.lower() == 'hcp':
        role = full_persona.get('specialty') or full_persona.get('role', 'Healthcare Professional')
    else:
        role = full_persona.get('condition', 'Patient')

    characteristics = []
    if decision_style:
        characteristics.append(decision_style)
    if segment:
        characteristics.append(segment)

    mbt = (full_persona.get('core', {}) or {}).get('mbt', {}) or {}
    if mbt:
        motivations = mbt.get('motivations', [])
        if motivations:
            first_mot = motivations[0] if isinstance(motivations[0], str) else motivations[0].get('text', '')
            if first_mot and len(first_mot) < 60:
                characteristics.append(first_mot)

    characteristics_str = ', '.join(characteristics[:3]) if characteristics else 'Not specified'

    # Content description
    image_count = len(stimulus_images) if stimulus_images else 0
    first_url = None
    first_id = None
    if stimulus_images and isinstance(stimulus_images, list) and len(stimulus_images) > 0 and isinstance(stimulus_images[0], dict):
        first_url = stimulus_images[0].get("url")
        first_id = stimulus_images[0].get("id")

    content_description = ""
    if content_type == "text":
        content_description = f"Marketing Message:\n\"{stimulus_text}\""
    elif content_type in ("image", ""):
        content_description = (
            f"Visual Content: {image_count} image(s) provided.\n"
            f"- First image_id: {first_id}\n"
            f"- First image_url: {first_url}\n"
            f"IMPORTANT: The image itself is attached in this chat input. Base your feedback ONLY on what you can see."
        )
    elif content_type == "both":
        content_description = (
            f"Marketing Message:\n\"{stimulus_text}\"\n\n"
            f"Visual Content: {image_count} image(s) provided.\n"
            f"- First image_id: {first_id}\n"
            f"- First image_url: {first_url}\n"
            f"IMPORTANT: The image itself is attached in this chat input. Base your feedback on text + what you can see."
        )

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

**CRITICAL RULES (follow strictly):**
1) If an image is provided, your response MUST reference at least 6 concrete visual details across the entire output.
   Examples: visible headline text, objects, people, setting, emotions, layout placement, CTA, fine print, colors, charts, icons.
2) Do NOT invent details. If unsure, say "appears" / "seems".
3) Avoid generic pharma marketing feedback. Every theme/strength/weakness MUST be tied to something visible or explicitly stated.
4) Persona grounding:
   - Patients: clarity, reassurance, safety, “what do I do next”.
   - HCPs: evidence, indication, dosing, safety, comparators, clinical relevance.

**YOUR TASK:**
Analyze this asset from the perspective of this persona. Provide:

1. Clean Read (1–3 sentences; include at least 2 concrete details if image present)
2. Key Themes (2–4; each tied to visible cue)
3. Strengths (2–4; each "because..." grounded)
4. Weaknesses (2–4; specify what’s missing/confusing and what caused it)
5. Actionable Recommendations (specific edits; cite which personas drove them)

**OUTPUT FORMAT (JSON only):**
{{
  "persona_header": {{
    "name": "{persona_name}",
    "role": "<role/specialty or condition>",
    "segment": "<primary segment or decision style>",
    "key_characteristics": ["<characteristic 1>", "<characteristic 2>", "<characteristic 3>"]
  }},
  "clean_read": "<1-3 sentences describing initial interpretation>",
  "key_themes": ["<theme 1>", "<theme 2>", "<theme 3>"],
  "strengths": ["<strength 1>", "<strength 2>"],
  "weaknesses": ["<weakness 1>", "<weakness 2>"]
  "recommendations": [
    {{"suggestion": "<actionable change>", "reasoning": "<who/why>"}},
    {{"suggestion": "<actionable change>", "reasoning": "<who/why>"}}
  ]
}}
"""
    return prompt


# -------------------------------
# SINGLE CARD RUN
# -------------------------------
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
    persona_id = persona_dict['id']
    persona_name = persona_dict['name']
    logger.info(f"🔄 Processing panel feedback for: {persona_name} (ID: {persona_id})")

    try:
        full_persona = json.loads(persona_dict.get('full_persona_json', '{}')) if persona_dict.get('full_persona_json') else {}
    except Exception as parse_error:
        logger.error(f"❌ Error parsing persona JSON for {persona_name}: {parse_error}")
        full_persona = {}

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

    prompt = create_panel_feedback_prompt(
        persona_data,
        stimulus_text,
        stimulus_images,
        content_type
    )

    messages = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]

    # ✅ Attach images for this card
    if stimulus_images and content_type in ["image", "both"]:
        _attach_images_to_message_parts(messages[0]["content"], stimulus_images)

    try:
        data = _chat_json_panel(messages)

        if data.get("error"):
            raise RuntimeError(data["error"])

        header = data.get("persona_header", {}) or {}

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
            "weaknesses": data.get("weaknesses", []),
            "recommendations":data.get("recommendations",[])
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
            "recommendations":[],
            "error": str(e)
        }


# -------------------------------
# SUMMARY PROMPT (FIX: unique persona count)
# -------------------------------
def synthesize_panel_summary(
    persona_cards: List[Dict[str, Any]],
    stimulus_text: str,
    stimulus_images: Optional[List[Dict[str, Any]]] = None,
    force_image_grounding: bool = True
) -> Dict[str, Any]:
    """
    Synthesize a summary from persona panel feedback.

    ✅ Attaches image_url(s) so summary can be image-grounded.
    ✅ FIX: counts are based on UNIQUE personas, not number of cards.
    """
    # unique persona count
    seen = set()
    for c in persona_cards:
        pid = c.get("persona_id")
        if pid is not None:
            seen.add(pid)
    unique_persona_count = len(seen) if seen else len({c.get("persona_name") for c in persona_cards if c.get("persona_name")})

    cards_summary = []
    for card in persona_cards:
        cards_summary.append({
            "persona_id": card.get("persona_id"),
            "name": card.get("persona_name"),
            "role": card.get("role"),
            "key_themes": card.get("key_themes", []),
            "strengths": card.get("strengths", []),
            "weaknesses": card.get("weaknesses", []),
            "recommendations":card.get("recommendations",[])
        })

    image_count = len(stimulus_images) if stimulus_images else 0
    first_url = None
    if stimulus_images and isinstance(stimulus_images, list) and len(stimulus_images) > 0 and isinstance(stimulus_images[0], dict):
        first_url = stimulus_images[0].get("url")

    grounding_rules = ""
    if force_image_grounding and stimulus_images:
        grounding_rules = f"""
**IMAGE GROUNDING (IMPORTANT):**
- An image is attached to this request (count={image_count}, first_url={first_url}).
- Your summary MUST reference at least 5 concrete visual details (headline text, objects, layout, CTA, fine print, colors, symbols).
- Do NOT invent details you cannot see.
"""

    prompt = f"""
You are an expert pharmaceutical marketing analyst.

You have collected panel feedback from {unique_persona_count} unique personas analyzing a marketing asset.

**STIMULUS TEXT (if any):**
"{stimulus_text[:1200]}"

{grounding_rules}

**INDIVIDUAL PERSONA FEEDBACK (derived from their viewpoint):**
{json.dumps(cards_summary, indent=2)}

**YOUR TASK:**
Synthesize the feedback into a cohesive summary:

1) Aggregated Themes (include counts like "3 of {unique_persona_count}...")
2) Dissent Highlights (name personas and WHY)
3) Actionable Recommendations (specific edits; cite which personas drove them)

**OUTPUT FORMAT (JSON only):**
{{
  "aggregated_themes": ["<pattern 1 with counts>", "<pattern 2>", "<pattern 3>"],
  "dissent_highlights": ["<disagreement 1>", "<disagreement 2>"],
  "recommendations": [
    {{"suggestion": "<actionable change>", "reasoning": "<who/why>"}},
    {{"suggestion": "<actionable change>", "reasoning": "<who/why>"}}
  ]
}}
"""

    messages = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]

    # ✅ Attach images to the SUMMARY call too
    if stimulus_images:
        _attach_images_to_message_parts(messages[0]["content"], stimulus_images)

    try:
        data = _chat_json_panel(messages, max_completion_tokens=1500)
        if data.get("error"):
            raise RuntimeError(data["error"])

        return {
            "aggregated_themes": data.get("aggregated_themes", []),
            "dissent_highlights": data.get("dissent_highlights", []),
            "recommendations": data.get("recommendations", []),
        }

    except Exception as e:
        logger.error(f"❌ Error synthesizing panel summary: {e}")
        return {
            "aggregated_themes": ["Unable to generate aggregated themes due to error."],
            "dissent_highlights": [],
            "recommendations": [{"suggestion": "Review individual persona feedback for insights.", "reasoning": str(e)}]
        }


# -------------------------------
# MAIN RUN
# -------------------------------
def run_panel_feedback_analysis_v2(
    campaign_id: str,
    task_id: str,
    persona_ids: List[int],
    stimulus_text: str,
    stimulus_images: Optional[List[Dict]] = None,
    content_type: str = "text",
    db=None,
    # ✅ SPEED CONTROL:
    generate_card_summaries: bool = False,  # ✅ default OFF (no extra LLM call)
    generate_image_summaries: bool = True,  # keep ON (usually what UI needs)
) -> Dict[str, Any]:

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

    if not persona_ids:
        raise ValueError("At least one persona ID is required")

    # -------------------------------
    # Fetch Personas
    # -------------------------------
    personas = []
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
        raise ValueError("No valid personas found")

    logger.info(f"🎯 Running panel feedback for {len(personas)} personas")

    has_images = isinstance(stimulus_images, list) and len(stimulus_images) > 0

    # ✅ Auto-fix content_type so images are actually sent
    if has_images and content_type not in ["image", "both"]:
        content_type = "both" if (stimulus_text and stimulus_text.strip()) else "image"

    # -------------------------------
    # BUILD JOBS (forced cartesian)
    # -------------------------------
    jobs = []

    if has_images:
        for img_idx, img in enumerate(stimulus_images):
            ikey = _image_key(img, img_idx)

            for persona_idx, persona_dict in enumerate(personas):
                card_number = (img_idx * len(personas)) + persona_idx + 1
                card_key = uuid.uuid4()

                image_id = img.get("id") if isinstance(img, dict) else None
                image_url = img.get("url") if isinstance(img, dict) else None
                image_url_str = img.get("image_url_str") if isinstance(img, dict) else None
                thumbnail_url = img.get("thumbnail_url") if isinstance(img, dict) else None
                thumbnail_url_str = img.get("thumbnail_url_str") if isinstance(img, dict) else None

                jobs.append((
                    persona_idx,
                    img_idx,
                    persona_dict,
                    img,
                    card_number,
                    card_key,
                    image_id,
                    image_url,
                    image_url_str,
                    thumbnail_url,
                    thumbnail_url_str,
                    ikey,  # ✅ crucial
                ))
    else:
        for persona_idx, persona_dict in enumerate(personas):
            jobs.append((
                persona_idx,
                None,
                persona_dict,
                None,
                persona_idx + 1,
                uuid.uuid4(),
                None,
                None,
                None,
                None,
            ))

    # -------------------------------
    # EXECUTE PANEL CALLS
    # -------------------------------
    persona_cards = []
    max_workers = min(5, len(jobs)) if jobs else 1

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}

        for (
            persona_index,
            image_index,
            persona_dict,
            single_img,
            card_number,
            card_key,
            image_id,
            image_url,
            image_url_str,
            thumbnail_url,
            thumbnail_url_str,
            image_key,
        ) in jobs:

            card_context = {
                "card_number": card_number,
                "card_key": str(card_key),
                "persona_id": persona_dict["id"],
                "persona_name": persona_dict.get("name"),
                "image_id": image_id,
                "image_url": image_url,
                "image_url_str": image_url_str,
                "thumbnail_url":thumbnail_url,
                "thumbnail_url_str":thumbnail_url_str,
                "image_index": image_index,
                "persona_index": persona_index,
                "image_key": image_key,  # ✅ crucial
            }

            injected_text = (
                "### CARD_CONTEXT\n"
                f"{json.dumps(_json_safe(card_context))}\n"
                "### END_CARD_CONTEXT\n\n"
                f"{stimulus_text}"
            )

            future = executor.submit(
                analyze_single_persona_panel,
                persona_dict,
                injected_text,
                [single_img] if has_images else None,  # single image per card
                content_type
            )

            futures[future] = {**card_context}

        for future in concurrent.futures.as_completed(futures):
            meta = futures[future]
            try:
                result = future.result()
                result.update(meta)
                persona_cards.append(_json_safe(result))
            except Exception as e:
                logger.error(f"❌ Panel failed: {e}")
                persona_cards.append({"error": str(e), **meta})

    # ordering
    if has_images:
        persona_cards.sort(key=lambda x: (x.get("image_index", 0), x.get("persona_index", 0)))

    # -------------------------------
    # PER CARD SUMMARY
    # ✅ NO LLM CALL
    # ✅ Use exact keys:
    #    "aggregated_themes", "dissent_highlights", "recommendations"
    # -------------------------------
    for c in persona_cards:
        recs = c.get("recommendations", [])

        # if recommendations is ["...", "..."] convert to [{"suggestion":..., "reasoning":...}]
        if recs and isinstance(recs, list) and isinstance(recs[0], str):
            recs = [{"suggestion": r, "reasoning": ""} for r in recs]

        c["summary"] = {
            "aggregated_themes": [],
            "dissent_highlights": [],
            "recommendations": recs or [],
        }

    # -------------------------------
    # GROUP BY IMAGE (FIX: use image_key)
    # -------------------------------
    images_grouped: Dict[str, Dict[str, Any]] = {}

    if has_images:
        for card in persona_cards:
            ikey = card.get("image_key") or "unknown_image"
            if ikey not in images_grouped:
                images_grouped[ikey] = {
                    "image_key": ikey,
                    "image_id": card.get("image_id"),
                    "image_url": card.get("image_url"),
                    "image_url_str": card.get("image_url_str"),
                    "thumbnail_url":card.get("thumbnail_url"),
                    "thumbnail_url_str":card.get("thumbnail_url_str"),
                    "cards": []
                }
            images_grouped[ikey]["cards"].append(card)

        images_list = list(images_grouped.values())

        # -------------------------------
        # IMAGE SUMMARY (per image bucket)
        # -------------------------------
        if generate_image_summaries:
            with concurrent.futures.ThreadPoolExecutor(max_workers=min(5, max(1, len(images_list)))) as ex:
                futs = {}
                for img in images_list:
                    img_payload = [{
                        "id": img.get("image_id"),
                        "url": img.get("image_url"),
                        "image_url_str": img.get("image_url_str"),
                        "thumbnail_url":img.get("thumbnail_url"),
                        "thumbnail_url_str":img.get("thumbnail_url_str"),
                    }]
                    futs[ex.submit(synthesize_panel_summary, img["cards"], stimulus_text, img_payload, True)] = img["image_key"]

                for f in concurrent.futures.as_completed(futs):
                    ikey = futs[f]
                    try:
                        images_grouped[ikey]["image_summary"] = _json_safe(f.result())
                    except Exception as e:
                        images_grouped[ikey]["image_summary"] = {"image_summary_error": str(e)}

            images_list = list(images_grouped.values())
        else:
            for k in images_grouped:
                images_grouped[k]["image_summary"] = None
            images_list = list(images_grouped.values())

    else:
        images_list = [{
            "image_key": None,
            "image_id": None,
            "image_url": None,
            "image_url_str": None,
            "thumbnail_url": None,
            "thumbnail_url_str": None,
            "cards": persona_cards,
            "image_summary": None
        }]

    result = {
        "images": images_list,
        "metadata": {
            "persona_count": len(personas),
            "cards_count": len(persona_cards),
            "campaign_id": campaign_id,
            "task_id": task_id,
            "image_count": len(stimulus_images) if has_images else 0,
            "mapping_mode": "forced_cartesian" if has_images else "per_persona",
            "created_at": datetime.now().isoformat(),
            "generate_card_summaries": bool(generate_card_summaries),
            "generate_image_summaries": bool(generate_image_summaries),
        }
    }

    result = _json_safe(result)
    json.dumps(result)  # validate JSON-serializable
    logger.info("✅ Panel feedback complete")
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






# def run_panel_feedback_analysis(
#     persona_ids: List[int],
#     stimulus_text: str,
#     stimulus_images: Optional[List[Dict]] = None,
#     content_type: str = "text",
#     db = None
# ) -> Dict[str, Any]:
#     """
#     Run structured panel feedback analysis for the given personas.
    
#     Args:
#         persona_ids: List of persona IDs to include in the panel
#         stimulus_text: Text content of the marketing asset
#         stimulus_images: Optional list of images (base64 encoded)
#         content_type: 'text', 'image', or 'both'
#         db: Database session
    
#     Returns:
#         Dict containing persona_cards, summary, and metadata
#     """
    
#     if not persona_ids:
#         raise ValueError("At least one persona ID is required")
    
#     # Fetch personas from database
#     personas = []
#     for persona_id in persona_ids:
#         persona = crud.get_persona(db, persona_id)
#         if persona:
#             # Serialize to dict to avoid DetachedInstanceError in threads
#             personas.append({
#                 'id': persona.id,
#                 'name': persona.name,
#                 'age': persona.age,
#                 'gender': persona.gender,
#                 'condition': persona.condition,
#                 'location': persona.location,
#                 'persona_type': persona.persona_type,
#                 'avatar_url': getattr(persona, 'avatar_url', None),
#                 'full_persona_json': persona.full_persona_json
#             })
    
#     if not personas:
#         raise ValueError("No valid personas found for the provided IDs")
    
#     logger.info(f"🎯 Running panel feedback for {len(personas)} personas")
    
#     # Process personas in parallel
#     persona_cards = []
#     with concurrent.futures.ThreadPoolExecutor(max_workers=min(5, len(personas))) as executor:
#         futures = {
#             executor.submit(
#                 analyze_single_persona_panel,
#                 persona_dict,
#                 stimulus_text,
#                 stimulus_images,
#                 content_type
#             ): persona_dict['id']
#             for persona_dict in personas
#         }
        
#         for future in concurrent.futures.as_completed(futures):
#             try:
#                 result = future.result()
#                 persona_cards.append(result)
#             except Exception as e:
#                 persona_id = futures[future]
#                 logger.error(f"❌ Panel feedback failed for persona {persona_id}: {e}")
#                 persona_cards.append({
#                     "persona_id": persona_id,
#                     "persona_name": f"Persona {persona_id}",
#                     "error": str(e)
#                 })
    
#     # Sort by persona_id for consistent ordering
#     persona_cards.sort(key=lambda x: x.get('persona_id', 0))
    
#     # Synthesize summary
#     logger.info("📊 Synthesizing panel summary...")
#     summary = synthesize_panel_summary(persona_cards, stimulus_text)
    
#     # Build final result
#     result = {
#         "persona_cards": persona_cards,
#         "summary": summary,
#         "metadata": {
#             "persona_count": len(personas),
#             "content_type": content_type,
#             "created_at": datetime.now().isoformat()
#         }
#     }
    
#     logger.info(f"✅ Panel feedback analysis complete for {len(personas)} personas")
#     return result



