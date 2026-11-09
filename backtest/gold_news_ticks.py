"""AUDIT of gold_news_breakout.py's 'fill artifact' verdict, on real Exness ticks (2026-11-08)

WHY. gold_news_breakout.py found a +-5 / +-10bp straddle on NFP worth +20bp a trade at LEVEL fills and called it a fill artifact, because the
trigger MINUTE runs a median 34bp past the level. A 1-minute bar cannot tell the two things apart: (a) the price JUMPED past the level (a stop
order fills far away = slippage) or (b) it crossed the level and kept going inside the minute (a stop fills near the level and earns the run).
Its CLOSE fill assumes you enter at the end of the trigger minute, which is a manual reaction, not a resting stop order. The file says 'no tick
data before 2026', but MT5 serves Exness XAUUSDm ticks for 2026: 9 NFP, 9 CPI and 6 FOMC releases. Too few for a verdict on the edge;
enough to MEASURE the fill.

THE MODEL (Exness Standard, no commission, the spread is in the bid / ask). Levels from the MID 5 s before the release, +-X bp.
A buy stop triggers on the first tick whose ASK >= up and fills at that tick's ask (L = 0 s) or at the ask L = 0.5 / 1 / 2 s later
(execution delay); a sell stop mirrors on the BID. The first side to trigger is the trade, the other level is its stop (filled the same way);
out at T + 120 min at the bid (long) / ask (short). Result in bp of the reference mid - net, nothing more to charge.
The same 2026 events through gold_news_breakout.rule_c on HistData bid bars (LEVEL / CLOSE / EXTREME, net of its 4.94bp) for comparison.

PREDICTIONS (written before the first run, 2026-11-08):
  K1  NFP, +-5bp: median slippage of the L = 0 tick fill past the level is 5-15bp (the first post-release tick gaps), far below the bar's
      34bp run; so the tick result sits between the bar's LEVEL and CLOSE fills, nearer LEVEL.
  K2  The release-second spread is 3-10x the pre-release spread.
  K3  With 24 events nothing here is significant; this measures the fill, not the edge.

RESULT (2026-11-08, logs/gold_news_ticks.txt + .csv; 8 NFP (04-03 was Good Friday, no ticks), 9 CPI, 6 FOMC).
  NFP +-5bp: the stop fill lands a median +9.1bp past the level at L = 0 (+11.0 / +11.5 / +9.8 at 0.5 / 1 / 2 s), triggers ~1.2 s after the
  release (Exness's quote lag); +-10bp +4.1 .. +14.9, +-20bp +1.6 .. +12.3. CPI and FOMC: 0 .. +6bp. NOT the bar's 34bp: most of the trigger
  minute's run is continuation that a resting stop earns. Tick net per trade (all-in): NFP +-5 +64.7 (bar LEVEL on the same events +55.5, bar
  CLOSE -2.1, EXTREME -12.2); CPI +-5 +10.8 (LEVEL +0.8, CLOSE -21.3); FOMC +-5 +44.3 (LEVEL +69.5, CLOSE +34.5). Per event the tick result
  tracks the LEVEL fill minus the entry slip; the two big gaps are feed differences (2026-02-11 NFP: a HistData whipsaw bar Exness did not have;
  2026-09-16 FOMC: Exness triggered the other side 4 s before the release). Release spread 0.6 -> 1.4bp median (this demo feed barely widens).
  K1 RIGHT on the slippage (5-15bp), half wrong on the place (the tick result sits AT the LEVEL fill, not between). K2 WRONG (1.7x, not 3-10x).
  K3 right. So gold_news_breakout.py's CLOSE / EXTREME 'realistic bounds' are bounds for a MANUAL entry after the minute closes, not for a
  resting stop order, and its 'fill artifact' verdict rested on them.
RE-SCORE (logs/gold_news_ticks_rescore.txt), S on the entry + 2bp on a stop exit: NFP +-5: S 2 +19.1bp (t 4.2), S 10 +11.1 (t 2.45; tune
  +13.4 t 2.2 / holdout +7.4 t 1.1; 12 of 17 years positive), S 15 +6.1 (t 1.3), S 20 +1.1. NFP +-10 at S 10: +10.3 (t 2.1; holdout +2.2).
  CPI +-5: gross +5.7, at S 10 -8.7 (t -3.1): dead. FOMC +-5 at S 10 +2.7 (t 0.4): nothing.
  S1 RIGHT (both halves positive, pooled t 2.45), S2 WRONG (CPI negative), S3 right. VERDICT: the NFP straddle is a weak LEAD, not an artifact
  and not a pass (holdout t 1.1 < 2; found after a 42-cell search; 2010-2026 slippage assumed from 8 2026 events on a DEMO feed).
  In money: Exness's minimum 0.01 lot = 1 oz (~$4,070, ~13.6x on $300): +11bp = ~$4.5 a release, ~12 a year; a stopped trade costs ~23bp
  (~$9), a winner +40..+200bp. What would settle it: the next NFPs as a DEMO straddle (real fills on the broker's execution, not its quote).

PART 2 - THE RE-SCORE (`--rescore`, HistData bars 2010-2026, no MT5 needed). gold_news_breakout's LEVEL straddle charged 2bp for a stop fill;
the ticks above say what a stop fill costs. Re-score the same straddle with S bp charged on the ENTRY fill and 2bp on a stop exit (amended after
the per-event tick table: stopped trades lost the level gap plus the entry slip, the exit slipped ~0-3bp; the first re-score charged S on both), S = 2 (the original), 10 (about the NFP tick median), 15, 20 (pessimistic). Adds CPI m/m
(08:30 New York), which the original never tested. Same halves (first 60% of events), same costs otherwise.
PREDICTIONS (written before the re-score):
  S1  NFP +-5bp at S = 10: net still > 0 on both halves, pooled t >= 2: 60%.
  S2  CPI +-5bp at S = 10: positive pooled, t < 2: 55%.
  S3  At S = 20 nothing has t >= 2 on both halves: 70%.

    python backtest/gold_news_ticks.py             (needs the MT5 terminal; ticks cached in strategy_analysis/data/news_ticks/)
    python backtest/gold_news_ticks.py --rescore   (bars only)
"""
from __future__ import annotations

