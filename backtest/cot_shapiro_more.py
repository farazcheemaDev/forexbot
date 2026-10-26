"""SHAPIRO'S COT CONTRARIAN PROCESS ON THE NON-CURRENCY FUTURES MARKETS, AND POOLED WITH THE CURRENCIES (2026-10-27)

cot_shapiro.py (steps 1 + 3 of the tradermonty skills, exactly as coded there) ran on the 7 currency futures and was
unresolved: S +0.35% a trade before costs, its mirror -0.33%, but tune -0.02% / holdout +0.12% a week (t -0.4 / +2.1) and a
circular-shift null that gave p = 0.26 on the all-sample trade mean and p = 0.04 on the holdout week mean. Seven markets and
202 trades cannot settle that. CFTC publishes the same legacy report for gold, silver, WTI crude, the E-mini S&P 500 and
Nasdaq-100 and the 10-year note; Yahoo has their prices. Same rules, no change, new markets = new data, so the FX result
cannot be re-fitted: whatever the new markets do is out of sample for the rule (the rule was fixed by the skill's author).

DATA   CFTC legacy futures-only reports (cftc.gov, the same zip files fx_macro_data.build_cot reads), cached to
       strategy_analysis/data/fx_macro/cot_more.csv. Prices: Yahoo daily OHLC (fx_anomalies.yf_daily; continuous futures,
       so roll gaps of 1-3% sit in WTI / gold / silver / notes - flagged, not repaired; indices are cash indices).
       Entry at the first trading day's close of the week after the Friday report. Costs: fx_tsmom.py's table (round-trip
       spread bp, swap bp a night CHARGED BOTH WAYS - Exness grants swap-free to many accounts, so net is shown with and
       without swap). Currencies keep their real Exness swaps (fd.COST). 156-week COT Index, 90/10, the skills' three weekly
       detectors + continuation veto, exit at the index crossing 50 or the swing stop or 26 weeks. Step 2 (news failure) is
       manual in the skills and is NOT here.

REGISTERED BEFORE THE FIRST RUN (2026-10-27)
  X1  On the six NEW markets alone, S does not repeat the currencies' holdout result: its weekly Exness mean is not positive
      with t >= 2 on both halves (the FX result was chance-sized).
  X2  Pooled over all 13 markets, S does not PASS (positive, t >= 2 on BOTH halves, and better than C1 and C2 on both).
  X3  The circular-shift null on the pooled panel leaves the share of shifted panels at or above the real S holdout mean
      above 0.05 (the currencies' 0.04 does not strengthen).
  X4  The flipped trade (F8) is not positive pooled either.
  Reading: all four right -> the skill's COT chain is a drawing, not an edge, at retail cost; X2 or X3 wrong -> record it.

    python -m backtest.cot_shapiro_more [--null]
"""
from __future__ import annotations

import io
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest import cot_shapiro as cs  # noqa: E402
from backtest import fx_drivers as fd  # noqa: E402
from backtest import fx_macro_data as md  # noqa: E402
from backtest.fx_anomalies import yf_daily  # noqa: E402

LOG = ROOT / "logs" / "cot_shapiro_more.txt"
OUT = ROOT / "strategy_analysis" / "data" / "fx_macro"
#       name: (CFTC contract code, yahoo ticker, round-trip spread bp, swap bp a night charged both ways)  [fx_tsmom.py]
MKT = {"GOLD": ("088691", "GC=F", 1.2, 1.25), "SILVER": ("084691", "SI=F", 9.5, 1.33), "WTI": ("067651", "CL=F", 3.0, 2.0),
       "SP500": ("13874A", "^GSPC", 1.0, 2.0), "NASDAQ": ("209742", "^NDX", 1.0, 2.0), "NOTE10": ("043602", "ZN=F", 2.0, 1.0)}
NEW = list(MKT)


def cot_more() -> pd.DataFrame:
    f = OUT / "cot_more.csv"
    if f.exists():
        return pd.read_csv(f, parse_dates=["date"])
    names = ["deacot1986_2016.zip"] + [f"deacot{y}.zip" for y in range(2017, 2027)]
    frames = []
    for nm in names:
        z = zipfile.ZipFile(io.BytesIO(md.get(f"https://www.cftc.gov/files/dea/history/{nm}")))
        for inner in z.namelist():
            frames.append(pd.read_csv(z.open(inner), low_memory=False, encoding="latin-1"))
    d = pd.concat(frames, ignore_index=True)
    code = d["CFTC Contract Market Code"].astype(str).str.strip().str.zfill(6)
    rows = []
    for nm, (c, *_rest) in MKT.items():
        g = d[code == c]
        rows.append(pd.DataFrame({"date": pd.to_datetime(g["As of Date in Form YYYY-MM-DD"]), "ccy": nm,
                                  "nc_long": g["Noncommercial Positions-Long (All)"].astype(float),
                                  "nc_short": g["Noncommercial Positions-Short (All)"].astype(float),
                                  "oi": g["Open Interest (All)"].astype(float)}))
    out = pd.concat(rows).drop_duplicates(["date", "ccy"]).sort_values(["ccy", "date"], kind="stable")
    out[out.date >= "1995-01-01"].to_csv(f, index=False)
    return out


