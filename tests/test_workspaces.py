from conftest import sign_in

from app.db import Grant, Patient, Record


def test_workspace_directory_requires_current_summary_scope_and_same_org(
    client, database
):
    with database() as db:
        for key, org, scopes, active in [
            ("help-only", "demo", ["help"], True),
            ("inactive", "demo", ["summary"], False),
            ("foreign", "different-org", ["summary"], True),
            ("readable", "demo", ["summary"], True),
        ]:
            db.add(Patient(id=key, name="Z " + key, org=org, age=65, region="Dubai"))
            db.flush()
            db.add(
                Grant(user_id="clinician", patient_id=key, scopes=scopes, active=active)
            )
        db.commit()
    sign_in(client, "clinician")
    result = client.get("/api/patients")
    assert result.status_code == 200
    directory = result.json()
    assert [row["id"] for row in directory] == ["patient-demo", "readable"]
    assert directory[1]["scopes"] == ["summary"]
    for key in ["help-only", "inactive", "foreign"]:
        assert client.get(f"/api/patients/{key}/workspace").status_code == 403


def test_family_multiple_workspaces_remain_record_and_role_scoped(client, database):
    with database() as db:
        db.add(
            Grant(
                user_id="family",
                patient_id="patient-other",
                scopes=["summary", "help", "messages"],
            )
        )
        db.add_all(
            [
                Record(
                    id="other-plan",
                    patient_id="patient-other",
                    kind="plan",
                    status="approved",
                    payload={"title": "Other approved plan"},
                ),
                Record(
                    id="other-task",
                    patient_id="patient-other",
                    kind="task",
                    status="pending",
                    payload={"title": "Other task", "plan_id": "other-plan"},
                ),
                Record(
                    id="other-case",
                    patient_id="patient-other",
                    kind="case",
                    status="awaiting_review",
                    payload={"concern": "Private clinical concern"},
                ),
                Record(
                    id="other-help",
                    patient_id="patient-other",
                    kind="help",
                    status="requested",
                    payload={
                        "text": "Private request",
                        "sender_id": "other",
                        "recipient_id": "clinician",
                    },
                ),
            ]
        )
        db.commit()
    sign_in(client, "family")
    assert {row["id"] for row in client.get("/api/patients").json()} == {
        "patient-demo",
        "patient-other",
    }
    result = client.get("/api/patients/patient-other/workspace").json()
    assert {row["id"] for row in result["records"]} == {"other-plan", "other-task"}
    assert "task-01" not in {row["id"] for row in result["records"]}
    assert client.get("/api/patients/patient-other/documents").status_code == 403
    assert client.post(
        "/api/patients/patient-other/tasks/task-01/response",
        json={
            "command_id": "workspace-cross-patient-command",
            "expected_version": 1,
            "response": "completed",
        },
    ).status_code in {403, 404}


def test_revoked_workspace_disappears_and_stale_links_fail(client, database):
    sign_in(client, "family")
    assert client.get("/api/patients").json()[0]["id"] == "patient-demo"
    with database() as db:
        db.query(Grant).filter_by(
            user_id="family", patient_id="patient-demo"
        ).one().active = False
        db.commit()
    assert client.get("/api/patients").json() == []
    assert client.get("/api/patients/patient-demo/workspace").status_code == 403
    assert client.get("/api/patients/patient-demo/reports/weekly").status_code == 403


def test_no_summary_scope_does_not_expose_patient_directory_metadata(client, database):
    with database() as db:
        db.query(Grant).filter_by(
            user_id="family", patient_id="patient-demo"
        ).one().scopes = ["messages", "help"]
        db.commit()
    sign_in(client, "family")
    assert client.get("/api/patients").json() == []


def test_participant_access_directory_and_revocation(client):
    sign_in(client)
    path = "/api/patients/patient-demo/grants"
    result = client.get(path)
    assert result.status_code == 200
    grants = {row["actor_id"]: row for row in result.json()}
    assert set(grants) == {"participant", "family", "clinician"}
    assert grants["participant"]["can_revoke"] is False
    assert grants["family"]["can_revoke"] is True
    assert client.get("/api/patients/patient-other/grants").status_code == 403
    assert client.post(path + "/family/revoke").status_code == 200
    family = next(row for row in client.get(path).json() if row["actor_id"] == "family")
    assert not family["active"] and not family["can_revoke"]
    for role in ["family", "clinician", "other"]:
        sign_in(client, role)
        assert client.get(path).status_code == 403
