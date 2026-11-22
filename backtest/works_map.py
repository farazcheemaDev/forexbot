"""THE MAP OF WHAT WORKS: every book that survived, on one calendar, cut by market state, and how they connect (2026-11-15)

THE USER (2026-11-15): "create a map or mapping of all the things that works - create mapping, connect them, align them - till this
day whatever works, then tell me your findings". all_books.py (2026-10-17) connected nine books by monthly correlation; this file
adds the books that came after it (crowd squeeze, RSI-80 momentum, NASDAQ noise), cuts every book by the MARKET STATE of each day,
and measures which signal lines up with which book. A map, not a test: nothing here changes a book or passes a candidate.

THE BOOKS (daily return as a share of the account, at the weight each runs at; backtest)
  machine (the final machine, as deployed on paper): trend (triple, guard 6.25x, gains shrunk 3x for hindsight), mn_blend, carry
    x0.5, sleeve, bids (crash bids, capped), daily x0.5, capit2 (2x), news, ndx_dip   - logs/daily_combos_cache/alt_bear_books.pkl
    (the 10 orderings; their MEAN is used here) + all_books.news_book / ndx_dip
  outside it: crowd (crowd_combo.crowd_daily, x1.0 as in the fresh account), rsi80 (rsi80_overlap.daily_book, 1% risk a trade,
    the original + new perps), noise (NASDAQ noise momentum, 1x, fx_intraday_pub at Exness costs)
THE STATES (each day, from closes through the day before - knowable)
  btc     bull / chop / bear (market_neutral.btc_regime: BTC vs its 50-day average and that average's 20-day slope)
  fuel    LOW / MID / HIGH: the share of the point-in-time top-40 alts up over 20% in 30 days, against its own past thirds
          (runner_gate.runner_state; the dashboard's gauge)
  bleed   the median top-40 alt down 15% or more over 30 days (the live tape of October-November 2026)
REPORTED
  1. each book alone: start, annualised mean (mean day x 365, % of the account), Sharpe, active days, the halves (machine.CUT)
  2. the STATE MAP: each book's annualised mean in each state, and whether it is positive on both halves there
  3. weekly correlation (pairwise, from the later book's start)
  4. the machine's worst and best 10% of weeks: what each book did in them
  5. signal -> book: the fuel share and the BTC trend (close / 50-day average) against each book's NEXT 30 days (Spearman, by half)

EXPECTED BEFORE THE RUN (2026-11-15; a map, so these are expectations, not a pass rule)
  W1 Only the trend book depends heavily on bull days; in CHOP the machine's annualised mean is the lowest of the three BTC states and
     at least three books are positive there.
  W2 Every weekly correlation between two books is under +0.40.
  W3 In the machine's worst 10% of weeks the trend book is the biggest loser and at least three books are positive on average.
  W4 The fuel share predicts the trend book's next 30 days on both halves (rho > 0); no other book has |rho| > 0.15 with the same sign
     on both halves.
  W5 The machine earns less than half as much (annualised) on LOW-fuel days as on HIGH-fuel days.

RESULT (2026-11-15, logs/works_map.txt, logs/works_map.json): THREE FAMILIES, EACH OWNING A MARKET. Weekly correlation between books is
low (highest daily ~ rsi80 +0.43 - over the +0.40 line, so W2 wrong by that pair - then mn ~ crowd +0.38); between families +0.04..+0.19 (post hoc grouping:
MOMENTUM = trend, daily, rsi80; FORCED FLOW = sleeve, capit2, news, crowd, bids; NEUTRAL / CARRY = mn, carry, ndx_dip, noise).
Momentum earns when alts run (fuel HIGH +1,324%/yr annualised mean, % of the account at machine weight) and loses in BTC bears (-103%)
and deep alt bleeds (-31%); forced flow is the mirror (bear +174%, deep bleed +192%); neutral is steady except mn in a deep bleed
(-31%). The machine is positive on both halves in every BTC state (W1 wrong: bear, not chop, is its weakest; 11 of 12 books earn in
chop) and its ONE losing state is BTC bull + fuel LOW: 75 days in 10 short episodes, -22.6% summed, trend -33.5%, the other books
+10.9%. Fuel, BTC vs its 50-day and the alt median predict trend and the machine's next 30 days on both halves (rho +0.21..+0.45) and
no other book (W4 right). In the worst 10% of weeks trend is the loser (-7.0% a week) and bids, capit2 and crowd are positive (W3
right). LOW-fuel days earn far under half of HIGH-fuel days (W5 right). POST HOC: the live tape (2026-10..11: BTC bull + fuel LOW,
then a -33% alt bleed under a chop label) is the map's worst corner; in deep bleeds (331 days) the machine still earned +125%/yr,
carried by capit2 +85%, sleeve +55%, crowd +54%, news +23%, while mn (-31%) and daily (-16%) lost - the two biggest live losers.
Tests 6 (9 of 9 planted bugs caught after four test gaps were closed); control survived.

    python -m backtest.works_map            (builds the series once into logs/works_map_series.pkl, ~10 minutes; then seconds)
    python -m backtest.works_map --rebuild
"""
from __future__ import annotations

