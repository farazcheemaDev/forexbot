"""WHAT DOES THE CHART ACTUALLY DO AROUND HIS ENTRIES?

    python -m backtest.his_event_study

WHY LOOK INSTEAD OF TEST
    backtest/his_entries_analysis.py tested pre-chosen hypotheses - fade or follow,
    position in the day's range - and every one came back directionally consistent and
    statistically silent (p 0.20-0.34 on 46 entries). Testing a hypothesis can only
    confirm or deny the hypothesis you brought. It cannot show you the thing you did not
    think to ask about.

    An EVENT STUDY has no hypothesis. Align every entry at t=0, overlay the price path
    either side, and look at the average shape. Whatever he is responding to should be
    visible in the approach; whatever he is capturing should be visible in the exit.

HOW IT IS BUILT, AND THE TWO THINGS THAT WOULD MAKE IT LIE
    * SIGN-ALIGNED. A SELL is flipped so that "up" always means "in his favour" on every
      panel. Without this, longs and shorts cancel and the average is a flat line that
      means nothing.
    * DE-BASED. He trades NASDAQ futures; the bars are the USTECm index CFD, and they
      differ by a rolling basis across three contract months. So every path is expressed
      as POINTS RELATIVE TO THE ENTRY BAR, never as a price. A constant basis cancels
      exactly; only the shape survives, which is all that is wanted.
    * The entry bar is the last bar that CLOSED BEFORE his fill. Nothing after t=0
      informs anything drawn at or before t=0.

WHAT TO LOOK FOR
    approach rising into t=0   -> he BUYS strength / SELLS weakness  (momentum)
    approach falling into t=0  -> he BUYS weakness / SELLS strength  (mean reversion)
    sharp move right after 0   -> he is early to a move
    flat after 0, then drift   -> he is patient, and the exit does the work
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ROOT = Path(__file__).resolve().parents[1]
GMT = 5.0                    # confirmed by the statement header
PRE, POST = 24, 12           # 5m bars: 2h before, 1h after
OUT = ROOT / "logs" / "his_event_study.png"


def bars():
    f = ROOT / "strategy_analysis" / "data" / "USTECm_1m_400d.json"
    g = ROOT / "strategy_analysis" / "data" / "USTECm_5m_400d.json"
    use = g if g.exists() else f
    d = pd.DataFrame(json.load(open(use)))
    d["t"] = pd.to_datetime(d["t"], unit="ms")
    return (d.rename(columns={"o": "open", "h": "high", "l": "low", "c": "close"})
            .set_index("t").sort_index())


def main():
    print(__doc__.split("WHAT TO LOOK FOR")[0].rstrip())
    b = bars()
    d = pd.read_csv(ROOT / "strategy_analysis" / "statement_trades.csv",
                    parse_dates=["open_time", "close_time"])
    n = d[d.symbol.str.contains("NASDAQ")].copy()
    n["utc"] = n.open_time - pd.Timedelta(hours=GMT)
    n["et"] = (n.utc - pd.Timedelta(hours=4)).dt.hour

    paths, meta = [], []
    for _, r in n.iterrows():
        i = b.index.searchsorted(r.utc, side="right") - 1
        if i < PRE or i + POST >= len(b):
            continue
        seg = b["close"].iloc[i - PRE:i + POST + 1].to_numpy(float)
        rel = seg - seg[PRE]                      # points relative to the entry bar
        if r.side == "SELL":
            rel = -rel                            # flip: up is always "his way"
        paths.append(rel)
        meta.append(dict(side=r.side, net=r.net, et=r.et, win=r.net > 0))
    if not paths:
        raise SystemExit("no entries with enough surrounding history")
    P = np.vstack(paths)
    m = pd.DataFrame(meta)
    x = (np.arange(-PRE, POST + 1)) * 5          # minutes
    print(f"\n{len(P)} entries with a full window "
          f"({PRE*5}min before to {POST*5}min after)\n")

    def band(sel, lab):
        if sel.sum() < 4:
            return None
        a = P[sel]
        return dict(lab=lab, n=int(sel.sum()), mu=a.mean(0),
                    se=a.std(0) / np.sqrt(len(a)))

    groups = [band(np.ones(len(P), bool), f"all {len(P)} entries"),
              band((m.et >= 11) & (m.et <= 13), "11:00-13:00 ET"),
              band(~((m.et >= 11) & (m.et <= 13)), "other hours")]
    groups = [g for g in groups if g]

    print(f"  {'group':<20}{'n':>4}{'-60m':>9}{'-30m':>9}{'-10m':>9}"
          f"{'ENTRY':>8}{'+15m':>9}{'+30m':>9}{'+60m':>9}")
    for g in groups:
        def at(mins):
            return g["mu"][np.argmin(np.abs(x - mins))]
        print(f"  {g['lab']:<20}{g['n']:>4}{at(-60):>9.1f}{at(-30):>9.1f}"
              f"{at(-10):>9.1f}{0.0:>8.1f}{at(15):>9.1f}{at(30):>9.1f}{at(60):>9.1f}")
    print("\n  (points, sign-aligned so positive = in his favour. -60m is where price")
    print("   sat an hour BEFORE he entered, relative to his entry.)")

    allg = groups[0]
    pre60, pre10 = allg["mu"][0], allg["mu"][np.argmin(np.abs(x + 10))]
    post30 = allg["mu"][np.argmin(np.abs(x - 30))]
    print("\n" + "=" * 78)
    print("READING THE SHAPE")
    print("=" * 78)
    if pre60 > 2:
        print(f"  Price sat {pre60:+.1f} pts IN HIS FAVOUR an hour before entry and fell")
        print("  toward his entry price => he enters AFTER a move against his direction,")
        print("  i.e. he BUYS pullbacks in an uptrend / SELLS bounces in a downtrend.")
    elif pre60 < -2:
        print(f"  Price sat {pre60:+.1f} pts AGAINST him an hour before entry and rose")
        print("  into it => he enters WITH an established move (momentum).")
    else:
        print(f"  Price was flat ({pre60:+.1f} pts) an hour before entry - no consistent")
        print("  approach shape. Whatever triggers him is not a 1-hour price pattern.")
    print(f"\n  After entry the average path reaches {post30:+.1f} pts by +30min.")
    print(f"  His actual average NASDAQ win is ~{n[n.net>0].net.mean():.0f} USD.")

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(1, 2, figsize=(13, 5.2), sharey=True)
        for a, sel, lab in ((ax[0], np.ones(len(P), bool), f"All {len(P)} NASDAQ entries"),
                            (ax[1], (m.et >= 11) & (m.et <= 13), "11:00-13:00 ET only")):
            if sel.sum() < 4:
                continue
            S = P[sel]
            mu, se = S.mean(0), S.std(0) / np.sqrt(len(S))
            for row in S:
                a.plot(x, row, color="#888", alpha=.13, lw=.8)
            a.fill_between(x, mu - 2 * se, mu + 2 * se, color="#1f77b4", alpha=.25,
                           label="mean +/- 2 s.e.")
            a.plot(x, mu, color="#1f77b4", lw=2.6, label="mean path")
            a.axvline(0, color="#d62728", lw=1.4, ls="--", label="his entry")
            a.axhline(0, color="#333", lw=.7)
            a.set_title(f"{lab}  (n={int(sel.sum())})")
            a.set_xlabel("minutes relative to his entry")
            a.grid(alpha=.25)
            a.legend(loc="upper left", fontsize=8)
        ax[0].set_ylabel("index points, sign-aligned (up = his way)")
        fig.suptitle("What the NASDAQ does around his entries — "
                     "USTECm 5m, GMT+5 confirmed", fontsize=12)
        fig.tight_layout()
        OUT.parent.mkdir(exist_ok=True)
        fig.savefig(OUT, dpi=130)
        print(f"\n  chart written to {OUT}")
    except Exception as e:
        print(f"\n  (plot skipped: {type(e).__name__}: {e})")


if __name__ == "__main__":
    main()
