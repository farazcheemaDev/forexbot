"""SENTIMENT ENGINE: POSITIONING - does the crowd's long / short stance predict a coin's next week? (2026-10-23)

THE USER (2026-10-23): "a better sentiment tool - add all the good stuff". Positioning is sentiment with money behind it.
Binance's free archive (data.binance.vision futures/um/daily/metrics, 5-minute rows since 2021-12) has, per perp:
    crowd    count_long_short_ratio            long / short ACCOUNTS, every user
    top_acc  count_toptrader_long_short_ratio  the same among the top 20% of accounts by margin
    top_pos  sum_toptrader_long_short_ratio    their POSITION sizes long / short
    taker    sum_taker_long_short_vol_ratio    aggressive buy / sell volume (the day's mean)
    oi7      open interest value now / 7 days ago - 1
Doc 12 tested some of this on BTC alone (top traders piling long preceded weaker weeks); never across coins.
TEST   every Monday and every Thursday 2022-01 .. 2026-09 (two anchors - a weekly book on one weekday has misled this
       repo before), the PIT top-40 (wide_book.eligibility, dead coins in): each measure as of the previous day's last row,
       ranked across the coins; the next 7 days' return vs BTC from the perp archive's daily closes, funding charged
       (a short receives it). IC = rank correlation per date, averaged; a BOOK = long the 25% on one side, short the
       25% on the other, 0.5 a side, 12bp on the names that change.
PASS   the book nets > 0 with t >= 2 on BOTH halves (60 / 40 by date), on BOTH anchors.

REGISTERED BEFORE THE RUN (2026-10-23)
  Q1 crowd is CONTRARIAN: mean IC <= -0.02, negative on both halves and both anchors.
  Q2 top_pos FOLLOWS (smart money): IC > 0 but under 0.02.
  Q3 oi7 is contrarian and small (IC -0.01..-0.03); taker ~0 (|IC| < 0.01).
  Q4 no book passes on both anchors.

RESULT (2026-10-23, logs/positioning_hist.txt; 19,243 coin-days, 245 weeks per anchor) - one LEAD, no pass. Q4 RIGHT; Q1-Q3 WRONG.
  Rank ICs are small and mostly POSITIVE: taker +0.062 / +0.046 (t +4.3 / +3.6 - aggressive buying precedes a better
  week, momentum, not contrarian), top_acc +0.03 / +0.02, crowd ~0. Yet the CROWD book (long the coins the crowd is most
  SHORT, short the most long) made +37% / +48%/yr (Monday / Thursday), t +1.84 / +2.00 and +1.78 / +1.87 by half - under
  the bar. Taken apart: +0.77%/wk, of which +0.32%/wk is FUNDING (crowded shorts pay longs) and the rest a fat tail of
  SQUEEZES in heavily shorted small coins (MYX +186% / +214%, FHE +268%, SIREN +293%, AIA +309% in a week; the low-crowd
  quartile had 39 weeks over +50%, the high one 12). Without its best 5 weeks +0.46%/wk; correlation with the running
  carry book +0.19. Mostly 2025-26 (holdout +61% / +96% vs tune +23%). A lead for a paper record (doc 22: a new book is
  the user's call), not an edge on this evidence.
  POST-HOC (--taker-follow, logs/positioning_taker_follow.txt): taker's IC came out positive, so its book was re-run
  FOLLOWING the flow: -9.8% / +6.7%/yr (Monday / Thursday), t -0.86..+1.19. The IC lives in the middle of the ranking,
  not in the quarters a book trades. Dead both ways.

    python -m news.positioning_hist           (downloads ~20k small daily files once, cached as features)
"""
from __future__ import annotations

import io
import sys
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

CACHE = ROOT / "strategy_analysis" / "data" / "news" / "positioning_features.parquet"
LOG = ROOT / "logs" / "positioning_hist.txt"
URL = "https://data.binance.vision/data/futures/um/daily/metrics/{s}/{s}-metrics-{d}.zip"
FEATS = ["crowd", "top_acc", "top_pos", "taker", "oi"]
SIGN = {"crowd": -1, "top_acc": -1, "top_pos": +1, "taker": -1, "oi7": -1}    # the registered direction of each book
FEE = 12.0 / 1e4
TUNE = 0.60
POST = "--taker-follow" in sys.argv     # POST-HOC: taker's IC came out positive, so its book is re-run FOLLOWING the flow
LOG_POST = ROOT / "logs" / "positioning_taker_follow.txt"


