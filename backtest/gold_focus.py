"""GOLD ONLY, ON 16 YEARS OF MINUTE BARS: the gold ideas never run on long data (2026-10-22)

THE USER (2026-10-22): "see gold nasdaq only, not other". NASDAQ has its candidate (noise_attack.py, noise_book.py). Gold
has failed every test here - but almost all of them on 2020-2026 (Exness 1h: fx_anomalies.py T5, fx_breakout.py,
fx_capit.py) or 2026 alone (cfd_scalp.py, cfd_bigtarget.py); today's fx_intraday_pub.py (ORB / NOISE on the COMEX session)
and fx_ml_leadlag.py were the first on 2010-2026. HistData XAUUSD minute bars (2010-01 .. 2026-09, New York clock with DST)
now allow the rest:
  G1 SESSIONS     long gold in each slice of the New York day, every day: Asia 18:00-03:00, London 03:00-08:20, COMEX
                  08:20-13:30, late 13:30-17:00; and NIGHT = 18:00 -> 08:20 next morning (the "gold is a night asset"
                  pattern, fx_anomalies.py T5 on 2020-26 only). None crosses the 17:00 rollover, so no swap
  G2 DATA         US high-impact releases with a surprise score >= 1 (fx_surprises.events(), 2010-2026): gold's move the
                  surprise's way (a strong US number is bad for gold): the jump (-1 -> +5 min), and trades that FOLLOW it
                  from +1 to +15 min, +5 to +65, +5 to +245, at 2x the normal spread (gold spreads widen after news)
  G3 DAILY TREND  gold alone, Yahoo GC=F daily 2001-2026: 12-month time-series momentum (monthly, long/short), long above
                  the 200-day average (else flat), Donchian 55-day breakout / 20-day exit (long/short); against buying and
                  holding gold. Exness: 1.22bp a trade, swap 1.25bp a night either side - shown SWAP-FREE and WITH swap
  G4 NOISE        fx_intraday_pub.py's NOISE on two other gold days: London open 03:00 -> 13:30 New York, and 00:00 ->
                  17:00 New York (the COMEX session failed there)
COSTS     Exness XAUUSD 1.22bp round trip + 0.5bp slippage (G1, G4); G2 at 2.44 + 0.5bp
PASS      net > 0 with t >= 2 on BOTH halves (60/40 by date); G3's trend rules must ALSO beat buy-and-hold's Sharpe on both
          halves (gold rose 1,100 -> 4,000: a long-biased rule rides that)

REGISTERED BEFORE THE RUN (2026-10-22)
  H1 G1: NIGHT gross positive on both halves and COMEX gross negative (the published pattern); NIGHT net positive but t < 2
     on a half.
  H2 G2: the jump goes the surprise's way on >= 60% of releases; every follow-on trade nets within +-1bp - none passes.
  H3 G3: swap-free, the trend rules' Sharpe is within 0.2 of buy-and-hold's and none beats it on both halves; WITH swap,
     buy-and-hold loses ~4.5%/yr to swap (1.25bp x 365) and the long-only 200-day rule beats it.
  H4 G4: neither NOISE anchor passes.
  H5 Nothing in this file passes.

RESULT (2026-10-22, logs/gold_focus.txt) - no gold edge beyond gold rising. H1, H2, H4, H5 RIGHT; H3 WRONG.
  G1: long in ASIA (18:00 -> 03:00 NY) +4.21bp a day gross, t +4.20, both halves - a "pass" that was partly a BID-PRICE
     ARTIFACT: HistData is bid-only and the 18:00 reopen spread is wide, so the bid alone rises +1.02bp from 18:00 to 18:30
     (t +4.48). Entered at 18:30 / 19:00 instead: +2.68 / +2.67bp gross (t +3.4), at 20:00 +1.96, at 21:00 +1.22 - gold's
     own rise (+4.9bp a day, 2001-26) happens mostly in Asian hours. Net of 1.72bp a day it is ~+1bp: less than holding
     through with swap (1.25bp a night). London / COMEX / late: ~0 or negative. (HistData's 18:00 bar is missing in
     2015-2018; those days drop out of the 18:00 rows.)
  G2: the first 6 minutes after a US surprise go the surprise's way 75% of the time (+17bp) - not reachable by a retail
     order (fx_news_seconds.py: the broker's own lag); following from +1 min: -0.5 / -2.2 / -2.6bp. Dead.
  G3: buy-and-hold gold swap-free +12.3%/yr, Sharpe 0.68, fall 44%; with swap +7.8%. 12-month momentum +8.7%, above the
     200-day +8.4% (fall 39%), Donchian -0.1%: no trend rule beats holding on both halves. H3 wrong: with swap the 200-day
     rule (+5.3%) does NOT beat holding (+7.8%) - swap costs less than the gold it skips.
  G4: NOISE on gold's London (-1.43bp) and midnight (-1.94bp) days: dead, as on COMEX.

    python -m backtest.gold_focus
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest import fx_intraday_pub as fip  # noqa: E402

LOG = ROOT / "logs" / "gold_focus.txt"
COST = (1.22 + 0.5) / 1e4
TUNE = 0.60


def tt(x):
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    return x.mean() / (x.std(ddof=1) / np.sqrt(len(x))) if len(x) > 2 and x.std(ddof=1) > 0 else 0.0


def row(lab, x: pd.Series, per_year, k=1e4, extra=""):
    x = x.dropna()
    cut = int(len(x) * TUNE)
    a, b = x.iloc[:cut], x.iloc[cut:]
    sh = x.mean() / x.std(ddof=1) * np.sqrt(per_year) if x.std(ddof=1) > 0 else 0.0
    ok = a.mean() > 0 and b.mean() > 0 and tt(a) >= 2 and tt(b) >= 2
    return (f"   {lab:<44}{len(x):>6}{x.mean() * k:>+8.2f}{tt(x):>+7.2f}{a.mean() * k:>+8.2f}{tt(a):>+6.2f}"
            f"{b.mean() * k:>+8.2f}{tt(b):>+6.2f}{sh:>7.2f}  {'PASS' if ok else 'fail'}{extra}"), ok, sh, (a, b)


HDR = f"   {'':<44}{'n':>6}{'mean':>8}{'t':>7}{'tune':>8}{'t':>6}{'hold':>8}{'t':>6}{'Sharpe':>7}"


def gold_ny():
    d = pd.read_parquet(fip.HD / "XAUUSD.parquet")
    lt = pd.to_datetime(d.t, unit="ms").dt.tz_localize("UTC").dt.tz_convert("America/New_York").dt.tz_localize(None)
    return pd.Series(d.c.to_numpy(), index=pd.DatetimeIndex(lt)).sort_index()


def px_at(s: pd.Series, times: pd.DatetimeIndex, tol="5min"):
    i = s.index.searchsorted(times, side="right") - 1
    ok = i >= 0
    out = np.full(len(times), np.nan)
    j = np.clip(i, 0, None)
    near = (times - s.index[j]) <= pd.Timedelta(tol)
    out[ok & near] = s.to_numpy()[j][ok & near]
    return out


def sessions(L, S):
    days = pd.bdate_range(S.index[0].normalize() + pd.Timedelta(days=2), S.index[-1].normalize() - pd.Timedelta(days=1))
    prevd = days - pd.offsets.BDay(1)                           # the evening before: Friday for a Monday
    W = {"Asia 18:00-03:00": (prevd + pd.Timedelta(hours=18), days + pd.Timedelta(hours=3)),
         "London 03:00-08:20": (days + pd.Timedelta(hours=3), days + pd.Timedelta(hours=8, minutes=20)),
         "COMEX 08:20-13:30": (days + pd.Timedelta(hours=8, minutes=20), days + pd.Timedelta(hours=13, minutes=30)),
         "late 13:30-17:00": (days + pd.Timedelta(hours=13, minutes=30), days + pd.Timedelta(hours=16, minutes=59)),
         "NIGHT 18:00 -> 08:20": (prevd + pd.Timedelta(hours=18), days + pd.Timedelta(hours=8, minutes=20))}
    L += ["G1 SESSIONS - long gold in each slice, every day (bp a day; net of 1.72bp)", HDR]
    res = {}
    for lab, (a, b) in W.items():
        r = pd.Series(px_at(S, b) / px_at(S, a) - 1, index=days).dropna()
        res[lab] = r
        L.append(row(f"{lab}, gross", r, 252)[0])
    s, ok_n, _, (na, nb) = row("NIGHT, net", res["NIGHT 18:00 -> 08:20"] - COST, 252)
    L.append(s)
    s2, ok_c, _, _ = row("short COMEX, net", -res["COMEX 08:20-13:30"] - COST, 252)
    L.append(s2)
    L.append("")
    g = res["NIGHT 18:00 -> 08:20"]
    cut = int(len(g) * TUNE)
    c = res["COMEX 08:20-13:30"]
    h1 = g.iloc[:cut].mean() > 0 and g.iloc[cut:].mean() > 0 and c.mean() < 0 and not ok_n
    return dict(h1=h1, passes=int(ok_n) + int(ok_c))


def data(L, S):
    from backtest.fx_surprises import events
    E = events()
    E = E[(E.currency == "USD") & (E.score.abs() >= 1)]
    E = E[pd.to_datetime(E.utc) > pd.Timestamp("2010-01-05")]
    t0 = pd.DatetimeIndex(pd.to_datetime(E.utc)).tz_localize("UTC").tz_convert("America/New_York").tz_localize(None).floor("min")
    side = -np.sign(E.score.to_numpy())                         # a strong US number -> gold down
    W = {"jump -1 -> +5 min": (-1, 5), "follow +1 -> +15 min": (1, 15), "follow +5 -> +65 min": (5, 65),
         "follow +5 -> +245 min": (5, 245)}
    cost = (2.44 + 0.5) / 1e4
    L += [f"G2 US DATA SURPRISES -> GOLD ({len(E)} releases with |score| >= 1; bp a trade; follow-on trades net of {cost * 1e4:.2f}bp)", HDR]
    passes, jump_right = 0, np.nan
    for lab, (a, b) in W.items():
        r = side * (px_at(S, t0 + pd.Timedelta(minutes=b), "2min") / px_at(S, t0 + pd.Timedelta(minutes=a), "2min") - 1)
        x = pd.Series(r, index=t0).dropna()
        if lab.startswith("jump"):
            jump_right = (x > 0).mean()
            L.append(row(lab + " (gross, not tradable)", x, 120, extra=f"   right way {jump_right * 100:.0f}%")[0])
        else:
            s, ok, _, _ = row(lab + ", net", x - cost, 120)
            L.append(s)
            passes += ok
    L.append("")
    return dict(h2=(jump_right >= 0.6) and passes == 0, passes=passes)


def trend(L):
    from backtest.fx_anomalies import yf_daily
    g = yf_daily("GC=F", start="2000-01-01").Close
    g = g[g.index >= "2001-01-01"]
    r = g.pct_change()
    r = r.where(r.abs() < 0.15).fillna(0.0)
    nights = pd.Series(g.index.to_series().diff().dt.days.fillna(1).to_numpy(), index=g.index)
    me = g.resample("ME").last()
    ts = np.sign(me / me.shift(12) - 1).reindex(g.index, method="ffill").shift(1)
    ma = (g > g.rolling(200).mean()).astype(float).shift(1)
    hi, lo = g.rolling(55).max().shift(1), g.rolling(20).min().shift(1)
    lo55, hi20 = g.rolling(55).min().shift(1), g.rolling(20).max().shift(1)
    don, p = [], 0.0
    for i in range(len(g)):
        c = g.iloc[i]
        if p <= 0 and np.isfinite(hi.iloc[i]) and c > hi.iloc[i]:
            p = 1.0
        elif p >= 0 and np.isfinite(lo55.iloc[i]) and c < lo55.iloc[i]:
            p = -1.0
        elif p > 0 and c < lo.iloc[i]:
            p = 0.0
        elif p < 0 and c > hi20.iloc[i]:
            p = 0.0
        don.append(p)
    don = pd.Series(don, index=g.index).shift(1)
    pos = {"buy and hold": pd.Series(1.0, index=g.index), "12-month momentum (long/short)": ts,
           "long above the 200-day average": ma, "Donchian 55 / 20 (long/short)": don}
    L += ["G3 GOLD DAILY TREND (Yahoo GC=F 2001-2026; % a day x 100 = bp)", HDR]
    out = {}
    for lab, pz in pos.items():
        pz = pz.fillna(0.0)
        turn = pz.diff().abs().fillna(pz.abs())
        sf = pz * r - turn * 1.22e-4 / 2 * 2 / 2           # half the round trip on each change of 1 unit
        ws = sf - pz.abs() * nights * 1.25e-4
        s, ok, sh, (a, b) = row(lab + ", swap-free", sf, 252)
        c = (1 + sf).cumprod()
        L.append(s + f"   {sf.mean() * 25200:+.1f}%/yr, fall {(1 - c / c.cummax()).max() * 100:.0f}%")
        s2, _, sh2, _ = row(lab + ", with swap", ws, 252)
        L.append(s2 + f"   {ws.mean() * 25200:+.1f}%/yr")
        out[lab] = dict(sh=(a.mean() / a.std(), b.mean() / b.std()), ws=ws.mean() * 25200, sh_all=sh)
    L.append("")
    bh = out["buy and hold"]
    beats = [k for k in out if k != "buy and hold" and out[k]["sh"][0] > bh["sh"][0] and out[k]["sh"][1] > bh["sh"][1]]
    L.append(f"   trend rules beating buy-and-hold's Sharpe on BOTH halves (swap-free): {beats or 'none'}")
    L.append("")
    h3 = (all(abs(out[k]["sh_all"] - bh["sh_all"]) <= 0.2 for k in out) and not beats
          and out["long above the 200-day average"]["ws"] > bh["ws"])
    return dict(h3=h3, beats=beats)


def noise_anchors(L):
    fip.INSTR["gold London 03:00-13:30"] = ("XAUUSD", "America/New_York", "03:00", 630, 1.22)
    fip.INSTR["gold 00:00-17:00"] = ("XAUUSD", "America/New_York", "00:00", 1019, 1.22)
    L += ["G4 NOISE ON TWO OTHER GOLD DAYS (bp a day, net of 1.72bp a round trip)", HDR]
    passes = 0
    for nm in ("gold London 03:00-13:30", "gold 00:00-17:00"):
        A, dates, prev = fip.session(nm)
        g, _, n = fip.noise(A, prev)
        s, ok, _, _ = row(nm, pd.Series(g - COST * n, index=dates), 252)
        L.append(s)
        passes += ok
    L.append("")
    return dict(h4=passes == 0, passes=passes)


def main():
    S = gold_ny()
    L = [f"backtest/gold_focus.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; HistData XAUUSD {S.index[0]:%Y-%m-%d}.."
         f"{S.index[-1]:%Y-%m-%d} (New York clock); first 60% = tune", ""]
    r1 = sessions(L, S)
    r2 = data(L, S)
    r3 = trend(L)
    r4 = noise_anchors(L)
    total = r1["passes"] + r2["passes"] + len(r3["beats"]) + r4["passes"]
    L += ["REGISTERED PREDICTIONS",
          f"  H1 NIGHT gross + on both halves, COMEX gross -, NIGHT net fails a half -> {'RIGHT' if r1['h1'] else 'WRONG'}",
          f"  H2 the jump goes the surprise's way >= 60% and no follow-on trade passes -> {'RIGHT' if r2['h2'] else 'WRONG'}",
          f"  H3 trend ~ buy-and-hold swap-free, none beats it on both halves; with swap the 200-day rule beats it -> "
          f"{'RIGHT' if r3['h3'] else 'WRONG'}",
          f"  H4 no NOISE anchor passes -> {'RIGHT' if r4['h4'] else 'WRONG'}",
          f"  H5 nothing passes -> {'RIGHT' if total == 0 else 'WRONG'} ({total})"]
    txt = "\n".join(L)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
