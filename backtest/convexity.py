"""THE MACHINE IS A CONVEX PAYOFF: WHAT THAT MEANS FOR WAITING, FOR THE DAY-45 KILL, AND FOR TIMING (2026-10-27)

residual_edge.py (2026-10-27) found that the final machine's backtest return is not BTC exposure (R2 0.02): its giant months came
with BTC flat or down (2024-12: machine +524%, BTC -2.9%), the best 3 of 78 months carry ~40% of the average month, the median month is
+7.8%. The user: "do something about the most useful finding". The finding does not change a rule - what it changes is how the
record has to be READ, so this file turns it into numbers the fund / kill decision can use, and tests the one thing that could
change a rule (can the explosive months be timed?).

DATA   the 9-book machine's DAILY account return, 10 orderings (backtest/scorecard_bands.py's own construction: the 7 booked books +
       news + NASDAQ dip, trend gains shrunk 3x for hindsight, everything else raw), 2020-03 .. 2026-08, cached by --build to
       logs/daily_combos_cache/machine_account_daily.pkl. A "window" is an N-day stretch from any start day of any ordering; the 10
       orderings share one market path and windows overlap, so the number of INDEPENDENT stretches is a handful of market episodes -
       every conditional count below is printed with the number of distinct start-MONTHS behind it.
PARTS  1 LUMPINESS: how much of the growth the best days / months carry, and how long the account waits between equity highs.
       2 WAITING: from a random start, how long until the account is +20% / +50% / +100% up.
       3 THE DAY-45 LINE (doc 22 s3b: KILL if main sits under -12.9% at day 45): among windows that sat under it at day 45, how many
         were above their start by day 90 / 180 / 365 - what a KILL gives up; and among those over it. Plus the analogue of today:
         windows 15% down at day 17.
       4 TIMING: do trailing dispersion / runner count / alt breadth of the point-in-time top-40 predict the NEXT month's trend or
         account return? Same-month relation (the mechanism) vs next-month (the use).
       5 LIVE (--live): the same measures today, from Binance daily klines of the current top-40 by prior-month volume.
THIS CHANGES NO RULE. doc 22's lines were fixed before the data and are not moved here; part 3 prices what they do.

REGISTERED BEFORE THE FIRST RUN (2026-10-27)
  C1  The best 5% of days carry more than 80% of the total log growth, and the best 10% of months more than 60%.
  C2  From a random start, P(account +20% within 90 days) is 20-40% and P(+20% within 365 days) is above 85%.
  C3  Among windows under -12.9% at day 45, at least 50% are above their start by day 180 and at least 70% by day 365
      (the KILL gives up a machine that mostly recovers - which is the machine's profile, and why the line was set at 10% / 58%).
  C4  Still, the line is informative: P(above start at day 180) is at least 15 points higher among windows over the line than under it.
  C5  Trailing dispersion / runner count / breadth do NOT predict next month: |Spearman| < 0.25 with the next month's trend return on at
      least one half; the SAME-month Spearman of dispersion with the trend book's month is >= 0.4 (the mechanism is there, the timing is not).
  C6  Today the opportunity set is not dead: the live cross-sectional dispersion of the top-40 is above its 2020-2026 median.

    python -m backtest.convexity --build     (once, ~15 min: caches the daily series)
    python -m backtest.convexity [--live]
"""
from __future__ import annotations

import json
import pickle
import sys
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

CACHE = ROOT / "logs" / "daily_combos_cache" / "machine_account_daily.pkl"
LOG = ROOT / "logs" / "convexity.txt"
NAMES = {"trend": "trend", "mn_blend": "mn", "carry": "carry", "sleeve": "sleeve", "daily": "daily", "capit2": "capit2", "bids": "bids"}
KILL = -0.129


def build():
    from backtest.all_books import machine_books, ndx_dip, news_book
    M = machine_books()
    news_all, ndx_all = news_book(), ndx_dip()
    tots, trends = [], []
    for x in M:
        nw = news_all.reindex(x.index).fillna(0.0).to_numpy()
        nd = ndx_all.reindex(x.index).fillna(0.0).to_numpy()
        tots.append(pd.Series(x[list(NAMES)].sum(axis=1).to_numpy() + nw + nd, index=x.index))
        trends.append(x["trend"].copy())
    CACHE.write_bytes(pickle.dumps(dict(tot=tots, trend=trends)))
    print("cached", CACHE, [len(t) for t in tots])


