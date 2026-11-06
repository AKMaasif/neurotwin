import uuid

import pytest
from conftest import sign_in
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.care_policies import install
from app.db import CareMessage


def test_restricted_postgres_role_select_insert_update_delete(client, database):
    engine = database.kw["bind"]
    if engine.dialect.name != "postgresql":
        pytest.skip("SQLite uses the same server authorization, not PostgreSQL RLS")
    sign_in(client)
    base = "/api/patients/patient-demo/messages"
    saved = client.post(
        base + "/threads/family",
        json={"body": "Private family text", "command_id": str(uuid.uuid4())},
    ).json()
    with engine.begin() as conn:
        install(conn)
    role = "nt_care_test_" + uuid.uuid4().hex
    with engine.connect() as conn:
        schema = conn.execute(text("SELECT current_schema()")).scalar()
        conn.rollback()
        try:
            with conn.begin():
                conn.exec_driver_sql(f'CREATE ROLE "{role}" NOLOGIN NOBYPASSRLS')
        except DBAPIError:
            pytest.skip(
                "Database credential cannot create a disposable non-owner test role"
            )
        try:
            with conn.begin():
                conn.exec_driver_sql(f'GRANT USAGE ON SCHEMA "{schema}" TO "{role}"')
                conn.exec_driver_sql(
                    f'GRANT SELECT ON "{schema}".users,"{schema}".patients,"{schema}".grants TO "{role}"'
                )
                for table in [
                    "care_conversations",
                    "care_participants",
                    "care_messages",
                    "care_audio",
                    "care_attachments",
                    "care_events",
                    "care_receipts",
                ]:
                    conn.exec_driver_sql(
                        f'GRANT SELECT,INSERT,UPDATE,DELETE ON "{schema}"."{table}" TO "{role}"'
                    )

            def assume(actor):
                conn.exec_driver_sql(f'SET LOCAL ROLE "{role}"')
                conn.execute(
                    text("SELECT set_config('neurotwin.actor_id',:actor,true)"),
                    {"actor": actor},
                )

            with conn.begin():
                assume("clinician")
                assert (
                    conn.execute(text("SELECT count(*) FROM care_messages")).scalar()
                    == 0
                )
            with conn.begin():
                assume("family")
                assert (
                    conn.execute(text("SELECT count(*) FROM care_messages")).scalar()
                    == 1
                )
                conn.execute(
                    text("UPDATE care_messages SET opened_at=:at WHERE id=:id"),
                    {"at": "2026-11-07T00:00:00+00:00", "id": saved["id"]},
                )
                assert (
                    conn.execute(
                        text("DELETE FROM care_messages WHERE id=:id"),
                        {"id": saved["id"]},
                    ).rowcount
                    == 0
                )
            with pytest.raises(DBAPIError):
                with conn.begin():
                    assume("family")
                    conn.execute(
                        text("UPDATE care_messages SET body='Tampered' WHERE id=:id"),
                        {"id": saved["id"]},
                    )
            with pytest.raises(DBAPIError):
                with conn.begin():
                    assume("family")
                    conn.execute(
                        text(
                            "INSERT INTO care_messages(id,patient_id,sender_id,recipient_id,body,media,command_id,created_at) VALUES (:id,'patient-demo','participant','family','Forged','{}',:key,:at)"
                        ),
                        {
                            "id": str(uuid.uuid4()),
                            "key": str(uuid.uuid4()),
                            "at": "2026-11-07T00:00:00+00:00",
                        },
                    )
            with conn.begin():
                assume("family")
                conn.execute(
                    text(
                        "INSERT INTO care_messages(id,patient_id,sender_id,recipient_id,body,media,command_id,created_at) VALUES (:id,'patient-demo','family','participant','Allowed','{}',:key,:at)"
                    ),
                    {
                        "id": str(uuid.uuid4()),
                        "key": str(uuid.uuid4()),
                        "at": "2026-11-07T00:00:00+00:00",
                    },
                )
            with conn.begin():
                conn.execute(
                    text(
                        "UPDATE grants SET active=false WHERE user_id='family' AND patient_id='patient-demo'"
                    )
                )
            with conn.begin():
                assume("family")
                assert (
                    conn.execute(text("SELECT count(*) FROM care_messages")).scalar()
                    == 0
                )
        finally:
            conn.rollback()
            with conn.begin():
                conn.exec_driver_sql(
                    f'REVOKE ALL ON ALL TABLES IN SCHEMA "{schema}" FROM "{role}"'
                )
                conn.exec_driver_sql(f'REVOKE USAGE ON SCHEMA "{schema}" FROM "{role}"')
                conn.exec_driver_sql(f'DROP ROLE "{role}"')


def test_cookie_account_switch_rejects_stale_actor_before_send(client, database):
    sign_in(client)
    expected = "participant"
    sign_in(client, "family")
    result = client.post(
        "/api/patients/patient-demo/messages/threads/clinician",
        json={
            "command_id": str(uuid.uuid4()),
            "body": "Must not send under another identity",
        },
        headers={"X-Expected-Actor": expected},
    )
    assert result.status_code == 409
    with database() as db:
        assert db.query(CareMessage).count() == 0


def test_care_access_logs_redact_search_terms_and_identifiers():
    import logging

    from app.care_logging import CareAccessFilter

    record = logging.LogRecord(
        "uvicorn.access",
        20,
        "",
        1,
        "%s %s %s %s %s",
        (
            "client",
            "GET",
            "/api/patients/private-patient/messages/threads/person?q=private-search",
            "1.1",
            200,
        ),
        None,
    )
    assert CareAccessFilter().filter(record)
    assert (
        "private-patient" not in record.getMessage()
        and "private-search" not in record.getMessage()
    )
