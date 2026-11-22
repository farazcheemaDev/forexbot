"""HIS FLIP PAIRS: WHAT CHANGED BETWEEN A BUY AND A SELL MINUTES APART? (2026-11-21)

THE USER (2026-11-21), after his_volume15.py: "that does narrow down" - the observation that he often buys and sells within minutes and
wins both (02-20, 04-06, 06-05, 08-07, 09-14, 10-08). A flip pair is a natural experiment: the same day, the same market, the same
volume and news, minutes apart - yet his side flips. Whatever sets his side must have FLIPPED between the two clicks. Earlier work
asked whether he alternates (his_strategy s50: 'not a two-sided range scalper', switches 33%) and ranked his moments against nearby
ones on 75 features (s33: ordinary), but never asked which feature flips WITH him inside a pair.
DATA   his NASDAQ trades (his_noise.his_trades: statement with its corrected clock + the later ones); CME NQ front 1-minute bars
       (Databento, strategy_analysis/data/nq_1m/NQ_2026.parquet, the price his broker's futures CFD tracks); closed bars only at each
       click (he clicks ~14 s after a minute's close).
PAIRS  consecutive trades on the same day, opposite sides, at most 10 minutes apart.
FEATURES (each with a 'buy-ish' reading)  range position of the last close in the high-low of the last 3 / 5 / 10 / 15 / 30 / 60 closed
       minutes (< 0.5 = buy-ish: low in the range); the last 1 / 2 / 5-minute move (< 0 = buy-ish if he FADES); the last close against the
       session VWAP from 09:30 New York (below = buy-ish) and against the 20-minute average (below = buy-ish); the 1-minute RSI(14)
       (< 50 = buy-ish). A pair is CONSISTENT with a feature as FADE if the feature is buy-ish at his buy and sell-ish at his sell, as
       FOLLOW if the reverse.
THEN   any feature consistent in all pairs (or all but one) is read on his OTHER trades (not in a pair): his side vs the feature's side,
       binomial against 50%.
REGISTERED BEFORE THE FIRST NUMBER (2026-11-21)
  P1  No feature is consistent (in either orientation) in every pair. (65%)
  P2  Any feature consistent in all pairs or all but one matches his side on 40-62% of his other trades (p > 0.05): what flips inside a
      handful of pairs does not carry. (80%)

RESULT (2026-11-21, logs/his_flip_pairs.txt): 6 flip pairs (02-20, 04-06, 06-05, 08-07, 09-14, 10-08; 0.5 to 7.9 minutes apart). No feature
  flips with him in every pair. The best - range position over the last 3 / 5 / 10 minutes and the last 2-minute move - fit 3 of 6 as a
  FADE (buy low in the recent range, sell high), never as a follow; the same lean s55 found (a style, -1.9 points a trade as a rule).
  In the other pairs the 1-minute chart read the SAME at his buy and his sell - and two pairs flipped within 27 and 39 seconds, inside
  one candle. Whatever flips him moves faster than the 1-minute chart. P1 right, P2 right (no feature qualified).
  ALL TRADES (added 2026-11-22): he trades OPPOSITE to the recent range position on 38-48% of his 50 trades (3-60 minute ranges, every
  p >= 0.12) and wins 91-96% when he does, 96-100% when he does not: 'nearer the level behind him' (s55) is entry timing, not his side.

    python -m backtest.his_flip_pairs
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
LOG = ROOT / "logs" / "his_flip_pairs.txt"
RANGES = (3, 5, 10, 15, 30, 60)
MOVES = (1, 2, 5)


def nq() -> pd.DataFrame:
    d = pd.read_parquet(ROOT / "strategy_analysis" / "data" / "nq_1m" / "NQ_2026.parquet")
    d = d.sort_values(["ts_event", "volume"]).drop_duplicates("ts_event", keep="last")
    t = pd.to_datetime(d.ts_event, utc=True).dt.tz_convert("America/New_York").dt.tz_localize(None)
    return pd.DataFrame({"o": d.open.to_numpy(), "h": d.high.to_numpy(), "l": d.low.to_numpy(), "c": d.close.to_numpy(),
                         "v": d.volume.to_numpy(float)}, index=pd.DatetimeIndex(t)).sort_index()


def rsi(c: np.ndarray, n: int = 14) -> float:
    d = np.diff(c)
    if len(d) < n + 5:
        return np.nan
    up = pd.Series(np.clip(d, 0, None)).ewm(alpha=1 / n, adjust=False).mean().iloc[-1]
    dn = pd.Series(np.clip(-d, 0, None)).ewm(alpha=1 / n, adjust=False).mean().iloc[-1]
    return float(100 - 100 / (1 + up / dn)) if dn > 0 else 100.0


def features(m: pd.DataFrame, t: pd.Timestamp) -> dict | None:
    """Signed 'buy-ish' readings at a click: +1 buy-ish, -1 sell-ish, 0 neutral (closed bars only)."""
    last = t.floor("min") - pd.Timedelta(minutes=1)
    hist = m[m.index <= last].tail(400)
    if len(hist) < 70 or hist.index[-1] != last:
        return None
    c = hist.c.to_numpy()
    f = {}
    for n in RANGES:
        w = hist.tail(n)
        hi, lo = w.h.max(), w.l.min()
        pos = (c[-1] - lo) / (hi - lo) if hi > lo else 0.5
        f[f"range_{n}m"] = 1 if pos < 0.5 else (-1 if pos > 0.5 else 0)
    for n in MOVES:
        mv = c[-1] - c[-1 - n]
        f[f"move_{n}m"] = 1 if mv < 0 else (-1 if mv > 0 else 0)          # buy-ish = the last n minutes fell (a FADE reading)
    day = hist[hist.index >= last.normalize() + pd.Timedelta(hours=9, minutes=30)]
    if len(day) >= 5:
        vwap = float((day.c * day.v).sum() / day.v.sum()) if day.v.sum() > 0 else np.nan
        f["vwap"] = 1 if c[-1] < vwap else (-1 if c[-1] > vwap else 0)
    else:
        f["vwap"] = 0
    ma = c[-20:].mean()
    f["ma20"] = 1 if c[-1] < ma else (-1 if c[-1] > ma else 0)
    r = rsi(c[-120:])
    f["rsi14"] = 1 if r < 50 else (-1 if r > 50 else 0)
    return f


def main():
    from scipy.stats import binomtest
    from backtest.his_noise import his_trades
    m = nq()
    T = his_trades()
    rows = []
    for r in T.itertuples():
        f = features(m, r.et)
        if f is not None:
            rows.append(dict(et=r.et, side=r.side, pts=r.pts, **f))
    X = pd.DataFrame(rows).sort_values("et").reset_index(drop=True)
    feats = [c for c in X.columns if c not in ("et", "side", "pts")]
    pairs = []
    for i in range(len(X) - 1):
        a, b = X.iloc[i], X.iloc[i + 1]
        if a.et.normalize() == b.et.normalize() and a.side != b.side and (b.et - a.et) <= pd.Timedelta(minutes=10):
            buy, sell = (a, b) if a.side > 0 else (b, a)
            pairs.append((buy, sell))
    in_pair = {p[0].et for p in pairs} | {p[1].et for p in pairs}
    out = [f"backtest/his_flip_pairs.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; his NASDAQ trades {len(T)}, with NQ minute data "
           f"{len(X)}; flip pairs (same day, opposite sides, <= 10 minutes apart): {len(pairs)}", ""]
    for buy, sell in pairs:
        out.append(f"  pair {min(buy.et, sell.et):%Y-%m-%d %H:%M:%S} -> {max(buy.et, sell.et):%H:%M:%S}  "
                   f"({abs((sell.et - buy.et).total_seconds()) / 60:.1f} min; buy {buy.pts:+.2f}, sell {sell.pts:+.2f})")
    out += ["", f"  {'feature':<10}{'FADE-consistent pairs':>24}{'FOLLOW-consistent pairs':>26}   reading at the BUY / at the SELL in each pair"]
    best = {}
    for f in feats:
        fade = sum(1 for b, s in pairs if b[f] > 0 and s[f] < 0)
        follow = sum(1 for b, s in pairs if b[f] < 0 and s[f] > 0)
        best[f] = (fade, follow)
        out.append(f"  {f:<10}{fade:>17} of {len(pairs)}{follow:>19} of {len(pairs)}   "
                   + "  ".join(f"{int(b[f]):+d}/{int(s[f]):+d}" for b, s in pairs))
    others = X[~X.et.isin(in_pair)]
    out += ["", f"  CARRY-OVER to his {len(others)} trades outside the pairs (only for features consistent in all pairs or all but one):"]
    carried = {}
    for f, (fade, follow) in best.items():
        for orient, k in (("fade", fade), ("follow", follow)):
            if pairs and k >= len(pairs) - 1:
                sgn = 1 if orient == "fade" else -1
                x = others[others[f] != 0]
                agree = int((x.side == sgn * x[f]).sum())
                p = binomtest(agree, len(x), 0.5).pvalue if len(x) else np.nan
                carried[(f, orient)] = (agree, len(x), p)
                out.append(f"    {f} as {orient.upper()}: his side matches on {agree} of {len(x)} ({agree / max(len(x), 1):.0%}), binomial p {p:.3f}")
    if not carried:
        out.append("    none qualifies")
    # ALL TRADES (added 2026-11-22, the user: "closer to a recent high or low - opposite directions?"): his side vs 'trade opposite to the
    # range position' (buy in the lower half of the recent range, sell in the upper half) on every trade, not just the pairs
    out += ["", "  ALL TRADES: his side = the OPPOSITE of the recent range position (buy in its lower half, sell in its upper half)"]
    for n in RANGES:
        c = f"range_{n}m"
        x = X[X[c] != 0]
        k = int((x.side == x[c]).sum())
        a, b = x[x.side == x[c]], x[x.side != x[c]]
        out.append(f"    last {n:>2} min: {k} of {len(x)} ({k / max(len(x), 1):.0%}), p {binomtest(k, len(x), 0.5).pvalue:.2f}; won when opposite "
                   f"{(a.pts > 0).mean():.0%} ({a.pts.mean():+.1f} pts), when the same way {(b.pts > 0).mean():.0%} ({b.pts.mean():+.1f} pts)")
    allp = any(k == len(pairs) for fa, fo in best.values() for k in (fa, fo)) if pairs else False
    ok = lambda b: "RIGHT" if b else "WRONG"  # noqa: E731
    out += ["", "REGISTERED PREDICTIONS",
            f"  P1 no feature consistent in every pair -> {ok(not allp)}",
            f"  P2 qualifying features match 40-62% on his other trades, p > 0.05 -> "
            f"{ok(all(0.40 <= a / max(n, 1) <= 0.62 and p > 0.05 for a, n, p in carried.values()))}"
            + (" (none qualified)" if not carried else "")]
    txt = "\n".join(out)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
