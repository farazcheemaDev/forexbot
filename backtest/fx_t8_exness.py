"""T8 (MONTH-END USD REBALANCING) RE-CHECKED ON EXNESS'S OWN PRICES (2026-10-12)

WHY. fx_anomalies.py's T8 was killed on 2026-09-25 (+4.13bp a month, t +1.15, Holm 0.999, tune +6.67 / holdout +0.33,
right sign 128 of 234 months; logs/fx_anomalies.txt) - measured on Yahoo's EURUSD=X daily closes. On 2026-10-11
fx_capit.py found those bars broken: the open sits ~27bp from the previous close (Exness ~1bp) and a Yahoo bar dated D
matches Exness's session D-1 (daily-return correlation 0.948 at a one-day shift, 0.05 unshifted). So T8's "last trading
day" return was largely the day BEFORE the month-end - the wrong day for a month-end-fix effect. Rule 9: a kill is
permanent unless the measurement was broken; this one was, so it is re-measured. fx_anomalies.py is left unchanged.

THE TEST (T8 exactly as defined, measurement fixed)
    Melvin-Prins (2015): foreign holders re-hedge their USD equity gains at the month-end fix. If US equities beat
    European ones month-to-date, USD is sold into the last day -> EURUSD up; else down.
    signal   S&P 500 vs EURO STOXX 50 month-to-date, each from its last close of the previous month to its last close
             at or before the day before the month's last forex day (Yahoo index bars - index closes are sound)
    trade    EURUSD from the close of the day before the month's last forex day to the close of that day, on EXNESS
             daily bars (backtest/fx_capit.exness_csv: MT5 1h -> forex days closing 17:00 New York), 2020-02 .. 2026-09
    costs    1.0bp round trip + the swap of the side held (long -0.51bp a night, short 0; Exness 2026-10-12)
    verdict  as the family: net > 0 on both halves (60/40 by date) and Holm p < 0.05 across the nine (the other eight
             keep their 2026-09-25 p-values)
ALSO REPORTED (not the verdict)
    A  Yahoo T8 as published, on the same months - how far off the broken measurement was
    B  Yahoo realigned by one day (its bar dated D+1 = Exness's day D), checked on the overlap first, then 2003-2026 -
       the long history with the right day, IF the realignment holds
    C  to the fix: Exness close of the day before -> the 16:00 London fix on the last day (the mechanism's own clock)

REGISTERED BEFORE THE RUN (2026-10-12)
    M1  On Exness 2020-2026 (~79 months) T8 stays within 2 se of zero: the kill stands; right sign in 45-60% of months.
    M2  The broken measurement was materially off: on the same months Yahoo's T8 and Exness's differ by more than 3bp a
        month on average.
    M3  Yahoo realigned by a day matches Exness on the overlap (daily-return correlation > 0.9), and over 2003-2026 the
        corrected T8 still fails (Holm p > 0.05 or a half <= 0).
    M4  To the fix it is within 2 se of zero as well.

RESULT (2026-10-11 23:35 UTC, logs/fx_t8_exness.txt) - THE KILL STANDS, now on a sound measurement
    - VERDICT (M1 RIGHT): on Exness's own prices, 78 month-ends 2020-02 .. 2026-09: -4.06bp a month net (gross -2.72bp),
      t -0.83, right sign 43 of 78 (55%), tune -14.75 / holdout +11.31bp; family Holm p 1.000. FAIL.
    - A (M2 RIGHT): the published Yahoo measurement read a DIFFERENT DAY - on the same 78 months it made +4.40bp where
      Exness makes -4.06bp, month by month 54.9bp apart on average, correlation -0.18, the same sign in 49% of months.
    - B (M3 RIGHT): Yahoo moved one day earlier matches Exness (daily-return correlation 0.947 on 1,702 days; the first
      run shifted the wrong way and read -0.002 - my bug, fixed before anything was concluded). On the right day the
      whole 2003-2026 history gives -4.74bp a month (t -1.20), right sign 112 of 233, BOTH halves negative (-4.85 /
      -4.57); on Exness's own months -5.14bp, beside Exness's -4.06bp.
    - C (M4 RIGHT): to the 16:00 London fix, the mechanism's own clock: -3.81bp a month (t -0.97), right sign 40 of 78.
    Reading: the original +4.13bp (right in 128 of 234 months) came from the day BEFORE the month-end. Measured on the
    month-end itself the trade is slightly negative over 23 years. Melvin-Prins' month-end USD flow is not tradable on
    EURUSD at Exness, and the 2026-09-25 verdict stands for a sound reason now.

    python -m backtest.fx_t8_exness
"""
from __future__ import annotations

import json
import sys
from math import erf, sqrt
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest import fx_capit  # noqa: E402
from backtest.fx_anomalies import yf_daily  # noqa: E402

