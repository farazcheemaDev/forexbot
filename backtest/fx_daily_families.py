"""THE SLOWER FOREX FAMILIES NEVER RUN HERE - currency factors, the pre-Fed drift, crosses, weekend gaps, a better trend
book (2026-10-22)

THE USER (2026-10-22): "test every possible thing or strategy you have ... I want a crazy good strategy". fx_intraday_pub.py
took the intraday side. These are the daily-to-monthly families the repo never ran (doc 18, doc 02's forex entries):
  D1 XS-MOM     currencies ranked by their 12-1 month return vs the dollar (the dollar counts as a currency at 0): long the
                top 2, short the bottom 2, monthly (Menkhoff, Sarno, Schmeling & Schrimpf 2012)
  D2 XS-VALUE   the same on the 5-year return, reversed: long the 2 that fell most, short the 2 that rose most (the usual
                proxy for currency value; Asness, Moskowitz & Pedersen 2013)
  D3 VAL+MOM    half each
                Fed H.10 noon rates 1996-2026, 7 currencies; costs fx_drivers.COST (spread on turnover; swap per night)
  D4 PRE-FED    long NASDAQ from 24h before each FOMC statement to 5 minutes before it (Lucca & Moench 2015); HistData
                NSXUSD minute bars 2010-2026, 161 statements in the ForexFactory calendar; control = the same window on
                every other weekday
  D5 CROSSES    AUDNZD, EURGBP, EURCHF built from HistData's majors, 17:00 New York closes: fade a 20-day z-score beyond
                2, out back inside 0.5 or after 10 days (the retail "AUDNZD ranges" idea, never run here)
  D6 WEEKEND    FX majors: fade a Sunday-open gap over 0.15% from Friday's close, out at the fill or Monday 12:00 New York;
                entered 5 minutes after the open at 3x the normal spread (Sunday-open spreads are wide)
  D7 TREND+     fx_tsmom.py's 12-month book (reproduced first) against a 3-speed version (the average of the 1-, 3- and
                12-month signs - Carver's / AQR's standard) and against 23 markets (+ FTSE, CAC, Hang Seng, ASX, copper,
                natural gas, Brent)
PASS  net > 0 with t >= 2 on BOTH halves (60/40 by date), Holm p < 0.05 across D1-D7's primary cells.
COSTS shown SWAP-FREE (Exness grants swap-free status to many accounts: the user must check theirs) and WITH Exness swap.

REGISTERED BEFORE THE RUN (2026-10-22)
  E1 D1 XS-MOM ~0 after 2010 (currency momentum faded after the 1990s); fails a half.
  E2 D2 XS-VALUE positive over 1996-2026 swap-free, t < 2 on a half.
  E3 D4 PRE-FED positive before 2016 and ~0 after (Kurov, Wolfe & Gilbert 2021); fails a half; 161 events cannot reach Holm.
  E4 D5 CROSSES: AUDNZD positive gross, all three fail after costs on a half.
  E5 D6 WEEKEND: dead after the Sunday spread.
  E6 D7: 3-speed has a higher Sharpe than 12-month on both halves; 23 markets beat 16 on both halves; neither is above 0.8.
  E7 Nothing passes Holm except possibly the trend book (which already passed as fx_tsmom.py).

RESULT (2026-10-22, logs/fx_daily_families.txt) - nothing passes; one lead (the pre-Fed drift).
  D1 XS-MOM ~0 (t -0.14), D2 XS-VALUE +0.07%/mo t +0.67 (holdout negative), D3 -0.04: currency factors are dead on spot.
  D4 PRE-FED +0.25% an event (128, swap-free) t +3.14, tune t +1.51 / holdout +2.84, Holm 0.025 - but the same window on other
  weekdays earns +0.05% (NASDAQ's drift), and it is all after 2016 (+0.35%, t +3.35; before: +0.04%) - E3's "gone after
  2016" WRONG in direction, right that it fails. D5 crosses: AUDNZD -0.03%, EURGBP +0.03% (tune negative), EURCHF +0.07% t
  +0.97 - dead. D6 weekend gaps: fill 67-73% of the time and still lose or flip after the Sunday spread. D7: the 12-month
  16-market book reproduces (+5.4%/yr swap-free, t +2.71, holdout t +1.81); 3-speed is WORSE (+3.6%), 23 markets the same
  (+5.4%) - E6 WRONG. With Exness swap every trend version loses.

    python -m backtest.fx_daily_families
"""
from __future__ import annotations

