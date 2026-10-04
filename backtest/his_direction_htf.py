"""DOES HE TAKE DIRECTION FROM THE HIGHER TIMEFRAME? - his side against the 1-hour .. 20-day trend.

WHY (the user, 2026-10-04: "how does a person with 20 years of forex experience decide entry")
    The textbook discretionary method is multi-timeframe: direction from the higher-timeframe trend (H1 / H4 / D1),
    timing from a pullback on M1 / M5. s36 tested fade-vs-follow only out to 30 minutes and found nothing (44-59%,
    best rule at his moments 57% against his 88%). Never tested: hours to weeks.

WHAT IS MEASURED (MT5 USTECm 5-minute bars, labels UTC - mt5_clock_anchor.py; his times at the corrected clock)
    1. Agreement: sign(price now - price H ago), signed by his side, for H = 1 h, 2 h, 4 h, 8 h, 1, 3, 5, 10, 20 days;
       and price against its EMA-50 / EMA-200 on 1-hour bars (the classic trend filter).
    2. At HIS moments, give the side to the higher-timeframe rule and run the +-7 mid race (tick cache, 600 s): if one
       rule wins near his 88%, his DIRECTION is that rule and only his timing is left to explain.

REGISTERED PREDICTIONS (2026-10-04, before running)
    1. He agrees with the 4-hour or daily trend more than with the minutes (55-70%), but under 80% at every horizon -
       a veteran leans with the bigger trend, not always.
    2. At his moments the best higher-timeframe rule wins the race under 70%; his 88% is not a trend filter.

    python -m backtest.his_direction_htf
"""
from __future__ import annotations

import json
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.his_race_curve import race2  # noqa: E402
from backtest.his_tape import entries  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
BARS = ROOT / "strategy_analysis" / "data" / "USTECm_5m_400d.json"
TICKS = ROOT / "strategy_analysis" / "data" / "ustec_tick_days.pkl"
H = {"1h": 12, "2h": 24, "4h": 48, "8h": 96, "1d": 288, "3d": 864, "5d": 1440, "10d": 2880, "20d": 5760}


def main():
    from scipy.stats import binomtest
    b = pd.DataFrame(json.load(open(BARS)))
    b["t"] = pd.to_datetime(b["t"], unit="ms")
    c = b.set_index("t")["c"].astype(float).sort_index()
    h1 = c.resample("1h").last().dropna()
    ema50, ema200 = h1.ewm(span=50, adjust=False).mean(), h1.ewm(span=200, adjust=False).mean()
    x = entries()
    ticks = pickle.loads(TICKS.read_bytes())
    rows = []
    for r in x.itertuples():
        k = c.index.searchsorted(r.utc, side="right") - 1             # last completed 5-min bar label <= his click
        if k < 5760:
            continue
        now = c.iat[k]
        row = dict(s=r.s)
        for lab, n in H.items():
            row[lab] = np.sign(now - c.iat[k - n])
        j = h1.index.searchsorted(r.utc, side="right") - 2            # last COMPLETED hour
        row["ema50"] = np.sign(h1.iat[j] - ema50.iat[j])
        row["ema200"] = np.sign(h1.iat[j] - ema200.iat[j])
        day = ticks.get(r.d)
        if day is not None:
            ts, mid, _ = day
            row["his"] = race2(ts, mid, r.t, r.s, 600, 7, 7)
            for lab in list(H) + ["ema50", "ema200"]:
                sd = int(row[lab])
                row["race_" + lab] = race2(ts, mid, r.t, sd, 600, 7, 7) if sd else None
        rows.append(row)
    D = pd.DataFrame(rows)
    out = [f"{len(D)} NASDAQ entries with 20 days of 5-minute history; his own +-7 race "
           f"{pd.to_numeric(D.his, errors='coerce').mean():.0%}",
           f"\n  {'trend':>7}{'he agrees':>11}{'p':>8}{'race if side = trend':>23}"]
    for lab in list(H) + ["ema50", "ema200"]:
        v = (D[lab] * D.s)
        v = v[v != 0]
        p = binomtest(int((v > 0).sum()), len(v), 0.5).pvalue
        rc = pd.to_numeric(D["race_" + lab], errors="coerce").mean()
        out.append(f"  {lab:>7}{(v > 0).mean():>10.0%}{p:>8.3f}{rc:>22.0%}")
    txt = "\n".join(out)
    print(txt)
    (ROOT / "logs" / "his_direction_htf.txt").write_text(txt, encoding="utf-8")


if __name__ == "__main__":
    main()
