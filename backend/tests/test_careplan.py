"""Care plan: who may write it, acceptance before tasks, the person's day, and that silence is never counted."""
from datetime import timedelta

from conftest import USERNAMES


def sign_in(client, uid):
    r = client.post("/api/auth/demo-enter", json={"username": USERNAMES[uid]})
    assert r.status_code == 200
    return {"X-CSRF-Token": r.json()["csrf"]}


def view(client):
    return client.get("/api/participants/demo-fatima/care-plan").json()


def clin(client):
    """Dr. Layla signed in, with the seeded demo routines stopped so each test starts from an empty plan."""
    h = sign_in(client, "demo-dr-layla")
    for p in view(client)["plans"]:
        for i in p["items"]:
            if i["status"] == "active":
                client.post(f"/api/care-plan/{i['id']}/stop", json={}, headers=h)
    return h


def today(app, uid="demo-fatima"):
    from app.models import User
    from app import careplan as CP
    with app.state.db.SessionLocal() as db:
        return CP.local_today(db, db.get(User, uid))


def add(client, h, **kw):
    body = {"text_en": "Walk for ten minutes after breakfast", "day_part": "morning", "weekdays": [], **kw}
    return client.post("/api/participants/demo-fatima/care-plan", json=body, headers=h)


def send(client, h):
    pid = view(client)["draft_id"]
    return client.post(f"/api/care-plans/{pid}/send", headers=h)


def accepted(client, h, **kw):
    """Add one routine, send, and have the person accept. Returns (clinician headers, person headers, item)."""
    item = add(client, h, **kw).json()
    assert send(client, h).status_code == 200
    h2 = sign_in(client, "demo-fatima")
    plan = client.get("/api/care-plan/awaiting").json()[0]
    assert client.post(f"/api/care-plans/{plan['id']}/respond", json={"response": "accept"}, headers=h2).status_code == 200
    return h, h2, item


def test_seeded_demo_plan_is_visible_to_the_participant(client):
    sign_in(client, "demo-fatima")
    items = client.get("/api/care-plan/today").json()["items"]
    assert any(i["day_part"] == "morning" for i in items) and all(i["written_by"] == "Dr. Layla" for i in items)


def test_a_new_routine_is_not_a_task_until_accepted(client):
    h = clin(client)
    r = add(client, h, text_ar="امشِ عشر دقائق بعد الإفطار")
    assert r.status_code == 200 and r.json()["written_by"]
    sign_in(client, "demo-fatima")
    assert client.get("/api/care-plan/today").json()["items"] == []        # draft: nothing yet
    h = sign_in(client, "demo-dr-layla")
    assert send(client, h).status_code == 200
    sign_in(client, "demo-fatima")
    assert client.get("/api/care-plan/today").json()["items"] == []        # sent but not accepted: still nothing
    waiting = client.get("/api/care-plan/awaiting").json()
    assert len(waiting) == 1 and waiting[0]["written_by"] == "Dr. Layla" and waiting[0]["items"][0]["text_ar"]


def test_accepting_makes_tasks_and_declining_does_not(client):
    h = clin(client)
    h, h2, _ = accepted(client, h)
    got = client.get("/api/care-plan/today").json()
    assert len(got["items"]) == 1 and got["items"][0]["reply"] is None
    h = clin(client)
    add(client, h, text_en="Drink a glass of water")
    send(client, h)
    h2 = sign_in(client, "demo-fatima")
    pid = client.get("/api/care-plan/awaiting").json()[0]["id"]
    assert client.post(f"/api/care-plans/{pid}/respond", json={"response": "decline", "note": "Too much"}, headers=h2).status_code == 200
    assert client.get("/api/care-plan/today").json()["items"] == []
    assert client.get("/api/care-plan/awaiting").json() == []
    assert client.post(f"/api/care-plans/{pid}/respond", json={"response": "accept"}, headers=h2).status_code == 409


