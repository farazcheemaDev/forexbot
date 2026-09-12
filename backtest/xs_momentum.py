"""CROSS-SECTIONAL MOMENTUM, MARKET-NEUTRAL — attacking the correlation tax.

WHY THIS EXISTS (read this before believing any number below)
-------------------------------------------------------------
The one strategy that survived every gate was regime-gated crypto momentum:
+0.13R/trade, profitable on 6/6 coins never used in selection, ~1000 trades each,
at Bitget's real fees. It then FAILED portfolio simulation: +0.03 to +0.087R with
35-59% drawdowns. I filed that as "strategy fails". That was the wrong diagnosis.

    Long-only return  =  (market move)  +  (relative-strength move)

The market term is where the correlation and the drawdown live. When 20 coins
signal long together you do not hold 20 bets; at rho=0.8 you hold about 1.6. You
carry 20x the risk to get 1.6x the diversification. The relative-strength term -
the part the ranking actually predicts - is a small share of that variance.

So: hold the top k LONG and the bottom k SHORT, equal dollars per side. The shared
move cancels inside every rebalance. Same signal, market term deleted. The
correlation that destroyed the long-only portfolio becomes the thing being
subtracted out - it is now an asset, not a tax.

WHAT I AM NOT CLAIMING
    This is not original. Cross-sectional momentum is one of the most replicated
    anomalies in finance (equities, futures, FX, and yes crypto). That cuts both
    ways: it is unlikely to be a mining artifact, and it is unlikely to be large.

THREE HEADWINDS, CHARGED EXPLICITLY - NOT ASSUMED AWAY
    1. FUNDING IS AGAINST US. Momentum says long the hot coin, and the hot coin
       has positive funding, so the long leg PAYS. The short leg receives. These
       partly cancel and the residual is an empirical question, so real 8h funding
       history is charged on both legs. This is the single most likely thing to
       kill the strategy and it is measured, not modelled.
    2. TURNOVER. Costs are charged on ACTUAL turnover (sum |dW|), not on a naive
       "2 legs x k coins" count. A coin that stays in the long book across a
       rebalance is not retraded. Ignoring this overstates cost by ~2-3x; assuming
       zero turnover understates it. Taker (6bp) is the headline number because we
       MEASURED maker fills at 53% and they are not dependable.
    3. SURVIVORSHIP. These 28 coins exist today. Coins that went to zero are
       absent. That inflates the long leg (survivors are winners) and deflates the
       short leg (the true zeros would have been our best shorts). Direction of the
       net bias is ambiguous, magnitude unknown. Stated, not corrected.

METHODOLOGY, same discipline as everything else
    * signal at close[t] -> trade at open[t+1] -> hold to open[t+1+hold].
      A bar can never see itself. This is the bug that inflated MAR to 35 once.
    * DEV = oldest data. HOLDOUT = most recent 500 days, in the realistic
      direction (develop in the past, verify on the recent unseen future).
    * The grid's OVERALL positivity is the test, not any single best cell. The
      gold disaster came from trusting one cell that passed at p=0.005.
    * The long-only version runs on identical data as a CONTROL, so we can see
      whether neutralisation is doing the work or whether it is just momentum.

    python -m backtest.xs_momentum
"""
from __future__ import annotations

import argparse
import itertools
import json
import sys
import time
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.mass_search import fetch  # noqa: E402
from bot.core.indicators import efficiency_ratio  # noqa: E402

CACHE = Path(__file__).resolve().parents[1] / "strategy_analysis" / "data"

UNIVERSE = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT", "ADAUSDT",
            "DOGEUSDT", "AVAXUSDT", "LINKUSDT", "DOTUSDT", "LTCUSDT", "ATOMUSDT",
            "FILUSDT", "NEARUSDT", "ETCUSDT", "UNIUSDT", "AAVEUSDT", "ARBUSDT",
            "OPUSDT", "APTUSDT", "SUIUSDT", "XLMUSDT", "BCHUSDT", "TRXUSDT",
            "TONUSDT", "PEPEUSDT", "SHIBUSDT", "PAXGUSDT"]

