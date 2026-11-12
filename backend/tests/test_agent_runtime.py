import json

import pytest

from app import agent_ledger as L
from app import agent_runtime as R
from app import llm
from test_agent_ledger import RUN


class Fake:
    provider, model = "gemini", "g-test"

    def __init__(self, text="{}", fail=False):
        self.text, self.fail, self.seen = text, fail, []

    def complete(self, system, user, json_mode=False):
        self.seen.append(user)
        if self.fail:
            raise llm.ModelError("gemini answered HTTP 500.")
        return llm.Reply(self.text, self.provider, self.model)


@pytest.fixture(autouse=True)
def reset_cap():
    R._cap.update({"day": None, "n": 0})


def test_mode_defaults_and_mock_is_never_silent():
    assert R.mode({}) == "off"
    assert R.mode({"GEMINI_API_KEY": "k"}) == "live"
    assert R.mode({"NEUROTWIN_AGENTS_MODE": "mock"}) == "mock"
    assert R.client_for("gemini", {}) is None
    assert R.client_for("meta", {"NEUROTWIN_AGENTS_MODE": "mock"}).provider == "mock-meta"


def test_model_choice_uses_agent_specific_id_first():
    c = R.client_for("gemini", {"GEMINI_API_KEY": "k", "GEMINI_MODEL": "a", "AGENTS_GEMINI_MODEL": "b"})
    assert c.model == "b"
    assert R.client_for("gemini", {"GEMINI_API_KEY": "k"}) is None  # no model id: not configured


def test_status_lists_names_and_booleans_only():
    s = R.status({"GEMINI_API_KEY": "secret-key", "GEMINI_MODEL": "g"})
    assert "secret-key" not in json.dumps(s) and s["providers"]["gemini"]["available"] and not s["providers"]["meta"]["available"]


def test_serialise_sends_only_ledger_facts():
    led = L.build(RUN)
    text, ids = R.serialise(led, ["F-total", "F-R4"])
    assert ids == ["F-total", "F-R4"] and text.startswith("Facts:\nF-total:") and "r1" not in text and "OAS2" not in text


def test_invoke_logs_egress_before_and_trace_after(tmp_path):
    f = Fake('{"statements": []}')
    out = R.invoke(tmp_path, "A3", "gemini", "sys", "Facts:\nF-total: x", ["F-total"], client=f)
    assert out["status"] == "completed" and out["text"] == '{"statements": []}'
    eg, tr = R.read(tmp_path, R.EGRESS), R.read(tmp_path, R.TRACE)
    assert eg[0]["fact_ids"] == ["F-total"] and eg[0]["images"] == 0 and eg[0]["sent_outside"] is True
    assert tr[0]["status"] == "completed" and tr[0]["agent"] == "A3" and len(tr[0]["prompt_sha256"]) == 16
    assert "key" not in json.dumps(eg + tr).lower()


def test_failed_call_is_recorded_and_returns_no_text(tmp_path):
    out = R.invoke(tmp_path, "A3", "gemini", "s", "u", [], client=Fake(fail=True))
    assert out["status"] == "failed" and out["text"] is None
    assert R.read(tmp_path, R.TRACE)[0]["status"] == "failed" and len(R.read(tmp_path, R.EGRESS)) == 1


def test_no_provider_gives_unavailable_and_sends_nothing(tmp_path):
    out = R.invoke(tmp_path, "A4", "meta", "s", "u", [], env={})
    assert out["status"] == "unavailable" and not (tmp_path / R.EGRESS).exists()
    assert R.read(tmp_path, R.TRACE)[0]["status"] == "unavailable"


def test_daily_cap_blocks_without_calling(tmp_path):
    env = {"NEUROTWIN_AGENTS_DAILY_CALLS": "1"}
    f = Fake("{}")
    assert R.invoke(tmp_path, "A3", "gemini", "s", "u", [], client=f, env=env)["status"] == "completed"
    assert R.invoke(tmp_path, "A3", "gemini", "s", "u", [], client=f, env=env)["status"] == "unavailable" and len(f.seen) == 1


def test_mock_is_labelled_scripted_and_not_counted_as_outside(tmp_path):
    led = L.build(RUN)
    text, ids = R.serialise(led)
    out = R.invoke(tmp_path, "A3", "gemini", "s", text, ids, env={"NEUROTWIN_AGENTS_MODE": "mock"})
    assert out["provider"] == "mock-gemini" and out["model"] == "scripted-demo"
    assert R.read(tmp_path, R.EGRESS)[0]["sent_outside"] is False and R.read(tmp_path, R.TRACE)[0]["scripted"] is True
    assert json.loads(out["text"])["statements"][0]["cites"]
