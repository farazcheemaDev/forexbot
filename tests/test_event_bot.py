"""Offline tests for event_bot.py - the paper account that runs only the final machine's event books. No network: the data
functions are replaced by synthetic bars. Each switch is tested where it must change something AND against a CONTROL where
the same input, without event_bot.configure(), does produce what is being switched off - a test that cannot see the thing it
switches off proves nothing.

    python tests/test_event_bot.py
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.argv = [sys.argv[0]]
import combo_bot as cb  # noqa: E402
import combo_paper as cp  # noqa: E402
import event_bot as eb  # noqa: E402
import final_books as fb  # noqa: E402
import mn_paper as mp  # noqa: E402

cp.set_dir(Path(tempfile.mkdtemp()))
NOFUND = lambda s, a, b: 0.0  # noqa: E731
ON_TIME = lambda day: int(pd.Timestamp(day).timestamp() * 1000) + 600_000  # noqa: E731


def daily_bars(closes, end="2026-10-08", qvol=1e6):
    t = pd.date_range(end=end, periods=len(closes), freq="D")
    return pd.DataFrame({"time": t, "close": np.asarray(closes, float), "qvol": qvol})


def final_account(eq=300.0):
    st = dict(equity=eq, cum=dict(trend=0.0, mn=0.0, sleeve=0.0, fees=0.0), last_day=None, exec={},
              trend=dict(open={}), mn=dict(weights={}, mark_px={}, base=0.0), sleeve=dict(hold={}, mark_px={}))
    st["fin"] = fb.fresh()
    return st


def setup_bars(path_last, coins=40):
    bars = {f"F{i:02d}USDT": daily_bars(np.full(75, 10.0 + i * 0.01), qvol=1e6 - i) for i in range(coins - 1)}
    bars["BRKUSDT"] = daily_bars(np.r_[np.full(75 - len(path_last), 100.0) + np.tile([0.5, -0.5], 50)[:75 - len(path_last)],
                                       path_last], qvol=2e6)
    fb.LAST.clear()
    fb.LAST.update(bars=bars, universe=(list(bars), {s: 5.0 for s in bars}))
    return bars


class configured:
    """event_bot.configure() for the length of a with-block, always restored."""

    def __enter__(self):
        self.saved = eb.configure()

    def __exit__(self, *a):
        eb.restore(self.saved)


# ------------------------------------------------------------------ the wrapper itself

def test_importing_event_bot_changes_nothing_in_any_other_process():
    """Only configure() changes anything, and only in the calling process: after the import the machine's weights and rules
    are exactly the deployed ones (main, fresh and v2 never call it)."""
    assert (cp.K_MN, cp.K_SLEEVE) == (1.0, 1.0)
    assert (fb.K_CARRY, fb.K_DAILY, fb.K_CAPIT2) == (0.5, 0.5, 1.0)
    assert fb.daily_entry(np.r_[np.full(60, 100.0), 130.0]) is True
    assert cp.signal("bear", 0.0) != 0, "the bear sleeve must still trade where event_bot is not running"
    with configured():
        assert (cp.K_MN, cp.K_SLEEVE, fb.K_DAILY, fb.K_CARRY) == (0.0, 0.0, 0.0, 1.0)
        assert fb.K_CAPIT2 == 1.0, "capit2 keeps the machine's weight"
        assert fb.daily_entry(np.r_[np.full(60, 100.0), 130.0]) is False
        assert cp.signal("bear", 0.0) == 0
        assert cp.trend_poll({}, {}, {}) is None
    assert (cp.K_MN, cp.K_SLEEVE, fb.K_DAILY, fb.K_CARRY) == (1.0, 1.0, 0.5, 0.5)       # restored
    assert fb.daily_entry(np.r_[np.full(60, 100.0), 130.0]) is True


def test_argv_is_fixed_to_a_dry_paper_account_and_refuses_overrides():
    assert eb.argv_for([]) == ["combo_bot.py", "--mode", "dry", "--final", "--account", "events"]
    assert eb.argv_for(["--status"])[-1] == "--status" and eb.argv_for(["--once"])[-1] == "--once"
    for bad in ("--mode", "--mode=live", "--account", "--crowd", "--wick", "--final", "--wick-usd=30"):
        try:
            eb.argv_for([bad])
        except SystemExit:
            continue
        raise AssertionError(f"{bad} must be refused")
    assert cb.state_dir("dry", True, eb.ACCOUNT).name == "combo_bot_dry_final_events"
    try:
        cb.state_dir("live", True, eb.ACCOUNT)
    except SystemExit:
        pass
    else:
        raise AssertionError("--account must stay dry-only")


# ------------------------------------------------------------------ the switches

def test_the_daily_breakout_book_never_buys_while_the_machine_would():
    st = final_account()
    setup_bars([112.0])
    st["fin"]["carry"]["last_rebal"] = "2026-10-08"
    st["last_day"] = "2026-10-09"
    fb.daily_books(st, {"BRKUSDT": 113.0}, fund=NOFUND, clock_ms=ON_TIME("2026-10-09"))
    assert "BRKUSDT" in st["fin"]["daily"]["open"], "control: the deployed rule buys this break"
    st = final_account()
    setup_bars([112.0])
    st["fin"]["carry"]["last_rebal"] = "2026-10-08"
    st["last_day"] = "2026-10-09"
    with configured():
        fb.daily_books(st, {"BRKUSDT": 113.0}, fund=NOFUND, clock_ms=ON_TIME("2026-10-09"))
    assert st["fin"]["daily"]["open"] == {} and st["fin"]["daily"]["taken"] == 0
    assert st["cum"].get("daily", 0.0) == 0.0 and st["cum"]["fees"] == 0.0


def test_carry_stays_on_at_150_dollars_where_the_machines_carry_switches_off():
    """The registered change of weight: at $150 the machine's x0.5 stake is under Bitget's $5 and the whole basket is
    dropped; at x1.0 it is above it and the book holds. 40 coins here (k = 8 a side); with the real 60 the same arithmetic
    puts the machine's switch-off at about $240 and the events account's at about $120."""
    def run(eq):
        setup_bars([100.0])
        bars = fb.LAST["bars"]
        elig = mp.eligible(bars, "2026-10")
        fund = lambda s, a, b: 0.0001 * (elig.index(s) if s in elig else 0)  # noqa: E731
        st = final_account(eq)
        st["last_day"] = "2026-10-09"
        live = {s: float(d.close.iloc[-1]) for s, d in bars.items()}
        fb.daily_books(st, live, fund=fund, clock_ms=ON_TIME("2026-10-09"))
        return st["fin"]["carry"]
    machine = run(150.0)
    assert machine["weights"] == {} and machine["n_rebal"] == 1, "control: the machine's carry is empty at $150"
    with configured():
        events = run(150.0)
        high = run(300.0)
    assert len(events["weights"]) == 16 and abs(events["base"] - 150.0) < 0.5          # 8 longs + 8 shorts of 40 coins
    assert abs(high["base"] - 300.0) < 0.5 and high["weights"], "x1.0 is the weight at $300 too"
    stake = {abs(w) * events["base"] for w in events["weights"].values()}
    assert min(stake) >= 5.0, stake


def test_market_neutral_and_bear_sleeve_take_no_position_in_a_bear_with_low_breadth():
    """combo_paper.daily on 40 falling coins and a falling BTC: the deployed machine rebalances the MN basket AND opens the
    bear sleeve's bounce long; the events account does neither."""
    rng = np.random.default_rng(7)
    end = pd.Timestamp("2026-11-20")
    bars = {}
    for i in range(40):
        drift = -0.004 + (i - 20) * 0.0002
        c = 100 * np.cumprod(1 + drift + rng.normal(0, 0.004, 100))
        bars[f"C{i:02d}USDT"] = daily_bars(c, end=end.strftime("%Y-%m-%d"), qvol=1e7 - i * 1e4)
    btc = daily_bars(100 * np.cumprod(np.full(130, 0.995)), end=end.strftime("%Y-%m-%d"))
    syms = list(bars)
    saved = (mp.perp_universe, mp.candidates, mp.fetch_all, mp.daily, mp.held_closes, mp.funding_since)
    try:
        mp.perp_universe = lambda: (syms, {s: 5.0 for s in syms})
        mp.candidates = lambda s: s
        mp.fetch_all = lambda s: bars
        mp.daily = lambda sym, limit=120: btc
        mp.held_closes = lambda *a, **k: {}
        mp.funding_since = lambda *a, **k: 0.0
        week = {f"2026-11-{d:02d}": 1 for d in range(14, 21)}                    # seven earlier +1 decisions: the ladder is full
        st = cp.fresh()
        st["sleeve"]["signals"] = dict(week)
        cp.daily(st)
        assert st["mn"]["weights"], "control: the deployed MN book rebalances here"
        assert st["sleeve"]["hold"], "control: the bear sleeve holds its bounce long here (BEAR, breadth under 10%)"
        with configured():
            st = cp.fresh()
            st["sleeve"]["signals"] = dict(week)                                  # even WITH the ladder full: stake x0
            cp.daily(st)
            assert st["mn"]["weights"] == {} and st["mn"]["base"] == 0.0
            assert st["sleeve"]["hold"] == {}, st["sleeve"]["hold"]
            assert st["cum"]["mn"] == 0.0 and st["cum"]["sleeve"] == 0.0 and st["cum"]["fees"] == 0.0
            assert st["last_day"] == "2026-11-21", "the day still advances: the marks and the other books keep their clock"
            st = cp.fresh()                                                       # and from a clean start it never decides +1
            cp.daily(st)
            assert st["sleeve"]["signals"] == {"2026-11-21": 0} and st["sleeve"]["hold"] == {}
    finally:
        (mp.perp_universe, mp.candidates, mp.fetch_all, mp.daily, mp.held_closes, mp.funding_since) = saved


