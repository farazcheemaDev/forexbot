"""MINIMUM VIABLE CAPITAL, PER VENUE — the thing actually blocking a small account.

THE PROBLEM THIS MEASURES
    longtrend is validated at ~+10.7%/month with a 74.8% drawdown. Neither number
    is the blocker. The blocker is arithmetic:

        capital floor = (minimum order value) / (risk fraction per unit)
                        / (1 - worst drawdown)

    Bitget's $5 minimum order against 0.13% risk per unit needs ~$116 to survive
    the measured drawdown and still place an order at the bottom. At $15 the
    strategy does not "underperform" - it cannot place a trade at all.

    So the highest-leverage remaining work is not a better signal. It is a venue
    whose minimum order is $1 instead of $5.

WHAT IS ACTUALLY MEASURED HERE
    ccxt's loaded market metadata for each venue's USDT perpetual on the 9 coins
    we trade: minimum amount in contracts, contract size, and the resulting
    minimum NOTIONAL at the current mark. Plus any explicitly declared minimum
    cost. No credentials, no orders - public market data only.

    The number that matters is the WORST minimum across the 9 coins, because the
    strategy needs all nine. A venue with a $0.20 floor on BTC and $5 on DOGE has
    a $5 floor for our purposes.

HONESTY NOTE
    Exchange metadata lies more often than price data does. ccxt reports what the
    venue publishes, and venues publish stale or nominal minimums. A floor derived
    here is a CLAIM TO VERIFY with one real demo order, not a fact. It is still
    worth computing first, because it tells us which venue is worth the work of
    writing an adapter for.

    python -m backtest.venue_floor
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ccxt  # noqa: E402

COINS = ["BTC", "ETH", "SOL", "XRP", "BNB", "ADA", "DOGE", "AVAX", "LINK"]
VENUES = ["bitget", "mexc", "gate", "bybit", "binance"]

RISK_PER_UNIT = 0.0013      # 0.13% - the validated setting
MAX_DD = 0.748              # measured worst drawdown of the validated config
SL_MULT = 2.0               # stop distance in ATR; risk = SL_MULT * ATR
TYPICAL_ATR_PCT = 0.010     # ~1.0%/hour ATR on majors; used only to turn a risk
                            # fraction into a NOTIONAL, see note below


def min_notional(mkt, price):
    """Smallest order value the venue admits, in USDT."""
    lim = mkt.get("limits") or {}
    cost_min = (lim.get("cost") or {}).get("min")
    amt_min = (lim.get("amount") or {}).get("min")
    csize = mkt.get("contractSize") or 1.0
    by_amt = (amt_min * csize * price) if amt_min else None
    cands = [c for c in (cost_min, by_amt) if c]
    return (max(cands) if cands else None), amt_min, cost_min, csize


def main():
    print(__doc__.split("HONESTY NOTE")[0].rstrip())
    print("\n" + "=" * 104)
    print(f"{'venue':<10} {'coins':>6} {'worst min $':>12} {'coin':>7} "
          f"{'median min $':>13} {'-> capital floor':>18}")
    print("=" * 104)
    rows = []
    for v in VENUES:
        try:
            ex = getattr(ccxt, v)({"enableRateLimit": True,
                                   "options": {"defaultType": "swap"}})
            ex.load_markets()
        except Exception as e:
            print(f"{v:<10} load failed: {type(e).__name__}: {str(e)[:60]}")
            continue
        found, detail = {}, {}
        for c in COINS:
            m = None
            for cand in (f"{c}/USDT:USDT", f"{c}/USDT"):
                if cand in ex.markets:
                    mm = ex.markets[cand]
                    if mm.get("swap") or mm.get("contract"):
                        m = mm
                        break
            if m is None:
                continue
            try:
                px = float((ex.fetch_ticker(m["symbol"]) or {}).get("last") or 0)
            except Exception:
                px = 0.0
            if px <= 0:
                continue
            mn, amt_min, cost_min, csize = min_notional(m, px)
            if mn:
                found[c] = mn
                detail[c] = (amt_min, cost_min, csize, px)
        if not found:
            print(f"{v:<10} no usable markets")
            continue
        worst_c = max(found, key=lambda k: found[k])
        worst = found[worst_c]
        med = sorted(found.values())[len(found) // 2]
        # capital floor: at the bottom of the measured drawdown, one unit's risk
        # must still buy an order the venue accepts.
        #   risk_$ = equity * RISK_PER_UNIT
        #   notional = risk_$ / (SL_MULT * ATR%)    <- risk is a stop distance,
        #                                              notional is the position
        # so equity_min = worst_min * SL_MULT * ATR% / RISK_PER_UNIT, then divided
        # by (1 - MAX_DD) so it still holds after the worst drawdown.
        per_unit = worst * SL_MULT * TYPICAL_ATR_PCT / RISK_PER_UNIT
        floor = per_unit / (1 - MAX_DD)
        rows.append((floor, v, worst, worst_c, med, found, detail))
        print(f"{v:<10} {len(found):>6} {worst:>12,.2f} {worst_c:>7} "
              f"{med:>13,.2f} {floor:>17,.0f}", flush=True)

    if not rows:
        return
    rows.sort()
    print("\n" + "=" * 104)
    print("CHEAPEST VENUE FIRST — per-coin minimum order value in USDT")
    print("=" * 104)
    for floor, v, worst, wc, med, found, detail in rows[:3]:
        print(f"\n{v}  (floor ~${floor:,.0f})")
        for c in COINS:
            if c not in found:
                print(f"    {c:<6} not listed")
                continue
            amt_min, cost_min, csize, px = detail[c]
            print(f"    {c:<6} ${found[c]:>9,.3f}   "
                  f"min amount {amt_min}  contract size {csize}  "
                  f"declared min cost {cost_min}  px {px:,.4f}")

    # ------------------------------------------------------------------
    # THE LEVER. The floor above is set by the SINGLE most expensive coin in the
    # book - ETH's 0.01 step is $25 whatever else we do. But the book is a
    # choice. If a venue lists enough cheap coins with tiny steps, a book made of
    # those has a far lower floor, and the strategy does not care which coins it
    # trades as long as they are liquid enough to rank.
    #
    # This is the difference between "you need $1,500" and "you need $100", so it
    # is worth measuring rather than assuming.
    print("\n" + "=" * 104)
    print("WHICH BOOK COULD A SMALL ACCOUNT ACTUALLY TRADE?")
    print("Floor if we keep only the k CHEAPEST of the 9 coins (by min order)")
    print("=" * 104)
    print(f"{'venue':<10} {'k':>3} {'binding coin':>13} {'worst min $':>12} "
          f"{'capital floor':>14}   book")
    for floor, v, worst, wc, med, found, detail in rows:
        order = sorted(found, key=lambda c: found[c])
        for k in (4, 5, 6, 9):
            if k > len(order):
                continue
            sub = order[:k]
            wmin = found[sub[-1]]
            f2 = wmin * SL_MULT * TYPICAL_ATR_PCT / RISK_PER_UNIT / (1 - MAX_DD)
            print(f"{v:<10} {k:>3} {sub[-1]:>13} {wmin:>12,.3f} "
                  f"{f2:>14,.0f}   {' '.join(sub)}")
        print()

    best = rows[0]
    print("=" * 104)
    bg = next((r for r in rows if r[1] == "bitget"), None)
    if bg:
        print(f"Bitget 9-coin floor ${bg[0]:,.0f}  vs  best venue "
              f"{best[1]} ${best[0]:,.0f}")
    print("\nTHE BINDING CONSTRAINT IS ONE COIN, NOT THE VENUE. Read the table")
    print("above: dropping the two or three most expensive contracts moves the")
    print("floor by an order of magnitude, while switching venue barely moves it.")
    print("That is a strategy decision (does a cheaper book still work?) and it")
    print("has to be BACKTESTED on that book, not assumed.")
    print("\nTHESE ARE CLAIMS TO VERIFY, NOT FACTS. Exchange metadata is often")
    print("stale or nominal. Before writing an adapter, place ONE real order at")
    print("the stated minimum on that venue's demo and confirm it fills.")
    print("The ATR assumption (1.0%/h) also moves the floor linearly - a quieter")
    print("market needs MORE notional per unit of risk, so the floor rises.")


if __name__ == "__main__":
    main()
