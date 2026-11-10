"""Synthetic demo accounts and records.

Everything here is invented. Every account is flagged `is_demo`, and the apps label demo data as synthetic.
The values are made up to exercise the screens and the quality rules (an interrupted session, an assisted one,
a missing answer); they carry no clinical meaning.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from . import quality as Q
from .models import AccessGrant, ActivitySession, ConsentEvent, Evidence, User

DEVICE = "demo-seed"


def seed(db: Session) -> None:
    if db.query(User).count():
        return
    users = [
        User(id="demo-fatima", display_name="فاطمة", role="participant", language="ar", is_demo=True),
        User(id="demo-yousef", display_name="Yousef", role="participant", language="en", is_demo=True),
        User(id="demo-mariam", display_name="مريم", role="family", language="ar", is_demo=True),
        User(id="demo-omar", display_name="Omar", role="family", language="en", is_demo=True),
        User(id="demo-dr-layla", display_name="Dr. Layla", role="clinician", language="en", is_demo=True),
    ]
    db.add_all(users)
    db.flush()

    start = datetime.now(timezone.utc) - timedelta(days=42)
    db.add(ConsentEvent(participant_id="demo-fatima", scope="participation", decision="granted",
                        text_version="0.1", language="ar", at=start))
    db.add(AccessGrant(owner_id="demo-fatima", grantee_id="demo-dr-layla", purpose="clinical_review", created_at=start))
    db.add(AccessGrant(owner_id="demo-fatima", grantee_id="demo-mariam", purpose="participation_updates",
                       created_at=start))

    # Six weekly reaction-time sessions and check-ins. Week 3 was interrupted, week 5 had a helper.
    rt = [612, 598, 640, 605, 655, 590]
    sleep = [7, 6.5, 5, 7, 6, None]
    for week in range(6):
        at = start + timedelta(days=7 * week + 1, hours=9)
        interrupted = week == 2
        assisted = week == 4
        s = ActivitySession(participant_id="demo-fatima", protocol_code="reaction_time", protocol_version="0.1",
                            language="ar", device=DEVICE, assisted=assisted,
                            assistance_note="Daughter held the tablet" if assisted else None, unwell_today=False,
                            interruptions=1 if interrupted else 0, status="interrupted" if interrupted else "completed",
                            started_at=at, ended_at=at + timedelta(minutes=4))
        db.add(s)
        db.flush()
        obs = [Q.ObservationIn("rt_median_ms", "observed", rt[week], unit="ms"),
               Q.ObservationIn("valid_trials", "observed", 5 if not interrupted else 3, unit="count"),
               Q.ObservationIn("anticipations", "observed", 0, unit="count")]
        _store(db, s, obs, at)

        c = ActivitySession(participant_id="demo-fatima", protocol_code="daily_checkin", protocol_version="0.1",
                            language="ar", device=DEVICE, status="completed", started_at=at - timedelta(minutes=10),
                            ended_at=at - timedelta(minutes=8))
        db.add(c)
        db.flush()
        sl = sleep[week]
        cobs = [Q.ObservationIn("sleep_hours", "self_reported", sl, unit="h") if sl is not None
                else Q.ObservationIn("sleep_hours", "self_reported", missing_reason="skipped_by_participant", unit="h"),
                Q.ObservationIn("sleep_quality", "self_reported", 3 if week != 2 else 2, unit="1-5")]
        _store(db, c, cobs, at - timedelta(minutes=8))
    db.commit()


def _store(db: Session, s: ActivitySession, obs: list[Q.ObservationIn], at: datetime) -> None:
    from . import protocols as P
    verdicts = Q.assess_session(P.get(s.protocol_code, s.protocol_version),
                                Q.SessionContext(status=s.status, assisted=s.assisted, unwell_today=s.unwell_today,
                                                 interruptions=s.interruptions), obs)
    from .services import raise_review_items
    pairs = []
    for o, v in zip(obs, verdicts):
        person = o.kind == "self_reported"
        e = Evidence(participant_id=s.participant_id, session_id=s.id, kind=o.kind, measure=o.measure,
                     value_num=o.value_num, value_text=o.value_text, unit=o.unit, missing_reason=o.missing_reason,
                     protocol_code=s.protocol_code, protocol_version=s.protocol_version,
                     producer_type="person" if person else "device",
                     producer_id=s.participant_id if person else DEVICE, producer_version="seed/0.1",
                     quality=v.level, quality_reasons=v.reasons, recorded_at=at)
        db.add(e)
        db.flush()
        pairs.append((e, v))
    raise_review_items(db, s, pairs, at=at)
