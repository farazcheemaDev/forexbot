"""THREE FIXES FOR THE HALVING, TESTED AGAINST THE ONE CONTROL THAT MATTERS.

why_drawdown.py (doc 13 section 10) found why the triple book still falls to half. Every big
fall came right after a boom (equity x2.4-x7.9 in 120 days), and the loss has three parts:
    hundreds of failed 1h alt breakouts;
    stacked 5-7 unit positions giving back (units 6-7 lose on 47-49% of positions);
    hedges too small to matter.
The user asked for all three fixes, tested properly, with no edge ignored.

THE CONTROL. Any rule that trades less has a smaller drawdown. So every fix is compared
with the SAME book at a lower uniform bet size, chosen to give the same drawdown: the baseline
run at 0.4, 0.5, ..., 1.0 x its risk traces a return-vs-drawdown frontier. A fix is real only if
it earns MORE than that frontier at its own drawdown, on BOTH halves. equity_filter.py died
exactly this way ("a slower way of betting less").

BASELINE: the triple (tight + time stop + 7 units) with the bot's 10x gross guard, entry-sized
realised equity, 12 slots, 1000h gate, 10 orderings - triple_capped.simulate, generalised so a
unit can close before its position (fix 3b) and an entry can be resized or refused.

THE FIXES
  1  SMALLER AFTER A BOOM
     1a  boom(L,G,m): while equity / equity L days ago >= G, new positions x m
         (L 60/120, G 1.5/2/3, m 0.5/0.25).
     1b  anchor(k): size from min(equity, its k-day average), k 30/90/180 - a boom is not
         bet at once.
     1c  dd(d,m): x m while equity is more than d below its peak. Doc 02 killed this family
         once; it is here so the kill is re-measured on this book.
  2  PAUSE AFTER FAILURES
     2a  streak(scope,N,f,act): the bot shadows its own signals; if >= f of the last N signals
         in scope that have CLOSED lost money, the next entry in scope is skipped or halved.
         scope 1h-longs / all-longs, N 10/20/40, f 0.8/0.9.
     2b  chop(scope,m): 1h longs or all longs x m (0 = skip) on days btc_regime calls CHOP.
  3  GET OUT OF STACKED ADDS SOONER
     3a  hi(T,m): once a long's best gain reaches T R, its trail x m (T 6/8/10, m 0.5/0.25),
         via graveyard_rescore.walk's own hi_thresh. Five of these died in doc 02 on the old
         engine and a 5-unit book.
     3b  unitstop(X): every ADDED unit gets its own stop X R below its own entry
         (X 2/4/6). A stopped unit closes alone; the rest of the position runs unchanged.
         Pessimistic: if the add bar's own low reaches the unit stop, the unit is stopped.
     3c  lev(L): the gross guard at 6x / 8x instead of 10x, which limits stacking book-wide.

REGISTERED PREDICTIONS (2026-09-24, before running)
  1a  lowers drawdown, costs return, fails the frontier on at least one half.
  1b  the same.
  1c  fails the frontier (as in doc 02).
  2a  mostly skips entries in the chop that PRECEDES trends, so it fails the frontier.
  2b  costs the bull starts, fails.
  3a  fails: the 10-exit-rule identification problem.
  3b  X = 2 cuts the giveback but also the adds that became runners; fails. X = 6 is ~neutral.
  3c  is just the frontier by another name, ~on it.
  At most one config beats the frontier on both halves, and if one does, it gets the
  four-bar-phase check before anything is claimed.

    python -m backtest.dd_fixes
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import blend  # noqa: E402
from backtest.bull_boost import regimes  # noqa: E402
from backtest.causal_t0 import real_t0  # noqa: E402
from backtest.compounding import summarize  # noqa: E402
from backtest.engine_variants import break_map, shorts_for  # noqa: E402
from backtest.expectations import haircut, month_ends, windows  # noqa: E402
from backtest.funding_cost import charged, long_funding, short_funding  # noqa: E402
from backtest.graveyard_rescore import walk  # noqa: E402
from backtest.market_neutral import btc_regime, load_panel  # noqa: E402
from backtest.mtm_sizing import attach_prices  # noqa: E402
from backtest.timeframes import resample  # noqa: E402

FEE = blend.FEE_BP / 1e4
SEEDS = tuple(range(10))
CUT = pd.Timestamp("2024-08-29").value
CAP = 221.0
DAY = 86_400_000_000_000


# ------------------------------------------------------------------ rows

def build(**walk_kw):
    """triple_capped.build(max_units=7) with walk overrides, keeping coin / rule / R and giving
    every unit its own close time (uc, = the position's t1 unless a fix moves it)."""
    raw = []
    for rule in ("1h", "4h", "12h"):
        raw += shorts_for(rule)
        for coin in blend.BOOK:
            d = blend.load(coin)
            if d is None:
                continue
            df = resample(d, rule)
            if len(df) < 300:
                continue
            raw += walk(df, rule, coin, tb=break_map(df, rule), time_stop=(100, 2.0), max_units=7, **walk_kw)
    return decompose(charged(real_t0(short_funding(long_funding(attach_prices(raw))))))


def decompose(rows):
    """Charged engine rows -> per-unit rows for sim()."""
    out = []
    for r in rows:
        risk, t1 = r["risk"], pd.Timestamp(r["t1"]).value
        units, fund = r["units"], r.get("fund", 0.0)
        if r["side"] == "long":
            n = len(units); se = sum(e for e, _ in units)
            x = (r["R"] - fund + (1 + FEE) * se / risk) * risk / n
            rk = [(x - e) / risk - FEE * e / risk for e, _ in units]
        else:
            x = None
            rk = [r["R"] - fund]
        hold = np.array([max(t1 - tk, 1) for _, tk in units], float)
        fk = fund * hold / hold.sum()
        out.append(dict(t0=pd.Timestamp(r["t0"]).value, t1=t1, side=r["side"],
                        uR=np.array(rk) + fk, fk=fk, ut=[tk for _, tk in units],
                        ue=[e for e, _ in units], uc=[t1] * len(units), risk=risk, x=x,
                        coin=r["coin"], rule=r["rule"], R=float(r["R"])))
    out.sort(key=lambda z: z["t0"])
    return out


def unit_stops(rows, X):
    """3b: each ADDED long unit closes alone at X R below its own entry, if the price gets
    there before the position's own exit. Bars are the engine's own (resample of the rule)."""
    frames = {}
    out = []
    for r in rows:
        if r["side"] != "long" or len(r["ue"]) < 2:
            out.append(r); continue
        key = (r["coin"], r["rule"])
        if key not in frames:
            df = resample(blend.load(r["coin"]), r["rule"])
            frames[key] = (pd.DatetimeIndex(df["time"]).as_unit("ns").asi8,
                           df["open"].to_numpy(float), df["low"].to_numpy(float))
        tt, op, lo = frames[key]
        uR, uc = r["uR"].copy(), list(r["uc"])
        for k in range(1, len(r["ue"])):
            e, stop = r["ue"][k], r["ue"][k] - X * r["risk"]
            ta = r["ut"][k] - 3_600_000_000_000          # the add bar's label (attach_prices +1h)
            a = np.searchsorted(tt, ta, side="left")
            b = np.searchsorted(tt, r["t1"], side="right")
            hit = np.flatnonzero(lo[a:b] <= stop)
            if not len(hit):
                continue
            i = a + hit[0]
            fill = stop if i == a else min(stop, op[i])
            if r["x"] is not None and fill <= r["x"] and tt[i] >= r["t1"]:
                continue                   # same bar as the position's exit: the trail fills
            old_hold = max(r["t1"] - r["ut"][k], 1)
            new_hold = max(tt[i] - r["ut"][k], 1)
            uR[k] = (fill - e) / r["risk"] - FEE * e / r["risk"] + r["fk"][k] * new_hold / old_hold
            uc[k] = int(tt[i])
        out.append(dict(r, uR=uR, uc=uc))
    return out


# ------------------------------------------------------------------ simulator

class Ctx:
    """What a sizing or gating rule may read at time t: realised equity history so far."""
    def __init__(self):
        self.ht = [0]; self.he = [1.0]; self.peak = 1.0

    def eq_at(self, t):
        i = np.searchsorted(self.ht, t, side="right") - 1
        return self.he[max(i, 0)]

    def mean_over(self, t, days):
        grid = t - np.arange(days)[::-1] * DAY
        idx = np.searchsorted(self.ht, grid, side="right") - 1
        return float(np.mean(np.asarray(self.he)[np.maximum(idx, 0)]))


def sim(rows, bear_ns, bear_v, seed, lev=10.0, t_from=None, t_to=None, g=1.0,
        size_fn=None, gate_fn=None):
    rng = np.random.default_rng(seed)
    tie = rng.random(len(rows))
    o = [rows[i] for i in sorted(range(len(rows)), key=lambda i: (rows[i]["t0"], tie[i]))]
    if t_from is not None:
        o = [r for r in o if r["t0"] >= t_from]
    if t_to is not None:
        o = [r for r in o if r["t0"] < t_to]
    ev = []
    for j, r in enumerate(o):
        ev.append((r["t0"], 1, j, 0))
        for k in range(1, len(r["ut"])):
            ev.append((max(r["ut"][k], r["t0"]), 1, j, k))
        for k in range(len(r["ut"])):
            if r["uc"][k] < r["t1"]:                      # a unit closing before its position
                ev.append((r["uc"][k], 0 if r["uc"][k] > max(r["ut"][k], r["t0"]) else 3, j, k))
        ev.append((r["t1"], 0 if r["t1"] > r["t0"] else 3, j, -1))
    ev.sort(key=lambda e: (e[0], e[1]))
    ctx = Ctx()
    state, open_n, eq = {}, 0, 1.0
    pts = []
    for t, kind, j, k in ev:
        r = o[j]
        if kind in (0, 3):
            s = state.get(j)
            if s is None:
                continue
            if k >= 0:                                     # one unit closes early
                if k in s["open"]:
                    s["open"].discard(k)
                    eq = max(eq + s["dpr"] * r["uR"][k], 0.0)
                    ctx.ht.append(t); ctx.he.append(eq); ctx.peak = max(ctx.peak, eq); pts.append((t, eq))
                continue
            state.pop(j)
            open_n -= 1
            if s["open"]:
                eq = max(eq + s["dpr"] * sum(r["uR"][kk] for kk in s["open"]), 0.0)
                ctx.ht.append(t); ctx.he.append(eq); ctx.peak = max(ctx.peak, eq); pts.append((t, eq))
            continue
        if k == 0:
            if open_n >= 12:
                continue
            m = gate_fn(r, t, ctx) if gate_fn else 1.0
            if m <= 0:
                continue
            ib = bear_v[max(np.searchsorted(bear_ns, t, side="right") - 1, 0)]
            f = blend.RISK / 100.0 * (blend.REGIME_MULT if ib else 1.0) * g * m
            base = size_fn(t, eq, ctx) if size_fn else eq
            s = dict(dpr=f * base, open=set())
        else:
            s = state.get(j)
            if s is None:
                continue
        notional = s["dpr"] * r["ue"][k] / r["risk"]
        gross = sum(st["dpr"] * o[jj]["ue"][kk] / o[jj]["risk"] for jj, st in state.items() for kk in st["open"])
        if gross + notional > lev * eq:
            continue
        s["open"].add(k)
        if k == 0:
            state[j] = s; open_n += 1
    c = pd.Series([p[1] for p in pts], index=pd.to_datetime([p[0] for p in pts]))
    return c.resample("D").last().ffill()


# ------------------------------------------------------------------ fixes

def boom(L, G, m):
    return lambda t, eq, ctx: eq * (m if eq / max(ctx.eq_at(t - L * DAY), 1e-12) >= G else 1.0)


def anchor(k):
    return lambda t, eq, ctx: min(eq, ctx.mean_over(t, k))


def ddcut(d, m):
    return lambda t, eq, ctx: eq * (m if eq < ctx.peak * (1 - d) else 1.0)


def streak_gate(rows, scope, N, f, act):
    sel = [r for r in rows if r["side"] == "long" and (scope == "all" or r["rule"] == "1h")]
    sel.sort(key=lambda r: r["t1"])
    t1s = np.array([r["t1"] for r in sel]); lost = np.array([r["R"] < 0 for r in sel], float)
    cum = np.r_[0.0, np.cumsum(lost)]

    def gate(r, t, ctx):
        if r["side"] != "long" or (scope == "1h" and r["rule"] != "1h"):
            return 1.0
        i = np.searchsorted(t1s, t, side="left")        # signals CLOSED before this entry
        if i < N:
            return 1.0
        return (0.0 if act == "skip" else 0.5) if (cum[i] - cum[i - N]) / N >= f else 1.0
    return gate


def chop_gate(reg_ns, reg_v, scope, m):
    def gate(r, t, ctx):
        if r["side"] != "long" or (scope == "1h" and r["rule"] != "1h"):
            return 1.0
        i = np.searchsorted(reg_ns, t, side="right") - 1
        return m if i >= 0 and reg_v[i] == "chop" else 1.0
    return gate


# ------------------------------------------------------------------ scoring

def score(rows, bear_ns, bear_v, **kw):
    """per seed: tune %/mo (haircut), holdout %/mo, drawdown per half and full (raw), worst
    month (raw, full), 12-month multiples (full)."""
    out = []
    for sd in SEEDS:
        tu = sim(rows, bear_ns, bear_v, sd, t_to=CUT, **kw)
        ho = sim(rows, bear_ns, bear_v, sd, t_from=CUT, **kw)
        fu = sim(rows, bear_ns, bear_v, sd, **kw)
        dd = lambda c: float((1 - c / c.cummax()).max() * 100)  # noqa: E731
        me = month_ends(fu)
        out.append(dict(tune=summarize(tu)[0], hold=summarize(ho)[0], dd_t=dd(tu), dd_h=dd(ho),
                        dd_f=dd(fu), worst=float(me.pct_change().min() * 100),
                        w12=windows(me, 12), w12h=windows(month_ends(ho), 12)))
    return out


def frontier(base_by_g, half):
    """return at drawdown d on the uniform-bet-size line, by interpolation over g."""
    pts = sorted((np.mean([s["dd_" + half[0]] for s in v]), np.mean([s[half] for s in v]))
                 for v in base_by_g.values())
    xs, ys = np.array([p[0] for p in pts]), np.array([p[1] for p in pts])
    return lambda d: float(np.interp(d, xs, ys, left=np.nan, right=np.nan))


def main():
    bear = regimes()[1000]
    bear_ns = pd.DatetimeIndex(bear.index).as_unit("ns").asi8
    bear_v = bear.to_numpy(bool)
    C, _F, _first = load_panel()
    C.index = C.index.astype("datetime64[ns]")
    reg = btc_regime(C).dropna()
    reg_ns = pd.DatetimeIndex(reg.index).as_unit("ns").asi8
    reg_v = reg.to_numpy()

    base = build()
    B = {}
    for g in (0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0):
        B[g] = score(base, bear_ns, bear_v, g=g)
    fr_t, fr_h = frontier(B, "tune"), frontier(B, "hold")
    ref = B[1.0]

    print("TRIPLE + 10x guard, entry-sized, 10 orderings. %/mo = haircut; drawdown and worst month RAW.")
    print("EXCESS = the fix's %/mo minus what the SAME book earns at a uniform smaller bet with the SAME")
    print("drawdown (the frontier). Paired = fix minus baseline on the same ordering, mean +- se (wins/10).\n")
    print("  FRONTIER (baseline at a uniform bet size g):")
    for g, v in B.items():
        print(f"    g {g:.1f}: tune {np.mean([s['tune'] for s in v]):+6.2f}%/mo DD {np.mean([s['dd_t'] for s in v]):4.1f}%"
              f" | holdout {np.mean([s['hold'] for s in v]):+6.2f}%/mo DD {np.mean([s['dd_h'] for s in v]):4.1f}%"
              f" | full DD {np.mean([s['dd_f'] for s in v]):4.1f}%")

    hdr = (f"\n  {'fix':<30}{'TUNE':>7}{'DD':>5}{'EXCESS':>8}{'HOLD':>8}{'DD':>5}{'EXCESS':>8}"
           f"{'full DD':>8}{'worst mo':>9}{'yr<$221':>8}{'typ yr':>8}   paired tune / hold")
    configs = []
    for L in (60, 120):
        for G in (1.5, 2.0, 3.0):
            for m in (0.5, 0.25):
                configs.append((f"1a boom L{L} G{G:g} x{m:g}", dict(size_fn=boom(L, G, m)), None))
    for k in (30, 90, 180):
        configs.append((f"1b anchor {k}d", dict(size_fn=anchor(k)), None))
    for d in (0.2, 0.3):
        configs.append((f"1c dd>{d*100:.0f}% x0.5", dict(size_fn=ddcut(d, 0.5)), None))
    for scope in ("1h", "all"):
        for N in (10, 20, 40):
            for f in (0.8, 0.9):
                for act in ("skip", "half"):
                    configs.append((f"2a streak {scope} N{N} {f:g} {act}",
                                    dict(gate_fn=streak_gate(base, scope, N, f, act)), None))
    for scope in ("1h", "all"):
        for m in (0.0, 0.5):
            configs.append((f"2b chop {scope} x{m:g}", dict(gate_fn=chop_gate(reg_ns, reg_v, scope, m)), None))
    for T in (6, 8, 10):
        for m in (0.5, 0.25):
            configs.append((f"3a hi T{T} x{m:g}", {}, dict(hi_thresh=T, hi_mult=m)))
    for X in (2, 4, 6):
        configs.append((f"3b unitstop {X}R", {}, ("unitstop", X)))
    for lv in (6.0, 8.0):
        configs.append((f"3c guard {lv:g}x", dict(lev=lv), None))

    rows_cache = {}
    results = {}
    group = None
    for name, kw, rows_spec in configs:
        if name[:2] != group:
            group = name[:2]
            print(hdr)
        if rows_spec is None:
            rows = base
        elif isinstance(rows_spec, tuple):
            rows = rows_cache.setdefault(rows_spec, unit_stops(base, rows_spec[1]))
        else:
            key = tuple(sorted(rows_spec.items()))
            rows = rows_cache.setdefault(key, build(**rows_spec))
        S = score(rows, bear_ns, bear_v, **kw)
        results[name] = S
        mt, mh = np.mean([s["tune"] for s in S]), np.mean([s["hold"] for s in S])
        dt, dh = np.mean([s["dd_t"] for s in S]), np.mean([s["dd_h"] for s in S])
        et, eh = mt - fr_t(dt), mh - fr_h(dh)
        pt = np.array([a["tune"] - b["tune"] for a, b in zip(S, ref)])
        ph = np.array([a["hold"] - b["hold"] for a, b in zip(S, ref)])
        w = np.concatenate([s["w12"] for s in S])
        typ = CAP * np.median([haircut(x, 12) for x in w])
        flag = "  <== beats the frontier on BOTH halves" if et > 0 and eh > 0 else ""
        print(f"  {name:<30}{mt:>+6.2f}%{dt:>4.0f}%{et:>+7.2f}{mh:>+7.2f}%{dh:>4.0f}%{eh:>+7.2f}"
              f"{np.mean([s['dd_f'] for s in S]):>7.0f}%{np.mean([s['worst'] for s in S]):>+8.1f}%"
              f"{(w < 1).mean()*100:>7.0f}%{typ:>7.0f}$   {pt.mean():+.2f}+-{pt.std(ddof=1)/np.sqrt(10):.2f} ({(pt > 0).sum()}) / "
              f"{ph.mean():+.2f}+-{ph.std(ddof=1)/np.sqrt(10):.2f} ({(ph > 0).sum()}){flag}")
    w = np.concatenate([s["w12"] for s in ref])
    print(f"\n  baseline (g 1.0): full DD {np.mean([s['dd_f'] for s in ref]):.0f}%, worst month "
          f"{np.mean([s['worst'] for s in ref]):+.1f}%, years < $221 {(w < 1).mean()*100:.0f}%, "
          f"typical year ${CAP*np.median([haircut(x, 12) for x in w]):.0f}")
    pd.to_pickle({k: [{kk: vv for kk, vv in s.items() if not kk.startswith('w12')} for s in v]
                  for k, v in results.items()}, Path(__file__).resolve().parents[1] / "logs" / "dd_fixes.pkl")


if __name__ == "__main__":
    main()
