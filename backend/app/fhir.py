"""Export one person's records as an HL7 FHIR R4 Bundle (JSON).

Why: the records should be able to move to an electronic health record or a health information exchange (for
example Malaffi in Abu Dhabi) without being retyped. This module only builds the document; nothing is sent anywhere.
How it would be sent, and what has to be agreed first, is in docs/INTEGRATION_DESIGN.md.

What is in the Bundle (type "collection"):
- Patient: an internal identifier, the display name and the preferred language. No Emirates ID, date of birth or
  contact details, because NeuroTwin does not hold them; the receiving system matches the person by its own rules.
- Observation, one per current record: the value with its unit (UCUM), the activity and version, the device, the
  record's quality label (meta.tag), and the answers to "today's conditions" as components. A record that has no
  value says why (dataAbsentReason). Amended or withdrawn records are left out unless asked for; when included they
  carry status "amended" or "entered-in-error".
- Provenance, one per software producer and version: which rule or scorer made the records.
- Consent, one per scope the person has ever answered: granted (active) or withdrawn (inactive).

What is NOT in it, on purpose:
- Change estimates. They are computed when a clinician looks, with provisional settings, and are decision support
  for that clinician, not part of the record.
- Model-written summary drafts, messages, the assistant conversation, family messages, education and first language.
- Clinical codes (LOINC, SNOMED CT). The activities are NeuroTwin prototypes with no published code, so every code
  is from NeuroTwin's own code system, and the Observation says the activity is not a validated instrument.
  Mapping WHO-5 and any future validated instrument to LOINC is a task for the integration study.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import protocols as P
from .models import ActivitySession, ConsentEvent, Evidence, User

FHIR_VERSION = "4.0.1"
EXPORT_VERSION = "fhir-export/0.1"
BASE = "https://neurotwin.example/fhir"           # placeholder namespace until a real one is registered
CS_MEASURE = f"{BASE}/CodeSystem/measure"
CS_PROTOCOL = f"{BASE}/CodeSystem/activity"
CS_QUALITY = f"{BASE}/CodeSystem/record-quality"
CS_CONDITION = f"{BASE}/CodeSystem/today-condition"
CS_CONSENT = f"{BASE}/CodeSystem/consent-scope"
ID_PARTICIPANT = f"{BASE}/sid/participant"
UCUM = "http://unitsofmeasure.org"
OBS_CATEGORY = "http://terminology.hl7.org/CodeSystem/observation-category"
ABSENT = "http://terminology.hl7.org/CodeSystem/data-absent-reason"
CONSENT_SCOPE = "http://terminology.hl7.org/CodeSystem/consentscope"
LOINC = "http://loinc.org"
PROVENANCE_AGENT = "http://terminology.hl7.org/CodeSystem/provenance-participant-type"

# NeuroTwin unit -> (UCUM code, what a person reads)
UNITS = {"ms": ("ms", "ms"), "h": ("h", "h"), "count": ("{count}", "count"),
         "0-5": ("{score}", "score 0-5"), "1-5": ("{score}", "score 1-5"), "0-25": ("{score}", "score 0-25")}

MEASURE_NAMES = {
    "rt_median_ms": "Reaction time, median of valid trials",
    "valid_trials": "Reaction time, valid trials",
    "anticipations": "Reaction time, presses before the signal",
    "rounds_correct": "Picture sequence, rounds correct",
    "rounds_shown": "Picture sequence, rounds shown",
    "longest_correct": "Picture sequence, longest sequence correct",
    "sleep_hours": "Hours slept (self-reported)",
    "sleep_quality": "Sleep quality 1-5 (self-reported)",
    "today_factors": "Things affecting today (self-reported)",
    "who5_raw": "WHO-5 Well-Being Index, raw total 0-25",
}
CONDITION_NAMES = {"see_clearly": "Could see the screen clearly", "hear_clearly": "Could hear clearly",
                   "slept_well": "Slept well", "quiet_place": "In a quiet place", "unwell_today": "Felt unwell today"}
MISSING = {"skipped_by_participant": "asked-declined"}
STATUS = {"current": "final", "amended": "amended", "withdrawn": "entered-in-error"}


def _instant(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _uid(*parts: object) -> str:
    """Stable id: the same record always gets the same id, so a resend updates instead of duplicating."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, BASE + "/" + "/".join(str(p) for p in parts)))


def _entry(resource: dict) -> dict:
    return {"fullUrl": f"urn:uuid:{resource['id']}", "resource": resource}


def patient(user: User) -> dict:
    return {
        "resourceType": "Patient", "id": _uid("Patient", user.id),
        "identifier": [{"system": ID_PARTICIPANT, "value": user.id}],
        "active": True,
        "name": [{"text": user.display_name}],
        "communication": [{"language": {"coding": [{"system": "urn:ietf:bcp:47", "code": user.language}]}, "preferred": True}],
    }


