"""Offline tests for final_books.py - the books `combo_bot.py --final` adds - and the account's 10x guard. No network:
the data functions are replaced by synthetic bars, funding by a function. Each rule is tested where it must fire and
where it must not.

    python tests/test_final_books.py
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
import final_books as fb  # noqa: E402
import mn_paper as mp  # noqa: E402

cp.set_dir(Path(tempfile.mkdtemp()))
H4 = fb.H4
NOFUND = lambda s, a, b: 0.0  # noqa: E731
ON_TIME = lambda day: int(pd.Timestamp(day).timestamp() * 1000) + 600_000  # noqa: E731   10 minutes after the close


def daily_bars(closes, end="2026-10-08", qvol=1e6):
    t = pd.date_range(end=end, periods=len(closes), freq="D")
    return pd.DataFrame({"time": t, "close": np.asarray(closes, float), "qvol": qvol})


def account(eq=300.0):
    st = dict(equity=eq, cum=dict(trend=0.0, mn=0.0, sleeve=0.0, fees=0.0), last_day=None, exec={},
              trend=dict(open={}), mn=dict(weights={}, mark_px={}, base=0.0), sleeve=dict(hold={}, mark_px={}))
    st["fin"] = fb.fresh()
    return st


# ------------------------------------------------------------------ the MN blend and carry

def test_mn_blend_is_half_momentum_half_rsi():
    """30 coins: momentum and RSI disagree on purpose. A coin that leads both rankings holds 0.5/k; a coin long on
    one and short on the other nets to nothing; gross stays at or under 1."""
    rng = np.random.default_rng(1)
    bars, elig = {}, []
    for i in range(30):
        c = 100 * np.cumprod(1 + rng.normal(0, 0.02, 75))
        bars[f"C{i:02d}USDT"] = daily_bars(c)
        elig.append(f"C{i:02d}USDT")
    m, r, w = fb.MOM_TARGET(bars, elig), fb.rsi_target(bars, elig), fb.mn_blend_target(bars, elig)
    assert m and r and m != r, "the test needs the two rankings to differ"
    for s in set(m) | set(r):
        assert abs(w.get(s, 0.0) - (0.5 * m.get(s, 0.0) + 0.5 * r.get(s, 0.0))) < 1e-12
    assert sum(abs(x) for x in w.values()) <= 1.0 + 1e-12
    k = max(int(30 * mp.FRAC), 3)
    up = daily_bars(np.r_[np.full(40, 100.0), 100 * 1.03 ** np.arange(1, 36)])      # steady riser: RSI 100, top momentum
    bars["UPUSDT"] = up
    w2 = fb.mn_blend_target(bars, elig + ["UPUSDT"])
    assert abs(w2["UPUSDT"] - 0.5 / max(int(31 * mp.FRAC), 3)) < 1e-12 and k == 3


def test_rsi_target_longs_high_rsi_shorts_low():
    bars, elig = {}, []
    for i in range(24):
        drift = (i - 12) / 400                                                       # C00 falls hardest, C23 rises most
        bars[f"C{i:02d}USDT"] = daily_bars(100 * np.cumprod(np.r_[1.0, np.full(74, 1 + drift)] *
                                                            np.r_[1.0, np.tile([1.01, 0.99], 37)]))
        elig.append(f"C{i:02d}USDT")
    w = fb.rsi_target(bars, elig)
    assert w["C23USDT"] > 0 and w["C00USDT"] < 0 and len(w) == 6


def test_carry_target_shorts_the_highest_funding():
    f7 = {f"C{i:02d}USDT": (i - 10) / 1e4 for i in range(25)}                      # C24 pays the most
    w = fb.carry_target(f7)
    k = max(int(25 * fb.CARRY_FRAC), 3)
    assert len(w) == 2 * k
    assert all(w[f"C{i:02d}USDT"] < 0 for i in range(25 - k, 25))                 # highest funding: short
    assert all(w[f"C{i:02d}USDT"] > 0 for i in range(k))                          # lowest (negative): long
    assert abs(sum(w.values())) < 1e-12 and fb.carry_target(dict(list(f7.items())[:19])) == {}


def test_carry_short_exit_and_v2_targets_untouched_without_final():
    st = account()
    st["fin"]["carry"].update(weights={"XRPUSDT": -0.1}, mark_px={"XRPUSDT": 2.0}, base=150.0)
    st["exec"]["carry_qty"] = {"XRPUSDT": -0.1 * 150.0 / 2.0}
    assert fb.carry_squeeze_exits(st, {"XRPUSDT": 2.0 * 1.49}) == []
    assert cb.book_targets(st)["XRPUSDT"] == -7.5
    assert fb.carry_squeeze_exits(st, {"XRPUSDT": 3.0}) == ["XRPUSDT"]
    assert "XRPUSDT" not in cb.book_targets(st) and abs(st["cum"]["carry"] - 150 * -0.1 * 0.5) < 1e-9
    v2 = account()
    v2.pop("fin")
    v2["exec"]["carry_qty"] = {"XRPUSDT": -7.5}                                   # ignored: no --final
    assert cb.book_targets(v2) == {}


# ------------------------------------------------------------------ the account's 10x guard

def test_gross_gate_reductions_first_then_opens_until_the_cap():
    px = {"A": 1.0, "B": 1.0, "C": 1.0}
    actual = {"A": 900.0}                                                         # 9x of $100 already on
    orders = [("B", "buy", 50.0, False, "open"), ("A", "sell", 300.0, True, "reduce"), ("C", "buy", 400.0, False, "open")]
    ok, no = fb.gross_gate(orders, actual, px, 100.0)                             # 900 - 300 + 50 = 650; + 400 > 1000
    assert [o[0] for o in ok] == ["B", "A"] and [o[0] for o in no] == ["C"]
    ok, no = fb.gross_gate(orders, actual, px, 100.0, cap=10.5)                   # 1050 fits under 10.5x
    assert not no and len(ok) == 3
    ok, no = fb.gross_gate([("C", "buy", 300.0, False, "open")], {}, px, 100.0)
    assert not no


def test_execute_holds_the_account_under_10x():
    """Books that together want 14x: the dry ledger stops at 10x, and reductions still go."""
    st = account(100.0)
    st["fin"]["daily"]["open"] = {f"C{i}USDT": dict(qty=200.0, entry=1.0, t_ms=0) for i in range(7)}
    px = {f"C{i}USDT": 1.0 for i in range(7)}
    cb.execute(st, None, "dry", px, dry=True)
    led = st["exec"]["virtual_pos"]
    assert sum(abs(q) for q in led.values()) <= 1000.0 + 1e-9 and len(led) == 5
    st["fin"]["daily"]["open"].pop("C0USDT")                                      # a close frees room
    cb.execute(st, None, "dry", px, dry=True)
    led = st["exec"]["virtual_pos"]
    assert "C0USDT" not in led and sum(abs(q) for q in led.values()) == 1000.0


# ------------------------------------------------------------------ the daily book

def daily_setup(path_last, coins=40):
    """40 eligible coins (flat), plus BRK whose last closes are `path_last`."""
    bars = {f"F{i:02d}USDT": daily_bars(np.full(75, 10.0 + i * 0.01), qvol=1e6 - i) for i in range(coins - 1)}
    bars["BRKUSDT"] = daily_bars(np.r_[np.full(75 - len(path_last), 100.0) + np.tile([0.5, -0.5], 50)[:75 - len(path_last)],
                                       path_last], qvol=2e6)
    fb.LAST.clear()
    fb.LAST.update(bars=bars, universe=(list(bars), {s: 5.0 for s in bars}))
    return bars


def test_daily_book_buys_the_break_and_sells_under_the_20_day_mean():
    daily_setup([112.0])
    st = account()
    st["fin"]["carry"]["last_rebal"] = "2026-10-08"                              # carry not due: its fee stays out
    st["last_day"] = "2026-10-09"
    fb.daily_books(st, {"BRKUSDT": 113.0}, fund=NOFUND, clock_ms=ON_TIME("2026-10-09"))
    p = st["fin"]["daily"]["open"]["BRKUSDT"]
    assert p["entry"] == 113.0 and abs(p["qty"] * 113.0 - fb.K_DAILY * 300.0 / fb.SLOTS) < 1e-9
    assert len(st["fin"]["daily"]["open"]) == 1 and st["fin"]["uni40"][0] == "BRKUSDT"
    fb.daily_books(st, {"BRKUSDT": 113.0}, fund=NOFUND, clock_ms=ON_TIME("2026-10-09"))                           # same day: nothing again
    assert st["fin"]["daily"]["taken"] == 1
    # next day: a close UNDER the 20-day mean but ABOVE the 30-day mean - the 20-day exit sells, the old one would not
    path = [112.0] + [130.0] * 18 + [120.0]                                      # mean20 128.6, mean30 119.1
    bars = daily_setup(path)
    c = bars["BRKUSDT"].close.to_numpy()
    assert c[-1] < c[-20:].mean() and c[-1] > c[-30:].mean(), "the test needs the 20- and 30-day exits to disagree"
    bars["BRKUSDT"]["time"] = pd.date_range(end="2026-10-09", periods=75, freq="D")
    for s in bars:
        bars[s]["time"] = pd.date_range(end="2026-10-09", periods=75, freq="D")
    st["last_day"] = "2026-10-10"
    eq = st["equity"]
    fb.daily_books(st, {"BRKUSDT": 105.0}, fund=lambda s, a, b: 0.001, clock_ms=ON_TIME("2026-10-10"))
    assert "BRKUSDT" not in st["fin"]["daily"]["open"]
    q = 150.0 / 8 / 113.0
    assert abs(st["equity"] - (eq + q * (105.0 - 113.0) - q * 113.0 * 0.001 - q * 105.0 * fb.SIDE_FEE)) < 1e-9


def test_daily_book_buys_only_soon_after_the_close():
    """A process started 5 hours after the close does not buy that close's signal; it still sells."""
    daily_setup([112.0])
    st = account()
    st["fin"]["carry"]["last_rebal"] = "2026-10-08"
    st["fin"]["daily"]["open"]["F00USDT"] = dict(qty=1.0, entry=10.0, t_ms=0)    # bought long ago: past the 31-day cap
    st["last_day"] = "2026-10-09"
    fb.daily_books(st, {"BRKUSDT": 113.0, "F00USDT": 10.0}, fund=NOFUND, clock_ms=ON_TIME("2026-10-09") + 5 * 3_600_000)
    assert "BRKUSDT" not in st["fin"]["daily"]["open"] and st["fin"]["last_day"] == "2026-10-09"
    assert "F00USDT" not in st["fin"]["daily"]["open"], "a late process must still exit (age past the 31-day cap)"


