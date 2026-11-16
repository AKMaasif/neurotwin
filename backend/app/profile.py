"""The person's background that changes how results read: highest education and first language.

Asked once, optional, changed or cleared by the person at any time. A clinician with a clinical-review grant sees it
next to the person's results. It is never used to score, adjust or compare results automatically: no normative
adjustment exists yet, so it is context for the clinician only."""
from __future__ import annotations

from sqlalchemy.orm import Session

from .models import PatientPreference, User, now
from .services import Refused, audit

EDUCATION = ("none", "primary", "secondary", "diploma", "university", "postgraduate")
LANGUAGES = ("arabic", "english", "hindi_urdu", "malayalam", "tagalog", "persian", "other")


def get(db: Session, person_id: str) -> dict:
    pref = db.get(PatientPreference, person_id)
    return {"education": pref.education if pref else None, "first_language": pref.first_language if pref else None}


def put(db: Session, user: User, education: str | None, first_language: str | None) -> dict:
    if user.role != "participant":
        raise Refused(404, "Not found, or you do not have access.")
    if education is not None and education not in EDUCATION:
        raise Refused(422, f"Unknown education level: {education}.")
    if first_language is not None and first_language not in LANGUAGES:
        raise Refused(422, f"Unknown language: {first_language}.")
    pref = db.get(PatientPreference, user.id)
    if pref is None:
        from . import careplan as CP
        pref = PatientPreference(user_id=user.id, timezone=CP.DEFAULT_TZ)
        db.add(pref)
    pref.education, pref.first_language, pref.updated_at = education, first_language, now()
    audit(db, user.id, "profile.background", user.id, None)   # the fact that it changed, never the answers
    db.commit()
    return get(db, user.id)


# ---- The person's own daily routine ---------------------------------------------------------------------------------------------------
# Saved by the person from an assistant draft. It is their list, not the clinician's care plan: no reminders are scored, nothing is sent to
# anyone, and it is never evidence. The person can replace or remove it at any time.
ROUTINE_MAX = 12


def get_routine(db: Session, person_id: str) -> dict:
    pref = db.get(PatientPreference, person_id)
    r = pref.own_routine if pref and pref.own_routine else None
    return {"items": list(r.get("items", [])) if r else [], "saved_at": r.get("saved_at") if r else None}


def put_routine(db: Session, user: User, items: list[dict]) -> dict:
    import re
    if user.role != "participant":
        raise Refused(404, "Not found, or you do not have access.")
    clean = []
    for it in items[:ROUTINE_MAX]:
        tm, act = str(it.get("time") or "").strip(), " ".join(str(it.get("activity") or "").split())
        m = re.fullmatch(r"([01]?\d|2[0-3])[:.]([0-5]\d)", tm)
        if not m or not act:
            raise Refused(422, "Each item needs a time (HH:MM) and an activity.")
        clean.append({"time": f"{int(m.group(1)):02d}:{m.group(2)}", "activity": act[:90]})
    if not clean:
        raise Refused(422, "The routine is empty.")
    clean.sort(key=lambda x: x["time"])
    pref = db.get(PatientPreference, user.id)
    if pref is None:
        from . import careplan as CP
        pref = PatientPreference(user_id=user.id, timezone=CP.DEFAULT_TZ)
        db.add(pref)
    pref.own_routine, pref.updated_at = {"items": clean, "saved_at": now().isoformat()}, now()
    audit(db, user.id, "routine.saved", user.id, None)      # that it was saved, never the activities
    db.commit()
    return get_routine(db, user.id)


def clear_routine(db: Session, user: User) -> dict:
    if user.role != "participant":
        raise Refused(404, "Not found, or you do not have access.")
    pref = db.get(PatientPreference, user.id)
    if pref is not None and pref.own_routine:
        pref.own_routine, pref.updated_at = None, now()
        audit(db, user.id, "routine.removed", user.id, None)
        db.commit()
    return get_routine(db, user.id)
