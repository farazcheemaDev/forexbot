"""EVERYTHING LINKED: ONE WALK-FORWARD MODEL FED EVERY DATA SOURCE THE REPO HOLDS (2026-11-09)

THE USER (2026-11-09): "run countless combinations / permutations where there is a link between anything like indicators or news or
market patterns". The answer given: do not enumerate rules (the repo has run ~16,000 and the luckiest of many no-edge rules always
looks good); fit ONE model that sees every source at once, let the trees find the links, and count it as one test. The user: "Yes,
part 1". indicator_model.py (2026-11-02) did this with price and volume only ("no funding, no sentiment, no news"); every other source
here was tested on its own (positioning_hist, news impact, unlocks, carry, Bluesky). This joins them.

DATA     the point-in-time top-40 perps (indicator_model.build_panel: prior month's volume, dead coins in, stables and non-crypto out),
         UTC daily bars. Every coin-level feature is known at the day's close and is turned into its cross-sectional rank among that
         day's members (-0.5 .. +0.5, missing = 0), exactly as indicator_model does.
FAMILIES (coin level)
  price     indicator_model's 32 price / volume features, unchanged
  funding   the day's mean funding rate (settlements inside the UTC day: 00, 08, 16), its 7-day mean, the difference
  position  Binance's metrics archive (news/positioning_features.parquet, the day's last 5-minute row): crowd long / short accounts,
            top-trader accounts, top-trader positions, taker buy / sell (day mean, 7-day mean), open interest change over 1 / 7 days,
            open interest / 7-day dollar volume, crowd change over 7 days
  news      11 public Telegram channels (news/events.parquet, coin-tagged headlines, UTC): headlines about the coin on the day and over 7
            days, the 7-day count against its 30-day pace, the mean FinBERT tone of its 7-day headlines, and 7-day counts of listings,
            delistings / monitoring tags, hacks, partnerships, whale / treasury buys, unlock headlines
  social    Bluesky posts mentioning the coin (25 coins, from 2024-11 only): 7-day hits and tone
  unlock    DefiLlama cliff unlocks as % of supply: scheduled in the next 7 days (published in advance) and in the last 7
  size      30-day mean dollar volume, days since the coin's first bar
MARKET   one value per day, the same for every coin, for gradient boosting only (it can only matter through an interaction): Fear &
         Greed (the value dated that day), BTC 7- / 30-day return, BTC against its 50-day average, BTC 30-day volatility, the share of
         members up > 20% in 30 days (the 'fuel'), the share above their 20-day average, the spread of members' 7-day returns, the
         members' median funding, the count and mean tone of market-wide headlines; each as a rolling 365-day percentile of itself (a
         headline count that grows with the channels keeps its meaning); plus weekday and month.
WINDOW   rows from 2022-01-01 (the positioning archive starts 2021-12); re-fitted every calendar quarter, out of sample 2022-10 ..
         2026-09; tune half before 2024-08-29, holdout after. The PRICE-only model is re-run on the SAME rows and quarters.
MODELS   indicator_model's, fixed and never tuned: ridge (alpha 10) on the coin-level ranks; gradient boosting (depth 3, 150 trees,
         learning rate 0.05, 200 rows a leaf) on the ranks plus the market block. Embargo H + 1 days; expanding window.
CONFIGS  ALL (every family + market), PRICE (price only, no market), NEW (everything except price), SINGLE (the best single coin-level
         feature of ALL on the training window, in its own direction).
TRADE    indicator_model's: each day long the top fifth of the prediction, short the bottom fifth, entered at the next open, out at the
         close H days later (H = 1, 3, 7); NET = spread - 24bp - the long leg's funding at 1bp / 8h (shorts receive nothing); the H
         entry alignments scored separately (mean, mean t, worst alignment).
PASS     (per cell, as indicator_model) on BOTH halves net > 0 with t >= 2, worst alignment > 0, IC t >= 2; Holm < 0.05 over the 6
         primary cells (ALL x ridge / gradient boosting x H 1 / 3 / 7).
VERDICT  CANDIDATE = an ALL cell passes AND beats PRICE with the same model (paired gross spread, t >= 2 on both halves): the link
         between sources is what pays. PRICE-ONLY = an ALL cell passes without beating PRICE. Otherwise NO PASS.
DIAGNOSTICS (not in the verdict) drop-one-family ablation (gradient boosting, every H); and POWER: a PLANTED feature built from the
         true future rank (correlation rho with it, rho 0.03 and 0.10) added to ALL at H = 7 - the size of hidden link this pipeline
         can see at all.

HONEST LIMITS (written before the run). Each family was already looked at alone on 2022-26, and the price-only model has read this
window, so this is not an unseen holdout; the holdout is the repo's shared, much-read one. The unlock schedules are DefiLlama's
current file (a schedule revised after the fact would read as known in advance). Bluesky covers 25 coins from 2024-11. A pass here
is a lead for the forward paper farm, not money.

REGISTERED BEFORE THE FIRST RUN (2026-11-09; my prior that a CANDIDATE appears: about 10%, as told to the user)
  A1  No primary ALL cell passes.
  A2  Joining adds little: ALL - PRICE (same model) paired gross spread has t < 2 on at least one half in >= 5 of the 6 cells, and
      ALL's mean IC beats PRICE's by under 0.02 in every cell on both halves.
  A3  NEW (no price) gradient boosting at H = 7 has an IC between 0.00 and +0.04 on both halves.
  A4  Ridge's largest |coefficient| in ALL is atr_pct at H = 3 and at H = 7 (the low-volatility tilt stays the main thing).
  A5  Every H = 1 ALL cell has a negative net spread on both halves.
  A6  In the drop-one ablation (gradient boosting, H = 7) 'position' is the new family whose removal costs the most IC.
  A7  Power: the planted rho = 0.03 feature does NOT make gradient boosting H = 7 meet the per-cell bar; rho = 0.10 does.

AMENDMENT (2026-11-09, after the first run; nothing registered above changed): two POST-HOC diagnostics were added because the
first run raised two questions - the model WITHOUT price features scored about the same IC as with them (one factor seen through
every source, or a leak?), and even the planted IC 0.10 feature did not lift the model over the bar (how strong must a link be?).
POST-HOC 1 prints each feature's own IC and its correlation with atr_pct; POST-HOC 2 trades a planted signal on its own at three
strengths. POST-HOC 2 then showed a clean IC 0.10 signal meets the bar easily, so the model's failure is not plain power; POST-HOC 3
(added after the second run) asks what the model knows BEYOND the volatility sort: its prediction with the daily line on the
atr_pct rank removed, traded the same way. Any pass in a post-hoc section is a lead on the shared holdout, not a candidate.
The code was also refactored (market_raw split out of market_block, load_fng takes a path) without changing a number;
the log is from the final code.

    python -m backtest.all_sources_model            (builds strategy_analysis/data/all_sources_panel.npz once, ~minutes)
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest import candle_scan as cs  # noqa: E402
from backtest import indicator_model as im  # noqa: E402

LOG = ROOT / "logs" / "all_sources_model.txt"
DATA = ROOT / "strategy_analysis" / "data"
NEWSD = DATA / "news"
PERPS = DATA / "perps"
CACHE = DATA / "all_sources_panel.npz"
HORIZONS = (1, 3, 7)
KEEP_FROM = np.datetime64("2021-11-01")         # rows kept once the features are built (earlier days only feed the look-backs)
TRAIN_FROM = np.datetime64("2022-01-01")
FIRST_OOS = np.datetime64("2022-10-01")
CUT = im.CUT
PLANT_RHO = (0.03, 0.10)
PLANT_H = 7

LISTING = ("list_spot", "list_futures", "new_pairs", "adds_products", "launchpool")
DELIST = ("delist", "delist_pairs", "delist_futures", "monitoring_tag", "seed_tag")
FAMILIES = {
    "price": list(im.FEATURES),
    "funding": ["fund1", "fund7", "fund_chg"],
    "position": ["crowd", "top_acc", "top_pos", "taker1", "taker7", "oi_chg1", "oi_chg7", "oi_vol", "crowd_chg7"],
    "news": ["news1", "news7", "news_spike", "tone7", "listing7", "delist7", "hack7", "partner7", "whale7", "unlocknews7"],
    "social": ["bsky7", "bsky_tone7"],
    "unlock": ["unl_next7", "unl_last7"],
    "size": ["liq30", "age"],
}
MARKET = ["fng", "btc_ret7", "btc_ret30", "btc_ma50", "btc_vol30", "fuel", "breadth20", "disp7", "mkt_fund", "mkt_news", "mkt_tone",
          "dow", "month"]
RAW_MARKET = ("dow", "month")                     # not turned into percentiles
COIN = [f for fam in FAMILIES.values() for f in fam]
NEW = [f for k, fam in FAMILIES.items() if k != "price" for f in fam]


# ---------------------------------------------------------------- grid helpers

def day_index(dates, day):
    """Integer row of each day on the grid `dates` (datetime64[D]); `day` anything numpy / pandas can read as a date."""
    d = pd.to_datetime(pd.Series(np.asarray(day))).to_numpy().astype("datetime64[D]")
    return (d - dates[0]).astype(int)


def to_grid(dates, coins, day, sym, val):
    """Scatter (day, symbol, value) rows onto a (days x coins) array of NaN; a later row for the same cell wins."""
    T, N = len(dates), len(coins)
    out = np.full((T, N), np.nan)
    k = day_index(dates, day)
    ci = {c: j for j, c in enumerate(coins)}
    j = np.array([ci.get(s, -1) for s in sym], int)
    v = np.asarray(val, float)
    ok = (k >= 0) & (k < T) & (j >= 0) & np.isfinite(v)
    out[k[ok], j[ok]] = v[ok]
    return out


def count_grid(dates, coins, day, sym, w=None):
    """Sum of weights (default 1) per (day, coin) cell; zero where nothing happened."""
    T, N = len(dates), len(coins)
    out = np.zeros((T, N))
    k = day_index(dates, day)
    ci = {c: j for j, c in enumerate(coins)}
    j = np.array([ci.get(s, -1) for s in sym], int)
    w = np.ones(len(k)) if w is None else np.asarray(w, float)
    ok = (k >= 0) & (k < T) & (j >= 0) & np.isfinite(w)
    np.add.at(out, (k[ok], j[ok]), w[ok])
    return out


def trailing_sum(a, w):
    """Sum of rows t-w+1 .. t (a zero-filled count array)."""
    c = np.cumsum(np.vstack([np.zeros((1,) + a.shape[1:]), a]), axis=0)
    out = c[1:].copy()
    out[w:] -= c[1:-w] if w < len(c) - 1 else 0
    return out


def leading_sum(a, w):
    """Sum of rows t+1 .. t+w (a schedule known in advance)."""
    T = len(a)
    c = np.cumsum(np.vstack([np.zeros((1,) + a.shape[1:]), a]), axis=0)
    hi = np.minimum(np.arange(T) + w + 1, T)
    return c[hi] - c[np.minimum(np.arange(T) + 1, T)]


# ---------------------------------------------------------------- coin-level families

def _funding_csv(sym):
    p = PERPS / f"{sym}_funding.csv.gz"
    return pd.read_csv(p) if p.exists() else None


def funding_panels(dates, coins, loader=_funding_csv):
    """fund1[t] = mean rate of the settlements inside UTC day t (a settlement at t+1 00:00 belongs to day t+1)."""
    T, N = len(dates), len(coins)
    d1 = np.full((T, N), np.nan)
    for j, s in enumerate(coins):
        f = loader(s)
        if f is None or not len(f):
            continue
        day = pd.to_datetime(f["time"]).dt.floor("D")
        m = f["rate"].astype(float).groupby(day.to_numpy()).mean()
        k = day_index(dates, m.index.to_numpy())
        ok = (k >= 0) & (k < T)
        d1[k[ok], j] = m.to_numpy(float)[ok]
    df = pd.DataFrame(d1)
    f7 = df.rolling(7, min_periods=3).mean()
    return {"fund1": d1, "fund7": f7.to_numpy(float), "fund_chg": (df - f7).to_numpy(float)}


def _log_pos(a):
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.log(np.where(a > 0, a, np.nan))


def position_panels(dates, coins, pos, V):
    """Binance metrics: the row of day t is the day's last 5-minute record (taker: the day's mean), known at the day's close."""
    g = {c: to_grid(dates, coins, pos["day"], pos["sym"], pos[c]) for c in ("crowd", "top_acc", "top_pos", "taker", "oi")}
    crowd, oi = pd.DataFrame(_log_pos(g["crowd"])), pd.DataFrame(_log_pos(g["oi"]))
    vol7 = pd.DataFrame(V).rolling(7, min_periods=5).mean().to_numpy(float)
    with np.errstate(invalid="ignore", divide="ignore"):
        oi_vol = np.where(vol7 > 0, g["oi"] / vol7, np.nan)
    return {"crowd": crowd.to_numpy(float), "top_acc": _log_pos(g["top_acc"]), "top_pos": _log_pos(g["top_pos"]),
            "taker1": g["taker"], "taker7": pd.DataFrame(g["taker"]).rolling(7, min_periods=3).mean().to_numpy(float),
            "oi_chg1": (oi - oi.shift(1)).to_numpy(float), "oi_chg7": (oi - oi.shift(7)).to_numpy(float), "oi_vol": oi_vol,
            "crowd_chg7": (crowd - crowd.shift(7)).to_numpy(float)}


