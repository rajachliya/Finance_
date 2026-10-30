# New features: finance, contingency, mitigation, Gantt, model ladder

## 1. Merge into your repo

Your repo has changed since the starter, so copy files rather than overwrite everything.

| File | What to do |
|---|---|
| `finance/cashflow.py` | New: replace the stub |
| `engine/analysis.py` | New: add |
| `engine/risks.py` | Changed: risk sampling now uses the same random numbers in every scenario, so before/after comparisons are fair. Copy over if you have not edited it; otherwise merge the `_tri_from_u` function and the loop in `sample_risks` |
| `app/charts.py` | New: add |
| `app/streamlit_app.py` | Rewritten with new tabs. If your team changed the app, copy the tab sections you need |
| `scripts/run_case_study.py` | New: add |
| `tests/test_finance_and_analysis.py` | New: add |
| `data/finance_inputs.json` | Keep your verified values; make sure every key in this file exists in yours |
| Your verified `case_study_activities.csv` and `correlation_groups.csv` | Keep yours. Do not overwrite them with the files in this zip |

Then run `pytest -q` (26 tests should pass) and `streamlit run app/streamlit_app.py`.

## 2. Build the Excel finance benchmark first

The Finance Modeller builds this from the rules below, **without looking at the Python code**, so the
comparison is a genuine independent check. Then compare with `results/plan_monthly_cashflow.csv`.

**Sheet "Inputs":** every value from `finance_inputs.json`, plus
- monthly loan rate `=(1+annual)^(1/12)-1`, and the same for the discount rates
- revenue (₹ lakh) `=area * price / 100000`

**Sheet "Schedule":** one row per activity with ES (early start, from your hand CPM using most-likely
durations), duration, finish = ES + duration, and cost = `cost_m_lakh + daily_cost_lakh * duration`.
Then one column per month k = 1, 2, ... with:

    =MAX(0, MIN(Finish, k*30) - MAX(ES, (k-1)*30)) / Duration * Cost

Total each month column: that is construction spend for month k.

**Sheet "CashFlow":** one column per month, k = 0 to completion + months to sell. Completion month =
`CEILING(project duration / 30, 1)`.

| Row | Formula (month k) |
|---|---|
| Upfront | land + approvals in month 0, else 0 |
| Spend | from Schedule |
| Overheads | `overhead * MAX(0, MIN(30, duration - (k-1)*30)) / 30` for k ≥ 1 |
| Progress share | spend_k / total spend |
| Presale collections | `presale_share * revenue * progress share` |
| Later collections | `(1 - presale_share) * revenue / months_to_sell` if completion < k ≤ completion + months_to_sell |
| Brokerage | `brokerage_pct * (presale + later collections)` |
| Project cash flow | collections − brokerage − spend − overheads − upfront |
| Debt opening | previous month's closing (0 in month 0) |
| Interest | opening × monthly loan rate |
| Funding need | `MAX(0, -project CF)` |
| Draw | 0 in month 0 (land is equity), else need × debt share |
| Surplus | `MAX(0, project CF)` |
| Repay | `MIN(opening + interest + draw, surplus)` |
| Closing | opening + interest + draw − repay |
| Equity cash flow | −(need − draw) + (surplus − repay); in the last month also subtract any closing balance |

**Results:**
- Project NPV `=CF_0 + NPV(monthly discount rate, CF_1:CF_T)`; equity NPV the same with the cost of equity
- Project IRR (annual) `=(1+IRR(CF_0:CF_T))^12-1`; equity IRR the same on equity cash flows
- IDC = sum of interest for months up to and including completion
- Flat 10% case: multiply every activity cost and the overhead by 1.10 and recompute NPV

Record in the Validation tab: T15 NPV (tolerance ₹0.01 lakh), T16 IRR (0.0001), and add T18 IDC,
T19 peak debt, T20 NPV with flat 10%. Any difference: find the month where the two first disagree.

## 3. Rerun the case study

    python scripts/run_case_study.py

This saves to `results/`:

| File | Use it for |
|---|---|
| `headline_results.md` | Every headline number plus a one-line result for slides, website and resume |
| `summary.json` | All numbers in one place |
| `model_ladder.csv` | Ladder chart in the report |
| `risk_contributions.csv` | Which risks matter most |
| `activity_drivers.csv` | Criticality and tornado table |
| `correlation_sensitivity.csv` | Validation report: how much correlation changes P80 |
| `convergence.csv` | Validation report: test T10 |
| `plan_monthly_cashflow.csv` | Line-by-line comparison with the Excel benchmark |
| `finance_distribution.csv` | NPV, IRR, IDC percentiles |

Commit the `results/` folder each time, so the report, slides and website quote the same run.
Rerun after every data change, and check `headline_results.md` against the app's numbers.

## 4. How to read the new outputs

**Contingency vs flat 10%.** "Contingency needed at P80" is P80 cost ÷ base estimate − 1. If it is
above 10%, a flat 10% is too little; if below, a flat 10% is more than needed at 80% confidence.
Either is a valid finding. "Chance a flat 10% is not enough" is the share of runs costing more than
base × 1.10.

**NPV effect.** Compare four numbers: plan NPV (no contingency), plan + flat 10% NPV, simulated median
NPV, and NPV with 80% confidence (80% of runs do at least this well). Delay hurts NPV twice: costs
rise (overheads, daily costs, interest) and sales cash arrives later.

**Mitigation.** Pick a risk, set its probability and impact after the fix, and its cost. The tool runs
the project with and without the fix using the same random numbers, so the difference comes only from
the fix. "Worth paying up to" is the expected NPV gain before the fix's cost.

**Cost of delay.** In the Finance tab, pick an activity and a delay. The tool reruns the plan with
that delay and splits the NPV loss into extra construction and overhead cost, extra interest,
compensation to buyers (if switched on) and later sales cash. A delay on an activity with float
does not move the finish until the float is used up.

**Gantt.** Coloured bars are the plan; colour shows how often the activity was critical. Grey bars
show how much later each activity finishes in 80% of runs (switchable to 50% or 90%).

**Model ladder.** Shows how each layer of realism changes the answer: plan → PERT → simulation →
correlation → risks. This is a good headline chart for the presentation.

## 5. Assumptions to add to the Assumptions tab

Land and approvals paid at month 0 by equity (check RBI rules on lending for land); costs spread evenly
over each activity; risk costs spread with construction spend; presales collected in step with
construction progress; remaining units sold evenly after completion; interest capitalised; cash sweep
repays debt first; mitigation cost paid at month 0; no taxes or GST; no sale price escalation.

## 6. AI log entries to add

This code was generated with Claude on 23 Oct 2026. Log at least: the finance layer, the analysis
functions (contingency, ladder, mitigation), the charts and app update, and the change to risk
sampling. Mark them "Pending" until your Excel benchmark and code review are done.
