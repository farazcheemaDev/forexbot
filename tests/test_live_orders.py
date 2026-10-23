"""Offline tests for the real-order pieces (2026-10-24): the coin-name map and its unit scale, the crash desk's fills in
the book's units, and capit2's limit resting ON THE VENUE. A fake Bitget (tests/test_wick_live.FakeEx: one net position
per coin, resting limit orders the test fills). No network, no keys.

    python tests/test_live_orders.py
"""
from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
sys.argv = [sys.argv[0]]
import combo_bot as cb  # noqa: E402
import combo_paper as cp  # noqa: E402
import final_books as fb  # noqa: E402
import news_books as nbk  # noqa: E402
import wick_live as wl  # noqa: E402
from test_wick_live import H, FakeEx  # noqa: E402

cp.set_dir(Path(tempfile.mkdtemp()))
SOL = "SOL/USDT:USDT"


def account(eq=300.0):
    st = dict(equity=eq, cum=dict(trend=0.0, mn=0.0, sleeve=0.0, fees=0.0), last_day=None, exec={},
              trend=dict(open={}), mn=dict(weights={}, mark_px={}, base=0.0), sleeve=dict(hold={}, mark_px={}))
    st["fin"] = fb.fresh()
    nbk.ensure(st)
    return st


def market_orders(ex):
    return [o for o in ex.log if o["typ"] == "market" and "triggerPrice" not in o["params"]]


def limits(ex):
    return [o for o in ex.log if o["typ"] == "limit"]


# ------------------------------------------------------------------ the coin-name map

def test_the_map_converts_units_and_names_and_never_guesses():
    v = cb.Venue(FakeEx(coins=("BTC", "SHIB", "PEPE", "RAY", "1MCHEEMS", "1000XYZ", "1MXYZ", "1INCH")), "live")
    assert v.mapped("BTCUSDT") == ("BTC/USDT:USDT", 1.0)
    assert v.mapped("1000SHIBUSDT") == ("SHIB/USDT:USDT", 1000.0)              # one Binance unit = 1,000 SHIB
    assert v.mapped("1000PEPEUSDT") == ("PEPE/USDT:USDT", 1000.0)
    assert v.mapped("RAYSOLUSDT") == ("RAY/USDT:USDT", 1.0)                    # renamed: ALIASES
    assert v.mapped("1000CHEEMSUSDT") == ("1MCHEEMS/USDT:USDT", 0.001)
    assert v.mapped("1INCHUSDT") == ("1INCH/USDT:USDT", 1.0)                   # a name that starts with 1 is not a unit
    assert v.mapped("XYZUSDT") == (None, 1.0)                                  # two candidates: no guess
    assert v.mapped("NOPEUSDT") == (None, 1.0)


def test_execute_trades_1000shib_as_shib_and_does_not_trade_it_twice():
    ex = FakeEx(coins=("SHIB",), px={"SHIB/USDT:USDT": 0.00001})
    v = cb.Venue(ex, "live")
    st = account()
    st["fin"]["daily"]["open"]["1000SHIBUSDT"] = dict(qty=600.0, entry=0.01, t_ms=0)    # 600 x 1000SHIB = $6
    cb.execute(st, v, "live", {"1000SHIBUSDT": 0.01}, dry=False)
    o = market_orders(ex)
    assert len(o) == 1 and o[0]["s"] == "SHIB/USDT:USDT" and o[0]["side"] == "buy" and abs(o[0]["amount"] - 600_000) < 1e-6
    cb.execute(st, v, "live", {"1000SHIBUSDT": 0.01}, dry=False)              # the venue's 600,000 SHIB = the target
    assert len(market_orders(ex)) == 1
    st["fin"]["daily"]["open"].pop("1000SHIBUSDT")                             # the book exits: all of it is sold
    cb.execute(st, v, "live", {"1000SHIBUSDT": 0.01}, dry=False)
    o = market_orders(ex)
    assert len(o) == 2 and o[1]["side"] == "sell" and abs(o[1]["amount"] - 600_000) < 1e-6 and "SHIB/USDT:USDT" not in ex.pos


