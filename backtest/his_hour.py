"""HE TRADES THE TOP OF THE HOUR - does he trade the RELEASE? And can a bot trade it his way? (2026-10-12)

THE USER (2026-10-12), on "a quarter of his NASDAQ entries come in the first five minutes of an hour, when scheduled US data
and settlements land - but the calendar test showed it doesn't give his direction": "here's your answer but you haven't
checked it properly". Fair: his_calendar.py (s28) counted only HIGH-impact releases, and compared each click with the SAME
CLOCK TIME on other days - which cancels a top-of-the-hour habit by design. It never checked medium / low releases (most of
the :00 slot: JOLTS, factory orders, inventories, UoM sentiment, ISM, auctions), the DIRECTION of the number, the market's
FIRST REACTION between the release and his click, or a bot doing the same at every release.

PART A - HIS CLICKS (his 48 NASDAQ entries, 2026; times as his_headlines.clicks). For each click, the latest scheduled USD
release (ForexFactory, any impact; speeches / testimony / holidays excluded) in the 10 minutes before it.
    A1 TIMING     the share of his clicks with a release in the prior 10 minutes, against (a) moments of the same sittings
                  and (b) the same clock time on his other trading days (the old control)
    A2 REACTION   for those clicks: the NASDAQ move (Exness USTECm 1m mid) from the release minute to his click, and
                  whether his side FOLLOWS it
    A3 NUMBER     his side against the number: ForexFactory's better / worse-for-the-dollar call (abw)
PART B - THE BOT RULE (every scheduled USD release with an Exness or HistData NASDAQ-100 price): k = 1 / 2 / 3 minutes after
    the release, if NASDAQ has moved >= 3bp, enter in that direction (FOLLOW) at the next minute's open; exits (i) his
    shape: +3bp target (~his +7 points at 25,000), no stop, out at 30 minutes; (ii) 5 and (iii) 15 minutes. 1bp a round
    trip (USTECm's spread is 0.8bp). CONTROL: the same rule at the same clock minute on days with NO USD release at that
    minute - the hour without the news. Data: HistData NSXUSD 1m 2010-11 .. 2026-09 (tune = first 60% of events), and
    Exness USTECm 1m 2026 as a check.

REGISTERED BEFORE THE RUN (2026-10-12) - the user's hypothesis, and my expectation beside it
    A1  His clicks have a release in the prior 10 minutes at >= 2x the same-sitting rate. (I expect ~2x: the :00 habit.)
    A2  He FOLLOWS the market's first reaction in >= 65% of those clicks - the hypothesis. (I expect 50-60%: s36 found
        him following the last 1-2 minutes only 44-48% of the time overall.)
    A3  No registered direction (US-good -> NASDAQ up or down is itself ambiguous); reported.
    B1  The bot rule wins the +3bp race in >= 60% of trades (the no-stop shape) but nets under +0.5bp after costs and does
        not pass both halves.
    B2  The same rule on the same clock minutes WITHOUT a release nets ~0 - whatever exists is the release, not the hour.
    C1  (added after Part A's first run showed 9 of his 12 top-of-hour clicks on the side of the hourly candle that had
        just closed - found after looking, so tested where it was not found) PART C: at the top of every New York hour
        10:00-16:00, follow the closed hourly candle (|move| >= 10bp), same exits, NASDAQ-100 2010-2026: nets < 0 after
        1bp on both halves; wins the +3bp race ~88% (the no-stop shape) and ~50% at fixed exits.

RESULT (2026-10-12 14:40 UTC, logs/his_hour.txt)
    CLOCK CHECK: HistData NSXUSD's payroll jump sits at the release minute on 99 of 185 days, within 2 minutes on 148.
    - A1 WRONG - his top-of-the-hour habit is NOT the release slot: only 3 of his 48 NASDAQ clicks came within 10 minutes
      after a USD release of any impact (6%; same-sitting moments 4.0%, 1.55x, p 0.31; the same clock time on his other
      days 9.0%, 0.70x). His 12 top-of-hour clicks sit at 10, 11, 13, 14, 15 and 16:00 New York - 11:00 most (4) - and
      only the two of 2026-02-20 follow a release (10:00 new home sales / UoM).
    - A2 WRONG: on those 3 he followed the market's first reaction once.
    - B1 RIGHT, B2 the same: a bot that follows NASDAQ's first 1-3 minutes after EVERY US release, 2010-2026 (5,158-6,533
      releases), loses -1.19..-1.71bp a trade at every entry and exit, both halves (t -1.4 to -7.6) - exactly what the
      same rule makes at the same clock minutes on days WITHOUT a release (-1.29..-2.00bp). The release adds nothing a
      bot can follow; the +3bp no-stop race wins 87-88% either way (the shape) and loses the cost.
    - C1 RIGHT: 9 of his 12 top-of-hour clicks sided with the hourly candle that had just closed (29 of all 48) - found
      after looking. Tested on 17,036 New York hours 2010-2026: following the closed hourly candle wins 49-51% at fixed
      exits and nets -0.22..-1.02bp a trade on both halves. A coin flip.
    Reading: the user's lead was worth checking properly and it is now checked: the hour is when he sits down, not what
    tells him the side - neither the release, its number, the first reaction, nor the hourly candle carries his direction.

    python -m backtest.his_hour
"""
from __future__ import annotations

