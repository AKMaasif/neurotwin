"""Fact ledger for Agent Analysis: every number an AI agent may cite, with a stable id. Rules only, no model.

The ledger is built from a finished run (run.json). Facts are of three kinds, kept apart on purpose:
  measured  taken as stored: the interval, alignment figures, segmentation volumes and voxel counts;
  derived   simple arithmetic on measured values (annualised rate, left-right gap, ventricle share), labelled as derived;
  stated    fixed statements of what is not known (uncertainty is not estimated).
An agent sentence must cite fact ids, and may contain only numbers found in the facts it cites (validator.py).
The change profile describes what changed in plain structure. It is not a finding: no region is called normal or abnormal,
no cut-offs are applied, and nothing predicts anything.
"""
from __future__ import annotations

from . import validator as V

VERSION = "agent-ledger/0.1"
SMALL_MM3 = 1500.0  # same threshold the charts use for "small structure"
VENTRICLES = ("lateral ventricle", "inferior lateral ventricle", "3rd ventricle", "4th ventricle")


def _n(v: float, nd: int = 0) -> str:
    s = f"{v:.{nd}f}"
    return s.rstrip("0").rstrip(".") if "." in s else s


def _pct(v: float | None) -> str:
    return "not available" if v is None else f"{v:+.1f}%"


def _side(name: str) -> tuple[str | None, str]:
    for s in ("left", "right"):
        if name.startswith(s + " "):
            return s, name[len(s) + 1:]
    return None, name


def build(run: dict) -> dict:
    """Returns {version, run_id, facts: [{id, kind, text}], profile, complete}. Missing parts give no fact, never a default."""
    facts: list[tuple[str, str, str]] = []  # id, kind, text
    iv = (run.get("validation") or {}).get("interval")
    months = iv["months"] if iv else None
    if iv:
        facts.append(("F-interval", "measured", f"The two scans are {_n(iv['months'], 1)} months ({_n(iv['days'])} days) apart, from the recorded day offsets."))
    al = run.get("alignment")
    if al:
        facts.append(("F-align", "measured", f"Alignment by {al['method']} ({al['tool']}): image similarity {al['correlation_before']} before and {al['correlation_after']} after, "
                      f"estimated head movement {_n(al['rotation_deg'], 1)} degrees and {_n(al['shift_mm_voxel_frame'], 1)} mm."))
        for i, f in enumerate(al.get("flags") or [], 1):
            facts.append((f"F-alignflag{i}", "measured", f"Alignment flag: {f}"))
    for i, l in enumerate((run.get("validation") or {}).get("limitations") or [], 1):
        facts.append((f"F-limit{i}", "measured", f"Limitation of this pair: {l}"))
    m, st = run.get("measurements"), run.get("segmentation_tool") or {}
    profile: dict = {"available": bool(m)}
    if m:
        facts.append(("F-seg", "measured", f"Volumes come from voxel counts of the {st.get('tool', 'imported')} {st.get('version', '')} segmentation, imported and not run by NeuroTwin."))
        tot_e, tot_l = m["earlier_total_mm3"], m["later_total_mm3"]
        tp = 100 * (tot_l - tot_e) / tot_e if tot_e else None
        facts.append(("F-total", "measured", f"Total of the {len(m['regions'])} measured structures: {_n(tot_e)} mm3 earlier and {_n(tot_l)} mm3 later (difference {_n(tot_l - tot_e)} mm3, {_pct(tp)})."))
        facts.append(("F-uncertainty", "stated", "Uncertainty of these volumes is not estimated, so every difference is uncertain."))
        by_name = {}
        for r in m["regions"]:
            by_name[r["name"]] = r
            small = r["earlier_mm3"] < SMALL_MM3
            facts.append((f"F-R{r['label']}", "measured",
                          f"{r['name']}: {_n(r['earlier_mm3'])} mm3 earlier ({r['earlier_voxels']} voxels), {_n(r['later_mm3'])} mm3 later ({r['later_voxels']} voxels), "
                          f"difference {_n(r['difference_mm3'])} mm3 ({_pct(r['difference_pct'])})." + (" Small structure." if small else "")))
            if months and r["difference_pct"] is not None:
                facts.append((f"F-rate{r['label']}", "derived", f"{r['name']}: {_pct(r['difference_pct'] * 12 / months)} per 12 months if the change were spread evenly over the {_n(months, 1)} months (derived, not measured)."))
        pairs = []
        for name, r in by_name.items():
            side, base = _side(name)
            if side == "left" and f"right {base}" in by_name:
                rr = by_name[f"right {base}"]
                if r["difference_pct"] is not None and rr["difference_pct"] is not None:
                    gap = abs(r["difference_pct"] - rr["difference_pct"])
                    pairs.append({"structure": base, "left_label": r["label"], "right_label": rr["label"], "left_pct": r["difference_pct"], "right_pct": rr["difference_pct"], "gap_points": round(gap, 2)})
                    facts.append((f"F-lr{r['label']}", "derived", f"{base}: left {_pct(r['difference_pct'])}, right {_pct(rr['difference_pct'])}, gap {_n(gap, 1)} percentage points (derived)."))
        pairs.sort(key=lambda p: -p["gap_points"])
        vent = [r for n, r in by_name.items() if any(n.endswith(v) for v in VENTRICLES)]
        if vent and tot_e and tot_l:
            ve, vl = sum(r["earlier_mm3"] for r in vent), sum(r["later_mm3"] for r in vent)
            facts.append(("F-vent", "derived", f"Ventricle volume is {_n(100 * ve / tot_e, 1)}% of the measured structures earlier and {_n(100 * vl / tot_l, 1)}% later "
                          f"({_n(ve)} to {_n(vl)} mm3; derived)."))
            profile["ventricle_share_pct"] = {"earlier": round(100 * ve / tot_e, 2), "later": round(100 * vl / tot_l, 2)}
        ranked = sorted([r for r in m["regions"] if r["difference_pct"] is not None], key=lambda r: -abs(r["difference_pct"]))
        profile.update({
            "total": {"earlier_mm3": tot_e, "later_mm3": tot_l, "difference_pct": None if tp is None else round(tp, 2)},
            "largest_percent": [{"id": f"F-R{r['label']}", "name": r["name"], "pct": r["difference_pct"], "small": r["earlier_mm3"] < SMALL_MM3} for r in ranked[:5]],
            "largest_mm3": [{"id": f"F-R{r['label']}", "name": r["name"], "mm3": r["difference_mm3"]} for r in sorted(m["regions"], key=lambda r: -abs(r["difference_mm3"]))[:5]],
            "small_structures": [f"F-R{r['label']}" for r in m["regions"] if r["earlier_mm3"] < SMALL_MM3],
            "left_right": pairs[:5], "interval_months": months,
            "note": "Descriptive only. No normal range or cut-off is applied.",
        })
    fl = (run.get("review") or {}).get("flags") or []
    for i, f in enumerate(fl, 1):
        facts.append((f"F-flag{i}", "measured", f"Findings review flag: {f}"))
    out = [{"id": i, "kind": k, "text": t} for i, k, t in facts]
    return {"version": VERSION, "run_id": run.get("run_id"), "facts": out, "profile": profile, "complete": bool(m and al and iv)}


def as_facts(ledger: dict) -> list[V.Fact]:
    """The ledger in the form validator.check expects."""
    return [V.Fact.of(f["id"], f["text"]) for f in ledger["facts"]]
