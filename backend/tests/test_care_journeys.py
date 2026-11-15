"""Linked workflow and adversarial access cases. Software behaviour, not clinical accuracy."""
import pytest
from sqlalchemy import select

from app import activity_analysis as AA
from app.models import AuditEvent, CareJourneyEvent, Evidence
from conftest import make_user


@pytest.fixture(autouse=True)
def isolated_runs(tmp_path, monkeypatch):
    monkeypatch.setenv("NEUROTWIN_ACTIVITY_RUNS", str(tmp_path / "activity"))
    monkeypatch.setenv("NEUROTWIN_AGENTS_MODE", "mock")


@pytest.fixture
def journey(client, login):
    hp = login("demo-fatima")
    c = client.post("/api/concerns", headers=hp, json={"topic": "sleep", "since": "few_days", "text": "PRIVATE-CONCERN waking at night"}).json()
    assert client.post(f"/api/concerns/{c['id']}/send", headers=hp, json={"rev": c["rev"]}).status_code == 200
    hc = login("demo-dr-layla")
    r = client.post(f"/api/care-journeys/from-concern/{c['id']}", headers=hc)
    assert r.status_code == 200, r.text
    return hp, hc, r.json()


def update(client, hc, j, **changes):
    return client.post(f"/api/care-journeys/{j['id']}", headers=hc, json={"expected_revision": j["revision"], **changes})


def reviewed_run(client, hc):
    r = client.post("/api/activity-analysis/participants/demo-fatima/runs", headers=hc, json={"range_days": 183}).json()
    got = client.get(f"/api/activity-analysis/runs/{r['run_id']}", headers=hc).json()
    assert got["summary"]["statements"], got
    response = client.post(f"/api/activity-analysis/runs/{r['run_id']}/review", headers=hc,
                           json={"decisions": [{"kind": "statement", "index": 0, "decision": "keep"}], "note": "Reviewed."})
    assert response.status_code == 200, response.text
    return response.json()


def test_open_is_idempotent_and_does_not_acknowledge_or_resolve(journey, client):
    hp, hc, j = journey
    twice = client.post(f"/api/care-journeys/from-concern/{j['concern_id']}", headers=hc).json()
    assert twice["id"] == j["id"] and len(twice["events"]) == 1
    assert j["concern_status"] == "delivered" and j["outcome"] == "open"
    assert client.get(f"/api/care-journeys/{j['id']}", headers=hp).status_code == 200


def test_follow_up_needs_action_date_and_preserves_history(journey, client):
    hp, hc, j = journey
    assert update(client, hc, j, outcome="follow_up_required").status_code == 422
    assert update(client, hc, j, outcome="follow_up_required", next_action="Review together", follow_up_on="bad").status_code == 422
    result = update(client, hc, j, outcome="follow_up_required", next_action="Review together", follow_up_on="2026-12-01", note="Shared note").json()
    assert result["revision"] == 2 and len(result["events"]) == 2
    assert client.get(f"/api/care-journeys/{j['id']}", headers=hp).json()["events"][-1]["note"] == "Shared note"
    assert update(client, hc, j, next_action="Old tab overwrite").status_code == 409


def test_outcome_is_explicit_and_not_a_concern_status(journey, client):
    _, hc, j = journey
    assert update(client, hc, j, outcome="resolved").status_code == 422
    result = update(client, hc, j, outcome="resolved", note="Discussed with the person.").json()
    assert result["outcome"] == "resolved" and result["concern_status"] == "delivered"
    assert update(client, hc, result, outcome="open").status_code == 422
    assert update(client, hc, result, outcome="open", note="Further review requested.").status_code == 200


@pytest.mark.parametrize("who", ["demo-yousef", "demo-mariam", "demo-omar"])
def test_other_roles_have_no_access(journey, client, login, who):
    _, _, j = journey
    h = login(who)
    assert client.get(f"/api/care-journeys/{j['id']}", headers=h).status_code == 404
    assert client.get("/api/care-journeys/participants/demo-fatima", headers=h).status_code == 404
    assert update(client, h, j, next_action="Forged").status_code == 404


def test_patient_is_read_only_and_csrf_required(journey, client):
    hp, hc, j = journey
    assert update(client, hp, j, outcome="resolved", note="x").status_code == 404
    assert client.post(f"/api/care-journeys/{j['id']}", headers={"Cookie": hc["Cookie"]}, json={"expected_revision": 1}).status_code == 403


def test_revocation_hides_journey_but_patient_keeps_it(journey, client):
    hp, hc, j = journey
    g = next(g for g in client.get("/api/grants", headers=hp).json() if g["purpose"] == "clinical_review")
    assert client.post(f"/api/grants/{g['id']}/revoke", headers=hp).status_code == 200
    assert client.get(f"/api/care-journeys/{j['id']}", headers=hc).status_code == 404
    assert client.get(f"/api/care-journeys/{j['id']}", headers=hp).status_code == 200


