"""Same-session repeat spread: a first, partial estimate of measurement noise (step 9).

The question: how much does a structure's volume change between acquisitions that should be identical? OASIS-2 stores several back-to-back
scans of one session (mpr-1 to mpr-4). If each is segmented by the same tool and version (outside NeuroTwin), the volumes of one structure across those
repeats show how much the acquisition and the segmentation alone move the number.

What is computed, per structure and for the total of the measured structures:
  - the pooled standard deviation across repeats: for each visit with at least two repeats, the sum of squared deviations from that visit's mean;
    the sums are added over both visits and divided by the total degrees of freedom (repeats minus one, per visit). At least 2 degrees of freedom are
    needed, otherwise nothing is estimated;
  - the largest range (max minus min) seen across repeats in either visit;
  - for the measured earlier-to-later difference: the difference as a multiple of that SD (derived), and whether it lies inside the largest repeat range.

What it is NOT, and the text shown with it says so:
  - a lower bound only. Back-to-back repeats share the same session, so positioning, time of day, hydration, scanner drift and everything else that changes
    between visits is not in it;
  - not a significance test, no p-value, no "real change" label. No threshold is chosen, so none is invented. The status of every difference stays "uncertain";
  - with very few repeats the SD itself is very uncertain (degrees of freedom are shown).
Repeats that were segmented by another tool or version are left out and listed. A repeat whose total differs from the main scan's by more than 5% is kept but flagged.

Layout of the inputs: segmentations/<MRI_ID>/ (the main scan, mpr-1) and segmentations/<MRI_ID>/repeats/<scan>/{seg.nii.gz, tool.json} (scripts/agent_segmentation.py).
"""
from __future__ import annotations

import json
import math
from pathlib import Path

VERSION = "agent-noise/0.1"
MIN_DF = 2
TOTAL_FLAG = 0.05
OLD_NOTE = "No measurement-uncertainty estimate exists, so the size of this difference cannot be judged against noise."
OLD_REVIEW = "Every regional difference is marked uncertain; no noise estimate exists."
OLD_FOLLOW = "Before any change is interpreted, estimate measurement noise: same-session repeat scans (mpr-2 to mpr-4) can give a spread for each region."
OLD_LONG = "Regional volumes counted on the segmentation tool's own grid; no uncertainty range exists yet."
OLD_FIND = "All regional differences are marked uncertain until a measurement-uncertainty estimate exists."
LOWER_BOUND = ("Same-session repeat spread only. Positioning, time of day and other differences between the two visits are not included, so real measurement noise is at least this large. "
               "It is not a test of whether a change is real.")


def _root():
    from . import oasis2_api as O
    return O.root()


def repeat_dirs(mri_id: str) -> dict[str, Path]:
    d = _root() / "segmentations" / mri_id / "repeats"
    return {p.name: p for p in sorted(d.iterdir()) if p.is_dir()} if d.is_dir() else {}


def _volumes(seg_dir: Path, labels: list[int]):
    """(per-label mm3 dict, tool record) for one segmentation folder, or (None, reason)."""
    import nibabel as nib
    import numpy as np
    tool_file = seg_dir / "tool.json"
    seg_file = next((seg_dir / n for n in ("seg.nii.gz", "seg.nii", "seg.img") if (seg_dir / n).is_file()), None)
    if seg_file is None or not tool_file.is_file():
        return None, "no segmentation and tool record"
    tool = json.loads(tool_file.read_text())
    if not tool.get("tool") or not tool.get("version"):
        return None, "tool.json does not name the tool and its version"
    img = nib.load(str(seg_file))
    arr = np.asarray(img.dataobj)
    while arr.ndim > 3 and arr.shape[-1] == 1:
        arr = arr[..., 0]
    arr = np.rint(arr).astype("int16")
    vox = abs(float(np.linalg.det(img.affine[:3, :3])))
    counts = np.bincount(arr[arr > 0].ravel(), minlength=max(labels) + 1)
    return {lab: round(float(counts[lab]) * vox, 3) for lab in labels}, tool


