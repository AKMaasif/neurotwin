import json

import pytest

nib = pytest.importorskip("nibabel")
np = pytest.importorskip("numpy")
pytest.importorskip("PIL")

from app import agent_analysis as A
from app import oasis2_api


@pytest.fixture(autouse=True)
def clear_cache():
    oasis2_api._volume.cache_clear()


def visit(mri, delay):
    return {"mri_id": mri, "delay_days": delay, "years_since_previous": None, "status": "usable", "usable_scans": ["mpr-1"],
            "problems": [], "clinical": {}, "imported_measures": {}}


def blob(shift=0, seed=0):
    rng = np.random.default_rng(seed)
    x, y, z = np.mgrid[0:24, 0:24, 0:20]
    v = 800 * np.exp(-(((x - 12 - shift) / 6) ** 2 + ((y - 12) / 7) ** 2 + ((z - 10) / 5) ** 2)) + rng.normal(0, 5, (24, 24, 20)) + 50
    return v.astype(np.float32)


@pytest.fixture
def data(tmp_path, monkeypatch):
    monkeypatch.setenv("NEUROTWIN_IMAGING_ROOT", str(tmp_path))
    monkeypatch.setenv("NEUROTWIN_IMAGING_USERS", "demo-dr-layla")
    base = tmp_path / "oasis2"
    subjects = []
    for sid, delays in (("OAS2_0001", (0, 457, 700)), ("OAS2_0002", (0, 30))):
        visits = []
        for k, d in enumerate(delays, 1):
            mri = f"{sid}_MR{k}"
            raw = base / "extracted" / "OAS2_RAW_PART1" / mri / "RAW"
            raw.mkdir(parents=True)
            nib.save(nib.AnalyzeImage(blob(shift=k, seed=k), np.eye(4)), raw / "mpr-1.nifti.img")
            visits.append(visit(mri, d))
        subjects.append({"subject_id": sid, "group_label_from_dataset": "x", "level1_compare": True, "level2_trend": False, "visits": visits})
    (base / "manifest.json").write_text(json.dumps({"summary": {}, "subjects": subjects}))
    return base


def test_interval_classes():
    assert A.classify_interval(457)["nearest_target_months"] == 15
    assert A.classify_interval(365)["nearest_target_months"] == 12
    assert A.classify_interval(560)["nearest_target_months"] == 18
    assert A.classify_interval(120)["within_requested_window"] is False


def test_valid_pair_reports_interval_and_limits(data):
    v = A.validate_pair("OAS2_0001_MR1", "OAS2_0001_MR2")
    assert v["status"] == "ok" and v["interval"]["nearest_target_months"] == 15
    assert any("relative" in x for x in v["limitations"]) and any("orientation" in x for x in v["limitations"])


def test_outside_window_is_a_warning_not_hidden(data):
    v = A.validate_pair("OAS2_0002_MR1", "OAS2_0002_MR2")
    assert v["status"] == "warning" and any("outside" in x for x in v["limitations"])


@pytest.mark.parametrize("a,b,word", [("OAS2_0001_MR1", "OAS2_0002_MR2", "different people"), ("OAS2_0001_MR2", "OAS2_0001_MR1", "not after"),
                                      ("OAS2_0001_MR1", "OAS2_0001_MR1", "different visits"), ("OAS2_0001_MR1", "OAS2_0001_MR9", "manifest"),
                                      ("../x", "OAS2_0001_MR1", "Unknown")])
def test_blocked_pairs(data, a, b, word):
    v = A.validate_pair(a, b)
    assert v["status"] == "blocked" and word in " ".join(v["blockers"])


def test_mismatched_sizes_blocked(data):
    raw = data / "extracted" / "OAS2_RAW_PART1" / "OAS2_0001_MR2" / "RAW"
    nib.save(nib.AnalyzeImage(np.ones((10, 10, 10), np.float32) * 100, np.eye(4)), raw / "mpr-1.nifti.img")
    v = A.validate_pair("OAS2_0001_MR1", "OAS2_0001_MR2")
    assert v["status"] == "blocked"


