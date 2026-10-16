"""WHAT DRIVES FOREX, 1996-2026 - and does any of it PREDICT the next move after Exness's costs? (2026-10-12)

THE USER (2026-10-12, /goal): "run these economic data and all other data that drives forex and correlation with them -
the last 30 years would be enough". Data: backtest/fx_macro_data.py (Fed H.10 noon rates, H.15 yields, BIS policy rates,
OECD 3-month / 10-year rates, CFTC positioning, VIX / S&P 500 / oil / gold / copper; the ForexFactory calendar is used by
fx_surprises.py). Seven currencies against the dollar: EUR (from 1999), JPY, GBP, AUD, NZD, CAD, CHF; a return is the
FOREIGN currency's move in dollars (up = it rose).

TWO DIFFERENT QUESTIONS, kept apart
    A  MOVES WITH: the correlation of each driver's change with the currency's move IN THE SAME MONTH. This is "what
       drives forex" - but it is known only afterwards, so it cannot be traded.
    B  PREDICTS: the driver up to the end of one period against the currency's move in the NEXT. Only this can be
       traded. Periods start at the H.10 noon fix of the first business day (month / Monday) and signals use data dated
       on or before the previous business day, so nothing is read before the trade.
RULES (part B), each a position per currency in {-1, 0, +1} against the dollar, equal weight, or cross-sectional:
    CARRY        long the 2 highest policy-rate currencies, short the 2 lowest (dollar included as a currency) - monthly
    RATE CHANGE  long a currency whose policy-rate gap to the US widened over the last 3 months, short if it narrowed
    LONG RATES   the same on the 10-year gap (EUR JPY AUD NZD CAD; the OECD has no GBP / CHF series)
    US 2Y        all currencies short when the US 2-year yield rose last month, long when it fell
    COT CROWD    weekly: speculators' net position (% of open interest), z-score over 156 weeks; |z| > 1.5 -> fade it
    COT FLOW     weekly: last week's change in that net position -> follow it
    RISK         weekly: last week's S&P 500 return x each currency's risk sign (AUD NZD CAD +, JPY CHF -, EUR GBP 0)
    COMMODITY    monthly: oil -> CAD, copper -> AUD, gold -> AUD (from 2000)
    MOMENTUM     monthly: the sign of the last 1 / 3 / 12 months (the baseline: fx_tsmom.py found FX momentum ~0)
RETURN VERSIONS
    SPOT         the exchange-rate move only
    +CARRY       spot plus the policy-rate gap earned or paid (what a futures / forward / interbank trader gets)
    EXNESS       spot minus Exness's spread on every position change and TODAY's swap for each side held each night
                 (EURUSD long -0.51bp, USDJPY short -0.88bp, ...; Exness pays no carry on either side). The verdict.
PASS     EXNESS net > 0 with t >= 2 on BOTH halves (60/40 by date) and Holm p < 0.05 across every rule.

REGISTERED BEFORE THE RUN (2026-10-12)
    P1  MOVES WITH is strong: the 3-month change in the policy gap correlates >= +0.2 with most currencies' same-month
        move; AUD / NZD / CAD move with the S&P (>= +0.3) and JPY / CHF against it; CAD with oil (>= +0.3, 2000+).
    P2  PREDICTS is weak: every one-period-ahead |correlation| is under 0.10.
    P3  CARRY: +CARRY positive on both halves with a worst month <= -5% (2008); EXNESS (no carry) <= 0.
    P4  COT CROWD positive but t < 2 on at least one half; COT FLOW ~0.
    P5  No rule PASSES on EXNESS.

RESULT (2026-10-12 01:10 UTC, logs/fx_drivers.txt; 368 months / 1,600 weeks, 1996-2026)
    A. WHAT MOVES WITH FOREX (same month): risk and commodities, and MARKET interest rates - not central-bank rates.
       - S&P 500: AUD +0.52, CAD +0.51, NZD +0.46, GBP +0.32, EUR +0.29 (JPY -0.03, CHF +0.10); VIX the mirror (-0.40..-0.48).
       - copper +0.36..+0.53 and gold +0.25..+0.43 on every currency but JPY; oil -> CAD +0.38, AUD +0.34.
       - the US 2-year yield: when it rises the dollar rises (JPY -0.40, CHF -0.29, EUR -0.22); the 10-year gap JPY +0.31,
         AUD +0.25.
       - P1 WRONG on its first leg: the change in the POLICY-rate gap moves with nothing (-0.05..+0.05) - central banks move
         in expected steps; the market prices the 2-year yield ahead of them. Right on risk and oil (CAD +0.38).
    B. WHAT PREDICTS FOREX (next month): nothing. 77 driver-currency correlations, all between -0.13 and +0.12 (P2 WRONG by
       a hair: the largest, S&P -> CHF -0.13, is one of 77 and ~2.5 se). Last month's policy, 2y, 10y, S&P, VIX, oil,
       copper, gold, positioning and the currency's own past all fail to say where it goes next.
    TRADING RULES (Exness costs): 0 of 11 pass (P5 RIGHT); every Holm p 1.00.
       - CARRY earns the textbook premium only where carry is PAID: +2.6%/yr with the rate gap (t +2.0 / +1.4 by half), worst
         month -10.7%; at Exness, which pays no carry, -0.26%/yr (P3 RIGHT).
       - COMMODITY (oil -> CAD, copper -> AUD): +0.74%/yr at Exness, tune +, holdout - : flips.
       - COT CROWD (fade extreme speculator positioning): -1.9%/yr, the wrong sign on the tune half (P4 WRONG).
       - momentum 1/3/12 months, rate changes, US 2y, risk, COT flow: all negative after costs.
    Reading: thirty years of the data that DRIVES forex explain a large share of each month's move - after the fact. None
    of it, known at the start of a month or week, predicts the next one; the only premium (carry) is the one Exness keeps.

    python -m backtest.fx_drivers
"""
from __future__ import annotations

