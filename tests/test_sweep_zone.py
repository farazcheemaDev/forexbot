"""sweep_zone.py offline: 4h bars, zones (base + impulse), the first-retest window, the daily trend, the R trade, a planted market end to end, a causality
(truncation) check and the gate logic on synthetic tables. Run as a script: python tests/test_sweep_zone.py"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import sweep_zone as sz  # noqa: E402

N = 1600


def hours(n=N):
    return pd.date_range("2024-01-01", periods=n, freq="h").to_numpy("datetime64[ns]")


def quiet():
    t = hours()
    o, h, l, c, q = (np.full(N, v, float) for v in (100.0, 101.0, 99.0, 100.0, 1000.0))
    return t, o, h, l, c, q


IMPULSE = [(100.0, 101.0, 99.9, 101.5), (101.5, 103.0, 101.4, 102.5), (102.5, 104.0, 102.4, 103.5), (103.5, 104.5, 103.4, 104.0)]


def planted_market(body=None):
    """Quiet at 100 (4h ATR 2), a base 4h bar at hours 1400-1403 (range 1.5), an impulse 4h bar 1404-1407 (100 -> 104; body 4 vs the 2.946 needed),
    flat near 104 afterwards, a long sweep at 1450 whose wick (100.5) is inside the demand zone [99.3, 100.8], and an unzoned long sweep at 600."""
    t, o, h, l, c, q = quiet()
    o[1400:1404], c[1400:1404], h[1400:1404], l[1400:1404] = 100.0, 100.0, 100.8, 99.3
    imp = IMPULSE if body is None else [(100.0, 101.0, 99.9, 101.0)] + [(101.0, 101.0 + body / 3, 100.9, 101.0 + body / 3)] * 2 + [(101.0 + body / 3, 100.0 + body + 0.2, 100.9, 100.0 + body)]
    for k, (oo, hh, ll, cc) in enumerate(imp):
        o[1404 + k], h[1404 + k], l[1404 + k], c[1404 + k] = oo, hh, ll, cc
    o[1408:], h[1408:], l[1408:], c[1408:] = 104.0, 104.5, 103.5, 104.0
    o[1450], h[1450], l[1450], c[1450] = 103.6, 103.8, 100.5, 103.7
    o[600], h[600], l[600], c[600] = 99.2, 99.9, 98.0, 99.6
    return t, o, h, l, c, q


# ------------------------------------------------------------------ 4h bars

def test_4h_bars_aggregate_complete_blocks_only():
    t = hours(12)
    o = np.arange(12.0) + 100
    h, l, c = o + 2, o - 1, o + 0.5
    t4, o4, h4, l4, c4 = sz.bars4h(t, o, h, l, c)
    assert len(t4) == 3 and t4[0] == t[0] and t4[1] == t[4]
    assert o4[0] == 100 and c4[0] == 103.5 and h4[0] == 105 and l4[0] == 99          # first open, last close, max high, min low of hours 0-3
    keep = np.r_[0:6, 7:12]                                                          # hour 6 missing: the block 4-7 is incomplete and dropped
    t4b = sz.bars4h(t[keep], o[keep], h[keep], l[keep], c[keep])[0]
    assert len(t4b) == 2 and t4b[0] == t[0] and t4b[1] == t[8]


# ------------------------------------------------------------------ zones

def quiet4h(n=40):
    t4 = hours(n * 4)[::4]
    return t4, np.full(n, 100.0), np.full(n, 101.0), np.full(n, 99.0), np.full(n, 100.0)


def with_pair(base_range, body, up=True, at=20):
    t4, o4, h4, l4, c4 = quiet4h()
    half = base_range / 2
    h4[at], l4[at] = 100 + half, 100 - half                                          # the base bar
    o4[at + 1] = 100.0
    c4[at + 1] = 100.0 + (body if up else -body)
    h4[at + 1], l4[at + 1] = max(o4[at + 1], c4[at + 1]) + 0.3, min(o4[at + 1], c4[at + 1]) - 0.3
    return t4, o4, h4, l4, c4


def test_a_demand_zone_is_a_base_then_an_impulse_known_when_the_impulse_closes():
    t4, o4, h4, l4, c4 = with_pair(1.5, 4.0)
    zs = sz.zones(t4, o4, h4, l4, c4)
    assert len(zs) == 1, zs
    side, created, lo, hi = zs[0]
    assert side == 1 and abs(lo - 99.25) < 1e-12 and abs(hi - 100.75) < 1e-12
    assert created == t4[21] + np.timedelta64(4, "h")                                # the END of the impulse bar, not its start


def test_the_supply_zone_mirrors_it():
    t4, o4, h4, l4, c4 = with_pair(1.5, 4.0, up=False)
    zs = sz.zones(t4, o4, h4, l4, c4)
    assert len(zs) == 1 and zs[0][0] == -1 and abs(zs[0][2] - 99.25) < 1e-12 and abs(zs[0][3] - 100.75) < 1e-12


def test_near_misses_make_no_zone():
    # ATR(j) = (13 x 2 + 1.5) / 14 = 1.9643: the impulse body must reach 1.5 x that = 2.946, the base range must not pass 1.9643
    assert len(sz.zones(*with_pair(1.5, 2.9))) == 0                                   # impulse a hair too small
    assert len(sz.zones(*with_pair(1.5, 3.0))) == 1                                   # just enough
    assert len(sz.zones(*with_pair(2.3, 4.0))) == 0                                   # a base that is too wide (2.3 > 1.0 x ATR)
    t4, o4, h4, l4, c4 = with_pair(1.5, 4.0)
    c4[21] = 100.7                                                                    # the impulse closes inside the base's range, not above its high 100.75? 100.7 < 100.75
    h4[21] = 101.0
    assert len(sz.zones(t4, o4, h4, l4, c4)) == 0                                     # body 0.7 is too small anyway; the close must also clear the base high


def test_a_gap_in_the_bars_between_base_and_impulse_makes_no_zone():
    t4, o4, h4, l4, c4 = with_pair(1.5, 4.0)
    t4 = t4.copy()
    t4[21:] += np.timedelta64(4, "h")                                                 # a missing 4h bar between the base and the impulse
    assert len(sz.zones(t4, o4, h4, l4, c4)) == 0


# ------------------------------------------------------------------ the live window

def flat_hourly(n=900):
    t = hours(n)
    return t, np.full(n, 105.0), np.full(n, 104.0), np.full(n, 104.5)               # h, l, c


def test_a_zone_is_live_from_its_first_retest_for_24_hours():
    t, h, l, c = flat_hourly()
    l[50] = 100.5                                                                     # first trades into the demand zone [100, 101]
    cov = sz.zone_cover(t, h, l, c, [(1, t[10], 100.0, 101.0)])[1]
    live = np.flatnonzero(cov["ok"])
    assert live[0] == 50 and live[-1] == 74 and len(live) == 25, (live[0], live[-1])  # f .. f + 24
    assert cov["lo"][50] == 100.0 and cov["hi"][74] == 101.0 and not cov["ok"][49] and not cov["ok"][75]
    assert not sz.zone_cover(t, h, l, c, [(1, t[10], 100.0, 101.0)])[-1]["ok"].any()  # nothing on the other side


def test_a_touch_before_the_zone_exists_does_not_count():
    t, h, l, c = flat_hourly()
    l[5] = 100.5                                                                      # before the zone was created (index 10)
    assert not sz.zone_cover(t, h, l, c, [(1, t[10], 100.0, 101.0)])[1]["ok"].any()


def test_a_close_beyond_the_far_edge_breaks_the_zone():
    t, h, l, c = flat_hourly()
    l[50] = 100.5
    c[60] = 99.5                                                                      # closes under the demand zone's low
    live = np.flatnonzero(sz.zone_cover(t, h, l, c, [(1, t[10], 100.0, 101.0)])[1]["ok"])
    assert live[0] == 50 and live[-1] == 59 and len(live) == 10
    t, h, l, c = flat_hourly()
    l[50] = 100.5
    c[50] = 99.5                                                                      # the touching bar itself closes through the zone: never live
    assert not sz.zone_cover(t, h, l, c, [(1, t[10], 100.0, 101.0)])[1]["ok"].any()


def test_a_zone_not_retested_within_30_days_is_dead():
    t, h, l, c = flat_hourly()
    l[729] = 100.5                                                                    # 719 hours after creation: inside the 720-hour life
    assert sz.zone_cover(t, h, l, c, [(1, t[10], 100.0, 101.0)])[1]["ok"][729]
    t, h, l, c = flat_hourly()
    l[730] = 100.5                                                                    # 720 hours after: expired
    assert not sz.zone_cover(t, h, l, c, [(1, t[10], 100.0, 101.0)])[1]["ok"].any()


def test_a_supply_zone_mirrors_the_window_and_the_break():
    t, h, l, c = flat_hourly()
    h[50] = 108.5
    cov = sz.zone_cover(t, h, l, c, [(-1, t[10], 108.0, 109.0)])[-1]
    assert np.flatnonzero(cov["ok"])[0] == 50 and np.flatnonzero(cov["ok"])[-1] == 74
    c[55] = 109.5                                                                     # closes above the supply zone's high
    cov = sz.zone_cover(t, h, l, c, [(-1, t[10], 108.0, 109.0)])[-1]
    assert np.flatnonzero(cov["ok"])[-1] == 54


def test_the_most_recently_created_live_zone_wins():
    t, h, l, c = flat_hourly()
    l[50] = 90.0                                                                      # trades into both demand zones
    zs = [(1, t[10], 100.0, 101.0), (1, t[20], 95.0, 96.0)]
    cov = sz.zone_cover(t, h, l, c, zs)[1]
    assert cov["lo"][50] == 95.0 and cov["hi"][50] == 96.0
    assert sz.zone_cover(t, h, l, c, zs[::-1])[1]["lo"][50] == 95.0                  # the list order does not matter


# ------------------------------------------------------------------ the daily trend

def daily_prices(days=80):
    t = hours(days * 24)
    c = np.repeat(100.0 + np.arange(days), 24)
    return t, c


def test_the_daily_trend_is_the_previous_completed_days_close_over_its_50_day_mean():
    t, c = daily_prices()
    tr = sz.daily_trend(t, c)
    D = 60                                                                            # a bar in day 60 sees day 59's close 159 and the mean of days 10..59
    exp = 159.0 / np.mean(100.0 + np.arange(10, 60)) - 1
    assert abs(tr[D * 24 + 5] - exp) < 1e-12 and abs(tr[D * 24 + 23] - exp) < 1e-12
    assert np.isnan(tr[40 * 24])                                                      # fewer than 50 complete days before it


def test_an_incomplete_day_blanks_the_trend_until_it_leaves_the_window():
    t, c = daily_prices(130)
    keep = np.ones(len(t), bool)
    keep[55 * 24 + 3] = False                                                         # day 55 loses an hour, so its daily close is unknown
    tr = sz.daily_trend(t[keep], c[keep])
    day = pd.DatetimeIndex(t[keep]).floor("D")
    d = lambda k: tr[np.flatnonzero(day == pd.Timestamp("2024-01-01") + pd.Timedelta(days=k))[0]]
    assert np.isfinite(d(54)) and np.isfinite(d(55))                                  # day 55 itself is not yet read, and day 54's window does not hold it
    assert np.isnan(d(56)) and np.isnan(d(57)) and np.isnan(d(70)) and np.isnan(d(105))   # day 55 is inside the 50-day window of days 55..104, read on days 56..105
    assert np.isfinite(d(106)) and np.isfinite(d(120))                                # and out of it afterwards


def test_the_daily_trend_never_reads_the_current_day():
    t, c = daily_prices()
    tr1 = sz.daily_trend(t, c)
    c2 = c.copy()
    c2[60 * 24:] = 999.0                                                              # change day 60 and later
    tr2 = sz.daily_trend(t, c2)
    assert np.allclose(tr1[:60 * 24 + 24], tr2[:60 * 24 + 24], equal_nan=True)       # every bar of day 60 and before is unchanged


# ------------------------------------------------------------------ the R trade

def flat_trade(n=120, p=100.0):
    return [np.full(n, p) for _ in range(4)] + [np.zeros(n)]                         # o, h, l, c, fc


def test_the_target_is_three_risks_away_and_pays_net_of_the_fee():
    o, h, l, c, fc = flat_trade()
    h[12] = 106.5                                                                      # entry 100 at bar 11's open? i = 10 -> entry o[11] = 100; stop 98 -> risk 2% -> target 106
    r = sz.trade_r(10, 1, 98.0, o, h, l, c, fc)
    assert r["hit"] and abs(r["rf"] - 0.02) < 1e-12 and abs(r["gross"] - 0.06) < 1e-12 and abs(r["net"] - (0.06 - sz.FEE)) < 1e-12


def test_a_bar_that_touches_both_stop_and_target_is_a_stop():
    o, h, l, c, fc = flat_trade()
    h[12], l[12] = 107.0, 97.5
    r = sz.trade_r(10, 1, 98.0, o, h, l, c, fc)
    assert not r["hit"] and abs(r["gross"] - (-0.02)) < 1e-12


def test_a_gap_through_the_stop_fills_at_the_open():
    o, h, l, c, fc = flat_trade()
    o[13], h[13], l[13], c[13] = 96.0, 96.5, 95.5, 96.0
    r = sz.trade_r(10, 1, 98.0, o, h, l, c, fc)
    assert abs(r["gross"] - (-0.04)) < 1e-12 and abs(r["net"] - (-0.04 - sz.FEE)) < 1e-12


def test_the_short_mirrors_and_funding_is_charged_to_the_side():
    o, h, l, c, fc = flat_trade()
    l[12] = 93.0                                                                      # short entry 100, stop 102 (risk 2%), target 94
    r = sz.trade_r(10, -1, 102.0, o, h, l, c, fc)
    assert r["hit"] and abs(r["gross"] - 0.06) < 1e-12
    o, h, l, c, fc = flat_trade()
    fc[12:] = 0.4                                                                      # 0.4 of price paid by longs to shorts between the entry and the target bar
    h[12] = 106.5
    long_ = sz.trade_r(10, 1, 98.0, o, h, l, c, fc)
    assert abs(long_["gross"] - (0.06 - 0.004)) < 1e-12                               # a long pays funding: -(0.4 / 100)
    l[12] = 93.0
    h[12] = 100.0
    short_ = sz.trade_r(10, -1, 102.0, o, h, l, c, fc)
    assert abs(short_["gross"] - (0.06 + 0.004)) < 1e-12                              # a short receives it


def test_a_trade_that_runs_out_of_time_closes_72_bars_later():
    o, h, l, c, fc = flat_trade(200)
    c[10 + 72] = 101.0
    r = sz.trade_r(10, 1, 98.0, o, h, l, c, fc)
    assert not r["hit"] and abs(r["gross"] - 0.01) < 1e-12
    c[10 + 72], c[10 + 73] = 100.0, 150.0                                              # a later bar must not be read
    assert abs(sz.trade_r(10, 1, 98.0, o, h, l, c, fc)["gross"]) < 1e-12


def test_a_stop_on_the_wrong_side_of_the_entry_is_no_trade():
    o, h, l, c, fc = flat_trade()
    assert sz.trade_r(10, 1, 100.0, o, h, l, c, fc) is None and sz.trade_r(10, -1, 99.0, o, h, l, c, fc) is None


# ------------------------------------------------------------------ the planted market, end to end

def run_planted(**kw):
    t, o, h, l, c, q = planted_market(**kw)
    ym = np.array(["m"] * N)
    pools = {"m": np.arange(200, 900)}
    rows = sz.coin_events(t, o, h, l, c, q, np.zeros(N), np.zeros(N), np.ones(N, bool), pools, ym, np.random.default_rng(0))
    return (t, o, h, l, c, q), pd.DataFrame(rows)


def test_the_planted_market_has_one_zoned_sweep_and_one_plain_sweep():
    (t, o, h, l, c, q), T = run_planted()
    assert len(T) == 2, T
    T = T.sort_values("t_in").reset_index(drop=True)
    plain, zoned = T.iloc[0], T.iloc[1]
    assert not plain.zoned and not plain.trend_ok and not plain.trend_known       # day 25: fewer than 50 complete days
    assert zoned.zoned and zoned.trend_ok and zoned.trend_known and zoned.side == 1 and not zoned.opp
    assert zoned.t_in == t[1451] and plain.t_in == t[601]                          # in at the NEXT bar's open


def test_the_zoned_events_trades_by_hand():
    (t, o, h, l, c, q), T = run_planted()
    z = T.sort_values("t_in").iloc[1]
    a = sz.atr1h(h, l, c)[1450]
    stop_a, stop_z = 100.5 - 0.25 * a, 99.3 - 0.25 * a                                # zone stop: the zone's low is further than the sweep extreme
    e = o[1451]
    assert abs(z.rf_a - (e - stop_a) / e) < 1e-12 and abs(z.rf_z - (e - stop_z) / e) < 1e-12 and z.rf_z > z.rf_a
    # nothing is hit in the next 72 bars, so each trade closes at bar 1450 + 72's close
    for net, rf in ((z.net_a, z.rf_a), (z.net_z, z.rf_z)):
        assert abs(net - ((c[1450 + 72] / e - 1) - sz.FEE)) < 1e-12
    assert abs(z.net24 - ((c[1450 + 24] / e - 1) - sz.FEE)) < 1e-12 and not z.hit_a and not z.hit_z


def test_the_control_uses_the_same_stop_distance_and_exits():
    (t, o, h, l, c, q), T = run_planted()
    z = T.sort_values("t_in").iloc[1]
    # the control hours sit in the flat quiet area: nothing is hit, the price does not move, so every control is exactly the round-trip fee
    assert abs(z.ctrl_a + sz.FEE) < 1e-12 and abs(z.ctrl_z + sz.FEE) < 1e-12 and abs(z.ctrl24 + sz.FEE) < 1e-12
    plain = T.sort_values("t_in").iloc[0]
    assert np.isnan(plain.net_z) and np.isnan(plain.ctrl_z)                           # an unzoned sweep has no zone trade


def test_a_weak_impulse_leaves_the_sweep_unzoned():
    (_, _, _, _, _, _), T = run_planted(body=2.9)
    assert not T.zoned.any()


# ------------------------------------------------------------------ causality

def test_no_flag_reads_a_later_bar():
    t, o, h, l, c, q = planted_market()
    full_cov = sz.zone_cover(t, h, l, c, sz.zones(*sz.bars4h(t, o, h, l, c)))[1]
    full_tr = sz.daily_trend(t, c)
    for i in (1407, 1408, 1449, 1450, 1462, 1474, 1475, 1500):
        n = i + 1
        cov = sz.zone_cover(t[:n], h[:n], l[:n], c[:n], sz.zones(*sz.bars4h(t[:n], o[:n], h[:n], l[:n], c[:n])))[1]
        assert np.array_equal(cov["ok"][:n], full_cov["ok"][:n]), i
        assert np.array_equal(cov["lo"][:n], full_cov["lo"][:n], equal_nan=True), i
        assert np.array_equal(sz.daily_trend(t[:n], c[:n])[:n], full_tr[:n], equal_nan=True), i
    ok = full_cov["ok"]
    assert not ok[1404:1408].any() and not ok[1449] and ok[1450] and ok[1474] and not ok[1475]


def test_the_sweep_before_the_zone_exists_cannot_be_zoned():
    t, o, h, l, c, q = planted_market()
    o[1405], h[1405], l[1405], c[1405] = 100.0, 100.3, 99.95, 100.2                   # nothing special; the zone only exists from hour 1408
    cov = sz.zone_cover(t, h, l, c, sz.zones(*sz.bars4h(t, o, h, l, c)))[1]
    assert not cov["ok"][:1408].any()


# ------------------------------------------------------------------ the gate on synthetic tables

def synthetic(good, seed=0):
    rng = np.random.default_rng(seed)
    rows = []
    days = pd.date_range("2022-01-01", "2026-06-30", freq="D")
    for side in (1, -1):
        for d in days:
            for _ in range(2):
                zoned = rng.random() < 0.3
                tr = rng.random() < 0.5
                strong = good and zoned and tr
                rf = 0.01
                noise = lambda s: rng.normal(0, s)
                net_z = (0.03 if strong else 0.0) - sz.FEE + noise(0.004) if zoned else np.nan
                rows.append(dict(t_in=d + pd.Timedelta(hours=int(rng.integers(0, 24))), day=d, side=side, zoned=zoned, opp=bool(rng.random() < 0.1), trend_ok=tr,
                                 net24=(0.01 if (good and zoned) else 0.0) + (0.01 if (good and zoned and tr) else 0.0) - sz.FEE + noise(0.01), gross24=0.0,
                                 ctrl24=-sz.FEE + noise(0.01),
                                 rf_a=rf, net_a=-sz.FEE + noise(0.004), gross_a=0.0, hit_a=bool(rng.random() < 0.25), ctrl_a=-sz.FEE + noise(0.004),
                                 ctrl_hit_a=bool(rng.random() < 0.25),
                                 rf_z=rf if zoned else np.nan, net_z=net_z, gross_z=net_z + sz.FEE if zoned else np.nan, hit_z=bool(strong),
                                 ctrl_z=(-sz.FEE + noise(0.004)) if zoned else np.nan, ctrl_hit_z=bool(rng.random() < 0.25), coin="X"))
    return pd.DataFrame(rows)


def gate_line(txt, arm, side):
    """The GATE section's line for one cell (the arms table above it starts the same way)."""
    return [ln for ln in txt.splitlines() if "Holm p" in ln and ln.startswith(f"  {arm} {side}")][0]


