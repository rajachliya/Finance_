"""Charts for the Streamlit app: Gantt with possible slip, and the model ladder waterfall."""
from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from engine.cpm import deterministic_cpm

CRIT_COLOURS = {"Critical in most runs (80%+)": "#C2410C",
                "Sometimes critical (20-80%)": "#F0B35B",
                "Rarely critical (<20%)": "#2F7F7A"}
SLIP_COLOUR = "rgba(20,32,43,0.18)"


def gantt_frame(net, res, crit_index: np.ndarray, start: dt.date, slip_percentile: int = 80) -> pd.DataFrame:
    """Planned bars (most-likely durations) plus how far each activity's finish could slip."""
    plan = deterministic_cpm(net, net.dur_m)
    ef_sim = res.es + res.durations
    slip_finish = np.percentile(ef_sim, slip_percentile, axis=0)
    def bucket(c):
        return ("Critical in most runs (80%+)" if c >= 0.8 else
                "Sometimes critical (20-80%)" if c >= 0.2 else "Rarely critical (<20%)")
    rows = []
    for i, aid in enumerate(net.ids):
        rows.append(dict(id=aid, activity=f"{aid} {net.names[i]}", plan_start=plan["es"][i], plan_finish=plan["ef"][i],
                         slip_finish=max(slip_finish[i], plan["ef"][i]), criticality=crit_index[i],
                         category=bucket(crit_index[i]), float_days=plan["float"][i]))
    df = pd.DataFrame(rows)
    to_date = lambda d: pd.Timestamp(start) + pd.to_timedelta(d, unit="D")
    for c in ["plan_start", "plan_finish", "slip_finish"]:
        df[c + "_date"] = df[c].map(to_date)
    return df


def gantt_chart(df: pd.DataFrame, slip_percentile: int = 80) -> go.Figure:
    fig = go.Figure()
    ms_per_day = 86_400_000
    for cat, colour in CRIT_COLOURS.items():
        d = df[df["category"] == cat]
        if d.empty:
            continue
        fig.add_bar(y=d["activity"], base=d["plan_start_date"], x=(d["plan_finish"] - d["plan_start"]) * ms_per_day,
                    orientation="h", marker_color=colour, name=cat,
                    customdata=np.stack([d["plan_start_date"].dt.strftime("%d %b %Y"), d["plan_finish_date"].dt.strftime("%d %b %Y"),
                                         (d["criticality"] * 100).round(0).astype(int).astype(str), d["float_days"].round(0).astype(int).astype(str)], axis=1),
                    hovertemplate="%{y}<br>Planned: %{customdata[0]} to %{customdata[1]}<br>"
                                  "Critical in %{customdata[2]}% of runs<br>Planned float: %{customdata[3]} days<extra></extra>")
    fig.add_bar(y=df["activity"], base=df["plan_finish_date"], x=(df["slip_finish"] - df["plan_finish"]) * ms_per_day,
                orientation="h", marker_color=SLIP_COLOUR, name=f"Possible slip (P{slip_percentile} finish)",
                customdata=df["slip_finish_date"].dt.strftime("%d %b %Y"),
                hovertemplate="%{y}<br>P" + str(slip_percentile) + " finish: %{customdata}<extra></extra>")
    fig.update_layout(barmode="overlay", height=max(450, 26 * len(df)), xaxis_type="date",
                      yaxis=dict(autorange="reversed"), legend=dict(orientation="h", y=-0.08),
                      margin=dict(l=10, r=10, t=40, b=10), title="Plan with possible slip")
    return fig


def ladder_chart(ladder: pd.DataFrame, column: str, unit: str) -> go.Figure:
    """Waterfall: plan first, then what each layer of realism adds, then the final answer."""
    vals = ladder[column].to_numpy()
    labels = [s.split(". ", 1)[1] for s in ladder["step"]]
    measure = ["absolute"] + ["relative"] * (len(vals) - 1) + ["total"]
    x = labels + ["Final P80" if "P80" in column else "Final"]
    y = [vals[0]] + list(np.diff(vals)) + [vals[-1]]
    fig = go.Figure(go.Waterfall(x=x, y=y, measure=measure, text=[f"{v:+,.0f}" if i and i < len(y) - 1 else f"{v:,.0f}" for i, v in enumerate(y)],
                                 textposition="outside", connector={"line": {"color": "#C9C1B1"}},
                                 increasing={"marker": {"color": "#E8772E"}}, decreasing={"marker": {"color": "#2F7F7A"}},
                                 totals={"marker": {"color": "#14202B"}}))
    lo = min(vals) * 0.97
    fig.update_layout(title=f"How the answer changes as realism is added ({unit})", yaxis=dict(range=[lo, max(vals) * 1.02], title=unit),
                      height=430, showlegend=False)
    return fig
