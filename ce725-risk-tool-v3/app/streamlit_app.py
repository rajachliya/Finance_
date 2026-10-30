"""Construction schedule and cost risk tool. Run from the repo root:
    streamlit run app/streamlit_app.py
"""
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "app"))

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from charts import gantt_chart, gantt_frame, ladder_chart
from engine import NetworkError, activity_table, baseline_comparison, build_network, percentiles, run_simulation
from engine.analysis import (contingency_summary, cost_of_delay, evaluate_mitigation, model_ladder,
                             npv_loss_per_month_from_simulation, risk_contributions)
from engine.risks import validate_risks
from finance.cashflow import deterministic_finance, promised_month_for, run_finance

DATA = ROOT / "data"
st.set_page_config(page_title="Schedule & Cost Risk Toolkit", page_icon="🏗️", layout="wide")
import ui  # noqa: E402  (presentation only)
ui.setup()


@st.cache_data
def read_csv(path):
    return pd.read_csv(path)


@st.cache_data(show_spinner="Running simulation...")
def simulate(acts, risks, rho, n_iter, seed, dist, inputs):
    net = build_network(acts)
    res = run_simulation(net, n_iter=n_iter, seed=seed, distribution=dist, rho_by_group=rho, risks=risks,
                         overhead_per_month_lakh=inputs["overhead_per_month_lakh"])
    fin, flows = run_finance(res, inputs, promised_month=promised_month_for(net, inputs))
    return net, res, fin, flows


@st.cache_data(show_spinner="Working out the cost of delay...")
def cached_delay(acts, inputs, activity_id, delays):
    return cost_of_delay(build_network(acts), inputs, activity_id, delays)


@st.cache_data(show_spinner="Building the model ladder...")
def cached_ladder(acts, rho, risks, overhead, n_iter, seed):
    return model_ladder(build_network(acts), rho, risks, overhead, n_iter, seed)


@st.cache_data(show_spinner="Testing each risk...")
def cached_contrib(acts, rho, risks, overhead, n_iter, seed):
    return risk_contributions(build_network(acts), rho, risks, overhead, n_iter, seed)


@st.cache_data(show_spinner="Comparing with and without the fix...")
def cached_mitigation(acts, rho, risks, rid, p, scale, cost, inputs, n_iter, seed):
    return evaluate_mitigation(build_network(acts), rho, risks, rid, p, scale, cost, inputs, n_iter, seed)


# ---------------- Sidebar ----------------
ui.sidebar_brand()
st.sidebar.header("Project data")
dataset = st.sidebar.radio("Activities", ["Case study (G+10 residential)", "Upload CSV"])
if dataset.startswith("Case"):
    acts = read_csv(DATA / "case_study_activities.csv")
else:
    up = st.sidebar.file_uploader("Activity CSV (same columns as the case study file)", type="csv")
    if up is None:
        st.info("Upload an activity CSV, or choose the case study.")
        st.stop()
    acts = pd.read_csv(up)
start_date = st.sidebar.date_input("Construction start date", dt.date(2027, 1, 1))

st.sidebar.header("Simulation")
n_iter = st.sidebar.select_slider("Iterations", [1_000, 5_000, 10_000, 20_000], value=10_000)
seed = int(st.sidebar.number_input("Random seed (same seed gives same results)", value=42, step=1))
dist = st.sidebar.radio("Distribution", ["pert", "triangular"], format_func=str.capitalize, horizontal=True)
use_corr = st.sidebar.toggle("Activities in the same group slip together", value=True)
use_risks = st.sidebar.toggle("Include risk events", value=True)