def test_noise_passes_nothing_and_a_planted_winner_passes_only_its_cell():
    txt = sz.report(synthetic(False))
    assert "cells passing: 0 of 6" in txt, txt[-900:]
    txt = sz.report(synthetic(True))
    assert gate_line(txt, "C", "LONG ").endswith("->  PASS") and gate_line(txt, "C", "SHORT").endswith("->  PASS")
    assert gate_line(txt, "B", "LONG ").endswith("->  PASS")              # B is also positive and informative in the planted world
    assert gate_line(txt, "A", "LONG ").endswith("->  no") and gate_line(txt, "A", "SHORT").endswith("->  no")      # the plain sweep still loses
    assert "cells passing: 4 of 6" in txt


def test_a_winner_without_information_does_not_pass():
    T = synthetic(True)
    # the zone no longer helps the plain sweep trade: zoned sweeps do WORSE than unzoned on T24 (and so do trend-agreeing ones inside the zone), so the information test must fail
    T["net24"] = -sz.FEE - 0.01 * T.zoned - 0.01 * (T.zoned & T.trend_ok) + np.random.default_rng(5).normal(0, 0.01, len(T))
    txt = sz.report(T)
    assert gate_line(txt, "C", "LONG ").endswith("->  no") and gate_line(txt, "B", "LONG ").endswith("->  no")
    assert "information no" in gate_line(txt, "B", "LONG ")
    assert "cells passing: 0 of 6" in txt


