"""SHORTING BINANCE DELISTINGS AFTER THE ANNOUNCEMENT - event study with a placebo.

WHY
    A delisting is a forced exit on a calendar: holders must sell or withdraw before a
    published date, index products drop the coin, market makers leave. That is the same
    non-informational class as the one real event edge found here (an old coin getting its
    first perp, doc 02: +10%/trade with a placebo pass). listing_events.py showed LISTINGS
    are priced inside a minute. Nobody here has measured whether the drift AFTER a delisting
    announcement is left for a poller that acts within the hour.

EVENTS
    Binance CMS catalog 161 (Delisting), 435 articles, fetched 2026-09-23:
      SPOT   "Binance Will Delist A, B, C on YYYY-MM-DD"            - the token leaves Binance
      PERP   "Binance Futures Will Delist USDⓈ-M XUSDT ... Perpetual" - only the perp closes
    Articles naming no tickers ("Multiple ... Contracts") and Margin/Loan notices are skipped.

TRADE
    Short the Binance perp at the first hourly open >= announcement + 10 minutes (a poller's
    realistic reaction), hold 24h / 72h / 7d, exit early at the perp's last bar if it is
    delisted first. Stop at +50% against the short, checked on hourly highs (pessimistic).
    12bp plus every funding settlement held (a short receives positive, pays negative).
    Costs are also shown at 50bp: these are dying coins and the spread widens.

CONTROL
    The same coin, same holds, entered at 5 random hours 30-180 days BEFORE its announcement.
    Dying coins fall anyway; only the excess over that placebo is an event effect.
    Standard errors cluster by ANNOUNCEMENT (one notice often names 5 coins at once).

REGISTERED PREDICTIONS (before running)
    SPOT: most of the drop is gone before a +10-70 minute entry (median -10% to -20% already);
    from entry the short earns +3-6% gross over 72h, funding takes 1-3%, and the excess over
    placebo is +1-3% with |t| < 2 after clustering. PERP-only notices: nothing.
    Expected verdict: dead or too small, like listings.

    python -m backtest.delist_events
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ROOT = Path(__file__).resolve().parents[1]
PERPS = ROOT / "strategy_analysis" / "data" / "perps"
CMS = ROOT / "strategy_analysis" / "data" / "listings" / "binance_cms161.json"
HOLDS = (24, 72, 168)
STOP = 0.50
HOUR = pd.Timedelta(hours=1)


def events():
    arts = json.load(open(CMS, encoding="utf-8"))
    ev = []
    for a in arts:
        t = pd.to_datetime(a["t"], unit="ms")
        title = a["title"]
        m = re.match(r"Binance Will Delist (.+?) on (\d{4}-\d{2}-\d{2})", title)
        if m:
            toks = re.split(r",\s*|\s+and\s+|\s*&\s*", m.group(1))
            ev += [dict(kind="SPOT", t=t, coin=x.strip(), aid=a["t"]) for x in toks if x.strip()]
            continue
        if title.startswith("Binance Futures Will Delist") and "Multiple" not in title \
                and "Leverage" not in title:
            for s in re.findall(r"\b([0-9A-Z]{2,20})USDT\b", title):
                ev.append(dict(kind="PERP", t=t, coin=s, aid=a["t"]))
            m2 = re.search(r"Delist ([A-Z0-9 ,and]+?) USDT-Margined", title)
            if m2:
                for s in re.split(r",\s*|\s+and\s+", m2.group(1)):
                    ev.append(dict(kind="PERP", t=t, coin=s.strip(), aid=a["t"]))
    E = pd.DataFrame(ev).drop_duplicates(["kind", "coin", "aid"])
    return E.sort_values("t").reset_index(drop=True)


_P: dict = {}


def perp(coin):
    for sym in (f"{coin}USDT", f"1000{coin}USDT"):
        if sym in _P:
            return _P[sym]
        f = PERPS / f"{sym}_1h.csv.gz"
        if f.exists():
            h = pd.read_csv(f, usecols=["time", "open", "high", "close"])
            h["time"] = pd.to_datetime(h["time"]).astype("datetime64[ns]")
            fu = pd.read_csv(PERPS / f"{sym}_funding.csv.gz")
            fu["time"] = pd.to_datetime(fu["time"]).dt.floor("h").astype("datetime64[ns]")
            _P[sym] = (sym, h.set_index("time"), fu.set_index("time")["rate"].sort_index())
            return _P[sym]
    return None


def short_trade(h, fu, t_entry, hold):
    """Short from the open at t_entry for `hold` hours (or to the last bar). Returns
    (price R, funding R) as fractions of entry notional, or None."""
    if t_entry not in h.index:
        return None
    seg = h.loc[t_entry: t_entry + (hold - 1) * HOUR]
    if len(seg) < 2:
        return None
    e = float(seg["open"].iloc[0])
    if not e or not np.isfinite(e):
        return None
    hit = np.nonzero(seg["high"].to_numpy(float) >= e * (1 + STOP))[0]
    if len(hit):
        t_exit = seg.index[hit[0]] + HOUR; px = -STOP
    else:
        t_exit = seg.index[-1] + HOUR
        px = -(float(seg["close"].iloc[-1]) / e - 1)
    f = fu[(fu.index > t_entry) & (fu.index <= t_exit)].sum()     # short receives +rate
    return px, float(f)


def cluster_t(x, groups, reps=3000, seed=5):
    x = np.asarray(x, float); g = np.asarray(groups)
    ug, inv = np.unique(g, return_inverse=True)
    s = np.bincount(inv, weights=x); c = np.bincount(inv)
    rng = np.random.default_rng(seed)
    pick = rng.integers(0, len(ug), size=(reps, len(ug)))
    bs = s[pick].sum(1) / c[pick].sum(1)
    return float(x.mean() / bs.std()) if bs.std() > 0 else np.nan


def main():
    E = events()
    rng = np.random.default_rng(9)
    rows = []
    for ev in E.itertuples():
        p = perp(ev.coin)
        if p is None:
            continue
        sym, h, fu = p
        t_ann = ev.t
        t_entry = (t_ann + pd.Timedelta(minutes=10)).ceil("h")
        if t_entry not in h.index or (t_ann.floor("h") - HOUR) not in h.index:
            continue
        pre = float(h.loc[t_entry, "open"]) / float(h.loc[t_ann.floor("h"), "open"]) - 1
        rec = dict(kind=ev.kind, coin=ev.coin, sym=sym, t=t_ann, aid=ev.aid, pre=pre)
        for H in HOLDS:
            r = short_trade(h, fu, t_entry, H)
            if r is None:
                continue
            rec[f"px{H}"], rec[f"f{H}"] = r
            pl = []
            for _ in range(5):
                tp = (t_ann - pd.Timedelta(days=int(rng.integers(30, 181)))).floor("h")
                rp = short_trade(h, fu, tp, H)
                if rp is not None:
                    pl.append(rp[0] + rp[1])
            rec[f"pl{H}"] = np.mean(pl) if pl else np.nan
        rows.append(rec)
    R = pd.DataFrame(rows)
    cut = R.t.quantile(0.6)
    print(f"{len(E)} ticker-events parsed; {len(R)} with a Binance perp trading at the notice | "
          f"tune < {cut:%Y-%m-%d} <= holdout\n")
    for kind in ("SPOT", "PERP"):
        K = R[R.kind == kind]
        if len(K) < 10:
            continue
        print(f"{kind} notices: {len(K)} coin-events in {K.aid.nunique()} announcements")
        print(f"  move from the notice hour to entry (already priced): median {K.pre.median()*100:+.1f}%"
              f"  mean {K.pre.mean()*100:+.1f}%")
        print(f"  {'hold':<6}{'n':>5}{'price':>9}{'funding':>9}{'net 12bp':>10}{'net 50bp':>10}"
              f"{'placebo':>9}{'excess':>9}{'t(clust)':>9}{'TUNE ex':>9}{'HOLD ex':>9}{'win':>6}")
        for H in HOLDS:
            k = K.dropna(subset=[f"px{H}"])
            net = k[f"px{H}"] + k[f"f{H}"] - 12 / 1e4
            ex = (net - k[f"pl{H}"]).dropna()
            kk = k.loc[ex.index]
            tu = kk.t < cut
            print(f"  {H:>4}h{len(k):>5}{k[f'px{H}'].mean()*100:>+8.1f}%{k[f'f{H}'].mean()*100:>+8.1f}%"
                  f"{net.mean()*100:>+9.1f}%{(net - 38/1e4).mean()*100:>+9.1f}%"
                  f"{k[f'pl{H}'].mean()*100:>+8.1f}%{ex.mean()*100:>+8.1f}%"
                  f"{cluster_t(ex, kk.aid):>+9.2f}{ex[tu].mean()*100:>+8.1f}%{ex[~tu].mean()*100:>+8.1f}%"
                  f"{(net > 0).mean()*100:>5.0f}%")
        print("  72h net by year: " + "  ".join(
            f"{y}: {v.mean()*100:+.1f}% (n{len(v)})" for y, v in
            (K[f'px72'] + K[f'f72'] - 12 / 1e4).groupby(K.t.dt.year)))
        print()


if __name__ == "__main__":
    main()
