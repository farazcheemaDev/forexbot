"""THE CROWD-SQUEEZE BOOK, JUDGED SOONER - what can be checked now instead of in April 2027 (2026-10-23)

THE USER (2026-10-23): "can't wait till April". The paper book (news/crowd_paper.py) needs 26 weeks. Four checks need none:
  A UNSEEN WEEKS  the backtest's data ended 2026-09-13; every Monday / Thursday since (2026-09-14 .. now) is replayed
                  through crowd_paper's OWN code (legs, fee, funding, marks) on Binance's archive crowd (the day's last
                  5-minute row), Binance daily closes and funding - a 6-week paper record that already exists
  B SEVEN DAYS    the book on all 7 anchor weekdays, 2022-26 (Binance archive): a weekly book measured on one or two
                  weekdays has misled this repo before (CLAUDE.md s3)
  C BYBIT CROWD   the same rule ranked on BYBIT's long / short account share (v5 account-ratio, 4h rows, the last row
                  before the anchor), prices Binance's: a different crowd, and back to 2021 - a year the book never saw
                  (it needs 16 coins with a reading; Bybit listed most alts during 2021)
  D HOW FAST      how well an N-week record separates the backtested book from a zero-edge one (contiguous N-week
                  windows of the 2022-26 weeks, half Monday / half Thursday; dead = the same weeks with the mean log
                  return removed, as backtest/verdict_power.py): P(kill) at the backtest's 10th percentile line

REGISTERED BEFORE THE RUN (2026-10-23)
  F1 A: the unseen weeks' combined return sits inside the backtest's 10th..90th percentile for their length.
  F2 B: positive on at least 6 of the 7 weekdays over 2022-26; t >= 2 on both halves on at most 2 of them.
  F3 C: Bybit's crowd ranks agree with Binance's (mean rank correlation per date >= 0.6), and the Bybit-ranked book is
     positive on both halves of 2022-26.
  F4 C: in 2021 (unseen) the Bybit-ranked book is positive, t under 2 (a bull year; ~half of it has enough coins).
  F5 D: a 13-week record kills a dead book less than half the time at the 10th-percentile line.

RESULT (2026-10-23, logs/crowd_fast.txt) - F1-F5 all RIGHT. The effect is there on every check that needs no waiting;
its SIZE is what stays uncertain.
  A  the 6 unseen weeks (2026-09-14 .. 10-23) through crowd_paper's own code: +9.6% ($300 -> $328.80), 8 of 10 closed
     half-weeks up, the 77th percentile of the backtest's 5.6-week stretches; while the final machine lost ~13%.
  B  positive on ALL 7 anchor weekdays 2022-26 (+33..+53%/yr) and on both halves of each; t >= 2 on both halves on none
     (Friday +2.79 / +1.98 nearest) - not one weekday's luck, still not a pass.
  C  Bybit's crowd (rank correlation +0.68 with Binance's - related, not the same people) gives the same book: 2022-24
     +16 / +23%/yr, 2024-26 +91 / +107%/yr (Monday / Thursday). 2021, a year never seen, from July when 16+ coins have a
     reading: +22% / +2%/yr, t +0.66 / +0.16 - positive, weak.
  D  a forward record alone is slow: right 56% / 62% / 66% / 74% / 79% of the time at 4 / 8 / 13 / 26 / 52 weeks; a
     13-week record at the 10th-percentile line kills a dead book 29% of the time.
  So: the evidence for the effect is now several independent reads, not one backtest; the size is the open question
  (2022-24 says +16..+24%/yr, 2024-26 says +60..+100%) - plan on the lower one. Checkpoints moved earlier on this basis
  (news/crowd_paper.py, registered before the first live anchor).

    python -m news.crowd_fast            (A, C, D; B once the seven-weekday archive is cached)
"""
from __future__ import annotations

import io
import json
import sys
import tempfile
import time
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from news import crowd_paper as cp  # noqa: E402
from news import mood_now as mn  # noqa: E402
from news import positioning_hist as ph  # noqa: E402

LOG = ROOT / "logs" / "crowd_fast.txt"
BYBIT = ROOT / "strategy_analysis" / "data" / "news" / "bybit_ratio.parquet"
UNSEEN = {"mon": "2026-09-14", "thu": "2026-09-17"}
ARCH = "https://data.binance.vision/data/futures/um/daily/metrics/{s}/{s}-metrics-{d}.zip"


def http(u, tries=4):
    for k in range(tries):
        try:
            return urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=30).read()
        except Exception:  # noqa: BLE001
            if k == tries - 1:
                return None
            time.sleep(1 + 2 * k)