def test_a_winner_that_loses_the_holdout_does_not_pass():
    T = synthetic(True)
    m = (T.t_in >= sz.HOLDOUT) & T.zoned
    T.loc[m, "net_z"] = -sz.FEE - 0.005                                                         # the holdout turns negative (a flip like the repo's old sweep results)
    T.loc[m, "gross_z"] = T.loc[m, "net_z"] + sz.FEE
    txt = sz.report(T)
    assert gate_line(txt, "B", "LONG ").endswith("->  no") and gate_line(txt, "C", "LONG ").endswith("->  no")


# ------------------------------------------------------------------ added after the first review: flags and controls that the planted long market cannot show

def test_an_impulse_must_close_beyond_the_base_not_just_have_a_big_body():
    t4, o4, h4, l4, c4 = with_pair(1.5, 4.0)
    o4[21], c4[21], h4[21], l4[21] = 96.0, 100.7, 100.9, 95.9                       # body 4.7 (big enough) but it closes at 100.7, inside the base [99.25, 100.75]
    assert len(sz.zones(t4, o4, h4, l4, c4)) == 0
    c4[21], h4[21] = 100.9, 101.0                                                      # closing above the base high makes it a zone
    assert len(sz.zones(t4, o4, h4, l4, c4)) == 1


def planted_supply_market():
    """A supply zone: the same base, then a 4h impulse DOWN (100 -> 96), flat near 96, and a LONG sweep at 1450 whose wick goes up to 99.5 (into the zone [99.3, 100.8])."""
    t, o, h, l, c, q = quiet()
    o[1400:1404], c[1400:1404], h[1400:1404], l[1400:1404] = 100.0, 100.0, 100.8, 99.3
    down = [(100.0, 100.1, 98.4, 98.5), (98.5, 98.6, 97.4, 97.5), (97.5, 97.6, 96.4, 96.5), (96.5, 96.6, 95.9, 96.0)]
    for k, (oo, hh, ll, cc) in enumerate(down):
        o[1404 + k], h[1404 + k], l[1404 + k], c[1404 + k] = oo, hh, ll, cc
    o[1408:], h[1408:], l[1408:], c[1408:] = 96.0, 96.5, 95.5, 96.0
    o[1450], h[1450], l[1450], c[1450] = 96.1, 99.5, 94.0, 96.3
    return t, o, h, l, c, q


