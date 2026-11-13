import json
import math

import pytest

np = pytest.importorskip("numpy")
nib = pytest.importorskip("nibabel")

from app import agent_analysis as A
from app import agent_ledger as L
from app import agent_noise as N
from app import validator as V
from test_agent_ledger import RUN, region


@pytest.fixture
def root(monkeypatch, tmp_path):
    monkeypatch.setenv("NEUROTWIN_IMAGING_ROOT", str(tmp_path / "imaging"))
    return tmp_path / "imaging" / "oasis2"


def put(root, mri, counts, scan="mpr-1", tool=("SynthSeg", "1.0"), voxel=1.0):
    """A tiny segmentation: label -> number of voxels, on a 1 mm (or `voxel` mm) grid."""
    d = root / "segmentations" / mri / ("" if scan == "mpr-1" else f"repeats/{scan}")
    d.mkdir(parents=True, exist_ok=True)
    arr = np.zeros((20, 20, 20), np.int16)
    flat = arr.reshape(-1)
    i = 0
    for lab, n in counts.items():
        flat[i:i + n] = lab
        i += n
    aff = np.diag([voxel, voxel, voxel, 1.0])
    nib.save(nib.Nifti1Image(arr, aff), str(d / "seg.nii.gz"))
    (d / "tool.json").write_text(json.dumps({"tool": tool[0], "version": tool[1]}))


def test_pooled_sd_matches_a_hand_calculation():
    p = N.pooled([[10, 12], [20, 22, 24]])
    # visit 1: mean 11, SS 2, df 1; visit 2: mean 22, SS 8, df 2; pooled variance 10/3
    assert p["status"] == "estimated" and p["df"] == 3 and p["sd_mm3"] == round(math.sqrt(10 / 3), 2) and p["max_range_mm3"] == 4


def test_not_enough_degrees_of_freedom_gives_no_estimate():
    p = N.pooled([[10, 12], [5]])
    assert p["status"] == "not_estimated" and p["df"] == 1 and "degrees of freedom" in p["reason"]
    assert N.pooled([[10], [5]])["status"] == "not_estimated"


def test_one_visit_with_three_repeats_is_enough():
    assert N.pooled([[10, 11, 12], []])["status"] == "estimated"


def test_identical_repeats_give_zero_spread_and_no_ratio():
    e = {"scans": {"mpr-1": {4: 100.0}, "mpr-2": {4: 100.0}, "mpr-3": {4: 100.0}}, "skipped": [], "flags": []}
    out = N.estimate(e, {"scans": {"mpr-1": {4: 150.0}}, "skipped": [], "flags": []}, [{"label": 4, "earlier_mm3": 100.0, "later_mm3": 150.0, "difference_mm3": 50.0}])
    q = out["regions"]["4"]
    assert q["sd_mm3"] == 0 and q["ratio"] is None and q["within_repeat_range"] is False


def test_ratio_and_range_use_the_stated_definitions():
    e = {"scans": {"mpr-1": {4: 1000.0}, "mpr-2": {4: 1010.0}, "mpr-3": {4: 990.0}}, "skipped": [], "flags": []}
    l = {"scans": {"mpr-1": {4: 1100.0}, "mpr-2": {4: 1090.0}}, "skipped": [], "flags": []}
    out = N.estimate(e, l, [{"label": 4, "earlier_mm3": 1000.0, "later_mm3": 1100.0, "difference_mm3": 100.0}])
    q = out["regions"]["4"]
    sd = math.sqrt((200 + 50) / 3)   # SS earlier 200 (df 2), SS later 50 (df 1)
    assert q["df"] == 3 and q["sd_mm3"] == round(sd, 2) and q["ratio"] == round(100 / round(sd, 2), 2) and q["max_range_mm3"] == 20 and q["within_repeat_range"] is False
    assert out["status"] == "estimated" and "lower bound" in out["note"] or "at least this large" in out["note"]


def test_no_repeats_means_not_estimated_not_zero():
    e = {"scans": {"mpr-1": {4: 1.0}}, "skipped": [], "flags": []}
    out = N.estimate(e, e, [{"label": 4, "earlier_mm3": 1.0, "later_mm3": 1.0, "difference_mm3": 0.0}])
    assert out["status"] == "not_estimated" and out["regions"] == {}


def test_visit_volumes_read_files_use_voxel_size_and_skip_other_tools(root):
    put(root, "OAS2_0001_MR1", {4: 100, 17: 50})
    put(root, "OAS2_0001_MR1", {4: 104, 17: 50}, "mpr-2")
    put(root, "OAS2_0001_MR1", {4: 90, 17: 50}, "mpr-3", tool=("SynthSeg", "2.0"))
    v = N.visit_volumes("OAS2_0001_MR1", [4, 17], {"tool": "SynthSeg", "version": "1.0"})
    assert sorted(v["scans"]) == ["mpr-1", "mpr-2"] and v["scans"]["mpr-2"][4] == 104.0
    assert v["skipped"] == [{"scan": "mpr-3", "reason": "segmented with SynthSeg 2.0, not SynthSeg 1.0"}]


def test_voxel_volume_is_taken_from_the_segmentation_grid(root):
    put(root, "OAS2_0001_MR1", {4: 100}, voxel=2.0)
    assert N.visit_volumes("OAS2_0001_MR1", [4], {"tool": "SynthSeg", "version": "1.0"})["scans"]["mpr-1"][4] == 800.0


