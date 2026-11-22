"""Offline tests for backtest/wait_leverage.py - the liquidation distance, the first-touch rule, the return on margin and the window
alignment. No archive.

    python tests/test_wait_leverage.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backtest import wait_leverage as wl  # noqa: E402


def bars(n=12, price=100.0):
    return [np.full(n, price), np.full(n, price), np.full(n, price), np.full(n, price)]      # o, h, l, c


def test_liquidation_distance_is_one_over_leverage_less_the_maintenance_margin():
    assert abs(wl.liq_distance(100) - 0.005) < 1e-12 and abs(wl.liq_distance(50) - 0.015) < 1e-12 and abs(wl.liq_distance(10) - 0.095) < 1e-12


def test_first_touch_target_liquidation_and_the_bar_that_touches_both():
    o, h, l, c = bars()
    h[3] = 100.5                                                   # long: target +0.30% = 100.3 is reached on bar 3
    code, kk, _ = wl.first_touch(o, h, l, c, [0], 1, 0.015, 0.003, 10)
    assert code[0] == 1 and kk[0] == 3
    o, h, l, c = bars()
    l[2] = 98.0                                                    # liquidation (-1.5% = 98.5) on bar 2, before the target on bar 3
    h[3] = 100.5
    code, kk, _ = wl.first_touch(o, h, l, c, [0], 1, 0.015, 0.003, 10)
    assert code[0] == -1 and kk[0] == 2
    o, h, l, c = bars()
    h[2], l[2] = 100.5, 98.0                                       # both on one bar: liquidated
    code, kk, _ = wl.first_touch(o, h, l, c, [0], 1, 0.015, 0.003, 10)
    assert code[0] == -1 and kk[0] == 2
    o, h, l, c = bars()
    c[10] = 99.0                                                   # neither within the cap: marked at the close of bar E + cap
    code, kk, mark = wl.first_touch(o, h, l, c, [0], 1, 0.015, 0.003, 10)
    assert code[0] == 0 and kk[0] == 10 and abs(mark[0] + 0.01) < 1e-12


def test_a_short_is_the_mirror():
    o, h, l, c = bars()
    l[4] = 99.5                                                    # short target 99.7 on bar 4
    code, kk, _ = wl.first_touch(o, h, l, c, [0], -1, 0.015, 0.003, 10)
    assert code[0] == 1 and kk[0] == 4
    o, h, l, c = bars()
    h[1] = 101.6                                                   # short liquidated at +1.5% = 101.5
    code, kk, _ = wl.first_touch(o, h, l, c, [0], -1, 0.015, 0.003, 10)
    assert code[0] == -1 and kk[0] == 1


def test_returns_on_margin():
    code, kk, mark = np.array([1, -1, 0]), np.array([4, 3, 10]), np.array([0.0, 0.0, -0.02])
    r = wl.margin_returns(code, kk, mark, 1, 50)
    assert abs(r[0] - (0.003 - wl.FEE2 - wl.FUND_H * 4) * 50) < 1e-12 and r[1] == -1.0
    assert abs(r[2] - max(-1.0, (-0.02 - wl.FEE2 - wl.FUND_H * 10) * 50)) < 1e-12 and r[2] == -1.0         # 50x loses everything on -2%
    rs = wl.margin_returns(np.array([1]), np.array([4]), np.array([0.0]), -1, 50)
    assert abs(rs[0] - (0.003 - wl.FEE2) * 50) < 1e-12                                                       # shorts pay no funding here


def test_touch_share_looks_at_the_bars_after_the_entry_only():
    l = np.full(30, 100.0)
    l[10] = 97.0                                                   # one deep low on bar 10
    o = np.full(30, 100.0)
    e = o[1:]
    s = wl.touch_share(l, e, 3, 0.02)
    # entries i whose window i+1 .. i+3 contains bar 10: i = 7, 8, 9 -> 3 of the 27 entries that have 3 bars ahead (i = 0 .. 26)
    assert abs(s - 3 / 27) < 1e-12
    hh = np.full(30, 100.0)
    hh[10] = 103.0
    assert abs(wl.touch_share(hh, e, 3, 0.02, side=-1) - 3 / 27) < 1e-12
    last = np.full(30, 100.0)
    last[29] = 97.0                                                # a low on the very last bar can only be reached from the entry at i = 26
    assert abs(wl.touch_share(last, e, 3, 0.02) - 1 / 27) < 1e-12


if __name__ == "__main__":
    n = 0
    for k, v in sorted(globals().items()):
        if k.startswith("test_") and callable(v):
            v()
            n += 1
            print("ok", k)
    print(n, "tests pass")