def news_panels(dates, coins, ev, tone):
    """Coin-tagged headlines counted on the UTC day of their time stamp (so day t holds only what was out before t+1 00:00).
    Returns the coin families and the two market-wide daily series (count and mean tone of headlines tagged to no coin)."""
    e = pd.DataFrame({"t": pd.to_datetime(ev["t"]), "etype": ev["etype"].astype(str), "coins": ev["coins"].fillna("").astype(str),
                      "tone": np.asarray(tone, float)})
    mk = e[e.coins == ""]
    T = len(dates)
    kd = day_index(dates, mk.t.dt.floor("D").to_numpy())
    ok = (kd >= 0) & (kd < T)
    mkt_n = np.bincount(kd[ok], minlength=T).astype(float)
    mkt_ts = np.bincount(kd[ok], weights=mk.tone.to_numpy(float)[ok], minlength=T)
    with np.errstate(invalid="ignore", divide="ignore"):
        mkt_tone = np.where(mkt_n > 0, mkt_ts / mkt_n, np.nan)
    c = e[e.coins != ""].assign(coin=lambda d: d.coins.str.split(",")).explode("coin")
    c = c[c.coin != ""]
    day = c.t.dt.floor("D").to_numpy()

    def cnt(mask=None, w=None):
        sel = np.ones(len(c), bool) if mask is None else np.asarray(mask)
        return count_grid(dates, coins, day[sel], c.coin.to_numpy()[sel], None if w is None else np.asarray(w)[sel])

    n1 = cnt()
    n7, n30 = trailing_sum(n1, 7), trailing_sum(n1, 30)
    tsum7 = trailing_sum(cnt(w=c.tone.to_numpy(float)), 7)
    et = c.etype.to_numpy()
    with np.errstate(invalid="ignore", divide="ignore"):
        out = {"news1": n1, "news7": n7, "news_spike": np.log((n7 + 1) / (n30 * 7 / 30 + 1)),
               "tone7": np.where(n7 > 0, tsum7 / n7, np.nan),
               "listing7": trailing_sum(cnt(np.isin(et, LISTING)), 7), "delist7": trailing_sum(cnt(np.isin(et, DELIST)), 7),
               "hack7": trailing_sum(cnt(et == "hack"), 7), "partner7": trailing_sum(cnt(et == "partnership"), 7),
               "whale7": trailing_sum(cnt(np.isin(et, ("whale", "treasury_buy"))), 7),
               "unlocknews7": trailing_sum(cnt(et == "unlock"), 7)}
    return out, mkt_n, mkt_tone


