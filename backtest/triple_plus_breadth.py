"""THE TRIPLE BOOK + THE BEAR-MARKET BREADTH SLEEVE: where does the whole account stand?

Asked: "with our perfected long bot, tight exit and 7 units, if we add this with them, where are
we at?" The trend side is the triple (tight + time stop + 7 units) WITH the bot's 10x gross
guard, entry-sized, 10 orderings - exactly triple_capped.simulate, whose figures CLAUDE.md
quotes. The sleeve is doc 13's rule, frozen: in btc_regime BEAR days, long the basket when
breadth20 is in the bottom third of prior bear days, short it in the top third, 7-day ladder,
entered a day after the signal, 12bp, actual funding.

Two sleeve versions:
  frictionless  the top-10 basket ladder (breadth_robust.run)
  REAL $221     a 5-coin basket through breadth_robust.small_account with Bitget's $5 minimum,
                trading on k x $221 of capital - so a half-size sleeve skips even more orders

Combined daily return = trend + k x sleeve, k = 0 / 0.5 / 1.0. The sleeve trades only on BEAR
days; the triple's 10x peaks are all in BULL (logs/regime_and_liq.txt), so the two do not
compete for the same margin.

THE HAIRCUT PROBLEM, stated rather than hidden: the 3x hindsight haircut belongs to the trend
book's 12 hand-picked coins. The sleeve is point-in-time and needs none. The planning numbers
below apply the standard haircut to the WHOLE combined 12-month result, which also shrinks the
sleeve - so they UNDERSTATE what the sleeve adds. Downside (drawdown, worst month, worst year,
losing years) is RAW, as always.

REGISTERED PREDICTION (2026-09-24, before running): at k = 0.5 with the REAL sleeve, the typical
year for $221 rises by $10-40 (haircut), drawdown falls 3-6 points, months up rise ~5 points,
bear-month mean goes from ~-1.6% to ~+2%; at k = 1.0 the drawdown gain is larger but the holdout
gain small, because the real sleeve's holdout is only +8%/yr.

    python -m backtest.triple_plus_breadth
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.breadth_attack import ls_signal  # noqa: E402
from backtest.breadth_robust import basket, breadth_n, run, small_account  # noqa: E402
from backtest.bull_boost import regimes  # noqa: E402
from backtest.carry_check import exact_funding  # noqa: E402
from backtest.expectations import haircut, month_ends, windows  # noqa: E402
from backtest.market_neutral import btc_regime, drop_non_crypto, load_panel  # noqa: E402
from backtest.regime_signals import member_mask  # noqa: E402
from backtest.triple_capped import build, simulate  # noqa: E402
from backtest.wide_book import eligibility  # noqa: E402

CAP = 221.0
SEEDS = tuple(range(10))
CUT = pd.Timestamp("2024-08-29")


def main():
    C, F, first = load_panel()
    C.index = C.index.astype("datetime64[ns]")
    F.index = C.index
    reg = btc_regime(C).reindex(C.index)
    Fx = exact_funding(C.index, C.columns)
    X = C.to_numpy(float)
    m60 = member_mask(C, first, drop_non_crypto(eligibility(60))) & np.isfinite(X)
    b20 = breadth_n(C, m60, 20)
    sig = ls_signal(b20, reg == "bear")
    top10 = basket(C, Fx, first, 10)
    fric, _ = run(sig, top10)                                      # daily net, whole-account at 1x

    elig5 = drop_non_crypto(eligibility(5))
    months = C.index.strftime("%Y-%m")
    by_month = {m: [s for s in C.columns if m in elig5.get(s, ())] for m in sorted(set(months))}
    ci = {s: i for i, s in enumerate(C.columns)}

    def top5(d):
        return [s for s in by_month[months[d]] if np.isfinite(X[d, ci[s]])][:5]

    real = {}
    for k in (0.5, 1.0):
        for lab, t0 in (("full", None), ("hold", CUT)):
            s = sig if t0 is None else sig.where(sig.index >= t0, 0.0)
            c, skip = small_account(C, Fx, first, s, top5, cap=CAP * k)
            real[(k, lab)] = (c.pct_change().fillna(0.0), skip)

    bear = regimes()[1000]
    bear_ns = pd.DatetimeIndex(bear.index).as_unit("ns").asi8
    bear_v = bear.to_numpy(bool)
    rows = build(max_units=7)
    trend = {lab: [simulate(rows, bear_ns, bear_v, sd, 10.0, t_from=(None if lab == "full" else CUT.value))[0]
                   for sd in SEEDS] for lab in ("full", "hold")}

    dom = reg.groupby(reg.index.to_period("M")).agg(lambda v: v.value_counts().index[0])
    print("TRIPLE (tight + time stop + 7 units, 10x guard, entry-sized, 10 orderings) + k x BREADTH SLEEVE")
    print("upside: 12-month results HAIRCUT on the whole book (understates the sleeve). downside: RAW.\n")
    hdr = (f"  {'book':<34}{'typical yr':>11}{'bad yr':>8}{'good yr':>9}{'yrs<$221':>9}{'worst yr':>9}"
           f"{'DD':>6}{'worst mo':>9}{'mo up':>7}{'bull mo':>9}{'chop mo':>9}{'bear mo':>9}")
    for lab in ("hold", "full"):
        print(f"=== {'HOLDOUT (from 2024-08-29)' if lab == 'hold' else 'FULL HISTORY'}  - $221 after 12 months")
        print(hdr)
        variants = [("triple alone", 0.0, None)]
        for k in (0.5, 1.0):
            variants.append((f"+ {k:g}x sleeve, frictionless", k, "fric"))
            variants.append((f"+ {k:g}x sleeve, REAL $221 ($5 min)", k, "real"))
        for name, k, kind in variants:
            W, DD, WM, UP, RG = [], [], [], [], {"bull": [], "chop": [], "bear": []}
            for c in trend[lab]:
                r = c.pct_change().fillna(0.0)
                if kind == "fric":
                    s_r = fric.reindex(r.index).fillna(0.0)
                elif kind == "real":
                    s_r = real[(k, lab)][0].reindex(r.index).fillna(0.0)
                else:
                    s_r = 0.0
                comb = (1 + r + k * s_r).cumprod()
                me = month_ends(comb)
                W.append(windows(me, 12))
                DD.append((1 - comb / comb.cummax()).max() * 100)
                mo = me.pct_change().dropna()
                WM.append(mo.min() * 100)
                UP.append((mo > 0).mean() * 100)
                rg = pd.Series([dom.get(p, "chop") for p in mo.index.to_period("M")], index=mo.index)
                for g in RG:
                    RG[g].append(mo[rg == g].mean() * 100)
            w = np.concatenate(W)
            h = np.array([haircut(x, 12) for x in w])
            print(f"  {name:<34}${CAP*np.median(h):>9,.0f}${CAP*np.percentile(h, 25):>7,.0f}"
                  f"${CAP*np.percentile(h, 75):>8,.0f}{(w < 1).mean()*100:>8.0f}%${CAP*w.min():>8,.0f}"
                  f"{np.mean(DD):>5.0f}%{np.mean(WM):>+8.1f}%{np.mean(UP):>6.0f}%"
                  + "".join(f"{np.mean(RG[g]):>+8.1f}%" for g in ("bull", "chop", "bear")))
        print()
    for k in (0.5, 1.0):
        print(f"  REAL sleeve at {k:g}x: orders skipped for the $5 minimum - full {real[(k, 'full')][1]*100:.0f}%, "
              f"holdout {real[(k, 'hold')][1]*100:.0f}%")
    print("  months by dominant BTC regime; 'bull/chop/bear mo' = mean RAW monthly return in those months")


if __name__ == "__main__":
    main()
