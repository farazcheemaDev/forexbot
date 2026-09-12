"""NEW-LISTING MOMENTUM, SURVIVORSHIP-FREE. The test that was impossible until now.

THE QUESTION
    Does trend-following on RECENTLY LISTED coins work? This is the category where
    crypto's largest returns are supposed to live, and it has been strictly
    untestable in this project because every universe was built from coins trading
    TODAY - a population pre-filtered to things that did not die.

    backtest/xs_wide.py measured +0.70R on "virgin recent listings" (WIF, BONK,
    PENGU, TRUMP, MUBARAK, DOGS, TREE, WLFI...). Those are in today's top-120 by
    volume BECAUSE they pumped. 203 USDT pairs have been delisted - a 30% death
    rate - and not one of them was in that test.

WHAT THIS DOES DIFFERENTLY
    Universe = recent listings from BOTH populations:
        SURVIVORS  still trading today          (the biased half)
        DEAD       delisted, from the archive    (the missing half)
    A coin is tradeable only between its first and last bar, so nothing knows in
    advance which coins will survive.

    The headline is not the absolute number. It is the DELTA between
    survivors-only and survivors+dead. That delta IS the survivorship bias,
    measured rather than argued about.

THE DELISTING EXIT, HANDLED EXPLICITLY
    A position open when a coin's data ends used to be dropped silently - which
    would have deleted precisely the trades where the coin died on us. Both
    plausible exits are now run:
        announced  exit at the last close. Binance usually gives notice and
                   force-settles perps near mark, so this is the fair case.
        collapse   exit at the stop. Right for a LUNA-style gap through it.
    Truth is bracketed by the two rather than assumed to be one.

    Even "collapse" is optimistic in one way: it caps the loss at the stop. A real
    gap can blow through a stop entirely, and on a dying altcoin the book may be
    empty. So the honest reading is that reality is at or below the collapse row.

PREDICTION, REGISTERED BEFORE THE DATA LANDED
    The recent-listing edge will fall substantially once corpses are included,
    probably below the fee toll (~0.10R on 1h alts). If it survives a 30% death
    rate it is real.

    python -m backtest.newlist
    python -m backtest.newlist --cutoff 2023-01-01
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.convex import describe, run_uncapped  # noqa: E402
from backtest.mass_search import fetch, gen_signals  # noqa: E402
from bot.strategies.base import Action  # noqa: E402

DATA = Path(__file__).resolve().parents[1] / "strategy_analysis" / "data"
DEAD = DATA / "dead"
FEE_BP = 12.0
RISK = 0.5
TRAILS = (5.0, 8.0, 12.0)
# frozen, same families as every other uncapped test today
FAMS = [("donchian", (20,)), ("bb_break", (30, 1.5)), ("roc_mom", (24, 2.0))]
MIN_BARS = 600          # ~25 days; below this there is no trend to follow


def load_dead() -> dict[str, pd.DataFrame]:
    out = {}
    for f in sorted(DEAD.glob("*_1h.csv.gz")):
        try:
            d = pd.read_csv(f, parse_dates=["time"])
        except Exception:
            continue
        if len(d) >= MIN_BARS:
            out[f.name.split("_")[0]] = d
    return out


def load_alive() -> dict[str, pd.DataFrame]:
    out = {}
    try:
        syms = json.load(open(DATA / "wide_universe.json"))
    except Exception:
        return out
    for s in syms:
        try:
            d = fetch(s, "1h", 1500)
        except Exception:
            continue
        if d is not None and len(d) >= MIN_BARS:
            out[s] = d
    return out


def pool(frames: dict[str, pd.DataFrame], fam, p, trail, end_mode):
    Rs, Ts, Ds = [], [], []
    for s, df in frames.items():
        sig = gen_signals(df, fam, p)
        if sig is None or int((sig != Action.HOLD).sum()) == 0:
            continue
        # long only: every family measured today earned ~0 on the short side
        sig = sig.where(sig != Action.SELL, Action.HOLD)
        R, idx, _b, D = run_uncapped(df, sig, sl_mult=2.0, fee_bp=FEE_BP,
                                     mode="trail_atr", trail=trail,
                                     close_at_end=end_mode)
        if len(R):
            Rs.append(R); Ts.append(df["time"].iloc[idx]); Ds.append(D)
    if not Rs:
        return None
    o = np.argsort(np.concatenate([t.values for t in Ts]))
    R = np.concatenate(Rs)[o]
    T = pd.Series(np.concatenate([t.values for t in Ts])[o])
    d = describe(R, T, RISK, dirs=np.concatenate(Ds)[o])
    if d:
        d["coins"] = len(Rs)
    return d


def portfolio(frames: dict[str, pd.DataFrame], fam, p, trail, end_mode,
              max_pos: int, risk_pct: float) -> dict | None:
    """Realistic portfolio pass with a CONCURRENT-POSITION CAP.

    WHY THIS IS NEEDED. pool() above computes each coin's trades independently and
    then pools the R values, which silently assumes unlimited capital and
    unlimited simultaneous positions. Across ~96 alts that is badly wrong: when 40
    coins break out together the pooled version books all 40 at full risk, which
    is why every CAGR column came out at -83% to -100%. The per-trade edge was
    valid; the portfolio arithmetic was not.

    Here trades are generated per coin, then accepted in CHRONOLOGICAL order only
    if a slot is free. A signal arriving with all slots full is skipped, exactly as
    it would be in a real account. That makes the return figure mean something and
    it also removes the fake correlation stacking.
    """
    trades = []
    for s, df in frames.items():
        sig = gen_signals(df, fam, p)
        if sig is None or int((sig != Action.HOLD).sum()) == 0:
            continue
        sig = sig.where(sig != Action.SELL, Action.HOLD)
        R, idx, bars, _D = run_uncapped(df, sig, sl_mult=2.0, fee_bp=FEE_BP,
                                        mode="trail_atr", trail=trail,
                                        close_at_end=end_mode)
        if not len(R):
            continue
        t = df["time"].to_numpy()
        for r, ix, nb in zip(R, idx, bars):
            entry_i = max(int(ix) - int(nb), 0)
            trades.append((t[entry_i], t[int(ix)], float(r)))
    if not trades:
        return None
    trades.sort(key=lambda x: x[0])

    eq, curve, times = 1.0, [], []
    open_until: list = []
    taken = skipped = 0
    ruined = False
    f = risk_pct / 100.0
    for t_in, t_out, r in trades:
        open_until = [u for u in open_until if u > t_in]   # free finished slots
        if len(open_until) >= max_pos:
            skipped += 1
            continue
        open_until.append(t_out)
        taken += 1
        if not ruined:
            eq *= (1 + r * f)
            if eq <= 1e-9:
                eq, ruined = 0.0, True
        curve.append(eq); times.append(t_out)
    if taken < 30:
        return None
    cur = np.asarray(curve)
    peak = np.maximum.accumulate(np.maximum(cur, 1e-12))
    dd = float((1 - cur / peak).max() * 100)
    ts = pd.DatetimeIndex(times)
    yrs = max((ts[-1] - ts[0]).days / 365.25, 1e-9)
    cagr = (max(cur[-1], 0.0) ** (1 / yrs) - 1) * 100 if not ruined else -100.0
    mo = pd.Series(cur, index=ts).resample("30D").last().pct_change().dropna() * 100
    if ruined:
        mo = mo.iloc[:0]
    return dict(taken=taken, skipped=skipped, cagr=float(cagr), dd=dd,
                ruined=ruined,
                mar=float(cagr / dd) if dd > 0.5 else 0.0,
                mo_med=float(mo.median()) if len(mo) else float("nan"),
                mo_over10=float((mo > 10).mean() * 100) if len(mo) else float("nan"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cutoff", default="2023-01-01")
    ap.add_argument("--max-pos", type=int, default=8,
                    help="concurrent position cap (a real account has one)")
    args = ap.parse_args()
    cut = pd.Timestamp(args.cutoff)

    dead_all = load_dead()
    alive_all = load_alive()
    # "recent listing" = first bar after the cutoff
    dead = {s: d for s, d in dead_all.items() if d["time"].iloc[0] >= cut}
    alive = {s: d for s, d in alive_all.items() if d["time"].iloc[0] >= cut}
    both = {**alive, **dead}

    print(f"NEW-LISTING MOMENTUM, SURVIVORSHIP-FREE   listed after {cut:%Y-%m-%d}")
    print(f"  SURVIVORS      {len(alive):>4} coins   (the biased half)")
    print(f"  DEAD           {len(dead):>4} coins   (the half every prior test "
          f"omitted)")
    print(f"  death rate in this universe: "
          f"{len(dead)/max(len(both),1)*100:.0f}%")
    print(f"  fetched so far: {len(dead_all)} dead / {len(alive_all)} alive "
          f"with >={MIN_BARS} bars")
    print(f"  long only | trail {TRAILS}xATR | fee {FEE_BP}bp | risk {RISK}%\n")
    if not dead:
        print("no dead coins listed after the cutoff yet - download still running")
        return

    print("=" * 112)
    print(f"{'family':<16} {'trail':>6} {'universe':<18} {'exit':<10} {'coins':>5} "
          f"{'n':>6} {'meanR':>8} {'t':>7} {'CAGR':>9} {'DD':>7} {'mo>10%':>7}")
    res = {}
    for fam, p in FAMS:
        for tr in TRAILS:
            for uname, frames in (("survivors only", alive),
                                  ("survivors+DEAD", both)):
                for em in ("close", "stop"):
                    if uname == "survivors only" and em == "stop":
                        continue          # survivors do not delist; one row is enough
                    d = pool(frames, fam, p, tr, em)
                    if not d:
                        continue
                    res[(fam, tr, uname, em)] = d
                    ru = " RUIN" if d["ruined"] else ""
                    lbl = "announced" if em == "close" else "collapse"
                    print(f"{fam+str(p):<16} {tr:>5.0f}x {uname:<18} {lbl:<10} "
                          f"{d['coins']:>5} {d['n']:>6} {d['mean']:>+8.3f} "
                          f"{d['t']:>+7.2f} {d['cagr']:>+8.1f}% {d['dd']:>6.1f}%"
                          f"{d['mo_over10']:>6.1f}%{ru}", flush=True)
            print()

    print("=" * 112)
    print("THE SURVIVORSHIP BIAS, MEASURED")
    print("=" * 112)
    print(f"{'family':<16} {'trail':>6} {'survivors':>10} {'+dead(ann)':>11} "
          f"{'+dead(coll)':>12} {'bias':>8}")
    deltas = []
    for fam, p in FAMS:
        for tr in TRAILS:
            a = res.get((fam, tr, "survivors only", "close"))
            b = res.get((fam, tr, "survivors+DEAD", "close"))
            c = res.get((fam, tr, "survivors+DEAD", "stop"))
            if not (a and b):
                continue
            bias = a["mean"] - b["mean"]
            deltas.append(bias)
            print(f"{fam+str(p):<16} {tr:>5.0f}x {a['mean']:>+10.3f} "
                  f"{b['mean']:>+11.3f} "
                  f"{(c['mean'] if c else float('nan')):>+12.3f} "
                  f"{bias:>+8.3f}")
    if deltas:
        print(f"\nmean survivorship bias: {np.mean(deltas):+.3f}R per trade")
        print("  that is how much every prior recent-listing number was overstated")
    surv = [v for k, v in res.items()
            if k[2] == "survivors+DEAD" and k[3] == "stop" and v["mean"] > 0.10]
    print(f"\ncells still above the ~0.10R alt fee toll with corpses included "
          f"and collapse exits: {len(surv)}")

    # ---- realistic portfolio, with a concurrent-position cap ----------------
    print("\n" + "=" * 112)
    print(f"REALISTIC PORTFOLIO — max {args.max_pos} concurrent positions, "
          f"risk swept. Corpses included, collapse exits.")
    print("=" * 112)
    print(f"{'family':<16} {'trail':>6} {'risk':>6} {'taken':>7} {'skipped':>8} "
          f"{'CAGR':>9} {'DD':>7} {'MAR':>6} {'medmo':>7} {'mo>10%':>7}")
    for fam, p in FAMS:
        for tr in TRAILS:
            for rk in (0.5, 1.0, 2.0):
                d = portfolio(both, fam, p, tr, "stop", args.max_pos, rk)
                if not d:
                    continue
                ru = " RUIN" if d["ruined"] else ""
                print(f"{fam+str(p):<16} {tr:>5.0f}x {rk:>5.2f}% {d['taken']:>7} "
                      f"{d['skipped']:>8} {d['cagr']:>+8.1f}% {d['dd']:>6.1f}% "
                      f"{d['mar']:>+6.2f} {d['mo_med']:>+6.2f}% "
                      f"{d['mo_over10']:>6.1f}%{ru}", flush=True)
    print("\n'skipped' = signals declined because all slots were full. A large "
          "skip count means\nthe strategy needs more capital than one account "
          "provides, and the pooled\nper-trade numbers above were counting trades "
          "you could never have taken.")
    print("PREDICTION MADE BEFORE THE DATA: the edge falls below the fee toll. "
          "If cells\nremain above it, new-listing momentum is real and is the "
          "first large finding here.")


if __name__ == "__main__":
    main()
