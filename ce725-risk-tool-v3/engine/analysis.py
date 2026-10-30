"""Higher-level analyses built on the simulation: contingency vs flat 10%, the model ladder,
correlation sensitivity, risk contributions and the mitigation calculator.

All comparisons use the same random seed, so differences between scenarios come from the change
being tested, not from random noise (common random numbers).
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from .cpm import deterministic_cpm
from .simulate import DAYS_PER_MONTH, run_simulation
from .sampling import pert_mean


def plan_cost(net, overhead_per_month_lakh: float) -> float:
    """The 'base estimate': most-likely costs and durations, no risks."""
    dur = deterministic_cpm(net, net.dur_m)["duration"]
    return float(net.cost_m.sum() + (net.daily_cost * net.dur_m).sum()
                 + overhead_per_month_lakh * dur / DAYS_PER_MONTH)


def contingency_summary(net, res, overhead_per_month_lakh: float, fin=None, inputs=None) -> dict:
    """Contingency needed at P50/P80/P90 vs a flat 10% allowance, and (optionally) the NPV effect.

    fin: per-iteration finance summary from finance.cashflow.run_finance
    """
    base = plan_cost(net, overhead_per_month_lakh)
    cost = res.project_cost
    p50, p80, p90 = np.percentile(cost, [50, 80, 90])
    out = {
        "base_estimate_lakh": base,
        "flat10_budget_lakh": 1.10 * base,
        "P50_cost_lakh": p50, "P80_cost_lakh": p80, "P90_cost_lakh": p90,
        "contingency_P50_pct": p50 / base - 1,
        "contingency_P80_pct": p80 / base - 1,
        "contingency_P90_pct": p90 / base - 1,
        "prob_cost_exceeds_flat10": float((cost > 1.10 * base).mean()),
        "shortfall_at_P80_vs_flat10_lakh": p80 - 1.10 * base,
    }
    if fin is not None and inputs is not None:
        from finance.cashflow import deterministic_finance
        plan_fin, _ = deterministic_finance(net, inputs)
        plan10_fin, _ = deterministic_finance(net, inputs, cost_multiplier=1.10)
        npv = fin["project_npv_lakh"]
        out.update({
            "plan_npv_lakh": float(plan_fin["project_npv_lakh"]),
            "plan_plus_flat10_npv_lakh": float(plan10_fin["project_npv_lakh"]),
            "sim_mean_npv_lakh": float(npv.mean()),
            "sim_P50_npv_lakh": float(npv.median()),
            "npv_80pct_confidence_lakh": float(np.percentile(npv, 20)),   # 80% of runs are at least this
            "prob_npv_negative": float((npv < 0).mean()),
            "plan_project_irr": float(plan_fin["project_irr"]),
            "sim_P50_project_irr": float(fin["project_irr"].median()),
            "plan_equity_irr": float(plan_fin["equity_irr"]),
            "sim_P50_equity_irr": float(fin["equity_irr"].median()),
            "plan_idc_lakh": float(plan_fin["idc_lakh"]),
            "sim_P50_idc_lakh": float(fin["idc_lakh"].median()),
        })
    return out


def model_ladder(net, rho_by_group, risks, overhead_per_month_lakh: float,
                 n_iter: int = 10_000, seed: int = 42) -> pd.DataFrame:
    """How the answer changes as each layer of realism is added."""
    rows = []
    ml = deterministic_cpm(net, net.dur_m)["duration"]
    base_cost = plan_cost(net, overhead_per_month_lakh)
    rows.append(("1. Plan: most-likely durations", ml, ml, base_cost, base_cost))

    pdur = pert_mean(net.dur_o, net.dur_m, net.dur_p)
    pd_ = deterministic_cpm(net, pdur)["duration"]
    pcost = float(pert_mean(net.cost_o, net.cost_m, net.cost_p).sum() + (net.daily_cost * pdur).sum()
                  + overhead_per_month_lakh * pd_ / DAYS_PER_MONTH)
    rows.append(("2. PERT means on one critical path", pd_, pd_, pcost, pcost))

    steps = [("3. Simulation, activities independent", None, None),
             ("4. + correlated activities", rho_by_group, None),
             ("5. + risk register events", rho_by_group, risks)]
    for label, rho, rk in steps:
        r = run_simulation(net, n_iter=n_iter, seed=seed, rho_by_group=rho, risks=rk,
                           overhead_per_month_lakh=overhead_per_month_lakh)
        rows.append((label, *np.percentile(r.project_duration, [50, 80]), *np.percentile(r.project_cost, [50, 80])))
    return pd.DataFrame(rows, columns=["step", "duration_P50_days", "duration_P80_days", "cost_P50_lakh", "cost_P80_lakh"])


def correlation_sensitivity(net, rho_by_group, risks, overhead_per_month_lakh: float,
                            levels=(0.0, 0.3, 0.6, 0.9), n_iter: int = 10_000, seed: int = 42) -> pd.DataFrame:
    """P80 with every group's correlation set to each level, plus your verified values."""
    cases = [(f"All groups = {lv}", {g: lv for g in set(net.groups)}) for lv in levels]
    cases.append(("Verified values", rho_by_group))
    rows = []
    for label, rho in cases:
        r = run_simulation(net, n_iter=n_iter, seed=seed, rho_by_group=rho, risks=risks,
                           overhead_per_month_lakh=overhead_per_month_lakh)
        rows.append((label, *np.percentile(r.project_duration, [50, 80, 90]), *np.percentile(r.project_cost, [50, 80, 90])))
    return pd.DataFrame(rows, columns=["case", "dur_P50", "dur_P80", "dur_P90", "cost_P50", "cost_P80", "cost_P90"])


