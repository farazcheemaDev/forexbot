"""THE TREND BOOK'S OWN PARAMETERS, ALL IN COMBINATION (2026-10-09).

Every trend-book parameter was swept ONE AT A TIME (graveyard_rescore.py, pyramid_params.py, units_on_tstop.py,
engine_rescore2.py); the triple itself is the only combination ever run (tight + time stop + 7 units, a 2x2 on two of
them). Here the full factorial on the corrected engine (engine_rescore2.walk2: real entry times, funding, entry-sized
compounding, 12 slots, 1000h gate, 10 orderings):
    tight exit       off / on
    time stop        off / out if under +2R after 100 bars
    units            5 / 7
    long trail       15 / 20 / 25 x ATR
    add every        1.5 / 2 / 2.5 R
    breakeven at     2 / 3 / 4 R
  = 216 configurations. Shorts as deployed.

The pick is HONEST: the best tune-half %/mo among configs whose tune-half fall is no deeper than MAIN's, then read on the
holdout. Also: how many configs beat MAIN on both halves by 2 paired standard errors, and where the triple ranks.

REGISTERED BEFORE RUNNING: the tune pick is the triple or a neighbour (tight + units 7 in it); on the holdout it ranks in
the top fifth of 216; under 15% of configs beat MAIN on both halves; no config beats the TRIPLE on both halves by 2 se.

RESULT (2026-10-09, logs/trend_factorial.txt): STOPPED at 37 of 216 by the user's rule ("if the first 37 succeed,
    continue, otherwise no"). All 37 are the plain / no-time-stop corner (units 5 and part of 7); none beats MAIN on
    both halves by 2 se - the deployed trail 20 / add 2R / BE 3R ties the best (+4.91 / +4.92 vs +4.88 / +4.88); the
    rest are 'holdout up, tune down' (trail 15). The tight-exit / time-stop half of the grid was NOT run.

    python -m backtest.trend_factorial         (~2 hours)
"""
from __future__ import annotations

import itertools
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest import engine_rescore2 as E  # noqa: E402
from backtest import graveyard_rescore as G  # noqa: E402
from backtest.bear_side import sleeve_sided  # noqa: E402
from backtest.bull_boost import regimes  # noqa: E402

LOG = ROOT / "logs" / "trend_factorial.txt"
CACHE = ROOT / "logs" / "daily_combos_cache" / "trend_factorial.pkl"


def key(c):
    return (c["tight"], c["time_stop"], c["max_units"], c["trail"], c["add_every"], c["be_at"])


