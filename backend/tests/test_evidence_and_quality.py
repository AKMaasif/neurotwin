import pytest

from app import protocols as P
from app import quality as Q
from app import services as S
from conftest import consent, run_reaction


def by_measure(records):
    return {r["measure"]: r for r in records}


def test_clean_session_is_usable_and_attributed(client, yousef):
    consent(client, yousef)
    r = run_reaction(client, yousef)
    assert r.status_code == 200
    rt = by_measure(r.json()["evidence"])["rt_median_ms"]
    assert rt["quality"] == "usable" and rt["quality_reasons"] == []
    assert rt["kind"] == "observed" and rt["producer_type"] == "device"
    assert rt["protocol_version"] == "0.1"


@pytest.mark.parametrize("kwargs,level,reason", [
    ({"status": "interrupted"}, "doubtful", "interrupted_session"),
    ({"interruptions": 2}, "doubtful", "interrupted_session"),
    ({"assisted": True}, "doubtful", "assisted_session"),
    ({"unwell": True}, "doubtful", "participant_unwell"),
    ({"early": 3}, "doubtful", "many_anticipations"),
    ({"valid": 2}, "unusable", "too_few_valid_trials"),
    ({"rt": 50}, "unusable", "out_of_range"),
    ({"status": "abandoned"}, "unusable", "abandoned_session"),
])
def test_conditions_lower_quality_and_are_kept(client, yousef, kwargs, level, reason):
    consent(client, yousef)
    r = run_reaction(client, yousef, **kwargs)
    assert r.status_code == 200
    rt = by_measure(r.json()["evidence"])["rt_median_ms"]
    assert rt["quality"] == level and reason in rt["quality_reasons"]
    assert rt["value_num"] is not None, "a low-quality value is labelled, never changed or dropped"


def test_review_items_raised_for_reviewable_reasons_only(client, yousef):
    consent(client, yousef)
    run_reaction(client, yousef, assisted=True)          # recorded, but no action needed
    run_reaction(client, yousef, valid=2)                 # needs a person to look
    items = client.get("/api/participants/demo-yousef/review-items", headers=yousef).json()
    assert {i["reason"] for i in items} == {"too_few_valid_trials"}


def test_missing_value_must_say_why(client, yousef):
    consent(client, yousef)
    s = client.post("/api/sessions", json={"protocol_code": "daily_checkin", "protocol_version": "0.1"},
                    headers=yousef).json()
    r = client.post(f"/api/sessions/{s['id']}/complete", json={"status": "completed", "observations": [
        {"measure": "sleep_hours", "kind": "self_reported"}]}, headers=yousef)
    assert r.status_code == 422


def test_skipped_answer_is_stored_as_missing_never_as_a_value(client, yousef):
    consent(client, yousef)
    s = client.post("/api/sessions", json={"protocol_code": "daily_checkin", "protocol_version": "0.1"},
                    headers=yousef).json()
    r = client.post(f"/api/sessions/{s['id']}/complete", json={"status": "completed", "observations": [
        {"measure": "sleep_hours", "kind": "self_reported", "missing_reason": "skipped_by_participant"},
        {"measure": "sleep_quality", "kind": "self_reported", "value_num": 4}]}, headers=yousef)
    sleep = by_measure(r.json()["evidence"])["sleep_hours"]
    assert sleep["value_num"] is None and sleep["quality"] == "unusable" and "missing_value" in sleep["quality_reasons"]


def test_kind_must_match_protocol(client, yousef):
    consent(client, yousef)
    s = client.post("/api/sessions", json={"protocol_code": "reaction_time", "protocol_version": "0.1"},
                    headers=yousef).json()
    r = client.post(f"/api/sessions/{s['id']}/complete", json={"status": "completed", "observations": [
        {"measure": "rt_median_ms", "kind": "self_reported", "value_num": 500}]}, headers=yousef)
    assert r.status_code == 422


def test_unknown_protocol_version_refused(client, yousef):
    consent(client, yousef)
    r = client.post("/api/sessions", json={"protocol_code": "reaction_time", "protocol_version": "9.9"},
                    headers=yousef)
    assert r.status_code == 422


def test_session_cannot_be_completed_twice(client, yousef):
    consent(client, yousef)
    s = client.post("/api/sessions", json={"protocol_code": "reaction_time", "protocol_version": "0.1"},
                    headers=yousef).json()
    body = {"status": "abandoned", "observations": []}
    assert client.post(f"/api/sessions/{s['id']}/complete", json=body, headers=yousef).status_code == 200
    assert client.post(f"/api/sessions/{s['id']}/complete", json=body, headers=yousef).status_code == 409


