"""THE CAPITULATION BUY ON COINS IT HAS NEVER SEEN - the frozen rule, the point-in-time top-40, 2020 .. 2026-09.

rsi_confluence.py --verify found ONE rule that survived bar phases, years and coins on BTC/ETH/SOL/DOGE/XRP:
    4h RSI(14) crosses under 20 AND the bar's volume > 3x its 20-bar average -> buy the next 4h open; +2% limit; out
    at the next open once 24 bars have passed with the close not in profit; 7-day cap. 12bp + funding.
It fires ~13 times a year on those 5 coins. Two questions, one test:
    1. Is it real? It was found in the ~10th sweep of one holdout; coins it was NOT found on are a clean test.
    2. Can it fire more often? More coins = more signals.

THE TEST
    Universe: wide_book.eligibility(40) - the top 40 perps by the PRIOR month's volume, dead coins included (rule 6);
    a coin can open a trade only in a month it is eligible. The 5 coins it was found on are reported SEPARATELY (a
    reproduction from a different data source: 1h perp bars with QUOTE volume, against 15m bars with base volume).
    4h bars built from the 1h perp archive at 4 phases (0 / +1h / +2h / +3h). Funding: every settlement after the entry
    up to the start of the exit bar. Trades counted per coin one at a time; t by DISTINCT DAY (coins crash together).
    LUNA (LUNAUSDT, delisted 2022-05) is shown with and without at the user's request - WITH is the honest number.

REGISTERED BEFORE THE RUN (2026-10-08)
    - On the OTHER coins: win rate 80-90%, average +0.3 to +1.0% a trade (under the majors' ~+1.0-1.6%), positive in at
      least 3 of the 4 phases.
    - 5-10x as many signals as on the 5 majors.
    - Deeper dips inside trades (40-80% at the worst).

RESULT (2026-10-08, logs/capitulation_wide.txt, logs/capitulation_wide_trades.csv)
    - The 5 majors from this data source (quote volume, 4h from 1h): phases 0 / +1h / +2h / +3h -> +1.66 / +1.19 / +0.15 /
      +1.23% a trade (the 15m-built test read +1.61 / +1.00 / +0.91 / +1.30): the +2h phase is SENSITIVE to the data
      source - a fragility the 15m test did not show.
    - OTHER top-40 coins, never seen (101-112 coins, ~44 trades a year, 5.5x the majors): win 85-93%, average
      +1.15 / +0.79 / +0.09 / +1.10% a trade, holdout +1.31 / +0.75 / -0.22 / +1.28%; t by DISTINCT DAY +2.0 / +0.3 /
      -1.3 / +0.5; worst trade -16 to -52%, deepest dip 41-74%. 24 of the 27 coins with 3+ trades positive. Every year
      2020-2026 positive at phase 0 (2023 weakest, +0.29%). LUNA never fired (its eligibility / data stop before the
      collapse), so "without LUNA" is identical.
    - Predictions: win 80-90% (85-93%: about right), +0.3..+1.0% (+0.09..+1.15%: right), >= 3 of 4 phases positive
      (all 4 per trade, 3 of 4 on the holdout: right), 5-10x the signals (5.5x: right), dips 40-80% (41-74%: right).
      Not predicted: the per-DAY t is weak on unseen coins - the per-trade edge is real-looking, the day-to-day
      variance (a few crash days with big losers) is large.
    - 10,000 PKR PER TRADE, all coins, PKR a year by phase: 1x +6,329 / +4,105 / +515 / +5,851; 2x +12,658 / +8,200 /
      -3,563 / +10,168. But signals bunch: 19 trades on the busiest day, 21 days with 5+, so 10,000 PKR PER TRADE is
      up to ~190,000 PKR of margin on a crash day. On 10,000 PKR in total, divide those figures by the positions it
      can hold at once.
    Reading: the rule carries to unseen coins in DIRECTION (92% wins, +0.8 to +1.2% a trade in 3 of 4 phases) but not
    with statistical confidence by day, and one bar phase is flat. A real-looking, modest, crash-dependent edge -
    a forward paper record on the top-40 (~50 signals a year) would answer it in ~6 months.

    python -m backtest.capitulation_wide

RE-RUN 2026-10-09 on the FIXED loader (capitulation_wide.halt_cut): until then a data-archive hole cut 51 coins (XRP, SOL,
    LTC ...) at 2022-02-25. Where a RESULT above differs from this file's log, THE LOG IS CURRENT - doc 02, "The archive-hole bug".
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest.rsi_confluence import outcome  # noqa: E402
from backtest.rsi_factors import prep  # noqa: E402
from backtest.wide_book import eligibility  # noqa: E402

PERPS = ROOT / "strategy_analysis" / "data" / "perps"
LOG = ROOT / "logs" / "capitulation_wide.txt"
MAJORS = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "DOGEUSDT", "XRPUSDT")
PHASES = (0, 60, 120, 180)
CAP = 42                                   # 7 days of 4h bars
HOLDOUT = pd.Timestamp("2024-04-07")
STAKE = 10_000.0


HALT_H = 168


def halt_cut(d):
    """Stop a coin's history at a REAL halt or relisting: a gap of more than 7 days (BNX 2023-02: 21 days, -98% across
    it; TLM 30 days; ICP 26 days). Shorter gaps are holes in the ARCHIVE and are kept: 2022-02-26..28 (73h) and
    2022-04-01..02 (49h) are missing for 47 and 48 coins at once, with prices a few percent apart across them.
    Until 2026-10-09 every gap over 48h was read as a halt, which cut 51 coins - XRP, SOL, LTC, NEAR, FIL, TRX, XLM... -
    at 2022-02-25: 16.4% of all PIT top-40 coin-months were missing from every book built on this loader (CLAUDE.md s3)."""
    gap = d.time.diff().dt.total_seconds().fillna(3600) / 3600
    if (gap > HALT_H).any():
        d = d.iloc[:int(np.argmax(gap.values > HALT_H))].reset_index(drop=True)
    return d


def hourly(sym):
    f = PERPS / f"{sym}_1h.csv.gz"
    if not f.exists():
        return None
    d = pd.read_csv(f, usecols=["time", "open", "high", "low", "close", "qvol"])
    d["time"] = pd.to_datetime(d["time"]).astype("datetime64[ns]")
    d = d[d.close > 0].drop_duplicates("time").sort_values("time", kind="stable").reset_index(drop=True)
    d = halt_cut(d)
    return d if len(d) > 600 else None


def four_hour(h, offset_min):
    g = h.set_index("time").resample("240min", offset=f"{offset_min}min")
    out = pd.DataFrame({"o": g["open"].first(), "h": g["high"].max(), "l": g["low"].min(), "c": g["close"].last(),
                        "v": g["qvol"].sum(), "n": g["close"].count()})
    return out[out.n == 4].drop(columns="n").reset_index()


def funding_cum(sym, times, h):
    """fc[k] = sum of rate x price over settlements at or before bar k's start; outcome() charges fc[j] - fc[i+1]."""
    f = PERPS / f"{sym}_funding.csv.gz"
    if not f.exists():
        return np.zeros(len(times))
    fu = pd.read_csv(f)
    s = pd.to_datetime(fu["time"]).dt.floor("h").astype("datetime64[ns]")
    px = pd.Series(h["open"].to_numpy(float), index=h["time"]).reindex(s.to_numpy(), method="ffill").to_numpy()
    val = np.nan_to_num(fu["rate"].to_numpy(float) * px)
    order = np.argsort(s.to_numpy(), kind="stable")
    st, cum = s.to_numpy()[order], np.r_[0.0, np.cumsum(val[order])]
    k = np.searchsorted(st, np.asarray(times, "datetime64[ns]"), side="right")
    return cum[k]