def load():
    d = pickle.loads(CACHE.read_bytes())
    return d["tot"], d["trend"]


def equity_paths(tot):
    return [np.r_[1.0, np.cumprod(1 + t.to_numpy())] for t in tot]


def part1(tot, L):
    L.append("1  LUMPINESS (daily account return, 10 orderings)")
    best5, best10m, months_pos = [], [], []
    droughts = []
    for t in tot:
        lg = np.log1p(t.clip(lower=-0.99).to_numpy())
        tgrow = lg.sum()
        k = int(len(lg) * 0.05)
        best5.append(np.sort(lg)[::-1][:k].sum() / tgrow)
        m = t.groupby(t.index.to_period("M")).apply(lambda s: np.log1p(s.clip(lower=-0.99)).sum())
        km = max(int(len(m) * 0.10), 1)
        best10m.append(np.sort(m.to_numpy())[::-1][:km].sum() / m.sum())
        eq = np.cumprod(1 + t.to_numpy())
        peak = np.maximum.accumulate(eq)
        newhigh = np.flatnonzero(eq >= peak - 1e-12)
        gaps = np.diff(np.r_[0, newhigh])
        droughts.append((gaps.max(), np.median(gaps[gaps > 1]) if (gaps > 1).any() else 0, (eq < peak).mean()))
    c1 = np.mean(best5) > 0.80 and np.mean(best10m) > 0.60
    d = np.array(droughts)
    L.append(f"   best 5% of days carry {np.mean(best5) * 100:.0f}% of the total log growth; best 10% of months {np.mean(best10m) * 100:.0f}%")
    L.append(f"   share of days the account sits below its previous peak {d[:, 2].mean() * 100:.0f}%; longest stretch without a new high "
             f"{d[:, 0].mean():.0f} days (orderings {d[:, 0].min():.0f}..{d[:, 0].max():.0f}); typical gap between highs {d[:, 1].mean():.0f} days")
    return c1


def windows_ret(eq, k):
    return eq[k:] / eq[:-k] - 1


def part2(tot, L):
    L.append("")
    L.append("2  WAITING: from a random start day, the share of stretches that have reached +X% by day N (any time up to N)")
    res = {}
    for X in (0.20, 0.50, 1.00):
        row = []
        for N in (90, 180, 365):
            hits = []
            for e in equity_paths(tot):
                n = len(e)
                # running max of equity relative to the start, over the next N days
                for s in range(0, n - N - 1, 1):
                    seg = e[s + 1:s + N + 1] / e[s]
                    hits.append(seg.max() >= 1 + X)
            row.append(np.mean(hits))
        res[X] = row
        L.append(f"   +{X * 100:.0f}% : within 90 days {row[0] * 100:4.0f}%   180 days {row[1] * 100:4.0f}%   365 days {row[2] * 100:4.0f}%")
    c2 = 0.20 <= res[0.20][0] <= 0.40 and res[0.20][2] > 0.85
    return c2


def part3(tot, L):
    L.append("")
    L.append("3  THE DAY-45 LINE (KILL if under -12.9% at day 45), priced on the backtest's own windows")
    rows = []
    for o, e in enumerate(equity_paths(tot)):
        idx = tot[o].index
        n = len(e)
        for s in range(0, n - 366):
            r17, r45 = e[s + 17] / e[s] - 1, e[s + 45] / e[s] - 1
            rows.append((o, s, idx[min(s, len(idx) - 1)], r17, r45, e[s + 90] / e[s] - 1, e[s + 180] / e[s] - 1, e[s + 365] / e[s] - 1))
    D = pd.DataFrame(rows, columns=["o", "s", "date", "r17", "r45", "r90", "r180", "r365"])
    D["month"] = D.date.dt.to_period("M")
    under, over = D[D.r45 < KILL], D[D.r45 >= KILL]
    L.append(f"   windows: {len(D)} ({D.month.nunique()} distinct start-months); under the line at day 45: {len(under)} "
             f"({under.month.nunique()} months, {len(under) / len(D) * 100:.0f}%)")
    out = {}
    for nm, g in (("UNDER -12.9% at day 45 (a KILL)", under), ("OVER the line (continue)", over)):
        out[nm] = [(g[c] > 0).mean() for c in ("r90", "r180", "r365")]
        L.append(f"   {nm:<34} above their start by day 90: {out[nm][0] * 100:3.0f}%   180: {out[nm][1] * 100:3.0f}%   365: {out[nm][2] * 100:3.0f}%"
                 f"   median day-365 return {g.r365.median() * 100:+.0f}%")
    ana = D[(D.r17 <= -0.13) & (D.r17 >= -0.18)]
    if len(ana):
        L.append(f"   TODAY'S ANALOGUE: windows 13-18% down at day 17 (main is -15.1%): {len(ana)} windows from {ana.month.nunique()} start-months: "
                 f"over the line at day 45: {(ana.r45 >= KILL).mean() * 100:.0f}%; above start by day 90 {(ana.r90 > 0).mean() * 100:.0f}%, "
                 f"180 {(ana.r180 > 0).mean() * 100:.0f}%, 365 {(ana.r365 > 0).mean() * 100:.0f}%; median day-365 return {ana.r365.median() * 100:+.0f}%")
        L.append(f"      the analogues' start-months: " + ", ".join(sorted({str(m) for m in ana.month.unique()})[:24]))
    k1, k2 = out["UNDER -12.9% at day 45 (a KILL)"], out["OVER the line (continue)"]
    c3 = k1[1] >= 0.50 and k1[2] >= 0.70
    c4 = k2[1] - k1[1] >= 0.15
    return c3, c4


