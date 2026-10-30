"""Critical path method, vectorised across all simulation iterations.

The loop runs over activities (about 30), not over iterations (10,000+). Each line works on a
whole column of iterations at once, which is why 10,000 runs take well under a second.

Durations array shape: (n_iter, n_activities), columns in the network's topological order.
"""
from __future__ import annotations

import numpy as np

from .network import Network


def forward_pass(net: Network, dur: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Early start, early finish, and project duration for every iteration."""
    dur = np.atleast_2d(dur)
    es = np.zeros_like(dur)
    ef = np.zeros_like(dur)
    for j in range(net.n):
        if net.preds[j]:
            es[:, j] = ef[:, net.preds[j]].max(axis=1)
        ef[:, j] = es[:, j] + dur[:, j]
    project = ef.max(axis=1)
    return es, ef, project


def backward_pass(net: Network, dur: np.ndarray, project: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Late start and late finish for every iteration."""
    dur = np.atleast_2d(dur)
    lf = np.zeros_like(dur)
    ls = np.zeros_like(dur)
    for j in reversed(range(net.n)):
        if net.succs[j]:
            lf[:, j] = ls[:, net.succs[j]].min(axis=1)
        else:
            lf[:, j] = project
        ls[:, j] = lf[:, j] - dur[:, j]
    return ls, lf


def total_float(es: np.ndarray, ls: np.ndarray) -> np.ndarray:
    return ls - es


def critical_mask(es: np.ndarray, ls: np.ndarray, tol: float = 1e-6) -> np.ndarray:
    """True where an activity has (near) zero total float in that iteration."""
    return np.abs(ls - es) <= tol


def deterministic_cpm(net: Network, durations: np.ndarray) -> dict:
    """Single-run CPM, e.g. with most-likely or PERT-mean durations."""
    es, ef, project = forward_pass(net, durations[None, :])
    ls, lf = backward_pass(net, durations[None, :], project)
    crit = critical_mask(es, ls)[0]
    return {
        "duration": float(project[0]),
        "es": es[0], "ef": ef[0], "ls": ls[0], "lf": lf[0],
        "float": (ls - es)[0],
        "critical_ids": [net.ids[i] for i in np.flatnonzero(crit)],
    }