def social_panels(dates, coins, bsky):
    hits = pd.DataFrame(to_grid(dates, coins, bsky["day"], bsky["sym"], bsky["hits"]))
    tone = pd.DataFrame(to_grid(dates, coins, bsky["day"], bsky["sym"], bsky["tone"]))
    return {"bsky7": hits.rolling(7, min_periods=1).sum().to_numpy(float),
            "bsky_tone7": tone.rolling(7, min_periods=1).mean().to_numpy(float)}


def coin_base(sym):
    b = sym[:-4] if sym.endswith("USDT") else sym
    for p in ("1000000", "1000"):
        if b.startswith(p) and len(b) > len(p):
            return b[len(p):]
    return b


def unlock_panels(dates, coins, rows):
    """Cliff unlocks as % of supply (unlocks.load_events' definition), summed per day; next7 = days t+1 .. t+7 (the schedule is
    published in advance), last7 = days t-6 .. t. Coins without a schedule read zero."""
    df = pd.DataFrame([r for r in rows if r.get("kind") == "cliff"])
    T, N = len(dates), len(coins)
    u = np.zeros((T, N))
    if len(df):
        df["supply"] = df["adj_supply"].fillna(df["max_supply"])
        df = df[df.supply > 0]
        pct = (df.tokens / df.supply * 100).to_numpy(float)
        k = day_index(dates, pd.to_datetime(df.ts, unit="s").dt.floor("D").to_numpy())
        bases = {}
        for j, c in enumerate(coins):
            bases.setdefault(coin_base(c), []).append(j)
        for kk, s, p in zip(k, df.sym.astype(str), pct):
            if 0 <= kk < T and np.isfinite(p):
                for j in bases.get(s, ()):
                    u[kk, j] += p
    return {"unl_next7": leading_sum(u, 7), "unl_last7": trailing_sum(u, 7)}


