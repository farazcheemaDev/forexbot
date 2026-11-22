"""THE PERP'S PREMIUM TO SPOT: when a coin's perpetual trades far below (or above) its spot index, does the gap close in a way a trader can be paid for? (2026-11-12)

THE USER: "find me a new strategy" -> "Yes, run it". The one mechanism with free history that this repo never tested: Binance's hourly PREMIUM
INDEX (the perp's price relative to the spot index, from which funding is computed). In a crash, liquidations hit the perps first and the perp can
trade below spot for hours; arbitrage pulls it back. Funding carry (`carry_revisit.py`, a candidate) and crowd positioning (a lead) were tested; the
live gap itself was not.

DATA  premium: data.binance.vision futures/um/monthly/premiumIndexKlines/<SYM>/1h (free, dead coins included), cached in
      strategy_analysis/data/premium/<SYM>.parquet; downloaded for every PIT top-40 coin-month (pair_lab.universe) and the month before it.
      Prices: pair_lab.hourly_all() (the perp's own hourly bars, the same loader as sweep_confluence / oi_flush_pit). Funding:
      capitulation_wide.funding_cum. 2020-01 .. 2026-09.

THE RULE (registered; nothing below the line is tuned)
  signal   at the close of hour i, the premium index's close for hour i <= -0.5% (the perp 0.5% under spot) -> LONG; >= +0.5% -> SHORT
           (the mirror). The coin must be PIT-eligible that month. One event per coin per side per 24 hours.
  entry    the perp's close one hour LATER (hour i+1), so the signal bar's own bounce cannot pay the trade.
  exit     PRIMARY: at the first hourly close where the premium is back inside +-0.1%, or after 24 hours, at the perp's close.
           SECONDARY: a fixed 24-hour hold.
  cost     12bp round trip + the coin's real funding (funding_cum).
  control  the capitulation confound: a perp that crashed is often below spot, and crashed coins bounce (capit2). CONTROL = the same coin, at an
           hour with the premium inside +-0.1%, whose 24h return lies in the same fifth of all events' 24h returns (side-specific), sampled
           one per coin per day, traded with the SECONDARY exit. Excess = event (secondary exit) minus the control in the same fifth, averaged.
  split    tune = the first 60% of events by time, holdout the rest. t by entry DAY (errors clustered by day: a crash day is one bet).
THE BAR  a side passes if its PRIMARY net is > 0 with day-clustered t >= 2 on BOTH halves, its excess over the drop-matched control is > 0 on both
         halves, and the holdout has >= 30 trades on >= 15 days. Fewer = 'cannot tell' (the minimum detectable edge is printed).

REGISTERED BEFORE ANY RESULT (2026-11-12; the threshold 0.5% was chosen from the SOL 2022-11 file's distribution only - median -0.09%, 25th
-0.17% - i.e. from how often the signal fires, not from any outcome)
  Q1  LONG: 300-3,000 events, on fewer than 400 distinct days (crash clusters).                                          (65%)
  Q2  LONG primary net is positive on the tune half, but the excess over the drop-matched control is not positive at t >= 2 on both halves.  (70%)
  Q3  SHORT loses on at least one half (strong up-moves continue; squeezes).                                               (65%)
  Q4  The premium is back inside +-0.1% within 4 hours for the median LONG event.                                          (60%)
  Q5  Neither side passes the bar.                                                                                          (90%)

RESULT (2026-11-12, logs/premium_dislocation.txt) - NO PASS on either side. Q2-Q5 right, Q1 wrong (879 days, not < 400).
  365 coins, 3,055 events. LONG (perp 0.5%+ under spot): tune +0.74% a trade (t +2.18), holdout +0.36% (t +0.40); the gap closes within 4h for 59%;
  excess over drop-matched calm hours +0.82% / +1.49% (24h hold, not significant: t 1.4 / 1.2); without its 5 best days -0.06%; 2026 -0.47%.
  SHORT (perp 0.5%+ over spot): -0.09% / +0.14% a trade, excess -0.48% / -0.90%: dead. The long side is a weak lead in the capitulation family, too
  small and too concentrated to trade. tests/test_premium_dislocation.py 6; planted bugs 11 of 11 caught, the do-nothing control survived.

    python -m backtest.premium_dislocation            (downloads on the first run, ~3,500 small files)
"""
from __future__ import annotations

