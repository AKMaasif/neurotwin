"""Six months of synthetic activity history for the demonstration accounts.

Everything produced here is invented to exercise the screens, the quality rules and the charts. It has no clinical meaning and
no person behind it. It is separate from the OASIS imaging cases.

How it stays reproducible and safe to re-run:
- The content of any one day is a pure function of (seed, participant, date). Nothing depends on random state, on the order of
  generation or on when the code runs, so the same seed always gives the same history.
- A re-run adds only what is missing. Each session carries a fixed device tag and each routine reply a fixed idempotency key; both are
  looked up before anything is written. Running it twice, or on a database that already holds the data, changes nothing.
- It never resets or removes anything. Records the demo seed already created are left alone, and no synthetic session is written
  on a day that already has a session of the same activity from another source.
- Every record is tagged: sessions use the device `synthetic-history/1`, evidence uses that producer and version, so the data can be
  told apart (and filtered) at any time. The clinician workspace shows the dataset label "Synthetic demonstration".

What it deliberately does not do: it writes no score, no composite, no interpretation, and no "decline" or "improvement" story. The
patterns (a few weeks of shorter sleep with slower responses, a gap with no records, assisted and interrupted sessions) exist so that
the charts have something honest to show, including missing and doubtful records. A gap is only a gap: no answer is never stored as a
miss.

Run:  python -m app.synthetic_history [--seed N] [--ref-date YYYY-MM-DD] [--tz Asia/Dubai] [--days 182]
or set NEUROTWIN_SEED_HISTORY=1 and start the server (the demo accounts must exist).
"""
from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import quality as Q
from .models import AccessGrant, ActivitySession, ConsentEvent, CarePlan, CarePlanItem, CarePlanReply, Evidence, ReviewItem, User

DATASET_ID = "synthetic-history"
VERSION = "1"
LABEL = "Synthetic demonstration"
DEVICE = f"{DATASET_ID}/{VERSION}"
PRODUCER = f"{DATASET_ID}/{VERSION}"
DEFAULT_SEED = 20260101
DEFAULT_TZ = "Asia/Dubai"
DEFAULT_DAYS = 182
REVIEW_OPEN_DAYS = 14        # items older than this are shown as already reviewed, so the queue looks like a real one
PEOPLE = ("demo-fatima", "demo-yousef")


def dataset_info() -> dict:
    return {"id": DATASET_ID, "version": VERSION, "label": LABEL,
            "note": "Invented records for demonstration. Not real people, not clinical data."}


def _rng(seed: int, *parts) -> random.Random:
    """A generator that depends only on its inputs, so one day's values never depend on any other day's."""
    h = hashlib.sha256(":".join(str(p) for p in (seed, *parts)).encode()).hexdigest()
    return random.Random(int(h[:16], 16))


@dataclass
class Profile:
    """The shape of one person's synthetic history. Days are counted back from the reference date."""
    pid: str
    language: str
    rt_base: float
    rt_sd: float
    checkin_rate: float
    rt_rate: float
    quiet_days: tuple[int, int] | None = None     # a stretch with no records at all (days before the reference)
    poor_sleep: tuple[int, int] | None = None     # a stretch of shorter sleep and slower responses (days before the reference)
    who5_every: int = 14
    helper_note: str = "A relative held the tablet"


PROFILES = {
    "demo-fatima": Profile("demo-fatima", "ar", 612, 26, 0.86, 3 / 7, quiet_days=(120, 108), poor_sleep=(58, 36)),
    "demo-yousef": Profile("demo-yousef", "en", 548, 22, 0.62, 2 / 7, quiet_days=(75, 61)),
}


def _in(span: tuple[int, int] | None, back: int) -> bool:
    return span is not None and span[1] <= back <= span[0]