import sys
from math import erf, sqrt
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest import fx_macro_data as md  # noqa: E402

LOG = ROOT / "logs" / "fx_drivers.txt"
CCY = md.CCY
TUNE = 0.60
#           spread bp RT, swap bp/night LONG the foreign ccy, SHORT it (Exness, mt5.symbol_info 2026-10-12)
COST = {"EUR": (1.0, -0.51, 0.00), "GBP": (1.0, -0.17, -0.04), "JPY": (1.0, -0.88, 0.00), "AUD": (1.3, 0.00, -0.27),
        "NZD": (2.5, -0.64, 0.00), "CAD": (1.2, -0.81, 0.00), "CHF": (1.6, -1.25, 0.00)}
RISK_SIGN = {"AUD": 1, "NZD": 1, "CAD": 1, "JPY": -1, "CHF": -1, "EUR": 0, "GBP": 0}


# ---------------------------------------------------------------- data on period grids

def period_starts(idx: pd.DatetimeIndex, freq: str) -> pd.DatetimeIndex:
    """first available H.10 day of each month (M) or week starting Monday (W)."""
    s = pd.Series(idx, index=idx)
    key = idx.to_period("M") if freq == "M" else idx.to_period("W-SUN")
    return pd.DatetimeIndex(s.groupby(key).first().values)


def grid(freq: str):
    fx = md.load("fx_h10.csv")[CCY].dropna(how="all")
    fx = fx[fx.index >= "1996-01-01"]
    starts = period_starts(fx.index, freq)
    px = fx.reindex(starts).ffill(limit=3)
    ret = px.shift(-1) / px - 1                                  # return over the period that STARTS at each date
    nights = pd.Series((starts[1:] - starts[:-1]).days.tolist() + [np.nan], index=starts)
    return starts, ret, nights


