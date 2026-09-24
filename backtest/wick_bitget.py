"""THE CRASH-BID PAPER BOOK, REPLAYED ON BITGET'S OWN PRICES, 2022-2026 - instead of waiting 6 months.

The user, 2026-09-25, on wick_paper.py's 6-month verdict: "i cant wait for so long". The forward book
exists to answer two questions: does the edge exist on BITGET (the venue the money would be on), and
does it persist? The first does not need the future: Bitget's public history serves 1-minute candles
back to 2022 for every coin it still lists (checked 2026-09-25). This replays wick_paper.py's OWN code
(process_hour, settle_x120) hour by hour from 2022-01-01 to 2026-09-21 on both venues:
  - UNIVERSE  the backtest's point-in-time top-40 by Binance's prior-month volume (wide_book, dead
              coins included); the same 40 coins on both venues.
  - LABEL     btc_regime's BEAR days get no bids (the paper book's rule).
  - HOURS     every hour in which some coin's hourly low went 0.1% through 90% of the previous close
              on EITHER venue (Binance: the local 1h data; Bitget: its 1H history) - any other hour
              cannot fill a bid, so it is skipped. Those hours get 1-minute bars from each venue.
  - DEAD ON BITGET  a coin Bitget no longer lists (OM, MKR, FTM, EOS...) cannot be fetched there. Left
              out, the Bitget ledger would never hold the coins that died - the flattering direction.
              So those coins use BINANCE's 1-minute bars inside the Bitget ledger, and are counted.

REGISTERED PREDICTION (2026-09-25, before running): over 2022-2026 the Bitget ledger's mean per kept
fill is within 0.5 points of Binance's; Bitget has 80-90% of Binance's fills before the cap; both are
negative in 2026 H1; the Bitget $300 ledger grows within +-5 points a year of Binance's, and its
worst in-hour paper loss is no deeper than -20%.

    python -m backtest.wick_bitget
"""
from __future__ import annotations

import json
import pickle
import sys
import tempfile
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import wick_paper as w  # noqa: E402
from backtest.crash_buy import CUT, PEN, load_1h  # noqa: E402
from backtest.market_neutral import drop_non_crypto  # noqa: E402
from backtest.wick_better import load_all  # noqa: E402
from backtest.wide_book import eligibility  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "strategy_analysis" / "data"
H1C = DATA / "bitget_1h_cache.pkl"
M1C = DATA / "wick1m_cache.pkl"
START, END = pd.Timestamp("2022-01-01"), pd.Timestamp("2026-09-21")
HOUR = pd.Timedelta(hours=1)
NB = 186                                   # 1-minute bars from H - 1 min: the hour + the +120 exit


def get(u):
    for a in range(4):
        try:
            with urllib.request.urlopen(u, timeout=25) as r:
                return json.loads(r.read().decode())
        except Exception:
            time.sleep(1.0 + a)
    return None


def bitget_1h(name, t0, t1):
    """Bitget 1H candles [t0, t1) as a DataFrame (time, low, close), paged 200 hours at a time."""
    rows, t = [], t0
    while t < t1:
        e = min(t + 200 * w.HOUR_MS, t1)
        d = get(f"{w.BG}/history-candles?symbol={name}&productType=USDT-FUTURES&granularity=1H"
                f"&startTime={t}&endTime={e}&limit=200")
        rows += [[int(r[0]), float(r[3]), float(r[4])] for r in ((d or {}).get("data") or [])]
        t = e
        time.sleep(0.02)
    if not rows:
        return None
    df = pd.DataFrame(rows, columns=["t", "low", "close"]).drop_duplicates("t").sort_values("t")
    df["time"] = pd.to_datetime(df.t, unit="ms")
    return df


