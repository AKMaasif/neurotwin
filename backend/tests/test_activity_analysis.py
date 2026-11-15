"""Analyze activity history: stages, evidence links, guardrails, access, and what is (not) sent to a model."""
import json
from datetime import date

import pytest
from sqlalchemy import select

from app import activity_analysis as AA
from app import agent_runtime as R
from app import synthetic_history as H
from app import validator as V
from app.models import AccessGrant, AuditEvent, User

PID = "demo-fatima"


@pytest.fixture(autouse=True)
def _env(tmp_path, monkeypatch):
    monkeypatch.setenv("NEUROTWIN_ACTIVITY_RUNS", str(tmp_path / "runs"))
    monkeypatch.setenv("NEUROTWIN_AGENTS_MODE", "mock")


@pytest.fixture()
def seeded(app):
    with app.state.db.SessionLocal() as db:
        H.apply(db, ref_date=date(2026, 11, 10))
    return app


def clin(client):
    r = client.post("/api/auth/demo-enter", json={"username": "dr.layla"})
    assert r.status_code == 200
    return {"X-CSRF-Token": r.json()["csrf"]}


def start(client, h, pid=PID, days=183):
    r = client.post(f"/api/activity-analysis/participants/{pid}/runs", json={"range_days": days}, headers=h)
    assert r.status_code == 200, r.text
    got = client.get(f"/api/activity-analysis/runs/{r.json()['run_id']}")
    assert got.status_code == 200
    return got.json()


def stage(run, sid):
    return next(s for s in run["stages"] if s["id"] == sid)


class Scripted:
    """A stand-in model client that returns whatever text it is given, and counts calls."""
    def __init__(self, text, provider="gemini"):
        self.text, self.provider, self.model, self.calls = text, provider, "fake-model", 0

    def complete(self, system, user, json_mode=False, images=None):
        from app import llm
        self.calls += 1
        return llm.Reply(self.text, self.provider, self.model)


def test_full_run_in_mock_mode_has_ten_stages_of_three_kinds(seeded, client):
    run = start(client, clin(client))
    assert run["run_id"].startswith("ah-") and run["state"] == "awaiting_review"
    assert [s["id"] for s in run["stages"]] == [i for i, _, _ in AA.STAGES]
    kinds = {s["id"]: s["kind"] for s in run["stages"]}
    assert kinds["ledger"] == "software" and kinds["summarise"] == "ai" and kinds["review"] == "human"
    assert all(stage(run, i)["status"] == "completed" for i in ("collect", "quality", "describe", "ledger", "summarise", "challenge", "check", "validate", "charts"))
    assert stage(run, "review")["status"] == "waiting"                 # nothing is final before a clinician decides
    assert run["review_state"] == "ai_draft_not_reviewed" and run["gate"]["passed"] is True
    assert stage(run, "summarise")["scripted"] is True and stage(run, "summarise")["prompt_version"] == AA.PROMPTS["summariser"]


def test_every_statement_cites_facts_and_only_uses_their_numbers(seeded, client):
    run = start(client, clin(client))
    facts = [V.Fact.of(f["id"], f["text"]) for f in run["ledger"]["facts"]]
    stmts = [V.Statement(s["text"], s["cites"]) for s in run["summary"]["statements"]]
    assert stmts and V.check(stmts, facts).ok
    assert any("F-uncertainty" in s.cites for s in stmts)
    for key in ("doubts", "questions"):
        assert V.check([V.Statement(x["text"], x["cites"]) for x in run["challenge"][key]], facts).ok


def test_facts_carry_no_name_no_condition_and_no_score(seeded, client):
    run = start(client, clin(client))
    text = " ".join(f["text"] for f in run["ledger"]["facts"])
    assert "فاطمة" not in text and "Fatima" not in text and PID not in text
    assert not V._banned(text)                                  # the facts themselves use none of the refused wording
    assert not any(w in text.lower() for w in ("composite", "brain health score", "failed"))
    assert text.lower().count("missed") == text.lower().count("not a missed")        # "missed" only ever appears in a denial
    ids = [f["id"] for f in run["ledger"]["facts"]]
    assert "F-uncertainty" in ids and "F-quality" in ids and any(i.startswith("F-m-") for i in ids)
    who5 = [f for f in run["ledger"]["facts"] if "who5" in f["id"] or "who5" in f["text"]]
    assert all("difference" not in f["text"] for f in who5)    # WHO-5 gets no change estimate


def test_a_gap_is_described_as_a_gap_not_a_miss(seeded, client):
    run = start(client, clin(client))
    gap = next(f for f in run["ledger"]["facts"] if f["id"] == "F-gap")
    assert "not a missed activity" in gap["text"]
    routine = next((f for f in run["ledger"]["facts"] if f["id"] == "F-routine"), None)
    if routine:
        assert "not a missed routine" in routine["text"]


