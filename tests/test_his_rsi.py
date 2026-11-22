"""Tests for backtest/his_rsi.py: RSI values, direction alignment, closed-candle-only features, the hook window, warm-up and Holm.

Run as a script (no pytest on this PC):  python tests/test_his_rsi.py
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backtest.his_rsi import CELLS, TFS, feats, holm, make_day, rsi_series  # noqa: E402


def test_rsi_known_values():
    r = rsi_series(np.array([0.0, 1.0, 0.0]), 1)               # Wilder with period 1 is the last change itself: flat -> 50, a gain -> 100, a loss -> 0
    assert list(r) == [50.0, 100.0, 0.0]
    assert np.all(rsi_series(np.arange(30, dtype=float), 5)[1:] == 100.0)
    assert rsi_series(np.full(10, 7.0), 3)[-1] == 50.0         # a series that never moved is neutral, not overbought


def test_a_sell_sees_the_mirror_image_of_a_buy():
    ts = np.arange(0, 7200, 1.0)
    D = make_day(ts, 100 + 0.01 * ts)                           # a steady rise
    b, s = feats(D, 5000.5, 1), feats(D, 5000.5, -1)
    assert b["1m_rsi5_lvl"] > 99 and s["1m_rsi5_lvl"] < 1
    assert abs(b["5m_rsi7_lvl"] + s["5m_rsi7_lvl"] - 100) < 1e-9


def test_only_closed_candles_are_read():
    rng = np.random.default_rng(3)
    ts = np.arange(0, 7200, 1.0)
    mid = 100 + np.cumsum(rng.normal(0, 0.05, len(ts)))
    t = 5000.5
    cut = max((t // w) * w for w, _, _ in TFS.values())         # the latest end of a CLOSED candle over the three lengths (15 s: 5000, 1 min: 4980, 5 min: 4800)
    mid2 = mid.copy()
    mid2[ts >= cut] += rng.normal(0, 5, int((ts >= cut).sum()))   # rewrite the present and the future
    a, b = feats(make_day(ts, mid), t, 1), feats(make_day(ts, mid2), t, 1)
    assert a is not None and a == b


def test_no_features_before_the_warm_up_and_all_cells_after():
    ts = np.arange(0, 7200, 1.0)
    D = make_day(ts, 100 + np.sin(ts / 50.0))
    assert feats(D, 600.0, 1) is None                           # 5-minute RSI has only 1 closed candle
    f = feats(D, 6000.5, 1)
    assert f is not None and sorted(f) == sorted(CELLS) and len(f) == 51


def _planted(values):
    """A day whose RSI arrays are all 50 except 1m RSI(5), which carries `values` ending at the last closed candle for t = 7200.5."""
    ts = np.arange(0, 7300, 1.0)
    D = {name: {n: np.full(700, 50.0) for n in ps} for name, (_, _, ps) in TFS.items()}
    k = int(7200.5 // 60) - 1                                    # = 119
    arr = np.full(700, 60.0)
    for off, v in values.items():
        arr[k + off] = v
    D["1m"][5] = arr
    return ts, 100 + 0 * ts, D


def test_hook_is_a_cross_up_through_30_within_the_last_three_candles():
    day = _planted({-2: 20.0, -1: 35.0, 0: 50.0})               # crossed up at k-1
    assert feats(day, 7200.5, 1)["1m_rsi5_hook"] is True
    assert feats(day, 7200.5, -1)["1m_rsi5_hook"] is False      # for a seller the same RSI is 80 / 65 / 50: no cross up through 30
    old = _planted({-4: 20.0, -3: 35.0, -2: 50.0, -1: 50.0, 0: 50.0})   # the cross was at k-3: outside the window
    assert feats(old, 7200.5, 1)["1m_rsi5_hook"] is False
    edge = _planted({-3: 20.0, -2: 35.0, -1: 50.0, 0: 50.0})    # the cross at k-2 is inside
    assert feats(edge, 7200.5, 1)["1m_rsi5_hook"] is True


def test_change_is_three_candles():
    day = _planted({-3: 40.0, 0: 55.0})
    assert abs(feats(day, 7200.5, 1)["1m_rsi5_chg"] - 15.0) < 1e-9
    assert abs(feats(day, 7200.5, -1)["1m_rsi5_chg"] - (-15.0)) < 1e-9


def test_holm_is_monotone_and_matches_hand_computation():
    adj = holm({"a": 0.01, "b": 0.04, "c": 0.03})
    assert abs(adj["a"] - 0.03) < 1e-12 and abs(adj["c"] - 0.06) < 1e-12 and abs(adj["b"] - 0.06) < 1e-12


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print("ok", t.__name__)
    print(len(tests), "tests passed")
