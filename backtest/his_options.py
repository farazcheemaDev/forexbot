"""DOES HE READ THE OPTIONS TAPE? - aggressive QQQ options flow (0DTE first) in the seconds before his NASDAQ clicks (2026-10-12)

WHY      Everything about his trades is ordinary except the SIDE (his_burst_after.py: ordinary moments, ordinary pace -
         median 29 s to +7, = any move - and his side right 39 of 41). Nothing in NQ's price, tape or book, the futures-
         cash gap, bonds / FX / oil / gold / ES / RTY (his_strategy s37-s44), the calendar, posts or headline wires
         carries it. One market never looked at: OPTIONS. A large aggressive 0DTE call (put) buy leaves the dealer short
         delta, and the dealer buys (sells) NASDAQ futures over the next tens of seconds - an ordinary-paced move his
         way, with nothing in NQ beforehand. Options flow feeds are a common day-trader screen since 0DTE took off. The
         record is real-time (closing tickets follow a live broker counter, his_strategy s53), so whatever he reads
         exists live.

DATA     Databento OPRA.PILLAR `tcbbo` (every options trade with the consolidated bid / offer at that moment), parent
         QQQ.OPT. ~$0.62 per 10 minutes, so STAGE 1 fetches only 180 s before to 30 s after each click inside the options
         session (09:30-16:15 New York; holidays and evening clicks drop out). Priced with --cost before any download; the
         key comes from the environment only (his_tape.client). Raw data is reduced at download to time, bull premium and
         days to expiry, kept in the git-ignored data folder; only aggregates are committed.

SIGNAL   each options trade: aggressor +1 at or above the offer, -1 at or below the bid, 0 between; bullish sign = +1
         for a call, -1 for a put. Bull premium = aggressor x bullish x price x size x 100. Summed over w = 15 / 30 / 60 s
         before T, for 0DTE contracts (d0) and all expiries <= 7 days (d7).
TESTS    A  does the sign at his click agree with HIS side? (binomial vs 50%)
         B  did it TURN his way: his-side reading at the click minus the same reading 60 s earlier (Wilcoxon vs 0).
         IC every 5 s inside the fetched windows: bull premium over 30 s vs the Exness USTECm mid move over the next 60 s.

REGISTERED BEFORE ANY DATA IS FETCHED (2026-10-12)
    1. A: 50-65% for every feature.
    2. B: p > 0.05 for every feature.
    3. IC: |corr| < 0.10 for both expiry sets.
    LEAD LINE: any feature with A >= 70% and p < 0.01 -> STAGE 2 (the sittings' other moments and a bot rule on wider
    windows, priced first). Otherwise the options tape is ruled out as his source.

RESULT (2026-10-12, logs/his_options.txt; $16.04 of the user's Databento credit, with their OK) - RULED OUT.
    297,508 QQQ options trades in 31 windows; 40 of his clicks inside the options session. Data check: 82% of trades
    classified by aggressor, 66% 0DTE, bull share 51%.
    A: 38-55% agreement with his side (n 40, every p > 0.15) - prediction 1 "wrong" only below its floor (38%, 40%).
    B: no turn his way in the last minute (every p > 0.30).  IC with the next 60 s: 0DTE -0.001, <= 7 days +0.032.
    Aggressive options buying is not what tells him the side, and it does not predict NASDAQ's next minute either.

RESULT --ndx (2026-10-16, logs/his_options_ndx.txt; NDX + NDXP index options, $0.88 with the user's OK) - RULED OUT.
    12,314 trades in 31 windows, 40 clicks: bull-premium sign agrees with his side 49-57% (every p >= 0.43); no turn his
    way in the last minute (p >= 0.61); IC with the next 60 s +0.063 (0DTE and <= 7 days). Prediction 1 "wrong" only
    because one cell sat at 49%, a point under its 50% floor.

    python -m backtest.his_options --cost        price the request, download nothing
    python -m backtest.his_options               fetch (if within --max-usd) and test
"""
from __future__ import annotations

import argparse
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import backtest.his_tape as TP  # noqa: E402

DATASET, SCHEMA, SYMBOL, STYPE = "OPRA.PILLAR", "tcbbo", "QQQ.OPT", "parent"
SYMBOLS = [SYMBOL]
CACHE = ROOT / "strategy_analysis" / "data" / "qqq_opt_windows.pkl"
LOG = ROOT / "logs" / "his_options.txt"
PRE, POST = 120, 30
W = (15, 30, 60)


def session(d: pd.Timestamp):
    o = (d + pd.Timedelta(hours=9, minutes=30)).tz_localize("America/New_York").tz_convert("UTC").tz_localize(None)
    c = (d + pd.Timedelta(hours=16, minutes=15)).tz_localize("America/New_York").tz_convert("UTC").tz_localize(None)
    return o, c


