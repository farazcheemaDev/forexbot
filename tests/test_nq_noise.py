"""Tests for backtest/nq_noise.py: cash-session building across daylight saving, roll handling, VWAP, the reference-trail rule against the original, volume flags and paired statistics.

Run as a script (no pytest on this PC):  python tests/test_nq_noise.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import backtest.nq_noise as nq  # noqa: E402
from backtest.fx_intraday_pub import noise  # noqa: E402


def synth(n_days=30, start="2026-02-23", roll_on=None, double_on=None, seed=4):
    """RTH minute bars (09:30-15:59 New York) for n business days, plus an out-of-session bar each day that must be ignored."""
    rng = np.random.default_rng(seed)
    rows = []
    px = 20000.0
    for k, day in enumerate(pd.bdate_range(start, periods=n_days)):
        open_utc = pd.Timestamp(f"{day.date()} 09:30", tz="America/New_York").tz_convert("UTC")
        iid = 100 + (1 if (roll_on is not None and k >= roll_on) else 0)
        for m in range(-5, 390 + 5):                                    # a few pre-open / post-close minutes
            px *= 1 + rng.normal(0, 0.0002)
            id_ = iid + (7 if (double_on == k and m == 200) else 0)
            rows.append((open_utc + pd.Timedelta(minutes=m), px, px * 1.0001, px * 0.9999, px * 1.00005, 10.0 + (m % 7), id_))
    return pd.DataFrame(rows, columns=["ts_event", "open", "high", "low", "close", "volume", "instrument_id"])


def test_sessions_start_at_0930_new_york_on_both_sides_of_daylight_saving_and_ignore_other_hours():
    d = synth()
    A, dates, prev, roll = nq.build_sessions(d)
    assert A["c"].shape == (30, 390) and len(dates) == 30
    first = d[d.ts_event.dt.tz_convert("America/New_York").dt.strftime("%H:%M") == "09:30"].reset_index(drop=True)
    assert np.allclose(A["o"][:, 0], first.open.to_numpy())             # minute 0 of every session is the 09:30 New York bar, in winter AND after the US clock change
    assert set(first.ts_event.dt.tz_convert("UTC").dt.strftime("%H:%M")) == {"14:30", "13:30"}


def test_a_contract_change_between_sessions_removes_that_sessions_previous_close():
    A, dates, prev, roll = nq.build_sessions(synth(roll_on=10))
    assert roll[10] and np.isnan(prev[10]) and not roll[11] and np.isfinite(prev[11]) and np.isnan(prev[0])


def test_a_session_where_the_contract_changes_inside_it_is_dropped():
    A, dates, prev, roll = nq.build_sessions(synth(double_on=5))
    assert len(dates) == 29


def test_vwap_is_the_volume_weighted_typical_price_and_ignores_empty_minutes():
    A = dict(h=np.array([[12.0, 13.0, 15.0]]), l=np.array([[8.0, 9.0, 10.0]]), c=np.array([[10.0, 11.0, 12.0]]), v=np.array([[1.0, 0.0, 3.0]]))
    vw = nq.vwap_array(A)                                                # typical prices (h + l + c) / 3 = 10, 11, 37/3  (NOT the closes 10, 11, 12)
    assert np.allclose(vw[0], [10.0, 10.0, (10.0 * 1 + (37 / 3) * 3) / 4])
    assert np.allclose(nq.twap_array(A)[0], np.cumsum([10.0, 11.0, 12.0]) / np.arange(1, 4))    # the TWAP stand-in averages the closes


def test_the_reference_rule_with_a_twap_is_exactly_the_original_twap_rule():
    d = synth(n_days=40)
    A, dates, prev, roll = nq.build_sessions(d)
    g, _, n = noise(A, prev, twap=True)
    g2, n2 = nq.noise_ref(A, prev, nq.twap_array(A))
    assert np.allclose(g, g2, atol=1e-12) and np.array_equal(n, n2)


def test_a_vwap_above_the_price_closes_a_long_that_the_bounds_alone_would_hold():
    n, Lm = 16, 390
    C = np.full((n, Lm), 100.0)
    O = C.copy()
    C[-1, 30:90] = 101.0                                                # a breakout long at the first checkpoint (m = 30) ...
    C[-1, 90:] = 103.0                                                  # ... that runs on later
    O[-1, 1:] = C[-1, :-1]
    A = dict(o=O, h=np.maximum(O, C), l=np.minimum(O, C), c=C, v=np.ones((n, Lm)))
    prev = np.r_[np.nan, C[:-1, -1]]
    g_hold, n_hold = nq.noise_ref(A, prev, np.zeros((n, Lm)))           # a reference far below the price never forces an exit
    ref = np.zeros((n, Lm))
    ref[-1, 60] = 102.0                                                 # a VWAP above the price at m = 60 only
    g_trail, n_trail = nq.noise_ref(A, prev, ref)
    assert n_hold[-1] == 1 and abs(g_hold[-1] - (103 / 101 - 1)) < 1e-12                # held all day: 101 -> 103
    assert n_trail[-1] == 2 and abs(g_trail[-1]) < 1e-12                                # stopped out flat at 101 at m = 60, re-entered at 103 at m = 90


def test_volume_flags_use_only_what_is_known_before_the_first_trade():
    n = 40
    dates = pd.bdate_range("2026-01-05", periods=n)
    v = np.ones((n, 390))
    A = dict(v=v.copy())
    base = nq.volume_flags(A, dates)
    A2 = dict(v=v.copy())
    A2["v"][30, :30] = 50.0                                             # a heavy opening on session 30
    f = nq.volume_flags(A2, dates)
    assert f["P4 opening volume"].iloc[30] == 1.0 and base["P4 opening volume"].iloc[30] == 0.0
    assert f["P5 yesterday's volume"].iloc[30] == base["P5 yesterday's volume"].iloc[30]      # today's heavy volume cannot flag today under P5 ...
    assert f["P5 yesterday's volume"].iloc[31] == 1.0                                         # ... only tomorrow
    assert f["P4 opening volume"].iloc[:14].isna().all() and f["P5 yesterday's volume"].iloc[:20].isna().all()


def test_paired_statistics_split_at_the_cut():
    base = np.zeros(100)
    var = np.r_[np.full(50, 0.0002), np.full(50, 0.0004)]
    r = nq.paired(base, var, 50)
    assert abs(r[0] - 3.0) < 1e-9 and abs(r[2] - 2.0) < 1e-9 and abs(r[4] - 4.0) < 1e-9


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        fn()
        print("ok", fn.__name__)
    print(len(tests), "tests passed")
