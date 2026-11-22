"""RSI ON 5-MINUTE AND 15-MINUTE CANDLES at the NASDAQ trader's entries, with overnight history (2026-11-03)

The user, 2026-11-02, after backtest/his_rsi.py (15 s / 1 min / 5 min candles, periods 2-14, 25 entries): "try it on 5 minute and 15 minute also".
his_rsi.py could not give 15-minute RSI a fair start: the tick cache begins at 09:30 New York and his entries start at 10:00, so a 15-minute RSI had two candles of history. Here the candles are
built from Exness's 1-MINUTE bars (strategy_analysis/data/mt5_1m/USTECm.parquet, UTC minute-open times, mid prices, 2026-01-01 .. 2026-10-09, the market's whole day), so every RSI has hours of history,
and the longer periods (14, 21) can be used. More entries too: the statement's clock is UTC+4 before 2026-03-08 and UTC+5 after 2026-03-29 (his_strategy s35); the three weeks between are skipped.

THE GRID (42 cells, sign-aligned to his direction): candles 5 min / 15 min x RSI periods 2 3 5 7 9 14 21 x form
    lvl  = the RSI of the last closed candle          chg  = that minus the RSI three candles earlier          hook = (flag) crossed UP through 30 (sign-aligned) in the last 3 closed candles
A candle is closed when its open + width is at or before the decision time. A decision at second t reads nothing at or after t.
STAGE A: his entries vs ~80 moments within 20 minutes of each (same direction); rank 0.50 = ordinary; flags by his rate vs the nearby rate; Holm over 42.
STAGE B: every tick day (the +7/-7 NET race over 3 minutes, base ~36%, break-even 50%), 40 random seconds x both directions; for each cell the extreme third (or flag on/off) is CHOSEN ON THE FIRST HALF
          of the days and READ ON THE SECOND; one-sided binomial vs 50%; Holm over 42.

REGISTERED BEFORE THE FIRST RUN (2026-11-03)
    Q1  Stage A: no cell survives Holm over 42 (with ~40 entries only a rank beyond ~0.65 would); the smallest raw p is between 0.01 and 0.20.
    Q2  Stage A: the 15-minute cells are no more separated from 0.5 than the 5-minute ones (mean |rank - 0.5| over the 15-minute continuous cells <= that of the 5-minute ones + 0.02).
    Q3  Stage B: no cell reaches 50% net on the second half; the best stays below 45%; 0 cells with Holm < 0.05.
    Q4  Stage B: 15 to 27 of the 42 cells keep the sign of (high - low) mid race in both halves (a coin gives 21).

RESULT (2026-11-03; logs/his_rsi_long.txt)
    Stage A: 45 of his 46 NASDAQ entries usable (1 in the changeover weeks skipped). 1 of 42 cells reaches raw p < 0.05 (chance gives ~2.1), 0 survive Holm. All seven 5-minute LEVELS sit on the
    pullback side at rank 0.41-0.42 (raw p 0.037-0.073) - that is ONE measurement, not seven (the same candles at seven smoothings); the 15-minute cells are ordinary (mean |rank - 0.5| 0.010 against
    0.064 for the 5-minute ones); the smallest 15-minute p is 0.111 (the RSI(2) hook, 12 of 45 vs 33.9% nearby). Stage B (181 tick days, 13,324 pairs): the best extreme chosen on the first half reads
    39.1% net on the second (base 35.6%, break-even 50%), 0 cells with Holm < 0.05, 27 of 42 cells keep the sign of (high - low) mid race in both halves (a coin gives ~21); the 5-minute low-third
    rule (the pullback side) reads 35.6% on the second half, i.e. nothing.
    Scored: Q1 right (smallest raw p 0.037), Q2 right, Q3 right, Q4 right at the edge of the registered 15-27 (27).
    Reading: a mild pullback tendency in his entries on 5-minute RSI (the same lean as his_ta.py's 0.44 and his_strategy s64's 'calm pullbacks'), which is not a rule: used as one it wins no more
    races than a random moment. RSI at 5 and 15 minutes does not carry his side.

    python -m backtest.his_rsi_long        writes logs/his_rsi_long.txt          tests: python tests/test_his_rsi_long.py
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.his_local import race  # noqa: E402
from backtest.his_predictors import race_net  # noqa: E402
from backtest.his_rsi import LEVEL, LOOK, holm, rsi_series  # noqa: E402
from backtest.his_ta import ROOT, TICKS, pz  # noqa: E402

BARS = ROOT / "strategy_analysis" / "data" / "mt5_1m" / "USTECm.parquet"
TFS = {"5m": 300_000, "15m": 900_000}               # candle width in ms
PERIODS = (2, 3, 5, 7, 9, 14, 21)
WARM = 60                                           # closed candles needed before a cell is read
FORMS = ("lvl", "chg")
CELLS_CONT = [f"{tf}_rsi{n}_{f}" for tf in TFS for n in PERIODS for f in FORMS]
CELLS_FLAG = [f"{tf}_rsi{n}_hook" for tf in TFS for n in PERIODS]
CELLS = CELLS_CONT + CELLS_FLAG
WINTER_END, SUMMER_START = pd.Timestamp("2026-03-08"), pd.Timestamp("2026-03-29")


def to_utc(open_time):
    """The statement's clock to UTC: UTC+4 before 2026-03-08, UTC+5 from 2026-03-29, None in between (the changeover weeks are ambiguous)."""
    t = pd.Timestamp(open_time)
    if t < WINTER_END:
        return t - pd.Timedelta(hours=4)
    if t >= SUMMER_START:
        return t - pd.Timedelta(hours=5)
    return None


