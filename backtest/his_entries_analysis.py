"""WHAT DO HIS 46 NASDAQ ENTRIES HAVE IN COMMON?

    python -m backtest.his_entries_analysis

WHY THIS CAN FINALLY BE ANSWERED
    Three things had to be true before this analysis meant anything, and as of
    2026-09-16 all three are:

      1. THE TIMEZONE IS KNOWN. Derived as UTC+5 by minimum basis variance in
         his_strategy.md section 15, and then confirmed verbatim by the broker
         statement's own header: "GMT Offset : 5.0".
      2. THE SAMPLE IS BIG ENOUGH TO MOVE ON. 46 NASDAQ entries from the official
         statement, against 26 transcribed from screenshots. The fade/follow question
         came in at p=0.17 on 26; 46 roughly halves the gap to the ~85 needed.
      3. THE RIGHT HALF OF HIS TRADING IS IDENTIFIED. NASDAQ is 46 trades and +$3,130;
         GOLD is 41 trades and +$118. Analysing his gold scalping - which is what
         his_strategy.md described for months - would be analysing the half that makes
         nothing.

WHAT IS MEASURED
    For each entry, using ONLY bars that closed BEFORE it:
      * fade or follow, at 5 / 15 / 30 / 60 minute horizons
      * position within the day's range so far (0 = at the low, 1 = at the high)
      * size of the preceding move, in points and in ATR units
      * hour of day in US Eastern

    Every test states its null. Direction without significance is reported as direction
    without significance - the fade thesis has already survived one round of that and
    must not be promoted by repetition.

THE INSTRUMENT MISMATCH, STATED PLAINLY
    He trades NASDAQ futures (Mar/June/Sep contracts). The available bars are USTECm, a
    CFD on the index. The two differ by a rolling basis, so ABSOLUTE prices are not
    comparable and nothing here uses them. Every feature is RELATIVE - a return, a
    position within a range, a distance in ATR - and those survive the basis intact.

REGISTERED PREDICTION (2026-09-16, before running)
    The follow rate stays above 50% and reaches significance at 46 entries, because the
    26-entry estimate of 65% would give p<0.05 by n=46 if the effect is real. If it
    instead drifts back toward 50%, the earlier reading was noise and the honest answer
    becomes "his entry timing is not explained by the preceding move at all".
"""
from __future__ import annotations

import json
import sys
from math import comb
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ROOT = Path(__file__).resolve().parents[1]
GMT_OFFSET = 5.0          # from the statement header, confirmed independently
TRADES = ROOT / "strategy_analysis" / "statement_trades.csv"


def binom_p(k, n, p=0.5):
    """Two-sided exact binomial p-value."""
    lo = min(k, n - k)
    return min(1.0, 2 * sum(comb(n, i) * p ** i * (1 - p) ** (n - i)
                            for i in range(0, lo + 1)))


def load_bars():
    for name in ("USTECm_5m_400d.json", "USTECm_5m_2400d.json"):
        f = ROOT / "strategy_analysis" / "data" / name
        if f.exists():
            d = pd.DataFrame(json.load(open(f)))
            d["t"] = pd.to_datetime(d["t"], unit="ms")
            return (d.rename(columns={"o": "open", "h": "high", "l": "low",
                                      "c": "close"})
                    .set_index("t").sort_index())
    raise SystemExit("no USTECm 5m bars - run fx_fetch.py first")


