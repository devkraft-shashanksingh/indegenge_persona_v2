from sqlalchemy import create_engine, inspect
import os

# Emulate database.py logic
BASE_DIR = os.path.join(os.getcwd(), 'backend')
DATABASE_URL = f"sqlite:///{os.path.join(BASE_DIR, 'pharma_personas.db')}"

print(f"Connecting to {DATABASE_URL}...")
engine = create_engine(DATABASE_URL)
inspector = inspect(engine)

if 'personas' in inspector.get_table_names():
    columns = [c['name'] for c in inspector.get_columns('personas')]
    print("SQLAlchemy sees columns:")
    for col in columns:
        print(f" - {col}")
else:
    print("Table 'personas' not found!")
