"""MORE LEVERS AGAINST THE HALVING, same control as dd_fixes.py (the uniform-bet-size frontier).

why_drawdown.py: the falls happen after booms, 42% of their days are CHOP and 42% bull, and 94-95%
of 1h long breakouts lose inside them. dd_fixes.py tested the three fixes the user named. Three
levers aimed at the same cause were still untested:

  4  SLEEVE WEIGHTS  1h longs x0 / x0.5, 4h longs x0.5, 12h longs x0.5, shorts x0 / x2 - is the 1h
                     sleeve a drag that the frontier cannot see?
  5  MARKET-NEUTRAL OVERLAY  doc 10's momentum book (PIT top-60 ex stables/gold, 30d look, weekly,
                     funding over the exact settlement window - bear_chop.fast_run(fshift=1)) on
                     top of the triple at k = 0.25 / 0.5 / 1.0. It earns +1.39%/wk in CHOP
                     (logs/carry_check.txt), where the falls live. Doc 10 measured the overlay on
                     the TIGHT book; never on the triple, never against this frontier.
  6  EVERYTHING      triple + the breadth sleeve (real $221 version, 1x) + the MN overlay.

For 5 and 6 the combined curve is trend daily return + k x the other book's daily return. The
MN book's weekly P&L is booked on its rebalance day. "%/mo" is haircut on the WHOLE combined
curve, which understates the point-in-time books (they need no haircut). DD and worst month raw.

REGISTERED PREDICTIONS (2026-09-24, before running)
  4  every sleeve weighting lies on or below the frontier: the 1h sleeve's losses in the falls
     are the price of its wins in the booms. Shorts x0 raises drawdown; x2 is ~on the frontier.
  5  the MN overlay BEATS the frontier on both halves at k = 0.25 and 0.5 - an independent
     earner whose best regime is the trend book's worst.
  6  everything together: typical year for $221 above the triple's $584 (full), DD near 40%.

    python -m backtest.dd_fix_more
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.bear_chop import fast_run  # noqa: E402
from backtest.bull_boost import regimes  # noqa: E402
from backtest.carry_check import exact_funding  # noqa: E402
from backtest.compounding import summarize  # noqa: E402
from backtest.dd_fixes import CAP, CUT, SEEDS, build, sim  # noqa: E402
from backtest.expectations import haircut, month_ends, windows  # noqa: E402
from backtest.market_neutral import drop_non_crypto, load_panel  # noqa: E402
from backtest.wide_book import eligibility  # noqa: E402

GS = (0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0)


def weights(w):
    def gate(r, t, ctx):
        return w.get((r["side"], r["rule"]), w.get(r["side"], 1.0))
    return gate


def curve_stats(c):
    dd = float((1 - c / c.cummax()).max() * 100)
    return summarize(c)[0], dd


def main():
    bear = regimes()[1000]
    bn = pd.DatetimeIndex(bear.index).as_unit("ns").asi8
    bv = bear.to_numpy(bool)
    rows = build()
    tcut = pd.Timestamp(CUT)

    # frontier, per ordering and half
    halves = {"tune": dict(t_to=CUT), "hold": dict(t_from=CUT)}
    fr = {h: {sd: [curve_stats(sim(rows, bn, bv, sd, g=g, **kw)) for g in GS] for sd in SEEDS}
          for h, kw in halves.items()}

    def excess(h, sd, ret, dd):
        dds = np.array([x[1] for x in fr[h][sd]]); rets = np.array([x[0] for x in fr[h][sd]])
        o = np.argsort(dds)
        return ret - np.interp(dd, dds[o], rets[o], left=np.nan, right=np.nan)

    def report(name, per_seed):
        """per_seed: {half: [(ret, dd), ...]} -> one line with excess mean +- se (wins)."""
        cells, ok = "", True
        for h in ("tune", "hold"):
            ex = np.array([excess(h, sd, *per_seed[h][i]) for i, sd in enumerate(SEEDS)])
            v = ex[np.isfinite(ex)]
            ret = np.mean([x[0] for x in per_seed[h]]); dd = np.mean([x[1] for x in per_seed[h]])
            if len(v) < 5:
                cells += f"{ret:>+8.2f}%{dd:>5.0f}%{'outside':>17}"; ok = False; continue
            m, se = v.mean(), v.std(ddof=1) / np.sqrt(len(v))
            cells += f"{ret:>+8.2f}%{dd:>5.0f}%{m:>+9.2f}+-{se:.2f}({(v > 0).sum():>2})"
            ok &= m > 0
        print(f"  {name:<40}{cells}{'   <== beats the frontier on BOTH halves' if ok else ''}")

    print("Excess = %/mo above the same ordering's uniform-bet-size frontier at the same drawdown; "
          "mean +- se (wins/10).")
    print(f"  {'lever':<40}{'TUNE':>9}{'DD':>5}{'excess':>17}{'HOLD':>9}{'DD':>5}{'excess':>17}")
    ref = {h: [fr[h][sd][-1] for sd in SEEDS] for h in halves}
    report("baseline (triple, g 1.0)", ref)

    print("\n4. SLEEVE WEIGHTS")
    for name, w in (("1h longs x0", {("long", "1h"): 0.0}), ("1h longs x0.5", {("long", "1h"): 0.5}),
                    ("4h longs x0.5", {("long", "4h"): 0.5}), ("12h longs x0.5", {("long", "12h"): 0.5}),
                    ("1h x0.5, 12h x1.5", {("long", "1h"): 0.5, ("long", "12h"): 1.5}),
                    ("shorts x0", {"short": 0.0}), ("shorts x2", {"short": 2.0})):
        report(name, {h: [curve_stats(sim(rows, bn, bv, sd, gate_fn=weights(w), **kw)) for sd in SEEDS]
                      for h, kw in halves.items()})

    # 5 / 6: other books as daily return series
    C, F, first = load_panel()
    C.index = C.index.astype("datetime64[ns]")
    Fx = exact_funding(C.index, C.columns)
    mn = fast_run(C, Fx, first, drop_non_crypto(eligibility(60)), look=30, hold=7, fshift=1)
    mn_d = pd.Series(mn.net.to_numpy(), index=pd.DatetimeIndex(mn.t) + pd.Timedelta(days=7))
    mn_d = mn_d.groupby(level=0).sum()
    # the real $221 breadth sleeve, built as in triple_plus_breadth.py
    sleeve =pd.read_pickle(Path(__file__).resolve().parents[1] / "logs" / "breadth_real_1x.pkl") \
        if (Path(__file__).resolve().parents[1] / "logs" / "breadth_real_1x.pkl").exists() else None
    if sleeve is None:
        from backtest.breadth_attack import ls_signal
        from backtest.breadth_robust import breadth_n, small_account
        from backtest.market_neutral import btc_regime
        from backtest.regime_signals import member_mask
        reg = btc_regime(C).reindex(C.index)
        X = C.to_numpy(float)
        m60 = member_mask(C, first, drop_non_crypto(eligibility(60))) & np.isfinite(X)
        sig = ls_signal(breadth_n(C, m60, 20), reg == "bear")
        e5 = drop_non_crypto(eligibility(5)); months = C.index.strftime("%Y-%m")
        bym = {m: [s for s in C.columns if m in e5.get(s, ())] for m in sorted(set(months))}
        ci = {s: i for i, s in enumerate(C.columns)}
        top5 = lambda d: [s for s in bym[months[d]] if np.isfinite(X[d, ci[s]])][:5]  # noqa: E731
        sleeve = {}
        for h, t0 in (("full", None), ("hold", tcut)):
            s_ = sig if t0 is None else sig.where(sig.index >= t0, 0.0)
            sleeve[h] = small_account(C, Fx, first, s_, top5, cap=CAP)[0].pct_change().fillna(0.0)
        pd.to_pickle(sleeve, Path(__file__).resolve().parents[1] / "logs" / "breadth_real_1x.pkl")

    def combo(sd, h, k_mn, k_sl):
        c = sim(rows, bn, bv, sd, **halves[h]) if h != "full" else sim(rows, bn, bv, sd)
        r = c.pct_change().fillna(0.0)
        add = pd.Series(0.0, index=r.index)
        if k_mn:
            add = add + k_mn * mn_d.reindex(r.index).fillna(0.0)
        if k_sl:
            sl = sleeve["full" if h in ("full", "tune") else "hold"]
            add = add + k_sl * sl.reindex(r.index).fillna(0.0)
        return (1 + r + add).cumprod()

    print("\n5. MARKET-NEUTRAL OVERLAY and 6. EVERYTHING")
    combos = [(f"+ {k:g} x MN", k, 0.0) for k in (0.25, 0.5, 1.0)]
    combos += [("+ 1x breadth sleeve", 0.0, 1.0), ("+ 1x sleeve + 0.25 x MN", 0.25, 1.0),
               ("+ 1x sleeve + 0.5 x MN", 0.5, 1.0)]
    for name, kmn, ksl in combos:
        report(name, {h: [curve_stats(combo(sd, h, kmn, ksl)) for sd in SEEDS] for h in halves})

    print("\n   what $221 does in 12 months (full history; upside haircut on the whole book, downside raw)")
    print(f"   {'book':<40}{'typical':>9}{'bad yr':>8}{'good yr':>9}{'yrs<$221':>9}{'worst yr':>9}{'DD':>6}{'worst mo':>9}{'mo up':>7}")
    for name, kmn, ksl in [("triple alone", 0.0, 0.0)] + combos:
        W, DD, WM, UP = [], [], [], []
        for sd in SEEDS:
            c = combo(sd, "full", kmn, ksl)
            me = month_ends(c)
            W.append(windows(me, 12)); DD.append(float((1 - c / c.cummax()).max() * 100))
            mo = me.pct_change().dropna(); WM.append(mo.min() * 100); UP.append((mo > 0).mean() * 100)
        w = np.concatenate(W); hc = np.array([haircut(x, 12) for x in w])
        print(f"   {name:<40}${CAP*np.median(hc):>8,.0f}${CAP*np.percentile(hc, 25):>7,.0f}${CAP*np.percentile(hc, 75):>8,.0f}"
              f"{(w < 1).mean()*100:>8.0f}%${CAP*w.min():>8,.0f}{np.mean(DD):>5.0f}%{np.mean(WM):>+8.1f}%{np.mean(UP):>6.0f}%")


if __name__ == "__main__":
    main()
