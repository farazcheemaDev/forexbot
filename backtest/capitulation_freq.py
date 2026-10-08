"""MORE SIGNALS FROM THE CAPITULATION BUY? - every way to loosen it, and what each costs per trade (2026-10-08).

THE USER: "no, I need more - find more frequency." capitulation_wide.py: the frozen rule (4h RSI(14) under 20 + volume
> 3x, +2% or out after 24 bars if not in profit) fires ~44 times a year on the point-in-time top-40, 85-93% win,
~+1% a trade in 3 of 4 bar phases. Frequency comes from loosening it; this measures the price of each loosening.

THE GRID (exit frozen: +2% limit, out at the next open once 24 bars have passed with the close not in profit, 7-day
cap; 12bp + funding; one trade at a time per coin)
    timeframe  4h (4 bar phases) | 1h (from the 1h perp archive)
    RSI(14)    crosses under 20 | 25 | 30
    volume     the bar's quote volume > 2x | 3x | 5x its 20-bar average
    universe   point-in-time top-40 | top-100 by prior-month volume, dead coins included
THE ACCOUNT (realistic for 10,000 PKR): at most 3 positions at once, each a third of current equity, signals taken in
    time order and SKIPPED while 3 are open; a slot frees when its trade exits. Liquidation when a trade's deepest dip
    reaches 1/L - 0.5% - 0.06%. Reported: PKR per year at 1x / 2x / 3x, signals taken vs skipped.

REGISTERED BEFORE THE RUN (2026-10-08)
    - RSI 25/30 or volume 2x: 2-5x the signals, average +0.2..+0.6% a trade, win 80-88%.
    - 1h versions: average <= +0.4% a trade.
    - Top-100: more signals, lower average than top-40.
    - The 10,000 PKR 3-slot account: no configuration beats ~+3,000 PKR a year at 1x averaged over the 4h phases;
      more frequency does not buy proportionally more money.

RESULT (2026-10-08, logs/capitulation_freq.txt, logs/capitulation_freq_configs.csv, 6.6 years, 599 coins ever top-100)
    - Loosening buys signals and sells the edge: 4h top-40 RSI<20 -> 25 -> 30 (vol > 3x): 50 -> 95 -> 140 a year,
      +0.82 -> +0.12 -> -0.24% a trade. Top-100 instead of top-40: 117 a year at +0.65%. 1h: 247-3,229 a year at
      -0.23..+0.23% a trade, holdout negative in every 1h configuration. Volume 2x instead of 3x keeps the average
      (+0.83%) at 84 a year - the one loosening that is nearly free.
    - The realistic 10,000 PKR account (3 slots, skip while full), phase-averaged PKR a year at 1x: best +395 (top-40,
      RSI<20, vol>2x), the original +300 (phases +862 / +434 / -651 / +556); every RSI<25/30 and every 1h row loses;
      at 2-3x almost everything loses. Predicted no configuration above ~+3,000 at 1x: right (far under).
    - Why the account earns so little from +0.8% trades (diagnostic in capitulation_breadth.py's docstring): on a crash
      day the FIRST 3 signals average -0.65..+0.85%, the later ones +1.1..+1.8% - the slots fill with the knives.
    - Predictions: RSI 25 -> +0.1..+0.3 (in the predicted band), RSI 30 negative (WRONG, predicted +0.2..+0.6),
      vol 2x did NOT lower the average (WRONG), 1h <= +0.4 (right), top-100 lower (right).

    python -m backtest.capitulation_freq
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest.capitulation_wide import four_hour, funding_cum, hourly  # noqa: E402
from backtest.rsi_confluence import outcome  # noqa: E402
from backtest.rsi_factors import prep  # noqa: E402
from backtest.wide_book import eligibility  # noqa: E402

LOG = ROOT / "logs" / "capitulation_freq.txt"
XS = (20, 25, 30)
VMS = (2.0, 3.0, 5.0)
GRIDS = (("4h", 0), ("4h", 60), ("4h", 120), ("4h", 180), ("1h", 0))
CAPS = {"4h": 42, "1h": 168}
BAR_H = {"4h": 4, "1h": 1}
SLOTS = 3
STAKE = 10_000.0
HOLDOUT = pd.Timestamp("2024-04-07")


def bars_for(h, tf, off):
    if tf == "1h":
        return h.rename(columns={"open": "o", "high": "h", "low": "l", "close": "c", "qvol": "v"})[
            ["time", "o", "h", "l", "c", "v"]].reset_index(drop=True)
    return four_hour(h, off)


def trades_coin(sym, h, tf, off, months_by_uni):
    """Every (X, vm, universe) configuration's trades on one coin: (cfg, entry time, exit time, net, worst)."""
    d = bars_for(h, tf, off)
    if len(d) < 300:
        return []
    P = prep(d, np.full(len(d), np.nan))
    fc = funding_cum(sym, d.time.to_numpy(), h)
    r, v = P["r"], P["v"]
    vavg = pd.Series(v).rolling(20).mean().shift(1).to_numpy()
    ym = d.time.dt.strftime("%Y-%m").to_numpy()
    t = d.time.to_numpy()
    bar = np.timedelta64(BAR_H[tf], "h")
    memo, out = {}, []
    for X in XS:
        cross = np.r_[False, (r[:-1] >= X) & (r[1:] < X)]
        cross[:250] = False
        for vm in VMS:
            sig = cross & (v > vm * vavg)
            for uni, months in months_by_uni.items():
                free = 0
                for i in np.flatnonzero(sig):
                    if i < free or i + 2 >= len(r) or ym[i] not in months:
                        continue
                    if i not in memo:
                        memo[i] = outcome(i, 1, "tp2_nw", P, fc, CAPS[tf])
                    j, net, worst = memo[i]
                    # the slot frees when the exit has happened: an intrabar target inside bar j -> at its close
                    out.append(((tf, off, X, vm, uni), t[i + 1], t[min(j, len(t) - 1)] + bar, net, worst))
                    free = j + 1
    return out