import json
import pickle
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

LOG = ROOT / "logs" / "works_map.txt"
SER = ROOT / "logs" / "works_map_series.pkl"
OUT = ROOT / "logs" / "works_map.json"
MACHINE = ["trend", "mn_blend", "carry", "sleeve", "bids", "daily", "capit2", "news", "ndx_dip"]
OUTSIDE = ["crowd", "rsi80", "noise"]
ALL = MACHINE + OUTSIDE
CUT = pd.Timestamp("2024-08-29")                    # machine.CUT


# ---------------------------------------------------------------- the series and the states (built once)

def build():
    from backtest import all_books as ab
    from backtest import crowd_combo as cc
    from backtest import rsi80_overlap as ro
    from backtest.fx_intraday_pub import INSTR, SLIP, noise, session
    from backtest.market_neutral import btc_regime, load_panel
    from backtest.runner_gate import runner_state
    M = pickle.loads((ROOT / "logs" / "daily_combos_cache" / "alt_bear_books.pkl").read_bytes())
    idx = M[0].index
    mean = sum(x[ab.BOOKS] for x in M) / len(M)
    S = pd.DataFrame({b: mean[b] for b in ab.BOOKS}, index=idx)
    S["news"] = ab.news_book().reindex(idx).fillna(0.0)
    S["ndx_dip"] = ab.ndx_dip().reindex(idx).fillna(0.0)
    S["crowd"] = cc.crowd_daily()[0].reindex(idx).fillna(0.0)
    X = pd.read_pickle(ro.TRADES)
    S["rsi80"] = ro.daily_book(X[X.src.isin(["OLD", "NEW-PERP"])], idx)
    A, dates, prev = session("NASDAQ")
    g, _, n = noise(A, prev)
    S["noise"] = pd.Series(g - (INSTR["NASDAQ"][4] + SLIP) / 1e4 * n, index=pd.DatetimeIndex(dates)).reindex(idx).fillna(0.0)
    C, _, first = load_panel()
    C.index = C.index.astype("datetime64[ns]")
    st = pd.DataFrame(index=idx)
    st["btc"] = btc_regime(C).reindex(idx).ffill()
    b = C["BTCUSDT"]
    st["btc_gap"] = (b / b.rolling(50).mean() - 1).shift(1).reindex(idx).ffill()
    share, low, high = runner_state()
    st["fuel_share"] = share.reindex(idx)
    st["fuel"] = np.where(low.reindex(idx).fillna(False), "LOW", np.where(high.reindex(idx).fillna(False), "HIGH", "MID"))
    st.loc[st.fuel_share.isna(), "fuel"] = None
    st["alt30"] = alt_median_30(C, first).reindex(idx)
    starts = {k: (S[k] != 0).idxmax() for k in S.columns}
    SER.write_bytes(pickle.dumps(dict(S=S, st=st, starts=starts)))
    return S, st, starts


def alt_median_30(C, first):
    """The median 30-day return of the point-in-time top-40 alts (BTC out), from closes through the day before."""
    from backtest.market_neutral import drop_non_crypto
    from backtest.runner_gate import member_mask
    from backtest.wide_book import eligibility
    X = C.to_numpy(float)
    mem = member_mask(C, first, drop_non_crypto(eligibility(40))) & np.isfinite(X)
    ib = list(C.columns).index("BTCUSDT")
    out = np.full(len(C), np.nan)
    for d in range(33, len(C)):
        m = mem[d - 1].copy()
        m[ib] = False
        m &= np.isfinite(X[d - 1]) & np.isfinite(X[d - 31])
        if m.sum() >= 8:
            out[d] = np.median(X[d - 1, m] / X[d - 31, m] - 1)
    return pd.Series(out, index=C.index)


