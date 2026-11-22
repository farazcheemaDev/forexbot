"""THE ONE LEAD THE COMBINATION TESTS LEFT: 'short at the top of the 24h range' - dissected before it is believed (2026-11-15)

THE USER (2026-11-15, /goal): "find an edge that gives good signals - a perfect combination of every signal, or everything you have so far, including the forward data from the Analyst desk."
combo_direction.py (18 gate cells, 0 pass) printed one thing that looked like an edge in its post-hoc DIAGNOSTICS: with a single aligned feature as the whole model, `-a_rng_pos24` at the top 10% of each quarter read selected +0.051R vs all -0.097R
(+0.147, Welch t +4.5, both halves +0.123 / +0.177) on the fixed 1.2% / 2.4% / 24h bracket. Registered there as W4 (no single feature clears +-2 se) - W4 was WRONG. Rules of this repo for a result that looks good: look for the bug first.
THE FIRST BUG IS ALREADY VISIBLE: a_rng_pos24 = rng_pos24 x side and rng_pos24 is in [0, 1], not centred. For a short the aligned value is -pos (<= 0), for a long it is +pos (>= 0); the NEGATED feature is therefore >= 0 for shorts and <= 0 for longs, and
the top 10% of all candidates (half of which are shorts) is essentially ONLY shorts that sit near the TOP of the 24h range. So the diagnostic was a short-only rule compared with an all-bets baseline that is half longs: any drift difference between the sides
(2023-26: alts fell, shorts paid) is credited to the signal.
THIS FILE: (1) the clean definitions - location c = rng_pos24 - 0.5, reversal score = -c x side (long near the low, short near the high), selected per (quarter, SIDE) top 10% so each side is compared with ITS OWN side's candidates; (2) the side drift on its own
(all shorts vs all longs); (3) the pieces: shorts at the high, longs at the low, both; (4) decile profile; (5) matched controls: same side, same quarter, same hour of day and same volatility tercile (the signal clusters on all of them); (6) a circular-shift
null (the selection series shifted by whole days against the outcomes); (7) by year (2022 is before the walk-forward start and no training is involved, so it is an unseen year), by coin, by hour; (8) the other two brackets; (9) slippage; (10) the same frozen rule on
PERPETUALS NOT IN THE FIVE (the PIT top-40 ex the five majors, when their 1h candles are on disk).

REGISTERED BEFORE THE FIRST RUN (2026-11-15; this is a post-hoc lead found after 63 gate cells and 8 diagnostics, so the bar is the repo's bar for a lead: t >= 2 on both halves AND against the same-side control AND on unseen data)
  R1  Once each side is compared with its OWN side's candidates, the short-at-the-high effect shrinks by at least a third (the side drift is a large part of the +0.147); it does not vanish entirely (prior 50% that a +0.05 or larger excess remains).
  R2  Long-at-the-low is worth less than short-at-the-high on the same bracket (prior 70%).
  R3  The excess is small or absent in 2022 (< +0.05R, prior 55%) and positive in fewer than every calendar year.
  R4  The hour-of-day and volatility-tercile matched excess is at most 70% of the same-side excess (the signal clusters on volatility / time; prior 60%).
  R5  The circular-shift null puts the observed same-side excess in the top 5% (p < 0.05; prior 50%).
  R6  With 10bp of extra slippage per trade the selected mean R is <= 0 (prior 85%).
  R7  On perpetuals outside the five majors the frozen rule's same-side excess is below +0.05R (prior 70%).

RESULT (2026-11-15, logs/combo_rangerev.txt): the +0.147 was the side drift plus a day-vote mean. (0) all shorts earn -0.079R, all longs -0.115R in 2023-26. (1) the diagnostic's selection was 100% shorts; the clean symmetric reversal, per BET: selected -0.038 vs same-side -0.096 =
+0.058 (t +2.0), but per CALL the selected mean is -0.157R (the bet mean gives a one-call quiet day the weight of a crash day with five coins losing together). (2) the decile profile FALLS with the reversal score (Spearman -0.79; top decile -0.157R). (3) matched to quarter /
hour / volatility the excess is -0.067..-0.071R. (4) circular-shift null p = 0.983: the selection is WORSE than a random one of its size. (5) bet-level excess is positive in 4 of 5 years (2022 +0.126), per-call not. (6) G2 / G3 bet-level +0.105 / +0.064 (still the day-vote mean).
Predictions: R1 right in spirit (the excess does not survive), R2 wrong, R3 wrong, R4 right, R5 wrong (p 0.983 the other way), R6 right (selected -0.038R at 0bp, -0.121R at 10bp), R7 not run here (section (7) is a stub; the out-of-universe test is combo_wide.py). No reversal edge:
what the direction-only models pick is trend CONTINUATION, not range reversal. Tests: tests/test_combo_wide.py.

    python -m backtest.combo_rangerev        writes logs/combo_rangerev.txt          tests: tests/test_combo_wide.py
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest import combo_meta as cm  # noqa: E402
from backtest import combo_universe as cu  # noqa: E402

LOG = ROOT / "logs" / "combo_rangerev.txt"
FRAC = 0.10
SLIPS = (0.0, 3.0, 6.0, 10.0)                       # extra bp per trade, charged on top of the 12bp
HALF = pd.Timestamp("2025-01-01")
SHIFTS = 400


def reversal_score(rng_pos24: np.ndarray, side: np.ndarray) -> np.ndarray:
    """Higher = more 'long near the low of the range / short near the high of it'. Centred: c = pos - 0.5 in [-0.5, +0.5]; score = -c x side."""
    return -(np.asarray(rng_pos24, float) - 0.5) * np.asarray(side, float)


def quarter_key(t: pd.Series) -> pd.Series:
    return t.dt.to_period("Q").astype(str)


def select_by_side(d: pd.DataFrame, score: np.ndarray, frac: float = FRAC) -> pd.Series:
    """True for the top `frac` of the score WITHIN each (quarter, side) of the candidates that have a score. Nothing is trained: the rule uses only each candidate's own entry-time feature and the quarter's candidate pool."""
    s = pd.Series(score, index=d.index)
    ok = s.notna()
    key = pd.Series(list(zip(quarter_key(d.t), d.side)), index=d.index)
    rk = s[ok].groupby(key[ok]).rank(pct=True, method="first")
    out = pd.Series(False, index=d.index)
    out[ok] = rk > 1.0 - frac
    return out


def same_side_diff(d: pd.DataFrame, sel: pd.Series, col: str = "r_net") -> dict:
    """Selected candidates against ALL candidates OF THE SAME SIDE: per independent bet (UTC day + side), Welch t. Also the plain row means and the within-bet uplift (selected minus the other candidates of the same day and side)."""
    s = d[sel]
    nan = float("nan")
    if len(s) == 0:
        return dict(n=0, bets=0, sel_r=nan, ctl_r=nan, diff=nan, t=nan, uplift=nan, t_within=nan)
    ba = d.groupby(["day", "side"])[col].mean()
    bs = s.groupby(["day", "side"])[col].mean()
    # the control for a selected bet is the mean of ALL bets of the SAME side
    ctl_by_side = {sd: ba[ba.index.get_level_values(1) == sd].mean() for sd in ("long", "short")}
    w = bs.groupby(level=1).size()
    ctl_r = float(sum(ctl_by_side[sd] * w[sd] for sd in w.index) / w.sum())
    diff = float(bs.mean() - ctl_r)
    # Welch against the same-side all-bets distribution, pooled by the selected side mix
    se2 = 0.0
    for sd in w.index:
        a_sd = ba[ba.index.get_level_values(1) == sd]
        s_sd = bs[bs.index.get_level_values(1) == sd]
        if len(s_sd) < 5 or len(a_sd) < 5:
            return dict(n=len(s), bets=len(bs), sel_r=float(bs.mean()), ctl_r=ctl_r, diff=diff, t=nan, uplift=nan, t_within=nan)
        frac_ = w[sd] / w.sum()
        se2 += frac_ ** 2 * (s_sd.var(ddof=1) / len(s_sd) + a_sd.var(ddof=1) / len(a_sd))
    up = (bs - ba.reindex(bs.index)).to_numpy()
    return dict(n=len(s), bets=len(bs), sel_r=float(bs.mean()), ctl_r=ctl_r, diff=diff, t=(diff / math.sqrt(se2) if se2 > 1e-18 else nan), uplift=float(up.mean()), t_within=cm.tstat(up))


def matched_diff(d: pd.DataFrame, sel: pd.Series, strata: list) -> tuple:
    """Selected minus the unselected candidates of the same side in the SAME STRATUM (stratum columns given); weighted by the number of selected calls per stratum. Returns (diff, number of selected calls compared)."""
    x = d.assign(sel=sel.to_numpy())
    g = x.groupby(strata + ["side"], observed=True)
    num = den = 0.0
    n_used = 0
    for _, grp in g:
        s, u = grp[grp.sel], grp[~grp.sel]
        if len(s) == 0 or len(u) < 5:
            continue
        num += (s.r_net.mean() - u.r_net.mean()) * len(s)
        den += len(s)
        n_used += len(s)
    return (num / den if den else float("nan")), n_used


def shift_null(d: pd.DataFrame, sel: pd.Series, rng, shifts: int = SHIFTS) -> tuple:
    """Circularly shift the selection flag, series by series (symbol, side), by a whole number of days against the outcomes; the statistic is the row-mean R of the shifted selection minus the same-side row mean.
    Returns (observed, p) with p = share of shifted statistics at least as large (+1 smoothing)."""
    x = d.assign(sel=sel.to_numpy()).sort_values("made_ms", kind="stable")
    ctl = x.groupby("side").r_net.transform("mean").to_numpy()
    r = x.r_net.to_numpy()
    obs = float((r[x.sel.to_numpy()] - ctl[x.sel.to_numpy()]).mean())
    series = [np.flatnonzero(((x.symbol == s) & (x.side == sd)).to_numpy()) for s in x.symbol.unique() for sd in ("long", "short")]
    per_day = 4
    nulls = []
    for _ in range(shifts):
        k = int(rng.integers(10, 300)) * per_day
        shifted = np.zeros(len(x), bool)
        for idx in series:
            shifted[idx] = np.roll(x.sel.to_numpy()[idx], k)
        nulls.append(float((r[shifted] - ctl[shifted]).mean()))
    nulls = np.array(nulls)
    return obs, float((1 + (nulls >= obs).sum()) / (1 + shifts)), float(np.std(nulls))


def slip_adjusted(d: pd.DataFrame, bp: float) -> pd.Series:
    return d.r_net - (bp / 1e4) / d.stop_pct


def fmt(st: dict) -> str:
    return (f"n {st['n']:>5} bets {st['bets']:>4}  selected {st['sel_r']:+.3f} vs same-side {st['ctl_r']:+.3f} = {st['diff']:+.3f} (t {st['t']:+.1f}); within-bet uplift {st['uplift']:+.3f} (t {st['t_within']:+.1f})")


def main():
    out = []

    def say(s=""):
        print(s, flush=True)
        out.append(s)

    rng = np.random.default_rng(20261115)
    bars = {s: cm.load_bars(s) for s in cm.SYMS}
    feats = {s: cm.symbol_features(bars[s]) for s in cm.SYMS}
    mkt = cm.market_frame(feats)
    say(f"backtest/combo_rangerev.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; the 24h-range reversal lead dissected; five majors, fixed brackets, every 6th hour, 12bp; selection = top {int(FRAC * 100)}% of the score within each (quarter, side); no training")
    built = {}
    for gname, geom in cu.GEOMS.items():
        d = cu.candidate_frame(bars, geom)
        Xp = cm.call_features(d, feats, mkt)
        d["pos"] = Xp.rng_pos24.to_numpy(float)
        d["hour"] = ((d.made_ms // cm.H1) % 24).astype(int)
        d["atr"] = Xp.atr_pct.to_numpy(float)
        built[gname] = d
    d1 = built["G1"]
    oos = d1[(d1.t >= cm.FIRST_OOS) & d1.pos.notna()]

    say()
    say("(0) THE SIDE DRIFT ALONE (G1, all candidates, no signal): mean R of every long and every short candidate")
    for lab, mask in (("2022-2026", d1.pos.notna()), ("2023-2026 (the walk-forward period)", d1.t >= cm.FIRST_OOS), ("2023-24", (d1.t >= cm.FIRST_OOS) & (d1.t < HALF)), ("2025-26", d1.t >= HALF)):
        m = d1[mask & d1.pos.notna()]
        say(f"  {lab:<36} long {m[m.side == 'long'].r_net.mean():+.3f}  short {m[m.side == 'short'].r_net.mean():+.3f}   (n {len(m):,})")

    say()
    say("(1) THE ORIGINAL DIAGNOSTIC REPRODUCED, then the clean versions (G1, 2023-26; selection per quarter)")
    x = oos.copy()
    uncentred = -(x.pos.to_numpy() * np.where(x.side == "long", 1.0, -1.0))
    sel_old = pd.Series(False, index=x.index)
    rk = pd.Series(uncentred, index=x.index).groupby(quarter_key(x.t)).rank(pct=True, method="first")
    sel_old[:] = (rk > 1.0 - FRAC).to_numpy()
    dall = x.copy()
    b_all = dall.groupby(["day", "side"]).r_net.mean()
    b_sel = dall[sel_old].groupby(["day", "side"]).r_net.mean()
    say(f"  the combo_direction diagnostic (uncentred, ALL-sides baseline): selected {b_sel.mean():+.3f} vs all {b_all.mean():+.3f} = {b_sel.mean() - b_all.mean():+.3f}; side mix of the selected: {dall[sel_old].side.value_counts(normalize=True).round(3).to_dict()}")
    cent = reversal_score(x.pos.to_numpy(), np.where(x.side == "long", 1.0, -1.0))
    for lab, mask in (("clean reversal, both sides  ", np.ones(len(x), bool)), ("short at the HIGH of the range ", (x.side == "short").to_numpy()), ("long at the LOW of the range   ", (x.side == "long").to_numpy())):
        sub = x[mask]
        sel = select_by_side(sub, cent[mask])
        say(f"  {lab} {fmt(same_side_diff(sub, sel))}")
        for hl, hm in (("    2023-24", sub.t < HALF), ("    2025-26", sub.t >= HALF)):
            say(f"  {hl:<30} {fmt(same_side_diff(sub[hm], sel[hm]))}")

    say()
    say("(2) DECILE PROFILE (G1, 2023-26, both sides, score deciles within (quarter, side); mean R of ALL candidates in each decile, row-level)")
    s = pd.Series(cent, index=x.index)
    key = pd.Series(list(zip(quarter_key(x.t), x.side)), index=x.index)
    dec = np.ceil(s.groupby(key).rank(pct=True, method="first") * 10).clip(1, 10).astype(int)
    prof = x.groupby(dec).r_net.agg(["mean", "std", "size"])
    for k, r_ in prof.iterrows():
        say(f"  decile {k:>2}: mean R {r_['mean']:+.3f}  (se {r_['std'] / math.sqrt(r_['size']):.3f}, n {int(r_['size']):,})")
    from scipy import stats as sps
    say(f"  Spearman of decile vs mean R: {sps.spearmanr(prof.index, prof['mean'])[0]:+.2f}")

    say()
    say("(3) MATCHED CONTROLS (G1, 2023-26, selected both sides vs unselected candidates of the SAME side in the same stratum)")
    sel = select_by_side(x, cent)
    base = same_side_diff(x, sel)
    say(f"  same side only                         {fmt(base)}")
    x2 = x.assign(hour_bin=x.hour, q=quarter_key(x.t))
    x2["atr_t"] = x2.groupby("q").atr.transform(lambda v: pd.qcut(v, 3, labels=False, duplicates="drop"))
    for lab, strata in (("+ same quarter", ["q"]), ("+ same quarter and hour of day", ["q", "hour_bin"]), ("+ same quarter and volatility tercile", ["q", "atr_t"]), ("+ same quarter, hour and volatility tercile", ["q", "hour_bin", "atr_t"])):
        dm, nu = matched_diff(x2, sel, strata)
        say(f"  {lab:<43} matched difference {dm:+.3f}  ({nu} selected calls compared)")

    say()
    say("(4) CIRCULAR-SHIFT NULL (G1, 2023-26, the selection flag shifted by 10-300 whole days per series; statistic = selected row mean minus same-side row mean)")
    obs, p, sd = shift_null(x, sel, rng)
    say(f"  observed {obs:+.3f}; null sd {sd:.3f}; p = {p:.3f} (of {SHIFTS} shifts)")

    say()
    say("(5) BY YEAR, COIN, HOUR (G1, the clean rule both sides, 2022 included: no training involved, so 2022 is unseen)")
    x_all = d1[d1.pos.notna()].copy()
    c_all = reversal_score(x_all.pos.to_numpy(), np.where(x_all.side == "long", 1.0, -1.0))
    s_all = select_by_side(x_all, c_all)
    for yr, g in x_all.groupby(x_all.t.dt.year):
        say(f"  {yr}: {fmt(same_side_diff(g, s_all[g.index]))}")
    for sym, g in x_all[x_all.t >= cm.FIRST_OOS].groupby("symbol"):
        say(f"  {sym:<8} (2023-26) {fmt(same_side_diff(g, s_all[g.index]))}")
    for hr, g in x_all[x_all.t >= cm.FIRST_OOS].groupby("hour"):
        say(f"  hour {hr:>2} (2023-26) {fmt(same_side_diff(g, s_all[g.index]))}")

    say()
    say("(6) THE OTHER BRACKETS (the same rule, 2023-26, both sides) and SLIPPAGE (selected mean R per bet after extra bp per trade)")
    for gname in ("G1", "G2", "G3"):
        dd = built[gname]
        dd = dd[(dd.t >= cm.FIRST_OOS) & dd.pos.notna()]
        sc = reversal_score(dd.pos.to_numpy(), np.where(dd.side == "long", 1.0, -1.0))
        sl = select_by_side(dd, sc)
        say(f"  {gname}: {fmt(same_side_diff(dd, sl))}")
        parts = []
        for bp in SLIPS:
            dd2 = dd.assign(r_net=slip_adjusted(dd, bp))
            st = same_side_diff(dd2, sl)
            parts.append(f"{bp:.0f}bp: selected {st['sel_r']:+.3f} (excess {st['diff']:+.3f})")
        say("      " + "   ".join(parts))

    say()
    say("(7) UNSEEN COINS: the same frozen rule on perpetuals outside the five (only if their 1h candles are on disk)")
    say("  " + unseen_coins_report(rng))

    LOG.parent.mkdir(parents=True, exist_ok=True)
    LOG.write_text("\n".join(out) + "\n", encoding="utf-8")


def unseen_coins_report(rng) -> str:
    return "not run in this version (no PIT 1h loader wired in)"


if __name__ == "__main__":
    main()
