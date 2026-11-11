import hashlib

import pytest

nib = pytest.importorskip("nibabel")
np = pytest.importorskip("numpy")

from app import native_imaging as N
from app.models import NativeRun
from app.logs import mask_path
from conftest import make_user, sign_in


@pytest.fixture(autouse=True)
def native_storage(tmp_path, monkeypatch):
    monkeypatch.setenv("NEUROTWIN_NATIVE_ROOT", str(tmp_path / "native"))
    monkeypatch.setenv("NEUROTWIN_IMAGING_USERS", "demo-dr-layla,research-two")
    monkeypatch.setenv("NEUROTWIN_IMAGING_OPEN", "0")


@pytest.fixture
def original(tmp_path):
    values = np.arange(32 ** 3, dtype=np.float32).reshape(32, 32, 32) % 300
    affine = np.diag([-1., 1.2, 1., 1.]); affine[0, 3] = 31
    path = tmp_path / "original.nii"
    nib.save(nib.Nifti1Image(values, affine), path)
    return path


def upload(client, headers, path):
    return client.post("/api/imaging/native/import", data={"confirmed": "true"}, files=[("files", (path.name, path.read_bytes(), "application/octet-stream"))], headers=headers)


def test_native_import_prepares_without_freesurfer_and_preserves_original(client, login, original, app):
    h = login("demo-dr-layla")
    response = upload(client, h, original)
    assert response.status_code == 200, response.text
    identifier = response.json()["id"]
    run = client.get(f"/api/imaging/native/runs/{identifier}", headers=h).json()
    assert run["status"] == "awaiting_review"
    assert [s["status"] for s in run["stages"]] == ["succeeded"] * 3 + ["blocked"] * 4
    assert run["producer_version"] == "neurotwin-native/0.1"
    assert run["result"]["segmentation_available"] is False
    assert run["result"]["prediction_available"] is False
    assert run["result"]["axis_codes"] == ["R", "A", "S"]
    preserved = N.root() / run["scan_id"] / "source" / "original.nii"
    assert preserved.read_bytes() == original.read_bytes()
    assert run["files"][0]["sha256"] == hashlib.sha256(original.read_bytes()).hexdigest()
    canonical = nib.as_closest_canonical(nib.load(original)).get_fdata()
    low, high = np.percentile(canonical, [1, 99.5])
    expected = np.clip((canonical - low) * 255 / (high - low), 0, 255).astype("u1")
    binary = client.get(f"/api/imaging/native/runs/{identifier}/volume", headers=h)
    assert binary.status_code == 200
    assert np.array_equal(np.frombuffer(binary.content, dtype="u1").reshape(expected.shape), expected)
    assert binary.headers["cache-control"] == "private, no-store"
    assert "anatomical_qc_pending" in [f["code"] for f in run["findings"]]
    with app.state.db.SessionLocal() as db:
        # A duplicate worker invocation cannot change a published attempt.
        before = db.get(NativeRun, identifier).updated_at
    N.process(app.state.db.SessionLocal, identifier, N.root())
    with app.state.db.SessionLocal() as db:
        assert db.get(NativeRun, identifier).updated_at == before


def test_native_requires_csrf_and_explicit_owner_access(client, login, original, app, monkeypatch):
    assert client.get("/api/imaging/native/runs").status_code == 401
    h = login("demo-dr-layla")
    no_csrf = {"Cookie": h["Cookie"]}
    assert upload(client, no_csrf, original).status_code == 403
    run = upload(client, h, original).json()
    make_user(app, "research-two", "research.two", role="clinician")
    other = sign_in(client, "research.two", "a real account phrase 1")
    assert client.get("/api/imaging/native/runs", headers=other).json()["runs"] == []
    for suffix in ["", "/volume"]:
        assert client.get(f"/api/imaging/native/runs/{run['id']}{suffix}", headers=other).status_code == 404
    assert client.post(f"/api/imaging/native/runs/{run['id']}/cancel", headers=other).status_code == 404
    monkeypatch.setenv("NEUROTWIN_IMAGING_USERS", "")
    assert client.get(f"/api/imaging/native/runs/{run['id']}/volume", headers=h).status_code == 403


@pytest.mark.parametrize("shape,fill", [((16, 16, 16, 2), "varied"), ((16, 16, 16), "nan"), ((16, 16, 16), "flat"), ((513, 16, 16), "varied")])
def test_invalid_volume_cannot_reach_analysis_or_be_retried(client, login, tmp_path, shape, fill):
    values = np.arange(np.prod(shape), dtype=np.float32).reshape(shape)
    if fill == "nan": values.flat[0] = np.nan
    if fill == "flat": values.fill(0)
    path = tmp_path / "bad.nii"; nib.save(nib.Nifti1Image(values, np.eye(4)), path)
    h = login("demo-dr-layla"); submitted = upload(client, h, path)
    assert submitted.status_code == 200
    run = client.get(f"/api/imaging/native/runs/{submitted.json()['id']}", headers=h).json()
    assert run["status"] == "failed" and not run["retryable"]
    assert run["result"] is None
    assert next(s for s in run["stages"] if s["id"] == "display")["status"] == "skipped"
    assert client.post(f"/api/imaging/native/runs/{run['id']}/retry", headers=h).status_code == 409
    assert client.get(f"/api/imaging/native/runs/{run['id']}/volume", headers=h).status_code == 409


