"""Tests for backtest/mn_booking_convention.py: the two bookings of one weekly basket (buy-and-hold vs re-struck daily), and that its weekly baskets ARE mn_run's.

Run as a script (no pytest on this PC):  python tests/test_mn_booking_convention.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import backtest.mn_booking_convention as bc  # noqa: E402
from backtest import mn_combos as mc  # noqa: E402


def panel(prices):
    X = np.array(prices, float).T                                   # rows = days, columns = coins
    R = np.r_[np.full((1, X.shape[1]), np.nan), X[1:] / X[:-1] - 1]
    ff = pd.DataFrame(X).ffill().to_numpy()
    return X, R, ff


def test_two_bookings_of_one_basket_by_hand():
    # long coin +10% a day for 3 days; short coin: -20%, -25%, then +100% (a crash and a squeeze)
    X, R, ff = panel([[1.0, 1.1, 1.21, 1.331], [1.0, 0.8, 0.6, 1.2]])
    bh, dr, glo, gsh = bc.basket_gap(R, ff, X, 0, 3, np.array([0]), np.array([1]))
    assert abs(bh - (0.5 * 0.331 - 0.5 * 0.2)) < 1e-12                # fixed coins: long +33.1%, the short coin ends +20% (a 20% loss on the short)
    assert abs(dr - (0.5 * 0.3 - 0.5 * 0.55)) < 1e-12                 # re-struck daily: the sum of the days' returns, +30% long, +55% on the coin
    assert abs(glo - 0.5 * (0.3 - 0.331)) < 1e-12 and abs(gsh - (-0.5 * (0.55 - 0.2))) < 1e-12
    assert abs((dr - bh) - (glo + gsh)) < 1e-12                       # the legs' gaps add up to the book's gap
    assert dr < bh                                                    # the squeeze after the crash hurts the daily-reset short far more


def test_with_a_one_day_hold_the_two_bookings_are_the_same():
    X, R, ff = panel([[1.0, 1.3], [1.0, 0.7], [1.0, 1.1]])
    bh, dr, glo, gsh = bc.basket_gap(R, ff, X, 0, 1, np.array([0, 2]), np.array([1]))
    assert abs(bh - dr) < 1e-12 and abs(glo) < 1e-12 and abs(gsh) < 1e-12


def test_a_coin_that_stops_trading_mid_week_keeps_its_last_price_in_both_bookings():
    X, R, ff = panel([[1.0, 1.1, 1.2, 1.3], [1.0, 0.9, np.nan, np.nan]])
    bh, dr, _, _ = bc.basket_gap(R, ff, X, 0, 3, np.array([0]), np.array([1]))
    assert np.isfinite(bh) and np.isfinite(dr)                          # a NaN day must not poison the week (nansum, forward-filled close)
    daily_long = 0.1 + (1.2 / 1.1 - 1) + (1.3 / 1.2 - 1)                  # +10%, +9.09%, +8.33%: a coin that rises by 0.1 a day
    assert abs(bh - (0.5 * 0.3 - 0.5 * (-0.1))) < 1e-12                   # fixed coins: long +30%, the short coin -10% before it stopped trading
    assert abs(dr - (0.5 * daily_long - 0.5 * (-0.1))) < 1e-12            # re-struck daily: the long's days sum to 27.4%; the dead coin contributes its one live day


def test_sharpe_and_t_use_the_weekly_scale_and_the_sample_deviation():
    x = np.array([0.02, 0.0, 0.04, 0.02])
    assert abs(bc.sharpe(x) - x.mean() / x.std(ddof=1) * np.sqrt(52)) < 1e-12
    assert abs(bc.tstat(x) - x.mean() / (x.std(ddof=1) / 2.0)) < 1e-12
    assert np.isnan(bc.sharpe(np.array([0.01, 0.01, 0.01])))


def _fake_panel(n_days=260, n_coins=40, seed=5):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=n_days, freq="D")
    r = rng.normal(0.0, 0.04, (n_days, n_coins))
    r[40:60, 0] -= 0.03                                                # coin 0: a steady fall into the first baskets, then ...
    X = 10 * np.exp(np.cumsum(r, axis=0))
    X[150:, 0] = np.nan                                                # ... it stops trading mid-history (a delisting)
    Fx = rng.normal(0.0, 0.0003, (n_days, n_coins))
    months = idx.strftime("%Y-%m")
    cols = [f"C{i}USDT" for i in range(n_coins)]
    return dict(idx=idx, X=X, cols=cols, Fx=Fx, months=months, fv=np.full(n_coins, idx[0].value - 400 * 86_400_000_000_000),
                Em={m: np.ones(n_coins, bool) for m in sorted(set(months))}, ff=pd.DataFrame(X).ffill().to_numpy(),
                R=np.r_[np.full((1, n_coins), np.nan), X[1:] / X[:-1] - 1], reg=None)


def test_the_weekly_baskets_are_mn_runs_own_and_the_gap_is_the_legs_gaps():
    old = dict(mc._D)
    mc._D.clear()
    mc._D.update(_fake_panel())
    try:
        for s in (0, 3):
            w = bc.weeks(start=s)
            ref = mc.mn_run(start=s)
            assert len(w) == len(ref) > 15
            assert float((w.net_bh - ref).abs().max()) < 1e-12                          # the buy-and-hold booking IS mn_run's, week for week
            assert float((w.gap - (w.long_gap + w.short_gap)).abs().max()) < 1e-12
            assert float((w.net_dr - w.net_bh - w.gap).abs().max()) < 1e-12              # carry and cost are identical in both bookings
            assert float(w.gap.abs().max()) > 1e-4 and np.isfinite(w.to_numpy()).all()
    finally:
        mc._D.clear()
        mc._D.update(old)


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        fn()
        print("ok", fn.__name__)
    print(len(tests), "tests passed")
