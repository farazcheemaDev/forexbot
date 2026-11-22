"""The Analyst desk's filters checked on its OWN history (2026-11-08, audit): the live 'sweet spot' (stop >= 0.8%), the 11-02 filter (RR <= 4 and
stop >= 0.4%), trend alignment, and calls on XAU / QQQ made while the UNDERLYING market is shut.

Data: backtest/analyst_replay.py's cached calls (strategy_analysis/data/analyst_replay/calls.json: 10,580 calls 2022-02 .. 2026-10, the desk's three
rules on 1h bars, a bar touching both stop and target = loss, 12bp) and its cached 1h bars; the live log copied from the VM is optional (argument).
Halves split 2024-12-07 as the replay does. Bet = calls made the same UTC day in the same direction (the desk's amended unit); t is over bets.
'Random' = the replay's own random-entry odds for each call's stop / target / hours.

RESULT (logs/analyst_replay_cuts.txt): every slice loses per call; the sweet spot -0.114R tune / -0.146R holdout (n 6,928, hit below random in every
year); wider stops only lose less because the 12bp fee is a smaller share of R. Trend-aligned calls lose a little less but hit below a random entry in
the same direction. XAU / QQQ calls made while the underlying is shut: replay QQQ -0.76R, XAU -0.84R a call (open: -0.08 / -0.22); live 16 calls
-17.8R, about two-thirds of the desk's loss.

    python backtest/analyst_replay_cuts.py [path/to/live/calls.csv]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
R = ROOT / "strategy_analysis" / "data" / "analyst_replay"
LOG = ROOT / "logs" / "analyst_replay_cuts.txt"
SPLIT = "2024-12-07"


def load():
    r = pd.DataFrame(json.loads((R / "calls.json").read_text()))
    r["t"] = pd.to_datetime(r.made_ms, unit="ms")
    r["rr"] = (r.target - r.entry).abs() / (r.entry - r.stop).abs()
    r["win"] = (r.status == "WIN").astype(float)
    r["day"] = r.t.dt.floor("D")
    r["half"] = np.where(r.t < SPLIT, "tune", "hold")
    return r


def line(lab, x):
    if len(x) < 10:
        return f"  {lab:<44} n {len(x):>5}"
    b = x.groupby(["day", "side"]).agg(R=("r_net", "mean"))
    t = b.R.mean() / (b.R.std(ddof=1) / np.sqrt(len(b))) if len(b) > 2 else np.nan
    return (f"  {lab:<44} n {len(x):>5}  bets {len(b):>4}  hit {x.win.mean() * 100:5.1f}% vs random {x.base_p.mean() * 100:5.1f}%  "
            f"R/call {x.r_net.mean():+.3f}  R/bet {b.R.mean():+.3f} (t {t:+.1f})")


def underlying_closed(sym, t) -> bool:
    """XAU: spot / CME gold shut Fri ~21:00 UTC .. Sun ~22:00 UTC and 21:00-22:00 UTC daily. QQQ: outside 14:30-20:00 UTC on weekdays (the hours that are
    the US cash session in both summer and winter)."""
    wd, hm = t.weekday(), t.hour + t.minute / 60
    if sym == "XAUUSDT":
        return wd == 5 or (wd == 6 and hm < 22) or (wd == 4 and hm >= 21) or (21 <= hm < 22)
    if sym == "QQQUSDT":
        return wd >= 5 or not (14.5 <= hm < 20)
    return False


def with_trend(r):
    out = []
    for sym, g in r[~r.symbol.isin(["XAUUSDT", "QQQUSDT"])].groupby("symbol"):
        b = pd.DataFrame(json.loads((R / f"{sym}_1h.json").read_text())).iloc[:, :5]
        b.columns = ["t", "o", "h", "l", "c"]
        b["t"] = pd.to_datetime(b.t, unit="ms")
        b = b.set_index("t").sort_index()
        d = b.c.resample("1D").last()
        dtr = (d / d.rolling(50).mean() - 1).shift(1)
        tt = g.t - pd.Timedelta(hours=1)                     # the closed bar the call was made on
        x = g.copy()
        x["tr1000"] = (b.c / b.c.rolling(1000).mean() - 1).reindex(tt, method="ffill").to_numpy()
        x["trd"] = dtr.reindex(x.t.dt.floor("D")).to_numpy()
        x["mom24"] = (b.c / b.c.shift(24) - 1).reindex(tt, method="ffill").to_numpy()
        out.append(x)
    return pd.concat(out)


def main():
    r = load()
    L = [f"backtest/analyst_replay_cuts.py, {pd.Timestamp.now():%Y-%m-%d %H:%M}; {len(r)} replay calls {r.t.min().date()} .. {r.t.max().date()}, halves split {SPLIT}"]
    cuts = [("all", r.r_net.notna()),
            ("stop < 0.4%", r.stop_pct < 0.004), ("stop 0.4-0.8%", (r.stop_pct >= 0.004) & (r.stop_pct < 0.008)),
            ("stop >= 0.8% (the sweet spot)", r.stop_pct >= 0.008), ("stop >= 1.2%", r.stop_pct >= 0.012),
            ("RR <= 2.5", r.rr <= 2.5), ("RR 2.5-4", (r.rr > 2.5) & (r.rr <= 4)), ("RR > 4", r.rr > 4),
            ("11-02 filter: RR <= 4 & stop >= 0.4%", (r.rr <= 4) & (r.stop_pct >= 0.004)),
            ("SMC & stop >= 0.8%", (r.method == "SMC") & (r.stop_pct >= 0.008)),
            ("SR & stop >= 0.8%", (r.method == "SR") & (r.stop_pct >= 0.008)),
            ("FIB & stop >= 0.8%", (r.method == "FIB") & (r.stop_pct >= 0.008)),
            ("long", r.side == "long"), ("short", r.side == "short")]
    for half in ("tune", "hold"):
        L.append(f"== {half}")
        L += [line(lab, r[m & (r.half == half)]) for lab, m in cuts]
    L.append("== the sweet spot by year")
    L += [line(str(y), x) for y, x in r[r.stop_pct >= 0.008].groupby(r.t.dt.year)]
    L.append("== trend alignment (crypto symbols): the call points WITH / AGAINST")
    tr = with_trend(r)
    sgn = np.where(tr.side == "long", 1, -1)
    for nm, col in (("the daily 50-day trend", "trd"), ("the 1000h average", "tr1000"), ("the last 24h move", "mom24")):
        w = sgn * tr[col] > 0
        for half in ("tune", "hold"):
            h = tr.half == half
            L.append(line(f"{nm} WITH {half}", tr[h & w]))
            L.append(line(f"{nm} AGAINST {half}", tr[h & ~w & tr[col].notna()]))
    L.append("== XAU / QQQ: underlying open vs shut when the call was made")
    frames = [("REPLAY", r)]
    if len(sys.argv) > 1:
        lv = pd.read_csv(sys.argv[1])
        lv = lv[lv.r_net.notna()].copy()
        lv["t"] = pd.to_datetime(lv.made_utc)
        lv["win"] = (lv.status == "WIN").astype(float)
        lv["day"] = lv.t.dt.floor("D")
        frames.append(("LIVE", lv))
    for nm, d in frames:
        d = d[d.symbol.isin(["XAUUSDT", "QQQUSDT"])].copy()
        d["shut"] = [underlying_closed(s, t) for s, t in zip(d.symbol, d.t)]
        for (s, c), x in d.groupby(["symbol", "shut"]):
            L.append(f"  {nm:6} {s} underlying {'SHUT' if c else 'open'}: n {len(x):4d} hit {x.win.mean() * 100:5.1f}% vs random {x.base_p.mean() * 100:5.1f}%  "
                     f"R/call {x.r_net.mean():+.3f}  sum {x.r_net.sum():+.1f}R  worst {x.r_net.min():+.2f}R  under -1.5R: {(x.r_net < -1.5).sum()}")
        if nm == "LIVE":
            L.append(f"  LIVE all resolved calls: n {len(lv)}, sum {lv.r_net.sum():+.1f}R")
    txt = "\n".join(L)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
