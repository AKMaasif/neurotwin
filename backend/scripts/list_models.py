"""Show which models each configured key can use. Run from the backend folder:

    python scripts/list_models.py

Reads keys from the environment or backend/.env. Prints model ids only. It never prints a key.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import llm  # noqa: E402  (also loads backend/.env through app.config)
from app import config  # noqa: E402,F401


def main() -> int:
    found = llm.clients()
    if not found:
        print("No keys found. Copy .env.example to .env in the backend folder and add GEMINI_API_KEY or META_API_KEY.")
        return 1
    failed = False
    for name, client in found.items():
        print(f"\n{name}:")
        try:
            models = client.list_models()
        except llm.ModelError as e:
            print(f"  could not list models: {e}")
            failed = True
            continue
        if not models:
            print("  the key works, but no text models were returned")
        for m in models:
            print(f"  {m}")
    state = llm.status()
    print(f"\nActive provider: {state['provider'] or 'none'}"
          f"{' · model ' + state['model'] if state['model'] else ''}")
    if not state["configured"]:
        print("Set NEUROTWIN_AI_PROVIDER and that provider's model id in backend/.env to switch model features on.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
