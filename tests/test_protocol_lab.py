"""protocol_lab.py offline: the selection machinery on synthetic series with known answers.
Run as a script: python tests/test_protocol_lab.py"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import protocol_lab as pr  # noqa: E402
from backtest.window_lab import fwd_change_bp  # noqa: E402


def ar1(n, phi, rng):
    e = rng.normal(size=n)
    x = np.zeros(n)
    for i in range(1, n):
        x[i] = phi * x[i - 1] + e[i]
    return x


def synthetic(n=30_000, seed=0, planted=False):
    rng = np.random.default_rng(seed)
    step = rng.normal(size=n) * 1e-4
    feats = {c: ar1(n, 0.9, rng) for c in ("imb1", "imb5", "imb20", "band10")}
    if planted:
        step[1:] += 4e-5 * feats["imb1"][:-1]                                                   # imb1 at t pushes the move from t to t+1
    mid = 100 * np.exp(np.cumsum(step))
    return mid, feats


def test_decision_seconds_are_non_overlapping_and_end_inside_the_segment():
    idx = pr.decision_idx(100, 1000, 30)
    assert idx[0] == 100 and (np.diff(idx) == 30).all() and idx[-1] + 30 < 1000
    assert len(pr.decision_idx(0, 20, 30)) == 0
    tune, hold = pr.decision_idx(0, 600, 30), pr.decision_idx(600, 1000, 30)
    assert tune.max() + 30 < 600 <= hold.min()                                                  # no tune window reaches into the read segment


def test_thresholds_are_fitted_on_the_tune_segment_only():
    feat = np.arange(1000.0)
    lo, hi = pr.thresholds(feat, 10, 0.9, 600)
    f2 = feat.copy()
    f2[600:] = 1e9                                                                              # the READ segment changes completely
    assert pr.thresholds(f2, 10, 0.9, 600) == (lo, hi)
    assert lo < hi and 0 < lo < 100 and 400 < hi < 600


def test_the_rule_goes_long_above_and_short_below_and_skips_the_middle_and_missing():
    feat = np.array([0.9, 0.1, 0.5, np.nan, 0.95, 0.05])
    fwd = np.array([2.0, 3.0, 9.0, 4.0, np.nan, -1.0])
    # decision seconds: 0 long +2, 1 short -3 (the market rose while we were short), 2 skipped (middle), 3 missing feature, 4 missing target, 5 short +1
    g = pr.gross_moves(feat, fwd, 1, 0.1, 0.9, 0, 6)
    assert list(g) == [2.0, -3.0]                                                                # idx 0..4 (5 + 1 = 6 is not < 6): long +2, short -3; the rest skipped / missing
    g = pr.gross_moves(feat, fwd, 1, 0.1, 0.9, 0, 7)
    assert list(g) == [2.0, -3.0, 1.0]                                                           # the short at idx 5 earns +1 on a -1 move


def test_a_planted_signal_is_selected_and_survives_out_of_sample():
    mid, F = synthetic(planted=True)
    fwd = {h: fwd_change_bp(mid, h) for h in pr.HS}
    (c, q, h), m_in, n_in, m_out, n_out, t_in = pr.select_and_read(F, fwd, len(mid))
    assert c == "imb1" and m_in > 1.0 and m_out > 0.6 * m_in, (c, q, h, m_in, m_out)           # a real relation: found, and most of it survives


def test_searching_pure_noise_produces_an_in_sample_winner_that_vanishes_out_of_sample():
    ins, outs = [], []
    for seed in range(30):
        mid, F = synthetic(seed=100 + seed)
        fwd = {h: fwd_change_bp(mid, h) for h in pr.HS}
        _, a, _, b, _, _ = pr.select_and_read(F, fwd, len(mid))
        ins.append(a)
        outs.append(b)
    ins, outs = np.array(ins), np.array(outs)
    assert ins.mean() > 0.6, ins.mean()                                                          # the winner of the search looks good in-sample (this market's noise is 1bp a second) ...
    assert abs(outs.mean()) < 0.35 * ins.mean(), (ins.mean(), outs.mean())                       # ... and is nothing out of sample


def test_selecting_by_t_prefers_the_precise_rule_over_the_lucky_noisy_one():
    mid, F = synthetic(planted=True)
    fwd = {h: fwd_change_bp(mid, h) for h in pr.HS}
    by_t = pr.select_and_read(F, fwd, len(mid), criterion="t")
    assert by_t[5] > 5 and by_t[0][0] == "imb1"                                                  # the planted signal has a large in-sample t
    ins_t = []
    for seed in range(30):
        mid2, F2 = synthetic(seed=300 + seed)
        fwd2 = {h: fwd_change_bp(mid2, h) for h in pr.HS}
        ins_t.append(pr.select_and_read(F2, fwd2, len(mid2), criterion="t")[5])
    assert 1.3 < np.median(ins_t) < 3.4                                                          # a search by t over pure noise still reaches ~2 - 3 by luck


def test_by_mean_chases_the_lucky_noisy_rule_while_by_t_finds_the_weak_precise_one():
    """A weak real relation (imb1 pushes the next second a little) against 59 other rules: the mean rewards a few-trade long-horizon fluke, the t does not."""
    for seed in range(500, 505):
        rng = np.random.default_rng(seed)
        n = 60_000
        step = rng.normal(size=n) * 1e-4
        F = {c: ar1(n, 0.9, rng) for c in ("imb1", "imb5", "imb20", "band10")}
        step[1:] += 6e-6 * F["imb1"][:-1]
        mid = 100 * np.exp(np.cumsum(step))
        fwd = {h: fwd_change_bp(mid, h) for h in pr.HS}
        by_mean = pr.select_and_read(F, fwd, n, criterion="mean")
        by_t = pr.select_and_read(F, fwd, n, criterion="t")
        assert by_mean[0][2] != 5 and by_mean[2] <= 240, (seed, by_mean)                         # a few-trade, long-horizon rule
        assert by_t[0][0] == "imb1" and by_t[0][2] == 5 and by_t[5] > 10, (seed, by_t)             # the real, precisely measured one
        assert by_t[3] > 0.5 * by_t[1]                                                          # and it holds out of sample


def test_the_selection_never_reads_the_read_segment():
    mid, F = synthetic(seed=7)
    fwd = {h: fwd_change_bp(mid, h) for h in pr.HS}
    a = pr.select_and_read(F, fwd, len(mid))
    split = int(len(mid) * pr.SPLIT)
    mid2 = mid.copy()
    mid2[split + 400:] = mid2[split + 400:] * np.random.default_rng(1).uniform(0.9, 1.1, len(mid) - split - 400)
    F2 = {c: f.copy() for c, f in F.items()}
    for f in F2.values():
        f[split + 400:] = np.random.default_rng(2).normal(size=len(f) - split - 400)
    fwd2 = {h: fwd_change_bp(mid2, h) for h in pr.HS}
    b = pr.select_and_read(F2, fwd2, len(mid))
    assert a[0] == b[0] and a[1] == b[1] and a[2] == b[2]                                       # same rule, same in-sample figures; only the out-of-sample number differs
    assert a[3] != b[3]


def test_hit_rate_counts_only_moves_that_happened():
    assert pr.hit_rate(np.array([1.0, 2.0, -1.0, 0.0, 0.0, 0.0])) == 2 / 3
    assert np.isnan(pr.hit_rate(np.zeros(4)))


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\n{len(tests)} passed")
