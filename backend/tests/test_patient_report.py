"""The person's own period report: right dates, own data only, nothing interpreted, WHO-5 answers never shown, missing days listed."""
from datetime import date, timedelta

from test_careplan import add, clin, send, sign_in


def session(client, h, code="daily_checkin", version="0.1", obs=None, **kw):
    s = client.post("/api/sessions", headers=h, json={"protocol_code": code, "protocol_version": version, "language": "en", "device": "web", **kw}).json()
    obs = obs or [{"measure": "sleep_hours", "kind": "self_reported", "unit": "h", "value_num": 7},
                  {"measure": "sleep_quality", "kind": "self_reported", "unit": "1-5", "value_num": 3},
                  {"measure": "today_factors", "kind": "self_reported", "value_text": "none"}]
    r = client.post(f"/api/sessions/{s['id']}/complete", headers=h, json={"status": "completed", "interruptions": 0, "client_version": "t", "observations": obs})
    assert r.status_code == 200, r.text


def test_default_is_eleven_days_ending_today_with_exact_dates(client):
    h = sign_in(client, "demo-fatima")
    r = client.get("/api/me/report").json()
    assert r["period"]["days"] == 11 and len(r["days"]) == 11
    assert date.fromisoformat(r["period"]["to"]) - date.fromisoformat(r["period"]["from"]) == timedelta(days=10)
    assert r["days"][0]["date"] == r["period"]["from"] and r["days"][-1]["date"] == r["period"]["to"]
    assert r["label"] == "patient_recorded" and "change_bands" in r["not_included"]


def test_shows_a_recorded_activity_and_lists_other_days_as_nothing_recorded(client):
    h = sign_in(client, "demo-fatima")
    session(client, h)
    r = client.get("/api/me/report?days=7").json()
    today = r["period"]["to"]
    day = next(d for d in r["days"] if d["date"] == today)
    assert [s["protocol_code"] for s in day["sessions"]] == ["daily_checkin"] and day["sessions"][0]["status"] == "completed"
    assert {v["measure"] for v in day["sessions"][0]["values"]} == {"sleep_hours", "sleep_quality", "today_factors"}
    missing = r["missing"]["days_without_activity"]
    assert today not in missing and len(missing) == 7 - sum(1 for d in r["days"] if d["sessions"])
    assert "problem" in r["missing"]["note"] and "score" not in str(r).replace("scores", "")


def test_who5_is_shown_as_done_but_answers_and_total_are_hidden(client):
    h = sign_in(client, "demo-fatima")
    obs = [{"measure": f"who5_{i}", "kind": "self_reported", "unit": "0-5", "value_num": 3} for i in range(1, 6)] + \
          [{"measure": "who5_raw", "kind": "self_reported", "unit": "0-25", "value_num": 15}]
    session(client, h, "who5", "1998-en", obs)
    s = next(s for d in client.get("/api/me/report").json()["days"] for s in d["sessions"] if s["protocol_code"] == "who5")
    assert s["status"] == "completed" and s["values"] == [] and s["shows_values"] is False


def test_skipped_answers_are_counted_not_filled_in(client):
    h = sign_in(client, "demo-fatima")
    before = client.get("/api/me/report").json()["missing"]["skipped_answers"]
    session(client, h, obs=[{"measure": "sleep_hours", "kind": "self_reported", "unit": "h", "missing_reason": "skipped_by_participant"},
                            {"measure": "sleep_quality", "kind": "self_reported", "unit": "1-5", "value_num": 4},
                            {"measure": "today_factors", "kind": "self_reported", "value_text": "none"}])
    r = client.get("/api/me/report").json()
    assert r["missing"]["skipped_answers"] == before + 1


def test_routines_count_answers_and_no_answer_is_not_missed(client):
    c = clin(client)
    add(client, c, text_en="Walk for ten minutes", day_part="morning", time_hhmm="08:00")
    add(client, c, text_en="Drink a glass of water", day_part="afternoon", time_hhmm="13:00")
    send(client, c)
    h = sign_in(client, "demo-fatima")
    pid = client.get("/api/care-plan/awaiting").json()[0]["id"]
    client.post(f"/api/care-plans/{pid}/respond", json={"response": "accept"}, headers=h)
    first = client.get("/api/care-plan/today").json()["items"][0]["id"] if client.get("/api/care-plan/today").status_code == 200 else None
    assert first is not None
    assert client.post(f"/api/care-plan/{first}/reply", json={"reply": "done"}, headers=h).status_code == 200
    r = client.get("/api/me/report").json()
    assert r["routine_plan_accepted"] is True
    assert [(x["marked_done_days"], x["answered_days"]) for x in r["routines"]] == [(1, 1)]      # the unanswered routine is simply absent
    assert "missed" not in str(r).lower()


def test_bounds_and_future_dates_are_refused(client):
    sign_in(client, "demo-fatima")
    assert client.get("/api/me/report?days=0").status_code == 422
    assert client.get("/api/me/report?days=91").status_code == 422
    assert client.get("/api/me/report?end=2999-01-01").status_code == 422
    assert client.get("/api/me/report?end=nonsense").status_code == 422
    assert client.get("/api/me/report?days=90").status_code == 200


def test_only_own_data_and_only_for_participants(client):
    h = sign_in(client, "demo-fatima")
    session(client, h)
    sign_in(client, "demo-yousef")
    r = client.get("/api/me/report").json()
    assert all(d["sessions"] == [] for d in r["days"])
    sign_in(client, "demo-dr-layla")
    assert client.get("/api/me/report").status_code == 404


def test_opening_it_is_audited_without_content(client, app):
    h = sign_in(client, "demo-fatima")
    session(client, h)
    client.get("/api/me/report")
    from app.models import AuditEvent
    with app.state.db.SessionLocal() as db:
        rows = [(a.action, a.target) for a in db.query(AuditEvent).filter(AuditEvent.action == "report.viewed")]
    assert rows and all(t is None for _, t in rows)


def test_needs_sign_in(client):
    assert client.get("/api/me/report").status_code in (401, 403)


def test_performance_numbers_are_not_shown(client):
    h = sign_in(client, "demo-fatima")
    obs = [{"measure": "rt_median_ms", "kind": "observed", "unit": "ms", "value_num": 400}, {"measure": "valid_trials", "kind": "observed", "unit": "count", "value_num": 5},
           {"measure": "anticipations", "kind": "observed", "unit": "count", "value_num": 0}]
    session(client, h, "reaction_time", "0.1", obs)
    ss = [s for d in client.get("/api/me/report").json()["days"] for s in d["sessions"] if s["protocol_code"] == "reaction_time"]
    assert ss and all(s["values"] == [] and s["shows_values"] is False for s in ss)
