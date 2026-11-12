import json

import pytest

from app import agent_explainer as X
from app import agent_family as FA
from app import agent_review as RW
from app import agent_runtime as R
from app import llm
from conftest import consent
from test_agent_ledger import RUN


class Fake:
    provider = "gemini"

    def __init__(self, text):
        self.text, self.model = text, "g-t"

    def complete(self, system, user, json_mode=False, images=None):
        t = self.text.pop(0) if isinstance(self.text, list) else self.text
        return llm.Reply(t, self.provider, self.model)


def sts(*pairs):
    return json.dumps({"statements": [{"text": t, "cites": c} for t, c in pairs]})


GOOD = sts(("Two scans of the same person, taken about 12 months apart, were compared.", ["F-interval"]),
           ("How reliable the measurements are is not known yet.", ["F-uncertainty"]),
           ("The clinician will talk through what this means with you.", ["F-uncertainty"]))


@pytest.fixture(autouse=True)
def reset(monkeypatch, tmp_path):
    R._cap.update({"day": None, "n": 0})
    monkeypatch.delenv("NEUROTWIN_AGENTS_MODE", raising=False)
    monkeypatch.setenv("NEUROTWIN_IMAGING_ROOT", str(tmp_path / "imaging"))


def run():
    r = json.loads(json.dumps(RUN)); r["earlier"], r["later"], r["state"] = "E1", "L1", "complete"
    r["validation"]["status"] = "ok"; r["validation"]["checks"] = {}
    return r


@pytest.fixture
def rd(tmp_path):
    from app import agent_analysis as A
    d = A.runs_root() / "r1"; d.mkdir(parents=True)
    return d


def approve(rd):
    X.explain(run(), rd, a3_client=Fake(sts(("The two scans are 12 months apart.", ["F-interval"]), ("Uncertainty of these volumes is not estimated.", ["F-uncertainty"]))), a4_client=None, env={})
    for i in RW.view(rd)["items"]:
        RW.decide_item(rd, i["id"], "accepted", "demo-dr-layla")
    RW.decide(rd, "approve", "demo-dr-layla")


def setup(client, app, login, rd, share=True, family=True, summary=True, approve_it=True):
    yousef = login("demo-yousef")
    consent(client, yousef)
    if summary:
        consent(client, yousef, scope="family_imaging_summary")
    if share:
        client.post("/api/grants", json={"grantee_id": "demo-dr-layla", "purpose": "clinical_review"}, headers=yousef)
    if family:
        client.post("/api/grants", json={"grantee_id": "demo-mariam", "purpose": "participation_updates"}, headers=yousef)
    if approve_it:
        approve(rd)
    with app.state.db.SessionLocal() as db:
        from app.models import User
        return yousef, db.get(User, "demo-dr-layla"), db.get(User, "demo-mariam")


def test_link_needs_the_participants_clinical_review_grant(client, app, login, rd):
    _, dr, _ = setup(client, app, login, rd, share=False)
    with app.state.db.SessionLocal() as db, pytest.raises(ValueError, match="not shared"):
        FA.link(db, rd, dr, "demo-yousef")


def test_full_release_flow_and_family_sees_it(client, app, login, rd):
    yousef, dr, fam = setup(client, app, login, rd)
    with app.state.db.SessionLocal() as db:
        FA.link(db, rd, dr, "demo-yousef")
        rec = FA.draft(run(), rd, [], client=Fake(GOOD))
        assert rec["status"] == "completed" and rec["release"] is None
        assert all(c["ok"] for c in FA.preconditions(db, rd, "demo-mariam"))
        FA.release(db, rd, dr, "demo-mariam")
    mariam = login("demo-mariam")
    r = client.get("/api/family/imaging-summaries", headers=mariam).json()
    assert r[0]["active"] and len(r[0]["statements"]) == 3 and "not a diagnosis" in r[0]["note"] and "cites" not in json.dumps(r)
    # participant, other family, clinician endpoint
    assert client.get("/api/family/imaging-summaries", headers=yousef).status_code == 403


@pytest.mark.parametrize("missing", ["family", "summary", "approve_it"])
def test_release_is_refused_when_any_condition_is_missing(client, app, login, rd, missing):
    kw = {missing: False}
    yousef, dr, fam = setup(client, app, login, rd, **kw)
    with app.state.db.SessionLocal() as db:
        FA.link(db, rd, dr, "demo-yousef")
        FA.draft(run(), rd, [], client=Fake(GOOD))
        with pytest.raises(ValueError, match="Not released"):
            FA.release(db, rd, dr, "demo-mariam")


