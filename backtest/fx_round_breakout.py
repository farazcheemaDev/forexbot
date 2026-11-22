"""ROUND-NUMBER BREAKOUT STOPS IN FOREX - the follow-up fx_round_levels.py's first run pointed to (2026-11-15)

WHY (post hoc - say so): fx_round_levels.py found the stop-cascade half of Osler's mechanism REAL and the take-profit
half absent. After a first touch of a big figure the price runs THROUGH it: the fade at the level loses 1.3-1.6 pips
gross at 5-60 minutes, 0.7-1.6 pips more than at arbitrary levels (t -7..-10 on both halves, all 7 pairs, every era);
crossings continue 0.2-1.0 pip more than at arbitrary levels (t +5..+9). The trade that sits on that is the OPPOSITE of
the fade: a resting STOP order just beyond the big figure (a buy stop above it while the price comes from below, a sell
stop below it from above) - the same place the cascading stops sit. Found after looking, so it is judged on a
registered bar and on Exness's own ticks, not on the run that suggested it.

RULE  First touch of a big figure in 60 minutes (fx_round_levels.touch_events, unchanged). Stop order at the level
      +- 0.5 pip in the approach direction. Exit at the close H minutes later (H 15 / 60). One event per pair per 60 min.
BARS  (HistData bid, 2007-2026): entry = level +- 0.5 pip, a trigger the bid must reach. A SELL stop on bid bars is exact
      (it fills on the bid); a BUY stop fills on the ASK, which reaches the trigger before the bid does, so the bar
      version keeps only the buy stops whose BID also got there - it flatters the longs. Shown separately.
      Cost 1.2 pips a round trip. Control: the same stop order at the arbitrary levels (+23/37/63/77 pips).
TICKS (--ticks, Exness MT5, 2026-01..2026-11, Standard account symbols EURUSDm ...): the order simulated on every tick,
      long on the ASK, short on the BID, filled at the first tick at or beyond the trigger (slippage included), exit at
      the opposite side's price H minutes later: the spread and the slippage are the real ones, no cost assumption.
      2026 overlaps the bars' holdout (Jan-Sep), so it is a cost-and-fill check, not an independent sample.

GATE (registered before the first run of this file): per H, round levels, 7 pairs pooled, bars: net of 1.2 pips > 0 with
t >= 2 (pair-days) on BOTH halves AND excess over control > 0 with t >= 2 on BOTH halves, shorts alone (the exact side)
positive on both halves; then the tick check must be net > 0 at Exness's real spread. Pass = a LEAD for the forward
ledger. Fail on ticks = the effect is real and the Standard account's spread eats it.

PREDICTIONS (registered 2026-11-15 before the first run of this file)
  B1  Bars, gross from the trigger: +0.8..+1.2 pips at H=60 on both halves (the fade's -1.6 less the 0.5-pip trigger).
  B2  Bars, net of 1.2 pips: about zero, t < 2 -> no pass at a Standard-account cost.
  B3  Shorts (exact) and longs (flattered) within 0.3 pip of each other gross.
  B4  Ticks 2026: the real spread at these moments averages 0.8-1.5 pips on the m symbols and the fill slips 0.0-0.3 pip
      beyond the trigger; the tick net is negative.

    python -m backtest.fx_round_breakout            # bars
    python -m backtest.fx_round_breakout --ticks    # Exness ticks 2026 (MT5 terminal open)
"""
from __future__ import annotations

import datetime as dt
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backtest import fx_round_levels as R  # noqa: E402

LOG = ROOT / "logs" / "fx_round_breakout.txt"
TLOG = ROOT / "logs" / "fx_round_breakout_ticks.txt"
HS = (15, 60)
TRIG = 0.5          # pips beyond the level


def breakout_frame(pair, d, off_pips, H):
    p = R.pip_of(pair)
    idx, level, appr = R.touch_events(d, off_pips * p, R.GRID_PIPS * p, H, R.THROUGH * p)
    c = d.c.to_numpy()
    entry = level + appr * TRIG * p
    r = appr * (c[idx + H] - entry)
    t = d.t.to_numpy()[idx]
    price = c[idx]
    return pd.DataFrame(dict(pair=pair, t=t, day=t // 86_400_000, side=appr, bp=r / price * 1e4,
                             cost=R.COST_PIPS * p / price * 1e4, pips=r / p))


