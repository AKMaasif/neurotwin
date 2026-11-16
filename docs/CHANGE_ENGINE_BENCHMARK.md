# Change-engine benchmark (simulated people)

Run on 2026-11-16 by `backend/eval/run_change_benchmark.py`, seed 20261116, 2000 simulated people per
scenario, 8 weekly reaction-activity sessions each. The engine under test is `backend/app/change.py`
(change-engine/0.2: the first 2 sessions are practice and never compared; then the earliest
3 usable records against the latest 2, t-based 95% interval from
the person's own variation), unchanged.

## What this measures, and what it does not

Because the people are simulated, the truth is known: who really slowed, by how much, and who had a practice gain.
That lets us count how often the engine says "outside usual variation" when it should and when it should not.

- Each person has their own usual speed (380–520 ms) and day-to-day spread (SD 15–40 ms), with normally distributed
  noise. Real reaction times are skewed, have outliers and depend on device and setting, so real performance will
  differ. **These are not clinical sensitivity or specificity figures** and say nothing about dementia or any condition.
- "Slowing of k SD" means the person's last 2 sessions are k times their own day-to-day spread slower.
- "Practice gain (40 ms)" means the person gets up to 40 ms faster while learning the task, most of it in the first
  sessions (an exponential learning curve).
- Brackets are 95% Wilson confidence intervals.

## Results (engine as shipped, with practice sessions)

| Scenario | Correct behaviour | Correct | Flagged slower | Flagged faster | Abstained |
|---|---|---|---|---|---|
| Stable, no practice effect | stay within | **95.2% (94.2–96.1)** | 2.5% (1.9–3.3) | 2.3% (1.7–3.1) | 0.0% (0.0–0.2) |
| Stable, with practice gain (40 ms) | stay within | **94.8% (93.7–95.7)** | 1.9% (1.4–2.6) | 3.3% (2.6–4.2) | 0.0% (0.0–0.2) |
| Slowing of 1 SD | flag slower | **11.7% (10.4–13.2)** | 11.7% (10.4–13.2) | 0.2% (0.1–0.5) | 0.0% (0.0–0.2) |
| Slowing of 2 SD | flag slower | **33.2% (31.2–35.3)** | 33.2% (31.2–35.3) | 0.0% (0.0–0.2) | 0.0% (0.0–0.2) |
| Slowing of 3 SD | flag slower | **60.8% (58.6–62.9)** | 60.8% (58.6–62.9) | 0.0% (0.0–0.2) | 0.0% (0.0–0.2) |
| Slowing of 4 SD | flag slower | **81.3% (79.5–82.9)** | 81.3% (79.5–82.9) | 0.0% (0.0–0.2) | 0.0% (0.0–0.2) |
| Slowing of 3 SD, with practice gain (40 ms) | flag slower | **54.1% (52.0–56.3)** | 54.1% (52.0–56.3) | 0.0% (0.0–0.2) | 0.0% (0.0–0.2) |
| Only 4 usable sessions | abstain | **100.0% (99.8–100.0)** | 0.0% (0.0–0.2) | 0.0% (0.0–0.2) | 100.0% (99.8–100.0) |

## Practice sessions: before and after

The same simulated people, with the engine run without practice sessions (change-engine/0.1 behaviour) and with
the first 2 sessions set aside (as shipped).

| Scenario | Flagged slower, no practice rule | Flagged slower, with practice rule | Flagged faster, no practice rule | Flagged faster, with practice rule |
|---|---|---|---|---|
| Stable, no practice effect | 2.0% (1.5–2.7) | 2.5% (1.9–3.3) | 2.1% (1.6–2.8) | 2.3% (1.7–3.1) |
| Stable, with practice gain (40 ms) | 0.5% (0.2–0.9) | 1.9% (1.4–2.6) | 7.7% (6.6–9.0) | 3.3% (2.6–4.2) |
| Slowing of 1 SD | 11.1% (9.7–12.5) | 11.7% (10.4–13.2) | 0.1% (0.0–0.3) | 0.2% (0.1–0.5) |
| Slowing of 2 SD | 32.1% (30.1–34.2) | 33.2% (31.2–35.3) | 0.0% (0.0–0.2) | 0.0% (0.0–0.2) |
| Slowing of 3 SD | 59.1% (57.0–61.3) | 60.8% (58.6–62.9) | 0.0% (0.0–0.2) | 0.0% (0.0–0.2) |
| Slowing of 4 SD | 81.1% (79.3–82.8) | 81.3% (79.5–82.9) | 0.0% (0.0–0.2) | 0.0% (0.0–0.2) |
| Slowing of 3 SD, with practice gain (40 ms) | 31.0% (29.0–33.1) | 54.1% (52.0–56.3) | 0.0% (0.0–0.2) | 0.0% (0.0–0.2) |

## Reliable change index (shown beside the interval, never changes the status)

RCI = difference / S_diff, with SEM = SD_ref × √(1 − r) = 70 × √(1 − 0.8) and
S_diff = SEM × √(1/3 + 1/2); |RCI| > 1.96 counts. **The reliability
figures are a provisional assumption, not measured for this activity**, so this table shows how the index behaves
when the assumed measurement error is close to the simulated one; it is not a validation of the index.

| Scenario | Interval: flagged slower | RCI: larger than error, slower | RCI: larger than error, faster |
|---|---|---|---|
| Stable, no practice effect | 2.5% (1.9–3.3) | 1.9% (1.3–2.5) | 1.9% (1.3–2.5) |
| Stable, with practice gain (40 ms) | 1.9% (1.4–2.6) | 1.6% (1.1–2.2) | 2.5% (1.9–3.3) |
| Slowing of 1 SD | 11.7% (10.4–13.2) | 13.2% (11.8–14.8) | 0.1% (0.0–0.4) |
| Slowing of 2 SD | 33.2% (31.2–35.3) | 45.9% (43.7–48.1) | 0.0% (0.0–0.2) |
| Slowing of 3 SD | 60.8% (58.6–62.9) | 77.0% (75.2–78.8) | 0.0% (0.0–0.2) |
| Slowing of 4 SD | 81.3% (79.5–82.9) | 94.3% (93.2–95.2) | 0.0% (0.0–0.2) |
| Slowing of 3 SD, with practice gain (40 ms) | 54.1% (52.0–56.3) | 69.4% (67.3–71.4) | 0.0% (0.0–0.2) |

## What this tells a clinician

- **False alarms on stable people: 4.8% (3.9–5.8)**, in line with
  the designed 95% interval. A flag is a reason to look, not a finding.
- **The engine is deliberately cautious.** With only 3 baseline and 2 recent records, a slowing has to be large
  (about 3–4 times the person's own day-to-day spread) before it is reliably flagged. Smaller real changes will often
  read "within usual variation", so that label is **not** reassurance that nothing changed.
- **Practice sessions remove most of the learning bias.** With a 40 ms learning gain, stable people flagged "faster"
  fall from 7.7% (6.6–9.0) to 3.3% (2.6–4.2); see the before-and-after
  table for a real 3 SD slowing combined with learning. The cost: an estimate now needs
  7 sessions instead of 5.
- **The RCI is a second reading.** It uses a fixed measurement error from an assumed reliability instead of estimating
  the error from five records, so it can disagree with the interval in either direction. It is marked provisional and
  never changes the status.
- With too few usable sessions the engine abstains instead of guessing.

## Next steps

Replace the simulation and the assumed reliability with real repeated measurements (test–retest study: ICC, SEM,
minimal detectable change), estimate device effects, and have a statistician and clinician set the window sizes,
practice period and interval (see docs/STATUS.md, "Awaiting qualified approval").
