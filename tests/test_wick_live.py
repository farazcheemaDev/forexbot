"""Offline tests for the crash-bid desk (wick_live.py) inside combo_bot.py. No network, no keys: a fake
Bitget that keeps one net position per coin, holds resting LIMIT orders until the test fills them,
and lists them the way the open-orders endpoint does. Each rule is checked where it must fire and
where it must not.

    python tests/test_wick_live.py
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.argv = [sys.argv[0]]
import combo_bot as cb  # noqa: E402
import combo_paper as cp  # noqa: E402
import wick_live as wl  # noqa: E402

cp.set_dir(Path(tempfile.mkdtemp()))
H = 1_790_000_000 // 3600 * 3600               # an hour boundary, seconds


class FakeEx:
    def __init__(self, coins=("BTC", "ETH", "XRP", "SOL"), px=None, prev=None):
        self.markets = {}
        for c in coins:
            s = f"{c}/USDT:USDT"
            self.markets[s] = dict(id=f"{c}USDT", symbol=s, contractSize=1.0)
        self.px = px or {s: 100.0 for s in self.markets}
        self.prev = prev or {s: 100.0 for s in self.markets}
        self.pos, self.log, self.resting, self.done, self.n = {}, [], {}, {}, 0

    def market(self, s):
        return self.markets[s]

    def amount_to_precision(self, s, a):
        return f"{a:.4f}"

    def price_to_precision(self, s, p):
        return f"{p:.6f}"

    def fetch_ticker(self, s):
        return {"last": self.px[s]}

    def set_margin_mode(self, *a):
        pass

    def set_leverage(self, *a):
        pass

    def fetch_ohlcv(self, s, tf, since=None, limit=None):
        return [[since, 0, 0, 0, self.prev[s], 0], [since + 3_600_000, 0, 0, 0, self.px[s], 0]]

    def _move(self, s, side, coins, reduce):
        old = self.pos.get(s, 0.0)
        new = old + (coins if side == "buy" else -coins)
        if reduce:
            assert abs(new) <= abs(old) + 1e-9, f"reduce-only would grow {s}"
        if abs(new) < 1e-9:
            self.pos.pop(s, None)
        else:
            self.pos[s] = new

    def create_order(self, s, typ, side, amount, price, params):
        self.n += 1
        oid = str(self.n)
        self.log.append(dict(id=oid, s=s, typ=typ, side=side, amount=float(amount), price=price, params=dict(params)))
        if typ == "limit":
            self.resting[oid] = dict(s=s, amount=float(amount), filled=0.0, price=float(price))
        elif "triggerPrice" not in params:
            self._move(s, side, float(amount), params.get("reduceOnly"))
        return {"id": oid, "average": self.px.get(s)}

    def fill(self, oid, amount=None):
        """The market trades through a resting bid (all of it, or `amount` of it)."""
        o = self.resting[oid]
        a = o["amount"] - o["filled"] if amount is None else amount
        o["filled"] += a
        self._move(o["s"], "buy", a, False)
        if o["filled"] >= o["amount"] - 1e-12:
            self.done[oid] = self.resting.pop(oid)

    def cancel_order(self, oid, s, params=None):
        if oid in self.resting:
            self.done[oid] = self.resting.pop(oid)

    def fetch_order(self, oid, s):
        o = self.resting.get(oid) or self.done.get(oid)
        return {"id": oid, "filled": o["filled"] if o else 0.0}

    def privateMixGetV2MixOrderOrdersPending(self, params):
        return {"data": {"entrustedList": [dict(orderId=oid, symbol=self.markets[o["s"]]["id"],
                                                baseVolume=str(o["filled"])) for oid, o in self.resting.items()]}}

    def privateMixGetV2MixPositionAllPosition(self, params):
        return {"data": [dict(symbol=self.markets[s]["id"], total=str(abs(q)), holdSide="long" if q > 0 else "short")
                         for s, q in self.pos.items()]}

    def privateMixGetV2MixAccountAccounts(self, params):
        return {"data": [{"marginCoin": "USDT", "accountEquity": "400"}]}


def desk(ex, label="bull", equity=400.0, cap=wl.CAP, coins=("BTCUSDT", "ETHUSDT", "XRPUSDT", "SOLUSDT", "NOPEUSDT")):
    v = cb.Venue(ex, "live")
    lines = []
    d = wl.WickDesk(v, lambda m: list(coins), lambda day: label, lambda: equity, lines.append, cap=cap)
    return d, v, lines


def state():
    return dict(trend=dict(open={}), mn=dict(weights={}, mark_px={}, base=0.0),
                sleeve=dict(hold={}, mark_px={}), exec=dict(mn_qty={}))


def bids(ex):
    return [o for o in ex.log if o["typ"] == "limit"]


def test_bids_are_post_only_limit_buys_at_90pct_of_the_last_close():
    ex = FakeEx(prev={"BTC/USDT:USDT": 200.0, "ETH/USDT:USDT": 100.0, "XRP/USDT:USDT": 50.0, "SOL/USDT:USDT": 10.0})
    d, v, _ = desk(ex)
    st = state()
    assert d.tick(st, H + 5) is True                 # a new hour: bids go out
    b = bids(ex)
    assert len(b) == 4                               # NOPEUSDT is not listed: no bid
    for o in b:
        assert o["side"] == "buy" and o["params"] == {"postOnly": True}
        prev = ex.prev[o["s"]]
        assert abs(o["price"] - 0.9 * prev) < 1e-6
        assert abs(o["amount"] * o["price"] - 400.0 / 40) < 0.01   # 1/40 of equity each


def test_no_bids_on_bear_days_or_under_five_dollars():
    ex = FakeEx()
    d, _, _ = desk(ex, label="bear")
    d.tick(state(), H + 5)
    assert bids(ex) == []
    ex2 = FakeEx()
    d2, _, _ = desk(ex2, equity=150.0)               # $3.75 a bid
    d2.tick(state(), H + 5)
    assert bids(ex2) == []


def test_a_fill_is_held_not_netted_away():
    ex = FakeEx()
    d, v, _ = desk(ex)
    st = state()
    d.tick(st, H + 5)
    oid = bids(ex)[0]["id"]
    ex.fill(oid)
    d.tick(st, H + 60)                                # same hour: watch only
    sym = st["wick"]["orders"][oid]["sym"]
    assert st["wick"]["fills"] == 1 and abs(st["wick"]["hold"][sym] - bids(ex)[0]["amount"]) < 1e-9
    before = len(ex.log)
    cb.execute(st, v, "live", {k: 100.0 for k in ("BTCUSDT", "ETHUSDT", "XRPUSDT", "SOLUSDT")}, dry=False)
    assert [o for o in ex.log[before:] if o["typ"] == "market" and "triggerPrice" not in o["params"]] == []


def test_cap_cancels_the_rest():
    ex = FakeEx()
    d, _, lines = desk(ex, cap=2)
    st = state()
    d.tick(st, H + 5)
    ids = [o["id"] for o in bids(ex)]
    ex.fill(ids[0]); ex.fill(ids[1])
    d.tick(st, H + 30)
    assert st["wick"]["cap_hit"] and st["wick"]["fills"] == 2
    assert ex.resting == {}                           # both others cancelled
    assert any("WICK CAP" in x for x in lines)


def test_partial_fill_counts_once_and_holds_the_delta():
    ex = FakeEx()
    d, _, _ = desk(ex)
    st = state()
    d.tick(st, H + 5)
    oid = bids(ex)[0]["id"]
    amt = ex.resting[oid]["amount"]
    ex.fill(oid, amt / 4)
    d.tick(st, H + 10)
    ex.fill(oid, amt / 4)
    d.tick(st, H + 15)
    sym = st["wick"]["orders"][oid]["sym"]
    assert st["wick"]["fills"] == 1 and abs(st["wick"]["hold"][sym] - amt / 2) < 1e-9


def test_the_cap_cancels_bids_that_are_only_PARTLY_filled():
    """The suite tested partial fills and the cap separately, never together - the trap CLAUDE.md
    calls "a test that cannot exhibit the bug".

    A partly filled bid is counted (it raises `fills`) but stays open. When the cancel filter also
    required `not counted`, such an order survived the cap and kept absorbing. In a sweep deep
    enough to touch every level - 2025-10-10, 38 of 40 bids filling in minutes - ALL the bids are
    partly filled between two watches, so the cap cancelled nothing at all."""
    ex = FakeEx()
    d, _, _ = desk(ex, cap=2)
    st = state()
    d.tick(st, H + 5)
    b = bids(ex)
    ex.fill(b[0]["id"])                                   # one filled outright
    ex.fill(b[1]["id"], ex.resting[b[1]["id"]]["amount"] / 2)   # one only PARTLY filled
    d.tick(st, H + 20)
    w = st["wick"]
    assert w["fills"] == 2 and w["cap_hit"] is True
    resting = [o["sym"] for oid, o in w["orders"].items() if oid in ex.resting]
    assert not resting, f"the cap left these bids live: {resting}"


def test_the_cap_cancels_everything_when_a_sweep_touches_every_level():
    """The disaster case the cap exists for, at the deployed cap of 10."""
    n = 12
    coins = tuple(f"C{i}" for i in range(n))
    ex = FakeEx(coins=coins)
    d, _, _ = desk(ex, cap=10, coins=tuple(f"C{i}USDT" for i in range(n)))
    st = state()
    d.tick(st, H + 5)
    for o in bids(ex):
        ex.fill(o["id"], ex.resting[o["id"]]["amount"] * 0.5)   # every bid partly filled at once
    d.tick(st, H + 8)
    w = st["wick"]
    assert w["cap_hit"] is True
    live = [o["sym"] for oid, o in w["orders"].items() if oid in ex.resting]
    assert not live, f"the cap left {len(live)} of {n} bids live in a full sweep: {live}"


def test_the_hour_close_sells_the_fills_and_places_new_bids():
    ex = FakeEx()
    d, v, _ = desk(ex)
    st = state()
    d.tick(st, H + 5)
    first = bids(ex)
    ex.fill(first[0]["id"]); ex.fill(first[1]["id"])
    d.tick(st, H + 100)
    held = dict(ex.pos)
    assert len(held) == 2
    assert d.tick(st, H + 3600 + 2) is True           # the next hour
    assert st["wick"]["hold"] == {}
    assert all(first[k]["id"] not in ex.resting for k in range(len(first)))   # leftovers cancelled
    cb.execute(st, v, "live", {k: 100.0 for k in ("BTCUSDT", "ETHUSDT", "XRPUSDT", "SOLUSDT")}, dry=False)
    assert ex.pos == {}                               # sold at the close, through the netting
    sells = [o for o in ex.log if o["typ"] == "market" and o["side"] == "sell" and "triggerPrice" not in o["params"]]
    assert len(sells) == 2 and all(o["params"].get("reduceOnly") for o in sells)
    assert len(ex.resting) == 4                       # the new hour's bids


def test_a_fill_against_a_trend_short_nets():
    ex = FakeEx()
    d, v, _ = desk(ex)
    st = state()
    st["trend"]["open"]["ETHUSDT:4h"] = dict(side="short", entry=100.0, units=1, notional=1000.0, stop=120.0)
    px = {k: 100.0 for k in ("BTCUSDT", "ETHUSDT", "XRPUSDT", "SOLUSDT")}
    cb.execute(st, v, "live", px, dry=False)
    assert abs(ex.pos["ETH/USDT:USDT"] + 10.0) < 1e-9
    d.tick(st, H + 5)
    eth = next(o for o in bids(ex) if o["s"] == "ETH/USDT:USDT")
    ex.fill(eth["id"])
    d.tick(st, H + 20)
    n = len(ex.log)
    cb.execute(st, v, "live", px, dry=False)
    assert [o for o in ex.log[n:] if o["typ"] == "market" and "triggerPrice" not in o["params"]] == []
    d.tick(st, H + 3602)
    cb.execute(st, v, "live", px, dry=False)
    assert abs(ex.pos["ETH/USDT:USDT"] + 10.0) < 1e-9  # back to the trend book's short


def test_stale_bids_from_a_dead_hour_are_cancelled_on_restart():
    ex = FakeEx()
    d, _, _ = desk(ex)
    st = state()
    d.tick(st, H + 5)
    old = set(ex.resting)
    d2, _, _ = desk(ex)                               # a restarted process, same state
    d2.tick(st, H + 3 * 3600 + 5)
    assert old.isdisjoint(ex.resting)


def test_the_desk_never_sells():
    ex = FakeEx()
    d, _, _ = desk(ex, cap=1)
    st = state()
    for k in range(3):
        d.tick(st, H + k * 3600 + 5)
        if ex.resting:
            ex.fill(next(iter(ex.resting)))
        d.tick(st, H + k * 3600 + 50)
    assert all(o["side"] == "buy" and o["typ"] == "limit" for o in ex.log)


def test_targets_include_the_desk_hold():
    st = state()
    st["wick"] = wl.fresh()
    st["wick"]["hold"] = {"SOLUSDT": 0.25}
    assert cb.book_targets(st) == {"SOLUSDT": 0.25}


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
