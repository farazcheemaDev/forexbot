"""THE 'WEAK BREAK' RULE - four signs that a NASDAQ break of a recent level is fake, stacked, FROZEN, and judged on days no test has seen
(2026-11-22)

THE USER (2026-11-22): "yes build it" - after three methods each showed the same small thing at the fake breaks (his_reclaim.py's setup):
weak breaks fail a little more often - the S&P holding its level (his_smt.py, +1.8 / +1.6 points), a weak breakout bar (his_brooks.py,
+2.3 / +1.0), a shallow light-volume 'No. 3' spring (his_wyckoff.py, +1.9 / +3.3) - and 5 of his 7 fake-break trades broke the previous
hour's high or low (his_wyckoff.py, base 31%). Every one of those numbers was found on the 181 tick days 2026-01-02 .. 09-14, so on those
days the stacked rule is 'chosen after looking'. Its only honest judge is days after 09-14.

THE RULE (frozen 2026-11-22 before any day after 2026-09-14 was fetched; RULE + the code below are pinned by a sha256 the fresh run checks)
  at his_reclaim.py's state-A moments (every 1-minute close + 14 s, 09:45-15:45 New York; the nearest swing level of the last 120 minutes
  within 10 points, broken by more than 3 points, the price still beyond it); the trade back through the level; the +-7 race on the mid
  (race2, 10 minutes). One point for each sign:
    S  the S&P 500 held its matching level (his_smt.partner_break, the scaled 3-point rule)
    B  the breakout bar was WEAK (his_brooks.brooks_a: not a body in the breakout direction of half its range or more, a close in its outer
       third and a range at least the 10 bars before)
    W  a No. 3 spring (his_wyckoff.features): depth under 22.4 points AND the spring leg's CME volume under 1.16x the 20 bars before
       (the tune half's medians in logs/his_wyckoff.txt)
    H  range support (his_wyckoff.features): the broken level was the extreme of the 60 bars before the break
  SCORE = S + B + W + H. THE RULE: SCORE >= 3. Strict: SCORE = 4. A moment where any sign cannot be read is left out.
DATA   in-sample: the 181 tick days of ustec_tick_days.pkl, the S&P from HistData (as his_smt.py), CME NQ volume (as his_wyckoff.py).
       FRESH: 2026-09-15 .. 10-29 - NASDAQ ticks from MT5 with the cache's own day_ticks, stored APART in strategy_analysis/data/fresh/ so no
       earlier study's numbers move; the S&P from Exness US500m 1-minute mid bars built from MT5 ticks (HistData's S&P ends 2026-09-30;
       the switch is checked on in-sample days where both exist); CME volume to 2026-10-29 (already on disk; later days need a purchase).
REGISTERED BEFORE ANY FRESH NUMBER (2026-11-22)
  F1  In-sample (seen): SCORE >= 3 wins 53-57% on both halves. (60%)
  F2  Fresh: SCORE >= 3 beats the rest of the fresh moments by less than its in-sample lift (shrinkage). (70%)
  F3  Fresh: SCORE >= 3 stays under 61%. (95%)
  F4  Fresh: the race does not rise steadily with the score from 0 to 4. (60%)
  F5  Source check: the S-sign from Exness US500m equals HistData's on >= 85% of the in-sample overlap moments. (75%)
  LEAD: fresh SCORE >= 3 beats the rest by 3+ points with a day-bootstrap 90% interval above zero. A TRADE needs 61%.

RESULT (2026-11-22; logs/weak_break_insample.txt, logs/weak_break_fresh.txt; frozen sha256 86fd452f... at 10:06:44 UTC, checked by the fresh
  run): THE STACK POINTS THE RIGHT WAY ON UNSEEN DAYS, SMALLER, NOT PROVEN, AND FAR FROM TRADABLE. Seen days (chosen after looking): score
  >= 3 won 53.9% / 56.1% (tune / holdout) against 49.7% / 51.8% for the rest, +4.2 points (F1 right). Fresh days (31 tick days
  2026-09-17 .. 10-29; MT5 has no USTECm ticks for 09-15 / 09-16): score >= 3 won 55.1% of 363 against 52.6% of 3,300 for the rest - +2.5
  points, day-bootstrap 90% interval -3.3 .. +7.9 (first half +1.6, second half +4.0); by score 51.9 / 51.7 / 54.8 / 54.8% for 0-3, 60.0%
  on 20 moments at 4. The fresh base rate was itself high (52.9%). F2-F5 right (the S&P switch agrees on 98.0% of 3,887 moments); NO
  LEAD by the registered bar. His 7 reclaims scored 2, 1, 2, 4, 2, 2, 2 - only one met the rule (base 11%), so it is not his selector.
  Even if the +2.5 is real, 55% is six points under the 61% a +-7 trade needs after the spread.

    python -m backtest.weak_break --insample      (seen days; writes the frozen hash to logs/weak_break_frozen.json)
    python -m backtest.weak_break --fetch         (MT5 open: fresh NASDAQ ticks + US500m bars into strategy_analysis/data/fresh/)
    python -m backtest.weak_break --fresh         (refuses to run unless the hash equals the frozen one)
"""
from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import backtest.his_brooks as BR  # noqa: E402
import backtest.his_smt as SM  # noqa: E402
import backtest.his_wyckoff as WY  # noqa: E402
from backtest.his_level_memory import TICKS, swings  # noqa: E402