def observation(e: Evidence, session: ActivitySession | None, patient_ref: str) -> dict:
    proto = P.get(e.protocol_code or "", e.protocol_version or "")
    category = "survey" if e.kind == "self_reported" else "exam"
    o: dict = {
        "resourceType": "Observation", "id": _uid("Observation", e.id),
        "meta": {"tag": [{"system": CS_QUALITY, "code": e.quality}]},
        "identifier": [{"system": f"{BASE}/sid/evidence", "value": str(e.id)}],
        "status": STATUS.get(e.status, "final"),
        "category": [{"coding": [{"system": OBS_CATEGORY, "code": category}]}],
        "code": {"coding": [{"system": CS_MEASURE, "code": e.measure, "display": MEASURE_NAMES.get(e.measure, e.measure)}],
                 "text": MEASURE_NAMES.get(e.measure, e.measure)},
        "subject": {"reference": patient_ref},
        "effectiveDateTime": _instant(session.started_at if session else e.recorded_at),
        "issued": _instant(e.recorded_at),
    }
    if e.value_num is not None:
        code, shown = UNITS.get(e.unit or "", ("1", e.unit or ""))
        o["valueQuantity"] = {"value": e.value_num, "unit": shown, "system": UCUM, "code": code}
    elif e.value_text:
        o["valueString"] = e.value_text
    else:
        o["dataAbsentReason"] = {"coding": [{"system": ABSENT, "code": MISSING.get(e.missing_reason or "", "unknown")}],
                                 "text": e.missing_reason or "not recorded"}
    if e.protocol_code:
        o["method"] = {"coding": [{"system": CS_PROTOCOL, "code": e.protocol_code, "version": e.protocol_version}],
                       "text": f"{e.protocol_code} {e.protocol_version}"}
    if session and session.device and session.device != "unknown":
        o["device"] = {"display": session.device}
    notes = []
    if proto is None or proto.review_status == P.PROTOTYPE:
        notes.append("NeuroTwin prototype activity: not a validated instrument; no norms or cut-offs apply.")
    elif proto.review_status == P.PUBLISHED:
        notes.append("Published instrument, English wording unmodified; no cut-off or interpretation applied by NeuroTwin.")
    if e.quality_reasons:
        notes.append("Quality: " + e.quality + " (" + ", ".join(map(str, e.quality_reasons)) + ").")
    if session and session.assisted:
        notes.append("Done with help" + (f": {session.assistance_note}" if session.assistance_note else "") + ".")
    if e.change_reason:
        notes.append(f"Change reason: {e.change_reason}")
    if notes:
        o["note"] = [{"text": n} for n in notes]
    if session:
        comps = [{"code": {"coding": [{"system": CS_CONDITION, "code": k, "display": v}]}, "valueBoolean": getattr(session, k)}
                 for k, v in CONDITION_NAMES.items() if getattr(session, k, None) is not None]
        if comps:
            o["component"] = comps
    if e.derived_from:
        o["derivedFrom"] = [{"reference": f"urn:uuid:{_uid('Observation', i)}"} for i in e.derived_from]
    return o


def provenance(producer: tuple[str, str, str], targets: list[str], when: datetime | None) -> dict:
    ptype, pid, pver = producer
    return {
        "resourceType": "Provenance", "id": _uid("Provenance", *producer),
        "target": [{"reference": t} for t in targets],
        "recorded": _instant(when or datetime.now(timezone.utc)),
        "agent": [{"type": {"coding": [{"system": PROVENANCE_AGENT, "code": "assembler"}]},
                   "who": {"display": f"NeuroTwin {ptype} {pid} {pver}"}}],
    }


def consents(db: Session, user: User, patient_ref: str) -> list[dict]:
    latest: dict[str, ConsentEvent] = {}
    for c in db.scalars(select(ConsentEvent).where(ConsentEvent.participant_id == user.id).order_by(ConsentEvent.at, ConsentEvent.id)):
        latest[c.scope] = c
    out = []
    for scope, c in latest.items():
        out.append({
            "resourceType": "Consent", "id": _uid("Consent", user.id, scope),
            "status": "active" if c.decision == "granted" else "inactive",
            "scope": {"coding": [{"system": CONSENT_SCOPE, "code": "patient-privacy"}]},
            "category": [{"coding": [{"system": LOINC, "code": "59284-0", "display": "Patient Consent"}]},
                         {"coding": [{"system": CS_CONSENT, "code": scope}]}],
            "patient": {"reference": patient_ref},
            "dateTime": _instant(c.at),
            "policyRule": {"text": f"NeuroTwin consent text {c.text_version} ({c.language})"},
            "provision": {"type": "permit" if c.decision == "granted" else "deny"},
        })
    return out


def bundle(db: Session, participant: User, include_history: bool = False, now: datetime | None = None) -> dict:
    """The person's records as a FHIR R4 collection Bundle. Pure read: writes nothing, sends nothing."""
    pat = patient(participant)
    pref = f"urn:uuid:{pat['id']}"
    q = select(Evidence).where(Evidence.participant_id == participant.id)
    if not include_history:
        q = q.where(Evidence.status == "current")
    rows = db.scalars(q.order_by(Evidence.recorded_at, Evidence.id)).all()
    sessions = {s.id: s for s in db.scalars(select(ActivitySession).where(ActivitySession.participant_id == participant.id))}
    obs, by_producer, last = [], {}, {}
    exported = {e.id for e in rows}
    for e in rows:
        o = observation(e, sessions.get(e.session_id), pref)
        if "derivedFrom" in o:      # only point at records that are in this Bundle
            o["derivedFrom"] = [r for r, i in zip(o["derivedFrom"], e.derived_from) if i in exported] or None
            if not o["derivedFrom"]:
                del o["derivedFrom"]
        obs.append(o)
        key = (e.producer_type, e.producer_id, e.producer_version)
        by_producer.setdefault(key, []).append(f"urn:uuid:{o['id']}")
        last[key] = max(filter(None, [last.get(key), e.recorded_at]), default=None)
    provs = [provenance(k, v, last.get(k)) for k, v in by_producer.items()]
    resources = [pat, *obs, *provs, *consents(db, participant, pref)]
    stamp = now or datetime.now(timezone.utc)
    return {
        "resourceType": "Bundle", "id": str(uuid.uuid4()),
        "meta": {"lastUpdated": _instant(stamp), "tag": [{"system": f"{BASE}/CodeSystem/export", "code": EXPORT_VERSION}]},
        "type": "collection", "timestamp": _instant(stamp),
        "entry": [_entry(r) for r in resources],
    }
