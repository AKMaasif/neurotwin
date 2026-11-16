"""FHIR R4 export: structure, references, who may export, what is left out, and that it is audited."""
import json
import re

import pytest

from conftest import run_reaction

ID = re.compile(r"^[A-Za-z0-9\-.]{1,64}$")
INSTANT = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$")
# The R4 elements each exported resource may use (a typo or an R5-only element fails the test).
ALLOWED = {
    "Bundle": {"resourceType", "id", "meta", "type", "timestamp", "entry"},
    "Patient": {"resourceType", "id", "identifier", "active", "name", "communication"},
    "Observation": {"resourceType", "id", "meta", "identifier", "status", "category", "code", "subject", "effectiveDateTime",
                    "issued", "valueQuantity", "valueString", "dataAbsentReason", "method", "device", "note", "component",
                    "derivedFrom"},
    "Provenance": {"resourceType", "id", "target", "recorded", "agent"},
    "Consent": {"resourceType", "id", "status", "scope", "category", "patient", "dateTime", "policyRule", "provision"},
}
OBS_STATUS = {"registered", "preliminary", "final", "amended", "corrected", "cancelled", "entered-in-error", "unknown"}
CONSENT_STATUS = {"draft", "proposed", "active", "rejected", "inactive", "entered-in-error"}


def refs(x):
    if isinstance(x, dict):
        for k, v in x.items():
            if k == "reference":
                yield v
            else:
                yield from refs(v)
    elif isinstance(x, list):
        for v in x:
            yield from refs(v)


def check_r4(b: dict) -> dict:
    """The R4 rules this export relies on, checked without a FHIR library. Returns resources by type."""
    assert b["resourceType"] == "Bundle" and b["type"] == "collection" and INSTANT.match(b["timestamp"])
    assert set(b) <= ALLOWED["Bundle"]
    urls = [e["fullUrl"] for e in b["entry"]]
    assert len(urls) == len(set(urls)), "fullUrl must be unique"
    by = {}
    for e in b["entry"]:
        r = e["resource"]
        t = r["resourceType"]
        assert set(r) <= ALLOWED[t], (t, set(r) - ALLOWED[t])
        assert ID.match(r["id"]) and e["fullUrl"] == f"urn:uuid:{r['id']}"
        by.setdefault(t, []).append(r)
    for ref in refs([e["resource"] for e in b["entry"]]):
        assert ref in urls, f"dangling reference {ref}"
    for o in by.get("Observation", []):
        assert o["status"] in OBS_STATUS and o["code"]["coding"] and o["subject"]["reference"]
        values = [k for k in o if k.startswith("value")]
        assert len(values) <= 1
        assert ("dataAbsentReason" in o) != bool(values), "obs-6: dataAbsentReason only when there is no value"
        if "valueQuantity" in o:
            q = o["valueQuantity"]
            assert isinstance(q["value"], (int, float)) and q["system"] == "http://unitsofmeasure.org" and q["code"]
        for c in o.get("component", []):
            assert c["code"]["coding"] and isinstance(c["valueBoolean"], bool)
        assert INSTANT.match(o["issued"]) and INSTANT.match(o["effectiveDateTime"])
    for c in by.get("Consent", []):
        assert c["status"] in CONSENT_STATUS and c["scope"] and c["category"] and c["patient"]
        assert "policy" in c or "policyRule" in c, "ppc-1"
        assert c["provision"]["type"] in ("permit", "deny")
    for p in by.get("Provenance", []):
        assert p["target"] and INSTANT.match(p["recorded"]) and p["agent"][0]["who"]
    assert len(by["Patient"]) == 1
    return by


def export(client, h, pid="demo-fatima", **params):
    r = client.get(f"/api/participants/{pid}/fhir", headers=h, params=params)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("application/fhir+json")
    return r.json()


def test_export_is_valid_r4_and_covers_every_current_record(client, login, app):
    h = login("demo-fatima")
    run_reaction(client, h, rt=480, conditions={"see_clearly": False, "slept_well": True})
    b = export(client, h)
    by = check_r4(b)
    from app.models import Evidence
    with app.state.db.SessionLocal() as db:
        current = db.query(Evidence).filter(Evidence.participant_id == "demo-fatima", Evidence.status == "current").count()
    assert len(by["Observation"]) == current
    rt = [o for o in by["Observation"] if o["code"]["coding"][0]["code"] == "rt_median_ms"][-1]
    assert rt["valueQuantity"] == {"value": 480, "unit": "ms", "system": "http://unitsofmeasure.org", "code": "ms"}
    assert rt["category"][0]["coding"][0]["code"] == "exam" and rt["method"]["coding"][0]["code"] == "reaction_time"
    comps = {c["code"]["coding"][0]["code"]: c["valueBoolean"] for c in rt["component"]}
    assert comps == {"see_clearly": False, "slept_well": True}
    assert rt["meta"]["tag"][0]["code"] == "doubtful"          # not seeing the screen clearly lowers quality
    assert any("not a validated instrument" in n["text"] for n in rt["note"])
    assert all(p["agent"][0]["who"]["display"].startswith("NeuroTwin ") for p in by["Provenance"])
    covered = {t["reference"] for p in by["Provenance"] for t in p["target"]}
    assert covered == {f"urn:uuid:{o['id']}" for o in by["Observation"]}


