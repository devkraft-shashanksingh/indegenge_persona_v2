from app.database import engine
from sqlalchemy import text

with engine.connect() as conn:
    conn.execute(text("DROP TABLE IF EXISTS persona.alembic_version;"))
    conn.commit()
print("Dropped persona.alembic_version table.")
