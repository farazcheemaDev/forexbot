"""Tests for backtest/fx_round_levels.py: synthetic minute bars where the answer is known.

    python tests/test_fx_round_levels.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backtest import fx_round_levels as m  # noqa: E402

P = 0.0001


def bars(close, start=1_600_000_000_000):
    c = np.asarray(close, float)
    o = np.r_[c[0], c[:-1]]
    h = np.maximum(o, c) + 0.2 * P
    l = np.minimum(o, c) - 0.2 * P
    return pd.DataFrame(dict(t=start + 60_000 * np.arange(len(c)), o=o, h=h, l=l, c=c))


def walk(n, seed, plant=0.0, sd=0.6):
    """Random walk in pips; after the close crosses a big figure (every 100 pips) add `plant` pips a bar for 15 bars in
    the crossing direction (a planted stop cascade)."""
    rng = np.random.default_rng(seed)
    x = np.empty(n)
    x[0] = 1.2050
    push, left = 0.0, 0
    for i in range(1, n):
        x[i] = x[i - 1] + rng.normal(0, sd) * P + push * P
        left -= 1
        if left <= 0:
            push = 0.0
        b0, b1 = np.floor(x[i - 1] / (100 * P)), np.floor(x[i] / (100 * P))
        if plant and b1 != b0:
            push, left = plant * np.sign(b1 - b0), 15
    return bars(x)


def test_cascade_return_sign_and_entry():
    # flat at 1.2098 / 1.2099, cross 1.2100 at bar 70, keep rising 1 pip a bar
    c = [1.2098] * 70 + [1.2101 + 0.0001 * k for k in range(40)]
    d = bars(c)
    idx, r = m.cascade_events(d, 0.0, 100 * P, 5)
    assert list(idx) == [70], idx
    # entry = next open = close of bar 70 = 1.2101; exit = close of bar 75 = 1.2106 -> +5 pips
    assert abs(r[0] / P - 5.0) < 1e-6, r


def test_cascade_short_side():
    c = [1.2102] * 70 + [1.2099 - 0.0001 * k for k in range(40)]
    idx, r = m.cascade_events(bars(c), 0.0, 100 * P, 5)
    assert list(idx) == [70] and abs(r[0] / P - 5.0) < 1e-6, (idx, r)


def test_fade_entry_at_level_and_through():
    # rises to 1.2099.8 (no touch with 0.5-pip through), then a bar with high 1.21006 touches, then falls 1 pip a bar
    c = [1.2090] * 70 + [1.2098, 1.20990] + [1.2099 - 0.0001 * k for k in range(30)]
    d = bars(c)
    d.loc[72, "h"] = 1.21006                         # traded through 1.2100 by 0.6 pip on bar 72
    idx, r = m.fade_events(d, 0.0, 100 * P, 5, 0.5 * P)
    assert list(idx) == [72], idx
    # sell at 1.2100, exit close of bar 77 = 1.2099 - 5 pips = 1.2094 -> +6 pips
    assert abs(r[0] / P - 6.0) < 1e-6, r
    # a touch by only 0.4 pip does not fill
    d.loc[72, "h"] = 1.21004
    idx2, _ = m.fade_events(d, 0.0, 100 * P, 5, 0.5 * P)
    assert 72 not in list(idx2)


def test_fade_not_first_touch_is_skipped():
    c = [1.2090] * 70 + [1.2099] * 30
    d = bars(c)
    d.loc[75, "h"] = 1.21006
    d.loc[90, "h"] = 1.21006                         # second touch 15 bars later: not a first touch in 60
    idx, _ = m.fade_events(d, 0.0, 100 * P, 5, 0.5 * P)
    assert list(idx) == [75], idx


def test_cascade_enters_at_next_open_not_signal_close():
    c = [1.2098] * 70 + [1.2101 + 0.0001 * k for k in range(40)]
    d = bars(c)
    d.loc[71, "o"] = 1.2103                           # the next bar opens 2 pips above the signal close
    idx, r = m.cascade_events(d, 0.0, 100 * P, 5)
    assert abs(r[0] / P - 3.0) < 1e-6, r             # exit 1.2106 - entry 1.2103


def test_cascade_declustered():
    c = [1.2098] * 70 + [1.2101] * 5 + [1.2099] * 5 + [1.2101] * 80
    idx, _ = m.cascade_events(bars(c), 0.0, 100 * P, 5)
    assert list(idx) == [70], idx                    # crosses at 75 and 80 fall inside 60 bars of the first


def test_fade_needs_no_trading_at_level_in_lookback():
    c = [1.2090] * 70 + [1.2099] * 120
    d = bars(c)
    d.loc[76:150, "h"] = 1.21000                      # sits AT the level (no 0.5-pip through) for 75 bars
    d.loc[75, "h"] = 1.21006
    d.loc[160, "h"] = 1.21006                         # 85 bars after the first touch, but it traded at the level just before
    idx, _ = m.fade_events(d, 0.0, 100 * P, 5, 0.5 * P)
    assert list(idx) == [75], idx


def test_gap_excluded():
    c = [1.2098] * 70 + [1.2101 + 0.0001 * k for k in range(40)]
    d = bars(c)
    d.loc[72:, "t"] += 3 * 86_400_000                # weekend gap inside the 5-bar hold
    idx, _ = m.cascade_events(d, 0.0, 100 * P, 5)
    assert len(idx) == 0, idx


def _excess(seed, plant):
    d = walk(200_000, seed, plant=plant)
    r = m.frame("EURUSD", d, "cascade", 0, 15)
    cs = pd.concat([m.frame("EURUSD", d, "cascade", off, 15) for off in m.CONTROL_OFFSETS])
    r["day"] = np.arange(len(r)) // 3                 # synthetic 'days'
    cs["day"] = np.arange(len(cs)) // 3
    return m.excess_t(r, cs)


def test_planted_cascade_is_found_and_null_is_quiet():
    ex, t = _excess(1, plant=0.4)
    assert ex > 0 and t > 3, (ex, t)
    ex0, t0 = _excess(2, plant=0.0)
    assert abs(t0) < 3, (ex0, t0)


def _ticks(bid, spread=0.8 * P, step_ms=10_000):
    bid = np.asarray(bid, float)
    return pd.DataFrame(dict(time_msc=1_600_000_000_000 + step_ms * np.arange(len(bid)), bid=bid, ask=bid + spread))


def test_tick_breakout_long_fill_on_ask_and_exit_on_bid():
    from backtest import fx_round_breakout as B
    flat = [1.2090] * 400                                   # 4,000 s > 60 min of history
    up = [1.20997, 1.21000] + [1.2105] * 200                 # ask = bid + 0.8 pip: 1.21005 / 1.21008 -> trigger 1.21005
    rows = B.tick_events(_ticks(flat + up), P, 0, 15)
    assert len(rows) == 1 and rows[0]["side"] == 1, rows
    r = rows[0]
    assert abs(r["slip"] - 0.0) < 1e-6 and abs(r["spread"] - 0.8) < 1e-6, r
    # fill ask 1.21005, exit bid 1.2105 -> +4.5 pips
    assert abs(r["pips"] - 4.5) < 1e-6, r


def test_tick_breakout_short_and_no_event_when_level_traded_recently():
    from backtest import fx_round_breakout as B
    rows = B.tick_events(_ticks([1.2010] * 400 + [1.19994] + [1.1990] * 200), P, 0, 15)
    assert len(rows) == 1 and rows[0]["side"] == -1, rows      # sell at bid 1.19994 (0.1 pip slip), exit ask 1.19908
    assert abs(rows[0]["slip"] - 0.1) < 1e-6 and abs(rows[0]["pips"] - 8.6) < 1e-6, rows
    # the level was traded 30 minutes earlier -> not a first touch
    rows2 = B.tick_events(_ticks([1.2010] * 300 + [1.1999] * 5 + [1.2010] * 180 + [1.19994] + [1.1990] * 200), P, 0, 15)
    assert rows2 == [], rows2


def test_holm_monotone():
    a = m.holm(np.array([0.01, 0.04, 0.03]))
    assert np.allclose(a, [0.03, 0.06, 0.06]), a


if __name__ == "__main__":
    n = 0
    for name, f in list(globals().items()):
        if name.startswith("test_") and callable(f):
            f()
            n += 1
    print(f"{n} tests passed")