def plan_day(seed: int, p: Profile, day: date, back: int) -> list[dict]:
    """The sessions a person has on one day, each with its observations. Pure: same inputs, same output."""
    if _in(p.quiet_days, back):
        return []
    out: list[dict] = []
    r = _rng(seed, p.pid, day.isoformat())
    poor = _in(p.poor_sleep, back)
    drift = 6 * (1 - back / 182)                               # a slight overall practice effect, in ms; not a trend claim

    if r.random() < p.checkin_rate:
        hours = round(min(12.0, max(2.0, r.gauss(5.2 if poor else 7.0, 0.8))) * 2) / 2
        quality = max(1, min(5, round(r.gauss(2.3 if poor else 3.4, 0.8))))
        skip_sleep = r.random() < 0.07
        obs = [dict(measure="sleep_hours", kind="self_reported", unit="h",
                    **({"missing_reason": "skipped_by_participant"} if skip_sleep else {"value_num": hours})),
               dict(measure="sleep_quality", kind="self_reported", unit="1-5", value_num=quality)]
        out.append(dict(protocol="daily_checkin", version="0.1", hour=8, minute=r.randrange(0, 40), obs=obs, status="completed"))

    # reaction activity: a fixed weekly rhythm (so the pattern is regular) with some days dropped
    weekday = day.weekday()
    rt_days = {0, 2, 4} if p.rt_rate > 0.35 else {1, 5}
    if weekday in rt_days and r.random() < 0.9:
        interrupted = r.random() < 0.06
        assisted = r.random() < 0.08
        unwell = True if r.random() < 0.04 else (False if r.random() < 0.8 else None)
        rt = r.gauss(p.rt_base + (38 if poor else 0) - drift, p.rt_sd)
        valid = 3 if interrupted else (5 if r.random() < 0.85 else 4)
        ant = 0 if r.random() < 0.8 else (1 if r.random() < 0.8 else 4)
        obs = [dict(measure="rt_median_ms", kind="observed", unit="ms", value_num=round(max(150, rt))),
               dict(measure="valid_trials", kind="observed", unit="count", value_num=valid),
               dict(measure="anticipations", kind="observed", unit="count", value_num=ant)]
        out.append(dict(protocol="reaction_time", version="0.1", hour=9, minute=r.randrange(0, 50), obs=obs,
                        status="interrupted" if interrupted else "completed", interruptions=1 if interrupted else 0,
                        assisted=assisted, unwell=unwell))

    # picture-sequence memory activity: about once a week
    if weekday == 6 and r.random() < 0.8:
        shown = 4
        correct = max(0, min(shown, round(r.gauss(2.6 if poor else 3.2, 0.8))))
        longest = max(0 if correct == 0 else 2, min(6, round(r.gauss(3.0 if poor else 3.6, 0.9))))
        obs = [dict(measure="rounds_correct", kind="observed", unit="count", value_num=correct),
               dict(measure="rounds_shown", kind="observed", unit="count", value_num=shown),
               dict(measure="longest_correct", kind="observed", unit="count", value_num=longest)]
        out.append(dict(protocol="picture_sequence", version="0.1", hour=16, minute=r.randrange(0, 50), obs=obs, status="completed",
                        assisted=r.random() < 0.1))

    # WHO-5 (English, published wording): every two weeks, only for the English-language profile, since no Arabic text is approved
    if p.language == "en" and (day.toordinal() % p.who5_every) == 3 and r.random() < 0.85:
        mean = 2.6 if poor else 3.3
        answers = [max(0, min(5, round(r.gauss(mean, 1.0)))) for _ in range(5)]
        obs = [dict(measure=f"who5_{i + 1}", kind="self_reported", unit="0-5", value_num=a) for i, a in enumerate(answers)]
        obs.append(dict(measure="who5_raw", kind="self_reported", unit="0-25", value_num=sum(answers)))
        out.append(dict(protocol="who5", version="1998-en", hour=18, minute=r.randrange(0, 50), obs=obs, status="completed"))
    return out


def _utc(day: date, hour: int, minute: int, tz: ZoneInfo) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=tz).astimezone(timezone.utc)


def _exists_session(db: Session, pid: str, protocol: str, at: datetime) -> bool:
    return db.scalar(select(ActivitySession.id).where(ActivitySession.participant_id == pid, ActivitySession.protocol_code == protocol,
                                                       ActivitySession.device == DEVICE, ActivitySession.started_at == at)) is not None


def _other_source_that_day(db: Session, pid: str, protocol: str, start: datetime, end: datetime) -> bool:
    return db.scalar(select(ActivitySession.id).where(
        ActivitySession.participant_id == pid, ActivitySession.protocol_code == protocol, ActivitySession.device != DEVICE,
        ActivitySession.started_at >= start, ActivitySession.started_at < end)) is not None


