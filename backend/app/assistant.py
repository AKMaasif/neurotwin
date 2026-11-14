"""Text assistant for the person. A fixed list of tools; the server checks and runs them.

This version understands a person's words with fixed English and Arabic patterns. It is NOT a language model, and no health data leaves the
server. A model could later propose a `{tool, arguments}` pair; it would go through the same `run` and the same checks below, and nothing in
this file lets text become a query, a URL, a recipient or code.

Rules:
- Only the tools in TOOLS exist. Anything else is "not understood".
- Navigation and reading run at once. Anything that records or changes something (done, not today, snooze) is read back to the person and runs
  only after they confirm, once, within a few minutes. Sending something to another person is never done here.
- If more than one routine could be meant, the assistant asks which. It never guesses.
- "Help" words open the emergency screen straight away. The assistant never calls anyone and never says help is coming.
- The audit log records that a tool was attempted, succeeded or failed, never the person's words.
"""
from __future__ import annotations

import re
import secrets
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import careplan as CP
from .models import AssistantAction, CarePlanItem, User, now
from .services import Refused, audit

CONFIRM_MINUTES = 5
SCREENS = {"today": "reminders", "reminders": "reminders", "messages": "messages", "record": "records", "records": "records",
           "home": "home", "urgent": "urgent", "checkin": "checkin", "reaction": "reaction"}
TOOLS = {  # name: (kind, needs confirmation)
    "open_screen": ("navigation", False), "read_today": ("read", False), "explain_instruction": ("read", False),
    "mark_done": ("change", True), "mark_not_today": ("change", True), "snooze": ("change", True),
    "start_activity": ("navigation", False), "emergency": ("navigation", False),
}

_EMERGENCY = re.compile(r"\b(emergency|urgent|ambulance|help me|i need help|i am hurt|i fell|can't breathe|cannot breathe|chest pain)\b|طوارئ|إسعاف|اسعاف|ساعدوني|ساعدني|أحتاج مساعدة|احتاج مساعدة|وقعت|ألم في الصدر", re.I)
_NOT_TODAY = re.compile(r"\b(not today|skip|won't do|will not do|can't do (it )?today)\b|ليس اليوم|مو اليوم|تخطي|تخطى|لن أفعل", re.I)
_DONE = re.compile(r"\b(i did|i have done|i've done|i finished|i have finished|i completed|done with|finished|completed|done)\b|\bتم\b|أنهيت|انتهيت|خلصت|أكملت|اكملت|فعلت|قمت ب", re.I)
_SNOOZE = re.compile(r"\b(snooze|remind me|later)\b|ذكرني|ذكّرني|لاحقا|لاحقًا", re.I)
_TODAY = re.compile(r"\b(what.*(today|to do)|my (tasks|routines|reminders)|today'?s (tasks|plan))\b|ماذا علي|مهامي|روتيني|تذكيراتي|ماذا أفعل اليوم", re.I)
_EXPLAIN = re.compile(r"\b(explain|what does .* mean|what is .* for|tell me about|why)\b|اشرح|ماذا يعني|ما معنى", re.I)
_OPEN = [(re.compile(r"\b(messages?|inbox)\b|رسائل|الرسائل", re.I), "messages"), (re.compile(r"\b(my record|records?|history)\b|سجلي|سجلّي|سجل", re.I), "records"),
         (re.compile(r"\b(reminders?|today)\b|التذكيرات|اليوم", re.I), "today"), (re.compile(r"\b(home|start)\b|الرئيسية", re.I), "home")]
_ACTIVITY = [(re.compile(r"\b(check-?in|questions|daily check)\b|الأسئلة|الاستبيان", re.I), "checkin"), (re.compile(r"\b(reaction|game|tap)\b|اللعبة|سرعة الاستجابة|التفاعل", re.I), "reaction")]
_MIN = re.compile(r"(\d{1,3})\s*(?:min|minutes?|دقيقة|دقائق)", re.I)
_HOUR = re.compile(r"(\d)\s*(?:hours?|hrs?|ساعة|ساعات)|\b(an hour|ساعة)\b", re.I)
_STOP = set("the a an my i it to do did have has done finished completed for of and is was today please skip later now not this that mark as".split())
_AR_STOP = set("تم أنا انا ال في من على إلى الى هذا هذه اليوم ليس لا ذكرني ذكّرني".split())