import sys
import warnings
from math import erf, sqrt
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest import fx_drivers as fd  # noqa: E402
from backtest.fx_anomalies import yf_daily  # noqa: E402
from backtest.fx_tsmom import MARKETS, START, VOL_T  # noqa: E402

LOG = ROOT / "logs" / "fx_daily_families.txt"
HD = ROOT / "strategy_analysis" / "data" / "histdata"
TUNE = 0.60
EXTRA = {"^FTSE": ("FTSE", 1.5, 2.0), "^FCHI": ("CAC", 1.5, 2.0), "^HSI": ("Hang Seng", 3.0, 2.0),
         "^AXJO": ("ASX 200", 2.0, 2.0), "HG=F": ("copper", 3.0, 2.0), "NG=F": ("natgas", 10.0, 2.0),
         "BZ=F": ("Brent", 3.0, 2.0)}                       # spreads / swaps ASSUMED from Exness's comparable symbols


def tt(x):
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    return x.mean() / (x.std(ddof=1) / np.sqrt(len(x))) if len(x) > 2 and x.std(ddof=1) > 0 else 0.0


def pv(t):
    return 2 * (1 - 0.5 * (1 + erf(abs(t) / sqrt(2))))


def halves(x: pd.Series):
    x = x.dropna()
    cut = int(len(x) * TUNE)
    return x.iloc[:cut], x.iloc[cut:]


def row(lab, x: pd.Series, per_year, unit="%"):
    a, b = halves(x)
    k = 100 if unit == "%" else 1e4
    sh = x.mean() / x.std(ddof=1) * np.sqrt(per_year) if x.std(ddof=1) > 0 else 0.0
    return (f"   {lab:<40}{len(x):>5}{x.mean() * k:>+8.2f}{tt(x):>+7.2f}{a.mean() * k:>+8.2f}{tt(a):>+6.2f}{b.mean() * k:>+8.2f}"
            f"{tt(b):>+6.2f}{sh:>7.2f}"), dict(t=tt(x), ta=tt(a), tb=tt(b), ma=a.mean(), mb=b.mean())


HDR = f"   {'':<40}{'n':>5}{'mean':>8}{'t':>7}{'tune':>8}{'t':>6}{'hold':>8}{'t':>6}{'Sharpe':>7}"


# ---------------------------------------------------------------- D1-D3
def currency_factors(L, P):
    starts, ret, nights = fd.grid("M")
    fx = fd.md.load("fx_h10.csv")[fd.CCY]
    px = fd.asof(fx, starts)
    mom = px.shift(1) / px.shift(12) - 1
    val = -(px / px.shift(60) - 1)
    sp = pd.Series({c: fd.COST[c][0] for c in fd.CCY})
    sw_l = pd.Series({c: fd.COST[c][1] for c in fd.CCY})
    sw_s = pd.Series({c: fd.COST[c][2] for c in fd.CCY})

    def net(pos):
        pos = pos.reindex(ret.index).fillna(0.0).where(ret.notna(), 0.0)
        n = pos.abs().sum(axis=1).replace(0, np.nan)
        g = (pos * ret.fillna(0)).sum(axis=1)
        turn = (pos - pos.shift(1).fillna(0)).abs()
        cost = (turn * sp / 1e4).sum(axis=1)          # a full round trip charged on each change (in at half, out at half)
        swap = ((pos.clip(lower=0) * sw_l + (-pos).clip(lower=0) * sw_s).mul(nights, axis=0) / 1e4).sum(axis=1)
        keep = n.notna()
        return ((g - cost) / n)[keep].dropna(), ((g - cost + swap) / n)[keep].dropna()

    L += ["D1-D3 CURRENCY FACTORS (monthly, % a month; 7 currencies vs USD, long top 2 / short bottom 2)", HDR]
    p_mom, p_val = fd.xs(mom.dropna(how="all")), fd.xs(val.dropna(how="all"))
    both = (p_mom.reindex(p_val.index).fillna(0) + p_val) / 2
    for lab, pos in (("D1 XS-MOM 12-1", p_mom), ("D2 XS-VALUE 5-year reversal", p_val), ("D3 VAL+MOM", both)):
        sf, ws = net(pos)
        s, r = row(f"{lab}, swap-free", sf, 12)
        L.append(s)
        P.append(dict(cell=lab, **r))
        L.append(row(f"{lab}, with Exness swap", ws, 12)[0])
        post = sf[sf.index >= "2010-01-01"]
        L.append(f"   {'':<40}since 2010: {post.mean() * 100:+.2f}%/mo t {tt(post):+.2f}")
    L.append("")


