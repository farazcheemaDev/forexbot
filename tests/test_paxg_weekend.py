"""Tests for backtest/paxg_weekend.py - run as a script (no pytest on this PC): python tests/test_paxg_weekend.py"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backtest import paxg_weekend as pw  # noqa: E402

H1 = pd.Timedelta(hours=1)


def world(move=0.0, revert=0.0, gap=0.0, weeks=12, start="2024-01-01", vol=5.0):
    """Hourly PAXG and minute gold. Each weekend PAXG moves `move` (alternating sign) between Friday 17:00 and Sunday
    16:00 New York, gold reopens `gap` x that move away, and PAXG gives back `revert` x the move in the hour after 18:00."""
    idx = pd.date_range(pd.Timestamp(start, tz="UTC"), periods=weeks * 168 + 200, freq="h").as_unit("ns")
    p = pd.Series(2000.0, index=idx)
    gidx = pd.date_range(idx[0], idx[-1], freq="min").as_unit("ns")
    g = pd.Series(2000.0, index=gidx)
    sign = 1.0
    for fri in pd.date_range(idx[0].tz_convert(pw.NY).normalize(), idx[-1].tz_convert(pw.NY).normalize(), freq="W-FRI"):
        f17, s16, s18 = pw.ny(fri, 17), pw.ny(fri + pd.Timedelta(days=2), 16), pw.ny(fri + pd.Timedelta(days=2), 18)
        if s18 + 30 * H1 > idx[-1] or f17 < idx[0]:
            continue
        m = sign * move
        p[(p.index > f17) & (p.index <= s16)] = 2000.0 * (1 + m)          # wandered by Sunday 16:00
        p[(p.index > s16) & (p.index <= s18)] = 2000.0 * (1 + m)
        p[(p.index > s18) & (p.index <= s18 + 100 * H1)] = 2000.0 * (1 + m * (1 - revert))
        g[(g.index > f17) & (g.index < s18)] = np.nan                       # gold shut
        g[(g.index >= s18) & (g.index <= s18 + pd.Timedelta(days=4))] = 2000.0 * (1 + m * gap)
        sign = -sign
    P = pd.DataFrame({"c": p.to_numpy(), "v": vol}, index=idx)
    return P, g.dropna()


def test_ny_clock_follows_daylight_saving():
    assert pw.ny(pd.Timestamp("2024-01-05"), 17).hour == 22          # winter: 17:00 New York = 22:00 UTC
    assert pw.ny(pd.Timestamp("2024-07-05"), 17).hour == 21          # summer: 21:00 UTC


def test_px_needs_the_bar_and_a_trade_in_it():
    P, _ = world()
    t = P.index[10]
    assert pw.px(P, t) == 2000.0
    assert np.isnan(pw.px(P, t + pd.Timedelta(minutes=7)))            # not a bar end
    P.loc[t, "v"] = 0.0
    assert np.isnan(pw.px(P, t)) and pw.px(P, t, need_volume=False) == 2000.0


def test_gold_is_nan_while_the_market_is_shut():
    P, G = world()
    fri = pd.Timestamp("2024-01-05")
    assert np.isfinite(pw.gold_at(G, pw.ny(fri, 17)))
    assert np.isnan(pw.gold_at(G, pw.ny(fri + pd.Timedelta(days=2), 12)))     # Sunday noon: the last print is 43 hours old
    assert np.isfinite(pw.gold_at(G, pw.ny(fri + pd.Timedelta(days=2), 19)))


def test_a_planted_snap_back_is_found_and_paid():
    P, G = world(move=0.01, revert=1.0, gap=0.0)
    W = pw.weekends(P, G)
    assert len(W) >= 8 and np.allclose(W["dev16"].abs(), 0.01)
    r = pw.fade(W, 0.005, 6)
    assert len(r) == len(W) and np.allclose(r, 0.01 / 1.01 - pw.COST, atol=2e-4)   # both sides earn the whole move back
    b, _, _ = pw.slope(W["dev16"], W["x6"] / W["entry"] - 1)
    assert b < -0.9


def test_information_is_not_paid():
    P, G = world(move=0.01, revert=0.0, gap=1.0)                     # gold reopens where the token went: nothing to fade
    W = pw.weekends(P, G)
    r = pw.fade(W, 0.005, 6)
    assert np.allclose(r, -pw.COST) and np.allclose(W["gap19"].abs(), 0.01, atol=1e-9)


def test_threshold_and_side():
    P, G = world(move=0.004, revert=1.0)
    W = pw.weekends(P, G)
    assert len(pw.fade(W, 0.005, 6)) == 0 and len(pw.fade(W, 0.0025, 6)) == len(W)
    P2, G2 = world(move=0.01, revert=-0.5)                           # the move CONTINUES after the reopen: the fade loses
    assert (pw.fade(pw.weekends(P2, G2), 0.005, 6) < 0).all()


def test_entry_is_one_bar_after_the_signal():
    P, G = world(move=0.01, revert=1.0)
    fri = pd.Timestamp("2024-01-05")
    s17 = pw.ny(fri + pd.Timedelta(days=2), 17)
    P.loc[s17, "c"] = 1234.0                                         # the 17:00 print is the ENTRY, not the signal
    W = pw.weekends(P, G)
    row = W[W.fri == fri].iloc[0]
    assert row["entry"] == 1234.0 and abs(abs(row["dev16"]) - 0.01) < 1e-9


def test_a_holiday_weekend_is_skipped():
    P, G = world()
    fri = pd.Timestamp("2024-01-12")
    f17 = pw.ny(fri, 17)
    G2 = G[~((G.index > f17 - pd.Timedelta(hours=8)) & (G.index <= f17))]     # gold did not trade on Friday afternoon
    assert fri not in set(pw.weekends(P, G2).fri) and fri in set(pw.weekends(P, G).fri)


def test_holm_is_monotone_and_capped():
    adj = pw.holm([0.01, 0.04, 0.03, 0.9])
    assert np.allclose(adj, [0.04, 0.09, 0.09, 0.9]) and (adj <= 1).all()


if __name__ == "__main__":
    n = 0
    for k, f in sorted(globals().items()):
        if k.startswith("test_"):
            f()
            n += 1
    print(f"{n} tests passed")
