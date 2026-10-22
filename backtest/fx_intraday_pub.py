"""THE PUBLISHED INTRADAY STRATEGIES, ON 13-19 YEARS OF MINUTE BARS AT EXNESS COSTS (2026-10-22)

THE USER (2026-10-22): "test every possible thing or strategy you have, his strategy's help also and all the other info -
I want a crazy good strategy" (forex / Exness). Every intraday test on the index CFDs so far used Exness's own ticks, which
start in 2026 (cfd_scalp.py, cfd_bigtarget.py: 9 months), or NQ 1h bars from 2024 (ndx_close_momo.py: 588 days) - too
short to see a 1-3bp-a-day edge. That closed "NASDAQ scalping at every horizon" by a council's kill line; this file
REOPENS it on purpose and says so: the measurement there had no power for a small daily edge, and these two rules were
never run. HistData's free minute bars (histdata_1m.py) go back to 2007 (FX), 2009-2010 (gold, NASDAQ, S&P, DAX).

RULES (as published, not tuned here)
  ORB    Zarattini & Aziz 2023, "Can day trading really be profitable?": the first 5-minute candle of the cash session
         sets the side (close above its open -> long, below -> short, equal -> no trade); enter at the next minute's open;
         stop at the first candle's opposite end; target 10x that risk; else out at the session close. ORB15 / ORB30 use
         the first 15 / 30 minutes - shown, not primary.
  NOISE  Zarattini, Aziz & Barbon 2024, "Beat the market: an effective intraday momentum strategy": sigma(m) = the mean,
         over the previous 14 days, of |price at minute m / the day's open - 1|; upper bound = max(open, previous close) x
         (1 + sigma(m)), lower = min(open, previous close) x (1 - sigma(m)). At every :00 / :30 from 30 minutes after the
         open: long above the upper bound, short below the lower, flat in between (the bound is the trailing stop); filled
         at the NEXT minute's open; flat at the close. HistData has no volume, so the paper's VWAP trail is replaced by
         the bound alone (primary) and by max(bound, TWAP) (NOISE-T, shown).
  CONTROL  long the whole session every day (the drift a long-biased rule could be riding).
SESSIONS  NASDAQ / S&P 09:30-16:00 New York; DAX 09:00-17:30 Frankfurt; gold 08:20-13:30 New York (COMEX day session);
          EURUSD / GBPUSD / USDJPY 08:00-16:30 London. A day needs >= 90% of its minutes; flat overnight, so no swap.
COSTS     Exness round-trip spread (forex.py, measured 2026-09-14) + 0.5bp slippage per round trip: NASDAQ 0.77+0.5,
          S&P 0.38+0.5 (US30's, as fx_anomalies.py), DAX 1.0+0.5 (assumed), gold 1.22+0.5, EUR 1.39+0.5, GBP 1.48+0.5,
          JPY 1.29+0.5 bp. Spreads were wider before ~2015, so early years are flattered.
PASS      net mean a day > 0 with t >= 2 on BOTH halves (first 60% of days / last 40%), and Holm p < 0.05 across the
          PRIMARY cells (ORB and NOISE x every instrument).

REGISTERED BEFORE THE RUN (2026-10-22)
  I1  ORB on NASDAQ: net positive over the whole period, but t < 2 on at least one half.
  I2  NOISE passes on at most one of NASDAQ / S&P; it is long-biased (more of its profit from longs than the control's
      share of up days would give).
  I3  On the three FX majors neither rule passes (Asian-range breakout, fx_breakout.py, already died: FX has no cash open).
  I4  Gold: NOISE gross positive, net fails at least one half.
  I5  Across all primary cells, 0-1 pass Holm.

RESULT (2026-10-22, logs/fx_intraday_pub.txt) - one near-pass, NASDAQ NOISE; the rest dead.
  NASDAQ NOISE +2.25bp a day net (gross +3.30), t +2.83, tune t +1.99 / holdout +2.01, Sharpe 0.74 at 1x, 13 of 17 years up;
  Holm 0.038 over the 14 primary cells - fails the pass line by 0.01 of a t on the tune half. S&P NOISE the same sign, weaker
  (+1.12bp, t +1.58); NASDAQ ORB +1.82bp t +1.98 (tune 1.62 / holdout 1.22). DAX, gold and the three FX majors: every rule
  negative after costs (FX ORB / NOISE t -3..-7, every year). I1-I3, I5 RIGHT; I4 RIGHT (gold NOISE fails both halves).
  noise_attack.py tries to break NASDAQ NOISE.

    python -m backtest.fx_intraday_pub
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

HD = ROOT / "strategy_analysis" / "data" / "histdata"
LOG = ROOT / "logs" / "fx_intraday_pub.txt"
TUNE = 0.60
SLIP = 0.5
INSTR = {  # name: (file, tz, start, minutes, round-trip spread bp)
    "NASDAQ": ("NSXUSD", "America/New_York", "09:30", 390, 0.77),
    "S&P 500": ("SPXUSD", "America/New_York", "09:30", 390, 0.38),
    "DAX": ("GRXEUR", "Europe/Berlin", "09:00", 510, 1.00),
    "gold": ("XAUUSD", "America/New_York", "08:20", 310, 1.22),
    "EURUSD": ("EURUSD", "Europe/London", "08:00", 510, 1.39),
    "GBPUSD": ("GBPUSD", "Europe/London", "08:00", 510, 1.48),
    "USDJPY": ("USDJPY", "Europe/London", "08:00", 510, 1.29),
}


def session(name: str):
    """days x minutes arrays O, H, L, C of the session, the dates, and the previous session's close."""
    f, tz, start, L, _ = INSTR[name]
    p = HD / f"{f}.parquet"
    if not p.exists():
        return None
    return session_df(pd.read_parquet(p), name)