import sys
from math import comb
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest import histdata_1m as hd  # noqa: E402
from backtest import mt5_1m  # noqa: E402
from backtest.his_headlines import clicks  # noqa: E402

LOG = ROOT / "logs" / "his_hour.txt"
MIN = 60_000
NOT_RELEASE = r"Speaks|Testifies|Press Conference|Holiday|Bank Holiday|Speech|Hearing|Statement|Minutes|Conference"
TUNE = 0.60


def releases(start="2007-01-01"):
    ff = pd.read_csv(ROOT / "strategy_analysis" / "data" / "fx_macro" / "ff_2007_2026.csv", parse_dates=["utc"])
    u = ff[(ff.currency == "USD") & (ff.utc >= start) & ~ff.name.str.contains(NOT_RELEASE, case=False, na=False)]
    u = u[u.impact.isin(["low", "medium", "high"])]
    g = u.groupby("utc").agg(names=("name", lambda x: "; ".join(x)), impact=("impact", lambda x: max(x, key=["low", "medium", "high"].index)),
                             abw=("abw", lambda x: int(np.sign(sum({1: 1, 2: -1}.get(int(v), 0) for v in x if pd.notna(v))))))
    return g.reset_index()


def price_fn(bars: pd.DataFrame):
    t, o, c = bars.t.to_numpy(np.int64), bars.o.to_numpy(), bars.c.to_numpy()

    def at(ms):
        """the price at ms: the open of the minute starting then, else the last close before it (<= 5 min old)."""
        i = np.searchsorted(t, ms, "left")
        if i < len(t) and t[i] == ms:
            return o[i]
        if i == 0 or ms - t[i - 1] > 6 * MIN:
            return np.nan
        return c[i - 1]
    return at, t, bars.h.to_numpy(), bars.l.to_numpy(), c, o


def binom_ge(k, n, p):
    return float(sum(comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k, n + 1)))


