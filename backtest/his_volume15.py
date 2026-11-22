"""THE DAY'S VOLUME AND THE 15-MINUTE CHART AT THE NASDAQ TRADER'S CLICKS (2026-11-21)

THE USER (2026-11-21): "there must be something - the volume pumping of that day, or the 15-min chart, or whatever". Tested before at his
clicks: the CME aggressor flow 5 s .. 2 min before (his_tape.py, s37: 48-55% agreement), volume in the prior 30 minutes (his_news.py:
rank 0.49), the volume profile (his_volprofile.py, s59), the previous session's range / gap / volatility (his_day_choice.py), 5- and
15-minute RSI (his_rsi_long.py), a 15-minute impulse + pullback setup (his_setup_sweep.py). NOT tested: how much volume the DAY has
pumped by his click, and the last 15-minute bar's direction, volume and buy-minus-sell volume.
DATA   his NASDAQ trades (his_noise.his_trades: the statement with its corrected clock + the later ones; New York time, side); CME NQ
       front-volume 1-minute bars WITH volume (Databento, strategy_analysis/data/nq_1m/NQ_2026.parquet, 2026-01 .. 10-29).
AT EACH CLICK (closed bars only - he clicks ~14 s after a minute's close):
  DAY      the Globex day (18:00 New York the evening before -> the click): its direction (last close vs the 18:00 open), its
           signed volume (each minute's volume x the sign of its close - open), and its RELATIVE VOLUME (volume so far / the median of
           the same clock window over the previous 20 trading days) - 'the volume pumping of that day'
  15 MIN   the last CLOSED clock 15-minute bar (:00 / :15 / :30 / :45): its direction, its relative volume (vs the same slot's median
           over 20 days); and the signed volume of the last 15 one-minute bars
TESTS    his side vs each direction (binomial against 50%), on all clicks and on 'pumping' clicks (day relative volume >= 1.3 or the
         15-minute bar's >= 1.5); Holm over the 8 agreement tests. Where his clicks sit in volume (percentile of the day's and the
         15-minute relative volume among all 2026 days at the same clock time). And the RULE itself on every 2026 day, 09:45-15:45 New
         York, regardless of him: after a high-volume 15-minute bar (>= 1.5x), does the next 15 minutes go its way?
REGISTERED BEFORE THE FIRST NUMBER (2026-11-21)
  V1  His side agrees with each direction measure on 40-60% of his clicks; none survives Holm. (80%)
  V2  On 'pumping' clicks the agreement is still 35-65%. (75%)
  V3  His clicks sit at ordinary volume: the mean percentile of the day's relative volume is 35-65. (65%)
  V4  The rule on all days: the next 15 minutes follow a high-volume 15-minute bar 47-53% of the time. (75%)

RESULT (2026-11-21, logs/his_volume15.txt): NOT VOLUME, NOT THE 15-MINUTE CHART. 50 of his 53 trades scored. His side vs the Globex day's
  direction 25 of 50 (50%), the day's signed volume 26 (52%), the last 15-minute bar's direction 26 (52%), the last 15 minutes' signed
  volume 26 (52%); Holm 1.00 for all. He trades at ORDINARY volume: the day's relative volume at his clicks median 0.99x (45th
  percentile of all 2026 days at the same clock time), the 15-minute bar's 0.97x (46th). On the 11 'pumping' clicks his side matched the
  15-minute bar and the day's signed volume 8 of 11 (p 0.23) - too few to read. The rule itself on every 2026 day: after a high-volume
  15-minute bar the next 15 minutes went the same way 46.5% of 621 times (p 0.09; ordinary bars 49.4%). V1, V3 right; V2 wrong (73% on
  11 clicks); V4 wrong (46.5%, a slight reversal).

    python -m backtest.his_volume15
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
LOG = ROOT / "logs" / "his_volume15.txt"


def nq_minutes() -> pd.DataFrame:
    d = pd.read_parquet(ROOT / "strategy_analysis" / "data" / "nq_1m" / "NQ_2026.parquet")
    d = d.sort_values(["ts_event", "volume"]).drop_duplicates("ts_event", keep="last")     # one row a minute: the busier contract
    t = pd.to_datetime(d.ts_event, utc=True).dt.tz_convert("America/New_York").dt.tz_localize(None)
    m = pd.DataFrame({"o": d.open.to_numpy(), "c": d.close.to_numpy(), "v": d.volume.to_numpy(float)}, index=pd.DatetimeIndex(t))
    m["sv"] = m.v * np.sign(m.c - m.o)
    # the Globex day a minute belongs to: 18:00 New York starts the next day's session
    m["gday"] = (m.index + pd.Timedelta(hours=6)).normalize()
    m["since"] = ((m.index.to_series() - (m.gday - pd.Timedelta(hours=6))).dt.total_seconds() // 60).astype(int)  # minutes since 18:00 the evening before
    return m


def at(m: pd.DataFrame, t: pd.Timestamp) -> dict | None:
    """Everything known at a click at New York time t (bars that closed by t)."""
    last = t.floor("min") - pd.Timedelta(minutes=1)                 # the last closed 1-minute bar
    if last not in m.index:
        return None
    gd = m.at[last, "gday"]
    day = m[(m.gday == gd) & (m.index <= last)]
    q_end = t.floor("15min")                                        # the last CLOSED 15-minute bar ends here
    q = m[(m.index >= q_end - pd.Timedelta(minutes=15)) & (m.index < q_end)]
    l15 = m[(m.index > last - pd.Timedelta(minutes=15)) & (m.index <= last)]
    if len(day) < 30 or len(q) < 10 or len(l15) < 10:
        return None
    return dict(day_dir=np.sign(day.c.iloc[-1] - day.o.iloc[0]), day_sv=np.sign(day.sv.sum()), day_vol=day.v.sum(),
                q_dir=np.sign(q.c.iloc[-1] - q.o.iloc[0]), q_vol=q.v.sum(), l15_sv=np.sign(l15.sv.sum()),
                since=int(m.at[last, "since"]), slot=(q_end - pd.Timedelta(minutes=15)).strftime("%H:%M"), gday=gd)


def norms(m: pd.DataFrame) -> tuple:
    """Per Globex day: cumulative volume by minutes-since-18:00; per day and 15-minute slot: the slot's volume."""
    cum = m.groupby("gday").apply(lambda x: pd.Series(x.v.cumsum().to_numpy(), index=x.since.to_numpy()), include_groups=False)
    slot = m.assign(slot=m.index.floor("15min").strftime("%H:%M")).groupby(["gday", "slot"]).v.sum()
    return cum, slot


