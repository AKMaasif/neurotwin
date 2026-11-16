"""The change-engine simulation stays within its designed behaviour (docs/CHANGE_ENGINE_BENCHMARK.md)."""
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("change_bench", Path(__file__).resolve().parent.parent / "eval" / "run_change_benchmark.py")
B = importlib.util.module_from_spec(spec)
spec.loader.exec_module(B)


def test_false_alarms_near_design_and_abstains_when_thin(monkeypatch):
    monkeypatch.setattr(B, "N_PEOPLE", 400)
    rows = {r["label"]: r for r in B.run()}
    stable = rows["Stable, no practice effect"]["tally"]
    assert (stable["outside_higher"] + stable["outside_lower"]) / 400 <= 0.09
    assert rows["Only 4 usable sessions"]["tally"]["abstain"] == 400
    assert rows["Slowing of 4 SD"]["hit"] > rows["Slowing of 1 SD"]["hit"]


def test_practice_rule_reduces_learning_bias(monkeypatch):
    """Setting aside the first sessions cuts false "faster" flags on stable learners and finds more slowings hidden by learning."""
    monkeypatch.setattr(B, "N_PEOPLE", 400)
    new = {r["label"]: r for r in B.run()}
    old = {r["label"]: r for r in B.run(practice=0)}
    learner = "Stable, with practice gain (40 ms)"
    hidden = "Slowing of 3 SD, with practice gain (40 ms)"
    assert new[learner]["tally"]["outside_lower"] < old[learner]["tally"]["outside_lower"]
    assert new[hidden]["hit"] > old[hidden]["hit"]


def test_rci_false_alarms_stay_low_on_stable_people(monkeypatch):
    monkeypatch.setattr(B, "N_PEOPLE", 400)
    stable = {r["label"]: r for r in B.run()}["Stable, no practice effect"]["tally"]
    assert (stable["rci_higher"] + stable["rci_lower"]) / 400 <= 0.09
