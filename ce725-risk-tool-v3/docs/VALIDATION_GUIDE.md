# Manual validation guide (CE725 Topic 5)

Validation is 20% of the grade, and the brief says a tool that has not been validated "will earn
limited credit, regardless of how polished it looks". This guide takes you through every check, in
order, using `validation/Validation_Benchmark.xlsx`.

## 0. Read this first: what makes it "manual"

The Excel workbook calculates everything with plain Excel formulas, so it is an independent
calculation from the Python tool. But both were written with AI help, and if the AI misunderstood a
rule, it could make the same mistake in both. Three things protect you against that, and they are
what make this your validation rather than the AI's:

1. **Hand calculations.** Every sheet has yellow "Your hand value" cells. Do these on paper or a
   calculator **before** looking at the Excel column.
2. **Formula audit.** The Validation Engineer and Finance Modeller read every formula in the
   workbook (click a cell, read the formula bar) and confirm it matches the rules in
   `docs/NEW_FEATURES_GUIDE.md` section 2. Note anything you disagree with.
3. **Disclosure.** Log in the AI_Log that the workbook was AI-built and that you verified it by hand
   calculation and formula audit. Write this up honestly in the validation report: it is good
   material for the "AI capability" section of the reflection.

## 1. Before you start (10 minutes)

1. Make sure the tool's `data/` folder has your **verified** data.
2. Run `python scripts/export_validation_values.py`. It writes `results/validation_tool_values.csv`.
3. Open the workbook. On `Fin_Inputs`, paste your verified finance inputs into the yellow cells.
   On `Fin_Activities`, paste `id, name, predecessors, dur_m, cost_m_lakh, daily_cost_lakh` from your
   verified CSV, replacing the starter rows.
4. Copy every value from `validation_tool_values.csv` into the matching yellow "Tool" cells (the
   test IDs match). The workbook is pre-filled with values for the starter data, so the finance ones
   **must** be updated.

## 2. T01: PERT means (sheet T1_PERT)

**By hand**, for each activity: PERT mean = (O + 4M + P) / 6.
Example for B (O = 3, M = 5, P = 9): (3 + 20 + 9) / 6 = 32 / 6 = **5.333 days**.
Type each into the yellow column. Column K shows any difference from Excel; it should be zero.

The tool's simulated mean (200,000 runs) should be within 0.02 days of the PERT mean. This is the
check the brief asks for by name: "compare simulated means with PERT mean calculations done by hand".

## 3. T02 and T03: critical path (sheet T2_CPM)

**By hand** for most-likely durations, forward pass:
- A: start 0, finish 4
- B and C start at 4: B finishes 9, C finishes 10
- D starts 9, finishes 14; E starts 10, finishes 14
- F starts at max(14, 14) = 14, finishes **16**

Backward pass from 16 gives zero float everywhere: both paths are critical. Enter 16 in the yellow
cell for T02. Repeat with PERT means for T03: path A-B-D-F = 4 + 5.333 + 5.333 + 2 = **16.667**.

## 4. T04 to T06: Monte Carlo in Excel (sheet T3_MonteCarlo)

Nothing to type except the tool values. Each of the 5,000 rows is one run; columns H and I are the
two paths, J the project duration, K whether path A-B-D-F was the longer one.

- Press **F9** a few times. The Excel numbers move slightly each time, because they are random.
  That is why each test has a tolerance (about five times the expected random error).
- Check the box under row 11: the Excel mean of each activity should match its PERT mean.
- Note "merge bias" (cell C14): the simulated mean is about 0.45 days above the PERT answer. This
  is a key finding for the report: single-path PERT is too optimistic when paths run in parallel.
- For the record, take a screenshot or copy the summary block and paste as values, since F9 will
  change it.

If a test fails once, press F9 and check again. If it keeps failing, it is a real discrepancy.

## 5. T09: correlation (sheet T4_Correlated, optional but recommended)

This rebuilds the tool's correlation method by hand for two activities: correlated normal numbers
(z2 = 0.6 × z1 + √(1 − 0.6²) × another normal), turned into uniforms, then into PERT-Beta durations.