def test_withdrawing_consent_grant_or_approval_hides_it_but_keeps_the_record(client, app, login, rd):
    yousef, dr, fam = setup(client, app, login, rd)
    with app.state.db.SessionLocal() as db:
        FA.link(db, rd, dr, "demo-yousef"); FA.draft(run(), rd, [], client=Fake(GOOD)); FA.release(db, rd, dr, "demo-mariam")
    mariam = login("demo-mariam")
    live = lambda: client.get("/api/family/imaging-summaries", headers=mariam).json()[0]  # noqa: E731
    assert live()["active"]
    consent(client, yousef, granted=False, scope="family_imaging_summary")
    e = live()
    assert not e["active"] and e["statements"] == [] and "not available" in e["note"]
    consent(client, yousef, scope="family_imaging_summary")
    assert live()["active"]                                   # consent can be given again
    RW.decide(rd, "reopen", "demo-dr-layla")
    assert not live()["active"]                               # the clinician reopening hides it
    assert FA._read(rd / FA.FILE)["release"]["by"] == "demo-dr-layla"   # the record is kept


def test_only_the_named_family_member_can_see_it(client, app, login, rd):
    yousef, dr, fam = setup(client, app, login, rd)
    with app.state.db.SessionLocal() as db:
        FA.link(db, rd, dr, "demo-yousef"); FA.draft(run(), rd, [], client=Fake(GOOD)); FA.release(db, rd, dr, "demo-mariam")
    other = client.get("/api/family/imaging-summaries", headers=login("demo-omar"))  # a family member the participant did not authorise
    assert other.status_code == 200 and other.json() == []


def test_a_changed_draft_after_release_is_not_what_family_sees(client, app, login, rd):
    yousef, dr, fam = setup(client, app, login, rd)
    with app.state.db.SessionLocal() as db:
        FA.link(db, rd, dr, "demo-yousef"); FA.draft(run(), rd, [], client=Fake(GOOD)); FA.release(db, rd, dr, "demo-mariam")
        other = sts(("Two scans were compared.", ["F-interval"]), ("How reliable the measurements are is not known.", ["F-uncertainty"]), ("Please talk to the clinician about it.", ["F-uncertainty"]))
        FA.draft(run(), rd, [], client=Fake(other))
    assert FA._read(rd / FA.FILE)["release"] is None and FA._read(rd / FA.FILE)["releases_history"]
    assert client.get("/api/family/imaging-summaries", headers=login("demo-mariam")).json() == []


@pytest.mark.parametrize("bad,code", [
    (sts(("It grew by 37 mm3.", ["F-interval"]), ("Not known.", ["F-uncertainty"]), ("Ask the clinician.", ["F-uncertainty"])), "jargon"),
    (sts(("This looks serious.", ["F-interval"]), ("Not known.", ["F-uncertainty"]), ("Ask the clinician.", ["F-uncertainty"])), "tone"),
    (sts(("Two scans were compared.", ["F-interval"]), ("It is all normal.", ["F-interval"]), ("Ask the clinician.", ["F-uncertainty"])), "normative_claim"),
    (sts(("Two scans were compared.", ["F-interval"]), ("Nothing to worry about.", ["F-uncertainty"]), ("Ask the clinician.", ["F-uncertainty"])), "reassurance"),
    (sts(("Two scans were compared.", ["F-interval"]), ("Reliability is not known.", ["F-uncertainty"]), ("That is all.", ["F-interval"])), "no_invitation"),
    (sts(("Two scans were compared.", ["F-interval"]), ("Please ask the clinician.", ["F-interval"]), ("Please ask the clinician again.", ["F-interval"])), "uncertainty_dropped"),
    (sts(("Two scans were compared 99 months apart.", ["F-interval"]), ("Not known.", ["F-uncertainty"]), ("Ask the clinician.", ["F-uncertainty"])), "unsupported_number"),
])
def test_family_draft_rules(rd, bad, code):
    rec = FA.draft(run(), rd, [], client=Fake(bad))
    assert rec["status"] == "refused" and code in {p["code"] for p in rec["validator"]["problems"]}


def test_selected_facts_are_limited_and_only_those_are_sent(rd):
    with pytest.raises(ValueError):
        FA.draft(run(), rd, ["F-R4", "F-R43", "F-total"], client=Fake(GOOD))
    with pytest.raises(ValueError):
        FA.draft(run(), rd, ["F-limit1"], client=Fake(GOOD))
    FA.draft(run(), rd, ["F-total"], client=Fake(GOOD))
    eg = R.read(rd, R.EGRESS)[-1]
    assert set(eg["fact_ids"]) == {"F-interval", "F-uncertainty", "F-total"}


def test_draft_without_provider_is_unavailable(rd):
    assert FA.draft(run(), rd, [], env={})["status"] == "unavailable"


def test_audit_records_release_and_family_view(client, app, login, rd):
    yousef, dr, fam = setup(client, app, login, rd)
    with app.state.db.SessionLocal() as db:
        FA.link(db, rd, dr, "demo-yousef"); FA.draft(run(), rd, [], client=Fake(GOOD)); FA.release(db, rd, dr, "demo-mariam")
    client.get("/api/family/imaging-summaries", headers=login("demo-mariam"))
    with app.state.db.SessionLocal() as db:
        from app.models import AuditEvent
        actions = {a.action for a in db.query(AuditEvent)}
    assert {"imaging.linked", "imaging.family_released", "family.viewed_imaging_summary"} <= actions