def test_unextracted_scan_blocked(data):
    v = A.validate_pair("OAS2_0001_MR1", "OAS2_0001_MR3", scan="mpr-2")
    assert v["status"] == "blocked"


def test_unavailable_steps_are_never_passed(data):
    run = A.create_run("OAS2_0001_MR1", "OAS2_0001_MR2")
    states = {s["key"]: s["state"] for s in run["steps"]}
    assert states["pair_validation"] == "done"
    for k in ("quality_review", "anatomical_analysis", "longitudinal_comparison", "findings_review", "report"):
        assert states[k] == "unavailable"
    assert any("Needs:" in s["detail"] for s in run["steps"][2:])


def test_alignment_improves_similarity_and_keeps_originals(data):
    pytest.importorskip("ants")
    img = data / "extracted" / "OAS2_RAW_PART1" / "OAS2_0001_MR2" / "RAW" / "mpr-1.nifti.img"
    before = img.read_bytes()
    run = A.create_run("OAS2_0001_MR1", "OAS2_0001_MR2")
    out = A.align(run["run_id"])
    assert img.read_bytes() == before
    assert out["state"] == "aligned" and out["alignment"]["correlation_after"] >= out["alignment"]["correlation_before"]
    assert (A.runs_root() / run["run_id"] / "later_aligned.npz").is_file()
    assert A.load_run(run["run_id"])["alignment"] is not None  # persisted


def test_blocked_run_does_not_align(data):
    run = A.create_run("OAS2_0001_MR1", "OAS2_0002_MR2")
    assert run["state"] == "blocked" and run["steps"][0]["state"] == "blocked"


def test_run_ids_are_validated(data):
    assert A.load_run("../../etc") is None


def test_api_flow(client, login, data):
    h = login("demo-dr-layla")
    assert client.get("/api/imaging/agent/tools").status_code == 401
    assert client.get("/api/imaging/agent/tools", headers=login("demo-yousef")).status_code == 403
    r = client.post("/api/imaging/agent/runs", json={"earlier": "OAS2_0001_MR1", "later": "OAS2_0001_MR2"}, headers=h)
    assert r.status_code == 202
    rid = r.json()["run_id"]
    got = client.get(f"/api/imaging/agent/runs/{rid}", headers=h).json()
    assert got["state"] in ("partial", "failed", "unavailable", "running", "queued")
    assert client.get("/api/imaging/agent/runs/zzz", headers=h).status_code == 404
    assert client.get(f"/api/imaging/agent/runs/{rid}/slice.png?layer=earlier&axis=2&index=5", headers=h).headers["content-type"] == "image/png"
    assert client.get(f"/api/imaging/agent/runs/{rid}/slice.png?layer=bad", headers=h).status_code == 422
    assert client.get(f"/api/imaging/agent/runs/{rid}/slice.png?layer=earlier&axis=2&index=99", headers=h).status_code == 422
    assert client.post(f"/api/imaging/agent/runs/{rid}/retry", headers=h).json()["parent_run_id"] == rid
    blocked = client.post("/api/imaging/agent/runs", json={"earlier": "OAS2_0001_MR1", "later": "OAS2_0002_MR2"}, headers=h)
    assert blocked.json()["state"] == "blocked"


def test_cancel_marks_run(data):
    run = A.create_run("OAS2_0001_MR1", "OAS2_0001_MR2")
    assert A.cancel(run["run_id"])["state"] == "cancelled"


def write_seg(base, mri, labels_shift=0, tool="SynthSeg", version="1.0"):
    d = base / "segmentations" / mri
    d.mkdir(parents=True)
    seg = np.zeros((24, 24, 20), np.int16)
    seg[8:16, 8:16, 6:14] = 3
    seg[10:14, 10:14, 8:12 + labels_shift] = 17
    nib.save(nib.Nifti1Image(seg, A.scan_affine(mri, "mpr-1")), d / "seg.nii.gz")
    (d / "tool.json").write_text(json.dumps({"tool": tool, "version": version, "source": "test"}))