def click_windows(x):
    """[click - PRE - 60, click + POST] in UTC, kept only when wholly inside 09:30-16:15 New York; merged."""
    out = []
    for r in x.itertuples():
        o, c = session(r.d)
        a, b = (r.utc - pd.Timedelta(seconds=PRE + 60)).floor("s"), (r.utc + pd.Timedelta(seconds=POST)).ceil("s")
        if a >= o and b <= c:
            out.append((a, b))
    out.sort()
    merged = []
    for a, b in out:
        if merged and a <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b))
        else:
            merged.append((a, b))
    return merged


def cost(cl, wins):
    """(total $, windows that resolve) - a window on an options holiday resolves no symbols and is dropped."""
    tot, ok = 0.0, []
    for a, b in wins:
        try:
            tot += float(cl.metadata.get_cost(dataset=DATASET, symbols=SYMBOLS, schema=SCHEMA, stype_in=STYPE,
                                              start=a.isoformat() + "Z", end=b.isoformat() + "Z"))
            ok.append((a, b))
        except Exception as e:  # noqa: BLE001
            print(f"  window {a} skipped: {str(e).splitlines()[0][:80]}")
    return tot, ok


def reduce(df: pd.DataFrame, day: pd.Timestamp) -> pd.DataFrame:
    """keep: time (ns), bull premium, days to expiry - parsed from the OSI symbol 'QQQ   YYMMDDCSSSSSSSS'."""
    df = df.reset_index()
    tcol = "ts_event" if "ts_event" in df.columns else df.columns[0]
    sym = df["symbol"].astype(str).str.replace(" ", "", regex=False)
    body = sym.str[-15:]
    exp = pd.to_datetime(body.str[:6], format="%y%m%d")
    cp = np.where(body.str[6] == "C", 1, -1)
    px, sz = df["price"].to_numpy(float), df["size"].to_numpy(float)
    bid, ask = df["bid_px_00"].to_numpy(float), df["ask_px_00"].to_numpy(float)
    ag = np.where(px >= ask, 1, np.where(px <= bid, -1, 0))
    return pd.DataFrame({
        "ns": pd.to_datetime(df[tcol], utc=True).dt.tz_localize(None).astype("datetime64[ns]").astype("int64").to_numpy(),
        "bull": ag * cp * px * sz * 100.0,
        "dte": (exp - day).dt.days.to_numpy()})


def fetch(cl, wins):
    C = pickle.loads(CACHE.read_bytes()) if CACHE.exists() else {}
    need = [w for w in wins if (str(w[0]), str(w[1])) not in C]
    for i, (a, b) in enumerate(need, 1):
        import time
        for attempt in range(1, 7):                                  # the gateway drops long streams now and then
            try:
                store = cl.timeseries.get_range(dataset=DATASET, symbols=SYMBOLS, schema=SCHEMA, stype_in=STYPE,
                                                start=a.isoformat() + "Z", end=b.isoformat() + "Z")
                df = store.to_df()
                break
            except Exception as e:  # noqa: BLE001
                if attempt == 6:
                    raise
                print(f"  window {i}: {type(e).__name__} - retry {attempt}", flush=True)
                time.sleep(10 * attempt)
        day = pd.Timestamp(a.tz_localize("UTC").tz_convert("America/New_York").date())
        C[(str(a), str(b))] = reduce(df, day)
        print(f"  fetched {i}/{len(need)} windows ({len(C[(str(a), str(b))]):,} options trades)", flush=True)
        CACHE.write_bytes(pickle.dumps(C))
    keys = {(str(a), str(b)) for a, b in wins}
    return pd.concat([v for k, v in C.items() if k in keys]).drop_duplicates().sort_values("ns", kind="stable").reset_index(drop=True)


