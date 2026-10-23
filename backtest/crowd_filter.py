"""THE CROWD AS A FILTER ON THE MACHINE'S OWN ENTRIES - learning from the live losses without cutting the books (2026-10-23)

THE USER (2026-10-23): "there must be something you should learn from why they are down, and maybe do something about it
without butchering our gains". The live record (both accounts, 194 positions, the crowd at entry from Binance's archive;
the closed trades' entry taken as the day before their close): longs lost in every crowd bucket - the alt sell-off;
shorts on coins the crowd was most LONG made +$4.09, shorts on coins it was most SHORT lost -$5.91; trend longs on
crowd-long coins -$16.38. The crowd book (news/positioning_hist.py) found the most-shorted quarter beats the most-longed.
So every book stays; each is only stopped from ENTERING on the wrong side of the crowd:
  TL   trend book: no new LONG on a coin in the crowd's most-long quarter
  TS   trend book: no new SHORT on a coin in the crowd's most-short quarter
  DL   daily book: no new LONG in the most-long quarter
  MS   MN blend: no SHORT leg in the most-short quarter (the next-weakest name takes its place)
  ML   MN blend: no LONG leg in the most-long quarter
  ALL  all five
CROWD  Binance's archive (positioning_hist.py's cache, every day 2022-01 .. 2026-09): each coin's long / short account
       ratio at the day's last row, ranked among the PIT top-40 that day; a coin without a reading is never filtered.
       Read on the day BEFORE a trend entry; on a daily bar's own label day (the bar closes after that day's last row);
       on the MN rebalance's close day.
SCORED the deployed machine (machine_fixes.py F1+F2) with ONE book changed at a time, on the crowd's dates only
       (2022-01-25 .. 2024-08-28 and 2024-08-29 .. 2026-09), $300: paired per ordering (% change in the typical year,
       wins of 10), worst month, fall; and the BET-SMALLER line (the unchanged machine scaled to the variant's fall).
       Each unfiltered rebuild reproduces the deployed book's series (asserted).
PASS   typical year up on BOTH spans with 8+/10 orderings each, worst month not worse by more than 1 point, and above the
       bet-smaller line on both spans.

REGISTERED BEFORE THE RUN (2026-10-23)
  G1 MS passes (shorting the crowd's favourite shorts is where the squeezes hit).
  G2 TL raises the typical year on 2024-26 but costs it on 2022-24 (bull runs are crowded long; skipping them costs).
  G3 DL and ML are small: |change| < 5% on both spans.
  G4 ALL does not pass (the long filters cost the bull runs more than the short filters save).

RESULT (2026-10-23, logs/crowd_filter.txt; BACKTEST) - DEAD: no filter passes on both spans. G3 G4 RIGHT; G1 G2 WRONG.
  Typical year vs the deployed machine, paired (2022-24 / 2024-26):
    TL  trend longs off crowd-long coins   -3.0% / -35.3% (0/10)  worst month -24.0% vs -18.2% on 2022-24
    TS  trend shorts off crowd-short coins -0.3% / -0.5%
    DL  daily longs off crowd-long coins   -3.5% (2/10) / +4.5% (8/10)
    MS  MN shorts off crowd-short coins    +1.3% / -3.3%
    ML  MN longs off crowd-long coins      +0.2% / +2.4% (9/10)
    ALL                                    +3.6% / -32.1%
  The crowded-long coins ARE the bull runners: the trend book's best trades start where everyone is already long, so
  keeping it out of them costs the year. The live two weeks (shorts on crowd-short coins lost, longs on crowd-long coins
  lost) were the alt sell-off, not a rule. The crowd's information pays as its OWN balanced long / short book
  (backtest/crowd_combo.py: +16..+34% to the typical year at x0.5, same worst month), not as a veto on the machine's
  direction books.

    python -m backtest.crowd_filter
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

LOG = ROOT / "logs" / "crowd_filter.txt"
CACHE = ROOT / "logs" / "daily_combos_cache" / "crowd_filter.pkl"
SPANS = (("2022-01 .. 2024-08", "2022-01-25", "2024-08-29"), ("2024-08 .. 2026-09", "2024-08-29", None))
LO_Q, HI_Q = 0.25, 0.75
ALIAS = {"SHIBUSDT": "1000SHIBUSDT", "PEPEUSDT": "1000PEPEUSDT"}


def crowd_rank() -> pd.DataFrame:
    """day x coin: the crowd ratio's percentile rank among that day's coins (positioning_hist's cache, all 7 weekdays)."""
    from news import positioning_hist as ph
    F = pd.read_parquet(ph.CACHE).dropna(subset=["crowd"])
    F["day"] = pd.to_datetime(F.day)
    return F.pivot_table(index="day", columns="sym", values="crowd").rank(axis=1, pct=True)


class Crowd:
    def __init__(self, P: pd.DataFrame):
        self.P = P
        self.days = P.index.as_unit("ns").asi8
        self.col = {c: i for i, c in enumerate(P.columns)}
        self.V = P.to_numpy(float)

    def at(self, sym: str, day_ns: int):
        """The rank on the calendar day containing day_ns (exact day only), or NaN."""
        j = self.col.get(ALIAS.get(sym, sym))
        if j is None:
            return np.nan
        d = day_ns - day_ns % 86_400_000_000_000
        i = np.searchsorted(self.days, d)
        return self.V[i, j] if i < len(self.days) and self.days[i] == d else np.nan


# ------------------------------------------------------------------ the books, rebuilt with an entry filter

def trend(cr: Crowd | None, longs: bool, shorts: bool):
    import backtest.dd_fixes as Dd
    from backtest import machine_combos as mc
    from backtest.bar_phase import rows_for_phase
    from backtest.bull_boost import regimes
    from backtest.worst_month import TCACHE
    shrink = pickle.loads(TCACHE.read_bytes())
    bear = regimes()[1000]
    bn, bv = pd.DatetimeIndex(bear.index).as_unit("ns").asi8, bear.to_numpy(bool)
    trows = Dd.decompose(rows_for_phase(0, tight=True, time_stop=(100, 2.0), max_units=7))
    day = 86_400_000_000_000

    def gate(r, t, ctx):
        if cr is None:
            return 1.0
        p = cr.at(r["coin"], int(t) - day)                       # the day before the entry
        if not np.isfinite(p):
            return 1.0
        if longs and r["side"] == "long" and p >= HI_Q:
            return 0.0
        if shorts and r["side"] == "short" and p <= LO_Q:
            return 0.0
        return 1.0
    out = {}
    for sd in mc.SEEDS:
        r = Dd.sim(trows, bn, bv, sd, lev=6.25, size_fn=Dd.anchor(21), gate_fn=gate).pct_change().fillna(0.0)
        s = shrink[("shrink", sd)]
        out[sd] = pd.Series(np.where(r > 0, s * r, r), index=r.index)
    return out


def daily(cr: Crowd | None):
    from backtest import daily_combos as dc
    from backtest import machine_combos as mc
    orig = dc.panel

    def panel_with_sym(off):
        PN = orig(off)
        for s, P in PN.items():
            P["sym"] = s
        return PN

    def entry(P):
        S = pd.Series(P["c"])
        m = S.rolling(dc.BASE["n"]).mean().to_numpy()
        sd = S.rolling(dc.BASE["n"]).std(ddof=0).to_numpy()
        ent = np.nan_to_num(P["c"] > m + dc.BASE["k"] * sd).astype(bool)
        if cr is not None:
            t = P["t"].astype("int64")
            hi = np.array([cr.at(P["sym"], int(x)) >= HI_Q for x in t])  # NaN >= q is False: unfiltered
            ent &= ~hi
        return ent
    dc.panel = panel_with_sym
    try:
        T = {off: dc.gen(off, dict(dc.BASE, mean_n=20, entry=entry)) for off in dc.PHASES}
    finally:
        dc.panel = orig
    return {sd: 0.5 * dc.curve(T[dc.PHASES[sd % 3]], dc.allocate(T[dc.PHASES[sd % 3]], sd), dc.PHASES[sd % 3]).pct_change()
            for sd in mc.SEEDS}


def scored(score_mat, start, cr: Crowd | None, shorts: bool, longs: bool, short_stop=0.5):
    """moderate_retests.scored_run (stop="short_only") with crowd exclusions on each leg; unfiltered it reproduces it."""
    from backtest import mn_combos as m
    Dd = m.ohl()
    idx, X_, Fx, ff = Dd["idx"], Dd["X"], Dd["Fx"], Dd["ff"]
    hold, look, frac = 7, 30, 0.1
    rows, pl_, ps_ = [], set(), set()
    for i in range(look + 1 + start, len(idx) - hold - 1, hold):
        t0 = idx[i]
        ok = (Dd["Em"][Dd["months"][i]] & ((t0.value - Dd["fv"]) // 86_400_000_000_000 >= m.MIN_AGE_D)
              & np.isfinite(X_[i]) & np.isfinite(X_[i - look]))
        if ok.sum() < 20:
            continue
        cand = np.flatnonzero(ok)
        past = score_mat[i, cand]
        k = max(int(len(cand) * frac), 3)
        order = cand[np.argsort(np.where(np.isnan(past), np.inf, past), kind="stable")]
        osh, olo = order, order
        if cr is not None:
            p = np.array([cr.at(Dd["cols"][x], t0.value) for x in order])
            if shorts:
                osh = order[~(p <= LO_Q)]
            if longs:
                olo = order[~(p >= HI_Q)]
        sh, lo = osh[:k], olo[-k:]
        fwd = ff[i + hold] / X_[i] - 1
        fwd = fwd.copy()
        for x in sh:
            lvl = X_[i, x] * (1 + short_stop)
            for dd in range(i + 1, i + hold + 1):
                if np.isfinite(Dd["Hi"][dd, x]) and Dd["Hi"][dd, x] >= lvl:
                    fwd[x] = max(Dd["Op"][dd, x], lvl) / X_[i, x] - 1
                    break
        fnd = Fx[i + 1:i + hold + 1].sum(axis=0)
        gross = 0.5 * fwd[lo].mean() - 0.5 * fwd[sh].mean()
        carry = 0.5 * (-fnd[lo].mean()) + 0.5 * fnd[sh].mean()
        L_, S_ = {Dd["cols"][x] for x in lo}, {Dd["cols"][x] for x in sh}
        cost = m.FEE * min((len(L_ ^ pl_) + len(S_ ^ ps_)) / (4 * k), 1.0)
        pl_, ps_ = L_, S_
        rows.append((t0 + pd.Timedelta(days=hold), gross + carry - cost))
    return pd.Series([r for _, r in rows], index=pd.DatetimeIndex([t for t, _ in rows])).groupby(level=0).sum()


def mn_blend(cr: Crowd | None, shorts: bool, longs: bool):
    from backtest import machine_combos as mc
    from backtest import mn_combos as m
    D = m.data()
    C = pd.DataFrame(D["X"])
    d = C.diff()
    up = d.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    rsi = (100 - 100 / (1 + up / dn.replace(0, np.nan))).to_numpy()
    mom = D["X"] / np.r_[np.full((30, D["X"].shape[1]), np.nan), D["X"][:-30]] - 1
    out = {}
    for sd in mc.SEEDS:
        o = sd % 7
        if o not in out:
            out[o] = (scored(mom, o, cr, shorts, longs), scored(rsi, o, cr, shorts, longs))
    return out


# ------------------------------------------------------------------ the machine with one book swapped

def main():
    from backtest import machine_combos as mc
    from backtest.all_books import machine_books, ndx_dip, news_book
    from backtest.machine import summary
    from backtest.machine_fixes import CACHE as MCACHE
    M = pickle.loads(MCACHE.read_bytes()) if MCACHE.exists() else machine_books()
    news, ndx = news_book(), ndx_dip()
    cr = Crowd(crowd_rank())
    B = pickle.loads(CACHE.read_bytes()) if CACHE.exists() else {}
    jobs = {"trend0": lambda: trend(None, False, False), "TL": lambda: trend(cr, True, False),
            "TS": lambda: trend(cr, False, True), "TLS": lambda: trend(cr, True, True),
            "daily0": lambda: daily(None), "DL": lambda: daily(cr),
            "mn0": lambda: mn_blend(None, False, False), "MS": lambda: mn_blend(cr, True, False),
            "ML": lambda: mn_blend(cr, False, True), "MSL": lambda: mn_blend(cr, True, True)}
    for k, f in jobs.items():
        if k not in B:
            print(f"building {k}", flush=True)
            B[k] = f()
            CACHE.parent.mkdir(parents=True, exist_ok=True)
            CACHE.write_bytes(pickle.dumps(B))

    def series(name, sd, x):
        r = lambda s: s.reindex(x.index).fillna(0.0)  # noqa: E731
        tr = {"TL": "TL", "TS": "TS", "ALL": "TLS"}.get(name, "trend0")
        dl = "DL" if name in ("DL", "ALL") else "daily0"
        mb = {"MS": "MS", "ML": "ML", "ALL": "MSL"}.get(name, "mn0")
        o = sd % 7
        mn = 0.5 * r(B[mb][o][0]) + 0.5 * r(B[mb][o][1])
        return (r(B[tr][sd]) + x.sleeve + r(B[dl][sd]) + r(news) + r(ndx) + mn + x.carry + x.capit2 + x.bids,
                (r(B[tr][sd]), r(B[dl][sd]), mn))

    chk = []
    for sd, x in zip(mc.SEEDS, M):                              # the unfiltered rebuilds reproduce the deployed books
        _, (t, dl, mn) = series("BASE", sd, x)
        chk.append(max((t - x.trend).abs().max(), (dl - x.daily).abs().max(), (mn - x.mn_blend).abs().max()))
    assert max(chk) < 1e-9, f"an unfiltered rebuild does not reproduce the deployed book ({max(chk):.2e})"

    names = ("BASE", "TL", "TS", "DL", "MS", "ML", "ALL")
    first = pd.Timestamp(SPANS[0][1])
    L = [f"backtest/crowd_filter.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; the deployed machine, one book's entries "
         f"filtered by the crowd (Binance archive rank, top-40); unfiltered rebuilds match the deployed books to {max(chk):.0e}; "
         f"10 orderings, $300, BACKTEST", "",
         f"   {'variant':<8}{'span':>20}{'typical':>10}{'bad':>9}{'worst mo':>10}{'fall':>6}{'mo up':>7}{'vs deployed, paired':>24}"
         f"{'deployed at same fall':>24}  pass"]
    R = {}
    for lab, a, b in SPANS:
        cut = lambda xs: [s[(s.index >= a) & ((s.index < b) if b else True)] for s in xs]  # noqa: E731
        base = cut([series("BASE", sd, x)[0] for sd, x in zip(mc.SEEDS, M)])
        s0 = summary(base)
        per0 = np.array([summary([x])["typ"] for x in base])
        for nm in names:
            xs = base if nm == "BASE" else cut([series(nm, sd, x)[0] for sd, x in zip(mc.SEEDS, M)])
            s = summary(xs)
            per = np.array([summary([x])["typ"] for x in xs])
            d = (per / per0 - 1) * 100
            lo, hi = 0.3, 3.0
            for _ in range(40):
                mm = (lo + hi) / 2
                lo, hi = (mm, hi) if summary([x * mm for x in base])["dd"] < s["dd"] else (lo, mm)
            line = summary([x * mm for x in base])["typ"]
            R[(nm, lab)] = dict(pair=d.mean(), wins=int((d > 0).sum()), wm=s["wm"], wm0=s0["wm"], typ=s["typ"], line=line)
            ok = nm != "BASE" and d.mean() > 0 and (d > 0).sum() >= 8 and s["wm"] >= s0["wm"] - 1 and s["typ"] > line
            R[(nm, lab)]["ok"] = ok
            pair = "" if nm == "BASE" else f"{d.mean():+.1f}% +- {d.std(ddof=1) / np.sqrt(len(d)):.1f}, {int((d > 0).sum())}/10"
            L.append(f"   {nm:<8}{lab:>20} ${s['typ']:>8,.0f} ${s['bad']:>7,.0f}{s['wm']:>+9.1f}%{s['dd']:>5.0f}%{s['up']:>6.0f}%"
                     f"{pair:>24}{'' if nm == 'BASE' else f'x{mm:.2f}: ${line:,.0f}':>24}  {'' if nm == 'BASE' else ('yes' if ok else 'no')}")
        L.append("")
    sp = [s[0] for s in SPANS]
    passes = [nm for nm in names[1:] if all(R[(nm, s)]["ok"] for s in sp)]
    g1 = "MS" in passes
    g2 = R[("TL", sp[1])]["pair"] > 0 and R[("TL", sp[0])]["pair"] < 0
    g3 = all(abs(R[(nm, s)]["pair"]) < 5 for nm in ("DL", "ML") for s in sp)
    g4 = "ALL" not in passes
    L += [f"PASS on both spans: {passes or 'none'}", "", "REGISTERED PREDICTIONS",
          f"  G1 MS passes -> {'RIGHT' if g1 else 'WRONG'}",
          f"  G2 TL helps 2024-26, costs 2022-24: {[(s, round(R[('TL', s)]['pair'], 1)) for s in sp]} -> {'RIGHT' if g2 else 'WRONG'}",
          f"  G3 DL and ML |change| < 5%: {[(nm, s, round(R[(nm, s)]['pair'], 1)) for nm in ('DL', 'ML') for s in sp]} -> "
          f"{'RIGHT' if g3 else 'WRONG'}",
          f"  G4 ALL does not pass -> {'RIGHT' if g4 else 'WRONG'}"]
    txt = "\n".join(L)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
