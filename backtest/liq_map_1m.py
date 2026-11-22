"""THE LIQUIDATION MAP ON 1-MINUTE CANDLES: DOES PRICE SNAP BACK WITHIN MINUTES OF HITTING A CLUSTER? (2026-11-15)

THE USER (2026-11-15), after backtest/liq_map.py found no pass on hourly bars: "test it on 1 minute candles". The hourly test scored a
fill at the hour's close, so a sweep that fills and reverses within minutes - the scalp the user means - could not be seen there.

FILLS    exactly liq_map.py's events (the same coins, order and random draws, so the same 37,905 events and their controls): every big-
         cluster event whose order filled, and each of its FILLED controls (the same order the same distance away at a random time of
         the same coin within 30 days, same half). The fill HOUR comes from the hourly run; this file finds the minute.
DATA     Binance's daily 1-minute futures klines (data.binance.vision, dead coins included), the fill hour and the two hours after it,
         cached per fill in strategy_analysis/data/liqmap_1m/ (gitignored).
TRADE    entry in the first minute of the fill hour that trades 0.05% through the level (at the level, or at the minute's open if it
         opens past it). Exits: the close 5 / 15 / 60 minutes after the fill minute, and a SCALP bracket: stop 0.5% past the entry,
         target 1.0% (2R), out after 60 minutes; the fill minute counts as stopped if it also reaches the stop; a minute touching both =
         stopped; a gap through the stop exits at the minute's open. Costs 12bp a round trip + funding 1bp / 8h pro rata.
         A fill whose hour has no minute through the level (the hourly bar and the minute bars disagree) is dropped and counted.
CONTROL  as in liq_map.py: EXCESS = the cluster trade minus the mean of its filled controls (same exit, minute-scored the same way).
PASS     (per cell: long / short x 5m / 15m / 60m / scalp = 8) on BOTH halves (liq_map.py's CUT) net > 0 with t >= 2 AND excess > 0 with
         t >= 2 (day-clustered); Holm < 0.05 over the 8. MDE80 printed.
SECONDARY (registered now, before any 1-minute number): DEEP longs, clusters 8% or more under the close - crash-bid territory, where
         this repo's one surviving dip-buy lives - at 15m and 60m. Reported, Holm over its own 2.
DIAGNOSTIC the OVERSHOOT: how far past the level the price goes in the 5 minutes after the fill (median, % of the level), cluster vs
         control - is the 'exact price' exact?

REGISTERED BEFORE THE FIRST 1-MINUTE NUMBER (2026-11-15; my prior that any primary cell passes: about 5%)
  M1  No primary cell passes.
  M2  The overshoot after a cluster fill is AT LEAST the control's (forced trading pushes through the level, it does not stop at it).
  M3  |excess| under 10bp at 5m and 15m on both halves, both sides.
  M4  The scalp bracket loses after costs on both halves, both sides.
  M5  The deep-long secondary cells do not pass.

RESULT (2026-11-15, logs/liq_map_1m.txt): NO PASS, 0 of 8. The collection reproduced liq_map.py exactly (37,905 events, 9,366
cluster fills) plus 19,755 filled controls; every fill found its minute. Every primary cell's net is negative on both halves (scalp
bracket -20 / -20bp long, -18 / -23bp short, t -12..-14) and no excess over the controls reaches |t| 2. The OVERSHOOT: within 5 minutes
of a cluster fill the price runs a median 0.58% (long) / 0.55% (short) past the level against 0.48% / 0.48% for random levels, 0.5%+ in
55% / 53% vs 49% / 48% of fills - the cluster level is where forced trading pushes THROUGH, not where it stops. Secondary deep longs
(8%+ away): +31 / +35bp at 15 minutes, both halves positive (t 1.6 / 2.1), Holm 0.12, excess over random 8% dips ~0 (the dip, not the
cluster). M1, M2, M4, M5 right; M3 wrong (the short side's holdout excess at 15 / 60 minutes is -13 / -21bp). Planted bugs: 15 of 16, the
survivor equivalent (unfilled rows have no return, so they are dropped either way); control survived.

    python -m backtest.liq_map_1m --collect   (re-runs liq_map's events, ~10 minutes; writes the fills table)
    python -m backtest.liq_map_1m --fetch     (downloads the minute windows; resumable)
    python -m backtest.liq_map_1m             (scores them; logs/liq_map_1m.txt)
"""
from __future__ import annotations