def size_panels(C, V):
    T, N = C.shape
    liq = pd.DataFrame(V).rolling(30, min_periods=20).mean().to_numpy(float)
    with np.errstate(invalid="ignore", divide="ignore"):
        liq30 = np.log(np.where(liq > 0, liq, np.nan))
    age = np.full((T, N), np.nan)
    for j in range(N):
        fin = np.flatnonzero(np.isfinite(C[:, j]))
        if len(fin):
            age[fin[0]:, j] = np.arange(T - fin[0], dtype=float)
    return {"liq30": liq30, "age": age}


# ---------------------------------------------------------------- market block

def causal_pct(x, w=365, min_periods=60):
    """Percentile of each day's value among the last w days' values, itself included (no later day takes part)."""
    return pd.Series(np.asarray(x, float)).rolling(w, min_periods=min_periods).rank(pct=True).to_numpy(float)


def _xs_stat(A, M, fn):
    out = np.full(len(A), np.nan)
    for t in range(len(A)):
        v = A[t][M[t] & np.isfinite(A[t])]
        if len(v) >= 5:
            out[t] = fn(v)
    return out


def market_block(dates, C, M, price, fund1, mkt_n, mkt_tone, fng, btc):
    """The market features as fed to the model: each raw series as its causal 365-day percentile, plus weekday and month."""
    out = {k: causal_pct(v) for k, v in market_raw(C, M, price, fund1, mkt_n, mkt_tone, fng, btc).items()}
    di = pd.DatetimeIndex(pd.to_datetime(dates))
    out["dow"], out["month"] = di.dayofweek.to_numpy(float), di.month.to_numpy(float)
    return out


def market_raw(C, M, price, fund1, mkt_n, mkt_tone, fng, btc):
    cb = pd.Series(C[:, btc])
    lr = np.log(cb / cb.shift(1))
    with np.errstate(invalid="ignore", divide="ignore"):
        above20 = np.where(np.isfinite(C), (C > pd.DataFrame(C).rolling(20).mean().to_numpy(float)).astype(float), np.nan)
    raw = {"fng": fng, "btc_ret7": np.log(cb / cb.shift(7)).to_numpy(float), "btc_ret30": np.log(cb / cb.shift(30)).to_numpy(float),
           "btc_ma50": (cb / cb.rolling(50).mean() - 1).to_numpy(float), "btc_vol30": lr.rolling(30).std().to_numpy(float),
           "fuel": _xs_stat(price["ret30"], M, lambda v: float(np.mean(v > np.log(1.2)))),
           "breadth20": _xs_stat(above20, M, lambda v: float(np.mean(v))),
           "disp7": _xs_stat(price["ret7"], M, lambda v: float(np.std(v))),
           "mkt_fund": _xs_stat(fund1, M, lambda v: float(np.median(v))), "mkt_news": mkt_n, "mkt_tone": mkt_tone}
    return raw


