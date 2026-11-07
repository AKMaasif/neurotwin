import datetime as dt
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from app.db import Grant, LoginSession
from app.main import app
from tests.conftest import sign_in


def test_session_summary_does_not_expose_credentials(client):
    sign_in(client)
    other = sign_in(TestClient(app))
    result = client.get("/api/account/sessions")
    assert result.status_code == 200
    assert result.json()["other_active_sessions"] == 1
    assert set(result.json()) == {"other_active_sessions", "current_expires"}
    assert other.cookies["nt_session"] not in result.text
    assert "csrf" not in result.text
    assert "token" not in result.text


def test_revoke_others_preserves_current_and_other_accounts(client):
    sign_in(client)
    other = sign_in(TestClient(app))
    family = sign_in(TestClient(app), "family")
    response = client.post("/api/account/sessions/revoke-others")
    assert response.status_code == 200
    assert response.json()["revoked"] == 1
    assert other.get("/api/session").status_code == 401
    assert client.get("/api/session").status_code == 200
    assert family.get("/api/session").status_code == 200
    assert client.post("/api/account/sessions/revoke-others").json()["revoked"] == 0


def test_auth_csrf_and_expected_actor_required(client):
    assert client.get("/api/account/sessions").status_code == 401
    sign_in(client)
    csrf = client.headers.pop("X-CSRF-Token")
    assert client.post("/api/account/sessions/revoke-others").status_code == 403
    client.headers["X-CSRF-Token"] = csrf
    client.headers["X-Expected-Actor"] = "family"
    assert client.post("/api/account/sessions/revoke-others").status_code == 409


def test_expired_sessions_are_not_counted_or_treated_as_active_revocations(
    client, database
):
    sign_in(client)
    with database() as db:
        db.add(
            LoginSession(
                token_hash="a" * 64,
                user_id="participant",
                csrf="expired-csrf",
                expires=(
                    dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1)
                ).isoformat(),
            )
        )
        db.commit()
    assert client.get("/api/account/sessions").json()["other_active_sessions"] == 0
    assert client.post("/api/account/sessions/revoke-others").json()["revoked"] == 0


def test_new_signin_is_possible_after_revocation(client):
    sign_in(client)
    other = sign_in(TestClient(app))
    assert client.post("/api/account/sessions/revoke-others").status_code == 200
    assert other.get("/api/session").status_code == 401
    sign_in(other)
    assert other.get("/api/session").status_code == 200
    assert client.get("/api/account/sessions").json()["other_active_sessions"] == 1


def test_session_security_does_not_require_patient_access(client, database):
    sign_in(client)
    with database() as db:
        db.query(Grant).filter_by(user_id="participant").update({"active": False})
        db.commit()
    assert client.get("/api/patients").json() == []
    assert client.get("/api/account/sessions").status_code == 200
    assert client.post("/api/account/sessions/revoke-others").status_code == 200


def test_concurrent_revocations_preserve_one_valid_caller(client, database):
    with database() as db:
        if db.bind.dialect.name != "postgresql":
            pytest.skip("Requires PostgreSQL account row locks")
    sign_in(client)
    other = sign_in(TestClient(app))
    barrier = threading.Barrier(2)

    def revoke(account):
        barrier.wait(timeout=10)
        return account.post("/api/account/sessions/revoke-others").status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(revoke, account) for account in (client, other)]
        assert sorted(f.result(timeout=20) for f in futures) == [200, 401]
    with database() as db:
        assert db.query(LoginSession).filter_by(user_id="participant").count() == 1
