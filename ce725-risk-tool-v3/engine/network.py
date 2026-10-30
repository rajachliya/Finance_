"""Load an activity network from CSV, check it for errors, and put activities in order.

Expected CSV columns (see data/case_study_activities.csv):
    id, name, predecessors, dur_o, dur_m, dur_p,
    cost_o_lakh, cost_m_lakh, cost_p_lakh, daily_cost_lakh, group

`predecessors` is a semicolon-separated list of activity ids (blank = no predecessor).
Only finish-to-start links with zero lag are supported in this version.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

REQUIRED_COLUMNS = ["id", "name", "predecessors", "dur_o", "dur_m", "dur_p"]
OPTIONAL_DEFAULTS = {
    "cost_o_lakh": 0.0,
    "cost_m_lakh": 0.0,
    "cost_p_lakh": 0.0,
    "daily_cost_lakh": 0.0,
    "group": "ungrouped",
}


class NetworkError(ValueError):
    """Raised when the activity network is not valid."""


@dataclass
class Network:
    ids: list[str]                 # activity ids in topological order
    names: list[str]
    preds: list[list[int]]         # predecessor indices (into the ordered list)
    succs: list[list[int]]         # successor indices
    dur_o: np.ndarray
    dur_m: np.ndarray
    dur_p: np.ndarray
    cost_o: np.ndarray
    cost_m: np.ndarray
    cost_p: np.ndarray
    daily_cost: np.ndarray
    groups: list[str]

    @property
    def n(self) -> int:
        return len(self.ids)

    def index(self, activity_id: str) -> int:
        return self.ids.index(activity_id)


def _split_preds(value) -> list[str]:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return []
    text = str(value).strip()
    if not text:
        return []
    return [p.strip() for p in text.replace(",", ";").split(";") if p.strip()]


def validate_frame(df: pd.DataFrame) -> list[str]:
    """Return a list of human-readable problems. Empty list means the data is usable."""
    problems: list[str] = []
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        return [f"Missing required column(s): {', '.join(missing)}"]

    ids = df["id"].astype(str).str.strip()
    dupes = ids[ids.duplicated()].unique().tolist()
    if dupes:
        problems.append(f"Duplicate activity id(s): {', '.join(dupes)}")

    known = set(ids)
    for _, row in df.iterrows():
        aid = str(row["id"]).strip()
        for p in _split_preds(row["predecessors"]):
            if p not in known:
                problems.append(f"{aid}: predecessor '{p}' does not exist")
            if p == aid:
                problems.append(f"{aid}: an activity cannot be its own predecessor")
        try:
            o, m, pp = float(row["dur_o"]), float(row["dur_m"]), float(row["dur_p"])
            if not (0 <= o <= m <= pp):
                problems.append(f"{aid}: durations must satisfy 0 <= O <= M <= P (got {o}, {m}, {pp})")
        except (TypeError, ValueError):
            problems.append(f"{aid}: durations must be numbers")
        if "cost_m_lakh" in df.columns:
            try:
                co, cm, cp = float(row["cost_o_lakh"]), float(row["cost_m_lakh"]), float(row["cost_p_lakh"])
                if not (0 <= co <= cm <= cp):
                    problems.append(f"{aid}: costs must satisfy 0 <= O <= M <= P (got {co}, {cm}, {cp})")
            except (TypeError, ValueError, KeyError):
                problems.append(f"{aid}: costs must be numbers")
    return problems


def _topological_order(ids: list[str], pred_ids: dict[str, list[str]]) -> list[str]:
    """Kahn's algorithm. Raises NetworkError if the network has a loop."""
    indegree = {a: len(pred_ids[a]) for a in ids}
    children: dict[str, list[str]] = {a: [] for a in ids}
    for a in ids:
        for p in pred_ids[a]:
            children[p].append(a)
    ready = [a for a in ids if indegree[a] == 0]   # keep input order for readability
    order: list[str] = []
    while ready:
        a = ready.pop(0)
        order.append(a)
        for c in children[a]:
            indegree[c] -= 1
            if indegree[c] == 0:
                ready.append(c)
    if len(order) != len(ids):
        stuck = sorted(set(ids) - set(order))
        raise NetworkError(f"The network has a loop involving: {', '.join(stuck)}")
    return order


def build_network(df: pd.DataFrame) -> Network:
    problems = validate_frame(df)
    if problems:
        raise NetworkError("; ".join(problems))

    df = df.copy()
    for col, default in OPTIONAL_DEFAULTS.items():
        if col not in df.columns:
            df[col] = default
    df["id"] = df["id"].astype(str).str.strip()
    df = df.set_index("id", drop=False)

    ids_in = df["id"].tolist()
    pred_ids = {a: _split_preds(df.at[a, "predecessors"]) for a in ids_in}
    order = _topological_order(ids_in, pred_ids)
    pos = {a: i for i, a in enumerate(order)}

    preds = [[pos[p] for p in pred_ids[a]] for a in order]
    succs: list[list[int]] = [[] for _ in order]
    for i, plist in enumerate(preds):
        for p in plist:
            succs[p].append(i)

    d = df.loc[order]
    return Network(
        ids=order,
        names=d["name"].astype(str).tolist(),
        preds=preds,
        succs=succs,
        dur_o=d["dur_o"].to_numpy(float),
        dur_m=d["dur_m"].to_numpy(float),
        dur_p=d["dur_p"].to_numpy(float),
        cost_o=d["cost_o_lakh"].to_numpy(float),
        cost_m=d["cost_m_lakh"].to_numpy(float),
        cost_p=d["cost_p_lakh"].to_numpy(float),
        daily_cost=d["daily_cost_lakh"].fillna(0).to_numpy(float),
        groups=d["group"].fillna("ungrouped").astype(str).tolist(),
    )


def load_network(path: str) -> Network:
    return build_network(pd.read_csv(path))