# ---------------------------------------------------------------- D4
def minute_px(name):
    d = pd.read_parquet(HD / f"{name}.parquet")
    return d.t.to_numpy(), d.c.to_numpy()


def at(t, c, ts_ms):
    i = np.searchsorted(t, ts_ms, side="right") - 1
    return np.where(i >= 0, c[np.clip(i, 0, None)], np.nan)


def pre_fed(L, P):
    ff = fd.md.load("ff_2007_2026.csv")
    st = pd.to_datetime(ff[(ff.currency == "USD") & (ff.name == "FOMC Statement")].utc)
    t, c = minute_px("NSXUSD")
    first = pd.Timestamp(t[0], unit="ms")
    st = st[st > first + pd.Timedelta(days=2)]
    ms = lambda x: (pd.DatetimeIndex(x).as_unit("ms").asi8)  # noqa: E731
    e0, e1 = ms(st - pd.Timedelta(hours=24)), ms(st - pd.Timedelta(minutes=5))
    r = at(t, c, e1) / at(t, c, e0) - 1
    cost_sf, swap = 1.27e-4, 2.04e-4
    ev = pd.Series(r - cost_sf, index=st.values).dropna()
    # control: the same clock window ending at the same UTC time on every weekday that is not an FOMC day
    days = pd.bdate_range(first + pd.Timedelta(days=3), pd.Timestamp(t[-1], unit="ms") - pd.Timedelta(days=1))
    hh = st.dt.hour.mode().iloc[0]
    ctl_end = (days + pd.Timedelta(hours=int(hh))).difference(st.dt.floor("h"))
    cr = at(t, c, ms(ctl_end - pd.Timedelta(minutes=5))) / at(t, c, ms(ctl_end - pd.Timedelta(hours=24))) - 1
    ctl = pd.Series(cr - cost_sf, index=ctl_end).dropna()
    L += ["D4 PRE-FED DRIFT (NASDAQ, % a trade, 24h before the statement -> 5 min before)", HDR]
    s, rr = row("D4 pre-FOMC, swap-free", ev, 8)
    L.append(s)
    P.append(dict(cell="D4 pre-FOMC", **rr))
    L.append(row("D4 pre-FOMC, with one night's swap", ev - swap, 8)[0])
    L.append(row("control: same window, other weekdays", ctl, 252)[0])
    for lab, m in (("before 2016", ev.index < "2016-01-01"), ("2016 on", ev.index >= "2016-01-01")):
        x = ev[m]
        L.append(f"   {lab:<12} {len(x):>3} events {x.mean() * 100:+.3f}% t {tt(x):+.2f}, won {(x > 0).mean() * 100:.0f}%")
    L.append("")


# ---------------------------------------------------------------- D5 / D6
def daily_closes(pair):
    d = pd.read_parquet(HD / f"{pair}.parquet")
    lt = pd.to_datetime(d.t, unit="ms").dt.tz_localize("UTC").dt.tz_convert("America/New_York").dt.tz_localize(None)
    s = pd.Series(d.c.to_numpy(), index=lt)
    s = s[(s.index.hour < 17) & (s.index.dayofweek < 5)]
    return s.groupby(s.index.normalize()).last()


def crosses(L, P):
    maj = {p: daily_closes(p) for p in ("AUDUSD", "NZDUSD", "EURUSD", "GBPUSD", "USDCHF")}
    X = {"AUDNZD": (maj["AUDUSD"] / maj["NZDUSD"], 3.0), "EURGBP": (maj["EURUSD"] / maj["GBPUSD"], 2.0),
         "EURCHF": (maj["EURUSD"] * maj["USDCHF"], 2.5)}               # spreads ASSUMED (Exness crosses)
    L += ["D5 CROSSES MEAN REVERSION (% a trade; fade |z20| > 2, out inside 0.5 or after 10 days)", HDR]
    for name, (s, spb) in X.items():
        s = s.dropna()
        z = (s - s.rolling(20).mean()) / s.rolling(20).std()
        tr, nights = [], []
        i, n = 20, len(s)
        while i < n - 1:
            if abs(z.iloc[i]) > 2:
                side = -np.sign(z.iloc[i])
                j = i + 1
                while j < n - 1 and abs(z.iloc[j]) > 0.5 and j - i < 10:
                    j += 1
                tr.append((s.index[i], side * (s.iloc[j] / s.iloc[i] - 1) - spb / 1e4))
                nights.append((s.index[j] - s.index[i]).days)
                i = j + 1
            else:
                i += 1
        x = pd.Series([v for _, v in tr], index=[k for k, _ in tr])
        s1, r = row(f"D5 {name}, swap-free", x, len(x) / ((s.index[-1] - s.index[0]).days / 365))
        L.append(s1)
        P.append(dict(cell=f"D5 {name}", **r))
        L.append(row(f"D5 {name}, with swap 0.5bp a night", x - np.array(nights) * 0.5e-4, 12)[0])
    L.append("")


