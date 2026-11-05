"""Generate local development password without displaying it in tool output."""

import secrets

from .config import ROOT


def main():
    path = ROOT / ".env"
    if path.exists():
        print("Existing .env preserved.")
        return
    text = (ROOT / ".env.example").read_text(encoding="utf-8")
    path.write_text(
        text.replace(
            "DEMO_PASSWORD=\n", f"DEMO_PASSWORD={secrets.token_urlsafe(24)}\n"
        ),
        encoding="utf-8",
    )
    print(
        "Created local .env with generated demo password. Add provider keys locally; values are not logged."
    )


if __name__ == "__main__":
    main()
