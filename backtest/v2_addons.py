"""ADD TODAY'S PIECES TO THE RUNNING BOT (v2) - does any of them make its worst month less bad? (2026-10-08)

Asked: "we can only add those in the current bot and that reduces worst month". v2 = the triple trend book (12 coins,
21-day anchor, 9x guard; gains shrunk for hindsight, losses whole) + MN 1x + bear sleeve 1x + capped crash bids
(machine.py, $300, 10 orderings). Today's pieces, each an overlay on the same account (pair_lab.py):
    capit   the 4h capitulation buy with breadth (RSI<20, volume >2x, >=5 coins in 24h, +5% or out after 24 bars if not
            in profit): half-account share, 8 slots, 1x; 2 bar phases (+0 / +120 min). Weight 1 = as in the pair.
    daily   the daily Bollinger(30,1.5) book: half-account share, 8 slots, 1x; 3 day boundaries (00/08/16 UTC).
    mncap   the market-neutral book with each coin-week capped at +100% (mn_capped.py), as a REPLACEMENT for v2's MN.

Two corrections to how pair_lab.account books today's books, both of which can flatter a worst month:
    1. MARKED TO MARKET. account() books a trade only on the day it closes. A daily-book trade lasts up to 30 days, so
       a crash month's open losses landed in a later month. Here every open position is marked at each day's last
       hourly close.
    2. A cap exit sells at the CLOSE of its 30th day, but daily_trades stamps it with that day's OPEN, so its slot was
       freed a day early (mistake #17's kind: the allocator knew a position would close later that day). Shifted +1
       day here. 248 of 1,328 daily trades are cap exits, averaging +70%.

THE TEST - against the "just bet smaller" line, the standard every drawdown fix here has had to meet (doc 14):
v2 x k (every part scaled, k = 0.4 .. 1.3) traces worst month against typical year. An add-on PASSES only if, on all 6
years AND on the last 2, it earns a better typical year than v2 x k at the same worst month. Paired by ordering against
v2: change in worst month and typical year, mean +- se and wins. And: what each piece did in v2's worst months.

REGISTERED BEFORE RUNNING:
    - marking to market deepens the daily book's own worst month by 2-5 points and moves the capitulation book's by
      under 1 (its trades last ~1.4 days); the cap-exit shift costs the daily book 1-3 points a year.
    - v2 + capit x1 lifts the typical year 10-20% with the worst month within +-1 point: PASSES.
    - v2 + daily x1 lifts the typical year but deepens the worst month 1-4 points (trend-pair +0.41): FAILS or ties.
    - in v2's 6 worst months, capit is ~0 (idle in most of them), daily is negative in most.
    - nothing ADDED on top makes v2's worst month less bad by itself; only a smaller v2 plus a passing add-on can.

CORRECTED (2026-10-08, machine_combos.py): this file's MN is on ONE rebalance day - a lucky one (mn_combos.py: on 1 of 7
    days the uncapped MN is wiped out). With the day rotated and a +50% short-leg exit, the add-ons buy ~1 point of
    worst month at v2's typical year (-26.0% vs -27.2%), not the -21% below.
RESULT (2026-10-08, logs/v2_addons.txt; $300 after 12 months, 6 years / last 2 years)
    v2 as running: typical $1,812 / $1,625, worst month -29.3% / -25.0%, biggest fall 57% / 45%.
    THE ANSWER - v2 + capit x1 + daily x1, EVERYTHING x0.75: typical $1,777 / $1,773 (same as v2), worst month
    -21.1% / -20.2%, fall 53%. Beats "v2 smaller" on both spans. At full size (x1): typical $2,529 / $2,566 (+49-53%
    over v2 at its worst month) with the worst month -27.3% / -26.2% but the biggest fall DEEPER, 64% / 50%.
    The daily book does the work (alone x1: +43% / +41% over the line; worst month +1.5 +- 0.4 less bad, 23/30); the
    capitulation book adds +4-10% and never moves the worst month (it is idle in v2's bad months: 0 to +3.7%).
    Swapping v2's MN for the capped one FAILS (-6 to -18% at the same worst month): v2's MN gains from the 2026 pumps
    are real backtest money; capping them is a robustness choice that costs return, not a fix.
    CAVEATS (scratchpad check, same run): the daily book was picked after looking (tv_indicators.py); alone it makes
    +64..68%/yr on the tune half and +24..31% on the holdout - it holds, at under half the rate. By year the x0.75 mix
    beats v2 in 2020-21, ties 2023-25, LOSES 2022 (+5% vs +27%) and 2026 (+330% vs +454%); 4 of the add-ons' 6 best
    months are 2021. Every ordering's biggest fall ends 2024-11 (median 53%).
    Predictions: marking deepens the daily worst month 2-5 (WRONG: -2.1 / +0.3 / +2.0 by phase, mixed); the cap-exit
    shift costs 1-3 points (WRONG: +0..+5, the slot held a day longer kept out worse trades - the early release did not
    flatter); capit passes, worst month +-1 (right); daily fails or ties (WRONG: passes, +43%); capit ~0 in v2's worst
    months (right); daily negative in most (half: 5 of 8, small, and +7 / +14 in two); nothing added on top makes the
    worst month less bad (WRONG: the daily book does, +1.5 points).

    python -m backtest.v2_addons
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest import pair_lab as pl  # noqa: E402
from backtest.machine import CUT, summary  # noqa: E402
from backtest.mn_capped import mn_series  # noqa: E402
from backtest.worst_month import TCACHE  # noqa: E402

LOG = ROOT / "logs" / "v2_addons.txt"
PARTS = ROOT / "logs" / "v2_addons_parts.pkl"
SEEDS = tuple(range(10))
DOFF, COFF = (0, 8, 16), (0, 120)
SHARE, SLOTS = 0.5, 8
DAY = pd.Timedelta(days=1)


def allocate(T, seed):
    """pl.account's allocation for ONE book at 1x: each taken trade with its size and P&L."""
    rng = np.random.default_rng(seed)
    ev = sorted(((r.t_in, rng.random(), r.coin, r.t_out, r.net, r.worst) for r in T.itertuples()),
                key=lambda x: (x[0], x[1]))
    liq = 1 - 0.005 - 0.0006
    eq, open_, out = 1.0, [], []
    for t_in, _, coin, t_out, net, worst in ev:
        for p in sorted([p for p in open_ if p[0] <= t_in], key=lambda p: p[0]):
            eq += p[1]
        open_ = [p for p in open_ if p[0] > t_in]
        if eq <= 0:
            break
        if len(open_) >= SLOTS:
            continue
        size = eq * SHARE / SLOTS
        pnl = -size if worst >= liq else size * max(net, -1.0)
        open_.append((t_out, pnl))
        out.append((coin, t_in, t_out, size, pnl))
    return pd.DataFrame(out, columns=["coin", "t_in", "t_out", "size", "pnl"])


