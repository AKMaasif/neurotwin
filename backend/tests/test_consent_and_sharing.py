from conftest import consent, run_reaction


def test_no_session_without_consent(client, yousef):
    r = client.post("/api/sessions", json={"protocol_code": "reaction_time", "protocol_version": "0.1"}, headers=yousef)
    assert r.status_code == 409
    assert "consent" in r.json()["detail"].lower()


def test_consent_then_withdraw_blocks_new_sessions_but_keeps_records(client, yousef):
    consent(client, yousef)
    assert run_reaction(client, yousef).status_code == 200
    consent(client, yousef, granted=False)
    r = client.post("/api/sessions", json={"protocol_code": "reaction_time", "protocol_version": "0.1"}, headers=yousef)
    assert r.status_code == 409
    kept = client.get("/api/participants/demo-yousef/evidence", headers=yousef).json()
    assert len(kept) == 3, "withdrawing consent must not delete earlier records"


def test_withdraw_mid_session_records_nothing(client, yousef):
    consent(client, yousef)
    s = client.post("/api/sessions", json={"protocol_code": "reaction_time", "protocol_version": "0.1"},
                    headers=yousef).json()
    consent(client, yousef, granted=False)
    r = client.post(f"/api/sessions/{s['id']}/complete", json={"status": "completed", "observations": [
        {"measure": "rt_median_ms", "kind": "observed", "value_num": 500}]}, headers=yousef)
    assert r.status_code == 409
    assert client.get("/api/participants/demo-yousef/evidence", headers=yousef).json() == []


def test_consent_history_is_append_only(client, yousef, app):
    consent(client, yousef)
    consent(client, yousef, granted=False)
    consent(client, yousef)
    from app.models import ConsentEvent
    with app.state.db.SessionLocal() as db:
        decisions = [c.decision for c in db.query(ConsentEvent).filter_by(participant_id="demo-yousef")
                     .order_by(ConsentEvent.id)]
    assert decisions == ["granted", "withdrawn", "granted"]


def test_only_participants_consent(client, login):
    r = client.post("/api/consents", json={"scope": "participation", "granted": True}, headers=login("demo-mariam"))
    assert r.status_code == 403


def test_clinician_sees_nothing_without_a_grant(client, yousef, login):
    consent(client, yousef)
    run_reaction(client, yousef)
    dr = login("demo-dr-layla")
    assert client.get("/api/participants/demo-yousef/evidence", headers=dr).status_code == 404
    assert all(p["id"] != "demo-yousef" for p in client.get("/api/clinician/participants", headers=dr).json())


def test_grant_opens_and_revoke_closes_access_without_deleting(client, yousef, login):
    consent(client, yousef)
    run_reaction(client, yousef)
    dr = login("demo-dr-layla")
    g = client.post("/api/grants", json={"grantee_id": "demo-dr-layla", "purpose": "clinical_review"}, headers=yousef)
    assert g.status_code == 200
    assert len(client.get("/api/participants/demo-yousef/evidence", headers=dr).json()) == 3
    client.post(f"/api/grants/{g.json()['id']}/revoke", headers=yousef)
    assert client.get("/api/participants/demo-yousef/evidence", headers=dr).status_code == 404
    assert len(client.get("/api/participants/demo-yousef/evidence", headers=yousef).json()) == 3


def test_purpose_must_match_role(client, yousef):
    r = client.post("/api/grants", json={"grantee_id": "demo-omar", "purpose": "clinical_review"}, headers=yousef)
    assert r.status_code == 422
    r = client.post("/api/grants", json={"grantee_id": "demo-dr-layla", "purpose": "participation_updates"},
                    headers=yousef)
    assert r.status_code == 422


def test_family_never_reads_evidence_even_with_a_grant(client, yousef, login):
    consent(client, yousef)
    run_reaction(client, yousef)
    client.post("/api/grants", json={"grantee_id": "demo-omar", "purpose": "participation_updates"}, headers=yousef)
    omar = login("demo-omar")
    assert client.get("/api/participants/demo-yousef/evidence", headers=omar).status_code == 404
    shared = client.get("/api/family/shared", headers=omar).json()
    entry = next(e for e in shared if e["participant_id"] == "demo-yousef")
    assert entry["active"] and entry["recent"][0]["protocol_code"] == "reaction_time"
    assert "value_num" not in str(entry) and "quality" not in str(entry)


def test_family_sees_ended_notice_after_revoke(client, yousef, login):
    consent(client, yousef)
    run_reaction(client, yousef)
    g = client.post("/api/grants", json={"grantee_id": "demo-omar", "purpose": "participation_updates"},
                    headers=yousef).json()
    client.post(f"/api/grants/{g['id']}/revoke", headers=yousef)
    entry = next(e for e in client.get("/api/family/shared", headers=login("demo-omar")).json()
                 if e["participant_id"] == "demo-yousef")
    assert entry["active"] is False and entry["ended_at"] and entry["recent"] == []


def test_cannot_revoke_someone_elses_grant(client, yousef, login):
    fatima = login("demo-fatima")
    grants = client.get("/api/grants", headers=fatima).json()
    r = client.post(f"/api/grants/{grants[0]['id']}/revoke", headers=yousef)
    assert r.status_code == 404


def test_unsigned_and_forged_sessions_are_refused(client):
    assert client.get("/api/me").status_code == 401
    assert client.get("/api/me", headers={"Cookie": "nt_session=forged"}).status_code == 401


def test_participants_cannot_read_each_other(client, yousef):
    assert client.get("/api/participants/demo-fatima/evidence", headers=yousef).status_code == 404