def load_fng(dates, path=DATA / "fng.csv"):
    """Fear & Greed: day t gets the value dated t (published at t 00:00 UTC)."""
    d = pd.read_csv(path)
    d.columns = ["date", "fng"]
    k = day_index(dates, d["date"].to_numpy())
    out = np.full(len(dates), np.nan)
    ok = (k >= 0) & (k < len(dates))
    out[k[ok]] = d["fng"].to_numpy(float)[ok]
    return out


# ---------------------------------------------------------------- build

def build(use_cache=True):
    if use_cache and CACHE.exists():
        z = np.load(CACHE, allow_pickle=True)
        feats = {k: z["f_" + k] for k in COIN}
        mkt = {k: z["m_" + k] for k in MARKET}
        return dict(dates=z["dates"], coins=list(z["coins"]), O=z["O"], C=z["C"], M=z["M"], feats=feats, mkt=mkt)
    t0 = time.time()
    dates, coins, O, H, L, C, V, M = im.build_panel()
    btc = coins.index("BTCUSDT")
    feats = dict(im.feature_panels(O, H, L, C, V, btc))
    print(f"price panel {time.time() - t0:.0f}s", flush=True)
    feats.update(funding_panels(dates, coins))
    feats.update(position_panels(dates, coins, pd.read_parquet(NEWSD / "positioning_features.parquet"), V))
    ev = pd.read_parquet(NEWSD / "events.parquet")
    tone = pd.read_parquet(NEWSD / "tone.parquet")["tone"].to_numpy(float)
    nf, mkt_n, mkt_tone = news_panels(dates, coins, ev, tone)
    feats.update(nf)
    feats.update(social_panels(dates, coins, pd.read_parquet(NEWSD / "bsky_daily.parquet")))
    feats.update(unlock_panels(dates, coins, json.load(open(DATA / "unlock_events.json"))))
    feats.update(size_panels(C, V))
    mkt = market_block(dates, C, M, feats, feats["fund1"], mkt_n, mkt_tone, load_fng(dates), btc)
    keep = dates >= KEEP_FROM
    P = dict(dates=dates[keep], coins=coins, O=O[keep], C=C[keep], M=M[keep],
             feats={k: feats[k][keep].astype(np.float32) for k in COIN}, mkt={k: np.asarray(mkt[k])[keep] for k in MARKET})
    np.savez(CACHE, dates=P["dates"], coins=np.array(coins), O=P["O"], C=P["C"], M=P["M"],
             **{"f_" + k: v for k, v in P["feats"].items()}, **{"m_" + k: v for k, v in P["mkt"].items()})
    print(f"built in {time.time() - t0:.0f}s", flush=True)
    return P


# ---------------------------------------------------------------- run

POST_RHO = (0.10, 0.20, 0.30)


def posthoc(dates, feats, mem, F, Y, H):
    """ADDED AFTER THE FIRST RUN (2026-11-09), not part of the registered test: (1) which single features carry the information and
    how much each one shares with atr_pct (the low-volatility tilt indicator_model found); (2) the IC a signal needs ON ITS OWN, with
    no model, to meet the per-cell bar on this universe and window."""
    fam_of = {k: fam for fam, names in FAMILIES.items() for k in names}
    oos = dates >= FIRST_OOS
    rows = []
    for k in COIN:
        c = im.cell(dates, feats[k].astype(float), F, mem, H)
        with_atr = im.day_scores(feats[k].astype(float), feats["atr_pct"].astype(float), mem)[0]
        rows.append((k, c["tu"]["ic"]["mean"], c["tu"]["ic"]["t"], c["ho"]["ic"]["mean"], c["ho"]["ic"]["t"], np.nanmean(with_atr[oos])))
    rows.sort(key=lambda r: -abs(r[1] + r[3]))
    L = ["", f"POST-HOC 1 (added after the first run): each feature on its own, H = {H}, out of sample (missing values left out); "
             f"'with atr_pct' = its mean daily rank correlation with atr_pct",
         f"  {'feature':<13}{'family':<10}{'IC tune (t)':<17}{'IC hold (t)':<17}with atr_pct"]
    for k, a, at, b, bt, w in rows[:20]:
        L.append(f"  {k:<13}{fam_of[k]:<10}{a:+.3f} ({at:+.1f})   {b:+.3f} ({bt:+.1f})   {w:+.2f}")
    best_new = {}
    for r in rows:
        if fam_of[r[0]] != "price" and fam_of[r[0]] not in best_new:
            best_new[fam_of[r[0]]] = r
    L.append("  strongest feature of each new family: " + "; ".join(
        f"{fam} {r[0]} {r[1]:+.3f} / {r[3]:+.3f} (atr {r[5]:+.2f})" for fam, r in best_new.items()))
    L += ["", f"POST-HOC 2 (added after the first run): a planted signal traded ON ITS OWN (no model), H = {H}: the IC it takes to meet "
              "the per-cell bar here"]
    for i, rho in enumerate(POST_RHO):
        c = im.cell(dates, planted(Y, mem, rho, seed=31 + i).astype(float), F, mem, H)
        L.append(f"  rho {rho:.2f}: IC {c['tu']['ic']['mean']:+.3f} / {c['ho']['ic']['mean']:+.3f}; NET "
                 f"{c['tu']['net']['mean'] * 1e4:+7.1f}bp ({c['tu']['net']['t']:+.1f}) / {c['ho']['net']['mean'] * 1e4:+7.1f}bp "
                 f"({c['ho']['net']['t']:+.1f}); worst alignment {c['tu']['net']['worst'] * 1e4:+.1f} / {c['ho']['net']['worst'] * 1e4:+.1f}"
                 f" -> bar {'MET' if bar_met(c) else 'not met'}")
    return L


