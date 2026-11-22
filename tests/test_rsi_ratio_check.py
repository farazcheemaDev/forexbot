"""Offline tests for backtest/rsi_ratio_check.py - the causal signal count and the capped account. Synthetic trades only.

    python tests/test_rsi_ratio_check.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backtest import rsi_ratio_check as ck  # noqa: E402


def h(x):
    return np.datetime64("2024-01-01T00:00") + np.timedelta64(int(x), "h")


def test_trailing_count_includes_the_same_hour_and_the_past_and_never_the_future():
    t = np.array([h(0), h(1), h(1), h(5), h(25), h(26), h(60)], "datetime64[ns]")
    c = ck.trailing_counts(t, 24)
    # window = (t - 24h, t]: h0 alone; the two h1 entries see h0 and both h1 (same-hour signals are known together) = 3; h5 sees four;
    # h25 loses h0 AND the h1 pair (h1 is exactly 24h old and out) and keeps h5, h25 = 2; h26 keeps h5, h25, h26 = 3; h60 is alone
    assert c.tolist() == [1, 3, 3, 4, 2, 3, 1], c.tolist()
    assert ck.trailing_counts(t, 1).tolist() == [1, 2, 2, 1, 1, 1, 1]                  # a one-hour window is (t-1h, t]: only the same-hour group counts


def trades(rows):
    return pd.DataFrame(rows, columns=["t_in", "t_out", "net"]).assign(t_in=lambda d: d.t_in.map(h), t_out=lambda d: d.t_out.map(h))


def test_account_sizes_at_booked_equity_books_at_exit_and_skips_when_full():
    x = trades([(0, 2, 1.0), (3, 5, 1.0), (6, 8, -1.0)])                               # three non-overlapping trades, K=1
    eq, cv = ck.account(x, 1, risk=0.01, start=100.0)
    assert abs(eq - 100.0 * 1.01 * 1.01 * 0.99) < 1e-9, eq
    assert len(cv) == 3 and abs(cv.iloc[0] - 101.0) < 1e-9
    y = trades([(0, 10, 1.0), (2, 4, 1.0)])                                            # the second signal arrives while the first is open and K=1
    eq1, _ = ck.account(y, 1, risk=0.01, start=100.0)
    assert abs(eq1 - 101.0) < 1e-9                                                     # skipped
    eq2, _ = ck.account(y, 2, risk=0.01, start=100.0)
    assert abs(eq2 - 102.0) < 1e-9                                                     # both sized on the SAME booked equity (the first has not exited)
    z = trades([(0, 3, 1.0), (3, 6, 1.0)])                                             # exit and entry in the same hour: the slot is free
    eqz, _ = ck.account(z, 1, risk=0.01, start=100.0)
    assert abs(eqz - 100.0 * 1.01 * 1.01) < 1e-9


def test_simultaneous_signals_are_ordered_at_random_but_only_k_are_taken():
    x = trades([(0, 4, 1.0), (0, 4, -1.0), (0, 4, 1.0)])
    outs = {round(ck.account(x, 1, risk=0.01, seed=s, start=100.0)[0], 6) for s in range(30)}
    assert outs == {101.0, 99.0}, outs                                                  # one of the three is taken; which one depends on the ordering seed


def test_a_losing_trade_before_a_winning_one_changes_the_size_of_the_second():
    x = trades([(0, 1, -1.0), (2, 3, 1.0)])
    eq, _ = ck.account(x, 1, risk=0.10, start=100.0)
    assert abs(eq - 99.0) < 1e-9, eq                                                    # the second risks 10% of 90 (= +9); sized on 100 it would end at 100


if __name__ == "__main__":
    n = 0
    for k, v in sorted(globals().items()):
        if k.startswith("test_") and callable(v):
            v()
            n += 1
            print("ok", k)
    print(n, "tests pass")
