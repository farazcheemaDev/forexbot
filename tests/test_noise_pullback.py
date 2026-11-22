"""Tests for backtest/noise_pullback.py: parity with the original rule at wait = 0, and the limit-fill logic on a hand-built day.

Run as a script (no pytest on this PC):  python tests/test_noise_pullback.py
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import backtest.noise_pullback as npb  # noqa: E402
from backtest.fx_intraday_pub import noise, session  # noqa: E402


def toy(path):
    """15 quiet history sessions (price 100, a tiny wobble so sigma > 0) + today with its own close path from minute 30 on. Returns arrays and `prev`."""
    L, n = 390, 16
    base = 100 + 0.05 * np.sin(np.arange(L) / 7.0)
    C = np.tile(base, (n, 1))
    O = np.tile(base, (n, 1))
    O[:, 0] = 100.0
    C[-1] = path
    O[-1, 1:] = C[-1, :-1]
    O[-1, 0] = 100.0
    A = dict(o=O, h=np.maximum(O, C), l=np.minimum(O, C), c=C)
    prev = np.r_[np.nan, C[:-1, -1]]
    return A, prev


def breakout_path(after):
    p = np.full(390, 100.0)
    p[30] = 101.0                                                       # a clean breakout at the first checkpoint (m = 30) ...
    p[31:] = 102.0                                                      # ... that keeps running, so entering at once earns the move
    for k, v in after.items():
        p[30 + k] = v
    return p


def test_with_no_waiting_it_is_exactly_the_original_rule_on_real_nasdaq_bars():
    S = session("NASDAQ")
    assert S is not None
    A, dates, prev = S
    sl = slice(len(dates) - 400, len(dates))
    A2 = {k: v[sl] for k, v in A.items()}
    g, nt = npb.noise_pb(A2, prev[sl])
    g0, _, nt0 = noise(A2, prev[sl])
    assert np.allclose(g, g0, atol=1e-12) and np.array_equal(nt, nt0)
    g1, nt1 = npb.noise_pb(A2, prev[sl], wait=15, retr_bp=0.0)           # no retracement asked: the same rule
    assert np.allclose(g1, g0, atol=1e-12)


def test_a_breakout_that_never_pulls_back_is_skipped():
    A, prev = toy(breakout_path({}))
    g, nt = npb.noise_pb(A, prev, wait=5, retr_bp=5.0)
    assert nt[-1] == 0 and g[-1] == 0.0
    g0, nt0 = npb.noise_pb(A, prev)
    assert nt0[-1] == 1 and g0[-1] > 0                                    # entering at once catches the move


def test_a_pullback_through_the_limit_fills_at_the_limit_price_and_holds_to_the_close():
    c = 101.0
    limit = c * (1 - 5.0 / 1e4)
    A, prev = toy(breakout_path({3: limit * (1 - 3.0 / 1e4)}))            # minute 33 trades 3 bp below the limit
    g, nt = npb.noise_pb(A, prev, wait=5, retr_bp=5.0)
    assert nt[-1] == 1 and abs(g[-1] - (A["c"][-1, -1] / limit - 1)) < 1e-12


def test_touching_the_limit_without_trading_through_does_not_fill_and_a_late_pullback_is_ignored():
    c = 101.0
    limit = c * (1 - 5.0 / 1e4)
    A, prev = toy(breakout_path({3: limit}))                               # touches the limit exactly: under the 0.5 bp trade-through
    assert npb.noise_pb(A, prev, wait=5, retr_bp=5.0)[1][-1] == 0
    A, prev = toy(breakout_path({7: limit * (1 - 3.0 / 1e4)}))             # pulls back in minute 37 but we only wait 5 minutes
    assert npb.noise_pb(A, prev, wait=5, retr_bp=5.0)[1][-1] == 0
    assert npb.noise_pb(A, prev, wait=15, retr_bp=5.0)[1][-1] == 1


def test_the_wait_window_includes_its_last_minute_and_not_the_next():
    limit = 101.0 * (1 - 5.0 / 1e4)
    dip = limit * (1 - 3.0 / 1e4)
    A, prev = toy(breakout_path({5: dip}))                                 # minute 35 = the 5th minute after the signal
    assert npb.noise_pb(A, prev, wait=5, retr_bp=5.0)[1][-1] == 1
    A, prev = toy(breakout_path({6: dip}))                                 # minute 36 is one too late
    assert npb.noise_pb(A, prev, wait=5, retr_bp=5.0)[1][-1] == 0


def test_a_flip_closes_the_old_position_even_when_the_new_limit_never_fills():
    p = np.full(390, 100.0)
    p[30] = 101.0
    p[31:60] = 102.0
    p[33] = 101.0 * (1 - 8.0 / 1e4)                                          # the long fills on a dip
    p[60] = 98.0                                                             # at the next checkpoint it collapses below the lower bound ...
    p[61:] = 97.0                                                            # ... and never bounces: the short limit does not fill
    A, prev = toy(p)
    g, nt = npb.noise_pb(A, prev, wait=5, retr_bp=5.0)
    limit = 101.0 * (1 - 5.0 / 1e4)
    assert nt[-1] == 1 and abs(g[-1] - (A["o"][-1, 61] / limit - 1)) < 1e-12   # flat after the exit at the market, not still long to the close


def test_a_short_signal_rests_its_limit_above_the_close():
    p = np.full(390, 100.0)
    p[30] = 99.0
    p[31:] = 98.0                                                           # the breakdown keeps running
    p[33] = 99.0 * (1 + 8.0 / 1e4)                                          # a bounce of 8 bp through a 5 bp limit
    A, prev = toy(p)
    g, nt = npb.noise_pb(A, prev, wait=5, retr_bp=5.0)
    limit = 99.0 * (1 + 5.0 / 1e4)
    assert nt[-1] == 1 and abs(g[-1] - (-1) * (A["c"][-1, -1] / limit - 1)) < 1e-12


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        fn()
        print("ok", fn.__name__)
    print(len(tests), "tests passed")
