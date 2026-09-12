"""Large-scale strategy search WITH multiple-comparisons control.

Searches hundreds/thousands of strategy configs across crypto assets and
timeframes, but splits data three ways:
    TRAIN      -> tune
    VALIDATION -> select the best
    HOLDOUT    -> touched exactly ONCE, final verdict

Also computes a CHANCE BASELINE: how many configs would look profitable by luck.
If the number of winners on the holdout is no better than chance, there is no
edge -- there is just a big search.

    python -m backtest.mass_search
"""
from __future__ import annotations

import itertools
import json
import sys
import time
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.engine import BacktestConfig, run_backtest  # noqa: E402
from bot.core.indicators import (adx, atr, bollinger, ema, macd, rsi,  # noqa: E402
                                 donchian, efficiency_ratio)
from bot.strategies.base import Action  # noqa: E402

DATA = Path(__file__).resolve().parents[1] / "strategy_analysis" / "data"
DATA.mkdir(parents=True, exist_ok=True)


def fetch(symbol: str, interval: str, days: int) -> pd.DataFrame:
    """Binance klines, cached to disk."""
    f = DATA / f"{symbol}_{interval}_{days}d.json"
    if f.exists():
        rows = json.load(open(f))
    else:
        rows, end = [], int(time.time() * 1000)
        start = end - days * 24 * 60 * 60 * 1000
        cur = start
        while cur < end:
            u = (f"https://api.binance.com/api/v3/klines?symbol={symbol}"
                 f"&interval={interval}&startTime={cur}&limit=1000")
            for a in range(4):
                try:
                    r = json.load(urllib.request.urlopen(u, timeout=25)); break
                except Exception:
                    if a == 3: raise
                    time.sleep(2)
            if not r: break
            rows.extend(r)
            cur = r[-1][0] + 1
        seen = {k[0]: k for k in rows}
        rows = [seen[t] for t in sorted(seen)]
        rows = [{"t": k[0], "o": float(k[1]), "h": float(k[2]), "l": float(k[3]),
                 "c": float(k[4]), "v": float(k[5])} for k in rows]
        json.dump(rows, open(f, "w"))
    df = pd.DataFrame(rows)
    df["time"] = pd.to_datetime(df["t"], unit="ms")
    return df.rename(columns={"o": "open", "h": "high", "l": "low",
                              "c": "close", "v": "volume"})[
        ["time", "open", "high", "low", "close", "volume"]].reset_index(drop=True)


# ---------------- strategy space (families x params x direction) -------------
def gen_signals(df: pd.DataFrame, fam: str, p: tuple) -> pd.Series:
    c = df["close"]
    sig = pd.Series(Action.HOLD, index=df.index, dtype=int)
    if fam == "ma_cross":
        f, s = p
        a, b = ema(c, f), ema(c, s)
        sig[(a > b) & (a.shift(1) <= b.shift(1))] = Action.BUY
        sig[(a < b) & (a.shift(1) >= b.shift(1))] = Action.SELL
    elif fam == "donchian":
        n, = p
        lo, hi = donchian(df, n)
        sig[c > hi] = Action.BUY
        sig[c < lo] = Action.SELL
    elif fam == "rsi_rev":
        n, lo_t, hi_t = p
        r = rsi(c, n)
        sig[(r > lo_t) & (r.shift(1) <= lo_t)] = Action.BUY
        sig[(r < hi_t) & (r.shift(1) >= hi_t)] = Action.SELL
    elif fam == "rsi_mom":
        n, lo_t, hi_t = p
        r = rsi(c, n)
        sig[r > hi_t] = Action.BUY
        sig[r < lo_t] = Action.SELL
    elif fam == "bb_rev":
        n, k = p
        lo, mid, hi = bollinger(c, n, k)
        sig[c < lo] = Action.BUY
        sig[c > hi] = Action.SELL
    elif fam == "bb_break":
        n, k = p
        lo, mid, hi = bollinger(c, n, k)
        sig[c > hi] = Action.BUY
        sig[c < lo] = Action.SELL
    elif fam == "macd":
        f, s, g = p
        line, sg, _ = macd(c, f, s, g)
        sig[(line > sg) & (line.shift(1) <= sg.shift(1))] = Action.BUY
        sig[(line < sg) & (line.shift(1) >= sg.shift(1))] = Action.SELL
    elif fam == "roc_mom":
        n, thr = p
        roc = c.pct_change(n) * 100
        sig[roc > thr] = Action.BUY
        sig[roc < -thr] = Action.SELL
    elif fam == "zscore_rev":
        n, k = p
        m, s = c.rolling(n).mean(), c.rolling(n).std()
        z = (c - m) / s
        sig[z < -k] = Action.BUY
        sig[z > k] = Action.SELL
    return sig.shift(1).fillna(Action.HOLD).astype(int)


SPACE = {
    "ma_cross":   list(itertools.product([5, 10, 20, 50], [50, 100, 200])),
    "donchian":   [(n,) for n in [10, 20, 30, 55, 80]],
    "rsi_rev":    list(itertools.product([7, 14, 21], [25, 30, 35], [65, 70, 75])),
    "rsi_mom":    list(itertools.product([7, 14, 21], [30, 40], [60, 70])),
    "bb_rev":     list(itertools.product([14, 20, 30], [1.5, 2.0, 2.5])),
    "bb_break":   list(itertools.product([14, 20, 30], [1.5, 2.0, 2.5])),
    "macd":       list(itertools.product([8, 12], [21, 26], [7, 9])),
    "roc_mom":    list(itertools.product([5, 10, 20], [1.0, 2.0, 4.0])),
    "zscore_rev": list(itertools.product([20, 50], [1.5, 2.0, 2.5])),
}
EXITS = [(2.0, 3.0), (1.5, 2.0), (2.0, 1.2)]   # (atr_sl, atr_tp)

