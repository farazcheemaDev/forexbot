"""Tests for backtest/premium_dislocation.py - run as a script (no pytest on this PC): python tests/test_premium_dislocation.py"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backtest import premium_dislocation as pd_  # noqa: E402


def frame(n=200, prem=None, c=None):
    t = (np.datetime64("2024-01-01T00") + np.arange(n) * pd_.H).astype("datetime64[ns]")
    return pd.DataFrame({"t": t, "c": np.full(n, 100.0) if c is None else np.asarray(c, float),
                         "prem": np.full(n, 0.0) if prem is None else np.asarray(prem, float)})


def run(X, side=1, fc=None, events=True, rng=None):
    n = len(X)
    return pd_.trades("X", X, np.ones(n, bool), np.zeros(n) if fc is None else fc, side, events=events, rng=rng)


def test_long_event_enters_one_hour_later_and_exits_when_the_gap_closes():
    prem = np.zeros(200); prem[50] = -0.008; prem[51:54] = -0.004          # closes back inside +-0.1% at hour 54
    c = np.full(200, 100.0); c[51] = 95.0; c[52:] = 97.0
    r = run(frame(prem=prem, c=c))
    assert len(r) == 1
    e = r[0]
    assert e["why"] == "closed" and e["hours1"] == 3                        # entry at 51, exit at 54
    assert abs(e["net1"] - (97.0 / 95.0 - 1 - pd_.FEE)) < 1e-12
    assert abs(e["net2"] - (97.0 / 95.0 - 1 - pd_.FEE)) < 1e-12           # 24h later the price is still 97


def test_threshold_side_and_cooldown():
    prem = np.zeros(200); prem[50] = -0.004
    assert run(frame(prem=prem)) == []                                    # -0.4% is inside the 0.5% line
    prem[50] = 0.008
    assert run(frame(prem=prem), side=1) == [] and len(run(frame(prem=prem), side=-1)) == 1
    prem = np.zeros(200); prem[50] = -0.008; prem[60] = -0.008; prem[80] = -0.008
    assert [x["t"] for x in run(frame(prem=prem))] == [frame().t[50], frame().t[80]]     # 60 is inside the 24h pause


def test_short_sign_and_funding():
    prem = np.zeros(200); prem[50] = 0.008
    c = np.full(200, 100.0); c[51:] = 100.0; c[75:] = 90.0
    fc = np.zeros(200); fc[60:] = 0.5                                      # a long pays 0.5 per unit of price over the hold; a short receives it
    e = run(frame(prem=prem, c=c), side=-1, fc=fc)[0]
    assert e["why"] == "closed" and e["hours1"] == 1                       # the premium is back to 0 at hour 52
    assert abs(e["net2"] - (0.10 - pd_.FEE + 0.005)) < 1e-12              # 24h hold: +10% for the short, fee, funding received


def test_a_hole_in_the_bars_is_skipped():
    X = frame()
    X.loc[50, "prem"] = -0.008
    X = X.drop(index=40).reset_index(drop=True)                              # the 24h look-back now spans 25 hours
    assert run(X) == []


def test_control_takes_only_calm_hours_one_a_day():
    class Always:
        def random(self):
            return 0.0
    prem = np.zeros(200); prem[48:60] = -0.004                                # not calm, not an event - from the first hour of day 3
    r = run(frame(prem=prem), events=False, rng=Always())
    days = [x["day"] for x in r]
    assert len(days) == len(set(days)) and all(abs(x["prem"]) <= pd_.CLOSE_BAND for x in r)


def test_clustered_counts_a_day_once():
    m, t, n, g = pd_.clustered([0.01] * 6 + [0.0, 0.02], ["a"] * 6 + ["b", "c"])
    assert n == 8 and g == 3 and abs(m - 0.01) < 1e-12


if __name__ == "__main__":
    k = 0
    for name, f in sorted(globals().items()):
        if name.startswith("test_"):
            f()
            k += 1
    print(f"{k} tests passed")
