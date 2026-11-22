"""LIQUIDITY SWEEP + HIGHER-TIMEFRAME SUPPLY / DEMAND ZONE + HIGHER-TIMEFRAME TREND, all three together (2026-11-08)

THE USER (2026-11-08): "what do you think about liquidity plus HTF supply and demand zone together, all three" -> "yes run it". Read as: a liquidity
sweep (the Analyst desk's SMC rule) that happens AT a fresh 4h supply / demand zone, in the direction of the daily trend.

WHAT IS ALREADY KNOWN (so this is not a fresh start)
  sweep_reclaim.py / sweep_confluence.py (2026-10): the 24-bar sweep + reclaim has REAL information (+5..+25bp over a matched random entry) but its gross edge is
    ~0 since 2024 and it loses after 12bp; 7 add-on factors incl. 'with the weekly trend' (168-bar mean) and 'equal lows' were tested: 0 of 14 confirmed.
  The desk's support / resistance bounce (41 calls): 22% hit, -0.36R. ict_fvg.py (fair value gaps): dead. rsi_confluence.py: higher-timeframe confirmations alone and in
    pairs: nothing.
  NOT tested before: an actual supply / demand ZONE (a base followed by an impulse, first retest) on 4h bars. That is the one new piece here.

THE EVENT = the desk's own sweep, imported unchanged from sweep_confluence.features: LONG bar low < the lowest low of the 24 bars before it, close > that low, close > open
  (SHORT mirrors). Same PIT top-40 (dead coins in), 1h bars 2020-2026, declustered (no event of the same coin and side within 12 bars of a kept one).
THE ZONE (4h bars built from the 1h bars, UTC grid, only complete 4h bars; every number fixed here, none tuned):
  base bar j: range <= 1.0 x ATR14(4h) (ATR through bar j). impulse bar j+1 right after it: DEMAND = body (close - open) >= +1.5 x ATR14(j) and close > the base's high;
  SUPPLY mirrors (body <= -1.5 ATR, close < the base's low). Zone = [low_j, high_j]. Known only when the impulse bar CLOSES (created = its end).
  Live: from creation, until the first 1h bar that trades into it (demand: low <= zone high; supply: high >= zone low) - the FIRST RETEST - and then for 24 more hours,
  unless a 1h close goes beyond the far edge (demand: close < zone low; supply: close > zone high) = broken. A zone not touched within 30 days (720 hours) is dead.
  An event is ZONED when a live zone of its own side exists at the signal bar AND the signal bar's wick is in it (long: bar low <= zone high; short: bar high >= zone low).
  Several live zones: the most recently created one.
THE TREND: previous completed UTC day's close / its 50-day mean - 1 (daily bars from the 1h bars, 50 complete days needed). Long wants > 0, short wants < 0.
THE TRADES (in at the NEXT bar's open, stop first inside a bar, gap-aware, 12bp round trip + funding, same funding code as sweep_confluence):
  T24  (the sweep_confluence trade, for the information test): stop = the sweep extreme, no target, out at the close 24 bars later.
  TR-A (the sweep's own trade, arm A): stop = sweep extreme -/+ 0.25 x ATR14(1h), target = 3 x the risk, out at the close 72 bars later. Result in R (net of fee / risk).
  TR-Z (the zone trader's trade, arms B and C): stop = beyond the zone's far edge or the sweep extreme, whichever is further, -/+ 0.25 ATR14(1h); target 3R; 72 bars.
THE CONTROL (per event, per trade): a random hour of the same coin and month with the SAME stop distance and target multiple. Excess = event - control. t is by distinct DAY
  (one market, many coins), halves split 2024-04-07 (pair_lab.HOLDOUT).
THE ARMS: A = every sweep (TR-A). B = zoned sweeps (TR-Z). C = zoned sweeps with the daily trend agreeing (TR-Z). Diagnostics: B and C on TR-A (same stop as A, so the
  zone's effect is not mixed with a wider stop); the INFORMATION TEST = zoned minus unzoned sweeps on T24 (and trend-agreeing minus not, inside zoned); the OPPOSITE-ZONE
  PLACEBO = long sweeps inside a live SUPPLY zone (short: inside DEMAND) - if the zone's side matters, these must do clearly worse.
GATE (per arm x side = 6 cells; Holm over the 6 on the holdout): PASS = net R > 0 on BOTH halves, holdout one-sided Holm p < 0.05 (day-clustered t), excess over the control
  > 0 on both halves, >= 100 holdout trades, and for B and C the information test positive on both halves (B: zoned - unzoned; C: trend-agreeing - not, inside zoned).
  A pass is a CANDIDATE for a forward paper record in the Analyst desk (registered separately), never a deployment. The holdout is the repo's shared, much-read one.

REGISTERED BEFORE THE FIRST RUN (2026-11-08; prior that any cell passes the gate: 6%)
  Z1  Arm A loses after fees on both halves for both sides (net R < 0): 85%.
  Z2  The zone adds no information: on T24 the zoned - unzoned spread is within +-0.15% and |t| < 2 on the holdout for both sides: 80%. P(spread > 0 with t > 2 on both
      halves for at least one side) = 10%.
  Z3  Arm B (zone stop, 3R) has net R < 0 on the holdout for both sides: 75%.
  Z4  The daily trend adds under +0.10R (C vs B on TR-Z) and nothing significant: 85%.
  Z5  The opposite-zone placebo is within 0.15% of the matching-zone sweeps on T24 (the zone's side does not matter): 65%.
  Z6  The 3R target is hit no more often than the control's by more than 3 points in any cell: 80%.
  Z7  Size: zoned sweeps are 5-20% of all sweeps; arm B 300-2,000 events a year, arm C 150-1,000 (the universe is large: 40 coins x 6.5 years).
  Z8  No cell passes the gate: 94%.

RESULT (2026-11-08, logs/sweep_zone.txt; 60,601 sweeps, 359 PIT coins, 2020-02 .. 2026-09; zoned 2,323 = 3.8% of sweeps (351 a year), zoned + daily trend agrees 1,352 = 58% of
  zoned (204 a year)): NO CELL PASSES THE GATE (0 of 6). The zone adds nothing, the trend adds a little that is not significant, and on the holdout the long zoned sweeps do WORSE.
  Arm A (every sweep, 3R / 72h), net R tune / holdout: long -0.10 / -0.19, short -0.05 / -0.07; excess over the matched control ~0 (within +-0.05R). Fee ~0.05-0.06R a trade.
  Arm B (zoned, zone stop, 3R / 72h): long +0.01 / -0.26 (holdout t -3.5, excess -0.21R, t -2.0), short -0.14 / -0.00. Arm C (zoned + daily trend): long -0.05 / -0.23,
    short -0.07 / +0.06 (holdout t +0.5, excess +0.03R, t +0.2).
  Information test on T24 (zoned - unzoned): long -0.03% / -0.38% (holdout t -2.1), short -0.00% / +0.08%. Trend-agrees - not, inside zoned: +0.34% / -0.04% long, +0.33% / +0.46%
    short (t 0.8-1.2, none significant). Hit rate at the 3R target: zoned 14-19% against the controls' 16-20%.
  Opposite-zone placebo: only 61 events (12-20 a cell; +6.7% to -2.4%): too few to say anything.
  Predictions: Z1 right. Z2 half wrong (the long holdout spread is -0.38%, t -2.1: worse, not 'within 0.15%'; the short side and the 'no positive spread' part were right).
    Z3 right (B short holdout -0.00R, i.e. zero). Z4 right. Z5 untestable (n 12-20). Z6 right in the 12 main cells (the diagnostic B-on-A long tune cell is +4 points, its
    holdout -6). Z7 wrong on the share (3.8%, registered 5-20%), right on the counts (B 351 a year, C 204). Z8 right.
  LIMITS: ONE zone definition (1.5 ATR impulse, one base bar, first retest within 24h, 30-day life) on 4h bars and one trend (previous day vs its 50-day mean); multi-bar bases,
    daily zones, 'tested' zones and a target at the next zone were not tried. The holdout cells have a standard error of about 0.07R and the fee is 0.05-0.06R, so a real net edge
    under about +0.15R could not have been seen. The holdout is the repo's shared, much-read one. Stated as: not found in this definition.

    python -m backtest.sweep_zone            run (caches the event table in logs/sweep_zone_events.pkl)
    python -m backtest.sweep_zone --refit    rebuild the event table
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest import pair_lab as pl  # noqa: E402
from backtest import sweep_confluence as sc  # noqa: E402
from backtest.capitulation_wide import funding_cum  # noqa: E402

LOG = ROOT / "logs" / "sweep_zone.txt"
CACHE = ROOT / "logs" / "sweep_zone_events.pkl"
HOLDOUT = pl.HOLDOUT
FEE = 0.0012
ATR_N = 14
IMPULSE, BASE_MAX = 1.5, 1.0
ZONE_LIFE_H, RETEST_H = 720, 24
PAD = 0.25
R_TARGET, HOLD_R, COOL = 3.0, 72, 12
DAILY_SMA = 50
TREND_WARM = 168
MIN_HOLD_TRADES = 100
FOUR_H = np.timedelta64(4, "h")


# ------------------------------------------------------------------ bars, zones, trend (every function reads only what is known at its timestamp)

def atr1h(h, l, c, n=ATR_N):
    pc = np.r_[np.nan, c[:-1]]
    tr = np.maximum.reduce([h - l, np.abs(h - pc), np.abs(l - pc)])
    return pd.Series(tr).rolling(n).mean().to_numpy()


def bars4h(t, o, h, l, c):
    """4h bars from 1h arrays on the UTC grid (00, 04, ...). Only blocks with all four hours present. Returns (start, o, h, l, c)."""
    df = pd.DataFrame({"k": pd.DatetimeIndex(t).floor("4h"), "o": o, "h": h, "l": l, "c": c})
    g = df.groupby("k", sort=True)
    cnt = g.size()
    a = pd.DataFrame({"o": g["o"].first(), "h": g["h"].max(), "l": g["l"].min(), "c": g["c"].last()})
    a = a[cnt == 4]
    return a.index.to_numpy("datetime64[ns]"), a.o.to_numpy(float), a.h.to_numpy(float), a.l.to_numpy(float), a.c.to_numpy(float)


def zones(t4, o4, h4, l4, c4):
    """Supply / demand zones: a list of (side, created, lo, hi); side +1 demand, -1 supply; created = the END of the impulse bar."""
    n = len(c4)
    if n < ATR_N + 2:
        return []
    atr = atr1h(h4, l4, c4)
    out = []
    for j in range(ATR_N, n - 1):
        a = atr[j]
        if not np.isfinite(a) or a <= 0 or h4[j] - l4[j] > BASE_MAX * a or t4[j + 1] - t4[j] != FOUR_H:
            continue
        body = c4[j + 1] - o4[j + 1]
        if body >= IMPULSE * a and c4[j + 1] > h4[j]:
            out.append((1, t4[j + 1] + FOUR_H, float(l4[j]), float(h4[j])))
        elif -body >= IMPULSE * a and c4[j + 1] < l4[j]:
            out.append((-1, t4[j + 1] + FOUR_H, float(l4[j]), float(h4[j])))
    return out


def zone_cover(t, h, l, c, zs):
    """Per 1h bar, the most recently created LIVE zone of each side: {side: dict(ok, lo, hi)} (arrays of length n).
    live at bar i  <=>  created at or before bar i's start, the zone was first touched at f <= i <= f + RETEST_H, and no 1h close from f through i went beyond the far edge.
    Everything about bar i uses bars <= i."""
    n = len(c)
    res = {s: dict(ok=np.zeros(n, bool), lo=np.full(n, np.nan), hi=np.full(n, np.nan)) for s in (1, -1)}
    for side, created, zlo, zhi in sorted(zs, key=lambda z: z[1]):
        i0 = int(np.searchsorted(t, created))
        if i0 >= n:
            continue
        end = min(n, i0 + ZONE_LIFE_H)
        touch = np.flatnonzero(l[i0:end] <= zhi) if side > 0 else np.flatnonzero(h[i0:end] >= zlo)
        if len(touch) == 0:
            continue
        f = i0 + int(touch[0])
        last = min(n, f + RETEST_H + 1)
        seg = c[f:last]
        brk = np.flatnonzero(seg < zlo) if side > 0 else np.flatnonzero(seg > zhi)
        stop = last if len(brk) == 0 else f + int(brk[0])
        if stop <= f:
            continue
        r = res[side]
        r["ok"][f:stop], r["lo"][f:stop], r["hi"][f:stop] = True, zlo, zhi
    return res


def daily_trend(t, c):
    """Per 1h bar: the previous COMPLETED UTC day's close / its 50-day mean - 1 (NaN until 50 complete consecutive days)."""
    ts = pd.DatetimeIndex(t)
    day = ts.floor("D")
    s = pd.Series(np.asarray(c, float), index=ts)
    g = s.groupby(day)
    last = g.last().where(g.size() == 24)
    last = last.reindex(pd.date_range(last.index.min(), last.index.max(), freq="D"))
    tr = (last / last.rolling(DAILY_SMA).mean() - 1).shift(1)
    return tr.reindex(day).to_numpy(float)


