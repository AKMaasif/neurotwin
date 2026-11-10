"""Settings, read once from the environment.

NEUROTWIN_DATABASE_URL  SQLAlchemy URL. Default: a SQLite file next to the backend folder.
NEUROTWIN_SEED_DEMO     "1" (default) loads the synthetic demo accounts on an empty database.
NEUROTWIN_DEMO_PASSWORD Password given to every demo account when they are first created. Demo only.
NEUROTWIN_SECURE_COOKIES "1" marks the sign-in cookie Secure (HTTPS only). Set it in any deployment.
NEUROTWIN_SESSION_HOURS How long a sign-in lasts. Default 8.
"""
from __future__ import annotations

import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BACKEND_DIR.parent

DATABASE_URL = os.environ.get("NEUROTWIN_DATABASE_URL") or f"sqlite:///{BACKEND_DIR / 'neurotwin.db'}"
SEED_DEMO = os.environ.get("NEUROTWIN_SEED_DEMO", "1") == "1"
DEMO_PASSWORD = os.environ.get("NEUROTWIN_DEMO_PASSWORD") or "neurotwin-demo-2026"
SECURE_COOKIES = os.environ.get("NEUROTWIN_SECURE_COOKIES", "0") == "1"
SESSION_HOURS = float(os.environ.get("NEUROTWIN_SESSION_HOURS") or 8)
FRONTEND_DIST = PROJECT_DIR / "frontend" / "dist"
