"""MARKET MOOD, NOW - a read-only readout of the crypto sentiment measures that held up (2026-10-23)

THE USER (2026-10-23): "we need to make better sentiment analysis tool ... add all the good stuff, also work on getting
news from X". What the history says is worth showing (news/impact_by_source.py, news/positioning_hist.py, news/bsky_hist.py):
  CROWD    Binance's long / short ACCOUNT ratio per perp, ranked across the backtest's universe (the top 40 by the prior
           month's volume, listed >= 30 days; cached once a month in mood_pool.json). The coins the crowd is
           most SHORT out-earned the most LONG by +37..+48%/yr over 2022-26 (t 1.8-2.0 - a LEAD, not a pass): ~40% of it
           funding paid to the longs, the rest short squeezes in small coins. The bottom quarter is flagged SQUEEZE WATCH;
           news/crowd_paper.py runs that book on paper.
  FUNDING  the last settlement, annualised (fundingInfo for 4h / 1h coins): who pays whom; the carry book trades it.
  TAKER    aggressive buy / sell volume, mean of the last 24h of 5-minute rows: a weak momentum read (IC +0.05..+0.06),
           no book in either direction (logs/positioning_hist.txt, logs/positioning_taker_follow.txt).
  OI 7D    open interest value now / 7 days ago - 1: predicts nothing; shown because it says where leverage builds.
  FEAR & GREED  alternative.me, market-wide: weekly momentum, but no use as a size dial (doc 02, 2026-10-05).
Checked 2026-10-23: the live endpoints give the archive's numbers (BTC crowd 1.0239 vs 1.0237 at 2026-10-21 23:50, SOL
taker 1.0812 vs 1.0812), so the readout shows the same quantities the backtest ranked.
LEFT OUT, measured dead: Bluesky chatter and tone (bsky_hist.py), top traders' positions, general news tone (news/tone.py).
NOT HERE: exchange notices - Binance adds_products / monitoring tags are the news book's job on the VM (news_books.py);
t.me does not load from this PC. X / Twitter: no free legal feed (the official API and LunarCrush are paid); nothing scraped.

STANDARD LIBRARY ONLY: it runs hourly on the VM (deploy/crowd-paper.*, via news/crowd_paper.py), which has ~50 MB free.
NON_CRYPTO and MIN_AGE_D are copies of backtest.market_neutral / backtest.wide_book's (tests/test_mood_now.py asserts it).

Public Binance endpoints only, no keys, no orders. INFORMATION, NOT A TRADE SIGNAL: doc 22 freezes new books.
    python -m news.mood_now            (table)
    python -m news.mood_now --json     (the snapshot, as the dashboard gets it)
"""
from __future__ import annotations

import json
import math
import statistics
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FAPI = "https://fapi.binance.com"
POOL = ROOT / "strategy_analysis" / "data" / "news" / "mood_pool.json"     # {month: top perps by last month's volume}
TOP_N = 40
SQUEEZE_Q, LONG_Q = 0.25, 0.75                       # the crowd book's quarters (positioning_hist.quarters)
NON_CRYPTO = {"PAXG", "XAUT", "EUR", "GBP", "AEUR", "USDC", "TUSD", "BUSD", "FDUSD",
              "USDP", "DAI", "USD1", "USDE", "SUSDE"}
MIN_AGE_D = 30
DAY_MS = 86_400_000


def get(u: str):
    for k in range(3):
        try:
            return json.load(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}),
                                                    timeout=30))
        except Exception:  # noqa: BLE001
            if k == 2:
                raise
            time.sleep(1 + 2 * k)


def utc(ms: int) -> datetime:
    return datetime.fromtimestamp(ms / 1000, timezone.utc)


def universe(n: int = TOP_N, now: datetime | None = None) -> list[str]:
    """THE BACKTEST'S UNIVERSE (drop_non_crypto(wide_book.eligibility(40))): every USDT perp listed >= MIN_AGE_D days at
    the month's start, ranked by the PRIOR calendar month's quote volume, the top n kept, then the stables / gold
    dropped - in that order, as the backtest does. Fixed for the month and cached. Today's 24h volume would let in the
    week's new listings (IRYS, MAGMA, BIRB on 2026-10-23), which the crowd book never ranked."""
    now = now or datetime.now(timezone.utc)
    month = now.strftime("%Y-%m")
    mstart = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
    prev = (mstart - timedelta(days=1)).strftime("%Y-%m")
    saved = json.loads(POOL.read_text()) if POOL.exists() else {}
    if month in saved:
        return saved[month][:n]
    info = [s["symbol"] for s in get(f"{FAPI}/fapi/v1/exchangeInfo")["symbols"]
            if s.get("contractType") == "PERPETUAL" and s.get("status") == "TRADING" and s.get("quoteAsset") == "USDT"
            and (mstart - utc(s["onboardDate"])).days >= MIN_AGE_D]

    def qvol(sym):
        try:
            k = get(f"{FAPI}/fapi/v1/klines?symbol={sym}&interval=1d&limit=65")
        except Exception:  # noqa: BLE001
            return sym, None
        return sym, sum(float(b[7]) for b in k if utc(b[0]).strftime("%Y-%m") == prev)
    with ThreadPoolExecutor(8) as ex:
        got = dict(ex.map(qvol, info))
    vol = {s: v for s, v in got.items() if v is not None}
    if len(vol) < 0.9 * len(info):
        raise RuntimeError(f"universe: read {len(vol)} of {len(info)} perps - try again")
    top = sorted(vol, key=lambda s: -vol[s])[:n]
    saved[month] = [s for s in top if s[:-4] not in NON_CRYPTO]
    POOL.parent.mkdir(parents=True, exist_ok=True)
    POOL.write_text(json.dumps(saved))
    return saved[month]


