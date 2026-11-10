# IFHAS-NeuroTwin

A research prototype for tracking personal brain-health change over time, with accessible activities in English
and Arabic, consent-controlled sharing with family, and a clinician dashboard that shows every record with its
provenance and quality.

**Independent research prototype. Not a medical device. It does not diagnose, score or predict, and it is not
approved for clinical use. It holds synthetic demo data only; do not enter real health information.**

## What is in this version (0.1)

- **Personal app** for older adults: consent, a daily check-in, a reaction activity, sharing controls, own records
  with corrections. Large type, one task per screen, English and Arabic (right-to-left).
- **Family view**: who shares with them and which activities were done. Never answers or results.
- **Clinician dashboard**: people who shared with the clinician, a within-person chart, every record with its
  type (observed, self-reported, inferred), quality, protocol version and source, a "To check" queue and an access log.
- **Evidence core**: append-only records, explicit missing data, deterministic quality rules, revocable purpose-scoped
  sharing, audit trail, logs that never contain health values.

What is verified, experimental, planned and awaiting approval is listed in [docs/STATUS.md](docs/STATUS.md).
How it fits together: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Run it on Windows

You need **Python 3.10 or newer** and **Node.js 18 or newer**.

```powershell
cd D:\NeuroTwin
.\start.ps1
```

The script creates a Python environment, installs everything, builds the web app, and starts the server.
Open **http://127.0.0.1:8000** and sign in with a demo account.

### Demo accounts

| Username | Role |
| --- | --- |
| `fatima`, `yousef` | Older adult |
| `mariam`, `omar` | Family member |
| `dr.layla` | Clinician |

All start with the password **`neurotwin-demo-2026`** (set `NEUROTWIN_DEMO_PASSWORD` before the first start to
choose another). Each person can change their own password under Account.

If PowerShell blocks the script, run once: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

### By hand

```powershell
cd D:\NeuroTwin\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

cd ..\frontend
npm install
npm run build

cd ..\backend
python -m uvicorn app.main:create_app --factory --port 8000 --no-access-log
```

Keep `--no-access-log`: uvicorn's own access log prints raw URLs, which include person ids.

### While developing the web app

Run the server as above, then in a second terminal `cd frontend` and `npm run dev`, and open
http://127.0.0.1:5173. Changes to the web app reload live.

### Tests

```powershell
cd D:\NeuroTwin\backend
.\.venv\Scripts\Activate.ps1
python -m pytest -q
```

### Start again with fresh demo data

Stop the server, delete `backend\neurotwin.db`, start it again.

## Settings

| Variable | Default | Meaning |
| --- | --- | --- |
| `NEUROTWIN_DATABASE_URL` | SQLite file `backend/neurotwin.db` | Any SQLAlchemy URL, e.g. PostgreSQL |
| `NEUROTWIN_SEED_DEMO` | `1` | Load the synthetic demo accounts into an empty database |
| `NEUROTWIN_DEMO_PASSWORD` | `neurotwin-demo-2026` | Password given to demo accounts when first created |
| `NEUROTWIN_SECURE_COOKIES` | `0` | Set to `1` when served over HTTPS (any deployment) |
| `NEUROTWIN_SESSION_HOURS` | `8` | How long a sign-in lasts |

## Contributing

Work happens on branches and reaches `main` through `develop` and pull requests, with CI on every pull request.
See [CONTRIBUTING.md](CONTRIBUTING.md).

## Folders

```
backend/   FastAPI service: evidence core, consent, sharing, quality rules, tests
frontend/  React + TypeScript web app: personal app, family view, clinician dashboard
docs/      Status, architecture, project brief
.github/   CI workflow
```
