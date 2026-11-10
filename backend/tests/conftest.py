import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture()
def app(tmp_path):
    return create_app(database_url=f"sqlite:///{tmp_path / 'test.db'}", secret="test-secret", seed_demo=True,
                      serve_frontend=False)


@pytest.fixture()
def client(app):
    return TestClient(app)


@pytest.fixture()
def login(client):
    def _login(user_id: str) -> dict:
        r = client.post("/api/auth/demo-login", json={"user_id": user_id})
        assert r.status_code == 200, r.text
        return {"Authorization": f"Bearer {r.json()['token']}"}
    return _login


@pytest.fixture()
def yousef(login, client):
    """A participant with no consent and no sharing yet."""
    return login("demo-yousef")


def consent(client, headers, granted=True, scope="participation"):
    r = client.post("/api/consents", json={"scope": scope, "granted": granted}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def run_reaction(client, headers, *, status="completed", rt=500, valid=5, early=0, assisted=False, unwell=None,
                 interruptions=0):
    s = client.post("/api/sessions", json={"protocol_code": "reaction_time", "protocol_version": "0.1",
                                           "assisted": assisted, "unwell_today": unwell}, headers=headers)
    assert s.status_code == 200, s.text
    obs = [{"measure": "rt_median_ms", "kind": "observed", "value_num": rt, "unit": "ms"},
           {"measure": "valid_trials", "kind": "observed", "value_num": valid, "unit": "count"},
           {"measure": "anticipations", "kind": "observed", "value_num": early, "unit": "count"}]
    return client.post(f"/api/sessions/{s.json()['id']}/complete",
                       json={"status": status, "interruptions": interruptions, "observations": obs}, headers=headers)
