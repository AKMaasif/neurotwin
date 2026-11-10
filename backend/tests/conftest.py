import pytest
from fastapi.testclient import TestClient

from app.main import create_app


DEMO_PASSWORD = "test-demo-password-123"
USERNAMES = {"demo-fatima": "fatima", "demo-yousef": "yousef", "demo-mariam": "mariam", "demo-omar": "omar",
             "demo-dr-layla": "dr.layla"}


@pytest.fixture(autouse=True)
def _fresh_rate_limits():
    from app import auth
    auth.login_attempts._seen.clear()
    auth.password_attempts._seen.clear()
    yield


@pytest.fixture()
def app(tmp_path):
    return create_app(database_url=f"sqlite:///{tmp_path / 'test.db'}", seed_demo=True, serve_frontend=False,
                      demo_password=DEMO_PASSWORD)


@pytest.fixture()
def client(app):
    return TestClient(app)


REAL_PASSWORD = "a real account phrase 1"


def make_user(app, user_id: str, username: str, role: str = "participant", password: str = REAL_PASSWORD) -> None:
    """A non-demo account, for testing what demo accounts are not allowed to do."""
    from app.models import User
    from app.security import hash_password
    with app.state.db.SessionLocal() as db:
        db.add(User(id=user_id, display_name=username.title(), role=role, language="en", is_demo=False,
                    username=username, password_hash=hash_password(password)))
        db.commit()


def sign_in(client, username: str, password: str = DEMO_PASSWORD) -> dict:
    """Sign in and return the headers that act as that person: their session cookie and CSRF token. The client's
    own cookie jar is cleared, so tests can act as several people in turn without one session replacing another."""
    r = client.post("/api/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    token = r.cookies.get("nt_session")
    client.cookies.clear()
    return {"Cookie": f"nt_session={token}", "X-CSRF-Token": r.json()["csrf"]}


@pytest.fixture()
def login(client):
    def _login(user_id: str) -> dict:
        return sign_in(client, USERNAMES[user_id])
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