Check that (a) the measured correlation is close to the theory value (6/π)·asin(0.3) = 0.582,
(b) the tool's result matches, and (c) P80 is higher than in T3. B and D are on the same path, so
when they slip together the bad outcomes get worse.

## 6. T15 to T21: finance (sheets Fin_Activities, Fin_Spread, Fin_CashFlow)

1. On `Fin_Activities`, check column P says "OK" for every row. "Predecessor missing or below this
   row" means a typo in the predecessors or the rows are out of order.
2. Check `Fin_Activities` project duration equals the tool's plan duration.
3. On `Fin_CashFlow`, read down the month columns and check each line makes sense: land in month 0,
   spending during construction, later collections after completion, debt rising then falling to zero.
4. Results table (row 27 onwards): every line should say Pass with the scenario "Plan".
5. **Hand checks** (bottom of the sheet): do the six items by calculator and type them in.
   For month-1 spend, take each activity running in days 0 to 30 and add cost × (days inside month 1
   ÷ duration).
6. **T20, flat 10%:** on `Fin_Inputs` set cost_multiplier to 1.10. The scenario changes to "Flat10";
   check every line passes. Set it back to 1.
7. **T21, delay:** set delay_days to 60. The scenario changes to "Delay60"; check again. This
   validates the cost-of-delay feature. Set it back to 0.
8. Optional: switch on buyer compensation (rera_delay_interest_annual above 0) with delay_days = 60
   and compare Excel's NPV with the app's cost-of-delay result for the same settings.

## 7. Tests done in the app or by script

| Test | How | Pass if |
|---|---|---|
| T07 degenerate case | Already a pytest test; also try a CSV where O = M = P for every activity | Every run gives the hand CPM duration |
| T08 serial chain | pytest | Mean = sum of PERT means |
| T10 convergence | `results/convergence.csv` from the rerun script | P80 changes less than 0.5% from 10,000 to 50,000 runs |
| T11 loop | Upload a CSV where A depends on B and B on A | App shows a clear "loop" error, no crash |
| T12 missing column | Upload a CSV with `dur_p` deleted | App shows "Missing required column" |
| T13 risk probability 0 | Edit a risk to probability 0, same seed | P80 unchanged versus the run with that risk removed |
| T14 risk probability 1 | Set the handover approval risk (on the last activity) to probability 1 | Mean duration rises by its mean delay, (O + M + P)/3 of the delay range |
| T17 AI feature | Not built | Mark "Not applicable" |

Run `pytest -q` and record the result (26 tests) as one line in the Validation tab too.

## 8. Recording results

For every test, copy the Summary sheet row into the tracking workbook's Validation tab: Excel value
in "Expected", tool value in "Tool result", tolerance, and the result will calculate.

**For any Fail:**
1. Find the first number where Excel and the tool disagree (for finance, go month by month).
2. Work out which one is wrong by hand.
3. Fix the formula or the code, rerun both, and confirm the Pass.
4. Record the cause and the fix in the Validation tab and, if AI-written code or formulas caused
   it, in the AI_Log and Bugs tabs.

Discrepancies you found and fixed are **good** for your grade: the validation report asks for "a
table of discrepancies, and how each was resolved". Common causes: a predecessor typed wrongly,
an input value different between Excel and `finance_inputs.json`, a percentage typed as 15 instead of
0.15, or an activity row out of order.

## 9. Structure for the validation report

1. Purpose and approach (hand calculation, plain-Excel benchmark, automated tests)
2. Benchmark case: the 6-activity network, with the hand PERT and CPM working shown
3. Results table: test, manual value, tool value, difference, tolerance, result
4. Monte Carlo comparison and merge bias
5. Correlation check
6. Finance benchmark: plan, flat 10%, delay; the hand checks
7. Edge cases and convergence
8. Discrepancies found and how each was resolved
9. Limits of the validation (both built with AI help; what the hand checks do and do not cover)
