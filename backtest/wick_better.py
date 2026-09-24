"""MAKING THE WICK BIDS BETTER (doc 15 follow-up): which rule for WHERE, ON WHAT and WHEN NOT.

Doc 15's book (crash_buy_check.honest): a resting buy 10% under the previous hour's close on each
PIT top-20 perp, 1/20 of equity each, sold at the fill hour's close; with 8bp fees and 30bp of extra
exit slippage it made +30.8%/yr, and added to the final version it made the worst month WORSE
(-29% -> -36%). Asked 2026-09-24: "go deeper, make this better, reduce the worst month".

Everything here is on $300 with Bitget's $5 order minimum, 8bp + 30bp per fill, dead coins included.
A. UNIVERSE      top-20 / 30 / 40 / 60, each bid 1/N of equity.
B. DISTANCE      fixed 6 / 8 / 10 / 12 / 15%, or scaled to each coin's own hourly volatility:
                 z x sigma (sigma = std of 1h log returns over the trailing 30 days, known at the
                 previous close), z = 6 / 8 / 10 / 12, clipped to 4-30%.
C. LADDER        two bids per coin (8% + 14%, 6% + 12%), half the size each.
D. REFERENCE     bid under the highest of the last 3 closes (a slide that spans hours) instead of
                 the last close; never nearer than 3% under the last close.
E. FILTERS       all causal: no second fill on a coin within 24h of its last (LUNA filled five
                 times); skip a coin already down more than 15% / 25% over the previous 24h; skip
                 days the BTC label calls BEAR.
F. EXIT          the fill hour's close (baseline) or the next hour's close.
G. SIZE          1 / 1.5 / 2 x the 1/N bid (more exposure in the same hours).
H. DIAGNOSTICS   per fill, what separates the losers: regime, the coin's prior 24h, first vs repeat
                 fill, and how many coins filled in the same hour (the last is known only AFTER the
                 fill, so it is description, not a rule).

The verdict rule, registered with the predictions: a change counts only if it beats the baseline
(top-20, 10%, fill-hour close) on BOTH halves (tune < 2024-08-29 <= holdout) in growth without a
worse worst month, or improves the worst month on both halves without costing growth on either.

REGISTERED PREDICTION (2026-09-24, before running):
  A. top-40 beats top-20 on both halves (more, smaller, less correlated bids; doc 15 already showed
     N40 +40.1% / DD 13% vs N20 +37.5% / DD 22% without slippage); top-60 no better than 40.
  B. volatility-scaled distance adds fills on BTC/ETH and is within +-20% of fixed 10%: no pass.
     6-8% fixed has more fills and a lower return per fill; net lower after 30bp slippage.
  C. the ladder ties the single bid.
  D. the multi-hour reference is WORSE (a slide is continuation, not a forced-seller wick).
  E. no-repeat improves the worst month and costs little; the prior-24h filter improves the worst
     month; skipping bear days costs growth (bear wicks bounce too) and helps the worst month.
  F. the next-hour exit is worse than the fill-hour close.
  G. size scales growth and the worst month roughly in proportion: not an improvement, a dial.
  H. losers are concentrated in coins already down >25% over 24h and in repeat fills.

I. COMBINATIONS (python -m backtest.wick_better --combos), added AFTER A-H were read, so post-hoc:
   judged against the doc 15 book simply sized up or down to the same worst month, on both halves.
   REGISTERED before running I: skipping BEAR days and top-40 each pass on their own; top-40 + skip
   BEAR passes and is the best single rule; stacking a second filter on it adds little (both remove
   the same LUNA-type fills); at x2 it makes +50-70%/yr tune and +20-30% holdout with a worst month
   near the doc 15 book's -22%. The post-hoc pump filter (skip coins up >50% in 24h) is listed so
   it can be seen, not adopted: it was picked from the worst-fills list of the same data.

    python -m backtest.wick_better
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.crash_buy import CUT, PEN, load_1h  # noqa: E402
from backtest.market_neutral import btc_regime, drop_non_crypto, load_panel  # noqa: E402
from backtest.wide_book import MIN_AGE_D, eligibility  # noqa: E402

CAP = 300.0
MIN_ORDER = 5.0
FEE = 8e-4
EXTRA = 0.003
KMIN = 0.04
HOUR = np.timedelta64(1, "h")
NS = (20, 30, 40, 60)
CACHE = Path(__file__).resolve().parents[1] / "strategy_analysis" / "data" / "wick_candidates.pkl"


def candidates(sym, d, months, first):
    """Every hour whose low went at least KMIN under the highest of the last three closes -
    a superset of every rule's fills - with what each rule needs, all known at the previous close."""
    o, h, l, c = (d[x].to_numpy(float) for x in ("open", "high", "low", "close"))
    t = d["time"].to_numpy()
    n = len(c)
    lc = np.log(c)
    sig = pd.Series(np.r_[np.nan, np.diff(lc)]).rolling(720, min_periods=240).std().shift(1).to_numpy()
    prev = np.r_[np.nan, c[:-1]]
    max3 = pd.Series(c).rolling(3).max().shift(1).to_numpy()
    ret24 = np.r_[np.full(25, np.nan), c[24:-1] / c[:-25] - 1] if n > 25 else np.full(n, np.nan)
    nxt = np.r_[c[1:], np.nan]
    gap_ok = np.r_[False, np.diff(t) == HOUR]
    nxt_ok = np.r_[np.diff(t) == HOUR, False]
    mon = pd.DatetimeIndex(t).strftime("%Y-%m").to_numpy()
    age = (pd.DatetimeIndex(t) - first).days.to_numpy() >= MIN_AGE_D
    ok = gap_ok & age & np.isfinite(max3) & (l < max3 * (1 - KMIN) * (1 - PEN))
    ok &= np.array([m in months for m in mon])
    i = np.flatnonzero(ok)
    return pd.DataFrame(dict(sym=sym, t=pd.DatetimeIndex(t[i]), month=mon[i], prev=prev[i], max3=max3[i],
                             open=o[i], low=l[i], close=c[i], nxt=np.where(nxt_ok[i], nxt[i], c[i]),
                             sig=sig[i], ret24=ret24[i]))