def test_another_clinician_cannot_take_over(journey, client, app):
    from conftest import sign_in, REAL_PASSWORD
    from app.models import AccessGrant
    _, _, j = journey
    make_user(app, "another", "another", role="clinician")
    with app.state.db.SessionLocal() as db:
        db.add(AccessGrant(owner_id="demo-fatima", grantee_id="another", purpose="clinical_review")); db.commit()
    h = sign_in(client, "another", REAL_PASSWORD)
    assert client.get(f"/api/care-journeys/{j['id']}", headers=h).status_code == 404
    assert client.post(f"/api/care-journeys/from-concern/{j['concern_id']}", headers=h).status_code == 404


def test_reviewed_analysis_is_linked_and_source_change_is_visible(journey, client, app):
    _, hc, j = journey
    run = reviewed_run(client, hc)
    linked = update(client, hc, j, analysis_run_id=run["run_id"]).json()
    assert linked["analysis"]["source_status"] == "current" and linked["analysis"]["review_unchanged"]
    with app.state.db.SessionLocal() as db:
        e = db.scalar(select(Evidence).where(Evidence.participant_id == "demo-fatima")); e.quality = "unusable"; db.commit()
    now = client.get(f"/api/care-journeys/{j['id']}", headers=hc).json()
    assert now["analysis"]["source_status"] == "changed"
    assert update(client, hc, linked, analysis_run_id=run["run_id"]).status_code == 409
    assert update(client, hc, linked, next_action="Recheck records").status_code == 200


def test_draft_analysis_cannot_be_linked_and_stale_review_is_blocked(journey, client, app):
    _, hc, j = journey
    run = client.post("/api/activity-analysis/participants/demo-fatima/runs", headers=hc, json={"range_days": 183}).json()
    assert update(client, hc, j, analysis_run_id=run["run_id"]).status_code == 409
    with app.state.db.SessionLocal() as db:
        e = db.scalar(select(Evidence).where(Evidence.participant_id == "demo-fatima")); e.status = "withdrawn"; db.commit()
    r = client.post(f"/api/activity-analysis/runs/{run['run_id']}/review", headers=hc,
                    json={"decisions": [{"kind": "statement", "index": 0, "decision": "keep"}]})
    assert r.status_code == 409


def test_plan_and_patient_reply_do_not_automatically_resolve(journey, client):
    hp, hc, j = journey
    run = reviewed_run(client, hc)
    response = update(client, hc, j, analysis_run_id=run["run_id"])
    assert response.status_code == 200
    j = response.json()
    assert client.post("/api/participants/demo-fatima/care-plan", headers=hc,
                       json={"text_en": "Discuss the diary", "day_part": "anytime", "weekdays": []}).status_code == 200
    plan = client.get("/api/participants/demo-fatima/care-plan", headers=hc).json()["draft_id"]
    linked = update(client, hc, j, plan_id=plan).json()
    assert linked["plan"]["status"] == "draft"
    assert client.post(f"/api/care-plans/{plan}/send", headers=hc).status_code == 200
    assert client.post(f"/api/care-plans/{plan}/respond", headers=hp, json={"response": "accept"}).status_code == 200
    item = client.get("/api/care-plan/today", headers=hp).json()["items"][0]
    assert client.post(f"/api/care-plan/{item['id']}/reply", headers=hp, json={"reply": "done"}).status_code == 200
    refreshed = client.get(f"/api/care-journeys/{j['id']}", headers=hc).json()
    assert refreshed["plan"]["status"] == "accepted" and refreshed["responses"]["done"] == 1
    assert refreshed["outcome"] == "open" and refreshed["concern_status"] == "delivered"
    followed = update(client, hc, refreshed, outcome="follow_up_required", next_action="Discuss the recorded response",
                      follow_up_on="2026-12-01", note="Response reviewed; follow-up arranged.")
    assert followed.status_code == 200
    patient_view = client.get(f"/api/care-journeys/{j['id']}", headers=hp).json()
    assert patient_view["outcome"] == "follow_up_required"
    assert patient_view["events"][-1]["note"] == "Response reviewed; follow-up arranged."


def test_audit_has_no_notes_and_get_calls_no_model(journey, client, app, monkeypatch):
    from app import agent_runtime
    _, hc, j = journey
    monkeypatch.setattr(agent_runtime, "invoke", lambda *a, **k: (_ for _ in ()).throw(AssertionError("model called")))
    assert update(client, hc, j, next_action="PRIVATE-ACTION", note="PRIVATE-NOTE").status_code == 200
    assert client.get(f"/api/care-journeys/{j['id']}", headers=hc).status_code == 200
    assert client.get("/api/activity-analysis/participants/demo-fatima/coverage", headers=hc).status_code == 200
    with app.state.db.SessionLocal() as db:
        logs = str([(a.action, a.target) for a in db.scalars(select(AuditEvent))])
        assert "PRIVATE" not in logs
        assert len(list(db.scalars(select(CareJourneyEvent)))) == 2
