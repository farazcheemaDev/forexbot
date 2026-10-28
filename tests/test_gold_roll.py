"""gold_roll.py offline: a synthetic gold market with hand-computed answers, no network. Run as a script: python tests/test_gold_roll.py"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import cot_metals as cm  # noqa: E402
from backtest import gold_roll as gr  # noqa: E402

DAYS = pd.bdate_range("2012-09-03", "2012-12-31")


def synthetic_panel():
    """Dec 2012 (GCZ2) is the active month, Feb 2013 (GCG3) the next, GCJ3 thin. Dec's OI falls from 100,000 to 20,000 by first notice (2012-11-30);
    the spread GCG3 - GCZ2 is 10 at t0 and 14 at F."""
    f = pd.Timestamp("2012-11-30")
    t0 = DAYS[DAYS.get_loc(f) - gr.WINDOW]
    rows = []
    for d in DAYS:
        frac = min(max((d - t0).days / max((f - t0).days, 1), 0.0), 1.0)
        z = 1700.0 + 5.0 * frac
        spread = 10.0 + 4.0 * frac
        rows += [dict(date=d, symbol="GCZ2", settle=z, oi=100000 - 80000 * frac, vol=1, cy=2012, cm=12),
                 dict(date=d, symbol="GCG3", settle=z + spread, oi=10000 + 60000 * frac, vol=1, cy=2013, cm=2),
                 dict(date=d, symbol="GCJ3", settle=z + spread + 8, oi=5000, vol=1, cy=2013, cm=4)]
    return pd.DataFrame(rows), t0, f


def fake_cftc(extra=None):
    idx = pd.date_range("2012-08-07", "2012-12-25", freq="7D")                       # Tuesdays
    df = pd.DataFrame({"mm_long": 60000.0, "mm_short": 10000.0, "mm_net": 0.2}, index=idx)
    if extra is not None:
        df.loc[extra[0], ["mm_long", "mm_short", "mm_net"]] = extra[1]
    return df


def run_cycles(panel, cftc):
    old = cm.cot_frame
    cm.cot_frame = lambda *a, **k: cftc
    try:
        return gr.cycles(panel)
    finally:
        cm.cot_frame = old


def test_the_contract_year_is_the_digit_that_falls_within_the_next_ten_years():
    ts = pd.Timestamp
    assert gr.parse_contract("GCZ6", ts("2026-10-19")) == (2026, 12)
    assert gr.parse_contract("GCM0", ts("2026-10-19")) == (2030, 6)                 # a contract listed years ahead
    assert gr.parse_contract("GCG7", ts("2026-12-15")) == (2027, 2)
    assert gr.parse_contract("GCF1", ts("2020-12-31")) == (2021, 1)                 # across a decade digit
    assert gr.parse_contract("GCZ0", ts("2010-06-07")) == (2010, 12)


def test_a_cycle_has_the_hand_computed_spread_change_stay_and_roll_share():
    panel, t0, f = synthetic_panel()
    c = run_cycles(panel, fake_cftc())
    assert len(c) == 1, c
    r = c.iloc[0]
    assert r["month"] == "2012-12" and r["F"] == "2012-11-30" and r["t0"] == str(t0.date())            # F = the last trading day of November
    assert abs(r["S0"] - 10 / 1700 * 100) < 1e-9 and abs(r["SF"] - 14 / 1705 * 100) < 1e-9
    assert abs(r["dS"] - (14 / 1705 - 10 / 1700) * 100) < 1e-9 and abs(r["dS_usd"] - 400.0) < 1e-6        # (14 - 10) dollars an ounce x 100
    assert abs(r["stay"] - 0.2) < 1e-9 and abs(r["roll_share"] - 50000 / 100000) < 1e-9
    assert abs(r["r"] - np.log(1705 / 1700)) < 1e-12


def test_a_report_must_be_public_before_t0_not_on_it():
    panel, t0, f = synthetic_panel()
    # the report whose release (date + 3 days) is exactly t0 must NOT be used; the one a week earlier is
    on_t0 = t0 - pd.Timedelta(days=3)
    earlier = on_t0 - pd.Timedelta(days=7)
    cftc = fake_cftc(extra=(on_t0, (1000000.0, 0.0, 9.9)))
    c = run_cycles(panel, cftc)
    assert abs(c.iloc[0]["net_lots"] - 50000.0) < 1e-9, c.iloc[0]["net_lots"]                    # the extreme value released on t0 is not read
    assert c.iloc[0]["report"] == str(earlier.date())
    cftc2 = fake_cftc(extra=(earlier, (1000000.0, 0.0, 9.9)))
    assert abs(run_cycles(panel, cftc2).iloc[0]["net_lots"] - 1000000.0) < 1e-9                  # the one released the week before IS read


def test_a_delivery_month_that_is_not_the_active_one_makes_no_cycle():
    panel, t0, f = synthetic_panel()
    panel.loc[(panel.symbol == "GCG3") & (panel.date <= t0), "oi"] = 500000.0                     # at t0 the NEXT month is the biggest
    assert run_cycles(panel, fake_cftc()).empty
    panel3, t0, f = synthetic_panel()
    panel3.loc[(panel3.symbol == "GCG3") & (panel3.date <= t0), "oi"] = 120000.0                  # M still holds 44% of the total, but the next month holds more
    assert run_cycles(panel3, fake_cftc()).empty
    panel2, _, _ = synthetic_panel()
    assert run_cycles(panel2[panel2.date < f], fake_cftc()).empty                                 # no data at first notice: no cycle, not a guess


def test_the_spearman_and_the_permutation_p_follow_the_registered_sign():
    x = np.arange(40.0)
    assert abs(gr.spearman(x, x) - 1.0) < 1e-12 and abs(gr.spearman(x, -x) + 1.0) < 1e-12
    rng = np.random.default_rng(3)
    assert gr.perm_p(x, x, 1.0, +1, rng, n=500) < 0.01                                            # a perfect relation is never matched by a shuffle
    y = rng.normal(size=40)
    up, down = gr.perm_p(x, y, gr.spearman(x, y), +1, rng, n=4000), gr.perm_p(x, y, gr.spearman(x, y), -1, rng, n=4000)
    assert abs(up + down - 1.0) < 0.06                                                              # the two one-sided p-values of a noise relation add up to about one
    assert gr.perm_p(x, -x, gr.spearman(x, -x), -1, rng, n=500) < 0.01                             # significant in the negative direction when asked for it
    assert gr.perm_p(x, -x, gr.spearman(x, -x), +1, rng, n=500) > 0.99


def test_the_verdict_needs_p_the_same_sign_on_both_halves_and_a_positive_trade_on_both():
    ok = dict(dS=dict(p=0.01, tune=0.2, hold=0.1), trade=dict(tune=10.0, hold=5.0))
    assert gr.verdict(ok).startswith("LEAD")
    assert gr.verdict(dict(ok, dS=dict(p=0.2, tune=0.2, hold=0.1))).startswith("NO LEAD")
    assert gr.verdict(dict(ok, dS=dict(p=0.01, tune=0.2, hold=-0.1))).startswith("NO LEAD")
    assert gr.verdict(dict(ok, trade=dict(tune=10.0, hold=-1.0))).startswith("NO LEAD")


def test_the_spread_trade_follows_the_crowds_side_and_pays_the_cost():
    c = pd.DataFrame(dict(month=["a", "b", "c", "d"], roll_share=[0.3, -0.3, 0.2, -0.2], dS=[0.1, -0.1, 0.1, -0.1], dS_usd=[100.0, -100.0, 100.0, -100.0],
                          r=[0.0] * 4, stay=[0.2] * 4))
    res = gr.run(c, np.random.default_rng(1))
    assert abs(res["trade"]["mean"] - (100.0 - gr.SPREAD_COST)) < 1e-9 and res["trade"]["hit"] == 1.0           # net long -> long the spread (+100); net short -> short it (+100)
    c["dS_usd"] = [-100.0, 100.0, -100.0, 100.0]
    assert gr.run(c, np.random.default_rng(1))["trade"]["mean"] < 0


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\n{len(tests)} passed")
