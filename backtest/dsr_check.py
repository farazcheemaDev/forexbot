"""THE DEFLATED SHARPE RATIO OF THE 9-BOOK MACHINE - how much of the backtest survives the number of ideas tried

Bailey & Lopez de Prado (2014, Journal of Portfolio Management): a Sharpe ratio found after N trials must beat the
EXPECTED MAXIMUM Sharpe of N skill-less trials, adjusted for skew and fat tails:
    SR0 = sqrt(V) * ((1 - g) * z(1 - 1/N) + g * z(1 - 1/(N e)))        g = 0.5772 (Euler-Mascheroni), z = inverse normal
    DSR = Phi( (SR - SR0) * sqrt(T - 1) / sqrt(1 - skew * SR + (kurt - 1) / 4 * SR^2) )
SR per day, T days, kurt the plain (not excess) kurtosis. V, the variance of the trials' Sharpe ratios, is not on record
here; under the null each daily Sharpe estimate has variance ~1 / T, used as V (the textbook stand-in - real trials are
correlated, which makes the true N smaller and this harsher than needed; their spread can also be wider, which makes it
milder). This repository has tested thousands of variants (doc 02, doc 21), so N is read at 10 / 100 / 1,000 / 10,000.
DSR is the probability the true Sharpe is above zero once selection is paid for: 0.95+ = significant.

REGISTERED BEFORE THE RUN (2026-10-20)
    Z1 at N = 1,000 the machine's DSR is below 0.95 on the holdout half (the backtest alone cannot carry the claim).
    Z2 on the full 2020-26 series at N = 100 it is above 0.95 (six years of a strong Sharpe survives a modest search).

RESULT (2026-10-20, logs/dsr_check.txt) - Z1 / Z2 RIGHT. Sharpe 1.72 a year (full / tune / holdout alike); daily returns are
    extremely skewed (skew ~20, kurtosis ~500 - the trend book books whole trades at their close). DSR, full 2020-26:
    1.00 / 1.00 / 0.99 / 0.85 at N = 10 / 100 / 1,000 / 10,000; tune 1.00 / 0.99 / 0.79 / 0.34; HOLDOUT 0.98 / 0.44 /
    0.03 / 0.00. Six years survive a search of ~1,000 ideas; the last two years alone prove nothing past ~10 ideas - the
    formal reason the forward paper record decides (doc 22).

    python -m backtest.dsr_check
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import kurtosis, norm, skew

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

LOG = ROOT / "logs" / "dsr_check.txt"
G = 0.5772156649


def dsr(r: np.ndarray, n_trials: int) -> tuple:
    T = len(r)
    sr = r.mean() / r.std(ddof=1)
    sk, ku = skew(r), kurtosis(r, fisher=False)
    v = 1.0 / T
    sr0 = np.sqrt(v) * ((1 - G) * norm.ppf(1 - 1 / n_trials) + G * norm.ppf(1 - 1 / (n_trials * np.e)))
    z = (sr - sr0) * np.sqrt(T - 1) / np.sqrt(max(1 - sk * sr + (ku - 1) / 4 * sr ** 2, 1e-12))
    return float(norm.cdf(z)), sr * np.sqrt(365), sr0 * np.sqrt(365), sk, ku


def main():
    from backtest.all_books import BOOKS, machine_books, ndx_dip, news_book
    from backtest.machine import CUT
    M = machine_books()
    nw, nd = news_book(), ndx_dip()
    RUN = [b for b in BOOKS if b != "bids"]
    lines = [f"backtest/dsr_check.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; the 9-book machine's daily returns "
             f"(no crash bids), median over 10 orderings; V = 1/T", "",
             f"   {'span':<10}{'days':>6}{'Sharpe/yr':>10}{'skew':>7}{'kurt':>7}" + "".join(f"{'N=' + str(n):>16}" for n in (10, 100, 1000, 10000)),
             f"   {'':<40}" + "".join(f"{'(bar / DSR)':>16}" for _ in range(4))]
    out = {}
    for span in ("full", "tune", "holdout"):
        rows = []
        for x in M:
            r = x[RUN].sum(axis=1) + nw.reindex(x.index).fillna(0.0) + nd.reindex(x.index).fillna(0.0)
            r = r[r.index >= r.ne(0).idxmax()]
            r = r if span == "full" else (r[r.index < CUT] if span == "tune" else r[r.index >= CUT])
            rows.append([dsr(r.to_numpy(), n) for n in (10, 100, 1000, 10000)] + [len(r)])
        med = lambda k, j: float(np.median([rw[k][j] for rw in rows]))  # noqa: E731
        out[span] = {n: med(i, 0) for i, n in enumerate((10, 100, 1000, 10000))}
        lines.append(f"   {span:<10}{int(np.median([rw[-1] for rw in rows])):>6}{med(0, 1):>10.2f}{med(0, 3):>7.2f}{med(0, 4):>7.1f}"
                     + "".join(f"{med(i, 2):>9.2f} / {med(i, 0):.2f}" for i in range(4)))
    z1 = out["holdout"][1000] < 0.95
    z2 = out["full"][100] > 0.95
    lines += ["", "   bar = the Sharpe a year the best of N skill-less trials would show by luck alone; DSR = the probability the",
              "   true Sharpe is above zero after paying for the search (0.95+ = significant)", "",
              "REGISTERED PREDICTIONS",
              f"  Z1 holdout DSR at N = 1,000 below 0.95: {out['holdout'][1000]:.2f} -> {'RIGHT' if z1 else 'WRONG'}",
              f"  Z2 full-span DSR at N = 100 above 0.95: {out['full'][100]:.2f} -> {'RIGHT' if z2 else 'WRONG'}"]
    txt = "\n".join(lines)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