def load():
    if SER.exists() and "--rebuild" not in sys.argv:
        d = pickle.loads(SER.read_bytes())
        return d["S"], d["st"], d["starts"]
    return build()


# ---------------------------------------------------------------- the measurements (pure functions; tested)

def ann(x: pd.Series) -> float:
    return float(x.mean() * 365) if len(x) else float("nan")


def sharpe(x: pd.Series) -> float:
    sd = x.std(ddof=1)
    return float(x.mean() / sd * np.sqrt(365)) if len(x) > 2 and sd > 0 else float("nan")


def state_cell(x: pd.Series, mask: pd.Series, cut=CUT) -> dict:
    """Annualised mean of x on the days in mask, overall and on each half; n days."""
    y = x[mask.reindex(x.index).fillna(False).astype(bool)]
    a, b = y[y.index < cut], y[y.index >= cut]
    return dict(ann=ann(y), tu=ann(a), ho=ann(b), n=int(len(y)), both=bool(len(a) > 20 and len(b) > 20 and ann(a) > 0 and ann(b) > 0))


def weekly(S: pd.DataFrame) -> pd.DataFrame:
    return S.resample("W-SUN").sum()


def pair_corr(W: pd.DataFrame, starts: dict) -> pd.DataFrame:
    """Weekly correlation of every pair, each pair from the later of the two books' starts."""
    cols = list(W.columns)
    R = pd.DataFrame(np.nan, index=cols, columns=cols)
    for i, a in enumerate(cols):
        for b in cols[i:]:
            t0 = max(starts[a], starts[b])
            w = W[W.index >= t0]
            r = 1.0 if a == b else float(w[a].corr(w[b]))
            R.loc[a, b] = R.loc[b, a] = r
    return R


def extreme_weeks(W: pd.DataFrame, total: pd.Series, q=0.10, worst=True) -> pd.Series:
    """Each book's mean weekly return in the total's worst (or best) q of weeks."""
    cut = total.quantile(q if worst else 1 - q)
    sel = total <= cut if worst else total >= cut
    return W[sel].mean()


def forward(x: pd.Series, k=30) -> pd.Series:
    """The sum of x over the NEXT k days (t+1 .. t+k), aligned to day t."""
    return x[::-1].rolling(k, min_periods=k).sum()[::-1].shift(-1)


def spearman_halves(sig: pd.Series, y: pd.Series, cut=CUT, step=30) -> tuple:
    """Spearman of sig with y on non-overlapping days (every `step`-th), per half."""
    d = pd.concat([sig, y], axis=1).dropna().iloc[::step]
    out = []
    for m in (d.index < cut, d.index >= cut):
        e = d[m]
        out.append(float(e.iloc[:, 0].rank().corr(e.iloc[:, 1].rank())) if len(e) > 8 else float("nan"))
    return tuple(out)


# ---------------------------------------------------------------- report

FAMILIES = {"MOMENTUM": ["trend", "daily", "rsi80"],                          # buys what is already running
            "FORCED FLOW": ["sleeve", "capit2", "news", "crowd", "bids"],       # trades someone else's forced or crowded position
            "NEUTRAL / CARRY": ["mn_blend", "carry", "ndx_dip", "noise"]}       # hedged books, carry, the NASDAQ books


def episodes(mask: pd.Series, x: pd.Series, min_days=3) -> list:
    """Contiguous runs of True in mask (at least min_days): (start, end, days, compounded x over the run)."""
    m = mask.fillna(False).astype(bool).to_numpy()
    out, i = [], 0
    while i < len(m):
        if m[i]:
            j = i
            while j + 1 < len(m) and m[j + 1]:
                j += 1
            if j - i + 1 >= min_days:
                seg = x.iloc[i:j + 1]
                out.append((x.index[i], x.index[j], j - i + 1, float((1 + seg).prod() - 1)))
            i = j + 1
        else:
            i += 1
    return out


