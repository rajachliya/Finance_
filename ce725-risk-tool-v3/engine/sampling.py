"""Sampling three-point estimates, with optional correlation between activities.

PERT-Beta (lambda = 4):
    alpha = 1 + 4 (M - O) / (P - O)
    beta  = 1 + 4 (P - M) / (P - O)
    X     = O + (P - O) * Beta(alpha, beta)
    mean  = (O + 4M + P) / 6              <- the "PERT mean" the brief asks you to check by hand

Correlation uses a Gaussian copula:
    1. build a correlation matrix R (here: one correlation value per group, 0 across groups)
    2. Z = N @ L.T, where L is the Cholesky factor of R and N are independent standard normals
    3. U = Phi(Z)  (uniforms that keep the rank correlation)
    4. X = inverse CDF of each activity's own distribution evaluated at U
"""
from __future__ import annotations

import numpy as np
from scipy import stats


def pert_params(o: np.ndarray, m: np.ndarray, p: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    o, m, p = (np.asarray(x, float) for x in (o, m, p))
    span = p - o
    safe = np.where(span > 0, span, 1.0)          # avoid divide-by-zero when O = M = P
    alpha = np.where(span > 0, 1 + 4 * (m - o) / safe, 1.0)
    beta = np.where(span > 0, 1 + 4 * (p - m) / safe, 1.0)
    return alpha, beta


def pert_mean(o, m, p):
    return (np.asarray(o, float) + 4 * np.asarray(m, float) + np.asarray(p, float)) / 6


def pert_sd(o, p):
    return (np.asarray(p, float) - np.asarray(o, float)) / 6


def uniforms_to_pert(u: np.ndarray, o, m, p) -> np.ndarray:
    """Turn uniforms (iterations x activities) into PERT-Beta samples."""
    o, m, p = (np.asarray(x, float) for x in (o, m, p))
    alpha, beta = pert_params(o, m, p)
    x01 = stats.beta.ppf(u, alpha, beta)
    return o + (p - o) * x01                       # when P = O this returns O exactly


def uniforms_to_triangular(u: np.ndarray, o, m, p) -> np.ndarray:
    o, m, p = (np.asarray(x, float) for x in (o, m, p))
    span = p - o
    c = np.where(span > 0, (m - o) / np.where(span > 0, span, 1.0), 0.5)
    return stats.triang.ppf(u, c, loc=o, scale=span)


def group_correlation_matrix(groups: list[str], rho_by_group: dict[str, float]) -> np.ndarray:
    """Equal correlation inside each group, zero between groups."""
    n = len(groups)
    r = np.eye(n)
    for i in range(n):
        for j in range(i + 1, n):
            if groups[i] == groups[j]:
                rho = float(rho_by_group.get(groups[i], 0.0))
                r[i, j] = r[j, i] = rho
    return r


def nearest_psd_correlation(r: np.ndarray, eps: float = 1e-10) -> tuple[np.ndarray, bool]:
    """Simple fix if R is not positive semi-definite: clip negative eigenvalues and rescale.

    Returns (matrix, was_changed). This is a quick approximation; Higham (2002) gives the
    proper nearest correlation matrix. TODO (team): decide whether you need Higham's method
    and log that decision.
    """
    r = (r + r.T) / 2
    vals, vecs = np.linalg.eigh(r)
    if vals.min() >= -eps:
        return r, False
    vals = np.clip(vals, eps, None)
    fixed = vecs @ np.diag(vals) @ vecs.T
    d = np.sqrt(np.diag(fixed))
    fixed = fixed / np.outer(d, d)
    np.fill_diagonal(fixed, 1.0)
    return fixed, True


def correlated_uniforms(n_iter: int, r: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Uniforms with the Gaussian-copula correlation structure R. Shape: (n_iter, n_activities)."""
    n = r.shape[0]
    normals = rng.standard_normal((n_iter, n))
    if np.allclose(r, np.eye(n)):
        z = normals
    else:
        l = np.linalg.cholesky(r + 1e-12 * np.eye(n))
        z = normals @ l.T
    u = stats.norm.cdf(z)
    return np.clip(u, 1e-12, 1 - 1e-12)


def sample_three_point(n_iter, o, m, p, r=None, rng=None, distribution="pert"):
    """Sample every activity n_iter times. Returns array (n_iter, n_activities)."""
    rng = rng or np.random.default_rng()
    n = len(np.atleast_1d(o))
    r = np.eye(n) if r is None else r
    u = correlated_uniforms(n_iter, r, rng)
    if distribution == "triangular":
        return uniforms_to_triangular(u, o, m, p)
    return uniforms_to_pert(u, o, m, p)