def main():
    print(__doc__.split("REGISTERED PREDICTION")[0].rstrip())
    print("\nREGISTERED: the follow rate stays >50% and reaches significance at n=46.")
    print("If it drifts to 50%, the 26-entry reading was noise and the honest answer is")
    print("that the preceding move does not explain his entries.\n")

    if not TRADES.exists():
        raise SystemExit(f"{TRADES} not found - parse the statement first")
    d = pd.read_csv(TRADES, parse_dates=["close_time", "open_time"])
    n = d[d.symbol.str.contains("NASDAQ")].copy()
    n["utc"] = n.open_time - pd.Timedelta(hours=GMT_OFFSET)
    b = load_bars()
    n = n[(n.utc >= b.index.min()) & (n.utc <= b.index.max())].copy()
    print(f"{len(n)} NASDAQ entries covered by bars "
          f"({n.utc.min():%Y-%m-%d} to {n.utc.max():%Y-%m-%d})\n")

    rec = []
    for _, r in n.iterrows():
        i = b.index.searchsorted(r.utc, side="right") - 1
        if i < 13:
            continue
        px = b["close"].iloc[i]
        day = b.loc[(b.index >= r.utc.normalize()) & (b.index <= r.utc)]
        if len(day) < 6:
            day = b.iloc[max(0, i - 78):i + 1]
        lo, hi = day["low"].min(), day["high"].max()
        prior = b.iloc[max(0, i - 48):i + 1]
        atr = float((prior["high"] - prior["low"]).mean()) or 1.0
        rec.append(dict(
            side=r.side, net=r.net, win=r.net > 0,
            et=(r.utc - pd.Timedelta(hours=4)).hour,
            pos=float((px - lo) / (hi - lo)) if hi > lo else 0.5,
            m5=float(px - b["close"].iloc[i - 1]),
            m15=float(px - b["close"].iloc[i - 3]),
            m30=float(px - b["close"].iloc[i - 6]),
            m60=float(px - b["close"].iloc[i - 12]),
            atr=atr))
    f = pd.DataFrame(rec)
    print(f"{len(f)} entries with enough prior history\n")

    # ---- 1. fade or follow -------------------------------------------------
    print("=" * 84)
    print("1. DOES HE FADE THE PRECEDING MOVE, OR FOLLOW IT?")
    print("=" * 84)
    print("   FOLLOW = SELL after a down move, BUY after an up move.")
    print("   Null = 50%. A level-fader would sit BELOW 50%.\n")
    print(f"  {'horizon':<12}{'n':>5}{'follow':>9}{'%':>8}{'p':>9}   verdict")
    for c, lab in (("m5", "5 min"), ("m15", "15 min"), ("m30", "30 min"),
                   ("m60", "60 min")):
        g = f[f[c] != 0]
        k = int((((g.side == "BUY") & (g[c] > 0)) |
                 ((g.side == "SELL") & (g[c] < 0))).sum())
        p = binom_p(k, len(g))
        v = ("FOLLOWS" if k / len(g) > .5 else "fades") + (" *" if p < .05 else "")
        print(f"  {lab:<12}{len(g):>5}{k:>9}{100*k/len(g):>7.0f}%{p:>9.3f}   {v}")

    # ---- 2. position in the day's range ------------------------------------
    print("\n" + "=" * 84)
    print("2. WHERE IN THE DAY'S RANGE DOES HE ENTER?   (0 = day low, 1 = day high)")
    print("=" * 84)
    print("   A fader SELLS high and BUYS low, so SELL-minus-BUY would be strongly")
    print("   POSITIVE. Null for each side on its own is 0.50.\n")
    for s, g in f.groupby("side"):
        print(f"  {s:<5} n={len(g):<3} mean {g.pos.mean():.3f}  median "
              f"{g.pos.median():.3f}")
    if {"BUY", "SELL"} <= set(f.side):
        diff = f[f.side == "SELL"].pos.mean() - f[f.side == "BUY"].pos.mean()
        # permutation null: shuffle the side labels
        rng = np.random.default_rng(3)
        pos, side = f.pos.to_numpy(), (f.side == "SELL").to_numpy()
        nulls = []
        for _ in range(20000):
            s2 = rng.permutation(side)
            nulls.append(pos[s2].mean() - pos[~s2].mean())
        nulls = np.array(nulls)
        pv = (np.abs(nulls) >= abs(diff)).mean()
        print(f"\n  SELL minus BUY: {diff:+.3f}   permutation p = {pv:.3f}"
              f"   {'(a fader needs this strongly POSITIVE)' if diff < 0.1 else ''}")

    # ---- 3. what separates his winners from his losers ---------------------
    print("\n" + "=" * 84)
    print("3. WHAT SEPARATES HIS WINNERS FROM HIS LOSERS?")
    print("=" * 84)
    w, l = f[f.win], f[~f.win]
    print(f"  {len(w)} winners, {len(l)} losers\n")
    if len(l) >= 3:
        print(f"  {'feature':<26}{'winners':>10}{'losers':>10}{'p':>9}")
        rng = np.random.default_rng(4)
        for c, lab in (("pos", "position in day range"), ("m15", "prior 15min (pts)"),
                       ("m60", "prior 60min (pts)"), ("et", "hour (ET)")):
            a, bb = w[c].to_numpy(), l[c].to_numpy()
            obs = a.mean() - bb.mean()
            allv = np.concatenate([a, bb])
            nulls = []
            for _ in range(20000):
                p2 = rng.permutation(allv)
                nulls.append(p2[:len(a)].mean() - p2[len(a):].mean())
            pv = (np.abs(np.array(nulls)) >= abs(obs)).mean()
            print(f"  {lab:<26}{a.mean():>10.2f}{bb.mean():>10.2f}{pv:>9.3f}"
                  + ("  *" if pv < .05 else ""))
    else:
        print("  too few losers to compare (that is itself the headline: "
              f"{100*len(w)/len(f):.0f}% win rate)")

    # ---- 4. time of day ----------------------------------------------------
    print("\n" + "=" * 84)
    print("4. WHEN DOES HE TRADE?   (US Eastern, from the confirmed GMT+5 header)")
    print("=" * 84)
    c = f.et.value_counts().sort_index()
    for h, k in c.items():
        net = f[f.et == h].net.sum()
        print(f"  {h:>2}:00 ET {k:>3}  {'#' * k:<14} net ${net:>9,.0f}")
    best = f.groupby("et").net.sum().sort_values(ascending=False)
    print(f"\n  most profitable hours: "
          + ", ".join(f"{h}:00 ET (${v:,.0f})" for h, v in best.head(3).items()))
    print("\n" + "=" * 84)
    print("Read the p-values, not the percentages. 46 entries is better than 26 and")
    print("still small; a direction without significance is a direction, not a rule.")


if __name__ == "__main__":
    main()