def rel(series_by_day: pd.Series, gd, key, n=20) -> float:
    """Value on day gd at key / the median of the same key over the previous n days (NaN when not enough)."""
    try:
        s = series_by_day.xs(key, level=1)
    except KeyError:
        return np.nan
    if gd not in s.index:
        return np.nan
    past = s[s.index < gd].tail(n)
    return float(s[gd] / past.median()) if len(past) >= 10 and past.median() > 0 else np.nan


def pct_vs_all(series_by_day: pd.Series, gd, key, n=20) -> float:
    """Where day gd's relative value at key sits among every 2026 day's relative value at the same key (percentile)."""
    try:
        s = series_by_day.xs(key, level=1)
    except KeyError:
        return np.nan
    r = {d: s[d] / s[s.index < d].tail(n).median() for d in s.index if (s.index < d).sum() >= 10}
    r = pd.Series(r)
    return float((r < r.get(gd, np.nan)).mean() * 100) if gd in r.index else np.nan


def main():
    from scipy.stats import binomtest
    from backtest import candle_scan as cs
    from backtest.his_noise import his_trades
    m = nq_minutes()
    cum, slot = norms(m)
    T = his_trades()
    rows = []
    for r in T.itertuples():
        a = at(m, r.et)
        if a is None:
            continue
        a["side"] = r.side
        a["et"] = r.et
        a["pts"] = r.pts
        a["day_rvol"] = rel(cum, a["gday"], a["since"])
        a["q_rvol"] = rel(slot, a["gday"], a["slot"])
        a["day_pct"] = pct_vs_all(cum, a["gday"], a["since"])
        a["q_pct"] = pct_vs_all(slot, a["gday"], a["slot"])
        rows.append(a)
    X = pd.DataFrame(rows)
    out = [f"backtest/his_volume15.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; his NASDAQ trades {len(T)}, scored {len(X)} "
           f"(CME NQ 1-minute bars with volume to {m.index[-1]:%Y-%m-%d})", ""]
    pump = (X.day_rvol >= 1.3) | (X.q_rvol >= 1.5)
    tests = {}
    for nm, col in (("the Globex day's direction", "day_dir"), ("the day's signed volume", "day_sv"),
                    ("the last 15-min bar's direction", "q_dir"), ("the last 15 minutes' signed volume", "l15_sv")):
        for sub, msk in (("all clicks", np.ones(len(X), bool)), ("pumping clicks", pump.to_numpy())):
            x = X[msk & (X[col] != 0)]
            k = int((x.side == x[col]).sum())
            p = binomtest(k, len(x), 0.5).pvalue if len(x) else np.nan
            tests[(nm, sub)] = (k, len(x), p)
    hp = dict(zip(tests, cs.holm([v[2] if np.isfinite(v[2]) else 1.0 for v in tests.values()])))
    out.append(f"  {'his side vs':<38}{'clicks':<16}{'agree':>12}{'p':>8}{'Holm':>8}")
    for (nm, sub), (k, n, p) in tests.items():
        out.append(f"  {nm:<38}{sub:<16}{k:>4} of {n:<4}{(k / n if n else np.nan):>5.0%}{p:>8.3f}{hp[(nm, sub)]:>8.3f}")
    out += ["", f"  'pumping' clicks (day volume >= 1.3x its norm or the 15-min bar >= 1.5x): {int(pump.sum())} of {len(X)}",
            f"  the day's relative volume at his clicks: median {X.day_rvol.median():.2f}x; percentile among all 2026 days at the same clock "
            f"time: mean {X.day_pct.mean():.0f} (0-100)",
            f"  the last 15-min bar's relative volume: median {X.q_rvol.median():.2f}x; percentile mean {X.q_pct.mean():.0f}",
            f"  his banked points on pumping clicks {X[pump].pts.mean():+.2f} (won {(X[pump].pts > 0).mean():.0%}) vs the rest "
            f"{X[~pump].pts.mean():+.2f} (won {(X[~pump].pts > 0).mean():.0%})"]

    # THE RULE ITSELF on every 2026 day: after a high-volume 15-minute bar (09:45-15:45 New York), do the next 15 minutes follow it?
    q = m.assign(slot=m.index.floor("15min")).groupby("slot").agg(o=("o", "first"), c=("c", "last"), v=("v", "sum"), n=("v", "size"))
    q = q[(q.n >= 12) & (q.index.strftime("%H:%M") >= "09:30") & (q.index.strftime("%H:%M") <= "15:30")]
    q["dir"] = np.sign(q.c - q.o)
    q["slotkey"] = q.index.strftime("%H:%M")
    q["norm"] = q.groupby("slotkey").v.transform(lambda s: s.shift(1).rolling(20, min_periods=10).median())
    q["rv"] = q.v / q.norm
    q["next_dir"] = q.dir.shift(-1).where(q.index.to_series().shift(-1).sub(q.index.to_series()).eq(pd.Timedelta(minutes=15)))
    hi = q[(q.rv >= 1.5) & (q.dir != 0) & q.next_dir.notna() & (q.next_dir != 0)]
    lo = q[(q.rv < 1.5) & (q.dir != 0) & q.next_dir.notna() & (q.next_dir != 0)]
    f_hi, f_lo = float((hi.dir == hi.next_dir).mean()), float((lo.dir == lo.next_dir).mean())
    out += ["", f"  THE RULE ON EVERY 2026 DAY (09:30-15:45 New York): after a high-volume 15-minute bar (>= 1.5x its slot's norm), the next 15 "
                f"minutes went the same way {f_hi:.1%} of {len(hi)} times (binomial p {binomtest(int((hi.dir == hi.next_dir).sum()), len(hi), 0.5).pvalue:.3f}); "
                f"after an ordinary bar {f_lo:.1%} of {len(lo)}"]
    ag = {k: v[0] / v[1] for k, v in tests.items() if v[1]}
    ok = lambda b: "RIGHT" if b else "WRONG"  # noqa: E731
    out += ["", "REGISTERED PREDICTIONS",
            f"  V1 every all-clicks agreement 40-60%, none survives Holm -> "
            f"{ok(all(0.40 <= v <= 0.60 for (nm, sub), v in ag.items() if sub == 'all clicks') and min(hp.values()) >= 0.05)}",
            f"  V2 pumping-click agreement 35-65% -> {ok(all(0.35 <= v <= 0.65 for (nm, sub), v in ag.items() if sub == 'pumping clicks'))}",
            f"  V3 the day's relative-volume percentile at his clicks 35-65 -> {ok(35 <= X.day_pct.mean() <= 65)} ({X.day_pct.mean():.0f})",
            f"  V4 the next 15 minutes follow a high-volume bar 47-53% -> {ok(0.47 <= f_hi <= 0.53)} ({f_hi:.1%})"]
    out += ["", "  each click: New York time, his side | the day's direction, its signed volume | the last 15-min bar's direction, the last 15 "
                "minutes' signed volume | day relative volume, 15-min relative volume | his points"]
    for r in X.itertuples():
        f = lambda v: "+" if v > 0 else ("-" if v < 0 else "0")  # noqa: E731
        out.append(f"    {r.et:%Y-%m-%d %H:%M:%S}  {'BUY ' if r.side > 0 else 'SELL'} | day {f(r.day_dir)} {f(r.day_sv)} | 15m {f(r.q_dir)} {f(r.l15_sv)} | "
                   f"{r.day_rvol:4.2f}x {r.q_rvol:4.2f}x | {r.pts:+6.2f}")
    txt = "\n".join(out)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
