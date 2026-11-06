import json
import uuid

import pytest
from conftest import sign_in

from app.db import Audit, CareMessage, Grant, Outbox, User

BASE = "/api/patients/patient-demo/messages"


def send(
    client,
    peer="family",
    text="Please help me prepare for my appointment.",
    command=None,
):
    return client.post(
        BASE + f"/threads/{peer}",
        json={"body": text, "command_id": command or str(uuid.uuid4())},
    )


@pytest.mark.parametrize(
    "sender,recipient",
    [("participant", "family"), ("family", "clinician"), ("clinician", "participant")],
)
def test_care_circle_directions_and_explicit_opening(
    client, database, sender, recipient
):
    sign_in(client, sender)
    before = client.get(BASE + "/inbox").json()
    assert recipient in [c["id"] for c in before["contacts"]]
    result = send(client, recipient)
    assert result.status_code == 200
    message = result.json()
    assert message["state"] == "saved_in_app"
    assert message["opened_at"] is None
    # Sending and simply fetching do not fabricate an opening acknowledgement.
    assert (
        client.post(
            BASE + f"/threads/{recipient}/opened", json={"message_ids": [message["id"]]}
        ).status_code
        == 404
    )
    sign_in(client, recipient)
    inbox = client.get(BASE + "/inbox").json()
    assert next(c for c in inbox["contacts"] if c["id"] == sender)["unopened"] == 1
    thread = client.get(BASE + f"/threads/{sender}").json()
    assert thread["messages"][0]["opened_at"] is None
    assert thread["messages"][0]["command_id"] is None
    result = client.post(
        BASE + f"/threads/{sender}/opened", json={"message_ids": [message["id"]]}
    )
    assert result.status_code == 200
    assert result.json()["acknowledged"] == 1
    at = result.json()["messages"][0]["opened_at"]
    assert (
        client.post(
            BASE + f"/threads/{sender}/opened", json={"message_ids": [message["id"]]}
        ).json()["acknowledged"]
        == 0
    )
    assert client.get(BASE + "/inbox").json()["unopened"] == 0
    sign_in(client, sender)
    updated = client.get(BASE + f"/threads/{recipient}").json()["messages"][0]
    assert updated["state"] == "opened_in_app" and updated["opened_at"] == at
    with database() as db:
        assert db.query(Audit).filter_by(action="message.opened").count() == 1
        assert db.query(Outbox).filter_by(event_type="message.saved").count() == 0


def test_retry_idempotence_and_conflicting_content(client, database):
    sign_in(client)
    key = str(uuid.uuid4())
    first = send(client, command=key).json()
    assert send(client, command=key).json() == first
    assert send(client, text="Different text", command=key).status_code == 409
    assert send(client, peer="clinician", command=key).status_code == 409
    with database() as db:
        assert db.query(CareMessage).count() == 1
        assert db.query(Audit).filter_by(action="message.saved").count() == 1


def test_direct_threads_are_private_even_to_other_clinicians(client, database):
    sign_in(client, "clinician")
    revision = client.get(BASE + "/inbox").json()["revision"]
    sign_in(client)
    row = send(client, text="PRIVATE FAMILY CONVERSATION").json()
    sign_in(client, "clinician")
    assert client.get(BASE + "/inbox").json()["revision"] == revision
    assert client.get(BASE + "/threads/participant").json()["messages"] == []
    assert client.get(BASE + "/threads/family").json()["messages"] == []
    assert (
        client.get(
            BASE + "/threads/participant", params={"before": row["id"]}
        ).status_code
        == 404
    )
    assert (
        client.post(
            BASE + "/threads/participant/opened", json={"message_ids": [row["id"]]}
        ).status_code
        == 404
    )
    assert (
        "PRIVATE FAMILY CONVERSATION"
        not in client.get("/api/patients/patient-demo/workspace").text
    )
    assert (
        "PRIVATE FAMILY CONVERSATION"
        not in client.get("/api/patients/patient-demo/reports/weekly").text
    )
    with database() as db:
        assert "PRIVATE FAMILY CONVERSATION" not in json.dumps(
            [a.detail for a in db.query(Audit)]
        )


def test_permission_revocation_blocks_history_retry_and_acknowledgement(
    client, database
):
    sign_in(client)
    command = str(uuid.uuid4())
    row = send(client, command=command).json()
    with database() as db:
        grant = (
            db.query(Grant).filter_by(user_id="family", patient_id="patient-demo").one()
        )
        grant.scopes = ["summary", "help"]
        db.commit()
    assert "family" not in [
        p["id"] for p in client.get(BASE + "/inbox").json()["contacts"]
    ]
    assert client.get(BASE + "/threads/family").status_code == 403
    assert send(client, command=command).status_code == 403
    sign_in(client, "family")
    assert client.get(BASE + "/inbox").status_code == 403
    assert (
        client.post(
            BASE + "/threads/participant/opened", json={"message_ids": [row["id"]]}
        ).status_code
        == 403
    )


