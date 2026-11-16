# Change-engine benchmark (simulated people)

Run on 2026-11-16 by `backend/eval/run_change_benchmark.py`, seed 20261116, 2000 simulated people per
scenario, 8 weekly reaction-activity sessions each. The engine under test is `backend/app/change.py`
(change-engine/0.1: earliest 3 usable records against the latest 2, t-based
95% interval from the person's own variation), unchanged.

## What this measures, and what it does not

Because the people are simulated, the truth is known: who really slowed, by how much, and who had a practice gain.
That lets us count how often the engine says "outside usual variation" when it should and when it should not.

- Each person has their own usual speed (380–520 ms) and day-to-day spread (SD 15–40 ms), with normally distributed
  noise. Real reaction times are skewed, have outliers and depend on device and setting, so real performance will
  differ. **These are not clinical sensitivity or specificity figures** and say nothing about dementia or any condition.
- "Slowing of k SD" means the person's last 2 sessions are k times their own day-to-day spread slower.
- Brackets are 95% Wilson confidence intervals.

## Results

| Scenario | Correct behaviour | Correct | Flagged slower | Flagged faster | Abstained |
|---|---|---|---|---|---|
| Stable, no practice effect | stay within | **95.9% (94.9–96.7)** | 2.0% (1.5–2.7) | 2.1% (1.6–2.8) | 0.0% (0.0–0.2) |
| Stable, with practice gain (40 ms) | stay within | **91.8% (90.6–93.0)** | 0.5% (0.2–0.9) | 7.7% (6.6–9.0) | 0.0% (0.0–0.2) |
| Slowing of 1 SD | flag slower | **11.1% (9.7–12.5)** | 11.1% (9.7–12.5) | 0.1% (0.0–0.3) | 0.0% (0.0–0.2) |
| Slowing of 2 SD | flag slower | **32.1% (30.1–34.2)** | 32.1% (30.1–34.2) | 0.0% (0.0–0.2) | 0.0% (0.0–0.2) |
| Slowing of 3 SD | flag slower | **59.1% (57.0–61.3)** | 59.1% (57.0–61.3) | 0.0% (0.0–0.2) | 0.0% (0.0–0.2) |
| Slowing of 4 SD | flag slower | **81.1% (79.3–82.8)** | 81.1% (79.3–82.8) | 0.0% (0.0–0.2) | 0.0% (0.0–0.2) |
| Slowing of 3 SD, with practice gain (40 ms) | flag slower | **31.0% (29.0–33.1)** | 31.0% (29.0–33.1) | 0.0% (0.0–0.2) | 0.0% (0.0–0.2) |
| Only 4 usable sessions | abstain | **100.0% (99.8–100.0)** | 0.0% (0.0–0.2) | 0.0% (0.0–0.2) | 100.0% (99.8–100.0) |

## What this tells a clinician

- **False alarms on stable people: 4.1% (3.3–5.1)**, in line with
  the designed 95% interval. A flag is a reason to look, not a finding.
- **The engine is deliberately cautious.** With only 3 baseline and 2 recent records, a slowing has to be large
  (about 3–4 times the person's own day-to-day spread) before it is reliably flagged. Smaller real changes will often
  read "within usual variation", so that label is **not** reassurance that nothing changed.
- **Practice effect matters.** A 40 ms learning gain makes stable people look faster
  (7.7% (6.6–9.0) flagged faster) and hides part of a real slowing (compare the two 3 SD rows).
  The engine does not yet adjust for practice; until it does, early sessions should be treated as familiarisation
  and the clinician should read early "faster" flags with caution.
- With too few usable sessions the engine abstains instead of guessing.

## Next steps

Replace the simulation with real repeated measurements (test–retest study), estimate practice and device effects,
consider a reliable-change method with published reliability once activities are chosen, and have a statistician
and clinician set the window sizes and interval (see docs/STATUS.md, "Awaiting qualified approval").
