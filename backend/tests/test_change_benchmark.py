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
