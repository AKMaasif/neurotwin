# NeuroTwin sells change detection to providers

> **Note added after this report.** The business case (docs/BUSINESS_CASE.md) uses **AED 15 per person per month**,
> not the AED 30 shown here. A later check found that Abu Dhabi already pays AED 200 for a clinician's review of
> digitally sent data (CPT 99091, DoH Addendum 30), so the lower price keeps the yearly fee below one billable review.
> The statement below that no UAE tariff could be verified is now out of date. See section 6 of the business case.

The business case for NeuroTwin is strongest as a **provider-paid (B2B2C) monitoring service**, not a consumer app or a fee-for-service test. The Gulf is about to age faster than anywhere else. GBD forecasts put the UAE's dementia cases at **+1,795% between 2019 and 2050**, against +166% globally. Arabic cognitive assessment, meanwhile, is still mostly paper tests with thin evidence on *detecting change*. And NeuroTwin's variable running cost is **about USD 0.35–1.50 per active user per month**, so a modest per-patient fee leaves gross margins above 80%. What is not yet proven is who in the UAE will pay, and how much. No UAE payer, tariff or reimbursement rule for digital cognitive monitoring could be verified. Every price in this report is therefore an estimate anchored on US reimbursement rates and UK health-economic data, and the first commercial task is to win a paid pilot with a DoH-licensed Abu Dhabi provider. On my estimates, the addressable market is **about 1.33 million UAE residents aged 50+** (roughly USD 130 million a year at an illustrative AED 360 per person per year), **about 8.0 million across the GCC** (about USD 780 million), and nearly a billion people aged 50+ in seven Asian markets. A realistic five-year UAE share of 1–5% yields **USD 1.3–6.5 million in annual recurring revenue** (estimate). The regulatory route depends almost entirely on the claims NeuroTwin makes. The US FDA device category for cognitive assessment aids explicitly includes "monitoring changes in cognitive function over time", so "not a diagnostic" does not automatically mean "not a medical device".

> **How to read this report.** Web search was broken during the research. Statements with an inline citation were read from the cited source on 16 November 2026. Anything labelled **estimate** is my own arithmetic, with the working shown. Items the researchers could not verify appear only in the **"To confirm"** table at the end and are never stated as fact in the body. Exchange rate: 1 USD = AED 3.6725.

## Provider groups pay, because UAE reimbursement for this is unproven

