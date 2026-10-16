"""HIS TWO TRADES OF 2026-10-13, seen live in the user's app (History screenshot) and scored on Exness ticks (2026-10-13)

The History screen's clock is UTC+5, like the statements: at UTC+5 the market's move over each hold equals the points he
banked to the cent (+12.01 vs +12.00, +6.74 vs +6.75) and the basis is steady (189.5 / 189.2); at UTC+3 neither holds.
Tickets in counter order: open 13990130 < close 13990135 < open 13990144 < close 13990146.

RESULT (logs/his_live_1013.txt): both SELLs won the +-7 race (in 30 s and 71 s), each after the market had moved slightly
    AGAINST him in the 5 s before his click (-0.50, -1.00) - the pullback again. 11:24 and 11:27 New York - his 11:00
    habit. Out-of-sample record: 40 of 45.

    python -m backtest.his_live_1013        (needs MT5 running)
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
TRADES = [("SELL", "20:24:30", 30698.25, "20:25:54", 30686.25), ("SELL", "20:27:06", 30678.25, "20:28:18", 30671.50)]


def main():
    import MetaTrader5 as mt5
    assert mt5.initialize(), mt5.last_error()
    out = ["backtest/his_live_1013.py - 2026-10-13, History clock tested at UTC+3 and UTC+5"]
    for off in (3, 5):
        out.append(f"--- History clock = UTC+{off}")
        for side, ot, op, ct, cp in TRADES:
            o = pd.Timestamp(f"2026-10-13 {ot}") - pd.Timedelta(hours=off)
            c = pd.Timestamp(f"2026-10-13 {ct}") - pd.Timedelta(hours=off)
            tk = mt5.copy_ticks_range("USTECm", (o - pd.Timedelta(minutes=2)).tz_localize("UTC").to_pydatetime(),
                                      (o + pd.Timedelta(minutes=12)).tz_localize("UTC").to_pydatetime(), mt5.COPY_TICKS_ALL)
            t = pd.to_datetime(tk["time_msc"], unit="ms").values
            mid = (tk["bid"] + tk["ask"]) / 2

            def at(x):
                return mid[np.searchsorted(t, np.datetime64(x), "right") - 1]
            s = -1 if side == "SELL" else 1
            i0 = np.searchsorted(t, np.datetime64(o), "right") - 1
            path, tt = s * (mid[i0:] - mid[i0]), (t[i0:] - t[i0]) / np.timedelta64(1, "s")
            up, dn = np.flatnonzero(path >= 7), np.flatnonzero(path <= -7)
            race = "WON" if len(up) and (not len(dn) or up[0] < dn[0]) else ("LOST" if len(dn) else "open")
            out.append(f"  {side} {ot}: basis {op - at(o):+.1f} | market {s * (at(c) - at(o)):+.2f} his way over the hold "
                       f"(banked {s * (cp - op):+.2f}) | +-7 race {race} in {tt[up[0]] if len(up) else float('nan'):.0f} s | "
                       f"5 s before the click {s * (at(o) - at(o - pd.Timedelta(seconds=5))):+.2f}")
    mt5.shutdown()
    txt = "\n".join(out)
    (ROOT / "logs" / "his_live_1013.txt").write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
