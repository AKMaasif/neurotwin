"""Read-only original-cohort benchmark; never computes a patient prediction."""

import hashlib
import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .config import ROOT
from .db import Audit, User, get_db
from .security import authenticated, authorize

router = APIRouter()


@router.get("/api/patients/{pid}/research-model")
def evaluation(
    pid: str, u: User = Depends(authenticated), db: Session = Depends(get_db)
):
    patient = authorize(db, u, pid, "review")
    if u.role != "clinician" or not patient.synthetic:
        raise HTTPException(
            403,
            "Original-cohort research evaluation requires a synthetic clinician workspace",
        )
    folder = ROOT / "research-artifacts" / "original-saturn-v1"
    try:
        model = (folder / "model.json").read_bytes()
        raw = (folder / "evaluation.json").read_bytes()
        if len(raw) > 64000:
            raise ValueError()
        report = json.loads(raw)
        if (
            hashlib.sha256(model).hexdigest() != report["artifact_sha256"]
            or report["clinical_use"] is not False
            or report["release_approved"] is not False
        ):
            raise ValueError()
    except (OSError, KeyError, ValueError):
        raise HTTPException(
            503, "Verified research evaluation is unavailable"
        ) from None
    fields = {
        "version",
        "source",
        "license",
        "target",
        "protocol",
        "training_performed",
        "synthetic",
        "clinical_use",
        "release_approved",
        "runtime_patient_inference",
        "features",
        "excluded",
        "partitions",
        "metrics",
        "calibration",
        "calibration_improved_test_brier",
        "roc_auc_group_bootstrap_95",
        "limitations",
        "source_sha256",
        "artifact_sha256",
        "split_unit",
    }
    db.add(
        Audit(
            patient_id=pid,
            actor=u.id,
            action="research_model.evaluation.read",
            detail={"model_version": report["version"]},
        )
    )
    db.commit()
    return {key: report[key] for key in fields}