def test_a_question_keeps_the_plan_waiting(client):
    h = clin(client)
    add(client, h)
    send(client, h)
    h2 = sign_in(client, "demo-fatima")
    pid = client.get("/api/care-plan/awaiting").json()[0]["id"]
    assert client.post(f"/api/care-plans/{pid}/respond", json={"response": "question"}, headers=h2).status_code == 422
    assert client.post(f"/api/care-plans/{pid}/respond", json={"response": "question", "note": "Is this safe with my knee?"}, headers=h2).status_code == 200
    assert client.get("/api/care-plan/awaiting").json()[0]["questions_asked"] == 1
    h = sign_in(client, "demo-dr-layla")
    plan = view(client)["plans"][0]
    assert plan["status"] == "sent" and plan["responses"][0]["note"].startswith("Is this safe")


def test_changes_are_a_new_version_the_old_one_keeps_running(client):
    h = clin(client)
    h, h2, _ = accepted(client, h)
    h = sign_in(client, "demo-dr-layla")
    add(client, h, text_en="Stretch gently", day_part="evening")
    sign_in(client, "demo-fatima")
    assert len(client.get("/api/care-plan/today").json()["items"]) == 1     # still version 1
    h = sign_in(client, "demo-dr-layla")
    send(client, h)
    h2 = sign_in(client, "demo-fatima")
    pid = client.get("/api/care-plan/awaiting").json()[0]["id"]
    client.post(f"/api/care-plans/{pid}/respond", json={"response": "accept"}, headers=h2)
    assert len(client.get("/api/care-plan/today").json()["items"]) == 2     # both routines under version 2
    h = sign_in(client, "demo-dr-layla")
    statuses = [p["status"] for p in view(client)["plans"] if p["items"]]
    assert "superseded" in statuses and "accepted" in statuses


def test_a_sent_plan_must_be_recalled_before_it_is_edited(client):
    h = clin(client)
    add(client, h)
    send(client, h)
    assert add(client, h, text_en="Another").status_code == 409
    pid = view(client)["plans"][0]["id"]
    assert client.post(f"/api/care-plans/{pid}/recall", headers=h).status_code == 200
    assert add(client, h, text_en="Another").status_code == 200
    sign_in(client, "demo-fatima")
    assert client.get("/api/care-plan/awaiting").json() == []


def test_unknown_plan_cannot_be_sent(client):
    h = clin(client)
    assert client.post("/api/care-plans/9999/send", headers=h).status_code == 404


def test_structured_fields_are_validated_and_units_never_guessed(client):
    h = clin(client)
    assert add(client, h, quantity=5).status_code == 422                       # a number needs its unit
    assert add(client, h, unit="mg").status_code == 422                        # and the reverse
    assert add(client, h, time_hhmm="25:00").status_code == 422
    assert add(client, h, time_hhmm="08:00", window_start="07:00", window_end="09:00").status_code == 422
    assert add(client, h, window_start="09:00", window_end="07:00").status_code == 422
    assert add(client, h, start_date="2026-12-01", end_date="2026-11-01").status_code == 422
    assert add(client, h, quantity=0, unit="min").status_code == 422
    ok = add(client, h, title="Walk", quantity=10, unit="minutes", time_hhmm="08:30", precautions="Stop if dizzy")
    assert ok.status_code == 200 and ok.json()["quantity"] == 10 and ok.json()["unit"] == "minutes"


def test_text_required_and_validated(client):
    h = clin(client)
    assert add(client, h, text_en="  ", text_ar=None).status_code == 422
    assert add(client, h, day_part="midnight").status_code == 422
    assert add(client, h, weekdays=[9]).status_code == 422


def test_only_clinicians_with_a_grant_write(client):
    h = sign_in(client, "demo-fatima")
    assert add(client, h).status_code == 404
    h = sign_in(client, "demo-mariam")
    assert add(client, h).status_code == 404
    h = sign_in(client, "demo-dr-layla")
    other = client.post("/api/participants/demo-yousef/care-plan", json={"text_en": "x"}, headers=h)
    assert other.status_code in (200, 404)


def test_only_the_named_person_can_answer_a_plan(client):
    h = clin(client)
    add(client, h)
    send(client, h)
    pid = view(client)["plans"][0]["id"]
    h3 = sign_in(client, "demo-yousef")
    assert client.post(f"/api/care-plans/{pid}/respond", json={"response": "accept"}, headers=h3).status_code == 404
    h2 = sign_in(client, "demo-mariam")
    assert client.post(f"/api/care-plans/{pid}/respond", json={"response": "accept"}, headers=h2).status_code == 404
    h = sign_in(client, "demo-dr-layla")
    assert client.post(f"/api/care-plans/{pid}/respond", json={"response": "accept"}, headers=h).status_code == 404


