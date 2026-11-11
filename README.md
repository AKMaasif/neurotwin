# IFHAS-NeuroTwin

A research prototype for tracking personal brain-health change over time, with accessible activities in English
and Arabic, consent-controlled sharing with family, and a clinician dashboard that shows every record with its
provenance and quality.

**Independent research prototype. Not a medical device. It does not diagnose, score or predict, and it is not
approved for clinical use. Clinical demo records are synthetic; do not enter real health information.**

An optional, separate **Brain Analytics** research preview can display one locally prepared OASIS-1 case, with
interactive MRI slices, actual 3D cortical surfaces, layers, internal exploration and imported measurements.
See [the preview guide](docs/IMAGING_PREVIEW.md) for setup, access restrictions and current limitations.

Start with the [project goal, completed work and remaining roadmap](docs/PROJECT_ROADMAP.md) for the current
development picture. New MRI processing follows the [NeuroTwin-owned architecture](docs/NATIVE_IMAGING_AND_AI_PLAN.md)
without FreeSurfer execution; the supplied derivative viewer remains a labelled reference.

## What is in this version (0.2)

- **Personal app** for older adults: consent, a daily check-in, a reaction activity, sharing controls, own records
  with corrections. Large type, one task per screen, English and Arabic (right-to-left).
- **Family view**: who shares with them and which activities were done. Never answers or results.
- **Clinician dashboard**: people who shared with the clinician, a within-person chart, every record with its
  type (observed, self-reported, inferred), quality, protocol version and source, a "To check" queue and an access log.
- **Change estimates** for clinicians: each person compared only with their own earlier results, with a 95%
  interval, abstaining when the evidence is thin.
- **Summary drafts** for clinicians (needs a model key): a model writes from stored facts, rules check every
  statement, and the clinician approves, edits or rejects.
- **Password sign-in** with server-side sessions, and an Account screen for changing passwords.
- **Evidence core**: append-only records, explicit missing data, deterministic quality rules, revocable purpose-scoped
  sharing, audit trail, logs that never contain health values.

What is verified, experimental, planned and awaiting approval is listed in [docs/STATUS.md](docs/STATUS.md).
Changes by version: [CHANGELOG.md](CHANGELOG.md).
How it fits together: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Run it on Windows

You need **Python 3.10 or newer** and **Node.js 18 or newer**.

```powershell
cd D:\NeuroTwin
.\start.ps1
```

The script creates a Python environment, installs everything, builds the web app, and starts the server.
Open **http://127.0.0.1:8000** and choose a view. No username or password is needed in demo mode.

### Demo views

| View | Opens as |
| --- | --- |
| Older adult | Fatima (Arabic) or Yousef (English) |
| Family member | Mariam or Omar |
| Clinician | Dr. Layla |

One click opens a view. The demo accounts are shared by everyone using the server, so password changes and
"sign out other devices" are switched off for them. On a server started with `NEUROTWIN_SEED_DEMO=0`, one-click
entry is off and the front page shows a username and password form instead.

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
| `NEUROTWIN_SEED_DEMO` | `1` | Demo mode: load the synthetic demo accounts and allow one-click entry to them |
| `NEUROTWIN_DEMO_PASSWORD` | `neurotwin-demo-2026` | Password of the demo accounts (only needed if you sign in to them by password) |
| `NEUROTWIN_SECURE_COOKIES` | `0` | Set to `1` when served over HTTPS (any deployment) |
| `NEUROTWIN_SESSION_HOURS` | `8` | How long a sign-in lasts |

## Model providers (optional)

NeuroTwin runs fully without any AI key. To prepare for the model-assisted features, add keys for Google Gemini,
Meta's Model API, or both:

```powershell
cd D:\NeuroTwin\backend
copy .env.example .env      # then open .env and paste your keys
.\.venv\Scripts\python.exe scripts\list_models.py
```

The script lists the models each key can use and never prints a key. Put the provider and model you choose in
`.env` (`NEUROTWIN_AI_PROVIDER`, `GEMINI_MODEL` or `META_MODEL`), then check a real draft end to end:

```powershell
.\.venv\Scripts\python.exe scripts\try_draft.py --all
```

With a provider set, the clinician's **Summary** tab can write a draft summary of a person's records. `backend/.env` is ignored by git: never commit it,
and never send real health data to a provider. Every model-written draft must pass the output validator
(`backend/app/validator.py`) and then a clinician's review.

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
