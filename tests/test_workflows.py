import uuid

from conftest import sign_in


def cmd(**kw):
    return {"command_id": str(uuid.uuid4()), "expected_version": 1, **kw}


def test_authentication_required(client):
    assert client.get("/api/patients").status_code == 401


def test_password_not_returned(client):
    r = client.post("/api/login", json={"username": "participant", "password": "wrong"})
    assert r.status_code == 401
    sign_in(client)
    assert "password" not in client.get("/api/session").text


def test_csrf_and_cross_patient(client):
    sign_in(client)
    assert client.get("/api/patients/patient-other/workspace").status_code == 403
    client.headers.pop("X-CSRF-Token")
    assert (
        client.post(
            "/api/patients/patient-demo/preferences", json={"text_size": "large"}
        ).status_code
        == 403
    )


def test_task_idempotence_and_conflict(client):
    sign_in(client)
    body = cmd(response="completed")
    url = "/api/patients/patient-demo/tasks/task-01/response"
    a = client.post(url, json=body)
    assert a.status_code == 200
    assert client.post(url, json=body).json() == a.json()
    assert client.post(url, json=body | {"response": "skipped"}).status_code == 409
    assert client.post(url, json=cmd(response="skipped")).status_code == 409
    assert (
        client.get("/api/patients/patient-demo/report").json()["counts"]["completed"]
        == 1
    )


def test_family_cannot_confirm_patient_tasks(client):
    sign_in(client, "family")
    assert (
        client.post(
            "/api/patients/patient-demo/tasks/task-01/response",
            json=cmd(response="completed"),
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/patients/patient-demo/plans",
            json={
                "title": "Test",
                "instructions": "Test task",
                "template": "appointment_preparation",
            },
        ).status_code
        == 403
    )


def test_help_round_trip(client):
    sign_in(client)
    body = {
        "command_id": str(uuid.uuid4()),
        "recipient_id": "family",
        "text": "Transport help",
    }
    h = client.post("/api/patients/patient-demo/help", json=body).json()
    assert (
        client.post("/api/patients/patient-demo/help", json=body).json()["id"]
        == h["id"]
    )
    sign_in(client, "family")
    r = client.post(f"/api/patients/patient-demo/help/{h['id']}/accept", json=cmd())
    assert r.status_code == 200 and r.json()["status"] == "accepted"


def test_revocation_blocks_read_and_send(client):
    sign_in(client)
    assert (
        client.post("/api/patients/patient-demo/grants/family/revoke").status_code
        == 200
    )
    assert (
        client.post(
            "/api/patients/patient-demo/help",
            json={
                "command_id": str(uuid.uuid4()),
                "recipient_id": "family",
                "text": "Help",
            },
        ).status_code
        == 403
    )
    sign_in(client, "family")
    assert client.get("/api/patients/patient-demo/workspace").status_code == 403


def test_case_review_and_urgent_hold(client):
    sign_in(client)
    r = client.post(
        "/api/patients/patient-demo/concerns",
        json={
            "command_id": str(uuid.uuid4()),
            "text": "New difficulty with appointments",
        },
    ).json()
    sign_in(client, "family")
    assert (
        client.post(
            f"/api/patients/patient-demo/cases/{r['id']}/review",
            json=cmd(decision="approve", rationale="Reviewed"),
        ).status_code
        == 403
    )
    sign_in(client, "clinician")
    x = client.post(
        f"/api/patients/patient-demo/cases/{r['id']}/review",
        json=cmd(decision="approve", rationale="Human review complete"),
    )
    assert x.status_code == 200
    assert x.json()["payload"]["reviewer"] == "clinician"
    u = client.post(
        "/api/patients/patient-demo/concerns",
        json={
            "command_id": str(uuid.uuid4()),
            "text": "Sudden change reported",
            "urgent_reported": True,
        },
    ).json()
    assert (
        client.post(
            f"/api/patients/patient-demo/cases/{u['id']}/review",
            json=cmd(decision="approve", rationale="Try routine"),
        ).status_code
        == 409
    )