def test_reply_and_silence(client):
    h = clin(client)
    h, h2, item = accepted(client, h)
    h2 = sign_in(client, "demo-fatima")
    items = client.get("/api/care-plan/today").json()["items"]
    iid = items[0]["id"]
    assert client.post(f"/api/care-plan/{iid}/reply", json={"reply": "done"}, headers=h2).status_code == 200
    assert client.get("/api/care-plan/today").json()["items"][0]["reply"] == "done"
    client.post(f"/api/care-plan/{iid}/reply", json={"reply": "not_today"}, headers=h2)
    assert client.get("/api/care-plan/today").json()["items"][0]["reply"] == "not_today"
    sign_in(client, "demo-dr-layla")
    plans = [p for p in view(client)["plans"] if p["status"] == "accepted"]
    marked = plans[0]["items"][0]["marked"]
    assert len(marked) == 1 and marked[0]["reply"] == "not_today"
    assert "missed" not in str(view(client)) and "rate" not in view(client)


def test_repeated_answers_and_retries_add_one_record(client, app):
    h = clin(client)
    h, h2, _ = accepted(client, h)
    iid = client.get("/api/care-plan/today").json()["items"][0]["id"]
    body = {"reply": "done", "idem_key": "retry-key-0001"}
    a = client.post(f"/api/care-plan/{iid}/reply", json=body, headers=h2).json()
    b = client.post(f"/api/care-plan/{iid}/reply", json=body, headers=h2).json()
    c = client.post(f"/api/care-plan/{iid}/reply", json={"reply": "done"}, headers=h2).json()
    assert a["duplicate"] is False and b["duplicate"] is True and c["duplicate"] is True
    assert client.post(f"/api/care-plan/{iid}/reply", json={"reply": "not_today", "idem_key": "retry-key-0001"}, headers=h2).status_code == 409
    from app.models import CarePlanReply
    with app.state.db.SessionLocal() as db:
        assert db.query(CarePlanReply).count() == 1


def test_snooze_moves_the_reminder_not_the_instruction(client):
    h = clin(client)
    h, h2, _ = accepted(client, h)
    iid = client.get("/api/care-plan/today").json()["items"][0]["id"]
    assert client.post(f"/api/care-plan/{iid}/reply", json={"reply": "snooze", "snooze_minutes": 7}, headers=h2).status_code == 422
    assert client.post(f"/api/care-plan/{iid}/reply", json={"reply": "snooze", "snooze_minutes": 30}, headers=h2).status_code == 200
    row = client.get("/api/care-plan/today").json()["items"][0]
    assert row["snoozed_until"] and row["reply"] is None                      # still to do, not marked anything
    client.post(f"/api/care-plan/{iid}/reply", json={"reply": "done"}, headers=h2)
    assert client.get("/api/care-plan/today").json()["items"][0]["snoozed_until"] is None


def test_difficulty_is_kept_with_its_reason_and_is_not_a_missed_dose(client):
    h = clin(client)
    h, h2, _ = accepted(client, h)
    iid = client.get("/api/care-plan/today").json()["items"][0]["id"]
    assert client.post(f"/api/care-plan/{iid}/reply", json={"reply": "difficulty", "reason": "bogus"}, headers=h2).status_code == 422
    assert client.post(f"/api/care-plan/{iid}/reply", json={"reply": "difficulty", "reason": "too_tiring", "note": "Knee hurt"}, headers=h2).status_code == 200
    row = client.get("/api/care-plan/today").json()["items"][0]
    assert row["difficulty"] == "too_tiring" and row["reply"] is None
    sign_in(client, "demo-dr-layla")
    plan = next(p for p in view(client)["plans"] if p["status"] == "accepted")
    assert plan["items"][0]["difficulty"][0]["reason"] == "too_tiring"


def test_unanswered_is_not_stored(client, app):
    h = clin(client)
    accepted(client, h)
    client.get("/api/care-plan/today")
    from app.models import CarePlanReply
    with app.state.db.SessionLocal() as db:
        assert db.query(CarePlanReply).count() == 0


