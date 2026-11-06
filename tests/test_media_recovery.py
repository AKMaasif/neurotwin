"""Recovery paths use real private objects and preserve explicit-send boundaries."""

import hashlib

from conftest import sign_in
from test_multimedia import BASE, commit, reserve, verify
from test_voice_notes import upload, wav

from app.db import CareAttachment, CareAudio, CareMessage
from app.media_maintenance import migrate_legacy
from app.media_store import object_path


def test_verified_voice_recovery_is_owner_only_and_not_a_send(client, database):
    sign_in(client)
    data = wav()
    row, _ = reserve(client, data, "voice.wav", kind="voice")
    preview = BASE + "/uploads/" + row["id"] + "/preview"
    assert client.get(preview).status_code == 404
    ready = verify(client, row, data)
    assert ready["status"] == "ready"
    response = client.get(preview)
    assert (
        response.status_code == 200 and response.headers["cache-control"] == "no-store"
    )
    assert response.content[:4] == b"RIFF"
    with database() as db:
        assert db.query(CareMessage).count() == 0
    sign_in(client, "family")
    assert client.get(preview).status_code == 404
    sign_in(client)
    assert client.delete(BASE + "/uploads/" + row["id"]).status_code == 200
    assert client.get(preview).status_code == 404


def test_modified_ready_object_cannot_be_committed(client, database):
    sign_in(client)
    data = b"Synthetic test content"
    row, _ = reserve(client, data, "test.txt")
    assert verify(client, row, data)["status"] == "ready"
    with database() as db:
        object_path(db.get(CareAttachment, row["id"]).object_key).write_bytes(
            b"tampered"
        )
    assert commit(client, [row]).status_code == 409
    with database() as db:
        assert db.query(CareMessage).count() == 0


def test_legacy_binary_copy_is_verified_idempotent_and_still_playable(client, database):
    sign_in(client)
    saved = upload(client).json()
    url = BASE + "/voice/" + saved["id"]
    original = client.get(url).content
    with database() as db:
        # Recreate a genuine pre-object-store row while retaining its canonical message.
        attached = db.query(CareAttachment).filter_by(message_id=saved["id"]).one()
        db.delete(attached)
        db.query(CareAudio).filter_by(message_id=saved["id"]).one().data = original
        db.commit()
        assert migrate_legacy(db) == 1
        assert migrate_legacy(db) == 0
        assert db.query(CareAudio).one().data == b""
        attached = db.query(CareAttachment).filter_by(message_id=saved["id"]).one()
        assert attached.detail["sha256"] == hashlib.sha256(original).hexdigest()
    assert client.get(url).content == original


def test_quarantined_upload_can_retry_only_after_scanner_configuration(
    client, monkeypatch
):
    import subprocess

    from app.config import settings

    sign_in(client)
    monkeypatch.setattr(settings, "media_allow_unscanned_development", False)
    data = b"Synthetic scanner recovery contract"
    row, _ = reserve(client, data, "test.txt")
    assert verify(client, row, data)["status"] == "quarantined"
    endpoint = BASE + "/uploads/" + row["id"] + "/complete?retry_scan=true"
    assert client.post(endpoint).json()["status"] == "quarantined"
    real_run = subprocess.run

    def scanner_contract(args, **kwargs):
        if args[0] == "test-scanner-contract":
            return subprocess.CompletedProcess(args, 0, b"", b"")
        return real_run(args, **kwargs)

    monkeypatch.setattr(settings, "media_scan_executable", "test-scanner-contract")
    monkeypatch.setattr(subprocess, "run", scanner_contract)
    # This verifies the scanner adapter/retry contract, not real antivirus efficacy.
    assert client.post(endpoint).json()["status"] == "ready"
    assert commit(client, [row]).status_code == 200


def test_production_requires_https_and_sets_hsts(client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "app_env", "production")
    assert client.get("/api/session").status_code == 400
    response = client.get("https://testserver/api/session")
    assert response.status_code == 401
    assert response.headers["strict-transport-security"] == "max-age=31536000"
