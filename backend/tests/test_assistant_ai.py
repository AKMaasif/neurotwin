"""Model routing and answering for the person's assistant (assistant_ai.py): the pure checks, and the API end to end with a stand-in model."""
import json

import pytest

from app import assistant_ai as AI
from app.assistant import parse

from conftest import make_user, sign_in


def login(client, name="fatima"):
    r = client.post("/api/auth/demo-enter", json={"username": name})
    assert r.status_code == 200
    return {"X-CSRF-Token": r.json()["csrf"]}


def consent(client, h, scope="assistant_model", granted=True):
    r = client.post("/api/consents", json={"scope": scope, "granted": granted, "language": "en"}, headers=h)
    assert r.status_code == 200, r.text


class Reply:
    def __init__(self, text):
        self.text, self.provider, self.model = text, "gemini", "fake"


class FakeModel:
    provider, model = "gemini", "fake"

    def __init__(self, out=None, fail=False):
        self.out, self.fail, self.calls = out, fail, []

    def complete(self, system, user, json_mode=False, images=None, timeout=None, temperature=0.2):
        self.calls.append({"system": system, "user": user, "json_mode": json_mode, "timeout": timeout})
        if self.fail:
            raise RuntimeError("down")
        return Reply(self.out if isinstance(self.out, str) else json.dumps(self.out, ensure_ascii=False))


@pytest.fixture(autouse=True)
def _fresh_cap(monkeypatch):
    monkeypatch.setattr(AI, "_calls", {"day": None, "n": 0})


def J(**kw):
    return json.dumps(kw, ensure_ascii=False)


# ---- pure: interpret() and guard() ---------------------------------------------------------------------------------------------------

def test_general_question_is_answered_with_a_spoken_version():
    out = AI.interpret(J(intent="general_question", lang="en", screen_text="India has about 1.4 billion people (2024 figure). It changes every year.",
                         speech_text="India has about one point four billion people."), [], "en")
    assert out["route"] == "reply"
    p = out["payload"]
    assert p["tool"] == "answer" and p["kind"] == "general_question" and p["lang"] == "en"
    assert "1.4 billion" in p["text"] and p["speech"].startswith("India has about one point four")


def test_arabic_question_is_answered_in_arabic_and_english_text_is_refused():
    ok = AI.interpret(J(intent="general_question", lang="ar", screen_text="يبلغ عدد سكان الهند نحو مليار وأربعمئة مليون نسمة.", speech_text=""), [], "ar")
    assert ok["route"] == "reply" and ok["payload"]["lang"] == "ar" and ok["payload"]["speech"]     # speech falls back to the screen text
    bad = AI.interpret(J(intent="general_question", lang="ar", screen_text="India has about 1.4 billion people."), [], "ar")
    assert bad == {"route": "blocked", "why": "wrong_language", "lang": "ar"}


@pytest.mark.parametrize("text,why", [
    ("Take 500 mg of paracetamol twice a day.", "dose"),
    ("You should stop taking your tablets if you feel dizzy.", "medicine_change"),
    ("You probably have early dementia.", "diagnosis"),
    ("There is nothing to worry about.", "reassurance"),
    ("Help is on its way.", "help_coming"),
    ("Call +971 50 123 4567 or visit www.example.com.", "contact_details"),
])
def test_health_answers_with_unsafe_content_are_blocked(text, why):
    out = AI.interpret(J(intent="health_general", lang="en", screen_text=text), [], "en")
    assert out["route"] == "blocked" and out["why"] == why


def test_amounts_are_fine_outside_health_answers():
    out = AI.interpret(J(intent="general_question", lang="en", screen_text="Use 200 g of flour and 2 eggs."), [], "en")
    assert out["route"] == "reply"


def test_unsafe_speech_text_is_blocked_too():
    out = AI.interpret(J(intent="health_general", lang="en", screen_text="Sleep helps memory.", speech_text="Take 20 mg before bed."), [], "en")
    assert out["route"] == "blocked" and out["why"] == "dose"


@pytest.mark.parametrize("intent", ["my_health", "not_allowed", "make_image"])
def test_fixed_reply_intents_never_show_model_text(intent):
    out = AI.interpret(J(intent=intent, lang="en", screen_text="Your memory is getting worse."), [], "en")
    assert out["route"] == "reply"
    assert out["payload"]["kind"] == intent and "text" not in out["payload"]


def test_emergency_from_the_model_asks_rather_than_opens():
    assert AI.interpret(J(intent="emergency", lang="en"), [], "en") == {"route": "urgent"}


