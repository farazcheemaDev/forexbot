"""WHAT DID EACH PART OF THE FINAL VERSION DO ON THE CRASH DAYS?

Asked 2026-09-24: "but in a crash shouldn't the short-market stuff we added work the best?" risk_300.py
found the worst hour in six years on 2025-10-10, with the trend book's open units at their lows
leaving 62% of the account. This measures, for 2021-05-19, 2024-08-05 and 2025-10-10, the day
itself and the 7 days after:
  - the BTC regime label that day (the sleeve can only act on BEAR days) and breadth20;
  - the bear sleeve's position and its real-$221 daily return (logs/breadth_real_1x.pkl);
  - the market-neutral basket held that week (rebuilt exactly as bear_chop.fast_run ranks it) and
    its return;
  - the trend book's own P&L (ordering 0, the account marked at daily closes, open profit included).

REGISTERED PREDICTION (2026-09-24, before running): on all three days the regime label was NOT bear,
so the sleeve was flat; the MN basket was roughly flat (+-3%) on the day, its shorts offsetting its
longs; the trend book took the hit; in the following week the sleeve, if it switched on at all,
went LONG (capitulation), because it is a contrarian rule, not a crash short.

    python -m backtest.crash_days
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import backtest.dd_fixes as D  # noqa: E402
from backtest import blend  # noqa: E402
from backtest.bar_phase import rows_for_phase  # noqa: E402
from backtest.breadth_attack import ls_signal  # noqa: E402
from backtest.breadth_robust import breadth_n  # noqa: E402
from backtest.bull_boost import regimes  # noqa: E402
from backtest.market_neutral import btc_regime, drop_non_crypto, load_panel  # noqa: E402
from backtest.regime_signals import member_mask  # noqa: E402
from backtest.risk_300 import sim_units  # noqa: E402
from backtest.wide_book import MIN_AGE_D, eligibility  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DAYS = ("2021-05-19", "2024-08-05", "2025-10-10")


def mn_basket(C, first, elig, i, look=30, frac=0.1):
    """fast_run's ranking at period start i (lag 0): top / bottom decile by `look`-day return."""
    X = C.to_numpy(float)
    cols = list(C.columns)
    m = C.index[i].strftime("%Y-%m")
    ok = [j for j, s in enumerate(cols) if m in elig.get(s, ()) and
          (C.index[i] - pd.Timestamp(first[s])).days >= MIN_AGE_D and np.isfinite(X[i, j]) and np.isfinite(X[i - look, j])]
    past = X[i, ok] / X[i - look, ok] - 1
    k = max(int(len(ok) * frac), 3)
    order = [ok[x] for x in np.argsort(past, kind="stable")]
    return [cols[x] for x in order[-k:]], [cols[x] for x in order[:k]]


def main():
    C, F, first = load_panel()
    C.index = C.index.astype("datetime64[ns]")
    reg = btc_regime(C).reindex(C.index)
    X = C.to_numpy(float)
    elig = drop_non_crypto(eligibility(60))
    m60 = member_mask(C, first, elig) & np.isfinite(X)
    b20 = breadth_n(C, m60, 20)
    sig = ls_signal(b20, reg == "bear")
    sleeve = pd.read_pickle(ROOT / "logs" / "breadth_real_1x.pkl")["full"]
    # the ladder position held on each day (lag 1, 7 tranches) - as breadth_trade.ladder builds it
    s = sig.to_numpy()
    pos = np.zeros(len(s))
    for k in range(7):
        pos += np.r_[np.zeros(1 + k), s[:len(s) - 1 - k]] / 7
    pos = pd.Series(pos, index=sig.index)

    # trend book, ordering 0: account value at daily closes including open profit
    bear = regimes()[1000]
    bn = pd.DatetimeIndex(bear.index).as_unit("ns").asi8
    bv = bear.to_numpy(bool)
    rows = D.decompose(rows_for_phase(0, tight=True, time_stop=(100, 2.0), max_units=7))
    pts, units = sim_units(rows, bn, bv, 0)
    days = C.index
    real = pd.Series([e for _, e in pts], index=pd.DatetimeIndex([t for t, _ in pts]).as_unit("ns"))
    real = real[~real.index.duplicated(keep="last")].reindex(days, method="ffill").fillna(1.0)
    close = {c: blend.load(c) for c in blend.BOOK}
    close = {c: d.set_index(pd.DatetimeIndex(d["time"]).as_unit("ns"))["close"] for c, d in close.items() if d is not None}
    unreal = pd.Series(0.0, index=days)
    gi = days.asi8
    for coin, side, t0, t1, e, q in units:
        if coin not in close:
            continue
        a, b = np.searchsorted(gi, t0), np.searchsorted(gi, t1)
        if b <= a:
            continue
        # daily closes: the close of row d is 24h after its label
        p = close[coin].reindex(days + pd.Timedelta(hours=23), method="ffill").to_numpy()[a:b]
        unreal.iloc[a:b] += q * ((p - e) if side == "long" else (e - p))
    acct = real + unreal
    trend_r = acct.pct_change()

    for d in DAYS:
        i = days.get_loc(pd.Timestamp(d))
        start = i - ((i - 31) % 7)                 # the fast_run period (look 30, step 7) holding day i
        longs, shorts = mn_basket(C, first, elig, start)
        def basket(lo, hi):
            r = lambda names: np.nanmean([X[hi, cols.get_loc(n)] / X[lo, cols.get_loc(n)] - 1 for n in names])  # noqa: E731
            return 0.5 * r(longs) - 0.5 * r(shorts), r(longs), r(shorts)
        cols = C.columns
        day_mn, day_l, day_s = basket(i - 1, i)
        wk_mn, _, _ = basket(i - 1, min(i + 7, len(days) - 1))
        btc = X[i, cols.get_loc("BTCUSDT")] / X[i - 1, cols.get_loc("BTCUSDT")] - 1
        wk_trend = acct.iloc[min(i + 7, len(acct) - 1)] / acct.iloc[i - 1] - 1
        wk_sl = (1 + sleeve.iloc[i:i + 8]).prod() - 1
        print(f"\n{d}: BTC {btc*100:+.1f}% that day | regime label {reg.iloc[i].upper()} | breadth20 {b20.iloc[i]:.0%}")
        print(f"  trend book      day {trend_r.iloc[i]*100:+6.1f}%   next 7 days {wk_trend*100:+6.1f}%   (account incl. open profit)")
        print(f"  market-neutral  day {day_mn*100:+6.1f}%   next 7 days {wk_mn*100:+6.1f}%   (its longs {day_l*100:+.1f}%, "
              f"its shorts {day_s*100:+.1f}% that day)")
        print(f"  bear sleeve     day {sleeve.iloc[i]*100:+6.1f}%   next 7 days {wk_sl*100:+6.1f}%   position that day "
              f"{pos.iloc[i]:+.2f}, decisions next 7 days {', '.join(f'{v:+.0f}' for v in sig.iloc[i:i + 7])}")


if __name__ == "__main__":
    main()
