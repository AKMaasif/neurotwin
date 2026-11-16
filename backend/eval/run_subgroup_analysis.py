"""Subgroup analysis: do the fixed rules behave the same for different groups of people?
Usage, from backend/:
  python eval/run_subgroup_analysis.py [--write]      benchmarks (--write updates docs/SUBGROUP_ANALYSIS.md)
  python eval/run_subgroup_analysis.py --db path.db   share of doubtful or unusable records by education, first language,
                                                      session language and device, in a pilot database

What it covers today:
1. The change engine on simulated people who differ in day-to-day spread, in device, and in how often they do the
   activity (the truth is known, so false alarms and detection can be counted per group).
2. The emergency-phrase rule, English against Arabic sentences.
3. The companion's text understanding, English against Arabic sentences.
It does NOT cover real people: no pilot data exists. Age, sex, education and first language can only be analysed once
a pilot collects them (the code for that is `app.subgroups.quality_by` and `--db`)."""
import json
import math
import random
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from app import assistant as A, change, subgroups as G  # noqa: E402

DOC = HERE.parent.parent / "docs" / "SUBGROUP_ANALYSIS.md"
SEED, N = 20261116, 2000
T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
SESSIONS = 9   # 2 practice + 7


def person(rng: random.Random, sd: float, slow_ms: float = 0, device_shift_from: int | None = None, device_ms: float = 30,
           usable: int = SESSIONS) -> list:
    mu = rng.uniform(380, 520)
    rows = []
    for i in range(SESSIONS):
        v = mu + rng.gauss(0, sd) - 40 * (1 - math.exp(-i / 1.5))
        if device_shift_from is not None and i >= device_shift_from:
            v += device_ms                       # a slower device (for example a touch screen instead of a mouse)
        if i >= SESSIONS - 2:
            v += slow_ms
        rows.append(SimpleNamespace(id=i + 1, status="current", value_num=round(v, 1), quality="usable" if i < usable else "unusable",
                                    recorded_at=T0 + timedelta(days=7 * i), protocol_code="reaction_time", protocol_version="0.1",
                                    measure="rt_median_ms", kind="observed", unit="ms"))
    return rows


def engine_rows(label: str, groups: dict) -> list:
    """groups: name -> person() keyword arguments (sd drawn from a range)."""
    rng = random.Random(f"{SEED}-{label}")
    out = []
    for name, kw in groups.items():
        lo, hi = kw.pop("sd_range")
        for _ in range(N):
            r = change.compare(person(rng, rng.uniform(lo, hi), **kw))
            out.append(SimpleNamespace(group=name, flagged_slower=r.status == "outside" and r.direction == "higher",
                                       flagged=r.status == "outside", abstained=r.status in ("insufficient", "no_variation")))
        kw["sd_range"] = (lo, hi)
    return out


def engine_results() -> list[G.SubgroupResult]:
    res = []
    rows = engine_rows("spread-stable", {"steady (day-to-day SD 15–25 ms)": {"sd_range": (15, 25)},
                                         "variable (day-to-day SD 30–40 ms)": {"sd_range": (30, 40)}})
    res.append(G.by_group(rows, lambda r: r.group, lambda r: r.flagged, "false alarm (stable person flagged)", "day-to-day spread"))
    rows = engine_rows("spread-60", {"steady (day-to-day SD 15–25 ms)": {"sd_range": (15, 25), "slow_ms": 60},
                                     "variable (day-to-day SD 30–40 ms)": {"sd_range": (30, 40), "slow_ms": 60}})
    res.append(G.by_group(rows, lambda r: r.group, lambda r: r.flagged_slower, "a real 60 ms slowing flagged", "day-to-day spread"))
    rows = engine_rows("device", {"same device throughout": {"sd_range": (15, 40)},
                                  "changed to a slower device (+30 ms) at session 6": {"sd_range": (15, 40), "device_shift_from": 5}})
    res.append(G.by_group(rows, lambda r: r.group, lambda r: r.flagged_slower, "stable person flagged slower", "device"))
    rows = engine_rows("regular", {"regular (all 9 sessions usable)": {"sd_range": (15, 40), "slow_ms": 60},
                                   "irregular (6 of 9 usable, 4 after practice)": {"sd_range": (15, 40), "slow_ms": 60, "usable": 6}})
    res.append(G.by_group(rows, lambda r: r.group, lambda r: r.abstained, "engine abstained (too few records)", "regularity of use"))
    return res


