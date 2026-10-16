"""SENTIMENT ENGINE, phase C: the IMPACT TABLE - what each kind of news did to the price afterwards (2026-10-16, docs/25)

For every coin-linked event in strategy_analysis/data/news/events.parquet (news/enrich.py), on Binance perp 1h bars
(strategy_analysis/data/perps, dead coins in; the archive ends 2026-09):
    t0       the event's first timestamp
    entry    the OPEN of the first full hour after t0 - the earliest a bot reading hourly bars could act (0-60 min late;
             phase C2 measures minutes with 1-minute bars)
    already  the coin's move vs BTC from the open of t0's hour to the entry: what was gone before we could act
    after h  the coin's move vs BTC (abnormal return) from the entry to +1h / 4h / 24h / 72h / 7d
A coin without a perp bar at the entry is skipped (a brand-new token whose perp did not exist yet). An event naming
several coins counts ONCE in the statistics (its coins averaged), so one 8-coin notice is not 8 observations.
SPLIT  by time: the first 60% of events tune, the last 40% holdout. Market-wide categories are measured on BTC itself
(its raw return, not vs itself).
REPORTED per event type: events, the mean and median move at each horizon (bp), the share in the mean's direction, t,
tune / holdout means; the round-trip cost to beat is ~12bp + funding.

REGISTERED BEFORE ANY RESULT WAS SEEN (2026-10-16)
    P1 monitoring_tag: the tagged coins keep falling: <= -300bp vs BTC at +72h, both halves.
    P2 delist (a token delisting announced): <= -500bp at +72h, both halves.
    P3 list_futures (a new perp launched): new perps drift down: <= -500bp over 7 days, both halves.
    P4 seed_tag / launchpool: down over 7 days, <= -500bp.
    P5 list_spot / adds_products: most of the move is ALREADY gone at the entry (|already| > |after 24h|).
    P6 market-wide types (etf, regulation, macro, treasury_buy, hack without a coin) on BTC: |mean| < 30bp at +1h..+24h.
    USABLE (a candidate for the bot): |mean| >= 24bp (2x cost) at some horizon, the same sign on both halves, t >= 2.

RESULT (2026-10-16, logs/news_impact.txt; full history, 150,789 events) - moves are EXCESS over the same coin's
    normal drift (control()). Market-wide types (ETF, regulation, macro, treasury buys, 'other'): ~0 at every horizon
    (P6 right). Coin events that hold on BOTH halves (tune / holdout, bp): exchange spot listings -307 / -312 over 7 days
    (n 518); Binance adds a token to Margin / Futures / Earn -237 / -1,028 at 72h (n 160); monitoring tag -868 / -183
    (n 28); new trading pairs -112 / -1,456 (n 182) - "sell the news", much stronger in 2025-26. Launchpool FLIPS (+445 /
    -1,150 over 7d) and delistings are no signal (P2 wrong). Without the control, every category inherited the altcoins'
    drift against BTC ('other' -36bp over 7 days at t -8.3 on 88k events) - fixed before any conclusion.

    python -m news.impact
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest.capitulation_wide import hourly  # noqa: E402

EV = ROOT / "strategy_analysis" / "data" / "news" / "events.parquet"
OUT = ROOT / "strategy_analysis" / "data" / "news" / "impact_obs.parquet"
LOG = ROOT / "logs" / "news_impact.txt"           # moves are EXCESS over the same coin's normal drift (control())
H = {"1h": 1, "4h": 4, "24h": 24, "72h": 72, "7d": 168}
MARKET = {"etf", "regulation", "macro", "treasury_buy", "hack", "partnership", "other", "unlock", "whale"}
_C: dict = {}


def bars(sym):
    if sym not in _C:
        h = hourly(sym)
        _C[sym] = None if h is None else (h.time.to_numpy("datetime64[ns]").astype("int64"), h.open.to_numpy(float),
                                          h.close.to_numpy(float))
    return _C[sym]


def px_at(b, t_ns, kind="open"):
    """The bar opening exactly at t_ns (open) or the last bar closing by t_ns (close); None if missing."""
    tt, o, c = b
    i = np.searchsorted(tt, t_ns)
    if kind == "open":
        return o[i] if i < len(tt) and tt[i] == t_ns else None
    i = np.searchsorted(tt, t_ns - 3600 * 10**9, "right") - 1
    return c[i] if 0 <= i < len(tt) and t_ns - tt[i] <= 2 * 3600 * 10**9 else None


def ret(b, a_ns, z_ns):
    p0, p1 = px_at(b, a_ns, "open"), px_at(b, z_ns, "close")
    return None if p0 is None or p1 is None or p0 <= 0 else p1 / p0 - 1


def btc_drift(btc):
    """BTC's average return over each horizon across every hour of its history: market-wide events are measured as
    BTC's move MINUS this, or every 'market' category inherits BTC's 2020-26 rise (the first trial run did: 'other'
    read +114bp over 7 days at t +5.1)."""
    tt, o, c = btc
    out = {}
    for k, hh in H.items():
        a = o[:-hh] if hh < len(o) else o[:0]
        z = c[hh - 1:-1] if hh < len(c) else c[:0]
        out[k] = float(np.nanmean(z / a - 1)) if len(a) else 0.0
    return out


def h_returns(b, starts, hh):
    """Vectorised: the bar opening at each start (exact hour) -> the close hh hours later; NaN where missing."""
    tt, o, c = b
    i = np.searchsorted(tt, starts)
    ok = (i < len(tt))
    i = np.minimum(i, len(tt) - 1)
    ok &= tt[i] == starts
    j = np.searchsorted(tt, starts + (hh - 1) * 3600 * 10**9)
    ok &= j < len(tt)
    j = np.minimum(j, len(tt) - 1)
    ok &= tt[j] == starts + (hh - 1) * 3600 * 10**9
    out = np.where(ok, c[j] / np.where(o[i] > 0, o[i], np.nan) - 1, np.nan)
    return out


def control(b, btc, entry, hh, vs_btc):
    """The SAME coin's normal move over the same horizon: the average of its hh-hour move (vs BTC) starting every 12 h
    in [entry - 60 d, entry - 7 d] and [entry + 7 d + hh, entry + 60 d]. Without it every category inherits the
    altcoins' drift against BTC (the full-history run read 'other' at -36bp over 7 days, t -8.3, on 88k events)."""
    step, day = 12 * 3600 * 10**9, 86400 * 10**9
    s = np.r_[np.arange(entry - 60 * day, entry - 7 * day, step),
              np.arange(entry + 7 * day + hh * 3600 * 10**9, entry + 60 * day, step)].astype("int64")
    s -= s % (3600 * 10**9)
    rc = h_returns(b, s, hh)
    rb = h_returns(btc, s, hh) if vs_btc else np.zeros(len(s))
    v = rc - rb
    return float(np.nanmean(v)) if np.isfinite(v).sum() >= 20 else None


