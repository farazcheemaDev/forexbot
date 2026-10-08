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
import pandas as pd

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


# ------------------------------------------------------------------ capit2, the improved capitulation book (2026-10-08)

def fall(f, n=130):
    """A wobble, then a fall of (1 - f) a bar until RSI crosses under 20 on the LAST close (asserted)."""
    c = [100.0 + (0.6 if k % 2 else -0.6) for k in range(n)]
    while True:
        c.append(c[-1] * f)
        r = pl.rsi14(np.array(c))
        if r[-1] < 20:
            assert r[-2] >= 20
            break
    return c[-n:]


def rows4(closes, end, extra=(), vol_spike=True):
    """Closed 4h bars from closes (o = previous close), then `extra` explicit (o, h, l, c) bars, then a forming bar
    opening at `end`. The last close of `closes` is the signal bar: volume x5 there."""
    out, prev = [], closes[0]
    for c in closes:
        out.append([0, prev, max(prev, c) * 1.001, min(prev, c) * 0.999, c, 100.0])
        prev = c
    if vol_spike:
        out[-1][5] = 500.0
    for o, h, l, c in extra:
        out.append([0, o, h, l, c, 100.0])
    last = out[-1][4]
    out.append([0, last, last, last, last, 100.0])                       # the forming bar
    n = len(out)
    for k, r in enumerate(out):
        r[0] = end - (n - 1 - k) * H4
    return out


def market(capit_closes, extra, shift, n_capit=6):
    """40 flat coins; n_capit of them capitulate on the same bar. `shift` = how many 4h bars have passed."""
    ex = FakeEx()
    end4 = boundary(H4) + shift * H4
    for k in range(40):
        s = f"C{k}/USDT:USDT"
        ex.d[s] = series([100.0] * 61, DAY, boundary(DAY))
        ex.h4[s] = rows4([100.0] * 130, end4, extra=[(100.0, 100.1, 99.9, 100.0)] * len(extra), vol_spike=False)
        ex.last[s] = 100.0
    for k in range(n_capit):
        s = f"C{k}/USDT:USDT"
        ex.h4[s] = rows4(capit_closes, end4, extra)
        ex.last[s] = (extra[-1][3] if extra else capit_closes[-1])
    return ex


def at(shift, fn):
    orig = pl.now_ms
    pl.now_ms = lambda: orig() + shift * H4
    try:
        return fn()
    finally:
        pl.now_ms = orig


def go(ex, shift, st):
    """One paper pass at `shift` 4h bars from now, on a fake market built BEFORE the clock moves (boundary() reads
    pl.now_ms, so building it inside the shifted call would shift every bar twice)."""
    return at(shift, lambda: pl.cycle(pl.Market(ex), st, say=lambda m: None))


def test_capit2_fills_on_a_trade_through_and_skips_the_fill_bar_target():
    with tempfile.TemporaryDirectory() as tmp:
        setup(tmp)
        c = fall(0.97)
        assert c[-1] / c[-7] - 1 <= -0.10, "the test needs a deep 24h drop"
        sig = c[-1]
        st = pl.fresh()
        pl.cycle(pl.Market(market(c, [], 0)), st, say=lambda m: None)
        assert len(st["pending"]) == 6 and st["limits"]["placed"] == 6 and not st["open"]["capit2"]
        lim = sig * (1 - pl.LIMIT)
        # the next bar trades through the limit AND spikes above the target: filled, but no target in the fill bar
        w = (sig, lim * 1.08, sig * 0.96, sig * 0.97)
        go(market(c, [w], 1), 1, st)
        assert len(st["open"]["capit2"]) == 6 and not st["pending"] and st["limits"]["filled"] == 6
        assert abs(st["open"]["capit2"]["C0/USDT:USDT"]["entry"] - lim) < 1e-9
        # a quiet bar under the target: still open (a book that counted the FILL bar's spike would have sold here)
        q = (sig * 0.97, sig * 0.98, sig * 0.96, sig * 0.97)
        go(market(c, [w, q], 2), 2, st)
        assert len(st["open"]["capit2"]) == 6, "sold on the fill bar's high"
        # a later bar reaches +5%: the target sells at entry x 1.05
        x = (sig * 0.97, lim * 1.06, sig * 0.96, sig)
        go(market(c, [w, q, x], 3), 3, st)
        assert not st["open"]["capit2"]
        t = pd.read_csv(pl.TRADES)
        t = t[t.book == "capit2"]
        assert len(t) == 6 and set(t.why) == {"target"} and abs(t.exit.iloc[0] - lim * 1.05) < 1e-9


def test_capit2_cancels_an_unfilled_limit_and_needs_the_drop():
    with tempfile.TemporaryDirectory() as tmp:
        setup(tmp)
        c = fall(0.97)
        sig = c[-1]
        lim = sig * (1 - pl.LIMIT)
        st = pl.fresh()
        pl.cycle(pl.Market(market(c, [], 0)), st, say=lambda m: None)
        w = (sig, sig * 1.01, lim * 0.999, sig)                         # touches the limit, not 0.3% THROUGH it
        go(market(c, [w], 1), 1, st)
        assert not st["pending"] and not st["open"]["capit2"] and st["limits"] == dict(placed=6, filled=0)
        shallow = fall(0.99)
        assert shallow[-1] / shallow[-7] - 1 > -0.10, "the test needs a shallow 24h drop"
        st = pl.fresh()
        pl.cycle(pl.Market(market(shallow, [], 0)), st, say=lambda m: None)
        assert not st["pending"], "a capitulation without the 10% drop placed a limit"
        assert len(st["open"]["capit"]) == 6                            # the plain book still bought them


def test_capit2_not_working_after_24_bars_from_the_signal():
    with tempfile.TemporaryDirectory() as tmp:
        setup(tmp)
        c = fall(0.97)
        sig = c[-1]
        lim = sig * (1 - pl.LIMIT)
        st = pl.fresh()
        pl.cycle(pl.Market(market(c, [], 0)), st, say=lambda m: None)
        w = (sig, sig, sig * 0.96, sig * 0.97)
        flat = [(sig * 0.97, sig * 0.975, sig * 0.965, sig * 0.97)] * 22   # bars 2..23 after the signal: below entry
        go(market(c, [w] + flat, 23), 23, st)
        assert len(st["open"]["capit2"]) == 6, "sold before 24 bars"
        go(market(c, [w] + flat + [flat[0]], 24), 24, st)
        assert not st["open"]["capit2"]
        t = pd.read_csv(pl.TRADES)
        assert set(t[t.book == "capit2"].why) == {"not_working"}
        assert lim > sig * 0.97                                          # it really was under the entry


if __name__ == "__main__":
    for fn in (test_stock_tokens_and_stables_excluded, test_capit2_fills_on_a_trade_through_and_skips_the_fill_bar_target,
               test_capit2_cancels_an_unfilled_limit_and_needs_the_drop, test_capit2_not_working_after_24_bars_from_the_signal):
        fn()
        print(f"PASS {fn.__name__}")
