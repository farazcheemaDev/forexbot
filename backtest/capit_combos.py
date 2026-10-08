"""THE CAPITULATION BOOK x EVERYTHING THAT WORKED - every combination not yet run (2026-10-08, same goal as
daily_combos.py).

The book (capitulation_exits.py, tp5_nw): a 4h RSI(14) cross under 20 with quote volume > 2x its 20-bar average, once
>= 5 distinct coins of the point-in-time top-40 have signalled within 24 hours (itself included); in at the next 4h
open; +5% (intrabar, pessimistic: exactly +5%), or out at the next open once a close at or after 24 bars is not above
the entry; 42-bar cap. 12bp + funding. Tested so far: RSI 20/25/30, 1h/4h, top-40/100, K 3/5/8, W 6/24h, targets
2/3/5/10%, ATR trails, fixed holds, slots 3/5/8, leverage 1-5x, as a machine sleeve. NEVER combined with the market
context that worked elsewhere, with a limit entry (the crash bids' mechanism), with a priority rule, or with a stop.

    F  filters at the signal: BTC regime (bear only / not bull / bull only - BTC 50-day trend, a day lagged), BTC under
       / over its 1000h mean, the coin above its 4h EMA200 (a dip in an uptrend), the coin's 30-day return > 0,
       daily breadth20 <= 10% / <= 30% (the bear sleeve's signal), Fear & Greed <= 25 / <= 40, RSI < 15, volume >= 3x,
       the coin down >= 10% over 24h, BTC down >= 5% over 24h, K >= 8, K >= 10
    E  entries: a limit 2% / 4% under the signal close, live for the next bar only; a limit 3% under live for 6 bars;
       wait for a green bar (in at the open after the next bar closes above its open)
    S  stops (to make leverage survivable - the book's dips inside a trade reach 29-53%): -10% / -15% / -25% intrabar
    Q  slot priority within a burst (19 signals on one day happened): deepest RSI, biggest volume, biggest 24h drop,
       best 30-day momentum

METHOD: 4 bar phases (+0/60/120/180 min) x 10 random same-bar orders; one book on the whole account, 8 slots of an
eighth, P&L booked at the close (trades last ~1.4 days; v2_addons.py found marking moves this book's worst month by 0).
PASS: beats the base's own leverage line (0.5 / 1 / 1.5 / 2 / 3x) at the same biggest fall, on the tune half AND the
holdout, in ALL 4 phases. A filter that just trades less cannot pass by being smaller.

REGISTERED BEFORE RUNNING (2026-10-08):
    F  the book already lives in crashes, so market filters mostly cut trades without raising the average: bear-only,
       F&G and breadth20 tie or fail; the coin's own uptrend (EMA200, momentum) raises the average (+0.5..+1 point a
       trade) but cuts trades by half and fails the line; RSI < 15 / volume >= 3x fail (capitulation_freq: the first,
       deepest signals keep falling). At most 2 of 17 pass.
    E  limit entries raise the average a trade but miss the fastest bounces; one of the three passes at most. The
       green-bar wait fails (it gives up the first bar's bounce).
    S  stops cut the average (the dips recover - 85-93% of trades win); at the same fall they fail the line, except
       perhaps -25% at 2-3x.
    Q  priority changes little (bursts rarely fill 8 slots): all tie.

RESULT (2026-10-08, logs/capit_combos.txt): 4 of 28 pass in all 4 phases on both halves - BTC down >= 5% in 24h,
    the coin down >= 10% in 24h, a limit 2% under (next bar), a limit 4% under. Market filters (regime, 1000h, breadth20,
    F&G), the coin's own uptrend, RSI < 15, volume >= 3x, K >= 8/10 fail; stops ruin it (-10% stop: holdout -3.5%);
    the green-bar wait fails; priorities tie. Predictions: F at most 2 pass - right in count, wrong in which (I
    expected none of the drop filters); E at most one passes - WRONG (two); S fail - right; Q tie - right.

    python -m backtest.capit_combos
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest import daily_combos as dc  # noqa: E402
from backtest import pair_lab as pl  # noqa: E402
from backtest.capitulation_wide import four_hour, funding_cum  # noqa: E402
from backtest.rsi_factors import prep  # noqa: E402
from backtest.sentiment import fng  # noqa: E402

CACHE = dc.CACHE
LOG = ROOT / "logs" / "capit_combos.txt"
HOLDOUT = pl.HOLDOUT
FEE = 0.0012
PHASES = (0, 60, 120, 180)
SEEDS = tuple(range(10))
SLOTS = 8
LEVS = (0.5, 1.0, 1.5, 2.0, 3.0)
H4 = np.timedelta64(4, "h")
BASE = dict(filt=None, entry=("open",), stop=None, prio=None, K=5)


def panel4(off):
    f = CACHE / f"panel4_{off}.pkl"
    if f.exists():
        return pickle.loads(f.read_bytes())
    el = pl.universe()
    out = {}
    for s, h in pl.hourly_all().items():
        d = four_hour(h, off)
        if len(d) < 300:
            continue
        P = prep(d, np.full(len(d), np.nan))
        P["t"] = d.time.to_numpy("datetime64[ns]")
        P["fc"] = funding_cum(s, d.time.to_numpy(), h)
        P["ym"] = d.time.dt.strftime("%Y-%m").to_numpy()
        P["el"] = el[s]
        out[s] = P
    f.write_bytes(pickle.dumps(out))
    return out


def daily_breadth():
    """breadth20 over the PIT top-40 on 00:00 UTC daily bars, indexed by the bar's CLOSE time (when it is known)."""
    PN = dc.panel(0)
    C = pd.DataFrame({s: pd.Series(P["c"], index=P["t"]) for s, P in PN.items()}).sort_index()
    ym = C.index.strftime("%Y-%m")
    elig = pd.DataFrame({s: ym.isin(list(PN[s]["el"])) for s in C.columns}, index=C.index) & C.notna()
    above = (C > C.rolling(20).mean()) & elig
    b = above.sum(axis=1) / elig.sum(axis=1).replace(0, np.nan)
    b.index = b.index + pd.Timedelta(days=1)
    return b


