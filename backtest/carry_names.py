"""DOES THE CARRY BOOK KEEP ITS EDGE WITH FEWER COINS? - the check behind a capital-floor fix (2026-11-21)

WHY: the live carry book sizes each of its ~12 coins a side at equity x 0.5 x 0.5 / 12 = equity / 48 and skips any coin under
Bitget's $5 minimum; all coins are the same size, so below ~$240 the WHOLE book goes empty (main since the 2026-11-13
rebalance, fresh since 11-14 - CLAUDE.md s10 2026-11-19; backtest/crash_lessons.py). The backtest never switched it off: it
held its ~12 a side at any account size. The fix that keeps the book doing what was tested (doc 22 s4 allows such fixes) is
to hold as many coins as the minimum allows at the SAME total size - the top-k by funding rank, k = the side's dollars / $5
(about 10 a side at $207, 6 at $120). This file checks that a smaller basket keeps the book's edge. It is a robustness check
of the deployed rule, not a search for a better setting: k = 12 stays the rule whenever the account can afford it.

TEST: mn_combos.mn_run(look=1, score="funding7", fwin=7, start=0..6, stop="short_only", short_stop=0.5) - the machine's carry
book exactly as all_books.machine_books runs it - with frac set so the basket holds k = 12 (as deployed), 10, 8, 6 and 4 coins
a side (k = max(int(n x frac), 3) over the ~60 eligible). Weekly net per rebalance; Sharpe and mean by half (split
pair_lab.HOLDOUT, 2024-04-07) and paired against k = 12 on the same weekday.

REGISTERED BEFORE RUNNING (2026-11-21)
  N1  With 10, 8 and 6 coins a side the carry book's Sharpe is within 0.2 of the 12-coin book's on BOTH halves (mean of the
      7 weekdays). (60%)
  N2  With 4 coins a side it drops by more than 0.2 on at least one half (fewer names, more squeeze risk). (55%)
  Decision rule, fixed now: the floor fix is supported if N1 holds; if a k between 6 and 10 fails it, the fix floors k at the
  smallest k that passes, and below that the book stays off as now.

RESULT (2026-11-21, logs/carry_names.txt): Sharpe tune / holdout, mean of 7 weekdays - 12 coins +1.40 / +0.74, 10 +1.31 / +0.57,
  8 +1.34 / +0.39, 6 +1.28 / +0.10, 4 +1.11 / +0.03; worst week -10.5% -> -12.6 / -15.4 / -18.5 / -23.5%. Fewer coins keep the
  tune half and lose the holdout on every weekday (0 of 7 at least as high for 10, 8, 6). N1 WRONG (10 passes, 8 and 6 fail),
  N2 right. By the rule fixed above the fix could floor at 10 coins - which only moves the switch-off from ~$240 to ~$200 of
  equity at a cost of 0.17 holdout Sharpe. NOT implemented: the carry book needs its full basket, so the lesson is capital -
  about $240 of equity at full size (12 coins x 2 sides x $5 / 0.25), $480 at half size - not code.

    python -m backtest.carry_names
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
LOG = ROOT / "logs" / "carry_names.txt"
KS = (12, 10, 8, 6, 4)


def sharpe(x: pd.Series) -> float:
    x = x.dropna()
    return float(x.mean() / x.std(ddof=1) * np.sqrt(52)) if len(x) > 5 and x.std(ddof=1) > 0 else float("nan")


def main():
    from backtest import mn_combos as m
    from backtest.pair_lab import HOLDOUT
    D = m.ohl()
    out = []
    say = lambda s="": (print(s, flush=True), out.append(s))  # noqa: E731
    # the eligible count per rebalance is ~60; frac is set from the median count so int(n x frac) = k
    n_el = []
    for i in range(32, len(D["idx"]) - 8, 7):
        t0 = D["idx"][i]
        ok = (D["Em"][D["months"][i]] & ((t0.value - D["fv"]) // 86_400_000_000_000 >= m.MIN_AGE_D) & np.isfinite(D["X"][i]))
        if ok.sum() >= 20:
            n_el.append(int(ok.sum()))
    n_med = int(np.median(n_el))
    say(f"backtest/carry_names.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; the machine's carry book (mn_combos.mn_run "
        f"funding7, +50% short exit) by coins a side; eligible coins per rebalance: median {n_med} (10th {np.percentile(n_el, 10):.0f}, "
        f"90th {np.percentile(n_el, 90):.0f}); split {HOLDOUT:%Y-%m-%d}")
    R = {}
    for k in KS:
        frac = 0.2 if k == 12 else (k + 0.5) / n_med        # k = 12: the deployed frac exactly
        R[k] = {o: m.mn_run(look=1, score="funding7", fwin=7, frac=frac, start=o, stop="short_only", short_stop=0.5)
                for o in range(7)}
    say("")
    say(f"  {'coins a side':<14}{'Sharpe tune':>12}{'Sharpe hold':>12}{'%/wk tune':>11}{'%/wk hold':>11}"
        f"{'worst week':>12}{'paired vs 12: tune / hold (wins of 7)':>42}")
    res = {}
    for k in KS:
        st, sh, mt, mh, worst, dt, dh, wt, wh = [], [], [], [], [], [], [], [], []
        for o in range(7):
            x = R[k][o]
            b = R[12][o]
            t, h = x[x.index < HOLDOUT], x[x.index >= HOLDOUT]
            st.append(sharpe(t)), sh.append(sharpe(h)), mt.append(t.mean()), mh.append(h.mean()), worst.append(x.min())
            d = (x - b.reindex(x.index)).dropna()
            dt.append(d[d.index < HOLDOUT].mean()), dh.append(d[d.index >= HOLDOUT].mean())
            wt.append(sharpe(t) >= sharpe(b[b.index < HOLDOUT])), wh.append(sharpe(h) >= sharpe(b[b.index >= HOLDOUT]))
        res[k] = (np.mean(st), np.mean(sh))
        say(f"  {k:<14}{np.mean(st):>+12.2f}{np.mean(sh):>+12.2f}{np.mean(mt) * 100:>+10.2f}%{np.mean(mh) * 100:>+10.2f}%"
            f"{np.min(worst) * 100:>+11.1f}%   {np.mean(dt) * 100:>+7.2f} / {np.mean(dh) * 100:>+6.2f} %/wk  "
            f"(Sharpe at least as high: {sum(wt)} / {sum(wh)})")
    b_t, b_h = res[12]
    n1 = all(abs(res[k][0] - b_t) <= 0.2 and abs(res[k][1] - b_h) <= 0.2 for k in (10, 8, 6))
    n2 = (res[4][0] < b_t - 0.2) or (res[4][1] < b_h - 0.2)
    say("")
    say(f"  N1 10 / 8 / 6 coins within 0.2 Sharpe of 12 on both halves: "
        + ", ".join(f"{k}: {res[k][0] - b_t:+.2f} / {res[k][1] - b_h:+.2f}" for k in (10, 8, 6)) + f" -> {'RIGHT' if n1 else 'WRONG'}")
    say(f"  N2 4 coins drop more than 0.2 on a half: {res[4][0] - b_t:+.2f} / {res[4][1] - b_h:+.2f} -> {'RIGHT' if n2 else 'WRONG'}")
    LOG.write_text("\n".join(out) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
