"""news/mood_now.py offline: a fake Binance, no network."""
import json
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from news import mood_now as mn  # noqa: E402

NOW = pd.Timestamp("2026-10-23 12:00", tz="UTC")
MS = lambda s: int(pd.Timestamp(s, tz="UTC").value // 10**6)  # noqa: E731


def fake_binance(listed):
    """listed: {sym: (onboard date, September daily qvol, October daily qvol)}"""
    def get(u):
        if u.endswith("/fapi/v1/exchangeInfo"):
            return {"symbols": [dict(symbol=s, contractType="PERPETUAL", status="TRADING", quoteAsset="USDT",
                                     onboardDate=MS(d)) for s, (d, _, _) in listed.items()]}
        if "/fapi/v1/klines" in u:
            s = u.split("symbol=")[1].split("&")[0]
            d0, sep, octo = listed[s]
            days = pd.date_range(max(pd.Timestamp(d0), pd.Timestamp("2026-08-20")), "2026-10-23", freq="D")
            return [[MS(d), 0, 0, 0, 0, 0, 0, str(sep if d.month == 9 else octo if d.month == 10 else 1e12)] for d in days]
        raise AssertionError(u)
    return get


class Patch:
    """mood_now's module attributes swapped for the test, restored after."""
    def __init__(self, **kw):
        self.kw, self.old = kw, {}

    def __enter__(self):
        for k, v in self.kw.items():
            self.old[k] = getattr(mn, k)
            setattr(mn, k, v)

    def __exit__(self, *a):
        for k, v in self.old.items():
            setattr(mn, k, v)


def test_universe_ranks_last_month_volume_old_enough_and_caches():
    listed = {"AAAUSDT": ("2024-01-01", 5e6, 1e6), "BBBUSDT": ("2024-01-01", 1e6, 9e9),   # BBB: big TODAY, small in Sept
              "NEWUSDT": ("2026-09-15", 9e9, 9e9),                                         # listed 16 days before Oct 1
              "USDCUSDT": ("2024-01-01", 9e9, 9e9), "CCCUSDT": ("2024-01-01", 3e6, 1e6)}
    pool = Path(tempfile.mkdtemp()) / "pool.json"
    with Patch(POOL=pool, get=fake_binance(listed)):
        assert mn.universe(2, now=NOW) == ["AAAUSDT", "CCCUSDT"]
    assert json.loads(pool.read_text()) == {"2026-10": ["AAAUSDT", "CCCUSDT"]}
    with Patch(POOL=pool, get=lambda u: (_ for _ in ()).throw(AssertionError("cached month must not refetch"))):
        assert mn.universe(2, now=NOW) == ["AAAUSDT", "CCCUSDT"]


def test_rank_flags_the_crowd_books_quarters():
    rows = [dict(sym=f"C{i}USDT", crowd=float(i), long_share=i / 10, taker=1.0, oi7=0.0) for i in range(1, 9)]
    rows.append(dict(sym="NANUSDT", crowd=np.nan, long_share=np.nan, taker=np.nan, oi7=np.nan))
    D = mn.rank(rows, {"C1USDT": -50.0})
    flags = dict(zip(D.sym, D.flag))
    assert flags["C1USDT"] == flags["C2USDT"] == "SQUEEZE WATCH"           # most short = lowest long / short ratio
    assert flags["C7USDT"] == flags["C8USDT"] == "crowd long"
    assert flags["C4USDT"] == "" and flags["NANUSDT"] == ""
    assert D.sym.iloc[0] == "C1USDT" and D.fund_yr.iloc[0] == -50.0


def test_funding_annualises_by_each_coins_interval():
    def get(u):
        if u.endswith("fundingInfo"):
            return [dict(symbol="FOURUSDT", fundingIntervalHours=4)]
        return [dict(symbol="EIGHTUSDT", lastFundingRate="0.0001"), dict(symbol="FOURUSDT", lastFundingRate="0.0001")]
    with Patch(get=get):
        f = mn.funding()
    assert abs(f["EIGHTUSDT"] - 10.95) < 1e-9 and abs(f["FOURUSDT"] - 21.9) < 1e-9


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\n{len(tests)} passed")