import datetime as dt
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest import gold_news_breakout as g  # noqa: E402

LOG = ROOT / "logs" / "gold_news_ticks.txt"
CACHE = ROOT / "strategy_analysis" / "data" / "news_ticks"
SYM = "XAUUSDm"
NAMES = (("NFP", "Non-Farm Employment Change"), ("CPI", "CPI m/m"), ("FOMC", "FOMC Statement"))
LAT = (0.0, 0.5, 1.0, 2.0)
XS = (5, 10, 20)
EXIT_S = 120 * 60
STOP_EXIT_SLIP = 2.0      # bp on the stop exit: the 2026 ticks show stopped NFP trades lose the level gap + the ENTRY slip, the exit itself ~0-3bp


def fetch(mt5, t0: pd.Timestamp):
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / f"{SYM}_{t0:%Y%m%d_%H%M%S}_2h.pkl"
    if f.exists():
        return pickle.loads(f.read_bytes())
    a = dt.datetime.fromtimestamp(t0.timestamp() - 180, dt.timezone.utc)
    b = dt.datetime.fromtimestamp(t0.timestamp() + EXIT_S + 120, dt.timezone.utc)
    r = mt5.copy_ticks_range(SYM, a, b, mt5.COPY_TICKS_ALL)
    out = None
    if r is not None and len(r):
        d = pd.DataFrame(r)
        d = d[(d.bid > 0) & (d.ask >= d.bid)]
        out = (d.time_msc.to_numpy() / 1000.0, d.bid.to_numpy(float), d.ask.to_numpy(float))
    f.write_bytes(pickle.dumps(out))
    return out


def at_or_after(ts, t):
    """index of the first tick at or after time t (len(ts) if none)."""
    return int(np.searchsorted(ts, t, side="left"))


def straddle(ts, bid, ask, T0, x, lat):
    """one straddle on ticks. Returns dict(side, net_bp, slip_bp, trig_s) or None (no trigger in 60 min / no data)."""
    i_ref = at_or_after(ts, T0 - 5) - 1
    if i_ref < 0 or T0 - ts[i_ref] > 120:
        return None
    p0 = (bid[i_ref] + ask[i_ref]) / 2
    up, dn = p0 * (1 + x / 1e4), p0 * (1 - x / 1e4)
    k0, k1 = at_or_after(ts, T0 - 5), at_or_after(ts, T0 + 3600)
    hu = np.flatnonzero(ask[k0:k1] >= up)
    hd = np.flatnonzero(bid[k0:k1] <= dn)
    iu = k0 + hu[0] if len(hu) else None
    idn = k0 + hd[0] if len(hd) else None
    if iu is None and idn is None:
        return None
    side = 1 if (idn is None or (iu is not None and iu < idn)) else -1
    it = iu if side > 0 else idn
    jf = min(at_or_after(ts, ts[it] + lat), len(ts) - 1)            # execution delay: the first tick L seconds after the trigger
    entry = ask[jf] if side > 0 else bid[jf]
    level = up if side > 0 else dn
    slip = side * (entry - level) / p0 * 1e4
    # the stop = the opposite level, from the tick after the entry
    t_exit = T0 + EXIT_S
    ke = at_or_after(ts, t_exit)
    seg = slice(jf + 1, ke)
    hs = np.flatnonzero(bid[seg] <= dn) if side > 0 else np.flatnonzero(ask[seg] >= up)
    if len(hs):
        js = jf + 1 + hs[0]
        jx = min(at_or_after(ts, ts[js] + lat), len(ts) - 1)
        out = bid[jx] if side > 0 else ask[jx]
    else:
        if ke >= len(ts):
            return None
        out = bid[ke - 1] if side > 0 else ask[ke - 1]
    net = side * (out - entry) / p0 * 1e4
    return dict(side=side, net_bp=net, slip_bp=slip, trig_s=ts[it] - T0, stopped=bool(len(hs)))


