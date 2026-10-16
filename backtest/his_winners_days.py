"""TWO ANGLES NEVER LOOKED AT: his losing races vs his winning ones, and the days he chooses to trade (2026-10-15)

TEST 1   Every earlier test compared him with the market. This compares him with HIMSELF: at the second of each NASDAQ
         entry (corrected clock, Exness ticks, ustec_burst_anatomy.day_frame features + his own sitting), do the entries
         that LOST the +-7 race differ from the ones that won? Features: hour, minute, second of the minute, quote rate and
         movement over 30 / 300 s, the move over the last 5 / 60 / 300 s signed his way (the pullback), position in the last
         60 s range, the day's movement so far, spread, his trade number in the sitting, seconds since his previous trade.
         Mann-Whitney per feature, Holm over the set.
TEST 2   He trades "when free" - on ~30 days. Are those days unusual? NASDAQ-100 cash session (HistData NSXUSD 1m, New
         York 09:30-16:00) on his NASDAQ days vs the other weekdays of 2026-01..09: range, |open-close|, trend efficiency
         (|close - open| / range), overnight gap, first-hour range, the previous day's range.

REGISTERED BEFORE THE RUN (2026-10-15)
    1. Test 1: no feature separates losers from winners after Holm (5 losers - only a very large difference could show).
    2. Test 2: his days are ordinary on every measure (Mann-Whitney p > 0.05); if any differs it is volatility (range),
       since a 7-point race resolves faster on a wide day.

RESULT (2026-10-15, logs/his_winners_days.txt) - both predictions right; nothing survives Holm, but a consistent picture.
    Test 1 (36 won / 5 lost): his LOSERS came in fast, already-moving markets and he was chasing - quote rate over 300 s
      3,411 vs 2,140 (p 0.04), movement over 30 / 300 s 1.6-1.8x (p 0.03), the market already +44 points his way over 5
      minutes (winners +0.8, p 0.04) and +5.4 in the last 5 s (winners -0.02), at the top of the last minute's range
      (0.91 vs 0.34). His WINNERS: calm, the market flat or slightly against him, mid-range - the pullback entry. Lowest
      Holm 0.40 on 5 losers: a description of his good trades, not a rule.
    Test 2 (30 days vs 162): his days lean to TRENDING days - |open-close| 0.71% vs 0.53% (p 0.11), close-to-range
      efficiency 0.56 vs 0.45 (p 0.06), gap 0.76% vs 0.53% (p 0.13); range itself the same (1.35% vs 1.27%, p 0.44).

    python -m backtest.his_winners_days
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import backtest.his_tape as TP  # noqa: E402
from backtest.his_race_curve import race2  # noqa: E402
from backtest.ustec_burst_anatomy import day_frame  # noqa: E402

LOG = ROOT / "logs" / "his_winners_days.txt"


def holm(ps):
    order = np.argsort(ps)
    out, run = np.empty(len(ps)), 0.0
    for k, i in enumerate(order):
        run = max(run, min(1.0, (len(ps) - k) * ps[i]))
        out[i] = run
    return out


def main():
    from scipy.stats import mannwhitneyu
    x = TP.entries()
    ticks = pickle.loads(TP.TICKS.read_bytes())
    rows, frames = [], {}
    for r in x.itertuples():
        day = ticks.get(r.d)
        if day is None or r.t < 330:
            continue
        ts, mid, _ = day
        won = race2(ts, mid, r.t, r.s, 600, 7, 7)
        if won is None:
            continue
        if r.d not in frames:
            frames[r.d] = day_frame(*day)
        F, (g, gm, gsp) = frames[r.d]
        i = int(np.searchsorted(g, r.t, "right") - 1)
        if i < 0 or i >= len(F):
            continue
        f = F.iloc[i]
        w = gm[max(i - 60, 0):i + 1]
        same = x[(x.d == r.d) & (x.t < r.t)]
        rows.append(dict(won=won, hour=f.hour, minute=f.minute, sec=f.sec, qr30=f.qr30, qr300=f.qr300, av30=f.av30,
                         av300=f.av300, pull5=r.s * f.r5, mv60=r.s * f.r60, mv300=r.s * f.r300,
                         pos60=(gm[i] - w.min()) / max(w.max() - w.min(), 1e-9) if r.s > 0 else (w.max() - gm[i]) / max(w.max() - w.min(), 1e-9),
                         dayvol=f.dayvol, spread=f.sp_rel, nth=len(same) + 1,
                         since_prev=(r.t - same.t.max()) if len(same) else np.nan))
    D = pd.DataFrame(rows)
    W, L = D[D.won == 1], D[D.won == 0]
    out = [f"backtest/his_winners_days.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC", "",
           f"TEST 1 - his {len(W)} winning vs {len(L)} losing +-7 races, at the second of entry (medians)"]
    feats = [c for c in D.columns if c != "won"]
    ps = []
    for c in feats:
        a, b = W[c].dropna(), L[c].dropna()
        p = mannwhitneyu(a, b).pvalue if len(a) > 2 and len(b) > 1 else np.nan
        ps.append(p if np.isfinite(p) else 1.0)
    hp = holm(np.array(ps))
    for c, p, h in zip(feats, ps, hp):
        out.append(f"   {c:<11} winners {W[c].median():>9.2f} | losers {L[c].median():>9.2f} "
                   f"(losers: {', '.join(f'{v:.1f}' for v in L[c].dropna())}) | p {p:.3f}, Holm {h:.2f}")
    out.append("")

    # TEST 2
    from backtest.histdata_1m import load
    m = load("NSXUSD")
    ny = pd.to_datetime(m.t, unit="ms", utc=True).dt.tz_convert("America/New_York").dt.tz_localize(None)
    m = m.assign(ny=ny)
    m = m[(m.ny >= "2025-12-01") & (m.ny < "2026-10-01")]
    tod = m.ny.dt.hour * 60 + m.ny.dt.minute
    cash = m[(tod >= 570) & (tod < 960)]
    dd = cash.groupby(cash.ny.dt.normalize()).agg(o=("o", "first"), h=("h", "max"), l=("l", "min"), c=("c", "last"))
    first = cash[(cash.ny.dt.hour * 60 + cash.ny.dt.minute) < 630].groupby(cash.ny.dt.normalize()).agg(fh=("h", "max"), fl=("l", "min"))
    dd = dd.join(first)
    dd["range"] = (dd.h - dd.l) / dd.o * 100
    dd["absmove"] = (dd.c - dd.o).abs() / dd.o * 100
    dd["trend_eff"] = (dd.c - dd.o).abs() / (dd.h - dd.l)
    dd["gap"] = (dd.o - dd.c.shift(1)).abs() / dd.o * 100
    dd["first_hour"] = (dd.fh - dd.fl) / dd.o * 100
    dd["prev_range"] = dd.range.shift(1)
    dd = dd[dd.index >= "2026-01-01"]
    his_days = set(pd.to_datetime(x.d).dt.normalize())
    dd["his"] = dd.index.isin(his_days)
    out.append(f"TEST 2 - his {int(dd.his.sum())} NASDAQ days vs {int((~dd.his).sum())} other weekdays, 2026-01..09 (cash session; % of price)")
    ps2 = []
    for c in ("range", "absmove", "trend_eff", "gap", "first_hour", "prev_range"):
        a, b = dd[dd.his][c].dropna(), dd[~dd.his][c].dropna()
        p = mannwhitneyu(a, b).pvalue
        ps2.append(p)
        out.append(f"   {c:<11} his days median {a.median():.3f} | other days {b.median():.3f} | p {p:.3f}")
    out.append("")
    hp1 = min(hp)
    out += ["REGISTERED PREDICTIONS",
            f"  1 no feature separates losers after Holm: min Holm {hp1:.2f} -> {'RIGHT' if hp1 >= 0.05 else 'WRONG'}",
            f"  2 his days ordinary on every measure: min p {min(ps2):.3f} -> {'RIGHT' if min(ps2) > 0.05 else 'WRONG'}"]
    txt = "\n".join(out)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
