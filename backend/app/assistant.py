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

Conversation memory (so it can follow a conversation the way a person would):
- The conversation is kept in `assistant_messages`: separate from clinical evidence and care messages, visible only to the person, never given
  to a model, a clinician or family. The person can clear it or switch it off at any time, and old messages are pruned.
- What a follow-up refers to ("it", "the other one", "the first", "yes", "again", "and the water?") is read from the last few minutes of that
  conversation. A topic goes stale after CONTEXT_MINUTES, and after that the assistant asks rather than assumes.
- Memory never lets a change run without the person's own confirmation: "yes" confirms only the one proposal waiting right now.
"""
from __future__ import annotations

import re
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import careplan as CP
from .models import AssistantAction, AssistantMessage, CarePlanItem, PatientPreference, User, now
from .services import Refused, audit

CONFIRM_MINUTES = 5
CONTEXT_MINUTES = 30      # how long a topic stays "the thing we were talking about"
KEEP_DAYS = 30
KEEP_MESSAGES = 200
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
_YES = re.compile(r"^\s*(yes|yeah|yep|ok|okay|sure|please do|do it|go ahead|confirm|that'?s right|correct|right)\b[\s.!]*$|^\s*(نعم|ايوه|أيوه|اي|أجل|تمام|موافق|نفذ|نفّذ|اكيد|أكيد)[\s.!]*$", re.I)
_NO = re.compile(r"^\s*(no|nope|cancel|stop|don'?t|never mind|nevermind|not now|wrong)\b[\s.!]*$|^\s*(لا|الغ|ألغ|إلغاء|الغي|ألغي|توقف|ليس الآن)[\s.!]*$", re.I)
_GREET = re.compile(r"^\s*(hi|hello|hey|good (morning|afternoon|evening)|salam)\b|^\s*(مرحبا|مرحباً|أهلا|اهلا|السلام عليكم|صباح الخير|مساء الخير)", re.I)
_THANKS = re.compile(r"\b(thanks|thank you|cheers)\b|شكرا|شكراً|يعطيك العافية", re.I)
_CAPS = re.compile(r"\b(what can you do|what do you do|how do you work|how can you help|what can i (say|ask))\b|ماذا يمكنك|ماذا تستطيع|كيف تعمل|ماذا أقول", re.I)
_RECALL_SAID = re.compile(r"\b(what did i (just )?(say|ask)|what was my (last|previous) (question|message))\b|ماذا قلت|ماذا سألت", re.I)
_RECAP = re.compile(r"\b(what did i (just )?(mark|do|record|change)|what have i (marked|done)( today)?|what did you (just )?(do|record))\b|ماذا سجلت|ماذا حددت|ماذا فعلت", re.I)
_DETAIL = re.compile(r"\b(what time|when|how (much|many|long)|why|who (wrote|gave|sent)|tell me more|more details?|what is it|details)\b|متى|كم|لماذا|من كتب|المزيد|تفاصيل", re.I)
_PRONOUN = re.compile(r"\b(it|that|this|that one|this one|the same|same|again|too)\b|ذلك|هذا|هذه|نفسه|نفس الشيء|مرة أخرى|أيضا|أيضاً", re.I)
_OTHER = re.compile(r"\b(the other( one)?|another( one)?|the second one)\b|الآخر|الاخر|الثاني|الثانية", re.I)
_ELLIPSIS = re.compile(r"^\s*(and|what about|how about|also|then|same for|do the same for)\b|^\s*(وماذا عن|وماذا|وكذلك|و)", re.I)
_ORD = [(re.compile(r"\b(first|1st)\b|الأول|الاول|الأولى|الاولى", re.I), 0), (re.compile(r"\b(second|2nd)\b|الثاني|الثانية", re.I), 1),
        (re.compile(r"\b(third|3rd)\b|الثالث|الثالثة", re.I), 2), (re.compile(r"\b(fourth|4th)\b|الرابع|الرابعة", re.I), 3)]
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


CHANGES = ("mark_done", "mark_not_today", "snooze")


def _minutes_from(t: str) -> int | None:
    m, h = _MIN.search(t), _HOUR.search(t)
    if m:
        return int(m.group(1))
    if h:
        return 60 * (int(h.group(1)) if h.group(1) else 1)
    if re.search(r"half an hour|نصف ساعة", t, re.I):
        return 30
    return None


def _resolve_item(text: str, rows: list, ctx: dict, restrict: list[int] | None = None) -> tuple[int | None, str | None, list[int]]:
    """Which routine is meant: by its words, then by "first/second", "the other one", or "it" (the one we were just talking about).
    Returns (item id or None, how it was found, tied ids). Several ties are returned, never picked between."""
    pool = [r for r in rows if restrict is None or r[0].id in restrict]
    ids = [r[0].id for r in pool]
    matches = _match_items(text, pool)
    if len(matches) == 1:
        return matches[0].id, "words", []
    if len(matches) > 1:
        return None, None, [m.id for m in matches]
    for rx, idx in _ORD:
        if rx.search(text) and idx < len(ids):
            return ids[idx], "order", []
    last = ctx.get("last_item")
    if _OTHER.search(text) and last in ids and len(ids) == 2:
        return next(i for i in ids if i != last), "other", []
    if _PRONOUN.search(text) and last in ids:
        return last, "context", []
    return None, None, ids


def parse(text: str, rows: list[tuple[CarePlanItem, dict]], ctx: dict | None = None) -> dict:
    """Words (and what was just said) to `{tool, arguments}`, a question back, or a yes/no for the proposal that is waiting.
    Order: help first, then an answer to a question just asked, then changes, reading, small talk, navigation."""
    ctx = ctx or {}
    pend = ctx.get("pending") or {}
    t = (text or "").strip()
    if not t:
        return {"tool": None, "reason": "empty"}
    if _EMERGENCY.search(t):
        return {"tool": "emergency", "arguments": {}}
    if _YES.match(t) or _NO.match(t):
        yes = bool(_YES.match(t))
        return {"special": "yes" if yes else "no", "pending": pend.get("kind")}
    # an answer to "which one?"
    if pend.get("kind") == "which":
        iid, via, tied = _resolve_item(t, rows, ctx, restrict=pend.get("choices"))
        if iid:
            return {"tool": pend["tool"], "arguments": {**pend.get("args", {}), "item_id": iid}, "via": "answer"}
    # an answer to "how long?"
    if pend.get("kind") == "minutes":
        n = _minutes_from(t) or (int(t) if t.isdigit() else None)
        if n in CP.SNOOZE_MINUTES:
            return {"tool": "snooze", "arguments": {"item_id": pend["item_id"], "minutes": n}, "via": "answer"}
        if n is not None or re.fullmatch(r"\d{1,3}", t):
            return {"tool": None, "reason": "snooze_minutes", "keep": pend}
    change = "mark_not_today" if _NOT_TODAY.search(t) else "snooze" if _SNOOZE.search(t) else "mark_done" if _DONE.search(t) else None
    last_tool = ctx.get("last_tool")
    if not change and last_tool in CHANGES and re.search(r"\b(again|same|the same)\b|نفس|مرة أخرى", t, re.I):
        change = last_tool                                    # "do the same again"
    if not change and last_tool in CHANGES + ("explain_instruction",) and _ELLIPSIS.match(t) and _match_items(t, rows):
        change = last_tool if last_tool in CHANGES else None   # "and the water?"
        if change is None:
            iid, via, tied = _resolve_item(t, rows, ctx)
            if iid:
                return {"tool": "explain_instruction", "arguments": {"item_id": iid}, "via": via}
    if change:
        if not rows:
            return {"tool": None, "reason": "no_tasks"}
        iid, via, tied = _resolve_item(t, rows, ctx)
        if iid is None and len(rows) == 1:
            iid, via = rows[0][0].id, "only"
        if iid is None:
            return {"tool": None, "reason": "which", "choices": tied or [r[0].id for r in rows], "pending": {"kind": "which", "tool": change,
                    "args": {k: v for k, v in {"minutes": _minutes_from(t)}.items() if v} if change == "snooze" else {}}}
        args: dict = {"item_id": iid}
        if change == "snooze":
            n = _minutes_from(t)
            explicit = n is not None
            n = n if explicit else (ctx.get("last_args", {}).get("minutes") if _PRONOUN.search(t) and last_tool == "snooze" else 30)
            if n not in CP.SNOOZE_MINUTES:
                return {"tool": None, "reason": "snooze_minutes", "keep": {"kind": "minutes", "item_id": iid}}
            args["minutes"] = n
        return {"tool": change, "arguments": args, "via": via}
    if _RECALL_SAID.search(t):
        return {"tool": "recall", "arguments": {}}
    if _RECAP.search(t):
        return {"tool": "recap", "arguments": {}}
    if _TODAY.search(t):
        return {"tool": "read_today", "arguments": {}}
    if _CAPS.search(t):
        return {"tool": "chat", "arguments": {"kind": "capabilities"}}
    if _THANKS.search(t) and len(t.split()) <= 6:
        return {"tool": "chat", "arguments": {"kind": "thanks"}}
    if _GREET.match(t) and len(t.split()) <= 5:
        return {"tool": "chat", "arguments": {"kind": "greeting"}}
    if _DETAIL.search(t) or _EXPLAIN.search(t):
        iid, via, tied = _resolve_item(t, rows, ctx)
        if iid is None and ctx.get("last_item") in [r[0].id for r in rows] and len(t.split()) <= 6:
            iid, via = ctx["last_item"], "context"        # "when is it?", "tell me more"
        if iid is None and len(rows) == 1:
            iid, via = rows[0][0].id, "only"
        if iid:
            return {"tool": "explain_instruction", "arguments": {"item_id": iid}, "via": via}
        return {"tool": None, "reason": "which", "choices": tied or [r[0].id for r in rows], "pending": {"kind": "which", "tool": "explain_instruction", "args": {}}}
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


# ---- the conversation memory ----------------------------------------------------------------------------------------

def memory_on(db: Session, user: User) -> bool:
    pref = db.get(PatientPreference, user.id)
    return True if pref is None else bool(pref.assistant_memory)


def set_memory(db: Session, user: User, enabled: bool) -> bool:
    pref = db.get(PatientPreference, user.id)
    if pref is None:
        pref = PatientPreference(user_id=user.id, timezone=CP.DEFAULT_TZ)
        db.add(pref)
    pref.assistant_memory, pref.updated_at = enabled, now()
    if not enabled:
        for m in db.scalars(select(AssistantMessage).where(AssistantMessage.user_id == user.id)):
            db.delete(m)
    audit(db, user.id, "assistant.memory_on" if enabled else "assistant.memory_off", user.id, None)
    db.commit()
    return enabled


def clear(db: Session, user: User) -> int:
    rows = list(db.scalars(select(AssistantMessage).where(AssistantMessage.user_id == user.id)))
    for m in rows:
        db.delete(m)
    for a in db.scalars(select(AssistantAction).where(AssistantAction.user_id == user.id, AssistantAction.used_at.is_(None))):
        a.used_at, a.outcome = now(), "cancelled"             # forgetting the conversation also drops any proposal waiting for a yes
    audit(db, user.id, "assistant.cleared", user.id, None)
    db.commit()
    return len(rows)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _context(db: Session, user: User) -> dict:
    """What the last few minutes of conversation point at. Empty when memory is off or the topic has gone stale."""
    if not memory_on(db, user):
        return {}
    last = db.scalar(select(AssistantMessage).where(AssistantMessage.user_id == user.id, AssistantMessage.who == "bot").order_by(AssistantMessage.id.desc()).limit(1))
    if last is None or not last.ctx or _aware(last.created_at) < now() - timedelta(minutes=CONTEXT_MINUTES):
        return {}
    return dict(last.ctx)


def _remember(db: Session, user: User, said: str | None, payload: dict, ctx: dict) -> None:
    if not memory_on(db, user):
        return
    if said is not None:
        db.add(AssistantMessage(user_id=user.id, who="you", text=said[:300]))
    db.add(AssistantMessage(user_id=user.id, who="bot", payload=payload, ctx=ctx))
    db.flush()
    cutoff = now() - timedelta(days=KEEP_DAYS)
    rows = list(db.scalars(select(AssistantMessage).where(AssistantMessage.user_id == user.id).order_by(AssistantMessage.id.desc())))
    for m in rows[KEEP_MESSAGES:] + [m for m in rows[:KEEP_MESSAGES] if _aware(m.created_at) < cutoff]:
        db.delete(m)


def history(db: Session, user: User, limit: int = 60) -> dict:
    if user.role != "participant":
        raise Refused(404, "Not found, or you do not have access.")
    on = memory_on(db, user)
    rows = list(db.scalars(select(AssistantMessage).where(AssistantMessage.user_id == user.id).order_by(AssistantMessage.id.desc()).limit(limit)))[::-1] if on else []
    out = []
    for m in rows:
        payload = m.payload
        if payload and payload.get("confirmation_id"):
            act = db.get(AssistantAction, payload["confirmation_id"])
            live = act is not None and act.used_at is None and _aware(act.expires_at) >= now()
            payload = {**payload, "pending": live}
        out.append({"id": m.id, "who": m.who, "text": m.text, "payload": payload, "at": CP._iso(m.created_at)})
    return {"memory": on, "messages": out, "keeps_days": KEEP_DAYS}


def _cancel_waiting(db: Session, user: User, except_id: str | None = None) -> None:
    for a in db.scalars(select(AssistantAction).where(AssistantAction.user_id == user.id, AssistantAction.used_at.is_(None))):
        if a.id != except_id:
            a.used_at, a.outcome = now(), "cancelled"


def message(db: Session, user: User, text: str) -> dict:
    """Understand one message, using the last few minutes of conversation. Reads and navigation are answered now; a change is returned as a
    proposal with a confirmation id (a typed or spoken "yes" confirms only that one proposal)."""
    if user.role != "participant":
        raise Refused(404, "Not found, or you do not have access.")
    d = CP.local_today(db, user)
    rows = CP.todays(db, user, d)
    ctx = _context(db, user)
    prev_said = None
    if memory_on(db, user):       # the last thing they really asked: not a bare yes/no and not this kind of question itself
        for said in db.scalars(select(AssistantMessage.text).where(AssistantMessage.user_id == user.id, AssistantMessage.who == "you").order_by(AssistantMessage.id.desc()).limit(10)):
            if said and not _YES.match(said) and not _NO.match(said) and not _RECALL_SAID.search(said):
                prev_said = said
                break
    p = parse(text, rows, ctx)
    new = {"last_item": ctx.get("last_item"), "last_tool": ctx.get("last_tool"), "last_args": ctx.get("last_args"), "pending": None}

    def finish(out: dict, **upd) -> dict:
        new.update(upd)
        _remember(db, user, text.strip() or None, out, new)
        db.commit()
        return out

    if "special" in p:
        pend = ctx.get("pending") or {}
        if pend.get("kind") == "confirm":
            if p["special"] == "yes":
                r = confirm(db, user, pend["id"], _record=False)
                act = db.get(AssistantAction, pend["id"])
                item = db.get(CarePlanItem, act.args["item_id"])
                return finish({"understood": True, "tool": act.tool, "confirmed": True, "ok": r["ok"], "duplicate": r["duplicate"], "item": _out(db, item), "via": "yes"},
                              last_item=item.id, last_tool=act.tool, last_args={"minutes": act.args.get("minutes")})
            act = db.get(AssistantAction, pend["id"])
            if act is not None and act.used_at is None:
                act.used_at, act.outcome = now(), "cancelled"
            item = db.get(CarePlanItem, act.args["item_id"]) if act else None
            return finish({"understood": True, "tool": act.tool if act else None, "cancelled": True, "item": _out(db, item) if item else None},
                          last_item=item.id if item else None)
        if pend.get("kind") in ("which", "minutes") and p["special"] == "no":
            return finish({"understood": True, "tool": None, "cancelled": True, "item": None})
        audit(db, user.id, "assistant.not_understood", user.id, None)
        return finish({"understood": False, "reason": "nothing_pending", "choices": []})
    tool = p.get("tool")
    if tool is None:
        audit(db, user.id, "assistant.not_understood", user.id, None)
        keep = p.get("keep") or p.get("pending")
        choices = [_out(db, db.get(CarePlanItem, i)) for i in p.get("choices", [])]
        return finish({"understood": False, "reason": p["reason"], "choices": choices}, pending=keep)
    args = p["arguments"]
    audit(db, user.id, f"assistant.{tool}.attempted", user.id, None)
    via = p.get("via")
    if TOOLS.get(tool, ("", False))[1]:
        item = db.get(CarePlanItem, args["item_id"])
        _cancel_waiting(db, user)
        act = AssistantAction(id=secrets.token_hex(16), user_id=user.id, tool=tool, args={**args, "day": d.isoformat()}, expires_at=now() + timedelta(minutes=CONFIRM_MINUTES))
        db.add(act)
        now_state = next((st["reply"] for i, st in rows if i.id == item.id), None)
        same = {"mark_done": "done", "mark_not_today": "not_today"}.get(tool)
        out = {"understood": True, "tool": tool, "needs_confirmation": True, "confirmation_id": act.id, "item": _out(db, item),
               "minutes": args.get("minutes"), "expires_minutes": CONFIRM_MINUTES, "via": via,
               "already": now_state if same and now_state == same else None}   # "you already marked this done today"
        return finish(out, last_item=item.id, last_tool=tool, last_args={"minutes": args.get("minutes")}, pending={"kind": "confirm", "id": act.id})
    if tool == "recall":
        return finish({"understood": True, "tool": "recall", "needs_confirmation": False, "said": prev_said})
    if tool == "recap":
        done = [{"item": _out(db, i), "reply": st["reply"]} for i, st in rows if st["reply"]]
        return finish({"understood": True, "tool": "recap", "needs_confirmation": False, "entries": done})
    if tool == "chat":
        return finish({"understood": True, "tool": "chat", "needs_confirmation": False, "kind": args["kind"]})
    res = _run_safe(db, user, tool, args, rows)
    out = {"understood": True, "tool": tool, "needs_confirmation": False, "via": via, **res}
    focus = res.get("item", {}).get("id") if isinstance(res.get("item"), dict) else (rows[0][0].id if tool == "read_today" and len(rows) == 1 else ctx.get("last_item"))
    return finish(out, last_item=focus, last_tool=tool)


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


def cancel(db: Session, user: User, action_id: str) -> dict:
    """The person said no to a proposal (tapped No). It can no longer be confirmed, by tap or by a typed yes."""
    act = db.get(AssistantAction, action_id)
    if act is None or act.user_id != user.id or user.role != "participant":
        raise Refused(404, "Not found, or you do not have access.")
    if act.used_at is None:
        act.used_at, act.outcome = now(), "cancelled"
    item = db.get(CarePlanItem, act.args["item_id"])
    _remember(db, user, None, {"understood": True, "tool": act.tool, "cancelled": True, "item": _out(db, item)},
              {"last_item": item.id, "last_tool": act.tool, "last_args": {"minutes": act.args.get("minutes")}, "pending": None})
    db.commit()
    return {"ok": True}


def confirm(db: Session, user: User, action_id: str, _record: bool = True) -> dict:
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
    if _record:
        _remember(db, user, None, {"understood": True, "tool": act.tool, "confirmed": True, "ok": True, "item": _out(db, item)},
                  {"last_item": item.id, "last_tool": act.tool, "last_args": {"minutes": act.args.get("minutes")}, "pending": None})
    db.commit()
    return {"ok": True, "duplicate": False, "tool": act.tool}
