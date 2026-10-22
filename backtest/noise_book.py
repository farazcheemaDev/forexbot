"""THE BEST EXNESS BOOK THE SEARCH FOUND, AS AN ACCOUNT: NASDAQ NOISE (+ the pre-Fed drift) on $300 (2026-10-22)

fx_intraday_pub.py / noise_attack.py: NOISE on NASDAQ (Zarattini, Aziz & Barbon 2024) nets +2.25bp a day at Exness costs,
2010-11..2026-09, Sharpe 0.74 at 1x, positive in all 6 decision phases, at every lookback, on Exness's own 2026 bars (daily
correlation 0.93 with HistData), alpha over the session drift t +2.99 - but tune t +1.99, one hundredth under the line, and
costs x2 take t to 1.5. fx_daily_families.py: the pre-FOMC drift on NASDAQ +0.25% an event (control +0.05%), 128 events,
tune t +1.51. Everything else in the forex search failed.

THE ACCOUNT QUESTION. Exness's smallest NASDAQ position (USTECm 0.05 lot, ~$1,546 at 30,000) is ~5x a $300 account, so a
$300 account cannot run this at 1x. Sizing, each pre-registered:
  Lx     constant leverage x1..x5 of current equity (the 0.05-lot minimum is stated in today's prices beside the table:
         NASDAQ was ~2,100 in 2010, so a historical minimum would bind on nothing then and on everything now)
  VOL    the paper's sizing: leverage = min(4, 2% / NASDAQ's 14-day daily volatility)
  + FED  the pre-FOMC drift added on its 8 days a year at the same leverage (one night's swap, 2.04bp, charged)
  HIS    his monthly target (his_monthly_target.py: he stops at ~+10% a month) on top of x3: no new trade for the rest of
         the month once the month is +10%
REPORTED  $300 after 12 months (every monthly start: typical / bad 1-in-4 / worst), CAGR, the biggest fall, the worst month
          and day, months up - over 2010-2026 and the holdout (last 40% of days)

REGISTERED BEFORE THE RUN (2026-10-22)
  B1 at x3 the typical year is +10..+25% with a biggest fall of 25-40%.
  B2 the paper's VOL sizing has a higher Sharpe than x3 (it sizes down in wild markets) - but NASDAQ's edge lives in the
     wild days (noise_attack.py A8), so: WRONG is likely; registered as "VOL Sharpe <= x3's".
  B3 + FED raises the typical year by 1-3 points at the same fall.
  B4 his monthly stop lowers the typical year (it cuts the months that run).

RESULT (2026-10-22, logs/noise_book.txt; BACKTEST) - a real but modest book; at $300 Exness forces it to x5.
  $300, constant leverage, 2010-2026 / holdout: x3 CAGR +14.2% / +17.1%, typical year $333 / $333, fall 37% / 29%, worst
  month -12.7%, worst day -8.2%; x5 (the 0.05-lot minimum on $300) +21.6% / +26.2%, fall 56% / 45%, worst month -20%,
  worst day -13.7%. The paper's vol sizing is worse here (Sharpe 0.61 vs 0.74: the edge lives in wild days). + the pre-Fed
  drift: x3 CAGR +18.9% / +27.1%, Sharpe 0.90 / 1.14, fall 42% / 30%. His +10% monthly stop changes nothing (~0). B1, B2
  RIGHT; B3 WRONG (FED adds ~5 points, and 5 points of fall); B4 WRONG (no effect, not lower).

    python -m backtest.noise_book
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest.fx_intraday_pub import INSTR, SLIP, TUNE, noise, session  # noqa: E402

LOG = ROOT / "logs" / "noise_book.txt"
LOT_PTS = 0.05            # USTECm minimum lot; $1 a point a lot


def fed_days(dates):
    from backtest import fx_drivers as fd
    from backtest.fx_daily_families import at, minute_px
    ff = fd.md.load("ff_2007_2026.csv")
    st = pd.to_datetime(ff[(ff.currency == "USD") & (ff.name == "FOMC Statement")].utc)
    t, c = minute_px("NSXUSD")
    ms = lambda x: pd.DatetimeIndex(x).as_unit("ms").asi8  # noqa: E731
    r = at(t, c, ms(st - pd.Timedelta(minutes=5))) / at(t, c, ms(st - pd.Timedelta(hours=24))) - 1
    s = pd.Series(r - 1.27e-4 - 2.04e-4, index=pd.DatetimeIndex(st.dt.normalize().values)).dropna()
    return s[s.index >= dates[0]].groupby(level=0).sum()


def account(r1x: pd.Series, lev: pd.Series, px: pd.Series, start=300.0, his=None):
    """r1x: the book's daily net return at 1x; lev: the leverage that day (constant leverage of current equity - the
    0.05-lot minimum is stated beside the table, in today's prices, because NASDAQ was 2,100 in 2010 and the minimum
    then was 0.35x of $300)."""
    eq, out, month, m_start = start, [], None, start
    for d, r in r1x.items():
        if d.month != month:
            month, m_start = d.month, eq
        k = lev[d]
        if his is not None and eq >= m_start * (1 + his):
            k = 0.0
        eq = max(eq * (1 + k * r), 0.0)
        out.append(eq)
    return pd.Series(out, index=r1x.index)


def report(lab, eq: pd.Series, start=300.0):
    me = pd.concat([pd.Series([start], index=[eq.index[0] - pd.Timedelta(days=1)]), eq]).resample("ME").last().ffill()
    mo = me.pct_change().dropna()
    yr = ((me.shift(-12) / me).dropna() * start).to_numpy()
    dr = eq.pct_change().dropna()
    cg = (eq.iloc[-1] / start) ** (365.25 / (eq.index[-1] - eq.index[0]).days) - 1 if eq.iloc[-1] > 0 else -1
    sh = dr.mean() / dr.std() * np.sqrt(252) if dr.std() > 0 else 0
    return (f"   {lab:<34}${np.median(yr):>6,.0f} ${np.quantile(yr, 0.25):>6,.0f} ${yr.min():>6,.0f}{cg * 100:>+7.1f}%"
            f"{(1 - eq / eq.cummax()).max() * 100:>6.0f}%{mo.min() * 100:>+8.1f}%{dr.min() * 100:>+8.1f}%{(mo > 0).mean() * 100:>6.0f}%"
            f"{sh:>7.2f}"), np.median(yr), sh, (1 - eq / eq.cummax()).max()


def main():
    A, dates, prev = session("NASDAQ")
    cost = (INSTR["NASDAQ"][4] + SLIP) / 1e4
    g, _, n = noise(A, prev)
    r = pd.Series(g - cost * n, index=dates)
    px = pd.Series(A["o"][:, 0], index=dates)
    close = pd.Series(A["c"][:, -1], index=dates)
    vol14 = close.pct_change().rolling(14).std().shift(1).bfill()
    fed = fed_days(dates).reindex(dates).fillna(0.0)
    hold = dates[int(len(dates) * TUNE)]
    hdr = (f"   {'sizing':<34}{'typical':>7}{'bad':>8}{'worst':>8}{'CAGR':>8}{'fall':>7}{'worst mo':>9}{'worst day':>9}"
           f"{'mo up':>7}{'Sharpe':>7}")
    L = [f"backtest/noise_book.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; NASDAQ NOISE at Exness costs, $300 start, "
         f"$300 after 12 months over every monthly start; constant leverage of equity", "",
         f"   THE MINIMUM, in today's prices: USTECm 0.05 lot = ${LOT_PTS * 30000:,.0f} of NASDAQ at 30,000 -> on $300 the smallest "
         f"position is x{LOT_PTS * 30000 / 300:.1f}; x3 needs ${LOT_PTS * 30000 / 3:,.0f}, x1 ${LOT_PTS * 30000:,.0f}", ""]
    res = {}
    for span, m in (("2010-2026", dates >= dates[0]), (f"holdout ({hold:%Y-%m} on)", dates >= hold)):
        L += [f"{span}", hdr]
        rr, pp, vv, ff_ = r[m], px[m], vol14[m], fed[m]
        for k in (1, 2, 3, 4, 5):
            s, typ, sh, dd = report(f"x{k}", account(rr, pd.Series(float(k), index=rr.index), pp))
            res[(span, f"x{k}")] = (typ, sh, dd)
            L.append(s)
        vl = (0.02 / vv).clip(upper=4.0)
        s, typ, sh, dd = report("VOL (paper: min(4, 2%/vol14))", account(rr, vl, pp))
        res[(span, "VOL")] = (typ, sh, dd)
        L.append(s)
        s, typ, sh, dd = report("x3 + FED", account(rr + ff_, pd.Series(3.0, index=rr.index), pp))
        res[(span, "x3+FED")] = (typ, sh, dd)
        L.append(s)
        s, typ, sh, dd = report("x3, HIS monthly stop at +10%", account(rr, pd.Series(3.0, index=rr.index), pp, his=0.10))
        res[(span, "x3 HIS")] = (typ, sh, dd)
        L.append(s)
        L.append("")
    a = res[("2010-2026", "x3")]
    b1 = 330 <= a[0] <= 375 and 0.25 <= a[2] <= 0.40
    b2 = res[("2010-2026", "VOL")][1] <= a[1]
    b3 = res[("2010-2026", "x3+FED")][0] - a[0] >= 3 and res[("2010-2026", "x3+FED")][2] <= a[2] + 0.02
    b4 = res[("2010-2026", "x3 HIS")][0] < a[0]
    L += ["REGISTERED PREDICTIONS",
          f"  B1 x3 typical year +10..+25%, fall 25-40% (${a[0]:,.0f}, {a[2] * 100:.0f}%) -> {'RIGHT' if b1 else 'WRONG'}",
          f"  B2 VOL Sharpe <= x3's ({res[('2010-2026', 'VOL')][1]:.2f} vs {a[1]:.2f}) -> {'RIGHT' if b2 else 'WRONG'}",
          f"  B3 + FED adds 1-3 points to the typical year at the same fall -> {'RIGHT' if b3 else 'WRONG'}",
          f"  B4 his monthly stop lowers the typical year -> {'RIGHT' if b4 else 'WRONG'}"]
    txt = "\n".join(L)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