# Coins with hourly history back to 2020-10-15 or earlier.
#
# WHY THIS EXISTS: the shared-index permutation needs every coin on ONE COMMON
# index, so the MCPT has to intersect. On the 28-coin universe TONUSDT alone
# (listed 2024-08) collapsed that intersection to 4,577 bars - a 190-day test
# whose permuted Sharpe had sd 1.345, i.e. incapable of resolving anything below
# Sharpe ~2.2. The first MCPT run returned p=0.2687 on that stub and it told us
# nothing; it was not a test of the strategy the grid had measured on 45,575 bars.
#
# Restricting to long-history coins gives 21 coins with ~4.5 years of common
# index, and lets the grid and the MCPT run on IDENTICAL data. Use this for any
# comparison between the two.
LONG_UNIVERSE = ["BTCUSDT", "ETHUSDT", "XRPUSDT", "BNBUSDT", "ADAUSDT",
                 "DOGEUSDT", "LINKUSDT", "LTCUSDT", "ATOMUSDT", "ETCUSDT",
                 "XLMUSDT", "BCHUSDT", "TRXUSDT", "SOLUSDT", "DOTUSDT",
                 "PAXGUSDT", "UNIUSDT", "AVAXUSDT", "NEARUSDT", "AAVEUSDT",
                 "FILUSDT"]

HOLDOUT_DAYS = 500      # most recent, untouched until the single final look
TAKER_BP = 6.0          # Bitget taker, per side, on notional traded
DAYS = 2400

# Pre-declared central config.
#
# LOOK #1 (spent) used lb=48 hold=24 k=5 er_min=0.30 invvol - chosen before any
# result was seen, and it was a bad choice for a reason now understood: the
# per-coin Kaufman gate is destructive to a ranking strategy (see weights()).
# Holdout result of look #1, for the record: neutral -12.1%/yr, long-only +12.9%.
#
# LOOK #2 (this one) is declared here from the DEV grid's positive REGION, not
# its argmax: gate off, week-long lookback, daily rebalance, k=5 not k=3 (more
# diversified), equal weight (invvol was consistently worse on dev). Daily
# rebalance is also the operationally realistic choice and costs ~13%/yr in fees
# against ~28%/yr for the 8-hour version.
#
# THIS IS THE LAST LOOK. A third would make this holdout worthless and any
# further work on cross-sectional momentum needs fresh unseen data.
CENTRAL = dict(lb=168, hold=24, k=5, er_min=0.0, invvol=False)

_DISP_CACHE: dict = {}


# ---------------------------------------------------------------- data ------
def funding_history(sym: str) -> pd.Series | None:
    """8h funding settlements. Cached by funding_xs.py's naming convention."""
    f = CACHE / f"funding_{sym}.csv"
    if f.exists():
        d = pd.read_csv(f, parse_dates=["t"])
        return d.set_index("t")["fundingRate"].astype(float)
    out, end = [], int(time.time() * 1000)
    for _ in range(6):
        u = (f"https://fapi.binance.com/fapi/v1/fundingRate?symbol={sym}"
             f"&limit=1000&endTime={end}")
        try:
            r = json.load(urllib.request.urlopen(u, timeout=25))
        except Exception:
            return None
        if not r:
            break
        out = r + out
        end = int(r[0]["fundingTime"]) - 1
        time.sleep(0.2)
    if not out:
        return None
    d = pd.DataFrame(out)
    d["fundingRate"] = d["fundingRate"].astype(float)
    d["t"] = pd.to_datetime(d["fundingTime"], unit="ms")
    d = d[["t", "fundingRate"]].drop_duplicates("t").sort_values("t")
    d.to_csv(f, index=False)
    return d.set_index("t")["fundingRate"]


