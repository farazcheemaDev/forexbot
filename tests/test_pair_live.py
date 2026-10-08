"""Offline tests for pair_live.py on a fake exchange. No network.

  daily     a daily breakout opens a paper position; a later close under the 30-day mean closes it
  breadth   4 coins capitulating -> no buy; 6 coins -> buys; the +5% target closes one
  closed    the still-forming bar is never used

    python tests/test_pair_live.py
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pair_live as pl  # noqa: E402

DAY, H4 = 86_400_000, 14_400_000


class FakeEx:
    def __init__(self):
        self.d, self.h4, self.last = {}, {}, {}

    def fetch_tickers(self):
        return {s: {"quoteVolume": 1e6} for s in self.d}

    def fetch_ohlcv(self, s, tf, limit):
        return (self.d if tf == "1d" else self.h4)[s][-limit:]

    def fetch_ticker(self, s):
        return {"last": self.last[s]}


def series(closes, step, end, vols=None):
    """OHLCV rows whose LAST row is still forming (opens at `end`), the rest closed."""
    n = len(closes)
    rows = []
    for k, c in enumerate(closes):
        t = end - (n - 1 - k) * step
        o = closes[k - 1] if k else c
        rows.append([t, o, max(o, c) * 1.001, min(o, c) * 0.999, c, (vols[k] if vols else 100.0)])
    return rows


def setup(tmp):
    pl.STATE, pl.TRADES = Path(tmp) / "st.json", Path(tmp) / "tr.csv"


def boundary(step):
    return (pl.now_ms() // step) * step


def test_daily_open_and_close():
    with tempfile.TemporaryDirectory() as tmp:
        setup(tmp)
        ex = FakeEx()
        end = boundary(DAY)
        flat = [100.0] * 60
        for k in range(40):
            s = f"C{k}/USDT:USDT"
            ex.d[s] = series(flat + [100.0], DAY, end)
            ex.h4[s] = series([100.0] * 130, H4, boundary(H4))
            ex.last[s] = 100.0
        ex.d["C0/USDT:USDT"] = series(flat[:-1] + [120.0, 121.0], DAY, end)     # breakout on the last CLOSED day
        ex.last["C0/USDT:USDT"] = 121.0
        mk = pl.Market(ex)
        st = pl.fresh()
        pl.cycle(mk, st, say=lambda m: None)
        assert "C0/USDT:USDT" in st["open"]["daily"] and len(st["open"]["daily"]) == 1
        # next day: the close falls under the 30-day mean -> sold at the price
        ex.d["C0/USDT:USDT"] = series(flat[:-1] + [120.0, 90.0, 90.0], DAY, end + DAY)
        for k in range(1, 40):
            ex.d[f"C{k}/USDT:USDT"] = series(flat + [100.0, 100.0], DAY, end + DAY)
        ex.last["C0/USDT:USDT"] = 90.0
        orig = pl.now_ms
        pl.now_ms = lambda: orig() + DAY
        try:
            pl.cycle(mk, st, say=lambda m: None)
        finally:
            pl.now_ms = orig
        assert "C0/USDT:USDT" not in st["open"]["daily"] and pl.TRADES.exists()


def crash(n):
    """A wobbling series that then falls until RSI crosses under 20 on its LAST value (asserted), with a volume spike
    on that bar."""
    c = [100.0 + (0.6 if k % 2 else -0.6) for k in range(n)]
    while True:
        c.append(c[-1] * 0.97)
        r = pl.rsi14(np.array(c))
        if r[-1] < 20:
            assert r[-2] >= 20
            break
    c = c[-n:]
    v = [100.0] * (n - 1) + [500.0]
    return c, v


def test_breadth_gate_and_target():
    with tempfile.TemporaryDirectory() as tmp:
        setup(tmp)
        ex = FakeEx()
        end4 = boundary(H4)
        for k in range(40):
            s = f"C{k}/USDT:USDT"
            ex.d[s] = series([100.0] * 61, DAY, boundary(DAY))
            ex.h4[s] = series([100.0] * 131, H4, end4)
            ex.last[s] = 100.0
        c, v = crash(130)
        for k in range(4):                                                         # only 4 coins
            ex.h4[f"C{k}/USDT:USDT"] = series(c + [80.0], H4, end4, v + [100.0])
        mk = pl.Market(ex)
        st = pl.fresh()
        pl.cycle(mk, st, say=lambda m: None)
        assert st["open"]["capit"] == {}, "bought with breadth 4"
        st = pl.fresh()
        for k in range(6):
            ex.h4[f"C{k}/USDT:USDT"] = series(c + [80.0], H4, end4, v + [100.0])
            ex.last[f"C{k}/USDT:USDT"] = 80.0
        pl.cycle(mk, st, say=lambda m: None)
        assert len(st["open"]["capit"]) == 6, st["open"]["capit"]
        # a later bar trades 6% above the entry -> target
        st["open"]["capit"]["C0/USDT:USDT"]["t"] = "2000-01-01T00:00:00+00:00"
        ex.h4["C0/USDT:USDT"] = series(c + [80.0, 85.0, 85.0], H4, end4 + 2 * H4, v + [100.0, 100.0, 100.0])
        orig = pl.now_ms
        pl.now_ms = lambda: orig() + 2 * H4
        try:
            pl.cycle(mk, st, say=lambda m: None)
        finally:
            pl.now_ms = orig
        assert "C0/USDT:USDT" not in st["open"]["capit"]


def test_forming_bar_is_ignored():
    ex = FakeEx()
    end = boundary(DAY)
    ex.d["X/USDT:USDT"] = series([1.0, 2.0, 3.0], DAY, end)
    d = pl.Market(ex).closed("X/USDT:USDT", "1d", 3)
    assert list(d.c) == [1.0, 2.0]


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\n{len(tests)} passed")


def test_stock_tokens_and_stables_excluded():
    ex = FakeEx()
    ex.markets = {"SPCX/USDT:USDT": {"info": {"isRwa": "YES"}}, "BTC/USDT:USDT": {"info": {"isRwa": "NO"}},
                  "USDC/USDT:USDT": {"info": {}}}
    mk = pl.Market(ex)
    assert not mk.crypto("SPCX/USDT:USDT") and mk.crypto("BTC/USDT:USDT") and not mk.crypto("USDC/USDT:USDT")


if __name__ == "__main__":
    test_stock_tokens_and_stables_excluded()
    print("PASS test_stock_tokens_and_stables_excluded")
