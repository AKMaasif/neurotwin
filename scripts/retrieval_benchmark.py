"""Small synthetic retrieval regression benchmark, not a clinical or agent benchmark."""

import json
from pathlib import Path

import httpx

from app.config import settings

with httpx.Client(base_url="http://127.0.0.1:8140", timeout=30) as c:
    r = c.post(
        "/api/login", json={"username": "clinician", "password": settings.demo_password}
    )
    r.raise_for_status()
    c.headers["X-CSRF-Token"] = r.json()["csrf"]
    base = "/api/patients/patient-demo/documents"
    docs = c.get(base).json()
    cases = [
        ("schedule.csv", "transport", "2026-11-18", "row", 2),
        ("appointment.docx", "transport", "Transport assistance", "paragraph", 2),
        ("activities.xlsx", "transport", "2026-11-18", "worksheet", "Appointments"),
        ("scan.pdf", "appointment", "2026-11-18", "page", 1),
        (
            "legacy.xls",
            "transport",
            "Transport assistance",
            "worksheet",
            "Appointments",
        ),
    ]
    results = []
    for filename, query, text, key, value in cases:
        d = next(d for d in docs if d["payload"].get("filename") == filename)
        r = c.post(
            base + "/search", json={"query": query, "document_id": d["id"], "limit": 3}
        )
        r.raise_for_status()
        hits = r.json()["results"]
        passed = any(text in h["text"] and h["source"].get(key) == value for h in hits)
        results.append(
            {
                "fixture": filename,
                "query": query,
                "hit_at_3": passed,
                "locator_matched": passed,
                "mode": r.json()["mode"],
            }
        )
    evidence = {
        "dataset": "5 fictional fixture queries with document filters",
        "cases": results,
        "hit_at_3": sum(x["hit_at_3"] for x in results) / len(results),
        "clinical_validity": False,
        "general_retrieval_accuracy_estimate": False,
    }
    Path("test-results/retrieval-benchmark.json").write_text(
        json.dumps(evidence, indent=2)
    )
    print(json.dumps(evidence))
    assert all(x["hit_at_3"] for x in results)
