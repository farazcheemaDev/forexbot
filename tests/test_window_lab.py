"""window_lab.py offline: the statistics Module 3 teaches, on synthetic series with known answers.
Run as a script: python tests/test_window_lab.py"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import window_lab as wl  # noqa: E402


def ar1(n, phi, rng):
    e = rng.normal(size=n)
    x = np.zeros(n)
    for i in range(1, n):
        x[i] = phi * x[i - 1] + e[i]
    return x


def test_the_forward_change_is_in_bp_of_the_start_and_never_reads_before_t():
    mid = np.array([100.0, 101.0, 102.0, 99.0, 100.0, 103.0])
    f = wl.fwd_change_bp(mid, 2)
    assert abs(f[0] - (102 - 100) / 100 * 1e4) < 1e-9 and abs(f[1] - (99 - 101) / 101 * 1e4) < 1e-9 and abs(f[3] - (103 - 99) / 99 * 1e4) < 1e-9
    assert np.isnan(f[4]) and np.isnan(f[5]) and np.isfinite(f[:4]).all()
    mid2 = mid.copy()
    mid2[:2] = [1.0, 2.0]                                                                         # the PAST changed: the forward change from t = 3 is the same
    assert wl.fwd_change_bp(mid2, 2)[3] == f[3]
    assert np.isnan(wl.fwd_change_bp(mid, 10)).all()


def test_spearman_ranks_ties_and_drops_missing_pairs():
    x = np.arange(10.0)
    assert abs(wl.spearman(x, x ** 3)[0] - 1.0) < 1e-12 and abs(wl.spearman(x, -x)[0] + 1.0) < 1e-12        # monotone, not linear
    y = x.copy()
    y[3] = np.nan
    r, n = wl.spearman(x, y)
    assert n == 9 and abs(r - 1.0) < 1e-12
    r, n = wl.spearman(np.array([1.0, 1.0, 2.0, 2.0]), np.array([1.0, 2.0, 1.0, 2.0]))
    assert n == 4 and abs(r) < 1e-12                                                              # ties get average ranks
    assert abs(wl.t_from_rho(0.1, 102) - 0.1 * np.sqrt(100 / 0.99)) < 1e-12


def test_nonoverlapping_samples_are_every_h_th_second_from_the_offset():
    feat = np.arange(100.0)
    fwd = feat * 2
    r, n, t = wl.ic_nonoverlap(feat, fwd, 10)
    assert n == 10 and abs(r - 1.0) < 1e-12
    r, n, t = wl.ic_nonoverlap(feat, fwd, 30, offset=5)
    assert n == 4                                                                                  # indices 5, 35, 65, 95
    feat2 = np.zeros(100)
    feat2[5::30] = [1, 2, 3, 4]
    fwd2 = np.zeros(100)
    fwd2[5::30] = [4, 3, 2, 1]
    assert abs(wl.ic_nonoverlap(feat2, fwd2, 30, offset=5)[0] + 1.0) < 1e-12                       # exactly the sampled seconds are used


def test_overlapping_samples_inflate_t_and_non_overlapping_ones_do_not():
    """A persistent feature unrelated to a random walk: the naive t is far from standard normal, the non-overlapping t is not."""
    naive, honest = [], []
    for seed in range(40):
        rng = np.random.default_rng(seed)
        mid = 100 + np.cumsum(rng.normal(size=20_000) * 0.05)
        feat = ar1(20_000, 0.98, rng)
        fwd = wl.fwd_change_bp(mid, 30)
        naive.append(wl.ic_overlap(feat, fwd)[2])
        honest.append(wl.ic_nonoverlap(feat, fwd, 30)[2])
    assert np.std(naive) > 3.0, np.std(naive)
    assert np.std(honest) < 1.5, np.std(honest)


def test_a_real_relation_is_found_and_the_shifted_null_does_not_find_it():
    rng = np.random.default_rng(3)
    n = 30_000
    feat = ar1(n, 0.9, rng)
    mid = 100 + np.cumsum(0.03 * feat + rng.normal(size=n) * 0.2)                                  # the feature pushes the next step
    fwd = wl.fwd_change_bp(mid, 5)
    real = wl.ic_overlap(feat, fwd)[0]
    nul = wl.null_ic(feat, fwd, np.random.default_rng(1), 100)
    assert real > 0.15 and np.abs(nul).max() < 0.5 * real and nul.std() < 0.08, (real, nul.std())
    p = (1 + np.sum(np.abs(nul) >= abs(real))) / (1 + len(nul))
    assert p < 0.02


def test_shifting_keeps_the_features_own_persistence():
    rng = np.random.default_rng(5)
    x = ar1(50_000, 0.95, rng)
    s = wl.shifted(x, 12_345)
    assert abs(wl.acf(s, 1) - wl.acf(x, 1)) < 0.01 and abs(wl.acf(s, 30) - wl.acf(x, 30)) < 0.01
    assert not np.allclose(s, x) and abs(wl.acf(x, 1) - 0.95) < 0.02


def test_acf_lags_follow_the_ar1_decay():
    x = ar1(60_000, 0.9, np.random.default_rng(8))
    assert abs(wl.acf(x, 1) - 0.9) < 0.02 and abs(wl.acf(x, 5) - 0.9 ** 5) < 0.03 and abs(wl.acf(x, 20) - 0.9 ** 20) < 0.05


def test_random_walk_dispersion_grows_with_the_square_root_of_the_window():
    rng = np.random.default_rng(2)
    mid = 100 * np.exp(np.cumsum(rng.normal(size=200_000) * 1e-4))
    s1 = np.nanstd(wl.fwd_change_bp(mid, 1))
    for h in (5, 30, 300):
        ratio = np.nanstd(wl.fwd_change_bp(mid, h)) / (s1 * np.sqrt(h))
        assert 0.93 < ratio < 1.07, (h, ratio)


def test_trailing_flow_share_uses_the_window_ending_at_each_second_only():
    signed = np.array([10.0, -5.0, 0.0, 5.0, 0.0, 0.0])
    absd = np.array([10.0, 5.0, 0.0, 5.0, 0.0, 0.0])
    f = wl.trailing_flow_share(signed, absd, 2)
    assert abs(f[0] - 1.0) < 1e-12 and abs(f[1] - 5 / 15) < 1e-12 and abs(f[2] - (-1.0)) < 1e-12 and abs(f[3] - 1.0) < 1e-12
    assert abs(f[4] - 1.0) < 1e-12                                                                 # seconds 3-4 still hold the $5 print
    assert np.isnan(f[5])                                                                          # seconds 4-5: nothing traded
    s2, a2 = signed.copy(), absd.copy()
    s2[3:], a2[3:] = [100.0, -50.0, 7.0], [100.0, 50.0, 7.0]                                       # the FUTURE changed
    f2 = wl.trailing_flow_share(s2, a2, 2)
    assert np.allclose(f2[:3], f[:3])


def test_the_flow_feature_excludes_the_trades_of_the_second_it_predicts():
    """Bin i holds trades AFTER the book row labelled i. A feature at i that includes bin i has seen part of the move it is asked to predict."""
    n = 40
    rng = np.random.default_rng(4)
    signed = np.zeros(n)
    absd = np.zeros(n)
    signed[20], absd[20] = 500.0, 500.0                                                            # one buy print inside second 20
    f = wl.known_flow_share(signed, absd, 5)
    assert np.isnan(f[19]) and np.isnan(f[20])                                                     # nothing traded before second 20 began: no share yet
    assert abs(f[21] - 1.0) < 1e-12 and abs(f[25] - 1.0) < 1e-12 and np.isnan(f[26])              # known from second 21 for 5 seconds
    # on a market where flow causes the SAME second's move and nothing later, the leaky feature shows a big IC and the safe one none
    sg = rng.normal(size=20_000)
    ab = np.ones(20_000)
    mid = 100 + np.cumsum(np.r_[0.0, 0.05 * sg[:-1]])                                              # the move from i to i+1 is made by bin i's flow
    fwd = wl.fwd_change_bp(mid, 1)
    leaky = wl.trailing_flow_share(sg, ab, 1)
    safe = wl.known_flow_share(sg, ab, 1)
    assert wl.spearman(leaky, fwd)[0] > 0.95 and abs(wl.spearman(safe, fwd)[0]) < 0.05


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\n{len(tests)} passed")
