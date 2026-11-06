import hashlib
import uuid

import pytest
from conftest import sign_in

from app.db import (
    CareAttachment,
    CareAudio,
    CareConversation,
    CareEvent,
    CareMessage,
    CareParticipant,
    CareReceipt,
    Grant,
)
from app.media_store import object_path
from app.media_uploads import TYPES
from scripts.chat_fixtures import fixture

BASE = "/api/patients/patient-demo/messages"


def reserve(
    client, data, name="synthetic.png", command=None, aid=None, mime=None, kind=None
):
    extension = "." + name.split(".")[-1]
    body = {
        "client_message_id": command or str(uuid.uuid4()),
        "client_attachment_id": aid or str(uuid.uuid4()),
        "filename": name,
        "content_type": mime or TYPES[extension][1][0],
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }
    if kind:
        body["kind"] = kind
    response = client.post(BASE + "/threads/family/uploads", json=body)
    assert response.status_code == 200, response.text
    return response.json(), body


def verify(client, row, data):
    for start in range(row["offset"], len(data), 1024 * 1024):
        response = client.patch(
            BASE + "/uploads/" + row["id"],
            content=data[start : start + 1024 * 1024],
            headers={
                "upload-offset": str(start),
                "content-type": "application/offset+octet-stream",
            },
        )
        assert response.status_code == 200, response.text
    response = client.post(BASE + "/uploads/" + row["id"] + "/complete")
    assert response.status_code == 200, response.text
    return response.json()


def commit(client, rows, body="", command=None, **kw):
    return client.post(
        BASE + "/threads/family",
        json={
            "command_id": command or rows[0]["client_message_id"],
            "body": body,
            "attachment_ids": [r["id"] for r in rows],
            **kw,
        },
    )


@pytest.mark.parametrize(
    "extension",
    [
        "jpg",
        "png",
        "webp",
        "pdf",
        "docx",
        "xlsx",
        "txt",
        "csv",
        "wav",
        "mp3",
        "m4a",
        "ogg",
        "mp4",
        "webm",
    ],
)
def test_actual_media_storage_commit_and_private_retrieval(client, database, extension):
    sign_in(client)
    data = fixture(extension)
    row, _ = reserve(client, data, name="synthetic." + extension)
    ready = verify(client, row, data)
    assert ready["status"] == "ready", ready
    assert "object_key" not in ready and "original_key" not in ready
    assert client.get(BASE + f"/attachments/{row['id']}/content").status_code == 404
    response = commit(client, [row], "Synthetic attachment")
    assert response.status_code == 200, response.text
    message = response.json()
    item = message["attachments"][0]
    assert item["status"] == "committed" and item["size"] > 0
    downloaded = client.get(item["url"])
    assert downloaded.status_code == 200
    assert hashlib.sha256(downloaded.content).hexdigest() == item["sha256"]
    assert downloaded.headers["cache-control"] == "no-store"
    sign_in(client, "family")
    assert client.get(item["url"]).status_code == 200
    if item["kind"] in {"audio", "video"}:
        ranged = client.get(item["url"], headers={"Range": "bytes=0-31"})
        assert ranged.status_code == 206 and len(ranged.content) == 32
    if item["kind"] == "audio":
        assert item["duration_ms"] > 0 and len(item["waveform"]) == 64
    if item["kind"] == "video":
        assert item["duration_ms"] > 0 and item["thumbnail"]
    if item["kind"] == "image":
        assert item["width"] == 80 and item["height"] == 60
    assert (
        client.get(BASE + "/threads/participant").json()["messages"][0]["attachments"][
            0
        ]["id"]
        == row["id"]
    )
    sign_in(client, "clinician")
    assert client.get(item["url"]).status_code == 404
    with database() as db:
        stored = db.get(CareAttachment, row["id"])
        assert object_path(stored.object_key).is_file()
        assert db.query(CareAudio).count() == 0
        assert db.query(CareMessage).one().media == {}
        assert db.query(CareParticipant).count() == 2
        assert db.query(CareEvent).count() == 1


