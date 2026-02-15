import json
import logging
import time
import asyncio
import os
from typing import List, Dict, Any, Optional, Tuple
from openai import OpenAI

from . import schemas, models, vector_search, persona_engine, crud
from .utils import get_openai_client, get_async_openai_client, MODEL_NAME

logger = logging.getLogger(__name__)

# Direct file debug logging (bypasses logging framework)
import datetime
DEBUG_LOG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "debug_discovery.log")
def debug_log(msg):
    with open(DEBUG_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.datetime.now().isoformat()}] {msg}\n")
        f.flush()

# === Prompts ===

DISCOVERY_PROMPT = """
You are an expert market researcher. Analyze the following summaries of research documents to identify distinct customer segments or personas.

**Context:**
We have a collection of documents (transcripts, segmentation studies, strategy decks) about a disease area or product.
We need to "discover" the distinct personas described in these documents so we can simulate them later.

**Document Summaries / Excerpts:**
{context_text}

**Task:**
Identify 3-6 distinct personas/segments found in this research.
For each segment, provide:
1. A descriptive name (e.g., "The Overwhelmed Caregiver", "The Skeptical Specialist").
2. A brief description (Who are they?).
3. Key differentiators (What makes them unique?).
4. Evidence (Which documents or themes point to them?).

**Output Format:**
Return a JSON object with a "segments" key containing an array of objects.
{{
  "segments": [
    {{
      "name": "Segment Name",
      "description": "Brief description...",
      "differentiators": ["Trait 1", "Trait 2"],
      "evidence": "Found in doc X, Y..."
    }}
  ]
}}
"""

# Dictionary mapping extraction passes to specific schema fields and queries
EXTRACTION_PASSES = {
    "demographics": {
        "query_template": "Demographics, lifestyle, daily routine, and life context of {segment_name}. {segment_description}",
        "focus": "FACTUAL",
        "schema_fields": [
            "age", "gender", "condition", "location", 
            "occupation", "financial_status", "family_context",
            "education", "ethnicity"
        ],
        "prompt_instruction": "Extract hard demographic data. Look for 'Age', 'Gender', 'Location', 'Routine'. If not found, estimating based on context is allowed but mark as estimated."
    },
    "psychographics": {
        "query_template": "Motivations, beliefs, fears, values, and psychological drivers of {segment_name}. {segment_description}",
        "focus": "EMOTIONAL",
        "schema_fields": [
            "motivations", "beliefs", "pain_points", "goals", "values", 
            "mbt_personality", "core_insight", "concerns"
        ],
        "prompt_instruction": "Extract deep psychological drivers. Populate 'motivations', 'beliefs', 'pain_points', and the 'core_insight' (the single most important truth about them)."
    },
    "behavioral": {
        "query_template": "Healthcare journey, relationship with HCPs, channel preferences, and decision making for {segment_name}. {segment_description}",
        "focus": "BEHAVIORAL",
        "schema_fields": [
            "hcp_relationship", "communication_preferences", "digital_behavior", 
            "adherence_to_protocols", "decision_drivers", "channel_use", 
            "decision_style", "decision_influencers"
        ],
        "prompt_instruction": "Extract behavioral patterns. specifically 'channel_use' (where do they get info?), 'decision_style' (paternalistic vs shared?), and 'decision_influencers'."
    }
}

PASS_PROMPT_TEMPLATE = """
You are extracting {focus} insights about a specific patient/HCP segment from research documents.

**Target Segment:** "{segment_name}"
**Segment Description:** {segment_description}

**Research Context (Retrieved from Documents):**
{rag_context}

**Your Task:**
{prompt_instruction}

**Fields to populate:**
{schema_fields}

**Rules:**
- ONLY extract information relevant to "{segment_name}". Ignore data about other segments.
- If a field cannot be found in the context, set it to null.
- Be specific — use exact quotes or data points from the context when possible.

**Output:** Return a JSON object with the requested fields.
"""

