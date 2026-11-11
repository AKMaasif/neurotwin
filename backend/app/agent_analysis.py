"""Two-scan comparison, stages 1-2: pair validation and native alignment.

Reads original OASIS-2 volumes (Analyze .hdr/.img) without ever writing to them. Derived files live under
``agent_analysis/<run id>/``. Steps that need tools or models this environment does not have are reported as unavailable,
with what they need; they are never reported as passed.
"""
import json
import math
import re
import shutil
import threading
import uuid
from pathlib import Path

from . import oasis2_api as O

TARGETS_MONTHS = (12, 15, 18)
TOLERANCE_MONTHS = 1.5
DAYS_PER_MONTH = 365.25 / 12
VISIT = re.compile(r"^OAS2_\d{4}_MR\d{1,2}$")
RUN_ID = re.compile(r"^[0-9a-f]{12}$")

SEG_LABELS = {  # SynthSeg 1.0 label names (BBillot/SynthSeg, Apache-2.0); 0 is background and is never measured
    2: "left cerebral white matter", 3: "left cerebral cortex", 4: "left lateral ventricle", 5: "left inferior lateral ventricle",
    7: "left cerebellum white matter", 8: "left cerebellum cortex", 10: "left thalamus", 11: "left caudate", 12: "left putamen",
    13: "left pallidum", 14: "3rd ventricle", 15: "4th ventricle", 16: "brain-stem", 17: "left hippocampus", 18: "left amygdala",
    26: "left accumbens area", 28: "left ventral DC", 41: "right cerebral white matter", 42: "right cerebral cortex",
    43: "right lateral ventricle", 44: "right inferior lateral ventricle", 46: "right cerebellum white matter",
    47: "right cerebellum cortex", 49: "right thalamus", 50: "right caudate", 51: "right putamen", 52: "right pallidum",
    53: "right hippocampus", 54: "right amygdala", 58: "right accumbens area", 60: "right ventral DC"}
SMALL_MM3 = 1000.0   # regions smaller than this are flagged: a few voxels of boundary shift is a large percentage
TOTAL_DISAGREE = 0.05

STEP_NEEDS = {
    "quality_review": "Per-scan checks run; a same-session repeat spread (mpr-2..4, not extracted) is still needed for uncertainty.",
    "anatomical_analysis": "Segmentation output for both scans from a validated tool (SynthSeg): see docs/AGENT_ANALYSIS_SEGMENTATION.md.",
    "longitudinal_comparison": "Regional volumes from the anatomical step on both scans, with one tool version.",
    "findings_review": "Measurements to review; none exist until the steps above run.",
    "report": "Verified measurements. Text may only restate them; real data is not sent to an external text provider.",
}


def runs_root() -> Path:
    return O.root().parent / "agent_analysis"


def tools() -> dict:
    out = {"nibabel": False, "numpy": False, "ants": False, "pydicom": False}
    for name in out:
        try:
            __import__(name)
            out[name] = True
        except Exception:
            pass
    return {
        "formats": {"analyze_nifti": out["nibabel"] and out["numpy"], "dicom": False,
                    "dicom_note": "DICOM reading is not enabled: there is no real DICOM longitudinal data to verify it against."},
        "alignment": {"available": out["ants"] and out["numpy"], "tool": "ANTsPy rigid", "needs": None if out["ants"] else "pip install antspyx"},
        "unavailable": {k: v for k, v in STEP_NEEDS.items()},
    }


def _visit(manifest: dict, mri_id: str):
    for s in manifest["subjects"]:
        for v in s["visits"]:
            if v["mri_id"] == mri_id:
                return s, v
    return None, None


def classify_interval(days: float) -> dict:
    months = days / DAYS_PER_MONTH
    nearest = min(TARGETS_MONTHS, key=lambda t: abs(months - t))
    within = abs(months - nearest) <= TOLERANCE_MONTHS
    return {"days": days, "months": round(months, 2), "nearest_target_months": nearest if within else None, "within_requested_window": within}


def scan_checks(mri_id: str, scan: str = "mpr-1") -> dict:
    import numpy as np
    data, lo, hi, zooms = O._load(mri_id, scan)
    finite = bool(np.isfinite(data).all())
    nonzero = float((data > 0).mean())
    problems = []
    if not finite:
        problems.append("contains non-finite values")
    if nonzero < 0.05:
        problems.append("almost empty volume")
    return {"mri_id": mri_id, "scan": scan, "shape": list(data.shape), "voxel_mm": [round(z, 4) for z in zooms],
            "intensity_min": float(data.min()), "intensity_max": float(data.max()), "p99": round(hi, 1),
            "nonzero_fraction": round(nonzero, 3), "problems": problems}


