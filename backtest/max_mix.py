"""THE COMBINATION, MEASURED FAIRLY AND SCALED TO TODAY'S RISK - and the user's regime idea.

The user, 2026-09-24: "the return isn't that good... I think you are understating the value", then:
"why cut the trend book to 70%... keep 100% of the trend book, and when there are reversals or a
bear market, our other strategy steps in." Three things are fixed or added here.

1. THE HAIRCUT, applied only where it belongs. Doc 14 haircut the WHOLE mix, but the 3x hindsight
   haircut belongs to the trend book's 12 hand-picked coins. The market-neutral book and the
   breadth sleeve are point-in-time and need none. withdraw.py also haircut every up-month.
   The method: SHRINK THE TREND BOOK'S GAINS, KEEP ITS LOSSES. Each ordering gets a factor s < 1
   that multiplies every positive daily trend return, solved so the deployed triple's full-history
   growth falls from its raw CAGR to raw/3 (the repo's haircut). Losses stay whole ("downside raw").
   The two point-in-time books stay raw.
   A first version used a constant daily DRAG instead. It matched the typical year ($560 against
   $584) but put today's triple at an 84% fall and a $69 worst year, against a real 53%. Hindsight
   inflates the winners, not the losers, so that version was replaced before any result was used
   (its partial log was overwritten).
2. SCALE TO TODAY'S RISK. The trend book at g 0.7-1.3 of today's size with the 21-day equity anchor
   (doc 14), breadth sleeve 1-2x, market-neutral 0.5-1x. Every fall is measured by the same method
   as "today", so "no worse than today" compares like with like.
3. THE USER'S IDEA: the other books step in when the trend book is weak. The market-neutral book is
   sized by btc_regime at each rebalance: SMALL in BULL (the trend book needs the margin there, and
   its 10x peaks are all in bulls) and LARGE in CHOP/BEAR, where the trend book's falls happen. The
   breadth sleeve already trades only in BEAR.
MARGIN: the trend book's gross guard is lowered by the MN book's BULL size (10 - k_bull).
NOT MODELLED: the MN book is booked weekly, so its swings inside a week are invisible (worst week at
1x is -24%, logs/carry_check.txt), and the falls here are slightly too shallow for large MN shares.

REGISTERED PREDICTION (2026-09-24, before running): today's triple reads ~$584 typical with a fall
near 60% under this method. The best mix with a fall no worse than today's has a typical year of
$1,300-1,800 on $221, and "take half of each month's profit" gives $60-90 a month. The regime-sized
MN book beats a fixed-size one at an equal fall.

    python -m backtest.max_mix
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.bar_phase import rows_for_phase  # noqa: E402
from backtest.bear_chop import fast_run  # noqa: E402
from backtest.bull_boost import regimes  # noqa: E402
from backtest.carry_check import exact_funding  # noqa: E402
from backtest.dd_fixes import CAP, CUT, SEEDS, anchor, decompose, sim  # noqa: E402
from backtest.expectations import month_ends, windows  # noqa: E402
from backtest.market_neutral import btc_regime, drop_non_crypto, load_panel  # noqa: E402
from backtest.wide_book import eligibility  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
HINDSIGHT = 3.0


def plan_a(m):
    bal, out = CAP, 0.0
    for x in m:
        bal *= x
        if bal > CAP:
            out += bal - CAP; bal = CAP
    return out


def plan_b(m):
    bal, out = CAP, 0.0
    for x in m:
        prev = bal; bal *= x
        if bal > prev:
            t = 0.5 * (bal - prev); out += t; bal -= t
    return out, bal


def cagr(c):
    yrs = (c.index[-1] - c.index[0]).days / 365.25
    return c.iloc[-1] ** (1 / yrs) - 1


def shrink_factor(r):
    """s such that compounding where(r > 0, s*r, r) grows at raw_cagr / 3 a year."""
    idx = r.index
    raw = cagr((1 + r).cumprod())
    target = raw / HINDSIGHT
    lo, hi = 0.0, 1.0
    for _ in range(50):
        s = (lo + hi) / 2
        g = cagr(pd.Series(np.cumprod(1 + np.where(r > 0, s * r, r)), index=idx))
        lo, hi = (s, hi) if g < target else (lo, s)
    return (lo + hi) / 2


def main():
    bear = regimes()[1000]
    bn = pd.DatetimeIndex(bear.index).as_unit("ns").asi8
    bv = bear.to_numpy(bool)
    C, F, first = load_panel()
    C.index = C.index.astype("datetime64[ns]")
    reg = btc_regime(C)
    Fx = exact_funding(C.index, C.columns)
    mn = fast_run(C, Fx, first, drop_non_crypto(eligibility(60)), look=30, hold=7, fshift=1)
    mn_reg = np.array([reg.asof(t) if t >= reg.index[0] else "chop" for t in pd.DatetimeIndex(mn.t)])
    mn_idx = pd.DatetimeIndex(mn.t) + pd.Timedelta(days=7)
    sleeve = pd.read_pickle(ROOT / "logs" / "breadth_real_1x.pkl")["full"]
    rows = decompose(rows_for_phase(0, tight=True, time_stop=(100, 2.0), max_units=7))

    def mn_series(k_bull, k_other):
        k = np.where(mn_reg == "bull", k_bull, k_other)
        return pd.Series(mn.net.to_numpy() * k, index=mn_idx).groupby(level=0).sum()

    cache = {}

    def trend(sd, g, lev, anc):
        key = (sd, g, lev, anc)
        if key not in cache:
            c = sim(rows, bn, bv, sd, g=g, lev=lev, size_fn=anchor(21) if anc else None)
            cache[key] = c.pct_change().fillna(0.0)
        return cache[key]

    s_f = {sd: shrink_factor(trend(sd, 1.0, 10.0, False)) for sd in SEEDS}
    print(f"gain-shrink factor on the trend book (so its growth = raw CAGR / 3, losses kept whole): "
          f"{np.mean(list(s_f.values())):.3f} (range {min(s_f.values()):.3f}-{max(s_f.values()):.3f})\n")

    def book(sd, g, k_sl, k_bull, k_other, anc=True, fair=True):
        r = trend(sd, g, 10.0 - k_bull, anc)
        if fair:
            r = pd.Series(np.where(r > 0, s_f[sd] * r, r), index=r.index)
        add = k_sl * sleeve.reindex(r.index).fillna(0.0)
        if k_bull or k_other:
            add = add + mn_series(k_bull, k_other).reindex(r.index).fillna(0.0)
        return (1 + r + add).cumprod()

    def report(name, curves, t0=None, show=True):
        W, DD, WM, UP, MED, A, B, BE = [], [], [], [], [], [], [], []
        for c in curves:
            if t0 is not None:
                c = c[c.index >= t0]; c = c / c.iloc[0]
            me = month_ends(c)
            m = (me / me.shift(1)).dropna().to_numpy()
            W.append(windows(me, 12)); DD.append(float((1 - c / c.cummax()).max() * 100))
            WM.append((m.min() - 1) * 100); UP.append((m > 1).mean() * 100); MED.append(np.median(m) - 1)
            for i in range(len(m) - 11):
                A.append(plan_a(m[i:i + 12])); b, be = plan_b(m[i:i + 12]); B.append(b); BE.append(be)
        w = np.concatenate(W)
        if show:
            print(f"  {name:<52}${CAP*np.median(w):>7,.0f}${CAP*np.percentile(w, 25):>6,.0f}{(w < 1).mean()*100:>5.0f}%"
                  f"${CAP*w.min():>5,.0f}{np.mean(DD):>5.0f}%{np.mean(WM):>+7.1f}%{np.mean(UP):>5.0f}%"
                  f"{CAP*np.mean(MED):>+6.0f}${np.median(B)/12:>6.0f}${np.median(BE):>7,.0f}${np.median(A)/12:>6.0f}")
        return np.mean(DD), np.median(w)

    hdr = (f"  {'book':<52}{'typ yr':>8}{'bad yr':>7}{'<$221':>6}{'worst':>6}{'fall':>6}{'wst mo':>8}{'up':>5}"
           f"{'typ mo':>7}{'B/mo':>7}{'B left':>8}{'A/mo':>7}")
    print("$221 over 12 months, 10 orderings, 2020-2026. Trend book's GAINS shrunk (hindsight), its losses whole;")
    print("the two point-in-time books raw. typ/bad yr = median / 25th pct of every 12-month window; fall = biggest")
    print("drop; typ mo = median month ($); B = take half of each month's profit ($/month taken, balance left after")
    print("12 months); A = take everything above $221 each month ($/month).\n")
    print(hdr)
    dd_today, _ = report("TODAY: triple alone", [book(sd, 1.0, 0, 0, 0, anc=False) for sd in SEEDS])
    report("doc 14 pick: trend 70% + anchor + sleeve + 0.5 MN", [book(sd, 0.7, 1.0, 0.5, 0.5) for sd in SEEDS])
    report("user's idea, plain: trend 100% + sleeve + 0.5 MN", [book(sd, 1.0, 1.0, 0.5, 0.5, anc=False) for sd in SEEDS])
    report("(raw, no haircut at all: today's triple)", [book(sd, 1.0, 0, 0, 0, anc=False, fair=False) for sd in SEEDS])

    print(f"\nTHE GRID - every mix; marked * if its fall is no worse than today's ({dd_today:.0f}%)")
    print(hdr)
    res = []
    mn_opts = [(0.5, 0.5), (0.75, 0.75), (1.0, 1.0), (0.25, 1.0), (0.5, 1.0), (0.5, 1.5), (0.25, 1.5)]
    for g in (0.7, 0.85, 1.0, 1.15, 1.3):
        for k_sl in (1.0, 1.5, 2.0):
            for kb, ko in mn_opts:
                name = f"trend {g*100:.0f}%+anc | sleeve {k_sl:g}x | MN {kb:g} bull / {ko:g} else"
                dd, typ = report(name, [book(sd, g, k_sl, kb, ko) for sd in SEEDS], show=False)
                res.append((typ, dd, name, g, k_sl, kb, ko))
    res.sort(key=lambda z: -z[0])
    shown = 0
    for typ, dd, name, g, k_sl, kb, ko in res:
        if shown >= 25:
            break
        mark = "*" if dd <= dd_today else " "
        report(("* " if mark == "*" else "  ") + name, [book(sd, g, k_sl, kb, ko) for sd in SEEDS])
        shown += 1
    ok = [z for z in res if z[1] <= dd_today]
    print(f"\n{len(ok)} of {len(res)} mixes have a fall no worse than today's triple.")
    fixed = [z for z in ok if z[5] == z[6]]; switched = [z for z in ok if z[5] != z[6]]
    if fixed and switched:
        print(f"  best with a FIXED-size MN book:   ${CAP*fixed[0][0]:,.0f} typical, fall {fixed[0][1]:.0f}%  ({fixed[0][2]})")
        print(f"  best with a REGIME-sized MN book: ${CAP*switched[0][0]:,.0f} typical, fall {switched[0][1]:.0f}%  ({switched[0][2]})")
    if ok:
        typ, dd, name, g, k_sl, kb, ko = ok[0]
        print("\nTHE BEST MIX AT TODAY'S RISK, LAST 2 YEARS ONLY (from 2024-08-29), against today's triple:")
        print(hdr)
        report(name, [book(sd, g, k_sl, kb, ko) for sd in SEEDS], t0=pd.Timestamp(CUT))
        report("TODAY: triple alone", [book(sd, 1.0, 0, 0, 0, anc=False) for sd in SEEDS], t0=pd.Timestamp(CUT))


if __name__ == "__main__":
    main()
