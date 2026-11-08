# Assessment selection and delivery

Reviewed 8 November 2026. This is an engineering and source/reuse review, not a medical endorsement, clinical validation study or approval by an institution.

## Decision

Select **SATURN 0.4.0 English as the source for a separately named research adaptation**, `saturn-derived-research` version `1.0`. The application now implements all 20 scored activity groups, plus reading and memory-presentation steps. It does **not** implement or claim a clinically validated mobile SATURN version. Formal clinical use remains unavailable; the API permits only synthetic patient workspaces.

SATURN is designed for digital, self-administered cognitive screening. Its authors deposited software, stimuli and research materials with a CC0 dedication. This provides a clearer reuse basis for an explicitly adapted prototype than instruments whose terms prohibit modification or require separate permission. The original research enrolled English-speaking adults aged 50–89 in Oregon neurology clinics and their partners; that evidence does not establish accuracy for Arabic speakers, Gulf populations, this interface, smartphones or home administration.

## Source and rights comparison

| Candidate | Fit and administration | Reuse review | Decision |
| --- | --- | --- | --- |
| SATURN, English 0.4.0 | Digital self-administration; multiple cognitive domains | Author-deposited software/stimuli marked CC0-1.0 in Dryad and Zenodo metadata | Selected source for research adaptation; no clinical norms transferred |
| Mini-Cog | Brief recall plus clock drawing; standardized health-team administration | Official contact page distinguishes clinical/educational use from research/commercial permissions | No instrument text or drawings copied into this implementation |
| GPCOG | Clinician-administered patient screen and informant pathway | Official FAQ restricts modification and describes commercial/reproduction permissions | Not selected for a redesigned self-administered mobile interface |
| 6CIT | Brief clinician-administered orientation/attention/recall | Clinical use availability does not establish unrestricted modified digital reuse; owner site could not be verified in this review | Not copied; rights review would be needed before adaptation |
| 4AT | Delirium screening; different primary clinical question | Official site permits adaptation under CC BY 4.0 and requires accurate attribution and modification disclosure | Not selected as the primary chronic-cognition activity set |

Primary references:

- Author deposit and administration/scoring materials: https://datadryad.org/dataset/doi:10.5061/dryad.02v6wwpzr
- Accessible author-deposit mirror: https://zenodo.org/records/3962060
- License metadata: https://zenodo.org/api/records/3962060 and https://datadryad.org/api/v2/datasets/doi%3A10.5061%2Fdryad.02v6wwpzr
- Original paper, Bissig, Kaye and Erten-Lyons (2020): https://doi.org/10.1002/trc2.12116 ; https://pmc.ncbi.nlm.nih.gov/articles/PMC7771179/
- Mini-Cog administration/rights: https://mini-cog.com/faqs/ ; https://mini-cog.com/contact/
- GPCOG administration/scoring/reuse: https://gpcog.com.au/index/frequently-asked-questions
- 6CIT clinical model and stated instrument rights: https://ckm.openehr.org/ckm/archetypes/1013.1.3341
- 4AT official reuse policy: https://www.the4at.com/attribution

The paper's publication license is separate from the deposited software/stimuli dedication. No paper text, participant dataset, bundled example participant results, author logo or diagnostic summary screen is redistributed. Original source code was inspected as reference, not executed. Four unchanged drawing stimuli and their checksums are retained in `web/dashboard/assessment-assets/provenance.json`.

The downloaded English archive's MD5 matched the mirror's published value, `0ae0e112078d4b792a2921243b03f3e5`. Local research downloads are ignored; only the four curated stimuli enter the app. Archive checksum matching verifies provenance/integrity, not clinical efficacy or a legal opinion.

## Administration workflow

1. Clinician opens **Dashboard → Patient → Research activities**, reviews the adaptation notice, enters the current state/emirate and an IANA timezone, and assigns it. Only one assignment can await consent, activity completion or review at a time. Assignment does not provide consent or signify clinical approval.
2. Participant opens **Mobile → My Check**. The app loads authorized assignments. The participant explicitly accepts the versioned consent, confirms English comprehension and comfortable reading, and declares self/assisted/video mode and device category. No proxy consent is implemented.
3. The server freezes the protocol, orientation date in the assigned timezone, location reference, full activity specification and participant identity. Source/version and activity definitions must still match before capture or review continues.
4. Each activity has a separate Begin action. Only the current activity can be answered. A response records values, bounded color-trial attempts, declared corrections/difficulties, client elapsed time and independent server timestamps. Client timing and assistance declarations are not verified clinical measurements.
5. A five-word presentation shows APPLE, CAR, HOUSE, PEN and TIE for two seconds each, with one-second gaps. The server rejects a completion received before 15 seconds. It does not certify frame-accurate presentation or prove the participant watched it.
6. Explicit Skip records missing evidence. It never assigns zero to a missing answer. Stop preserves the partial session for invalidation/review. Refreshing a started activity does not replay it; the participant must stop that session. Hiding the page stops the presentation locally and prevents further answers from that running view. The participant then explicitly stops the session. A 15-minute server session limit prevents further capture and marks the session interrupted on the next capture/finish command.
7. Completion requires all activity slots to be answered or explicitly skipped, plus a quality declaration. The server computes an attributed provisional research result. No model or LLM assigns points, diagnoses dementia, infers mood from video or changes care plans.
8. Clinician reviews raw evidence and conditions, checks every item, records bounded item-level decisions, rationale and a plain-language participant note. Point adjustments remain beside the original deterministic item scores. Missing evidence cannot be awarded points. Assisted/video, interrupted, skipped or declared-difficulty/poor-quality sessions cannot become accepted research results; they must be invalidated. Invalidation is reviewable, not a clinical classification.
9. Participant sees session state and the clinician's note, never answer keys, raw prior responses, provisional totals or private review rationale. Family accounts have no access to this module. Assessment results are excluded from ordinary workspace records, family reports and the care-summary export.
10. Withdrawal stops capture/review and removes the active score/review projection. Raw evidence and audit history remain under the existing retention model; withdrawal is explicitly not erasure. Historical command receipts cannot resurrect withdrawn results.

