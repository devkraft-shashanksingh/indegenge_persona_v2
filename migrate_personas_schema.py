import sqlite3
import os

db_path = os.path.join('backend', 'pharma_personas.db')
if not os.path.exists(db_path):
    db_path = 'pharma_personas.db'

print(f"Connecting to {db_path}...")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get existing columns
cursor.execute("PRAGMA table_info(personas)")
existing_cols = [c[1] for c in cursor.fetchall()]

# Columns to add if missing
new_cols = [
    ("persona_subtype", "TEXT"),
    ("tagline", "TEXT"),
    ("specialty", "TEXT"),
    ("practice_setup", "TEXT"),
    ("system_context", "TEXT"),
    ("decision_influencers", "TEXT"),
    ("adherence_to_protocols", "TEXT"),
    ("channel_use", "TEXT"),
    ("decision_style", "TEXT"),
    ("additional_context", "JSON")
]

for col_name, col_type in new_cols:
    if col_name not in existing_cols:
        try:
            print(f"Adding column '{col_name}'...")
            cursor.execute(f"ALTER TABLE personas ADD COLUMN {col_name} {col_type}")
            conn.commit()
            print(f"Successfully added '{col_name}'.")
        except Exception as e:
            print(f"Error adding '{col_name}': {e}")
    else:
        print(f"Column '{col_name}' already exists.")

conn.close()
print("Migration check complete.")