@pytest.mark.parametrize("raw", ["not json", "[]", J(intent="do_anything"), J(intent="unclear")])
def test_bad_or_unclear_output_is_not_understood(raw):
    assert AI.interpret(raw, [], "en")["route"] == "unclear"


def test_plan_is_cleaned_sorted_and_needs_at_least_three_items():
    plan = [{"time": "9:00", "activity": "Short walk"}, {"time": "07:30", "activity": "Glass of water"},
            {"time": "25:00", "activity": "Bad time"}, {"time": "13:00", "activity": "Take 20 mg of your tablet"},
            {"time": "21.30", "activity": "Wind down, no screens"}]
    out = AI.interpret(J(intent="make_plan", lang="en", screen_text="Here is a gentle plan.", plan=plan), [], "en")
    assert out["route"] == "reply" and out["payload"]["tool"] == "plan"
    assert out["payload"]["plan"] == [{"time": "07:30", "activity": "Glass of water"}, {"time": "09:00", "activity": "Short walk"},
                                      {"time": "21:30", "activity": "Wind down, no screens"}]
    short = AI.interpret(J(intent="make_plan", lang="en", screen_text="Plan.", plan=plan[:2]), [], "en")
    assert short["route"] == "blocked" and short["why"] == "bad_plan"


def test_app_command_goes_through_the_same_menu_check():
    assert AI.interpret(J(intent="app_command", command={"tool": "open_screen", "screen": "messages"}), [], "en") == \
        {"route": "command", "parse": {"tool": "open_screen", "arguments": {"screen": "messages"}, "via": "model"}}
    assert AI.interpret(J(intent="app_command", command={"tool": "open_screen", "screen": "urgent"}), [], "en")["route"] == "unclear"
    assert AI.interpret(J(intent="app_command", command={"tool": "delete_everything"}), [], "en")["route"] == "unclear"


def test_markdown_emoji_and_exclamations_are_calmed():
    out = AI.interpret(J(intent="chat", lang="en", screen_text="**Hello!** 😀 Nice to see you!"), [], "en")
    assert out["payload"]["text"] == "Hello. Nice to see you."


def test_long_answers_are_cut_at_a_sentence():
    long = " ".join(["This is a sentence."] * 60)
    out = AI.interpret(J(intent="general_question", lang="en", screen_text=long), [], "en")
    assert len(out["payload"]["text"].split()) <= AI.MAX_SCREEN_WORDS and out["payload"]["text"].endswith(".")
    assert len(out["payload"]["speech"].split()) <= AI.MAX_SPEECH_WORDS


# ---- the fixed rules hand these to the model instead of refusing or guessing ---------------------------------------------------------

@pytest.mark.parametrize("text", [
    "i want an daily routine work shedule for my daily acutuvuty, can you make one to do list please",
    "can you creaate one image based on my current situation",
    "make me a daily routine", "draw a picture of my day", "اعمل لي جدول يومي", "ارسم صورة ليومي",
    "How many people live in India?", "what is the current population of india", "كم عدد سكان الهند؟",
])
def test_rules_pass_general_requests_on(text):
    assert parse(text, [], {}) == {"tool": None, "reason": "not_understood"}


def test_emergency_words_still_win_before_any_model():
    assert parse("make me a plan, I can't breathe", [], {})["tool"] in ("emergency", "ask_urgent")


# ---- API end to end with a stand-in model ---------------------------------------------------------------------------------------------

def test_without_consent_the_model_is_not_called_and_the_screen_says_how_to_switch_it_on(app, client):
    m = FakeModel(J(intent="general_question", lang="en", screen_text="About 1.4 billion."))
    app.state.get_llm = lambda: m
    h = login(client)
    r = client.post("/api/assistant/message", json={"text": "what is the current population of india"}, headers=h).json()
    assert r["understood"] is False and r["reason"] == "not_understood" and r["ai"] == "needs_consent"
    assert m.calls == []


def test_with_consent_a_general_question_is_answered_and_nothing_personal_beyond_the_list_is_sent(app, client):
    m = FakeModel(J(intent="general_question", lang="en", screen_text="India has about 1.4 billion people (2024 figure).",
                    speech_text="India has about one point four billion people."))
    app.state.get_llm = lambda: m
    h = login(client)
    consent(client, h)
    r = client.post("/api/assistant/message", json={"text": "what is the current population of india"}, headers=h).json()
    assert r["understood"] is True and r["tool"] == "answer" and r["kind"] == "general_question"
    assert "1.4 billion" in r["text"] and r["speech"]
    sent = m.calls[0]
    assert sent["json_mode"] is True and sent["timeout"] == AI.TIMEOUT_S
    assert "Message: what is the current population of india" in sent["user"]
    for private in ("Fatima", "fatima", "@", "demo-fatima"):
        assert private not in sent["user"]
    with app.state.db.SessionLocal() as db:
        from sqlalchemy import select
        from app.models import AuditEvent
        actions = [a for a in db.scalars(select(AuditEvent.action))]
    assert "assistant.ai.general_question" in actions