# ------------------------------------------------------------------ A: the unseen weeks, through crowd_paper's own code

_POOL: dict = {}


def universe_at(now: datetime) -> list:
    """wide_book.eligibility for one month from Binance's API: every USDT perp listed (any status) >= 30 days at the
    month's start, ranked by the prior month's quote volume, top 40, stables dropped - as mood_now.universe."""
    month = now.strftime("%Y-%m")
    if month in _POOL:
        return _POOL[month]
    mstart = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
    pstart = datetime((mstart - timedelta(days=1)).year, (mstart - timedelta(days=1)).month, 1, tzinfo=timezone.utc)
    info = [s["symbol"] for s in mn.get(f"{mn.FAPI}/fapi/v1/exchangeInfo")["symbols"]
            if s.get("contractType") == "PERPETUAL" and s.get("quoteAsset") == "USDT"
            and (mstart - mn.utc(s["onboardDate"])).days >= mn.MIN_AGE_D]

    def qv(sym):
        k = json.loads(http(f"{mn.FAPI}/fapi/v1/klines?symbol={sym}&interval=1d&startTime={cp.ms(pstart)}"
                            f"&endTime={cp.ms(mstart) - 1}&limit=40") or b"[]")
        return sym, sum(float(b[7]) for b in k) if isinstance(k, list) else None
    with ThreadPoolExecutor(8) as ex:
        vol = {s: v for s, v in ex.map(qv, info) if v}
    top = sorted(vol, key=lambda s: -vol[s])[:mn.TOP_N]
    _POOL[month] = [s for s in top if s[:-4] not in mn.NON_CRYPTO]
    return _POOL[month]


