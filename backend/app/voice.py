"""Speech to text, for dictating a short message.

- Recording is started and stopped by the person, in the browser, with a visible indicator. This module only
  receives the finished clip.
- The clip is sent to the speech provider once and is never written to disk or to the database. Only the text comes
  back, and it goes into a text box for the person to read and fix: nothing is sent or saved because of it.
- A transcript is untrusted text. It is not given to any model, and it is not evidence.
- Limits: 2.5 MB and a daily call cap, so the open demo cannot spend the owner's quota without bound.
- A participant needs their voice-recording consent switched on; the audit log records that a clip was transcribed,
  never its words.
"""
from __future__ import annotations

import os
from datetime import date

from sqlalchemy.orm import Session

from . import llm
from .models import User
from .services import Refused, audit, consent_state

MAX_BYTES = 2_500_000
MIME = {"audio/webm", "audio/ogg", "audio/mp4", "audio/mpeg", "audio/wav"}
MAX_TEXT = 1000
_calls = {"day": None, "n": 0}


def daily_limit() -> int:
    try:
        return int(os.environ.get("NEUROTWIN_STT_DAILY_CALLS") or 100)
    except ValueError:
        return 100


def _take_call() -> None:
    today = date.today()
    if _calls["day"] != today:
        _calls["day"], _calls["n"] = today, 0
    if _calls["n"] >= daily_limit():
        raise Refused(429, "Today's limit for voice typing has been reached. Please type instead.")
    _calls["n"] += 1


def transcribe(db: Session, user: User, audio: bytes, content_type: str, language: str, client) -> dict:
    if client is None:
        raise Refused(503, "Voice typing is not set up on this server. Please type instead.")
    mime = (content_type or "").split(";")[0].strip().lower()
    if mime not in MIME:
        raise Refused(415, "That audio format is not supported.")
    if language not in ("en", "ar"):
        raise Refused(422, "Language must be en or ar.")
    if not audio:
        raise Refused(422, "No sound was received.")
    if len(audio) > MAX_BYTES:
        raise Refused(413, "That recording is too long. Keep it under a minute.")
    if user.role == "participant" and not consent_state(db, user.id).get("voice_recording", {}).get("granted"):
        raise Refused(403, "Voice recording is switched off for you. You can turn it on under Consent.")
    _take_call()
    try:
        reply = client.transcribe(audio, mime, language)
    except llm.ModelError as e:
        audit(db, user.id, "voice.failed", None, client.provider)
        db.commit()
        raise Refused(502, f"Voice typing could not be used: {e}") from None
    audit(db, user.id, "voice.transcribed", user.id if user.role == "participant" else None, client.provider)
    db.commit()
    return {"text": reply.text[:MAX_TEXT], "provider": reply.provider, "model": reply.model}