_S: dict = {}


def signals(off, vmin=2.0):
    """Every raw signal with its breadth count and context, known at the signal bar's CLOSE."""
    if (off, vmin) in _S:
        return _S[(off, vmin)]
    PN = panel4(off)
    rows = []
    for s, P in PN.items():
        r, v = P["r"], P["v"]
        vavg = pd.Series(v).rolling(20).mean().shift(1).to_numpy()
        sig = np.r_[False, (r[:-1] >= 20) & (r[1:] < 20)] & (v > vmin * vavg)
        sig[:250] = False
        for i in np.flatnonzero(sig):
            if i + 3 < len(r) and P["ym"][i] in P["el"]:
                c = P["c"]
                rows.append((P["t"][i], s, i, r[i], v[i] / vavg[i], c[i] / c[i - 6] - 1, c[i] / c[i - 180] - 1,
                             c[i] > P["ema200"][i]))
    S = pd.DataFrame(rows, columns=["t", "coin", "i", "rsi", "vr", "drop24", "mom30", "up200"])
    S = S.sort_values("t", kind="stable").reset_index(drop=True)
    tt = S.t.to_numpy("datetime64[ns]").astype(np.int64)
    day, lo, br = 24 * 3600 * 10 ** 9, 0, []
    for k in range(len(S)):
        while tt[lo] < tt[k] - day:
            lo += 1
        hi = np.searchsorted(tt, tt[k], side="right")
        br.append(S.coin.iloc[lo:hi].nunique())
    S["K"] = br
    known = pd.DatetimeIndex(S.t) + pd.Timedelta(hours=4)
    reg = pl.btc_regime_daily()
    S["regime"] = reg.reindex(known.floor("D"), method="ffill").to_numpy()
    g = pl.btc_gate_daily(1000)
    S["above1000"] = g.reindex(known.floor("D"), method="ffill").to_numpy().astype(bool)
    S["breadth"] = daily_breadth().reindex(known, method="ffill").to_numpy()
    S["fg"] = fng().reindex(known.floor("D"), method="ffill").to_numpy()
    b = PN["BTCUSDT"]
    bt = pd.Series(b["c"], index=b["t"])
    S["btc24"] = (bt / bt.shift(6) - 1).reindex(pd.DatetimeIndex(S.t)).to_numpy()
    _S[(off, vmin)] = S
    return S


def exit_tp(i, ib, e, P, fc, stop=None, tp=0.05, nw=24, cap=42, limit_fill=False):
    """In at price e during bar ib. Target +tp intrabar (not in a limit's own fill bar - the order inside it is
    unknown), stop intrabar (checked first), not-working after nw bars from the signal: out at the next open. Returns
    (next-signal bar, net, worst, exit-time bar index, exit-time offset in bars past that index's open)."""
    o, h, l, c = P["o"], P["h"], P["l"], P["c"]
    n = len(c)
    j_end = min(i + 1 + cap, n - 2)
    worst = 0.0
    for j in range(ib, j_end + 1):
        worst = max(worst, 1 - l[j] / e)
        if stop is not None and l[j] <= e * (1 - stop):
            x = min(o[j], e * (1 - stop)) if j > ib else e * (1 - stop)
            return j, x / e - 1 - FEE - (fc[j] - fc[ib]) / e, worst, j, 1
        if not (limit_fill and j == ib) and h[j] >= e * (1 + tp):
            return j, tp - FEE - (fc[j] - fc[ib]) / e, worst, j, 1
        if j - i >= nw and c[j] <= e:
            return j + 1, o[j + 1] / e - 1 - FEE - (fc[j + 1] - fc[ib]) / e, worst, j + 1, 0
    return j_end, c[j_end] / e - 1 - FEE - (fc[j_end] - fc[ib]) / e, worst, j_end, 1


