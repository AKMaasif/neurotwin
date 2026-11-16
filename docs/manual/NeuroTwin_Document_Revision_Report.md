# NeuroTwin document revision report

**Source:** *NeuroTwin_Complete_Clinical_and_Brain_Analytics_Manual.pdf*, Edition 1.2, 136 pages, local build b0044e9.
**Result:** *IFHAS-NeuroTwin_Professional_Clinical_Product_Manual.pdf*, Edition 2.0, 75 pages, software revision e9db1ca.
**Date:** 16 November 2026.

All 136 pages of the original were read as extracted text. The new PDF was rendered and every page was inspected
as an image. Original text is quoted briefly or paraphrased (marked "paraphrase"). "Evidence" points to the repository
at e9db1ca, to a check run on 16 Nov 2026, or to the new manual. The application source code was not modified.

## 1. Structural changes

| Original page | Original text | Revised text | Reason | Evidence | Unresolved item |
|---|---|---|---|---|---|
| Every page (1–136) | Footer: "Research prototype · synthetic data · not a medical device" and "Research prototype \| separate synthetic personas and de-identified scans \| no clinical validation" | One cover statement plus Section 2, *Intended use, limitations and data provenance*. The footer now reads "Revision e9db1ca · Research software · intended use: Section 2". | The instructions asked for repeated disclaimers to be consolidated. Nothing was dropped: every limitation from the footers is in Section 2. | Manual §2 | — |
| 3–5 | Contents and list of figures (static) | Clickable contents, 83 PDF bookmarks and a clickable list of figures | The instructions asked for navigation. | 292 internal links on pages 3–7 of the new PDF | — |
| 6–66 (A–H, appendices) and 97–136 (J) | Two overlapping guides. Page 2 says "For the current prepared clinical/imaging environment use section J. The original illustrated guide (pages 6-62) … remain for continuity" | One guide in 21 sections and 6 appendices. Section J's Brain Analytics content was merged into Sections 13–17. | Two guides that partly contradict each other cannot be read safely. | Manual contents | — |
| 67–96 | "I. A judge's route through NeuroTwin" and the judges' evidence dossier | Removed as a section. Content still valid was moved: evaluation results to §20, privacy to §19, architecture to Appendices B and C, claims boundaries to §2. | The material was written for a competition, not for users. The instructions asked for no promotional framing. | Manual §§2, 19, 20 | The dossier's business and market text (pp. 88–92) is not in the manual. It is in docs/BUSINESS_CASE.md. |
| 58–62 | Appendix A navigation inventory (every control) | Control-level detail folded into the step-by-step text of §§7–17. The feature status register is now Appendix A. | The status register was asked for. The control inventory was 5 pages of a table that repeated the guide. | Manual App. A | A per-control inventory could be added back as an annex if a test team needs it. |
| 1 | "Edition 1.0 (draft for owner review)" next to "EDITION 1.2" | "Edition 2.0, 16 November 2026" | The cover was internally inconsistent. | Manual cover | — |

## 2. Authorship and drafting language

| Original page | Original text | Revised text | Reason | Evidence | Unresolved item |
|---|---|---|---|---|---|
| 1–2 | "Project owner … A.K.M. Aasif", "MIT Open Source" | Kept: "Project owner and licence: A.K.M. Aasif, as named in Edition 1.2. MIT licence." | This is real attribution taken from the source. No authorship was invented. | LICENSE, THIRD_PARTY_NOTICES.md | — |
| 2 | "Owner, clinical, native-language and legal review remain necessary. The guide is supporting evidence, not medical approval or a judging guarantee." | "Review status: not yet reviewed by an independent clinician, an Arabic-language reviewer or a legal or regulatory adviser." | Required disclosure kept; the competition wording was removed. | Manual, Document control | All three reviews are still open. |
| 2 | "Desktop screenshots and cropped details, not recreated mockups." | A screenshot-method row: unedited screenshots at e9db1ca, 16 Nov 2026, headless Chromium, personas and OASIS scans only. | The disclosure is kept and updated for new captures. | Manual, Document control | — |
| 36 | "Arabic wording is machine-and-author drafted" | "Arabic wording was drafted by the developer with machine-translation assistance and has not had a formal native-language or cultural review." | This is a required disclosure about translation quality, so it was kept. Only the phrasing changed. | Manual §2.5 | Native-language review is still open. |
| 44, 47 | "Mock-provider output: All drafted text in this manual is scripted stand-in text." | Note in §12: "Scripted demonstration mode … must never be described as a model's output". The AI-mode status bar is explained in §5. | The disclosure is kept and tied to the on-screen status. | Fig. 34; status bar in every clinician figure | — |
| Various | Statements that model features "draft" text | Kept. The AI features are described factually as drafting under clinician review. | The instructions said to keep professional descriptions of the AI features. | §§10.5, 12, 16.3, 17 | — |

