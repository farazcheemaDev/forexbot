"""Tests for backtest/rsi80_overlap.py: exit-day booking, the best-day overlap and the bet-bigger line. Offline. Run: python tests/test_rsi80_overlap.py"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import backtest.rsi80_overlap as ov  # noqa: E402


def test_trades_are_booked_on_their_exit_day_at_risk_times_r():
    idx = pd.date_range("2021-01-01", periods=5, freq="D")
    T = pd.DataFrame(dict(t_out=pd.to_datetime(["2021-01-02 04:00", "2021-01-02 20:00", "2021-01-04 08:00", "2021-02-01 00:00"]), net=[2.0, -1.0, 0.5, 9.0]))
    s = ov.daily_book(T, idx, 0.01)
    assert list(s.round(6)) == [0.0, 0.01, 0.0, 0.005, 0.0]                  # two exits on the 2nd net +1R; a trade outside the calendar is dropped


def test_best_day_overlap_reads_the_other_book_on_those_days():
    idx = pd.date_range("2021-01-01", periods=100, freq="D")
    rsi = pd.Series(0.0, index=idx)
    rsi.iloc[[3, 7]] = [0.05, 0.04]
    trend = pd.Series(np.linspace(-0.01, 0.01, 100), index=idx)
    mean, n = ov.best_day_overlap(rsi, trend, n=2, top=0.10)
    assert abs(mean - (trend.iloc[3] + trend.iloc[7]) / 2) < 1e-12 and n == 0      # early days: trend's lowest, not its best 10%
    trend.iloc[7] = 1.0
    assert ov.best_day_overlap(rsi, trend, n=2, top=0.10)[1] == 1
    trend.iloc[3] = 0.0                                                             # an ordinary, middle-of-the-range trend day: not in its best 10%
    assert ov.best_day_overlap(rsi, trend, n=2, top=0.10)[1] == 1


def _base(seed, n=1460):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2020-01-01", periods=n, freq="D")
    return pd.Series(rng.normal(0.002, 0.03, n), index=idx)


def test_a_scaled_machine_sits_on_the_line_and_real_extra_return_sits_above_it():
    base = [_base(s) for s in range(3)]
    on = ov.line_gap(base, [1.3 * b for b in base], None)
    assert on["inside"] and abs(on["gap"]) < 0.03 * on["combo"]["typ"]             # betting bigger IS the line
    extra = ov.line_gap(base, [b + 0.002 for b in base], None)                       # +0.2% a day with no extra risk
    assert extra["gap"] > 0.1 * extra["line_typ"]
    worse = ov.line_gap(base, [b - 0.001 for b in base], None)
    assert worse["gap"] < 0
    half = ov.line_gap(base, [b + 0.002 for b in base], (base[0].index[0], base[0].index[700]))
    assert half["combo"]["typ"] != extra["combo"]["typ"]                             # the half is really cut


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\n{len(tests)} passed")