MERGE_PROMPT = """
You are aggregating research insights into a single, coherent persona profile for "{segment_name}".

**Inputs from Research Passes:**
1. **Demographics & Life Context**: {demo_json}
2. **Psychographics & Motivations**: {psych_json}
3. **Behavioral & Decision Patterns**: {behav_json}

**Task:**
Merge these inputs into a SINGLE, coherent persona profile JSON.
Resolve any contradictions (e.g., if Demographics says "Age 70", Behavioral shouldn't say "Uses TikTok heavily" unless substantiated).

**Required Output Structure:**
{{
  "name": "<persona name>",
  "age": <int>,
  "gender": "<string>",
  "condition": "<primary condition>",
  "location": "<location>",
  "persona_type": "Patient" or "HCP",
  "tagline": "<one-line essence of this persona>",
  "core_insight": "<the single most important truth about them>",
  "specialty": "<if HCP, their specialty>",
  "practice_setup": "<if HCP, their practice context>",
  "decision_style": "<how they make decisions>",
  "decision_influencers": "<who influences their decisions>",
  "adherence_to_protocols": "<their adherence pattern>",
  "channel_use": "<preferred information channels>",
  "core": {{
    "snapshot": {{
      "life_context": {{ "value": "<daily life description>" }},
      "occupation": {{ "value": "<job or role>" }}
    }},
    "mbt": {{
      "motivation": {{
        "primary_motivation": {{ "value": "<m1>" }},
        "top_outcomes": {{ "value": ["<m1>", "<m2>", "<m3>"] }}
      }},
      "beliefs": {{
        "core_belief_statements": {{ "value": ["<b1>", "<b2>", "<b3>"] }}
      }},
      "tension": {{
        "main_worry": {{ "value": "<t1>" }},
        "sensitivity_points": {{ "value": ["<t1>", "<t2>", "<t3>"] }}
      }}
    }},
    "decision_drivers": {{
      "ranked_drivers": [
        {{"rank": 1, "driver": "<d1>", "detail": "<details>"}},
        {{"rank": 2, "driver": "<d2>", "detail": "<details>"}}
      ],
      "tie_breakers": {{ "value": ["<tb1>", "<tb2>"] }}
    }},
    "messaging": {{
      "what_lands": {{ "value": ["<proof1>", "<proof2>"], "evidence": ["<quote1>", "<quote2>"] }},
      "what_fails": {{ "value": ["<fail1>"], "evidence": ["<quote3>"] }},
      "preferred_voice": {{ "value": "<tone description>" }}
    }},
    "barriers_objections": {{
        "objections": {{ "value": ["<obj1>"], "evidence": ["<quote4>"] }},
        "practical_barriers": {{ "value": ["<pb1>"] }},
        "perceptual_barriers": {{ "value": ["<psb1>"] }}
    }}
  }},
  "additional_context": {{
    "nuances": ["<unique detail 1>", "<unique detail 2>"],
    "quote_style": "<how they talk>",
    "raw_evidence": ["<key quote from research>"]
  }},
  "sources": [
      {{ "filename": "doc1.pdf", "relevance": "High" }}
  ]
}}
"""

# === Engine Functions ===

def discover_segments_from_documents(
    documents: List[models.BrandDocument], 
    limit: int = 5
) -> List[Dict[str, Any]]:
    """
    Scans the provided brand documents (summaries) to discover potential personas/segments.
    """
    client = get_openai_client()
    if not client:
        return [{"name": "Error", "description": "OpenAI API not available"}]

    # 1. Aggregate context from document summaries
    context_parts = []
    for doc in documents:
        info = f"Document: {doc.filename}\n"
        if doc.summary:
            info += f"Summary: {doc.summary}\n"
        if doc.extracted_insights:
            # Include key insights if available
            insights = doc.extracted_insights
            if isinstance(insights, dict):
                for key, val in list(insights.items())[:5]:
                    info += f"  - {key}: {val}\n"
        context_parts.append(info)
        
    # Limit context size to avoid token overflow
    context_text = "\n---\n".join(context_parts)[:20000] 
    
    if not context_text.strip():
        logger.warning("No document summaries available for discovery")
        return [{"name": "No Data", "description": "Documents have no summaries. Please process documents first."}]
    
    # 2. Call LLM for segment discovery
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "You are a helpful market research assistant."},
                {"role": "user", "content": DISCOVERY_PROMPT.format(context_text=context_text)}
            ],
            response_format={"type": "json_object"},
            temperature=0.7  # Higher temp for creative discovery
        )
        
        result_json = json.loads(response.choices[0].message.content)
        segments = result_json.get("segments", [])
        return segments[:limit]
        
    except Exception as e:
        logger.error(f"Discovery failed: {e}")
        return []

