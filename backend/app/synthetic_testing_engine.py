# """
# Synthetic Testing Engine for PharmaPersonaSim.

# This module provides "Synthetic Testing" capabilities:
# 1. Objective scoring (1-7 scale) of marketing assets against key metrics.
# 2. Structured qualitative feedback (What works, what doesn't, improvements).
# 3. Aggregation of results across multiple personas and assets.
# """

# import os
# import json
# import logging
# import base64
# import concurrent.futures
# from typing import Dict, Any, List, Optional
# from datetime import datetime
# import requests

# from .utils import get_openai_client, MODEL_NAME
# from . import crud

# # Configure logging
# logger = logging.getLogger(__name__)

# # Model token limit
# MODEL_MAX_TOKENS = int(os.getenv("OPENAI_MODEL_MAX_TOKENS", "32768"))

# def _extract_json(text: str) -> str:
#     """Attempt to extract the first JSON object from arbitrary model text."""
#     import re
#     if not text:
#         return "{}"
#     # Remove fences
#     if text.startswith("```"):
#         text = re.sub(r"^```(json)?", "", text.strip(), flags=re.IGNORECASE).strip()
#     if text.endswith("```"):
#         text = text[:-3].strip()
#     # Fast path
#     try:
#         json.loads(text)
#         return text
#     except Exception:
#         pass
#     # Regex object match
#     match = re.search(r"\{[\s\S]*\}", text)
#     if match:
#         candidate = match.group(0)
#         try:
#             json.loads(candidate)
#             return candidate
#         except Exception:
#             return "{}"
#     return "{}"

# def _chat_json_synthetic(messages: List[Dict[str, Any]], max_completion_tokens: Optional[int] = None) -> Dict[str, Any]:
#     """Call chat.completions ensuring JSON-only output."""
#     client = get_openai_client()
#     if client is None:
#         return {"error": "OpenAI API key not configured"}
    
#     if max_completion_tokens is None:
#         max_completion_tokens = 2048
    
#     enforce = "\n\nReturn ONLY valid JSON. No commentary."
#     if messages and messages[-1].get("role") == "user":
#         for part in messages[-1].get("content", []):
#             if part.get("type") == "text":
#                 part["text"] += enforce
#                 break
#         else:
#             messages[-1]["content"].append({"type": "text", "text": enforce})

#     try:
#         response = client.chat.completions.create(
#             model=MODEL_NAME,
#             messages=messages,
#             max_completion_tokens=max_completion_tokens,
#             temperature=0.4, # Lower temperature for stable scoring
#             response_format={"type": "json_object"}
#         )
        
#         raw = response.choices[0].message.content if response.choices else "{}"
#         return json.loads(_extract_json(raw))
            
#     except Exception as e:
#         logger.error(f"❌ OpenAI API call failed: {e}")
#         return {"error": f"Analysis failed: {str(e)}"}

# def create_synthetic_prompt(
#     persona: Dict[str, Any],
#     asset_name: str,
#     stimulus_text: str,
#     has_image: bool
# ) -> str:
#     """Creates the prompt for synthetic testing."""
    
#     # Extract key persona attributes
#     full_persona = persona.get('full_persona', {})
#     segment = full_persona.get('persona_subtype') or full_persona.get('segment', 'Standard')
#     role = full_persona.get('specialty') or persona.get('condition', 'Patient')
    
#     content_desc = f"Message: \"{stimulus_text}\"" if stimulus_text else ""
#     if has_image:
#         content_desc += "\n(See attached image)"

#     return f"""
# You are simulating {persona['name']}, a {role} ({segment}), evaluating a pharmaceutical marketing asset named "{asset_name}".

# **YOUR PROFILE:**
# - Age: {persona['age']}
# - Gender: {persona['gender']}
# - Location: {persona['location']}
# - Bio: {json.dumps(full_persona.get('core', {}), indent=2)}
# - Additional Context: {json.dumps(persona.get('additional_context', {}), indent=2)}

# **MARKETING ASSET:**
# {content_desc}

# **TASK:**
# Evaluate this asset objectively on a 1-7 scale (1 = Poor/Low, 7 = Excellent/High) and provide specific qualitative feedback.

# **GUIDELINES FOR FEEDBACK:**
# - **BE CONCISE**: Use short, punchy bullet points (maximum 15 words per bullet).
# - **BE DIRECT**: Go straight to the point. No fluff.
# - **AVOID MARKETER ARGOT**: Speak as the patient/HCP would naturally but clearly.

# **METRICS TO SCORE (1-7):**
# 1. **Motivation to Prescribe** (or "Ask for" if patient): How strongly does this motivate action?
# 2. **Connection to Story**: Does the narrative/visual connect with your reality?
# 3. **Differentiation**: Is this unique compared to other treatments?
# 4. **Believability**: Do you trust this message?
# 5. **Stopping Power**: Does this grab your attention immediately?

# **QUALITATIVE FEEDBACK SECTIONS:**
# 1. **Does Well**: What this cover concept does well.
# 2. **Challenges**: What this cover concept does NOT do as well.
# 3. **Considerations**: Considerations to improve the cover concept.

# **OUTPUT JSON FORMAT:**
# {{
#     "scores": {{
#         "motivation_to_prescribe": <1-7 int>,
#         "connection_to_story": <1-7 int>,
#         "differentiation": <1-7 int>,
#         "believability": <1-7 int>,
#         "stopping_power": <1-7 int>
#     }},
#     "feedback": {{
#         "does_well": ["<concise bullet 1>", "<concise bullet 2>"],
#         "does_not_do_well": ["<concise bullet 1>", "<concise bullet 2>"],
#         "considerations": ["<concise bullet 1>", "<concise bullet 2>"]
#     }}
# }}
# """

# def analyze_single_asset_persona(
#     persona_dict: Dict[str, Any],
#     asset: Dict[str, Any]
# ) -> Dict[str, Any]:
#     """Analyze one asset for one persona."""
    
#     asset_name = asset.get('name', 'Unnamed Asset')
#     image_data = asset.get('data') 
#     text_content = asset.get('text', '')
    
#     prompt = create_synthetic_prompt(
#         persona_dict, 
#         asset_name, 
#         text_content, 
#         has_image=bool(image_data)
#     )
    
#     messages = [{"role": "user", "content": []}]
#     messages[0]["content"].append({"type": "text", "text": prompt})
    
#     if image_data:
#         # data is base64 string
#         messages[0]["content"].append({
#             "type": "image_url",
#             "image_url": {"url": f"data:image/png;base64,{image_data}"}
#         })
        
#     result = _chat_json_synthetic(messages)
    
#     if "error" in result:
#         return {
#             "persona_id": persona_dict['id'],
#             "asset_id": asset.get('id'),
#             "error": result["error"]
#         }
        
#     # Calculate Overall Preference (Aggregate of 5 metrics)
#     scores = result.get("scores", {})
#     total_score = sum(scores.values()) if scores else 0
#     # Normalize 5-35 sum to 0-100% preference
#     # (Score - 5) / (35 - 5) * 100 roughly
#     # Actually, simpler: Average score (1.0-7.0) 
#     # Let's map 1->0%, 4->50%, 7->100%
#     avg_score = total_score / 5.0 if scores else 0
#     preference_pct = int(((avg_score - 1) / 6.0) * 100) if avg_score >= 1 else 0
    
#     return {
#         "persona_id": persona_dict['id'],
#         "persona_name": persona_dict['name'],
#         "asset_id": asset.get('id'),
#         "scores": scores,
#         "overall_preference_score": preference_pct,
#         "feedback": result.get("feedback", {})
#     }

# def image_url_to_base64(url: str, timeout: int = 20) -> Dict[str, Optional[str]]:
#     r = requests.get(url, timeout=timeout)
#     r.raise_for_status()

#     content_type = (r.headers.get("Content-Type") or "").split(";")[0].strip().lower()

#     if content_type in ("image/png", "image/jpeg", "image/jpg", "image/webp"):
#         mime = "image/jpeg" if content_type == "image/jpg" else content_type
#     else:
#         mime = "image/png"

#     b64 = base64.b64encode(r.content).decode("utf-8")
#     return {"base64": b64, "mime": mime}


# def analyze_single_asset_persona_via_url(
#     persona_dict: Dict[str, Any],
#     asset: Dict[str, Any]
# ) -> Dict[str, Any]:

#     asset_name = asset.get("name", "Unnamed Asset")
#     text_content = asset.get("text", "")

#     image_data = None
#     mime = "image/png"

#     asset_url = asset.get("data")
#     if asset_url:
#         try:
#             out = image_url_to_base64(asset_url)
#             image_data = out["base64"]
#             mime = out["mime"] or "image/png"
#         except Exception as e:
#             return {
#         "persona_id": persona_dict["id"],
#         "persona_name": persona_dict["name"],
#         "asset_id": asset.get("id"),
#         "image_id":asset.get("id"),
#         "image_name":asset.get("name"),
#         "thumbnail_url":asset.get("thumbnail_url"),
#         "thumbnail_url_str":asset.get("thumbnail_url_str"),
#         "image_url": asset.get("data"),
#         "asset_url":asset.get("data"),
#                 "error": f"Failed to fetch/encode image url: {str(e)}"
#             }

#     prompt = create_synthetic_prompt(
#         persona_dict,
#         asset_name,
#         text_content,
#         has_image=bool(image_data)
#     )

#     messages = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]

#     if image_data:
#         messages[0]["content"].append({
#             "type": "image_url",
#             "image_url": {"url": f"data:{mime};base64,{image_data}"}
#         })

#     result = _chat_json_synthetic(messages)

#     if "error" in result:
#         return {
#              "persona_id": persona_dict["id"],
#         "persona_name": persona_dict["name"],
#         "asset_id": asset.get("id"),
#         "image_id":asset.get("id"),
#         "image_name":asset.get("name"),
#         "thumbnail_url":asset.get("thumbnail_url"),
#         "thumbnail_url_str":asset.get("thumbnail_url_str"),
#         "image_url": asset.get("data"),
#         "asset_url":asset.get("data"),
#             "error": result["error"]
#         }

#     scores = result.get("scores", {}) or {}
#     total_score = sum(scores.values()) if scores else 0
#     avg_score = (total_score / 5.0) if scores else 0
#     preference_pct = int(((avg_score - 1) / 6.0) * 100) if avg_score >= 1 else 0

#     if preference_pct < 0:
#         preference_pct = 0
#     if preference_pct > 100:
#         preference_pct = 100

#     return {
#         "persona_id": persona_dict["id"],
#         "persona_name": persona_dict["name"],
#         "asset_id": asset.get("id"),
#         "image_id":asset.get("id"),
#         "image_name":asset.get("name"),
#         "thumbnail_url":asset.get("thumbnail_url"),
#         "thumbnail_url_str":asset.get("thumbnail_url_str"),
#         "image_url": asset.get("data"),
#         "asset_url":asset.get("data"),
#         "scores": scores,
#         "overall_preference_score": preference_pct,
#         "feedback": result.get("feedback", {}) or {}
#     }


