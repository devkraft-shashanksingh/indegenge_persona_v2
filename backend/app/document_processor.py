import json
import os
import tempfile
import logging
from typing import List, Optional, Tuple

from openai import OpenAI
from pypdf import PdfReader

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_openai_client: Optional[OpenAI] = None


def chunk_text(text: str, chunk_size: int = 800, overlap: int = 100) -> List[str]:
    """Simple text chunker to break long passages into overlapping chunks.
    
    Args:
        text: The text to chunk.
        chunk_size: Maximum size of each chunk in characters.
        overlap: Number of characters to overlap between chunks.
        
    Returns:
        List of text chunks.
        
    Note:
        To prevent pathological cases where overlap is very close to chunk_size
        (e.g., chunk_size=100, overlap=99 creating 100x more chunks than expected),
        the effective increment is enforced to be at least 10% of chunk_size or 50 chars.
    """
    if not text:
        return []

    if chunk_size <= 0:
        logger.warning("Chunk size must be positive; returning empty list.")
        return []
    
    if overlap >= chunk_size:
        logger.warning("Overlap must be smaller than chunk size; using non-overlapping chunks.")
        overlap = 0
    
    # Calculate minimum increment to prevent pathological cases
    # Minimum is 10% of chunk_size or 50 chars, whichever is larger (but capped at chunk_size)
    min_increment = min(chunk_size, max(50, chunk_size // 10))
    
    # If overlap would cause increment below minimum, reduce overlap
    effective_overlap = overlap
    if chunk_size - overlap < min_increment:
        effective_overlap = chunk_size - min_increment
        if effective_overlap != overlap:
            logger.warning(
                f"Overlap {overlap} too close to chunk_size {chunk_size}; "
                f"reduced to {effective_overlap} for minimum increment of {min_increment}."
            )

    chunks: List[str] = []
    start = 0
    text_length = len(text)

    while start < text_length:
        end = min(text_length, start + chunk_size)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        # Use the effective overlap to ensure reasonable increment
        increment = max(min_increment, chunk_size - effective_overlap)
        start += increment

    return chunks


from .utils import get_openai_client as _get_openai_client, MODEL_NAME

def extract_text(filepath: str) -> str:
    """
    Extracts text from a file (PDF or Text).
    Returns empty string if no text could be extracted (e.g. image-based PDF).
    """
    try:
        ext = os.path.splitext(filepath)[1].lower()
        text = ""
        
        if ext == ".pdf":
            reader = PdfReader(filepath)
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"
        elif ext in [".txt", ".md", ".csv"]:
            with open(filepath, "r", encoding="utf-8") as f:
                text = f.read()
        
        return text.strip()
    except Exception as e:
        logger.error(f"Error extracting text from {filepath}: {e}")
        return ""

def classify_document(text: str) -> str:
    """
    Classifies the document text into one of the 7 knowledge pillars using OpenAI.
    """
    if not text:
        return "Unclassified / Image-only"

    client = _get_openai_client()
    if client is None:
        logger.warning("OpenAI API key not configured; returning offline classification.")
        return "Unclassified (Offline)"

    # Truncate text to first 1000 chars to save tokens, usually enough for classification
    truncated_text = text[:1000]

    prompt = f"""
    You are an expert pharma brand strategist. Classify the following document text into EXACTLY ONE of these 4 categories:

    1. Clinical Data - Clinical trials, safety info, disease state, medical literature
    2. Marketing Content - Value proposition, messaging, visual aids, brand guidelines
    3. Patient Insights - Patient journey, segmentation, interviews, behavior
    4. Other - Regulatory, competitive intel, or unclassified

    If the text doesn't fit well, choose the closest match.
    Return ONLY the category name, nothing else.

    Document Text:
    {truncated_text}
    """

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "You are a helpful assistant that classifies documents."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.0,
            max_completion_tokens=50
        )
        category = response.choices[0].message.content.strip()
        
        # Validate category against list to ensure exact match
        valid_categories = [
            "Clinical Data",
            "Marketing Content",
            "Patient Insights",
            "Other"
        ]
        
        # Simple fuzzy match or exact match check
        for valid in valid_categories:
            if valid.lower() in category.lower():
                return valid
                
        return "Other"
        
    except Exception as e:
        logger.error(f"Error classifying document: {e}")
        return "Unclassified (Error)"




def generate_vector_embeddings(
    chunks: List[str],
    *,
    brand_id: int,
    filename: str,
    chunk_size: int,
    insights: Optional[List[dict]] = None,
    existing_corpus_id: Optional[str] = None
) -> Tuple[Optional[str], Optional[str], List[str]]:
    """
    Generate vector embeddings for the given chunks using OpenAI.
    
    This function:
    1. Creating a Vector Store for the brand/document if needed.
    2. Uploading the file to OpenAI.
    3. Attaching the file to the Vector Store.
    
    Returns:
        (None, vector_store_id, []) - We return vector_store_id as the second element (document identifier)
    """
    client = _get_openai_client()
    if not client:
        logger.warning("OpenAI client not initialized.")
        return None, None, []

    if not chunks:
        logger.info("No chunks/text to ingest.")
        return None, None, []
        
    # Create valid filename
    safe_filename = "".join([c for c in filename if c.isalnum() or c in "._-"])
    
    try:
        # 1. Create a Vector Store
        try:
            # Check if beta.vector_stores exists on the client
            if not hasattr(client, 'beta') or not hasattr(client.beta, 'vector_stores'):
                logger.warning("OpenAI client does not support beta.vector_stores. Skipping vector store creation.")
                return None, None, []
            
            vs_name = f"brand-{brand_id}-{safe_filename}"
            vector_store = client.beta.vector_stores.create(name=vs_name)
        except Exception as e:
            logger.warning(f"Failed to create OpenAI Vector Store (feature might be unavailable): {e}")
            return None, None, []
        
        # 2. Upload File (Stream the text content as a file)
        # We need to recreate the file content from chunks or use the original file if we had the path.
        # Since we receive 'chunks' (list of str), we'll join them to form the document content.
        full_text = "\n\n".join(chunks)
        
        # Create a temporary file to upload
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix=".txt", encoding='utf-8') as tmp:
            tmp.write(full_text)
            tmp_path = tmp.name
            
        try:
            with open(tmp_path, "rb") as file_stream:
                file_batch = client.beta.vector_stores.file_batches.upload_and_poll(
                    vector_store_id=vector_store.id,
                    files=[file_stream]
                )
                logger.info(f"Uploaded file batch status: {file_batch.status}")
                logger.info(f"File counts: {file_batch.file_counts}")
 
            return None, vector_store.id, []
            
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    except Exception as e:
        logger.error(f"Failed to ingest into OpenAI Vector Store: {e}")
        return None, None, []