import io
import sys
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

PREM = ROOT / "strategy_analysis" / "data" / "premium"
LOG = ROOT / "logs" / "premium_dislocation.txt"
BASE = "https://data.binance.vision/data/futures/um/monthly/premiumIndexKlines"
H = np.timedelta64(1, "h")
TH, CLOSE_BAND, MAX_H, COOL = 0.005, 0.001, 24, 24
FEE = 0.0012


# ------------------------------------------------------------------ data

def months_needed(el: dict) -> dict:
    out = {}
    for s, ms in el.items():
        if not ms:
            continue
        need = set(ms)
        for m in ms:
            p = pd.Period(m, "M") - 1
            need.add(str(p))
        out[s] = sorted(need)
    return out


def one_month(sym: str, m: str):
    u = f"{BASE}/{sym}/1h/{sym}-1h-{m}.zip"
    for a in range(3):
        try:
            b = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "research"}), timeout=40).read()
            z = zipfile.ZipFile(io.BytesIO(b))
            d = pd.read_csv(z.open(z.namelist()[0]), header=None, usecols=[0, 4])
            d.columns = ["t", "prem"]
            d["t"] = pd.to_numeric(d.t, errors="coerce")
            d["prem"] = pd.to_numeric(d.prem, errors="coerce")
            return d.dropna()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
        except Exception:  # noqa: BLE001 - retried, then reported as missing
            pass
    return None


def fetch(el: dict) -> dict:
    PREM.mkdir(parents=True, exist_ok=True)
    need = months_needed(el)
    out, todo = {}, []
    for s, ms in need.items():
        f = PREM / f"{s}.parquet"
        if f.exists():
            out[s] = pd.read_parquet(f)
        else:
            todo.append((s, ms))
    print(f"premium: {len(out)} cached, {len(todo)} coins to fetch ({sum(len(m) for _, m in todo)} files)", flush=True)
    with ThreadPoolExecutor(16) as ex:
        for k, (s, ms) in enumerate(todo):
            parts = [p for p in ex.map(lambda m: one_month(s, m), ms) if p is not None and len(p)]
            d = (pd.concat(parts).drop_duplicates("t").sort_values("t").reset_index(drop=True) if parts
                 else pd.DataFrame({"t": pd.Series(dtype="int64"), "prem": pd.Series(dtype=float)}))
            d.to_parquet(PREM / f"{s}.parquet")
            out[s] = d
            if k % 50 == 0:
                print(f"  {k}/{len(todo)} {s} {len(d)} rows", flush=True)
    return out


# ------------------------------------------------------------------ events

def coin_frame(hh: pd.DataFrame, pr: pd.DataFrame) -> pd.DataFrame:
    """Perp hourly bars with the premium of the SAME hour (premium kline open time = bar open time)."""
    t = hh.time.to_numpy("datetime64[ns]")
    p = pd.Series(pr.prem.to_numpy(float), index=pd.to_datetime(pr.t, unit="ms").to_numpy("datetime64[ns]"))
    p = p[~p.index.duplicated()]
    return pd.DataFrame({"t": t, "c": hh.close.to_numpy(float), "prem": p.reindex(t).to_numpy()})


def trades(sym: str, X: pd.DataFrame, elig: np.ndarray, fc: np.ndarray, side: int, events: bool = True, rng=None, ret_bins=None):
    """events=True: the registered events. events=False: control hours (premium inside the band), one a coin a day, 24h hold."""
    t, c, pm = X.t.to_numpy(), X.c.to_numpy(), X.prem.to_numpy()
    n, rows, last = len(c), [], -10 ** 9
    day = t.astype("datetime64[D]")
    used_days = set()
    for i in range(24, n - MAX_H - 2):
        if not elig[i] or not np.isfinite(pm[i]) or not np.isfinite(c[i + 1]) or not np.isfinite(c[i - 24]):
            continue
        if t[i] - t[i - 24] != 24 * H or t[i + 1] - t[i] != H:
            continue
        if events:
            hit = pm[i] <= -TH if side == 1 else pm[i] >= TH
            if not hit or i - last < COOL:
                continue
        else:
            if abs(pm[i]) > CLOSE_BAND or day[i] in used_days:
                continue
            if rng.random() > 0.08:                                    # thin the control hours (about 2 a coin-day on offer)
                continue
            used_days.add(day[i])
        e = i + 1
        if t[e + MAX_H] - t[e] != MAX_H * H or not np.isfinite(c[e + MAX_H]):
            continue
        last = i
        x1, why = e + MAX_H, "time"
        if events:
            for j in range(e + 1, e + MAX_H + 1):
                if np.isfinite(pm[j]) and abs(pm[j]) <= CLOSE_BAND and np.isfinite(c[j]):
                    x1, why = j, "closed"
                    break
        x2 = e + MAX_H

        def net(x):
            g = side * (c[x] / c[e] - 1)
            f = side * (fc[x] - fc[e + 1]) / c[e]
            return g - FEE - f
        rows.append(dict(sym=sym, side=side, t=t[i], day=day[i], prem=pm[i], ret24=c[i] / c[i - 24] - 1, net1=net(x1), net2=net(x2),
                         hours1=x1 - e, why=why))
    return rows


