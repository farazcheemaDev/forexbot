"""A BOOK THAT DOES NOT CARE WHICH WAY THE MARKET GOES - tested honestly for once.

THE ASK
    A strategy that earns the same in a bull, a bear and a chop. The only construction that
    can do that structurally is CROSS-SECTIONAL: rank the universe, go long the strongest and
    short the weakest in equal dollars, so the market factor cancels inside the book rather
    than being forecast.

WHY IT IS WORTH ONE MORE TEST
    Doc 02 closed the market-neutral category, but on narrow universes: funding carry
    (2.7%/yr, dead), funding dislocation (funding_xs.py, all 18 cells negative), and one
    survivor - cross-sectional momentum at Sharpe 0.62, "genuine and too small". Meanwhile
    bear_shorts.py measured, in passing, that shorting the WEAKEST coins beat shorting the
    strongest in BOTH bull and bear weeks (+2.02%/wk bull, +0.90%/wk bear) - the same spread,
    gross, on the survivorship-free universe. That was never turned into a book with costs.

WHAT IS CHARGED, because this is a turnover strategy and turnover is what kills them
    * 855 perps including the 339 DEAD ones, point-in-time top-N by the PRIOR month's volume,
      minimum 30 days listed. Nothing knows which coins survive.
    * 12bp on the notional actually turned over at each rebalance, measured from basket
      overlap - not a flat assumption.
    * The ACTUAL funding both legs paid or received, from the archive.
    * Equal dollars each side, gross 1x (half long, half short), so the reported return is
      return on the whole account, not on one leg.

    Reported by REGIME - BTC bull / bear / chop - which is the entire point of the exercise.

    python -m backtest.market_neutral
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import blend  # noqa: E402
from backtest.wide_book import DATA, MIN_AGE_D, eligibility  # noqa: E402

FEE = 12.0 / 1e4

# EXCLUDED BY CATEGORY, not by performance. PAXG and XAUT are both claims on physical gold -
# the SAME underlying - so a decile book can put two of six short slots on one bet, and a
# "cross-sectional crypto momentum" book has no thesis about gold at all. USDCUSDT is a
# stablecoin pair whose momentum rank is meaningless. Disclosed because it cuts both ways:
# excluding them also IMPROVES the backtest (+1.130% -> +1.222%/wk, Sharpe 1.16 -> 1.22),
# and that improvement is gold's 2025-26 bull run, which is exactly the hindsight this
# project haircuts everywhere else. The category argument stands without the number; the
# number is printed next to it so a reader can judge whether it is being leaned on.
#
# Matched on the EXACT base asset. A substring filter was tried first and silently deleted
# VETUSDT ("TUSD"), UBUSDT ("BUSD"), VELVETUSDT, WCTUSDT and ZBTUSDT - VET alone was
# eligible in 27 months - then reported the loss as the effect of removing gold.
NON_CRYPTO = {"PAXG", "XAUT", "EUR", "GBP", "AEUR", "USDC", "TUSD", "BUSD", "FDUSD",
              "USDP", "DAI", "USD1", "USDE", "SUSDE"}


def drop_non_crypto(elig: dict) -> dict:
    """elig without the gold-backed and fiat/stable perps. See NON_CRYPTO."""
    return {k: v for k, v in elig.items()
            if not (k.endswith("USDT") and k[:-4] in NON_CRYPTO)}


def load_panel():
    """Daily closes and daily funding sums for every perp, plus each coin's first day."""
    close, fund, first = {}, {}, {}
    for p in sorted(DATA.glob("*_1d.csv.gz")):
        s = p.name.split("_")[0]
        try:
            d = pd.read_csv(p, parse_dates=["time"])
        except Exception:
            continue
        d = d[d.close > 0]
        if len(d) < 60:
            continue
        ser = d.set_index("time")["close"]
        close[s] = ser[~ser.index.duplicated()]
        first[s] = ser.index[0]
        f = DATA / f"{s}_funding.csv.gz"
        if f.exists():
            try:
                fr = pd.read_csv(f, parse_dates=["time"])
                fund[s] = fr.set_index("time")["rate"].resample("D").sum()
            except Exception:
                pass
    C = pd.DataFrame(close).sort_index()
    F = pd.DataFrame(fund).reindex(C.index).fillna(0.0)
    return C, F, pd.Series(first)


def btc_regime(C):
    """bull / bear / chop from BTC's own 50-day trend, shifted so it is knowable."""
    b = C["BTCUSDT"].dropna()
    ma = b.rolling(50).mean()
    slope = (ma / ma.shift(20) - 1)
    r = pd.Series("chop", index=b.index)
    r[(b > ma) & (slope > 0.02)] = "bull"
    r[(b < ma) & (slope < -0.02)] = "bear"
    return r.shift(1).ffill()