def funding() -> dict[str, float]:
    """Last funding rate per symbol, annualised in %."""
    hours = {f["symbol"]: float(f["fundingIntervalHours"]) for f in get(f"{FAPI}/fapi/v1/fundingInfo")}
    return {p["symbol"]: float(p["lastFundingRate"]) * (24 / hours.get(p["symbol"], 8.0)) * 365 * 100
            for p in get(f"{FAPI}/fapi/v1/premiumIndex")}


def crowd_at(sym: str, at_ms: int | None = None):
    """The crowd's long / short account ratio and long share: the latest 5-minute row, or the last one BEFORE at_ms
    (Binance keeps 30 days). The backtest read the archive day's last row (23:45 / 23:50); this reads 23:55."""
    q = f"{FAPI}/futures/data/globalLongShortAccountRatio?symbol={sym}&period=5m&limit=1"
    g = get(q + (f"&endTime={at_ms - 1}" if at_ms else ""))
    return (float(g[0]["longShortRatio"]), float(g[0]["longAccount"])) if g else (None, None)


def coin(sym: str) -> dict:
    q = f"symbol={sym}&period=5m"
    crowd, long_share = crowd_at(sym)
    tk = get(f"{FAPI}/futures/data/takerlongshortRatio?{q}&limit=288")
    oi = get(f"{FAPI}/futures/data/openInterestHist?symbol={sym}&period=1d&limit=8")
    o = [float(x["sumOpenInterestValue"]) for x in oi]
    return dict(sym=sym, crowd=crowd, long_share=long_share,
                taker=statistics.fmean(float(x["buySellRatio"]) for x in tk) if tk else None,
                oi7=(o[-1] / o[0] - 1) if len(o) >= 8 and o[0] > 0 else None)


def pct_rank(vals: dict) -> dict:
    """pandas Series.rank(pct=True): ranks 1..n over the values, ties sharing their mean rank, divided by n."""
    items = sorted(vals.items(), key=lambda kv: kv[1])
    n, out, i = len(items), {}, 0
    while i < n:
        j = i
        while j + 1 < n and items[j + 1][1] == items[i][1]:
            j += 1
        for k in range(i, j + 1):
            out[items[k][0]] = (i + j + 2) / 2 / n
        i = j + 1
    return out


def rank(rows: list[dict], fund: dict[str, float]) -> list[dict]:
    """Rank the crowd across the coins and flag the crowd book's quarters; most short first."""
    ok = {r["sym"]: r["crowd"] for r in rows if r["crowd"] is not None and math.isfinite(r["crowd"])}
    pr = pct_rank(ok)
    out = []
    for r in rows:
        p = pr.get(r["sym"])
        out.append(dict(r, fund_yr=fund.get(r["sym"]), crowd_pct=p,
                        flag="" if p is None else "SQUEEZE WATCH" if p <= SQUEEZE_Q else "crowd long" if p >= LONG_Q else ""))
    return sorted(out, key=lambda r: (r["crowd_pct"] is None, r["crowd_pct"] or 0.0))


def fear_greed():
    try:
        d = get("https://api.alternative.me/fng/?limit=1")["data"][0]
        return int(d["value"]), d["value_classification"]
    except Exception:  # noqa: BLE001
        return None, "unavailable"


FUEL_BANDS = ROOT / "news" / "fuel_bands.json"       # 2020-09..2026-09 history of the three readings (backtest/convexity.py --bands)
RUNNER_UP = 0.20                                      # "running" = up more than 20% over 30 days


def pct_in(value: float, q: list) -> float:
    """Share of the stored 0..100 quantile grid strictly below value, in percent (0 = lowest ever seen, 100 = highest)."""
    return 100.0 * sum(1 for x in q if x < value) / len(q)


