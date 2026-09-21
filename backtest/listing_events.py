"""LISTING ANNOUNCEMENTS - is there anything left for a trader who is not first?

THE IDEA
    When a big exchange announces it will list a coin that already trades elsewhere, the
    coin gets a demand shock from a new user base. Upbit (Korea's largest exchange) is the
    famous case: its KRW listing notices have moved coins 30-100% within minutes, on every
    venue, because Korean retail money arrives all at once.

    The fastest bots react in milliseconds. A home setup polling an announcement feed reacts
    in seconds and fills within a minute or so. So the only question worth testing is
    whether the move CONTINUES after the first minutes - whether a late entry still earns.

THE DATA, ALL FREE
    Announcements: Upbit's notice API (777 trade notices back to 2017, with the ORIGINAL
    posting time in first_listed_at, not the time of later edits) and Binance's CMS
    catalog 48 (2,263 listing articles, releaseDate to the millisecond).
    Prices: Binance's 1-minute archive (data.binance.vision), which keeps dead coins. So
    every event is measured on Binance, for coins that ALREADY traded there:
      UPBIT_KRW   Upbit adds a coin to its KRW market; price measured on Binance.
      BN_SPOT     Binance announces SPOT listing of a coin whose Binance PERP already
                  trades (perp-first listings, common since 2023); measured on the perp.
      BN_PERP     Binance Futures announces a perp for a coin already on Binance spot;
                  measured on spot. (backtest/bear_shorts.py found these coins fall over
                  the following month; this checks the announcement minute itself.)

WHAT IS MEASURED
    Entry at the OPEN of the minute that starts `delay` whole minutes after the
    announcement (delay 0 = the first minute that begins after it - realistic for a
    poller that reacts inside a minute; the fastest bots got in before that). Exits at
    +15m, +1h, +4h, +24h, +72h after entry. Costs: 10bp taker round trip, plus a slippage
    stress column at 50bp total, because a book in a listing pump is thin.

    Also the 60 minutes BEFORE each announcement, to see whether the information leaks.

    Events in the same week share a market, so t-statistics are over EVENTS but the
    headline is also shown by year - an effect like this decays as more bots arrive, and
    only the recent years describe what is available now.

    python -m backtest.listing_events
"""
from __future__ import annotations

import io
import json
import re
import sys
import time
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "strategy_analysis" / "data" / "listings"
MIN1 = OUT / "min1"
BASE = "https://data.binance.vision"
DELAYS = (0, 1, 2, 5, 15)
HORIZONS = {"15m": 15, "1h": 60, "4h": 240, "24h": 1440, "72h": 4320}
FEE, STRESS = 10 / 1e4, 50 / 1e4


def get_json(u, tries=4):
    for a in range(tries):
        try:
            r = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
            return json.load(urllib.request.urlopen(r, timeout=40))
        except Exception:
            if a == tries - 1:
                raise
            time.sleep(2 * (a + 1))


# ---- announcements -----------------------------------------------------------------
def upbit_notices():
    f = OUT / "upbit_notices.json"
    if f.exists():
        return json.load(open(f, encoding="utf-8"))
    out, page = [], 1
    while True:
        d = get_json("https://api-manager.upbit.com/api/v1/announcements?os=web"
                     f"&page={page}&per_page=20&category=trade")["data"]
        out += d["notices"]
        if page >= d["total_pages"]:
            break
        page += 1
        time.sleep(0.3)
    OUT.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(f, "w", encoding="utf-8"), ensure_ascii=False)
    return out


def binance_articles():
    f = OUT / "binance_cms48.json"
    if f.exists():
        return json.load(open(f, encoding="utf-8"))
    out, page = [], 1
    while True:
        d = get_json("https://www.binance.com/bapi/composite/v1/public/cms/article/list/"
                     f"query?type=1&catalogId=48&pageNo={page}&pageSize=50")
        cats = (d.get("data") or {}).get("catalogs") or []
        arts = cats[0]["articles"] if cats else []
        if not arts:
            break
        out += [{"t": a["releaseDate"], "title": a["title"]} for a in arts]
        page += 1
        time.sleep(0.3)
    json.dump(out, open(f, "w", encoding="utf-8"), ensure_ascii=False)
    return out


TICK = re.compile(r"\(([A-Z0-9]{2,12})\)")


