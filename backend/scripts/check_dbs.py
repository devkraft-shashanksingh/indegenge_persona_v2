"""
Check which database has the knowledge_relations table
"""
import sqlite3
import os

# Check both databases
dbs = [
    "pharma_personas.db",
    "backend/pharma_personas.db"
]

for db_path in dbs:
    if os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cursor.fetchall()]
        print(f"{db_path}: {tables}")
        
        if "knowledge_relations" in tables:
            cursor.execute("SELECT COUNT(*) FROM knowledge_relations")
            count = cursor.fetchone()[0]
            print(f"  -> knowledge_relations has {count} rows")
            
            cursor.execute("SELECT relation_type FROM knowledge_relations")
            types = [r[0] for r in cursor.fetchall()]
            print(f"  -> relation_types: {types}")
        
        conn.close()
    else:
        print(f"{db_path}: NOT FOUND")
