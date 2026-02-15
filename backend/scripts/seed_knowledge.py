import sys
import os
from pathlib import Path
import uuid
import random
from datetime import datetime

# Add backend to path
backend_path = Path(__file__).parent / "backend"
sys.path.append(str(backend_path))

# Set DB URL explicitely to match backend folder
os.environ["DATABASE_URL"] = "sqlite:///backend/pharma_personas.db"

from app.database import SessionLocal
from app import models

def seed_mounjaro_knowledge():
    print("🌱 Seeding knowledge graph for Mounjaro (ID 3)...")
    db = SessionLocal()
    brand_id = 3
    
    # Check if brand exists
    brand = db.query(models.Brand).filter(models.Brand.id == brand_id).first()
    if not brand:
        print(f"❌ Brand ID {brand_id} not found/created yet.")
        return

    # Define Data
    tensions = [
        ("Fear of needles", "patient_tension", "Anxiety about self-injection process and pain.", "Patient"),
        ("Weight regain anxiety", "patient_tension", "Worry that weight will come back after stopping.", "Patient"),
        ("Cost of treatment", "patient_tension", "Concerns about insurance coverage and out-of-pocket costs.", "Patient"),
        ("GI side effects", "patient_tension", "Nausea and stomach issues are a major barrier.", "Patient"),
        ("Social stigma", "patient_tension", "Feeling judged for taking medication for weight loss.", "Patient"),
        ("Long-term safety", "patient_tension", "Uncertainty about the long-term effects of the drug.", "Patient")
    ]

    messages = [
        ("Once-weekly injection", "key_message", "Convenient dosing schedule simplifies treatment.", "All"),
        ("Superior weight loss", "key_message", "Clinical trials show significant reduction compared to placebo.", "HCP"),
        ("Savings card program", "key_message", "Commercial savings card helps eligible patients pay as little as $25.", "Patient"),
        ("Titration support", "key_message", "Gradual dose increase helps manage GI side effects.", "HCP"),
        ("Body composition benefits", "key_message", "Helps reduce fat mass while preserving lean muscle.", "All")
    ]
    
    hcps = [
        ("Patient compliance", "hcp_concern", "Will patients stick to the weekly schedule?", "HCP"),
        ("Prior Authorization burden", "hcp_concern", "Administrative time needed for insurance approvals.", "HCP")
    ]

    nodes_to_create = []
    
    # Helper to create node
    def create_node(text, type, summary, segment):
        node_id = str(uuid.uuid4())
        node = models.KnowledgeNode(
            id=node_id,
            brand_id=brand_id,
            node_type=type,
            text=text,
            summary=summary,
            segment=segment,
            confidence=0.95,
            verified_by_user=True,
            created_at=datetime.now()
        )
        nodes_to_create.append(node)
        return node

    # Create Nodes
    node_map = {} # text -> node object
    
    for t in tensions:
        n = create_node(t[0], t[1], t[2], t[3])
        node_map[t[0]] = n
        
    for m in messages:
        n = create_node(m[0], m[1], m[2], m[3])
        node_map[m[0]] = n
        
    for h in hcps:
        n = create_node(h[0], h[1], h[2], h[3])
        node_map[h[0]] = n

    # Bulk add nodes
    print(f"➕ Adding {len(nodes_to_create)} nodes...")
    for n in nodes_to_create:
        db.merge(n) # merge avoids error if UUID somehow duplicates
    db.commit()

    # Define Relations (From -> Type -> To)
    relations_data = [
        ("Once-weekly injection", "addresses", "Fear of needles"),
        ("Once-weekly injection", "supports", "Patient compliance"),
        ("Superior weight loss", "addresses", "Weight regain anxiety"),
        ("Savings card program", "addresses", "Cost of treatment"),
        ("Titration support", "addresses", "GI side effects"),
        ("Titration support", "supports", "Patient compliance"),
        ("Prior Authorization burden", "reinforces", "Cost of treatment"), # Admin burden reinforces cost concerns indirectly
        ("Social stigma", "contradicts", "Superior weight loss"), # Stigma fights against the clinical success narrative
        ("Cost of treatment", "triggers", "Prior Authorization burden"),
    ]

    print("🔗 Creating relationships...")
    for src_txt, rel_type, tgt_txt in relations_data:
        src = node_map.get(src_txt)
        tgt = node_map.get(tgt_txt)
        
        if src and tgt:
            rel = models.KnowledgeRelation(
                brand_id=brand_id,
                from_node_id=src.id,
                to_node_id=tgt.id,
                relation_type=rel_type,
                strength=0.85,
                context=f"{src_txt} {rel_type} {tgt_txt}",
                created_at=datetime.now()
            )
            db.add(rel)
    
    db.commit()
    print("✅ Seed complete successfully!")

if __name__ == "__main__":
    seed_mounjaro_knowledge()
