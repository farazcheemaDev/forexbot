"""PICKING THE PRODUCT'S WEIGHTS - the menu, with every column the decision needs.

all_weather.py ranked 54 mixes by their worst regime cell and all_weather_check.py showed the
winner beats the matched-risk control (+7.0% chop against +0.5% for machine v2 scaled to the same
68% fall), on both halves and all four bar phases.

This file is the last step before the product: the shortlist, with return AND risk side by side,
so the weight choice is made on evidence rather than on the ranking alone. The question it
answers is not "which mix is best" - it is "what does each point of sideways return COST".

Note the two things that do NOT change across this menu, and so are not decision columns:
  * the crash bids stay at 1x everywhere, so the worst-hour exposure is machine v2's (46% of the
    account left, logs/machine.txt) in every row. This menu does not touch that risk.
  * the trend book's gross guard drops to 8x wherever MN runs at 2x, since they share margin.

    python -m backtest.all_weather_pick
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.all_weather_check import HDR, books, cells, row  # noqa: E402

MENU = [
    ("machine v2 (TODAY, on the VM)", dict(g=1.00, k_mn=1.0, k_sl=1.0, k_bid=1.0)),
    ("MN 1.5x, trend 100%", dict(g=1.00, k_mn=1.5, k_sl=1.0, k_bid=1.0)),
    ("MN 1.5x, trend 85%, sleeve 1.5x", dict(g=0.85, k_mn=1.5, k_sl=1.5, k_bid=1.0)),
    ("MN 2x, trend 100%", dict(g=1.00, k_mn=2.0, k_sl=1.0, k_bid=1.0)),
    ("MN 2x, trend 85%, sleeve 1.5x", dict(g=0.85, k_mn=2.0, k_sl=1.5, k_bid=1.0)),
    ("MN 2x, trend 85%, sleeve 2x", dict(g=0.85, k_mn=2.0, k_sl=2.0, k_bid=1.0)),
    ("MN 2x, trend 70%, sleeve 1x", dict(g=0.70, k_mn=2.0, k_sl=1.0, k_bid=1.0)),
    ("MN 2x, trend 70%, sleeve 1.5x", dict(g=0.70, k_mn=2.0, k_sl=1.5, k_bid=1.0)),
]


def main():
    print("building the four books...")
    tr, mn_d, sl, bd, dom = books(0)
    print("\nTHE MENU - all on $221, 10 orderings, trend gains shrunk for hindsight")
    print(HDR)
    out = []
    for lab, kw in MENU:
        c = cells(tr, mn_d, sl, bd, dom, **kw)
        out.append((lab, kw, c))
        allpos = min(c["bull"], c["chop"], c["bear"]) > 0
        print(row(lab, c, "  ALL 3 POSITIVE" if allpos else ""))

    base = out[0][2]
    print("\nWHAT EACH MIX COSTS AND BUYS, against machine v2")
    print(f"  {'mix':<34}{'chop gain':>11}{'yr change':>11}{'extra DD':>10}"
          f"{'worse wst mo':>14}{'$/chop point':>14}")
    for lab, kw, c in out[1:]:
        dchop = c["chop"] - base["chop"]
        dyr = c["yr"] - base["yr"]
        print(f"  {lab:<34}{dchop:>+10.1f}%{dyr:>+10.0f}${c['dd'] - base['dd']:>+9.0f}%"
              f"{c['worst'] - base['worst']:>+13.0f}%"
              + (f"{dyr / dchop:>+13.0f}$" if abs(dchop) > 0.1 else f"{'-':>14}"))
    print("\n  $/chop point = dollars of typical year given up (or gained) per point of sideways")
    print("  return bought. Negative means the sideways return is paid for in return.")


if __name__ == "__main__":
    main()
