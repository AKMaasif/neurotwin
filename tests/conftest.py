import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.db import Base, get_db
from app.main import app, attempts
from app.seed import seed


@pytest.fixture(
    params=["sqlite"] + (["postgres"] if os.environ.get("TEST_POSTGRES") == "1" else [])
)
def database(monkeypatch, request, tmp_path):
    monkeypatch.setattr(settings, "media_store_path", str(tmp_path / "private-media"))
    monkeypatch.setattr(settings, "demo_password", "test-password-not-for-deployment")
    monkeypatch.setattr(settings, "ai_enabled", False)
    schema = None
    admin = None
    if request.param == "postgres":
        schema = "nt_test_" + uuid.uuid4().hex
        admin = create_engine(settings.database_url)
        with admin.begin() as conn:
            conn.execute(text(f"CREATE SCHEMA {schema}"))
        engine = create_engine(
            settings.database_url, connect_args={"options": f"-csearch_path={schema}"}
        )
    else:
        engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory() as db:
        seed(db)

    def dependency():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = dependency
    attempts.clear()
    yield factory
    app.dependency_overrides.clear()
    engine.dispose()
    if schema:
        assert schema.startswith("nt_test_") and schema[8:].isalnum()
        with admin.begin() as conn:
            conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        admin.dispose()


@pytest.fixture
def client(database):
    return TestClient(app)


def sign_in(client, user="participant"):
    r = client.post(
        "/api/login",
        json={"username": user, "password": "test-password-not-for-deployment"},
    )
    assert r.status_code == 200, r.text
    client.headers["X-CSRF-Token"] = r.json()["csrf"]
    return client
