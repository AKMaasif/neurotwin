import json
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from app.db import LoginSession, User
from app.main import app
from app.security import password_matches
from tests.conftest import sign_in

PATH = "/api/account/password"
OLD = "test-password-not-for-deployment"
NEW = "Synthetic replacement passphrase 2026"


def change(client, **updates):
    return client.post(
        PATH, json={"current_password": OLD, "new_password": NEW} | updates
    )


def test_change_verifies_old_password_and_revokes_all_own_sessions(client, database):
    sign_in(client)
    other = sign_in(TestClient(app))
    family = sign_in(TestClient(app), "family")
    result = change(client)
    assert result.status_code == 200, result.text
    assert OLD not in result.text and NEW not in result.text
    assert client.get("/api/session").status_code == 401
    assert other.get("/api/session").status_code == 401
    assert family.get("/api/session").status_code == 200
    with database() as db:
        assert password_matches(NEW, db.get(User, "participant").password_hash)
        assert db.query(LoginSession).filter_by(user_id="participant").count() == 0
    assert (
        client.post(
            "/api/login", json={"username": "participant", "password": OLD}
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/login", json={"username": "participant", "password": NEW}
        ).status_code
        == 200
    )


def test_wrong_current_password_and_reuse_preserve_session_and_hash(client, database):
    sign_in(client)
    with database() as db:
        original = db.get(User, "participant").password_hash
    assert (
        change(client, current_password="wrong-current-passphrase").status_code == 400
    )
    assert change(client, new_password=OLD).status_code == 422
    assert client.get("/api/session").status_code == 200
    with database() as db:
        assert db.get(User, "participant").password_hash == original


@pytest.mark.parametrize(
    "body",
    [
        {"current_password": OLD, "new_password": "private-short"},
        {"current_password": OLD, "new_password": " " * 20},
        {"current_password": OLD, "new_password": "private-long" * 50},
        {"current_password": OLD, "new_password": 123456789012345},
        {"current_password": OLD, "new_password": NEW, "actor_id": "family"},
        ["private-invalid-body"],
        {"current_password": OLD, "new_password": "\ud800" * 15},
        {"current_password": "\ud800", "new_password": NEW},
    ],
)
def test_validation_does_not_echo_secrets(client, body):
    sign_in(client)
    response = client.post(
        PATH,
        content=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422
    assert OLD not in response.text and NEW not in response.text
    assert "private-" not in response.text
    assert client.get("/api/session").status_code == 200


def test_auth_csrf_actor_and_request_size_limits(client):
    assert change(client).status_code == 401
    sign_in(client)
    csrf = client.headers.pop("X-CSRF-Token")
    assert change(client).status_code == 403
    client.headers["X-CSRF-Token"] = csrf
    client.headers["X-Expected-Actor"] = "family"
    assert change(client).status_code == 409
    client.headers.pop("X-Expected-Actor")
    assert (
        client.post(
            PATH, content=b"x" * 17000, headers={"Content-Type": "application/json"}
        ).status_code
        == 413
    )
    response = client.post(
        PATH,
        content=b"private-invalid-json",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422
    assert "private-invalid-json" not in response.text


def test_reauthentication_attempts_are_rate_limited(client):
    sign_in(client)
    for _ in range(5):
        assert change(client, current_password="incorrect-current").status_code == 400
    assert change(client, current_password="incorrect-current").status_code == 429


def test_unicode_and_spaces_are_not_silently_truncated_or_trimmed(client):
    sign_in(client)
    password = "  Synthetic café passphrase 2026  "
    assert change(client, new_password=password).status_code == 200
    assert (
        client.post(
            "/api/login", json={"username": "participant", "password": password.strip()}
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/login", json={"username": "participant", "password": password}
        ).status_code
        == 200
    )


def test_concurrent_changes_allow_only_one_commit(client, database):
    with database() as db:
        if db.bind.dialect.name != "postgresql":
            pytest.skip("Requires PostgreSQL account row locks")
    sign_in(client)
    other = sign_in(TestClient(app))
    barrier = threading.Barrier(2)

    def attempt(account):
        barrier.wait(timeout=10)
        return change(account).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(attempt, account) for account in (client, other)]
        assert sorted(f.result(timeout=20) for f in futures) == [200, 401]