def visit_volumes(mri_id: str, labels: list[int], main_tool: dict) -> dict:
    """Volumes of every usable repeat of one visit. The main scan (mpr-1) is the first repeat."""
    used, skipped = {}, []
    main, mt = _volumes(_root() / "segmentations" / mri_id, labels)
    if main is not None:
        used["mpr-1"] = main
    for scan, d in repeat_dirs(mri_id).items():
        vols, tool = _volumes(d, labels)
        if vols is None:
            skipped.append({"scan": scan, "reason": tool})
        elif (tool["tool"], tool["version"]) != (main_tool["tool"], main_tool["version"]):
            skipped.append({"scan": scan, "reason": f"segmented with {tool['tool']} {tool['version']}, not {main_tool['tool']} {main_tool['version']}"})
        else:
            used[scan] = vols
    flags = []
    if "mpr-1" in used:
        t0 = sum(used["mpr-1"].values())
        for s, v in used.items():
            if s != "mpr-1" and t0 and abs(sum(v.values()) - t0) / t0 > TOTAL_FLAG:
                flags.append(f"{s}: total labelled volume differs from mpr-1 by more than 5%; kept, but the spread may be inflated by a failed acquisition or segmentation.")
    return {"scans": used, "skipped": skipped, "flags": flags}


def pooled(groups: list[list[float]]) -> dict:
    """Pooled SD over visits (each a list of repeat volumes). Visits with fewer than two repeats add nothing."""
    ss = df = 0.0
    rng = 0.0
    allv = []
    for g in groups:
        if len(g) >= 2:
            m = sum(g) / len(g)
            ss += sum((x - m) ** 2 for x in g)
            df += len(g) - 1
            rng = max(rng, max(g) - min(g))
        allv += g
    if df < MIN_DF:
        return {"status": "not_estimated", "df": int(df), "reason": f"Needs at least {MIN_DF} degrees of freedom (two visits with two repeats, or one visit with three); this has {int(df)}."}
    sd = math.sqrt(ss / df)
    mean = sum(allv) / len(allv)
    return {"status": "estimated", "df": int(df), "sd_mm3": round(sd, 2), "cv_pct": None if mean == 0 else round(100 * sd / mean, 2), "max_range_mm3": round(rng, 2), "mean_mm3": round(mean, 1)}


def estimate(earlier: dict, later: dict, regions: list[dict]) -> dict:
    """`earlier`/`later` are visit_volumes() results. Returns the noise record stored as run["noise"]."""
    ke, kl = sorted(earlier["scans"]), sorted(later["scans"])
    base = {"version": VERSION, "earlier_repeats": ke, "later_repeats": kl, "skipped": earlier["skipped"] + later["skipped"], "flags": earlier["flags"] + later["flags"], "note": LOWER_BOUND}
    if max(len(ke), len(kl)) < 2:
        return {**base, "status": "not_estimated", "reason": "No repeat scans were segmented for either visit.", "regions": {}, "total": None}
    out = {}
    for r in regions:
        lab = r["label"]
        p = pooled([[v[lab] for v in earlier["scans"].values()], [v[lab] for v in later["scans"].values()]])
        if p["status"] == "estimated":
            d = r["difference_mm3"]
            p["difference_mm3"] = d
            p["ratio"] = None if p["sd_mm3"] == 0 else round(abs(d) / p["sd_mm3"], 2)
            p["within_repeat_range"] = abs(d) <= p["max_range_mm3"]
        out[str(lab)] = p
    tot = pooled([[sum(v.values()) for v in earlier["scans"].values()], [sum(v.values()) for v in later["scans"].values()]])
    if tot["status"] == "estimated":
        d = sum(r["later_mm3"] - r["earlier_mm3"] for r in regions)
        tot["difference_mm3"] = round(d, 1)
        tot["ratio"] = None if tot["sd_mm3"] == 0 else round(abs(d) / tot["sd_mm3"], 2)
        tot["within_repeat_range"] = abs(d) <= tot["max_range_mm3"]
    est = any(v["status"] == "estimated" for v in out.values())
    return {**base, "status": "estimated" if est else "not_estimated", "reason": None if est else "Not enough repeats to estimate a spread.", "regions": out, "total": tot}