def session_df(d: pd.DataFrame, name: str):
    """session() on any minute-bar frame with t (ms UTC) and o h l c - e.g. Exness's own bars (mt5_1m.py)."""
    _, tz, start, L, _ = INSTR[name]
    lt =pd.to_datetime(d.t, unit="ms").dt.tz_localize("UTC").dt.tz_convert(tz).dt.tz_localize(None)
    h0, m0 = map(int, start.split(":"))
    day = lt.dt.normalize()
    off = ((lt - day).dt.total_seconds() // 60 - (h0 * 60 + m0)).astype(int).to_numpy()
    ok = (off >= 0) & (off < L) & (lt.dt.dayofweek < 5).to_numpy()
    codes, dates = pd.factorize(day[ok], sort=True)
    n = len(dates)
    A = {k: np.full((n, L), np.nan) for k in "ohlc"}
    for k in "ohlc":
        A[k][codes, off[ok]] = d[k].to_numpy()[ok]
    cover = np.isfinite(A["c"]).mean(1)
    keep = (cover >= 0.9) & np.isfinite(A["o"][:, 0])
    for k in "ohlc":
        A[k] = A[k][keep]
    dates = pd.DatetimeIndex(dates[keep])
    C = pd.DataFrame(A["c"].T).ffill().to_numpy().T
    for k in "ohl":
        A[k] = np.where(np.isfinite(A[k]), A[k], C)
    A["c"] = C
    prev = np.r_[np.nan, C[:-1, -1]]
    return A, dates, prev


def orb(A, k=5):
    O, H, Lo, C = A["o"], A["h"], A["l"], A["c"]
    n, L = C.shape
    out = np.zeros(n)
    side = np.zeros(n)
    for i in range(n):
        o0, c0 = O[i, 0], C[i, k - 1]
        hi, lo = H[i, :k].max(), Lo[i, :k].min()
        s = np.sign(c0 - o0)
        if s == 0 or not np.isfinite(c0):
            continue
        e = O[i, k]
        stop = lo if s > 0 else hi
        risk = abs(e - stop)
        if risk <= 0:
            continue
        tgt = e + s * 10 * risk
        x = C[i, -1]
        for m in range(k, L):
            if (s > 0 and Lo[i, m] <= stop) or (s < 0 and H[i, m] >= stop):
                x = min(stop, O[i, m]) if s > 0 else max(stop, O[i, m])
                break
            if (s > 0 and H[i, m] >= tgt) or (s < 0 and Lo[i, m] <= tgt):
                x = tgt
                break
        out[i] = s * (x / e - 1)
        side[i] = s
    return out, side, (side != 0).astype(float)


def noise(A, prev, twap=False, phase=0, look=14, delay=1, side=0, last=None):
    """phase: minutes added to every decision point (0 = :00 / :30); delay: minutes from the decision to the fill;
    side: +1 longs only / -1 shorts only / 0 both; last: no new entry after this session minute."""
    O, C = A["o"], A["c"]
    n, L = C.shape
    op = O[:, :1]
    move = np.abs(C / op - 1)
    sig = pd.DataFrame(move).rolling(look).mean().shift(1).to_numpy()
    out = np.zeros(n)
    longpart = np.zeros(n)
    trades = np.zeros(n)
    tw = np.cumsum(C, axis=1) / np.arange(1, L + 1)
    for i in range(n):
        if not np.isfinite(sig[i, 0]) or not np.isfinite(prev[i]):
            continue
        ub_base, lb_base = max(op[i, 0], prev[i]), min(op[i, 0], prev[i])
        pos, entry, r, rl, nt = 0, np.nan, 0.0, 0.0, 0
        for m in range(30 + phase, L - delay, 30):
            c = C[i, m]
            ub, lb = ub_base * (1 + sig[i, m]), lb_base * (1 - sig[i, m])
            if twap and pos > 0:
                want = 1 if c > max(ub, tw[i, m]) else (-1 if c < lb else 0)
            elif twap and pos < 0:
                want = -1 if c < min(lb, tw[i, m]) else (1 if c > ub else 0)
            else:
                want = 1 if c > ub else (-1 if c < lb else 0)
            if side and want == -side:
                want = 0
            if last is not None and m > last and want != 0 and want != pos:
                want = 0
            if want != pos:
                px = O[i, m + delay]
                if pos != 0:
                    g = pos * (px / entry - 1)
                    r += g
                    rl += g if pos > 0 else 0.0
                pos, entry = want, px
                nt += abs(want) > 0
        if pos != 0:
            g = pos * (C[i, -1] / entry - 1)
            r += g
            rl += g if pos > 0 else 0.0
        out[i], longpart[i], trades[i] = r, rl, nt
    return out, longpart, trades


def tstat(x):
    x = x[np.isfinite(x)]
    return x.mean() / (x.std(ddof=1) / np.sqrt(len(x))) if len(x) > 2 and x.std() > 0 else 0.0


def pval(t):
    from scipy.stats import norm
    return 2 * (1 - norm.cdf(abs(t)))


def main():
    L = [f"backtest/fx_intraday_pub.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; HistData 1m bars; net of Exness spread + "
         f"{SLIP}bp; first 60% of days = tune", "",
         f"   {'instrument':<9}{'rule':<9}{'days':>6}{'traded':>7}{'gross bp':>9}{'net bp/day':>11}{'t':>7}"
         f"{'tune bp':>8}{'t':>6}{'hold bp':>8}{'t':>6}{'Sharpe':>7}{'CAGR 1x':>8}   span"]
    prim = []
    years = {}
    for name in INSTR:
        S = session(name)
        if S is None:
            L.append(f"   {name:<9} (no data)")
            continue
        A, dates, prev = S
        cost = (INSTR[name][4] + SLIP) / 1e4
        cut = int(len(dates) * TUNE)
        res = {}
        r, side, tr = orb(A, 5)
        res["ORB"] = (r, tr)
        for k in (15, 30):
            r2, _, tr2 = orb(A, k)
            res[f"ORB{k}"] = (r2, tr2)
        rn, rl, ntn = noise(A, prev)
        # one-way changes: every entry and every exit; NOISE's exits = entries (flat at the close)
        res["NOISE"] = (rn, ntn)
        rt, _, ntt = noise(A, prev, twap=True)
        res["NOISE-T"] = (rt, ntt)
        ctl = A["c"][:, -1] / A["o"][:, 0] - 1
        res["CONTROL"] = (ctl, np.ones(len(ctl)))
        for rule, (g, ntrades) in res.items():
            net = g - cost * ntrades
            a, b = net[:cut], net[cut:]
            sh = net.mean() / net.std(ddof=1) * np.sqrt(252) if net.std() > 0 else 0
            cagr = (np.prod(1 + net) ** (252 / len(net)) - 1) * 100
            L.append(f"   {name:<9}{rule:<9}{len(net):>6}{(ntrades > 0).mean() * 100:>6.0f}%{g.mean() * 1e4:>+9.2f}"
                     f"{net.mean() * 1e4:>+11.2f}{tstat(net):>+7.2f}{a.mean() * 1e4:>+8.2f}{tstat(a):>+6.2f}"
                     f"{b.mean() * 1e4:>+8.2f}{tstat(b):>+6.2f}{sh:>7.2f}{cagr:>+7.1f}%   {dates[0]:%Y-%m}..{dates[-1]:%Y-%m}")
            if rule in ("ORB", "NOISE"):
                prim.append(dict(name=name, rule=rule, t=tstat(net), ta=tstat(a), tb=tstat(b), ma=a.mean(), mb=b.mean()))
            if rule in ("ORB", "NOISE", "CONTROL"):
                years[(name, rule)] = pd.Series(net, index=dates).groupby(dates.year).sum() * 100
        lp = rl.sum() / rn.sum() if rn.sum() != 0 else np.nan
        L.append(f"   {'':<9}NOISE: share of gross profit from longs {lp * 100:.0f}%; up days in the session "
                 f"{(ctl > 0).mean() * 100:.0f}%")
        L.append("")
    P = pd.DataFrame(prim)
    P["p"] = [pval(t) for t in P.t]
    o = np.argsort(P.p.to_numpy())
    run, holm = 0.0, np.empty(len(P))
    for k, i in enumerate(o):
        run = max(run, (len(P) - k) * P.p.iloc[i])
        holm[i] = min(run, 1.0)
    P["holm"] = holm
    P["pass"] = (P.ma > 0) & (P.mb > 0) & (P.ta >= 2) & (P.tb >= 2) & (P.holm < 0.05)
    L += ["PRIMARY CELLS (Holm over all of them)"] + [
        f"   {r['name']:<9}{r['rule']:<7} t {r['t']:+.2f}  tune t {r['ta']:+.2f}  holdout t {r['tb']:+.2f}  Holm {r['holm']:.3f}"
        f"  -> {'PASS' if r['pass'] else 'fail'}" for _, r in P.iterrows()]
    L += ["", "BY YEAR, net % (sum of daily returns, 1x)"]
    for (name, rule), s in years.items():
        L.append(f"   {name:<9}{rule:<8}" + " ".join(f"{y % 100:02d}:{v:+.0f}" for y, v in s.items()))
    g = lambda n, r: P[(P.name == n) & (P.rule == r)]  # noqa: E731
    i1 = len(g("NASDAQ", "ORB")) and bool((g("NASDAQ", "ORB").t > 0).iloc[0]) and bool((g("NASDAQ", "ORB")[["ta", "tb"]].min(axis=1) < 2).iloc[0])
    i2 = int(P[(P.rule == "NOISE") & P.name.isin(["NASDAQ", "S&P 500"])]["pass"].sum()) <= 1
    i3 = not P[P.name.isin(["EURUSD", "GBPUSD", "USDJPY"])]["pass"].any()
    gd = g("gold", "NOISE")
    i4 = bool(len(gd)) and not bool(gd["pass"].iloc[0])
    i5 = int(P["pass"].sum()) <= 1
    L += ["", "REGISTERED PREDICTIONS",
          f"  I1 ORB NASDAQ net > 0, t < 2 on a half -> {'RIGHT' if i1 else 'WRONG'}",
          f"  I2 NOISE passes on at most one US index -> {'RIGHT' if i2 else 'WRONG'} (long-bias: see the share lines)",
          f"  I3 no FX major passes -> {'RIGHT' if i3 else 'WRONG'}",
          f"  I4 gold NOISE fails a half -> {'RIGHT' if i4 else 'WRONG'}{'' if len(gd) else ' (no gold data)'}",
          f"  I5 0-1 primary cells pass -> {'RIGHT' if i5 else 'WRONG'} ({int(P['pass'].sum())} pass)"]
    txt = "\n".join(L)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