def build_panel(days: int, universe: list[str] | None = None):
    """Aligned open/close panels plus a funding panel on the same hourly index."""
    op, cl, fr = {}, {}, {}
    for s in (universe or UNIVERSE):
        try:
            d = fetch(s, "1h", days)
        except Exception:
            continue
        d = d.drop_duplicates("time").sort_values("time").set_index("time")
        op[s] = d["open"].astype(float)
        cl[s] = d["close"].astype(float)
        f = funding_history(s)
        if f is not None:
            fr[s] = f
    O = pd.DataFrame(op).sort_index()
    C = pd.DataFrame(cl).sort_index()
    keep = [c for c in O.columns if C[c].notna().sum() > 8000]
    O, C = O[keep], C[keep]
    # funding onto the hourly grid: a settlement is charged on the bar it lands on,
    # every other bar is 0. Never forward-filled - that would charge it 8x.
    F = pd.DataFrame(0.0, index=O.index, columns=O.columns)
    for s in keep:
        if s not in fr:
            continue
        g = fr[s]
        g = g[~g.index.duplicated()]
        aligned = g.reindex(g.index.floor("h")).groupby(level=0).sum()
        common = F.index.intersection(aligned.index)
        F.loc[common, s] = aligned.reindex(common).values
    return O, C, F


