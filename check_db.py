import sqlite3
import os

db_path = os.path.join('backend', 'pharma_personas.db')
if not os.path.exists(db_path):
    db_path = 'pharma_personas.db'

print(f"Connecting to {db_path}...")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("PRAGMA table_info(personas)")
cols = cursor.fetchall()
print("PERSONAS TABLE COLUMNS:")
for col in cols:
    print(col)

conn.close()
