"""THREE SHORT IDEAS THAT HAVE NEVER BEEN TESTED HERE - on every perp that ever existed.

Every earlier short test shorted today's 12-14 big coins with price signals. This file
uses a different universe (all 864 USDT perps, 339 of them dead, backtest/perp_fetch.py)
and ideas whose reason to work is not a chart pattern.

  1. LISTING DECAY    short a NEW perp shortly after it lists and hold for weeks.
                      Structural reason: new tokens list with low float and high FDV,
                      then airdrop recipients, market makers and early investors sell
                      into whoever is buying. Supply arrives on a schedule; demand does
                      not. Never tested here - newlist.py tested the LONG side.
  2. PUMP FADE        short an established perp after a violent multi-day rise.
                      A reversal idea, and every reversal idea in this project died, so
                      it is guilty until proven. Included because in a bear the rallies
                      are short covering, which has no buyer behind it.
  3. WEAKEST COINS    each week short the coins with the worst 30-day return. The short
                      leg of cross-sectional momentum, measured by regime. The control
                      is shorting EVERYTHING, because in a bear everything falls.

WHAT IS CHARGED
    Perp prices, 12bp round trip, and the ACTUAL funding a short paid or received at
    every settlement (new listings are often crowded short, so funding can go deeply
    negative and bleed a short dry - this is the thing most likely to kill idea 1).
    Stops on daily highs; a gap through the stop fills at the open. A coin whose data
    ends while short is closed at its last close (Binance settles delistings near mark).

THE BETA PROBLEM, FACED DIRECTLY
    Short anything in 2022 and you made money. So every result is shown twice: the raw
    short return, and the EXCESS over shorting an equal-weight index of established
    perps (listed >= 365 days, point in time, dead coins included) over the same days.
    Raw return is what the account earns. Excess says whether the idea adds anything
    over just being short the market.

SIGNIFICANCE
    Trades in the same month share one market move, so they are not independent.
    t-statistics are computed across MONTHS (each month's mean trade = one observation).

PRIMARY CONFIGURATION, REGISTERED BEFORE THE DATA WAS SEEN (2026-09-21)
    Idea 1: new token (no spot history >60 days before the perp), enter at the open of
    day 1 after listing, hold 30 days, stop at +100%. Everything else in the grid is
    secondary and read with Holm in mind.
    Prediction: raw mean positive, excess positive but much smaller, funding eats a
    visible share, and 2021 (alt season) is the losing year.

    python -m backtest.bear_shorts
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

DATA = Path(__file__).resolve().parents[1] / "strategy_analysis" / "data" / "perps"
FEE = 12.0 / 1e4
ARCHIVE_START = pd.Timestamp("2020-02-01")   # perps already listed then have no listing date

COINS: dict = {}


def load():
    uni = json.load(open(DATA / "universe.json"))
    for m in uni:
        s = m["sym"]
        try:
            d = pd.read_csv(DATA / f"{s}_1d.csv.gz", parse_dates=["time"])
        except Exception:
            continue
        d = d[d.close > 0].reset_index(drop=True)
        if len(d) < 5:
            continue
        # relisted symbols have gaps; keep the FIRST continuous episode only
        gap = d.time.diff().dt.days.fillna(1)
        if (gap > 7).any():
            d = d.iloc[:int(np.argmax(gap.values > 7))].reset_index(drop=True)
            if len(d) < 5:
                continue
        f = DATA / f"{s}_funding.csv.gz"
        fr = pd.read_csv(f, parse_dates=["time"]) if f.exists() else None
        # funding cumsum weighted by that day's close, so a trade's funding is
        # (cs[exit] - cs[entry]) / entry_price - see funding_ret()
        if fr is not None and len(fr):
            day = fr.time.dt.floor("D")
            px = d.set_index("time")["close"].reindex(day).to_numpy()
            ok = np.isfinite(px)
            ft = fr.time.to_numpy()[ok]
            cs = np.cumsum(fr.rate.to_numpy()[ok] * px[ok])
        else:
            ft, cs = np.array([], dtype="datetime64[ns]"), np.array([])
        sp = m.get("spot_first")
        COINS[s] = dict(df=d, t=d.time.to_numpy(), o=d.open.to_numpy(float),
                        h=d.high.to_numpy(float), l=d.low.to_numpy(float),
                        c=d.close.to_numpy(float), q=d.qvol.to_numpy(float),
                        qmed=d.qvol.rolling(31, min_periods=1).median().to_numpy(float),
                        ft=ft, cs=cs, alive=m["alive"],
                        first=d.time.iloc[0],
                        spot=pd.Timestamp(sp + "-01") if sp else None)
    print(f"loaded {len(COINS)} perps "
          f"({sum(1 for c in COINS.values() if not c['alive'])} dead)")


def funding_ret(c, t0, t1, entry):
    """Funding a SHORT receives between t0 and t1 per unit of entry notional.
    Positive rate = longs pay shorts."""
    if not len(c["ft"]):
        return 0.0
    a = np.searchsorted(c["ft"], t0, side="right")
    b = np.searchsorted(c["ft"], t1, side="right")
    if b <= a:
        return 0.0
    lo = c["cs"][a - 1] if a > 0 else 0.0
    return float((c["cs"][b - 1] - lo) / entry)


def short(c, i, hold, stop):
    """Short at the open of bar i, out after `hold` bars or at the stop.
    Returns (exit_bar, total_ret, price_ret, funding_ret) per unit notional."""
    n = len(c["c"])
    if i >= n:
        return None
    e = c["o"][i]
    sp = e * (1 + stop) if stop else np.inf
    last = min(i + hold, n) - 1
    j, x = last, c["c"][last]
    for k in range(i, last + 1):
        if c["h"][k] >= sp:
            j, x = k, (max(sp, c["o"][k]) if k > i else sp)
            break
    t0 = c["t"][i]
    t1 = c["t"][j] + np.timedelta64(1, "D")
    pr = (e - x) / e
    fu = funding_ret(c, t0, t1, e)
    return j, pr + fu - FEE, pr, fu


# ---- point-in-time market index and regime --------------------------------------
def build_index():
    """Equal-weight daily return of perps listed >= 365 days earlier (dead included)."""
    frames = []
    for s, c in COINS.items():
        r = pd.Series(c["c"], index=pd.DatetimeIndex(c["t"])).pct_change()
        age = (r.index - c["first"]).days
        frames.append(r[age >= 365].rename(s))
    m = pd.concat(frames, axis=1, sort=True)
    idx = m.clip(-0.9, 3.0).mean(axis=1, skipna=True).fillna(0.0)
    btc = pd.Series(COINS["BTCUSDT"]["c"], index=pd.DatetimeIndex(COINS["BTCUSDT"]["t"]))
    bear = (btc < btc.rolling(50).mean()).shift(1).fillna(False)
    return idx, bear


def idx_short(idx, t0, t1):
    """Return of SHORTING the index from the open of t0's day to the close of t1's day."""
    w = idx.loc[t0:t1]
    return float(-(np.prod(1 + w.values) - 1)) if len(w) else 0.0


# ---- statistics ------------------------------------------------------------------
def month_t(ts, x):
    s = pd.Series(np.asarray(x), index=pd.DatetimeIndex(ts))
    m = s.groupby(s.index.to_period("M")).mean()
    if len(m) < 3 or m.std(ddof=1) == 0:
        return float("nan"), len(m), float("nan")
    return float(m.mean() / (m.std(ddof=1) / np.sqrt(len(m)))), len(m), float((m > 0).mean() * 100)


def summary(tr, label):
    if len(tr) < 10:
        return None
    t = tr["t0"]
    r, ex = tr["ret"].to_numpy(), tr["excess"].to_numpy()
    tt, nm, pos = month_t(t, r)
    te, _, _ = month_t(t, ex)
    return dict(label=label, n=len(tr), coins=tr["sym"].nunique(), mean=r.mean() * 100,
                med=np.median(r) * 100, win=(r > 0).mean() * 100,
                fund=tr["fund"].mean() * 100, worst=r.min() * 100, t=tt,
                ex=ex.mean() * 100, tex=te, months=nm, mpos=pos)


HDR = (f"  {'':<34}{'n':>5}{'coins':>6}{'mean':>8}{'median':>8}{'win%':>6}{'fund':>7}"
       f"{'worst':>8}{'t(mo)':>7}{'mo+%':>6} |{'excess':>8}{'t':>6}")


def row(d):
    if d is None:
        return "  (too few)"
    return (f"  {d['label']:<34}{d['n']:>5}{d['coins']:>6}{d['mean']:>+7.1f}%"
            f"{d['med']:>+7.1f}%{d['win']:>5.0f}%{d['fund']:>+6.1f}%{d['worst']:>+7.0f}%"
            f"{d['t']:>+7.2f}{d['mpos']:>5.0f}% |{d['ex']:>+7.1f}%{d['tex']:>+6.2f}")


def portfolio(tr, slots=10, gross=1.0):
    """Take trades in entry order while a slot is free; each is gross/slots of equity.
    Compounded by exit date. Returns CAGR, max DD, worst month, % months up."""
    tr = tr.sort_values("t0")
    opens, rows = [], []
    w = gross / slots
    for t0, t1, r in zip(tr["t0"], tr["t1"], tr["ret"]):
        opens = [u for u in opens if u > t0]
        if len(opens) >= slots:
            continue
        opens.append(t1)
        rows.append((t1, r * w))
    if len(rows) < 10:
        return None
    s = pd.Series([x[1] for x in rows], index=pd.DatetimeIndex([x[0] for x in rows]))
    daily = s.resample("D").sum()
    cur = np.cumprod(np.maximum(1 + daily.values, 0))
    pk = np.maximum.accumulate(np.maximum(cur, 1e-12))
    yrs = max((daily.index[-1] - daily.index[0]).days / 365.25, 0.1)
    mon = daily.resample("ME").sum()
    return dict(taken=len(rows), cagr=(max(cur[-1], 1e-12) ** (1 / yrs) - 1) * 100,
                mo=((max(cur[-1], 1e-12) ** (1 / (yrs * 12))) - 1) * 100,
                dd=float((1 - cur / pk).max() * 100), worst_mo=float(mon.min() * 100),
                up=float((mon > 0).mean() * 100))


def split_report(tr, idxs, bear, title):
    """Regime, year and time-split rows for one trade set."""
    tr = tr.copy()
    tr["bear"] = [bool(bear.asof(t)) for t in tr["t0"]]
    cut = tr["t0"].quantile(0.6)
    print(f"\n  {title}")
    print(HDR)
    print(row(summary(tr, "ALL")))
    print(row(summary(tr[tr.bear], "BTC bear at entry")))
    print(row(summary(tr[~tr.bear], "BTC bull at entry")))
    print(row(summary(tr[tr.t0 < cut], f"tune (< {cut:%Y-%m})")))
    print(row(summary(tr[tr.t0 >= cut], "HOLDOUT")))
    for y in sorted(tr.t0.dt.year.unique()):
        print(row(summary(tr[tr.t0.dt.year == y], f"  {y}")))
    return tr


# ---- idea 1: listing decay -------------------------------------------------------
def listing_trades(idx, enter_day, hold, stop, kind):
    out = []
    for s, c in COINS.items():
        if c["first"] < ARCHIVE_START:
            continue
        new = c["spot"] is None or (c["first"] - c["spot"]).days <= 60
        if (kind == "new") != new:
            continue
        got = short(c, enter_day, hold, stop)
        if got is None:
            continue
        j, r, pr, fu = got
        t0, t1 = c["t"][enter_day], c["t"][j]
        out.append(dict(sym=s, t0=pd.Timestamp(t0), t1=pd.Timestamp(t1), ret=r,
                        price=pr, fund=fu,
                        excess=pr + fu - FEE - idx_short(idx, t0, t1)))
    return pd.DataFrame(out)


# ---- idea 2: pump fade -----------------------------------------------------------
def pump_trades(idx, bear, look, thresh, hold, stop, min_age=60, bear_only=False):
    out = []
    for s, c in COINS.items():
        cl, n = c["c"], len(c["c"])
        age0 = int(np.searchsorted(c["t"], np.datetime64(c["first"] + pd.Timedelta(days=min_age))))
        i = max(age0, look + 1)
        while i < n - 1:
            ret = cl[i] / cl[i - look] - 1
            med_q = c["qmed"][i]
            if ret >= thresh and med_q >= 2e6:
                t0 = c["t"][i + 1]
                if bear_only and not bool(bear.asof(pd.Timestamp(t0))):
                    i += 1; continue
                got = short(c, i + 1, hold, stop)
                if got is None:
                    break
                j, r, pr, fu = got
                out.append(dict(sym=s, t0=pd.Timestamp(t0), t1=pd.Timestamp(c["t"][j]),
                                ret=r, price=pr, fund=fu,
                                excess=pr + fu - FEE - idx_short(idx, t0, c["t"][j])))
                i = j + 1                     # one position per coin at a time
            else:
                i += 1
    return pd.DataFrame(out)


# ---- idea 3: weakest coins -------------------------------------------------------
def weekly_panel():
    closes, vols = {}, {}
    for s, c in COINS.items():
        ix = pd.DatetimeIndex(c["t"])
        closes[s] = pd.Series(c["c"], index=ix)
        vols[s] = pd.Series(c["q"], index=ix)
    C = pd.DataFrame(closes); Q = pd.DataFrame(vols)
    first = pd.Series({s: c["first"] for s, c in COINS.items()})
    return C, Q, first


def weakest(idx, bear, C, Q, first, look=30, hold=7, frac=0.1):
    """Every `hold` days: rank eligible perps by `look`-day return, short the bottom
    decile, the top decile, and everything, equal weight, for `hold` days. Funding is
    charged at a flat per-coin rate over the window from the actual settlements."""
    days = C.index[C.index >= pd.Timestamp("2020-06-01")][::hold]
    rows = []
    for d in days:
        loc = C.index.get_loc(d)
        if loc + hold >= len(C.index) or loc < look:
            continue
        past = C.iloc[loc] / C.iloc[loc - look] - 1
        liq = Q.iloc[max(0, loc - 30):loc + 1].median()
        age = (d - first).dt.days
        ok = past.notna() & (liq >= 5e6) & (age >= 60) & C.iloc[loc + 1].notna()
        p = past[ok]
        if len(p) < 20:
            continue
        k = max(int(len(p) * frac), 3)
        order = p.sort_values().index
        groups = {"bottom": order[:k], "top": order[-k:], "all": order}
        t0 = C.index[loc + 1]
        rec = {"t0": t0, "bear": bool(bear.asof(t0)), "n": len(p)}
        for g, names in groups.items():
            rs = []
            for s in names:
                c = COINS[s]
                i = int(np.searchsorted(c["t"], np.datetime64(t0)))
                got = short(c, i, hold, None)
                if got is not None:
                    rs.append(got[1])
            rec[g] = float(np.mean(rs)) if rs else np.nan
        rows.append(rec)
    return pd.DataFrame(rows)


def main():
    load()
    idx, bear = build_index()

    print("\n" + "=" * 110)
    print("IDEA 1 - LISTING DECAY: short a new perp after it lists")
    print("=" * 110)
    print("  returns are per trade, % of the position's notional; excess = over shorting "
          "the established-perp index for the same days")
    print("\n  PRIMARY (registered): new tokens, enter day 1, hold 30d, stop +100%")
    prim = listing_trades(idx, 1, 30, 1.0, "new")
    prim = split_report(prim, idx, bear, "primary, by split")
    p = portfolio(prim, slots=10, gross=1.0)
    if p:
        print(f"\n  as a book: 10 slots, 1x gross (each position 10% of equity): "
              f"{p['taken']} taken, {p['mo']:+.2f}%/mo compounded, CAGR {p['cagr']:+.0f}%,"
              f" max DD {p['dd']:.0f}%, worst month {p['worst_mo']:+.1f}%, "
              f"{p['up']:.0f}% of months up")
    print("\n  grid (secondary). New tokens unless marked OLD = coin had spot history "
          ">60 days before the perp")
    print(HDR)
    for kind in ("new", "old"):
        for ed in (1, 7):
            for hold in (14, 30, 90):
                for stop in (None, 1.0, 0.5):
                    tr = listing_trades(idx, ed, hold, stop, kind)
                    lab = (f"{'OLD ' if kind == 'old' else ''}d{ed} hold {hold}d stop "
                           f"{'none' if stop is None else f'+{stop*100:.0f}%'}")
                    print(row(summary(tr, lab)))

    print("\n" + "=" * 110)
    print("IDEA 2 - PUMP FADE: short an established perp (>=60d old, >=$2M/day) after a "
          "violent rise")
    print("=" * 110)
    print(HDR)
    best = None
    for look, th in ((3, 0.3), (3, 0.5), (7, 0.5), (7, 1.0)):
        for hold in (3, 7, 14):
            for stop in (None, 0.5):
                tr = pump_trades(idx, bear, look, th, hold, stop)
                d = summary(tr, f"+{th*100:.0f}% in {look}d, hold {hold}d, stop "
                                f"{'none' if stop is None else '+50%'}")
                print(row(d))
                if d and (best is None or d["t"] > best[0]):
                    best = (d["t"], look, th, hold, stop)
    if best:
        _, look, th, hold, stop = best
        tr = pump_trades(idx, bear, look, th, hold, stop)
        split_report(tr, idx, bear, f"best-t cell by split (+{th*100:.0f}% in {look}d, "
                                    f"hold {hold}d) - selected on the full sample, so "
                                    f"the holdout row is NOT out of sample")

    print("\n" + "=" * 110)
    print("IDEA 3 - WEAKEST COINS: short the worst 30-day performers each week")
    print("=" * 110)
    C, Q, first = weekly_panel()
    for look in (30, 90):
        w = weakest(idx, bear, C, Q, first, look=look)
        w["spread"] = w["bottom"] - w["all"]
        print(f"\n  lookback {look}d, weekly, equal weight. mean weekly return of the SHORT, "
              f"% of notional")
        print(f"  {'':<22}{'weeks':>6}{'short bottom':>14}{'short all':>11}"
              f"{'short top':>11}{'bottom-all':>12}{'t':>7}")
        for lab, m in (("ALL weeks", w.index == w.index),
                       ("BTC bear weeks", w.bear), ("BTC bull weeks", ~w.bear)):
            x = w[m]
            sp = x["spread"].dropna()
            t = sp.mean() / (sp.std(ddof=1) / np.sqrt(len(sp))) if len(sp) > 2 else np.nan
            print(f"  {lab:<22}{len(x):>6}{x['bottom'].mean()*100:>+13.2f}%"
                  f"{x['all'].mean()*100:>+10.2f}%{x['top'].mean()*100:>+10.2f}%"
                  f"{sp.mean()*100:>+11.2f}%{t:>+7.2f}")
        for y in sorted(w.t0.dt.year.unique()):
            x = w[w.t0.dt.year == y]
            print(f"    {y:<20}{len(x):>6}{x['bottom'].mean()*100:>+13.2f}%"
                  f"{x['all'].mean()*100:>+10.2f}%{x['top'].mean()*100:>+10.2f}%"
                  f"{(x['bottom']-x['all']).mean()*100:>+11.2f}%")


if __name__ == "__main__":
    main()
