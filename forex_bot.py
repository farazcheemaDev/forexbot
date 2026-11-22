"""THE FOREX BOT, release 1: NASDAQ "noise area" momentum on Exness USTECm, intraday, DEMO ONLY (2026-11-03)

WHAT IT IS. The one forex-side candidate this project's search left standing (backtest/fx_intraday_pub.py, noise_attack.py, noise_book.py; doc 02 2026-10-22): Zarattini, Aziz & Barbon (2024) "noise area" momentum on the
NASDAQ cash session, run on Exness's index CFD. Backtest 2010-2026 at Exness costs: +2.25 bp a day net, t +2.83, Sharpe 0.74 at 1x, 13 of 17 years up; tune t +1.99 (a hair under the 2.0 bar), t 1.5 at double costs, and all of the
profit sits on high-VXN days (found after looking). At $300 the 0.05-lot minimum forces ~4.8x: BACKTEST +21.6% a year, fall 56%, worst day -13.7%. It is MOSTLY NASDAQ BETA with a thin edge: this release is a PLUMBING-AND-COST
PROOF, not an income plan. It holds nothing overnight, so no swap, no swap-free account needed.

THE RULE (ported verbatim from fx_intraday_pub.noise(); NOT re-tuned)
  Session 09:30-16:00 New York. sigma(m) = the mean over the previous 14 sessions of |close(minute m) / that day's open - 1|.
  Upper bound = max(today's open, previous session's close) x (1 + sigma(m)); lower = min(...) x (1 - sigma(m)).
  At minute m = 30, 60, ..., 360 (10:01, 10:31, ... 15:31 New York, once the minute bar has closed): close above the upper bound -> long; below the lower -> short; between -> flat.
  A change of side is executed at once at the market. Flat by 15:58 New York (the backtest exits at the 16:00 print; two minutes earlier is a stated deviation).
THE SHELL (the council's design, 2026-11-03: five advisors, doc 02): New York clock (not server time), DEMO account assertion on every start, a human-only ALLOW_REAL flag (release 1 has NO real-money path), one position at a
  time, a server-side disaster stop (3% of price) on every order, a spread filter, a stale-tick filter, a holiday / half-day skip, a daily loss kill, a virtual $300 equity (the demo balance is irrelevant), an equity floor where
  the minimum lot would exceed 6x, restart reconciliation by magic number, an append-only HASH-CHAINED log, and a COST AUDIT (intended price vs fill vs the backtest's 1.27 bp round trip).
DELIBERATELY NOT IN RELEASE 1: news filter, any other instrument, the VXN gate (logged as a shadow covariate only - it was found after looking), the pre-FOMC / gap / RSI(2) books, any copy of the NASDAQ trader's habits.

REGISTERED BEFORE ANY RUN (2026-11-03)
  F1  Parity: over >= 100 historical days the bot's incremental decisions reproduce fx_intraday_pub.noise() day by day (returns equal to 1e-9, trade counts equal).
  F2  Plumbing: >= 95% of decision minutes are processed within 5 s of schedule; no position is ever held past 16:00 New York; every unexplained order failure is a defect.
  F3  Costs (the kill line): the realised round trip (entry + exit versus the mid at the decision) averages <= 1.5 x 1.27 bp = 1.9 bp over >= 20 trades. If it is higher the backtest's cost model was wrong.
  F4  What the demo can NOT show: at Sharpe 0.74 a t of 2 takes ~7 years; 100 trading days gives t ~ 0.5. The demo record is judged by doc 22's rule, never by a good-looking month. A rolling year net-negative after costs = retire it.
  Honest range at $300: 0% to +20% a year, falls of 40-55%, a -20% month plausible; ~1 year in 4 loses even if the backtest Sharpe is real.

BUILT 2026-11-03 - STATE AT HAND-OVER (nothing has traded; nothing is running)
  F1 parity: `--parity 150` = 150 of 150 days identical to fx_intraday_pub.noise(), max difference 0.0. tests/test_forex_bot.py: 23 tests (signal, calendar / New York DST, sizing, hash chain, the MT5 link against a fake
  terminal, whole simulated sessions through the bot's own loop in dry and demo modes, late start, holiday skip, spread / stale-tick / small-account guards, the daily kill, reconciliation, a position vanishing, the
  CLI refusing live mode). Mutation check: 25 planted bugs, 24 caught; the one survivor (the hash chain's explicit 'previous' comparison) is redundant - the record's own hash already covers it.
  Read-only smoke test against the real MT5 demo terminal (09:41 New York, 2026-11-03): demo asserted, tick 0.5 s old, spread 1.12 points, 31 complete history sessions, sigma ready, previous close 28,022.88.
  NOT yet done: a first dry day end to end on the live terminal; a first demo round trip (real slippage); the 10-day dry-run the council asked for before demo orders. Active window: 09:30-16:00 New York =
  19:30-02:00 Pakistan time (18:30-01:00 in the US summer); the PC and the MT5 terminal must stay on.

    python forex_bot.py --mode dry            run the days forever, NO orders: logs what it would do, fills at the live bid / ask
    python forex_bot.py --mode demo           same, with real orders on the DEMO account (refuses any other account)
    python forex_bot.py --status | --report | --verify     state / cost audit / hash-chain check      python forex_bot.py --parity [DAYS]
    tests: python tests/test_forex_bot.py
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import statistics
import sys
import time
import urllib.request
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from backtest.fx_intraday_pub import session_df  # noqa: E402  (the backtest's own session builder: one code path)

ALLOW_REAL = False                     # a HUMAN edits this. Release 1 has no real-money path whatever its value.
SYMBOL, MAGIC = "USTECm", 5150301
NY = "America/New_York"
SESSION_MIN = 390
DECISIONS = tuple(range(30, SESSION_MIN - 1, 30))          # 30, 60, ..., 360  (the backtest: range(30, L - delay, 30), delay 1)
LOOK = 14

# NYSE closed days and 13:00 early closes. VERIFY EACH YEAR against the exchange's calendar; the bot refuses dates beyond 2027.
NYSE_CLOSED = {"2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03", "2026-05-25", "2026-06-19", "2026-07-03", "2026-09-07", "2026-11-26", "2026-12-25",
               "2027-01-01", "2027-01-18", "2027-02-15", "2027-03-26", "2027-05-31", "2027-06-18", "2027-07-05", "2027-09-06", "2027-11-25", "2027-12-24"}
NYSE_EARLY = {"2026-11-27", "2026-12-24", "2027-11-26"}
CALENDAR_LAST = date(2027, 12, 31)


@dataclass
class Cfg:
    symbol: str = SYMBOL
    magic: int = MAGIC
    equity0: float = 300.0             # the VIRTUAL account the record is kept for (the demo balance is irrelevant)
    target_lev: float = 5.0            # the backtest's constant leverage; at $300 the 0.05 minimum lot binds (4.7-4.8x)
    max_lev: float = 6.0               # refuse to trade when even the minimum lot would exceed this (equity ~ $238)
    lot_min: float = 0.05
    lot_step: float = 0.01
    contract: float = 1.0
    disaster_sl: float = 0.03          # server-side stop, a fraction of the entry price. A GUESS; not part of the strategy; every trigger is logged
    day_kill: float = 0.08             # flat and halted for the day at -8% of the day's starting equity. A GUESS (the backtest's worst day at 5x was -13.7%)
    max_spread_pts: float = 6.0        # index points; ~5x the normal 1.1. A GUESS
    max_tick_age_s: float = 5.0
    deviation: int = 20
    flat_before_close_min: int = 2
    late_tolerance_s: float = 120.0    # a decision more than this late is skipped (logged), not made on old information
    cost_assumed_bp: float = 1.27      # the backtest's round trip: 0.77 spread + 0.5 slippage
    cost_kill_mult: float = 1.5
    state_dir: str = "logs/forex_bot"


# ---------------------------------------------------------------- calendar and clock
def is_trading_day(d: date):
    if d > CALENDAR_LAST:
        return False, "calendar ends 2027-12-31: extend NYSE_CLOSED / NYSE_EARLY"
    if d.weekday() >= 5:
        return False, "weekend"
    s = d.isoformat()
    if s in NYSE_CLOSED:
        return False, "NYSE holiday"
    if s in NYSE_EARLY:
        return False, "NYSE early close (the backtest drops days under 90% coverage)"
    return True, ""


def session_times(d: date):
    """(open, close) of the New York cash session as UTC timestamps."""
    return (pd.Timestamp(f"{d} 09:30", tz=NY).tz_convert("UTC"), pd.Timestamp(f"{d} 16:00", tz=NY).tz_convert("UTC"))


def ms(ts: pd.Timestamp) -> int:
    return int(ts.value // 10**6)


class RealClock:
    def now(self):
        return pd.Timestamp.now(tz="UTC")

    def sleep(self, s: float):
        time.sleep(max(0.0, s))


# ---------------------------------------------------------------- the signal (pure functions)
def sigma_from_history(O, C, look: int = LOOK):
    """sigma[m] from the previous sessions (oldest first, sessions x 390): mean |C/open - 1|. None with fewer than `look` sessions. The backtest's rolling(14).mean().shift(1)."""
    if len(C) < look:
        return None
    return np.abs(np.asarray(C)[-look:] / np.asarray(O)[-look:, :1] - 1.0).mean(axis=0)