def _get_filename_map(documents: List[models.BrandDocument]) -> Dict[str, str]:
    """Create a mapping of known vector_store_ids (if any) or prepare for remote lookup."""
    return {doc.filename: doc.filename for doc in documents}

def _resolve_citation_filenames(
    citations: List[Dict[str, str]], 
    documents: List[models.BrandDocument]
) -> List[Dict[str, str]]:
    """
    Enhance citations with filenames. 
    """
    if not citations:
        return []

    client = get_openai_client()
    resolved = []
    
    # Simple cache for this request scope
    file_id_cache = {}
    
    for cit in citations:
        fid = cit.get("file_id")
        if not fid:
            continue
            
        filename = "Unknown Document"
        
        if fid in file_id_cache:
            filename = file_id_cache[fid]
        else:
            try:
                if client:
                    f = client.files.retrieve(fid)
                    filename = f.filename
                    file_id_cache[fid] = filename
            except Exception:
                filename = f"File {fid[:8]}..."
        
        resolved.append({
            "file_id": fid,
            "filename": filename,
            "quote": cit.get("quote", "")
        })
        
    return resolved


def _retrieve_rag_context(
    brand_id: int,
    query: str,
    documents: List[models.BrandDocument],
    segment_name: str
) -> Tuple[str, List[Dict[str, str]]]:
    """
    Retrieves relevant context from OpenAI Vector Stores for a given query.
    Falls back to document summaries if no vector stores are available.
    """
    # Try vector search first
    try:
        t0 = time.time()
        logger.info(f"[DEBUG] _retrieve_rag_context: starting vector search for '{segment_name}' pass, query='{query[:60]}...'")
        results = vector_search.search_brand_chunks(
            brand_id=brand_id,
            documents=documents,
            query_text=query,
            top_k=5,
            target_segment=segment_name
        )
        elapsed = time.time() - t0
        logger.info(f"[DEBUG] _retrieve_rag_context: vector search returned in {elapsed:.1f}s, results={'yes' if results else 'none'}")
        
        if results:
            context_parts = []
            all_citations = []
            
            for r in results:
                context_parts.append(f"[Source: {r.get('source_document', 'unknown')}]\n{r['text']}")
                if 'citations' in r:
                    all_citations.extend(r['citations'])
            
            # Pack the raw list of citations (file_ids) into the return string as a hidden JSON or header? 
            # Ideally we return a strict struct, but this function returns str.
            # We'll just return the text context for LLM consumption. 
            # The citations for UI need to be handled separately or passed through side channels if we want them out of this function.
            # Only stream_persona_generation needs them for UI.
            # We will refactor _retrieve_rag_context to return a Tuple later or just let the caller handle it.
            # For now, let's keep this signature and rely on the fact that we call vector_search inside stream_persona_generation too? 
            # NO, stream_persona_generation delegates to this.
            
            # HACK: We can't easily return the citations from here without changing signature.
            # BUT, we can make this function return (str, list).
            return "\n\n---\n\n".join(context_parts), all_citations
    except Exception as e:
        logger.warning(f"Vector search failed, falling back to summaries: {e}")
    
    # Fallback: use document summaries
    logger.info(f"[DEBUG] _retrieve_rag_context: falling back to document summaries")
    fallback_parts = []
    for doc in documents:
        if doc.summary:
            fallback_parts.append(f"[{doc.filename}] {doc.summary}")
    
    if fallback_parts:
        return "\n\n".join(fallback_parts), []
    
    return f"No detailed context available for {segment_name}. Generate a reasonable profile based on the segment description.", []


