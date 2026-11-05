"""Transactional in-app outbox projection. No fabricated SMS/push delivery."""

import time

from sqlalchemy import select

from .db import Audit, Grant, Outbox, Session


def run_once(db):
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
    while True:
        with Session() as db:
            run_once(db)
        time.sleep(2)