def test_known_commands_never_reach_the_model(app, client):
    m = FakeModel(J(intent="chat", lang="en", screen_text="Hi."))
    app.state.get_llm = lambda: m
    h = login(client)
    consent(client, h)
    r = client.post("/api/assistant/message", json={"text": "open my messages"}, headers=h).json()
    assert r["navigate"] == "messages" and m.calls == []


def test_a_routine_is_drafted_and_saved_only_when_the_person_saves_it(app, client):
    plan = [{"time": "08:00", "activity": "Glass of water"}, {"time": "09:30", "activity": "Short walk"},
            {"time": "13:00", "activity": "Lunch and rest"}, {"time": "17:00", "activity": "Call family"}]
    app.state.get_llm = lambda: FakeModel(J(intent="make_plan", lang="en", screen_text="Here is a gentle plan for today.", plan=plan))
    h = login(client)
    consent(client, h)
    r = client.post("/api/assistant/message", json={"text": "make me a daily routine"}, headers=h).json()
    assert r["tool"] == "plan" and len(r["plan"]) == 4
    assert client.get("/api/me/routine").json() == {"items": [], "saved_at": None}          # a draft is not saved
    saved = client.put("/api/me/routine", json={"items": r["plan"]}, headers=h).json()
    assert saved["items"][0] == {"time": "08:00", "activity": "Glass of water"} and saved["saved_at"]
    assert client.get("/api/me/routine").json()["items"] == saved["items"]
    assert client.put("/api/me/routine", json={"items": [{"time": "99:00", "activity": "x"}]}, headers=h).status_code == 422
    assert client.delete("/api/me/routine", headers=h).json() == {"items": [], "saved_at": None}


def test_routine_is_for_participants_only(client):
    login(client, "dr.layla")
    assert client.get("/api/me/routine").status_code == 404


def test_provider_failure_is_a_helpful_not_understood(app, client):
    app.state.get_llm = lambda: FakeModel(fail=True)
    h = login(client)
    consent(client, h)
    r = client.post("/api/assistant/message", json={"text": "tell me about the history of Dubai please"}, headers=h).json()
    assert r["understood"] is False and r["reason"] == "not_understood" and r["ai"] == "on"


def test_blocked_answer_is_replaced_by_a_fixed_reply(app, client):
    app.state.get_llm = lambda: FakeModel(J(intent="health_general", lang="en", screen_text="Take 500 mg of aspirin."))
    h = login(client)
    consent(client, h)
    r = client.post("/api/assistant/message", json={"text": "how much vitamin d should an older person take daily"}, headers=h).json()
    assert r["tool"] == "answer" and r["kind"] == "blocked" and "text" not in r


def test_no_provider_says_off(app, client):
    app.state.get_llm = lambda: None
    h = login(client)
    r = client.post("/api/assistant/message", json={"text": "what is the capital of japan, can you tell me"}, headers=h).json()
    assert r["ai"] == "off"


def test_real_accounts_words_are_never_sent(app, client):
    make_user(app, "real-1", "realperson")
    m = FakeModel(J(intent="general_question", lang="en", screen_text="Tokyo."))
    app.state.get_llm = lambda: m
    h = sign_in(client, "realperson", "a real account phrase 1")
    r = client.post("/api/assistant/message", json={"text": "what is the capital of japan, can you tell me"}, headers=h).json()
    assert r["ai"] == "real_data" and m.calls == []


def test_a_short_general_question_is_not_taken_for_a_question_about_a_task(app, client):
    # with tasks on today's list, a short "how many ...?" naming no task used to be answered with "Which one do you mean?"
    m = FakeModel(J(intent="general_question", lang="ar", screen_text="يبلغ عدد سكان الهند نحو مليار وأربعمئة مليون نسمة."))
    app.state.get_llm = lambda: m
    h = login(client)
    consent(client, h)
    assert client.get("/api/care-plan/today").json()["items"]                     # the demo person has tasks today
    r = client.post("/api/assistant/message", json={"text": "كم عدد سكان الهند؟"}, headers=h).json()
    assert r["tool"] == "answer" and r["lang"] == "ar" and len(m.calls) == 1
    r = client.post("/api/assistant/message", json={"text": "when is it"}, headers=h).json()
    assert r["reason"] == "which" and len(m.calls) == 1                           # a real question about a task still asks which one