def clustered(r, day):
    r = np.asarray(r, float)
    n = len(r)
    if n < 3:
        return (float(r.mean()) if n else np.nan), np.nan, n, len(set(day))
    m = r.mean()
    s = pd.Series(r - m).groupby(np.asarray(day)).sum().to_numpy()
    g = len(s)
    se = np.sqrt((s ** 2).sum() * g / (g - 1)) / n if g > 2 else np.nan
    return float(m), (float(m / se) if se and se > 0 else np.nan), n, g


def fmt(lab, x, col):
    m, t, n, g = clustered(x[col], x["day"])
    if not n:
        return f"   {lab:<30} n    0"
    return (f"   {lab:<30} n {n:>5} days {g:>4}  net {m * 100:+6.2f}%  t(day) {t:+5.2f}  won {(x[col] > 0).mean() * 100:3.0f}%  "
            f"worst {x[col].min() * 100:+6.1f}%")


def main():
    from backtest import pair_lab as pl
    from backtest.capitulation_wide import funding_cum
    el = pl.universe()
    P = fetch(el)
    Hh = pl.hourly_all()
    rng = np.random.default_rng(0)
    ev, ctl = [], []
    for s, hh in Hh.items():
        if not el.get(s) or s not in P or not len(P[s]):
            continue
        X = coin_frame(hh, P[s])
        ym = pd.DatetimeIndex(X.t).strftime("%Y-%m").to_numpy()
        elig = np.array([m in el[s] for m in ym])
        fc = funding_cum(s, X.t.to_numpy("datetime64[ns]"), hh)
        for side in (1, -1):
            ev += trades(s, X, elig, fc, side)
            ctl += trades(s, X, elig, fc, side, events=False, rng=rng)
    E, C = pd.DataFrame(ev).sort_values("t").reset_index(drop=True), pd.DataFrame(ctl)
    L = [f"backtest/premium_dislocation.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; PIT top-40 incl. dead coins, premium threshold "
         f"+-{TH * 100:.1f}%, exit at +-{CLOSE_BAND * 100:.1f}% or {MAX_H}h, 12bp + funding",
         f"   premium history found for {sum(1 for s in P if len(P[s]))} coins; events {len(E)} (long {int((E.side == 1).sum())}, short "
         f"{int((E.side == -1).sum())}); control hours {len(C)}"]
    res = {}
    for side, nm in ((1, "LONG (perp under spot)"), (-1, "SHORT (perp over spot)")):
        e = E[E.side == side].copy()
        if len(e) < 10:
            L += ["", f"{nm}: {len(e)} events - nothing to test"]
            continue
        cut = e.t.iloc[int(len(e) * 0.6)]
        e["half"] = np.where(e.t < cut, "tune", "hold")
        c = C[C.side == side].copy()
        c["half"] = np.where(c.t < cut, "tune", "hold")
        q = np.quantile(e.ret24, [0.2, 0.4, 0.6, 0.8])
        e["b"], c["b"] = np.searchsorted(q, e.ret24), np.searchsorted(q, c.ret24)
        L += ["", f"{nm}: {len(e)} events on {e.day.nunique()} days, holdout from {pd.Timestamp(cut):%Y-%m-%d}; median premium {e.prem.median() * 100:+.2f}%, "
              f"median 24h move before {e.ret24.median() * 100:+.1f}%; premium back inside +-0.1% within 4h: "
              f"{((e.why == 'closed') & (e.hours1 <= 4)).mean() * 100:.0f}% (median {e.hours1.median():.0f}h to exit)"]
        out = {}
        for half in ("tune", "hold"):
            x, y = e[e.half == half], c[c.half == half]
            L.append(fmt(f"{half} PRIMARY (gap closes / 24h)", x, "net1"))
            L.append(fmt(f"{half} SECONDARY (24h)", x, "net2"))
            ex = []
            for b in range(5):
                xb, yb = x[x.b == b], y[y.b == b]
                if len(xb) >= 5 and len(yb) >= 20:
                    ex.append((len(xb), xb.net2.mean() - yb.net2.mean()))
            exc = sum(n * d for n, d in ex) / max(sum(n for n, _ in ex), 1) if ex else np.nan
            L.append(f"   {half} excess over the drop-matched control (24h hold, weighted by fifth): {exc * 100:+.2f}% "
                     f"({len(ex)} fifths with data; control n {len(y)})")
            m, t, n, g = clustered(x.net1, x.day)
            out[half] = dict(m=m, t=t, n=n, g=g, exc=exc, se=(abs(m / t) if t and np.isfinite(t) and t != 0 else np.nan))
        L.append("   PRIMARY by year: " + "  ".join(f"{y} {len(g)} {g.net1.mean() * 100:+.2f}%" for y, g in e.groupby(pd.DatetimeIndex(e.t).year)))
        top = e.groupby("day").net1.sum().sort_values(ascending=False)
        L.append(f"   PRIMARY without its 5 best days: {e[~e.day.isin(top.index[:5])].net1.mean() * 100:+.2f}% (all {e.net1.mean() * 100:+.2f}%)")
        L.append(f"   without premiums beyond +-5% (index glitches?): {e[e.prem.abs() <= 0.05].net1.mean() * 100:+.2f}% (n {int((e.prem.abs() <= 0.05).sum())})")
        tu, ho = out["tune"], out["hold"]
        ok = tu["m"] > 0 and ho["m"] > 0 and tu["t"] >= 2 and ho["t"] >= 2 and tu["exc"] > 0 and ho["exc"] > 0 and ho["n"] >= 30 and ho["g"] >= 15
        verdict = "PASS" if ok else ("cannot tell" if (ho["n"] < 30 or ho["g"] < 15) else "no pass")
        L.append(f"   VERDICT: {verdict}   (minimum detectable edge on the holdout, 2.8 x se: {2.8 * ho['se'] * 100:.2f}%)")
        res[side] = dict(n=len(e), days=e.day.nunique(), tune=tu, hold=ho, verdict=verdict,
                         closed4=((e.why == "closed") & (e.hours1 <= 4)).mean())
    lo, sh = res.get(1), res.get(-1)
    L += ["", "REGISTERED PREDICTIONS"]
    if lo:
        L.append(f"  Q1 LONG 300-3,000 events on < 400 days ({lo['n']}, {lo['days']}) -> {'RIGHT' if 300 <= lo['n'] <= 3000 and lo['days'] < 400 else 'WRONG'}")
        q2 = lo["tune"]["m"] > 0 and not (lo["tune"]["exc"] > 0 and lo["hold"]["exc"] > 0 and lo["tune"]["t"] >= 2 and lo["hold"]["t"] >= 2)
        L.append(f"  Q2 LONG tune net > 0 ({lo['tune']['m'] * 100:+.2f}%) and no clean excess on both halves ({lo['tune']['exc'] * 100:+.2f}% / "
                 f"{lo['hold']['exc'] * 100:+.2f}%) -> {'RIGHT' if q2 else 'WRONG'}")
        L.append(f"  Q4 LONG gap closed within 4h for the median event ({lo['closed4'] * 100:.0f}% of events) -> {'RIGHT' if lo['closed4'] >= 0.5 else 'WRONG'}")
    if sh:
        L.append(f"  Q3 SHORT loses on at least one half ({sh['tune']['m'] * 100:+.2f}% / {sh['hold']['m'] * 100:+.2f}%) -> "
                 f"{'RIGHT' if min(sh['tune']['m'], sh['hold']['m']) < 0 else 'WRONG'}")
    L.append(f"  Q5 neither side passes -> {'RIGHT' if all(r['verdict'] != 'PASS' for r in res.values()) else 'WRONG'}")
    txt = "\n".join(L)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
