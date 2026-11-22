"""THE LIQUIDATION MAP: CAN WE PREDICT WHERE A SWEEP WILL HIT, AND DOES PRICE BOUNCE THERE? (2026-11-15)

THE USER (2026-11-15): "if we can predict the exact liquidity sweep prices of buyers we can scalp in crypto too with high leverage" ->
"Yes, test it". Already known here: the obvious sweep level (the 24-hour low) beats a random entry by 5-25bp and nets ~0 since 2024
(sweep_confluence.py); the bounce after liquidation cascades is dead (cascade_redux.py); buying an open-interest flush is dead on the
PIT top-40 (oi_flush_pit.py); deep resting buys (crash bids, capit2) survive at 1x; and leverage cannot rescue a small edge (scalp_1m.py:
the best edges' best leverage is 4-11x at zero fees). The one untested piece: an ESTIMATED LIQUIDATION MAP (the idea behind Coinglass's
heatmap) - where leveraged traders' liquidation prices cluster, from when open interest grew and at what price.

MAP (per coin, rebuilt hour by hour; the map at an hour's close uses that hour and earlier only)
  - open interest in coins at each hour's close (Binance's metrics archive, backtest/liq_map_fetch.py: the hour's last 5-minute row);
  - existing positions are liquidated first: every long-liquidation bin at or above the hour's low is removed, every short bin at or
    below its high;
  - then, when open interest FELL, every live position shrinks by the same fraction (closed in proportion);
  - when it ROSE by dOI coins, new positions worth dOI x P are booked at the hour's typical price P = (H + L + C) / 3: every contract
    has a long and a short, each side spread equally over 10x / 20x / 50x / 100x, a long liquidated at P x (1 - 1/L), a short at
    P x (1 + 1/L) (maintenance margin ignored);
  - bins 0.25% wide in log price; a cluster's value = the sum of 3 neighbouring bins (0.75%).
EVENTS   at every 4-hour close (00, 04, ... 20 UTC) per coin in the point-in-time top-40 (dead coins in; wide_book.eligibility via
         market_neutral.drop_non_crypto), 2022-02..2026-09 (January 2022 = warm-up): the LONG cluster = the strongest long-liquidation
         cluster 1-10% below the close, the SHORT cluster the same above. BIG = its value / the coin's open-interest value at or above
         the 80th percentile of the coin's own readings in the previous 90 days (strictly earlier, at least 60 readings). One event per
         coin and side per 24 hours (a cooldown from the last big event), so one cluster is not counted six times a day.
TRADE    a resting LIMIT at the cluster price for the next 24 hours (a buy for a long cluster, a sell for a short one), filled when an
         hour trades 0.05% through it, at the level (or at the open if the hour opens past it). Exits, on 1-hour bars:
           4h       the close 4 hours after the fill hour
           24h      the close 24 hours after the fill hour
           bracket  stop 1.5 x ATR(14, 1h) past the entry, target 2 x that distance (2R), out after 48 hours; the fill hour counts as
                    stopped if it also reaches the stop; later hours touching both = stopped; a gap through the stop exits at the open.
         Costs: 12bp a round trip + funding 1bp / 8h on either side (flat, conservative). No leverage in the test: a pass would be
         judged at 1x first, and leverage only through the Kelly arithmetic scalp_1m.py already did.
CONTROL  the SAME order (same coin, side, % distance from the close, rules) at 5 random OTHER 4-hour closes of the same coin within 30
         days either side, same half: "a dip-buy (or rally-sell) that far away at a random time". MAGNET = the events' fill rate over
         the controls'. EXCESS = the event's net return minus the mean of its filled controls' (events with no filled control drop out).
HALVES   the 60% point of the 4-hour grid (CUT, printed). t clustered by fill day (sweep_confluence.t_by_day).
PASS     (per cell: long / short x 4h / 24h / bracket = 6) on BOTH halves net > 0 with t >= 2 AND excess > 0 with t >= 2; Holm < 0.05
         over the 6 (p from the weaker half's net t). MDE80 printed per cell (2.8 x the holdout net's standard error).
LIMITS   the map is a MODEL: Binance publishes no historical liquidations, the leverage mix is assumed, and open interest is net (a long
         closing against a new long leaves it unchanged). One venue's open interest. Hourly bars decide fills and exits.

REGISTERED BEFORE THE FIRST RUN (2026-11-15; my prior that any cell passes: about 5%)
  L1  No cell passes.
  L2  No magnet: big clusters fill at 0.9x-1.1x the controls' rate on both halves, both sides.
  L3  After a fill the cluster trade is no better than the control: |excess| under 15bp at 4 hours on both halves, both sides.
  L4  The long side loses after costs on the holdout at all three exits.
  L5  Big clusters sit a median 2-6% from the close.

RESULT (2026-11-15, logs/liq_map.txt): NO PASS, 0 of 6. 37,905 events on 346 coins. Big clusters sit a median 5.9% (long) / 6.8% (short)
from the close and fill exactly as often as a random level that far away (ratio 0.97-1.01); after the fill no cell beats the control on
both halves (excess |t| <= 1.9, the short side's holdout excess negative); the long side loses at every exit on the holdout. L1, L2, L4,
L5 right; L3 wrong (the short 4h holdout excess is -38bp, worse than random, not inside +-15bp).
AMENDMENT (after the first run, POST HOC, `--validate`, logs/liq_map_validate.txt): is the map blind? On the 60 coins with the longest
open interest, the hour that trades through a CLUSTER carries more volume than the hour that trades through a random level the same
distance away (mean log volume ratio +0.19 long / +0.21 short, t +13.9 / +15.3; medians 2.45x vs 2.01x the previous 24 hours): the map
finds where extra forced trading happens, and that trading does not say which way the price goes next.

    python -m backtest.liq_map            (needs backtest/liq_map_fetch.py's open interest first)
    python -m backtest.liq_map --validate (the post-hoc volume check)
"""
from __future__ import annotations