def posthoc(S, st, starts):
    """POST HOC (added after the first run): the books grouped into mechanism families, each family's state profile, and the
    machine's one losing state (BTC bull while the alts are not running) as dated episodes."""
    machine = S[MACHINE].sum(axis=1)
    L = ["", "6. POST HOC (added after the first run showed BULL+LOW as the machine's only losing state): FAMILIES and EPISODES",
         "   families by mechanism: " + "; ".join(f"{k} = {', '.join(v)}" for k, v in FAMILIES.items())]
    masks = {"BULL": st.btc == "bull", "CHOP": st.btc == "chop", "BEAR": st.btc == "bear", "fuel LOW": st.fuel == "LOW",
             "fuel HIGH": st.fuel == "HIGH", "alt bleed": st.alt30 <= -0.15, "BULL+LOW": (st.btc == "bull") & (st.fuel == "LOW")}
    fam = pd.DataFrame({k: S[v].sum(axis=1) for k, v in FAMILIES.items()})
    L.append(f"   {'family':<16}" + "".join(f"{m:>12}" for m in masks))
    for k in fam.columns:
        L.append(f"   {k:<16}" + "".join(f"{state_cell(fam[k], v)['ann'] * 100:>+11.1f}%" for v in masks.values()))
    W = fam.resample("W-SUN").sum()
    L.append("   weekly correlation between families: " + ", ".join(
        f"{a} ~ {b} {W[a].corr(W[b]):+.2f}" for i, a in enumerate(W.columns) for b in W.columns[i + 1:]))
    bl = (st.btc == "bull") & (st.fuel == "LOW")
    ep = episodes(bl, machine)
    L.append(f"   BULL+LOW episodes (3+ days): {len(ep)}; machine compounded over each:")
    for a, b, n, r in ep:
        seg = slice(a, b)
        L.append(f"     {a:%Y-%m-%d} .. {b:%Y-%m-%d} ({n:>3} days) machine {r * 100:+6.1f}%  trend {S.trend[seg].sum() * 100:+6.1f}%  "
                 f"forced flow {fam['FORCED FLOW'][seg].sum() * 100:+5.1f}%  neutral {fam['NEUTRAL / CARRY'][seg].sum() * 100:+5.1f}%  "
                 f"alt median 30d at start {st.alt30.get(a, float('nan')) * 100:+.0f}%")
    L += ["", "   ALT BLEED split by the BTC label (the live tape of 2026-11: alts -33% median, BTC labelled chop) - annualised, % of the account"]
    cells = {"bleed+BULL": (st.alt30 <= -0.15) & (st.btc == "bull"), "bleed+CHOP": (st.alt30 <= -0.15) & (st.btc == "chop"),
             "bleed+BEAR": (st.alt30 <= -0.15) & (st.btc == "bear"), "deep bleed (<= -25%)": st.alt30 <= -0.25}
    L.append(f"   {'book':<16}" + "".join(f"{k:>22}" for k in cells))
    L.append(f"   {'(days)':<16}" + "".join(f"{'(' + str(int(v.sum())) + ')':>22}" for v in cells.values()))
    for k in ALL + ["MACHINE"]:
        x = machine if k == "MACHINE" else S[k][S.index >= starts[k]]
        cs_ = [state_cell(x, v) for v in cells.values()]
        L.append(f"   {k:<16}" + "".join(f"{c['ann'] * 100:>+20.1f}%{'*' if c['both'] else ' '}" for c in cs_))
    ev = S[["sleeve", "bids", "capit2", "news", "ndx_dip"]].sum(axis=1)
    L += ["", "   THE EVENT-ONLY ACCOUNT (audit_event_only.py's set: sleeve + bids + capit2 + news + ndx_dip, at machine weights) by state - annualised, % of the account"]
    allc = {"BULL": st.btc == "bull", "CHOP": st.btc == "chop", "BEAR": st.btc == "bear", "fuel LOW": st.fuel == "LOW", "fuel HIGH": st.fuel == "HIGH",
            "alt bleed": st.alt30 <= -0.15, "deep bleed": st.alt30 <= -0.25, "BULL+LOW": (st.btc == "bull") & (st.fuel == "LOW")}
    L.append("   " + "  ".join(f"{k} {state_cell(ev, v)['ann'] * 100:+.0f}%{'*' if state_cell(ev, v)['both'] else ''}" for k, v in allc.items()))
    L.append("   by year (sum of days): " + "  ".join(f"{y} {x.sum() * 100:+.0f}%" for y, x in ev.groupby(ev.index.year)))
    m = bl.reindex(S.index).fillna(False).astype(bool)
    no_trend = machine - S.trend
    L.append(f"   all {int(m.sum())} BULL+LOW days: machine {machine[m].sum() * 100:+.1f}% (sum of days), of which trend {S.trend[m].sum() * 100:+.1f}%; "
             f"the machine without trend {no_trend[m].sum() * 100:+.1f}%")
    return L


