"""sweep_zone_daily.py offline: daily bars, daily zones, the 72-hour first-retest window, the zone index and the next-zone target, the explicit-target trade, a planted market end to
end (a supply zone above, a demand zone below, a sweep into the demand zone), a causality (truncation) check and the gate on synthetic tables.
Run as a script: python tests/test_sweep_zone_daily.py"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import sweep_zone_daily as sd  # noqa: E402

NAN = float("nan")


def hours(n):
    return pd.date_range("2024-01-01", periods=n, freq="h").to_numpy("datetime64[ns]")


# ------------------------------------------------------------------ daily bars

def test_daily_bars_aggregate_complete_days_only():
    t = hours(72)
    o = np.arange(72.0) + 100
    h, l, c = o + 2, o - 1, o + 0.5
    td, od, hd, ld, cd = sd.bars1d(t, o, h, l, c)
    assert len(td) == 3 and td[0] == t[0] and td[1] == t[24]
    assert od[0] == 100 and cd[0] == 123.5 and hd[0] == 125 and ld[0] == 99
    keep = np.r_[0:30, 31:72]                                                       # hour 30 missing: day 1 is incomplete
    td2 = sd.bars1d(t[keep], o[keep], h[keep], l[keep], c[keep])[0]
    assert len(td2) == 2 and td2[0] == t[0] and td2[1] == t[48]


# ------------------------------------------------------------------ daily zones

def quiet_days(n=40):
    td = hours(n * 24)[::24]
    return td, np.full(n, 100.0), np.full(n, 101.0), np.full(n, 99.0), np.full(n, 100.0)


def with_pair(base_range, body, up=True, at=20):
    td, od, hd, ld, cd = quiet_days()
    half = base_range / 2
    hd[at], ld[at] = 100 + half, 100 - half
    od[at + 1] = 100.0
    cd[at + 1] = 100.0 + (body if up else -body)
    hd[at + 1], ld[at + 1] = max(od[at + 1], cd[at + 1]) + 0.3, min(od[at + 1], cd[at + 1]) - 0.3
    return td, od, hd, ld, cd


def test_a_daily_demand_zone_is_known_when_the_impulse_day_closes():
    td, od, hd, ld, cd = with_pair(1.5, 4.0)
    zs = sd.zones(td, od, hd, ld, cd)
    assert len(zs) == 1, zs
    side, created, lo, hi = zs[0]
    assert side == 1 and abs(lo - 99.25) < 1e-12 and abs(hi - 100.75) < 1e-12
    assert created == td[21] + np.timedelta64(1, "D")                                # the END of the impulse day


def test_the_daily_supply_zone_mirrors_it():
    zs = sd.zones(*with_pair(1.5, 4.0, up=False))
    assert len(zs) == 1 and zs[0][0] == -1 and abs(zs[0][2] - 99.25) < 1e-12 and abs(zs[0][3] - 100.75) < 1e-12


def test_daily_near_misses_make_no_zone():
    assert len(sd.zones(*with_pair(1.5, 2.9))) == 0 and len(sd.zones(*with_pair(1.5, 3.0))) == 1     # ATR 1.9643: impulse body must reach 2.946
    assert len(sd.zones(*with_pair(2.3, 4.0))) == 0                                                    # a base wider than 1.0 ATR
    td, od, hd, ld, cd = with_pair(1.5, 4.0)
    od[21], cd[21], hd[21], ld[21] = 96.0, 100.7, 100.9, 95.9                         # body 4.7 but it closes inside the base
    assert len(sd.zones(td, od, hd, ld, cd)) == 0
    td, od, hd, ld, cd = with_pair(1.5, 4.0, up=False)
    od[21], cd[21], hd[21], ld[21] = 104.0, 99.3, 104.1, 99.2                         # a supply impulse that closes inside the base
    assert len(sd.zones(td, od, hd, ld, cd)) == 0
    td, od, hd, ld, cd = with_pair(1.5, 4.0)
    td = td.copy()
    td[21:] += np.timedelta64(1, "D")                                                  # a missing day between the base and the impulse
    assert len(sd.zones(td, od, hd, ld, cd)) == 0


# ------------------------------------------------------------------ the live window (72 hours, 180 days)

def flat_hourly(n=5000):
    return hours(n), np.full(n, 105.0), np.full(n, 104.0), np.full(n, 104.5)           # t, h, l, c


def test_a_zone_is_live_from_its_first_retest_for_72_hours():
    t, h, l, c = flat_hourly()
    l[50] = 100.5
    cov = sd.zone_cover(t, h, l, c, [(1, t[10], 100.0, 101.0)])[1]
    live = np.flatnonzero(cov["ok"])
    assert live[0] == 50 and live[-1] == 122 and len(live) == 73, (live[0], live[-1])  # f .. f + 72
    assert not cov["ok"][49] and not cov["ok"][123] and cov["lo"][50] == 100.0 and cov["hi"][122] == 101.0
    assert not sd.zone_cover(t, h, l, c, [(1, t[10], 100.0, 101.0)])[-1]["ok"].any()


def test_a_daily_zone_not_retested_within_180_days_is_dead():
    t, h, l, c = flat_hourly()
    l[10 + 4319] = 100.5
    assert sd.zone_cover(t, h, l, c, [(1, t[10], 100.0, 101.0)])[1]["ok"][10 + 4319]
    t, h, l, c = flat_hourly()
    l[10 + 4320] = 100.5
    assert not sd.zone_cover(t, h, l, c, [(1, t[10], 100.0, 101.0)])[1]["ok"].any()


def test_a_touch_before_creation_a_break_and_a_close_inside_behave():
    t, h, l, c = flat_hourly()
    l[5] = 100.5
    assert not sd.zone_cover(t, h, l, c, [(1, t[10], 100.0, 101.0)])[1]["ok"].any()
    t, h, l, c = flat_hourly()
    l[50] = 100.5
    c[60] = 99.5
    live = np.flatnonzero(sd.zone_cover(t, h, l, c, [(1, t[10], 100.0, 101.0)])[1]["ok"])
    assert live[-1] == 59 and len(live) == 10
    t, h, l, c = flat_hourly()
    l[50] = 100.5
    c[60] = 100.5                                                                       # inside the zone: not a break
    assert np.flatnonzero(sd.zone_cover(t, h, l, c, [(1, t[10], 100.0, 101.0)])[1]["ok"])[-1] == 122
    t, h, l, c = flat_hourly()
    h[50] = 108.5
    c[55] = 109.5
    assert np.flatnonzero(sd.zone_cover(t, h, l, c, [(-1, t[10], 108.0, 109.0)])[-1]["ok"])[-1] == 54


def test_the_most_recently_created_live_zone_wins():
    t, h, l, c = flat_hourly()
    l[50] = 90.0
    zs = [(1, t[10], 100.0, 101.0), (1, t[20], 95.0, 96.0)]
    assert sd.zone_cover(t, h, l, c, zs)[1]["lo"][50] == 95.0 and sd.zone_cover(t, h, l, c, zs[::-1])[1]["lo"][50] == 95.0


# ------------------------------------------------------------------ the zone index and the next-zone target

def test_the_zone_index_finds_the_first_break_within_the_target_life():
    n = 10000
    t, h, l, c = hours(n), np.full(n, 105.0), np.full(n, 104.0), np.full(n, 104.5)
    c[300] = 99.0                                                                       # a close under the demand zone [100, 101]
    zi = sd.zone_index(t, c, [(1, t[100], 100.0, 101.0)])
    assert zi == [(1, 100, 100.0, 101.0, 300)]
    assert sd.zone_index(t, c, [(1, t[400], 100.0, 101.0)])[0][4] == n                 # created after the break: never broken
    c2 = np.full(n, 104.5)
    c2[100 + 8640] = 99.0
    assert sd.zone_index(t, c2, [(1, t[100], 100.0, 101.0)])[0][4] == 100 + 8640      # the last hour of the target life is seen
    c2 = np.full(n, 104.5)
    c2[100 + 8641] = 99.0
    assert sd.zone_index(t, c2, [(1, t[100], 100.0, 101.0)])[0][4] == n                # one hour later is not searched
    cs = np.full(n, 104.5)
    cs[300] = 112.0                                                                     # a close over a SUPPLY zone [110, 111] breaks it
    assert sd.zone_index(t, cs, [(-1, t[100], 110.0, 111.0)])[0][4] == 300


BIG = 10 ** 9


def test_the_next_zone_target_for_a_long():
    zi = [(-1, 100, 110.0, 111.0, BIG), (-1, 100, 108.0, 109.0, BIG), (1, 100, 90.0, 91.0, BIG),
          (-1, 100, 106.0, 107.0, 150), (-1, 300, 105.5, 106.0, BIG), (-1, 100, 102.0, 103.0, BIG)]
    assert sd.next_zone_target(200, 1, 104.0, zi) == 108.0          # nearest supply LOW above the entry; the 106 zone is broken (150), the 105.5 zone is not created yet,
    assert sd.next_zone_target(140, 1, 104.0, zi) == 106.0          # ... 102 is below the entry, the demand zone is the wrong type; at bar 140 the 106 zone is still unbroken
    assert sd.next_zone_target(150, 1, 104.0, zi) == 108.0          # broken AT bar 150: unusable from then
    assert sd.next_zone_target(300, 1, 104.0, zi) == 105.5          # created at 300: usable at 300 (known), and now the nearest
    assert sd.next_zone_target(200, 1, 120.0, zi) is None           # nothing above the entry


def test_the_next_zone_target_for_a_short_and_the_age_limit():
    zi = [(1, 100, 90.0, 95.0, BIG), (1, 100, 96.0, 97.0, BIG), (-1, 100, 120.0, 121.0, BIG), (1, 100, 101.0, 102.0, BIG)]
    assert sd.next_zone_target(200, -1, 100.0, zi) == 97.0          # the HIGHEST demand-zone high below the entry; the 101-102 zone is above it, supply is the wrong type
    assert sd.next_zone_target(100 + 8640, -1, 100.0, zi) == 97.0
    assert sd.next_zone_target(100 + 8641, -1, 100.0, zi) is None   # older than 360 days


# ------------------------------------------------------------------ the target trade

def flat_trade(n=400, p=100.0):
    return [np.full(n, p) for _ in range(4)] + [np.zeros(n)]


def test_the_target_price_pays_its_distance_net_of_the_fee():
    o, h, l, c, fc = flat_trade()
    h[12] = 105.5
    r = sd.trade_rm(10, 1, 98.0, 105.0, o, h, l, c, fc)
    assert r["hit"] and abs(r["gross"] - 0.05) < 1e-12 and abs(r["net"] - (0.05 - sd.FEE)) < 1e-12 and abs(r["rr"] - 2.5) < 1e-12 and abs(r["rf"] - 0.02) < 1e-12


def test_a_bar_touching_both_is_a_stop_and_a_gap_fills_at_the_open():
    o, h, l, c, fc = flat_trade()
    h[12], l[12] = 106.0, 97.5
    r = sd.trade_rm(10, 1, 98.0, 105.0, o, h, l, c, fc)
    assert not r["hit"] and abs(r["gross"] + 0.02) < 1e-12
    o, h, l, c, fc = flat_trade()
    o[13], h[13], l[13], c[13] = 96.0, 96.5, 95.5, 96.0
    assert abs(sd.trade_rm(10, 1, 98.0, 105.0, o, h, l, c, fc)["gross"] + 0.04) < 1e-12


def test_the_short_and_funding():
    o, h, l, c, fc = flat_trade()
    l[12] = 94.5
    r = sd.trade_rm(10, -1, 102.0, 95.0, o, h, l, c, fc)
    assert r["hit"] and abs(r["gross"] - 0.05) < 1e-12
    o, h, l, c, fc = flat_trade()
    fc[12:] = 0.4
    h[12] = 105.5
    assert abs(sd.trade_rm(10, 1, 98.0, 105.0, o, h, l, c, fc)["gross"] - (0.05 - 0.004)) < 1e-12      # a long pays
    l[12], h[12] = 94.5, 100.0
    assert abs(sd.trade_rm(10, -1, 102.0, 95.0, o, h, l, c, fc)["gross"] - (0.05 + 0.004)) < 1e-12     # a short receives


def test_the_hold_is_240_bars_and_a_wrong_sided_stop_or_target_is_no_trade():
    o, h, l, c, fc = flat_trade(600)
    c[10 + 240] = 101.0
    r = sd.trade_rm(10, 1, 98.0, 105.0, o, h, l, c, fc)
    assert not r["hit"] and abs(r["gross"] - 0.01) < 1e-12
    c[10 + 240], c[10 + 241] = 100.0, 150.0
    assert abs(sd.trade_rm(10, 1, 98.0, 105.0, o, h, l, c, fc)["gross"]) < 1e-12
    assert sd.trade_rm(10, 1, 100.0, 105.0, o, h, l, c, fc) is None and sd.trade_rm(10, 1, 98.0, 100.0, o, h, l, c, fc) is None
    assert sd.trade_rm(10, -1, 99.0, 95.0, o, h, l, c, fc) is None and sd.trade_rm(10, -1, 102.0, 100.0, o, h, l, c, fc) is None


def test_tp_at_is_a_multiple_of_the_risk():
    assert sd.tp_at(100.0, 98.0, 3.0, 1) == 106.0 and sd.tp_at(100.0, 102.0, 2.5, -1) == 95.0


# ------------------------------------------------------------------ the planted market, end to end

N = 3120


def daily_market(supply=115.0, break_supply=False):
    """Quiet at 100 (daily ATR 2). A SUPPLY zone from day 20 (base at `supply`, impulse day 21 down by 5), a DEMAND zone from day 60 (base 100.8 / 99.3, impulse day 61 up to 104), flat near 104,
    a long sweep at hour 24*70+5 whose wick (100.5) is inside the demand zone, a run up to the supply zone's near edge ten bars later, and a plain unzoned sweep at day 30."""
    t = hours(N)
    o, h, l, c, q = (np.full(N, v, float) for v in (100.0, 101.0, 99.0, 100.0, 1000.0))
    d = lambda k: slice(24 * k, 24 * k + 24)
    o[d(20)], c[d(20)], h[d(20)], l[d(20)] = supply, supply, supply + 0.8, supply - 0.7
    for k in range(24):
        a, b, i = supply - 5.0 * k / 24, supply - 5.0 * (k + 1) / 24, 24 * 21 + k
        o[i], c[i], h[i], l[i] = a, b, a + 0.05, b - 0.05
    o[d(60)], c[d(60)], h[d(60)], l[d(60)] = 100.0, 100.0, 100.8, 99.3
    for k in range(24):
        a, b, i = 100.0 + 4.0 * k / 24, 100.0 + 4.0 * (k + 1) / 24, 24 * 61 + k
        o[i], c[i], h[i], l[i] = a, b, b + 0.05, a - 0.05
    o[24 * 62:], h[24 * 62:], l[24 * 62:], c[24 * 62:] = 104.0, 104.5, 103.5, 104.0
    S = 24 * 70 + 5
    o[S], h[S], l[S], c[S] = 103.6, 103.8, 100.5, 103.7
    o[S + 10], h[S + 10], l[S + 10], c[S + 10] = 104.0, supply - 0.4, 104.0, supply - 0.6
    P = 24 * 30 + 5
    o[P], h[P], l[P], c[P] = 99.2, 99.9, 98.0, 99.6
    if break_supply:
        c[24 * 40 + 3] = supply + 3.0                                                     # a close over the supply zone's high: it is broken long before the sweep
    return t, o, h, l, c, q, S, P


