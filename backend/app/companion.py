"""Voice companion: configuration, speech output and (demo accounts only) model-assisted understanding.

The companion is a layer on the existing assistant. It adds no new way to change anything: every action still goes through
`assistant.message` and its confirmation rules. This module only decides what the browser may offer and speaks text the server
already produced.

Rules:
- Off unless NEUROTWIN_COMPANION=1. Off means the existing assistant screen is all there is.
- Real participants' voices, words and tasks are never sent to an external provider. Speech-to-text (voice.py) is for demo
  (synthetic) accounts only; server speech and the language model also need the person's own `assistant_model` consent.
  Everyone else types, and gets the browser's voice and the fixed-pattern assistant.
- No audio is stored. The audit log records that speech was produced or a model was asked, never the words.
"""
from __future__ import annotations

import os
from datetime import date

from sqlalchemy.orm import Session

from . import llm
from .models import User
from .services import Refused, audit, consent_state

MAX_SPEAK_CHARS = 600
_calls = {"day": None, "n": 0}


def enabled(env: dict | None = None) -> bool:
    env = os.environ if env is None else env
    return str(env.get("NEUROTWIN_COMPANION") or "").strip().lower() in ("1", "true", "on", "yes")


def _daily(env: dict | None = None) -> int:
    env = os.environ if env is None else env
    try:
        return int(env.get("NEUROTWIN_TTS_DAILY_CALLS") or 200)
    except ValueError:
        return 200


def _take_call() -> None:
    today = date.today()
    if _calls["day"] != today:
        _calls["day"], _calls["n"] = today, 0
    if _calls["n"] >= _daily():
        raise Refused(429, "Today's limit for the spoken voice has been reached. The device's voice is used instead.")
    _calls["n"] += 1


def config(db: Session, user: User, stt, tts, model_ok: bool) -> dict:
    """What the browser may offer to this person right now. Booleans and numbers only."""
    if user.role != "participant":
        raise Refused(404, "Not found, or you do not have access.")
    cs = consent_state(db, user.id)
    model_consent = bool(cs["assistant_model"]["granted"])
    return {
        "enabled": enabled(),
        "stt": {"available": stt is not None and bool(user.is_demo), "consented": bool(cs["voice_recording"]["granted"])},
        "tts": {"server": tts is not None and bool(user.is_demo) and model_consent,
                "why_not": None if tts is not None and user.is_demo and model_consent else
                           "not_configured" if tts is None else "needs_consent" if user.is_demo else "real_data_stays_here"},
        "model": {"available": bool(model_ok and user.is_demo), "consented": model_consent},
        # Defaults the browser starts from; the person can change them. Silence is deliberately long: people pause to think.
        "defaults": {"silence_ms": 1800, "min_speech_ms": 350, "max_turn_s": 45, "speed": 0.9, "volume": 1.0},
        "limits": {"speak_chars": MAX_SPEAK_CHARS},
    }


def speak(db: Session, user: User, text: str, language: str, client, voice: str | None) -> bytes:
    if user.role != "participant":
        raise Refused(404, "Not found, or you do not have access.")
    if client is None:
        raise Refused(503, "The spoken voice is not set up on this server. The device's voice is used instead.")
    if not user.is_demo:
        raise Refused(403, "Your words and tasks stay on this server. The device's voice is used instead.")
    if not consent_state(db, user.id)["assistant_model"]["granted"]:
        raise Refused(403, "Sending text to the voice service needs your permission first.")
    text = (text or "").strip()
    if not text:
        raise Refused(422, "There is nothing to say.")
    if language not in ("en", "ar"):
        raise Refused(422, "Language must be en or ar.")
    _take_call()
    try:
        audio = client.speak(text[:MAX_SPEAK_CHARS], voice, language)
    except llm.ModelError as e:
        audit(db, user.id, "companion.speech_failed", user.id, client.provider)
        db.commit()
        raise Refused(502, f"The spoken voice could not be used: {e}") from None
    audit(db, user.id, "companion.spoken", user.id, client.provider)
    db.commit()
    return audio


def nlu_client(db: Session, user: User, client):
    """The model client for understanding, or None. Needs the flag, a demonstration account (synthetic data) and the person's model consent."""
    if client is None or not enabled() or user.role != "participant" or not user.is_demo:
        return None
    return client if consent_state(db, user.id).get("assistant_model", {}).get("granted") else None
