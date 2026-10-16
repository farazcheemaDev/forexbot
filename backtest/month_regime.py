"""IS THIS A GOOD MONTH? - a start-of-month signal sizing the whole machine, fit 2020-26, judged on 2017-19 (2026-10-16)

The user: "I want the inflated return AND a stable minimum 10% - there must be indicators that tell the bot this month
or this day is not right". Tried before and dead (doc 20, doc 02): cutting the trend book in chop, 16 monthly brakes,
Fear & Greed as a dial, 14 BTC signals, vol targeting, regime weights. NOT tried: one model reading the market at each
month's START and sizing the whole machine for that month - fit on the deployed machine's 2020-2026 months and judged
on the frozen machine's 2017-08..2019-12 months (oos1719.py), which it never saw.
FEATURES (known at the close of the previous month)
    btc_r1 / btc_r3   BTC's return over the last 1 / 3 months
    btc_ma            BTC's close / its 42-day (1000h) mean - 1
    btc_vol           BTC's 30-day realised volatility (daily returns)
    breadth           share of the PIT top-40 above their 20-day mean
    own_r1 / own_r3   the machine's own return over the last 1 / 3 months
MODELS (fit on 2020-26 only)  a linear regression on all 7 (standardised), and the best single feature with its sign.
RULES  size this month 1.5x when the model's prediction is above its 2020-26 median, 0.5x when below (average 1x),
       against the machine at a constant 1x; and "skip" - 1x / 0x - against a constant 0.5x (the same average exposure).
LIMIT  sizing is applied to the month's booked returns: trades opened before the month started are re-scaled too, which
       a bot cannot do (they were sized at entry). Not future information - a coarse attribution.
STEPS  --dump-in (perps, 2020-26), --dump-oos (spot, 2017-19: a separate process, oos1719 re-points the engines' data),
       then --fit. Monthly returns are the mean over the 10 orderings.

REGISTERED BEFORE THE RUN (2026-10-16)
    1. On 2017-19 no rule beats its constant line by more than 0.1 in monthly Sharpe (the months are ~28, noisy).
    2. If any feature carries, it is own_r3 (strategy momentum: trend books' good months cluster).
    3. No rule makes losing months fewer than 40% on 2017-19.

RESULT: see logs/month_regime.txt (filled in after the run).

    python -m backtest.month_regime --dump-in && python -m backtest.month_regime --dump-oos && python -m backtest.month_regime --fit
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OUT = ROOT / "logs" / "month_regime_cache"
LOG = ROOT / "logs" / "month_regime.txt"
FEATS = ["btc_r1", "btc_r3", "btc_ma", "btc_vol", "breadth", "own_r1", "own_r3"]


def features(machine_daily, btc_close, breadth_daily):
    """One row per month: the month's machine return and the features known at the previous month's close."""
    c = (1 + machine_daily.fillna(0.0)).cumprod()
    me = c.resample("ME").last()
    ret = me / me.shift(1) - 1
    b = btc_close.resample("D").last().ffill()
    bm = b.resample("ME").last()
    vol = b.pct_change().rolling(30).std().resample("ME").last() * np.sqrt(365)
    ma = (b / b.rolling(42).mean() - 1).resample("ME").last()
    br = breadth_daily.resample("ME").last()
    F = pd.DataFrame({"ret": ret,
                      "btc_r1": (bm / bm.shift(1) - 1).shift(1), "btc_r3": (bm / bm.shift(3) - 1).shift(1),
                      "btc_ma": ma.shift(1), "btc_vol": vol.shift(1), "breadth": br.reindex(ret.index).shift(1),
                      "own_r1": ret.shift(1), "own_r3": (me / me.shift(3) - 1).shift(1)})
    return F.dropna()


def dump_in():
    from backtest import capit_combos as cc
    from backtest.capitulation_wide import hourly
    from backtest.final_confidence import parts
    xs = [s + mi for s, mi in parts()]
    daily = pd.concat(xs, axis=1).mean(axis=1)
    btc = hourly("BTCUSDT").set_index("time").close
    br = cc.daily_breadth()
    F = features(daily, btc, br)
    OUT.mkdir(parents=True, exist_ok=True)
    F.to_pickle(OUT / "in.pkl")
    print(f"in-sample months: {len(F)} ({F.index[0]:%Y-%m} .. {F.index[-1]:%Y-%m})")


def dump_oos():
    import backtest.oos1719 as O
    got = []
    orig = O.stats
    O.stats = lambda r: (got.append(r), orig(r))[1]
    O.LOG = ROOT / "logs" / "oos1719_rerun_for_month_regime.txt"
    O.main()
    xs = got[-10:]
    daily = pd.concat(xs, axis=1).mean(axis=1)
    btc = O.cw.hourly("BTCUSDT").set_index("time").close
    br = O.cc.daily_breadth()
    F = features(daily, btc, br)
    F = F[(F.index >= O.START) & (F.index <= O.END)]
    OUT.mkdir(parents=True, exist_ok=True)
    F.to_pickle(OUT / "oos.pkl")
    print(f"out-of-sample months: {len(F)} ({F.index[0]:%Y-%m} .. {F.index[-1]:%Y-%m})")


def score(ret, size):
    r = ret * size
    eq = (1 + r).cumprod()
    yrs = len(r) / 12
    return dict(cagr=eq.iloc[-1] ** (1 / yrs) - 1 if eq.iloc[-1] > 0 else -1, sharpe=r.mean() / r.std() * np.sqrt(12),
                fall=float((1 - eq / eq.cummax()).max()), lose=float((r < 0).mean()), ten=float((r >= 0.0999).mean()),
                avg=float(r.mean()))


def fit():
    A, B = pd.read_pickle(OUT / "in.pkl"), pd.read_pickle(OUT / "oos.pkl")
    mu, sd = A[FEATS].mean(), A[FEATS].std()
    Za, Zb = (A[FEATS] - mu) / sd, (B[FEATS] - mu) / sd
    X = np.c_[np.ones(len(Za)), Za.to_numpy()]
    beta = np.linalg.lstsq(X, A.ret.to_numpy(), rcond=None)[0]
    pred = {"linear, all 7": (X @ beta, np.c_[np.ones(len(Zb)), Zb.to_numpy()] @ beta)}
    corr = {f: np.corrcoef(A[f], A.ret)[0, 1] for f in FEATS}
    best = max(corr, key=lambda f: abs(corr[f]))
    pred[f"single: {best} ({'+' if corr[best] > 0 else '-'})"] = (np.sign(corr[best]) * Za[best].to_numpy(),
                                                                 np.sign(corr[best]) * Zb[best].to_numpy())
    lines = [f"backtest/month_regime.py --fit, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; fit on {len(A)} months "
             f"({A.index[0]:%Y-%m}..{A.index[-1]:%Y-%m}), judged on {len(B)} unseen months ({B.index[0]:%Y-%m}..{B.index[-1]:%Y-%m})",
             "", "  feature correlation with the month's return - fit years / unseen years:"]
    for f in FEATS:
        lines.append(f"    {f:<9}{corr[f]:>+7.2f}{np.corrcoef(B[f], B.ret)[0, 1]:>+8.2f}")
    lines += ["", f"  {'rule':<44}{'data':<8}{'CAGR':>8}{'Sharpe':>8}{'fall':>7}{'losing':>8}{'>=+10%':>8}{'avg mo':>8}"]
    R = {}
    for nm, (pa, pb) in pred.items():
        thr = np.median(pa)
        for data, ret, p in (("fit", A.ret, pa), ("UNSEEN", B.ret, pb)):
            for rule, size, base in (("1.5x good / 0.5x bad", np.where(p > thr, 1.5, 0.5), 1.0),
                                     ("1x good / out bad", np.where(p > thr, 1.0, 0.0), 0.5)):
                s, c = score(ret, pd.Series(size, index=ret.index)), score(ret, pd.Series(base, index=ret.index))
                R[(nm, rule, data)] = (s, c)
                lines.append(f"  {nm + ' | ' + rule:<44}{data:<8}{s['cagr'] * 100:>+7.0f}%{s['sharpe']:>8.2f}{s['fall'] * 100:>6.0f}%"
                             f"{s['lose'] * 100:>7.0f}%{s['ten'] * 100:>7.0f}%{s['avg'] * 100:>+7.1f}%")
                lines.append(f"  {'   constant ' + str(base) + 'x':<44}{data:<8}{c['cagr'] * 100:>+7.0f}%{c['sharpe']:>8.2f}"
                             f"{c['fall'] * 100:>6.0f}%{c['lose'] * 100:>7.0f}%{c['ten'] * 100:>7.0f}%{c['avg'] * 100:>+7.1f}%")
    uns = [(k, v) for k, v in R.items() if k[2] == "UNSEEN"]
    gain = max(v[0]["sharpe"] - v[1]["sharpe"] for _, v in uns)
    lose = min(v[0]["lose"] for _, v in uns)
    lines += ["", "REGISTERED PREDICTIONS",
              f"  1 no rule beats its constant line by > 0.1 Sharpe on the unseen years: best {gain:+.2f} -> {'RIGHT' if gain <= 0.1 else 'WRONG'}",
              f"  2 the strongest feature is own_r3: {best} -> {'RIGHT' if best == 'own_r3' else 'WRONG'}",
              f"  3 no rule gets losing months under 40% on the unseen years: fewest {lose * 100:.0f}% -> {'RIGHT' if lose >= 0.40 else 'WRONG'}"]
    txt = "\n".join(lines)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    {"--dump-in": dump_in, "--dump-oos": dump_oos, "--fit": fit}[sys.argv[1]]()
