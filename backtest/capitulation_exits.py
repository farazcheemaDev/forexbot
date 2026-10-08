"""LET THE CAPITULATION BOUNCE RUN - the best candidate's entry, frozen, with exits that can catch +10-30%.

capitulation_breadth.py: buy a 4h RSI(14) cross under 20 with volume > 2x, only once >= 5 coins of the point-in-time
top-40 have done so within 24 hours: +1.1..+1.7% a trade in all 4 bar phases - with a +2% CAP on every trade. A
capitulation bounce is often far bigger than 2%. This changes ONLY the exit.

ENTRY (frozen; breadth now counted from SIGNALS on all top-40 coins, not from taken trades): RSI(14) crosses under
    20 at a 4h close, quote volume > 2x its 20-bar average, >= 5 distinct coins (itself included) signalled within the
    24 hours up to and including this bar. Next 4h open. 4 bar phases; 2020 .. 2026-09; dead coins included.
EXITS (one at a time per coin per exit; 12bp + funding; deepest dip recorded for liquidation):
    tp2_nw    +2%, or out after 24 bars if not in profit            (the baseline)
    tp5_nw    +5%, same rule;  tp10_nw  +10%, same rule (7-day cap)
    trail3    no target: stop 6xATR, trail 3xATR under the best price (14-day cap)
    trail5    the same with a 5xATR trail
    hold3d    out at the close 18 bars (3 days) later;  hold7d  42 bars (7 days)
ACCOUNT: 10,000 PKR, 3 slots of a third, skip while full, random same-bar order (5 seeds); 1x / 2x / 3x.

REGISTERED BEFORE THE RUN (2026-10-08)
    - tp5/tp10: average +1.5..+2.5% a trade, win 70-80%. Trailing: +1.5..+3%.
    - The 1x account rises to +1,000..+3,000 PKR a year - still nowhere near +10% a month.
    - At least one wide exit is positive in all 4 phases on both halves.

    python -m backtest.capitulation_exits
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest.capitulation_freq import account  # noqa: E402
from backtest.capitulation_wide import four_hour, funding_cum, hourly  # noqa: E402
from backtest.doge_focus import exit_target, exit_trail  # noqa: E402
from backtest.rsi_factors import prep  # noqa: E402
from backtest.wide_book import eligibility  # noqa: E402

LOG = ROOT / "logs" / "capitulation_exits.txt"
PHASES = (0, 60, 120, 180)
K = 5
EXITS = {"tp2_nw": ("t", 0.02, 24, 42), "tp5_nw": ("t", 0.05, 24, 42), "tp10_nw": ("t", 0.10, 24, 42),
         "trail3": ("r", 3.0, None, 84), "trail5": ("r", 5.0, None, 84),
         "hold3d": ("t", None, None, 18), "hold7d": ("t", None, None, 42)}
HOLDOUT = pd.Timestamp("2024-04-07")


def run_exit(ex, i, P, fc):
    kind, a, nw, cap = EXITS[ex]
    if kind == "t":
        return exit_target(i, 1, a, None, nw, P, fc, cap)
    return exit_trail(i, 1, a, P, fc, s0=6.0, cap=cap)


def main():
    t0 = time.time()
    el = eligibility(40)
    syms = sorted(s for s, m in el.items() if m)
    H = {s: hourly(s) for s in syms}
    H = {s: h for s, h in H.items() if h is not None}
    print(f"  {len(H)} coins loaded ({time.time() - t0:.0f}s)", flush=True)
    rows = []
    for off in PHASES:
        coins = {}
        sigs = []
        for s, h in H.items():
            d = four_hour(h, off)
            if len(d) < 300:
                continue
            P = prep(d, np.full(len(d), np.nan))
            r, v = P["r"], P["v"]
            vavg = pd.Series(v).rolling(20).mean().shift(1).to_numpy()
            sig = np.r_[False, (r[:-1] >= 20) & (r[1:] < 20)] & (v > 2 * vavg)
            sig[:250] = False
            ym = d.time.dt.strftime("%Y-%m").to_numpy()
            t = d.time.to_numpy()
            for i in np.flatnonzero(sig):
                if i + 3 < len(r) and ym[i] in el[s]:
                    sigs.append((t[i], s, i))
            coins[s] = (P, funding_cum(s, t, h), t)
        S = pd.DataFrame(sigs, columns=["t", "coin", "i"]).sort_values("t", kind="stable").reset_index(drop=True)
        tt = S.t.to_numpy("datetime64[ns]").astype(np.int64)
        day, lo, br = 24 * 3600 * 10 ** 9, 0, []
        for k in range(len(S)):
            while tt[lo] < tt[k] - day:
                lo += 1
            hi = np.searchsorted(tt, tt[k], side="right")
            br.append(S.coin.iloc[lo:hi].nunique())
        S = S[np.array(br) >= K]
        for ex in EXITS:
            for s, g in S.groupby("coin"):
                P, fc, t = coins[s]
                free = 0
                for i in g.i:
                    if i < free:
                        continue
                    j, net, worst, jx = run_exit(ex, i, P, fc)
                    rows.append((off, ex, s, t[i + 1], t[min(jx, len(t) - 1)] + np.timedelta64(4, "h"), net, worst))
                    free = j + 1
        print(f"  phase {off}: {len(S)} breadth signals ({time.time() - t0:.0f}s)", flush=True)
    A = pd.DataFrame(rows, columns=["off", "exit", "coin", "t_in", "t_out", "net", "worst"])
    A["t_in"], A["t_out"] = pd.to_datetime(A.t_in), pd.to_datetime(A.t_out)
    A.to_csv(ROOT / "logs" / "capitulation_exits_trades.csv", index=False)
    span = (A.t_in.max() - A.t_in.min()).days / 365
    lines = [f"backtest/capitulation_exits.py, {pd.Timestamp.now():%Y-%m-%d %H:%M}; entry frozen (top-40, 4h RSI<20, vol>2x, "
             f">= {K} coins in 24h); {span:.1f} years; account 10,000 PKR, 3 slots, random same-bar order (5 seeds)", ""]
    lines.append(f"  {'exit':8} | per phase: trades/yr, win, avg/trade, tune / holdout avg | account PKR a year at 1x / 2x / 3x")
    for ex in EXITS:
        cells, acc = [], {1: [], 2: [], 3: []}
        for off in PHASES:
            g = A[(A.exit == ex) & (A.off == off)].sort_values("t_in", kind="stable")
            for lev in (1, 2, 3):
                v = []
                for sd in range(5):
                    gg = g.assign(k=np.random.default_rng(sd).random(len(g))).sort_values(["t_in", "k"], kind="stable")
                    v.append((account(gg, lev)[0] - 10_000) / span)
                acc[lev].append(np.mean(v))
            cells.append(f"+{off:>3}m {len(g) / span:3.0f}/yr {np.mean(g.net > 0):.0%} {g.net.mean() * 100:+.2f}% "
                         f"({g[g.t_in < HOLDOUT].net.mean() * 100:+.2f}/{g[g.t_in >= HOLDOUT].net.mean() * 100:+.2f})")
        lines.append(f"  {ex:8} | " + " | ".join(cells))
        lines.append(f"  {'':8} | account: 1x " + ", ".join(f"{x:+,.0f}" for x in acc[1]) + " | 2x "
                     + ", ".join(f"{x:+,.0f}" for x in acc[2]) + " | 3x " + ", ".join(f"{x:+,.0f}" for x in acc[3]))
    txt = "\n".join(lines)
    print(txt)
    LOG.write_text(txt + "\n")
    print(f"\n-> {LOG} ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