# def run_synthetic_testing(
#     persona_ids: List[int],
#     assets: List[Dict[str, Any]],
#     db = None
# ) -> Dict[str, Any]:
#     """
#     Run synthetic testing for multiple assets and personas.
    
#     Args:
#         persona_ids: List of persona IDs
#         assets: List of dicts {id: str, name: str, data: str|None, text: str}
#     """
    
#     # Fetch personas
#     try:
#         personas = []
#         for pid in persona_ids:
#             p = crud.get_persona(db, pid)
#             if p:
#                 personas.append({
#                     'id': p.id,
#                     'name': p.name,
#                     'age': p.age,
#                     'gender': p.gender,
#                     'location': p.location,
#                     'condition': p.condition,
#                     'condition': p.condition,
#                     'full_persona': json.loads(p.full_persona_json) if getattr(p, 'full_persona_json', None) else {},
#                     'additional_context': p.additional_context or {}
#                 })
                
#         if not personas:
#             return {"error": "No valid personas found"}

#         results = []
        
#         # Process all combinations in parallel
#         with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
#             futures = []
#             for persona in personas:
#                 for asset in assets:
#                     futures.append(
#                         executor.submit(analyze_single_asset_persona, persona, asset)
#                     )
                    
#             for future in concurrent.futures.as_completed(futures):
#                 try:
#                     res = future.result()
#                     results.append(res)
#                 except Exception as e:
#                     import traceback
#                     logger.error(f"Analysis task failed: {e}\n{traceback.format_exc()}")

#         # Aggregation
#         aggregated_results = {} # asset_id -> {metrics_avg, feedback_summary}
        
#         for asset in assets:
#             a_id = asset['id']
#             asset_responses = [r for r in results if r.get('asset_id') == a_id and 'error' not in r]
            
#             if not asset_responses:
#                 continue
                
#             # Calc averages
#             count = len(asset_responses)
#             avg_scores = {
#                 "motivation_to_prescribe": 0.0,
#                 "connection_to_story": 0.0,
#                 "differentiation": 0.0,
#                 "believability": 0.0,
#                 "stopping_power": 0.0
#             }
#             avg_pref = 0.0
            
#             for r in asset_responses:
#                 s = r.get('scores', {})
#                 if not s: continue # Skip if scores missing
#                 for k in avg_scores:
#                     avg_scores[k] += s.get(k, 0)
#                 avg_pref += r.get('overall_preference_score', 0)
                
#             for k in avg_scores:
#                 avg_scores[k] = round(avg_scores[k] / count, 1) if count > 0 else 0
            
#             aggregated_results[a_id] = {
#                 "asset_name": asset['name'],
#                 "average_scores": avg_scores,
#                 "average_preference": int(avg_pref / count) if count > 0 else 0,
#                 "respondent_count": count
#             }

#         return {
#             "results": results,
#             "aggregated": aggregated_results,
#             "metadata": {
#                 "personas_count": len(personas),
#                 "assets_count": len(assets),
#                 "timestamp": datetime.now().isoformat()
#             }
#         }
#     except Exception as e:
#         import traceback
#         logger.error(f"Global synthetic testing error: {e}\n{traceback.format_exc()}")
#         raise e



# def run_synthetic_testingV2(
#     campaign_id:str,
#     task_id:str,
#     persona_ids: List[int],
#     assets: List[Dict[str, Any]],
#     db = None
# ) -> Dict[str, Any]:
#     """
#     Run synthetic testing for multiple assets and personas.
    
#     Args:
#         persona_ids: List of persona IDs
#         assets: List of dicts {id: str, name: str, data: str|None, text: str}
#     """
    
#     # Fetch personas
#     try:
#         personas = []
#         for pid in persona_ids:
#             p = crud.get_persona(db, pid)
#             if p:
#                 personas.append({
#                     'id': p.id,
#                     'name': p.name,
#                     'age': p.age,
#                     'gender': p.gender,
#                     'location': p.location,
#                     'condition': p.condition,
#                     'condition': p.condition,
#                     'full_persona': json.loads(p.full_persona_json) if getattr(p, 'full_persona_json', None) else {},
#                     'additional_context': p.additional_context or {}
#                 })
                
#         if not personas:
#             return {"error": "No valid personas found"}

#         results = []
        
#         # Process all combinations in parallel
#         with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
#             futures = []
#             for persona in personas:
#                 for asset in assets:
#                     futures.append(
#                         executor.submit(analyze_single_asset_persona_via_url, persona, asset)
#                     )
                    
#             for future in concurrent.futures.as_completed(futures):
#                 try:
#                     res = future.result()
#                     results.append(res)
#                 except Exception as e:
#                     import traceback
#                     logger.error(f"Analysis task failed: {e}\n{traceback.format_exc()}")

#         # Aggregation
#         aggregated_results = {} # asset_id -> {metrics_avg, feedback_summary}
        
#         for asset in assets:
#             a_id = asset['id']
#             asset_responses = [r for r in results if r.get('asset_id') == a_id and 'error' not in r]
            
#             if not asset_responses:
#                 continue
                
#             # Calc averages
#             count = len(asset_responses)
#             avg_scores = {
#                 "motivation_to_prescribe": 0.0,
#                 "connection_to_story": 0.0,
#                 "differentiation": 0.0,
#                 "believability": 0.0,
#                 "stopping_power": 0.0
#             }
#             avg_pref = 0.0
            
#             for r in asset_responses:
#                 s = r.get('scores', {})
#                 if not s: continue # Skip if scores missing
#                 for k in avg_scores:
#                     avg_scores[k] += s.get(k, 0)
#                 avg_pref += r.get('overall_preference_score', 0)
                
#             for k in avg_scores:
#                 avg_scores[k] = round(avg_scores[k] / count, 1) if count > 0 else 0
            
#             aggregated_results[a_id] = {
#                 "asset_name": asset['name'],
#                 "average_scores": avg_scores,
#                 "average_preference": int(avg_pref / count) if count > 0 else 0,
#                 "respondent_count": count
#             }

#         return {
#             "results": results,
#             "aggregated": aggregated_results,
#             "metadata": {
#                 "campaign_id":campaign_id,
#                 "task_id":task_id,
#                 "personas_count": len(personas),
#                 "assets_count": len(assets),
#                 "timestamp": datetime.now().isoformat()
#             }
#         }
#     except Exception as e:
#         import traceback
#         logger.error(f"Global synthetic testing error: {e}\n{traceback.format_exc()}")
#         raise e




# import os
# import json
# import logging
# import base64
# import concurrent.futures
# from typing import Dict, Any, List, Optional, Tuple
# from datetime import datetime

# import requests

# from .utils import get_openai_client, MODEL_NAME
# from . import crud

# logger = logging.getLogger(__name__)

# MODEL_MAX_TOKENS = int(os.getenv("OPENAI_MODEL_MAX_TOKENS", "32768"))


# # =========================================================
# # ------------------- DEFAULT PROMPT TEMPLATE -------------
# # =========================================================

# DEFAULT_SYNTHETIC_PROMPT_TEMPLATE = """
# # You are {persona_name}, a {role} ({segment}), evaluating a pharmaceutical marketing asset named "{asset_name}".

# # **YOUR PROFILE:**
# # - Age: {persona_age}
# # - Gender: {persona_gender}
# # - Location: {persona_location}
# # - Bio: {core_bio_pretty}
# # - Additional Context: {additional_context_pretty}

# # **MARKETING ASSET:**
# # {content_desc}

# **TASK:**
# Evaluate this asset objectively on a 1-7 scale (1 = Poor/Low, 7 = Excellent/High) and provide specific qualitative feedback.

# **GUIDELINES FOR FEEDBACK:**
# - **BE CONCISE**: Use short, punchy bullet points (maximum 15 words per bullet).
# - **BE DIRECT**: Go straight to the point. No fluff.
# - **AVOID MARKETER ARGOT**: Speak as the patient/HCP would naturally but clearly.

# **METRICS TO SCORE (1-7):**
# 1. **Motivation to Prescribe** (or "Ask for" if patient): How strongly does this motivate action?
# 2. **Connection to Story**: Does the narrative/visual connect with your reality?
# 3. **Differentiation**: Is this unique compared to other treatments?
# 4. **Believability**: Do you trust this message?
# 5. **Stopping Power**: Does this grab your attention immediately?

# **QUALITATIVE FEEDBACK SECTIONS:**
# 1. **Does Well**: What this cover concept does well.
# 2. **Challenges**: What this cover concept does NOT do as well.
# 3. **Considerations**: Considerations to improve the cover concept.

# **OUTPUT JSON FORMAT:**
# {
#   "scores": {
#     "motivation_to_prescribe": <1-7 int>,
#     "connection_to_story": <1-7 int>,
#     "differentiation": <1-7 int>,
#     "believability": <1-7 int>,
#     "stopping_power": <1-7 int>
#   },
#   "feedback": {
#     "does_well": ["<concise bullet 1>", "<concise bullet 2>"],
#     "does_not_do_well": ["<concise bullet 1>", "<concise bullet 2>"],
#     "considerations": ["<concise bullet 1>", "<concise bullet 2>"]
#   }
# }
# """.strip()


# # =========================================================
# # ------------------- PROMPT HELPERS ----------------------
# # =========================================================

# def _is_blank(s: Optional[str]) -> bool:
#     return s is None or (isinstance(s, str) and s.strip() == "")


# def _pretty_json(obj: Any) -> str:
#     """Pretty JSON for prompt readability. Never throws."""
#     try:
#         return json.dumps(obj or {}, indent=2, ensure_ascii=False, sort_keys=True)
#     except Exception:
#         return "{}"


# def _quoted(text: str) -> str:
#     """
#     Safe quoting for prompt inclusion.
#     Uses JSON string encoding so quotes/newlines are preserved.
#     Example output: "Hello \\"world\\"\nNew line"
#     """
#     try:
#         return json.dumps(text or "", ensure_ascii=False)
#     except Exception:
#         return "\"\""


# class _SafeFormatDict(dict):
#     def __missing__(self, key: str) -> str:
#         # Keep unknown placeholders untouched (prevents crashes and preserves braces)
#         return "{" + key + "}"


# def _safe_format_map(template: str, variables: Dict[str, Any]) -> str:
#     """
#     Safe .format_map:
#     - substitutes ONLY keys present in `variables`
#     - preserves unknown {placeholders} as-is
#     - if braces are malformed -> returns template as-is
#     """
#     if _is_blank(template):
#         return template or ""