def _words(text: str) -> set[str]:
    toks = re.findall(r"[\w']+", (text or "").lower())
    return {t for t in toks if len(t) > 2 and t not in _STOP and t not in _AR_STOP}


_AR_MARKS = re.compile("[\u064b-\u0652\u0640]")
_AR_WEAK = re.compile("[اأإآوىيءةئؤ]")


def _skeleton(word: str) -> str | None:
    """A rough Arabic root-like form: marks, the article and weak letters removed, so "المشي" and "امشِ" meet. None for non-Arabic words.
    It can join two different words; that is why every change is read back and confirmed before it is recorded."""
    if not re.search("[\u0600-\u06ff]", word):
        return None
    w = _AR_MARKS.sub("", word)
    if w.startswith("ال") and len(w) > 4:
        w = w[2:]
    sk = _AR_WEAK.sub("", w)
    return sk if len(sk) >= 2 else None


def _match_items(text: str, rows: list[tuple[CarePlanItem, dict]]) -> list[CarePlanItem]:
    """The routine(s) the words point at: those sharing the most words with what the person said. Several tied matches are all returned."""
    said = _words(text)
    scored = []
    for item, _ in rows:
        mine = _words(" ".join(filter(None, [item.title, item.text_en, item.text_ar])))
        # a shared stem counts too, so "walked" can point at "walk"
        sk_mine = {k for k in map(_skeleton, mine) if k}
        hit = len(said & mine) + sum(1 for w in said - mine if (k := _skeleton(w)) and k in sk_mine) + sum(1 for w in said - mine if any(len(w) >= 4 and (w.startswith(m[:4]) and m[:4] == w[:4]) for m in mine))
        if hit:
            scored.append((hit, item))
    if not scored:
        return []
    best = max(h for h, _ in scored)
    return [i for h, i in scored if h == best]


def parse(text: str, rows: list[tuple[CarePlanItem, dict]]) -> dict:
    """Words to `{tool, arguments}` or a question back. Order matters: help first, then changes, then reading, then navigation."""
    t = (text or "").strip()
    if not t:
        return {"tool": None, "reason": "empty"}
    if _EMERGENCY.search(t):
        return {"tool": "emergency", "arguments": {}}
    change = "mark_not_today" if _NOT_TODAY.search(t) else "snooze" if _SNOOZE.search(t) else "mark_done" if _DONE.search(t) else None
    if change:
        if not rows:
            return {"tool": None, "reason": "no_tasks"}
        matches = _match_items(t, rows)
        if len(matches) == 1:
            args: dict = {"item_id": matches[0].id}
        elif len(rows) == 1 and not matches:
            args = {"item_id": rows[0][0].id}
        else:
            return {"tool": None, "reason": "which", "choices": [i.id for i in (matches or [r[0] for r in rows])]}
        if change == "snooze":
            m, h = _MIN.search(t), _HOUR.search(t)
            minutes = int(m.group(1)) if m else 60 if h else 30
            if minutes not in CP.SNOOZE_MINUTES:
                return {"tool": None, "reason": "snooze_minutes"}
            args["minutes"] = minutes
        return {"tool": change, "arguments": args}
    if _TODAY.search(t):
        return {"tool": "read_today", "arguments": {}}
    if _EXPLAIN.search(t):
        matches = _match_items(t, rows)
        if len(matches) == 1:
            return {"tool": "explain_instruction", "arguments": {"item_id": matches[0].id}}
        return {"tool": None, "reason": "which", "choices": [i.id for i in (matches or [r[0] for r in rows])]}
    if len(t.split()) > 6:       # a long, mixed sentence is not a plain request to open something; ask again rather than act
        return {"tool": None, "reason": "not_understood"}
    for rx, name in _ACTIVITY:
        if rx.search(t):
            return {"tool": "start_activity", "arguments": {"activity": name}}
    for rx, name in _OPEN:
        if rx.search(t):
            return {"tool": "open_screen", "arguments": {"screen": name}}
    return {"tool": None, "reason": "not_understood"}