def run(**kw):
    t, o, h, l, c, q, S, P = daily_market(**kw)
    ym = np.array(["m"] * N)
    rows = sd.coin_events(t, o, h, l, c, q, np.zeros(N), np.zeros(N), np.ones(N, bool), {"m": np.array([1000])}, ym, np.random.default_rng(0))
    T = pd.DataFrame(rows)
    return (t, o, h, l, c, q, S, P), T[(T.t_in == t[S + 1]) | (T.t_in == t[P + 1])].sort_values("t_in").reset_index(drop=True)


def test_the_planted_zoned_sweep_has_its_flags_and_the_next_zone_target():
    (t, o, h, l, c, q, S, P), T = run()
    assert len(T) == 2, T
    plain, z = T.iloc[0], T.iloc[1]
    assert not plain.zoned and not plain.has_target and not plain.trend_known             # day 30: fewer than 50 complete days
    assert z.zoned and z.has_target and z.trend_ok and z.side == 1 and not z.opp
    a = sd.z4.atr1h(h, l, c)[S]
    e = o[S + 1]
    stop_z = 99.3 - 0.25 * a
    tgt = 115.0 - 0.7                                                                      # the supply zone's LOW (114.3)
    assert abs(z.rf_b - (e - stop_z) / e) < 1e-12 and abs(z.rr_b - (tgt - e) / (e - stop_z)) < 1e-12 and z.rr_b >= 1.5
    assert z.hit_b and abs(z.net_b - ((tgt / e - 1) - sd.FEE)) < 1e-12                    # the run to 114.6 reaches the target 114.3
    # the sweep's own trade (3R, further than the high of the run) and the zone-stop 3R trade close flat at the 240-bar limit
    assert not z.hit_a and not z.hit_3 and abs(z.net_a + sd.FEE) < 1e-12 and abs(z.net_3 + sd.FEE) < 1e-12


