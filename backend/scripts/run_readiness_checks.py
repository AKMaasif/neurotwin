"""Run the fixed software evaluation and export actual results; never a clinical accuracy report.

Usage: .venv/Scripts/python scripts/run_readiness_checks.py --out imaging_data/verification/readiness
Only isolated test databases are used. No real model, audio upload or emergency call is made.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

BACKEND = Path(__file__).resolve().parents[1]
CASES = [
    ("linked_journey", "tests/test_care_journeys.py", "Authorized links, versioned follow-up, explicit outcomes, source freshness and patient access"),
    ("fixed_guardrails", "tests/test_readiness_cases.py", "Report navigation, unsupported commands, emergency priority, citations and fingerprints"),
    ("activity_agents", "tests/test_activity_analysis.py", "Scripted agent pipeline, missing evidence, refusal, handoffs, review, cancellation and recovery"),
    ("voice_plumbing", "tests/test_voice_assistant.py", "Mock transcription, confirmation, repeat requests and consent"),
    ("source_quality", "tests/test_evidence_and_quality.py", "Attribution, context, missing data, correction and protocol rules"),
    ("change_rules", "tests/test_change.py", "Within-person calculations and abstention; no clinical threshold validation"),
    ("migration", "tests/test_migration_with_data.py", "Old and half-upgraded databases preserve existing records"),
    ("journey_regression", "tests/test_end_to_end_journey.py", "Existing patient journey stays functional"),
    ("privacy_logs", "tests/test_logs.py", "Identifiers, free text and tokens do not appear in application request logs"),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="imaging_data/verification/readiness")
    args = parser.parse_args()
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    # Never let a local test setting select a populated external database.
    env.pop("NEUROTWIN_TEST_DATABASE_URL", None)
    env["NEUROTWIN_AGENTS_MODE"] = "mock"
    xml = out / "results.xml"
    completed = subprocess.run([sys.executable, "-m", "pytest", *[c[1] for c in CASES], "-q", "--tb=short", f"--junitxml={xml}"],
                               cwd=BACKEND, env=env, capture_output=True, text=True)
    (out / "test-output.txt").write_text(completed.stdout + completed.stderr, encoding="utf-8")
    root = ET.parse(xml).getroot() if xml.exists() else ET.Element("testsuites")
    results = []
    for case in root.iter("testcase"):
        status = "failed" if case.find("failure") is not None else "error" if case.find("error") is not None else "skipped" if case.find("skipped") is not None else "passed"
        results.append({"test": case.attrib.get("classname", "") + "::" + case.attrib.get("name", ""), "result": status,
                        "seconds": float(case.attrib.get("time", "0"))})
    report = {"version": "readiness-software/1", "at": datetime.now(timezone.utc).isoformat(),
              "git_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=BACKEND, capture_output=True, text=True).stdout.strip(),
              "working_tree": subprocess.run(["git", "status", "--short"], cwd=BACKEND, capture_output=True, text=True).stdout.strip(),
              "scope": "Developer-authored software regression scenarios with synthetic data and stand-in providers; not an independent or clinical benchmark.",
              "not_measured": ["live model quality", "live speech recognition", "clinical sensitivity or specificity", "test-retest reliability", "clinical benefit", "Arabic clinical suitability"],
              "groups": [{"id": i, "tests": t, "expected": e} for i, t, e in CASES],
              "counts": {s: sum(r["result"] == s for r in results) for s in ("passed", "failed", "error", "skipped")},
              "results": results, "exit_code": completed.returncode}
    (out / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    lines = ["# Readiness software evaluation", "", report["scope"], "", f"Executed: {report['at']}", "", str(report["counts"]), "",
             "Live-model quality, speech accuracy, measurement validity and clinical outcomes were not measured.", "",
             "| Case | Actual result | Seconds |", "|---|---|---|"]
    lines += [f"| {r['test']} | {r['result']} | {r['seconds']:.3f} |" for r in results]
    (out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(report["counts"]))
    print(f"Evidence: {out / 'report.md'}")
    raise SystemExit(completed.returncode)


if __name__ == "__main__":
    main()