def validate_pair(earlier: str, later: str, scan: str = "mpr-1") -> dict:
    """Stage 1. Returns status ok / warning / blocked, the measured interval and every limitation found."""
    manifest = O._manifest()
    limits, blocked = [], []
    if not (VISIT.match(earlier) and VISIT.match(later)):
        return {"status": "blocked", "blockers": ["Unknown visit id."], "limitations": []}
    s1, v1 = _visit(manifest, earlier)
    s2, v2 = _visit(manifest, later)
    if v1 is None or v2 is None:
        blocked.append("A selected visit is not in the manifest.")
    elif s1["subject_id"] != s2["subject_id"]:
        blocked.append("The two scans are from different people.")
    elif earlier == later:
        blocked.append("Choose two different visits.")
    interval = None
    if not blocked:
        d1, d2 = v1.get("delay_days"), v2.get("delay_days")
        if d1 is None or d2 is None:
            blocked.append("A visit has no recorded date offset.")
        elif d2 <= d1:
            blocked.append("The later scan is not after the earlier scan.")
        else:
            interval = classify_interval(d2 - d1)
            if not interval["within_requested_window"]:
                limits.append(f"Interval is {interval['months']} months, outside 12, 15 or 18 months (±{TOLERANCE_MONTHS}).")
    checks = {}
    if not blocked:
        for key, vid in (("earlier", earlier), ("later", later)):
            try:
                checks[key] = scan_checks(vid, scan)
            except Exception as exc:
                blocked.append(f"{key} scan could not be read: {getattr(exc, 'detail', None) or type(exc).__name__}")
        if len(checks) == 2:
            a, b = checks["earlier"], checks["later"]
            for key in ("earlier", "later"):
                blocked += [f"{key}: {p}" for p in checks[key]["problems"]]
            if a["shape"] != b["shape"]:
                limits.append("Different image sizes; resampling would be needed and is not applied.")
                blocked.append("Scans have different matrix sizes.")
            if a["voxel_mm"] != b["voxel_mm"]:
                limits.append("Different voxel sizes between visits.")
    limits += ["Dates are OASIS relative day offsets, not calendar dates.",
               "Scanner orientation is not recorded in these Analyze files; no left/right or named anatomy is shown.",
               "Sequence is inferred from the file name (mpr) only; scanner settings are not in the files.",
               "Only one acquisition per visit is used here; repeat acquisitions are not extracted."]
    status = "blocked" if blocked else ("warning" if interval is not None and not interval["within_requested_window"] else "ok")
    return {"status": status, "blockers": blocked, "limitations": limits, "interval": interval, "scan": scan,
            "subject_id": s1["subject_id"] if s1 else None, "checks": checks,
            "visits": {"earlier": v1 and {"mri_id": earlier, "delay_days": v1.get("delay_days")},
                       "later": v2 and {"mri_id": later, "delay_days": v2.get("delay_days")}}}


def _write(run_dir: Path, run: dict) -> None:
    tmp = run_dir / "run.json.tmp"
    tmp.write_text(json.dumps(run, indent=1))
    tmp.replace(run_dir / "run.json")


def load_run(run_id: str) -> dict | None:
    if not RUN_ID.match(run_id):
        return None
    path = runs_root() / run_id / "run.json"
    return json.loads(path.read_text()) if path.is_file() else None


def base_steps() -> list[dict]:
    steps = [{"key": "pair_validation", "label": "Pair validation", "state": "pending", "detail": None},
             {"key": "alignment", "label": "Alignment", "state": "pending", "detail": None}]
    for key, need in STEP_NEEDS.items():
        steps.append({"key": key, "label": key.replace("_", " ").capitalize(), "state": "unavailable", "detail": "Needs: " + need})
    return steps


_CANCEL: dict[str, threading.Event] = {}


def create_run(earlier: str, later: str, scan: str = "mpr-1", parent: str | None = None) -> dict:
    validation = validate_pair(earlier, later, scan)
    run_id = uuid.uuid4().hex[:12]
    run_dir = runs_root() / run_id
    run_dir.mkdir(parents=True)
    run = {"run_id": run_id, "earlier": earlier, "later": later, "scan": scan, "parent_run_id": parent, "state": "queued",
           "validation": validation, "steps": base_steps(), "alignment": None, "producer": "neurotwin-agent-analysis 0.1 (stages 1-2)"}
    step = run["steps"][0]
    if validation["status"] == "blocked":
        step.update(state="blocked", detail="; ".join(validation["blockers"]))
        run["state"] = "blocked"
    else:
        step.update(state="done", detail="Interval and files checked." if validation["status"] == "ok" else "Checked with warnings.")
    _write(run_dir, run)
    return run