def timing(L):
    from backtest.market_neutral import drop_non_crypto, load_panel
    from backtest.regime_signals import member_mask
    from backtest.wide_book import eligibility
    C, F, first = load_panel()
    C.index = C.index.astype("datetime64[ns]")
    X = C.to_numpy(float)
    mem = member_mask(C, first, drop_non_crypto(eligibility(40))) & np.isfinite(X)
    ib = list(C.columns).index("BTCUSDT")
    n = len(C)
    st = pd.DataFrame(np.nan, index=C.index, columns=["disp", "runners", "breadth", "med"])
    for d in range(201, n):
        m = mem[d - 1].copy()
        m[ib] = False
        m &= np.isfinite(X[d]) & np.isfinite(X[d - 30])
        if m.sum() >= 8:
            r = X[d, m] / X[d - 30, m] - 1
            st.iloc[d] = [np.std(r), np.mean(r > 0.20), np.nan, np.median(r)]
            a200 = pd.Series(X[d - 199:d + 1].mean(axis=0))
            ok = m & np.isfinite(a200.to_numpy())
            st.iat[d, 2] = np.mean(X[d, ok] > a200.to_numpy()[ok]) if ok.sum() >= 8 else np.nan
    me = st.resample("ME").last()
    me.index = me.index.to_period("M")
    P = pd.read_pickle(ROOT / "logs" / "chop_gap_months.pkl")
    mp = P.groupby("month")[["trend", "account"]].mean()
    mp.index = pd.PeriodIndex(mp.index, freq="M")
    nxt = me.copy()
    nxt.index = nxt.index + 1
    D = pd.concat([nxt.add_prefix("prev_"), mp], axis=1).dropna()
    # same-month: dispersion over the month's own 30-day window ending at the month-end
    same = pd.concat([me.add_prefix("same_"), mp], axis=1).dropna()
    cut = int(len(D) * 0.6)

    def sp(a, b):
        return float(np.corrcoef(pd.Series(a).rank(), pd.Series(b).rank())[0, 1])

    L.append("")
    L.append(f"4  TIMING: Spearman of the state variable with the trend book's month ({len(D)} months, split at the 60% month)")
    L.append(f"   {'variable':<10} {'SAME month tune/hold':>22} {'NEXT month tune/hold':>22}   (account, next: tune/hold)")
    out = {}
    for v in ("disp", "runners", "breadth", "med"):
        s1 = (sp(same[f"same_{v}"].iloc[:int(len(same) * .6)], same.trend.iloc[:int(len(same) * .6)]),
              sp(same[f"same_{v}"].iloc[int(len(same) * .6):], same.trend.iloc[int(len(same) * .6):]))
        s2 = (sp(D[f"prev_{v}"].iloc[:cut], D.trend.iloc[:cut]), sp(D[f"prev_{v}"].iloc[cut:], D.trend.iloc[cut:]))
        s3 = (sp(D[f"prev_{v}"].iloc[:cut], D.account.iloc[:cut]), sp(D[f"prev_{v}"].iloc[cut:], D.account.iloc[cut:]))
        out[v] = (s1, s2, s3)
        L.append(f"   {v:<10} {s1[0]:>+10.2f} / {s1[1]:+.2f}   {s2[0]:>+10.2f} / {s2[1]:+.2f}      ({s3[0]:+.2f} / {s3[1]:+.2f})")
    c5 = (abs(out["disp"][1][0]) < 0.25 or abs(out["disp"][1][1]) < 0.25) and min(out["disp"][0]) >= 0.4
    return c5, st