def cost(c):
    if c in fd.COST:
        return fd.COST[c]
    _, _, sp, sw = MKT[c]
    return (sp, -sw, -sw)


def build_all():
    starts, ret, nights, ci, px, bars = cs.build()
    cot = cot_more()
    net = (cot.nc_long - cot.nc_short).to_frame("net").join(cot[["date", "ccy"]])
    p = net.pivot_table(index="date", columns="ccy", values="net")[NEW]
    mn, mx = p.rolling(cs.LOOK_IDX, min_periods=cs.LOOK_IDX).min(), p.rolling(cs.LOOK_IDX, min_periods=cs.LOOK_IDX).max()
    idx = (p - mn) / (mx - mn).replace(0, np.nan) * 100
    idx.index = idx.index + pd.Timedelta(days=3)
    ci2 = fd.asof(idx, starts)[NEW]
    px2, bars2 = {}, {}
    for nm, (_, tk, _, _) in MKT.items():
        d = yf_daily(tk, start="1995-01-01")
        d = d[~(d.Close.pct_change().abs() > 0.25)]                                    # bad prints
        px2[nm] = d.Close.reindex(starts).ffill(limit=3)
        g = d.groupby(d.index.to_period("W-SUN"))
        bars2[nm] = pd.DataFrame(dict(o=g.Open.first(), h=g.High.max(), l=g.Low.min(), c=g.Close.last()))
    px2 = pd.DataFrame(px2)
    names = list(cs.CCY) + NEW
    ci_all = pd.concat([ci, ci2], axis=1)[names]
    px_all = pd.concat([px, px2], axis=1)[names]
    ret_all = px_all.shift(-1) / px_all - 1
    return starts, ret_all, nights, ci_all, px_all, {**bars, **bars2}, names


def run_generic(pos, ret, nights, names):
    pos = pos.reindex(ret.index).fillna(0.0)[names]
    pos = pos.where(ret[names].notna(), 0.0)
    n_on = (pos != 0).sum(axis=1).replace(0, np.nan)
    turn = (pos - pos.shift(1).fillna(0)).abs()
    sp = pd.Series({c: cost(c)[0] for c in names})
    swl = pd.Series({c: cost(c)[1] for c in names})
    sws = pd.Series({c: cost(c)[2] for c in names})
    swap = (pos.clip(lower=0) * swl + (-pos).clip(lower=0) * sws).mul(nights, axis=0) / 1e4
    gross = pos * ret[names].fillna(0)
    spot = gross.sum(axis=1) / n_on
    ex = (gross - turn * sp / 2 / 1e4 + swap).sum(axis=1) / n_on
    exsf = (gross - turn * sp / 2 / 1e4).sum(axis=1) / n_on
    keep = n_on.notna()
    return spot[keep].dropna(), ex[keep].dropna(), exsf[keep].dropna()


def report(label, names, starts, ret, nights, ci, px, bars, cache, L, variants=("S", "C1", "C2", "S8", "F8", "C1_8", "C2_8")):
    L.append(f"-- {label}: {', '.join(names)}")
    L.append(f"  {'variant':6} {'trades':>6} {'median wks':>10} | per TRADE spot   net(swap)  net(swap-free) win | per ACTIVE WEEK, swap-free: "
             f"all (t)      tune (t)       holdout (t)")
    res = {}
    for v in variants:
        pos, tr = cs.simulate(v, starts, ci[names], px[names], bars, cache, names)
        ts = cs.trade_stats(tr, px[names], None, cost)
        ts_sf = cs.trade_stats(tr, px[names], None, lambda c: (cost(c)[0], 0.0, 0.0))
        if not len(ts):
            L.append(f"  {v:6} no trades")
            continue
        sp_, ex_, sf_ = run_generic(pos, ret, nights, names)
        e, f = fd.stat(ex_, 52), fd.stat(sf_, 52)
        res[v] = (ts, e, f)
        L.append(f"  {v:6} {len(ts):>6} {ts.weeks.median():>10.1f} | spot {ts.spot.mean() * 100:>+6.2f}% {ts.net.mean() * 100:>+7.2f}% "
                 f"{ts_sf.net.mean() * 100:>+10.2f}%   {(ts_sf.net > 0).mean() * 100:>3.0f}% | {f['mean'] * 100:>+7.3f}% (t {f['t']:+.1f}) "
                 f"{f['tu'] * 100:>+7.3f}% ({f['t_tu']:+.1f}) {f['ho'] * 100:>+7.3f}% ({f['t_ho']:+.1f})")
    L.append("")
    return res


