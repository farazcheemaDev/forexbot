"""cot_metals.py / positioning_lean.py offline: synthetic series, no network. Run as a script: python tests/test_cot_metals.py"""
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import cot_metals as cm  # noqa: E402
import positioning_lean as pl  # noqa: E402


def daily(start: str, values: dict, n: int = 40) -> pd.Series:
    """Business-day closes from `start`; `values` overrides specific dates (YYYY-MM-DD) with a price, everything else 100."""
    idx = pd.bdate_range(start, periods=n)
    s = pd.Series(100.0, index=idx)
    for k, v in values.items():
        s[pd.Timestamp(k)] = v
    return s


def test_the_rank_reads_only_weeks_up_to_today():
    rng = np.random.default_rng(1)
    x = rng.normal(size=300)
    r_all = cm.causal_rank(x)
    y = x.copy()
    y[200:] = 99.0                                                    # change everything after week 199: ranks before it must not move
    r_chg = cm.causal_rank(y)
    assert np.allclose(r_all[:200], r_chg[:200], equal_nan=True)
    assert np.isnan(r_all[:cm.MIN_N - 1]).all() and not np.isnan(r_all[cm.MIN_N:]).any()          # no rank until two years of weeks exist
    z = np.arange(300.0)                                              # a value above everything before it is the top of its window
    assert cm.causal_rank(z)[250] == 1.0 and cm.causal_rank(-z)[250] == 1 / cm.WIN


def test_the_first_trade_is_the_close_after_the_friday_release_not_the_report_tuesday():
    # report Tuesday 2026-10-20 -> public Friday 10-23 -> first trade = Monday 10-26's close; held 2 trading days -> Wednesday 10-28's close
    px = daily("2026-10-12", {"2026-10-20": 50.0, "2026-10-23": 1000.0, "2026-10-26": 100.0, "2026-10-27": 105.0, "2026-10-28": 110.0})
    got = cm.fwd_returns([pd.Timestamp("2026-10-20")], px, h=2)[0]
    assert abs(got - (np.log(110 / 100) - cm.COST)) < 1e-12, got        # Friday's 1000 and Tuesday's 50 are not used: nothing known before Friday evening trades
    # a report whose Friday is a holiday with no bar: the next bar after the release date is used
    px2 = daily("2026-10-12", {"2026-10-26": 100.0, "2026-10-27": 120.0}).drop(pd.Timestamp("2026-10-23"))
    assert abs(cm.fwd_returns([pd.Timestamp("2026-10-20")], px2, h=1)[0] - (np.log(1.2) - cm.COST)) < 1e-12
    assert np.isnan(cm.fwd_returns([pd.Timestamp("2026-10-20")], px, h=500)[0])                  # not enough future: no number, not a short window


def test_the_p_value_is_one_sided_in_the_registered_direction():
    null = np.array([-0.3, -0.1, 0.0, 0.1, 0.2])
    assert abs(cm.p_one_sided(0.2, null, +1) - 0.2) < 1e-12           # only 0.2 is as high
    assert abs(cm.p_one_sided(-0.3, null, -1) - 0.2) < 1e-12          # only -0.3 is as low
    assert cm.p_one_sided(0.2, null, -1) == 1.0 and cm.p_one_sided(float("nan"), null, +1) != cm.p_one_sided(float("nan"), null, +1)


def test_a_signal_passes_only_with_p_sign_on_both_halves_and_the_holdout_buckets_ordered():
    base = dict(p=0.01, ic=-0.2, ic_tune=-0.2, ic_hold=-0.1, sign=-1, low_hold=(0.02, 0.6, 10), high_hold=(-0.01, 0.4, 10))
    assert cm.passes("S1", base)
    assert not cm.passes("S1", dict(base, p=0.2))                                         # not significant
    assert not cm.passes("S1", dict(base, ic_hold=+0.1))                                  # the holdout flipped sign
    assert not cm.passes("S1", dict(base, low_hold=(-0.02, 0.4, 10)))                     # crowded-short bucket below the crowded-long one
    s2 = dict(p=0.01, ic=0.2, ic_tune=0.2, ic_hold=0.1, sign=+1, low_hold=(-0.01, 0.4, 10), high_hold=(0.02, 0.6, 10))
    assert cm.passes("S2", s2) and not cm.passes("S2", dict(s2, ic_tune=-0.1))
    s3 = dict(p=0.01, ic=0.2, ic_tune=0.2, ic_hold=0.1, sign=+1)
    assert cm.passes("S3", s3) and not cm.passes("S3", dict(s3, p=0.06))


def test_first_notice_is_the_last_business_day_of_the_month_before_the_delivery_month():
    assert pl.first_notice("DEC 26") == date(2026, 11, 30)            # a Monday
    assert pl.first_notice("JAN 27") == date(2026, 12, 31)            # across the year end
    assert pl.first_notice("MAR 27") == date(2027, 2, 26)             # Feb 28 2027 is a Sunday: the Friday before
    assert pl.first_notice("JUL 27") == date(2027, 6, 30)
    assert pl.ordinal(0.42) == "42nd" and pl.ordinal(0.11) == "11th" and pl.ordinal(0.03) == "3rd" and pl.ordinal(0.28) == "28th"


def test_the_cme_view_finds_the_delivery_month_its_share_and_which_side_the_calendar_pays():
    def row(m, settle, oi):
        return dict(product="PA", trade_date="10/27/2026", type="Final", month=m, settle=settle, volume="1", open_interest=oi)
    snap = {"PA": [row("NOV 26", "1022.7", "11"), row("DEC 26", "1028.5", "24137"), row("MAR 27", "1040.5", "1887"), row("Total", "-", "26209")]}
    v = pl.cme_view("PA", date(2026, 10, 27), snap)
    assert v["active"] == "DEC 26" and abs(v["share"] - 24137 / 26209) < 1e-12 and v["fnd"] == "2026-11-30" and v["days_to_fnd"] == 34
    assert v["next"] == "MAR 27" and abs(v["spread"] - 12.0) < 1e-9                     # the NEXT delivery month after first notice, priced over it: contango
    assert pl.cme_view("GC", date(2026, 10, 27), snap) is None


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\n{len(tests)} passed")