def live(st, L):
    from news import mood_now as mn
    now = pd.Timestamp.now(tz="UTC").to_pydatetime()
    names = mn.universe(40, now=now)
    r30 = {}
    for s in names:
        if s == "BTCUSDT":
            continue
        try:
            with urllib.request.urlopen(f"https://fapi.binance.com/fapi/v1/klines?symbol={s}&interval=1d&limit=35", timeout=20) as r:
                k = json.loads(r.read().decode())
        except Exception:
            continue
        if len(k) >= 32:
            r30[s] = float(k[-2][4]) / float(k[-32][4]) - 1               # last CLOSED day vs 30 days before
    v = np.array(list(r30.values()))
    cur = dict(disp=float(np.std(v)), runners=float(np.mean(v > 0.20)), med=float(np.median(v)))
    L.append("")
    L.append(f"5  LIVE ({pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; {len(v)} of today's top-40 by prior-month volume, 30-day returns to the last closed day)")
    pct = {}
    for k in cur:
        h = st[k].dropna()
        pct[k] = float((h < cur[k]).mean() * 100)
        L.append(f"   {k:<8} now {cur[k]:+.3f}   2020-2026 median {h.median():+.3f}   today's percentile {pct[k]:.0f}")
    big = sorted(r30.items(), key=lambda x: -x[1])
    L.append("   biggest 30-day movers now: " + ", ".join(f"{s[:-4]} {x * 100:+.0f}%" for s, x in big[:6]) + " | weakest: "
             + ", ".join(f"{s[:-4]} {x * 100:+.0f}%" for s, x in big[-5:]))
    return pct["disp"] > 50, cur


def main():
    if "--build" in sys.argv:
        build()
        return
    if "--bands" in sys.argv:                       # the history the dashboard's FUEL gauge ranks today against (news/mood_now.fuel)
        _, st = timing([])
        h = st.dropna(subset=["runners", "med", "disp"])
        q = {k: [round(float(x), 5) for x in np.percentile(h[k], range(101))] for k in ("runners", "med", "disp")}
        out = dict(made=f"{pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC", source="backtest/convexity.py --bands",
                   span=f"{h.index[0]:%Y-%m-%d} .. {h.index[-1]:%Y-%m-%d}", days=int(len(h)), q=q)
        (ROOT / "news" / "fuel_bands.json").write_text(json.dumps(out, separators=(",", ":")))
        print("wrote news/fuel_bands.json", out["span"], out["days"], "days; runners 33rd/67th pct:", q["runners"][33], q["runners"][67])
        return
    tot, trend = load()
    L = [f"backtest/convexity.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; machine daily account series, 10 orderings, {tot[0].index[0]:%Y-%m-%d} .. {tot[0].index[-1]:%Y-%m-%d}", ""]
    c1 = part1(tot, L)
    c2 = part2(tot, L)
    c3, c4 = part3(tot, L)
    c5, st = timing(L)
    c6 = None
    if "--live" in sys.argv:
        c6, _ = live(st, L)
    L += ["", "REGISTERED PREDICTIONS",
          f"  C1 lumpiness (best 5% of days > 80%, best 10% of months > 60%) -> {'RIGHT' if c1 else 'WRONG'}",
          f"  C2 +20% within 90 days 20-40%, within 365 days > 85% -> {'RIGHT' if c2 else 'WRONG'}",
          f"  C3 a KILL gives up a machine that mostly recovers (>= 50% above start by 180, >= 70% by 365) -> {'RIGHT' if c3 else 'WRONG'}",
          f"  C4 the line is still informative (>= 15 points better at day 180 over the line) -> {'RIGHT' if c4 else 'WRONG'}",
          f"  C5 dispersion explains the same month (>= 0.4) but not the next (|rho| < 0.25 on one half) -> {'RIGHT' if c5 else 'WRONG'}"]
    if c6 is not None:
        L.append(f"  C6 live dispersion above its median -> {'RIGHT' if c6 else 'WRONG'}")
    txt = "\n".join(L)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
