"""MARKET BREADTH RECORDER - TICK / ADD / VOLD / TRIN-style breadth of the Nasdaq-100, minute by minute, recorded from 2026-11-22 (VM)

WHY   The user (2026-11-22): "start recording the market breadth from now on, on the VM". Breadth (the exchanges' TICK, ADD, VOLD, TRIN)
      is the one public scalper tool not properly tested on the NASDAQ trader: his_strategy s69 had Nasdaq TICK on 5-minute bars only
      (12 trades), because TradingView keeps ~3 weeks of 1-minute bars. The exchanges' own breadth indices are vendor data, and the free
      TradingView copy may not be pulled by a server. So this records the SAME measures computed from the Nasdaq-100 stocks' own
      1-minute bars (Yahoo Finance's public chart endpoint: 1-minute history for the last ~30 days, pre- and post-market included):
        tick      = stocks whose last 1-minute change was up minus down (a flat minute keeps its last direction, as TICK does)   ~ TICK
        add       = stocks above minus below their previous regular-session close                                           ~ ADD
        vold_min  = that minute's volume of the stocks that rose minus those that fell                                       ~ VOLD's pace
        vold_day  = volume so far today of the stocks above their previous close minus those below                         ~ VOLD
        trin      = (advancers / decliners) / (their volume so far today)                                                    ~ TRIN
      A PROXY of the exchange indices (about 100 big Nasdaq stocks, 1-minute closes instead of every trade); say so wherever it is used.
HOW   Standard library only (the VM's Python 3.10, ~130 MB free; one stock in memory at a time). One run a day (breadth-rec.timer, 02:00
      UTC, after New York's 20:00 post-market close): one request per stock for the last day (range=1d), or the last 5 days when an older
      day is missing; every COMPLETE New York weekday not on disk yet is stored (idempotent; a weekday with no bars is marked empty).
      --backfill takes the last 29 days in 7-day pieces (Yahoo serves 1-minute bars for ~30 days, at most 7 days a request).
        raw bars  strategy_analysis/data/breadth/raw/YYYY-MM-DD.json.gz   (per stock: minute open times UTC, o h l c v, previous close)
        breadth   strategy_analysis/data/breadth/minute/YYYY-MM-DD.csv    (per minute, New York time)
        log       strategy_analysis/data/breadth/breadth_rec.log
      No keys, no accounts, no orders; ~100 requests a day, spaced, under a generic client name.

    python breadth_rec.py                 (the daily run)
    python breadth_rec.py --backfill      (the last 29 days)
    python breadth_rec.py --status
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "strategy_analysis" / "data" / "breadth"
UA = "Mozilla/5.0 (X11; Linux x86_64) breadth-recorder"
URL = "https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval=1m&includePrePost=true&{span}"
PAUSE = 0.4
MIN_STOCKS = 60                        # a day with fewer stocks is a failed fetch, retried next run
REFERENCE = ("QQQ",)                   # stored with the raw bars, left out of the counts
# The Nasdaq-100, approximately as of mid-2026. Membership drift does not matter for a breadth count; a symbol Yahoo no longer serves is
# logged and skipped.
SYMBOLS = (
    "AAPL", "MSFT", "NVDA", "AMZN", "META", "AVGO", "GOOGL", "GOOG", "TSLA", "NFLX", "COST", "PLTR", "AMD", "TMUS", "CSCO", "ASML",
    "AZN", "LIN", "PEP", "INTU", "ISRG", "TXN", "QCOM", "BKNG", "AMGN", "ADBE", "AMAT", "SHOP", "HON", "PDD", "GILD", "ARM", "LRCX",
    "MU", "PANW", "ADP", "CMCSA", "KLAC", "APP", "ADI", "MELI", "VRTX", "SBUX", "INTC", "CRWD", "DASH", "CEG", "MSTR", "ORLY", "CDNS",
    "SNPS", "CTAS", "MDLZ", "MAR", "ABNB", "PYPL", "MRVL", "FTNT", "REGN", "WDAY", "ADSK", "CSX", "AXON", "ROP", "NXPI", "AEP", "CHTR",
    "PCAR", "FAST", "MNST", "PAYX", "IDXX", "ROST", "CPRT", "TTWO", "KDP", "EXC", "BKR", "VRSK", "XEL", "FANG", "CCEP", "ODFL", "EA",
    "CTSH", "GEHC", "DDOG", "KHC", "LULU", "ZS", "TEAM", "CSGP", "TTD", "ON", "DXCM", "BIIB", "CDW", "GFS", "WBD", "MCHP", "MDB", "TRI")
FIELDS = ("minute_ny", "utc", "n_live", "n_traded", "tick", "adv", "dec", "add", "vold_min", "vold_day", "trin")


def paths(data: Path):
    return data / "raw", data / "minute", data / "breadth_rec.log"


def log(data: Path, msg: str):
    line = f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S} UTC  {msg}"
    print(line, flush=True)
    f = paths(data)[2]
    f.parent.mkdir(parents=True, exist_ok=True)
    with f.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def ny_offset_h(t: datetime) -> int:
    """New York's offset from UTC in hours at UTC moment t: -4 from the second Sunday of March 07:00 UTC to the first Sunday of November
    06:00 UTC, else -5 (the US rule since 2007; written out so the VM needs no time-zone database, as analyst.ny_offset_h)."""
    def sunday(month: int, n: int) -> datetime:
        first = datetime(t.year, month, 1, tzinfo=timezone.utc)
        return first + timedelta(days=(6 - first.weekday()) % 7 + 7 * (n - 1))
    return -4 if sunday(3, 2) + timedelta(hours=7) <= t < sunday(11, 1) + timedelta(hours=6) else -5


def ny_local(ts: int) -> datetime:
    """The New York wall-clock time (naive) of a UTC epoch second."""
    u = datetime.fromtimestamp(ts, timezone.utc)
    return (u + timedelta(hours=ny_offset_h(u))).replace(tzinfo=None)


def regular(loc: datetime) -> bool:
    """A minute of the regular session (09:30-15:59 New York)."""
    m = loc.hour * 60 + loc.minute
    return 570 <= m < 960


def fetch(sym: str, span: str):
    """One Yahoo chart result, or None (after 3 tries)."""
    req = urllib.request.Request(URL.format(sym=sym, span=span), headers={"User-Agent": UA})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                d = json.load(r)
            res = (d.get("chart") or {}).get("result") or []
            return res[0] if res else None
        except urllib.error.HTTPError as e:
            if e.code in (400, 404, 422):                            # bad symbol / range older than Yahoo keeps: no retry
                return None
            time.sleep(5 * (attempt + 1))
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            time.sleep(5 * (attempt + 1))
    return None


def split_days(res: dict) -> dict:
    """{New York date: {'pc': previous regular close, 't','o','h','l','c','v': lists}} from one chart result. The first day's previous
    close is the result's chartPreviousClose; later days' the last regular-session close of the day before in the same result."""
    ts = res.get("timestamp") or []
    q = ((res.get("indicators") or {}).get("quote") or [{}])[0]
    cols = {k: q.get(k) or [] for k in ("open", "high", "low", "close", "volume")}
    days: dict = {}
    for i, t in enumerate(ts):
        vals = [cols[k][i] if i < len(cols[k]) else None for k in ("open", "high", "low", "close", "volume")]
        if vals[3] is None:
            continue
        loc = ny_local(int(t))
        rec = days.setdefault(loc.strftime("%Y-%m-%d"), {"t": [], "o": [], "h": [], "l": [], "c": [], "v": [], "reg_close": None})
        o, h, l, c, v = vals
        rec["t"].append(int(t)); rec["o"].append(o if o is not None else c); rec["h"].append(h if h is not None else c)
        rec["l"].append(l if l is not None else c); rec["c"].append(c); rec["v"].append(v or 0)
        if regular(loc):
            rec["reg_close"] = c
    prev = (res.get("meta") or {}).get("chartPreviousClose")
    out = {}
    for day in sorted(days):
        rec = days[day]
        rec["pc"] = prev
        if rec["reg_close"] is not None:
            prev = rec["reg_close"]
        del rec["reg_close"]
        out[day] = rec
    return out


def breadth(stocks: dict) -> list:
    """Minute rows (FIELDS) of one New York day from {symbol: day record}. Cumulative day volumes restart at 04:00 and at 09:30."""
    minutes = sorted({t for s in stocks.values() for t in s["t"]})
    bar = {sym: dict(zip(s["t"], zip(s["c"], s["v"]))) for sym, s in stocks.items()}
    last, state, cum_vol = {}, {}, {}
    rows, session = [], None
    for t in minutes:
        loc = ny_local(t)
        sess = "regular" if regular(loc) else ("pre" if loc.hour * 60 + loc.minute < 570 else "post")
        if sess != session and sess in ("pre", "regular"):
            cum_vol = {}
        session = sess
        traded = 0
        vup = vdn = 0.0
        for sym, b in bar.items():
            x = b.get(t)
            if x is None:
                continue
            c, v = x
            traded += 1
            p = last.get(sym)
            if p is not None and c != p:
                state[sym] = 1 if c > p else -1
                if c > p:
                    vup += v
                else:
                    vdn += v
            last[sym] = c
            cum_vol[sym] = cum_vol.get(sym, 0.0) + v
        adv = dec = 0
        adv_vol = dec_vol = 0.0
        for sym, c in last.items():
            pc = stocks[sym].get("pc")
            if pc is None or c == pc:
                continue
            if c > pc:
                adv += 1
                adv_vol += cum_vol.get(sym, 0.0)
            else:
                dec += 1
                dec_vol += cum_vol.get(sym, 0.0)
        trin = (adv / dec) / (adv_vol / dec_vol) if dec and adv_vol > 0 and dec_vol > 0 else ""
        rows.append({"minute_ny": loc.strftime("%H:%M"), "utc": t, "n_live": len(last), "n_traded": traded,
                     "tick": sum(state.values()), "adv": adv, "dec": dec, "add": adv - dec, "vold_min": vup - vdn,
                     "vold_day": adv_vol - dec_vol, "trin": round(trin, 4) if trin != "" else ""})
    return rows


def complete_days(now: datetime, back: int) -> list:
    """New York weekdays of the last `back` days whose sessions are over (before today in New York, or today after 20:05)."""
    loc = now + timedelta(hours=ny_offset_h(now))
    out = []
    for k in range(back, -1, -1):
        d = (loc - timedelta(days=k)).date()
        if d.weekday() >= 5:
            continue
        if d < loc.date() or (d == loc.date() and loc.hour * 60 + loc.minute >= 20 * 60 + 5):
            out.append(d.isoformat())
    return out


def stored(data: Path, day: str) -> bool:
    mn = paths(data)[1]
    return (mn / f"{day}.csv").exists() or (mn / f"{day}.empty").exists()


def collect(data: Path, spans: list, want: set, symbols) -> dict:
    """Fetch every symbol over the spans; stream each stock's wanted days to per-day temp files. Returns {day: stocks written}."""
    tmp = data / "tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    for f in tmp.glob("*.jsonl"):
        f.unlink()
    count: dict = {}
    failed = []
    for sym in tuple(symbols) + REFERENCE:
        got = False
        for span in spans:
            res = fetch(sym, span)
            time.sleep(PAUSE)
            if not res:
                continue
            got = True
            for day, rec in split_days(res).items():
                if day not in want:
                    continue
                with (tmp / f"{day}.jsonl").open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps({"sym": sym, **rec}) + "\n")
                if sym not in REFERENCE:
                    count[day] = count.get(day, 0) + 1
        if not got:
            failed.append(sym)
    if failed:
        log(data, f"no data for {len(failed)} symbols: {' '.join(failed)}")
    return count, len(tuple(symbols)) - len([f for f in failed if f not in REFERENCE])