def account(T, lev):
    """10,000 PKR, 3 slots of a third of current equity, skip while full. Returns (end PKR, taken, skipped)."""
    liq = 1 / lev - 0.005 - 0.0006
    eq, open_, taken, skipped = STAKE, [], 0, 0
    for r in T.itertuples():
        for p in sorted([p for p in open_ if p[0] <= r.t_in], key=lambda p: p[0]):
            eq += p[1]
        open_ = [p for p in open_ if p[0] > r.t_in]
        if len(open_) >= SLOTS or eq <= 0:
            skipped += 1
            continue
        size = eq / SLOTS
        pnl = -size if r.worst >= liq else size * max(lev * r.net, -1.0)
        open_.append((r.t_out, pnl))
        taken += 1
    eq += sum(p[1] for p in open_)
    return max(eq, 0.0), taken, skipped


def main():
    t0 = time.time()
    el40, el100 = eligibility(40), eligibility(100)
    syms = sorted({s for s, m in el100.items() if m})
    print(f"  {len(syms)} coins ever in the top-100 ({time.time() - t0:.0f}s)", flush=True)
    rows = []
    for k, sym in enumerate(syms):
        h = hourly(sym)
        if h is None:
            continue
        mb = {"top40": el40.get(sym, set()), "top100": el100.get(sym, set())}
        for tf, off in GRIDS:
            rows += [(sym,) + x for x in trades_coin(sym, h, tf, off, mb)]
        if (k + 1) % 50 == 0:
            print(f"  {k + 1}/{len(syms)} coins ({time.time() - t0:.0f}s)", flush=True)
    A = pd.DataFrame(rows, columns=["coin", "cfg", "t_in", "t_out", "net", "worst"])
    A[["tf", "off", "X", "vm", "uni"]] = pd.DataFrame(A.cfg.tolist(), index=A.index)
    A = A.drop(columns="cfg")
    A["t_in"], A["t_out"] = pd.to_datetime(A.t_in), pd.to_datetime(A.t_out)
    A.to_csv(ROOT / "logs" / "capitulation_freq_trades.csv.gz", index=False, compression="gzip")
    span = (A.t_in.max() - A.t_in.min()).days / 365
    S = []
    for (tf, off, X, vm, uni), g in A.groupby(["tf", "off", "X", "vm", "uni"]):
        g = g.sort_values("t_in", kind="stable")
        per_day = g.groupby(g.t_in.dt.floor("D")).net.mean()
        td = per_day.mean() / (per_day.std(ddof=1) / np.sqrt(len(per_day))) if len(per_day) > 2 else np.nan
        acc = {lev: account(g, lev) for lev in (1, 2, 3)}
        S.append(dict(tf=tf, off=off, X=X, vm=vm, uni=uni, n=len(g), per_year=len(g) / span, win=np.mean(g.net > 0),
                      avg=g.net.mean(), t_day=td, tune=g[g.t_in < HOLDOUT].net.mean(), hold=g[g.t_in >= HOLDOUT].net.mean(),
                      worst=g.net.min(), **{f"pkr{lev}": (acc[lev][0] - STAKE) / span for lev in (1, 2, 3)},
                      end1=acc[1][0], taken=acc[1][1], skipped=acc[1][2]))
    S = pd.DataFrame(S)
    S.to_csv(ROOT / "logs" / "capitulation_freq_configs.csv", index=False)
    lines = [f"backtest/capitulation_freq.py, {pd.Timestamp.now():%Y-%m-%d %H:%M}; {span:.1f} years; exit frozen (+2% or "
             f"out after 24 bars not in profit); 10,000 PKR account = 3 slots of a third, skip while full", ""]
    lines.append("4h, AVERAGED OVER THE 4 BAR PHASES (signals/yr | win | avg/trade | t by day (min over phases) | holdout | "
                 "PKR a year from 10,000 at 1x / 2x / 3x (worst phase at 1x)):")
    f4 = S[S.tf == "4h"]
    for (uni, X, vm), g in f4.groupby(["uni", "X", "vm"]):
        lines.append(f"  {uni:6} RSI<{X} vol>{vm:.0f}x: {g.per_year.mean():6.0f}/yr | {g.win.mean():.0%} | {g.avg.mean() * 100:+.2f}% | "
                     f"t {g.t_day.mean():+.1f} (min {g.t_day.min():+.1f}) | hold {g.hold.mean() * 100:+.2f}% | "
                     f"{g.pkr1.mean():+7,.0f} / {g.pkr2.mean():+8,.0f} / {g.pkr3.mean():+8,.0f}  (worst phase {g.pkr1.min():+,.0f})")
    lines.append("\n1h (one phase):")
    for r in S[S.tf == "1h"].sort_values(["uni", "X", "vm"]).itertuples():
        lines.append(f"  {r.uni:6} RSI<{r.X} vol>{r.vm:.0f}x: {r.per_year:6.0f}/yr | {r.win:.0%} | {r.avg * 100:+.2f}% | t {r.t_day:+.1f} | "
                     f"hold {r.hold * 100:+.2f}% | {r.pkr1:+7,.0f} / {r.pkr2:+8,.0f} / {r.pkr3:+8,.0f} | taken {r.taken} skipped {r.skipped}")
    base = f4[(f4.uni == "top40") & (f4.X == 20) & (f4.vm == 3.0)]
    best = f4.groupby(["uni", "X", "vm"]).pkr1.mean().sort_values(ascending=False)
    lines.append(f"\n  the original (top40, RSI<20, vol>3x): {base.per_year.mean():.0f} signals/yr, {base.pkr1.mean():+,.0f} PKR/yr at 1x "
                 f"(phases {', '.join(f'{x:+,.0f}' for x in base.pkr1)})")
    lines.append(f"  best 4h configuration by phase-averaged PKR at 1x: {best.index[0]} -> {best.iloc[0]:+,.0f} PKR/yr")
    txt = "\n".join(lines)
    print(txt)
    LOG.write_text(txt + "\n")
    print(f"\n-> {LOG} ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