def minutes_raw(venue, name, H):
    t0 = H - w.MIN_MS
    if venue == "binance":
        d = get(f"https://fapi.binance.com/fapi/v1/klines?symbol={name}&interval=1m&startTime={t0}&limit={NB}")
        rows = [[int(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4])] for r in (d or [])]
    else:
        d = get(f"{w.BG}/history-candles?symbol={name}&productType=USDT-FUTURES&granularity=1m"
                f"&startTime={t0}&endTime={t0 + NB * w.MIN_MS}&limit=200")
        rows = [[int(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4])]
                for r in ((d or {}).get("data") or [])]
    rows = sorted({r[0]: r for r in rows if t0 <= r[0] < t0 + NB * w.MIN_MS}.values())
    return np.array(rows) if rows else None


def cached(path, keys, fn, label):
    c = pickle.loads(path.read_bytes()) if path.exists() else {}
    todo = [k for k in keys if k not in c]
    for a in range(0, len(todo), 400):
        chunk = todo[a:a + 400]
        with ThreadPoolExecutor(6) as ex:
            for k, v in zip(chunk, ex.map(lambda k: fn(*k), chunk)):
                c[k] = v
        path.write_bytes(pickle.dumps(c))
        print(f"    {label}: {a + len(chunk)} / {len(todo)}", flush=True)
    return c


