"""Emergency-phrase benchmark for the assistant's fixed help rule (what opens the help screen from typed or transcribed words).
Usage, from backend/:  python eval/run_emergency_benchmark.py [--write]   (--write updates docs/EMERGENCY_BENCHMARK.md)

What this measures: whether a sentence opens the help screen. Sentences are developer-written, English and Arabic.
"dev" sentences were used to tune the rule; "held_out" sentences were written after tuning and never used to change it.
It does NOT measure speech recognition, real users' wording, or anything clinical. The app never calls anyone."""
import json
import math
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from app import assistant as A  # noqa: E402

SET = HERE / "emergency_set.jsonl"
HISTORY = "\n".join([
    "| 2026-11-16 | round 1 | 17/20 = 85% (95% CI 64–95%) | 13/15 = 87% (95% CI 62–96%) | \"please help\", \"I think I'm having a heart attack\", \"النجدة\" (false alarm \"I fell behind on my tasks\") |",
    "| 2026-11-16 | round 2 | 18/20 = 90% (95% CI 70–97%) | 15/15 = 100% (95% CI 80–100%) | \"pain in my chest\", \"عندي ألم شديد في الصدر\" |",
])
DOC = HERE.parent.parent / "docs" / "EMERGENCY_BENCHMARK.md"


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def run() -> tuple[dict, list]:
    cases = [json.loads(line) for line in SET.read_text(encoding="utf-8").splitlines() if line.strip()]
    stats, wrong = {}, []
    for c in cases:
        got = A.parse(c["text"], [], {}).get("tool") == "emergency"
        s = stats.setdefault(c["split"], {"tp": 0, "fn": 0, "tn": 0, "fp": 0})
        key = ("tp" if got else "fn") if c["emergency"] else ("fp" if got else "tn")
        s[key] += 1
        if key in ("fn", "fp"):
            wrong.append({**c, "result": "missed" if key == "fn" else "false alarm"})
    return stats, wrong


def pct(k, n):
    lo, hi = wilson(k, n)
    return f"{k}/{n} = {100 * k / n:.0f}% (95% CI {100 * lo:.0f}–{100 * hi:.0f}%)" if n else "—"


def report(stats: dict, wrong: list) -> str:
    rows = []
    for split in ("dev", "held_out"):
        s = stats.get(split, {"tp": 0, "fn": 0, "tn": 0, "fp": 0})
        rows.append(f"| {split.replace('_', '-')} | {pct(s['tp'], s['tp'] + s['fn'])} | {pct(s['tn'], s['tn'] + s['fp'])} |")
    w = "\n".join(f"- {x['split']}, {x['lang']}: \"{x['text']}\" — {x['result']}" for x in wrong) or "- none"
    fresh = "" if "held_out" in stats else "\n\n**There is no fresh held-out set yet for the current rule; write one before quoting a held-out figure.**\n"
    return f"""# Emergency-phrase benchmark{fresh}

Run on {date.today().isoformat()} by `backend/eval/run_emergency_benchmark.py` (sentences: `backend/eval/emergency_set.jsonl`).

## What this measures, and what it does not

When a person types or says something that sounds like an emergency, the assistant must open the help screen (local
emergency numbers and the person's trusted contact) **before anything else**, without a language model. This benchmark
checks that fixed rule on English and Arabic sentences.

- **Sensitivity**: of the emergency sentences, how many opened the help screen. **Specificity**: of the ordinary
  sentences, how many did not.
- **dev** sentences have been used to tune the rule. **held-out** sentences are written after a rule change and run
  once; whatever they miss is recorded below, then fixed, and they move into dev. So the current held-out line is only
  meaningful when it is a fresh set: see the history.
- All sentences were written by the build team, not by older adults, and are typed text: speech recognition errors are
  not included. Small sets give wide confidence intervals (Wilson, 95%). This is a software safety check, not a
  clinical or triage accuracy figure. The app never calls anyone and never says help is coming.
- The rule deliberately errs towards opening the help screen: a false alarm costs one tap back; a miss could cost more.

## Results

| Set | Sensitivity (emergencies caught) | Specificity (ordinary sentences left alone) |
|---|---|---|
{chr(10).join(rows)}

## Sentences handled wrongly (current rule)

{w}

## History of held-out runs (each set seen once, before it was used for tuning)

| Date | Rule version | Held-out sensitivity | Held-out specificity | Missed, then fixed |
|---|---|---|---|---|
{HISTORY}

Before round 1, the original rule missed 8 of 32 dev emergency sentences, including "Help!", "I'm hurt", "my chest
hurts", "لا أستطيع التنفس" and "سقطت", and wrongly fired on "I fell asleep early".

## Next steps

Collect real wording from older adults and family members in both languages (spoken and typed), add regional Arabic
dialect forms, and repeat after speech-to-text so recognition errors are counted.
"""


def main() -> int:
    stats, wrong = run()
    text = report(stats, wrong)
    if "--write" in sys.argv:
        DOC.write_text(text, encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