def asof(series: pd.DataFrame | pd.Series, starts: pd.DatetimeIndex):
    """the last value dated strictly BEFORE each period start (known before the noon fix)."""
    s = series.sort_index()
    pos = s.index.searchsorted(starts, side="left") - 1
    vals = s.iloc[np.clip(pos, 0, None)]
    vals.index = starts
    if isinstance(vals, pd.DataFrame):
        vals[pos < 0] = np.nan
    else:
        vals[pos < 0] = np.nan
    return vals


def policy_gap(starts):
    p = md.load("policy_bis.csv").ffill()
    g = pd.DataFrame({c: p[c] - p["USD"] for c in CCY})
    lvl = asof(g, starts)
    return lvl, asof(p, starts)


# ---------------------------------------------------------------- returns of a rule

def run(pos: pd.DataFrame, ret: pd.DataFrame, nights: pd.Series, rates: pd.DataFrame | None):
    """pos: positions per currency at each period start (+1 long foreign). Returns per-period portfolio series for SPOT,
    +CARRY and EXNESS (mean over currencies with a position; 0 when flat)."""
    pos = pos.reindex(ret.index).fillna(0.0)
    valid = ret.notna()
    pos = pos.where(valid, 0.0)
    n_on = (pos != 0).sum(axis=1).replace(0, np.nan)
    spot = (pos * ret.fillna(0)).sum(axis=1) / n_on
    turn = (pos - pos.shift(1).fillna(0)).abs()
    sp = pd.Series({c: COST[c][0] for c in CCY})
    swap_l = pd.Series({c: COST[c][1] for c in CCY})
    swap_s = pd.Series({c: COST[c][2] for c in CCY})
    swap = (pos.clip(lower=0) * swap_l + (-pos).clip(lower=0) * swap_s).mul(nights, axis=0) / 1e4
    ex = ((pos * ret.fillna(0)) - turn * sp / 2 / 1e4 + swap).sum(axis=1) / n_on
    if rates is not None:
        gap = pd.DataFrame({c: rates[c] - rates["USD"] for c in CCY}).reindex(ret.index)
        carry = (pos * gap.fillna(0) / 100 / 365).mul(nights, axis=0)
        cr = ((pos * ret.fillna(0)) + carry).sum(axis=1) / n_on
    else:
        cr = spot
    keep = n_on.notna() & ret.notna().any(axis=1)
    return spot[keep].dropna(), cr[keep].dropna(), ex[keep].dropna()


def xs(signal: pd.DataFrame, k=2, with_usd=True):
    """cross-sectional: long the top k, short the bottom k (the dollar counts as a currency with signal 0 when
    with_usd). Positions in foreign currency vs USD; a long-short pair X/Y appears as +1 X, -1 Y."""
    out = pd.DataFrame(0.0, index=signal.index, columns=signal.columns)
    for t, row in signal.iterrows():
        r = row.dropna()
        if with_usd:
            r = pd.concat([r, pd.Series({"USD": 0.0})])
        if len(r) < 2 * k + 1:
            continue
        o = r.sort_values(kind="stable")
        for c in o.index[-k:]:
            if c != "USD":
                out.at[t, c] += 1
        for c in o.index[:k]:
            if c != "USD":
                out.at[t, c] -= 1
    return out


def stat(x: pd.Series, periods_per_year: float):
    x = x.dropna()
    cut = x.index[int(len(x) * TUNE)]
    a, b = x[x.index < cut], x[x.index >= cut]
    t = lambda y: y.mean() / (y.std(ddof=1) / np.sqrt(len(y))) if len(y) > 2 and y.std(ddof=1) > 0 else np.nan  # noqa: E731
    return dict(n=len(x), mean=x.mean(), t=t(x), tu=a.mean(), t_tu=t(a), ho=b.mean(), t_ho=t(b),
                ann=x.mean() * periods_per_year, worst=x.min(), cut=cut,
                p=1 - 0.5 * (1 + erf(t(x) / sqrt(2))) if np.isfinite(t(x)) else 1.0)


# ---------------------------------------------------------------- the analysis

