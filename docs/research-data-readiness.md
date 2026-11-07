# Research dataset preflight

The user confirmed that no clinician-approved assessment instrument has been selected. Formal My Check administration/scoring remains gated. This offline tool checks the existing research scalar data contract before future model work; it does not approve an instrument, verify permission documents, train a model or produce patient results.

## Run

From the project directory, create a report in an existing private/local output directory:

```powershell
uv run python -m app.research_dataset examples/research-dataset.synthetic.json test-results/research-dataset-example.json
```

The input example is an explicitly hand-authored software fixture, not clinical data or a training cohort. The CLI returns exit code 0 when structural/consistency checks pass, 1 when they fail, and an error for unreadable/malformed/oversized input or an existing output. It refuses to overwrite reports, including the original input. Choose a new report filename for subsequent runs. The input limit is 10 MB and 100,000 rows. No database, provider credentials or external service is used.

## Input contract

The version-1 JSON object requires schema_version, synthetic, source_reference, permission_reference and rows. Each row requires a sample ID, pseudonymous participant ID, split (`train`, `validation`, `test`), relative time_days, scalar value or null, quality (`usable`, `poor`, `interrupted`), protocol ID/version, administration mode (`self`, `assisted`, `video`) and consent_reference. Unknown fields and blank references are rejected. Do not place names, dates of birth or contact details in identifiers/references; the tool cannot determine whether a supplied identifier is genuinely pseudonymous.

The scalar contract matches the existing illustrative research input: finite values from −10 to 10, relative times from 0 to 36,500 days. These are software bounds, not medical normal ranges. Real instruments require reviewed, versioned preprocessing and their own domain/scoring contract; raw clinical scores must not be silently forced into this range.

Checks:

- A participant may belong to exactly one split, including repeated visits. This detects row-level split leakage; it does not detect linked identities using different pseudonyms.
- Sample IDs must be unique, and each participant's relative times must be unique.
- A participant's longitudinal series must use a consistent protocol ID, protocol version and administration mode. The tool does not establish equivalence between different participants' protocols or permit pooled model training.
- All three splits must contain rows. A split without usable non-null values has an explicit gate.
- Null values, poor quality and interruptions remain represented. They are counted separately and excluded from usable counts; no zero-filling or other imputation is performed.
- Source, permission and per-row consent references must be present. Presence is not a check of their validity, authenticity, licensing, consent scope or continued applicability.

## Report interpretation

`valid` means the supplied contract and consistency rules passed. `ready_for_training`, `training_performed` and `clinical_use` remain false: permitted data review, protocol selection, suitable labels, sample sufficiency, preprocessing, training and independent model validation are outstanding. Neither real nor synthetic input can toggle those gates through this tool.

Reports contain split/quality counts, redacted error locations/codes and up to 50 error entries with the total error count. They omit input participant/sample identifiers, raw values and source/consent reference contents. Validated datasets also receive a SHA-256 fingerprint of normalized validated JSON (dictionary keys sorted; row order retained), tied to a validator version. This fingerprints the supplied content; it is not proof of consent or anonymization. No timestamp is added, so the same input yields the same report. Raw source data remains only in the operator's chosen input file and transient process memory.

This tool is not an authenticated upload/export endpoint and cannot pull private app records or bypass enrollment/access controls. It creates no medical record, model artifact or patient-visible score. The mobile and clinical UI designs are unchanged.

## Verification

Tests were written first and reproduced the missing module. Dataset validation and related capture/numerical contract tests exercise split leakage, duplicate IDs/times, incompatible protocols/modes, non-finite/out-of-range inputs, blank provenance, unknown-field redaction, missing/poor/interrupted data, deterministic fingerprints, CLI exit codes and overwrite protection. Exact current results are recorded in DEVELOPMENT_PLAN.md and ignored `test-results/dataset-readiness-tests.xml`. The synthetic example was also executed through the actual CLI, separately from the test runner.

Next clinical input: select an assessment instrument and obtain its appropriate administration/scoring and reuse requirements with qualified clinical review. Next model input: permitted longitudinal records with reviewed outcome labels and a versioned preprocessing contract. The validator prepares those engineering checks without implying that either dependency is already satisfied.
