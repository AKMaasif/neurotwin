"""Run each browser flow against its own fresh synthetic SQLite application."""

import datetime as dt
import json
import os
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path

import httpx

DEFAULT_CHECKS = [
    "browser_check",
    "companion_browser_check",
    "report_browser_check",
    "routine_browser_check",
    "message_browser_check",
    "voice_note_browser_check",
    "multimedia_browser_check",
    "ui_reference_browser_check",
    "plan_design_browser_check",
    "clinical_design_browser_check",
    "clinical_privacy_browser_check",
]
SUPPORTED_CHECKS = DEFAULT_CHECKS + [
    "account_sessions_browser_check",
    "camera_browser_check",
    "iot_browser_check",
    "research_browser_check",
    "adaptive_mobile_browser_check",
    "care_pages_browser_check",
    "family_reports_design_check",
    "premium_mobile_browser_check",
]


def main():
    root = Path(__file__).resolve().parents[1]
    checks = sys.argv[1:] or DEFAULT_CHECKS
    if any(check not in SUPPORTED_CHECKS for check in checks):
        raise SystemExit(
            "Choose a known browser check; script names cannot be arbitrary paths"
        )
    batch = uuid.uuid4().hex[:12]
    out = root / "test-results" / "isolated-browser" / batch
    out.mkdir(parents=True)
    results = []
    for check in checks:
        fixture = root / "data" / f"browser-{batch}-{check}.db"
        if fixture.exists():
            raise SystemExit("Refusing to reuse a browser fixture")
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        env = os.environ | {
            "DATABASE_URL": "sqlite:///" + fixture.as_posix(),
            "AI_ENABLED": "false",
            "SEED_DEMO": "true",
            "APP_ENV": "development",
            "MEDIA_STORE_PATH": str(root / "data" / f"browser-{batch}-{check}-media"),
            "NEUROTWIN_BASE_URL": f"http://127.0.0.1:{port}",
        }
        with (out / f"{check}-server.log").open("w", encoding="utf-8") as log:
            worker = None
            server = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "app.main:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                ],
                cwd=root,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
            try:
                ready = False
                for _ in range(100):
                    if server.poll() is not None:
                        break
                    try:
                        ready = (
                            httpx.get(
                                env["NEUROTWIN_BASE_URL"] + "/health", timeout=1
                            ).status_code
                            == 200
                        )
                    except httpx.HTTPError:
                        pass
                    if ready:
                        break
                    time.sleep(0.1)
                if not ready:
                    raise RuntimeError(
                        "Isolated API did not become healthy; see local server log"
                    )
                worker = subprocess.Popen(
                    [sys.executable, "-m", "app.worker"],
                    cwd=root,
                    env=env,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                )
                start = time.monotonic()
                execution = subprocess.run(
                    ["node", f"scripts/{check}.cjs"],
                    cwd=root,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=240,
                    check=False,
                )
                (out / f"{check}.log").write_text(
                    execution.stdout + execution.stderr, encoding="utf-8"
                )
                result = {
                    "check": check,
                    "exit_code": execution.returncode,
                    "seconds": round(time.monotonic() - start, 2),
                }
            except (RuntimeError, subprocess.TimeoutExpired) as error:
                result = {"check": check, "exit_code": 1, "error": str(error)}
            finally:
                if worker:
                    worker.terminate()
                    try:
                        worker.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        worker.kill()
                        worker.wait(timeout=5)
                server.terminate()
                try:
                    server.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait(timeout=5)
        results.append(result)
        print(json.dumps(result), flush=True)
        (out / "report.json").write_text(
            json.dumps(
                {
                    "at": dt.datetime.now(dt.timezone.utc).isoformat(),
                    "mode": "one fresh synthetic app/database per browser script; AI disabled",
                    "results": results,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    raise SystemExit(0 if all(result["exit_code"] == 0 for result in results) else 1)


if __name__ == "__main__":
    main()