base_inputs = json.loads((DATA / "finance_inputs.json").read_text())
with st.sidebar.expander("Finance inputs"):
    inputs = {}
    fields = [("land_cost_lakh", "Land cost (₹ lakh)", 1.0), ("approvals_cost_lakh", "Approvals (₹ lakh)", 1.0),
              ("saleable_area_sqft", "Saleable area (sq ft)", 1.0), ("sale_price_per_sqft_inr", "Sale price (₹ per sq ft)", 1.0),
              ("presale_share", "Share sold before completion", 0.05), ("months_to_sell_after_completion", "Months to sell the rest", 1.0),
              ("brokerage_pct", "Brokerage (share of sales)", 0.005), ("debt_share", "Loan share of funding gap", 0.05),
              ("interest_rate_annual", "Loan interest rate (per year)", 0.005), ("discount_rate_annual", "Discount rate, project (per year)", 0.005),
              ("equity_discount_rate_annual", "Cost of equity (per year)", 0.005), ("overhead_per_month_lakh", "Site overheads (₹ lakh per month)", 0.5),
              ("rera_delay_interest_annual", "Compensation to buyers for late possession (per year, 0 = off)", 0.005),
              ("rera_grace_months", "Grace months before compensation starts", 1.0)]
    for key, label, step in fields:
        inputs[key] = float(st.number_input(label, value=float(base_inputs.get(key, 0.0)), step=step, key=key))
    inputs["months_to_sell_after_completion"] = int(inputs["months_to_sell_after_completion"])

rho = dict(read_csv(DATA / "correlation_groups.csv")[["group", "rho"]].values) if use_corr else None
risks = read_csv(DATA / "risk_register.csv") if use_risks else None

# ---------------- Run ----------------
try:
    net, res, fin, flows = simulate(acts, risks, rho, n_iter, seed, dist, inputs)
except NetworkError as e:
    st.error(f"The activity data has a problem: {e}")
    st.stop()
if risks is not None and (problems := validate_risks(risks, net)):
    st.error("Risk register problems: " + "; ".join(problems))
    st.stop()

base = baseline_comparison(net)
pdur, pcost = percentiles(res.project_duration), percentiles(res.project_cost)
cont = contingency_summary(net, res, inputs["overhead_per_month_lakh"], fin, inputs)
table = activity_table(net, res)

plan_m = base["most_likely_duration"] / 30
prob_plan = float((res.project_duration <= base["most_likely_duration"]).mean())

ui.hero(res.project_duration, base["most_likely_duration"], pdur["P80"], prob_plan, cont["contingency_P80_pct"])

ui.kpi_grid([
    dict(label="Plan", value=f"{plan_m:.1f}", unit="months", chip="most-likely durations", tone="neutral", accent="#8A96A3",
         help="The finish date if every activity takes its most likely time. This is what a normal schedule shows."),
    dict(label="P50 finish · 50% sure", value=f"{pdur['P50'] / 30:.1f}", unit="months", chip="a coin flip", tone="neutral", accent="#2F7F7A",
         help="Half of the simulated runs finished by this date. Committing to it means being late half the time."),
    dict(label="P80 finish · 80% sure", value=f"{pdur['P80'] / 30:.1f}", unit="months",
         chip=f"+{(pdur['P80'] - base['most_likely_duration']) / 30:.1f} months vs plan", tone="bad", accent="#E8772E",
         help="8 out of 10 runs finished by this date. A common level for committing to a date or a budget."),
    dict(label="P90 finish · 90% sure", value=f"{pdur['P90'] / 30:.1f}", unit="months", chip="cautious commitment", tone="neutral", accent="#14202B",
         help="9 out of 10 runs finished by this date. A cautious level, for when lateness is very costly."),
    dict(label="Base cost estimate", value=f"₹{cont['base_estimate_lakh']:,.0f}", unit="lakh", chip="everything to plan", tone="neutral", accent="#8A96A3",
         help="Cost if every activity takes its most likely time and cost and no risk happens, including site overheads."),
    dict(label="P80 cost · 80% sure", value=f"₹{cont['P80_cost_lakh']:,.0f}", unit="lakh", chip="budget you can defend", tone="neutral", accent="#2F7F7A",
         help="8 out of 10 runs cost this much or less."),
    dict(label="Contingency at P80", value=f"{cont['contingency_P80_pct']:.1%}",
         chip=f"{cont['contingency_P80_pct'] - 0.10:+.1%} vs flat 10%", tone="bad" if cont["contingency_P80_pct"] > 0.10 else "good", accent="#E8772E",
         help="Extra money to add to the base estimate to be 80% sure the budget is enough: P80 cost ÷ base estimate − 1."),
    dict(label="Flat 10% falls short", value=f"{cont['prob_cost_exceeds_flat10']:.0%}", unit="of runs",
         chip="rule-of-thumb check", tone="bad" if cont["prob_cost_exceeds_flat10"] > 0.2 else "neutral", accent="#14202B",
         help="Share of runs where the cost went above the base estimate plus 10%."),
])
ui.plain_words(f"<b>In plain words:</b> the plan says {plan_m:.1f} months, but only {prob_plan:.1%} of runs finished that fast. "
               f"To be 80% sure, allow <b>{pdur['P80'] / 30:.1f} months</b> and a contingency of <b>{cont['contingency_P80_pct']:.1%}</b>. "
               "New here? Open the <b>Start here</b> tab.")

