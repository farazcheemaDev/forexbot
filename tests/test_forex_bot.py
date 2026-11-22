"""Tests for forex_bot.py: signal parity with the backtest, calendar and New York clock, sizing, the hash-chained log, the MT5 link (fake terminal), and full simulated sessions through the bot's own loop.

Run as a script (no pytest on this PC):  python tests/test_forex_bot.py
"""
import json
import subprocess
import sys
import tempfile
import time
import types
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import forex_bot as fb  # noqa: E402
from backtest.fx_intraday_pub import noise, session_df  # noqa: E402

BARS = ROOT / "strategy_analysis" / "data" / "mt5_1m" / "USTECm.parquet"
_frame = None


def frame():
    global _frame
    if _frame is None:
        _frame = pd.read_parquet(BARS).sort_values("t").reset_index(drop=True).rename(columns={})[["t", "o", "h", "l", "c"]]
    return _frame


class FakeClock:
    def __init__(self, start):
        self.t = start

    def now(self):
        return self.t

    def sleep(self, s):
        self.t = self.t + pd.Timedelta(seconds=s)


class FakeLink:
    """A demo terminal replaying a minute-bar frame: bars, a tick from the bar open +- half the spread, one-position-at-a-time orders."""

    def __init__(self, f, clock, spread=1.2):
        self.f, self.clock, self.spread = f, clock, spread
        self.T, self.O = f.t.to_numpy("int64"), f.o.to_numpy(float)
        self.pos, self.n, self.fail_open, self.stale = [], 0, False, False

    def bars(self, start, end):
        s, e = fb.ms(start), fb.ms(end)
        return self.f[(self.f.t >= s) & (self.f.t < e)]

    def tick(self):
        now = self.clock.now()
        i = int(np.searchsorted(self.T, fb.ms(now), side="right")) - 1
        mid = self.O[i]
        return dict(t=now.timestamp() - (60 if self.stale else 0), bid=mid - self.spread / 2, ask=mid + self.spread / 2)

    def positions(self):
        return [dict(p) for p in self.pos]

    def open(self, side, lots, sl_pct):
        if self.fail_open:
            return dict(ok=False, price=None, retcode=10006, comment="rejected")
        tk = self.tick()
        px = tk["ask"] if side > 0 else tk["bid"]
        self.n += 1
        p = dict(ticket=self.n, side=side, lots=lots, entry=px, sl=px * (1 - sl_pct * side), t=self.clock.now().timestamp())
        self.pos.append(p)
        return dict(ok=True, price=px, ticket=self.n, sl=p["sl"], retcode=10009)

    def close(self, pos):
        tk = self.tick()
        self.pos = [p for p in self.pos if p["ticket"] != pos["ticket"]]
        return dict(ok=True, price=tk["bid"] if pos["side"] > 0 else tk["ask"], retcode=10009)

    def closed_exit(self, ticket):
        return None


def tmpcfg(**kw):
    return fb.Cfg(state_dir=tempfile.mkdtemp(prefix="fb_test_"), **kw)


def a_day(min_trades=1, flip=False):
    """(date, index, A, dates, prev, out, trades) of a recent real session on which the backtest trades."""
    A, dates, prev = session_df(frame(), "NASDAQ")
    out, _, tr = noise(A, prev)
    for i in range(len(dates) - 1, fb.LOOK, -1):
        if tr[i] >= min_trades and np.isfinite(prev[i]) and (not flip or tr[i] >= 2):
            return dates[i].date(), i, A, dates, prev, out, tr
    raise AssertionError("no such day")


# ---------------------------------------------------------------- signal
def test_replay_day_reproduces_the_backtest_on_real_exness_bars():
    n, ok, worst = fb.parity(frame(), 150)
    assert n >= 100 and ok == n and worst < 1e-9


def test_sigma_is_the_mean_of_the_previous_fourteen_sessions_only():
    rng = np.random.default_rng(5)
    O = 100 + rng.normal(0, 1, (30, 390))
    C = O + rng.normal(0, 1, (30, 390))
    i = 20
    expect = pd.DataFrame(np.abs(C / O[:, :1] - 1)).rolling(14).mean().shift(1).to_numpy()[i]
    assert np.allclose(fb.sigma_from_history(O[i - 14:i], C[i - 14:i]), expect)
    assert fb.sigma_from_history(O[:13], C[:13]) is None