## 3. Claims, validation and compliance wording

| Original page | Original text | Revised text | Reason | Evidence | Unresolved item |
|---|---|---|---|---|---|
| 6 | "This guide does not establish medical-device approval, diagnosis, validated prediction or clinical benefit." | §2.3: "no regulatory clearance or approval in any jurisdiction … not been clinically validated" | Consolidated into one place. | Manual §2.3 | — |
| 90 | "Consent controls and tests … do not establish UAE health-data-law, GDPR, HIPAA or medical-device …" | §2.3 lists HIPAA, GDPR, UAE health-data law, ISO 13485, IEC 62304 and ISO 14971, and states that no compliance is claimed. | The instructions forbid compliance claims without evidence. | Manual §§2.3, 19 | No conformity assessment exists. |
| 20 | "Implemented with limitations: English only; no validated Arabic wording." (WHO-5) | "Partial. … shown in English only (in the published wording)." | The status was made explicit. "Validated" is no longer used positively. | Fig. 12 | Whether a licensed, validated Arabic WHO-5 can be used is open. |
| 21 (picture memory) | Described as a memory activity | "It is not a validated memory test." | This prevents the activity being read as a cognitive assessment. | Manual §7.4 | — |
| 84 | "recorded result: 47/50 correctly mapped (94%)" | Kept in §20 with its limits: sentences written by one developer, spoken input not tested. | The number is unchanged; the limits now sit next to it. | docs/COMPANION_EVALUATION.md | — |
| 89, 91 | "validated triage", "No first-in-market, best accuracy …" | Not reproduced. §20 states what each benchmark does not show. | No superiority or market claims are made. | Manual §20.2 | — |
| — (new) | — | §20.2 adds the emergency held-out history (17/20, 18/20, 8/20, 0/20, 3/20). | Edition 1.2 did not show that held-out sensitivity drops sharply. Leaving it out would overstate safety. | docs/EMERGENCY_BENCHMARK.md | No fresh held-out set exists for the current rule. |
| — (new) | — | Change-engine figures from simulation (95.2% stable; 33.2/60.8/81.3% detection at 2/3/4 SD) are labelled "not clinical sensitivity or specificity". | Added with their limits so they are not read as clinical accuracy. | docs/CHANGE_ENGINE_BENCHMARK.md | — |

## 4. Implementation status updates (b0044e9 → e9db1ca)

