import uuid

from conftest import sign_in

from app.ai import gateway
from app.db import Record

TEXT = "Synthetic appointment note. Appointment date: 2026-11-18. Transport assistance requested."


def source(client):
    r = client.post(
        "/api/patients/patient-demo/documents",
        json={
            "title": "Fictional appointment note",
            "text": TEXT,
            "source_date": "2026-11-05",
            "synthetic": True,
        },
    )
    assert r.status_code == 200, r.text
    return r.json()


def fake_extraction(
    monkeypatch, value="2026-11-18", quote="Appointment date: 2026-11-18."
):
    async def structured(*args, **kwargs):
        return {
            "facts": [
                {
                    "label": "Appointment date",
                    "value": value,
                    "unit": "",
                    "quote": quote,
                }
            ]
        }

    monkeypatch.setattr(gateway, "structured", structured)


def extract(client, doc):
    return client.post(
        f"/api/patients/patient-demo/documents/{doc['id']}/extract",
        json={"expected_version": doc["version"]},
    )


def verify(client, doc, decision="verify", value=None):
    return client.post(
        f"/api/patients/patient-demo/documents/{doc['id']}/candidates/{doc['payload']['candidates'][0]['id']}/review",
        json={
            "expected_version": doc["version"],
            "decision": decision,
            "value": value,
            "reason": "Compared with fictional source text",
        },
    )


def test_document_scope_and_synthetic_only(client):
    sign_in(client, "family")
    assert client.get("/api/patients/patient-demo/documents").status_code == 403
    sign_in(client, "clinician")
    assert client.get("/api/patients/patient-other/documents").status_code == 403
    d = source(client)
    assert d["status"] == "awaiting_extraction" and len(d["payload"]["sha256"]) == 64
    assert (
        client.post(
            "/api/patients/patient-demo/documents",
            json={
                "title": "Real",
                "text": TEXT,
                "source_date": "2026-11-05",
                "synthetic": False,
            },
        ).status_code
        == 422
    )


def test_extraction_and_verification_never_activate_plan(client, monkeypatch):
    sign_in(client, "clinician")
    fake_extraction(monkeypatch)
    doc = source(client)
    result = extract(client, doc)
    assert result.status_code == 200, result.text
    doc = result.json()
    assert doc["status"] == "awaiting_verification"
    assert doc["payload"]["candidates"][0]["status"] == "unverified"
    assert extract(client, doc).status_code == 409
    result = verify(client, doc)
    assert result.status_code == 200
    verified = result.json()
    assert verified["status"] == "reviewed"
    assert verified["payload"]["candidates"][0]["reviewed_by"] == "clinician"
    assert verify(client, doc).status_code == 409
    plans = [
        x
        for x in client.get("/api/patients/patient-demo/workspace").json()["records"]
        if x["kind"] == "plan"
    ]
    assert len(plans) == 1 and plans[0]["id"] == "plan-demo"


def test_unsupported_extraction_rejected(client, monkeypatch):
    sign_in(client, "clinician")
    fake_extraction(monkeypatch, value="2099-01-01")
    doc = source(client)
    assert extract(client, doc).status_code == 422
    stored = client.get("/api/patients/patient-demo/documents").json()[0]
    assert stored["version"] == 1 and stored["payload"]["candidates"] == []


