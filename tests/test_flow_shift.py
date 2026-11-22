"""Offline tests for backtest/flow_shift.py - the weighted slot allocator (w = 1 is daily_combos.allocate; a raised weight liquidates
at its own leverage), the weighted news booking (w = 1 is news.combo.daily), resizing a marked-to-market series with the fee on
flips, and the day-open state lookup. Synthetic data only.

    python tests/test_flow_shift.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backtest import daily_combos as dc  # noqa: E402
from backtest import flow_shift as fs  # noqa: E402


def _T(n=40, seed=2):
    rng = np.random.default_rng(seed)
    t0 = pd.Timestamp("2023-01-01")
    tin = [t0 + pd.Timedelta(hours=int(h)) for h in np.sort(rng.integers(0, 2000, n))]
    tout = [a + pd.Timedelta(hours=int(rng.integers(4, 200))) for a in tin]
    return pd.DataFrame(dict(t_in=tin, t_out=tout, net=rng.normal(0.01, 0.05, n), worst=rng.uniform(0.0, 0.6, n), score=0.0))


def test_weight_one_is_the_original_allocator():
    T = _T()
    for sd in (0, 3):
        a = dc.allocate(T, sd, 2.0)
        b = fs.allocate_w(T, sd, 2.0, np.ones(len(T)))
        assert a == b
    tied = _T(30, seed=5).assign(t_in=pd.Timestamp("2023-02-01"), t_out=pd.Timestamp("2023-02-03"))   # 30 entries at once, 8 slots
    for sd in (0, 1, 7):
        assert dc.allocate(tied, sd, 2.0) == fs.allocate_w(tied, sd, 2.0, np.ones(30))


def test_a_loss_beyond_the_margin_is_floored_at_the_stake():
    T = pd.DataFrame(dict(t_in=[pd.Timestamp("2023-01-01")], t_out=[pd.Timestamp("2023-01-03")], net=[-0.6], worst=[0.1], score=[0.0]))
    q, size, pnl = fs.allocate_w(T, 0, 2.0, np.array([1.0]))[0]
    assert pnl == -size


def test_a_raised_weight_liquidates_at_its_own_leverage():
    T = pd.DataFrame(dict(t_in=[pd.Timestamp("2023-01-01")], t_out=[pd.Timestamp("2023-01-03")], net=[0.04], worst=[0.30], score=[0.0]))
    q, size, pnl = fs.allocate_w(T, 0, 2.0, np.array([1.0]))[0]
    assert abs(pnl - size * 2.0 * 0.04) < 1e-15                                               # 2x: a 30% dip survives (line 49%)
    q, size, pnl = fs.allocate_w(T, 0, 2.0, np.array([2.0]))[0]
    assert pnl == -size                                                                        # 4x: the line is 24%, liquidated
    q, size, pnl = fs.allocate_w(T.assign(worst=[0.1]), 0, 2.0, np.array([2.0]))[0]
    assert abs(pnl - size * 4.0 * 0.04) < 1e-15


def test_weighted_news_booking():
    import news.combo as NC
    t0 = pd.Timestamp("2023-01-01")
    trades = [(t0 + pd.Timedelta(days=d), t0 + pd.Timedelta(days=d + 3), r) for d, r in ((0, 0.10), (1, -0.05), (5, 0.20), (6, 0.02))]
    a, b = NC.daily(trades), fs.news_daily_w(trades, lambda t: 1.0)
    assert np.allclose(a.to_numpy(), b.to_numpy()) and (a.index == b.index).all()
    c = fs.news_daily_w(trades, lambda t: 2.0 if t >= t0 + pd.Timedelta(days=5) else 1.0)
    eq_before = 1 + 0.1 * 0.10 + 0.1 * (-0.05) * (1 + 0.0)                                   # the first two closed before day 5
    assert c.index[-1] == a.index[-1] and abs((1 + c).prod() - 1 - ((1 + a).prod() - 1)) > 1e-6
    v = (1 + c).cumprod()                                                                     # starts at the first exit (equity 1.01)
    assert abs(v.loc[t0 + pd.Timedelta(days=4)] / v.loc[t0 + pd.Timedelta(days=3)] - eq_before / 1.01) < 1e-9
    one = [(t0 + pd.Timedelta(days=4), t0 + pd.Timedelta(days=7), 0.10)]                      # enters at weight 1, exits where it is 2
    d = fs.news_daily_w([(t0, t0 + pd.Timedelta(days=1), 0.0)] + one, lambda t: 2.0 if t >= t0 + pd.Timedelta(days=5) else 1.0)
    assert abs((1 + d).prod() - 1 - 0.1 * 0.10) < 1e-12                                       # sized by the ENTRY weight


def test_resized_scales_and_charges_the_flip():
    idx = pd.date_range("2023-01-01", periods=5, freq="D")
    x = pd.Series([0.01, 0.02, -0.01, 0.03, 0.0], index=idx)
    w = pd.Series([1.0, 1.0, 2.0, 2.0, 1.0], index=idx)
    r = fs.resized(x, w, gross=0.5)
    exp = x * w - fs.FEE1 * np.array([0, 0, 1, 0, 1]) * 0.5
    assert np.allclose(r.to_numpy(), exp.to_numpy())


def test_day_lookup_reads_the_state_of_the_trades_day():
    idx = pd.date_range("2023-01-01", periods=4, freq="D")
    b = pd.Series([False, True, False, True], index=idx)
    f = fs.day_lookup(b)
    assert f(pd.Timestamp("2023-01-02 13:00")) and not f(pd.Timestamp("2023-01-03 00:00")) and not f(pd.Timestamp("2022-12-31 23:00"))
    assert f(np.datetime64("2023-01-04T20:00"))


def test_state_weight():
    b = pd.Series([False, True, np.nan], index=pd.date_range("2023-01-01", periods=3, freq="D"), dtype=object)
    assert list(fs.state_weight(b, 2.0)) == [1.0, 2.0, 1.0]


if __name__ == "__main__":
    n = 0
    for k, v in sorted(globals().items()):
        if k.startswith("test_") and callable(v):
            v()
            n += 1
            print("ok", k)
    print(n, "tests passed")
