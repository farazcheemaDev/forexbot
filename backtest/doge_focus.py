"""STUDY ONE COIN (DOGE) AND ADAPT - can it make 1,000 PKR a month on 10,000 (+10% EVERY month)?

THE USER (2026-10-08): "what if we study one coin like DOGE only and then we can achieve greater results ... I want
1000 at least on 10k every month ... think and apply whatever will help us achieve that goal."

THE HONEST FORM OF "STUDY ONE COIN": a WALK-FORWARD. At the start of every month pick the DOGE strategy that did best
over the previous 12 months (or 3 / 6), trade ONLY the next month with it, repeat. It never sees the future. Beside it,
the configuration that was best over the WHOLE history - the hindsight illusion - to show the gap.

THE MENU (DOGE perp, 1h and 4h bars built from 15m, 2020-09 .. 2026-08; 12bp + funding; one trade at a time)
    rsi        long when RSI(14) crosses under X (15/20/25/30); exit +1/+2/+3% or RSI back to 50; with / without "out after
               24 bars if not in profit"; 7-day cap
    capit      capitulation: RSI under 20/25 AND volume > 2x/3x; +2/+3%; with "not working"
    breakout   close above (long) / below (short) the prior N-bar extreme (20/50/100); trailing stop k x ATR (3/5/10)
    ema        EMA fast/slow cross (9/21, 20/50, 50/200), long and short, out on the reverse cross
    bb         the deployed family: Bollinger(30, 1.5) break, stop 2xATR, trail 5/10/20 x ATR, breakeven at 3R, long
    Monthly return of a configuration at leverage L = sum of its trades closed that month, each trade's return x L, a
    trade whose deepest dip reaches 1/L - 0.5% - 0.06% losing the whole stake (liquidation).
THE GOAL TEST: months at +10% or better (1,000 PKR on 10,000), the median and worst month, and 10,000 PKR compounded.

REGISTERED BEFORE THE RUN (2026-10-08)
    - The hindsight-best configuration averages >= +10% a month at 1x (2021 does most of it).
    - The walk-forward averages <= +2% a month at 1x and <= +5% at 3x.
    - Walk-forward months at >= +10%: <= 20% even at 3x; its median month <= 0.

RESULT (2026-10-08, logs/doge_focus.txt; months 2020-12 .. 2026-08, walk-forward from 2021-12, 57 months)
    - Buy and hold DOGE: avg month +20.4% (the 2021 run), MEDIAN month -3.4%, months >= +10% 32%, worst -39%.
    - Hindsight best (EMA 20/50 long, 4h): 10,000 -> 1,040,190 PKR at 1x, avg month +19.0% - median -3.4%, months
      >= +10% 22%, max fall 72%. Predicted the illusion >= +10%/month: right.
    - THE WALK-FORWARD (pick the best trailing 3/6/12 months, trade the next): 10,000 PKR -> 1,798 / 11,620 / 3,177 at
      1x; 102 / 6,370 / 383 at 2x; 0 / 731 / 8 at 3x. Avg month -2.3..+2.7%, median 0 to -2.5%, months up 28-35%.
      Predicted <= +2% at 1x and <= +5% at 3x, median <= 0: right. Months >= +10% at 3x: 25-32% (predicted <= 20%:
      WRONG) - but those months sit beside -60..-95% months, and the 3x accounts end at 0-731 PKR.
    - Every configuration at 3x since 2021-12: the most frequent +10% months (42-49%) all come with accounts ending
      near 0.
    Reading: studying ONE coin does not reach 1,000 PKR every month on 10,000; adapting to DOGE's recent past (the
    only way to "study" it without seeing the future) loses at 1x on two of three look-backs. Months of +10% exist in
    every leveraged version - they are paid for by months that wipe the account.

    python -m backtest.doge_focus
"""
from __future__ import annotations

import itertools
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import odds_now as on  # noqa: E402
from backtest.rsi_factors import bars, prep  # noqa: E402
from backtest.rsi_only import FEE  # noqa: E402

LOG = ROOT / "logs" / "doge_focus.txt"
COIN = "DOGEUSDT"
TFS = {"1h": 4, "4h": 16}
LEVS = (1, 2, 3)
START = 10_000.0
MAINT = 0.005


# ---------------------------------------------------------------- exits