def _angle_deg(matrix) -> float:
    import numpy as np
    r = np.asarray(matrix).reshape(3, 3)
    return float(math.degrees(math.acos(max(-1.0, min(1.0, (np.trace(r) - 1) / 2)))))


def align(run_id: str) -> dict:
    """Stage 2. Rigid-align the later scan to the earlier one in voxel space; originals untouched."""
    import numpy as np
    run = load_run(run_id)
    run_dir = runs_root() / run_id
    cancel = _CANCEL.setdefault(run_id, threading.Event())
    step = run["steps"][1]
    try:
        import ants
    except Exception:
        step.update(state="unavailable", detail="Needs: pip install antspyx")
        run["state"] = "unavailable"
        _write(run_dir, run)
        return run
    step.update(state="running", detail="Aligning the later scan to the earlier scan.")
    run["state"] = "running"
    _write(run_dir, run)
    try:
        d1, _, _, z = O._load(run["earlier"], run["scan"])
        d2, _, _, _ = O._load(run["later"], run["scan"])
        fixed = ants.from_numpy(np.ascontiguousarray(d1), spacing=tuple(z))
        moving = ants.from_numpy(np.ascontiguousarray(d2), spacing=tuple(z))
        reg = ants.registration(fixed=fixed, moving=moving, type_of_transform="Rigid", aff_metric="mattes")
        if cancel.is_set():
            step.update(state="cancelled", detail="Cancelled; the result was discarded.")
            run["state"] = "cancelled"
            _write(run_dir, run)
            return run
        aligned = reg["warpedmovout"].numpy().astype("float32")
        mask = d1 > np.percentile(d1, 60)
        before = float(np.corrcoef(d1[mask], d2[mask])[0, 1])
        after = float(np.corrcoef(d1[mask], aligned[mask])[0, 1])
        tx = ants.read_transform(reg["fwdtransforms"][0])
        params = list(tx.parameters)
        rot, shift = _angle_deg(params[:9]), float(np.linalg.norm(params[9:12]))
        shutil.copy(reg["fwdtransforms"][0], run_dir / "later_to_earlier.mat")
        np.save(run_dir / "later_aligned.npy", aligned)
        flags = []
        if after - before < 0.05:
            flags.append("Similarity barely improved; check the alignment before using it.")
        if rot > 15 or shift > 40:
            flags.append("Unusually large head movement estimated; check the alignment.")
        run["alignment"] = {"method": "rigid, mattes mutual information", "tool": f"ANTsPy {ants.__version__}",
                            "correlation_before": round(before, 4), "correlation_after": round(after, 4),
                            "rotation_deg": round(rot, 2), "shift_mm_voxel_frame": round(shift, 2), "flags": flags,
                            "mask": "voxels above the earlier scan's 60th intensity percentile (not a brain mask)",
                            "files": ["later_aligned.npy", "later_to_earlier.mat"]}
        step.update(state="warning" if flags else "done", detail="; ".join(flags) or "Aligned. Derived files stored separately from the originals.")
        run["state"] = "partial"  # becomes complete only when every later step has run
    except Exception as exc:
        step.update(state="failed", detail=f"{type(exc).__name__}: alignment did not finish.")
        run["state"] = "failed"
    _write(run_dir, run)
    return run


def cancel(run_id: str) -> dict | None:
    run = load_run(run_id)
    if run is None:
        return None
    if run["state"] in ("queued", "running"):
        _CANCEL.setdefault(run_id, threading.Event()).set()
        run["state"] = "cancelled"
        run["steps"][1].update(state="cancelled", detail="Cancelled.")
        _write(runs_root() / run_id, run)
    return run


def layer_volume(run: dict, layer: str):
    import numpy as np
    if layer == "later_aligned":
        path = runs_root() / run["run_id"] / "later_aligned.npy"
        if not path.is_file():
            return None
        return np.load(path)
    mri = {"earlier": run["earlier"], "later_original": run["later"]}.get(layer)
    return None if mri is None else O._load(mri, run["scan"])[0]


