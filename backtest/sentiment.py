"""CROWD SENTIMENT AND RETAIL ATTENTION - do they tell us when crypto (and our combo) will do well?

The user, 2026-10-05: "new idea about sentiment analysis, because that drives crypto as well". Already dead here:
Fear & Greed as an ENTRY filter for the bot's trades (entry_features.py: flips sign between halves), funding, open
interest, stablecoin growth, the crowd's long/short positioning as a book (crowd_ls.py: beta), taker flow
(retracted); the Coinbase premium and top traders' positioning only weakly contrarian (doc 12). Never tested:
  - Fear & Greed as a MARKET-TIMING signal (alternative.me, daily from 2018-02, free);
  - RETAIL ATTENTION: English Wikipedia page views of Bitcoin, Cryptocurrency, Ethereum and Dogecoin (Wikimedia
    API, daily from 2015-07, free) - Dogecoin's views are the classic retail-mania gauge.
FEATURES, each known at the end of day d and applied from the close of day d+1 (one extra day of lag):
  fg        Fear & Greed level (0 = extreme fear, 100 = extreme greed)
  fg_chg7   its 7-day change
  att_btc   log Bitcoin views minus their trailing 90-day mean, over the 90-day sd (an attention spike)
  att_doge  the same for Dogecoin
  att_all   the mean of the four articles' spikes
TARGETS (forward, from the close of day d+1):
  btc_7 / btc_30   BTC's 7- / 30-day return
  alt_btc_7        the PIT top-60 alts (equal weight, ex BTC) minus BTC over 7 days: alt strength
  combo_7          the combo book's 7-day return (trend + MN + sleeve, combo_window.py's series, 10 orderings mean)
Top third minus bottom third of each feature, each half of the period (split at 60% of days, as everywhere here),
Newey-West t with lag = the horizon; Holm across all 20 feature x target cells. PASS = the same sign on both halves
AND pooled Holm p < 0.05.

REGISTERED PREDICTION (2026-10-05, before any data): at most one cell passes. Fear & Greed and attention look
contrarian on BTC's 30 days in the first half (high greed / attention spikes -> weaker months) and fade or flip in
the second, as Fear & Greed did at the trade level. Nothing predicts the combo's next 7 days by more than 1 point.

    python -m backtest.sentiment
"""
from __future__ import annotations

import json
import pickle
import sys
import time
import urllib.request
from itertools import product
from math import erf, sqrt
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.bear_chop import fast_run  # noqa: E402
from backtest.carry_check import exact_funding  # noqa: E402
from backtest.market_neutral import drop_non_crypto, load_panel  # noqa: E402
from backtest.wide_book import eligibility  # noqa: E402
from backtest.worst_month import TCACHE  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "strategy_analysis" / "data"
UA = {"User-Agent": "forexbot-research/1.0 (personal research; contact via github farazcheemaDev)"}
ARTICLES = ("Bitcoin", "Cryptocurrency", "Ethereum", "Dogecoin")


def get_json(url):
    return json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read())


def fng():
    f = DATA / "fng.csv"
    if not f.exists():
        d = get_json("https://api.alternative.me/fng/?limit=0&format=json")["data"]
        s = pd.Series({pd.Timestamp(int(x["timestamp"]), unit="s").normalize(): float(x["value"]) for x in d}).sort_index()
        s.rename("fng").to_csv(f)
    return pd.read_csv(f, index_col=0, parse_dates=True).iloc[:, 0]


def wiki(article):
    f = DATA / f"wiki_{article}.csv"
    if not f.exists():
        u = (f"https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/user/"
             f"{article}/daily/20150701/20261004")
        d = get_json(u)["items"]
        s = pd.Series({pd.Timestamp(x["timestamp"][:8]): float(x["views"]) for x in d}).sort_index()
        s.rename(article).to_csv(f)
        time.sleep(1)
    return pd.read_csv(f, index_col=0, parse_dates=True).iloc[:, 0]


def spike(s):
    x = np.log(s.clip(lower=1))
    m, sd = x.rolling(90, min_periods=60).mean(), x.rolling(90, min_periods=60).std()
    return (x - m) / sd


def nw_t(y, x, lag):
    """t of the slope of y on a 0/1 dummy x, Newey-West with `lag`"""
    X = np.c_[np.ones(len(x)), x]
    b = np.linalg.lstsq(X, y, rcond=None)[0]
    e = y - X @ b
    XtX = np.linalg.inv(X.T @ X)
    S = (X * e[:, None]).T @ (X * e[:, None])
    for L in range(1, lag + 1):
        w = 1 - L / (lag + 1)
        G = (X[L:] * e[L:, None]).T @ (X[:-L] * e[:-L, None])
        S += w * (G + G.T)
    V = XtX @ S @ XtX
    return b[1], b[1] / np.sqrt(V[1, 1])