def test_a_late_carry_rebalance_is_marked_at_the_live_price():
    """Rebalanced 5h after the close: the basket's marks are the live prices, so day 1 books only what it held."""
    bars = daily_setup([100.0])
    elig = mp.eligible(bars, "2026-10")
    fund = lambda s, a, b: 0.0001 * (elig.index(s) if s in elig else 0)  # noqa: E731   distinct funding sums
    live = {s: 2.0 * float(d.close.iloc[-1]) for s, d in bars.items()}
    for late, want in ((False, "close"), (True, "live")):
        daily_setup([100.0])
        st = account()
        st["last_day"] = "2026-10-09"
        clock = ON_TIME("2026-10-09") + (5 * 3_600_000 if late else 0)
        fb.daily_books(st, live, fund=fund, clock_ms=clock)
        cr = st["fin"]["carry"]
        assert cr["weights"] and set(cr["mark_px"]) == set(cr["weights"])
        for s, px in cr["mark_px"].items():
            assert px == (live[s] if want == "live" else float(bars[s].close.iloc[-1])), (late, s)
        q = st["exec"]["carry_qty"]
        for s, w in cr["weights"].items():
            assert abs(q[s] - w * cr["base"] / cr["mark_px"][s]) < 1e-12


def test_poll_marks_a_late_mn_rebalance_at_live_prices():
    """combo_paper.daily ranks the MN basket on the close and marks it there; the final bot re-marks a LATE rebalance at
    the live price (and v2, without --final, is left exactly as it was)."""
    saved = (cp.daily, cp.trend_poll, fb.daily_books, fb.capit2_poll)
    live = {"AUSDT": 12.0, "BUSDT": 3.0}

    def fake_daily(st):
        st["mn"].update(weights={"AUSDT": 0.25, "BUSDT": -0.25}, mark_px={"AUSDT": 10.0, "BUSDT": 4.0}, base=100.0,
                        last_rebal="2026-01-01")
        st["last_day"] = "2026-01-01"                                             # long ago: late
    try:
        cp.daily, cp.trend_poll = fake_daily, (lambda st, a, b: None)
        fb.daily_books, fb.capit2_poll = (lambda *a, **k: None), (lambda *a, **k: None)
        for final in (True, False):
            st = account(100.0)
            st["mn"]["last_rebal"] = None
            if not final:
                st.pop("fin")
            cb.poll(st, None, "dry", ({}, {}), prices_fn=lambda: dict(live))
            want = live if final else {"AUSDT": 10.0, "BUSDT": 4.0}
            assert st["mn"]["mark_px"] == want, (final, st["mn"]["mark_px"])
            assert st["exec"]["mn_qty"] == {"AUSDT": 25.0 / want["AUSDT"], "BUSDT": -25.0 / want["BUSDT"]}
    finally:
        cp.daily, cp.trend_poll, fb.daily_books, fb.capit2_poll = saved


