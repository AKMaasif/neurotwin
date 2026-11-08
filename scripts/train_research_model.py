"""Offline original-SATURN benchmark; never a patient inference endpoint."""

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from sklearn import __version__ as sklearn_version
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    balanced_accuracy_score,
    brier_score_loss,
    confusion_matrix,
    log_loss,
    roc_auc_score,
)
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

FEATURES = ["TOTAL_TABLET_PLANNED_ANALYSIS", "AGE", "YR_EDU"]
SOURCE = "https://zenodo.org/records/3962060"
VERSION = "original-saturn-phase3-research-1"


def digest(content):
    return hashlib.sha256(content).hexdigest()


def number(value):
    if value in {"", "NA"}:
        return float("nan")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("Non-finite source value")
    return result


def prepare(rows, allow_presumed=False):
    seen, eligible, excluded = set(), [], {}
    required = {"SUBJECT", "COUPLE", "PHASE", "CDR_score", *FEATURES}
    for row in rows:
        if not required <= row.keys():
            raise ValueError("Missing required source columns")
        identifier = row["SUBJECT"]
        if not identifier or identifier in seen or not row["COUPLE"]:
            raise ValueError("Missing or duplicate participant/group identity")
        seen.add(identifier)
        reason = None
        if row["PHASE"] != "3":
            reason = "incompatible_development_phase"
        age, label = number(row["AGE"]), number(row["CDR_score"])
        if reason is None and (not math.isfinite(age) or not 50 <= age <= 89):
            reason = "outside_source_age_eligibility"
        if reason is None and math.isnan(label):
            reason = "missing_reference_label"
        if reason is None and label == -1 and not allow_presumed:
            reason = "presumed_normal_not_independently_rated"
        if reason:
            excluded[reason] = excluded.get(reason, 0) + 1
            continue
        if label not in {-1, 0, 0.5, 1, 2, 3}:
            raise ValueError("Unexpected reference label")
        x = [number(row[f]) for f in FEATURES]
        if (
            not math.isfinite(x[0])
            or not 0 <= x[0] <= 30
            or (math.isfinite(x[2]) and not 0 <= x[2] <= 30)
        ):
            raise ValueError("Invalid source feature range")
        eligible.append(
            dict(
                subject=identifier,
                group=row["COUPLE"],
                x=x,
                y=int(label > 0),
                label_source="presumed_normal" if label == -1 else "clinician_rated",
            )
        )
    return eligible, excluded


def partitions(records):
    if len(records) < 20:
        raise ValueError(
            "Insufficient eligible participants for three independent partitions"
        )
    y = np.array([r["y"] for r in records])
    groups = np.array([r["group"] for r in records])
    trainval, test = next(
        GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=42).split(
            records, y, groups
        )
    )
    t, v = next(
        GroupShuffleSplit(n_splits=1, test_size=0.3, random_state=43).split(
            trainval, y[trainval], groups[trainval]
        )
    )
    result = dict(train=trainval[t], validation=trainval[v], test=test)
    group_sets = [set(groups[ix]) for ix in result.values()]
    if any(group_sets[i] & group_sets[j] for i in range(3) for j in range(i)):
        raise ValueError("Linked-group leakage")
    for ix in result.values():
        if min(np.bincount(y[ix], minlength=2)) < 2:
            raise ValueError(
                "Insufficient independent class representation; do not search test seeds"
            )
    return result


def metrics(y, probabilities):
    p = np.clip(probabilities, 1e-6, 1 - 1e-6)
    return dict(
        participants=len(y),
        roc_auc=float(roc_auc_score(y, p)),
        brier=float(brier_score_loss(y, p)),
        log_loss=float(log_loss(y, p, labels=[0, 1])),
        balanced_accuracy=float(balanced_accuracy_score(y, p >= 0.5)),
        confusion_matrix=confusion_matrix(y, p >= 0.5, labels=[0, 1]).tolist(),
        threshold=0.5,
    )


