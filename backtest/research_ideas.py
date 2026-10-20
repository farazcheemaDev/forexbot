"""WHAT THE OUTSIDE WORLD SUGGESTS, TESTED ON OUR DATA (2026-10-20)

The user: "search the web / do extensive research on what algorithmic traders and repos do, and what we can include in
our bots". Read: Zarattini, Pagani & Barbon, "Catching Crypto Trends" (SSRN 5209907, 2025; ~30%/yr, Sharpe ~1.58 net,
top-20 rotation 2015-2025 - but a public GitHub replication reports 0 passes); Grobys et al. 2025, "Cryptocurrency
momentum has (not) its moments" (volatility management softens crypto momentum crashes, large caps); Barroso & Santa-Clara
2015; Quantpedia's Bitcoin hour-of-day study (21:00-23:00 UTC strongest, Gemini 2015-2022). Already dead HERE and not
re-run: volatility targeting of the trend book and of the machine (doc 02 s4, machine_combos.py), single Donchian
20 / 55 entries for the daily book (daily_families.py).

A  THE DONCHIAN ENSEMBLE, AS PUBLISHED (rules from the paper's summaries; fixed, not tuned here)
   per coin, for each lookback L in 5 10 20 30 60 90 150 250 360: enter when the close beats the highest of the prior L
   closes; a trailing stop = max(yesterday's stop, the midpoint of the L-day highest and lowest close); out on a close
   under it. A coin's signal = the share of the 9 models in. Weight = signal x min(25% / its 90-day annualised vol, 2) / N,
   gross capped at 2x; long only; rebalanced daily (decided at the close, filled at the next open - crypto has no gap);
   12bp round trip on turnover; funding on the long exposure. Universe: point-in-time top-20 (and top-40) perps by the
   prior month's volume, dead coins in.
   judged alone (both halves) and inside the 9-book machine: REPLACING the daily book (x0.5) and ADDED to it (x0.5).
B  VOLATILITY-MANAGED MARKET-NEUTRAL BOOK
   each week's MN result x k, k = min(target / the std of its previous 26 weekly results, CAP), target = the median of
   that std over all earlier weeks (causal); CAP 1.0 (only ever smaller) and 2.0 (Barroso-style, can lever up).
C  BITCOIN'S EVENING HOURS: long BTC from the 21:00 UTC open to the 23:00 UTC open, every day; 12bp a round trip.

REGISTERED BEFORE THE RUN (2026-10-20)
    E1 the ensemble (top-20) is positive on both halves alone, but below the deployed daily book's CAGR on the holdout.
    E2 replacing the daily book with it does NOT beat the machine on both halves.
    E3 adding it (x0.5) raises the machine's typical year on at most one half.
    V1 vol-managed MN (cap 1.0) improves the MN book's worst week by >= 3 points and costs the machine < 5% of its typical
       year on both halves (a risk control, not a return lever).
    S1 the BTC evening trade loses after fees on both halves (the effect is a few bp; the fee is 12).

RESULT (2026-10-20, logs/research_ideas.txt) - nothing from outside beats the machine. E1 / E2 / E3 / S1 RIGHT, V1 WRONG.
    A  the published Donchian ensemble on our PIT data: +5.4% / +1.7% a year (tune / holdout), Sharpe 0.85 / 0.38
       (top-20; top-40 0.82 / 0.06) against the deployed daily book's 1.56 / 1.05 - far below the paper's ~30%, Sharpe 1.58
       on 2015-2025 (the 2017 mania is in theirs, not ours; a public GitHub replication also found 0 passes). Its weight
       here is signal x vol-target / N (gross ~25% when all 20 are long), so its CAGR is small by construction - the
       Sharpe, which does not depend on that scale, is the comparison. Replacing the daily book halves the holdout's
       typical year ($9,416 -> $4,725); adding it moves nothing (+0.7% / -1%).
    B  vol-managed MN: cap 1.0 costs -0.8% / -19% of the typical year for a worst week 2 points better (-21.1 -> -19.0);
       cap 2.0 +10% tune / -16% holdout, falls deeper - it flips. Dead, as the trend book's vol targeting (doc 02 s4).
    C  BTC long 21:00 -> 23:00 UTC: +8.3bp / +5.1bp a day gross - the pattern is there - and -3.7 / -6.9bp after 12bp.

    python -m backtest.research_ideas
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

LOG = ROOT / "logs" / "research_ideas.txt"
LBS = (5, 10, 20, 30, 60, 90, 150, 250, 360)
TV, CAP_COIN, CAP_GROSS, FEE_SIDE = 0.25, 2.0, 2.0, 6e-4
CUT = pd.Timestamp("2024-08-29")


# ------------------------------------------------------------------ A. the Donchian ensemble

def ensemble(top_n: int) -> pd.Series:
    from backtest import daily_combos as dc
    from backtest.market_neutral import drop_non_crypto
    from backtest.wide_book import eligibility
    PN = dc.panel(0)
    elig = drop_non_crypto(eligibility(top_n))
    days = sorted(set().union(*[set(pd.DatetimeIndex(P["t"])) for P in PN.values()]))
    idx = pd.DatetimeIndex(days)
    W = pd.DataFrame(0.0, index=idx, columns=list(PN))          # weight decided at the close of day t
    R = pd.DataFrame(0.0, index=idx, columns=list(PN))          # return of day t (close t-1 -> close t)
    FU = pd.DataFrame(0.0, index=idx, columns=list(PN))         # funding paid by a long over day t
    for s, P in PN.items():
        t = pd.DatetimeIndex(P["t"])
        c = pd.Series(P["c"], index=t)
        ym = t.strftime("%Y-%m")
        ok = np.array([m in elig.get(s, ()) for m in ym])
        if not ok.any():
            continue
        r = c.pct_change().fillna(0.0)
        vol = r.rolling(90).std() * np.sqrt(365)
        fc = pd.Series(P["fc"], index=t)
        fund = (fc.diff() / c.shift(1)).fillna(0.0)
        cv = c.to_numpy()
        sig = np.zeros(len(c))
        for L in LBS:
            hi = c.shift(1).rolling(L).max().to_numpy()
            mx, mn = c.rolling(L).max().to_numpy(), c.rolling(L).min().to_numpy()
            inpos, stop = False, -np.inf
            pos = np.zeros(len(c))
            for i in range(len(c)):
                if not np.isfinite(hi[i]):
                    continue
                if inpos:
                    stop = max(stop, (mx[i] + mn[i]) / 2)
                    if cv[i] < stop:
                        inpos = False
                elif cv[i] > hi[i]:
                    inpos, stop = True, (mx[i] + mn[i]) / 2
                pos[i] = 1.0 if inpos else 0.0
            sig += pos / len(LBS)
        w = sig * np.minimum(TV / vol.to_numpy(), CAP_COIN) / top_n
        w = np.where(ok & np.isfinite(w), w, 0.0)
        W.loc[t, s] = w
        R.loc[t, s] = r.to_numpy()
        FU.loc[t, s] = fund.to_numpy()
    g = W.sum(axis=1)
    W = W.mul(np.minimum(1.0, CAP_GROSS / g.replace(0, np.nan)).fillna(1.0), axis=0)
    held = W.shift(1).fillna(0.0)                               # decided at yesterday's close, held over today
    turn = W.diff().abs().sum(axis=1).fillna(W.abs().sum(axis=1))
    ret = (held * R).sum(axis=1) - (held * FU).sum(axis=1) - turn.shift(1).fillna(0.0) * FEE_SIDE
    ret.index = ret.index + pd.Timedelta(days=1)                # booked at the day's end, as the machine's calendar
    return ret


def stats(r: pd.Series):
    r = r[r.index >= r.ne(0).idxmax()]
    out = {}
    for h, x in (("tune", r[r.index < CUT]), ("holdout", r[r.index >= CUT])):
        c = (1 + x).cumprod()
        yrs = max(len(x) / 365.0, 0.25)
        out[h] = (c.iloc[-1] ** (1 / yrs) - 1, float((1 - c / c.cummax()).max()),
                  x.mean() / x.std() * np.sqrt(365) if x.std() else np.nan)
    return out


# ------------------------------------------------------------------ B. volatility-managed MN

def vol_managed(s: pd.Series, cap: float, n: int = 26) -> pd.Series:
    """s = the MN book's weekly results (booked at each week's end, zeros elsewhere)."""
    wk = s[s != 0]
    sd = wk.rolling(n).std().shift(1)                           # the previous n weeks only
    tgt = sd.expanding().median()
    k = (tgt / sd).clip(upper=cap).fillna(1.0)
    out = s.copy()
    out.loc[wk.index] = wk * k
    return out


# ------------------------------------------------------------------ C. BTC's evening hours

def evening() -> tuple:
    from backtest.capitulation_wide import hourly
    h = hourly("BTCUSDT").copy()
    h["time"] = pd.to_datetime(h.time)
    h = h.set_index("time")
    o = h.open
    a = o[o.index.hour == 21]
    b = o[o.index.hour == 23]
    a.index, b.index = a.index.normalize(), b.index.normalize()
    r = (b / a - 1).dropna() - 2 * FEE_SIDE
    gross = (b / a - 1).dropna()
    res = {}
    for hname, x, gx in (("tune", r[r.index < CUT], gross[gross.index < CUT]), ("holdout", r[r.index >= CUT], gross[gross.index >= CUT])):
        res[hname] = (gx.mean(), x.mean(), x.mean() / x.std() * np.sqrt(len(x)), len(x))
    fri = gross[gross.index.dayofweek == 4]
    return res, fri.mean(), len(fri)


def main():
    from backtest import machine_combos as mc
    from backtest.all_books import BOOKS, machine_books, ndx_dip, news_book
    from backtest.machine import summary
    from backtest.profit_take import mn_series, mn_weeks, score_mats
    lines = [f"backtest/research_ideas.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC", ""]
    ens = {n: ensemble(n) for n in (20, 40)}
    M = machine_books()
    nw, nd = news_book(), ndx_dip()
    RUN = [b for b in BOOKS if b != "bids"]

    def machine(extra=None, replace=None):
        out = []
        for x in M:
            y = x[RUN].copy()
            if replace is not None:
                y[replace[0]] = replace[1].reindex(x.index).fillna(0.0) if isinstance(replace[1], pd.Series) \
                    else replace[1][len(out)].reindex(x.index).fillna(0.0)
            tot = y.sum(axis=1) + nw.reindex(x.index).fillna(0.0) + nd.reindex(x.index).fillna(0.0)
            if extra is not None:
                tot = tot + extra.reindex(x.index).fillna(0.0)
            out.append(tot)
        return out

    def row(name, daily):
        st, sh = summary([x[x.index < CUT] for x in daily]), summary(daily, CUT)
        return (st, sh), (f"   {name:<40}${st['typ']:>7,.0f} ${sh['typ']:>7,.0f}{st['dd']:>5.0f}/{sh['dd']:<3.0f}"
                          f"{st['wm']:>+5.0f}/{sh['wm']:<+4.0f}")

    hdr = f"   {'machine ($300, 12 months)':<40}{'tune':>8}{'holdout':>9}{'fall':>9}{'worst mo':>10}"
    lines += ["A. THE DONCHIAN ENSEMBLE (alone, 1x of its own sizing)",
              f"   {'universe':<10}{'tune CAGR':>11}{'fall':>6}{'Sharpe':>7}{'hold CAGR':>11}{'fall':>6}{'Sharpe':>7}"]
    for n, r in ens.items():
        s = stats(r)
        lines.append(f"   top-{n:<6}{s['tune'][0] * 100:>+10.1f}%{s['tune'][1] * 100:>5.0f}%{s['tune'][2]:>7.2f}"
                     f"{s['holdout'][0] * 100:>+10.1f}%{s['holdout'][1] * 100:>5.0f}%{s['holdout'][2]:>7.2f}")
    dref = [x["daily"] / 0.5 for x in M]                                     # the deployed daily book at 1x, ordering by ordering
    dstat = [stats(d) for d in dref]
    lines.append(f"   deployed daily book at 1x (median of orderings): tune {np.median([d['tune'][0] for d in dstat]) * 100:+.1f}%, "
                 f"holdout {np.median([d['holdout'][0] for d in dstat]) * 100:+.1f}%, Sharpe "
                 f"{np.median([d['tune'][2] for d in dstat]):.2f} / {np.median([d['holdout'][2] for d in dstat]):.2f}")
    lines += ["", hdr]
    base, txt = row("deployed machine", machine())
    lines.append(txt)
    RA = {}
    for n in (20, 40):
        RA[("rep", n)], txt = row(f"daily book REPLACED by ensemble top-{n} x0.5", machine(replace=("daily", 0.5 * ens[n])))
        lines.append(txt)
        RA[("add", n)], txt = row(f"ensemble top-{n} x0.5 ADDED", machine(extra=0.5 * ens[n]))
        lines.append(txt)
    print("\n".join(lines), flush=True)

    lines += ["", "B. VOLATILITY-MANAGED MARKET-NEUTRAL BOOK", hdr + f"{'MN worst wk':>13}{'MN CAGR t/h':>15}"]
    mom, rsi = score_mats()
    W = {o: (mn_weeks(mom, o), mn_weeks(rsi, o)) for o in sorted({sd % 7 for sd in mc.SEEDS})}
    RB = {}
    for name, cap in (("MN as deployed", None), ("vol-managed, cap 1.0 (only smaller)", 1.0), ("vol-managed, cap 2.0", 2.0)):
        ser = []
        for sd, x in zip(mc.SEEDS, M):
            s, _ = mn_series(*W[sd % 7], None)
            s = s.reindex(x.index).fillna(0.0)
            ser.append(s if cap is None else vol_managed(s, cap))
        RB[name], txt = row(name, machine(replace=("mn_blend", ser)))
        ws = np.median([s[s != 0].min() for s in ser])
        bs = [stats(s) for s in ser]
        lines.append(txt + f"{ws * 100:>+11.1f}%{np.median([b['tune'][0] for b in bs]) * 100:>+8.0f}%/"
                           f"{np.median([b['holdout'][0] for b in bs]) * 100:<+5.0f}%")
    print("\n".join(lines[-4:]), flush=True)

    res, fri, nfri = evening()
    lines += ["", "C. BITCOIN'S EVENING HOURS (long 21:00 -> 23:00 UTC open, every day)"]
    for h, (g, net, t, n) in res.items():
        lines.append(f"   {h:<8} gross {g * 1e4:+.1f}bp, net {net * 1e4:+.1f}bp a day (t {t:+.1f}, {n} days)")
    lines.append(f"   Fridays only, gross {fri * 1e4:+.1f}bp ({nfri} days)")

    e20 = stats(ens[20])
    d_hold = np.median([d["holdout"][0] for d in dstat])
    e1 = e20["tune"][0] > 0 and e20["holdout"][0] > 0 and e20["holdout"][0] < d_hold
    e2 = not any(all(RA[("rep", n)][h]["typ"] > base[h]["typ"] for h in (0, 1)) for n in (20, 40))
    e3 = all(sum(RA[("add", n)][h]["typ"] > base[h]["typ"] for h in (0, 1)) <= 1 for n in (20, 40))
    dep = RB["MN as deployed"]
    v1 = RB["vol-managed, cap 1.0 (only smaller)"]
    s1 = all(res[h][1] < 0 for h in res)
    lines += ["", "REGISTERED PREDICTIONS",
              f"  E1 ensemble top-20 positive both halves, below the daily book's holdout ({d_hold * 100:+.0f}%): "
              f"{e20['tune'][0] * 100:+.0f}% / {e20['holdout'][0] * 100:+.0f}% -> {'RIGHT' if e1 else 'WRONG'}",
              f"  E2 replacing the daily book does not beat the machine on both halves -> {'RIGHT' if e2 else 'WRONG'}",
              f"  E3 adding it raises the typical year on at most one half -> {'RIGHT' if e3 else 'WRONG'}",
              f"  V1 vol-managed MN (cap 1): machine typical year {v1[0]['typ'] / dep[0]['typ'] - 1:+.1%} / "
              f"{v1[1]['typ'] / dep[1]['typ'] - 1:+.1%} (> -5% both) - see the MN worst week above",
              f"  S1 BTC evening trade loses after fees on both halves -> {'RIGHT' if s1 else 'WRONG'}"]
    txt = "\n".join(lines)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
