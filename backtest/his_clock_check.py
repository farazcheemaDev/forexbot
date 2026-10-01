"""WAS HIS JANUARY-MARCH CLOCK ONE HOUR OFF? - a per-period timezone check on his NASDAQ trades.

WHY (2026-10-01, from logs/his_vs_market.csv, no new data)
    Every analysis of him converts the statement's times with ONE offset, GMT = 5.0, for all nine
    months. Split at the European clock change (2026-03-29) the record looks like two different
    traders:

                                         before 29 Mar (19)   after 29 Mar (27)
      real market moved his way              37%, -1.3 pts       96%, +10.2 pts
      |his points - market move|, median        11.0                 3.2
      his broker's basis across days        -192 ... +351       smooth roll-down to ~0 at expiry

    s25 read the left column as "his January-March PRICES are not the market's". A clock error
    gives the same picture: compare his fill with the market at the wrong hour and the basis turns
    into the market's one-hour move (hundreds of points, random sign), and "the market move during
    his hold" becomes the move of some other few minutes (~0 on average). The checks that settled
    the offset could not see a seasonal error: s15 tested +0/+3/+5/+7 pooled over all months (s14's
    methods had split between +4 and +5), and s25 searched only +-600 s, pooled. His sitting time
    agrees: 19:14 Pakistan time before the change, 20:38 after - in a country with no DST.

WHAT THIS DOES
    For every candidate offset, and separately for each period, his entry and exit are placed at
    statement_time - offset and the real USTECm mid is read at both from MT5 ticks. With the right
    clock his points equal the market's move minus his costs, so |pts - mv| is small (it is also the
    in-trade jump of his broker's basis). Reported per period and offset: that error, the share of
    trades where the market moved his way, and the mean market move.
    Periods: before 2026-03-08 (US DST), 03-08..03-29, after 2026-03-29 (EU DST).

REGISTERED PREDICTION (2026-10-01, before any run on real data)
    - after 29 Mar: best offset 5.0. This is the CONTROL - if it is not 5.0, the method is broken.
    - before 08 Mar: best offset 4.0 (true UTC = statement - 4 h), with median |pts - mv| <= 5 and
      the market moving his way in >= 80% of trades, against 11.0 and 37% at 5.0.
    - If confirmed: s25's "his broker's January-March prices are not the market's" was the clock,
      ~19 January-March NASDAQ trades rejoin the clean sample (25 -> ~44), and every s17-s34 result
      that used January-March times must be re-run at the corrected offset.

    python -m backtest.his_clock_check            on the PC with the MT5 terminal open
    python -m backtest.his_clock_check --offsets 3.5,4,4.5,5,5.5
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
US_DST = pd.Timestamp("2026-03-08 07:00")      # 02:00 EST, in UTC
EU_DST = pd.Timestamp("2026-03-29 01:00")      # 01:00 UTC
OFFSETS = (3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0)
PERIODS = ("before 08 Mar", "08-29 Mar", "after 29 Mar")


def period(t: pd.Timestamp) -> str:
    return PERIODS[0] if t < US_DST else PERIODS[1] if t < EU_DST else PERIODS[2]


def to_utc(t: pd.Series, winter: float = 5.0, summer: float = 5.0) -> pd.Series:
    """Statement time -> UTC, with one offset before the EU clock change and another after. The
    defaults reproduce every earlier script (one GMT = 5.0); run this check first to choose them."""
    off = np.where(t - pd.Timedelta(hours=summer) < EU_DST, winter, summer)
    return t - pd.to_timedelta(off, unit="h")


class MT5Mid:
    """The USTECm mid at a UTC instant: the last tick at or before it."""

    def __init__(self, sym: str = "USTECm"):
        import MetaTrader5 as mt5
        assert mt5.initialize(), mt5.last_error()
        self.mt5, self.sym = mt5, sym

    def __call__(self, t: pd.Timestamp) -> float | None:
        a = (t - pd.Timedelta(seconds=120)).tz_localize("UTC").to_pydatetime()
        b = (t + pd.Timedelta(seconds=1)).tz_localize("UTC").to_pydatetime()
        # a NAIVE datetime is read as local time by MT5 (CLAUDE.md s10, 2026-09-25): pass UTC-aware
        x = self.mt5.copy_ticks_range(self.sym, a, b, self.mt5.COPY_TICKS_ALL)
        if x is None or not len(x):
            return None
        d = pd.DataFrame(x)
        d["ts"] = pd.to_datetime(d.time_msc, unit="ms")
        d = d[(d.bid > 0) & (d.ask > 0) & (d.ts <= t)]
        return float((d.bid.iloc[-1] + d.ask.iloc[-1]) / 2) if len(d) else None


def load_trades(path: Path) -> pd.DataFrame:
    x = pd.read_csv(path, parse_dates=["open_time", "close_time"])
    x = x[x.symbol.str.startswith("NASDAQ")].copy()
    x["sgn"] = np.where(x.side.str.upper() == "BUY", 1, -1)
    x["pts"] = x.sgn * (x.close_price - x.open_price)
    return x.reset_index(drop=True)


def measure(x: pd.DataFrame, mid, offsets=OFFSETS) -> pd.DataFrame:
    """One row per trade per offset: the market move his way over his hold, and |pts - mv|."""
    rows = []
    for o in offsets:
        sh = pd.Timedelta(hours=o)
        for r in x.itertuples():
            a, b = mid(r.open_time - sh), mid(r.close_time - sh)
            if a is None or b is None:
                continue
            mv = r.sgn * (b - a)
            rows.append(dict(offset=o, period=period(r.open_time - pd.Timedelta(hours=5)),
                             open_time=r.open_time, pts=r.pts, mv=mv, err=abs(r.pts - mv)))
    return pd.DataFrame(rows)


def summarise(m: pd.DataFrame) -> pd.DataFrame:
    g = m.groupby(["period", "offset"]).agg(trades=("err", "size"), median_err=("err", "median"),
                                            market_his_way=("mv", lambda v: (v > 0).mean()),
                                            mean_move=("mv", "mean"))
    return g.reset_index()


def best(s: pd.DataFrame) -> dict:
    return {p: float(g.loc[g.median_err.idxmin(), "offset"]) for p, g in s.groupby("period")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trades", default=str(ROOT / "strategy_analysis" / "statement_trades.csv"))
    ap.add_argument("--offsets", default=",".join(str(o) for o in OFFSETS))
    args = ap.parse_args()
    x = load_trades(Path(args.trades))
    offs = tuple(float(v) for v in args.offsets.split(","))
    m = measure(x, MT5Mid(), offs)
    s = summarise(m)
    print(f"HIS CLOCK, PER PERIOD - {len(x)} NASDAQ trades, offsets {offs}")
    print("With the right offset his points = the market's move minus costs: median |pts - mv| ~3.\n")
    for p in PERIODS:
        g = s[s.period == p]
        if not len(g):
            continue
        print(f"{p}")
        print(f"  {'offset':>7}{'trades':>8}{'median |pts-mv|':>17}{'market his way':>16}{'mean move':>11}")
        for r in g.itertuples():
            print(f"  {r.offset:>7.1f}{r.trades:>8}{r.median_err:>17.2f}{r.market_his_way:>15.0%}{r.mean_move:>+11.2f}")
    b = best(s)
    print(f"\nBEST OFFSET: " + " | ".join(f"{p}: UTC+{o:g}" for p, o in b.items()))
    ok = b.get(PERIODS[2]) == 5.0
    print(f"CONTROL (after 29 Mar must be UTC+5): {'PASS' if ok else 'FAIL - the method is broken, trust nothing above'}")
    out = ROOT / "logs" / "his_clock_check.csv"
    m.to_csv(out, index=False)
    print(f"per trade and offset: {out}")


if __name__ == "__main__":
    sys.exit(main())