def test_amend_keeps_original(client, yousef):
    consent(client, yousef)
    s = client.post("/api/sessions", json={"protocol_code": "daily_checkin", "protocol_version": "0.1"},
                    headers=yousef).json()
    rec = client.post(f"/api/sessions/{s['id']}/complete", json={"status": "completed", "observations": [
        {"measure": "sleep_hours", "kind": "self_reported", "value_num": 4},
        {"measure": "sleep_quality", "kind": "self_reported", "value_num": 3}]}, headers=yousef).json()
    old = by_measure(rec["evidence"])["sleep_hours"]
    new = client.post(f"/api/evidence/{old['id']}/amend", json={"value_num": 7, "reason": "Typed the wrong number"},
                      headers=yousef).json()
    assert new["supersedes_id"] == old["id"] and new["value_num"] == 7
    detail = client.get(f"/api/evidence/{new['id']}", headers=yousef).json()
    assert detail["earlier_versions"][0]["value_num"] == 4 and detail["earlier_versions"][0]["status"] == "amended"
    current = client.get("/api/participants/demo-yousef/evidence", headers=yousef).json()
    assert old["id"] not in [e["id"] for e in current]
    history = client.get("/api/participants/demo-yousef/evidence?include_history=true", headers=yousef).json()
    assert old["id"] in [e["id"] for e in history]


def test_observed_results_cannot_be_amended(client, yousef):
    consent(client, yousef)
    rt = by_measure(run_reaction(client, yousef).json()["evidence"])["rt_median_ms"]
    r = client.post(f"/api/evidence/{rt['id']}/amend", json={"value_num": 400, "reason": "faster"}, headers=yousef)
    assert r.status_code == 409


def test_withdraw_needs_reason_and_keeps_record(client, yousef):
    consent(client, yousef)
    rt = by_measure(run_reaction(client, yousef).json()["evidence"])["rt_median_ms"]
    assert client.post(f"/api/evidence/{rt['id']}/withdraw", json={"reason": " "}, headers=yousef).status_code == 422
    w = client.post(f"/api/evidence/{rt['id']}/withdraw", json={"reason": "Grandchild pressed the screen"},
                    headers=yousef).json()
    assert w["status"] == "withdrawn"
    assert any(e["id"] == rt["id"] for e in client.get("/api/participants/demo-yousef/evidence", headers=yousef).json())


def test_clinician_resolves_review_with_note(client, login):
    dr = login("demo-dr-layla")
    items = client.get("/api/participants/demo-fatima/review-items", headers=dr).json()
    assert items, "seed data has an interrupted session"
    assert client.post(f"/api/review-items/{items[0]['id']}/resolve", json={"note": ""}, headers=dr).status_code == 422
    done = client.post(f"/api/review-items/{items[0]['id']}/resolve", json={"note": "Phone call mid-task; keep."},
                       headers=dr).json()
    assert done["status"] == "resolved" and done["resolved_by"] == "demo-dr-layla"


def test_participant_cannot_resolve_review(client, login):
    fatima = login("demo-fatima")
    items = client.get("/api/participants/demo-fatima/review-items", headers=fatima).json()
    assert client.post(f"/api/review-items/{items[0]['id']}/resolve", json={"note": "fine"},
                       headers=fatima).status_code == 404


def test_audit_trail_records_access_without_values(client, login):
    dr = login("demo-dr-layla")
    client.get("/api/participants/demo-fatima/evidence", headers=dr)
    trail = client.get("/api/participants/demo-fatima/audit", headers=dr).json()
    assert any(a["action"] == "evidence.viewed" and a["actor_id"] == "demo-dr-layla" for a in trail)
    assert "612" not in str(trail)


# ---- Inferred records (service-level rule; nothing infers yet) -------------------------------------------------

def test_inferred_requires_sources_and_rule_or_model(app, client, yousef):
    consent(client, yousef)
    rt = by_measure(run_reaction(client, yousef).json()["evidence"])["rt_median_ms"]
    with app.state.db.SessionLocal() as db:
        with pytest.raises(S.Refused):
            S.record_inferred(db, "demo-yousef", "x", 1, None, [], "rule", "r", "1")
        with pytest.raises(S.Refused):
            S.record_inferred(db, "demo-yousef", "x", 1, None, [rt["id"]], "person", "p", "1")
        with pytest.raises(S.Refused):
            S.record_inferred(db, "demo-fatima", "x", 1, None, [rt["id"]], "rule", "r", "1")
        e = S.record_inferred(db, "demo-yousef", "x", 1, None, [rt["id"]], "rule", "r", "1")
        assert e.kind == "inferred" and e.derived_from == [rt["id"]]


def test_quality_rules_unit():
    p = P.get("reaction_time", "0.1")
    obs = [Q.ObservationIn("rt_median_ms", "observed", 500), Q.ObservationIn("valid_trials", "observed", 5),
           Q.ObservationIn("anticipations", "observed", 0)]
    assert Q.assess_session(p, Q.SessionContext("completed"), obs)[0].level == "usable"
    assert Q.assess_session(None, Q.SessionContext("completed"), obs)[0].reasons == ["unknown_protocol"]
    with pytest.raises(Q.EvidenceRejected):
        Q.check_shape(Q.ObservationIn("rt_median_ms", "observed", 500, missing_reason="x"))


def test_session_level_reason_raises_one_item_per_session(client, yousef):
    consent(client, yousef)
    run_reaction(client, yousef, status="interrupted")
    items = client.get("/api/participants/demo-yousef/review-items", headers=yousef).json()
    assert [i["reason"] for i in items] == ["interrupted_session"]