# ------------------------------------------------------------------ the R trade

def trade_r(i, side, stop, o, h, l, c, fc):
    """In at o[i+1]; stop first inside a bar (gap-aware); target = entry +/- R_TARGET x risk; else the close HOLD_R bars on. Returns dict(net, gross, rf, hit) or None
    (stop on the wrong side of the entry). net / gross are fractions of the entry price (fee and funding charged); rf = the risk as a fraction of the entry."""
    n = len(c)
    e = o[i + 1]
    if side > 0 and stop >= e or side < 0 and stop <= e:
        return None
    rf = abs(e - stop) / e
    tp = e * (1 + side * R_TARGET * rf)
    j_end = min(i + HOLD_R, n - 1)
    for j in range(i + 1, j_end + 1):
        if (l[j] <= stop) if side > 0 else (h[j] >= stop):
            x = min(o[j], stop) if side > 0 else max(o[j], stop)
            g = side * (x / e - 1) - side * (fc[j] - fc[i + 1]) / e
            return dict(net=g - FEE, gross=g, rf=rf, hit=False)
        if (h[j] >= tp) if side > 0 else (l[j] <= tp):
            g = R_TARGET * rf - side * (fc[j] - fc[i + 1]) / e
            return dict(net=g - FEE, gross=g, rf=rf, hit=True)
    g = side * (c[j_end] / e - 1) - side * (fc[j_end] - fc[i + 1]) / e
    return dict(net=g - FEE, gross=g, rf=rf, hit=False)