The comparable vendors do not sell to consumers at a list price. BrainCheck, Cognivue, Neurotrack and Linus Health sell to providers, health systems and health plans on "request a demo" terms, and none publishes a price ([BrainCheck](https://braincheck.com/); [Neurotrack](https://neurotrack.com); [Cognivue](https://cognivue.com)). Their argument to buyers is that the test pays for itself through US billing codes. Cognivue states that insurers reimburse providers both for administering its test and for interpreting it ([Cognivue reimbursement](https://cognivue.com/reimbursement/)). BrainCheck's 2025 reimbursement guide maps its product to CPT codes worth **USD 158.82 per test encounter (96138 + 96132, about AED 583)** and **USD 266.21 for a cognitive assessment and care-plan visit (99483, about AED 978)** at the 2025 national Medicare rate ([BrainCheck 2025 Reimbursement Guide](https://info.braincheck.com/hubfs/4)%20Documents/2025%20Reimbursement%20Guide_MKT006_Rev004.pdf)). US policy is also moving toward per-patient monthly payment. The CMS GUIDE dementia model, which runs for 8 years from 1 July 2024, pays a tiered monthly per-patient care-management fee plus **up to USD 2,500 a year in respite** per eligible patient ([CMS GUIDE Model](https://www.cms.gov/priorities/innovation/innovation-models/guide)). A continuous monitor like NeuroTwin fits a monthly per-patient structure far better than a one-off test code.

None of this transfers automatically to Abu Dhabi. The researchers could not verify any Daman or Thiqa reimbursement, DoH tariff, or government screening budget for digital cognitive monitoring. That is the single largest gap in the case. The institutional route is nonetheless clear from verified sources. Every DoH-licensed facility must connect to Malaffi, the Abu Dhabi health information exchange. Unconnected facilities cannot renew their licence, and facilities with Daman contracts cannot submit claims until connected ([Malaffi: facilities required to connect](https://www.malaffi.ae/providers/facilities-required-to-connect/)). The exchange links **more than 3,000 hospitals and facilities** ([Malaffi LOINC article](https://www.malaffi.ae/beyond-connectivity-malaffi-marks-90-loinc-adoption-laying-the-foundation-for-intelligent-healthcare/)). An app vendor does not plug into Malaffi itself. Connection is free, but the provider pays for the secure link, and the connected system is the provider's EMR ([Malaffi: connected EMRs](https://www.malaffi.ae/connected-emrs/)). NeuroTwin's buyer is therefore the DoH-licensed provider. Its FHIR R4 export lands in that provider's EMR, which already carries data to Malaffi.

### Pricing model (estimate)

I recommend a per-enrolled-patient subscription paid by the provider, with a family add-on and programme contracts layered on top. The figures below are **estimates** built from the cited anchors, not market prices.

| Tier | Who pays | Illustrative price (estimate) | Reasoning |
|---|---|---|---|
| Clinic licence | DoH/DHA-licensed provider (primary care, longevity, diabetes or cardiology clinic) | **AED 30 per enrolled patient per month** (≈ USD 8.17; AED 360 ≈ USD 98 a year) | A year of monitoring costs about **37% of one US 99483 visit** (AED 360 ÷ AED 978). It sits well below the per-encounter value providers already accept for cognitive testing in the US. |
| Programme contract | Government health programme, insurer or provider group buying for a defined population | Volume discount on the clinic rate, e.g. AED 20–25 per person per month (estimate) | Mirrors GUIDE's per-patient monthly logic. Needs a buyer with a prevention budget, which is not yet verified. |
| Family add-on | Adult children or the person themselves | Optional, flat monthly fee (level to be tested) | Informal care accounts for about half of the **USD 1.3 trillion** global dementia cost ([WHO](https://www.who.int/news-room/fact-sheets/detail/dementia)), so families carry a real burden. Gulf consumer willingness to pay is unverified. |
| Research licence | Pharma, academic or registry partners, with consent | Per-study contract | Cogstate and Cambridge Cognition both market trial-focused products ([Cogstate](https://www.cogstate.com/investors/); [Cambridge Cognition](https://www.cambridgecognition.com/investors/)). Arabic longitudinal data is scarce. |

The value case for a buyer rests on the economics of digital triage. A UK model found a digital cognitive test dominated standard tools, saving about **£123 per person in primary care and £226 in memory clinics over a lifetime** ([Front Public Health 2023, PMID 37841740](https://pubmed.ncbi.nlm.nih.gov/37841740/)). That evidence is for a one-off test in the NHS, not for NeuroTwin. NeuroTwin will need its own UAE pilot data before any buyer accepts an equivalent claim.

## Each active user costs about AED 1.3–5.5 a month to run

NeuroTwin's variable costs are small because its heavy components (language-model summaries and voice) are cheap at the volumes a check-in app uses. Notifications are the only line that matters. The figures below come from the providers' own price lists. The per-user totals are estimates.

UAE data residency adds about **16–30%** to cloud prices. On Azure UAE North, compute and managed PostgreSQL run 16–23% above East US. On AWS me-central-1, RDS runs 17–22% above us-east-1 and Fargate 30% above it ([Azure Retail Prices API](https://prices.azure.com/api/retail/prices); [AWS RDS me-central-1 price list](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonRDS/current/me-central-1/index.csv); [AWS ECS me-central-1 price list](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonECS/current/me-central-1/index.csv)). Google Cloud has no UAE region; its nearest are Doha and Dammam ([GCP regions](https://cloud.google.com/compute/docs/regions-zones)). Oracle runs live regions in Dubai and Abu Dhabi ([Oracle regions](https://www.oracle.com/cloud/public-cloud-regions/)).

A minimal production stack is a fixed cost of about **USD 115 a month on AWS** (two small Fargate tasks at USD 46.87, RDS db.t4g.medium at USD 55.48, 50 GB storage at USD 7.00 and 50 GB of snapshots at USD 5.23). The Azure equivalent is about **USD 205 a month** (two B2s VMs at USD 72.86, PostgreSQL B2ms at USD 115.34, plus storage and backup). Both figures exclude load balancers, monitoring, egress and high availability (estimate). At 1,000 users that is USD 0.12–0.25 per user per month, and a few cents at 10,000 users.

A 300-word clinician summary costs about **USD 0.0014** on gemini-3.1-flash-lite ([Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing)). The confirmed in-UAE option, Azure OpenAI GPT-4o "regional" in UAE North at **USD 3.025 per million input tokens and USD 12.10 per million output tokens**, costs about **USD 0.014** per summary ([Azure Retail Prices API](https://prices.azure.com/api/retail/prices)). Both assume 3,000 input and 400 output tokens (estimate). At four summaries a month, language-model cost stays under USD 0.06 per user. The model choice therefore turns on residency, not price. The Gemini free tier is listed as used to improve Google's products, which rules it out for health data ([Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing)).

Azure Speech in UAE North charges **USD 1.00 per audio hour** for speech-to-text and **USD 15 per million characters** for neural text-to-speech ([Azure Retail Prices API](https://prices.azure.com/api/retail/prices)). Ten minutes of dictation plus 5,000 characters of spoken replies therefore costs about USD 0.24 a month (estimate).

Notifications dominate the variable cost. Twilio SMS to the UAE costs **USD 0.1176 per segment** ([Twilio SMS pricing](https://www.twilio.com/en-us/sms/pricing/ae)), so eight reminders a month cost about USD 0.94 (estimate). Since 1 July 2025, WhatsApp has charged per delivered message by category, and messages inside the user-initiated service window carry no Meta charge ([Meta WhatsApp pricing](https://developers.facebook.com/docs/whatsapp/pricing)). Twilio adds a USD 0.005 handling fee per message ([Twilio WhatsApp pricing](https://www.twilio.com/en-us/whatsapp/pricing)).

| Cost per active user per month (estimate) | WhatsApp-first | SMS-first |
|---|---|---|
| Hosting (1,000 users) | USD 0.12–0.25 | USD 0.12–0.25 |
| Language-model summaries (4 a month) | USD 0.01–0.06 | USD 0.01–0.06 |
| Voice (10 min speech-to-text, 5k characters text-to-speech) | USD 0.16–0.25 | USD 0.16–0.25 |
| Reminders (8 a month) | USD 0.04 + Meta UAE fee (not retrieved) | USD 0.94 |
| **Total** | **USD 0.35–0.60 (AED 1.3–2.2) + Meta fee** | **USD 1.25–1.50 (AED 4.6–5.5)** |

Against the illustrative AED 30 (USD 8.17) monthly price, **gross margin is about 82% (SMS-first) to 96% (WhatsApp-first)**: (8.17 − 1.50) ÷ 8.17 = 81.6%, and (8.17 − 0.35) ÷ 8.17 = 95.7% (estimate). The cost lines that will actually decide profitability are fixed and were not researched: ISO 27001 and ADHICS audits, penetration tests, a clinical safety officer, liability insurance and salaries. A useful rule of thumb follows from the contribution per user, which is about USD 80–91 a year: (8.17 − 1.50) × 12 = USD 80.0, and (8.17 − 0.60) × 12 = USD 90.8. **Every USD 1 million of annual fixed cost therefore needs roughly 11,000–12,500 paying users to break even** (estimate).

## Eight million Gulf adults aged 50+ today, sixteen million by 2050

Market size here is people first and dollars second. Vendor top-down figures for "digital cognitive assessment" could not be verified, and the one vendor figure that could be read is for a different category: Grand View Research puts global digital therapeutics at USD 9.5 billion in 2025, rising to USD 75.2 billion by 2033 ([Grand View Research](https://www.grandviewresearch.com/industry-analysis/digital-therapeutics-market)). That is low-confidence context only. The bottom-up figures below use World Bank population projections ([World Bank Population Estimates and Projections](https://databank.worldbank.org/source/population-estimates-and-projections)). The extraction cannot separate the 50–75 core band from people aged 75+, so "50+" is a slightly generous proxy.

| Population, millions (World Bank) | 50+ (2024) | 60+ (2024) | 50+ (2030) | 60+ (2030) | 50+ (2050) | 60+ (2050) |
|---|---|---|---|---|---|---|
| UAE | 1.327 | 0.412 | 1.415 | 0.522 | 2.072 | 0.577 |
| Saudi Arabia | 4.621 | 1.836 | 5.935 | 2.469 | 10.679 | 6.122 |
| GCC (six states) | 7.974 | 2.968 | 9.731 | 3.858 | 16.411 | 8.500 |
| Japan | 62.761 | 44.520 | 63.589 | 45.471 | 56.772 | 45.484 |
| South Korea | 22.833 | 14.188 | 25.087 | 16.997 | 27.257 | 20.689 |
| Singapore | 1.859 | 1.152 | 2.157 | 1.388 | 3.353 | 2.175 |
| China | 522.965 | 290.059 | 568.775 | 366.539 | 670.718 | 496.951 |
| India | 295.450 | 156.667 | 351.323 | 191.457 | 575.151 | 345.982 |

The UAE series carries a caveat. The projection shows the 65+ group falling between 2040 and 2050 while the 50+ group jumps, which reflects migration assumptions about expatriates leaving before old age. The 2050 UAE figures should therefore be read loosely.

**Abu Dhabi and Dubai cannot be sized from verified data.** Neither the Statistics Centre Abu Dhabi nor the Dubai Statistics Center age tables could be retrieved. The illustrative Abu Dhabi line below therefore rests on an **unverified assumption** that the emirate holds about a third of UAE residents. It must be replaced with SCAD data before use.

### TAM, SAM and SOM (all estimates; price = AED 360 ≈ USD 98.03 per person per year)

| Layer | Definition | People | Arithmetic | Annual value |
|---|---|---|---|---|
| TAM, UAE | Residents aged 50+, 2024 | 1.327 M | 1.327 M × USD 98.03 | **≈ USD 130 M** (AED 478 M) |
| TAM, GCC 2024 | Residents aged 50+ | 7.974 M | 7.974 M × 98.03 | **≈ USD 782 M** |
| TAM, GCC 2030 | Residents aged 50+ | 9.731 M | 9.731 M × 98.03 | ≈ USD 954 M |
| TAM, GCC 2050 | Residents aged 50+ | 16.411 M | 16.411 M × 98.03 | ≈ USD 1.61 B |
| TAM, high-income Asia | Japan + Korea + Singapore, 50+, 2024 | 87.453 M | 87.453 M × 98.03 | ≈ USD 8.57 B (price parity assumed) |
| Asia, people only | Seven markets incl. China, India, Malaysia, Indonesia, 50+, 2024 | ≈ 978 M | sum of table rows | Not priced: India's health spend is USD 84.7 per person ([World Bank](https://data.worldbank.org/indicator/SH.XPD.CHEX.PC.CD)) |
| SAM | UAE + Saudi residents aged 60+, the group health systems most plausibly enrol | 2.248 M (2024); 2.991 M (2030) | 0.412 + 1.836; 0.522 + 2.469 | ≈ USD 220 M (2024); ≈ USD 293 M (2030) |
| SOM, UAE year 5 | 1% / 2% / 5% of UAE 50+ | 13,270 / 26,540 / 66,350 | × AED 360 | **USD 1.30 M / 2.60 M / 6.50 M ARR** |
| SOM, Abu Dhabi illustrative | 2% of an *assumed* one-third of UAE 50+ | ≈ 8,850 | 1.327 M ÷ 3 × 2% × AED 360 | ≈ USD 0.87 M ARR |

The UAE TAM is about 0.5% of the country's roughly USD 26 billion annual health spend. That total is the researchers' estimate from World Bank per-person spending of **USD 2,401.5 in 2023** ([World Bank](https://data.worldbank.org/indicator/SH.XPD.CHEX.PC.CD)). The UAE alone is a niche. The GCC and Asia are where a scaled business lives.

A clinical lens narrows the pool. Global MCI prevalence among community-dwelling adults aged 50+ is **15.56%** ([Bai et al., Age Ageing 2022](https://pubmed.ncbi.nlm.nih.gov/35977150/)). Applied to the UAE's 1.327 million, that gives an upper bound of about **206,000 people** (estimate), and about **1.24 million** across the GCC. Age-specific rates of **6.7% at 60–64, 8.4% at 65–69 and 10.1% at 70–74** ([Petersen et al., Neurology 2018](https://pubmed.ncbi.nlm.nih.gov/29282327/)) give a lower, core-band figure. At about 8.4% of the UAE's 412,000 people aged 60+, that is roughly 35,000 (estimate). NeuroTwin's market is broader than people with MCI, because it monitors people whose trajectory is not yet known. But these are the people for whom a clinician most values a documented change.

## Gulf adults aged 50–75 carry high vascular risk and are mostly undiagnosed

The core user is a bilingual or Arabic-speaking adult aged 50–75 who is still independent, attends primary care, and very often lives with diabetes, hypertension or obesity. Gulf vascular risk is among the highest in the world. In the UAE, **31.6% of adults are obese** (2024), **41.4% of 30–79-year-olds have hypertension** (2019), and age-standardised diabetes is **26.1–33.5%** (2022). Japan's equivalent figures are 5.9%, 31.4% and 6.4–8.6% ([WHO GHO obesity](https://ghoapi.azureedge.net/api/NCD_BMI_30A); [hypertension](https://ghoapi.azureedge.net/api/NCD_HYP_PREVALENCE_A); [diabetes](https://ghoapi.azureedge.net/api/NCD_DIABETES_PREVALENCE_AGESTD)). In a Saudi records study, diabetes and hypertension were the leading comorbidities among dementia patients, and vascular dementia made up 23.6% of cases ([Beigh et al., Cureus 2024](https://pubmed.ncbi.nlm.nih.gov/38371043/)). This makes **diabetes and cardiology clinics a natural second channel** after primary care.

The undiagnosed pool is large, and monitoring finds it. Across 23 studies, **61.7% of dementia was undetected** ([Lang et al., BMJ Open 2017](https://pubmed.ncbi.nlm.nih.gov/28159845/)). In Saudi primary care, cognitive screening coverage rose from 8.3% in 2016 to 21.7% in 2023. Among those screened, **34.2% received a new MCI or dementia diagnosis, and 71.3% of them had no previously documented concern** ([Almohammadi et al., 2026](https://pubmed.ncbi.nlm.nih.gov/42696526/)). Awareness is low too: only **22.8%** of a UAE public sample showed moderate dementia knowledge ([Alhaj Ahmad et al., Sci Rep 2025](https://pubmed.ncbi.nlm.nih.gov/41381630/)). That argues for clinician-initiated enrolment, not consumer marketing.

NeuroTwin serves three user groups, and each needs its own value proposition. The **person** gets short activities and check-ins in their own language. The **clinician**, who is also the buyer's staff, gets a reviewed trend that flags meaningful within-person change. The **family member** gets a defined supporting role; informal carers already absorb about half of global dementia costs ([WHO](https://www.who.int/news-room/fact-sheets/detail/dementia)). One structural caution matters for sizing. The UAE's 65+ share is only 1.8%, because most expatriates leave before old age. The people who age in place are mostly nationals and long-term residents, and no verified age data for them by nationality was found.

## NeuroTwin competes on language, longitudinal design and the home

Nearly every Western digital cognitive tool is a **one-off, norm-referenced test of 5–15 minutes run in a clinic**. NeuroTwin is a home-based, bilingual, within-person monitor with family support and FHIR export. The verified competitors fit this pattern:

| Product | Model | Regulatory status (verified) | Arabic / MENA |
|---|---|---|---|
| Cognivue Clarity / Thrive | 10-minute / 5-minute self-administered test in a clinic or pharmacy | FDA De Novo DEN130033 (2015) | None found |
| BrainCheck | 15-minute, 5-domain battery plus care planning; correlates with MoCA at r = 0.77 | Listed under the exempt Class II code PTY | None found |
| Creyos | Task battery; 85,000+ normative participants | PTY listing | Norms by culture and language; Arabic not confirmed |
| CANTAB (Cambridge Cognition) | Trial-focused batteries | 510(k) K161328 (2017) | None found |
| Neurotrack | 3-minute screen plus care planning; also insurance underwriting | PTY listing | None found |
| Altoida | AR/tablet test that claims to track change | "Investigational use only… not available for commercial sale" | None found |
| CognICA (Cognetivity) | 5-minute AI visual test at home or in clinic; 93% sensitivity in the ADePT study | Not confirmed in openFDA | None found |

Sources: [openFDA PKQ 510(k)](https://api.fda.gov/device/510k.json?search=product_code:PKQ&limit=60); [openFDA PTY listings](https://api.fda.gov/device/registrationlisting.json?search=products.product_code:PTY&limit=100); [Cognivue](https://www.cognivue.com/); [BrainCheck](https://braincheck.com/); [Creyos](https://creyos.com/); [Cambridge Cognition](https://cambridgecognition.com/); [Neurotrack](https://neurotrack.com/); [Altoida](https://altoida.com/); [ADePT, PMID 37781102](https://pubmed.ncbi.nlm.nih.gov/37781102/).

Four differences hold up against the evidence. **First, the within-person design addresses a documented scientific gap rather than a translation gap.** A 2025 systematic review found 20 Arabic cognitive tools across 29 validation studies. Only three had been validated in more than one setting, and the authors flagged missing evidence on "the detection of cognitive changes" ([Kabalan et al., Alzheimers Dement 2025](https://pubmed.ncbi.nlm.nih.gov/40420359/)). Competitors answer norm bias with ever-larger norm sets, as Creyos markets norms by "education, cultural background, and language" ([Creyos](https://creyos.com/)). A within-person baseline sidesteps much of the education and dialect bias. A 2026 *Cortex* review names a "diglossic validity problem" between Modern Standard Arabic and the dialects ([PMID 42641352](https://pubmed.ncbi.nlm.nih.gov/42641352/)). **Second, home use and usability are named gaps in the field.** A JMIR review found a lack of evaluations across diverse education levels, cultures and degrees of technology acceptance, and called for attention to emotional and usability aspects ([Cubillos & Rienzo, JMIR Ment Health 2023](https://pubmed.ncbi.nlm.nih.gov/38064247/)). Home testing in older adults is feasible: ADePT ran its test at home or in clinic with people aged 55–90 ([PMID 37781102](https://pubmed.ncbi.nlm.nih.gov/37781102/)). **Third, no verified competitor documents a family role or capture of the day's conditions** (sleep, vision, hearing, setting). **Fourth, FHIR R4 export matches the region's direction.** Malaffi has reached about 90% LOINC adoption and large-scale SNOMED CT ([Malaffi milestones](https://www.malaffi.ae/what-is-malaffi/history-and-milestones/)), and India's ABDM publishes an official FHIR implementation guide ([ABDM](https://en.wikipedia.org/wiki/Ayushman_Bharat_Digital_Mission)).

The honest counter-argument is that differentiation is not a moat. NeuroTwin needs its own Arabic test-retest reliability data before its reliable-change thresholds are credible. Asian vendors (Neurowyzr in Singapore, HippoScreen in Taiwan, and Chinese firms including one with voice-based assessment) already use the US exempt route ([openFDA PTY](https://api.fda.gov/device/registrationlisting.json?search=products.product_code:PTY&limit=100)). The clinic tools are also complements: a NeuroTwin trend could trigger a one-off clinic battery.

## The claims decide the regulatory route in Dubai, the Gulf and Asia

The most important regulatory fact is American, but it applies everywhere. The FDA's "Computerized Cognitive Assessment Aid" class covers tools that give clinicians measurements of cognitive function in adults 55 and older, including for "**monitoring changes in cognitive function over time**" ([openFDA PKQ classification](https://api.fda.gov/device/classification.json?search=product_code:PKQ)). NeuroTwin's function sits squarely inside that description. Being "not a diagnostic" lowers the risk class, but it does not by itself take software out of device regulation. Most competitors' "FDA" status is a registration under the 510(k)-exempt Class II code PTY, not a clearance, which shows the US bar is reachable if NeuroTwin chooses a device claim later.

The **UAE** now has a single federal medical-products regulator, the Emirates Drug Establishment (EDE), established in September 2023 and covering medical devices ([EDE](https://www.ede.gov.ae/en)). Its legislation page lists the medical-products decree-law published on 1 October 2024 but **no software-as-a-medical-device guideline** ([EDE legislations](https://www.ede.gov.ae/en/legislations)). A formal classification opinion from EDE is therefore the prudent first step. Locally, Abu Dhabi providers must adopt ADHICS, the DoH cyber-security standard tied to the health information exchange ([Malaffi policies](https://www.malaffi.ae/what-is-malaffi/policies/)). NeuroTwin will be assessed against ADHICS as each provider's third-party processor. Hub71 offers an Abu Dhabi base with a life-sciences vertical and a link to an ADGM tech licence ([Hub71](https://www.hub71.com/)).

**Dubai** is a separate jurisdiction. Health insurance there has been compulsory and employer-paid since a phase-in completed on 30 June 2016 ([Wikipedia: DHA](https://en.wikipedia.org/wiki/Dubai_Health_Authority)), which makes insurers and employers potential programme buyers. Inside Dubai Healthcare City, a separate free-zone regulator licenses providers ([Wikipedia: DHCC](https://en.wikipedia.org/wiki/Dubai_Healthcare_City)), so the location of the legal entity decides which regulator applies. Integration between Riayati, Malaffi and Dubai's NABIDH was announced in January 2023 ([Malaffi milestones](https://www.malaffi.ae/what-is-malaffi/history-and-milestones/)). In principle, a record exported in Abu Dhabi can therefore follow the patient. In **Saudi Arabia**, the SFDA has been the device regulator since 2003 and publishes a filterable medical-device guidance library ([SFDA guidelines](https://www.sfda.gov.sa/en/guide)). Its specific software rules were not retrieved. Qatar, Kuwait, Oman and Bahrain were not verified at all.

In **Asia**, Singapore is the best-documented entry point. HSA has a life-cycle software device guideline (revised December 2025) and a SaMD risk-classification guideline (July 2025). It has run an immediate registration pathway for standalone software since 2018 that relies on reference-regulator approvals, and digital health makes up over 40% of its pre-submission consultations ([HSA guidance](https://www.hsa.gov.sg/medical-devices/guidance-documents/); [HSA digital health](https://www.hsa.gov.sg/medical-devices/digital-health/)). Its Healthier SG programme enrols residents with a GP clinic under a personal health plan ([Healthier SG](https://www.healthiersg.gov.sg/)), which is the same provider-led channel NeuroTwin needs. India's ABDM is FHIR-based but low-priced. Japan and Korea, the two largest high-income Asian markets, could not be verified.

The recommended sequence is: launch in Abu Dhabi with tightly disciplined, non-diagnostic, clinician-review claims; ask EDE for a classification opinion in parallel; add Dubai through a DHA-licensed partner; then decide whether a device claim (FDA exempt listing or CE) is worth the cost, mainly because it unlocks Singapore's reliance route and the Saudi market. Lumosity shows what happens when claims outrun evidence. Its 2016 FTC settlement (a USD 50 million judgment, suspended to USD 2 million) barred it from claiming to protect against age-related decline or dementia without evidence ([Wikipedia: Lumosity](https://en.wikipedia.org/wiki/Lumosity)). NeuroTwin should never claim prevention, "brain age" or detection of dementia.

## Gulf dementia cases rise elevenfold by 2050, and the care pathway needs a triage step

The demand curve is set by ageing, not by rising age-specific rates. GBD forecasts take **GCC dementia cases from about 137,000 in 2019 to about 1.52 million in 2050** (sum of six countries), while age-standardised prevalence barely moves (UAE +0.7%) ([Nichols et al., Lancet Public Health 2022](https://pmc.ncbi.nlm.nih.gov/articles/PMC8810394/)).

| Dementia cases (GBD) | 2019 | 2050 | Change |
|---|---|---|---|
| UAE | 11,711 | 221,672 | +1,795% |
| Saudi Arabia | 85,735 | 855,760 | +898% |
| Qatar | 4,201 | 85,046 | +1,926% |
| GCC total | 136,739 | 1,519,052 | ≈ +1,011% |
| China | 15.3 M | 45.5 M | +197% |
| Japan | 4.1 M | 5.2 M | +27% |
| Global | 57.4 M | 152.8 M | +166% |

For 2035, the midpoint of the World Bank series gives about **11.4 million GCC residents aged 50+ and 4.8 million aged 60+**, by linear interpolation of the 2030 and 2040 figures (estimate). At the illustrative price, the GCC TAM in 2035 is therefore roughly USD 1.1 billion. Global dementia costs are projected to rise from USD 1.3 trillion to **USD 2.8 trillion by 2030** ([ADI](https://www.alzint.org/about/dementia-facts-figures/dementia-statistics/)). Dividing USD 1.3 trillion by 57.4 million cases implies about USD 22,600 per person per year (estimate). Against that figure, a USD 98 annual monitoring fee is a rounding error, if it produces earlier, better-managed care.

Three shifts will reshape the market between 2035 and 2050. **First, diagnosis is moving to blood tests that need a gatekeeper.** On 16 May 2025 the FDA cleared the first blood test to aid Alzheimer's diagnosis, for symptomatic adults 55+. It explicitly states the test is "not intended as a screening or stand-alone diagnostic test" ([FDA](https://www.fda.gov/news-events/press-announcements/fda-clears-first-blood-test-used-diagnosing-alzheimers-disease)). Something cheap has to decide who is symptomatic enough to be tested, and documented within-person change is exactly that signal. **Second, treatment is arriving faster than specialist capacity.** Lecanemab was approved in the US in 2023, with subcutaneous maintenance dosing approved in August 2025 ([Wikipedia: Lecanemab](https://en.wikipedia.org/wiki/Lecanemab)), and donanemab followed in 2024 ([Wikipedia: Donanemab](https://en.wikipedia.org/wiki/Donanemab)). RAND modelled an **18.6-month average wait** in the US, with specialist evaluation as the binding constraint ([RAND RR-2272](https://www.rand.org/pubs/research_reports/RR2272.html)). The Gulf, building capacity from a low base, will face the same squeeze. **Third, payment is shifting to monthly, per-patient care management.** GUIDE runs to 2032, and Abu Dhabi completed 12 disease registries for "proactive, prevention-first care" in July 2026 ([Malaffi milestones](https://www.malaffi.ae/what-is-malaffi/history-and-milestones/)).

By 2050, Bahrain (8.5%) and Saudi Arabia (8.2%) will have more than four times the UAE's current 65+ share of 1.8%. Monitoring will then be a standing service line rather than a pilot. The risk side of this outlook is that if blood biomarkers become cheap enough to screen everyone, cognitive triage tools lose their gatekeeping role. NeuroTwin's defence is that a trajectory of function, which reflects daily life, carries information a single molecular snapshot does not.

## A detailed business model: land with providers, expand through programmes

| Element | Design (recommendations and estimates) |
|---|---|
| **Customer (pays)** | DoH-licensed Abu Dhabi provider groups first (primary care, longevity, diabetes and cardiology clinics); later Dubai providers, insurers and employers, government prevention programmes, and research sponsors. |
| **Users (use)** | Adults aged 50–75 (person); reviewing clinicians; invited family supporters. |
| **Value proposition** | For providers: a documented, reviewable within-person trend in Arabic and English, delivered into their EMR as FHIR R4, which flags who needs a full assessment. For families: a defined way to help. For the person: a short, respectful routine in their own language. |
| **Channels** | Direct enterprise sales to provider groups; clinician-initiated enrolment; EMR integration via FHIR; Hub71 ecosystem. Consumer marketing is secondary, given low dementia literacy. |
| **Revenue streams** | (1) Per-enrolled-patient monthly licence (illustrative AED 30). (2) Programme contracts at volume rates. (3) Optional family add-on. (4) Consented research and data licensing. (5) One-off implementation and integration fees (estimate, typical for enterprise health software). |
| **Cost structure** | Variable: USD 0.35–1.50 per user per month (cited inputs, estimated totals). Fixed: team, compliance audits (ADHICS, ISO 27001), clinical safety, insurance and UAE-resident hosting; not quantified. |
| **Key partners** | Provider EMR vendors connected to Malaffi; UAE-region cloud (Azure UAE North or AWS me-central-1); in-region language and speech services; academic partners for Arabic reliability studies. |
| **Key resources** | Arabic test-retest reliability data; a claim-disciplined clinical safety case; integration templates. |
| **Unit economics** | Gross margin ≈ 82–96%; contribution ≈ USD 80–91 per user per year; break-even ≈ 11,000–12,500 users per USD 1 M of fixed cost (all estimates). |

The phasing follows the regulatory and payer evidence. **Phase 1 (years 0–2)** is one or two paid Abu Dhabi pilots of a few hundred to a few thousand enrolled patients. They should measure adherence, clinician review time, the rate of flagged change and conversion to formal assessment. Those are the numbers a Daman or DoH conversation needs. **Phase 2 (years 2–4)** adds Dubai providers and the first programme contract, aiming at the 1–2% UAE SOM (13,000–27,000 users, USD 1.3–2.6 million ARR, estimate). That is roughly the scale needed to cover USD 1–2 million of fixed cost. **Phase 3 (years 4–7)** enters Saudi Arabia, the GCC's largest and fastest-ageing market (1.8 to 6.1 million people aged 60+ by 2050), and Singapore. A device-claim decision would be made before this phase. **Phase 4 (2030s onward)** licenses the Arabic engine and the longitudinal method to partners in larger Asian markets, where NeuroTwin is unlikely to win alone on price.

The case is weakest on four points that a buyer or investor will probe. No UAE payer is confirmed. No UAE salary or compliance cost is known, so break-even is a formula, not a date. NeuroTwin has no Arabic reliability data yet. And the 50–75 core band has not been separated from older age groups in the population data. Each is fixable with targeted work, set out below.

## To confirm (unverified; do not present as fact)

| Item | What the notes say (unverified) | Where to check |
|---|---|---|
| UAE payer reimbursement | Whether Daman or Thiqa reimburse digital cognitive testing or remote monitoring; whether any DoH tariff exists for software-only monitoring | doh.gov.ae; damanhealth.ae |
| DoH telemedicine standard and price list | DoH regulates telemedicine through a standard (versions from about 2020) and a CPT-based mandatory price list | doh.gov.ae standards |
| UAE health data residency | Federal Law No. 2 of 2019, Article 13: in-country storage unless exempted (Ministerial Resolution 51/2021); 25-year record retention | uaelegislation.gov.ae; law-firm notes |
| UAE PDPL | Federal Decree-Law No. 45 of 2021 treats health data as sensitive; status of its executive regulations | uaelegislation.gov.ae |
| EDE decree number and device rules | Whether the October 2024 decree-law is No. 38 of 2024; device classes, reliance on CE or FDA approval, fees and timelines | ede.gov.ae |
| Wellness versus device boundary in the UAE and Gulf | Whether a "change tracking, no disease claim" product falls outside device regulation | EDE classification opinion; SFDA |
| DoH AI policy, Healthy Longevity Medicine framework, research sandbox, ADIO incentives | Reported to exist from about 2018–2024 | doh.gov.ae; adio.gov.ae |
| Malaffi FHIR APIs | Whether Malaffi exposes FHIR to third parties (historically HL7 v2) | malaffi.ae; ADHDS |
| Abu Dhabi provider landscape | Ownership links among PureHealth, SEHA, Daman, M42 and Cleveland Clinic Abu Dhabi | Company filings; The National |
| NABIDH, ISAHD, DHA telehealth and AI policy, Dubai Health, DHCR rename, Dubai Future Foundation | NABIDH connection mandate and FHIR; DHA telehealth licence; DHA AI policy (2021) | dha.gov.ae; nabidh.ae |
| Dubai licensing | A pure software vendor may need only a trade or IT licence | DHA or law-firm guidance |
| Saudi SFDA software guidance | Guidance codes MDS-G010 and MDS-G23; MDMA through GHAD; Authorised Representative; timelines | sfda.gov.sa |
| Saudi infrastructure | Health Holding clusters, Seha Virtual Hospital, NPHIES (FHIR R4), Lean | Official Saudi sites |
| Qatar, Kuwait, Oman, Bahrain | Qatar National Dementia Plan 2018–2022; Bahrain NHRA software guidance and sandbox; GCC joint registration route | moph.gov.qa; nhra.bh; WHO GDO |
| Japan and Korea | Japan's Basic Act on Dementia (in force 1 January 2024) and PMDA software route; Korea's dementia relief centres and MFDS digital medical products act | mhlw.go.jp; nid.or.kr |
| Anti-amyloid approvals in the UAE or Saudi Arabia | Lecanemab and donanemab Gulf approvals | EDE; SFDA |
| Lancet Commission 2024 | 14 modifiable risk factors (vision loss newly added); about 45% of dementia potentially preventable or delayable | The Lancet, Livingston et al. 2024 |
| WHO dementia action plan extension | Reportedly extended to 2031 at WHA78 | who.int |
| Second Alzheimer's blood test | A Roche Elecsys pTau test cleared around October 2025 | fda.gov |
| Hevolution Foundation funding; UAE retirement and Golden Visa ageing statistics | Reported figures not checked | Official sites |
| Emirate split and nationality | Abu Dhabi and Dubai each about a third of UAE residents; Emiratis about 10–12% of residents | SCAD; Dubai Statistics Center |
| Smartphone use among Gulf adults aged 50+ | Not found by age band | TDRA ICT surveys; GSMA |
| US monthly codes | RPM and RTM rates (about USD 43–52 a month for core codes); RPM needs physiologic data; GUIDE pays about USD 150–360 per patient per month | CY2025/2026 PFS final rules; CMS GUIDE methodology |
| Industry pricing norms | About USD 1–5 PMPM for population access; USD 10–100 per engaged user per month; USD 50–300 per clinician seat per month | Rock Health; Peterson Health Technology Institute |
| Competitor finances and prices | Revenue and funding for Cogstate, Cambridge Cognition, Linus Health, Neurotrack, Altoida and Cognetivity; Creyos self-serve plans; MoCA training fees | Annual reports; Crunchbase; vendor pricing pages |
| CognICA regulatory status | Marketed as "FDA cleared"; not found in openFDA | FDA 510(k) and registration databases |
| Competitor languages and CE marks | Arabic support and CE status for Cogstate, CANTAB, Creyos, BrainCheck, Linus and Cognivue | Vendor sites; EUDAMED |
| Digital-health failures | Mindstrong's 2023 shutdown; Akili and Pear Therapeutics analogues | Primary press sources |
| WhatsApp UAE rates | Meta's utility and authentication rates for the UAE | Meta rate-card CSV |
| Arabic speech support | Gulf dialect locales (ar-AE, ar-SA) and Arabic neural voices on Azure and Google | Provider language-support pages |
| Arabic SMS segment length | About 70 characters per segment (UCS-2), so about USD 0.235 per Arabic reminder | Twilio documentation |
| In-region model hosting | Vertex AI Gemini in Doha or Dammam; Bedrock in me-central-1; Core42/Jais and Falcon pricing | Provider pages |
| Fixed costs | ISO 27001, SOC 2, ADHICS audit, penetration tests, clinical safety officer, liability insurance, UAE salaries, free-zone and Hub71 licence fees and incentives | Quotes; Hays and Cooper Fitch salary guides; hub71.com |
| SaaS benchmarks | Gross margin, CAC, payback, churn and sales-cycle norms for digital health | KeyBanc/Sapphire; Rock Health |

## Conclusion

NeuroTwin's advantage is timing more than technology. The Gulf is building its dementia-care infrastructure about two decades before its case load arrives. Diagnosis worldwide is shifting toward blood tests that explicitly need symptomatic patients. And no verified competitor offers an Arabic-first, home-based, within-person record that drops into a provider's FHIR-ready EMR. Running cost is almost irrelevant at a margin above 80%. What will decide the business is whether one Abu Dhabi provider will pay to find out who among its 50–75-year-olds is changing, and whether NeuroTwin can show that the change it flags is real (Arabic reliability data) and actionable (conversion to assessment).

The regulatory finding cuts against a common assumption. Because the FDA's own device category names "monitoring changes in cognitive function over time", "not a diagnostic" is a positioning choice, not an exemption. Claim discipline is therefore both the cheapest regulatory strategy and a commercial asset. A device claim should be pursued later, only when it is worth paying for to unlock Saudi Arabia and Singapore. The next three pieces of work are a paid Abu Dhabi pilot, an EDE classification opinion, and an Arabic test-retest study. Together they turn this case from a plausible estimate into an investable one.