def compute(run: dict) -> dict:
    """Read the repeats for both visits of this run and estimate. Never raises: a failure is recorded as not_estimated with the reason."""
    from .agent_analysis import SEG_LABELS
    try:
        tool = run.get("segmentation_tool")
        if not tool or not run.get("measurements"):
            return {"version": VERSION, "status": "not_estimated", "reason": "The run has no measurements yet.", "regions": {}, "total": None, "skipped": [], "flags": [], "note": LOWER_BOUND, "earlier_repeats": [], "later_repeats": []}
        labels = sorted(SEG_LABELS)
        return estimate(visit_volumes(run["earlier"], labels, tool), visit_volumes(run["later"], labels, tool), run["measurements"]["regions"])
    except Exception as e:  # noqa: BLE001  the main comparison must not fail because the optional estimate did
        return {"version": VERSION, "status": "not_estimated", "reason": f"The repeat scans could not be read: {type(e).__name__}.", "regions": {}, "total": None, "skipped": [], "flags": [], "note": LOWER_BOUND, "earlier_repeats": [], "later_repeats": []}


def apply(run: dict, noise: dict) -> dict:
    """Write the estimate into the run: per-region fields, review notes and report lines. Idempotent; 'uncertain' is never changed to anything else."""
    run["noise"] = noise
    est = noise["status"] == "estimated"
    for r in (run.get("measurements") or {}).get("regions", []):
        n = noise["regions"].get(str(r["label"])) if est else None
        r["repeat"] = n if n and n["status"] == "estimated" else None
        notes = [x for x in r.get("review_notes", []) if x != OLD_NOTE and not x.startswith("Same-session repeat spread")]
        if r["repeat"]:
            q = r["repeat"]
            ratio = "the repeat spread was zero" if q["ratio"] is None else f"the difference is {q['ratio']} times that spread"
            notes.insert(0, f"Same-session repeat spread {q['sd_mm3']} mm3 ({q['df']} degrees of freedom), {ratio}; "
                            f"{'inside' if q['within_repeat_range'] else 'outside'} the largest repeat range of {q['max_range_mm3']} mm3. A lower bound, not a test.")
        else:
            notes.insert(0, OLD_NOTE)
        r["review_notes"] = notes
    for f in (run.get("review") or {}).get("findings", []):
        r = next((x for x in run["measurements"]["regions"] if x["label"] == f["label"]), None)
        if r:
            f["notes"] = r["review_notes"]
    steps = {s["key"]: s for s in run.get("steps", [])}
    if "longitudinal_comparison" in steps and steps["longitudinal_comparison"]["state"] == "done":
        steps["longitudinal_comparison"]["detail"] = (f"Regional volumes counted on the segmentation tool's own grid; same-session repeat spread estimated from {len(noise['earlier_repeats'])} earlier and "
                                                       f"{len(noise['later_repeats'])} later repeats (a lower bound)." if est else OLD_LONG)
    if "findings_review" in steps and steps["findings_review"]["state"] == "warning" and not (run.get("review") or {}).get("flags"):
        steps["findings_review"]["detail"] = ("All regional differences stay marked uncertain; only a same-session repeat spread (a lower bound) exists." if est else OLD_FIND)
    sec = (run.get("report") or {}).get("sections")
    if sec:
        sec["needs_clinical_review"] = [("Every regional difference stays marked uncertain; only a same-session repeat spread (a lower bound) exists." if est else OLD_REVIEW)
                                        if x in (OLD_REVIEW,) or x.startswith("Every regional difference") else x for x in sec["needs_clinical_review"]]
        sec["suggested_follow_up"] = [(("Same-session repeat scans were used for a spread. Between-visit variation is still not estimated; a repeat scan on another day with the same protocol and tool would add it.")
                                       if est else OLD_FOLLOW) if (x == OLD_FOLLOW or x.startswith("Same-session repeat scans were used")) else x for x in sec["suggested_follow_up"]]
    return run


def refresh(run_id: str) -> dict:
    """Recompute the estimate for a saved run (new repeats imported later). Does not touch alignment or the main volumes."""
    from . import agent_analysis as A
    run = A.load_run(run_id)
    if run is None or not run.get("measurements"):
        raise ValueError("The run has no measurements.")
    apply(run, compute(run))
    A._write(A.runs_root() / run_id, run)
    return run