def test_the_noise_bounds_and_the_three_way_decision():
    p = fb.Plan(op=100.0, prev=102.0, sig=np.full(390, 0.01))
    ub, lb = p.bounds(30)
    assert abs(ub - 102 * 1.01) < 1e-9 and abs(lb - 100 * 0.99) < 1e-9          # the upper bound uses the larger of open / previous close, the lower the smaller
    assert p.want(30, ub + 0.01) == 1 and p.want(30, ub) == 0 and p.want(30, lb) == 0 and p.want(30, lb - 0.01) == -1 and p.want(30, 101.0) == 0


# ---------------------------------------------------------------- calendar, clock, sizing
def test_calendar():
    assert fb.is_trading_day(date(2026, 11, 30))[0]
    for d, frag in ((date(2026, 11, 26), "holiday"), (date(2026, 11, 27), "early"), (date(2026, 11, 28), "weekend"), (date(2028, 1, 3), "calendar")):
        ok, why = fb.is_trading_day(d)
        assert not ok and frag in why


def test_session_times_follow_new_york_daylight_saving():
    f = lambda d: fb.session_times(d)[0].strftime("%H:%M")  # noqa: E731
    assert f(date(2026, 11, 3)) == "14:30" and f(date(2026, 10, 28)) == "13:30"        # US clocks went back on 2026-11-01
    assert f(date(2026, 3, 2)) == "14:30" and f(date(2026, 3, 10)) == "13:30"          # US forward on 03-08, Europe only on 03-29
    assert fb.session_times(date(2026, 11, 3))[1].strftime("%H:%M") == "21:00"


def test_lot_sizing_and_the_minimum_lot_leverage_cap():
    c = fb.Cfg()
    assert fb.lots_for(300, 28000, c) == 0.05 and fb.lots_for(1000, 28000, c) == 0.17
    assert fb.lots_for(240, 28500, c) == 0.05                                            # 5.9x: allowed
    assert fb.lots_for(230, 28500, c) == 0.0                                             # 6.2x: refused
    assert fb.lots_for(0, 28000, c) == 0.0 and fb.pnl_usd(-1, 100.0, 90.0, 0.05, 1.0) == 0.5


# ---------------------------------------------------------------- the log
def test_the_hash_chain_detects_tampering_and_continues_after_a_restart():
    p = Path(tempfile.mkdtemp()) / "x.jsonl"
    L = fb.ChainLog(p)
    for i in range(3):
        L.append(dict(kind="k", i=i))
    assert fb.ChainLog.verify(p) == (True, 3)
    fb.ChainLog(p).append(dict(kind="k", i=3))                                           # a restarted process continues the chain
    assert fb.ChainLog.verify(p) == (True, 4)
    lines = p.read_text().splitlines()
    d = json.loads(lines[1])
    d["rec"]["i"] = 99
    lines[1] = json.dumps(d, sort_keys=True)
    p.write_text("\n".join(lines) + "\n")
    assert fb.ChainLog.verify(p) == (False, 1)


# ---------------------------------------------------------------- the MT5 link against a fake terminal
def fake_mt5(trade_mode=0, retcodes=(10009,)):
    ns = types.SimpleNamespace(ACCOUNT_TRADE_MODE_DEMO=0, TIMEFRAME_M1=1, TRADE_ACTION_DEAL=1, ORDER_TYPE_BUY=0, ORDER_TYPE_SELL=1, ORDER_FILLING_IOC=2, ORDER_FILLING_FOK=0,
                               ORDER_FILLING_RETURN=1, ORDER_TIME_GTC=0, TRADE_RETCODE_DONE=10009, TRADE_RETCODE_INVALID_FILL=10030, POSITION_TYPE_BUY=0, DEAL_ENTRY_OUT=1)
    sent = []
    ns.initialize, ns.last_error = (lambda: True), (lambda: (1, "x"))
    ns.account_info = lambda: types.SimpleNamespace(trade_mode=trade_mode)
    ns.symbol_select = lambda s, b: True
    ns.symbol_info_tick = lambda s: types.SimpleNamespace(time=time.time(), bid=28000.0, ask=28001.0)

    def order_send(req):
        sent.append(req)
        return types.SimpleNamespace(retcode=retcodes[min(len(sent) - 1, len(retcodes) - 1)], price=req["price"], comment="c")
    ns.order_send = order_send
    ns.positions_get = lambda symbol=None: [types.SimpleNamespace(ticket=7, type=0, volume=0.05, price_open=28001.0, sl=27161.0, time=1, magic=fb.MAGIC)]
    return ns, sent


