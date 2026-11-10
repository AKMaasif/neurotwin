import logging

from app.logs import mask_path
from conftest import consent


def test_mask_path_hides_ids():
    assert mask_path("/api/participants/demo-fatima/evidence") == "/api/participants/:person/evidence"
    assert mask_path("/api/evidence/42/amend") == "/api/evidence/:id/amend"
    assert mask_path("/api/auth/demo-login") == "/api/auth/demo-login"


def test_logs_never_contain_values_tokens_or_bodies(client, yousef, caplog):
    caplog.set_level(logging.INFO, logger="neurotwin.http")
    consent(client, yousef)
    s = client.post("/api/sessions", json={"protocol_code": "daily_checkin", "protocol_version": "0.1",
                                           "assistance_note": "SECRET-NOTE"}, headers=yousef).json()
    client.post(f"/api/sessions/{s['id']}/complete", json={"status": "completed", "observations": [
        {"measure": "sleep_hours", "kind": "self_reported", "value_num": 4.25},
        {"measure": "today_factors", "kind": "self_reported", "value_text": "PRIVATE-TEXT"}]}, headers=yousef)
    text = caplog.text
    assert "neurotwin.http" in text or "POST" in text
    token = yousef["Cookie"].split("=", 1)[1]
    for leak in ("4.25", "PRIVATE-TEXT", "SECRET-NOTE", "demo-yousef", token, yousef["X-CSRF-Token"]):
        assert leak not in text