FRESH_DIR = ROOT / "strategy_analysis" / "data" / "fresh"
FRESH_TICKS = FRESH_DIR / "ustec_tick_days_fresh.pkl"
FRESH_SPX = FRESH_DIR / "US500m.parquet"
FROZEN = ROOT / "logs" / "weak_break_frozen.json"
LOG_IN, LOG_FR = ROOT / "logs" / "weak_break_insample.txt", ROOT / "logs" / "weak_break_fresh.txt"
RULE = dict(signs=("S: S&P held its matching level", "B: weak breakout bar", "W: No. 3 spring (depth < 22.4, volume < 1.16x)",
                   "H: range support (extreme of the 60 bars before the break)"),
            depth_max=22.4, relvol_max=1.16, rule_min=3, strict=4, race=(600, 7, 7),
            fresh_from="2026-09-15", fresh_to="2026-10-29", overlap_from="2026-08-03", fetch_to="2026-11-20")


def score_moment(o, h, l, c, vol, sph, spl, lev: dict, p: float):
    """The four signs and the score at a state-A moment, or None if a sign cannot be read."""
    pb = SM.partner_break(sph, spl, lev["kind"], lev["j"], lev["M"], lev["v"]) if sph is not None else None
    b = BR.brooks_a(o, h, l, c, lev)
    f = WY.features(h, l, c, vol, lev, p)
    if pb is None or not np.isfinite(b["strong_bo"]) or not np.isfinite(f["relvol"]):
        return None
    sg = dict(S=int(not pb[1]), B=int(b["strong_bo"] == 0.0),
              W=int(f["depth"] < RULE["depth_max"] and f["relvol"] < RULE["relvol_max"]), H=int(f["rs"] == 1.0))
    sg["score"] = sg["S"] + sg["B"] + sg["W"] + sg["H"]
    return sg


def rule_hash() -> str:
    """sha256 of the rule's constants and every function its score depends on."""
    parts = [json.dumps(RULE, sort_keys=True)]
    for fn in (score_moment, SM.partner_break, SM.level_at, BR.brooks_a, BR.strong, BR.ohlc, WY.features, WY.argext, WY.nmean):
        parts.append(inspect.getsource(fn))
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()


