"""WHAT SEPARATES THE MOVES HE TOOK FROM THE ONES HE IGNORED?

    python -m backtest.his_trigger

THE RIGHT QUESTION
    Sections 17 and 18 described his entries in isolation, which can only ever say what
    they look like on average. It cannot say what makes one 20-point move worth taking
    and the 20-point move an hour earlier not worth taking - because it never looks at
    the ones he skipped.

    So: build the OPPORTUNITY SET. Every 5m bar in the same hours and on the same days he
    traded is a moment he could have entered and mostly did not. 39 positives against
    thousands of controls is a discriminative problem, and discriminative problems are
    far easier than descriptive ones - a feature only has to separate, not explain.

MAKING CONTROLS COMPARABLE
    His features are computed in HIS trade's direction. A control bar has no direction,
    so one has to be assigned, and assigning it randomly would add noise that buries the
    signal. Section 18 established he enters WITH the prior move, so each control is
    given the direction of its own preceding 60-minute move. Controls are therefore
    "what a momentum trader would have done here", which is the correct comparison: the
    question is not why he trades with momentum - that is settled - but which momentum
    moments he picks.

THE MULTIPLE-COMPARISON TRAP, HANDLED BEFORE LOOKING
    Ten features against 39 positives will produce a p<0.05 by chance roughly 40% of the
    time. So:
      * every feature is declared in FEATURES below, before any result is seen
      * p-values are Holm-corrected across the whole family
      * the entries are SPLIT: features are ranked on the first 2/3 by date and the
        survivor is re-tested on the last 1/3, which never informed the ranking
    A feature that only survives the uncorrected test is reported as not surviving.

REGISTERED PREDICTION (2026-09-16, before running)
    Move SIZE and SPEED separate weakly at best - if simply "20 points in an hour" were
    the trigger he would trade many times a day, and he trades ~5 times a month. The
    stronger candidates are the ones that make a move rare rather than large: a new
    session extreme, or range EXPANSION after a quiet period. I expect at most one
    feature to survive Holm correction, and quite possibly none - in which case the
    honest answer is that his selection is judgment and this file closes the question.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ROOT = Path(__file__).resolve().parents[1]
GMT = 5.0
rng = np.random.default_rng(17)

# Declared BEFORE looking at any result. Each is (name, description).
FEATURES = [
    ("move60", "size of the prior 60min move, in his direction (pts)"),
    ("move15", "size of the prior 15min move (pts)"),
    ("speed", "prior 15min move divided by prior 60min move (burst vs grind)"),
    ("move60_atr", "prior 60min move in ATR units (size, volatility-normalised)"),
    ("atr_ratio", "recent 1h ATR vs the prior 4h ATR (expansion vs contraction)"),
    ("new_extreme", "is price at a new session extreme in his direction (0/1)"),
    ("day_pos", "position in the session range so far (0=low, 1=high)"),
    ("run", "consecutive 5m bars closing in his direction"),
    ("from_open", "distance from the session open, in ATR units"),
    ("mins_in", "minutes since the US cash open"),
]


def bars():
    f = ROOT / "strategy_analysis" / "data" / "USTECm_5m_400d.json"
    d = pd.DataFrame(json.load(open(f)))
    d["t"] = pd.to_datetime(d["t"], unit="ms")
    return (d.rename(columns={"o": "open", "h": "high", "l": "low", "c": "close"})
            .set_index("t").sort_index())


def featurise(b, i, direction):
    """Features at bar i, expressed in `direction` (+1 long, -1 short). Uses only
    bars up to and including i - nothing after it informs anything here."""
    c = b["close"].to_numpy()
    h, l = b["high"].to_numpy(), b["low"].to_numpy()
    if i < 60:
        return None
    px = c[i]
    m60 = (px - c[i - 12]) * direction
    m15 = (px - c[i - 3]) * direction
    tr = (h[i - 48:i + 1] - l[i - 48:i + 1])
    atr4 = float(tr.mean()) or 1.0
    atr1 = float((h[i - 12:i + 1] - l[i - 12:i + 1]).mean()) or 1.0
    t = b.index[i]
    day = b.loc[(b.index >= t.normalize()) & (b.index <= t)]
    lo, hi = float(day["low"].min()), float(day["high"].max())
    op = float(day["close"].iloc[0])
    ext = (px >= hi - 1e-9) if direction > 0 else (px <= lo + 1e-9)
    run = 0
    for k in range(i, max(i - 12, 0), -1):
        if (c[k] - c[k - 1]) * direction > 0:
            run += 1
        else:
            break
    pos = (px - lo) / (hi - lo) if hi > lo else .5
    # US cash open is 13:30 UTC
    mins = (t - t.normalize() - pd.Timedelta(hours=13, minutes=30)).total_seconds() / 60
    return dict(move60=m60, move15=m15,
                speed=m15 / m60 if abs(m60) > 1e-9 else 0.0,
                move60_atr=m60 / atr4, atr_ratio=atr1 / atr4,
                new_extreme=float(ext),
                day_pos=pos if direction > 0 else 1 - pos,
                run=float(run), from_open=(px - op) * direction / atr4,
                mins_in=float(mins))


def perm_p(a, b_, n=20000):
    obs = a.mean() - b_.mean()
    allv = np.concatenate([a, b_])
    k = len(a)
    cnt = 0
    for _ in range(n):
        p = rng.permutation(allv)
        if abs(p[:k].mean() - p[k:].mean()) >= abs(obs):
            cnt += 1
    return obs, cnt / n


def holm(ps):
    order = np.argsort(ps)
    m = len(ps)
    out = np.empty(m)
    prev = 0.0
    for rank, idx in enumerate(order):
        v = min(1.0, (m - rank) * ps[idx])
        prev = max(prev, v)
        out[idx] = prev
    return out


def main():
    print(__doc__.split("REGISTERED PREDICTION")[0].rstrip())
    print("\nREGISTERED: size and speed separate weakly; the better candidates are")
    print("rarity features (new session extreme, range expansion). At most one survives")
    print("Holm correction, possibly none - in which case his selection is judgment.\n")

    b = bars()
    d = pd.read_csv(ROOT / "strategy_analysis" / "statement_trades.csv",
                    parse_dates=["open_time"])
    n = d[d.symbol.str.contains("NASDAQ")].copy()
    n["utc"] = n.open_time - pd.Timedelta(hours=GMT)

    pos_rows, pos_idx = [], set()
    for _, r in n.iterrows():
        i = b.index.searchsorted(r.utc, side="right") - 1
        if i < 60 or i >= len(b):
            continue
        f = featurise(b, i, 1 if r.side == "BUY" else -1)
        if f:
            f["t"] = b.index[i]
            pos_rows.append(f)
            pos_idx.add(i)
    P = pd.DataFrame(pos_rows)

    # controls: same hours-of-day and same dates he traded
    hours = set(pd.DatetimeIndex([r["t"] for r in pos_rows]).hour)
    days = set(pd.DatetimeIndex([r["t"] for r in pos_rows]).normalize())
    ctrl = []
    c = b["close"].to_numpy()
    for i in range(60, len(b) - 1):
        t = b.index[i]
        if i in pos_idx or t.hour not in hours or t.normalize() not in days:
            continue
        dirn = 1 if c[i] - c[i - 12] > 0 else -1     # momentum direction
        f = featurise(b, i, dirn)
        if f:
            ctrl.append(f)
    C = pd.DataFrame(ctrl)
    print(f"{len(P)} entries he TOOK   vs   {len(C):,} comparable moments he did NOT")
    print(f"  (same {len(hours)} hours of day, same {len(days)} trading days)\n")

    cut = P.t.sort_values().iloc[int(len(P) * 2 / 3)]
    tr, te = P[P.t < cut], P[P.t >= cut]
    print(f"  ranking on {len(tr)} entries before {cut:%Y-%m-%d}, "
          f"holding out {len(te)} after\n")

    print("=" * 96)
    print("1. WHICH FEATURES SEPARATE HIS ENTRIES?  (ranked on the first 2/3 only)")
    print("=" * 96)
    print(f"  {'feature':<38}{'his':>9}{'other':>9}{'diff':>9}{'p':>8}{'Holm p':>9}")
    raw = []
    for k, _desc in FEATURES:
        obs, p = perm_p(tr[k].to_numpy(float), C[k].to_numpy(float))
        raw.append(p)
    hp = holm(np.array(raw))
    rows = []
    for (k, desc), p, h in zip(FEATURES, raw, hp):
        a, bb = tr[k].mean(), C[k].mean()
        star = " **" if h < .05 else (" *" if p < .05 else "")
        print(f"  {desc[:36]:<38}{a:>9.2f}{bb:>9.2f}{a-bb:>9.2f}{p:>8.3f}{h:>9.3f}{star}")
        rows.append((k, desc, p, h))
    print("\n  * = uncorrected only (expect ~1 by chance from 10 tests)")
    print("  ** = survives Holm correction across all 10")

    surv = [r for r in rows if r[3] < .05]
    print("\n" + "=" * 96)
    print("2. HOLDOUT — does the survivor hold on entries that never informed the ranking?")
    print("=" * 96)
    if not surv:
        print("  NOTHING survived Holm correction, so there is nothing to hold out.")
        print("  Uncorrected hits, if any, are what 10 tests on 39 points produce by chance.")
    else:
        for k, desc, p, h in surv:
            obs, pv = perm_p(te[k].to_numpy(float), C[k].to_numpy(float))
            ok = "HOLDS" if pv < .05 and np.sign(obs) == np.sign(
                tr[k].mean() - C[k].mean()) else "does NOT hold"
            print(f"  {desc[:44]:<46} held-out diff {obs:>+7.2f}  p {pv:.3f}   {ok}")

    print("\n" + "=" * 96)
    print("VERDICT")
    print("=" * 96)
    if not surv:
        print("  No single feature separates the moves he took from the ones he skipped,")
        print("  once the 10 tests are corrected for. He is NOT applying a threshold on")
        print("  any of: move size, speed, volatility expansion, session extreme, range")
        print("  position, run length, distance from the open, or time since the open.")
        print("\n  That is a real finding, not an absence of one: it means the trigger is")
        print("  not a measurable property of the 5-minute chart at the moment he enters.")
    else:
        print(f"  {len(surv)} feature(s) survived correction - see the holdout line above.")


if __name__ == "__main__":
    main()
