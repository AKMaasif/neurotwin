"""Test–retest reliability: check the analysis code on simulated people, and run it on pilot data when there is some.
Usage, from backend/:
  python eval/run_reliability_study.py [--write]          simulation check (--write updates docs/RELIABILITY_STUDY.md)
  python eval/run_reliability_study.py --db path.db        real test–retest pairs from a database (synthetic demo history left out)

The simulation knows the true reliability (between-person SD 50 ms, within-person SD 25 ms: true ICC 0.80, true SEM
25 ms), so we can see whether app/reliability.py recovers it, how often its 95% intervals contain the truth, and how a
practice effect distorts a test–retest study that does not set practice sessions aside. It is a check of the code and
the study design, NOT a measurement of this activity's reliability: that needs real people (protocol below)."""
import json
import math
import random
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from app import change, reliability as R  # noqa: E402

DOC = HERE.parent.parent / "docs" / "RELIABILITY_STUDY.md"
SEED, REPS = 20261116, 400
MU, SD_B, SD_W, PRACTICE_MS = 450.0, 50.0, 25.0, 40.0
TRUE_ICC = SD_B ** 2 / (SD_B ** 2 + SD_W ** 2)


def people(rng: random.Random, n: int, sessions: tuple[int, int], practice_ms: float) -> list[list[float]]:
    """Each person: a usual speed, then sessions with independent day-to-day noise and an exponential learning curve."""
    out = []
    for _ in range(n):
        mu = rng.gauss(MU, SD_B)
        out.append([mu + rng.gauss(0, SD_W) - practice_ms * (1 - math.exp(-i / 1.5)) for i in sessions])
    return out


def scenario(label: str, n: int, sessions: tuple[int, int], practice_ms: float) -> dict:
    rng = random.Random(f"{SEED}-{label}")
    a, c, sem, mdc, cov_a, cov_c, width, bias = [], [], [], [], 0, 0, [], []
    for _ in range(REPS):
        r = R.icc(people(rng, n, sessions, practice_ms))
        a.append(r.icc_a); c.append(r.icc_c); sem.append(r.sem); mdc.append(r.mdc95); bias.append(r.bias)
        cov_a += r.icc_a_ci[0] <= TRUE_ICC <= r.icc_a_ci[1]
        cov_c += r.icc_c_ci[0] <= TRUE_ICC <= r.icc_c_ci[1]
        width.append(r.icc_a_ci[1] - r.icc_a_ci[0])
    m = lambda xs: sum(xs) / len(xs)  # noqa: E731
    return {"label": label, "n": n, "sessions": sessions, "icc_a": m(a), "icc_c": m(c), "cover_a": cov_a / REPS, "cover_c": cov_c / REPS,
            "width": m(width), "sem": m(sem), "mdc": m(mdc), "bias": m(bias)}


SCENARIOS = [
    ("40 people, sessions 3 and 4 (practice set aside)", 40, (2, 3), PRACTICE_MS),
    ("40 people, sessions 1 and 2 (practice included)", 40, (0, 1), PRACTICE_MS),
    ("15 people, sessions 3 and 4", 15, (2, 3), PRACTICE_MS),
    ("100 people, sessions 3 and 4", 100, (2, 3), PRACTICE_MS),
]


