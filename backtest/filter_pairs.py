"""EVERY PAIR OF FILTERS, and the improved capitulation book against every single change (2026-10-09).

daily_combos.py and capit_combos.py ran each filter ONE AT A TIME. Two filters that fail alone can pass together, so
the goal ("every combination") needs the pairs:
    D  the daily book x every pair of its 13 filters (78), 3 day boundaries x 10 orders, vs the base's leverage line
    C  the capitulation book x every pair of its 15 signal filters plus K>=8 / K>=10 (136), 4 phases x 10 orders
    C2 the IMPROVED book (coin down >= 10% + limit 2% under) against every one of the other 16 filters, the two
       other entries, the three stops, targets +3 / +8 / +10%, and "not working" after 12 / 48 bars - each judged
       against the IMPROVED book's own line (does anything improve the improvement?)
Same rules as the single-filter files: PASS = above the line at the same biggest fall, on the tune half AND the holdout,
at EVERY phase. With ~250 tries a few passes are expected by chance alone; a pass here is a candidate for the forward
paper book, nothing more.

REGISTERED BEFORE RUNNING: D - at most 3 of 78 pass (all singles failed; the pairs that pass will be two "holdout-helping"
filters together); C - the passes are pairs containing a drop filter (BTC -5% or coin -10%), at most 10 of 136; C2 - at
most 2 of ~30 improve on the improved book, and no change to the target or the 4-day rule does.

    python -m backtest.filter_pairs            (D, C and C2; ~35 minutes)
"""
from __future__ import annotations

import itertools
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest import capit_combos as cc  # noqa: E402
from backtest import daily_combos as dc  # noqa: E402

LOG = ROOT / "logs" / "filter_pairs.txt"


def judge(run, base_cfg, cfg, levs, phases, seeds):
    """(ok, cells, mean tune, mean hold, mean fall, trades) against base_cfg's leverage line."""
    base = judge.cache.get(id(run), {}).get(str(sorted(base_cfg.items(), key=str)))
    if base is None:
        base, _ = run(base_cfg, levs)
        judge.cache.setdefault(id(run), {})[str(sorted(base_cfg.items(), key=str))] = base

    def agg(r, off, key, lev=1.0):
        return np.mean([r[(off, s, lev)][key] for s in seeds])

    line = {off: sorted((agg(base, off, "fall", lv), agg(base, off, "tune", lv), agg(base, off, "hold", lv)) for lv in levs)
            for off in phases}
    r, tr = run(cfg)
    cells, ok = [], True
    for off in phases:
        fa = agg(r, off, "fall")
        f = [a for a, _, _ in line[off]]
        dt = agg(r, off, "tune") - np.interp(fa, f, [b for _, b, _ in line[off]])
        dh = agg(r, off, "hold") - np.interp(fa, f, [c for _, _, c in line[off]])
        ok = ok and dt > 0 and dh > 0
        cells.append(f"{dt * 100:+.0f}/{dh * 100:+.0f}")
    return (ok, cells, np.mean([agg(r, o, "tune") for o in phases]), np.mean([agg(r, o, "hold") for o in phases]),
            np.mean([agg(r, o, "fall") for o in phases]), np.mean([tr[o][0] for o in phases]))


judge.cache = {}


