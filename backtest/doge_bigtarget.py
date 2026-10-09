"""AIM FOR 1%, NOT 0.1% - does a bigger target beat the fee on DOGE? (2026-10-09)

THE USER (2026-10-09): "we have to make more than 0.12 percent, we can aim for 1 percent also". Right in principle: with
a 1% target the 12bp round trip is ~12% of the win instead of ~50-100% of it (doge_adapt.py's ATR-sized 1m/5m brackets
needed 61-105% accuracy). The cost is that a 1% target is hit less often and takes hours, so the trade stops being a
scalp. Measured here on the same 90 days of Bitget 1m DOGE perp bars (backtest/bitget_1m.py):
    ENTRIES    doge_adapt.signals' families on 5m, 15m and 1h bars, side both / long / short
    BRACKETS   target / stop in % of the entry: 0.5/0.5, 1/0.5, 1/1, 1.5/0.75, 2/1; time stop 4h or 24h; the stop first when
               one 1m bar touches both; stops filled at the worse of the stop and the bar's open; 12bp a round trip
    BASELINE   RANDOM entries - a long (or short) every 4 hours on the hour, same brackets - the coin flip
    SPLIT      first 60% of the days / last 40% (the repo's holdout rule); a rule counts only if net positive on BOTH

REGISTERED BEFORE THE RUN (2026-10-09 ~17:20 UTC)
    B1  Bigger brackets cut the fee's share but not the sign: at 1% / 1% the median rule nets about -0.12% a trade (the
        fee; entries add ~0 over hours), and under 5% of all rules are net positive on BOTH halves at 12bp.
    B2  Random entries hit their target ~ the bracket's no-edge rate (stop / (target + stop): 50% at 1/1, 33% at 1/0.5)
        and lose about the fee.
    B3  No entry family beats random entries at the same bracket by more than 2 standard errors on the second half.

RESULT (2026-10-09 17:23 UTC, logs/doge_bigtarget.txt / .csv; 790 rules, 2026-07-11 .. 2026-10-09, holdout from 09-03)
    - B1 RIGHT: at every bracket the median rule nets -0.117% to -0.124% a trade - exactly the fee - and 2 of 790 rules
      (0.3%) are net positive on both halves, fewer than luck alone would give.
    - B2 RIGHT: random entries win at the bracket's no-edge rate (50.0% at 1/1, 36.4% at 1/0.5, 40.5% at 2/1) and lose
      -0.120% to -0.131% a trade. The rules' median win rates are the same as random's at every bracket.
    - B3 RIGHT: the best of the 2 (1h close above the 20-bar high, long, 2% / 1%, 24h) beats random by +0.9 se on 18
      holdout trades.
    Reading: a bigger target lowers the accuracy a trade needs, and the price reaches it less often in exactly the same
    proportion - as a coin flip does. The fee stays the loss per trade. What a bigger bracket DOES buy is room: the fee is
    -0.12R a trade at 1% / 1% against roughly -1R at 0.1% brackets, so an entry with real information would pay there and
    could not pay on 1-minute scalps. None of these chart entries has that information at the hours scale.

    python -m backtest.doge_bigtarget
"""
from __future__ import annotations

import itertools
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest import bitget_1m as bg  # noqa: E402
from backtest import doge_adapt as da  # noqa: E402

LOG = ROOT / "logs" / "doge_bigtarget.txt"
MIN, DAY = 60_000, 86_400_000
FEE = 0.0012
BRACKETS = ((0.005, 0.005), (0.010, 0.005), (0.010, 0.010), (0.015, 0.0075), (0.020, 0.010))
TSTOPS = (240, 1440)                                                   # minutes


def simulate(d1, ct_close, lo, sh, tgt, stop, H):
    """Fixed-% brackets on 1m bars. ct_close = the signal bars' close times. Returns (entry_t, gross)."""
    t1, o1, h1, l1, c1 = (d1[k].to_numpy() for k in ("t", "o", "h", "l", "c"))
    j_of = np.searchsorted(t1, ct_close)
    ev = sorted([(i, 1) for i in np.flatnonzero(lo)] + [(i, -1) for i in np.flatnonzero(sh)])
    free, ent, ret = -1, [], []
    for i, sd in ev:
        j0 = j_of[i]
        if j0 >= len(t1) or t1[j0] != ct_close[i] or j0 <= free or j0 + H >= len(t1):
            continue
        e = o1[j0]
        sp, tp = e * (1 - sd * stop), e * (1 + sd * tgt)
        hh, ll = h1[j0:j0 + H], l1[j0:j0 + H]
        s_hit = (ll <= sp) if sd > 0 else (hh >= sp)
        t_hit = (hh >= tp) if sd > 0 else (ll <= tp)
        si, ti = np.flatnonzero(s_hit), np.flatnonzero(t_hit)
        s0 = si[0] if len(si) else H
        g0 = ti[0] if len(ti) else H
        if s0 <= g0 and s0 < H:
            k = j0 + s0
            x = sp if k == j0 else (min(o1[k], sp) if sd > 0 else max(o1[k], sp))
        elif g0 < H:
            k, x = j0 + g0, tp
        else:
            k, x = j0 + H - 1, c1[j0 + H - 1]
        ent.append(t1[j0])
        ret.append(sd * (x / e - 1))
        free = k
    return np.array(ent, np.int64), np.array(ret)


