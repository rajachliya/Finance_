"""Tests for the finance layer, contingency, ladder and mitigation. Record each in the Validation tab."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from engine import load_network, run_simulation
from engine.analysis import evaluate_mitigation, model_ladder, plan_cost
from engine.risks import load_risks
from finance.cashflow import (build_cashflows, deterministic_finance, irr, monthly_rate, npv,
                              spread_to_months)

DATA = Path(__file__).resolve().parents[1] / "data"
INPUTS = json.loads((DATA / "finance_inputs.json").read_text())


@pytest.fixture(scope="module")
def net():
    return load_network(DATA / "case_study_activities.csv")


@pytest.fixture(scope="module")
def risks():
    return load_risks(DATA / "risk_register.csv")


def test_npv_matches_hand_formula():
    cf = np.array([[-1000.0, 300.0, 400.0, 500.0]])
    r = monthly_rate(0.12)
    hand = -1000 + 300 / (1 + r) + 400 / (1 + r) ** 2 + 500 / (1 + r) ** 3
    assert npv(cf, 0.12)[0] == pytest.approx(hand)


def test_irr_simple_case():
    # -100 now, +110 next month: monthly IRR 10%, annual (1.1^12 - 1)
    assert irr(np.array([[-100.0, 110.0]]))[0] == pytest.approx(1.1 ** 12 - 1, rel=1e-6)


def test_irr_is_nan_without_sign_change():
    assert np.isnan(irr(np.array([[100.0, 50.0, 20.0]]))[0])


def test_spread_keeps_total_and_splits_across_months():
    out = spread_to_months(np.array([[15.0]]), np.array([[30.0]]), np.array([[90.0]]), 3)
    assert out.sum() == pytest.approx(90.0)
    assert out[0, 1] == pytest.approx(45.0) and out[0, 2] == pytest.approx(45.0)


def test_plan_spend_equals_plan_cost(net):
    _, table = deterministic_finance(net, INPUTS)
    expected = plan_cost(net, INPUTS["overhead_per_month_lakh"])
    assert (table["spend"].sum() + table["overheads"].sum()) == pytest.approx(expected, rel=1e-9)


def test_debt_is_fully_repaid_and_interest_reconciles(net):
    _, t = deterministic_finance(net, INPUTS)
    assert t["debt_balance"].iloc[-1] == pytest.approx(0.0, abs=1e-9)
    assert t["debt_repay"].sum() == pytest.approx(t["debt_draw"].sum() + t["interest"].sum())
    assert t["equity_cf"].sum() == pytest.approx(t["project_cf"].sum() - t["interest"].sum())


def test_land_is_paid_by_equity(net):
    _, t = deterministic_finance(net, INPUTS)
    assert t.loc[0, "debt_draw"] == 0.0
    assert t.loc[0, "equity_cf"] == pytest.approx(-(INPUTS["land_cost_lakh"] + INPUTS["approvals_cost_lakh"]))


def test_delay_lowers_npv():
    start, dur, cost = np.array([[0.0]]), np.array([[300.0]]), np.array([[1000.0]])
    fast = build_cashflows(start, dur, cost, np.array([300.0]), np.array([0.0]), INPUTS, n_months=40)
    slow = build_cashflows(start, dur * 1.3, cost, np.array([390.0]), np.array([0.0]), INPUTS, n_months=40)
    assert npv(slow["project_cf"], 0.12)[0] < npv(fast["project_cf"], 0.12)[0]


def test_flat10_plan_has_lower_npv(net):
    p, _ = deterministic_finance(net, INPUTS)
    p10, _ = deterministic_finance(net, INPUTS, cost_multiplier=1.10)
    assert p10["project_npv_lakh"] < p["project_npv_lakh"]


def test_ladder_first_step_is_deterministic(net, risks):
    lad = model_ladder(net, {}, risks, INPUTS["overhead_per_month_lakh"], n_iter=2_000, seed=1)
    from engine.cpm import deterministic_cpm
    assert lad.iloc[0]["duration_P80_days"] == pytest.approx(deterministic_cpm(net, net.dur_m)["duration"])
    assert lad.iloc[-1]["duration_P80_days"] >= lad.iloc[2]["duration_P80_days"]


def test_mitigation_with_no_change_has_zero_effect(net, risks):
    """Common random numbers: an unchanged risk and a free fix must give exactly zero difference."""
    rid = risks["id"].iloc[1]
    p = float(risks["probability"].iloc[1])
    out = evaluate_mitigation(net, None, risks, rid, p, 1.0, 0.0, INPUTS, n_iter=2_000, seed=3)
    assert out["npv_gain_lakh"] == pytest.approx(0.0, abs=1e-9)


def test_removing_a_risk_never_lengthens_the_project(net, risks):
    full = run_simulation(net, n_iter=2_000, seed=4, risks=risks)
    off = risks.copy(); off.loc[off.index[1], "probability"] = 0.0
    less = run_simulation(net, n_iter=2_000, seed=4, risks=off)
    assert (less.project_duration <= full.project_duration + 1e-9).all()


def test_zero_delay_costs_nothing(net):
    from engine.analysis import cost_of_delay
    t = cost_of_delay(net, INPUTS, net.ids[-1], (0,))
    assert t.loc[0, "npv_loss_lakh"] == pytest.approx(0.0, abs=1e-9)


def test_delay_within_float_does_not_move_finish(net):
    from engine.analysis import cost_of_delay
    from engine.cpm import deterministic_cpm
    plan = deterministic_cpm(net, net.dur_m)
    i = int(np.argmax(plan["float"]))                     # activity with the most float
    d = float(plan["float"][i]) * 0.5
    t = cost_of_delay(net, INPUTS, net.ids[i], (0, d))
    assert t.loc[1, "project_delay_days"] == pytest.approx(0.0, abs=1e-9)


def test_buyer_compensation_only_when_switched_on(net):
    from engine.analysis import cost_of_delay
    last = net.ids[-1]
    off = cost_of_delay(net, dict(INPUTS, rera_delay_interest_annual=0.0), last, (0, 90))
    on = cost_of_delay(net, dict(INPUTS, rera_delay_interest_annual=0.10, rera_grace_months=0), last, (0, 90))
    assert off.loc[1, "buyer_compensation_lakh"] == 0.0
    assert on.loc[1, "buyer_compensation_lakh"] > 0.0
    assert on.loc[1, "npv_loss_lakh"] > off.loc[1, "npv_loss_lakh"]