def test_a_long_sweep_in_a_supply_zone_is_the_opposite_zone_not_zoned():
    t, o, h, l, c, q = planted_supply_market()
    ym = np.array(["m"] * N)
    rows = sz.coin_events(t, o, h, l, c, q, np.zeros(N), np.zeros(N), np.ones(N, bool), {"m": np.arange(200, 900)}, ym, np.random.default_rng(0))
    T = pd.DataFrame(rows)
    z = T[T.t_in == t[1451]].iloc[0]
    assert z.side == 1 and z.opp and not z.zoned and np.isnan(z.net_z)


def test_the_control_stop_distance_is_the_events_own():
    t, o, h, l, c, q = planted_market()
    l[310] = 96.0                                                                      # one dip in the control area: inside the sweep-stop distance of the zone event's A-trade, outside its wider zone stop
    ym = np.array(["m"] * N)
    rows = sz.coin_events(t, o, h, l, c, q, np.zeros(N), np.zeros(N), np.ones(N, bool), {"m": np.array([300])}, ym, np.random.default_rng(0))
    T = pd.DataFrame(rows).sort_values("t_in").reset_index(drop=True)
    z = T.iloc[1]
    e_k = o[301]
    stop_a, stop_z = e_k * (1 - z.rf_a), e_k * (1 - z.rf_z)
    assert stop_z < 96.0 < stop_a, (stop_a, stop_z)                                     # the setup the test needs: 96.0 is between the two stops
    assert abs(z.ctrl_a - ((stop_a / e_k - 1) - sz.FEE)) < 1e-12                       # the control A trade is stopped out at ITS stop distance
    assert abs(z.ctrl_z + sz.FEE) < 1e-12                                                # the control Z trade (wider) is not touched and closes flat
    assert z.ctrl_hit_a is False or not z.ctrl_hit_a