def observe(E):
    btc = bars("BTCUSDT")
    drift = btc_drift(btc)
    rows = []
    for e in E.itertuples():
        t0 = pd.Timestamp(e.t)
        h0 = t0.floor("h").value
        entry = (t0.floor("h") + pd.Timedelta(hours=1)).value
        coins = [c for c in e.coins.split(",") if c] or (["BTCUSDT"] if e.etype in MARKET else [])
        for c in coins:
            b = bars(c)
            if b is None or px_at(b, entry) is None:
                continue
            vs_btc = c != "BTCUSDT"
            r = {}
            rb = ret(btc, h0, entry) if vs_btc else 0.0
            ra = ret(b, h0, entry)
            r["already"] = None if ra is None or rb is None else ra - rb
            for k, hh in H.items():
                z = entry + hh * 3600 * 10**9
                rc = ret(b, entry, z)
                rbb = ret(btc, entry, z) if vs_btc else 0.0
                raw = None if rc is None or rbb is None else rc - rbb
                ctl = control(b, btc, entry, hh, vs_btc) if raw is not None else None
                r[k + "_raw"] = raw
                r[k] = None if raw is None or ctl is None else raw - ctl          # EXCESS over the coin's own normal
            rows.append(dict(eid=e.Index, t=t0, etype=e.etype, channel=e.channel, coin=c, market=not vs_btc, **r))
    return pd.DataFrame(rows)