def test_all_opened_ids_validated_before_any_write(client, database):
    sign_in(client)
    a = send(client, text="First").json()
    b = send(client, peer="clinician", text="Doctor only").json()
    sign_in(client, "family")
    result = client.post(
        BASE + "/threads/participant/opened", json={"message_ids": [a["id"], b["id"]]}
    )
    assert result.status_code == 404
    with database() as db:
        assert db.get(CareMessage, a["id"]).opened_at is None
        assert db.query(Audit).filter_by(action="message.opened").count() == 0


def test_cursor_pagination_is_stable_on_equal_timestamps(client, database):
    with database() as db:
        for i in range(9):
            db.add(
                CareMessage(
                    id=f"m-{i:02}",
                    patient_id="patient-demo",
                    sender_id="participant",
                    recipient_id="family",
                    body=str(i),
                    command_id=str(uuid.uuid4()),
                    created_at="2026-11-06T10:00:00+00:00",
                )
            )
        db.commit()
    sign_in(client, "family")
    seen, cursor = [], None
    for _ in range(3):
        params = {"limit": 3}
        if cursor:
            params["before"] = cursor
        page = client.get(BASE + "/threads/participant", params=params).json()
        seen += [r["id"] for r in page["messages"]]
        cursor = page["next_before"]
    assert len(set(seen)) == 9 and cursor is None
    assert seen[:3] == ["m-06", "m-07", "m-08"]
    assert (
        client.get(BASE + "/threads/participant", params={"limit": 101}).status_code
        == 422
    )
    assert (
        client.get(
            BASE + "/threads/participant", params={"before": "unknown"}
        ).status_code
        == 404
    )


def test_auth_csrf_roles_and_patient_isolation(client, database):
    assert client.get(BASE + "/inbox").status_code == 401
    sign_in(client)
    client.headers.pop("X-CSRF-Token")
    assert send(client).status_code == 403
    sign_in(client)
    assert client.get("/api/patients/patient-other/messages/inbox").status_code == 403
    assert send(client, peer="other").status_code == 403
    assert send(client, peer="participant").status_code == 403
    assert send(client, peer="missing").status_code == 403
    with database() as db:
        db.get(User, "family").org = "unrelated"
        db.commit()
    assert send(client).status_code == 403
    with database() as db:
        db.get(User, "family").org = "demo"
        db.get(User, "family").role = "unassigned"
        db.commit()
    assert send(client).status_code == 403


def test_same_pair_different_patient_cannot_reuse_command_or_cursor(client, database):
    sign_in(client)
    key = str(uuid.uuid4())
    row = send(client, command=key).json()
    with database() as db:
        for user in ["participant", "family"]:
            db.add(
                Grant(
                    user_id=user,
                    patient_id="patient-other",
                    scopes=["summary", "messages"],
                )
            )
        db.commit()
    other = "/api/patients/patient-other/messages/threads/family"
    assert (
        client.post(
            other,
            json={
                "body": "Please help me prepare for my appointment.",
                "command_id": key,
            },
        ).status_code
        == 409
    )
    assert client.get(other, params={"before": row["id"]}).status_code == 404
    assert client.get(other).json()["messages"] == []


@pytest.mark.parametrize("text", ["", "  \n  ", "x" * 2001, "message\x00bad"])
def test_text_validation(client, text):
    sign_in(client)
    assert send(client, text=text).status_code == 422


def test_plain_text_and_payload_cannot_claim_delivery(client):
    sign_in(client)
    text = '<img src=x onerror="alert(1)">\nPlain text only.'
    result = send(client, text=text)
    assert result.status_code == 200
    assert result.json()["body"] == text
    assert result.json()["state"] == "saved_in_app"
    assert (
        client.post(
            BASE + "/threads/family",
            json={
                "body": "Hello",
                "command_id": str(uuid.uuid4()),
                "opened_at": "now",
                "sender_id": "clinician",
            },
        ).status_code
        == 422
    )


@pytest.mark.parametrize(
    "text,screen",
    [
        ("open messages", "messages"),
        ("open inbox", "messages"),
        ("open weekly summary", "weekly"),
    ],
)
def test_companion_navigation_does_not_send_or_open_messages(
    client, database, text, screen
):
    sign_in(client)
    result = client.post("/api/patients/patient-demo/companion", json={"text": text})
    assert result.status_code == 200
    assert result.json()["intent"] == "navigate"
    assert result.json()["screen"] == screen
    with database() as db:
        assert db.query(CareMessage).count() == 0
        if screen == "messages":
            db.query(Grant).filter_by(
                user_id="participant", patient_id="patient-demo"
            ).one().scopes = ["summary"]
            db.commit()
    if screen == "messages":
        assert (
            client.post(
                "/api/patients/patient-demo/companion", json={"text": text}
            ).status_code
            == 403
        )
