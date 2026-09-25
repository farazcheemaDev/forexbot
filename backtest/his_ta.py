"""THE RETAIL TOOLKIT AT HIS MOMENTS - smart-money concepts and the standard indicators, tick-exact.

The user, 2026-09-26: "there must be something you are missing, cross check his everything". §17-29 read his
entries against price features, ticks, other markets, order flow, the news calendar and Trump's posts.
Never tested: the chart method most retail traders in Pakistan actually learn - SMC (smart-money concepts:
liquidity sweeps, fair value gaps, break of structure, premium/discount) - and the standard indicators
(EMA, RSI, Stochastic, MACD, Bollinger). §26's one real marker, the rejection wick, is what an SMC trader
calls a liquidity sweep, and "the pause" is what they call a retracement into a fair value gap.

All sign-aligned to his direction s, from USTECm mid ticks (ustec_tick_days.pkl) rebuilt into 1-minute and
5-minute candles; only CLOSED candles plus the current price are used.
  1m: ema9, ema21 (price - EMA, in ATR14), emax (EMA9 - EMA21), rsi (RSI14), stoch (%K 14), macd
      (histogram / ATR), bbpb (Bollinger %B 20,2), fvg (price at an unfilled fair value gap in his
      direction formed in the last 30 bars, +-0.25 ATR), sweep (one of the last 3 candles ran the prior
      10-bar low - high for a sell - and closed back inside), bos (a close beyond the prior 20-bar high -
      low for a sell - in the last 15 bars), discount (position in the last 60 min's range: low = cheap
      for his direction)
  5m: ema20_5, rsi_5, fvg_5 (last 12 bars), sweep_5 (last 2 bars vs the prior 12), trend_5 (the 1-hour
      move / ATR)
STAGE A: his 26 clean entries (April on) vs ~80 moments of the SAME day within 20 minutes, same direction
(his_local.py's design). Warm-up: 30 one-minute and 12 five-minute candles (from 10:00 ET; the tick cache
starts at 09:30). A first run required 60 / 20 and silently kept only 17 of the 26 entries - the whole
11:00-11:15 cluster - so it was rerun; both are in his_strategy.md s30. Continuous features by rank (0.50 = ordinary); flags by his rate vs the nearby
rate (Poisson-binomial). Holm over 16.
STAGE B: all tick days, 40 random seconds a day x both directions: does the feature (top vs bottom third,
or flag on vs off) move the 3-minute mid race, on both halves - and the NET race (at the quote, +7/-7 on
the exit side), where 50% is break-even?

REGISTERED PREDICTION (2026-09-26, before running): the toolkit does not find his pick. sweep may show
(his rate ~1.5x nearby, p ~0.05, the rejection wick again); fvg, bos, the EMAs and the oscillators are
ordinary; nothing survives Holm over 16. In B no feature moves the net race by more than 3 points and
none reaches 50%.

    python -m backtest.his_ta
"""
from __future__ import annotations

import pickle
import sys
from math import erf, sqrt
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.his_local import race  # noqa: E402
from backtest.his_predictors import race_net  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
TICKS = ROOT / "strategy_analysis" / "data" / "ustec_tick_days.pkl"
GMT = 5.0
CONT = ("ema9", "ema21", "emax", "rsi", "stoch", "macd", "bbpb", "discount", "ema20_5", "rsi_5", "trend_5")
FLAGS = ("fvg", "sweep", "bos", "fvg_5", "sweep_5")
FEATS = CONT + FLAGS


def ema(x, n):
    a, out = 2 / (n + 1), np.empty_like(x)
    out[0] = x[0]
    for i in range(1, len(x)):
        out[i] = a * x[i] + (1 - a) * out[i - 1]
    return out


def wilder(x, n):
    out = np.empty_like(x)
    out[0] = x[0]
    for i in range(1, len(x)):
        out[i] = out[i - 1] + (x[i] - out[i - 1]) / n
    return out


