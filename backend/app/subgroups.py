"""Subgroup analysis: does a rule or measure behave the same for different groups of people?

Used by eval/run_subgroup_analysis.py on the benchmarks (simulated people, English and Arabic sentences) and ready for
pilot data (by language, education, first language, device, age band). It reports a rate per group with a 95% Wilson
interval and the largest gap between groups with a 95% Newcombe interval. Groups smaller than `min_n` are reported as
"too few to say" and are left out of the gap, so a small group never produces a headline difference.

It describes; it does not adjust anything. A gap whose interval excludes 0 is a reason to look (and to collect more
data), not proof of unfairness, and no gap is not proof of fairness when groups are small.
"""
from __future__ import annotations

import math
from collections.abc import Callable, Iterable
from dataclasses import dataclass

Z95 = 1.959963984540054
MIN_N = 20


def wilson(k: int, n: int, z: float = Z95) -> tuple[float, float]:
    if n == 0:
        return (math.nan, math.nan)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def newcombe(k1: int, n1: int, k2: int, n2: int) -> tuple[float, float, float]:
    """Difference p1 − p2 with Newcombe's hybrid score interval (method 10)."""
    p1, p2 = k1 / n1, k2 / n2
    l1, u1 = wilson(k1, n1)
    l2, u2 = wilson(k2, n2)
    d = p1 - p2
    lo = d - math.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2)
    hi = d + math.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2)
    return d, lo, hi


@dataclass
class Group:
    name: str
    n: int
    k: int

    @property
    def rate(self) -> float:
        return self.k / self.n if self.n else math.nan

    @property
    def ci(self) -> tuple[float, float]:
        return wilson(self.k, self.n)


@dataclass
class SubgroupResult:
    outcome: str
    by: str
    groups: list[Group]
    small: list[Group]                       # fewer than min_n: shown, never compared
    gap: tuple[str, str, float, float, float] | None   # (higher group, lower group, difference, lo, hi)

    @property
    def gap_clear(self) -> bool:
        """True when the largest gap's interval excludes 0."""
        return bool(self.gap and (self.gap[3] > 0 or self.gap[4] < 0))

    def as_dict(self) -> dict:
        g = lambda x: {"name": x.name, "n": x.n, "k": x.k, "rate": round(x.rate, 4), "ci": [round(c, 4) for c in x.ci]}  # noqa: E731
        return {"outcome": self.outcome, "by": self.by, "groups": [g(x) for x in self.groups], "too_few": [g(x) for x in self.small],
                "gap": None if not self.gap else {"higher": self.gap[0], "lower": self.gap[1], "difference": round(self.gap[2], 4),
                                                  "ci": [round(self.gap[3], 4), round(self.gap[4], 4)], "clear": self.gap_clear}}


def by_group(rows: Iterable, group: Callable[[object], str | None], hit: Callable[[object], bool], outcome: str, by: str,
             min_n: int = MIN_N) -> SubgroupResult:
    """`group(row)` names the row's group (None: not known, left out); `hit(row)` is the outcome being counted."""
    tally: dict[str, list[int]] = {}
    for r in rows:
        g = group(r)
        if g is None:
            g = "not recorded"
        t = tally.setdefault(g, [0, 0])
        t[0] += 1
        t[1] += 1 if hit(r) else 0
    all_groups = [Group(name, n, k) for name, (n, k) in sorted(tally.items())]
    big = [x for x in all_groups if x.n >= min_n and x.name != "not recorded"]
    small = [x for x in all_groups if x not in big]
    gap = None
    if len(big) >= 2:
        hi, lo = max(big, key=lambda x: x.rate), min(big, key=lambda x: x.rate)
        d, a, b = newcombe(hi.k, hi.n, lo.k, lo.n)
        gap = (hi.name, lo.name, d, a, b)
    return SubgroupResult(outcome, by, big, small, gap)


def quality_by(db, attribute: str, min_n: int = MIN_N, exclude_synthetic: bool = False) -> SubgroupResult:
    """Share of activity records rated doubtful or unusable, by a person attribute: "education", "first_language"
    (from the person's own answers), "language" (of the session) or "device". For pilot data; the demo has two people."""
    from sqlalchemy import select
    from .models import ActivitySession, Evidence, PatientPreference
    prefs = {p.user_id: p for p in db.scalars(select(PatientPreference))}
    sessions = {s.id: s for s in db.scalars(select(ActivitySession))}
    rows = [e for e in db.scalars(select(Evidence).where(Evidence.kind == "observed", Evidence.status == "current"))
            if not (exclude_synthetic and (e.producer_id or "").startswith("synthetic-history"))]

    def group(e):
        if attribute in ("education", "first_language"):
            p = prefs.get(e.participant_id)
            return getattr(p, attribute, None) if p else None
        s = sessions.get(e.session_id)
        return getattr(s, attribute, None) if s else None
    return by_group(rows, group, lambda e: e.quality in ("doubtful", "unusable"), "doubtful or unusable record", attribute, min_n)
