"""Stage 3: notifications, the person's history, clinician review of responses, and rule-checked field suggestions."""
from test_careplan import add, clin, send, sign_in, view
from app import extraction as E


def waiting(client, h):
    add(client, h)
    send(client, h)


def test_sending_notifies_the_person_with_no_text(client):
    h = clin(client)
    add(client, h, text_en="Secret routine words")
    send(client, h)
    sign_in(client, "demo-fatima")
    n = client.get("/api/notifications").json()
    assert len(n) == 1 and n[0]["kind"] == "plan_waiting" and not n[0]["read"]
    assert "Secret" not in str(n)


def test_response_notifies_the_sending_clinician_and_closes_the_waiting_notice(client):
    h = clin(client)
    waiting(client, h)
    h2 = sign_in(client, "demo-fatima")
    pid = client.get("/api/care-plan/awaiting").json()[0]["id"]
    client.post(f"/api/care-plans/{pid}/respond", json={"response": "question", "note": "Is it safe?"}, headers=h2)
    assert client.get("/api/notifications").json()[0]["read"] is False        # a question leaves the plan waiting
    client.post(f"/api/care-plans/{pid}/respond", json={"response": "accept"}, headers=h2)
    assert all(n["read"] for n in client.get("/api/notifications").json())    # answering closes it
    sign_in(client, "demo-dr-layla")
    kinds = [n["kind"] for n in client.get("/api/notifications").json()]
    assert "plan_question" in kinds and "plan_accepted" in kinds
    assert "Is it safe" not in str(client.get("/api/notifications").json())


def test_recall_closes_the_waiting_notice(client):
    h = clin(client)
    waiting(client, h)
    pid = view(client)["plans"][0]["id"]
    client.post(f"/api/care-plans/{pid}/recall", headers=h)
    sign_in(client, "demo-fatima")
    assert all(n["read"] for n in client.get("/api/notifications").json())


def test_notifications_are_private(client):
    h = clin(client)
    waiting(client, h)
    sign_in(client, "demo-fatima")
    nid = client.get("/api/notifications").json()[0]["id"]
    h3 = sign_in(client, "demo-yousef")
    assert client.get("/api/notifications").json() == []
    assert client.post(f"/api/notifications/{nid}/read", headers=h3).status_code == 404
    h2 = sign_in(client, "demo-fatima")
    assert client.post(f"/api/notifications/{nid}/read", headers=h2).status_code == 200
    assert client.get("/api/notifications").json()[0]["read"] is True


def test_clinician_review_is_what_marks_a_response_seen(client):
    h = clin(client)
    waiting(client, h)
    h2 = sign_in(client, "demo-fatima")
    pid = client.get("/api/care-plan/awaiting").json()[0]["id"]
    client.post(f"/api/care-plans/{pid}/respond", json={"response": "question", "note": "Is it safe?"}, headers=h2)
    hist = client.get("/api/care-plan/history").json()
    assert hist["plans"][0]["your_answers"][0]["reviewed"] is False
    h = sign_in(client, "demo-dr-layla")
    rid = view(client)["plans"][0]["responses"][0]["id"]
    assert client.post(f"/api/plan-responses/{rid}/review", json={"note": "Fine with the knee."}, headers=h).status_code == 200
    assert view(client)["plans"][0]["responses"][0]["reviewed_by"] == "Dr. Layla"
    sign_in(client, "demo-fatima")
    assert client.get("/api/care-plan/history").json()["plans"][0]["your_answers"][0]["reviewed"] is True


def test_only_a_clinician_with_access_can_review(client):
    h = clin(client)
    waiting(client, h)
    h2 = sign_in(client, "demo-fatima")
    pid = client.get("/api/care-plan/awaiting").json()[0]["id"]
    client.post(f"/api/care-plans/{pid}/respond", json={"response": "question", "note": "Q"}, headers=h2)
    h = sign_in(client, "demo-dr-layla")
    rid = view(client)["plans"][0]["responses"][0]["id"]
    for who in ("demo-fatima", "demo-mariam"):
        hh = sign_in(client, who)
        assert client.post(f"/api/plan-responses/{rid}/review", json={}, headers=hh).status_code == 404


def test_history_is_own_patient_reported_and_omits_silence(client):
    h = clin(client)
    accepted_item = add(client, h, text_en="Stretch").json()
    send(client, h)
    h2 = sign_in(client, "demo-fatima")
    pid = client.get("/api/care-plan/awaiting").json()[0]["id"]
    client.post(f"/api/care-plans/{pid}/respond", json={"response": "accept"}, headers=h2)
    items = client.get("/api/care-plan/today").json()["items"]
    client.post(f"/api/care-plan/{items[0]['id']}/reply", json={"reply": "done"}, headers=h2)
    hist = client.get("/api/care-plan/history").json()
    assert hist["label"] == "patient_reported" and len(hist["days"]) == 1 and len(hist["days"][0]["entries"]) == 1
    assert "missed" not in str(hist)
    h3 = sign_in(client, "demo-yousef")
    assert client.get("/api/care-plan/history").json()["days"] == []
    sign_in(client, "demo-dr-layla")
    assert client.get("/api/care-plan/history").status_code == 404


# ---- rules for suggested fields -------------------------------------------------------------------------------

def codes(text, fields):
    return [f["code"] for f in E.check(text, fields)]


def test_numbers_and_units_must_be_in_the_text():
    assert "number_not_in_text" in codes("Walk after breakfast", {"quantity": 30, "unit": "minutes", "day_part": "morning", "weekdays": [1]})
    assert "unit_not_in_text" in codes("Walk for 10 minutes", {"quantity": 10, "unit": "mg", "day_part": "morning", "weekdays": [1]})
    assert codes("Walk for 10 minutes", {"quantity": 10, "unit": "minutes", "day_part": "morning", "weekdays": [1]}) == []


def test_units_are_never_guessed():
    p = E.propose("Do a 10 millimeter stretch")
    assert p["quantity"] is None and p["unit"] is None
    assert "number_without_unit" in codes("Do a 10 millimeter stretch", p)


def test_missing_time_and_days_are_flagged_not_filled():
    p = E.propose("Drink water")
    assert p["time_hhmm"] is None and p["day_part"] is None and p["weekdays"] == []
    assert codes("Drink water", p).count("needs_clinician") == 2


def test_proposal_reads_only_what_is_stated():
    p = E.propose("Walk for 10 minutes after breakfast on Monday and Wednesday at 8:30")
    assert p == {"day_part": "morning", "weekdays": [0, 2], "time_hhmm": "08:30", "quantity": 10.0, "unit": "minutes"}
    assert E.propose("Take 2 tablets at 8pm")["time_hhmm"] == "20:00"


def test_suggest_endpoint_saves_nothing(client):
    h = clin(client)
    before = view(client)
    r = client.post("/api/participants/demo-fatima/care-plan/suggest", json={"text_en": "Walk for 10 minutes"}, headers=h)
    assert r.status_code == 200 and r.json()["source"] == "rules" and r.json()["fields"]["unit"] == "minutes"
    assert view(client) == before
    h2 = sign_in(client, "demo-fatima")
    assert client.post("/api/participants/demo-fatima/care-plan/suggest", json={"text_en": "x"}, headers=h2).status_code == 404
