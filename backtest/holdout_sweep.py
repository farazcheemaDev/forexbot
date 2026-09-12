"""EVERY strategy we have, tested on data that played no part in any decision.

This is gate 5 of strategy_analysis/validation_protocol.md applied across the
board. It exists because gate 3 (MCPT) turned out to be passable by a strategy
that loses money: gold scored p=0.0050 and then -12.6%/yr on unseen data.

ORDERING MATTERS. The holdout is the DISCRIMINATING test and it is cheap (one
backtest per config). MCPT is expensive and can be passed by junk. So we screen
everything here first and spend permutation compute only on survivors.

NO OPTIMISATION HAPPENS HERE. Each config is evaluated as-is on the holdout.
There is no re-fitting, no parameter selection, nothing to overfit with - which
is the entire point. Configs come from the same SPACE the original search used,
so this measures "would the things we were choosing among have worked on data we
never saw?"

THE SPLIT: for each asset, everything OLDER than the most recent USED_DAYS is
holdout. The recent window is what every prior experiment touched, and is shown
alongside purely for contrast - it is contaminated and proves nothing.

    python -m backtest.holdout_sweep                 # all families, crypto
    python -m backtest.holdout_sweep --family rsi_mom
    python -m backtest.holdout_sweep --min-trades 50
"""
from __future__ import annotations

import argparse
import itertools
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.mass_search import FILTERS, SPACE, fetch  # noqa: E402
from backtest.mcpt import gen_signals_ext  # noqa: E402
from backtest.rtest import run_r, stats  # noqa: E402
from bot.core.indicators import atr as atr_ind  # noqa: E402
from bot.strategies.base import Action  # noqa: E402
from bot.strategies.bollinger_rsi import BollingerRsi  # noqa: E402
from bot.strategies.level_fade import LevelFade  # noqa: E402
from bot.strategies.liquidity_sweep import LiquiditySweep  # noqa: E402
from bot.strategies.rsi_trend import RsiTrend  # noqa: E402
from bot.strategies.stoch_rsi import StochRsi  # noqa: E402
from bot.strategies.vwap_reversion import VwapReversion  # noqa: E402

LOGS = Path(__file__).resolve().parents[1] / "logs"
ASSETS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT",
          "AVAXUSDT", "DOGEUSDT", "ADAUSDT", "LINKUSDT"]
USED_DAYS = 900            # every prior experiment used the most recent 900d
SL, TP, FEE_BP = 2.0, 3.0, 10.0
DAYS = 2400

# Families driven by the class-based strategies (incl. the one reverse-engineered
# from the screen recording of the human NASDAQ scalper).
CLASS_SPACE = {
    "level_fade":      [(p, rl, rh) for p in (6.0, 10.0)
                        for rl, rh in ((32.0, 68.0), (25.0, 75.0))],
    "liquidity_sweep": [(s,) for s in (10, 20, 40)],
    "vwap_rev":        [(k,) for k in (1.5, 2.0, 2.5)],
    "stoch_rsi_pb":    [(o, ob) for o, ob in ((0.2, 0.8), (0.3, 0.7))],
    "stoch_rsi_rev":   [(o, ob) for o, ob in ((0.2, 0.8), (0.3, 0.7))],
    "bollinger_rsi":   list(itertools.product([20, 30], [2.0, 2.5])),
    "rsi_trend":       list(itertools.product([14, 21], [(40.0, 60.0)])),
}


def round_step_for(df: pd.DataFrame) -> float:
    """The scalper faded 25-point levels on NASDAQ (~1.4bp of a 18000 index).
    Crypto prices span 0.1 to 100000, so the equivalent must be scaled: pick the
    power of 10 nearest 0.1% of median price. Documented because it is a judgement
    call, not a fitted parameter."""
    px = float(df["close"].median())
    return float(10 ** round(np.log10(max(px * 0.001, 1e-9))))