def run_coin(sym, months, offset, btc_close):
    h = hourly(sym)
    if h is None:
        return []
    d = four_hour(h, offset)
    if len(d) < 300:
        return []
    P = prep(d, btc_close.reindex(d.time).to_numpy(float))
    fc = funding_cum(sym, d.time.to_numpy(), h)
    r, v = P["r"], P["v"]
    vavg = pd.Series(v).rolling(20).mean().shift(1).to_numpy()
    sig = np.r_[False, (r[:-1] >= 20) & (r[1:] < 20)] & (v > 3 * vavg)
    sig[:250] = False
    ym = d.time.dt.strftime("%Y-%m").to_numpy()
    t = d.time.to_numpy()
    out, free = [], 0
    for i in np.flatnonzero(sig):
        if i < free or i + 2 >= len(r) or (months is not None and ym[i] not in months):
            continue
        j, net, worst = outcome(i, 1, "tp2_nw", P, fc, CAP)
        out.append((sym, t[i + 1], net, worst))
        free = j + 1
    return out


def summary(T, label):
    if T.empty:
        return f"  {label}: no trades"
    per_day = T.groupby(T.t.dt.floor("D")).net.mean()
    td = per_day.mean() / (per_day.std(ddof=1) / np.sqrt(len(per_day))) if len(per_day) > 2 else np.nan
    tu, ho = T[T.t < HOLDOUT].net, T[T.t >= HOLDOUT].net
    yrs = len(T.t.dt.year.unique())
    return (f"  {label}: {len(T)} trades ({len(T) / max((T.t.max() - T.t.min()).days / 365, 0.5):.0f} a year) on "
            f"{len(per_day)} days, {T.coin.nunique()} coins, win {np.mean(T.net > 0):.0%}, avg {T.net.mean() * 100:+.2f}%, "
            f"t by day {td:+.1f}, tune {tu.mean() * 100:+.2f}% / holdout {ho.mean() * 100:+.2f}%, worst {T.net.min() * 100:+.1f}%, "
            f"deepest dip {T.worst.max() * 100:.0f}%")


