import copy

from app import agent_ledger as L
from app import validator as V


def region(label, name, e, l, ev=None, lv=None):
    d = l - e
    return {"label": label, "name": name, "earlier_mm3": e, "later_mm3": l, "difference_mm3": d, "difference_pct": round(100 * d / e, 2) if e else None,
            "earlier_voxels": ev or int(e * 0.8), "later_voxels": lv or int(l * 0.8), "uncertainty": None, "status": "uncertain", "review_notes": []}


RUN = {"run_id": "r1", "validation": {"interval": {"months": 12.0, "days": 365, "nearest_target_months": 12, "within_requested_window": True}, "limitations": ["No repeat scan."]},
       "alignment": {"method": "rigid", "tool": "ANTsPy 0.6.3", "correlation_before": 0.32, "correlation_after": 0.84, "rotation_deg": 4.83, "shift_mm_voxel_frame": 6.11, "flags": [], "mask": "m"},
       "segmentation_tool": {"tool": "SynthSeg", "version": "1.0"},
       "measurements": {"unit": "mm3", "earlier_total_mm3": 100000.0, "later_total_mm3": 99000.0, "source": "s", "regions": [
           region(4, "left lateral ventricle", 2000, 2200), region(43, "right lateral ventricle", 2000, 2100),
           region(17, "left hippocampus", 1000, 950), region(53, "right hippocampus", 1000, 1000)]},
       "review": {"flags": ["Whole-brain total changed by 1%."], "note": "n"}}


def ids(led):
    return {f["id"] for f in led["facts"]}


def test_ledger_has_ids_kinds_and_is_complete():
    led = L.build(RUN)
    assert led["complete"] and len(ids(led)) == len(led["facts"])
    assert {"F-interval", "F-align", "F-seg", "F-total", "F-uncertainty", "F-R4", "F-rate4", "F-lr4", "F-vent", "F-limit1", "F-flag1"} <= ids(led)
    kinds = {f["id"]: f["kind"] for f in led["facts"]}
    assert kinds["F-R4"] == "measured" and kinds["F-rate4"] == "derived" and kinds["F-uncertainty"] == "stated"


def test_derived_values_are_correct():
    led = {f["id"]: f["text"] for f in L.build(RUN)["facts"]}
    assert "+10.0% per 12 months" in led["F-rate4"]          # 10 % over exactly 12 months
    assert "gap 5 percentage points" in led["F-lr4"]       # +10.0 vs +5.0
    assert "is 4% of the measured structures earlier and 4.3% later" in led["F-vent"]  # 4000/100000 and 4300/99000


def test_ventricle_share_is_computed_from_totals():
    p = L.build(RUN)["profile"]["ventricle_share_pct"]
    assert p == {"earlier": 4.0, "later": 4.34}


def test_rate_scales_with_interval():
    r = copy.deepcopy(RUN); r["validation"]["interval"]["months"] = 24.0
    led = {f["id"]: f["text"] for f in L.build(r)["facts"]}
    assert "+5.0% per 12 months" in led["F-rate4"]


def test_small_structures_and_ranking_are_descriptive_only():
    p = L.build(RUN)["profile"]
    assert "F-R17" in p["small_structures"] and p["largest_percent"][0]["name"] == "left lateral ventricle"
    assert "No normal range" in p["note"]
    blob = str(L.build(RUN)).lower()
    for word in ("abnormal", "alzheimer", "diagnos", "risk", "predict"):
        assert word not in blob.replace("not a diagnosis", "")


def test_missing_parts_give_no_facts_instead_of_defaults():
    r = copy.deepcopy(RUN); r["measurements"] = None; r["alignment"] = None
    led = L.build(r)
    assert not led["complete"] and led["profile"] == {"available": False}
    assert not any(i.startswith(("F-R", "F-total", "F-align", "F-vent")) for i in ids(led))


def test_unknown_interval_gives_no_rate():
    r = copy.deepcopy(RUN); r["validation"]["interval"] = None
    assert not any(i.startswith("F-rate") for i in ids(L.build(r)))


def test_validator_accepts_cited_numbers_and_rejects_invented_ones():
    facts = L.as_facts(L.build(RUN))
    ok = V.check([V.Statement("The left lateral ventricle volume was 2000 mm3 earlier and 2200 mm3 later.", ["F-R4"])], facts)
    bad = V.check([V.Statement("The left lateral ventricle grew by 37 mm3.", ["F-R4"])], facts)
    assert ok.ok, ok.problems
    assert not bad.ok and any(p.code == "unsupported_number" for p in bad.problems)