def emergency_results() -> list[G.SubgroupResult]:
    cases = [json.loads(x) for x in (HERE / "emergency_set.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    for c in cases:
        c["fired"] = A.parse(c["text"], [], {}).get("tool") == "emergency"
    lang = {"en": "English", "ar": "Arabic"}
    return [G.by_group([c for c in cases if c["emergency"]], lambda c: lang[c["lang"]], lambda c: c["fired"],
                       "emergency sentence opened help (tuning set)", "language"),
            G.by_group([c for c in cases if not c["emergency"]], lambda c: lang[c["lang"]], lambda c: not c["fired"],
                       "ordinary sentence left alone (tuning set)", "language")]


def companion_results() -> list[G.SubgroupResult]:
    import run_companion_eval as C
    out = []
    for which in ("dev", "final"):
        cases = [json.loads(x) for x in (HERE / f"companion_{which}.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
        lang = {"en": "English", "ar": "Arabic"}
        out.append(G.by_group(cases, lambda c: lang[c["lang"]], lambda c: C.judge(c, C.predict(c)) == "ok",
                              f"request understood ({which} set)", "language", min_n=10))
    return out


def pct(x: float) -> str:
    return f"{100 * x:.1f}%" if not math.isnan(x) else "—"


def table(results: list[G.SubgroupResult]) -> str:
    lines = ["| Outcome | Group | n | Rate (95% CI) | Largest gap (95% CI) |", "|---|---|---|---|---|"]
    for r in results:
        gap = "—"
        if r.gap:
            gap = f"{100 * r.gap[2]:+.1f} points ({100 * r.gap[3]:+.1f} to {100 * r.gap[4]:+.1f}){' **clear**' if r.gap_clear else ''}"
        for i, g in enumerate(r.groups + r.small):
            small = " (too few to compare)" if g in r.small else ""
            lines.append(f"| {r.outcome if i == 0 else ''} | {g.name}{small} | {g.n} | {pct(g.rate)} ({pct(g.ci[0])}–{pct(g.ci[1])}) | {gap if i == 0 else ''} |")
    return "\n".join(lines)


def report(eng, emg, cmp_) -> str:
    fa, sixty, dev, reg = eng
    return f"""# Subgroup analysis

Run on {date.today().isoformat()} by `backend/eval/run_subgroup_analysis.py` (code: `backend/app/subgroups.py`), seed {SEED}.
Each rate has a 95% Wilson interval; the largest gap between groups has a 95% Newcombe interval and is marked
**clear** when that interval excludes 0. Groups below the minimum size are shown but never compared.

## What this covers, and what it does not

There is **no pilot data yet**, so nothing here is about real people. It checks whether the fixed rules behave
differently for kinds of people and situations we can simulate or write sentences for. Age, sex, education and first
language can only be analysed once a pilot collects them; the code is ready (`--db`, `subgroups.quality_by`). The
"About you" screen already asks education and first language, optionally, for exactly this purpose.

## 1. Change engine on simulated people ({N} per group; 2 practice + 7 weekly sessions)

{table(eng)}

What this tells a clinician:
- **Equal false alarms, unequal detection.** The engine works in each person's own spread, so false alarms are about
  the same for steady and variable people ({pct(fa.groups[0].rate)} and {pct(fa.groups[1].rate)}). But the same real
  60 ms slowing is flagged for {pct(sixty.groups[0].rate)} of steady people and only {pct(sixty.groups[1].rate)} of
  variable people. People whose results vary a lot day to day (fatigue, tremor, distraction, an unfamiliar device)
  need a larger change before it shows. "Within usual variation" means less for them.
- **A device change looks like a slowing.** Stable people who switch to a slower device part-way are flagged slower
  {pct(dev.groups[0].rate)} of the time, against {pct(dev.groups[1].rate)} on one device. Each session records its
  device, and the clinician sees it; the engine does not yet compare only like with like. Pilot task: measure device
  offsets, then decide whether to split by device.
- **Irregular use means no answer, not a wrong one.** With 6 of 9 sessions usable (4 after the practice sessions, 5 are needed) the engine abstains
  {pct(reg.groups[0].rate if reg.groups[0].name.startswith('irregular') else reg.groups[1].rate)} of the time instead of guessing.

## 2. Emergency-phrase rule, by language

{table(emg)}

These are the sentences the rule was tuned on, so both languages are near 100% by construction. The held-out rounds
(docs/EMERGENCY_BENCHMARK.md) are too small to split by language. Arabic dialect coverage is the known weak point.

## 3. Companion text understanding, by language

{table(cmp_)}

Arabic has fewer sentences, so its interval is wide; a gap of this size cannot be ruled in or out.

## Next steps

In the pilot: collect age band, sex, education, first language, device and session language (all optional), report
every outcome above by each, with a minimum group size of {G.MIN_N}, and have a statistician review any clear gap
before anything is changed.
"""


def from_db(path: str) -> int:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    with Session(create_engine(f"sqlite:///{path}")) as db:
        for attr in ("education", "first_language", "language", "device"):
            print(json.dumps(G.quality_by(db, attr).as_dict(), ensure_ascii=False))
    return 0


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.path.insert(0, str(HERE))
    if "--db" in sys.argv:
        return from_db(sys.argv[sys.argv.index("--db") + 1])
    text = report(engine_results(), emergency_results(), companion_results())
    if "--write" in sys.argv:
        DOC.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