(t_start, t_dist, t_gantt, t_drivers, t_fin, t_mit, t_ladder, t_inputs) = st.tabs(
    ["Start here", "Distributions", "Gantt", "Delay drivers", "Finance and contingency", "Mitigation", "Model ladder", "Inputs"])


def takeaway(text):
    st.markdown(f"**What this run shows:** {text}")


def how_to_read(text, label="How to read this chart"):
    with st.expander(label):
        st.markdown(text)


def hist_cdf(x, title, unit):
    xs = np.sort(x)
    fig = go.Figure()
    fig.add_histogram(x=x, nbinsx=60, name="Number of runs", marker=dict(color="rgba(20,32,43,0.55)", line=dict(color="rgba(20,32,43,0.75)", width=0.5)))
    fig.add_scatter(x=xs, y=np.arange(1, len(xs) + 1) / len(xs), name="Chance of finishing within (right axis)", yaxis="y2", line=dict(color="#E8772E", width=3))
    for p in ("P50", "P80", "P90"):
        fig.add_vline(x=np.percentile(x, int(p[1:])), line_dash="dot", line_color="#A84A14" if p == "P80" else "#8A96A3", annotation_text=p)
    fig.update_layout(title=title, xaxis_title=unit, yaxis_title="Number of runs", height=400, legend=dict(orientation="h"),
                      yaxis2=dict(overlaying="y", side="right", range=[0, 1], tickformat=".0%"))
    return fig