def test_without_segmentation_steps_stay_unavailable(data):
    pytest.importorskip("ants")
    run = A.create_run("OAS2_0001_MR1", "OAS2_0001_MR2")
    out = A.run_all(run["run_id"])
    states = {s["key"]: s["state"] for s in out["steps"]}
    assert states["quality_review"] in ("done", "warning") and states["anatomical_analysis"] == "unavailable"
    assert states["longitudinal_comparison"] == states["findings_review"] == states["report"] == "unavailable"
    assert out["state"] == "partial" and "segmentations/OAS2_0001_MR1" in out["steps"][3]["detail"]


def test_with_segmentation_measures_and_marks_uncertain(data):
    pytest.importorskip("ants")
    write_seg(data, "OAS2_0001_MR1")
    write_seg(data, "OAS2_0001_MR2", labels_shift=-2)
    out = A.run_all(A.create_run("OAS2_0001_MR1", "OAS2_0001_MR2")["run_id"])
    assert out["state"] == "complete"
    hip = next(r for r in out["measurements"]["regions"] if r["label"] == 17)
    assert hip["earlier_voxels"] == 4 * 4 * 4 and hip["later_voxels"] == 4 * 4 * 2
    assert hip["difference_pct"] == -50.0 and hip["uncertainty"] is None and hip["status"] == "uncertain"
    assert all(f["status"] == "uncertain" for f in out["review"]["findings"])
    assert out["report"]["status"].startswith("draft") and "no language model" in out["report"]["author"]
    text = json.dumps(out["report"]).lower()
    assert "alzheimer" not in text and "diseased" not in text.replace("no region is labelled as diseased", "")


def test_mixed_tool_versions_fail(data):
    pytest.importorskip("ants")
    write_seg(data, "OAS2_0001_MR1")
    write_seg(data, "OAS2_0001_MR2", version="2.0")
    out = A.run_all(A.create_run("OAS2_0001_MR1", "OAS2_0001_MR2")["run_id"])
    assert out["state"] == "failed" and "different tools or versions" in out["steps"][3]["detail"]


def test_pairs_listing_and_overlay_endpoints(client, login, data):
    pytest.importorskip("ants")
    h = login("demo-dr-layla")
    pairs = client.get("/api/imaging/agent/pairs", headers=h).json()["pairs"]
    assert any(p["earlier"] == "OAS2_0001_MR1" and p["interval"]["nearest_target_months"] == 15 and not p["segmented"] for p in pairs)
    write_seg(data, "OAS2_0001_MR1")
    write_seg(data, "OAS2_0001_MR2", labels_shift=-2)
    rid = client.post("/api/imaging/agent/runs", json={"earlier": "OAS2_0001_MR1", "later": "OAS2_0001_MR2"}, headers=h).json()["run_id"]
    got = client.get(f"/api/imaging/agent/runs/{rid}", headers=h).json()
    assert got["state"] == "complete"
    for layer in ("regions", "change"):
        r = client.get(f"/api/imaging/agent/runs/{rid}/overlay.png?layer={layer}&axis=2&index=10&label=17", headers=h)
        assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    assert client.get(f"/api/imaging/agent/runs/{rid}/overlay.png?layer=x", headers=h).status_code == 422


def test_finer_segmentation_grid_is_measured_natively_and_resampled_for_display(data):
    pytest.importorskip("ants")
    # a tool output on a grid twice as fine (as SynthSeg does): volumes come from its own voxels, overlays from the scan grid
    for mri in ("OAS2_0001_MR1", "OAS2_0001_MR2"):
        d = data / "segmentations" / mri
        d.mkdir(parents=True)
        aff = A.scan_affine(mri, "mpr-1").copy()
        aff[:3, :3] /= 2
        fine = np.zeros((48, 48, 40), np.int16)
        fine[16:32, 16:32, 12:28] = 17
        nib.save(nib.Nifti1Image(fine, aff), d / "seg.nii.gz")
        (d / "tool.json").write_text(json.dumps({"tool": "SynthSeg", "version": "1.0"}))
    out = A.run_all(A.create_run("OAS2_0001_MR1", "OAS2_0001_MR2")["run_id"])
    assert out["state"] == "complete"
    hip = next(r for r in out["measurements"]["regions"] if r["label"] == 17)
    assert hip["earlier_voxels"] == 16 * 16 * 16 and hip["earlier_mm3"] == 16 * 16 * 16 * 0.125  # native voxel volume, not the scan's
    assert A.layer_labels(out, "earlier_seg").shape == (24, 24, 20)