def test_the_control_copies_the_events_stop_distance_and_reward_to_risk():
    (t, o, h, l, c, q, S, P), T = run()
    z = T.iloc[1]
    assert abs(z.ctrl_b + sd.FEE) < 1e-12 and abs(z.ctrl_a + sd.FEE) < 1e-12 and abs(z.ctrl_3 + sd.FEE) < 1e-12   # a flat quiet hour: nothing is hit
    # a control hour with two dips and one spike. rf_a (the sweep stop) is the TIGHTER distance, rf_b = rf_3 (the zone stop) the wider one:
    #   dip 1 at 3.3% is beyond a 3% stop but not rf_a;  dip 2 at the midpoint of rf_a and rf_b is beyond rf_a but not rf_b;  the spike reaches the B target but no 3R target
    t, o, h, l, c, q, S, P = daily_market()
    k = 1000
    e_k = o[k + 1]
    assert 0.033 < z.rf_a < z.rf_b
    l[k + 30] = e_k * (1 - 0.033)
    l[k + 40] = e_k * (1 - (z.rf_a + z.rf_b) / 2)
    h[k + 50] = e_k * (1 + (z.rr_b + 0.2) * z.rf_b)
    ym = np.array(["m"] * N)
    rows = sd.coin_events(t, o, h, l, c, q, np.zeros(N), np.zeros(N), np.ones(N, bool), {"m": np.array([k])}, ym, np.random.default_rng(0))
    T2 = pd.DataFrame(rows)
    z2 = T2[T2.t_in == t[S + 1]].iloc[0]
    assert not z2.ctrl_hit_a and abs(z2.ctrl_a - (-z.rf_a - sd.FEE)) < 1e-12                  # A control: stopped out by dip 2 at ITS stop distance, not by dip 1
    assert z2.ctrl_hit_b and abs(z2.ctrl_b - (z.rr_b * z.rf_b - sd.FEE)) < 1e-12              # B control: survives both dips (wider stop), then takes the event's own reward:risk
    assert not z2.ctrl_hit_3 and abs(z2.ctrl_3 + sd.FEE) < 1e-12                               # Z3 control: wider stop survives, the 3R target is not reached, closes flat


