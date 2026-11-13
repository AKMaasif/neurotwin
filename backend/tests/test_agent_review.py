import json

import pytest

from app import agent_activity as AC
from app import agent_explainer as X
from app import agent_followup as F
from app import agent_review as RW
from app import agent_runtime as R
from app import llm
from test_agent_ledger import RUN


class Fake:
    provider = "gemini"

    def __init__(self, text):
        self.text, self.model = text, "g-t"

    def complete(self, system, user, json_mode=False, images=None):
        t = self.text.pop(0) if isinstance(self.text, list) else self.text
        return llm.Reply(t, self.provider, self.model)


@pytest.fixture(autouse=True)
def reset(monkeypatch):
    R._cap.update({"day": None, "n": 0})
    monkeypatch.delenv("NEUROTWIN_AGENTS_MODE", raising=False)


@pytest.fixture
def rd(tmp_path):
    d = tmp_path / "r1"; d.mkdir()
    return d


def run():
    r = json.loads(json.dumps(RUN)); r["earlier"], r["later"], r["state"] = "E1", "L1", "complete"
    r["steps"] = [{"key": k, "state": "done", "label": k, "detail": ""} for k in ("pair_validation", "alignment", "quality_review", "anatomical_analysis", "longitudinal_comparison", "findings_review", "report")]
    r["validation"]["status"] = "ok"; r["validation"]["checks"] = {}
    return r


def items(*pairs):
    return json.dumps({"items": [{"text": t, "cites": c} for t, c in pairs]})


GOOD = items(("Consider checking whether a repeat scan with the same protocol exists.", ["F-limit1"]),
             ("It may help to ask how large the measurement noise of this segmentation is.", ["F-uncertainty"]),
             ("Consider looking at the regions marked uncertain first.", ["F-uncertainty", "F-seg"]))


def test_followup_happy_path(rd):
    rec = F.plan(run(), rd, client=Fake(GOOD))
    assert rec["status"] == "completed" and len(rec["items"]) == 3 and rec["review_state"] == "ai_draft_not_reviewed"
    assert F.load(rd)["status"] == "completed"


@pytest.mark.parametrize("text", ["Refer him to a specialist.", "Book a scan within 3 months.", "This is urgent.", "Do not worry about this.", "Consider stopping the medication.", "Consider it normal."])
def test_followup_refuses_directives_urgency_treatment_and_norms(rd, text):
    bad = items((text, ["F-limit1"]), ("Consider a.", ["F-uncertainty"]), ("Consider b.", ["F-uncertainty"]))
    rec = F.plan(run(), rd, client=Fake(bad))
    assert rec["status"] == "refused" and rec["validator"]["problems"]


def test_followup_item_must_trace_to_a_limitation_or_flag(rd):
    bad = items(("Consider rescanning.", ["F-interval"]), ("Consider a.", ["F-uncertainty"]), ("Consider b.", ["F-uncertainty"]))
    rec = F.plan(run(), rd, client=Fake(bad))
    assert any(p["code"] == "not_traceable" for p in rec["validator"]["problems"])


def test_followup_count_and_retry(rd):
    few = items(("Consider a.", ["F-uncertainty"]))
    rec = F.plan(run(), rd, client=Fake([few, GOOD]))
    assert rec["attempts"] == 2 and rec["status"] == "completed"


def test_followup_without_provider(rd):
    rec = F.plan(run(), rd, env={})
    assert rec["status"] == "unavailable" and rec["items"] == []


def drafts(rd):
    F.plan(run(), rd, client=Fake(GOOD))
    X.explain(run(), rd, a3_client=Fake(json.dumps({"statements": [
        {"text": "The two scans are 12 months apart.", "cites": ["F-interval"]},
        {"text": "Uncertainty of these volumes is not estimated, so every difference is uncertain.", "cites": ["F-uncertainty"]}]})), a4_client=None, env={})


def test_items_appear_and_regeneration_makes_new_undecided_items(rd):
    drafts(rd)
    v = RW.view(rd)
    assert {i["kind"] for i in v["items"]} == {"explanation", "followup"} and v["undecided"] == 5 and v["state"] == "ai_drafts"
    first = v["items"][0]["id"]
    v = RW.decide_item(rd, first, "accepted", "dr1")
    assert v["state"] == "in_review" and v["accepted"] == 1 and v["undecided"] == 4
    F.plan(run(), rd, client=Fake(items(("Consider a different thing entirely.", ["F-uncertainty"]), ("Consider b.", ["F-uncertainty"]), ("Consider c.", ["F-uncertainty"]))))
    assert RW.view(rd)["accepted"] == 1  # the explanation decision stays, the new follow-up items are undecided
    assert RW.view(rd)["undecided"] == 4


def test_cannot_approve_with_undecided_items_and_return_needs_a_comment(rd):
    drafts(rd)
    with pytest.raises(ValueError, match="still have no decision"):
        RW.decide(rd, "approve", "dr1")
    with pytest.raises(ValueError, match="what should change"):
        RW.decide(rd, "return", "dr1", " ")


def test_approve_records_who_and_fingerprint_and_updates_the_graph(rd):
    drafts(rd)
    for i in RW.view(rd)["items"]:
        RW.decide_item(rd, i["id"], "rejected" if i["kind"] == "followup" else "accepted", "dr1")
    v = RW.decide(rd, "approve", "dr1", "Reviewed.")
    assert v["state"] == "approved" and v["approval"]["by"] == "dr1" and len(v["approval"]["accepted"]) == 2 and RW.approved(rd)
    ev = [e for e in AC.read_events(rd) if e["node"] == "clinician_review"]
    assert ev[-1]["status"] == "completed" and "not a clinical approval" in ev[-1]["summary"]
    act = {n["id"]: n["status"] for n in AC.activity(run(), rd)["nodes"]}
    assert act["clinician_review"] == "completed"


def test_regenerating_a_draft_after_approval_voids_it(rd):
    drafts(rd)
    for i in RW.view(rd)["items"]:
        RW.decide_item(rd, i["id"], "accepted", "dr1")
    RW.decide(rd, "approve", "dr1")
    assert RW.approved(rd)
    X.explain(run(), rd, a3_client=Fake(json.dumps({"statements": [
        {"text": "The two scans are about a year apart.", "cites": ["F-interval"]},
        {"text": "Uncertainty of these volumes is not estimated.", "cites": ["F-uncertainty"]}]})), a4_client=None, env={})
    v = RW.view(rd)
    assert v["state"] == "approval_outdated" and v["approval_outdated"] and not RW.approved(rd)


def test_return_and_reopen(rd):
    drafts(rd)
    v = RW.decide(rd, "return", "dr1", "Please check the ventricle wording.")
    assert v["state"] == "returned" and v["approval"]["comment"].startswith("Please")
    assert RW.decide(rd, "reopen", "dr1")["approval"] is None
    assert [h["event"] for h in RW.view(rd)["history"]] == ["return", "reopen"]


def test_unknown_item_or_decision_is_refused(rd):
    drafts(rd)
    with pytest.raises(ValueError):
        RW.decide_item(rd, "explanation:nope", "accepted", "dr1")
    with pytest.raises(ValueError):
        RW.decide_item(rd, RW.view(rd)["items"][0]["id"], "maybe", "dr1")