def risk_contributions(net, rho_by_group, risks, overhead_per_month_lakh: float,
                       n_iter: int = 10_000, seed: int = 42) -> pd.DataFrame:
    """How much P80 duration and cost fall when each risk is removed (others left on)."""
    def run(rk):
        r = run_simulation(net, n_iter=n_iter, seed=seed, rho_by_group=rho_by_group, risks=rk,
                           overhead_per_month_lakh=overhead_per_month_lakh)
        return np.percentile(r.project_duration, 80), np.percentile(r.project_cost, 80), r.project_duration.mean()
    base_d, base_c, base_m = run(risks)
    rows = []
    for i, rk in risks.iterrows():
        off = risks.copy()
        off.loc[i, "probability"] = 0.0
        d, c, m = run(off)
        rows.append((rk["id"], rk["name"], rk["probability"], base_d - d, base_c - c, base_m - m))
    return pd.DataFrame(rows, columns=["id", "risk", "probability", "P80_days_added", "P80_cost_added_lakh",
                                       "mean_days_added"]).sort_values("P80_days_added", ascending=False)


def evaluate_mitigation(net, rho_by_group, risks, risk_id: str, new_probability: float,
                        impact_scale: float, mitigation_cost_lakh: float, inputs: dict,
                        n_iter: int = 10_000, seed: int = 42) -> dict:
    """Is a mitigation worth its cost?

    new_probability: probability of the risk after the fix
    impact_scale:    multiply the risk's delay and cost impact (1 = unchanged, 0.5 = halved)
    mitigation_cost_lakh: paid at project start (month 0); record this choice as an assumption
    """
    from finance.cashflow import _months_needed, run_finance
    oh = inputs["overhead_per_month_lakh"]
    before = run_simulation(net, n_iter=n_iter, seed=seed, rho_by_group=rho_by_group, risks=risks,
                            overhead_per_month_lakh=oh)
    mod = risks.copy()
    i = mod.index[mod["id"] == risk_id][0]
    mod.loc[i, "probability"] = new_probability
    for col in ["delay_o", "delay_m", "delay_p", "cost_o_lakh", "cost_m_lakh", "cost_p_lakh"]:
        mod.loc[i, col] = float(mod.loc[i, col]) * impact_scale
    after = run_simulation(net, n_iter=n_iter, seed=seed, rho_by_group=rho_by_group, risks=mod,
                           overhead_per_month_lakh=oh)
    T = max(_months_needed(before.project_duration, inputs), _months_needed(after.project_duration, inputs))
    fb, _ = run_finance(before, inputs, n_months=T)
    fa, _ = run_finance(after, inputs, extra_upfront_lakh=mitigation_cost_lakh, n_months=T)
    fa_free, _ = run_finance(after, inputs, extra_upfront_lakh=0.0, n_months=T)

    def row(label, b, a, unit):
        return {"measure": label, "without fix": b, "with fix": a, "change": a - b, "unit": unit}
    table = pd.DataFrame([
        row("Mean duration", before.project_duration.mean(), after.project_duration.mean(), "days"),
        row("P80 duration", np.percentile(before.project_duration, 80), np.percentile(after.project_duration, 80), "days"),
        row("Mean construction cost (excl. fix)", before.project_cost.mean(), after.project_cost.mean(), "Rs lakh"),
        row("P80 construction cost (excl. fix)", np.percentile(before.project_cost, 80), np.percentile(after.project_cost, 80), "Rs lakh"),
        row("Mean project NPV (incl. fix cost)", fb["project_npv_lakh"].mean(), fa["project_npv_lakh"].mean(), "Rs lakh"),
        row("NPV at 80% confidence (incl. fix cost)", np.percentile(fb["project_npv_lakh"], 20), np.percentile(fa["project_npv_lakh"], 20), "Rs lakh"),
        row("Chance NPV < 0", (fb["project_npv_lakh"] < 0).mean(), (fa["project_npv_lakh"] < 0).mean(), "probability"),
    ])
    npv_gain = float(fa["project_npv_lakh"].mean() - fb["project_npv_lakh"].mean())
    breakeven = float(fa_free["project_npv_lakh"].mean() - fb["project_npv_lakh"].mean())   # max worth paying today
    return {"table": table, "npv_gain_lakh": npv_gain, "worth_it": npv_gain > 0,
            "max_worth_paying_lakh": breakeven, "risk_id": risk_id}