class Plan:
    """One day's bounds: needs today's open, the previous session's close and sigma."""

    def __init__(self, op: float, prev: float, sig):
        self.ub_base, self.lb_base, self.sig = max(op, prev), min(op, prev), sig

    def bounds(self, m: int):
        return self.ub_base * (1 + self.sig[m]), self.lb_base * (1 - self.sig[m])

    def want(self, m: int, c: float) -> int:
        ub, lb = self.bounds(m)
        return 1 if c > ub else (-1 if c < lb else 0)


def replay_day(Ad, i: int, prev_i: float):
    """The backtest's day, run through Plan: (return, trades). Used by --parity and the tests. Entries at the next minute's open, exit at the last close."""
    sig = sigma_from_history(Ad["o"][i - LOOK:i], Ad["c"][i - LOOK:i])
    if sig is None or not np.isfinite(prev_i):
        return None
    plan = Plan(Ad["o"][i, 0], prev_i, sig)
    pos, entry, r, nt = 0, float("nan"), 0.0, 0
    for m in DECISIONS:
        want = plan.want(m, Ad["c"][i, m])
        if want != pos:
            px = Ad["o"][i, m + 1]
            if pos != 0:
                r += pos * (px / entry - 1)
            pos, entry = want, px
            nt += abs(want) > 0
    if pos != 0:
        r += pos * (Ad["c"][i, -1] / entry - 1)
    return r, nt


