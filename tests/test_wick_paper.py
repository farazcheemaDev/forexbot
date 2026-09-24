"""Offline tests for wick_paper.py (the crash-bid paper book). No network: a fake market serves the
1-minute bars, and the universe and BTC label are stubbed. Each rule is checked where it must fire
and where it must not.

    python tests/test_wick_paper.py
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.argv = [sys.argv[0]]
import wick_paper as w  # noqa: E402

TMP = Path(tempfile.mkdtemp())
w.set_dir(TMP)
w.time.sleep = lambda s: None                    # the pacing sleep, not needed offline
H = 1_790_000_000_000 // w.HOUR_MS * w.HOUR_MS   # an hour boundary


def flat(p, n, t0):
    return [[t0 + k * w.MIN_MS, p, p, p, p] for k in range(n)]


class Market:
    """bars[(venue, sym)] = 61 one-minute bars from H - 1 min. Unknown pairs are flat at 100."""
    def __init__(self, bars=None):
        self.bars = bars or {}
        self.calls = []

    def __call__(self, venue, sym, t0, n):
        self.calls.append((venue, sym, t0, n))
        b = self.bars.get((venue, sym)) or flat(100.0, 61 + 200, H - w.MIN_MS)
        out = [r for r in b if t0 <= r[0] < t0 + n * w.MIN_MS]
        return out if len(out) == n else None


def wick(minute, low, close=95.0, prev=100.0, open_=None, tail=None):
    """prev close 100, then the hour: flat at 100 until `minute`, where the low is `low`, then
    `close` for the rest of the hour; `tail` (list of 1m closes) after the hour."""
    b = [[H - w.MIN_MS, prev, prev, prev, prev]]
    for k in range(60):
        t = H + k * w.MIN_MS
        if k < minute:
            b.append([t, 100.0, 100.0, 100.0, 100.0])
        elif k == minute:
            b.append([t, open_ if open_ is not None else 100.0, 100.0, low, close])
        else:
            b.append([t, close, close, close, close])
    t = H + 60 * w.MIN_MS
    for k, c in enumerate(tail or [close] * 200):
        b.append([t + k * w.MIN_MS, c, c, c, c])
    return b


def fresh_state(coins, lab="bull"):
    st = w.fresh()
    month = f"{w.datetime.fromtimestamp(H / 1000, w.timezone.utc):%Y-%m}"
    day = f"{w.datetime.fromtimestamp(H / 1000, w.timezone.utc):%Y-%m-%d}"
    st["universes"][month] = coins
    st["labels"][day] = lab
    return st


def test_touch_does_not_fill_penetration_does():
    assert w.fill_of(wick(10, 90.0)[1:], 100.0) is None                  # exactly the bid
    assert w.fill_of(wick(10, 89.95)[1:], 100.0) is None                 # inside the 0.1%
    r = w.fill_of(wick(10, 89.8)[1:], 100.0)
    assert r and r[0] == 10 and abs(r[1] - 90.0) < 1e-12                 # filled AT the bid


def test_gap_below_the_bid_fills_at_the_open():
    j, f, low_after, ex = w.fill_of(wick(5, 80.0, open_=85.0)[1:], 100.0)
    assert j == 5 and f == 85.0                                          # not 90: it opened lower
    assert abs(low_after - (80.0 / 85.0 - 1)) < 1e-12


def test_low_after_counts_the_fill_minute_and_later_only():
    b = wick(20, 89.0, close=95.0)[1:]
    b[5][3] = 50.0                                   # an earlier, deeper dip is itself the first fill
    assert w.fill_of(b, 100.0)[0] == 5
    b = wick(20, 89.0, close=95.0)[1:]
    b[40][3] = 70.0                                  # after the fill: counted
    _, f, low_after, _ = w.fill_of(b, 100.0)
    assert abs(low_after - (70.0 / 90.0 - 1)) < 1e-12


def test_cap_keeps_the_first_ten_by_minute_then_symbol():
    fills = [dict(sym=f"C{i:02d}USDT", minute=30 - i) for i in range(12)]
    kept = w.cap(fills)
    assert len(kept) == w.CAP_FILLS == 10
    assert [x["minute"] for x in kept] == sorted(x["minute"] for x in kept)
    assert {"C00USDT", "C01USDT"}.isdisjoint({x["sym"] for x in kept})    # the two latest are cancelled
    tie = [dict(sym=s, minute=7) for s in ("ZZZUSDT", "AAAUSDT", "MMMUSDT")]
    assert [x["sym"] for x in w.cap(tie)] == ["AAAUSDT", "MMMUSDT", "ZZZUSDT"]


def test_net_charges_38bp():
    assert abs(w.COST - 0.0038) < 1e-15
    assert abs(w.net(99.0, 90.0) - (99.0 / 90.0 - 1 - 0.0038)) < 1e-15


def test_bitget_names():
    listed = {"PEPEUSDT", "1000BONKUSDT", "SHIBUSDT", "BTCUSDT"}
    assert w.bitget_name("BTCUSDT", listed) == "BTCUSDT"
    assert w.bitget_name("1000PEPEUSDT", listed) == "PEPEUSDT"
    assert w.bitget_name("1000BONKUSDT", listed) == "1000BONKUSDT"
    assert w.bitget_name("BONKUSDT", listed) == "1000BONKUSDT"
    assert w.bitget_name("NOPEUSDT", listed) is None


def test_one_hour_end_to_end_both_venues():
    coins = [f"C{i:02d}USDT" for i in range(40)]
    bars = {}
    for i in range(12):                              # 12 coins wick at minutes 10..21
        for v in w.VENUES:
            bars[(v, coins[i])] = wick(10 + i, 88.0, close=99.0)
    m = Market(bars)
    st = fresh_state(coins)
    w.process_hour(st, H, fetch=m, listed=set(coins))
    for v in w.VENUES:
        L = st["led"][v]
        assert L["fills"] == 12 and L["kept"] == 10
        size = 300.0 / 40
        want = 10 * size * (99.0 / 90.0 - 1 - 0.0038)
        assert abs(L["equity"] - (300.0 + want)) < 1e-9, L["equity"]
        assert abs(L["worst_hour"] - 10 * size * (88.0 / 90.0 - 1) / 300.0) < 1e-12
        assert len(L["pending"]) == 10
    fetched = {c for (_, c, _, _) in m.calls}
    assert fetched == set(coins)
    assert all(t0 == H - w.MIN_MS and n == 61 for (_, _, t0, n) in m.calls)   # prev close + the hour


def test_bear_day_places_no_bids():
    m = Market({("binance", "AUSDT"): wick(10, 50.0), ("bitget", "AUSDT"): wick(10, 50.0)})
    st = fresh_state(["AUSDT"], lab="bear")
    w.process_hour(st, H, fetch=m, listed={"AUSDT"})
    assert m.calls == [] and st["bear_hours"] == 1
    assert all(st["led"][v]["fills"] == 0 and st["led"][v]["equity"] == 300.0 for v in w.VENUES)


def test_under_five_dollars_no_bids():
    m = Market({("binance", "AUSDT"): wick(10, 50.0)})
    st = fresh_state(["AUSDT"])
    for v in w.VENUES:
        st["led"][v]["equity"] = 150.0              # 150 / 40 = $3.75 a bid
    w.process_hour(st, H, fetch=m, listed={"AUSDT"})
    assert m.calls == []
    assert all(st["led"][v]["skipped_small"] == 1 and st["led"][v]["equity"] == 150.0 for v in w.VENUES)


def test_coin_missing_on_bitget_is_skipped_there_only():
    bars = {(v, "AUSDT"): wick(10, 88.0, close=99.0) for v in w.VENUES}
    m = Market(bars)
    st = fresh_state(["AUSDT"])
    w.process_hour(st, H, fetch=m, listed=set())    # Bitget lists nothing
    assert st["led"]["binance"]["kept"] == 1 and st["led"]["bitget"]["kept"] == 0
    assert all(v == "binance" for (v, _, _, _) in m.calls)


def test_x120_settles_at_the_bar_120_minutes_after_the_fill():
    tail = [99.0] * 200
    tail[70] = 120.0                                 # minute 60 + 70 = 130 = fill minute 10 + 120
    bars = {(v, "AUSDT"): wick(10, 88.0, close=99.0, tail=tail) for v in w.VENUES}
    m = Market(bars)
    st = fresh_state(["AUSDT"])
    w.process_hour(st, H, fetch=m, listed={"AUSDT"})
    t_exit = H + (10 + 120) * w.MIN_MS
    w.settle_x120(st, t_exit + w.MIN_MS + w.DELAY_S * 1000 - 1, fetch=m)
    assert all(len(st["led"][v]["pending"]) == 1 for v in w.VENUES)      # not yet
    w.settle_x120(st, t_exit + w.MIN_MS + w.DELAY_S * 1000, fetch=m)
    for v in w.VENUES:
        L = st["led"][v]
        assert L["pending"] == [] and L["n120"] == 1
        assert abs(L["eq120"] - (300.0 + 7.5 * (120.0 / 90.0 - 1 - 0.0038))) < 1e-9


def test_due_hours_first_run_catch_up_and_gap():
    st = w.fresh()
    now = H + 5 * w.HOUR_MS + 10 * w.MIN_MS          # 3-minute delay passed: hour H+4 is closed
    assert w.due_hours(st, now) == [H + 4 * w.HOUR_MS]                 # first run: only the last hour
    st["last_hour"] = H + 1 * w.HOUR_MS
    assert w.due_hours(st, now) == [H + 2 * w.HOUR_MS, H + 3 * w.HOUR_MS, H + 4 * w.HOUR_MS]
    assert w.due_hours(st, H + 5 * w.HOUR_MS + 60_000) == [H + 2 * w.HOUR_MS, H + 3 * w.HOUR_MS]  # too early for H+4
    st["last_hour"] = H - 100 * w.HOUR_MS
    d = w.due_hours(st, now)
    assert len(d) == w.CATCHUP_H and d[-1] == H + 4 * w.HOUR_MS and len(st["gaps"]) == 1


def test_it_cannot_place_orders():
    src = (ROOT / "wick_paper.py").read_text(encoding="utf-8")
    for bad in ("ccxt", "API_KEY", "SECRET", "create_order", "placeOrder", "place-order"):
        assert bad not in src, bad


if __name__ == "__main__":
    fails = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn(); print(f"ok    {name}")
            except Exception as e:  # noqa: BLE001
                fails += 1; print(f"FAIL  {name}: {type(e).__name__}: {e}")
    print(f"\n{sum(1 for n in globals() if n.startswith('test_')) - fails} passed, {fails} failed")
    sys.exit(1 if fails else 0)
