from app.db import Audit, Grant, Outbox
from app.worker import run_once


def test_worker_rechecks_grant_and_deduplicates(database):
    with database() as db:
        db.add(
            Outbox(
                patient_id="patient-demo",
                event_type="help.requested",
                payload={"recipient_id": "family"},
            )
        )
        db.commit()
        grant = db.query(Grant).filter_by(user_id="family").one()
        grant.active = False
        db.commit()
        assert run_once(db) == 1
        assert db.query(Outbox).one().status == "cancelled_access_revoked"
        assert run_once(db) == 0
        assert db.query(Audit).filter_by(action="delivery.blocked").count() == 1