def test_the_link_refuses_any_account_that_is_not_a_demo():
    for mode in (1, 2):
        try:
            fb.MT5Link(fb.Cfg(), fake_mt5(trade_mode=mode)[0]).connect()
        except fb.RealAccountRefused:
            continue
        raise AssertionError(f"trade_mode {mode} was accepted")
    assert fb.MT5Link(fb.Cfg(), fake_mt5(0)[0]).connect().offset_s == 0


def test_the_link_sends_a_market_order_with_a_disaster_stop_and_reads_the_position_back():
    m, sent = fake_mt5()
    link = fb.MT5Link(fb.Cfg(), m).connect()
    r = link.open(1, 0.05, 0.03)
    assert r["ok"] and r["ticket"] == 7 and r["price"] == 28001.0 and abs(r["sl"] - 28001 * 0.97) < 1e-6
    q = sent[0]
    assert q["volume"] == 0.05 and q["type"] == 0 and q["magic"] == fb.MAGIC and q["price"] == 28001.0 and abs(q["sl"] - 28001 * 0.97) < 1e-6
    link.open(-1, 0.05, 0.03)
    assert sent[1]["type"] == 1 and sent[1]["price"] == 28000.0 and sent[1]["sl"] > 28000                  # a sell is struck at the bid with the stop ABOVE


def test_an_unsupported_filling_mode_falls_through_but_a_real_rejection_stops():
    m, sent = fake_mt5(retcodes=(10030, 10009))
    assert fb.MT5Link(fb.Cfg(), m).connect().open(1, 0.05, 0.03)["ok"] and len(sent) == 2 and sent[0]["type_filling"] != sent[1]["type_filling"]
    m, sent = fake_mt5(retcodes=(10004,))
    r = fb.MT5Link(fb.Cfg(), m).connect().open(1, 0.05, 0.03)
    assert not r["ok"] and r["retcode"] == 10004 and len(sent) == 1


# ---------------------------------------------------------------- the bot: whole sessions through its own loop
def run_one_day(mode, d, cfg=None, start_offset_min=-10, link_kw=None):
    cfg = cfg or tmpcfg()
    open_utc, _ = fb.session_times(d)
    clock = FakeClock(open_utc + pd.Timedelta(minutes=start_offset_min))
    link = FakeLink(frame(), clock, **(link_kw or {}))
    bot = fb.NoiseBot(link, clock, mode, cfg, vxn=lambda: (22.0, 20.0))
    bot.run_day(d)
    recs = [json.loads(x)["rec"] for x in (Path(cfg.state_dir) / f"decisions_{mode}.jsonl").read_text().splitlines()]
    return bot, link, recs, cfg


def expected_wants(d):
    dd, i, A, dates, prev, out, tr = a_day()
    assert dd == d
    plan = fb.Plan(A["o"][i, 0], prev[i], fb.sigma_from_history(A["o"][i - fb.LOOK:i], A["c"][i - fb.LOOK:i]))
    return [plan.want(m, A["c"][i, m]) for m in fb.DECISIONS]


def test_a_dry_session_makes_the_backtests_decisions_and_ends_flat():
    d = a_day(flip=False)[0]
    bot, link, recs, cfg = run_one_day("dry", d)
    dec = [r for r in recs if r["kind"] == "decision"]
    assert [r["m"] for r in dec] == list(fb.DECISIONS) and [r["want"] for r in dec] == expected_wants(d)
    assert all(1.0 <= r["lag_s"] <= 1.5 for r in dec)                                      # processed one second after the minute closed
    assert bot.st["pos"] is None and recs[-1]["kind"] == "day_end" and fb.ChainLog.verify(Path(cfg.state_dir) / "decisions_dry.jsonl")[0]
    assert any(r["kind"] == "open" for r in recs)
    closes = [r for r in recs if r["kind"] == "close"]
    assert abs(bot.st["equity"] - 300 - sum(r["pnl_usd"] for r in closes)) < 1e-9 and len(bot.st["costs_bp"]) == len(closes)