def moments(cache: dict, days, spx: dict, cme: dict, with_his: bool = False):
    """Every scored state-A moment of these days: (rows, his reclaims)."""
    from backtest.his_race_curve import race2
    W_, T_, S_ = RULE["race"]
    rows, his = [], []
    for day in days:
        dd = cache.get(day)
        if dd is None or day not in cme or day not in spx:
            continue
        ts, mid = dd[0], dd[1]
        o, h, l, c = BR.ohlc(ts, mid)
        sh, sl = swings(h, l)
        vol, (sph, spl, _) = cme[day][0], spx[day]
        for t in np.arange(15 * 60 + 14, 375 * 60 + 14, 60.0):
            lev = SM.level_at(ts, mid, h, l, sh, sl, t)
            if lev is None or lev["state"] != "A":
                continue
            w = race2(ts, mid, t, lev["side"], W_, T_, S_)
            if w is None:
                continue
            p = float(mid[np.searchsorted(ts, t - 1.0, side="right") - 1])
            sg = score_moment(o, h, l, c, vol, sph, spl, lev, p)
            if sg is not None:
                rows.append(dict(day=day, t=float(t), win=w, **sg))
    if with_his:
        import backtest.his_tape as TP
        for r in TP.entries().itertuples():
            dd = cache.get(r.d)
            if dd is None or r.t < 15 * 60 or r.d not in cme or r.d not in spx:
                continue
            ts, mid = dd[0], dd[1]
            o, h, l, c = BR.ohlc(ts, mid)
            sh, sl = swings(h, l)
            lev = SM.level_at(ts, mid, h, l, sh, sl, float(r.t))
            if lev is None or lev["state"] != "A" or lev["side"] != r.s:
                continue
            p = float(mid[np.searchsorted(ts, float(r.t) - 1.0, side="right") - 1])
            sg = score_moment(o, h, l, c, cme[r.d][0], spx[r.d][0], spx[r.d][1], lev, p)
            his.append(dict(d=r.d, s=r.s, won=race2(ts, mid, r.t, r.s, W_, T_, S_), **(sg or dict(score=np.nan))))
    return pd.DataFrame(rows), pd.DataFrame(his)


def boot_diff(R: pd.DataFrame, reps: int = 2000, seed: int = 11):
    """Day-bootstrap of win(score >= rule_min) - win(rest): (5th, 95th percentile)."""
    codes, uniq = pd.factorize(R.day)
    win = R.win.to_numpy(float)
    m1 = (R.score >= RULE["rule_min"]).to_numpy(float)
    m0 = 1.0 - m1
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(reps):
        w = np.bincount(rng.integers(0, len(uniq), len(uniq)), minlength=len(uniq))[codes].astype(float)
        a, b = (w * m1).sum(), (w * m0).sum()
        if a > 0 and b > 0:
            out.append((w * m1 * win).sum() / a - (w * m0 * win).sum() / b)
    return (float(np.percentile(out, 5)), float(np.percentile(out, 95))) if out else (np.nan, np.nan)


def report(R: pd.DataFrame, halves: dict, out: list) -> dict:
    """Race by score, the rule and the strict rule vs the rest, per period in `halves` {name: mask}."""
    res = {}
    out.append(f"    {'':<30}" + "".join(f"{nm:>20}" for nm in halves))
    for k in range(5):
        cells = []
        for nm, m in halves.items():
            y = R[m & (R.score == k)]
            res[("score", k, nm)] = (y.win.mean(), len(y))
            cells.append(f"{y.win.mean():.1%} of {len(y):,}" if len(y) else "-")
        out.append(f"    {'score ' + str(k):<30}" + "".join(f"{x:>20}" for x in cells))
    for lab, sel in (("RULE: score >= 3", R.score >= RULE["rule_min"]), ("strict: score = 4", R.score == RULE["strict"]),
                     ("rest: score <= 2", R.score < RULE["rule_min"]), ("every moment", pd.Series(True, index=R.index))):
        cells = []
        for nm, m in halves.items():
            y = R[m & sel]
            res[(lab, nm)] = (y.win.mean() if len(y) else np.nan, len(y))
            cells.append(f"{y.win.mean():.1%} of {len(y):,}" if len(y) else "-")
        out.append(f"    {lab:<30}" + "".join(f"{x:>20}" for x in cells))
    out.append("    share with each sign: " + ", ".join(f"{s} {R[s].mean():.0%}" for s in ("S", "B", "W", "H")))
    return res