def fills(X, k=0.10, z=None, ladder=None, ref="prev", no_repeat=False, max_drop24=None, skip_bear=None,
          exit="close", max_rise24=None):
    """The fills one rule produces on candidate set X: columns t, sym, w (share of the 1/N bid), ret."""
    levels = ladder or [(k, 1.0)]
    out = []
    for kk, w in levels:
        dist = np.clip(z * X.sig.to_numpy(), KMIN, 0.30) if z else np.full(len(X), kk)
        if ref == "prev":
            lvl = X.prev.to_numpy() * (1 - dist)
        else:
            lvl = np.minimum(X.max3.to_numpy() * (1 - dist), X.prev.to_numpy() * (1 - 0.03))
        hit = X.low.to_numpy() < lvl * (1 - PEN)
        if z:
            hit &= np.isfinite(X.sig.to_numpy())
        fill = np.minimum(lvl, X.open.to_numpy())
        px = X["close" if exit == "close" else "nxt"].to_numpy()
        y = X[hit].copy()
        y["w"] = w
        y["ret"] = px[hit] / fill[hit] - 1
        out.append(y)
    Y = pd.concat(out).sort_values(["t", "sym"], kind="stable")
    if max_drop24 is not None:
        Y = Y[~(Y.ret24 < -max_drop24)]
    if max_rise24 is not None:
        Y = Y[~(Y.ret24 > max_rise24)]
    if skip_bear is not None:
        Y = Y[~Y.t.dt.normalize().map(skip_bear).fillna(False).astype(bool).to_numpy()]
    if no_repeat:
        keep = []
        for _, g in Y.groupby("sym", sort=False):
            last = None
            for idx, tt in zip(g.index, g.t):
                if last is None or tt - last >= pd.Timedelta(hours=24) or tt == last:
                    keep.append(idx)
                    last = tt
        Y = Y.loc[sorted(set(keep))] if keep else Y.iloc[:0]
        Y = Y.sort_values(["t", "sym"], kind="stable")
    return Y


