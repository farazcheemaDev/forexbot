"""Tests for backtest/combo_universe.py: the fixed-bracket scoring (both sides, ties, timeouts, the entry bar, the fee in R) against hand cases and a brute-force loop, and the candidate frame (hours, entry bar, full horizon, the random-entry baseline).

Run as a script (no pytest on this PC):  python tests/test_combo_universe.py     (exit code 0 = all passed)
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import backtest.combo_universe as cu  # noqa: E402

FEE = cu.FEE
H1 = cu.H1


def flat(n, px=100.0):
    return [np.full(n, px, float) for _ in range(4)]                     # o, h, l, c


def one(o, h, l, c, j, side, stop=0.01, target=0.02, hours=4):
    r, st = cu.score_fixed(o, h, l, c, [j], side, stop, target, hours)
    return float(r[0]), int(st[0])


def near(a, b):
    return abs(a - b) < 1e-12


def test_a_long_that_reaches_its_target_first_wins_and_pays_the_target_less_the_fee_in_r():
    o, h, l, c = flat(10)
    h[4] = 102.5                                                         # bar 4 is inside the horizon 3..6 of an entry at bar 3 and touches +2.5% (target +2%)
    r, st = one(o, h, l, c, 3, 1)
    assert st == 1 and near(r, (0.02 - FEE) / 0.01)


def test_a_long_that_reaches_its_stop_first_loses_the_stop_plus_the_fee_in_r():
    o, h, l, c = flat(10)
    l[4] = 98.9                                                          # -1.1% touches the -1% stop
    r, st = one(o, h, l, c, 3, 1)
    assert st == 0 and near(r, -(0.01 + FEE) / 0.01)


def test_a_bar_that_touches_both_levels_is_a_loss_and_an_earlier_target_still_wins():
    o, h, l, c = flat(10)
    h[4], l[4] = 102.5, 98.9                                             # both in one bar: the pessimistic rule says loss
    assert one(o, h, l, c, 3, 1)[1] == 0 and one(o, h, l, c, 3, -1)[1] == 0
    o, h, l, c = flat(10)
    h[4] = 102.5
    l[5] = 98.9                                                          # target in bar 4, stop in bar 5: the target came first
    assert one(o, h, l, c, 3, 1)[1] == 1


def test_the_entry_price_is_the_open_of_the_entry_bar_not_the_previous_close():
    o, h, l, c = flat(10)
    o[3] = 101.0                                                         # the market opens 1% above the previous close
    h[4] = 102.5                                                         # +2.5% from the old close would be a win; from the real entry (101) it is only +1.5%: the target (103.02) is not reached
    r, st = one(o, h, l, c, 3, 1)
    assert st == 2
    h[4] = 103.1
    r, st = one(o, h, l, c, 3, 1)
    assert st == 1 and near(r, (0.02 - FEE) / 0.01)


def test_a_short_mirrors_the_long():
    o, h, l, c = flat(10)
    l[4] = 97.5                                                          # -2.5%: a short's target
    r, st = one(o, h, l, c, 3, -1)
    assert st == 1 and near(r, (0.02 - FEE) / 0.01)
    o, h, l, c = flat(10)
    h[4] = 101.1                                                         # +1.1%: a short's stop
    r, st = one(o, h, l, c, 3, -1)
    assert st == 0 and near(r, -(0.01 + FEE) / 0.01)
    o, h, l, c = flat(10)
    h[4] = 102.5                                                         # the same bar is a long's win and a short's loss
    assert one(o, h, l, c, 3, 1)[1] == 1 and one(o, h, l, c, 3, -1)[1] == 0


def test_the_entry_bar_is_scanned_and_the_bar_before_it_is_not():
    o, h, l, c = flat(10)
    l[3] = 98.9                                                          # the stop is touched in the ENTRY bar (the open is 100)
    assert one(o, h, l, c, 3, 1)[1] == 0
    o, h, l, c = flat(10)
    l[2] = 98.9                                                          # touched in the bar before the entry: irrelevant
    assert one(o, h, l, c, 3, 1)[1] == 2
    o, h, l, c = flat(10)
    h[7] = 102.5                                                         # the horizon is bars 3..6: bar 7 is outside it
    assert one(o, h, l, c, 3, 1)[1] == 2


def test_a_trade_neither_level_touches_exits_at_the_last_bars_close_with_the_fee_and_the_sign_of_its_side():
    o, h, l, c = flat(10)
    c[6] = 100.5                                                         # the close of the last bar of the horizon (3..6)
    r, st = one(o, h, l, c, 3, 1)
    assert st == 2 and near(r, (0.005 - FEE) / 0.01)
    r, st = one(o, h, l, c, 3, -1)
    assert st == 2 and near(r, (-0.005 - FEE) / 0.01)
    c[5] = 90.0                                                          # a close inside the horizon but not the last one: not the exit
    assert near(one(o, h, l, c, 3, 1)[0], (0.005 - FEE) / 0.01)


def test_the_vectorised_scoring_equals_a_brute_force_loop():
    rng = np.random.default_rng(3)
    n = 400
    c = 100 * np.exp(np.cumsum(rng.normal(0, 0.004, n)))
    o = np.r_[c[0], c[:-1]] * (1 + rng.normal(0, 0.003, n))                                              # opens that gap away from the previous close
    h = np.maximum(o, c) * (1 + np.abs(rng.normal(0, 0.002, n)))
    l = np.minimum(o, c) * (1 - np.abs(rng.normal(0, 0.002, n)))
    H = 12
    js = np.arange(5, n - H, 3)
    for side in (1, -1):
        r, st = cu.score_fixed(o, h, l, c, js, side, 0.012, 0.03, H)
        for k, j in enumerate(js):
            e = o[j]
            stop = e * (1 - side * 0.012)
            tgt = e * (1 + side * 0.03)
            out = None
            for b in range(j, j + H):
                hit_s = l[b] <= stop if side > 0 else h[b] >= stop
                hit_t = h[b] >= tgt if side > 0 else l[b] <= tgt
                if hit_s:
                    out = (-(0.012 + FEE) / 0.012, 0)
                    break
                if hit_t:
                    out = ((0.03 - FEE) / 0.012, 1)
                    break
            if out is None:
                out = ((side * (c[j + H - 1] / e - 1) - FEE) / 0.012, 2)
            assert near(r[k], out[0]) and st[k] == out[1], (side, j)


def frame_bars(n=24 * 40):
    rng = np.random.default_rng(1)
    start = int(pd.Timestamp("2023-01-01").timestamp() * 1000)
    out = {}
    for i, s in enumerate(["BTCUSDT", "ETHUSDT"]):
        c = 100 * np.exp(np.cumsum(rng.normal(0, 0.003, n)))
        o = np.r_[c[0], c[:-1]]
        out[s] = pd.DataFrame(dict(o=o, h=np.maximum(o, c) * 1.001, l=np.minimum(o, c) * 0.999, c=c), index=(start + np.arange(n) * H1).astype("int64"))
    return out


def test_candidates_are_made_at_the_four_hours_with_a_closed_bar_before_and_the_whole_horizon_after():
    bars = frame_bars()
    geom = (0.012, 0.024, 24)
    d = cu.candidate_frame(bars, geom)
    hod = (d.made_ms // H1) % 24
    assert set(hod) == {0, 6, 12, 18}
    n = len(bars["BTCUSDT"])
    first_ms, last_ms = bars["BTCUSDT"].index[0], bars["BTCUSDT"].index[-1]
    assert d.made_ms.min() >= first_ms + H1                                                                    # never the very first bar: a closed bar must precede the entry
    assert d.made_ms.max() <= last_ms - 23 * H1                                                                # the full 24-bar horizon must be observed
    per = d.groupby(["symbol", "side"]).size()
    assert len(per) == 4 and per.nunique() == 1                                                                # both sides, both symbols, the same candidate hours
    assert (d.entry.to_numpy() == [bars[s].o.loc[m] for s, m in zip(d.symbol, d.made_ms)]).all()              # the entry is the OPEN of the bar the candidate is stamped with
    assert set(d.status) <= {"WIN", "LOSS", "EXPIRED"} and (d.win == (d.status == "WIN")).all()


def test_the_random_entry_baseline_is_the_hit_rate_of_all_candidates_of_the_same_side_and_quarter():
    d = cu.candidate_frame(frame_bars(), (0.012, 0.024, 24))
    q = d.t.dt.to_period("Q").astype(str)
    for (qq, side), g in d.groupby([q, d.side]):
        assert np.allclose(g.base_p, g.win.mean())
    assert d.base_p.nunique() > 1                                                                              # it differs by side / quarter (not one global number)


def test_the_three_registered_brackets_and_the_fraction_grid():
    assert cu.GEOMS == {"G1": (0.012, 0.024, 24), "G2": (0.012, 0.036, 24), "G3": (0.020, 0.040, 48)}
    assert cu.HOURS == (0, 6, 12, 18) and cu.FRACS == (0.05, 0.10, 0.20) and cu.FEE == 0.0012
    assert cu.KINDS == (("ridge", "P"), ("hgb", "P"), ("hgb", "P+E"))


if __name__ == "__main__":
    tests = sorted((v for k, v in globals().items() if k.startswith("test_")), key=lambda f: f.__code__.co_firstlineno)
    for fn in tests:
        fn()
        print("ok", fn.__name__)
    print(len(tests), "tests passed")
