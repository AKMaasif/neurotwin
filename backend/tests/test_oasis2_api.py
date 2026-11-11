import json

import pytest

nib = pytest.importorskip("nibabel")
np = pytest.importorskip("numpy")
pytest.importorskip("PIL")

from app import oasis2_api


@pytest.fixture(autouse=True)
def clear_cache():
    oasis2_api._volume.cache_clear()


def visit(mri, delay, gap, status="usable"):
    return {"mri_id": mri, "delay_days": delay, "years_since_previous": gap, "status": status, "usable_scans": ["mpr-1"], "problems": [],
            "clinical": {"Age": 80, "MMSE": 28, "CDR": 0}, "imported_measures": {"eTIV": 1500, "nWBV": 0.7, "ASF": 1.1}}


@pytest.fixture
def files(tmp_path, monkeypatch):
    monkeypatch.setenv("NEUROTWIN_IMAGING_ROOT", str(tmp_path))
    monkeypatch.setenv("NEUROTWIN_IMAGING_USERS", "demo-dr-layla")
    base = tmp_path / "oasis2"; raw = base / "extracted" / "OAS2_RAW_PART1" / "OAS2_0001_MR1" / "RAW"; raw.mkdir(parents=True)
    vol = (np.arange(8 * 10 * 12, dtype=np.float32).reshape(8, 10, 12) % 200 + 1)
    nib.save(nib.AnalyzeImage(vol, np.eye(4)), raw / "mpr-1.nifti.img")  # writes the .hdr beside it
    manifest = {"summary": {"subjects": 1}, "subjects": [{"subject_id": "OAS2_0001", "group_label_from_dataset": "Nondemented",
                "level1_compare": True, "level2_trend": False, "visits": [visit("OAS2_0001_MR1", 0, None), visit("OAS2_0001_MR2", 457, 1.251)]}]}
    (base / "manifest.json").write_text(json.dumps(manifest))
    return base


def test_requires_login_and_research_access(client, login, files):
    assert client.get("/api/imaging/oasis2/subjects").status_code == 401
    for uid in ("demo-yousef", "demo-mariam"):
        h = login(uid)
        assert client.get("/api/imaging/oasis2/subjects", headers=h).status_code == 403
        assert client.get("/api/imaging/oasis2/visits/OAS2_0001_MR1/slice.png", headers=h).status_code == 403


def test_subjects_report_which_visits_are_extracted_and_not_ready_until_two(client, login, files):
    r = client.get("/api/imaging/oasis2/subjects", headers=login("demo-dr-layla"))
    assert r.status_code == 200 and r.headers["cache-control"] == "private, no-store"
    s = r.json()["subjects"][0]
    assert [v["prepared"] for v in s["visits"]] == [True, False] and s["ready"] is False


def test_slice_is_a_png_with_the_expected_size_per_axis(client, login, files):
    h = login("demo-dr-layla")
    from PIL import Image
    import io
    for axis, size in ((2, (8, 10)), (1, (8, 12)), (0, (10, 12))):  # plane is rotated a quarter turn, so size is (rows, columns) of the plane
        r = client.get(f"/api/imaging/oasis2/visits/OAS2_0001_MR1/slice.png?axis={axis}&index=3", headers=h)
        assert r.status_code == 200 and r.headers["content-type"] == "image/png"
        assert Image.open(io.BytesIO(r.content)).size == size


def test_out_of_range_index_and_bad_axis_are_refused(client, login, files):
    h = login("demo-dr-layla")
    assert client.get("/api/imaging/oasis2/visits/OAS2_0001_MR1/slice.png?axis=2&index=99", headers=h).status_code == 422
    assert client.get("/api/imaging/oasis2/visits/OAS2_0001_MR1/slice.png?axis=7&index=0", headers=h).status_code == 422


def test_unextracted_visit_is_a_clear_404_not_a_blank_image(client, login, files):
    r = client.get("/api/imaging/oasis2/visits/OAS2_0001_MR2/slice.png?index=0", headers=login("demo-dr-layla"))
    assert r.status_code == 404 and "extracted" in r.json()["detail"]


def test_ids_are_validated_so_paths_cannot_be_injected(client, login, files):
    h = login("demo-dr-layla")
    for bad in ("..%2F..%2Fetc", "OAS2_0001_MR1%2F..", "x"):
        assert client.get(f"/api/imaging/oasis2/visits/{bad}/slice.png?index=0", headers=h).status_code in (404, 422)
    assert client.get("/api/imaging/oasis2/visits/OAS2_0001_MR1/slice.png?index=0&scan=..%2Fmpr-1", headers=h).status_code == 404


def test_info_states_the_frame_is_unverified(client, login, files):
    r = client.get("/api/imaging/oasis2/visits/OAS2_0001_MR1/info", headers=login("demo-dr-layla"))
    assert r.json()["shape"] == [8, 10, 12] and "not verified" in r.json()["frame"]


def test_missing_manifest_says_how_to_build_it(client, login, tmp_path, monkeypatch):
    monkeypatch.setenv("NEUROTWIN_IMAGING_ROOT", str(tmp_path)); monkeypatch.setenv("NEUROTWIN_IMAGING_USERS", "demo-dr-layla")
    r = client.get("/api/imaging/oasis2/subjects", headers=login("demo-dr-layla"))
    assert r.status_code == 404 and "manifest" in r.json()["detail"]


def test_non_cubic_voxels_are_drawn_in_true_proportion(client, login, files):
    raw = files / "extracted" / "OAS2_RAW_PART1" / "OAS2_0001_MR1" / "RAW"
    vol = (np.arange(8 * 10 * 12, dtype=np.float32).reshape(8, 10, 12) % 200 + 1)
    img = nib.AnalyzeImage(vol, np.diag([1.0, 1.0, 2.0, 1.0])); nib.save(img, raw / "mpr-1.nifti.img")
    oasis2_api._volume.cache_clear()
    from PIL import Image
    import io
    r = client.get("/api/imaging/oasis2/visits/OAS2_0001_MR1/slice.png?axis=0&index=2", headers=login("demo-dr-layla"))
    assert Image.open(io.BytesIO(r.content)).size == (10, 24)  # axes 1 and 2 are 10 and 12 voxels; the second is twice as thick
