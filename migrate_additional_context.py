import sqlite3
import os

db_path = os.path.join('backend', 'pharma_personas.db')
if not os.path.exists(db_path):
    # Try alternate location if root is backend
    db_path = 'pharma_personas.db'

print(f"Connecting to {db_path}...")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    print("Attempting to add 'additional_context' column to 'personas' table...")
    cursor.execute("ALTER TABLE personas ADD COLUMN additional_context JSON")
    conn.commit()
    print("Successfully added 'additional_context' column.")
except sqlite3.OperationalError as e:
    if "duplicate column name" in str(e).lower():
        print("Column 'additional_context' already exists.")
    else:
        print(f"Error: {e}")
finally:
    conn.close()
