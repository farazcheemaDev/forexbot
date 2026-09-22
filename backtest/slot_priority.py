"""WHICH SIGNAL GETS THE LAST SLOT? - ranking simultaneous signals instead of taking them at random.

WHY
    The 12 shared slots bind constantly: the paper bot has declined 462 signals against 47
    taken. When several signals arrive at the same bar and there are fewer free slots than
    signals, today's allocator takes them in whatever order they were generated - in
    effect at random. btc_exit.py measured what that costs: shuffling the order of
    simultaneous entries alone moved the deployed holdout between +4.2% and +11.4%/mo.

    So WHICH trade gets the slot is worth several %/mo, and nobody has tried to choose.
    corr_alloc.py capped slots per correlated cluster and slot_split.py split them by
    side; neither ranked contested signals. Ranking changes nothing about risk: same
    slots, same sizing, same exits, same total exposure - only a different pick.

FEATURES, DECLARED BEFORE LOOKING - all known at the signal bar, before entry
    tf        sleeve timeframe (1h/4h/12h)                  - do slower trends run further?
    mom       the coin's own 30-day return, side-signed      - cross-sectional momentum is
                                                               the one XS edge that lived
    vol       stop distance as % of price (ATR%)             - bigger movers, bigger runners?
    brk       breakout strength: distance past the band / ATR
    vsurge    signal-bar volume / its 20-bar average

    Each is run in BOTH directions. A real effect has to help in one direction and HURT in
    the other; if both directions land inside the random band, the feature is noise.

    Every variant is run over 5 random tie-break seeds (ties within equal priority), and the
    RANDOM row is the deployed behaviour. 1000h gate, compounded by close date, 3x
    hindsight haircut on %/mo, tune/holdout as bear_date.py.

    python -m backtest.slot_priority
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import blend  # noqa: E402
from backtest.bear_side import sleeve_sided  # noqa: E402
from backtest.bull_boost import evaluate, pyramid_detail, regimes  # noqa: E402
from backtest.timeframes import resample  # noqa: E402
from bot.core.indicators import atr as atr_ind  # noqa: E402

RULES = ["1h", "4h", "12h"]
TF_RANK = {"1h": 0, "4h": 1, "12h": 2}
SEEDS = (1, 2, 3, 4, 5)


def build():
    rows = []
    for rule in RULES:
        _tr, stops = sleeve_sided(rule)
        shorts = [(a_, b_, r, c_) for a_, b_, r, _ru, c_, side in _tr if side == "short"]
        for coin in blend.BOOK:
            d = blend.load(coin)
            if d is None:
                continue
            df = resample(d, rule)
            if len(df) < 300:
                continue
            h1 = pd.Series(d["close"].to_numpy(), index=pd.DatetimeIndex(d["time"]))
            t = pd.DatetimeIndex(df["time"])
            c = df["close"].to_numpy(float)
            v = df["volume"].to_numpy(float)
            a = atr_ind(df, 14).to_numpy(float)
            ma = pd.Series(c).rolling(30).mean().to_numpy()
            sd = pd.Series(c).rolling(30).std(ddof=0).to_numpy()
            vavg = pd.Series(v).rolling(20).mean().shift(1).to_numpy()

            def feats(t0, side):
                i = t.get_indexer([pd.Timestamp(t0)])[0]
                if i < 2:
                    return None
                j = i - 1                                     # the signal bar
                dsgn = 1 if side == "long" else -1
                band = ma[j] + dsgn * 1.5 * sd[j]
                past = h1.asof(pd.Timestamp(t0) - pd.Timedelta(hours=1))
                ago = h1.asof(pd.Timestamp(t0) - pd.Timedelta(hours=721))
                return dict(
                    tf=TF_RANK[rule],
                    mom=dsgn * (past / ago - 1) if ago and np.isfinite(ago) else 0.0,
                    vol=2 * a[j] / c[j] if c[j] > 0 else 0.0,
                    brk=dsgn * (c[j] - band) / a[j] if a[j] > 0 else 0.0,
                    vsurge=v[j] / vavg[j] if vavg[j] and vavg[j] > 0 else 1.0)

            for x in pyramid_detail(df):
                f = feats(x["t0"], "long")
                if f:
                    rows.append(dict(x, side="long", coin=coin, rule=rule, **f))
            for a_, b_, r, c_ in shorts:
                if c_ != coin:
                    continue
                f = feats(a_, "short")
                if f:
                    rows.append(dict(t0=a_, t1=b_, R=r, sf=stops.get(c_, 0.05), adds=[a_],
                                     side="short", coin=coin, rule=rule, **f))
    return rows


def order(rows, key=None, reverse=False, seed=1):
    """Rows sorted by entry time; WITHIN one entry time, by the priority key (then random)."""
    rng = np.random.default_rng(seed)
    tie = rng.random(len(rows))
    sgn = -1 if not reverse else 1
    kf = (lambda r: 0.0) if key is None else (lambda r: sgn * r[key])
    idx = sorted(range(len(rows)), key=lambda i: (rows[i]["t0"], kf(rows[i]), tie[i]))
    return [rows[i] for i in idx]


def contested(rows, slots=12):
    """How often does priority matter at all: entry times with more candidates than free
    slots, under the deployed (random) order."""
    groups = {}
    for r in rows:
        groups.setdefault(r["t0"], []).append(r)
    opens, n_groups, n_cont, n_rows_cont = [], 0, 0, 0
    for t0 in sorted(groups):
        opens = [u for u in opens if u > t0]
        free = slots - len(opens)
        g = groups[t0]
        n_groups += 1
        if len(g) > free > 0:
            n_cont += 1; n_rows_cont += len(g)
        for r in g[:max(free, 0)]:
            opens.append(r["t1"])
    return n_groups, n_cont, n_rows_cont


def main():
    rows = build()
    bear = regimes()[1000]
    ts = pd.DatetimeIndex(sorted(x[0] for x in sleeve_sided("1h")[0]))
    cut = ts[int(len(ts) * 0.6)]
    ng, nc, nr = contested(order(rows, seed=1))
    print(f"{len(rows):,} candidate positions; {ng:,} distinct entry times; {nc:,} of them "
          f"CONTESTED (more signals than free slots, {nr:,} signals involved)\n")

    def run(key, rev):
        A, B = [], []
        for sd in SEEDS:
            o = order(rows, key, rev, sd)
            a = evaluate(o, bear, t_to=cut); b = evaluate(o, bear, t_from=cut)
            A.append((a["hpm"], a["dd"])); B.append((b["hpm"], b["dd"], b["worst_mo"]))
        return np.array(A), np.array(B)

    print(f"  {'priority':<26}| {'TUNE/mo':>22}{'DD':>6} | {'HOLD/mo':>22}{'DD':>6}{'worst':>8}")
    base = run(None, False)

    def show(lab, A, B):
        print(f"  {lab:<26}| {A[:,0].mean():>+6.2f}% ({A[:,0].min():+5.1f}..{A[:,0].max():+5.1f})"
              f"{A[:,1].mean():>5.0f}% | {B[:,0].mean():>+6.2f}% ({B[:,0].min():+5.1f}.."
              f"{B[:,0].max():+5.1f}){B[:,1].mean():>5.0f}%{B[:,2].mean():>+7.1f}%")

    show("RANDOM (deployed)", *base)
    res = {}
    for key, lab in (("tf", "timeframe"), ("mom", "30d momentum"), ("vol", "volatility (ATR%)"),
                     ("brk", "breakout strength"), ("vsurge", "volume surge")):
        for rev in (False, True):
            A, B = run(key, rev)
            res[(key, rev)] = (A, B)
            show(f"{lab} {'LOW' if rev else 'HIGH'} first", A, B)
        print()
    bt, bh = base[0][:, 0].mean(), base[1][:, 0].mean()
    print("A feature is only real if one direction beats RANDOM on BOTH halves and the other")
    print("direction loses to it on both:")
    for key in ("tf", "mom", "vol", "brk", "vsurge"):
        hi, lo = res[(key, False)], res[(key, True)]
        up = hi[0][:, 0].mean() > bt and hi[1][:, 0].mean() > bh
        dn = lo[0][:, 0].mean() < bt and lo[1][:, 0].mean() < bh
        up2 = lo[0][:, 0].mean() > bt and lo[1][:, 0].mean() > bh
        dn2 = hi[0][:, 0].mean() < bt and hi[1][:, 0].mean() < bh
        verdict = ("HIGH-first helps, LOW-first hurts" if up and dn else
                   "LOW-first helps, HIGH-first hurts" if up2 and dn2 else "no consistent effect")
        print(f"  {key:<8} {verdict}")


if __name__ == "__main__":
    main()