def book(Y, n, mult=1.0, cap=CAP):
    """$ equity, entry-sized: each fill w x mult / n of equity at its hour, under $5 skipped.
    P&L booked at the exit (the same or next hour). Returns (daily curve, share of fills skipped)."""
    eq, pts, skipped, total = cap, [], 0, 0
    for t, g in Y.groupby("t", sort=True):
        amt = eq * mult / n * g.w.to_numpy()
        total += len(g)
        ok = amt >= MIN_ORDER
        skipped += int((~ok).sum())
        eq = max(eq + float((amt[ok] * (g.ret.to_numpy()[ok] - FEE - EXTRA)).sum()), 0.0)
        pts.append((t, eq))
    s = pd.Series([p[1] for p in pts], index=pd.DatetimeIndex([p[0] for p in pts]))
    s = s[~s.index.duplicated(keep="last")]
    grid = pd.date_range("2020-01-01", "2026-09-21", freq="D")
    c = s.resample("D").last().reindex(grid).ffill().fillna(cap)
    return c, skipped / max(total, 1)


def stats(c):
    def g(z):
        y = (z.index[-1] - z.index[0]).days / 365.25
        return ((z.iloc[-1] / z.iloc[0]) ** (1 / y) - 1) * 100
    me = c.resample("ME").last()
    m = me.pct_change().dropna()
    tu, ho = c[c.index < CUT], c[c.index >= CUT]
    mt, mh = m[m.index < CUT], m[m.index >= CUT]
    return dict(cagr=g(c), tune=g(tu), hold=g(ho), wm_t=mt.min() * 100, wm_h=mh.min() * 100,
                wd=c.pct_change().min() * 100, dd=(1 - c / c.cummax()).max() * 100)


def line(name, Y, n, mult=1.0):
    c, sk = book(Y, n, mult)
    s = stats(c)
    yrs = (pd.Timestamp("2026-09-21") - pd.Timestamp("2020-01-01")).days / 365.25
    print(f"  {name:<44}{len(Y)/yrs:>7.0f}{s['cagr']:>+8.1f}%{s['tune']:>+8.1f}%{s['hold']:>+8.1f}%"
          f"{s['wm_t']:>+9.1f}%{s['wm_h']:>+8.1f}%{s['wd']:>+8.1f}%{s['dd']:>6.0f}%{sk*100:>6.0f}%")
    return s


HEAD = (f"  {'rule':<44}{'fills/yr':>7}{'CAGR':>9}{'TUNE':>9}{'HOLD':>9}{'worst mo':>10}{'(hold)':>9}"
        f"{'worst d':>9}{'DD':>7}{'<$5':>7}")


def load_all():
    """Candidate hours for the PIT top-60 (cached), and the daily BTC regime label."""
    if CACHE.exists():
        X = pd.read_pickle(CACHE)
    else:
        el = {n: drop_non_crypto(eligibility(n)) for n in NS}
        top = el[max(NS)]
        parts = []
        for s in sorted(x for x, ms in top.items() if ms):
            d = load_1h(s)
            if d is not None:
                parts.append(candidates(s, d, top[s], d.time.iloc[0]))
        X = pd.concat(parts, ignore_index=True)
        for n in NS:
            X[f"in{n}"] = [m in el[n].get(s, ()) for s, m in zip(X.sym, X.month)]
        X.to_pickle(CACHE)
    C, _, _ = load_panel()
    C.index = C.index.astype("datetime64[ns]")
    reg = btc_regime(C)
    reg.index = pd.DatetimeIndex(reg.index).normalize()
    return X, reg, (reg == "bear")