def main():
    el = drop_non_crypto(eligibility(40))
    months = [m.strftime("%Y-%m") for m in pd.period_range(START, END, freq="M")]
    uni = {m: sorted(s for s, ms in el.items() if m in ms) for m in months}
    coins = sorted({s for m in months for s in uni[m]})
    _, reg, bear_day = load_all()
    bear = {d.strftime("%Y-%m-%d"): bool(v) for d, v in bear_day.items()}
    listed = w.bitget_listed()
    bname = {s: w.bitget_name(s, listed) for s in coins}
    print(f"{len(coins)} coins in the top-40 over {months[0]}..{months[-1]}; Bitget lists "
          f"{sum(1 for v in bname.values() if v)} of them today\n", flush=True)

    def ok_hour(s, t):
        return t.strftime("%Y-%m") in uni and s in uni[t.strftime("%Y-%m")] and not bear.get(t.strftime("%Y-%m-%d"), False)

    # candidate hours - Binance from the local 1h files
    cand = set()
    for s in coins:
        d = load_1h(s)
        if d is None:
            continue
        d = d[(d.time >= START - HOUR) & (d.time < END)].reset_index(drop=True)
        gap = d.time.diff() == HOUR
        hit = gap & (d.low < d.close.shift(1) * (1 - w.BID_K) * (1 - PEN))
        for t in d.time[hit]:
            if ok_hour(s, t):
                cand.add((s, t))
    n_bn = len(cand)
    # candidate hours - Bitget from its 1H history, for the months each coin was eligible
    spans = {}
    for s in coins:
        ms = [m for m in months if s in uni[m]]
        if bname[s] and ms:
            a = pd.Timestamp(ms[0] + "-01") - HOUR
            b = min(pd.Timestamp(ms[-1] + "-01") + pd.offsets.MonthBegin(1), END)
            spans[s] = (int(a.value // 10**6), int(b.value // 10**6))
    h1 = cached(H1C, [(bname[s], a, b) for s, (a, b) in spans.items()], bitget_1h, "Bitget 1H")
    bg_hours = 0
    for s, (a, b) in spans.items():
        d = h1.get((bname[s], a, b))
        if d is None:
            continue
        d = d.reset_index(drop=True)
        gap = d.time.diff() == HOUR
        hit = gap & (d.low < d.close.shift(1) * (1 - w.BID_K) * (1 - PEN))
        for t in d.time[hit]:
            if ok_hour(s, t):
                bg_hours += 1
                cand.add((s, t))
    hours = sorted({t for _, t in cand})
    print(f"candidate coin-hours: Binance {n_bn}, Bitget {bg_hours}, union {len(cand)} in {len(hours)} hours", flush=True)

    # 1-minute bars for every candidate coin-hour, both venues (Bitget: its own name, if it lists the coin)
    keys = [("binance", s, int(t.value // 10**6)) for s, t in cand]
    keys += [("bitget", bname[s], int(t.value // 10**6)) for s, t in cand if bname[s]]
    m1 = cached(M1C, keys, minutes_raw, "1-minute")

    back = {"n": 0, "coins": set()}

    def find(arrs, t0, n):
        want = t0 + np.arange(n) * w.MIN_MS
        for a in arrs:
            if a is None or not len(a):
                continue
            idx = {int(r[0]): r for r in a}
            if all(int(x) in idx for x in want):
                return [list(idx[int(x)]) for x in want]
        return None

    def fetch(venue, sym, t0, n):
        H = (t0 + w.MIN_MS) // w.HOUR_MS * w.HOUR_MS
        hs = (H, H - w.HOUR_MS, H - 2 * w.HOUR_MS, H - 3 * w.HOUR_MS)    # a fill hour's array covers +120
        bn = [m1.get(("binance", sym, h)) for h in hs]
        if venue == "binance":
            r = find(bn, t0, n)
        else:
            r = find([m1.get(("bitget", bname[sym], h)) for h in hs], t0, n) if bname.get(sym) else None
            if r is None:                              # Bitget cannot serve this coin: Binance stands in
                r = find(bn, t0, n)
                if r is not None and n == 61:
                    back["n"] += 1
                    back["coins"].add(sym + ("" if bname.get(sym) else "*"))
                    back.setdefault("keys", set()).add((sym, H))
        if r is None and n == 61:                      # no bars kept: this coin cannot fill this hour
            return [[t0 + k * w.MIN_MS, 1.0, 1.0, 1.0, 1.0] for k in range(n)]
        return r

    w.time.sleep = lambda s: None
    w.set_dir(Path(tempfile.mkdtemp(prefix="wick_bitget_")))
    st = w.fresh()
    st["universes"] = uni
    st["labels"] = {d: ("bear" if v else "replay") for d, v in bear.items()}
    all_names = set(coins)
    for i, t in enumerate(hours):
        H = int(t.value // 10**6)
        w.process_hour(st, H, fetch=fetch, listed=all_names)
        w.settle_x120(st, H + 4 * w.HOUR_MS, fetch=fetch)
    w.settle_x120(st, 10**15, fetch=fetch)
    print(f"\nreplayed {len(hours)} hours; Bitget ledger used Binance bars for {back['n']} coin-hours on "
          f"{len(back["coins"])} coins Bitget did not serve (* = not listed there today; {', '.join(sorted(c.replace('USDT', '') for c in back['coins']))[:400]})\n")

    F = pd.read_csv(w.P["fills"])
    F["t"] = pd.to_datetime(F.hour)
    Hr = pd.read_csv(w.P["hours"])
    Hr["t"] = pd.to_datetime(Hr.hour)
    X = pd.read_csv(w.P["exits"]) if w.P["exits"].exists() else pd.DataFrame()
    out = ROOT / "logs" / "wick_bitget_fills.csv.gz"
    F.to_csv(out, index=False, compression="gzip")
    grid = pd.date_range(START, END, freq="D")
    print(f"{'':<9}{'fills':>7}{'kept':>6}{'per kept fill':>15}{'se':>6}{'median':>8}{'losing':>8}"
          f"{'$300 ->':>10}{'CAGR':>8}{'worst mo':>10}{'worst hour':>12}{'+120 per fill':>15}{'+120 $300 ->':>14}")
    for v in w.VENUES:
        L = st["led"][v]
        k = F[(F.venue == v) & (F.kept == 1)]
        eq = Hr[Hr.venue == v].set_index("t").equity
        c = eq[~eq.index.duplicated(keep="last")].resample("D").last().reindex(grid).ffill().fillna(300.0)
        y = (c.index[-1] - c.index[0]).days / 365.25
        me = c.resample("ME").last().pct_change().dropna()
        x = X[X.venue == v] if len(X) else X
        print(f"{v.upper():<9}{L['fills']:>7}{L['kept']:>6}{k.net.mean()*100:>+14.2f}%{k.net.std()/np.sqrt(len(k))*100:>6.2f}"
              f"{k.net.median()*100:>+7.2f}%{(k.net < 0).mean()*100:>7.0f}%${L['equity']:>9,.0f}"
              f"{((L['equity'] / 300) ** (1 / y) - 1) * 100:>+7.1f}%{me.min()*100:>+9.1f}%{L['worst_hour']*100:>+11.1f}%"
              f"{(x.net.mean()*100 if len(x) else float('nan')):>+14.2f}%${L['eq120']:>12,.0f}")
    print("\nPER KEPT FILL BY HALF-YEAR (after 38bp): Bitget / Binance, and kept fills")
    for (yr, h2), g in F[F.kept == 1].groupby([F.t.dt.year, F.t.dt.month > 6]):
        b, n = g[g.venue == "bitget"], g[g.venue == "binance"]
        print(f"  {yr} H{2 if h2 else 1}:  Bitget {b.net.mean()*100:+6.2f}% ({len(b):>3})   Binance {n.net.mean()*100:+6.2f}% ({len(n):>3})")
    for lab, g in (("TUNE, to 2024-08-28", F[F.t < CUT]), ("HOLDOUT, from 2024-08-29", F[F.t >= CUT]),
                   ("LAST 12 MONTHS", F[F.t >= END - pd.Timedelta(days=365)])):
        b, n = g[(g.venue == "bitget") & (g.kept == 1)], g[(g.venue == "binance") & (g.kept == 1)]
        print(f"  {lab:<26} Bitget {b.net.mean()*100:+.2f}% ({len(b)}), Binance {n.net.mean()*100:+.2f}% ({len(n)}); "
              f"fills before the cap Bitget {len(g[g.venue == 'bitget'])} / Binance {len(g[g.venue == 'binance'])}")
    by_h = F[F.kept == 1].pivot_table(index="hour", columns="venue", values="net", aggfunc="sum").fillna(0.0) / 40
    print(f"\n  hour-by-hour P&L (share of equity per bid summed): correlation Bitget vs Binance {by_h.corr().iloc[0, 1]:+.2f}")
    print(f"  the fills: {out.relative_to(ROOT)}")
    # the venue question on REAL Bitget bars only: kept Bitget fills whose bars are Bitget's own,
    # paired with the same coin-hour on Binance when Binance kept it too
    F["H"] = (F.t - pd.Timestamp("1970-01-01")) // pd.Timedelta(milliseconds=1)   # unit-proof (CLAUDE.md s3)
    assert F.H.min() > 1.6e12, "hour keys are not milliseconds"
    fb = back.get("keys", set())
    F["stand_in"] = [(v == "bitget") and ((s, h) in fb) for v, s, h in zip(F.venue, F.sym, F.H)]
    kb = F[(F.venue == "bitget") & (F.kept == 1)]
    nat, sub = kb[~kb.stand_in], kb[kb.stand_in]
    print()
    print(f"  Bitget kept fills on Bitget's OWN bars: {len(nat)}, mean {nat.net.mean()*100:+.2f}% (se "
          f"{nat.net.std()/np.sqrt(len(nat))*100:.2f}), median {nat.net.median()*100:+.2f}% | on Binance stand-in "
          f"bars: {len(sub)}, mean {sub.net.mean()*100:+.2f}%")
    kn = F[(F.venue == "binance") & (F.kept == 1)].set_index(["sym", "hour"]).net
    pair = nat.set_index(["sym", "hour"]).net.to_frame("bitget").join(kn.rename("binance"), how="inner")
    d = pair.bitget - pair.binance
    print(f"  the same coin-hour kept on both venues (Bitget's own bars): {len(pair)} pairs, Bitget "
          f"{pair.bitget.mean()*100:+.2f}% vs Binance {pair.binance.mean()*100:+.2f}%, difference "
          f"{d.mean()*100:+.2f} (se {d.std()/np.sqrt(len(d))*100:.2f})")
    for lab, g in (("TUNE", nat[nat.t < CUT]), ("HOLDOUT", nat[nat.t >= CUT])):
        print(f"  Bitget own bars, {lab}: {len(g)} kept fills, mean {g.net.mean()*100:+.2f}%")


if __name__ == "__main__":
    main()
