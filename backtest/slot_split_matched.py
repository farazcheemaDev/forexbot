"""SLOTS SPLIT BY SIDE AT MATCHED DRAWDOWN - is a long/short split a better deployment of risk, or just less of it?

slot_ideas.py (2026-10-06, causal allocator + the live bot's position model, the triple, 10 orderings): every long/short
split loses return on the tune half and gains on the holdout (8 long / 4 short -1.74 / +2.21, 6 / 6 -2.37 / +1.10) -
so none passes - but with far shallower falls (8/4: 49% / 45%, 6/6: 37% / 39%, against the shared 12's 64% / 56%).
Less drawdown for less return is what betting smaller also buys. The question that decides it, the same control that
made MAX_UNITS = 7 believable (doc 11 part 8): at the SAME drawdown, which earns more?
For each ordering and each half: the shared-12 book scaled by k (risk x k, k = 0.30 .. 1.00) gives a return-for-drawdown
curve; it is read at the split's own drawdown (linear interpolation) and paired against the split's return.
Scaling the SHARED book down, not the split up, keeps every comparison under the 10x leverage line.

REGISTERED PREDICTION (2026-10-06, before running): at matched drawdown a split beats the shared pool on the holdout
(by +1 to +2 %/mo) but not on the tune half, so it fails the both-halves bar like every other holdout-only result.

    python -m backtest.slot_split_matched
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import blend  # noqa: E402
from backtest.bull_boost import regimes  # noqa: E402
from backtest.slot_ideas import MU, TS  # noqa: E402
from backtest.slot_retry import RULES, Key, measure, simulate  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SEEDS = range(10)
KS = np.round(np.arange(0.30, 1.001, 0.05), 2)


def main():
    bear = regimes()[1000]
    keys = [Key(c, r, True) for c in blend.BOOK if blend.load(c) is not None for r in RULES]
    keys = [k for k in keys if len(k.t) >= 300]
    splits = {"8 long / 4 short": {"long": 8, "short": 4}, "6 long / 6 short": {"long": 6, "short": 6},
              "10 long / 2 short": {"long": 10, "short": 2}}
    diffs = {s: {"tune": [], "hold": []} for s in splits}
    info = {s: {"tune": [], "hold": []} for s in splits}
    cut = None
    for sd in SEEDS:
        base = simulate(keys, "retry", TS, MU, seed=sd)
        if cut is None:
            allt = sorted(x["t0"] for x in base)
            cut = allt[int(len(allt) * 0.6)]
        curve_k = {k: measure(base, bear, cut, risk_mult=k) for k in KS}
        for s, cap in splits.items():
            m = measure(simulate(keys, "retry", TS, MU, seed=sd, side_cap=cap), bear, cut)
            for h in ("tune", "hold"):
                dd = np.array([curve_k[k][h][1] for k in KS]); ret = np.array([curve_k[k][h][0] for k in KS])
                o = np.argsort(dd)
                matched = float(np.interp(m[h][1], dd[o], ret[o]))
                diffs[s][h].append(m[h][0] - matched)
                info[s][h].append((m[h][0], m[h][1], matched))
        print(f"  ordering {sd} done", flush=True)
    out = [f"TRIPLE, causal allocator + live position model, 10 orderings, halves split {cut:%Y-%m-%d}: each split against the "
           "shared 12 SCALED DOWN to the split's own drawdown", "",
           f"  {'split':<20}{'half':<6}{'split %/mo':>11}{'its DD':>8}{'shared 12 at that DD':>22}{'split - shared, paired':>30}"]
    for s in splits:
        for h in ("tune", "hold"):
            d = np.array(diffs[s][h]); se = d.std(ddof=1) / np.sqrt(len(d))
            r, dd, mt = (np.mean([x[i] for x in info[s][h]]) for i in range(3))
            out.append(f"  {s:<20}{h:<6}{r:>+10.2f}%{dd:>7.0f}%{mt:>+21.2f}%{d.mean():>+14.2f} +- {se:.2f} ({int((d > 0).sum())}/10)")
        dt, dh = np.array(diffs[s]["tune"]), np.array(diffs[s]["hold"])
        ok = all(x.mean() / (x.std(ddof=1) / np.sqrt(len(x))) > 2 for x in (dt, dh))
        out.append(f"  {'':<20}-> {'PASSES: a better deployment of risk on both halves' if ok else 'fails the both-halves bar'}")
    txt = "\n".join(out)
    print(txt)
    (ROOT / "logs" / "slot_split_matched.txt").write_text(txt, encoding="utf-8")


def phases():
    """The adoption bar (the tight exit and MAX_UNITS = 7 both met it): BOTH halves on ALL FOUR bar phases. Phase p moves
    the 4h grid by p hours and the 12h grid by 3p (bar_phase.py). Here the WHOLE sleeve moves - longs and shorts - since
    the live bot holds one position per coin x sleeve; bar_phase.py moved only the long sleeves. Only the split that
    passed on phase 0 (6 long / 6 short) is carried forward.
    REGISTERED PREDICTION (2026-10-06, before running): its matched-drawdown advantage holds on both halves in all four
    phases (a structural effect - capping correlated longs - not a timing one)."""
    bear = regimes()[1000]
    out = ["6 LONG / 6 SHORT against the shared 12 scaled to the split's drawdown, per bar phase (10 orderings each)", "",
           f"  {'phase':<8}{'half':<6}{'split %/mo':>11}{'its DD':>8}{'shared at that DD':>19}{'split - shared, paired':>30}"]
    verdicts = []
    for p in (0, 1, 2, 3):
        offs = {"1h": 0, "4h": p, "12h": 3 * p}
        keys = [Key(c, r, True, offset=offs[r]) for c in blend.BOOK if blend.load(c) is not None for r in RULES]
        keys = [k for k in keys if len(k.t) >= 300]
        cut, D, I = None, {"tune": [], "hold": []}, {"tune": [], "hold": []}
        for sd in SEEDS:
            base = simulate(keys, "retry", TS, MU, seed=sd)
            if cut is None:
                allt = sorted(x["t0"] for x in base)
                cut = allt[int(len(allt) * 0.6)]
            ck = {k: measure(base, bear, cut, risk_mult=k) for k in KS}
            m = measure(simulate(keys, "retry", TS, MU, seed=sd, side_cap={"long": 6, "short": 6}), bear, cut)
            for h in ("tune", "hold"):
                dd = np.array([ck[k][h][1] for k in KS]); ret = np.array([ck[k][h][0] for k in KS])
                o = np.argsort(dd)
                mt = float(np.interp(m[h][1], dd[o], ret[o]))
                D[h].append(m[h][0] - mt); I[h].append((m[h][0], m[h][1], mt))
        ok = True
        for h in ("tune", "hold"):
            d = np.array(D[h]); se = d.std(ddof=1) / np.sqrt(len(d))
            ok = ok and d.mean() / se > 2
            r, dd, mt = (np.mean([x[i] for x in I[h]]) for i in range(3))
            out.append(f"  {p:<8}{h:<6}{r:>+10.2f}%{dd:>7.0f}%{mt:>+18.2f}%{d.mean():>+14.2f} +- {se:.2f} ({int((d > 0).sum())}/10)")
        verdicts.append(ok)
        print(f"  phase {p} done", flush=True)
    out.append(f"\n  both halves > 2 paired se on {sum(verdicts)} of 4 phases -> "
               f"{'PASSES the four-phase bar' if all(verdicts) else 'fails the four-phase bar'}")
    txt = "\n".join(out)
    print(txt)
    (ROOT / "logs" / "slot_split_phases.txt").write_text(txt, encoding="utf-8")


if __name__ == "__main__":
    if "--phases" in sys.argv:
        phases()
    else:
        main()
