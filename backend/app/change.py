"""Change engine: is a person's recent result different from their own earlier results?

Deterministic, no model. For one person, one measure and one activity version:

1. Practice: for an observed activity (a task the person performs), the first PRACTICE_N sessions of that activity
   version are familiarisation. People get faster or better at a new task while they learn it, so these sessions are
   never compared, whatever their quality. Self-reports (sleep, mood) have no practice period.
   Eligible records are the remaining ones that are current (not corrected or withdrawn), have a value, and are
   usable. Doubtful records are left out unless the caller asks for them; unusable ones never count.
2. Baseline = the earliest BASELINE_N eligible records. Recent = the latest RECENT_N, which never overlap the
   baseline. With fewer than BASELINE_N + RECENT_N eligible records the engine abstains.
3. Difference = mean(recent) - mean(baseline). Its uncertainty comes from this person's own variation: the pooled
   standard deviation within the two windows, a t-based 95% interval on the difference.
4. The interval either includes zero ("within usual variation") or does not ("outside usual variation", with the
   direction). If the person's values do not vary at all, the variation cannot be estimated and the engine abstains.

5. Two further readings of the same difference, for the clinician beside the interval (they never change the status):
   - z: the difference in units of the person's own day-to-day spread (pooled SD). Descriptive only.
   - Reliable change index (Jacobson & Truax, 1991): the difference divided by the standard error of a difference built
     from a test-retest reliability figure for the measure, adapted to window means: SEM = SD_ref * sqrt(1 - r),
     S_diff = SEM * sqrt(1/n_baseline + 1/n_recent). |RCI| > 1.96 reads "larger than measurement error alone".
     Only measures with a reliability entry in RELIABILITY get one; every entry names its source. The current entry is a
     PROVISIONAL assumption, not a figure measured for this activity; the planned test-retest study replaces it.

What this is not: a diagnosis, a clinical threshold, a population comparison, or a prediction. Window sizes and the
interval level are engineering defaults for the prototype and await review by a statistician and a clinician
(docs/STATUS.md). The result is a research estimate for a clinician to read beside the records it names.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime

from .models import Evidence

METHOD = "change-engine/0.2"
BASELINE_N = 3
RECENT_N = 2
LEVEL = 0.95
PRACTICE_N = 2          # familiarisation sessions per observed activity version, never compared
RCI_CRITICAL = 1.96


@dataclass(frozen=True)
class Reliability:
    sd_ref: float      # between-person SD of the measure in the reference group
    r: float           # test-retest reliability (ICC or Pearson r)
    source: str        # where the two figures come from
    provisional: bool  # True while the figures are assumptions rather than measured for this activity


# Keyed by (activity, measure). Applies to every version of the activity until a measured figure says otherwise.
RELIABILITY: dict[tuple[str, str], Reliability] = {
    ("reaction_time", "rt_median_ms"): Reliability(
        sd_ref=70.0, r=0.80, provisional=True,
        source="Provisional assumption: typical spread and test-retest reliability reported for simple reaction time in "
               "older adults. Not measured for this activity; replaced by the planned test-retest study."),
}

# Two-sided 95% critical values of Student's t, by degrees of freedom.
_T95 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228,
        11: 2.201, 12: 2.179, 13: 2.160, 14: 2.145, 15: 2.131, 16: 2.120, 17: 2.110, 18: 2.101, 19: 2.093,
        20: 2.086, 25: 2.060, 30: 2.042, 40: 2.021, 60: 2.000, 120: 1.980}


def t95(df: int) -> float:
    if df in _T95:
        return _T95[df]
    larger = [k for k in _T95 if k > df]
    return _T95[min(larger)] if larger else 1.960   # next table row up: slightly wider, never narrower


@dataclass
class Window:
    ids: list[int]
    values: list[float]
    first: datetime
    last: datetime

    @property
    def n(self) -> int:
        return len(self.values)

    @property
    def mean(self) -> float:
        return sum(self.values) / len(self.values)

    def sum_sq(self) -> float:
        m = self.mean
        return sum((v - m) ** 2 for v in self.values)

    def as_dict(self) -> dict:
        return {"n": self.n, "mean": round(self.mean, 3), "ids": self.ids, "from": self.first, "to": self.last}


@dataclass
class ChangeResult:
    protocol_code: str | None
    protocol_version: str | None
    measure: str
    kind: str
    unit: str | None
    status: str                      # insufficient | no_variation | within | outside
    eligible_n: int
    excluded: dict = field(default_factory=dict)
    include_doubtful: bool = False
    baseline: Window | None = None
    recent: Window | None = None
    difference: float | None = None
    interval: tuple[float, float] | None = None
    direction: str | None = None     # higher | lower, only when outside
    practice_ids: list[int] = field(default_factory=list)
    z: float | None = None
    rci: dict | None = None

    def as_dict(self) -> dict:
        return {
            "method": METHOD, "level": LEVEL, "protocol_code": self.protocol_code,
            "protocol_version": self.protocol_version, "measure": self.measure, "kind": self.kind, "unit": self.unit,
            "status": self.status, "direction": self.direction, "eligible_n": self.eligible_n,
            "needed": {"baseline": BASELINE_N, "recent": RECENT_N, "practice": PRACTICE_N if self.kind == "observed" else 0},
            "include_doubtful": self.include_doubtful, "excluded": self.excluded, "practice_ids": self.practice_ids,
            "baseline": self.baseline.as_dict() if self.baseline else None,
            "recent": self.recent.as_dict() if self.recent else None,
            "difference": None if self.difference is None else round(self.difference, 3),
            "interval": None if self.interval is None else [round(self.interval[0], 3), round(self.interval[1], 3)],
            "z": None if self.z is None else round(self.z, 2),
            "rci": self.rci,
        }


def practice_count(kind: str, practice: int | None = None) -> int:
    return (PRACTICE_N if practice is None else practice) if kind == "observed" else 0


def compare(records: list[Evidence], include_doubtful: bool = False, practice: int | None = None) -> ChangeResult:
    """`records` must all share one participant, measure and activity version (the caller groups them).
    `practice` overrides PRACTICE_N (tests and the benchmark use it to compare with and without)."""
    first = records[0]
    allowed = {"usable", "doubtful"} if include_doubtful else {"usable"}
    excluded = {"practice": 0, "doubtful": 0, "unusable": 0, "withdrawn": 0, "missing": 0}
    # Practice is counted in sessions the person did, whatever came of them: learning happens either way. An older corrected
    # version is not a separate session, so it is skipped.
    done = sorted((e for e in records if e.status in ("current", "withdrawn")), key=lambda e: (e.recorded_at, e.id))
    practice_ids = [e.id for e in done[:practice_count(first.kind, practice)]]
    eligible: list[Evidence] = []
    for e in records:
        if e.id in practice_ids:
            excluded["practice"] += 1
        elif e.status == "withdrawn":
            excluded["withdrawn"] += 1
        elif e.status != "current":
            continue                                   # an older corrected version: its replacement counts instead
        elif e.value_num is None:
            excluded["missing"] += 1
        elif e.quality not in allowed:
            excluded[e.quality] += 1
        else:
            eligible.append(e)
    eligible.sort(key=lambda e: (e.recorded_at, e.id))

    result = ChangeResult(first.protocol_code, first.protocol_version, first.measure, first.kind, first.unit,
                          status="insufficient", eligible_n=len(eligible), excluded=excluded,
                          include_doubtful=include_doubtful, practice_ids=practice_ids)
    if len(eligible) < BASELINE_N + RECENT_N:
        return result

    def window(rows: list[Evidence]) -> Window:
        return Window([e.id for e in rows], [float(e.value_num) for e in rows], rows[0].recorded_at, rows[-1].recorded_at)

    base, rec = window(eligible[:BASELINE_N]), window(eligible[-RECENT_N:])
    result.baseline, result.recent = base, rec
    result.difference = rec.mean - base.mean
    df = base.n + rec.n - 2
    pooled_sd = math.sqrt((base.sum_sq() + rec.sum_sq()) / df)
    if pooled_sd == 0:
        result.status = "no_variation"
        return result
    result.z = result.difference / pooled_sd
    ref = RELIABILITY.get((first.protocol_code, first.measure))
    if ref is not None:
        sem = ref.sd_ref * math.sqrt(1 - ref.r)
        s_diff = sem * math.sqrt(1 / base.n + 1 / rec.n)
        value = result.difference / s_diff
        result.rci = {"value": round(value, 2), "critical": RCI_CRITICAL, "reliable": abs(value) > RCI_CRITICAL,
                      "sem": round(sem, 2), "s_diff": round(s_diff, 2), "sd_ref": ref.sd_ref, "r": ref.r,
                      "provisional": ref.provisional, "source": ref.source}
    half = t95(df) * pooled_sd * math.sqrt(1 / base.n + 1 / rec.n)
    lo, hi = result.difference - half, result.difference + half
    result.interval = (lo, hi)
    if lo > 0 or hi < 0:
        result.status, result.direction = "outside", ("higher" if result.difference > 0 else "lower")
    else:
        result.status = "within"
    return result


# A published instrument is shown as recorded. No "within usual variation" or "outside" label is computed for it: that would be
# an interpretation nobody has validated for this implementation.
NO_CHANGE_LABEL = {"who5"}


def compare_all(records: list[Evidence], include_doubtful: bool = False) -> list[ChangeResult]:
    """Group by activity, version and measure; numeric observed and self-reported measures only. Records of
    different versions are never pooled."""
    groups: dict[tuple, list[Evidence]] = {}
    for e in records:
        if e.kind == "inferred" or e.unit in (None, "count") or e.protocol_code is None:
            continue
        if e.protocol_code in NO_CHANGE_LABEL:
            continue
        groups.setdefault((e.protocol_code, e.protocol_version, e.measure), []).append(e)
    return [compare(rows, include_doubtful) for _, rows in sorted(groups.items(), key=lambda kv: kv[0])]
