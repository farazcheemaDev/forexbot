"""EVERY COMBINATION OF THE BOOKS THAT WORKED - a full factorial, with an honest pick (2026-10-09).

The goal: "run every type of combination we haven't run for the things which worked". The six books that survived
(machine_combos.py's parts, built per ordering with the market-neutral rebalance day, daily boundary and capitulation
phase rotated): trend (v2's triple, gains shrunk for hindsight), mn_safe (MN with the +50% short-leg exit), sleeve (bear
breadth), bids (capped crash bids), daily (daily Bollinger book, half-account), capit2 (improved capitulation,
half-account). Each at 0 / 0.5 / 1: 3^6 - 1 = 728 machines, every one measured ($300, machine.summary: typical / bad /
worst 12 months, worst month, biggest fall) on the FIRST 4 YEARS (before 2024-08-29) and the LAST 2 (from it).

Searching 728 machines and quoting the best is the selection-bias trap this repo exists to avoid. So the pick is made on
the first 4 years only - the best typical year among machines whose worst month there is no worse than v2's own
(as published) - and then READ on the last 2 years, against "E" (machine_combos.py: all six at 1) and "v2 safe" (trend
+ mn_safe + sleeve + bids).

REGISTERED BEFORE RUNNING:
    - every machine without the trend book has a typical year under half of E's on both spans (trend is the engine);
    - the first-4-year pick contains trend, MN and daily; on the last 2 years it lands within +-20% of E's typical year
      at a similar worst month (no hidden combination far better than E);
    - the efficient frontier on the first 4 years keeps at most half of its members efficient on the last 2.

    python -m backtest.machine_factorial
"""
from __future__ import annotations

import itertools
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest import machine_combos as mc  # noqa: E402
from backtest.machine import CUT, summary  # noqa: E402

LOG = ROOT / "logs" / "machine_factorial.txt"
CSV = ROOT / "logs" / "machine_factorial.csv"
BOOKS = ("trend", "mn_safe", "sleeve", "bids", "daily", "capit2")


def frontier(df, typ, wm):
    """Rows not dominated: no other row has a higher typical year AND a less-bad worst month."""
    v = df[[typ, wm]].to_numpy()
    keep = []
    for i, (t, w) in enumerate(v):
        dom = ((v[:, 0] > t) & (v[:, 1] >= w)) | ((v[:, 0] >= t) & (v[:, 1] > w))
        keep.append(not dom.any())
    return df[np.array(keep)]


