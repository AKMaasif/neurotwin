"""Live check: ask a real model for a summary of the synthetic demo person and show what the validator made of it.

    python scripts/try_draft.py                 # the provider set in backend/.env
    python scripts/try_draft.py --all           # every provider that has a key and a model id
    python scripts/try_draft.py --language ar

Uses a throwaway copy of the demo data, never your real database. Prints no keys. Spends a little model quota.
"""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import drafts as D  # noqa: E402
from app import llm  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models import User  # noqa: E402
from app.services import Refused  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--language", default="en", choices=["en", "ar"])
    args = ap.parse_args()

    if args.all:
        chosen = [c for c in llm.clients().values() if c.model]
    else:
        chosen = [c for c in [llm.get_client()] if c]
    if not chosen:
        print("No provider is ready. In backend/.env set NEUROTWIN_AI_PROVIDER and that provider's model id.")
        return 1

    with tempfile.TemporaryDirectory() as tmp:
        app = create_app(database_url=f"sqlite:///{Path(tmp) / 'try.db'}", seed_demo=True, serve_frontend=False)
        failed = False
        for client in chosen:
            print(f"\n=== {client.provider} · {client.model} · {args.language} ===")
            D._calls.update(day=None, n=0)
            with app.state.db.SessionLocal() as db:
                clinician = db.get(User, "demo-dr-layla")
                try:
                    draft = D.generate(db, clinician, "demo-fatima", args.language, client)
                except Refused as e:
                    print(f"FAILED: {e.message}")
                    failed = True
                    continue
                print(f"status: {draft.status} · attempts: {draft.attempts} · {draft.validator_version}")
                if draft.status == "refused":
                    failed = True
                    print("The validator refused both attempts:")
                    for p in draft.problems:
                        print(f"  - statement {p['index'] + 1}: {p['code']}: {p['detail']}")
                else:
                    for i, s in enumerate(draft.statements, start=1):
                        print(f"  {i}. {s['text']}  [{', '.join(s['cites'])}]")
        app.state.db.engine.dispose()
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
