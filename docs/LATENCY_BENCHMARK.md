# Response-time benchmark (server, in process)

Run on 2026-11-16 by `backend/eval/run_latency_benchmark.py`: 200 timed requests per endpoint after
10 warm-up requests, seeded synthetic demo data, SQLite, Python 3.14.7 on Windows
(AMD64), one request at a time.

## What this measures, and what it does not

The time the application code and database take to answer, measured inside the process. It excludes the network,
the browser, and any external AI provider (no provider keys are set; the model-assisted fallback is not called).
A deployed server on other hardware, with PostgreSQL and real network, will be slower; this is a lower bound and a
regression check, not a load test. Concurrency and many-user load are not measured.

## Results (milliseconds)

| What | Endpoint | Median | 95th percentile | Slowest |
|---|---|---|---|---|
| Health check | `GET /api/health` | 6.3 | 26.3 | 41.9 |
| Clinician caseload | `GET /api/clinician/participants` | 13.7 | 34.6 | 48.7 |
| Person's timeline (evidence) | `GET /api/participants/{pid}/evidence` | 18.8 | 34.5 | 48.2 |
| Change estimates (change engine) | `GET /api/participants/{pid}/change` | 15.6 | 31.3 | 41.2 |
| Clinician report | `GET /api/participants/{pid}/report` | 17.3 | 34.3 | 65.8 |
| Person's Today routines | `GET /api/care-plan/today` | 11.0 | 22.8 | 29.0 |
| Assistant: "what is on today" | `POST /api/assistant/message` | 41.3 | 64.0 | 101.7 |
| Assistant: "I need help" (emergency rule) | `POST /api/assistant/message` | 37.5 | 59.3 | 110.1 |

The emergency rule answers without a model, so opening the help screen does not wait for any provider.

## Next steps

Repeat against the deployed link (including network), add a concurrent-users load test on PostgreSQL, and time the
model-assisted paths separately with their provider timeouts.
