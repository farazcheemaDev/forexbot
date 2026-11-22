"""LIQUIDITY SWEEP + DAILY SUPPLY / DEMAND ZONE + DAILY TREND, with the TARGET AT THE NEXT ZONE (2026-11-08) - the second try after sweep_zone.py

THE USER (2026-11-08): after sweep_zone.py found nothing with 4h zones ("0 of 6; one zone definition, not 'impossible'"), "try the daily zones version". My suggestion, accepted:
daily zones with a target at the next zone, the shape the zone traders actually use. sweep_zone.py is NOT edited; this is a new file with its own rules and its own tests.

WHAT IS ALREADY KNOWN: sweep_zone.py (4h zones, first retest within 24h, 3R target): the zone added nothing on the plain sweep trade (long holdout -0.38%, t -2.1), 0 of 6 gate
  cells; sweep_confluence.py: 0 of 14 factors; the desk's SR bounce 22% hit. This is a second look at the same idea, so the prior that it passes is LOWER than for the first (4%).

THE EVENT = the desk's 24-bar sweep + reclaim, imported unchanged from sweep_confluence.features, PIT top-40, 1h bars 2020-2026, declustered (12 bars). The same entry: in at the next open.
THE ZONE (daily bars built from the 1h bars, UTC days, only complete days; every number fixed here and none tuned):
  base day j: range <= 1.0 x ATR14(daily, through day j); impulse day j+1 right after it: DEMAND = body >= +1.5 x ATR14(j) and close above the base's high; SUPPLY mirrors.
  Zone = [low_j, high_j], known when the impulse day CLOSES. Live from creation until the first 1h bar that trades into it (the FIRST RETEST), then for 72 hours (3 days), unless a 1h
  close goes beyond the far edge (broken). Never retested within 180 days (4,320 hours): dead. An event is ZONED when a live zone of its own side exists at the signal bar and the
  signal bar's wick is in it (long: low <= zone high; short: high >= zone low). Several live zones: the most recently created.
THE TREND: previous completed UTC day's close / its 50-day mean - 1 (sweep_zone.daily_trend). Long wants > 0, short < 0.
THE NEXT-ZONE TARGET: at the signal bar, the nearest UNBROKEN zone of the OPPOSITE type beyond the entry price (long: the lowest supply-zone LOW above the entry; short: the highest
  demand-zone HIGH below it), created at or before the signal bar, not older than 360 days (8,640 hours), 'unbroken' = no 1h close beyond its far edge since it was created. The
  trade is taken only if the target is at least 1.5 x the risk away (the desk's own 1.5R floor); otherwise the sweep is zoned but has NO target trade (counted in the funnel).
THE TRADES (in at the NEXT bar's open, stop first inside a bar, gap-aware, 12bp round trip + funding, the same funding code as sweep_confluence), hold at most 240 bars (10 days):
  T24  the sweep_confluence trade (stop = sweep extreme, no target, out 24 bars on) - for the INFORMATION test only.
  A    every sweep: stop = sweep extreme -/+ 0.25 ATR14(1h), target 3 x the risk.
  B    zoned sweeps with a next-zone target: stop beyond the zone's far edge or the sweep extreme (whichever is further) -/+ 0.25 ATR14(1h), target = the next zone's near edge.
  C    B with the daily trend agreeing.
  Z3   (diagnostic) zoned sweeps with the zone stop and a plain 3R target, so the target choice is separate from the stop.
THE CONTROL (per event, per trade): a random hour of the same coin and month, the SAME stop distance and the SAME target multiple of the risk (B: the event's own reward:risk), the same
  exits. Excess = event - control. t by distinct DAY, halves split 2024-04-07.
GATE: unchanged from sweep_zone.py: per arm x side (6 cells, Holm over them on the holdout) PASS = net R > 0 on BOTH halves, holdout one-sided Holm p < 0.05, excess over the control > 0
  on both halves, >= 100 holdout trades, and for B and C the information test (zoned - unzoned on T24; for C, trend-agrees - not inside zoned) > 0 on both halves. A cell with fewer
  than 100 holdout trades is reported UNDERPOWERED: that is not a rejection of the idea. A pass would be a CANDIDATE for a forward paper record in the Analyst desk, not a deployment.

REGISTERED BEFORE THE FIRST RUN (2026-11-08; prior that any cell passes: 4%)
  D1  Arm A (every sweep, 3R, 10 days) loses after fees on both halves for both sides: 85%.
  D2  The daily zone adds no information on T24: |zoned - unzoned| < 0.30% with |t| < 2 on the holdout for both sides: 75%.
  D3  Arm B has net R < 0 on the holdout for at least one side: 90%.
  D4  Zoned sweeps are 0.5-3% of all sweeps (daily zones are rarer than the 4h zones' 3.8%): 75%. A next-zone target of at least 1.5R exists for 20-60% of the zoned sweeps: 65%.
  D5  B's hit rate is not above its control's by more than 5 points in any cell: 75%.
  D6  The next-zone target is not the point: B and Z3 differ by less than 0.15R on the holdout in each side: 60%.
  D7  Some of the six cells are UNDERPOWERED (< 100 holdout trades): 70% (arm C most likely).
  D8  No cell passes the gate: 96%.

RESULT (2026-11-08, logs/sweep_zone_daily.txt; 60,390 sweeps, 359 PIT coins, 2020-02 .. 2026-09): NO CELL PASSES THE GATE (0 of 6), and the four zone cells are UNDERPOWERED, so this is
  'cannot tell' for the zone arms, not a clean rejection. Funnel: zoned 726 (1.20% of sweeps, 110 a year); with a next-zone target >= 1.5R 286 (39% of zoned, 43 a year); with the daily trend
  agreeing 130 (20 a year). The median next-zone target is 7.3 x the risk away, so it is rarely reached (hit 0-16%).
  Arm A (every sweep, 3R, 10 days) loses again: net R tune / holdout long -0.11 / -0.20, short -0.06 / -0.06, no excess over the control.
  Arm B (zoned, zone stop, next-zone target), tune / holdout: long -0.31 (n 75) / -0.10 (n 68); short +0.21 (n 94) / +0.26 (n 49); all |t| <= 1.9. Arm C (+ trend): long +0.12 / +0.27 (n 25 / 31),
    short +0.52 / +0.37 (n 38 / 36), all |t| <= 1.3, excess over the control +0.13..+0.43 except C short tune -0.45. Holdout cells have 31-68 trades: a standard error of about 0.3-0.5R.
  Information test (T24, zoned - unzoned): +0.47% / +0.16% long, +0.25% / +0.38% short (t <= 1.0): positive on all four halves, not significant. Trend inside zones: long +1.97% (t +2.6) tune,
    -0.01% holdout (a flip); short +0.58% / +0.09%.
  Diagnostic Z3 (zone stop, plain 3R): long -0.12 / -0.13R, short +0.04 / +0.29R (holdout excess +0.64R, t +2.8, n 93): one cell of about 16 diagnostics, not a finding.
  Predictions: D1 right. D2 half wrong (short holdout spread +0.38%, above the +-0.30% band; t +0.9 so still not significant). D3 right (B long holdout -0.10R). D4 right (1.20%; 39%).
    D5 WRONG (C long tune hit 16% vs control 4%, on 25 trades). D6 right (B and Z3 within 0.03R on the holdout, both sides: the target choice is not the point). D7 right, and larger than
    expected (all four B and C cells under 100 holdout trades, not just C). D8 right.
  LIMITS: only 43 zoned sweeps with a target a year across the whole 40-coin universe: to reach 100 holdout trades a side would take ~4 more years of data, and 30 independent bets ~9+ months of live
    paper. One daily zone definition (one base day, first retest within 72h, 360-day target zones); one trend rule; targets at the next zone are far (median 7.3R). An edge under about +0.7R a
    trade could not have been seen. Stated as: not found, and not testable with the data there is.

    python -m backtest.sweep_zone_daily            run (caches the event table in logs/sweep_zone_daily_events.pkl)
    python -m backtest.sweep_zone_daily --refit    rebuild the event table
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
from backtest import sweep_zone as z4  # noqa: E402
from backtest.capitulation_wide import funding_cum  # noqa: E402

LOG = ROOT / "logs" / "sweep_zone_daily.txt"
CACHE = ROOT / "logs" / "sweep_zone_daily_events.pkl"
HOLDOUT = pl.HOLDOUT
FEE = 0.0012
ATR_N = 14
IMPULSE, BASE_MAX = 1.5, 1.0
ZONE_LIFE_H, RETEST_H, TARGET_LIFE_H = 4320, 72, 8640
PAD = 0.25
R3, MIN_RR, HOLD, COOL = 3.0, 1.5, 240, 12
MIN_HOLD_TRADES = 100
TREND_WARM = 168
ONE_D = np.timedelta64(1, "D")
NAN = float("nan")


# ------------------------------------------------------------------ daily bars, zones, live window, targets (each reads only what is known at its timestamp)

def bars1d(t, o, h, l, c):
    """Daily bars (UTC days) from 1h arrays, only days with all 24 hours present. Returns (start, o, h, l, c)."""
    df = pd.DataFrame({"k": pd.DatetimeIndex(t).floor("D"), "o": o, "h": h, "l": l, "c": c})
    g = df.groupby("k", sort=True)
    cnt = g.size()
    a = pd.DataFrame({"o": g["o"].first(), "h": g["h"].max(), "l": g["l"].min(), "c": g["c"].last()})
    a = a[cnt == 24]
    return a.index.to_numpy("datetime64[ns]"), a.o.to_numpy(float), a.h.to_numpy(float), a.l.to_numpy(float), a.c.to_numpy(float)


def zones(td, od, hd, ld, cd):
    """Daily supply / demand zones: a list of (side, created, lo, hi); created = the END of the impulse day; side +1 demand, -1 supply."""
    n = len(cd)
    if n < ATR_N + 2:
        return []
    atr = z4.atr1h(hd, ld, cd)
    out = []
    for j in range(ATR_N, n - 1):
        a = atr[j]
        if not np.isfinite(a) or a <= 0 or hd[j] - ld[j] > BASE_MAX * a or td[j + 1] - td[j] != ONE_D:
            continue
        body = cd[j + 1] - od[j + 1]
        if body >= IMPULSE * a and cd[j + 1] > hd[j]:
            out.append((1, td[j + 1] + ONE_D, float(ld[j]), float(hd[j])))
        elif -body >= IMPULSE * a and cd[j + 1] < ld[j]:
            out.append((-1, td[j + 1] + ONE_D, float(ld[j]), float(hd[j])))
    return out


def zone_cover(t, h, l, c, zs):
    """Per 1h bar, the most recently created LIVE zone of each side: {side: dict(ok, lo, hi)}.
    live at bar i <=> created at or before bar i's start, first touched at f <= i <= f + RETEST_H, no 1h close from f through i beyond the far edge.
    The first touch must come within ZONE_LIFE_H hours of creation. Everything about bar i uses bars <= i."""
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


def zone_index(t, c, zs):
    """Every zone as (side, i0, lo, hi, brk): i0 = the first 1h bar at or after creation; brk = the first 1h index >= i0 whose close is beyond the far edge
    (demand: under lo; supply: over hi), searched over the zone's first TARGET_LIFE_H hours, else n (never broken)."""
    n = len(c)
    out = []
    for side, created, zlo, zhi in zs:
        i0 = int(np.searchsorted(t, created))
        if i0 >= n:
            continue
        seg = c[i0:i0 + TARGET_LIFE_H + 1]
        brk = np.flatnonzero(seg < zlo) if side > 0 else np.flatnonzero(seg > zhi)
        out.append((side, i0, zlo, zhi, i0 + int(brk[0]) if len(brk) else n))
    return out


