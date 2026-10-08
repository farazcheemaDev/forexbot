"""TRADINGVIEW'S POPULAR INDICATORS, AS ENTRIES ON THE POINT-IN-TIME TOP-40 (2026-10-08).

THE USER: "groundbreaking edge ... rsi or the volume indicators or live analysing TradingView ... whatever." Doc 02
already holds MA cross, Donchian, RSI, MACD, ROC, Bollinger, StochRSI, VWAP reversion, VSA. These are the community
favourites that were NOT tested here, each as a LONG entry, with the deployed Bollinger(30, 1.5) break as the baseline:
    supertrend   SuperTrend(10, 3) flips up
    squeeze      LazyBear squeeze: Bollinger(20,2) was inside Keltner(20,1.5) last bar and is not now, momentum > 0
    ichimoku     close crosses above the cloud (Senkou A/B 26 bars back) with Tenkan > Kijun
    psar         Parabolic SAR (0.02, 0.2) flips below price
    hull         Hull MA(55) turns up
    willr        Williams %R(14) crosses up through -80
    cci          CCI(20) crosses up through +100
    mfi          MFI(14) (volume-weighted RSI) crosses up through 20
    obv          OBV makes a 20-bar high while the close makes a 20-bar high
    heikin       two green Heikin-Ashi candles with no lower wick after a red one
    vwap         close crosses above the 24-bar rolling VWAP
    bb           Bollinger(30, 1.5) close above the upper band (the deployed entry - the baseline)
EXITS: trail5 - stop 2xATR, trail 5xATR from the best price, breakeven at 3R (doge_focus.exit_trail, tested); and
    own - out at the next open after the entry's opposite condition (SuperTrend / PSAR flip down, Hull down, close back
    under VWAP / Kijun / the middle band ...), 30-day cap. 12bp + funding; one trade at a time per coin.
4h bars at 4 phases and 1d bars, 2020 .. 2026-09, point-in-time top-40 (dead coins in). Per indicator: trades, win,
avg per trade, tune / holdout, t by DISTINCT DAY, and the gap to the bb baseline on the same bars.

REGISTERED BEFORE THE RUN (2026-10-08)
    - No indicator beats bb's average on BOTH halves in >= 3 of the 4 4h phases.
    - SuperTrend / squeeze / ichimoku / psar / hull land near bb (all breakouts underneath).
    - willr and mfi (reversal entries) lose with the trend exit.

RESULT (2026-10-08, logs/tv_indicators.txt): on 4h bars every indicator - and the bb baseline - is negative or ~0 on
    the holdout with either exit; none beats bb with its own exit in any phase; mfi "beats" bb with trail5 in 3 of 4
    phases only because both sit at ~0 / negative (prediction "none in >= 3 of 4": technically WRONG, meaninglessly).
    willr / mfi as reversal entries lose (right). The one standout: bb on DAILY bars with its own exit (close under the
    30-day mean): +7.35% a trade, tune +10.0 / holdout +2.0%, t by day +3.3 -> pair_books.py, daily_phase.py.

    python -m backtest.tv_indicators
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest.capitulation_wide import funding_cum, hourly  # noqa: E402
from backtest.doge_focus import exit_trail  # noqa: E402
from backtest.rsi_factors import prep  # noqa: E402
from backtest.rsi_only import FEE  # noqa: E402
from backtest.wide_book import eligibility  # noqa: E402

LOG = ROOT / "logs" / "tv_indicators.txt"
GRIDS = (("4h", 0), ("4h", 60), ("4h", 120), ("4h", 180), ("1d", 0))
HOLDOUT = pd.Timestamp("2024-04-07")
NAMES = ("supertrend", "squeeze", "ichimoku", "psar", "hull", "willr", "cci", "mfi", "obv", "heikin", "vwap", "bb")


def bars(h, tf, off):
    rule = "240min" if tf == "4h" else "1440min"
    n_need = 4 if tf == "4h" else 24
    g = h.set_index("time").resample(rule, offset=f"{off}min")
    d = pd.DataFrame({"o": g["open"].first(), "h": g["high"].max(), "l": g["low"].min(), "c": g["close"].last(),
                      "v": g["qvol"].sum(), "n": g["close"].count()})
    return d[d.n == n_need].drop(columns="n").reset_index()


def wma(x, n):
    """Linearly weighted moving average, vectorised (weights 1..n, newest heaviest); NaN until n values."""
    x = np.asarray(x, float)
    w = np.arange(1, n + 1, dtype=float)
    out = np.full(len(x), np.nan)
    if len(x) >= n:
        out[n - 1:] = np.convolve(np.nan_to_num(x), w[::-1], mode="valid") / w.sum()
        bad = pd.Series(np.isnan(x).astype(float)).rolling(n).sum().to_numpy() > 0
        out[bad] = np.nan
    return out


def indicators(P):
    """(entry, own-exit) boolean arrays per indicator - each reads bar i and earlier only."""
    o, h, l, c, v, atr = P["o"], P["h"], P["l"], P["c"], P["v"], P["atr"]
    n = len(c)
    S = pd.Series
    out = {}
    # SuperTrend(10, 3)
    a10 = S(np.fmax(h - l, np.fmax(np.abs(h - np.r_[c[0], c[:-1]]), np.abs(l - np.r_[c[0], c[:-1]])))).rolling(10).mean().to_numpy()
    hl2 = (h + l) / 2
    up, dn = hl2 - 3 * a10, hl2 + 3 * a10
    fu, fd, trend = up.copy(), dn.copy(), np.ones(n, int)
    for i in range(1, n):
        fu[i] = max(up[i], fu[i - 1]) if c[i - 1] > fu[i - 1] else up[i]
        fd[i] = min(dn[i], fd[i - 1]) if c[i - 1] < fd[i - 1] else dn[i]
        trend[i] = 1 if c[i] > fd[i - 1] else (-1 if c[i] < fu[i - 1] else trend[i - 1])
    flip_up = np.r_[False, (trend[1:] == 1) & (trend[:-1] == -1)]
    out["supertrend"] = (flip_up, np.r_[False, (trend[1:] == -1) & (trend[:-1] == 1)])
    # squeeze
    mid, sd = S(c).rolling(20).mean().to_numpy(), S(c).rolling(20).std(ddof=0).to_numpy()
    kc = S(np.fmax(h - l, 0)).rolling(20).mean().to_numpy()
    sq_on = (mid - 2 * sd > mid - 1.5 * kc) & (mid + 2 * sd < mid + 1.5 * kc)
    mom = c - (S(h).rolling(20).max().to_numpy() + S(l).rolling(20).min().to_numpy()) / 4 - mid / 2
    out["squeeze"] = (np.r_[False, sq_on[:-1] & ~sq_on[1:]] & (mom > 0), c < mid)
    # Ichimoku
    ten = (S(h).rolling(9).max() + S(l).rolling(9).min()).to_numpy() / 2
    kij = (S(h).rolling(26).max() + S(l).rolling(26).min()).to_numpy() / 2
    sa = np.r_[np.full(26, np.nan), ((ten + kij) / 2)[:-26]]
    sb_raw = (S(h).rolling(52).max() + S(l).rolling(52).min()).to_numpy() / 2
    sb = np.r_[np.full(26, np.nan), sb_raw[:-26]]
    top = np.fmax(sa, sb)
    above = c > top
    out["ichimoku"] = (np.r_[False, above[1:] & ~above[:-1]] & (ten > kij), c < kij)
    # Parabolic SAR
    sar, bull, ep, af = np.full(n, np.nan), True, h[0], 0.02
    sar[0] = l[0]
    for i in range(1, n):
        s_ = sar[i - 1] + af * (ep - sar[i - 1])
        if bull:
            s_ = min(s_, l[i - 1], l[i - 2] if i > 1 else l[i - 1])
            if l[i] < s_:
                bull, s_, ep, af = False, ep, l[i], 0.02
            elif h[i] > ep:
                ep, af = h[i], min(af + 0.02, 0.2)
        else:
            s_ = max(s_, h[i - 1], h[i - 2] if i > 1 else h[i - 1])
            if h[i] > s_:
                bull, s_, ep, af = True, ep, h[i], 0.02
            elif l[i] < ep:
                ep, af = l[i], min(af + 0.02, 0.2)
        sar[i] = s_
    below = sar < c
    out["psar"] = (np.r_[False, below[1:] & ~below[:-1]], np.r_[False, ~below[1:] & below[:-1]])
    # Hull MA(55)
    hull = wma(2 * wma(c, 27) - wma(c, 55), 7)
    rising = np.r_[False, hull[1:] > hull[:-1]]
    out["hull"] = (np.r_[False, rising[1:] & ~rising[:-1]], np.r_[False, ~rising[1:] & rising[:-1]])
    # Williams %R(14)
    hh, ll = S(h).rolling(14).max().to_numpy(), S(l).rolling(14).min().to_numpy()
    wr = -100 * (hh - c) / (hh - ll)
    out["willr"] = (np.r_[False, (wr[:-1] < -80) & (wr[1:] >= -80)], wr > -20)
    # CCI(20)
    tp = (h + l + c) / 3
    md = np.full(n, np.nan)
    if n >= 20:
        win = np.lib.stride_tricks.sliding_window_view(tp, 20)
        md[19:] = np.mean(np.abs(win - win.mean(axis=1, keepdims=True)), axis=1)
    cci = (tp - S(tp).rolling(20).mean().to_numpy()) / (0.015 * md)
    out["cci"] = (np.r_[False, (cci[:-1] <= 100) & (cci[1:] > 100)], cci < 0)
    # MFI(14)
    mf = tp * v
    pos = S(np.where(np.r_[False, tp[1:] > tp[:-1]], mf, 0.0)).rolling(14).sum().to_numpy()
    neg = S(np.where(np.r_[False, tp[1:] < tp[:-1]], mf, 0.0)).rolling(14).sum().to_numpy()
    with np.errstate(divide="ignore", invalid="ignore"):
        mfi = 100 - 100 / (1 + pos / neg)
    out["mfi"] = (np.r_[False, (mfi[:-1] < 20) & (mfi[1:] >= 20)], mfi > 80)
    # OBV
    obv = np.cumsum(np.sign(np.r_[0.0, np.diff(c)]) * v)
    out["obv"] = ((obv >= S(obv).rolling(20).max().to_numpy()) & (c >= S(c).rolling(20).max().to_numpy()),
                  c < S(c).rolling(20).mean().to_numpy())
    # Heikin-Ashi
    hc = (o + h + l + c) / 4
    ho = np.empty(n)
    ho[0] = (o[0] + c[0]) / 2
    for i in range(1, n):
        ho[i] = (ho[i - 1] + hc[i - 1]) / 2
    hl_ = np.fmin(l, np.fmin(ho, hc))
    green = hc > ho
    nowick = np.isclose(hl_, np.fmin(ho, hc))
    out["heikin"] = (np.r_[False, False, green[2:] & green[1:-1] & nowick[2:] & ~green[:-2]], ~green)
    # rolling VWAP(24)
    vw = S(tp * v).rolling(24).sum().to_numpy() / S(v).rolling(24).sum().to_numpy()
    ab = c > vw
    out["vwap"] = (np.r_[False, ab[1:] & ~ab[:-1]], ~ab)
    # Bollinger(30, 1.5) break - the deployed entry
    m30, s30 = S(c).rolling(30).mean().to_numpy(), S(c).rolling(30).std(ddof=0).to_numpy()
    out["bb"] = (c > m30 + 1.5 * s30, c < m30)
    return out


def own_exit(i, ex_sig, P, fc, cap):
    o, c, l = P["o"], P["c"], P["l"]
    n = len(c)
    j_end = min(i + 1 + cap, n - 2)
    seg = ex_sig[i + 1:j_end + 1]
    e = o[i + 1]
    worst = float(np.max(1 - l[i + 1:j_end + 1] / e))
    if seg.any():
        j = i + 1 + int(np.argmax(seg))
        return j + 1, o[j + 1] / e - 1 - FEE - (fc[j + 1] - fc[i + 1]) / e, worst
    return j_end, c[j_end] / e - 1 - FEE - (fc[j_end] - fc[i + 1]) / e, worst


def main():
    t0 = time.time()
    el = eligibility(40)
    H = {s: hourly(s) for s in sorted(s for s, m in el.items() if m)}
    H = {s: h for s, h in H.items() if h is not None}
    rows = []
    for tf, off in GRIDS:
        cap = 30 * (6 if tf == "4h" else 1)
        for s, h in H.items():
            d = bars(h, tf, off)
            if len(d) < 120:
                continue
            P = prep(d, np.full(len(d), np.nan))
            fc = funding_cum(s, d.time.to_numpy(), h)
            ym = d.time.dt.strftime("%Y-%m").to_numpy()
            t = d.time.to_numpy()
            ind = indicators(P)
            for nm, (ent, exs) in ind.items():
                ent = np.nan_to_num(ent).astype(bool)
                exs = np.nan_to_num(exs).astype(bool)
                for ex in ("trail5", "own"):
                    free = 0
                    for i in np.flatnonzero(ent):
                        if i < 60 or i < free or i + 3 >= len(t) or ym[i] not in el[s]:
                            continue
                        if ex == "trail5":
                            j, net, worst, _ = exit_trail(i, 1, 5.0, P, fc, s0=2.0, be=3.0, cap=cap * 4)
                        else:
                            j, net, worst = own_exit(i, exs, P, fc, cap)
                        rows.append((tf, off, nm, ex, s, t[i + 1], net, worst))
                        free = j + 1
        print(f"  {tf} +{off} done ({time.time() - t0:.0f}s)", flush=True)
    A = pd.DataFrame(rows, columns=["tf", "off", "ind", "exit", "coin", "t", "net", "worst"])
    A["t"] = pd.to_datetime(A.t)
    A.to_csv(ROOT / "logs" / "tv_indicators_trades.csv.gz", index=False, compression="gzip")
    lines = [f"backtest/tv_indicators.py, {pd.Timestamp.now():%Y-%m-%d %H:%M}; PIT top-40, long entries; per grid: n, win, "
             f"avg/trade (tune / holdout), t by day; 'vs bb' = avg minus the bb baseline on the same grid and exit", ""]
    for ex in ("trail5", "own"):
        lines.append(f"EXIT {ex}")
        beats = {}
        for nm in NAMES:
            cells = []
            for tf, off in GRIDS:
                g = A[(A.tf == tf) & (A.off == off) & (A.ind == nm) & (A.exit == ex)]
                b = A[(A.tf == tf) & (A.off == off) & (A.ind == "bb") & (A.exit == ex)]
                if len(g) < 30:
                    cells.append(f"{tf}+{off}: n<30")
                    continue
                pdm = g.groupby(g.t.dt.floor("D")).net.mean()
                td = pdm.mean() / (pdm.std(ddof=1) / np.sqrt(len(pdm)))
                tu, ho = g[g.t < HOLDOUT].net.mean(), g[g.t >= HOLDOUT].net.mean()
                btu, bho = b[b.t < HOLDOUT].net.mean(), b[b.t >= HOLDOUT].net.mean()
                if tf == "4h" and nm != "bb":
                    beats[nm] = beats.get(nm, 0) + int(tu > btu and ho > bho)
                cells.append(f"{tf}+{off}: {len(g)} {np.mean(g.net > 0):.0%} {g.net.mean() * 100:+.2f}% "
                             f"({tu * 100:+.2f}/{ho * 100:+.2f}) t {td:+.1f}")
            lines.append(f"  {nm:10} " + " | ".join(cells))
        lines.append("  4h phases (of 4) where the indicator beats bb on BOTH halves: "
                     + ", ".join(f"{k} {v}" for k, v in sorted(beats.items(), key=lambda x: -x[1])))
        lines.append("")
    txt = "\n".join(lines)
    print(txt)
    LOG.write_text(txt + "\n")
    print(f"-> {LOG} ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