def one(sym: str, day: str):
    try:
        b = urllib.request.urlopen(urllib.request.Request(URL.format(s=sym, d=day), headers={"User-Agent": "forexbot"}),
                                   timeout=30).read()
        d = pd.read_csv(zipfile.ZipFile(io.BytesIO(b)).open(f"{sym}-metrics-{day}.csv"))
    except Exception:  # noqa: BLE001 - not listed that day, or no file
        return None
    if not len(d):
        return None
    last = d.iloc[-1]
    return dict(sym=sym, day=day, crowd=float(last.count_long_short_ratio), top_acc=float(last.count_toptrader_long_short_ratio),
                top_pos=float(last.sum_toptrader_long_short_ratio), taker=float(d.sum_taker_long_short_vol_ratio.mean()),
                oi=float(last.sum_open_interest_value))


def plan(days=(0, 3)):
    from backtest.market_neutral import drop_non_crypto
    from backtest.wide_book import eligibility
    el = drop_non_crypto(eligibility(40))
    anchors = pd.date_range("2022-01-03", "2026-09-10", freq="D")
    anchors = anchors[anchors.dayofweek.isin(list(days))]
    jobs = []
    for a in anchors:
        m = a.strftime("%Y-%m")
        day = (a - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        for s, months in el.items():
            if m in months:
                jobs.append((s, day))
    return anchors, el, sorted(set(jobs))


def fetch(jobs):
    have = pd.read_parquet(CACHE) if CACHE.exists() else pd.DataFrame(columns=["sym", "day"] + FEATS)
    done = set(zip(have.sym, have.day))
    todo = [j for j in jobs if j not in done]
    print(f"positioning: {len(jobs):,} coin-days needed, {len(todo):,} to download", flush=True)
    rows = []
    with ThreadPoolExecutor(24) as ex:
        for k, r in enumerate(ex.map(lambda j: one(*j), todo)):
            rows.append(r if r else dict(sym=todo[k][0], day=todo[k][1], **{f: np.nan for f in FEATS}))
            if (k + 1) % 2000 == 0:
                print(f"  {k + 1:,} / {len(todo):,}", flush=True)
                pd.concat([have, pd.DataFrame(rows)]).to_parquet(CACHE)
    out = pd.concat([have, pd.DataFrame(rows)], ignore_index=True)
    out.to_parquet(CACHE)
    return out


def inputs(days=(0, 3)):
    from backtest.market_neutral import load_panel
    anchors, el, jobs = plan(days)
    F = fetch(jobs)
    C, Fd, first = load_panel()
    C.index = C.index.astype("datetime64[ns]")
    Fd = Fd.reindex(C.index).fillna(0.0)
    F["day"] = pd.to_datetime(F.day)
    piv = {f: F.pivot_table(index="day", columns="sym", values=f) for f in FEATS}
    return anchors, el, F, C, Fd, C.ffill(), piv


def panel(wd, anchors, el, C, Fd, cff, piv) -> pd.DataFrame:
    """One row per (anchor on weekday wd, coin of that month's universe): the measures as of the anchor, the next 7 days."""
    rows = []
    for a in anchors[anchors.dayofweek == wd]:
        d0 = a - pd.Timedelta(days=1)                     # the bar that closes at the anchor
        d1 = a + pd.Timedelta(days=6)                     # the bar that closes 7 days later
        if d1 > C.index[-1] or d0 not in C.index:
            continue
        m = a.strftime("%Y-%m")
        names = [s for s, ms in el.items() if m in ms and s in C.columns]
        btc = cff.at[d1, "BTCUSDT"] / C.at[d0, "BTCUSDT"] - 1
        prev = d0 - pd.Timedelta(days=7)
        for s in names:
            p0 = C.at[d0, s]
            if not np.isfinite(p0):
                continue
            p1 = cff.at[d1, s]
            fwd = p1 / p0 - 1 - btc
            fund = Fd.loc[(Fd.index > d0) & (Fd.index <= d1), s].sum() if s in Fd else 0.0
            r = dict(a=a, s=s, fwd=fwd, fund=fund)
            for f in FEATS:
                r[f] = piv[f].at[d0, s] if (d0 in piv[f].index and s in piv[f].columns) else np.nan
            o0 = piv["oi"].at[prev, s] if (prev in piv["oi"].index and s in piv["oi"].columns) else np.nan
            o1 = piv["oi"].at[d0, s] if (d0 in piv["oi"].index and s in piv["oi"].columns) else np.nan
            r["oi7"] = o1 / o0 - 1 if (np.isfinite(o0) and o0 > 0 and np.isfinite(o1)) else np.nan
            rows.append(r)
    return pd.DataFrame(rows)


def quarters(v: pd.Series):
    """The book's two sides on one date: the coins in the bottom and the top quarter of the ranking (pct rank, ties
    averaged). news/crowd_paper.py picks its legs with the same rule (tests/test_crowd_paper.py checks every week)."""
    q = v.rank(pct=True)
    return set(v.index[q <= 0.25]), set(v.index[q >= 0.75])


def turnover_fee(prev_l: set, prev_s: set, ln: set, sn: set) -> float:
    ch = (len(ln ^ prev_l) + len(sn ^ prev_s)) / max(2 * (len(ln) + len(sn)), 1)
    return FEE * min(ch * 2, 1.0)


def book(D: pd.DataFrame, f: str, sg: int):
    """Per date: the rank IC, and the book's net week (long the registered side's quarter, short the other, 0.5 a side)."""
    from scipy.stats import spearmanr
    ics, bk, prev_l, prev_s = [], [], set(), set()
    for a, g in D.groupby("a"):
        g = g.dropna(subset=[f]).set_index("s")
        if len(g) < 16:
            continue
        ics.append((a, spearmanr(g[f], g.fwd).correlation))
        lo, hi = quarters(g[f])
        ln, sn = (hi, lo) if sg > 0 else (lo, hi)                          # long the registered side
        L_, S_ = g.loc[sorted(ln)], g.loc[sorted(sn)]
        gross = 0.5 * (L_.fwd - L_.fund).mean() - 0.5 * (S_.fwd - S_.fund).mean()
        bk.append((a, gross - turnover_fee(prev_l, prev_s, ln, sn)))
        prev_l, prev_s = ln, sn
    return pd.Series(dict(ics)), pd.Series(dict(bk))


def band():
    """--band: the crowd book as news/crowd_paper.py runs it - a Monday sleeve and a Thursday sleeve, half the account
    each - over every N-week stretch of 2022-26 (N 1..52), as quantiles; written to crowd_bands.json for the paper book's
    scorecard and verdict, and summarised in logs/crowd_bands.txt."""
    import json
    anchors, el, F, C, Fd, cff, piv = inputs()
    S = {k: book(panel(wd, anchors, el, C, Fd, cff, piv), "crowd", SIGN["crowd"])[1] for wd, k in ((0, "mon"), (3, "thu"))}
    m, t = S["mon"], S["thu"]
    levels = [5, 10, 25, 50, 75, 90, 95]
    out, up, n_w = {}, {}, {}
    for N in range(1, 53):
        rets = []
        for i in range(len(m) - N + 1):
            mw = m.iloc[i:i + N]
            a = mw.index[0]
            if mw.index[-1] != a + pd.Timedelta(weeks=N - 1):              # contiguous weeks only
                continue
            tw = t.reindex([a + pd.Timedelta(days=3 + 7 * k) for k in range(N)])
            if tw.isna().any():
                continue
            rets.append(0.5 * ((1 + mw).prod() - 1) + 0.5 * ((1 + tw).prod() - 1))
        out[N] = [round(float(x), 5) for x in np.percentile(rets, levels)]
        up[N], n_w[N] = round(float(np.mean(np.array(rets) > 0)), 3), len(rets)
    span = f"{m.index[0]:%Y-%m-%d}..{m.index[-1]:%Y-%m-%d}"
    # dashboard_push's band format (band_at / pctile): lengths in WEEKS, the whole book as "total"
    (ROOT / "crowd_bands.json").write_text(json.dumps(dict(
        made=f"{pd.Timestamp.now(tz='UTC'):%Y-%m-%d}", span=span, levels=levels, lengths=list(out),
        total={str(N): dict(q=q, idle=0.0) for N, q in out.items()}, share_up={str(N): v for N, v in up.items()})))
    L = [f"news/positioning_hist.py --band, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; the crowd book as crowd_paper runs it"
         f" (Monday + Thursday sleeves, half each), every N-week stretch {span}", "",
         f"   {'weeks':>5}{'stretches':>10}" + "".join(f"{f'p{q}':>8}" for q in levels) + f"{'share up':>10}"]
    for N in (1, 2, 4, 8, 13, 26, 39, 52):
        L.append(f"   {N:>5}{n_w[N]:>10}" + "".join(f"{x * 100:>+7.1f}%" for x in out[N]) + f"{up[N] * 100:>9.0f}%")
    L += ["", f"   per sleeve, mean week: Monday {m.mean() * 100:+.2f}%, Thursday {t.mean() * 100:+.2f}%; "
              f"weeks {len(m)} / {len(t)}; correlation of the two sleeves' weeks (Thursday 3 days later) "
              f"{np.corrcoef(m.to_numpy()[:min(len(m), len(t))], t.to_numpy()[:min(len(m), len(t))])[0, 1]:+.2f}"]
    txt = "\n".join(L)
    (ROOT / "logs" / "crowd_bands.txt").write_text(txt + "\n", encoding="utf-8")
    print(txt)


def main():
    if "--band" in sys.argv:
        return band()
    anchors, el, F, C, Fd, cff, piv = inputs()
    L = [f"news/positioning_hist.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; Binance metrics archive, PIT top-40, "
         f"{F[FEATS[0]].notna().sum():,} coin-days with data; next 7 days vs BTC, funding charged", ""]
    res = {}
    for wd, name in ((0, "MONDAY"), (3, "THURSDAY")):
        D = panel(wd, anchors, el, C, Fd, cff, piv)
        dates = sorted(D.a.unique())
        cut = dates[int(len(dates) * TUNE)]
        L += [f"{name} anchors: {len(dates)} weeks, tune before {pd.Timestamp(cut):%Y-%m-%d}",
              f"   {'measure':<9}{'IC':>8}{'t':>7}{'IC tune':>9}{'IC hold':>9}{'book %/yr':>11}{'tune':>8}{'hold':>8}{'t tune':>8}{'t hold':>8}"]
        for f, sg in (SIGN if not POST else {"taker": +1}).items():
            ic, bk = book(D, f, sg)
            t = lambda x: x.mean() / (x.std(ddof=1) / np.sqrt(len(x))) if len(x) > 2 and x.std(ddof=1) > 0 else 0.0  # noqa: E731
            ta, ha = bk[bk.index < cut], bk[bk.index >= cut]
            yr = lambda x: ((1 + x).prod() ** (52 / max(len(x), 1)) - 1) * 100  # noqa: E731
            res[(name, f)] = dict(ic=ic.mean(), ict=ic[ic.index < cut].mean(), ich=ic[ic.index >= cut].mean(), tb=t(ta), th=t(ha),
                                  ma=ta.mean(), mh=ha.mean())
            L.append(f"   {f:<9}{ic.mean():>+8.3f}{t(ic):>+7.2f}{ic[ic.index < cut].mean():>+9.3f}{ic[ic.index >= cut].mean():>+9.3f}"
                     f"{yr(bk):>+10.1f}%{yr(ta):>+7.1f}%{yr(ha):>+7.1f}%{t(ta):>+8.2f}{t(ha):>+8.2f}")
        L.append("")
    if POST:
        txt = "\n".join(L)
        LOG_POST.write_text(txt + "\n", encoding="utf-8")
        print(txt)
        return
    r = res
    q1 = all(r[(n, "crowd")]["ic"] <= -0.02 and r[(n, "crowd")]["ict"] < 0 and r[(n, "crowd")]["ich"] < 0 for n in ("MONDAY", "THURSDAY"))
    q2 = all(0 < r[(n, "top_pos")]["ic"] < 0.02 for n in ("MONDAY", "THURSDAY"))
    q3 = all(-0.03 <= r[(n, "oi7")]["ic"] <= -0.01 and abs(r[(n, "taker")]["ic"]) < 0.01 for n in ("MONDAY", "THURSDAY"))
    passes = [f for f in SIGN if all(r[(n, f)]["ma"] > 0 and r[(n, f)]["mh"] > 0 and r[(n, f)]["tb"] >= 2 and r[(n, f)]["th"] >= 2
                                     for n in ("MONDAY", "THURSDAY"))]
    L += ["REGISTERED PREDICTIONS",
          f"  Q1 crowd contrarian, IC <= -0.02 both halves both anchors -> {'RIGHT' if q1 else 'WRONG'}",
          f"  Q2 top_pos follows, 0 < IC < 0.02 -> {'RIGHT' if q2 else 'WRONG'}",
          f"  Q3 oi7 -0.03..-0.01, taker |IC| < 0.01 -> {'RIGHT' if q3 else 'WRONG'}",
          f"  Q4 no book passes on both anchors -> {'RIGHT' if not passes else 'WRONG'} ({passes})"]
    txt = "\n".join(L)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