def run(C, F, first, elig, look=30, hold=7, frac=0.1, min_names=20, lag=0):
    """Long top decile / short bottom decile by `look`-day return, held `hold` days."""
    idx = C.index
    rows, prev_long, prev_short = [], set(), set()
    for i in range(look + 1, len(idx) - hold, hold):
        t0, t1 = idx[i], idx[i + hold]
        month = t0.strftime("%Y-%m")
        # SELECTION USES THE PAST ONLY. An earlier version also required a finite price at
        # i+hold, which silently excluded any coin that was delisted during the hold - i.e.
        # it selected on the future. Those coins are precisely what the short leg exists for.
        ok = [s for s in C.columns
              if month in elig.get(s, ()) and (t0 - first[s]).days >= MIN_AGE_D
              and np.isfinite(C[s].iat[i]) and np.isfinite(C[s].iat[i - look])]
        if len(ok) < min_names:
            continue
        # lag>0 ranks on data up to i-lag and still enters at i: a check that the result does
        # not depend on ranking and trading at the same close
        j = i - lag
        past = pd.Series({s: C[s].iat[j] / C[s].iat[j - look] - 1 for s in ok})
        k = max(int(len(past) * frac), 3)
        order = past.sort_values().index
        shorts, longs = list(order[:k]), list(order[-k:])
        def exit_px(s):
            """close at t1, or the last print before it if the coin stopped trading -
            Binance settles a delisted perp near mark, so the last close is the fair exit."""
            v = C[s].iloc[i:i + hold + 1].dropna()
            return float(v.iloc[-1]) if len(v) else float(C[s].iat[i])
        fwd = {s: exit_px(s) / C[s].iat[i] - 1 for s in ok}
        fnd = {s: float(F[s].iloc[i:i + hold].sum()) if s in F else 0.0 for s in ok}
        lr = float(np.mean([fwd[s] for s in longs]))
        sr = float(np.mean([fwd[s] for s in shorts]))
        lf = float(np.mean([fnd[s] for s in longs]))
        sf = float(np.mean([fnd[s] for s in shorts]))
        # half the account each side; long pays funding, short receives it
        gross = 0.5 * lr - 0.5 * sr
        carry = 0.5 * (-lf) + 0.5 * sf
        turn = (len(set(longs) ^ prev_long) + len(set(shorts) ^ prev_short)) / (2 * k * 2)
        cost = FEE * min(turn, 1.0)
        prev_long, prev_short = set(longs), set(shorts)
        rows.append(dict(t=t0, net=gross + carry - cost, gross=gross, carry=carry,
                         cost=cost, n=len(ok), long_ret=lr, short_ret=sr))
    return pd.DataFrame(rows)


def report(df, reg, lab):
    if len(df) < 20:
        print(f"  {lab}: too few periods"); return
    df = df.copy()
    df["regime"] = [reg.asof(t) if t >= reg.index[0] else "chop" for t in df.t]
    per_yr = 365 / 7
    def line(name, x):
        if len(x) < 5:
            return f"  {name:<16}{len(x):>6}      too few"
        ann = (1 + x.net.mean()) ** per_yr - 1
        sh = x.net.mean() / x.net.std(ddof=1) * np.sqrt(per_yr) if x.net.std(ddof=1) else np.nan
        return (f"  {name:<16}{len(x):>6}{x.net.mean()*100:>+9.3f}%{ann*100:>+9.1f}%"
                f"{sh:>7.2f}{x.gross.mean()*100:>+9.3f}%{x.carry.mean()*100:>+8.3f}%"
                f"{x.cost.mean()*100:>+7.3f}%")
    print(f"\n{lab}")
    print(f"  {'window':<16}{'n':>6}{'net/wk':>10}{'ann':>9}{'Sharpe':>7}{'gross':>10}"
          f"{'funding':>8}{'cost':>7}")
    print(line("ALL", df))
    for r in ("bull", "bear", "chop"):
        print(line(r, df[df.regime == r]))
    for y in sorted(df.t.dt.year.unique()):
        print(line(f"  {y}", df[df.t.dt.year == y]))


def main():
    C, F, first = load_panel()
    reg = btc_regime(C)
    print(f"panel: {C.shape[1]} perps, {C.index[0]:%Y-%m} .. {C.index[-1]:%Y-%m}")
    print(f"regime days: " + "  ".join(f"{k} {int(v)}" for k, v in reg.value_counts().items()))
    elig60 = eligibility(60)
    for look, hold in ((30, 7), (90, 7), (30, 14)):
        df = run(C, F, first, elig60, look=look, hold=hold)
        report(df, reg, f"PIT top-60 | {look}d momentum, rebalanced every {hold}d")
    report(run(C, F, first, elig60, look=30, hold=7, lag=1), reg,
           "PIT top-60 | 30d momentum, weekly, RANKED ONE DAY BEFORE ENTRY (robustness)")
    report(run(C, F, first, eligibility(100), look=30, hold=7), reg,
           "PIT top-100 | 30d momentum, rebalanced every 7d")
    report(run(C, F, first, drop_non_crypto(elig60), look=30, hold=7), reg,
           "PIT top-60 | WITHOUT gold tokens and stables - what mn_paper.py trades live")
    print("\n  A book that does not care about direction must earn in bull AND bear AND chop.")


if __name__ == "__main__":
    main()