def gen(off, cfg):
    PN, S = panel4(off), signals(off, cfg.get("vmin", 2.0))
    S = S[S.K >= cfg["K"]]
    if cfg["filt"] is not None:
        S = S[cfg["filt"](S).astype(bool)]
    rows = []
    for s, g in S.groupby("coin"):
        P = PN[s]
        o, l, c, t = P["o"], P["l"], P["c"], P["t"]
        free = 0
        for row in g.itertuples():
            i = row.i
            if i < free:
                continue
            kind = cfg["entry"][0]
            if kind == "open":
                ib, e, lf = i + 1, o[i + 1], False
            elif kind == "limit":
                lim, bars_live = c[i] * (1 - cfg["entry"][1]), cfg["entry"][2]
                thr = lim * (1 - (cfg["entry"][3] if len(cfg["entry"]) > 3 else 0.0))   # trade-through needed to fill
                ib = next((j for j in range(i + 1, min(i + 1 + bars_live, len(c) - 3)) if l[j] <= thr), None)
                if ib is None:
                    free = i + 1 + bars_live
                    continue
                e, lf = min(o[ib], lim), o[ib] > lim
            else:                                                          # green: next bar closes above its open
                if not c[i + 1] > o[i + 1]:
                    free = i + 2
                    continue
                ib, e, lf = i + 2, o[i + 2], False
            j, net, worst, jx, after = exit_tp(i, ib, e, P, fc=P["fc"], stop=cfg["stop"], limit_fill=lf,
                                               tp=cfg.get("tp", 0.05), nw=cfg.get("nw", 24))
            t_out = t[min(jx, len(t) - 1)] + (H4 if after else np.timedelta64(0, "h"))
            sc = cfg["prio"](row) if cfg["prio"] is not None else 0.0
            rows.append((s, t[ib], t_out, net, worst, sc))
            free = j + 1
    return pd.DataFrame(rows, columns=["coin", "t_in", "t_out", "net", "worst", "score"])


def curve(T, taken):
    q = np.array([a for a, _, _ in taken], dtype=int)
    pnl = np.array([c for _, _, c in taken], dtype=float)
    tout = T.t_out.to_numpy("datetime64[ns]")[q]
    days = pd.date_range(pd.Timestamp("2020-03-01"), pd.Timestamp("2026-09-15"))     # one span for every variant
    E = (days + pd.Timedelta(days=1)).to_numpy("datetime64[ns]")
    o = np.argsort(tout, kind="stable")
    cum = np.concatenate([[0.0], np.cumsum(pnl[o])])
    return pd.Series(1 + cum[np.searchsorted(tout[o], E, side="left")], index=days)


def run(cfg, levs=(1.0,)):
    res, tr = {}, {}
    for off in PHASES:
        T = gen(off, cfg)
        tr[off] = (len(T), T.net[T.t_in < HOLDOUT].mean(), T.net[T.t_in >= HOLDOUT].mean())
        for lev in levs:
            for sd in SEEDS:
                tk = dc.allocate(T.assign(units=None), sd, lev, prio=cfg["prio"] is not None)
                res[(off, sd, lev)] = dc.stats(curve(T, tk))
    return res, tr


def variants():
    V = {
        "F BTC regime bear only": dict(filt=lambda S: S.regime == "bear"),
        "F BTC regime not bull": dict(filt=lambda S: S.regime != "bull"),
        "F BTC regime bull only": dict(filt=lambda S: S.regime == "bull"),
        "F BTC under 1000h mean": dict(filt=lambda S: ~S.above1000),
        "F BTC over 1000h mean": dict(filt=lambda S: S.above1000),
        "F coin above 4h EMA200": dict(filt=lambda S: S.up200),
        "F coin 30-day return > 0": dict(filt=lambda S: S.mom30 > 0),
        "F breadth20 <= 10%": dict(filt=lambda S: S.breadth <= 0.10),
        "F breadth20 <= 30%": dict(filt=lambda S: S.breadth <= 0.30),
        "F Fear&Greed <= 25": dict(filt=lambda S: S.fg <= 25),
        "F Fear&Greed <= 40": dict(filt=lambda S: S.fg <= 40),
        "F RSI < 15": dict(filt=lambda S: S.rsi < 15),
        "F volume >= 3x": dict(filt=lambda S: S.vr >= 3),
        "F coin down >= 10% in 24h": dict(filt=lambda S: S.drop24 <= -0.10),
        "F BTC down >= 5% in 24h": dict(filt=lambda S: S.btc24 <= -0.05),
        "F K >= 8": dict(K=8),
        "F K >= 10": dict(K=10),
        "E limit -2%, next bar": dict(entry=("limit", 0.02, 1)),
        "E limit -4%, next bar": dict(entry=("limit", 0.04, 1)),
        "E limit -3%, 6 bars": dict(entry=("limit", 0.03, 6)),
        "E wait for a green bar": dict(entry=("green",)),
        "S stop -10%": dict(stop=0.10),
        "S stop -15%": dict(stop=0.15),
        "S stop -25%": dict(stop=0.25),
        "Q priority: deepest RSI": dict(prio=lambda r: -r.rsi),
        "Q priority: biggest volume": dict(prio=lambda r: r.vr),
        "Q priority: biggest 24h drop": dict(prio=lambda r: -r.drop24),
        "Q priority: best 30-day momentum": dict(prio=lambda r: r.mom30),
    }
    return V


