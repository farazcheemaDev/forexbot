"""GOLD AROUND NFP AND FOMC: follow the move, break the first range, or a straddle - against the same clock time on ordinary days (2026-11-08)

The user, 2026-11-08 (after being told the first seconds of a news release are not reachable by a retail order): "many traders are doing it live, you are not looking rightly" - the idea being to WAIT for the release and then trade gold in the
direction it breaks a level ("if gold starts dropping to a level we sell, if it rises to a level we buy"). The repo had already run the follow-the-move version on gold across ALL US surprises (gold_focus.py G2: from +1 minute -0.5 / -2.2 / -2.6 bp, dead)
but never NFP and FOMC on their own, never the break-of-the-range rule and never a pre-placed straddle. This file does those, with a matched control, and checks the one thing a news test can get wrong: where the fill is.

DESIGN. HistData XAUUSD 1-minute BID bars 2010-01..2026-09 (strategy_analysis/data/histdata/XAUUSD.parquet, t = minute start in ms UTC); events from the ForexFactory calendar (fx_macro_data 'ff_2007_2026.csv'): USD 'Non-Farm Employment Change' at
08:30 New York (199 events 2010-02..2026-09) and 'FOMC Statement' at 14:00 New York (108 events, 2013 on - earlier statements came at 14:15). Control = the SAME New York clock time on every other weekday (no event of that type that day), same rule, same costs.
Costs as gold_focus.py G2: 2.44bp round trip + 0.5bp slippage at news (a normal 1.22 + 0.5 doubled for the post-release spread); the stop-entry rules (B, C) pay 2bp more for stop-order slippage. A minute bar t covers [t, t+1m); the price at time T is
the OPEN of the bar starting at T (else the close of the last bar before T, stale beyond 30 minutes = no price).
  A  FOLLOW      direction = sign(price at T+delay - price at T-1m), enter at T+delay (1, 2, 5 minutes), hold 15 or 60 minutes
  B  BREAK       the user's rule: range = high / low of the first W minutes after the release (W = 5, 15); during the next 60 minutes the first bar that takes out the range is the entry (a bar that takes out BOTH sides = no trade);
                 stop at the opposite side of the range (a gap fills at the open), exit 180 minutes after the range ends
  C  STRADDLE    pending orders +-X bp (5, 10, 20) around the price at T; the first bar that touches one side is the entry, the other side is the stop; a bar that touches BOTH sides is the whipsaw loss (dn / up - 1); exit 120 minutes after T
FILL MODELS for B and C (added after the first run, see AMENDMENT): LEVEL = filled at the trigger level (a gap fills at the open) - zero slippage; CLOSE = at the close of the bar that triggered it (you react inside the minute); EXTREME = at that bar's worst
price in your direction (high for a long). Real fills lie between LEVEL (unreachable) and EXTREME (the floor).
PASS (stated in the chat before the run): net mean > 0 and a positive excess over the control with Welch t >= 2 on BOTH halves (the first 60% of events by date, the rest), for the same cell.

REGISTERED BEFORE THE FIRST RUN (2026-11-08, in the chat)
    P1  Following the first minute after the release is about zero net of costs, with no significant excess over ordinary days at the same clock time.
    P2  Waiting for gold to break the first-5-minute range and trading the break has no significant excess.
    P3  Prior under 10% that anything clears the bar (a few hundred events).
AMENDMENT (same day, after the first run, 11 cells per event type): the straddle at +-5 and +-10bp 'passed' on NFP at +20bp a trade (t +5). That is the result this repo says to hunt a bug for; the cause was the fill (the level fill ignores that the trigger
minute runs tens of bp past the level), so the CLOSE and EXTREME fills were added for B and C (21 cells per event type) and the straddle's trigger statistics were printed. The cell count is 42 in all; the first run's A and B-LEVEL numbers are unchanged.

RESULT (2026-11-08, logs/gold_news_breakout.txt)
    Data checks. The release minute moves gold a median 24.6bp at NFP (3.3bp at the same clock time on ordinary days) and 16.4bp at FOMC (1.3bp). The biggest 1-minute move around an NFP sits in the release minute in 64% of summer and 57% of winter events
    (the rest at +1 / +2), FOMC 39% / 41%: no clock error. A +-5bp straddle triggers in 192 of 199 NFP events and one minute touches BOTH sides in 26% (FOMC 36%); the trigger minute runs a MEDIAN 34.4bp (NFP) / 21.0bp (FOMC) past the level.
    NFP (199 events, split 2020-01-10, bp per trade net). A follow: +1m +1.55 (15m) / +1.65 (60m), +2m +1.87 / +4.40, +5m -4.99 / -2.96; excess over the control +4.7 / +4.4 / +5.1 / +6.9 / -1.9 / -0.3, t +1.79 / +1.10 / +2.16 / +1.85 / -0.79 / -0.09: positive in the
    first two minutes, never t >= 2 on both halves, gone by +5 minutes. B (the user's rule) 5m range: LEVEL -3.71, CLOSE -5.83, EXTREME -10.85 (excess +0.2 / -1.1 / -3.8); 15m range -3.99 / -4.70 / -9.96. C straddle +-5bp: LEVEL +20.41 (t +5.23, halves +4.31 / +2.95, PASS),
    CLOSE -2.82, EXTREME -11.36; +-10bp: LEVEL +19.45 (PASS), CLOSE -1.29, EXTREME -11.75; +-20bp: LEVEL +17.47 (hold t +1.43), CLOSE +1.94, EXTREME -9.87. The only two passing cells are the LEVEL-fill straddle, i.e. the fill model that cannot be had.
    FOMC (108 events, split 2021-04-28). A follow: +1m +2.83 / +2.68, +2m -0.40 / +5.07, +5m +0.72 / +7.17 (excess +2.5 .. +10.5, t +0.70 .. +1.88). B 5m range: LEVEL +9.80, CLOSE +9.03, EXTREME +4.44 (excess +14.9 / +14.5 / +11.1, t +2.29 / +2.29 / +1.73, tune / hold
    t +1.87 / +1.41, +2.05 / +1.27, +1.43 / +1.04); 15m range +5.97 / +5.76 / +1.09 (t +2.01 / +2.03 / +1.46). C: LEVEL +12.27 / +8.02 / +12.77, CLOSE -0.05 / -4.87 / +4.28, EXTREME -7.16 / -14.66 / -7.39. 0 of 21 cells pass.
    Reading. (1) The move is real and large, and a fill at the trigger level would pay +17..+20bp a trade on NFP - but the same straddle filled at the trigger bar's close is about -3bp and at its worst price -11bp: the profit is in the fill (latency, spread, slippage), not in the rule.
    (2) The user's rule on NFP loses, and is no better than an ordinary day. (3) On FOMC the range break is a LEAD, not a result: +9.0bp net at the CLOSE fill on 101 trades, standard error about 6.5bp (t about 1.4 against zero), excess t +2.29 pooled but +2.05 / +1.27 by half, one of
    42 cells; confirming +9bp would take about 200 events (roughly 25 years of meetings). (4) The first two minutes after an NFP show a small continuation (+4..+5bp gross), which decays within 5 minutes and is not significant. gold_focus.py's 'following later loses' stands from +5 minutes.
    Predictions: P1 PARTLY WRONG (NFP net +1.6 .. +4.4bp at +1 / +2 minutes, not zero; none significant on both halves), P2 RIGHT on NFP and by the PASS rule on FOMC (pooled t 2.29, halves 2.05 / 1.27), P3 RIGHT after the fill check (the only passes were the LEVEL-fill artifact).
    Limits. HistData is BID only (the spread at the release is charged as a constant, not measured on gold); no tick data before 2026, so the first seconds cannot be tested here (fx_news_seconds.py: +6bp at 0.5-1s on FX pairs, gone by 2s); the fills are three bounds, not a model; 199 and 108 events are
    small (2 x standard error of a cell's net 5-15bp); the FOMC cells are correlated (one lead, not 21). Nothing in any bot changed; the paper desk can log a manual FOMC / NFP plan (python desk.py plan).
    Tests: 42 (tests/test_gold_news_breakout.py); 41 of 41 planted bugs caught over two rounds, a do-nothing control survived (the first round left 15 alive - all gaps in the tests: hold / exit times indistinguishable on flat price paths,
    boundary touches, short-side stops, unequal sample sizes; one is equivalent at the rule level - the stop IS the opposite trigger - and is pinned through enter() directly). The module reproduces the exploratory run's 60 output lines exactly.

AUDIT (2026-11-08, later; backtest/gold_news_ticks.py): reading (1) is WRONG in its mechanism. On Exness ticks for the 2026 releases a resting
    +-5bp stop fills a median ~9-11bp past the level on NFP (0-6bp on CPI / FOMC), not the bar's 34bp run, and the tick result tracks the LEVEL
    fill, not the CLOSE (the CLOSE fill is a manual entry after the minute ends). Re-scored with 10bp of entry slippage, the NFP +-5 straddle is
    +11.1bp a trade (t 2.45; holdout +7.4, t 1.1): a weak lead, not an artifact, not a pass. CPI tested there too: dead.

    python -m backtest.gold_news_breakout      writes logs/gold_news_breakout.txt        tests: python tests/test_gold_news_breakout.py
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

LOG = ROOT / "logs" / "gold_news_breakout.txt"
MIN = 60_000
NEWS_COST = (2.44 + 0.5) / 1e4          # round trip + slippage at news, as gold_focus.py G2
STOP_SLIP = 2.0 / 1e4                   # extra for a stop-entry (rules B and C)
TUNE = 0.60
NY = "America/New_York"
STALE = 30 * MIN


class Bars:
    """1-minute bars: t = bar start in ms UTC (sorted, unique), o / h / l / c prices."""

    def __init__(self, t, o, h, l, c):  # noqa: E741
        self.t = np.asarray(t, np.int64)
        self.o, self.h, self.l, self.c = (np.asarray(x, float) for x in (o, h, l, c))

    def px_at(self, t):
        """price at time t: the open of the bar starting at t, else the close of the last bar before t (stale > 30 min -> nan)."""
        i = np.searchsorted(self.t, t)
        if i < len(self.t) and self.t[i] == t:
            return self.o[i]
        if i == 0 or t - self.t[i - 1] > STALE:
            return np.nan
        return self.c[i - 1]


def load_gold() -> Bars:
    from backtest import fx_intraday_pub as fip
    d = pd.read_parquet(fip.HD / "XAUUSD.parquet").sort_values("t").drop_duplicates("t")
    return Bars(d["t"].to_numpy(np.int64), d["o"], d["h"], d["l"], d["c"])


# ----------------------------------------------------------------------------------------------- rules
def rule_a(b: Bars, T, delay, hold):
    te = T + delay * MIN
    p0, pe, px = b.px_at(T - MIN), b.px_at(te), b.px_at(te + hold * MIN)
    if np.isnan([p0, pe, px]).any() or pe == p0:
        return np.nan, np.nan
    g = np.sign(pe - p0) * (px / pe - 1)
    return g, g - NEWS_COST


def manage(b: Bars, start, jent, dirn, stop, t_exit):
    """from bar `start` on: pessimistic stop (a bar that touches the stop is stopped; a gap past it fills at the open)."""
    k = start
    while k < len(b.t) and b.t[k] < t_exit:
        if dirn > 0 and b.l[k] <= stop:
            return min(stop, b.o[k]) if k > jent else stop
        if dirn < 0 and b.h[k] >= stop:
            return max(stop, b.o[k]) if k > jent else stop
        k += 1
    return b.px_at(t_exit)


def enter(b: Bars, fill, j, dirn, level):
    """fill model for a stop order triggered inside bar j: LEVEL (at the trigger, a gap at the open), CLOSE (the bar's close),
    EXTREME (the bar's worst price in your direction). Returns the entry price and the first bar the stop can act on."""
    if fill == "level":
        return (max(level, b.o[j]) if dirn > 0 else min(level, b.o[j])), j
    if fill == "close":
        return b.c[j], j + 1
    return (b.h[j] if dirn > 0 else b.l[j]), j + 1


def rule_b(b: Bars, T, w, fill="level"):
    te = T + w * MIN
    i0, i1 = np.searchsorted(b.t, T), np.searchsorted(b.t, te)
    if i1 - i0 < max(2, w // 2):
        return np.nan, np.nan
    hi, lo = b.h[i0:i1].max(), b.l[i0:i1].min()
    j, end = i1, np.searchsorted(b.t, te + 60 * MIN)
    while j < min(end, len(b.t)):
        up, dn = b.h[j] > hi, b.l[j] < lo
        if up and dn:
            return np.nan, np.nan                                     # ambiguous bar: no trade
        if up or dn:
            dirn = 1 if up else -1
            entry, start = enter(b, fill, j, dirn, hi if up else lo)
            ex = manage(b, start, j, dirn, lo if up else hi, te + 180 * MIN)
            if np.isnan(ex):
                return np.nan, np.nan
            g = dirn * (ex / entry - 1)
            return g, g - NEWS_COST - STOP_SLIP
        j += 1
    return np.nan, np.nan


def rule_c(b: Bars, T, x, fill="level"):
    p0 = b.px_at(T)
    if np.isnan(p0):
        return np.nan, np.nan
    up, dn = p0 * (1 + x / 1e4), p0 * (1 - x / 1e4)
    j, end = np.searchsorted(b.t, T), np.searchsorted(b.t, T + 60 * MIN)
    while j < min(end, len(b.t)):
        u, v = b.h[j] >= up, b.l[j] <= dn
        if u and v:                                                   # whipsaw inside one bar: in on one side, stopped on the other
            g = dn / up - 1
            return g, g - NEWS_COST - STOP_SLIP
        if u or v:
            dirn = 1 if u else -1
            entry, start = enter(b, fill, j, dirn, up if u else dn)
            ex = manage(b, start, j, dirn, dn if u else up, T + 120 * MIN)
            if np.isnan(ex):
                return np.nan, np.nan
            g = dirn * (ex / entry - 1)
            return g, g - NEWS_COST - STOP_SLIP
        j += 1
    return np.nan, np.nan


def trigger_stats(b: Bars, ev, x):
    """for the straddle: events that trigger, how many touch both sides inside ONE minute, and how far past the level the trigger bar runs (bp)."""
    both = n = 0
    run = []
    for T in ev:
        p0 = b.px_at(T)
        if np.isnan(p0):
            continue
        up, dn = p0 * (1 + x / 1e4), p0 * (1 - x / 1e4)
        j, end = np.searchsorted(b.t, T), np.searchsorted(b.t, T + 60 * MIN)
        while j < min(end, len(b.t)):
            u, v = b.h[j] >= up, b.l[j] <= dn
            if u or v:
                n += 1
                if u and v:
                    both += 1
                else:
                    run.append(((b.h[j] - up) / p0 if u else (dn - b.l[j]) / p0) * 1e4)
                break
            j += 1
    return both, n, (np.median(run) if run else np.nan), (np.mean(run) if run else np.nan)


CELLS = ([(f"A follow, +{dl}m, hold {h}m", "A", dict(delay=dl, hold=h)) for dl in (1, 2, 5) for h in (15, 60)]
         + [(f"B break {w}m range, {f}", "B", dict(w=w, fill=f)) for w in (5, 15) for f in ("level", "close", "extreme")]
         + [(f"C straddle +-{x}bp, {f}", "C", dict(x=x, fill=f)) for x in (5, 10, 20) for f in ("level", "close", "extreme")])


def run_cell(b: Bars, kind, params, T):
    return {"A": rule_a, "B": rule_b, "C": rule_c}[kind](b, T, **params)


# ----------------------------------------------------------------------------------------------- events / controls / statistics
def ny(ts):
    return pd.DatetimeIndex(ts).tz_localize("UTC").tz_convert(NY)


def to_ms(idx) -> np.ndarray:
    return np.asarray((pd.DatetimeIndex(idx) - pd.Timestamp("1970-01-01")) // pd.Timedelta(milliseconds=1), dtype=np.int64)


def at_ny_clock(ev_utc, hour, minute):
    """the events whose New York wall-clock time is hour:minute (statements before 2013 came at 14:15, not 14:00)."""
    ev = pd.DatetimeIndex(ev_utc)
    lt = ny(ev)
    return ev[(lt.hour == hour) & (lt.minute == minute)]


def control_times(ev_utc, hour, minute, start, end) -> np.ndarray:
    """ms UTC of hour:minute New York time on every weekday in [start, end] that has no event (by New York date)."""
    ev_days = set(ny(pd.DatetimeIndex(ev_utc)).date)
    days = [x for x in pd.bdate_range(start, end) if x.date() not in ev_days]
    return np.array([int(pd.Timestamp(f"{x.date()} {hour:02d}:{minute:02d}", tz=NY).tz_convert("UTC").value // 10**6) for x in days], dtype=np.int64)


def welch(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    a, b = a[np.isfinite(a)], b[np.isfinite(b)]
    if len(a) < 5 or len(b) < 5:
        return np.nan
    return (a.mean() - b.mean()) / np.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b))


def verdict(ne, nc, early, cearly):
    """the registered bar for one cell: net > 0 and excess > 0 with Welch t >= 2 on BOTH halves. ne / nc are per-event / per-control-day nets (bp)."""
    ne, nc = np.asarray(ne, float), np.asarray(nc, float)
    m = np.isfinite(ne)
    t_a, t_b = welch(ne[early], nc[cearly]), welch(ne[~early], nc[~cearly])
    ex_a = np.nanmean(ne[early]) - np.nanmean(nc[cearly])
    ex_b = np.nanmean(ne[~early]) - np.nanmean(nc[~cearly])
    ok = bool(np.nanmean(ne[early]) > 0 and np.nanmean(ne[~early]) > 0 and ex_a > 0 and ex_b > 0 and t_a >= 2 and t_b >= 2)
    return dict(taken=int(m.sum()), net=float(np.nanmean(ne)), ctl=float(np.nanmean(nc)), excess=float(np.nanmean(ne) - np.nanmean(nc)),
                t=welch(ne, nc), t_a=t_a, t_b=t_b, se2=float(2 * np.nanstd(ne, ddof=1) / np.sqrt(m.sum())), ok=ok)


def run(b: Bars, ff, label, name, hour, minute):
    """one event type; returns (printed lines, number of passing cells)."""
    usd = ff[(ff.currency == "USD") & (ff.name == name)]
    ev_utc = pd.DatetimeIndex(pd.to_datetime(usd.utc))
    ev_utc = ev_utc[(ev_utc >= "2010-02-01") & (ev_utc <= "2026-09-20")]
    ev_utc = at_ny_clock(ev_utc, hour, minute)
    ev = to_ms(ev_utc)
    ctl = control_times(ev_utc, hour, minute, "2010-02-01", "2026-09-20")
    assert len(ev) > 50 and len(ctl) > 1000 and ev[0] > 1.2e12, "event table is empty or in the wrong time unit"
    cut = ev[int(len(ev) * TUNE)]
    out = [f"==== {label}: {len(ev)} events ({pd.to_datetime(ev[0], unit='ms').date()} .. {pd.to_datetime(ev[-1], unit='ms').date()}), "
           f"{len(ctl)} control days at {hour:02d}:{minute:02d} New York; split {pd.to_datetime(cut, unit='ms').date()}"]
    # clock check: the largest 1-minute move around the release should sit in the release minute, summer AND winter
    offs = {"summer": [], "winter": []}
    for T in ev:
        i0, i1 = np.searchsorted(b.t, T - 15 * MIN), np.searchsorted(b.t, T + 15 * MIN)
        if i1 - i0 < 20:
            continue
        r = np.abs(np.diff(b.c[i0:i1]))
        off = int((b.t[i0 + 1 + int(np.argmax(r))] - T) // MIN)
        summer = ny([pd.to_datetime(T, unit="ms")])[0].utcoffset().total_seconds() == -4 * 3600
        offs["summer" if summer else "winter"].append(off)
    for k, v in offs.items():
        out.append(f"   clock check {k:<6}: n {len(v):>3}, biggest 1-min move at offset 0 in {np.mean(np.array(v) == 0) * 100:.0f}% "
                   f"(offsets {dict(Counter(v).most_common(3))})")
        if len(v) >= 20 and Counter(v).most_common(1)[0][0] != 0:
            raise RuntimeError(f"{label} {k}: the biggest 1-minute move is not in the release minute - the calendar clock is off")
    mv = lambda ts: np.array([abs(b.px_at(T + MIN) / b.px_at(T) - 1) * 1e4 for T in ts])  # noqa: E731
    out.append(f"   release-minute |move|: event median {np.nanmedian(mv(ev)):.1f}bp vs control {np.nanmedian(mv(ctl[::3])):.1f}bp")
    for x in (5, 10, 20):
        bo, n, med, mean = trigger_stats(b, ev, x)
        out.append(f"   straddle +-{x}bp: triggered in {n} events, both sides touched inside ONE minute in {bo} ({bo / max(n, 1) * 100:.0f}%); "
                   f"trigger bar runs past the level by median {med:.1f}bp / mean {mean:.1f}bp (the slippage a level fill ignores)")
    out.append(f"   {'rule':<34}{'taken':>6}{'gross':>8}{'net':>8}{'ctl net':>9}{'excess':>8}{'t':>7}{'tune t':>8}{'hold t':>8}{'2se':>6}  verdict")
    npass = 0
    early, cearly = ev < cut, ctl < cut
    for lab, kind, params in CELLS:
        res_e = np.array([run_cell(b, kind, params, T) for T in ev])
        res_c = np.array([run_cell(b, kind, params, T) for T in ctl])
        ge, ne, nc = res_e[:, 0] * 1e4, res_e[:, 1] * 1e4, res_c[:, 1] * 1e4
        if np.isfinite(ne).sum() < 8:
            out.append(f"   {lab:<34}{int(np.isfinite(ne).sum()):>6}  too few trades")
            continue
        v = verdict(ne, nc, early, cearly)
        npass += v["ok"]
        out.append(f"   {lab:<34}{v['taken']:>6}{np.nanmean(ge):>+8.2f}{v['net']:>+8.2f}{v['ctl']:>+9.2f}{v['excess']:>+8.2f}{v['t']:>+7.2f}"
                   f"{v['t_a']:>+8.2f}{v['t_b']:>+8.2f}{v['se2']:>6.1f}  {'PASS' if v['ok'] else 'fail'}")
    out.append(f"   cells passing both halves: {npass} of {len(CELLS)}   (bp per trade; 2se = smallest mean that would reach t 2 on this sample)")
    return out, npass


def main():
    from backtest import fx_macro_data as md
    b, ff = load_gold(), md.load("ff_2007_2026.csv")
    lines = []
    for label, name, hour, minute in (("NFP (8:30 New York)", "Non-Farm Employment Change", 8, 30),
                                       ("FOMC statement (14:00 New York, 2013 on)", "FOMC Statement", 14, 0)):
        out, _ = run(b, ff, label, name, hour, minute)
        lines += [""] + out
    text = "\n".join(lines).strip()
    LOG.write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
