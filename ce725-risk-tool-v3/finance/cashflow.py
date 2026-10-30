"""Finance layer: construction spend -> funding -> sales -> NPV and IRR, for every iteration.

Timeline convention (use the same in the Excel benchmark):
    month 0           = project start: land and approvals are paid here
    month k (k >= 1)  = days (k-1)*30 to k*30 of construction
    completion month  = ceil(project duration / 30)

Cash flows, all in Rs lakh:
    construction spend  each activity's cost spread evenly over its own start..finish days
    overheads           overhead_per_month for every month (or part month) until completion
    risk costs          spread in proportion to construction spend
    collections         presale_share of revenue collected in step with construction progress
                        (construction-linked plan); the rest collected evenly over
                        months_to_sell_after_completion months after completion
    brokerage           brokerage_pct of collections
    delay compensation  optional: interest owed to buyers who have paid, for each month that
                        completion is later than the promised month (RERA-style; set
                        rera_delay_interest_annual to 0 to switch off). Promised month = plan
                        completion month + rera_grace_months. TEAM: verify the rule and the
                        prescribed rate against the RERA Act (Section 18) and your state's rules.

Funding (equity view):
    month 0 costs (land, approvals) are paid by equity, because banks generally do not fund
    land purchase (TEAM: verify against current RBI rules and log the source)
    any later month with negative project cash flow: debt pays debt_share, equity the rest
    interest accrues monthly on the debt balance and is capitalised (added to the balance);
    interest accrued up to completion = interest during construction (IDC)
    any month with positive project cash flow: first repays debt (cash sweep), rest goes to equity
    any debt left at the end is repaid by equity in the last month

Every rule above is a modelling choice. Record each in the Assumptions tab.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

DAYS_PER_MONTH = 30.0


def monthly_rate(annual: float) -> float:
    return (1 + annual) ** (1 / 12) - 1


def annualise(monthly: np.ndarray) -> np.ndarray:
    return (1 + monthly) ** 12 - 1


def spread_to_months(start: np.ndarray, dur: np.ndarray, cost: np.ndarray, n_months: int) -> np.ndarray:
    """Spread each activity's cost evenly over its days. Returns (n_iter, n_months + 1), column 0 = month 0."""
    start, dur, cost = (np.atleast_2d(x) for x in (start, dur, cost))
    finish = start + dur
    out = np.zeros((start.shape[0], n_months + 1))
    safe = np.where(dur > 0, dur, 1.0)
    for k in range(1, n_months + 1):
        a, b = (k - 1) * DAYS_PER_MONTH, k * DAYS_PER_MONTH
        overlap = np.clip(np.minimum(finish, b) - np.maximum(start, a), 0, None)
        frac = np.where(dur > 0, overlap / safe, ((start >= a) & (start < b)).astype(float))
        out[:, k] = (cost * frac).sum(axis=1)
    return out


def _months_needed(project_days: np.ndarray, inputs: dict) -> int:
    return int(math.ceil(float(np.max(project_days)) / DAYS_PER_MONTH)) + int(inputs["months_to_sell_after_completion"]) + 1


