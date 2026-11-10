"""Settings, read once from the environment.

NEUROTWIN_DATABASE_URL  SQLAlchemy URL. Default: a SQLite file next to the backend folder.
NEUROTWIN_SECRET        Key that signs session tokens. When unset, a random key is made per process,
                        so tokens stop working after a restart. Set it for anything longer-lived.
NEUROTWIN_SEED_DEMO     "1" (default) loads the synthetic demo accounts on an empty database.
"""
from __future__ import annotations

import os
import secrets
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BACKEND_DIR.parent

DATABASE_URL = os.environ.get("NEUROTWIN_DATABASE_URL") or f"sqlite:///{BACKEND_DIR / 'neurotwin.db'}"
SECRET = os.environ.get("NEUROTWIN_SECRET") or secrets.token_urlsafe(32)
SEED_DEMO = os.environ.get("NEUROTWIN_SEED_DEMO", "1") == "1"
FRONTEND_DIST = PROJECT_DIR / "frontend" / "dist"