def cost_of_delay(net, inputs: dict, activity_id: str, delays=(0, 15, 30, 60, 90, 120, 180)) -> pd.DataFrame:
    """What a delay of X days in one activity costs, split into its parts (plan basis, no risks).

    A delay on an activity with float does not move the finish date until the float is used up,
    but its own time-dependent cost still grows. Completion is counted in whole months, so a short
    delay that stays inside the same month changes little.
    later_sales_and_timing_lakh = NPV loss not explained by the (undiscounted) extra costs, interest
    and compensation: mainly sales cash arriving later. It is an approximation.
    """
    from finance.cashflow import deterministic_finance
    base, _ = deterministic_finance(net, inputs)
    rows = []
    for d in delays:
        s, _ = deterministic_finance(net, inputs, delay_activity=activity_id, delay_days=d)
        loss = base["project_npv_lakh"] - s["project_npv_lakh"]
        rows.append({
            "delay_days": d,
            "project_delay_days": s["project_days"] - base["project_days"],
            "finish_month": s["completion_month"],
            "extra_construction_cost_lakh": s["construction_cost_lakh"] - base["construction_cost_lakh"],
            "extra_interest_lakh": s["total_interest_lakh"] - base["total_interest_lakh"],
            "buyer_compensation_lakh": s["delay_comp_lakh"] - base["delay_comp_lakh"],
            "project_npv_lakh": s["project_npv_lakh"],
            "npv_loss_lakh": loss,
            "later_sales_and_timing_lakh": loss - (s["construction_cost_lakh"] - base["construction_cost_lakh"])
                                           - (s["total_interest_lakh"] - base["total_interest_lakh"])
                                           - (s["delay_comp_lakh"] - base["delay_comp_lakh"]),
            "npv_loss_per_day_lakh": loss / d if d else 0.0,
            "equity_irr": s["equity_irr"],
        })
    return pd.DataFrame(rows)


def npv_loss_per_month_from_simulation(res, fin) -> float:
    """Average fall in project NPV per extra month of duration across all runs (least-squares slope).
    Includes the extra costs that tend to come with longer runs, so it is an association, not a
    pure time effect; the cost_of_delay table isolates the time effect."""
    months = res.project_duration / DAYS_PER_MONTH
    slope = np.polyfit(months, fin["project_npv_lakh"].to_numpy(), 1)[0]
    return float(-slope)
