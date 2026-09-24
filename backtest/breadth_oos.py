"""OUT OF SAMPLE: the bear-market breadth trade on the 2018 bear market, parameters FROZEN.

Everything in docs/13 was measured on 2020-01 .. 2026-09 perp data. The 2018 bear (BTC -84%
from its December 2017 top) and 2019 are data this repo has never used for this question. The
universe is Binance's BTC-quoted spot book priced in dollars (ALTBTC x BTCUSDT), because in 2018
most altcoins traded against BTC, with dead pairs included (backtest/spot2018_fetch.py).

FROZEN, nothing re-chosen: bear = market_neutral.btc_regime (BTC below its 50-day average and the
average down > 2% over 20 days, one day lagged); breadth20 over the point-in-time top-60 by prior-
month dollar volume, listed >= 30 days, stablecoins excluded; thresholds LOW <= 10.0% and
HIGH >= 28.8% - the terciles of breadth20 over every 2020-26 bear day (doc 13, section 5); hold 7
days as a 7-tranche ladder; entered one day after the signal; 12bp round trip + 1bp/day basket
rebalancing. No funding: these are spot prices (Binance perps began 2019-09) - and shorting was
not available on Binance spot in 2018, so the short leg here is a measurement of the signal, not a
trade anyone could have placed there.
WINDOW: 2017-07 .. 2019-12. 2020-01 .. 2020-03 is shown apart: the perp scan already saw it.

REGISTERED PREDICTIONS (2026-09-24, written before this file was run or its data looked at):
  1. in bear days, next-7-day alt return: low-breadth tercile beats high by >= 2%/wk.
  2. the frozen long+short trade is positive over 2018-2019, and so is each leg.
  3. the same frozen rule gated to CHOP or BULL is not positive (the placebo).
  4. smaller than in-sample: +5% to +20%/yr on the alt index (in-sample +27%).

    python -m backtest.breadth_oos
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import breadth_trade as bt  # noqa: E402
from backtest.market_neutral import NON_CRYPTO, btc_regime  # noqa: E402

SRC = Path(__file__).resolve().parents[1] / "strategy_analysis" / "data" / "spot1d_2017"
LOW, HIGH = 0.100, 0.288
END = pd.Timestamp("2019-12-31")
MIN_AGE = 30


def panel():
    btc = pd.read_csv(SRC / "BTCUSDT.csv.gz", parse_dates=["time"]).set_index("time")
    bu = btc["close"]
    close, vol = {"BTC": bu}, {"BTC": btc["volume"] * bu}
    for p in sorted(SRC.glob("*BTC.csv.gz")):
        base = p.name[:-len("BTC.csv.gz")]
        if base in NON_CRYPTO or base in ("USDT", "USDS", "USDSB", "BKRW", "BIDR", "IDRT", "BVND", "NGN", "RUB", "TRY", "EUR", "GBP", "AUD", "BRL", "UAH", "ZAR"):
            continue
        d = pd.read_csv(p, parse_dates=["time"]).set_index("time")
        d = d[~d.index.duplicated()]
        d = d[d.close > 0]
        if len(d) < 40:
            continue
        px = d["close"] * bu.reindex(d.index)
        close[base] = px
        vol[base] = d["volume"] * px
    C = pd.DataFrame(close).sort_index()
    V = pd.DataFrame(vol).reindex(C.index).fillna(0.0)
    C.index = C.index.astype("datetime64[ns]"); V.index = C.index
    first = C.apply(lambda s: s.first_valid_index())
    return C, V, first


def members(C, V, first, n):
    """T x N bool: top-n by the PRIOR calendar month's dollar volume, listed >= MIN_AGE days."""
    mv = V.resample("ME").sum()
    months = C.index.to_period("M")
    out = np.zeros(C.shape, bool)
    cols = list(C.columns)
    fv = np.array([first[s].value for s in cols])
    for per in sorted(set(months)):
        prev = (per - 1).to_timestamp(how="end").normalize()
        rows = np.flatnonzero(months == per)
        if prev not in mv.index.normalize():
            continue
        vv = mv.loc[mv.index.normalize() == prev].iloc[0]
        start = per.to_timestamp()
        ok = [s for s in cols if (start.value - first[s].value) / 86_400e9 >= MIN_AGE and vv[s] > 0]
        top = set(vv[ok].sort_values(ascending=False).index[:n])
        mask = np.array([s in top for s in cols])
        out[rows] = mask
    return out & np.isfinite(C.to_numpy(float))


