"""THE DAILY BOOK x EVERYTHING THAT WORKED - every combination not yet run (2026-10-08, goal: "run every type of
combination we haven't ran for the things which worked").

The daily book (pair_lab.daily_trades): close above Bollinger(30, 1.5) on DAILY bars, in at the next open, out at the
next open after a close under the 30-day mean, 30-day cap; point-in-time top-40, dead coins in, 12bp + funding. Tested
so far: 6 day boundaries, cap 30/60/90/365, slots 8-24, a shared pool, gates not-bear / BTC 1000h, the 21-day anchor.
NEVER combined with the rest of what worked here. This file does that, one dimension at a time, then stacks the passers:

    P  Bollinger neighbours (is 30 / 1.5 a peak or a plateau?): 20/1.5, 30/1.0, 30/2.0, 50/1.5, 20/2.0
    X  exits from the trend book and elsewhere: ATR trail 3/5/8 (close basis), mean-or-trail-5, faster means (10/20),
       an initial 2xATR stop, a time stop (out after 10 days if not +5%), breakeven after +10%, and the BTC exit (out
       when BTC closes under its own 20-day mean - the daily cousin of v2's "tight exit")
    U  pyramiding (the trend book's 7-unit finding): add a unit at every +10% / +20% close, up to 3 units
    F  entry filters (each read at the signal close): breadth20 >= 50% / <= 50%, 30-day momentum rank in the top half,
       above the 200-day EMA, volume >= 1.5x / 2x its 20-day average, Fear & Greed < 75 / > 50 (1-day-safe), BTC 28-day
       return > 0, BTC above its 50-day mean, daily RSI(14) < 80, a new 50-day high, not overextended ((close - upper
       band) / ATR < 1)
    Q  which signal gets a free slot (the book skips ~half its signals): highest momentum rank, highest volume ratio,
       calmest (lowest ATR%), strongest break - instead of random

METHOD. 3 day boundaries (00/08/16 UTC) x 10 random same-day orders. One book on the whole account: 8 slots of an
eighth, 1x, MARKED TO MARKET daily (v2_addons.py showed booking at the close moves the worst month 2 points). Cap and
stop exits free their slot at the END of the bar (mistake #17). Per variant: CAGR on the tune half / holdout (split
2024-04-07), biggest fall, worst month; paired against the base on the same day boundary and order.
PASS (registered): beats the base's own leverage line (the base at 0.5 / 0.75 / 1 / 1.25 / 1.5x) at the SAME biggest
fall, on the tune half AND the holdout, at ALL 3 day boundaries. A filter that only trades less cannot pass by being
smaller - the line catches it. ~37 variants against one mined holdout: a single pass is not a finding until the stack
and the forward paper agree.

REGISTERED BEFORE RUNNING (2026-10-08):
    P  >= 4 of 5 neighbours positive on both halves at all 3 boundaries (a plateau); none passes the line by much.
    X  ATR trails lose to the mean exit on the holdout; faster means / the 2xATR stop / breakeven cut the fall and
       fail the line; the BTC exit is the one exit that passes (v2's tight exit did).
    U  pyramiding raises CAGR and fall; at the same fall it passes the tune half, not the holdout.
    F  momentum top-half passes; volume, Fear & Greed, RSI < 80 and not-overextended fail (the strongest breaks pay);
       the rest tie. At most 3 of 13 pass.
    Q  momentum priority passes; volume priority fails; the others tie.
    Overall at most 5 of ~37 pass at all 3 boundaries; their stack keeps at most two-thirds of the summed gains.

RESULT (2026-10-08, logs/daily_combos.txt): 0 of 37 pass. Base: +133% tune / +41% holdout CAGR, fall 64%, worst
    month -27% (8 slots 1x, marked). Bollinger neighbours all lose (bb(50,1.5) holdout better, tune worse); every ATR
    trail loses the holdout; faster means / stops / breakeven / time stop fail; the BTC exit cuts the fall to 52% and
    fails one cell; pyramiding falls 87-92%; every filter fails (above-200EMA, volume, new-high, F&G>50 help the holdout
    and cost the tune half - the mined-holdout signature); priorities tie. FRAGILITY (scratchpad check, same day): the
    holdout rests on 5 trades - MYX 2025-09, RIVER 2026-01, AKE 2026-09, PIPPIN 2025-12, SOON/PENGU 2025 - and without
    them the holdout CAGR is -30..-39%/yr at all 3 boundaries. Predictions: P plateau - partly (none pass, several
    lose badly); X BTC exit passes - WRONG (fails one cell); U - right; F momentum passes - WRONG; Q - WRONG (momentum
    priority fails); "at most 5 pass" - right (0).

    python -m backtest.daily_combos
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest import pair_lab as pl  # noqa: E402
from backtest.capitulation_wide import funding_cum  # noqa: E402
from backtest.rsi_factors import prep  # noqa: E402
from backtest.sentiment import fng  # noqa: E402
from backtest.tv_indicators import bars  # noqa: E402

CACHE = ROOT / "logs" / "daily_combos_cache"
LOG = ROOT / "logs" / "daily_combos.txt"
HOLDOUT = pl.HOLDOUT
FEE = 0.0012
PHASES = (0, 8, 16)
SEEDS = tuple(range(10))
SLOTS = 8
LEVS = (0.5, 0.75, 1.0, 1.25, 1.5)
DAY = np.timedelta64(1, "D")
BASE = dict(n=30, k=1.5, exit="mean", mean_n=30, trail=None, stop=None, tstop=None, be=None, btc_exit=False, cap=30,
            pyr=None, filt=None, prio=None)


def panel(off):
    f = CACHE / f"panel_{off}.pkl"
    if f.exists():
        return pickle.loads(f.read_bytes())
    el = pl.universe()
    out = {}
    for s, h in pl.hourly_all().items():
        d = bars(h, "1d", off * 60)
        if len(d) < 120:
            continue
        P = prep(d, np.full(len(d), np.nan))
        P["t"] = d.time.to_numpy("datetime64[ns]")
        P["fc"] = funding_cum(s, d.time.to_numpy(), h)
        P["ym"] = d.time.dt.strftime("%Y-%m").to_numpy()
        P["el"] = el[s]
        out[s] = P
    CACHE.mkdir(parents=True, exist_ok=True)
    f.write_bytes(pickle.dumps(out))
    return out


_X: dict = {}


def features(off):
    """Per coin, arrays aligned to its bars: breadth20, momentum rank, volume ratio, BTC context, Fear & Greed..."""
    if off in _X:
        return _X[off]
    PN = panel(off)
    C = pd.DataFrame({s: pd.Series(P["c"], index=P["t"]) for s, P in PN.items()}).sort_index()
    ym = C.index.strftime("%Y-%m")
    elig = pd.DataFrame({s: ym.isin(list(PN[s]["el"])) for s in C.columns}, index=C.index) & C.notna()
    above = (C > C.rolling(20).mean()) & elig
    breadth = above.sum(axis=1) / elig.sum(axis=1).replace(0, np.nan)
    rank = (C / C.shift(30) - 1).where(elig).rank(axis=1, pct=True)
    b = PN["BTCUSDT"]
    bc = pd.Series(b["c"], index=b["t"])
    btc = pd.DataFrame({"c": bc, "m20": bc.rolling(20).mean(), "m50": bc.rolling(50).mean(), "r28": bc / bc.shift(28) - 1})
    fg = fng()
    out = {}
    for s, P in PN.items():
        t = P["t"]
        c = P["c"]
        bt = btc.reindex(pd.DatetimeIndex(t))
        m = pd.Series(c).rolling(30).mean().to_numpy()
        sd = pd.Series(c).rolling(30).std(ddof=0).to_numpy()
        close_day = (pd.DatetimeIndex(t) + pd.Timedelta(days=1)).floor("D")           # the signal is read at the close
        out[s] = dict(br=breadth.reindex(pd.DatetimeIndex(t)).to_numpy(), rk=rank[s].reindex(pd.DatetimeIndex(t)).to_numpy(),
                      vr=P["v"] / P["vavg"], atrp=P["atr"] / c, ema200=P["ema200"],
                      hi50p=np.r_[np.nan, P["hi50"][:-1]], ext=(c - (m + 1.5 * sd)) / P["atr"],
                      btc_c=bt.c.to_numpy(), btc_m20=bt.m20.to_numpy(), btc_m50=bt.m50.to_numpy(), btc_r28=bt.r28.to_numpy(),
                      fg=fg.reindex(close_day, method="ffill").to_numpy())
    _X[off] = out
    return out


def gen(off, cfg):
    """All trades of one variant: coin, t_in, t_out, net (per BASE unit), worst (deepest loss, per base unit), units
    [(t, price)], score (for slot priority)."""
    PN, X = panel(off), features(off)
    rows = []
    for s, P in PN.items():
        o, h, l, c, atr, t, fc = P["o"], P["h"], P["l"], P["c"], P["atr"], P["t"], P["fc"]
        F = X[s]
        n = len(c)
        S = pd.Series(c)
        m = S.rolling(cfg["n"]).mean().to_numpy()
        sd = S.rolling(cfg["n"]).std(ddof=0).to_numpy()
        ent = np.nan_to_num(c > m + cfg["k"] * sd).astype(bool) if cfg.get("entry") is None             else np.nan_to_num(cfg["entry"](P)).astype(bool)
        mx = S.rolling(cfg["mean_n"]).mean().to_numpy()
        exs = c < mx
        ym, el = P["ym"], P["el"]
        free = 0
        for i in np.flatnonzero(ent):
            if i < 60 or i < free or i + 3 >= n or ym[i] not in el:
                continue
            if cfg["filt"] is not None and not cfg["filt"](F, P, i):
                continue
            e = o[i + 1]
            units = [(i + 1, e)]
            j_end = min(i + 1 + cfg["cap"], n - 2)
            best, worst, be_on = c[i + 1], 0.0, False
            stop_lv = e - cfg["stop"] * atr[i] if cfg["stop"] else None
            jo, x, t_out, why = None, None, None, "cap"
            for j in range(i + 1, j_end + 1):
                if stop_lv is not None and l[j] <= stop_lv:
                    x = min(o[j], stop_lv)
                    worst = max(worst, sum(1 - l[j] / eu for ju, eu in units if ju <= j))
                    jo, t_out, why = j, t[j] + DAY, "stop"
                    break
                worst = max(worst, sum(1 - l[j] / eu for ju, eu in units if ju <= j))
                best = max(best, c[j])
                hit = None
                if cfg["exit"] in ("mean", "mean_or_trail") and exs[j]:
                    hit = "mean"
                if cfg["trail"] and cfg["exit"] in ("trail", "mean_or_trail") and c[j] < best - cfg["trail"] * atr[j]:
                    hit = "trail"
                if cfg["tstop"] and j == i + cfg["tstop"][0] and c[j] < e * (1 + cfg["tstop"][1]):
                    hit = "tstop"
                if cfg["be"]:
                    be_on = be_on or c[j] >= e * (1 + cfg["be"])
                    if be_on and c[j] < e:
                        hit = "be"
                if cfg["btc_exit"] and F["btc_c"][j] < F["btc_m20"][j]:
                    hit = "btc"
                if hit:
                    jo, why = j + 1, hit
                    x, t_out = o[jo], t[jo]
                    break
                if cfg["pyr"] and len(units) < cfg["pyr"][1] and j + 1 <= j_end \
                        and c[j] >= e * (1 + cfg["pyr"][0] * len(units)):
                    units.append((j + 1, o[j + 1]))
            if jo is None:
                jo, x, t_out = j_end, c[j_end], t[j_end] + DAY
            net = sum(x / eu - 1 - FEE - (fc[jo] - fc[ju]) / eu for ju, eu in units)
            sc = 0.0
            if cfg["prio"] is not None:
                sc = cfg["prio"](F, P, i)
            rows.append((s, t[i + 1], t_out, net, worst, [(t[ju], eu) for ju, eu in units], why, sc))
            free = jo
    T = pd.DataFrame(rows, columns=["coin", "t_in", "t_out", "net", "worst", "units", "why", "score"])
    T["score"] = T.score.fillna(-np.inf)
    return T


def allocate(T, seed, lev=1.0, prio=False):
    rng = np.random.default_rng(seed)
    rnd = rng.random(len(T))
    tin = T.t_in.to_numpy("datetime64[ns]")
    key = -T.score.to_numpy() if prio else np.zeros(len(T))
    order = sorted(range(len(T)), key=lambda q: (tin[q], key[q], rnd[q]))
    tout, net, worst = T.t_out.to_numpy("datetime64[ns]"), T.net.to_numpy(), T.worst.to_numpy()
    liq = 1 / lev - 0.005 - 0.0006
    eq, open_, out = 1.0, [], []
    for q in order:
        for p in sorted([p for p in open_ if p[0] <= tin[q]], key=lambda p: p[0]):
            eq += p[1]
        open_ = [p for p in open_ if p[0] > tin[q]]
        if eq <= 0:
            break
        if len(open_) >= SLOTS:
            continue
        size = eq / SLOTS
        pnl = -size if worst[q] >= liq else size * max(lev * net[q], -1.0)
        open_.append((tout[q], pnl))
        out.append((q, size, pnl))
    return out


def curve(T, taken, off, lev=1.0):
    """Marked-to-market daily equity (value at each UTC day's end)."""
    PN = panel(off)
    q = np.array([a for a, _, _ in taken])
    size = np.array([b for _, b, _ in taken])
    pnl = np.array([c for _, _, c in taken])
    tin = T.t_in.to_numpy("datetime64[ns]")[q]
    tout = T.t_out.to_numpy("datetime64[ns]")[q]
    days = pd.date_range(pd.Timestamp(tin.min()).normalize(), pd.Timestamp(tout.max()).normalize() + pd.Timedelta(days=1))
    E = (days + pd.Timedelta(days=1)).to_numpy("datetime64[ns]")
    o = np.argsort(tout, kind="stable")
    cum = np.concatenate([[0.0], np.cumsum(pnl[o])])
    real = 1 + cum[np.searchsorted(tout[o], E, side="left")]
    mark = np.zeros(len(E))
    coins, units = T.coin.to_numpy()[q], T.units.to_numpy()[q]
    for k in range(len(q)):
        k0 = np.searchsorted(E, tin[k], side="right")
        k1 = np.searchsorted(E, tout[k], side="right")
        if k1 <= k0:
            continue
        P = PN[coins[k]]
        cl = P["c"]
        idx = np.clip(np.searchsorted(P["t"] + DAY, E[k0:k1], side="right") - 1, 0, len(cl) - 1)
        mv = np.zeros(k1 - k0)
        for tu, eu in units[k]:
            mv += np.where(E[k0:k1] > np.datetime64(tu, "ns"), cl[idx] / eu - 1, 0.0)
        mark[k0:k1] += size[k] * np.maximum(lev * mv, -1.0)
    return pd.Series(real + mark, index=days)


def stats(c):
    def cg(x):
        yrs = (x.index[-1] - x.index[0]).days / 365
        return (x.iloc[-1] / x.iloc[0]) ** (1 / yrs) - 1 if x.iloc[-1] > 0 else -1.0
    tu, ho = c[c.index < HOLDOUT], c[c.index >= HOLDOUT]
    me = c.resample("ME").last()
    mo = (me / me.shift(1)).dropna() - 1
    return dict(tune=cg(tu), hold=cg(ho), fall=float((1 - c / c.cummax()).max()), wm=float(mo.min()))


def run(cfg, levs=(1.0,)):
    """{(off, seed, lev): stats} and per-phase trade stats."""
    res, tr = {}, {}
    for off in PHASES:
        T = gen(off, cfg)
        tr[off] = (len(T), T.net[T.t_in < HOLDOUT].mean(), T.net[T.t_in >= HOLDOUT].mean())
        for lev in levs:
            for sd in SEEDS:
                tk = allocate(T, sd, lev, prio=cfg["prio"] is not None)
                res[(off, sd, lev)] = stats(curve(T, tk, off, lev))
    return res, tr


def variants():
    V = {}
    for n, k in ((20, 1.5), (30, 1.0), (30, 2.0), (50, 1.5), (20, 2.0)):
        V[f"P bb({n},{k})"] = dict(n=n, k=k, mean_n=n)
    V["X trail 3 ATR"] = dict(exit="trail", trail=3)
    V["X trail 5 ATR"] = dict(exit="trail", trail=5)
    V["X trail 8 ATR"] = dict(exit="trail", trail=8)
    V["X mean or trail 5"] = dict(exit="mean_or_trail", trail=5)
    V["X under 10-day mean"] = dict(mean_n=10)
    V["X under 20-day mean"] = dict(mean_n=20)
    V["X + 2xATR stop"] = dict(stop=2.0)
    V["X + time stop 10d/+5%"] = dict(tstop=(10, 0.05))
    V["X + breakeven after +10%"] = dict(be=0.10)
    V["X + BTC exit (BTC < 20d)"] = dict(btc_exit=True)
    V["U add every +10%, 3 units"] = dict(pyr=(0.10, 3))
    V["U add every +20%, 3 units"] = dict(pyr=(0.20, 3))
    f = {
        "breadth20 >= 50%": lambda F, P, i: F["br"][i] >= 0.5,
        "breadth20 <= 50%": lambda F, P, i: F["br"][i] <= 0.5,
        "momentum top half": lambda F, P, i: F["rk"][i] >= 0.5,
        "above 200d EMA": lambda F, P, i: P["c"][i] > F["ema200"][i],
        "volume >= 1.5x": lambda F, P, i: F["vr"][i] >= 1.5,
        "volume >= 2x": lambda F, P, i: F["vr"][i] >= 2.0,
        "Fear&Greed < 75": lambda F, P, i: not (F["fg"][i] >= 75),
        "Fear&Greed > 50": lambda F, P, i: F["fg"][i] > 50,
        "BTC 28d > 0": lambda F, P, i: F["btc_r28"][i] > 0,
        "BTC > its 50d mean": lambda F, P, i: F["btc_c"][i] > F["btc_m50"][i],
        "RSI(14) < 80": lambda F, P, i: P["r"][i] < 80,
        "new 50-day high": lambda F, P, i: P["c"][i] > F["hi50p"][i],
        "not overextended": lambda F, P, i: F["ext"][i] < 1.0,
    }
    for nm, fn in f.items():
        V[f"F {nm}"] = dict(filt=fn)
    q = {
        "momentum rank": lambda F, P, i: F["rk"][i],
        "volume ratio": lambda F, P, i: F["vr"][i],
        "calmest": lambda F, P, i: -F["atrp"][i],
        "strongest break": lambda F, P, i: F["ext"][i],
    }
    for nm, fn in q.items():
        V[f"Q priority: {nm}"] = dict(prio=fn)
    return V


def main(only=None):
    lines = [f"backtest/daily_combos.py, {pd.Timestamp.now():%Y-%m-%d %H:%M}; daily book, PIT top-40, 8 slots, marked to "
             f"market; 3 day boundaries x 10 orders", ""]
    # self-check: the generator reproduces pair_lab.daily_trades (cap exits 1 day later, by design)
    ref = pl.daily_trades(off_h=0).sort_values(["coin", "t_in"]).reset_index(drop=True)
    me = gen(0, BASE).sort_values(["coin", "t_in"]).reset_index(drop=True)
    assert len(ref) == len(me) and np.allclose(ref.net, me.net) and (ref.coin == me.coin).all(), "generator != daily_trades"
    shift = (me.t_out - ref.t_out).dt.days
    assert ((shift == 1) == (ref.why == "cap")).all() and (shift[ref.why == "mean"] == 0).all()
    base, btr = run(BASE, LEVS)
    line = {off: sorted((np.mean([base[(off, s, lv)]["fall"] for s in SEEDS]),
                         np.mean([base[(off, s, lv)]["tune"] for s in SEEDS]),
                         np.mean([base[(off, s, lv)]["hold"] for s in SEEDS])) for lv in LEVS) for off in PHASES}

    def agg(r, off, key, lev=1.0):
        return np.mean([r[(off, s, lev)][key] for s in SEEDS])

    lines.append("THE BASE and its leverage line (per day boundary: fall / tune CAGR / holdout CAGR, mean of 10 orders)")
    for off in PHASES:
        lines.append(f"  {off:02d} UTC: " + "; ".join(f"x{lv}: {f * 100:.0f}% / {a * 100:+.0f}% / {b * 100:+.0f}%"
                                                    for lv, (f, a, b) in zip(LEVS, line[off])))
    lines.append("")
    hdr = (f"  {'variant':32} {'trades':>6} {'per trade tune/hold':>20} | {'CAGR tune':>9} {'hold':>6} {'fall':>5} "
           f"{'worst mo':>8} | vs the line at the same fall: tune / hold, by boundary -> verdict")
    lines.append(hdr)
    V = variants()
    if only:
        V = {k: v for k, v in V.items() if k in only}
    rows = {}

    def line_at(off, fall, key):
        f = [a for a, _, _ in line[off]]
        y = [b if key == "tune" else c for _, b, c in line[off]]
        return float(np.interp(fall, f, y))

    for nm, ch in [("BASE (bb 30/1.5, mean exit)", {})] + list(V.items()):
        cfg = dict(BASE, **ch)
        r, tr = (base, btr) if not ch else run(cfg)
        cells, ok = [], True
        for off in PHASES:
            fa = agg(r, off, "fall")
            dt = agg(r, off, "tune") - line_at(off, fa, "tune")
            dh = agg(r, off, "hold") - line_at(off, fa, "hold")
            ok = ok and dt > 0 and dh > 0
            cells.append(f"{dt * 100:+.0f}/{dh * 100:+.0f}")
        ntr = np.mean([tr[o][0] for o in PHASES])
        pt, ph = np.mean([tr[o][1] for o in PHASES]), np.mean([tr[o][2] for o in PHASES])
        verdict = "-" if not ch else ("PASS" if ok else "fail")
        rows[nm] = dict(ok=ok, tune=np.mean([agg(r, o, "tune") for o in PHASES]), hold=np.mean([agg(r, o, "hold") for o in PHASES]))
        lines.append(f"  {nm:32} {ntr:6.0f} {pt * 100:+9.2f}% / {ph * 100:+5.2f}% | {rows[nm]['tune'] * 100:+8.0f}% "
                     f"{rows[nm]['hold'] * 100:+5.0f}% {np.mean([agg(r, o, 'fall') for o in PHASES]) * 100:4.0f}% "
                     f"{np.mean([agg(r, o, 'wm') for o in PHASES]) * 100:+7.1f}% | {'  '.join(cells):24} -> {verdict}")
        print(lines[-1], flush=True)
    txt = "\n".join(lines)
    LOG.write_text(txt + "\n")
    pickle.dump(rows, open(CACHE / "rows.pkl", "wb"))
    print("\n" + txt)


if __name__ == "__main__":
    main()
