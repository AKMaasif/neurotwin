"""Explicit small paid checks, synthetic fixtures only. Never logs credentials/context."""

import json
from pathlib import Path

import httpx

from app.config import settings


def main():
    with httpx.Client(base_url="http://127.0.0.1:8140", timeout=90) as c:
        r = c.post(
            "/api/login",
            json={"username": "clinician", "password": settings.demo_password},
        )
        r.raise_for_status()
        c.headers["X-CSRF-Token"] = r.json()["csrf"]
        base = "/api/patients/patient-demo/documents"
        docs = c.get(base).json()
        visual = next(
            d
            for d in docs
            if d["payload"].get("filename") == "appointment.png"
            and d["payload"].get("processing_status") == "partial"
        )
        r = c.post(
            base + "/" + visual["id"] + "/visuals",
            json={"expected_version": visual["version"]},
        )
        visual_ok = r.status_code == 200
        tabular = next(
            d
            for d in docs
            if d["payload"].get("filename") == "schedule.csv"
            and d["payload"].get("processing_status") == "processed"
        )
        r = c.post(
            base + "/" + tabular["id"] + "/embeddings",
            json={"expected_version": tabular["version"]},
        )
        embedding_ok = r.status_code == 200
        r = c.post(
            base + "/search",
            json={
                "query": "help with a journey to an appointment",
                "semantic": True,
                "document_id": tabular["id"],
            },
        )
        result = r.json()
        hybrid_ok = (
            r.status_code == 200
            and result.get("mode") == "hybrid_rrf"
            and bool(result.get("results"))
        )
        evidence = {
            "synthetic_only": True,
            "live_visual_interpretation": visual_ok,
            "live_document_embeddings": embedding_ok,
            "live_hybrid_query": hybrid_ok,
            "clinical_validation": False,
        }
        Path("test-results/document-provider-check.json").write_text(
            json.dumps(evidence, indent=2)
        )
        print(json.dumps(evidence))
        assert all([visual_ok, embedding_ok, hybrid_ok])


if __name__ == "__main__":
    main()
