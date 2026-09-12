"""Hardest available out-of-sample test of the crypto momentum edge.

- FIXED config (no re-fitting anywhere)
- Assets the config was NEVER selected on (DOGE, ADA, LINK, AVAX, XRP, BNB)
- Sequential windows across ~900 days (bull, bear, chop)
- Realistic fees (20bp) and pessimistic (40bp)
- Compared against buy & hold per asset

    python -m backtest.wf_crypto
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.engine import run_backtest  # noqa: E402
from backtest.mass_search import FILTERS, cost_cfg, fetch, gen_signals  # noqa: E402

# assets used in the original search (for reference) vs NEW unseen assets
SEEN = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
UNSEEN = ["DOGEUSDT", "ADAUSDT", "LINKUSDT", "AVAXUSDT", "XRPUSDT", "BNBUSDT"]

CONFIGS = [
    ("roc_mom", (20, 1.0), 2.0, 3.0, "er30"),
    ("rsi_mom", (7, 40, 60), 2.0, 3.0, "er30"),
]
N_WINDOWS = 10


def window_stats(df, fam, p, sl, tp, fn, fee_bp, n_windows=N_WINDOWS):
    """Run the fixed config over sequential windows, compounding equity."""
    size = len(df) // n_windows
    eq = 10000.0
    all_pnl, win_rets = [], []
    for w in range(n_windows):
        part = df.iloc[w * size:(w + 1) * size].reset_index(drop=True)
        if len(part) < 300:
            continue
        cfg = cost_cfg(sl, tp)
        cfg.start_equity = eq
        sig = FILTERS[fn](part, gen_signals(part, fam, p))
        res = run_backtest(part, sig, cfg)
        if len(res.trades) < 5:
            win_rets.append(0.0)
            continue
        pnl = np.array([t.pnl for t in res.trades])
        notion = np.array([t.entry * t.lots for t in res.trades])
        pnl = pnl - notion * (fee_bp / 10000.0)
        start = eq
        eq = eq + pnl.sum()
        all_pnl.extend(pnl.tolist())
        win_rets.append((eq / start - 1) * 100)
    pnl = np.array(all_pnl)
    if len(pnl) < 20:
        return None
    gw, gl = pnl[pnl > 0].sum(), -pnl[pnl < 0].sum()
    curve = 10000 + np.cumsum(pnl)
    peak = np.maximum.accumulate(np.concatenate([[10000.0], curve]))[1:]
    dd = ((peak - curve) / peak).max() * 100
    return dict(trades=len(pnl), pf=gw / gl if gl > 0 else 99.0,
                win=(pnl > 0).mean() * 100, ret=(curve[-1] / 10000 - 1) * 100,
                dd=dd, wins_pos=np.mean([r > 0 for r in win_rets]) * 100,
                nwin=len(win_rets))


def run_set(name, symbols, fee_bp):
    print(f"\n{'='*94}\n{name}  (fee {fee_bp}bp, {N_WINDOWS} sequential windows, FIXED config)\n{'='*94}")
    for fam, p, sl, tp, fn in CONFIGS:
        print(f"\n-- {fam} {p} + {fn} --")
        print(f"  {'asset':10} {'trades':>7} {'pf':>6} {'win%':>6} {'return%':>9} "
              f"{'maxDD%':>8} {'wins/windows':>13} {'buy&hold%':>10}")
        agg = []
        for s in symbols:
            df = fetch(s, "1h", 900)
            r = window_stats(df, fam, p, sl, tp, fn, fee_bp)
            bh = (df.close.iloc[-1] / df.close.iloc[0] - 1) * 100
            if r is None:
                print(f"  {s:10} (insufficient trades)")
                continue
            agg.append(r)
            print(f"  {s:10} {r['trades']:>7} {r['pf']:>6.2f} {r['win']:>6.1f} "
                  f"{r['ret']:>+9.1f} {r['dd']:>8.1f} {r['wins_pos']:>12.0f}% {bh:>+10.1f}")
        if agg:
            print(f"  {'MEAN':10} {np.mean([a['trades'] for a in agg]):>7.0f} "
                  f"{np.mean([a['pf'] for a in agg]):>6.2f} "
                  f"{np.mean([a['win'] for a in agg]):>6.1f} "
                  f"{np.mean([a['ret'] for a in agg]):>+9.1f} "
                  f"{np.mean([a['dd'] for a in agg]):>8.1f} "
                  f"{np.mean([a['wins_pos'] for a in agg]):>12.0f}%")
            pos = sum(1 for a in agg if a['pf'] > 1.0)
            print(f"  -> assets with PF>1: {pos}/{len(agg)}")


def main():
    for fee in (20, 40):
        run_set("UNSEEN ASSETS (never used in the search)", UNSEEN, fee)
    run_set("SEEN ASSETS (used in search - for reference)", SEEN, 20)


if __name__ == "__main__":
    main()