def test_daily_book_respects_slots_and_history():
    bars = daily_setup([112.0])
    for i in range(10):                                                           # 10 more breakouts
        bars[f"B{i}USDT"] = bars["BRKUSDT"].copy()
    young = bars["BRKUSDT"].iloc[-50:].reset_index(drop=True)                     # 50 days of history: too young
    bars["YNGUSDT"] = young
    fb.LAST["universe"] = (list(bars), {s: 5.0 for s in bars})
    st = account()
    st["last_day"] = "2026-10-09"
    fb.daily_books(st, {s: 113.0 for s in bars}, fund=NOFUND, clock_ms=ON_TIME("2026-10-09"))
    assert len(st["fin"]["daily"]["open"]) == fb.SLOTS and "YNGUSDT" not in st["fin"]["daily"]["open"]
    bars = daily_setup([112.0])                                                   # slots free: still too young
    bars["YNGUSDT"] = bars["BRKUSDT"].iloc[-50:].reset_index(drop=True)
    fb.LAST["universe"] = (list(bars), {s: 5.0 for s in bars})
    st = account()
    st["last_day"] = "2026-10-09"
    fb.daily_books(st, {s: 113.0 for s in bars}, fund=NOFUND, clock_ms=ON_TIME("2026-10-09"))
    assert "YNGUSDT" in st["fin"]["uni40"] and set(st["fin"]["daily"]["open"]) == {"BRKUSDT"}