with t_start:
    st.subheader("What this tool does")
    st.markdown(
        "A normal schedule gives one finish date and one cost. Real projects rarely go exactly to plan: activities run "
        "long or short, risk events happen, and bad weather or a stretched crew can delay several activities at once. "
        "This tool plays the project out **thousands of times**, each time with different but realistic luck, and counts "
        "how often each finish date, cost and profit happened. That tells you how much time and money to allow, which "
        "activities and risks matter most, and what delay does to the project's value.")
    st.subheader("Key words in plain language")
    st.markdown("""
| Term | What it means |
| --- | --- |
| Three-point estimate | Three guesses for each activity: **optimistic** (best realistic case), **most likely**, and **pessimistic** (worst realistic case). |
| PERT | A standard way to turn the three guesses into a range of possible values. Most draws fall near the most-likely value, a few near the extremes. The PERT average is (optimistic + 4 × most likely + pessimistic) ÷ 6. |
| Simulation run | One imagined version of the project, with a duration and cost drawn for every activity. The tool does 10,000 of them. |
| P50 | Half the runs finished within this value. A coin flip. |
| P80 | 8 out of 10 runs finished within this value. A common level for committing to a date or budget. |
| P90 | 9 out of 10 runs finished within this value. A cautious level. |
| Critical path | The chain of activities that sets the finish date. If any of them is late, the whole project is late. |
| Float | How many days an activity can slip without delaying the finish. Critical activities have zero float. |
| Criticality index | How often (out of all runs) an activity was on the critical path. 90% means it almost always mattered. |
| Activities that slip together | Activities affected by the same cause (monsoon, same crew, same supplier) tend to run late at the same time. The tool links them (correlation). |
| Risk event | Something that may or may not happen, such as an approval delay, with a chance and a delay if it does. |
| Contingency | Extra time or money added to the plan to cover what might go wrong. |
| NPV (net present value) | The project's profit in today's money: future money is worth less than money now, so later cash is discounted. |
| IRR (internal rate of return) | The yearly return the project earns on the money put in. Higher is better. |
| Interest during construction | Interest on the construction loan that builds up before the project earns money. Delay makes it larger. |
| Lakh | ₹1,00,000. ₹100 lakh = ₹1 crore. |
""")
    st.subheader("Which tab answers which question")
    st.markdown("""
| Question | Tab |
| --- | --- |
| How long will it really take, and what will it really cost? | Distributions |
| Which activities could slip, and by how much? | Gantt |
| What drives the delay most? | Delay drivers |
| What contingency do I need? What is the project worth? What does delay cost? | Finance and contingency |
| Is it worth paying to reduce a risk? | Mitigation |
| Why does the simulation give a later date than the plan? | Model ladder |
| What data is the tool using? | Inputs |
""")
    st.subheader("A two-minute tour")
    st.markdown(
        "1. Read the headline numbers at the top: the plan date against the P80 date, and the contingency needed against 10%.\n"
        "2. **Distributions:** see the full range of finish dates and costs.\n"
        "3. **Gantt:** find the red activities that almost always decide the finish.\n"
        "4. **Finance and contingency:** compare the plan's NPV with the NPV you can count on, and try a delay.\n"
        "5. **Mitigation:** test whether reducing the biggest risk pays for itself.\n\n"
        "Hover over any number or chart for details. Every chart has a **How to read this chart** box under it.")

with t_dist:
    ui.section("Commitment checker", "Pick a date and a budget. See your odds.",
               "Slide to any finish date or budget to read the chance of meeting it, straight from the 10,000 runs.")
    m_lo, m_hi = float(np.percentile(res.project_duration, 1) / 30), float(np.percentile(res.project_duration, 99) / 30)
    c_lo, c_hi = float(np.percentile(res.project_cost, 1)), float(np.percentile(res.project_cost, 99))
    cc = st.columns(2)
    target_m = cc[0].slider("Target finish (months)", round(min(m_lo, plan_m) - 0.5, 1), round(m_hi + 0.5, 1),
                            round(pdur["P80"] / 30, 1), 0.1, format="%.1f months")
    flat10 = cont["flat10_budget_lakh"]
    target_c = cc[1].slider("Budget (₹ lakh)", float(np.floor(min(c_lo, cont["base_estimate_lakh"]) / 10) * 10),
                            float(np.ceil(c_hi / 10) * 10), float(np.round(flat10 / 10) * 10), 10.0, format="₹%.0f lakh",
                            help="Starts at the base estimate plus a flat 10%.")
    p_date = float((res.project_duration <= target_m * 30).mean() * 100)
    p_budget = float((res.project_cost <= target_c).mean() * 100)
    cc[0].plotly_chart(ui.gauge(p_date, f"Chance of finishing within {target_m:.1f} months"), width="stretch")
    cc[1].plotly_chart(ui.gauge(p_budget, f"Chance of staying within ₹{target_c:,.0f} lakh"), width="stretch")
    st.caption("The orange tick marks 80%, the level most teams commit to.")
    ui.section("Distributions", "The full range of outcomes")
    st.plotly_chart(hist_cdf(res.project_duration, "Project duration", "days"), width="stretch")
    takeaway(f"half the runs finished within {pdur['P50'] / 30:.1f} months and 8 in 10 within {pdur['P80'] / 30:.1f} months. "
             f"The plan of {plan_m:.1f} months was met in only {prob_plan:.1%} of runs.")
    how_to_read(
        "- Each **bar** counts how many of the runs finished in that range of days. Tall bars are common outcomes.\n"
        "- The **rising line** (right-hand scale) is the running total: pick a number of days on the bottom, go up to the line, "
        "and read across to the right to get the chance of finishing by then.\n"
        "- The **dotted lines** mark P50, P80 and P90.\n"
        "- A **wide** spread means an uncertain project. A long tail to the right means a few runs went very badly.")
    st.plotly_chart(hist_cdf(res.project_cost, "Construction cost", "₹ lakh"), width="stretch")
    takeaway(f"8 in 10 runs cost ₹{cont['P80_cost_lakh']:,.0f} lakh or less, {cont['contingency_P80_pct']:.1%} above the base "
             f"estimate of ₹{cont['base_estimate_lakh']:,.0f} lakh.")
    how_to_read(
        "Read it the same way as the duration chart, but in money. Cost includes activity costs, site overheads for "
        "however long the project took, and the cost of any risk events that happened. That is why longer runs also cost more.")