def weekend(L, P):
    L += ["D6 WEEKEND GAP FADE (% a trade; gap > 0.15%, in 5 min after the open at 3x spread, out at the fill or Mon 12:00 NY)", HDR]
    for pair, spb in (("EURUSD", 1.39), ("GBPUSD", 1.48), ("USDJPY", 1.29), ("AUDUSD", 1.6)):
        d = pd.read_parquet(HD / f"{pair}.parquet")
        lt = pd.to_datetime(d.t, unit="ms").dt.tz_localize("UTC").dt.tz_convert("America/New_York").dt.tz_localize(None)
        s = pd.Series(d.c.to_numpy(), index=lt)
        dow, hr = s.index.dayofweek, s.index.hour
        fri = s[(dow == 4) & (hr < 17)]
        fri_c = fri.groupby(fri.index.normalize()).last()
        sun = s[(dow == 6) & (hr >= 17)]
        out = []
        for day, grp in sun.groupby(sun.index.normalize()):
            f = fri_c[(fri_c.index < day) & (fri_c.index >= day - pd.Timedelta(days=3))]
            if not len(f) or len(grp) < 10:
                continue
            fc = f.iloc[-1]
            gap = grp.iloc[0] / fc - 1
            if abs(gap) < 0.0015:
                continue
            side = -np.sign(gap)
            e = grp.iloc[min(5, len(grp) - 1)]
            path = s[(s.index > grp.index[min(5, len(grp) - 1)]) & (s.index <= day + pd.Timedelta(hours=36))]
            hit = np.flatnonzero((path.to_numpy() - fc) * side >= 0) if len(path) else []
            x = fc if len(hit) else (path.iloc[-1] if len(path) else e)
            out.append((day, side * (x / e - 1) - 3 * spb / 1e4))
        x = pd.Series([v for _, v in out], index=[k for k, _ in out])
        s1, r = row(f"D6 {pair}", x, 30)
        L.append(s1 + f"   filled {np.mean([v > 0 for v in x]) * 100:.0f}% won")
        P.append(dict(cell=f"D6 {pair}", **r))
    L.append("")


# ---------------------------------------------------------------- D7
def trend(L, P):
    warnings.filterwarnings("ignore")
    allm = {**MARKETS, **EXTRA}
    C = pd.DataFrame({tk: yf_daily(tk, start="2003-01-01").Close for tk in allm}).sort_index()
    C = C[C.index >= "2003-01-01"].ffill(limit=5)
    R = C.pct_change()
    R = R.where(R.abs() < 0.25)
    vol = R.rolling(60, min_periods=40).std() * np.sqrt(252)
    me = C.resample("ME").last().index
    me = me[me >= START]
    days = R.index
    past = {k: C / C.shift(21 * k) - 1 for k in (1, 3, 12)}

    def book(mk, speeds):
        rows, prev_w = [], pd.Series(0.0, index=mk)
        sp = pd.Series({tk: allm[tk][1] for tk in mk}) / 1e4
        sw = pd.Series({tk: allm[tk][2] for tk in mk}) / 1e4
        for a, b in zip(me[:-1], me[1:]):
            ia = days.searchsorted(a, side="right") - 1
            s = sum(np.sign(past[k].iloc[ia][mk]) for k in speeds) / len(speeds)
            v = vol.iloc[ia][mk]
            live = np.isfinite(s) & (v > 0)
            w = (s * (VOL_T / v) / len(mk)).where(live, 0.0).fillna(0.0)
            seg = R[(R.index > days[ia]) & (R.index <= b)][mk].fillna(0.0)
            if not len(seg):
                continue
            g = seg.mul(w, axis=1).sum(axis=1)
            nights = pd.Series(seg.index.to_series().diff().dt.days.fillna(1).to_numpy(), index=seg.index)
            spread = pd.Series(0.0, index=seg.index)
            spread.iloc[0] = ((w - prev_w).abs() * sp).sum()
            rows.append(pd.DataFrame({"sf": g - spread, "sw": g - spread - nights * (w.abs() * sw).sum()}))
            prev_w = w
        x = pd.concat(rows)
        cut = x.index[int(len(x) * TUNE)]
        k = VOL_T / (x.sf[x.index < cut].std() * np.sqrt(252))
        return x * k

    L += ["D7 TREND BOOK (daily returns, % a day; scaled to 10% vol on the tune half)", HDR]
    m16 = list(MARKETS)
    m23 = m16 + list(EXTRA)
    res = {}
    for lab, mk, sp_ in (("12-month, 16 markets (fx_tsmom.py)", m16, (12,)), ("3-speed, 16 markets", m16, (1, 3, 12)),
                         ("12-month, 23 markets", m23, (12,)), ("3-speed, 23 markets", m23, (1, 3, 12))):
        x = book(mk, sp_)
        res[lab] = x
        s, r = row(lab + ", swap-free", x.sf, 252)
        c = (1 + x.sf).cumprod()
        L.append(s + f"   {x.sf.mean() * 25200:+.1f}%/yr, fall {(1 - c / c.cummax()).max() * 100:.0f}%")
        L.append(row(lab + ", with swap", x.sw, 252)[0])
        P.append(dict(cell="D7 " + lab, **r))
    L.append("")
    return res