def spread_bp(ts, bid, ask, a, b):
    k0, k1 = at_or_after(ts, a), at_or_after(ts, b)
    if k1 <= k0:
        return np.nan
    m = (bid[k0:k1] + ask[k0:k1]) / 2
    return float(np.max((ask[k0:k1] - bid[k0:k1]) / m) * 1e4)


def main():
    import MetaTrader5 as mt5
    from backtest import fx_macro_data as md
    assert mt5.initialize(), mt5.last_error()
    mt5.symbol_select(SYM, True)
    ff = md.load("ff_2007_2026.csv")
    usd = ff[ff.currency == "USD"].copy()
    usd["utc"] = pd.to_datetime(usd.utc)
    bars = g.load_gold()
    rows = []
    try:
        for lab, name in NAMES:
            for t in usd[(usd.name == name) & (usd.utc >= "2026-01-01")].utc.drop_duplicates():
                t0 = pd.Timestamp(t).tz_localize("UTC")
                tk = fetch(mt5, t0)
                if tk is None:
                    continue
                ts, bid, ask = tk
                T0 = t0.timestamp()
                pre = spread_bp(ts, bid, ask, T0 - 60, T0 - 5)
                rel = spread_bp(ts, bid, ask, T0, T0 + 10)
                Tms = int(T0 * 1000)
                for x in XS:
                    bar = {f: g.rule_c(bars, Tms, x, f)[1] * 1e4 for f in ("level", "close", "extreme")}
                    for lat in LAT:
                        r = straddle(ts, bid, ask, T0, x, lat)
                        if r is None:
                            continue
                        rows.append(dict(ev=lab, t=t0, x=x, lat=lat, pre_spread=pre, rel_spread=rel,
                                         bar_level=bar["level"], bar_close=bar["close"], bar_extreme=bar["extreme"], **r))
    finally:
        mt5.shutdown()
    D = pd.DataFrame(rows)
    L = [f"backtest/gold_news_ticks.py, {pd.Timestamp.now():%Y-%m-%d %H:%M}; Exness {SYM} ticks, 2026 releases; straddle +-X bp from the mid 5 s before; "
         f"stop orders filled at the first tick's ask / bid through the level (+ L s delay); out at T+120 min; bp of the reference mid, net (spread inside)"]
    sp = D.drop_duplicates(["ev", "t"])
    L.append(f"events: {sp.groupby('ev').size().to_dict()}; spread pre-release (max over T-60..T-5 s) median {sp.pre_spread.median():.1f}bp, "
             f"release (max over T..T+10 s) median {sp.rel_spread.median():.1f}bp, ratio median {(sp.rel_spread / sp.pre_spread).median():.1f}x")
    L.append(f"{'event':<5}{'x':>4}{'L s':>5}{'n':>4}{'slip med':>10}{'slip mean':>10}{'tick net':>10}{'bar LEVEL':>11}{'bar CLOSE':>11}{'bar EXTR':>10}   tick net per event")
    for (ev, x, lat), d in D.groupby(["ev", "x", "lat"], sort=False):
        L.append(f"{ev:<5}{x:>4}{lat:>5.1f}{len(d):>4}{d.slip_bp.median():>+10.1f}{d.slip_bp.mean():>+10.1f}{d.net_bp.mean():>+10.1f}"
                 f"{d.bar_level.mean():>+11.1f}{d.bar_close.mean():>+11.1f}{d.bar_extreme.mean():>+10.1f}   "
                 + " ".join(f"{v:+.0f}" for v in d.net_bp))
    L.append("(bar columns: gold_news_breakout.rule_c on HistData bid bars for the SAME events, net of its 4.94bp; tick net needs no extra cost)")
    txt = "\n".join(L)
    LOG.write_text(txt + "\n", encoding="utf-8")
    D.to_csv(LOG.with_suffix(".csv"), index=False)
    print(txt)


