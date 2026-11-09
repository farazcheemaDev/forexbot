"""THE DASHBOARD'S FEED: each paper account's live picture, pushed to Upstash every minute (2026-10-17, docs/24)

Runs on the VM (systemd timer, deploy/forexbot-dash.*). READ-ONLY towards the bots: it reads their state and trade
files, asks Binance for public prices (one request) and systemd for service health, and writes compressed JSON to
Upstash Redis keys the Vercel page reads (dashboard/). Its only own files are the equity curves in logs/dashboard/.
Standard library only - the VM has ~200 MB to spare.

ACCOUNTS    main   combo_bot --final, dry, $300 from 2026-10-09 (logs/combo_bot_dry_final)
            fresh  the same code, a separate $300 from 2026-10-17 (logs/combo_bot_dry_final_fresh, --account fresh)
PER ACCOUNT equity LIVE = the bot's booked equity + every open position's P&L since the bot last booked it:
              trend / daily / capit2 / news / NASDAQ book at the close  -> open P&L since ENTRY
              market-neutral / carry / bear sleeve are marked daily     -> open P&L since the last daily MARK
            open positions (Binance style: side, size, entry, mark, P&L), closed trades, P&L by book (booked + open),
            the netted account's long / short exposure, daily P&L, the equity curve (5-min for 24h, hourly since start),
            the news the bot read
MOOD / CROWD (2026-10-23) meta.mood = news/crowd_paper.py's hourly market-mood snapshot; meta.crowd = the crowd-squeeze
            paper book (logs/crowd_paper/), live-marked here, placed in crowd_bands.json from week 4
ANALYST (2026-10-27) meta.analyst = the Analyst desk (analyst.py, logs/analyst/): the levels it draws on 7 symbols with their
            distance from the LIVE price, its open predictions with live marks, its hit rate against the random baseline,
            and a separate $300 paper book (booked P&L + open calls at live prices). A paper book outside both accounts.
KEYS        forexbot:meta (accounts, health, the other paper books), forexbot:acct:<id> - values "gz:" + base64(gzip(json))
CURVES      logs/dashboard/eq_<id>_m.csv (one point a minute, last 2 days) and eq_<id>_h.csv (last point of each hour)
SECRETS     UPSTASH_REDIS_REST_URL / UPSTASH_REDIS_REST_TOKEN from the environment only (the service's EnvironmentFile,
            root, 600) - never in the repo, a log or an argument.

    python dashboard_push.py --print     build and print (no push, no curve point written)
    python dashboard_push.py             build and push
"""
from __future__ import annotations

import base64
import csv
import gzip
import json
import math
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LOGS = ROOT / "logs"
CURVES = LOGS / "dashboard"
ACCOUNTS = [("main", LOGS / "combo_bot_dry_final"), ("fresh", LOGS / "combo_bot_dry_final_fresh")]
SERVICES = ["combo-bot-final", "combo-bot-fresh", "combo-paper", "blend-paper", "wick-paper", "pair-paper",
            "crowd-paper.timer", "analyst-paper.timer", "rsi80-paper.timer"]
# combo-bot-demo was stopped 2026-10-17 at the user's word: its order-path test was done (191 orders over 16.9 days, all
# filled and priced, 0 failures; logs/combo_bot_demo/final_report_20261017.txt on the VM)
START_EQUITY = 300.0
GROSS_CAP = 14.5
META_KEY, ACCT_KEY = "forexbot:meta", "forexbot:acct:"
CLOSED_KEEP, NEWS_KEEP = 120, 30
BANDS = ROOT / "dashboard_bands.json"           # backtest/scorecard_bands.py: each book's normal N-day range
SCORE_MIN_DAYS = 7                              # the backtest books MN / carry weekly: shorter stretches do not compare
SCORE_BOOKS = ("trend", "mn", "carry", "sleeve", "daily", "capit2", "bids", "news", "ndx")
MOOD = LOGS / "mood" / "mood.json"              # news/crowd_paper.py writes it hourly (news/mood_now.snapshot)
CROWD = LOGS / "crowd_paper"                    # the crowd-squeeze paper book's state / marks / weeks
CROWD_BANDS = ROOT / "crowd_bands.json"         # positioning_hist.py --band: that book's normal N-week range
CROWD_MIN_WEEKS = 4
ANALYST = LOGS / "analyst"                      # analyst.py's state / calls / levels / marks (hourly, analyst-paper.timer)
ANALYST_KEEP = 40
ANALYST_REPLAY = ROOT / "analyst_replay.json"   # backtest/analyst_replay.py: the same rules over history, with the leverage grid
RSI80 = LOGS / "rsi80"                          # rsi80_paper.py's state / trades (30 s after every 4h close, rsi80-paper.timer)


# ------------------------------------------------------------------ small readers

def jload(p: Path, default=None):
    try:
        return json.loads(p.read_text())
    except Exception:
        return default


def read_csv(p: Path) -> list:
    try:
        with p.open(newline="") as f:
            return list(csv.DictReader(f))
    except Exception:
        return []


def fnum(x, default=None):
    try:
        v = float(x)
        return v if v == v else default
    except (TypeError, ValueError):
        return default


def binance_prices() -> dict:
    try:
        with urllib.request.urlopen("https://fapi.binance.com/fapi/v1/ticker/price", timeout=20) as r:
            return {x["symbol"]: float(x["price"]) for x in json.loads(r.read().decode())}
    except Exception:
        return {}


def price(prices: dict, sym: str):
    """The bot's symbol -> a Binance futures price in the SAME units (SHIBUSDT is listed as 1000SHIBUSDT)."""
    if sym in prices:
        return prices[sym]
    if "1000" + sym in prices:
        return prices["1000" + sym] / 1000
    if sym.startswith("1000") and sym[4:] in prices:
        return prices[sym[4:]] * 1000
    if sym.startswith("1M") and "1000" + sym[2:] in prices:          # Bitget's 1MCHEEMS = 1,000 x Binance's 1000CHEEMS
        return prices["1000" + sym[2:]] * 1000
    if sym == "RAYUSDT" and "RAYSOLUSDT" in prices:                  # Bitget's RAY is Binance's RAYSOL (combo_bot.ALIASES)
        return prices["RAYSOLUSDT"]
    return None


def ms_utc(ms) -> str | None:
    return datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%Y-%m-%d %H:%M:%S") if ms else None


def day_ts(day: str) -> int:
    return int(datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())


# ------------------------------------------------------------------ open positions, Binance style

def struck_price(weight, base, coins):
    """The price a daily-marked basket name was OPENED at: weight x base / coins (the identity combo_bot.mn_squeeze_exits uses;
    the coins are fixed at the rebalance, the weights and base too). None when the bot holds no coins for the name."""
    if not weight or not base or not coins or (weight > 0) != (coins > 0):
        return None
    return weight * base / coins