# ---- stages 3-6: quality review, imported segmentation, volume comparison, findings review, report ----

def seg_dir(mri_id: str) -> Path:
    return O.root() / "segmentations" / mri_id


def _read_seg(mri_id: str):
    """Segmentation produced elsewhere by a named tool. Returns (labels array, tool record) or (None, reason)."""
    d = seg_dir(mri_id)
    tool_file = d / "tool.json"
    seg_file = next((d / n for n in ("seg.nii.gz", "seg.nii", "seg.img") if (d / n).is_file()), None)
    if seg_file is None or not tool_file.is_file():
        return None, f"no segmentation and tool record for {mri_id} (expected seg.nii.gz and tool.json in segmentations/{mri_id}/)"
    import nibabel as nib
    import numpy as np
    tool = json.loads(tool_file.read_text())
    if not tool.get("tool") or not tool.get("version"):
        return None, f"tool.json for {mri_id} must name the tool and its version"
    arr = np.asarray(nib.load(str(seg_file)).dataobj)
    while arr.ndim > 3 and arr.shape[-1] == 1:
        arr = arr[..., 0]
    return np.rint(arr).astype("int16"), tool


def _set(run: dict, key: str, state: str, detail: str) -> None:
    next(s for s in run["steps"] if s["key"] == key).update(state=state, detail=detail)