def merge(recs: list) -> dict:
    """{symbol: day record} from the temp lines, merging a symbol that came in more than one piece (sorted by time, no repeats; the
    previous close from the earliest piece that has one)."""
    out: dict = {}
    for r in recs:
        k = r["sym"]
        if k not in out:
            out[k] = {f: r[f] for f in ("pc", "t", "o", "h", "l", "c", "v")}
            continue
        a = out[k]
        if a["pc"] is None:
            a["pc"] = r["pc"]
        rows = dict(zip(a["t"], zip(a["o"], a["h"], a["l"], a["c"], a["v"])))
        for i, t in enumerate(r["t"]):
            rows.setdefault(t, (r["o"][i], r["h"][i], r["l"][i], r["c"][i], r["v"][i]))
        ts = sorted(rows)
        a["t"] = ts
        for j, f in enumerate(("o", "h", "l", "c", "v")):
            a[f] = [rows[t][j] for t in ts]
    return out


def write_days(data: Path, want: list, count: dict, now: datetime, min_stocks: int = MIN_STOCKS):
    raw, mn, _ = paths(data)
    raw.mkdir(parents=True, exist_ok=True)
    mn.mkdir(parents=True, exist_ok=True)
    tmp = data / "tmp"
    for day in want:
        f = tmp / f"{day}.jsonl"
        n = count.get(day, 0)
        if n == 0:
            (mn / f"{day}.empty").write_text(f"no bars for any stock, checked {now:%Y-%m-%d %H:%M} UTC\n", encoding="utf-8")
            log(data, f"{day}: no bars (a market holiday) - marked empty")
            continue
        if n < min_stocks:
            log(data, f"{day}: only {n} stocks - not stored, retried next run")
            continue
        recs = [json.loads(line) for line in f.read_text(encoding="utf-8").splitlines() if line.strip()]
        stocks = merge(recs)
        rows = breadth({k: v for k, v in stocks.items() if k not in REFERENCE})
        with gzip.open(raw / f"{day}.json.gz", "wt", encoding="utf-8") as fh:
            json.dump({"source": "Yahoo Finance v8 chart, 1-minute, pre/post included", "fetched_utc": f"{now:%Y-%m-%d %H:%M:%S}",
                       "stocks": stocks}, fh)
        with (mn / f"{day}.csv").open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=FIELDS)
            w.writeheader()
            w.writerows(rows)
        reg = [r for r in rows if "09:30" <= r["minute_ny"] < "16:00"]
        log(data, f"{day}: {n} stocks, {len(rows)} minutes ({len(reg)} regular); tick {min(r['tick'] for r in reg) if reg else '-'} .. "
                  f"{max(r['tick'] for r in reg) if reg else '-'}; add at the close {reg[-1]['add'] if reg else '-'}")
    for f in tmp.glob("*.jsonl"):
        f.unlink()


