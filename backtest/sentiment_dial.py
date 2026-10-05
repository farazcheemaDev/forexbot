"""DOES SENTIMENT ADD ANYTHING THE BOOK DOESN'T ALREADY KNOW? The bug hunt on sentiment.py's two passes.

sentiment.py (2026-10-05) found two cells passing both halves and Holm: Fear & Greed's top third against its bottom
third precedes the combo's next 7 days by +8.10 points (+7.20 / +9.16), and retail attention (Wikipedia views, all
four articles) by +7.02 (+5.31 / +9.73). Momentum, not contrarian - the registered prediction was wrong.
The suspect: greed is high AFTER prices rose, and a trend book that is winning keeps winning for a while. If so,
sentiment only restates the book's own momentum and the 1000h BTC gate the bot already uses, and adds nothing.
  1. PARTIAL: the combo's forward 7 days on standardized fg (or att_all) ALONE, then WITH the combo's own trailing
     30-day return, BTC's trailing 30-day return and the 1000h gate (1 = bull) as controls. Newey-West, lag 7.
  2. THE DIAL: the combo's daily returns scaled by the PREVIOUS day's signal - 1.5x in its top third, 1.0x middle,
     0.5x bottom, the thirds from an EXPANDING window (min 180 days, so no future cut-offs) - for fg, att_all, and the
     combo's OWN trailing 30-day return (the control dial). Per half: CAGR, worst fall, Sharpe. Paired on the same
     ordering against the static book: mean difference +- se and wins of 10 (CLAUDE.md, "comparing medians").

REGISTERED PREDICTION (2026-10-05, before running): 1 - fg's t falls below 2 once the book's own momentum and the gate
are in; att_all the same. 2 - as dials both raise Sharpe by at most 0.1 and only on one half, and the own-momentum
dial does as well as either: sentiment adds nothing a book can trade.

    python -m backtest.sentiment_dial
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.bear_chop import fast_run  # noqa: E402
from backtest.bull_boost import regimes  # noqa: E402
from backtest.carry_check import exact_funding  # noqa: E402
from backtest.market_neutral import drop_non_crypto, load_panel  # noqa: E402
from backtest.sentiment import ARTICLES, fng, nw_t, spike, wiki  # noqa: E402
from backtest.wide_book import eligibility  # noqa: E402
from backtest.worst_month import TCACHE  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def ols_nw(y, X, lag=7):
    X = np.c_[np.ones(len(X)), X]
    b = np.linalg.lstsq(X, y, rcond=None)[0]
    e = y - X @ b
    XtX = np.linalg.inv(X.T @ X)
    S = (X * e[:, None]).T @ (X * e[:, None])
    for L in range(1, lag + 1):
        G = (X[L:] * e[L:, None]).T @ (X[:-L] * e[:-L, None])
        S += (1 - L / (lag + 1)) * (G + G.T)
    V = XtX @ S @ XtX
    return b, b / np.sqrt(np.diag(V))


def stats(r):
    c = (1 + r).cumprod()
    yrs = len(r) / 365
    return dict(cagr=c.iloc[-1] ** (1 / yrs) - 1, dd=float((1 - c / c.cummax()).max()),
                sharpe=r.mean() / r.std() * np.sqrt(365) if r.std() > 0 else np.nan)


def tercile_mult(sig):
    """1.5 / 1.0 / 0.5 by the signal's EXPANDING terciles, using only the past; applied the next day"""
    lo = sig.expanding(180).quantile(1 / 3)
    hi = sig.expanding(180).quantile(2 / 3)
    m = pd.Series(1.0, index=sig.index)
    m[sig >= hi] = 1.5
    m[sig <= lo] = 0.5
    m[lo.isna() | sig.isna()] = 1.0
    return m.shift(1).fillna(1.0)


