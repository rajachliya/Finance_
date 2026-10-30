"""Starter tests. The Validation Engineer should extend these and record each one in the
Validation tab of the tracking workbook (test ID, expected value, tolerance, result)."""
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from engine import NetworkError, build_network, load_network, run_simulation, activity_table
from engine.cpm import deterministic_cpm
from engine.sampling import pert_mean, pert_params, sample_three_point

DATA = Path(__file__).resolve().parents[1] / "data"


@pytest.fixture
def bench():
    return load_network(DATA / "benchmark_6_activity.csv")


def test_pert_params_known_case():
    # O=2, M=4, P=6 is symmetric -> alpha = beta = 3
    a, b = pert_params(np.array([2.0]), np.array([4.0]), np.array([6.0]))
    assert a[0] == pytest.approx(3.0) and b[0] == pytest.approx(3.0)


def test_simulated_means_match_hand_pert_means(bench):
    """The check the course brief asks for: simulated mean vs hand-calculated PERT mean."""
    res = run_simulation(bench, n_iter=200_000, seed=11)
    expected = pert_mean(bench.dur_o, bench.dur_m, bench.dur_p)
    assert np.allclose(res.durations.mean(axis=0), expected, atol=0.02)


def test_samples_stay_inside_range(bench):
    res = run_simulation(bench, n_iter=50_000, seed=3)
    assert (res.durations >= bench.dur_o - 1e-9).all()
    assert (res.durations <= bench.dur_p + 1e-9).all()


def test_degenerate_case_equals_deterministic_cpm():
    df = pd.DataFrame({"id": ["A", "B", "C"], "name": ["a", "b", "c"], "predecessors": ["", "A", "A"],
                       "dur_o": [5, 3, 4], "dur_m": [5, 3, 4], "dur_p": [5, 3, 4]})
    net = build_network(df)
    res = run_simulation(net, n_iter=1_000, seed=1)
    assert np.allclose(res.project_duration, 9.0)


def test_deterministic_cpm_benchmark(bench):
    out = deterministic_cpm(bench, bench.dur_m)
    assert out["duration"] == pytest.approx(16.0)       # both paths are 16 days with most-likely values


def test_merge_bias_simulation_exceeds_pert_path(bench):
    """Two near-equal parallel paths: the simulated mean must exceed the single-path PERT answer."""
    pert = deterministic_cpm(bench, pert_mean(bench.dur_o, bench.dur_m, bench.dur_p))["duration"]
    res = run_simulation(bench, n_iter=50_000, seed=5)
    assert res.project_duration.mean() > pert + 0.2


def test_serial_chain_mean_is_sum_of_pert_means():
    df = pd.DataFrame({"id": list("ABC"), "name": list("abc"), "predecessors": ["", "A", "B"],
                       "dur_o": [2, 3, 1], "dur_m": [4, 5, 2], "dur_p": [9, 10, 6]})
    net = build_network(df)
    res = run_simulation(net, n_iter=200_000, seed=2)
    assert res.project_duration.mean() == pytest.approx(pert_mean(net.dur_o, net.dur_m, net.dur_p).sum(), abs=0.03)


def test_correlation_is_reproduced():
    rng = np.random.default_rng(0)
    r = np.array([[1, 0.6], [0.6, 1]])
    x = sample_three_point(100_000, [0, 0], [5, 5], [10, 10], r, rng)
    rank_corr = pd.DataFrame(x).corr(method="spearman").iloc[0, 1]
    # Gaussian copula: Spearman = (6/pi) * arcsin(rho/2) ~= 0.58 for rho = 0.6
    assert rank_corr == pytest.approx(6 / np.pi * np.arcsin(0.3), abs=0.01)


def test_loop_is_detected():
    df = pd.DataFrame({"id": ["A", "B"], "name": ["a", "b"], "predecessors": ["B", "A"],
                       "dur_o": [1, 1], "dur_m": [2, 2], "dur_p": [3, 3]})
    with pytest.raises(NetworkError):
        build_network(df)


def test_missing_predecessor_is_detected():
    df = pd.DataFrame({"id": ["A"], "name": ["a"], "predecessors": ["Z"],
                       "dur_o": [1], "dur_m": [2], "dur_p": [3]})
    with pytest.raises(NetworkError):
        build_network(df)


def test_criticality_sums_on_parallel_paths(bench):
    res = run_simulation(bench, n_iter=20_000, seed=9)
    t = activity_table(bench, res).set_index("id")
    assert t.loc["A", "criticality_index"] == pytest.approx(1.0)
    assert t.loc["F", "criticality_index"] == pytest.approx(1.0)
    # B and C are on competing paths, so their criticality should add to roughly 1
    assert t.loc["B", "criticality_index"] + t.loc["C", "criticality_index"] == pytest.approx(1.0, abs=0.01)
