"""Live check of speech to text with a short recording of your own voice.

    python scripts/try_voice.py clip.webm            # the provider chosen in backend/.env
    python scripts/try_voice.py clip.m4a --all --language ar

Record a few seconds with any recorder (a phone voice memo works), save it as .webm, .ogg, .m4a, .mp3 or .wav.
The clip goes to the provider once. Nothing is stored. Prints no keys.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import llm  # noqa: E402
from app.config import load_env  # noqa: E402

MIME = {".webm": "audio/webm", ".ogg": "audio/ogg", ".m4a": "audio/mp4", ".mp4": "audio/mp4",
        ".mp3": "audio/mpeg", ".wav": "audio/wav"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--language", default="en", choices=["en", "ar"])
    ap.add_argument("--all", action="store_true", help="try every provider that has a key and a speech model")
    args = ap.parse_args()
    load_env()
    path = Path(args.file)
    mime = MIME.get(path.suffix.lower())
    if mime is None or not path.is_file():
        print(f"Use an existing file ending in {', '.join(MIME)}.")
        return 1
    import os
    env = dict(os.environ)
    if args.all:
        chosen = [llm.get_stt_client({**env, "NEUROTWIN_STT_PROVIDER": p}) for p in ("gemini", "meta")]
    else:
        chosen = [llm.get_stt_client(env)]
    chosen = [c for c in chosen if c]
    if not chosen:
        print("No speech provider is ready. Set META_STT_MODEL (and a Meta key) or a Gemini key and model in backend/.env.")
        return 1
    failed = False
    for c in chosen:
        print(f"\n=== {c.provider} · {c.model} · {args.language} ===")
        try:
            print(c.transcribe(path.read_bytes(), mime, args.language).text or "(nothing recognised)")
        except llm.ModelError as e:
            print(f"FAILED: {e}")
            failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
