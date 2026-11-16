"""Change-engine benchmark on simulated people (no real data, no model).
Usage, from backend/:  python eval/run_change_benchmark.py [--write]   (--write updates docs/CHANGE_ENGINE_BENCHMARK.md)

Each simulated person does 8 sessions of the reaction activity. Their usual speed and day-to-day spread are drawn at
random; some get a true slowing in their last 2 sessions, some a practice gain over the first sessions. We know the
truth, so we can count how often the engine (app/change.py, unchanged) says "outside usual variation" when it should
and should not. This measures the engine's statistical behaviour under stated assumptions; it is NOT clinical
sensitivity or specificity, and real reaction times are skewed and messier than this simulation."""
import math
import random
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from app import change  # noqa: E402

DOC = HERE.parent.parent / "docs" / "CHANGE_ENGINE_BENCHMARK.md"
SEED, N_PEOPLE, SESSIONS = 20261116, 2000, 8
T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def person(rng: random.Random, shift_sd: float, practice_ms: float, usable: int = SESSIONS):
    """Reaction time in ms. shift_sd: true slowing in the last 2 sessions, in this person's own SDs.
    practice_ms: total speed-up from learning, mostly over the first sessions (exponential)."""
    mu, sd = rng.uniform(380, 520), rng.uniform(15, 40)
    rows = []
    for i in range(SESSIONS):
        v = mu + rng.gauss(0, sd) - practice_ms * (1 - math.exp(-i / 1.5))
        if i >= SESSIONS - 2:
            v += shift_sd * sd
        rows.append(SimpleNamespace(id=i + 1, status="current", value_num=round(v, 1),
                                    quality="usable" if i < usable else "unusable", recorded_at=T0 + timedelta(days=7 * i),
                                    protocol_code="reaction_time", protocol_version="0.1", measure="median_rt_ms",
                                    kind="observed", unit="ms"))
    return rows


SCENARIOS = [
    # (label, true slowing in SDs, practice gain ms, usable sessions, what should happen)
    ("Stable, no practice effect", 0, 0, 8, "stay within"),
    ("Stable, with practice gain (40 ms)", 0, 40, 8, "stay within"),
    ("Slowing of 1 SD", 1, 0, 8, "flag slower"),
    ("Slowing of 2 SD", 2, 0, 8, "flag slower"),
    ("Slowing of 3 SD", 3, 0, 8, "flag slower"),
    ("Slowing of 4 SD", 4, 0, 8, "flag slower"),
    ("Slowing of 3 SD, with practice gain (40 ms)", 3, 40, 8, "flag slower"),
    ("Only 4 usable sessions", 3, 0, 4, "abstain"),
]


def run() -> list[dict]:
    rng = random.Random(SEED)
    out = []
    for label, shift, practice, usable, want in SCENARIOS:
        tally = {"within": 0, "outside_higher": 0, "outside_lower": 0, "abstain": 0}
        for _ in range(N_PEOPLE):
            r = change.compare(person(rng, shift, practice, usable))
            key = "abstain" if r.status in ("insufficient", "no_variation") else (
                "within" if r.status == "within" else f"outside_{r.direction}")
            tally[key] += 1
        hit = {"stay within": tally["within"], "flag slower": tally["outside_higher"], "abstain": tally["abstain"]}[want]
        out.append({"label": label, "want": want, "hit": hit, "tally": tally})
    return out


def pct(k, n=N_PEOPLE):
    lo, hi = wilson(k, n)
    return f"{100 * k / n:.1f}% ({100 * lo:.1f}–{100 * hi:.1f})"


def report(rows: list[dict]) -> str:
    table = "\n".join(
        f"| {r['label']} | {r['want']} | **{pct(r['hit'])}** | {pct(r['tally']['outside_higher'])} | {pct(r['tally']['outside_lower'])} | {pct(r['tally']['abstain'])} |"
        for r in rows)
    stable, practice = rows[0], rows[1]
    return f"""# Change-engine benchmark (simulated people)

Run on {date.today().isoformat()} by `backend/eval/run_change_benchmark.py`, seed {SEED}, {N_PEOPLE} simulated people per
scenario, {SESSIONS} weekly reaction-activity sessions each. The engine under test is `backend/app/change.py`
({change.METHOD}: earliest {change.BASELINE_N} usable records against the latest {change.RECENT_N}, t-based
{int(change.LEVEL * 100)}% interval from the person's own variation), unchanged.

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
{table}

## What this tells a clinician

- **False alarms on stable people: {pct(stable['tally']['outside_higher'] + stable['tally']['outside_lower'])}**, in line with
  the designed 95% interval. A flag is a reason to look, not a finding.
- **The engine is deliberately cautious.** With only 3 baseline and 2 recent records, a slowing has to be large
  (about 3–4 times the person's own day-to-day spread) before it is reliably flagged. Smaller real changes will often
  read "within usual variation", so that label is **not** reassurance that nothing changed.
- **Practice effect matters.** A 40 ms learning gain makes stable people look faster
  ({pct(practice['tally']['outside_lower'])} flagged faster) and hides part of a real slowing (compare the two 3 SD rows).
  The engine does not yet adjust for practice; until it does, early sessions should be treated as familiarisation
  and the clinician should read early "faster" flags with caution.
- With too few usable sessions the engine abstains instead of guessing.

## Next steps

Replace the simulation with real repeated measurements (test–retest study), estimate practice and device effects,
consider a reliable-change method with published reliability once activities are chosen, and have a statistician
and clinician set the window sizes and interval (see docs/STATUS.md, "Awaiting qualified approval").
"""


def main() -> int:
    text = report(run())
    if "--write" in sys.argv:
        DOC.write_text(text, encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
