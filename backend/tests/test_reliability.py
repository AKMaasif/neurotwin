"""Test–retest reliability (ICC, SEM, MDC, Bland–Altman) and subgroup comparison: checked against published figures."""
import math
import random
from datetime import datetime, timedelta, timezone

import pytest

from app import reliability as R, subgroups as G
from conftest import make_user

# Shrout & Fleiss (1979), Table 2: 6 targets rated by 4 judges
SF = [[9, 2, 5, 8], [6, 1, 3, 2], [8, 4, 6, 8], [7, 1, 2, 6], [10, 5, 6, 9], [6, 2, 4, 7]]


def test_icc_matches_shrout_and_fleiss():
    r = R.icc(SF)
    assert round(r.icc_a, 2) == 0.29 and round(r.icc_c, 2) == 0.71
    assert [round(x, 2) for x in r.icc_a_ci] == [0.02, 0.76]       # McGraw & Wong, as in standard software
    assert [round(x, 2) for x in r.icc_c_ci] == [0.34, 0.95]


def test_f_quantile_matches_tables():
    assert R.f_ppf(0.975, 5, 15) == pytest.approx(3.576, abs=1e-3)
    assert R.f_ppf(0.95, 1, 10) == pytest.approx(4.965, abs=1e-3)
    assert R.f_ppf(0.99, 10, 20) == pytest.approx(3.368, abs=1e-3)


def test_sem_mdc_and_bland_altman_follow_their_formulas():
    rng = random.Random(1)
    rows = [[m + rng.gauss(0, 10), m + 5 + rng.gauss(0, 10)] for m in (rng.gauss(400, 40) for _ in range(60))]
    r = R.icc(rows)
    assert r.sem == pytest.approx(r.sd * math.sqrt(1 - r.icc_a))
    assert r.mdc95 == pytest.approx(1.96 * math.sqrt(2) * r.sem, rel=1e-3)
    diffs = [b - a for a, b in rows]
    assert r.bias == pytest.approx(sum(diffs) / len(diffs))
    assert r.loa[0] < r.bias < r.loa[1]
    assert r.icc_c > r.icc_a            # a shared +5 shift lowers absolute agreement only


def test_perfect_agreement_and_bad_input():
    r = R.icc([[1, 1], [2, 2], [3, 3], [5, 5]])
    assert r.icc_a == pytest.approx(1, abs=1e-6) and r.sem == pytest.approx(0, abs=1e-3)
    with pytest.raises(ValueError):
        R.icc([[1, 2], [3, 4]])
    with pytest.raises(ValueError):
        R.icc([[1, 2], [3], [4, 5]])


def test_sample_size_matches_walter_eliasziw_donner():
    assert R.sample_size(0.8, 0.6) == 39
    assert R.sample_size(0.8, 0.7) == 117


def test_simulation_recovers_the_true_reliability():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "eval"))
    import run_reliability_study as S
    S.REPS = 150
    r = S.scenario("40 people, sessions 3 and 4 (practice set aside)", 40, (2, 3), S.PRACTICE_MS)
    assert abs(r["icc_a"] - S.TRUE_ICC) < 0.04 and 0.88 <= r["cover_a"] <= 1.0 and abs(r["sem"] - S.SD_W) < 2
    with_practice = S.scenario("40 people, sessions 1 and 2 (practice included)", 40, (0, 1), S.PRACTICE_MS)
    assert with_practice["bias"] < r["bias"] - 10 and with_practice["sem"] > r["sem"]


def test_retest_pairs_skip_practice_doubtful_and_synthetic(app):
    from app.models import Evidence
    make_user(app, "p-rt", "p-rt")
    t0 = datetime(2026, 10, 1, tzinfo=timezone.utc)

    def ev(day, v, quality="usable", producer="reaction-scorer"):
        return Evidence(participant_id="p-rt", kind="observed", measure="rt_median_ms", value_num=v, unit="ms", protocol_code="reaction_time",
                        protocol_version="0.1", producer_type="rule", producer_id=producer, producer_version="1", quality=quality,
                        recorded_at=t0 + timedelta(days=day))
    with app.state.db.SessionLocal() as db:
        db.add_all([ev(0, 600), ev(1, 590),                 # practice
                    ev(2, 500, "doubtful"), ev(3, 480), ev(3.5, 470), ev(5, 475),   # 3.5 is under a day after 3
                    ev(6, 300, producer="synthetic-history/1")])
        db.commit()
        pairs = [p for p in R.retest_pairs(db) if p["participant_id"] == "p-rt"]     # the demo seed is there too
    assert pairs == [{"participant_id": "p-rt", "protocol_version": "0.1", "test": 480.0, "retest": 475.0, "gap_days": 2.0}]


def test_subgroups_compare_only_groups_big_enough():
    rows = [("a", True)] * 30 + [("a", False)] * 10 + [("b", True)] * 10 + [("b", False)] * 30 + [("c", True)] * 5
    r = G.by_group(rows, lambda x: x[0], lambda x: x[1], "hit", "group")
    assert [g.name for g in r.groups] == ["a", "b"] and [g.name for g in r.small] == ["c"]
    assert r.gap[0] == "a" and r.gap[1] == "b" and r.gap[2] == pytest.approx(0.5) and r.gap_clear
    same = G.by_group([("a", True), ("a", False)] * 20 + [("b", True), ("b", False)] * 20, lambda x: x[0], lambda x: x[1], "hit", "group")
    assert not same.gap_clear


def test_newcombe_interval_matches_published_example():
    # Newcombe (1998), example (a): 56/70 against 48/80, difference 0.2, method 10 interval 0.0524 to 0.3339
    d, lo, hi = G.newcombe(56, 70, 48, 80)
    assert d == pytest.approx(0.2) and lo == pytest.approx(0.0524, abs=5e-4) and hi == pytest.approx(0.3339, abs=5e-4)


def test_quality_by_runs_on_a_database(app):
    with app.state.db.SessionLocal() as db:
        r = G.quality_by(db, "device")
    assert r.outcome == "doubtful or unusable record" and r.by == "device"