def extract_persona_from_segment(
    segment_name: str,
    segment_description: str,
    brand_id: int,
    db_session: Any 
) -> Dict[str, Any]:
    """
    Generates a full persona profile for a chosen segment using Multi-Pass RAG.
    
    Steps:
    1. For each extraction pass (demographics, psychographics, behavioral),
       query the vector store with a targeted query.
    2. Feed the retrieved context + schema fields to the LLM.
    3. Merge all pass results into a single coherent profile.
    """
    client = get_openai_client()
    if not client:
        return {}

    # Fetch brand documents for RAG
    documents = crud.get_brand_documents(db_session, brand_id)
    
    pass_results = {}
    
    # 1. Execute 3 Extraction Passes
    for pass_name, config in EXTRACTION_PASSES.items():
        logger.info(f"🔍 Running {pass_name} pass for '{segment_name}'...")
        
        # A. Construct targeted RAG query
        query = config["query_template"].format(
            segment_name=segment_name, 
            segment_description=segment_description
        )
        
        # B. Retrieve relevant context from vector stores
        rag_context, _ = _retrieve_rag_context(
            brand_id=brand_id,
            query=query,
            documents=documents,
            segment_name=segment_name
        )
        
        # C. LLM Extraction with structured prompt
        pass_prompt = PASS_PROMPT_TEMPLATE.format(
            focus=config["focus"],
            segment_name=segment_name,
            segment_description=segment_description,
            rag_context=rag_context,
            prompt_instruction=config["prompt_instruction"],
            schema_fields=", ".join(config["schema_fields"])
        )
        
        try:
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": "You are an expert persona researcher. Extract structured insights from research documents."},
                    {"role": "user", "content": pass_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.3  # Low temp for factual extraction
            )
            pass_results[pass_name] = response.choices[0].message.content
            logger.info(f"✅ {pass_name} pass complete")
        except Exception as e:
            logger.error(f"Pass {pass_name} failed: {e}")
            pass_results[pass_name] = "{}"

    # 2. Merge all pass results into final profile
    logger.info(f"🔄 Merging passes for '{segment_name}'...")
    try:
        merge_response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "You are a persona synthesis expert. Merge research findings into a single coherent profile."},
                {"role": "user", "content": MERGE_PROMPT.format(
                    segment_name=segment_name,
                    demo_json=pass_results.get("demographics", "{}"),
                    psych_json=pass_results.get("psychographics", "{}"),
                    behav_json=pass_results.get("behavioral", "{}")
                )}
            ],
            response_format={"type": "json_object"},
            temperature=0.2  # Very low temp for consistent output
        )
        final_profile = json.loads(merge_response.choices[0].message.content)
        
        # Ensure flat legacy keys exist for UI fallback compatibility
        if "core" in final_profile and "mbt" in final_profile["core"]:
            mbt = final_profile["core"]["mbt"]
            final_profile["motivations"] = mbt.get("motivation", {}).get("top_outcomes", {}).get("value", [])
            final_profile["beliefs"] = mbt.get("beliefs", {}).get("core_belief_statements", {}).get("value", [])
            final_profile["pain_points"] = mbt.get("tension", {}).get("sensitivity_points", {}).get("value", [])
            
        logger.info(f"✅ Persona profile merged for '{segment_name}'")
        return final_profile
        
    except Exception as e:
        logger.error(f"Merge failed: {e}")
        return {}