def vol_neutral(pred, atr, mem, min_names=im.MIN_NAMES):
    """POST-HOC 3: each day, the prediction minus its least-squares line on the coins' atr_pct rank (members only): what the model
    knows beyond 'calm coins beat volatile ones'."""
    out = np.full(pred.shape, np.nan)
    for t in range(len(pred)):
        ok = mem[t] & np.isfinite(pred[t]) & np.isfinite(atr[t])
        if ok.sum() < min_names:
            continue
        A = np.column_stack([np.ones(int(ok.sum())), atr[t, ok]])
        b = np.linalg.lstsq(A, pred[t, ok], rcond=None)[0]
        out[t, ok] = pred[t, ok] - A @ b
    return out


def train_mask(mem, dates, start=TRAIN_FROM):
    """Rows a model may learn from: members on or after `start` (walk_forward adds the embargo)."""
    return mem & (np.asarray(dates) >= start)[:, None]


def verdict(cells_all, cells_price, holm_adj):
    """'CANDIDATE' / 'PRICE-ONLY' / 'NO PASS' over the primary ALL cells; cells_* {(H, model): im.cell output with 'paired' vs PRICE}."""
    passing = [k for k, c in cells_all.items() if im.passes(c, holm_adj[k])]
    if not passing:
        return "NO PASS", passing
    beats = [k for k in passing if min(cells_all[k]["tu"]["paired"]["t"], cells_all[k]["ho"]["paired"]["t"]) >= 2]
    return ("CANDIDATE" if beats else "PRICE-ONLY"), passing


def bar_met(c):
    return im.passes(c, 0.0)


def planted(Y, mem, rho, seed):
    """A coin-level feature with correlation ~rho to the TRUE future rank (pure noise where the future is unknown), ranked."""
    rng = np.random.default_rng(seed)
    eps = rng.standard_normal(Y.shape)
    z = np.where(np.isfinite(Y), Y / np.sqrt(1 / 12), 0.0)
    raw = np.where(np.isfinite(Y), rho * z + np.sqrt(1 - rho ** 2) * eps, eps)
    return np.nan_to_num(im.xs_rank(raw, mem), nan=0.0).astype(np.float32)


def fmt_cell(name, c):
    tu, ho = c["tu"], c["ho"]
    pr = (f"{tu['paired']['mean'] * 1e4:+5.1f}bp ({tu['paired']['t']:+.1f}) / {ho['paired']['mean'] * 1e4:+5.1f}bp ({ho['paired']['t']:+.1f})"
          if "paired" in tu else "")
    return (f"{name:<16}{tu['ic']['mean']:+.3f} ({tu['ic']['t']:+.1f}) / {ho['ic']['mean']:+.3f} ({ho['ic']['t']:+.1f})   "
            f"{tu['gross']['mean'] * 1e4:+6.1f} / {ho['gross']['mean'] * 1e4:+6.1f}bp   "
            f"{tu['net']['mean'] * 1e4:+6.1f}bp ({tu['net']['t']:+.1f}) / {ho['net']['mean'] * 1e4:+6.1f}bp ({ho['net']['t']:+.1f})   "
            f"{tu['net']['worst'] * 1e4:+6.1f} / {ho['net']['worst'] * 1e4:+6.1f}  {pr}")


