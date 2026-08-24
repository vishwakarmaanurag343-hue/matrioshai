from sqlalchemy import text
from app.core.database import Base, engine
from app.core.logging import logger
from app.models import db_models  # Ensure models are registered

def run_migrations():
    """
    Initializes database tables if they do not exist.
    Supports lightweight schema verification and column migrations.
    """
    logger.info("Initializing database schema and checking migrations...")
    Base.metadata.create_all(bind=engine)

    # Lightweight SQLite column additions if tables existed prior to phase 2
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE memory_items ADD COLUMN classification VARCHAR(20) DEFAULT 'PRIVATE'"))
            conn.commit()
        except Exception:
            pass  # Column already exists

        try:
            conn.execute(text("ALTER TABLE notes ADD COLUMN classification VARCHAR(20) DEFAULT 'PRIVATE'"))
            conn.commit()
        except Exception:
            pass

    logger.info("Database migration check completed successfully.")
