"""THE NOISE RULE ON THE REAL FUTURES, WITH VOLUME: the published VWAP version, volume regimes, and a data-vendor cross-check (2026-11-03)

Data: CME E-mini NASDAQ-100 continuous front-month 1-minute bars with volume, Databento GLBX.MDP3, 2010-06..2026-10 (backtest/nq_fetch.py, USD 19.93, bought with the user's permission). Sessions are the cash hours 09:30-16:00 New York
(390 minutes), >= 90% of the minutes present; sessions in which the contract rolls (the instrument changes inside the session) are dropped, and a session whose first bar is a different contract from the previous session's last
bar gets no 'previous close' (its gap would be the roll spread) - so the rule skips it. The rule, costs (0.77 bp spread + 0.5 bp slippage per entered trade) and splits are exactly fx_intraday_pub.noise(); the futures are the
same market as the CFD, so the cost is kept for comparability.

WHAT IT TESTS
  V1  integrity / vendor cross-check: the bound-only rule on NQ vs the HistData CFD result (net bp/day and the daily correlation over the common sessions).
  V2  the PUBLISHED trailing stop (Zarattini, Aziz & Barbon 2024): a long is held while the price stays above max(upper bound, session VWAP), a short below min(lower bound, VWAP). fx_intraday_pub's TWAP stand-in was identical to the
      bound-only rule (+2.24 vs +2.25 bp/day); this uses the true volume-weighted price. Paired daily differences against the bound-only rule, tune / holdout.
  V3  regimes, same summary as nasdaq_regimes.py: P1-P3 repeated on NQ (a different data vendor), plus two VOLUME proxies fixed in advance:
        P4  the opening 30 minutes' volume above its trailing 14-session mean (known at 10:00, before the first trade)
        P5  the previous session's total volume above its trailing 20-session mean
      Mechanism: heavy participation = informed, directional flow; momentum should work there.

REGISTERED BEFORE THE DATA WAS OPENED (2026-11-03)
    V1  NOISE on NQ nets between +1.0 and +3.5 bp/day and its daily series correlates >= 0.85 with the HistData CFD series.
    V2  The VWAP version does NOT beat the bound-only rule on both halves with a paired t >= 2.4 (the TWAP stand-in did not move it).
    V3  P1-P3 keep their order on NQ (P2 the strongest, concentrated on-days +3..+6 bp); neither volume proxy has on-day profit with t >= 2 on BOTH halves and off-day profit near zero.

RESULT (2026-11-03; logs/nq_noise.txt; 5,458,196 NQ bars -> 4,016 cash sessions 2010-06..2026-10, 67 roll sessions without a previous close)
    V1 RIGHT: the rule on the real futures nets +2.27 bp/day (t +2.92, Sharpe 0.73, 0.81 trades a day) against the CFD's +2.25; over the 3,638 common sessions CFD +2.28 / NQ +2.52 bp/day, daily correlation 0.972.
    BUT the halves are uneven: tune +1.13 bp (t +1.22), holdout +3.98 (t +2.91) - the edge is mostly 2020 on; at DOUBLE costs +1.25 bp/day (t +1.59; tune t +0.12, holdout t +2.15).
    V2 RIGHT: the published VWAP trail adds nothing: -0.02 bp/day (paired t -0.21; tune +0.10, holdout -0.22); the TWAP stand-in -0.00.
    V3 RIGHT: P2 VXN > 1-year median is the strongest and, on NQ, the first proxy to clear the bar - 48% of sessions, on +4.51 bp (t +3.2), off +0.23, tune +3.70 (t 2.2), holdout +5.71 (t 2.3), Sharpe of only those days 0.81 vs 0.73.
    P3 range +3.72 / off +1.09 (hold t 1.6), P1 curve +7.71 on 7% of days (t 1.4), P5 yesterday's volume +3.60 / off +1.00 (hold t 1.6); the opening-volume proxy P4 does not separate at all (+2.34 vs +2.22).
    V4 (descriptive, after seeing V3): a $300 account at x5, 12-month starts: all days typical $365, bad $291, worst $157, CAGR +22.9%, fall 65%, worst month -25.9%; only P2 days typical $353, bad $313, worst $220, CAGR +23.5%, fall 44%,
    worst month -17.3%, Sharpe 0.81. The gate keeps the return and cuts the fall by a third. Gated at 2x costs: +3.42 bp per trading day (t +2.46; tune t 1.59, holdout t 1.89), 0.86 trades a day.
    Reading: the rule is confirmed on a second vendor and is NOT helped by volume or the VWAP; the dealer-gamma mechanism points the same way on three proxies and VXN clears the bar on NQ, but it was found after looking
    and the early years are weak, so it enters the bot as a SHADOW arm first.

    python -m backtest.nq_noise        writes logs/nq_noise.txt          tests: python tests/test_nq_noise.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest.fx_intraday_pub import INSTR, SLIP, TUNE, noise, session  # noqa: E402
from backtest.nasdaq_regimes import regimes, summarize, tstat  # noqa: E402

NQ_DIR = ROOT / "strategy_analysis" / "data" / "nq_1m"
L = 390


def load_nq() -> pd.DataFrame:
    fs = sorted(NQ_DIR.glob("NQ_*.parquet"))
    d = pd.concat([pd.read_parquet(f) for f in fs], ignore_index=True)
    d["ts_event"] = pd.to_datetime(d["ts_event"], utc=True)
    return d.sort_values("ts_event", kind="stable").reset_index(drop=True)


def build_sessions(d: pd.DataFrame, min_cover: float = 0.9):
    """(A, dates, prev, roll_gap): arrays o, h, l, c, v of shape sessions x 390 for the New York cash session. prev = the previous KEPT session's last close, NaN where the contract changed in between."""
    ny = d.ts_event.dt.tz_convert("America/New_York")
    minute = ny.dt.hour * 60 + ny.dt.minute - (9 * 60 + 30)
    ok = ((minute >= 0) & (minute < L) & (ny.dt.dayofweek < 5)).to_numpy()
    sub = d[ok].reset_index(drop=True)
    day = ny[ok].dt.normalize().dt.tz_localize(None).reset_index(drop=True)
    mi = minute[ok].to_numpy()
    codes, dates = pd.factorize(day, sort=True)
    n = len(dates)
    A = {k: np.full((n, L), np.nan) for k in "ohlcv"}
    for k, col in zip("ohlcv", ("open", "high", "low", "close", "volume")):
        A[k][codes, mi] = sub[col].to_numpy(float)
    g = sub.groupby(codes).instrument_id
    first_id, last_id, n_id = g.first().to_numpy(), g.last().to_numpy(), g.nunique().to_numpy()
    cover = np.isfinite(A["c"]).mean(1)
    keep = (cover >= min_cover) & np.isfinite(A["o"][:, 0]) & (n_id == 1)
    for k in "ohlcv":
        A[k] = A[k][keep]
    first_id, last_id, dates = first_id[keep], last_id[keep], pd.DatetimeIndex(dates[keep])
    C = pd.DataFrame(A["c"].T).ffill().to_numpy().T
    for k in "ohl":
        A[k] = np.where(np.isfinite(A[k]), A[k], C)
    A["v"] = np.where(np.isfinite(A["v"]), A["v"], 0.0)
    A["c"] = C
    prev = np.r_[np.nan, C[:-1, -1]]
    roll_gap = np.r_[True, first_id[1:] != last_id[:-1]]
    prev = np.where(roll_gap, np.nan, prev)
    return A, dates, prev, roll_gap