def test_resume_offsets_lost_response_and_duplicate_commit(client, database):
    sign_in(client)
    data = b"Synthetic row\n" * 100000
    row, body = reserve(client, data, "synthetic.txt")
    assert (
        client.post(BASE + "/threads/family/uploads", json=body).json()["id"]
        == row["id"]
    )
    assert (
        client.patch(
            BASE + "/uploads/" + row["id"],
            content=data[:500000],
            headers={"upload-offset": "0"},
        ).status_code
        == 200
    )
    assert (
        client.patch(
            BASE + "/uploads/" + row["id"],
            content=data[:500000],
            headers={"upload-offset": "0"},
        ).status_code
        == 409
    )
    current = client.get(BASE + "/uploads/" + row["id"]).json()
    assert current["offset"] == 500000
    ready = verify(client, current, data)
    assert ready["status"] == "ready"
    first = commit(client, [row], "Resume test")
    assert first.status_code == 200
    second = commit(client, [row], "Resume test")
    assert second.json()["id"] == first.json()["id"]
    assert (
        client.get(BASE + "/threads/family/command/" + row["client_message_id"]).json()[
            "message"
        ]["id"]
        == first.json()["id"]
    )
    with database() as db:
        assert (
            db.query(CareAttachment).count()
            == db.query(CareMessage).count()
            == db.query(CareEvent).count()
            == 1
        )


def test_uncommitted_bytes_are_truncated_on_offset_recovery(client, database):
    sign_in(client)
    data = fixture("txt")
    row, _ = reserve(client, data, "synthetic.txt")
    with database() as db:
        stored = db.get(CareAttachment, row["id"])
        path = object_path(stored.original_key)
        path.parent.mkdir(parents=True)
        path.write_bytes(b"uncommitted-crash-bytes")
    assert verify(client, row, data)["status"] == "ready"


@pytest.mark.parametrize(
    "mode",
    ["forged_mime", "forged_signature", "malware", "checksum", "scanner", "empty"],
)
def test_rejected_or_quarantined_media_is_never_published(
    client, database, monkeypatch, mode
):
    sign_in(client)
    data = fixture("png")
    if mode == "forged_mime":
        response = client.post(
            BASE + "/threads/family/uploads",
            json={
                "client_message_id": str(uuid.uuid4()),
                "client_attachment_id": str(uuid.uuid4()),
                "filename": "image.png",
                "content_type": "application/pdf",
                "size": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            },
        )
        assert response.status_code == 415
        return
    if mode == "empty":
        response = client.post(
            BASE + "/threads/family/uploads",
            json={
                "client_message_id": str(uuid.uuid4()),
                "client_attachment_id": str(uuid.uuid4()),
                "filename": "image.png",
                "content_type": "image/png",
                "size": 0,
                "sha256": hashlib.sha256(b"").hexdigest(),
            },
        )
        assert response.status_code == 422
        return
    if mode == "forged_signature":
        data = b"not an image"
    if mode == "malware":
        data = b"EICAR-STANDARD-ANTIVIRUS-TEST-FILE"
    row, _ = reserve(client, data, "bad.txt" if mode == "malware" else "image.png")
    if mode == "checksum":
        with database() as db:
            db.get(CareAttachment, row["id"]).expected_sha256 = "0" * 64
            db.commit()
    if mode == "scanner":
        monkeypatch.setattr(
            "app.config.settings.media_allow_unscanned_development", False
        )
    result = verify(client, row, data)
    assert result["status"] == ("quarantined" if mode == "scanner" else "rejected")
    assert commit(client, [row]).status_code == 409
    assert client.get(BASE + f"/attachments/{row['id']}/content").status_code == 404
    with database() as db:
        assert db.query(CareMessage).count() == 0


def test_attachment_batch_commit_is_atomic_and_reply_is_scoped(client, database):
    sign_in(client)
    key = str(uuid.uuid4())
    data = fixture("txt")
    a, _ = reserve(client, data, "a.txt", command=key)
    b, _ = reserve(client, data, "b.txt", command=key)
    verify(client, a, data)
    assert commit(client, [a, b]).status_code == 409
    with database() as db:
        assert db.query(CareMessage).count() == 0
    verify(client, b, data)
    first = commit(client, [a, b], "Two attachments").json()
    assert len(first["attachments"]) == 2
    reply = client.post(
        BASE + "/threads/family",
        json={
            "command_id": str(uuid.uuid4()),
            "body": "Reply",
            "reply_to_id": first["id"],
        },
    )
    assert reply.status_code == 200 and reply.json()["reply_to"]["id"] == first["id"]
    assert (
        client.post(
            BASE + "/threads/clinician",
            json={
                "command_id": str(uuid.uuid4()),
                "body": "Wrong pair",
                "reply_to_id": first["id"],
            },
        ).status_code
        == 404
    )


