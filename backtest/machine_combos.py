"""THE MACHINE WITH EVERYTHING THAT PASSED - and the market-neutral book on every rebalance day (2026-10-08).

Inputs from today's combination tests:
    mn_combos.py / logs/mn_rebalance_days.txt  the market-neutral book was only ever measured on ONE rebalance day. On the
        seven: six fine, one WIPED OUT on the holdout (2025-09-12 week, -99%: MYX squeezed its short basket). v2's
        published figures (machine.py) use the lucky day. The live bot's 30% disaster stop is no protection - it is a
        backstop the netting re-enters 2 minutes later. A short-leg BOOK exit at +50% (out until the next rebalance)
        keeps the average Sharpe (+1.06 / +1.31 vs +1.06 / +1.33) and removes the wipe-out (worst day +0.85 / +0.76).
    capit_combos.py / capit_stack.py  the capitulation book improved: only coins down >= 10% in 24h, bought with a limit
        2% under the signal close (next bar only) - passes in all 4 phases, also with a 0.3% trade-through fill.
    daily_combos.py  nothing beat the daily book's base; it is kept as it is.
Built here per ordering k (10): trend = v2's triple (worst_month.TCACHE "anchor", gains shrunk for hindsight); MN on
rebalance day k % 7; daily book on day boundary (0, 8, 16)[k % 3]; capitulation book on phase (0, 60, 120, 180)[k % 4];
sleeve and bids as machine.py. $300, machine.summary, 6 years and the last 2.

    A  v2 as published (MN on its one lucky day)       B  v2 with MN on the rotating day (the honest v2)
    C  B with the short-leg exit at +50% ("v2 safe")    D  C + daily + capitulation (base)        = "v2.1 safe"
    E  C + daily + capitulation IMPROVED                 F  E with the improved capitulation at 2x
    G  E with volatility targeting (30-day realised vol, causal target, scale capped at 2)
    H  E with regime weights fixed in advance: bull trend/daily 1, MN 0.5; chop trend/daily 0.5, MN 1.5; bear
       trend/daily 0.5, MN 1, sleeve 1.5, capitulation 1.5
    I  E with the daily book kept OFF the 12 trend coins (no doubling up)
    ablations of E: without the bids / the sleeve / MN / capitulation / daily
THE LINE: C x k - an addition counts only if it beats a smaller "v2 safe" at the same worst month, on both spans.

REGISTERED BEFORE RUNNING:
    B  the rotating MN deepens v2's worst month by 3-8 points and its biggest fall to 65-80%: the published v2 is lucky.
    C  removes most of that, back within 2 points of A's worst month.
    D/E pass the line on both spans (as v2_addons.py found); E beats D by a small margin (+3..+8% typical year).
    F  2x capitulation adds a little more; passes.  G  vol targeting fails the line (doc 14: sizing rules lose to
    betting smaller).  H  regime weights fail on at least one span.  I  ties D/E within 5%.
    Ablations: removing the bids, sleeve or capitulation costs under 10% of the typical year; removing MN or daily
    costs more than 15%.

RESULT (2026-10-08, logs/machine_combos.txt; $300, 6 years / last 2): A v2 as published $1,812 / $1,625, worst
    month -29.3%. B v2 with MN on the rotating day: typical $2,385 / $3,134 but WORST YEAR $17 (the wipe-out) and worst
    month -35.6%. C "v2 safe" (MN short-leg exit +50%): $2,248 / $2,741, -31.3%, worst year $196. D / E (C + daily +
    capitulation, base / improved): BEAT the line +10% / +11% (6y) and +35% / +34% (2y); F (improved capit x2) +20% /
    +41%; I (daily off the 12 trend coins) +14% / +40%. G vol targeting fails (-37% / -39%). H regime weights read +45%
    / +70% - A LOOK-AHEAD (the trend book is booked at its close); fixed in regime_weights.py it FAILS (-12% on 6y).
    Scaled to the published v2's typical year: E x0.70 worst month -26.0% (C x0.85 -27.2%, A -29.3%), fall 46% vs 49%
    vs 57%. So with the MN measured honestly, the add-ons buy ~1 point of worst month, not 8 (v2_addons.py's -21% sat
    on the lucky MN day). Ablations of E: without MN on the line (+1%) for 6y, -25% for 2y; without the sleeve fails
    (-10% 6y); bids / capitulation / daily each add a few points. Predictions: B deepens the worst month 3-8 points -
    right (+6.3); C within 2 of A - right; D/E pass - right; F passes - right; G fails - right; H fails - right once the
    leak was removed; I ties - right; ablations: MN > 15% - right on 2y, WRONG on 6y.

    python -m backtest.machine_combos
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest import capit_combos as cc  # noqa: E402
from backtest import daily_combos as dc  # noqa: E402
from backtest import mn_combos as mc  # noqa: E402
from backtest import pair_lab as pl  # noqa: E402
from backtest.blend import BOOK  # noqa: E402
from backtest.machine import CUT, summary  # noqa: E402
from backtest.worst_month import TCACHE  # noqa: E402

LOG = ROOT / "logs" / "machine_combos.txt"
PARTS = ROOT / "logs" / "daily_combos_cache" / "machine_parts.pkl"
SEEDS = tuple(range(10))
CAPIT_BETTER = dict(filt=lambda S: S.drop24 <= -0.10, entry=("limit", 0.02, 1))


def parts():
    if PARTS.exists():
        return pickle.loads(PARTS.read_bytes())
    cache = pickle.loads(TCACHE.read_bytes())
    sleeve = pd.read_pickle(ROOT / "logs" / "breadth_real_1x.pkl")["full"]
    bids = pd.read_pickle(ROOT / "logs" / "wick_capped.pkl")[10]
    mn_pub = pl.mn_daily()
    mn_rot = {o: mc.mn_run(start=o) for o in range(7)}
    mn_safe = {o: mc.mn_run(start=o, stop="short_only", short_stop=0.5) for o in range(7)}
    dT = {off: dc.gen(off, dc.BASE) for off in dc.PHASES}
    cT = {off: cc.gen(off, cc.BASE) for off in cc.PHASES}
    cT2 = {off: cc.gen(off, dict(cc.BASE, **CAPIT_BETTER)) for off in cc.PHASES}
    out = {}
    for sd in SEEDS:
        t = cache[("anchor", sd)]
        idx = t.index
        doff, coff, moff = dc.PHASES[sd % 3], cc.PHASES[sd % 4], sd % 7
        r = lambda s: s.reindex(idx).fillna(0.0)  # noqa: E731
        D = dT[doff]
        Dx = D[~D.coin.isin(BOOK)].reset_index(drop=True)
        daily = dc.curve(D, dc.allocate(D, sd), doff).pct_change()
        daily_x = dc.curve(Dx, dc.allocate(Dx, sd), doff).pct_change()
        cap = cc.curve(cT[coff], dc.allocate(cT[coff].assign(units=None), sd)).pct_change()
        cap2 = cc.curve(cT2[coff], dc.allocate(cT2[coff].assign(units=None), sd)).pct_change()
        out[sd] = pd.DataFrame({"trend": t, "mn_pub": r(mn_pub), "mn_rot": r(mn_rot[moff]), "mn_safe": r(mn_safe[moff]),
                                "sleeve": r(sleeve), "bids": r(bids),
                                # the books are whole-account curves; x0.5 = half the account each, as in the pair
                                "daily": 0.5 * r(daily), "daily_x": 0.5 * r(daily_x), "capit": 0.5 * r(cap),
                                "capit2": 0.5 * r(cap2)})
    PARTS.write_bytes(pickle.dumps(out))
    return out


def vol_target(x, cap=2.0):
    vol = x.rolling(30).std().shift(1)
    tgt = vol.expanding(min_periods=60).median()
    return x * (tgt / vol).clip(upper=cap).fillna(1.0)


def main():
    P = parts()
    reg = pl.btc_regime_daily()
    C_ = dict(trend=1, mn_safe=1, sleeve=1, bids=1)
    E_ = dict(C_, daily=1, capit2=1)
    W = {
        "A v2 as published (MN on its lucky day)": dict(trend=1, mn_pub=1, sleeve=1, bids=1),
        "B v2, MN on the rotating day": dict(trend=1, mn_rot=1, sleeve=1, bids=1),
        "C v2 safe (MN short-leg exit +50%)": C_,
        "D v2.1 safe = C + daily + capitulation": dict(C_, daily=1, capit=1),
        "E C + daily + capitulation IMPROVED": E_,
        "F E with improved capitulation x2": dict(E_, capit2=2),
        "G E + volatility targeting": dict(E_, _vt=1),
        "H E with regime weights": dict(E_, _reg=1),
        "I E, daily book off the 12 trend coins": dict(C_, daily_x=1, capit2=1),
        "  E without the bids": {k: v for k, v in E_.items() if k != "bids"},
        "  E without the sleeve": {k: v for k, v in E_.items() if k != "sleeve"},
        "  E without MN": {k: v for k, v in E_.items() if k != "mn_safe"},
        "  E without capitulation": {k: v for k, v in E_.items() if k != "capit2"},
        "  E without daily": {k: v for k, v in E_.items() if k != "daily"},
        "  E without trend (= v3-like, safe MN x1)": {k: v for k, v in E_.items() if k != "trend"},
    }
    RW = {"bull": dict(trend=1, daily=1, mn_safe=0.5), "chop": dict(trend=0.5, daily=0.5, mn_safe=1.5),
          "bear": dict(trend=0.5, daily=0.5, mn_safe=1, sleeve=1.5, capit2=1.5)}

    def build(w, k=1.0):
        xs = []
        for sd in SEEDS:
            b = P[sd]
            if w.get("_reg"):
                lab0 = reg.reindex(b.index, method="ffill").fillna("chop")
                x = pd.Series(0.0, index=b.index)
                # a part BOOKED after it is held must be sized by the label at its ENTRY: MN books a week's P&L on the
                # day it closes (label 7 days earlier), a capitulation trade ~1.4 days after it opens (2 days earlier)
                lags = {"mn_safe": 7, "capit2": 2}
                for p_ in ("trend", "mn_safe", "sleeve", "bids", "daily", "capit2"):
                    lab = lab0.shift(lags.get(p_, 0)).fillna("chop").to_numpy()
                    wt = np.array([RW.get(l_, {}).get(p_, w.get(p_, 0)) for l_ in lab])
                    x = x + wt * b[p_]
            else:
                x = sum(v * b[p_] for p_, v in w.items() if not p_.startswith("_"))
                if w.get("_vt"):
                    x = vol_target(x)
            xs.append(k * x)
        return xs

    spans = (("all 6 years", None), ("last 2 years", CUT))
    front = {sp: [] for sp, _ in spans}
    for k in np.round(np.arange(0.4, 1.81, 0.05), 2):
        xs = build(C_, k)
        for sp, t0 in spans:
            s = summary(xs, t0)
            front[sp].append((s["wm"], s["typ"]))

    def on_line(sp, wm):
        f = sorted(front[sp])
        return float(np.interp(wm, [a for a, _ in f], [b for _, b in f]))

    lines = [f"backtest/machine_combos.py, {pd.Timestamp.now():%Y-%m-%d %H:%M}; $300, 10 orderings (MN rebalance day, daily "
             f"boundary and capitulation phase rotated with the ordering); trend gains shrunk for hindsight, the rest raw", ""]
    for sp, t0 in spans:
        lines.append(f"{sp}: $300 after 12 months - typical / bad / worst | under $300 | worst month | fall | months up "
                     f"|| 'v2 safe' x k at the same worst month -> verdict")
        for nm, w in W.items():
            s = summary(build(w), t0)
            ref = on_line(sp, s["wm"])
            tag = "" if nm[0] in "ABC" else ("BEATS" if s["typ"] > ref * 1.02 else "no")
            lines.append(f"  {nm:44} ${s['typ']:>6,.0f} / ${s['bad']:>6,.0f} / ${s['worst']:>5,.0f} | {s['below']:3.0f}% | "
                         f"{s['wm']:+6.1f}% | {s['dd']:3.0f}% | {s['up']:3.0f}% || ${ref:>6,.0f} {tag} ({(s['typ'] / ref - 1) * 100:+.0f}%)")
            print(lines[-1], flush=True)
        lines.append("")
    lines.append("the line ('v2 safe' x k, all 6 years): " + "; ".join(
        f"{wm:+.1f}% ${ty:,.0f}" for (wm, ty), k in zip(sorted(front['all 6 years'], reverse=True),
                                                        np.round(np.arange(0.4, 1.81, 0.05), 2)) if k in (0.5, 0.75, 1.0, 1.25, 1.5)))
    lines.append("")
    lines.append("SCALED TO THE PUBLISHED v2's TYPICAL YEAR (all 6 years): the worst month each then has")
    a = summary(build(W["A v2 as published (MN on its lucky day)"]))
    for nm in ("B v2, MN on the rotating day", "C v2 safe (MN short-leg exit +50%)", "D v2.1 safe = C + daily + capitulation",
               "E C + daily + capitulation IMPROVED", "F E with improved capitulation x2"):
        best = min(((g, summary(build(W[nm], g))) for g in np.round(np.arange(0.4, 1.61, 0.05), 2)),
                   key=lambda z: abs(z[1]["typ"] - a["typ"]))
        g, s = best
        s2 = summary(build(W[nm], g), CUT)
        lines.append(f"  {nm:44} x{g:.2f}: typical ${s['typ']:,.0f}, worst month {s['wm']:+.1f}%, fall {s['dd']:.0f}%, worst "
                     f"year ${s['worst']:,.0f} | last 2y ${s2['typ']:,.0f}, {s2['wm']:+.1f}%, fall {s2['dd']:.0f}%")
    lines.append(f"  (A itself: typical ${a['typ']:,.0f}, worst month {a['wm']:+.1f}%, fall {a['dd']:.0f}%)")
    txt = "\n".join(lines)
    LOG.write_text(txt + "\n")
    print("\n" + txt)


if __name__ == "__main__":
    main()