def events():
    ev = []
    for n in upbit_notices():
        t = n.get("first_listed_at") or n.get("listed_at")
        title = n["title"]
        if not t or any(k in title for k in ("종료", "유의", "연장", "취소", "변경", "입출금")):
            continue
        new = ("신규 거래지원" in title) or ("디지털 자산 추가" in title) or \
              ("원화 마켓" in title and any(k in title for k in ("상장", "오픈", "추가")))
        krw = ("KRW" in title) or ("원화" in title)
        if not (new and krw):
            continue
        ts = pd.Timestamp(t).tz_convert("UTC").tz_localize(None)
        for tk in TICK.findall(title):
            ev.append(dict(kind="UPBIT_KRW", t=ts, coin=tk, title=title))
    for a in binance_articles():
        ts = pd.Timestamp(a["t"], unit="ms")
        title = a["title"]
        if title.startswith("Binance Will List"):
            for tk in TICK.findall(title):
                ev.append(dict(kind="BN_SPOT", t=ts, coin=tk, title=title))
        m = re.search(r"Will Launch USD.-M(?:argined)? ([A-Z0-9]+)USDT Perpetual", title)
        if m and "TradFi" not in title:
            ev.append(dict(kind="BN_PERP", t=ts, coin=m.group(1), title=title))
    e = pd.DataFrame(ev).drop_duplicates(["kind", "coin"]).sort_values("t")
    return e.reset_index(drop=True)


