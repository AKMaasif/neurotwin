"""Synthetic intent/confirmation regression benchmark; no live speech or clinical scoring."""

import json
import secrets
import tempfile
import time
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.db import Base, get_db
from app.main import app
from app.seed import seed


def main():
    cases = [
        ("navigation", "Open settings", "navigate"),
        ("plan", "read my plan", "read_plan"),
        ("activity", "what should I do", "coach_task"),
        ("confirmation", "I finished", "task_response"),
        ("preferences", "make text larger", "set_text_size"),
        ("help", "help me with transport", "prepare_help"),
        ("acceptance", "help request status", "help_status"),
        ("unavailable_model", "an unfamiliar request", "clarify"),
        ("unsafe", "invent a diagnosis", "clarify"),
        ("urgent", "sudden confusion open settings", "clinical_review"),
    ]
    old_password, old_ai = settings.demo_password, settings.ai_enabled
    settings.demo_password = secrets.token_urlsafe(24)
    settings.ai_enabled = False
    try:
        with tempfile.TemporaryDirectory(prefix="nt-companion-bench-") as folder:
            engine = create_engine(
                "sqlite:///" + str(Path(folder) / "bench.db"),
                connect_args={"check_same_thread": False},
            )
            Base.metadata.create_all(engine)
            factory = sessionmaker(engine, expire_on_commit=False)
            with factory() as db:
                seed(db)

            def dependency():
                with factory() as db:
                    yield db

            app.dependency_overrides[get_db] = dependency
            client = TestClient(app)
            r = client.post(
                "/api/login",
                json={"username": "participant", "password": settings.demo_password},
            )
            client.headers["X-CSRF-Token"] = r.json()["csrf"]
            results = []
            for name, text, intent in cases:
                start = time.perf_counter()
                r = client.post(
                    "/api/patients/patient-demo/companion", json={"text": text}
                )
                body = r.json()
                passed = r.status_code == 200 and body.get("intent") == intent
                if intent in ["task_response", "set_text_size"]:
                    passed = passed and body.get("requires_confirmation") is True
                results.append(
                    {
                        "case": name,
                        "passed": passed,
                        "intent": body.get("intent"),
                        "source": body.get("source"),
                        "latency_ms": round((time.perf_counter() - start) * 1000, 2),
                    }
                )
            data = client.get("/api/patients/patient-demo/workspace").json()
            assert all(
                t["status"] == "pending" for t in data["records"] if t["kind"] == "task"
            )
            client.close()
            app.dependency_overrides.clear()
            engine.dispose()
        evidence = {
            "mode": "synthetic deterministic and disabled-provider intent benchmark",
            "cases": results,
            "passed": sum(r["passed"] for r in results),
            "total": len(results),
            "clinical_validation": False,
            "speech_accuracy_evaluated": False,
        }
        Path("test-results").mkdir(exist_ok=True)
        Path("test-results/companion-benchmark.json").write_text(
            json.dumps(evidence, indent=2)
        )
        print(json.dumps(evidence))
        assert all(r["passed"] for r in results)
    finally:
        settings.demo_password = old_password
        settings.ai_enabled = old_ai
        app.dependency_overrides.clear()


if __name__ == "__main__":
    main()
