# Test–retest reliability study (code check on simulated people, and protocol)

Run on 2026-11-16 by `backend/eval/run_reliability_study.py`, seed 20261116, 400 simulated studies per row.
Analysis code: `backend/app/reliability.py` (standard library only). Checked against the published example of Shrout &
Fleiss (1979): ICC(2,1) 0.29 (95% CI 0.02–0.76) and ICC(3,1) 0.71 (0.34–0.95), reproduced exactly (`tests/test_reliability.py`).

## Why this matters

The change engine shows a reliable change index beside each estimate. It needs the activity's measurement error
(SEM). Today that comes from an **assumed** reliability (SD 70 ms, r = 0.8: SEM 31.3 ms, minimal
detectable change 87 ms between two single sessions), shown as provisional on screen. A
test–retest study replaces the assumption with a measured figure and its confidence interval.

## What the code computes

- **ICC(2,1)**, two-way random effects, absolute agreement: a retest must give the same value, so a practice effect
  counts as error. This is the figure to use for SEM.
- **ICC(3,1)**, consistency: ignores a shift shared by everyone. The gap between the two shows a practice effect.
- **SEM** = SD × √(1 − ICC(2,1)); **MDC95** = 1.96 × √2 × SEM; Bland–Altman bias and 95% limits of agreement.
- 95% confidence intervals: F-based for ICC(3,1), McGraw & Wong (1996) for ICC(2,1).
- From a database: `reliability.retest_pairs()` takes each person's first two usable sessions **after the practice
  sessions**, 1 to 14 days apart, and leaves out the synthetic demonstration history.

## Simulation check (truth: ICC 0.80, SEM 25 ms, practice gain 40 ms)

| Study | Mean ICC(2,1) | 95% CI contains truth | Mean CI width | Mean ICC(3,1) | Mean bias (retest − test, ms) | Mean SEM (ms) | Mean MDC95 (ms) |
|---|---|---|---|---|---|---|---|
| 40 people, sessions 3 and 4 (practice set aside) | 0.79 | 94% | 0.25 | 0.80 | -5.3 | 24.9 | 69 |
| 40 people, sessions 1 and 2 (practice included) | 0.75 | 96% | 0.40 | 0.79 | -19.6 | 27.8 | 77 |
| 15 people, sessions 3 and 4 | 0.76 | 96% | 0.47 | 0.77 | -5.7 | 24.7 | 69 |
| 100 people, sessions 3 and 4 | 0.79 | 95% | 0.15 | 0.80 | -5.2 | 25.2 | 70 |

What this shows:
- With practice sessions set aside, the code recovers the true reliability (ICC 0.79, SEM 25 ms)
  and its intervals contain the truth about 95% of the time, as they should. A little learning is left after two
  practice sessions (retest -5 ms on average).
- **If the first two sessions are used, the retest is faster for everyone** (-20 ms): absolute agreement
  falls to 0.75, SEM rises to 28 ms and the minimal detectable change to 77 ms, and the interval is
  wider. The study must set aside the same practice sessions as the change engine.
- 15 people give an interval 0.47 wide, too wide to be useful; around 40 people give 0.25.

## Protocol for the pilot study (to be approved before use)

- **Who**: adults of the intended age, both languages, with their own device; target **39 people** (enough to show
  ICC above 0.6 when it is 0.8, one-sided 5%, 80% power; 117 people to show it above 0.7). Walter, Eliasziw &
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
