# Construction cost and schedule risk tool (CE725, Topic 5)

Monte Carlo risk analysis for construction cost and schedule contingency. Instead of a flat
contingency percentage, the tool simulates the project thousands of times and reports P50, P80
and P90 duration and cost, shows which activities and risks drive delay, and (once the finance
layer is built) shows the effect on NPV and IRR.

**Status:** engine, finance layer, contingency, mitigation, Gantt and model ladder all working
and tested (26 tests). See `docs/NEW_FEATURES_GUIDE.md` and `docs/VALIDATION_GUIDE.md`.

## What it does now

- Reads an activity network with three-point (optimistic, most likely, pessimistic) durations and costs
- Samples PERT-Beta or triangular distributions
- Correlates activities in the same group (Gaussian copula)
- Adds discrete risk events from a risk register
- Runs the critical path method for every iteration (vectorised, about 1 second for 10,000 runs)
- Reports P50, P80, P90, criticality index, rank-correlation tornado and cruciality
- Monthly cash flow, interest during construction, NPV and IRR (project and equity) for every run
- P80 contingency versus a flat 10%, and its effect on NPV
- Mitigation calculator: is reducing a risk worth its cost?
- Cost of delay: what X days of delay in any activity costs, split into extra cost, interest,
  buyer compensation (optional, RERA-style) and later sales cash
- Gantt chart with possible slip, and the model ladder chart
- `scripts/run_case_study.py` saves every headline number to `results/`

## Run it

```bash
pip install -r requirements.txt
pytest -q                          # 26 tests should pass
streamlit run app/streamlit_app.py
python scripts/run_case_study.py   # headline results into results/
python scripts/export_validation_values.py   # tool values for the Excel validation workbook
```

## Folder layout

| Folder | Contents | Owner |
|---|---|---|
| `engine/` | Sampling, correlation, CPM, risks, simulation | Developer |
| `finance/` | Cash flow, debt, IDC, NPV, IRR | Finance Modeller |
| `app/` | Streamlit interface | Docs Lead + Developer |
| `data/` | Case study, benchmark network, risk register, correlation groups, finance inputs | Data Lead |
| `scripts/` | Rerun the case study and save results | Team |
| `results/` | Saved results from the latest run | Team |
| `tests/` | Automated tests (run on every push via GitHub Actions) | Validation Engineer |
| `validation/` | Excel benchmark workbooks and validation outputs | Validation Engineer |
| `docs/` | Sources, method note, manuals, reports | Docs Lead |

## Data files

- `data/case_study_activities.csv`: 28-activity G+10 residential building (about 11,000 m²).
  Columns `source_status` and `verify_against` show where each value must be checked.
- `data/benchmark_6_activity.csv`: small network with two near-equal parallel paths, used for
  the manual benchmark and to demonstrate merge bias.
- `data/risk_register.csv`: 12 starter risks.
- `data/correlation_groups.csv`: one correlation value per activity group.
- `data/finance_inputs.json`: placeholders for the finance layer.

Units: days for durations, ₹ lakh for costs. `daily_cost_lakh` is the time-dependent cost of an
activity (equipment hire, crew standing time), so a longer activity costs more.

## Known limitations (starter version)

- Finish-to-start links only, no lags, no calendar (monsoon months are not modelled by date yet)
- A risk that lists several activities adds its delay to each of them
- The positive semi-definite fix is a simple eigenvalue clip, not Higham's method
- Cost and duration of the same activity are sampled independently

## AI use

Starter code, the activity list, the risk register and the reference list were generated with
Claude (Anthropic) on 14 Oct 2026 and are logged in the AI usage log. The team must review,
test and verify all of it; see `docs/SOURCES.md` for the citation warning.

## Privacy note

The public Streamlit app processes uploaded data on Streamlit's servers. For confidential project
data, run the app locally. Any AI feature must state what text is sent to the AI provider.
