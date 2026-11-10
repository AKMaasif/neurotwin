"""Family messages: preview before send, who may write, links refused, the person's control."""
from conftest import USERNAMES


def sign_in(client, uid):
    r = client.post("/api/auth/demo-enter", json={"username": USERNAMES[uid]})
    assert r.status_code == 200
    return {"X-CSRF-Token": r.json()["csrf"]}


def draft(client, h, text="Thinking of you. See you Friday.", pid="demo-fatima"):
    return client.post("/api/family/messages", json={"participant_id": pid, "text": text}, headers=h)


def test_draft_is_not_delivered_until_sent(client):
    h = sign_in(client, "demo-mariam")
    d = draft(client, h)
    assert d.status_code == 200 and d.json()["status"] == "draft"
    sign_in(client, "demo-fatima")
    assert client.get("/api/messages").json() == []
    h = sign_in(client, "demo-mariam")
    assert client.post(f"/api/family/messages/{d.json()['id']}/send", headers=h).json()["status"] == "sent"
    sign_in(client, "demo-fatima")
    got = client.get("/api/messages").json()
    assert len(got) == 1 and got[0]["text"].startswith("Thinking") and got[0]["read"] is False


def test_new_draft_replaces_old_unsent_one(client):
    h = sign_in(client, "demo-mariam")
    a = draft(client, h, "First").json()
    b = draft(client, h, "Second").json()
    assert client.post(f"/api/family/messages/{a['id']}/send", headers=h).status_code == 409
    assert client.post(f"/api/family/messages/{b['id']}/send", headers=h).status_code == 200


def test_discard(client):
    h = sign_in(client, "demo-mariam")
    d = draft(client, h).json()
    assert client.post(f"/api/family/messages/{d['id']}/discard", headers=h).json()["status"] == "discarded"
    assert client.post(f"/api/family/messages/{d['id']}/send", headers=h).status_code == 409


def test_only_authorised_family_can_write(client):
    for who in ("demo-fatima", "demo-dr-layla", "demo-yousef"):
        assert draft(client, sign_in(client, who)).status_code == 404
    # Omar is family but has no grant from Fatima in the demo data, or none to Yousef
    h = sign_in(client, "demo-mariam")
    assert draft(client, h, pid="demo-yousef").status_code == 404


def test_text_rules(client):
    h = sign_in(client, "demo-mariam")
    assert draft(client, h, "   ").status_code == 422
    assert draft(client, h, "x" * 301).status_code == 422
    for bad in ("see https://example.com", "visit www.example.org", "go to bit.ly now", "mail me at evil.com"):
        assert draft(client, h, bad).status_code == 422, bad
    ok = draft(client, h, "Hello‮  there   friend").json()
    assert ok["text"] == "Hello there friend"


def test_grant_checked_again_at_send(client):
    h = sign_in(client, "demo-mariam")
    d = draft(client, h).json()
    hf = sign_in(client, "demo-fatima")
    grants = client.get("/api/grants", headers=hf).json()
    mine = next(g for g in grants if g["grantee"]["id"] == "demo-mariam" and g["active"])
    assert client.post(f"/api/grants/{mine['id']}/revoke", headers=hf).status_code == 200
    h = sign_in(client, "demo-mariam")
    assert client.post(f"/api/family/messages/{d['id']}/send", headers=h).status_code == 404


def test_daily_limit(client):
    h = sign_in(client, "demo-mariam")
    for i in range(5):
        d = draft(client, h, f"Note {i}").json()
        assert client.post(f"/api/family/messages/{d['id']}/send", headers=h).status_code == 200
    d = draft(client, h, "One more").json()
    assert client.post(f"/api/family/messages/{d['id']}/send", headers=h).status_code == 429


def test_person_can_read_and_remove_from_view(client, app):
    h = sign_in(client, "demo-mariam")
    d = draft(client, h).json()
    client.post(f"/api/family/messages/{d['id']}/send", headers=h)
    hf = sign_in(client, "demo-fatima")
    assert client.post(f"/api/messages/{d['id']}/read", headers=hf).status_code == 200
    assert client.get("/api/messages").json()[0]["read"] is True
    assert client.post(f"/api/messages/{d['id']}/hide", headers=hf).status_code == 200
    assert client.get("/api/messages").json() == []
    from app.models import FamilyMessage
    with app.state.db.SessionLocal() as db:
        assert db.get(FamilyMessage, d["id"]).text            # removed from view, not erased
    hy = sign_in(client, "demo-yousef")
    assert client.post(f"/api/messages/{d['id']}/read", headers=hy).status_code == 404


def test_clinician_has_no_route_and_audit_has_no_text(client, app):
    h = sign_in(client, "demo-mariam")
    d = draft(client, h, "Private words here").json()
    client.post(f"/api/family/messages/{d['id']}/send", headers=h)
    sign_in(client, "demo-dr-layla")
    assert client.get("/api/messages").status_code == 404
    from app.models import AuditEvent
    with app.state.db.SessionLocal() as db:
        rows = db.query(AuditEvent).filter(AuditEvent.action.like("message.%")).all()
        assert rows and all("Private" not in (r.target or "") for r in rows)