import sys
import time
from math import log
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest import candle_scan as cs  # noqa: E402
from backtest import sweep_confluence as sc  # noqa: E402

OI_DIR = ROOT / "strategy_analysis" / "data" / "liqmap"
LOG = ROOT / "logs" / "liq_map.txt"
H = 3_600_000
LEVS = (10, 20, 50, 100)
STEP = log(1.0025)
WIN = 3                                   # bins in a cluster
NEAR, FAR = 0.01, 0.10
BIG_Q, LOOKBACK, MIN_READ = 0.80, 90 * 6, 60
COOLDOWN = 24
LIVE = 24
THROUGH = 0.0005
HOLD = {"4h": 4, "24h": 24}
BR_STOP, BR_R, BR_MAX = 1.5, 2.0, 48
FEE, FUND_H = 12e-4, 1e-4 / 8
N_CTRL, CTRL_SPAN = 5, 30 * 6
START = pd.Timestamp("2022-02-01")
CELLS = [(s, x) for s in ("long", "short") for x in ("4h", "24h", "bracket")]


# ---------------------------------------------------------------- the map

class Grid:
    """Log-price bins 0.25% wide covering [lo, hi]."""

    def __init__(self, lo, hi):
        self.p0 = log(lo)
        self.n = int((log(hi) - self.p0) / STEP) + 2

    def idx(self, p):
        return int(np.clip(np.floor((log(p) - self.p0) / STEP), 0, self.n - 1))

    def price(self, i):
        return float(np.exp(self.p0 + (i + 0.5) * STEP))