def main():
    L = [f"backtest/fx_daily_families.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC", ""]
    P = []
    currency_factors(L, P)
    pre_fed(L, P)
    crosses(L, P)
    weekend(L, P)
    res = trend(L, P)
    D = pd.DataFrame(P)
    D["p"] = [pv(t) for t in D.t]
    o = np.argsort(D.p.to_numpy())
    run, holm = 0.0, np.empty(len(D))
    for k, i in enumerate(o):
        run = max(run, (len(D) - k) * D.p.iloc[i])
        holm[i] = min(run, 1.0)
    D["holm"] = holm
    D["pass"] = (D.ma > 0) & (D.mb > 0) & (D.ta >= 2) & (D.tb >= 2) & (D.holm < 0.05)
    L += ["PRIMARY CELLS (swap-free; Holm across all)"] + [
        f"   {r['cell']:<42} t {r['t']:+.2f}  tune t {r['ta']:+.2f}  holdout t {r['tb']:+.2f}  Holm {r['holm']:.3f}  -> "
        f"{'PASS' if r['pass'] else 'fail'}" for _, r in D.iterrows()]
    g = lambda c: D[D.cell == c].iloc[0]  # noqa: E731
    sh = {k: (lambda x: (halves(x.sf)[0].mean() / halves(x.sf)[0].std(), halves(x.sf)[1].mean() / halves(x.sf)[1].std()))(v)
          for k, v in res.items()}
    e1 = not g("D1 XS-MOM 12-1")["pass"]
    e2 = g("D2 XS-VALUE 5-year reversal").t > 0 and min(g("D2 XS-VALUE 5-year reversal").ta, g("D2 XS-VALUE 5-year reversal").tb) < 2
    e3 = not g("D4 pre-FOMC")["pass"]
    e4 = not D[D.cell.str.startswith("D5")]["pass"].any()
    e5 = not D[D.cell.str.startswith("D6")]["pass"].any()
    a, b = "12-month, 16 markets (fx_tsmom.py)", "3-speed, 16 markets"
    e6 = (sh[b][0] > sh[a][0] and sh[b][1] > sh[a][1] and sh["12-month, 23 markets"][0] > sh[a][0]
          and sh["12-month, 23 markets"][1] > sh[a][1])
    e7 = not D[~D.cell.str.startswith("D7")]["pass"].any()
    L += ["", "REGISTERED PREDICTIONS",
          f"  E1 XS-MOM fails a half -> {'RIGHT' if e1 else 'WRONG'}",
          f"  E2 XS-VALUE positive, t < 2 on a half -> {'RIGHT' if e2 else 'WRONG'}",
          f"  E3 pre-FOMC fails -> {'RIGHT' if e3 else 'WRONG'}",
          f"  E4 no cross passes -> {'RIGHT' if e4 else 'WRONG'}",
          f"  E5 weekend gap dead -> {'RIGHT' if e5 else 'WRONG'}",
          f"  E6 3-speed and 23 markets each beat the 12-month 16-market book's Sharpe on both halves -> {'RIGHT' if e6 else 'WRONG'}",
          f"  E7 nothing outside the trend book passes -> {'RIGHT' if e7 else 'WRONG'}"]
    txt = "\n".join(L)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
