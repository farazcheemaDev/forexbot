"""Tests for backtest/his_rsi_long.py: candle building from 1-minute bars, closed-candle-only features, the statement clock and warm-up / staleness.

Run as a script (no pytest on this PC):  python tests/test_his_rsi_long.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backtest.his_rsi_long import CELLS, feats, make_bars, to_utc  # noqa: E402
from backtest.his_rsi_long import build_bars  # noqa: E402


def walk(n=6000, seed=3):
    rng = np.random.default_rng(seed)
    return np.arange(n, dtype="int64") * 60_000, 100 + np.cumsum(rng.normal(0, 0.05, n))


def test_build_bars_closes_at_the_last_minute_of_each_candle():
    t = np.arange(15, dtype="int64") * 60_000
    ct, cl = build_bars(t, np.arange(15, dtype=float), 300_000)
    assert list(ct) == [300_000, 600_000, 900_000] and list(cl) == [4.0, 9.0, 14.0]


def test_only_closed_candles_are_read():
    t, c = walk()
    t_dec = 400 * 60_000 * 10 + 30_000                          # 240,030,000 ms, 30 s into a candle
    cut = (t_dec // 300_000) * 300_000                          # the latest end of a closed candle over the two widths
    c2 = c.copy()
    c2[t >= cut] += np.random.default_rng(9).normal(0, 5, int((t >= cut).sum()))   # rewrite the present and the future
    a, b = feats(make_bars(t, c), t_dec, 1), feats(make_bars(t, c2), t_dec, 1)
    assert a is not None and a == b and sorted(a) == sorted(CELLS) and len(a) == 42


def test_a_candle_closing_exactly_at_the_decision_time_is_included():
    t, c = walk()
    B = make_bars(t, c)
    t_dec = 900_000 * 100                                       # a multiple of 15 minutes (so of 5 too): both widths close here, after the 60-candle warm-up
    assert t_dec % 900_000 == 0
    assert feats(B, t_dec, 1) != feats(B, t_dec - 1, 1)


def test_a_sell_sees_the_mirror_image_of_a_buy():
    t = np.arange(6000, dtype="int64") * 60_000
    B = make_bars(t, 100 + 0.01 * np.arange(6000))              # a steady rise
    b, s = feats(B, 120_000_001, 1), feats(B, 120_000_001, -1)
    assert b["5m_rsi5_lvl"] > 99 and s["5m_rsi5_lvl"] < 1
    assert abs(b["15m_rsi14_lvl"] + s["15m_rsi14_lvl"] - 100) < 1e-9


def test_no_features_before_the_warm_up_or_when_the_data_has_stopped():
    t, c = walk()
    B = make_bars(t, c)
    assert feats(B, 600_000, 1) is None                         # 2 closed 5-minute candles
    assert feats(B, 900_000 * 30, 1) is None                    # 5-minute RSI is warm (90 candles) but the 15-minute one has only 30 of the 60 it needs
    assert feats(B, 5_999 * 60_000 + 3 * 900_000, 1) is None    # the last candle closed more than two widths ago (a gap in the market)


def _planted(values, k=300):
    """Bars whose RSI arrays are all 50 except 5-minute RSI(5), which carries `values` (offsets from the last closed candle k at t = (k+1) * 5 minutes)."""
    B = {}
    for name, w in (("5m", 300_000), ("15m", 900_000)):
        rsi = {n: np.full(700, 50.0) for n in (2, 3, 5, 7, 9, 14, 21)}
        B[name] = dict(close_t=(np.arange(700, dtype="int64") + 1) * w, w=w, rsi=rsi)
    arr = np.full(700, 60.0)
    for off, v in values.items():
        arr[k + off] = v
    B["5m"]["rsi"][5] = arr
    return B, (k + 1) * 300_000


def test_hook_is_a_cross_up_through_30_within_the_last_three_candles():
    B, t = _planted({-2: 20.0, -1: 35.0, 0: 50.0})                       # crossed up at k-1
    assert feats(B, t, 1)["5m_rsi5_hook"] is True
    assert feats(B, t, -1)["5m_rsi5_hook"] is False                       # for a seller the same RSI reads 80 / 65 / 50: no cross up through 30
    B, t = _planted({-4: 20.0, -3: 35.0, -2: 50.0, -1: 50.0, 0: 50.0})   # the cross was at k-3: outside the window
    assert feats(B, t, 1)["5m_rsi5_hook"] is False
    B, t = _planted({-3: 20.0, -2: 35.0, -1: 50.0, 0: 50.0})             # the cross at k-2 is inside
    assert feats(B, t, 1)["5m_rsi5_hook"] is True
    B, t = _planted({-2: 40.0, -1: 31.0, 0: 50.0})                       # never below 30: no hook
    assert feats(B, t, 1)["5m_rsi5_hook"] is False


def test_change_is_three_candles():
    B, t = _planted({-3: 40.0, 0: 55.0})
    assert abs(feats(B, t, 1)["5m_rsi5_chg"] - 15.0) < 1e-9
    assert abs(feats(B, t, -1)["5m_rsi5_chg"] - (-15.0)) < 1e-9


def test_the_statement_clock():
    assert to_utc("2026-02-10 12:00:00") == pd.Timestamp("2026-02-10 08:00:00")      # winter: UTC+4
    assert to_utc("2026-04-10 12:00:00") == pd.Timestamp("2026-04-10 07:00:00")      # summer: UTC+5
    assert to_utc("2026-03-15 12:00:00") is None                                      # the changeover weeks are skipped
    assert to_utc("2026-03-08 00:00:00") is None and to_utc("2026-03-28 23:59:59") is None
    assert to_utc("2026-03-29 00:00:00") == pd.Timestamp("2026-03-28 19:00:00")
    assert to_utc("2026-03-07 23:59:59") == pd.Timestamp("2026-03-07 19:59:59")


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        fn()
        print("ok", fn.__name__)
    print(len(tests), "tests passed")