def run(data: Path = DATA, backfill: bool = False, now: datetime | None = None, symbols=SYMBOLS):
    now = now or datetime.now(timezone.utc)
    days = complete_days(now, 29 if backfill else 6)               # 6 back = 7 calendar days: at most 5 weekdays, one range=5d request
    want = [d for d in days if not stored(data, d)]
    if not want:
        log(data, "nothing new")
        return
    if backfill:
        spans = backfill_spans(now)
    else:
        spans = ["range=1d" if want == days[-1:] else "range=5d"]
    log(data, f"fetching {len(symbols)} stocks for {len(want)} day(s): {want[0]} .. {want[-1]} ({len(spans)} request(s) each)")
    min_stocks = max(1, min(MIN_STOCKS, int(0.6 * len(symbols))))
    count, answered = collect(data, spans, set(want), symbols)
    if answered < min_stocks:                                      # Yahoo or the network failed: mark nothing, retry next run
        log(data, f"only {answered} of {len(symbols)} stocks answered - nothing stored")
        for f in (data / "tmp").glob("*.jsonl"):
            f.unlink()
        return
    write_days(data, want, count, now, min_stocks)


def backfill_spans(now: datetime) -> list:
    """period1 / period2 pieces of at most 7 days covering the last 29 New York days, cut at New York midnight so no session splits."""
    loc = now + timedelta(hours=ny_offset_h(now))
    start = (loc - timedelta(days=29)).date()
    edges = []
    for k in range(0, 36, 7):
        d = start + timedelta(days=k)
        mid = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
        edges.append(int((mid - timedelta(hours=ny_offset_h(mid + timedelta(hours=12)))).timestamp()))
    end = int(now.timestamp())
    edges = [e for e in edges if e < end] + [end]
    return [f"period1={a}&period2={b}" for a, b in zip(edges[:-1], edges[1:])]


