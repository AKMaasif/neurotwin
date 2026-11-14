"""The assistant follows a conversation: it remembers what was just said, answers follow-ups, and still never changes anything without the
person's own yes. Memory is private, clearable and can be switched off. Rule-based understanding only; no model is involved."""
from datetime import timedelta

from test_careplan import sign_in
from test_assistant import say, two_tasks

WALK, WATER = "Walk for ten minutes", "Drink a glass of water"


def replies(client):
    return {i["text_en"]: i["reply"] for i in client.get("/api/care-plan/today").json()["items"]}


def test_yes_confirms_the_one_proposal_waiting(client):
    h = two_tasks(client)
    r = say(client, h, "I finished the walk")
    assert r["needs_confirmation"] and replies(client)[WALK] is None
    y = say(client, h, "yes")
    assert y["confirmed"] and y["via"] == "yes" and y["item"]["text_en"] == WALK
    assert replies(client)[WALK] == "done"
    assert say(client, h, "yes")["reason"] == "nothing_pending"                 # a second yes does nothing
    assert replies(client)[WATER] is None


def test_no_cancels_and_a_later_yes_cannot_revive_it(client):
    h = two_tasks(client)
    r = say(client, h, "I finished the walk")
    n = say(client, h, "no")
    assert n["cancelled"] and replies(client)[WALK] is None
    assert say(client, h, "yes")["reason"] == "nothing_pending"
    c = client.post("/api/assistant/confirm", json={"confirmation_id": r["confirmation_id"]}, headers=h).json()
    assert c["ok"] is False and replies(client)[WALK] is None                    # even tapping the old Yes does nothing


def test_it_means_what_we_were_just_talking_about(client):
    h = two_tasks(client)
    say(client, h, "tell me about the walk")
    r = say(client, h, "I did it")
    assert r["tool"] == "mark_done" and r["item"]["text_en"] == WALK and r["via"] == "context"
    say(client, h, "no")
    r = say(client, h, "actually, not today for it")
    assert r["tool"] == "mark_not_today" and r["item"]["text_en"] == WALK


def test_follow_up_with_a_new_item_repeats_the_last_request(client):
    h = two_tasks(client)
    say(client, h, "I finished the walk")
    say(client, h, "yes")
    r = say(client, h, "and the water?")
    assert r["tool"] == "mark_done" and r["item"]["text_en"] == WATER and r["needs_confirmation"]
    say(client, h, "yes")
    assert replies(client) == {WALK: "done", WATER: "done"}


def test_same_again_and_the_other_one(client):
    h = two_tasks(client)
    say(client, h, "skip the walk today")
    say(client, h, "yes")
    r = say(client, h, "the same for the other one")
    assert r["tool"] == "mark_not_today" and r["item"]["text_en"] == WATER


def test_which_question_is_answered_in_the_next_message(client):
    h = two_tasks(client)
    q = say(client, h, "I am done")
    assert q["reason"] == "which" and len(q["choices"]) == 2
    r = say(client, h, "the second one")
    assert r["tool"] == "mark_done" and r["item"]["text_en"] == WATER and r["via"] == "answer"
    say(client, h, "no")
    q = say(client, h, "I am done")
    r = say(client, h, "the walk")
    assert r["item"]["text_en"] == WALK


def test_a_missing_snooze_length_is_asked_then_answered(client):
    h = two_tasks(client)
    q = say(client, h, "remind me about the walk in 7 minutes")
    assert q["reason"] == "snooze_minutes"
    r = say(client, h, "an hour")
    assert r["tool"] == "snooze" and r["minutes"] == 60 and r["item"]["text_en"] == WALK
    say(client, h, "yes")
    assert client.get("/api/care-plan/today").json()["items"][0]["snoozed_until"]


def test_a_new_request_replaces_the_waiting_one(client):
    h = two_tasks(client)
    first = say(client, h, "I finished the walk")
    second = say(client, h, "I finished the water")
    assert say(client, h, "yes")["item"]["text_en"] == WATER
    assert replies(client) == {WALK: None, WATER: "done"}
    old = client.post("/api/assistant/confirm", json={"confirmation_id": first["confirmation_id"]}, headers=h).json()
    assert old["ok"] is False


def test_questions_about_a_routine_use_the_conversation(client):
    h = two_tasks(client)
    say(client, h, "tell me about the walk")
    r = say(client, h, "when is it?")
    assert r["tool"] == "explain_instruction" and r["item"]["text_en"] == WALK and r["via"] == "context"


def test_recall_and_recap(client):
    h = two_tasks(client)
    say(client, h, "tell me about the walk")
    r = say(client, h, "what did I just ask?")
    assert r["tool"] == "recall" and r["said"] == "tell me about the walk"
    say(client, h, "I finished the walk")
    say(client, h, "yes")
    r = say(client, h, "what have I marked today?")
    assert r["tool"] == "recap" and [(e["item"]["text_en"], e["reply"]) for e in r["entries"]] == [(WALK, "done")]


