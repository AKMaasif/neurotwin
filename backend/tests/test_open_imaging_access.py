import json


def prepare(tmp_path, monkeypatch):
    base = tmp_path / "oasis2"; base.mkdir()
    (base / "manifest.json").write_text(json.dumps({"summary": {}, "subjects": []}))
    monkeypatch.setenv("NEUROTWIN_IMAGING_ROOT", str(tmp_path))
    monkeypatch.delenv("NEUROTWIN_IMAGING_USERS", raising=False)


def test_in_demo_mode_every_clinician_account_can_open_imaging_without_any_setting(client, login, tmp_path, monkeypatch):
    prepare(tmp_path, monkeypatch); monkeypatch.delenv("NEUROTWIN_IMAGING_OPEN", raising=False)
    assert client.get("/api/imaging/oasis2/subjects", headers=login("demo-dr-layla")).status_code == 200


def test_participants_and_family_never_get_imaging_even_in_open_mode(client, login, tmp_path, monkeypatch):
    prepare(tmp_path, monkeypatch); monkeypatch.delenv("NEUROTWIN_IMAGING_OPEN", raising=False)
    for uid in ("demo-fatima", "demo-yousef", "demo-mariam", "demo-omar"):
        assert client.get("/api/imaging/oasis2/subjects", headers=login(uid)).status_code == 403


def test_signed_out_visitors_are_still_refused(client, tmp_path, monkeypatch):
    prepare(tmp_path, monkeypatch)
    assert client.get("/api/imaging/oasis2/subjects").status_code == 401


def test_open_mode_can_be_switched_off(client, login, tmp_path, monkeypatch):
    prepare(tmp_path, monkeypatch); monkeypatch.setenv("NEUROTWIN_IMAGING_OPEN", "0")
    assert client.get("/api/imaging/oasis2/subjects", headers=login("demo-dr-layla")).status_code == 403
    monkeypatch.setenv("NEUROTWIN_IMAGING_USERS", "demo-dr-layla")
    assert client.get("/api/imaging/oasis2/subjects", headers=login("demo-dr-layla")).status_code == 200
