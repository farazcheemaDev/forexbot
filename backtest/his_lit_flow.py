"""ON-EXCHANGE BUYING AND SELLING IN QQQ AND THE 8 NASDAQ MEGA-CAPS BEFORE HIS CLICKS (2026-11-21)

THE USER (2026-11-21): "test what we can" - the last public second-level source on the list: the big NASDAQ stocks' own buying and
selling. his_darkpool.py (2026-10-16) downloaded EVERY XNAS.BASIC print in QQQ NVDA MSFT AAPL AMZN GOOGL META AVGO TSLA for his 31
windows (22 min before to 20 min after each NASDAQ click; $6.07 then, cached in strategy_analysis/data/nasdaq_basic_trades.pkl) but used
only the OFF-exchange prints (FINN / FINC: 13.5M). The ON-exchange prints (Nasdaq's own markets - XNAS, BX, PSX: ~4.8M) were never
tested. No new data is bought.
SIGNAL   the lit prints only (publishers other than FINN / FINC). Side by the tick rule against the symbol's previous print on any venue
         (his_darkpool's rule): up-tick = buy. Signed notional (his way > 0) over the 5 / 15 / 30 / 60 / 120 s before T, for ALL nine
         names together, for NVDA alone (the heaviest and busiest) and for QQQ alone.
TESTS    his_darkpool's three, unchanged: A his side vs the sign (binomial); B his moment's rank among his sitting's moments (Wilcoxon on
         the ranks); C the rule at the sittings' moments: trade with a top-quintile reading, +-7 race on the Exness mid, against the
         sittings' baseline for his side; also the unsigned rule (with / against the flow's own sign).
REGISTERED BEFORE THE FIRST NUMBER (2026-11-21)
  L1  A within 35-65% for every feature. (75%)
  L2  B within 0.40-0.60 for every feature. (70%)
  L3  C within 5 points of the baseline for every feature. (75%)
  LEAD LINE (his_darkpool's): A >= 75% with p < 0.01 or B >= 0.65 with p < 0.01, AND the rule beats the baseline by >= 10 points.

RESULT (2026-11-21, logs/his_lit_flow.txt): RULED OUT, the last public second-level source. 17.9M cached prints, 4.4M on-exchange (EQUS,
  XBOS, XNAS, XPSX; $151.5bn); 46 of his entries, 1,763 sitting moments, baseline 55.7%. His side vs the lit buy-minus-sell notional over
  5-120 s: 48-61% (every p >= 0.17) for all nine names, NVDA alone and QQQ alone; his moment's rank in his sitting 0.48-0.56 (every p >=
  0.24); trading with the top-quintile flow 50-57% (baseline 55.7%), with / against the flow's own sign 46-54%. L1, L2 right; L3 wrong by a
  hair on the low side (one cell 50%); the lead line not hit.

    python -m backtest.his_lit_flow
"""
from __future__ import annotations

import pickle
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import backtest.his_tape as TP  # noqa: E402
from backtest.his_darkpool import call, fetch  # noqa: E402
from backtest.his_race_curve import race2  # noqa: E402

LOG = ROOT / "logs" / "his_lit_flow.txt"
W = (5, 15, 30, 60, 120)
GROUPS = {"all9": None, "nvda": {"NVDA"}, "qqq": {"QQQ"}}


