"""HOW MUCH OF THE MACHINE IS JUST BTC? THE residual-edge-analyzer METHOD, APPLIED TO OUR OWN BOOKS (2026-10-27)

From tradermonty/claude-trading-skills (residual-edge-analyzer): separate a strategy's returns into a DECLARED baseline
exposure and a residual, by OLS with HAC (Newey-West) standard errors, rolling stability and a regime breakdown; the baseline
must be declared BEFORE looking at the residual, a plausible simple copy of the strategy, with an alternate for sensitivity.
It is a validation method, not a trading rule - so this file asks one question of the repo's own backtest: is the machine's
backtest return an edge or BTC (and alt) beta in a bull market?

DATA   logs/chop_gap_months.pkl (backtest/chop_gap.py, 2026-10-18): the 9-book final machine's MONTHLY return per book and for
       the account, 2020-03 .. 2026-08, 10 orderings (MN weekday, daily boundary, capitulation phase rotated), $300, the TREND
       book's gains shrunk 3x for hindsight and its losses kept (so a trend alpha here is UNDERSTATED by design; everything
       else raw). BASELINES, declared now: PRIMARY = long BTC (Binance perp, month-end to month-end); ALTERNATE = equal-weight
       long of the 12-coin trend book universe (blend.BOOK). Per ordering and on the mean of the orderings.
METHOD r_book = alpha + beta x baseline + e; HAC with 2 monthly lags; alpha annualised x12; R2; rolling 24-month alpha; alpha
       by the month's BTC regime label (bull / chop / bear).

REGISTERED BEFORE THE FIRST RUN (2026-10-27)
  Z1  The account's BTC beta is between 0.2 and 0.8 and its R2 under 0.5 (long-biased but diversified by the other books).
  Z2  The account's alpha over BTC is positive with HAC t under 2 (a trend book shrunk 3x leaves little to find).
  Z3  The trend book's beta is the largest of the nine books and its R2 the highest; MN, carry, news and capit2 have betas
      under 0.2 in absolute value.
  Z4  Alpha is concentrated in BULL months: bull alpha > 0, chop and bear alpha under bull alpha (the machine is a bull-market
      amplifier - CLAUDE.md s6).
  Z5  The conclusion does not change with the alternate baseline: the sign of the account's alpha is the same.
READING  alpha t >= 2 on the account and positive in all three regimes -> a residual edge worth the name; otherwise the backtest
         return is mostly exposure and the forward record has to supply the rest.

    python -m backtest.residual_edge
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
DATA = ROOT / "strategy_analysis" / "data"
LOG = ROOT / "logs" / "residual_edge.txt"
BOOKS = ["trend", "mn", "carry", "sleeve", "daily", "capit2", "news", "ndx", "account"]


def monthly_close(sym):
    rows = json.load(open(DATA / f"{sym}USDT_1h_2400d.json"))
    d = pd.DataFrame(rows)
    d["t"] = pd.to_datetime(d.t, unit="ms")
    s = d.set_index("t").c.astype(float)
    return s.resample("ME").last()


def baselines():
    btc = monthly_close("BTC")
    from backtest import blend
    cols = {}
    for c in blend.BOOK:
        base = c.replace("USDT", "")
        try:
            cols[base] = monthly_close(base).pct_change()
        except Exception:
            continue
    ew = pd.DataFrame(cols).mean(axis=1, skipna=True)
    out = pd.DataFrame(dict(btc=btc.pct_change(), ew12=ew))
    out.index = out.index.to_period("M").astype(str)
    return out


def ols_hac(y, X, lags=2):
    """OLS with an intercept; Newey-West covariance. Returns coef, t-stats, R2."""
    n = len(y)
    Z = np.column_stack([np.ones(n), X])
    b = np.linalg.lstsq(Z, y, rcond=None)[0]
    e = y - Z @ b
    S = (Z * e[:, None]).T @ (Z * e[:, None])
    for L in range(1, lags + 1):
        w = 1 - L / (lags + 1)
        G = (Z[L:] * e[L:, None]).T @ (Z[:-L] * e[:-L, None])
        S += w * (G + G.T)
    XtXi = np.linalg.inv(Z.T @ Z)
    V = XtXi @ S @ XtXi
    t = b / np.sqrt(np.diag(V))
    r2 = 1 - (e ** 2).sum() / ((y - y.mean()) ** 2).sum()
    return b, t, r2, e


def main():
    P = pd.read_pickle(ROOT / "logs" / "chop_gap_months.pkl")
    B = baselines()
    mean_p = P.groupby("month")[BOOKS].mean()
    reg = P[P.order == 0].set_index("month").reg
    common = mean_p.index.intersection(B.dropna().index)
    mean_p, B, reg = mean_p.loc[common], B.loc[common], reg.loc[common]
    L = [f"backtest/residual_edge.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; {len(common)} months {common[0]} .. {common[-1]}; "
         f"returns are monthly, mean of 10 orderings; trend gains shrunk 3x (alpha understated)", ""]
    res = {}
    for bn, bl in (("BTC", "btc"), ("EW12", "ew12")):
        L.append(f"-- baseline {bn}: mean monthly {B[bl].mean() * 100:+.1f}%, sd {B[bl].std() * 100:.1f}%")
        L.append(f"   {'book':8} {'mean mo':>8} {'beta':>6} {'t(b)':>6} {'alpha/yr':>9} {'t(a)':>6} {'R2':>5} | alpha by regime (%/mo): bull / chop / bear")
        for bk in BOOKS:
            y = mean_p[bk].to_numpy(float)
            b, t, r2, e = ols_hac(y, B[bl].to_numpy(float))
            ev = pd.Series(e, index=common)
            rg = {k: ev[reg == k].mean() * 100 + 0 for k in ("bull", "chop", "bear")}
            res[(bn, bk)] = (b[0], t[0], b[1], t[1], r2, rg)
            L.append(f"   {bk:8} {y.mean() * 100:>+7.2f}% {b[1]:>6.2f} {t[1]:>6.1f} {b[0] * 1200:>+8.1f}% {t[0]:>6.1f} {r2:>5.2f} | "
                     f"{rg['bull']:>+6.2f} / {rg['chop']:>+6.2f} / {rg['bear']:>+6.2f}")
        L.append("")
    # per-ordering dispersion of the account's alpha over BTC
    al = []
    for o in range(10):
        po = P[P.order == o].set_index("month").loc[common]
        b, t, r2, _ = ols_hac(po["account"].to_numpy(float), B["btc"].to_numpy(float))
        al.append((b[0] * 1200, t[0], b[1]))
    al = np.array(al)
    L.append(f"-- account over BTC, by ordering: alpha/yr {al[:, 0].min():+.1f}% .. {al[:, 0].max():+.1f}% (mean {al[:, 0].mean():+.1f}%), "
             f"t(alpha) {al[:, 1].min():+.1f} .. {al[:, 1].max():+.1f}, beta {al[:, 2].min():.2f} .. {al[:, 2].max():.2f}")
    # rolling stability
    y, x = mean_p["account"].to_numpy(float), B["btc"].to_numpy(float)
    roll = []
    for i in range(24, len(y) + 1):
        b, _, _, _ = ols_hac(y[i - 24:i], x[i - 24:i])
        roll.append(b[0] * 1200)
    L.append(f"-- rolling 24-month alpha/yr over BTC: min {min(roll):+.1f}%  median {np.median(roll):+.1f}%  max {max(roll):+.1f}%  "
             f"share of windows > 0: {np.mean(np.array(roll) > 0) * 100:.0f}%")
    # predictions
    a = res[("BTC", "account")]
    z1 = 0.2 <= a[2] <= 0.8 and a[4] < 0.5
    z2 = a[0] > 0 and a[1] < 2
    betas = {bk: res[("BTC", bk)][2] for bk in BOOKS if bk != "account"}
    r2s = {bk: res[("BTC", bk)][4] for bk in BOOKS if bk != "account"}
    z3 = max(betas, key=betas.get) == "trend" and max(r2s, key=r2s.get) == "trend" and all(abs(betas[k]) < 0.2 for k in ("mn", "carry", "news", "capit2"))
    rg = a[5]
    z4 = rg["bull"] > 0 and rg["chop"] < rg["bull"] and rg["bear"] < rg["bull"]
    z5 = np.sign(res[("EW12", "account")][0]) == np.sign(a[0])
    L += ["", "REGISTERED PREDICTIONS",
          f"  Z1 account beta over BTC 0.2-0.8 and R2 < 0.5 (beta {a[2]:.2f}, R2 {a[4]:.2f}) -> {'RIGHT' if z1 else 'WRONG'}",
          f"  Z2 alpha positive, HAC t < 2 (alpha {a[0] * 1200:+.1f}%/yr, t {a[1]:+.1f}) -> {'RIGHT' if z2 else 'WRONG'}",
          f"  Z3 trend has the largest beta and R2; mn/carry/news/capit2 |beta| < 0.2 -> {'RIGHT' if z3 else 'WRONG'} "
          f"(betas: " + ", ".join(f"{k} {v:+.2f}" for k, v in betas.items()) + ")",
          f"  Z4 alpha concentrated in bull months (bull {rg['bull']:+.2f} / chop {rg['chop']:+.2f} / bear {rg['bear']:+.2f} %/mo) -> {'RIGHT' if z4 else 'WRONG'}",
          f"  Z5 same alpha sign over the 12-coin equal-weight baseline -> {'RIGHT' if z5 else 'WRONG'}"]
    txt = "\n".join(L)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