def main():
    t0 = time.time()
    P = build(use_cache="--rebuild" not in sys.argv)
    dates, coins, O, C, M = P["dates"], P["coins"], P["O"], P["C"], P["M"]
    feats, mkt = P["feats"], P["mkt"]
    nfin = sum(np.isfinite(feats[k]).astype(np.int16) for k in im.FEATURES)
    mem = M & (nfin >= im.MIN_FEATS) & np.isfinite(O) & np.isfinite(C)
    mem_tr = train_mask(mem, dates)
    oos = mem & (dates >= FIRST_OOS)[:, None]
    ranked = {k: np.nan_to_num(im.xs_rank(feats[k], mem), nan=0.0).astype(np.float32) for k in COIN}
    mk = np.stack([np.broadcast_to(np.asarray(mkt[k], np.float32)[:, None], M.shape) for k in MARKET], -1)

    def X(names, market=False, extra=None):
        a = np.stack([ranked[k] for k in names] + ([] if extra is None else [extra]), -1)
        return np.concatenate([a, mk], -1) if market else a

    blocks = im.make_blocks(dates, FIRST_OOS)
    L_ = [f"backtest/all_sources_model.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; {len(coins)} PIT coins; "
          f"{int(mem_tr.sum()):,} trainable coin-days from {TRAIN_FROM}; {len(COIN)} coin-level features ({len(im.FEATURES)} price) + "
          f"{len(MARKET)} market; {len(blocks)} quarterly blocks from {FIRST_OOS}; tune < {CUT}; 24bp + long funding per trade", "",
          "COVERAGE (share of out-of-sample member coin-days with a value, before the missing = 0 fill):"]
    for fam, names in FAMILIES.items():
        cov = np.mean([np.isfinite(feats[k][oos]).mean() for k in names])
        L_.append(f"  {fam:<9} {cov * 100:5.1f}%   ({', '.join(names[:6])}{' ...' if len(names) > 6 else ''})")
    mcov = np.mean([np.isfinite(np.asarray(mkt[k])[dates >= FIRST_OOS]).mean() for k in MARKET])
    L_ += [f"  market    {mcov * 100:5.1f}%", ""]

    cells_all, cells_price, extra_lines, ridge_top = {}, {}, [], {}
    ablate = {}
    plant_res = {}
    neutral = {}
    for H in HORIZONS:
        F = im.forward_returns(O, C, H)
        Y = im.xs_rank(F, mem & np.isfinite(F))

        def wf(Xa, model):
            return im.walk_forward(Xa, Y, mem_tr, blocks, H, model)

        p_price = {m: wf(X(FAMILIES["price"]), m) for m in ("ridge", "gbm")}
        p_all = {"ridge": wf(X(COIN), "ridge"), "gbm": wf(X(COIN, market=True), "gbm")}
        p_new = wf(X(NEW, market=True), "gbm")
        p_single = wf(X(COIN), "single")
        for m in ("ridge", "gbm"):
            cp = im.cell(dates, p_price[m][0], F, mem, H)
            cells_price[(H, m)] = cp
            cells_all[(H, m)] = im.cell(dates, p_all[m][0], F, mem, H, ref_spread=cp["spread"])
        neutral[H] = im.cell(dates, vol_neutral(p_all["gbm"][0].astype(float), ranked["atr_pct"].astype(float), mem), F, mem, H)
        cn = im.cell(dates, p_new[0], F, mem, H)
        cs_ = im.cell(dates, p_single[0], F, mem, H)
        extra_lines += [fmt_cell(f"PRICE ridge H{H}", cells_price[(H, "ridge")]), fmt_cell(f"PRICE gbm H{H}", cells_price[(H, "gbm")]),
                        fmt_cell(f"NEW gbm H{H}", cn), fmt_cell(f"SINGLE H{H}", cs_)]
        cells_all[(H, "new")] = cn
        pick = np.bincount(np.array(p_single[1], int), minlength=len(COIN))
        coef = np.mean(p_all["ridge"][1], axis=0)
        ridge_top[H] = COIN[int(np.argmax(coef))]
        L_.append(f"H={H}: single feature chosen most often: " + ", ".join(f"{COIN[k]} x{pick[k]}" for k in np.argsort(-pick)[:4] if pick[k] > 0))
        L_.append("      ridge ALL |coefficient| largest: " + ", ".join(f"{COIN[k]} {coef[k]:.3f}" for k in np.argsort(-coef)[:6]))
        print(f"H={H} main done {time.time() - t0:.0f}s", flush=True)
        for fam in list(FAMILIES) + ["market"]:
            names = [k for k in COIN if k not in FAMILIES.get(fam, [])]
            pa = wf(X(names, market=(fam != "market")), "gbm")
            ablate[(H, fam)] = im.cell(dates, pa[0], F, mem, H)
        print(f"H={H} ablation done {time.time() - t0:.0f}s", flush=True)
        if H == PLANT_H:
            post = posthoc(dates, feats, mem, F, Y, H)
            for i, rho in enumerate(PLANT_RHO):
                pl = planted(Y, mem, rho, seed=11 + i)
                own = im.cell(dates, pl.astype(float), F, mem, H)
                pp = wf(X(COIN, market=True, extra=pl), "gbm")
                plant_res[rho] = (own, im.cell(dates, pp[0], F, mem, H))
            print(f"planted done {time.time() - t0:.0f}s", flush=True)
        L_.append("")

    prim = [(H, m) for H in HORIZONS for m in ("ridge", "gbm")]
    pvals = [cs.p_one_sided(min(cells_all[k]["tu"]["net"]["t"], cells_all[k]["ho"]["net"]["t"])) for k in prim]
    adj = dict(zip(prim, cs.holm(pvals)))
    head = f"{'cell':<16}{'IC tune / hold (t)':<30}{'gross spread':<22}{'NET spread tune / hold (t)':<38}{'worst align':<17}{'paired vs PRICE (t)'}"
    L_ += ["PRIMARY: ALL (every source)", head]
    for k in prim:
        L_.append(fmt_cell(f"ALL {k[1]} H{k[0]}", cells_all[k]) + f"  holm {adj[k]:.2f} {'BAR MET' if im.passes(cells_all[k], adj[k]) else ''}")
    L_ += ["", "REFERENCE (same rows, same quarters)", head] + extra_lines
    L_ += ["", "DROP ONE FAMILY (gradient boosting; mean IC tune / hold, gross spread tune / hold; ALL first)"]
    for H in HORIZONS:
        base = cells_all[(H, "gbm")]
        L_.append(f"  H={H} ALL           IC {base['tu']['ic']['mean']:+.4f} / {base['ho']['ic']['mean']:+.4f}   gross "
                  f"{base['tu']['gross']['mean'] * 1e4:+6.1f} / {base['ho']['gross']['mean'] * 1e4:+6.1f}bp")
        for fam in list(FAMILIES) + ["market"]:
            c = ablate[(H, fam)]
            L_.append(f"      without {fam:<9} IC {c['tu']['ic']['mean']:+.4f} / {c['ho']['ic']['mean']:+.4f}   gross "
                      f"{c['tu']['gross']['mean'] * 1e4:+6.1f} / {c['ho']['gross']['mean'] * 1e4:+6.1f}bp   IC lost "
                      f"{(base['tu']['ic']['mean'] - c['tu']['ic']['mean']):+.4f} / {(base['ho']['ic']['mean'] - c['ho']['ic']['mean']):+.4f}")
    L_ += ["", f"POWER: a planted feature with a known link to the future (H = {PLANT_H}, added to ALL, gradient boosting)"]
    for rho, (own, c) in plant_res.items():
        L_.append(f"  rho {rho:.2f}: the feature's own IC {own['tu']['ic']['mean']:+.3f} / {own['ho']['ic']['mean']:+.3f}; ALL + it: "
                  + fmt_cell("", c).strip() + f"  -> per-cell bar {'MET' if bar_met(c) else 'not met'}")
    L_ += post
    L_ += ["", "POST-HOC 3 (added after the first run): the ALL gradient-boosting prediction made VOLATILITY-NEUTRAL (each day its line on "
               "the atr_pct rank removed), traded the same way", head]
    for H in HORIZONS:
        L_.append(fmt_cell(f"ALL gbm-vn H{H}", neutral[H]) + f"  -> per-cell bar {'MET' if bar_met(neutral[H]) else 'not met'}")

    v, passing = verdict({k: cells_all[k] for k in prim}, cells_price, adj)
    gain = [cells_all[k][h]["ic"]["mean"] - cells_price[k][h]["ic"]["mean"] for k in prim for h in ("tu", "ho")]
    a2n = sum(1 for k in prim if min(cells_all[k]["tu"]["paired"]["t"], cells_all[k]["ho"]["paired"]["t"]) < 2)
    a2 = a2n >= 5 and max(gain) < 0.02
    nh7 = cells_all[(7, "new")]
    a3 = all(0.0 <= nh7[h]["ic"]["mean"] <= 0.04 for h in ("tu", "ho"))
    a4 = ridge_top[3] == "atr_pct" and ridge_top[7] == "atr_pct"
    a5 = all(cells_all[(1, m)][h]["net"]["mean"] < 0 for m in ("ridge", "gbm") for h in ("tu", "ho"))
    b7 = cells_all[(7, "gbm")]
    loss = {f: np.mean([b7[h]["ic"]["mean"] - ablate[(7, f)][h]["ic"]["mean"] for h in ("tu", "ho")]) for f in FAMILIES if f != "price"}
    top_new = max(loss, key=loss.get)
    a7 = (not bar_met(plant_res[PLANT_RHO[0]][1])) and bar_met(plant_res[PLANT_RHO[1]][1])
    L_ += ["", f"VERDICT: {v}" + (f" (cells meeting the bar: {passing})" if passing else ""),
           "REGISTERED PREDICTIONS",
           f"  A1 no primary ALL cell passes -> {'RIGHT' if not passing else 'WRONG'} ({len(passing)})",
           f"  A2 joining adds little (paired t < 2 on a half in >= 5 of 6; IC gain < 0.02 everywhere) -> {'RIGHT' if a2 else 'WRONG'} "
           f"({a2n} of 6; IC gain {min(gain):+.4f} .. {max(gain):+.4f})",
           f"  A3 NEW gbm H7 IC in [0, +0.04] on both halves -> {'RIGHT' if a3 else 'WRONG'} "
           f"({nh7['tu']['ic']['mean']:+.4f} / {nh7['ho']['ic']['mean']:+.4f})",
           f"  A4 ridge's largest coefficient atr_pct at H3 and H7 -> {'RIGHT' if a4 else 'WRONG'} ({ridge_top[3]}, {ridge_top[7]})",
           f"  A5 every H1 ALL cell net negative on both halves -> {'RIGHT' if a5 else 'WRONG'}",
           f"  A6 'position' costs the most IC when dropped (gbm H7) -> {'RIGHT' if top_new == 'position' else 'WRONG'} "
           f"({', '.join(f'{f} {x:+.4f}' for f, x in sorted(loss.items(), key=lambda kv: -kv[1]))})",
           f"  A7 planted rho 0.03 fails the bar, 0.10 meets it -> {'RIGHT' if a7 else 'WRONG'}",
           "", f"run time {time.time() - t0:.0f}s"]
    txt = "\n".join(L_)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