#     try:
#         clean: Dict[str, str] = {}
#         for k, v in variables.items():
#             if v is None:
#                 clean[k] = ""
#             elif isinstance(v, (dict, list, tuple)):
#                 clean[k] = _pretty_json(v)
#             else:
#                 clean[k] = str(v)

#         return template.format_map(_SafeFormatDict(clean))
#     except Exception as e:
#         logger.warning(f"[synthetic] safe_format_map failed, returning template as-is. err={e}")
#         return template


# def _safe_prompt_preview(s: str, n: int = 220) -> str:
#     s = (s or "").replace("\n", "\\n")
#     if len(s) <= n:
#         return s
#     return s[:n] + "..."


# def _build_synthetic_vars_map(
#     persona: Dict[str, Any],
#     asset_name: str,
#     stimulus_text: str,
#     has_image: bool
# ) -> Dict[str, Any]:
#     """
#     Locked variables ONLY.
#     Frontend can reference these keys in synthetic_prompt, e.g.:
#       {persona_name}, {role}, {segment}, {asset_name}, {content_desc}, etc.
#     """
#     full_persona = persona.get("full_persona", {}) or {}
#     segment = full_persona.get("persona_subtype") or full_persona.get("segment", "Standard")
#     role = full_persona.get("specialty") or persona.get("condition", "Patient")

#     stimulus_quoted = _quoted(stimulus_text or "")

#     content_desc = f"Message: {stimulus_quoted}" if (stimulus_text or "").strip() else 'Message: ""'
#     if has_image:
#         content_desc += "\n(See attached image)"

#     locked_map = {
#         # persona basics
#         "persona_id": persona.get("id"),
#         "persona_name": persona.get("name"),
#         "persona_age": persona.get("age"),
#         "persona_gender": persona.get("gender"),
#         "persona_location": persona.get("location"),

#         # persona derived
#         "role": role,
#         "segment": segment,

#         # asset
#         "asset_name": asset_name,
#         "stimulus_text": stimulus_text or "",
#         "stimulus_text_quoted": stimulus_quoted,
#         "has_image": has_image,
#         "content_desc": content_desc,

#         # pretty JSON blocks (string)
#         "core_bio_pretty": _pretty_json(full_persona.get("core", {})),
#         "full_persona_pretty": _pretty_json(full_persona),
#         "additional_context_pretty": _pretty_json(persona.get("additional_context", {})),
#     }
#     return locked_map


# def create_synthetic_prompt_pair(
#     persona: Dict[str, Any],
#     asset_name: str,
#     stimulus_text: str,
#     has_image: bool,
#     synthetic_prompt: str = ""
# ) -> Tuple[str, str]:
#     """
#     Returns:
#       prompt_used_for_model: rendered with locked vars (default or override)
#       prompt_echo_for_api:   raw override OR default template (unpopulated)
#     """
#     vars_map = _build_synthetic_vars_map(persona, asset_name, stimulus_text, has_image)
#     override_used = not _is_blank(synthetic_prompt)

#     logger.info(
#         f"[synthetic] create_synthetic_prompt_pair persona_id={vars_map.get('persona_id')} "
#         f"asset_name={asset_name} has_image={has_image} override_used={override_used}"
#     )

#     if override_used:
#         prompt_used = _safe_format_map(synthetic_prompt, vars_map).strip()
#         prompt_echo = synthetic_prompt.strip()  # ✅ RAW user prompt (unrendered)
#         logger.info(
#             f"[synthetic] override prompt rendered for model. locked_keys={len(vars_map)} "
#             f"prompt_used_len={len(prompt_used)} preview={_safe_prompt_preview(prompt_used)}"
#         )
#         return prompt_used, prompt_echo

#     # default: render for model, echo template for API (UNPOPULATED)
#     prompt_used = _safe_format_map(DEFAULT_SYNTHETIC_PROMPT_TEMPLATE, vars_map).strip()
#     prompt_echo = DEFAULT_SYNTHETIC_PROMPT_TEMPLATE
#     logger.info(
#         f"[synthetic] default prompt rendered for model. prompt_used_len={len(prompt_used)} "
#         f"preview={_safe_prompt_preview(prompt_used)}"
#     )
#     return prompt_used, prompt_echo


# # =========================================================
# # ------------------- JSON EXTRACTION ---------------------
# # =========================================================

# def _extract_json(text: str) -> str:
#     """Attempt to extract the first JSON object from arbitrary model text."""
#     import re

#     if not text:
#         return "{}"

#     t = text.strip()

#     # Remove markdown fences (```json ... ```)
#     if t.startswith("```"):
#         t = re.sub(r"^```(?:json)?", "", t, flags=re.IGNORECASE).strip()
#     if t.endswith("```"):
#         t = t[:-3].strip()

#     # Fast path: already JSON
#     try:
#         json.loads(t)
#         return t
#     except Exception:
#         pass

#     # Regex object match
#     match = re.search(r"\{[\s\S]*\}", t)
#     if match:
#         candidate = match.group(0)
#         try:
#             json.loads(candidate)
#             return candidate
#         except Exception:
#             return "{}"

#     return "{}"


# # =========================================================
# # ------------------- OPENAI CALL -------------------------
# # =========================================================

# def _chat_json_synthetic(
#     messages: List[Dict[str, Any]],
#     max_completion_tokens: Optional[int] = None
# ) -> Dict[str, Any]:
#     """Call chat.completions ensuring JSON-only output."""
#     client = get_openai_client()
#     if client is None:
#         return {"error": "OpenAI API key not configured"}

#     if max_completion_tokens is None:
#         max_completion_tokens = 2048

#     # Enforce JSON in the last user message
#     enforce = "\n\nReturn ONLY valid JSON. No commentary."
#     if messages and messages[-1].get("role") == "user":
#         content = messages[-1].get("content", [])
#         if isinstance(content, list):
#             for part in content:
#                 if isinstance(part, dict) and part.get("type") == "text":
#                     part["text"] = (part.get("text") or "") + enforce
#                     break
#             else:
#                 content.append({"type": "text", "text": enforce})
#         else:
#             messages[-1]["content"] = [{"type": "text", "text": str(content) + enforce}]

#     try:
#         logger.info(f"[synthetic] OpenAI call start model={MODEL_NAME} max_completion_tokens={max_completion_tokens}")
#         response = client.chat.completions.create(
#             model=MODEL_NAME,
#             messages=messages,
#             max_completion_tokens=max_completion_tokens,
#             temperature=0.4,
#             response_format={"type": "json_object"},
#         )
#         logger.info("[synthetic] OpenAI call success")

#         raw = response.choices[0].message.content if response.choices else "{}"
#         return json.loads(_extract_json(raw))

#     except Exception as e:
#         logger.error(f"❌ OpenAI API call failed: {e}")
#         return {"error": f"Analysis failed: {str(e)}"}


# # =========================================================
# # ------------------- SCORE NORMALIZATION -----------------
# # =========================================================

# def _to_int_1_7(x: Any) -> int:
#     try:
#         if isinstance(x, bool):
#             return 0
#         if isinstance(x, (int, float)):
#             v = int(round(float(x)))
#         elif isinstance(x, str):
#             v = int(round(float(x.strip())))
#         else:
#             return 0
#         if v < 1:
#             return 1
#         if v > 7:
#             return 7
#         return v
#     except Exception:
#         return 0


# def _normalize_scores_required(scores: Any) -> Dict[str, int]:
#     """
#     Ensures API response always includes the 5 required score fields.
#     Missing/invalid => 0
#     """
#     if not isinstance(scores, dict):
#         scores = {}

#     return {
#         "motivation_to_prescribe": _to_int_1_7(scores.get("motivation_to_prescribe")),
#         "connection_to_story": _to_int_1_7(scores.get("connection_to_story")),
#         "differentiation": _to_int_1_7(scores.get("differentiation")),
#         "believability": _to_int_1_7(scores.get("believability")),
#         "stopping_power": _to_int_1_7(scores.get("stopping_power")),
#     }


# # =========================================================
# # ------------------- FEEDBACK NORMALIZATION --------------
# # =========================================================

# def _as_list_str(x: Any) -> List[str]:
#     """
#     Always returns list[str].
#     - None/missing -> []
#     - string -> [string] (if non-empty)
#     - list -> keep only non-empty strings
#     - everything else -> []
#     """
#     if x is None:
#         return []
#     if isinstance(x, str):
#         s = x.strip()
#         return [s] if s else []
#     if isinstance(x, list):
#         out: List[str] = []
#         for v in x:
#             if isinstance(v, str):
#                 s = v.strip()
#                 if s:
#                     out.append(s)
#         return out
#     return []


# def _normalize_feedback(feedback: Any) -> Dict[str, List[str]]:
#     """
#     Ensures feedback sections are lists.
#     If model doesn't return something usable -> empty lists.
#     """
#     if not isinstance(feedback, dict):
#         feedback = {}

#     return {
#         "does_well": _as_list_str(feedback.get("does_well")),
#         "does_not_do_well": _as_list_str(feedback.get("does_not_do_well")),
#         "considerations": _as_list_str(feedback.get("considerations")),
#     }


# # =========================================================
# # ------------------- SINGLE ANALYSIS ---------------------
# # =========================================================

# def analyze_single_asset_persona(
#     persona_dict: Dict[str, Any],
#     asset: Dict[str, Any],
#     synthetic_prompt: str = ""
# ) -> Dict[str, Any]:
#     """Analyze one asset for one persona (image as base64 already)."""

#     asset_name = asset.get("name", "Unnamed Asset")
#     image_data = asset.get("data")  # base64 string
#     text_content = asset.get("text", "")

#     logger.info(
#         f"[synthetic] analyze_single_asset_persona start persona_id={persona_dict.get('id')} "
#         f"asset_id={asset.get('id')} has_image={bool(image_data)} override_provided={not _is_blank(synthetic_prompt)}"
#     )

#     prompt_used, prompt_echo = create_synthetic_prompt_pair(
#         persona_dict,
#         asset_name,
#         text_content,
#         has_image=bool(image_data),
#         synthetic_prompt=synthetic_prompt,
#     )

#     logger.info(
#         f"[synthetic] prompt selected persona_id={persona_dict.get('id')} asset_id={asset.get('id')} "
#         f"echo_is_default={_is_blank(synthetic_prompt)} prompt_used_len={len(prompt_used)} prompt_echo_len={len(prompt_echo)}"
#     )

#     messages = [{"role": "user", "content": [{"type": "text", "text": prompt_used}]}]

#     if image_data:
#         logger.info(f"[synthetic] attaching base64 image asset_id={asset.get('id')} b64_len={len(image_data)}")
#         messages[0]["content"].append({
#             "type": "image_url",
#             "image_url": {"url": f"data:image/png;base64,{image_data}"},
#         })