def test_a_crash_bid_fill_is_held_in_the_books_units():
    ex = FakeEx(coins=("SHIB",), px={"SHIB/USDT:USDT": 0.00001}, prev={"SHIB/USDT:USDT": 0.00001})
    d = wl.WickDesk(cb.Venue(ex, "live"), lambda m: ["1000SHIBUSDT"], lambda day: "bull", lambda: 400.0, lambda m: None)
    st = dict(trend=dict(open={}), mn=dict(weights={}, mark_px={}, base=0.0), sleeve=dict(hold={}, mark_px={}),
              exec=dict(mn_qty={}))
    d.tick(st, H + 5)
    b = limits(ex)
    assert len(b) == 1 and abs(b[0]["price"] - 0.000009) < 1e-12
    ex.fill(b[0]["id"])
    d.watch(st)
    want = b[0]["amount"] / 1000.0                                             # SHIB -> 1000SHIB
    assert abs(st["wick"]["hold"]["1000SHIBUSDT"] - want) < 1e-9, st["wick"]["hold"]


# ------------------------------------------------------------------ capit2's resting order

def pending_now(lim=98.0):
    """A capit2 limit whose live bar contains the real clock (execute reads time.time())."""
    now = int(time.time() * 1000)
    sig = (now // fb.H4) * fb.H4 - fb.H4
    return dict(lim=lim, signal_t=sig), now, sig + 2 * fb.H4


def test_capit2_places_a_post_only_buy_at_the_limit_for_the_backtests_size():
    ex = FakeEx(coins=("SOL",), px={SOL: 100.0})
    st = account()
    r, now, _ = pending_now()
    st["fin"]["capit2"]["pending"]["SOLUSDT"] = r
    fb.capit2_orders(st, cb.Venue(ex, "live"), now)
    b = limits(ex)
    assert len(b) == 1 and b[0]["side"] == "buy" and b[0]["params"] == {"postOnly": True} and abs(b[0]["price"] - 98.0) < 1e-9
    assert abs(b[0]["amount"] - fb.K_CAPIT2 * fb.CAPIT2_LEV * 300.0 / fb.SLOTS / 98.0) < 1e-4
    fb.capit2_orders(st, cb.Venue(ex, "live"), now)                            # resting: not placed twice
    assert len(limits(ex)) == 1


def test_the_paper_fill_leaves_a_venue_order_alone():
    ex = FakeEx(coins=("SOL",), px={SOL: 100.0})
    st = account()
    r, now, _ = pending_now()
    st["fin"]["capit2"]["pending"]["SOLUSDT"] = r
    fb.capit2_orders(st, cb.Venue(ex, "live"), now)
    st["fin"]["last_4h"] = (now // fb.H4) * fb.H4 - fb.H4                     # no new 4h bar: only the pending loop runs
    fb.capit2_poll(st, {"SOLUSDT": 90.0}, now, fund=lambda s, a, b: 0.0,
                   get1m=lambda s, a, b: pd.DataFrame(dict(t=[a], l=[80.0])))  # the minutes trade far through it
    assert "SOLUSDT" not in st["fin"]["capit2"]["open"] and "SOLUSDT" in st["fin"]["capit2"]["pending"]


def test_a_part_fill_is_the_position_at_the_limit_and_the_netting_keeps_it():
    ex = FakeEx(coins=("SOL",), px={SOL: 99.0})
    v = cb.Venue(ex, "live")
    st = account()
    r, now, end = pending_now()
    st["fin"]["capit2"]["pending"]["SOLUSDT"] = r
    cb.execute(st, v, "live", {"SOLUSDT": 99.0}, dry=False)                    # places the order
    oid = limits(ex)[0]["id"]
    ex.fill(oid, 0.4)                                                          # the venue now holds 0.4 SOL
    cb.execute(st, v, "live", {"SOLUSDT": 99.0}, dry=False)
    p = st["fin"]["capit2"]["open"]["SOLUSDT"]
    assert abs(p["qty"] - 0.4) < 1e-9 and p["entry"] == 98.0
    assert market_orders(ex) == []                                             # nothing sold back, nothing bought
    fb.capit2_orders(st, v, end + 1)                                           # the bar is over: the rest is cancelled
    assert oid in ex.done and "SOLUSDT" not in st["fin"]["capit2"]["pending"]
    assert abs(st["fin"]["capit2"]["open"]["SOLUSDT"]["qty"] - 0.4) < 1e-9 and st["fin"]["capit2"]["filled"] == 1


def test_nothing_filled_by_the_end_of_the_bar_is_a_cancel():
    ex = FakeEx(coins=("SOL",), px={SOL: 100.0})
    v = cb.Venue(ex, "live")
    st = account()
    r, now, end = pending_now()
    st["fin"]["capit2"]["pending"]["SOLUSDT"] = r
    fb.capit2_orders(st, v, now)
    fb.capit2_orders(st, v, end + 1)
    cb_ = st["fin"]["capit2"]
    assert cb_["pending"] == {} and cb_["open"] == {} and cb_["cancelled"] == 1 and limits(ex)[0]["id"] in ex.done


def test_no_order_without_a_free_slot_and_the_fallbacks():
    ex = FakeEx(coins=("SOL", "ADA"), px={SOL: 100.0, "ADA/USDT:USDT": 0.5})
    v = cb.Venue(ex, "live")
    st = account()
    r, now, _ = pending_now()
    st["fin"]["capit2"]["open"] = {f"C{i}USDT": dict(qty=1.0, entry=1.0, t_ms=0) for i in range(fb.SLOTS)}
    st["fin"]["capit2"]["pending"]["SOLUSDT"] = dict(r)
    fb.capit2_orders(st, v, now)
    assert limits(ex) == [] and not st["fin"]["capit2"]["pending"]["SOLUSDT"].get("paper")   # waits for a slot
    st["fin"]["capit2"]["open"] = {}
    st["fin"]["capit2"]["pending"] = {"NOPEUSDT": dict(r), "ADAUSDT": dict(r, lim=0.6), "SOLUSDT": dict(r)}
    fb.capit2_orders(st, v, now)
    pend = st["fin"]["capit2"]["pending"]
    assert pend["NOPEUSDT"]["paper"] and "oid" not in pend["NOPEUSDT"]                 # not listed
    assert pend["ADAUSDT"]["paper"] and "oid" not in pend["ADAUSDT"]                   # already under its limit
    assert pend["SOLUSDT"].get("oid") and len(limits(ex)) == 1


def test_an_order_the_venue_drops_unfilled_hands_over_to_the_poll():
    ex = FakeEx(coins=("SOL",), px={SOL: 100.0})
    v = cb.Venue(ex, "live")
    st = account()
    r, now, _ = pending_now()
    st["fin"]["capit2"]["pending"]["SOLUSDT"] = r
    fb.capit2_orders(st, v, now)
    ex.cancel_order(limits(ex)[0]["id"], SOL)                                  # refused / gone, nothing filled
    fb.capit2_orders(st, v, now + 1000)
    p = st["fin"]["capit2"]["pending"]["SOLUSDT"]
    assert p["paper"] and "oid" not in p and st["fin"]["capit2"]["cancelled"] == 0


def test_a_live_final_account_always_runs_the_real_crash_desk():
    a = lambda **k: type("A", (), dict(dict(wick=False, final=False, mode="dry"), **k))()  # noqa: E731
    assert cb.wants_desk(a(final=True, mode="live")) is True
    assert cb.wants_desk(a(final=True, mode="dry")) is False                   # dry keeps the ledger
    assert cb.wants_desk(a(wick=True, mode="demo")) is True


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\n{len(tests)} passed")