def main():
    lines = [f"backtest/fx_drivers.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; Fed H.10 noon rates 1996-2026, "
             f"7 currencies vs USD (up = the foreign currency rose); Exness costs as of 2026-10-12", ""]
    mstarts, mret, mn = grid("M")
    wstarts, wret, wn = grid("W")
    _, pol_m = policy_gap(mstarts)
    gap_m, _ = policy_gap(mstarts)
    _, pol_w = policy_gap(wstarts)
    mk = md.load("markets_yahoo.csv")
    ust = md.load("ust_h15.csv")
    oe = md.load("oecd_rates.csv")
    cot = md.load("cot.csv")

    # ----- A: MOVES WITH (same month) -----
    lines.append("A. MOVES WITH - correlation of each driver's change with the currency's move IN THE SAME MONTH (1996-2026;"
                 " commodities 2000+). Not tradable: known only afterwards.")
    gap_next = gap_m.shift(-1)                                   # gap at the END of the period (next start)
    d_gap = gap_next - gap_m
    lt = {c: oe[f"lt_{c}"] - oe["lt_USD"] for c in CCY if f"lt_{c}" in oe.columns}
    lt_m = asof(pd.DataFrame(lt), mstarts)
    d_lt = lt_m.shift(-1) - lt_m
    m_end = lambda s: asof(s, mstarts)                           # noqa: E731
    spx, vix = m_end(mk["^GSPC"]), m_end(mk["^VIX"])
    r_spx, d_vix = spx.shift(-1) / spx - 1, vix.shift(-1) - vix
    oil, cop, gold = m_end(mk["CL=F"]), m_end(mk["HG=F"]), m_end(mk["GC=F"])
    r_oil, r_cop, r_gold = oil.shift(-1) / oil - 1, cop.shift(-1) / cop - 1, gold.shift(-1) / gold - 1
    us2 = m_end(ust["2y"])
    d_us2 = us2.shift(-1) - us2
    drivers_same = {"policy-gap change": d_gap, "10y-gap change": d_lt, "US 2y change": d_us2, "S&P 500": r_spx,
                    "VIX change": d_vix, "oil": r_oil, "copper": r_cop, "gold": r_gold}
    hdr = f"  {'driver':20}" + "".join(f"{c:>7}" for c in CCY)
    lines.append(hdr)
    corr_same = {}
    for nm, drv in drivers_same.items():
        row = f"  {nm:20}"
        for c in CCY:
            if isinstance(drv, pd.DataFrame) and c not in drv.columns:
                row += f"{'':>7}"
                continue
            x = drv[c] if isinstance(drv, pd.DataFrame) else drv
            j = pd.concat([x.rename("x"), mret[c].rename("y")], axis=1).dropna()
            r = j.x.corr(j.y) if len(j) > 24 else np.nan
            corr_same[(nm, c)] = r
            row += f"{r:+7.2f}"
        lines.append(row)
    lines.append("")

    # ----- B: PREDICTS (next month) correlation table -----
    lines.append("B1. PREDICTS - correlation of each driver over the LAST month with the currency's move in the NEXT month")
    lines.append(hdr)
    corr_next = {}
    lag = {nm: (drv.shift(1)) for nm, drv in drivers_same.items()}        # the change over the previous period
    lag["policy gap level"] = gap_m
    lag["own last month"] = mret.shift(1)
    lag["own last 12 months"] = (mret.shift(1) + 1).rolling(12).apply(np.prod, raw=True) - 1
    for nm, drv in lag.items():
        row = f"  {nm:20}"
        for c in CCY:
            if isinstance(drv, pd.DataFrame) and c not in drv.columns:
                row += f"{'':>7}"
                continue
            x = drv[c] if isinstance(drv, pd.DataFrame) else drv
            j = pd.concat([x.rename("x"), mret[c].rename("y")], axis=1).dropna()
            r = j.x.corr(j.y) if len(j) > 24 else np.nan
            corr_next[(nm, c)] = r
            row += f"{r:+7.2f}"
        lines.append(row)
    lines.append("")

    # ----- B2: trading rules -----
    rules = {}
    ppy_m, ppy_w = 12, 52
    # CARRY: cross-sectional on the policy gap level
    rules["CARRY (top/bottom 2 policy rates)"] = ("M", xs(gap_m))
    # RATE CHANGE: 3-month change in the gap
    d3 = gap_m - gap_m.shift(3)
    rules["RATE CHANGE (3m policy-gap change)"] = ("M", np.sign(d3).where(d3.abs() > 0.01, 0.0))
    dl = lt_m - lt_m.shift(1)
    rules["LONG RATES (1m 10y-gap change)"] = ("M", np.sign(dl).reindex(columns=CCY).fillna(0.0))
    rules["US 2Y (last month's change)"] = ("M", pd.DataFrame({c: -np.sign(us2 - us2.shift(1)) for c in CCY}))
    for k in (1, 3, 12):
        mom = (mret.shift(1) + 1).rolling(k).apply(np.prod, raw=True) - 1
        rules[f"MOMENTUM {k}m"] = ("M", np.sign(mom))
    com = pd.DataFrame(0.0, index=mstarts, columns=CCY)
    r_oil_l, r_cop_l = (oil / oil.shift(1) - 1), (cop / cop.shift(1) - 1)
    com["CAD"] = np.sign(r_oil_l)
    com["AUD"] = np.sign(r_cop_l)
    rules["COMMODITY (oil->CAD, copper->AUD)"] = ("M", com.where(com.notna(), 0.0))
    # weekly
    w_spx = asof(mk["^GSPC"], wstarts)
    r_w = w_spx / w_spx.shift(1) - 1
    rules["RISK (last week's S&P x risk sign)"] = ("W", pd.DataFrame({c: np.sign(r_w) * RISK_SIGN[c] for c in CCY}))
    c2 = cot.assign(net=(cot.nc_long - cot.nc_short) / cot.oi)
    netp = c2.pivot_table(index="date", columns="ccy", values="net")
    netp.index = netp.index + pd.Timedelta(days=3)               # as of Tuesday, published Friday
    z = (netp - netp.rolling(156, min_periods=104).mean()) / netp.rolling(156, min_periods=104).std()
    zw = asof(z, wstarts)
    rules["COT CROWD (fade |z| > 1.5)"] = ("W", (-np.sign(zw)).where(zw.abs() > 1.5, 0.0).reindex(columns=CCY).fillna(0.0))
    fl = asof(netp.diff(), wstarts)
    rules["COT FLOW (follow last week's change)"] = ("W", np.sign(fl).reindex(columns=CCY).fillna(0.0))

    lines.append("B2. TRADING RULES - next period's return a period (%), by version; EXNESS is the verdict")
    lines.append(f"  {'rule':40} {'n':>5} | {'SPOT':>7} {'+CARRY':>7} {'EXNESS':>7} | EXNESS tune (t) / holdout (t)  | "
                 f"ann. EXNESS | worst")
    res = {}
    for nm, (fq, pos) in rules.items():
        ret, nights, rates, ppy = (mret, mn, pol_m, ppy_m) if fq == "M" else (wret, wn, pol_w, ppy_w)
        pos = pos.reindex(columns=CCY).fillna(0.0)
        s_spot, s_carry, s_ex = run(pos, ret, nights, rates)
        st_s, st_c, st_e = stat(s_spot, ppy), stat(s_carry, ppy), stat(s_ex, ppy)
        res[nm] = (st_s, st_c, st_e)
        lines.append(f"  {nm:40} {st_e['n']:5} | {st_s['mean'] * 100:+7.3f} {st_c['mean'] * 100:+7.3f} {st_e['mean'] * 100:+7.3f} | "
                     f"{st_e['tu'] * 100:+.3f} ({st_e['t_tu']:+.1f}) / {st_e['ho'] * 100:+.3f} ({st_e['t_ho']:+.1f}) | "
                     f"{st_e['ann'] * 100:+6.2f}%/yr | {st_e['worst'] * 100:+.1f}%")
        lines.append(f"  {'':40}       +CARRY: tune {st_c['tu'] * 100:+.3f} ({st_c['t_tu']:+.1f}) / holdout {st_c['ho'] * 100:+.3f} "
                     f"({st_c['t_ho']:+.1f}), {st_c['ann'] * 100:+.2f}%/yr, worst {st_c['worst'] * 100:+.1f}%")
    # Holm on EXNESS
    names = list(res)
    ps = sorted((res[n][2]["p"], n) for n in names)
    m = len(ps)
    holm, run_max = {}, 0.0
    for r_, (p, n) in enumerate(ps):
        run_max = max(run_max, min(1.0, p * (m - r_)))
        holm[n] = run_max
    passes = [n for n in names if res[n][2]["tu"] > 0 and res[n][2]["ho"] > 0 and res[n][2]["t_tu"] >= 2
              and res[n][2]["t_ho"] >= 2 and holm[n] < 0.05]
    lines.append(f"  Holm p (EXNESS): " + ", ".join(f"{n.split(' (')[0]} {holm[n]:.2f}" for n in names))
    lines.append(f"  PASS: {passes or 'none'}")
    lines.append("")
    # ----- predictions -----
    lines.append("REGISTERED PREDICTIONS")
    gp = [corr_same[("policy-gap change", c)] for c in CCY if np.isfinite(corr_same.get(("policy-gap change", c), np.nan))]
    risk_ok = all(corr_same[("S&P 500", c)] >= 0.3 for c in ("AUD", "NZD", "CAD")) and \
        all(corr_same[("S&P 500", c)] < 0 for c in ("JPY", "CHF"))
    cad_oil = corr_same[("oil", "CAD")]
    p1 = (np.mean(np.array(gp) >= 0.2) > 0.5) and risk_ok and cad_oil >= 0.3
    lines.append(f"  P1 policy-gap change >= +0.2 in {sum(np.array(gp) >= 0.2)}/{len(gp)}; S&P: " +
                 ", ".join(f"{c} {corr_same[('S&P 500', c)]:+.2f}" for c in ("AUD", "NZD", "CAD", "JPY", "CHF")) +
                 f"; CAD-oil {cad_oil:+.2f} -> {'RIGHT' if p1 else 'WRONG'}")
    big = max((abs(v), k) for k, v in corr_next.items() if np.isfinite(v))
    lines.append(f"  P2 largest one-month-ahead |corr| {big[0]:.2f} ({big[1][0]}, {big[1][1]}) -> {'RIGHT' if big[0] < 0.10 else 'WRONG'}")
    cs, cc, ce = res["CARRY (top/bottom 2 policy rates)"]
    p3 = cc["tu"] > 0 and cc["ho"] > 0 and cc["worst"] <= -0.05 and ce["mean"] <= 0
    lines.append(f"  P3 CARRY +carry {cc['tu'] * 100:+.3f} / {cc['ho'] * 100:+.3f}% a month, worst {cc['worst'] * 100:+.1f}%; EXNESS "
                 f"{ce['mean'] * 100:+.3f}% -> {'RIGHT' if p3 else 'WRONG'}")
    cw = res["COT CROWD (fade |z| > 1.5)"][2]
    cf = res["COT FLOW (follow last week's change)"][2]
    p4 = cw["mean"] > 0 and min(cw["t_tu"], cw["t_ho"]) < 2 and abs(cf["t"]) < 2
    lines.append(f"  P4 COT CROWD {cw['mean'] * 100:+.3f}% a week (t {cw['t_tu']:+.1f} / {cw['t_ho']:+.1f}); COT FLOW t {cf['t']:+.1f} -> "
                 f"{'RIGHT' if p4 else 'WRONG'}")
    lines.append(f"  P5 no rule passes on EXNESS: {passes or 'none'} -> {'RIGHT' if not passes else 'WRONG'}")
    txt = "\n".join(lines)
    print(txt)
    LOG.write_text(txt + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
