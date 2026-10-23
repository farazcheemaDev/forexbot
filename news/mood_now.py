"""MARKET MOOD, NOW - a read-only readout of the crypto sentiment measures that held up (2026-10-23)

THE USER (2026-10-23): "we need to make better sentiment analysis tool ... add all the good stuff, also work on getting
news from X". What the history says is worth showing (news/impact_by_source.py, news/positioning_hist.py, news/bsky_hist.py):
  CROWD    Binance's long / short ACCOUNT ratio per perp, ranked across the backtest's universe (the top 40 by the prior
           month's volume, listed >= 30 days; cached once a month in mood_pool.json). The coins the crowd is
           most SHORT out-earned the most LONG by +37..+48%/yr over 2022-26 (t 1.8-2.0 - a LEAD, not a pass): ~40% of it
           funding paid to the longs, the rest short squeezes in small coins. The bottom quarter is flagged SQUEEZE WATCH.
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

Public Binance endpoints only, no keys, no orders. INFORMATION, NOT A TRADE SIGNAL: doc 22 freezes new books.
    python -m news.mood_now            (table)
    python -m news.mood_now --json     (the snapshot, for the dashboard)
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest.market_neutral import NON_CRYPTO  # noqa: E402

FAPI = "https://fapi.binance.com"
POOL = ROOT / "strategy_analysis" / "data" / "news" / "mood_pool.json"     # {month: top perps by last month's volume}
TOP_N = 40
SQUEEZE_Q, LONG_Q = 0.25, 0.75                       # the crowd book's quarters (positioning_hist: long <= 25%, short >= 75%)


def get(u: str):
    for k in range(3):
        try:
            return json.load(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}),
                                                    timeout=30))
        except Exception:  # noqa: BLE001
            if k == 2:
                raise
            time.sleep(1 + 2 * k)


def universe(n: int = TOP_N, now: pd.Timestamp | None = None) -> list[str]:
    """THE BACKTEST'S UNIVERSE (wide_book.eligibility): every USDT perp listed >= MIN_AGE_D days at the month's start,
    ranked by the PRIOR calendar month's quote volume, fixed for the month and cached. Today's 24h volume would let in
    the week's new listings (IRYS, MAGMA, BIRB on 2026-10-23), which the crowd book never ranked."""
    from backtest.wide_book import MIN_AGE_D
    now = now or pd.Timestamp.now(tz="UTC")
    month = now.strftime("%Y-%m")
    mstart = pd.Timestamp(month + "-01", tz="UTC")
    prev = (mstart - pd.Timedelta(days=1)).strftime("%Y-%m")
    saved = json.loads(POOL.read_text()) if POOL.exists() else {}
    if month in saved:
        return saved[month][:n]
    info = [s for s in get(f"{FAPI}/fapi/v1/exchangeInfo")["symbols"]
            if s.get("contractType") == "PERPETUAL" and s.get("status") == "TRADING" and s.get("quoteAsset") == "USDT"
            and s["symbol"][:-4] not in NON_CRYPTO
            and (mstart - pd.Timestamp(s["onboardDate"], unit="ms", tz="UTC")).days >= MIN_AGE_D]

    def qvol(sym):
        try:
            k = get(f"{FAPI}/fapi/v1/klines?symbol={sym}&interval=1d&limit=65")
        except Exception:  # noqa: BLE001
            return sym, None
        return sym, sum(float(b[7]) for b in k if pd.Timestamp(b[0], unit="ms").strftime("%Y-%m") == prev)
    with ThreadPoolExecutor(8) as ex:
        got = dict(ex.map(qvol, [s["symbol"] for s in info]))
    vol = {s: v for s, v in got.items() if v is not None}
    if len(vol) < 0.9 * len(info):
        raise RuntimeError(f"universe: read {len(vol)} of {len(info)} perps - try again")
    saved[month] = sorted(vol, key=lambda s: -vol[s])[:n]
    POOL.parent.mkdir(parents=True, exist_ok=True)
    POOL.write_text(json.dumps(saved))
    return saved[month]


def funding() -> dict[str, float]:
    """Last funding rate per symbol, annualised in %."""
    hours = {f["symbol"]: float(f["fundingIntervalHours"]) for f in get(f"{FAPI}/fapi/v1/fundingInfo")}
    return {p["symbol"]: float(p["lastFundingRate"]) * (24 / hours.get(p["symbol"], 8.0)) * 365 * 100
            for p in get(f"{FAPI}/fapi/v1/premiumIndex")}