## Activity and scoring specification

The following weights come from the deposited Python source's score logs and summation. The resulting number is an **adaptation research total**, not a validated SATURN score.

| Activity groups | Maximum | Implemented rule |
| --- | ---: | --- |
| J-word, fruit selection, entering 1239 | 2 + 2 + 2 | Exact answer; declared correction disqualifies full points on these attention tasks |
| Incidental phrase, J-word and number recall | 1 + 1 + 1 | Exact structured response |
| Month, year, weekday, state/emirate | 1 + 1 + 1 + 1 | Frozen local-date and location reference; case-insensitive location match |
| Five-word recognition | 5 | One point for each original target in the five selected choices from the original 100-word list |
| Purchase total and money remaining | 1 + 2 | Exact integer answers 67 and 33 |
| Four visual composition tasks | 1 each | Exact pair of original numbered choices: 1/5, 2/6, 3/6 and 3/4 |
| Color interference task | 3 | Three practice trials excluded; subsequent 12 trials: 0/1/2/3+ wrong-color attempts yield 3/2/1/0 points |
| Number trail and alternating trail | 1 each | Exact first selection sequence; no correction/retry coaching |
| Total | 30 | Only when every scored item has evidence; no missing-item imputation |

Reading and learning-presentation steps carry no points but are required administration evidence. Skipping either makes the session unsuitable for acceptance even if the numerical item sum can be computed. Correctness of 0 points is distinguishable from a missing/null response.

## Deliberate changes from the source

- Responsive HTML controls replace the original fixed 1024×600 VisionEgg/Pygame interface. Drawings remain original PNGs; selections use separately labelled number buttons. The 100 recall choices are the original list, reflowed into accessible buttons.
- Reading phrase uses explicit acknowledgement; motor/reading-speed exploratory measures from the source are not reproduced as validated measures.
- Location accepts a clinician-set state or emirate rather than the original US-state selection screen. Date is frozen at consent, rather than recalculated during each answer. This avoids inconsistent reference answers at a midnight boundary and is a documented administration change.
- Number entry uses device keyboard controls. Attention correction is declared from the browser interaction; this is not a trusted or tamper-proof observation.
- Trail tasks use responsive dot buttons and preserve the first sequence instead of the original spatial drawing/error-correction loop. Therefore these are adapted executive-function activities, not equivalent spatial/timed Trails measurements.
- A color activity uses responsive text and labelled color buttons. Color-vision or visual difficulty must be declared; no claim of accessible equivalence for color-blind or screen-reader administration is made. Affected activities can be skipped and reviewed as invalid.
- No normative z-scores, MoCA conversion, dementia probabilities, diagnostic cutoffs, regional population scores or automatic clinical recommendations are included.
- A stopped/refreshed session cannot resume timed material. New sessions require clinician assignment and can have practice effects; repeat testing is not a longitudinal cognitive-decline estimate.

## Accessibility and privacy

One activity at a time, explicit start/save/skip/stop, labelled inputs, semantic grouped choices, selected states, visible focus, keyboard access, minimum 48px action targets, reduced-motion support, wrapping text and a native progress indicator. The source drawing can be opened full-size, but doing so interrupts the activity and invalidates continuation. This gives access to the material without silently treating altered administration as equivalent testing.

No voice or camera capture, no browser persistent answer storage and no external AI request occur in this module. Each panel captures patient, actor and workspace epoch; delayed responses from a different context are discarded. API authorization and ownership checks precede idempotent replay. Patient-row locking serializes PostgreSQL commands; version conflicts require refresh. Audit events contain session ID/version, not raw answers. Receipt records retain only minimal identifiers/status. Stored evidence fields are bounded by Pydantic/domain checks; the activity specification is a fixed server-defined protocol.

## Required before real clinical use

Not complete in this build: a named qualified clinical lead must approve instrument suitability, consent/capacity and proxy procedures, administration conditions, scoring/adjudication policy, language/device eligibility, repeat intervals, follow-up and emergency pathways. The adapted implementation needs fidelity/usability studies and independent validation for its intended population and devices, plus applicable data-governance/regulatory review. A demo clinician clicking Review does not satisfy any of these conditions. Do not lift the synthetic-only server gate on that basis.

Clinical sign-off record to obtain externally: clinician name/credentials; institution; exact protocol version; intended population/language/device/mode; approved administration/scoring; limitations; follow-up responsibility; approval date and evidence. No such record has been supplied.

See `assessment-delivery-checklist.md` for delivery status and `assessment-verification.md` for executed engineering checks.