#     logger.info(f"[synthetic] OpenAI analyze start persona_id={persona_dict.get('id')} asset_id={asset.get('id')}")
#     result = _chat_json_synthetic(messages)
#     logger.info(f"[synthetic] OpenAI analyze end persona_id={persona_dict.get('id')} asset_id={asset.get('id')}")

#     if "error" in result:
#         logger.error(
#             f"[synthetic] analysis failed persona_id={persona_dict.get('id')} asset_id={asset.get('id')} err={result.get('error')}"
#         )
#         return {
#             "persona_id": persona_dict["id"],
#             "persona_name": persona_dict["name"],
#             "asset_id": asset.get("id"),
#             "synthetic_prompt": prompt_echo,  # ✅ RAW user prompt or DEFAULT TEMPLATE
#             "error": result["error"],
#         }

#     scores = _normalize_scores_required(result.get("scores", None))
#     feedback = _normalize_feedback(result.get("feedback", None))

#     # preference score: average of only valid (1..7) values
#     vals = [v for v in scores.values() if isinstance(v, int) and 1 <= v <= 7]
#     if vals:
#         avg_score = sum(vals) / float(len(vals))
#         preference_pct = int(((avg_score - 1) / 6.0) * 100) if avg_score >= 1 else 0
#         preference_pct = max(0, min(100, preference_pct))
#     else:
#         avg_score = 0.0
#         preference_pct = 0

#     logger.info(
#         f"[synthetic] analysis success persona_id={persona_dict.get('id')} asset_id={asset.get('id')} "
#         f"avg_score={avg_score:.2f} preference_pct={preference_pct}"
#     )

#     return {
#         "persona_id": persona_dict["id"],
#         "persona_name": persona_dict["name"],
#         "asset_id": asset.get("id"),
#         "synthetic_prompt": prompt_echo,  # ✅ RAW user prompt or DEFAULT TEMPLATE
#         "scores": scores,
#         "overall_preference_score": preference_pct,
#         "feedback": feedback,
#     }


# # =========================================================
# # ------------------- IMAGE URL -> B64 --------------------
# # =========================================================

# def image_url_to_base64(url: str, timeout: int = 20) -> Dict[str, Optional[str]]:
#     logger.info(f"[synthetic] image_url_to_base64 start url_present={bool(url)} timeout={timeout}")

#     r = requests.get(url, timeout=timeout)
#     r.raise_for_status()

#     content_type = (r.headers.get("Content-Type") or "").split(";")[0].strip().lower()

#     if content_type in ("image/png", "image/jpeg", "image/jpg", "image/webp"):
#         mime = "image/jpeg" if content_type == "image/jpg" else content_type
#     else:
#         mime = "image/png"

#     b64 = base64.b64encode(r.content).decode("utf-8")

#     logger.info(
#         f"[synthetic] image_url_to_base64 success content_type={content_type} mime={mime} bytes={len(r.content)} b64_len={len(b64)}"
#     )
#     return {"base64": b64, "mime": mime}


# def analyze_single_asset_persona_via_url(
#     persona_dict: Dict[str, Any],
#     asset: Dict[str, Any],
#     synthetic_prompt: str = ""
# ) -> Dict[str, Any]:
#     """Analyze one asset for one persona (image fetched by URL)."""

#     asset_name = asset.get("name", "Unnamed Asset")
#     text_content = asset.get("text", "")

#     logger.info(
#         f"[synthetic] analyze_single_asset_persona_via_url start persona_id={persona_dict.get('id')} "
#         f"asset_id={asset.get('id')} override_provided={not _is_blank(synthetic_prompt)}"
#     )

#     image_data = None
#     mime = "image/png"

#     asset_url = asset.get("data")
#     if asset_url:
#         try:
#             logger.info(f"[synthetic] fetching image url asset_id={asset.get('id')}")
#             out = image_url_to_base64(asset_url)
#             image_data = out["base64"]
#             mime = out["mime"] or "image/png"
#             logger.info(f"[synthetic] image fetched+encoded asset_id={asset.get('id')} mime={mime} b64_len={len(image_data)}")
#         except Exception as e:
#             logger.error(f"[synthetic] image fetch failed asset_id={asset.get('id')} err={e}")

#             prompt_used, prompt_echo = create_synthetic_prompt_pair(
#                 persona_dict,
#                 asset_name,
#                 text_content,
#                 has_image=False,
#                 synthetic_prompt=synthetic_prompt,
#             )

#             return {
#                 "persona_id": persona_dict["id"],
#                 "persona_name": persona_dict["name"],
#                 "asset_id": asset.get("id"),
#                 "image_id": asset.get("id"),
#                 "image_name": asset.get("name"),
#                 "thumbnail_url": asset.get("thumbnail_url"),
#                 "thumbnail_url_str": asset.get("thumbnail_url_str"),
#                 "image_url": asset.get("data"),
#                 "asset_url": asset.get("data"),
#                 "synthetic_prompt": prompt_echo,  # ✅ RAW user prompt or DEFAULT TEMPLATE
#                 "scores": _normalize_scores_required(None),  # ✅ satisfy pydantic
#                 "overall_preference_score": 0,
#                 "feedback": _normalize_feedback(None),
#                 "error": f"Failed to fetch/encode image url: {str(e)}",
#             }

#     prompt_used, prompt_echo = create_synthetic_prompt_pair(
#         persona_dict,
#         asset_name,
#         text_content,
#         has_image=bool(image_data),
#         synthetic_prompt=synthetic_prompt,
#     )

#     logger.info(
#         f"[synthetic] prompt selected via_url persona_id={persona_dict.get('id')} asset_id={asset.get('id')} "
#         f"echo_is_default={_is_blank(synthetic_prompt)} prompt_used_len={len(prompt_used)} prompt_echo_len={len(prompt_echo)}"
#     )

#     messages = [{"role": "user", "content": [{"type": "text", "text": prompt_used}]}]

#     if image_data:
#         messages[0]["content"].append({
#             "type": "image_url",
#             "image_url": {"url": f"data:{mime};base64,{image_data}"},
#         })

#     logger.info(f"[synthetic] OpenAI analyze start via_url persona_id={persona_dict.get('id')} asset_id={asset.get('id')}")
#     result = _chat_json_synthetic(messages)
#     logger.info(f"[synthetic] OpenAI analyze end via_url persona_id={persona_dict.get('id')} asset_id={asset.get('id')}")

#     if "error" in result:
#         logger.error(
#             f"[synthetic] analysis failed via_url persona_id={persona_dict.get('id')} asset_id={asset.get('id')} err={result.get('error')}"
#         )
#         return {
#             "persona_id": persona_dict["id"],
#             "persona_name": persona_dict["name"],
#             "asset_id": asset.get("id"),
#             "image_id": asset.get("id"),
#             "image_name": asset.get("name"),
#             "thumbnail_url": asset.get("thumbnail_url"),
#             "thumbnail_url_str": asset.get("thumbnail_url_str"),
#             "image_url": asset.get("data"),
#             "asset_url": asset.get("data"),
#             "synthetic_prompt": prompt_echo,  # ✅ RAW user prompt or DEFAULT TEMPLATE
#             "scores": _normalize_scores_required(None),  # ✅ satisfy pydantic
#             "overall_preference_score": 0,
#             "feedback": _normalize_feedback(None),
#             "error": result["error"],
#         }

#     scores = _normalize_scores_required(result.get("scores", None))
#     feedback = _normalize_feedback(result.get("feedback", None))

#     vals = [v for v in scores.values() if isinstance(v, int) and 1 <= v <= 7]
#     if vals:
#         avg_score = sum(vals) / float(len(vals))
#         preference_pct = int(((avg_score - 1) / 6.0) * 100) if avg_score >= 1 else 0
#         preference_pct = max(0, min(100, preference_pct))
#     else:
#         avg_score = 0.0
#         preference_pct = 0

#     logger.info(
#         f"[synthetic] analysis success via_url persona_id={persona_dict.get('id')} asset_id={asset.get('id')} "
#         f"avg_score={avg_score:.2f} preference_pct={preference_pct}"
#     )

#     return {
#         "persona_id": persona_dict["id"],
#         "persona_name": persona_dict["name"],
#         "asset_id": asset.get("id"),
#         "image_id": asset.get("id"),
#         "image_name": asset.get("name"),
#         "thumbnail_url": asset.get("thumbnail_url"),
#         "thumbnail_url_str": asset.get("thumbnail_url_str"),
#         "image_url": asset.get("data"),
#         "asset_url": asset.get("data"),
#         "synthetic_prompt": prompt_echo,  # ✅ RAW user prompt or DEFAULT TEMPLATE
#         "scores": scores,
#         "overall_preference_score": preference_pct,
#         "feedback": feedback,
#     }


# # =========================================================
# # ------------------- RUNNER V1 ---------------------------
# # =========================================================

# def run_synthetic_testing(
#     persona_ids: List[int],
#     assets: List[Dict[str, Any]],
#     db=None,
#     synthetic_prompt: str = ""
# ) -> Dict[str, Any]:
#     """
#     Run synthetic testing for multiple assets and personas.
#     assets: [{id, name, data(base64|None), text}]
#     """

#     logger.info(
#         f"[synthetic] run_synthetic_testing start persona_ids={persona_ids} assets_count={len(assets)} "
#         f"override_provided={not _is_blank(synthetic_prompt)}"
#     )

#     try:
#         personas = []
#         for pid in persona_ids:
#             p = crud.get_persona(db, pid)
#             if p:
#                 personas.append({
#                     "id": p.id,
#                     "name": p.name,
#                     "age": p.age,
#                     "gender": p.gender,
#                     "location": p.location,
#                     "condition": p.condition,
#                     "full_persona": json.loads(p.full_persona_json) if getattr(p, "full_persona_json", None) else {},
#                     "additional_context": p.additional_context or {},
#                 })
#                 logger.info(f"[synthetic] loaded persona pid={pid}")
#             else:
#                 logger.warning(f"[synthetic] persona not found pid={pid}")

#         if not personas:
#             logger.error("[synthetic] No valid personas found")
#             return {"error": "No valid personas found"}

#         results: List[Dict[str, Any]] = []

#         with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
#             futures = []
#             for persona in personas:
#                 for asset in assets:
#                     futures.append(executor.submit(analyze_single_asset_persona, persona, asset, synthetic_prompt))

#             logger.info(f"[synthetic] submitted tasks count={len(futures)}")

#             for future in concurrent.futures.as_completed(futures):
#                 try:
#                     res = future.result()
#                     results.append(res)
#                 except Exception as e:
#                     import traceback
#                     logger.error(f"[synthetic] Analysis task failed: {e}\n{traceback.format_exc()}")

#         logger.info(f"[synthetic] all tasks done results_count={len(results)}")