def test_only_the_numbered_facts_were_sent_and_the_call_was_recorded(seeded, client, tmp_path):
    run = start(client, clin(client))
    rdir = tmp_path / "runs" / run["run_id"]
    egress = R.read(rdir, "egress.jsonl")
    trace = R.read(rdir, "agents.jsonl")
    assert {e["agent"] for e in egress} == {"AH-summariser", "AH-challenger", "AH-checker", "AH-charts"}
    assert all(e["data"] == "ledger facts (text)" and e["images"] == 0 and e["sent_outside"] is False for e in egress)   # mock: nothing left the server
    assert all(t["provider"].startswith("mock") and t.get("prompt_sha256") for t in trace if t["status"] == "completed")


def test_no_get_endpoint_ever_calls_a_model(seeded, client, monkeypatch):
    h = clin(client)
    run = start(client, h)
    monkeypatch.setattr(R, "invoke", lambda *a, **k: (_ for _ in ()).throw(AssertionError("a model was called")))
    assert client.get("/api/activity-analysis/roster").status_code == 200
    assert client.get(f"/api/activity-analysis/participants/{PID}/runs").status_code == 200
    assert client.get(f"/api/activity-analysis/runs/{run['run_id']}").status_code == 200
    assert client.get("/api/system/status").status_code == 200


def test_off_mode_runs_the_software_stages_and_invents_nothing(seeded, client, monkeypatch):
    monkeypatch.setenv("NEUROTWIN_AGENTS_MODE", "off")
    run = start(client, clin(client))
    assert stage(run, "ledger")["status"] == "completed"
    for sid in ("summarise", "challenge", "charts"):
        assert stage(run, sid)["status"] == "unavailable"
    assert run["summary"]["statements"] == [] and run["challenge"]["doubts"] == [] and run["charts"]["charts"] == []
    assert run["gate"]["passed"] is False and stage(run, "check")["status"] == "skipped"


def test_real_participant_data_is_not_sent_to_a_live_provider(seeded, client, monkeypatch):
    monkeypatch.setenv("NEUROTWIN_AGENTS_MODE", "live")
    with seeded.state.db.SessionLocal() as db:
        db.get(User, PID).is_demo = False
        db.commit()
    fake = Scripted('{"statements": []}')
    monkeypatch.setattr(R, "client_for", lambda provider, env=None: fake)
    run = start(client, clin(client))
    assert fake.calls == 0
    assert stage(run, "summarise")["status"] == "unavailable" and "not sent" in stage(run, "summarise")["summary"]


def test_a_draft_with_a_condition_an_unknown_fact_or_a_new_number_is_refused_and_stays_visible(seeded, client, monkeypatch):
    bad = json.dumps({"statements": [
        {"text": "This pattern suggests early dementia.", "cites": ["F-quality"]},
        {"text": "Reaction time rose by 999 ms.", "cites": ["F-quality"]},
        {"text": "Sleep was short.", "cites": ["F-made-up"]}]})
    fake = Scripted(bad)
    monkeypatch.setattr(R, "client_for", lambda provider, env=None: fake if provider == "gemini" else None)
    run = start(client, clin(client))
    sm = run["summary"]
    assert sm["status"] == "refused" and len(sm["statements"]) == 3                 # shown as refused, not dropped
    codes = {p["code"] for p in sm["validator"]["problems"]}
    assert {"clinical_claim", "unsupported_number", "unknown_citation"} <= codes
    assert fake.calls >= 2                                                           # it was asked to try again once
    assert run["gate"]["passed"] is False and stage(run, "validate")["status"] == "blocked"
    assert stage(run, "check")["status"] == "skipped"


def test_chart_proposals_are_validated_and_only_known_measures_are_kept(seeded, client, monkeypatch):
    spec = json.dumps({"charts": [
        {"measure": "rt_median_ms", "range": "3m", "why": "See the reaction records.", "cites": ["F-m-rt_median_ms"]},
        {"measure": "brain_health_score", "range": "all", "why": "x", "cites": ["F-quality"]},
        {"measure": "sleep_hours", "range": "forever", "why": "x", "cites": ["F-quality"]},
        {"measure": "sleep_quality", "range": "all", "why": "This shows risk of decline.", "cites": ["F-m-sleep_quality"]},
        {"measure": "rounds_correct", "range": "6m", "why": "Memory rounds over time.", "cites": ["F-m-rounds_correct"]}]})
    fake = Scripted(spec)
    monkeypatch.setattr(R, "client_for", lambda provider, env=None: fake if provider == "gemini" else None)
    run = start(client, clin(client))
    charts = run["charts"]
    assert [c["measure"] for c in charts["charts"]] == ["rt_median_ms", "rounds_correct"]
    reasons = " ".join(d["reason"] for d in charts["dropped"])
    assert "Not a measure" in reasons and "allowed range" in reasons and "refused" in reasons