def next_zone_target(i, side, e, zi):
    """The near edge of the nearest UNBROKEN zone of the OPPOSITE type beyond the entry price e, as known at signal bar i:
    long -> the lowest supply-zone low above e; short -> the highest demand-zone high below e. None if there is none."""
    best = None
    for s, i0, zlo, zhi, brk in zi:
        if s != -side or i0 > i or brk <= i or i - i0 > TARGET_LIFE_H:
            continue
        if side > 0 and zlo > e:
            cand, better = zlo, best is None or zlo < best
        elif side < 0 and zhi < e:
            cand, better = zhi, best is None or zhi > best
        else:
            continue
        if better:
            best = cand
    return best


# ------------------------------------------------------------------ the trade with an explicit target price

def tp_at(e, stop, m, side):
    """The target price m x the risk away from the entry."""
    return e + side * m * abs(e - stop)


def trade_rm(i, side, stop, tp, o, h, l, c, fc, hold=HOLD):
    """In at o[i+1]; stop first inside a bar (gap-aware); target tp (a price); else the close `hold` bars on. Returns dict(net, gross, rf, rr, hit) or None
    (stop or target on the wrong side of the entry). net / gross are fractions of the entry price; rf = the risk as a fraction of the entry; rr = reward / risk."""
    n = len(c)
    e = o[i + 1]
    if side > 0 and stop >= e or side < 0 and stop <= e or side > 0 and tp <= e or side < 0 and tp >= e:
        return None
    rf, rr = abs(e - stop) / e, abs(tp - e) / abs(e - stop)
    j_end = min(i + hold, n - 1)
    for j in range(i + 1, j_end + 1):
        if (l[j] <= stop) if side > 0 else (h[j] >= stop):
            x = min(o[j], stop) if side > 0 else max(o[j], stop)
            g = side * (x / e - 1) - side * (fc[j] - fc[i + 1]) / e
            return dict(net=g - FEE, gross=g, rf=rf, rr=rr, hit=False)
        if (h[j] >= tp) if side > 0 else (l[j] <= tp):
            g = side * (tp / e - 1) - side * (fc[j] - fc[i + 1]) / e
            return dict(net=g - FEE, gross=g, rf=rf, rr=rr, hit=True)
    g = side * (c[j_end] / e - 1) - side * (fc[j_end] - fc[i + 1]) / e
    return dict(net=g - FEE, gross=g, rf=rf, rr=rr, hit=False)


