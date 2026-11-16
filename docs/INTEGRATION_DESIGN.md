# Integration design: FHIR R4, the provider's health record, Malaffi and Sahatna

**Status:** a design for the pilot. **What works today:** a person, or a clinician they chose, can download the
person's records as an HL7 FHIR R4 Bundle (`GET /api/participants/{id}/fhir`, button "Download FHIR R4" on the
clinician report; code `backend/app/fhir.py`, tests `backend/tests/test_fhir.py`). **What does not exist:** no
connection to any electronic health record, to Malaffi or to Sahatna. Nothing is sent anywhere automatically.

Facts about Malaffi and Sahatna below are from public descriptions. Formats, onboarding steps and any interface
must be confirmed with the Department of Health – Abu Dhabi (DoH) and Malaffi during the integration study.

## 1. Where NeuroTwin sits

```
 Person's phone / tablet          Clinic                                   Abu Dhabi
 ┌──────────────────────┐   FHIR R4   ┌───────────────────────────┐   existing   ┌──────────────────────┐
 │ NeuroTwin personal   │ ──────────▶ │ NeuroTwin clinician view  │   feed       │ Malaffi (health      │
 │ app (records,        │  (server)   │   │ clinician decides       │ ───────────▶ │ information exchange)│
 │ reminders, help)     │             │   ▼                       │  (the EMR's, │          │           │
 └──────────────────────┘             │ Facility EMR (holds the   │   not ours)  │          ▼           │
                                      │ Emirates ID, already      │              │ Sahatna (DoH patient │
                                      │ connected to Malaffi)     │              │ app) shows records   │
                                      └───────────────────────────┘              └──────────────────────┘
```

NeuroTwin is a **clinician-review layer**. It does not become a source system for the exchange. The facility's
health record (EMR) already has the person's identity, the legal relationship with Malaffi and the clinical record;
NeuroTwin hands the EMR a small, reviewed set of records and lets the EMR decide what goes further.

## 2. Options considered

| Option | How | For | Against | Decision |
|---|---|---|---|---|
| A. File download (exists) | Clinician downloads the FHIR file and imports or attaches it in the EMR | Works today; no interface to build; the clinician sees exactly what moves | Manual; depends on the EMR accepting FHIR files | **Now** |
| B. FHIR API to the facility EMR | NeuroTwin server sends the Bundle (transaction, conditional update by identifier) to the EMR's FHIR endpoint after a clinician approves; or the EMR launches NeuroTwin with SMART on FHIR and reads it | No retyping; the EMR stays the record of care and its existing Malaffi feed carries what it chooses | Needs the EMR vendor's FHIR endpoint and an agreement per facility | **Pilot** |
| C. Direct contribution to Malaffi | NeuroTwin onboarded as a data provider | One connection for all facilities | NeuroTwin is not a licensed healthcare facility; duplicates the EMR's role; heavy onboarding | **Not planned** |
| D. Sahatna | The person sees NeuroTwin-derived entries in Sahatna | People already use it | Only through Malaffi, i.e. through option B and the EMR; no direct path is assumed | **Follows B** |

## 3. What moves, and what never moves

The Bundle (`fhir-export/0.1`) carries:

| NeuroTwin | FHIR R4 | Notes |
|---|---|---|
| The person | `Patient` | Internal identifier, display name, preferred language. No Emirates ID, birth date or contact details (NeuroTwin does not hold them). |
| Each current record | `Observation` | Value with a UCUM unit (`ms`, `h`, `{count}`, `{score}`); category `exam` (activities) or `survey` (self-reports); activity and version in `method`; quality label in `meta.tag`; "today's conditions" as boolean `component`s; missing values carry `dataAbsentReason`; a note that prototype activities are not validated instruments. |
| Amended or withdrawn records | `Observation` with `amended` / `entered-in-error` | Only when history is asked for, so a receiver can correct what it received earlier. |
| Which software made each record | `Provenance` | One per producer and version. |
| Consent decisions | `Consent` | One per scope, latest decision; `active` + permit or `inactive` + deny. |

Never in the export: change estimates (provisional decision support computed on view), model-written drafts,
messages, the assistant conversation, family messages, education and first language, imaging research output.

Resource ids are stable (UUID v5 from the record id), so sending again updates rather than duplicates.

## 4. Identity

NeuroTwin does not store the Emirates ID and should not need to. In option B the link is made **once, at the EMR**:
the clinician opens NeuroTwin from the EMR (SMART on FHIR launch) or picks the person in the EMR, and NeuroTwin
stores the EMR's patient reference against its own participant id. Every later export carries that reference as a
second `Patient.identifier`. The EMR's own matching to Malaffi is unchanged.

## 5. Terminology

- Units: UCUM (done).
- Codes: every activity and measure is coded in NeuroTwin's own code system (placeholder namespace
  `https://neurotwin.example/fhir`, to be replaced by a registered one). The activities are prototypes with no
  published code, and inventing a standard code would mislead a receiver.
- WHO-5: map the total and items to LOINC during the integration study, checked by a terminologist.
- If DoH or Malaffi publish a FHIR implementation guide or profiles, the export is profiled against it and validated
  with the HL7 FHIR validator before any live exchange.

## 6. Consent and control

Before option B can send anything:
1. A new consent scope, "share with my health record", explained in English and Arabic, separate from participation.
   Withdrawing it stops future sends; it cannot recall what the EMR already holds, and the consent text says so.
2. A clinician approves each send and sees exactly what will go (the same Bundle as the download).
3. Every export and send is in the audit log (`fhir.exported` today), with no values.

## 7. Security and data residency

- Transport: TLS; server-to-server authentication with SMART Backend Services (OAuth 2.0 client credentials with a
  signed JWT) or the EMR vendor's equivalent.
- Data stays in the UAE, as UAE health-data law requires for health data (the Federal Law on the use of ICT in health
  fields); hosting and any AI provider must follow the residency choice agreed in the ethics and DoH process.
- Align with DoH information and cyber-security requirements for healthcare (ADHICS) and the DoH patient-data
  privacy standard; to be confirmed with the facility's information-security team.

## 8. Steps and gates

| Step | Done when |
|---|---|
| 1. FHIR R4 export and download | **Done**: Bundle checked against the R4 rules it relies on (8 tests; an optional stricter check runs where the `fhir.resources` library is installed) |
| 2. Validate with the official HL7 FHIR validator | No errors against R4 base; any warnings explained |
| 3. Confirm with DoH / Malaffi | Written answer on formats, any implementation guide, and whether option B is the right route |
| 4. "Share with my health record" consent | Wording reviewed in both languages; tests |
| 5. EMR sandbox (one vendor) | SMART launch and a send to the vendor sandbox; correction by resend shown |
| 6. Pilot facility | Information-security review, data-sharing agreement, clinician training, then live with a small group |

## 9. Try it

```bash
# as the demo clinician, after signing in (a read needs only the session cookie)
curl -s -b "nt_session=…" http://localhost:8000/api/participants/demo-fatima/fhir > fatima-fhir-r4.json
```

Or open a person in the clinician view, choose "Report", then "Download FHIR R4".
