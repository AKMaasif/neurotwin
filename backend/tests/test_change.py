from datetime import datetime, timedelta, timezone

import pytest

from app import change as C
from app.models import Evidence
from conftest import consent, run_reaction

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def rec(i, value, quality="usable", status="current", version="0.1", measure="rt_median_ms"):
    return Evidence(id=i, participant_id="p", kind="observed", measure=measure, value_num=value, unit="ms",
                    protocol_code="reaction_time", protocol_version=version, producer_type="device",
                    producer_id="d", producer_version="1", quality=quality, quality_reasons=[], status=status,
                    recorded_at=T0 + timedelta(days=7 * i))


def P0(rows, **kw):
    """The comparison itself, without the practice rule (tested separately below)."""
    return C.compare(rows, practice=0, **kw)


def test_abstains_with_too_few_usable_records():
    r = C.compare([rec(i, 500) for i in range(4)])
    assert r.status == "insufficient" and r.difference is None and r.interval is None


def test_doubtful_and_unusable_and_withdrawn_are_not_counted_by_default():
    rows = [rec(0, 500), rec(1, 510), rec(2, 505), rec(3, 900, "doubtful"), rec(4, 50, "unusable"),
            rec(5, 700, status="withdrawn")]
    r = P0(rows)
    assert r.status == "insufficient" and r.eligible_n == 3
    assert r.excluded == {"practice": 0, "doubtful": 1, "unusable": 1, "withdrawn": 1, "missing": 0}


def test_doubtful_counted_only_when_asked():
    rows = [rec(0, 500), rec(1, 510), rec(2, 505), rec(3, 508, "doubtful"), rec(4, 502)]
    assert P0(rows).status == "insufficient"
    assert P0(rows, include_doubtful=True).status in ("within", "outside")


def test_no_variation_abstains_instead_of_claiming_certainty():
    r = P0([rec(i, 500) for i in range(5)])
    assert r.status == "no_variation" and r.interval is None


def test_noise_reads_as_within_usual_variation():
    r = P0([rec(0, 600), rec(1, 640), rec(2, 590), rec(3, 625), rec(4, 605)])
    assert r.status == "within" and r.interval[0] < 0 < r.interval[1]


def test_clear_shift_reads_as_outside_with_direction():
    r = P0([rec(0, 500), rec(1, 505), rec(2, 498), rec(3, 700), rec(4, 705)])
    assert r.status == "outside" and r.direction == "higher" and r.interval[0] > 0
    assert r.baseline.ids == [0, 1, 2] and r.recent.ids == [3, 4]


def test_windows_never_overlap():
    r = P0([rec(i, 500 + i * 3) for i in range(5)])
    assert set(r.baseline.ids).isdisjoint(r.recent.ids)


def test_versions_are_never_pooled():
    rows = [rec(i, 500 + i) for i in range(3)] + [rec(3 + i, 700 + i, version="0.2") for i in range(3)]
    results = C.compare_all(rows)
    assert {(x.protocol_version, x.status) for x in results} == {("0.1", "insufficient"), ("0.2", "insufficient")}


def test_first_two_sessions_of_a_task_are_practice_and_never_compared():
    # A big learning gain in the first two sessions, then stable: without the practice rule the baseline carries it.
    rows = [rec(0, 700), rec(1, 610)] + [rec(2 + i, v) for i, v in enumerate([520, 530, 525, 522, 528])]
    assert P0(rows).difference < -80
    r = C.compare(rows)
    assert r.practice_ids == [0, 1] and r.excluded["practice"] == 2 and abs(r.difference) < 5
    assert r.baseline.ids == [2, 3, 4] and r.as_dict()["needed"] == {"baseline": 3, "recent": 2, "practice": 2}


def test_practice_counts_sessions_done_whatever_their_quality():
    rows = [rec(0, 900, "unusable"), rec(1, 650, "doubtful")] + [rec(2 + i, 500 + i) for i in range(5)]
    r = C.compare(rows)
    assert r.practice_ids == [0, 1] and r.excluded == {"practice": 2, "doubtful": 0, "unusable": 0, "withdrawn": 0, "missing": 0}
    assert r.eligible_n == 5


def test_self_reports_have_no_practice_period():
    rows = [Evidence(id=i, participant_id="p", kind="self_reported", measure="sleep_hours", value_num=7 + (i % 2), unit="h",
                     protocol_code="daily_checkin", protocol_version="0.1", producer_type="person", producer_id="p",
                     producer_version="1", quality="usable", quality_reasons=[], status="current",
                     recorded_at=T0 + timedelta(days=i)) for i in range(5)]
    r = C.compare(rows)
    assert r.practice_ids == [] and r.status != "insufficient" and r.as_dict()["needed"]["practice"] == 0