def pz(t):
    return 2 * (1 - 0.5 * (1 + erf(abs(t) / sqrt(2))))


def main():
    C, F, first = load_panel()
    C.index = C.index.astype("datetime64[ns]")
    btc = C["BTCUSDT"].dropna()
    elig = drop_non_crypto(eligibility(60))
    rets = C.pct_change(fill_method=None)
    months = rets.index.strftime("%Y-%m")
    cols = [s for s in elig if s in rets.columns and s != "BTCUSDT"]
    em = pd.DataFrame({s: months.isin(sorted(elig[s])) for s in cols}, index=rets.index)   # top-60 by the PRIOR month
    alt_d = rets[cols].where(em).mean(axis=1)
    alt_idx = (1 + alt_d.fillna(0.0)).cumprod()
    cache = pickle.loads(TCACHE.read_bytes())
    Fx = exact_funding(C.index, C.columns)
    mn = fast_run(C, Fx, first, elig, look=30, hold=7, fshift=1)
    mn_d = pd.Series(mn.net.to_numpy(), index=pd.DatetimeIndex(mn.t) + pd.Timedelta(days=7)).groupby(level=0).sum()
    sleeve = pd.read_pickle(ROOT / "logs" / "breadth_real_1x.pkl")["full"]
    combo = []
    for sd in range(10):
        t = cache[("anchor", sd)]
        combo.append((1 + t + mn_d.reindex(t.index).fillna(0.0) + sleeve.reindex(t.index).fillna(0.0)).cumprod())
    combo_idx = pd.concat(combo, axis=1).mean(axis=1)

    g = fng()
    W = {a: wiki(a) for a in ARTICLES}
    feat = pd.DataFrame({"fg": g, "fg_chg7": g - g.shift(7), "att_btc": spike(W["Bitcoin"]),
                         "att_doge": spike(W["Dogecoin"]),
                         "att_all": pd.concat([spike(W[a]) for a in ARTICLES], axis=1).mean(axis=1)})
    feat = feat.shift(1)                       # known at the end of day d, used from d+1's close
    def fwd(idx, h):
        idx = idx.dropna()
        return np.log(idx.shift(-h) / idx)
    tgt = pd.DataFrame({"btc_7": fwd(btc, 7), "btc_30": fwd(btc, 30),
                        "alt_btc_7": fwd(alt_idx, 7) - fwd(btc, 7), "combo_7": fwd(combo_idx, 7)})
    D = feat.join(tgt, how="inner")
    out = [f"sentiment data: Fear & Greed {g.index.min():%Y-%m-%d}..{g.index.max():%Y-%m-%d}; Wikipedia "
           f"{W['Bitcoin'].index.min():%Y-%m-%d}..{W['Bitcoin'].index.max():%Y-%m-%d}; prices to {btc.index.max():%Y-%m-%d}",
           "top third minus bottom third of the feature: mean forward log return, percentage points "
           "(first half / second half / pooled, Newey-West t)", ""]
    res = {}
    for fname, tname in product(feat.columns, tgt.columns):
        q = D[[fname, tname]].dropna()
        if len(q) < 300:
            continue
        h = int(tname.split("_")[-1])
        cut = q.index[int(len(q) * 0.6)]
        row = {}
        for lab, part in (("h1", q[q.index < cut]), ("h2", q[q.index >= cut]), ("all", q)):
            lo, hi = part[fname].quantile(1 / 3), part[fname].quantile(2 / 3)
            m = (part[fname] <= lo) | (part[fname] >= hi)
            y, x = part[tname][m].to_numpy(), (part[fname][m] >= hi).to_numpy(float)
            row[lab] = nw_t(y, x, h)
        res[(fname, tname)] = row
    ps = {k: pz(v["all"][1]) for k, v in res.items()}
    order = sorted(ps, key=ps.get)
    holm = {k: min(1.0, max(ps[j] * (len(ps) - i) for i, j in enumerate(order[:order.index(k) + 1]))) for k in ps}
    out.append(f"  {'feature':<10}{'target':<11}{'1st half':>10}{'2nd half':>10}{'pooled':>9}{'t':>7}{'Holm':>7}  verdict")
    for (fname, tname), v in res.items():
        same = np.sign(v["h1"][0]) == np.sign(v["h2"][0])
        ok = same and holm[(fname, tname)] < 0.05
        out.append(f"  {fname:<10}{tname:<11}{v['h1'][0]*100:>+9.2f}{v['h2'][0]*100:>+10.2f}{v['all'][0]*100:>+9.2f}"
                   f"{v['all'][1]:>+7.2f}{holm[(fname, tname)]:>7.3f}  {'PASS' if ok else ('same sign' if same else 'flips')}")
    txt = "\n".join(out)
    print(txt)
    (ROOT / "logs" / "sentiment.txt").write_text(txt, encoding="utf-8")


if __name__ == "__main__":
    main()
