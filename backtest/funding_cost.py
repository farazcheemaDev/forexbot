"""THE DEPLOYED BOOK HAS NEVER BEEN CHARGED FUNDING - charged here, per unit, per settlement.

WHY
    grep the engine (pyramid.py, convex.py, blend.py, engine_variants.py, bull_boost.py):
    nothing charges funding. Every figure for the deployed book is fees-only. That is fine
    for a 1h scalp and not fine for THIS book, whose whole edge is 5-unit pyramids held for
    weeks through bull markets - exactly when longs pay the most (2021 funding sat far above
    the 0.01%/8h baseline for months). Shorts, conversely, RECEIVE positive funding, so the
    hedge sleeve is under-credited. Nobody knows the net sign or size.

HOW
    Binance's actual USDT-M funding history per coin (perp_fetch.py archive; 1000SHIBUSDT for
    SHIB). For every UNIT of every position:
        funding R = -side x sum over settlements held of  rate_s x price_s / r
    where r is the position's 1R price distance (2 x ATR at entry). A unit is held from its
    real fill time to the real exit. Real times, not bar labels (causal_t0.py): resampled
    rows enter at the bar OPEN, L - rule + 1h. Adds fill somewhere inside their bar and are
    counted from the bar's START (overcounts at most one settlement - conservative for a
    long). Exits are counted to the exit bar's midpoint (off by at most one settlement).
    Before a coin's perp existed nothing is charged; the live bot could not have traded it.

    Book re-scored causally (t0 = real entry), 5 orderings, 1000h gate, 3x haircut.

REGISTERED PREDICTION (before running)
    Longs pay on average 0.2-0.5R per position against a +3.4R mean, i.e. 6-15% of total
    long R, concentrated in 2021. Shorts earn a small +0.01-0.03R. Net: -2 to -4%/mo on the
    tune half, -1 to -2%/mo on the holdout.

    python -m backtest.funding_cost
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
from backtest.causal_t0 import LATE, boost, real_t0  # noqa: E402
from backtest.convex import run_uncapped  # noqa: E402
from backtest.engine_variants import BASE_RULES, rows_for, run, shorts_for  # noqa: E402
from backtest.shortside import signals  # noqa: E402
from backtest.timeframes import resample  # noqa: E402
from bot.core.indicators import atr as atr_ind  # noqa: E402

PERPS = Path(__file__).resolve().parents[1] / "strategy_analysis" / "data" / "perps"
PERP_NAME = {"SHIBUSDT": "1000SHIBUSDT"}
RULE_H = {"1h": 1, "2h": 2, "4h": 4, "8h": 8, "12h": 12, "1d": 24}
_F: dict = {}


def funding(coin):
    """(settlement times as int64 ns, rate x price at settlement) for one coin."""
    if coin in _F:
        return _F[coin]
    f = pd.read_csv(PERPS / f"{PERP_NAME.get(coin, coin)}_funding.csv.gz")
    ts = pd.to_datetime(f["time"]).dt.floor("h")
    d = blend.load(coin)
    px = pd.Series(d["open"].to_numpy(float), index=pd.DatetimeIndex(d["time"]))
    p = px.reindex(px.index.union(ts)).ffill().reindex(ts).to_numpy(float)
    ok = np.isfinite(p)
    _F[coin] = (pd.DatetimeIndex(ts[ok]).as_unit("ns").asi8,
                (f["rate"].to_numpy(float) * p)[ok])
    return _F[coin]


def paid(coin, t_from, t_to):
    """Sum of rate x price over settlements with t_from < s <= t_to (a long pays this)."""
    ts, rp = funding(coin)
    a = np.searchsorted(ts, pd.Timestamp(t_from).as_unit("ns").value, side="right")
    b = np.searchsorted(ts, pd.Timestamp(t_to).as_unit("ns").value, side="right")
    return float(rp[a:b].sum())


def _real(label, rule):
    return pd.Timestamp(label) - LATE[rule]


def _exit(label, rule):
    """Midpoint of the exit bar in real time: bar spans (L-rule+1h, L+1h]."""
    return pd.Timestamp(label) + pd.Timedelta(hours=1) - pd.Timedelta(hours=RULE_H[rule]) / 2


def _with_fund(r, e0):
    """One long row plus its funding cost in R, given its entry price.

    Each unit starts paying from its own add bar's START - conservative, since the add fills
    somewhere inside that bar - and stops at the position's exit."""
    risk = r["sf"] * e0
    t_exit = _exit(r["t1"], r["rule"])
    tot = 0.0
    for k, ta in enumerate(r["adds"]):
        start = _real(r["t0"], r["rule"]) if k == 0 else _real(ta, r["rule"])
        if start < t_exit:
            tot += paid(r["coin"], start, t_exit)
    return dict(r, fund=-tot / risk)


def long_funding(rows):
    """Adds 'fund' (R, negative = paid) to every long row. Needs each position's r and
    entry price, recovered from the coin's own bars at the entry label."""
    frames = {}
    out = []
    for r in rows:
        if r["side"] != "long":
            out.append(r); continue
        # Prefer the entry price attach_prices already computed. It is the same number, it
        # saves re-resampling, and it is the only version that is correct when the rows were
        # walked on a SHIFTED bar grid (backtest/bar_phase.py) - a shifted t0 is not a label
        # on the deployed grid, which raised KeyError here. Fallback keeps older callers that
        # run long_funding without attach_prices first.
        if "e0" in r:
            out.append(_with_fund(r, float(r["e0"])))
            continue
        key = (r["coin"], r["rule"])
        if key not in frames:
            df = resample(blend.load(r["coin"]), r["rule"])
            frames[key] = pd.Series(df["open"].to_numpy(float),
                                    index=pd.DatetimeIndex(df["time"]))
        out.append(_with_fund(r, float(frames[key].loc[pd.Timestamp(r["t0"])])))
    return out


