"""Extend an isolated workspace-browser SQLite fixture; never touch the demo DB."""

from pathlib import Path

from app.config import settings
from app.db import Base, Grant, Patient, Session, engine
from app.seed import seed


def main():
    prefix = "sqlite:///./data/workspace-browser-"
    if not settings.database_url.startswith(prefix):
        raise SystemExit("Use a dedicated data/workspace-browser-*.db SQLite fixture")
    target = Path(settings.database_url.removeprefix("sqlite:///")).resolve()
    if target.parent != Path("data").resolve() or target.suffix != ".db":
        raise SystemExit(
            "Fixture path must remain inside the repository data directory"
        )
    Base.metadata.create_all(engine)
    with Session() as db:
        seed(db)
        if not db.get(Patient, "patient-readonly"):
            db.add(
                Patient(
                    id="patient-readonly",
                    name="Read only (synthetic)",
                    age=70,
                    region="Dubai",
                )
            )
            db.flush()
            for user, patient, scopes in [
                ("family", "patient-other", ["summary", "tasks", "help", "messages"]),
                (
                    "clinician",
                    "patient-other",
                    ["summary", "tasks", "help", "messages", "review", "audit"],
                ),
                ("clinician", "patient-readonly", ["summary"]),
            ]:
                db.add(Grant(user_id=user, patient_id=patient, scopes=scopes))
            grant = (
                db.query(Grant)
                .filter_by(user_id="other", patient_id="patient-other")
                .one()
            )
            grant.scopes = [
                "summary",
                "tasks",
                "respond",
                "help",
                "messages",
                "sharing",
            ]
            db.commit()
    print("Isolated synthetic workspace fixture ready")


if __name__ == "__main__":
    main()
