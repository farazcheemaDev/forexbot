"""Offline tests for combo_bot.py's EXECUTION layer - the part that places orders. No network,
no keys: a fake Bitget that keeps one net position per coin (one-way mode) and refuses a
reduce-only order that would grow a position. Each rule is tested where it must fire and where
it must not.

    python tests/test_combo_bot.py
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

cp.set_dir(Path(tempfile.mkdtemp()))


class FakeEx:
    def __init__(self, prefix="S", quote="SUSDT", coins=("BTC", "ETH", "XRP"), px=None, cs=None):
        self.markets = {}
        for c in coins:
            s = f"{prefix}{c}/{quote}:{quote}"
            self.markets[s] = dict(id=f"{prefix}{c}{quote}", symbol=s, contractSize=(cs or {}).get(c, 1.0))
        self.px = px or {}
        self.pos, self.orders, self.cancelled, self.n = {}, [], [], 0

    def market(self, s):
        return self.markets[s]

    def amount_to_precision(self, s, a):
        return f"{a:.4f}"

    def price_to_precision(self, s, p):
        return f"{p:.6f}"

    def fetch_ticker(self, s):
        return {"last": self.px[s]}

    def set_margin_mode(self, *a):
        self.margin = a

    def set_leverage(self, *a):
        pass

    def create_order(self, s, typ, side, amount, price, params):
        self.n += 1
        self.orders.append(dict(s=s, side=side, amount=float(amount), params=dict(params)))
        if "triggerPrice" not in params:
            coins = float(amount) * self.markets[s]["contractSize"]
            old = self.pos.get(s, 0.0)
            new = old + (coins if side == "buy" else -coins)
            if params.get("reduceOnly"):
                assert abs(new) <= abs(old) + 1e-9 and (new == 0 or (new > 0) == (old > 0)), \
                    f"reduce-only order would grow or flip {s}: {old} -> {new}"
            if abs(new) < 1e-9:
                self.pos.pop(s, None)
            else:
                self.pos[s] = new
        return {"id": str(self.n), "average": self.px.get(s)}

    def cancel_order(self, oid, s, params=None):
        self.cancelled.append(oid)

    def privateMixGetV2MixPositionAllPosition(self, params):
        return {"data": [dict(symbol=self.markets[s]["id"], total=str(abs(q)),
                              holdSide="long" if q > 0 else "short") for s, q in self.pos.items()]}

    def privateMixGetV2MixAccountAccounts(self, params):
        return {"data": [{"marginCoin": "SUSDT", "accountEquity": "2900"}]}


def state(trend=None, mn_qty=None, hold=None, mark=None):
    return dict(trend=dict(open=trend or {}), mn=dict(weights={}, mark_px={}, base=0.0),
                sleeve=dict(hold=hold or {}, mark_px=mark or {}), exec=dict(mn_qty=mn_qty or {}))


def trec(side, entry, units, notional, stop):
    return dict(side=side, entry=entry, units=units, notional=notional, stop=stop)


# ------------------------------------------------------------------ targets

def test_targets_net_the_three_books():
    st = state(trend={"XRPUSDT:1h": trec("long", 2.0, 3, 10.0, 1.8),       # 3 units x 5 coins
                      "XRPUSDT:4h": trec("short", 2.0, 1, 4.0, 2.2)},      # -2 coins
               mn_qty={"XRPUSDT": -1.0, "SOLUSDT": 0.5},
               hold={"BTCUSDT": -50.0}, mark={"BTCUSDT": 100000.0})
    t = cb.book_targets(st)
    assert abs(t["XRPUSDT"] - (15 - 2 - 1)) < 1e-12
    assert t["SOLUSDT"] == 0.5 and abs(t["BTCUSDT"] + 0.0005) < 1e-15


def test_breach_is_sticky_and_removes_only_that_position():
    st = state(trend={"XRPUSDT:1h": trec("long", 2.0, 1, 10.0, 1.8),
                      "ADAUSDT:4h": trec("short", 1.0, 1, 10.0, 1.1)})
    assert cb.mark_breaches(st, {"XRPUSDT": 1.79, "ADAUSDT": 1.05}) == ["XRPUSDT:1h"]
    assert "XRPUSDT" not in cb.book_targets(st) and "ADAUSDT" in cb.book_targets(st)
    assert cb.mark_breaches(st, {"XRPUSDT": 1.95}) == []                  # bounced: still out
    assert "XRPUSDT" not in cb.book_targets(st)
    assert cb.mark_breaches(st, {"ADAUSDT": 1.11}) == ["ADAUSDT:4h"]      # short stop is ABOVE


def test_demo_routing_keeps_dollars():
    px = {"BTCUSDT": 100000.0, "ETHUSDT": 4000.0, "XRPUSDT": 2.0, "SOLUSDT": 200.0}
    r = cb.route_demo({"SOLUSDT": 1.0, "XRPUSDT": 10.0}, px)
    p = cb.proxy("SOLUSDT")
    assert p in cb.DEMO_COINS and cb.proxy("SOLUSDT") == p                 # deterministic
    dollars = sum(q * px[s] for s, q in r.items())
    assert abs(dollars - (200.0 + 20.0)) < 1e-9


# ------------------------------------------------------------------ order planning

def test_plan_open_add_reduce_close():
    px = {"A": 10.0}
    assert cb.plan_orders({"A": 2.0}, {}, px) == [("A", "buy", 2.0, False, "open")]
    assert cb.plan_orders({"A": 3.0}, {"A": 2.0}, px) == [("A", "buy", 1.0, False, "add")]
    assert cb.plan_orders({"A": 1.0}, {"A": 2.0}, px) == [("A", "sell", 1.0, True, "reduce")]
    assert cb.plan_orders({}, {"A": 0.2}, px) == [("A", "sell", 0.2, True, "close")]   # $2: a close always goes


def test_plan_skips_small_adjustments():
    assert cb.plan_orders({"A": 2.3}, {"A": 2.0}, {"A": 10.0}) == []       # $3 change


def test_plan_flip_closes_then_opens():
    o = cb.plan_orders({"A": -1.0}, {"A": 2.0}, {"A": 10.0})
    assert o == [("A", "sell", 2.0, True, "close"), ("A", "sell", 1.0, False, "open")]
    o = cb.plan_orders({"A": -0.3}, {"A": 2.0}, {"A": 10.0})             # new side is $3: close only
    assert o == [("A", "sell", 2.0, True, "close")]


# ------------------------------------------------------------------ execution against the fake venue

PX = {"BTCUSDT": 100000.0, "ETHUSDT": 4000.0, "XRPUSDT": 2.0}


def fake_demo():
    return FakeEx(px={"SBTC/SUSDT:SUSDT": 100000.0, "SETH/SUSDT:SUSDT": 4000.0, "SXRP/SUSDT:SUSDT": 2.0})


def test_execute_reconciles_and_is_idempotent():
    ex = fake_demo()
    v = cb.Venue(ex, "demo")
    st = state(mn_qty={"XRPUSDT": 20.0, "ETHUSDT": -0.01})
    cb.execute(st, v, "demo", PX, dry=False)
    assert abs(ex.pos["SXRP/SUSDT:SUSDT"] - 20.0) < 1e-9 and abs(ex.pos["SETH/SUSDT:SUSDT"] + 0.01) < 1e-9
    n = len([o for o in ex.orders if "triggerPrice" not in o["params"]])
    cb.execute(st, v, "demo", PX, dry=False)                              # nothing changed
    assert len([o for o in ex.orders if "triggerPrice" not in o["params"]]) == n
    assert ex.margin[0] == "cross"


def test_leftover_positions_are_closed():
    ex = fake_demo()
    ex.pos["SBTC/SUSDT:SUSDT"] = 0.001                                    # e.g. longtrend_bot's leftover
    cb.execute(state(), cb.Venue(ex, "demo"), "demo", PX, dry=False)
    assert "SBTC/SUSDT:SUSDT" not in ex.pos


def test_disaster_stops_follow_the_position():
    ex = fake_demo()
    v = cb.Venue(ex, "demo")
    st = state(mn_qty={"XRPUSDT": 20.0})
    cb.execute(st, v, "demo", PX, dry=False)
    trig = [o for o in ex.orders if "triggerPrice" in o["params"]]
    assert len(trig) == 1 and trig[0]["side"] == "sell" and trig[0]["params"]["reduceOnly"]
    assert abs(trig[0]["params"]["triggerPrice"] - 2.0 * (1 - cb.CAT_STOP)) < 1e-6
    st["exec"]["mn_qty"] = {"XRPUSDT": -20.0}                             # flip to short
    cb.execute(st, v, "demo", PX, dry=False)
    trig = [o for o in ex.orders if "triggerPrice" in o["params"]]
    assert len(ex.cancelled) == 1 and trig[-1]["side"] == "buy"
    assert abs(trig[-1]["params"]["triggerPrice"] - 2.0 * (1 + cb.CAT_STOP)) < 1e-6
    st["exec"]["mn_qty"] = {}
    cb.execute(st, v, "demo", PX, dry=False)
    assert not ex.pos and len(ex.cancelled) == 2 and not st["exec"]["stops"]


def test_price_mismatch_is_refused():
    ex = FakeEx(prefix="", quote="USDT", coins=("PEPE",), px={"PEPE/USDT:USDT": 0.00001})
    st = state(mn_qty={"PEPEUSDT": 1_000_000.0})
    sent = cb.execute(st, cb.Venue(ex, "live"), "live", {"PEPEUSDT": 0.01}, dry=False)  # 1000x off
    assert sent == [] and not ex.pos


def test_contract_size_conversion():
    ex = FakeEx(prefix="", quote="USDT", coins=("ABC",), px={"ABC/USDT:USDT": 1.0}, cs={"ABC": 10.0})
    cb.execute(state(mn_qty={"ABCUSDT": 50.0}), cb.Venue(ex, "live"), "live", {"ABCUSDT": 1.0}, dry=False)
    o = [o for o in ex.orders if "triggerPrice" not in o["params"]][0]
    assert o["amount"] == 5.0 and ex.pos["ABC/USDT:USDT"] == 50.0          # 5 contracts = 50 coins


def test_dry_places_nothing_and_keeps_a_ledger():
    ex = FakeEx(prefix="", quote="USDT", coins=("XRP", "SOL"), px={})
    st = state(mn_qty={"XRPUSDT": 20.0, "SOLUSDT": 0.5, "NOTLISTEDUSDT": 3.0})
    cb.execute(st, cb.Venue(ex, "dry"), "dry", {"XRPUSDT": 2.0, "SOLUSDT": 200.0, "NOTLISTEDUSDT": 5.0}, dry=True)
    assert ex.orders == []
    assert st["exec"]["virtual_pos"] == {"XRP/USDT:USDT": 20.0, "SOL/USDT:USDT": 0.5}
    assert st["exec"]["unmapped"] == ["NOTLISTEDUSDT"]


# ------------------------------------------------------------------ gates

def test_live_is_refused_without_allow_real():
    assert cb.ALLOW_REAL is False
    try:
        cb.resolve("live")
    except SystemExit as e:
        assert "ALLOW_REAL" in str(e)
    else:
        raise AssertionError("live mode started with ALLOW_REAL False")
    cb.resolve("demo")                                                    # demo is allowed


def test_one_account_one_bot():
    other = lambda: ["pid 3432: python longtrend_bot.py"]  # noqa: E731
    for mode in ("demo", "live"):
        try:
            cb.guard_one_bot(mode, lister=other)
        except SystemExit:
            pass
        else:
            raise AssertionError(f"{mode} started beside longtrend_bot")
    cb.guard_one_bot("dry", lister=other)                                 # dry trades nothing
    cb.guard_one_bot("demo", lister=lambda: ["pid 9: python combo_bot.py --mode dry"])
    cb.guard_one_bot("demo", lister=lambda: [])


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\n{len(tests)} passed")