def test_missing_value_says_why(client, login):
    h = login("demo-fatima")
    s = client.post("/api/sessions", json={"protocol_code": "daily_checkin", "protocol_version": "0.1"}, headers=h).json()
    r = client.post(f"/api/sessions/{s['id']}/complete", headers=h, json={"status": "completed", "observations": [
        {"measure": "sleep_hours", "kind": "self_reported", "value_num": 7, "unit": "h"},
        {"measure": "sleep_quality", "kind": "self_reported", "value_num": 4, "unit": "1-5"},
        {"measure": "today_factors", "kind": "self_reported", "missing_reason": "skipped_by_participant"}]})
    assert r.status_code == 200, r.text
    by = check_r4(export(client, h))
    tf = [o for o in by["Observation"] if o["code"]["coding"][0]["code"] == "today_factors"][-1]
    assert tf["dataAbsentReason"]["coding"][0]["code"] == "asked-declined" and tf["category"][0]["coding"][0]["code"] == "survey"
    sq = [o for o in by["Observation"] if o["code"]["coding"][0]["code"] == "sleep_quality"][-1]
    assert sq["valueQuantity"]["code"] == "{score}"


def test_withdrawn_records_are_left_out_unless_history_is_asked_for(client, login):
    h = login("demo-fatima")
    rec = run_reaction(client, h, rt=650).json()["evidence"][0]
    r = client.post(f"/api/evidence/{rec['id']}/withdraw", json={"reason": "I was interrupted"}, headers=h)
    assert r.status_code == 200, r.text
    ident = lambda b: {o["identifier"][0]["value"]: o for o in check_r4(b).get("Observation", [])}  # noqa: E731
    assert str(rec["id"]) not in ident(export(client, h))
    o = ident(export(client, h, include_history=True))[str(rec["id"])]
    assert o["status"] == "entered-in-error"


def test_ids_are_stable_so_a_resend_updates_rather_than_duplicates(client, login):
    h = login("demo-fatima")
    a, b = export(client, h), export(client, h)
    assert [e["fullUrl"] for e in a["entry"]] == [e["fullUrl"] for e in b["entry"]]
    assert a["id"] != b["id"]          # each Bundle is its own document


def test_who_may_export(client, login):
    assert client.get("/api/participants/demo-fatima/fhir", headers=login("demo-dr-layla")).status_code == 200
    assert client.get("/api/participants/demo-fatima/fhir", headers=login("demo-mariam")).status_code == 404   # family
    assert client.get("/api/participants/demo-fatima/fhir", headers=login("demo-yousef")).status_code == 404
    assert client.get("/api/participants/demo-yousef/fhir", headers=login("demo-dr-layla")).status_code == 404  # not shared
    assert client.get("/api/participants/nobody/fhir", headers=login("demo-dr-layla")).status_code == 404


def test_export_is_audited_without_values(client, login):
    h = login("demo-dr-layla")
    export(client, h)
    rows = client.get("/api/participants/demo-fatima/audit", headers=h).json()
    ev = [r for r in rows if r["action"] == "fhir.exported"]
    assert ev and ev[0]["target"] == "fhir-export/0.1"


def test_leaves_out_what_is_not_part_of_the_record(client, login):
    h = login("demo-fatima")
    client.put("/api/me/background", json={"education": "university", "first_language": "arabic"}, headers=h)
    text = json.dumps(export(client, h))
    for word in ("university", "education", "first_language", "change-engine", "draft"):
        assert word not in text
    types = {e["resource"]["resourceType"] for e in export(client, h)["entry"]}
    assert types <= {"Patient", "Observation", "Provenance", "Consent"}


def test_consent_follows_the_latest_decision(client, login):
    h = login("demo-fatima")
    client.post("/api/consents", json={"scope": "voice_recording", "granted": True}, headers=h)
    client.post("/api/consents", json={"scope": "voice_recording", "granted": False}, headers=h)
    by = check_r4(export(client, h))
    voice = [c for c in by["Consent"] if c["category"][1]["coding"][0]["code"] == "voice_recording"]
    assert len(voice) == 1 and voice[0]["status"] == "inactive" and voice[0]["provision"]["type"] == "deny"


def test_validates_with_a_fhir_library_when_installed(client, login):
    """Stricter check where `fhir.resources` is installed (pip install fhir.resources). R4B shares these resources' R4 shape."""
    lib = pytest.importorskip("fhir.resources.R4B.bundle")
    lib.Bundle.model_validate(export(client, login("demo-fatima")))