def table(O):
    # one observation per EVENT: its coins averaged
    cols = ["already"] + list(H)
    ev = O.groupby(["eid", "etype", "t"])[cols].mean().reset_index().sort_values("t", kind="stable")
    cut = ev.t.iloc[int(len(ev) * 0.6)] if len(ev) else None
    lines = [f"  {'event type':<15}{'n':>5}  " + "".join(f"{k:>16}" for k in cols),
             f"  {'':<15}{'':>5}  " + "".join(f"{'mean/med/t':>16}" for _ in cols)]
    res = {}
    for et, g in ev.groupby("etype"):
        if len(g) < 8:
            continue
        cells = []
        for k in cols:
            v = g[k].dropna() * 1e4
            if len(v) < 8:
                cells.append(f"{'-':>16}")
                continue
            t = v.mean() / (v.std(ddof=1) / np.sqrt(len(v))) if v.std() > 0 else 0.0
            tu, ho = (g[g.t < cut][k].dropna() * 1e4), (g[g.t >= cut][k].dropna() * 1e4)
            res[(et, k)] = dict(n=len(v), mean=v.mean(), med=v.median(), t=t, tune=tu.mean() if len(tu) else np.nan,
                                hold=ho.mean() if len(ho) else np.nan, hit=(np.sign(v) == np.sign(v.mean())).mean())
            cells.append(f"{v.mean():>+7.0f}/{v.median():>+5.0f}/{t:>+3.1f}")
        lines.append(f"  {et:<15}{len(g):>5}  " + "".join(cells))
    return lines, res, ev


def main():
    E = pd.read_parquet(EV)
    O = observe(E)
    O.to_parquet(OUT)
    lines = [f"news/impact.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; {len(E):,} events, {len(O):,} coin observations "
             f"({O.coin.nunique()} coins); move vs BTC in bp from the next hour's open (market-wide types: BTC's own move)", ""]
    tl, res, ev = table(O)
    lines += tl
    lines += ["", "  TUNE / HOLDOUT means (bp) and the share of events moving the mean's way, where n >= 8:"]
    for (et, k), r in sorted(res.items()):
        if k in ("24h", "72h", "7d"):
            lines.append(f"    {et:<15}{k:>4}: tune {r['tune']:>+6.0f}  holdout {r['hold']:>+6.0f}  hit {r['hit'] * 100:3.0f}%  (n {r['n']})")
    usable = sorted((et, k, round(r["mean"]), round(r["t"], 1)) for (et, k), r in res.items()
                    if k != "already" and abs(r["mean"]) >= 24 and abs(r["t"]) >= 2 and np.sign(r["tune"]) == np.sign(r["hold"]) == np.sign(r["mean"]))

    def g(et, k, f="mean"):
        return res.get((et, k), {}).get(f, np.nan)
    lines += ["", "REGISTERED PREDICTIONS",
              f"  P1 monitoring_tag <= -300 at 72h both halves: {g('monitoring_tag', '72h'):+.0f} (tune {g('monitoring_tag', '72h', 'tune'):+.0f} / "
              f"hold {g('monitoring_tag', '72h', 'hold'):+.0f})",
              f"  P2 delist <= -500 at 72h both halves: {g('delist', '72h'):+.0f} (tune {g('delist', '72h', 'tune'):+.0f} / hold {g('delist', '72h', 'hold'):+.0f})",
              f"  P3 list_futures <= -500 over 7d both halves: {g('list_futures', '7d'):+.0f} (tune {g('list_futures', '7d', 'tune'):+.0f} / "
              f"hold {g('list_futures', '7d', 'hold'):+.0f})",
              f"  P4 seed_tag / launchpool <= -500 over 7d: {g('seed_tag', '7d'):+.0f} / {g('launchpool', '7d'):+.0f}",
              f"  P5 list_spot / adds_products: already {g('list_spot', 'already'):+.0f} / {g('adds_products', 'already'):+.0f} vs after 24h "
              f"{g('list_spot', '24h'):+.0f} / {g('adds_products', '24h'):+.0f}",
              f"  P6 market-wide on BTC |mean| < 30 at 1h-24h: " + ", ".join(f"{et} {g(et, '24h'):+.0f}" for et in ("etf", "regulation", "macro", "treasury_buy")),
              f"  USABLE (|mean| >= 24bp, t >= 2, same sign both halves): {usable if usable else 'none yet'}"]
    txt = "\n".join(lines)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
