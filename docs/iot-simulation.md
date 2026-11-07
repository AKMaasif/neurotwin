# Device simulation: software-only interface

This module implements the approved missing-reading, connectivity, failure/recovery and manual-review demonstration. It is a single logical simulator stream per synthetic patient, using the existing versioned Record storage, cookie/CSRF authentication, patient-scoped authorization and command receipts. No broker, external service, new dependency or database migration was introduced.

## Use

1. Participant: **Mobile → My Check → Device simulator · no physical hardware → Load device simulation**. Read the permission text, explicitly check the choice and select Allow device simulation.
2. Clinician: **Dashboard → Patient workspace → Device simulator · no physical hardware → Load device simulation**. Inject connection, activity-count, disconnect, missing-reading, fault, recovery or test-review events.
3. Select Acknowledge or Reject on an awaiting-review test signal. These decisions stay in this simulator; they never approve a care plan or dispatch emergency assistance.
4. Participant: refresh the stored state and withdraw permission with confirmation to stop future injection. Existing events and audit records remain. Withdrawal is not deletion.

Permission starts absent. No device events are seeded or generated in the background. Family accounts have neither a panel nor endpoint access. Both interfaces retain their existing styles, with the simulator in a secondary expandable panel.

## API and provenance

All routes are under `/api/patients/{pid}/iot-simulation`:

| Method / path | Contract |
| --- | --- |
| GET root `?offset=0` | Permission state, consent text/version and up to 50 newest events, with offset and total for explicit pagination. Requires participant/clinician role and assessment scope. |
| POST `/permission` | Participant only: command_id, expected_version (0 before first consent), enabled, consent_version when enabling. Cannot give proxy consent or overwrite a stale version. |
| POST `/events` | Clinician with assessment and review scopes: command_id, expected_version, increasing integer sequence, timezone-aware occurred_at, kind, and value for readings only. Active permission and the consenting participant's active assessment grant are required. |
| POST `/events/{id}/review` | Clinician only: command_id, expected_version, decision acknowledged/rejected. Only awaiting-review simulator signals are reviewable. |

Event kinds are `connected`, `disconnected`, `reading`, `missing_reading`, `fault`, `review_signal`. A reading is an integer `activity_count` from 0 to 1,000,000, unit `count`. These bounds are software input bounds, not medical normal ranges. UI counts are operator-entered examples; no human activity sensor is implemented.

The server stamps every event `simulated=true`, `source_type=simulated_device`, `clinical_use=false`, injected_by, received_at, permission_version and consent_version. Clients cannot override these fields. Permission snapshots include their text/version in the audit history. The simulator permission is separate from research-session consent and companion memory preferences.

Event sequences must strictly increase. Gaps are retained as sequence_gap rather than filled with fabricated readings. Timestamps require a timezone, cannot go backwards in the accepted stream and cannot exceed server time by more than five minutes. Equal timestamps are allowed because sequence provides ordering. Connection loss/fault prevents readings until an explicit connection/recovery event. Missing readings do not change connectivity or become zeros. Enabling after withdrawal resets connection to unknown but retains the monotonic stream history. Connection state describes the last injected event, not verified real-time availability; there is no automatic timeout watchdog.

Writes are authorized before idempotency replay, serialized by the established PostgreSQL patient-row lock and committed atomically with an audit and receipt. Reusing a command ID with changed arguments is rejected. An identical retry returns its historical receipt without performing another action; clients reload canonical state after writes. In particular, replaying an old consent receipt cannot re-enable withdrawn permission. SQLite remains a development/test option and does not provide PostgreSQL's command concurrency guarantees.

No events enter medical observations, the illustrative estimator, clinical concerns, family reports or approved treatment plans. A review_signal is an operator-injected test flag, not an inferred fall, emergency or diagnosis. There is no autonomous clinical interpretation, external delivery or background monitoring.

## Verification and remaining work

Tests are in `tests/test_iot_simulation.py`; the new browser flow is `scripts/iot_browser_check.cjs`, supported by the existing isolated browser runner. Coverage includes permission/proxy denial, scope/patient/family restrictions, non-synthetic rejection, grant revocation, stale updates, retries, timestamp/sequence/value validation, explicit failures and recovery, manual review, bounded history and provenance spoof rejection. Tests run with providers disabled and isolated synthetic databases.

The browser report and visually inspected screenshots are under ignored `test-results/iot-simulation/`. Ten end-to-end scenarios cover explicit permission, connection/count persistence, disconnect and gaps, fault/recovery, human review, withdrawal/stale-state recovery, family denial, responsive layouts/enlarged text, request failure recovery and delayed page-response isolation. Five existing browser flows run alongside this new one: research sessions, care pages, clinical design, core and companion.

Physical hardware, device enrollment/authentication, firmware, a 3D model, calibrated sensors, actual device-to-server ingestion, physical-device testing and organizer acceptance of a simulation-only submission remain unimplemented or external. This interface is deliberately named a simulator and is not suitable for accepting physical telemetry. Adding real devices requires a separately authenticated ingestion contract, reviewed consent and safety/clinical requirements.