def test_the_daily_trend_flag_by_side():
    assert sz.trend_agrees(1, 0.02) and not sz.trend_agrees(-1, 0.02)
    assert sz.trend_agrees(-1, -0.02) and not sz.trend_agrees(1, -0.02)
    assert not sz.trend_agrees(1, float("nan")) and not sz.trend_agrees(-1, float("nan")) and not sz.trend_agrees(1, 0.0)


def test_a_winner_no_better_than_its_control_does_not_pass():
    T = synthetic(True)
    T["ctrl_z"] = T["net_z"]                                                           # the control earns exactly what the event does: no excess
    txt = sz.report(T)
    assert gate_line(txt, "B", "LONG ").endswith("->  no") and gate_line(txt, "C", "LONG ").endswith("->  no")


def test_a_winner_with_fewer_than_100_holdout_trades_does_not_pass():
    T = synthetic(True)
    keep = ~(T.zoned & (T.t_in >= sz.HOLDOUT))
    drop_idx = T[~keep].index[40:]                                                     # keep only 40 zoned events per ... in the holdout overall (about 20 a side)
    T = T.drop(drop_idx)
    txt = sz.report(T)
    assert gate_line(txt, "B", "LONG ").endswith("->  no") and gate_line(txt, "C", "LONG ").endswith("->  no")