def parity(frame: pd.DataFrame, days: int = 150):
    """Compare replay_day with fx_intraday_pub.noise() on the last `days` sessions of a minute-bar frame. Returns (compared, matched, max |difference|)."""
    from backtest.fx_intraday_pub import noise
    A, dates, prev = session_df(frame, "NASDAQ")
    out, _, tr = noise(A, prev)
    n, ok, worst = 0, 0, 0.0
    for i in range(max(LOOK, len(dates) - days), len(dates)):
        got = replay_day(A, i, prev[i])
        if got is None:
            continue
        n += 1
        d = abs(got[0] - out[i])
        worst = max(worst, d)
        ok += int(d < 1e-9 and got[1] == tr[i])
    return n, ok, worst


def lots_for(equity: float, price: float, cfg: Cfg) -> float:
    """Constant-leverage lots of the virtual equity, floored to the step, never below the minimum lot; 0.0 = refuse (the minimum lot would exceed max_lev)."""
    if equity <= 0 or price <= 0:
        return 0.0
    lots = max(cfg.lot_min, math.floor(cfg.target_lev * equity / (price * cfg.contract) / cfg.lot_step + 1e-9) * cfg.lot_step)
    lots = round(lots, 2)
    return 0.0 if lots * price * cfg.contract / equity > cfg.max_lev + 1e-9 else lots


