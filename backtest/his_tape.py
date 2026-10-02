"""DOES HE READ THE TAPE? - real CME NQ futures order flow at his moments (Databento).

WHY (his_strategy.md s36)
    His edge needs BOTH his moment and his side: 88% on the +-7 race, against 57% for the best price rule given his
    timing and 55% for his side at nearby moments. At his click he knows which way the next 1-5 minutes go, and it is
    not in the price before it. The most likely carrier is ORDER FLOW on the real futures - aggressive buyers or
    sellers hitting CME NQ before price moves. s27 tested only Binance's QQQ perp, a thin crypto proxy. This tests the
    real thing.

DATA
    Databento GLBX.MDP3, schema `trades` (every trade, with the AGGRESSOR side: 'B' a buyer lifted the offer, 'A' a
    seller hit the bid), continuous front-volume contract NQ.v.0. Only the windows needed: 22 minutes before to 20
    minutes after each entry, merged per day. The key is read from the DATABENTO_API_KEY environment variable by the
    client itself - never passed, printed or logged. Raw data is cached under strategy_analysis/data/ (git-ignored:
    the repo is public and CME data may not be republished). Only aggregate results are committed.

    python -m backtest.his_tape --cost     price the request, download nothing
    python -m backtest.his_tape           download (refuses above --max-usd unless --go) and test

AT EACH MOMENT T (his entry, or a same-sitting moment: whole-minute offsets within 20 min, same second, same side)
    imb_w  = (buy-aggressor volume - sell-aggressor volume) / total volume over (T - w, T],  w = 5/15/30/60/120 s
    big_w  = the same, counting only trades of 5+ contracts
    Signed by the side (> 0: flow ran his way).

TESTS
    A. DIRECTION: at his moments, how often does the flow's sign agree with his side? (binomial vs 50%)
    B. TIMING: is the flow at his moment stronger in his direction than at the sitting's other moments? (rank vs 0.50)
    C. A RULE ANYONE COULD RUN: at random moments on every day fetched, trade WITH strong flow (top decile of |imb|):
       does it win the +-7 race? If B and C hold, a bot can read what he reads.

REGISTERED PREDICTIONS (2026-10-02, before any data is fetched)
    1. A: flow agrees with his side at 60-75% at some w <= 60 s - real but short of his 88%.
    2. B: his moments rank 0.55-0.65 on signed flow - somewhat stronger than the sitting's other moments.
    3. C: trading with top-decile flow at random moments wins 52-56% of +-7 races - order flow has a little direction
       content at minutes, mostly priced in seconds.
    If A >= 80% and C >= 60%, the tape is his source and his strategy can be automated. If A ~ 50%, it is not the
    trade flow, and what is left is the book, a live headline, or someone else.
"""
from __future__ import annotations

import argparse
import os
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.his_clock_check import to_utc  # noqa: E402
from backtest.his_race_curve import race2  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
TICKS = ROOT / "strategy_analysis" / "data" / "ustec_tick_days.pkl"
CACHE = ROOT / "strategy_analysis" / "data" / "nq_trades_windows.pkl"
DATASET, SCHEMA, SYMBOL, STYPE = "GLBX.MDP3", "trades", "NQ.v.0", "continuous"
GMT, WINTER = 5.0, 4.0
W = (5, 15, 30, 60, 120)
BIG = 5


def entries():
    x = pd.read_csv(ROOT / "strategy_analysis" / "statement_trades.csv", parse_dates=["open_time"])
    x = x[x.symbol.str.startswith("NASDAQ")].copy()
    x["utc"] = to_utc(x.open_time, WINTER, GMT)
    x["et"] = x.utc.dt.tz_localize("UTC").dt.tz_convert("America/New_York").dt.tz_localize(None)
    x["d"] = x.et.dt.normalize()
    x["t"] = (x.et - x.d - pd.Timedelta(hours=9, minutes=30)).dt.total_seconds()
    x["s"] = np.where(x.side.str.upper() == "BUY", 1, -1)
    return x.sort_values("utc", kind="stable").reset_index(drop=True)


