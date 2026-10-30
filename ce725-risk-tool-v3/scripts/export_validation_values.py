"""Export the tool's values for every check in the Excel validation workbook.

Run from the repo root:   python scripts/export_validation_values.py
Then copy each value into the yellow "Tool value" cells of validation/Validation_Benchmark.xlsx.
Rerun after any data change (the finance values depend on your activity and finance data).
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

from engine import activity_table, baseline_comparison, load_network, run_simulation
from finance.cashflow import deterministic_finance

DATA, OUT = ROOT / "data", ROOT / "results"
OUT.mkdir(exist_ok=True)
rows = []
add = lambda test, item, value: rows.append({"test": test, "item": item, "tool_value": float(value)})

# ---- 6-activity benchmark (independent) ----
b = load_network(DATA / "benchmark_6_activity.csv")
base = baseline_comparison(b)
add("T02", "Deterministic duration, most-likely (days)", base["most_likely_duration"])
add("T03", "PERT single critical path duration (days)", base["pert_duration"])
big = run_simulation(b, n_iter=200_000, seed=42)
t = activity_table(b, big).set_index("id")
for a in b.ids:
    add(f"T01{a}", f"Simulated mean duration of {a} (days)", t.loc[a, "simulated_mean_days"])
d = big.project_duration
add("T04", "Project mean duration (days)", d.mean())
add("T05", "Project P80 duration (days)", np.percentile(d, 80))
add("T05b", "Project P50 duration (days)", np.percentile(d, 50))
add("T05c", "Project P90 duration (days)", np.percentile(d, 90))
add("T06", "Criticality index of B", t.loc["B", "criticality_index"])

# ---- benchmark with B and D correlated at 0.6 ----
bc = load_network(DATA / "benchmark_6_activity_correlated.csv")
rc = run_simulation(bc, n_iter=200_000, seed=42, rho_by_group={"pairBD": 0.6})
add("T09b", "Correlated case: project mean duration (days)", rc.project_duration.mean())
add("T09c", "Correlated case: project P80 duration (days)", np.percentile(rc.project_duration, 80))
add("T09d", "Correlated case: rank correlation B-D", pd.DataFrame(rc.durations[:, [bc.index("B"), bc.index("D")]]).corr("spearman").iloc[0, 1])

# ---- finance, deterministic plan and two variants ----
net = load_network(DATA / "case_study_activities.csv")
inputs = json.loads((DATA / "finance_inputs.json").read_text())
last = [net.ids[i] for i in range(net.n) if not net.succs[i]][0]
for label, kw in [("Plan", {}), ("Flat10", {"cost_multiplier": 1.10}),
                  ("Delay60", {"delay_activity": last, "delay_days": 60})]:
    s, _ = deterministic_finance(net, inputs, **kw)
    for key in ["project_days", "construction_cost_lakh", "project_npv_lakh", "equity_npv_lakh", "project_irr",
                "equity_irr", "idc_lakh", "total_interest_lakh", "peak_debt_lakh", "delay_comp_lakh", "profit_lakh"]:
        add(f"FIN-{label}", key, s[key])

out = pd.DataFrame(rows)
out.to_csv(OUT / "validation_tool_values.csv", index=False)
print(out.to_string(index=False))
print(f"\nDelay scenario uses activity {last}. Saved to {OUT / 'validation_tool_values.csv'}")