with t_gantt:
    ui.section("Gantt", "Where the schedule could slip")
    slip_p = st.radio("Show possible slip up to", [50, 80, 90], index=1, horizontal=True, format_func=lambda p: f"P{p}")
    gdf = gantt_frame(net, res, table["criticality_index"].to_numpy(), start_date, slip_p)
    st.plotly_chart(gantt_chart(gdf, slip_p), width="stretch")
    hot = table[table["criticality_index"] >= 0.8]
    takeaway(f"{len(hot)} of {net.n} activities were on the critical path in at least 8 of 10 runs. These have no room to "
             "slip, so they deserve the closest watch.")
    how_to_read(
        "- Each **coloured bar** is an activity in the plan, from its planned start to its planned finish.\n"
        "- The **colour** shows how often it was on the critical path: red almost always, orange sometimes, blue rarely.\n"
        f"- The **grey bar** after it shows how much later it finished in {slip_p}% of runs. Change P50, P80 or P90 above.\n"
        "- Hover over a bar to see its dates, how often it was critical and its float (spare days).")

with t_drivers:
    ui.section("Delay drivers", "What really causes the delay")
    top = table.sort_values("cruciality", ascending=False).head(12).iloc[::-1]
    fig = go.Figure(go.Bar(x=top["spearman_with_project"], y=top["id"] + " " + top["activity"], orientation="h",
                           marker=dict(color=top["spearman_with_project"], colorscale=[[0, "#F2D3BC"], [1, "#E8772E"]], line=dict(width=0))))
    fig.update_layout(title="Activities most linked to project delay", xaxis_title="Link with project duration (0 = none, 1 = moves exactly with it)", height=450)
    st.plotly_chart(fig, width="stretch")
    lead = table.sort_values("cruciality", ascending=False).head(3)
    takeaway("the activities most linked to a late finish are " + ", ".join(f"{r.id} {r.activity}" for r in lead.itertuples()) + ".")
    how_to_read(
        "- A **longer bar** means that when this activity runs long, the whole project tends to run long too.\n"
        "- The value runs from 0 (no link) to 1 (moves exactly with the project). It is a rank correlation.\n"
        "- In the table: **criticality index** = how often the activity was on the critical path; **link with project** = "
        "the bar's value; **cruciality** = the two multiplied, the best single ranking of what to manage first.")
    st.dataframe(table.sort_values("cruciality", ascending=False).round(3), hide_index=True, width="stretch")
    if risks is not None:
        st.subheader("How much each risk adds")
        if st.button("Test each risk (takes about 15 seconds)"):
            st.session_state["contrib"] = cached_contrib(acts, rho, risks, inputs["overhead_per_month_lakh"], n_iter, seed)
        if "contrib" in st.session_state:
            st.dataframe(st.session_state["contrib"].round(2), hide_index=True, width="stretch")
            how_to_read(
                "Each row switches off **one** risk, keeps everything else the same, and shows how much P80 duration and "
                "cost fall. The biggest numbers are the risks most worth reducing. A risk on an activity with spare days "
                "(float) can add zero days, because the delay is absorbed.", "How to read this table")