def straddle_level(b, T, x):
    """gold_news_breakout.rule_c with LEVEL fills, returning (gross, number of stop-order fills): entry = 1, +1 if stopped (a whipsaw bar = 2)."""
    p0 = b.px_at(T)
    if np.isnan(p0):
        return np.nan, 0
    up, dn = p0 * (1 + x / 1e4), p0 * (1 - x / 1e4)
    j, end = np.searchsorted(b.t, T), np.searchsorted(b.t, T + 60 * g.MIN)
    while j < min(end, len(b.t)):
        u, v = b.h[j] >= up, b.l[j] <= dn
        if u and v:
            return dn / up - 1, 2
        if u or v:
            d = 1 if u else -1
            entry = max(up, b.o[j]) if d > 0 else min(dn, b.o[j])
            stop = dn if d > 0 else up
            k, t_exit = j, T + 120 * g.MIN
            while k < len(b.t) and b.t[k] < t_exit:
                if d > 0 and b.l[k] <= stop:
                    return d * ((min(stop, b.o[k]) if k > j else stop) / entry - 1), 2
                if d < 0 and b.h[k] >= stop:
                    return d * ((max(stop, b.o[k]) if k > j else stop) / entry - 1), 2
                k += 1
            ex = b.px_at(t_exit)
            return (d * (ex / entry - 1) if np.isfinite(ex) else np.nan), 1
        j += 1
    return np.nan, 0


def rescore():
    from backtest import fx_macro_data as md
    b, ff = g.load_gold(), md.load("ff_2007_2026.csv")
    L = [f"backtest/gold_news_ticks.py --rescore, {pd.Timestamp.now():%Y-%m-%d %H:%M}; HistData XAUUSD bid bars; LEVEL straddle with S bp on the ENTRY fill and "
         f"{STOP_EXIT_SLIP:.0f}bp on a stop exit + the original {g.NEWS_COST * 1e4:.2f}bp; halves = first 60% of events"]
    L.append(f"{'event':<6}{'x':>4}{'S':>4}{'n':>5}{'gross':>8}{'net':>8}{'t':>7}{'tune net':>10}{'t':>6}{'hold net':>10}{'t':>6}{'win%':>6}  by year (mean net bp)")
    for lab, name, hh, mm, since in (("NFP", "Non-Farm Employment Change", 8, 30, "2010-02-01"), ("CPI", "CPI m/m", 8, 30, "2010-02-01"),
                                      ("FOMC", "FOMC Statement", 14, 0, "2013-01-01")):
        usd = ff[(ff.currency == "USD") & (ff.name == name)]
        ev_utc = pd.DatetimeIndex(pd.to_datetime(usd.utc)).unique()
        ev_utc = g.at_ny_clock(ev_utc[(ev_utc >= since) & (ev_utc <= "2026-09-20")], hh, mm)
        ev = g.to_ms(ev_utc)
        early = ev < ev[int(len(ev) * g.TUNE)]
        yr = pd.to_datetime(ev, unit="ms").year
        for x in XS:
            res = np.array([straddle_level(b, T, x) for T in ev], dtype=float)
            gross, nfill = res[:, 0] * 1e4, res[:, 1]
            for S in (2, 10, 15, 20):
                net = gross - g.NEWS_COST * 1e4 - S * (nfill > 0) - STOP_EXIT_SLIP * np.maximum(nfill - 1, 0)
                m = np.isfinite(net)

                def tt(a):
                    a = a[np.isfinite(a)]
                    return a.mean() / (a.std(ddof=1) / np.sqrt(len(a))) if len(a) > 4 else np.nan
                byy = pd.Series(net[m], index=yr[m]).groupby(level=0).mean()
                L.append(f"{lab:<6}{x:>4}{S:>4}{m.sum():>5}{np.nanmean(gross):>+8.2f}{np.nanmean(net):>+8.1f}{tt(net):>+7.2f}{np.nanmean(net[early]):>+10.1f}{tt(net[early]):>+6.1f}"
                         f"{np.nanmean(net[~early]):>+10.1f}{tt(net[~early]):>+6.1f}{(net[m] > 0).mean() * 100:>6.0f}  "
                         + " ".join(f"{y % 100:02d}:{v:+.0f}" for y, v in byy.items()))
    txt = "\n".join(L)
    out = LOG.with_name("gold_news_ticks_rescore.txt")
    out.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    rescore() if "--rescore" in sys.argv else main()
