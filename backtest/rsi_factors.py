"""RSI(14) BOTH WAYS WITH NO FIXED STOP - BUT A "FACTOR" DECIDES WHEN TO GET OUT.

THE USER (2026-10-08): "RSI 14, long and short when RSI is too high/low, with no stop loss - but we can also account
for a stop loss by looking at some factors." rsi_only.py showed the no-stop RSI trade wins 80-90% of trades and loses
in bad years through a few huge losers. This asks: can a FACTOR-based exit cut those losers without cutting the edge?

ENTRIES (rsi_only.py's): RSI(14) crosses under L (30 / 25) -> LONG; crosses over 100-L (70 / 75) -> SHORT.
    Optional trend filter: long only above the 200-bar EMA, short only below it.
PROFIT EXITS: tp2 (+2% limit) or rsi50 (RSI back through 50 at a close, out at the next open).
PROTECTIVE FACTORS (one at a time; checked at each bar's close, out at the next open, unless marked intrabar):
    none        no protection at all (rsi_only.py's trade)
    rsi_deeper  RSI keeps going: under 15 (shorts: over 85)
    level_break the close goes past the lowest low / highest high of the 50 bars BEFORE the entry
    btc_against BTC 3% against the position since the entry (for the BTC trades: BTC itself)
    vol_against a bar with volume > 3x its 20-bar average closes against the position while it is losing
    not_working after 24 bars the close is still not in profit
    atr6        a disaster stop 6 x ATR14 from the entry (intrabar; a bar touching it and the target reads as the stop)
Everything closes at market after 7 days. 12bp round trip + funding. One trade at a time per coin.
15m / 1h / 4h, BTC ETH SOL DOGE XRP, 2020-09 .. 2026-08. Tune < 2024-04-07 <= holdout.
SELECTION: the configuration (tf, side, L, profit exit, factor, trend filter) with the best TUNE average per trade,
pooled over the 5 coins, 200+ tune trades - judged on the holdout; 10,000 PKR at 1/3/5x all-in on its holdout trades.

REGISTERED BEFORE THE RUN (2026-10-08)
    - Factor exits cut the worst trade from -20..-55% to about -5..-15%, and the win rate by 5-20 points.
    - The holdout average stays at or under zero for nearly every configuration.
    - The trend filter helps longs in 2022 and hurts them in 2021.
    - Shorts stay negative in most configurations.
    - The tune-picked configuration earns at most +0.1% a trade on the holdout, below its tune value.

RESULT (2026-10-08, logs/rsi_factors.txt, logs/rsi_factors_configs.csv, logs/rsi_factors_trades.csv)
    - Longs, averaged over tf / L / profit exit, no trend filter (win | avg | worst | holdout):
        none 73% +0.08% -43.5% -0.12% | rsi_deeper 71% -0.07% -42.0% -0.33% | level_break 42% -0.17% -17.2% -0.29%
        btc_against 64% -0.23% -37.7% -0.50% | vol_against 55% -0.05% -25.6% -0.31% | not_working 60% +0.08% -33.6%
        -0.05% | atr6 68% -0.16% -36.0% -0.42%
      Every factor cuts the win rate (predicted 5-20 points: level_break cut 31); only level_break and vol_against
      cut the worst trade much (predicted -5..-15%: WRONG, -17% at best); NO factor makes the holdout positive
      (predicted: right). not_working is the least harmful - same average, holdout -0.05 vs -0.12.
    - Shorts lose with every factor in nearly every year (predicted: right).
    - Trend filter (longs, without / with): 2020 +0.30/+1.63, 2021 +0.77/+0.73, 2022 -0.56/-1.27, 2023 +0.14/+1.12,
      2024 -0.14/+0.13, 2025-26 -0.25/-0.29 %/trade. Predicted "helps in 2022, hurts in 2021": WRONG - it HURT in
      2022 (more trades bought the first dips of the turn) and was flat in 2021.
    - 16 of 336 configurations positive on both halves; the top two are 4h longs at RSI < 25, +2% target, no stop
      (holdout +0.64%, n 149, worst -51%) and the same with not_working (+0.42%, worst -29%) - rsi_only's exception.
    - Picked on the tune half: the 5 best (1h/4h longs, RSI 25/30, exit at RSI 50) all LOST on the holdout (-0.24 to
      -0.82% a trade). 10,000 PKR on one coin: 1x ends 3,286-11,411; 3x 0-5,706; 5x 0-2,267.

    python -m backtest.rsi_factors
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import odds_now as on  # noqa: E402
from backtest import scalp_15m as s15  # noqa: E402
from backtest.rsi_only import FEE, LEVELS, TFS, YEARS, rsi14  # noqa: E402

LOG = ROOT / "logs" / "rsi_factors.txt"
COINS = s15.COINS
HOLDOUT = pd.Timestamp("2024-04-07")
PROFIT = ("tp2", "rsi50")
FACTORS = ("none", "rsi_deeper", "level_break", "btc_against", "vol_against", "not_working", "atr6")
MAINT = 0.005
STAKE = 10_000.0


def bars(sym, k):
    d = s15.load(sym)
    if k == 1:
        return d.reset_index(drop=True)
    g = d.set_index("time").resample(f"{15 * k}min")
    out = pd.DataFrame({"o": g["o"].first(), "h": g["h"].max(), "l": g["l"].min(), "c": g["c"].last(),
                        "v": g["v"].sum(), "n": g["c"].count()})
    return out[out.n == k].drop(columns="n").reset_index()


def prep(d, btc_c):
    o, h, l, c, v = (d[k].to_numpy(float) for k in ("o", "h", "l", "c", "v"))
    pc = np.r_[np.nan, c[:-1]]
    tr = np.fmax(h - l, np.fmax(np.abs(h - pc), np.abs(l - pc)))
    return dict(o=o, h=h, l=l, c=c, r=rsi14(c), v=v,
                vavg=pd.Series(v).rolling(20).mean().shift(1).to_numpy(),
                atr=pd.Series(tr).ewm(alpha=1 / 14, adjust=False).mean().to_numpy(),
                ema200=pd.Series(c).ewm(span=200, adjust=False).mean().to_numpy(),
                lo50=pd.Series(l).rolling(50).min().to_numpy(), hi50=pd.Series(h).rolling(50).max().to_numpy(),
                btc=btc_c)


def trade(i, side, prof, fac, P, fc, cap):
    """Signal at bar i's close, in at o[i+1]. Returns (bar after which the next signal may come, net, worst)."""
    o, h, l, c, r = P["o"], P["h"], P["l"], P["c"], P["r"]
    n = len(c)
    e = o[i + 1]
    lvl = P["lo50"][i] if side > 0 else P["hi50"][i]            # bars up to the signal - all before the entry
    b0 = P["btc"][i]
    stop6 = e - side * 6 * P["atr"][i]
    worst = 0.0
    j_end = min(i + 1 + cap, n - 2)

    def out(j_fill_open):
        x = o[j_fill_open]
        return side * (x / e - 1) - FEE - side * (fc[j_fill_open] - fc[i + 1]) / e

    for j in range(i + 1, j_end + 1):
        adv = (1 - l[j] / e) if side > 0 else (h[j] / e - 1)
        if fac == "atr6" and ((l[j] <= stop6) if side > 0 else (h[j] >= stop6)):
            fill = min(o[j], stop6) if side > 0 else max(o[j], stop6)
            worst = max(worst, adv)
            return j, side * (fill / e - 1) - FEE - side * (fc[j] - fc[i + 1]) / e, worst
        worst = max(worst, adv)
        if prof == "tp2" and ((h[j] >= e * 1.02) if side > 0 else (l[j] <= e * 0.98)):
            return j, 0.02 - FEE - side * (fc[j] - fc[i + 1]) / e, worst
        if prof == "rsi50" and ((r[j] >= 50) if side > 0 else (r[j] <= 50)):
            return j + 1, out(j + 1), worst
        losing = (c[j] < e) if side > 0 else (c[j] > e)
        hit = False
        if fac == "rsi_deeper":
            hit = (r[j] < 15) if side > 0 else (r[j] > 85)
        elif fac == "level_break":
            hit = (c[j] < lvl) if side > 0 else (c[j] > lvl)
        elif fac == "btc_against":
            mv = P["btc"][j] / b0 - 1
            hit = np.isfinite(mv) and ((mv < -0.03) if side > 0 else (mv > 0.03))
        elif fac == "vol_against":
            against = (c[j] < o[j]) if side > 0 else (c[j] > o[j])
            hit = losing and against and np.isfinite(P["vavg"][j]) and P["v"][j] > 3 * P["vavg"][j]
        elif fac == "not_working":
            hit = (j - i >= 24) and ((c[j] <= e) if side > 0 else (c[j] >= e))
        if hit:
            return j + 1, out(j + 1), worst
    return j_end, side * (c[j_end] / e - 1) - FEE - side * (fc[j_end] - fc[i + 1]) / e, worst


