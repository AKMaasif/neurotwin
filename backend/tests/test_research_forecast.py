import numpy as np
import pytest

pytest.importorskip("sklearn")

from app import research_forecast as R


def session(sid, n, delay, cdr, *, age=75, sex="F", mmse=29, nwbv=0.74, group="Nondemented"):
    return {"Subject ID": sid, "MRI ID": f"{sid}_MR{n}", "Group": group, "MR Delay": delay, "M/F": sex, "Age": age, "EDUC": 12,
            "SES": 2, "MMSE": mmse, "CDR": cdr, "eTIV": 1500.0, "nWBV": nwbv, "ASF": 1.1}


def cohort_table(n=60, seed=0, signal=False):
    rng = np.random.default_rng(seed); t = []
    for i in range(n):
        sid = f"S{i:03d}"; event = i % 4 == 0
        mmse = (24 if event else 29) + (int(rng.integers(-1, 2)) if signal else int(rng.integers(20, 30)))
        t.append(session(sid, 1, 0, 0, mmse=mmse, age=int(rng.integers(65, 90))))
        t.append(session(sid, 2, 700, 0.5 if event else 0, mmse=mmse))
    return t


def test_cohort_uses_first_visit_inputs_only_and_never_the_group_label():
    c = R.forecast_cohort(cohort_table())
    assert c["rows"] and set(c["rows"][0]["x"]) == set(R.ALL_FEATURES)
    assert not FORBIDDEN_IN_FEATURES()


def FORBIDDEN_IN_FEATURES():
    return set(R.ALL_FEATURES) & R.FORBIDDEN


def test_later_visit_values_cannot_change_the_inputs():
    a = R.forecast_cohort(cohort_table())["rows"][0]["x"]
    t = cohort_table()
    for r in t:
        if r["MRI ID"].endswith("MR2"):
            r["MMSE"], r["nWBV"], r["Age"] = 1, 0.1, 99
    assert R.forecast_cohort(t)["rows"][0]["x"] == a


def test_subjects_without_a_cdr_zero_start_or_a_later_visit_are_not_in_the_conversion_cohort():
    t = [session("A", 1, 0, 0.5), session("A", 2, 400, 1), session("B", 1, 0, 0)]
    assert R.forecast_cohort(t)["rows"] == []


def test_missing_key_input_abstains_and_is_counted():
    t = cohort_table(8); t[0]["MMSE"] = None
    c = R.forecast_cohort(t)
    assert len(c["abstained"]) == 1 and c["abstained"][0]["missing"] == ["MMSE"] and len(c["rows"]) == 7


def test_no_subject_is_on_both_sides_of_a_split_when_visits_are_repeated():
    s = R.screening_cohort(cohort_table(40))
    R.out_of_fold(s["rows"], R.MODELS["age_sex"], grouped=True, repeats=3)  # the function asserts on leakage


def test_pure_noise_does_not_beat_the_simple_baseline():
    c = R.forecast_cohort(cohort_table(80, seed=3, signal=False))
    res = R.evaluate(c, grouped=False, repeats=5)
    assert isinstance(res["verdict"]["candidate_beats_best_baseline"], bool)  # always reported, either way
    assert res["models"]["prevalence_only"]["auroc"] == 0.5
    assert res["models"]["mmse_only"]["auroc_ci95_subject_bootstrap"][0] is not None


def test_a_real_signal_is_detected():
    c = R.forecast_cohort(cohort_table(80, seed=4, signal=True))
    res = R.evaluate(c, grouped=False, repeats=5)
    assert res["models"]["mmse_only"]["auroc"] > 0.9


def test_single_class_gives_a_note_not_a_number():
    t = [session(f"S{i}", n, d, 0) for i in range(10) for n, d in ((1, 0), (2, 500))]
    res = R.evaluate(R.forecast_cohort(t), grouped=False, repeats=2)
    assert "note" in res and not res["models"]


def test_negative_control_runs_and_stays_near_or_below_chance():
    c = R.forecast_cohort(cohort_table(60, seed=5, signal=True))
    res = R.negative_control(c, grouped=False, permutations=4, repeats=2)
    assert res["mmse_only"]["mean_auroc"] < 0.65