def report(rows: list[dict]) -> str:
    table = "\n".join(
        f"| {r['label']} | {r['icc_a']:.2f} | {100 * r['cover_a']:.0f}% | {r['width']:.2f} | {r['icc_c']:.2f} | {r['bias']:+.1f} | {r['sem']:.1f} | {r['mdc']:.0f} |"
        for r in rows)
    ref = change.RELIABILITY[("reaction_time", "rt_median_ms")]
    p_sem = ref.sd_ref * math.sqrt(1 - ref.r)
    n_needed = R.sample_size(0.8, 0.6)
    n_needed_7 = R.sample_size(0.8, 0.7)
    return f"""# Test–retest reliability study (code check on simulated people, and protocol)

Run on {date.today().isoformat()} by `backend/eval/run_reliability_study.py`, seed {SEED}, {REPS} simulated studies per row.
Analysis code: `backend/app/reliability.py` (standard library only). Checked against the published example of Shrout &
Fleiss (1979): ICC(2,1) 0.29 (95% CI 0.02–0.76) and ICC(3,1) 0.71 (0.34–0.95), reproduced exactly (`tests/test_reliability.py`).

## Why this matters

The change engine shows a reliable change index beside each estimate. It needs the activity's measurement error
(SEM). Today that comes from an **assumed** reliability (SD {ref.sd_ref:g} ms, r = {ref.r:g}: SEM {p_sem:.1f} ms, minimal
detectable change {R.Z95 * math.sqrt(2) * p_sem:.0f} ms between two single sessions), shown as provisional on screen. A
test–retest study replaces the assumption with a measured figure and its confidence interval.

## What the code computes

- **ICC(2,1)**, two-way random effects, absolute agreement: a retest must give the same value, so a practice effect
  counts as error. This is the figure to use for SEM.
- **ICC(3,1)**, consistency: ignores a shift shared by everyone. The gap between the two shows a practice effect.
- **SEM** = SD × √(1 − ICC(2,1)); **MDC95** = 1.96 × √2 × SEM; Bland–Altman bias and 95% limits of agreement.
- 95% confidence intervals: F-based for ICC(3,1), McGraw & Wong (1996) for ICC(2,1).
- From a database: `reliability.retest_pairs()` takes each person's first two usable sessions **after the practice
  sessions**, 1 to 14 days apart, and leaves out the synthetic demonstration history.

## Simulation check (truth: ICC {TRUE_ICC:.2f}, SEM {SD_W:g} ms, practice gain {PRACTICE_MS:g} ms)

| Study | Mean ICC(2,1) | 95% CI contains truth | Mean CI width | Mean ICC(3,1) | Mean bias (retest − test, ms) | Mean SEM (ms) | Mean MDC95 (ms) |
|---|---|---|---|---|---|---|---|
{table}

What this shows:
- With practice sessions set aside, the code recovers the true reliability (ICC {rows[0]['icc_a']:.2f}, SEM {rows[0]['sem']:.0f} ms)
  and its intervals contain the truth about 95% of the time, as they should. A little learning is left after two
  practice sessions (retest {rows[0]['bias']:+.0f} ms on average).
- **If the first two sessions are used, the retest is faster for everyone** ({rows[1]['bias']:+.0f} ms): absolute agreement
  falls to {rows[1]['icc_a']:.2f}, SEM rises to {rows[1]['sem']:.0f} ms and the minimal detectable change to {rows[1]['mdc']:.0f} ms, and the interval is
  wider. The study must set aside the same practice sessions as the change engine.
- 15 people give an interval {rows[2]['width']:.2f} wide, too wide to be useful; around 40 people give {rows[0]['width']:.2f}.

## Protocol for the pilot study (to be approved before use)

- **Who**: adults of the intended age, both languages, with their own device; target **{n_needed} people** (enough to show
  ICC above 0.6 when it is 0.8, one-sided 5%, 80% power; {n_needed_7} people to show it above 0.7). Walter, Eliasziw &
  Donner (1998).
- **What**: two practice sessions, then a test and a retest **1–14 days apart**, same device, similar time of day,
  today's-conditions questions answered. Only usable records count.
- **Report**: ICC(2,1) and ICC(3,1) with 95% CI, SEM, MDC95, Bland–Altman plot, and the same by language and device
  (`eval/run_subgroup_analysis.py`). Interpretation (Koo & Li 2016): below 0.5 poor, 0.5–0.75 moderate, 0.75–0.9 good,
  above 0.9 excellent, judged on the lower confidence limit.
- **Then**: a statistician and a clinician decide whether to replace the provisional figure in `change.RELIABILITY`
  (and remove the "provisional" mark). Nothing changes automatically.

Run on pilot data: `python eval/run_reliability_study.py --db path/to/pilot.db`.

## Current data

The demonstration database has two people and a synthetic history, so it **cannot** give a reliability figure. No
reliability has been measured for this activity yet.
"""


def from_db(path: str) -> int:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    with Session(create_engine(f"sqlite:///{path}")) as db:
        pairs = R.retest_pairs(db)
    print(f"{len(pairs)} test–retest pairs (practice set aside, 1–14 days apart, synthetic history left out)")
    if len(pairs) < 3:
        print("Too few people for a reliability figure.")
        return 0
    r = R.icc([[p["test"], p["retest"]] for p in pairs])
    print(json.dumps(r.as_dict(), indent=1))
    return 0


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    if "--db" in sys.argv:
        return from_db(sys.argv[sys.argv.index("--db") + 1])
    text = report([scenario(*s) for s in SCENARIOS])
    if "--write" in sys.argv:
        DOC.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
