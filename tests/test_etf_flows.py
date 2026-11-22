"""Offline tests for backtest/etf_flows.py - holiday rows, the causal percentile, the entry time, the day windows, a cell's selection /
net / excess / overlap handling, and the pass rule. Synthetic data only.

    python tests/test_etf_flows.py
"""
from __future__ import annotations

import sys
from math import sqrt
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backtest import etf_flows as ef  # noqa: E402
from backtest import options_expiry as ox  # noqa: E402

H = ox.H


def ms(s):
    return int(pd.Timestamp(s, tz="UTC").value // 10**6)


def test_holiday_rows_are_dropped(tmp=Path(__file__).resolve().parent / "_etf_tmp.csv"):
    pd.DataFrame({"day": ["2024-01-12", "2024-01-15", "2024-01-16"], "total": [203.0, 0.0, -10.0],
                  "ibit": [386.0, np.nan, np.nan], "gbtc": [-484.1, np.nan, -10.0]}).to_csv(tmp, index=False)
    try:
        d = ef.load_flows(tmp)
    finally:
        tmp.unlink()
    assert d.day.dt.strftime("%Y-%m-%d").tolist() == ["2024-01-12", "2024-01-16"]          # 15 Jan: every fund '-'


def test_the_percentile_uses_only_earlier_days():
    x = [1.0, 2.0, 3.0, 4.0, 2.0, 10.0, 3.0]
    p = ef.percentiles(x, lookback=4)
    assert np.isnan(p[:4]).all()
    assert abs(p[4] - (1 + 0.5) / 4) < 1e-12                                           # 2 vs [1, 2, 3, 4]: one below, one tie
    assert p[5] == 1.0 and abs(p[6] - 1.5 / 4) < 1e-12                                 # 3 vs [3, 4, 2, 10]: one below, one tie
    y = list(x)
    y[6] = 999.0
    assert np.allclose(ef.percentiles(y, lookback=4)[:6], p[:6], equal_nan=True)         # a later value never moves an earlier one


def test_entry_is_14_utc_the_next_calendar_day():
    assert ef.entry_ms(pd.Timestamp("2024-03-15")) == ms("2024-03-16 14:00")           # Friday's flows -> Saturday
    assert ef.entry_ms(pd.Timestamp("2024-12-31")) == ms("2025-01-01 14:00")


def test_the_day_windows():
    d = pd.Timestamp("2024-03-15")
    px = {ms("2024-03-15"): 100.0, ms("2024-03-16"): 103.0, ms("2024-03-10"): 80.0}
    assert abs(ef.day_return(px, d) - 0.03) < 1e-12
    assert abs(ef.prev_return(px, d, 5) - (100 / 80 - 1)) < 1e-12
    assert np.isnan(ef.prev_return(px, d, 4))


def _frame():
    rng = np.random.default_rng(2)
    n = 40
    D = pd.DataFrame({"pct": np.tile([0.9, 0.1, 0.75, 0.85], n // 4), "r24": rng.normal(0, 0.02, n), "r72": rng.normal(0, 0.03, n)})
    D["half"] = np.where(np.arange(n) < 24, "tu", "ho")
    return D


def test_a_cell_selects_by_side_nets_costs_and_measures_excess_over_all_days():
    D = _frame()
    c = ef.cell(D, 1, 24)
    tu = D[D.half == "tu"]
    x = tu.r24[tu.pct >= 0.8].to_numpy()
    assert c["tu"]["n"] == len(x) == 12
    assert abs(c["tu"]["net"] - (x.mean() - ox.FEE - ox.FUND_PER_H * 24)) < 1e-12
    assert abs(c["tu"]["excess"] - (x.mean() - tu.r24.mean())) < 1e-12
    s = ef.cell(D, -1, 24)
    y = -tu.r24[tu.pct <= 0.2].to_numpy()
    assert s["tu"]["n"] == 6 and abs(s["tu"]["excess"] - (y.mean() - (-tu.r24).mean())) < 1e-12
    z = ef.cell(D, 1, 72)
    w = tu.r72[tu.pct >= 0.8].to_numpy() - ox.FEE - ox.FUND_PER_H * 72
    v = w[::3]
    assert abs(z["tu"]["net_t"] - v.mean() / (v.std(ddof=1) / sqrt(len(v)))) < 1e-9          # overlapping 72h: every 3rd entry


def test_the_pass_rule():
    def half(net=5e-3, t=2.5, ex=1e-3):
        return dict(net=net, net_t=t, excess=ex)
    assert ef.passes(dict(tu=half(), ho=half()), 0.01) and not ef.passes(dict(tu=half(), ho=half()), 0.05)
    for kw in (dict(net=-1e-4), dict(t=1.99), dict(ex=-1e-4)):
        assert not ef.passes(dict(tu=half(**kw), ho=half()), 0.01) and not ef.passes(dict(tu=half(), ho=half(**kw)), 0.01), kw


def test_build_splits_60_40_after_the_warm_up():
    days = pd.date_range("2024-01-01", periods=80, freq="D")
    fl = pd.DataFrame({"day": days, "total": np.arange(80, dtype=float)})
    D = ef.build(fl, {})
    assert len(D) == 20 and (D.half == "tu").sum() == 12 and D.pct.eq(1.0).all()          # rising flows: always the top
    assert D.day.iloc[0] == days[60]


if __name__ == "__main__":
    n = 0
    for k, v in sorted(globals().items()):
        if k.startswith("test_") and callable(v):
            v()
            n += 1
            print("ok", k)
    print(n, "tests passed")