def test_a_marginal_winner_is_not_significant_after_holm():
    T = synthetic(False, seed=3)
    z = T.zoned & T.net_z.notna()
    rng = np.random.default_rng(9)
    # about +0.2R a trade on both halves with 3R of noise a trade: t is around 1.5, not 2.9+, so only the significance clause stops it
    T.loc[z, "net_z"] = 0.0022 + rng.normal(0, 0.03, int(z.sum()))
    T.loc[z, "gross_z"] = T.loc[z, "net_z"] + sz.FEE
    T["net24"] = -sz.FEE + 0.005 * T.zoned + 0.005 * (T.zoned & T.trend_ok) + rng.normal(0, 0.004, len(T))     # the information test is satisfied
    txt = sz.report(T)
    for side in ("LONG ", "SHORT"):
        ln = gate_line(txt, "B", side)
        tune_net = float(ln.split("tune net ")[1].split("R")[0])
        hold_net = float(ln.split("holdout net ")[1].split("R")[0])
        assert tune_net > 0 and hold_net > 0 and "information ok" in ln, ln                # everything but the significance clause is met
        assert ln.endswith("->  no"), ln


def test_the_information_test_must_hold_on_each_half():
    T = synthetic(True)
    m = T.zoned & (T.t_in >= sz.HOLDOUT)
    T.loc[m, "net24"] = T.loc[m, "net24"] - 0.06                                       # the zone's T24 spread turns negative on the holdout only
    txt = sz.report(T)
    assert "information no" in gate_line(txt, "B", "LONG ") and gate_line(txt, "B", "LONG ").endswith("->  no")
    T = synthetic(True)
    m = T.zoned & (T.t_in < sz.HOLDOUT)
    T.loc[m, "net24"] = T.loc[m, "net24"] - 0.06                                       # ... or on the tune half only
    txt = sz.report(T)
    assert "information no" in gate_line(txt, "B", "LONG ") and gate_line(txt, "B", "LONG ").endswith("->  no")