# ------------------------------------------------------------ simulation ----
def weights(C: pd.DataFrame, lb: int, hold: int, k: int, er_min: float,
            invvol: bool, long_only: bool = False,
            disp_min: float = 0.0, hedge_index: bool = False,
            reverse: bool = False, rank_by: str = "ret") -> pd.DataFrame:
    """Target weights decided at close[t]. Gross exposure is 1.0x capital.

    Dollar-neutral: +0.5 spread over k longs, -0.5 over k shorts. Long-only
    control puts the full 1.0 on the k longs so the two are risk-comparable in
    gross notional (and therefore in fees).

    er_min: per-coin Kaufman gate. KEPT ONLY AS A CONTROL - measured at
        t = -9 to -25 across all 60 gated configs, i.e. reliably destructive here.
        It filters the pool down to coins already trending cleanly, so the
        bottom-ranked survivor is still rising and we short a live uptrend. The
        filter that MADE the long-only strategy is poison for a ranking strategy.
    disp_min: the correct regime analogue for a ranking strategy - trade only
        when the top-vs-bottom momentum SPREAD is wide enough to be worth paying
        the spread for. Expressed as a rolling percentile so it self-calibrates
        and is scale-free. 0.0 = always trade.

    WEIGHT CONSTRUCTION: rows are assigned explicitly for the whole holding
    window. The earlier version used replace(0)->ffill, which also refilled coins
    that had been DROPPED from the book (0 -> NaN -> ffilled from the old weight),
    so positions outlived their exit and turnover was understated. Found
    2026-09-12; every pre-fix number in this file was wrong.
    """
    mom = C / C.shift(lb) - 1.0
    if rank_by == "sharpe":
        # rank by RISK-ADJUSTED move, so a coin that got there smoothly outranks
        # one that got there on a single violent candle. Different sleeve, not a
        # tweak: it reorders the book, so it is tested as its own strategy.
        rv = C.pct_change().rolling(lb).std()
        mom = mom / rv.replace(0, np.nan)
    if reverse:
        # SHORT-TERM REVERSAL: long the losers, short the winners. Motivated by
        # the leg attribution on the momentum book - once market drift is removed
        # the short-the-losers leg carried ~no alpha, i.e. losers bounce. At short
        # lookbacks that bounce is the effect itself rather than a nuisance, and
        # it should be NEGATIVELY correlated with medium-horizon momentum, which
        # is worth far more in a blend than another positively-correlated sleeve.
        mom = -mom
    if er_min > 0:
        er = pd.DataFrame({c: efficiency_ratio(C[c], lb) for c in C.columns})
        mom = mom.where(er >= er_min)
    if invvol:
        vol = C.pct_change().rolling(max(lb, 48)).std()
        scale = 1.0 / vol.replace(0, np.nan)
    else:
        scale = pd.DataFrame(1.0, index=C.index, columns=C.columns)

    # cross-sectional dispersion, and its own trailing distribution.
    # Vectorised with a row sort and cached: the spread depends only on (lb, k),
    # not on hold/weighting/threshold, so a 120-config grid needs 10 of these.
    # The previous apply(axis=1) version cost ~45k Python calls per config.
    spread = thresh = None
    if disp_min > 0:
        key = (len(C), C.index[0], C.index[-1], lb, k, disp_min)
        if key in _DISP_CACHE:
            spread, thresh = _DISP_CACHE[key]
        else:
            M = mom.to_numpy(dtype=float)
            hi_s = np.sort(np.where(np.isnan(M), -np.inf, M), axis=1)
            lo_s = np.sort(np.where(np.isnan(M), np.inf, M), axis=1)
            top = hi_s[:, -k:].mean(axis=1)
            bot = lo_s[:, :k].mean(axis=1)
            sp = pd.Series(top - bot, index=C.index).replace(
                [np.inf, -np.inf], np.nan)
            th = sp.rolling(24 * 90, min_periods=24 * 30).quantile(disp_min)
            spread, thresh = sp, th
            _DISP_CACHE[key] = (sp, th)

    # Pure-numpy rebalance loop. The pandas version (mom.iloc[t].dropna() /
    # sort_values / sc[hi] per rebalance) cost ~2 minutes PER CONFIG - several
    # hundred microseconds of Series construction x ~5,700 rebalances. Same
    # arithmetic, ~50x faster.
    n = len(C)
    cols = list(C.columns)
    ncol = len(cols)
    Mv = mom.to_numpy(dtype=float)
    Sv = scale.to_numpy(dtype=float)
    Sv = np.where(np.isfinite(Sv) & (Sv > 0), Sv, np.nan)
    spv = spread.to_numpy(dtype=float) if spread is not None else None
    thv = thresh.to_numpy(dtype=float) if thresh is not None else None

    Wa = np.zeros((n, ncol))
    start = max(lb, 48) + 2
    for t in range(start, n, hold):
        if spv is not None:
            if not (np.isfinite(thv[t]) and np.isfinite(spv[t])) or spv[t] < thv[t]:
                continue                      # flat: nothing worth trading
        m = Mv[t]
        vi = np.flatnonzero(np.isfinite(m) & np.isfinite(Sv[t]))
        if len(vi) < 2 * k:
            continue
        order = vi[np.argsort(m[vi], kind="stable")]
        lo_i, hi_i = order[:k], order[-k:]
        sc = Sv[t]
        w = np.zeros(ncol)
        if long_only:
            s = sc[hi_i].sum()
            if s <= 0:
                continue
            w[hi_i] = sc[hi_i] / s
        elif hedge_index:
            # LONG the winners, SHORT an equal-weight index of the whole universe.
            # Motivated by the leg attribution: the short-the-losers leg carries
            # ~no alpha once market drift is removed, yet pays full fees. An index
            # short buys the same beta neutralisation and barely turns over,
            # because its weights are near-identical from one rebalance to the
            # next. Same hedge, a fraction of the cost.
            s = sc[hi_i].sum()
            if s <= 0:
                continue
            w[hi_i] += 0.5 * sc[hi_i] / s
            w[vi] -= 0.5 / len(vi)
        else:
            sl, ss = sc[hi_i].sum(), sc[lo_i].sum()
            if sl <= 0 or ss <= 0:
                continue
            w[hi_i] += 0.5 * sc[hi_i] / sl
            w[lo_i] -= 0.5 * sc[lo_i] / ss
        # hold exactly `hold` bars; a coin not re-selected goes to a TRUE zero
        Wa[t:min(t + hold, n)] = w
    return pd.DataFrame(Wa, index=C.index, columns=cols)