#         aggregated_results: Dict[str, Any] = {}

#         for asset in assets:
#             a_id = asset["id"]
#             asset_responses = [r for r in results if r.get("asset_id") == a_id and "error" not in r]
#             if not asset_responses:
#                 logger.warning(f"[synthetic] no successful responses for asset_id={a_id}")
#                 continue

#             sums = {
#                 "motivation_to_prescribe": 0.0,
#                 "connection_to_story": 0.0,
#                 "differentiation": 0.0,
#                 "believability": 0.0,
#                 "stopping_power": 0.0,
#             }
#             counts = {
#                 "motivation_to_prescribe": 0,
#                 "connection_to_story": 0,
#                 "differentiation": 0,
#                 "believability": 0,
#                 "stopping_power": 0,
#             }

#             pref_sum = 0.0
#             pref_count = 0

#             for r in asset_responses:
#                 s = r.get("scores", {}) or {}
#                 if isinstance(s, dict):
#                     for k in sums.keys():
#                         v = s.get(k, 0)
#                         if isinstance(v, (int, float)) and 1 <= float(v) <= 7:
#                             sums[k] += float(v)
#                             counts[k] += 1

#                 op = r.get("overall_preference_score", None)
#                 if isinstance(op, (int, float)):
#                     pref_sum += float(op)
#                     pref_count += 1

#             avg_scores = {}
#             for k in sums.keys():
#                 c = counts.get(k, 0)
#                 avg_scores[k] = round(sums[k] / c, 1) if c > 0 else 0.0

#             aggregated_results[a_id] = {
#                 "asset_name": asset.get("name"),
#                 "average_scores": avg_scores,
#                 "average_preference": int(pref_sum / pref_count) if pref_count > 0 else 0,
#                 "respondent_count": len(asset_responses),
#             }

#             logger.info(f"[synthetic] aggregated asset_id={a_id} respondent_count={len(asset_responses)}")

#         logger.info("[synthetic] run_synthetic_testing end")

#         top_prompt_echo = synthetic_prompt.strip() if not _is_blank(synthetic_prompt) else DEFAULT_SYNTHETIC_PROMPT_TEMPLATE

#         return {
#             "results": results,
#             "aggregated": aggregated_results,
#             "metadata": {
#                 "personas_count": len(personas),
#                 "assets_count": len(assets),
#                 "timestamp": datetime.now().isoformat(),
#                 "synthetic_prompt_provided": (not _is_blank(synthetic_prompt)),
#             },
#             "synthetic_prompt": top_prompt_echo,
#         }

#     except Exception as e:
#         import traceback
#         logger.error(f"[synthetic] Global synthetic testing error: {e}\n{traceback.format_exc()}")
#         raise


# # =========================================================
# # ------------------- RUNNER V2 (URL) ---------------------
# # =========================================================

# def run_synthetic_testingV2(
#     campaign_id: str,
#     task_id: str,
#     persona_ids: List[int],
#     assets: List[Dict[str, Any]],
#     synthetic_prompt: str = "",
#     db=None
# ) -> Dict[str, Any]:
#     """
#     assets: [{id, name, data(url|None), text}]
#     """

#     logger.info(
#         f"[synthetic] run_synthetic_testingV2 start campaign_id={campaign_id} task_id={task_id} "
#         f"persona_ids={persona_ids} assets_count={len(assets)} override_provided={not _is_blank(synthetic_prompt)}"
#     )

#     try:
#         personas = []
#         for pid in persona_ids:
#             p = crud.get_persona(db, pid)
#             if p:
#                 personas.append({
#                     "id": p.id,
#                     "name": p.name,
#                     "age": p.age,
#                     "gender": p.gender,
#                     "location": p.location,
#                     "condition": p.condition,
#                     "full_persona": json.loads(p.full_persona_json) if getattr(p, "full_persona_json", None) else {},
#                     "additional_context": p.additional_context or {},
#                 })
#                 logger.info(f"[synthetic] loaded persona pid={pid}")
#             else:
#                 logger.warning(f"[synthetic] persona not found pid={pid}")

#         if not personas:
#             logger.error("[synthetic] No valid personas found (V2)")
#             return {"error": "No valid personas found"}

#         results: List[Dict[str, Any]] = []

#         with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
#             futures = []
#             for persona in personas:
#                 for asset in assets:
#                     futures.append(executor.submit(analyze_single_asset_persona_via_url, persona, asset, synthetic_prompt))

#             logger.info(f"[synthetic] submitted tasks (V2) count={len(futures)}")

#             for future in concurrent.futures.as_completed(futures):
#                 try:
#                     res = future.result()
#                     results.append(res)
#                 except Exception as e:
#                     import traceback
#                     logger.error(f"[synthetic] Analysis task failed (V2): {e}\n{traceback.format_exc()}")

#         logger.info(f"[synthetic] all tasks done (V2) results_count={len(results)}")

#         aggregated_results: Dict[str, Any] = {}

#         for asset in assets:
#             a_id = asset["id"]
#             asset_responses = [r for r in results if r.get("asset_id") == a_id and "error" not in r]
#             if not asset_responses:
#                 logger.warning(f"[synthetic] no successful responses (V2) for asset_id={a_id}")
#                 continue

#             sums = {
#                 "motivation_to_prescribe": 0.0,
#                 "connection_to_story": 0.0,
#                 "differentiation": 0.0,
#                 "believability": 0.0,
#                 "stopping_power": 0.0,
#             }
#             counts = {
#                 "motivation_to_prescribe": 0,
#                 "connection_to_story": 0,
#                 "differentiation": 0,
#                 "believability": 0,
#                 "stopping_power": 0,
#             }

#             pref_sum = 0.0
#             pref_count = 0

#             for r in asset_responses:
#                 s = r.get("scores", {}) or {}
#                 if isinstance(s, dict):
#                     for k in sums.keys():
#                         v = s.get(k, 0)
#                         if isinstance(v, (int, float)) and 1 <= float(v) <= 7:
#                             sums[k] += float(v)
#                             counts[k] += 1

#                 op = r.get("overall_preference_score", None)
#                 if isinstance(op, (int, float)):
#                     pref_sum += float(op)
#                     pref_count += 1

#             avg_scores = {}
#             for k in sums.keys():
#                 c = counts.get(k, 0)
#                 avg_scores[k] = round(sums[k] / c, 1) if c > 0 else 0.0

#             aggregated_results[a_id] = {
#                 "asset_name": asset.get("name"),
#                 "average_scores": avg_scores,
#                 "average_preference": int(pref_sum / pref_count) if pref_count > 0 else 0,
#                 "respondent_count": len(asset_responses),
#             }
#             logger.info(f"[synthetic] aggregated (V2) asset_id={a_id} respondent_count={len(asset_responses)}")

#         top_prompt_echo = synthetic_prompt.strip() if not _is_blank(synthetic_prompt) else DEFAULT_SYNTHETIC_PROMPT_TEMPLATE

#         logger.info("[synthetic] run_synthetic_testingV2 end")

#         return {
#             "results": results,
#             "aggregated": aggregated_results,
#             "metadata": {
#                 "campaign_id": campaign_id,
#                 "task_id": task_id,
#                 "personas_count": len(personas),
#                 "assets_count": len(assets),
#                 "timestamp": datetime.now().isoformat(),
#                 "override_provided": (not _is_blank(synthetic_prompt)),
#             },
#             "synthetic_prompt": top_prompt_echo,  # ✅ RAW user prompt OR DEFAULT TEMPLATE (unpopulated)
#         }

#     except Exception as e:
#         import traceback
#         logger.error(f"[synthetic] Global synthetic testing error (V2): {e}\n{traceback.format_exc()}")
#         raise

import os
import json
import logging
import base64
import concurrent.futures
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

import requests

from .utils import get_openai_client, MODEL_NAME
from . import crud

logger = logging.getLogger(__name__)

MODEL_MAX_TOKENS = int(os.getenv("OPENAI_MODEL_MAX_TOKENS", "32768"))


# =========================================================
# ------------------- DEFAULT PROMPT TEMPLATE -------------
# =========================================================

DEFAULT_SYNTHETIC_PROMPT_TEMPLATE = """
# You are {persona_name}, a {role} ({segment}), evaluating a pharmaceutical marketing asset named "{asset_name}".

# **YOUR PROFILE:**
# - Age: {persona_age}
# - Gender: {persona_gender}
# - Location: {persona_location}
# - Bio: {core_bio_pretty}
# - Additional Context: {additional_context_pretty}

# **MARKETING ASSET:**
# {content_desc}

**TASK:**
Evaluate this asset objectively on a 1.0-7.0 scale (1.0 = Poor/Low, 7.0 = Excellent/High) and provide specific qualitative feedback. Give score with 1 decimal point too. For each score, provide a brief rationale (1-2 sentances) explaining why you gave that specific score.

**GUIDELINES FOR FEEDBACK:**
- **BE CONCISE**: Use short, punchy bullet points (maximum 15 words per bullet).
- **BE DIRECT**: Go straight to the point. No fluff.
- **AVOID MARKETER ARGOT**: Speak as the patient/HCP would naturally but clearly.

**METRICS TO SCORE (1.0-7.0):**
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
{
  "scores": {
    "motivation_to_prescribe": <1-7 float>,
    "connection_to_story": <1-7 float>,
    "differentiation": <1-7 float>,
    "believability": <1-7 float>,
    "stopping_power": <1-7 float>
  },
  "score_rationale": {
    "motivation_to_prescribe": "<1-2 sentence rationale for this score>",
    "connection_to_story": "<1-2 sentence rationale for this score>",
    "differentiation": "<1-2 sentence rationale for this score>",
    "believability": "<1-2 sentence rationale for this score>",
    "stopping_power": "<1-2 sentence rationale for this score>"
  },
  "feedback": {
    "does_well": ["<concise bullet 1>", "<concise bullet 2>"],
    "does_not_do_well": ["<concise bullet 1>", "<concise bullet 2>"],
    "considerations": ["<concise bullet 1>", "<concise bullet 2>"]
  }
}
""".strip()