def test_events_of_one_coin_and_side_within_12_bars_are_declustered():
    t, o, h, l, c, q, S, P = daily_market()
    o[S + 5], h[S + 5], l[S + 5], c[S + 5] = 100.7, 101.0, 100.0, 100.9                      # a second sweep 5 bars after the first (the 24-bar low is now 100.5)
    ym = np.array(["m"] * N)
    rows = sd.coin_events(t, o, h, l, c, q, np.zeros(N), np.zeros(N), np.ones(N, bool), {"m": np.array([1000])}, ym, np.random.default_rng(0))
    T = pd.DataFrame(rows)
    assert (T.t_in == t[S + 6]).sum() == 0 and (T.t_in == t[S + 1]).sum() == 1


def test_a_close_inside_a_zone_does_not_break_it_in_the_target_index_or_the_supply_window():
    n = 10000
    t = hours(n)
    c = np.full(n, 104.5)
    c[300] = 100.5                                                                           # inside the demand zone [100, 101]
    assert sd.zone_index(t, c, [(1, t[100], 100.0, 101.0)])[0][4] == n
    c = np.full(n, 104.5)
    c[300] = 110.5                                                                           # inside the supply zone [110, 111]
    assert sd.zone_index(t, c, [(-1, t[100], 110.0, 111.0)])[0][4] == n
    t, h, l, c = flat_hourly()
    h[50] = 108.5
    c[55] = 108.5                                                                            # inside the supply zone [108, 109] while live
    assert np.flatnonzero(sd.zone_cover(t, h, l, c, [(-1, t[10], 108.0, 109.0)])[-1]["ok"])[-1] == 122