def run_insample():
    cache = pickle.loads(TICKS.read_bytes())
    days = sorted(d for d, v in cache.items() if v is not None)
    n_of = {d: len(BR.ohlc(cache[d][0], cache[d][1])[1]) for d in days}
    spx, cme = SM.by_day_minutes(SM.SPX, days, n_of), WY.cme_minutes(days, n_of)
    R, Hh = moments(cache, days, spx, cme, with_his=True)
    cut = days[int(len(days) * 0.6)]
    hv = rule_hash()
    out = [f"backtest/weak_break.py --insample, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; RULE sha256 {hv}",
           f"  SEEN DAYS (every sign was found on them): {len(days)} tick days {days[0]:%Y-%m-%d} .. {days[-1]:%Y-%m-%d}, split {cut:%Y-%m-%d}; "
           f"scored state-A moments {len(R):,}", ""]
    res = report(R, {"tune": R.day < cut, "holdout": R.day >= cut}, out)
    lift = res[("RULE: score >= 3", "tune")][0] - res[("rest: score <= 2", "tune")][0], \
        res[("RULE: score >= 3", "holdout")][0] - res[("rest: score <= 2", "holdout")][0]
    pooled = R[R.score >= 3].win.mean() - R[R.score < 3].win.mean()
    out += ["", f"    lift of the rule over the rest: tune {lift[0] * 100:+.1f}, holdout {lift[1] * 100:+.1f}, pooled {pooled * 100:+.1f} points", "",
            f"  HIS 7 RECLAIMS by score: " + ", ".join(f"{r.d:%m-%d} {'' if not np.isfinite(r.score) else int(r.score)}"
                                                      f"{'' if not np.isfinite(r.score) else ' (' + ''.join(s for s in 'SBWH' if r[s] == 1) + ')'}"
                                                      for _, r in Hh.iterrows())]
    f1 = all(0.53 <= res[("RULE: score >= 3", h)][0] <= 0.57 for h in ("tune", "holdout"))
    out += ["", f"  F1 (seen) score >= 3 wins 53-57% on both halves -> {'RIGHT' if f1 else 'WRONG'}"]
    txt = "\n".join(out)
    LOG_IN.write_text(txt + "\n", encoding="utf-8")
    FROZEN.write_text(json.dumps(dict(sha256=hv, frozen_utc=f"{pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M:%S}", rule=RULE,
                                      insample_lift_pooled=pooled, insample_rule=[res[("RULE: score >= 3", h)][0] for h in ("tune", "holdout")]),
                                 indent=1, default=str), encoding="utf-8")
    print(txt)


def run_fetch():
    import MetaTrader5 as mt5
    from backtest.his_microstructure import day_ticks
    from backtest.mt5_1m import day_bars
    FRESH_DIR.mkdir(parents=True, exist_ok=True)
    assert mt5.initialize(), mt5.last_error()
    try:
        ticks = pickle.loads(FRESH_TICKS.read_bytes()) if FRESH_TICKS.exists() else {}
        need = [d for d in pd.bdate_range(RULE["fresh_from"], RULE["fetch_to"]) if d not in ticks]
        for k, d in enumerate(need, 1):
            ticks[d] = day_ticks(mt5, d)
            if k % 5 == 0 or k == len(need):
                FRESH_TICKS.write_bytes(pickle.dumps(ticks))
                print(f"  NASDAQ ticks: {k}/{len(need)} days", flush=True)
        print(f"fresh NASDAQ tick days: {sum(v is not None for v in ticks.values())} of {len(ticks)}", flush=True)
        parts = [pd.read_parquet(FRESH_SPX)] if FRESH_SPX.exists() else []
        have = set() if not parts else set(pd.to_datetime(parts[0].t, unit="ms", utc=True).dt.normalize().dt.tz_localize(None))
        for d in pd.bdate_range(RULE["overlap_from"], RULE["fetch_to"]):
            for dd in (d, d + pd.Timedelta(days=1)):                    # a New York session spans two UTC dates
                if dd not in have:
                    b = day_bars(mt5, "US500m", dd)
                    if len(b):
                        parts.append(b)
                    have.add(dd)
        allb = pd.concat(parts).drop_duplicates("t").sort_values("t", kind="stable")
        allb.to_parquet(FRESH_SPX)
        print(f"US500m 1-minute bars: {len(allb):,} ({pd.to_datetime(allb.t.min(), unit='ms')} .. {pd.to_datetime(allb.t.max(), unit='ms')} UTC)")
    finally:
        mt5.shutdown()


