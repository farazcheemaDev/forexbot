"""IS THE RESULT AN ARTIFACT OF WHERE THE BARS HAPPEN TO START? - and can that be harvested.

THE ARBITRARY CHOICE NOBODY HAS QUESTIONED
    Every figure in this project's 4h and 12h sleeves comes from bars anchored to midnight UTC.
    A 4h bar could equally start at 01:00, 02:00 or 03:00, and a 12h bar at any of twelve hours.
    Nothing in the strategy says which. The choice is an implementation accident inherited from
    how Binance labels klines.

    That matters twice over:

    1. AS A ROBUSTNESS CHECK. If shifting the phase moves the result by several %/month, then
       part of the deployed number is luck about bar boundaries, and the honest expectation is
       the average over phases rather than the one phase that happens to be running.
    2. AS A FREE DIVERSIFIER. Four phase-shifted books trade the same rule on the same coins at
       the same risk, but see different bars, so their signals only partly overlap. Splitting the
       account across them cannot change the average edge - it can only reduce the variance
       around it. Less variance at the same mean is MORE compounded growth, because volatility
       drag falls. That is the one way left in this repo to raise return without raising risk.

    No new data, no new universe, no new rule. Only the 1h bars already cached, resampled with
    an offset.

WHAT IS HELD FIXED
    The 1h sleeve cannot be phase-shifted without sub-hourly data, and only 23 coins have any,
    so it is identical in every variant. SHORTS are also identical in every variant (their
    builder is not phase-aware), which is fine because they are a hedge that loses money by
    design - so any difference measured here is attributable purely to the 4h and 12h LONG
    sleeves, which is where the profit is.

    causal_t0.real_t0 subtracts a fixed (bar duration - 1h) per rule. That offset does not
    depend on the phase - a right-labelled bar's open is always that far before its label - so
    the mistake #12 correction stays valid for shifted bars.

    Scored on the corrected engine throughout: entry-sized compounding, funding charged, causal
    entry times, 10 orderings, 3x haircut, tune/holdout as everywhere else.

REGISTERED PREDICTIONS (before the run, 2026-09-23)
    1. The spread across phases on the holdout is at least 1.5%/month, i.e. the deployed number
       carries material phase luck.
    2. Phase 0 - the deployed one - is NOT the best of the four. It has no reason to be.
    3. The 4-phase blend returns about the phase MEAN, not the phase max, with a LOWER drawdown
       than the average phase, so its Sharpe is higher than any single phase.
    4. The blend's COMPOUNDED return slightly EXCEEDS the mean of the phases' compounded
       returns, because averaging four noisy series before compounding removes volatility drag.
       If 4 fails, the diversification is cosmetic and only the robustness reading survives.

    python -m backtest.bar_phase
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import blend  # noqa: E402
from backtest.bear_side import sleeve_sided  # noqa: E402
from backtest.bull_boost import regimes  # noqa: E402
from backtest.causal_t0 import real_t0  # noqa: E402
from backtest.engine_variants import shorts_for  # noqa: E402
from backtest.funding_cost import charged, long_funding, short_funding  # noqa: E402
from backtest.graveyard_rescore import walk  # noqa: E402
from backtest.kelly_corrected import simulate  # noqa: E402
from backtest.mtm_sizing import attach_prices  # noqa: E402
from backtest.small_capital import price_maps  # noqa: E402
from backtest.timeframes import resample  # noqa: E402

SEEDS = tuple(range(10))
PHASES = (0, 1, 2, 3)          # 4h offset = p hours, 12h offset = 3p hours
RISK = blend.RISK


def resample_phase(df, rule, hours):
    """1h -> rule, with the bar grid shifted `hours` forward. hours=0 is the deployed grid.

    Same aggregation as timeframes.resample - first open, max high, min low, last close - and
    the same right label and right-closed interval, so only the boundaries move."""
    if hours == 0:
        return resample(df, rule)
    d = df.set_index("time")
    out = d.resample(rule, label="right", closed="right", offset=f"{hours}h").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last",
         "volume": "sum"}).dropna()
    return out.reset_index()


def rows_for_phase(p):
    """Every row of the deployed book with the 4h and 12h LONG sleeves on phase p."""
    rows = []
    for rule, off in (("1h", 0), ("4h", p), ("12h", 3 * p)):
        rows += shorts_for(rule)                    # identical in every phase, see docstring
        for coin in blend.BOOK:
            d = blend.load(coin)
            if d is None:
                continue
            df = resample_phase(d, rule, off if rule != "1h" else 0)
            if len(df) >= 300:
                rows += walk(df, rule, coin)
    def rs(coin, rule):
        """attach_prices must price entries on the SAME grid the rows were walked on, or a
        shifted t0 is not a bar label it recognises (it raised KeyError on 13:00, which is not
        on the deployed 4h grid)."""
        return resample_phase(blend.load(coin), rule, 0 if rule == "1h"
                              else (p if rule == "4h" else 3 * p))
    return charged(real_t0(short_funding(long_funding(attach_prices(rows, rs)))))


def daily(rows, bear, seed, t_from=None, t_to=None):
    r = simulate(rows, bear, seed, RISK, t_from=t_from, t_to=t_to)
    if r is None:
        return None
    return r["curve"].pct_change().replace([np.inf, -np.inf], np.nan).fillna(0.0)


def stats(ret):
    """Geometric %/month after the 3x haircut, drawdown and Sharpe from a daily series."""
    if ret is None or len(ret) < 50:
        return None
    cur = np.cumprod(1 + ret.to_numpy())
    yrs = max((ret.index[-1] - ret.index[0]).days / 365.25, 0.1)
    cagr = max(cur[-1], 1e-12) ** (1 / yrs) - 1
    hc = cagr / blend.HINDSIGHT
    dd = float((1 - cur / np.maximum.accumulate(cur)).max() * 100)
    sd = ret.std(ddof=1)
    return dict(hpm=((1 + hc) ** (1 / 12) - 1) * 100 if hc > -1 else -100.0, dd=dd,
                sharpe=float(ret.mean() / sd * np.sqrt(365)) if sd else np.nan,
                mult=float(cur[-1]))


def agg(list_of):
    good = [x for x in list_of if x]
    if not good:
        return None
    return {k: float(np.median([g[k] for g in good])) for k in good[0]}


def simulate_floor(rows, bear, seed, risk_pct, capital, px, step, t_from=None, t_to=None):
    """Entry-sized compounding WITH the venue minimum enforced, in dollars.

    This is the test the blend has to pass before it can be used at $200. Four books at a
    quarter of the capital each means every unit is a quarter the size, and unit notional =
    dollars_at_risk / stop_fraction. The 12h sleeve has the widest stops, so it produces the
    smallest notionals and is where rejections land first.

    The contract step is recovered in COIN units from today's minimum and today's price, as
    small_capital.py does, because MEXC's minimum is a fixed number of coins and its dollar
    value tracked the coin's price - using today's dollar minimum across 2021 would understate
    it badly."""
    rng = np.random.default_rng(seed)
    tie = rng.random(len(rows))
    o = [rows[i] for i in sorted(range(len(rows)), key=lambda i: (rows[i]["t0"], tie[i]))]
    eq, open_, pts = capital, [], []
    taken = skipped = 0

    def bank(upto):
        nonlocal eq, open_
        keep = []
        for q in sorted(open_, key=lambda z: z["t1"]):
            if q["t1"] <= upto:
                eq = max(eq + q["dpr"] * q["R"], 0.0)
                pts.append((q["t1"], eq))
            else:
                keep.append(q)
        open_ = keep

    for r in o:
        t0 = pd.Timestamp(r["t0"])
        if (t_from is not None and t0 < t_from) or (t_to is not None and t0 >= t_to):
            continue
        bank(t0)
        if len(open_) >= 12:
            continue
        try:
            ib = bool(bear.asof(t0))
        except Exception:
            ib = False
        f = risk_pct / 100.0 * (blend.REGIME_MULT if ib else 1.0)
        risk_usd = eq * f
        notional = risk_usd / max(r["sf"], 1e-6)
        coin = r["coin"]
        price = px[coin].asof(t0) if coin in px else np.nan
        floor = step.get(coin, 0.0) * (price if np.isfinite(price) else 0.0)
        if notional < floor:
            skipped += 1
            continue
        taken += 1
        open_.append(dict(r, t1=pd.Timestamp(r["t1"]), dpr=risk_usd))
    bank(pd.Timestamp("2100-01-01"))
    if len(pts) < 20:
        return None
    s_ = pd.Series([q[1] for q in pts], index=pd.DatetimeIndex([q[0] for q in pts]))
    cur = (s_.resample("D").last().ffill()) / capital
    return dict(ret=cur.pct_change().replace([np.inf, -np.inf], np.nan).fillna(0.0),
                taken=taken, skipped=skipped)


def floor_check(rows, bear, cut):
    """Does quartering the unit size break the book at $200? The question Part 5 left open."""
    px, step = price_maps()
    print()
    print("THE $200 QUESTION - venue minimum enforced, unit size quartered by the blend")
    print(f"  {'setup':<34}{'capital/book':>13}{'rejected':>10}{'HOLD/mo':>10}{'DD':>6}")
    out = {}
    for lab, nbooks in (("1 phase (deployed)", 1), ("4 phases, quarter each", 4)):
        for cap in (200.0, 1000.0, 5000.0):
            rets, rej = [], []
            for i, seed in enumerate(SEEDS):
                parts = []
                for p in (PHASES[:1] if nbooks == 1 else PHASES):
                    r = simulate_floor(rows[p], bear, seed, RISK, cap / nbooks, px, step,
                                       t_from=cut)
                    if r is None:
                        break
                    parts.append(r)
                if len(parts) != nbooks:
                    continue
                df = pd.concat([x["ret"] for x in parts], axis=1).fillna(0.0)
                rets.append(df.mean(axis=1))
                tk = sum(x["taken"] for x in parts); sk = sum(x["skipped"] for x in parts)
                rej.append(sk / max(tk + sk, 1) * 100)
            st = agg([stats(x) for x in rets])
            out[(lab, cap)] = st
            print(f"  {lab:<34}{cap/nbooks:>12,.0f}{np.mean(rej):>9.0f}%"
                  f"{st['hpm']:>+9.2f}%{st['dd']:>5.0f}%")
    print("  A rejection rate that jumps from ~0% to double digits is the blend being")
    print("  unaffordable, not the rule failing.")
    return out


def main():
    bear = regimes()[1000]
    ts = pd.DatetimeIndex(sorted(x[0] for x in sleeve_sided("1h")[0]))
    cut = ts[int(len(ts) * 0.6)]
    print(f"{len(PHASES)} bar phases | {len(SEEDS)} orderings | 3x haircut | "
          f"tune < {cut:%Y-%m-%d} <= holdout")
    print("1h sleeve and ALL shorts identical in every phase - only 4h/12h longs move")

    rows = {}
    for p in PHASES:
        rows[p] = rows_for_phase(p)
        print(f"  phase {p}: 4h offset {p}h, 12h offset {3*p}h -> {len(rows[p])} trades")

    series = {"tune": {}, "hold": {}, "full": {}}
    print()
    print(f"  {'phase':<8}{'TUNE/mo':>10}{'DD':>6}{'HOLD/mo':>10}{'DD':>6}"
          f"{'FULL/mo':>10}{'DD':>6}{'Sharpe':>8}")
    for p in PHASES:
        for win, kw in (("tune", dict(t_to=cut)), ("hold", dict(t_from=cut)),
                        ("full", {})):
            series[win][p] = [daily(rows[p], bear, s, **kw) for s in SEEDS]
        t = agg([stats(x) for x in series["tune"][p]])
        h = agg([stats(x) for x in series["hold"][p]])
        f = agg([stats(x) for x in series["full"][p]])
        tag = "  <- DEPLOYED" if p == 0 else ""
        print(f"  {p:<8}{t['hpm']:>+9.2f}%{t['dd']:>5.0f}%{h['hpm']:>+9.2f}%{h['dd']:>5.0f}%"
              f"{f['hpm']:>+9.2f}%{f['dd']:>5.0f}%{f['sharpe']:>8.2f}{tag}")

    for win in ("tune", "hold", "full"):
        vals = [agg([stats(x) for x in series[win][p]])["hpm"] for p in PHASES]
        print(f"  phase spread on {win:<5} {max(vals) - min(vals):>5.2f} %/mo "
              f"(best phase {PHASES[int(np.argmax(vals))]}, worst {PHASES[int(np.argmin(vals))]})")

    # ---- the blend: a quarter of the account in each phase ----------------------------
    print()
    print("BLENDED BOOK - a quarter of the account in each phase, same total risk")
    print(f"  {'window':<8}{'blend/mo':>10}{'DD':>6}{'Sharpe':>8}{'mean phase/mo':>15}"
          f"{'mean phase DD':>15}{'mean Sharpe':>13}")
    for win in ("tune", "hold", "full"):
        blends = []
        for i in range(len(SEEDS)):
            parts = [series[win][p][i] for p in PHASES if series[win][p][i] is not None]
            if len(parts) < len(PHASES):
                continue
            df = pd.concat(parts, axis=1).fillna(0.0)
            blends.append(df.mean(axis=1))
        b = agg([stats(x) for x in blends])
        per = [agg([stats(x) for x in series[win][p]]) for p in PHASES]
        mh = float(np.mean([x["hpm"] for x in per]))
        md = float(np.mean([x["dd"] for x in per]))
        ms = float(np.mean([x["sharpe"] for x in per]))
        print(f"  {win:<8}{b['hpm']:>+9.2f}%{b['dd']:>5.0f}%{b['sharpe']:>8.2f}"
              f"{mh:>+14.2f}%{md:>14.0f}%{ms:>13.2f}")

    floor_check(rows, bear, cut)

    print()
    print("  Prediction 4 is the one that matters: the blend's COMPOUNDED return should beat")
    print("  the mean phase because averaging before compounding removes volatility drag. If")
    print("  it does not, phase diversification is cosmetic and only the robustness reading")
    print("  survives - and that reading is the phase spread above.")


if __name__ == "__main__":
    main()
