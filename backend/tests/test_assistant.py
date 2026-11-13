"""Text assistant: allowlisted tools, confirmation before any change, no guessing, emergency first, nothing logged from the person's words."""
import pytest

from test_careplan import add, clin, send, sign_in


def two_tasks(client):
    h = clin(client)
    add(client, h, text_en="Walk for ten minutes", day_part="morning", time_hhmm="08:00")
    add(client, h, text_en="Drink a glass of water", day_part="afternoon", time_hhmm="13:00")
    send(client, h)
    h2 = sign_in(client, "demo-fatima")
    pid = client.get("/api/care-plan/awaiting").json()[0]["id"]
    client.post(f"/api/care-plans/{pid}/respond", json={"response": "accept"}, headers=h2)
    return h2


def say(client, h, text):
    return client.post("/api/assistant/message", json={"text": text}, headers=h).json()


def test_reads_and_navigation_run_at_once(client):
    h = two_tasks(client)
    r = say(client, h, "What do I need to do today?")
    assert r["tool"] == "read_today" and len(r["items"]) == 2 and r["needs_confirmation"] is False
    assert say(client, h, "open my messages")["navigate"] == "messages"
    assert say(client, h, "start the daily check-in")["navigate"] == "checkin"
    assert say(client, h, "ماذا علي اليوم")["tool"] == "read_today"


def test_a_change_waits_for_confirmation_and_runs_once(client):
    h = two_tasks(client)
    r = say(client, h, "I finished the walk")
    assert r["tool"] == "mark_done" and r["needs_confirmation"] and "walk" in r["item"]["text_en"].lower()
    assert client.get("/api/care-plan/today").json()["items"][0]["reply"] is None      # nothing recorded yet
    c = client.post("/api/assistant/confirm", json={"confirmation_id": r["confirmation_id"]}, headers=h).json()
    assert c["ok"] and not c["duplicate"]
    again = client.post("/api/assistant/confirm", json={"confirmation_id": r["confirmation_id"]}, headers=h).json()
    assert again["duplicate"] is True
    items = client.get("/api/care-plan/today").json()["items"]
    assert [i["reply"] for i in items] == ["done", None]
    from app.models import CarePlanReply
    assert client.get("/api/care-plan/history").json()["days"][0]["entries"][0]["reply"] == "done"


def test_not_today_and_snooze(client):
    h = two_tasks(client)
    r = say(client, h, "skip the water today")
    assert r["tool"] == "mark_not_today"
    client.post("/api/assistant/confirm", json={"confirmation_id": r["confirmation_id"]}, headers=h)
    r = say(client, h, "remind me about the walk in 30 minutes")
    assert r["tool"] == "snooze" and r["minutes"] == 30
    client.post("/api/assistant/confirm", json={"confirmation_id": r["confirmation_id"]}, headers=h)
    items = {i["text_en"]: i for i in client.get("/api/care-plan/today").json()["items"]}
    assert items["Drink a glass of water"]["reply"] == "not_today" and items["Walk for ten minutes"]["snoozed_until"]
    assert say(client, h, "remind me about the walk in 7 minutes")["reason"] == "snooze_minutes"


def test_ambiguity_asks_which_and_never_guesses(client):
    h = two_tasks(client)
    r = say(client, h, "I am done")
    assert r["understood"] is False and r["reason"] == "which" and len(r["choices"]) == 2
    r = say(client, h, "mark something as done")
    assert r["understood"] is False
    from app.models import CarePlanReply
    assert client.get("/api/care-plan/history").json()["days"] == []


def test_unknown_and_empty_are_not_understood(client):
    h = two_tasks(client)
    assert say(client, h, "tell me a joke")["reason"] == "not_understood"
    assert say(client, h, "   ")["reason"] == "empty"
    assert say(client, h, "DROP TABLE users; http://evil.example")["understood"] is False


@pytest.mark.parametrize("text", ["I need help", "emergency", "I fell down", "أحتاج مساعدة", "طوارئ"])
def test_help_words_open_the_urgent_screen_and_nothing_else(client, text):
    h = two_tasks(client)
    r = say(client, h, text)
    assert r["tool"] == "emergency" and r["navigate"] == "urgent" and r["needs_confirmation"] is False
    assert "call" not in str(r).lower() and "coming" not in str(r).lower()


def test_confirmation_is_private_and_expires(client, app):
    h = two_tasks(client)
    r = say(client, h, "I finished the walk")
    h3 = sign_in(client, "demo-yousef")
    assert client.post("/api/assistant/confirm", json={"confirmation_id": r["confirmation_id"]}, headers=h3).status_code == 404
    h = sign_in(client, "demo-fatima")
    from datetime import timedelta
    from app.models import AssistantAction, now
    with app.state.db.SessionLocal() as db:
        db.get(AssistantAction, r["confirmation_id"]).expires_at = now() - timedelta(minutes=1)
        db.commit()
    assert client.post("/api/assistant/confirm", json={"confirmation_id": r["confirmation_id"]}, headers=h).status_code == 410
    assert client.get("/api/care-plan/today").json()["items"][0]["reply"] is None


def test_clinician_and_family_cannot_use_it(client):
    two_tasks(client)
    for who in ("demo-dr-layla", "demo-mariam"):
        h = sign_in(client, who)
        assert client.post("/api/assistant/message", json={"text": "help"}, headers=h).status_code == 404


def test_audit_records_tool_outcomes_without_words(client, app):
    h = two_tasks(client)
    r = say(client, h, "I finished the walk, my secret sentence")
    client.post("/api/assistant/confirm", json={"confirmation_id": r["confirmation_id"]}, headers=h)
    say(client, h, "tell me a secret joke")
    from app.models import AuditEvent
    with app.state.db.SessionLocal() as db:
        rows = [a.action for a in db.query(AuditEvent).filter(AuditEvent.action.like("assistant.%"))]
        text = str([(a.action, a.target) for a in db.query(AuditEvent).all()])
    assert "assistant.mark_done.attempted" in rows and "assistant.mark_done.succeeded" in rows and "assistant.not_understood" in rows
    assert "secret" not in text


def test_arabic_word_forms_meet_and_are_still_confirmed(client):
    h = clin(client)
    add(client, h, text_en=None, text_ar="امشِ عشر دقائق بعد الإفطار", day_part="morning")
    add(client, h, text_en=None, text_ar="اشرب كوب ماء", day_part="afternoon")
    send(client, h)
    h2 = sign_in(client, "demo-fatima")
    pid = client.get("/api/care-plan/awaiting").json()[0]["id"]
    client.post(f"/api/care-plans/{pid}/respond", json={"response": "accept"}, headers=h2)
    r = say(client, h2, "أنهيت المشي")
    assert r["tool"] == "mark_done" and r["needs_confirmation"] and "امش" in r["item"]["text_ar"]
    assert client.get("/api/care-plan/today").json()["items"][0]["reply"] is None
