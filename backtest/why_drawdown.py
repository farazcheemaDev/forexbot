"""WHY DOES THE ACCOUNT STILL FALL TO HALF, WITH LONGS, SHORTS AND A BEAR SLEEVE?

Asked 2026-09-24 after triple_plus_breadth.py: the triple book (tight + time stop + 7 units, 10x
guard) has a 50-53% drawdown, and adding the breadth sleeve only takes it to 44-49%. The book
trades both directions, so why is it not hedged?

WHAT THIS DOES
    Re-runs triple_capped's entry-sized simulation with a trade log (the curve is REALISED
    equity - it moves when positions close, as the bot's own sizing does), finds the largest
    peak-to-trough fall for every ordering, and takes apart the worst ones:
      * when: dates, days, what BTC did, how many days were bull / chop / bear
      * who lost: longs vs shorts, 1h/4h/12h, full stop-outs (<= -0.9R) vs small losses vs
        winners, and how big positions were (dollars per R set at entry from a PEAK equity)
      * the sleeve: what the breadth sleeve did over the same days, and why
      * the giveback: how much of the loss is profit that had been open at the peak

REGISTERED PREDICTION (2026-09-24, before running): the big drops start right after a strong
bull run and run through the CHOP that follows, not through bears. At least 60% of the loss is
longs stopped out near -1R (whipsaw), sized large because equity had just peaked. The shorts
lose in the same stretch (a 5xATR short trail is whipsawed by chop just as a long is). The sleeve
is mostly idle because the days are chop, not bear.

    python -m backtest.why_drawdown
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import blend  # noqa: E402
from backtest.bull_boost import regimes  # noqa: E402
from backtest.causal_t0 import real_t0  # noqa: E402
from backtest.engine_variants import break_map, shorts_for  # noqa: E402
from backtest.funding_cost import charged, long_funding, short_funding  # noqa: E402
from backtest.graveyard_rescore import walk  # noqa: E402
from backtest.market_neutral import btc_regime, load_panel  # noqa: E402
from backtest.mtm_sizing import attach_prices  # noqa: E402
from backtest.timeframes import resample  # noqa: E402

FEE = blend.FEE_BP / 1e4
SEEDS = tuple(range(10))


def build_meta():
    """triple_capped.build(max_units=7), keeping coin / rule / total R for attribution."""
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
            raw += walk(df, rule, coin, tb=break_map(df, rule), time_stop=(100, 2.0), max_units=7)
    rows = charged(real_t0(short_funding(long_funding(attach_prices(raw)))))
    out = []
    for r in rows:
        risk, t1 = r["risk"], pd.Timestamp(r["t1"]).value
        units, fund = r["units"], r.get("fund", 0.0)
        if r["side"] == "long":
            n = len(units); se = sum(e for e, _ in units)
            x = (r["R"] - fund + (1 + FEE) * se / risk) * risk / n
            rk = [(x - e) / risk - FEE * e / risk for e, _ in units]
        else:
            rk = [r["R"] - fund]
        hold = np.array([max(t1 - tk, 1) for _, tk in units], float)
        uR = np.array(rk) + fund * hold / hold.sum()
        out.append(dict(t0=pd.Timestamp(r["t0"]).value, t1=t1, side=r["side"], uR=uR,
                        ut=[tk for _, tk in units], ue=[e for e, _ in units], risk=risk,
                        coin=r["coin"], rule=r["rule"], R=float(r["R"])))
    out.sort(key=lambda z: z["t0"])
    return out


def simulate_log(rows, bear_ns, bear_v, seed, lev=10.0):
    """triple_capped.simulate, plus a log of every close: its dollar P&L as a share of equity."""
    rng = np.random.default_rng(seed)
    tie = rng.random(len(rows))
    o = [rows[i] for i in sorted(range(len(rows)), key=lambda i: (rows[i]["t0"], tie[i]))]
    events = []
    for j, r in enumerate(o):
        events.append((r["t0"], 1, j, 0))
        for k in range(1, len(r["ut"])):
            events.append((max(r["ut"][k], r["t0"]), 1, j, k))
        events.append((r["t1"], 0 if r["t1"] > r["t0"] else 2, j, -1))
    events.sort(key=lambda e: (e[0], e[1]))
    state, open_n, eq = {}, 0, 1.0
    pts, log = [], []
    for t, kind, j, k in events:
        r = o[j]
        if kind in (0, 2):
            s = state.pop(j, None)
            if s is None:
                continue
            open_n -= 1
            pnl = s["dpr"] * sum(r["uR"][kk] for kk in s["units"])
            log.append(dict(t=t, eq_before=eq, pnl=pnl, side=r["side"], rule=r["rule"], coin=r["coin"],
                            n_units=len(s["units"]), R_taken=float(sum(r["uR"][kk] for kk in s["units"])),
                            R_first=float(r["uR"][0]), dpr=s["dpr"], t0=r["t0"], small=s["small"]))
            eq = max(eq + pnl, 0.0)
            pts.append((t, eq))
            continue
        if k == 0:
            if open_n >= 12:
                continue
            ib = bear_v[max(np.searchsorted(bear_ns, t, side="right") - 1, 0)]
            f = blend.RISK / 100.0 * (blend.REGIME_MULT if ib else 1.0)
            s = dict(dpr=f * eq, units=[], small=bool(ib))
        else:
            s = state.get(j)
            if s is None:
                continue
        notional = s["dpr"] * r["ue"][k] / r["risk"]
        gross = sum(st["dpr"] * o[jj]["ue"][kk] / o[jj]["risk"] for jj, st in state.items() for kk in st["units"])
        if gross + notional > lev * eq:
            continue
        s["units"].append(k)
        if k == 0:
            state[j] = s; open_n += 1
    c = pd.Series([p[1] for p in pts], index=pd.to_datetime([p[0] for p in pts]))
    L = pd.DataFrame(log)
    L["t"] = pd.to_datetime(L.t); L["t0"] = pd.to_datetime(L.t0)
    return c, L


def worst_falls(c, n=3, min_gap_days=60):
    """The n largest peak-to-trough falls that do not overlap."""
    d = c.resample("D").last().ffill()
    out, used = [], []
    peak = d.cummax()
    dd = 1 - d / peak
    for _ in range(n):
        cand = dd.copy()
        for a, b in used:
            cand[(cand.index >= a) & (cand.index <= b)] = 0
        if cand.max() <= 0:
            break
        tr = cand.idxmax()
        pk = d[:tr].idxmax() if not used else d[:tr][d[:tr].index > max([b for a, b in used if b < tr], default=d.index[0])].idxmax()
        rec = d[(d.index > tr) & (d >= d[pk])]
        rec_t = rec.index[0] if len(rec) else d.index[-1]
        out.append((pk, tr, rec_t, float(1 - d[tr] / d[pk])))
        used.append((pk, rec_t))
    return out


def main():
    C, F, first = load_panel()
    C.index = C.index.astype("datetime64[ns]")
    reg = btc_regime(C).reindex(C.index)
    btc = C["BTCUSDT"]
    bear = regimes()[1000]
    bear_ns = pd.DatetimeIndex(bear.index).as_unit("ns").asi8
    bear_v = bear.to_numpy(bool)
    rows = build_meta()

    # the breadth sleeve, frictionless top-10 (doc 13), for "what did it do in those days"
    from backtest.breadth_attack import ls_signal
    from backtest.breadth_robust import basket, breadth_n, run
    from backtest.carry_check import exact_funding
    from backtest.market_neutral import drop_non_crypto
    from backtest.regime_signals import member_mask
    from backtest.wide_book import eligibility
    Fx = exact_funding(C.index, C.columns)
    X = C.to_numpy(float)
    m60 = member_mask(C, first, drop_non_crypto(eligibility(60))) & np.isfinite(X)
    sig = ls_signal(breadth_n(C, m60, 20), reg == "bear")
    sleeve, _ = run(sig, basket(C, Fx, first, 10))

    print("THE LARGEST FALLS OF THE TRIPLE BOOK (realised equity, 10x guard, entry-sized)\n")
    print("1. WHERE, across the 10 orderings (peak -> bottom, depth)")
    allf = []
    for sd in SEEDS:
        c, L = simulate_log(rows, bear_ns, bear_v, sd)
        f = worst_falls(c, 3)
        allf.append((sd, c, L, f))
        print(f"   ordering {sd}: " + " | ".join(f"{a:%Y-%m-%d} -> {b:%Y-%m-%d} -{x*100:.0f}% (back {r:%Y-%m})"
                                                for a, b, r, x in f))

    # take ordering 0's three falls apart; the others are printed above for consistency
    sd, c, L, falls = allf[0]
    for i, (pk, tr, rec, depth) in enumerate(falls, 1):
        w = L[(L.t > pk) & (L.t <= tr)].copy()
        eq_pk = float(c[c.index <= pk].iloc[-1])
        w["pct_peak"] = w.pnl / eq_pk * 100                  # each close as % of PEAK equity
        days = (tr - pk).days
        rg = reg[(reg.index > pk) & (reg.index <= tr)].value_counts()
        b0, b1 = btc.asof(pk), btc.asof(tr)
        print(f"\n2.{i} FALL {i}: {pk:%Y-%m-%d} -> {tr:%Y-%m-%d}, {days} days, -{depth*100:.0f}% "
              f"(back to the peak {rec:%Y-%m-%d})")
        print(f"   BTC {b0:,.0f} -> {b1:,.0f} ({(b1/b0-1)*100:+.0f}%). Days: "
              + ", ".join(f"{k} {int(v)}" for k, v in rg.items()))
        run_up = c[(c.index > pk - pd.Timedelta(days=120)) & (c.index <= pk)]
        if len(run_up) > 1:
            print(f"   the 120 days BEFORE the peak: equity x{run_up.iloc[-1]/run_up.iloc[0]:.2f}")
        tot = w.pct_peak.sum()
        print(f"   {len(w)} positions closed, net {tot:+.1f}% of peak equity "
              f"(losers {w[w.pnl < 0].pct_peak.sum():+.1f}%, winners {w[w.pnl > 0].pct_peak.sum():+.1f}%)")
        print("   by side / timeframe (% of peak equity, positions, share that lost):")
        for (sd_, ru), g in w.groupby(["side", "rule"]):
            print(f"     {sd_:<5} {ru:<4} {g.pct_peak.sum():+7.1f}%   {len(g):>4} positions   {(g.pnl < 0).mean()*100:3.0f}% lost")
        full = w[w.R_first <= -0.9]; small = w[(w.pnl < 0) & (w.R_first > -0.9)]
        print(f"   full stop-outs (first unit <= -0.9R): {len(full)} positions, {full.pct_peak.sum():+.1f}% "
              f"| smaller losses: {len(small)}, {small.pct_peak.sum():+.1f}%")
        multi = w[w.n_units >= 3]
        print(f"   positions that had pyramided (3+ units): {len(multi)}, net {multi.pct_peak.sum():+.1f}% "
              f"(these are profit given back or adds stopped out)")
        print(f"   positions opened at the reduced x0.25 size (BTC below its 1000h average): "
              f"{int(w.small.sum())} of {len(w)}")
        # how big each bet was relative to the equity it ended up losing from
        print(f"   typical risk per position at entry: {w.dpr.median()/eq_pk*100:.2f}% of peak equity "
              f"(0.30% of equity at entry)")
        worst = w.nsmallest(5, "pnl")[["t0", "t", "side", "rule", "coin", "n_units", "R_taken", "pct_peak"]]
        print("   the five biggest single losses:")
        for _, r in worst.iterrows():
            print(f"     {r.t0:%Y-%m-%d} -> {r.t:%Y-%m-%d} {r.side:<5} {r.rule:<4} {r.coin:<9} {r.n_units} unit(s) "
                  f"{r.R_taken:+6.1f}R  {r.pct_peak:+5.1f}% of peak")
        sl = sleeve[(sleeve.index > pk) & (sleeve.index <= tr)]
        print(f"   the breadth sleeve over the same days: {((1 + sl).prod() - 1)*100:+.1f}%, "
              f"active on {(sig[(sig.index > pk) & (sig.index <= tr)] != 0).sum()} signal days")

    # 3. all falls, all orderings: what share of the losses is longs vs shorts, and chop
    print("\n3. ACROSS EVERY ORDERING'S WORST FALL")
    agg = []
    for sd, c, L, falls in allf:
        pk, tr, rec, depth = falls[0]
        w = L[(L.t > pk) & (L.t <= tr)]
        eq_pk = float(c[c.index <= pk].iloc[-1])
        lo = w[w.pnl < 0]
        rgw = reg[(reg.index > pk) & (reg.index <= tr)]
        agg.append(dict(depth=depth * 100, days=(tr - pk).days,
                        long_loss=lo[lo.side == "long"].pnl.sum() / eq_pk * 100,
                        short_loss=lo[lo.side == "short"].pnl.sum() / eq_pk * 100,
                        win=w[w.pnl > 0].pnl.sum() / eq_pk * 100,
                        full_stop=lo[lo.R_first <= -0.9].pnl.sum() / lo.pnl.sum() * 100 if len(lo) else np.nan,
                        chop=(rgw == "chop").mean() * 100, bear=(rgw == "bear").mean() * 100,
                        bull=(rgw == "bull").mean() * 100))
    A = pd.DataFrame(agg)
    print(f"   depth {A.depth.mean():.0f}% over {A.days.mean():.0f} days on average")
    print(f"   losses from longs {A.long_loss.mean():+.1f}% and shorts {A.short_loss.mean():+.1f}% of peak equity; "
          f"winners gave back {A.win.mean():+.1f}%")
    print(f"   {A.full_stop.mean():.0f}% of the losing dollars were full stop-outs")
    print(f"   days in the fall: chop {A.chop.mean():.0f}%, bear {A.bear.mean():.0f}%, bull {A.bull.mean():.0f}%")


if __name__ == "__main__":
    main()