def run_fresh():
    hv = rule_hash()
    fz = json.loads(FROZEN.read_text(encoding="utf-8"))
    assert hv == fz["sha256"], f"the rule changed after it was frozen ({hv} vs {fz['sha256']}) - refused"
    old = pickle.loads(TICKS.read_bytes())
    fresh = pickle.loads(FRESH_TICKS.read_bytes())
    assert not (set(fresh) & {d for d, v in old.items() if v is not None}), "fresh days overlap the seen days"
    out = [f"backtest/weak_break.py --fresh, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; RULE sha256 {hv} = frozen at {fz['frozen_utc']} UTC"]
    # F5: the S&P source switch, on seen days where both sources exist
    ov = sorted(d for d, v in old.items() if v is not None and d >= pd.Timestamp(RULE["overlap_from"]))
    n_ov = {d: len(BR.ohlc(old[d][0], old[d][1])[1]) for d in ov}
    hist, exn = SM.by_day_minutes(SM.SPX, ov, n_ov), SM.by_day_minutes(FRESH_SPX, ov, n_ov)
    cme_ov = WY.cme_minutes(ov, n_ov)
    Ra, _ = moments(old, ov, hist, cme_ov)
    Rb, _ = moments(old, ov, exn, cme_ov)
    j = Ra.merge(Rb, on=["day", "t"], suffixes=("_h", "_e"), how="inner") if len(Ra) and len(Rb) else pd.DataFrame()
    agree = float((j.S_h == j.S_e).mean()) if len(j) else np.nan
    out += [f"  SOURCE CHECK on {len(ov)} seen days from {RULE['overlap_from']}: the S-sign from Exness US500m = HistData's on {agree:.1%} of "
            f"{len(j):,} matched moments (scored moments {len(Ra):,} / {len(Rb):,})", ""]
    # the fresh test
    days = sorted(d for d, v in fresh.items() if v is not None and pd.Timestamp(RULE["fresh_from"]) <= d <= pd.Timestamp(RULE["fresh_to"]))
    n_of = {d: len(BR.ohlc(fresh[d][0], fresh[d][1])[1]) for d in days}
    spx, cme = SM.by_day_minutes(FRESH_SPX, days, n_of), WY.cme_minutes(days, n_of)
    R, _ = moments(fresh, days, spx, cme)
    out += [f"  FRESH DAYS (no test has seen them): {len(days)} tick days {days[0]:%Y-%m-%d} .. {days[-1]:%Y-%m-%d} "
            f"({sum(d in cme for d in days)} with CME volume); scored state-A moments {len(R):,}", ""]
    mid_d = days[len(days) // 2]
    res = report(R, {"first half": R.day < mid_d, "second half": R.day >= mid_d, "all fresh": pd.Series(True, index=R.index)}, out)
    lift = res[("RULE: score >= 3", "all fresh")][0] - res[("rest: score <= 2", "all fresh")][0]
    lo, hi = boot_diff(R)
    out += ["", f"    lift of the rule over the rest: {lift * 100:+.1f} points (day-bootstrap 90% interval {lo * 100:+.1f} .. {hi * 100:+.1f}); "
                f"in-sample pooled lift {fz['insample_lift_pooled'] * 100:+.1f}"]
    rates = [res[("score", k, "all fresh")] for k in range(5)]
    usable = [r for r, n in rates if n >= 30]
    steady = len(usable) >= 3 and all(b >= a for a, b in zip(usable, usable[1:]))
    rule_rate = res[("RULE: score >= 3", "all fresh")][0]
    out += ["", "REGISTERED PREDICTIONS (fresh)",
            f"  F2 the fresh lift is below the in-sample lift -> {'RIGHT' if lift < fz['insample_lift_pooled'] else 'WRONG'}",
            f"  F3 score >= 3 under 61% -> {'RIGHT' if rule_rate < 0.61 else 'WRONG'} ({rule_rate:.1%})",
            f"  F4 the race does not rise steadily with the score -> {'RIGHT' if not steady else 'WRONG'} ("
            + " / ".join(f"{r:.1%}" if n >= 30 else "n<30" for r, n in rates) + ")",
            f"  F5 the S&P source switch agrees on >= 85% -> {'RIGHT' if agree >= 0.85 else 'WRONG'}",
            f"  LEAD (lift >= 3 points and the 90% interval above zero): {'YES' if lift >= 0.03 and lo > 0 else 'no'}"]
    txt = "\n".join(out)
    LOG_FR.write_text(txt + "\n", encoding="utf-8")
    print(txt)


def main(argv=None):
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--insample", action="store_true")
    g.add_argument("--fetch", action="store_true")
    g.add_argument("--fresh", action="store_true")
    a = ap.parse_args(argv)
    run_insample() if a.insample else (run_fetch() if a.fetch else run_fresh())


if __name__ == "__main__":
    main()
