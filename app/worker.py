"""Transactional in-app outbox projection. No fabricated SMS/push delivery."""

import logging
import time

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from .db import Audit, Grant, Outbox, Session
from .routines import tick


def run_once(db):
    tick(db)
    pending = (
        db.execute(
            select(Outbox)
            .where(Outbox.status == "pending")
            .order_by(Outbox.created_at)
            .with_for_update(skip_locked=True)
        )
        .scalars()
        .all()
    )
    for event in pending:
        recipient = event.payload.get("recipient_id")
        if recipient:
            grant = (
                db.query(Grant)
                .filter_by(user_id=recipient, patient_id=event.patient_id, active=True)
                .first()
            )
            if not grant or "help" not in grant.scopes:
                event.status = "cancelled_access_revoked"
                db.add(
                    Audit(
                        patient_id=event.patient_id,
                        actor="worker",
                        action="delivery.blocked",
                        detail={"event": event.id},
                    )
                )
                continue
        event.status = "projected_in_app"
        db.add(
            Audit(
                patient_id=event.patient_id,
                actor="worker",
                action="event.projected",
                detail={"event": event.id, "external_delivery": "not_connected"},
            )
        )
    db.commit()
    return len(pending)


if __name__ == "__main__":
    next_media_cleanup = 0
    while True:
        try:
            with Session() as db:
                run_once(db)
            if time.monotonic() >= next_media_cleanup:
                from .media_maintenance import cleanup

                with Session() as db:
                    cleanup(db)
                next_media_cleanup = time.monotonic() + 300
        except (SQLAlchemyError, OSError):
            logging.getLogger(__name__).warning(
                "Reminder database unavailable; retrying without confirming delivery."
            )
            time.sleep(5)
            continue
        time.sleep(2)