def main():
    X, reg, bear_day = load_all()
    print(f"{X.sym.nunique()} coins ever in the PIT top-{max(NS)} (dead included); {len(X)} candidate hours\n")
    print("$300, 8bp fees + 30bp exit slippage, $5 minimum. TUNE < 2024-08-29 <= HOLD. worst mo = worst calendar month.")

    X20 = X[X.in20]
    base = fills(X20)
    print("\nA. UNIVERSE (10% under the last close, sold at the fill hour's close)")
    print(HEAD)
    res = {}
    for n in NS:
        res[f"A{n}"] = line(f"top-{n}, 1/{n} each", fills(X[X[f"in{n}"]]), n)

    print("\nB. DISTANCE (top-20)")
    print(HEAD)
    for k in (0.06, 0.08, 0.10, 0.12, 0.15):
        res[f"Bk{k}"] = line(f"fixed {k*100:.0f}%", fills(X20, k=k), 20)
    for z in (6, 8, 10, 12):
        res[f"Bz{z}"] = line(f"{z} x the coin's hourly volatility (4-30%)", fills(X20, z=z), 20)

    print("\nC. LADDER (top-20, two bids per coin at half size each)")
    print(HEAD)
    for lad in ([(0.08, 0.5), (0.14, 0.5)], [(0.06, 0.5), (0.12, 0.5)], [(0.10, 0.5), (0.20, 1.0)]):
        res["C" + str(lad)] = line(" + ".join(f"{k*100:.0f}% x{w}" for k, w in lad), fills(X20, ladder=lad), 20)

    print("\nD. REFERENCE (top-20, 10%)")
    print(HEAD)
    line("under the last close (baseline)", base, 20)
    res["D"] = line("under the highest of the last 3 closes", fills(X20, ref="max3"), 20)

    print("\nE. FILTERS (top-20, 10%)")
    print(HEAD)
    line("none (baseline)", base, 20)
    res["Enr"] = line("no second fill on a coin within 24h", fills(X20, no_repeat=True), 20)
    for x in (0.15, 0.25):
        res[f"Ed{x}"] = line(f"skip a coin already down >{x*100:.0f}% over 24h", fills(X20, max_drop24=x), 20)
    res["Eb"] = line("skip BEAR days", fills(X20, skip_bear=bear_day), 20)
    res["Enr40"] = line("top-40 + no second fill within 24h", fills(X[X.in40], no_repeat=True), 40)

    print("\nF. EXIT (top-20, 10%)")
    print(HEAD)
    line("the fill hour's close (baseline)", base, 20)
    res["F"] = line("the NEXT hour's close", fills(X20, exit="next"), 20)

    print("\nG. SIZE (top-20, 10%)")
    print(HEAD)
    for m in (1.0, 1.5, 2.0):
        res[f"G{m}"] = line(f"{m} x 1/20 per bid", base, 20, mult=m)
    for m in (1.0, 1.5, 2.0):
        res[f"G40_{m}"] = line(f"top-40, {m} x 1/40 per bid", fills(X[X.in40]), 40, mult=m)

    print("\nH. DIAGNOSTICS: top-20, 10%, per fill after 8bp + 30bp (mean / share losing / worst / fills)")
    B = base.copy()
    B["net"] = B.ret - FEE - EXTRA
    B["regime"] = B.t.dt.normalize().map(reg).fillna("?")
    wave = B.groupby("t").sym.transform("count")
    B["wave"] = pd.cut(wave, [0, 1, 4, 999], labels=["alone", "2-4 coins", "5+ coins"])
    B["prior24"] = pd.cut(B.ret24, [-9, -0.25, -0.10, 0, 9], labels=["<-25%", "-25..-10%", "-10..0%", ">0%"])
    prevfill = B.groupby("sym").t.shift(1)
    B["repeat"] = np.where((B.t - prevfill) < pd.Timedelta(hours=24), "repeat <24h", "first")
    B["half"] = np.where(B.t < CUT, "tune", "hold")
    for col in ("regime", "wave", "prior24", "repeat"):
        print(f"  by {col}:")
        for key, g in B.groupby(col, observed=True):
            tu, ho = g[g.half == "tune"], g[g.half == "hold"]
            print(f"    {str(key):<12} {g.net.mean()*100:+6.2f}%  losing {(g.net < 0).mean()*100:3.0f}%  worst "
                  f"{g.net.min()*100:+5.0f}%  n {len(g):>4}  | tune {tu.net.mean()*100:+.2f}% ({len(tu)})  "
                  f"hold {ho.net.mean()*100:+.2f}% ({len(ho)})")
    print("  the 10 worst fills:")
    for _, r in B.nsmallest(10, "net").iterrows():
        print(f"    {r.t:%Y-%m-%d %H:00} {r.sym:<14} net {r.net*100:+5.1f}%  prior 24h {r.ret24*100:+5.0f}%  "
              f"{r['regime']:<5} {r['wave']} {r['repeat']}")
    print("  the worst months of the baseline book, and what filled in them:")
    c, _ = book(base, 20)
    m = c.resample("ME").last().pct_change().dropna().nsmallest(5)
    for me, v in m.items():
        g = B[B.t.dt.to_period("M") == me.to_period("M")]
        print(f"    {me:%Y-%m}: {v*100:+.1f}%  fills {len(g)}, of them losing {(g.net < 0).sum()}; "
              f"worst coins {', '.join(g.nsmallest(3, 'net').sym.str.replace('USDT', ''))}")