def test_roster_names_every_stage_and_never_calls_a_key_verification(seeded, client, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "secret-key-value-123")
    monkeypatch.setenv("NEUROTWIN_AGENTS_MODE", "live")
    clin(client)
    r = client.get("/api/activity-analysis/roster")
    assert "secret-key-value-123" not in r.text
    d = r.json()
    assert [s["kind"] for s in d["stages"]].count("ai") == 4 and d["mode"] == "live"
    assert all(s["verified"] is False for s in d["stages"] if s["kind"] == "ai")     # a key is not a verified capability
    R.record_check("gemini", True)
    d = client.get("/api/activity-analysis/roster").json()
    assert d["providers"]["gemini"]["verified"] is True and d["providers"]["meta"]["verified"] is False


def test_roster_in_mock_mode_is_never_verified(seeded, client):
    clin(client)
    d = client.get("/api/activity-analysis/roster").json()
    assert d["mode"] == "mock" and all(p["scripted"] and not p["verified"] for p in d["providers"].values())


def test_access_rules(seeded, client, login):
    h = clin(client)
    run = start(client, h)
    rid = run["run_id"]
    # other roles
    client.post("/api/auth/demo-enter", json={"username": "fatima"})
    assert client.get(f"/api/activity-analysis/runs/{rid}").status_code == 404
    assert client.post(f"/api/activity-analysis/participants/{PID}/runs", json={"range_days": 91}, headers={"X-CSRF-Token": "x"}).status_code in (403, 404)
    client.post("/api/auth/demo-enter", json={"username": "mariam"})
    assert client.get("/api/activity-analysis/roster").status_code == 404
    # a clinician whose grant was withdrawn
    client.post("/api/auth/demo-enter", json={"username": "dr.layla"})
    with seeded.state.db.SessionLocal() as db:
        g = db.scalar(select(AccessGrant).where(AccessGrant.owner_id == PID, AccessGrant.grantee_id == "demo-dr-layla", AccessGrant.purpose == "clinical_review"))
        from datetime import datetime, timezone
        g.revoked_at = datetime.now(timezone.utc)
        db.commit()
    assert client.get(f"/api/activity-analysis/runs/{rid}").status_code == 404
    assert client.get(f"/api/activity-analysis/participants/{PID}/runs").status_code == 404
    # shapes of ids
    assert client.get("/api/activity-analysis/runs/..%2f..%2fetc").status_code == 404
    assert client.get("/api/activity-analysis/runs/ah-000000000000").status_code == 404


def test_starting_and_reviewing_are_audited_and_review_needs_a_real_decision(seeded, client):
    h = clin(client)
    run = start(client, h)
    rid = run["run_id"]
    bad = client.post(f"/api/activity-analysis/runs/{rid}/review", json={"decisions": [{"kind": "statement", "index": 99, "decision": "keep"}], "note": ""}, headers=h)
    assert bad.status_code == 422
    unknown = client.post(f"/api/activity-analysis/runs/{rid}/review", json={"decisions": [{"kind": "statement", "index": 0, "decision": "approve"}], "note": ""}, headers=h)
    assert unknown.status_code == 422
    ok = client.post(f"/api/activity-analysis/runs/{rid}/review", headers=h, json={"note": "Read against the records.", "decisions": [
        {"kind": "statement", "index": 0, "decision": "keep"}, {"kind": "statement", "index": 1, "decision": "discard", "note": "not needed"}]})
    assert ok.status_code == 200 and ok.json()["review_state"] == "reviewed_by_clinician" and ok.json()["state"] == "reviewed"
    assert stage(ok.json(), "review")["status"] == "completed"
    again = client.post(f"/api/activity-analysis/runs/{rid}/review", json={"decisions": [], "note": ""}, headers=h)
    assert again.status_code == 422
    with seeded.state.db.SessionLocal() as db:
        actions = [a.action for a in db.scalars(select(AuditEvent))]
    assert "activity_analysis.start" in actions and "activity_analysis.review" in actions


def test_a_person_with_no_records_gets_a_quiet_run_and_no_model_call(app, client, monkeypatch):
    monkeypatch.setattr(R, "invoke", lambda *a, **k: (_ for _ in ()).throw(AssertionError("a model was called")))
    h = clin(client)
    with app.state.db.SessionLocal() as db:       # Yousef has no activity in a fresh demo database; give the clinician a grant
        db.add(AccessGrant(owner_id="demo-yousef", grantee_id="demo-dr-layla", purpose="clinical_review"))
        db.commit()
    run = start(client, h, pid="demo-yousef")
    assert stage(run, "collect")["status"] == "completed" and stage(run, "summarise")["status"] == "skipped"
    assert run["state"] == "completed"


def test_range_must_be_one_of_the_offered_ones(seeded, client):
    h = clin(client)
    r = client.post(f"/api/activity-analysis/participants/{PID}/runs", json={"range_days": 5}, headers=h)
    assert r.status_code == 422


def test_run_ids_are_their_own_kind_and_unguessable_shape(seeded, client):
    ids = {start(client, clin(client))["run_id"] for _ in range(3)}
    assert len(ids) == 3 and all(AA.RUN_ID.match(i) for i in ids)
