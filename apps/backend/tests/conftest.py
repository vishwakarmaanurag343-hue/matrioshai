import pytest
import os
import tempfile
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.core.database import Base, get_db
from app.core.config import settings
from main import app

@pytest.fixture(scope="function")
def test_db():
    # Use temporary directory for isolated test data
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_file = Path(tmp_dir) / "test.db"
        notes_dir = Path(tmp_dir) / "notes"
        notes_dir.mkdir(parents=True, exist_ok=True)

        settings.DATABASE_PATH = str(db_file)
        settings.NOTES_PATH = str(notes_dir)

        engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
        TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        Base.metadata.create_all(bind=engine)

        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

@pytest.fixture(scope="function")
def client(test_db):
    def override_get_db():
        try:
            yield test_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