def main():
    starts, ret, nights, ci, px, bars, names = build_all()
    L = [f"backtest/cot_shapiro_more.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; 13 CFTC futures markets "
         f"{starts.min():%Y-%m-%d} .. {starts.max():%Y-%m-%d}; steps 1 + 3 only; net shown with and without swap", ""]
    cache = {}
    new = report("THE SIX NEW MARKETS", NEW, starts, ret, nights, ci, px, bars, cache, L)
    allr = report("POOLED, ALL 13", names, starts, ret, nights, ci, px, bars, cache, L)
    for nm in NEW:
        pos, tr = cs.simulate("S", starts, ci[names], px[names], bars, cache, names)
        ts = cs.trade_stats([t for t in tr if t[0] == nm], px[names], None, lambda c: (cost(c)[0], 0.0, 0.0))
        L.append(f"  S in {nm:7}: {len(ts):3} trades, spot {ts.spot.mean() * 100 if len(ts) else float('nan'):+.2f}%, "
                 f"net swap-free {ts.net.mean() * 100 if len(ts) else float('nan'):+.2f}%")
    S_new, S_all = new.get("S"), allr.get("S")
    ok_both = lambda f: f["tu"] > 0 and f["ho"] > 0 and f["t_tu"] >= 2 and f["t_ho"] >= 2  # noqa: E731
    x1 = S_new is not None and not ok_both(S_new[2])
    passed = (S_all is not None and ok_both(S_all[2]) and S_all[2]["tu"] > allr["C1"][2]["tu"] and S_all[2]["ho"] > allr["C1"][2]["ho"]
              and S_all[2]["tu"] > allr["C2"][2]["tu"] and S_all[2]["ho"] > allr["C2"][2]["ho"])
    L += ["", "REGISTERED PREDICTIONS (swap-free weekly series)",
          f"  X1 the new markets alone do not pass both halves (t >= 2) -> {'RIGHT' if x1 else 'WRONG'}",
          f"  X2 pooled S does not PASS -> {'RIGHT' if not passed else 'WRONG'}"]
    if "--null" in sys.argv:
        rng = np.random.default_rng(11)
        base = fd.stat(run_generic(cs.simulate("S", starts, ci[names], px[names], bars, cache, names)[0], ret, nights, names)[2], 52)["ho"]
        hos, s8s = [], []
        base8 = cs.trade_stats(cs.simulate("S8", starts, ci[names], px[names], bars, cache, names)[1], px[names], None, cost).spot.mean()
        for _ in range(300):
            k = int(rng.integers(26, len(starts) - 26))
            sh = pd.DataFrame(np.roll(ci[names].to_numpy(), k, axis=0), index=ci.index, columns=names)
            pp, _ = cs.simulate("S", starts, sh, px[names], bars, cache, names)
            hos.append(fd.stat(run_generic(pp, ret, nights, names)[2], 52)["ho"])
            t8 = cs.trade_stats(cs.simulate("S8", starts, sh, px[names], bars, cache, names)[1], px[names], None, cost)
            s8s.append(t8.spot.mean() if len(t8) else np.nan)
        hos, s8s = np.array(hos, float), np.array(s8s, float)
        ph, p8 = float(np.nanmean(hos >= base)), float(np.nanmean(s8s >= base8))
        L += ["", "NULL TEST on the pooled panel (300 circular shifts of the COT Index panel; swap-free)",
              f"  S holdout weekly mean: real {base * 100:+.4f}% | shifted mean {np.nanmean(hos) * 100:+.4f}% -> share >= real {ph:.3f}",
              f"  S8 spot mean per trade: real {base8 * 100:+.3f}% | shifted mean {np.nanmean(s8s) * 100:+.3f}% -> share >= real {p8:.3f}",
              f"  X3 share >= real above 0.05 -> {'RIGHT' if ph > 0.05 else 'WRONG'}"]
    f8 = allr.get("F8")
    if f8 is not None:
        L.append(f"  X4 F8 pooled not positive: net {f8[0].net.mean() * 100:+.2f}% a trade -> {'RIGHT' if f8[0].net.mean() <= 0 else 'WRONG'}")
    L.append(f"  VERDICT: {'PASS' if passed else 'NO PASS'}")
    txt = "\n".join(L)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