with t_fin:
    ui.section("Finance and contingency", "What the project is really worth")
    c = st.columns(3)
    c[0].metric("NPV of the plan", f"₹{cont['plan_npv_lakh']:,.0f} lakh",
                help="Project value in today's money if everything goes exactly to plan.")
    c[1].metric("NPV of plan + flat 10%", f"₹{cont['plan_plus_flat10_npv_lakh']:,.0f} lakh",
                help="Value if costs are simply 10% higher than plan, the usual rule of thumb.")
    c[2].metric("Simulated median NPV", f"₹{cont['sim_P50_npv_lakh']:,.0f} lakh",
                help="Half the runs gave more than this, half less.")
    c = st.columns(3)
    c[0].metric("NPV with 80% confidence", f"₹{cont['npv_80pct_confidence_lakh']:,.0f} lakh",
                help="8 out of 10 runs gave at least this value. The figure to rely on when deciding.")
    c[1].metric("Chance NPV is negative", f"{cont['prob_npv_negative']:.1%}", help="Share of runs where the project lost value.")
    c[2].metric("Median interest during construction", f"₹{cont['sim_P50_idc_lakh']:,.0f} lakh", f"plan: ₹{cont['plan_idc_lakh']:,.0f} lakh",
                delta_color="off", help="Loan interest that builds up before completion. Delay keeps the loan open longer.")
    c = st.columns(2)
    c[0].metric("Project IRR: plan vs median", f"{cont['plan_project_irr']:.1%} → {cont['sim_P50_project_irr']:.1%}",
                help="Yearly return on all money put in, in the plan and in a typical (median) run.")
    c[1].metric("Equity IRR: plan vs median", f"{cont['plan_equity_irr']:.1%} → {cont['sim_P50_equity_irr']:.1%}",
                help="Yearly return on the developer's own money, after the loan.")
    fig = go.Figure(go.Histogram(x=fin["project_npv_lakh"], nbinsx=60, marker=dict(color="rgba(47,127,122,0.65)")))
    fig.add_vline(x=cont["plan_npv_lakh"], line_dash="dash", annotation_text="Plan")
    fig.add_vline(x=0, line_color="#C2410C", line_width=2)
    fig.update_layout(title="Project NPV across all runs", xaxis_title="₹ lakh", yaxis_title="Number of runs", height=380)
    st.plotly_chart(fig, width="stretch")
    takeaway(f"8 in 10 runs gave an NPV of at least ₹{cont['npv_80pct_confidence_lakh']:,.0f} lakh, against ₹{cont['plan_npv_lakh']:,.0f} lakh "
             f"in the plan. The project lost value in {cont['prob_npv_negative']:.1%} of runs.")
    how_to_read(
        "- Each bar counts the runs whose NPV fell in that range.\n"
        "- The **dashed line** is the plan's NPV. Most runs sit to its left, because delays and overruns reduce value.\n"
        "- The **red line** is zero: runs to its left lost money in today's terms.")
    st.subheader("Contingency")
    st.dataframe(pd.DataFrame({
        "Budget basis": ["Base estimate", "Flat 10%", "P50", "P80", "P90"],
        "Budget (₹ lakh)": [cont["base_estimate_lakh"], cont["flat10_budget_lakh"], cont["P50_cost_lakh"], cont["P80_cost_lakh"], cont["P90_cost_lakh"]],
        "Contingency": [0, 0.10, cont["contingency_P50_pct"], cont["contingency_P80_pct"], cont["contingency_P90_pct"]],
    }).style.format({"Budget (₹ lakh)": "{:,.0f}", "Contingency": "{:.1%}"}), hide_index=True)
    how_to_read(
        "Each row is a way of setting the budget. **Contingency** is how much it adds above the base estimate. "
        "Choose the confidence level you need (P80 is common), and compare its contingency with the flat 10% many projects use.",
        "How to read this table")
    st.subheader("Cost of delay")
    st.write(f"Across all runs, each extra month of duration goes with about "
             f"**₹{npv_loss_per_month_from_simulation(res, fin):,.0f} lakh** less NPV on average (including the extra costs that come with delay).")
    last = [net.ids[i] for i in range(net.n) if not net.succs[i]]
    c = st.columns([2, 1])
    act = c[0].selectbox("Delayed activity", net.ids, index=net.ids.index(last[0]),
                         format_func=lambda i: f"{i}: {net.names[net.ids.index(i)]}")
    days = c[1].slider("Delay (days)", 0, 180, 60, 5)
    delays = tuple(sorted(set([0, 15, 30, 60, 90, 120, 150, 180, days])))
    dt_ = cached_delay(acts, inputs, act, delays)
    row = dt_[dt_["delay_days"] == days].iloc[0]
    c = st.columns(4)
    c[0].metric("Finish moves by", f"{row['project_delay_days']:.0f} days",
                help="Can be less than the delay if the activity has spare days (float).")
    c[1].metric("NPV loss", f"₹{row['npv_loss_lakh']:,.1f} lakh", help="Fall in project value in today's money.")
    c[2].metric("Loss per day of delay", f"₹{row['npv_loss_per_day_lakh']:,.2f} lakh")
    c[3].metric("Equity IRR", f"{row['equity_irr']:.1%}", help="Return on the developer's own money with this delay.")
    parts = pd.DataFrame({"Part": ["Extra construction and overhead cost", "Extra loan interest", "Compensation to buyers",
                                   "Later sales cash and other timing (approx.)"],
                          "₹ lakh": [row["extra_construction_cost_lakh"], row["extra_interest_lakh"],
                                     row["buyer_compensation_lakh"], row["later_sales_and_timing_lakh"]]})
    c = st.columns(2)
    c[0].dataframe(parts.style.format({"₹ lakh": "{:,.1f}"}), hide_index=True, width="stretch")
    fig = go.Figure(go.Scatter(x=dt_["delay_days"], y=dt_["npv_loss_lakh"], mode="lines+markers", line=dict(color="#E8772E", width=3),
                                marker=dict(size=8, color="#14202B"), fill="tozeroy", fillcolor="rgba(232,119,46,0.12)"))
    fig.update_layout(title="NPV loss by length of delay", xaxis_title="Delay (days)", yaxis_title="₹ lakh", height=320)
    c[1].plotly_chart(fig, width="stretch")
    how_to_read(
        "Pick an activity and a delay. The tool reruns the **plan** with that delay and shows what it costs, split into "
        "its parts. Delay hurts twice: building costs more (site overheads, equipment, loan interest) and sales money "
        "arrives later, which is worth less in today's terms. The line shows how the loss grows with longer delays. "
        "A delay on an activity with spare days does not move the finish until those days are used up. Completion is "
        "counted in whole months, so small delays can show steps.", "How to read the cost of delay")
    with st.expander("Monthly cash flow of the plan (for checking against Excel)"):
        _, plan_table = deterministic_finance(net, inputs)
        st.dataframe(plan_table.round(2), width="stretch")