def simulate(O: pd.DataFrame, C: pd.DataFrame, F: pd.DataFrame, *,
             lb: int, hold: int, k: int, er_min: float, invvol: bool,
             fee_bp: float = TAKER_BP, long_only: bool = False,
             charge_funding: bool = True, disp_min: float = 0.0,
             hedge_index: bool = False, reverse: bool = False,
             rank_by: str = "ret") -> dict:
    """Hourly net portfolio returns. Signal at close[t], traded at open[t+1]."""
    W = weights(C, lb, hold, k, er_min, invvol, long_only, disp_min, hedge_index,
                reverse, rank_by)
    # r[t] is the return earned from open[t] to open[t+1]
    r = O.shift(-1) / O - 1.0
    # W is decided at close[t] and is live from open[t+1] -> shift by 1
    Wh = W.shift(1).fillna(0.0)
    rf = r.fillna(0.0)
    gross = (Wh * rf).sum(axis=1)
    # leg attribution: a REAL cross-sectional effect pays on both sides. If only
    # the long leg pays, the "alpha" is just disguised market beta.
    leg_l = (Wh.clip(lower=0) * rf).sum(axis=1)
    leg_s = (Wh.clip(upper=0) * rf).sum(axis=1)
    turn = (Wh - Wh.shift(1).fillna(0.0)).abs().sum(axis=1)
    cost = turn * fee_bp / 1e4
    fund = (Wh * F).sum(axis=1) if charge_funding else pd.Series(0.0, index=gross.index)
    net = gross - cost - fund          # long pays when funding is positive
    net = net.iloc[:-1]                # last bar has no forward return

    live = Wh.abs().sum(axis=1) > 0
    # realised beta to the equal-weight universe: confirms neutrality empirically
    mkt = rf.mean(axis=1).reindex(net.index)
    lv = live.reindex(net.index).fillna(False).to_numpy()
    beta = 0.0
    mv = mkt.to_numpy()[lv]
    nv = net.to_numpy()[lv]
    if lv.sum() > 50 and np.nanstd(mv) > 0:
        beta = float(np.cov(nv, mv)[0, 1] / np.var(mv))
    eq = (1 + net).cumprod()
    dd = float((1 - eq / eq.cummax()).max() * 100) if len(eq) else 0.0
    hrs = max(len(net), 1)
    yrs = hrs / (24 * 365.25)
    cagr = (float(eq.iloc[-1]) ** (1 / yrs) - 1) * 100 if yrs > 0 and len(eq) else 0.0
    nz = net[live]
    sh = (nz.mean() / nz.std(ddof=1) * np.sqrt(24 * 365.25)
          if len(nz) > 10 and nz.std(ddof=1) > 0 else 0.0)
    tstat = (nz.mean() / (nz.std(ddof=1) / np.sqrt(len(nz)))
             if len(nz) > 10 and nz.std(ddof=1) > 0 else 0.0)
    mo = net.resample("30D").sum() * 100
    return dict(cagr=cagr, dd=dd, sharpe=float(sh), t=float(tstat),
                mar=cagr / dd if dd > 0.5 else 0.0,
                beta=beta,
                leg_l=float(leg_l.sum() / max(yrs, 1e-9) * 100),
                leg_s=float(leg_s.sum() / max(yrs, 1e-9) * 100),
                n_hours=int(live.sum()),
                turn_day=float(turn[live].mean() * 24) if live.any() else 0.0,
                fee_yr=float(cost.sum() / max(yrs, 1e-9) * 100),
                fund_yr=float(fund.sum() / max(yrs, 1e-9) * 100),
                gross_yr=float(gross.sum() / max(yrs, 1e-9) * 100),
                mo_med=float(mo.median()) if len(mo) else 0.0,
                mo_pos=float((mo > 0).mean() * 100) if len(mo) else 0.0,
                mo_over10=float((mo > 10).mean() * 100) if len(mo) else 0.0,
                eq=eq, net=net)


