# Breast ROI Copilot

A Streamlit decision-support application migrated from `breast_with_baseline_delta.R`. The deterministic ROI mathematics lives in `src/models/breast_roi.py`. A separate Evidence Search page retrieves real PubMed records through NCBI E-utilities; it does not use an LLM or RAG.

## Run

```bash
cd breast_roi_copilot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Run tests with `pytest -q`.

## Evidence Search

Open **Evidence search** in the top navigation. Enter medical keywords and select **Search PubMed** to retrieve up to five live records. The page displays article metadata, PMID, abstract, and a direct PubMed link. If internet access is unavailable, select the explicitly labeled offline demo mode. No API key is required for this small-volume prototype; the client makes two requests per search and caches results for one hour.

## Evidence Analyst

Open **Evidence analyst** to run the no-key verified demo or analyze the current live PubMed results with an optional OpenAI API key. Every displayed live answer must pass deterministic validation: cited PMIDs must match the current result set and each evidence excerpt must occur in a cited abstract. The LLM never performs or modifies ROI calculations.

To enable live AI mode, copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`, replace the placeholder key, and restart Streamlit. The real secrets file is ignored by Git. Demo mode requires no key and no LLM request.

## Effect-size extraction and Care Gap Value Library

The **Evidence extraction** page converts one PubMed abstract into a structured AI candidate covering study design, population, intervention, comparator, outcome, effect measure, confidence interval, ROI parameter mapping, and limitations. PMID, title, excerpt, and reported numbers are validated locally. A human reviewer must add a note and explicitly approve or reject the candidate.

Reviews are saved to `data/care_gap_value_library.csv` and appended to `data/care_gap_audit.jsonl`. The **Care Gap library** page displays governance status and evidence details. Approval never changes the deterministic ROI model; a future Parameter Copilot must require a separate user acceptance step.

## Parameter Copilot

The **Parameter Copilot** reads only Approved Library records. Its deterministic evidence gate distinguishes directly usable evidence, conversion-required effects, relevant-but-insufficient evidence, and parameters with no approved evidence. Users must Keep, Accept, Edit, or Reset each value with a required decision note. Confirmed values and an append-only audit trail are stored separately in `data/parameter_decisions.csv` and `data/parameter_decision_audit.jsonl`.

The ROI page applies only human-confirmed final values and labels how many Copilot decisions are active. Evidence approval never equals parameter acceptance, and the LLM still performs no ROI mathematics.

## Executive Report Generator

The **Executive report** page reads the exact current-session ROI snapshot and human-approved Care Gap Library records. Live AI returns a structured draft; verified demo mode makes no API call. Before display and again before approval, deterministic validators require an exact ROI snapshot, approved PMIDs, and excerpts found in the approved records. The report remains a Draft until a reviewer supplies an approval note. Approved reports and append-only lifecycle events are saved under `data/` and can be downloaded as JSON.

## Synthetic model evaluation and risk prioritization

**Model performance** creates a reproducible, fully synthetic cohort and evaluates a care-gap detection score with sensitivity, specificity, precision, accuracy, F1, a confusion matrix, and threshold trade-offs. The demo ground-truth rule defines a screening gap as at least two years since the last screen. All patient IDs begin with `SYN-`; no PHI or HDR records are used.

**Risk prioritization** compares the expected impact of random outreach with a transparent priority score when outreach capacity is limited. Its financial simulation reuses the active deterministic ROI inputs for annualized screening cost, expected follow-up cost, and stage-shift savings per detected case. Random outreach is averaged over repeated Monte Carlo trials. These are synthetic scenario estimates, not observed program results.

## Data intake and quality gate

The **Data intake** page accepts the standard patient-level CSV schema or the bundled 10,000-row synthetic test file. Deterministic checks cover required columns, parseability, missing values, duplicate identifiers, age and probability ranges, synthetic-data marking, and sample size. A reviewer note is mandatory before a passing dataset becomes available to Model performance and Risk prioritization. Uploads remain in the current Streamlit session; unmarked datasets have patient IDs replaced by local one-way hashes before downstream use. This MVP does not persist uploaded patient-level data or connect to an EHR/HDR.

## Formula map

- Additional screened = population × max(target rate − current rate, 0)
- Detected cases = additional screened × detection rate / 1,000 × age adjustment factor
- Age adjustment factor = selected age-band incidence / 239.8
- Lives saved = additional screened × lives saved per 1,000 / 1,000
- Stage-shift savings/case = regional share × regional shift × (regional cost − localized cost) + distant share × distant shift × (distant cost − regional cost)
- Treatment cost avoided = detected cases × stage-shift savings/case
- Screening cost = additional screened × mammography cost / screening interval
- Follow-up cost = additional screened × recall rate × completion rate × follow-up cost
- Net savings = treatment cost avoided − screening cost − follow-up cost
- ROI = net savings / (screening cost + follow-up cost)

## Important interpretation notes

- The original model calls `lives_saved_per_1000` a workbook evidence input but does not encode a time horizon or causal derivation.
- Breast incidence is used only as a relative age adjustment to the detection rate; the model does not calculate cases directly from incidence per 100,000.
- With “unknown excluded,” known-stage percentages are divided by 100 but not renormalized. This preserves the R behavior exactly.
- The baseline shown by the original Shiny app is the first reactive state captured at session start. This Streamlit version uses the documented R defaults as a stable comparison baseline.
- Negative incremental screening is retained as a reported percentage-point change, but downstream incremental volumes are clamped to zero, matching R.
