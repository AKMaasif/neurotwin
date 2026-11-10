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


def test_abstains_with_too_few_usable_records():
    r = C.compare([rec(i, 500) for i in range(4)])
    assert r.status == "insufficient" and r.difference is None and r.interval is None


def test_doubtful_and_unusable_and_withdrawn_are_not_counted_by_default():
    rows = [rec(0, 500), rec(1, 510), rec(2, 505), rec(3, 900, "doubtful"), rec(4, 50, "unusable"),
            rec(5, 700, status="withdrawn")]
    r = C.compare(rows)
    assert r.status == "insufficient" and r.eligible_n == 3
    assert r.excluded == {"doubtful": 1, "unusable": 1, "withdrawn": 1, "missing": 0}


def test_doubtful_counted_only_when_asked():
    rows = [rec(0, 500), rec(1, 510), rec(2, 505), rec(3, 508, "doubtful"), rec(4, 502)]
    assert C.compare(rows).status == "insufficient"
    assert C.compare(rows, include_doubtful=True).status in ("within", "outside")


def test_no_variation_abstains_instead_of_claiming_certainty():
    r = C.compare([rec(i, 500) for i in range(5)])
    assert r.status == "no_variation" and r.interval is None


def test_noise_reads_as_within_usual_variation():
    r = C.compare([rec(0, 600), rec(1, 640), rec(2, 590), rec(3, 625), rec(4, 605)])
    assert r.status == "within" and r.interval[0] < 0 < r.interval[1]


def test_clear_shift_reads_as_outside_with_direction():
    r = C.compare([rec(0, 500), rec(1, 505), rec(2, 498), rec(3, 700), rec(4, 705)])
    assert r.status == "outside" and r.direction == "higher" and r.interval[0] > 0
    assert r.baseline.ids == [0, 1, 2] and r.recent.ids == [3, 4]


def test_windows_never_overlap():
    r = C.compare([rec(i, 500 + i * 3) for i in range(5)])
    assert set(r.baseline.ids).isdisjoint(r.recent.ids)


def test_versions_are_never_pooled():
    rows = [rec(i, 500 + i) for i in range(3)] + [rec(3 + i, 700 + i, version="0.2") for i in range(3)]
    results = C.compare_all(rows)
    assert {(x.protocol_version, x.status) for x in results} == {("0.1", "insufficient"), ("0.2", "insufficient")}


def test_t_table_is_never_narrower_than_the_true_value():
    assert C.t95(3) == pytest.approx(3.182) and C.t95(22) == pytest.approx(2.060) and C.t95(500) == 1.96


# ---- over HTTP ---------------------------------------------------------------------------------------------

def test_clinician_gets_estimates_for_demo_person(client, login):
    dr = login("demo-dr-layla")
    rows = client.get("/api/participants/demo-fatima/change", headers=dr).json()
    rt = next(r for r in rows if r["measure"] == "rt_median_ms")
    assert rt["status"] == "insufficient" and rt["eligible_n"] == 4 and rt["excluded"]["doubtful"] == 2
    rt2 = next(r for r in client.get("/api/participants/demo-fatima/change?include_doubtful=true", headers=dr).json()
               if r["measure"] == "rt_median_ms")
    assert rt2["status"] in ("within", "outside") and rt2["method"] == "change-engine/0.1"
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
