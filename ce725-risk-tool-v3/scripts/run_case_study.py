"""Rerun the case study with the current data and save every number the reports need.

Run from the repo root:   python scripts/run_case_study.py
Outputs go to results/. Rerun whenever any input file changes, and commit the results folder so
the report, slides and website always quote the same numbers.
"""
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

from engine import activity_table, baseline_comparison, convergence, load_network, percentiles, run_simulation
from engine.analysis import (contingency_summary, correlation_sensitivity, cost_of_delay, model_ladder,
                             npv_loss_per_month_from_simulation, risk_contributions)
from engine.risks import load_risks, validate_risks
from finance.cashflow import deterministic_finance, promised_month_for, run_finance

N_ITER, SEED = 10_000, 42
DATA, OUT = ROOT / "data", ROOT / "results"
OUT.mkdir(exist_ok=True)

net = load_network(DATA / "case_study_activities.csv")
risks = load_risks(DATA / "risk_register.csv")
assert not (p := validate_risks(risks, net)), p
rho = dict(pd.read_csv(DATA / "correlation_groups.csv")[["group", "rho"]].values)
inputs = json.loads((DATA / "finance_inputs.json").read_text())
oh = inputs["overhead_per_month_lakh"]

print("Running main simulation...")
res = run_simulation(net, n_iter=N_ITER, seed=SEED, rho_by_group=rho, risks=risks, overhead_per_month_lakh=oh)
fin, _ = run_finance(res, inputs, promised_month=promised_month_for(net, inputs))
base = baseline_comparison(net)
dur, cost = percentiles(res.project_duration), percentiles(res.project_cost)
cont = contingency_summary(net, res, oh, fin, inputs)
drivers = activity_table(net, res).sort_values("cruciality", ascending=False)

print("Model ladder, risk contributions, correlation sensitivity, convergence...")
ladder = model_ladder(net, rho, risks, oh, N_ITER, SEED)
contrib = risk_contributions(net, rho, risks, oh, N_ITER, SEED)
corr = correlation_sensitivity(net, rho, risks, oh, n_iter=N_ITER, seed=SEED)
conv = convergence(net, sizes=(1_000, 5_000, 10_000, 20_000, 50_000), seed=SEED, rho_by_group=rho, risks=risks,
                   overhead_per_month_lakh=oh)
plan_fin, plan_cf = deterministic_finance(net, inputs)
last_act = [net.ids[i] for i in range(net.n) if not net.succs[i]][0]
delay_tab = cost_of_delay(net, inputs, last_act, (0, 30, 60, 90, 180))
slope = npv_loss_per_month_from_simulation(res, fin)

# ---- save tables ----
ladder.to_csv(OUT / "model_ladder.csv", index=False)
contrib.to_csv(OUT / "risk_contributions.csv", index=False)
corr.to_csv(OUT / "correlation_sensitivity.csv", index=False)
conv.to_csv(OUT / "convergence.csv", index=False)
delay_tab.to_csv(OUT / "cost_of_delay.csv", index=False)
drivers.to_csv(OUT / "activity_drivers.csv", index=False)
plan_cf.to_csv(OUT / "plan_monthly_cashflow.csv")          # compare line by line with the Excel benchmark
fin.describe(percentiles=[0.1, 0.2, 0.5, 0.8, 0.9]).T.to_csv(OUT / "finance_distribution.csv")
summary = {"run_date": str(date.today()), "iterations": N_ITER, "seed": SEED,
           "prob_finish_by_plan": float((res.project_duration <= base["most_likely_duration"]).mean()),
           "duration_days": dur, "cost_lakh": cost, "plan": base, **{k: float(v) for k, v in cont.items()},
           "plan_finance": {k: float(v) for k, v in plan_fin.items()}}
(OUT / "summary.json").write_text(json.dumps(summary, indent=2, default=str))