def coin(sym: str) -> dict:
    q = f"symbol={sym}&period=5m"
    g = get(f"{FAPI}/futures/data/globalLongShortAccountRatio?{q}&limit=1")
    tk = get(f"{FAPI}/futures/data/takerlongshortRatio?{q}&limit=288")
    oi = get(f"{FAPI}/futures/data/openInterestHist?symbol={sym}&period=1d&limit=8")
    o = [float(x["sumOpenInterestValue"]) for x in oi]
    return dict(sym=sym,
                crowd=float(g[0]["longShortRatio"]) if g else np.nan,
                long_share=float(g[0]["longAccount"]) if g else np.nan,
                taker=float(np.mean([float(x["buySellRatio"]) for x in tk])) if tk else np.nan,
                oi7=(o[-1] / o[0] - 1) if len(o) >= 8 and o[0] > 0 else np.nan)


def rank(rows: list[dict], fund: dict[str, float]) -> pd.DataFrame:
    """Rank the crowd across the coins and flag the crowd book's quarters."""
    D = pd.DataFrame(rows)
    D["fund_yr"] = D.sym.map(fund)
    D["crowd_pct"] = D.crowd.rank(pct=True)
    D["flag"] = np.where(D.crowd_pct <= SQUEEZE_Q, "SQUEEZE WATCH", np.where(D.crowd_pct >= LONG_Q, "crowd long", ""))
    D.loc[D.crowd.isna(), "flag"] = ""
    return D.sort_values("crowd_pct", kind="stable").reset_index(drop=True)


def fear_greed():
    try:
        d = get("https://api.alternative.me/fng/?limit=1")["data"][0]
        return int(d["value"]), d["value_classification"]
    except Exception:  # noqa: BLE001
        return None, "unavailable"


def snapshot(n: int = TOP_N) -> dict:
    syms = universe(n)
    fund = funding()
    with ThreadPoolExecutor(8) as ex:
        rows = list(ex.map(coin, syms))
    D = rank(rows, fund)
    fg, fg_txt = fear_greed()
    mkt = dict(fear_greed=fg, fear_greed_txt=fg_txt, median_long_share=float(D.long_share.median()),
               share_neg_funding=float((D.fund_yr < 0).mean()), btc_crowd=float(D.loc[D.sym == "BTCUSDT", "crowd"].iloc[0])
               if (D.sym == "BTCUSDT").any() else None)
    return dict(t=pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%d %H:%M UTC"), market=mkt,
                coins=[{k: (None if isinstance(v, float) and not np.isfinite(v) else v) for k, v in r.items()}
                       for r in D.to_dict("records")])


def show(S: dict) -> str:
    m = S["market"]
    L = [f"MARKET MOOD  {S['t']}  (Binance perps, top {len(S['coins'])} by last month's volume; information, not a trade signal)", "",
         f"   Fear & Greed {m['fear_greed']} ({m['fear_greed_txt']}) | median coin: {m['median_long_share'] * 100:.0f}% of accounts long"
         f" | {m['share_neg_funding'] * 100:.0f}% of coins pay shorts (negative funding)"
         + (f" | BTC crowd long/short {m['btc_crowd']:.2f}" if m["btc_crowd"] else ""), "",
         f"   {'coin':<14}{'long %':>7}{'crowd rank':>11}{'funding %/yr':>13}{'taker b/s':>10}{'OI 7d':>8}   flag"]
    for r in S["coins"]:
        f = lambda v, fmt: format(v, fmt) if v is not None else "-"  # noqa: E731
        L.append(f"   {r['sym'][:-4]:<14}{f(r['long_share'] and r['long_share'] * 100, '>7.0f')}"
                 f"{f(r['crowd_pct'] and r['crowd_pct'] * 100, '>11.0f')}{f(r['fund_yr'], '>+13.1f')}{f(r['taker'], '>10.2f')}"
                 f"{f(r['oi7'] and r['oi7'] * 100, '>+7.0f')}%   {r['flag']}")
    L += ["", "   SQUEEZE WATCH = the quarter of coins the crowd is most short. Over 2022-26 that quarter beat the most-long quarter",
          "   by +37..+48%/yr (funding + squeezes, t 1.8-2.0: a lead, not proven). Bluesky chatter, top traders, OI: no edge."]
    return "\n".join(L)


if __name__ == "__main__":
    S = snapshot()
    print(json.dumps(S, indent=1) if "--json" in sys.argv else show(S))
