"""Portfolio-level simulation: all assets trading SIMULTANEOUSLY from one shared
equity pool, so correlated exposure and real drawdown show up honestly.

Per-trade expectancy (+0.13R) does NOT translate to returns by simple
multiplication, because these coins move together — when one signals long, they
often all do. This simulates that properly.

    python -m backtest.portfolio_sim
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.mass_search import FILTERS, fetch, gen_signals  # noqa: E402
from bot.core.indicators import atr as atr_ind  # noqa: E402
from bot.strategies.base import Action  # noqa: E402

ASSETS = ["DOGEUSDT", "ADAUSDT", "LINKUSDT", "AVAXUSDT", "XRPUSDT", "BNBUSDT"]
FAM, PARAMS, FILT = "rsi_mom", (7, 40, 60), "er30"
SL_MULT, TP_MULT = 2.0, 3.0
MAKER, TAKER = 0.0002, 0.0006


def prep(sym):
    df = fetch(sym, "1h", 900)
    sig = FILTERS[FILT](df, gen_signals(df, FAM, PARAMS)).values
    # .shift(1): ATR[i] contains bar i's own range, unknown at bar i's open
    # where the entry fills. Using it is look-ahead (see rtest.py).
    a = atr_ind(df, 14).shift(1).values
    t = df["time"].values.astype("datetime64[ms]").astype(np.int64)   # ms epoch
    return dict(t=t, o=df["open"].values, h=df["high"].values,
                l=df["low"].values, sig=sig, atr=a,
                idx={int(x): i for i, x in enumerate(t)})


def simulate(data, risk_pct, max_concurrent=None, start=1000.0):
    timeline = sorted({int(t) for d in data.values() for t in d["t"]})
    equity = start
    pos, pending = {}, {}
    curve, times, trades, concur = [], [], [], []

    for t in timeline:
        # ---- exits first ----
        for s, d in data.items():
            i = d["idx"].get(t)
            if i is None or s not in pos:
                continue
            p = pos[s]
            dr = p["dir"]
            hit_sl = (d["l"][i] <= p["sl"]) if dr == 1 else (d["h"][i] >= p["sl"])
            hit_tp = (d["h"][i] >= p["tp"]) if dr == 1 else (d["l"][i] <= p["tp"])
            px, taker_exit = None, True
            if hit_sl:
                px, taker_exit = p["sl"], True
            elif hit_tp:
                px, taker_exit = p["tp"], False
            if px is not None:
                R = (px - p["entry"]) * dr / p["risk"]
                R -= (MAKER + (TAKER if taker_exit else MAKER)) * p["entry"] / p["risk"]
                equity += R * p["risk_amt"]
                trades.append(R)
                pos.pop(s)

        # ---- fill pending at this bar's open ----
        for s in list(pending):
            i = data[s]["idx"].get(t)
            if i is None:
                continue
            if s in pos:
                pending.pop(s); continue
            if max_concurrent and len(pos) >= max_concurrent:
                pending.pop(s); continue
            pd_ = pending.pop(s)
            entry = data[s]["o"][i]
            risk = pd_["risk"]
            pos[s] = dict(dir=pd_["dir"], entry=entry, risk=risk,
                          sl=entry - pd_["dir"] * risk,
                          tp=entry + pd_["dir"] * TP_MULT * pd_["atr"],
                          risk_amt=equity * risk_pct / 100.0)

        # ---- new signals -> pending next bar ----
        for s, d in data.items():
            i = d["idx"].get(t)
            if i is None or s in pos or s in pending:
                continue
            a = d["atr"][i]
            if d["sig"][i] != Action.HOLD and np.isfinite(a) and a > 0:
                pending[s] = dict(dir=1 if d["sig"][i] == Action.BUY else -1,
                                  atr=a, risk=SL_MULT * a)

        curve.append(equity); times.append(t); concur.append(len(pos))

    eq = np.array(curve)
    ts = pd.to_datetime(pd.Series(times), unit="ms")
    peak = np.maximum.accumulate(eq)
    dd = (peak - eq) / peak * 100
    ser = pd.Series(eq, index=ts)
    monthly = ser.resample("ME").last().pct_change().dropna() * 100
    yrs = (ts.iloc[-1] - ts.iloc[0]).days / 365.25
    R = np.array(trades)
    return dict(eq=ser, final=eq[-1], ret=(eq[-1] / start - 1) * 100,
                cagr=((eq[-1] / start) ** (1 / yrs) - 1) * 100,
                maxdd=dd.max(), n=len(R), expR=R.mean() if len(R) else 0,
                win=(R > 0).mean() * 100 if len(R) else 0,
                monthly=monthly, avg_concur=np.mean(concur),
                max_concur=max(concur), yrs=yrs)


def main():
    print("Loading assets...")
    data = {s: prep(s) for s in ASSETS}
    print(f"{len(ASSETS)} assets, "
          f"{pd.to_datetime(min(d['t'][0] for d in data.values()), unit='ms').date()}"
          f"..{pd.to_datetime(max(d['t'][-1] for d in data.values()), unit='ms').date()}\n")

    print(f"{'risk/trade':>11} {'maxconc':>8} {'trades':>7} {'expR':>7} {'return%':>9} "
          f"{'CAGR%':>8} {'maxDD%':>8} {'avg pos':>8} {'max pos':>8} "
          f"{'mo mean%':>9} {'mo worst%':>10} {'mo +ve':>7}")
    for risk in (0.5, 1.0, 2.0):
        for mc in (None, 3):
            r = simulate(data, risk, mc)
            print(f"{risk:>10}% {str(mc or 'all'):>8} {r['n']:>7} {r['expR']:>+7.3f} "
                  f"{r['ret']:>+9.0f} {r['cagr']:>+8.1f} {r['maxdd']:>8.1f} "
                  f"{r['avg_concur']:>8.2f} {r['max_concur']:>8} "
                  f"{r['monthly'].mean():>+9.2f} {r['monthly'].min():>+10.1f} "
                  f"{(r['monthly']>0).mean()*100:>6.0f}%")

    # detail for the moderate setting
    r = simulate(data, 1.0, 3)
    print("\n--- detail: 1% risk, max 3 concurrent positions ---")
    print(f"  span {r['yrs']:.2f}yr | trades {r['n']} | win {r['win']:.1f}% | expectancy {r['expR']:+.3f}R")
    print(f"  final equity ${r['final']:.0f} from $1000 | maxDD {r['maxdd']:.1f}%")
    print(f"  monthly returns ({len(r['monthly'])} months):")
    for d, v in r["monthly"].items():
        print(f"    {d:%Y-%m}  {v:+7.2f}%")


if __name__ == "__main__":
    main()
