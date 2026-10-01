"""Offline test for backtest/his_clock_check.py on a SYNTHETIC market where the answer is planted.

A random-walk NASDAQ (1 point a second, ~60 points an hour) and a trader who wins against it, with
his broker's price = market + a smooth futures basis. His statement times carry the suspected bug:
true UTC + 4 h before the clock change, + 5 h after. The check must find exactly that - and on a
second market with NO bug it must find +5 everywhere, or it would "find" a seasonal error in any
data.

    python tests/test_his_clock_check.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backtest import his_clock_check as hc  # noqa: E402

T0 = pd.Timestamp("2026-01-05")
DAYS = [T0 + pd.Timedelta(days=d) for d in range(0, 170, 7)]          # Jan .. Jun, one sitting a week


def market(seed: int):
    """A 1-second mid around each sitting (14:00-16:00 UTC), looked up like MT5Mid."""
    rng = np.random.default_rng(seed)
    path = {}
    for d in DAYS:
        a = d + pd.Timedelta(hours=11)                                 # wide enough for any offset
        n = 6 * 3600
        path[a] = (a, 25000 + np.cumsum(rng.normal(0, 1.0, n)))

    def mid(t: pd.Timestamp):
        for a, (start, p) in path.items():
            i = int((t - start).total_seconds())
            if 0 <= i < len(p):
                return float(p[i])
        return None
    return mid, rng


def trader(mid, rng, winter_shift_h: float) -> pd.DataFrame:
    """Two trades a sitting, each a winner AGAINST THE REAL MARKET (it picks the side the market then
    moves), +6..+20 points, minus 2 points of cost. Statement time = true UTC + 5 h, or + the winter
    shift before 2026-03-29."""
    rows = []
    for d in DAYS:
        for k in range(2):
            t_open = d + pd.Timedelta(hours=14, minutes=20 + 40 * k, seconds=int(rng.integers(0, 59)))
            hold = int(rng.integers(30, 300))
            t_close = t_open + pd.Timedelta(seconds=hold)
            move = mid(t_close) - mid(t_open)
            if abs(move) < 6:
                continue
            side = "BUY" if move > 0 else "SELL"
            basis = 260 - (t_open - T0).days * 2.5                     # a smooth roll-down
            o = mid(t_open) + basis
            c = mid(t_close) + basis - (2 if side == "BUY" else -2)     # 2 points of cost
            sh = winter_shift_h if t_open < hc.EU_DST else 5.0
            rows.append(dict(open_time=t_open + pd.Timedelta(hours=sh),
                             close_time=t_close + pd.Timedelta(hours=sh),
                             symbol="NASDAQ Mar", side=side, open_price=o, close_price=c))
    x = pd.DataFrame(rows)
    x["sgn"] = np.where(x.side == "BUY", 1, -1)
    x["pts"] = x.sgn * (x.close_price - x.open_price)
    return x


def test_it_finds_a_planted_one_hour_winter_error():
    mid, rng = market(1)
    x = trader(mid, rng, winter_shift_h=4.0)
    s = hc.summarise(hc.measure(x, mid))
    b = hc.best(s)
    assert b["after 29 Mar"] == 5.0, b                                # the control
    assert b["before 08 Mar"] == 4.0 and b["08-29 Mar"] == 4.0, b
    w = s[(s.period == "before 08 Mar")].set_index("offset")
    assert abs(w.loc[4.0, "median_err"] - 2.0) < 0.5, w             # = the planted 2-point cost
    assert w.loc[5.0, "median_err"] > 5.0, w
    assert w.loc[4.0, "market_his_way"] == 1.0 and w.loc[5.0, "market_his_way"] < 0.8, w


def test_no_error_planted_means_none_found():
    mid, rng = market(2)
    x = trader(mid, rng, winter_shift_h=5.0)
    b = hc.best(hc.summarise(hc.measure(x, mid)))
    assert set(b.values()) == {5.0}, b


def test_periods():
    assert hc.period(pd.Timestamp("2026-03-07")) == "before 08 Mar"
    assert hc.period(pd.Timestamp("2026-03-16")) == "08-29 Mar"
    assert hc.period(pd.Timestamp("2026-03-31")) == "after 29 Mar"


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\n{len(tests)} passed")
