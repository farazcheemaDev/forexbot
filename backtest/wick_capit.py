"""CRASH BIDS x TODAY'S CAPITULATION SIGNALS - the combinations not yet run (2026-10-08).

The deployed crash-bid rule (wick_better.py --combos, doc 16): a resting buy 10% under the previous hour's close on the
PIT top-40, 1/40 of equity each, none on BEAR days, sold at the fill hour's close; 8bp + 30bp exit slippage, $5 minimum,
$300. Its combinations were all run on its own features (prior 24h, repeats, distance, ladder, size). Never combined
with what today found in the capitulation book (capit_combos.py): the BREADTH count (distinct top-40 coins whose 4h
RSI(14) crossed under 20 with volume > 2x in the past 24 hours, phase 0, known at the hour) and BTC's own 24h drop.

    K>=5 only    bid only while >= 5 coins have capitulated in the past 24h (a confirmed market-wide panic)
    K>=5 skip    the opposite: no bids while >= 5 have (avoid joining a cascade)
    BTC-5 only   bid only while BTC is down >= 5% over the past 24h;   BTC-5 skip   the opposite
    K>=1 skip    no bids while ANY coin has capitulated in the past 24h
Judged as wick_better.py judges: growth minus what the baseline makes when simply sized to the same worst month, on
BOTH halves (tune < 2024-08-29 <= holdout). PASS = positive on both.

REGISTERED BEFORE RUNNING: the bids are already a crash book, so "only in a panic" cuts fills by 80-95% and fails
(too few, and the worst fills are in panics - 2025-10-10); "skip in a panic" improves the worst month and passes on
at least one of K>=5 skip / BTC-5 skip; K>=1 skip fails (it removes most fills).

RESULT (2026-10-08, logs/wick_capit.txt): all 5 fail. Only-in-a-panic: 31 / 108 fills a year, below the line;
    skip-in-a-panic: no better than smaller bids. Predictions: only-in-panic fails - right; a skip passes - WRONG;
    K>=1 skip fails - right.

    python -m backtest.wick_capit

RE-RUN 2026-10-09 on the FIXED loader (capitulation_wide.halt_cut): until then a data-archive hole cut 51 coins (XRP, SOL,
    LTC ...) at 2022-02-25. Where a RESULT above differs from this file's log, THE LOG IS CURRENT - doc 02, "The archive-hole bug".
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest import capit_combos as cc  # noqa: E402
from backtest import pair_lab as pl  # noqa: E402
from backtest import wick_better as wb  # noqa: E402

LOG = ROOT / "logs" / "wick_capit.txt"


def k_at(times, S, kmin_hours=24):
    """Distinct coins with a capitulation signal KNOWN (bar label + 4h) in (t - 24h, t]."""
    known = (pd.DatetimeIndex(S.t) + pd.Timedelta(hours=4)).as_unit("ns").asi8
    order = np.argsort(known, kind="stable")
    kn, coins = known[order], S.coin.to_numpy()[order]
    out = np.zeros(len(times), int)
    tv = pd.DatetimeIndex(times).as_unit("ns").asi8
    lo_i = np.searchsorted(kn, tv - kmin_hours * 3600 * 10 ** 9, side="right")
    hi_i = np.searchsorted(kn, tv, side="right")
    for q, (a, b) in enumerate(zip(lo_i, hi_i)):
        if b > a:
            out[q] = len(set(coins[a:b]))
    return out


def main():
    X, _, bear_day = wb.load_all()
    X40 = X[X.in40]
    base = wb.fills(X40, skip_bear=bear_day)
    S = cc.signals(0)
    base = base.assign(K=k_at(base.t, S))
    b = pl.hourly_all()["BTCUSDT"]
    bc = pd.Series(b.close.to_numpy(), index=pd.DatetimeIndex(b.time)).sort_index()
    # known at the bid's hour t: the close of hour t-1 against the close of hour t-25
    btc24 = (bc.shift(1) / bc.shift(25) - 1)
    base["btc24"] = btc24.reindex(pd.DatetimeIndex(base.t)).to_numpy()
    fr = {m: wb.stats(wb.book(base, 40, m)[0]) for m in (0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0)}

    def vs(s, half, wk):
        pts = sorted((fr[m][wk], fr[m][half]) for m in fr)
        return s[half] - float(np.interp(s[wk], [p[0] for p in pts], [p[1] for p in pts]))

    yrs = (pd.Timestamp("2026-09-21") - pd.Timestamp("2020-01-01")).days / 365.25
    lines = [f"backtest/wick_capit.py, {pd.Timestamp.now():%Y-%m-%d %H:%M}; base = top-40, 10% under, skip BEAR days, $300",
             f"  {'rule':24}{'fills/yr':>9}{'TUNE':>8}{'worst mo':>9}{'HOLD':>8}{'worst mo':>9}{'DD':>5} | vs smaller tune / hold"]
    rules = {"base (deployed rule)": base, "K>=5 only": base[base.K >= 5], "K>=5 skip": base[base.K < 5],
             "BTC-5 only": base[base.btc24 <= -0.05], "BTC-5 skip": base[~(base.btc24 <= -0.05)], "K>=1 skip": base[base.K < 1]}
    for nm, Y in rules.items():
        s = wb.stats(wb.book(Y, 40)[0])
        a, c = vs(s, "tune", "wm_t"), vs(s, "hold", "wm_h")
        lines.append(f"  {nm:24}{len(Y) / yrs:>9.0f}{s['tune']:>+7.1f}%{s['wm_t']:>+8.1f}%{s['hold']:>+7.1f}%{s['wm_h']:>+8.1f}%"
                     f"{s['dd']:>4.0f}% | {a:+6.1f} / {c:+6.1f}  {'-' if nm.startswith('base') else ('PASS' if a > 0 and c > 0 else 'fail')}")
        print(lines[-1], flush=True)
    LOG.write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