def test_analyze_pair_has_unverified_orientation(client, login, tmp_path):
    values = np.arange(32 ** 3, dtype=np.int16).reshape(32, 32, 32)
    nib.save(nib.AnalyzeImage(values, np.eye(4)), tmp_path / "pair.img")
    files = [("files", (f"pair.{ext}", (tmp_path / f"pair.{ext}").read_bytes())) for ext in ["hdr", "img"]]
    h = login("demo-dr-layla")
    response = client.post("/api/imaging/native/import", data={"confirmed": "true"}, files=files, headers=h)
    assert response.status_code == 200
    run = client.get(f"/api/imaging/native/runs/{response.json()['id']}", headers=h).json()
    assert run["status"] == "awaiting_review"
    assert run["result"]["axis_codes"] is None
    assert not run["result"]["spatial_frame_explicit"]
    assert "orientation_unverified" in [f["code"] for f in run["findings"]]


def test_singleton_frame_is_supported_without_accepting_time_series(client, login, tmp_path):
    values = (np.arange(32 ** 3, dtype=np.int16) % 1000).reshape(32, 32, 32, 1)
    path = tmp_path / "single-frame.nii"; nib.save(nib.Nifti1Image(values, np.eye(4)), path)
    h = login("demo-dr-layla"); submitted = upload(client, h, path).json()
    run = client.get(f"/api/imaging/native/runs/{submitted['id']}", headers=h).json()
    assert run["status"] == "awaiting_review"
    assert run["result"]["source_shape"] == [32, 32, 32, 1]
    assert run["result"]["shape"] == [32, 32, 32]


def test_gzip_expansion_limit_and_invalid_uploads(client, login, original, monkeypatch):
    import gzip
    h = login("demo-dr-layla")
    for files in [[("files", ("bad.exe", b"data"))], [("files", ("pair.hdr", b"data"))],
                  [("files", ("a.hdr", b"data")), ("files", ("b.img", b"data"))]]:
        assert client.post("/api/imaging/native/import", data={"confirmed": "true"}, files=files, headers=h).status_code == 422
    monkeypatch.setattr(N, "MAX_EXPANDED", 1024)
    response = client.post("/api/imaging/native/import", data={"confirmed": "true"}, files=[("files", ("scan.nii.gz", gzip.compress(original.read_bytes())))], headers=h)
    run = client.get(f"/api/imaging/native/runs/{response.json()['id']}", headers=h).json()
    assert run["status"] == "failed" and "limit" in run["error"]


def test_cancellation_and_retry_preserve_history(client, login, original, monkeypatch):
    monkeypatch.setattr(N, "process", lambda *args: None)
    h = login("demo-dr-layla")
    first = upload(client, h, original).json()
    cancelled = client.post(f"/api/imaging/native/runs/{first['id']}/cancel", headers=h).json()
    assert cancelled["status"] == "cancelled"
    assert client.get(f"/api/imaging/native/runs/{first['id']}/volume", headers=h).status_code == 409
    second = client.post(f"/api/imaging/native/runs/{first['id']}/retry", headers=h).json()
    assert second["id"] != first["id"] and second["parent_run_id"] == first["id"]
    assert second["scan_id"] == first["scan_id"] and second["status"] == "queued"
    assert client.post(f"/api/imaging/native/runs/{first['id']}/retry", headers=h).status_code == 409


def test_interrupted_run_recovery_and_checksum_guard(app, original):
    with app.state.db.SessionLocal() as db:
        scan, run = N.intake(db, "demo-dr-layla", [(original.name, original.read_bytes())])
        run.status = "running"; db.commit()
        N.recover_interrupted(db)
        assert run.status == "failed" and run.retryable
        run.status = "queued"; db.commit()
        (N.root() / scan.id / "source" / "original.nii").write_bytes(b"changed")
        identifier = run.id
    N.process(app.state.db.SessionLocal, identifier, N.root())
    with app.state.db.SessionLocal() as db:
        failed = db.get(NativeRun, identifier)
        assert failed.status == "failed" and "checksum" in failed.error and not failed.retryable


def test_unavailable_dependencies_and_masked_log_paths(client, login, original, monkeypatch):
    monkeypatch.setattr(N, "dependencies_available", lambda: False)
    h = login("demo-dr-layla")
    assert client.get("/api/imaging/native/runs", headers=h).json()["available"] is False
    assert upload(client, h, original).status_code == 503
    assert mask_path("/api/imaging/native/runs/private-identifier/volume") == "/api/imaging/native/runs/:run/volume"


def test_import_identity_confirmation_and_body_limit(client, login, original):
    h = login("demo-dr-layla")
    files = [("files", (original.name, original.read_bytes()))]
    assert client.post("/api/imaging/native/import", files=files, headers=h).status_code == 422
    excessive = {**h, "Content-Length": str(N.MAX_UPLOAD + 2 * 1024 * 1024)}
    assert client.post("/api/imaging/native/import", content=b"", headers=excessive).status_code == 413
