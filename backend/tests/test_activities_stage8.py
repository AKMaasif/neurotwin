"""Stage 8: picture-sequence memory (prototype) and WHO-5 (published wording and scoring, unchanged). No score is interpreted."""
import pytest

from app import protocols as P
from app.quality import ObservationIn as O, SessionContext, assess_session

DONE = SessionContext(status="completed")


def obs(**kw):
    return [O(measure=k, kind=P.get(*key).measure(k).kind, value_num=v, unit="x") for key, d in kw.items() for k, v in d]


def who5(answers, raw):
    out = [O(f"who5_{i + 1}", "self_reported", a, unit="0-5") if a is not None
           else O(f"who5_{i + 1}", "self_reported", missing_reason="skipped_by_participant") for i, a in enumerate(answers)]
    out.append(O("who5_raw", "self_reported", raw, unit="0-25") if raw is not None else O("who5_raw", "self_reported", missing_reason="incomplete_items"))
    return out


def test_who5_is_registered_as_published_not_a_prototype():
    p = P.get("who5", "1998-en")
    assert p.kind == "self_report" and p.review_status == P.PUBLISHED != P.PROTOTYPE
    assert [m.code for m in p.measures] == ["who5_1", "who5_2", "who5_3", "who5_4", "who5_5", "who5_raw"]
    assert all((m.valid_min, m.valid_max) == (0, 5) for m in p.measures[:5]) and (p.measure("who5_raw").valid_max == 25)


def test_who5_consistent_total_is_usable():
    vs = assess_session(P.get("who5", "1998-en"), DONE, who5([5, 4, 3, 2, 1], 15))
    assert {v.level for v in vs} == {"usable"}


@pytest.mark.parametrize("answers,raw", [([5, 4, 3, 2, 1], 16), ([5, 4, 3, 2, None], 14), ([5, 4, 3, 2, None], 0)])
def test_who5_total_must_equal_the_sum_of_five_answers(answers, raw):
    vs = assess_session(P.get("who5", "1998-en"), DONE, who5(answers, raw))
    assert vs[-1].level == "unusable" and "inconsistent_total" in vs[-1].reasons


def test_who5_skipped_item_leaves_total_missing_not_zero():
    vs = assess_session(P.get("who5", "1998-en"), DONE, who5([5, 4, 3, 2, None], None))
    assert [v.level for v in vs[-2:]] == ["unusable", "unusable"] and "missing_value" in vs[-1].reasons


def test_who5_out_of_range_answer_is_unusable():
    vs = assess_session(P.get("who5", "1998-en"), DONE, who5([6, 4, 3, 2, 1], 16))
    assert vs[0].level == "unusable" and "out_of_range" in vs[0].reasons


def ps(correct, shown, longest):
    return [O("rounds_correct", "observed", correct, unit="count"), O("rounds_shown", "observed", shown, unit="count"),
            O("longest_correct", "observed", longest, unit="count")]


def test_picture_sequence_normal_run_is_usable():
    assert {v.level for v in assess_session(P.get("picture_sequence", "0.1"), DONE, ps(3, 4, 4))} == {"usable"}


def test_picture_sequence_few_rounds_and_impossible_counts_are_flagged():
    vs = assess_session(P.get("picture_sequence", "0.1"), DONE, ps(1, 2, 3))
    assert vs[0].level == "doubtful" and "too_few_rounds" in vs[0].reasons
    vs = assess_session(P.get("picture_sequence", "0.1"), DONE, ps(4, 3, 3))
    assert vs[0].level == "unusable" and "inconsistent_total" in vs[0].reasons


def test_picture_sequence_is_labelled_prototype():
    assert P.get("picture_sequence", "0.1").review_status == P.PROTOTYPE


def test_both_run_through_the_session_api(client):
    from test_careplan import sign_in
    h = sign_in(client, "demo-fatima")
    s = client.post("/api/sessions", headers=h, json={"protocol_code": "who5", "protocol_version": "1998-en", "language": "en", "device": "web"})
    assert s.status_code in (200, 201), s.text
    body = {"status": "completed", "interruptions": 0, "client_version": "t", "observations": [
        {"measure": f"who5_{i}", "kind": "self_reported", "unit": "0-5", "value_num": 3} for i in range(1, 6)
    ] + [{"measure": "who5_raw", "kind": "self_reported", "unit": "0-25", "value_num": 15}]}
    r = client.post(f"/api/sessions/{s.json()['id']}/complete", headers=h, json=body)
    assert r.status_code == 200, r.text
    s2 = client.post("/api/sessions", headers=h, json={"protocol_code": "picture_sequence", "protocol_version": "0.1", "language": "en", "device": "web"})
    assert s2.status_code in (200, 201)


def test_assistant_opens_the_new_activities(client):
    from test_careplan import sign_in
    h = sign_in(client, "demo-fatima")
    say = lambda t: client.post("/api/assistant/message", json={"text": t}, headers=h).json()
    assert say("start the picture game")["navigate"] == "memory"
    assert say("well-being questions")["navigate"] == "wellbeing"
    assert say("start the daily check-in")["navigate"] == "checkin"


def test_who5_protocol_carries_no_threshold_or_interpretation():
    d = P.as_dict(P.get("who5", "1998-en"))
    assert not any(k in str(d).lower() for k in ("cutoff", "cut_off", "threshold", "depress", "low", "significant"))