def test_z_is_the_difference_in_the_persons_own_spread():
    rows = [rec(0, 500), rec(1, 505), rec(2, 498), rec(3, 700), rec(4, 705)]
    r = P0(rows)
    pooled = ((sum((v - 501) ** 2 for v in (500, 505, 498)) + sum((v - 702.5) ** 2 for v in (700, 705))) / 3) ** 0.5
    assert r.z == pytest.approx(r.difference / pooled)


def test_rci_uses_the_named_reliability_and_says_it_is_provisional():
    rows = [rec(0, 500), rec(1, 520), rec(2, 510), rec(3, 590), rec(4, 600)]
    r = P0(rows)
    ref = C.RELIABILITY[("reaction_time", "rt_median_ms")]
    sem = ref.sd_ref * (1 - ref.r) ** 0.5
    s_diff = sem * (1 / 3 + 1 / 2) ** 0.5
    assert r.rci["value"] == pytest.approx(r.difference / s_diff, abs=0.01)
    assert r.rci["reliable"] is True and r.rci["provisional"] is True and "Provisional" in r.rci["source"]


def test_no_rci_without_a_reliability_figure():
    r = P0([rec(i, 3 + i % 2, measure="rounds_correct") for i in range(5)])
    assert r.rci is None


def test_rci_never_changes_the_status():
    # A small shift the interval calls "within" can still exceed the provisional RCI: both are shown, the status is the interval's.
    rows = [rec(0, 480), rec(1, 560), rec(2, 470), rec(3, 600), rec(4, 530)]
    r = P0(rows)
    assert r.status == "within" and r.rci["reliable"] is True


def test_t_table_is_never_narrower_than_the_true_value():
    assert C.t95(3) == pytest.approx(3.182) and C.t95(22) == pytest.approx(2.060) and C.t95(500) == 1.96


# ---- over HTTP ---------------------------------------------------------------------------------------------

def test_clinician_gets_estimates_for_demo_person(client, login):
    dr = login("demo-dr-layla")
    rows = client.get("/api/participants/demo-fatima/change", headers=dr).json()
    rt = next(r for r in rows if r["measure"] == "rt_median_ms")
    # Six reaction sessions: the first two are practice, two of the rest are doubtful.
    assert rt["status"] == "insufficient" and rt["eligible_n"] == 2 and rt["excluded"]["doubtful"] == 2
    assert rt["excluded"]["practice"] == 2 and len(rt["practice_ids"]) == 2 and rt["method"] == "change-engine/0.2"
    sleep = next(r for r in rows if r["measure"] == "sleep_hours")
    assert sleep["status"] in ("within", "outside") and sleep["excluded"]["practice"] == 0 and sleep["z"] is not None
    assert all(r["measure"] not in ("valid_trials", "anticipations", "today_factors") for r in rows)
    trail = client.get("/api/participants/demo-fatima/audit", headers=dr).json()
    assert any(a["action"] == "change.computed" for a in trail)


def test_participant_and_family_cannot_get_estimates(client, login):
    assert client.get("/api/participants/demo-fatima/change", headers=login("demo-fatima")).status_code == 404
    assert client.get("/api/participants/demo-fatima/change", headers=login("demo-mariam")).status_code == 404


def test_clinician_without_grant_cannot_get_estimates(client, login, yousef):
    consent(client, yousef)
    for _ in range(5):
        run_reaction(client, yousef)
    assert client.get("/api/participants/demo-yousef/change", headers=login("demo-dr-layla")).status_code == 404


def test_who5_gets_no_change_label():
    """The published WHO-5 is shown as recorded; the change engine never labels it."""
    from datetime import datetime, timedelta, timezone
    from app.change import compare_all
    from app.models import Evidence
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows = [Evidence(id=i, participant_id="p", session_id=i, kind="self_reported", measure="who5_raw", value_num=10 + i % 3, unit="0-25",
                     protocol_code="who5", protocol_version="1998-en", producer_type="person", producer_id="p", producer_version="x",
                     derived_from=[], quality="usable", quality_reasons=[], status="current", recorded_at=base + timedelta(days=14 * i))
            for i in range(8)]
    assert compare_all(rows) == []