def test_source_correction_invalidates_linked_draft(client, monkeypatch, database):
    sign_in(client, "clinician")
    fake_extraction(monkeypatch)
    doc = extract(client, source(client)).json()
    # A partially verified source is never used automatically.
    body = {
        "title": "Appointment support",
        "instructions": "Check the date with your helper.",
        "template": "appointment_preparation",
        "source_ids": [doc["id"]],
    }
    assert client.post("/api/patients/patient-demo/plans", json=body).status_code == 409
    doc = verify(client, doc).json()
    plan = client.post("/api/patients/patient-demo/plans", json=body).json()
    assert plan["payload"]["source_versions"][doc["id"]] == doc["version"]
    with database() as db:
        db.add(
            Record(
                id="source-linked-draft",
                patient_id="patient-demo",
                kind="draft",
                status="awaiting_human_review",
                payload={"source_versions": {doc["id"]: doc["version"]}},
            )
        )
        db.commit()
    changed = verify(client, doc, "correct", "2026-11-19")
    assert changed.status_code == 200
    response = client.post(
        f"/api/patients/patient-demo/plans/{plan['id']}/approve",
        json={"command_id": str(uuid.uuid4()), "expected_version": plan["version"]},
    )
    assert response.status_code == 409
    data = client.get("/api/patients/patient-demo/workspace").json()["records"]
    assert any(
        r["kind"] == "case" and r["payload"].get("document_id") == doc["id"]
        for r in data
    )
    assert (
        next(r for r in data if r["id"] == "source-linked-draft")["status"]
        == "source_changed"
    )


def test_correction_flags_approved_plan_and_blocks_stale_task(client, monkeypatch):
    sign_in(client, "clinician")
    fake_extraction(monkeypatch)
    doc = verify(client, extract(client, source(client)).json()).json()
    plan = client.post(
        "/api/patients/patient-demo/plans",
        json={
            "title": "Appointment support",
            "instructions": "Check the date.",
            "template": "appointment_preparation",
            "source_ids": [doc["id"]],
        },
    ).json()
    approved = client.post(
        f"/api/patients/patient-demo/plans/{plan['id']}/approve",
        json={"command_id": str(uuid.uuid4()), "expected_version": plan["version"]},
    )
    assert approved.status_code == 200
    assert verify(client, doc, "correct", "2026-11-19").status_code == 200
    sign_in(client)
    data = client.get("/api/patients/patient-demo/workspace").json()["records"]
    assert (
        next(p for p in data if p["id"] == plan["id"])["payload"][
            "source_review_required"
        ]
        is True
    )
    task = next(t for t in data if t["kind"] == "task" and t["status"] == "pending")
    assert (
        client.post(
            f"/api/patients/patient-demo/tasks/{task['id']}/response",
            json={
                "command_id": str(uuid.uuid4()),
                "expected_version": task["version"],
                "response": "completed",
            },
        ).status_code
        == 409
    )
    reply = client.post(
        "/api/patients/patient-demo/companion", json={"text": "read my plan"}
    ).json()
    assert "corrected" in reply["explanation"] and "review" in reply["explanation"]


def test_draft_source_qa_and_human_review_status(client, monkeypatch):
    sign_in(client, "clinician")
    case = client.post(
        "/api/patients/patient-demo/concerns",
        json={"command_id": str(uuid.uuid4()), "text": "Transport help requested"},
    ).json()

    async def bad(*a, **kw):
        return {
            "items": [{"source_id": "invented", "observation": "Wrong source"}],
            "missing_information": [],
        }

    monkeypatch.setattr(gateway, "structured", bad)
    path = f"/api/patients/patient-demo/cases/{case['id']}/evidence-draft"
    assert client.post(path).status_code == 422

    async def good(*a, **kw):
        return {
            "items": [
                {
                    "source_id": case["id"],
                    "observation": "Participant requests transport help.",
                }
            ],
            "missing_information": ["Appointment time"],
        }

    monkeypatch.setattr(gateway, "structured", good)
    r = client.post(path)
    assert r.status_code == 200
    assert (
        r.json()["status"] == "awaiting_human_review"
        and r.json()["payload"]["clinical_use"] is False
    )


def test_extraction_rechecks_source_revision_after_model_call(
    client, monkeypatch, database
):
    sign_in(client, "clinician")
    doc = source(client)

    async def changed(*a, **kw):
        with database() as db:
            r = db.get(Record, doc["id"])
            r.version += 1
            db.commit()
        return {
            "facts": [
                {
                    "label": "Date",
                    "value": "2026-11-18",
                    "unit": "",
                    "quote": "Appointment date: 2026-11-18.",
                }
            ]
        }

    monkeypatch.setattr(gateway, "structured", changed)
    assert extract(client, doc).status_code == 409