def main():
    C, V, first = panel()
    X = C.to_numpy(float); ff = pd.DataFrame(X).ffill().to_numpy()
    print(f"spot panel: {C.shape[1]} assets priced in USD, {C.index[0]:%Y-%m-%d} .. {C.index[-1]:%Y-%m-%d}")
    m60 = members(C, V, first, 60)
    print(f"  PIT top-60 size by month (first/median/last): {m60.sum(1)[m60.sum(1) > 0][0]} / "
          f"{int(np.median(m60.sum(1)[m60.sum(1) > 0]))} / {m60.sum(1)[-1]}")
    ma = C.rolling(20, min_periods=20).mean().to_numpy()
    ok = np.isfinite(ma) & m60
    cnt = ok.sum(1)
    br = pd.Series(((X > ma) & ok).sum(1) / np.where(cnt >= 10, cnt, np.nan), index=C.index).shift(1)
    reg = btc_regime(C.rename(columns={"BTC": "BTCUSDT"})).reindex(C.index)
    ins = {}
    for lab, n in (("alt index (top-40)", 40), ("top-10 basket", 10)):
        m = members(C, V, first, n)
        r = np.full(len(C), np.nan)
        for d in range(1, len(C)):
            mem = m[d - 1]
            if mem.sum() >= min(8, n):
                r[d] = np.nanmean(ff[d, mem] / X[d - 1, mem] - 1)
        ins[lab] = (pd.Series(r, index=C.index), pd.Series(0.0, index=C.index), bt.REBAL_BP)
    b = C["BTC"]
    ins["BTC"] = (b / b.shift(1) - 1, pd.Series(0.0, index=C.index), 0.0)

    win = (C.index <= END)
    print("  regime days in 2017-07..2019-12: " + "  ".join(
        f"{k} {int(v)}" for k, v in reg[win].value_counts().items()))

    # 1. the raw effect, as in regime_signals.py: next 7 days from the open of D
    alt_r = ins["alt index (top-40)"][0]
    fwd = (1 + alt_r.fillna(0)).rolling(7).apply(np.prod, raw=True).shift(-6) - 1
    fwd_b = b.shift(-6) / b.shift(1) - 1
    Dd = pd.DataFrame({"br": br, "fwd": fwd, "fwd_btc": fwd_b, "reg": reg})[win].dropna()
    print("\n1. RAW EFFECT, 2017-07..2019-12: next-7-day return by breadth20, FROZEN thresholds")
    for r_ in ("bear", "chop", "bull"):
        g = Dd[Dd.reg == r_]
        lo, mid, hi = g[g.br <= LOW], g[(g.br > LOW) & (g.br < HIGH)], g[g.br >= HIGH]
        print(f"   {r_:<5} low {lo.fwd.mean()*100:+6.2f}% (n {len(lo):>3})   mid {mid.fwd.mean()*100:+6.2f}% (n {len(mid):>3})"
              f"   high {hi.fwd.mean()*100:+6.2f}% (n {len(hi):>3})   low - high {(lo.fwd.mean()-hi.fwd.mean())*100:+6.2f}%/wk"
              f"   | BTC low - high {(lo.fwd_btc.mean()-hi.fwd_btc.mean())*100:+6.2f}%")

    # 2-4. the frozen trade
    def sig(gate, side="both"):
        lo = (gate & (br <= LOW)).astype(float)
        hi = (gate & (br >= HIGH)).astype(float)
        return lo - hi if side == "both" else (lo if side == "long" else -hi)

    print("\n2-4. FROZEN TRADE, lag 1, 7-day ladder, 12bp + 1bp/day. Window 2017-07..2019-12; "
          "%/yr on the whole account")
    print(f"   {'rule':<34}{'instrument':<20}{'CAGR':>8}{'DD':>6}{'worst wk':>9}{'in mkt':>7}   2018    2019   | 2020Q1 (seen)")
    for lab, gate, side in (("BEAR long+short", reg == "bear", "both"), ("BEAR long only", reg == "bear", "long"),
                            ("BEAR short only", reg == "bear", "short"), ("placebo: CHOP", reg == "chop", "both"),
                            ("placebo: BULL", reg == "bull", "both"), ("control: long every bear day", reg == "bear", "ctl")):
        s = (gate.astype(float) if side == "ctl" else sig(gate, side))
        for iname, inst in ins.items():
            x, pos = bt.ladder(s, *inst, lag=1)
            xw, pw = x[win], pos[win]
            cagr, dd, ww, sh, inm = stats(xw, pw) if len(xw) else (np.nan,) * 5
            y = lambda yr: ((1 + x[x.index.year == yr]).prod() - 1) * 100  # noqa: E731
            q1 = ((1 + x[(x.index > END) & (x.index <= pd.Timestamp("2020-03-31"))]).prod() - 1) * 100
            print(f"   {lab:<34}{iname:<20}{cagr:>+7.1f}%{dd:>5.0f}%{ww:>+8.1f}%{inm:>6.0f}%  {y(2018):+6.1f}% {y(2019):+6.1f}%  | {q1:+6.1f}%")


def stats(x, pos):
    return bt.stats(x, pos)


if __name__ == "__main__":
    main()