def status(data: Path = DATA):
    _, mn, _ = paths(data)
    days = sorted(f.stem for f in mn.glob("*.csv")) if mn.exists() else []
    empty = sorted(f.stem for f in mn.glob("*.empty")) if mn.exists() else []
    print(f"breadth days stored: {len(days)}" + (f" ({days[0]} .. {days[-1]})" if days else "") + (f"; empty: {', '.join(empty)}" if empty else ""))
    if days:
        with (mn / f"{days[-1]}.csv").open(encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        reg = [r for r in rows if "09:30" <= r["minute_ny"] < "16:00"]
        if reg:
            ticks = [int(r["tick"]) for r in reg]
            print(f"  {days[-1]}: {len(rows)} minutes ({len(reg)} regular), stocks live {reg[-1]['n_live']}, tick {min(ticks)} .. {max(ticks)}, "
                  f"add at the close {reg[-1]['add']}, vold_day {float(reg[-1]['vold_day']):,.0f}")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--backfill", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--data", default=str(DATA), help="data folder (tests / trials)")
    ap.add_argument("--symbols", default="", help="comma-separated subset (trials)")
    a = ap.parse_args(argv)
    data = Path(a.data)
    if a.status:
        status(data)
        return
    run(data, backfill=a.backfill, symbols=tuple(s for s in a.symbols.split(",") if s) or SYMBOLS)


if __name__ == "__main__":
    main()
