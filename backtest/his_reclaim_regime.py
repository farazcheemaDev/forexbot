"""THE FAKE-BREAK RECLAIM BY THE DAILY TREND - the one filter the literature says matters (2026-11-22)

THE USER (2026-11-22): "search the web for how professional traders predict fake breaks". The closest study is Taylor (2026), arXiv
2610.35887, the ICT accumulation-manipulation-distribution model on CME NQ (15-minute bars, 2022-01 .. 2026-07, 484 signal days): the
fake break ('manipulation' of the Asia range) predicts the day's close only when it agrees with the DAILY trend regime (a 20-day EMA on
daily closes; uptrend = close > 0.5% above it, downtrend > 0.5% below, else ranging): trend-aligned 61.6% / 70.8% correct, trend-opposed
29.6% / 24.8%; "no directional information beyond the daily trend regime". This applies that filter to OUR fake-break setup
(his_reclaim.py: back through a broken swing level, 50-52% of +-7 races on 181 days) and to his trades.
DATA   the reclaim moments of his_reclaim.py (181 Exness tick days, every 1-minute close + 14 s, 09:45-15:45 New York); the regime from
       CME NQ daily closes at 16:00 New York (Databento 1-minute bars, strategy_analysis/data/nq_1m/NQ_2025.parquet + NQ_2026.parquet), the
       EMA20 and the 0.5% band of the paper, as of the PREVIOUS close (known before the day).
TESTS  the reclaim race (+-7, race2, 10 minutes) for trend-ALIGNED, trend-OPPOSED and RANGING reclaims, by half; his 7 reclaims and all his
       trades by regime alignment.
REGISTERED BEFORE THE FIRST NUMBER (2026-11-22)
  W1  Trend-aligned reclaims beat trend-opposed ones by at least 3 points on both halves (the paper's direction). (55%)
  W2  Trend-aligned reclaims stay under 56% on both halves - short of the 61% a +-7 trade needs after costs. (70%)
  W3  His 7 reclaims are not mostly trend-aligned (at most 5 of 7). (50%)
  W4  All his trades: his side agrees with the daily regime on 40-65% of the trending-regime days' trades. (70%)

RESULT (2026-11-22, logs/his_reclaim_regime.txt): THE DAILY TREND DOES NOT SORT OUR FAKE BREAKS OR HIS. 181 days (76 up, 61 down, 44 ranging
  by the paper's EMA20 / 0.5% rule), 21,211 reclaim moments: trend-aligned 51.2% / 51.3% (tune / holdout), opposed 49.4% / 53.5%, ranging
  49.9% / 52.5% - no consistent edge (W1 wrong: +1.7 / -2.2 points). His 7 reclaims: 2 aligned, 2 opposed, 3 on ranging days, all won;
  his side = the daily trend on 14 of 28 trending-day trades (50%). The paper's effect is the trend predicting the rest of the DAY; it
  says nothing about the next minute. W2-W4 right.

    python -m backtest.his_reclaim_regime
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backtest.his_level_memory import TICKS, minute_bars, swings  # noqa: E402
from backtest.his_reclaim import broken_level  # noqa: E402

LOG = ROOT / "logs" / "his_reclaim_regime.txt"


def daily_regime() -> pd.Series:
    """+1 uptrend / -1 downtrend / 0 ranging for each New York date, from the PREVIOUS 16:00 close vs its EMA20 (the paper's 0.5% band)."""
    parts = []
    for y in (2025, 2026):
        d = pd.read_parquet(ROOT / "strategy_analysis" / "data" / "nq_1m" / f"NQ_{y}.parquet")
        parts.append(d.sort_values(["ts_event", "volume"]).drop_duplicates("ts_event", keep="last"))
    d = pd.concat(parts)
    t = pd.to_datetime(d.ts_event, utc=True).dt.tz_convert("America/New_York").dt.tz_localize(None)
    s = pd.Series(d.close.to_numpy(float), index=pd.DatetimeIndex(t)).sort_index()
    s = s[(s.index.hour < 16) & (s.index.dayofweek < 5)]
    close = s.groupby(s.index.normalize()).last()                   # the last trade before 16:00 New York
    ema = close.ewm(span=20, adjust=False).mean()
    gap = close / ema - 1
    reg = pd.Series(np.where(gap > 0.005, 1, np.where(gap < -0.005, -1, 0)), index=close.index)
    return reg.shift(1)                                             # known at the open: yesterday's regime


def main():
    import backtest.his_tape as TP
    from backtest.his_race_curve import race2
    reg = daily_regime()
    cache = pickle.loads(TICKS.read_bytes())
    prep = {}
    for day, dd in cache.items():
        if dd is None:
            continue
        ts, mid = dd[0], dd[1]
        hi, lo = minute_bars(ts, mid)
        sh, sl = swings(hi, lo)
        prep[day] = (ts, mid, hi, lo, sh, sl)
    days = sorted(prep)
    cut = days[int(len(days) * 0.6)]
    rows = []
    for day in days:
        rg = reg.get(day, np.nan)
        if not np.isfinite(rg):
            continue
        ts, mid, hi, lo, sh, sl = prep[day]
        for t in np.arange(15 * 60 + 14, 375 * 60 + 14, 60.0):
            b = broken_level(ts, mid, hi, lo, sh, sl, t)
            if b is None:
                continue
            w = race2(ts, mid, t, b[0], 600, 7, 7)
            if w is not None:
                al = "ranging" if rg == 0 else ("aligned" if b[0] == rg else "opposed")
                rows.append(dict(day=day, win=w, al=al))
    R = pd.DataFrame(rows)
    R["half"] = np.where(R.day < cut, "tune", "hold")
    out = [f"backtest/his_reclaim_regime.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; {R.day.nunique()} tick days with a daily regime, split "
           f"{pd.Timestamp(cut):%Y-%m-%d}; reclaim moments {len(R):,}; days by regime: "
           + ", ".join(f"{k} {v}" for k, v in reg.reindex(sorted(R.day.unique())).map({1: 'up', -1: 'down', 0: 'ranging'}).value_counts().items()), "",
           f"  {'reclaim vs the daily trend':<28}{'tune':>18}{'holdout':>18}"]
    res = {}
    for al in ("aligned", "opposed", "ranging"):
        cells = []
        for h in ("tune", "hold"):
            x = R[(R.al == al) & (R.half == h)]
            res[(al, h)] = x.win.mean() if len(x) else np.nan
            cells.append(f"{x.win.mean():.1%} of {len(x):,}" if len(x) else "-")
        out.append(f"  {al:<28}{cells[0]:>18}{cells[1]:>18}")
    # his trades
    x = TP.entries()
    his, recl = [], []
    for r in x.itertuples():
        rg = reg.get(r.d, np.nan)
        if not np.isfinite(rg):
            continue
        his.append(dict(s=r.s, rg=rg))
        pr = prep.get(r.d)
        if pr is not None and r.t >= 15 * 60:
            b = broken_level(*pr, r.t)
            if b is not None and b[0] == r.s:
                recl.append(dict(s=r.s, rg=rg, win=race2(pr[0], pr[1], r.t, r.s, 600, 7, 7)))
    Hh, Rc = pd.DataFrame(his), pd.DataFrame(recl)
    tr = Hh[Hh.rg != 0]
    agree = int((tr.s == tr.rg).sum())
    al_recl = int((Rc.s == Rc.rg).sum()) if len(Rc) else 0
    out += ["", f"  HIS TRADES on trending-regime days: {len(tr)} of {len(Hh)}; his side = the daily trend on {agree} ({agree / max(len(tr), 1):.0%}); "
                f"ranging days {int((Hh.rg == 0).sum())}",
            f"  HIS RECLAIMS: {len(Rc)} - trend-aligned {al_recl}, opposed {int(((Rc.s != Rc.rg) & (Rc.rg != 0)).sum())}, on ranging days "
            f"{int((Rc.rg == 0).sum())}; won {int((Rc.win == 1).sum())}"]
    ok = lambda b: "RIGHT" if b else "WRONG"  # noqa: E731
    w1 = all(res[("aligned", h)] - res[("opposed", h)] >= 0.03 for h in ("tune", "hold"))
    out += ["", "REGISTERED PREDICTIONS",
            f"  W1 aligned beats opposed by 3+ points on both halves -> {ok(w1)} ("
            + " | ".join(f"{h} {(res[('aligned', h)] - res[('opposed', h)]) * 100:+.1f}" for h in ("tune", "hold")) + " points)",
            f"  W2 aligned under 56% on both halves -> {ok(all(res[('aligned', h)] < 0.56 for h in ('tune', 'hold')))}",
            f"  W3 his 7 reclaims at most 5 trend-aligned -> {ok(al_recl <= 5)} ({al_recl})",
            f"  W4 his side = the daily trend on 40-65% of trending days' trades -> {ok(0.40 <= agree / max(len(tr), 1) <= 0.65)}"]
    txt = "\n".join(out)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