def map_step(longm, shortm, grid, oi_prev, oi_now, hi, lo, cl):
    """One hour of the map, in place: liquidate against the hour's range, shrink on a fall in open interest, book new positions on a
    rise. Returns the typical price used."""
    longm[grid.idx(lo):] = 0.0
    shortm[:grid.idx(hi) + 1] = 0.0
    P = (hi + lo + cl) / 3
    if oi_prev and oi_now and oi_prev > 0 and np.isfinite(oi_now) and np.isfinite(oi_prev):
        if oi_now < oi_prev:
            f = oi_now / oi_prev
            longm *= f
            shortm *= f
        elif oi_now > oi_prev:
            v = (oi_now - oi_prev) * P / len(LEVS)
            for L in LEVS:
                longm[grid.idx(P * (1 - 1 / L))] += v
                shortm[grid.idx(P * (1 + 1 / L))] += v
    return P


def cluster(m, grid, close, side):
    """(price, value) of the strongest WIN-bin cluster 1-10% below (side long) or above (short) the close; (nan, 0) if empty."""
    if side == "long":
        a, b = grid.idx(close * (1 - FAR)), grid.idx(close * (1 - NEAR))
    else:
        a, b = grid.idx(close * (1 + NEAR)), grid.idx(close * (1 + FAR))
    if b - a + 1 < WIN:
        return float("nan"), 0.0
    seg = m[a:b + 1]
    sums = np.convolve(seg, np.ones(WIN), mode="valid")
    k = int(np.argmax(sums))
    if sums[k] <= 0:
        return float("nan"), 0.0
    return grid.price(a + k + WIN // 2), float(sums[k])


def is_big(hist, ratio, lv):
    """A cluster is BIG when the coin has at least MIN_READ earlier readings and this one is at or above their 80th percentile."""
    return len(hist) >= MIN_READ and np.isfinite(lv) and ratio > 0 and ratio >= np.quantile(hist, BIG_Q)


# ---------------------------------------------------------------- trades

def atr14(h, l, c, i):  # noqa: E741
    if i < 15:
        return float("nan")
    pc = c[i - 14:i]
    tr = np.maximum(h[i - 13:i + 1] - l[i - 13:i + 1], np.maximum(np.abs(h[i - 13:i + 1] - pc), np.abs(l[i - 13:i + 1] - pc)))
    return float(tr.mean())


def trade(o, h, l, c, i, side, level, atr):  # noqa: E741
    """The limit order placed at the close of bar i. None if not filled in LIVE bars or the data ends before every exit; else
    dict(j fill bar, fill, r4h, r24h, rbr, hbr hours in the bracket trade) as signed returns before costs."""
    n = len(c)
    sg = 1 if side == "long" else -1
    a, b = i + 1, min(i + 1 + LIVE, n)
    if a >= n:
        return None
    if sg > 0:
        hit = np.flatnonzero(l[a:b] <= level * (1 - THROUGH))
    else:
        hit = np.flatnonzero(h[a:b] >= level * (1 + THROUGH))
    if not hit.size:
        return None
    j = a + int(hit[0])
    fill = min(level, o[j]) if sg > 0 else max(level, o[j])
    if j + max(HOLD.values()) >= n or j + BR_MAX >= n or not np.isfinite(atr) or atr <= 0:
        return None
    out = dict(j=j, fill=fill)
    for k, hh in HOLD.items():
        out["r" + k] = sg * (c[j + hh] / fill - 1)
    d = BR_STOP * atr
    stop, tgt = fill - sg * d, fill + sg * BR_R * d
    if (l[j] <= stop) if sg > 0 else (h[j] >= stop):
        out["rbr"], out["hbr"] = sg * (stop / fill - 1), 1
        return out
    for k in range(j + 1, j + 1 + BR_MAX):
        if (l[k] <= stop) if sg > 0 else (h[k] >= stop):
            ex = min(stop, o[k]) if sg > 0 else max(stop, o[k])
            out["rbr"], out["hbr"] = sg * (ex / fill - 1), k - j + 1
            return out
        if (h[k] >= tgt) if sg > 0 else (l[k] <= tgt):
            out["rbr"], out["hbr"] = sg * (tgt / fill - 1), k - j + 1
            return out
    out["rbr"], out["hbr"] = sg * (c[j + BR_MAX] / fill - 1), BR_MAX + 1
    return out


def net(r, hours):
    return r - FEE - FUND_H * hours


def nets(tr):
    return {"4h": net(tr["r4h"], HOLD["4h"] + 1), "24h": net(tr["r24h"], HOLD["24h"] + 1), "bracket": net(tr["rbr"], tr["hbr"])}


# ---------------------------------------------------------------- one coin

def is_ref(t_ms):
    """A 4-hour close: the bar that STARTS at 03, 07, ..., 23 UTC closes at 04, 08, ..., 00."""
    return ((t_ms // H) + 1) % 4 == 0


def coin_events(t, o, h, l, c, oi, months, rng, cut_ms):  # noqa: E741
    """All big-cluster events of one coin with their trades and controls. t hour starts (ms), oi aligned (NaN = no reading),
    months = the set of 'YYYY-MM' the coin is eligible in (judged at the reference bar's CLOSE). A gap of more than 48 hours between
    open-interest readings (a stretch out of the universe, not fetched) RESETS the map: the jump across it is not booked as new
    positions."""
    n = len(c)
    grid = Grid(np.nanmin(l[l > 0]) * 0.5, np.nanmax(h) * 2.0)
    longm, shortm = np.zeros(grid.n), np.zeros(grid.n)
    ratios = {"long": [], "short": []}
    last_ev = {"long": -10**9, "short": -10**9}
    refs, out = [], []
    prev = np.nan
    oiv_px = np.nan
    last_t = None
    for i in range(n):
        if np.isfinite(oi[i]):
            if last_t is not None and t[i] - last_t > 48 * H:
                longm[:] = 0.0
                shortm[:] = 0.0
                prev = np.nan
            last_t = t[i]
        cur = oi[i] if np.isfinite(oi[i]) else prev
        map_step(longm, shortm, grid, prev, cur, h[i], l[i], c[i])
        prev = cur
        if not is_ref(t[i]):
            continue
        tc = pd.Timestamp(t[i] + H, unit="ms")
        if tc < START or tc.strftime("%Y-%m") not in months or not np.isfinite(cur) or cur <= 0:
            continue
        oiv_px = cur * c[i]
        refs.append(i)
        atr = atr14(h, l, c, i)
        for side, m in (("long", longm), ("short", shortm)):
            lv, val = cluster(m, grid, c[i], side)
            ratio = val / oiv_px if oiv_px > 0 else 0.0
            big = is_big(ratios[side][-LOOKBACK:], ratio, lv)
            ratios[side].append(ratio)
            if not big or i - last_ev[side] < COOLDOWN:
                continue
            last_ev[side] = i
            dist = abs(lv / c[i] - 1)
            out.append(dict(i=i, side=side, level=lv, dist=dist, ratio=ratio, atr=atr, tr=trade(o, h, l, c, i, side, lv, atr)))
    # controls: the same order, same % distance, at 5 random other reference closes within 30 days either side (same half later)
    refs = np.array(refs, int)
    for ev in out:
        k = int(np.searchsorted(refs, ev["i"]))
        pool = np.r_[refs[max(0, k - CTRL_SPAN):k], refs[k + 1:k + 1 + CTRL_SPAN]]
        same = (t[ev["i"]] + H < cut_ms)
        pool = pool[(t[pool] + H < cut_ms) == same] if len(pool) else pool
        pick = rng.choice(pool, size=min(N_CTRL, len(pool)), replace=False) if len(pool) else []
        ctrl = []
        for i2 in pick:
            sg = 1 if ev["side"] == "long" else -1
            lv2 = c[i2] * (1 - sg * ev["dist"])
            ctrl.append(dict(i=int(i2), tr=trade(o, h, l, c, int(i2), ev["side"], lv2, atr14(h, l, c, int(i2)))))
        ev["ctrl"] = ctrl
    return out


# ---------------------------------------------------------------- statistics

def rows_from(evs_by_coin, t_by_coin, cut_ms):
    """One row per event: coin, side, half, fill day, the three nets, the control mean of each (filled controls), the control fill rate."""
    R = []
    for s, evs in evs_by_coin.items():
        t = t_by_coin[s]
        for ev in evs:
            t_ref = t[ev["i"]] + H
            ctrl = [x for x in ev["ctrl"] if x["tr"] is not None]
            r = dict(coin=s, side=ev["side"], half="tu" if t_ref < cut_ms else "ho", dist=ev["dist"], ratio=ev["ratio"],
                     filled=ev["tr"] is not None, n_ctrl=len(ev["ctrl"]), ctrl_filled=len(ctrl))
            if ev["tr"] is not None:
                ne = nets(ev["tr"])
                r["day"] = pd.Timestamp(t[ev["tr"]["j"]], unit="ms").strftime("%Y-%m-%d")
                for x in ("4h", "24h", "bracket"):
                    r[x] = ne[x]
                    r["c_" + x] = float(np.mean([nets(cx["tr"])[x] for cx in ctrl])) if ctrl else np.nan
            R.append(r)
    return pd.DataFrame(R)


def cell_stats(D, side, x, half):
    d = D[(D.side == side) & (D.half == half)]
    f = d[d.filled]
    out = dict(n_ev=len(d), n=len(f), fill=float(d.filled.mean()) if len(d) else np.nan,
               cfill=float(d.ctrl_filled.sum() / d.n_ctrl.sum()) if d.n_ctrl.sum() else np.nan)
    if len(f) < 3:
        return dict(out, net=np.nan, t=np.nan, ex=np.nan, ex_t=np.nan, mde=np.nan)
    y = f[x].astype(float)
    ex = (f[x] - f["c_" + x]).dropna()
    se = y.std(ddof=1) / np.sqrt(len(y))
    return dict(out, net=float(y.mean()), t=sc.t_by_day(y, f.day), ex=float(ex.mean()) if len(ex) else np.nan,
                ex_t=sc.t_by_day(ex, f.loc[ex.index, "day"]) if len(ex) > 2 else np.nan, mde=2.8 * float(se))


def passes(st, holm_p):
    return all(st[h]["net"] > 0 and st[h]["t"] >= 2 and st[h]["ex"] > 0 and st[h]["ex_t"] >= 2 for h in ("tu", "ho")) and holm_p < 0.05


# ---------------------------------------------------------------- run

def load_coin(s):
    from backtest.capitulation_wide import hourly
    f = OI_DIR / f"{s}.parquet"
    if not f.exists():
        return None
    hh = hourly(s)
    if hh is None:
        return None
    oi = pd.read_parquet(f)
    if not len(oi):
        return None
    t = hh.time.to_numpy("datetime64[ns]").astype(np.int64) // 10**6
    m = pd.Series(oi.oi.to_numpy(float), index=oi.t.astype(np.int64).to_numpy())
    oia = m.reindex(t).to_numpy(float)
    first = int(oi.t.min()) - 31 * 24 * H                       # the map starts at the first open interest (warm-up month included)
    keep = t >= first
    if keep.sum() < 600 or not np.isfinite(oia[keep]).any():
        return None                                              # the price history ends before (or barely overlaps) the open interest
    return (t[keep], *(hh[k].to_numpy(float)[keep] for k in ("open", "high", "low", "close")), oia[keep])


def main():
    t0 = time.time()
    from backtest.market_neutral import drop_non_crypto
    from backtest.wide_book import eligibility
    el = drop_non_crypto(eligibility(40))
    grid_t = pd.date_range(START, "2026-09-20", freq="4h")
    cut = grid_t[int(len(grid_t) * 0.6)]
    cut_ms = int(cut.value // 10**6)
    rng = np.random.default_rng(7)
    evs, ts = {}, {}
    for s in sorted(el):
        if not el[s]:
            continue
        x = load_coin(s)
        if x is None:
            continue
        t, o, h, l, c, oi = x  # noqa: E741
        evs[s] = coin_events(t, o, h, l, c, oi, set(el[s]), rng, cut_ms)
        ts[s] = t
    D = rows_from(evs, ts, cut_ms)
    st = {k: {h: cell_stats(D, k[0], k[1], h) for h in ("tu", "ho")} for k in CELLS}
    hp = dict(zip(CELLS, cs.holm([cs.p_one_sided(np.nan_to_num(min(st[k]["tu"]["t"], st[k]["ho"]["t"]), nan=-10.0)) for k in CELLS])))
    L = [f"backtest/liq_map.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; {len(evs)} coins with open interest; events "
         f"{len(D)} ({(D.side == 'long').sum()} long, {(D.side == 'short').sum()} short); CUT {cut:%Y-%m-%d %H:%M}; "
         f"12bp + 1bp / 8h; leverage mix {LEVS}", ""]
    for side in ("long", "short"):
        d = D[D.side == side]
        L.append(f"{side}: big clusters a median {d.dist.median() * 100:.2f}% from the close (IQR {d.dist.quantile(.25) * 100:.2f}-"
                 f"{d.dist.quantile(.75) * 100:.2f}%); filled {d.filled.mean() * 100:.1f}% vs controls "
                 f"{d.ctrl_filled.sum() / max(1, d.n_ctrl.sum()) * 100:.1f}%")
    L += ["", f"{'cell':<16}{'n tune/hold':<14}{'fill vs ctrl tune / hold':<30}{'NET tune / hold (t)':<34}{'EXCESS tune / hold (t)':<34}MDE80 hold"]
    for k in CELLS:
        a, b = st[k]["tu"], st[k]["ho"]
        L.append(f"{k[0] + ' ' + k[1]:<16}{a['n']:>5}/{b['n']:<7}  "
                 f"{a['fill'] * 100:4.1f}/{a['cfill'] * 100:4.1f}% | {b['fill'] * 100:4.1f}/{b['cfill'] * 100:4.1f}%   "
                 f"{a['net'] * 1e4:+7.1f} ({a['t']:+.1f}) / {b['net'] * 1e4:+7.1f}bp ({b['t']:+.1f})   "
                 f"{a['ex'] * 1e4:+7.1f} ({a['ex_t']:+.1f}) / {b['ex'] * 1e4:+7.1f}bp ({b['ex_t']:+.1f})   "
                 f"{b['mde'] * 1e4:5.0f}bp  holm {hp[k]:.2f}{'  PASS' if passes(st[k], hp[k]) else ''}")
    npass = sum(passes(st[k], hp[k]) for k in CELLS)
    mag = {(s, h): st[(s, "4h")][h]["fill"] / st[(s, "4h")][h]["cfill"] for s in ("long", "short") for h in ("tu", "ho")}
    l3 = all(abs(st[(s, "4h")][h]["ex"]) < 0.0015 for s in ("long", "short") for h in ("tu", "ho"))
    l4 = all(st[("long", x)]["ho"]["net"] < 0 for x in ("4h", "24h", "bracket"))
    md = D[D.side == "long"].dist.median()
    L += ["", f"PASSING: {npass} of 6", "REGISTERED PREDICTIONS",
          f"  L1 no cell passes -> {'RIGHT' if npass == 0 else 'WRONG'}",
          f"  L2 no magnet (fill ratio 0.9-1.1 on both halves, both sides) -> {'RIGHT' if all(0.9 <= v <= 1.1 for v in mag.values()) else 'WRONG'} "
          f"({', '.join(f'{s} {h} {v:.2f}' for (s, h), v in mag.items())})",
          f"  L3 |excess| < 15bp at 4h everywhere -> {'RIGHT' if l3 else 'WRONG'}",
          f"  L4 the long side loses on the holdout at all three exits -> {'RIGHT' if l4 else 'WRONG'}",
          f"  L5 long clusters a median 2-6% away -> {'RIGHT' if 0.02 <= md <= 0.06 else 'WRONG'} ({md * 100:.2f}%)",
          f"run time {time.time() - t0:.0f}s"]
    txt = "\n".join(L)
    LOG.write_text(txt + "\n", encoding="utf-8")
    D.to_pickle(LOG.with_suffix(".pkl"))
    print(txt)


def validate(n_coins=60):
    """POST HOC (added after the first run, 2026-11-15): is the map blind? Binance publishes no liquidation history, so the check is
    indirect: if the map's clusters are real piles of liquidations, the hour that trades through one should carry MORE volume and a
    WIDER range than the hour that trades through a random level the same distance away (the controls). Coins with the longest
    open-interest history; the fill hour's dollar volume over its previous 24 hours' mean, and its high-low range over the previous
    close. Writes logs/liq_map_validate.txt."""
    from backtest.capitulation_wide import hourly
    from backtest.market_neutral import drop_non_crypto
    from backtest.wide_book import eligibility
    el = drop_non_crypto(eligibility(40))
    sizes = sorted(((len(pd.read_parquet(OI_DIR / f"{s}.parquet")), s) for s in el if el[s] and (OI_DIR / f"{s}.parquet").exists()),
                   reverse=True)[:n_coins]
    grid_t = pd.date_range(START, "2026-09-20", freq="4h")
    cut_ms = int(grid_t[int(len(grid_t) * 0.6)].value // 10**6)
    rng = np.random.default_rng(7)
    rows = []
    for _, s in sizes:
        x = load_coin(s)
        if x is None:
            continue
        t, o, h, l, c, oi = x  # noqa: E741
        hh = hourly(s)
        qv = pd.Series(hh.qvol.to_numpy(float), index=hh.time.to_numpy("datetime64[ns]").astype(np.int64) // 10**6).reindex(t).to_numpy(float)
        for ev in coin_events(t, o, h, l, c, oi, set(el[s]), rng, cut_ms):
            for kind, tr in [("cluster", ev["tr"])] + [("control", cx["tr"]) for cx in ev["ctrl"]]:
                if tr is None or tr["j"] < 25:
                    continue
                j = tr["j"]
                base = np.nanmean(qv[j - 24:j])
                rows.append(dict(kind=kind, side=ev["side"], vol=qv[j] / base if base > 0 else np.nan, rng=(h[j] - l[j]) / c[j - 1]))
    V = pd.DataFrame(rows)
    L = [f"backtest/liq_map.py --validate (POST HOC), {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; the {len(sizes)} coins with the longest "
         f"open-interest history; the hour a resting order at a CLUSTER vs at a random level the same distance away (controls) trades through", ""]
    for side in ("long", "short"):
        for kind in ("cluster", "control"):
            d = V[(V.side == side) & (V.kind == kind)]
            L.append(f"  {side:<5} {kind:<8} n {len(d):>6}  fill-hour volume / previous 24h: median {d.vol.median():.2f}, mean {d.vol.mean():.2f}; "
                     f"range: median {d.rng.median() * 100:.2f}%")
        a, b = V[(V.side == side) & (V.kind == "cluster")], V[(V.side == side) & (V.kind == "control")]
        lv, lb = np.log(a.vol.dropna()), np.log(b.vol.dropna())
        se = np.sqrt(lv.var() / len(lv) + lb.var() / len(lb))
        L.append(f"        cluster minus control, mean log volume ratio {lv.mean() - lb.mean():+.3f} (t {(lv.mean() - lb.mean()) / se:+.1f})")
    txt = "\n".join(L)
    (ROOT / "logs" / "liq_map_validate.txt").write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    if "--validate" in sys.argv:
        validate()
    else:
        main()