def class_signals(df: pd.DataFrame, fam: str, p: tuple) -> pd.Series:
    if fam == "level_fade":
        prox, rlo, rhi = p
        return LevelFade(round_step=round_step_for(df), prox=prox,
                         rsi_lo=rlo, rsi_hi=rhi, use_prior_day=True).signals(df)
    if fam == "liquidity_sweep":
        return LiquiditySweep(swing=p[0], use_prior_day=True).signals(df)
    if fam == "vwap_rev":
        return VwapReversion(k=p[0]).signals(df)
    if fam in ("stoch_rsi_pb", "stoch_rsi_rev"):
        o, ob = p
        mode = "pullback" if fam.endswith("pb") else "reversion"
        return StochRsi(oversold=o, overbought=ob, mode=mode).signals(df)
    if fam == "bollinger_rsi":
        n, k = p
        return BollingerRsi(bb_period=n, bb_std=k).signals(df)
    if fam == "rsi_trend":
        n, (lo, hi) = p
        return RsiTrend(rsi_period=n, rsi_low=lo, rsi_high=hi).signals(df)
    raise ValueError(fam)


def signals_for(df: pd.DataFrame, fam: str, p: tuple) -> pd.Series:
    if fam in CLASS_SPACE:
        return class_signals(df, fam, p)
    return gen_signals_ext(df, fam, p)


def evaluate(df: pd.DataFrame, sig: pd.Series) -> dict | None:
    """One fixed config, one asset, in SCALE-FREE R.

    Uses backtest.rtest, not run_backtest: the latter clamps lots to broker
    limits, so dollar P&L per trade depends on price level and R = pnl/100 is
    then meaningless. That bug produced mean R = +2.15 on BTC (impossible: a win
    caps at +1.5R) and near-zero on DOGE. See rtest.py docstring.
    """
    R, idx = run_r(df, sig, SL, TP, FEE_BP)
    if len(R) < 10:
        return None
    st = stats(R, df["time"].iloc[idx] if len(idx) else None)
    return dict(n=st["n"], meanR=st["meanR"], sumR=st["sumR"], pf=st["pf"],
                win=st["win"], dd=st["dd"], mar=st.get("mar", float("nan")),
                cagr=st.get("cagr", float("nan")))