def build_cashflows(start, dur, activity_cost, project_days, risk_cost, inputs: dict,
                    extra_upfront_lakh: float = 0.0, n_months: int | None = None,
                    promised_month: float | None = None) -> dict:
    """All monthly cash flow lines for every iteration. Arrays have shape (n_iter, n_months + 1)."""
    project_days = np.atleast_1d(np.asarray(project_days, float))
    risk_cost = np.broadcast_to(np.atleast_1d(np.asarray(risk_cost, float)), project_days.shape)
    n_iter = project_days.shape[0]
    T = n_months or _months_needed(project_days, inputs)
    k = np.arange(T + 1)[None, :]

    spend = spread_to_months(start, dur, activity_cost, T)
    total_spend = spend.sum(axis=1, keepdims=True)
    share = np.divide(spend, total_spend, out=np.zeros_like(spend), where=total_spend > 0)

    months_open = np.clip(project_days[:, None] - (k - 1) * DAYS_PER_MONTH, 0, DAYS_PER_MONTH) / DAYS_PER_MONTH
    months_open[:, 0] = 0.0
    overheads = inputs["overhead_per_month_lakh"] * months_open
    risks = risk_cost[:, None] * share
    upfront = np.zeros((n_iter, T + 1))
    upfront[:, 0] = inputs["land_cost_lakh"] + inputs["approvals_cost_lakh"] + extra_upfront_lakh

    revenue = inputs["saleable_area_sqft"] * inputs["sale_price_per_sqft_inr"] / 1e5      # Rs lakh
    presale = inputs["presale_share"] * revenue * share                                      # follows progress
    completion = np.ceil(project_days / DAYS_PER_MONTH)[:, None]
    m_after = int(inputs["months_to_sell_after_completion"])
    after_mask = (k > completion) & (k <= completion + m_after)
    post = (1 - inputs["presale_share"]) * revenue / max(m_after, 1) * after_mask
    collections = presale + post
    brokerage = inputs["brokerage_pct"] * collections

    rera_rate = float(inputs.get("rera_delay_interest_annual", 0.0))
    delay_comp = np.zeros((n_iter, T + 1))
    if rera_rate > 0 and promised_month is not None:
        paid_before = np.cumsum(presale, axis=1) - presale            # buyers' payments up to last month
        late = (k > promised_month) & (k <= completion)
        delay_comp = rera_rate / 12 * paid_before * late

    project_cf = collections - brokerage - spend - overheads - risks - upfront - delay_comp

    # Debt with capitalised interest and cash sweep (loop over months, vectorised over iterations)
    im = monthly_rate(inputs["interest_rate_annual"])
    ds = inputs["debt_share"]
    bal = np.zeros(n_iter)
    draw, interest, repay, balance, equity_cf = (np.zeros((n_iter, T + 1)) for _ in range(5))
    for t in range(T + 1):
        interest[:, t] = bal * im
        bal = bal + interest[:, t]
        cf = project_cf[:, t]
        need = np.where(cf < 0, -cf, 0.0)
        d = need * ds if t > 0 else np.zeros(n_iter)        # month 0 (land) is all equity
        draw[:, t] = d
        bal = bal + d
        surplus = np.where(cf > 0, cf, 0.0)
        r = np.minimum(bal, surplus)
        repay[:, t] = r
        bal = bal - r
        equity_cf[:, t] = -(need - d) + (surplus - r)
        balance[:, t] = bal
    equity_cf[:, -1] -= bal                                  # equity clears any debt left at the end
    repay[:, -1] += bal
    balance[:, -1] = 0.0

    idc = (interest * (k <= completion)).sum(axis=1)
    return dict(months=np.arange(T + 1), spend=spend, overheads=overheads, risk_costs=risks,
                upfront=upfront, collections=collections, brokerage=brokerage, delay_comp=delay_comp,
                project_cf=project_cf,
                debt_draw=draw, interest=interest, debt_repay=repay, debt_balance=balance,
                equity_cf=equity_cf, idc=idc, peak_debt=balance.max(axis=1), revenue_total=revenue,
                completion_month=completion[:, 0])


def npv(cashflows: np.ndarray, annual_rate: float) -> np.ndarray:
    """NPV at month 0 using a monthly rate equivalent to the annual rate. Same as Excel
    =CF0 + NPV(monthly_rate, CF1:CFn)."""
    cf = np.atleast_2d(cashflows)
    disc = (1 + monthly_rate(annual_rate)) ** -np.arange(cf.shape[1])
    return cf @ disc


