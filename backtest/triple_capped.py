"""THE TRIPLE BOOK WITH THE LIVE BOT'S 10x MARGIN GUARD - the honest version of +10.76%/mo.

regime_and_liq.py (the other session) found the triple (tight + time stop + 7 units) reaches
12.2x gross leverage for 731 hours, and that blend_paper.py refuses any entry or pyramid add
that would take gross notional past MAX_LEVERAGE x equity. No backtest modelled that guard, so
every triple figure quoted so far (+10.76%/mo holdout, $568-619 a year) assumes adds the live
bot would block. Its estimate from a count: 293 of 4,315 sixth/seventh units blocked, the
7-unit gain falling from ~+1.5 to ~+1.4 %/mo. This measures it on the equity path instead.

HOW
    Every long position is decomposed into its units (entry level e_k = e0 + k*2R, known when
    its add bar closes; mtm_sizing.attach_prices). The exit price is solved from the position's
    price-R, so each unit's own R is exact: R_k = (x - e_k)/r - fee*e_k/r. Funding is split over
    the units in proportion to how long each was held. GUARD CHECK: the sum of those unit R's plus
    funding must reproduce the row's R to 1e-6, and with the guard OFF the whole simulation must
    reproduce units_on_tstop.py's entry-sized result.
    Account: entry-sized (a unit's dollars fixed at its position's entry from realised equity -
    the bot's convention), 12 slots, 1000h gate. The GUARD, as blend_paper.py applies it: an
    entry or add is refused if open notional (units at their fill prices) plus the new unit
    would exceed 10x realised equity.

REGISTERED PREDICTION: the guard costs the triple 0.1-0.2 %/mo on each half (the other
session's +1.5 -> +1.4), leaves 5-unit books almost untouched, and lowers the worst month.

    python -m backtest.triple_capped
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import blend  # noqa: E402
from backtest.bear_side import sleeve_sided  # noqa: E402
from backtest.bull_boost import regimes  # noqa: E402
from backtest.causal_t0 import real_t0  # noqa: E402
from backtest.compounding import summarize  # noqa: E402
from backtest.engine_variants import break_map, shorts_for  # noqa: E402
from backtest.expectations import haircut, month_ends, windows  # noqa: E402
from backtest.funding_cost import charged, long_funding, short_funding  # noqa: E402
from backtest.graveyard_rescore import walk  # noqa: E402
from backtest.mtm_sizing import attach_prices  # noqa: E402
from backtest.timeframes import resample  # noqa: E402

SEEDS = tuple(range(10))
FEE = blend.FEE_BP / 1e4
LEV = 10.0
CAP = 221.0


def build(tight=True, time_stop=(100, 2.0), max_units=7):
    raw = []
    for rule in ("1h", "4h", "12h"):
        raw += shorts_for(rule)
        for coin in blend.BOOK:
            d = blend.load(coin)
            if d is None:
                continue
            df = resample(d, rule)
            if len(df) < 300:
                continue
            tb = break_map(df, rule) if tight else None
            raw += walk(df, rule, coin, tb=tb, time_stop=time_stop, max_units=max_units)
    rows = charged(real_t0(short_funding(long_funding(attach_prices(raw)))))
    out = []
    for r in rows:
        risk, t1 = r["risk"], pd.Timestamp(r["t1"]).value
        units = r["units"]
        fund = r.get("fund", 0.0)
        if r["side"] == "long":
            n = len(units)
            se = sum(e for e, _ in units)
            x = (r["R"] - fund + (1 + FEE) * se / risk) * risk / n      # solve the exit price
            rk = [(x - e) / risk - FEE * e / risk for e, _ in units]
        else:
            rk = [r["R"] - fund]
        hold = np.array([max(t1 - tk, 1) for _, tk in units], float)
        fk = fund * hold / hold.sum()
        uR = np.array(rk) + fk
        assert abs(uR.sum() - r["R"]) < 1e-6, (r["coin"], r["rule"], uR.sum(), r["R"])
        out.append(dict(t0=pd.Timestamp(r["t0"]).value, t1=t1, side=r["side"], uR=uR,
                        ut=[tk for _, tk in units], ue=[e for e, _ in units], risk=risk))
    out.sort(key=lambda z: z["t0"])
    return out


def simulate(rows, bear_ns, bear_v, seed, lev=LEV, t_from=None, t_to=None):
    rng = np.random.default_rng(seed)
    tie = rng.random(len(rows))
    o = [rows[i] for i in sorted(range(len(rows)), key=lambda i: (rows[i]["t0"], tie[i]))]
    if t_from is not None:
        o = [r for r in o if r["t0"] >= t_from]
    if t_to is not None:
        o = [r for r in o if r["t0"] < t_to]
    eq = 1.0
    events = []                      # (time, kind, pos index, unit k); kind 0 close, 1 entry/add
    pos = []
    for j, r in enumerate(o):
        events.append((r["t0"], 1, j, 0))
        for k in range(1, len(r["ut"])):
            events.append((max(r["ut"][k], r["t0"]), 1, j, k))
        # closes sort BEFORE new risk at the same instant (a slot freed at t is usable at t,
        # as in btc_dial.taken) - EXCEPT a position that closes on its own entry bar, whose
        # close must follow its own entry. Sorting it first leaked it: popped before it was
        # opened, it never closed and held a slot forever (first run: 1,116 trades taken
        # instead of 1,893, and a guard that never fired because the book was starved).
        events.append((r["t1"], 0 if r["t1"] > r["t0"] else 2, j, -1))
    events.sort(key=lambda e: (e[0], e[1]))
    state = {}
    open_n = 0
    pts, blocked, tried = [], 0, 0
    for t, kind, j, k in events:
        r = o[j]
        if kind in (0, 2):
            s = state.pop(j, None)
            if s is None:
                continue
            open_n -= 1
            eq = max(eq + s["dpr"] * sum(r["uR"][kk] for kk in s["units"]), 0.0)
            pts.append((t, eq))
            continue
        if k == 0:
            if open_n >= 12:
                continue
            ib = bear_v[max(np.searchsorted(bear_ns, t, side="right") - 1, 0)]
            f = blend.RISK / 100.0 * (blend.REGIME_MULT if ib else 1.0)
            dpr = f * eq                                    # dollars per R, fixed at entry
            s = dict(dpr=dpr, units=[])
        else:
            s = state.get(j)
            if s is None:
                continue
        notional = s["dpr"] * r["ue"][k] / r["risk"]
        gross = sum(st["dpr"] * o[jj]["ue"][kk] / o[jj]["risk"]
                    for jj, st in state.items() for kk in st["units"])
        if k > 0:
            tried += 1
        if gross + notional > lev * eq:
            if k > 0:
                blocked += 1
            continue                                        # refused, like blend_paper.py
        s["units"].append(k)
        if k == 0:
            state[j] = s; open_n += 1
    c = pd.Series([p[1] for p in pts], index=pd.to_datetime([p[0] for p in pts])).resample("D").last().ffill()
    return c, blocked, tried


def main():
    bear = regimes()[1000]
    bear_ns = pd.DatetimeIndex(bear.index).as_unit("ns").asi8
    bear_v = bear.to_numpy(bool)
    ts = pd.DatetimeIndex(sorted(x[0] for x in sleeve_sided("1h")[0]))
    cut = ts[int(len(ts) * 0.6)].value
    books = {"main (5 units)": build(tight=False, time_stop=None, max_units=5),
             "tight + time stop (5 units)": build(max_units=5),
             "TRIPLE (tight + time stop + 7 units)": build(max_units=7)}
    print("entry-sized, 12 slots, 1000h gate, 10 orderings | %/mo = CAGR/3 (haircut); DD/worst raw\n")
    print(f"  {'book':<38}{'guard':>8}{'TUNE':>8}{'HOLD':>8}{'DD':>6}{'worst':>8}{'adds blocked':>15}")
    res = {}
    for lab, rows in books.items():
        for lev in (np.inf, LEV):
            T, H, D, W, B = [], [], [], [], []
            for sd in SEEDS:
                tune, _b, _t = simulate(rows, bear_ns, bear_v, sd, lev, t_to=cut)
                ch, bl, tr = simulate(rows, bear_ns, bear_v, sd, lev, t_from=cut)
                T.append(summarize(tune)[0]); H.append(summarize(ch)[0])
                D.append((1 - ch / ch.cummax()).max() * 100)
                W.append(ch.resample("ME").last().pct_change().min() * 100)
                B.append(bl / max(tr, 1) * 100)
            res[(lab, lev)] = (np.array(T), np.array(H))
            print(f"  {lab:<38}{'off' if lev == np.inf else '10x':>8}{np.mean(T):>+7.2f}%{np.mean(H):>+7.2f}%"
                  f"{np.mean(D):>5.0f}%{np.mean(W):>+7.1f}%{np.mean(B):>13.1f}%")
    print("\n  cost of the guard, paired on the same orderings:")
    for lab in books:
        dT = res[(lab, LEV)][0] - res[(lab, np.inf)][0]
        dH = res[(lab, LEV)][1] - res[(lab, np.inf)][1]
        print(f"    {lab:<38} tune {dT.mean():+.2f} +- {dT.std(ddof=1)/np.sqrt(len(dT)):.2f}   "
              f"hold {dH.mean():+.2f} +- {dH.std(ddof=1)/np.sqrt(len(dH)):.2f} %/mo")
    # one year from $221 for the capped triple, holdout starts
    rows = books["TRIPLE (tight + time stop + 7 units)"]
    for lab_w, tf in (("holdout", cut), ("full", None)):
        w = np.concatenate([windows(month_ends(simulate(rows, bear_ns, bear_v, sd, LEV, t_from=tf)[0]), 12)
                            for sd in SEEDS])
        h = np.array([haircut(x, 12) for x in w])
        print(f"\n  TRIPLE with the 10x guard, $221 after 12 months ({lab_w}): typical "
              f"${CAP*np.median(h):,.0f} (haircut) / ${CAP*np.median(w):,.0f} raw; bad year (25th) "
              f"${CAP*np.percentile(h, 25):,.0f}; ended below $221 {(w < 1).mean()*100:.0f}%; worst ${CAP*w.min():,.0f} raw")


if __name__ == "__main__":
    main()