def main():
    bear = regimes()[1000]
    ts = pd.DatetimeIndex(sorted(x[0] for x in sleeve_sided("1h")[0]))
    cut = ts[int(len(ts) * 0.6)]
    res = pickle.loads(CACHE.read_bytes()) if CACHE.exists() else {}
    for w in CACHE.parent.glob("trend_factorial_w*.pkl"):          # parallel workers' results (--worker k/n)
        res.update(pickle.loads(w.read_bytes()))
    grid = [dict(tight=t, time_stop=s, max_units=u, trail=tr, add_every=a, be_at=b)
            for t, s, u, tr, a, b in itertools.product((False, True), (None, (100, 2.0)), (5, 7), (15.0, 20.0, 25.0),
                                                       (1.5, 2.0, 2.5), (2.0, 3.0, 4.0))]
    wk = next((a.split("=")[1] for a in sys.argv if a.startswith("--worker=")), None)
    if wk:                                                          # a worker: its share of the missing configs, own file
        k, nw = (int(x) for x in wk.split("/"))
        mine = {}
        wf = CACHE.parent / f"trend_factorial_w{k}.pkl"
        for n, c in enumerate(grid):
            if n % nw != k or key(c) in res:
                continue
            mine[key(c)] = G.score(E.rows2(**c), bear, cut)
            E._C.clear()
            wf.write_bytes(pickle.dumps(mine))
            print(f"  worker {k}: config {n + 1}/{len(grid)} done ({len(mine)} by this worker)", flush=True)
        return
    for n, c in enumerate(grid):
        if key(c) in res:
            continue
        S = G.score(E.rows2(**c), bear, cut)
        res[key(c)] = S
        E._C.clear()
        if n % 12 == 0:
            CACHE.write_bytes(pickle.dumps(res))
            print(f"  {n + 1}/{len(grid)}", flush=True)
    CACHE.write_bytes(pickle.dumps(res))
    MAIN = (False, None, 5, 20.0, 2.0, 3.0)
    TRI = (True, (100, 2.0), 7, 20.0, 2.0, 3.0)
    B, Tr = res[MAIN], res[TRI]
    rows = []
    for k, S in res.items():
        dt = S["tune"][:, 0] - B["tune"][:, 0]
        dh = S["hold"][:, 0] - B["hold"][:, 0]
        et = S["tune"][:, 0] - Tr["tune"][:, 0]
        eh = S["hold"][:, 0] - Tr["hold"][:, 0]
        se = lambda x: x.std(ddof=1) / np.sqrt(len(x))  # noqa: E731
        rows.append(dict(cfg=k, tune=S["tune"][:, 0].mean(), tdd=S["tune"][:, 1].mean(), hold=S["hold"][:, 0].mean(),
                         hdd=S["hold"][:, 1].mean(), hwm=S["hold"][:, 2].mean(),
                         beats_main=(dt.mean() > 2 * se(dt)) and (dh.mean() > 2 * se(dh)),
                         beats_triple=(et.mean() > 2 * se(et)) and (eh.mean() > 2 * se(eh))))
    D = pd.DataFrame(rows)
    D["hold_rank"] = D.hold.rank(ascending=False).astype(int)
    name = lambda k: (f"{'tight' if k[0] else 'plain'}, {'tstop' if k[1] else 'no tstop'}, {k[2]} units, trail {k[3]:.0f}, "  # noqa: E731
                      f"add {k[4]}R, BE {k[5]:.0f}R")
    lines = [f"backtest/trend_factorial.py, {pd.Timestamp.now():%Y-%m-%d %H:%M}; {len(D)} configs, corrected engine, 10 paired "
             f"orderings; tune < {cut:%Y-%m-%d} <= holdout; %/mo is CAGR/3", ""]
    m = D[D.cfg == MAIN].iloc[0]
    t = D[D.cfg == TRI].iloc[0]
    lines.append(f"  MAIN:   tune {m.tune:+.2f}%/mo DD {m.tdd:.0f}% | holdout {m.hold:+.2f}%/mo DD {m.hdd:.0f}% (holdout rank {m.hold_rank})")
    lines.append(f"  TRIPLE: tune {t.tune:+.2f}%/mo DD {t.tdd:.0f}% | holdout {t.hold:+.2f}%/mo DD {t.hdd:.0f}% (holdout rank {t.hold_rank})")
    pool = D[D.tdd <= m.tdd]
    pick = pool.sort_values("tune", ascending=False).iloc[0]
    lines.append(f"  HONEST PICK (best tune %/mo with a tune fall no deeper than MAIN's {m.tdd:.0f}%): {name(pick.cfg)}")
    lines.append(f"    tune {pick.tune:+.2f}%/mo DD {pick.tdd:.0f}% | HOLDOUT {pick.hold:+.2f}%/mo DD {pick.hdd:.0f}% - holdout rank "
                 f"{pick.hold_rank} of {len(D)}")
    lines.append(f"  configs beating MAIN on both halves by 2 paired se: {int(D.beats_main.sum())} of {len(D)}; beating the "
                 f"TRIPLE: {int(D.beats_triple.sum())}")
    lines.append("")
    lines.append("  TOP 10 BY HOLDOUT (read with care - the holdout is mined):")
    for _, r in D.sort_values("hold", ascending=False).head(10).iterrows():
        lines.append(f"    {name(r.cfg):58} tune {r.tune:+6.2f} DD {r.tdd:3.0f}% | hold {r.hold:+6.2f} DD {r.hdd:3.0f}% "
                     f"{'beats MAIN' if r.beats_main else ''} {'BEATS TRIPLE' if r.beats_triple else ''}")
    lines.append("")
    lines.append("  EACH PARAMETER'S AVERAGE EFFECT (mean holdout / tune %/mo by level, over all other settings):")
    for i, nm in enumerate(("tight", "time stop", "units", "trail", "add every", "BE at")):
        lv = D.cfg.map(lambda k: k[i])
        lines.append(f"    {nm:10} " + "  ".join(f"{str(v):12} tune {D.tune[lv == v].mean():+5.2f} hold {D.hold[lv == v].mean():+5.2f}"
                                               for v in sorted(lv.unique(), key=str)))
    D.assign(cfg=D.cfg.map(name)).to_csv(ROOT / "logs" / "trend_factorial.csv", index=False)
    txt = "\n".join(lines)
    print(txt)
    LOG.write_text(txt + "\n")


if __name__ == "__main__":
    main()