# NOTE: filters MUST be shifted by 1 like the signals. Using the current bar's
# indicator to gate a trade entered at that bar's open is LOOK-AHEAD BIAS.
FILTERS = {
    "none":  lambda df, s: s,
    "adx25": lambda df, s: s.where(adx(df, 14).shift(1) >= 25, Action.HOLD),
    "er30":  lambda df, s: s.where(efficiency_ratio(df["close"], 20).shift(1) >= 0.30, Action.HOLD),
}


def cost_cfg(sl, tp):
    # crypto taker-ish cost: ~0.05% per side -> expressed via commission
    return BacktestConfig(pip_size=1.0, pip_value_per_lot=1.0, spread_pips=0.0,
                          slippage_pips=0.0, commission_per_lot=0.0,
                          exit_mode="atr", atr_sl_mult=sl, atr_tp_mult=tp,
                          risk_per_trade_pct=1.0, start_equity=10000)


def pf_of(df, sig, sl, tp, fee_bp=10.0):
    """Backtest and return (profit_factor, n_trades) net of a per-trade fee in bps."""
    cfg = cost_cfg(sl, tp)
    res = run_backtest(df, sig, cfg)
    if len(res.trades) < 15:
        return None, len(res.trades)
    # apply round-trip fee as a fraction of notional risked
    pnl = np.array([t.pnl for t in res.trades])
    notional = np.array([t.entry * t.lots for t in res.trades])
    pnl = pnl - notional * (fee_bp / 10000.0)
    gw, gl = pnl[pnl > 0].sum(), -pnl[pnl < 0].sum()
    return (gw / gl if gl > 0 else 99.0), len(pnl)


def main():
    assets = [("BTCUSDT", "1h", 900), ("ETHUSDT", "1h", 900), ("SOLUSDT", "1h", 900)]
    print("Fetching data (cached after first run)...")
    data = {}
    for sym, iv, days in assets:
        d = fetch(sym, iv, days)
        data[(sym, iv)] = d
        print(f"  {sym} {iv}: {len(d)} bars {d.time.iloc[0].date()}..{d.time.iloc[-1].date()}")

    # three-way split (same proportions on every asset)
    def split(df):
        n = len(df)
        a, b = int(n * 0.50), int(n * 0.75)
        return (df.iloc[:a].reset_index(drop=True),
                df.iloc[a:b].reset_index(drop=True),
                df.iloc[b:].reset_index(drop=True))

    configs = []
    for fam, plist in SPACE.items():
        for p in plist:
            for sl, tp in EXITS:
                for fname in FILTERS:
                    configs.append((fam, p, sl, tp, fname))
    print(f"\nSearch space: {len(configs)} configs x {len(assets)} assets = "
          f"{len(configs)*len(assets)} backtests per split\n")

    # --- stage 1+2: train/validation, select survivors ---
    survivors = []
    for i, (fam, p, sl, tp, fname) in enumerate(configs):
        ok = True
        val_pfs = []
        for key, df in data.items():
            tr, va, _ho = split(df)
            for part, store in ((tr, False), (va, True)):
                s = FILTERS[fname](part, gen_signals(part, fam, p))
                pf, n = pf_of(part, s, sl, tp)
                if pf is None or pf <= 1.0:
                    ok = False; break
                if store:
                    val_pfs.append(pf)
            if not ok:
                break
        if ok:
            survivors.append((fam, p, sl, tp, fname, float(np.mean(val_pfs))))
        if (i + 1) % 100 == 0:
            print(f"  screened {i+1}/{len(configs)}  survivors so far: {len(survivors)}")

    print(f"\n=== survivors of TRAIN+VALIDATION on ALL {len(assets)} assets: "
          f"{len(survivors)} / {len(configs)} ===")
    survivors.sort(key=lambda x: -x[5])
    for s in survivors[:15]:
        print(f"   {s[0]:11} p={str(s[1]):18} sl/tp={s[2]}/{s[3]} filt={s[4]:6} val_pf={s[5]:.2f}")

    # --- chance baseline ---
    # P(a coin-flip strategy beats PF>1 on 6 independent windows) ~ 0.5^6
    exp_by_chance = len(configs) * (0.5 ** (len(assets) * 2))
    print(f"\nExpected survivors BY PURE CHANCE (~coin flips): {exp_by_chance:.1f}")
    print(f"Actual survivors: {len(survivors)}  -> "
          f"{'ABOVE chance (promising)' if len(survivors) > exp_by_chance*2 else 'CONSISTENT WITH CHANCE (no edge)'}")

    # --- stage 3: LOCKED HOLDOUT, touched once ---
    if survivors:
        print("\n=== HOLDOUT (touched once) — top 10 survivors ===")
        print(f"  {'strategy':11} {'params':18} {'filt':6} {'holdout PF per asset':30}")
        passed = 0
        for fam, p, sl, tp, fname, vpf in survivors[:10]:
            pfs = []
            for key, df in data.items():
                _tr, _va, ho = split(df)
                s = FILTERS[fname](ho, gen_signals(ho, fam, p))
                pf, n = pf_of(ho, s, sl, tp)
                pfs.append(pf if pf is not None else float("nan"))
            allpos = all((x is not None and not np.isnan(x) and x > 1.0) for x in pfs)
            passed += allpos
            txt = " ".join(f"{x:.2f}" if x is not None and not np.isnan(x) else " n/a" for x in pfs)
            print(f"  {fam:11} {str(p):18} {fname:6} {txt:30} {'<< PASSES' if allpos else ''}")
        print(f"\nStrategies profitable on the untouched holdout across ALL assets: {passed}")


if __name__ == "__main__":
    main()
