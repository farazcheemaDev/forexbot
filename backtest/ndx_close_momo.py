"""NASDAQ'S LAST HOUR FOLLOWS ITS FIRST - "market intraday momentum", the council's one remaining test (2026-10-12)

THE COUNCIL (2026-10-12): scalping NASDAQ is dead because short-horizon entries carry no direction (cfd_scalp.py); the
only minute-scale effect with a FORCED counterparty is the close: option dealers short gamma and leveraged ETFs must
trade in the day's direction near 16:00 ET (Gao, Han, Li, Zhou 2018 "Market intraday momentum", JFE: the first
half-hour's return, from the previous close, predicts the last half-hour's; Baltussen, Da, Lammers, Martens 2021:
stronger when dealers are short gamma). One registered test, flat before the close (no swap), with a kill line: if it
fails, NASDAQ scalping is closed for good.

DATA     A  NQ futures 1h bars, 2024-04-19 .. 2026-09-11 (strategy_analysis/data/NQ_1h_730d.csv; labels are New York time:
            the 17:00 bar is the daily halt). First window = previous 16:00 -> 10:00 ET; trade the 15:00-16:00 ET hour.
         B  Exness USTECm 5m bars, 2025-09 .. 2026-09 (MT5 cache, UTC) - the paper's exact half-hours: previous 16:00 ->
            10:00 ET, trade 15:30-16:00 ET. Overlaps A in time: a check on the instrument, not a second sample.
RULES    S1  every day: the sign of the first window
         S2  only days whose |first window| is in the top third (threshold from the TUNE days only)
         S3  the sign of (first window + the 14:00-15:00 ET hour on A / 15:00-15:30 on B) - the paper's second predictor
COSTS    0.8bp a round trip (USTECm's spread); flat before 16:00 ET, so no swap.
CONTROLS ALWAYS LONG the same last window (the drift); and the hit rate a coin would get (50%).
PASS     net > 0 with t >= 2 on BOTH halves (60/40 by date) of A, and above ALWAYS LONG on both halves.

REGISTERED BEFORE THE RUN (2026-10-12)
    C1  On A, S1 calls the last hour's sign right on 52-56% of days and nets +1..+4bp a day - but with ~600 days it does
        not reach t >= 2 on both halves: no rule PASSES (the test has power only for an edge of ~5bp a day or more).
    C2  ALWAYS LONG the last hour nets between -1 and +3bp a day.
    C3  B (Exness, the exact half-hours) gives S1 the same sign of edge as A.
    C4  S2 (big first windows) earns at least twice S1's edge a trade.

RESULT (2026-10-11 23:52 UTC, logs/ndx_close_momo.txt) - DEAD; by the kill line, NASDAQ scalping is closed
    - A (NQ futures, 588 days 2024-04 .. 2026-09): the first window says nothing about the last hour - correlation -0.005.
      S1 right 53.2%, +0.26bp a day (tune -0.39 / holdout +1.22bp, t -0.19 / +0.54); S2 (big first windows) -0.24bp;
      S3 -1.76bp. No rule passes. C1 WRONG on size (+0.26bp, under the +1..+4 written), right that nothing passes.
    - C2 WRONG: always-long the last hour -1.25bp a day (predicted -1..+3).
    - B (Exness USTECm, the paper's exact half-hours, 242 days): S1 +0.41bp a day, tune -2.59bp / holdout +4.89bp - the
      halves flip sign; S3 the same (-2.74 / +5.90). C3 RIGHT (same sign as A, both ~0). C4 WRONG: big days are worse.
    Reading: the published effect (SPY 1993-2013) is not in NASDAQ's last hour in 2024-2026. With cfd_scalp.py (no
    direction in 1m/5m entries), ustec_seconds.py (0.14bp vs a 0.82bp spread) and nq_leadlag.py (no lag), every
    horizon from seconds to the session close is now tested on NASDAQ. Scalping NASDAQ is closed.

    python -m backtest.ndx_close_momo
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "strategy_analysis" / "data"
LOG = ROOT / "logs" / "ndx_close_momo.txt"
COST = 0.8e-4
TUNE = 0.60


def days_from(bars: pd.DataFrame, first_end: str, last_start: str, mid_start: str, close: str = "16:00") -> pd.DataFrame:
    """bars: index = New York local time of the bar's START, columns o/c. Per day: r_first (prev close -> first_end),
    r_mid (mid_start -> last_start), r_last (last_start -> close)."""
    t = bars.index
    out = []
    by_day = {d: g for d, g in bars.groupby(t.normalize())}
    days = sorted(by_day)
    prev_close = None
    for d in days:
        g = by_day[d]
        tod = g.index.strftime("%H:%M")

        def px_at(hhmm, field="o"):            # price at hh:mm = the open of the bar starting then
            m = g[tod == hhmm]
            return float(m[field].iloc[0]) if len(m) else None

        def close_before(hhmm):                 # close of the bar that ends at hh:mm
            m = g[g.index < pd.Timestamp(f"{d:%Y-%m-%d} {hhmm}")]
            return float(m.c.iloc[-1]) if len(m) else None

        c_close = close_before(close)
        p_first = px_at(first_end)
        p_mid, p_last = px_at(mid_start), px_at(last_start)
        ok = all(v is not None for v in (c_close, p_first, p_mid, p_last)) and prev_close is not None
        if ok and (g.index.max() >= pd.Timestamp(f"{d:%Y-%m-%d} {close}") - pd.Timedelta(minutes=60)):
            out.append(dict(day=d, r_first=p_first / prev_close - 1, r_mid=p_last / p_mid - 1, r_last=c_close / p_last - 1))
        if c_close is not None:
            prev_close = c_close
    return pd.DataFrame(out).set_index("day")


def evaluate(D: pd.DataFrame, tag: str, lines: list, thr=None):
    cut = D.index[int(len(D) * TUNE)]
    tu = D.index < cut
    if thr is None:
        thr = D.r_first[tu].abs().quantile(2 / 3)
    rules = {
        "S1 sign(first)": np.sign(D.r_first),
        "S2 sign(first), big days": np.where(D.r_first.abs() >= thr, np.sign(D.r_first), 0.0),
        "S3 sign(first + mid)": np.sign(D.r_first + D.r_mid),
        "ALWAYS LONG": np.ones(len(D)),
    }
    lines.append(f"{tag}: {len(D)} days {D.index.min():%Y-%m-%d} .. {D.index.max():%Y-%m-%d}, holdout from {cut:%Y-%m-%d}; "
                 f"last window |move| median {D.r_last.abs().median() * 1e4:.1f}bp; corr(first, last) "
                 f"{D.r_first.corr(D.r_last):+.3f}")
    res = {}
    for nm, s in rules.items():
        s = pd.Series(s, index=D.index)
        on = s != 0
        net = (s * D.r_last - COST)[on]
        hit = (np.sign(D.r_last[on]) == s[on]).mean()
        row = {}
        for half, m in (("tune", net.index < cut), ("hold", net.index >= cut)):
            x = net[m]
            row[half] = (x.mean(), x.mean() / (x.std(ddof=1) / np.sqrt(len(x))) if len(x) > 2 else np.nan, len(x))
        res[nm] = dict(n=len(net), mean=net.mean(), hit=hit, **row)
        lines.append(f"  {nm:26} {len(net):4} days | right {hit * 100:4.1f}% | net {net.mean() * 1e4:+6.2f}bp a day | tune "
                     f"{row['tune'][0] * 1e4:+6.2f}bp (t {row['tune'][1]:+.2f}) | holdout {row['hold'][0] * 1e4:+6.2f}bp (t {row['hold'][1]:+.2f})")
    lo = res["ALWAYS LONG"]
    for nm in ("S1 sign(first)", "S2 sign(first), big days", "S3 sign(first + mid)"):
        r = res[nm]
        r["PASS"] = (r["tune"][0] > 0 and r["hold"][0] > 0 and r["tune"][1] >= 2 and r["hold"][1] >= 2
                     and r["tune"][0] > lo["tune"][0] and r["hold"][0] > lo["hold"][0])
    lines.append("  PASS: " + (", ".join(k for k in res if res[k].get("PASS")) or "none"))
    lines.append("")
    return res, thr


def main():
    lines = [f"backtest/ndx_close_momo.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; cost {COST * 1e4:.1f}bp a round trip, "
             f"flat by 16:00 ET", ""]
    a = pd.read_csv(DATA / "NQ_1h_730d.csv", parse_dates=["time"]).rename(columns={"open": "o", "close": "c"}).set_index("time")
    a = a[a.index.dayofweek < 5]
    A = days_from(a[["o", "c"]], first_end="10:00", last_start="15:00", mid_start="14:00")
    resA, _ = evaluate(A, "A  NQ futures, 1h (first: prev close -> 10:00 ET; trade 15:00-16:00 ET)", lines)
    b = pd.DataFrame(json.load(open(DATA / "USTECm_5m_2400d.json")))
    b.index = pd.to_datetime(b.t, unit="ms").dt.tz_localize("UTC").dt.tz_convert("America/New_York").dt.tz_localize(None)
    b = b[b.index.dayofweek < 5]
    B = days_from(b[["o", "c"]], first_end="10:00", last_start="15:30", mid_start="15:00")
    resB, _ = evaluate(B, "B  Exness USTECm, 5m (first: prev close -> 10:00 ET; trade 15:30-16:00 ET)", lines)
    s1a, s1b, s2a = resA["S1 sign(first)"], resB["S1 sign(first)"], resA["S2 sign(first), big days"]
    lines.append("REGISTERED PREDICTIONS")
    passes = [k for k in resA if resA[k].get("PASS")]
    c1 = 0.52 <= s1a["hit"] <= 0.56 and 0.0001 <= s1a["mean"] <= 0.0004 and not passes
    lines.append(f"  C1 A, S1: right {s1a['hit'] * 100:.1f}%, net {s1a['mean'] * 1e4:+.2f}bp a day; passes {passes or 'none'} -> "
                 f"{'RIGHT' if c1 else 'WRONG'}")
    lo = resA["ALWAYS LONG"]["mean"]
    lines.append(f"  C2 ALWAYS LONG the last hour: {lo * 1e4:+.2f}bp a day -> {'RIGHT' if -0.0001 <= lo <= 0.0003 else 'WRONG'}")
    lines.append(f"  C3 Exness S1 {s1b['mean'] * 1e4:+.2f}bp vs NQ S1 {s1a['mean'] * 1e4:+.2f}bp -> "
                 f"{'RIGHT' if np.sign(s1b['mean']) == np.sign(s1a['mean']) else 'WRONG'}")
    lines.append(f"  C4 S2 {s2a['mean'] * 1e4:+.2f}bp vs S1 {s1a['mean'] * 1e4:+.2f}bp a trade -> "
                 f"{'RIGHT' if s1a['mean'] > 0 and s2a['mean'] >= 2 * s1a['mean'] else 'WRONG'}")
    txt = "\n".join(lines)
    print(txt)
    LOG.write_text(txt + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