def pnl_usd(side: int, entry: float, exit_: float, lots: float, contract: float) -> float:
    return side * (exit_ - entry) * lots * contract


def fetch_vxn(timeout: float = 6.0):
    """Shadow covariate only (never gates a trade): (last close, 1-year median) of ^VXN from Yahoo's public chart API, or None."""
    try:
        req = urllib.request.Request("https://query1.finance.yahoo.com/v8/finance/chart/%5EVXN?range=1y&interval=1d", headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            q = json.loads(r.read())["chart"]["result"][0]["indicators"]["quote"][0]["close"]
        q = [x for x in q if x is not None]
        return (q[-1], statistics.median(q)) if len(q) > 20 else None
    except Exception:
        return None


# ---------------------------------------------------------------- the append-only, hash-chained log and atomic state
class ChainLog:
    GENESIS = "0" * 64

    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.prev = self.GENESIS
        if self.path.exists() and self.path.stat().st_size:
            self.prev = json.loads(self.path.read_text(encoding="utf-8").strip().splitlines()[-1])["h"]

    def append(self, rec: dict):
        rec = dict(rec, prev=self.prev)
        body = json.dumps(rec, sort_keys=True, default=str)
        h = hashlib.sha256((self.prev + body).encode()).hexdigest()
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"rec": rec, "h": h}, sort_keys=True, default=str) + "\n")
        self.prev = h

    @classmethod
    def verify(cls, path):
        """(ok, lines): every record points at the hash of the one before and hashes to its own h."""
        prev, n = cls.GENESIS, 0
        p = Path(path)
        if not p.exists():
            return True, 0
        for line in p.read_text(encoding="utf-8").splitlines():
            d = json.loads(line)
            body = json.dumps(d["rec"], sort_keys=True, default=str)
            if d["rec"].get("prev") != prev or hashlib.sha256((prev + body).encode()).hexdigest() != d["h"]:
                return False, n
            prev, n = d["h"], n + 1
        return True, n


def save_state(path, st: dict):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(st, indent=1, default=str), encoding="utf-8")
    os.replace(tmp, p)


# ---------------------------------------------------------------- the MT5 link (the only code that talks to the terminal)
class LinkError(RuntimeError):
    pass


class RealAccountRefused(LinkError):
    pass


