"""The clinician footer status: names and states only, never keys; configured is not the same as available; idle unless something runs."""
import json
import os

from test_careplan import sign_in


def test_only_clinicians_and_no_secrets(client, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "secret-key-value-123")
    monkeypatch.setenv("NEUROTWIN_GEMINI_MODEL", "some-model")
    sign_in(client, "demo-fatima")
    assert client.get("/api/system/status").status_code == 404
    sign_in(client, "demo-dr-layla")
    r = client.get("/api/system/status")
    assert r.status_code == 200
    assert "secret-key-value-123" not in r.text and "some-model" not in r.text
    d = r.json()
    assert d["checked"] is None and set(d["providers"]) == {"gemini", "meta"}
    assert all(p["state"] in ("configured", "not_configured") for p in d["providers"].values())
    assert not any("live" in json.dumps(p) or "available" in json.dumps(p) for p in d["providers"].values())


def test_idle_when_nothing_runs_and_stale_runs_do_not_count(client, tmp_path, monkeypatch):
    from app import agent_analysis as AA
    monkeypatch.setattr(AA, "runs_root", lambda: tmp_path)
    (tmp_path / "r1").mkdir()
    f = tmp_path / "r1" / "run.json"
    f.write_text(json.dumps({"state": "running"}))
    sign_in(client, "demo-dr-layla")
    assert client.get("/api/system/status").json()["analysis"] == {"state": "running", "running": 1}
    old = f.stat().st_mtime - 3600
    os.utime(f, (old, old))
    assert client.get("/api/system/status").json()["analysis"] == {"state": "idle", "running": 0}