def test_plan_signed_revision_updates_mobile(client):
    sign_in(client, "clinician")
    p = client.post(
        "/api/patients/patient-demo/plans",
        json={
            "title": "Prepare for appointment",
            "instructions": "Check appointment date with your chosen helper.",
            "template": "appointment_preparation",
        },
    ).json()
    body = cmd()
    url = f"/api/patients/patient-demo/plans/{p['id']}/approve"
    r = client.post(url, json=body)
    assert r.status_code == 200
    assert client.post(url, json=body).json() == r.json()
    sign_in(client)
    rows = client.get("/api/patients/patient-demo/workspace").json()["records"]
    assert sum(x["kind"] == "plan" and x["status"] == "approved" for x in rows) == 1
    assert any(x["kind"] == "task" and x["payload"]["plan_id"] == p["id"] for x in rows)
    assert (
        client.post(
            "/api/patients/patient-demo/tasks/task-01/response",
            json=cmd(response="completed"),
        ).status_code
        == 409
    )
    assert client.get("/api/patients/patient-demo/report").json()["denominator"] == 1


def test_unapproved_plan_not_visible_to_family(client):
    sign_in(client, "clinician")
    p = client.post(
        "/api/patients/patient-demo/plans",
        json={
            "title": "Not yet reviewed",
            "instructions": "Draft only",
            "template": "social_contact",
        },
    ).json()
    sign_in(client, "family")
    assert all(
        r["id"] != p["id"]
        for r in client.get("/api/patients/patient-demo/workspace").json()["records"]
    )


def test_companion_local_and_fallback(client):
    sign_in(client)
    for text, expected in [
        ("Open settings", "navigate"),
        ("make text larger", "set_text_size"),
        ("help me with transport", "prepare_help"),
        ("invent a diagnosis", "clarify"),
        ("sudden confusion", "clinical_review"),
    ]:
        r = client.post("/api/patients/patient-demo/companion", json={"text": text})
        assert r.status_code == 200
        assert r.json()["intent"] == expected
    assert (
        client.get("/api/patients/patient-demo/report").json()["counts"]["pending"] == 2
    )


def test_invalid_assessment_and_family_projection(client):
    sign_in(client)
    for d in [0, 7, 14]:
        r = client.post(
            "/api/patients/patient-demo/observations",
            json={
                "time_days": d,
                "value": 0.1,
                "quality": "usable",
                "protocol": "research-test-v1",
                "mode": "self",
            },
        )
        assert r.status_code == 200
    sign_in(client, "family")
    data = client.get("/api/patients/patient-demo/workspace").json()
    assert all(
        r["kind"] not in ["model", "case", "observation"] for r in data["records"]
    )


def test_invalid_audio_and_disabled_provider(client):
    sign_in(client)
    r = client.post(
        "/api/patients/patient-demo/voice/transcribe",
        files={"audio": ("fake.wav", b"bad", "audio/wav")},
    )
    assert r.status_code == 415
    sign_in(client, "clinician")
    r = client.get("/api/providers/catalog")
    assert r.status_code == 200


def test_logout_expires_session(client):
    sign_in(client)
    assert client.post("/api/logout").status_code == 200
    assert client.get("/api/patients").status_code == 401


def test_foreground_revision_changes_only_with_domain_state(client):
    sign_in(client)
    url = "/api/patients/patient-demo/changes"
    first = client.get(url).json()["revision"]
    client.get("/api/patients/patient-demo/workspace")
    assert client.get(url).json()["revision"] == first
    client.post(
        "/api/patients/patient-demo/tasks/task-01/response",
        json=cmd(response="completed"),
    )
    assert client.get(url).json()["revision"] != first
    assert client.get("/api/patients/patient-other/changes").status_code == 403
