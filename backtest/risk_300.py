"""$300 IN THE FINAL VERSION: best and worst months, monthly withdrawals, and liquidation.

Asked 2026-09-24: "what am I looking at with best month on $300, the worst, and is there a risk of
liquidation, and if I have to withdraw an amount every month". The final version is the trend
book (triple) at 100% + 21-day equity anchor (9x gross guard) + bear sleeve 1x + market-neutral 1x,
measured as in max_mix.py (trend gains shrunk for hindsight, losses whole; the other two raw).

A. MONTHS on $300: best, good, typical, bad, worst - dollars and percent, 6 years and last 2.
B. FIXED WITHDRAWALS of $10 / $20 / $30 / $50 at every month end from $300, over every 12-month
   window: what is left, how often the account ends below $300 and below $150 (doc 14 section 12's
   floor), and how much came out.
C. LIQUIDATION. The backtests book exits at stop prices and cannot model a margin call. So the
   trend book is replayed HOUR BY HOUR with every open unit marked at its coin's LOW (longs) or
   HIGH (shorts) in that hour - all coins at their worst in the same hour, a deliberately
   pessimistic stack - against the account's realised equity. If that ever reaches zero the
   account would have been liquidated. Reported: gross leverage through time, the worst moment's
   account value, and the three crash days (2021-05-19, 2024-08-05, 2025-10-10).
   The MN book (dollar-neutral) and the sleeve (bear-only) are not in C; C is the trend book,
   which carries the leverage.

REGISTERED PREDICTION (2026-09-24, before running): worst month about -30% (-$90 on $300), best
month several hundred percent; withdrawing $20/month leaves the account above $300 in most years
and $50/month drains it in most years; C: no historical liquidation, with the worst hour leaving
~40-60% of the account, and the 2025-10-10 crash the closest call.

    python -m backtest.risk_300
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import backtest.dd_fixes as D  # noqa: E402
import backtest.max_mix as M  # noqa: E402
from backtest import blend  # noqa: E402
from backtest.bar_phase import rows_for_phase  # noqa: E402
from backtest.bear_chop import fast_run  # noqa: E402
from backtest.bull_boost import regimes  # noqa: E402
from backtest.carry_check import exact_funding  # noqa: E402
from backtest.expectations import month_ends  # noqa: E402
from backtest.market_neutral import drop_non_crypto, load_panel  # noqa: E402
from backtest.wide_book import eligibility  # noqa: E402

CAP = 300.0
SEEDS = tuple(range(10))
ROOT = Path(__file__).resolve().parents[1]
CUT = pd.Timestamp("2024-08-29")


def sim_units(rows, bear_ns, bear_v, seed, lev=9.0):
    """dd_fixes.sim (anchor 21d) that also returns every TAKEN unit:
    (coin, side, open ns, close ns, entry price, coins held) - coins = dollars-per-R / risk."""
    import numpy as np
    rng = np.random.default_rng(seed)
    tie = rng.random(len(rows))
    o = [rows[i] for i in sorted(range(len(rows)), key=lambda i: (rows[i]["t0"], tie[i]))]
    ev = []
    for j, r in enumerate(o):
        ev.append((r["t0"], 1, j, 0))
        for k in range(1, len(r["ut"])):
            ev.append((max(r["ut"][k], r["t0"]), 1, j, k))
        ev.append((r["t1"], 0 if r["t1"] > r["t0"] else 3, j, -1))
    ev.sort(key=lambda e: (e[0], e[1]))
    ctx = D.Ctx()
    size_fn = D.anchor(21)
    state, open_n, eq, pts, units = {}, 0, 1.0, [], []
    for t, kind, j, k in ev:
        r = o[j]
        if kind in (0, 3):
            s = state.pop(j, None)
            if s is None:
                continue
            open_n -= 1
            eq = max(eq + s["dpr"] * sum(r["uR"][kk] for kk in s["open"]), 0.0)
            ctx.ht.append(t); ctx.he.append(eq); ctx.peak = max(ctx.peak, eq); pts.append((t, eq))
            for kk in s["open"]:
                units.append((r["coin"], r["side"], max(r["ut"][kk], r["t0"]), r["t1"], r["ue"][kk], s["dpr"] / r["risk"]))
            continue
        if k == 0:
            if open_n >= 12:
                continue
            ib = bear_v[max(np.searchsorted(bear_ns, t, side="right") - 1, 0)]
            f = blend.RISK / 100.0 * (blend.REGIME_MULT if ib else 1.0)
            s = dict(dpr=f * size_fn(t, eq, ctx), open=set())
        else:
            s = state.get(j)
            if s is None:
                continue
        notional = s["dpr"] * r["ue"][k] / r["risk"]
        gross = sum(st["dpr"] * o[jj]["ue"][kk] / o[jj]["risk"] for jj, st in state.items() for kk in st["open"])
        if gross + notional > lev * eq:
            continue
        s["open"].add(k)
        if k == 0:
            state[j] = s; open_n += 1
    return pts, units


def part_c(rows, bn, bv):
    px = {}
    for c in blend.BOOK:
        d = blend.load(c)
        if d is not None:
            px[c] = d.set_index(pd.DatetimeIndex(d["time"]).as_unit("ns"))[["high", "low", "close"]]
    grid = pd.date_range(min(p.index[0] for p in px.values()), max(p.index[-1] for p in px.values()), freq="h").as_unit("ns")
    H = {c: p.reindex(grid).ffill() for c, p in px.items()}
    out = []
    for sd in (0, 1, 2):
        pts, units = sim_units(rows, bn, bv, sd)
        real = pd.Series([e for _, e in pts], index=pd.DatetimeIndex([t for t, _ in pts]).as_unit("ns"))
        real = real[~real.index.duplicated(keep="last")].reindex(grid, method="ffill").fillna(1.0).to_numpy()
        worst = np.zeros(len(grid)); gross = np.zeros(len(grid)); unreal = np.zeros(len(grid))
        gi = grid.asi8
        for coin, side, t_open, t_close, e, q in units:
            if coin not in H:
                continue
            a = np.searchsorted(gi, t_open, side="left")
            b = np.searchsorted(gi, t_close, side="left")
            if b <= a:
                continue
            h = H[coin]
            cl = h["close"].to_numpy()[a:b]
            if side == "long":
                worst[a:b] += q * (h["low"].to_numpy()[a:b] - e)
                unreal[a:b] += q * (cl - e)
            else:
                worst[a:b] += q * (e - h["high"].to_numpy()[a:b])
                unreal[a:b] += q * (e - cl)
            gross[a:b] += q * cl
        val = real + worst                       # account value with every coin at its worst this hour
        frac = val / real
        # LEVERAGE AS THE EXCHANGE SEES IT: open notional over the account INCLUDING open profit.
        # A first version divided by realised equity only and read p99 12.6x / max 21.2x against a
        # 9x guard; deep-in-profit runners made that denominator far too small.
        lev = gross / (real + unreal)
        i = int(np.nanargmin(frac))
        crash = {}
        for day in ("2021-05-19", "2024-08-05", "2025-10-10"):
            m = (grid >= pd.Timestamp(day)) & (grid < pd.Timestamp(day) + pd.Timedelta(days=2))
            crash[day] = (float(np.nanmin(frac[m])), float(np.nanmax(lev[m])))
        mx_i = int(np.nanargmax(lev))
        out.append(dict(min_frac=float(frac[i]), when=grid[i], lev_then=float(lev[i]), p99=float(np.nanpercentile(lev, 99)),
                        mx=float(np.nanmax(lev)), over5=float((lev > 5).mean() * 100), over8=float((lev > 8).mean() * 100),
                        over10=float((lev > 10).mean() * 100), mx_when=grid[mx_i], crash=crash))
    print("\nC. LIQUIDATION - trend book (triple + 21d anchor, 9x guard), hour by hour, every open unit at its")
    print("   coin's worst price of that hour at the same time (pessimistic). 'left' = account value / account.")
    for sd, r in zip((0, 1, 2), out):
        print(f"   ordering {sd}: leverage (open notional / account incl. open profit) p99 {r['p99']:.1f}x, max {r['mx']:.1f}x "
              f"({r['mx_when']:%Y-%m-%d}); above 5x {r['over5']:.1f}% of hours, above 8x {r['over8']:.2f}%, above 10x "
              f"{r['over10']:.2f}% | WORST HOUR {r['when']:%Y-%m-%d %H:00}: {r['min_frac']*100:.0f}% of the account left "
              f"(at {r['lev_then']:.1f}x)")
        print("      crash days - worst hour left / peak leverage: " + " | ".join(
            f"{d}: {v[0]*100:.0f}% / {v[1]:.1f}x" for d, v in r["crash"].items()))
    return out


def main():
    bear = regimes()[1000]
    bn = pd.DatetimeIndex(bear.index).as_unit("ns").asi8
    bv = bear.to_numpy(bool)
    C, F, first = load_panel()
    C.index = C.index.astype("datetime64[ns]")
    Fx = exact_funding(C.index, C.columns)
    mn = fast_run(C, Fx, first, drop_non_crypto(eligibility(60)), look=30, hold=7, fshift=1)
    mn_d = pd.Series(mn.net.to_numpy(), index=pd.DatetimeIndex(mn.t) + pd.Timedelta(days=7)).groupby(level=0).sum()
    sleeve = pd.read_pickle(ROOT / "logs" / "breadth_real_1x.pkl")["full"]
    rows = D.decompose(rows_for_phase(0, tight=True, time_stop=(100, 2.0), max_units=7))

    books = {"today: triple alone": [], "FINAL version": []}
    for sd in SEEDS:
        base = D.sim(rows, bn, bv, sd).pct_change().fillna(0.0)
        s = M.shrink_factor(base)
        t0 = pd.Series(np.where(base > 0, s * base, base), index=base.index)
        r = D.sim(rows, bn, bv, sd, lev=9.0, size_fn=D.anchor(21)).pct_change().fillna(0.0)
        t1 = pd.Series(np.where(r > 0, s * r, r), index=r.index)
        fin = t1 + mn_d.reindex(t1.index).fillna(0.0) + sleeve.reindex(t1.index).fillna(0.0)
        for name, x in (("today: triple alone", t0), ("FINAL version", fin)):
            me = month_ends((1 + x).cumprod())
            books[name].append((me / me.shift(1)).dropna())

    print(f"A. A MONTH ON ${CAP:.0f} (10 orderings; trend gains shrunk for hindsight, losses whole)")
    for span, t0 in (("all 6 years", None), ("last 2 years", CUT)):
        print(f"\n  {span}")
        print(f"  {'book':<22}{'best':>14}{'1 in 10':>12}{'1 in 4':>11}{'typical':>11}{'1 in 4 bad':>12}{'1 in 10 bad':>13}{'worst':>13}{'up':>6}")
        for name, lst in books.items():
            m = pd.concat([x if t0 is None else x[x.index >= t0] for x in lst]).to_numpy() - 1
            q = lambda p: np.percentile(m, p)  # noqa: E731
            cells = [m.max(), q(90), q(75), q(50), q(25), q(10), m.min()]
            print(f"  {name:<22}" + "".join(f"{v*100:>+6.0f}% ${CAP*v:>+5.0f}" for v in cells) + f"{(m > 0).mean()*100:>5.0f}%")

    print(f"\nB. WITHDRAWING A FIXED AMOUNT AT EVERY MONTH END, starting from ${CAP:.0f} (FINAL version, every")
    print("   12-month window, 6 years). If the balance cannot cover it, the withdrawal is skipped that month.")
    print(f"  {'per month':>10}{'taken out/yr':>14}{'balance left: typical':>23}{'bad (1 in 4)':>14}{'below $300':>12}{'below $150':>12}{'skipped':>9}")
    fin = books["FINAL version"]
    for w in (0, 10, 20, 30, 50, 75):
        outs, ends, skips = [], [], []
        for x in fin:
            m = x.to_numpy()
            for i in range(len(m) - 11):
                bal, out, sk = CAP, 0.0, 0
                for g in m[i:i + 12]:
                    bal *= g
                    if bal - w >= 150:
                        bal -= w; out += w
                    elif w:
                        sk += 1
                outs.append(out); ends.append(bal); skips.append(sk)
        e = np.array(ends)
        print(f"  ${w:>9}{np.median(outs):>13.0f}${np.median(e):>22,.0f}${np.percentile(e, 25):>13,.0f}"
              f"{(e < CAP).mean()*100:>11.0f}%{(e < 150).mean()*100:>11.0f}%{np.mean(skips):>9.1f}")
    part_c(rows, bn, bv)


if __name__ == "__main__":
    main()