| Original page | Original text | Revised text | Reason | Evidence | Unresolved item |
|---|---|---|---|---|---|
| 2, 9, 63, 75–77 | "Local source b0044e9"; "Fresh run, b0044e9: 648 passed, 1 failed, 0 errors and 13 skipped" | "756 passed, 14 skipped, 0 failed (6 min 10 s)" at e9db1ca; vitest 60/60; build succeeded | The figures were re-run on the current revision. | pytest output on 16 Nov 2026 | SUBMISSION.md quotes 775 passed and 12 skipped, which differs from today's run. Not edited; see the verification report. |
| 11, 63, 78 | "Known in this tested build: 'well-being questions' opens check-in." | Removed from troubleshooting. | Fixed in 8465aa6, with regression tests. The suite passes today. | git log 8465aa6; backend tests | — |
| 9 | "The remote branch was observed at 8465aa6 …" | §4.3: "Whether the public remote contains e9db1ca was not checked here." | The remote was not re-checked, so the manual says so. | — | Push and freeze the commit you intend to submit. |
| 11 | "No deployment URL was supplied …" | §4 note "Public access": no hosted address was verified. | Still true. | — | Deploy by 18 Nov and re-check. |
| — (new) | — | §8.1 *Model answers (optional)*: provider, operator setting and assistant_model consent; fixed action menu | Feature added after Edition 1.2 (e9db1ca). | assistant_ai.py, test_assistant_ai.py | Not exercised with a live provider. |
| — (new) | — | §7.1 daily routine; §7.12 About you; §7.3 Today's conditions; §8.1 "Do you need urgent help now?" | Features added after Edition 1.2. | Figs 1, 4, 16; profile.py; emergency.py | — |
| — (new) | — | §18 FHIR R4 download | Feature added after Edition 1.2. | Fig. 64; fhir.py; test_fhir.py | The independent FHIR library test was skipped (library not installed). |
| — (new) | — | §10.4 change-engine/0.2: practice sessions, z-score, provisional RCI with assumed r = 0.8 | Feature added after Edition 1.2. | change.py; docs/RELIABILITY_STUDY.md | Test–retest study not done. |
| 28, 35 | Voice companion "Implemented and verified …" | §8.2: off by default; speech-to-text for demo accounts only; server voice only with GEMINI_TTS_MODEL, otherwise the browser voice | Current behaviour at e9db1ca. | voice.py; speak.ts; commit 335c855 | No real-voice evaluation. |
| 53, 56, 62 | "Run agent replays a recorded run" | §16.1: "Run agent" replays without calling any provider; live runs need keys and antspyx. | Confirmed in the running app. | Figs 46–53 | The idle text in the Agent Activity panel still says "Press Run live", but that button was removed. Recorded in §20.3; the code was not changed. |
| 107 | "Export measurements downloads a CSV …" | §13.2 kept. §12 adds activity-analysis SVG and CSV export. | Checked in source. | BrainAnalytics.tsx:41; ActivityAnalysis.tsx:323 | — |
| 57 | Privacy table | §3.2 consent scopes, §19 "What the code does" and "What has not been established" | Split so that implemented controls and missing assurance are not mixed. | auth.py, security.py, main.py:877 (/audit) | DPIA, penetration test, retention policy. |

## 5. Screenshots

| Original page | Original text | Revised text | Reason | Evidence | Unresolved item |
|---|---|---|---|---|---|
| All figures (orig. figs 1–60, J1–J28) | Captures from b0044e9 and earlier | 64 new captures from e9db1ca on 16 Nov 2026. None were reused or edited. | The software has changed since the earlier captures. The instructions require authentic screenshots. | Scratch capture scripts; the method is in Document control | — |
| — | — | Fig. 35 caption corrected during QC to "entry page", not the OASIS case | The image shows the access gate. | Rendered page 43 | — |
| — | — | Arabic heading text was removed from body text because the PDF font cannot shape Arabic. Arabic screens appear as screenshots (Fig. 2). | Unshaped Arabic text would have rendered wrongly. | QC render of page 17 | — |

## 6. Section mapping

| Original section (pages) | New location |
|---|---|
| A Orientation (6–8) | §1, §2, §6 |
| B Installation (9–11) | §4, §5, §21 |
| C Patient guide C.1–C.17 (12–37) | §7, §8 |
| D Family (38–39) | §9 |
| E Clinician E.1–E.8 (40–51) | §10, §11, §12 |
| F 12-step journey (52) | §1 overview and §§7–17 in order; the separate step table was dropped |
| G Imaging (53–56) | §13–§16 |
| H Privacy (57) | §3, §19 |
| Appendices A–E (58–66) | App. A–F |
| I Judges' dossier (67–96) | Removed; valid content moved to §2, §19, §20 and App. B–C |
| J Clinical and Brain Analytics (97–136) | §10, §13–§17, App. D |