NAN = float("nan")


def trend_agrees(side, v):
    """The daily trend points the sweep's way: long wants the previous day above its 50-day mean, short wants it below. Unknown (NaN) is no."""
    return bool(np.isfinite(v) and side * v > 0)


def coin_events(t, o, h, l, c, q, rate, fc, elig, pools, ym, rng):
    """All kept sweep events of one coin with their zone / trend flags, three trades and their controls. `pools[month]` = candidate control hours (already causal-safe)."""
    n = len(c)
    F = sc.features(t, o, h, l, c, q, rate)
    atr = atr1h(h, l, c)
    zs = zones(*bars4h(t, o, h, l, c))
    cov = zone_cover(t, h, l, c, zs)
    dt = daily_trend(t, c)
    day = pd.DatetimeIndex(t).floor("D")
    rows = []
    for side in (1, -1):
        f, last = F[side], -10 ** 9
        z, zo = cov[side], cov[-side]
        for i in np.flatnonzero(f["ev"] & elig):
            if i - last < COOL or i + HOLD_R + 2 >= n or not np.isfinite(atr[i]):
                continue
            ext, a = float(f["extreme"][i]), float(atr[i])
            r24 = sc.trade(i, side, ext, None, o, h, l, c, fc)
            stop_a = ext - side * PAD * a
            ra = trade_r(i, side, stop_a, o, h, l, c, fc)
            if r24 is None or ra is None:
                continue
            last = i
            zoned = bool(z["ok"][i] and ((l[i] <= z["hi"][i]) if side > 0 else (h[i] >= z["lo"][i])))
            opp = bool(zo["ok"][i] and ((h[i] >= zo["lo"][i]) if side > 0 else (l[i] <= zo["hi"][i])))
            rz = None
            if zoned:
                far = z["lo"][i] if side > 0 else z["hi"][i]
                stop_z = (min(ext, far) if side > 0 else max(ext, far)) - side * PAD * a
                rz = trade_r(i, side, stop_z, o, h, l, c, fc)
            pool = pools[ym[i]]
            k = int(rng.choice(pool))
            e_k = o[k + 1]
            k24 = sc.trade(k, side, c[k] * (1 - side * abs(ext / c[i] - 1)), None, o, h, l, c, fc)
            ka = trade_r(k, side, e_k * (1 - side * ra["rf"]), o, h, l, c, fc)
            kz = trade_r(k, side, e_k * (1 - side * rz["rf"]), o, h, l, c, fc) if rz else None
            if k24 is None or ka is None:
                continue
            dtv = dt[i]
            rows.append(dict(t_in=t[i + 1], day=day[i + 1], side=side, zoned=zoned, opp=opp,
                             trend_ok=trend_agrees(side, dtv), trend_known=bool(np.isfinite(dtv)),
                             net24=r24[0], gross24=r24[1], ctrl24=k24[0],
                             rf_a=ra["rf"], net_a=ra["net"], gross_a=ra["gross"], hit_a=ra["hit"], ctrl_a=ka["net"], ctrl_hit_a=ka["hit"],
                             rf_z=rz["rf"] if rz else NAN, net_z=rz["net"] if rz else NAN, gross_z=rz["gross"] if rz else NAN,
                             hit_z=rz["hit"] if rz else False, ctrl_z=kz["net"] if kz else NAN, ctrl_hit_z=kz["hit"] if kz else False))
    return rows