def exit_target(i, side, tp, rsi_lvl, nw, P, fc, cap):
    """Target (intrabar, first), RSI level at a close, not-working after nw bars - out at the next open; cap at the
    close. Returns (exit bar for the next signal, net, worst, exit bar index for the calendar)."""
    o, h, l, c, r = P["o"], P["h"], P["l"], P["c"], P["r"]
    n = len(c)
    e = o[i + 1]
    j_end = min(i + 1 + cap, n - 2)
    js = np.arange(i + 1, j_end + 1)
    adv = (1 - l[i + 1:j_end + 1] / e) if side > 0 else (h[i + 1:j_end + 1] / e - 1)
    cw = np.maximum.accumulate(adv)
    cands = []
    if tp is not None:
        hit = (h[i + 1:j_end + 1] >= e * (1 + tp)) if side > 0 else (l[i + 1:j_end + 1] <= e * (1 - tp))
        if hit.any():
            cands.append((int(js[np.argmax(hit)]), 0))
    if rsi_lvl is not None:
        rr = r[i + 1:j_end + 1]
        hit = (rr >= rsi_lvl) if side > 0 else (rr <= rsi_lvl)
        if hit.any():
            cands.append((int(js[np.argmax(hit)]), 1))
    if nw is not None:
        cl = c[i + 1:j_end + 1]
        hit = ((js - i) >= nw) & ((cl <= e) if side > 0 else (cl >= e))
        if hit.any():
            cands.append((int(js[np.argmax(hit)]), 1))
    if cands:
        j, kind = min(cands)
        worst = float(cw[j - (i + 1)])
        if kind == 0:
            return j, tp - FEE - side * (fc[j] - fc[i + 1]) / e, worst, j
        return j + 1, side * (o[j + 1] / e - 1) - FEE - side * (fc[j + 1] - fc[i + 1]) / e, worst, j + 1
    return j_end, side * (c[j_end] / e - 1) - FEE - side * (fc[j_end] - fc[i + 1]) / e, float(cw[-1]), j_end


def exit_trail(i, side, k_trail, P, fc, s0=2.0, be=None, cap=5000):
    """Initial stop s0 x ATR from the entry, trail = best price -/+ k_trail x ATR (bar's ATR), breakeven once the best
    price is `be` R in profit; the stop in force during a bar is the one set at the previous close; a gap fills at the
    open. Returns (next-signal bar, net, worst, exit bar)."""
    o, h, l, c, a = P["o"], P["h"], P["l"], P["c"], P["atr"]
    n = len(c)
    e = o[i + 1]
    r0 = s0 * a[i]
    stop, best = e - side * r0, e
    worst = 0.0
    for j in range(i + 1, min(i + 1 + cap, n - 1)):
        adv = (1 - l[j] / e) if side > 0 else (h[j] / e - 1)
        if (l[j] <= stop) if side > 0 else (h[j] >= stop):
            fill = min(o[j], stop) if side > 0 else max(o[j], stop)
            worst = max(worst, adv)
            return j, side * (fill / e - 1) - FEE - side * (fc[j] - fc[i + 1]) / e, worst, j
        worst = max(worst, adv)
        best = max(best, h[j]) if side > 0 else min(best, l[j])
        cand = best - side * k_trail * a[j]
        if be is not None and (best - e) * side / r0 >= be:
            cand = max(cand, e) if side > 0 else min(cand, e)
        stop = max(stop, cand) if side > 0 else min(stop, cand)
    j = min(i + cap, n - 2)
    return j, side * (c[j] / e - 1) - FEE - side * (fc[j] - fc[i + 1]) / e, worst, j


def exit_cross(i, side, fast, slow, P, fc):
    o, c = P["o"], P["c"]
    up = fast > slow
    n = len(c)
    rng = np.arange(i + 1, n - 1)
    rev = (~up[i + 1:n - 1]) if side > 0 else up[i + 1:n - 1]
    j = int(rng[np.argmax(rev)]) if rev.any() else n - 2
    e = o[i + 1]
    adv = (1 - P["l"][i + 1:j + 1] / e) if side > 0 else (P["h"][i + 1:j + 1] / e - 1)
    return j + 1, side * (o[j + 1] / e - 1) - FEE - side * (fc[j + 1] - fc[i + 1]) / e, float(adv.max()), j + 1


# ---------------------------------------------------------------- the menu