def test_a_broken_supply_zone_gives_no_target():
    _, T = run(break_supply=True)
    z = T.iloc[1]
    assert z.zoned and not z.has_target and np.isnan(z.net_b) and np.isfinite(z.net_3)


def test_a_target_under_1_5r_is_no_trade():
    _, T = run(supply=108.0)                                                               # the supply zone's low is 107.3: about 0.66R away
    z = T.iloc[1]
    assert z.zoned and not z.has_target and np.isnan(z.net_b)


# ------------------------------------------------------------------ causality

def test_no_flag_or_target_reads_a_later_bar():
    t, o, h, l, c, q, S, P = daily_market()
    zs = sd.zones(*sd.bars1d(t, o, h, l, c))
    cov_full, zi_full = sd.zone_cover(t, h, l, c, zs)[1], sd.zone_index(t, c, zs)
    e = 104.0
    for i in (S - 1, S, S + 5, S + 30):
        n = i + 1
        zs_n = sd.zones(*sd.bars1d(t[:n], o[:n], h[:n], l[:n], c[:n]))
        cov = sd.zone_cover(t[:n], h[:n], l[:n], c[:n], zs_n)[1]
        assert np.array_equal(cov["ok"][:n], cov_full["ok"][:n]), i
        assert np.array_equal(cov["lo"][:n], cov_full["lo"][:n], equal_nan=True), i
        zi_n = sd.zone_index(t[:n], c[:n], zs_n)
        assert sd.next_zone_target(i, 1, e, zi_n) == sd.next_zone_target(i, 1, e, zi_full), i
    ok = cov_full["ok"]
    assert not ok[S - 1] and ok[S] and ok[S + 72] and not ok[S + 73]