def line(tag, s):
    return (f"{tag:<26} {s['cagr']:>+8.1f}%/yr {s['dd']:>6.1f}%DD "
            f"{s['mar']:>+6.2f}MAR {s['sharpe']:>+6.2f}Sh {s['t']:>+6.2f}t "
            f"| gross{s['gross_yr']:>+7.1f} fee{s['fee_yr']:>6.1f} "
            f"fund{s['fund_yr']:>+6.1f} | legL{s['leg_l']:>+7.1f} "
            f"legS{s['leg_s']:>+7.1f} beta{s['beta']:>+6.2f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=DAYS)
    ap.add_argument("--fee", type=float, default=TAKER_BP)
    args = ap.parse_args()

    O, C, F = build_panel(args.days)
    cut = O.index[-1] - pd.Timedelta(days=HOLDOUT_DAYS)
    dev = slice(None, cut)
    hld = slice(cut, None)
    print(f"CROSS-SECTIONAL MOMENTUM (market-neutral)   {len(C.columns)} coins")
    print(f"  DEV     {C.index[0]:%Y-%m-%d} .. {cut:%Y-%m-%d}  "
          f"({len(C.loc[dev]):,} hourly bars)")
    print(f"  HOLDOUT {cut:%Y-%m-%d} .. {C.index[-1]:%Y-%m-%d}  "
          f"({len(C.loc[hld]):,} bars)  <- ONE look, at the end")
    # coverage measured in BARS, not coins: "25/28 coins have some funding data"
    # is worthless when the archive only reaches back over the tail of the window.
    def fcov(w):
        sub = F.loc[w]
        return float((sub != 0).any(axis=1).mean() * 100)
    cd, ch = fcov(dev), fcov(hld)
    print(f"  funding coverage: DEV {cd:.0f}% of bars, HOLDOUT {ch:.0f}% of bars")
    if cd < 60:
        print(f"  WARNING: the funding archive only reaches back ~670 days, so only "
              f"{cd:.0f}% of DEV\n           bars carry funding. A small dev 'fund' "
              f"column means MISSING DATA, not\n           zero cost. The HOLDOUT "
              f"number ({ch:.0f}% covered) is the real measurement.")
    print(f"  cost {args.fee}bp/side taker on actual turnover\n")

    Od, Cd, Fd = O.loc[dev], C.loc[dev], F.loc[dev]

    # ---- DEV GRID. The question is whether the whole space is positive, not
    # ---- whether some cell is. One good cell out of 120 is noise.
    print("=" * 104)
    print("DEV GRID — market-neutral long/short")
    print("=" * 104)
    print(f"{'lb':>4} {'hold':>5} {'k':>3} {'disp':>5} {'wt':>7} | "
          f"{'CAGR':>8} {'DD':>7} {'MAR':>6} {'Sharpe':>7} {'t':>6} "
          f"{'trn/d':>6} {'fee/y':>6} {'legL':>7} {'legS':>7} {'beta':>6}")
    rows = []
    for lb, hold, k, dmin, iv in itertools.product(
            (12, 24, 48, 96, 168), (8, 24, 48), (3, 5), (0.0, 0.50), (True, False)):
        s = simulate(Od, Cd, Fd, lb=lb, hold=hold, k=k, er_min=0.0,
                     invvol=iv, fee_bp=args.fee, disp_min=dmin)
        rows.append((s["sharpe"], dict(lb=lb, hold=hold, k=k, disp_min=dmin,
                                       invvol=iv), s))
        print(f"{lb:>4} {hold:>5} {k:>3} {dmin:>5.2f} "
              f"{'invvol' if iv else 'equal':>7} | "
              f"{s['cagr']:>+7.1f}% {s['dd']:>6.1f}% {s['mar']:>+6.2f} "
              f"{s['sharpe']:>+7.2f} {s['t']:>+6.2f} {s['turn_day']:>6.2f} "
              f"{s['fee_yr']:>6.1f} {s['leg_l']:>+7.1f} {s['leg_s']:>+7.1f} "
              f"{s['beta']:>+6.2f}", flush=True)

    pos = sum(1 for sh, _, _ in rows if sh > 0)
    print(f"\nGRID ROBUSTNESS: {pos}/{len(rows)} configs have positive Sharpe "
          f"({pos/len(rows)*100:.0f}%). Coin-flip expectation is 50%.")
    shs = np.array([sh for sh, _, _ in rows])
    print(f"  Sharpe distribution: median {np.median(shs):+.2f}  "
          f"p25 {np.percentile(shs,25):+.2f}  p75 {np.percentile(shs,75):+.2f}  "
          f"max {shs.max():+.2f}")

    # ---- CONTROLS on dev: is neutralisation doing the work, and is funding
    # ---- the thing that kills it?
    print("\n" + "=" * 104)
    print("DEV CONTROLS at the pre-declared central config "
          f"(lb={CENTRAL['lb']} hold={CENTRAL['hold']} k={CENTRAL['k']} "
          f"gate={CENTRAL['er_min']})")
    print("=" * 104)
    base = simulate(Od, Cd, Fd, **CENTRAL, fee_bp=args.fee)
    print(line("neutral L/S", base))
    print(line("LONG-ONLY (control)",
               simulate(Od, Cd, Fd, **CENTRAL, fee_bp=args.fee, long_only=True)))
    print(line("neutral, zero fees",
               simulate(Od, Cd, Fd, **CENTRAL, fee_bp=0.0)))
    print(line("neutral, maker 2bp",
               simulate(Od, Cd, Fd, **CENTRAL, fee_bp=2.0)))
    print(line("+ Kaufman gate 0.30",
               simulate(Od, Cd, Fd, **{**CENTRAL, "er_min": 0.30},
                        fee_bp=args.fee)))
    print(line("+ dispersion gate p50",
               simulate(Od, Cd, Fd, **CENTRAL, fee_bp=args.fee, disp_min=0.50)))
    print(line("k=3 (concentrated)",
               simulate(Od, Cd, Fd, **{**CENTRAL, "k": 3}, fee_bp=args.fee)))
    print(line("hold=8 (3x/day)",
               simulate(Od, Cd, Fd, **{**CENTRAL, "hold": 8}, fee_bp=args.fee)))
    print()
    print("  INDEX-HEDGED variant: long the winners, short an equal-weight index")
    print("  instead of shorting the losers (see leg attribution above).")
    for kk in (3, 5):
        for hh in (8, 24, 48):
            print(line(f"  idx-hedge k={kk} hold={hh}",
                       simulate(Od, Cd, Fd, **{**CENTRAL, "k": kk, "hold": hh},
                                fee_bp=args.fee, hedge_index=True)))

    # ---- HOLDOUT: exactly one config, exactly once.
    print("\n" + "=" * 104)
    print("HOLDOUT — most recent 500 days, never touched. ONE config, ONE look.")
    print("=" * 104)
    Oh, Ch, Fh = O.loc[hld], C.loc[hld], F.loc[hld]
    h = simulate(Oh, Ch, Fh, **CENTRAL, fee_bp=args.fee)
    hl = simulate(Oh, Ch, Fh, **CENTRAL, fee_bp=args.fee, long_only=True)
    print(line("neutral L/S  HOLDOUT", h))
    print(line("long-only    HOLDOUT", hl))
    print(f"\n  30-day blocks: median {h['mo_med']:+.2f}%   "
          f"positive {h['mo_pos']:.0f}%   above +10% {h['mo_over10']:.0f}%")
    print(f"  hours in market {h['n_hours']:,}   turnover {h['turn_day']:.2f}x/day")

    print("\n" + "-" * 104)
    ok = (pos / len(rows) >= 0.70 and base["sharpe"] > 0.5
          and h["sharpe"] > 0.3 and h["cagr"] > 0)
    print(f"VERDICT: {'worth the full gate battery (MCPT + cross-asset)' if ok else 'does NOT clear the bar'}")
    print("  needs: >=70% of grid positive, dev Sharpe >0.5, holdout Sharpe >0.3, "
          "holdout CAGR >0")
    print(f"  got:   {pos/len(rows)*100:.0f}% grid, dev {base['sharpe']:+.2f}, "
          f"holdout {h['sharpe']:+.2f}, holdout CAGR {h['cagr']:+.1f}%")


if __name__ == "__main__":
    main()
