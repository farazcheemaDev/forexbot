"""DOES ANOTHER MARKET MOVE FIRST? The other indices, gold and USDJPY in the seconds before his entries.

At the tick level (his_ticks.py, his_pullback_ticks.py) his 26 clean NASDAQ entries (April on) look
ordinary BEFORE entry - NASDAQ's own 5-minute and 30-second path does not separate them, and a rule
built on it does no better than random (-3.0 against -2.9 points a trade) - yet AFTER entry the price
reaches +7 before -7 in ~88% of them against ~50% at random. He knows something in those seconds that
NASDAQ's own price does not show. A scalper watching several screens may be reading a market that
moves FIRST. This measures, at each clean entry, the sign-aligned moves of US500 (S&P 500), US30 (Dow),
gold and USDJPY over the last 10 / 30 / 60 / 300 seconds - and each one MINUS NASDAQ's own move, scaled
to NASDAQ points - ranked against the same clock second on 20 other days (time-of-day matched).

REGISTERED PREDICTION (2026-09-25, before running): the S&P and Dow move his way in the 30-60 s before
entry more than NASDAQ does (divergence rank > 0.65, p < 0.05): he buys NASDAQ when its peers are
already up and NASDAQ has dipped. Gold and USDJPY show nothing.

    python -m backtest.his_crossmarket
"""
from __future__ import annotations

import sys
from math import erf, sqrt
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
GMT = 5.0
SYMS = ("USTECm", "US500m", "US30m", "XAUUSDm", "USDJPYm")
WINS = (10, 30, 60, 300)


def mids(mt5, sym, t, back=320):
    a = (t - pd.Timedelta(seconds=back)).tz_localize("UTC").to_pydatetime()
    b = (t + pd.Timedelta(seconds=1)).tz_localize("UTC").to_pydatetime()
    k = mt5.copy_ticks_range(sym, a, b, mt5.COPY_TICKS_ALL)
    if k is None or len(k) < 5:
        return None
    d = pd.DataFrame(k)
    d = d[(d.bid > 0) & (d.ask > 0)]
    s = pd.Series(((d.bid + d.ask) / 2).to_numpy(), index=pd.to_datetime(d.time_msc, unit="ms"))
    s = s[~s.index.duplicated(keep="last")]
    out = {}
    for w in WINS + (0,):
        i = s.index.searchsorted(t - pd.Timedelta(seconds=w), side="right") - 1
        out[w] = s.iloc[i] if i >= 0 else np.nan
    return out


def feats(mt5, t, sgn):
    """Sign-aligned relative moves (fraction) per symbol and window, plus peer-minus-NASDAQ."""
    P = {s: mids(mt5, s, t) for s in SYMS}
    if P["USTECm"] is None:
        return None
    f = {}
    for s in SYMS:
        for w in WINS:
            f[f"{s}_{w}"] = (sgn * (P[s][0] / P[s][w] - 1)) if P[s] and P[s][w] else np.nan
    for s in ("US500m", "US30m"):
        for w in WINS:
            f[f"{s}-NDX_{w}"] = f[f"{s}_{w}"] - f[f"USTECm_{w}"]
    return f


def main():
    import MetaTrader5 as mt5
    assert mt5.initialize(), mt5.last_error()
    x = pd.read_csv(ROOT / "strategy_analysis" / "statement_trades.csv", parse_dates=["open_time"])
    x = x[x.symbol.str.startswith("NASDAQ")].copy()
    x["utc"] = x.open_time - pd.Timedelta(hours=GMT)
    x = x[x.utc >= "2026-04-01"]
    x["sgn"] = np.where(x.side == "BUY", 1, -1)
    rng = np.random.default_rng(1)
    ranks = []
    for r in x.itertuples():
        mine = feats(mt5, r.utc, r.sgn)
        if mine is None:
            continue
        ctrl = []
        for k in rng.permutation(np.r_[np.arange(-40, 0), np.arange(1, 41)]):
            ct = r.utc + pd.Timedelta(days=int(k))
            if ct.weekday() >= 5 or ct < pd.Timestamp("2026-03-01"):
                continue
            cf = feats(mt5, ct, r.sgn)
            if cf is not None:
                ctrl.append(cf)
            if len(ctrl) >= 20:
                break
        C = pd.DataFrame(ctrl)
        rec = {}
        for k, v in mine.items():
            c = C[k].dropna()
            rec[k] = np.nan if (not len(c) or np.isnan(v)) else (c < v).mean() + 0.5 * (c == v).mean()
        ranks.append(rec)
    mt5.shutdown()
    R = pd.DataFrame(ranks)
    print(f"{len(R)} clean NASDAQ entries (April on); each feature ranked against the same clock second on ~20 other days "
          f"(0.50 = ordinary; above 0.50 = more in HIS direction).\n")
    print(f"  {'feature':<18}" + "".join(f"{w:>9}s" for w in WINS))
    ps = {}
    for base in ("USTECm", "US500m", "US30m", "XAUUSDm", "USDJPYm", "US500m-NDX", "US30m-NDX"):
        cells = []
        for w in WINS:
            v = R[f"{base}_{w}"].dropna()
            z = (v.mean() - 0.5) / (np.sqrt(1 / 12) / np.sqrt(len(v)))
            p = 2 * (1 - 0.5 * (1 + erf(abs(z) / sqrt(2))))
            ps[f"{base}_{w}"] = p
            cells.append(f"{v.mean():.2f}{'*' if p < 0.05 else ' '}")
        print(f"  {base:<18}" + "".join(f"{c:>10}" for c in cells))
    print("\n  * = two-sided p < 0.05 before correction; there are "
          f"{len(ps)} cells, so a Holm-corrected pass needs p < {0.05 / len(ps):.4f}.")
    best = min(ps, key=ps.get)
    print(f"  strongest: {best} p = {ps[best]:.4f}")


if __name__ == "__main__":
    main()
