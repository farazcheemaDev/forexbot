"""DIVERSIFIED TREND ACROSS 16 MARKETS - the managed-futures design, at Exness costs.

strategy_analysis/his_strategy.md ended with "best automatable approach: a DIVERSIFIED trend portfolio
across many markets". It was never tested in its proper form: backtest/tradfi.py ran the CRYPTO rules
(bb_break, 20xATR trail) on daily bars and lost. This is the textbook design instead - time-series
momentum (Moskowitz, Ooi & Pedersen 2012): hold each market in the direction of its own past return,
sized to equal risk, rebalanced monthly.

UNIVERSE (Yahoo daily, 2004-2026, all tradable as Exness CFDs): EURUSD GBPUSD USDJPY AUDUSD USDCAD
USDCHF NZDUSD, gold, silver, WTI, S&P 500, Nasdaq-100, Dow, DAX, Nikkei, US 10-year note.
RULE: at each month end, position = sign(past return) x (10% / the market's 60-day realised vol),
each market 1/16 of the risk, held one month. PRIMARY lookback 12 months; 3 and 6 shown beside it.
Portfolio scaled so the whole book targets ~10% a year of volatility (on the tune half only - no
holdout information in the scale).
COSTS: turnover x round-trip spread (FX 1.4bp, gold 1.2, silver 9.5, oil 3, indices 1, bond 2) and
SWAP on every position every night it is held: FX 0.49bp, gold 1.25, silver 1.33, oil 2, indices
2.0, bond 1 (forex.py's measured longs, charged both ways - Exness charges negative swap on most
shorts too). Shown with and without swap, because Exness grants SWAP-FREE status to many accounts.

REGISTERED PREDICTION (2026-09-25, before running): gross Sharpe ~0.5 in 2004-2016 and ~0.1 after
(the documented decay of trend-following in the 2010s); with swap, net return negative on the
holdout; swap-free, positive but under 5%/yr at 10% volatility. Verdict: not a book worth running
next to the crypto machine.

    python -m backtest.fx_tsmom
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.fx_anomalies import yf_daily  # noqa: E402

MARKETS = {  # yahoo ticker: (name, spread bp round trip, swap bp per night)
    "EURUSD=X": ("EURUSD", 1.4, 0.49), "GBPUSD=X": ("GBPUSD", 1.5, 0.49), "JPY=X": ("USDJPY", 1.3, 0.49),
    "AUDUSD=X": ("AUDUSD", 1.6, 0.49), "CAD=X": ("USDCAD", 1.8, 0.49), "CHF=X": ("USDCHF", 1.8, 0.49),
    "NZDUSD=X": ("NZDUSD", 2.0, 0.49), "GC=F": ("gold", 1.2, 1.25), "SI=F": ("silver", 9.5, 1.33),
    "CL=F": ("WTI", 3.0, 2.0), "^GSPC": ("S&P 500", 1.0, 2.0), "^NDX": ("Nasdaq-100", 1.0, 2.0),
    "^DJI": ("Dow", 1.0, 2.0), "^GDAXI": ("DAX", 1.0, 2.0), "^N225": ("Nikkei", 1.5, 2.0),
    "ZN=F": ("US 10y note", 2.0, 1.0),
}
START, CUT = "2004-01-01", 0.60
VOL_T = 0.10


def main():
    warnings.filterwarnings("ignore")
    C = {}
    for tk in MARKETS:
        d = yf_daily(tk, start="2003-01-01")
        C[tk] = d.Close
    C = pd.DataFrame(C).sort_index()
    C = C[C.index >= "2003-01-01"].ffill(limit=5)
    R = C.pct_change()
    R = R.where(R.abs() < 0.25)                                   # drop bad prints (roll gaps, glitches)
    vol = R.rolling(60, min_periods=40).std() * np.sqrt(252)
    me = C.resample("ME").last().index
    me = me[(me >= START)]
    days = R.index
    out = {}
    for L in (12, 6, 3):
        past = C / C.shift(21 * L) - 1
        daily = {"gross": [], "net": [], "net_swapfree": []}
        idx = []
        prev_w = pd.Series(0.0, index=C.columns)
        for a, b in zip(me[:-1], me[1:]):
            ia = days.searchsorted(a, side="right") - 1
            s = np.sign(past.iloc[ia])
            v = vol.iloc[ia]
            w = (s * (VOL_T / v) / len(MARKETS)).where(np.isfinite(s) & (v > 0), 0.0).fillna(0.0)
            turn = (w - prev_w).abs()
            sp = pd.Series({tk: MARKETS[tk][1] for tk in MARKETS}) / 1e4
            sw = pd.Series({tk: MARKETS[tk][2] for tk in MARKETS}) / 1e4
            seg = R[(R.index > days[ia]) & (R.index <= b)].fillna(0.0)
            if not len(seg):
                continue
            g = seg.mul(w, axis=1).sum(axis=1)
            nights = pd.Series((seg.index.to_series().diff().dt.days.fillna(1)).to_numpy(), index=seg.index)
            swap = nights * (w.abs() * sw).sum()
            spread = pd.Series(0.0, index=seg.index)
            spread.iloc[0] = (turn * sp).sum() / 2 * 2                # half-spread in, half out
            daily["gross"].append(g)
            daily["net_swapfree"].append(g - spread)
            daily["net"].append(g - spread - swap)
            prev_w = w
        res = {k: pd.concat(v) for k, v in daily.items()}
        cut = res["gross"].index[int(len(res["gross"]) * CUT)]
        k = VOL_T / (res["gross"][res["gross"].index < cut].std() * np.sqrt(252))   # scale on tune only
        out[L] = ({n: s * k for n, s in res.items()}, cut)

    def stats(x):
        ann = x.mean() * 252
        sd = x.std() * np.sqrt(252)
        c = (1 + x).cumprod()
        return ann * 100, ann / sd if sd > 0 else np.nan, (1 - c / c.cummax()).max() * 100

    print("DIVERSIFIED TREND, 16 markets, monthly rebalance, scaled to ~10% volatility (scale set on the tune half)")
    print(f"{'lookback':<10}{'series':<14}{'all: %/yr':>11}{'Sharpe':>8}{'max DD':>8}{'TUNE %/yr':>11}{'Sharpe':>8}"
          f"{'HOLD %/yr':>11}{'Sharpe':>8}")
    for L, (res, cut) in out.items():
        for n in ("gross", "net_swapfree", "net"):
            x = res[n]
            a, s, dd = stats(x)
            ta, ts, _ = stats(x[x.index < cut])
            ha, hs, _ = stats(x[x.index >= cut])
            print(f"{str(L) + ' months':<10}{n:<14}{a:>+10.1f}%{s:>+8.2f}{dd:>7.0f}%{ta:>+10.1f}%{ts:>+8.2f}{ha:>+10.1f}%{hs:>+8.2f}")
        print(f"{'':<10}(tune to {cut:%Y-%m-%d}, holdout after)")
    res, cut = out[12]
    x = res["net_swapfree"]
    print("\n12-month lookback, swap-free net, by year: " + "  ".join(
        f"{y}: {((1 + g).prod() - 1) * 100:+.0f}%" for y, g in x.groupby(x.index.year)))
    x = res["net"]
    print("12-month lookback, WITH swap, by year:    " + "  ".join(
        f"{y}: {((1 + g).prod() - 1) * 100:+.0f}%" for y, g in x.groupby(x.index.year)))


if __name__ == "__main__":
    main()
