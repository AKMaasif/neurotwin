"""Everything that changes stored state goes through here, and every change writes an audit event."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import protocols as P
from . import quality as Q
from .models import (CONSENT_SCOPES, GRANT_PURPOSES, AccessGrant, ActivitySession, AuditEvent, ConsentEvent,
                     Evidence, ReviewItem, User, now)
from .security import PURPOSE_ROLE, active_grant

CONSENT_TEXT_VERSION = "0.1"


class Refused(Exception):
    """A request that is understood but not allowed. Carries an HTTP status and a plain message."""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def audit(db: Session, actor: str, action: str, participant_id: str | None = None, target: str | None = None) -> None:
    db.add(AuditEvent(actor_id=actor, action=action, participant_id=participant_id, target=target))


# ---- Consent -------------------------------------------------------------------------------------------------

def consent_state(db: Session, participant_id: str) -> dict[str, dict]:
    rows = db.scalars(select(ConsentEvent).where(ConsentEvent.participant_id == participant_id)
                      .order_by(ConsentEvent.id)).all()
    state = {s: {"scope": s, "granted": False, "at": None, "text_version": None} for s in CONSENT_SCOPES}
    for r in rows:
        state[r.scope] = {"scope": r.scope, "granted": r.decision == "granted", "at": r.at,
                          "text_version": r.text_version}
    return state


def set_consent(db: Session, user: User, scope: str, granted: bool, language: str) -> dict:
    if user.role != "participant":
        raise Refused(403, "Only the participant can give or withdraw their own consent.")
    if scope not in CONSENT_SCOPES:
        raise Refused(422, f"Unknown consent scope: {scope}.")
    db.add(ConsentEvent(participant_id=user.id, scope=scope, decision="granted" if granted else "withdrawn",
                        text_version=CONSENT_TEXT_VERSION, language=language))
    audit(db, user.id, f"consent.{'granted' if granted else 'withdrawn'}", user.id, scope)
    db.commit()
    return consent_state(db, user.id)[scope]


def has_consent(db: Session, participant_id: str, scope: str) -> bool:
    return consent_state(db, participant_id)[scope]["granted"]


# ---- Sharing -------------------------------------------------------------------------------------------------

def create_grant(db: Session, owner: User, grantee_id: str, purpose: str) -> AccessGrant:
    if owner.role != "participant":
        raise Refused(403, "Only the participant can share their own information.")
    if purpose not in GRANT_PURPOSES:
        raise Refused(422, f"Unknown purpose: {purpose}.")
    grantee = db.get(User, grantee_id)
    if grantee is None or grantee.id == owner.id:
        raise Refused(404, "That person was not found.")
    if grantee.role != PURPOSE_ROLE[purpose]:
        raise Refused(422, f"{purpose} can only be shared with a {PURPOSE_ROLE[purpose]}.")
    existing = active_grant(db, owner.id, grantee.id, purpose)
    if existing:
        return existing
    grant = AccessGrant(owner_id=owner.id, grantee_id=grantee.id, purpose=purpose)
    db.add(grant)
    db.flush()
    audit(db, owner.id, "grant.created", owner.id, f"grant:{grant.id}:{purpose}:{grantee.id}")
    db.commit()
    return grant


def revoke_grant(db: Session, owner: User, grant_id: int) -> AccessGrant:
    grant = db.get(AccessGrant, grant_id)
    if grant is None or grant.owner_id != owner.id:
        raise Refused(404, "That sharing arrangement was not found.")
    if grant.revoked_at is None:
        grant.revoked_at = now()
        audit(db, owner.id, "grant.revoked", owner.id, f"grant:{grant.id}")
        db.commit()
    return grant


# ---- Sessions and evidence -----------------------------------------------------------------------------------

def start_session(db: Session, user: User, protocol_code: str, protocol_version: str, language: str,
                  device: str, assisted: bool, assistance_note: str | None, unwell_today: bool | None) -> ActivitySession:
    if user.role != "participant":
        raise Refused(403, "Only participants take part in activities.")
    if not has_consent(db, user.id, "participation"):
        raise Refused(409, "Participation consent is not in place. Nothing was recorded.")
    if P.get(protocol_code, protocol_version) is None:
        raise Refused(422, f"Unknown activity {protocol_code} version {protocol_version}.")
    s = ActivitySession(participant_id=user.id, protocol_code=protocol_code, protocol_version=protocol_version,
                        language=language, device=device[:80], assisted=assisted,
                        assistance_note=(assistance_note or None), unwell_today=unwell_today)
    db.add(s)
    db.flush()
    audit(db, user.id, "session.started", user.id, f"session:{s.id}")
    db.commit()
    return s


def complete_session(db: Session, user: User, session_id: int, status: str, interruptions: int,
                     observations: list[Q.ObservationIn], device_version: str) -> list[Evidence]:
    s = db.get(ActivitySession, session_id)
    if s is None or s.participant_id != user.id:
        raise Refused(404, "Session not found.")
    if s.status != "in_progress":
        raise Refused(409, "This session is already finished.")
    if status not in ("completed", "interrupted", "abandoned"):
        raise Refused(422, f"Unknown session status: {status}.")
    if not has_consent(db, user.id, "participation"):
        raise Refused(409, "Participation consent was withdrawn. Nothing from this session was recorded.")
    if interruptions < 0:
        raise Refused(422, "interruptions cannot be negative.")

    protocol = P.get(s.protocol_code, s.protocol_version)
    ctx = Q.SessionContext(status=status, assisted=s.assisted, unwell_today=s.unwell_today,
                           interruptions=interruptions)
    try:
        verdicts = Q.assess_session(protocol, ctx, observations)
    except Q.EvidenceRejected as e:
        raise Refused(422, str(e)) from e

    s.status, s.interruptions, s.ended_at = status, interruptions, now()
    records: list[Evidence] = []
    for obs, v in zip(observations, verdicts):
        producer_type = "person" if obs.kind == "self_reported" else "device"
        e = Evidence(
            participant_id=user.id, session_id=s.id, kind=obs.kind, measure=obs.measure,
            value_num=obs.value_num, value_text=obs.value_text, unit=obs.unit, missing_reason=obs.missing_reason,
            protocol_code=s.protocol_code, protocol_version=s.protocol_version,
            producer_type=producer_type, producer_id=user.id if producer_type == "person" else s.device,
            producer_version=device_version, quality=v.level, quality_reasons=v.reasons,
        )
        db.add(e)
        db.flush()
        records.append(e)
    raise_review_items(db, s, list(zip(records, verdicts)))
    audit(db, user.id, f"session.{status}", user.id, f"session:{s.id}")
    db.commit()
    return records


def raise_review_items(db: Session, s: ActivitySession, pairs: list[tuple[Evidence, Q.Verdict]], at=None) -> None:
    """One item per record-level reason; one per session for reasons about the whole session."""
    seen: set[str] = set()
    for e, v in pairs:
        for reason in v.reasons:
            if reason not in Q.NEEDS_REVIEW:
                continue
            if reason in Q.SESSION_LEVEL:
                if reason in seen:
                    continue
                seen.add(reason)
            item = ReviewItem(participant_id=s.participant_id, evidence_id=e.id, session_id=s.id, reason=reason,
                              raised_by=Q.RULES_VERSION)
            if at is not None:
                item.created_at = at
            db.add(item)


def record_inferred(db: Session, participant_id: str, measure: str, value_num: float | None, unit: str | None,
                    derived_from: list[int], producer_type: str, producer_id: str, producer_version: str) -> Evidence:
    """An inferred record must name the records it came from and what produced it. Not exposed over HTTP yet:
    nothing in this phase infers anything. It exists so the rule is enforced before anything does."""
    if producer_type not in ("rule", "model"):
        raise Refused(422, "Inferred records are produced by a rule or a model.")
    if not derived_from:
        raise Refused(422, "An inferred record must list the evidence it was derived from.")
    sources = db.scalars(select(Evidence).where(Evidence.id.in_(derived_from))).all()
    if len(sources) != len(set(derived_from)) or any(x.participant_id != participant_id for x in sources):
        raise Refused(422, "Every source must exist and belong to the same participant.")
    if any(x.status != "current" or x.quality == "unusable" for x in sources):
        raise Refused(422, "Sources must be current and not unusable.")
    e = Evidence(participant_id=participant_id, kind="inferred", measure=measure, value_num=value_num, unit=unit,
                 producer_type=producer_type, producer_id=producer_id, producer_version=producer_version,
                 derived_from=sorted(set(derived_from)), quality="usable", quality_reasons=[])
    db.add(e)
    db.flush()
    audit(db, producer_id, "evidence.inferred", participant_id, f"evidence:{e.id}")
    db.commit()
    return e


def amend_self_report(db: Session, user: User, evidence_id: int, value_num: float | None, value_text: str | None,
                      reason: str) -> Evidence:
    """A participant corrects something they reported. The old record stays, marked amended."""
    old = db.get(Evidence, evidence_id)
    if old is None or old.participant_id != user.id:
        raise Refused(404, "Record not found.")
    if old.kind != "self_reported":
        raise Refused(409, "Only self-reported answers can be corrected. Observed results are kept as recorded.")
    if old.status != "current":
        raise Refused(409, "This record has already been corrected or withdrawn.")
    if not reason.strip():
        raise Refused(422, "Say briefly why it is being corrected.")
    protocol = P.get(old.protocol_code or "", old.protocol_version or "")
    obs = Q.ObservationIn(measure=old.measure, kind=old.kind, value_num=value_num, value_text=value_text,
                          unit=old.unit)
    try:
        v = Q.assess_session(protocol, Q.SessionContext(status="completed"), [obs])[0]
    except Q.EvidenceRejected as e:
        raise Refused(422, str(e)) from e
    # A single-record re-check cannot see the rest of its session, so drop that one session-level reason.
    reasons = [r for r in v.reasons if r != "missing_required"]
    level = v.level if reasons else "usable"
    new = Evidence(participant_id=old.participant_id, session_id=old.session_id, kind=old.kind, measure=old.measure,
                   value_num=value_num, value_text=value_text, unit=old.unit, protocol_code=old.protocol_code,
                   protocol_version=old.protocol_version, producer_type="person", producer_id=user.id,
                   producer_version=old.producer_version, quality=level, quality_reasons=reasons,
                   supersedes_id=old.id, change_reason=reason.strip()[:300])
    db.add(new)
    db.flush()
    old.status, old.superseded_by_id = "amended", new.id
    audit(db, user.id, "evidence.amended", user.id, f"evidence:{old.id}->{new.id}")
    db.commit()
    return new


def withdraw_evidence(db: Session, user: User, evidence_id: int, reason: str) -> Evidence:
    """Mark a record as not to be used. It is kept, visibly withdrawn, with the reason and who did it."""
    e = db.get(Evidence, evidence_id)
    if e is None:
        raise Refused(404, "Record not found.")
    allowed = user.id == e.participant_id or (
        user.role == "clinician" and active_grant(db, e.participant_id, user.id, "clinical_review"))
    if not allowed:
        raise Refused(404, "Record not found.")
    if e.status != "current":
        raise Refused(409, "This record has already been corrected or withdrawn.")
    if not reason.strip():
        raise Refused(422, "Say briefly why it is being withdrawn.")
    e.status, e.change_reason = "withdrawn", reason.strip()[:300]
    audit(db, user.id, "evidence.withdrawn", e.participant_id, f"evidence:{e.id}")
    db.commit()
    return e


REVIEW_DECISIONS = ("keep", "exclude")


def resolve_review(db: Session, user: User, item_id: int, note: str, decision: str = "keep",
                   commit: bool = True) -> ReviewItem:
    """A clinician closes a "To check" item with a decision and a note.

    keep:    the record stays in use, with its quality label unchanged (a person's judgement does not rewrite what
             the rules found; it is recorded beside it).
    exclude: the record is withdrawn (kept, visibly withdrawn, with the note as the reason).
    """
    item = db.get(ReviewItem, item_id)
    if item is None:
        raise Refused(404, "Item not found.")
    if user.role != "clinician" or not active_grant(db, item.participant_id, user.id, "clinical_review"):
        raise Refused(404, "Item not found.")
    if item.status != "open":
        raise Refused(409, "This item is already resolved.")
    if decision not in REVIEW_DECISIONS:
        raise Refused(422, f"Decision must be one of {', '.join(REVIEW_DECISIONS)}.")
    if not note.strip():
        raise Refused(422, "Add a short note saying what you decided.")
    item.status, item.decision = "resolved", decision
    item.resolved_by, item.resolution_note, item.resolved_at = user.id, note.strip()[:500], now()
    if decision == "exclude" and item.evidence_id:
        e = db.get(Evidence, item.evidence_id)
        targets = [e] if e else []
        if item.reason in Q.SESSION_LEVEL and item.session_id:  # a session-wide problem excludes the whole session
            targets = db.scalars(select(Evidence).where(Evidence.session_id == item.session_id)).all()
        for t in targets:
            if t.status == "current":
                t.status, t.change_reason = "withdrawn", f"Excluded in review: {note.strip()[:280]}"
                audit(db, user.id, "evidence.withdrawn", t.participant_id, f"evidence:{t.id}")
    audit(db, user.id, f"review.{decision}", item.participant_id, f"review:{item.id}")
    if commit:
        db.commit()
    return item


def resolve_reviews(db: Session, user: User, item_ids: list[int], note: str, decision: str) -> list[ReviewItem]:
    """Several items, one decision and note. All or nothing: if any item cannot be resolved, none is."""
    if not item_ids:
        raise Refused(422, "Choose at least one item.")
    if len(set(item_ids)) > 200:
        raise Refused(422, "At most 200 items at once.")
    try:
        items = [resolve_review(db, user, i, note, decision, commit=False) for i in dict.fromkeys(item_ids)]
    except Refused:
        db.rollback()
        raise
    db.commit()
    return items


# ---- Report --------------------------------------------------------------------------------------------------

def build_report(db: Session, user: User, participant_id: str) -> dict:
    """A factual summary for a clinician to print or keep. Counts and lists only: no interpretation, no score."""
    person = db.get(User, participant_id)
    sessions = db.scalars(select(ActivitySession).where(ActivitySession.participant_id == participant_id)
                          .order_by(ActivitySession.started_at)).all()
    evidence = db.scalars(select(Evidence).where(Evidence.participant_id == participant_id,
                                                 Evidence.status != "amended")
                          .order_by(Evidence.recorded_at)).all()
    items = db.scalars(select(ReviewItem).where(ReviewItem.participant_id == participant_id)
                       .order_by(ReviewItem.created_at)).all()

    measures: dict[tuple, dict] = {}
    for e in evidence:
        key = (e.protocol_code, e.protocol_version, e.measure)
        m = measures.setdefault(key, {"protocol_code": e.protocol_code, "protocol_version": e.protocol_version,
                                      "measure": e.measure, "kind": e.kind, "unit": e.unit, "records": 0,
                                      "usable": 0, "doubtful": 0, "unusable": 0, "missing": 0, "withdrawn": 0,
                                      "first": None, "last": None, "values": []})
        m["records"] += 1
        if e.status == "withdrawn":
            m["withdrawn"] += 1
            continue
        m[e.quality] += 1
        if e.missing_reason:
            m["missing"] += 1
        m["first"] = m["first"] or e.recorded_at
        m["last"] = e.recorded_at
        if e.value_num is not None and e.quality != "unusable":
            m["values"].append({"at": e.recorded_at, "value": e.value_num, "quality": e.quality, "id": e.id})

    status_counts: dict[str, int] = {}
    for s in sessions:
        status_counts[s.status] = status_counts.get(s.status, 0) + 1

    audit(db, user.id, "report.generated", participant_id, None)
    db.commit()
    return {
        "participant": {"id": person.id, "display_name": person.display_name, "is_demo": person.is_demo},
        "generated_by": user.display_name, "generated_at": now(),
        "period": {"from": sessions[0].started_at if sessions else None,
                   "to": sessions[-1].started_at if sessions else None},
        "sessions": {"total": len(sessions), "by_status": status_counts,
                     "assisted": sum(1 for s in sessions if s.assisted),
                     "unwell": sum(1 for s in sessions if s.unwell_today)},
        "measures": list(measures.values()),
        "review": {"open": [i for i in items if i.status == "open"],
                   "resolved": [i for i in items if i.status != "open"]},
        "rules_version": Q.RULES_VERSION,
    }


# ---- What a family member may see ----------------------------------------------------------------------------

def family_view(db: Session, user: User) -> list[dict]:
    """For each participant who shares with this person: either their participation summary, or a plain note that
    sharing has ended. No values, no quality, no evidence detail, ever."""
    grants = db.scalars(select(AccessGrant).where(AccessGrant.grantee_id == user.id,
                                                  AccessGrant.purpose == "participation_updates")
                        .order_by(AccessGrant.id)).all()
    latest: dict[str, AccessGrant] = {}
    for g in grants:  # oldest first: an active grant, once found, stays; otherwise the newest ended one shows
        current = latest.get(g.owner_id)
        if current is None or current.revoked_at is not None:
            latest[g.owner_id] = g
    out = []
    for owner_id, g in latest.items():
        owner = db.get(User, owner_id)
        entry = {"participant_id": owner_id, "display_name": owner.display_name, "active": g.revoked_at is None,
                 "since": g.created_at, "ended_at": g.revoked_at, "recent": []}
        if g.revoked_at is None:
            sessions = db.scalars(select(ActivitySession).where(ActivitySession.participant_id == owner_id,
                                                                ActivitySession.status != "in_progress")
                                  .order_by(ActivitySession.started_at.desc()).limit(10)).all()
            entry["recent"] = [{"protocol_code": s.protocol_code, "status": s.status, "at": s.ended_at or s.started_at}
                               for s in sessions]
            audit(db, user.id, "family.viewed", owner_id, None)
        out.append(entry)
    db.commit()
    return out