LOG = ROOT / "logs" / "fx_t8_exness.txt"
SPREAD, SWAP_LONG, SWAP_SHORT = 1.0, -0.51, 0.0          # bp; swap: negative = you pay
TUNE = 0.60
# the t of the other nine rows of logs/fx_anomalies.txt (2026-09-25), in order: NDX overnight, NDX intraday, NDX turn of
# month, SPX overnight, SPX intraday, SPX turn of month, gold outside NY, silver outside NY, FX home-hours. The family's
# Holm ran over all ten rows (fx_anomalies.main), so T8 is adjusted against these nine.
OTHER_T = (-0.31, 0.74, 1.43, -4.44, 1.30, 1.15, -0.16, -1.76, -3.36)


def p_one(t):
    return 1 - 0.5 * (1 + erf(t / sqrt(2)))


def holm(p_t8, others):
    ps = sorted(others + [p_t8])
    m = len(ps)
    adj, run = {}, 0.0
    for r, p in enumerate(ps):
        run = max(run, min(1.0, p * (m - r)))
        adj.setdefault(p, run)
    return adj[p_t8]


def nights(a, b):
    return max((pd.Timestamp(b).normalize() - pd.Timestamp(a).normalize()).days, 0)


def signal(spx, sx5, month_start, upto):
    """+1 if the S&P beat the STOXX 50 from the previous month's last close to the last close at or before `upto`."""
    out = []
    for d in (spx, sx5):
        prev = d.Close[d.index < month_start]
        cur = d.Close[(d.index >= month_start) & (d.index <= upto)]
        if not len(prev) or not len(cur):
            return None
        out.append(cur.iloc[-1] / prev.iloc[-1] - 1)
    return 1 if out[0] > out[1] else -1


def t8(fx: pd.DataFrame, spx, sx5, label):
    """fx: daily bars indexed by forex-day label, column Close. One trade per month: the last forex day's close-to-close."""
    per = fx.index.to_period("M")
    rows = []
    for m in per.unique():
        days = fx.index[per == m]
        if len(days) < 15:
            continue
        L = days[-1]
        k = fx.index.get_loc(L)
        if k == 0:
            continue
        P = fx.index[k - 1]
        sgn = signal(spx, sx5, m.start_time, P)
        if sgn is None:
            continue
        g = fx.Close.iloc[k] / fx.Close.iloc[k - 1] - 1
        swap = SWAP_LONG if sgn > 0 else SWAP_SHORT
        net = sgn * g - SPREAD / 1e4 + swap / 1e4 * nights(P, L)
        rows.append((L, sgn, g, net))
    r = pd.DataFrame(rows, columns=["day", "sgn", "gross", "net"]).set_index("day")
    return r


def stats(r):
    x = r.net.to_numpy()
    cut = r.index[int(len(r) * TUNE)]
    a, b = r.net[r.index < cut], r.net[r.index >= cut]
    t = x.mean() / (x.std(ddof=1) / np.sqrt(len(x)))
    return dict(n=len(x), mean=x.mean() * 1e4, t=t, p=p_one(t), tune=a.mean() * 1e4, hold=b.mean() * 1e4,
                hits=int((r.sgn * r.gross > 0).sum()), cut=cut)


def fmt(s, name):
    return (f"  {name:44} n {s['n']:3} | net {s['mean']:+6.2f}bp a month (t {s['t']:+.2f}, one-sided p {s['p']:.3f}) | tune "
            f"{s['tune']:+6.2f} / holdout {s['hold']:+6.2f}bp (split {s['cut']:%Y-%m}) | right sign {s['hits']}/{s['n']}")