def test_arm_c_is_the_trend_agreeing_part_of_arm_b():
    txt = sz.report(synthetic(True))
    b, c = gate_line(txt, "B", "LONG "), gate_line(txt, "C", "LONG ")
    nb, nc = int(b.split("holdout net ")[1].split("n ")[1].split(",")[0]), int(c.split("holdout net ")[1].split("n ")[1].split(",")[0])
    assert 0.35 < nc / nb < 0.65, (nb, nc)                                              # about half of B's events (trend agrees on half of them in the planted table)
    assert float(c.split("holdout net ")[1].split("R")[0]) > float(b.split("holdout net ")[1].split("R")[0]) + 1.0     # and the planted winners are all in C


def test_events_of_one_coin_and_side_within_12_bars_are_declustered():
    t, o, h, l, c, q = planted_market()
    o[1455], h[1455], l[1455], c[1455] = 100.7, 101.0, 100.0, 100.9                   # a second sweep 5 bars after the first (24-bar low is now 100.5)
    ym = np.array(["m"] * N)
    rows = sz.coin_events(t, o, h, l, c, q, np.zeros(N), np.zeros(N), np.ones(N, bool), {"m": np.arange(200, 900)}, ym, np.random.default_rng(0))
    T = pd.DataFrame(rows)
    assert sorted(T.t_in.tolist()) == [t[601], t[1451]], T.t_in.tolist()                # the 1455 sweep is dropped


