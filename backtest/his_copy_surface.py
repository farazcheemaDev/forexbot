"""s107 - THE DELAYED-COPY PAYOFF SURFACE: a copy of his side with a HARD STOP and a wider target (2026-11-22)

THE USER (2026-11-22): s56 showed his moves keep running past +7 (84% at +-15 vs 68% for a driftless walk) and s34 / s47 / s74 showed that
copies 5-30 s late still win +7. He trades with NO stop; before the 2026-12-31 research cut-off the exact economics of a copy that a small
account can actually carry - a hard stop, a +7 .. +15 target, a 30-minute time stop - are needed.

DATA (on disk, nothing bought or downloaded): Exness USTECm ticks with the real spread (strategy_analysis/data/ustec_tick_days.pkl,
  2026-01-02 .. 09-14, 09:30-19:30 New York; strategy_analysis/data/fresh/ustec_tick_days_fresh.pkl, 2026-09-15 .. 11-20, same hours).
  Trades: his 46 statement NASDAQ entries (his_tape.entries, corrected clock) + the 4 October entries (logs/his_new_trades.csv) = 50; those with
  ticks: 42 + 4 = 46. Not covered: 4 statement entries outside 09:30-19:30 New York and the 3 pre-market entries of 2026-11-12 (04:38-05:00;
  s74 scored those three from MT5 at the time: a copy 0-30 s late won +7 on all three).
THE COPY  his side, entered d = 5 / 10 / 15 / 30 s after his click AT THE QUOTE (buy at the ask, sell at the bid), marked on the side it would
  exit at. Target: a limit at +T points (fills at exactly +T). Stop: a market order when the mark touches -S (fills at that tick's mark, so
  gaps through the stop cost what they cost). Time stop: the mark at 30 minutes. His own exit: +7, no stop, closed at 30 minutes.
  MAE = the deepest open loss before the target is hit (or over the 30 minutes if it never is).
CONTROL  the same rules from the same-sitting moments (whole minutes +-1..20 from each click, his side, none within 60 s of a click), entered
  at the same delay - what the bracket gives with no information.
MONEY  R = result / S. At 1% of equity risked per trade and his observed ~5.1 NASDAQ trades a month (53 trades 2026-01-02 .. 11-12): monthly
  return = (1 + 1% x mean R)^5.1 - 1, and the deepest fall of the equity path in time order. Half-Kelly: half the fraction f that maximises
  mean log(1 + f R) - on his sample, and with stop-outs added until the loss rate equals the Wilson 95% upper bound of his observed one
  (a sample with almost no losers makes the raw Kelly meaningless).

REGISTERED BEFORE THE FIRST RUN (2026-11-22)
  C1  His own exit copied (+7, no stop): 5 / 10 s win >= 95% at +5.5..+7.0 points a trade; 30 s wins >= 90% at +4..+7.                 (75%)
  C2  MAE before +7 (5 s copy): median 2-6, 90th 12-25, worst 30-50 points.                                                             (70%)
  C3  MAE before +15 (5 s copy): median 4-12, 90th 20-45, worst 40-90 points, or +15 not reached in 30 min on >= 10% of trades.          (60%)
  C4  Hard stops: at 5-10 s at least one cell with a target >= +10 earns >= +3 points a trade with its 90% interval above 0, and the same
      cell from the controls earns <= 0.                                                                                                 (65%)
  C5  The best cell with a stop >= 15 earns +0.5% .. +3% a month at 1% risk and his trade rate; half-Kelly on his raw sample is >= 10% of
      equity per trade (a number that only says the sample has almost no losers).                                                          (65%)
  C6  30 s copies earn at least 1 point a trade less than 5 s copies on the +12 / +15 targets (averaged over the stops).                    (60%)

RESULT (2026-11-22, logs/his_copy_surface.txt, logs/his_copy_surface_grid.csv) - A COPY WITH A HARD STOP IS POSITIVE ON PAPER AT
  5-15 s; HIS OWN NO-STOP EXIT DOES NOT SURVIVE A 15-30 s DELAY. C2-C6 right; C1 WRONG (the 15 / 30 s no-stop copies).
  46 trades with Exness ticks (42 statement + 4 October). His exit copied (+7, no stop): 5 s 98% / +6.60 points, 10 s 100% / +7.00, 15 s 96% /
  +3.70, 30 s 93% / +1.58 - the trades a late copy misses can run 123-127 points against it (2026-06-05 11:04 buy: the 5-10 s copies hit +7 in
  10-14 s, the 15-30 s copies sat through a ~125-point fall; 2026-02-20 10:01:48 buy: the 30 s copy -94.9).
  MAE before +7 (5 s copy): median 4.4, 90th 18.3, worst 40.5 points; before +15: median 5.7, 90th 31.6, worst 212.1, +15 not reached in 15%.
  Hard stops: every cell at 5-10 s is positive, e.g. stop 20 / +12 at 5 s +7.04 points (90% +4.11..+9.84; controls +0.49), stop 25 / +12
  +8.74, stop 30 / +15 +9.21; at 15 s +2.5..+7.4; at 30 s +1.8..+4.3 with most intervals touching 0.
  At 1% risk and his 5.1 NASDAQ trades a month: +0.8..+2.7% a month at 5-15 s (best with a stop >= 15: stop 15 / +15 at 10 s, +2.4%, deepest
  fall 4.3%), +0.4..+1.7% at 30 s. Half-Kelly 6-45% raw (15-45% at 5-10 s) and 0-22% with the loss rate raised to its Wilson bound: it only says the sample has
  very few losers. The controls (same-sitting moments, his side) make 0..+2 points with wide stops - the drift of his sittings, not
  information. 80 cells on 46 trades: the best cell is picked after looking; none of it exists without his clicks in real time.

    python -m backtest.his_copy_surface
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
DATA = ROOT / "strategy_analysis" / "data"
LOG = ROOT / "logs" / "his_copy_surface.txt"
DELAYS = (5, 10, 15, 30)
STOPS = (10, 15, 20, 25, 30)
TARGETS = (7, 10, 12, 15)
W = 1800
RISK = 0.01
SPAN_MONTHS = (pd.Timestamp("2026-11-12") - pd.Timestamp("2026-01-02")).days / 30.44
RATE = 53 / SPAN_MONTHS                       # his NASDAQ trades a month over the whole record


def trades() -> pd.DataFrame:
    import backtest.his_tape as TP
    x = TP.entries()
    pts = np.where(x.side.str.upper() == "BUY", x.close_price - x.open_price, x.open_price - x.close_price)
    a = pd.DataFrame({"d": x.d.to_numpy(), "t": x.t.to_numpy(), "s": x.s.to_numpy(), "banked": pts, "src": "statement",
                      "utc": x.utc.to_numpy()})
    n = pd.read_csv(ROOT / "logs" / "his_new_trades.csv")
    rows = []
    for r in n.itertuples():
        et = pd.Timestamp(f"{r.date} {r.ny_time}")
        rows.append(dict(d=et.normalize(), t=(et - et.normalize() - pd.Timedelta(hours=9, minutes=30)).total_seconds(),
                         s=1 if r.side == "BUY" else -1, banked=float(r.banked), src="new",
                         utc=pd.Timestamp(f"{r.date} {r.open}") - pd.Timedelta(hours=5)))
    return pd.concat([a, pd.DataFrame(rows)], ignore_index=True).sort_values("utc", kind="stable").reset_index(drop=True)


def path(ts, mid, spr, t, s):
    """Marks (points, his way, net of the spread) of a copy entered at t at the quote, over the next 30 minutes: (times, marks)."""
    i = np.searchsorted(ts, t, side="right") - 1
    if i < 0 or i >= len(ts) - 1:
        return None
    e = mid[i] + s * spr[i] / 2
    j1 = min(np.searchsorted(ts, t + W, side="right"), len(ts))
    if j1 <= i + 1:
        return None
    p = s * ((mid[i + 1:j1] - s * spr[i + 1:j1] / 2) - e)
    return ts[i + 1:j1] - t, p


def bracket(p, stop, target):
    """(result points, 'T' target / 'S' stop / 'X' time) for a limit at +target, a market stop at -stop (None = no stop)."""
    up = np.flatnonzero(p >= target)
    dn = np.flatnonzero(p <= -stop) if stop is not None else np.array([], int)
    ku = up[0] if len(up) else None
    kd = dn[0] if len(dn) else None
    if ku is not None and (kd is None or ku < kd):
        return float(target), "T"
    if kd is not None:
        return float(p[kd]), "S"
    return float(p[-1]), "X"


def mae_before(p, target):
    up = np.flatnonzero(p >= target)
    k = up[0] if len(up) else len(p) - 1
    return max(0.0, -float(p[:k + 1].min())), bool(len(up))


def kelly(R):
    R = np.asarray(R, float)
    if not len(R) or R.min() >= 0:
        return np.inf
    fmax = 0.999 / -R.min()
    f = np.linspace(0, fmax, 4001)[1:]
    g = np.log1p(f[:, None] * R[None, :]).mean(1)
    return float(f[np.argmax(g)])


def wilson_ub(k, n, z=1.96):
    if n == 0:
        return 1.0
    ph = k / n
    den = 1 + z * z / n
    return float((ph + z * z / (2 * n) + z * np.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n))) / den)


def money(R):
    """Monthly return at RISK per trade, the deepest fall of the equity path in time order, half-Kelly raw and pessimistic."""
    R = np.asarray(R, float)
    mR = R.mean()
    month = (1 + RISK * mR) ** RATE - 1
    eq = np.cumprod(1 + RISK * R)
    dd = float((1 - eq / np.maximum.accumulate(np.concatenate([[1.0], eq]))[1:]).max())
    kraw = kelly(R)
    n_loss = int((R < 0).sum())
    ub = wilson_ub(n_loss, len(R))
    worst_loss = R[R < 0].min() if n_loss else -1.0
    m = 0
    while (n_loss + m) / (len(R) + m) < ub and m < 10 * len(R):
        m += 1
    kp = kelly(np.concatenate([R, np.full(m, worst_loss)]))
    return month, dd, kraw / 2, kp / 2, ub


def boot_ci(v, rng, n=2000):
    v = np.asarray(v, float)
    bs = [v[rng.integers(0, len(v), len(v))].mean() for _ in range(n)]
    return np.percentile(bs, [5, 95])


def summarise(tt, p) -> dict:
    """Everything the report needs from one 30-minute path, so no path is kept in memory."""
    out = {"x7": bracket(p, None, 7)[0]}
    up7 = np.flatnonzero(p >= 7)
    out["hold7"] = float(tt[up7[0]]) if len(up7) else float(W)
    for T in TARGETS:
        out[f"mae{T}"], out[f"hit{T}"] = mae_before(p, T)
    for S in STOPS:
        for T in TARGETS:
            out[f"r{S}_{T}"], out[f"k{S}_{T}"] = bracket(p, S, T)
    return out


def main():
    rng = np.random.default_rng(107)
    x = trades()
    old = pickle.loads((DATA / "ustec_tick_days.pkl").read_bytes())
    fresh = pickle.loads((DATA / "fresh" / "ustec_tick_days_fresh.pkl").read_bytes())
    cache = {k: v for k, v in fresh.items() if v is not None}
    cache.update({k: v for k, v in old.items() if v is not None})
    del old, fresh
    his, ctl, covered = [], [], []
    for r in x.itertuples():
        v = cache.get(r.d)
        if v is None or not (0 <= r.t <= 36000 - W - 60):
            continue
        ts, mid, spr = v
        if path(ts, mid, spr, r.t, r.s) is None:
            continue
        covered.append(r.Index)
        others = x[x.d == r.d].t.to_numpy()
        for d in DELAYS:
            P = path(ts, mid, spr, r.t + d, r.s)
            if P is not None:
                his.append(dict(i=r.Index, d=d, **summarise(*P)))
        for m in list(range(-20, 0)) + list(range(1, 21)):
            t0 = r.t + 60 * m
            if t0 < 60 or t0 > 36000 - W - 60 or np.min(np.abs(others - t0)) < 60:
                continue
            for d in DELAYS:
                P = path(ts, mid, spr, t0 + d, r.s)
                if P is not None:
                    ctl.append(dict(i=r.Index, d=d, **summarise(*P)))
    Hh, Cc = pd.DataFrame(his), pd.DataFrame(ctl)
    xc = x.loc[covered]
    L = [f"backtest/his_copy_surface.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC (s107); his trades with Exness ticks {len(xc)} of {len(x)} "
         f"(statement {int((xc.src == 'statement').sum())}, October {int((xc.src == 'new').sum())}); same-sitting control moments "
         f"{int((Cc.d == 5).sum())}; his rate {RATE:.1f} NASDAQ trades a month; risk {RISK:.0%} of equity per trade", "",
         f"HIS OWN RECORD on these {len(xc)} trades: banked {xc.banked.mean():+.2f} points a trade (median {xc.banked.median():+.2f}, worst "
         f"{xc.banked.min():+.2f}), {int((xc.banked > 0).sum())} of {len(xc)} green", ""]
    L.append("1. HIS OWN EXIT COPIED (+7 limit, NO stop, 30-min close), at the Exness quote")
    L.append(f"  {'delay':>6}{'trades':>8}{'won +7':>9}{'pts/trade':>11}{'90% interval':>16}{'worst':>9}{'median hold':>13} | {'controls: won':>14}{'pts/trade':>11}")
    C1 = {}
    for d in DELAYS:
        h, c = Hh[Hh.d == d], Cc[Cc.d == d]
        res = h.x7.to_numpy()
        lo, hi = boot_ci(res, rng)
        C1[d] = (np.mean(res >= 7), res.mean())
        L.append(f"  {d:>5}s{len(res):>8}{np.mean(res >= 7):>9.0%}{res.mean():>+11.2f}{lo:>+9.2f}..{hi:+.2f}{res.min():>+9.1f}{h.hold7.median():>11.0f} s | "
                 f"{np.mean(c.x7 >= 7):>13.0%}{c.x7.mean():>+11.2f}")
    L += ["", "2. HOW FAR A COPY GOES AGAINST YOU BEFORE THE TARGET (no stop; points; 'not hit' = never reached in 30 min, MAE over the 30 min)"]
    L.append(f"  {'delay':>6}{'target':>7}{'median':>8}{'75th':>7}{'90th':>7}{'95th':>7}{'worst':>7}{'not hit':>9} | {'controls 90th':>14}{'95th':>7}{'99th':>7}{'worst':>7}{'not hit':>9}")
    MAE = {}
    for d in DELAYS:
        h, c = Hh[Hh.d == d], Cc[Cc.d == d]
        for T in TARGETS:
            mm, hit = h[f"mae{T}"].to_numpy(float), h[f"hit{T}"].to_numpy(bool)
            cm, chit = c[f"mae{T}"].to_numpy(float), c[f"hit{T}"].to_numpy(bool)
            q = np.percentile(mm, [50, 75, 90, 95])
            MAE[(d, T)] = (q[0], q[2], mm.max(), 1 - hit.mean())
            L.append(f"  {d:>5}s{T:>+7}{q[0]:>8.1f}{q[1]:>7.1f}{q[2]:>7.1f}{q[3]:>7.1f}{mm.max():>7.1f}{1 - hit.mean():>9.0%} | "
                     f"{np.percentile(cm, 90):>14.1f}{np.percentile(cm, 95):>7.1f}{np.percentile(cm, 99):>7.1f}{cm.max():>7.1f}{1 - chit.mean():>9.0%}")
    L += ["", "3. THE HARD-STOP GRID (30-min time stop). win = target hit; stop = stopped; pts = points a trade net of the spread (90% interval);",
          "   ctl = the same cell from the same-sitting moments; month = return a month at 1% risk and his rate; fall = deepest fall of that",
          "   equity path in time order; hK = half-Kelly (raw on his sample / with losses raised to the Wilson 95% upper bound)"]
    G = []
    for d in DELAYS:
        h, c = Hh[Hh.d == d], Cc[Cc.d == d]
        L.append(f"  delay {d} s")
        L.append(f"    {'stop':>5}{'tgt':>5}{'win':>6}{'stop':>6}{'time':>6}{'pts':>8}{'90% interval':>16}{'worst':>8}{'ctl pts':>9}{'ctl win':>9}{'mean R':>8}"
                 f"{'month':>8}{'fall':>7}{'hK raw':>8}{'hK pess':>9}")
        for S in STOPS:
            for T in TARGETS:
                res, kind = h[f"r{S}_{T}"].to_numpy(float), h[f"k{S}_{T}"].to_numpy()
                cres, ckind = c[f"r{S}_{T}"].to_numpy(float), c[f"k{S}_{T}"].to_numpy()
                lo, hi = boot_ci(res, rng, 1000)
                R = res / S
                month, dd, hk, hkp, ub = money(R)
                g = dict(d=d, S=S, T=T, win=np.mean(kind == "T"), stop=np.mean(kind == "S"), time=np.mean(kind == "X"), pts=res.mean(),
                         lo=lo, hi=hi, worst=res.min(), ctl=cres.mean(), ctl_win=np.mean(ckind == "T"), mR=R.mean(), month=month, dd=dd,
                         hk=hk, hkp=hkp)
                G.append(g)
                hks = "  inf" if not np.isfinite(hk) else f"{hk:>5.0%}"
                L.append(f"    {S:>5}{T:>+5}{g['win']:>6.0%}{g['stop']:>6.0%}{g['time']:>6.0%}{g['pts']:>+8.2f}{lo:>+8.2f}..{hi:+.2f}{g['worst']:>+8.1f}"
                         f"{g['ctl']:>+9.2f}{g['ctl_win']:>9.0%}{g['mR']:>+8.3f}{month:>+8.1%}{dd:>7.1%}{hks:>8}{hkp:>9.0%}")
    G = pd.DataFrame(G)
    L += ["", "4. THE COMPARISON - his own +7 / no-stop exit vs the best hard-stopped cells"]
    for d in (5, 10, 30):
        b = G[(G.d == d) & (G["T"] >= 10)].sort_values("pts", ascending=False).iloc[0]
        b15 = G[(G.d == d) & (G.S >= 15)].sort_values("month", ascending=False).iloc[0]
        L.append(f"  {d:>2} s: his exit +7/no stop {C1[d][1]:+.2f} pts ({C1[d][0]:.0%} won) | best target >= +10: stop {int(b.S)} / +{int(b['T'])} "
                 f"{b.pts:+.2f} pts ({b.lo:+.2f}..{b.hi:+.2f}), ctl {b.ctl:+.2f} | best month with stop >= 15: stop {int(b15.S)} / +{int(b15['T'])} "
                 f"{b15.month:+.1%} a month, fall {b15.dd:.1%}")
    c1 = C1[5][0] >= 0.95 and C1[10][0] >= 0.95 and 5.5 <= C1[5][1] <= 7.0 and 5.5 <= C1[10][1] <= 7.0 and C1[30][0] >= 0.90 and 4 <= C1[30][1] <= 7
    m7, m15 = MAE[(5, 7)], MAE[(5, 15)]
    c2 = 2 <= m7[0] <= 6 and 12 <= m7[1] <= 25 and 30 <= m7[2] <= 50
    c3 = (4 <= m15[0] <= 12 and 20 <= m15[1] <= 45 and 40 <= m15[2] <= 90) or m15[3] >= 0.10
    early = G[G.d.isin([5, 10]) & (G["T"] >= 10)]
    ok4 = early[(early.pts >= 3) & (early.lo > 0) & (early.ctl <= 0)].sort_values("pts")
    c4 = len(ok4) > 0
    s15 = G[G.S >= 15].sort_values("month", ascending=False).iloc[0]
    raw_hk = s15.hk
    c5 = 0.005 <= s15.month <= 0.03 and (not np.isfinite(raw_hk) or raw_hk >= 0.10)
    w5 = G[(G.d == 5) & G["T"].isin([12, 15])].pts.mean()
    w30 = G[(G.d == 30) & G["T"].isin([12, 15])].pts.mean()
    c6 = w5 - w30 >= 1.0
    best4 = f"(best stop {int(ok4.iloc[-1].S)} / +{int(ok4.iloc[-1]['T'])} at {int(ok4.iloc[-1].d)} s) " if c4 else ""
    hk_txt = "unbounded" if not np.isfinite(raw_hk) else format(raw_hk, ".0%")
    L += ["", "PREDICTIONS",
          f"  C1 his exit copied: 5 s {C1[5][0]:.0%} / {C1[5][1]:+.2f}, 10 s {C1[10][0]:.0%} / {C1[10][1]:+.2f}, 30 s {C1[30][0]:.0%} / {C1[30][1]:+.2f} -> "
          f"{'RIGHT' if c1 else 'WRONG'}",
          f"  C2 MAE before +7 (5 s): median {m7[0]:.1f}, 90th {m7[1]:.1f}, worst {m7[2]:.1f} -> {'RIGHT' if c2 else 'WRONG'}",
          f"  C3 MAE before +15 (5 s): median {m15[0]:.1f}, 90th {m15[1]:.1f}, worst {m15[2]:.1f}, not hit {m15[3]:.0%} -> {'RIGHT' if c3 else 'WRONG'}",
          f"  C4 a 5-10 s cell with target >= +10, >= +3 pts, interval above 0, controls <= 0: {len(ok4)} cells {best4}-> {'RIGHT' if c4 else 'WRONG'}",
          f"  C5 best cell with stop >= 15: {s15.month:+.1%} a month (stop {int(s15.S)} / +{int(s15['T'])} at {int(s15.d)} s), raw half-Kelly {hk_txt} -> "
          f"{'RIGHT' if c5 else 'WRONG'}",
          f"  C6 5 s minus 30 s on +12 / +15 targets: {w5 - w30:+.2f} pts -> {'RIGHT' if c6 else 'WRONG'}"]
    txt = "\n".join(L)
    LOG.write_text(txt + "\n", encoding="utf-8")
    G.to_csv(ROOT / "logs" / "his_copy_surface_grid.csv", index=False)
    print(txt)


if __name__ == "__main__":
    sys.exit(main())
