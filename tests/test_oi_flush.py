"""Tests for backtest/oi_flush.py - run as a script (no pytest on this PC): python tests/test_oi_flush.py"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backtest import oi_flush as of  # noqa: E402


def frame(prices, oi=None, long=None, start="2024-01-01"):
    idx = pd.date_range(pd.Timestamp(start, tz="UTC"), periods=len(prices), freq="h").as_unit("ns")
    n = len(prices)
    return pd.DataFrame({"p": np.asarray(prices, float), "oi": np.full(n, 1000.0) if oi is None else np.asarray(oi, float),
                         "long": np.full(n, 0.5) if long is None else np.asarray(long, float)}, index=idx)


def crash(n=200, at=50, depth=0.10, after=None, oi_after=1000.0):
    """Flat at 100, falls `depth` at hour `at`, then follows `after` (a list of prices from at + 1 on)."""
    p = np.full(n, 100.0)
    p[at:] = 100.0 * (1 - depth)
    if after is not None:
        p[at + 1:at + 1 + len(after)] = after
        p[at + 1 + len(after):] = after[-1]
    oi = np.full(n, 1000.0)
    oi[at:] = oi_after
    return p, oi


def test_a_drop_is_an_event_and_the_entry_is_one_hour_later():
    p, oi = crash(after=[91.0, 92.0, 96.0])                       # event at hour 50 (price 90); entry at hour 51 = 91
    ev = of.events(frame(p, oi), "X")
    assert len(ev) == 1
    e = ev[0]
    assert e["t"] == frame(p).index[50] and abs(e["drop"] + 0.10) < 1e-12
    assert e["why"] == "target" and abs(e["gross"] - (96.0 / 91.0 - 1)) < 1e-12 and e["hours"] == 2


def test_no_event_above_the_drop_line_and_one_event_per_day():
    p, _ = crash(depth=0.07)
    assert of.events(frame(p), "X") == []
    p, _ = crash(depth=0.10)
    p[60:] = 80.0                                                 # a second leg 10 hours later: inside the 24-hour pause
    ev = of.events(frame(p), "X")
    assert [e["t"].hour + 24 * (e["t"].day - 1) for e in ev] == [50, 74]      # the second event waits out the pause


def test_time_exit_and_the_worst_dip():
    after = [90.0] + [85.0] * 10 + [88.0] * 200
    p, _ = crash(n=400, after=after)
    e = of.events(frame(p), "X")[0]
    assert e["why"] == "time" and e["hours"] == of.MAX_H
    assert abs(e["gross"] - (88.0 / 90.0 - 1)) < 1e-12 and abs(e["worst"] - (85.0 / 90.0 - 1)) < 1e-12


def test_the_group_uses_the_open_interest_change():
    p, oi = crash(oi_after=880.0)
    assert abs(of.events(frame(p, oi), "X")[0]["doi"] + 0.12) < 1e-12
    assert of.group(-0.12) == "FLUSH" and of.group(-0.10) == "FLUSH" and of.group(-0.05) == "MID"
    assert of.group(0.0) == "BUILD" and of.group(0.3) == "BUILD"


def test_a_hole_in_the_archive_is_not_an_event():
    p, oi = crash()
    X = frame(p, oi)
    X.iloc[26, 0] = np.nan                                        # the price 24 hours before the event hour is missing
    assert all(e["t"] != X.index[50] for e in of.events(X, "X"))
    X = frame(p, oi)
    X.iloc[51, 0] = np.nan                                        # no price to enter at: no trade
    assert all(e["t"] != X.index[50] for e in of.events(X, "X"))


def test_funding_real_where_covered_else_flat():
    t0, t1 = pd.Timestamp("2024-01-02", tz="UTC"), pd.Timestamp("2024-01-03", tz="UTC")
    F = pd.Series([0.001, 0.002, -0.0005, 0.004], index=pd.to_datetime(
        ["2024-01-02 00:00", "2024-01-02 08:00", "2024-01-03 00:00", "2024-01-03 08:00"], utc=True).as_unit("ns"))
    assert abs(of.funding_paid(F, t0, t1) - 0.0015) < 1e-12      # (t0, t1]: 08:00 and the next 00:00 only
    assert abs(of.funding_paid(None, t0, t1) - 3 * of.FLAT_FUND) < 1e-12
    assert abs(of.funding_paid(F, t0 - pd.Timedelta(days=5), t1) - of.FLAT_FUND * 18) < 1e-12     # not covered: flat
    p, oi = crash(after=[91.0, 96.0])
    X = frame(p, oi)
    e = of.events(X, "X")[0]
    assert abs(e["net"] - (e["gross"] - of.COST - of.FLAT_FUND / 8)) < 1e-12                       # one hour held


def test_clustered_t_counts_a_day_once():
    r = np.array([0.02] * 10 + [-0.01, 0.01, 0.0, 0.02])
    same_day = ["a"] * 10 + ["b", "c", "d", "e"]
    own_days = [f"d{i}" for i in range(len(r))]
    m1, t1, n1, g1 = of.clustered(r, same_day)
    m2, t2, n2, g2 = of.clustered(r, own_days)
    assert abs(m1 - m2) < 1e-15 and n1 == 14 and g1 == 5 and g2 == 14
    assert t1 < t2                                               # ten trades on one day are not ten independent bets
    assert np.isnan(of.clustered([0.01, 0.02], ["a", "b"])[1])


def test_long_share_change_is_carried():
    p, oi = crash()
    lg = np.full(len(p), 0.5)
    lg[40:] = 0.6
    e = of.events(frame(p, oi, lg), "X")[0]
    assert abs(e["dlong"] - 0.1) < 1e-12


if __name__ == "__main__":
    n = 0
    for k, f in sorted(globals().items()):
        if k.startswith("test_"):
            f()
            n += 1
    print(f"{n} tests passed")
