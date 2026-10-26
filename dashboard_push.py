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
            "crowd-paper.timer", "analyst-paper.timer"]
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

def open_positions(st: dict, prices: dict) -> list:
    rows = []

    def add(book, sym, qty, entry, mark, upnl, since, note=""):
        cost = abs(qty) * entry if entry else 0.0
        rows.append(dict(book=book, sym=sym, side="long" if qty > 0 else "short", qty=qty,
                         size=round(abs(qty) * (mark or entry or 0.0), 2), entry=entry, mark=mark,
                         upnl=None if upnl is None else round(upnl, 4),
                         pct=None if upnl is None or not cost else round(upnl / cost, 5), since=since, note=note))

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

    def basket(book, b, note):
        for s, w in (b.get("weights", {}) or {}).items():
            p0 = (b.get("mark_px", {}) or {}).get(s)
            if not p0:
                continue
            qty = b.get("base", 0.0) * w / p0
            m = price(prices, s)
            add(book, s, qty, p0, m, qty * (m - p0) if m else None, b.get("last_rebal"), note)

    basket("mn", st.get("mn", {}) or {}, "weekly basket, booked daily (entry = last daily mark)")
    fin = st.get("fin", {}) or {}
    basket("carry", fin.get("carry", {}) or {}, "funding basket, booked daily (entry = last daily mark)")
    sl = st.get("sleeve", {}) or {}
    for s, n in (sl.get("hold", {}) or {}).items():
        p0 = (sl.get("mark_px", {}) or {}).get(s)
        if p0:
            m = price(prices, s)
            add("sleeve", s, n / p0, p0, m, n * (m / p0 - 1) if m else None, None, "bear basket, booked daily")
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
                what_if=dict(live=slim_grid(an.grid(rows)), replay=replay_view(jload(ANALYST_REPLAY))),
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
    oth = others() + ([dict(name="Crowd squeeze paper", equity=cr["equity"], start=cr["start"], started=cr["started"])]
                      if cr else []) + ([dict(name="Analyst desk paper", equity=an["equity"], start=an["start"], started=an["started"])]
                                        if an else [])
    meta = dict(generated=now, btc=prices.get("BTCUSDT"), health=health(), others=oth, mood=mood(), crowd=cr, analyst=an,
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