def analyze(run_id: str) -> dict:
    """Runs after alignment. Each step reports exactly what it could do."""
    import numpy as np
    run = load_run(run_id)
    run_dir = runs_root() / run_id
    if run["state"] != "partial":
        return run
    v = run["validation"]
    qprob = [p for k in ("earlier", "later") for p in v["checks"][k]["problems"]]
    align = run["alignment"]
    _set(run, "quality_review", "warning" if (qprob or align["flags"]) else "done",
         "; ".join(qprob + align["flags"]) or f"Intensity range and coverage normal for both scans; alignment similarity {align['correlation_after']}. No repeat-scan spread, so measurement uncertainty is not estimated.")
    es, et = _read_seg(run["earlier"])
    ls, lt = _read_seg(run["later"])
    if es is None or ls is None:
        reason = "; ".join(x for x in (es is None and et, ls is None and lt) if x)
        _set(run, "anatomical_analysis", "unavailable", "Needs: " + reason)
        for k in ("longitudinal_comparison", "findings_review", "report"):
            _set(run, k, "unavailable", "Needs the anatomical analysis step first.")
        run["state"] = "partial"
        _write(run_dir, run)
        return run
    d1, _, _, zooms = O._load(run["earlier"], run["scan"])
    problems = []
    if es.shape != d1.shape or ls.shape != d1.shape:
        problems.append("segmentation size does not match the scan")
    if (et["tool"], et["version"]) != (lt["tool"], lt["version"]):
        problems.append("the two segmentations came from different tools or versions")
    unknown = sorted((set(np.unique(es).tolist()) | set(np.unique(ls).tolist())) - set(SEG_LABELS) - {0})
    if problems:
        _set(run, "anatomical_analysis", "failed", "; ".join(problems))
        run["state"] = "failed"
        _write(run_dir, run)
        return run
    # bring the later labels onto the earlier anatomy with the stored rigid transform (nearest label, never blended)
    import ants
    fixed = ants.from_numpy(np.ascontiguousarray(d1), spacing=tuple(zooms))
    moving = ants.from_numpy(ls.astype("float32"), spacing=tuple(zooms))
    warped = ants.apply_transforms(fixed=fixed, moving=moving, transformlist=[str(run_dir / "later_to_earlier.mat")], interpolator="genericLabel")
    np.save(run_dir / "earlier_seg.npy", es)
    np.save(run_dir / "later_seg_aligned.npy", np.rint(warped.numpy()).astype("int16"))
    _set(run, "anatomical_analysis", "done",
         f"Segmentation imported from {et['tool']} {et['version']} for both scans; labels carried to the earlier anatomy without blending."
         + (f" Labels outside the known list were ignored: {unknown}." if unknown else ""))
    run["segmentation_tool"] = {"tool": et["tool"], "version": et["version"], "source": et.get("source")}
    vox = float(np.prod(zooms))
    rows, e_tot, l_tot = [], 0.0, 0.0
    for lab, name in SEG_LABELS.items():
        ne, nl = int((es == lab).sum()), int((ls == lab).sum())
        e_mm3, l_mm3 = ne * vox, nl * vox
        e_tot += e_mm3
        l_tot += l_mm3
        rows.append({"label": lab, "name": name, "earlier_mm3": round(e_mm3, 1), "later_mm3": round(l_mm3, 1),
                     "difference_mm3": round(l_mm3 - e_mm3, 1), "difference_pct": None if e_mm3 == 0 else round(100 * (l_mm3 - e_mm3) / e_mm3, 2),
                     "earlier_voxels": ne, "later_voxels": nl, "uncertainty": None})
    run["measurements"] = {"unit": "mm3", "voxel_mm3": round(vox, 3), "source": "voxel counts of the imported segmentation in each scan's own space (not resampled)",
                           "earlier_total_mm3": round(e_tot, 1), "later_total_mm3": round(l_tot, 1), "regions": rows}
    _set(run, "longitudinal_comparison", "done", "Regional volumes measured in each scan's own space; no uncertainty range exists yet.")
    # findings review: deterministic rules, no model
    flags = []
    total_pct = None if e_tot == 0 else (l_tot - e_tot) / e_tot
    if total_pct is None or abs(total_pct) > TOTAL_DISAGREE:
        flags.append("Total labelled volume differs by more than 5% between scans, which points to acquisition or processing differences rather than anatomy." if total_pct is not None else "Earlier scan has no labelled volume.")
    findings = []
    for r in rows:
        why = ["No measurement-uncertainty estimate exists, so the size of this difference cannot be judged against noise."]
        if min(r["earlier_mm3"], r["later_mm3"]) < SMALL_MM3:
            why.append("Small region: a few voxels at the boundary are a large percentage.")
        if r["earlier_voxels"] == 0 or r["later_voxels"] == 0:
            why.append("Region absent in one scan.")
        r["status"] = "uncertain"
        r["review_notes"] = why
        findings.append({"label": r["label"], "name": r["name"], "status": "uncertain", "notes": why})
    run["review"] = {"flags": flags, "findings": findings, "rules": ["uncertainty not estimated", "small region", "region absent", "total volume disagreement"],
                     "note": "Measured differences, not findings of disease. Clinical interpretation is left to a clinician."}
    _set(run, "findings_review", "warning", "; ".join(flags) or "All regional differences are marked uncertain until a measurement-uncertainty estimate exists.")
    top = sorted((r for r in rows if r["difference_pct"] is not None), key=lambda r: -abs(r["difference_pct"]))[:5]
    run["report"] = {"status": "draft for clinical review", "author": "deterministic template; no language model used",
                     "sections": {
                         "measured": [f"{r['name']}: {r['earlier_mm3']} to {r['later_mm3']} mm3 ({r['difference_pct']:+.1f}%)" for r in top],
                         "quality_limitations": v["limitations"] + align["flags"],
                         "processing": [f"Alignment: {align['method']} ({align['tool']}), similarity {align['correlation_before']} to {align['correlation_after']}",
                                        f"Segmentation: {run['segmentation_tool']['tool']} {run['segmentation_tool']['version']}"],
                         "needs_clinical_review": ["Every regional difference is marked uncertain; no noise estimate exists.",
                                                   "Nothing here is a diagnosis; no region is labelled as diseased."] + flags}}
    _set(run, "report", "done", "Draft report built from the measurements above; needs clinical review.")
    run["state"] = "complete"
    _write(run_dir, run)
    return run


def candidate_pairs() -> list[dict]:
    """Every ordered pair of locally extracted visits of one person, with its interval class."""
    manifest = O._manifest()
    out = []
    for s in manifest["subjects"]:
        ready = [v for v in s["visits"] if O._scans(v["mri_id"])]
        for i, a in enumerate(ready):
            for b in ready[i + 1:]:
                iv = classify_interval(b["delay_days"] - a["delay_days"])
                out.append({"subject_id": s["subject_id"], "earlier": a["mri_id"], "later": b["mri_id"], "interval": iv,
                            "segmented": seg_dir(a["mri_id"]).is_dir() and seg_dir(b["mri_id"]).is_dir()})
    return sorted(out, key=lambda p: (not p["interval"]["within_requested_window"], p["subject_id"]))


def layer_labels(run: dict, layer: str):
    import numpy as np
    d = runs_root() / run["run_id"]
    if layer in ("earlier_seg", "later_seg_aligned") and (d / f"{layer}.npy").is_file():
        return np.load(d / f"{layer}.npy")
    return None


def run_all(run_id: str) -> dict:
    """The Agent Analysis button: alignment, then quality review through report, in order."""
    align(run_id)
    return analyze(run_id)
