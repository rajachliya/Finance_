"""Build tool inputs from completed construction project reports.

You fill ONE extraction sheet (a CSV) from the reports; this script turns it into:
  - an activity CSV with three-point durations (and costs) based on what really happened
  - ratio statistics per activity type
  - suggested correlation values per activity group
  - suggested risk probabilities and delays
  - a summary comparing results before and after

Nothing in data/ is overwritten. Review the outputs, then copy what you accept into data/.

Run from the repo root:
    python scripts/build_inputs_from_reports.py --extraction data/reports_extraction.csv

Options:
    --map          activity id -> activity type (default data/activity_type_map.csv)
    --activities   the plan to apply ratios to (default data/case_study_activities.csv)
    --risks        current risk register (default data/risk_register.csv)
    --groups       current correlation groups (default data/correlation_groups.csv)
    --out          output folder (default results/from_reports)
    --m-basis      "median" (default): most likely = plan x typical ratio
                   "plan": most likely = the planned duration; only the range comes from reports
    --min-projects minimum projects per activity type before its values are changed (default 3)

Method (record it in the Assumptions tab):
    ratio = actual / planned, per project and activity type (rows of the same type in one project
    are added up first). With 5 or more projects: optimistic = plan x 10th percentile ratio,
    most likely = plan x median ratio, pessimistic = plan x 90th percentile ratio. With 3 or 4
    projects: lowest and highest ratios instead of percentiles. Fewer: values are left unchanged.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

REQUIRED = ["project", "activity_type", "planned_days", "actual_days"]
PCTL_MIN_N = 5


def load_extraction(path: Path) -> tuple[pd.DataFrame, list[str]]:
    df = pd.read_csv(path)
    warnings = []
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise SystemExit(f"Extraction sheet is missing column(s): {', '.join(missing)}")
    df["project"] = df["project"].astype(str).str.strip()
    df["activity_type"] = df["activity_type"].astype(str).str.strip().str.lower()
    if df["project"].str.upper().str.contains("EXAMPLE").any():
        warnings.append("Rows whose project name contains EXAMPLE were found and ignored. Delete the template's example rows.")
        df = df[~df["project"].str.upper().str.contains("EXAMPLE")]
    for c in ["planned_days", "actual_days", "planned_cost_lakh", "actual_cost_lakh", "delay_days"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    risk_only = pd.Series(False, index=df.index)
    for c in ["delay_reason", "risk_id"]:
        if c in df.columns:
            risk_only |= df[c].notna() & (df[c].astype(str).str.strip() != "")
    no_dur = df["planned_days"].isna() & df["actual_days"].isna()
    bad = df[~(risk_only & no_dur) & ((df["planned_days"] <= 0) | df["planned_days"].isna() | df["actual_days"].isna() | (df["actual_days"] < 0))]
    if len(bad):
        warnings.append(f"{len(bad)} row(s) with missing or invalid planned/actual durations were skipped "
                        f"(first: {bad.iloc[0]['project']} / {bad.iloc[0]['activity_type']}).")
    return df, warnings


def ratios_per_project(df: pd.DataFrame, planned: str, actual: str) -> pd.DataFrame:
    """One ratio per project and activity type: sum of actual / sum of planned."""
    ok = df[(df[planned] > 0) & df[actual].notna() & (df[actual] >= 0)]
    g = ok.groupby(["project", "activity_type"])[[planned, actual]].sum().reset_index()
    g["ratio"] = g[actual] / g[planned]
    return g[["project", "activity_type", "ratio"]]


def ratio_stats(r: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for t, s in r.groupby("activity_type")["ratio"]:
        v = s.to_numpy()
        n = len(v)
        if n >= PCTL_MIN_N:
            lo, hi, how = np.percentile(v, 10), np.percentile(v, 90), "10th-90th percentile"
        else:
            lo, hi, how = v.min(), v.max(), "lowest-highest (fewer than 5 projects)"
        rows.append(dict(activity_type=t, n_projects=n, mean=v.mean(), median=np.median(v), low=lo, high=hi,
                         min=v.min(), max=v.max(), share_late=(v > 1).mean(), range_method=how))
    return pd.DataFrame(rows)


def factors(st_row, basis):
    mid = st_row["median"]
    lo, hi = min(st_row["low"], mid), max(st_row["high"], mid)
    if basis == "plan":
        return min(lo, 1.0), 1.0, max(hi, 1.0)
    return lo, mid, hi


def apply_to_plan(acts, amap, dstats, cstats, basis, min_n):
    out = acts.copy()
    for c in ["dur_o", "dur_m", "dur_p", "cost_o_lakh", "cost_m_lakh", "cost_p_lakh"]:
        out[c] = out[c].astype(float)
    t_of = dict(zip(amap["id"], amap["activity_type"].str.lower()))
    ds = dstats.set_index("activity_type") if len(dstats) else pd.DataFrame()
    cs = cstats.set_index("activity_type") if len(cstats) else pd.DataFrame()
    log = []
    for i, a in out.iterrows():
        t = t_of.get(a["id"])
        notes = []
        if t is not None and t in ds.index and ds.loc[t, "n_projects"] >= min_n:
            fo, fm, fp = factors(ds.loc[t], basis)
            plan = float(a["dur_m"])
            o, m, p = round(plan * fo, 1), round(plan * fm, 1), round(plan * fp, 1)
            o = max(o, 0.5)
            out.loc[i, ["dur_o", "dur_m", "dur_p"]] = [min(o, m), m, max(p, m)]
            notes.append(f"durations from {int(ds.loc[t, 'n_projects'])} projects")
        else:
            notes.append("durations unchanged (not enough projects)" if t else "durations unchanged (no activity type)")
        if t is not None and len(cs) and t in cs.index and cs.loc[t, "n_projects"] >= min_n:
            fo, fm, fp = factors(cs.loc[t], basis)
            plan = float(a["cost_m_lakh"])
            o, m, p = round(plan * fo, 1), round(plan * fm, 1), round(plan * fp, 1)
            out.loc[i, ["cost_o_lakh", "cost_m_lakh", "cost_p_lakh"]] = [min(o, m), m, max(p, m)]
            notes.append(f"costs from {int(cs.loc[t, 'n_projects'])} projects")
        changed = any(n.startswith(("durations from", "costs from")) for n in notes)
        if "source_status" in out.columns and changed:
            out.loc[i, "source_status"] = "From completed project reports (ratio method): " + "; ".join(notes)
        log.append(dict(id=a["id"], activity=a["name"], activity_type=t, result="; ".join(notes)))
    return out, pd.DataFrame(log)


def suggest_correlations(r, acts, amap, groups, min_common=4):
    t_of = dict(zip(amap["id"], amap["activity_type"].str.lower()))
    piv = r.pivot_table(index="project", columns="activity_type", values="ratio")
    logp = np.log(piv.clip(lower=1e-6))
    corr_all = logp.corr(method="spearman", min_periods=min_common)
    rows = []
    for g, members in acts.groupby("group")["id"]:
        types = sorted({t_of.get(x) for x in members if t_of.get(x) in piv.columns})
        vals, used = [], 0
        for a_i in range(len(types)):
            for b_i in range(a_i + 1, len(types)):
                v = corr_all.loc[types[a_i], types[b_i]]
                if pd.notna(v):
                    vals.append(v)
                    used += 1
        current = groups.set_index("group")["rho"].get(g, np.nan) if len(groups) else np.nan
        if vals:
            sug = float(np.clip(np.mean(vals), 0.0, 0.9))
            note = f"mean of {used} type pair(s), each with at least {min_common} common projects"
        elif len(types) < 2:
            sug, note = current, "kept current value: only one activity type in this group, so no pair to compare"
        else:
            sug, note = current, "kept current value: not enough projects reporting two types from this group"
        rows.append(dict(group=g, current_rho=current, suggested_rho=round(sug, 2) if pd.notna(sug) else sug,
                         types=", ".join(types), basis=note))
    return pd.DataFrame(rows), corr_all


def suggest_risks(df, risks, min_n):
    if "delay_reason" not in df.columns and "risk_id" not in df.columns:
        return pd.DataFrame(), None
    n_proj = df["project"].nunique()
    key = df["risk_id"].fillna("").astype(str).str.strip() if "risk_id" in df.columns else pd.Series("", index=df.index)
    reason = df["delay_reason"].fillna("").astype(str).str.strip() if "delay_reason" in df.columns else pd.Series("", index=df.index)
    d = df.assign(_key=np.where(key != "", key, reason)).query("_key != ''")
    rows = []
    for k, s in d.groupby("_key"):
        dd = s["delay_days"].dropna().to_numpy() if "delay_days" in s.columns else np.array([])
        row = dict(risk=k, reason_examples="; ".join(sorted(set(s.get("delay_reason", pd.Series(dtype=str)).dropna().astype(str)))[:3]),
                   projects_with_it=s["project"].nunique(), projects_total=n_proj,
                   probability=round(s["project"].nunique() / n_proj, 2), delay_events=len(dd))
        if len(dd) >= 3:
            row.update(delay_o=round(float(np.min(dd)), 1), delay_m=round(float(np.median(dd)), 1), delay_p=round(float(np.max(dd)), 1))
        rows.append(row)
    sug = pd.DataFrame(rows).sort_values("probability", ascending=False) if rows else pd.DataFrame()
    updated = None
    if risks is not None and len(sug) and n_proj >= min_n:
        updated = risks.copy()
        for c in ["probability", "delay_o", "delay_m", "delay_p"]:
            updated[c] = updated[c].astype(float)
        s_idx = sug.set_index("risk")
        for i, r in updated.iterrows():
            if r["id"] in s_idx.index:
                srow = s_idx.loc[r["id"]]
                updated.loc[i, "probability"] = srow["probability"]
                note = f"probability from {int(srow['projects_with_it'])} of {n_proj} completed projects"
                if pd.notna(srow.get("delay_m", np.nan)):
                    updated.loc[i, ["delay_o", "delay_m", "delay_p"]] = [srow["delay_o"], srow["delay_m"], srow["delay_p"]]
                    note += f"; delays from {int(srow['delay_events'])} events"
                if "source_status" in updated.columns:
                    updated.loc[i, "source_status"] = "From completed project reports: " + note
    return sug, updated


def compare_runs(old_acts, new_acts, risks_old, risks_new, groups_old, groups_new):
    from engine import build_network, percentiles, run_simulation
    out = {}
    for label, a, rk, g in [("before", old_acts, risks_old, groups_old), ("after", new_acts, risks_new, groups_new)]:
        net = build_network(a)
        rho = dict(g[["group", "rho"]].values) if g is not None else None
        r = run_simulation(net, n_iter=10_000, seed=42, rho_by_group=rho, risks=rk, overhead_per_month_lakh=12)
        out[label] = percentiles(r.project_duration)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--extraction", required=True, type=Path)
    ap.add_argument("--map", default=ROOT / "data/activity_type_map.csv", type=Path)
    ap.add_argument("--activities", default=ROOT / "data/case_study_activities.csv", type=Path)
    ap.add_argument("--risks", default=ROOT / "data/risk_register.csv", type=Path)
    ap.add_argument("--groups", default=ROOT / "data/correlation_groups.csv", type=Path)
    ap.add_argument("--out", default=ROOT / "results/from_reports", type=Path)
    ap.add_argument("--m-basis", choices=["median", "plan"], default="median")
    ap.add_argument("--min-projects", type=int, default=3)
    args = ap.parse_args()

    df, warnings = load_extraction(args.extraction)
    acts = pd.read_csv(args.activities)
    amap = pd.read_csv(args.map)
    risks = pd.read_csv(args.risks) if args.risks.exists() else None
    groups = pd.read_csv(args.groups) if args.groups.exists() else pd.DataFrame(columns=["group", "rho"])
    args.out.mkdir(parents=True, exist_ok=True)

    known = set(amap["activity_type"].str.lower())
    unknown = sorted(set(df["activity_type"]) - known)
    if unknown:
        warnings.append("Activity types in the extraction sheet with no match in the map (ignored): " + ", ".join(unknown))

    r_dur = ratios_per_project(df, "planned_days", "actual_days")
    dstats = ratio_stats(r_dur)
    if {"planned_cost_lakh", "actual_cost_lakh"} <= set(df.columns):
        cstats = ratio_stats(ratios_per_project(df, "planned_cost_lakh", "actual_cost_lakh"))
    else:
        cstats = pd.DataFrame()

    new_acts, log = apply_to_plan(acts, amap, dstats, cstats, args.m_basis, args.min_projects)
    corr_sug, corr_all = suggest_correlations(r_dur, acts, amap, groups)
    risk_sug, risks_new = suggest_risks(df, risks, args.min_projects)

    # Check the new activity file is valid for the tool
    from engine import build_network
    build_network(new_acts)

    new_acts.to_csv(args.out / "case_study_activities_from_reports.csv", index=False)
    dstats.round(3).to_csv(args.out / "duration_ratio_statistics.csv", index=False)
    if len(cstats):
        cstats.round(3).to_csv(args.out / "cost_ratio_statistics.csv", index=False)
    log.to_csv(args.out / "activity_changes.csv", index=False)
    corr_sug.to_csv(args.out / "suggested_correlation_groups.csv", index=False)
    corr_all.round(3).to_csv(args.out / "ratio_correlations_by_type.csv")
    if len(risk_sug):
        risk_sug.to_csv(args.out / "risk_suggestions.csv", index=False)
    if risks_new is not None:
        risks_new.to_csv(args.out / "risk_register_from_reports.csv", index=False)

    groups_new = corr_sug.rename(columns={"suggested_rho": "rho"})[["group", "rho"]].dropna() if len(corr_sug) else None
    cmp = compare_runs(acts, new_acts, risks, risks_new if risks_new is not None else risks,
                       groups if len(groups) else None, groups_new)

    n_proj = df["project"].nunique()
    changed = log["result"].str.contains("durations from").sum()
    lines = [
        "# Inputs built from completed project reports", "",
        f"- Projects in the extraction sheet: {n_proj}",
        f"- Activity types with data: {len(dstats)} (at least {args.min_projects} projects needed to change values)",
        f"- Activities whose durations were updated: {changed} of {len(acts)}",
        f"- Most-likely basis: {args.m_basis}", "",
        "## Effect on results (10,000 runs, seed 42)",
        f"- Before: P50 {cmp['before']['P50']:.0f} days, P80 {cmp['before']['P80']:.0f} days",
        f"- After:  P50 {cmp['after']['P50']:.0f} days, P80 {cmp['after']['P80']:.0f} days", "",
        "## Duration ratios (actual / planned) by activity type",
        *[f"- {r.activity_type}: {r.n_projects} projects, median {r.median:.2f}, range {r.low:.2f} to {r.high:.2f}, late in {r.share_late:.0%}"
          for r in dstats.itertuples()], "",
        "## Suggested correlation by group",
        *[f"- {r.group}: current {r.current_rho}, suggested {r.suggested_rho} ({r.basis})" for r in corr_sug.itertuples()], "",
    ]
    if len(risk_sug):
        lines += ["## Risks found in the reports",
                  *[f"- {r.risk}: in {r.projects_with_it} of {r.projects_total} projects (probability {r.probability})" for r in risk_sug.itertuples()], ""]
    if warnings:
        lines += ["## Warnings", *[f"- {w}" for w in warnings], ""]
    lines += ["## Next steps",
              "1. Check activity_changes.csv and the ratio statistics for anything implausible.",
              "2. Copy the files you accept into data/ (rename them to the existing file names).",
              "3. Rerun scripts/run_case_study.py and scripts/export_validation_values.py.",
              "4. Record the method and the reports used in the Data_Sources and Assumptions tabs."]
    (args.out / "summary.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    print(f"\nOutputs saved to {args.out}")


if __name__ == "__main__":
    main()
