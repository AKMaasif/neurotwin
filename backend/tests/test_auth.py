from datetime import timedelta

from app.models import LoginSession
from app.security import hash_password, password_matches, utcnow
from conftest import DEMO_PASSWORD, REAL_PASSWORD, make_user, sign_in


def test_password_hash_round_trip_and_format():
    h = hash_password("a long enough phrase")
    assert h.startswith("scrypt$") and "a long enough phrase" not in h
    assert password_matches("a long enough phrase", h)
    assert not password_matches("wrong phrase entirely", h)
    assert not password_matches("anything", None) and not password_matches("anything", "garbage")
    assert hash_password("same") != hash_password("same"), "salted"


def test_sign_in_sets_a_protected_cookie(client):
    r = client.post("/api/auth/login", json={"username": "Fatima", "password": DEMO_PASSWORD})
    assert r.status_code == 200 and r.json()["user"]["username"] == "fatima"
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie and "nt_session=" in cookie
    assert "password" not in r.text.lower()


def test_wrong_username_and_wrong_password_look_the_same(client):
    a = client.post("/api/auth/login", json={"username": "fatima", "password": "not the password at all"})
    b = client.post("/api/auth/login", json={"username": "nobody-here", "password": "not the password at all"})
    assert a.status_code == b.status_code == 401 and a.json() == b.json()


def test_repeated_failures_are_slowed_down(client):
    for _ in range(5):
        client.post("/api/auth/login", json={"username": "fatima", "password": "wrong password guess"})
    r = client.post("/api/auth/login", json={"username": "fatima", "password": DEMO_PASSWORD})
    assert r.status_code == 429


def test_changes_need_the_csrf_token(client):
    h = sign_in(client, "yousef")
    r = client.post("/api/consents", json={"scope": "participation", "granted": True}, headers={"Cookie": h["Cookie"]})
    assert r.status_code == 403
    r = client.post("/api/consents", json={"scope": "participation", "granted": True},
                    headers={**h, "X-CSRF-Token": "wrong"})
    assert r.status_code == 403
    assert client.post("/api/consents", json={"scope": "participation", "granted": True}, headers=h).status_code == 200
    assert client.get("/api/me", headers={"Cookie": h["Cookie"]}).status_code == 200, "reading needs no CSRF token"


def test_sign_out_ends_the_session(client):
    h = sign_in(client, "yousef")
    assert client.post("/api/auth/logout", headers=h).status_code == 200
    assert client.get("/api/me", headers=h).status_code == 401


def test_expired_session_is_refused(client, app):
    h = sign_in(client, "yousef")
    with app.state.db.SessionLocal() as db:
        for row in db.query(LoginSession).all():
            row.expires_at = utcnow() - timedelta(minutes=1)
        db.commit()
    assert client.get("/api/me", headers=h).status_code == 401


def test_session_endpoint_returns_user_and_csrf(client):
    h = sign_in(client, "dr.layla")
    r = client.get("/api/auth/session", headers={"Cookie": h["Cookie"]}).json()
    assert r["user"]["role"] == "clinician" and r["csrf"] == h["X-CSRF-Token"]


def test_password_change_rules_and_other_sessions_end(client, app):
    make_user(app, "u-sara", "sara")
    first = sign_in(client, "sara", REAL_PASSWORD)
    second = sign_in(client, "sara", REAL_PASSWORD)
    new = "a brand new long phrase"
    post = lambda cur, nxt: client.post("/api/account/password", json={"current_password": cur, "new_password": nxt},
                                        headers=first)
    assert post("wrong one entirely", new).status_code == 400
    assert post(REAL_PASSWORD, "short").status_code == 422
    assert post(REAL_PASSWORD, REAL_PASSWORD).status_code == 422
    ok = post(REAL_PASSWORD, new)
    assert ok.status_code == 200 and ok.json()["other_sessions_ended"] == 1
    assert client.get("/api/me", headers=first).status_code == 200
    assert client.get("/api/me", headers=second).status_code == 401
    assert client.post("/api/auth/login", json={"username": "sara", "password": REAL_PASSWORD}).status_code == 401
    client.cookies.clear()
    assert sign_in(client, "sara", new)


def test_revoke_other_sessions(client, app):
    make_user(app, "u-sara", "sara", role="family")
    first = sign_in(client, "sara", REAL_PASSWORD)
    second = sign_in(client, "sara", REAL_PASSWORD)
    assert client.get("/api/account/sessions", headers=first).json()["other_active_sessions"] == 1
    assert client.post("/api/account/sessions/revoke-others", headers=first).json()["ended"] == 1
    assert client.get("/api/me", headers=second).status_code == 401
    assert client.get("/api/me", headers=first).status_code == 200


def test_usernames_are_not_shown_to_other_people(client):
    h = sign_in(client, "fatima")
    grants = client.get("/api/grants", headers=h).json()
    assert grants and all("username" not in g["grantee"] for g in grants)


def test_account_events_are_audited_without_secrets(client, app):
    make_user(app, "u-sara", "sara")
    h = sign_in(client, "sara", REAL_PASSWORD)
    client.post("/api/account/password", json={"current_password": REAL_PASSWORD,
                                               "new_password": "another long phrase here"}, headers=h)
    trail = client.get("/api/participants/u-sara/audit", headers=h).json()
    assert {"auth.signed_in", "account.password_changed"} <= {a["action"] for a in trail}
    assert "another long phrase" not in str(trail) and REAL_PASSWORD not in str(trail)


# ---- One-click demo entry ------------------------------------------------------------------------------------

def test_demo_entry_needs_no_password(client):
    r = client.post("/api/auth/demo-enter", json={"username": "dr.layla"})
    assert r.status_code == 200 and r.json()["user"]["role"] == "clinician"
    assert "httponly" in r.headers["set-cookie"].lower()
    assert client.get("/api/clinician/participants").status_code == 200


def test_demo_entry_never_opens_a_real_account(client, app):
    make_user(app, "u-sara", "sara")
    assert client.post("/api/auth/demo-enter", json={"username": "sara"}).status_code == 404
    assert client.post("/api/auth/demo-enter", json={"username": "nobody"}).status_code == 404


def test_demo_entry_is_off_outside_demo_mode(tmp_path):
    from fastapi.testclient import TestClient
    from app.main import create_app
    url = f"sqlite:///{tmp_path / 'd.db'}"
    create_app(database_url=url, seed_demo=True, serve_frontend=False, demo_password=DEMO_PASSWORD)
    live = TestClient(create_app(database_url=url, seed_demo=False, serve_frontend=False))
    assert live.post("/api/auth/demo-enter", json={"username": "fatima"}).status_code == 404
    assert live.get("/api/demo-accounts").json() == []


def test_shared_demo_accounts_cannot_lock_each_other_out(client):
    h = sign_in(client, "omar")
    r = client.post("/api/account/password", json={"current_password": DEMO_PASSWORD,
                                                   "new_password": "a brand new long phrase"}, headers=h)
    assert r.status_code == 403
    assert client.post("/api/account/sessions/revoke-others", headers=h).status_code == 403
