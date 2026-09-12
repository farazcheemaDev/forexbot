"""CASCADE DIP-BUYING AT 1-MINUTE RESOLUTION — is the 60bp bounce capturable?

WHERE THIS SITS
---------------
liq_cascade.py established the effect: 5m bars with FALLING open interest and a
sharp price drop (forced liquidation) bounce 60.6bp low-to-close, versus 14.2bp for
identical price drops with RISING OI (voluntary selling). t=+3.79, 7.4 events/day.
That is 15x the maker cost - the only effect measured today that is not swamped by
its own frictions.

cascade_ticks.py then failed for a data reason, not a strategy reason: Binance
serves aggTrades for only ~2-3 days (400 Bad Request beyond), so 61 of 70 events
had no tick data.

THE CAUSAL LOOPHOLE THAT MAKES THIS TRADEABLE
---------------------------------------------
Open interest for the 5-minute window ENDING at T is published AT T. So at T+1min
we legitimately know that deleveraging was under way during the window just
finished - and cascades run across several windows. That is a real, causal,
real-time signal. Nothing here uses information from the future.

    filter (causal):  OI fell sharply over the LAST COMPLETED 5m window
    trigger (causal): the current 1m bar drops sharply vs recent volatility
    action:           post a LIMIT BUY below the trigger bar's close
    fill:             only if a later 1m bar's LOW actually reaches it
    exit:             after a fixed number of minutes

Entry is a maker fill (we are providing the liquidity that distressed sellers
need - that is the entire thesis), exit is a taker fill. Costs charged accordingly.

THE CONTROL THAT DECIDES IT
---------------------------
The same dip-buy is run with the OI filter INVERTED (OI rising = voluntary
selling). If forced and voluntary dips pay the same, there is no mechanism and we
are just buying dips - which we already know loses. The gap between them IS the
edge.

    python -m backtest.cascade_1m
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.liq_cascade import _get, oi_hist  # noqa: E402

CACHE = Path(__file__).resolve().parents[1] / "strategy_analysis" / "data"

COINS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT",
         "AVAXUSDT", "ARBUSDT", "SUIUSDT"]
MAKER_BP, TAKER_BP = 2.0, 6.0


def klines_1m(sym: str, pages: int = 44) -> pd.DataFrame | None:
    f = CACHE / f"k1m_{sym}.csv"
    if f.exists():
        return pd.read_csv(f, parse_dates=["t"])
    rows, end = [], int(time.time() * 1000)
    for _ in range(pages):
        r = _get(f"https://fapi.binance.com/fapi/v1/klines?symbol={sym}"
                 f"&interval=1m&limit=1000&endTime={end}")
        if not r:
            break
        rows = r + rows
        end = int(r[0][0]) - 1
        time.sleep(0.15)
    if not rows:
        return None
    d = pd.DataFrame([{"t": pd.to_datetime(k[0], unit="ms"), "open": float(k[1]),
                       "high": float(k[2]), "low": float(k[3]),
                       "close": float(k[4]), "vol": float(k[5])} for k in rows])
    d = d.drop_duplicates("t").sort_values("t").reset_index(drop=True)
    d.to_csv(f, index=False)
    return d


def prepare(sym: str) -> pd.DataFrame | None:
    k = klines_1m(sym)
    oi = oi_hist(sym)
    if k is None or oi is None or len(k) < 5000:
        return None
    oi = oi.copy()
    oi["doi"] = oi.oi.pct_change()
    oi["doi_z"] = oi.doi / oi.doi.rolling(288).std()
    # SHIFT BY ONE 5m PERIOD: the reading stamped at T describes the window that
    # just closed, so it is only usable from T onward. Shifting guarantees no bar
    # can see its own OI.
    oi["doi_z_avail"] = oi["doi_z"].shift(1)
    oi = oi[["t", "doi_z_avail"]].copy()
    # the two cached CSVs parse to different datetime precisions (ms vs us), which
    # merge_asof refuses. Normalise both before joining.
    k = k.copy()
    k["t"] = k["t"].astype("datetime64[ns]")
    oi["t"] = oi["t"].astype("datetime64[ns]")
    d = pd.merge_asof(k.sort_values("t"), oi.sort_values("t"), on="t",
                      direction="backward", tolerance=pd.Timedelta("10min"))
    d["ret1"] = np.log(d.close).diff()
    d["vol60"] = d.ret1.rolling(60).std()
    d["ret_z"] = d.ret1 / d.vol60
    d["atr"] = (d.high - d.low).rolling(60).mean()
    d["sym"] = sym
    return d.dropna(subset=["ret_z", "atr", "doi_z_avail"])


def run(d: pd.DataFrame, trig_z: float, oi_cut: float, invert: bool,
        offset_atr: float, wait: int, hold: int) -> tuple[np.ndarray, int, int]:
    """Return (R-free net bp per filled trade, attempts, fills)."""
    lo = d.low.to_numpy(); hi = d.high.to_numpy(); cl = d.close.to_numpy()
    rz = d.ret_z.to_numpy(); oz = d.doi_z_avail.to_numpy(); at = d.atr.to_numpy()
    n = len(d)
    out = []
    att = fills = 0
    i = 60
    while i < n - (wait + hold + 1):
        oi_ok = (oz[i] > oi_cut) if invert else (oz[i] < -oi_cut)
        if rz[i] < -trig_z and oi_ok and at[i] > 0:
            att += 1
            limit = cl[i] - offset_atr * at[i]
            got = None
            for j in range(i + 1, i + 1 + wait):
                if lo[j] <= limit:
                    got = j
                    break
            if got is not None:
                fills += 1
                ex = min(got + hold, n - 1)
                bp = (cl[ex] / limit - 1) * 1e4 - (MAKER_BP + TAKER_BP)
                out.append(bp)
                i = ex + 1
                continue
            i += wait
            continue
        i += 1
    return np.asarray(out), att, fills


def main():
    print("Fetching 1m klines + open interest (cached after first run)...")
    frames = []
    for s in COINS:
        d = prepare(s)
        if d is not None:
            frames.append(d)
            print(f"  {s:9} {len(d):>6} usable 1m bars")
    if not frames:
        print("no data"); return
    D = pd.concat(frames, ignore_index=True)
    print(f"\n  {len(D):,} bars, {len(frames)} coins, "
          f"{(D.t.max()-D.t.min()).days} days\n")

    print("=" * 92)
    print("FORCED (OI falling) vs VOLUNTARY (OI rising) dip-buying — the gap is the edge")
    print("=" * 92)
    print(f"{'trig':>5} {'off':>5} {'hold':>5} | "
          f"{'FORCED  n   fill%   net bp      t':>38} | "
          f"{'VOLUNTARY  n   net bp':>24} | {'gap bp':>8}")
    best = []
    for trig in (2.5, 3.5):
        for off in (0.25, 0.5, 1.0):
            for hold in (5, 15):
                a, att_a, f_a = run(pd.concat(frames), trig, 1.0, False, off, 5, hold)
                b, att_b, f_b = run(pd.concat(frames), trig, 1.0, True, off, 5, hold)
                if len(a) < 25 or len(b) < 25:
                    continue
                sea = a.std(ddof=1) / np.sqrt(len(a))
                seb = b.std(ddof=1) / np.sqrt(len(b))
                gap = a.mean() - b.mean()
                print(f"{trig:>5.1f} {off:>5.2f} {hold:>4}m | "
                      f"{len(a):>6} {f_a/max(att_a,1)*100:>6.0f}% "
                      f"{a.mean():>+8.1f} ±{sea:>4.1f} {a.mean()/sea:>+6.2f} | "
                      f"{len(b):>7} {b.mean():>+8.1f} ±{seb:>4.1f} | {gap:>+8.1f}")
                best.append((a.mean() / sea, trig, off, hold, a, b, gap))
    if not best:
        print("\nno configuration produced enough fills")
        return
    best.sort(reverse=True, key=lambda x: x[0])
    t, trig, off, hold, a, b, gap = best[0]
    print(f"\nstrongest: trigger {trig}z, offset {off}xATR, hold {hold}m")
    print(f"  forced    {a.mean():+.1f}bp on {len(a)} trades  t={t:+.2f}")
    print(f"  voluntary {b.mean():+.1f}bp on {len(b)} trades")
    print(f"  gap       {gap:+.1f}bp  <- this is the mechanism, if it is real")
    print(f"\n  costs already deducted: {MAKER_BP}bp maker in + {TAKER_BP}bp taker out")


if __name__ == "__main__":
    main()