_PX: dict = {}


def prices(coin):
    if coin not in _PX:
        h = pl.hourly_all()[coin]
        _PX[coin] = (h.time.to_numpy("datetime64[ns]"), h.open.to_numpy(float), h.close.to_numpy(float))
    return _PX[coin]


def curves(tk, start):
    """(realised, marked) daily equity of one sub-account, indexed by day label; value = state at the day's END."""
    end = tk.t_out.max().normalize() + DAY
    days = pd.date_range(start, end, freq="D")
    E = (days + DAY).to_numpy("datetime64[ns]")
    o = tk.sort_values("t_out", kind="stable")
    cum = np.concatenate([[0.0], np.cumsum(o.pnl.to_numpy())])
    real = 1 + cum[np.searchsorted(o.t_out.to_numpy("datetime64[ns]"), E, side="left")]
    mark = np.zeros(len(E))
    for r in tk.itertuples():
        k0 = np.searchsorted(E, np.datetime64(r.t_in, "ns"), side="right")
        k1 = np.searchsorted(E, np.datetime64(r.t_out, "ns"), side="right")
        if k1 <= k0:
            continue
        ht, ho, hc = prices(r.coin)
        j = np.searchsorted(ht, np.datetime64(r.t_in, "ns"))
        e = ho[j] if j < len(ht) and ht[j] == np.datetime64(r.t_in, "ns") else hc[max(j - 1, 0)]
        idx = np.clip(np.searchsorted(ht, E[k0:k1], side="left") - 1, 0, len(hc) - 1)
        mark[k0:k1] += r.size * np.maximum(hc[idx] / e - 1, -1.0)
    return pd.Series(real, index=days), pd.Series(real + mark, index=days)


