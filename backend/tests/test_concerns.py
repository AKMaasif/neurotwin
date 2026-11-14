"""Concern reports: preview-then-send, server-chosen recipient, honest states, clinician inbox, privacy."""
import pytest

from test_careplan import sign_in
from test_assistant import say, two_tasks

BODY = {"topic": "sleep", "since": "few_days", "text": "I have been waking up at night."}


def draft(client, h, **kw):
    return client.post("/api/concerns", json={**BODY, **kw}, headers=h)


def sent(client):
    h = sign_in(client, "demo-fatima")
    r = draft(client, h).json()
    s = client.post(f"/api/concerns/{r['id']}/send", json={"rev": r["rev"]}, headers=h)
    assert s.status_code == 200, s.text
    return h, s.json()


def test_draft_is_not_sent_and_the_recipient_comes_from_the_grants(client):
    h = sign_in(client, "demo-fatima")
    info = client.get("/api/concerns/info").json()
    assert [r["name"] for r in info["recipients"]] == ["Dr. Layla"]
    r = draft(client, h).json()
    assert r["status"] == "draft" and r["recipient"] is None and [e["kind"] for e in r["events"]] == ["created"]
    sign_in(client, "demo-dr-layla")
    assert client.get("/api/concerns/inbox").json() == []                       # a draft is private to the person


def test_send_delivers_but_does_not_claim_it_was_read(client):
    h, r = sent(client)
    assert r["status"] == "delivered" and r["recipient"] == "Dr. Layla"
    assert [e["kind"] for e in r["events"]] == ["created", "sent", "delivered"]
    assert not any(e["kind"] in ("acknowledged", "reviewed") for e in r["events"])
    sign_in(client, "demo-dr-layla")
    inbox = client.get("/api/concerns/inbox").json()                            # opening the inbox is not an acknowledgement
    assert len(inbox) == 1 and inbox[0]["status"] == "delivered" and inbox[0]["label"] == "patient_reported"
    sign_in(client, "demo-fatima")
    assert client.get("/api/concerns").json()[0]["status"] == "delivered"


def test_acknowledge_review_close_each_leave_an_event_the_person_can_see(client):
    sent(client)
    hc = sign_in(client, "demo-dr-layla")
    rid = client.get("/api/concerns/inbox").json()[0]["id"]
    assert client.post(f"/api/concerns/{rid}/review", json={"note": "x"}, headers=hc).status_code == 409      # cannot skip acknowledge
    assert client.post(f"/api/concerns/{rid}/close", json={}, headers=hc).status_code == 409
    assert client.post(f"/api/concerns/{rid}/acknowledge", headers=hc).json()["status"] == "acknowledged"
    assert client.post(f"/api/concerns/{rid}/acknowledge", headers=hc).json()["status"] == "acknowledged"     # repeat adds nothing
    assert client.post(f"/api/concerns/{rid}/review", json={"note": "Will call you."}, headers=hc).json()["status"] == "reviewed"
    assert client.post(f"/api/concerns/{rid}/close", json={"note": "Spoke by phone."}, headers=hc).json()["status"] == "closed"
    sign_in(client, "demo-fatima")
    r = client.get("/api/concerns").json()[0]
    assert [e["kind"] for e in r["events"]] == ["created", "sent", "delivered", "acknowledged", "reviewed", "closed"]
    assert r["status"] == "closed" and all(e["by"] for e in r["events"])
    kinds = [n["kind"] for n in client.get("/api/notifications").json()]
    assert {"concern_acknowledged", "concern_reviewed", "concern_closed"} <= set(kinds)


def test_send_only_what_was_previewed(client):
    h = sign_in(client, "demo-fatima")
    r = draft(client, h).json()
    e = client.put(f"/api/concerns/{r['id']}", json={**BODY, "text": "Changed after preview."}, headers=h).json()
    assert e["rev"] == r["rev"] + 1
    assert client.post(f"/api/concerns/{r['id']}/send", json={"rev": r["rev"]}, headers=h).status_code == 409
    assert client.post(f"/api/concerns/{r['id']}/send", json={"rev": e["rev"]}, headers=h).status_code == 200
    assert client.put(f"/api/concerns/{r['id']}", json=BODY, headers=h).status_code == 409                    # no edits after sending
    assert client.post(f"/api/concerns/{r['id']}/send", json={"rev": e["rev"]}, headers=h).status_code == 409  # no double send


def test_validation(client):
    h = sign_in(client, "demo-fatima")
    assert draft(client, h, topic="diagnosis").status_code == 422
    assert draft(client, h, since="yesterday").status_code == 422
    assert draft(client, h, text="   ").status_code == 422
    assert draft(client, h, text="x" * 601).status_code in (422,)