def test_small_talk_is_answered_without_doing_anything(client):
    h = two_tasks(client)
    assert say(client, h, "hello")["kind"] == "greeting"
    assert say(client, h, "thank you")["kind"] == "thanks"
    assert say(client, h, "what can you do?")["kind"] == "capabilities"
    assert say(client, h, "مرحبا")["kind"] == "greeting"
    assert replies(client) == {WALK: None, WATER: None}


def test_a_stale_topic_is_not_assumed(client, app):
    h = two_tasks(client)
    say(client, h, "tell me about the walk")
    from app.models import AssistantMessage, now
    with app.state.db.SessionLocal() as db:
        for m in db.query(AssistantMessage).all():
            m.created_at = now() - timedelta(minutes=45)
        db.commit()
    r = say(client, h, "I did it")
    assert r["understood"] is False and r["reason"] == "which"                   # asks instead of assuming "it"


def test_help_is_always_first_even_with_a_proposal_waiting(client):
    h = two_tasks(client)
    say(client, h, "I finished the walk")
    r = say(client, h, "I need help")
    assert r["tool"] == "emergency" and r["navigate"] == "urgent"
    assert replies(client)[WALK] is None


def test_history_is_restored_and_marks_what_is_still_waiting(client):
    h = two_tasks(client)
    say(client, h, "I finished the walk")
    hist = client.get("/api/assistant/history").json()
    assert hist["memory"] is True and [m["who"] for m in hist["messages"]] == ["you", "bot"]
    assert hist["messages"][1]["payload"]["pending"] is True
    say(client, h, "yes")
    hist = client.get("/api/assistant/history").json()
    waiting = [m for m in hist["messages"] if m["payload"] and m["payload"].get("confirmation_id")]
    assert waiting and waiting[0]["payload"]["pending"] is False


def test_clear_forgets_and_drops_a_waiting_proposal(client):
    h = two_tasks(client)
    say(client, h, "I finished the walk")
    assert client.delete("/api/assistant/history", headers=h).json()["cleared"] == 2
    assert client.get("/api/assistant/history").json()["messages"] == []
    assert say(client, h, "yes")["reason"] == "nothing_pending"
    assert replies(client)[WALK] is None


def test_memory_off_stores_nothing_and_follow_ups_need_the_whole_sentence(client):
    h = two_tasks(client)
    say(client, h, "tell me about the walk")
    assert client.put("/api/assistant/memory", json={"enabled": False}, headers=h).json() == {"memory": False}
    assert client.get("/api/assistant/history").json() == {"memory": False, "messages": [], "keeps_days": 30}
    r = say(client, h, "I did it")
    assert r["reason"] == "which"
    r = say(client, h, "I finished the walk")
    assert r["needs_confirmation"]
    assert say(client, h, "yes")["reason"] == "nothing_pending"                  # no memory: only the Yes button confirms
    client.post("/api/assistant/confirm", json={"confirmation_id": r["confirmation_id"]}, headers=h)
    assert replies(client)[WALK] == "done"
    from app.models import AssistantMessage
    assert client.get("/api/assistant/history").json()["messages"] == []
    assert client.put("/api/assistant/memory", json={"enabled": True}, headers=h).json() == {"memory": True}


def test_memory_is_private(client, app):
    h = two_tasks(client)
    say(client, h, "tell me about my secret walk plan")
    for who in ("demo-dr-layla", "demo-mariam"):
        hh = sign_in(client, who)
        assert client.get("/api/assistant/history").status_code == 404
        assert client.delete("/api/assistant/history", headers=hh).status_code == 404
        assert client.put("/api/assistant/memory", json={"enabled": False}, headers=hh).status_code == 404
    hy = sign_in(client, "demo-yousef")
    assert client.get("/api/assistant/history").json()["messages"] == []
    from app.models import AuditEvent
    with app.state.db.SessionLocal() as db:
        assert "secret" not in str([(a.action, a.target) for a in db.query(AuditEvent).all()])


def test_old_messages_are_pruned(client, app):
    h = two_tasks(client)
    from app import assistant as AS
    from app.models import AssistantMessage, User, now
    with app.state.db.SessionLocal() as db:
        u = db.get(User, "demo-fatima")
        for k in range(AS.KEEP_MESSAGES + 20):
            db.add(AssistantMessage(user_id=u.id, who="you", text=f"m{k}"))
        db.add(AssistantMessage(user_id=u.id, who="you", text="ancient", created_at=now() - timedelta(days=AS.KEEP_DAYS + 1)))
        db.commit()
    say(client, h, "hello")
    with app.state.db.SessionLocal() as db:
        n = db.query(AssistantMessage).count()
        assert n <= AS.KEEP_MESSAGES
        assert db.query(AssistantMessage).filter(AssistantMessage.text == "ancient").count() == 0


def test_it_notices_when_something_is_already_marked(client):
    h = two_tasks(client)
    say(client, h, "I finished the walk")
    say(client, h, "yes")
    r = say(client, h, "I finished the walk again")
    assert r["needs_confirmation"] and r["already"] == "done"
    r = say(client, h, "skip the walk")
    assert r["already"] is None


def test_recall_skips_bare_yes_and_no(client):
    h = two_tasks(client)
    say(client, h, "tell me about the water")
    say(client, h, "no")
    assert say(client, h, "what did I ask before?")["said"] == "tell me about the water"
