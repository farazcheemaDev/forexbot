"""HOW HE ACCOUNTS FOR LOSSES: his losing trades one by one, the shape of all his outcomes, and the gold spree (2026-11-03)

The user, 2026-11-03: "yes do it also" (examine his losses) after: "pattern recognition - how does he account for losses". Descriptive, not a test: he has only 2 losing NASDAQ trades and 11 gold ones.
EXPLORATORY LOOK FIRST (before this script was written, so NOT predictions): the statement shows 37 of his 41 gold trades are ONE sitting (2026-02-02, 09:51-10:39 statement time, holds of 4-36 s) and that 17 of his 46
NASDAQ trades closed short of +6.5 points, 15 of them as small wins.

REGISTERED BEFORE THE FIRST RUN OF THIS SCRIPT (2026-11-03; they concern the market context at each trade, which had not been looked at)
    P1  Both NASDAQ losers were entered after a move in his own direction larger than the median winner's over the previous 5 / 30 minutes (chasing; his_strategy s64: his lost races were fast, chased moments).
    P2  The gold spree day's range is at least 3x the median daily range of gold since January (the spree was a violent market, not a style).
    P3  The 10-second -7.5 NASDAQ loss and the 48-minute -31.75 one are NOT alike: one is a deliberate quick cut (held under a minute), the other is waiting (held for most of an hour).

CONTEXT per trade, from Exness 1-minute bars (USTECm / XAUUSDm; strategy_analysis/data/mt5_1m), the statement clock converted with his_rsi_long.to_utc (UTC+4 before 2026-03-08, UTC+5 from 03-29; trades in the
changeover weeks are skipped): the move in his direction over the 5 / 30 / 120 minutes before entry (index points), where the price sat in the day's range so far (0 = at the low for a buy / at the high for a sell = the
'cheap' end), how wild the last hour was against the same clock time on the 20 days before (percentile of the mean 1-minute range), the worst and best price during the hold, and the next 60 minutes after he got out.

RESULT (2026-11-03; logs/his_losers.txt)
    A. 21 of his 46 NASDAQ trades finished above +7.5 points and make 83% of the profit; the 14 above +12 make 54%. 17 closed short of +6.5, and 15 of those were small WINS (median hold 82 s): that is how a 95.7% win
       rate is built - a stalled trade is taken out at whatever green it has. Two real losses: -7.50 (10 s) and -31.75 (48 min).
    B. P1 WRONG: neither loser was a chase of a recent move. 2026-02-04 (-7.5, cut in 10 s): bought a bounce (+7.3 in 5 min) inside a 2-hour fall of -102.6 points, near the low of the last 6.5 hours (range position 0.14),
       in a wild hour (86th percentile); the market then fell another 56 points. 2026-09-14 (-31.75, held 48 min): bought a 5-minute dip (-8.0) after a +123.5-point two-hour run, at the EXPENSIVE end of the range (0.94,
       88th percentile among his winners); the market then fell another 94 points. Both were pullback buys in a trend that turned; both BUYS. P3 RIGHT (a deliberate 10-second cut vs waiting for most of an hour).
    C. P2 RIGHT: 37 of his 41 gold trades are ONE 48-minute sitting on 2026-02-02 (gold's range that day 483 points = 5.4x its median, the 99th percentile): 26 won / 11 lost, net +$74, median hold 7 s, average winner
       +3.47 points against an average loser -8.38 - a high win rate that earns roughly nothing, the same shape as the exit-shape study. No tilt (longest losing run 2). The other 4 gold trades all won.

    python -m backtest.his_losers        writes logs/his_losers.txt          tests: python tests/test_his_losers.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest.his_rsi_long import to_utc  # noqa: E402

BARS = ROOT / "strategy_analysis" / "data" / "mt5_1m"
EDGES = [-1e9, -0.01, 1.5, 3.5, 6.5, 7.5, 12, 1e9]
LABELS = ["loss", "0..1.5 scratch", "1.5..3.5 small", "3.5..6.5 short of target", "6.5..7.5 = the +7", "7.5..12", ">12"]


def load_trades():
    x = pd.read_csv(ROOT / "strategy_analysis" / "statement_trades.csv", parse_dates=["open_time", "close_time"])
    x["s"] = x.side.map({"BUY": 1, "SELL": -1})
    x["pts"] = (x.close_price - x.open_price) * x.s
    x["hold_s"] = (x.close_time - x.open_time).dt.total_seconds()
    x["fam"] = np.where(x.symbol.str.startswith("NASDAQ"), "NASDAQ", x.symbol)
    return x


def outcome_buckets(n: pd.DataFrame) -> pd.DataFrame:
    b = pd.cut(n.pts, EDGES, labels=LABELS)
    t = n.groupby(b, observed=False).agg(n=("pts", "size"), hold_median_s=("hold_s", "median"), net=("net", "sum"))
    t["share_of_profit"] = t.net / n.net.sum() * 100
    return t


def percentile_among(v: float, ref) -> float:
    ref = np.asarray([r for r in ref if np.isfinite(r)], float)
    return float("nan") if len(ref) == 0 else float((ref < v).mean() + 0.5 * (ref == v).mean()) * 100


def context(bars: pd.DataFrame, t0_ms: int, s: int, hold_s: float, range_bars: int = 390, days_back: int = 20):
    """Market context at an entry (see the docstring). `bars`: t (ms, minute open), o h l c, sorted. Only bars closed before the entry's minute are used for the 'before' numbers;
    'cheapness' is where the price sat in the range of the previous `range_bars` minute bars (6.5 hours: a cash session's length, valid at any hour of his day)."""
    T, C, H, L = bars.t.to_numpy("int64"), bars.c.to_numpy(float), bars.h.to_numpy(float), bars.l.to_numpy(float)
    i = int(np.searchsorted(T, t0_ms, side="right")) - 1                       # the bar that contains the entry
    if i < range_bars + 5 or T[i] + 60_000 <= t0_ms:
        return None
    p0 = C[i - 1]
    mv = {k: s * (p0 - C[i - 1 - k]) for k in (5, 30, 120)}
    lo, hi = L[i - range_bars:i].min(), H[i - range_bars:i].max()
    pos = (p0 - lo) / (hi - lo) if hi > lo else 0.5
    cheap = pos if s == 1 else 1 - pos
    wild = np.mean(H[i - 60:i] - L[i - 60:i])
    past = []
    for d in range(1, days_back + 1):
        k = int(np.searchsorted(T, t0_ms - d * 86_400_000, side="right")) - 1
        if k >= 60 and abs(T[k] - (t0_ms - d * 86_400_000)) < 120_000:
            past.append(np.mean(H[k - 60:k] - L[k - 60:k]))
    k_exit = int(np.searchsorted(T, t0_ms + hold_s * 1000, side="right")) - 1
    during = slice(i, max(i, k_exit) + 1)
    out = dict(mv5=mv[5], mv30=mv[30], mv120=mv[120], cheap=cheap, wild_pct=percentile_among(wild, past),
               mae=s * (L[during].min() - p0) if s == 1 else s * (H[during].max() - p0),
               mfe=s * (H[during].max() - p0) if s == 1 else s * (L[during].min() - p0))
    out["after60"] = s * (C[min(k_exit + 60, len(C) - 1)] - C[k_exit]) if k_exit + 60 < len(C) else float("nan")
    return out


def contexts_for(x: pd.DataFrame, fam: str, sym: str):
    bars = pd.read_parquet(BARS / f"{sym}.parquet").sort_values("t").reset_index(drop=True)
    rows = []
    for r in x[x.fam == fam].itertuples():
        u = to_utc(r.open_time)
        if u is None:
            rows.append(None)
            continue
        u = u.tz_localize("UTC")
        rows.append(context(bars, int(u.value // 10**6), r.s, r.hold_s))
    return rows, bars


def main():
    x = load_trades()
    n = x[x.fam == "NASDAQ"].sort_values("open_time").reset_index(drop=True)
    out = [f"backtest/his_losers.py - {len(x)} statement trades: NASDAQ {len(n)}, gold {int((x.fam == 'GOLD').sum())}, silver {int((x.fam == 'SILVER').sum())}",
           "\nA. THE SHAPE OF ALL HIS NASDAQ OUTCOMES (points a trade, his own broker prices):", outcome_buckets(n).round(1).to_string()]
    short = n[n.pts < 6.5]
    out.append(f"   closed short of +6.5: {len(short)} of {len(n)}; of them {(short.pts > 0).sum()} were small WINS (median hold {short[short.pts > 0].hold_s.median():.0f} s) and {(short.pts <= 0).sum()} losses; "
               f"trades above +7.5: {(n.pts > 7.5).sum()}, making {n[n.pts > 7.5].net.sum() / n.net.sum() * 100:.0f}% of the profit; the biggest 14 (> +12) make {n[n.pts > 12].net.sum() / n.net.sum() * 100:.0f}%")
    rows, bars_n = contexts_for(x.sort_values("open_time").reset_index(drop=True), "NASDAQ", "USTECm")
    n["ctx"] = rows
    ok = n[n.ctx.notna()]
    W = pd.DataFrame(list(ok[ok.pts > 0].ctx))
    out.append(f"\nB. HIS NASDAQ LOSERS IN CONTEXT ({int(n.ctx.isna().sum())} trades without usable context: changeover weeks or too little history); winners n = {len(W)}; 'pct' = the loser's percentile among the winners")
    out.append(f"   winners' median: move in his direction 5 min {W.mv5.median():+.1f} / 30 min {W.mv30.median():+.1f} / 120 min {W.mv120.median():+.1f} pts; range position {W.cheap.median():.2f} (0 = bought at the cheap end of the last 6.5 hours, 1 = at the expensive end); wildness percentile {W.wild_pct.median():.0f}; worst price during the hold {W.mae.median():+.1f}")
    for r in ok[ok.pts <= 0].itertuples():
        c = r.ctx
        out.append(f"   {r.open_time:%Y-%m-%d %H:%M:%S} {r.side} {r.lots} lot  {r.pts:+.2f} pts  held {r.hold_s:.0f} s (${r.net:+.2f})")
        out.append(f"      before entry: {c['mv5']:+.1f} / {c['mv30']:+.1f} / {c['mv120']:+.1f} pts in his direction over 5 / 30 / 120 min (winners' percentile {percentile_among(c['mv5'], W.mv5):.0f} / {percentile_among(c['mv30'], W.mv30):.0f} / {percentile_among(c['mv120'], W.mv120):.0f}); "
                   f"range position {c['cheap']:.2f} (0 = cheap end, 1 = expensive end; pct {percentile_among(c['cheap'], W.cheap):.0f}); hour wildness {c['wild_pct']:.0f}th pct")
        out.append(f"      during the hold: worst {c['mae']:+.1f}, best {c['mfe']:+.1f} pts (index bars); the 60 minutes after he got out moved {c['after60']:+.1f} in his direction")
    g = x[x.fam == "GOLD"].sort_values("open_time").reset_index(drop=True)
    spree = g[g.open_time.dt.date == pd.Timestamp("2026-02-02").date()]
    out.append(f"\nC. GOLD: {len(spree)} of {len(g)} trades are the sitting of 2026-02-02 ({spree.open_time.min():%H:%M:%S}-{spree.open_time.max():%H:%M:%S}, {(spree.open_time.max() - spree.open_time.min()).total_seconds() / 60:.0f} minutes); "
               f"{int((spree.net > 0).sum())} won / {int((spree.net <= 0).sum())} lost, net ${spree.net.sum():+.0f}, median hold {spree.hold_s.median():.0f} s, average winner {spree[spree.net > 0].pts.mean():+.2f} pts / average loser {spree[spree.net <= 0].pts.mean():+.2f} pts; "
               f"the other {len(g) - len(spree)} gold trades: {int((g.drop(spree.index).net > 0).sum())} won")
    gb = pd.read_parquet(BARS / "XAUUSDm.parquet").sort_values("t")
    day = pd.to_datetime(gb.t, unit="ms").dt.normalize()
    rng = gb.groupby(day).agg(h=("h", "max"), l=("l", "min"))
    rng = (rng.h - rng.l)
    d0 = pd.Timestamp("2026-02-02")
    out.append(f"   gold's range that day {rng.get(d0, float('nan')):.0f} points against a median daily range of {rng.median():.0f} since January ({rng.get(d0, float('nan')) / rng.median():.1f}x; rank {percentile_among(rng.get(d0, float('nan')), rng.to_numpy()):.0f}th percentile)")
    seq = "".join("W" if v > 0 else "L" for v in spree.net)
    out.append(f"   the sitting in order (W win / L loss): {seq}; losses are followed by a win {sum(1 for a, b in zip(seq, seq[1:]) if a == 'L' and b == 'W')} of {seq.count('L') - (seq[-1] == 'L')} times; the longest losing run is {max(len(s) for s in seq.split('W'))}")
    txt = "\n".join(out)
    print(txt)
    (ROOT / "logs" / "his_losers.txt").write_text(txt + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
