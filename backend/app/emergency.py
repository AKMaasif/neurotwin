"""Emergency access. Deliberately small, and independent of every model.

What this module does: say which emergency numbers to show for the deployment, and keep one trusted person the user chose.
What it never does: place a call, send a message, notify anyone, track that the screen was opened, or say that anything connected or that
help is coming. The phone's own dialer does the calling; NeuroTwin cannot know what happened afterwards.

The numbers are a setting the owner of the deployment verifies (NEUROTWIN_EMERGENCY_NUMBERS, NEUROTWIN_EMERGENCY_REGION,
NEUROTWIN_EMERGENCY_VERIFIED). They are not guessed from the interface language. The screen works from built-in defaults when the server
cannot be reached.
"""
from __future__ import annotations

import os
import re

from sqlalchemy.orm import Session

from .models import PatientPreference, User, now
from .services import Refused

DEFAULT_NUMBERS = [("ambulance", "998"), ("police", "999")]
_NUM = re.compile(r"^\d{3,6}$")
_PHONE = re.compile(r"^\+?[\d ]{6,20}$")


def numbers() -> list[dict]:
    raw = (os.environ.get("NEUROTWIN_EMERGENCY_NUMBERS") or "").strip()
    pairs = DEFAULT_NUMBERS
    if raw:
        parsed = []
        for part in raw.split(","):
            label, _, num = part.partition(":")
            if label.strip() in ("ambulance", "police", "fire", "general") and _NUM.match(num.strip()):
                parsed.append((label.strip(), num.strip()))
        pairs = parsed or DEFAULT_NUMBERS
    return [{"id": a, "number": b} for a, b in pairs]


def config(db: Session, user: User) -> dict:
    pref = db.get(PatientPreference, user.id) if user.role == "participant" else None
    trusted = {"name": pref.trusted_name, "phone": pref.trusted_phone} if pref and pref.trusted_phone else None
    return {"region": (os.environ.get("NEUROTWIN_EMERGENCY_REGION") or "AE").upper(), "numbers": numbers(),
            "verified": os.environ.get("NEUROTWIN_EMERGENCY_VERIFIED") == "1", "trusted": trusted}


def set_trusted(db: Session, user: User, name: str, phone: str) -> dict:
    if user.role != "participant":
        raise Refused(404, "Not found, or you do not have access.")
    name, phone = " ".join((name or "").split()), " ".join((phone or "").split())
    if not name or len(name) > 80:
        raise Refused(422, "Write the name of the person you would ring.")
    if not _PHONE.match(phone):
        raise Refused(422, "The phone number should have digits only, with an optional + at the start.")
    pref = db.get(PatientPreference, user.id)
    if pref is None:
        from . import careplan as CP
        pref = PatientPreference(user_id=user.id, timezone=CP.DEFAULT_TZ)
        db.add(pref)
    pref.trusted_name, pref.trusted_phone, pref.updated_at = name, phone, now()
    db.commit()                      # no audit entry: it would only hold the fact that a number exists, and the number itself must stay private
    return {"name": name, "phone": phone}


def clear_trusted(db: Session, user: User) -> None:
    if user.role != "participant":
        raise Refused(404, "Not found, or you do not have access.")
    pref = db.get(PatientPreference, user.id)
    if pref is not None:
        pref.trusted_name = pref.trusted_phone = None
        pref.updated_at = now()
        db.commit()
