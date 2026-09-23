"""SIZE NEW TRADES ON MARK-TO-MARKET EQUITY, NOT REALISED EQUITY.

compounding.py established that the bot's real compounding is ENTRY-SIZED: a position's
dollars are fixed at entry from the equity of trades already CLOSED. For this book that is a
large drag, because almost all of its profit is unrealised at any moment - it lives in
pyramids held for weeks. With every runner still open, the bot keeps sizing new trades off
the equity it had before the runners started. Entry-sized reads about half of the
daily-sum figures most docs quote (holdout +4.88%/mo against +8.83%, haircut).

The lever: size each new entry on equity INCLUDING the open positions' unrealised P&L,
marked at the entry time. Open positions are never resized; only the base for new ones
changes. That is legal, causal (prices up to the entry bar), and it is how most trend
followers size ("notional equity").

The cost is the book's own giveback: open profit is kept at only 21% (giveback.py), so
sizing on it means betting bigger on money that mostly evaporates. Hence a middle variant:
count only HALF of the unrealised profit (losses counted in full).

REGISTERED PREDICTION: MTM recovers 60-80% of the gap between entry-sized and daily-sum
returns on both halves, and costs 5-10 points of drawdown. The half-credit variant sits in
between on both.

Marks use each coin's 1h close known at the entry time; units count once their add bar has
closed; funding and fees are already in R. Drawdown is reported on the REALISED equity curve,
which is kind to all three rows equally.

    python -m backtest.mtm_sizing
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
from backtest.causal_t0 import LATE, real_t0  # noqa: E402
from backtest.compounding import summarize  # noqa: E402
from backtest.engine_variants import BASE_RULES, rows_for  # noqa: E402
from backtest.funding_cost import charged, long_funding, short_funding, short_rows_with_risk  # noqa: E402
from backtest.timeframes import resample  # noqa: E402

SEEDS = tuple(range(10))
_PX: dict = {}


def closes(coin):
    """(known-at times in ns, close) - a 1h bar's close is known one hour after its open."""
    if coin not in _PX:
        d = blend.load(coin)
        t = (pd.DatetimeIndex(d["time"]) + pd.Timedelta(hours=1)).as_unit("ns").asi8
        _PX[coin] = (t, d["close"].to_numpy(float))
    return _PX[coin]


def price_at(coin, t_ns):
    t, c = closes(coin)
    k = np.searchsorted(t, t_ns, side="right") - 1
    return c[k] if k >= 0 else np.nan


def attach_prices(raw_rows, resampler=None):
    """Entry price, 1R distance and unit entry levels / known-times for every row. Rows
    are the engine's own (label t0); the unit arithmetic mirrors long_walk exactly.

    resampler(coin, rule) -> OHLC frame, for callers whose rows were built on a bar grid other
    than the deployed one (backtest/bar_phase.py shifts the 4h/12h phase). Default is the
    deployed grid, so every existing caller is unaffected."""
    if resampler is None:
        def resampler(coin, rule):
            return resample(blend.load(coin), rule)
    frames, look = {}, {}
    for rule in BASE_RULES:
        for x in short_rows_with_risk(rule):
            look[(rule, x["coin"], str(x["t0"]), round(x["R"], 9))] = x
    out = []
    for r in raw_rows:
        if r["side"] == "long":
            key = (r["coin"], r["rule"])
            if key not in frames:
                df = resampler(r["coin"], r["rule"])
                frames[key] = pd.Series(df["open"].to_numpy(float),
                                        index=pd.DatetimeIndex(df["time"]))
            e0 = float(frames[key].loc[pd.Timestamp(r["t0"])])
            risk = r["sf"] * e0
            units = [(e0 + k * blend.ADD_EVERY * risk,
                      (pd.Timestamp(ta) + pd.Timedelta(hours=1)).value)   # add bar closed
                     for k, ta in enumerate(r["adds"])]
            units[0] = (e0, (pd.Timestamp(r["t0"]) - LATE[r["rule"]]).value)
            out.append(dict(r, e0=e0, risk=risk, units=units, d=1))
        else:
            x = look[(r["rule"], r["coin"], str(r["t0"]), round(r["R"], 9))]
            out.append(dict(r, e0=x["e0"], risk=x["risk"],
                            units=[(x["e0"], (pd.Timestamp(r["t0"]) - LATE[r["rule"]]).value)],
                            d=-1))
    return out