import io
import pickle
import sys
import time
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest import candle_scan as cs  # noqa: E402
from backtest import liq_map as lm  # noqa: E402
from backtest import sweep_confluence as sc  # noqa: E402

OUT = ROOT / "strategy_analysis" / "data" / "liqmap_1m"
FILLS = OUT / "fills.pkl"
WINDOWS = OUT / "windows.pkl"
LOG = ROOT / "logs" / "liq_map_1m.txt"
URL = "https://data.binance.vision/data/futures/um/daily/klines/{s}/1m/{s}-1m-{d}.zip"
M = 60_000
H = lm.H
WIN_MIN = 180                                     # the fill hour + two hours
EXITS = {"5m": 5, "15m": 15, "60m": 60}
SC_STOP, SC_TGT, SC_MAX = 0.005, 0.010, 60
DEEP = 0.08
CELLS = [(s, x) for s in ("long", "short") for x in ("5m", "15m", "60m", "scalp")]


# ---------------------------------------------------------------- 1. the fills (liq_map's own events)

def collect():
    from backtest.market_neutral import drop_non_crypto
    from backtest.wide_book import eligibility
    el = drop_non_crypto(eligibility(40))
    grid_t = pd.date_range(lm.START, "2026-09-20", freq="4h")
    cut_ms = int(grid_t[int(len(grid_t) * 0.6)].value // 10**6)
    rng = np.random.default_rng(7)                # liq_map.main's seed, consumed in the same order
    rows, n_ev = [], 0
    for s in sorted(el):
        if not el[s]:
            continue
        x = lm.load_coin(s)
        if x is None:
            continue
        t, o, h, l, c, oi = x  # noqa: E741
        for k, ev in enumerate(lm.coin_events(t, o, h, l, c, oi, set(el[s]), rng, cut_ms)):
            n_ev += 1
            if ev["tr"] is None:
                continue
            eid = f"{s}:{k}"
            half = "tu" if t[ev["i"]] + H < cut_ms else "ho"
            rows.append(dict(eid=eid, coin=s, side=ev["side"], half=half, dist=ev["dist"], kind="cluster", level=ev["level"],
                             hour=int(t[ev["tr"]["j"]])))
            sg = 1 if ev["side"] == "long" else -1
            for cx in ev["ctrl"]:
                if cx["tr"] is not None:
                    rows.append(dict(eid=eid, coin=s, side=ev["side"], half=half, dist=ev["dist"], kind="control",
                                     level=c[cx["i"]] * (1 - sg * ev["dist"]), hour=int(t[cx["tr"]["j"]])))
    D = pd.DataFrame(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    D.to_pickle(FILLS)
    print(f"{n_ev} events (liq_map.txt: 37905); {(D.kind == 'cluster').sum()} cluster fills, {(D.kind == 'control').sum()} control fills")
    return D


# ---------------------------------------------------------------- 2. the minute windows

def parse_day(b: bytes):
    """(open time ms, open, high, low, close) arrays from one daily klines zip; a header row, if present, is dropped."""
    z = zipfile.ZipFile(io.BytesIO(b))
    d = pd.read_csv(z.open(z.namelist()[0]), header=None, usecols=[0, 1, 2, 3, 4])
    d = d[pd.to_numeric(d[0], errors="coerce").notna()].astype(float)
    return d[0].to_numpy(np.int64), d[1].to_numpy(), d[2].to_numpy(), d[3].to_numpy(), d[4].to_numpy()


def get_day(sym, day):
    for attempt in range(3):
        try:
            b = urllib.request.urlopen(urllib.request.Request(URL.format(s=sym, d=day), headers={"User-Agent": "forexbot"}), timeout=30).read()
            return parse_day(b)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            time.sleep(1 + attempt)
        except Exception:  # noqa: BLE001 - retry a blip
            time.sleep(1 + attempt)
    return None


def window(day_arrays: list, start_ms: int, n=WIN_MIN):
    """(n, 4) open / high / low / close for the minutes start_ms .. start_ms + n - 1 (NaN rows where a minute is missing)."""
    out = np.full((n, 4), np.nan)
    for arr in day_arrays:
        if arr is None:
            continue
        t, o, h, l, c = arr  # noqa: E741
        k = (t - start_ms) // M
        ok = (k >= 0) & (k < n) & ((t - start_ms) % M == 0)
        out[k[ok]] = np.column_stack([o[ok], h[ok], l[ok], c[ok]])
    return out


def fetch():
    D = pd.read_pickle(FILLS)
    W = pickle.loads(WINDOWS.read_bytes()) if WINDOWS.exists() else {}
    need = D[~D.apply(lambda r: (r.coin, r.hour) in W, axis=1)]
    days = {}
    for r in need.itertuples():
        for ms in (r.hour, r.hour + WIN_MIN * M - 1):
            days.setdefault((r.coin, pd.Timestamp(ms, unit="ms").strftime("%Y-%m-%d")), set()).add(r.hour)
    keys = sorted(days)
    print(f"{len(need)} fills need windows; {len(keys)} coin-days to fetch", flush=True)
    t0 = time.time()
    got = {}
    with ThreadPoolExecutor(32) as ex:
        for n_done, (k, arr) in enumerate(zip(keys, ex.map(lambda k: get_day(*k), keys)), 1):
            got[k] = arr
            if n_done % 2000 == 0:
                print(f"  {n_done}/{len(keys)} {time.time() - t0:.0f}s", flush=True)
    for r in need.itertuples():
        d0 = pd.Timestamp(r.hour, unit="ms").strftime("%Y-%m-%d")
        d1 = pd.Timestamp(r.hour + WIN_MIN * M - 1, unit="ms").strftime("%Y-%m-%d")
        W[(r.coin, r.hour)] = window([got.get((r.coin, d0))] + ([got.get((r.coin, d1))] if d1 != d0 else []), r.hour).astype(np.float32)
    WINDOWS.write_bytes(pickle.dumps(W))
    print(f"windows stored: {len(W)}; {time.time() - t0:.0f}s")


# ---------------------------------------------------------------- 3. scoring

def minute_trade(w, side, level):
    """The trade on one window (WIN_MIN x [o, h, l, c]). None if no minute of the FIRST hour trades through the level. Else signed
    returns before costs for each exit, the scalp's minutes held and the 5-minute overshoot past the level (fraction of the level)."""
    sg = 1 if side == "long" else -1
    o, h, l, c = (w[:, k].astype(float) for k in range(4))  # noqa: E741
    through = (l[:60] <= level * (1 - lm.THROUGH)) if sg > 0 else (h[:60] >= level * (1 + lm.THROUGH))
    hit = np.flatnonzero(np.nan_to_num(through, nan=0).astype(bool))
    if not hit.size:
        return None
    m = int(hit[0])
    fill = min(level, o[m]) if sg > 0 else max(level, o[m])
    if not np.isfinite(fill):
        fill = level
    out = dict(m=m, fill=fill)
    out.update(exits_from(w, sg, m, fill))
    w5 = slice(m, min(m + 6, len(c)))
    ext = np.nanmin(l[w5]) if sg > 0 else np.nanmax(h[w5])
    out["over"] = sg * (level - ext) / level
    return out


def exits_from(w, sg, m, fill):
    """Signed returns before costs of a position filled at `fill` in minute m (sg +1 long, -1 short): the close 5 / 15 / 60 minutes
    on (r5m / r15m / r60m) and the scalp bracket (rscalp, mscalp = minutes held). Shared with backtest/liq_map_past.py."""
    o, h, l, c = (w[:, k].astype(float) for k in range(4))  # noqa: E741
    out = {}
    for k, mm in EXITS.items():
        px = c[m + mm] if m + mm < len(c) else np.nan
        out["r" + k] = sg * (px / fill - 1) if np.isfinite(px) else np.nan
    stop, tgt = fill * (1 - sg * SC_STOP), fill * (1 + sg * SC_TGT)
    seg = slice(m + 1, min(m + 1 + SC_MAX, len(c)))
    if (l[m] <= stop) if sg > 0 else (h[m] >= stop):
        out["rscalp"], out["mscalp"] = sg * (stop / fill - 1), 1
    else:
        out["rscalp"], out["mscalp"] = np.nan, SC_MAX + 1
        for k in range(seg.start, seg.stop):
            if not np.isfinite(l[k]):
                continue
            if (l[k] <= stop) if sg > 0 else (h[k] >= stop):
                ex = min(stop, o[k]) if sg > 0 else max(stop, o[k])
                out["rscalp"], out["mscalp"] = sg * (ex / fill - 1), k - m + 1
                break
            if (h[k] >= tgt) if sg > 0 else (l[k] <= tgt):
                out["rscalp"], out["mscalp"] = sg * (tgt / fill - 1), k - m + 1
                break
        else:
            px = c[m + SC_MAX] if m + SC_MAX < len(c) else np.nan
            out["rscalp"] = sg * (px / fill - 1) if np.isfinite(px) else np.nan
    return out


def net(r, minutes):
    return r - lm.FEE - lm.FUND_H * minutes / 60


def score(D: pd.DataFrame, W: dict) -> pd.DataFrame:
    rows = []
    for r in D.itertuples():
        w = W.get((r.coin, r.hour))
        tr = None if w is None else minute_trade(w, r.side, r.level)
        x = dict(eid=r.eid, coin=r.coin, side=r.side, half=r.half, dist=r.dist, kind=r.kind, ok=tr is not None,
                 day=pd.Timestamp(r.hour, unit="ms").strftime("%Y-%m-%d"))
        if tr is not None:
            for k, mm in EXITS.items():
                x[k] = net(tr["r" + k], mm + 1)
            x["scalp"] = net(tr["rscalp"], tr["mscalp"])
            x["over"] = tr["over"]
        rows.append(x)
    return pd.DataFrame(rows)


def cell(S: pd.DataFrame, side, x, half, sub=None):
    d = S[(S.side == side) & (S.half == half) & S.ok]
    if sub is not None:
        d = d[sub(d)]
    cl = d[d.kind == "cluster"].dropna(subset=[x])
    ct = d[d.kind == "control"].dropna(subset=[x]).groupby("eid")[x].mean()
    if len(cl) < 3:
        return dict(n=len(cl), net=np.nan, t=np.nan, ex=np.nan, ex_t=np.nan, mde=np.nan)
    ex = (cl.set_index("eid")[x] - ct).dropna()
    days = cl.set_index("eid").loc[ex.index, "day"]
    y = cl[x].astype(float)
    return dict(n=len(cl), net=float(y.mean()), t=sc.t_by_day(y, cl.day), ex=float(ex.mean()) if len(ex) else np.nan,
                ex_t=sc.t_by_day(ex, days) if len(ex) > 2 else np.nan, mde=2.8 * float(y.std(ddof=1) / np.sqrt(len(y))))


def passes(st, holm_p):
    return all(st[h]["net"] > 0 and st[h]["t"] >= 2 and st[h]["ex"] > 0 and st[h]["ex_t"] >= 2 for h in ("tu", "ho")) and holm_p < 0.05


def fmt(name, st, hp):
    a, b = st["tu"], st["ho"]
    return (f"{name:<22}{a['n']:>5}/{b['n']:<6} NET {a['net'] * 1e4:+7.1f} ({a['t']:+.1f}) / {b['net'] * 1e4:+7.1f}bp ({b['t']:+.1f})   "
            f"EXCESS {a['ex'] * 1e4:+7.1f} ({a['ex_t']:+.1f}) / {b['ex'] * 1e4:+7.1f}bp ({b['ex_t']:+.1f})   MDE80 hold {b['mde'] * 1e4:4.0f}bp"
            f"  holm {hp:.2f}{'  PASS' if passes(st, hp) else ''}")


def holm_of(st, keys):
    return dict(zip(keys, cs.holm([cs.p_one_sided(np.nan_to_num(min(st[k]["tu"]["t"], st[k]["ho"]["t"]), nan=-10.0)) for k in keys])))


def main():
    t0 = time.time()
    D = pd.read_pickle(FILLS)
    W = pickle.loads(WINDOWS.read_bytes())
    S = score(D, W)
    st = {k: {h: cell(S, k[0], k[1], h) for h in ("tu", "ho")} for k in CELLS}
    hp = holm_of(st, CELLS)
    deep = [("long", "15m"), ("long", "60m")]
    st2 = {k: {h: cell(S, k[0], k[1], h, sub=lambda d: d.dist >= DEEP) for h in ("tu", "ho")} for k in deep}
    hp2 = holm_of(st2, deep)
    L = [f"backtest/liq_map_1m.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; liq_map.py's fills re-scored on Binance 1-minute bars: "
         f"{(S.kind == 'cluster').sum()} cluster fills, {(S.kind == 'control').sum()} control fills; with a minute through the level "
         f"{S[S.kind == 'cluster'].ok.mean() * 100:.1f}% / {S[S.kind == 'control'].ok.mean() * 100:.1f}%; 12bp + 1bp / 8h", ""]
    for side in ("long", "short"):
        a, b = S[(S.side == side) & (S.kind == "cluster") & S.ok], S[(S.side == side) & (S.kind == "control") & S.ok]
        L.append(f"OVERSHOOT {side}: past the level within 5 minutes of the fill, median {a.over.median() * 100:.2f}% (cluster) vs "
                 f"{b.over.median() * 100:.2f}% (control); 0.5% or more {np.mean(a.over >= 0.005) * 100:.0f}% vs {np.mean(b.over >= 0.005) * 100:.0f}%")
    L += ["", f"PRIMARY (tune / holdout){'':<6}", *[fmt(f"{k[0]} {k[1]}", st[k], hp[k]) for k in CELLS],
          "", "SECONDARY: deep longs (cluster 8%+ under the close)", *[fmt(f"deep {k[0]} {k[1]}", st2[k], hp2[k]) for k in deep]]
    npass = sum(passes(st[k], hp[k]) for k in CELLS)
    over = {s: (S[(S.side == s) & (S.kind == "cluster") & S.ok].over.median(), S[(S.side == s) & (S.kind == "control") & S.ok].over.median())
            for s in ("long", "short")}
    m3 = all(abs(st[(s, x)][h]["ex"]) < 0.0010 for s in ("long", "short") for x in ("5m", "15m") for h in ("tu", "ho"))
    m4 = all(st[(s, "scalp")][h]["net"] < 0 for s in ("long", "short") for h in ("tu", "ho"))
    m5 = not any(passes(st2[k], hp2[k]) for k in deep)
    L += ["", f"PASSING: {npass} of 8 primary", "REGISTERED PREDICTIONS",
          f"  M1 no primary cell passes -> {'RIGHT' if npass == 0 else 'WRONG'}",
          f"  M2 cluster overshoot >= control's -> {'RIGHT' if all(a >= b for a, b in over.values()) else 'WRONG'} "
          f"({', '.join(f'{s} {a * 100:.2f}% vs {b * 100:.2f}%' for s, (a, b) in over.items())})",
          f"  M3 |excess| < 10bp at 5m / 15m everywhere -> {'RIGHT' if m3 else 'WRONG'}",
          f"  M4 the scalp bracket loses on both halves, both sides -> {'RIGHT' if m4 else 'WRONG'}",
          f"  M5 the deep-long cells do not pass -> {'RIGHT' if m5 else 'WRONG'}",
          f"run time {time.time() - t0:.0f}s"]
    txt = "\n".join(L)
    LOG.write_text(txt + "\n", encoding="utf-8")
    S.to_pickle(LOG.with_suffix(".pkl"))
    print(txt)


if __name__ == "__main__":
    if "--collect" in sys.argv:
        collect()
    elif "--fetch" in sys.argv:
        fetch()
    else:
        main()