# ---- headline report ----
m = lambda d: d / 30
top3 = drivers.head(3)
toprisk = contrib.head(3)
p80_change_corr = corr.iloc[-2]["dur_P80"] - corr.iloc[0]["dur_P80"]
lines = [
    f"# Case study headline results ({date.today():%d %b %Y})",
    "",
    f"{N_ITER:,} iterations, seed {SEED}. Rerun `python scripts/run_case_study.py` after any data change.",
    "",
    "## Schedule",
    f"- Plan with most-likely durations: {base['most_likely_duration']:.0f} days ({m(base['most_likely_duration']):.1f} months)",
    f"- PERT on one critical path: {base['pert_duration']:.0f} days",
    f"- Simulated P50 / P80 / P90: {dur['P50']:.0f} / {dur['P80']:.0f} / {dur['P90']:.0f} days "
    f"({m(dur['P50']):.1f} / {m(dur['P80']):.1f} / {m(dur['P90']):.1f} months)",
    f"- Chance of finishing by the plan date: {(res.project_duration <= base['most_likely_duration']).mean():.1%}",
    "",
    "## Cost and contingency",
    f"- Base estimate: Rs {cont['base_estimate_lakh']:,.0f} lakh; flat 10% budget: Rs {cont['flat10_budget_lakh']:,.0f} lakh",
    f"- P50 / P80 / P90 cost: Rs {cont['P50_cost_lakh']:,.0f} / {cont['P80_cost_lakh']:,.0f} / {cont['P90_cost_lakh']:,.0f} lakh",
    f"- Contingency needed: {cont['contingency_P50_pct']:.1%} (P50), {cont['contingency_P80_pct']:.1%} (P80), {cont['contingency_P90_pct']:.1%} (P90)",
    f"- Chance a flat 10% is not enough: {cont['prob_cost_exceeds_flat10']:.1%}",
    "",
    "## Finance",
    f"- Plan NPV: Rs {cont['plan_npv_lakh']:,.0f} lakh; plan + flat 10%: Rs {cont['plan_plus_flat10_npv_lakh']:,.0f} lakh",
    f"- Simulated median NPV: Rs {cont['sim_P50_npv_lakh']:,.0f} lakh; NPV with 80% confidence: Rs {cont['npv_80pct_confidence_lakh']:,.0f} lakh",
    f"- Chance NPV < 0: {cont['prob_npv_negative']:.1%}",
    f"- Project IRR: plan {cont['plan_project_irr']:.1%}, simulated median {cont['sim_P50_project_irr']:.1%}",
    f"- Equity IRR: plan {cont['plan_equity_irr']:.1%}, simulated median {cont['sim_P50_equity_irr']:.1%}",
    f"- Interest during construction: plan Rs {cont['plan_idc_lakh']:,.0f} lakh, simulated median Rs {cont['sim_P50_idc_lakh']:,.0f} lakh",
    "",
    "## Cost of delay",
    *[f"- {int(r.delay_days)} days late at {last_act}: NPV falls by Rs {r.npv_loss_lakh:,.0f} lakh" for r in delay_tab.itertuples() if r.delay_days],
    f"- From the simulation: each extra month goes with about Rs {slope:,.0f} lakh less NPV",
    "",
    "## What drives delay",
    *[f"- {r.id} {r.activity}: critical in {r.criticality_index:.0%} of runs, rank correlation {r.spearman_with_project:.2f}" for r in top3.itertuples()],
    *[f"- Risk {r.id} ({r.risk}) adds {r.P80_days_added:.0f} days to P80" for r in toprisk.itertuples()],
    "",
    "## Model ladder (P80 duration, days)",
    *[f"- {r.step}: {r.duration_P80_days:.0f}" for r in ladder.itertuples()],
    "",
    "## Checks",
    f"- Correlation sensitivity: P80 moves {p80_change_corr:+.0f} days between all-0 and all-0.9 correlation",
    f"- Convergence: P80 = {conv.iloc[2]['P80_days']:.1f} days at 10,000 runs vs {conv.iloc[-1]['P80_days']:.1f} at 50,000",
    "",
    "## One-line result (for slides, website, resume)",
    f"P80 contingency of {cont['contingency_P80_pct']:.1%} versus a flat 10%; P80 finish {m(dur['P80'] - base['most_likely_duration']):.1f} months "
    f"later than plan; median NPV Rs {cont['plan_npv_lakh'] - cont['sim_P50_npv_lakh']:,.0f} lakh below the plan's.",
]
(OUT / "headline_results.md").write_text("\n".join(lines) + "\n")
print("\n".join(lines))
print(f"\nSaved to {OUT}")