# ------------------------------------------------------------------ capit2

def crash4h(last4, spike=True):
    c = [100.0]
    for i in range(130):
        c.append(c[-1] * (1.006 if i % 3 else 0.995))
    for i in range(6):
        c.append(c[-1] * 0.97)
    c = np.array(c)                                                               # RSI crosses under 20 on the last bar
    n = len(c)
    t = last4 - (n - 1) * H4 + np.arange(n) * H4
    q = np.full(n, 1000.0)
    if spike:
        q[-1] = 5000.0
    return pd.DataFrame(dict(t=t.astype("int64"), o=c, h=c * 1.002, l=c * 0.998, c=c, q=q))


def slow4h(last4):
    """RSI crosses under 20 on a volume spike at the last bar, but the coin is down less than 10% over 24h."""
    c = [100.0]
    for i in range(130):
        c.append(c[-1] * (1.004 if i % 2 == 0 else 0.997))
    for i in range(10):
        c.append(c[-1] * 0.975)
    c = np.array(c)
    r = fb.rsi(c)
    i = next(j for j in range(60, len(c)) if r[j - 1] >= 20 > r[j])
    c = c[:i + 1]
    n = len(c)
    t = last4 - (n - 1) * H4 + np.arange(n) * H4
    q = np.full(n, 1000.0)
    q[-1] = 5000.0
    return pd.DataFrame(dict(t=t.astype("int64"), o=c, h=c * 1.002, l=c * 0.998, c=c, q=q))


