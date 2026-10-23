"""SENTIMENT ENGINE: CROWD MOOD from Bluesky, on history - attention and tone per coin vs its next week (2026-10-23)

THE USER (2026-10-23): "add all the good stuff, also work on getting news from X". X cannot be read without its paid API
or a licensed aggregator (no scraping); Bluesky - where much of crypto-X's crowd moved in 2024-25 - has an open public
search (api.bsky.app app.bsky.feed.searchPosts, no key) with since / until, so its history can be tested now.
COINS  only those with a distinctive name (the search drops the "$" of a cashtag, so "$SOL" finds Spanish "sol"):
       bitcoin, ethereum, solana, dogecoin, cardano, chainlink, polkadot, litecoin, uniswap, aave, shiba inu, hyperliquid,
       bittensor, ethena, arbitrum, ondo, worldcoin, filecoin, injective, toncoin, aptos, zcash, monero, xrp, bnb
PER COIN-DAY  hitsTotal (all posts naming it that UTC day) and the first page (up to 100 latest posts): a crude crypto
       word tone, (bull words - bear words) / posts, from a fixed list written before the run; cached
FEATURES  attention = log(hits / its own 30-day median); tone; both read on day D-1 for the week from D's open
TEST   cross-sectional (the coins each Monday, ranked) and BTC alone (crypto-wide attention / tone -> BTC's next week);
       next 7 days vs BTC (coins) or raw (BTC); 2024-11 .. 2026-09 (Bluesky's crypto crowd is thin before late 2024)
REGISTERED BEFORE THE RUN (2026-10-23)
  B1 attention is CONTRARIAN across coins (a coin talked about far more than usual underperforms next week): IC <= -0.03,
     same sign on both halves.
  B2 tone adds nothing beyond attention: |IC| < 0.03.
  B3 crypto-wide attention -> BTC's next week: correlation between -0.15 and +0.15 (too few weeks to pass anything).
  B4 nothing passes (t >= 2 on both halves).

RESULT (2026-10-23, logs/bsky_hist.txt; 17,075 coin-days, all read; 94 Mondays) - DEAD. B2-B4 RIGHT, B1 WRONG.
  Attention (a coin talked about more than its usual) IC -0.007 (t -0.32), tune +0.007 / holdout -0.027 - not even the
  contrarian lean registered. Tone IC +0.029, tune +0.062 (t +2.39) / holdout -0.019 (t -0.59): flips between halves.
  Crypto-wide attention vs BTC's next week -0.03. Volumes are real (bitcoin ~1,900 posts a day, solana ~240, worldcoin 4)
  - the crowd's chatter carries no information about next week here. X would need its paid API; nothing suggests it
  would differ enough to pay for.

    python -m news.bsky_hist            (fetches ~17k coin-days once, politely; then tests)
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

CACHE = ROOT / "strategy_analysis" / "data" / "news" / "bsky_daily.parquet"
LOG = ROOT / "logs" / "bsky_hist.txt"
API = "https://api.bsky.app/xrpc/app.bsky.feed.searchPosts"
COINS = {"BTCUSDT": "bitcoin", "ETHUSDT": "ethereum", "SOLUSDT": "solana", "DOGEUSDT": "dogecoin", "ADAUSDT": "cardano",
         "LINKUSDT": "chainlink", "DOTUSDT": "polkadot", "LTCUSDT": "litecoin", "UNIUSDT": "uniswap", "AAVEUSDT": "aave",
         "1000SHIBUSDT": "shiba inu", "HYPEUSDT": "hyperliquid", "TAOUSDT": "bittensor", "ENAUSDT": "ethena",
         "ARBUSDT": "arbitrum", "ONDOUSDT": "ondo", "WLDUSDT": "worldcoin", "FILUSDT": "filecoin", "INJUSDT": "injective",
         "TONUSDT": "toncoin", "APTUSDT": "aptos", "ZECUSDT": "zcash", "XMRUSDT": "monero", "XRPUSDT": "xrp", "BNBUSDT": "bnb"}
BULL = re.compile(r"\b(bull\w*|moon\w*|pump\w*|buy\w*|long|ath|breakout|rally|send it|lfg|undervalued|accumulat\w*)\b|🚀", re.I)
BEAR = re.compile(r"\b(bear\w*|dump\w*|crash\w*|sell\w*|short|rug\w*|scam\w*|dead|rekt|capitulat\w*|overvalued)\b|💀", re.I)
START, END = "2024-11-01", "2026-09-14"


def day(q: str, d: str):
    u = API + "?" + urllib.parse.urlencode(dict(q=q, since=f"{d}T00:00:00Z",
                                                until=(pd.Timestamp(d) + pd.Timedelta(days=1)).strftime("%Y-%m-%dT00:00:00Z"),
                                                limit=100, sort="latest"))
    for k in range(4):
        try:
            r = json.load(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "forexbot-research"}),
                                                 timeout=30))
            p = r.get("posts", [])
            txt = [x["record"].get("text", "") for x in p]
            txt = [t for t in txt if q.split()[0] in t.lower()]
            bull = sum(bool(BULL.search(t)) for t in txt)
            bear = sum(bool(BEAR.search(t)) for t in txt)
            return dict(hits=float(r.get("hitsTotal", len(p))), n=len(txt), tone=(bull - bear) / len(txt) if txt else np.nan)
        except Exception:  # noqa: BLE001
            time.sleep(2 + 3 * k)
    return None


def fetch():
    have = pd.read_parquet(CACHE) if CACHE.exists() else pd.DataFrame(columns=["sym", "day", "hits", "n", "tone"])
    done = set(zip(have.sym, have.day))
    days = [d.strftime("%Y-%m-%d") for d in pd.date_range(START, END)]
    todo = [(s, d) for s in COINS for d in days if (s, d) not in done]
    print(f"bluesky: {len(todo):,} coin-days to fetch", flush=True)
    rows = []

    def job(j):
        time.sleep(0.05)
        r = day(COINS[j[0]], j[1])
        return dict(sym=j[0], day=j[1], **(r or dict(hits=np.nan, n=0, tone=np.nan)))
    with ThreadPoolExecutor(12) as ex:
        for k, r in enumerate(ex.map(job, todo)):
            rows.append(r)
            if (k + 1) % 500 == 0:
                print(f"  {k + 1:,} / {len(todo):,}", flush=True)
                pd.concat([have, pd.DataFrame(rows)]).to_parquet(CACHE)
    out = pd.concat([have, pd.DataFrame(rows)], ignore_index=True)
    out.to_parquet(CACHE)
    return out


def main():
    from scipy.stats import spearmanr
    from backtest.market_neutral import load_panel
    B = fetch()
    B["day"] = pd.to_datetime(B.day)
    hits = B.pivot_table(index="day", columns="sym", values="hits")
    tone = B.pivot_table(index="day", columns="sym", values="tone")
    att = np.log(hits.clip(lower=1) / hits.clip(lower=1).rolling(30, min_periods=20).median())
    C, _, _ = load_panel()
    C.index = C.index.astype("datetime64[ns]")
    cff = C.ffill()
    mons = pd.date_range("2024-12-02", END, freq="W-MON")
    rows = []
    for a in mons:
        d0, d1 = a - pd.Timedelta(days=1), a + pd.Timedelta(days=6)
        if d1 > C.index[-1] or d0 not in att.index:
            continue
        btc = cff.at[d1, "BTCUSDT"] / C.at[d0, "BTCUSDT"] - 1
        for s in COINS:
            if s not in C.columns or not np.isfinite(C.at[d0, s]):
                continue
            rows.append(dict(a=a, s=s, att=att.at[d0, s], tone=tone.at[d0, s],
                             fwd=(cff.at[d1, s] / C.at[d0, s] - 1) - (btc if s != "BTCUSDT" else 0.0)))
    D = pd.DataFrame(rows)
    X = D[D.s != "BTCUSDT"]
    dates = sorted(X.a.unique())
    cut = dates[int(len(dates) * 0.6)]
    t = lambda x: x.mean() / (x.std(ddof=1) / np.sqrt(len(x))) if len(x) > 2 and x.std(ddof=1) > 0 else 0.0  # noqa: E731
    L = [f"news/bsky_hist.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; Bluesky public search, {len(COINS)} coins, "
         f"{B.hits.notna().sum():,} coin-days ({START}..{END}); {len(dates)} Mondays, tune before {pd.Timestamp(cut):%Y-%m-%d}", "",
         f"   posts naming a coin a day (median): " + ", ".join(f"{COINS[s]} {hits[s].median():.0f}" for s in list(COINS)[:8]), "",
         "ACROSS COINS (next 7 days vs BTC): mean IC, t, tune / holdout"]
    res = {}
    for f in ("att", "tone"):
        ics = pd.Series({a: spearmanr(g[f], g.fwd).correlation for a, g in X.dropna(subset=[f]).groupby("a") if len(g) >= 10})
        res[f] = (ics.mean(), t(ics), ics[ics.index < cut].mean(), ics[ics.index >= cut].mean(),
                  t(ics[ics.index < cut]), t(ics[ics.index >= cut]))
        L.append(f"   {f:<5} IC {ics.mean():+.3f} t {t(ics):+.2f} | tune {res[f][2]:+.3f} (t {res[f][4]:+.2f}) | holdout "
                 f"{res[f][3]:+.3f} (t {res[f][5]:+.2f}) | {len(ics)} weeks")
    bt = D[D.s == "BTCUSDT"].set_index("a")
    wide = att.mean(axis=1).reindex([a - pd.Timedelta(days=1) for a in bt.index]).to_numpy()
    rb = np.corrcoef(wide[np.isfinite(wide)], bt.fwd.to_numpy()[np.isfinite(wide)])[0, 1]
    L += ["", f"BTC ALONE: crypto-wide attention (mean over coins) vs BTC's next 7 days: correlation {rb:+.2f} over {np.isfinite(wide).sum()} weeks"]
    b1 = res["att"][0] <= -0.03 and res["att"][2] < 0 and res["att"][3] < 0
    b2 = abs(res["tone"][0]) < 0.03
    b3 = -0.15 <= rb <= 0.15
    b4 = not any(min(r[4], r[5]) >= 2 or max(r[4], r[5]) <= -2 for r in res.values())
    L += ["", "REGISTERED PREDICTIONS",
          f"  B1 attention contrarian, IC <= -0.03, both halves negative -> {'RIGHT' if b1 else 'WRONG'}",
          f"  B2 tone |IC| < 0.03 -> {'RIGHT' if b2 else 'WRONG'}",
          f"  B3 crypto-wide attention vs BTC within +-0.15 ({rb:+.2f}) -> {'RIGHT' if b3 else 'WRONG'}",
          f"  B4 nothing at |t| >= 2 on both halves -> {'RIGHT' if b4 else 'WRONG'}"]
    txt = "\n".join(L)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