def coin_events(t, o, h, l, c, q, rate, fc, elig, pools, ym, rng):
    """All kept sweep events of one coin with zone / trend flags, the trades A, Z3 and B and their controls. `pools[month]` = candidate control hours."""
    n = len(c)
    F = sc.features(t, o, h, l, c, q, rate)
    atr = z4.atr1h(h, l, c)
    zs = zones(*bars1d(t, o, h, l, c))
    cov = zone_cover(t, h, l, c, zs)
    zi = zone_index(t, c, zs)
    dt = z4.daily_trend(t, c)
    day = pd.DatetimeIndex(t).floor("D")
    rows = []
    for side in (1, -1):
        f, last = F[side], -10 ** 9
        z, zo = cov[side], cov[-side]
        for i in np.flatnonzero(f["ev"] & elig):
            if i - last < COOL or i + HOLD + 2 >= n or not np.isfinite(atr[i]):
                continue
            ext, a, e = float(f["extreme"][i]), float(atr[i]), float(o[i + 1])
            r24 = sc.trade(i, side, ext, None, o, h, l, c, fc)
            stop_a = ext - side * PAD * a
            ra = trade_rm(i, side, stop_a, tp_at(e, stop_a, R3, side), o, h, l, c, fc)
            if r24 is None or ra is None:
                continue
            last = i
            zoned = bool(z["ok"][i] and ((l[i] <= z["hi"][i]) if side > 0 else (h[i] >= z["lo"][i])))
            opp = bool(zo["ok"][i] and ((h[i] >= zo["lo"][i]) if side > 0 else (l[i] <= zo["hi"][i])))
            r3 = rb = None
            tgt = None
            if zoned:
                far = z["lo"][i] if side > 0 else z["hi"][i]
                stop_z = (min(ext, far) if side > 0 else max(ext, far)) - side * PAD * a
                r3 = trade_rm(i, side, stop_z, tp_at(e, stop_z, R3, side), o, h, l, c, fc)
                tgt = next_zone_target(i, side, e, zi)
                if tgt is not None and (e - stop_z) * side > 0 and abs(tgt - e) / abs(e - stop_z) >= MIN_RR:
                    rb = trade_rm(i, side, stop_z, tgt, o, h, l, c, fc)
            k = int(rng.choice(pools[ym[i]]))
            e_k = float(o[k + 1])
            k24 = sc.trade(k, side, c[k] * (1 - side * abs(ext / c[i] - 1)), None, o, h, l, c, fc)
            ka = trade_rm(k, side, e_k * (1 - side * ra["rf"]), tp_at(e_k, e_k * (1 - side * ra["rf"]), R3, side), o, h, l, c, fc)
            k3 = trade_rm(k, side, e_k * (1 - side * r3["rf"]), tp_at(e_k, e_k * (1 - side * r3["rf"]), R3, side), o, h, l, c, fc) if r3 else None
            kb = trade_rm(k, side, e_k * (1 - side * rb["rf"]), tp_at(e_k, e_k * (1 - side * rb["rf"]), rb["rr"], side), o, h, l, c, fc) if rb else None
            if k24 is None or ka is None:
                continue
            dtv = dt[i]
            rows.append(dict(t_in=t[i + 1], day=day[i + 1], side=side, zoned=zoned, opp=opp,
                             trend_ok=z4.trend_agrees(side, dtv), trend_known=bool(np.isfinite(dtv)),
                             net24=r24[0], gross24=r24[1], ctrl24=k24[0],
                             rf_a=ra["rf"], net_a=ra["net"], gross_a=ra["gross"], hit_a=ra["hit"], ctrl_a=ka["net"], ctrl_hit_a=ka["hit"],
                             rf_3=r3["rf"] if r3 else NAN, net_3=r3["net"] if r3 else NAN, gross_3=r3["gross"] if r3 else NAN, hit_3=r3["hit"] if r3 else False,
                             ctrl_3=k3["net"] if k3 else NAN, ctrl_hit_3=k3["hit"] if k3 else False,
                             has_target=bool(rb), rr_b=rb["rr"] if rb else NAN,
                             rf_b=rb["rf"] if rb else NAN, net_b=rb["net"] if rb else NAN, gross_b=rb["gross"] if rb else NAN, hit_b=rb["hit"] if rb else False,
                             ctrl_b=kb["net"] if kb else NAN, ctrl_hit_b=kb["hit"] if kb else False))
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
        pools = {m: v[(v > TREND_WARM) & (v + HOLD + 2 < n)] for m, v in by_month.items()}
        pools = {m: v for m, v in pools.items() if len(v)}
        fc = funding_cum(s, t, hh)
        rows = coin_events(t, o, h, l, c, q, sc.last_rate(s, t), fc, elig & np.array([m in pools for m in ym]), pools, ym, rng)
        for r in rows:
            r["coin"] = s
        out += rows
    return pd.DataFrame(out)


