"""Server-side response time of key endpoints, in process (FastAPI TestClient, SQLite, seeded demo data, no model calls).
Usage, from backend/:  python eval/run_latency_benchmark.py [--write]   (--write updates docs/LATENCY_BENCHMARK.md)

It times the application code and database only: no network, no browser, no external AI provider. A deployed server
adds network time and runs on different hardware, so treat these as a lower bound and a regression check."""
import os
import platform
import statistics
import sys
import tempfile
import time
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
for k in ("GEMINI_API_KEY", "META_API_KEY"):
    os.environ.pop(k, None)  # never call a provider from a benchmark
from fastapi.testclient import TestClient  # noqa: E402
from app.main import create_app  # noqa: E402

DOC = HERE.parent.parent / "docs" / "LATENCY_BENCHMARK.md"
N, WARMUP, PW = 200, 10, "latency-benchmark-pw-1"


def sign_in(c: TestClient, username: str) -> dict:
    r = c.post("/api/auth/login", json={"username": username, "password": PW})
    r.raise_for_status()
    tok = r.cookies.get("nt_session")
    c.cookies.clear()
    return {"Cookie": f"nt_session={tok}", "X-CSRF-Token": r.json()["csrf"]}


def timed(fn) -> dict:
    for _ in range(WARMUP):
        fn()
    ms = []
    for _ in range(N):
        t = time.perf_counter()
        r = fn()
        ms.append((time.perf_counter() - t) * 1000)
        assert r.status_code < 400, (r.status_code, r.text[:200])
    ms.sort()
    return {"median": statistics.median(ms), "p95": ms[int(0.95 * N) - 1], "max": ms[-1]}


def run() -> list[tuple[str, str, dict]]:
    tmp = tempfile.mkdtemp()
    app = create_app(database_url=f"sqlite:///{tmp}/bench.db", seed_demo=True, serve_frontend=False, demo_password=PW)
    c = TestClient(app)
    clin, fatima = sign_in(c, "dr.layla"), sign_in(c, "fatima")
    pid = c.get("/api/clinician/participants", headers=clin).json()[0]["id"]
    cases = [
        ("Health check", "GET /api/health", lambda: c.get("/api/health")),
        ("Clinician caseload", "GET /api/clinician/participants", lambda: c.get("/api/clinician/participants", headers=clin)),
        ("Person's timeline (evidence)", "GET /api/participants/{pid}/evidence", lambda: c.get(f"/api/participants/{pid}/evidence", headers=clin)),
        ("Change estimates (change engine)", "GET /api/participants/{pid}/change", lambda: c.get(f"/api/participants/{pid}/change", headers=clin)),
        ("Clinician report", "GET /api/participants/{pid}/report", lambda: c.get(f"/api/participants/{pid}/report", headers=clin)),
        ("Person's Today routines", "GET /api/care-plan/today", lambda: c.get("/api/care-plan/today", headers=fatima)),
        ("Assistant: \"what is on today\"", "POST /api/assistant/message", lambda: c.post("/api/assistant/message", json={"text": "what is on today"}, headers=fatima)),
        ("Assistant: \"I need help\" (emergency rule)", "POST /api/assistant/message", lambda: c.post("/api/assistant/message", json={"text": "I need help"}, headers=fatima)),
    ]
    out = [(name, route, timed(fn)) for name, route, fn in cases]
    app.state.db.engine.dispose()
    return out


def report(rows) -> str:
    table = "\n".join(f"| {n} | `{r}` | {s['median']:.1f} | {s['p95']:.1f} | {s['max']:.1f} |" for n, r, s in rows)
    return f"""# Response-time benchmark (server, in process)

Run on {date.today().isoformat()} by `backend/eval/run_latency_benchmark.py`: {N} timed requests per endpoint after
{WARMUP} warm-up requests, seeded synthetic demo data, SQLite, Python {platform.python_version()} on {platform.system()}
({platform.machine()}), one request at a time.

## What this measures, and what it does not

The time the application code and database take to answer, measured inside the process. It excludes the network,
the browser, and any external AI provider (no provider keys are set; the model-assisted fallback is not called).
A deployed server on other hardware, with PostgreSQL and real network, will be slower; this is a lower bound and a
regression check, not a load test. Concurrency and many-user load are not measured.

## Results (milliseconds)

| What | Endpoint | Median | 95th percentile | Slowest |
|---|---|---|---|---|
{table}

The emergency rule answers without a model, so opening the help screen does not wait for any provider.

## Next steps

Repeat against the deployed link (including network), add a concurrent-users load test on PostgreSQL, and time the
model-assisted paths separately with their provider timeouts.
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