def main():
    t0 = time.time()
    S, st, starts = load()
    S = S.loc[:, ALL]
    machine = S[MACHINE].sum(axis=1)
    L = [f"backtest/works_map.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; {S.index[0]:%Y-%m-%d} .. {S.index[-1]:%Y-%m-%d}; machine books = the "
         f"mean of the 10 orderings; trend gains shrunk 3x, the rest raw; halves split {CUT.date()}; BACKTEST", ""]
    J = dict(books={}, states={}, corr={}, worst={}, best={}, signals={}, meta=dict(start=str(S.index[0].date()), end=str(S.index[-1].date()),
                                                                                    cut=str(CUT.date())))
    # 1
    L.append("1. EACH BOOK ALONE (annualised mean day, % of the account at its machine weight)")
    L.append(f"   {'book':<9}{'start':>12}{'ann':>8}{'tune':>8}{'hold':>8}{'Sharpe':>8}{'active':>8}")
    for k in ALL + ["MACHINE"]:
        x = (machine if k == "MACHINE" else S[k])
        x = x[x.index >= (starts.get(k, S.index[0]) if k != "MACHINE" else S.index[0])]
        act = float((x != 0).mean())
        row = dict(start=str(x.index[0].date()), ann=ann(x), tu=ann(x[x.index < CUT]), ho=ann(x[x.index >= CUT]), sharpe=sharpe(x), active=act)
        J["books"][k] = row
        L.append(f"   {k:<9}{row['start']:>12}{row['ann'] * 100:>+7.1f}%{row['tu'] * 100:>+7.1f}%{row['ho'] * 100:>+7.1f}%{row['sharpe']:>8.2f}{act * 100:>7.0f}%")
    # 2
    masks = {"BULL": st.btc == "bull", "CHOP": st.btc == "chop", "BEAR": st.btc == "bear",
             "fuel LOW": st.fuel == "LOW", "fuel MID": st.fuel == "MID", "fuel HIGH": st.fuel == "HIGH",
             "alt bleed": st.alt30 <= -0.15, "no bleed": st.alt30 > -0.15,
             "CHOP+LOW": (st.btc == "chop") & (st.fuel == "LOW"), "BULL+LOW": (st.btc == "bull") & (st.fuel == "LOW")}
    L += ["", "2. THE STATE MAP - annualised mean in each state (% of the account); * = positive on both halves; days in brackets"]
    L.append(f"   {'book':<9}" + "".join(f"{m:>12}" for m in masks))
    L.append(f"   {'(days)':<9}" + "".join(f"{'(' + str(int(v.sum())) + ')':>12}" for v in masks.values()))
    for k in ALL + ["MACHINE"]:
        x = machine if k == "MACHINE" else S[k][S.index >= starts[k]]
        cells = {m: state_cell(x, v) for m, v in masks.items()}
        J["states"][k] = cells
        L.append(f"   {k:<9}" + "".join(f"{c['ann'] * 100:>+10.1f}%{'*' if c['both'] else ' '}" for c in cells.values()))
    # 3
    W = weekly(S)
    R = pair_corr(W, starts)
    J["corr"] = {a: {b: R.loc[a, b] for b in ALL} for a in ALL}
    L += ["", "3. WEEKLY CORRELATION (pairwise, from the later book's start)", "   " + " " * 9 + "".join(f"{k[:7]:>8}" for k in ALL)]
    for a in ALL:
        L.append(f"   {a:<9}" + "".join(f"{R.loc[a, b]:>+8.2f}" for b in ALL))
    off = R.where(~np.eye(len(ALL), dtype=bool)).stack()
    top = off[off.index.get_level_values(0) < off.index.get_level_values(1)].sort_values()
    L.append(f"   highest: {', '.join(f'{a}~{b} {v:+.2f}' for (a, b), v in top.iloc[::-1][:4].items())}; lowest: "
             f"{', '.join(f'{a}~{b} {v:+.2f}' for (a, b), v in top[:4].items())}")
    # 4
    Wm = W[MACHINE].sum(axis=1)
    wk, bk = extreme_weeks(W, Wm, worst=True), extreme_weeks(W, Wm, worst=False)
    J["worst"], J["best"] = {k: float(wk[k]) for k in ALL}, {k: float(bk[k]) for k in ALL}
    L += ["", f"4. THE MACHINE'S WORST 10% OF WEEKS (machine {Wm[Wm <= Wm.quantile(0.1)].mean() * 100:+.2f}% a week) and BEST 10% "
          f"({Wm[Wm >= Wm.quantile(0.9)].mean() * 100:+.2f}%) - each book's average week then",
          "   worst: " + ", ".join(f"{k} {wk[k] * 100:+.2f}%" for k in ALL),
          "   best:  " + ", ".join(f"{k} {bk[k] * 100:+.2f}%" for k in ALL)]
    # 5
    L += ["", "5. SIGNAL -> BOOK: Spearman with each book's NEXT 30 days, every 30th day (tune / holdout); ! = same sign, |rho| > 0.15 both halves"]
    for nm, sig in (("fuel share", st.fuel_share), ("BTC vs 50d", st.btc_gap), ("alt median 30d", st.alt30)):
        rs = {k: spearman_halves(sig, forward(machine if k == "MACHINE" else S[k])) for k in ALL + ["MACHINE"]}
        J["signals"][nm] = {k: dict(tu=a, ho=b) for k, (a, b) in rs.items()}
        L.append(f"   {nm:<15}" + "  ".join(f"{k} {a:+.2f}/{b:+.2f}{'!' if np.sign(a) == np.sign(b) and min(abs(a), abs(b)) > 0.15 else ''}"
                                              for k, (a, b) in rs.items()))
    # expectations
    sm = J["states"]
    w1 = (sm["MACHINE"]["CHOP"]["ann"] < min(sm["MACHINE"]["BULL"]["ann"], sm["MACHINE"]["BEAR"]["ann"])
          and sum(sm[k]["CHOP"]["ann"] > 0 for k in ALL) >= 3)
    w2 = bool(top.max() < 0.40)
    w3 = wk[MACHINE].idxmin() == "trend" and int((wk[ALL] > 0).sum()) >= 3
    f = J["signals"]["fuel share"]
    w4 = (f["trend"]["tu"] > 0 and f["trend"]["ho"] > 0
          and not any(np.sign(f[k]["tu"]) == np.sign(f[k]["ho"]) and min(abs(f[k]["tu"]), abs(f[k]["ho"])) > 0.15 for k in ALL if k != "trend"))
    w5 = sm["MACHINE"]["fuel LOW"]["ann"] < 0.5 * sm["MACHINE"]["fuel HIGH"]["ann"]
    ok = lambda b: "RIGHT" if b else "WRONG"  # noqa: E731
    L += ["", "EXPECTATIONS (registered before the run)",
          f"  W1 chop is the machine's weakest BTC state and >= 3 books earn in it -> {ok(w1)} "
          f"(machine bull {sm['MACHINE']['BULL']['ann'] * 100:+.0f}% / chop {sm['MACHINE']['CHOP']['ann'] * 100:+.0f}% / bear {sm['MACHINE']['BEAR']['ann'] * 100:+.0f}%; "
          f"{sum(sm[k]['CHOP']['ann'] > 0 for k in ALL)} books positive in chop)",
          f"  W2 every weekly correlation under +0.40 -> {ok(w2)} (max {top.max():+.2f})",
          f"  W3 in the worst weeks trend is the biggest loser and >= 3 books are positive -> {ok(w3)} (biggest loser {wk[MACHINE].idxmin()}, "
          f"{int((wk[ALL] > 0).sum())} positive)",
          f"  W4 fuel predicts trend on both halves, no other book with a same-sign |rho| > 0.15 -> {ok(w4)}",
          f"  W5 machine on LOW-fuel days < half its HIGH-fuel rate -> {ok(w5)}",
          f"run time {time.time() - t0:.0f}s"]
    L += posthoc(S, st, starts)
    fam = pd.DataFrame({k: S[v].sum(axis=1) for k, v in FAMILIES.items()})
    J["families"] = {k: {m: state_cell(fam[k], v) for m, v in masks.items()} for k in fam.columns}
    txt = "\n".join(L)
    LOG.write_text(txt + "\n", encoding="utf-8")
    OUT.write_text(json.dumps(J, default=float), encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
