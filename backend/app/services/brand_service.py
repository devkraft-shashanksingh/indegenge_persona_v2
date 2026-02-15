import logging
import json
from typing import List, Dict, Optional, Tuple
from .. import models, vector_search, persona_engine

logger = logging.getLogger(__name__)

def normalize_insight_type(raw_type: Optional[str]) -> str:
    if not raw_type:
        return "Motivation"
    normalized = raw_type.strip().lower()
    if "tension" in normalized or "pain" in normalized or "barrier" in normalized:
        return "Tension"
    if "belief" in normalized or "perception" in normalized or "attitude" in normalized:
        return "Belief"
    return "Motivation"


def insight_matches_segment(insight_segment: Optional[str], target_segment: Optional[str]) -> bool:
    if not target_segment:
        return True
    if not insight_segment or insight_segment.lower() == "general":
        return True
    return target_segment.lower() in insight_segment.lower()


def llm_merge_insights(insights: List[Dict[str, str]], limit: int) -> List[Dict[str, str]]:
    client = persona_engine.get_openai_client()
    if client is None:
        return insights[:limit]

    system_prompt = (
        "You are consolidating brand insights for the MBT framework. "
        "Merge overlapping items, retain citations, and output at most "
        f"{limit} concise insights as JSON array."
    )
    user_payload = json.dumps(insights)[:6000]

    try:
        response = client.chat.completions.create(
            model=persona_engine.MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_payload},
            ],
            response_format={"type": "json_array"},
            max_tokens=600,
        )
        content = response.choices[0].message.content or "[]"
        merged = json.loads(content)
        normalized = []
        for entry in merged:
            normalized.append(
                {
                    "type": normalize_insight_type(entry.get("type")),
                    "text": (entry.get("text") or "").strip(),
                    "segment": entry.get("segment", "General"),
                    "source_snippet": (entry.get("source_snippet") or "").strip(),
                    "source_document": entry.get("source_document"),
                }
            )
        return [item for item in normalized if item["text"]][:limit]
    except Exception as exc:
        logger.warning(f"Insight consolidation failed: {exc}")
        return insights[:limit]


def dedupe_and_limit(insights: List[Dict[str, str]], limit: int = 5) -> List[Dict[str, str]]:
    seen = set()
    unique = []
    for insight in insights:
        text = insight.get("text", "").strip()
        if not text:
            continue
        key = (insight.get("type", ""), text.lower())
        if key in seen:
            continue
        seen.add(key)
        unique.append(insight)
    if len(unique) > limit * 2:
        llm_result = llm_merge_insights(unique, limit)
        if llm_result:
            return llm_result
    if limit:
        return unique[:limit]
    return unique


def aggregate_insight_entries(
    insight_entries: List[Dict[str, str]],
    target_segment: Optional[str],
    limit_per_category: int,
) -> Dict[str, List[Dict[str, str]]]:
    motivations: List[Dict[str, str]] = []
    beliefs: List[Dict[str, str]] = []
    tensions: List[Dict[str, str]] = []

    for raw_insight in insight_entries:
        insight_type = normalize_insight_type(raw_insight.get("type"))
        segment = raw_insight.get("segment") or "General"

        if not insight_matches_segment(segment, target_segment):
            continue

        normalized = {
            "type": insight_type,
            "text": (raw_insight.get("text") or "").strip(),
            "segment": segment,
            "source_snippet": (raw_insight.get("source_snippet") or "").strip(),
            "source_document": raw_insight.get("source_document")
            or raw_insight.get("source_document_filename")
            or "",
        }

        if insight_type == "Motivation":
            motivations.append(normalized)
        elif insight_type == "Belief":
            beliefs.append(normalized)
        else:
            tensions.append(normalized)

    return {
        "motivations": dedupe_and_limit(motivations, limit_per_category),
        "beliefs": dedupe_and_limit(beliefs, limit_per_category),
        "tensions": dedupe_and_limit(tensions, limit_per_category),
    }


def aggregate_brand_insights(
    documents: List[models.BrandDocument],
    target_segment: Optional[str],
    limit_per_category: int
) -> Dict[str, List[Dict[str, str]]]:
    insight_entries: List[Dict[str, str]] = []

    for doc in documents:
        for raw_insight in (doc.extracted_insights or []):
            insight_entries.append(
                {
                    **raw_insight,
                    "source_document_filename": getattr(doc, "filename", None),
                }
            )

    return aggregate_insight_entries(insight_entries, target_segment, limit_per_category)


def aggregate_with_vector_search(
    brand_id: int,
    documents: List[models.BrandDocument],
    target_segment: Optional[str],
    limit_per_category: int,
) -> Dict[str, List[Dict[str, str]]]:
    """Prefer vector-search snippets when available, fall back to full documents."""

    vector_results = vector_search.search_brand_chunks(
        brand_id=brand_id,
        documents=documents,
        query_text=target_segment or "brand insights",
        top_k=limit_per_category * 3,
        target_segment=target_segment
    )

    if vector_results:
        logger.info("Using vector search results for brand %s", brand_id)
        return aggregate_insight_entries(vector_results, target_segment, limit_per_category)

    logger.info("Vector search unavailable (or empty); aggregating from documents for brand %s", brand_id)
    return aggregate_brand_insights(documents, target_segment, limit_per_category)


def flatten_insights(aggregated: Dict[str, List[Dict[str, str]]]) -> List[Dict[str, str]]:
    ordered_types = [("motivations", "Motivation"), ("beliefs", "Belief"), ("tensions", "Tension")]
    flattened: List[Dict[str, str]] = []
    for key, label in ordered_types:
        for insight in aggregated.get(key, []):
            flattened.append({**insight, "type": label})
    return flattened
