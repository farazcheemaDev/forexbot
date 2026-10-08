"""THE PAIR UNDER BITGET'S $5 MINIMUM ORDER, by starting amount (2026-10-08). Question: "the running bot had a capital
constraint - does this one too?" Each position = equity x 0.5 / slots; an order under $5 is refused (skipped), as the
bots do. RESULT (this run): 10,000 PKR at 8 slots - EVERY order refused ($2.23 a position), it cannot trade; 25,000 PKR
and up - 0% refused, the full +51%/yr. A smaller pair for 10,000 PKR: 3 slots per book +63%/yr but a 57% fall and a -23%
worst month; 2 slots a 73% fall. The MN overlay (x0.5, 3-6 names a side) needs ~$60-120 and the bear sleeve skipped a
third of orders at $221 (doc 13), so the FULL machine v3 wants roughly 100,000-150,000 PKR.

    python -m backtest.pair_min_capital
"""
import sys; sys.path.insert(0, r'D:\forexbot')
import numpy as np, pandas as pd
from backtest import pair_lab as pl
reg = pl.btc_regime_daily()
D, C = pl.daily_trades(), pl.capit_trades(0)

def run(start_usd, slots, seed, min_usd=5.0):
    """The pair in dollars: equity x 0.5 / slots per position; refused (skipped) if under min_usd - what the bot does."""
    rng = np.random.default_rng(seed)
    ev = sorted(((r.t_in, rng.random(), nm, r.t_out, r.net) for nm, T in (("daily", D), ("capit", C)) for r in T.itertuples()), key=lambda x: (x[0], x[1]))
    eq, open_, pts, refused, placed = start_usd, [], [], 0, 0
    for t_in, _, nm, t_out, net in ev:
        for p in sorted([p for p in open_ if p[0] <= t_in], key=lambda p: p[0]):
            eq += p[1]; pts.append((p[0], eq))
        open_ = [p for p in open_ if p[0] > t_in]
        if sum(1 for p in open_ if p[2] == nm) >= slots: continue
        size = eq * 0.5 / slots
        if size < min_usd: refused += 1; continue
        open_.append((t_out, size * net, nm)); placed += 1
    for p in sorted(open_, key=lambda p: p[0]): eq += p[1]; pts.append((p[0], eq))
    if not pts:
        return None, 1.0
    s = pd.Series([e for _, e in pts], index=pd.DatetimeIndex([t for t, _ in pts])).groupby(level=0).last().resample("D").last().ffill() / start_usd
    return s, refused / max(refused + placed, 1)

print("THE PAIR (8 slots per book) WITH BITGET'S $5 MINIMUM, by starting amount:")
for pkr in (10_000, 25_000, 50_000, 100_000):
    res = [run(pkr / 280, 8, sd) for sd in range(5)]
    if all(c is None for c, _ in res):
        print(f"  {pkr:>7,} PKR (${pkr/280:,.0f}): EVERY order refused - each position would be ${pkr/280*0.5/8:.2f}, under $5; it cannot trade")
        continue
    m = pd.DataFrame([pl.metrics(c, reg) for c, _ in res if c is not None]).median()
    print(f"  {pkr:>7,} PKR (${pkr/280:,.0f}): orders refused {np.median([r for _, r in res]):.0%} | {m.cagr*100:+.0f}%/yr, fall {m.dd:.0%}, months up {m.up:.0%}")
print("\nA SMALLER PAIR FOR 10,000 PKR (fewer, bigger positions; no order under $5):")
for slots in (2, 3):
    res = [run(10_000 / 280, slots, sd) for sd in range(10)]
    m = pd.DataFrame([pl.metrics(c, reg) for c, _ in res]).median()
    print(f"  {slots} slots per book (${10_000/280*0.5/slots:.2f} each at the start): refused {np.median([r for _, r in res]):.0%} | {m.cagr*100:+.0f}%/yr (tune {m.tune*100:+.0f} / holdout {m.hold*100:+.0f}), fall {m.dd:.0%}, months up {m.up:.0%}, worst month {m.worst*100:+.0f}%")
