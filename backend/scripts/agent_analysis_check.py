"""Run Agent Analysis stages 1-2 on a real extracted pair and print the result. Usage: agent_analysis_check.py EARLIER LATER"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import agent_analysis as A  # noqa: E402

run = A.create_run(sys.argv[1], sys.argv[2])
print("validation:", json.dumps({k: run["validation"].get(k) for k in ("status", "blockers", "interval")}))
if run["state"] != "blocked":
    run = A.align(run["run_id"])
    print("alignment:", json.dumps(run["alignment"]))
print("state:", run["state"], "| run", run["run_id"])
