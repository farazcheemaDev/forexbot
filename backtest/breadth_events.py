"""MARKET-WIDE EXTREMES: capitulation on 1h bars (more signals) and the mirror, euphoria shorts (2026-10-08).

Breadth turned the 4h capitulation buy from fragile into the best candidate here (capitulation_breadth.py,
capitulation_exits.py). Two untested twists:
  1. LONG capitulation on 1h bars with breadth - every 1h version WITHOUT breadth lost (capitulation_freq.py).
  2. SHORT euphoria: RSI(14) crosses OVER 80 with volume > 2x, once >= K coins have done so within the window.
Universe: point-in-time top-40 by prior-month volume, dead coins included; 4h bars at 4 phases, 1h at one. Breadth =
distinct coins with the same-side signal within W hours up to and including the bar (K 5 / 8, W 6 / 24). Exits
+3% / +5% (short: -3% / -5%) or out after 24 bars if not in profit, 7-day cap; 12bp + funding. Account: 10,000 PKR,
8 slots of an eighth, skip while full, 1x / 2x, CAGR.

REGISTERED BEFORE THE RUN (2026-10-08)
    - 1h breadth longs: +0.8..+1.8% a trade, holdout positive, 2-3x the 4h signal count.
    - Euphoria shorts: ~0 or negative in most phases.

RESULT (2026-10-08, logs/breadth_events.txt)
    - 1h breadth longs: tune +1.1..+1.6% a trade, HOLDOUT -0.17..+0.34% - dead (predicted holdout positive: WRONG).
    - Euphoria shorts (1h and 4h): ~0 or mixed, rare; accounts flat - dead (predicted).
    - 4h breadth longs: EVERY W (6/24h) x K (5/8) x target (3/5%) cell is positive in all 4 phases on both halves -
      a plateau, not a peak. Strictest (K >= 8) with +5%: +2.7..+4.1% a trade, ~40-47 a year, t by day +1.4..+8.7;
      10,000 PKR 8-slot account +8..+12%/yr at 1x, +15..+25%/yr at 2x.

    python -m backtest.breadth_events

RE-RUN 2026-10-09 on the FIXED loader (capitulation_wide.halt_cut): until then a data-archive hole cut 51 coins (XRP, SOL,
    LTC ...) at 2022-02-25. Where a RESULT above differs from this file's log, THE LOG IS CURRENT - doc 02, "The archive-hole bug".
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest.capitulation_tp5 import account  # noqa: E402
from backtest.capitulation_wide import four_hour, funding_cum, hourly  # noqa: E402
from backtest.doge_focus import exit_target  # noqa: E402
from backtest.rsi_factors import prep  # noqa: E402
from backtest.wide_book import eligibility  # noqa: E402

LOG = ROOT / "logs" / "breadth_events.txt"
GRIDS = (("4h", 0), ("4h", 60), ("4h", 120), ("4h", 180), ("1h", 0))
BAR_H = {"4h": 4, "1h": 1}
HOLDOUT = pd.Timestamp("2024-04-07")


def one_bars(h, tf, off):
    if tf == "1h":
        return h.rename(columns={"open": "o", "high": "h", "low": "l", "close": "c", "qvol": "v"})[
            ["time", "o", "h", "l", "c", "v"]].reset_index(drop=True)
    return four_hour(h, off)


def breadth(S, hours):
    tt = S.t.to_numpy("datetime64[ns]").astype(np.int64)
    w, lo, out = hours * 3600 * 10 ** 9, 0, []
    for k in range(len(S)):
        while tt[lo] < tt[k] - w:
            lo += 1
        out.append(S.coin.iloc[lo:np.searchsorted(tt, tt[k], side="right")].nunique())
    return np.array(out)


def main():
    t0 = time.time()
    el = eligibility(40)
    H = {s: hourly(s) for s in sorted(s for s, m in el.items() if m)}
    H = {s: h for s, h in H.items() if h is not None}
    rows = []
    for tf, off in GRIDS:
        coins, sigs = {}, []
        for s, h in H.items():
            d = one_bars(h, tf, off)
            if len(d) < 300:
                continue
            P = prep(d, np.full(len(d), np.nan))
            r, v = P["r"], P["v"]
            vavg = pd.Series(v).rolling(20).mean().shift(1).to_numpy()
            spike = v > 2 * vavg
            lo_sig = np.r_[False, (r[:-1] >= 20) & (r[1:] < 20)] & spike
            hi_sig = np.r_[False, (r[:-1] <= 80) & (r[1:] > 80)] & spike
            ym = d.time.dt.strftime("%Y-%m").to_numpy()
            t = d.time.to_numpy()
            for side, sig in ((1, lo_sig), (-1, hi_sig)):
                for i in np.flatnonzero(sig):
                    if 250 <= i < len(r) - 3 and ym[i] in el[s]:
                        sigs.append((t[i], s, i, side))
            coins[s] = (P, funding_cum(s, t, h), t)
        S0 = pd.DataFrame(sigs, columns=["t", "coin", "i", "side"]).sort_values("t", kind="stable").reset_index(drop=True)
        for side in (1, -1):
            S1 = S0[S0.side == side].reset_index(drop=True)
            for W in (6, 24):
                b = breadth(S1, W)
                for K in (5, 8):
                    S = S1[b >= K]
                    for tp in (0.03, 0.05):
                        for s, g in S.groupby("coin"):
                            P, fc, t = coins[s]
                            free = 0
                            for i in g.i:
                                if i < free:
                                    continue
                                j, net, worst, jx = exit_target(i, side, tp, None, 24, P, fc, 7 * 24 // BAR_H[tf])
                                rows.append((tf, off, side, W, K, tp, s, t[i + 1],
                                             t[min(jx, len(t) - 1)] + np.timedelta64(BAR_H[tf], "h"), net, worst))
                                free = j + 1
        print(f"  {tf} +{off} done ({time.time() - t0:.0f}s)", flush=True)
    A = pd.DataFrame(rows, columns=["tf", "off", "side", "W", "K", "tp", "coin", "t_in", "t_out", "net", "worst"])
    A["t_in"], A["t_out"] = pd.to_datetime(A.t_in), pd.to_datetime(A.t_out)
    A.to_csv(ROOT / "logs" / "breadth_events_trades.csv.gz", index=False, compression="gzip")
    span = (A.t_in.max() - A.t_in.min()).days / 365
    lines = [f"backtest/breadth_events.py, {pd.Timestamp.now():%Y-%m-%d %H:%M}; top-40 PIT, {span:.1f} years; per phase: "
             f"trades/yr, avg/trade (tune/holdout), t by day; 10,000 PKR 8-slot CAGR at 1x / 2x", ""]
    for (tf, side, W, K, tp), G in A.groupby(["tf", "side", "W", "K", "tp"]):
        cells = []
        for off, g in G.groupby("off"):
            g = g.sort_values("t_in", kind="stable")
            pdm = g.groupby(g.t_in.dt.floor("D")).net.mean()
            td = pdm.mean() / (pdm.std(ddof=1) / np.sqrt(len(pdm))) if len(pdm) > 2 else np.nan
            c1 = (account(g, 1, 8)[0] / 10_000) ** (1 / span) - 1
            c2 = (max(account(g, 2, 8)[0], 1e-9) / 10_000) ** (1 / span) - 1
            cells.append(f"+{off}m {len(g) / span:4.0f}/yr {g.net.mean() * 100:+.2f}% ({g[g.t_in < HOLDOUT].net.mean() * 100:+.2f}/"
                         f"{g[g.t_in >= HOLDOUT].net.mean() * 100:+.2f}) t {td:+.1f} | {c1 * 100:+.0f}%/{c2 * 100:+.0f}%")
        lines.append(f"{tf} {'LONG ' if side > 0 else 'SHORT'} W{W:>2}h K>={K} tp{tp * 100:.0f}: " + "  ||  ".join(cells))
    txt = "\n".join(lines)
    print(txt)
    LOG.write_text(txt + "\n")


if __name__ == "__main__":
    main()
