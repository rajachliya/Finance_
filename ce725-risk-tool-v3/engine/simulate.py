"""Run the Monte Carlo simulation and summarise the results."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy import stats

from .cpm import backward_pass, critical_mask, deterministic_cpm, forward_pass
from .network import Network
from .risks import sample_risks
from .sampling import (group_correlation_matrix, nearest_psd_correlation, pert_mean,
                       sample_three_point)

PERCENTILES = (10, 50, 80, 90)
DAYS_PER_MONTH = 30.0


@dataclass
class SimulationResult:
    durations: np.ndarray          # (n_iter, n_act) activity durations incl. risk delays
    project_duration: np.ndarray   # (n_iter,) days
    project_cost: np.ndarray       # (n_iter,) lakh
    critical: np.ndarray           # (n_iter, n_act) bool
    es: np.ndarray                 # (n_iter, n_act) early start, needed later for cash flow timing
    activity_cost: np.ndarray      # (n_iter, n_act) lakh, excluding overheads and risk cost
    risk_cost: np.ndarray          # (n_iter,) lakh
    settings: dict = field(default_factory=dict)
    psd_fixed: bool = False


def run_simulation(net: Network, n_iter: int = 10_000, seed: int | None = 42,
                   distribution: str = "pert", rho_by_group: dict[str, float] | None = None,
                   risks: pd.DataFrame | None = None, enabled_risks: list[str] | None = None,
                   overhead_per_month_lakh: float = 0.0) -> SimulationResult:
    rng = np.random.default_rng(seed)

    r = np.eye(net.n)
    psd_fixed = False
    if rho_by_group:
        r, psd_fixed = nearest_psd_correlation(group_correlation_matrix(net.groups, rho_by_group))

    dur = sample_three_point(n_iter, net.dur_o, net.dur_m, net.dur_p, r, rng, distribution)
    base_cost = sample_three_point(n_iter, net.cost_o, net.cost_m, net.cost_p, r, rng, distribution)

    risk_cost = np.zeros(n_iter)
    if risks is not None and len(risks):
        rs = sample_risks(net, risks, n_iter, rng, enabled_risks)
        dur = dur + rs["extra_delay"]
        risk_cost = rs["extra_cost"]

    es, ef, project = forward_pass(net, dur)
    ls, lf = backward_pass(net, dur, project)
    crit = critical_mask(es, ls)

    activity_cost = base_cost + net.daily_cost * dur        # time-dependent part grows with delay
    overheads = overhead_per_month_lakh * project / DAYS_PER_MONTH
    total_cost = activity_cost.sum(axis=1) + overheads + risk_cost

    return SimulationResult(
        durations=dur, project_duration=project, project_cost=total_cost, critical=crit, es=es,
        activity_cost=activity_cost, risk_cost=risk_cost, psd_fixed=psd_fixed,
        settings=dict(n_iter=n_iter, seed=seed, distribution=distribution,
                      rho_by_group=rho_by_group or {}, risks_on=risks is not None,
                      overhead_per_month_lakh=overhead_per_month_lakh),
    )


def percentiles(x: np.ndarray, ps=PERCENTILES) -> dict[str, float]:
    return {f"P{p}": float(np.percentile(x, p)) for p in ps} | {"Mean": float(np.mean(x))}


def activity_table(net: Network, res: SimulationResult) -> pd.DataFrame:
    """Per-activity criticality index, rank correlation with project duration, and cruciality."""
    ranks_act = stats.rankdata(res.durations, axis=0)
    ranks_proj = stats.rankdata(res.project_duration)
    a = ranks_act - ranks_act.mean(axis=0)
    b = ranks_proj - ranks_proj.mean()
    denom = np.sqrt((a ** 2).sum(axis=0) * (b ** 2).sum())
    spearman = np.divide((a * b[:, None]).sum(axis=0), denom, out=np.zeros(net.n), where=denom > 0)
    ci = res.critical.mean(axis=0)
    return pd.DataFrame({
        "id": net.ids,
        "activity": net.names,
        "group": net.groups,
        "pert_mean_days": pert_mean(net.dur_o, net.dur_m, net.dur_p),
        "simulated_mean_days": res.durations.mean(axis=0),
        "criticality_index": ci,
        "spearman_with_project": spearman,
        "cruciality": ci * spearman,
    })


def baseline_comparison(net: Network) -> dict:
    """Deterministic answers to compare against the simulation (the start of the 'model ladder')."""
    most_likely = deterministic_cpm(net, net.dur_m)
    pert = deterministic_cpm(net, pert_mean(net.dur_o, net.dur_m, net.dur_p))
    return {
        "most_likely_duration": most_likely["duration"],
        "most_likely_critical_path": most_likely["critical_ids"],
        "pert_duration": pert["duration"],
        "pert_critical_path": pert["critical_ids"],
        "base_cost_most_likely": float(net.cost_m.sum() + (net.daily_cost * net.dur_m).sum()),
    }


def convergence(net: Network, sizes=(500, 1_000, 5_000, 10_000, 50_000), seed: int = 1, **kwargs) -> pd.DataFrame:
    """How P80 duration settles as the number of iterations grows (for the validation report)."""
    rows = []
    for n in sizes:
        res = run_simulation(net, n_iter=n, seed=seed, **kwargs)
        p = percentiles(res.project_duration)
        rows.append({"iterations": n, "mean_days": p["Mean"], "P80_days": p["P80"], "P90_days": p["P90"]})
    return pd.DataFrame(rows)