def book_parts():
    """Overlay daily returns per (book, phase, seed): booked-as-before, shifted, and shifted + marked."""
    if PARTS.exists():
        return pickle.loads(PARTS.read_bytes())
    out = {}
    for doff in DOFF:
        D = pl.daily_trades(off_h=doff)
        Ds = D.copy()
        Ds.loc[Ds.why == "cap", "t_out"] = Ds.loc[Ds.why == "cap", "t_out"] + DAY
        start = D.t_in.min().normalize()
        for sd in SEEDS:
            r0, _ = curves(allocate(D, sd), start)
            if doff == 0 and sd == 0:                                   # self-check: the replica IS pl.account
                ref = pl.account({"d": (D, SHARE, SLOTS)}, seed=sd)[0]
                both = pd.concat([ref, r0], axis=1).dropna()
                assert len(both) > 1000 and np.abs(both.iloc[:, 0] - both.iloc[:, 1]).max() < 1e-9, "replica != account"
            r1, m1 = curves(allocate(Ds, sd), start)
            assert abs(m1.iloc[-1] - r1.iloc[-1]) < 1e-12, "positions still open at the end"
            out[("daily", doff, sd)] = {"booked": r0, "shifted": r1, "marked": m1}
    for coff in COFF:
        C = pl.capit_trades(coff)
        start = C.t_in.min().normalize()
        for sd in SEEDS:
            r1, m1 = curves(allocate(C, sd), start)
            assert abs(m1.iloc[-1] - r1.iloc[-1]) < 1e-12
            out[("capit", coff, sd)] = {"booked": r1, "shifted": r1, "marked": m1}
    PARTS.write_bytes(pickle.dumps(out))
    return out


def cagr(c):
    yrs = (c.index[-1] - c.index[0]).days / 365
    return c.iloc[-1] ** (1 / yrs) - 1


def worst_month(c):
    return (c.resample("ME").last() / c.resample("ME").last().shift(1)).dropna().min() - 1


