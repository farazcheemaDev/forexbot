"""HIS OWN CHART - CapitalFX's NASDAQ Dec 1-minute candles (VertexFX app) against the real market (2026-10-12)

WHY      his_strategy s45: he reads his broker's chart, not the exchange's, and no test had seen it. The user has the app
         (VertexFX Trader Pro, Hybrid Solutions - not MetaTrader, so no tick export) and screenshotted the 1-minute chart
         of NASDAQ Dec around his two 2026-10-08 trades. The app's clock is UTC+3 (selectable; his statement runs UTC+5).
DATA     the candles' open / close READ BY EYE from the user's zoomed screenshot (19:57-20:25 UTC+3, +-2 points), against
         Exness USTECm 1-minute bars from MT5 for the same minutes.
QUESTION does his chart show anything the market did not - a spike, a wick, a lead, a moving offset?

RESULT (2026-10-12, logs/his_chart_capfx.txt) - HIS CHART IS THE MARKET. Basis (CapitalFX close - Exness close) median
    207.4 points (the December futures premium), every minute 197-212 (reading error +-2 per price); 1-minute moves
    correlate 0.992. Nothing on his screen that the market did not show, at 1-minute resolution. What it shows him that
    day: a violent range (+-40-55 points a minute, 30,923-31,006). He SOLD at 20:10:48 (30,938.75) after a bounce had
    stalled, out at 20:11:35 at 30,923.25 - the 20:06 low - and BOUGHT at 20:17:55 (30,928.75) on the retest of that
    low, out 6 s later +5.5. Held 3 minutes, the sell would have been ~-60 and the buy ~-80 points.

    python -m backtest.his_chart_capfx        (needs the MT5 terminal running)
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / "logs" / "his_chart_capfx.txt"

# CapitalFX NASDAQ Dec, 1-minute open / close, UTC+3, read off the user's screenshot (2026-10-08)
CAP = {"19:57": (30977, 30985), "19:58": (30989, 31006), "19:59": (31003, 31000), "20:00": (31000, 30951),
       "20:01": (30949, 30935), "20:02": (30935, 30991), "20:03": (30991, 30940), "20:04": (30949, 30943),
       "20:05": (30945, 30927), "20:06": (30927, 30923), "20:07": (30925, 30938), "20:08": (30944, 30948),
       "20:09": (30948, 30946), "20:10": (30946, 30934), "20:11": (30933, 30936), "20:12": (30936, 30979),
       "20:13": (30979, 30997), "20:14": (30997, 31003), "20:15": (31003, 30991), "20:16": (31000, 30956),
       "20:17": (30954, 30934), "20:18": (30934, 30941), "20:19": (30941, 30934), "20:20": (30932, 30925),
       "20:21": (30924, 30902), "20:22": (30900, 30883), "20:23": (30882, 30887), "20:24": (30886, 30881),
       "20:25": (30881, 30866)}


def main():
    import MetaTrader5 as mt5
    assert mt5.initialize(), mt5.last_error()
    r = mt5.copy_rates_range("USTECm", mt5.TIMEFRAME_M1, datetime(2026, 10, 8, 16, 55, tzinfo=timezone.utc),
                             datetime(2026, 10, 8, 17, 28, tzinfo=timezone.utc))
    mt5.shutdown()
    d = pd.DataFrame(r)
    d["t3"] = (pd.to_datetime(d.time, unit="s") + pd.Timedelta(hours=3)).dt.strftime("%H:%M")
    d = d[d.t3.isin(CAP)].copy()
    d["cap_o"] = d.t3.map(lambda k: CAP[k][0])
    d["cap_c"] = d.t3.map(lambda k: CAP[k][1])
    d["basis"] = d.cap_c - d.close
    d["exn_move"], d["cap_move"] = d.close - d.open, d.cap_c - d.cap_o
    c = np.corrcoef(d.cap_move, d.exn_move)[0, 1]
    out = [f"backtest/his_chart_capfx.py; {len(d)} one-minute candles, 2026-10-08 19:57-20:25 UTC+3 (his trades 20:10:48 SELL, "
           f"20:17:55 BUY)", f"basis CapitalFX - Exness: median {d.basis.median():.1f}, range {d.basis.min():.1f}..{d.basis.max():.1f}; "
           f"1-minute moves corr {c:.3f}", "",
           d[["t3", "open", "close", "cap_o", "cap_c", "exn_move", "cap_move", "basis"]].round(1).to_string(index=False)]
    txt = "\n".join(out)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
