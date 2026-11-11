import json

import pytest

from app.models import AuditEvent
from sqlalchemy import select


@pytest.fixture
def imaging_files(tmp_path, monkeypatch):
    assets = tmp_path / "OAS1_0001_MR1" / "assets"
    assets.mkdir(parents=True)
    (assets / "manifest.json").write_text(json.dumps({"subject": "OAS1_0001_MR1", "status": "QC pending"}))
    (assets / "volume.bin").write_bytes(b"\x00\x01\x02")
    monkeypatch.setenv("NEUROTWIN_IMAGING_ROOT", str(tmp_path))
    monkeypatch.setenv("NEUROTWIN_IMAGING_USERS", "demo-dr-layla")
    return assets


def test_imaging_requires_session_and_explicit_research_access(client, login, imaging_files, monkeypatch):
    assert client.get("/api/imaging/case").status_code == 401
    assert client.get("/api/imaging/artifacts/volume.bin").status_code == 401
    for uid in ["demo-yousef", "demo-mariam"]:
        headers = login(uid)
        assert client.get("/api/imaging/case", headers=headers).status_code == 403
        assert client.get("/api/imaging/artifacts/volume.bin", headers=headers).status_code == 403
    headers = login("demo-dr-layla")
    monkeypatch.setenv("NEUROTWIN_IMAGING_USERS", "")
    assert client.get("/api/imaging/case", headers=headers).status_code == 403
    monkeypatch.setenv("NEUROTWIN_IMAGING_USERS", "demo-mariam")
    assert client.get("/api/imaging/case", headers=login("demo-mariam")).status_code == 403


def test_case_read_is_audited_and_binary_is_private(client, login, imaging_files, app):
    headers = login("demo-dr-layla")
    response = client.get("/api/imaging/case", headers=headers)
    assert response.status_code == 200
    assert response.json()["subject"] == "OAS1_0001_MR1"
    assert response.headers["cache-control"] == "private, no-store"
    binary = client.get("/api/imaging/artifacts/volume.bin", headers=headers)
    assert binary.content == b"\x00\x01\x02"
    assert binary.headers["cache-control"] == "private, no-store"
    assert binary.headers["x-content-type-options"] == "nosniff"
    with app.state.db.SessionLocal() as db:
        event = db.scalar(select(AuditEvent).where(AuditEvent.action == "research_imaging.view"))
        assert event.actor_id == "demo-dr-layla"
        assert event.participant_id is None  # never attached to a synthetic clinical participant


def test_artifacts_cannot_read_other_files_and_revocation_applies(client, login, imaging_files, monkeypatch):
    headers = login("demo-dr-layla")
    for name in ["manifest.json", "recon-all.log", ".env", "unknown.bin", "lh.pial.vertices.bin"]:
        assert client.get(f"/api/imaging/artifacts/{name}", headers=headers).status_code == 404
    monkeypatch.setenv("NEUROTWIN_IMAGING_USERS", "")
    assert client.get("/api/imaging/artifacts/volume.bin", headers=headers).status_code == 403


def test_unprepared_case_is_reported(client, login, tmp_path, monkeypatch):
    monkeypatch.setenv("NEUROTWIN_IMAGING_ROOT", str(tmp_path))
    monkeypatch.setenv("NEUROTWIN_IMAGING_USERS", "demo-dr-layla")
    assert client.get("/api/imaging/case", headers=login("demo-dr-layla")).status_code == 404