_SH: dict = {}


def short_rows_with_risk(rule):
    """The deployed short sleeve rebuilt with each trade's own r, guarded against
    shorts_for(rule) so the rows are the same trades."""
    if rule in _SH:
        return _SH[rule]
    rows = []
    for coin in blend.BOOK:
        d = blend.load(coin)
        if d is None:
            continue
        df = resample(d, rule)
        if len(df) < 300:
            continue
        a = atr_ind(df, 14).to_numpy(float)
        o = df["open"].to_numpy(float)
        t = df["time"].to_numpy()
        R, idx, bars, _d = run_uncapped(df, signals(df, "short", "all"),
                                        sl_mult=blend.SL_MULT, fee_bp=blend.FEE_BP,
                                        mode="trail_atr", trail=blend.SHORT_TRAIL,
                                        be_at=blend.BE_AT)
        for rr, i, b in zip(R, idx, bars):
            j = max(int(i) - int(b), 0)
            risk = blend.SL_MULT * a[j - 1]
            rows.append(dict(coin=coin, t0=t[j], t1=t[int(i)], R=float(rr), risk=risk,
                             e0=o[j]))
    ref = shorts_for(rule)
    assert len(rows) == len(ref), (rule, len(rows), len(ref))
    k1 = sorted((str(x["t0"]), round(x["R"], 9)) for x in rows)
    k2 = sorted((str(x["t0"]), round(x["R"], 9)) for x in ref)
    assert k1 == k2, rule
    _SH[rule] = rows
    return rows


def short_funding(rows):
    """Adds 'fund' to every short row: a short RECEIVES positive funding."""
    look = {}
    for rule in sorted({r["rule"] for r in rows if r["side"] == "short"}):
        for x in short_rows_with_risk(rule):
            look[(rule, x["coin"], str(x["t0"]), round(x["R"], 9))] = x
    out = []
    for r in rows:
        if r["side"] != "short":
            out.append(r); continue
        x = look[(r["rule"], r["coin"], str(r["t0"]), round(r["R"], 9))]
        got = paid(r["coin"], _real(r["t0"], r["rule"]), _exit(r["t1"], r["rule"]))
        out.append(dict(r, fund=got / x["risk"]))
    return out


def charged(rows):
    return [dict(r, R=r["R"] + r.get("fund", 0.0)) for r in rows]


def main():
    bear = regimes()[1000]
    ts = pd.DatetimeIndex(sorted(x[0] for x in sleeve_sided("1h")[0]))
    cut = ts[int(len(ts) * 0.6)]

    base = short_funding(long_funding(rows_for(BASE_RULES)))
    tight = short_funding(long_funding(rows_for(BASE_RULES, tight=True)))

    D = pd.DataFrame([dict(side=r["side"], rule=r["rule"], R=r["R"], fund=r["fund"],
                           year=pd.Timestamp(r["t1"]).year) for r in base])
    print("PER POSITION (deployed book, every signal, before the slot cap)\n")
    print(f"  {'side':<6}{'rule':<5}{'n':>6}{'mean R':>9}{'funding R':>11}{'share':>8}"
          f"{'median fund':>13}{'worst':>9}")
    for (side, rule), g in D.groupby(["side", "rule"]):
        print(f"  {side:<6}{rule:<5}{len(g):>6}{g.R.mean():>+9.3f}{g.fund.mean():>+11.3f}"
              f"{g.fund.sum() / g.R.sum() * 100:>+7.1f}%{g.fund.median():>+13.3f}"
              f"{g.fund.min():>+9.2f}")
    print("\n  total R vs total funding R, by year of exit:")
    print(f"  {'year':<6}{'long R':>10}{'long fund':>11}{'short R':>10}{'short fund':>12}")
    for y, g in D.groupby("year"):
        L = g[g.side == "long"]; S = g[g.side == "short"]
        print(f"  {y:<6}{L.R.sum():>+10.0f}{L.fund.sum():>+11.0f}{S.R.sum():>+10.0f}"
              f"{S.fund.sum():>+12.0f}")

    print(f"\nPORTFOLIO (causal t0, 12 slots, 1000h gate, 5 orderings, 3x haircut)")
    print(f"  tune < {cut:%Y-%m-%d} <= holdout\n")
    print(f"  {'book':<46}{'TUNE/mo':>9}{'DD':>5}{'HOLD/mo':>9}{'DD':>5}{'worst':>8}")

    def show(lab, rows):
        a = run(rows, bear, cut, "tune"); b = run(rows, bear, cut, "hold")
        print(f"  {lab:<46}{a[0]:>+8.2f}%{a[1]:>4.0f}%{b[0]:>+8.2f}%{b[1]:>4.0f}%{b[2]:>+7.1f}%")

    show("deployed, fees only (as every doc reports)", real_t0(base))
    show("deployed, fees + FUNDING", charged(real_t0(base)))
    show("tight, fees only", real_t0(tight))
    show("tight, fees + funding", charged(real_t0(tight)))
    show("tight + short boost x5, fees + funding", boost(charged(real_t0(tight)), 5, True))


if __name__ == "__main__":
    main()