def test_no_clinician_means_it_cannot_be_sent_and_the_draft_is_kept(client):
    h = sign_in(client, "demo-yousef")
    r = draft(client, h).json()
    assert client.get("/api/concerns/info").json()["recipients"] == []
    s = client.post(f"/api/concerns/{r['id']}/send", json={"rev": r["rev"]}, headers=h)
    assert s.status_code == 409 and "not chosen a clinician" in s.json()["detail"]
    assert client.get("/api/concerns").json()[0]["status"] == "draft"


def test_a_typed_recipient_must_be_on_the_grant_list(client):
    h = sign_in(client, "demo-fatima")
    r = draft(client, h).json()
    assert client.post(f"/api/concerns/{r['id']}/send", json={"rev": r["rev"], "recipient_id": "demo-omar"}, headers=h).status_code == 422
    assert client.post(f"/api/concerns/{r['id']}/send", json={"rev": r["rev"], "recipient_id": "demo-dr-layla"}, headers=h).status_code == 200


def test_revoked_access_hides_it_from_the_clinician_but_keeps_the_record(client):
    h, r = sent(client)
    g = next(x for x in client.get("/api/grants").json() if x["purpose"] == "clinical_review")
    assert client.post(f"/api/grants/{g['id']}/revoke", headers=h).status_code == 200
    hc = sign_in(client, "demo-dr-layla")
    assert client.get("/api/concerns/inbox").json() == []
    assert client.post(f"/api/concerns/{r['id']}/acknowledge", headers=hc).status_code == 404
    sign_in(client, "demo-fatima")
    assert client.get("/api/concerns").json()[0]["status"] == "delivered"        # the person's record stays


def test_withdraw(client):
    h, r = sent(client)
    w = client.post(f"/api/concerns/{r['id']}/withdraw", headers=h).json()
    assert w["status"] == "withdrawn" and w["events"][-1]["kind"] == "withdrawn"
    hc = sign_in(client, "demo-dr-layla")
    assert client.post(f"/api/concerns/{r['id']}/acknowledge", headers=hc).status_code == 409
    h = sign_in(client, "demo-fatima")
    r2 = draft(client, h).json()
    client.post(f"/api/concerns/{r2['id']}/send", json={"rev": r2["rev"]}, headers=h)
    hc = sign_in(client, "demo-dr-layla")
    rid = [x for x in client.get("/api/concerns/inbox").json() if x["id"] == r2["id"]][0]["id"]
    client.post(f"/api/concerns/{rid}/acknowledge", headers=hc)
    h = sign_in(client, "demo-fatima")
    assert client.post(f"/api/concerns/{r2['id']}/withdraw", headers=h).status_code == 409                    # too late once acknowledged


def test_privacy_between_people(client, app):
    h, r = sent(client)
    for who in ("demo-yousef", "demo-mariam", "demo-omar"):
        hh = sign_in(client, who)
        assert client.post(f"/api/concerns/{r['id']}/withdraw", headers=hh).status_code == 404
        assert client.post(f"/api/concerns/{r['id']}/acknowledge", headers=hh).status_code == 404
        if who == "demo-yousef":
            assert client.get("/api/concerns").json() == []
        else:
            assert client.get("/api/concerns").status_code == 404
            assert client.get("/api/concerns/inbox").status_code == 404
    from app.models import AuditEvent, Notification
    with app.state.db.SessionLocal() as db:
        assert "waking" not in str([(a.action, a.target) for a in db.query(AuditEvent).all()])
        assert "waking" not in str([(n.kind, n.about_id) for n in db.query(Notification).all()])


def test_clinician_can_not_write_for_the_person(client):
    hc = sign_in(client, "demo-dr-layla")
    assert client.post("/api/concerns", json=BODY, headers=hc).status_code == 404


def test_the_page_states_what_it_is_not(client, monkeypatch):
    h = sign_in(client, "demo-fatima")
    assert client.get("/api/concerns/info").json()["monitoring_hours"] is None            # unstated until the owner supplies it
    monkeypatch.setenv("NEUROTWIN_MONITORING_HOURS", "Sunday to Thursday, 9:00 to 15:00")
    assert client.get("/api/concerns/info").json()["monitoring_hours"].startswith("Sunday")


@pytest.mark.parametrize("text", ["I want to report a concern", "tell my doctor about a problem", "something is wrong", "أريد الإبلاغ عن مشكلة"])
def test_the_assistant_only_opens_the_flow(client, text):
    h = two_tasks(client)
    r = say(client, h, text)
    assert r["tool"] == "start_concern" and r["navigate"] == "concern" and r["needs_confirmation"] is False
    assert client.get("/api/concerns").json() == []                                       # nothing was created or sent