def build_events() -> pd.DataFrame:
    rng = np.random.default_rng(0)
    H = pl.hourly_all()
    el = pl.universe()
    out = []
    for s, hh in H.items():
        t = hh.time.to_numpy("datetime64[ns]")
        o, h, l, c, q = (hh[k].to_numpy(float) for k in ("open", "high", "low", "close", "qvol"))
        n = len(c)
        if n < 400 or not el[s]:
            continue
        ym = pd.DatetimeIndex(t).strftime("%Y-%m").to_numpy()
        elig = np.array([m in el[s] for m in ym])
        by_month = pd.Series(np.arange(n)).groupby(ym).apply(lambda x: x.to_numpy())
        pools = {m: v[(v > TREND_WARM) & (v + HOLD_R + 2 < n)] for m, v in by_month.items()}
        pools = {m: v for m, v in pools.items() if len(v)}
        fc = funding_cum(s, t, hh)
        rows = coin_events(t, o, h, l, c, q, sc.last_rate(s, t), fc, elig & np.array([m in pools for m in ym]), pools, ym, rng)
        for r in rows:
            r["coin"] = s
        out += rows
    return pd.DataFrame(out)


# ------------------------------------------------------------------ the statistics (day-clustered, as in sweep_confluence)

def r_of(T, net, rf):
    return T[net] / T[rf]


