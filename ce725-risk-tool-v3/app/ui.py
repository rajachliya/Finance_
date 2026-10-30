"""Look and feel for the Streamlit app: brand styles, animations, hero, KPI cards and chart theme.

Presentation only. Nothing here changes a calculation.
HTML passed to st.markdown must have no indented lines (Markdown would turn them into code blocks),
so every block is built as a list of lines and joined.
"""
from __future__ import annotations

import html

import numpy as np
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

NAVY = "#14202B"
NAVY_2 = "#1E3042"
ORANGE = "#E8772E"
ORANGE_DEEP = "#A84A14"
TEAL = "#2F7F7A"
SAND = "#F6F3EC"
CARD = "#FFFFFF"
LINE = "#E3DDD0"
MUTED = "#52606D"
INK = "#1F2933"

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Oswald:wght@500;600&family=Public+Sans:wght@400;500;600;700&display=swap');

:root { --navy:#14202B; --orange:#E8772E; --orange-deep:#A84A14; --sand:#F6F3EC; --line:#E3DDD0; --muted:#52606D; --ink:#1F2933; }

.stApp { background: var(--sand); }
.stApp p, .stApp li, .stApp label, .stApp td, .stApp th, [data-testid="stMarkdownContainer"],
[data-testid="stMetricValue"], [data-testid="stMetricLabel"] { font-family: 'Public Sans', Arial, sans-serif; }
.stApp h1, .stApp h2, .stApp h3 { font-family: 'Oswald', Arial, sans-serif !important; letter-spacing: .2px; color: var(--ink); }
.block-container { padding-top: 1.6rem; max-width: 1400px; }

/* Sidebar */
[data-testid="stSidebar"] { background: #EFEAE0; border-right: 1px solid var(--line); }
[data-testid="stSidebar"] h2 { font-size: 0.95rem !important; text-transform: uppercase; letter-spacing: 2px; color: var(--orange-deep) !important; margin-top: .6rem; }
.sb-brand { display:flex; align-items:center; gap:12px; padding:14px 14px; margin:-6px 0 10px; border-radius:14px;
  background: linear-gradient(135deg, #14202B, #1E3042); color:#F4F1EA; box-shadow: 0 8px 22px rgba(20,32,43,.18); }
.sb-brand .t { font-family:'Oswald', Arial, sans-serif; font-size:1.05rem; line-height:1.1; }
.sb-brand .s { font-size:.72rem; color:#C3CCD4; letter-spacing:1px; text-transform:uppercase; }

/* Hero */
@keyframes gridpan { from { background-position: 0 0, 0 0, 0 0; } to { background-position: 0 0, 48px 48px, 48px 48px; } }
@keyframes rise { from { opacity:0; transform: translateY(14px); } to { opacity:1; transform:none; } }
@keyframes draw { from { stroke-dashoffset: 1; } to { stroke-dashoffset: 0; } }
@keyframes pop { 0% { opacity:0; transform: scale(.4); } 70% { transform: scale(1.15); } 100% { opacity:1; transform: scale(1); } }
@keyframes pulse { 0% { box-shadow: 0 0 0 0 rgba(232,119,46,.55); } 70% { box-shadow: 0 0 0 10px rgba(232,119,46,0); } 100% { box-shadow: 0 0 0 0 rgba(232,119,46,0); } }
.hero { position:relative; overflow:hidden; border-radius:22px; padding:30px 34px; color:#F4F1EA;
  background:
    linear-gradient(120deg, rgba(20,32,43,.97), rgba(30,48,66,.93)),
    repeating-linear-gradient(0deg, rgba(255,255,255,.05) 0 1px, transparent 1px 48px),
    repeating-linear-gradient(90deg, rgba(255,255,255,.05) 0 1px, transparent 1px 48px);
  animation: gridpan 18s linear infinite; box-shadow: 0 18px 40px rgba(20,32,43,.22); }
.hero-wrap { display:flex; gap:28px; align-items:center; flex-wrap:wrap; }
.hero-left { flex: 1 1 420px; animation: rise .7s ease both; }
.hero-right { flex: 1 1 420px; animation: rise .9s ease .15s both; }
.eyebrow { font-size:.78rem; font-weight:700; letter-spacing:3px; text-transform:uppercase; color:#F2A26A; }
.hero h1 { color:#F4F1EA !important; font-size:2.6rem !important; line-height:1.08 !important; margin:.35rem 0 .6rem !important; padding:0 !important; }
.hero p.sub { color:#C3CCD4; font-size:1.02rem; line-height:1.55; max-width:640px; }
.verdict { display:inline-block; margin-top:12px; padding:9px 18px; border-radius:18px; line-height:1.6;
  background: rgba(255,255,255,.08); border:1px solid rgba(255,255,255,.18); font-size:.92rem; }
.verdict b { white-space:nowrap; }
.verdict .dot { display:inline-block; vertical-align:middle; margin-right:8px; width:11px; height:11px; border-radius:50%; animation: pulse 2s infinite; }
.curve-card { background: rgba(255,255,255,.05); border:1px solid rgba(255,255,255,.12); border-radius:16px; padding:14px 16px 6px; }
.curve-card .cap { font-size:.78rem; color:#C3CCD4; letter-spacing:1px; text-transform:uppercase; }
.curve-path { stroke-dasharray: 1; stroke-dashoffset: 1; animation: draw 2.2s ease .35s forwards; }
.curve-mark { opacity:0; transform-box: fill-box; transform-origin: center; animation: pop .6s ease 2.3s forwards; }
.curve-label { opacity:0; animation: rise .6s ease 2.4s forwards; }

/* KPI cards */
.kpi-grid { display:grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap:14px; margin:18px 0 6px; }
@media (max-width: 1000px) { .kpi-grid { grid-template-columns: repeat(2, minmax(0,1fr)); } }
.kpi { position:relative; background:#FFFFFF; border:1px solid var(--line); border-radius:16px; padding:16px 18px 14px;
  box-shadow: 0 2px 10px rgba(20,32,43,.05); transition: transform .2s ease, box-shadow .2s ease; animation: rise .6s ease both; }
.kpi:hover { transform: translateY(-3px); box-shadow: 0 10px 24px rgba(20,32,43,.12); }
.kpi .bar { position:absolute; left:0; top:14px; bottom:14px; width:4px; border-radius:4px; }
.kpi .lab { font-size:.78rem; font-weight:700; color:var(--muted); letter-spacing:.6px; text-transform:uppercase; display:flex; justify-content:space-between; gap:8px; }
.kpi .lab .q { cursor:help; color:#8A96A3; font-weight:700; }
.kpi .val { font-family:'Oswald', Arial, sans-serif; font-size:2.05rem; color:var(--ink); line-height:1.15; margin-top:4px; }
.kpi .val small { font-family:'Public Sans', Arial, sans-serif; font-size:.95rem; color:var(--muted); font-weight:500; }
.kpi .chip { display:inline-block; margin-top:6px; padding:3px 10px; border-radius:999px; font-size:.78rem; font-weight:700; }
.chip-bad { background:#FCE7DA; color:#9A3A0B; }
.chip-good { background:#DDEFEC; color:#1F5F5A; }
.chip-neutral { background:#ECEFF2; color:#3E4A56; }

/* Plain-words callout */
.plain { display:flex; gap:14px; align-items:flex-start; background:#FFFFFF; border:1px solid var(--line); border-left:6px solid var(--orange);
  border-radius:14px; padding:14px 18px; margin:8px 0 18px; animation: rise .6s ease .3s both; }
.plain .ic { font-size:1.3rem; line-height:1.4; }
.plain p { margin:0; color:var(--ink); line-height:1.55; }

/* Section header inside tabs */
.sec { margin: 6px 0 10px; animation: rise .5s ease both; }
.sec .k { font-size:.74rem; font-weight:700; letter-spacing:2.5px; text-transform:uppercase; color:var(--orange-deep); }
.sec .h { font-family:'Oswald', Arial, sans-serif; font-size:1.55rem; color:var(--ink); line-height:1.2; }
.sec .d { color:var(--muted); font-size:.95rem; }

/* Tabs as pills (covers both older baseweb and newer react-aria tab markup) */
.stTabs [role="tablist"] { gap:6px !important; flex-wrap:wrap; border-bottom:none !important; box-shadow:none !important; padding:4px 0 10px; }
.stTabs [role="tab"] { background:#FFFFFF; border:1px solid var(--line); border-radius:999px; padding:7px 14px !important; height:auto;
  margin:0 !important; transition: background .2s ease, transform .15s ease, box-shadow .2s ease; }
.stTabs [role="tab"]:hover { transform: translateY(-1px); border-color:#CFC6B4; box-shadow: 0 4px 12px rgba(20,32,43,.08); }
.stTabs [role="tab"] p { font-weight:600; font-size:.86rem; color:var(--ink); white-space:nowrap; }
.stTabs [role="tab"][aria-selected="true"] { background: var(--navy) !important; border-color: var(--navy) !important; box-shadow: 0 6px 16px rgba(20,32,43,.22); }
.stTabs [role="tab"][aria-selected="true"] p { color:#F4F1EA !important; }
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"], .stTabs .react-aria-SelectionIndicator { display:none !important; }
.stTabs [role="tabpanel"] { animation: rise .45s ease both; }

/* Cards around charts, tables, metrics, expanders */
[data-testid="stPlotlyChart"] { background:#FFFFFF; border:1px solid var(--line); border-radius:16px; padding:8px 10px;
  box-shadow: 0 2px 10px rgba(20,32,43,.04); animation: rise .6s ease both; }
[data-testid="stMetric"] { background:#FFFFFF; border:1px solid var(--line); border-radius:14px; padding:12px 16px; box-shadow: 0 2px 8px rgba(20,32,43,.04); animation: rise .5s ease both; }
[data-testid="stMetricValue"] { font-family:'Oswald', Arial, sans-serif !important; color:var(--ink); }
[data-testid="stDataFrame"] { border-radius:12px; overflow:hidden; border:1px solid var(--line); }
[data-testid="stExpander"] { background:#FFFFFF; border-radius:12px; border:1px solid var(--line); }
[data-testid="stExpander"] details { border:none; }
.stButton button { border-radius:999px; border:1px solid var(--navy); background:var(--navy); color:#F4F1EA; font-weight:600; padding:.45rem 1.2rem;
  transition: transform .15s ease, box-shadow .15s ease; }
.stButton button:hover { transform: translateY(-1px); box-shadow: 0 6px 16px rgba(20,32,43,.2); color:#FFFFFF; border-color:var(--navy); }

/* Commitment checker */
.checker { background: linear-gradient(135deg, #FFFFFF, #FBF6EE); border:1px solid var(--line); border-radius:18px; padding:16px 20px 6px; margin-bottom:14px; }
.footer { margin-top:28px; padding:18px 4px 6px; border-top:1px solid var(--line); color:var(--muted); font-size:.82rem; display:flex; justify-content:space-between; flex-wrap:wrap; gap:8px; }
</style>
"""


def _template():
    t = go.layout.Template()
    t.layout = go.Layout(
        font=dict(family="Public Sans, Arial, sans-serif", size=13, color=INK),
        title=dict(font=dict(family="Oswald, Arial, sans-serif", size=19, color=INK), x=0.01, xanchor="left"),
        colorway=[NAVY, ORANGE, TEAL, "#8A96A3", "#C9A227"],
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(gridcolor="#EEE9DF", zerolinecolor="#D9D2C3", linecolor="#D9D2C3", ticks="outside", tickcolor="#D9D2C3"),
        yaxis=dict(gridcolor="#EEE9DF", zerolinecolor="#D9D2C3", linecolor="#D9D2C3"),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=12)),
        hoverlabel=dict(bgcolor=NAVY, font=dict(color="#F4F1EA", family="Public Sans, Arial, sans-serif")),
        margin=dict(l=40, r=24, t=56, b=40),
        transition=dict(duration=500, easing="cubic-in-out"),
    )
    return t


def setup():
    """Inject styles and register the chart theme. Call once, right after set_page_config."""
    st.markdown(CSS, unsafe_allow_html=True)
    pio.templates["ce725"] = _template()
    pio.templates.default = "plotly_white+ce725"


def _md(lines):
    st.markdown("".join(l.strip() for l in lines), unsafe_allow_html=True)


def sidebar_brand():
    st.sidebar.markdown(
        "<div class='sb-brand'>"
        "<svg width='38' height='38' viewBox='0 0 40 40' aria-hidden='true'>"
        "<rect x='4' y='22' width='8' height='14' rx='2' fill='#E8772E'/>"
        "<rect x='16' y='14' width='8' height='22' rx='2' fill='#F2A26A'/>"
        "<rect x='28' y='6' width='8' height='30' rx='2' fill='#F4F1EA'/></svg>"
        "<div><div class='t'>Schedule &amp; Cost Risk</div><div class='s'>Decision toolkit</div></div></div>",
        unsafe_allow_html=True)


def _curve_svg(durations_days, plan_days, p80_days):
    """Small animated S-curve: chance of finishing by each duration, with plan and P80 marked."""
    m = np.sort(np.asarray(durations_days)) / 30.0
    lo, hi = np.percentile(m, 0.5), np.percentile(m, 99.5)
    plan_m, p80_m = plan_days / 30.0, p80_days / 30.0
    lo = min(lo, plan_m - 0.3)
    W, H, L, R, T, B = 560, 210, 34, 16, 14, 34
    X = lambda v: L + (v - lo) / (hi - lo) * (W - L - R)
    Y = lambda p: T + (1 - p) * (H - T - B)
    xs = np.linspace(lo, hi, 70)
    ps = np.searchsorted(m, xs, side="right") / len(m)
    d = "M" + " L".join(f"{X(x):.1f} {Y(p):.1f}" for x, p in zip(xs, ps))
    p_plan = float((m <= plan_m).mean())
    ticks = range(int(np.ceil(lo)), int(np.floor(hi)) + 1)
    tick_svg = "".join(f"<text x='{X(t):.1f}' y='{H - 12}' fill='#9AA6B2' font-size='11' text-anchor='middle'>{t}</text>" for t in ticks)
    grid = "".join(f"<line x1='{L}' x2='{W - R}' y1='{Y(q):.1f}' y2='{Y(q):.1f}' stroke='rgba(255,255,255,.08)'/>"
                   f"<text x='{L - 6}' y='{Y(q) + 4:.1f}' fill='#9AA6B2' font-size='10' text-anchor='end'>{int(q * 100)}%</text>" for q in (0, .5, 1))
    return (
        f"<svg viewBox='0 0 {W} {H}' width='100%' role='img' aria-label='Chance of finishing by each month'>"
        f"{grid}{tick_svg}"
        f"<line x1='{X(plan_m):.1f}' x2='{X(plan_m):.1f}' y1='{T}' y2='{H - B}' stroke='#9AA6B2' stroke-dasharray='4 4'/>"
        f"<line x1='{L}' x2='{X(p80_m):.1f}' y1='{Y(.8):.1f}' y2='{Y(.8):.1f}' stroke='#E8772E' stroke-dasharray='4 4' opacity='.7'/>"
        f"<path class='curve-path' pathLength='1' d='{d}' fill='none' stroke='#F4F1EA' stroke-width='3' stroke-linecap='round'/>"
        f"<circle class='curve-mark' cx='{X(plan_m):.1f}' cy='{Y(p_plan):.1f}' r='6' fill='#9AA6B2'/>"
        f"<circle class='curve-mark' cx='{X(p80_m):.1f}' cy='{Y(.8):.1f}' r='7' fill='#E8772E'/>"
        f"<text class='curve-label' x='{X(plan_m) + 8:.1f}' y='{T + 14}' fill='#C3CCD4' font-size='12'>Plan {plan_m:.1f} mo · {p_plan:.0%}</text>"
        f"<text class='curve-label' x='{X(p80_m) - 8:.1f}' y='{Y(.8) - 10:.1f}' fill='#F2A26A' font-size='12' font-weight='700' text-anchor='end'>P80 {p80_m:.1f} mo</text>"
        "</svg>")


def hero(durations_days, plan_days, p80_days, prob_plan, contingency_p80):
    if prob_plan < 0.10:
        verdict, colour = "High schedule risk", "#E8772E"
    elif prob_plan < 0.40:
        verdict, colour = "Moderate schedule risk", "#F2C14E"
    else:
        verdict, colour = "Low schedule risk", "#5FBFA8"
    budget = "contingency above a flat 10%" if contingency_p80 > 0.10 else "contingency within a flat 10%"
    _md([
        "<div class='hero'><div class='hero-wrap'>",
        "<div class='hero-left'>",
        "<div class='eyebrow'>10,000 simulated futures · one defensible plan</div>",
        "<h1>Construction schedule &amp; cost risk</h1>",
        "<p class='sub'>Every run gives each activity a realistic duration and cost, lets linked work slip together, "
        "rolls the dice on each risk and rebuilds the cash flow. Read the result as odds, not a single promise.</p>",
        f"<div class='verdict'><span class='dot' style='background:{colour}'></span><b>{verdict}</b>"
        f" <span style='color:#C3CCD4'>· plan date met in {prob_plan:.1%} of runs · {budget}</span></div>",
        "</div>",
        "<div class='hero-right'><div class='curve-card'>",
        "<div class='cap'>Chance of finishing by each month</div>",
        _curve_svg(durations_days, plan_days, p80_days),
        "</div></div>",
        "</div></div>",
    ])


def kpi_grid(cards):
    """cards: list of dicts {label, value, unit, chip, tone, help, accent}."""
    out = ["<div class='kpi-grid'>"]
    for i, c in enumerate(cards):
        tone = {"bad": "chip-bad", "good": "chip-good"}.get(c.get("tone"), "chip-neutral")
        chip = f"<span class='chip {tone}'>{html.escape(c['chip'])}</span>" if c.get("chip") else ""
        unit = f" <small>{html.escape(c['unit'])}</small>" if c.get("unit") else ""
        out.append(
            f"<div class='kpi' style='animation-delay:{0.08 * i:.2f}s'>"
            f"<span class='bar' style='background:{c.get('accent', NAVY)}'></span>"
            f"<div class='lab'><span>{html.escape(c['label'])}</span>"
            f"<span class='q' title='{html.escape(c.get('help', ''), quote=True)}'>?</span></div>"
            f"<div class='val'>{html.escape(c['value'])}{unit}</div>{chip}</div>")
    out.append("</div>")
    _md(out)


def plain_words(text_html):
    _md([f"<div class='plain'><div class='ic'>💡</div><p>{text_html}</p></div>"])


def section(kicker, title, desc=""):
    d = f"<div class='d'>{desc}</div>" if desc else ""
    _md([f"<div class='sec'><div class='k'>{kicker}</div><div class='h'>{title}</div>{d}</div>"])


def gauge(value_pct, title):
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=value_pct,
        number=dict(suffix="%", font=dict(family="Oswald, Arial, sans-serif", size=46, color=INK)),
        title=dict(text=title, font=dict(size=14, color=MUTED)),
        gauge=dict(
            axis=dict(range=[0, 100], tickwidth=1, tickcolor="#B8B0A0", ticksuffix="%"),
            bar=dict(color=NAVY, thickness=0.28),
            bgcolor="#FFFFFF", borderwidth=0,
            steps=[dict(range=[0, 50], color="#FCE7DA"), dict(range=[50, 80], color="#F7EFDF"), dict(range=[80, 100], color="#DDEFEC")],
            threshold=dict(line=dict(color=ORANGE, width=4), thickness=0.85, value=80),
        )))
    fig.update_layout(height=250, margin=dict(l=24, r=24, t=60, b=10))
    return fig


def footer():
    _md(["<div class='footer'><span>Schedule &amp; Cost Risk Toolkit · CE725 Construction Economics and Finance</span>",
         "<span>Checked against hand calculations and an independent Excel model · AI-assisted, team-verified</span></div>"])