def _out(db: Session, i: CarePlanItem) -> dict:
    return {"id": i.id, "title": i.title, "text_en": i.text_en, "text_ar": i.text_ar, "time_hhmm": i.time_hhmm, "day_part": i.day_part,
            "quantity": i.quantity, "unit": i.unit, "precautions": i.precautions, "written_by": CP._name(db, i.created_by)}


def message(db: Session, user: User, text: str) -> dict:
    """Understand one message. Reads and navigation are answered now; a change is returned as a proposal with a confirmation id."""
    if user.role != "participant":
        raise Refused(404, "Not found, or you do not have access.")
    d = CP.local_today(db, user)
    rows = CP.todays(db, user, d)
    p = parse(text, rows)
    tool = p.get("tool")
    if tool is None:
        audit(db, user.id, "assistant.not_understood", user.id, None)
        db.commit()
        choices = [_out(db, db.get(CarePlanItem, i)) for i in p.get("choices", [])]
        return {"understood": False, "reason": p["reason"], "choices": choices}
    args = p["arguments"]
    audit(db, user.id, f"assistant.{tool}.attempted", user.id, None)
    if TOOLS[tool][1]:
        item = db.get(CarePlanItem, args["item_id"])
        act = AssistantAction(id=secrets.token_hex(16), user_id=user.id, tool=tool, args={**args, "day": d.isoformat()}, expires_at=now() + timedelta(minutes=CONFIRM_MINUTES))
        db.add(act)
        db.commit()
        return {"understood": True, "tool": tool, "needs_confirmation": True, "confirmation_id": act.id, "item": _out(db, item),
                "minutes": args.get("minutes"), "expires_minutes": CONFIRM_MINUTES}
    db.commit()
    return {"understood": True, "tool": tool, "needs_confirmation": False, **_run_safe(db, user, tool, args, rows)}


def _run_safe(db: Session, user: User, tool: str, args: dict, rows: list) -> dict:
    if tool == "emergency":
        return {"navigate": "urgent"}
    if tool == "open_screen":
        return {"navigate": SCREENS[args["screen"]]}
    if tool == "start_activity":
        return {"navigate": SCREENS[args["activity"]]}
    if tool == "read_today":
        return {"items": [{**_out(db, i), "reply": st["reply"], "snoozed_until": CP._iso(st["snoozed_until"])} for i, st in rows], "navigate": None}
    if tool == "explain_instruction":
        i = db.get(CarePlanItem, args["item_id"])
        if i is None or i.participant_id != user.id:
            raise Refused(404, "Not found, or you do not have access.")
        return {"item": _out(db, i), "navigate": None}
    raise Refused(422, "Unknown action.")


def confirm(db: Session, user: User, action_id: str) -> dict:
    """Run a proposed change once. Same id twice returns the first result; another person's id, an expired id or a used-up id is refused."""
    act = db.get(AssistantAction, action_id)
    if act is None or act.user_id != user.id or user.role != "participant":
        raise Refused(404, "Not found, or you do not have access.")
    if act.used_at is not None:
        return {"ok": act.outcome == "succeeded", "duplicate": True, "tool": act.tool}
    exp = act.expires_at if act.expires_at.tzinfo else act.expires_at.replace(tzinfo=now().tzinfo)
    if exp < now():
        raise Refused(410, "That took too long, so nothing was recorded. Please ask again.")
    item = db.get(CarePlanItem, act.args["item_id"])
    act.used_at = now()
    try:
        if item is None:
            raise Refused(404, "Not found, or you do not have access.")
        from datetime import date
        day = date.fromisoformat(act.args["day"])
        if act.tool == "snooze":
            CP.reply(db, user, item, day, "snooze", idem_key=f"asst-{act.id}", snooze_minutes=act.args["minutes"])
        else:
            CP.reply(db, user, item, day, "done" if act.tool == "mark_done" else "not_today", idem_key=f"asst-{act.id}")
        act.outcome = "succeeded"
    except Refused:
        db.rollback()
        act = db.get(AssistantAction, action_id)
        act.used_at, act.outcome = now(), "failed"
        audit(db, user.id, f"assistant.{act.tool}.failed", user.id, None)
        db.commit()
        raise
    audit(db, user.id, f"assistant.{act.tool}.succeeded", user.id, None)
    db.commit()
    return {"ok": True, "duplicate": False, "tool": act.tool}