def vwap_array(A):
    """Running session VWAP at each minute from the typical price (h + l + c) / 3 and the volume."""
    tp = (A["h"] + A["l"] + A["c"]) / 3
    cv = np.cumsum(A["v"], axis=1)
    pv = np.cumsum(tp * A["v"], axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        vw = np.where(cv > 0, pv / cv, np.nan)
    return pd.DataFrame(vw.T).ffill().bfill().to_numpy().T


def twap_array(A):
    return np.cumsum(A["c"], axis=1) / np.arange(1, A["c"].shape[1] + 1)


def noise_ref(A, prev, ref, look=14):
    """fx_intraday_pub.noise() with the trailing reference (TWAP in the original `twap=True`) passed in: a long is kept while the close stays above max(upper bound, ref), a short below min(lower bound, ref)."""
    O, C = A["o"], A["c"]
    n, Lm = C.shape
    op = O[:, :1]
    sig = pd.DataFrame(np.abs(C / op - 1)).rolling(look).mean().shift(1).to_numpy()
    out, trades = np.zeros(n), np.zeros(n)
    for i in range(n):
        if not np.isfinite(sig[i, 0]) or not np.isfinite(prev[i]):
            continue
        ub_base, lb_base = max(op[i, 0], prev[i]), min(op[i, 0], prev[i])
        pos, entry, r, nt = 0, np.nan, 0.0, 0
        for m in range(30, Lm - 1, 30):
            c = C[i, m]
            ub, lb = ub_base * (1 + sig[i, m]), lb_base * (1 - sig[i, m])
            if pos > 0:
                want = 1 if c > max(ub, ref[i, m]) else (-1 if c < lb else 0)
            elif pos < 0:
                want = -1 if c < min(lb, ref[i, m]) else (1 if c > ub else 0)
            else:
                want = 1 if c > ub else (-1 if c < lb else 0)
            if want != pos:
                px = O[i, m + 1]
                if pos != 0:
                    r += pos * (px / entry - 1)
                pos, entry = want, px
                nt += abs(want) > 0
        if pos != 0:
            r += pos * (C[i, -1] / entry - 1)
        out[i], trades[i] = r, nt
    return out, trades


def volume_flags(A, dates):
    """P4 / P5, both known before the first trade of the session. NaN until the trailing windows exist."""
    v30 = pd.Series(A["v"][:, :30].sum(axis=1), index=dates)
    m30 = v30.rolling(14).mean().shift(1)
    p4 = (v30 > m30).astype(float).where(m30.notna())
    tot = pd.Series(A["v"].sum(axis=1), index=dates)
    ptot = tot.shift(1)
    mtot = ptot.rolling(20).mean()
    p5 = (ptot > mtot).astype(float).where(mtot.notna())
    return {"P4 opening volume": p4, "P5 yesterday's volume": p5}


def paired(base, var, cut):
    d = var - base
    return d.mean() * 1e4, tstat(d), d[:cut].mean() * 1e4, tstat(d[:cut]), d[cut:].mean() * 1e4, tstat(d[cut:])


def main():
    from backtest.fx_anomalies import yf_daily
    d = load_nq()
    A, dates, prev, roll = build_sessions(d)
    cost = (INSTR["NASDAQ"][4] + SLIP) / 1e4
    cut = int(len(dates) * TUNE)
    g, _, nt = noise(A, prev)
    base = g - cost * nt
    out = [f"backtest/nq_noise.py - {len(d):,} NQ minute bars -> {len(dates)} cash sessions {dates[0]:%Y-%m}..{dates[-1]:%Y-%m} ({int(roll.sum())} roll sessions without a previous close); net of {cost * 1e4:.2f} bp per entered trade; tune = first {cut}",
           f"\nV1 CROSS-CHECK: NOISE on NQ futures {base.mean() * 1e4:+.2f} bp/day (t {tstat(base):+.2f}), Sharpe {base.mean() / base.std(ddof=1) * np.sqrt(252):.2f}, trades {nt.mean():.2f}/day"]
    A0, d0, p0 = session("NASDAQ")
    g0, _, n0 = noise(A0, p0)
    cfd = pd.Series(g0 - cost * n0, index=d0.normalize())
    nqs = pd.Series(base, index=dates.normalize())
    both = pd.concat([cfd, nqs], axis=1, join="inner").dropna()
    out.append(f"   HistData CFD over its own sessions {cfd.mean() * 1e4:+.2f} bp/day; common sessions {len(both)}: CFD {both.iloc[:, 0].mean() * 1e4:+.2f} / NQ {both.iloc[:, 1].mean() * 1e4:+.2f} bp/day, daily correlation {both.corr().iloc[0, 1]:.3f}")
    dbl = g - 2 * cost * nt
    out.append(f"   halves: tune {base[:cut].mean() * 1e4:+.2f} bp (t {tstat(base[:cut]):+.2f}), holdout {base[cut:].mean() * 1e4:+.2f} bp (t {tstat(base[cut:]):+.2f}); at DOUBLE costs {dbl.mean() * 1e4:+.2f} bp/day (t {tstat(dbl):+.2f}; tune t {tstat(dbl[:cut]):+.2f}, holdout t {tstat(dbl[cut:]):+.2f})")
    out.append("\nV2 THE PUBLISHED VWAP TRAIL vs the bound-only rule (paired daily differences, bp/day):")
    out.append(f"   {'variant':<28}{'net bp/day':>11}{'diff':>8}{'paired t':>9}{'tune diff':>10}{'t':>6}{'hold diff':>10}{'t':>6}{'trades/day':>11}{'Sharpe':>7}")
    out.append(f"   {'bound only (base)':<28}{base.mean() * 1e4:>+11.2f}{'':>8}{'':>9}{'':>10}{'':>6}{'':>10}{'':>6}{nt.mean():>11.2f}{base.mean() / base.std(ddof=1) * np.sqrt(252):>7.2f}")
    res = {}
    for name, ref in (("with TWAP (stand-in)", twap_array(A)), ("with VWAP (published)", vwap_array(A))):
        g2, n2 = noise_ref(A, prev, ref)
        net = g2 - cost * n2
        res[name] = paired(base, net, cut)
        r = res[name]
        out.append(f"   {name:<28}{net.mean() * 1e4:>+11.2f}{r[0]:>+8.2f}{r[1]:>+9.2f}{r[2]:>+10.2f}{r[3]:>+6.1f}{r[4]:>+10.2f}{r[5]:>+6.1f}{n2.mean():>11.2f}{net.mean() / net.std(ddof=1) * np.sqrt(252):>7.2f}")
    v = res["with VWAP (published)"]
    out.append(f"   VWAP beats the base on both halves with paired t >= 2.4: {v[2] > 0 and v[4] > 0 and v[3] >= 2.4 and v[5] >= 2.4}")
    out.append("\nV3 REGIMES ON NQ (previous-close / pre-trade values):")
    out.append(f"   {'regime':<24}{'days on':>8}{'on bp/day':>10}{'t':>6}{'off bp/day':>11}{'t':>6}{'tune on':>9}{'t':>6}{'hold on':>9}{'t':>6}{'Sharpe on-only':>15}{'Sharpe all':>11}")
    flags = regimes(dates, A, yf_daily("^VIX").Close, yf_daily("^VIX3M").Close, yf_daily("^VXN").Close)
    flags.update(volume_flags(A, dates))
    conf = []
    for name, flag in flags.items():
        s = summarize(base, flag.to_numpy(dtype=float), cut)
        out.append(f"   {name:<24}{s['share'] * 100:>7.0f}%{s['on']:>+10.2f}{s['ton']:>+6.1f}{s['off']:>+11.2f}{s['toff']:>+6.1f}{s['tune']:>+9.2f}{s['ttune']:>+6.1f}{s['hold']:>+9.2f}{s['thold']:>+6.1f}{s['sharpe']:>15.2f}{s['sharpe_all']:>11.2f}")
        if s["on"] > 0 and s["ttune"] >= 2 and s["thold"] >= 2 and abs(s["off"]) < 0.5:
            conf.append(name)
    out.append(f"   proxies with regime-day profit t >= 2 on BOTH halves and off-day profit near zero: {conf}")
    out.append("\nV4 (DESCRIPTIVE, after seeing V3 - not a test): what trading only the P2 days (VXN above its 1-year median) does to a $300 account at the 0.05-lot minimum (x5), same sessions for both, 12-month starts")
    from backtest.noise_book import account, report
    f2 = flags["P2 VXN > 1y median"].to_numpy(dtype=float)
    use = np.isfinite(f2)
    idx = dates[use]
    r_all = pd.Series(base[use], index=idx)
    r_gate = pd.Series(np.where(f2[use] == 1.0, base[use], 0.0), index=idx)
    lev = pd.Series(5.0, index=idx)
    hdr = f"   {'':<30}{'typical':>7}{'bad':>8}{'worst':>8}{'CAGR':>8}{'fall':>7}{'worst mo':>9}{'worst day':>9}{'mo up':>7}{'Sharpe':>7}"
    out.append(hdr)
    for lab, r in (("all days (the bot as built)", r_all), ("only VXN-above-median days", r_gate)):
        s, *_ = report(lab, account(r, lev, r), 300.0)
        out.append(s)
    on = f2[use] == 1.0
    gg, nn = g[use], nt[use]
    cu = int(use.sum() * TUNE)
    for k in (1.0, 2.0):
        x = np.where(on, gg - k * cost * nn, 0.0)
        xo = (gg - k * cost * nn)[on]
        out.append(f"   gated at {k:g}x costs: {xo.mean() * 1e4:+.2f} bp per trading day (t {tstat(xo):+.2f}); tune t {tstat(np.where(on, gg - k * cost * nn, np.nan)[:cu]):+.2f}, holdout t {tstat(np.where(on, gg - k * cost * nn, np.nan)[cu:]):+.2f}; trades/day {nn[on].mean():.2f}")
    txt = "\n".join(out)
    print(txt)
    (ROOT / "logs" / "nq_noise.txt").write_text(txt + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