def _write_session(db: Session, pid: str, language: str, spec: dict, at: datetime, ref_utc: datetime, clinician_id: str | None) -> None:
    from . import protocols as P
    from .services import raise_review_items
    s = ActivitySession(participant_id=pid, protocol_code=spec["protocol"], protocol_version=spec["version"], language=language,
                        device=DEVICE, assisted=bool(spec.get("assisted")),
                        assistance_note="A relative held the tablet (synthetic)" if spec.get("assisted") else None,
                        unwell_today=spec.get("unwell"), interruptions=spec.get("interruptions", 0), status=spec["status"],
                        started_at=at, ended_at=at + timedelta(minutes=4))
    db.add(s)
    db.flush()
    obs = [Q.ObservationIn(o["measure"], o["kind"], o.get("value_num"), unit=o.get("unit"), missing_reason=o.get("missing_reason")) for o in spec["obs"]]
    verdicts = Q.assess_session(P.get(spec["protocol"], spec["version"]),
                                Q.SessionContext(status=s.status, assisted=s.assisted, unwell_today=s.unwell_today, interruptions=s.interruptions), obs)
    pairs = []
    for o, v in zip(obs, verdicts):
        person = o.kind == "self_reported"
        e = Evidence(participant_id=pid, session_id=s.id, kind=o.kind, measure=o.measure, value_num=o.value_num, unit=o.unit,
                     missing_reason=o.missing_reason, protocol_code=s.protocol_code, protocol_version=s.protocol_version,
                     producer_type="person" if person else "device", producer_id=pid if person else DEVICE, producer_version=PRODUCER,
                     quality=v.level, quality_reasons=v.reasons, recorded_at=at)
        db.add(e)
        db.flush()
        pairs.append((e, v))
    before = db.scalar(select(ReviewItem.id).order_by(ReviewItem.id.desc()).limit(1)) or 0
    raise_review_items(db, s, pairs, at=at)
    db.flush()
    if (ref_utc - at).days > REVIEW_OPEN_DAYS and clinician_id:   # older items read as already reviewed; recent ones stay open
        for it in db.scalars(select(ReviewItem).where(ReviewItem.id > before, ReviewItem.session_id == s.id)):
            it.status, it.decision, it.resolved_by = "resolved", "keep", clinician_id
            it.resolution_note = f"{LABEL}: kept after review."
            it.resolved_at = at + timedelta(days=2)


def _routine_replies(db: Session, pid: str, seed: int, first: date, last: date, tz: ZoneInfo, ref_utc: datetime) -> int:
    """Replies to routines in the person's accepted plan, only for days on or after the routine was created. No reply is stored for a
    day with no reply: silence is never recorded as a miss."""
    n = 0
    plan = db.scalar(select(CarePlan).where(CarePlan.participant_id == pid, CarePlan.status == "accepted").order_by(CarePlan.version.desc()))
    if plan is None:
        return 0
    items = db.scalars(select(CarePlanItem).where(CarePlanItem.plan_id == plan.id)).all()
    for it in items:
        created = it.created_at.astimezone(tz).date() if it.created_at.tzinfo else it.created_at.date()
        for k in range((last - max(first, created)).days + 1):
            day = max(first, created) + timedelta(days=k)
            if it.weekdays and day.weekday() not in it.weekdays:
                continue
            key = f"{DATASET_ID}:{pid}:{it.id}:{day.isoformat()}"
            r = _rng(seed, pid, "routine", it.id, day.isoformat())
            roll = r.random()
            if roll < 0.2:                       # no reply that day: nothing is written
                continue
            if db.scalar(select(CarePlanReply.id).where(CarePlanReply.idem_key == key)) is not None:
                continue
            reply = "done" if roll < 0.74 else ("not_today" if roll < 0.88 else ("difficulty" if roll < 0.95 else "snooze"))
            at = _utc(day, 10 if it.day_part == "morning" else 19, r.randrange(0, 50), tz)
            if at > ref_utc:
                continue
            db.add(CarePlanReply(item_id=it.id, participant_id=pid, day=day.isoformat(), reply=reply, at=at, idem_key=key,
                                 reason="too_tiring" if reply == "difficulty" else None, recorded_by=pid))
            n += 1
    return n