# ------------------------------------------------------------------ closing the survivors of the first planted-bug round

def test_a_supply_impulse_must_close_below_the_base():
    t4, o4, h4, l4, c4 = with_pair(1.5, 4.0, up=False)
    o4[21], c4[21], h4[21], l4[21] = 104.0, 99.3, 104.1, 99.2                         # body -4.7, but it closes at 99.3, inside the base [99.25, 100.75]
    assert len(sz.zones(t4, o4, h4, l4, c4)) == 0
    c4[21], l4[21] = 99.0, 98.9                                                        # closing under the base low makes it a zone
    assert len(sz.zones(t4, o4, h4, l4, c4)) == 1


def test_a_close_inside_the_zone_does_not_break_it():
    t, h, l, c = flat_hourly()
    l[50] = 100.5
    c[60] = 100.5                                                                      # closes inside the demand zone [100, 101]: the far edge (100) still holds
    live = np.flatnonzero(sz.zone_cover(t, h, l, c, [(1, t[10], 100.0, 101.0)])[1]["ok"])
    assert live[0] == 50 and live[-1] == 74 and len(live) == 25
    t, h, l, c = flat_hourly()
    h[50] = 108.5
    c[55] = 108.5                                                                      # closes inside the supply zone [108, 109]
    live = np.flatnonzero(sz.zone_cover(t, h, l, c, [(-1, t[10], 108.0, 109.0)])[-1]["ok"])
    assert live[0] == 50 and live[-1] == 74 and len(live) == 25


def test_the_holdout_excess_over_the_control_is_required():
    T = synthetic(True)
    m = T.zoned & (T.t_in >= sz.HOLDOUT)
    T.loc[m, "ctrl_z"] = T.loc[m, "net_z"]                                             # on the holdout the control earns exactly what the zone trade earns
    txt = sz.report(T)
    assert gate_line(txt, "B", "LONG ").endswith("->  no") and gate_line(txt, "C", "LONG ").endswith("->  no")


def test_the_tune_half_must_be_positive_too():
    T = synthetic(True)
    m = T.zoned & (T.t_in < sz.HOLDOUT)
    T.loc[m, "net_z"] = -sz.FEE - 0.004                                                # negative on the tune half, still a strong winner on the holdout
    T.loc[m, "gross_z"] = T.loc[m, "net_z"] + sz.FEE
    T.loc[m, "ctrl_z"] = T.loc[m, "net_z"] - 0.003                                     # ... but still ahead of its control on the tune half, so only the 'net > 0 on both halves' clause can stop it
    txt = sz.report(T)
    assert gate_line(txt, "B", "LONG ").endswith("->  no") and gate_line(txt, "C", "LONG ").endswith("->  no")


def test_the_trend_must_add_information_inside_the_zone_for_arm_c():
    T = synthetic(True)
    m = T.zoned & T.trend_ok & (T.t_in >= sz.HOLDOUT)
    T.loc[m, "net24"] = T.loc[m, "net24"] - 0.015                                      # inside the zone, trend-agreeing sweeps do WORSE than the rest on T24 (holdout)
    txt = sz.report(T)
    assert "information ok" in gate_line(txt, "B", "LONG ") and gate_line(txt, "B", "LONG ").endswith("->  PASS")     # B still adds information (zoned > unzoned)
    assert "information no" in gate_line(txt, "C", "LONG ") and gate_line(txt, "C", "LONG ").endswith("->  no")


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
    print(f"{len(fns)} tests passed")
