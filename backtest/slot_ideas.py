"""THE SLOT IDEAS, RE-TESTED ON A CAUSAL ALLOCATOR WITH THE LIVE BOT'S POSITION MODEL (rule 9's legitimate reopening).

Mistake #17 (docs/03-mistakes.md, 2026-10-06): graveyard_rescore.taken() freed a slot at the LABEL of the bar a stop is
hit in - for 1h bars its open - so it gave a slot away before the position had closed. It flattered the tune half by
1.3-1.6 %/mo (logs/slot_release.txt). And the live bots run a different position model: one position per coin x sleeve,
a declined signal retried on every later bar, a one-bar pause after an exit (slot_retry.py). The ideas whose verdict
rested on HOW SLOTS ARE HANDED OUT are re-tested here, on the triple (the product's trend book), with the live model and
causal release (slot_retry.simulate defaults: lanes="key", release="close", retry, pause):
  slot count    8 / 16 / 20 against 12 (slots_sweep.py: 16 was tune-only and failed the matched-risk control)
  matched risk  12 slots at 0.40% risk - the control that killed 16 slots: does plain exposure do it better?
  split by side 8 long / 4 short, 10 / 2, 6 / 6 against one shared pool (slot_split.py: shared beat every split)
  per-coin cap  at most 1 or 2 positions per coin across its 3 sleeves - the simplest correlation cap (corr_alloc.py's
                clusters did not exist: 12 coins at ~0.63 pairwise correlation; one coin on three sleeves is the most
                correlated pile-on the book can make)
NOT re-run, and why: slot PRIORITY (slot_priority.py) was killed by a head-to-head of simultaneous signals' R, which
never touched the allocator; correlation CLUSTERS died because the clusters are unstable, also allocator-free.
Each variant paired against the 12-slot book on the same 10 random orderings; gross leverage from every open unit's
notional (risk / stop distance), hour by hour.

PASS (as slots_sweep.py): beat 12 slots on BOTH halves, paired |t| > 2, AND p99 gross leverage under 10x; a slot-count
increase must ALSO beat 12 slots at 0.40% (more exposure the plain way).

REGISTERED PREDICTION (2026-10-06, before running): nothing passes. 16 slots gains more than it did on the old
allocator (crowding costs more here) but fails the matched-risk control again; 8 slots loses return on both halves
with a smaller drawdown; the shared pool beats every split; a 1-per-coin cap loses return and 2-per-coin is about
neutral.

    python -m backtest.slot_ideas
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import blend  # noqa: E402
from backtest.bull_boost import regimes  # noqa: E402
from backtest.slot_retry import RULES, Key, measure, simulate  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SEEDS = range(10)
TS, MU = (100, 2.0), 7                       # the triple: tight exit + time stop + 7 units


def leverage(tr, bear, risk_mult=1.0):
    """gross notional / equity, hour by hour: each open unit carries f / stop-fraction (entry-sized)"""
    ev = []
    for x in tr:
        f = risk_mult * blend.RISK / 100.0 * (blend.REGIME_MULT if bool(bear.asof(x["t0"])) else 1.0)
        for u in x["units"]:
            if u < x["t_out"]:
                ev.append((pd.Timestamp(u).floor("h"), f / x["sf"]))
                ev.append((pd.Timestamp(x["t_out"]).floor("h"), -f / x["sf"]))
    s = pd.Series([v for _, v in ev], index=pd.DatetimeIndex([t for t, _ in ev])).groupby(level=0).sum().sort_index()
    lev = s.cumsum().reindex(pd.date_range(s.index.min(), s.index.max(), freq="h")).ffill().fillna(0.0)
    return float(np.percentile(lev, 99)), float(lev.max()), float((lev > 10).mean() * 100)


def main():
    bear = regimes()[1000]
    keys = [Key(c, r, True) for c in blend.BOOK if blend.load(c) is not None for r in RULES]
    keys = [k for k in keys if len(k.t) >= 300]
    V = {"12 slots (the bot)": dict(),
         "8 slots": dict(slots=8), "16 slots": dict(slots=16), "20 slots": dict(slots=20),
         "split 8 long / 4 short": dict(side_cap={"long": 8, "short": 4}),
         "split 10 long / 2 short": dict(side_cap={"long": 10, "short": 2}),
         "split 6 long / 6 short": dict(side_cap={"long": 6, "short": 6}),
         "max 1 position per coin": dict(coin_cap=1), "max 2 per coin": dict(coin_cap=2)}
    res = {v: {} for v in V}
    res["12 slots at 0.40% risk (control)"] = {}
    levs = {v: [] for v in res}
    cut = None
    for sd in SEEDS:
        for v, kw in V.items():
            tr = simulate(keys, "retry", TS, MU, seed=sd, **kw)
            if cut is None:
                allt = sorted(x["t0"] for x in tr)
                cut = allt[int(len(allt) * 0.6)]
            res[v][sd] = measure(tr, bear, cut)
            if sd < 3:
                levs[v].append(leverage(tr, bear))
            if v == "12 slots (the bot)":
                res["12 slots at 0.40% risk (control)"][sd] = measure(tr, bear, cut, risk_mult=0.40 / 0.30)
                if sd < 3:
                    levs["12 slots at 0.40% risk (control)"].append(leverage(tr, bear, risk_mult=0.40 / 0.30))
        print(f"  ordering {sd} done", flush=True)
    base = res["12 slots (the bot)"]

    def pair(v, h, ref=base):
        d = np.array([res[v][s][h][0] - ref[s][h][0] for s in SEEDS])
        se = d.std(ddof=1) / np.sqrt(len(d))
        return d.mean(), se, int((d > 0).sum())

    out = [f"TRIPLE, live position model + causal release, 10 random orderings, halves split {cut:%Y-%m-%d}; "
           "leverage from orderings 0-2", "",
           f"  {'variant':<34}{'tune %/mo':>10}{'hold %/mo':>10}{'DD t/h':>10}{'vs 12 slots, tune':>24}"
           f"{'vs 12 slots, hold':>24}{'lev p99':>9}{'max':>7}{'>10x':>7}  verdict"]
    for v in res:
        mt = np.mean([res[v][s]["tune"][0] for s in SEEDS]); mh = np.mean([res[v][s]["hold"][0] for s in SEEDS])
        dt = np.mean([res[v][s]["tune"][1] for s in SEEDS]); dh = np.mean([res[v][s]["hold"][1] for s in SEEDS])
        lp99, lmax, lover = np.mean([x[0] for x in levs[v]]), np.mean([x[1] for x in levs[v]]), np.mean([x[2] for x in levs[v]])
        if v == "12 slots (the bot)":
            out.append(f"  {v:<34}{mt:>+9.2f}%{mh:>+9.2f}%{dt:>5.0f}/{dh:<4.0f}{'':>24}{'':>24}{lp99:>8.1f}x{lmax:>6.1f}x{lover:>6.1f}%")
            continue
        (a, sa, wa), (b, sb, wb) = pair(v, "tune"), pair(v, "hold")
        ok = a / sa > 2 and b / sb > 2 and lp99 < 10
        verdict = "PASS" if ok else ("both halves up, not significant" if a > 0 and b > 0 else "fails")
        if ok and v in ("16 slots", "20 slots"):
            (c, sc, wc), (e, se_, we) = pair(v, "tune", res["12 slots at 0.40% risk (control)"]), \
                pair(v, "hold", res["12 slots at 0.40% risk (control)"])
            verdict = "PASS (beats the control too)" if (c / sc > 2 and e / se_ > 2) else \
                f"fails the control (vs 0.40%: {c:+.2f}/{e:+.2f})"
        out.append(f"  {v:<34}{mt:>+9.2f}%{mh:>+9.2f}%{dt:>5.0f}/{dh:<4.0f}{a:>+9.2f} +- {sa:.2f} ({wa}/10){b:>+9.2f} +- {sb:.2f} "
                   f"({wb}/10){lp99:>8.1f}x{lmax:>6.1f}x{lover:>6.1f}%  {verdict}")
    txt = "\n".join(out)
    print(txt)
    (ROOT / "logs" / "slot_ideas.txt").write_text(txt, encoding="utf-8")


if __name__ == "__main__":
    main()