def main():
    C, F, first = load_panel()
    C.index = C.index.astype("datetime64[ns]")
    btc = C["BTCUSDT"].dropna()
    Fx = exact_funding(C.index, C.columns)
    mn = fast_run(C, Fx, first, drop_non_crypto(eligibility(60)), look=30, hold=7, fshift=1)
    mn_d = pd.Series(mn.net.to_numpy(), index=pd.DatetimeIndex(mn.t) + pd.Timedelta(days=7)).groupby(level=0).sum()
    sleeve = pd.read_pickle(ROOT / "logs" / "breadth_real_1x.pkl")["full"]
    cache = pickle.loads(TCACHE.read_bytes())
    R = {}
    for sd in range(10):
        t = cache[("anchor", sd)]
        R[sd] = t + mn_d.reindex(t.index).fillna(0.0) + sleeve.reindex(t.index).fillna(0.0)
    idx = R[0].index
    bear = regimes()[1000]
    gate = (~bear.astype(bool)).astype(float)
    gate.index = pd.DatetimeIndex(gate.index)
    gate_d = gate.resample("D").last().reindex(idx).ffill()
    g = fng()
    att = pd.concat([spike(wiki(a)) for a in ARTICLES], axis=1).mean(axis=1)
    fg_d, att_d = g.reindex(idx), att.reindex(idx)

    # 1. partial regressions (on the 10-ordering mean book)
    combo = pd.concat([(1 + R[sd]).cumprod() for sd in R], axis=1).mean(axis=1)
    y7 = np.log(combo.shift(-7) / combo)
    own30 = np.log(combo / combo.shift(30))
    btc30 = np.log(btc / btc.shift(30)).reindex(idx)
    D = pd.DataFrame({"y": y7, "fg": fg_d.shift(1), "att": att_d.shift(1), "own30": own30, "btc30": btc30,
                      "gate": gate_d}).dropna()
    z = lambda s: (s - s.mean()) / s.std()  # noqa: E731
    out = [f"1. PARTIAL - combo forward 7 days (log), {len(D)} days {D.index.min():%Y-%m-%d}..{D.index.max():%Y-%m-%d}; "
           "coefficient per 1 sd of the feature, in points, Newey-West t"]
    for f in ("fg", "att"):
        b0, t0 = ols_nw(D.y.to_numpy(), z(D[f]).to_numpy()[:, None])
        Xc = np.c_[z(D[f]), z(D.own30), z(D.btc30), D.gate]
        b1, t1 = ols_nw(D.y.to_numpy(), Xc)
        out.append(f"  {f:<4} alone {b0[1]*100:+.2f} (t {t0[1]:+.2f})  |  with own 30d, BTC 30d, gate: {b1[1]*100:+.2f} "
                   f"(t {t1[1]:+.2f});  own 30d t {t1[2]:+.2f}, BTC 30d t {t1[3]:+.2f}, gate t {t1[4]:+.2f}")

    # 2. the dial, per ordering, per half
    cut = idx[int(len(idx) * 0.6)]
    sigs = {"Fear & Greed": fg_d, "attention": att_d}
    res = {k: {"h1": [], "h2": []} for k in ("static", "Fear & Greed", "attention", "own momentum")}
    for sd, r in R.items():
        own = np.log((1 + r).cumprod() / (1 + r).cumprod().shift(30))
        mults = {"static": pd.Series(1.0, index=idx), "Fear & Greed": tercile_mult(fg_d),
                 "attention": tercile_mult(att_d), "own momentum": tercile_mult(own)}
        for k, m in mults.items():
            rr = r * m.reindex(idx).fillna(1.0)
            res[k]["h1"].append(stats(rr[rr.index < cut]) | {"lev": m[m.index < cut].mean()})
            res[k]["h2"].append(stats(rr[rr.index >= cut]) | {"lev": m[m.index >= cut].mean()})
    out.append(f"\n2. THE DIAL (1.5x top third / 1.0x / 0.5x bottom, expanding thirds, next day), 10 orderings; "
               f"halves split {cut:%Y-%m-%d}")
    out.append(f"  {'dial':<14}{'half':<6}{'avg size':>9}{'CAGR':>9}{'worst fall':>12}{'Sharpe':>8}"
               f"{'Sharpe vs static (paired)':>30}")
    for k in res:
        for h in ("h1", "h2"):
            v = pd.DataFrame(res[k][h])
            dS = v.sharpe.to_numpy() - pd.DataFrame(res["static"][h]).sharpe.to_numpy()
            se = dS.std(ddof=1) / np.sqrt(len(dS)) if k != "static" else 0.0
            pair = f"{dS.mean():+.3f} +- {se:.3f}, wins {int((dS > 0).sum())}/10" if k != "static" else ""
            out.append(f"  {k:<14}{h:<6}{v.lev.mean():>9.2f}{v.cagr.median()*100:>+8.0f}%{v.dd.median()*100:>11.0f}%"
                       f"{v.sharpe.median():>8.2f}{pair:>30}")
    txt = "\n".join(out)
    print(txt)
    (ROOT / "logs" / "sentiment_dial.txt").write_text(txt, encoding="utf-8")


if __name__ == "__main__":
    main()