def archive_crowd(sym: str, a_ms: int):
    """Binance's archive crowd for the day before the anchor: its last row, as the backtest read it."""
    d = (datetime.fromtimestamp(a_ms / 1000, timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    b = http(ARCH.format(s=sym, d=d), tries=2)
    if not b:
        return None, None
    df = pd.read_csv(zipfile.ZipFile(io.BytesIO(b)).open(f"{sym}-metrics-{d}.csv"))
    return (float(df.count_long_short_ratio.iloc[-1]), None) if len(df) else (None, None)


def unseen(now: datetime, L: list):
    old = {k: getattr(cp, k) for k in ("DIR", "STATE", "WEEKS", "SLEEVES_CSV", "MARKS")}
    d = Path(tempfile.mkdtemp())
    cp.DIR, cp.STATE, cp.WEEKS, cp.SLEEVES_CSV, cp.MARKS = d, d / "s.json", d / "w.csv", d / "sl.csv", d / "m.csv"
    try:
        st = cp.fresh()
        for k in st["sleeves"]:
            st["sleeves"][k]["next"] = UNSEEN[k]
        cp.anchors(st, now, universe=universe_at, crowd=archive_crowd)
        st["marked"] = None
        cp.mark(st, now)
        wk = pd.read_csv(cp.SLEEVES_CSV) if cp.SLEEVES_CSV.exists() else pd.DataFrame()
        legs = pd.read_csv(cp.WEEKS) if cp.WEEKS.exists() else pd.DataFrame()
        eq = {k: cp.sleeve_now(sl) for k, sl in st["sleeves"].items()}
        open_legs = {k: sl["pos"] for k, sl in st["sleeves"].items()}
    finally:
        for k, v in old.items():
            setattr(cp, k, v)
    tot = sum(eq.values())
    weeks = (now - cp.day0(UNSEEN["mon"])).days / 7
    bands = json.loads((ROOT / "crowd_bands.json").read_text())
    import dashboard_push as dp
    q, _ = dp.band_at(bands["total"], bands["lengths"], weeks)
    pc = dp.pctile(tot / 300 - 1, bands["levels"], q)
    L += [f"A  UNSEEN WEEKS: {UNSEEN['mon']} .. {now:%Y-%m-%d} ({weeks:.1f} weeks), crowd_paper's own code on Binance's archive crowd",
          f"   {'half':<6}{'week':<26}{'longs':>6}{'shorts':>7}{'gross':>9}{'fee':>7}{'net':>9}"]
    for r in wk.itertuples():
        L.append(f"   {r.sleeve:<6}{r.opened} -> {r.closed:<12}{r.n_long:>6}{r.n_short:>7}{r.gross * 100:>+8.2f}%"
                 f"{r.fee * 100:>6.2f}%{r.net * 100:>+8.2f}%")
    for k, pos in open_legs.items():
        if pos:
            L.append(f"   {k:<6}open week, marked at {now:%Y-%m-%d} 00:00: ${eq[k]:.2f} on ${st['sleeves'][k]['equity']:.2f}")
    if len(legs):
        lg = legs[legs.side > 0].sort_values("ret")
        L.append(f"   long legs' best weeks: " + ", ".join(f"{r.sym[:-4]} {r.ret * 100:+.0f}%" for r in lg.tail(5)[::-1].itertuples())
                 + " | worst: " + ", ".join(f"{r.sym[:-4]} {r.ret * 100:+.0f}%" for r in lg.head(3).itertuples()))
        sh = legs[legs.side < 0].sort_values("ret")
        L.append(f"   short legs' worst (rose most): " + ", ".join(f"{r.sym[:-4]} {r.ret * 100:+.0f}%" for r in sh.tail(3)[::-1].itertuples()))
    L.append(f"   $300 -> ${tot:.2f} ({(tot / 300 - 1) * 100:+.2f}%): the {pc:.0f}th percentile of the backtest's {weeks:.1f}-week "
             f"stretches (p10 {q[1] * 100:+.1f}%, median {q[3] * 100:+.1f}%, p90 {q[5] * 100:+.1f}%)")
    return dict(ret=tot / 300 - 1, pctile=pc)


# ------------------------------------------------------------------ B: seven weekdays (Binance archive, 2022-26)

def seven(L: list):
    anchors, el, F, C, Fd, cff, piv = ph.inputs(days=range(7))
    L.append("B  SEVEN ANCHOR WEEKDAYS, 2022-26 (Binance crowd; the book as positioning_hist.book runs it)")
    L.append(f"   {'weekday':<11}{'weeks':>6}{'%/yr':>9}{'tune':>9}{'hold':>9}{'t tune':>8}{'t hold':>8}")
    out = {}
    for wd, nm in enumerate(("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")):
        D = ph.panel(wd, anchors, el, C, Fd, cff, piv)
        _, bk = ph.book(D, "crowd", ph.SIGN["crowd"])
        cut = bk.index[int(len(bk) * ph.TUNE)]
        tu, ho = bk[bk.index < cut], bk[bk.index >= cut]
        t = lambda x: x.mean() / (x.std(ddof=1) / np.sqrt(len(x)))  # noqa: E731
        yr = lambda x: ((1 + x).prod() ** (52 / len(x)) - 1) * 100  # noqa: E731
        out[nm] = dict(yr=yr(bk), tt=t(tu), th=t(ho))
        L.append(f"   {nm:<11}{len(bk):>6}{yr(bk):>+8.1f}%{yr(tu):>+8.1f}%{yr(ho):>+8.1f}%{t(tu):>+8.2f}{t(ho):>+8.2f}")
    return out


# ------------------------------------------------------------------ C: Bybit's crowd

def bybit_fetch(el: dict):
    """4h account-ratio rows for every symbol over its eligible months (+ the day before), cached."""
    have = pd.read_parquet(BYBIT) if BYBIT.exists() else pd.DataFrame(columns=["sym", "ts", "buy"])
    done = set(have.sym.unique())
    jobs = []
    for s, months in el.items():
        if s in done or s[:-4] in mn.NON_CRYPTO:
            continue
        ms_ = sorted(m for m in months if m >= "2021-01")
        if not ms_:
            continue
        a = pd.Timestamp(ms_[0] + "-01", tz="UTC") - pd.Timedelta(days=2)
        z = min(pd.Timestamp(ms_[-1] + "-01", tz="UTC") + pd.offsets.MonthEnd(1) + pd.Timedelta(days=1),
                pd.Timestamp("2026-09-15", tz="UTC"))
        jobs.append((s, int(a.value // 10**6), int(z.value // 10**6)))
    print(f"bybit: {len(jobs)} symbols to fetch", flush=True)

    def one(j):
        s, a, z = j
        rows, end = [], z
        while end > a:
            b = http(f"https://api.bybit.com/v5/market/account-ratio?category=linear&symbol={s}&period=4h&limit=500"
                     f"&startTime={a}&endTime={end}")
            L_ = (json.loads(b).get("result") or {}).get("list") or [] if b else []
            if not L_:
                break
            rows += [(s, int(x["timestamp"]), float(x["buyRatio"])) for x in L_]
            nxt = min(int(x["timestamp"]) for x in L_) - 1
            if nxt >= end:
                break
            end = nxt
            time.sleep(0.05)
        return rows
    new = []
    with ThreadPoolExecutor(4) as ex:
        for k, rows in enumerate(ex.map(one, jobs)):
            new += rows
            if (k + 1) % 50 == 0:
                print(f"  {k + 1} / {len(jobs)}", flush=True)
    out = pd.concat([have, pd.DataFrame(new, columns=["sym", "ts", "buy"])], ignore_index=True)
    out.to_parquet(BYBIT)
    return out


def bybit(L: list):
    from scipy.stats import spearmanr
    _, el, _ = ph.plan()
    anchors = pd.date_range("2021-01-04", "2026-09-10", freq="D")
    anchors = anchors[anchors.dayofweek.isin([0, 3])]
    B = bybit_fetch(el)
    B = B.drop_duplicates(["sym", "ts"]).sort_values("ts", kind="stable")
    from backtest.market_neutral import load_panel
    C, Fd, _ = load_panel()
    C.index = C.index.astype("datetime64[ns]")
    Fd = Fd.reindex(C.index).fillna(0.0)
    cff = C.ffill()
    # the crowd at each anchor = the last 4h row strictly before it (within 12h), indexed by d0 like the archive's
    rows = []
    for s, g in B.groupby("sym"):
        ts, buy = g.ts.to_numpy(np.int64), g.buy.to_numpy(float)
        for a in anchors:
            am = int(a.value // 10**6)
            i = np.searchsorted(ts, am) - 1
            if i >= 0 and am - ts[i] <= 12 * 3600 * 1000:
                rows.append((a - pd.Timedelta(days=1), s, buy[i]))
    P = pd.DataFrame(rows, columns=["day", "sym", "crowd"]).pivot_table(index="day", columns="sym", values="crowd")
    piv = {f: pd.DataFrame() for f in ph.FEATS}
    piv["crowd"] = P
    L.append("C  BYBIT'S CROWD (long account share, last 4h row before the anchor), Binance prices, same rule")
    res = {}
    for wd, nm in ((0, "Monday"), (3, "Thursday")):
        D = ph.panel(wd, anchors, el, C, Fd, cff, piv)
        n_ok = D.dropna(subset=["crowd"]).groupby("a").size()
        _, bk = ph.book(D, "crowd", ph.SIGN["crowd"])
        t = lambda x: x.mean() / (x.std(ddof=1) / np.sqrt(len(x))) if len(x) > 2 else 0.0  # noqa: E731
        yr = lambda x: ((1 + x).prod() ** (52 / len(x)) - 1) * 100 if len(x) else np.nan  # noqa: E731
        y21 = bk[bk.index < "2022-01-01"]
        x = bk[bk.index >= "2022-01-01"]
        cut = x.index[int(len(x) * ph.TUNE)]
        tu, ho = x[x.index < cut], x[x.index >= cut]
        res[nm] = dict(y21=y21.mean(), t21=t(y21), tu=tu.mean(), ho=ho.mean(), n21=len(y21))
        first = n_ok[n_ok >= 16].index.min()
        L.append(f"   {nm:<9} 2021 (unseen): {len(y21):>3} weeks {yr(y21):>+7.1f}%/yr t {t(y21):+.2f} (16+ coins from {first:%Y-%m-%d})"
                 f" | 2022-24 {yr(tu):+.1f}%/yr t {t(tu):+.2f} | 2024-26 {yr(ho):+.1f}%/yr t {t(ho):+.2f}")
    # do the two crowds rank the coins alike?
    _, _, F, _, _, _, pv = ph.inputs()
    bin_ = pv["crowd"]
    common = bin_.index.intersection(P.index)
    rc = []
    for d in common:
        x = bin_.loc[d]
        y = P.loc[d].reindex(x.index)
        ok = x.notna() & y.notna()
        if ok.sum() >= 16:
            rc.append(spearmanr(x[ok], y[ok]).correlation)
    rc = float(np.nanmean(rc)) if rc else np.nan
    L.append(f"   Binance vs Bybit crowd ranks, same dates: mean rank correlation {rc:+.2f} over {len(common)} dates")
    res["rank_corr"] = rc
    return res


# ------------------------------------------------------------------ D: how fast a record can tell

def power(L: list):
    anchors, el, F, C, Fd, cff, piv = ph.inputs()
    m = ph.book(ph.panel(0, anchors, el, C, Fd, cff, piv), "crowd", -1)[1]
    t = ph.book(ph.panel(3, anchors, el, C, Fd, cff, piv), "crowd", -1)[1]
    tt = t.reindex([a + pd.Timedelta(days=3) for a in m.index]).to_numpy()
    ok = np.isfinite(tt)
    w = 0.5 * m.to_numpy()[ok] + 0.5 * tt[ok]                         # a week of both halves
    lg = np.log1p(w)
    dead = np.expm1(lg - lg.mean())                                    # zero edge, same swings
    L.append("D  HOW FAST A PAPER RECORD CAN TELL (contiguous windows of the 2022-26 weeks)")
    L.append(f"   {'weeks':>6}{'line (p10)':>12}{'P(kill | works)':>17}{'P(kill | dead)':>16}{'right, 50/50 prior':>20}")
    res = {}
    for N in (4, 8, 13, 26, 52):
        win = np.array([np.prod(1 + w[i:i + N]) - 1 for i in range(len(w) - N + 1)])
        dwin = np.array([np.prod(1 + dead[i:i + N]) - 1 for i in range(len(dead) - N + 1)])
        line = np.percentile(win, 10)
        pk_w, pk_d = (win < line).mean(), (dwin < line).mean()
        thr = np.median(np.r_[win, dwin])
        acc = 0.5 * (win >= thr).mean() + 0.5 * (dwin < thr).mean()
        res[N] = dict(line=line, kill_dead=pk_d, acc=acc)
        L.append(f"   {N:>6}{line * 100:>+11.1f}%{pk_w * 100:>16.0f}%{pk_d * 100:>15.0f}%{acc * 100:>19.0f}%")
    return res


def main():
    now = datetime.now(timezone.utc)
    L = [f"news/crowd_fast.py, {now:%Y-%m-%d %H:%M} UTC; the crowd-squeeze book judged without waiting for April", ""]
    R = {}
    keep = ROOT / "logs" / "crowd_fast_unseen.json"                 # A takes ~10 minutes: --reuse-a reads today's run
    if "--reuse-a" in sys.argv and keep.exists() and json.loads(keep.read_text())["day"] == f"{now:%Y-%m-%d}":
        k = json.loads(keep.read_text())
        L += k["lines"]
        R["A"] = k["res"]
    else:
        n0 = len(L)
        R["A"] = unseen(now, L)
        keep.write_text(json.dumps(dict(day=f"{now:%Y-%m-%d}", lines=L[n0:], res=R["A"])))
    L.append("")
    R["D"] = power(L)
    L.append("")
    R["C"] = bybit(L)
    L.append("")
    if "--seven" in sys.argv or _seven_cached():
        R["B"] = seven(L)
        L.append("")
    a = R["A"]
    f1 = 10 <= a["pctile"] <= 90
    c = R["C"]
    f3 = c["rank_corr"] >= 0.6 and all(c[n]["tu"] > 0 and c[n]["ho"] > 0 for n in ("Monday", "Thursday"))
    f4 = all(c[n]["y21"] > 0 and c[n]["t21"] < 2 for n in ("Monday", "Thursday"))
    f5 = R["D"][13]["kill_dead"] < 0.5
    L += ["REGISTERED PREDICTIONS",
          f"  F1 unseen weeks inside p10..p90: {a['pctile']:.0f}th -> {'RIGHT' if f1 else 'WRONG'}"]
    if "B" in R:
        pos = sum(v["yr"] > 0 for v in R["B"].values())
        both = sum(min(v["tt"], v["th"]) >= 2 for v in R["B"].values())
        L.append(f"  F2 positive on >= 6 of 7 weekdays ({pos}), t >= 2 both halves on <= 2 ({both}) -> "
                 f"{'RIGHT' if pos >= 6 and both <= 2 else 'WRONG'}")
    L += [f"  F3 Bybit ranks agree (>= 0.6: {c['rank_corr']:+.2f}) and its book is positive on both halves -> {'RIGHT' if f3 else 'WRONG'}",
          f"  F4 2021 positive with t < 2 on both weekdays -> {'RIGHT' if f4 else 'WRONG'}",
          f"  F5 a 13-week record kills a dead book under half the time ({R['D'][13]['kill_dead'] * 100:.0f}%) -> {'RIGHT' if f5 else 'WRONG'}"]
    txt = "\n".join(L)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


def _seven_cached() -> bool:
    if not ph.CACHE.exists():
        return False
    _, _, jobs = ph.plan(range(7))
    have = pd.read_parquet(ph.CACHE, columns=["sym", "day"])
    return len(set(jobs) - set(zip(have.sym, have.day))) == 0


if __name__ == "__main__":
    main()