def test_stopped_item_leaves_the_person_view_but_stays_recorded(client):
    h = clin(client)
    h, h2, item = accepted(client, h)
    iid = client.get("/api/care-plan/today").json()["items"][0]["id"]
    h = sign_in(client, "demo-dr-layla")
    assert client.post(f"/api/care-plan/{iid}/stop", json={"note": "Replaced"}, headers=h).status_code == 200
    assert client.post(f"/api/care-plan/{iid}/stop", json={}, headers=h).status_code == 409
    sign_in(client, "demo-fatima")
    assert client.get("/api/care-plan/today").json()["items"] == []
    sign_in(client, "demo-dr-layla")
    assert any(i["status"] == "stopped" for p in view(client)["plans"] for i in p["items"])


def test_weekday_dates_and_day_limits(client, app):
    h = clin(client)
    d = today(app)
    add(client, h, weekdays=[(d.weekday() + 1) % 7])
    add(client, h, text_en="Future start", start_date=(d + timedelta(days=3)).isoformat())
    add(client, h, text_en="Already ended", end_date=(d - timedelta(days=1)).isoformat())
    send(client, h)
    h2 = sign_in(client, "demo-fatima")
    client.post(f"/api/care-plans/{client.get('/api/care-plan/awaiting').json()[0]['id']}/respond", json={"response": "accept"}, headers=h2)
    assert client.get("/api/care-plan/today").json()["items"] == []
    assert client.get("/api/care-plan/today?day=2020-01-01").status_code == 422
    assert client.get("/api/care-plan/today?day=nonsense").status_code == 422


def test_today_is_ordered_by_time(client):
    h = clin(client)
    add(client, h, text_en="Late", time_hhmm="20:00", day_part="evening")
    add(client, h, text_en="Early", time_hhmm="07:15", day_part="morning")
    send(client, h)
    h2 = sign_in(client, "demo-fatima")
    client.post(f"/api/care-plans/{client.get('/api/care-plan/awaiting').json()[0]['id']}/respond", json={"response": "accept"}, headers=h2)
    assert [i["text_en"] for i in client.get("/api/care-plan/today").json()["items"]] == ["Early", "Late"]


def test_timezone_decides_the_day(client, app):
    h2 = sign_in(client, "demo-fatima")
    assert client.get("/api/me/preferences").json()["timezone"] == "Asia/Dubai"
    assert client.put("/api/me/preferences", json={"timezone": "Not/AZone"}, headers=h2).status_code == 422
    assert client.put("/api/me/preferences", json={"timezone": "Pacific/Kiritimati"}, headers=h2).status_code == 200
    from datetime import datetime
    from zoneinfo import ZoneInfo
    assert client.get("/api/care-plan/today").json()["day"] == datetime.now(ZoneInfo("Pacific/Kiritimati")).date().isoformat()
    assert client.get("/api/care-plan/today").json()["timezone"] == "Pacific/Kiritimati"


def test_cannot_reply_to_someone_elses_item(client):
    h = clin(client)
    h, h2, _ = accepted(client, h)
    iid = client.get("/api/care-plan/today").json()["items"][0]["id"]
    h3 = sign_in(client, "demo-yousef")
    assert client.post(f"/api/care-plan/{iid}/reply", json={"reply": "done"}, headers=h3).status_code == 404


def test_cannot_reply_to_an_unaccepted_routine(client, app):
    h = clin(client)
    item = add(client, h).json()
    h2 = sign_in(client, "demo-fatima")
    assert client.post(f"/api/care-plan/{item['id']}/reply", json={"reply": "done"}, headers=h2).status_code == 404


def test_audit_has_no_text(client, app):
    h = clin(client)
    add(client, h, text_en="Secret routine words", precautions="Secret precaution")
    send(client, h)
    from app.models import AuditEvent
    with app.state.db.SessionLocal() as db:
        rows = db.query(AuditEvent).filter(AuditEvent.action.like("careplan.%")).all()
        assert rows and all("Secret" not in (r.target or "") for r in rows)


def test_active_limit(client):
    h = clin(client)
    for i in range(12):
        assert add(client, h, text_en=f"Routine {i}").status_code == 200
    assert add(client, h, text_en="One more").status_code == 409