def test_a_demo_session_sends_orders_through_the_link_and_leaves_nothing_open():
    d = a_day()[0]
    bot, link, recs, cfg = run_one_day("demo", d)
    assert [r["want"] for r in recs if r["kind"] == "decision"] == expected_wants(d)
    assert link.pos == [] and bot.st["pos"] is None and link.n >= 1
    assert all(r["sl"] > 0 for r in recs if r["kind"] == "open")


def test_a_late_start_skips_the_missed_decisions_instead_of_acting_on_old_news():
    d = a_day()[0]
    bot, link, recs, cfg = run_one_day("dry", d, start_offset_min=4 * 60)               # 13:30 New York
    kinds = [r["kind"] for r in recs]
    assert kinds.count("decision_missed") >= 6 and bot.st["pos"] is None and kinds[-1] == "day_end"


def test_holidays_and_half_days_are_skipped_without_touching_the_terminal():
    cfg = tmpcfg()
    clock = FakeClock(pd.Timestamp("2026-11-27 12:00", tz="UTC"))
    bot = fb.NoiseBot(FakeLink(frame(), clock), clock, "dry", cfg)
    bot.run_day(date(2026, 11, 27))
    rec = json.loads((Path(cfg.state_dir) / "decisions_dry.jsonl").read_text().splitlines()[0])["rec"]
    assert rec["kind"] == "skip_day" and "early" in rec["why"]


# ---------------------------------------------------------------- the bot: single guards
def bot_at(mode="dry", spread=1.2, equity=300.0):
    d = a_day()[0]
    open_utc, _ = fb.session_times(d)
    clock = FakeClock(open_utc + pd.Timedelta(minutes=31, seconds=1))
    link = FakeLink(frame(), clock, spread=spread)
    bot = fb.NoiseBot(link, clock, mode, tmpcfg(), vxn=lambda: None)
    bot.st["equity"] = bot.st["day_start_equity"] = equity
    return bot, link, clock


def last_kind(bot):
    return json.loads(bot.log_.path.read_text().splitlines()[-1])["rec"]


def test_a_wide_spread_a_stale_tick_and_a_too_small_account_each_block_an_entry():
    bot, link, _ = bot_at(spread=10.0)
    bot.open_pos(1, 30, 28000.0)
    assert bot.st["pos"] is None and last_kind(bot)["kind"] == "entry_skipped" and "spread" in last_kind(bot)["why"]
    bot, link, _ = bot_at()
    link.stale = True
    bot.open_pos(1, 30, 28000.0)
    assert bot.st["pos"] is None and "stale" in last_kind(bot)["why"]
    bot, link, _ = bot_at(equity=200.0)
    bot.open_pos(1, 30, 28000.0)
    assert bot.st["pos"] is None and "too low" in last_kind(bot)["why"]
    bot, link, _ = bot_at()
    bot.open_pos(1, 30, 28000.0)
    assert bot.st["pos"] and bot.st["pos"]["lots"] == 0.05


def test_a_failed_demo_order_leaves_no_position_and_is_logged():
    bot, link, _ = bot_at("demo")
    link.fail_open = True
    bot.open_pos(1, 30, 28000.0)
    assert bot.st["pos"] is None and last_kind(bot)["kind"] == "order_failed"


def test_the_daily_loss_kill_flattens_halts_and_blocks_new_entries():
    bot, link, clock = bot_at()
    bot.open_pos(1, 30, 28000.0)
    pos = bot.st["pos"]
    link.O = np.full_like(link.O, pos["entry"] - 600.0)                                    # -600 points x 0.05 lot = -$30 = -10% of $300
    bot.heartbeat()
    assert bot.halted and bot.st["pos"] is None and any(json.loads(x)["rec"]["kind"] == "day_kill" for x in bot.log_.path.read_text().splitlines())
    bot.act(1, 60, 28000.0)
    assert bot.st["pos"] is None                                                           # halted: a long signal opens nothing