def windows(x):
    """UTC windows, 22 min before to 20 min after each entry, merged per day."""
    w = sorted((r.utc - pd.Timedelta(minutes=22), r.utc + pd.Timedelta(minutes=20)) for r in x.itertuples())
    out = []
    for a, b in w:
        if out and a <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out


def client():
    if not os.environ.get("DATABENTO_API_KEY"):
        sys.exit("DATABENTO_API_KEY is not set in this environment. Set it as a user environment variable and "
                 "restart the app; it is never passed on the command line.")
    import databento as db
    return db.Historical()                               # reads the key from the environment itself


def cost(cl, wins):
    tot = 0.0
    for a, b in wins:
        tot += float(cl.metadata.get_cost(dataset=DATASET, symbols=[SYMBOL], schema=SCHEMA, stype_in=STYPE,
                                          start=a.isoformat() + "Z", end=b.isoformat() + "Z"))
    return tot


def fetch(cl, wins):
    C = pickle.loads(CACHE.read_bytes()) if CACHE.exists() else {}
    need = [w for w in wins if (str(w[0]), str(w[1])) not in C]
    for i, (a, b) in enumerate(need, 1):
        df = cl.timeseries.get_range(dataset=DATASET, symbols=[SYMBOL], schema=SCHEMA, stype_in=STYPE,
                                     start=a.isoformat() + "Z", end=b.isoformat() + "Z").to_df()
        df = df.reset_index()
        tcol = "ts_event" if "ts_event" in df.columns else df.columns[0]
        C[(str(a), str(b))] = pd.DataFrame({
            "ns": pd.to_datetime(df[tcol], utc=True).dt.tz_localize(None).astype("datetime64[ns]").astype("int64"),
            "size": df["size"].to_numpy(np.int64),
            "aggr": np.where(df["side"] == "B", 1, np.where(df["side"] == "A", -1, 0))})
        print(f"  fetched {i}/{len(need)} windows ({len(df):,} trades)", flush=True)
        CACHE.write_bytes(pickle.dumps(C))
    return pd.concat(C.values()).drop_duplicates().sort_values("ns", kind="stable").reset_index(drop=True)


def flow(T, at_ns):
    """Signed-by-nothing imbalance at each window w ending at at_ns: (imb, big)."""
    ns, sz, ag = T["ns"].to_numpy(), T["size"].to_numpy(), T["aggr"].to_numpy()
    cs = np.concatenate([[0], np.cumsum(sz * ag)])
    ct = np.concatenate([[0], np.cumsum(sz)])
    big = sz >= BIG
    cbs = np.concatenate([[0], np.cumsum(np.where(big, sz * ag, 0))])
    cbt = np.concatenate([[0], np.cumsum(np.where(big, sz, 0))])
    j = np.searchsorted(ns, at_ns, side="right")
    out = {}
    for w in W:
        i = np.searchsorted(ns, at_ns - w * 10**9, side="right")
        tot, bt = ct[j] - ct[i], cbt[j] - cbt[i]
        out[f"imb{w}"] = (cs[j] - cs[i]) / tot if tot > 0 else np.nan
        out[f"big{w}"] = (cbs[j] - cbs[i]) / bt if bt > 0 else np.nan
    return out