def main():
    t0 = time.time()
    el = eligibility(40)
    btc_h = hourly("BTCUSDT")
    lines = [f"backtest/capitulation_wide.py, {pd.Timestamp.now():%Y-%m-%d %H:%M}; frozen rule, PIT top-40 by prior-month "
             f"volume (dead coins in), 4h bars from 1h perps, 4 phases", ""]
    allT = []
    for off in PHASES:
        btc4 = four_hour(btc_h, off)
        btc_close = pd.Series(btc4.c.to_numpy(float), index=btc4.time)
        rows = []
        for sym, months in el.items():
            if not months:
                continue
            rows += run_coin(sym, None if sym in MAJORS else months, off, btc_close)
        T = pd.DataFrame(rows, columns=["coin", "t", "net", "worst"]).assign(t=lambda x: pd.to_datetime(x.t), phase=off)
        allT.append(T)
        maj, oth = T[T.coin.isin(MAJORS)], T[~T.coin.isin(MAJORS)]
        lines.append(f"PHASE +{off} min")
        lines.append(summary(maj, "the 5 majors (reproduction)"))
        lines.append(summary(oth, "OTHER top-40 coins (never seen)"))
        lines.append(summary(oth[oth.coin != "LUNAUSDT"], "other coins without LUNA"))
        print(f"  phase {off} done ({time.time() - t0:.0f}s)", flush=True)
    A = pd.concat(allT, ignore_index=True)
    A.to_csv(ROOT / "logs" / "capitulation_wide_trades.csv", index=False)
    oth = A[(A.phase == 0) & ~A.coin.isin(MAJORS)]
    lines.append("\nOTHER COINS, phase 0, by year (avg per trade, trades):  " +
                 " ".join(f"{y}: {g.net.mean() * 100:+.2f}% ({len(g)})" for y, g in oth.groupby(oth.t.dt.year)))
    lines.append("worst 8 trades on the other coins, phase 0: " +
                 ", ".join(f"{r.coin[:-4]} {r.t:%Y-%m-%d} {r.net * 100:+.0f}%" for r in oth.nsmallest(8, "net").itertuples()))
    per_coin = oth.groupby("coin").net.agg(["count", "mean"])
    lines.append(f"coins with 3+ trades: {int((per_coin['count'] >= 3).sum())}, of which positive on average: "
                 f"{int(((per_coin['count'] >= 3) & (per_coin['mean'] > 0)).sum())}")
    lines.append("\n10,000 PKR, fixed per trade (not compounded), phase 0, everything that fired on the PIT top-40 (all coins):")
    al = A[A.phase == 0].sort_values("t", kind="stable")
    for lev in (1, 2, 3, 5):
        liq = 1 / lev - 0.005 - 0.0006
        pnl = np.where(al.worst >= liq, -1.0, np.maximum(lev * al.net, -1.0)) * STAKE
        yrs = (al.t.max() - al.t.min()).days / 365
        lines.append(f"  {lev}x: {len(al)} trades over {yrs:.1f} years, total {pnl.sum():+,.0f} PKR ({pnl.sum() / yrs:+,.0f} a year), "
                     f"liquidated {int((al.worst >= liq).sum())}x, worst trade {pnl.min():+,.0f} PKR")
    txt = "\n".join(lines)
    print(txt)
    LOG.write_text(txt + "\n")
    print(f"\n-> {LOG} ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