def unrealised_R(p, t_ns):
    px = price_at(p["coin"], t_ns)
    if not np.isfinite(px):
        return 0.0
    return sum((px - e) * p["d"] / p["risk"] for e, tk in p["units"] if tk <= t_ns)


def simulate(rows, bear, seed, mode, t_from=None, t_to=None, want_curve=False):
    """mode: 'realised' (what the bot does), 'mtm' (full unrealised), 'half' (half of
    unrealised gains, all of unrealised losses). want_curve returns the daily realised
    equity curve (start 1.0) instead of the summary."""
    rng = np.random.default_rng(seed)
    tie = rng.random(len(rows))
    o = [rows[i] for i in sorted(range(len(rows)), key=lambda i: (rows[i]["t0"], tie[i]))]
    eq, open_, pts = 1.0, [], []

    def bank(upto):
        nonlocal eq, open_
        keep = []
        for p in sorted(open_, key=lambda q: q["t1"]):
            if p["t1"] <= upto:
                eq = max(eq + p["dollars_per_R"] * p["R"], 0.0)
                pts.append((p["t1"], eq))
            else:
                keep.append(p)
        open_ = keep

    for r in o:
        t0 = pd.Timestamp(r["t0"])
        if (t_from is not None and t0 < t_from) or (t_to is not None and t0 >= t_to):
            continue
        bank(t0)
        if len(open_) >= 12:
            continue
        f = blend.RISK / 100.0 * (blend.REGIME_MULT if bool(bear.asof(t0)) else 1.0)
        base = eq
        if mode != "realised" and open_:
            tn = t0.value
            u = sum(p["dollars_per_R"] * unrealised_R(p, tn) for p in open_)
            base = eq + (u if (mode == "mtm" or u < 0) else 0.5 * u)
        base = max(base, 0.0)
        open_.append(dict(r, t1=pd.Timestamp(r["t1"]), dollars_per_R=f * base))
    bank(pd.Timestamp("2100-01-01"))
    s = pd.Series([p[1] for p in pts], index=pd.DatetimeIndex([p[0] for p in pts]))
    c = s.resample("D").last().ffill()
    return c if want_curve else summarize(c)


def main():
    bear = regimes()[1000]
    ts = pd.DatetimeIndex(sorted(x[0] for x in sleeve_sided("1h")[0]))
    cut = ts[int(len(ts) * 0.6)]
    print(f"causal t0, funding charged, {len(SEEDS)} orderings | tune < {cut:%Y-%m-%d} <= holdout")
    print("hpm = CAGR/3 per month; raw un-haircut; DD on the realised curve\n")
    print(f"  {'book':<7}{'sizing base':<30}{'TUNE hpm':>9}{'raw':>8}{'DD':>5}"
          f"{'HOLD hpm':>10}{'raw':>8}{'DD':>5}")
    for bk, tight in (("main", False), ("tight", True)):
        rows = charged(real_t0(short_funding(long_funding(attach_prices(
            rows_for(BASE_RULES, tight=tight))))))
        for mode, lab in (("realised", "closed equity (the bot today)"),
                          ("half", "closed + half of open gains"),
                          ("mtm", "closed + all open P&L (MTM)")):
            a = np.mean([simulate(rows, bear, s, mode, t_to=cut) for s in SEEDS], axis=0)
            b = np.mean([simulate(rows, bear, s, mode, t_from=cut) for s in SEEDS], axis=0)
            print(f"  {bk:<7}{lab:<30}{a[0]:>+8.2f}%{a[1]:>+7.2f}%{a[2]:>4.0f}%"
                  f"{b[0]:>+9.2f}%{b[1]:>+7.2f}%{b[2]:>4.0f}%")


if __name__ == "__main__":
    main()
