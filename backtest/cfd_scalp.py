"""THE CRYPTO SCALPING MENU ON NASDAQ, US30, GOLD AND FOREX - AT EXNESS'S REAL SPREADS (2026-10-12)

THE USER (2026-10-12): "you have all the recent studies we conducted on his strategy and also the scalping strategies we
applied on crypto ... and also other that we didnt apply on nasdaq or forex i think we should give it a shot"

WHY THIS IS NOT THE DOGE TEST AGAIN. On DOGE the 228-rule menu (doge_adapt.py) lost exactly the fee: 12bp a round trip,
which is most of a 1-minute move there. An Exness Standard account charges no commission, only the spread, and on the US
indices and gold the spread is a far smaller share of a minute's move. If the rules hold a small GROSS edge that the
crypto fee hid, it shows here. (His own pattern as a rule was already tested on NASDAQ - his_micro.py, 18 of 18 cells
lose - and is not repeated.)

DATA   backtest/mt5_1m.py: 1-minute MID bars built from every Exness tick, with the spread at each minute's first tick;
       ticks start late Dec 2025 / Jan 2026 on this account, so ~9 months, to 2026-10-09.
RULES  doge_adapt.py's 228, unchanged (vwap fade, Bollinger re-entry, volume breakout, EMA pullback, level bounce,
       opening-range breakout, RSI fades x 1m/5m x both/long/short x 1-2 ATR stop x 1R/2R), with two changes CFDs need:
       - the third ORB session is 09:30 NEW YORK (= DOGE's 13:30 UTC in summer, 14:30 UTC in winter);
       - the time stop (30 min on 1m, 120 min on 5m) runs on the CLOCK, so the daily break or a weekend cannot stretch a
         trade - a position open across a break carries the gap, as a real one would.
COSTS  each trade pays half the spread at its entry minute's first tick and half the average spread of its exit minute
       (a mid-price trade crossing the spread both ways); no commission (Standard account); one night's swap (forex.py's
       measured rates) on a trade open across 21:00 UTC.
TESTS  A  the fee toll: median round-trip spread / median 1-minute ATR(14), beside DOGE's 12bp
       B  every rule over the whole period, net: share positive; share positive at ZERO cost; tune = first 60% of days,
          holdout = the rest. SURVIVOR = net t > 2 by DAY on BOTH halves (if independent, ~0.05% of rules by chance)
       C  RANDOM entries (1% of bars, random side) in the same brackets: the cost-only line
       D  walk-forward "pick the recent winner" (6h/12h/24h/3d/7d windows, 6-hour blocks) - the user's DOGE method

REGISTERED BEFORE THE RUN (2026-10-12, before any rule was run; only a 5-day EURUSD smoke test of the fetcher had been seen)
    Q1  Fee toll (spread / 1m ATR): DOGE ~0.8; EURUSD / GBPUSD / USDJPY 0.4-1.0; XAUUSD, USTEC, US30 0.1-0.3.
    Q2  Survivors: 0-2 of the 1,368 instrument-rules in total, none on the forex majors.
    Q3  Net-positive share over the whole period: forex majors under 10% of rules; indices and gold 10-40% (a small
        cost lets noise fall on either side) - and most of those positive on one half only.
    Q4  Random entries lose about the spread on every instrument (gross within 2 se of zero).
    Q5  Walk-forward: no instrument-window nets > 0 a trade with t > 2; picking the recent winner beats a random
        positive rule by 2 se in at most 1 of the 30 instrument-windows.

RESULT (2026-10-11 20:42 UTC, logs/cfd_scalp.txt; 2026-01-01 .. 2026-10-09, holdout from 2026-06-19, 1,368 rules)
    - Q1 RIGHT: the spread is 0.12 (gold), 0.21 (US30), 0.24 (NASDAQ) of a 1-minute ATR, and 0.57-0.68 on the forex
      majors. DOGE's 12bp is 1.73 of its 1m ATR (6.94bp) - the ~0.8 written for DOGE was too low, so the cost advantage
      the test was built on is even larger than assumed: 7-14x on the indices and gold.
    - The cost is not what kills these rules here. Before ANY cost the median rule makes -0.08 (NASDAQ), -0.02 (US30),
      -0.03 (gold), +0.00 / +0.02 / +0.03bp (EUR / GBP / JPY) a trade, and 38-64% of rules are positive at zero cost -
      a coin flip. Every entry family's median rule is within +-0.6bp gross on every instrument except gold.
    - Q2 RIGHT: 0 survivors of 1,368 (t > 2 by day on both halves). The best on the weaker half is gold's 5m breakout20
      long 2 ATR / 2R: +4.95bp a trade, t +1.1 tune / +2.0 holdout - gold's 2026 rise, long side only.
    - Q3 WRONG: net-positive rules NASDAQ 3%, US30 4%, gold 18%, forex 0-1% (predicted 10-40% on indices and gold): the
      indices' rules sit slightly BELOW zero gross, so the small spread still turns almost all of them negative.
    - Q4 right in substance, wrong in letter: random entries lose 0.22-0.91bp net on every instrument (about the spread),
      but their gross is +0.06..+0.38bp, 2.0-2.4 se above zero on four of six (a slight trend at the bracket scale).
    - Q5 RIGHT: picking the recent winner loses at every window on every instrument (-0.001% to -0.011% a trade, t up
      to -11 on the forex majors) and never beats a random positive rule by 2 se; on forex the "persistence" (rho
      +0.29..+0.45) is the spread again - busy rules lose in every window, as on DOGE.
    Reading: the user's DOGE method and the 228 retail rules fail on NASDAQ, US30, gold and forex for the same reason
    they failed on DOGE - the entries carry no direction (gross ~0) - and NOT because of the cost. A 14x cheaper market
    shrinks the loss to the spread; it cannot make a coin flip pay.

    python -m backtest.cfd_scalp                 (needs backtest/mt5_1m.py's cache)
"""
from __future__ import annotations