def main():
    from scipy.stats import binomtest, wilcoxon
    warnings.filterwarnings("ignore")
    x = TP.entries()
    wins = TP.windows(x)
    cl = TP.client()
    pubs = [p for p in call(cl.metadata.list_publishers) if p["dataset"] == "XNAS.BASIC"]
    dark_ids = {p["publisher_id"] for p in pubs if p["venue"] in ("FINN", "FINC")}
    lit_names = sorted({p["venue"] for p in pubs if p["venue"] not in ("FINN", "FINC")})
    from backtest.his_darkpool import CACHE
    cached = pickle.loads(CACHE.read_bytes())
    missing = [w for w in wins if (str(w[0]), str(w[1])) not in cached]
    assert not missing, f"{len(missing)} windows are not in the cache - refusing to download (no spend without the user's OK)"
    T = fetch(cl, wins)                                     # every window is cached: nothing is downloaded
    T["sign"] = 0
    for s, g in T.groupby("sym"):
        d = np.sign(np.diff(np.r_[g.px.iat[0], g.px.to_numpy()]))
        d = pd.Series(np.where(d == 0, np.nan, d)).ffill().fillna(0).to_numpy()
        T.loc[g.index, "sign"] = d
    T["notional"] = T.px * T.sz
    L = T[~T.pub.isin(dark_ids)].reset_index(drop=True)
    cum = {}
    for gname, syms in GROUPS.items():
        g = L if syms is None else L[L.sym.isin(syms)]
        cum[gname] = (g.ns.to_numpy(), np.r_[0.0, np.cumsum(g.sign * g.notional)])
    ticks = pickle.loads(TP.TICKS.read_bytes())
    rows = []
    for r in x.itertuples():
        day = ticks.get(r.d)
        if day is None:
            continue
        ts, mid, _ = day
        base = (r.d + pd.Timedelta(hours=9, minutes=30)).tz_localize("America/New_York").tz_convert("UTC").tz_localize(None).value
        others = x[x.d == r.d].t.to_numpy()
        starts = [("his", r.t)] + [("near", r.t + 60 * m) for m in list(range(-20, 0)) + list(range(1, 21))
                                   if np.min(np.abs(others - (r.t + 60 * m))) >= 60]
        for who, t in starts:
            at = base + int(t * 1e9)
            f = {}
            for gname, (ns, flow) in cum.items():
                j = np.searchsorted(ns, at, "right")
                for w in W:
                    i = np.searchsorted(ns, at - w * 10**9, "right")
                    f[f"{gname}_{w}s"] = r.s * (flow[j] - flow[i])
            rows.append(dict(entry=r.Index, who=who, s=r.s, up=race2(ts, mid, t, 1, 600, 7, 7), **f))
    D = pd.DataFrame(rows)
    H, N = D[D.who == "his"], D[D.who == "near"]
    nb = N.dropna(subset=["up"])
    base = np.where(nb.s > 0, nb.up, 1 - nb.up).mean()
    out = [f"backtest/his_lit_flow.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; {len(T):,} prints in {len(wins)} windows (cached), "
           f"{len(L):,} ON-exchange ({', '.join(lit_names)}; {L.notional.sum() / 1e9:.1f} $bn); {len(H)} of his entries, {len(N)} sitting moments",
           f"baseline: his side at the sittings' moments wins {base * 100:.1f}%", "",
           f"  {'feature':>11}{'agree':>8}{'p':>8}{'rank':>8}{'p':>8}{'rule':>8}{'n':>6}"]
    res = {}
    for k in [c for c in D.columns if c.startswith(tuple(GROUPS))]:
        v = H[k][H[k] != 0]
        ag = (v > 0).mean() if len(v) else np.nan
        pa = binomtest(int((v > 0).sum()), len(v), 0.5).pvalue if len(v) else np.nan
        rk = []
        for _, g in D.groupby("entry"):
            h, n = g[g.who == "his"], g[g.who == "near"]
            if len(h) and len(n) >= 10:
                rk.append((n[k] < h[k].iat[0]).mean() + 0.5 * (n[k] == h[k].iat[0]).mean())
        pb = wilcoxon(np.array(rk) - 0.5).pvalue if len(rk) > 5 and np.any(np.array(rk) != 0.5) else np.nan
        hi = nb[nb[k] >= nb[k].quantile(0.8)]
        hi = hi[hi[k] > 0]
        rule = np.where(hi.s > 0, hi.up, 1 - hi.up).mean() if len(hi) else np.nan
        raw = nb[k] * nb.s
        big = nb[(raw.abs() >= raw.abs().quantile(0.8)) & (raw != 0)]
        rb = big[k] * big.s
        w_with = np.where(rb > 0, big.up, 1 - big.up).mean() if len(big) else np.nan
        res[k] = (ag, pa, np.mean(rk), pb, rule)
        out.append(f"  {k:>11}{ag * 100:>7.0f}%{pa:>8.3f}{np.mean(rk):>8.2f}{pb:>8.3f}{rule * 100:>7.0f}%{len(hi):>6}"
                   f"   (n {len(v)}; any side: WITH the flow {w_with * 100:.0f}%, AGAINST {100 - w_with * 100:.0f}% of {len(big)})")
    lead = [k for k, v in res.items() if ((v[0] >= 0.75 and v[1] < 0.01) or (v[2] >= 0.65 and v[3] < 0.01)) and v[4] - base >= 0.10]
    A = [v[0] for v in res.values() if np.isfinite(v[0])]
    B = [v[2] for v in res.values()]
    Cc = [v[4] for v in res.values() if np.isfinite(v[4])]
    out += ["", "REGISTERED PREDICTIONS",
            f"  L1 A within 35-65%: {min(A) * 100:.0f}..{max(A) * 100:.0f}% -> {'RIGHT' if min(A) >= 0.35 and max(A) <= 0.65 else 'WRONG'}",
            f"  L2 B within 0.40-0.60: {min(B):.2f}..{max(B):.2f} -> {'RIGHT' if min(B) >= 0.40 and max(B) <= 0.60 else 'WRONG'}",
            f"  L3 C within 5 points of {base * 100:.0f}%: {min(Cc) * 100:.0f}..{max(Cc) * 100:.0f}% -> "
            f"{'RIGHT' if all(abs(c - base) <= 0.05 for c in Cc) else 'WRONG'}",
            f"  LEAD LINE: {', '.join(lead) if lead else 'not hit'}"]
    txt = "\n".join(out)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