def main():
    spx, sx5 = yf_daily("^GSPC"), yf_daily("^STOXX50E")
    ex = pd.read_csv(fx_capit.exness_csv("EURUSD"), parse_dates=["Date"]).set_index("Date")
    yh = yf_daily("EURUSD=X")
    lines = [f"backtest/fx_t8_exness.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; T8 re-measured. Exness EURUSD daily "
             f"{ex.index.min():%Y-%m-%d} .. {ex.index.max():%Y-%m-%d}; costs {SPREAD}bp + swap (long {SWAP_LONG}, short {SWAP_SHORT}bp a night)", ""]
    # the verdict: Exness
    R = t8(ex, spx, sx5, "exness")
    s = stats(R)
    others = [p_one(t) for t in OTHER_T]
    hp = holm(s["p"], others)
    lines.append("VERDICT - T8 on Exness's own EURUSD prices")
    lines.append(fmt(s, "T8, Exness, last forex day close-to-close"))
    ok = s["tune"] > 0 and s["hold"] > 0 and hp < 0.05
    lines.append(f"  family Holm p (with the other nine rows of logs/fx_anomalies.txt): {hp:.3f} -> {'PASS' if ok else 'FAIL - the kill stands'}")
    lines.append(f"  gross {R.gross.mul(R.sgn).mean() * 1e4:+.2f}bp a month before costs")
    lines.append("")
    # A: Yahoo as published, same months
    Y = t8(yh, spx, sx5, "yahoo")
    same = Y.index.to_period("M").isin(R.index.to_period("M"))
    Ys = Y[same]
    lines.append("A  YAHOO AS PUBLISHED (the broken measurement), the same months")
    lines.append(fmt(stats(Ys), "T8, Yahoo, as in fx_anomalies.py"))
    j = pd.DataFrame({"ex": R.net.to_numpy()}, index=R.index.to_period("M")).join(
        pd.DataFrame({"yh": Ys.net.to_numpy()}, index=Ys.index.to_period("M")), how="inner")
    diff = (j.yh - j.ex).abs().mean() * 1e4
    lines.append(f"  month by month, |Yahoo - Exness| averages {diff:.1f}bp; the two agree in sign in "
                 f"{(np.sign(j.yh) == np.sign(j.ex)).mean() * 100:.0f}% of {len(j)} months; correlation {j.yh.corr(j.ex):.2f}")
    lines.append("")
    # B: Yahoo realigned one day
    ys = yh.copy()
    ys.index = ys.index.to_series().shift(1).to_numpy()                  # the bar dated D+1 -> day D (the previous row's date)
    ys = ys.iloc[1:]
    ys = ys[~ys.index.duplicated(keep="last")]
    rr = pd.concat([ys.Close.pct_change().rename("y"), ex.Close.pct_change().rename("e")], axis=1, join="inner").dropna()
    c_al = float(rr.corr().iloc[0, 1])
    lines.append(f"B  YAHOO REALIGNED (its bar dated D+1 read as day D): daily-return correlation with Exness on the overlap "
                 f"{c_al:.3f} ({len(rr)} days)")
    Yb = t8(ys, spx, sx5, "yahoo_shift")
    sb = stats(Yb)
    hb = holm(sb["p"], others)
    lines.append(fmt(sb, "T8, Yahoo realigned, all years"))
    lines.append(f"  Holm p {hb:.3f}" + (" -> passes" if sb["tune"] > 0 and sb["hold"] > 0 and hb < 0.05 else " -> fails"))
    yb_same = Yb[Yb.index.to_period("M").isin(R.index.to_period("M"))]
    lines.append(fmt(stats(yb_same), "  same, only Exness's months (cross-check)"))
    lines.append("")
    # C: to the 16:00 London fix
    h = pd.DataFrame(json.load(open(ROOT / "strategy_analysis" / "data" / "EURUSDm_1h_2400d.json")))
    h["ts"] = pd.to_datetime(h.t, unit="ms").dt.tz_localize("UTC")
    h = h.set_index("ts")
    rows = []
    for L, row in R.iterrows():
        fix = pd.Timestamp(f"{L:%Y-%m-%d} 16:00", tz="Europe/London").tz_convert("UTC")
        if fix not in h.index:
            continue
        k = ex.index.get_loc(L)
        P = ex.index[k - 1]
        e = ex.Close.iloc[k - 1]
        x = h.loc[fix, "o"]                                                  # the price at 16:00 London
        g = x / e - 1
        swap = SWAP_LONG if row.sgn > 0 else SWAP_SHORT
        rows.append((L, row.sgn, g, row.sgn * g - SPREAD / 1e4 + swap / 1e4 * nights(P, L)))
    Rc = pd.DataFrame(rows, columns=["day", "sgn", "gross", "net"]).set_index("day")
    sc = stats(Rc)
    lines.append("C  TO THE FIX (Exness close of the day before -> 16:00 London on the last day)")
    lines.append(fmt(sc, "T8, Exness, to the 16:00 London fix"))
    lines.append("")
    lines.append("REGISTERED PREDICTIONS")
    m1 = abs(s["t"]) < 2 and 0.45 <= s["hits"] / s["n"] <= 0.60
    lines.append(f"  M1 Exness t {s['t']:+.2f}, right sign {s['hits'] / s['n'] * 100:.0f}% -> {'RIGHT' if m1 else 'WRONG'}")
    lines.append(f"  M2 |Yahoo - Exness| {diff:.1f}bp a month -> {'RIGHT' if diff > 3 else 'WRONG'}")
    m3 = c_al > 0.9 and not (sb["tune"] > 0 and sb["hold"] > 0 and hb < 0.05)
    lines.append(f"  M3 realigned corr {c_al:.3f}; 2003-2026 corrected T8 Holm {hb:.3f}, halves {sb['tune']:+.2f} / {sb['hold']:+.2f} -> "
                 f"{'RIGHT' if m3 else 'WRONG'}")
    lines.append(f"  M4 to the fix t {sc['t']:+.2f} -> {'RIGHT' if abs(sc['t']) < 2 else 'WRONG'}")
    txt = "\n".join(lines)
    print(txt)
    LOG.write_text(txt + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
