"""news/mood_now.py offline: a fake Binance, no network."""
import json
import random
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from news import mood_now as mn  # noqa: E402

NOW = datetime(2026, 10, 23, 12, tzinfo=timezone.utc)
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


def test_copies_match_the_backtests_constants():
    from backtest.market_neutral import NON_CRYPTO
    from backtest.wide_book import MIN_AGE_D
    assert mn.NON_CRYPTO == NON_CRYPTO and mn.MIN_AGE_D == MIN_AGE_D


def test_universe_ranks_last_month_volume_old_enough_then_drops_stables_and_caches():
    listed = {"AAAUSDT": ("2024-01-01", 5e6, 1e6), "BBBUSDT": ("2024-01-01", 1e6, 9e9),   # BBB: big TODAY, small in Sept
              "NEWUSDT": ("2026-09-15", 9e9, 9e9),                                         # listed 16 days before Oct 1
              "USDCUSDT": ("2024-01-01", 9e9, 9e9), "CCCUSDT": ("2024-01-01", 3e6, 1e6)}
    pool = Path(tempfile.mkdtemp()) / "pool.json"
    with Patch(POOL=pool, get=fake_binance(listed)):                 # top 3 = USDC, AAA, CCC; USDC then dropped
        assert mn.universe(3, now=NOW) == ["AAAUSDT", "CCCUSDT"]
    assert json.loads(pool.read_text()) == {"2026-10": ["AAAUSDT", "CCCUSDT"]}
    with Patch(POOL=pool, get=lambda u: (_ for _ in ()).throw(AssertionError("cached month must not refetch"))):
        assert mn.universe(3, now=NOW) == ["AAAUSDT", "CCCUSDT"]


def test_pct_rank_is_pandas_rank_pct_ties_included():
    rnd = random.Random(5)
    for _ in range(300):
        v = {f"C{i}": float(rnd.randint(1, 8)) for i in range(rnd.randint(1, 45))}
        want = pd.Series(v).rank(pct=True).to_dict()
        got = mn.pct_rank(v)
        assert got.keys() == want.keys() and all(abs(got[k] - want[k]) < 1e-12 for k in v)


def test_rank_flags_the_crowd_books_quarters():
    rows = [dict(sym=f"C{i}USDT", crowd=float(i), long_share=i / 10, taker=1.0, oi7=0.0) for i in range(1, 9)]
    rows.append(dict(sym="NANUSDT", crowd=None, long_share=None, taker=None, oi7=None))
    R = mn.rank(rows, {"C1USDT": -50.0})
    flags = {r["sym"]: r["flag"] for r in R}
    assert flags["C1USDT"] == flags["C2USDT"] == "SQUEEZE WATCH"           # most short = lowest long / short ratio
    assert flags["C7USDT"] == flags["C8USDT"] == "crowd long"
    assert flags["C4USDT"] == "" and flags["NANUSDT"] == ""
    assert R[0]["sym"] == "C1USDT" and R[0]["fund_yr"] == -50.0 and R[-1]["sym"] == "NANUSDT"


def test_funding_annualises_by_each_coins_interval():
    def get(u):
        if u.endswith("fundingInfo"):
            return [dict(symbol="FOURUSDT", fundingIntervalHours=4)]
        return [dict(symbol="EIGHTUSDT", lastFundingRate="0.0001"), dict(symbol="FOURUSDT", lastFundingRate="0.0001")]
    with Patch(get=get):
        f = mn.funding()
    assert abs(f["EIGHTUSDT"] - 10.95) < 1e-9 and abs(f["FOURUSDT"] - 21.9) < 1e-9


def fuel_klines(moves):
    """35 daily rows per coin: the close 31 rows before the last CLOSED one is 100, the last closed close is 100*(1+move); the
    forming (last) row is a decoy at 1e6 so a gauge that reads the OPEN day lands far away."""
    def get(u):
        s = u.split("symbol=")[1].split("&")[0]
        k = [[0, 0, 0, 0, "100", 0] for _ in range(35)]
        k[-32] = [0, 0, 0, 0, "100", 0]
        k[-2] = [0, 0, 0, 0, str(100 * (1 + moves[s])), 0]
        k[-1] = [0, 0, 0, 0, "1000000", 0]
        return k
    return get


def test_fuel_counts_coins_running_over_30_days_to_the_last_closed_day_with_btc_out():
    moves = {f"C{i}USDT": m for i, m in enumerate([0.25, 0.21, 0.19, 0.0, -0.1, -0.3, -0.5, 0.05, 0.10, 0.5])}
    moves["BTCUSDT"] = 3.0                                              # BTC must not count
    bands = {"q": {k: [i / 100 for i in range(101)] for k in ("runners", "med", "disp")}}
    with Patch(get=fuel_klines(moves)):
        f = mn.fuel(list(moves), bands)
    assert f["n"] == 10, f                                              # BTC dropped
    assert abs(f["runners"] - 0.3) < 1e-9, f                            # 0.25, 0.21, 0.5 are above +20%; 0.19 is not
    assert abs(f["med"] - 0.075) < 1e-9, f                              # median of the ten moves: (0.05 + 0.10) / 2
    assert f["runners_pct"] == 30.0 and f["state"] == "LOW"             # 30 of the 101 grid points are below 0.3; 0.3 <= the 33rd (0.33)


def test_fuel_state_low_mid_high_from_the_historic_terciles_and_none_when_too_few_coins():
    bands = {"q": {k: [i / 100 for i in range(101)] for k in ("runners", "med", "disp")}}
    for share, want in ((0.10, "LOW"), (0.50, "MID"), (0.90, "HIGH")):
        n_run = round(share * 10)
        moves = {f"C{i}USDT": (0.3 if i < n_run else 0.0) for i in range(10)}
        with Patch(get=fuel_klines(moves)):
            assert mn.fuel(list(moves), bands)["state"] == want, (share, want)
    few = {f"C{i}USDT": 0.3 for i in range(5)}
    with Patch(get=fuel_klines(few)):
        assert mn.fuel(list(few), bands) is None                        # under 8 usable coins -> no reading


def test_the_mood_snapshot_survives_a_failing_gauge():
    def boom(syms, bands=None):
        raise RuntimeError("klines down")
    stubs = dict(universe=lambda n: ["AUSDT", "BUSDT"], funding=lambda: {"AUSDT": 1.0},
                 coin=lambda s: dict(sym=s, crowd=1.0, long_share=0.5, taker=1.0, oi7=0.0),
                 fear_greed=lambda: (50, "Neutral"), fuel=boom)
    with Patch(**stubs):
        S = mn.snapshot(2)
    assert S["market"]["fuel"] is None and S["market"]["fear_greed"] == 50 and len(S["coins"]) == 2   # the readout still comes out


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\n{len(tests)} passed")
