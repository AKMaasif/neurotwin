"""Fixed software evaluation cases. Uses no external model and no patient measurements."""
import pytest

from app import assistant, activity_analysis as AA, validator as V
from test_assistant import say, two_tasks


@pytest.mark.parametrize("command", ["Open my report for the last eleven days", "show my report for the last 11 days",
                                     "open my report", "افتح تقريري عن آخر أحد عشر يومًا", "اعرض التقرير عن آخر ١١ يوم"])
def test_report_command_opens_eleven_day_report_without_a_change(client, command):
    h = two_tasks(client)
    r = say(client, h, command)
    assert r["understood"] and r["navigate"] == "report" and r["needs_confirmation"] is False


@pytest.mark.parametrize("command", ["Open my report for the last 30 days", "send my report to everyone", "delete my report"])
def test_unsupported_report_requests_are_not_silently_changed(command):
    r = assistant.parse(command, [], {})
    assert r.get("tool") is None


def test_emergency_has_priority_over_report_navigation():
    assert assistant.parse("I cannot breathe, open my report", [], {})["tool"] == "emergency"


@pytest.mark.parametrize("text,cites", [("The result is 999.", ["F1"]), ("A recorded value.", ["UNKNOWN"]),
                                       ("This proves dementia.", ["F1"])])
def test_unsupported_agent_statements_are_rejected(text, cites):
    assert not V.check([V.Statement(text, cites)], [V.Fact.of("F1", "The recorded value is 5.")]).ok


def test_same_content_has_stable_fingerprint_and_quality_change_invalidates_it():
    from types import SimpleNamespace
    from datetime import date
    e = SimpleNamespace(**dict.fromkeys(("id", "session_id", "measure", "kind", "value_num", "value_text", "unit", "missing_reason", "quality", "quality_reasons", "status", "superseded_by_id", "protocol_code", "protocol_version", "recorded_at")))
    e.id, e.quality, e.value_num = 1, "usable", 5
    c = {"start": date(2026, 1, 1), "end": date(2026, 1, 2), "sessions": [], "evidence": [e], "replies": []}
    first = AA.fingerprint(c)
    assert AA.fingerprint(c) == first
    e.quality = "unusable"
    assert AA.fingerprint(c) != first


def test_changed_review_content_has_a_different_digest():
    run = {"review": {"decisions": [{"decision": "keep"}]}}
    first = AA.review_digest(run)
    run["review"]["decisions"][0]["decision"] = "discard"
    assert AA.review_digest(run) != first