def stats(ent, ret, cut):
    out = {}
    for nm, m in (("all", np.ones(len(ent), bool)), ("tune", ent < cut), ("hold", ent >= cut)):
        r = ret[m] - FEE
        out[nm] = (len(r), r.mean() if len(r) else np.nan, (ret[m] > 0).mean() if len(r) else np.nan,
                   r.std(ddof=1) / np.sqrt(len(r)) if len(r) > 1 else np.nan)
    return out


def main():
    d1 = bg.fetch("DOGE", 90, quiet=True)
    d1 = d1[d1.t >= d1.t.max() - 90 * DAY].reset_index(drop=True)
    days = (d1.t.max() - d1.t.min()) / DAY
    cut = int(d1.t.min() + 0.6 * (d1.t.max() - d1.t.min()))
    rows = []
    for tf in (5, 15, 60):
        b = da.bars(d1, tf)
        sig, A = da.signals(b, d1, tf)
        ct = b.close_t.to_numpy()
        # the random baseline: an entry at every 4th hour's close, long or short
        rnd = (b.t.to_numpy() % (4 * 3_600_000) == (4 * 3_600_000 - tf * MIN))
        sig["RANDOM"] = (rnd, rnd)
        for name, (lo_, sh_) in sig.items():
            for side, (tgt, stop), H in itertools.product(("both", "long", "short"), BRACKETS, TSTOPS):
                if name == "RANDOM" and (side == "both" or tf != 60):
                    continue
                lo = lo_ if side in ("both", "long") else np.zeros_like(lo_)
                sh = sh_ if side in ("both", "short") else np.zeros_like(sh_)
                ent, ret = simulate(d1, ct, lo, sh, tgt, stop, H)
                if len(ret) < 10:
                    continue
                s = stats(ent, ret, cut)
                rows.append(dict(tf=f"{tf}m", entry=name, side=side, tgt=tgt, stop=stop, H=H, n=s["all"][0],
                                 net=s["all"][1], win=s["all"][2], n_t=s["tune"][0], net_t=s["tune"][1], n_h=s["hold"][0],
                                 net_h=s["hold"][1], se_h=s["hold"][3], per_day=s["all"][0] / days))
    R = pd.DataFrame(rows)
    real = R[R.entry != "RANDOM"]
    lines = [f"backtest/doge_bigtarget.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; Bitget DOGE perp 1m "
             f"{pd.Timestamp(d1.t.min(), unit='ms'):%Y-%m-%d} .. {pd.Timestamp(d1.t.max(), unit='ms'):%Y-%m-%d %H:%M}; "
             f"tune < {pd.Timestamp(cut, unit='ms'):%Y-%m-%d} <= holdout; {len(real)} rules; 12bp a round trip, 1x", ""]
    lines.append("BY BRACKET (all rules with 10+ trades): accuracy needed vs got, net a trade, and how many are net positive")
    for (tgt, stop), g in real.groupby(["tgt", "stop"]):
        need = (stop + FEE) / (tgt + stop)
        rn = R[(R.entry == "RANDOM") & (R.tgt == tgt) & (R.stop == stop)]
        both = g[(g.net_t > 0) & (g.net_h > 0) & (g.n_t >= 10) & (g.n_h >= 10)]
        lines.append(f"  target {tgt * 100:.1f}% / stop {stop * 100:.2f}%: need {need * 100:4.1f}% wins | rules: median win "
                     f"{g.win.median() * 100:4.1f}%, median net {g.net.median() * 100:+.3f}% a trade, positive over 90 days "
                     f"{(g.net > 0).sum()}/{len(g)}, on BOTH halves {len(both)} | RANDOM: win {rn.win.mean() * 100:4.1f}%, "
                     f"net {rn.net.mean() * 100:+.3f}% a trade")
    lines.append("")
    both = real[(real.net_t > 0) & (real.net_h > 0) & (real.n_t >= 10) & (real.n_h >= 10)].copy()
    lines.append(f"RULES NET POSITIVE ON BOTH HALVES at 12bp: {len(both)} of {len(real)} ({len(both) / len(real) * 100:.1f}%)")
    for r in both.sort_values("net_h", ascending=False).head(15).itertuples():
        rn = R[(R.entry == "RANDOM") & (R.tgt == r.tgt) & (R.stop == r.stop) & (R.H == r.H)]
        base = rn.net_h.mean()
        lines.append(f"  {r.tf:3} {r.entry:13} {r.side:5} tgt {r.tgt * 100:.1f}% stop {r.stop * 100:.2f}% {r.H // 60:2}h | "
                     f"{r.n} trades ({r.per_day:.1f}/day), win {r.win * 100:.0f}% | net tune {r.net_t * 100:+.3f}% (n {r.n_t}) "
                     f"holdout {r.net_h * 100:+.3f}% (n {r.n_h}, se {r.se_h * 100:.3f}) | random at this bracket, holdout "
                     f"{base * 100:+.3f}% | beats random by {(r.net_h - base) / r.se_h if r.se_h else np.nan:+.1f} se")
    txt = "\n".join(lines)
    print(txt)
    LOG.write_text(txt + "\n", encoding="utf-8")
    R.to_csv(ROOT / "logs" / "doge_bigtarget.csv", index=False)


if __name__ == "__main__":
    main()