# ------------------------------------------------------------------ the statistics (day-clustered, as in sweep_confluence / sweep_zone)

def cell_r(x, net, ctrl, rf, hit, ctrl_hit):
    """n, net R per trade (day-clustered t), gross R, hit rate vs the control's, excess over the control in R (t)."""
    if len(x) == 0:
        return "n 0"
    R, C = x[net] / x[rf], x[ctrl] / x[rf]
    ex = R - C
    return (f"n {len(x)}, net {R.mean():+.2f}R (t {sc.t_by_day(R, x.day):+.1f}), gross {(x[net.replace('net', 'gross')] / x[rf]).mean():+.2f}R, "
            f"hit {x[hit].mean() * 100:.0f}% vs control {x[ctrl_hit].mean() * 100:.0f}%, excess {ex.mean():+.2f}R (t {sc.t_by_day(ex, x.day):+.1f})")


def arm_frames(T):
    """A: every sweep (sweep stop, 3R). B: zoned sweeps with a next-zone target of >= 1.5R. C: B with the daily trend agreeing."""
    B = T[T.zoned & T.has_target & T.net_b.notna() & T.ctrl_b.notna()]
    return {"A": (T, "net_a", "ctrl_a", "rf_a", "hit_a", "ctrl_hit_a"),
            "B": (B, "net_b", "ctrl_b", "rf_b", "hit_b", "ctrl_hit_b"),
            "C": (B[B.trend_ok], "net_b", "ctrl_b", "rf_b", "hit_b", "ctrl_hit_b")}


