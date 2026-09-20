"""CROWD POSITIONING AS A PORTFOLIO — the portfolio test FIRST this time.

    python -m backtest.crowd_ls

THE LESSON THIS FILE IS BUILT AROUND
    backtest/positioning.py found a quintile spread on taker flow that survived Holm
    correction (p=0.002), held out of sample with a LARGER effect, and had 10 of 11
    coins agreeing in sign. backtest/taker_ls.py then turned it into a book and it lost
    money GROSS OF ALL FEES, in three separate constructions. The spread was measured on
    an hourly grid with 4-hour forward returns, so every observation overlapped the next
    three and there were far fewer independent episodes than rows.

    `crowd` was the other lead from that run: +0.377% at 24h with 9 of 11 coins
    agreeing, failing Holm at 0.273. Under this project's rules it was discarded. So
    this file does not re-measure the spread. It goes straight to the only question
    that matters: DOES A BOOK BUILT ON IT MAKE MONEY, GROSS, ON A NON-OVERLAPPING GRID?

    If gross is negative, nothing else about it is worth computing.

THE STRATEGY
    count_long_short_ratio is the share of all Binance accounts that are long. Tested
    CONTRARIAN, which is the standard claim: when the crowd is heavily long, go short.

    Each coin is ranked against its OWN trailing 90 days - not against other coins,
    because coins have different baseline retail mixes and a cross-sectional rank is
    then mostly a ranking of coin identity. Long the coins in their own bottom quintile
    (crowd least long), short those in their own top quintile.

    Non-overlapping 12-hour and 24-hour grids, because that is where the effect was
    seen and because longer holds mean lower turnover, which is the only way a small
    per-period edge survives fees.

WHY THIS SHAPE SUITS THE STATED GOAL
    The goal is maximum return on minimum capital. A position-sized book with no stop
    has a capital floor equal to the minimum orders of its open positions - measured at
    ~$8 for six positions on MEXC, against the deployed blend's $377, because
    `min_order x stop_fraction / risk` is a ~40x amplifier that this book never enters.
    So IF the gross edge exists, this is the right shape for $10-20. If it does not,
    the shape is irrelevant.

REGISTERED PREDICTION (2026-09-20, before running)
    Gross will be near zero and most likely negative, for the same reason taker's was:
    the 24h spread was measured with 24x overlap on an hourly grid, and the overlap is
    what made it look consistent. Retail-contrarian is also the single most widely
    traded sentiment idea in crypto, so a real edge surviving in free, public,
    5-minutely data would be surprising.

    If gross IS positive at 24h, the deciding number is the net at 12bp, because
    turnover at a 24h hold should be low enough that fees do not automatically kill it.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import blend  # noqa: E402
from backtest.positioning import causal_quintile, load_bars, load_metrics  # noqa: E402
from backtest.timeframes import MIN_ORDER  # noqa: E402

FEATURE = "count_long_short_ratio"
CONTRARIAN = True                 # long the bottom quintile, short the top
HOLDS = (12, 24)
WIN_D = 90
FEES = (0.0, 3.0, 9.0, 12.0)


def panel(hold_h):
    px, ft = {}, {}
    for c in blend.BOOK:
        m, p = load_metrics(c), load_bars(c)
        if m is None or p is None or FEATURE not in m:
            continue
        j = pd.DataFrame({"px": p}).join(m[[FEATURE]], how="inner").dropna()
        if len(j) < 24 * 200:
            continue
        g = j.resample(f"{hold_h}h").last().dropna()
        px[c], ft[c] = g.px, g[FEATURE]
    return pd.DataFrame(px).dropna(how="all"), pd.DataFrame(ft).dropna(how="all")


def run(PX, FT, hold_h, fee_bp, neutral=False, t_from=None, t_to=None):
    win_p = max(int(WIN_D * 24 / hold_h), 30)
    Q = pd.DataFrame({c: causal_quintile(FT[c].dropna(), win_p)
                      for c in FT.columns}).reindex(FT.index)
    ret = PX.pct_change().shift(-1)
    idx = PX.index
    if t_from is not None:
        idx = idx[idx >= t_from]
    if t_to is not None:
        idx = idx[idx < t_to]
    one_way = fee_bp / 2.0 / 1e4
    sign = -1.0 if CONTRARIAN else 1.0
    w_prev = pd.Series(0.0, index=PX.columns)
    eq, curve, times, turns, gr = 1.0, [], [], [], []
    for t in idx:
        q = Q.loc[t].dropna()
        r = ret.loc[t]
        q = q[q.index.isin(r.dropna().index)]
        if len(q) < 3:
            continue
        raw = pd.Series(0.0, index=PX.columns)
        raw[q[q == 1.0].index] = sign            # top quintile of crowd-long
        raw[q[q == 0.0].index] = -sign
        if neutral and len(q):
            raw[q.index] = raw[q.index] - raw[q.index].mean()
        act = raw[raw.abs() > 1e-12]
        w = raw / max(act.abs().sum(), 1e-12) if len(act) else raw * 0.0
        g = float((w * r.fillna(0.0)).sum())
        turn = float((w - w_prev).abs().sum())
        eq *= (1 + g - turn * one_way)
        curve.append(eq); times.append(t); turns.append(turn); gr.append(g)
        w_prev = w
    if len(curve) < 150:
        return None
    cur = np.asarray(curve); ts = pd.DatetimeIndex(times)
    rets = np.diff(np.concatenate([[1.0], cur])) / np.concatenate([[1.0], cur])[:-1]
    yrs = max((ts[-1] - ts[0]).days / 365.25, 1e-9)
    per_yr = 365 * 24 / hold_h
    m = pd.Series(rets, index=ts).resample("ME").sum()
    return dict(n=len(cur), turn=float(np.mean(turns)),
                gross=float(np.mean(gr)) * 100, net=float(np.mean(rets)) * 100,
                cagr=(max(cur[-1], 1e-12) ** (1 / yrs) - 1) * 100,
                dd=float((1 - cur / np.maximum.accumulate(cur)).max() * 100),
                sharpe=(rets.mean() / rets.std() * np.sqrt(per_yr))
                if rets.std() > 0 else 0.0,
                mpos=float((m > 0).mean()) * 100, monthly=m)


def main():
    print(__doc__.split("REGISTERED PREDICTION")[0].rstrip())
    print("\nREGISTERED: gross near zero and probably negative - the 24h spread was")
    print("measured with 24x overlap, and retail-contrarian is the most widely traded")
    print("sentiment idea in crypto. If gross IS positive, the net at 12bp decides.\n")

    print("=" * 100)
    print("1. GROSS FIRST — if this is negative, nothing else matters")
    print("=" * 100)
    print(f"  {'hold':>6}{'mode':<12}{'periods':>9}{'turnover':>10}"
          f"{'GROSS/pd':>11}{'half':>7}")
    keep = {}
    for h in HOLDS:
        PX, FT = panel(h)
        cut = PX.index[int(len(PX) * 0.6)]
        keep[h] = (PX, FT, cut)
        for neutral in (False, True):
            for lab, kw in (("tune", dict(t_to=cut)), ("HOLD", dict(t_from=cut))):
                d = run(PX, FT, h, 0.0, neutral=neutral, **kw)
                if not d:
                    continue
                print(f"  {h:>5}h{'neutral' if neutral else 'directional':<12}"
                      f"{d['n']:>9}{d['turn']:>10.3f}{d['gross']:>+11.4f}{lab:>7}")
        print()

    pos = []
    for h in HOLDS:
        PX, FT, cut = keep[h]
        for neutral in (False, True):
            a = run(PX, FT, h, 0.0, neutral=neutral, t_to=cut)
            b = run(PX, FT, h, 0.0, neutral=neutral, t_from=cut)
            if a and b and a["gross"] > 0 and b["gross"] > 0:
                pos.append((h, neutral))

    print("=" * 100)
    print("2. NET, ONLY FOR CONFIGURATIONS POSITIVE GROSS IN BOTH HALVES")
    print("=" * 100)
    if not pos:
        print("  None. Every configuration is negative gross in at least one half, so")
        print("  there is nothing for a fee ladder to be charged against.")
    else:
        print(f"  {'hold':>6}{'mode':<12}{'fee':>5}{'net/pd':>10}{'CAGR':>9}"
              f"{'maxDD':>8}{'Sharpe':>8}{'months>0':>10}{'half':>7}")
        for h, neutral in pos:
            PX, FT, cut = keep[h]
            for fee in FEES:
                for lab, kw in (("tune", dict(t_to=cut)), ("HOLD", dict(t_from=cut))):
                    d = run(PX, FT, h, fee, neutral=neutral, **kw)
                    if not d:
                        continue
                    print(f"  {h:>5}h{'neutral' if neutral else 'directional':<12}"
                          f"{fee:>4.0f}b{d['net']:>+10.4f}{d['cagr']:>+8.1f}%"
                          f"{d['dd']:>7.1f}%{d['sharpe']:>8.2f}{d['mpos']:>9.0f}%"
                          f"{lab:>7}")

    print("\n" + "=" * 100)
    print("3. CAPITAL FLOOR — the reason this shape was worth testing at all")
    print("=" * 100)
    PX = keep[HOLDS[0]][0]
    mo = sorted((MIN_ORDER.get(c, 5.0) for c in PX.columns), reverse=True)
    for n in (4, 6, 8):
        print(f"  {n} positions: floor ~ ${sum(mo[:n]):,.0f} at 1x gross exposure")
    print("  vs the deployed blend's $377 — because a no-stop book never enters")
    print("  min_order x stop_fraction / risk, which is a ~40x amplifier.")

    print("\n" + "=" * 100)
    print("VERDICT")
    print("=" * 100)
    if not pos:
        print("  DEAD. Crowd positioning does not make money as a book even before")
        print("  costs, on a non-overlapping grid. Both leads from the positioning")
        print("  archive are now closed, and the archive's own headline result was")
        print("  an artifact of overlapping windows.")
        print("\n  Per the stated goal, drop it. The capital-floor mechanism in")
        print("  section 3 is the only thing from this line worth carrying forward.")
    else:
        print(f"  {len(pos)} configuration(s) positive gross in BOTH halves. Read the")
        print("  net table: if 12bp survives, this is the first tradable thing from")
        print("  non-price data and it has a single-digit-dollar capital floor.")


if __name__ == "__main__":
    main()