# ------------------------------------------------------------------ the gate on synthetic tables

def synthetic(good, seed=0):
    rng = np.random.default_rng(seed)
    FEE = sd.FEE
    rows = []
    for side in (1, -1):
        for d in pd.date_range("2022-01-01", "2026-06-30", freq="D"):
            for _ in range(2):
                zoned = rng.random() < 0.3
                tgt = zoned and rng.random() < 0.6
                tr = rng.random() < 0.5
                strong = good and tgt and tr
                rf = 0.02
                nz = lambda s: rng.normal(0, s)
                nb = (0.05 if strong else 0.0) - FEE + nz(0.004) if tgt else NAN
                rows.append(dict(t_in=d + pd.Timedelta(hours=int(rng.integers(0, 24))), day=d, side=side, zoned=zoned, opp=False, trend_ok=tr, trend_known=True,
                                 net24=(0.01 if (good and zoned) else 0.0) + (0.01 if (good and zoned and tr) else 0.0) - FEE + nz(0.01), gross24=0.0, ctrl24=-FEE + nz(0.01),
                                 rf_a=rf, net_a=-FEE + nz(0.004), gross_a=0.0, hit_a=bool(rng.random() < 0.25), ctrl_a=-FEE + nz(0.004), ctrl_hit_a=bool(rng.random() < 0.25),
                                 rf_3=rf if zoned else NAN, net_3=(-FEE + nz(0.004)) if zoned else NAN, gross_3=0.0 if zoned else NAN, hit_3=False,
                                 ctrl_3=(-FEE + nz(0.004)) if zoned else NAN, ctrl_hit_3=False,
                                 has_target=bool(tgt), rr_b=3.0 if tgt else NAN, rf_b=rf if tgt else NAN, net_b=nb, gross_b=nb + FEE if tgt else NAN, hit_b=bool(strong),
                                 ctrl_b=(-FEE + nz(0.004)) if tgt else NAN, ctrl_hit_b=bool(rng.random() < 0.25), coin="X"))
    return pd.DataFrame(rows)


