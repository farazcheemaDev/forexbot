"""POST-HOC CHECK OF THE INDICATOR MODEL'S SURPRISINGLY LARGE IC (2026-11-02)

backtest/indicator_model.py (logs/indicator_model.txt): no primary cell passed Holm, but my predictions P2, P4 and P5 were wrong - the
out-of-sample daily rank correlations were +0.10 .. +0.18 (t 5-14), not under +0.04, and the best SINGLE feature was ATR% in 17-19 of 19
quarterly fits. An IC of +0.09 for a plain volatility measure is the kind of number this repo treats as a bug until shown otherwise.
The repo has been here before: cross-sectional short-term reversal "came from the close print itself" (doc 02: ranked at the close,
the gain vanished once ranked a day earlier). The model enters at the NEXT DAY'S 00:00 OPEN, which is the last day's closing print; a
coin that dumped in the final minutes of the day shows a gain at that print that nobody could trade a minute later.

THE CHECK: the predictions are re-made exactly as in indicator_model.py (single feature and ridge; gradient boosting is skipped, it is
the slow one) and scored four ways -
    entry at 00:00 (the official run), at 01:00, at 04:00 UTC of the next day, and at 00:00 of the day AFTER (skip a day).
If the edge is a closing-print artifact it should be mostly gone after one hour; if it is a real daily tilt it should shrink slowly.
Also: the IC by calendar year, and the IC of ATR% against the SAME day's return (what the feature mechanically correlates with).

REGISTERED BEFORE THIS RUN (after seeing the main result; my reading is that part of it is the capitulation bounce and part the print)
  C1  The IC at H = 1 falls by more than half when entry moves from 00:00 to 01:00.
  C2  At H = 7 the IC is not much affected by a one-hour delay (the print matters for the first day only): it keeps at least 70%.
  C3  The IC of the single feature is positive in every calendar year 2022-2026.

    python -m backtest.indicator_model_check
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest import candle_scan as cs  # noqa: E402
from backtest import indicator_model as im  # noqa: E402

LOG = ROOT / "logs" / "indicator_model_check.txt"
DELAYS = (("00:00 (official)", None), ("01:00", 1), ("04:00", 4), ("next day 00:00", "day"))


def late_opens(coins, T):
    """Open of the 01:00 and 04:00 UTC hourly bars of every day, (days x coins) each."""
    from backtest.capitulation_wide import hourly
    O1, O4 = np.full((T, len(coins)), np.nan), np.full((T, len(coins)), np.nan)
    for j, sym in enumerate(coins):
        h = hourly(sym)
        if h is None:
            continue
        t = h["time"].to_numpy("datetime64[ns]")
        day = (t.astype("datetime64[D]") - im.D0).astype(int)
        hr = ((t - t.astype("datetime64[D]").astype("datetime64[ns]")) / np.timedelta64(1, "h")).astype(int)
        for arr, hh in ((O1, 1), (O4, 4)):
            m = (hr == hh) & (day >= 0) & (day < T)
            arr[day[m], j] = h["open"].to_numpy(float)[m]
    return O1, O4


def forward_from(open_next, C, H, shift=0):
    """F[t] = close(t + H + shift) / open_next[t + 1 + shift] - 1: enter at the given open on day t+1 (+shift days), leave at the close
    that completes the same holding length. A coin whose history ends inside the window is left at its last close."""
    T, N = C.shape
    Cf = C.copy()
    for j in range(N):
        fin = np.flatnonzero(np.isfinite(C[:, j]))
        if len(fin):
            Cf[fin[-1] + 1:, j] = C[fin[-1], j]
    F = np.full((T, N), np.nan)
    if T > H + shift + 1:
        with np.errstate(invalid="ignore", divide="ignore"):
            F[:T - H - shift] = Cf[H + shift:] / open_next[1 + shift:T - H + 1] - 1
    return F


def main():
    dates, coins, O, Hh, L, C, V, M = im.build_panel()
    T = len(dates)
    btc = coins.index("BTCUSDT")
    feats = im.feature_panels(O, Hh, L, C, V, btc)
    ranked = np.stack([np.nan_to_num(im.xs_rank(feats[k], M), nan=0.0) for k in im.FEATURES], axis=-1).astype(np.float32)
    nfin = sum(np.isfinite(feats[k]).astype(np.int16) for k in im.FEATURES)
    mem = M & (nfin >= im.MIN_FEATS) & np.isfinite(O) & np.isfinite(C)
    blocks = im.make_blocks(dates)
    O1, O4 = late_opens(coins, T)
    L_ = [f"backtest/indicator_model_check.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; POST-HOC check of indicator_model.py; same predictions, different entry times", ""]
    rows = {}
    atr_rank = ranked[:, :, im.FEATURES.index("atr_pct")]
    for H in im.HORIZONS:
        Fo = im.forward_returns(O, C, H)
        Y = im.xs_rank(Fo, mem & np.isfinite(Fo))
        preds = {m: im.walk_forward(ranked, Y, mem, blocks, H, m)[0] for m in ("single", "ridge")}
        variants = {}
        for name, mode in DELAYS:
            if mode is None:
                F = Fo
            elif mode == "day":
                F = forward_from(O, C, H, shift=1)
            else:
                F = forward_from(O1 if mode == 1 else O4, C, H)
            variants[name] = F
        for m in ("single", "ridge"):
            for name, _ in DELAYS:
                c = im.cell(dates, preds[m], variants[name], mem, H)
                rows[(H, m, name)] = c
                tu, ho = c["tu"], c["ho"]
                L_.append(f"H={H} {m:<6} entry {name:<17} IC {tu['ic']['mean']:+.3f} ({tu['ic']['t']:+.1f}) / {ho['ic']['mean']:+.3f} ({ho['ic']['t']:+.1f})   "
                          f"gross spread {tu['gross']['mean'] * 1e4:+6.1f} / {ho['gross']['mean'] * 1e4:+6.1f}bp   NET {tu['net']['mean'] * 1e4:+6.1f} / {ho['net']['mean'] * 1e4:+6.1f}bp   "
                          f"LONG-ONLY top fifth minus the universe, net: {tu['lexc']['mean'] * 1e4:+6.1f}bp ({tu['lexc']['t']:+.1f}) / {ho['lexc']['mean'] * 1e4:+6.1f}bp ({ho['lexc']['t']:+.1f})")
            L_.append("")
        if H == 1:
            ic, _, _, _ = im.day_scores(preds["single"], Fo, mem)
            yrs = dates.astype("datetime64[Y]").astype(int) + 1970
            L_.append("single-feature IC by calendar year (H=1, official entry): " + "  ".join(
                f"{y}: {np.nanmean(ic[(yrs == y)]):+.3f}" for y in range(2022, 2027) if np.isfinite(ic[yrs == y]).any()))
            same = np.where(np.isfinite(O) & np.isfinite(C), C / O - 1, np.nan)
            ic_same, _, _, _ = im.day_scores(atr_rank.astype(np.float32), same, mem)
            L_.append(f"ATR% rank vs the SAME day's open-to-close return (not tradable, mechanical): IC {np.nanmean(ic_same):+.3f}")
            ic_atr, _, _, _ = im.day_scores(atr_rank.astype(np.float32), Fo, mem)
            L_.append(f"ATR% rank vs the next day's return (the single feature, all days): IC {np.nanmean(ic_atr):+.3f}")
            L_.append("  -> the single feature is used with the OPPOSITE sign: LOW-ATR% coins outperform (the model's IC is +0.09 because it predicts -ATR%)")
            L_.append("")
    c1 = all(rows[(1, m, "01:00")][h]["ic"]["mean"] < 0.5 * rows[(1, m, "00:00 (official)")][h]["ic"]["mean"] for m in ("single", "ridge") for h in ("tu", "ho"))
    c2 = all(rows[(7, m, "01:00")][h]["ic"]["mean"] >= 0.7 * rows[(7, m, "00:00 (official)")][h]["ic"]["mean"] for m in ("single", "ridge") for h in ("tu", "ho"))
    L_ += ["REGISTERED (post-hoc)",
           f"  C1 H=1 IC falls by more than half with a one-hour delay -> {'RIGHT' if c1 else 'WRONG'}",
           f"  C2 H=7 IC keeps >= 70% with a one-hour delay -> {'RIGHT' if c2 else 'WRONG'}"]
    txt = "\n".join(L_)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
