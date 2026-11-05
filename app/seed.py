from .config import settings
from .db import Grant, Patient, Record, User
from .security import password_hash


def seed(db):
    if not settings.seed_demo or db.get(User, "participant"):
        return
    if settings.app_env != "development" or len(settings.demo_password) < 16:
        raise RuntimeError(
            "Demo seed needs development mode and a generated password; run python -m app.bootstrap"
        )
    for key, name, role in [
        ("participant", "Mansoor", "participant"),
        ("family", "Fatima", "family"),
        ("clinician", "Dr. Mariam", "clinician"),
        ("other", "Other participant", "participant"),
    ]:
        db.add(
            User(
                id=key,
                name=name,
                role=role,
                password_hash=password_hash(settings.demo_password),
            )
        )
    for key, name, region in [
        ("patient-demo", "Mansoor (synthetic)", "Al Ain"),
        ("patient-other", "Other (synthetic)", "Dubai"),
    ]:
        db.add(Patient(id=key, name=name, age=64, region=region, synthetic=True))
    db.flush()
    for user, patient, scopes in [
        (
            "participant",
            "patient-demo",
            [
                "summary",
                "tasks",
                "respond",
                "help",
                "messages",
                "assessment",
                "preferences",
                "sharing",
            ],
        ),
        ("family", "patient-demo", ["summary", "tasks", "help", "messages"]),
        (
            "clinician",
            "patient-demo",
            ["summary", "tasks", "help", "messages", "assessment", "review", "audit"],
        ),
        ("other", "patient-other", ["summary", "tasks", "respond"]),
    ]:
        db.add(Grant(user_id=user, patient_id=patient, scopes=scopes))
    db.add(
        Record(
            id="plan-demo",
            patient_id="patient-demo",
            kind="plan",
            status="approved",
            payload={
                "title": "Synthetic daily support plan",
                "signed_by": "Synthetic clinician seed",
                "clinical_use": False,
                "instructions": "Ask for help preparing your appointment.",
            },
        )
    )
    for i, title, period, steps in [
        (
            1,
            "Prepare for your clinic visit",
            "morning",
            [
                "Find your appointment details.",
                "Check the date and time.",
                "Ask for transport help if needed.",
            ],
        ),
        (
            2,
            "Connect with someone you choose",
            "afternoon",
            ["Choose a permitted contact.", "Send a message or request a call."],
        ),
    ]:
        db.add(
            Record(
                id=f"task-{i:02}",
                patient_id="patient-demo",
                kind="task",
                status="pending",
                payload={
                    "title": title,
                    "period": period,
                    "time": "Today",
                    "steps": steps,
                    "plan_id": "plan-demo",
                    "plan_version": 1,
                    "evidence_type": None,
                },
            )
        )
    db.commit()
