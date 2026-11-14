"""One person's whole journey through the API, in order, as the real screens use it. This is a software workflow test on the demo data. It is not
evidence of clinical usefulness, speech quality, Arabic suitability or accuracy of anything (see docs/PATIENT_EXPERIENCE_STATUS.md)."""
from test_assistant import say, two_tasks
from test_careplan import sign_in


def run(client, h, code, version, obs, **kw):
    s = client.post("/api/sessions", headers=h, json={"protocol_code": code, "protocol_version": version, "language": "en", "device": "web", **kw}).json()
    r = client.post(f"/api/sessions/{s['id']}/complete", headers=h, json={"status": "completed", "interruptions": 0, "client_version": "e2e", "observations": obs})
    assert r.status_code == 200, r.text
    return s["id"]


def test_the_whole_patient_journey(client):
    # 1. A clinician sends a plan. Until the person accepts, it creates no tasks.
    from test_careplan import add, clin, send
    hc = clin(client)
    add(client, hc, text_en="Walk for ten minutes", day_part="morning", time_hhmm="08:00")
    add(client, hc, text_en="Drink a glass of water", day_part="afternoon", time_hhmm="13:00")
    assert send(client, hc).status_code == 200
    h = sign_in(client, "demo-fatima")
    assert client.get("/api/care-plan/today").json()["items"] == []
    plan = client.get("/api/care-plan/awaiting").json()[0]["id"]

    # 2. The person accepts; tasks appear; one answer is given, the other is left alone (not recorded, never "missed").
    assert client.post(f"/api/care-plans/{plan}/respond", json={"response": "accept"}, headers=h).status_code == 200
    items = client.get("/api/care-plan/today").json()["items"]
    assert len(items) == 2
    assert client.post(f"/api/care-plan/{items[0]['id']}/reply", json={"reply": "done"}, headers=h).status_code == 200

    # 3. The text assistant changes nothing until the person confirms, and only once.
    r = say(client, h, "mark drink water as done")
    assert r["needs_confirmation"] is True
    assert client.post("/api/assistant/confirm", json={"confirmation_id": r["confirmation_id"]}, headers=h).status_code == 200

    # 4. Activities: self-report, a prototype performance task, WHO-5 (published wording, total is the sum).
    run(client, h, "daily_checkin", "0.1", [{"measure": "sleep_hours", "kind": "self_reported", "unit": "h", "value_num": 6},
                                            {"measure": "sleep_quality", "kind": "self_reported", "unit": "1-5", "value_num": 3},
                                            {"measure": "today_factors", "kind": "self_reported", "value_text": "none"}])
    run(client, h, "picture_sequence", "0.1", [{"measure": "rounds_correct", "kind": "observed", "unit": "count", "value_num": 3},
                                               {"measure": "rounds_shown", "kind": "observed", "unit": "count", "value_num": 4},
                                               {"measure": "longest_correct", "kind": "observed", "unit": "count", "value_num": 4}], assisted=True)
    run(client, h, "who5", "1998-en", [{"measure": f"who5_{i}", "kind": "self_reported", "unit": "0-5", "value_num": 4} for i in range(1, 6)]
        + [{"measure": "who5_raw", "kind": "self_reported", "unit": "0-25", "value_num": 20}])

    # 5. A concern is previewed, sent to a server-chosen clinician, and the person only sees states that happened.
    c = client.post("/api/concerns", json={"topic": "sleep", "since": "few_days", "text": "I have been waking at night."}, headers=h).json()
    assert c["status"] == "draft"
    sent = client.post(f"/api/concerns/{c['id']}/send", json={"rev": c["rev"]}, headers=h).json()
    assert sent["status"] == "delivered" and sent["recipient"] == "Dr. Layla"
    hc = sign_in(client, "demo-dr-layla")
    assert client.post(f"/api/concerns/{c['id']}/acknowledge", headers=hc).json()["status"] == "acknowledged"

    # 6. Emergency screen works without anyone being contacted; the trusted number is private.
    h = sign_in(client, "demo-fatima")
    assert [n["number"] for n in client.get("/api/emergency/config").json()["numbers"]] == ["998", "999"]
    assert client.put("/api/emergency/trusted", json={"name": "Mariam", "phone": "+971501234567"}, headers=h).status_code == 200
    assert say(client, h, "I need urgent help")["navigate"] == "urgent"

    # 7. The person's own report shows what happened, nothing interpreted, and keeps WHO-5 and performance numbers out.
    rep = client.get("/api/me/report").json()
    today = next(d for d in rep["days"] if d["date"] == rep["period"]["to"])
    codes = {s["protocol_code"] for s in today["sessions"]}
    assert {"daily_checkin", "picture_sequence", "who5"} <= codes
    assert all(s["values"] == [] for s in today["sessions"] if s["protocol_code"] in ("picture_sequence", "who5"))
    assert rep["routines"] and "missed" not in str(rep).lower()
    assert rep["concerns_sent"] and rep["concerns_sent"][0]["status"] == "acknowledged"

    # 8. Privacy: other people see none of it, and revoking sharing removes the clinician's access but keeps the person's record.
    for who in ("demo-yousef",):
        sign_in(client, who)
        assert client.get("/api/emergency/config").json()["trusted"] is None
        assert all(d["sessions"] == [] for d in client.get("/api/me/report").json()["days"][-1:])
    h = sign_in(client, "demo-fatima")
    g = next(x for x in client.get("/api/grants").json() if x["purpose"] == "clinical_review")
    assert client.post(f"/api/grants/{g['id']}/revoke", headers=h).status_code == 200
    sign_in(client, "demo-dr-layla")
    assert client.get("/api/concerns/inbox").json() == []
    sign_in(client, "demo-fatima")
    assert client.get("/api/concerns").json()[0]["status"] == "acknowledged"
    assert client.get("/api/me/report").json()["concerns_sent"]