def fuel(syms: list[str], bands: dict | None = None) -> dict | None:
    """THE TREND BOOK'S FUEL (backtest/convexity.py, doc 02 2026-10-27): the machine's profit comes in a few explosive alt
    months, and the trend book earns after months when many coins were already running - by the previous month-end's tercile of
    the RUNNER SHARE its next month averaged -0.5% (lowest third), +3.0%, +69.4% (highest third). Read-only; information, not a signal.
    runners = share of the coins (BTC out) up more than 20% over 30 days to the last CLOSED day; med = their median 30-day move;
    disp = the spread (population sd) of the 30-day moves. The `_pct` fields place each in the 2020-2026 history."""
    def one(s):
        k = get(f"{FAPI}/fapi/v1/klines?symbol={s}&interval=1d&limit=35")
        return float(k[-2][4]) / float(k[-32][4]) - 1 if len(k) >= 32 else None
    todo = [s for s in syms if s != "BTCUSDT"]
    with ThreadPoolExecutor(8) as ex:
        r30 = [r for r in ex.map(one, todo) if r is not None and math.isfinite(r)]
    if len(r30) < 8:
        return None
    out = dict(n=len(r30), runners=sum(r > RUNNER_UP for r in r30) / len(r30), med=statistics.median(r30), disp=statistics.pstdev(r30))
    if bands is None and FUEL_BANDS.exists():
        bands = json.loads(FUEL_BANDS.read_text())
    if bands:
        for k in ("runners", "med", "disp"):
            out[k + "_pct"] = round(pct_in(out[k], bands["q"][k]), 0)
        lo, hi = bands["q"]["runners"][33], bands["q"]["runners"][67]
        out["state"] = "LOW" if out["runners"] <= lo else "HIGH" if out["runners"] > hi else "MID"
    return out


def snapshot(n: int = TOP_N) -> dict:
    syms = universe(n)
    fund = funding()
    with ThreadPoolExecutor(8) as ex:
        rows = list(ex.map(coin, syms))
    R = rank(rows, fund)
    fg, fg_txt = fear_greed()
    ls = [r["long_share"] for r in R if r["long_share"] is not None]
    fy = [r["fund_yr"] for r in R if r["fund_yr"] is not None]
    btc = next((r["crowd"] for r in R if r["sym"] == "BTCUSDT"), None)
    try:
        fl = fuel(syms)
    except Exception:  # noqa: BLE001 - the gauge is context; the mood readout must still come out
        fl = None
    mkt = dict(fear_greed=fg, fear_greed_txt=fg_txt, median_long_share=statistics.median(ls) if ls else None,
               share_neg_funding=sum(f < 0 for f in fy) / len(fy) if fy else None, btc_crowd=btc, fuel=fl)
    return dict(t=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), market=mkt, coins=R)


def show(S: dict) -> str:
    m = S["market"]
    f = lambda v, fmt, k=1.0: format(v * k, fmt) if v is not None else "-"  # noqa: E731
    L = [f"MARKET MOOD  {S['t']}  (Binance perps, top {len(S['coins'])} by last month's volume; information, not a trade signal)", "",
         f"   Fear & Greed {m['fear_greed']} ({m['fear_greed_txt']}) | median coin: {f(m['median_long_share'], '.0f', 100)}% of accounts"
         f" long | {f(m['share_neg_funding'], '.0f', 100)}% of coins pay shorts (negative funding)"
         + (f" | BTC crowd long/short {m['btc_crowd']:.2f}" if m["btc_crowd"] else ""), ""]
    fl = m.get("fuel")
    if fl:
        L += [f"   TREND-BOOK FUEL {fl.get('state', '-')}: {fl['runners'] * 100:.0f}% of the coins are up >20% in 30 days"
              + (f" (percentile {fl['runners_pct']:.0f} of 2020-26)" if "runners_pct" in fl else "")
              + f", the median coin {fl['med'] * 100:+.0f}%"
              + (f" (percentile {fl['med_pct']:.0f})" if "med_pct" in fl else "")
              + ". The machine's explosive months follow months with many runners (convexity.py).", ""]
    L += [f"   {'coin':<14}{'long %':>7}{'crowd rank':>11}{'funding %/yr':>13}{'taker b/s':>10}{'OI 7d':>8}   flag"]
    for r in S["coins"]:
        L.append(f"   {r['sym'][:-4]:<14}{f(r['long_share'], '>7.0f', 100)}{f(r['crowd_pct'], '>11.0f', 100)}"
                 f"{f(r['fund_yr'], '>+13.1f')}{f(r['taker'], '>10.2f')}{f(r['oi7'], '>+7.0f', 100)}%   {r['flag']}")
    L += ["", "   SQUEEZE WATCH = the quarter of coins the crowd is most short. Over 2022-26 that quarter beat the most-long quarter",
          "   by +37..+48%/yr (funding + squeezes, t 1.8-2.0: a lead, not proven). Bluesky chatter, top traders, OI: no edge."]
    return "\n".join(L)


if __name__ == "__main__":
    S = snapshot()
    print(json.dumps(S, indent=1) if "--json" in sys.argv else show(S))