DEFAULT_EMOTION_PROMPT = """
You are an expert AI persona simulator and medical marketing analyst. Your task is to evaluate marketing concepts/images through the lens of specific Healthcare Professional (HCP) personas.
 
Instead of generating long-form text, you must output a structured matrix called "Emotional Response". In this matrix, Concepts must be the rows, and Personas must be the columns.
 
For each "cell" (the intersection of a Concept and a Persona), generate two specific data points:
Emotional Response: A concise, 1-2 sentence description of the persona's immediate psychological and emotional reaction to the visual and copy.
Gut Check: An immediate RAG status indicating their overall receptiveness:
   - GREEN: Positive reaction, feels aligned, trusting, and ready to engage.
   - AMBER: Mixed reaction, feels intrigued but hesitant, requires more data or clarification.
   - RED: Negative reaction, feels alienated, skeptical, confused, or dismissive.
 
Input Data:
Concepts to evaluate (Rows):
{asset_text}

Personas to simulate (Columns):
{persona_text}
 
Output format:
Return ONLY a valid JSON object with a single key "emotion_data" which is an array. Each object in the array represents the evaluation of a single Concept by a single Persona. Do not include introductory text or markdown formatting outside of the JSON block.
 
Use this exact JSON schema:
 
{{
  "emotion_data": [
    {{
      "concept_name": "Name of the image/concept",
      "persona_name": "Persona Name",
      "persona_subtype": "Persona Subtype",
      "emotion_response": "1-2 sentence emotional reaction.",
      "gut_check": "Green"
    }},
    {{
      "concept_name": "Name of the image/concept",
      "persona_name": "Another Persona Name",
      "persona_subtype": "Persona Subtype",
      "emotion_response": "1-2 sentence emotional reaction.",
      "gut_check": "Red"
    }}
  ]
}}
""".strip()


# =========================================================
# ------------------- PROMPT HELPERS ----------------------
# =========================================================

def _is_blank(s: Optional[str]) -> bool:
    return s is None or (isinstance(s, str) and s.strip() == "")


def _pretty_json(obj: Any) -> str:
    """Pretty JSON for prompt readability. Never throws."""
    try:
        return json.dumps(obj or {}, indent=2, ensure_ascii=False, sort_keys=True)
    except Exception:
        return "{}"


def _quoted(text: str) -> str:
    """
    Safe quoting for prompt inclusion.
    Uses JSON string encoding so quotes/newlines are preserved.
    Example output: "Hello \\"world\\"\nNew line"
    """
    try:
        return json.dumps(text or "", ensure_ascii=False)
    except Exception:
        return "\"\""


class _SafeFormatDict(dict):
    def __missing__(self, key: str) -> str:
        # Keep unknown placeholders untouched (prevents crashes and preserves braces)
        return "{" + key + "}"


def _safe_format_map(template: str, variables: Dict[str, Any]) -> str:
    """
    Safe .format_map:
    - substitutes ONLY keys present in `variables`
    - preserves unknown {placeholders} as-is
    - if braces are malformed -> returns template as-is
    """
    if _is_blank(template):
        return template or ""

    try:
        clean: Dict[str, str] = {}
        for k, v in variables.items():
            if v is None:
                clean[k] = ""
            elif isinstance(v, (dict, list, tuple)):
                clean[k] = _pretty_json(v)
            else:
                clean[k] = str(v)

        return template.format_map(_SafeFormatDict(clean))
    except Exception as e:
        logger.warning(f"[synthetic] safe_format_map failed, returning template as-is. err={e}")
        return template


def _safe_prompt_preview(s: str, n: int = 220) -> str:
    s = (s or "").replace("\n", "\\n")
    if len(s) <= n:
        return s
    return s[:n] + "..."


# =========================================================
# ------------------- JSON EXTRACTION ---------------------
# =========================================================

def _extract_json(text: str) -> str:
    """Attempt to extract the first JSON object from arbitrary model text."""
    import re

    if not text:
        return "{}"

    t = text.strip()

    # Remove markdown fences (```json ... ```)
    if t.startswith("```"):
        t = re.sub(r"^```(?:json)?", "", t, flags=re.IGNORECASE).strip()
    if t.endswith("```"):
        t = t[:-3].strip()

    # Fast path: already JSON
    try:
        json.loads(t)
        return t
    except Exception:
        pass

    # Regex object match
    match = re.search(r"\{[\s\S]*\}", t)
    if match:
        candidate = match.group(0)
        try:
            json.loads(candidate)
            return candidate
        except Exception:
            return "{}"

    return "{}"


# =========================================================
# ------------------- OPENAI CALL -------------------------
# =========================================================

def _chat_json_synthetic(
    messages: List[Dict[str, Any]],
    max_completion_tokens: Optional[int] = None
) -> Dict[str, Any]:
    """Call chat.completions ensuring JSON-only output."""
    client = get_openai_client()
    if client is None:
        return {"error": "OpenAI API key not configured"}

    if max_completion_tokens is None:
        max_completion_tokens = 2048

    # Enforce JSON in the last user message
    enforce = "\n\nReturn ONLY valid JSON. No commentary."
    if messages and messages[-1].get("role") == "user":
        content = messages[-1].get("content", [])
        if isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    part["text"] = (part.get("text") or "") + enforce
                    break
            else:
                content.append({"type": "text", "text": enforce})
        else:
            messages[-1]["content"] = [{"type": "text", "text": str(content) + enforce}]

    try:
        logger.info(
            f"[synthetic] OpenAI call start model={MODEL_NAME} max_completion_tokens={max_completion_tokens}"
        )
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            max_completion_tokens=max_completion_tokens,
            temperature=0.4,
            response_format={"type": "json_object"},
        )
        logger.info("[synthetic] OpenAI call success")

        raw = response.choices[0].message.content if response.choices else "{}"
        return json.loads(_extract_json(raw))

    except Exception as e:
        logger.error(f"❌ OpenAI API call failed: {e}")
        return {"error": f"Analysis failed: {str(e)}"}


# =========================================================
# -------- NEW: ASSET IMAGE DESCRIPTORS (URL-BASED) -------
# =========================================================

ASSET_DESCRIPTOR_PROMPT = (
    "You are labeling marketing images.\n"
    "For each image, generate a short 2–3 word descriptor.\n\n"
    "Rules:\n"
    "- 2 to 3 words only\n"
    "- No punctuation, no emojis\n"
    "- Title Case preferred\n"
    "- Must be based only on what you can see\n"
    "- If unclear: return \"Unclear Visual\"\n\n"
    "Return STRICT JSON ONLY:\n"
    "{\n"
    "  \"descriptors\": [\n"
    "    {\"index\": 0, \"descriptor\": \"...\"},\n"
    "    {\"index\": 1, \"descriptor\": \"...\"}\n"
    "  ]\n"
    "}\n"
)


def _attach_asset_urls_to_parts(parts: List[Dict[str, Any]], assets: List[Dict[str, Any]]) -> None:
    """
    Attach asset images (url) to multimodal parts.
    Expects asset['data'] to be a URL (as in V2).
    """
    if not assets:
        return

    for a in assets:
        if not isinstance(a, dict):
            continue
        url = a.get("data")  # V2: url stored in data
        if isinstance(url, str) and url.strip():
            parts.append({"type": "image_url", "image_url": {"url": url.strip()}})


def generate_asset_image_descriptors_via_url(
    assets: List[Dict[str, Any]],
    max_assets: int = 12,
) -> List[Dict[str, Any]]:
    """
    Adds `image_descriptor` to each asset dict (V2 assets with url in `data`)
    using ONE batched multimodal call.

    Safe fallback: "Asset 1", "Asset 2", etc.
    """
    if not assets or not isinstance(assets, list):
        return assets

    subset = assets[:max_assets]

    parts: List[Dict[str, Any]] = [{"type": "text", "text": ASSET_DESCRIPTOR_PROMPT}]
    for i, asset in enumerate(subset):
        parts.append({"type": "text", "text": f"\nAsset index: {i}\n"})
        _attach_asset_urls_to_parts(parts, [asset])

    messages = [{"role": "user", "content": parts}]
    data = _chat_json_synthetic(messages, max_completion_tokens=600)

    idx_to_desc: Dict[int, str] = {}
    if isinstance(data, dict) and "error" not in data:
        rows = data.get("descriptors") or []
        if isinstance(rows, list):
            for row in rows:
                if not isinstance(row, dict):
                    continue
                idx = row.get("index")
                desc = row.get("descriptor")
                if isinstance(idx, int) and isinstance(desc, str) and desc.strip():
                    idx_to_desc[idx] = desc.strip()

    for i, asset in enumerate(subset):
        if isinstance(asset, dict):
            asset["image_descriptor"] = idx_to_desc.get(i) or f"Asset {i+1}"

    for i in range(max_assets, len(assets)):
        if isinstance(assets[i], dict) and "image_descriptor" not in assets[i]:
            assets[i]["image_descriptor"] = f"Asset {i+1}"

    return assets


# =========================================================
# ------------------- SCORE NORMALIZATION -----------------
# =========================================================

def _to_float_1_7(x: Any) -> float:
    """
    Keeps score as float with 1 decimal place.
    Valid range: 1.0 to 7.0
    Invalid/missing => 0.0
    """
    try:
        if isinstance(x, bool):
            return 0.0

        if isinstance(x, (int, float)):
            v = round(float(x), 1)
        elif isinstance(x, str):
            v = round(float(x.strip()), 1)
        else:
            return 0.0

        if v < 1.0:
            return 1.0
        if v > 7.0:
            return 7.0

        return round(v, 1)
    except Exception:
        return 0.0


def _normalize_scores_required(scores: Any) -> Dict[str, float]:
    """
    Ensures API response always includes the 5 required score fields.
    Missing/invalid => 0.0
    Keeps 1 decimal place.
    """
    if not isinstance(scores, dict):
        scores = {}

    return {
        "motivation_to_prescribe": _to_float_1_7(scores.get("motivation_to_prescribe")),
        "connection_to_story": _to_float_1_7(scores.get("connection_to_story")),
        "differentiation": _to_float_1_7(scores.get("differentiation")),
        "believability": _to_float_1_7(scores.get("believability")),
        "stopping_power": _to_float_1_7(scores.get("stopping_power")),
    }


# =========================================================
# ------------------- FEEDBACK NORMALIZATION --------------
# =========================================================

def _as_list_str(x: Any) -> List[str]:
    """
    Always returns list[str].
    - None/missing -> []
    - string -> [string] (if non-empty)
    - list -> keep only non-empty strings
    - everything else -> []
    """
    if x is None:
        return []
    if isinstance(x, str):
        s = x.strip()
        return [s] if s else []
    if isinstance(x, list):
        out: List[str] = []
        for v in x:
            if isinstance(v, str):
                s = v.strip()
                if s:
                    out.append(s)
        return out
    return []


def _normalize_feedback(feedback: Any) -> Dict[str, List[str]]:
    """
    Ensures feedback sections are lists.
    If model doesn't return something usable -> empty lists.
    """
    if not isinstance(feedback, dict):
        feedback = {}

    return {
        "does_well": _as_list_str(feedback.get("does_well")),
        "does_not_do_well": _as_list_str(feedback.get("does_not_do_well")),
        "considerations": _as_list_str(feedback.get("considerations")),
    }