def part_a(lines):
    C = clicks()
    N = C[C.kind == "NASDAQ"].reset_index(drop=True)
    R = releases("2025-12-01")
    rt = (R.utc.astype("datetime64[ns]").astype("int64") // 10**9).to_numpy()
    def prior_release(ts):
        i = np.searchsorted(rt, ts, "right") - 1
        return i if i >= 0 and ts - rt[i] <= 600 else -1
    ck = (N.utc.astype("int64") // 10**9).to_numpy()
    allclk = (C.utc.astype("int64") // 10**9).to_numpy()
    ctrl = np.unique(np.array([t + o for t in allclk for o in range(-1200, 1201, 30) if np.min(np.abs(allclk - (t + o))) >= 60]))
    his = np.array([prior_release(t) >= 0 for t in ck])
    base = np.array([prior_release(t) >= 0 for t in ctrl])
    # same clock time on his other NASDAQ days
    days = sorted(set(N.utc.dt.normalize()))
    same = []
    for t in N.utc:
        for d in days:
            if d != t.normalize():
                u = int((d + (t - t.normalize())).value // 10**9)
                same.append(prior_release(u) >= 0)
    same = np.array(same)
    k = int(his.sum())
    lines.append(f"PART A - his {len(N)} NASDAQ clicks; USD scheduled releases (any impact, no speeches) from ForexFactory")
    lines.append(f"  A1 a release in the 10 min before: his {k}/{len(N)} = {his.mean() * 100:.0f}% | same-sitting moments "
                 f"{base.mean() * 100:.1f}% ({his.mean() / base.mean():.2f}x, p {binom_ge(k, len(N), base.mean()):.4f}) | same clock time, "
                 f"his other days {same.mean() * 100:.1f}% ({his.mean() / same.mean():.2f}x, p {binom_ge(k, len(N), same.mean()):.3f})")
    bars = mt5_1m.load("USTECm")
    at, *_ = price_fn(bars)
    rows = []
    for i, (t, side, net) in enumerate(zip(ck, N.side, N.net)):
        j = prior_release(t)
        if j < 0:
            continue
        r_ms = int(rt[j]) * 1000
        p_rel, p_clk = at(r_ms), at((int(t) // 60) * 60 * 1000)          # release minute's open, the click minute's open
        mv = p_clk - p_rel
        s = 1 if side == "BUY" else -1
        rows.append(dict(click=N.utc[i], rel=R.utc[j], names=R.names[j][:70], impact=R.impact[j], abw=R.abw[j],
                         secs=int(t - rt[j]), move=mv, side=s, follow=np.sign(mv) == s if abs(mv) >= 1 else np.nan, net=net))
    D = pd.DataFrame(rows)
    fol = D.follow.dropna()
    lines.append(f"  A2 his side FOLLOWS the NASDAQ move from the release to his click (>= 1 point): {int(fol.sum())}/{len(fol)} = "
                 f"{fol.mean() * 100:.0f}% (binomial p vs 50%: {binom_ge(int(fol.sum()), len(fol), 0.5):.3f})")
    ab = D[D.abw != 0]
    lines.append(f"  A3 his side vs the number (FF better/worse for USD): BUY NASDAQ on US-better {int(((ab.abw > 0) & (ab.side > 0)).sum())}, "
                 f"SELL on US-better {int(((ab.abw > 0) & (ab.side < 0)).sum())}, BUY on US-worse {int(((ab.abw < 0) & (ab.side > 0)).sum())}, "
                 f"SELL on US-worse {int(((ab.abw < 0) & (ab.side < 0)).sum())} ({len(ab)} with a call)")
    lines.append(f"  {'click (UTC)':20} {'release':9} {'s after':>7} {'impact':7} {'move since':>10} side  follow  result  release")
    for r in D.itertuples():
        lines.append(f"  {r.click:%Y-%m-%d %H:%M:%S} {r.rel:%H:%M} {r.secs:7d} {r.impact:7} {r.move:+10.2f} {'BUY ' if r.side > 0 else 'SELL'}  "
                     f"{'yes' if r.follow is True else ('no' if r.follow is False else '-'):5} {r.net:+8.2f}  {r.names}")
    lines.append("")
    return his.mean() / base.mean(), (fol.mean() if len(fol) else np.nan)


def part_b(lines, bars: pd.DataFrame, label: str, start: str, end: str, cost_bp=1.0):
    at, t, h, l, c, o = price_fn(bars)
    R = releases(start)
    R = R[R.utc < end].reset_index(drop=True)
    rel_ms = set((R.utc.astype("datetime64[ns]").astype("int64") // 10**6).tolist())
    # control: the same clock minutes on days with no USD release at that minute
    ctrl_ms = []
    for r in R.itertuples():
        for dd in (-7, 7, -14, 14):
            u = (r.utc + pd.Timedelta(days=dd))
            ms = int(u.value // 10**6)
            if ms not in rel_ms and u.dayofweek < 5:
                ctrl_ms.append(ms)
    sets = {"RELEASE": (R.utc.astype("datetime64[ns]").astype("int64") // 10**6).to_numpy(), "CONTROL (same minute, no release)": np.array(ctrl_ms)}
    res = {}
    for nm, ev in sets.items():
        for k in (1, 2, 3):
            out = {"race": [], "x5": [], "x15": [], "ts": []}
            for ms in ev:
                p0, pk = at(ms), at(ms + k * MIN)
                if not (np.isfinite(p0) and np.isfinite(pk)) or abs(pk / p0 - 1) < 3e-4:
                    continue
                s = np.sign(pk - p0)
                i = np.searchsorted(t, ms + k * MIN, "left")
                if i >= len(t) or t[i] != ms + k * MIN:
                    continue
                e = o[i]
                j30 = np.searchsorted(t, ms + (k + 30) * MIN, "left")
                hh, ll = h[i:j30], l[i:j30]
                tgt = e * (1 + s * 3e-4)
                hit = np.flatnonzero((hh >= tgt) if s > 0 else (ll <= tgt))
                race = 3e-4 if len(hit) else s * (c[j30 - 1] / e - 1)
                out["race"].append(race)
                for x, key in ((5, "x5"), (15, "x15")):
                    px = at(ms + (k + x) * MIN)
                    out[key].append(s * (px / e - 1) if np.isfinite(px) else np.nan)
                out["ts"].append(ms)
            df = pd.DataFrame(out).dropna()
            if len(df) < 20:
                continue
            cut = df.ts.iloc[int(len(df) * TUNE)]
            for key in ("race", "x5", "x15"):
                net = df[key] * 1e4 - cost_bp
                a, b = net[df.ts < cut], net[df.ts >= cut]
                tt = lambda y: y.mean() / (y.std(ddof=1) / np.sqrt(len(y))) if len(y) > 2 else np.nan  # noqa: E731
                res[(nm, k, key)] = dict(n=len(net), mean=net.mean(), won=(df[key] > 0).mean(), tu=a.mean(), t_tu=tt(a),
                                         ho=b.mean(), t_ho=tt(b))
    lines.append(f"PART B - {label}: FOLLOW the first k minutes' NASDAQ reaction (>= 3bp), {cost_bp:.1f}bp a round trip; net bp a trade "
                 f"(won %) | tune / holdout (t)")
    for (nm, k, key), v in res.items():
        lines.append(f"  {nm:34} k={k} {key:5} n {v['n']:5} | {v['mean']:+6.2f}bp ({v['won'] * 100:3.0f}%) | {v['tu']:+6.2f} "
                     f"({v['t_tu']:+.1f}) / {v['ho']:+6.2f} ({v['t_ho']:+.1f})")
    lines.append("")
    return res


def part_c(lines, bars: pd.DataFrame, cost_bp=1.0):
    at, t, h, l, c, o = price_fn(bars)
    days = pd.date_range("2010-12-01", "2026-09-30", freq="B")
    out = {"race": [], "x5": [], "x15": [], "x60": [], "ts": []}
    for d in days:
        for hh_ in range(10, 17):
            u = pd.Timestamp(f"{d:%Y-%m-%d} {hh_:02d}:00", tz="America/New_York").tz_convert("UTC")
            ms = int(u.value // 10**6)
            p0, pm = at(ms), at(ms - 60 * MIN)
            if not (np.isfinite(p0) and np.isfinite(pm)) or abs(p0 / pm - 1) < 1e-3:
                continue
            sd = np.sign(p0 - pm)
            i = np.searchsorted(t, ms, "left")
            if i >= len(t) or t[i] != ms:
                continue
            e = o[i]
            j30 = np.searchsorted(t, ms + 30 * MIN, "left")
            tgt = e * (1 + sd * 3e-4)
            hit = np.flatnonzero((h[i:j30] >= tgt) if sd > 0 else (l[i:j30] <= tgt))
            out["race"].append(3e-4 if len(hit) else sd * (c[j30 - 1] / e - 1))
            for x, key in ((5, "x5"), (15, "x15"), (60, "x60")):
                px = at(ms + x * MIN)
                out[key].append(sd * (px / e - 1) if np.isfinite(px) else np.nan)
            out["ts"].append(ms)
    df = pd.DataFrame(out).dropna()
    cut = df.ts.iloc[int(len(df) * TUNE)]
    lines.append(f"PART C - follow the hourly candle that just closed, at every New York hour 10:00-16:00 (|move| >= 10bp), "
                 f"HistData NASDAQ-100 2010-2026, {cost_bp:.1f}bp a round trip; {len(df)} trades")
    res = {}
    for key in ("race", "x5", "x15", "x60"):
        net = df[key] * 1e4 - cost_bp
        a, b = net[df.ts < cut], net[df.ts >= cut]
        tt = lambda y: y.mean() / (y.std(ddof=1) / np.sqrt(len(y)))  # noqa: E731
        res[key] = (net.mean(), (df[key] > 0).mean(), a.mean(), tt(a), b.mean(), tt(b))
        lines.append(f"  {key:5} {net.mean():+6.2f}bp a trade ({(df[key] > 0).mean() * 100:3.0f}% won) | tune {a.mean():+6.2f} ({tt(a):+.1f}) / "
                     f"holdout {b.mean():+6.2f} ({tt(b):+.1f})")
    lines.append("")
    return res


def main():
    lines = [f"backtest/his_hour.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC", ""]
    # clock check for HistData NASDAQ-100: the biggest 1-min move on payroll days must sit at the release minute
    nsx = pd.read_parquet(hd.OUT / "NSXUSD.parquet")
    R = releases("2011-01-01")
    nfp = R[R.names.str.contains("Non-Farm Employment Change") & ~R.names.str.contains("ADP")]
    tt_, cc = nsx.t.to_numpy(np.int64), nsx.c.to_numpy()
    offs = []
    for u in nfp.utc:
        ms = int(pd.Timestamp(u).value // 10**6)
        i0, i1 = np.searchsorted(tt_, ms - 30 * MIN), np.searchsorted(tt_, ms + 30 * MIN)
        if i1 - i0 > 40:
            offs.append(int((tt_[i0 + 1 + int(np.argmax(np.abs(np.diff(cc[i0:i1]))))] - ms) // MIN))
    lines.append(f"CLOCK CHECK (HistData NSXUSD): minute of the biggest 1-min move on {len(offs)} payroll days: "
                 f"{pd.Series(offs).value_counts().head(5).to_dict()}")
    lines.append("")
    ratio, follow = part_a(lines)
    rb = part_b(lines, nsx, "HistData NASDAQ-100 1m", "2010-12-01", "2026-10-01")
    part_b(lines, mt5_1m.load("USTECm"), "Exness USTECm 1m (2026 check)", "2026-01-01", "2026-10-10", cost_bp=0.8)
    rc = part_c(lines, nsx)
    lines.append("REGISTERED PREDICTIONS")
    lines.append(f"  A1 release in the prior 10 min at >= 2x the same-sitting rate: {ratio:.2f}x -> {'RIGHT' if ratio >= 2 else 'WRONG'}")
    lines.append(f"  A2 he follows the first reaction >= 65%: {follow * 100:.0f}% -> {'RIGHT (the hypothesis holds)' if follow >= 0.65 else 'WRONG (the hypothesis fails)'}")
    best = max(((v["mean"], k) for k, v in rb.items() if k[0] == "RELEASE"), default=(np.nan, None))
    b1 = all(not (v["tu"] > 0 and v["ho"] > 0 and v["t_tu"] >= 2 and v["t_ho"] >= 2) for k, v in rb.items() if k[0] == "RELEASE")
    lines.append(f"  B1 no RELEASE rule passes both halves: {b1}; best {best[1]} {best[0]:+.2f}bp -> {'RIGHT' if b1 else 'WRONG'}")
    ctrl = [v["mean"] for k, v in rb.items() if k[0].startswith("CONTROL")]
    lines.append(f"  B2 control (no release) nets ~0: " + ", ".join(f"{x:+.2f}" for x in ctrl))
    c1 = all(v[0] < 0 for v in rc.values()) and not any(v[2] > 0 and v[4] > 0 and v[3] >= 2 and v[5] >= 2 for v in rc.values())
    lines.append(f"  C1 following the closed hourly candle nets < 0 at every exit: " + ", ".join(f"{k} {v[0]:+.2f}" for k, v in rc.items())
                 + f" -> {'RIGHT' if c1 else 'WRONG'}")
    txt = "\n".join(lines)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt.encode("ascii", "replace").decode())


if __name__ == "__main__":
    main()