def bars(pairs=R.PAIRS):
    out, split = {}, {}
    for pair in pairs:
        d = R.load(pair)
        ts = d.t.to_numpy()
        split[pair] = ts[int(len(ts) * 0.6)]
        for H in HS:
            out.setdefault((H, "round"), []).append(breakout_frame(pair, d, 0, H))
            for off in R.CONTROL_OFFSETS:
                out.setdefault((H, "control"), []).append(breakout_frame(pair, d, off, H))
    for k, parts in out.items():
        x = pd.concat(parts, ignore_index=True)
        x["half"] = np.where(x.t < x.pair.map(split), "tune", "hold")
        x["bp_net"] = x.bp - x.cost
        out[k] = x
    L = [f"backtest/fx_round_breakout.py (bars), {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; stop order at the big figure "
         f"+- {TRIG} pip on first touch; cost {R.COST_PIPS} pips", "",
         "H   half  side    events  gross pips  ctl pips | EXCESS bp (t) | net bp (t, pair-days)  net@0.6"]
    verdict = {}
    for H in HS:
        r, c = out[(H, "round")], out[(H, "control")]
        ok = True
        for half in ("tune", "hold"):
            for side, lab in ((0, "all"), (-1, "short"), (1, "long")):
                rr = r[(r.half == half) & ((r.side == side) | (side == 0))]
                cc = c[(c.half == half) & ((c.side == side) | (side == 0))]
                m, t, n = R.day_t(rr)
                ex, ext = R.excess_t(rr, cc)
                L.append(f"{H:<3} {half:<5} {lab:<6} {len(rr):>7}   {rr.pips.mean():+7.2f}   {cc.pips.mean():+6.2f}  | "
                         f"{ex:+5.2f} ({ext:+5.1f}) | {m:+6.2f} ({t:+5.1f}, {n:>5})   {(rr.bp - rr.cost / 2).mean():+6.2f}")
                if side == 0:
                    ok &= m > 0 and t >= 2 and ex > 0 and ext >= 2
                if side == -1:
                    ok &= rr.bp_net.mean() > 0
        verdict[H] = ok
        L.append(f"    H={H}: {'PASS on bars - go to the tick check' if ok else 'no pass on bars'}")
        L.append("")
    L.append("BY PAIR (H=60, both halves, gross pips round | control):  " + "  ".join(
        f"{p} {out[(60, 'round')].query('pair == @p').pips.mean():+.2f}|{out[(60, 'control')].query('pair == @p').pips.mean():+.2f}"
        for p in R.PAIRS))
    txt = "\n".join(L)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)
    return out, verdict


# ---------------------------------------------------------------- ticks (Exness MT5)
def hour_extremes(tk):
    t = tk.time_msc.to_numpy()
    idx_t = pd.to_datetime(t, unit="ms")
    amax = pd.Series(tk.ask.to_numpy(), index=idx_t).rolling("60min", closed="left").max().to_numpy()
    bmin = pd.Series(tk.bid.to_numpy(), index=idx_t).rolling("60min", closed="left").min().to_numpy()
    return amax, bmin


def tick_events(tk, pip, off_pips, H, ext=None):
    """Stop orders on a tick stream (time_msc, bid, ask). Returns rows with real fills."""
    t = tk.time_msc.to_numpy()
    bid, ask = tk.bid.to_numpy(), tk.ask.to_numpy()
    grid, off = R.GRID_PIPS * pip, off_pips * pip
    amax, bmin = ext if ext is not None else hour_extremes(tk)
    first = t - t[0] >= 3_600_000
    rows, last_ev = [], -10**15
    # long: the ask crosses level + TRIG with no ask at/above the level in the previous 60 minutes
    lvl_up = off + grid * (np.floor((amax - off) / grid) + 1)           # the level just above the last hour's high ask
    lvl_dn = off + grid * np.floor((bmin - off) / grid)                  # the level at / below the last hour's low bid
    lvl_dn = np.where(np.isclose((bmin - off) / grid, np.round((bmin - off) / grid)), lvl_dn - grid, lvl_dn)
    # The FIRST TOUCH of a fresh level arms a resting stop at level +- TRIG; it fills on the first tick at or beyond the
    # trigger within 60 minutes (else it is cancelled). (A first version triggered only if the touching tick itself
    # was already past the trigger: any tick between the level and the trigger moved the 'fresh level' up, and it
    # found ~0 events - fixed before reading any result.)
    with np.errstate(invalid="ignore"):
        lg = first & (ask >= lvl_up)
        sh = first & (bid <= lvl_dn)
    cand = np.flatnonzero(lg | sh)
    for i0 in cand:
        if lg[i0] and sh[i0]:
            continue
        side = 1 if lg[i0] else -1
        trig = (lvl_up[i0] + TRIG * pip) if side == 1 else (lvl_dn[i0] - TRIG * pip)
        k1 = np.searchsorted(t, t[i0] + 3_600_000, "right")
        seg = ask[i0:k1] >= trig if side == 1 else bid[i0:k1] <= trig
        if not seg.any():
            continue
        i = i0 + int(np.argmax(seg))
        if t[i] - last_ev < 3_600_000:
            continue
        fill = ask[i] if side == 1 else bid[i]
        j = np.searchsorted(t, t[i] + H * 60_000, "right") - 1
        if j <= i or t[-1] < t[i] + H * 60_000 or t[j] < t[i] + (H - 5) * 60_000:
            continue
        exitp = bid[j] if side == 1 else ask[j]
        rows.append(dict(t=int(t[i]), side=side, pips=side * (exitp - fill) / pip, slip=side * (fill - trig) / pip,
                         spread=(ask[i] - bid[i]) / pip, bp=side * (exitp - fill) / fill * 1e4))
        last_ev = t[i]
    return rows