def run(P, t, fc, side, L, prof, fac, trend, cap):
    r = P["r"]
    lv = L if side > 0 else 100 - L
    sig = np.r_[False, (r[:-1] >= lv) & (r[1:] < lv)] if side > 0 else np.r_[False, (r[:-1] <= lv) & (r[1:] > lv)]
    if trend:
        sig &= (P["c"] > P["ema200"]) if side > 0 else (P["c"] < P["ema200"])
    sig[:250] = False
    out, free = [], 0
    for i in np.flatnonzero(sig):
        if i < free or i + 2 >= len(r):
            continue
        j, net, worst = trade(i, side, prof, fac, P, fc, cap)
        out.append((t[i + 1], net, worst))
        free = j + 1
    return out


def play(net, worst, lev):
    liq = 1 / lev - MAINT - FEE / 2
    eq = STAKE
    for x, w in zip(net, worst):
        eq = 0.0 if w >= liq else eq * max(0.0, 1 + lev * x)
        if eq <= 0:
            break
    return eq


def main():
    t0 = time.time()
    rows = []
    for tf, k in TFS.items():
        cap = 7 * 96 // k
        btc = bars("BTCUSDT", k)
        btc_s = pd.Series(btc.c.to_numpy(float), index=btc.time)
        for sym in COINS:
            d = bars(sym, k)
            P = prep(d, btc_s.reindex(d.time).to_numpy(float))
            fc = on.fund_by_bar(sym, d.time, P["o"])
            t = d.time.to_numpy()
            for side in (1, -1):
                for L in LEVELS:
                    for prof in PROFIT:
                        for fac in FACTORS:
                            for trend in (False, True):
                                for tt, net, worst in run(P, t, fc, side, L, prof, fac, trend, cap):
                                    rows.append((tf, sym, "long" if side > 0 else "short", L, prof, fac, trend, tt, net, worst))
        print(f"  {tf} done ({time.time() - t0:.0f}s)", flush=True)
    A = pd.DataFrame(rows, columns=["tf", "coin", "side", "L", "prof", "fac", "trend", "t", "net", "worst"])
    A["t"] = pd.to_datetime(A["t"])
    A.to_csv(ROOT / "logs" / "rsi_factors_trades.csv", index=False)

    keys = ["tf", "side", "L", "prof", "fac", "trend"]
    S = []
    for kk, g in A.groupby(keys, sort=False):
        tu, ho = g[g.t < HOLDOUT].net, g[g.t >= HOLDOUT].net
        yrs = {y: g[(g.t >= a) & (g.t < b)].net.mean() for y, a, b in YEARS}
        S.append(dict(zip(keys, kk), n=len(g), win=np.mean(g.net > 0), avg=g.net.mean(), worst=g.net.min(),
                      n_t=len(tu), tune=tu.mean(), n_h=len(ho), hold=ho.mean(), **{f"y{y}": v for y, v in yrs.items()}))
    S = pd.DataFrame(S)
    S.to_csv(ROOT / "logs" / "rsi_factors_configs.csv", index=False)

    lines = [f"backtest/rsi_factors.py, {pd.Timestamp.now():%Y-%m-%d %H:%M}; {len(S)} configurations x 5 coins pooled; "
             f"tune < {HOLDOUT:%Y-%m-%d} <= holdout", ""]
    lines.append("1. WHAT EACH FACTOR DOES (averaged over tf, L, profit exit; no trend filter), pooled coins:")
    lines.append(f"  {'side':>5} {'factor':>12} {'win':>5} {'avg/trade':>10} {'worst trade':>12} {'tune':>8} {'holdout':>8}   "
                 + "  ".join(f"{y:>7}" for y, _, _ in YEARS))
    base = S[~S.trend]
    for (side, fac), g in base.groupby(["side", "fac"], sort=False):
        lines.append(f"  {side:>5} {fac:>12} {g.win.mean():>5.0%} {g.avg.mean() * 100:>+9.2f}% {g.worst.mean() * 100:>+11.1f}% "
                     f"{g.tune.mean() * 100:>+7.2f}% {g.hold.mean() * 100:>+7.2f}%   "
                     + "  ".join(f"{g[f'y{y}'].mean() * 100:>+6.2f}%" for y, _, _ in YEARS))
    lines.append("\n2. THE TREND FILTER (EMA200), longs, averaged over everything else: without / with")
    for y, _, _ in YEARS:
        a = S[(S.side == "long") & ~S.trend][f"y{y}"].mean()
        b = S[(S.side == "long") & S.trend][f"y{y}"].mean()
        lines.append(f"  {y:>7}: {a * 100:+.2f}% / {b * 100:+.2f}% a trade")
    lines.append(f"   holdout: {S[(S.side == 'long') & ~S.trend].hold.mean() * 100:+.2f}% / "
                 f"{S[(S.side == 'long') & S.trend].hold.mean() * 100:+.2f}%")
    pos = S[(S.hold > 0) & (S.n_h >= 50)]
    lines.append(f"\n3. CONFIGURATIONS POSITIVE ON THE HOLDOUT (50+ trades): {len(pos)} of {len(S)}; "
                 f"positive on BOTH halves: {int(((S.tune > 0) & (S.hold > 0) & (S.n_h >= 50)).sum())}")
    for r in S[(S.tune > 0) & (S.hold > 0) & (S.n_h >= 50)].sort_values("hold", ascending=False).head(10).itertuples():
        lines.append(f"    {r.tf:>3} {r.side:5} L{r.L} {r.prof:5} {r.fac:12} trend={str(r.trend):5} win {r.win:.0%} "
                     f"tune {r.tune * 100:+.2f}% (n {r.n_t}) holdout {r.hold * 100:+.2f}% (n {r.n_h}) worst {r.worst * 100:+.1f}%")
    lines.append("\n4. PICKED ON THE TUNE HALF (best tune average, 200+ tune trades), judged on the holdout:")
    pick = S[S.n_t >= 200].sort_values("tune", ascending=False).head(5)
    for r in pick.itertuples():
        g = A[(A.tf == r.tf) & (A.side == r.side) & (A.L == r.L) & (A.prof == r.prof) & (A.fac == r.fac)
              & (A.trend == r.trend) & (A.t >= HOLDOUT)].sort_values("t", kind="stable")
        lines.append(f"    {r.tf:>3} {r.side:5} L{r.L} {r.prof:5} {r.fac:12} trend={str(r.trend):5} tune {r.tune * 100:+.2f}% "
                     f"-> holdout {r.hold * 100:+.2f}% (n {r.n_h}, win {np.mean(g.net > 0):.0%}, worst {g.net.min() * 100:+.1f}%)")
        for lev in (1, 3, 5):                     # one coin per account: a coin's trades never overlap
            ends = [play(x.net.to_numpy(), x.worst.to_numpy(), lev) for _, x in g.groupby("coin")]
            lines.append(f"        10,000 PKR all-in on ONE coin, {lev}x: ends " + ", ".join(f"{e:,.0f}" for e in ends)
                         + f"  ({', '.join(sorted(g.coin.unique()))})")
    txt = "\n".join(lines)
    print(txt)
    LOG.write_text(txt + "\n")
    print(f"\n-> {LOG} ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
