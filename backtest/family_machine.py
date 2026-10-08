"""THE INDICATOR FAMILIES IN COMBINATION - inside the machine, with the exits, and with every filter (2026-10-09).

daily_families.py ran 10 indicator families (+ ER) as the daily book's ENTRY one at a time, with the 30-day-mean exit,
on their own. Never run: (A) each family as the daily book INSIDE the machine ("E", machine_combos.py), with each of the
three exits that now matter (the 30-day mean; the 20-day mean; the 20-day mean + the BTC exit - daily_stack.py's pass);
(B) each family x each of the 13 daily filters, on its own, against bb's line.
    A  11 entries (bb + 10 families) x 3 exits = 33 machines, $300, 10 orderings (daily boundary rotated), against E's
       own size line at the same worst month, 6 years and the last 2
    B  10 families x 13 filters = 130 daily books, 3 day boundaries x 10 orders, against the bb base's line (PASS =
       both halves, every boundary)

REGISTERED BEFORE RUNNING: A - no family beats bb as the machine's daily book by more than 5% on both spans; the 20-day
+ BTC exit improves the machine's worst month for most entries. B - at most 7 of 130 pass (chance at this many tries).

    python -m backtest.family_machine            (~40 minutes)
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest import daily_combos as dc  # noqa: E402
from backtest import machine_combos as mc  # noqa: E402
from backtest.daily_families import FAM  # noqa: E402
from backtest.machine import CUT, summary  # noqa: E402

LOG = ROOT / "logs" / "family_machine.txt"
EXITS = {"30-day mean": dict(), "20-day mean": dict(mean_n=20), "20-day mean + BTC exit": dict(mean_n=20, btc_exit=True)}


def out(lines, s):
    lines.append(s)
    print(s, flush=True)
    LOG.write_text("\n".join(lines) + "\n")


def main():
    lines = [f"backtest/family_machine.py, {pd.Timestamp.now():%Y-%m-%d %H:%M}", ""]
    P = mc.parts()
    E_ = ("trend", "mn_safe", "sleeve", "bids", "capit2")
    base = {sd: sum(P[sd][p] for p in E_) for sd in mc.SEEDS}
    spans = (("6y", None), ("2y", CUT))
    xs_E = [base[sd] + P[sd]["daily"] for sd in mc.SEEDS]
    line = {sp: sorted((summary([k * x for x in xs_E], t0)["wm"], summary([k * x for x in xs_E], t0)["typ"])
                       for k in np.arange(0.5, 1.61, 0.1)) for sp, t0 in spans}
    out(lines, "A. EACH DAILY ENTRY x EACH EXIT AS THE MACHINE'S DAILY BOOK (E with that daily book): $300 typical year / worst "
               "month, and E's own size line at that worst month, 6y | 2y")
    entries = {"bb(30,1.5)": None, **FAM}
    for en, fn in entries.items():
        for xn, xk in EXITS.items():
            cfg = dict(dc.BASE, entry=fn, **xk)
            T = {off: dc.gen(off, cfg) for off in dc.PHASES}
            xs = []
            for sd in mc.SEEDS:
                off = dc.PHASES[sd % 3]
                d = dc.curve(T[off], dc.allocate(T[off], sd), off).pct_change()
                xs.append(base[sd] + 0.5 * d.reindex(base[sd].index).fillna(0.0))
            cells = []
            for sp, t0 in spans:
                s = summary(xs, t0)
                ref = float(np.interp(s["wm"], [a for a, _ in line[sp]], [b for _, b in line[sp]]))
                cells.append(f"${s['typ']:>6,.0f} {s['wm']:+5.1f}% (line ${ref:>6,.0f}, {(s['typ'] / ref - 1) * 100:+4.0f}%)")
            out(lines, f"  {en:20} {xn:24} " + " | ".join(cells))
    out(lines, "")
    # B: every family x every filter, on its own
    F = {k[2:]: v["filt"] for k, v in dc.variants().items() if k.startswith("F ")}
    bres, _ = dc.run(dc.BASE, dc.LEVS)

    def agg(r, off, key, lev=1.0):
        return np.mean([r[(off, s, lev)][key] for s in dc.SEEDS])

    bl = {off: sorted((agg(bres, off, "fall", lv), agg(bres, off, "tune", lv), agg(bres, off, "hold", lv)) for lv in dc.LEVS)
          for off in dc.PHASES}
    out(lines, f"B. EACH FAMILY x EACH FILTER ({len(FAM)} x {len(F)}), vs bb's line, 3 day boundaries")
    passes = 0
    for en, fn in FAM.items():
        for fnm, ff in F.items():
            r, tr = dc.run(dict(dc.BASE, entry=fn, filt=ff))
            ok, cells = True, []
            for off in dc.PHASES:
                fa = agg(r, off, "fall")
                f_ = [a for a, _, _ in bl[off]]
                dt = agg(r, off, "tune") - np.interp(fa, f_, [b for _, b, _ in bl[off]])
                dh = agg(r, off, "hold") - np.interp(fa, f_, [c for _, _, c in bl[off]])
                ok = ok and dt > 0 and dh > 0
                cells.append(f"{dt * 100:+.0f}/{dh * 100:+.0f}")
            passes += ok
            if ok:
                out(lines, f"  PASS {en} & {fnm}: {'  '.join(cells)} ({np.mean([tr[o][0] for o in dc.PHASES]):.0f} trades)")
    out(lines, f"  B: {passes} of {len(FAM) * len(F)} family x filter books pass")


if __name__ == "__main__":
    main()