def combos():
    """I. Combinations, chosen AFTER reading A-H (logs/wick_better.txt): judged against 'just smaller'."""
    X, _, bear_day = load_all()
    X20, X40 = X[X.in20], X[X.in40]
    base = fills(X20)
    fr = {m: stats(book(base, 20, m)[0]) for m in (0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0)}

    def vs(s, half, wk):
        pts = sorted((fr[m][wk], fr[m][half]) for m in fr)
        return s[half] - float(np.interp(s[wk], [p[0] for p in pts], [p[1] for p in pts]))

    print("I. COMBINATIONS, chosen after A-H. 'vs smaller' = growth minus what the doc 15 book (top-20, 10%) makes")
    print("   when simply sized down (or up) to the same worst month; PASS = positive on BOTH halves.")
    print(f"  {'rule':<52}{'TUNE':>8}{'worst mo':>10}{'HOLD':>8}{'worst mo':>10}{'DD':>6}{'vs smaller: tune':>18}{'hold':>7}")
    for m in (0.5, 1.0, 1.5, 2.0):
        s = fr[m]
        print(f"  {'doc 15 book x' + str(m):<52}{s['tune']:>+7.1f}%{s['wm_t']:>+9.1f}%{s['hold']:>+7.1f}%{s['wm_h']:>+9.1f}%{s['dd']:>5.0f}%")
    rules = [
        ("top-40", X40, dict(), 40, 1.0),
        ("top-20, skip BEAR days", X20, dict(skip_bear=bear_day), 20, 1.0),
        ("top-20, no 2nd fill <24h", X20, dict(no_repeat=True), 20, 1.0),
        ("top-20, skip coins down >25%/24h", X20, dict(max_drop24=0.25), 20, 1.0),
        ("top-20, 8 x hourly volatility", X20, dict(z=8), 20, 1.0),
        ("top-40, skip BEAR", X40, dict(skip_bear=bear_day), 40, 1.0),
        ("top-40, skip BEAR, no 2nd fill <24h", X40, dict(skip_bear=bear_day, no_repeat=True), 40, 1.0),
        ("top-40, skip BEAR, skip coins down >25%/24h", X40, dict(skip_bear=bear_day, max_drop24=0.25), 40, 1.0),
        ("top-40, skip BEAR, skip coins UP >50%/24h (post-hoc)", X40, dict(skip_bear=bear_day, max_rise24=0.5), 40, 1.0),
        ("top-40, skip BEAR x1.5", X40, dict(skip_bear=bear_day), 40, 1.5),
        ("top-40, skip BEAR x2", X40, dict(skip_bear=bear_day), 40, 2.0),
        ("top-40, skip BEAR x2.5", X40, dict(skip_bear=bear_day), 40, 2.5),
        ("top-40, skip BEAR x3", X40, dict(skip_bear=bear_day), 40, 3.0),
    ]
    for name, XX, kw, n, mult in rules:
        s = stats(book(fills(XX, **kw), n, mult)[0])
        a, b = vs(s, "tune", "wm_t"), vs(s, "hold", "wm_h")
        print(f"  {name:<52}{s['tune']:>+7.1f}%{s['wm_t']:>+9.1f}%{s['hold']:>+7.1f}%{s['wm_h']:>+9.1f}%{s['dd']:>5.0f}%"
              f"{a:>+17.1f}{b:>+7.1f}  {'PASS' if a > 0 and b > 0 else 'fail'}")
    Y = fills(X40, skip_bear=bear_day)
    c, _ = book(Y, 40)
    print()
    print("  top-40, skip BEAR, x1: by year " + "  ".join(
        f"{y}: {(g.iloc[-1] / g.iloc[0] - 1) * 100:+.0f}%" for y, g in c.groupby(c.index.year)))
    m = c.resample("ME").last().pct_change().dropna()
    print(f"  months up {(m > 0).mean()*100:.0f}%, flat {(m == 0).mean()*100:.0f}%, worst 3: "
          + ", ".join(f"{i:%Y-%m} {v*100:+.1f}%" for i, v in m.nsmallest(3).items()))


if __name__ == "__main__":
    combos() if "--combos" in sys.argv else main()
