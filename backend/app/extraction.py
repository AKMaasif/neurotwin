"""Suggested structured fields from a clinician's routine text, checked by rules.

This is NOT a model. It reads the clinician's own sentence with fixed patterns and proposes fields; then `check` decides, by rules, whether
each proposed field is safe to show. A model may later propose fields too; whatever proposes them, the same checks apply, and the clinician
must still approve by saving the routine. Rules:

- Every number in a field must appear in the source text.
- A unit is accepted only if it appears in the text next to its number. A unit is never inferred, converted or guessed.
- A missing time, frequency or unit is reported as "needs the clinician", never filled with a default.
- Nothing is added that the text does not say: no amount, duration, medication or precaution.
"""
from __future__ import annotations

import re

UNITS = ("minutes", "minute", "min", "hours", "hour", "hr", "glasses", "glass", "cups", "cup", "steps", "times", "tablet", "tablets",
         "mg", "ml", "g", "mcg", "drops", "drop", "puffs", "puff", "units", "sessions", "session", "km", "meters", "metres")
_NUM = r"(\d+(?:[.,]\d+)?)"
_QTY = re.compile(rf"\b{_NUM}\s*({'|'.join(sorted(UNITS, key=len, reverse=True))})\b", re.I)
_BARE_NUM = re.compile(rf"\b{_NUM}\b")
_TIME = re.compile(r"\b(?:at\s+)?([01]?\d|2[0-3]):([0-5]\d)\b")
_AMPM = re.compile(r"\b(?:at\s+)?(1[0-2]|0?[1-9])\s*(am|pm)\b", re.I)
_DAYS = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6}
_PARTS = {"morning": "morning", "afternoon": "afternoon", "evening": "evening", "night": "evening", "breakfast": "morning", "lunch": "afternoon", "dinner": "evening"}


def _num(s: str) -> float:
    return float(s.replace(",", "."))


def propose(text: str) -> dict:
    """Fields read directly from the sentence. Anything not stated is left None."""
    t = (text or "").strip()
    out: dict = {"day_part": None, "weekdays": [], "time_hhmm": None, "quantity": None, "unit": None}
    low = t.lower()
    m = _TIME.search(t)
    if m:
        out["time_hhmm"] = f"{int(m.group(1)):02d}:{m.group(2)}"
    else:
        m = _AMPM.search(t)
        if m:
            h = int(m.group(1)) % 12 + (12 if m.group(2).lower() == "pm" else 0)
            out["time_hhmm"] = f"{h:02d}:00"
    q = _QTY.search(t)
    if q:
        out["quantity"], out["unit"] = _num(q.group(1)), q.group(2).lower()
    for part, val in _PARTS.items():
        if re.search(rf"\b{part}\b", low):
            out["day_part"] = val
            break
    out["weekdays"] = sorted({d for name, d in _DAYS.items() if re.search(rf"\b{name}s?\b", low)})
    return out


def check(source_text: str, fields: dict) -> list[dict]:
    """Flags for a set of proposed fields. Each flag: {field, code, message}. An empty list means no rule objects, which is not approval."""
    src = source_text or ""
    flags: list[dict] = []

    def flag(field: str, code: str, msg: str) -> None:
        flags.append({"field": field, "code": code, "message": msg})

    nums = {_num(n) for n in _BARE_NUM.findall(src)}
    qty, unit = fields.get("quantity"), fields.get("unit")
    if qty is not None and qty not in nums:
        flag("quantity", "number_not_in_text", "This number does not appear in the instruction.")
    if unit:
        found = [m for m in _QTY.finditer(src) if m.group(2).lower() == str(unit).lower() and (qty is None or _num(m.group(1)) == qty)]
        if not found:
            flag("unit", "unit_not_in_text", "This unit does not appear next to that number in the instruction. Units are never guessed.")
    if (qty is None) != (unit is None):
        flag("unit" if qty is not None else "quantity", "quantity_unit_pair", "A quantity needs its unit and a unit needs its quantity.")
    if qty is None and nums and not fields.get("time_hhmm") and not _TIME.search(src) and not _AMPM.search(src):
        flag("quantity", "number_without_unit", "The instruction contains a number but no unit was found. The clinician should confirm what it means.")
    if not fields.get("time_hhmm") and not fields.get("day_part"):
        flag("time_hhmm", "needs_clinician", "No time or part of the day is stated. The clinician needs to choose one.")
    if not fields.get("weekdays"):
        flag("weekdays", "needs_clinician", "No days are stated. Leaving it empty means every day. The clinician should confirm.")
    t = fields.get("time_hhmm")
    if t and not _TIME.search(src) and not _AMPM.search(src):
        flag("time_hhmm", "time_not_in_text", "This time does not appear in the instruction.")
    return flags
