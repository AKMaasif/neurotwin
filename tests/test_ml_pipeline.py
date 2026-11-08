import hashlib
import json

import numpy as np
import pytest

from app.config import ROOT
from scripts.train_research_model import FEATURES, partitions, prepare, train
from tests.conftest import sign_in


def source_rows():
    return [
        dict(
            SUBJECT=str(i),
            COUPLE=str(i // 2),
            PHASE="3",
            CDR_score="0" if i % 2 else "1",
            AGE=str(60 + i % 10),
            YR_EDU="12",
            TOTAL_TABLET_PLANNED_ANALYSIS=str(28 if i % 2 else 17),
        )
        for i in range(60)
    ]


def test_group_and_participant_split_integrity():
    records, excluded = prepare(source_rows())
    split = partitions(records)
    for left, a in split.items():
        for right, b in split.items():
            if left != right:
                assert not {records[i]["subject"] for i in a} & {
                    records[i]["subject"] for i in b
                }
                assert not {records[i]["group"] for i in a} & {
                    records[i]["group"] for i in b
                }
    assert sorted(np.concatenate(list(split.values())).tolist()) == list(range(60))
    assert not excluded


def test_presumed_labels_explicit_and_missing_not_zero():
    rows = source_rows()
    rows[0]["CDR_score"] = "-1"
    rows[1]["CDR_score"] = "NA"
    a, excluded = prepare(rows)
    assert len(a) == 58
    assert excluded == dict(
        presumed_normal_not_independently_rated=1, missing_reference_label=1
    )
    b, _ = prepare(rows, True)
    assert len(b) == 59 and b[0]["label_source"] == "presumed_normal"


@pytest.mark.parametrize(
    "field,value",
    [
        ("AGE", "inf"),
        ("TOTAL_TABLET_PLANNED_ANALYSIS", "31"),
        ("CDR_score", "-2"),
        ("COUPLE", ""),
    ],
)
def test_invalid_source_fails_closed(field, value):
    rows = source_rows()
    rows[0][field] = value
    with pytest.raises(ValueError):
        prepare(rows)


def test_protocol_and_age_exclusions_duplicate_identity():
    rows = source_rows()
    rows[0]["PHASE"] = "2"
    rows[1]["AGE"] = "49"
    records, excluded = prepare(rows)
    assert len(records) == 58 and len(excluded) == 2
    rows[2]["SUBJECT"] = rows[3]["SUBJECT"]
    with pytest.raises(ValueError):
        prepare(rows)


def test_leakage_features_absent_and_training_reproducible():
    records, excluded = prepare(source_rows())
    a, r = train(records, excluded)
    b, s = train(records, excluded)
    assert a == b and r == s
    assert FEATURES == ["TOTAL_TABLET_PLANNED_ANALYSIS", "AGE", "YR_EDU"]
    assert (
        r["training_performed"] and not r["clinical_use"] and not r["release_approved"]
    )
    assert set(r["metrics"]) == {"prevalence_baseline", "uncalibrated", "calibrated"}
    assert r["split_unit"] == "Participant and linked patient-partner dyad"


def test_published_artifact_integrity_and_no_participant_rows():
    folder = ROOT / "research-artifacts/original-saturn-v1"
    model = (folder / "model.json").read_bytes()
    report = json.loads((folder / "evaluation.json").read_text())
    assert hashlib.sha256(model).hexdigest() == report["artifact_sha256"]
    assert report["partitions"]["test"]["participants"] == 7
    assert report["partitions"]["test"]["clinician_rated_negative"] == 0
    assert report["calibration_improved_test_brier"] is False
    assert not {"rows", "SUBJECT", "COUPLE", "predictions"} & report.keys()
    assert report["runtime_patient_inference"] is False


def test_insufficient_data_not_presented_as_validated():
    records, _ = prepare(source_rows()[:10])
    with pytest.raises(ValueError):
        partitions(records)
    records, _ = prepare(source_rows())
    for r in records:
        r["y"] = 1
    with pytest.raises(ValueError):
        partitions(records)


def test_evaluation_authorization_and_read_only(client):
    path = "/api/patients/patient-demo/research-model"
    assert client.get(path).status_code == 401
    sign_in(client, "family")
    assert client.get(path).status_code == 403
    sign_in(client, "participant")
    assert client.get(path).status_code == 403
    sign_in(client, "clinician")
    response = client.get(path)
    assert response.status_code == 200, response.text
    assert response.json()["release_approved"] is False
    assert client.post(path, json={"predict": True}).status_code == 405
