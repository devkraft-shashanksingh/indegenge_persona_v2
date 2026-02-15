from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Body, BackgroundTasks, Response
from sqlalchemy.orm import Session
from typing import List, Optional, Dict
import os
import shutil
import uuid
import re
import time
import json
import logging
import asyncio

from .. import models, schemas, crud, persona_engine, document_processor
from ..database import get_db
from ..services import brand_service
from .. import knowledge_extractor, knowledge_merger, persona_check, auto_enrichment

router = APIRouter(
    tags=["brands"]
)

logger = logging.getLogger(__name__)

# --- Brand Library Endpoints ---

@router.post("/api/brands", response_model=schemas.Brand)
async def create_brand(brand: schemas.BrandCreate, db: Session = Depends(get_db)):
    """Create a new brand context."""
    # Check if brand exists
    existing = db.query(models.Brand).filter(models.Brand.name == brand.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Brand already exists")
    return crud.create_brand(db, brand)

@router.get("/api/brands", response_model=List[schemas.Brand])
async def get_brands(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """List all brands."""
    return crud.get_brands(db, skip, limit)


# --- Document Management ---

@router.post("/api/brands/{brand_id}/upload", response_model=schemas.BrandDocument)
async def upload_brand_document(
    brand_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload a document, extract text, classify it, and save to DB."""
    # Verify brand exists
    brand = db.query(models.Brand).filter(models.Brand.id == brand_id).first()
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")

    # Create uploads directory if not exists
    upload_dir = "uploads"
    os.makedirs(upload_dir, exist_ok=True)
    
    # Save file locally with sanitized filename and UUID prefix to avoid collisions
    original_filename = file.filename or "upload"
    safe_filename = os.path.basename(original_filename)
    safe_filename = re.sub(r"[^A-Za-z0-9._-]", "_", safe_filename).lstrip(".") or "upload"
    unique_prefix = uuid.uuid4().hex
    safe_file_location = os.path.join(upload_dir, f"{unique_prefix}_{safe_filename}")

    with open(safe_file_location, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    # Extract text
    text = document_processor.extract_text(safe_file_location)

    # Classify
    category = document_processor.classify_document(text)

    extracted_insights = [
        {
            **insight,
            "source_document": safe_filename
        }
        for insight in persona_engine.extract_mbt_from_text(text)
    ]

    # Create chunks and vector embeddings (OpenAI)
    chunk_size = 800
    chunks = document_processor.chunk_text(text, chunk_size=chunk_size)
    
    # generate_vector_embeddings returns (None, vector_store_id, chunk_ids)
    _, vector_store_id, chunk_ids = document_processor.generate_vector_embeddings(
        chunks,
        brand_id=brand_id,
        filename=safe_filename,
        chunk_size=chunk_size,
        insights=extracted_insights
    )

    # Create or replace document record while cleaning up any stale vectors
    chunk_size_value = chunk_size if (chunks or vector_store_id) else None

    doc_create = schemas.BrandDocumentCreate(
        brand_id=brand_id,
        filename=safe_filename,
        filepath=safe_file_location,
        category=category,
        summary=text[:200] + "..." if text else "No text extracted",
        extracted_insights=extracted_insights,
        vector_store_id=vector_store_id,
        chunk_size=chunk_size_value,
        chunk_ids=chunk_ids or None,
    )

    new_doc = crud.upsert_brand_document(db, doc_create)

    # Trigger Knowledge Graph Extraction
    try:
        logger.info(f"🧠 Starting knowledge extraction for document {new_doc.id}")
        nodes = await knowledge_extractor.extract_knowledge_from_document(
            document_id=new_doc.id,
            document_text=text,
            document_type=category or "brand_messaging",
            brand_id=brand_id,
            brand_name=brand.name,
            db=db
        )
        
        if nodes:
            logger.info(f"🧠 Inferring relationships for brand {brand_id}")
            await knowledge_extractor.infer_relationships(
                brand_id=brand_id,
                new_nodes=nodes,
                db=db
            )
    except Exception as e:
        logger.error(f"❌ Knowledge extraction failed for document {new_doc.id}: {e}")
        # We don't fail the request, just log the error

    return new_doc

@router.get("/api/brands/{brand_id}/documents", response_model=List[schemas.BrandDocument])
async def get_brand_documents(brand_id: int, db: Session = Depends(get_db)):
    """List documents for a specific brand."""
    return crud.get_brand_documents(db, brand_id)


@router.get("/api/brands/{brand_id}/documents/{document_id}/content")
async def get_brand_document_content(brand_id: int, document_id: int, db: Session = Depends(get_db)):
    """Get the text content of a specific brand document."""
    doc = db.query(models.BrandDocument).filter(
        models.BrandDocument.id == document_id, 
        models.BrandDocument.brand_id == brand_id
    ).first()
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if not doc.filepath or not os.path.exists(doc.filepath):
        # Fallback to summary if file is missing
        return {"content": doc.summary or "No content available."}
    
    try:
        # We reuse extract_text which handles PDF/Text etc.
        text = document_processor.extract_text(doc.filepath)
        return {"content": text}
    except Exception as e:
        logger.error(f"Error extracting text for document {document_id}: {e}")
        return {"content": doc.summary or "Error extracting content."}


@router.delete("/api/brands/{brand_id}/documents/{document_id}", status_code=204)
async def delete_brand_document(brand_id: int, document_id: int, db: Session = Depends(get_db)):
    """Delete a brand document and remove any associated vectors."""
    brand = db.query(models.Brand).filter(models.Brand.id == brand_id).first()
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")

    deleted = crud.delete_brand_document(db, document_id=document_id, brand_id=brand_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found")

    return Response(status_code=204)


# --- Brand Persona Management ---

@router.get("/api/brands/{brand_id}/personas", response_model=List[schemas.Persona])
async def get_brand_personas(
    brand_id: int, 
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db)
):
    """List personas belonging to a specific brand."""
    # Verify brand exists
    brand = db.query(models.Brand).filter(models.Brand.id == brand_id).first()
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")
    
    return crud.get_personas_by_brand(db, brand_id, skip=skip, limit=limit)

@router.get("/api/brands/{brand_id}/personas/count")
async def get_brand_personas_count(brand_id: int, db: Session = Depends(get_db)):
    """Get the count of personas for a specific brand."""
    # Verify brand exists
    brand = db.query(models.Brand).filter(models.Brand.id == brand_id).first()
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")
    
    count = crud.get_personas_count_by_brand(db, brand_id)
    return {"brand_id": brand_id, "brand_name": brand.name, "persona_count": count}


# --- Brand Context & Suggestions ---

@router.get("/api/brands/{brand_id}/context", response_model=schemas.BrandContextResponse)
async def get_brand_context(
    brand_id: int,
    target_segment: Optional[str] = None,
    limit_per_category: int = 5,
    db: Session = Depends(get_db)
):
    """Aggregate MBT insights for a brand with optional segment filtering."""
    brand = db.query(models.Brand).filter(models.Brand.id == brand_id).first()
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")

    limit_per_category = max(1, min(limit_per_category, 15))
    documents = crud.get_brand_documents(db, brand_id)
    aggregated = brand_service.aggregate_with_vector_search(
        brand_id=brand_id,
        documents=documents,
        target_segment=target_segment,
        limit_per_category=limit_per_category,
    )

    return schemas.BrandContextResponse(
        brand_id=brand.id,
        brand_name=brand.name,
        **aggregated
    )

@router.post("/api/brands/{brand_id}/persona-suggestions", response_model=schemas.BrandSuggestionResponse)
async def get_brand_persona_suggestions(
    brand_id: int,
    request: schemas.BrandSuggestionRequest,
    db: Session = Depends(get_db)
):
    """Generate MBT suggestion lists for manual persona creation."""
    brand = db.query(models.Brand).filter(models.Brand.id == brand_id).first()
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")

    limit = max(1, min(request.limit_per_category, 10))
    documents = crud.get_brand_documents(db, brand_id)
    aggregated = brand_service.aggregate_with_vector_search(
        brand_id=brand_id,
        documents=documents,
        target_segment=request.target_segment,
        limit_per_category=limit,
    )
    flattened = brand_service.flatten_insights(aggregated)

    suggestions = persona_engine.suggest_persona_attributes(
        flattened,
        persona_type=request.persona_type or "Patient"
    )

    return schemas.BrandSuggestionResponse(
        brand_id=brand.id,
        brand_name=brand.name,
        target_segment=request.target_segment,
        persona_type=request.persona_type,
        motivations=suggestions.get("motivations", []),
        beliefs=suggestions.get("beliefs", []),
        tensions=suggestions.get("tensions", []),
    )


# --- Seeding & Ingestion ---

@router.post("/api/brands/{brand_id}/seed", response_model=List[schemas.BrandDocument])
async def seed_brand_documents(brand_id: int, db: Session = Depends(get_db)):
    """Populate the brand with mock documents for demo purposes."""
    # Verify brand exists
    brand = db.query(models.Brand).filter(models.Brand.id == brand_id).first()
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")

    # Mock data for 7 categories
    mock_data = {
        "Disease & Patient Journey Overview": "This document covers the epidemiology, pathophysiology, and patient journey for Type 2 Diabetes. It highlights the emotional burden of diagnosis and the progressive nature of the disease.",
        "Treatment Landscape / SoC": "Current Standard of Care involves Metformin as first-line, followed by GLP-1 RAs or SGLT2 inhibitors. This review analyzes the efficacy and safety profiles of leading competitors.",
        "Brand Value Proposition & Core Messaging": "Our brand offers superior glycemic control with weight loss benefits. Key message: 'Power to control, freedom to live.' Differentiators include once-weekly dosing.",
        "Safety & Tolerability Summary": "Summary of adverse events from Phase 3 trials. GI side effects are most common but transient. No new safety signals observed in long-term extension studies.",
        "HCP & Patient Segmentation": "HCP Segments: 1. Efficacy-Driven Experts, 2. Safety-First Prescribers. Patient Segments: 1. The Proactive Manager, 2. The Overwhelmed Struggler.",
        "Market Research & Insight Summaries": "Qualitative research indicates that HCPs are hesitant to switch stable patients. Patients desire treatments that minimize lifestyle disruption.",
        "Adherence / Persistence / Discontinuation Insights": "Data shows 20% discontinuation rate at 6 months due to cost and GI issues. Persistence is higher with the autoinjector device compared to vials."
    }

    created_docs = []
    upload_dir = "uploads"
    os.makedirs(upload_dir, exist_ok=True)

    for category, text in mock_data.items():
        # Create a dummy file
        filename = f"Mock_{category.replace(' ', '_').replace('/', '-')}.txt"
        filepath = f"{upload_dir}/{int(time.time())}_{filename}"
        
        with open(filepath, "w") as f:
            f.write(text)
            
        chunk_size = 800
        chunks = document_processor.chunk_text(text, chunk_size=chunk_size)
        
        extracted_insights = [
            {
                **insight,
                "source_document": filename
            }
            for insight in persona_engine.extract_mbt_from_text(text)
        ]

        _, vector_store_id, chunk_ids = document_processor.generate_vector_embeddings(
            chunks,
            brand_id=brand_id,
            filename=filename,
            chunk_size=chunk_size,
            insights=extracted_insights
        )

        doc_create = schemas.BrandDocumentCreate(
            brand_id=brand_id,
            filename=filename,
            filepath=filepath,
            category=category,
            summary=text,
            extracted_insights=extracted_insights,
            vector_store_id=vector_store_id,
            chunk_size=chunk_size,
            chunk_ids=chunk_ids or None
        )
        
        new_doc = crud.upsert_brand_document(db, doc_create)
        created_docs.append(new_doc)
        
        # Trigger Knowledge Graph Extraction for this document
        try:
            logger.info(f"🧠 Starting knowledge extraction for seeded document {new_doc.id}")
            nodes = await knowledge_extractor.extract_knowledge_from_document(
                document_id=new_doc.id,
                document_text=text,
                document_type="brand_messaging", # Default for mock data
                brand_id=brand_id,
                brand_name=brand.name,
                db=db
            )
            
            if nodes:
                # We can infer relationships cumulatively
                await knowledge_extractor.infer_relationships(
                    brand_id=brand_id,
                    new_nodes=nodes,
                    db=db
                )
        except Exception as e:
            logger.error(f"❌ Knowledge extraction failed for seeded document {new_doc.id}: {e}")

    return created_docs

class FolderIngestRequest(schemas.BaseModel):
    """Request model for folder ingestion."""
    folder_path: str
    recursive: bool = True

class IngestResult(schemas.BaseModel):
    """Result of ingesting a single file."""
    filename: str
    status: str
    document_id: Optional[int] = None
    nodes_created: int = 0
    error: Optional[str] = None

class FolderIngestResponse(schemas.BaseModel):
    """Response for folder ingestion."""
    total_files: int
    successful: int
    failed: int
    total_nodes_created: int
    results: List[IngestResult]

@router.post("/api/brands/{brand_id}/ingest-folder", response_model=FolderIngestResponse)
async def ingest_folder(
    brand_id: int,
    request: FolderIngestRequest,
    db: Session = Depends(get_db)
):
    """
    Ingest all documents from a folder into the brand's knowledge graph.
    """
    # Verify brand exists
    brand = db.query(models.Brand).filter(models.Brand.id == brand_id).first()
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")
    
    folder_path = request.folder_path
    
    # Handle relative paths from project root
    if not os.path.isabs(folder_path):
        # Try relative to current working directory
        if not os.path.exists(folder_path):
            # Try relative to backend directory
            backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            project_root = os.path.dirname(backend_dir)
            folder_path = os.path.join(project_root, request.folder_path)
    
    if not os.path.exists(folder_path) or not os.path.isdir(folder_path):
        raise HTTPException(
            status_code=400, 
            detail=f"Folder not found: {request.folder_path}"
        )
    
    # Collect files
    supported_extensions = {'.pdf', '.txt', '.md', '.csv'}
    files_to_process = []
    
    if request.recursive:
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in supported_extensions:
                    files_to_process.append(os.path.join(root, file))
    else:
        for file in os.listdir(folder_path):
            ext = os.path.splitext(file)[1].lower()
            if ext in supported_extensions:
                files_to_process.append(os.path.join(folder_path, file))
    
    if not files_to_process:
        raise HTTPException(
            status_code=400,
            detail=f"No supported files found in folder (PDF, TXT, MD, CSV)"
        )
    
    logger.info(f"📁 Found {len(files_to_process)} files to ingest for brand {brand.name}")
    
    results: List[IngestResult] = []
    total_nodes_created = 0
    all_new_nodes = []
    
    upload_dir = "uploads"
    os.makedirs(upload_dir, exist_ok=True)
    
    for filepath in files_to_process:
        filename = os.path.basename(filepath)
        logger.info(f"📄 Processing: {filename}")
        
        try:
            # Extract text
            text = document_processor.extract_text(filepath)
            
            if not text or len(text.strip()) < 50:
                results.append(IngestResult(
                    filename=filename,
                    status="skipped",
                    error="No text content or too short"
                ))
                continue
            
            # Classify document
            category = document_processor.classify_document(text)
            
            # Extract MBT insights
            extracted_insights = [
                {**insight, "source_document": filename}
                for insight in persona_engine.extract_mbt_from_text(text)
            ]
            
            # Create chunks and embeddings
            chunk_size = 800
            chunks = document_processor.chunk_text(text, chunk_size=chunk_size)
            
            _, vector_store_id, chunk_ids = document_processor.generate_vector_embeddings(
                chunks,
                brand_id=brand_id,
                filename=filename,
                chunk_size=chunk_size,
                insights=extracted_insights
            )
            
            # Copy file to uploads with unique prefix
            unique_prefix = uuid.uuid4().hex
            safe_filename = re.sub(r"[^A-Za-z0-9._-]", "_", filename).lstrip(".") or "upload"
            dest_path = os.path.join(upload_dir, f"{unique_prefix}_{safe_filename}")
            shutil.copy2(filepath, dest_path)
            
            # Create document record
            doc_create = schemas.BrandDocumentCreate(
                brand_id=brand_id,
                filename=safe_filename,
                filepath=dest_path,
                category=category,
                summary=text[:200] + "..." if len(text) > 200 else text,
                extracted_insights=extracted_insights,
                vector_store_id=vector_store_id,
                chunk_size=chunk_size if chunks else None,
                chunk_ids=chunk_ids or None,
            )
            
            new_doc = crud.upsert_brand_document(db, doc_create)
            
            # Extract knowledge graph nodes
            nodes_created = 0
            try:
                nodes = await knowledge_extractor.extract_knowledge_from_document(
                    document_id=new_doc.id,
                    document_text=text,
                    document_type=category or "brand_messaging",
                    brand_id=brand_id,
                    brand_name=brand.name,
                    db=db
                )
                nodes_created = len(nodes) if nodes else 0
                total_nodes_created += nodes_created
                if nodes:
                    all_new_nodes.extend(nodes)
            except Exception as e:
                logger.error(f"❌ Knowledge extraction failed for {filename}: {e}")
            
            results.append(IngestResult(
                filename=filename,
                status="success",
                document_id=new_doc.id,
                nodes_created=nodes_created
            ))
            
        except Exception as e:
            logger.error(f"❌ Failed to process {filename}: {e}")
            results.append(IngestResult(
                filename=filename,
                status="failed",
                error=str(e)
            ))
    
    # Infer relationships for all new nodes at the end
    if all_new_nodes:
        try:
            logger.info(f"🧠 Inferring relationships for {len(all_new_nodes)} new nodes")
            await knowledge_extractor.infer_relationships(
                brand_id=brand_id,
                new_nodes=all_new_nodes,
                db=db
            )
        except Exception as e:
            logger.error(f"❌ Relationship inference failed: {e}")
    
    successful = sum(1 for r in results if r.status == "success")
    failed = sum(1 for r in results if r.status == "failed")
    
    logger.info(f"✅ Ingestion complete: {successful} successful, {failed} failed, {total_nodes_created} nodes created")
    
    return FolderIngestResponse(
        total_files=len(files_to_process),
        successful=successful,
        failed=failed,
        total_nodes_created=total_nodes_created,
        results=results
    )


# --- Knowledge Graph Endpoints ---

@router.get("/api/knowledge/brands/{brand_id}/nodes")
async def get_knowledge_nodes(
    brand_id: int,
    node_type: Optional[str] = None,
    segment: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get knowledge nodes for a brand."""
    query = db.query(models.KnowledgeNode).filter(
        models.KnowledgeNode.brand_id == brand_id
    )
    
    if node_type:
        query = query.filter(models.KnowledgeNode.node_type == node_type)
    if segment:
        query = query.filter(models.KnowledgeNode.segment.ilike(f"%{segment}%"))
    
    total = query.count()
    nodes = query.offset(skip).limit(limit).all()
    
    return {
        "total": total,
        "nodes": [
            {
                "id": n.id,
                "node_type": n.node_type,
                "text": n.text,
                "summary": n.summary,
                "segment": n.segment,
                "journey_stage": n.journey_stage,
                "confidence": n.confidence,
                "source_document_id": n.source_document_id,
                "source_quote": n.source_quote,
                "verified": n.verified_by_user,
                "created_at": n.created_at.isoformat() if n.created_at else None
            }
            for n in nodes
        ]
    }

@router.get("/api/knowledge/brands/{brand_id}/relations")
async def get_knowledge_relations(
    brand_id: int,
    relation_type: Optional[str] = None,
    skip: int = 0,
    limit: int = 200,
    db: Session = Depends(get_db)
):
    """Get knowledge relations for a brand."""
    query = db.query(models.KnowledgeRelation).filter(
        models.KnowledgeRelation.brand_id == brand_id
    )
    
    if relation_type:
        query = query.filter(models.KnowledgeRelation.relation_type == relation_type)
    
    total = query.count()
    relations = query.offset(skip).limit(limit).all()
    
    return {
        "total": total,
        "relations": [
            {
                "id": r.id,
                "from_node_id": r.from_node_id,
                "to_node_id": r.to_node_id,
                "relation_type": r.relation_type,
                "strength": r.strength,
                "context": r.context,
                "inferred_by": r.inferred_by,
                "created_at": r.created_at.isoformat() if r.created_at else None
            }
            for r in relations
        ]
    }

@router.get("/api/knowledge/brands/{brand_id}/graph")
async def get_full_knowledge_graph(
    brand_id: int,
    db: Session = Depends(get_db)
):
    """
    Get the full knowledge graph for visualization.
    Returns nodes and edges in a format suitable for React Flow.
    """
    nodes = db.query(models.KnowledgeNode).filter(
        models.KnowledgeNode.brand_id == brand_id
    ).all()
    
    relations = db.query(models.KnowledgeRelation).filter(
        models.KnowledgeRelation.brand_id == brand_id
    ).all()
    
    # Format for React Flow
    graph_nodes = []
    for n in nodes:
        graph_nodes.append({
            "id": n.id,
            "type": "knowledgeNode",  # Custom React Flow node type
            "data": {
                "label": n.summary or n.text[:50],
                "node_type": n.node_type,
                "text": n.text,
                "segment": n.segment,
                "confidence": n.confidence,
                "verified": n.verified_by_user,
                "source_quote": n.source_quote
            },
            "position": {"x": 0, "y": 0}  # Frontend will compute layout
        })
    
    graph_edges = []
    for r in relations:
        graph_edges.append({
            "id": f"e-{r.id}",
            "source": r.from_node_id,
            "target": r.to_node_id,
            "type": "knowledgeEdge",  # Custom React Flow edge type
            "data": {
                "relation_type": r.relation_type,
                "strength": r.strength,
                "context": r.context
            },
            "label": r.relation_type,
            "animated": r.relation_type == "contradicts"  # Highlight contradictions
        })
    
    # Count by type for stats
    type_counts = {}
    for n in nodes:
        type_counts[n.node_type] = type_counts.get(n.node_type, 0) + 1
    
    return {
        "brand_id": brand_id,
        "nodes": graph_nodes,
        "edges": graph_edges,
        "stats": {
            "total_nodes": len(nodes),
            "total_edges": len(relations),
            "node_types": type_counts,
            "contradictions": sum(1 for r in relations if r.relation_type == "contradicts")
        }
    }


@router.post("/api/knowledge/documents/{document_id}/extract")
async def extract_knowledge_from_document(
    document_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Trigger knowledge extraction from a document.
    """
    # Get the document
    document = db.query(models.BrandDocument).filter(
        models.BrandDocument.id == document_id
    ).first()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Get brand info
    brand = db.query(models.Brand).filter(models.Brand.id == document.brand_id).first()
    brand_name = brand.name if brand else "Unknown Brand"
    
    # Get document text from extracted insights or re-extract
    document_text = ""
    if document.extracted_insights:
        insights = document.extracted_insights
        if isinstance(insights, str):
            try:
                insights = json.loads(insights)
            except:
                insights = {}
        
        # Try to get raw text
        document_text = insights.get("raw_text", "")
        if not document_text:
            # Reconstruct from insights
            for key in ["motivations", "beliefs", "tensions"]:
                items = insights.get(key, [])
                if isinstance(items, list):
                    for item in items:
                        if isinstance(item, dict):
                            document_text += item.get("text", "") + ". "
                        elif isinstance(item, str):
                            document_text += item + ". "
    
    if not document_text:
        return {
            "success": False,
            "message": "No text content found in document. Please re-upload with text extraction."
        }
    
    # Determine document type
    doc_type = document.document_type or "brand_messaging"
    
    # Extract knowledge nodes
    nodes = knowledge_extractor.extract_knowledge_from_document_sync(
        document_id=document_id,
        document_text=document_text,
        document_type=doc_type,
        brand_id=document.brand_id,
        brand_name=brand_name,
        db=db
    )
    
    # Infer relationships
    relations = []
    if nodes:
        relations = knowledge_extractor.infer_relationships_sync(
            brand_id=document.brand_id,
            new_nodes=nodes,
            db=db
        )
    
    return {
        "success": True,
        "document_id": document_id,
        "document_type": doc_type,
        "nodes_extracted": len(nodes),
        "relationships_inferred": len(relations),
        "node_ids": [n.id for n in nodes]
    }


@router.post("/api/knowledge/brands/{brand_id}/personas/{persona_id}/enrich")
async def enrich_persona_from_graph(
    brand_id: int,
    persona_id: int,
    db: Session = Depends(get_db)
):
    """
    Enrich a persona with relevant insights from the knowledge graph.
    """
    result = auto_enrichment.enrich_persona_from_knowledge_graph_sync(
        persona_id=persona_id,
        brand_id=brand_id,
        db=db
    )
    
    if result is None:
        raise HTTPException(status_code=404, detail="Persona not found")
    
    return {
        "success": True,
        "persona_id": persona_id,
        "enriched": True,
        "nodes_applied": result.get("knowledge_graph_enrichment", {}).get("nodes_applied", 0)
    }


@router.get("/api/knowledge/brands/{brand_id}/persona-check")
async def check_persona_alignment(
    brand_id: int,
    persona_ids: str,  # Comma-separated list of persona IDs
    db: Session = Depends(get_db)
):
    """
    Pre-flight check: Validate if selected personas have known triggers or gaps
    in brand messaging before asset analysis.
    """
    # Parse persona IDs
    try:
        ids = [int(id.strip()) for id in persona_ids.split(",") if id.strip()]
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid persona_ids format")
    
    if not ids:
        raise HTTPException(status_code=400, detail="At least one persona_id is required")
    
    result = persona_check.check_persona_alignment(
        brand_id=brand_id,
        persona_ids=ids,
        db=db
    )
    
    result["summary"] = persona_check.get_persona_check_summary(result)
    
    return result

@router.delete("/api/knowledge/nodes/{node_id}")
async def delete_knowledge_node(
    node_id: str,
    db: Session = Depends(get_db)
):
    """Delete a knowledge node and its relationships."""
    node = db.query(models.KnowledgeNode).filter(
        models.KnowledgeNode.id == node_id
    ).first()
    
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    
    # Delete related relations
    db.query(models.KnowledgeRelation).filter(
        (models.KnowledgeRelation.from_node_id == node_id) |
        (models.KnowledgeRelation.to_node_id == node_id)
    ).delete()
    
    db.delete(node)
    db.commit()
    
    return {"success": True, "deleted_node_id": node_id}


@router.put("/api/knowledge/nodes/{node_id}/verify")
async def verify_knowledge_node(
    node_id: str,
    verified: bool = True,
    db: Session = Depends(get_db)
):
    """Mark a knowledge node as verified by user."""
    node = db.query(models.KnowledgeNode).filter(
        models.KnowledgeNode.id == node_id
    ).first()
    
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    
    node.verified_by_user = verified
    db.commit()
    
    return {"success": True, "node_id": node_id, "verified": verified}





@router.get("/api/knowledge/brands/{brand_id}/duplicates")
async def get_duplicate_nodes(
    brand_id: int,
    threshold: float = 0.60,
    db: Session = Depends(get_db)
):
    """
    Find duplicate/similar knowledge nodes for review.
    """
    candidates = knowledge_merger.find_duplicate_candidates(
        brand_id=brand_id,
        db=db,
        threshold=threshold
    )
    
    return {
        "brand_id": brand_id,
        "threshold": threshold,
        "duplicate_count": len(candidates),
        "duplicates": candidates
    }


@router.post("/api/knowledge/nodes/merge")
async def merge_knowledge_nodes(
    payload: dict = Body(...),
    db: Session = Depends(get_db)
):
    """
    Merge multiple nodes into a primary node.
    """
    primary_id = payload.get("primary_id")
    secondary_ids = payload.get("secondary_ids", [])
    
    if not primary_id or not secondary_ids:
        raise HTTPException(status_code=400, detail="primary_id and secondary_ids required")
    
    result = knowledge_merger.merge_nodes(
        primary_id=primary_id,
        secondary_ids=secondary_ids,
        db=db
    )
    
    if result.get("error"):
        raise HTTPException(status_code=404, detail=result["error"])
    
    return result

@router.post("/api/knowledge/brands/{brand_id}/rebuild-relationships")
async def rebuild_brand_relationships(
    brand_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Rebuild all relationships for a brand using comprehensive inference.
    """
    def rebuild_task():
        """Background task to rebuild relationships."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Delete existing LLM relationships
            deleted = db.query(models.KnowledgeRelation).filter(
                models.KnowledgeRelation.brand_id == brand_id,
                models.KnowledgeRelation.inferred_by == "llm"
            ).delete()
            db.commit()
            
            logger.info(f"🗑️  Deleted {deleted} existing LLM relationships for brand {brand_id}")
            
            # Run comprehensive inference
            new_rels = loop.run_until_complete(
                knowledge_extractor.create_comprehensive_relationships(
                    brand_id=brand_id,
                    db=db,
                    batch_size=20
                )
            )
            
            logger.info(f"✅ Created {len(new_rels)} new relationships for brand {brand_id}")
            
        finally:
            loop.close()
    
    background_tasks.add_task(rebuild_task)
    
    return {
        "success": True,
        "message": "Relationship rebuild started in background",
        "brand_id": brand_id
    }


@router.post("/api/knowledge/brands/{brand_id}/auto-merge")
async def auto_merge_duplicate_nodes(
    brand_id: int,
    threshold: float = 0.85,
    db: Session = Depends(get_db)
):
    """
    Automatically merge nodes with very high similarity (>= threshold).
    """
    result = knowledge_merger.auto_merge_duplicates(
        brand_id=brand_id,
        db=db,
        threshold=threshold
    )
    
    return result