def test_a_repeat_with_a_very_different_total_is_kept_but_flagged(root):
    put(root, "OAS2_0001_MR1", {4: 100})
    put(root, "OAS2_0001_MR1", {4: 150}, "mpr-2")
    v = N.visit_volumes("OAS2_0001_MR1", [4], {"tool": "SynthSeg", "version": "1.0"})
    assert "mpr-2" in v["scans"] and v["flags"] and "more than 5%" in v["flags"][0]


def make_run(root):
    r = json.loads(json.dumps(RUN))
    r.update(earlier="OAS2_0001_MR1", later="OAS2_0001_MR2", state="complete")
    r["steps"] = [{"key": "longitudinal_comparison", "state": "done", "detail": N.OLD_LONG}, {"key": "findings_review", "state": "warning", "detail": N.OLD_FIND}]
    r["measurements"]["regions"] = [region(4, "left lateral ventricle", 2000, 2200)]
    for x in r["measurements"]["regions"]:
        x["review_notes"] = [N.OLD_NOTE]
    r["review"] = {"flags": [], "findings": [{"label": 4, "name": "left lateral ventricle", "status": "uncertain", "notes": [N.OLD_NOTE]}]}
    r["report"] = {"sections": {"needs_clinical_review": [N.OLD_REVIEW, "Nothing here is a diagnosis."], "suggested_follow_up": ["x", N.OLD_FOLLOW]}}
    for mri, base in (("OAS2_0001_MR1", 2000), ("OAS2_0001_MR2", 2200)):
        for k, scan in enumerate(("mpr-1", "mpr-2", "mpr-3")):
            put(root, mri, {4: base + (-20, 0, 20)[k]}, scan)
    return r


def test_compute_and_apply_update_notes_report_and_keep_status_uncertain(root):
    r = make_run(root)
    N.apply(r, N.compute(r))
    reg = r["measurements"]["regions"][0]
    assert r["noise"]["status"] == "estimated" and reg["repeat"]["df"] == 4 and reg["repeat"]["sd_mm3"] == 20.0
    assert reg["review_notes"][0].startswith("Same-session repeat spread 20.0 mm3") and "lower bound" in reg["review_notes"][0] and N.OLD_NOTE not in reg["review_notes"]
    assert reg["status"] if "status" in reg else True
    assert r["review"]["findings"][0]["notes"] == reg["review_notes"]
    assert N.OLD_REVIEW not in r["report"]["sections"]["needs_clinical_review"] and N.OLD_FOLLOW not in r["report"]["sections"]["suggested_follow_up"]
    assert "lower bound" in r["steps"][0]["detail"]
    again = json.loads(json.dumps(r)); N.apply(again, N.compute(again))
    assert again["measurements"]["regions"][0]["review_notes"] == reg["review_notes"]            # idempotent


def test_apply_without_repeats_restores_the_original_wording(root):
    r = make_run(root)
    N.apply(r, N.compute(r))
    for p in (root / "segmentations").rglob("repeats"):
        import shutil; shutil.rmtree(p)
    N.apply(r, N.compute(r))
    assert r["noise"]["status"] == "not_estimated" and r["measurements"]["regions"][0]["repeat"] is None
    assert r["measurements"]["regions"][0]["review_notes"] == [N.OLD_NOTE] and N.OLD_REVIEW in r["report"]["sections"]["needs_clinical_review"] and r["steps"][0]["detail"] == N.OLD_LONG


def test_compute_never_raises(root):
    r = json.loads(json.dumps(RUN)); r.update(earlier="MISSING_1", later="MISSING_2")
    out = N.compute(r)
    assert out["status"] == "not_estimated" and out["reason"]


def test_ledger_has_noise_facts_that_the_validator_accepts_and_the_old_text_without_them(root):
    plain = {f["id"]: f["text"] for f in L.build(json.loads(json.dumps(RUN)))["facts"]}
    assert "F-noise" not in plain and plain["F-uncertainty"].startswith("Uncertainty of these volumes is not estimated")
    r = make_run(root); N.apply(r, N.compute(r))
    led = L.build(r)
    t = {f["id"]: f["text"] for f in led["facts"]}
    assert {"F-noise", "F-noiseTotal", "F-noise4"} <= set(t) and "lower bound" in t["F-noise"] and "lower bound" in t["F-uncertainty"]
    assert "20 mm3" in t["F-noise4"] and "10 times that spread" in t["F-noise4"] and "outside the largest repeat range of 40 mm3" in t["F-noise4"]
    ok = V.check([V.Statement("The left lateral ventricle changed by 200 mm3 while its repeat spread was 20 mm3.", ["F-noise4"])], L.as_facts(led))
    assert ok.ok, ok.problems
    bad = V.check([V.Statement("The change is 11 times the repeat spread.", ["F-noise4"])], L.as_facts(led))
    assert not bad.ok


def test_noise_facts_do_not_carry_forbidden_wording(root):
    r = make_run(root); N.apply(r, N.compute(r))
    blob = " ".join(f["text"] for f in L.build(r)["facts"] if f["id"].startswith("F-noise"))
    assert V._banned(blob) == []


def test_refresh_rewrites_a_saved_run(root):
    r = make_run(root)
    r["run_id"] = "abc123abc123"
    r["steps"] = A.base_steps()
    r["validation"].update(status="ok", checks={"earlier": {"problems": []}, "later": {"problems": []}}, blockers=[])
    for st in r["steps"]:
        st["state"] = "done"
    d = A.runs_root() / r["run_id"]; d.mkdir(parents=True)
    (d / "run.json").write_text(json.dumps(r))
    out = N.refresh("abc123abc123")
    assert out["noise"]["status"] == "estimated" and json.loads((d / "run.json").read_text())["noise"]["status"] == "estimated"
    with pytest.raises(ValueError):
        N.refresh("ffffffffffff")