def cell_r(x, net, ctrl, rf, hit, ctrl_hit):
    """One line: n, net R per trade (day-clustered t), gross R, hit rate vs the control's, excess over the control in R (t)."""
    if len(x) == 0:
        return "n 0"
    R, C = x[net] / x[rf], x[ctrl] / x[rf]
    ex = R - C
    return (f"n {len(x)}, net {R.mean():+.2f}R (t {sc.t_by_day(R, x.day):+.1f}), gross {(x[net.replace('net', 'gross')] / x[rf]).mean():+.2f}R, "
            f"hit {x[hit].mean() * 100:.0f}% vs control {x[ctrl_hit].mean() * 100:.0f}%, excess {ex.mean():+.2f}R (t {sc.t_by_day(ex, x.day):+.1f})")


def arm_frames(T):
    """The arm -> (frame, trade columns). A: every sweep, TR-A. B: zoned, TR-Z. C: zoned and the daily trend agrees, TR-Z. Rows with no valid zone trade are dropped for B and C."""
    A = T
    Z = T[T.zoned & T.net_z.notna() & T.ctrl_z.notna()]
    B = Z
    Cc = Z[Z.trend_ok]
    return {"A": (A, "net_a", "ctrl_a", "rf_a", "hit_a", "ctrl_hit_a"),
            "B": (B, "net_z", "ctrl_z", "rf_z", "hit_z", "ctrl_hit_z"),
            "C": (Cc, "net_z", "ctrl_z", "rf_z", "hit_z", "ctrl_hit_z")}