def train(records, excluded):
    split = partitions(records)
    x = np.array([r["x"] for r in records])
    y = np.array([r["y"] for r in records])
    tr, va, te = (split[k] for k in ["train", "validation", "test"])
    # All imputation, scaling and model fitting are train-only. No CDR/TYPE/MoCA/clinic inputs.
    model = make_pipeline(
        SimpleImputer(strategy="median"),
        StandardScaler(),
        LogisticRegression(C=1, max_iter=2000, random_state=44),
    )
    model.fit(x[tr], y[tr])
    # Fixed regularized sigmoid calibration on validation participants only.
    calibration = LogisticRegression(C=1, max_iter=2000, random_state=45)
    calibration.fit(model.decision_function(x[va]).reshape(-1, 1), y[va])
    uncalibrated = model.predict_proba(x[te])[:, 1]
    calibrated = calibration.predict_proba(
        model.decision_function(x[te]).reshape(-1, 1)
    )[:, 1]
    baseline = np.repeat(y[tr].mean(), len(te))
    # Group bootstrap expresses limited test-set variability, not population validity.
    rng = np.random.default_rng(46)
    group = np.array([records[i]["group"] for i in te])
    unique = np.unique(group)
    samples = []
    for _ in range(1000):
        selected = rng.choice(unique, size=len(unique), replace=True)
        ix = np.concatenate([np.flatnonzero(group == g) for g in selected])
        if len(np.unique(y[te][ix])) == 2:
            samples.append(float(roc_auc_score(y[te][ix], calibrated[ix])))
    counts = {}
    for name, ix in split.items():
        counts[name] = dict(
            participants=len(ix),
            linked_groups=len({records[i]["group"] for i in ix}),
            positive=int(y[ix].sum()),
            negative=int((1 - y[ix]).sum()),
            presumed_normal=sum(
                records[i]["label_source"] == "presumed_normal" for i in ix
            ),
            clinician_rated_negative=sum(
                records[i]["y"] == 0 and records[i]["label_source"] == "clinician_rated"
                for i in ix
            ),
        )
    scaler = model[1]
    logistic = model[2]
    artifact = dict(
        version=VERSION,
        features=FEATURES,
        imputation=model[0].statistics_.tolist(),
        mean=scaler.mean_.tolist(),
        scale=scaler.scale_.tolist(),
        coefficients=logistic.coef_[0].tolist(),
        intercept=float(logistic.intercept_[0]),
        calibration_coefficient=float(calibration.coef_[0][0]),
        calibration_intercept=float(calibration.intercept_[0]),
        clinical_use=False,
        runtime_patient_inference=False,
    )
    report = dict(
        version=VERSION,
        source=SOURCE,
        license="CC0-1.0 (author deposit)",
        target="Original-study CDR > 0 versus rated/presumed normal; exploratory only",
        protocol="Original SATURN final development phase; not the adapted mobile protocol",
        training_performed=True,
        synthetic=False,
        clinical_use=False,
        release_approved=False,
        runtime_patient_inference=False,
        features=FEATURES,
        excluded=excluded,
        partitions=counts,
        seeds=dict(
            test_split=42, validation_split=43, model=44, calibration=45, bootstrap=46
        ),
        split_unit="Participant and linked patient-partner dyad",
        calibration="Regularized sigmoid fit on validation partition only; no test-set model selection",
        calibration_improved_test_brier=bool(
            brier_score_loss(y[te], calibrated) < brier_score_loss(y[te], uncalibrated)
        ),
        metrics=dict(
            prevalence_baseline=metrics(y[te], baseline),
            uncalibrated=metrics(y[te], uncalibrated),
            calibrated=metrics(y[te], calibrated),
        ),
        roc_auc_group_bootstrap_95=[
            float(v) for v in np.quantile(samples, [0.025, 0.975])
        ]
        if samples
        else None,
        bootstrap_valid_replicates=len(samples),
        sklearn_version=sklearn_version,
        limitations=[
            f"Only {len(records)} eligible final-phase labelled participants in this source release",
            "Most negative labels are presumed-normal partners, not independent clinical ratings",
            "Very small held-out partitions; unstable discrimination and calibration estimates",
            "Cross-sectional source study: no longitudinal decline prediction",
            "Original protocol/English/Oregon cohort does not validate the adapted app, Arabic or Gulf populations",
            "No clinical deployment, automatic care decision or patient-level inference is enabled",
        ],
    )
    return artifact, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--allow-presumed-normal",
        action="store_true",
        help="Explicitly include author-defined presumed-normal partner labels; not independent clinical labels",
    )
    args = parser.parse_args()
    if args.output.exists() or args.input.stat().st_size > 2_000_000:
        raise SystemExit(
            "Use a new output directory and a bounded original source file"
        )
    raw = args.input.read_bytes()
    if hashlib.md5(raw).hexdigest() != "ea4fcc55d829a47ea7ca04fb17c031ab":
        raise SystemExit(
            "This benchmark requires the pinned original author-deposited source"
        )
    records, excluded = prepare(
        list(csv.DictReader(raw.decode("utf-8-sig").splitlines())),
        args.allow_presumed_normal,
    )
    artifact, report = train(records, excluded)
    args.output.mkdir(parents=True)
    encoded = (
        json.dumps(artifact, sort_keys=True, indent=2, allow_nan=False) + "\n"
    ).encode()
    report.update(source_sha256=digest(raw), artifact_sha256=digest(encoded))
    (args.output / "model.json").write_bytes(encoded)
    (args.output / "evaluation.json").write_text(
        json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            dict(
                training_performed=True,
                clinical_use=False,
                partitions=report["partitions"],
                metrics=report["metrics"],
            ),
            ensure_ascii=True,
        )
    )


if __name__ == "__main__":
    main()