def main():
    P = mc.parts()
    rows = []
    for ws in itertools.product((0.0, 0.5, 1.0), repeat=len(BOOKS)):
        if not any(ws):
            continue
        xs = [sum(w * P[s][b] for w, b in zip(ws, BOOKS) if w) for s in mc.SEEDS]
        first = summary([x[x.index < CUT] for x in xs])
        last = summary(xs, CUT)
        rows.append(dict(zip(BOOKS, ws), f_typ=first["typ"], f_wm=first["wm"], f_dd=first["dd"], f_worst=first["worst"],
                         l_typ=last["typ"], l_wm=last["wm"], l_dd=last["dd"], l_worst=last["worst"]))
    D = pd.DataFrame(rows)
    D.to_csv(CSV, index=False)
    name = lambda r: " + ".join(f"{b}{'' if r[b] == 1 else ' x0.5'}" for b in BOOKS if r[b]) or "-"  # noqa: E731
    ref = {"v2 as published (lucky MN day)": None}
    E = D[(D[list(BOOKS)] == 1.0).all(axis=1)].iloc[0]
    V2S = D[(D.trend == 1) & (D.mn_safe == 1) & (D.sleeve == 1) & (D.bids == 1) & (D.daily == 0) & (D.capit2 == 0)].iloc[0]
    pub = mc.parts()
    v2p = [pub[s]["trend"] + pub[s]["mn_pub"] + pub[s]["sleeve"] + pub[s]["bids"] for s in mc.SEEDS]
    v2p_first = summary([x[x.index < CUT] for x in v2p])
    del ref
    lines = [f"backtest/machine_factorial.py, {pd.Timestamp.now():%Y-%m-%d %H:%M}; {len(D)} machines (6 books x 0 / 0.5 / 1), "
             f"$300, 10 orderings; first 4 years < {CUT:%Y-%m-%d} <= last 2 years (all rows: {CSV.name})", ""]
    lines.append(f"  E (all six at 1):  first 4y typical ${E.f_typ:,.0f}, worst month {E.f_wm:+.1f}% | last 2y ${E.l_typ:,.0f}, "
                 f"{E.l_wm:+.1f}%, fall {E.l_dd:.0f}%")
    lines.append(f"  v2 safe:           first 4y typical ${V2S.f_typ:,.0f}, worst month {V2S.f_wm:+.1f}% | last 2y "
                 f"${V2S.l_typ:,.0f}, {V2S.l_wm:+.1f}%, fall {V2S.l_dd:.0f}%")
    lines.append(f"  v2 as published:   first 4y worst month {v2p_first['wm']:+.1f}% (the pick's risk ceiling)")
    no_trend = D[D.trend == 0]
    lines.append(f"  machines WITHOUT the trend book: best typical first 4y ${no_trend.f_typ.max():,.0f} / last 2y "
                 f"${no_trend.l_typ.max():,.0f} (E: ${E.f_typ:,.0f} / ${E.l_typ:,.0f})")
    lines.append("")
    pick_pool = D[D.f_wm >= v2p_first["wm"]]
    pick = pick_pool.sort_values("f_typ", ascending=False).iloc[0]
    lines.append(f"THE HONEST PICK (best first-4y typical year with a worst month no worse than v2's {v2p_first['wm']:+.1f}%):")
    lines.append(f"  {name(pick)}")
    lines.append(f"  first 4y: typical ${pick.f_typ:,.0f}, worst month {pick.f_wm:+.1f}%, fall {pick.f_dd:.0f}%")
    lines.append(f"  LAST 2y (never seen by the pick): typical ${pick.l_typ:,.0f}, worst month {pick.l_wm:+.1f}%, fall "
                 f"{pick.l_dd:.0f}%, worst year ${pick.l_worst:,.0f}   vs E ${E.l_typ:,.0f} / {E.l_wm:+.1f}%")
    rank = (D.l_typ > pick.l_typ).sum() + 1
    lines.append(f"  its last-2y typical year ranks {rank} of {len(D)}")
    lines.append("")
    F = frontier(D, "f_typ", "f_wm").sort_values("f_wm")
    FL = frontier(D, "l_typ", "l_wm")
    still = F.index.isin(FL.index)
    lines.append(f"THE FIRST-4Y EFFICIENT FRONTIER: {len(F)} machines; still efficient on the last 2y: {still.sum()}")
    for (i, r), st in zip(F.iterrows(), still):
        lines.append(f"  {name(r):70} 4y ${r.f_typ:>7,.0f} {r.f_wm:+6.1f}% | 2y ${r.l_typ:>7,.0f} {r.l_wm:+6.1f}% "
                     f"{'(still efficient)' if st else ''}")
    lines.append("")
    lines.append("EACH BOOK'S AVERAGE EFFECT across all machines (mean change in typical year / worst month when the book goes "
                 "0 -> 1, other books held fixed), first 4y | last 2y")
    for b in BOOKS:
        others = [x for x in BOOKS if x != b]
        a = D[D[b] == 0].set_index(others)
        c = D[D[b] == 1].set_index(others)
        j = a.join(c, lsuffix="_0", rsuffix="_1", how="inner")
        lines.append(f"  {b:8} typical {np.mean(j.f_typ_1 / j.f_typ_0 - 1) * 100:+6.0f}% worst month "
                     f"{np.mean(j.f_wm_1 - j.f_wm_0):+5.1f} pts | typical {np.mean(j.l_typ_1 / j.l_typ_0 - 1) * 100:+6.0f}% "
                     f"worst month {np.mean(j.l_wm_1 - j.l_wm_0):+5.1f} pts")
    txt = "\n".join(lines)
    print(txt)
    LOG.write_text(txt + "\n")


if __name__ == "__main__":
    main()