async def stream_persona_generation(
    segment_name: str,
    segment_description: str,
    brand_id: int,
    db_session: Any
):
    """
    Async generator that streams the persona generation process.
    Yields JSON strings for SSE events.
    """
    yield json.dumps({"type": "progress", "step": "initializing", "percentage": 10})
    debug_log(f"=== stream_persona_generation START: segment='{segment_name}', brand_id={brand_id} ===")
    
    async_client = get_async_openai_client()
    if not async_client:
        debug_log("ERROR: async_client is None")
        yield json.dumps({"type": "error", "message": "OpenAI API not available"})
        return

    # Fetch brand documents for RAG (Sync call, but fast enough)
    documents = crud.get_brand_documents(db_session, brand_id)
    docs_with_vs = [d for d in documents if d.vector_store_id]
    yield json.dumps({"type": "log", "message": f"📁 Attached {len(documents)} brand documents. {len(docs_with_vs)} have active vector index.", "step": "initializing"})
    if len(docs_with_vs) == 0:
        yield json.dumps({"type": "log", "message": "⚠️ Warning: No documents have vector indices. Falling back to semantic summaries.", "step": "initializing"})
    yield json.dumps({"type": "log", "message": f"⚙️ Search Parameters: top_k=5, model='gpt-4o', strategy='file_search'", "step": "initializing"})

    pass_results = {}
    total_passes = len(EXTRACTION_PASSES)
    current_pass_idx = 0

    # 1. Execute 3 Extraction Passes
    for pass_name, config in EXTRACTION_PASSES.items():
        current_pass_idx += 1
        progress = 10 + (current_pass_idx / total_passes) * 60  # Scale up to 70%
        
        yield json.dumps({
            "type": "progress", 
            "step": pass_name, 
            "percentage": progress
        })
        
        logger.info(f"🔍 Running {pass_name} pass for '{segment_name}'...")
        debug_log(f"--- Pass {current_pass_idx}/{total_passes}: {pass_name} ---")
        yield json.dumps({"type": "log", "message": f"Running {pass_name} analysis...", "step": pass_name})

        # A. Construct targeted RAG query
        query = config["query_template"].replace("{segment_name}", segment_name or "").replace("{segment_description}", segment_description or "")
        logger.info(f"🔍 Research Query: \"{query}\"")
        yield json.dumps({"type": "log", "message": f"🔍 Research Query: \"{query}\"", "step": pass_name})
        yield json.dumps({"type": "log", "message": f"🎯 Primary Focus: {config['focus']} extraction patterns.", "step": pass_name})
        
        # B. Retrieve relevant context (run sync call in thread pool to avoid blocking event loop)
        try:
            yield json.dumps({"type": "log", "message": f"📡 Searching brand documents for {pass_name} context...", "step": pass_name})
            result = await asyncio.wait_for(
                asyncio.to_thread(
                    _retrieve_rag_context,
                    brand_id=brand_id,
                    query=query,
                    documents=documents,
                    segment_name=segment_name
                ),
                timeout=90  # 90 second timeout per RAG retrieval
            )
            rag_context = result[0]
            citations = result[1]
        except asyncio.TimeoutError:
            debug_log(f"TIMEOUT: RAG retrieval timed out for {pass_name}")
            logger.warning(f"RAG context retrieval timed out for {pass_name}, using document summaries")
            yield json.dumps({"type": "log", "message": f"Context retrieval slow, using summaries for {pass_name}.", "step": pass_name})
            # Fallback to document summaries
            fallback_parts = [f"[{doc.filename}] {doc.summary}" for doc in documents if doc.summary]
            rag_context = "\n\n".join(fallback_parts) if fallback_parts else f"No context available for {segment_name}."
            citations = []
        except Exception as e:
            debug_log(f"ERROR: RAG retrieval failed for {pass_name}: {type(e).__name__}: {e}")
            logger.warning(f"RAG context retrieval failed for {pass_name}: {e}")
            yield json.dumps({"type": "log", "message": f"Context retrieval failed, using summaries for {pass_name}.", "step": pass_name})
            fallback_parts = [f"[{doc.filename}] {doc.summary}" for doc in documents if doc.summary]
            rag_context = "\n\n".join(fallback_parts) if fallback_parts else f"No context available for {segment_name}."
            citations = []

        debug_log(f"RAG context retrieved for {pass_name}, length={len(rag_context)} chars, citations={len(citations)}")
        yield json.dumps({"type": "log", "message": f"📘 Context Dense: Analyzed ~{max(1, len(rag_context)//4)} tokens of research material.", "step": pass_name})
        
        # Resolve citation filenames (Sync call wrapped in thread if we want to be pure, but for now we do it inline or simple)
        # For better UX, let's resolve them in a thread
        resolved_citations = await asyncio.to_thread(_resolve_citation_filenames, citations, documents)
        
        if resolved_citations:
             yield json.dumps({
                "type": "citations",
                "step": pass_name,
                "data": resolved_citations
             })
             yield json.dumps({"type": "log", "message": f"📑 Found {len(resolved_citations)} evidence snippets in docs.", "step": pass_name})
        else:
             yield json.dumps({"type": "log", "message": f"⚠️ No direct citations found, using general context for {pass_name}.", "step": pass_name})
             
        yield json.dumps({"type": "log", "message": f"🤖 Synthesizing {pass_name} analysis...", "step": pass_name})

        # C. LLM Extraction (Async)
        pass_prompt = PASS_PROMPT_TEMPLATE.replace("{focus}", config["focus"])\
            .replace("{segment_name}", segment_name or "")\
            .replace("{segment_description}", segment_description or "")\
            .replace("{rag_context}", rag_context or "No context found.")\
            .replace("{prompt_instruction}", config["prompt_instruction"])\
            .replace("{schema_fields}", ", ".join(config["schema_fields"]))
        
        try:
            debug_log(f"LLM call START for {pass_name}")
            response = await async_client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": "You are an expert persona researcher. Extract structured insights from research documents."},
                    {"role": "user", "content": pass_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.3
            )
            debug_log(f"LLM call DONE for {pass_name}")
            pass_content = response.choices[0].message.content
            pass_results[pass_name] = pass_content
            
            # Yield partial result
            try:
                pass_data = json.loads(pass_content)
                yield json.dumps({
                    "type": "partial_result", 
                    "data": {pass_name: pass_data},
                    "step": pass_name
                })
            except:
                pass

            logger.info(f"✅ {pass_name} pass complete")
            pass_title = pass_name.capitalize()
            yield json.dumps({"type": "log", "message": f"{pass_title} analysis complete.", "step": pass_name})

        except Exception as e:
            debug_log(f"ERROR: Pass {pass_name} failed: {type(e).__name__}: {e}")
            logger.error(f"Pass {pass_name} failed: {e}", exc_info=True)
            yield json.dumps({"type": "log", "message": f"Error in {pass_name}: {str(e)}", "step": pass_name})
            pass_results[pass_name] = "{}"

    # 2. Merge all pass results (Async)
    debug_log("=== MERGE STEP START ===")
    yield json.dumps({"type": "progress", "step": "synthesizing", "percentage": 80})
    yield json.dumps({"type": "log", "message": "🔄 Merging research findings from all passes into a unified persona model...", "step": "synthesizing"})
    yield json.dumps({"type": "log", "message": "⚖️ Resolving cross-dimensional attributes and validating consistency...", "step": "synthesizing"})
    
    logger.info(f"🔄 Merging passes for '{segment_name}'...")
    
    try:
        debug_log("Merge LLM call START")
        
        merge_prompt = MERGE_PROMPT.replace("{segment_name}", segment_name or "")\
            .replace("{demo_json}", pass_results.get("demographics", "{}"))\
            .replace("{psych_json}", pass_results.get("psychographics", "{}"))\
            .replace("{behav_json}", pass_results.get("behavioral", "{}"))

        merge_response = await async_client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "You are a persona synthesis expert. Merge research findings into a single coherent profile."},
                {"role": "user", "content": merge_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.2
        )
        debug_log("Merge LLM call DONE")
        final_profile_json = json.loads(merge_response.choices[0].message.content)
        
        # Ensure flat legacy keys
        if "core" in final_profile_json and "mbt" in final_profile_json["core"]:
            mbt = final_profile_json["core"]["mbt"]
            final_profile_json["motivations"] = mbt.get("motivation", {}).get("top_outcomes", {}).get("value", [])
            final_profile_json["beliefs"] = mbt.get("beliefs", {}).get("core_belief_statements", {}).get("value", [])
            final_profile_json["pain_points"] = mbt.get("tension", {}).get("sensitivity_points", {}).get("value", [])
            
        logger.info(f"✅ Persona profile merged for '{segment_name}'")
        debug_log(f"=== STREAM COMPLETE: yielding final persona ===")
        yield json.dumps({"type": "progress", "step": "synthesizing", "percentage": 100})
        yield json.dumps({"type": "complete", "persona": final_profile_json})
        
    except Exception as e:
        debug_log(f"ERROR: Merge failed: {type(e).__name__}: {e}")
        logger.error(f"Merge failed: {e}")
        yield json.dumps({"type": "error", "message": f"Merge failed: {str(e)}"})