def gate_line(txt, arm, side):
    return [ln for ln in txt.splitlines() if "Holm p" in ln and ln.startswith(f"  {arm} {side}")][0]


def test_noise_passes_nothing_and_a_planted_winner_passes_B_and_C_only():
    txt = sd.report(synthetic(False))
    assert "cells passing: 0 of 6" in txt, txt[-900:]
    txt = sd.report(synthetic(True))
    for arm in ("B", "C"):
        for side in ("LONG ", "SHORT"):
            assert gate_line(txt, arm, side).endswith("->  PASS"), gate_line(txt, arm, side)
    assert gate_line(txt, "A", "LONG ").endswith("->  no") and "cells passing: 4 of 6" in txt


def test_arm_b_needs_a_target_and_c_is_its_trend_agreeing_part():
    T = synthetic(True)
    txt = sd.report(T)
    b, c = gate_line(txt, "B", "LONG "), gate_line(txt, "C", "LONG ")
    nb, nc = int(b.split("holdout net ")[1].split("n ")[1].split(",")[0]), int(c.split("holdout net ")[1].split("n ")[1].split(",")[0])
    assert 0.35 < nc / nb < 0.65, (nb, nc)
    T2 = T.copy()
    T2["has_target"] = False                                                                 # no zoned sweep has a next-zone target: B and C are empty, nothing crashes
    txt2 = sd.report(T2)
    assert "UNDERPOWERED" in gate_line(txt2, "B", "LONG ") and "cells passing: 0 of 6" in txt2


def test_a_winner_that_loses_the_holdout_or_the_tune_half_does_not_pass():
    T = synthetic(True)
    m = T.has_target & (T.t_in >= sd.HOLDOUT)
    T.loc[m, "net_b"] = -sd.FEE - 0.005
    T.loc[m, "gross_b"] = T.loc[m, "net_b"] + sd.FEE
    assert gate_line(sd.report(T), "B", "LONG ").endswith("->  no")
    T = synthetic(True)
    m = T.has_target & (T.t_in < sd.HOLDOUT)
    T.loc[m, "net_b"] = -sd.FEE - 0.004
    T.loc[m, "gross_b"] = T.loc[m, "net_b"] + sd.FEE
    T.loc[m, "ctrl_b"] = T.loc[m, "net_b"] - 0.003                                           # still ahead of its control, so only the net clause can stop it
    assert gate_line(sd.report(T), "B", "LONG ").endswith("->  no")


def test_no_excess_over_the_control_on_either_half_does_not_pass():
    for half in ("tune", "hold"):
        T = synthetic(True)
        m = T.has_target & ((T.t_in < sd.HOLDOUT) if half == "tune" else (T.t_in >= sd.HOLDOUT))
        T.loc[m, "ctrl_b"] = T.loc[m, "net_b"]
        assert gate_line(sd.report(T), "B", "LONG ").endswith("->  no"), half


