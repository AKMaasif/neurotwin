import copy
import json

import pytest

from app.research_dataset import main, validate_dataset, write_report


def dataset():
    return {
        "schema_version": "1",
        "synthetic": True,
        "source_reference": "generated-software-fixture",
        "permission_reference": "synthetic-test-use",
        "rows": [
            {
                "sample_id": f"sample-{i}",
                "participant_id": f"subject-{i}",
                "split": split,
                "time_days": 0,
                "value": 0.1,
                "quality": "usable",
                "protocol_id": "synthetic",
                "protocol_version": "1",
                "mode": "self",
                "consent_reference": "synthetic-permission",
            }
            for i, split in enumerate(["train", "validation", "test"])
        ],
    }


def test_disjoint_dataset_reports_counts_without_training_or_identifiers():
    source = dataset()
    result = validate_dataset(source)
    assert result["valid"] is True
    assert result["counts"]["participants"] == 3
    assert result["splits"]["test"]["usable"] == 1
    assert result["training_performed"] is False
    assert result["clinical_use"] is False
    assert "subject-" not in json.dumps(result)
    assert validate_dataset(copy.deepcopy(source)) == result


@pytest.mark.parametrize(
    "change,code",
    [
        ({"participant_id": "subject-0"}, "participant_split_leakage"),
        ({"sample_id": "sample-0"}, "duplicate_sample"),
        ({"value": float("nan")}, "finite_number"),
        ({"time_days": -1}, "greater_than_equal"),
        ({"consent_reference": " "}, "blank_reference"),
    ],
)
def test_invalid_dataset_flags_are_precise_and_redacted(change, code):
    source = dataset()
    source["rows"][1].update(change)
    result = validate_dataset(source)
    assert result["valid"] is False
    assert code in {item["code"] for item in result["errors"]}
    assert "subject-" not in json.dumps(result)


def test_protocol_mode_and_duplicate_time_are_rejected_within_participant():
    for updates, code in [
        ({"protocol_version": "2", "time_days": 7}, "incompatible_protocol"),
        ({"mode": "assisted", "time_days": 7}, "incompatible_protocol"),
        ({"time_days": 0}, "duplicate_time"),
    ]:
        source = dataset()
        source["rows"].append(source["rows"][0] | {"sample_id": "repeat"} | updates)
        assert code in {e["code"] for e in validate_dataset(source)["errors"]}


def test_missing_poor_and_interrupted_values_are_not_imputed():
    source = dataset()
    source["rows"][0].update(value=None, quality="poor")
    source["rows"][1].update(value=None, quality="interrupted")
    result = validate_dataset(source)
    assert result["valid"] is True
    assert result["counts"]["missing_values"] == 2
    assert result["counts"]["usable"] == 1
    assert result["counts"]["excluded"] == 2
    assert result["quality_counts"] == {"usable": 1, "poor": 1, "interrupted": 1}
    assert source["rows"][0]["value"] is None
    assert result["ready_for_training"] is False


def test_provenance_unknown_fields_empty_split_and_real_data_gate():
    source = dataset()
    source["permission_reference"] = ""
    assert validate_dataset(source)["valid"] is False
    source = dataset()
    source["rows"][0]["name"] = "Unexpected identifying field"
    result = validate_dataset(source)
    assert result["valid"] is False
    assert "Unexpected identifying field" not in json.dumps(result)
    source = dataset()
    source["rows"] = source["rows"][:1]
    assert "empty_split" in {e["code"] for e in validate_dataset(source)["errors"]}
    source = dataset()
    source["synthetic"] = False
    result = validate_dataset(source)
    assert result["valid"] is True  # Structural check, not permission verification.
    assert result["ready_for_training"] is False
    assert "permission_and_protocol_require_manual_review" in result["gates"]


def test_report_hash_tracks_input_and_existing_file_is_preserved(tmp_path):
    source = dataset()
    result = validate_dataset(source)
    source["rows"][0]["value"] = 0.2
    assert validate_dataset(source)["input_sha256"] != result["input_sha256"]
    target = tmp_path / "report.json"
    write_report(target, result)
    with pytest.raises(FileExistsError):
        write_report(target, result)
    assert json.loads(target.read_text()) == result


def test_cli_writes_redacted_report_and_refuses_overwrite(
    tmp_path, monkeypatch, capsys
):
    source = tmp_path / "source.json"
    target = tmp_path / "report.json"
    source.write_text(json.dumps(dataset()))
    monkeypatch.setattr("sys.argv", ["research_dataset", str(source), str(target)])
    with pytest.raises(SystemExit) as result:
        main()
    assert result.value.code == 0
    assert json.loads(target.read_text())["valid"] is True
    assert "subject-" not in capsys.readouterr().out
    before = target.read_bytes()
    with pytest.raises(SystemExit) as result:
        main()
    assert isinstance(result.value.code, str)
    assert target.read_bytes() == before


def test_cli_rejects_leakage_and_bad_json_without_exposing_input(
    tmp_path, monkeypatch, capsys
):
    source = tmp_path / "source.json"
    target = tmp_path / "report.json"
    raw = dataset()
    raw["rows"][1]["participant_id"] = "subject-0"
    source.write_text(json.dumps(raw))
    monkeypatch.setattr("sys.argv", ["research_dataset", str(source), str(target)])
    with pytest.raises(SystemExit) as result:
        main()
    assert result.value.code == 1
    report = json.loads(target.read_text())
    assert report["splits"]["validation"]["participants"] == 1
    assert "subject-0" not in capsys.readouterr().out
    source.write_text("private invalid input")
    with pytest.raises(SystemExit) as result:
        main()
    assert "private invalid input" not in str(result.value.code)


def test_usable_flag_with_missing_value_remains_excluded():
    source = dataset()
    source["rows"][1]["value"] = None
    report = validate_dataset(source)
    assert report["valid"] is True
    assert report["counts"]["usable"] == 2
    assert "no_usable_rows_in_validation" in report["gates"]


def test_unknown_private_field_names_are_redacted():
    source = dataset()
    source["rows"][0]["synthetic-private-person-name"] = "synthetic-private-value"
    report = validate_dataset(source)
    assert report["valid"] is False
    assert "synthetic-private" not in json.dumps(report)
