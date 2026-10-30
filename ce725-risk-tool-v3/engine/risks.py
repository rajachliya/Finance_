"""Discrete risk events from a risk register.

Each risk either happens or not in an iteration (Bernoulli with its probability). If it happens,
a delay (days) is drawn from a triangular distribution and added to each affected activity, and a
cost impact (lakh) is drawn and added to project cost.

Note for the team: if one risk lists two activities that are in series, the delay is counted
twice along that path. Either link each risk to one activity, or change this rule, and record the
choice in the decision log.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from .network import Network


def _tri_from_u(u, o, m, p):
    """Triangular inverse CDF. Uses supplied uniforms so every scenario consumes the same random
    numbers (common random numbers), which keeps before/after comparisons fair."""
    o, m, p = float(o), float(m), float(p)
    if p <= o:
        return np.full_like(u, o)
    c = (m - o) / (p - o)
    return stats.triang.ppf(u, c, loc=o, scale=p - o)


def load_risks(path: str) -> pd.DataFrame:
    return pd.read_csv(path)


def validate_risks(risks: pd.DataFrame, net: Network) -> list[str]:
    problems = []
    for _, r in risks.iterrows():
        if not 0 <= float(r["probability"]) <= 1:
            problems.append(f"{r['id']}: probability must be between 0 and 1")
        targets = str(r.get("affected_activities", "") or "")
        for a in [t.strip() for t in targets.replace(",", ";").split(";") if t.strip() and t.strip() != "nan"]:
            if a not in net.ids:
                problems.append(f"{r['id']}: affected activity '{a}' does not exist")
    return problems


def sample_risks(net: Network, risks: pd.DataFrame, n_iter: int, rng: np.random.Generator,
                 enabled: list[str] | None = None) -> dict:
    """Returns extra delay per activity (n_iter x n_act), extra cost (n_iter,), and per-risk occurrence."""
    extra_delay = np.zeros((n_iter, net.n))
    extra_cost = np.zeros(n_iter)
    occurred = {}
    for _, r in risks.iterrows():
        rid = str(r["id"])
        # Always draw the same three sets of uniforms per risk, even if the risk is switched off,
        # so switching one risk off or changing its probability does not change any other draw.
        u_hit, u_delay, u_cost = rng.random(n_iter), rng.random(n_iter), rng.random(n_iter)
        p = float(r["probability"]) if (enabled is None or rid in enabled) else 0.0
        hit = u_hit < p
        occurred[rid] = hit
        delay = _tri_from_u(u_delay, r["delay_o"], r["delay_m"], r["delay_p"]) * hit
        cost = _tri_from_u(u_cost, r["cost_o_lakh"], r["cost_m_lakh"], r["cost_p_lakh"]) * hit
        extra_cost += cost
        targets = str(r.get("affected_activities", "") or "")
        for a in [t.strip() for t in targets.replace(",", ";").split(";") if t.strip() and t.strip() != "nan"]:
            extra_delay[:, net.index(a)] += delay
    return {"extra_delay": extra_delay, "extra_cost": extra_cost, "occurred": occurred}
