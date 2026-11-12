import json

import pytest

from app import agent_activity as AC
from app import agent_explainer as X
from app import agent_runtime as R
from app import llm
from test_agent_ledger import RUN


class Fake:
    def __init__(self, provider, text, fail=False):
        self.provider, self.model, self.text, self.fail, self.calls = provider, f"{provider}-test", text, fail, 0

    def complete(self, system, user, json_mode=False):
        self.calls += 1
        if self.fail:
            raise llm.ModelError(f"{self.provider} answered HTTP 500.")
        return llm.Reply(self.text(user) if callable(self.text) else self.text, self.provider, self.model)


GOOD = json.dumps({"statements": [
    {"text": "The two scans are 12 months apart.", "cites": ["F-interval"]},
    {"text": "The left lateral ventricle measured 2000 mm3 earlier and 2200 mm3 later.", "cites": ["F-R4"]},
    {"text": "Uncertainty of these volumes is not estimated, so every difference is uncertain.", "cites": ["F-uncertainty"]}]})
INVENTED = json.dumps({"statements": [{"text": "The left lateral ventricle grew by 37 mm3.", "cites": ["F-R4"]},
                                      {"text": "Uncertainty of these volumes is not estimated.", "cites": ["F-uncertainty"]}]})
ALL_OK = lambda user: json.dumps({"checks": [{"index": i, "supported": True, "reason": "ok"} for i in range(user.count("Statement "))]})  # noqa: E731


@pytest.fixture(autouse=True)
def reset(monkeypatch):
    R._cap.update({"day": None, "n": 0})
    monkeypatch.delenv("NEUROTWIN_AGENTS_MODE", raising=False)


@pytest.fixture
def rd(tmp_path):
    d = tmp_path / "r1"
    d.mkdir()
    return d


def run():
    return json.loads(json.dumps(RUN))


def test_happy_path_is_checked_gated_and_stored(rd):
    a4 = Fake("meta", ALL_OK)
    rec = X.explain(run(), rd, a3_client=Fake("gemini", GOOD), a4_client=a4)
    assert rec["explanation"]["status"] == "completed" and rec["cross_check"]["status"] == "completed" and rec["qa"]["passed"]
    assert rec["review_state"] == "ai_draft_not_reviewed" and "Not a diagnosis" in rec["note"]
    assert X.load(rd)["qa"]["passed"] and len(R.read(rd, R.TRACE)) == 2 and len(R.read(rd, R.EGRESS)) == 2
    assert all(e["images"] == 0 for e in R.read(rd, R.EGRESS))


def test_invented_number_is_refused_twice_and_never_cross_checked(rd):
    a3, a4 = Fake("gemini", INVENTED), Fake("meta", ALL_OK)
    rec = X.explain(run(), rd, a3_client=a3, a4_client=a4)
    assert a3.calls == 2 and a4.calls == 0
    assert rec["explanation"]["status"] == "refused" and any(p["code"] == "unsupported_number" for p in rec["explanation"]["validator"]["problems"])
    assert rec["cross_check"]["status"] == "skipped" and not rec["qa"]["passed"]
    assert rec["explanation"]["statements"]  # kept visible as refused, not dropped


def test_second_attempt_can_fix_the_draft(rd):
    seq = iter([INVENTED, GOOD])
    rec = X.explain(run(), rd, a3_client=Fake("gemini", lambda u: next(seq)), a4_client=Fake("meta", ALL_OK))
    assert rec["explanation"]["attempts"] == 2 and rec["qa"]["passed"]


def test_forbidden_wording_is_refused(rd):
    bad = json.dumps({"statements": [{"text": "This pattern is typical of Alzheimer's disease.", "cites": ["F-total"]}]})
    rec = X.explain(run(), rd, a3_client=Fake("gemini", bad), a4_client=Fake("meta", ALL_OK))
    codes = {p["code"] for p in rec["explanation"]["validator"]["problems"]}
    assert "clinical_claim" in codes and not rec["qa"]["passed"]


