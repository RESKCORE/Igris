"""Shared pytest fixtures for OpsPilot test suite."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.config import settings
from app.db import Base, get_db
from app.main import app


@pytest.fixture(autouse=True)
def no_owner_mail(monkeypatch):
    """Hermetic: .env may carry a real OWNER_EMAIL; tests never mail the owner."""
    monkeypatch.setattr(settings, "OWNER_EMAIL", "")
    monkeypatch.setattr(settings, "OWNER_NOTIFY", True)


@pytest.fixture
def test_db():
    """Create an isolated in-memory SQLite database with StaticPool for thread safety."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(test_db):
    """FastAPI TestClient with overridden database session."""
    def override_get_db():
        try:
            yield test_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

