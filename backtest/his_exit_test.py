"""IS THE EXIT THE EDGE?  Random entries, his exit rule.

    python -m backtest.his_exit_test

THE PROPOSITION BEING TESTED
    §21 ended with a claim: "at a 15-minute half-life and a 7-point target, a mediocre
    entry still works if the exit is disciplined." That is falsifiable and this file
    falsifies it or not.

    §20 established that nothing about the chart distinguishes the MOMENTS he picks. If
    the exit really carries the edge, then entries chosen AT RANDOM inside his window,
    exited by his rule, should make money. If they lose, his entry selection is doing
    real work even though no measurable feature captures it - and the honest conclusion
    becomes that the edge is in the part that cannot be written down.

HIS RULE, AS MEASURED IN §21
    take ~7 points, be out inside ~2 minutes, no stop loss
    (his two losses ran to -7.5 and -31.75 points; he does not use a protective stop,
     and one SL/TP order appears in 92 rows)

COSTS, FROM HIS OWN STATEMENT
    commission is $10 per side on 0.20 lots = $50/lot/side = $100/lot round trip, and
    the contract is $100 per point per lot (verified: points x lots x 100 reproduces the
    profit column exactly). So commission = 1.0 POINT round trip regardless of size.
    Spread on the index is ~1 point. Total 2.0 points, charged on every trade.

    That is the whole difficulty: a 7-point target against a 2-point cost needs the
    target to be hit far more often than not.

REGISTERED PREDICTION (2026-09-16, before running)
    RANDOM ENTRIES LOSE. A fixed target with a time exit and no stop is a structurally
    negative payoff - the upside is capped at +7 while the time exit accepts whatever
    the loss happens to be - and 2 points of cost on a 7-point target is a 29% tax. I
    expect every random variant to be negative, which would mean §21's closing claim is
    WRONG and his entry selection is doing the work after all.

    If instead random entries are profitable, the exit is genuinely the edge and this is
    learnable without knowing what he sees.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ROOT = Path(__file__).resolve().parents[1]
COST = 2.0            # points, round trip: 1.0 commission + ~1.0 spread
rng = np.random.default_rng(101)


def bars():
    f = ROOT / "strategy_analysis" / "data" / "USTECm_1m_400d.json"
    d = pd.DataFrame(json.load(open(f)))
    d["t"] = pd.to_datetime(d["t"], unit="ms")
    return (d.rename(columns={"o": "open", "h": "high", "l": "low", "c": "close"})
            .set_index("t").sort_index())


def simulate(b, starts, direction_mode, target, max_min, stop=None):
    """One trade per start index. Exits at target, at stop, or at the time limit."""
    o = b["open"].to_numpy(); h = b["high"].to_numpy()
    l = b["low"].to_numpy(); c = b["close"].to_numpy()
    out = []
    for i in starts:
        if i + max_min + 1 >= len(b) or i < 61:
            continue
        if direction_mode == "random":
            d = 1 if rng.random() < .5 else -1
        elif direction_mode == "momentum":
            d = 1 if c[i] - c[i - 60] > 0 else -1
        else:                                     # fade
            d = -1 if c[i] - c[i - 60] > 0 else 1
        entry = o[i + 1]                          # fill on the NEXT bar's open
        pnl = None
        for k in range(i + 1, i + 1 + max_min):
            hi = (h[k] - entry) * d
            lo = (l[k] - entry) * d
            if stop is not None and lo <= -stop:
                pnl = -stop                        # stop beats target on a tie
                break
            if hi >= target:
                pnl = target
                break
        if pnl is None:
            pnl = (c[i + max_min] - entry) * d
        out.append(pnl - COST)
    return np.array(out)


def main():
    print(__doc__.split("REGISTERED PREDICTION")[0].rstrip())
    print("\nREGISTERED: random entries LOSE. A capped +7 against an uncapped time exit,")
    print("taxed 2 points on a 7-point target, is structurally negative. If they lose,")
    print("§21's closing claim is wrong and his ENTRY is doing the work.\n")

    b = bars()
    et = b.index - pd.Timedelta(hours=4)          # UTC -> US Eastern
    inwin = (et.hour >= 11) & (et.hour < 13) & (b.index.dayofweek < 5)
    cand = np.flatnonzero(np.asarray(inwin))
    cand = cand[(cand > 61) & (cand < len(b) - 30)]
    print(f"  {len(b):,} 1-minute bars, {len(cand):,} inside 11:00-13:00 ET on weekdays")
    print(f"  cost charged every trade: {COST} points\n")

    N = 4000
    starts = rng.choice(cand, size=min(N, len(cand)), replace=False)

    print("=" * 92)
    print("HIS EXIT RULE (7 points / 2 minutes / no stop) ON ENTRIES HE DID NOT CHOOSE")
    print("=" * 92)
    print(f"  {'entry direction':<18}{'n':>6}{'win%':>8}{'avg pts':>10}"
          f"{'total pts':>11}{'$ on 0.20 lots':>16}")
    for mode in ("random", "momentum", "fade"):
        r = simulate(b, starts, mode, target=7.0, max_min=2)
        print(f"  {mode:<18}{len(r):>6}{100*(r>0).mean():>7.0f}%{r.mean():>10.3f}"
              f"{r.sum():>11.0f}{r.sum()*0.20*100:>15,.0f}")

    print("\n" + "=" * 92)
    print("DOES ANY TARGET / TIME COMBINATION WORK ON RANDOM ENTRIES?")
    print("=" * 92)
    print(f"  {'target':>7}{'minutes':>9}{'win%':>8}{'avg pts':>10}{'verdict':>12}")
    best = None
    for tgt in (3.0, 5.0, 7.0, 10.0, 15.0):
        for mm in (1, 2, 5, 10):
            r = simulate(b, starts, "random", target=tgt, max_min=mm)
            if best is None or r.mean() > best[0]:
                best = (r.mean(), tgt, mm)
            flag = "  positive" if r.mean() > 0 else ""
            print(f"  {tgt:>7.1f}{mm:>9}{100*(r>0).mean():>7.0f}%{r.mean():>10.3f}{flag:>12}")
    print(f"\n  best random-entry cell: target {best[1]:.0f} / {best[2]} min "
          f"= {best[0]:+.3f} pts per trade")

    print("\n" + "=" * 92)
    print("WHAT HE ACTUALLY ACHIEVED, FOR SCALE")
    print("=" * 92)
    d = pd.read_csv(ROOT / "strategy_analysis" / "statement_trades.csv",
                    parse_dates=["open_time", "close_time"])
    n = d[d.symbol.str.contains("NASDAQ")].copy()
    n["pts"] = (n.close_price - n.open_price) * np.where(n.side == "BUY", 1, -1)
    print(f"  his 46 NASDAQ trades: {100*(n.pts>0).mean():.0f}% win, "
          f"{n.pts.mean():+.2f} pts gross, {n.pts.mean()-COST:+.2f} net of the same cost")
    print(f"  a random entry with the same exit: see above")

    print("\n" + "=" * 92)
    print("VERDICT")
    print("=" * 92)
    r7 = simulate(b, starts, "random", 7.0, 2)
    if r7.mean() > 0:
        print("  RANDOM ENTRIES ARE PROFITABLE with his exit rule. The exit carries the")
        print("  edge and this is learnable without knowing what he sees.")
    else:
        print(f"  RANDOM ENTRIES LOSE ({r7.mean():+.3f} pts/trade). §21's closing claim -")
        print("  that a mediocre entry works if the exit is disciplined - is WRONG.")
        print(f"\n  His entry selection is worth {n.pts.mean()-r7.mean()-COST:+.2f} points")
        print("  per trade over a random one in the same window, and §20 showed no")
        print("  measurable feature captures it. The edge is in the part he cannot")
        print("  write down - which is also why nobody can hand it to you.")


if __name__ == "__main__":
    main()