def _ensure_demo_access(db: Session, pid: str, clinician_id: str | None, since: datetime) -> None:
    """A demo person with a history is only useful if the demo clinician can see them: add the consent and the clinical-review grant
    when the person has none. Existing grants (including revoked ones) are never touched, so a person who withdrew stays withdrawn."""
    if clinician_id is None:
        return
    if db.scalar(select(AccessGrant.id).where(AccessGrant.owner_id == pid, AccessGrant.grantee_id == clinician_id,
                                              AccessGrant.purpose == "clinical_review")) is not None:
        return
    if db.scalar(select(ConsentEvent.id).where(ConsentEvent.participant_id == pid, ConsentEvent.scope == "participation")) is None:
        db.add(ConsentEvent(participant_id=pid, scope="participation", decision="granted", text_version="0.1",
                            language=PROFILES[pid].language, at=since))
    db.add(AccessGrant(owner_id=pid, grantee_id=clinician_id, purpose="clinical_review", created_at=since))


def apply(db: Session, seed: int = DEFAULT_SEED, ref_date: date | None = None, tz_name: str = DEFAULT_TZ, days: int = DEFAULT_DAYS,
          people: tuple[str, ...] = PEOPLE) -> dict:
    """Add the synthetic history for the given people. Idempotent; never removes or changes an existing record."""
    tz = ZoneInfo(tz_name)
    ref = ref_date or datetime.now(tz).date()
    ref_utc = datetime(ref.year, ref.month, ref.day, 23, 59, tzinfo=tz).astimezone(timezone.utc)
    clinician = db.get(User, "demo-dr-layla")
    cid = clinician.id if clinician is not None else None
    added = {"sessions": 0, "routine_replies": 0}
    for pid in people:
        person = db.get(User, pid)
        if person is None or not person.is_demo or pid not in PROFILES:
            continue
        p = PROFILES[pid]
        _ensure_demo_access(db, pid, cid, _utc(ref - timedelta(days=days), 8, 0, tz))
        for back in range(days, -1, -1):
            day = ref - timedelta(days=back)
            day_start = _utc(day, 0, 0, tz)
            day_end = day_start + timedelta(days=1)
            for spec in plan_day(seed, p, day, back):
                at = _utc(day, spec["hour"], spec["minute"], tz)
                if _exists_session(db, pid, spec["protocol"], at) or _other_source_that_day(db, pid, spec["protocol"], day_start, day_end):
                    continue
                _write_session(db, pid, p.language, spec, at, ref_utc, cid)
                added["sessions"] += 1
        added["routine_replies"] += _routine_replies(db, pid, seed, ref - timedelta(days=days), ref, tz, ref_utc)
    db.commit()
    return added


def summary(db: Session, pid: str) -> dict | None:
    """Counts for the dataset-level label: how many sessions of a person came from the synthetic history."""
    n = db.scalar(select(ActivitySession.id).where(ActivitySession.participant_id == pid, ActivitySession.device == DEVICE).limit(1))
    if n is None:
        return None
    rows = db.execute(select(ActivitySession.protocol_code, ActivitySession.started_at).where(
        ActivitySession.participant_id == pid, ActivitySession.device == DEVICE)).all()
    by: dict[str, int] = {}
    for code, _ in rows:
        by[code] = by.get(code, 0) + 1
    return {**dataset_info(), "sessions": len(rows), "by_protocol": by,
            "from": min(r[1] for r in rows).isoformat(), "to": max(r[1] for r in rows).isoformat()}


if __name__ == "__main__":
    import argparse

    from .db import Database
    from . import config

    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ap.add_argument("--ref-date", type=date.fromisoformat, default=None)
    ap.add_argument("--tz", default=DEFAULT_TZ)
    ap.add_argument("--days", type=int, default=DEFAULT_DAYS)
    a = ap.parse_args()
    database = Database(config.DATABASE_URL)
    database.create_all()
    with database.SessionLocal() as s:
        print(apply(s, a.seed, a.ref_date, a.tz, a.days))