def test_checker_disagreement_blocks_qa_but_keeps_text(rd):
    no = lambda user: json.dumps({"checks": [{"index": 0, "supported": True, "reason": ""}, {"index": 1, "supported": False, "reason": "direction"}, {"index": 2, "supported": True, "reason": ""}]})  # noqa: E731
    rec = X.explain(run(), rd, a3_client=Fake("gemini", GOOD), a4_client=Fake("meta", no))
    assert not rec["qa"]["passed"] and "statement(s) 2" in next(c["detail"] for c in rec["qa"]["checks"] if c["name"] == "Independent cross-check")
    assert len(rec["explanation"]["statements"]) == 3


def test_missing_meta_gives_unchecked_warning_not_a_pass_claim(rd):
    rec = X.explain(run(), rd, a3_client=Fake("gemini", GOOD), a4_client=None, env={})
    assert rec["cross_check"]["status"] == "unavailable" and rec["qa"]["passed"]
    chk = next(c for c in rec["qa"]["checks"] if c["name"] == "Independent cross-check")
    assert chk.get("warning") and "Not cross-checked" in chk["detail"]


def test_malformed_checker_reply_is_failed_not_supported(rd):
    rec = X.explain(run(), rd, a3_client=Fake("gemini", GOOD), a4_client=Fake("meta", "not json"))
    assert rec["cross_check"]["status"] == "failed" and rec["qa"]["passed"] and rec["qa"]["checks"][-1].get("warning")


def test_provider_failure_gives_no_text(rd):
    rec = X.explain(run(), rd, a3_client=Fake("gemini", "", fail=True), a4_client=Fake("meta", ALL_OK))
    assert rec["explanation"]["status"] == "failed" and rec["explanation"]["statements"] == [] and not rec["qa"]["passed"]


def test_missing_uncertainty_statement_blocks(rd):
    only = json.dumps({"statements": [{"text": "The two scans are 12 months apart.", "cites": ["F-interval"]}]})
    rec = X.explain(run(), rd, a3_client=Fake("gemini", only), a4_client=Fake("meta", ALL_OK))
    assert not rec["qa"]["passed"] and any(c["name"] == "Uncertainty stated" and not c["ok"] for c in rec["qa"]["checks"])


def test_run_without_measurements_is_refused(rd):
    r = run(); r["measurements"] = None
    with pytest.raises(ValueError):
        X.explain(r, rd, a3_client=Fake("gemini", GOOD))


def test_mock_mode_is_labelled_scripted(rd, monkeypatch):
    monkeypatch.setenv("NEUROTWIN_AGENTS_MODE", "mock")
    rec = X.explain(run(), rd)
    assert rec["explanation"]["scripted"] is True and rec["explanation"]["provider"] == "mock-gemini"
    assert all(e["sent_outside"] is False for e in R.read(rd, R.EGRESS))


def test_agent_events_keep_their_status_when_the_run_is_synced_again(rd):
    run_ = run(); run_["run_id"] = "r1"
    run_["state"] = "complete"; run_["earlier"], run_["later"] = "E1", "L1"
    run_["steps"] = [{"key": k, "state": "done", "label": k, "detail": ""} for k in
                     ("pair_validation", "alignment", "quality_review", "anatomical_analysis", "longitudinal_comparison", "findings_review", "report")]
    run_["validation"]["status"] = "ok"; run_["validation"]["checks"] = {}
    X.explain(run_, rd, a3_client=Fake("gemini", GOOD), a4_client=Fake("meta", ALL_OK))
    AC.sync(rd, run_)
    ev = [e for e in AC.read_events(rd) if e["node"] in ("evidence_explanation", "report_review_ai") and e["type"] == "status"]
    assert ev[-1]["origin"] == "agent" or ev[-2]["origin"] == "agent"
    again = len(AC.read_events(rd)); AC.sync(rd, run_)
    assert len(AC.read_events(rd)) == again  # idempotent: a second sync adds nothing
    act = {n["id"]: n["status"] for n in AC.activity(run_, rd)["nodes"]}
    assert act["evidence_explanation"] == "completed" and act["report_review_ai"] == "completed"


def test_scripted_cross_check_is_never_reported_as_a_real_check(rd, monkeypatch):
    monkeypatch.setenv("NEUROTWIN_AGENTS_MODE", "mock")
    rec = X.explain(run(), rd)
    chk = next(c for c in rec["qa"]["checks"] if c["name"] == "Independent cross-check")
    assert chk["warning"] and "no real cross-check" in chk["detail"] and rec["cross_check"]["scripted"] is True