def test_the_information_test_must_hold_on_each_half_and_for_c_inside_the_zone():
    for half in ("tune", "hold"):
        T = synthetic(True)
        m = T.zoned & ((T.t_in < sd.HOLDOUT) if half == "tune" else (T.t_in >= sd.HOLDOUT))
        T.loc[m, "net24"] = T.loc[m, "net24"] - 0.06
        ln = gate_line(sd.report(T), "B", "LONG ")
        assert "information no" in ln and ln.endswith("->  no"), half
    T = synthetic(True)
    m = T.zoned & T.trend_ok & (T.t_in >= sd.HOLDOUT)
    T.loc[m, "net24"] = T.loc[m, "net24"] - 0.015
    txt = sd.report(T)
    assert gate_line(txt, "B", "LONG ").endswith("->  PASS") and "information no" in gate_line(txt, "C", "LONG ") and gate_line(txt, "C", "LONG ").endswith("->  no")


def test_too_few_holdout_trades_is_underpowered_not_a_pass():
    T = synthetic(True)
    idx = T[T.has_target & (T.t_in >= sd.HOLDOUT)].index[40:]
    T = T.drop(idx)
    txt = sd.report(T)
    assert "UNDERPOWERED" in gate_line(txt, "B", "LONG ") and "cells passing: 0 of 6" in txt
    assert not gate_line(txt, "B", "LONG ").endswith("->  PASS")


def test_a_marginal_winner_is_not_significant_after_holm():
    T = synthetic(False, seed=3)
    z = T.has_target & T.net_b.notna()
    rng = np.random.default_rng(9)
    T.loc[z, "net_b"] = 0.0044 + rng.normal(0, 0.06, int(z.sum()))                         # about +0.22R with 3R of noise: t about 1.5
    T.loc[z, "gross_b"] = T.loc[z, "net_b"] + sd.FEE
    T["net24"] = -sd.FEE + 0.005 * T.zoned + 0.005 * (T.zoned & T.trend_ok) + rng.normal(0, 0.004, len(T))
    txt = sd.report(T)
    for side in ("LONG ", "SHORT"):
        ln = gate_line(txt, "B", side)
        assert float(ln.split("tune net ")[1].split("R")[0]) > 0 and float(ln.split("holdout net ")[1].split("R")[0]) > 0 and "information ok" in ln, ln
        assert ln.endswith("->  no"), ln


def test_a_sweep_that_does_not_wick_into_a_live_zone_is_not_zoned():
    t, o, h, l, c, q, S, P = daily_market()
    f = S - 40
    o[f], h[f], l[f], c[f] = 104.0, 104.2, 100.5, 103.8                                      # the first retest 40 bars earlier (a down bar, so not a sweep itself): the zone is live for 72 bars
    o[S], h[S], l[S], c[S] = 103.6, 103.8, 103.0, 103.7                                      # a sweep of the 24-bar low whose wick stops at 103.0, well above the zone top 100.8
    ym = np.array(["m"] * N)
    rows = sd.coin_events(t, o, h, l, c, q, np.zeros(N), np.zeros(N), np.ones(N, bool), {"m": np.array([1000])}, ym, np.random.default_rng(0))
    T = pd.DataFrame(rows)
    z = T[T.t_in == t[S + 1]].iloc[0]
    assert not z.zoned and not z.has_target
    cov = sd.zone_cover(t, h, l, c, sd.zones(*sd.bars1d(t, o, h, l, c)))[1]
    assert cov["ok"][S] and cov["ok"][f + 72] and not cov["ok"][f + 73]                      # the zone itself IS live at the sweep bar, the wick test is what excludes it


def test_a_long_sweep_whose_wick_reaches_a_supply_zone_is_the_opposite_zone():
    t, o, h, l, c, q, S, P = daily_market()
    h[S] = 114.5                                                                             # the sweep bar's high now reaches the supply zone [114.3, 115.8]
    ym = np.array(["m"] * N)
    rows = sd.coin_events(t, o, h, l, c, q, np.zeros(N), np.zeros(N), np.ones(N, bool), {"m": np.array([1000])}, ym, np.random.default_rng(0))
    T = pd.DataFrame(rows)
    assert T[T.t_in == t[S + 1]].iloc[0].opp
    assert not T[T.t_in == t[P + 1]].iloc[0].opp


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
    print(f"{len(fns)} tests passed")