class MT5Link:
    """Attaches to the logged-in terminal (no credentials anywhere), asserts a DEMO account, and offers bars / tick / positions / market orders."""

    def __init__(self, cfg: Cfg, mt5=None):
        self.cfg = cfg
        self.mt5 = mt5
        self.offset_s = 0

    def connect(self):
        if self.mt5 is None:
            import MetaTrader5 as mt5
            self.mt5 = mt5
        m = self.mt5
        if not m.initialize():
            raise LinkError(f"initialize failed: {m.last_error()}")
        a = m.account_info()
        if a is None:
            raise LinkError("no account info (is the terminal logged in?)")
        if a.trade_mode != m.ACCOUNT_TRADE_MODE_DEMO:
            raise RealAccountRefused(f"account trade_mode {a.trade_mode} is not DEMO - release 1 refuses every non-demo account (ALLOW_REAL={ALLOW_REAL} changes nothing here)")
        if not m.symbol_select(self.cfg.symbol, True):
            raise LinkError(f"cannot select {self.cfg.symbol}")
        tk = m.symbol_info_tick(self.cfg.symbol)
        if tk is not None and abs(tk.time - time.time()) < 300:        # a fresh tick: derive the server clock's offset to UTC (Exness: 0)
            self.offset_s = int(round((tk.time - time.time()) / 3600.0)) * 3600
        return self

    def tick(self):
        tk = self.mt5.symbol_info_tick(self.cfg.symbol)
        if tk is None:
            return None
        return dict(t=tk.time - self.offset_s, bid=float(tk.bid), ask=float(tk.ask))

    def bars(self, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
        s = (start + pd.Timedelta(seconds=self.offset_s)).to_pydatetime()
        e = (end + pd.Timedelta(seconds=self.offset_s)).to_pydatetime()
        r = self.mt5.copy_rates_range(self.cfg.symbol, self.mt5.TIMEFRAME_M1, s, e)
        if r is None or len(r) == 0:
            return pd.DataFrame(columns=["t", "o", "h", "l", "c"])
        d = pd.DataFrame(r)
        return pd.DataFrame({"t": (d["time"].astype("int64") - self.offset_s) * 1000, "o": d["open"], "h": d["high"], "l": d["low"], "c": d["close"]})

    def positions(self):
        ps = self.mt5.positions_get(symbol=self.cfg.symbol) or []
        return [dict(ticket=p.ticket, side=1 if p.type == self.mt5.POSITION_TYPE_BUY else -1, lots=p.volume, entry=p.price_open, sl=p.sl, t=p.time)
                for p in ps if p.magic == self.cfg.magic]

    def _send(self, side, lots, price, sl, position=None, comment="noise"):
        m = self.mt5
        last = None
        for filling in (m.ORDER_FILLING_IOC, m.ORDER_FILLING_FOK, m.ORDER_FILLING_RETURN):
            req = dict(action=m.TRADE_ACTION_DEAL, symbol=self.cfg.symbol, volume=float(lots), type=m.ORDER_TYPE_BUY if side > 0 else m.ORDER_TYPE_SELL,
                       price=float(price), deviation=self.cfg.deviation, magic=self.cfg.magic, comment=comment, type_time=m.ORDER_TIME_GTC, type_filling=filling)
            if sl:
                req["sl"] = float(sl)
            if position:
                req["position"] = int(position)
            last = m.order_send(req)
            if last is not None and last.retcode == m.TRADE_RETCODE_DONE:
                return dict(ok=True, price=float(last.price), retcode=last.retcode)
            if last is not None and last.retcode != getattr(m, "TRADE_RETCODE_INVALID_FILL", 10030):
                break
        return dict(ok=False, price=None, retcode=getattr(last, "retcode", None), comment=getattr(last, "comment", "no result"))

    def open(self, side, lots, sl_pct):
        tk = self.tick()
        price = tk["ask"] if side > 0 else tk["bid"]
        sl = price * (1 - sl_pct) if side > 0 else price * (1 + sl_pct)
        res = self._send(side, lots, price, sl)
        if not res["ok"]:
            return res
        mine = self.positions()
        if not mine:
            return dict(ok=False, price=res["price"], retcode=res["retcode"], comment="order done but no position found")
        p = max(mine, key=lambda x: x["t"])
        return dict(ok=True, price=res["price"], ticket=p["ticket"], sl=sl, retcode=res["retcode"])

    def close(self, pos):
        tk = self.tick()
        price = tk["bid"] if pos["side"] > 0 else tk["ask"]
        return self._send(-pos["side"], pos["lots"], price, None, position=pos["ticket"], comment="noise-close")

    def closed_exit(self, ticket):
        deals = self.mt5.history_deals_get(position=ticket) or []
        outs = [d for d in deals if d.entry == self.mt5.DEAL_ENTRY_OUT]
        return float(outs[-1].price) if outs else None


# ---------------------------------------------------------------- the bot
class NoiseBot:
    def __init__(self, link, clock, mode: str, cfg: Cfg = None, vxn=fetch_vxn):
        assert mode in ("dry", "demo")
        self.link, self.clock, self.mode, self.cfg, self.vxn = link, clock, mode, cfg or Cfg(), vxn
        d = ROOT / self.cfg.state_dir
        self.state_path = d / f"state_{mode}.json"
        self.log_ = ChainLog(d / f"decisions_{mode}.jsonl")
        self.st = self._load()
        self.plan = None
        self.halted = False

    # -- state / log
    def _load(self):
        if self.state_path.exists():
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        return dict(equity=self.cfg.equity0, day=None, day_start_equity=self.cfg.equity0, pos=None, trades=0, costs_bp=[])

    def save(self):
        save_state(self.state_path, self.st)

    def log(self, kind, **kw):
        self.log_.append(dict(ts=str(self.clock.now()), kind=kind, mode=self.mode, **kw))

    # -- waiting with a heartbeat
    def wait_until(self, target: pd.Timestamp):
        while self.clock.now() < target:
            self.heartbeat()
            self.clock.sleep(min(10.0, max(0.2, (target - self.clock.now()).total_seconds())))

    def heartbeat(self):
        pos = self.st["pos"]
        if not pos:
            return
        tk = self.link.tick()
        if self.mode == "demo" and not any(p["ticket"] == pos.get("ticket") for p in self.link.positions()):
            exit_px = self.link.closed_exit(pos.get("ticket")) or pos["sl"]
            self.log("broker_closed", exit=exit_px, note="position vanished from the terminal (disaster stop or manual close)")
            self._book(exit_px, "broker_closed", tk, intended_mid=None)
            return
        if tk:
            px = tk["bid"] if pos["side"] > 0 else tk["ask"]
            open_pnl = pnl_usd(pos["side"], pos["entry"], px, pos["lots"], self.cfg.contract)
            if self.st["equity"] + open_pnl - self.st["day_start_equity"] <= -self.cfg.day_kill * self.st["day_start_equity"] and not self.halted:
                self.halted = True
                self.log("day_kill", open_pnl=open_pnl, equity=self.st["equity"])
                self.close_pos("day_kill")

    # -- orders
    def open_pos(self, side: int, m: int, c: float):
        tk = self.link.tick()
        if tk is None or self.clock.now().timestamp() - tk["t"] > self.cfg.max_tick_age_s:
            return self.log("entry_skipped", m=m, side=side, why="stale or missing tick")
        spread = tk["ask"] - tk["bid"]
        if spread > self.cfg.max_spread_pts:
            return self.log("entry_skipped", m=m, side=side, why=f"spread {spread:.2f} points over the cap {self.cfg.max_spread_pts}")
        lots = lots_for(self.st["equity"], tk["ask"], self.cfg)
        if lots <= 0:
            return self.log("entry_skipped", m=m, side=side, why=f"equity {self.st['equity']:.2f} too low for the minimum lot (> {self.cfg.max_lev}x)")
        mid = (tk["bid"] + tk["ask"]) / 2
        quote = tk["ask"] if side > 0 else tk["bid"]
        if self.mode == "demo":
            res = self.link.open(side, lots, self.cfg.disaster_sl)
            if not res["ok"]:
                return self.log("order_failed", m=m, side=side, lots=lots, result=res)
            fill, ticket, sl = res["price"], res["ticket"], res["sl"]
        else:
            fill, ticket, sl = quote, None, quote * (1 - self.cfg.disaster_sl * side)
        cost_bp = side * (fill - mid) / mid * 1e4
        self.st["pos"] = dict(side=side, lots=lots, entry=fill, ticket=ticket, sl=sl, mid_in=mid, cost_in_bp=cost_bp, t=str(self.clock.now()), m=m)
        self.save()
        self.log("open", m=m, side=side, lots=lots, close_m=c, mid=mid, quote=quote, fill=fill, spread_pts=spread, slippage_bp=side * (fill - quote) / mid * 1e4, entry_cost_bp=cost_bp, sl=sl)

    def close_pos(self, why: str):
        pos = self.st["pos"]
        if not pos:
            return
        tk = self.link.tick()
        if self.mode == "demo":
            res = self.link.close(pos)
            if not res["ok"]:
                return self.log("close_failed", why=why, result=res)
            exit_px = res["price"]
        else:
            exit_px = tk["bid"] if pos["side"] > 0 else tk["ask"]
        self._book(exit_px, why, tk, intended_mid=(tk["bid"] + tk["ask"]) / 2 if tk else None)

    def _book(self, exit_px, why, tk, intended_mid):
        pos = self.st["pos"]
        pnl = pnl_usd(pos["side"], pos["entry"], exit_px, pos["lots"], self.cfg.contract)
        cost_out = pos["side"] * (intended_mid - exit_px) / intended_mid * 1e4 if intended_mid else float("nan")
        rt = pos["cost_in_bp"] + cost_out
        self.st["equity"] += pnl
        self.st["trades"] += 1
        if math.isfinite(rt):
            self.st["costs_bp"].append(rt)
        self.log("close", why=why, side=pos["side"], lots=pos["lots"], entry=pos["entry"], exit=exit_px, pnl_usd=pnl, equity=self.st["equity"], round_trip_cost_bp=rt)
        self.st["pos"] = None
        self.save()

    def act(self, want: int, m: int, c: float):
        cur = self.st["pos"]["side"] if self.st["pos"] else 0
        if self.halted:
            want = 0
        if want == cur:
            return
        if cur:
            self.close_pos("signal")
        if want and not self.st["pos"]:
            self.open_pos(want, m, c)

    # -- start-up reconciliation
    def reconcile(self, now: pd.Timestamp):
        if self.mode != "demo":
            return
        mine = self.link.positions()
        st = self.st["pos"]
        for p in mine:
            if st and st.get("ticket") == p["ticket"]:
                continue
            self.log("orphan_position", position=p, action="closing")
            res = self.link.close(p)
            self.log("orphan_closed" if res["ok"] else "orphan_close_failed", result=res)
        if st and not any(p["ticket"] == st.get("ticket") for p in mine):
            self.log("state_position_missing", position=st, action="dropping from state (booked at the stop price)")
            self._book(st["sl"], "reconcile_lost", None, intended_mid=None)

    # -- one session
    def run_day(self, d: date):
        ok, why = is_trading_day(d)
        if not ok:
            return self.log("skip_day", date=str(d), why=why)
        open_utc, close_utc = session_times(d)
        flat_utc = close_utc - pd.Timedelta(minutes=self.cfg.flat_before_close_min)
        self.wait_until(open_utc - pd.Timedelta(minutes=5))
        self.reconcile(self.clock.now())
        self.halted = False
        self.st["day"], self.st["day_start_equity"] = str(d), self.st["equity"]
        self.save()
        hist = self.link.bars(open_utc - pd.Timedelta(days=45), open_utc - pd.Timedelta(minutes=1))
        A, dates, _ = session_df(hist, "NASDAQ") if len(hist) else (None, [], None)
        sig = sigma_from_history(A["o"], A["c"]) if A is not None and len(dates) else None
        vx = self.vxn()
        self.log("day_start", date=str(d), equity=self.st["equity"], history_sessions=len(dates), have_sigma=sig is not None,
                 prev_close=float(A["c"][-1, -1]) if sig is not None else None, vxn_shadow=vx, vxn_above_median=(vx[0] > vx[1]) if vx else None)
        if sig is None:
            self.log("skip_day", date=str(d), why=f"fewer than {LOOK} complete history sessions")
            return
        prev_close = float(A["c"][-1, -1])
        self.plan = None
        for m in DECISIONS:
            t_dec = open_utc + pd.Timedelta(minutes=m + 1)
            if self.clock.now() > t_dec + pd.Timedelta(seconds=self.cfg.late_tolerance_s):
                self.log("decision_missed", m=m, why="late start or overrun")
                continue
            self.wait_until(t_dec + pd.Timedelta(seconds=1))
            bars = self.link.bars(open_utc, t_dec + pd.Timedelta(seconds=1))
            row0 = bars[bars.t == ms(open_utc)]
            rowm = bars[bars.t == ms(open_utc) + m * 60000]
            if rowm.empty or row0.empty:
                self.log("no_bar", m=m, bars=len(bars))
                continue
            if self.plan is None:
                self.plan = Plan(float(row0.o.iloc[0]), prev_close, sig)
            c = float(rowm.c.iloc[0])
            ub, lb = self.plan.bounds(m)
            want = self.plan.want(m, c)
            cur = self.st["pos"]["side"] if self.st["pos"] else 0
            self.log("decision", m=m, close=c, ub=ub, lb=lb, want=want, have=cur, lag_s=(self.clock.now() - t_dec).total_seconds())
            self.act(want, m, c)
        self.wait_until(flat_utc)
        for _ in range(60):                                  # flat by 15:58; keep trying until 16:45 New York
            self.close_pos("close")
            if not self.st["pos"]:
                break
            self.log("not_flat_retry")
            self.clock.sleep(5.0)
        if self.st["pos"]:
            self.log("CRITICAL_NOT_FLAT", position=self.st["pos"])
        self.log("day_end", date=str(d), equity=self.st["equity"], day_pnl=self.st["equity"] - self.st["day_start_equity"], trades=self.st["trades"])

    def run_forever(self):
        while True:
            now = self.clock.now()
            d = now.tz_convert(NY).date()
            while True:
                if d > CALENDAR_LAST:
                    raise SystemExit("calendar ends 2027-12-31: extend NYSE_CLOSED / NYSE_EARLY before running further")
                ok, _ = is_trading_day(d)
                if ok and now < session_times(d)[1] - pd.Timedelta(minutes=self.cfg.flat_before_close_min):
                    break
                d += timedelta(days=1)
            self.run_day(d)
            self.clock.sleep(60.0)


# ---------------------------------------------------------------- reports
def report(cfg: Cfg = None, mode: str = "dry") -> str:
    cfg = cfg or Cfg()
    d = ROOT / cfg.state_dir
    sp = d / f"state_{mode}.json"
    if not sp.exists():
        return f"no state for mode {mode} yet"
    st = json.loads(sp.read_text(encoding="utf-8"))
    ok, n = ChainLog.verify(d / f"decisions_{mode}.jsonl")
    c = st.get("costs_bp", [])
    lines = [f"mode {mode}: virtual equity ${st['equity']:.2f} (start ${cfg.equity0:.0f}), trades {st['trades']}, position {st['pos'] and (st['pos']['side'], st['pos']['lots'])}",
             f"log hash chain: {'OK' if ok else 'BROKEN'} ({n} records)"]
    if c:
        mean = sum(c) / len(c)
        lines.append(f"cost audit: {len(c)} round trips, mean {mean:.2f} bp (backtest {cfg.cost_assumed_bp} bp, kill line {cfg.cost_assumed_bp * cfg.cost_kill_mult:.2f} bp) -> "
                     + ("KILL LINE BREACHED" if len(c) >= 20 and mean > cfg.cost_assumed_bp * cfg.cost_kill_mult else "within the line" if len(c) >= 20 else "too few trades to judge (need 20)"))
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--mode", choices=["dry", "demo", "live"])
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--parity", nargs="?", const=150, type=int)
    a = ap.parse_args()
    cfg = Cfg()
    if a.status or a.report:
        for m in ("dry", "demo"):
            print(report(cfg, m))
        return
    if a.verify:
        for m in ("dry", "demo"):
            print(m, ChainLog.verify(ROOT / cfg.state_dir / f"decisions_{m}.jsonl"))
        return
    if a.parity is not None:
        from backtest import mt5_1m
        n, ok, worst = parity(mt5_1m.load(cfg.symbol), a.parity)
        print(f"parity vs fx_intraday_pub.noise(): {ok} of {n} days identical, max |difference| {worst:.2e}")
        return
    if a.mode == "live":
        raise SystemExit(f"REFUSED: release 1 has no real-money path (ALLOW_REAL={ALLOW_REAL}). A human must write that path and flip the flag.")
    if not a.mode:
        ap.print_help()
        return
    link = MT5Link(cfg).connect()
    print(f"connected to a DEMO account; mode {a.mode}; virtual equity ${NoiseBot(link, RealClock(), a.mode, cfg).st['equity']:.2f}")
    NoiseBot(link, RealClock(), a.mode, cfg).run_forever()


if __name__ == "__main__":
    main()
