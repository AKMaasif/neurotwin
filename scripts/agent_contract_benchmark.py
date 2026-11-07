"""Execute service-contract cases and report evidence per registry role, not clinical accuracy."""

import datetime as dt
import hashlib
import json
import subprocess
import sys
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path

from app.agents import AGENTS

# Shared contracts are intentionally attributed to more than one role. They are
# not independent model experiments and must not be added together as such.
CONTRACTS = {
    "A1": ["test_capture_abstains_without_comparable_history"],
    "A2": [
        "test_extraction_and_verification_never_activate_plan",
        "test_unsupported_extraction_rejected",
        "test_source_correction_invalidates_linked_draft",
        "test_draft_source_qa_and_human_review_status",
        "test_extraction_rechecks_source_revision_after_model_call",
    ],
    "A3": [
        "test_task_guidance_confirmation_and_stale_plan",
        "test_task_idempotence_and_conflict",
        "test_family_cannot_confirm_patient_tasks",
        "test_plan_signed_revision_updates_mobile",
        "test_correction_flags_approved_plan_and_blocks_stale_task",
    ],
    "A4": [
        "test_case_review_and_urgent_hold",
        "test_unapproved_plan_not_visible_to_family",
        "test_clinician_proposal_requires_participant_consent",
        "test_late_response_is_rejected_even_if_worker_was_unavailable",
        "test_pause_resume_and_source_correction_cancel_old_reminders",
    ],
    "A5": [
        "test_size_proposal_is_not_executed_and_safety_precedes_navigation",
        "test_provider_failure_and_revoked_inflight_request",
        "test_negated_navigation_and_stop_never_execute",
        "test_silent_empty_transcript_and_revoked_asr",
        "test_cloud_context_requires_separate_consent_and_rechecks_forget",
    ],
    "A6": [
        "test_help_round_trip",
        "test_revocation_blocks_read_and_send",
        "test_help_contacts_status_and_revocation",
        "test_changed_help_recipient_cancels_previous_request",
        "test_snooze_followup_acknowledgement_and_acceptance",
    ],
    "A7": [
        "test_weekly_timezone_cohorts_no_invented_denominator",
        "test_clinical_projection_and_approval_visibility",
        "test_stale_snapshot_rejected_and_rejection_allowed",
        "test_empty_week_caps_and_non_synthetic_ai",
        "test_scheduled_date_templates_cancellations_and_historical_plans",
    ],
    "A8": [
        "test_invalid_model_output_rejected",
        "test_unsupported_extraction_rejected",
        "test_draft_source_qa_and_human_review_status",
        "test_ai_exact_fact_validation_and_inflight_checks",
        "test_extraction_rechecks_source_revision_after_model_call",
    ],
}


def summarize(xml_path):
    cases = []
    for case in ET.parse(xml_path).iter("testcase"):
        state = "passed"
        for tag in ["failure", "error", "skipped"]:
            if case.find(tag) is not None:
                state = tag
        cases.append(
            {
                "id": case.get("classname") + "::" + case.get("name"),
                "name": case.get("name"),
                "state": state,
                "seconds": float(case.get("time", 0)),
            }
        )
    result = {}
    for key, names in CONTRACTS.items():
        relevant = [case for case in cases if case["name"].split("[")[0] in names]
        missing = [
            name
            for name in names
            if not any(case["name"].split("[")[0] == name for case in relevant)
        ]
        # Strip DB fixture variation, retaining meaningful scenario parameter IDs.
        scenarios = {
            case["name"].replace("[sqlite]", "").replace("[postgres]", "")
            for case in relevant
        }
        passed = sum(case["state"] == "passed" for case in relevant)
        verified = not missing and len(scenarios) >= 5 and passed == len(relevant)
        result[key] = {
            "name": AGENTS[key]["name"],
            "implementation": AGENTS[key]["implementation"],
            "required_manual_reviewer": AGENTS[key]["reviewer"],
            "scenario_count": len(scenarios),
            "executions": len(relevant),
            "passed": passed,
            "contract_pass_percent": round(100 * passed / len(relevant), 1)
            if relevant
            else None,
            "missing_contracts": missing,
            "status": "contracts_passed" if verified else "review_required",
            "recommendation": "Retain human review; clinical/model quality and real-device evaluation remain separate."
            if verified
            else "Investigate failing, skipped or missing contracts before accepting this role's output.",
            "cases": relevant,
        }
    return result


def main():
    root = Path(__file__).resolve().parents[1]
    out = root / "test-results" / "agent-contracts"
    out.mkdir(parents=True, exist_ok=True)
    xml_path = out / f"results-{uuid.uuid4().hex}.xml"
    files = [
        "test_capture_boundaries",
        "test_documents",
        "test_companion",
        "test_workflows",
        "test_routines",
        "test_reports",
        "test_numerics_ai",
    ]
    execution = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            *[f"tests/{name}.py" for name in files],
            "-q",
            f"--junitxml={xml_path}",
        ],
        cwd=root,
        check=False,
    )
    if not xml_path.exists():
        raise SystemExit("No current test report produced; benchmark not scored")
    roles = summarize(xml_path)
    report = {
        "schema_version": "neurotwin.agent-contract-benchmark.v1",
        "at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "mode": "Synthetic service-contract regression; provider transport failures/outputs are test doubles. No live model calls.",
        "clinical_validation": False,
        "model_accuracy_measured": False,
        "score_definition": "Percentage of selected contract test executions passing. Shared tests are reused across roles; this is not clinical accuracy or independent agent reliability.",
        "evidence_sha256": hashlib.sha256(xml_path.read_bytes()).hexdigest(),
        "evidence_file": xml_path.name,
        "pytest_exit_code": execution.returncode,
        "roles": roles,
    }
    (out / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    for key, role in roles.items():
        print(
            f"{key}: {role['passed']}/{role['executions']} contract executions; {role['scenario_count']} scenarios; {role['status']}"
        )
    raise SystemExit(
        0
        if execution.returncode == 0
        and all(role["status"] == "contracts_passed" for role in roles.values())
        else 1
    )


if __name__ == "__main__":
    main()
