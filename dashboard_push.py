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
SERVICES = ["combo-bot-final", "combo-bot-fresh", "combo-paper", "blend-paper", "wick-paper", "pair-paper"]
# combo-bot-demo was stopped 2026-10-17 at the user's word: its order-path test was done (191 orders over 16.9 days, all
# filled and priced, 0 failures; logs/combo_bot_demo/final_report_20261017.txt on the VM)
START_EQUITY = 300.0
GROSS_CAP = 14.5
META_KEY, ACCT_KEY = "forexbot:meta", "forexbot:acct:"
CLOSED_KEEP, NEWS_KEEP = 120, 30


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
    rows.sort(key=lambda r: -abs(r["upnl"] or 0.0))
    return rows


# ------------------------------------------------------------------ closed trades

def closed_trades(d: Path) -> list:
    out = []
    for r in read_csv(d / "combo_final_trades.csv"):
        entry, exit_, ret, pnl = fnum(r.get("entry")), fnum(r.get("exit")), fnum(r.get("ret")), fnum(r.get("pnl"))
        out.append(dict(ts=r.get("ts"), book=r.get("book"), sym=r.get("symbol"),
                        side="short" if r.get("book") == "news" else "long", entry=entry, exit=exit_, pct=ret,
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


# ------------------------------------------------------------------ one account

def account(acct: str, d: Path, prices: dict, now: int, write: bool) -> dict | None:
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
             for b in ("trend", "mn", "carry", "sleeve", "daily", "capit2", "news", "ndx")}
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
        pending=dict(capit2=len((fin.get("capit2", {}) or {}).get("pending", {}) or {}),
                     news=len(news.get("pending", {}) or {})),
        news=dict(recent=list(reversed((news.get("recent") or [])[-NEWS_KEEP:])), seen=news.get("seen", 0),
                  taken=news.get("taken", 0), dropped=news.get("dropped", 0)))


# ------------------------------------------------------------------ everything else (meta)

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
    accts = {}
    for acct, d in ACCOUNTS:
        a = account(acct, d, prices, now, write)
        if a:
            accts[acct] = a
    meta = dict(generated=now, btc=prices.get("BTCUSDT"), health=health(), others=others(),
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