def main(argv=None):
    from scipy.stats import binomtest, wilcoxon
    ap = argparse.ArgumentParser()
    ap.add_argument("--cost", action="store_true")
    ap.add_argument("--max-usd", type=float, default=10.0)
    ap.add_argument("--ndx", action="store_true", help="NDX + NDXP index options instead of QQQ (2026-10-16)")
    a = ap.parse_args(argv)
    global SYMBOLS, SYMBOL, CACHE, LOG
    if a.ndx:
        SYMBOLS, SYMBOL = ["NDX.OPT", "NDXP.OPT"], "NDX.OPT+NDXP.OPT"
        CACHE = ROOT / "strategy_analysis" / "data" / "ndx_opt_windows.pkl"
        LOG = ROOT / "logs" / "his_options_ndx.txt"
    x = TP.entries()
    cl = TP.client()
    usd, wins = cost(cl, click_windows(x))
    print(f"{len(x)} NASDAQ entries -> {len(wins)} windows in the options session, "
          f"{sum((b - a_).total_seconds() for a_, b in wins) / 60:.0f} min of {SYMBOL} {SCHEMA}: estimated ${usd:.2f}")
    if a.cost:
        return
    if usd > a.max_usd:
        sys.exit(f"over the ${a.max_usd:.0f} limit - not fetched")
    T = fetch(cl, wins)
    ns = T["ns"].to_numpy()
    sets = {"d0": T["dte"].to_numpy() == 0, "d7": T["dte"].to_numpy() <= 7}
    cums = {k: np.r_[0.0, np.cumsum(np.where(m, T["bull"].to_numpy(), 0.0))] for k, m in sets.items()}

    def read(at_ns, k, w):
        return cums[k][np.searchsorted(ns, at_ns, "right")] - cums[k][np.searchsorted(ns, at_ns - w * 10**9, "right")]

    def inside(t0):
        return any(a_ <= t0 - pd.Timedelta(seconds=PRE + 60) and t0 + pd.Timedelta(seconds=POST) <= b for a_, b in wins)

    rows = []
    for r in x.itertuples():
        if not inside(r.utc):
            continue
        at = r.utc.value
        f = {f"{k}_{w}": read(at, k, w) for k in sets for w in W}
        f.update({f"{k}_{w}_prev": read(at - 60 * 10**9, k, w) for k in sets for w in W})
        rows.append(dict(s=r.s, **f))
    D = pd.DataFrame(rows)
    out = [f"backtest/his_options.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; {len(T):,} {SYMBOL} options trades in "
           f"{len(wins)} windows (cost ${usd:.2f}); {len(D)} of his NASDAQ clicks inside the options session", "",
           "A = bull premium's sign agrees with HIS side at his click | B = his-side reading at the click minus 60 s earlier",
           f"  {'feature':>8}{'agree':>8}{'n':>5}{'p':>8}{'B median $':>12}{'p':>8}"]
    res = {}
    for k in [f"{k}_{w}" for k in sets for w in W]:
        v = D[k] * D.s
        nz = v[v != 0]
        ag = (nz > 0).mean() if len(nz) else np.nan
        pa = binomtest(int((nz > 0).sum()), len(nz), 0.5).pvalue if len(nz) else np.nan
        dlt = v - D[f"{k}_prev"] * D.s
        dlt = dlt[dlt != 0]
        pb = wilcoxon(dlt).pvalue if len(dlt) > 5 else np.nan
        res[k] = (ag, pa, pb)
        out.append(f"  {k:>8}{ag:>8.0%}{len(nz):>5}{pa:>8.3f}{(np.median(dlt) if len(dlt) else np.nan):>12,.0f}{pb:>8.3f}")
    # IC: every 5 s inside the windows, bull premium over 30 s vs the next 60 s on Exness
    ticks = pickle.loads(TP.TICKS.read_bytes())
    ic = {}
    for k in sets:
        xs, ys = [], []
        for a_, b in wins:
            d = pd.Timestamp(a_.tz_localize("UTC").tz_convert("America/New_York").date())
            day = ticks.get(d)
            if day is None:
                continue
            ts, mid, _ = day
            base = session(d)[0]
            for t0 in pd.date_range(a_ + pd.Timedelta(seconds=30), b, freq="5s"):
                tt = (t0 - base).total_seconds()
                i0, i1 = np.searchsorted(ts, tt, "right") - 1, np.searchsorted(ts, tt + 60, "right") - 1
                if i0 < 0 or i1 >= len(ts) - 1:
                    continue
                xs.append(read(t0.value, k, 30))
                ys.append(mid[i1] - mid[i0])
        ic[k] = (np.corrcoef(xs, ys)[0, 1] if len(xs) > 10 else np.nan, len(xs))
    out.append("")
    out.append("IC (bull premium over 30 s vs the next 60 s on Exness, every 5 s in the windows): " +
               ", ".join(f"{k} {c:+.3f} (n {n})" for k, (c, n) in ic.items()))
    A = [v[0] for v in res.values()]
    pbs = [v[2] for v in res.values()]
    lead = [k for k, v in res.items() if v[0] >= 0.70 and v[1] < 0.01]
    out += ["", "REGISTERED PREDICTIONS",
            f"  1 A within 50-65%: {min(A):.0%}..{max(A):.0%} -> {'RIGHT' if min(A) >= 0.5 and max(A) <= 0.65 else 'WRONG'}",
            f"  2 B p > 0.05 everywhere: min p {min(pbs):.3f} -> {'RIGHT' if min(pbs) > 0.05 else 'WRONG'}",
            "  3 |IC| < 0.10: " + ", ".join(f"{c:+.3f}" for c, _ in ic.values()) +
            f" -> {'RIGHT' if all(abs(c) < 0.10 for c, _ in ic.values()) else 'WRONG'}",
            f"  LEAD LINE (A >= 70%, p < 0.01): {', '.join(lead) if lead else 'none'}"]
    txt = "\n".join(out)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