def _normalize_score_rationale(rationale: Any) -> Dict[str, str]:
    """
    Ensures score_rationale has all 5 required fields as strings.
    Missing/invalid => empty string.
    """
    if not isinstance(rationale, dict):
        rationale = {}

    required_keys = [
        "motivation_to_prescribe",
        "connection_to_story",
        "differentiation",
        "believability",
        "stopping_power",
    ]
    result = {}
    for key in required_keys:
        val = rationale.get(key, "")
        result[key] = str(val).strip() if val else ""
    return result


def _synthesize_average_rationale(
    asset_name: str,
    avg_scores: Dict[str, float],
    individual_rationales: List[Dict[str, str]],
) -> Dict[str, str]:
    """
    Uses LLM to synthesize individual persona rationales into a single
    combined rationale per metric for the aggregated result.
    Returns dict with 5 metric keys -> combined rationale string.
    Falls back to empty strings on error.
    """
    metrics = [
        "motivation_to_prescribe",
        "connection_to_story",
        "differentiation",
        "believability",
        "stopping_power",
    ]

    # Build per-metric input for the LLM
    metric_inputs = {}
    for m in metrics:
        persona_texts = []
        for i, r in enumerate(individual_rationales, 1):
            text = r.get(m, "").strip()
            if text:
                persona_texts.append(f"  Persona {i}: {text}")
        metric_inputs[m] = {
            "average_score": avg_scores.get(m, 0.0),
            "individual_rationales": persona_texts,
        }

    prompt = f"""You are synthesizing feedback from {len(individual_rationales)} healthcare professionals who evaluated a pharmaceutical marketing asset named "{asset_name}".

For each metric below, you are given the average score and the individual rationales from each persona. Write ONE concise combined rationale (2-3 sentences) that captures the consensus view. Do NOT just list each persona's opinion — synthesize the common themes, agreements, and key tensions into a unified summary.

"""
    for m in metrics:
        info = metric_inputs[m]
        prompt += f"**{m}** (average: {info['average_score']}):\n"
        if info["individual_rationales"]:
            prompt += "\n".join(info["individual_rationales"]) + "\n\n"
        else:
            prompt += "  No rationales provided.\n\n"

    prompt += """Return ONLY valid JSON in this format:
{
  "average_rationale": {
    "motivation_to_prescribe": "<combined 2-3 sentence rationale>",
    "connection_to_story": "<combined 2-3 sentence rationale>",
    "differentiation": "<combined 2-3 sentence rationale>",
    "believability": "<combined 2-3 sentence rationale>",
    "stopping_power": "<combined 2-3 sentence rationale>"
  }
}"""

    messages = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]

    try:
        logger.info(f"[synthetic] synthesizing average_rationale for asset={asset_name}")
        result = _chat_json_synthetic(messages, max_completion_tokens=1024)

        if "error" in result:
            logger.error(f"[synthetic] average_rationale synthesis failed: {result['error']}")
            return {m: "" for m in metrics}

        avg_rat = result.get("average_rationale", {})
        if not isinstance(avg_rat, dict):
            avg_rat = {}

        return {m: str(avg_rat.get(m, "")).strip() for m in metrics}

    except Exception as e:
        logger.error(f"[synthetic] average_rationale synthesis exception: {e}")
        return {m: "" for m in metrics}



# =========================================================
# ------------------- PROMPT VARS MAP ---------------------
# =========================================================