def test_the_kill_does_not_fire_inside_the_limit():
    bot, link, clock = bot_at()
    bot.open_pos(1, 30, 28000.0)
    link.O = np.full_like(link.O, bot.st["pos"]["entry"] - 300.0)                          # -$15 = -5%
    bot.heartbeat()
    assert not bot.halted and bot.st["pos"] is not None


def test_the_cost_audit_charges_half_the_spread_each_way():
    bot, link, clock = bot_at(spread=2.0)
    bot.open_pos(1, 30, 28000.0)
    mid = (link.tick()["bid"] + link.tick()["ask"]) / 2
    assert abs(bot.st["pos"]["cost_in_bp"] - 1.0 / mid * 1e4) < 1e-6
    bot.close_pos("signal")
    assert abs(bot.st["costs_bp"][0] - 2 * 1.0 / mid * 1e4) < 1e-6 and bot.st["pos"] is None


def test_restart_reconciliation_closes_orphans_and_books_a_vanished_position():
    bot, link, clock = bot_at("demo")
    link.pos.append(dict(ticket=99, side=1, lots=0.05, entry=28000.0, sl=27000.0, t=0))
    bot.reconcile(clock.now())
    assert link.pos == [] and any(json.loads(x)["rec"]["kind"] == "orphan_closed" for x in bot.log_.path.read_text().splitlines())
    bot.st["pos"] = dict(side=1, lots=0.05, entry=28000.0, ticket=123, sl=27160.0, mid_in=28000.0, cost_in_bp=0.3, t="x", m=30)
    bot.reconcile(clock.now())
    assert bot.st["pos"] is None and bot.st["trades"] == 1 and abs(bot.st["equity"] - (300 + (27160 - 28000) * 0.05)) < 1e-9


def a_day_held_to_the_close():
    A, dates, prev = session_df(frame(), "NASDAQ")
    for i in range(len(dates) - 1, fb.LOOK, -1):
        if not np.isfinite(prev[i]):
            continue
        plan = fb.Plan(A["o"][i, 0], prev[i], fb.sigma_from_history(A["o"][i - fb.LOOK:i], A["c"][i - fb.LOOK:i]))
        if plan.want(fb.DECISIONS[-1], A["c"][i, fb.DECISIONS[-1]]) != 0:
            return dates[i].date()
    raise AssertionError("no day ends with an open position")


def test_a_position_held_into_the_afternoon_is_flattened_at_1558_new_york_before_the_close():
    d = a_day_held_to_the_close()
    bot, link, recs, cfg = run_one_day("dry", d)
    closes = [r for r in recs if r["kind"] == "close" and r["why"] == "close"]
    open_utc, close_utc = fb.session_times(d)
    assert len(closes) == 1 and pd.Timestamp(closes[0]["ts"]) == close_utc - pd.Timedelta(minutes=2)
    assert pd.Timestamp(recs[-1]["ts"]) <= close_utc and recs[-1]["kind"] == "day_end" and bot.st["pos"] is None


def test_a_position_that_vanishes_from_the_terminal_is_booked_at_its_stop():
    bot, link, clock = bot_at("demo")
    bot.open_pos(1, 30, 28000.0)
    sl, entry = bot.st["pos"]["sl"], bot.st["pos"]["entry"]
    link.pos.clear()                                                                       # the disaster stop was hit (or someone closed it by hand)
    bot.heartbeat()
    assert bot.st["pos"] is None and bot.st["trades"] == 1 and abs(bot.st["equity"] - (300 + (sl - entry) * 0.05)) < 1e-9
    assert any(json.loads(x)["rec"]["kind"] == "broker_closed" for x in bot.log_.path.read_text().splitlines())


def test_the_cli_refuses_live_mode():
    r = subprocess.run([sys.executable, str(ROOT / "forex_bot.py"), "--mode", "live"], capture_output=True, text=True, timeout=60)
    assert r.returncode != 0 and "REFUSED" in (r.stdout + r.stderr) and fb.ALLOW_REAL is False


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        t0 = time.time()
        fn()
        print(f"ok {fn.__name__} ({time.time() - t0:.1f}s)")
    print(len(tests), "tests passed")