with t_mit:
    ui.section("Mitigation", "Is this fix worth paying for?")
    if risks is None:
        st.info("Switch on risk events in the sidebar to test a mitigation.")
    else:
        rid = st.selectbox("Risk to reduce", risks["id"], format_func=lambda i: f"{i}: {risks.set_index('id').loc[i, 'name']}")
        cur = float(risks.set_index("id").loc[rid, "probability"])
        c = st.columns(3)
        new_p = c[0].slider("Probability after the fix", 0.0, 1.0, round(cur / 2, 2), 0.01, help=f"Currently {cur:.0%}")
        scale = c[1].slider("Impact after the fix (share of current)", 0.0, 1.0, 1.0, 0.05,
                            help="1 = the delay and cost if it happens are unchanged; 0.5 = halved.")
        fix_cost = c[2].number_input("Cost of the fix (₹ lakh, paid at start)", value=20.0, step=5.0)
        out = cached_mitigation(acts, rho, risks, rid, new_p, scale, fix_cost, inputs, n_iter, seed)
        verdict = "is worth it" if out["worth_it"] else "is not worth it"
        st.subheader(f"The fix {verdict}: mean NPV changes by ₹{out['npv_gain_lakh']:,.1f} lakh")
        st.write(f"Paying up to **₹{out['max_worth_paying_lakh']:,.1f} lakh** for this fix still improves expected NPV.")
        st.dataframe(out["table"].style.format({"without fix": "{:,.2f}", "with fix": "{:,.2f}", "change": "{:+,.2f}"}), hide_index=True, width="stretch")
        how_to_read(
            "A **fix** is anything that makes a risk less likely or less damaging, such as applying for approvals early or "
            "booking extra labour. The tool runs the project twice, **with the same luck in every run**, once without and "
            "once with the fix, so the only difference is the fix itself. If the average NPV goes up after paying for the "
            "fix, it is worth it. \"Worth paying up to\" is the most the fix could cost and still pay off.",
            "How to read this result")

