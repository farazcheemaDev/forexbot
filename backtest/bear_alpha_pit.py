"""PHASE 2 (the thin kills): LONG BTC / SHORT ALTS in bears, on a POINT-IN-TIME alt basket (2026-10-08).

THE KILL (doc 02, "relative-value dispersion as a bear trade", bear_alpha.py): long BTC, short an equal-weight alt
basket, dollar-neutral, weekly, only while blend.btc_bear() says bear: +0.04%/month net - zero. Its short leg was the 11
alts of the 12-coin BOOK, chosen in 2026 because they SURVIVED - the worst possible sample for a short leg (the coins
that died were the best shorts; short_families.py made the same point and re-ran its shorts on 365 PIT coins). Funding
was not charged either. Re-run here on the PIT top-20 alts by prior-month volume (dead coins in, no stables / gold,
BTC excluded), funding charged on both legs (a short receives positive funding), a delisted coin exits at its last
price, 12bp on turnover; the same gate and weekly grid; the bull mirror beside it.

REGISTERED BEFORE RUNNING: the original reproduces ~+0.04%/month (self-check). On the PIT basket the bear leg earns
MORE gross (dying alts in the short leg) but funding and fees take most of it: under +0.5%/month net, negative on one
half - the kill stands on its real reason (fees and funding), not on the sample.

RESULT (2026-10-08, logs/bear_alpha_pit.txt): the original reproduces (+0.04%/month). On the PIT top-20 with funding,
    weeks ending Sunday (the original grid): +0.55%/month (tune +0.69 / holdout +0.34), and as an overlay on
    machine_combos.py's machine it read +18% / +20% over the line. BUT ON THE OTHER SIX WEEKLY ANCHORS it is -0.67,
    -0.53, -0.14, -0.38, +0.10, +0.11 %/month - positive on both halves on 1 of 7. The survivor sample hid a little,
    and the weekday hid the rest: THE KILL STANDS. Predictions: under +0.5 and negative on a half - WRONG on the
    Sunday grid; positive on >= 6 of 7 anchors - WRONG (1 of 7); overlay ties - WRONG on the one lucky anchor.

    python -m backtest.bear_alpha_pit
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest import bear_alpha as BA  # noqa: E402
from backtest import blend  # noqa: E402
from backtest.carry_check import exact_funding  # noqa: E402
from backtest.market_neutral import drop_non_crypto, load_panel  # noqa: E402
from backtest.wide_book import eligibility  # noqa: E402

LOG = ROOT / "logs" / "bear_alpha_pit.txt"
HOLDOUT = pd.Timestamp("2024-04-07")


def pit(C, Fx, bear, direction, n=20, rule="W"):
    el = drop_non_crypto(eligibility(n + 1))
    W = C.resample(rule).last()
    FW = Fx.resample(rule).sum()
    ff = W.ffill()
    rows, w_prev = [], pd.Series(0.0, index=C.columns)
    idx = W.index
    for k in range(len(idx) - 1):
        t, t1 = idx[k], idx[k + 1]
        on = bool(bear.asof(t)) if direction == "bear" else not bool(bear.asof(t))
        w = pd.Series(0.0, index=C.columns)
        m = t.strftime("%Y-%m")
        alts = [s for s in C.columns if s != "BTCUSDT" and m in el.get(s, ()) and np.isfinite(W.at[t, s])]
        if on and len(alts) >= 4 and np.isfinite(W.at[t, "BTCUSDT"]):
            sg = 1.0 if direction == "bear" else -1.0
            w["BTCUSDT"] = 0.5 * sg
            w[alts] = -0.5 * sg / len(alts)
        r = (ff.loc[t1] / W.loc[t] - 1).fillna(0.0)
        gross = float((w * r).sum())
        fund = -float((w * FW.loc[t1].fillna(0.0)).sum())          # a long pays positive funding, a short receives it
        turn = float((w - w_prev).abs().sum())
        rows.append((t1, gross, gross + fund - turn * 6e-4, fund))
        w_prev = w
    return pd.DataFrame(rows, columns=["t", "gross", "net", "fund"]).set_index("t")


def line(d, lab):
    act = d[(d.gross != 0) | (d.net != 0)]
    m = act.net.resample("ME").sum()
    m = m[m != 0]
    geo = lambda x: ((1 + x).prod() ** (1 / max(len(x), 1)) - 1) * 100  # noqa: E731
    return (f"  {lab:46} active weeks {len(act):3d} | net %/month {geo(m):+.2f} (tune {geo(m[m.index < HOLDOUT]):+.2f} / "
            f"holdout {geo(m[m.index >= HOLDOUT]):+.2f}) | gross/wk {act.gross.mean() * 100:+.3f}% funding/wk "
            f"{act.fund.mean() * 100:+.3f}% | months up {(m > 0).mean() * 100:.0f}%")


def main():
    bear = blend.btc_bear()
    lines = [f"backtest/bear_alpha_pit.py, {pd.Timestamp.now():%Y-%m-%d %H:%M}; weekly, dollar-neutral, gate blend.btc_bear()"]
    d0 = BA.dispersion(BA.panel(), bear, "bear")
    lines.append(line(d0.assign(fund=0.0), "ORIGINAL: 11 BOOK alts, no funding (reproduce)"))
    C, F, first = load_panel()
    C.index = C.index.astype("datetime64[ns]")
    Fx = exact_funding(C.index, C.columns).reindex(columns=C.columns).fillna(0.0)
    Fx.index = C.index
    for direction in ("bear", "bull"):
        for n in (20, 40):
            lines.append(line(pit(C, Fx, bear, direction, n), f"PIT top-{n} alts, {direction} leg, funding charged"))
    print("\n".join(lines))
    LOG.write_text("\n".join(lines) + "\n")


if __name__ == "__main__" and "--overlay" not in sys.argv and "--weekdays" not in sys.argv:
    main()


def overlay():
    """Does the PIT bear leg add to the machine ('v2 safe' + daily + improved capitulation, machine_combos.py) against
    that machine's own size line? Weekly net booked on its close day, as the MN book is."""
    from backtest import machine_combos as mc
    from backtest.machine import CUT, summary
    C, F, first = load_panel()
    C.index = C.index.astype("datetime64[ns]")
    Fx = exact_funding(C.index, C.columns).reindex(columns=C.columns).fillna(0.0)
    Fx.index = C.index
    disp = pit(C, Fx, blend.btc_bear(), "bear", 20).net
    P = mc.parts()
    E = dict(trend=1, mn_safe=1, sleeve=1, bids=1, daily=1, capit2=1)
    build = lambda w, k=1.0, extra=0.0: [k * (sum(v * P[s][p] for p, v in w.items())  # noqa: E731
                                              + extra * disp.reindex(P[s].index).fillna(0.0)) for s in mc.SEEDS]
    out = []
    for sp, t0 in (("all 6 years", None), ("last 2 years", CUT)):
        f = sorted((summary(build(E, k), t0)["wm"], summary(build(E, k), t0)["typ"]) for k in np.arange(0.5, 1.61, 0.1))
        for x in (0.0, 1.0, 2.0):
            s = summary(build(E, extra=x), t0)
            ref = float(np.interp(s["wm"], [a for a, _ in f], [b for _, b in f]))
            out.append(f"  {sp:12} machine E + dispersion x{x:.0f}: typical ${s['typ']:,.0f}, worst month {s['wm']:+.1f}%, fall "
                       f"{s['dd']:.0f}% | E's own line at that worst month ${ref:,.0f} ({(s['typ'] / ref - 1) * 100:+.0f}%)")
            print(out[-1], flush=True)
    s0 = pd.concat([P[s]["sleeve"] for s in mc.SEEDS], axis=1).mean(axis=1)
    mo = lambda x: (1 + x).resample("ME").prod() - 1  # noqa: E731
    out.append(f"  monthly correlation with the bear sleeve {mo(disp.reindex(s0.index).fillna(0.0)).corr(mo(s0)):+.2f}")
    print(out[-1])
    with open(LOG, "a") as fh:
        fh.write("\nAS AN OVERLAY ON THE MACHINE (machine_combos.py's E), registered: ties the line (+-5%)\n" + "\n".join(out) + "\n")


if __name__ == "__main__" and "--overlay" in sys.argv:
    overlay()


def weekdays():
    """The rebalance-day check (mn_combos.py found a weekly book can live or die on it): the PIT top-20 bear leg on all
    7 weekly anchors. Registered: positive on both halves on at least 6 of 7."""
    C, F, first = load_panel()
    C.index = C.index.astype("datetime64[ns]")
    Fx = exact_funding(C.index, C.columns).reindex(columns=C.columns).fillna(0.0)
    Fx.index = C.index
    out = []
    for rule in ("W-SUN", "W-MON", "W-TUE", "W-WED", "W-THU", "W-FRI", "W-SAT"):
        out.append(line(pit(C, Fx, blend.btc_bear(), "bear", 20, rule), f"PIT top-20 bear leg, weeks end {rule[2:]}"))
        print(out[-1], flush=True)
    with open(LOG, "a") as fh:
        fh.write(chr(10) + "THE 7 WEEKLY ANCHORS (registered: both halves positive on >= 6 of 7)" + chr(10)
                 + chr(10).join(out) + chr(10))


if __name__ == "__main__" and "--weekdays" in sys.argv:
    weekdays()