def irr(cashflows: np.ndarray, lo: float = -0.5, hi: float = 0.5, iters: int = 100) -> np.ndarray:
    """Annual IRR for each row, by bisection on the monthly rate (vectorised).
    Returns NaN where the NPV does not change sign between lo and hi (no IRR in range).
    Same as Excel =(1+IRR(CF0:CFn))^12-1 for conventional cash flows."""
    cf = np.atleast_2d(cashflows)
    t = np.arange(cf.shape[1])
    f = lambda r: (cf * (1 + r[:, None]) ** -t).sum(axis=1)
    a = np.full(cf.shape[0], lo)
    b = np.full(cf.shape[0], hi)
    fa, fb = f(a), f(b)
    ok = np.sign(fa) != np.sign(fb)
    for _ in range(iters):
        m = (a + b) / 2
        fm = f(m)
        left = np.sign(fm) == np.sign(fa)
        a, fa = np.where(left, m, a), np.where(left, fm, fa)
        b = np.where(left, b, m)
    return np.where(ok, annualise((a + b) / 2), np.nan)


def summarise(flows: dict, inputs: dict) -> pd.DataFrame:
    """One row per iteration: NPV, IRRs, IDC, peak debt, profit."""
    return pd.DataFrame({
        "project_npv_lakh": npv(flows["project_cf"], inputs["discount_rate_annual"]),
        "equity_npv_lakh": npv(flows["equity_cf"], inputs.get("equity_discount_rate_annual", inputs["discount_rate_annual"])),
        "project_irr": irr(flows["project_cf"]),
        "equity_irr": irr(flows["equity_cf"]),
        "idc_lakh": flows["idc"],
        "total_interest_lakh": flows["interest"].sum(axis=1),
        "construction_cost_lakh": (flows["spend"] + flows["overheads"] + flows["risk_costs"]).sum(axis=1),
        "delay_comp_lakh": flows["delay_comp"].sum(axis=1),
        "peak_debt_lakh": flows["peak_debt"],
        "profit_lakh": flows["project_cf"].sum(axis=1),
        "completion_month": flows["completion_month"],
    })


def promised_month_for(net, inputs: dict) -> float:
    """Month promised to buyers: plan completion (most-likely durations) + grace months."""
    from engine.cpm import deterministic_cpm
    return math.ceil(deterministic_cpm(net, net.dur_m)["duration"] / DAYS_PER_MONTH) + float(inputs.get("rera_grace_months", 0))


def run_finance(result, inputs: dict, extra_upfront_lakh: float = 0.0, n_months: int | None = None,
                promised_month: float | None = None):
    """Finance for every iteration of a SimulationResult. Returns (summary DataFrame, flows dict)."""
    flows = build_cashflows(result.es, result.durations, result.activity_cost, result.project_duration,
                            result.risk_cost, inputs, extra_upfront_lakh, n_months, promised_month)
    return summarise(flows, inputs), flows


def deterministic_finance(net, inputs: dict, cost_multiplier: float = 1.0,
                          delay_activity: str | None = None, delay_days: float = 0.0,
                          n_months: int | None = None):
    """Single plan: most-likely durations and costs, no risks. Use this to check against Excel.

    cost_multiplier = 1.10 gives the 'plan plus flat 10% contingency' case (activity costs and
    overheads both scaled).
    delay_activity / delay_days: add a delay to one activity (its time-dependent cost grows too),
    used by the cost-of-delay calculator. The promised month stays at the undelayed plan.
    """
    from engine.cpm import deterministic_cpm
    dur = net.dur_m.astype(float).copy()
    if delay_activity is not None and delay_days:
        dur[net.index(delay_activity)] += delay_days
    cpm = deterministic_cpm(net, dur)
    act_cost = (net.cost_m + net.daily_cost * dur) * cost_multiplier
    scaled = dict(inputs, overhead_per_month_lakh=inputs["overhead_per_month_lakh"] * cost_multiplier)
    flows = build_cashflows(cpm["es"][None, :], dur[None, :], act_cost[None, :],
                            np.array([cpm["duration"]]), np.array([0.0]), scaled,
                            n_months=n_months, promised_month=promised_month_for(net, inputs))
    table = pd.DataFrame({name: flows[name][0] for name in
                          ["upfront", "spend", "overheads", "collections", "brokerage", "delay_comp", "project_cf",
                           "debt_draw", "interest", "debt_repay", "debt_balance", "equity_cf"]},
                         index=pd.Index(flows["months"], name="month"))
    out = summarise(flows, scaled).iloc[0]
    out["project_days"] = cpm["duration"]
    return out, table
