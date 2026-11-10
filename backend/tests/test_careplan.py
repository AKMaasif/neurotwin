"""Care plan: who may write it, what a person sees, and that silence is never counted."""
from datetime import date, datetime, timezone

from conftest import DEMO_PASSWORD, USERNAMES


def sign_in(client, uid):
    r = client.post("/api/auth/demo-enter", json={"username": USERNAMES[uid]})
    assert r.status_code == 200
    return {"X-CSRF-Token": r.json()["csrf"]}


def clin(client):
    """Dr. Layla signed in, with the two seeded demo routines stopped so each test starts from an empty plan."""
    h = sign_in(client, "demo-dr-layla")
    for i in client.get("/api/participants/demo-fatima/care-plan").json():
        if i["status"] == "active":
            client.post(f"/api/care-plan/{i['id']}/stop", json={}, headers=h)
    return h


def test_seeded_demo_plan_is_visible_to_the_participant(client):
    sign_in(client, "demo-fatima")
    items = client.get("/api/care-plan/today").json()["items"]
    assert any(i["day_part"] == "morning" for i in items) and all(i["written_by"] == "Dr. Layla" for i in items)


def today():
    return datetime.now(timezone.utc).date().isoformat()


def add(client, h, **kw):
    body = {"text_en": "Walk for ten minutes after breakfast", "day_part": "morning", "weekdays": [], **kw}
    return client.post("/api/participants/demo-fatima/care-plan", json=body, headers=h)


def test_clinician_adds_and_participant_sees(client):
    h = clin(client)
    r = add(client, h, text_ar="امشِ عشر دقائق بعد الإفطار")
    assert r.status_code == 200 and r.json()["written_by"]
    h2 = sign_in(client, "demo-fatima")
    got = client.get("/api/care-plan/today").json()
    assert got["day"] == today() and len(got["items"]) == 1
    assert got["items"][0]["reply"] is None and got["items"][0]["text_ar"]


def test_text_required_and_validated(client):
    h = clin(client)
    assert add(client, h, text_en="  ", text_ar=None).status_code == 422
    assert add(client, h, day_part="midnight").status_code == 422
    assert add(client, h, weekdays=[9]).status_code == 422


def test_only_clinicians_with_a_grant_write(client):
    h = sign_in(client, "demo-fatima")
    assert add(client, h).status_code == 404            # participants cannot write their own plan
    h = sign_in(client, "demo-mariam")
    assert add(client, h).status_code == 404            # family cannot either
    h = sign_in(client, "demo-dr-layla")
    other = client.post("/api/participants/demo-yousef/care-plan", json={"text_en": "x"}, headers=h)
    assert other.status_code in (200, 404)              # allowed only if a clinical_review grant exists


def test_reply_and_silence(client):
    h = clin(client)
    item = add(client, h).json()
    h2 = sign_in(client, "demo-fatima")
    assert client.post(f"/api/care-plan/{item['id']}/reply", json={"reply": "done"}, headers=h2).status_code == 200
    assert client.get("/api/care-plan/today").json()["items"][0]["reply"] == "done"
    client.post(f"/api/care-plan/{item['id']}/reply", json={"reply": "not_today"}, headers=h2)
    assert client.get("/api/care-plan/today").json()["items"][0]["reply"] == "not_today"   # latest counts
    h = clin(client)
    view = client.get("/api/participants/demo-fatima/care-plan").json()[0]
    assert len(view["marked"]) == 1 and view["marked"][0]["reply"] == "not_today"
    assert "missed" not in str(view) and "rate" not in view


def test_unanswered_is_not_stored(client, app):
    h = clin(client)
    add(client, h)
    sign_in(client, "demo-fatima")
    client.get("/api/care-plan/today")
    from app.models import CarePlanReply
    with app.state.db.SessionLocal() as db:
        assert db.query(CarePlanReply).count() == 0


def test_stopped_item_leaves_the_person_view_but_stays_recorded(client):
    h = clin(client)
    item = add(client, h).json()
    assert client.post(f"/api/care-plan/{item['id']}/stop", json={"note": "Replaced"}, headers=h).status_code == 200
    assert client.post(f"/api/care-plan/{item['id']}/stop", json={}, headers=h).status_code == 409
    assert client.get("/api/participants/demo-fatima/care-plan").json()[0]["status"] == "stopped"
    sign_in(client, "demo-fatima")
    assert client.get("/api/care-plan/today").json()["items"] == []


def test_weekday_filter_and_day_limits(client):
    h = clin(client)
    wd = datetime.now(timezone.utc).date().weekday()
    add(client, h, weekdays=[(wd + 1) % 7])
    sign_in(client, "demo-fatima")
    assert client.get("/api/care-plan/today").json()["items"] == []
    assert client.get("/api/care-plan/today?day=2020-01-01").status_code == 422
    assert client.get("/api/care-plan/today?day=nonsense").status_code == 422


def test_cannot_reply_to_someone_elses_item(client):
    h = clin(client)
    item = add(client, h).json()
    h2 = sign_in(client, "demo-yousef")
    assert client.post(f"/api/care-plan/{item['id']}/reply", json={"reply": "done"}, headers=h2).status_code == 404


def test_audit_has_no_text(client, app):
    h = clin(client)
    add(client, h, text_en="Secret routine words")
    from app.models import AuditEvent
    with app.state.db.SessionLocal() as db:
        rows = db.query(AuditEvent).filter(AuditEvent.action.like("careplan.%")).all()
        assert rows and all("Secret" not in (r.target or "") for r in rows)


def test_active_limit(client):
    h = clin(client)
    for i in range(12):
        assert add(client, h, text_en=f"Routine {i}").status_code == 200
    assert add(client, h, text_en="One more").status_code == 409
