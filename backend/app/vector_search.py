
import logging
import time
from typing import Dict, List, Optional
import os
import openai

logger = logging.getLogger(__name__)
def _get_openai_client():
    """Configure OpenAI client with key from environment."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.warning("OpenAI API key not found (OPENAI_API_KEY).")
        return None
    return openai.OpenAI(api_key=api_key)

def search_brand_chunks(
    brand_id: int,
    documents: List[dict],
    query_text: str = "",
    top_k: int = 5,
    target_segment: str = None
) -> Optional[List[Dict[str, str]]]:
    """
    Search OpenAI Vector Stores for relevant chunks.
    
    Args:
        documents: List of dictionaries comprising [{'vector_store_id': ...}]
    """
    client = _get_openai_client()
    if not client:
        return None
        
    # Aggregate vector store IDs
    vector_store_ids = []
    for d in documents:
        if isinstance(d, dict):
            vs_id = d.get('vector_store_id')
        else:
            vs_id = getattr(d, 'vector_store_id', None)
            
        if vs_id:
            vector_store_ids.append(vs_id)
    
    # Deduplicate IDs to avoid redundancy
    unique_vs_ids = list(set(vector_store_ids))

    if not unique_vs_ids:
        logger.info("No vector stores to search.")
        return None

    all_results = []
    
    try:
        # Create a single thread with ALL vector stores attached
        logger.info(f"[DEBUG] search_brand_chunks: Starting vector search across {len(unique_vs_ids)} vector stores for query: {query_text[:50]}...")
        
        t0 = time.time()
        thread = client.beta.threads.create(
            tool_resources={
                "file_search": {
                    "vector_store_ids": unique_vs_ids
                }
            }
        )
        logger.info(f"[DEBUG] search_brand_chunks: thread created in {time.time()-t0:.1f}s")
        
        t1 = time.time()
        # Create a message with the query
        client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=query_text
        )
        logger.info(f"[DEBUG] search_brand_chunks: message created in {time.time()-t1:.1f}s")
        
        t2 = time.time()
        # Create a temporary assistant for this search
        assistant = client.beta.assistants.create(
            name="RAG Search Helper",
            instructions="""You are a research assistant. Search the attached files and return relevant excerpts that answer the user's query. 

CRITICAL: You MUST include citations for every factual claim or quote using the format [1], [2], etc.
The citations must link to the annotations in your response. 
If you don't find relevant information in the files, state that clearly.""",
            model="gpt-4o",  # Use gpt-4o for speed and better retrieval
            tools=[{"type": "file_search"}]
        )
        logger.info(f"[DEBUG] search_brand_chunks: assistant created in {time.time()-t2:.1f}s")
        
        t3 = time.time()
        # Run the thread
        run = client.beta.threads.runs.create_and_poll(
            thread_id=thread.id,
            assistant_id=assistant.id
        )
        logger.info(f"[DEBUG] search_brand_chunks: run completed in {time.time()-t3:.1f}s, status={run.status}")
        
        if run.status == 'completed':
            messages = list(client.beta.threads.messages.list(thread_id=thread.id, run_id=run.id))
            # Parse messages for citations/content
            for msg in messages:
                if msg.role == 'assistant' and msg.content:
                        for content_block in msg.content:
                            if hasattr(content_block, 'text'):
                                text_content = content_block.text.value
                                annotations = content_block.text.annotations
                                citations = []
                                
                                # Process annotations for citations
                                if annotations:
                                    for annotation in annotations:
                                        if hasattr(annotation, 'file_citation'):
                                            citation_data = {
                                                "file_id": annotation.file_citation.file_id,
                                                "quote": annotation.text if hasattr(annotation, 'text') else ""
                                            }
                                            citations.append(citation_data)
                                            logger.info(f"[DEBUG] Extracted citation: {citation_data['file_id']} - '{citation_data['quote'][:30]}...'")
                                            # Optional: Remove citation markers from text if desired
                                            # text_content = text_content.replace(annotation.text, "")
                                
                                all_results.append({
                                    "text": text_content,
                                    "source_document": "aggregated_search",
                                    "segment": target_segment or "General",
                                    "citations": citations
                                })
                        
        else:
            logger.warning(f"Vector search run did not complete. Status: {run.status}")

        # Cleanup
        try:
            client.beta.assistants.delete(assistant.id)
            client.beta.threads.delete(thread.id)
        except Exception as cleanup_error:
            logger.warning(f"Failed to cleanup search resources: {cleanup_error}")

    except Exception as e:
        logger.error(f"Vector search failed: {e}")
        return None

    if not all_results:
        logger.info("No results found in vector search.")
        return None
        
    return all_results[:top_k]
