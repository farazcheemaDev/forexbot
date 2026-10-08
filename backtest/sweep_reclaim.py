"""PHASE 2 (the thin kills): the "liquidity sweep" and "fade the prior day's high/low" reversals (2026-10-08).

THE KILLS (doc 02's first table, "tried to predict reversals", 2026-09-14 era): "Liquidity-sweep / stop-hunt reversal
(ICT style): PF 0.53-0.79" and "Level-fade at round numbers and prior-day highs/lows: PF ~1.0, not robust". Backing: one
line each, measured before every engine fix, universe and timeframe not recorded, no control. Re-tested here properly:
    SWEEP LONG   an hour trades BELOW the prior UTC day's low and closes back ABOVE it (the stop run is reclaimed); in
                 at the next open; stop at that hour's low (intrabar, checked first), target +2% (intrabar), else out at
                 the close 24 hours later. First signal per coin per day.
    SWEEP SHORT  the mirror at the prior day's high (stop at the sweep high, target -2%).
On the PIT top-40 (dead coins in), hourly bars, 12bp + funding. CONTROL: for every signal, a random hour of the same coin
in the same month with the SAME stop distance and the same exits. Excess = signal minus its control, t by distinct day
(trades on one day share one market). Halves split 2024-04-07. PASS: excess > 0 with t > 2 on BOTH halves.

REGISTERED BEFORE RUNNING: the sweep long's excess is within +-0.15% a trade and fails on at least one half; the short
loses to its control (crypto's upward drift and squeezes). Both kills stand.

RESULT (2026-10-08, logs/sweep_reclaim.txt): the signal carries information - long excess over its control +0.12%
    (t +6.4) / +0.06% (t +4.0), short +0.08% (t +4.5) / +0.03% (t +2.8) - but the TRADE LOSES after 12bp: long -0.09%
    / -0.13% a trade, short -0.04% / -0.09% (the controls lose more). At maker fees it is about zero. THE KILL STANDS
    AS A TRADE; the old "PF ~1, not robust" was the right verdict, now with a sample (30,000 longs, 30,000 shorts, PIT).
    Caveat: the control matches the stop distance, not the hour's volatility. Predictions: long excess within +-0.15 -
    right; fails a half - WRONG; short loses to its control - WRONG.

    python -m backtest.sweep_reclaim
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest import pair_lab as pl  # noqa: E402
from backtest.capitulation_wide import funding_cum  # noqa: E402

LOG = ROOT / "logs" / "sweep_reclaim.txt"
HOLDOUT = pl.HOLDOUT
FEE = 0.0012
TP, HOLD = 0.02, 24


def trade(i, side, stop, o, h, l, c, fc):
    """In at o[i+1]; stop (intrabar, first), target (intrabar), else the close HOLD bars later."""
    n = len(c)
    e = o[i + 1]
    if side > 0 and stop >= e or side < 0 and stop <= e:
        return None                                   # the open gapped through the stop: no trade
    j_end = min(i + HOLD, n - 1)
    for j in range(i + 1, j_end + 1):
        if (l[j] <= stop) if side > 0 else (h[j] >= stop):
            x = min(o[j], stop) if side > 0 else max(o[j], stop)
            return side * (x / e - 1) - FEE - side * (fc[j] - fc[i + 1]) / e
        if (h[j] >= e * (1 + TP)) if side > 0 else (l[j] <= e * (1 - TP)):
            return TP - FEE - side * (fc[j] - fc[i + 1]) / e
    return side * (c[j_end] / e - 1) - FEE - side * (fc[j_end] - fc[i + 1]) / e


def main():
    rng = np.random.default_rng(0)
    rows = []
    for s, hh in pl.hourly_all().items():
        t = hh.time.to_numpy("datetime64[ns]")
        o, h, l, c = (hh[k].to_numpy(float) for k in ("open", "high", "low", "close"))
        fc = funding_cum(s, hh.time.to_numpy(), hh)
        day = pd.DatetimeIndex(t).floor("D")
        dlow = pd.Series(l, index=t).groupby(day).min()
        dhigh = pd.Series(h, index=t).groupby(day).max()
        pdl = dlow.shift(1).reindex(day).to_numpy()
        pdh = dhigh.shift(1).reindex(day).to_numpy()
        ym = pd.DatetimeIndex(t).strftime("%Y-%m").to_numpy()
        el = pl.universe()[s]
        by_month = pd.Series(np.arange(len(t))).groupby(ym).apply(lambda x: x.to_numpy())
        for side, sig, lvl in ((1, (l < pdl) & (c > pdl), l), (-1, (h > pdh) & (c < pdh), h)):
            seen = set()
            for i in np.flatnonzero(sig):
                if i < 48 or i + HOLD + 2 >= len(c) or ym[i] not in el or (day[i], side) in seen:
                    continue
                seen.add((day[i], side))
                stop = lvl[i]
                r = trade(i, side, stop, o, h, l, c, fc)
                if r is None:
                    continue
                dist = abs(stop / c[i] - 1)
                pool = by_month[ym[i]]
                pool = pool[(pool > 48) & (pool + HOLD + 2 < len(c))]
                k = int(rng.choice(pool))
                rc = trade(k, side, c[k] * (1 - side * dist), o, h, l, c, fc)
                if rc is None:
                    continue
                rows.append((s, t[i + 1], side, r, rc))
    T = pd.DataFrame(rows, columns=["coin", "t_in", "side", "net", "ctrl"])
    T["ex"] = T.net - T.ctrl
    T["day"] = pd.DatetimeIndex(T.t_in).floor("D")
    lines = [f"backtest/sweep_reclaim.py, {pd.Timestamp.now():%Y-%m-%d %H:%M}; PIT top-40 hourly, prior UTC day's low/high, "
             f"+-2% target, stop at the sweep, 24h; control = same coin-month, same stop distance"]
    for side, nm in ((1, "SWEEP LONG (reclaim the prior day's low)"), (-1, "SWEEP SHORT (reject the prior day's high)")):
        g = T[T.side == side]
        cells, ok = [], True
        for half, x in (("tune", g[g.t_in < HOLDOUT]), ("holdout", g[g.t_in >= HOLDOUT])):
            d = x.groupby("day").ex.mean()
            tt = d.mean() / d.std(ddof=1) * np.sqrt(len(d)) if len(d) > 2 else np.nan
            ok = ok and d.mean() > 0 and tt > 2
            cells.append(f"{half}: n {len(x)}, signal {x.net.mean() * 100:+.2f}% vs control {x.ctrl.mean() * 100:+.2f}%, excess "
                         f"{x.ex.mean() * 100:+.2f}% (t by day {tt:+.1f})")
        lines.append(f"  {nm}")
        lines += [f"    {cc}" for cc in cells]
        lines.append(f"    -> {'PASS' if ok else 'dead'}")
    txt = "\n".join(lines)
    print(txt)
    LOG.write_text(txt + "\n")


if __name__ == "__main__":
    main()
