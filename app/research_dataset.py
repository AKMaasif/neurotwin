"""Offline structural checks for research data; never trains or scores a patient."""

import hashlib
import json
import sys
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from pydantic_core import PydanticCustomError


class Row(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    sample_id: str = Field(min_length=1, max_length=80)
    participant_id: str = Field(min_length=1, max_length=80)
    split: Literal["train", "validation", "test"]
    time_days: float = Field(ge=0, le=36500, allow_inf_nan=False)
    value: float | None = Field(ge=-10, le=10, allow_inf_nan=False)
    quality: Literal["usable", "poor", "interrupted"]
    protocol_id: str = Field(min_length=1, max_length=80)
    protocol_version: str = Field(min_length=1, max_length=80)
    mode: Literal["self", "assisted", "video"]
    consent_reference: str = Field(min_length=1, max_length=200)

    @field_validator(
        "sample_id",
        "participant_id",
        "protocol_id",
        "protocol_version",
        "consent_reference",
    )
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise PydanticCustomError("blank_reference", "Reference must not be blank")
        return value.strip()


class Dataset(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    schema_version: Literal["1"]
    synthetic: bool
    source_reference: str = Field(min_length=1, max_length=200)
    permission_reference: str = Field(min_length=1, max_length=200)
    rows: list[Row] = Field(min_length=1, max_length=100000)

    _references = field_validator("source_reference", "permission_reference")(
        Row.nonblank.__func__
    )


def validate_dataset(raw):
    report = {
        "validator_version": "research-dataset-1",
        "valid": False,
        "ready_for_training": False,
        "training_performed": False,
        "clinical_use": False,
        "gates": [
            "permission_and_protocol_require_manual_review",
            "labels_and_model_validation_not_established",
        ],
        "errors": [],
    }
    try:
        data = Dataset.model_validate(raw)
    except ValidationError as exc:
        known = set(Row.model_fields) | set(Dataset.model_fields)
        report["errors"] = [
            {
                "path": [
                    part if isinstance(part, int) or part in known else "<field>"
                    for part in error["loc"]
                ],
                "code": error["type"],
            }
            for error in exc.errors(include_input=False, include_url=False)[:50]
        ]
        report["error_count"] = exc.error_count()
        return report
    canonical = json.dumps(
        data.model_dump(), sort_keys=True, separators=(",", ":"), allow_nan=False
    )
    report["input_sha256"] = hashlib.sha256(canonical.encode()).hexdigest()
    splits = {
        name: {"rows": 0, "participants": 0, "usable": 0}
        for name in ("train", "validation", "test")
    }
    samples, people, times, protocols = set(), {}, set(), {}
    missing = usable = 0
    qualities = {"usable": 0, "poor": 0, "interrupted": 0}
    for index, row in enumerate(data.rows):

        def flag(code):
            report["errors"].append({"path": ["rows", index], "code": code})

        if row.sample_id in samples:
            flag("duplicate_sample")
        samples.add(row.sample_id)
        previous_split = people.setdefault(row.participant_id, row.split)
        if previous_split != row.split:
            flag("participant_split_leakage")
        protocol = (row.protocol_id, row.protocol_version, row.mode)
        if protocols.setdefault(row.participant_id, protocol) != protocol:
            flag("incompatible_protocol")
        instant = (row.participant_id, row.time_days)
        if instant in times:
            flag("duplicate_time")
        times.add(instant)
        missing += row.value is None
        qualities[row.quality] += 1
        is_usable = row.quality == "usable" and row.value is not None
        usable += is_usable
        splits[row.split]["rows"] += 1
        splits[row.split]["usable"] += is_usable
    for name, count in splits.items():
        count["participants"] = len(
            {row.participant_id for row in data.rows if row.split == name}
        )
        if not count["rows"]:
            report["errors"].append({"path": ["splits", name], "code": "empty_split"})
        if not count["usable"]:
            report["gates"].append(f"no_usable_rows_in_{name}")
    report |= {
        "valid": not report["errors"],
        "synthetic": data.synthetic,
        "quality_counts": qualities,
        "splits": splits,
        "counts": {
            "rows": len(data.rows),
            "participants": len(people),
            "usable": usable,
            "excluded": len(data.rows) - usable,
            "missing_values": missing,
        },
        "error_count": len(report["errors"]),
    }
    report["errors"] = report["errors"][:50]
    return report


def write_report(path, report):
    with Path(path).open("x", encoding="utf-8") as out:
        json.dump(report, out, indent=2, allow_nan=False)


def main():
    if len(sys.argv) != 3:
        raise SystemExit(
            "Usage: python -m app.research_dataset INPUT.json NEW_REPORT.json"
        )
    try:
        path = Path(sys.argv[1])
        with path.open("rb") as source:
            raw = source.read(10 * 1024 * 1024 + 1)
        if len(raw) > 10 * 1024 * 1024:
            raise ValueError("Dataset exceeds 10 MB")
        report = validate_dataset(json.loads(raw))
        write_report(sys.argv[2], report)
    except (OSError, ValueError, TypeError):
        raise SystemExit(
            "Could not validate input or create a new report. Check JSON, the 10 MB limit, and that the output does not already exist."
        )
    print(
        json.dumps(
            {
                "valid": report["valid"],
                "errors": report["error_count"],
                "training_performed": False,
            }
        )
    )
    raise SystemExit(0 if report["valid"] else 1)


if __name__ == "__main__":
    main()