def capit_state(n_crash, last4, spike=True):
    st = account()
    coins = [f"K{i}USDT" for i in range(n_crash)] + [f"Q{i}USDT" for i in range(40 - n_crash)]
    st["fin"]["uni40"] = coins
    data = {s: crash4h(last4, spike) if s.startswith("K") else
            crash4h(last4).assign(c=lambda d: 100.0, o=100.0, h=100.2, l=99.8) for s in coins}
    return st, (lambda s, now: data[s][data[s].t + H4 <= now].reset_index(drop=True)), data


def test_capit2_signal_needs_five_coins_volume_and_the_24h_drop():
    last4 = 1_790_000_000_000 // H4 * H4
    now = last4 + H4 + 60_000
    d = crash4h(last4)
    assert d.c.iloc[-1] / d.c.iloc[-7] - 1 <= -0.10 and fb.rsi(d.c.to_numpy())[-1] < 20 <= fb.rsi(d.c.to_numpy())[-2]
    st, get4, _ = capit_state(5, last4)
    fb.capit2_poll(st, {}, now, fund=NOFUND, get4=get4)
    assert len(st["fin"]["capit2"]["pending"]) == 5 and st["fin"]["last_4h"] == last4
    st, get4, _ = capit_state(4, last4)                                          # 4 coins: breadth not met
    fb.capit2_poll(st, {}, now, fund=NOFUND, get4=get4)
    assert not st["fin"]["capit2"]["pending"]
    st, get4, _ = capit_state(5, last4, spike=False)                             # no volume spike: no signal
    fb.capit2_poll(st, {}, now, fund=NOFUND, get4=get4)
    assert not st["fin"]["capit2"]["pending"]
    st, get4, data = capit_state(6, last4)                                       # a 6th coin crossing on volume
    data["K5USDT"] = slow4h(last4)                                               # but down only ~9.5% in 24h
    assert -0.10 < data["K5USDT"].c.iloc[-1] / data["K5USDT"].c.iloc[-7] - 1 < -0.05
    assert last4 in fb.capit_hits(data["K5USDT"])
    fb.capit2_poll(st, {}, now, fund=NOFUND, get4=get4)
    assert len(st["fin"]["capit2"]["pending"]) == 5 and "K5USDT" not in st["fin"]["capit2"]["pending"]