def _build_synthetic_vars_map(
    persona: Dict[str, Any],
    asset_name: str,
    stimulus_text: str,
    has_image: bool,
    image_descriptor: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Locked variables ONLY.
    Frontend can reference these keys in synthetic_prompt, e.g.:
      {persona_name}, {role}, {segment}, {asset_name}, {content_desc}, etc.
    """
    full_persona = persona.get("full_persona", {}) or {}
    segment = full_persona.get("persona_subtype") or full_persona.get("segment", "Standard")
    role = full_persona.get("specialty") or persona.get("condition", "Patient")

    stimulus_quoted = _quoted(stimulus_text or "")

    content_desc = f"Message: {stimulus_quoted}" if (stimulus_text or "").strip() else 'Message: ""'
    if has_image:
        if isinstance(image_descriptor, str) and image_descriptor.strip():
            content_desc += f"\n(See attached image: {image_descriptor.strip()})"
        else:
            content_desc += "\n(See attached image)"

    locked_map = {
        "persona_id": persona.get("id"),
        "persona_name": persona.get("name"),
        "persona_age": persona.get("age"),
        "persona_gender": persona.get("gender"),
        "persona_location": persona.get("location"),
        "role": role,
        "segment": segment,
        "asset_name": asset_name,
        "stimulus_text": stimulus_text or "",
        "stimulus_text_quoted": stimulus_quoted,
        "has_image": has_image,
        "content_desc": content_desc,
        "image_descriptor": (image_descriptor or ""),
        "core_bio_pretty": _pretty_json(full_persona.get("core", {})),
        "full_persona_pretty": _pretty_json(full_persona),
        "additional_context_pretty": _pretty_json(persona.get("additional_context", {})),
    }
    return locked_map


def create_synthetic_prompt_pair(
    persona: Dict[str, Any],
    asset_name: str,
    stimulus_text: str,
    has_image: bool,
    synthetic_prompt: str = "",
    image_descriptor: Optional[str] = None,
) -> Tuple[str, str]:
    """
    Returns:
      prompt_used_for_model: rendered with locked vars (default or override)
      prompt_echo_for_api:   raw override OR default template (unpopulated)
    """
    vars_map = _build_synthetic_vars_map(
        persona,
        asset_name,
        stimulus_text,
        has_image,
        image_descriptor=image_descriptor,
    )
    override_used = not _is_blank(synthetic_prompt)

    logger.info(
        f"[synthetic] create_synthetic_prompt_pair persona_id={vars_map.get('persona_id')} "
        f"asset_name={asset_name} has_image={has_image} override_used={override_used} "
        f"image_descriptor={image_descriptor}"
    )

    if override_used:
        prompt_used = _safe_format_map(synthetic_prompt, vars_map).strip()
        prompt_echo = synthetic_prompt.strip()
        logger.info(
            f"[synthetic] override prompt rendered for model. locked_keys={len(vars_map)} "
            f"prompt_used_len={len(prompt_used)} preview={_safe_prompt_preview(prompt_used)}"
        )
        return prompt_used, prompt_echo

    prompt_used = _safe_format_map(DEFAULT_SYNTHETIC_PROMPT_TEMPLATE, vars_map).strip()
    prompt_echo = DEFAULT_SYNTHETIC_PROMPT_TEMPLATE
    logger.info(
        f"[synthetic] default prompt rendered for model. prompt_used_len={len(prompt_used)} "
        f"preview={_safe_prompt_preview(prompt_used)}"
    )
    return prompt_used, prompt_echo


# =========================================================
# ------------------- IMAGE URL -> B64 --------------------
# =========================================================

def image_url_to_base64(url: str, timeout: int = 20) -> Dict[str, Optional[str]]:
    logger.info(f"[synthetic] image_url_to_base64 start url_present={bool(url)} timeout={timeout}")

    r = requests.get(url, timeout=timeout)
    r.raise_for_status()

    content_type = (r.headers.get("Content-Type") or "").split(";")[0].strip().lower()

    if content_type in ("image/png", "image/jpeg", "image/jpg", "image/webp"):
        mime = "image/jpeg" if content_type == "image/jpg" else content_type
    else:
        mime = "image/png"

    b64 = base64.b64encode(r.content).decode("utf-8")

    logger.info(
        f"[synthetic] image_url_to_base64 success content_type={content_type} "
        f"mime={mime} bytes={len(r.content)} b64_len={len(b64)}"
    )
    return {"base64": b64, "mime": mime}


# =========================================================
# ------------------- SINGLE ANALYSIS (URL) ---------------
# =========================================================

def analyze_single_asset_persona_via_url(
    persona_dict: Dict[str, Any],
    asset: Dict[str, Any],
    synthetic_prompt: str = ""
) -> Dict[str, Any]:
    """Analyze one asset for one persona (image fetched by URL)."""

    asset_name = asset.get("name", "Unnamed Asset")
    text_content = asset.get("text", "")
    image_descriptor = asset.get("image_descriptor")

    logger.info(
        f"[synthetic] analyze_single_asset_persona_via_url start persona_id={persona_dict.get('id')} "
        f"asset_id={asset.get('id')} override_provided={not _is_blank(synthetic_prompt)} "
        f"image_descriptor={image_descriptor}"
    )

    image_data = None
    mime = "image/png"

    asset_url = asset.get("data")
    if asset_url:
        try:
            logger.info(f"[synthetic] fetching image url asset_id={asset.get('id')}")
            out = image_url_to_base64(asset_url)
            image_data = out["base64"]
            mime = out["mime"] or "image/png"
            logger.info(
                f"[synthetic] image fetched+encoded asset_id={asset.get('id')} "
                f"mime={mime} b64_len={len(image_data)}"
            )
        except Exception as e:
            logger.error(f"[synthetic] image fetch failed asset_id={asset.get('id')} err={e}")

            prompt_used, prompt_echo = create_synthetic_prompt_pair(
                persona_dict,
                asset_name,
                text_content,
                has_image=False,
                synthetic_prompt=synthetic_prompt,
                image_descriptor=image_descriptor,
            )

            return {
                "persona_id": persona_dict["id"],
                "persona_name": persona_dict["name"],
                "asset_id": asset.get("id"),
                "image_id": asset.get("id"),
                "image_name": asset.get("name"),
                "thumbnail_url": asset.get("thumbnail_url"),
                "thumbnail_url_str": asset.get("thumbnail_url_str"),
                "image_url": asset.get("data"),
                "asset_url": asset.get("data"),
                "image_descriptor": asset.get("image_descriptor"),
                "synthetic_prompt": prompt_echo,
                "scores": _normalize_scores_required(None),
                "score_rationale": _normalize_score_rationale(None),
                "overall_preference_score": 0,
                "feedback": _normalize_feedback(None),
                "error": f"Failed to fetch/encode image url: {str(e)}",
            }

    prompt_used, prompt_echo = create_synthetic_prompt_pair(
        persona_dict,
        asset_name,
        text_content,
        has_image=bool(image_data),
        synthetic_prompt=synthetic_prompt,
        image_descriptor=image_descriptor,
    )

    logger.info(
        f"[synthetic] prompt selected via_url persona_id={persona_dict.get('id')} asset_id={asset.get('id')} "
        f"echo_is_default={_is_blank(synthetic_prompt)} prompt_used_len={len(prompt_used)} "
        f"prompt_echo_len={len(prompt_echo)}"
    )

    messages = [{"role": "user", "content": [{"type": "text", "text": prompt_used}]}]

    if image_data:
        messages[0]["content"].append({
            "type": "image_url",
            "image_url": {"url": f"data:{mime};base64,{image_data}"},
        })

    logger.info(
        f"[synthetic] OpenAI analyze start via_url persona_id={persona_dict.get('id')} "
        f"asset_id={asset.get('id')}"
    )
    result = _chat_json_synthetic(messages)
    logger.info(
        f"[synthetic] OpenAI analyze end via_url persona_id={persona_dict.get('id')} "
        f"asset_id={asset.get('id')}"
    )

    if "error" in result:
        logger.error(
            f"[synthetic] analysis failed via_url persona_id={persona_dict.get('id')} "
            f"asset_id={asset.get('id')} err={result.get('error')}"
        )
        return {
            "persona_id": persona_dict["id"],
            "persona_name": persona_dict["name"],
            "asset_id": asset.get("id"),
            "image_id": asset.get("id"),
            "image_name": asset.get("name"),
            "thumbnail_url": asset.get("thumbnail_url"),
            "thumbnail_url_str": asset.get("thumbnail_url_str"),
            "image_url": asset.get("data"),
            "asset_url": asset.get("data"),
            "image_descriptor": asset.get("image_descriptor"),
            "synthetic_prompt": prompt_echo,
            "scores": _normalize_scores_required(None),
            "score_rationale": _normalize_score_rationale(None),
            "overall_preference_score": 0,
            "feedback": _normalize_feedback(None),
            "error": result["error"],
        }

    scores = _normalize_scores_required(result.get("scores", None))
    score_rationale = _normalize_score_rationale(result.get("score_rationale", None))
    feedback = _normalize_feedback(result.get("feedback", None))

    vals = [v for v in scores.values() if isinstance(v, (int, float)) and 1.0 <= float(v) <= 7.0]
    if vals:
        avg_score = sum(vals) / float(len(vals))
        preference_pct = int(((avg_score - 1.0) / 6.0) * 100) if avg_score >= 1.0 else 0
        preference_pct = max(0, min(100, preference_pct))
    else:
        preference_pct = 0

    return {
        "persona_id": persona_dict["id"],
        "persona_name": persona_dict["name"],
        "asset_id": asset.get("id"),
        "image_id": asset.get("id"),
        "image_name": asset.get("name"),
        "thumbnail_url": asset.get("thumbnail_url"),
        "thumbnail_url_str": asset.get("thumbnail_url_str"),
        "image_url": asset.get("data"),
        "asset_url": asset.get("data"),
        "image_descriptor": asset.get("image_descriptor"),
        "synthetic_prompt": prompt_echo,
        "scores": scores,
        "score_rationale": score_rationale,
        "overall_preference_score": preference_pct,
        "feedback": feedback,
    }


def generate_emotion_data(personas: List[Dict[str, Any]], assets: List[Dict[str, Any]], emotion_prompt : str) -> List[Dict[str, Any]]:
    """
    Generates an emotional response matrix for all personas and assets.
    """
    persona_text = ""
    for i, p in enumerate(personas, 1):
        print(f"persona data --> {p}")
        name = p.get('name', f'Persona {i}')
        sub_type = p.get('persona_subtype', f'Persona {i}')
        role = p.get('condition') or p.get('full_persona', {}).get('specialty') or 'HCP'
        bio = p.get('additional_context', {}).get('background', '')
        persona_text += f"- Name: {name}, Persona SubType: {sub_type}, Role: {role}, Bio: {bio}\n"
    
    asset_text = ""
    for i, a in enumerate(assets, 1):
        name = a.get('name', f'Asset {i}')
        desc = a.get('image_descriptor', '')
        text = a.get('text', '') or a.get('text_content', '')
        asset_text += f"- Concept Name: {name}, Description: {desc}, Text: {text}\n"

    if not emotion_prompt or not emotion_prompt.strip():
        emotion_prompt = DEFAULT_EMOTION_PROMPT

    prompt = _safe_format_map(emotion_prompt, {
        "asset_text": asset_text,
        "persona_text": persona_text
    })
    print(f"prompt with text --> {prompt}")
    
    messages = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
    
    try:
        logger.info("[synthetic] generating emotion data matrix")
        result = _chat_json_synthetic(messages)
        if "error" in result:
            logger.error(f"[synthetic] emotion data generation failed: {result['error']}")
            return []
        return result.get("emotion_data", [])
    except Exception as e:
        logger.error(f"[synthetic] emotion data generation exception: {e}")
        return []


# =========================================================
# ------------------- RUNNER V2 (URL) ---------------------
# =========================================================

def run_synthetic_testingV2(
    campaign_id: str,
    task_id: str,
    persona_ids: List[int],
    assets: List[Dict[str, Any]],
    synthetic_prompt: str = "",
    emotion_prompt: str = "",
    db=None
) -> Dict[str, Any]:
    """
    assets: [{id, name, data(url|None), text}]
    adds assets[i]["image_descriptor"] using one batched LLM call before analysis
    """

    logger.info(
        f"[synthetic] run_synthetic_testingV2 start campaign_id={campaign_id} task_id={task_id} "
        f"persona_ids={persona_ids} assets_count={len(assets)} "
        f"override_provided={not _is_blank(synthetic_prompt)}"
        f"emotion_prompt_provided={not _is_blank(emotion_prompt)}"
    )

    logger.info(assets)
    logger.info("✅✅✅✅✅✅✅✅✅")

    try:
        personas = []
        for pid in persona_ids:
            p = crud.get_persona(db, pid)
            if p:
                personas.append({
                    "id": p.id,
                    "name": p.name,
                    "age": p.age,
                    "persona_subtype": p.persona_subtype,
                    "gender": p.gender,
                    "location": p.location,
                    "condition": p.condition,
                    "full_persona": json.loads(p.full_persona_json)
                    if getattr(p, "full_persona_json", None)
                    else {},
                    "additional_context": p.additional_context or {},
                })
                logger.info(f"[synthetic] loaded persona pid={pid}")
            else:
                logger.warning(f"[synthetic] persona not found pid={pid}")

        if not personas:
            logger.error("[synthetic] No valid personas found (V2)")
            return {"error": "No valid personas found"}

        # Pre-label asset images once before per-persona analysis
        try:
            assets = generate_asset_image_descriptors_via_url(assets)
            logger.info("[synthetic] asset descriptors generated successfully")
        except Exception as e:
            logger.warning(f"[synthetic] asset descriptor generation failed, continuing. err={e}")
            for i, asset in enumerate(assets):
                if isinstance(asset, dict) and "image_descriptor" not in asset:
                    asset["image_descriptor"] = f"Asset {i+1}"

        results: List[Dict[str, Any]] = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            futures = []
            for persona in personas:
                for asset in assets:
                    futures.append(
                        executor.submit(
                            analyze_single_asset_persona_via_url,
                            persona,
                            asset,
                            synthetic_prompt,
                        )
                    )

            logger.info(f"[synthetic] submitted tasks (V2) count={len(futures)}")

            for future in concurrent.futures.as_completed(futures):
                try:
                    res = future.result()
                    results.append(res)
                except Exception as e:
                    import traceback
                    logger.error(f"[synthetic] Analysis task failed (V2): {e}\n{traceback.format_exc()}")

        logger.info(f"[synthetic] all tasks done (V2) results_count={len(results)}")

        aggregated_results: Dict[str, Any] = {}

        for asset in assets:
            a_id = asset["id"]
            asset_responses = [r for r in results if r.get("asset_id") == a_id and "error" not in r]
            if not asset_responses:
                logger.warning(f"[synthetic] no successful responses (V2) for asset_id={a_id}")
                continue

            sums = {
                "motivation_to_prescribe": 0.0,
                "connection_to_story": 0.0,
                "differentiation": 0.0,
                "believability": 0.0,
                "stopping_power": 0.0,
            }
            counts = {
                "motivation_to_prescribe": 0,
                "connection_to_story": 0,
                "differentiation": 0,
                "believability": 0,
                "stopping_power": 0,
            }

            pref_sum = 0.0
            pref_count = 0
            individual_rationales: List[Dict[str, str]] = []

            for r in asset_responses:
                s = r.get("scores", {}) or {}
                if isinstance(s, dict):
                    for k in sums.keys():
                        v = s.get(k, 0)
                        if isinstance(v, (int, float)) and 1.0 <= float(v) <= 7.0:
                            sums[k] += float(v)
                            counts[k] += 1

                op = r.get("overall_preference_score", None)
                if isinstance(op, (int, float)):
                    pref_sum += float(op)
                    pref_count += 1

                # Collect individual rationales for synthesis
                sr = r.get("score_rationale", {})
                if isinstance(sr, dict) and any(sr.values()):
                    individual_rationales.append(sr)

            avg_scores = {}
            for k in sums.keys():
                c = counts.get(k, 0)
                avg_scores[k] = round(sums[k] / c, 1) if c > 0 else 0.0

            # Synthesize combined rationale via LLM
            print(f"generate combine individual rationales --> {individual_rationales}")
            avg_rationale = _synthesize_average_rationale(
                asset_name=asset.get("name", a_id),
                avg_scores=avg_scores,
                individual_rationales=individual_rationales,
            )

            aggregated_results[a_id] = {
                "asset_name": asset.get("name"),
                "image_descriptor": asset.get("image_descriptor"),
                "average_scores": avg_scores,
                "average_rationale": avg_rationale,
                "average_preference": round(pref_sum / pref_count, 1) if pref_count > 0 else 0.0,
                "respondent_count": len(asset_responses),
            }
            logger.info(
                f"[synthetic] aggregated (V2) asset_id={a_id} respondent_count={len(asset_responses)}"
            )

        top_prompt_echo = (
            synthetic_prompt.strip()
            if not _is_blank(synthetic_prompt)
            else DEFAULT_SYNTHETIC_PROMPT_TEMPLATE
        )

        emotion_prompt_echo = (
            emotion_prompt.strip()
            if not _is_blank(emotion_prompt)
            else DEFAULT_EMOTION_PROMPT
        )

        logger.info("[synthetic] run_synthetic_testingV2 end")
        print(f"waiting for emotion data")
        try:
            emotion_data = generate_emotion_data(personas, assets, emotion_prompt_echo)
            print(f"emotion data generated successfully")
        except Exception as e:
            logger.error(f"Failed to generate emotion data: {e}")
            emotion_data = []
        return {
            "results": results,
            "aggregated": aggregated_results,
            "emotion_data": emotion_data,
            "metadata": {
                "campaign_id": campaign_id,
                "task_id": task_id,
                "personas_count": len(personas),
                "assets_count": len(assets),
                "timestamp": datetime.now().isoformat(),
            },
            "synthetic_prompt": top_prompt_echo,
            "emotion_prompt": emotion_prompt_echo,
        }

    except Exception as e:
        import traceback
        logger.error(f"[synthetic] Global synthetic testing error (V2): {e}\n{traceback.format_exc()}")
        raise