def report(T: pd.DataFrame) -> str:
    L = []
    P = L.append
    yrs = (T.t_in.max() - T.t_in.min()).days / 365.25
    tune, hold = T.t_in < HOLDOUT, T.t_in >= HOLDOUT
    P(f"backtest/sweep_zone_daily.py, {pd.Timestamp.now():%Y-%m-%d %H:%M}; PIT top-40 1h, 24-bar sweep + DAILY supply/demand zone (1.5 ATR impulse, 1.0 ATR base, first retest + 72h) + "
      f"daily 50-day trend; target at the next opposite zone (>= 1.5R); hold <= 240 bars; 12bp + funding; halves split {HOLDOUT.date()}")
    P(f"sweeps {len(T)} ({int((T.side == 1).sum())} long / {int((T.side == -1).sum())} short), {T.coin.nunique()} coins, {T.t_in.min().date()} .. {T.t_in.max().date()}")
    nz, nt, nc = int(T.zoned.sum()), int((T.zoned & T.has_target).sum()), int((T.zoned & T.has_target & T.trend_ok).sum())
    P(f"FUNNEL: zoned {nz} ({nz / len(T) * 100:.2f}% of sweeps, {nz / yrs:.0f} a year); with a next-zone target of >= 1.5R {nt} ({nt / max(nz, 1) * 100:.0f}% of zoned, {nt / yrs:.0f} a year); "
      f"and the daily trend agrees {nc} ({nc / yrs:.0f} a year); opposite-zone sweeps {int(T.opp.sum())}")
    P(f"        zoned share by side: long {T[T.side == 1].zoned.mean() * 100:.2f}%, short {T[T.side == -1].zoned.mean() * 100:.2f}%; by half: tune {T[tune].zoned.mean() * 100:.2f}%, "
      f"holdout {T[hold].zoned.mean() * 100:.2f}%; median reward:risk of the next-zone target {T[T.has_target].rr_b.median():.2f}")
    arms = arm_frames(T)
    P("\nTHE THREE ARMS on their own trade (A: sweep stop, 3R; B and C: zone stop, target at the next zone); net of 12bp + funding, in R")
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
    P("\nDIAGNOSTIC Z3: zoned sweeps with the zone stop and a plain 3R target (the target choice separated from the stop), in R")
    for side, nm in ((1, "LONG "), (-1, "SHORT")):
        for half, m in (("tune", tune), ("hold", hold)):
            x = T[T.zoned & T.net_3.notna() & T.ctrl_3.notna() & (T.side == side) & m]
            P(f"  Z3 {nm} {half:5s} {cell_r(x, 'net_3', 'ctrl_3', 'rf_3', 'hit_3', 'ctrl_hit_3')}")
    P("\nDIAGNOSTIC: zoned sweeps on arm A's own trade (same sweep stop, 3R), in R")
    for side, nm in ((1, "LONG "), (-1, "SHORT")):
        for half, m in (("tune", tune), ("hold", hold)):
            x = T[T.zoned & (T.side == side) & m]
            P(f"  zoned-on-A {nm} {half:5s} {cell_r(x, 'net_a', 'ctrl_a', 'rf_a', 'hit_a', 'ctrl_hit_a')}")
    P("\nINFORMATION TEST on T24 (stop = sweep extreme, out 24 bars on), net % per trade: flagged minus unflagged, day-clustered t")
    info_b = z4.info_spread(T, "zoned")
    info_c = z4.info_spread(T, "trend_ok", sub=T.zoned)
    for nm_, info in (("B: zoned - unzoned", info_b), ("C: trend-agrees - not, inside zoned", info_c)):
        for side, sn in ((1, "LONG "), (-1, "SHORT")):
            tu, ho = info[side, "tune"], info[side, "hold"]
            P(f"  {nm_:36s} {sn} tune spread {tu[0] * 100:+.2f}% (t {tu[1]:+.1f}, {tu[2]} of {tu[3]}) | holdout {ho[0] * 100:+.2f}% (t {ho[1]:+.1f}, {ho[2]} of {ho[3]})")
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
            flag = "UNDERPOWERED" if ho["n"] < MIN_HOLD_TRADES else ("PASS" if ok else "no")
            P(f"  {arm} {sn}: tune net {tu['net']:+.2f}R (n {tu['n']}), holdout net {ho['net']:+.2f}R (t {ho['t']:+.1f}, n {ho['n']}, {ho['n'] / yrs:.0f} a year), "
              f"excess {tu['ex']:+.2f}R / {ho['ex']:+.2f}R, Holm p {hp[arm, side]:.2f}, information {'ok' if info_ok else 'no'}  ->  {flag}")
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