import itertools
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest import doge_adapt as da  # noqa: E402
from backtest import mt5_1m  # noqa: E402

LOG = ROOT / "logs" / "cfd_scalp.txt"
MIN, DAY, H6 = 60_000, 86_400_000, 6 * 3_600_000
SYMS = ["USTECm", "US30m", "XAUUSDm", "EURUSDm", "GBPUSDm", "USDJPYm"]
SWAP_BP = {"XAUUSDm": 1.25, "EURUSDm": 0.49, "GBPUSDm": 0.49, "USDJPYm": 0.49, "USTECm": 2.04, "US30m": 1.83}  # forex.py
TUNE = 0.60


def orb_ny(b: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """doge_adapt's ORB with the third session at 09:30 New York: first 1m close beyond the first 30 minutes' range
    within the next 3 hours, for 00:00 UTC, 08:00 UTC and 09:30 ET."""
    t, h, l, c = b.t.to_numpy(), b.h.to_numpy(), b.l.to_numpy(), b.c.to_numpy()
    lo_s, sh_s = np.zeros(len(t), bool), np.zeros(len(t), bool)
    day = t // DAY
    for dy in np.unique(day):
        d0 = int(dy) * DAY
        ny = pd.Timestamp(d0, unit="ms").strftime("%Y-%m-%d") + " 09:30"
        ny_ms = int(pd.Timestamp(ny, tz="America/New_York").tz_convert("UTC").timestamp() * 1000)
        for s0 in (d0, d0 + 8 * 3_600_000, ny_ms):
            i0, i1 = np.searchsorted(t, s0), np.searchsorted(t, s0 + 30 * MIN)
            if i1 - i0 < 30:
                continue
            rh, rl = h[i0:i1].max(), l[i0:i1].min()
            j1 = np.searchsorted(t, s0 + 210 * MIN)
            up = np.flatnonzero(c[i1:j1] > rh)
            dn = np.flatnonzero(c[i1:j1] < rl)
            if len(up):
                lo_s[i1 + up[0]] = True
            if len(dn):
                sh_s[i1 + dn[0]] = True
    return lo_s, sh_s


def simulate(d1, b, tf, lo_sig, sh_sig, A, stop_k, tgt_r, swap_bp):
    """doge_adapt.simulate with a clock time stop and per-trade spread + swap: (entry_t, exit_t, gross, net)."""
    t1, o1, h1, l1, c1 = (d1[k].to_numpy() for k in ("t", "o", "h", "l", "c"))
    spo, spm = d1.sp_o.to_numpy(), d1.sp.to_numpy()
    pos1 = {int(x): i for i, x in enumerate(t1)}
    H = da.TIME_STOP[tf]
    ev = sorted([(i, 1) for i in np.flatnonzero(lo_sig)] + [(i, -1) for i in np.flatnonzero(sh_sig)])
    ct = b.close_t.to_numpy()
    free_t, rows = -1, []
    for i, side in ev:
        if ct[i] <= free_t:
            continue
        j0 = pos1.get(int(ct[i]))
        if j0 is None:
            continue
        jn = np.searchsorted(t1, t1[j0] + H * MIN)                   # bars inside the clock time stop
        if jn >= len(t1) or jn - j0 < 2:
            continue
        e = o1[j0]
        dist = stop_k * A[i]
        if not np.isfinite(dist) or dist <= 0:
            continue
        stop, tgt = e - side * dist, e + side * tgt_r * dist
        hh, ll = h1[j0:jn], l1[j0:jn]
        s_hit, t_hit = (ll <= stop, hh >= tgt) if side > 0 else (hh >= stop, ll <= tgt)
        si, ti = np.flatnonzero(s_hit), np.flatnonzero(t_hit)
        n_ = jn - j0
        s0 = si[0] if len(si) else n_
        g0 = ti[0] if len(ti) else n_
        if s0 <= g0 and s0 < n_:
            k = j0 + s0
            x = stop if k == j0 else (min(o1[k], stop) if side > 0 else max(o1[k], stop))
        elif g0 < n_:
            k, x = j0 + g0, tgt
        else:
            k = jn - 1
            x = c1[k]
        gross = side * (x / e - 1)
        cost = (spo[j0] + spm[k]) / 2 / e
        t_out = t1[k] + MIN
        roll = (t1[j0] // DAY) * DAY + 21 * 3_600_000
        if t1[j0] >= roll:
            roll += DAY
        if t_out > roll:
            cost += swap_bp / 1e4
        rows.append((t1[j0], t_out, gross, gross - cost))
        free_t = t_out
    if not rows:
        z = np.zeros(0)
        return np.zeros(0, np.int64), np.zeros(0, np.int64), z, z
    r = np.array(rows)
    return r[:, 0].astype(np.int64), r[:, 1].astype(np.int64), r[:, 2], r[:, 3]


def menu(d1, swap_bp, rng=None):
    rules, rand = {}, {}
    for tf in (1, 5):
        b = da.bars(d1, tf)
        sig, A = da.signals(b, d1, tf)
        if tf == 1:
            warm = np.arange(len(b)) < 240 + 60
            lo, sh = orb_ny(b)
            sig["orb"] = (lo & ~warm, sh & ~warm)
        for name, (lo, sh) in sig.items():
            for side, stop_k, tgt_r in itertools.product(("both", "long", "short"), (1, 2), (1, 2)):
                L_ = lo if side in ("both", "long") else np.zeros_like(lo)
                S_ = sh if side in ("both", "short") else np.zeros_like(sh)
                rules[(f"{tf}m", name, side, stop_k, tgt_r)] = simulate(d1, b, tf, L_, S_, A, stop_k, tgt_r, swap_bp)
        if rng is not None:
            pick = rng.random(len(b)) < 0.01
            pick[: 240 // tf + 60] = False
            up = rng.random(len(b)) < 0.5
            for stop_k, tgt_r in itertools.product((1, 2), (1, 2)):
                rand[(f"{tf}m", "RANDOM", "both", stop_k, tgt_r)] = simulate(d1, b, tf, pick & up, pick & ~up, A,
                                                                              stop_k, tgt_r, swap_bp)
    return rules, rand


def day_t(ent, x):
    """t of the daily sums (days with a trade)."""
    if len(x) < 5:
        return np.nan, 0
    s = pd.Series(x).groupby(ent // DAY).sum()
    if len(s) < 5 or s.std(ddof=1) == 0:
        return np.nan, len(s)
    return float(s.mean() / (s.std(ddof=1) / np.sqrt(len(s)))), len(s)


def instrument(sym, rng):
    d1 = mt5_1m.load(sym)
    d1 = d1[d1.t < int(pd.Timestamp("2026-10-10").timestamp() * 1000)].reset_index(drop=True)
    days = np.unique(d1.t // DAY)
    split = int(days[int(len(days) * TUNE)]) * DAY
    A1 = da.atr(d1.h.to_numpy(), d1.l.to_numpy(), d1.c.to_numpy())
    toll = float(np.median(d1.sp_o / d1.c)) / float(np.nanmedian(A1[300:] / d1.c.to_numpy()[300:]))
    rules, rand = menu(d1, SWAP_BP[sym], rng)
    out = dict(sym=sym, d1=d1, split=split, toll=toll, rules=rules, rand=rand,
               sp_bp=float(np.median(d1.sp_o / d1.c)) * 1e4, atr_bp=float(np.nanmedian(A1[300:] / d1.c.to_numpy()[300:])) * 1e4)
    stats = []
    for k, (ent, ext, g, n) in rules.items():
        if not len(n):
            continue
        tu, ho = ent < split, ent >= split
        t_tu, _ = day_t(ent[tu], n[tu])
        t_ho, _ = day_t(ent[ho], n[ho])
        stats.append(dict(rule=k, n=len(n), net=n.mean(), gross=g.mean(), sum=n.sum(), n_tu=int(tu.sum()), n_ho=int(ho.sum()),
                          net_tu=n[tu].mean() if tu.any() else np.nan, net_ho=n[ho].mean() if ho.any() else np.nan,
                          t_tu=t_tu, t_ho=t_ho))
    out["stats"] = pd.DataFrame(stats)
    return out


def report(res, lines):
    sym, S = res["sym"], res["stats"]
    d1 = res["d1"]
    lines.append(f"== {sym}: {len(d1):,} one-minute bars, {pd.Timestamp(d1.t.min(), unit='ms'):%Y-%m-%d} .. "
                 f"{pd.Timestamp(d1.t.max(), unit='ms'):%Y-%m-%d}; holdout from {pd.Timestamp(res['split'], unit='ms'):%Y-%m-%d}")
    lines.append(f"  A  spread {res['sp_bp']:.2f}bp round trip (median, at a minute's first tick) | 1m ATR {res['atr_bp']:.2f}bp | "
                 f"fee toll {res['toll']:.2f} of a 1-minute ATR")
    pos, gpos = (S["sum"] > 0).mean(), (S.gross > 0).mean()
    both = (S.net_tu > 0) & (S.net_ho > 0)
    surv = S[(S.t_tu > 2) & (S.t_ho > 2)]
    lines.append(f"  B  {len(S)} rules: net positive {pos * 100:.0f}% | positive at ZERO cost {gpos * 100:.0f}% | net positive on "
                 f"BOTH halves {both.mean() * 100:.0f}% | median rule net {S.net.median() * 1e4:+.2f}bp, gross "
                 f"{S.gross.median() * 1e4:+.2f}bp a trade | SURVIVORS (t > 2 by day, both halves): {len(surv)}")
    for r in surv.itertuples():
        lines.append(f"     SURVIVOR {str(r.rule):42} {r.n:5} trades, net {r.net * 1e4:+.2f}bp (tune {r.net_tu * 1e4:+.2f} t {r.t_tu:+.1f} | "
                     f"holdout {r.net_ho * 1e4:+.2f} t {r.t_ho:+.1f})")
    S2 = S.assign(mt=S[["t_tu", "t_ho"]].min(axis=1)).sort_values("mt", ascending=False, kind="stable")
    lines.append("     best five by the weaker half's t:")
    for r in S2.head(5).itertuples():
        lines.append(f"       {str(r.rule):42} {r.n:5} trades, net {r.net * 1e4:+.2f}bp a trade (tune {r.net_tu * 1e4:+.2f} t {r.t_tu:+.1f} | "
                     f"holdout {r.net_ho * 1e4:+.2f} t {r.t_ho:+.1f})")
    fam = S.assign(f=S.rule.map(lambda k: f"{k[0]} {k[1]}")).groupby("f").agg(net=("net", "median"), gross=("gross", "median"),
                                                                           n=("n", "sum"))
    lines.append("     by entry (median rule, bp a trade, net / gross): " + "; ".join(
        f"{f} {r.net * 1e4:+.1f}/{r.gross * 1e4:+.1f}" for f, r in fam.iterrows()))
    rg = np.concatenate([v[2] for v in res["rand"].values()])
    rn = np.concatenate([v[3] for v in res["rand"].values()])
    lines.append(f"  C  RANDOM entries, same brackets: {len(rg)} trades, gross {rg.mean() * 1e4:+.2f}bp (se "
                 f"{rg.std(ddof=1) / np.sqrt(len(rg)) * 1e4:.2f}), net {rn.mean() * 1e4:+.2f}bp a trade")
    # D: walk-forward on NET returns (cost already inside each trade)
    rules = {k: (v[0], v[1], v[3]) for k, v in res["rules"].items() if len(v[3])}
    first = (int(d1.t.min()) // DAY + 8) * DAY
    last = int(d1.t.max()) // H6 * H6 - H6
    starts = np.arange(first, last + 1, H6, dtype=np.int64)
    wf = {}
    for wn, span in da.WINDOWS.items():
        w = da.walk(rules, starts, 0, span)
        wf[wn] = w
        lines.append("  D" + da.fmt(w, f"window {wn}")[1:])
    lines.append("")
    return wf


def main():
    rng = np.random.default_rng(20261012)
    lines = [f"backtest/cfd_scalp.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; doge_adapt.py's 228-rule scalping menu on "
             f"Exness CFDs, 1m mid bars from ticks (backtest/mt5_1m.py), net of the real spread; returns at 1x", ""]
    db = da.bg.fetch("DOGE", 90, quiet=True)
    Ad = da.atr(db.h.to_numpy(), db.l.to_numpy(), db.c.to_numpy())
    doge_atr = float(np.nanmedian(Ad[300:] / db.c.to_numpy()[300:]))
    lines.append(f"DOGE for reference (Bitget, backtest/bitget_1m.py): 1m ATR {doge_atr * 1e4:.2f}bp; fee 12bp = toll "
                 f"{0.0012 / doge_atr:.2f} of a 1-minute ATR; 0 of 228 rules net positive (logs/doge_adapt.txt)")
    lines.append("")
    allS, tolls, wfs = [], {}, {}
    for sym in SYMS:
        try:
            res = instrument(sym, rng)
        except FileNotFoundError:
            lines.append(f"== {sym}: no cache - run backtest/mt5_1m.py")
            continue
        wfs[sym] = report(res, lines)
        tolls[sym] = res["toll"]
        allS.append(res["stats"].assign(sym=sym))
        print("\n".join(lines[-14:]), flush=True)
    A = pd.concat(allS, ignore_index=True)
    surv = A[(A.t_tu > 2) & (A.t_ho > 2)]
    fx = A.sym.isin(["EURUSDm", "GBPUSDm", "USDJPYm"])
    lines.append("REGISTERED PREDICTIONS")
    ok1 = all(0.4 <= tolls[s] <= 1.0 for s in tolls if s in ("EURUSDm", "GBPUSDm", "USDJPYm")) and \
        all(0.1 <= tolls[s] <= 0.3 for s in tolls if s in ("XAUUSDm", "USTECm", "US30m"))
    lines.append(f"  Q1 fee toll: " + ", ".join(f"{s} {v:.2f}" for s, v in tolls.items()) + f" -> {'RIGHT' if ok1 else 'WRONG'}")
    lines.append(f"  Q2 survivors: {len(surv)} of {len(A)} ({int(surv.sym.isin(['EURUSDm', 'GBPUSDm', 'USDJPYm']).sum())} on the forex "
                 f"majors) -> {'RIGHT' if len(surv) <= 2 and not surv.sym.isin(['EURUSDm', 'GBPUSDm', 'USDJPYm']).any() else 'WRONG'}")
    sh = A.groupby("sym").apply(lambda g: (g["sum"] > 0).mean(), include_groups=False)
    ok3 = all(sh[s] < 0.10 for s in sh.index if s in ("EURUSDm", "GBPUSDm", "USDJPYm")) and \
        all(0.10 <= sh[s] <= 0.40 for s in sh.index if s in ("XAUUSDm", "USTECm", "US30m"))
    lines.append("  Q3 net-positive share: " + ", ".join(f"{s} {v * 100:.0f}%" for s, v in sh.items()) + f" -> {'RIGHT' if ok3 else 'WRONG'}")
    good = [(s, w) for s, ws in wfs.items() for w, r in ws.items()
            if len(r["pick_r"]) > 1 and r["pick_r"].sum() > 0
            and r["pick_r"].mean() / (r["pick_r"].std(ddof=1) / np.sqrt(len(r["pick_r"]))) > 2]
    beat = [(s, w) for s, ws in wfs.items() for w, r in ws.items() if len(r["pick_r"]) > 1 and
            (lambda d: d.mean() / (d.std(ddof=1) / np.sqrt(len(d))) > 2)(r["pick_r"] - r["base_r"])]
    lines.append(f"  Q5 walk-forward windows net > 0 with t > 2: {good or 'none'}; beating a random winner by 2 se: {beat or 'none'} "
                 f"-> {'RIGHT' if not good and len(beat) <= 1 else 'WRONG'}")
    lines.append("  (Q4 is read from the C lines above.)")
    txt = "\n".join(lines)
    print(txt)
    LOG.write_text(txt + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