def open_positions(st: dict, prices: dict) -> list:
    rows = []

    def add(book, sym, qty, entry, mark, upnl, since, note="", **extra):
        cost = abs(qty) * entry if entry else 0.0
        rows.append(dict(book=book, sym=sym, side="long" if qty > 0 else "short", qty=qty,
                         size=round(abs(qty) * (mark or entry or 0.0), 2), entry=entry, mark=mark,
                         upnl=None if upnl is None else round(upnl, 4),
                         pct=None if upnl is None or not cost else round(upnl / cost, 5), since=since, note=note, **extra))

    tr = st.get("trend", {}) or {}
    for key, r in (tr.get("open", {}) or {}).items():
        sym, _, tf = key.partition(":")
        sgn = 1 if r.get("side") == "long" else -1
        entries = [r["entry"]] + list(r.get("adds", []))
        rusd = r.get("risk_usd") or (tr.get("equity") or st.get("equity", START_EQUITY)) * r.get("risk_used", 0.3) / 100
        per = rusd / max(r.get("risk", 0.0), 1e-12)                    # coins per unit (blend_paper.marked)
        m = price(prices, sym)
        upnl = sum((m - e) * sgn for e in entries) * per if m else None
        add("trend", sym, sgn * per * len(entries), sum(entries) / len(entries), m, upnl, r.get("entry_bar"),
            f"{tf} breakout, {len(entries)} unit{'s' if len(entries) > 1 else ''}, stop {r.get('stop', 0):.6g}")

    # The market-neutral, carry and bear baskets are booked DAILY: each day's P&L is the day's move on that day's exposure, and
    # the next day starts from the new mark. So for these rows `entry` is the last daily MARK, `upnl` / `pct` are TODAY's move
    # (they sum to the account's open P&L), and `daily` tells the page to say so. `open_px` is the price the basket was really
    # opened at and `chg_open` the PRICE move since - information, not the position's P&L.
    def basket(book, b, note, coins):
        for s, w in (b.get("weights", {}) or {}).items():
            p0 = (b.get("mark_px", {}) or {}).get(s)
            if not p0:
                continue
            qty = b.get("base", 0.0) * w / p0
            m = price(prices, s)
            op = struck_price(w, b.get("base"), (coins or {}).get(s))
            add(book, s, qty, p0, m, qty * (m - p0) if m else None, b.get("last_rebal"), note, daily=1,
                open_px=None if op is None else round(op, 10), chg_open=None if op is None or not m else round(m / op - 1, 5))

    ex = st.get("exec", {}) or {}
    basket("mn", st.get("mn", {}) or {}, "weekly basket, booked daily: P&L is today's move from the last daily mark", ex.get("mn_qty"))
    fin = st.get("fin", {}) or {}
    basket("carry", fin.get("carry", {}) or {}, "funding basket, booked daily: P&L is today's move from the last daily mark", ex.get("carry_qty"))
    sl = st.get("sleeve", {}) or {}
    for s, n in (sl.get("hold", {}) or {}).items():
        p0 = (sl.get("mark_px", {}) or {}).get(s)
        if p0:
            m = price(prices, s)
            add("sleeve", s, n / p0, p0, m, n * (m / p0 - 1) if m else None, None,
                "bear basket, booked daily: P&L is today's move from the last daily mark", daily=1)
    for b, note in (("daily", "daily Bollinger breakout"), ("capit2", "crash buy")):
        for s, p in ((fin.get(b, {}) or {}).get("open", {}) or {}).items():
            m = price(prices, s)
            add(b, s, p["qty"], p["entry"], m, p["qty"] * (m - p["entry"]) if m else None, ms_utc(p.get("t_ms")), note)
    for p in ((fin.get("news", {}) or {}).get("open", {}) or {}).values():
        mc, mb = price(prices, p["coin"]), price(prices, "BTCUSDT")
        add("news", p["coin"], p["q_coin"], p["e_coin"], mc, p["q_coin"] * (mc - p["e_coin"]) if mc else None,
            ms_utc(p.get("t_ms")), f"after '{p.get('etype')}' news")
        add("news", "BTCUSDT", p["q_btc"], p["e_btc"], mb, p["q_btc"] * (mb - p["e_btc"]) if mb else None,
            ms_utc(p.get("t_ms")), f"hedge for the {p['coin'].replace('USDT', '')} short")
    nd = (fin.get("ndx", {}) or {}).get("open")
    if nd:
        m = price(prices, "QQQUSDT")
        add("ndx", "QQQUSDT", nd["qty"], nd["entry"], m, nd["qty"] * (m - nd["entry"]) if m else None,
            ms_utc(nd.get("t_ms")), f"NASDAQ dip buy, {nd.get('days', 0)} closes held")
    for k, sl in ((fin.get("crowd", {}) or {}).get("sleeves", {}) or {}).items():     # --crowd (crowd_book.py)
        for p in sl.get("pos", []) or []:
            m = price(prices, p["sym"])
            add("crowd", p["sym"], p["qty"], p["entry"], m, p["qty"] * (m - p["entry"]) if m else None,
                ms_utc(p.get("t_ms")), f"{'Monday' if k == 'mon' else 'Thursday'} half, "
                f"crowd most {'short' if p['side'] > 0 else 'long'}")
    rows.sort(key=lambda r: -abs(r["upnl"] or 0.0))
    return rows


# ------------------------------------------------------------------ closed trades

def closed_trades(d: Path) -> list:
    out = []
    for r in read_csv(d / "combo_final_trades.csv"):
        entry, exit_, ret, pnl = fnum(r.get("entry")), fnum(r.get("exit")), fnum(r.get("ret")), fnum(r.get("pnl"))
        # the log has no side column: the news book and the carry book's "short_exit" are always shorts, the crowd
        # book says so in its reason, everything else (daily, capit2, bids, ndx) is long
        short = (r.get("book") == "news" or r.get("why") == "short_exit"
                 or (r.get("book") == "crowd" and str(r.get("why", "")).endswith("short")))
        out.append(dict(ts=r.get("ts"), book=r.get("book"), sym=r.get("symbol"),
                        side="short" if short else "long", entry=entry, exit=exit_, pct=ret,
                        pnl=pnl, why=r.get("why"), approx=False))
    for r in read_csv(d / "trades_combo_trend.csv"):
        entry, exit_, R = fnum(r.get("entry")), fnum(r.get("exit")), fnum(r.get("R"), 0.0)
        rk, eq_after = fnum(r.get("risk_pct"), 0.3) / 100, fnum(r.get("equity"))
        sgn = 1 if r.get("side") == "long" else -1
        # the trend log has R, not dollars: P&L = R x the unit's risk, risk = rk x the book's equity at entry
        pnl = eq_after * R * rk / (1 + R * rk) if eq_after else None
        out.append(dict(ts=r.get("ts"), book="trend", sym=r.get("symbol"), side=r.get("side"), entry=entry, exit=exit_,
                        pct=(exit_ / entry - 1) * sgn if entry and exit_ else None, pnl=pnl, R=R,
                        why=f"{r.get('sleeve')} exit, {r.get('units')} unit(s)", approx=True))
    out.sort(key=lambda r: r.get("ts") or "", reverse=True)
    for r in out:
        for k in ("pct", "pnl"):
            if r.get(k) is not None:
                r[k] = round(r[k], 5 if k == "pct" else 4)
    return out


def book_stats(closed: list) -> dict:
    """Per book: closed trades and their mean % (the Leads tab's record of the books that live inside the machine)."""
    out = {}
    for r in closed:
        if r.get("book") in ("trend", None) or r.get("pct") is None:
            continue
        b = out.setdefault(r["book"], dict(n=0, sum=0.0))
        b["n"] += 1
        b["sum"] += r["pct"]
    return {k: dict(n=v["n"], mean=round(v["sum"] / v["n"] * 100, 3)) for k, v in out.items()}


def trade_stats(closed: list) -> dict:
    pn = [r["pnl"] for r in closed if r.get("pnl") is not None]
    wins = [x for x in pn if x > 0]
    return dict(n=len(pn), wins=len(wins), win_rate=len(wins) / len(pn) if pn else None, total=round(sum(pn), 2),
                best=round(max(pn), 2) if pn else None, worst=round(min(pn), 2) if pn else None)


# ------------------------------------------------------------------ the equity curve (own files)

def read_pairs(p: Path) -> list:
    out = []
    try:
        for line in p.read_text().splitlines():
            a, _, b = line.partition(",")
            if a.isdigit() and fnum(b) is not None:
                out.append((int(a), float(b)))
    except FileNotFoundError:
        pass
    return out


def write_pairs(p: Path, rows: list):
    tmp = p.with_suffix(".tmp")
    tmp.write_text("".join(f"{t},{e:.4f}\n" for t, e in rows))
    tmp.replace(p)


def record_curve(acct: str, t: int, eq: float) -> tuple:
    CURVES.mkdir(parents=True, exist_ok=True)
    pm, ph = CURVES / f"eq_{acct}_m.csv", CURVES / f"eq_{acct}_h.csv"
    m = [r for r in read_pairs(pm) if r[0] >= t - 2 * 86400] + [(t, eq)]
    write_pairs(pm, m)
    h = read_pairs(ph)
    if h and h[-1][0] // 3600 == t // 3600:
        h[-1] = (t, eq)                           # the hour's LAST value
    else:
        h.append((t, eq))
    write_pairs(ph, h)
    return m, h