def configs():
    out = []
    for tf in TFS:
        for X, ex, nw in itertools.product((15, 20, 25, 30), ("tp1", "tp2", "tp3", "rsi50"), (None, 24)):
            out.append(dict(fam="rsi", tf=tf, X=X, ex=ex, nw=nw, side=1))
        for X, vm, tp in itertools.product((20, 25), (2.0, 3.0), (0.02, 0.03)):
            out.append(dict(fam="capit", tf=tf, X=X, vm=vm, tp=tp, nw=24, side=1))
        for N, k, side in itertools.product((20, 50, 100), (3.0, 5.0, 10.0), (1, -1)):
            out.append(dict(fam="breakout", tf=tf, N=N, k=k, side=side))
        for (f, s), side in itertools.product(((9, 21), (20, 50), (50, 200)), (1, -1)):
            out.append(dict(fam="ema", tf=tf, f=f, s=s, side=side))
        for k in (5.0, 10.0, 20.0):
            out.append(dict(fam="bb", tf=tf, k=k, side=1))
    return out


def name(cf):
    return " ".join(f"{k}={v}" for k, v in cf.items())


def trades_for(cf, D):
    P, fc, t = D[cf["tf"]]
    o, c, r, v = P["o"], P["c"], P["r"], P["v"]
    n = len(c)
    side = cf["side"]
    if cf["fam"] in ("rsi", "capit"):
        sig = np.r_[False, (r[:-1] >= cf["X"]) & (r[1:] < cf["X"])]
        if cf["fam"] == "capit":
            sig &= v > cf["vm"] * pd.Series(v).rolling(20).mean().shift(1).to_numpy()
    elif cf["fam"] == "breakout":
        hi = pd.Series(P["h"]).rolling(cf["N"]).max().shift(1).to_numpy()
        lo = pd.Series(P["l"]).rolling(cf["N"]).min().shift(1).to_numpy()
        sig = (c > hi) if side > 0 else (c < lo)
    elif cf["fam"] == "ema":
        ef = pd.Series(c).ewm(span=cf["f"], adjust=False).mean().to_numpy()
        es = pd.Series(c).ewm(span=cf["s"], adjust=False).mean().to_numpy()
        up = ef > es
        sig = np.r_[False, up[1:] & ~up[:-1]] if side > 0 else np.r_[False, ~up[1:] & up[:-1]]
    else:                                                       # bb(30, 1.5) break
        mid = pd.Series(c).rolling(30).mean().to_numpy()
        sd = pd.Series(c).rolling(30).std(ddof=0).to_numpy()
        sig = c > mid + 1.5 * sd
    sig = np.asarray(sig, bool)
    sig[:250] = False
    cap = 7 * 96 // TFS[cf["tf"]]
    out, free = [], 0
    for i in np.flatnonzero(sig):
        if i < free or i + 3 >= n:
            continue
        if cf["fam"] == "rsi":
            tp = {"tp1": 0.01, "tp2": 0.02, "tp3": 0.03}.get(cf["ex"])
            j, net, worst, jx = exit_target(i, 1, tp, 50.0 if cf["ex"] == "rsi50" else None, cf["nw"], P, fc, cap)
        elif cf["fam"] == "capit":
            j, net, worst, jx = exit_target(i, 1, cf["tp"], None, cf["nw"], P, fc, cap)
        elif cf["fam"] == "breakout":
            j, net, worst, jx = exit_trail(i, side, cf["k"], P, fc, s0=cf["k"])
        elif cf["fam"] == "ema":
            j, net, worst, jx = exit_cross(i, side, ef, es, P, fc)
        else:
            j, net, worst, jx = exit_trail(i, 1, cf["k"], P, fc, s0=2.0, be=3.0)
        out.append((t[i + 1], t[min(jx, n - 1)], net, worst))
        free = j + 1
    return pd.DataFrame(out, columns=["t_entry", "t_exit", "net", "worst"])


def monthly(T, lev, months):
    """Sum of trade returns at leverage lev by the month they were OPENED (a configuration picked for month m gets
    exactly the trades it opens in m); liquidation = the whole stake."""
    liq = 1 / lev - MAINT - FEE / 2
    x = np.where(T.worst >= liq, -1.0, np.maximum(lev * T.net, -1.0))
    s = pd.Series(x, index=pd.to_datetime(T.t_entry).dt.to_period("M")).groupby(level=0).sum()
    return s.reindex(months, fill_value=0.0).clip(lower=-1.0)


def stats(m):
    eq = START * np.cumprod(1 + m.to_numpy())
    peak = np.maximum.accumulate(eq)
    return dict(avg=m.mean(), median=m.median(), p10=np.mean(m >= 0.10), worst=m.min(), up=np.mean(m > 0),
                end=eq[-1], dd=float(np.max(1 - eq / peak)))


