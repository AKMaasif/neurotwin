"""Run the agent scenario evaluation and write docs/AGENT_EVAL_REPORT.md.

    python scripts/run_agent_eval.py            # from backend/

The scenarios are in tests/test_agent_eval.py. They feed each agent prepared replies from stand-in models and check that the rules around
the model behaved as designed. This is NOT a measure of model quality, diagnostic accuracy, or Arabic quality.
"""
from __future__ import annotations

import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent.parent
OUT = HERE.parent / "docs" / "AGENT_EVAL_REPORT.md"
NAMES = {"A1": "A1 Quality reviewer", "A2": "A2 Findings challenger", "A3": "A3 Evidence explainer", "A4": "A4 Cross-checker", "A5": "A5 Ask-the-Evidence",
         "A6": "A6 Follow-up planner", "A7": "A7 Family summary", "A8": "A8 Report QA", "A9": "A9 Visual comparison", "AR": "Arabic glossary and back-translation"}


class Collector:
    def __init__(self):
        self.rows = []

    def pytest_runtest_logreport(self, report):
        if report.when == "call" or (report.when == "setup" and report.failed):
            self.rows.append(report)

    def pytest_collection_modifyitems(self, items):
        self.marks = {i.nodeid: next((m.args for m in i.iter_markers("scenario")), None) for i in items}


def main() -> int:
    c = Collector()
    code = pytest.main(["-q", "-p", "no:cacheprovider", str(HERE / "tests" / "test_agent_eval.py")], plugins=[c])
    by = defaultdict(list)
    for r in c.rows:
        m = c.marks.get(r.nodeid)
        if m:
            by[m[0]].append((m[1], r.passed))
    lines = ["# Agent scenario evaluation", "", f"Run on {date.today().isoformat()} by `backend/scripts/run_agent_eval.py` (scenarios: `backend/tests/test_agent_eval.py`).", "",
             "## What this measures, and what it does not", "",
             "Each scenario gives an agent a prepared reply from a **stand-in model** (often a bad one, such as a draft that alters a number, names a condition or cites a fact it was not given) and checks that the rules around the model did what the design says: refused, blocked, flagged, abstained or passed.",
             "",
             "- A pass means the guard rail works on that input. It does **not** say how often Gemini or Meta write such replies, how often the word lists miss a paraphrase, or whether accepted text is clinically useful.",
             "- Nothing here is a diagnostic accuracy, sensitivity or specificity figure, and no live model was called.",
             "- Arabic scenarios test numbers, structure names and word lists only. Arabic quality needs a native clinical reader.",
             "- The scenarios were written by the build team, so they reflect what we thought to test. A clinician-written set and a run on real model output are still needed.", "",
             "## Results", "", "| Agent | Scenarios | Passed | Failed |", "|---|---|---|---|"]
    tp = tf = 0
    for k in NAMES:
        rows = by.get(k, [])
        p = sum(1 for _, ok in rows if ok); tp += p; tf += len(rows) - p
        lines.append(f"| {NAMES[k]} | {len(rows)} | {p} | {len(rows) - p} |")
    lines += [f"| **Total** | **{tp + tf}** | **{tp}** | **{tf}** |", "", "## Scenarios", ""]
    for k in NAMES:
        lines.append(f"### {NAMES[k]}")
        lines += [f"- {'PASS' if ok else 'FAIL'}: {n}" for n, ok in by.get(k, [])]
        lines.append("")
    lines += ["## Not yet evaluated", "",
              "- Live Gemini and Meta output (no live call has been made); repair-attempt rate, refusal rate and cross-model disagreement rate on real replies.",
              "- Miss and over-block rates of the word lists on real paraphrases (English and Arabic).",
              "- Whether the Arabic is natural and clinically right (native clinical reader).",
              "- Whether the explanations and family text are understandable to older adults and families (usability testing).",
              "- Any clinical suitability or intended-population validation."]
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {OUT} ({tp} passed, {tf} failed)")
    return int(code != 0)


if __name__ == "__main__":
    sys.exit(main())
