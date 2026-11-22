"""SWEEP + ZONE + TREND WITH MORE DATA: the 4h and daily zone rules, FROZEN, on data they have never seen (2026-11-08)

THE USER (2026-11-08): after blindness_check.py showed the zone studies could not see a moderate edge ("the 4h test catches +0.07R 12% of the time, the daily
test can pass nothing"): "yes, more data". So the two studies' rules run UNCHANGED - sweep_zone.coin_events and sweep_zone_daily.coin_events, the very functions
that produced logs/sweep_zone.txt and logs/sweep_zone_daily.txt - on two samples neither study read:
  NEW-PERP   Binance USDT perps 2020-2026, the coins ranked 41-100 by the PRIOR month's volume in that month (point in time, dead coins in; the studies used 1-40).
  NEW-SPOT   Binance USDT spot 2017-08 .. 2019-12 (strategy_analysis/data/spot1719, 89 pairs; every pair 30+ days old, i.e. top-100 = all): before any perp
             existed. No funding (spot), 12bp as everywhere. Shorts here measure price behaviour (a spot account could not short then).
  NEW        both together = the confirm sample. OLD (top-40 perps, the studies' own events, already read) is shown beside it, and ALL = OLD + NEW.
The coins are loaded one at a time (memory), with the same per-coin setup as each study's build_events; `same_as_study()` checks that this loop reproduces the
studies' own event rows on top-40 coins before anything new is read.

THE CELLS JUDGED (8, Holm over all 8 on NEW): {4h B (zoned, zone stop, 3R / 72h), 4h C (B + the daily trend), daily B (zoned, zone stop, next-zone target >= 1.5R,
  240 bars), daily C (daily B + the daily trend)} x {long, short}. Arm A (every sweep) and daily Z3 are shown, not judged.
PASS (a cell, on NEW): net R > 0 with a Holm-adjusted one-sided p < 0.05 (t clustered by day), excess over the matched random-hour control > 0, at least 100 trades,
  and net R > 0 in BOTH halves of NEW by time (split at its median event date, so one regime cannot carry it). A pass = a candidate for a forward paper record.
POWER LINE (blindness_check.py's lesson, printed beside every cell before its verdict): MDE80 = (z for Holm's first step, 0.05 / 8, one-sided + 0.84) x the cell's
  day-clustered standard error = the true edge the cell would catch about 80% of the time. A NO PASS with MDE80 above +0.15R reads 'cannot tell', not 'dead'.

REGISTERED BEFORE THE FIRST RUN (2026-11-08)
  M1  NEW is at least 3x the studies' zoned samples: >= 7,000 4h-zoned sweeps and >= 850 daily-zoned sweeps with a target.                              55%
  M2  Arm A (every sweep) loses after fees on NEW, both sides.                                                                                          85%
  M3  No judged cell passes.                                                                                                                             85%
  M4  MDE80 on NEW: 4h B +0.08 .. +0.15R a side; daily B still above +0.25R a side (daily zones with a target stay rare).                               60%
  M5  The old daily-zone SHORT cells (+0.26R / +0.37R on 49 / 36 holdout trades, underpowered) come out at or under +0.10R on NEW (regression to the mean).  65%
  M6  The 4h zoned-minus-unzoned spread on the 24-bar trade is within +-0.15% on NEW for both sides (the zone carries no information).                    70%

RESULT (2026-11-08, logs/sweep_zone_more.txt). The loop reproduces both studies' event rows exactly (BTC / ETH / LINK, every column but the controls).
  SAMPLES: NEW-PERP 83,969 sweeps on 555 coins (4h-zoned 2,792, daily-zoned with a target 377); NEW-SPOT 10,218 on 79 pairs (413 / 51); NEW 94,187 (3,205 / 428);
  ALL = OLD + NEW 154,788 sweeps, 610 coins, 2017-10 .. 2026-09 (5,528 / 714).
  VERDICT ON NEW (registered, Holm over 8): 0 of 8 pass.
  4h zones: NEW long +0.013R (n 1,537, excess -0.03R), short -0.146R (n 1,668, t -2.9); ALL long -0.042R / short -0.123R with MDE80 +0.15 / +0.16R. With
    the extra data an edge of about +0.15R would have been caught 80% of the time, and the measured result is at or below zero on both sides: DEAD at any size
    worth trading. (The zoned-minus-unzoned 24-bar spread, long: OLD -0.19%, NEW +0.38% t 2.3, ALL +0.13% t 1.0 - it flips between samples.)
  Daily zones, LONG: NEW -0.19R (n 279), ALL -0.20R (t -2.1): dead.
  Daily zones, SHORT: positive in OLD and in NEW-PERP - B short NEW +0.35R (n 149, halves -0.12 / +0.81, excess +0.55R), C short NEW +1.12R (n 49, t 2.13,
    Holm 0.13); pooled ALL C short +0.72R (n 123, t 2.69, Holm 0.03 - but ALL contains the sample that suggested the cell). Diagnosed (post hoc,
    scratch): median trade -1.0R, 16% hit the target, the mean is carried by ~10 trades out of 123 (without the best 10: +0.09R; for B short -0.03R), the best
    being the 2025-10-10 crash (CRV short +17.9R), INJ twice and the 2024 alt bleed; 2024-25 make most of it, 2026 is negative. A crash-tail bet in the bear
    sleeve's family, ~14 trades a year: a LEAD that a forward record would take years to confirm, not a book.
  PREDICTIONS: M1 WRONG (NEW is 1.4x / 1.5x the studies' zoned samples, not 3x: the coins ranked 41-100 form fewer zones). M2 right (arm A -0.111R / -0.078R).
    M3 right (0 of 8). M4 half wrong (4h MDE80 +0.18 / +0.17R on NEW, above +0.15; daily above +0.25 right). M5 WRONG (the daily short cells stayed positive,
    carried by a few crash trades). M6 half wrong (long spread +0.38%, t 2.3, on NEW; short right).

    python backtest/sweep_zone_more.py            (builds logs/sweep_zone_more_{new_perp,new_spot}_{4h,1d}.pkl, then reports; --refit rebuilds)
    tests: python tests/test_sweep_zone_more.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import backtest.capitulation_wide as cw  # noqa: E402
import backtest.sweep_confluence as sc  # noqa: E402
import backtest.sweep_zone as z4  # noqa: E402
import backtest.sweep_zone_daily as zd  # noqa: E402
import backtest.wide_book as wb  # noqa: E402

LOG = ROOT / "logs" / "sweep_zone_more.txt"
PERPS = ROOT / "strategy_analysis" / "data" / "perps"
SPOT = ROOT / "strategy_analysis" / "data" / "spot1719"
SPOT_END = pd.Timestamp("2020-01-01")
N_JUDGED = 8
MIN_TRADES = 100


def point_at(folder: Path):
    """Every loader the studies use reads its folder at call time: the 1h / 1d files (wide_book.DATA, capitulation_wide.PERPS) and the funding files
    (capitulation_wide.funding_cum, sweep_confluence.last_rate). A spot folder has no funding files, so funding is zero there."""
    wb.DATA = folder
    cw.PERPS = folder
    sc.PERPS = folder


def samples(kind: str) -> dict:
    """{coin: set of 'YYYY-MM' months} for NEW-PERP (ranks 41-100) or NEW-SPOT (every pair 30+ days old, months before 2020)."""
    if kind == "perp":
        point_at(PERPS)
        e100, e40 = wb.eligibility(100), wb.eligibility(40)
        return {s: m - e40.get(s, set()) for s, m in e100.items() if m - e40.get(s, set())}
    point_at(SPOT)
    e = wb.eligibility(100)
    return {s: {x for x in m if x < SPOT_END.strftime("%Y-%m")} for s, m in e.items() if any(x < SPOT_END.strftime("%Y-%m") for x in m)}


def coin_rows(mod, s: str, months: set, rng) -> list:
    """One coin through a study's own coin_events, with that study's own per-coin setup (copied from its build_events: eligible months, the control pools of
    hours with room for the hold, funding, the funding rate)."""
    hh = cw.hourly(s)
    if hh is None:
        return []
    t = hh.time.to_numpy("datetime64[ns]")
    o, h, l, c, q = (hh[k].to_numpy(float) for k in ("open", "high", "low", "close", "qvol"))
    n = len(c)
    if n < 400:
        return []
    hold = mod.HOLD_R if mod is z4 else mod.HOLD
    ym = pd.DatetimeIndex(t).strftime("%Y-%m").to_numpy()
    elig = np.array([m in months for m in ym])
    by_month = pd.Series(np.arange(n)).groupby(ym).apply(lambda x: x.to_numpy())
    pools = {m: v[(v > mod.TREND_WARM) & (v + hold + 2 < n)] for m, v in by_month.items()}
    pools = {m: v for m, v in pools.items() if len(v)}
    fc = cw.funding_cum(s, t, hh)
    rows = mod.coin_events(t, o, h, l, c, q, sc.last_rate(s, t), fc, elig & np.array([m in pools for m in ym]), pools, ym, rng)
    for r in rows:
        r["coin"] = s
    return rows


def build(kind: str, mod) -> pd.DataFrame:
    el = samples(kind)
    rng = np.random.default_rng(0)
    out = []
    for s in sorted(el):
        out += coin_rows(mod, s, el[s], rng)
    return pd.DataFrame(out)


def rows_match(new: pd.DataFrame, ref: pd.DataFrame) -> list:
    """The columns where two event tables differ (the random-control columns excluded: their draws depend on the coins drawn before). [] = identical."""
    if len(new) != len(ref):
        return [f"rows {len(new)} vs {len(ref)}"]
    bad = []
    for k in ref.columns:
        if k.startswith("ctrl") or k == "coin":
            continue
        a, b = new[k].reset_index(drop=True), ref[k].reset_index(drop=True)
        if k in ("t_in", "day"):
            same = (pd.to_datetime(a).to_numpy() == pd.to_datetime(b).to_numpy()).all()
        else:
            same = np.allclose(a.to_numpy(float), b.to_numpy(float), equal_nan=True)
        if not same:
            bad.append(k)
    return bad


def same_as_study(coins=("BTCUSDT", "ETHUSDT", "LINKUSDT")) -> list:
    """This file's loop against the studies' own event rows on top-40 coins, for both studies: [] = every row and column (but the controls) reproduced."""
    point_at(PERPS)
    el = wb.eligibility(40)
    bad = []
    for mod, pkl in ((z4, ROOT / "logs" / "sweep_zone_events.pkl"), (zd, ROOT / "logs" / "sweep_zone_daily_events.pkl")):
        old = pd.read_pickle(pkl)
        for s in coins:
            new = pd.DataFrame(coin_rows(mod, s, el[s], np.random.default_rng(0)))
            d = rows_match(new.drop(columns=["coin"]), old[old.coin == s].reset_index(drop=True))
            bad += [f"{mod.__name__.split('.')[-1]} {s}: {x}" for x in d]
    return bad


# ------------------------------------------------------------------ the report

def mde80(se: float, k: int = N_JUDGED) -> float:
    from statistics import NormalDist
    return (NormalDist().inv_cdf(1 - 0.05 / k) + NormalDist().inv_cdf(0.80)) * se


def cell_stats(x: pd.DataFrame, net: str, ctrl: str, rf: str) -> dict:
    if len(x) < 3:
        return dict(n=len(x), R=np.nan, t=np.nan, se=np.nan, ex=np.nan, h1=np.nan, h2=np.nan)
    R, C = (x[net] / x[rf]).to_numpy(), (x[ctrl] / x[rf]).to_numpy()
    t = sc.t_by_day(pd.Series(R), pd.Series(x.day.to_numpy()))
    se = abs(R.mean() / t) if np.isfinite(t) and t != 0 else np.nan
    tt = pd.to_datetime(x.t_in).to_numpy()
    mid = np.sort(tt)[len(tt) // 2]
    return dict(n=len(x), R=float(R.mean()), t=t, se=se, ex=float((R - C).mean()), h1=float(R[tt < mid].mean()), h2=float(R[tt >= mid].mean()))


def judged(T4: pd.DataFrame, TD: pd.DataFrame) -> list:
    """The 8 judged cells as (name, frame, net, ctrl, rf)."""
    Z4 = T4[T4.zoned & T4.net_z.notna() & T4.ctrl_z.notna()]
    B = TD[TD.zoned & TD.has_target & TD.net_b.notna() & TD.ctrl_b.notna()]
    out = []
    for side, nm in ((1, "long"), (-1, "short")):
        out += [(f"4h B {nm}", Z4[Z4.side == side], "net_z", "ctrl_z", "rf_z"),
                (f"4h C {nm}", Z4[(Z4.side == side) & Z4.trend_ok], "net_z", "ctrl_z", "rf_z"),
                (f"daily B {nm}", B[B.side == side], "net_b", "ctrl_b", "rf_b"),
                (f"daily C {nm}", B[(B.side == side) & B.trend_ok], "net_b", "ctrl_b", "rf_b")]
    return out


def verdicts(cells: list) -> list:
    """Holm over the judged cells on the confirm sample, then the rest of the bar."""
    st = [cell_stats(*c[1:]) for c in cells]
    ps = {k: (sc.p_one_sided(s["t"]) if np.isfinite(s["t"]) else 1.0) for k, s in enumerate(st)}
    hp = sc.holm(ps)
    out = []
    for k, (c, s) in enumerate(zip(cells, st)):
        ok = bool(s["n"] >= MIN_TRADES and s["R"] > 0 and hp[k] < 0.05 and s["ex"] > 0 and s["h1"] > 0 and s["h2"] > 0)
        m = mde80(s["se"]) if np.isfinite(s["se"]) else np.nan
        word = "PASS" if ok else ("no (cannot tell: MDE80 > +0.15R)" if not np.isfinite(m) or m > 0.15 else "no")
        out.append(dict(name=c[0], holm=hp[k], mde=m, ok=ok, word=word, **s))
    return out


def line(v: dict) -> str:
    return (f"  {v['name']:<14} n {v['n']:>5}  net {v['R']:+.3f}R (t {v['t']:+.2f})  halves {v['h1']:+.2f} / {v['h2']:+.2f}  excess {v['ex']:+.3f}R  "
            f"MDE80 {v['mde']:+.2f}R  Holm p {v['holm']:.2f}  -> {v['word']}")


def info(T4: pd.DataFrame) -> list:
    out = []
    for side, nm in ((1, "long"), (-1, "short")):
        g = T4[T4.side == side]
        if g.zoned.nunique() < 2:
            continue
        b, t = sc.spread_t(g.net24.to_numpy(), g.zoned.to_numpy(), g.day.to_numpy())
        out.append(f"  zoned - unzoned on the 24-bar trade, {nm:<5}: {b * 100:+.2f}% (t {t:+.2f}; {int(g.zoned.sum())} of {len(g)})")
    return out


def arm_a(T4: pd.DataFrame) -> list:
    out = []
    for side, nm in ((1, "long"), (-1, "short")):
        s = cell_stats(T4[T4.side == side], "net_a", "ctrl_a", "rf_a")
        out.append(f"  arm A {nm:<5} n {s['n']:>6}  net {s['R']:+.3f}R (t {s['t']:+.1f})  excess {s['ex']:+.3f}R")
    return out


def main():
    L = [f"backtest/sweep_zone_more.py, {pd.Timestamp.now():%Y-%m-%d %H:%M}; the 4h and daily zone rules FROZEN (sweep_zone / sweep_zone_daily coin_events) on unseen data"]
    bad = same_as_study()
    L.append(f"this file's loop reproduces the studies' own event rows on BTC / ETH / LINK (both studies): {'yes' if not bad else bad}")
    if bad:
        print("\n".join(L))
        raise SystemExit("the loop does not reproduce the studies: stop")
    T = {}
    for kind in ("perp", "spot"):
        for mod, tag in ((z4, "4h"), (zd, "1d")):
            f = ROOT / "logs" / f"sweep_zone_more_new_{kind}_{tag}.pkl"
            if not f.exists() or "--refit" in sys.argv:
                build(kind, mod).to_pickle(f)
            T[kind, tag] = pd.read_pickle(f)
    point_at(PERPS)
    old4, oldd = pd.read_pickle(ROOT / "logs" / "sweep_zone_events.pkl"), pd.read_pickle(ROOT / "logs" / "sweep_zone_daily_events.pkl")
    new4 = pd.concat([T["perp", "4h"].assign(src="perp"), T["spot", "4h"].assign(src="spot")], ignore_index=True)
    newd = pd.concat([T["perp", "1d"].assign(src="perp"), T["spot", "1d"].assign(src="spot")], ignore_index=True)
    for nm, a, b in (("NEW-PERP (ranks 41-100, 2020-26)", T["perp", "4h"], T["perp", "1d"]), ("NEW-SPOT (2017-19)", T["spot", "4h"], T["spot", "1d"]),
                     ("NEW = both (THE CONFIRM SAMPLE)", new4, newd), ("OLD (top-40, already read)", old4, oldd),
                     ("ALL = OLD + NEW", pd.concat([old4, new4], ignore_index=True), pd.concat([oldd, newd], ignore_index=True))):
        nz = int(a.zoned.sum())
        nt = int((b.zoned & b.has_target).sum())
        L.append(f"\n== {nm}: {len(a)} sweeps, {a.coin.nunique()} coins, {pd.to_datetime(a.t_in).min():%Y-%m} .. {pd.to_datetime(a.t_in).max():%Y-%m}; "
                 f"4h-zoned {nz} ({nz / max(len(a), 1) * 100:.1f}%), daily-zoned with a target {nt}")
        L += arm_a(a)
        L += info(a)
        L += [line(v) for v in verdicts(judged(a, b))]
    vs = verdicts(judged(new4, newd))
    L.append(f"\nVERDICT on NEW (Holm over {N_JUDGED}): {sum(v['ok'] for v in vs)} of {N_JUDGED} pass: {[v['name'] for v in vs if v['ok']]}")
    txt = "\n".join(L)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