def build_bars(t_ms, c, width_ms):
    """Candles from 1-minute bars: (close_time_ms, close) per candle, close_time = candle open + width."""
    t_ms, c = np.asarray(t_ms, "int64"), np.asarray(c, float)
    bins = t_ms // width_ms
    last = np.r_[np.flatnonzero(np.diff(bins)), len(bins) - 1]      # index of the last 1-minute bar of each candle
    return (bins[last] + 1) * width_ms, c[last]


def make_bars(t_ms, c):
    out = {}
    for name, w in TFS.items():
        ct, cl = build_bars(t_ms, c, w)
        out[name] = dict(close_t=ct, w=w, rsi={n: rsi_series(cl, n) for n in PERIODS})
    return out


def feats(B, t_ms, s):
    """The 42 cells at decision time t_ms (UTC ms) for a trade in direction s; None before the warm-up or when the last closed candle is stale (a market gap)."""
    out = {}
    for name, bar in B.items():
        k = int(np.searchsorted(bar["close_t"], t_ms, side="right")) - 1   # last candle whose close is at or before t
        if k < WARM or t_ms - bar["close_t"][k] > 2 * bar["w"]:
            return None
        for n in PERIODS:
            r = bar["rsi"][n]
            o = r if s == 1 else 100.0 - r
            out[f"{name}_rsi{n}_lvl"] = float(o[k])
            out[f"{name}_rsi{n}_chg"] = float(o[k] - o[k - LOOK])
            out[f"{name}_rsi{n}_hook"] = bool(any(o[j - 1] < LEVEL <= o[j] for j in range(k - LOOK + 1, k + 1)))
    return out


def stage_a(B, entries, rng):
    ranks, flag_obs, flag_ps = [], {k: 0 for k in CELLS_FLAG}, {k: [] for k in CELLS_FLAG}
    for t0, s in entries:
        mine = feats(B, t0, s)
        if mine is None:
            continue
        near = []
        for _ in range(200):
            f = feats(B, t0 + int(rng.uniform(30, 1200) * rng.choice((-1, 1)) * 1000), s)
            if f is not None:
                near.append(f)
            if len(near) >= 80:
                break
        N = pd.DataFrame(near)
        ranks.append({k: (N[k] < mine[k]).mean() + 0.5 * (N[k] == mine[k]).mean() for k in CELLS_CONT})
        for k in CELLS_FLAG:
            flag_obs[k] += int(mine[k])
            flag_ps[k].append(N[k].mean())
    RA = pd.DataFrame(ranks)
    pA, desc, rk = {}, {}, {}
    for k in CELLS_CONT:
        v = RA[k]
        rk[k] = v.mean()
        pA[k], desc[k] = pz((v.mean() - 0.5) / (np.sqrt(1 / 12) / np.sqrt(len(v)))), f"rank {v.mean():.2f}"
    for k in CELLS_FLAG:
        ps = np.array(flag_ps[k])
        e, var = ps.sum(), (ps * (1 - ps)).sum()
        pA[k] = pz((flag_obs[k] - e) / np.sqrt(var)) if var > 0 else 1.0
        desc[k] = f"his {flag_obs[k]:>2}/{len(ps)} vs nearby {ps.mean() * 100:4.1f}%"
    return len(RA), pA, desc, rk


