"""JASON SHAPIRO'S COT CONTRARIAN PROCESS, AS THE tradermonty/claude-trading-skills SKILLS WRITE IT (2026-10-26)

THE USER (2026-10-26): "check all of them [the Claude trading skills] and see if we can take something from them, and do not
assume that because we tested something already it is certified wrong". This file implements the one skill chain whose
rules are written as code, exactly:
  STEP 1  cot-contrarian-detector: COT Index = (net - min) / (max - min) x 100 over the last 156 weeks (including this one),
          net = large speculators' long - short. CROWDED_LONG >= 90, CROWDED_SHORT <= 10.
  STEP 3  technical-analyst/scripts/weekly_price_action.py, on COMPLETED weekly bars, signal window = the last 4 weeks:
          weekly key reversal (a new 13-week high, then a close below the prior week's low), failed extreme (a poke above
          the 52-week high that closes back below it), failed breakout (a weekly close above the 52-week high followed within
          3 weeks by a close back below it); mirror for crowded shorts. CONTINUATION VETO: a new 52-week closing extreme in
          the crowd's direction AFTER the newest signal -> not confirmed. CONFIRMED = a signal and no veto.
  STEP 2  (news-reaction failure) is a manual / web-search step in the skills and CANNOT be backtested here; it is left out.
          Every number below is therefore steps 1 + 3 only. Said once, here, so it is never read as the full process.
  ENTRY   against the crowd (short a crowded-long currency, long a crowded-short one) at the next Monday noon fix after the
          COT report (positions as of Tuesday, published Friday) - the machinery of fx_tff.py / fx_drivers.py.
  EXIT    the skills' own: positioning normalises (COT Index back to 50) OR the stop at the crowd's swing extreme (the 13-week
          high / low at entry, read on the last completed weekly close). My ADDITION, for a bounded test: a 26-week cap.
DATA    7 currency futures (cot.csv, CFTC legacy report, 1995-2026) against USD; Fed H.10 noon fix (1996-); EXNESS costs and
        swaps (fx_drivers.COST, the user's demo account). tune = first 60% of the weekly series.

VARIANTS (all with the same machinery)
  S     steps 1 + 3, the full exit (normalise / stop / 26 weeks)                   <- THE TEST
  C1    step 1 only (crowding, no confirmation), same exit
  C2    step 3 only (the weekly pattern in EITHER direction, no COT), 8 weeks fixed, same stop
  S8    S's entries held a FIXED 8 weeks, no stop (information content)
  F8    S8 with the side FLIPPED (do the confirmed reversals actually continue?)
  C1_8  C1's entries held 8 weeks fixed
  C2_8  C2's entries held 8 weeks fixed, no stop

REGISTERED BEFORE THE FIRST RUN (2026-10-26)
  S1  C1 (crowding alone) loses at Exness (net <= 0 per active week), as fx_tff.py's fade-the-crowd did.
  S2  S makes fewer than 80 trades in 30 years (the confirmation is rare), and its Exness result does not pass both halves
      (t >= 2 on each); at most a LEAD.
  S3  Confirmation adds little over the price pattern alone: |S8 - C2_8| < 0.3% a trade.
  S4  F8 (flipped) is not positive either: no side of the confirmed reversal pays after costs.
NULL TEST (added 2026-10-26 after the first run showed S at +0.35% a trade before costs and its mirror F8 at -0.33%, with the
  halves disagreeing): shift the whole COT Index panel in time by a random offset (400 draws, 26..N-26 weeks, circular) so
  how often and how clustered crowding is stays but its link to price is cut; rerun S and S8 on each. REGISTERED BEFORE IT RUNS:
  N1  the share of shifted panels whose S8 spot mean per trade is >= the real +0.33% is above 0.10 (chance does this often).
  N2  the share whose S holdout weekly mean is >= the real one is above 0.05.
  Reading: both above -> what price patterns plus any crowd give by luck; either under 0.05 -> a real lead.
PASS    S has net > 0 and t >= 2 on BOTH halves (weekly series, fd.stat) AND beats C1 and C2 on both halves.
LEAD    S net > 0 on both halves, pooled t >= 2, one half under t 2 - a thing to record forward, never a pass.

    python -m backtest.cot_shapiro
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest import fx_drivers as fd  # noqa: E402
from backtest import fx_macro_data as md  # noqa: E402

LOG = ROOT / "logs" / "cot_shapiro.txt"
CCY = fd.CCY
LOOK_IDX, HI, LO, MID = 156, 90.0, 10.0, 50.0
SWING, EXTREME, RECENT, MINW, CAP, FIX = 13, 52, 4, 30, 26, 8


# ------------------------------------------------------------------ the skills' weekly detectors (completed bars 0..n-1)

def key_reversal(H, L, C, n, long_crowd):
    for i in range(n - 1, max(n - RECENT, 1) - 1, -1):       # most recent first
        a = max(0, i - SWING)
        if a == i:
            continue
        if long_crowd:
            if H[i] > H[a:i].max() and C[i] < L[i - 1]:
                return i
        elif L[i] < L[a:i].min() and C[i] > H[i - 1]:
            return i
    return None


def failed_extreme(H, L, C, n, long_crowd):
    for i in range(n - 1, max(n - RECENT, 0) - 1, -1):
        a = max(0, i - EXTREME)
        if a == i:
            continue
        if long_crowd:
            lv = H[a:i].max()
            if H[i] > lv and C[i] < lv:
                return i
        else:
            lv = L[a:i].min()
            if L[i] < lv and C[i] > lv:
                return i
    return None


def failed_breakout(H, L, C, n, long_crowd):
    rs = max(0, n - RECENT)
    best = None
    for b in range(max(0, rs - 3), n - 1):
        a = max(0, b - EXTREME)
        if a == b:
            continue
        lv = H[a:b].max() if long_crowd else L[a:b].min()
        if not ((C[b] > lv) if long_crowd else (C[b] < lv)):
            continue
        for f in range(b + 1, min(b + 3, n - 1) + 1):
            if (C[f] < lv) if long_crowd else (C[f] > lv):
                if f >= rs and (best is None or f > best):
                    best = f
                break
    return best


def continuation(C, n, long_crowd, newest):
    start = (newest + 1) if newest is not None else max(0, n - RECENT)
    for i in range(max(start, 0), n):
        a = max(0, i - EXTREME)
        if a == i:
            continue
        if (C[i] > C[a:i].max()) if long_crowd else (C[i] < C[a:i].min()):
            return True
    return False


def confirmed(H, L, C, n, long_crowd) -> bool:
    if n < MINW:
        return False
    sig = [x for x in (key_reversal(H, L, C, n, long_crowd), failed_extreme(H, L, C, n, long_crowd),
                       failed_breakout(H, L, C, n, long_crowd)) if x is not None]
    newest = max(sig) if sig else None
    if continuation(C, n, long_crowd, newest):
        return False
    return newest is not None


# ------------------------------------------------------------------ data

def build():
    cot = md.load("cot.csv")
    net = (cot.nc_long - cot.nc_short).to_frame("net").join(cot[["date", "ccy"]])
    p = net.pivot_table(index="date", columns="ccy", values="net")[CCY]
    mn, mx = p.rolling(LOOK_IDX, min_periods=LOOK_IDX).min(), p.rolling(LOOK_IDX, min_periods=LOOK_IDX).max()
    idx = (p - mn) / (mx - mn).replace(0, np.nan) * 100
    idx.index = idx.index + pd.Timedelta(days=3)                      # published Friday
    starts, ret, nights = fd.grid("W")
    ci = fd.asof(idx, starts)[CCY]
    fx = md.load("fx_h10.csv")[CCY].dropna(how="all")
    fx = fx[fx.index >= "1996-01-01"]
    px = fx.reindex(starts).ffill(limit=3)
    wk = fx.index.to_period("W-SUN")
    bars = {}
    for c in CCY:
        s = fx[c].dropna()
        g = s.groupby(s.index.to_period("W-SUN"))
        b = pd.DataFrame(dict(o=g.first(), h=g.max(), l=g.min(), c=g.last()))
        bars[c] = b
    return starts, ret, nights, ci, px, bars


def simulate(variant: str, starts, ci, px, bars, cache=None, names=None):
    """Returns pos (weeks x CCY, the position held in the week that STARTS at each Monday) and the trade list.
    `cache` holds the weekly-pattern confirmations (they depend on prices only), so the null test can reuse them."""
    names = list(names or CCY)
    pos = pd.DataFrame(0.0, index=starts, columns=names)
    trades = []
    cache = {} if cache is None else cache

    def cf(c, n, lc, H, L, C):
        key = (c, n, lc)
        if key not in cache:
            cache[key] = confirmed(H, L, C, n, lc)
        return cache[key]

    per = {c: (bars[c].index, bars[c].h.to_numpy(float), bars[c].l.to_numpy(float), bars[c].c.to_numpy(float)) for c in names}
    for c in names:
        pidx, H, L, C = per[c]
        starts_per = starts.to_period("W-SUN")
        nmap = pidx.searchsorted(starts_per, side="left")              # completed weeks = periods before the start's week
        cur, ent_i, side, stop = None, None, 0, None
        for k, s in enumerate(starts):
            n = int(nmap[k])
            v = ci[c].iloc[k]
            if cur is not None:
                held = k - ent_i
                out = False
                fixed = variant in ("S8", "F8", "C1_8", "C2_8")
                if fixed:
                    out = held >= FIX
                else:
                    if variant in ("S", "C1") and np.isfinite(v):
                        out = (v <= MID) if side < 0 else (v >= MID)             # positioning normalised
                    if variant == "C2":
                        out = out or held >= FIX
                    if held >= CAP:
                        out = True
                    if not fixed and n >= 1 and stop is not None:
                        out = out or ((C[n - 1] > stop) if side < 0 else (C[n - 1] < stop))
                if out:
                    trades.append((c, starts[ent_i], s, cur))
                    cur = None
            if cur is None and n >= MINW:
                want = 0
                if variant in ("S", "S8", "F8", "C1", "C1_8"):
                    if np.isfinite(v) and v >= HI:
                        lc = True
                    elif np.isfinite(v) and v <= LO:
                        lc = False
                    else:
                        lc = None
                    if lc is not None and (variant in ("C1", "C1_8") or cf(c, n, lc, H, L, C)):
                        want = -1 if lc else 1
                        if variant == "F8":
                            want = -want
                else:                                                          # C2, C2_8: the pattern alone, either side
                    if cf(c, n, True, H, L, C):
                        want = -1
                    elif cf(c, n, False, H, L, C):
                        want = 1
                if want != 0:
                    cur, ent_i, side = want, k, want
                    a = max(0, n - SWING)
                    stop = (H[a:n].max() if want < 0 else L[a:n].min()) if n > 0 else None
                    if variant == "F8":
                        stop = None
            if cur is not None:
                pos.iat[k, names.index(c)] = cur
        if cur is not None:
            trades.append((c, starts[ent_i], starts[-1], cur))
    return pos, trades


def trade_stats(trades, px, nights_idx, cost=None):
    """cost(c) -> (round-trip spread bp, swap bp a night long, swap bp a night short); default = Exness FX (fd.COST)."""
    cost = cost or (lambda c: fd.COST[c])
    rows = []
    for c, a, b, side in trades:
        if a not in px.index or b not in px.index:
            continue
        p0, p1 = px.at[a, c], px.at[b, c]
        if not (np.isfinite(p0) and np.isfinite(p1)):
            continue
        sp = cost(c)[0]
        sw = cost(c)[1] if side > 0 else cost(c)[2]
        nt = (b - a).days
        spot = side * (p1 / p0 - 1)
        rows.append(dict(ccy=c, t0=a, spot=spot, net=spot - sp / 1e4 + sw * nt / 1e4, weeks=nt / 7))
    return pd.DataFrame(rows)


def null_test(starts, ret, nights, ci, px, bars, pol, draws=400, seed=7):
    rng = np.random.default_rng(seed)
    cache = {}
    base_s8 = trade_stats(simulate("S8", starts, ci, px, bars, cache)[1], px, None).spot.mean()
    pos, _ = simulate("S", starts, ci, px, bars, cache)
    base_ho = fd.stat(fd.run(pos, ret, nights, pol)[2], 52)["ho"]
    n = len(starts)
    s8, ho = [], []
    for _ in range(draws):
        k = int(rng.integers(26, n - 26))
        sh = pd.DataFrame(np.roll(ci.to_numpy(), k, axis=0), index=ci.index, columns=ci.columns)
        t8 = trade_stats(simulate("S8", starts, sh, px, bars, cache)[1], px, None)
        s8.append(t8.spot.mean() if len(t8) else np.nan)
        pp, _ = simulate("S", starts, sh, px, bars, cache)
        ho.append(fd.stat(fd.run(pp, ret, nights, pol)[2], 52)["ho"])
    s8, ho = np.array(s8, float), np.array(ho, float)
    p8, ph = float(np.nanmean(s8 >= base_s8)), float(np.nanmean(ho >= base_ho))
    return ["", f"NULL TEST ({draws} circular shifts of the COT panel; S and S8 rerun on each)",
            f"  S8 spot mean per trade: real {base_s8 * 100:+.3f}% | shifted mean {np.nanmean(s8) * 100:+.3f}% "
            f"(5th-95th {np.nanpercentile(s8, 5) * 100:+.3f}..{np.nanpercentile(s8, 95) * 100:+.3f}) -> share >= real {p8:.3f}",
            f"  S holdout weekly mean (Exness): real {base_ho * 100:+.4f}% | shifted mean {np.nanmean(ho) * 100:+.4f}% "
            f"(5th-95th {np.nanpercentile(ho, 5) * 100:+.4f}..{np.nanpercentile(ho, 95) * 100:+.4f}) -> share >= real {ph:.3f}",
            f"  N1 share > 0.10: {p8:.3f} -> {'RIGHT' if p8 > 0.10 else 'WRONG'}",
            f"  N2 share > 0.05: {ph:.3f} -> {'RIGHT' if ph > 0.05 else 'WRONG'}"]


def main():
    starts, ret, nights, ci, px, bars = build()
    pol = fd.policy_gap(starts)[1]
    L = [f"backtest/cot_shapiro.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; 7 currency futures vs USD, "
         f"{starts.min():%Y-%m-%d} .. {starts.max():%Y-%m-%d} ({len(starts)} Mondays), COT Index {LOOK_IDX} weeks, crowd >= {HI:g} / <= {LO:g}; "
         f"STEPS 1 + 3 ONLY (step 2, news failure, is manual in the skills)", ""]
    L.append(f"  {'variant':6} {'trades':>6} {'median wks':>10} | per TRADE spot {'':>6} net(Exness) {'win':>5} | "
             f"per ACTIVE WEEK, Exness: all {'':>6} tune (t) {'':>9} holdout (t)")
    res = {}
    for v in ("S", "C1", "C2", "S8", "F8", "C1_8", "C2_8"):
        pos, tr = simulate(v, starts, ci, px, bars)
        ts = trade_stats(tr, px, None)
        s_spot, s_carry, s_ex = fd.run(pos, ret, nights, pol)
        e = fd.stat(s_ex, 52)
        res[v] = (ts, e)
        if not len(ts):
            L.append(f"  {v:6} no trades")
            continue
        L.append(f"  {v:6} {len(ts):>6} {ts.weeks.median():>10.1f} | spot {ts.spot.mean() * 100:>+7.2f}% net {ts.net.mean() * 100:>+7.2f}% "
                 f"{(ts.net > 0).mean() * 100:>4.0f}% | {e['mean'] * 100:>+7.3f}% (t {e['t']:+.1f}) | "
                 f"{e['tu'] * 100:>+7.3f}% ({e['t_tu']:+.1f}) | {e['ho'] * 100:>+7.3f}% ({e['t_ho']:+.1f})")
    L.append("")
    s_t, s_e = res["S"]
    L.append(f"  S by currency (trades, net %/trade): " + ", ".join(
        f"{c} {int((s_t.ccy == c).sum())}/{s_t[s_t.ccy == c].net.mean() * 100:+.2f}" for c in CCY if (s_t.ccy == c).any()))
    L.append(f"  S trades by year: " + ", ".join(f"{y} {n}" for y, n in s_t.groupby(s_t.t0.dt.year).size().items()))
    pos_flag = lambda e: e["tu"] > 0 and e["ho"] > 0  # noqa: E731
    c1_t, c1_e = res["C1"]
    c2_t, c2_e = res["C2"]
    passed = (pos_flag(s_e) and s_e["t_tu"] >= 2 and s_e["t_ho"] >= 2 and s_e["tu"] > c1_e["tu"] and s_e["ho"] > c1_e["ho"]
              and s_e["tu"] > c2_e["tu"] and s_e["ho"] > c2_e["ho"])
    lead = pos_flag(s_e) and s_e["t"] >= 2 and not passed
    L += ["", "REGISTERED PREDICTIONS",
          f"  S1 C1 (crowding alone) <= 0 at Exness: per active week {c1_e['mean'] * 100:+.3f}% -> {'RIGHT' if c1_e['mean'] <= 0 else 'WRONG'}",
          f"  S2 S makes < 80 trades ({len(s_t)}) and does not pass both halves -> "
          f"{'RIGHT' if len(s_t) < 80 and not passed else 'WRONG'}",
          f"  S3 |S8 - C2_8| < 0.3% a trade: {res['S8'][0].net.mean() * 100:+.2f}% vs {res['C2_8'][0].net.mean() * 100:+.2f}% -> "
          f"{'RIGHT' if abs(res['S8'][0].net.mean() - res['C2_8'][0].net.mean()) < 0.003 else 'WRONG'}",
          f"  S4 F8 (flipped) not positive: net {res['F8'][0].net.mean() * 100:+.2f}% a trade -> "
          f"{'RIGHT' if res['F8'][0].net.mean() <= 0 else 'WRONG'}",
          f"  VERDICT: {'PASS' if passed else ('LEAD' if lead else 'NO PASS, NO LEAD')}"]
    if "--null" in sys.argv:
        L += null_test(starts, ret, nights, ci, px, bars, pol)
    txt ="\n".join(L)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