def test_receipts_search_withdrawal_and_revoked_media(client, database):
    sign_in(client)
    data = fixture("wav")
    row, _ = reserve(client, data, "sound.wav")
    verify(client, row, data)
    message = commit(client, [row], "Unique search phrase").json()
    url = message["attachments"][0]["url"]
    sign_in(client, "family")
    receipts = BASE + "/threads/participant/receipts"
    assert (
        client.post(
            receipts,
            json={"message_ids": [message["id"]], "event": "playback_completed"},
        ).status_code
        == 409
    )
    for event in ["delivered", "playback_started", "playback_completed"]:
        assert (
            client.post(
                receipts, json={"message_ids": [message["id"]], "event": event}
            ).json()["acknowledged"]
            == 1
        )
        assert (
            client.post(
                receipts, json={"message_ids": [message["id"]], "event": event}
            ).json()["acknowledged"]
            == 0
        )
    sign_in(client)
    result = client.get(
        BASE + "/threads/family", params={"q": "search phrase", "kind": "audio"}
    ).json()
    assert len(result["messages"]) == 1
    assert result["messages"][0]["receipt"]["playback_completed_at"]
    assert (
        client.get(BASE + "/threads/family", params={"q": "%"}).json()["messages"] == []
    )
    assert (
        client.post(
            BASE + f"/threads/family/messages/{message['id']}/withdraw"
        ).status_code
        == 200
    )
    assert client.get(url).status_code == 404
    hidden = client.get(BASE + "/threads/family").json()["messages"][0]
    assert hidden["body"] == "Message withdrawn" and hidden["attachments"] == []
    with database() as db:
        assert object_path(db.get(CareAttachment, row["id"]).object_key).is_file()
        assert db.query(CareReceipt).count() == 1
        assert db.query(CareConversation).one().sequence == 5


def test_owner_upload_scope_expiry_cancellation_and_cleanup(client, database):
    from app.media_maintenance import cleanup

    sign_in(client)
    data = fixture("txt")
    row, _ = reserve(client, data, "safe.txt")
    verify(client, row, data)
    sign_in(client, "family")
    assert client.get(BASE + "/uploads/" + row["id"]).status_code == 404
    sign_in(client)
    with database() as db:
        obj = db.get(CareAttachment, row["id"])
        key = obj.object_key
        obj.expires_at = "2000-01-01T00:00:00+00:00"
        db.commit()
    assert client.get(BASE + "/uploads/" + row["id"]).status_code == 410
    with database() as db:
        assert cleanup(db) == 1
        assert cleanup(db) == 0
    assert not object_path(key).exists()
    row, _ = reserve(client, data, "safe.txt")
    verify(client, row, data)
    with database() as db:
        db.query(Grant).filter_by(
            user_id="family", patient_id="patient-demo"
        ).one().active = False
        db.commit()
    assert client.get(BASE + "/uploads/" + row["id"]).status_code == 403


def test_private_object_paths_and_configured_limits(client, monkeypatch):
    from fastapi import HTTPException

    for value in ["../secret", "/absolute", "a/../../secret", "a\\secret", "a//b"]:
        with pytest.raises(HTTPException):
            object_path(value)
    sign_in(client)
    policy = client.get(BASE + "/media-policy").json()
    assert policy["limits"]["video"] > 0
    monkeypatch.setattr("app.config.settings.media_uploads_per_day", 1)
    data = fixture("txt")
    reserve(client, data, "one.txt")
    response = client.post(
        BASE + "/threads/family/uploads",
        json={
            "client_message_id": str(uuid.uuid4()),
            "client_attachment_id": str(uuid.uuid4()),
            "filename": "two.txt",
            "content_type": "text/plain",
            "size": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        },
    )
    assert response.status_code == 429