def main():
    bp = book_parts()
    cache = pickle.loads(TCACHE.read_bytes())
    mn_raw, mn_cap = pl.mn_daily(), mn_series(1.0)
    sleeve = pd.read_pickle(ROOT / "logs" / "breadth_real_1x.pkl")["full"]
    bids = pd.read_pickle(ROOT / "logs" / "wick_capped.pkl")[10]
    lines = [f"backtest/v2_addons.py, {pd.Timestamp.now():%Y-%m-%d %H:%M}; $300, 10 orderings; trend gains shrunk for "
             f"hindsight, everything else raw; today's books marked to market", ""]

    lines.append("A. THE CORRECTIONS, each book alone (its half-account, 8 slots, 1x), mean of 10 orderings")
    lines.append(f"  {'book':18} {'growth/yr: booked':>18} {'cap fix':>8} {'worst month: booked':>20} {'marked':>7}")
    for bk, offs in (("daily", DOFF), ("capit", COFF)):
        for off in offs:
            g0 = np.mean([cagr(bp[(bk, off, s)]["booked"]) for s in SEEDS])
            g1 = np.mean([cagr(bp[(bk, off, s)]["shifted"]) for s in SEEDS])
            w0 = np.mean([worst_month(bp[(bk, off, s)]["shifted"]) for s in SEEDS])
            w1 = np.mean([worst_month(bp[(bk, off, s)]["marked"]) for s in SEEDS])
            lines.append(f"  {bk + ' phase ' + str(off):18} {g0 * 100:>17.1f}% {g1 * 100:>7.1f}% {w0 * 100:>19.1f}% "
                         f"{w1 * 100:>6.1f}%")
    lines.append("")

    def ov(bk, off, sd, idx):
        return bp[(bk, off, sd)]["marked"].pct_change().reindex(idx).fillna(0.0)

    base = {}
    for sd in SEEDS:
        t = cache[("anchor", sd)]
        idx = t.index
        base[sd] = pd.DataFrame({"trend": t, "mn_raw": mn_raw.reindex(idx).fillna(0.0),
                                 "mn_cap": mn_cap.reindex(idx).fillna(0.0), "sleeve": sleeve.reindex(idx).fillna(0.0),
                                 "bids": bids.reindex(idx).fillna(0.0)})

    def build(w, k=1.0):
        """[(seed, curve-of-daily-returns)] for weights w over every phase combination the weights touch."""
        doffs = DOFF if w.get("daily", 0) else (None,)
        coffs = COFF if w.get("capit", 0) else (None,)
        res = []
        for sd in SEEDS:
            b = base[sd]
            core = sum(w.get(p, 0) * b[p] for p in ("trend", "mn_raw", "mn_cap", "sleeve", "bids"))
            for d in doffs:
                for c in coffs:
                    x = core.copy()
                    if d is not None:
                        x = x + w["daily"] * ov("daily", d, sd, b.index)
                    if c is not None:
                        x = x + w["capit"] * ov("capit", c, sd, b.index)
                    res.append((sd, k * x))
        return res

    V2 = dict(trend=1, mn_raw=1, sleeve=1, bids=1)
    v2 = dict(build(V2))

    # B. what each piece did in v2's worst months (months ranked by v2's mean over orderings)
    mo = lambda x: (1 + x).resample("ME").prod() - 1  # noqa: E731
    v2m = pd.concat([mo(v2[s]) for s in SEEDS], axis=1).mean(axis=1)
    pieces = {"trend": [mo(base[s]["trend"]) for s in SEEDS], "MN": [mo(base[s]["mn_raw"]) for s in SEEDS],
              "sleeve": [mo(base[s]["sleeve"]) for s in SEEDS], "bids": [mo(base[s]["bids"]) for s in SEEDS],
              "MN capped": [mo(base[s]["mn_cap"]) for s in SEEDS],
              "capit": [mo(ov("capit", c, s, base[s].index)) for c in COFF for s in SEEDS],
              "daily": [mo(ov("daily", d, s, base[s].index)) for d in DOFF for s in SEEDS]}
    pm = {k: pd.concat(v, axis=1).mean(axis=1) for k, v in pieces.items()}
    lines.append("B. v2's 8 WORST MONTHS (mean of 10 orderings) and what each piece did in them, % of the account")
    lines.append(f"  {'month':8} {'v2':>7} | " + " ".join(f"{k:>9}" for k in pm))
    for m in v2m.nsmallest(8).index:
        lines.append(f"  {m:%Y-%m} {v2m[m] * 100:>6.1f}% | " + " ".join(f"{pm[k][m] * 100:>8.1f}%" for k in pm))
    allm = pd.DataFrame(pm).loc[v2m.index]
    lines.append(f"  monthly correlation with v2: " + ", ".join(f"{k} {allm[k].corr(v2m):+.2f}" for k in pm))
    lines.append("")

    # C. the frontier and the add-ons
    ks = np.round(np.arange(0.4, 1.31, 0.05), 2)
    spans = (("all 6 years", None), ("last 2 years", CUT))
    front = {sp: [] for sp, _ in spans}
    for k in ks:
        xs = [x for _, x in build(V2, k)]
        for sp, t0 in spans:
            s = summary(xs, t0)
            front[sp].append((s["wm"], s["typ"], k))

    def on_front(sp, wm):
        f = sorted(front[sp])
        return float(np.interp(wm, [a for a, _, _ in f], [b for _, b, _ in f]))

    def k_for_typ(sp, typ):
        f = sorted(front[sp], key=lambda z: z[1])
        return float(np.interp(typ, [b for _, b, _ in f], [a for a, _, _ in f]))

    configs = {
        "v2 (as running)": V2,
        "v2 + capit x0.5": dict(V2, capit=0.5),
        "v2 + capit x1": dict(V2, capit=1),
        "v2 + capit x2": dict(V2, capit=2),
        "v2 + daily x0.5": dict(V2, daily=0.5),
        "v2 + daily x1": dict(V2, daily=1),
        "v2 + capit x1 + daily x1": dict(V2, capit=1, daily=1),
        "v2, MN -> capped x1": dict(trend=1, mn_cap=1, sleeve=1, bids=1),
        "v2, MN -> capped x0.5": dict(trend=1, mn_cap=0.5, sleeve=1, bids=1),
        "v2 + capit x2, MN -> capped x1": dict(trend=1, mn_cap=1, sleeve=1, bids=1, capit=2),
        "MIX B (trend x0.5 + pair + MNcap x0.5 + sl + bids)": dict(trend=0.5, mn_cap=0.5, sleeve=1, bids=1, capit=1,
                                                                    daily=1),
    }
    lines.append("C. $300 after 12 months - typical / bad / worst | worst month | biggest fall | months up || v2 x k at the "
                 "SAME worst month earns -> verdict")
    passes = {}
    results = {}
    for sp, t0 in spans:
        lines.append(f"  {sp}")
        for nm, w in configs.items():
            xs = build(w)
            s = summary([x for _, x in xs], t0)
            ref = on_front(sp, s["wm"])
            ok = s["typ"] > ref * 1.02
            passes.setdefault(nm, []).append(ok)
            results[(nm, sp)] = (s, xs)
            lines.append(f"    {nm:52} ${s['typ']:>6,.0f} / ${s['bad']:>6,.0f} / ${s['worst']:>5,.0f} | {s['wm']:+6.1f}% | "
                         f"{s['dd']:3.0f}% | {s['up']:3.0f}% || ${ref:>6,.0f} -> {'BEATS' if ok else 'no'} "
                         f"({(s['typ'] / ref - 1) * 100:+.0f}%)")
        lines.append("")
    lines.append("  the line (v2 x k): " + "; ".join(f"x{k:.2f} {wm:+.1f}% ${ty:,.0f}"
                                                   for wm, ty, k in front["all 6 years"] if k in (0.5, 0.7, 0.85, 1.0, 1.2)))
    lines.append("")

    # D. paired against v2, same ordering
    lines.append("D. PAIRED vs v2 on the same ordering (all 6 years): change in worst month (points, + = less bad) and in "
                 "typical year ($); mean +- se, wins")
    per_v2 = {sd: summary([v2[sd]]) for sd in SEEDS}
    for nm, w in configs.items():
        if nm == "v2 (as running)":
            continue
        xs = results[(nm, "all 6 years")][1]
        dw = np.array([summary([x])["wm"] - per_v2[sd]["wm"] for sd, x in xs])
        dt = np.array([summary([x])["typ"] - per_v2[sd]["typ"] for sd, x in xs])
        se = lambda a: a.std(ddof=1) / np.sqrt(len(a))  # noqa: E731
        lines.append(f"  {nm:52} worst month {dw.mean():+5.1f} +- {se(dw):.1f} ({(dw > 0).sum()}/{len(dw)} less bad) | "
                     f"typical ${dt.mean():+6,.0f} +- {se(dt):,.0f} ({(dt > 0).sum()}/{len(dt)} higher)")
    lines.append("")

    # E. passing add-ons scaled to v2's typical year: what worst month do they buy?
    lines.append("E. EVERY config scaled so its typical year equals v2's (all 6 years): the worst month it then has")
    v2s = results[("v2 (as running)", "all 6 years")][0]
    for nm, w in configs.items():
        best = None
        for g in np.round(np.arange(0.5, 1.61, 0.05), 2):
            s = summary([x for _, x in build(w, g)])
            if best is None or abs(s["typ"] - v2s["typ"]) < abs(best[1]["typ"] - v2s["typ"]):
                best = (g, s)
        g, s = best
        s2 = summary([x for _, x in build(w, g)], CUT)
        tag = "PASSES both spans" if all(passes[nm]) else ("passes 6y only" if passes[nm][0] else
                                                          ("passes 2y only" if passes[nm][1] else "fails"))
        lines.append(f"  {nm:52} x{g:.2f}: typical ${s['typ']:>6,.0f}, worst month {s['wm']:+6.1f}% (v2 {v2s['wm']:+.1f}%), "
                     f"fall {s['dd']:3.0f}% | last 2y ${s2['typ']:,.0f}, {s2['wm']:+.1f}% | {tag}")
    lines.append("")

    # F. by market type, v2 vs the add-on books
    reg = pl.btc_regime_daily()
    lab = reg.reindex(v2m.index.normalize(), method="ffill")
    labm = reg.groupby(reg.index.to_period("M")).agg(lambda x: x.value_counts().idxmax())
    rg = labm.reindex(v2m.index.to_period("M")).to_numpy()
    lines.append("F. AVERAGE MONTH BY MARKET TYPE (BTC 50-day trend), % of the account")
    for nm in ("v2", "capit", "daily", "MN capped", "MN"):
        ser = v2m if nm == "v2" else pm[nm]
        lines.append(f"  {nm:10} " + "  ".join(f"{r} {ser.to_numpy()[rg == r].mean() * 100:+5.1f}% ({(rg == r).sum()})"
                                             for r in ("bull", "chop", "bear")))
    del lab
    txt = "\n".join(lines)
    print(txt)
    LOG.write_text(txt + "\n")


if __name__ == "__main__":
    main()
