import os
root_db = 'pharma_personas.db'
backend_db = os.path.join('backend', 'pharma_personas.db')

print(f"Root DB Path: {os.path.abspath(root_db)}")
print(f"Root DB Size: {os.path.getsize(root_db) if os.path.exists(root_db) else 'Missing'}")

print(f"Backend DB Path: {os.path.abspath(backend_db)}")
print(f"Backend DB Size: {os.path.getsize(backend_db) if os.path.exists(backend_db) else 'Missing'}")