def test_a_whole_poll_with_no_event_to_trade_books_nothing():
    """cb.poll on a fresh events state with every data function stubbed: no trend, MN, sleeve, daily or carry-less P&L, the
    equity unchanged, and the poll finishes (the books it keeps - capit2, bids, news, ndx - are stubbed to idle)."""
    saved = (cp.daily, fb.daily_books, fb.capit2_poll, fb.bids_poll)
    import news_books as nbk
    saved_n = (nbk.news_poll, nbk.ndx_poll)
    called = []
    try:
        cp.daily = lambda st: called.append("daily") or st.update(last_day="2026-11-27")
        fb.daily_books = lambda *a, **k: called.append("daily_books")
        fb.capit2_poll = lambda *a, **k: called.append("capit2")
        fb.bids_poll = lambda *a, **k: called.append("bids")
        nbk.news_poll = lambda *a, **k: called.append("news")
        nbk.ndx_poll = lambda *a, **k: called.append("ndx")
        with configured():
            st = final_account(300.0)
            st["trend"] = cp.fresh()["trend"]
            cb.poll(st, None, "dry", ({}, {}), prices_fn=lambda: {"BTCUSDT": 60000.0})
        assert {"daily_books", "capit2", "bids", "news", "ndx"} <= set(called), called
        assert st["equity"] == 300.0 and st["trend"]["open"] == {}
        assert st["exec"].get("virtual_pos", {}) == {}, "nothing to hold: the dry ledger is empty"
    finally:
        cp.daily, fb.daily_books, fb.capit2_poll, fb.bids_poll = saved
        nbk.news_poll, nbk.ndx_poll = saved_n


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    failed = 0
    for n, f in tests:
        try:
            f()
            print("PASS", n)
        except Exception as e:  # noqa: BLE001
            failed += 1
            import traceback
            print("FAIL", n, type(e).__name__, e)
            traceback.print_exc()
    print(f"\n{len(tests) - failed} passed" + (f", {failed} FAILED" if failed else ""))
    sys.exit(1 if failed else 0)