# ---- 1-minute prices -----------------------------------------------------------------
def day_1m(market, sym, day):
    """One UTC day of 1m bars from the archive, cached. market: 'spot' or 'um'."""
    MIN1.mkdir(parents=True, exist_ok=True)
    f = MIN1 / f"{market}_{sym}_{day}.csv.gz"
    if f.exists():
        d = pd.read_csv(f)
        return d if len(d) else None
    path = (f"data/spot/daily/klines/{sym}/1m/{sym}-1m-{day}.zip" if market == "spot"
            else f"data/futures/um/daily/klines/{sym}/1m/{sym}-1m-{day}.zip")
    try:
        with urllib.request.urlopen(urllib.request.Request(
                f"{BASE}/{path}", headers={"User-Agent": "research"}), timeout=40) as r:
            z = zipfile.ZipFile(io.BytesIO(r.read()))
        raw = z.open(z.namelist()[0]).read().decode()
        rows = [x.split(",") for x in raw.strip().splitlines()]
        if rows and not rows[0][0].isdigit():
            rows = rows[1:]
        t0 = int(rows[0][0])
        div = 1000 if t0 > 10**14 else 1          # 2025+ spot files are in microseconds
        d = pd.DataFrame({"t": [int(x[0]) // div for x in rows],
                          "o": [float(x[1]) for x in rows], "h": [float(x[2]) for x in rows],
                          "l": [float(x[3]) for x in rows], "c": [float(x[4]) for x in rows]})
    except Exception:
        d = pd.DataFrame(columns=["t", "o", "h", "l", "c"])
    d.to_csv(f, index=False, compression="gzip")
    return d if len(d) else None


def window(market, sym, t):
    """1m bars from 1 day before to 4 days after t, or None if the coin was not
    trading on this market BEFORE the announcement."""
    days = [(t + pd.Timedelta(days=k)).strftime("%Y-%m-%d") for k in (-1, 0, 1, 2, 3, 4)]
    parts = [day_1m(market, sym, d) for d in days]
    parts = [p for p in parts if p is not None]
    if not parts:
        return None
    d = pd.concat(parts).drop_duplicates("t").sort_values("t").reset_index(drop=True)
    d["time"] = pd.to_datetime(d.t, unit="ms")
    if not (d.time < t - pd.Timedelta(minutes=60)).any():
        return None                                # not trading before the news
    return d.set_index("time")


def measure(ev):
    kind, t, coin = ev["kind"], ev["t"], ev["coin"]
    order = {"UPBIT_KRW": ("spot", "um"), "BN_SPOT": ("um",), "BN_PERP": ("spot",)}[kind]
    for mkt in order:
        for sym in (f"{coin}USDT", f"1000{coin}USDT"):
            d = window(mkt, sym, t)
            if d is None:
                continue
            first = t.ceil("min")
            if t == first:
                first = t + pd.Timedelta(minutes=1)
            pre = d.loc[:t - pd.Timedelta(minutes=1)]
            pre60 = d.loc[t - pd.Timedelta(minutes=60):t - pd.Timedelta(minutes=1)]
            row = dict(kind=kind, t=t, coin=coin, market=mkt, sym=sym)
            if len(pre60) >= 30 and len(pre):
                row["pre60"] = pre.c.iloc[-1] / pre60.o.iloc[0] - 1
                ref = pre.c.iloc[-1]                   # last price before the news
            else:
                continue
            row["peak60"] = d.loc[t:t + pd.Timedelta(minutes=60)].h.max() / ref - 1
            for dl in DELAYS:
                te = first + pd.Timedelta(minutes=dl)
                if te not in d.index:
                    continue
                e = d.at[te, "o"]
                row[f"chase_d{dl}"] = e / ref - 1       # how much was already gone
                for hn, hm in HORIZONS.items():
                    tx = te + pd.Timedelta(minutes=hm)
                    sub = d.loc[:tx]
                    if sub.index[-1] < tx - pd.Timedelta(minutes=5):
                        continue
                    row[f"d{dl}_{hn}"] = sub.c.iloc[-1] / e - 1
            return row
    return None


def show(E, kind):
    x = E[E.kind == kind]
    if len(x) < 10:
        print(f"\n  {kind}: {len(x)} usable events - too few")
        return
    print(f"\n  {kind}: {len(x)} usable events ({x.t.min():%Y-%m} .. {x.t.max():%Y-%m})")
    print(f"    60 min BEFORE the notice: mean {x.pre60.mean()*100:+.2f}%  "
          f"median {x.pre60.median()*100:+.2f}%   (leak check)")
    print(f"    peak within 60 min of the notice, vs last price before it: "
          f"median {x.peak60.median()*100:+.1f}%, mean {x.peak60.mean()*100:+.1f}%")
    print(f"    {'entry':<9}{'already gone':>13} |" +
          "".join(f"{h:>15}" for h in HORIZONS) + "      (net of 10bp; [50bp stress])")
    for dl in DELAYS:
        c = f"chase_d{dl}"
        if c not in x:
            continue
        line = f"    +{dl:>2} min  {x[c].median()*100:>+11.1f}% |"
        for hn in HORIZONS:
            k = f"d{dl}_{hn}"
            if k not in x or x[k].notna().sum() < 10:
                line += f"{'':>15}"; continue
            r = x[k].dropna()
            net, st = r.mean() - FEE, r.mean() - STRESS
            t = r.mean() / (r.std(ddof=1) / np.sqrt(len(r))) if len(r) > 2 else np.nan
            line += f"{net*100:>+7.2f}[{st*100:+.1f}]{'*' if abs(t) > 2 else ' '}"
        print(line)
    print("    * |t| > 2 over events.  By year, entry +1 min, exit +1h and +24h (mean, net 10bp):")
    for y in sorted(x.t.dt.year.unique()):
        z = x[x.t.dt.year == y]
        a = z.get("d1_1h", pd.Series(dtype=float)).dropna()
        b = z.get("d1_24h", pd.Series(dtype=float)).dropna()
        if len(a) < 3:
            continue
        print(f"      {y}: n={len(a):>3}  1h {a.mean()*100-FEE*100:+6.2f}% "
              f"(win {np.mean(a > FEE)*100:3.0f}%)   24h {b.mean()*100-FEE*100:+6.2f}% "
              f"(win {np.mean(b > FEE)*100:3.0f}%)   peak60 med "
              f"{z.peak60.median()*100:+5.1f}%")


def main():
    ev = events()
    print(f"announcements parsed: " + ", ".join(f"{k} {v}" for k, v in
                                              ev.kind.value_counts().items()))
    rows = []
    with ThreadPoolExecutor(12) as ex:
        for k, r in enumerate(ex.map(measure, ev.to_dict("records"))):
            if r:
                rows.append(r)
            if (k + 1) % 100 == 0:
                print(f"  {k + 1}/{len(ev)} events checked, {len(rows)} usable", flush=True)
    E = pd.DataFrame(rows)
    E.to_pickle(OUT / "events_measured.pkl")
    print(f"{len(E)} events had the coin trading on Binance before the announcement")
    for kind in ("UPBIT_KRW", "BN_SPOT", "BN_PERP"):
        show(E, kind)


if __name__ == "__main__":
    main()