def ticks(start="2026-01-04", end="2026-11-14"):
    import MetaTrader5 as mt5
    assert mt5.initialize(), mt5.last_error()
    syms = {p: p + "m" for p in R.PAIRS}
    res = []
    weeks = pd.date_range(start, end, freq="7D")
    for pair, sym in syms.items():
        mt5.symbol_select(sym, True)
        pip = R.pip_of(pair)
        for w in weeks:
            a = dt.datetime(w.year, w.month, w.day, tzinfo=dt.timezone.utc)
            tk = mt5.copy_ticks_range(sym, a, a + dt.timedelta(days=7), mt5.COPY_TICKS_ALL)
            if tk is None or len(tk) < 1000:
                continue
            tk = pd.DataFrame(tk)[["time_msc", "bid", "ask"]]
            tk = tk[(tk.bid > 0) & (tk.ask >= tk.bid)].drop_duplicates("time_msc", keep="last").reset_index(drop=True)
            ext = hour_extremes(tk)
            for H in HS:
                for off, cls in [(0, "round")] + [(o, "control") for o in R.CONTROL_OFFSETS]:
                    for row in tick_events(tk, pip, off, H, ext):
                        res.append(dict(row, pair=pair, H=H, cls=cls))
        print(f"{pair}: {sum(r['pair'] == pair for r in res)} events", flush=True)
    mt5.shutdown()
    X = pd.DataFrame(res)
    X["day"] = X.t // 86_400_000
    L = [f"backtest/fx_round_breakout.py --ticks, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; Exness MT5 ticks "
         f"{start}..{end}, 7 majors (m symbols); stop at the level +- {TRIG} pip, filled on the first tick through, exit on "
         "the opposite side H min later (real spread + slippage, no other cost)", "",
         "H   class    side    events  net pips (t, pair-days)   spread at fill  slip beyond trigger"]
    for H in HS:
        for cls in ("round", "control"):
            for side, lab in ((0, "all"), (-1, "short"), (1, "long")):
                x = X[(X.H == H) & (X.cls == cls) & ((X.side == side) | (side == 0))]
                g = x.groupby(["pair", "day"]).pips.mean()
                tt = g.mean() / (g.std(ddof=1) / math.sqrt(len(g))) if len(g) > 2 else float("nan")
                L.append(f"{H:<3} {cls:<8} {lab:<6} {len(x):>6}   {x.pips.mean():+6.2f} ({tt:+5.1f}, {len(g):>4})       "
                         f"{x.spread.mean():5.2f}          {x.slip.mean():+5.2f}")
        r, c = X[(X.H == H) & (X.cls == "round")], X[(X.H == H) & (X.cls == "control")]
        L.append(f"    H={H}: round minus control {r.pips.mean() - c.pips.mean():+.2f} pips")
        rn, cn = r[r.spread <= 2.0], c[c.spread <= 2.0]
        g = rn.groupby(["pair", "day"]).pips.mean()
        L.append(f"    H={H}, fills with spread <= 2 pips only (a bot can skip a blown-out quote): round {rn.pips.mean():+.2f} pips "
                 f"(t {g.mean() / (g.std(ddof=1) / math.sqrt(len(g))):+.1f}, n {len(rn)}), control {cn.pips.mean():+.2f}")
        L.append("")
    L.append("BY PAIR (H=60, round, net pips / spread):  " + "  ".join(
        f"{p} {X[(X.H == 60) & (X.cls == 'round') & (X.pair == p)].pips.mean():+.2f}/"
        f"{X[(X.H == 60) & (X.cls == 'round') & (X.pair == p)].spread.mean():.2f}" for p in R.PAIRS))
    txt = "\n".join(L)
    TLOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)
    X.to_csv(ROOT / "logs" / "fx_round_breakout_ticks.csv", index=False)


if __name__ == "__main__":
    if "--ticks" in sys.argv:
        ticks()
    else:
        bars()
