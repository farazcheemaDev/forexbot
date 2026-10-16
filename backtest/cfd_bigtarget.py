"""BIGGER TARGETS ON NASDAQ, US30, GOLD AND FOREX - doge_bigtarget.py at Exness costs (2026-10-12)

The second crypto test the user asked to carry over ("aim for 1%, not 0.1%"). On DOGE, 790 rules with 0.5-2% brackets won
exactly as often as RANDOM entries at every bracket and lost the 12bp fee (logs/doge_bigtarget.txt). Here the cost is the
Exness spread (~0.4-0.8bp) plus swap for a position held past 21:00 UTC, so a bigger bracket costs almost nothing extra -
the question is only whether the chart entries pick direction better than a coin flip at the hours scale.

DATA     backtest/mt5_1m.py's 1m mid bars from ticks, 2026-01-01 .. 2026-10-09; tune = first 60% of days.
ENTRIES  doge_adapt.signals' families on 5m, 15m and 1h bars (ORB only exists on 1m and is not here), side both / long /
         short. RANDOM = an entry at the close of every 4th hour, long and short separately (the coin flip, with the
         instrument's drift).
BRACKETS a fraction of the instrument's DAILY ATR(14) known before the day (DOGE's 1% was ~0.2 of its daily ATR):
         target / stop = 0.25/0.25, 0.5/0.25, 0.5/0.5, 0.75/0.375, 1.0/0.5 of a daily ATR; time stop 4h or 24h by the
         clock; stop first when one 1m bar touches both; stops at the worse of the stop and the bar's open.
COSTS    half the spread at the entry minute's first tick + half the exit minute's mean spread; one night's swap
         (forex.py's rates) for each 21:00 UTC passed. No commission (Standard account).
VERDICT  a rule BEATS RANDOM if, on BOTH halves, its net a trade exceeds RANDOM's at the same bracket and time stop (same
         side; "both" against the average of long and short) by more than 2 standard errors of the rule's mean.

REGISTERED BEFORE THE RUN (2026-10-12; cfd_scalp.py's first two instruments had been seen: gross ~0, net ~ -spread)
    F1  At every bracket the rules' median win rate is within 3 points of RANDOM's, on every instrument.
    F2  Rules that BEAT RANDOM on both halves: under 1% on every instrument, and no entry/side/bracket that does so on
        more than one instrument.
    F3  The plain RANDOM long is net positive on both halves on gold and NASDAQ (their 2026 drift) - i.e. "just buy"
        does as well as the best chart entry there.

RESULT (2026-10-11 20:47 UTC, logs/cfd_bigtarget.txt / .csv; 4,820 rules, 2026-01-01 .. 2026-10-09, holdout 06-19)
    - F2 RIGHT: 0 of 4,820 rules beat random entries by 2 se on both halves - on every instrument, at every bracket.
    - F1 WRONG by a hair, the wrong way for the rules: their median win rate is within 2 points of random's in 27 of 30
      instrument-brackets, and 3.2 points BELOW it at US30's 0.75 / 0.375. Median rule gross -0.6..+0.6bp a trade; net
      -0.2..-1.8bp.
    - F3 WRONG: "just buy" did not pay either - a random long nets +2.6 / -3.2bp (NASDAQ tune / holdout), -0.9 / -2.1bp
      (gold), +0.4 / +0.9bp (US30). These nine months had no drift a coin flip could ride.
    Reading: as on DOGE, a bigger target lowers the accuracy needed and is reached less often in exactly the same
    proportion. Cheap costs do not change it: the chart entries choose direction like a coin.

    python -m backtest.cfd_bigtarget             (needs backtest/mt5_1m.py's cache)
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
from backtest.cfd_scalp import SWAP_BP, SYMS, TUNE  # noqa: E402

LOG = ROOT / "logs" / "cfd_bigtarget.txt"
MIN, DAY, HOUR = 60_000, 86_400_000, 3_600_000
BRACKETS = ((0.25, 0.25), (0.5, 0.25), (0.5, 0.5), (0.75, 0.375), (1.0, 0.5))
TSTOPS = (240, 1440)


def simulate(d1, ct_close, frac, lo, sh, tgt_k, stop_k, H, swap_bp):
    """daily-ATR brackets on 1m bars: (entry_t, gross, net). frac = daily ATR / price for each signal bar."""
    t1, o1, h1, l1, c1 = (d1[k].to_numpy() for k in ("t", "o", "h", "l", "c"))
    spo, spm = d1.sp_o.to_numpy(), d1.sp.to_numpy()
    j_of = np.searchsorted(t1, ct_close)
    ev = sorted([(i, 1) for i in np.flatnonzero(lo)] + [(i, -1) for i in np.flatnonzero(sh)])
    free, out = -1, []
    for i, sd in ev:
        j0 = j_of[i]
        if j0 >= len(t1) or t1[j0] != ct_close[i] or j0 <= free or not np.isfinite(frac[i]):
            continue
        jn = np.searchsorted(t1, t1[j0] + H * MIN)
        if jn >= len(t1):
            continue
        e = o1[j0]
        stp, tp = e * (1 - sd * stop_k * frac[i]), e * (1 + sd * tgt_k * frac[i])
        hh, ll = h1[j0:jn], l1[j0:jn]
        s_hit = (ll <= stp) if sd > 0 else (hh >= stp)
        t_hit = (hh >= tp) if sd > 0 else (ll <= tp)
        si, ti = np.flatnonzero(s_hit), np.flatnonzero(t_hit)
        n_ = jn - j0
        s0 = si[0] if len(si) else n_
        g0 = ti[0] if len(ti) else n_
        if s0 <= g0 and s0 < n_:
            k = j0 + s0
            x = stp if k == j0 else (min(o1[k], stp) if sd > 0 else max(o1[k], stp))
        elif g0 < n_:
            k, x = j0 + g0, tp
        else:
            k = jn - 1
            x = c1[k]
        gross = sd * (x / e - 1)
        roll = (t1[j0] // DAY) * DAY + 21 * HOUR
        if t1[j0] >= roll:
            roll += DAY
        nights = 0 if t1[k] + MIN <= roll else 1 + (t1[k] + MIN - roll - 1) // DAY
        out.append((t1[j0], gross, gross - (spo[j0] + spm[k]) / 2 / e - nights * swap_bp / 1e4))
        free = k
    if not out:
        return np.zeros(0, np.int64), np.zeros(0), np.zeros(0)
    r = np.array(out)
    return r[:, 0].astype(np.int64), r[:, 1], r[:, 2]


def instrument(sym):
    d1 = mt5_1m.load(sym)
    d1 = d1[d1.t < int(pd.Timestamp("2026-10-10").timestamp() * 1000)].reset_index(drop=True)
    days = np.unique(d1.t // DAY)
    cut = int(days[int(len(days) * TUNE)]) * DAY
    dd = d1.assign(day=d1.t // DAY).groupby("day").agg(h=("h", "max"), l=("l", "min"), c=("c", "last"))
    pc = dd.c.shift(1)
    tr = np.maximum(dd.h - dd.l, np.maximum((dd.h - pc).abs(), (dd.l - pc).abs()))
    datr = (tr.rolling(14).mean() / dd.c).shift(1)                   # known before the day
    rows = []
    for tf in (5, 15, 60):
        b = da.bars(d1, tf)
        sig, _ = da.signals(b, d1, tf)
        sig.pop("orb", None)
        ct = b.close_t.to_numpy()
        frac = datr.reindex(b.t.to_numpy() // DAY).to_numpy()
        if tf == 60:
            rnd = (b.t.to_numpy() % (4 * HOUR)) == (4 * HOUR - HOUR)
            sig["RANDOM"] = (rnd, rnd)
        for name, (lo_, sh_) in sig.items():
            for side, (tk, sk), H in itertools.product(("both", "long", "short"), BRACKETS, TSTOPS):
                if name == "RANDOM" and side == "both":
                    continue
                lo = lo_ if side in ("both", "long") else np.zeros_like(lo_)
                sh = sh_ if side in ("both", "short") else np.zeros_like(sh_)
                ent, g, n = simulate(d1, ct, frac, lo, sh, tk, sk, H, SWAP_BP[sym])
                if len(n) < 10:
                    continue
                r = dict(sym=sym, tf=f"{tf}m", entry=name, side=side, tgt=tk, stop=sk, H=H, n=len(n), net=n.mean(),
                         gross=g.mean(), win=(n > 0).mean())
                for nm, m in (("t", ent < cut), ("h", ent >= cut)):
                    r[f"n_{nm}"], r[f"net_{nm}"] = int(m.sum()), n[m].mean() if m.any() else np.nan
                    r[f"se_{nm}"] = n[m].std(ddof=1) / np.sqrt(m.sum()) if m.sum() > 1 else np.nan
                rows.append(r)
    R = pd.DataFrame(rows)
    rnd = R[R.entry == "RANDOM"].set_index(["side", "tgt", "stop", "H"])
    for nm in ("t", "h"):
        def base(r):
            k = (r.tgt, r.stop, r.H)
            if r.side == "both":
                return np.nanmean([rnd[f"net_{nm}"].get(("long",) + k, np.nan), rnd[f"net_{nm}"].get(("short",) + k, np.nan)])
            return rnd[f"net_{nm}"].get((r.side,) + k, np.nan)
        R[f"rnd_{nm}"] = R.apply(base, axis=1)
        R[f"z_{nm}"] = (R[f"net_{nm}"] - R[f"rnd_{nm}"]) / R[f"se_{nm}"]
    return R, d1, cut


def main():
    lines = [f"backtest/cfd_bigtarget.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; doge_bigtarget.py's test on Exness CFDs, "
             f"brackets in daily ATRs, net of spread and swap, 1x", ""]
    allR, f1, f3 = [], [], {}
    for sym in SYMS:
        R, d1, cut = instrument(sym)
        real = R[R.entry != "RANDOM"]
        lines.append(f"== {sym}: {pd.Timestamp(d1.t.min(), unit='ms'):%Y-%m-%d} .. {pd.Timestamp(d1.t.max(), unit='ms'):%Y-%m-%d}, "
                     f"holdout from {pd.Timestamp(cut, unit='ms'):%Y-%m-%d}; {len(real)} rules")
        for (tk, sk), g in real.groupby(["tgt", "stop"]):
            rn = R[(R.entry == "RANDOM") & (R.tgt == tk) & (R.stop == sk)]
            gap = g.win.median() - rn.win.mean()
            f1.append(abs(gap))
            lines.append(f"  tgt {tk:.2f} / stop {sk:.3f} daily ATR: rules median win {g.win.median() * 100:4.1f}% vs RANDOM "
                         f"{rn.win.mean() * 100:4.1f}% | median net {g.net.median() * 1e4:+6.1f}bp, gross {g.gross.median() * 1e4:+6.1f}bp "
                         f"| RANDOM long {rn[rn.side == 'long'].net.mean() * 1e4:+6.1f}bp, short {rn[rn.side == 'short'].net.mean() * 1e4:+6.1f}bp")
        rl = R[(R.entry == "RANDOM") & (R.side == "long")]
        f3[sym] = (rl.net_t.mean(), rl.net_h.mean())
        lines.append(f"  RANDOM long, all brackets: tune {rl.net_t.mean() * 1e4:+.1f}bp, holdout {rl.net_h.mean() * 1e4:+.1f}bp a trade")
        win = real[(real.z_t > 2) & (real.z_h > 2) & (real.n_t >= 10) & (real.n_h >= 10)]
        lines.append(f"  BEAT RANDOM by 2 se on BOTH halves: {len(win)} of {len(real)} ({len(win) / len(real) * 100:.1f}%)")
        for r in win.sort_values("z_h", ascending=False).head(8).itertuples():
            lines.append(f"     {r.tf:3} {r.entry:13} {r.side:5} {r.tgt:.2f}/{r.stop:.3f} {r.H // 60:2}h | {r.n} trades | net tune "
                         f"{r.net_t * 1e4:+.1f}bp (random {r.rnd_t * 1e4:+.1f}, z {r.z_t:+.1f}) | holdout {r.net_h * 1e4:+.1f}bp "
                         f"(random {r.rnd_h * 1e4:+.1f}, z {r.z_h:+.1f})")
        lines.append("")
        allR.append(R)
        print("\n".join(lines[-12:]), flush=True)
    A = pd.concat(allR, ignore_index=True)
    real = A[A.entry != "RANDOM"]
    win = real[(real.z_t > 2) & (real.z_h > 2) & (real.n_t >= 10) & (real.n_h >= 10)]
    share = win.groupby("sym").size().reindex(SYMS, fill_value=0) / real.groupby("sym").size().reindex(SYMS)
    multi = win.groupby(["tf", "entry", "side", "tgt", "stop", "H"]).sym.nunique()
    multi = multi[multi > 1]
    lines.append("REGISTERED PREDICTIONS")
    lines.append(f"  F1 largest gap between the rules' median win rate and RANDOM's: {max(f1) * 100:.1f} points -> "
                 f"{'RIGHT' if max(f1) <= 0.03 else 'WRONG'}")
    lines.append(f"  F2 share beating random on both halves: " + ", ".join(f"{s} {v * 100:.1f}%" for s, v in share.items())
                 + f"; on more than one instrument: {len(multi)} -> {'RIGHT' if (share < 0.01).all() and not len(multi) else 'WRONG'}")
    for k, v in multi.items():
        lines.append(f"     {k}: {v} instruments")
    lines.append(f"  F3 RANDOM long tune / holdout: " + ", ".join(f"{s} {a * 1e4:+.1f}/{b * 1e4:+.1f}bp" for s, (a, b) in f3.items())
                 + f" -> {'RIGHT' if all(f3[s][0] > 0 and f3[s][1] > 0 for s in ('XAUUSDm', 'USTECm')) else 'WRONG'}")
    txt = "\n".join(lines)
    print(txt)
    LOG.write_text(txt + "\n", encoding="utf-8")
    A.to_csv(ROOT / "logs" / "cfd_bigtarget.csv", index=False)


if __name__ == "__main__":
    main()