def info_spread(T, flag_col, sub=None):
    """Spread (flagged minus unflagged) of net24, day-clustered t, per side and half. `sub` restricts the frame first (e.g. to zoned events)."""
    out = {}
    for side in (1, -1):
        g = T[T.side == side] if sub is None else T[(T.side == side) & sub]
        for half, m in (("tune", g.t_in < HOLDOUT), ("hold", g.t_in >= HOLDOUT)):
            x = g[m]
            if len(x) < 30 or x[flag_col].nunique() < 2:
                out[side, half] = (NAN, NAN, int(x[flag_col].sum()), len(x))
                continue
            b, tt = sc.spread_t(x.net24.to_numpy(), x[flag_col].to_numpy(), x.day.to_numpy())
            out[side, half] = (b, tt, int(x[flag_col].sum()), len(x))
    return out


def report(T: pd.DataFrame) -> str:
    L = []
    P = L.append
    yrs = (T.t_in.max() - T.t_in.min()).days / 365.25
    tune, hold = T.t_in < HOLDOUT, T.t_in >= HOLDOUT
    P(f"backtest/sweep_zone.py, {pd.Timestamp.now():%Y-%m-%d %H:%M}; PIT top-40 1h, 24-bar sweep + 4h supply/demand zone (1.5 ATR impulse, 1.0 ATR base, first retest + 24h) + "
      f"daily 50-day trend; 12bp + funding; halves split {HOLDOUT.date()}")
    P(f"sweeps {len(T)} ({int((T.side == 1).sum())} long / {int((T.side == -1).sum())} short), {T.coin.nunique()} coins, {T.t_in.min().date()} .. {T.t_in.max().date()}")
    n_z, n_zt = int(T.zoned.sum()), int((T.zoned & T.trend_ok).sum())
    P(f"FUNNEL: zoned {n_z} ({n_z / len(T) * 100:.1f}% of sweeps, {n_z / yrs:.0f} a year); zoned + daily trend agrees {n_zt} ({n_zt / max(n_z, 1) * 100:.0f}% of zoned, {n_zt / yrs:.0f} a year); "
      f"opposite-zone sweeps {int(T.opp.sum())}; zoned without a valid zone trade {int((T.zoned & T.net_z.isna()).sum())}")
    P(f"        zoned share by side: long {T[T.side == 1].zoned.mean() * 100:.1f}%, short {T[T.side == -1].zoned.mean() * 100:.1f}%; "
      f"by half: tune {T[tune].zoned.mean() * 100:.1f}%, holdout {T[hold].zoned.mean() * 100:.1f}%")
    arms = arm_frames(T)
    P("\nTHE THREE ARMS on their own trade (A: sweep stop, 3R, 72h; B and C: zone stop, 3R, 72h); net of 12bp + funding, in R")
    cells, pv = {}, {}
    for arm, (F_, net, ctrl, rf, hit, ch) in arms.items():
        for side, nm in ((1, "LONG "), (-1, "SHORT")):
            for half, m in (("tune", F_.t_in < HOLDOUT), ("hold", F_.t_in >= HOLDOUT)):
                x = F_[(F_.side == side) & m]
                P(f"  {arm} {nm} {half:5s} {cell_r(x, net, ctrl, rf, hit, ch)}")
                R, C = x[net] / x[rf], x[ctrl] / x[rf]
                cells[arm, side, half] = dict(n=len(x), net=float(R.mean()) if len(x) else NAN, t=sc.t_by_day(R, x.day) if len(x) else NAN,
                                              ex=float((R - C).mean()) if len(x) else NAN)
            pv[arm, side] = sc.p_one_sided(cells[arm, side, "hold"]["t"]) if np.isfinite(cells[arm, side, "hold"]["t"]) else 1.0
    P("\nDIAGNOSTIC - B and C on arm A's own trade (same sweep stop, so the zone's effect is not mixed with a wider stop), in R")
    for arm, sub in (("B", T.zoned), ("C", T.zoned & T.trend_ok)):
        for side, nm in ((1, "LONG "), (-1, "SHORT")):
            for half, m in (("tune", tune), ("hold", hold)):
                x = T[sub & (T.side == side) & m]
                P(f"  {arm}-on-A {nm} {half:5s} {cell_r(x, 'net_a', 'ctrl_a', 'rf_a', 'hit_a', 'ctrl_hit_a')}")
    P("\nINFORMATION TEST on T24 (the sweep_confluence trade: stop = sweep extreme, out 24 bars on), net % per trade: flagged minus unflagged, day-clustered t")
    info_b = info_spread(T, "zoned")
    info_c = info_spread(T, "trend_ok", sub=T.zoned)
    for nm_, info, what in (("B: zoned - unzoned", info_b, "zoned"), ("C: trend-agrees - not, inside zoned", info_c, "trend-agrees")):
        for side, sn in ((1, "LONG "), (-1, "SHORT")):
            tu, ho = info[side, "tune"], info[side, "hold"]
            P(f"  {nm_:36s} {sn} tune spread {tu[0] * 100:+.2f}% (t {tu[1]:+.1f}, {tu[2]} of {tu[3]}) | holdout {ho[0] * 100:+.2f}% (t {ho[1]:+.1f}, {ho[2]} of {ho[3]})")
    P("\nOPPOSITE-ZONE PLACEBO on T24: sweeps inside a live zone of the OPPOSITE type (a long sweep in a supply zone, a short sweep in a demand zone) vs the matching-zone sweeps")
    for side, sn in ((1, "LONG "), (-1, "SHORT")):
        for half, m in (("tune", tune), ("hold", hold)):
            a_ = T[T.opp & (T.side == side) & m]
            b_ = T[T.zoned & (T.side == side) & m]
            u_ = T[~T.zoned & ~T.opp & (T.side == side) & m]
            P(f"  {sn} {half:5s} opposite-zone n {len(a_)} net24 {a_.net24.mean() * 100:+.2f}% | matching-zone n {len(b_)} net24 {b_.net24.mean() * 100:+.2f}% | no zone n {len(u_)} net24 {u_.net24.mean() * 100:+.2f}%")
    # ---- the gate
    hp = sc.holm(pv)
    P("\nGATE (net R > 0 on both halves; holdout Holm p < 0.05 over the 6 cells; excess over control > 0 on both halves; >= 100 holdout trades; B and C: the information test > 0 on both halves)")
    passed = []
    for arm in ("A", "B", "C"):
        for side, sn in ((1, "LONG "), (-1, "SHORT")):
            tu, ho = cells[arm, side, "tune"], cells[arm, side, "hold"]
            info_ok = True
            if arm == "B":
                info_ok = info_b[side, "tune"][0] > 0 and info_b[side, "hold"][0] > 0
            if arm == "C":
                info_ok = info_b[side, "tune"][0] > 0 and info_b[side, "hold"][0] > 0 and info_c[side, "tune"][0] > 0 and info_c[side, "hold"][0] > 0
            ok = (tu["net"] > 0 and ho["net"] > 0 and hp[arm, side] < 0.05 and tu["ex"] > 0 and ho["ex"] > 0 and ho["n"] >= MIN_HOLD_TRADES and info_ok)
            if ok:
                passed.append((arm, side))
            P(f"  {arm} {sn}: tune net {tu['net']:+.2f}R (n {tu['n']}), holdout net {ho['net']:+.2f}R (t {ho['t']:+.1f}, n {ho['n']}, {ho['n'] / yrs:.0f} a year), "
              f"excess {tu['ex']:+.2f}R / {ho['ex']:+.2f}R, Holm p {hp[arm, side]:.2f}, information {'ok' if info_ok else 'no'}  ->  {'PASS' if ok else 'no'}")
    P(f"  cells passing: {len(passed)} of 6  {passed}")
    return "\n".join(L)


def main():
    if "--refit" in sys.argv or not CACHE.exists():
        T = build_events()
        T.to_pickle(CACHE)
    else:
        T = pd.read_pickle(CACHE)
    txt = report(T)
    print(txt)
    LOG.write_text(txt + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
