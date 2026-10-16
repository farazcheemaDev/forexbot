"""THE FINAL MACHINE WITH CAPIT2 GIVEN ROOM - its capitulation book at 2-3x leverage (2026-10-16)

capit2_lev.py: capit2 alone at 2x (isolated liquidation modelled) doubles its return (+8.6 / +14.3 -> +20.0 / +29.9 %/yr,
tune / holdout) for 2 more points of fall (10 -> 12%), 0.6% of trades liquidated; 3x lifts the holdout again (+43.6) but
the fall reaches 33%. The deployable final machine (final_machine.py DEPLOYABLE, = combo_bot.py --final) carries capit2 at
half the account and 1x. Here the SAME machine, the same 10 orderings, with capit2's book re-allocated at leverage L
(its own liquidations, not the 1x curve scaled) and given a share W of the account:
    W 0.5 / L 1 (the deployed setting - must reproduce final_machine.py's DEPLOYABLE row)
    W 0.5 / L 2,  W 0.5 / L 3,  W 1.0 / L 2
On $300, typical / bad / worst 12 months, worst month, biggest fall - 6 years and the last 2 (summary(), machine.py).
The capitulation book is booked at its trades' closes, as in every machine file.

REGISTERED BEFORE THE RUN (2026-10-16)
    1. The W 0.5 / L 1 row reproduces DEPLOYABLE ($3,400 / $4,735 typical) within 1%.
    2. W 0.5 / L 2 raises the typical year 5-15% on both spans with the worst month within 2 points of the deployed one.
    3. W 1.0 / L 2 and W 0.5 / L 3 add more return but deepen the worst month by > 2 points.

RESULT (2026-10-16, logs/final_capit2_lev.txt) - capit2 at FULL share and 2x lifts the machine at the SAME worst month.
    $300, typical 12 months (6 years / last 2): deployed W0.5 L1 $3,400 / $4,735 (reproduced exactly) | W0.5 L2 $3,666 /
    $4,967 | W0.5 L3 $3,915 / $5,216 | W1.0 L2 $4,098 / $5,494 (+21% / +16%). Worst month -30.0% in every row (it comes
    from the trend book, not capit2); fall 60 -> 57%; months up 59 -> 64%; median month +4.6 -> +7.6% / +7.3 -> +11.4%.
    Predictions: 1 right; 2 wrong by a hair (+7.8 / +4.9%, registered 5-15% on both); 3 wrong - more capit2 did NOT
    deepen the worst month. Caveats: capit2 booked at its trades' closes; the live bot fills capit2 by a market order on
    a 2-minute poll, worth ~0.4 points a trade less than this resting limit (capit2_exec.py); liquidations at 2x modelled
    per position (0.6% of trades). A parameter change to final_books.py is frozen by docs/22 s4 - the user's call.

    python -m backtest.final_capit2_lev
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest import capit_combos as cc  # noqa: E402
from backtest import daily_combos as dc  # noqa: E402
from backtest import final_machine as fm  # noqa: E402
from backtest import machine_combos as mc  # noqa: E402
from backtest import mn_combos as m  # noqa: E402
from backtest.machine import CUT, summary  # noqa: E402
from backtest.moderate_retests import scored_run  # noqa: E402

LOG = ROOT / "logs" / "final_capit2_lev.txt"
CELLS = ((0.5, 1.0), (0.5, 2.0), (0.5, 3.0), (1.0, 2.0))


def main():
    P = mc.parts()
    T625 = fm.trend_capped(6.25)
    D = m.data()
    C = pd.DataFrame(D["X"])
    d = C.diff()
    up = d.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    rsi = (100 - 100 / (1 + up / dn.replace(0, np.nan))).to_numpy()
    mom = D["X"] / np.r_[np.full((30, D["X"].shape[1]), np.nan), D["X"][:-30]] - 1
    T20 = {off: dc.gen(off, dict(dc.BASE, mean_n=20)) for off in dc.PHASES}
    cT2 = {off: cc.gen(off, dict(cc.BASE, **mc.CAPIT_BETTER)) for off in cc.PHASES}
    X = {c: [] for c in CELLS}
    for sd in mc.SEEDS:
        b = P[sd]
        idx = b.index
        o = sd % 7
        r = lambda s: s.reindex(idx).fillna(0.0)  # noqa: E731
        mn_blend = 0.5 * r(scored_run(mom, start=o, stop="short_only", short_stop=0.5)) \
            + 0.5 * r(scored_run(rsi, start=o, stop="short_only", short_stop=0.5))
        carry = r(m.mn_run(look=1, score="funding7", fwin=7, frac=0.2, start=o, stop="short_only", short_stop=0.5))
        off = dc.PHASES[sd % 3]
        daily20 = 0.5 * r(dc.curve(T20[off], dc.allocate(T20[off], sd), off).pct_change())
        rest = T625[sd].reindex(idx).fillna(0.0) + b.sleeve + b.bids + mn_blend + 0.5 * carry + daily20
        coff = cc.PHASES[sd % 4]
        for W, L in CELLS:
            cap2 = cc.curve(cT2[coff], dc.allocate(cT2[coff].assign(units=None), sd, L)).pct_change()
            X[(W, L)].append(rest + W * r(cap2))
    lines = [f"backtest/final_capit2_lev.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; $300, 10 orderings; the deployable "
             f"final machine with capit2 at share W and leverage L; BACKTEST ONLY (trend gains shrunk, the rest raw)", ""]
    S = {}
    for (W, L), xs in X.items():
        for sp, t0 in (("all 6 years", None), ("last 2 years", CUT)):
            s = summary(xs, t0)
            avg, med, up_, bad = fm.months(xs, t0)
            S[(W, L, sp)] = s
            lines.append(f"  capit2 W {W:.1f} L {L:.0f}x  {sp:12} typical ${s['typ']:>6,.0f} / bad ${s['bad']:>6,.0f} / worst ${s['worst']:>5,.0f}"
                         f" | month avg {avg * 100:+5.1f}%, median {med * 100:+5.1f}%, up {up_ * 100:3.0f}% | worst month {s['wm']:+6.1f}%"
                         f" | fall {s['dd']:3.0f}%")
        lines.append("")
    b6, b2 = S[(0.5, 1.0, "all 6 years")], S[(0.5, 1.0, "last 2 years")]
    p1 = abs(b6["typ"] / 3400 - 1) < 0.01 and abs(b2["typ"] / 4735 - 1) < 0.01
    g = [S[(0.5, 2.0, sp)]["typ"] / S[(0.5, 1.0, sp)]["typ"] - 1 for sp in ("all 6 years", "last 2 years")]
    w = [S[(0.5, 2.0, sp)]["wm"] - S[(0.5, 1.0, sp)]["wm"] for sp in ("all 6 years", "last 2 years")]
    p2 = all(0.05 <= x <= 0.15 for x in g) and all(abs(x) <= 2 for x in w)
    p3 = all(S[(c[0], c[1], sp)]["typ"] > S[(0.5, 1.0, sp)]["typ"] and S[(c[0], c[1], sp)]["wm"] < S[(0.5, 1.0, sp)]["wm"] - 2
             for c in ((1.0, 2.0), (0.5, 3.0)) for sp in ("all 6 years", "last 2 years"))
    lines += ["REGISTERED PREDICTIONS",
              f"  1 W0.5 L1 reproduces DEPLOYABLE ($3,400 / $4,735): ${b6['typ']:,.0f} / ${b2['typ']:,.0f} -> {'RIGHT' if p1 else 'WRONG'}",
              f"  2 W0.5 L2: typical {g[0] * 100:+.1f}% / {g[1] * 100:+.1f}%, worst month {w[0]:+.1f} / {w[1]:+.1f} points -> {'RIGHT' if p2 else 'WRONG'}",
              f"  3 W1.0 L2 and W0.5 L3 more return, worst month > 2 points deeper -> {'RIGHT' if p3 else 'WRONG'}"]
    txt = "\n".join(lines)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
