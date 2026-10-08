"""THE HYPOTHETICAL FINAL MACHINE - everything that passed, together, measured once (2026-10-09).

Asked: "hypothetically the final version of the machine after today, adding the successful things - minimum capital,
average month and all". Nothing below runs anywhere; it is the backtest of the combination, built from parts that were
each measured on the fixed loader with the market-neutral rebalance weekday rotated over the 10 orderings:
    E      (machine_combos.py) trend triple (12 coins, gains shrunk for hindsight) + MN with the +50% short-leg exit +
           bear sleeve + capped crash bids + daily Bollinger book (30-day-mean exit) + improved capitulation (capit2)
    FINAL  E, with: the daily book's exit under the 20-day mean (family_machine.py: +8% / +13% in the machine); the MN
           book ranked half by 30-day momentum, half by RSI(14) (mn_blend_rsi.py); funding carry (7-day window, 20%
           basket, +50% short exit) at 0.5x beside it (kill_followups.py)
Reported on $300: typical / bad / worst 12 months, the AVERAGE and the MEDIAN month, the share of months up, the worst
month and the biggest fall - 6 years and the last 2 - at full size and scaled to E's worst month.

REGISTERED BEFORE RUNNING: FINAL's typical year is 5-15% above E's on both spans at about the same worst month; its median
month stays near +2..+5% and about 4 months in 10 still lose.

    python -m backtest.final_machine
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
from backtest import mn_combos as m  # noqa: E402
from backtest.machine import CUT, summary  # noqa: E402
from backtest.moderate_retests import scored_run  # noqa: E402

LOG = ROOT / "logs" / "final_machine.txt"


def months(xs, t0=None):
    mo = []
    for x in xs:
        y = x if t0 is None else x[x.index >= t0]
        c = (1 + y).cumprod()
        me = c.resample("ME").last()
        mo.append((me / me.shift(1)).dropna() - 1)
    a = np.concatenate([v.to_numpy() for v in mo])
    return a.mean(), np.median(a), (a > 0).mean(), (a <= -0.10).mean()


def main():
    P = mc.parts()
    D = m.data()
    C = pd.DataFrame(D["X"])
    d = C.diff()
    up = d.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    rsi = (100 - 100 / (1 + up / dn.replace(0, np.nan))).to_numpy()
    mom = D["X"] / np.r_[np.full((30, D["X"].shape[1]), np.nan), D["X"][:-30]] - 1
    T20 = {off: dc.gen(off, dict(dc.BASE, mean_n=20)) for off in dc.PHASES}
    E, F = [], []
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
        core = b.trend + b.sleeve + b.bids + b.capit2
        E.append(core + b.mn_safe + b.daily)
        F.append(core + mn_blend + 0.5 * carry + daily20)
    lines = [f"backtest/final_machine.py, {pd.Timestamp.now():%Y-%m-%d %H:%M}; $300, 10 orderings (MN weekday, daily boundary, "
             f"capitulation phase rotated); trend gains shrunk for hindsight, everything else raw; BACKTEST ONLY", ""]
    e_wm = summary(E)["wm"]
    g = min(np.round(np.arange(0.4, 1.21, 0.05), 2), key=lambda k: abs(summary([k * x for x in F])["wm"] - e_wm))
    for nm, xs in (("E (current best, measured 10-09)", E), ("FINAL, full size", F),
                   (f"FINAL x{g:.2f} (E's worst month)", [g * x for x in F]), ("FINAL x0.65 (a safer size)", [0.65 * x for x in F])):
        for sp, t0 in (("all 6 years", None), ("last 2 years", CUT)):
            s = summary(xs, t0)
            avg, med, up_, bad = months(xs, t0)
            lines.append(f"  {nm:34} {sp:12} 12 months: typical ${s['typ']:>6,.0f} / bad ${s['bad']:>6,.0f} / worst ${s['worst']:>5,.0f}"
                         f" | month: average {avg * 100:+5.1f}%, median {med * 100:+5.1f}%, up {up_ * 100:3.0f}%, -10% or worse "
                         f"{bad * 100:3.0f}% | worst month {s['wm']:+6.1f}% | biggest fall {s['dd']:3.0f}%")
        lines.append("")
    txt = "\n".join(lines)
    print(txt)
    LOG.write_text(txt + "\n")


if __name__ == "__main__":
    main()