def stage_b(B, cache, days, rng):
    from scipy.stats import binomtest
    rows = []
    for d in days:
        open_ms = pd.Timestamp(d + pd.Timedelta(hours=9, minutes=30)).tz_localize("America/New_York").tz_convert("UTC").value // 10**6
        ts, mid, spr = cache[d]
        for t in rng.uniform(1800, 23400, 40):
            for s in (1, -1):
                f = feats(B, open_ms + int(t * 1000), s)
                o = race(ts, mid, t, s)
                if f is None or o is None:
                    continue
                rows.append(f | {"o": o, "on": race_net(ts, mid, spr, t, s), "day": d})
    P = pd.DataFrame(rows)
    mid_day = days[len(days) // 2]
    res, same = {}, 0
    for k in CELLS:
        q = P.dropna(subset=[k, "on"])
        if k in CELLS_FLAG:
            hi, lo = q[k].astype(bool), ~q[k].astype(bool)
        else:
            hi, lo = q[k] >= q[k].quantile(2 / 3), q[k] <= q[k].quantile(1 / 3)
        h1, h2 = q.day < mid_day, q.day >= mid_day
        side, name = (hi, "high/on") if q["on"][hi & h1].mean() >= q["on"][lo & h1].mean() else (lo, "low/off")
        sel1, sel2 = q["on"][side & h1], q["on"][side & h2]
        n2, k2 = len(sel2), int(sel2.sum())
        res[k] = dict(side=name, first=sel1.mean() * 100, second=(k2 / n2 * 100) if n2 else np.nan, n2=n2,
                      p=binomtest(k2, n2, 0.5, alternative="greater").pvalue if n2 else 1.0)
        qo = P.dropna(subset=[k, "o"])
        if k in CELLS_FLAG:
            h, l = qo[k].astype(bool), ~qo[k].astype(bool)
        else:
            h, l = qo[k] >= qo[k].quantile(2 / 3), qo[k] <= qo[k].quantile(1 / 3)
        a, b = qo.day < mid_day, qo.day >= mid_day
        d1, d2 = qo["o"][h & a].mean() - qo["o"][l & a].mean(), qo["o"][h & b].mean() - qo["o"][l & b].mean()
        same += int(np.sign(d1) == np.sign(d2))
    return P, res, same


def main():
    bars = pd.read_parquet(BARS).sort_values("t")
    B = make_bars(bars.t.to_numpy("int64"), bars.c.to_numpy(float))
    x = pd.read_csv(ROOT / "strategy_analysis" / "statement_trades.csv", parse_dates=["open_time"])
    x = x[x.symbol.str.startswith("NASDAQ")]
    entries, skipped = [], 0
    for r in x.itertuples():
        u = to_utc(r.open_time)
        if u is None:
            skipped += 1
            continue
        entries.append((int(u.tz_localize("UTC").value // 10**6), 1 if r.side == "BUY" else -1))
    kept, pA, desc, rk = stage_a(B, entries, np.random.default_rng(17))
    hA = holm(pA)
    m5 = np.mean([abs(rk[k] - 0.5) for k in CELLS_CONT if k.startswith("5m")])
    m15 = np.mean([abs(rk[k] - 0.5) for k in CELLS_CONT if k.startswith("15m")])
    out = [f"backtest/his_rsi_long.py - {len(CELLS)} cells ({len(CELLS_CONT)} continuous, {len(CELLS_FLAG)} hooks) on 5- and 15-minute candles built from Exness 1-minute bars",
           f"\nSTAGE A - {kept} of his {len(x)} NASDAQ entries usable ({skipped} in the 8-29 March changeover skipped, the rest lacked warm-up) vs ~80 moments within 20 minutes, same direction. Smallest raw p (of {len(CELLS)}):"]
    for k in sorted(pA, key=pA.get)[:8]:
        out.append(f"  {k:<16}{desc[k]:<26} p {pA[k]:.3f}  Holm {hA[k]:.3f}")
    out.append(f"  cells with raw p < 0.05: {sum(v < 0.05 for v in pA.values())} of {len(pA)} (chance alone gives ~{0.05 * len(pA):.1f}); with Holm < 0.05: {sum(v < 0.05 for v in hA.values())}")
    out.append(f"  mean |rank - 0.5| over continuous cells: 5-minute {m5:.3f}, 15-minute {m15:.3f}; cells on the pullback side (rank < 0.5): {sum(rk[k] < 0.5 for k in CELLS_CONT)} of {len(CELLS_CONT)}")

    cache = pickle.loads(TICKS.read_bytes())
    days = [d for d in sorted(cache) if cache[d] is not None]
    P, res, same = stage_b(B, cache, days, np.random.default_rng(23))
    hB = holm({k: v["p"] for k, v in res.items()})
    out.append(f"\nSTAGE B - {len(P)} random moment x direction pairs on {P.day.nunique()} days; NET +7/-7 race, base {P['on'].dropna().mean() * 100:.1f}%, break-even 50%."
               f"\n  extreme chosen on the first half of the days, read on the second:")
    out.append(f"  {'cell':<16}{'chosen':>9}{'1st half':>10}{'2nd half':>10}{'n 2nd':>7}{'p':>8}{'Holm':>7}")
    for k in sorted(res, key=lambda c: res[c]["p"])[:8]:
        v = res[k]
        out.append(f"  {k:<16}{v['side']:>9}{v['first']:>9.1f}%{v['second']:>9.1f}%{v['n2']:>7}{v['p']:>8.3f}{hB[k]:>7.3f}")
    out.append(f"  best second-half net race over all {len(res)} cells: {max(v['second'] for v in res.values() if np.isfinite(v['second'])):.1f}%   cells with Holm < 0.05: {sum(v < 0.05 for v in hB.values())}")
    out.append(f"  mid race (high - low), same sign in both halves: {same} of {len(res)} cells (a coin gives ~{len(res) / 2:.0f})")
    txt = "\n".join(out)
    print(txt)
    (ROOT / "logs" / "his_rsi_long.txt").write_text(txt + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