def candles(ts, mid, w):
    idx = (ts // w).astype(int)
    df = pd.DataFrame({"i": idx, "p": mid}).groupby("i").p.agg(["first", "max", "min", "last"])
    df = df.reindex(range(0, idx.max() + 1))
    df["last"] = df["last"].ffill()
    for c in ("first", "max", "min"):
        df[c] = df[c].fillna(df["last"])
    o, h, l, c = (df[k].to_numpy(float) for k in ("first", "max", "min", "last"))
    tr = np.maximum(h - l, np.abs(np.r_[h[0], h[1:]] - np.r_[c[0], c[:-1]]))
    tr = np.maximum(tr, np.abs(np.r_[l[0], l[1:]] - np.r_[c[0], c[:-1]]))
    d = np.diff(c, prepend=c[0])
    up, dn = wilder(np.maximum(d, 0), 14), wilder(np.maximum(-d, 0), 14)
    rsi = 100 - 100 / (1 + up / np.where(dn > 0, dn, np.nan))
    rsi = np.where(dn > 0, rsi, 100.0)
    macd = ema(c, 12) - ema(c, 26)
    s20 = pd.Series(c).rolling(20)
    mu, sd = s20.mean().to_numpy(), s20.std(ddof=0).to_numpy()
    lo14 = pd.Series(l).rolling(14).min().to_numpy()
    hi14 = pd.Series(h).rolling(14).max().to_numpy()
    return dict(o=o, h=h, l=l, c=c, atr=wilder(tr, 14), ema9=ema(c, 9), ema20=ema(c, 20), ema21=ema(c, 21), rsi=rsi,
                hist=macd - ema(macd, 9), pb=(c - (mu - 2 * sd)) / np.where(sd > 0, 4 * sd, np.nan),
                stoch=100 * (c - lo14) / np.where(hi14 > lo14, hi14 - lo14, np.nan))


def fvg(B, k, p, s, look):
    h, l, a = B["h"], B["l"], B["atr"][k]
    for j in range(max(2, k - look + 1), k + 1):
        if s == 1 and h[j - 2] < l[j]:
            bot, top = h[j - 2], l[j]
            if (j == k or l[j + 1:k + 1].min() > bot) and bot - 0.25 * a <= p <= top + 0.25 * a:
                return True
        if s == -1 and l[j - 2] > h[j]:
            bot, top = h[j], l[j - 2]
            if (j == k or h[j + 1:k + 1].max() < top) and bot - 0.25 * a <= p <= top + 0.25 * a:
                return True
    return False


def sweep(B, k, s, last, ref):
    h, l, c = B["h"], B["l"], B["c"]
    for j in range(k - last + 1, k + 1):
        if j - ref < 0:
            continue
        if s == 1:
            r = l[j - ref:j].min()
            if l[j] < r and c[j] > r:
                return True
        else:
            r = h[j - ref:j].max()
            if h[j] > r and c[j] < r:
                return True
    return False


def bos(B, k, s):
    h, l, c = B["h"], B["l"], B["c"]
    for j in range(max(20, k - 14), k + 1):
        if (s == 1 and c[j] > h[j - 20:j].max()) or (s == -1 and c[j] < l[j - 20:j].min()):
            return True
    return False


def feats(D, t, s):
    ts, mid, B1, B5 = D
    k, k5 = int(t // 60) - 1, int(t // 300) - 1
    if k < 30 or k5 < 12 or k >= len(B1["c"]) or k5 >= len(B5["c"]):
        return None
    i = np.searchsorted(ts, t, side="right") - 1
    p = mid[i]
    a, a5 = B1["atr"][k], B5["atr"][k5]
    if not (a > 0 and a5 > 0):
        return None
    H, L = B1["h"][max(0, k - 59):k + 1].max(), B1["l"][max(0, k - 59):k + 1].min()
    pos = (p - L) / (H - L) if H > L else 0.5
    osc = lambda v: v if s == 1 else 100 - v  # noqa: E731
    return dict(ema9=s * (p - B1["ema9"][k]) / a, ema21=s * (p - B1["ema21"][k]) / a,
                emax=s * (B1["ema9"][k] - B1["ema21"][k]) / a, rsi=osc(B1["rsi"][k]), stoch=osc(B1["stoch"][k]),
                macd=s * B1["hist"][k] / a, bbpb=B1["pb"][k] if s == 1 else 1 - B1["pb"][k],
                discount=pos if s == 1 else 1 - pos, ema20_5=s * (p - B5["ema20"][k5]) / a5, rsi_5=osc(B5["rsi"][k5]),
                trend_5=s * (p - B5["c"][k5 - 12]) / a5,
                fvg=fvg(B1, k, p, s, 30), sweep=sweep(B1, k, s, 3, 10), bos=bos(B1, k, s),
                fvg_5=fvg(B5, k5, p, s, 12), sweep_5=sweep(B5, k5, s, 2, 12))


def pz(z):
    return 2 * (1 - 0.5 * (1 + erf(abs(z) / sqrt(2))))


def main():
    cache = pickle.loads(TICKS.read_bytes())
    days = [d for d in sorted(cache) if cache[d] is not None]
    DD = {}
    def day(d):
        if d not in DD:
            ts, mid, spr = cache[d]
            DD[d] = (ts, mid, candles(ts, mid, 60), candles(ts, mid, 300))
        return DD[d]
    x = pd.read_csv(ROOT / "strategy_analysis" / "statement_trades.csv", parse_dates=["open_time"])
    x = x[x.symbol.str.startswith("NASDAQ")].copy()
    x["utc"] = x.open_time - pd.Timedelta(hours=GMT)
    x = x[x.utc >= "2026-04-01"]
    rng = np.random.default_rng(17)
    ranks, flag_obs, flag_ps, his_rows = [], {k: 0 for k in FLAGS}, {k: [] for k in FLAGS}, []
    for r in x.itertuples():
        et = pd.Timestamp(r.utc).tz_localize("UTC").tz_convert("America/New_York").tz_localize(None)
        d = et.normalize()
        if d not in cache or cache[d] is None:
            continue
        D = day(d)
        t0 = (et - (d + pd.Timedelta(hours=9, minutes=30))).total_seconds()
        s = 1 if r.side == "BUY" else -1
        mine = feats(D, t0, s)
        if mine is None:
            continue
        near = []
        for _ in range(200):
            f = feats(D, t0 + rng.uniform(30, 1200) * rng.choice((-1, 1)), s)
            if f is not None:
                near.append(f)
            if len(near) >= 80:
                break
        N = pd.DataFrame(near)
        ranks.append({k: (N[k].dropna() < mine[k]).mean() + 0.5 * (N[k].dropna() == mine[k]).mean()
                      for k in CONT if np.isfinite(mine[k])})
        for k in FLAGS:
            flag_obs[k] += mine[k]
            flag_ps[k].append(N[k].mean())
        his_rows.append(mine | {"et": et, "side": r.side, "net": r.net})
    RA = pd.DataFrame(ranks)
    pA, lines = {}, []
    for k in CONT:
        v = RA[k].dropna()
        z = (v.mean() - 0.5) / (np.sqrt(1 / 12) / np.sqrt(len(v)))
        pA[k] = pz(z)
        lines.append((k, f"rank {v.mean():.2f}  (top third {np.mean(v > 2/3)*100:3.0f}%)"))
    for k in FLAGS:
        ps = np.array(flag_ps[k])
        e, var = ps.sum(), (ps * (1 - ps)).sum()
        pA[k] = pz((flag_obs[k] - e) / sqrt(var)) if var > 0 else 1.0
        lines.append((k, f"his {flag_obs[k]:>2} / {len(ps)}  nearby rate {ps.mean()*100:4.1f}%  ratio {flag_obs[k] / e if e else np.nan:4.2f}"))
    order = sorted(pA, key=pA.get)
    holm = {k: min(1.0, max(pA[j] * (len(pA) - i) for i, j in enumerate(order[:order.index(k) + 1]))) for k in pA}
    out = [f"STAGE A - his {len(RA)} clean entries vs ~80 moments of the same day within 20 min, same direction"]
    for k, txt in lines:
        out.append(f"  {k:<9}{txt:<52} p {pA[k]:.3f}  Holm {holm[k]:.3f}")

    rows = []
    for d in days:
        D = day(d)
        ts, mid, spr = cache[d]
        for t in rng.uniform(1800, 23400, 40):
            for s in (1, -1):
                f = feats(D, t, s)
                o = race(ts, mid, t, s)
                if f is None or o is None:
                    continue
                rows.append(f | {"o": o, "on": race_net(ts, mid, spr, t, s), "day": d})
    P = pd.DataFrame(rows)
    mid_day = days[len(days) // 2]
    w = lambda g, c="o": g[c].dropna().mean() * 100 if len(g) else np.nan  # noqa: E731
    out.append(f"\nSTAGE B - {len(P)} random moment x direction pairs on {P.day.nunique()} days; mid race (base "
               f"{w(P):.1f}%) and NET race (base {w(P, 'on'):.1f}%, break-even 50%)")
    out.append(f"  {'feature':<9}{'low/off':>9}{'high/on':>9}{'diff':>7}{'1st half':>9}{'2nd half':>9}{'net high/on':>13}{'n':>7}")
    for k in FEATS:
        q = P.dropna(subset=[k])
        if k in FLAGS:
            hi_m, lo_m = q[k].astype(bool), ~q[k].astype(bool)
        else:
            lo, hi = q[k].quantile(1 / 3), q[k].quantile(2 / 3)
            hi_m, lo_m = q[k] >= hi, q[k] <= lo
        h1, h2 = q.day < mid_day, q.day >= mid_day
        out.append(f"  {k:<9}{w(q[lo_m]):>8.1f}%{w(q[hi_m]):>8.1f}%{w(q[hi_m]) - w(q[lo_m]):>+7.1f}"
                   f"{w(q[hi_m & h1]) - w(q[lo_m & h1]):>+9.1f}{w(q[hi_m & h2]) - w(q[lo_m & h2]):>+9.1f}"
                   f"{w(q[hi_m], 'on'):>12.1f}%{int(hi_m.sum()):>7}")
    H = pd.DataFrame(his_rows)
    out.append("\nHIS ENTRIES, the flags (1 = present)")
    for r in H.itertuples():
        out.append(f"  {r.et:%Y-%m-%d %H:%M:%S} {r.side:<4} ${r.net:>8.2f}  fvg {int(r.fvg)} sweep {int(r.sweep)} bos {int(r.bos)}"
                   f"  fvg_5 {int(r.fvg_5)} sweep_5 {int(r.sweep_5)}  rsi {r.rsi:5.1f}  discount {r.discount:.2f}  ema9 {r.ema9:+.2f}")
    txt = "\n".join(out)
    print(txt)
    (ROOT / "logs" / "his_ta.txt").write_text(txt, encoding="utf-8")


if __name__ == "__main__":
    main()