def main():
    lines = [f"backtest/filter_pairs.py, {pd.Timestamp.now():%Y-%m-%d %H:%M}", ""]

    def out(s):
        lines.append(s)
        print(s, flush=True)
        LOG.write_text("\n".join(lines) + "\n")

    # D: daily book, every pair of its 13 filters
    F = {k[2:]: v["filt"] for k, v in dc.variants().items() if k.startswith("F ")}
    out(f"D. THE DAILY BOOK x EVERY PAIR OF ITS {len(F)} FILTERS ({len(F) * (len(F) - 1) // 2} pairs), vs the base's line, 3 day "
        f"boundaries: tune/hold above the line by boundary")
    passes = 0
    for (a, fa), (b, fb) in itertools.combinations(F.items(), 2):
        cfg = dict(dc.BASE, filt=(lambda F_, P, i, fa=fa, fb=fb: fa(F_, P, i) and fb(F_, P, i)))
        ok, cells, t, h, fl, n = judge(dc.run, dc.BASE, cfg, dc.LEVS, dc.PHASES, dc.SEEDS)
        passes += ok
        out(f"  {a + ' & ' + b:48} trades {n:5.0f} | CAGR {t * 100:+5.0f}% / {h * 100:+4.0f}% fall {fl * 100:3.0f}% | "
            f"{'  '.join(cells)} -> {'PASS' if ok else 'fail'}")
    out(f"  D: {passes} of {len(F) * (len(F) - 1) // 2} pairs pass")
    out("")
    # C: capitulation book, every pair of its signal filters (K thresholds included as filters)
    CF = {k[2:]: v["filt"] for k, v in cc.variants().items() if k.startswith("F ") and "filt" in v}
    CF["K >= 8"] = lambda S: S.K >= 8
    CF["K >= 10"] = lambda S: S.K >= 10
    out(f"C. THE CAPITULATION BOOK x EVERY PAIR OF ITS {len(CF)} FILTERS ({len(CF) * (len(CF) - 1) // 2} pairs), 4 phases")
    passes = 0
    for (a, fa), (b, fb) in itertools.combinations(CF.items(), 2):
        cfg = dict(cc.BASE, filt=(lambda S, fa=fa, fb=fb: fa(S) & fb(S)))
        try:
            ok, cells, t, h, fl, n = judge(cc.run, cc.BASE, cfg, cc.LEVS, cc.PHASES, cc.SEEDS)
        except (IndexError, ValueError):
            out(f"  {a + ' & ' + b:48} too few trades to score -> fail")
            continue
        passes += ok
        out(f"  {a + ' & ' + b:48} trades {n:5.0f} | CAGR {t * 100:+5.1f}% / {h * 100:+5.1f}% fall {fl * 100:3.0f}% | "
            f"{'  '.join(cells)} -> {'PASS' if ok else 'fail'}")
    out(f"  C: {passes} of {len(CF) * (len(CF) - 1) // 2} pairs pass")
    out("")
    # C2: the improved book against every single change, judged on ITS OWN line
    IMP = dict(cc.BASE, filt=lambda S: S.drop24 <= -0.10, entry=("limit", 0.02, 1))
    ch = {}
    for k, v in CF.items():
        if k == "coin down >= 10% in 24h":
            continue
        ch[f"+ {k}"] = dict(IMP, filt=(lambda S, f=v: (S.drop24 <= -0.10) & f(S)))
    ch["entry: limit 4% instead of 2%"] = dict(IMP, entry=("limit", 0.04, 1))
    ch["entry: limit 3%, live 6 bars"] = dict(IMP, entry=("limit", 0.03, 6))
    for s_ in (0.10, 0.15, 0.25):
        ch[f"stop -{s_:.0%}"] = dict(IMP, stop=s_)
    for tp in (0.03, 0.08, 0.10):
        ch[f"target +{tp:.0%}"] = dict(IMP, tp=tp)
    for nw in (12, 48):
        ch[f"'not working' after {nw} bars"] = dict(IMP, nw=nw)
    out(f"C2. THE IMPROVED CAPITULATION BOOK x EVERY SINGLE CHANGE ({len(ch)}), vs the IMPROVED book's own line, 4 phases")
    passes = 0
    for nm, cfg in ch.items():
        try:
            ok, cells, t, h, fl, n = judge(cc.run, IMP, cfg, cc.LEVS, cc.PHASES, cc.SEEDS)
        except (IndexError, ValueError):
            out(f"  {nm:48} too few trades to score -> fail")
            continue
        passes += ok
        out(f"  {nm:48} trades {n:5.0f} | CAGR {t * 100:+5.1f}% / {h * 100:+5.1f}% fall {fl * 100:3.0f}% | "
            f"{'  '.join(cells)} -> {'PASS' if ok else 'fail'}")
    out(f"  C2: {passes} of {len(ch)} improve on the improved book")


if __name__ == "__main__":
    main()