def main():
    t0 = time.time()
    D = {}
    for tf, k in TFS.items():
        d = bars(COIN, k)
        P = prep(d, np.full(len(d), np.nan))
        D[tf] = (P, on.fund_by_bar(COIN, d.time, P["o"]), d.time.to_numpy())
    cfs = configs()
    months = pd.period_range("2020-12", "2026-08", freq="M")
    M = {lev: {} for lev in LEVS}
    for cf in cfs:
        T = trades_for(cf, D)
        for lev in LEVS:
            M[lev][name(cf)] = monthly(T, lev, months)
    print(f"  {len(cfs)} configurations ({time.time() - t0:.0f}s)", flush=True)
    lines = [f"backtest/doge_focus.py, {pd.Timestamp.now():%Y-%m-%d %H:%M}; DOGE only, {len(cfs)} configurations, months "
             f"{months[0]} .. {months[-1]}; 'months >= +10%' = 1,000 PKR on 10,000", ""]
    bh = pd.Series(D["4h"][0]["c"], index=pd.to_datetime(D["4h"][2])).resample("ME").last().pct_change()
    bh.index = bh.index.to_period("M")
    bhs = stats(bh.reindex(months).fillna(0.0))
    lines.append(f"BUY AND HOLD DOGE (1x): avg month {bhs['avg'] * 100:+.1f}%, median {bhs['median'] * 100:+.1f}%, months >= +10% "
                 f"{bhs['p10']:.0%}, worst {bhs['worst'] * 100:+.0f}%, 10,000 -> {bhs['end']:,.0f} PKR")
    lines.append("\n1. THE HINDSIGHT ILLUSION - the configuration that was best over the whole period:")
    for lev in LEVS:
        tot = {k: stats(v)["end"] for k, v in M[lev].items()}
        best = max(tot, key=tot.get)
        s = stats(M[lev][best])
        lines.append(f"  {lev}x: {best}\n      avg month {s['avg'] * 100:+.1f}%, median {s['median'] * 100:+.1f}%, months >= +10% "
                     f"{s['p10']:.0%}, months up {s['up']:.0%}, worst {s['worst'] * 100:+.0f}%, 10,000 -> {s['end']:,.0f} PKR, "
                     f"max fall {s['dd']:.0%}")
    lines.append("\n2. THE WALK-FORWARD - each month, the configuration with the best trailing record, traded NEXT month:")
    first = pd.Period("2021-12", "M")
    for look in (3, 6, 12):
        for lev in LEVS:
            names = list(M[1])
            got, picks = [], []
            for k_, m in enumerate(months):
                if m < first:
                    continue
                past = [mm for mm in months if m - look <= mm < m]
                score = {nm: M[1][nm].reindex(past).sum() for nm in names}       # picked on the 1x record
                pick = max(score, key=score.get)
                got.append(M[lev][pick][m])
                picks.append(pick.split(" ")[0])
            g = pd.Series(got, index=[m for m in months if m >= first])
            s = stats(g)
            fams = pd.Series(picks).value_counts().head(3).to_dict()
            lines.append(f"  look-back {look:>2}m, {lev}x: avg month {s['avg'] * 100:+5.1f}%, median {s['median'] * 100:+5.1f}%, "
                         f"months >= +10% {s['p10']:4.0%}, months up {s['up']:4.0%}, worst {s['worst'] * 100:+4.0f}%, "
                         f"10,000 -> {s['end']:>10,.0f} PKR ({len(g)} months), max fall {s['dd']:.0%}; picks {fams}")
    lines.append("\n3. EVERY CONFIGURATION, months >= +10% at 3x (the goal), best 8 over 2021-12 .. :")
    rows = []
    for nm, m in M[3].items():
        mm = m[m.index >= first]
        rows.append((nm, np.mean(mm >= 0.10), mm.mean(), mm.median(), stats(mm)["end"]))
    for nm, p10, avg, med, end in sorted(rows, key=lambda x: -x[1])[:8]:
        lines.append(f"  {p10:4.0%} of months  avg {avg * 100:+5.1f}%  median {med * 100:+5.1f}%  10,000 -> {end:>10,.0f}  {nm}")
    txt = "\n".join(lines)
    print(txt)
    LOG.write_text(txt + "\n")
    print(f"\n-> {LOG} ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