def test_segmentation_missing_part_of_the_scan_is_refused(data):
    pytest.importorskip("ants")
    for mri in ("OAS2_0001_MR1", "OAS2_0001_MR2"):
        d = data / "segmentations" / mri
        d.mkdir(parents=True)
        nib.save(nib.Nifti1Image(np.ones((6, 6, 6), np.int16), A.scan_affine(mri, "mpr-1")), d / "seg.nii.gz")
        (d / "tool.json").write_text(json.dumps({"tool": "SynthSeg", "version": "1.0"}))
    out = A.run_all(A.create_run("OAS2_0001_MR1", "OAS2_0001_MR2")["run_id"])
    assert out["state"] == "failed" and "field of view" in out["steps"][3]["detail"]


def test_completed_run_is_self_contained_and_listed(client, login, data):
    pytest.importorskip("ants")
    write_seg(data, "OAS2_0001_MR1")
    write_seg(data, "OAS2_0001_MR2", labels_shift=-2)
    out = A.run_all(A.create_run("OAS2_0001_MR1", "OAS2_0001_MR2")["run_id"])
    assert out["state"] == "complete"
    assert "suggested_follow_up" in out["report"]["sections"] and "alzheimer" not in json.dumps(out["report"]).lower()
    import shutil
    shutil.rmtree(data / "extracted")  # a saved run must open without the original scans
    oasis2_api._volume.cache_clear()
    h = login("demo-dr-layla")
    listed = client.get("/api/imaging/agent/saved", headers=h).json()["runs"]
    assert [r["run_id"] for r in listed] == [out["run_id"]] and listed[0]["target_months"] == 15
    rid = out["run_id"]
    for url in (f"slice.png?layer=earlier&axis=0&index=3", "slice.png?layer=later_aligned&axis=2&index=5", "slice.png?layer=later_original&axis=1&index=4",
                "overlay.png?layer=regions&axis=2&index=10", "overlay.png?layer=change&axis=2&index=10"):
        assert client.get(f"/api/imaging/agent/runs/{rid}/{url}", headers=h).status_code == 200, url


def test_saved_list_skips_blocked_and_duplicate_pairs(data):
    pytest.importorskip("ants")
    A.create_run("OAS2_0001_MR1", "OAS2_0002_MR2")  # blocked
    first = A.run_all(A.create_run("OAS2_0001_MR1", "OAS2_0001_MR2")["run_id"])
    second = A.run_all(A.create_run("OAS2_0001_MR1", "OAS2_0001_MR2")["run_id"])
    assert [r["run_id"] for r in A.list_runs()] == [second["run_id"]] and first["run_id"] != second["run_id"]


def test_cancel_stops_the_worker_process(monkeypatch, tmp_path):
    import subprocess
    import sys
    import threading
    import time
    real = subprocess.Popen
    started = []

    def slow(cmd, **kw):
        p = real([sys.executable, "-c", "import time; time.sleep(60)"])
        started.append(p)
        return p
    monkeypatch.setattr(A.subprocess, "Popen", slow)
    cancel = threading.Event()
    threading.Timer(0.5, cancel.set).start()
    t0 = time.time()
    with pytest.raises(A.Cancelled):
        A._worker("register", tmp_path, cancel)
    assert time.time() - t0 < 5 and started[0].poll() is not None  # stopped, not left running


def test_failed_worker_reports_failure(monkeypatch, tmp_path):
    import subprocess
    import sys
    real = subprocess.Popen
    monkeypatch.setattr(A.subprocess, "Popen", lambda cmd, **kw: real([sys.executable, "-c", "import sys; sys.exit(3)"], stderr=subprocess.PIPE))
    import threading
    with pytest.raises(RuntimeError):
        A._worker("register", tmp_path, threading.Event())