def test_capit2_fills_only_through_the_limit_and_takes_the_target():
    last4 = 1_790_000_000_000 // H4 * H4
    now = last4 + H4 + 60_000
    st, get4, data = capit_state(5, last4)
    fb.capit2_poll(st, {}, now, fund=NOFUND, get4=get4)
    lim = st["fin"]["capit2"]["pending"]["K0USDT"]["lim"]
    assert abs(lim - data["K0USDT"].c.iloc[-1] * 0.98) < 1e-9
    px = {f"K{i}USDT": lim * 0.999 for i in range(5)}                            # AT the limit, not 0.3% through
    fb.capit2_poll(st, px, now + 60_000, fund=NOFUND, get4=get4)
    assert not st["fin"]["capit2"]["open"] and len(st["fin"]["capit2"]["pending"]) == 5
    px["K0USDT"] = lim * 0.996                                                   # through: filled at that price
    fb.capit2_poll(st, px, now + 120_000, fund=NOFUND, get4=get4)
    p = st["fin"]["capit2"]["open"]["K0USDT"]
    assert p["entry"] == lim * 0.996 and abs(p["qty"] * p["entry"] - fb.K_CAPIT2 * 300.0 / fb.SLOTS) < 1e-9
    assert cb.book_targets(st)["K0USDT"] == p["qty"]
    fb.capit2_poll(st, {"K0USDT": p["entry"] * 1.049}, now + 180_000, fund=NOFUND, get4=get4)
    assert "K0USDT" in st["fin"]["capit2"]["open"]
    eq = st["equity"]
    fb.capit2_poll(st, {"K0USDT": p["entry"] * 1.05}, now + 240_000, fund=NOFUND, get4=get4)
    assert "K0USDT" not in st["fin"]["capit2"]["open"]
    assert abs(st["equity"] - (eq + p["qty"] * p["entry"] * 0.05 - p["qty"] * p["entry"] * 1.05 * fb.SIDE_FEE)) < 1e-9
    fb.capit2_poll(st, {}, last4 + 2 * H4, fund=NOFUND, get4=get4)               # the limit's bar is over
    assert not st["fin"]["capit2"]["pending"] and st["fin"]["capit2"]["cancelled"] == 4


def test_capit2_not_working_after_24_bars_and_the_cap():
    last4 = 1_790_000_000_000 // H4 * H4
    st = account()
    sig = last4 - 30 * H4
    st["fin"]["capit2"]["open"]["K0USDT"] = dict(qty=1.0, entry=100.0, t_ms=sig + H4 + 1, signal_t=sig)
    t = sig + np.arange(-60, 31) * H4
    c = np.full(len(t), 101.0)
    data = pd.DataFrame(dict(t=t.astype("int64"), o=c, h=c * 1.001, l=c * 0.999, c=c, q=1000.0))
    get4 = lambda s, now: data[data.t + H4 <= now].reset_index(drop=True)  # noqa: E731
    fb.capit2_poll(st, {"K0USDT": 101.0}, last4 + H4 + 1, fund=NOFUND, get4=get4)
    assert "K0USDT" in st["fin"]["capit2"]["open"], "in profit at bar 30 and under the cap: it stays"
    data.loc[data.t == sig + 26 * H4, "c"] = 99.0                                 # a close under the entry at bar 26
    st["fin"]["last_4h"] = None
    fb.capit2_poll(st, {"K0USDT": 101.0}, last4 + H4 + 1, fund=NOFUND, get4=get4)
    assert "K0USDT" not in st["fin"]["capit2"]["open"]


def test_enable_installs_the_blend_and_the_6_25x_trend_guard():
    saved = (mp.target, mp.fetch_all, mp.perp_universe, cp.bp.MAX_LEVERAGE)
    try:
        fb.enable(cp)
        assert mp.target is fb.mn_blend_target and cp.bp.MAX_LEVERAGE == 6.25
        fb.enable(cp)                                                              # twice: still one wrapper deep
        assert mp.fetch_all.__closure__[0].cell_contents is fb._FETCH_ALL or \
            fb._FETCH_ALL in [c.cell_contents for c in mp.fetch_all.__closure__]
    finally:
        mp.target, mp.fetch_all, mp.perp_universe, cp.bp.MAX_LEVERAGE = saved
    assert fb.TREND_LEV + 1.0 + fb.K_CARRY + 1.0 + 0.25 + fb.K_DAILY + fb.K_CAPIT2 == fb.GROSS_CAP


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\n{len(tests)} passed")
