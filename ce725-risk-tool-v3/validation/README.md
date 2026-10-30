# Validation

Put the manual benchmark files here:

- `benchmark_6_activity.xlsx`: hand PERT means and SDs, deterministic CPM, 5,000-row Excel
  simulation using RAND() and BETA.INV. The network is the same as `data/benchmark_6_activity.csv`.
- `finance_benchmark.xlsx`: deterministic cash flow, NPV and IRR checked by hand.
- `convergence.csv`: output of `engine.convergence(...)`.

Excel PERT-Beta sample for one activity (O in B2, M in C2, P in D2):
  alpha: =1+4*(C2-B2)/(D2-B2)
  beta:  =1+4*(D2-C2)/(D2-B2)
  draw:  =BETA.INV(RAND(), alpha, beta, B2, D2)

Every comparison goes in the Validation tab of the tracking workbook.