def main(argv=None):
    from scipy.stats import binomtest, wilcoxon
    ap = argparse.ArgumentParser()
    ap.add_argument("--cost", action="store_true", help="price the request and stop")
    ap.add_argument("--max-usd", type=float, default=25.0)
    ap.add_argument("--go", action="store_true", help="download even above --max-usd")
    a = ap.parse_args(argv)
    x = entries()
    wins = windows(x)
    cl = client()
    usd = cost(cl, wins)
    print(f"{len(x)} entries -> {len(wins)} merged windows, {sum((b - a_).total_seconds() for a_, b in wins) / 3600:.1f} "
          f"hours of {SYMBOL} {SCHEMA}: estimated cost ${usd:.2f}")
    if a.cost:
        return
    if usd > a.max_usd and not a.go:
        sys.exit(f"over the ${a.max_usd:.0f} limit - rerun with --go to accept ${usd:.2f}")
    T = fetch(cl, wins)

    ticks = pickle.loads(TICKS.read_bytes())
    rows = []
    for r in x.itertuples():
        day = ticks.get(r.d)
        if day is None or r.t < 960:
            continue
        ts, mid, _ = day
        base_ns = (r.d + pd.Timedelta(hours=9, minutes=30)).tz_localize("America/New_York").tz_convert("UTC")
        base_ns = base_ns.tz_localize(None).value
        others = x[x.d == r.d].t.to_numpy()
        starts = [("his", r.t)] + [("near", r.t + 60 * m) for m in list(range(-20, 0)) + list(range(1, 21))
                                   if r.t + 60 * m > 960 and np.min(np.abs(others - (r.t + 60 * m))) >= 60]
        for who, t in starts:
            f = flow(T, base_ns + int(t * 1e9))
            rows.append(dict(entry=r.Index, who=who, s=r.s, race=race2(ts, mid, t, r.s, 600, 7, 7),
                             race_up=race2(ts, mid, t, 1, 600, 7, 7), **f))
    D = pd.DataFrame(rows)
    H, N = D[D.who == "his"], D[D.who == "near"]
    out = [f"{len(H)} of his entries with futures trades in range; {len(N)} same-sitting moments; "
           f"{len(T):,} NQ trades in {len(wins)} windows (aggregates only - raw data stays local)"]

    out.append("\nA. DIRECTION - does the futures flow's sign agree with HIS side at his click?")
    out.append(f"  {'window':>7}{'all trades':>13}{'p':>8}{'5+ lots':>11}{'p':>8}")
    for w in W:
        cells = ""
        for k in (f"imb{w}", f"big{w}"):
            v = (H[k] * H.s).dropna()
            v = v[v != 0]
            ag = (v > 0).mean() if len(v) else np.nan
            p = binomtest(int((v > 0).sum()), len(v), 0.5).pvalue if len(v) else np.nan
            cells += f"{ag:>12.0%}{p:>8.3f}"
        out.append(f"  {w:>6}s{cells}")

    out.append("\nB. TIMING - his moment's flow (signed his way) ranked among the sitting's other moments")
    out.append(f"  {'window':>7}{'rank':>8}{'p':>8}")
    for w in W:
        rk = []
        for e, g in D.groupby("entry"):
            h, n = g[g.who == "his"], g[g.who == "near"]
            if len(h) and len(n) >= 10 and np.isfinite(h[f"imb{w}"].iat[0]):
                hv = h[f"imb{w}"].iat[0] * h.s.iat[0]
                nv = (n[f"imb{w}"] * n.s).dropna()
                rk.append((nv < hv).mean())
        p = wilcoxon(np.array(rk) - 0.5).pvalue if len(rk) > 5 else np.nan
        out.append(f"  {w:>6}s{np.mean(rk):>8.2f}{p:>8.3f}")

    out.append("\nC. A RULE ANYONE COULD RUN - at the sitting's moments, trade WITH strong flow (top decile of |imb|)")
    out.append(f"  {'window':>7}{'race won':>10}{'n':>6}   (base: the race in either direction is ~50%)")
    for w in W:
        k = f"imb{w}"
        v = N.dropna(subset=[k, "race_up"])
        v = v[v[k] != 0]
        cut = v[k].abs().quantile(0.9)
        top = v[v[k].abs() >= cut]
        won = np.where(np.sign(top[k]) > 0, top.race_up, 1 - top.race_up).astype(float)
        out.append(f"  {w:>6}s{np.mean(won):>9.0%}{len(won):>6}")
    txt = "\n".join(out)
    print(txt)
    (ROOT / "logs" / "his_tape.txt").write_text(txt, encoding="utf-8")


if __name__ == "__main__":
    main()