def full_space() -> dict:
    space = {f: [tuple(p) for p in ps] for f, ps in SPACE.items()}
    space["donch_lo"] = list(itertools.product([10, 20, 30, 55, 80], [100, 200]))
    space["macd_trend"] = list(itertools.product([8, 12], [21, 26], [9], [200]))
    space.update(CLASS_SPACE)
    return space


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--family", default=None)
    ap.add_argument("--min-trades", type=int, default=100,
                    help="minimum TOTAL trades across assets to report a family")
    args = ap.parse_args()

    space = full_space()
    if args.family:
        space = {args.family: space[args.family]}

    data = {}
    for a in ASSETS:
        try:
            d = fetch(a, "1h", DAYS)
        except Exception as e:
            print(f"  {a}: fetch failed {e}"); continue
        cut = d.time.iloc[-1] - pd.Timedelta(days=USED_DAYS)
        hold = d[d.time < cut].reset_index(drop=True)
        used = d[d.time >= cut].reset_index(drop=True)
        if len(hold) < 3000:
            print(f"  {a}: only {len(hold)} holdout bars - skipped")
            continue
        data[a] = (hold, used)
        print(f"  {a:9} holdout {len(hold):6} bars "
              f"({hold.time.iloc[0].date()}..{hold.time.iloc[-1].date()})  "
              f"used {len(used):6}")

    n_cfg = sum(len(v) for v in space.values()) * len(FILTERS)
    print(f"\n{len(space)} families, {n_cfg} configs x {len(data)} assets "
          f"= {n_cfg*len(data)} backtests on UNTOUCHED data")
    print(f"frozen: exits {SL}/{TP} ATR, {FEE_BP}bp, no optimisation\n")

    rows = []
    for fam, plist in space.items():
        for p in plist:
            for fname in FILTERS:
                agg = {"hold": [], "used": []}
                for a, (hold, used) in data.items():
                    for key, df in (("hold", hold), ("used", used)):
                        try:
                            s = FILTERS[fname](df, signals_for(df, fam, p))
                            r = evaluate(df, s)
                        except Exception:
                            r = None
                        if r:
                            agg[key].append(r)
                if len(agg["hold"]) < 3:
                    continue
                h = agg["hold"]
                nh = sum(x["n"] for x in h)
                if nh < args.min_trades:
                    continue
                # trade-weighted mean R across assets
                mh = sum(x["meanR"] * x["n"] for x in h) / nh
                pos = sum(1 for x in h if x["meanR"] > 0)
                u = agg["used"]
                nu = sum(x["n"] for x in u) or 1
                mu = (sum(x["meanR"] * x["n"] for x in u) / nu) if u else float("nan")
                rows.append(dict(fam=fam, p=str(p), filt=fname, n_hold=nh,
                                 meanR_hold=mh, assets_pos=pos, n_assets=len(h),
                                 meanR_used=mu, n_used=nu))
        print(f"  ...{fam} done", flush=True)

    rows.sort(key=lambda r: -r["meanR_hold"])
    print(f"\n{'='*96}")
    print("RANKED BY MEAN R ON UNTOUCHED DATA  (holdout is the verdict; "
          "'used' is contaminated, shown for contrast)")
    print(f"{'='*96}")
    print(f"{'family':16} {'params':17} {'filt':6} {'trades':>7} {'meanR':>8} "
          f"{'assets+':>8} {'usedR':>8}")
    for r in rows[:35]:
        print(f"{r['fam']:16} {r['p'][:17]:17} {r['filt']:6} {r['n_hold']:>7} "
              f"{r['meanR_hold']:>+8.4f} {r['assets_pos']:>3}/{r['n_assets']:<4} "
              f"{r['meanR_used']:>+8.4f}")

    print(f"\n{'-'*96}\nWORST 10 (for contrast):")
    for r in rows[-10:]:
        print(f"{r['fam']:16} {r['p'][:17]:17} {r['filt']:6} {r['n_hold']:>7} "
              f"{r['meanR_hold']:>+8.4f} {r['assets_pos']:>3}/{r['n_assets']:<4} "
              f"{r['meanR_used']:>+8.4f}")

    # family-level summary: the individual config is noise, the family is signal
    print(f"\n{'='*96}\nBY FAMILY (all params/filters pooled — "
          f"a family that only works at one setting is a fluke)")
    print(f"{'='*96}")
    print(f"{'family':16} {'cfgs':>5} {'trades':>8} {'meanR':>9} "
          f"{'cfgs>0':>8}  verdict")
    fams = {}
    for r in rows:
        fams.setdefault(r["fam"], []).append(r)
    fsum = []
    for fam, rs in fams.items():
        nt = sum(r["n_hold"] for r in rs)
        m = sum(r["meanR_hold"] * r["n_hold"] for r in rs) / nt
        pos = sum(1 for r in rs if r["meanR_hold"] > 0)
        fsum.append((m, fam, len(rs), nt, pos))
    for m, fam, ncfg, nt, pos in sorted(fsum, reverse=True):
        frac = pos / ncfg
        v = ("SURVIVES - worth MCPT" if m > 0.02 and frac >= 0.6 else
             "marginal" if m > 0 else "DEAD on unseen data")
        print(f"{fam:16} {ncfg:>5} {nt:>8} {m:>+9.4f} {pos:>4}/{ncfg:<3}  {v}")

    out = LOGS / "holdout_sweep.json"
    json.dump(rows, open(out, "w"), indent=1)
    print(f"\nsaved -> {out}")
    surv = [f for m, f, c, n, p in sorted(fsum, reverse=True) if m > 0.02]
    print(f"\nSURVIVORS to put through MCPT: {surv or 'NONE'}")


if __name__ == "__main__":
    main()
