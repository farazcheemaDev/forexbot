"""THE DAILY BOLLINGER BOOK AT 6 DAY BOUNDARIES - the bar-phase check before believing pair_books.py (2026-10-08).

pair_books.py's daily book (close above Bollinger(30, 1.5) on DAILY bars, out after a close under the 30-day mean,
point-in-time top-40) was picked from tv_indicators.py's table after looking. The check that has killed findings here
before: the same book on daily bars that start at 00 / 04 / 08 / 12 / 16 / 20 UTC.

REGISTERED BEFORE RUNNING: positive on both halves at all 6 boundaries; 1x 8-slot CAGR within +-30% of the 00:00 one.

RESULT (2026-10-08, logs/daily_phase.txt): day starts 00/04/08/12/16/20 UTC -> +7.35 / +6.80 / +7.13 / +6.71 / +7.40 /
    +7.34% a trade, holdout +2.04 / +2.41 / +2.07 / +1.13 / +2.06 / +2.07%, t by day +2.9..+3.4, 1x 8-slot +69..+90%/yr,
    falls 48-63%. Prediction (positive everywhere, CAGR within +-30%): right.

    python -m backtest.daily_phase

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

from backtest.capitulation_wide import funding_cum, hourly  # noqa: E402
from backtest.pair_books import curve, stats  # noqa: E402
from backtest.rsi_factors import prep  # noqa: E402
from backtest.tv_indicators import bars, indicators, own_exit  # noqa: E402
from backtest.wide_book import eligibility  # noqa: E402

LOG = ROOT / "logs" / "daily_phase.txt"
HOLDOUT = pd.Timestamp("2024-04-07")


def main():
    el = eligibility(40)
    H = {s: hourly(s) for s in sorted(k for k, m in el.items() if m)}
    H = {s: h for s, h in H.items() if h is not None}
    lines = [f"backtest/daily_phase.py, {pd.Timestamp.now():%Y-%m-%d %H:%M}; daily bb own-exit book, PIT top-40", ""]
    for off_h in (0, 4, 8, 12, 16, 20):
        rows = []
        for s, h in H.items():
            d = bars(h, "1d", off_h * 60)
            if len(d) < 120:
                continue
            P = prep(d, np.full(len(d), np.nan))
            fc = funding_cum(s, d.time.to_numpy(), h)
            ent, exs = indicators(P)["bb"]
            ym, t = d.time.dt.strftime("%Y-%m").to_numpy(), d.time.to_numpy()
            exs = np.nan_to_num(exs).astype(bool)
            free = 0
            for i in np.flatnonzero(np.nan_to_num(ent).astype(bool)):
                if i < 60 or i < free or i + 3 >= len(t) or ym[i] not in el[s]:
                    continue
                j, net, worst = own_exit(i, exs, P, fc, 30)
                rows.append((s, t[i + 1], t[min(j, len(t) - 1)], net, worst))
                free = j + 1
        D = pd.DataFrame(rows, columns=["coin", "t_in", "t_out", "net", "worst"])
        D["t_in"], D["t_out"] = pd.to_datetime(D.t_in), pd.to_datetime(D.t_out)
        cagr, dd, up, wm, _ = stats(curve(D, 1, 8))
        tu, ho = D[D.t_in < HOLDOUT].net.mean(), D[D.t_in >= HOLDOUT].net.mean()
        pdm = D.groupby(D.t_in.dt.floor("D")).net.mean()
        td = pdm.mean() / (pdm.std(ddof=1) / np.sqrt(len(pdm)))
        lines.append(f"  day starts {off_h:02d}:00 UTC: {len(D)} trades, avg {D.net.mean() * 100:+.2f}% (tune {tu * 100:+.2f} / holdout "
                     f"{ho * 100:+.2f}), t by day {td:+.1f}; 10,000 PKR 8 slots 1x: {cagr * 100:+.0f}%/yr, worst fall {dd:.0%}, "
                     f"months up {up:.0%}")
    txt = "\n".join(lines)
    print(txt)
    LOG.write_text(txt + "\n")


if __name__ == "__main__":
    main()
