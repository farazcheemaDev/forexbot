"""Offline tests for odds_now.py - the manual-trade setup checker. No network, no table.

What each one guards:
  races_*        the trade replay: target, stop, the same-bar case read as a STOP, a gap through
                 the stop filled at the open, a timeout at the close, fees, and funding counted
                 only for settlements after the entry bar's open
  causal         no feature at bar i moves when the bars after i are changed
  no_overlap     one trade at a time per coin
  planted_edge   prices with a real drift planted after RSI < 30: the verdict must be EDGE
  null           the same prices without the drift: the verdict must be NO EDGE, t under 2.4

    python tests/test_odds_now.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import odds_now as on  # noqa: E402

FEE_R = on.FEE * 100 / 2          # entry 100, R = 2 (atr 1)


def bars(rows):
    """rows: (o, h, l, c) for bars 1..n after a signal bar 0 that closes at 100."""
    o = [100.0] + [r[0] for r in rows]
    h = [100.0] + [r[1] for r in rows]
    l = [100.0] + [r[2] for r in rows]
    c = [100.0] + [r[3] for r in rows]
    return o, h, l, c, [1.0] * len(o)


def race(rows, side, k=1, fund=None):
    o, h, l, c, a = bars(rows)
    code, net, pct, held = on.races(o, h, l, c, a, side, fund, ks=(k,), hold=3)[k]
    return code[0], net[0], held[0]


def test_races_long_target():
    code, net, held = race([(100, 101, 99.5, 100.5), (100.5, 102.5, 100, 102), (102, 103, 101, 102)], 1)
    assert code == 1 and abs(net - (1 - FEE_R)) < 1e-9 and held == 2


def test_races_same_bar_is_a_stop():
    code, net, _ = race([(100, 103, 97, 101), (101, 101, 101, 101), (101, 101, 101, 101)], 1)
    assert code == -1 and abs(net - (-1 - FEE_R)) < 1e-9


def test_races_gap_through_stop_fills_at_open():
    code, net, _ = race([(100, 100.5, 99, 99.5), (96, 96.5, 95, 96), (96, 96, 96, 96)], 1)
    assert code == -1 and abs(net - (-2 - FEE_R)) < 1e-9


def test_races_timeout_at_close():
    code, net, held = race([(100, 101, 99, 100), (100, 101, 99, 100), (100, 101, 99, 101)], 1)
    assert code == 0 and abs(net - (0.5 - FEE_R)) < 1e-9 and held == 3


def test_races_short_mirror():
    code, net, _ = race([(100, 100.5, 99, 99.5), (99.5, 100, 97.5, 98), (98, 98, 98, 98)], -1)
    assert code == 1 and abs(net - (1 - FEE_R)) < 1e-9
    code, net, _ = race([(100, 103, 97, 100), (100, 100, 100, 100), (100, 100, 100, 100)], -1)
    assert code == -1


def test_races_funding_sign_and_window():
    flat = [(100, 101, 99, 100)] * 3
    paid_later = np.cumsum([0, 0, 0.5, 0])           # settlement on bar 2: inside the hold
    at_entry = np.cumsum([0, 0.5, 0, 0])             # settlement at the entry bar's open
    _, long_net, _ = race(flat, 1, fund=paid_later)
    _, short_net, _ = race(flat, -1, fund=paid_later)
    assert abs(long_net - (0 - 0.25 - FEE_R)) < 1e-9    # long pays 0.5 / R 2
    assert abs(short_net - (0 + 0.25 - FEE_R)) < 1e-9   # short receives it
    _, net, _ = race(flat, 1, fund=at_entry)
    assert abs(net - (0 - FEE_R)) < 1e-9


def walk(n, seed, drift=0.0, sigma=0.01):
    """Random walk; if drift, every bar within 12 bars of an RSI(14) < 30 close gets +drift x
    sigma. RSI computed bar by bar exactly as features() does, so the plant sits on the cell."""
    rng = np.random.default_rng(seed)
    c = np.empty(n)
    c[0] = 100.0
    up = dn = 0.0
    left = 0
    a = 1 / 14
    for t in range(1, n):
        mu = drift * sigma if left > 0 else 0.0
        left = max(left - 1, 0)
        c[t] = c[t - 1] * np.exp(mu + sigma * rng.standard_normal())
        d = c[t] - c[t - 1]
        up = (1 - a) * up + a * max(d, 0.0)
        dn = (1 - a) * dn + a * max(-d, 0.0)
        rsi = 100 - 100 / (1 + up / dn) if dn > 0 else 100.0
        if drift and t >= on.WARMUP and rsi < 30:
            left = 12
    o = np.r_[c[0], c[:-1]]
    w = np.abs(rng.standard_normal((2, n))) * 0.003
    h = np.maximum(o, c) * np.exp(w[0])
    l = np.minimum(o, c) * np.exp(-w[1])
    return o, h, l, c


def synthetic_table(drift):
    t = pd.date_range("2021-01-01", periods=20000, freq="h")
    bull = pd.Series(1.0, index=t)
    parts = []
    for s in range(4):
        o, h, l, c = walk(len(t), seed=s, drift=drift)
        d = pd.DataFrame(dict(time=t, o=o, h=h, l=l, c=c))
        parts.append(on.coin_rows(f"C{s}", d, bull))
    tab = pd.concat(parts, ignore_index=True)
    tab["coin"] = tab["coin"].astype("category")
    return tab


def verdict(tab):
    rows = tab[tab["rsi_b"].to_numpy() == 0]
    return on.judge(on.trades(rows, "long", 1), on.trades(tab, "long", 1), on.split_time(tab))


def test_planted_edge_is_found():
    j = verdict(synthetic_table(drift=0.15))
    assert j["edge"], j["why"]


def test_null_is_not_an_edge():
    j = verdict(synthetic_table(drift=0.0))
    assert not j["edge"] and j["all"]["t"] < on.T_EDGE, (j["all"]["t"], j["why"])


def test_causal():
    o, h, l, c = walk(600, seed=9)
    f0 = on.features(o, h, l, c)
    h2, l2, c2 = h.copy(), l.copy(), c.copy()
    c2[301:] *= 1.5
    h2[301:] *= 1.6
    l2[301:] *= 0.5
    f1 = on.features(o, h2, l2, c2)
    for k in ("atr", "rsi", "mom", "loc", "rsi_b", "mom_b", "loc_b", "ok"):
        assert np.array_equal(f0[k][:301], f1[k][:301], equal_nan=True), k
    b0, b1 = on.btc_bull(np.r_[c, c]), on.btc_bull(np.r_[c, c2])
    assert np.array_equal(b0[:901], b1[:901], equal_nan=True)


def test_windows_never_cross_a_hole_in_the_bars():
    o, h, l, c = walk(800, seed=3)
    t = pd.date_range("2021-01-01", periods=800, freq="h")
    t = t.where(np.arange(800) < 400, t + pd.Timedelta(days=21))   # BNX-style 3-week halt
    d = pd.DataFrame(dict(time=t, o=o, h=h, l=l, c=c))
    got = on.coin_rows("X", d, pd.Series(1.0, index=t))
    idx = np.searchsorted(t.as_unit("ns").asi8, pd.DatetimeIndex(got["time"]).as_unit("ns").asi8)
    assert len(got) > 0
    assert not ((idx >= 400 - on.HOLD - 1) & (idx < 400 + on.WARMUP)).any()


def test_no_overlap():
    keep = on.no_overlap(np.array([0, 0, 0, 1, 1]), np.array([0, 1, 5, 0, 2]),
                         np.array([3, 3, 3, 5, 1]))
    assert keep.tolist() == [True, False, True, True, False]


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\n{len(tests)} passed")
