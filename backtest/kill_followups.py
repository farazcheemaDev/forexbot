"""TWO PARTIAL REVERSALS FROM kill_sweeps.py, CHECKED BEFORE THEY ARE BELIEVED (2026-10-09).

1. GRID BOTS: range-gated grids at 4-5% spacing made money on 12-14 of 20 coins (kill_sweeps --grid). Those 20 coins are
   big TODAY (survivors) and the figure is the full history. Here: the same configs split at the holdout (tune / holdout
   %/yr), plus 20 coins that were top-40 perps and later DELISTED (point-in-time-style survivorship check).
2. FUNDING CARRY: with a 20% basket and the +50% short-leg exit it reached Sharpe +1.40 / +0.74 on the 7 weekdays
   (kill_sweeps --carry). Here: as an OVERLAY on the market-neutral book (momentum + RSI, half each - mn_blend_rsi.py),
   carry at 0.5x: does the pair of books beat the MN blend alone on both halves and on the worst weekday?
REGISTERED BEFORE RUNNING: grids - the holdout half is weaker than the tune half and the delisted coins lose (survivors
carried it); carry overlay - it raises the tune-half Sharpe and leaves the holdout within +-0.1 (a tie, not a pass).

    python -m backtest.kill_followups
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

LOG = ROOT / "logs" / "kill_followups.txt"
H = pd.Timestamp("2024-04-07")


def grids(lines):
    from backtest import grid_bot as G
    from backtest.wide_book import eligibility
    survivors = G.COINS + ("ADAUSDT", "LINKUSDT", "AVAXUSDT", "LTCUSDT", "DOTUSDT", "BNBUSDT", "TRXUSDT", "BCHUSDT",
                           "NEARUSDT", "UNIUSDT", "ATOMUSDT", "FILUSDT", "ETCUSDT", "AAVEUSDT", "XLMUSDT")
    el = eligibility(40)
    last = pd.Timestamp("2026-08-01").strftime("%Y-%m")
    dead = [s for s, m in el.items() if m and max(m) < "2025-06" and (G.PERPS / f"{s}_1h.csv.gz").exists()
            and s not in survivors]
    dead = sorted(dead, key=lambda s: -len(el[s]))[:20]
    lines.append(f"1. GRIDS, range-gated, %/yr of one side's ladder capital, tune / holdout (split {H:%Y-%m-%d})")
    for grp, coins in (("20 coins big today", survivors), ("20 top-40 coins that DIED", dead)):
        res = {0.04: [], 0.05: []}
        for sym in coins:
            try:
                h = G.load(sym)
            except Exception:
                continue
            for s in (0.04, 0.05):
                d = G.run(h, s, True)
                yrs = lambda x: max((x.index[-1] - x.index[0]).days / 365.25, 0.1) if len(x) else np.nan  # noqa: E731
                tu, ho = d[d.index < H], d[d.index >= H]
                res[s].append((tu.sum() / yrs(tu) * 100 if len(tu) else np.nan, ho.sum() / yrs(ho) * 100 if len(ho) > 30 else np.nan))
        for s, v in res.items():
            a = np.array(v, float)
            lines.append(f"  {grp:28} {s:.0%} gated: {len(a)} coins | tune median {np.nanmedian(a[:, 0]):+.0f}%/yr, positive "
                         f"{np.nansum(a[:, 0] > 0)}/{np.sum(np.isfinite(a[:, 0]))} | holdout median {np.nanmedian(a[:, 1]):+.0f}%/yr, "
                         f"positive {np.nansum(a[:, 1] > 0)}/{np.sum(np.isfinite(a[:, 1]))}")
        print("\n".join(lines[-2:]), flush=True)


def carry(lines):
    from backtest import mn_combos as m
    from backtest.moderate_retests import scored_run
    D = m.data()
    C = pd.DataFrame(D["X"])
    d = C.diff()
    up = d.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    rsi = (100 - 100 / (1 + up / dn.replace(0, np.nan))).to_numpy()
    mom = D["X"] / np.r_[np.full((30, D["X"].shape[1]), np.nan), D["X"][:-30]] - 1
    lines.append("")
    lines.append("2. FUNDING CARRY (7-day window, 20% basket, +50% short exit) AS AN OVERLAY at 0.5x on the MN blend "
                 "(momentum + RSI half each, +50% exit); Sharpe tune / holdout mean (worst weekday)")
    rows = {"MN blend alone": [], "MN blend + carry x0.5": [], "carry alone": []}
    cors = []
    for o in range(7):
        a = scored_run(mom, start=o, stop="short_only", short_stop=0.5)
        b = scored_run(rsi, start=o, stop="short_only", short_stop=0.5)
        c = m.mn_run(look=1, score="funding7", fwin=7, frac=0.2, start=o, stop="short_only", short_stop=0.5)
        idx = a.index.union(b.index).union(c.index)
        a, b, c = (x.reindex(idx).fillna(0.0) for x in (a, b, c))
        blend = 0.5 * a + 0.5 * b
        rows["MN blend alone"].append(m.stats(blend, 7))
        rows["MN blend + carry x0.5"].append(m.stats(blend + 0.5 * c, 7))
        rows["carry alone"].append(m.stats(c, 7))
        cors.append(blend.corr(c))
    for nm, st in rows.items():
        lines.append(f"  {nm:24} {np.mean([s['tune'] for s in st]):+.2f} / {np.mean([s['hold'] for s in st]):+.2f} "
                     f"({min(s['tune'] for s in st):+.2f} / {min(s['hold'] for s in st):+.2f}), falls "
                     f"{min(s['fall'] for s in st) * 100:.0f}-{max(s['fall'] for s in st) * 100:.0f}%")
    lines.append(f"  correlation, MN blend vs carry: {np.mean(cors):+.2f}")
    print("\n".join(lines[-5:]), flush=True)


def main():
    lines = [f"backtest/kill_followups.py, {pd.Timestamp.now():%Y-%m-%d %H:%M}", ""]
    grids(lines)
    carry(lines)
    LOG.write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