def curves(m: list, h: list, eq_hist: list, now: int, live_eq: float, start: float) -> dict:
    """5-min points for the last 24h, hourly since the start (the bot's daily marks before this feed existed), and
    the P&L of each UTC day. Before the feed, a day's P&L is the booked change between the bot's daily marks; from
    the feed's first day on it is LIVE equity (booked + open), the first day measured from the feed's first point."""
    m = m + [(now, live_eq)] if not m or m[-1][0] != now else m
    buckets = {}
    for t, e in m:
        if t >= now - 86400:
            buckets[t // 300] = (t, round(e, 2))
    d5 = [list(v) for _, v in sorted(buckets.items())]
    first_live = h[0][0] if h else now
    hist = [(day_ts(dy) - 1, e) for dy, e in (eq_hist or []) if day_ts(dy) - 1 < first_live]   # a mark = previous close
    hourly = [[t, round(e, 2)] for t, e in hist + h]
    if not hourly or hourly[-1][0] < now:
        hourly.append([now, round(live_eq, 2)])
    days = {}
    for t, e in h + [(now, live_eq)]:
        dy = datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%d")
        days.setdefault(dy, [e, e])[1] = e
    bars, prev = [], None
    hd = [(datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%d"), e) for t, e in hist]   # (day, its close)
    for i in range(1, len(hd)):                      # booked days, before the feed
        if hd[i][0] not in days:
            bars.append([hd[i][0], round(hd[i][1] - hd[i - 1][1], 2)])
    for dy in sorted(days):
        first, last = days[dy]
        base = prev if prev is not None else (start if not hist else first)
        bars.append([dy, round(last - base, 2)])
        prev = last
    return dict(d=d5, h=hourly, daily=bars[-120:])


# ------------------------------------------------------------------ the scorecard: live vs the backtest's range

def pctile(v: float, levels: list, q: list) -> float:
    """Where v sits in the stored quantiles (ties: the middle of the tied range) - scorecard_bands.pctile's twin."""
    if v < q[0]:
        return 0.0
    if v > q[-1]:
        return 100.0
    eq = [i for i, x in enumerate(q) if abs(x - v) < 1e-12]
    if eq:
        return (levels[eq[0]] + levels[eq[-1]]) / 2
    i = max(j for j, x in enumerate(q) if x < v)
    return levels[i] + (levels[i + 1] - levels[i]) * (v - q[i]) / (q[i + 1] - q[i])


def band_at(b: dict, lengths: list, n: float) -> tuple:
    """The quantiles and idle share for a stretch of n days, linear between the stored lengths."""
    n = min(max(n, lengths[0]), lengths[-1])
    lo = max(x for x in lengths if x <= n)
    hi = min(x for x in lengths if x >= n)
    w = 0.0 if hi == lo else (n - lo) / (hi - lo)
    a, z = b[str(lo)], b[str(hi)]
    return [x + (y - x) * w for x, y in zip(a["q"], z["q"])], a["idle"] + (z["idle"] - a["idle"]) * w


def status(p: float, live_idle: bool, idle_share: float) -> str:
    if live_idle and idle_share >= 0.2:
        return "idle"                              # no trade yet, and the backtest is often idle this long
    return "worse" if p < 5 else "below" if p < 25 else "ok" if p <= 75 else "above"


def scorecard(started: str | None, now: int, books: dict, equity: float, start: float, bands: dict | None) -> dict:
    if not bands or not started:
        return dict(ready=False, why="no yardstick")
    days = (now - datetime.strptime(started[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc).timestamp()) / 86400
    if days < SCORE_MIN_DAYS:
        return dict(ready=False, days=round(days, 2), min_days=SCORE_MIN_DAYS, why="under a week old")
    L, lengths = bands["levels"], bands["lengths"]

    def q_at(q, lv):                               # the quantile at any level, linear between the stored ones
        i = max(j for j, x in enumerate(L) if x <= lv)
        return q[i] if L[i] == lv else q[i] + (q[i + 1] - q[i]) * (lv - L[i]) / (L[i + 1] - L[i])

    pick = lambda q: {k: round(q_at(q, lv) * start, 2) for k, lv in (("p5", 5), ("p25", 25), ("p50", 50),  # noqa: E731
                                                                       ("p75", 75), ("p95", 95))}
    rows = []
    for bk in SCORE_BOOKS:
        if bk not in bands["books"]:
            continue
        usd = books[bk]["booked"] + books[bk]["open"]
        q, idle = band_at(bands["books"][bk], lengths, days)
        p = pctile(usd / start, L, q)
        rows.append(dict(book=bk, usd=round(usd, 2), pctile=round(p, 1), status=status(p, abs(usd) < 0.01, idle),
                         idle_share=round(idle, 3), **pick(q)))
    q, _ = band_at(bands["total"], lengths, days)
    v = equity / start - 1
    p = pctile(v, L, q)
    return dict(ready=True, days=round(days, 2), capped=days > lengths[-1], span=bands.get("span"), made=bands.get("made"),
                total=dict(usd=round(equity - start, 2), ret=round(v, 5), pctile=round(p, 1), status=status(p, False, 0),
                           **{k: round(x / start, 5) for k, x in pick(q).items()}), books=rows)


# ------------------------------------------------------------------ one account

def account(acct: str, d: Path, prices: dict, now: int, write: bool, bands: dict | None = None) -> dict | None:
    st = jload(d / "combo_state.json")
    if not st:
        return None
    booked = float(st.get("equity", START_EQUITY))
    pos = open_positions(st, prices)
    unreal = sum(r["upnl"] or 0.0 for r in pos)
    live = booked + unreal
    m, h = record_curve(acct, now, live) if write else (read_pairs(CURVES / f"eq_{acct}_m.csv"),
                                                          read_pairs(CURVES / f"eq_{acct}_h.csv"))
    cv = curves(m, h, st.get("eq_hist") or [], now, live, START_EQUITY)
    peak = max([float(st.get("peak", booked)), live] + [e for _, e in h])
    cum = {k: round(v, 4) for k, v in (st.get("cum") or {}).items()}
    by_book = {}
    for r in pos:
        by_book[r["book"]] = by_book.get(r["book"], 0.0) + (r["upnl"] or 0.0)
    books = {b: dict(booked=round(cum.get(b, 0.0), 2), open=round(by_book.get(b, 0.0), 2))
             for b in ("trend", "mn", "carry", "sleeve", "daily", "capit2", "bids", "news", "ndx")}
    has_crowd = "crowd" in (st.get("fin", {}) or {})
    if has_crowd:                                   # --crowd (the fresh account): its own bar, NOT in the scorecard
        books["crowd"] = dict(booked=round(cum.get("crowd", 0.0), 2), open=round(by_book.get("crowd", 0.0), 2))
    # the scorecard's bands are the machine WITHOUT the crowd book: compare the account without it (P&L, open, fees)
    live_ex = live - (cum.get("crowd", 0.0) + by_book.get("crowd", 0.0) - cum.get("crowd_fees", 0.0)) if has_crowd else live
    led = (st.get("exec", {}) or {}).get("virtual_pos", {}) or {}
    lng = sht = 0.0
    for s, q in led.items():
        v = q * (price(prices, s.split("/")[0] + "USDT") or 0.0)
        lng, sht = (lng + v, sht) if v > 0 else (lng, sht - v)
    closed = closed_trades(d)
    fin = st.get("fin", {}) or {}
    news = fin.get("news", {}) or {}
    today = datetime.fromtimestamp(now, timezone.utc).strftime("%Y-%m-%d")
    return dict(
        book_stats=book_stats(closed),
        id=acct, started=st.get("started"), start=START_EQUITY, equity=round(live, 2), booked=round(booked, 2),
        unrealized=round(unreal, 2), today=next((p for dy, p in cv["daily"] if dy == today), 0.0),
        peak=round(peak, 2), fall=round(1 - live / peak, 4) if peak else 0.0, max_dd=st.get("max_dd"),
        fees=round(cum.get("fees", 0.0), 2), books=books,
        exposure=dict(long=round(lng, 2), short=round(sht, 2), lev=round((lng + sht) / live, 2) if live > 0 else None,
                      cap=GROSS_CAP),
        open=pos, closed=closed[:CLOSED_KEEP], stats=trade_stats(closed), curve=cv,
        score=scorecard(st.get("started"), now, books, live_ex, START_EQUITY, bands),
        pending=dict(capit2=len((fin.get("capit2", {}) or {}).get("pending", {}) or {}),
                     news=len(news.get("pending", {}) or {})),
        news=dict(recent=list(reversed((news.get("recent") or [])[-NEWS_KEEP:])), seen=news.get("seen", 0),
                  taken=news.get("taken", 0), dropped=news.get("dropped", 0)))


# ------------------------------------------------------------------ everything else (meta)

def mood() -> dict | None:
    """news/crowd_paper.py's hourly market-mood snapshot (news/mood_now.py), trimmed for the page."""
    m = jload(MOOD)
    if not m:
        return None
    keep = ("sym", "long_share", "crowd_pct", "fund_yr", "taker", "oi7", "flag")
    rd = lambda v: round(v, 4) if isinstance(v, float) else v  # noqa: E731
    return dict(t=m.get("t"), market={k: rd(v) for k, v in (m.get("market") or {}).items()},
                coins=[{k: rd(r.get(k)) for k in keep} for r in m.get("coins") or []])


def crowd(prices: dict, now: int, bands: dict | None) -> dict | None:
    """The crowd-squeeze paper book (news/crowd_paper.py): live equity = each sleeve's opening equity x (1 + its legs'
    moves since entry at Binance's price now - the funding counted at the last daily mark - the week's fee), the legs,
    the daily marks, the closed weeks, and its place in the backtest's range (crowd_bands.json) from week 4."""
    st = jload(CROWD / "state.json")
    if not st:
        return None
    sleeves, legs, tot = [], [], 0.0
    for k, sl in st["sleeves"].items():
        pos, g = sl.get("pos") or [], 0.0
        for p in pos:
            mk = prices.get(p["sym"]) or p.get("mark") or p["entry"]
            r, f = mk / p["entry"] - 1, p.get("fund", 0.0)
            g += p["side"] * p["w"] * (r - f)
            legs.append(dict(sleeve=k, sym=p["sym"], side="long" if p["side"] > 0 else "short", entry=p["entry"], mark=mk,
                             pct=round(r, 5), size=round(sl["equity"] * p["w"], 2),
                             upnl=round(sl["equity"] * p["side"] * p["w"] * (r - f), 2)))
        eq = sl["equity"] * (1 + g - (sl.get("fee", 0.0) if pos else 0.0))
        tot += eq
        sleeves.append(dict(id=k, equity=round(eq, 2), booked=round(sl["equity"], 2), weeks=sl.get("weeks", 0),
                            next=sl.get("next"), opened=sl.get("opened"), funding=round(sl.get("fund_usd", 0.0), 2)))
    start = st.get("start", 300.0)
    marks = [(day_ts(r["day"]), fnum(r.get("total"))) for r in read_csv(CROWD / "marks.csv")]
    h = [[t, round(e, 2)] for t, e in marks if e is not None][-400:] + [[now, round(tot, 2)]]
    weeks = [dict(sleeve=r["sleeve"], opened=r["opened"], closed=r["closed"], net=fnum(r["net"]),
                  usd=round(fnum(r["equity_after"], 0.0) - fnum(r["equity_before"], 0.0), 2))
             for r in read_csv(CROWD / "sleeves.csv")][-30:][::-1]
    score = dict(ready=False, min_weeks=CROWD_MIN_WEEKS)
    first = st.get("first")
    if first and bands:
        wk = (now - day_ts(first)) / (7 * 86400)
        score["weeks"] = round(wk, 2)
        if wk >= CROWD_MIN_WEEKS:
            q, _ = band_at(bands["total"], bands["lengths"], wk)
            v = tot / start - 1
            p = pctile(v, bands["levels"], q)
            score = dict(ready=True, weeks=round(wk, 2), ret=round(v, 5), pctile=round(p, 1), status=status(p, False, 0),
                         p10=q[1], p50=q[3], span=bands.get("span"))
    return dict(started=st.get("started"), first=first, start=start, equity=round(tot, 2), sleeves=sleeves, legs=legs,
                curve=dict(d=h[-2:], h=h), weeks=weeks, score=score)


def slim_grid(g: list) -> list:
    keep = ("capital", "lev", "equity", "ret", "taken", "wins", "liquidated", "skipped_busy", "pending", "worst", "maxdd", "ruined")
    return [{k: (round(c[k], 4) if isinstance(c[k], float) else c[k]) for k in keep} for c in g]


def replay_view(r: dict | None) -> dict | None:
    """backtest/analyst_replay.py's result, trimmed for the page: the grid on the whole span and the holdout, the resampled years, the rule table."""
    if not r or not r.get("grid"):
        return None
    rd = lambda v: round(v, 4) if isinstance(v, float) else v  # noqa: E731
    return dict(made=r.get("made"), span=r.get("span"), years=r.get("years"), calls=r.get("calls"), taken=r.get("taken"), per_year=r.get("per_year"),
                stats={k: {a: rd(b) for a, b in (v or {}).items()} for k, v in (r.get("stats") or {}).items()},
                by_method={m: dict(n=v["n"], hold=v["hold"], tune=v["tune"]) for m, v in (r.get("by_method") or {}).items()},
                grid=dict(all=slim_grid(r["grid"]["all"]), hold=slim_grid(r["grid"]["hold"])),
                boot=[{k: rd(v) for k, v in b.items()} for b in r.get("boot") or []],
                paper_book={k: (rd(v) if not isinstance(v, dict) else {a: rd(b) for a, b in v.items()}) for k, v in (r.get("paper_book") or {}).items()} or None,
                check_1m={k: ({a: rd(b) for a, b in v.items()} if isinstance(v, dict) else v) for k, v in (r.get("check_1m") or {}).items()} or None)


# ------------------------------------------------------------------ the Analyst desk's "sweet spot" watch (2026-11-06, backtest/analyst_sweetspot.py)

SWEET_STOP, SCALP_STOP = 0.008, 0.004          # a call is "sweet-spot-sized" from a 0.8% stop; under 0.4% it is scalp-sized (registered 2026-11-06 15:00 UTC)
SWEET_BETS = 30                                 # independent bets the registered test needs
SWEET_REGISTERED_MS = 1793977200000             # 2026-11-06 15:00 UTC: only calls made from here on are scored (= backtest.analyst_sweetspot.REGISTERED_MS)
DESK_MIN_RR, SR_NEAR_ATR, WATCH_MAX = 1.5, 1.5, 6


def wilson(k: float, n: float, z: float = 1.96):
    """Wilson score interval for k successes in n trials (k may be fractional: it is rescaled to the number of independent bets)."""
    if n <= 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def call_kind(stop_pct):
    if stop_pct is None:
        return None
    return "sweet" if stop_pct >= SWEET_STOP else "scalp" if stop_pct < SCALP_STOP else "mid"


def desk_history(rows: list, kind: str | None = None, method: str | None = None) -> dict:
    """The desk's RESOLVED calls of one stop size (and method): calls, independent bets (same UTC day + same side), wins, hit rate, a 95% range that
    counts the BETS and not the calls (a Wilson interval on the bets), and the mean result after fees per call and per bet."""
    sel = []
    for r in rows:
        if r.get("status") not in ("WIN", "LOSS", "EXPIRED"):
            continue
        res, sp = fnum(r.get("r_net")), fnum(r.get("stop_pct"))
        if res is None or sp is None or (kind and call_kind(sp) != kind) or (method and r.get("method") != method):
            continue
        sel.append((str(r.get("made_utc"))[:10], r.get("side"), res, r["status"] == "WIN"))
    if not sel:
        return dict(n=0, bets=0)
    groups: dict = {}
    for d, s, res, _ in sel:
        groups.setdefault((d, s), []).append(res)
    per_bet = [sum(v) / len(v) for _, v in sorted(groups.items())]
    wins = sum(1 for x in sel if x[3])
    p = wins / len(sel)
    lo, hi = wilson(p * len(per_bet), len(per_bet))
    return dict(n=len(sel), bets=len(per_bet), wins=wins, hit=round(p, 4), lo=round(lo, 3), hi=round(hi, 3),
                mean_r=round(sum(x[2] for x in sel) / len(sel), 3), mean_r_bet=round(sum(per_bet) / len(per_bet), 3))


def watch_items(symbols: dict, next_run: int | None = None) -> list:
    """Where a desk rule could fire in the NEXT run, from the levels and the live price - the rule's own geometry (analyst.signals), no prediction.
    FIB: the live price is inside the 50-78.6% zone, so the call that would be logged if the hour closed with the swing is fully fixed (stop and target
    come from the levels). SR: a strong level is within 1.5 ATR; the stop depends on how far the hour's wick goes, so it is a RANGE (wick no deeper than
    the level ... one ATR through it). Liquidity sweeps depend on the hour's own wick and cannot be previewed.
    With `next_run` (ms), a symbol the desk cannot call at that run (analyst.can_call: gold / QQQ while their market is shut) is left out."""
    can = None
    if next_run is not None:
        import analyst as an
        bar = next_run // 3_600_000 * 3_600_000 - 3_600_000                  # the candle the next run reads began an hour before its hour
        can = lambda s: an.can_call(s, next_run, bar)                        # noqa: E731
    out = []
    for sym, v in symbols.items():
        if can is not None and not can(sym):
            continue
        px = v.get("price")
        a1 = (v.get("atr1_pct") or 0.0) * (px or 0.0)
        if not px or a1 <= 0:
            continue
        sw = v.get("fib")
        l886 = ((sw or {}).get("levels") or {}).get("0.886")
        if sw and l886 is not None and sw.get("retraced") is not None and 0.5 <= sw["retraced"] <= 0.786:
            up = sw["trend"] == "up"
            stop = l886 - 0.25 * a1 if up else l886 + 0.25 * a1
            tgt = sw["hi"] if up else sw["lo"]
            risk, reward = abs(px - stop), abs(tgt - px)
            geo = (stop < px < tgt) if up else (tgt < px < stop)
            fires = bool(geo and risk > 0 and reward / risk >= DESK_MIN_RR and 0.3 * a1 <= risk <= 4 * a1)
            out.append(dict(kind="FIB", symbol=sym, side="long" if up else "short", price=px, dist_atr=0.0, stop=round(stop, 8), target=tgt,
                            stop_pct=round(risk / px, 5), rr=round(reward / risk, 2) if risk else None, fires=fires, kind_size=call_kind(risk / px),
                            need=f"price is {sw['retraced'] * 100:.0f}% into the {sw['trend']} swing; fires if the hour closes {'up' if up else 'down'}"
                                 if fires else "inside the 50-78.6% zone, but the stop or reward:risk fails the desk's limits - no call"))
        for side, levels, other in (("long", v.get("support") or [], v.get("resistance") or []), ("short", v.get("resistance") or [], v.get("support") or [])):
            strong = [x for x in levels if x.get("touches", 0) >= 3]
            if not strong:
                continue
            lv = min(strong, key=lambda x: abs(x["price"] - px))
            dist = abs(px - lv["price"]) / a1
            if dist > SR_NEAR_ATR or (side == "long" and lv["price"] >= px) or (side == "short" and lv["price"] <= px):
                continue
            lo_stop = abs(px - lv["price"]) + 0.5 * a1                       # the wick stops at the level
            hi_stop = abs(px - lv["price"]) + 1.5 * a1                       # the wick goes a full ATR through it
            tgt = other[0]["price"] if other else None
            rr = None if tgt is None else (round(abs(tgt - px) / hi_stop, 2), round(abs(tgt - px) / lo_stop, 2))
            out.append(dict(kind="SR", symbol=sym, side=side, price=px, dist_atr=round(dist, 2), level=lv["price"], touches=lv["touches"],
                            stop_pct_lo=round(lo_stop / px, 5), stop_pct_hi=round(hi_stop / px, 5), target=tgt, rr=rr,
                            kind_size="sweet" if lo_stop / px >= SWEET_STOP else "maybe" if hi_stop / px >= SWEET_STOP else "small",
                            need=f"{'above' if side == 'long' else 'below'} a {lv['touches']}-touch level; fires if an hourly candle wicks into it and "
                                 f"closes back {'above' if side == 'long' else 'below'} with a wick of at least half its range"))
    out.sort(key=lambda x: (0 if x["kind"] == "FIB" else 1, x["dist_atr"]))
    return out[:WATCH_MAX]


def sweet_view(rows: list, open_calls: list, symbols: dict, now: int) -> dict:
    """The sweet-spot watch: the registered claim and its forward progress, the desk's history by stop size with its real uncertainty, every open call
    tagged and priced from here, and the setups that could fire next. Everything is the desk's own record - a measurement, not a forecast."""
    hist = dict(sweet=desk_history(rows, "sweet"), mid=desk_history(rows, "mid"), scalp=desk_history(rows, "scalp"),
                by_method={m: desk_history(rows, "sweet", m) for m in ("SR", "FIB", "SMC")})
    by_id = {int(r["id"]): r for r in rows if str(r.get("id", "")).isdigit()}
    calls = []
    for c in open_calls:
        r = by_id.get(c["id"], {})
        sp = fnum(r.get("stop_pct"))
        kind = call_kind(sp)
        cell = hist["by_method"].get(c["method"]) if kind == "sweet" else None
        odds = cell if cell and cell.get("n", 0) >= 5 else hist.get(kind) if kind else None
        px, entry, stop, tgt = c.get("mark"), c.get("entry"), c.get("stop"), c.get("target")
        long_ = c["side"] == "long"
        have = px is not None and stop is not None and tgt is not None
        risk_now = ((px - stop) if long_ else (stop - px)) if have else 0.0
        rr_now = ((tgt - px) if long_ else (px - tgt)) / risk_now if have and risk_now > 0 else None
        calls.append(dict(id=c["id"], kind=kind, stop_pct=sp, odds=odds, odds_scope=("method" if odds is cell else "size") if odds else None,
                          rr_now=None if rr_now is None else round(rr_now, 2), valid=bool(rr_now is not None and rr_now >= DESK_MIN_RR)))
    fw = dict(bets=0, needed=SWEET_BETS, verdict=f"NOT YET - 0 of {SWEET_BETS} independent bets")
    try:
        from backtest import analyst_sweetspot as ss
        sc = ss.score(ss.load(ANALYST / "calls.csv"))
        fw = dict(calls=sc["calls"], bets=sc["bets"], needed=SWEET_BETS, mean_r_bet=round(sc["mean_r"], 3), hit=round(sc["hit"], 3), base=round(sc["base"], 3),
                  t=None if sc["t"] is None else round(sc["t"], 2), verdict=sc["verdict"])
    except Exception:                                    # the registered scorer must never break the rest of the feed
        pass
    nxt = (now // 3600) * 3600 + 7 * 60
    nxt = nxt if nxt > now else nxt + 3600
    return dict(def_stop=SWEET_STOP, scalp_stop=SCALP_STOP, registered="2026-11-06 15:00 UTC", registered_ms=SWEET_REGISTERED_MS, forward=fw, history=hist, calls=calls,
                watch=watch_items(symbols, nxt * 1000), next_run=nxt, min_rr=DESK_MIN_RR)


def analyst_view(prices: dict, now: int) -> dict | None:
    """The Analyst desk (analyst.py): its levels against the LIVE price, its open predictions marked live, its record against
    the random baseline, and its own $300 paper book (booked P&L + every open booked call at the live price, fee included)."""
    st = jload(ANALYST / "state.json")
    if not st:
        return None
    try:
        import analyst as an
    except Exception:                                   # the desk's module must never break the rest of the feed
        return None
    rows = read_csv(ANALYST / "calls.csv")
    lv = jload(ANALYST / "levels.json") or {}
    fee = an.desk.FEE
    marks, up_tot = {}, 0.0
    open_calls = []
    for r in rows:
        if r.get("status") != "open":
            continue
        px = price(prices, r["symbol"])
        side = 1 if r["side"] == "long" else -1
        entry, sp, risk = fnum(r["entry"]), fnum(r["stop_pct"]), fnum(r["risk_usd"], 0.0)
        pct = side * (px / entry - 1) if px and entry else None
        rr = (pct - fee) / sp if pct is not None and sp else None
        booked = r.get("nobook") != "1"
        upnl = round(rr * risk, 2) if rr is not None and booked else None
        up_tot += upnl or 0.0
        open_calls.append(dict(id=int(r["id"]), symbol=r["symbol"], side=r["side"], method=r["method"], why=r.get("why") or r.get("note"),
                               made=r["made_utc"], entry=entry, stop=fnum(r["stop"]), target=fnum(r["target"]), mark=px,
                               pct=None if pct is None else round(pct, 5), r=None if rr is None else round(rr, 3), upnl=upnl,
                               booked=booked, base_p=fnum(r["base_p"]), be_p=fnum(r["be_p"]), rr=fnum(r["rr"]),
                               left_h=round((fnum(r["expires_ms"], 0.0) - now * 1000) / 3_600_000, 1), size=fnum(r["notional"])))
    closed = [r for r in rows if r.get("status") in ("WIN", "LOSS", "EXPIRED")]
    closed.sort(key=lambda r: fnum(r.get("exit_ms"), 0.0), reverse=True)
    recent = [dict(id=int(r["id"]), symbol=r["symbol"], side=r["side"], method=r["method"], status=r["status"], made=r["made_utc"],
                   entry=fnum(r["entry"]), exit=fnum(r.get("exit_price")), r=round(fnum(r["r_net"], 0.0), 3), base_p=fnum(r["base_p"]),
                   usd=fnum(r.get("pnl_usd")) if r.get("booked") == "1" else None, booked=r.get("booked") == "1",
                   closed=ms_utc(fnum(r.get("exit_ms"))))
              for r in closed[:ANALYST_KEEP]]
    symbols = {}
    for sym, d in (lv.get("symbols") or {}).items():
        px = price(prices, sym) or d.get("price")
        if not px:
            continue
        sd = d.get("typical_move_pct") or 0.0
        sw = d.get("fib")
        if sw and sw.get("hi") and sw.get("lo") and sw["hi"] > sw["lo"]:
            ret = (sw["hi"] - px) / (sw["hi"] - sw["lo"]) if sw["trend"] == "up" else (px - sw["lo"]) / (sw["hi"] - sw["lo"])
            sw = dict(sw, retraced=round(ret, 3))
        lvl = lambda xs: [dict(price=x["price"], touches=x["touches"], dist=round(x["price"] / px - 1, 5)) for x in xs]  # noqa: E731
        symbols[sym] = dict(price=px, atr1_pct=d.get("atr1_pct"), typical_move_pct=sd,
                            typical=[round(px * (1 - sd), 8), round(px * (1 + sd), 8)],
                            support=lvl(d.get("support") or []), resistance=lvl(d.get("resistance") or []), fib=sw,
                            gaps=d.get("gaps") or [], calls=[c["id"] for c in open_calls if c["symbol"] == sym])
    start, booked_eq = st.get("start", 300.0), st["equity"]
    live = booked_eq + up_tot
    h = [[day_ts(r["day"]), round(fnum(r["equity"]), 2)] for r in read_csv(ANALYST / "marks.csv") if fnum(r.get("equity")) is not None][-400:]
    if not h:
        h = [[int(st.get("started_ms", now * 1000) / 1000), round(start, 2)]]
    h = h + [[now, round(live, 2)]]
    s = an.stats(rows)
    s["min_resolved"] = an.MIN_RESOLVED
    return dict(started=st.get("started"), start=start, equity=round(live, 2), booked=round(booked_eq, 2), peak=round(st.get("peak", start), 2),
                levels_t=lv.get("made"), symbols=symbols, open=open_calls, recent=recent, stats=s, curve=dict(d=h[-2:], h=h),
                sweet=sweet_view(rows, open_calls, symbols, now), what_if=dict(live=slim_grid(an.grid(rows)), replay=replay_view(jload(ANALYST_REPLAY))),
                cfg=dict(watch=an.WATCH, risk_pct=an.RISK_PCT, max_gross=an.MAX_GROSS, hours=an.HOURS, review=dict(resolved=100, date="2027-01-31")))


def others() -> list:
    out = []
    c = jload(LOGS / "combo_state.json")
    if c:
        out.append(dict(name="Machine v2 paper", equity=round(c.get("equity", 0.0), 2), start=221.0, started=c.get("started")))
    w = jload(LOGS / "wickp_state.json")
    if w:
        for venue, l in (w.get("led") or {}).items():
            out.append(dict(name=f"Crash bids ({venue})", equity=round(l.get("equity", 0.0), 2), start=300.0,
                            started=w.get("started")))
    return out


def health() -> dict:
    svc = {}
    for s in SERVICES:
        try:
            a = subprocess.run(["systemctl", "is-active", s], capture_output=True, text=True, timeout=10).stdout.strip()
            n = subprocess.run(["systemctl", "show", s, "-p", "NRestarts", "--value"], capture_output=True, text=True,
                               timeout=10).stdout.strip()
            svc[s] = dict(active=a, restarts=int(n) if n.isdigit() else None)
        except Exception:
            svc[s] = dict(active="unknown", restarts=None)
    mem = {}
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            k, v = line.split(":", 1)
            if k in ("MemTotal", "MemAvailable"):
                mem[k] = int(v.split()[0]) // 1024
    except Exception:
        pass
    du = shutil.disk_usage(str(ROOT))
    return dict(services=svc, memory_mb=mem, disk_used_pct=round(du.used / du.total * 100, 1))


# ------------------------------------------------------------------ the user's Bitget futures wallet, READ-ONLY (for the page's position sizer)

WALLET_TTL_S = 300
WALLET_ENV = ("BITGET_RO_KEY", "BITGET_RO_SECRET", "BITGET_RO_PASSPHRASE")


def _bitget(key: str, secret: str, passphrase: str):
    import ccxt
    return ccxt.bitget({"apiKey": key, "secret": secret, "password": passphrase, "enableRateLimit": True, "timeout": 10000,
                        "options": {"defaultType": "swap"}})


def wallet_view(env=None, factory=None, now=None, cache=None, ttl: int = WALLET_TTL_S):
    """The user's Bitget USDT-futures wallet (equity, available, margin used) for the page's position sizer. INERT unless all three BITGET_RO_* variables are
    set in the service's environment (the user installs them with deploy/bitget_ro_env.sh, a READ-ONLY API key bound to the VM's IP; these are NOT the demo bot's
    keys). The only exchange call is fetch_balance - no order, transfer, leverage or margin call exists in this function (a test pins that). The feed carries three
    totals and a timestamp, never the key, an account id or an error message (an exception is reduced to its class name, which cannot echo a secret). The result,
    errors included, is cached for `ttl` seconds so a bad key is not retried every minute. Never breaks the rest of the feed."""
    env = os.environ if env is None else env
    key, secret, passphrase = (env.get(k) for k in WALLET_ENV)
    if not (key and secret and passphrase):
        return None
    now = int(time.time()) if now is None else now
    cache = CURVES / "wallet.json" if cache is None else cache
    c = jload(cache)
    if c and ttl > 0 and 0 <= now - c.get("t", 0) < ttl:
        return c
    try:
        bal = (factory or _bitget)(key, secret, passphrase).fetch_balance()
        u = bal.get("USDT") or {}
        out = dict(t=now, equity=round(float(u.get("total") or 0.0), 2), available=round(float(u.get("free") or 0.0), 2), used=round(float(u.get("used") or 0.0), 2))
    except Exception as e:                               # the class name only
        out = dict(t=now, error=type(e).__name__)
    try:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(out))
    except Exception:
        pass
    return out


def next_4h_run(now: int) -> int:
    """The paper book's next run: 30 seconds after the next 4h bar closes (00:00:30, 04:00:30, ... UTC; deploy/rsi80-paper.timer), in unix seconds."""
    t = now // 14400 * 14400 + 30
    return t if t > now else t + 14400


def momentum(prices: dict, now: int) -> dict | None:
    """The RSI-80 momentum paper book (rsi80_paper.py): live equity = the booked equity + each open BOOKED trade at Binance's price now (before its exit fee
    and funding); every open trade with its stop, target, result so far and hours left; the record against the registered lines (rsi80_paper.verdict and
    its constants, so the page can never disagree with the book); the recent closed trades and the equity curve from the trade log."""
    st = jload(RSI80 / "state.json")
    if not st:
        return None
    try:
        import rsi80_paper as rp
    except Exception:
        return None
    rows = read_csv(RSI80 / "trades.csv")
    opn, upnl = [], 0.0
    for coin, tr in sorted((st.get("open") or {}).items()):
        e, rf, mk = tr["entry"], tr["rf"], prices.get(coin)
        r_now = (mk - e) / (e * rf) if mk and e > 0 and rf > 0 else None
        u = tr["risk_usd"] * r_now if (r_now is not None and tr.get("booked")) else 0.0
        upnl += u
        opn.append(dict(coin=coin, opened=int(tr["entry_ms"]) // 1000, entry=e, mark=mk, stop=tr["stop"], target=tr["target"],
                        r=None if r_now is None else round(r_now, 3), usd=round(u, 2), notional=round(tr["notional"], 2), booked=bool(tr.get("booked")),
                        hours_left=max(0, (rp.CAP - int(tr.get("bars", 0))) * 4)))
    net = [fnum(r.get("net_r"), 0.0) for r in rows]
    flat = [fnum(r.get("net_r_flat"), 0.0) for r in rows]
    n, booked, start = len(rows), float(st["equity"]), rp.START
    pts = {int(st["started_ms"]) // 1000: start}
    for r in rows:                                       # trades closed in the same run share an exit time: the chart needs ONE point per instant (the later balance)
        pts[int(fnum(r.get("exit_ms"), 0)) // 1000] = round(fnum(r.get("equity_after"), start), 2)
    pts[now] = round(booked + upnl, 2)
    h = [[t, v] for t, v in sorted(pts.items())]                                      # strictly ascending in time, as the chart requires
    curve = dict(d=h[-2:], h=h)                                                         # the chart's shape (charts.EquityChart: d = the 1D view, h = the rest)
    recent = [dict(coin=r["coin"], opened=int(fnum(r.get("entry_ms"), 0)) // 1000, closed=int(fnum(r.get("exit_ms"), 0)) // 1000, kind=r.get("kind"),
                   entry=fnum(r.get("entry")), exit=fnum(r.get("exit")), r=round(fnum(r.get("net_r"), 0.0), 3), usd=round(fnum(r.get("pnl_usd"), 0.0), 2),
                   booked=str(r.get("booked")) in ("True", "true", "1")) for r in rows][-30:][::-1]
    month = datetime.fromtimestamp(now, timezone.utc).strftime("%Y-%m")
    return dict(start=start, equity=round(booked + upnl, 2), booked=round(booked, 2), upnl=round(upnl, 2), started=int(st["started_ms"]) // 1000,
                open=opn, n=n, mean_r=round(sum(net) / n, 3) if n else None, mean_r_flat=round(sum(flat) / n, 3) if n else None,
                wins=sum(1 for x in net if x > 0), exits={k: sum(1 for r in rows if r.get("kind") == k) for k in ("target", "stop", "time")},
                recent=recent, curve=curve, coins=len((st.get("universe") or {}).get(month, [])), next_run=next_4h_run(now),
                verdict=rp.verdict(rows, booked, datetime.fromtimestamp(now, timezone.utc).strftime("%Y-%m-%d")),
                lines=dict(kill_date=rp.KILL_DATE, kill_r=rp.KILL_R, kill_min=rp.KILL_MIN, verdict_date=rp.VERDICT_DATE, held_r=rp.HELD_R,
                           dead_r=rp.DEAD_R, extend=rp.EXTEND_DATE))


# ------------------------------------------------------------------ the Leads tab: every forward record in one list

LEADS_DIR = LOGS / "leads"                      # backtest/forward_ledger.py's ledger.json (replayed on the PC, copied here)
WICK_STATE = LOGS / "wickp_state.json"
DAY45 = dict(ts=1795392240, line=261.30)        # doc 22 s3b: the main account is stopped if under $261.30 at 2026-11-23 00:04 UTC
CROWD_LINES = dict(kill_ts=1800835200, kill=-0.078, verdict_ts=1807228800, dead=-0.066, held=0.168)   # news/crowd_paper.py's docstring
WICK_VERDICT_TS = 1805932800                    # wick_paper.py: verdict at 6 months (from 2026-09-25) with 60+ Bitget fills, else 12
MACHINE_BOOKS = (                               # books inside the final machine: no line of their own, decided with the machine
    ("news", "News book", "Shorts a coin (long BTC beside it) 15 minutes after Binance tags it for monitoring or adds a product for it; "
     "out within 72 hours.", 2.67, "news/entry.py: +3.16% / +2.67% a trade (tune / holdout), 313 trades"),
    ("ndx", "NASDAQ dip-buy", "Buys NASDAQ (QQQ) after a sharp down day (RSI(2) under 10); out at the first close above the 5-day average.",
     0.95, "ndx_capit.py: +0.95% a trade, ~12 a year, 1999-2026"),
    ("capit2", "Capitulation buy", "A limit buy 2% under a coin that fell 10%+ in 24 hours (when several coins capitulate); out at +5% or "
     "after a set time.", 3.0, "capit_stack.py: +3.0% / +4.3% a trade, all four bar phases"),
)


def progress(n, mean, claim, n_min=5):
    """For a record with no line of its own yet: too early under n_min, else on track at half the claim or better."""
    if not n or n < n_min or mean is None:
        return "too early"
    return "on track" if mean >= claim / 2 else "below the claim"


def word_status(v: str) -> str:
    """A book's own verdict sentence -> one of the tab's status words."""
    s = str(v or "")
    if s.startswith(("HELD UP", "PASS")):
        return "held up"
    if s.startswith(("DEAD", "NO PASS")):
        return "dead"
    if s.startswith("CANNOT TELL"):
        return "keep recording"
    return "too early"


def curve_value_at(acct: dict, ts: int):
    """The account's balance at the first hourly point at or after ts (None if the curve has not reached it)."""
    for t, v in (acct.get("curve") or {}).get("h") or []:
        if t >= ts:
            return v
    return None


def leads(mo, cr, an, accts: dict, now: int, ledger=None, wick=None) -> dict:
    rows = []
    a = (accts or {}).get("main")
    if a:
        v = curve_value_at(a, DAY45["ts"])
        st = ("dead" if v < DAY45["line"] else "on track") if v is not None else (
            "on track" if a["equity"] >= DAY45["line"] else "below the line")
        rows.append(dict(id="machine", name="The machine (main account)", kind="the product", started=a.get("started"),
                         what="All the books together on one $300 paper account - the thing real money would go into.",
                         n=None, n_label="", mean=a["equity"], unit="$", mean_label="balance now", claim=DAY45["line"],
                         claim_src="doc 22 s3b: the day-45 line ($261.30 = -12.9%)", decide="23 Nov 2026 (day 45), then 9 Apr 2027",
                         line="Stopped if under $261.30 on 23 Nov 2026 00:04 UTC; the money verdict is 9 Apr 2027 (doc 22).",
                         status=st, years=None, note=f"day-45 balance {v:.2f}" if v is not None else ""))
    if mo:
        rows.append(dict(id="rsi80", name="RSI-80 momentum", kind="live paper", started=mo.get("started"),
                         what="Buys a coin when its 4-hour RSI jumps above 80; wide stop, target 4R, out after 4 days.",
                         n=mo.get("n"), n_label="trades", mean=mo.get("mean_r"), unit="R", mean_label="a trade", claim=0.138,
                         claim_src="rsi80_more.py: +0.138R a trade on coins it had never seen (day-vote t 1.80)", decide="9 Apr 2027",
                         line="Stopped on 31 Jan 2027 if worse than -0.24R a trade after 30+; on 9 Apr 2027 held up at +0.072R or better "
                              "with the book above $300, dead under -0.107R, else runs to Oct 2027.",
                         status=word_status(mo.get("verdict")), years=6.0, note=""))
    if cr:
        ret = cr["equity"] / cr["start"] - 1
        L = CROWD_LINES
        if now < L["kill_ts"]:
            st = "too early"
        elif now < L["verdict_ts"]:
            st = "below the line" if ret < L["kill"] else "on track"
        else:
            st = "dead" if ret < L["dead"] else ("held up" if ret >= L["held"] else "keep recording")
        weeks = (cr.get("score") or {}).get("weeks")
        rows.append(dict(id="crowd", name="Crowd squeeze", kind="live paper", started=cr.get("started"),
                         what="Long the coins the crowd is most short, short the ones it is most long; rebalanced weekly in two halves.",
                         n=weeks, n_label="weeks", mean=round(ret * 100, 2), unit="%", mean_label="since the start", claim=18.4,
                         claim_src="positioning_hist.py --band: median 26 weeks +18.4%, 1 in 10 under -6.5%", decide="9 Apr 2027",
                         line="Stopped on 25 Jan 2027 if under -7.8%; on 9 Apr 2027 dead under -6.6%, held up at +16.8% or better.",
                         status=st, years=None, note=""))
    sw = ((an or {}).get("sweet") or {}).get("forward")
    if sw:
        rows.append(dict(id="sweet", name="Analyst desk sweet spot", kind="live paper", started=SWEET_REGISTERED_MS // 1000,
                         what="The desk's chart calls with a stop at least 0.8% away, counted as independent bets (one per day and side).",
                         n=sw.get("bets"), n_label="of 30 bets", mean=sw.get("mean_r_bet"), unit="R", mean_label="a bet", claim=0.15,
                         claim_src="analyst_sweetspot.py: 13 of 28 calls won in the desk's own record (found after looking)",
                         decide="at 30 bets", line="At 30 bets: mean +0.15R a bet or better, t >= 2, wins above the random odds, both halves positive.",
                         status=word_status(sw.get("verdict")), years=None, note=sw.get("verdict", "")))
    led = ((wick or {}).get("led") or {}).get("bitget")
    if led:
        n = int(led.get("fills", 0))
        m = round(led.get("sum_net", 0.0) / n * 100, 3) if n else None
        rows.append(dict(id="wick", name="Crash bids", kind="live paper", started=wick.get("started"),
                         what="Resting buys 10% under the top-40 coins (none on bear days, at most 10 fills an hour), sold at the hour's close.",
                         n=n, n_label="fills", mean=m, unit="%", mean_label="a fill", claim=0.8,
                         claim_src="wick_bitget.py: +1.01% a kept fill on Bitget 2022-26; expected +0.8-1.0%",
                         decide="25 Mar 2027", line="Verdict at 6 months with 60+ Bitget fills (25 Mar 2027), else at 12 months.",
                         status=progress(n, m, 0.8), years=None, note=""))
    bs = (a or {}).get("book_stats") or {}
    for book, name, what, claim, src in MACHINE_BOOKS:
        b = bs.get(book) or {}
        rows.append(dict(id=book, name=name, kind="inside the machine", started=(a or {}).get("started"), what=what,
                         n=b.get("n", 0), n_label="trades", mean=b.get("mean"), unit="%", mean_label="a trade", claim=claim, claim_src=src,
                         decide="9 Apr 2027 (with the machine)", line="No line of its own: it is judged as part of the machine.",
                         status=progress(b.get("n", 0), b.get("mean"), claim), years=None, note=""))
    for x in (ledger or {}).get("leads", []):
        st = x.get("status", "too early")
        rows.append(dict(id=x["id"], name=x["name"], kind="forward replay", started=(ledger or {}).get("forward_from"), what=x.get("what", ""),
                         n=x.get("n"), n_label="trades", mean=None if x.get("mean") is None else round(x["mean"], 4), unit=x.get("unit"),
                         mean_label="a trade", claim=x.get("claim"), claim_src=x.get("claim_src", ""), decide="when the record allows",
                         line="Dead if the average falls more than 2 standard errors under the backtest claim (5+ trades); confirmed at "
                              "t >= 2 after Holm across the ledger's leads.",
                         status="RULE CHANGED" if st == "RULE CHANGED" else st, years=x.get("years"),
                         note="; ".join(e["note"] for e in (x.get("events") or [])[:1] if e.get("note"))))
    lg = ledger or {}
    return dict(rows=rows, ledger=dict(generated=lg.get("generated"), forward_from=lg.get("forward_from"),
                                       next_nfp=(lg.get("data") or {}).get("next_nfp"), next_fomc=(lg.get("data") or {}).get("next_fomc"),
                                       minutes_to=(lg.get("data") or {}).get("nasdaq_minutes_to"), rule_ok=lg.get("rule_ok"))
                if ledger else None)


def build(write: bool = False) -> tuple:
    prices = binance_prices()
    if not prices:
        raise SystemExit("no Binance prices - nothing pushed this minute")
    now = int(time.time())
    bands = jload(BANDS)
    accts = {}
    for acct, d in ACCOUNTS:
        a = account(acct, d, prices, now, write, bands)
        if a:
            accts[acct] = a
    cr = crowd(prices, now, jload(CROWD_BANDS))
    an = analyst_view(prices, now)
    mo = momentum(prices, now)
    oth = others() + ([dict(name="Crowd squeeze paper", equity=cr["equity"], start=cr["start"], started=cr["started"])]
                      if cr else []) + ([dict(name="Analyst desk paper", equity=an["equity"], start=an["start"], started=an["started"])]
                                        if an else []) + ([dict(name="Momentum book paper", equity=mo["equity"], start=mo["start"], started=mo["started"])]
                                                          if mo else [])
    ld = leads(mo, cr, an, accts, now, ledger=jload(LEADS_DIR / "ledger.json"), wick=jload(WICK_STATE))
    meta = dict(generated=now, btc=prices.get("BTCUSDT"), health=health(), others=oth, mood=mood(), crowd=cr, analyst=an, momentum=mo, leads=ld,
                wallet=wallet_view(),
                accounts=[dict(id=a["id"], started=a["started"], equity=a["equity"], start=a["start"])
                          for a in accts.values()])
    return meta, accts


def pack(obj) -> str:
    return "gz:" + base64.b64encode(gzip.compress(json.dumps(obj, separators=(",", ":")).encode(), 9)).decode()


def push(meta: dict, accts: dict):
    url, tok = os.environ.get("UPSTASH_REDIS_REST_URL"), os.environ.get("UPSTASH_REDIS_REST_TOKEN")
    if not url or not tok:
        sys.exit("UPSTASH_REDIS_REST_URL / UPSTASH_REDIS_REST_TOKEN are not set in this environment")
    cmds = [["SET", ACCT_KEY + k, pack(v)] for k, v in accts.items()] + [["SET", META_KEY, pack(meta)]]
    req = urllib.request.Request(url.rstrip("/") + "/pipeline", data=json.dumps(cmds).encode(), method="POST",
                                 headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        res = json.loads(r.read().decode())
    bad = [x for x in res if isinstance(x, dict) and x.get("error")]
    if bad:
        sys.exit(f"Upstash refused: {bad[0]['error'][:120]}")


def main():
    if "--wallet-check" in sys.argv:                    # deploy/bitget_ro_env.sh: one read-only balance call, three numbers or the error's class name
        w = wallet_view(ttl=0)
        if not w:
            sys.exit("FAILED no BITGET_RO_* key in this environment")
        if w.get("error"):
            sys.exit(f"FAILED {w['error']}")
        print(f"OK equity={w['equity']:.2f} available={w['available']:.2f} margin used={w['used']:.2f}")
        return
    if "--print" in sys.argv:
        meta, accts = build(write=False)
        print(json.dumps(dict(meta=meta, accounts=accts), indent=1))
        sizes = {k: (len(json.dumps(v)), len(pack(v))) for k, v in dict(meta=meta, **accts).items()}
        print("sizes (json, packed):", sizes, file=sys.stderr)
        return
    meta, accts = build(write=True)
    push(meta, accts)


if __name__ == "__main__":
    main()