with t_ladder:
    ui.section("Model ladder", "Why a normal plan is so optimistic")
    lad = cached_ladder(acts, rho if rho else {}, risks, inputs["overhead_per_month_lakh"], n_iter, seed)
    c = st.columns(2)
    c[0].plotly_chart(ladder_chart(lad, "duration_P80_days", "days"), width="stretch")
    c[1].plotly_chart(ladder_chart(lad, "cost_P80_lakh", "₹ lakh"), width="stretch")
    steps = np.diff(lad["duration_P80_days"].to_numpy())
    big = int(np.argmax(steps)) + 1
    takeaway(f"the plan says {lad['duration_P80_days'].iloc[0]:.0f} days; the full model's P80 is {lad['duration_P80_days'].iloc[-1]:.0f} days. "
             f"The biggest jump comes from \"{lad['step'].iloc[big].split('. ', 1)[1]}\" (+{steps.max():.0f} days).")
    how_to_read(
        "This chart explains **why** the simulation gives a later date than the plan, by adding realism one layer at a time:\n"
        "1. **Plan:** every activity at its most likely duration.\n"
        "2. **PERT on one path:** uses each activity's PERT average, which is usually longer than its most likely value.\n"
        "3. **Simulation:** plays the project out thousands of times. Parallel paths can overtake each other, which "
        "pushes the finish later (\"merge bias\").\n"
        "4. **Correlated activities:** delays with a shared cause stop cancelling out.\n"
        "5. **Risk events:** approval delays, labour shortages and the like.\n\n"
        "Each bar is the extra time (or cost) that layer adds. The last bar is the final P80.")
    st.dataframe(lad.round(1), hide_index=True, width="stretch")
    st.caption("Steps 1 and 2 are single answers, so P50 and P80 are the same. Steps 3 to 5 come from the simulation. "
               "If correlation or risks are switched off in the sidebar, those steps show no change.")

with t_inputs:
    ui.section("Inputs", "The data behind every number")
    st.caption("Check these are your verified values before using any result.")
    st.subheader("Activities"); st.dataframe(acts, hide_index=True, width="stretch")
    st.subheader("Risk register"); st.dataframe(read_csv(DATA / "risk_register.csv"), hide_index=True, width="stretch")
    st.subheader("Correlation groups"); st.dataframe(read_csv(DATA / "correlation_groups.csv"), hide_index=True, width="stretch")
    st.subheader("Finance inputs used"); st.json(inputs)

ui.footer()