def main():
    lines = [f"backtest/capit_combos.py, {pd.Timestamp.now():%Y-%m-%d %H:%M}; capitulation book (tp5_nw), PIT top-40, 8 "
             f"slots of an eighth; 4 bar phases x 10 orders", ""]
    ref = pd.read_csv(ROOT / "logs" / "capitulation_exits_trades.csv", parse_dates=["t_in", "t_out"])
    ref = ref[(ref.exit == "tp5_nw") & (ref.off == 0)].sort_values(["coin", "t_in"]).reset_index(drop=True)
    me = gen(0, BASE).sort_values(["coin", "t_in"]).reset_index(drop=True)
    print(f"self-check: {len(me)} trades vs {len(ref)}; net equal {np.allclose(me.net, ref.net) if len(me) == len(ref) else 'n/a'}",
          flush=True)
    assert len(me) == len(ref) and np.allclose(me.net, ref.net, atol=1e-9), "generator != capitulation_exits"
    base, btr = run(BASE, LEVS)

    def agg(r, off, key, lev=1.0):
        return np.mean([r[(off, s, lev)][key] for s in SEEDS])

    line = {off: sorted((agg(base, off, "fall", lv), agg(base, off, "tune", lv), agg(base, off, "hold", lv)) for lv in LEVS)
            for off in PHASES}
    lines.append("THE BASE and its leverage line (per phase: fall / tune CAGR / holdout CAGR, mean of 10 orders)")
    for off in PHASES:
        lines.append(f"  +{off:3d}m: " + "; ".join(f"x{lv}: {f * 100:.0f}% / {a * 100:+.1f}% / {b * 100:+.1f}%"
                                                 for lv, (f, a, b) in zip(LEVS, line[off])))
    lines.append("")
    lines.append(f"  {'variant':34} {'trades':>6} {'per trade tune/hold':>20} | {'CAGR tune':>9} {'hold':>6} {'fall':>5} "
                 f"{'worst mo':>8} | vs the line at the same fall: tune / hold by phase -> verdict")

    def line_at(off, fall, key):
        f = [a for a, _, _ in line[off]]
        y = [b if key == "tune" else c for _, b, c in line[off]]
        return float(np.interp(fall, f, y))

    for nm, ch in [("BASE (tp5_nw, K>=5)", {})] + list(variants().items()):
        cfg = dict(BASE, **ch)
        r, tr = (base, btr) if not ch else run(cfg)
        cells, ok = [], True
        for off in PHASES:
            fa = agg(r, off, "fall")
            dt = agg(r, off, "tune") - line_at(off, fa, "tune")
            dh = agg(r, off, "hold") - line_at(off, fa, "hold")
            ok = ok and dt > 0 and dh > 0
            cells.append(f"{dt * 100:+.1f}/{dh * 100:+.1f}")
        ntr = np.mean([tr[o][0] for o in PHASES])
        pt, ph = np.nanmean([tr[o][1] for o in PHASES]), np.nanmean([tr[o][2] for o in PHASES])
        verdict = "-" if not ch else ("PASS" if ok else "fail")
        lines.append(f"  {nm:34} {ntr:6.0f} {pt * 100:+9.2f}% / {ph * 100:+5.2f}% | "
                     f"{np.mean([agg(r, o, 'tune') for o in PHASES]) * 100:+8.1f}% "
                     f"{np.mean([agg(r, o, 'hold') for o in PHASES]) * 100:+5.1f}% "
                     f"{np.mean([agg(r, o, 'fall') for o in PHASES]) * 100:4.0f}% "
                     f"{np.mean([agg(r, o, 'wm') for o in PHASES]) * 100:+7.1f}% | {'  '.join(cells)} -> {verdict}")
        print(lines[-1], flush=True)
    txt = "\n".join(lines)
    LOG.write_text(txt + "\n")
    print("\n" + txt)


if __name__ == "__main__":
    main()
