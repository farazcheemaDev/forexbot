"""BUY STRONG 4h MOMENTUM (RSI CROSSES ABOVE 80), FROZEN, ON DATA IT HAS NEVER SEEN - and what it does to a $20 account (2026-11-08)

THE USER (2026-11-08): "I want an edge that has no capital restraints - liquidity sweep, indicators, whatever, I don't care". Read as: an edge measured in
percent that a small account can trade with one position at a time (Bitget's $5 minimum is the only floor). The strongest untested lead of that kind in the repo
is the one rsi_ratio.py found and set aside (2026-11-02, 1 of 448 cells, Holm 1.00): on 4h bars, when RSI(14) crosses UP through 80, go LONG (the momentum
side, not the textbook short), stop 4 x ATR(14) = 1R, target 4R, out at the close of bar 24 (4 days), one position per coin, 12bp + 1bp / 8h funding in R.
On the point-in-time top-40 perps it read +0.227R / +0.292R a trade (775 / 313 trades) with an excess over random entries of +0.19R on both halves, and its
neighbours (RSI above 75, stops of 2-4 ATR) lean the same way: the repo's recurring finding that strong crypto moves CONTINUE (market_fade.py, the trend book).

THE TEST. The cell is run with rsi_ratio.py's OWN code (process(), rsi14, rsi_flags, warm_mask, candle_manage.simulate / cost_r / pick_trades), unchanged, on:
  NEW-PERP   USDT perps 2020-2026, coins ranked 41-100 by the prior month's volume (sweep_zone_more.samples; stock tokens and stables dropped as rsi_ratio does)
  NEW-SPOT   USDT spot 2017-08 .. 2019-12 (89 pairs, no funding file: funding as rsi_ratio charges it, 1bp / 8h on longs, kept - a little pessimistic on spot)
  NEW        both = the confirm sample. OLD (the top-40 it was found on) is re-run first and must reproduce rsi_ratio.py's logged line exactly.
  The control is rsi_ratio's: the same bracket entered from EVERY coin-bar of the same universe at the same entry day x 4h slot.
  The day counter (candle_scan.D0) is moved from 2019-01-01 to 2017-01-01 so the spot years fit; the tune / holdout split date (2024-08-29) is unchanged.
PASS (one pre-registered cell, so no multiple-test correction), on NEW: at least 100 trades on 30 days, day-vote mean R > 0 with t >= 2, excess over the control
  > 0 with t >= 2, the per-trade mean R > 0, and the per-trade mean > 0 in BOTH halves of NEW by entry day. MDE80 = (2.0 + 0.84) x the day-vote standard error,
  printed beside it. A pass = a candidate for a forward paper record, never a deployment.
THE SMALL ACCOUNT (descriptive, not part of the verdict): every signal in time order, ONE position at a time (a signal while a trade is open is skipped; ties at
  the same entry bar in 5 random orders, the median reported), the whole account at 1x (and 2x) on each trade; $20 needs $5 a position, so the account is stuck
  if it falls under $5.

REGISTERED BEFORE THE FIRST RUN (2026-11-08)
  R1  OLD reproduces rsi_ratio.py's logged lead line exactly (n 775 / 313; per-trade +0.227 / +0.292R).                                         95%
  R2  On NEW the per-trade mean R is positive (45%); the whole bar passes (20%).
  R3  NEW-SPOT alone (2017 bull, 2018 bear, 2019) is positive per trade.                                                                         40%
  R4  The neighbour cells (RSI 75 / 80 x stop 2 / 4 ATR x target 2 / 4R) are positive per trade on NEW in at least 5 of 8.                       40%
  R5  The $20 one-position account at 1x on every top-100 perp signal 2020-26 ends above $20 (55%), with a deepest fall over 50% (70%).

RESULT (2026-11-08, logs/rsi80_more.txt, logs/rsi80_more_costs.txt; trades in logs/rsi80_more_trades.pkl)
  OLD REPRODUCED exactly (n 775 / 313, day-vote +0.221 / +0.192R, per-trade +0.227 / +0.292R), and lead_trades == rsi_ratio.process on all three universes.
  NEW-PERP (561 coins, 1,292 trades): per-trade +0.126R, day-vote +0.070R (t 1.53), excess +0.074R (t 1.83), both halves positive per trade (+0.11 / +0.14).
  NEW-SPOT (80 pairs, 182 trades): per-trade +0.229R, day-vote +0.119R (t 1.04), excess +0.166R (t 2.02).
  NEW (the confirm sample, 1,474 trades): per-trade +0.138R, day-vote +0.076R (t 1.80), excess +0.086R (t 2.34), halves +0.138 / +0.139R per trade, MDE80 +0.12R.
  VERDICT: NO PASS - the day-vote t is 1.80 against the registered 2.0. The direction replicated on two independent unseen samples, smaller than where it was
    found (+0.14R against +0.23..+0.29R); all 8 neighbours positive per trade on NEW (+0.006 .. +0.138R; excess t 1.3-2.4).
  WHERE THE MONEY IS (post hoc): NEW-PERP is positive in 6 of 7 years (2022 -0.07R) but its best 20 of 666 entry days carry it (+173R of +162R; without them
    -0.008R a trade, median trade -0.17R); NEW-SPOT the same (best 20 days +79R of +42R). A convex alt-momentum burst rule - the trend book's shape.
  COSTS (post hoc, --costs): the funding these trades really paid is LOWER than the flat 1bp / 8h charged (NEW-PERP -0.001R a trade against 0.007R), and +30bp of
    extra round-trip slippage costs ~0.02R a trade. Not a cost artefact.
  THE SMALL ACCOUNT: all-in one position at a time is ruinous (the 4-ATR stop on a small coin can be 50-70% of the price: worst trade -70% of the account; NEW-PERP
    $20 -> $4.38). Traded as meant (every signal, 1-2% of booked equity at risk, real funding, +10bp slippage): NEW-PERP $100 at 1% -> $277 (+19%/yr, deepest
    fall 26%, up to 3.7x the account open at once), at 2% -> $906 (+45%/yr, fall 48%, 7.3x); NEW-SPOT 2017-19 +19%/yr at 1% (fall 9%). It is NOT capital-free:
    at 1% risk $20 can take 34 of 2,380 signals (positions under $5), $50 about half; from ~$100 nearly all. Including the top-40 it was found on reads +65%/yr -
    in-sample, not a planning number.
  PREDICTIONS: R1 right. R2 right (per-trade positive; no pass). R3 right (+0.229R). R4 right (8 of 8). R5 right but marginal (median $21.81, 5 orders $4 .. $153;
    deepest fall 99%).
  NOT DONE: the overlap with the machine's trend book (likely high - same convex alt bursts) and a forward record.

    python backtest/rsi80_more.py         tests: python tests/test_rsi80_more.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import backtest.candle_manage as cm  # noqa: E402
import backtest.candle_scan as cs  # noqa: E402
import backtest.capitulation_wide as cw  # noqa: E402
import backtest.rsi_ratio as rr  # noqa: E402
import backtest.sweep_zone_more as szm  # noqa: E402
import backtest.wide_book as wb  # noqa: E402
from backtest.market_neutral import drop_non_crypto  # noqa: E402

LOG = ROOT / "logs" / "rsi80_more.txt"
ORIGIN = np.datetime64("2017-01-01", "D")
TFH, FLAG, SIDE, STOP, TGT = 4, "hi80", 1, 4.0, 4.0
BI = rr.BRACKETS.index((STOP, TGT))
LOGGED = dict(tu=dict(n=775, pt=0.227, net=0.221), ho=dict(n=313, pt=0.292, net=0.192))      # rsi_ratio.txt line 412
NEIGH = [(fl, s, g) for fl in ("hi75", "hi80") for s in (2.0, 4.0) for g in (2.0, 4.0)]
MIN_POS = 5.0
START = 20.0


def move_day_origin(origin=ORIGIN):
    """candle_scan counts days from D0 (2019-01-01): move it so 2017-19 fits; the split date and the end date stay where they were."""
    cs.D0 = origin
    cs.CUT_DAY = int((np.datetime64("2024-08-29", "D") - origin) / np.timedelta64(1, "D"))
    cs.ND = int((np.datetime64("2027-01-01", "D") - origin) / np.timedelta64(1, "D"))


def universes() -> dict:
    """{name: {coin: months}} - OLD (top-40 perps, rsi_ratio's own universe), NEW-PERP (ranks 41-100), NEW-SPOT (2017-19)."""
    szm.point_at(szm.PERPS)
    old = drop_non_crypto(wb.eligibility(40))
    old = {s: m for s, m in old.items() if m and s.endswith("USDT")}
    newp = drop_non_crypto(szm.samples("perp"))
    news = drop_non_crypto(szm.samples("spot"))
    szm.point_at(szm.PERPS)
    return {"OLD": old, "NEW-PERP": {s: m for s, m in newp.items() if s.endswith("USDT")}, "NEW-SPOT": {s: m for s, m in news.items() if s.endswith("USDT")}}


def lead_trades(d: pd.DataFrame, em: np.ndarray) -> pd.DataFrame:
    """The lead cell's trades on one coin, built exactly as rsi_ratio.process builds them (same validity, same 0.2% risk floor, same simulate / cost /
    one-position pick) - with the entry and exit times and the risk fraction kept, which process() throws away."""
    cols = ["t_in", "t_out", "net", "rf", "day", "key"]
    n = len(d)
    if n < 200:
        return pd.DataFrame(columns=cols)
    t = d["time"].to_numpy("datetime64[ns]")
    o, h, l, c = (d[k].to_numpy(float) for k in ("o", "h", "l", "c"))
    v = d["v"].to_numpy(float)
    atr = cm.atr14(h, l, c)
    fl = rr.rsi_flags(rr.rsi14(c), v)[FLAG]
    member = np.isin(t.astype("datetime64[M]"), em)
    step = TFH * 3600 * 10 ** 9
    S = cs.n_slots(TFH)
    valid = (cs.valid_mask(t, step, rr.CAP) & rr.warm_mask(t, step, rr.WARM) & member & (o > 0) & (c > 0) & np.isfinite(atr) & (atr > 0))
    E = np.flatnonzero(valid)
    if not len(E):
        return pd.DataFrame(columns=cols)
    valid[E[STOP * atr[E] / o[E + 1] < cm.MIN_RISK]] = False
    E = np.flatnonzero(valid)
    if not len(E):
        return pd.DataFrame(columns=cols)
    rg, kx, rf = cm.simulate(o, h, l, c, atr, E, SIDE, dict(stop=STOP, be=None, trail=None, target=TGT, cap=rr.CAP))
    net = rg - cm.cost_r(kx, rf, SIDE, TFH)
    net_full, rf_full, exit_idx = np.full(n, np.nan), np.full(n, np.nan), np.zeros(n, int)
    net_full[E], rf_full[E], exit_idx[E] = net, rf, E + kx
    idx = np.flatnonzero(fl & valid & np.isfinite(net_full))
    if not len(idx):
        return pd.DataFrame(columns=cols)
    pk = cm.pick_trades(idx, exit_idx.tolist())
    ent = t[pk + 1]
    dy = cs.day_index(ent)
    return pd.DataFrame(dict(t_in=ent, t_out=t[exit_idx[pk]] + np.timedelta64(TFH, "h"), net=net_full[pk], rf=rf_full[pk], day=dy,
                             key=dy * S + cs.slot_of(ent, TFH)))


def run(univ: dict, folder: Path):
    """Every coin through rsi_ratio.process (all cells + the control) and lead_trades. Returns (lead trades, cells, control accumulators)."""
    szm.point_at(folder)
    cells, acc, rows = {}, rr.new_acc(), []
    for s in sorted(univ):
        hh = cw.hourly(s)
        if hh is None:
            continue
        d = rr.to_tf(hh, TFH)
        em = np.array(sorted(univ[s]), dtype="datetime64[M]")
        rr.process(d, em, TFH, cells, acc)
        tr = lead_trades(d, em)
        if len(tr):
            rows.append(tr.assign(coin=s))
    szm.point_at(szm.PERPS)
    T = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
    return T, cells, acc


def same_as_process(T: pd.DataFrame, cells: dict) -> bool:
    """lead_trades reproduces rsi_ratio.process's own trades for the cell (as multisets of day, key, net)."""
    parts = cells.get((TFH, BI, SIDE, FLAG), [])
    if not parts:
        return len(T) == 0
    a = np.c_[np.concatenate([p[0] for p in parts]), np.concatenate([p[1] for p in parts]), np.concatenate([p[2] for p in parts])]
    b = np.c_[T.day.to_numpy(float), T.key.to_numpy(float), T.net.to_numpy(float)]
    if a.shape != b.shape:
        return False
    a, b = a[np.lexsort(a.T[::-1])], b[np.lexsort(b.T[::-1])]
    return bool(np.allclose(a, b))


def baseline(acc: dict, bi=BI, side=SIDE):
    kk = (TFH, bi, side)
    cnt, sm, wn = acc["cnt"][kk], acc["sum"][kk], acc["win"][kk]
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(cnt > 0, sm / np.maximum(cnt, 1), np.nan), np.where(cnt > 0, wn / np.maximum(cnt, 1), np.nan)


def cell_rows(cells: dict, key) -> tuple:
    parts = cells.get(key, [])
    if not parts:
        return np.array([], int), np.array([], int), np.array([])
    return np.concatenate([p[0] for p in parts]), np.concatenate([p[1] for p in parts]), np.concatenate([p[2] for p in parts])


def pooled(*runs) -> tuple:
    """Pool (day, key, net) with each universe's own control: keys are offset per universe so every trade reads its own baseline."""
    S = cs.n_slots(TFH)
    days, keys, nets, bases, bws, off = [], [], [], [], [], 0
    for (d, k, n), (b, w) in runs:
        days.append(d)
        keys.append(k + off)
        nets.append(n)
        bases.append(b)
        bws.append(w)
        off += cs.ND * S
    return np.concatenate(days), np.concatenate(keys), np.concatenate(nets), np.concatenate(bases), np.concatenate(bws)


def verdict(day, key, net, base, bw) -> dict:
    """The registered bar on the confirm sample: the whole of it and its two halves by entry day."""
    allm = np.ones(len(day), bool)
    whole = rr.half(day, net, key, base, bw, allm)
    if whole is None:
        return dict(whole=None, h1=None, h2=None, ok=False, mde=np.nan)
    mid = np.sort(day)[len(day) // 2]
    h1, h2 = rr.half(day, net, key, base, bw, day < mid), rr.half(day, net, key, base, bw, day >= mid)
    se = abs(whole["net"] / whole["t"]) if whole["t"] else np.nan
    ok = bool(cs.sized(whole) and whole["net"] > 0 and whole["t"] >= 2 and whole["exc"] > 0 and whole["t_exc"] >= 2 and whole["pt"] > 0
              and h1 is not None and h2 is not None and h1["pt"] > 0 and h2["pt"] > 0)
    return dict(whole=whole, h1=h1, h2=h2, ok=ok, mde=(2.0 + 0.84) * se)


def account(T: pd.DataFrame, lev: float = 1.0, seed: int = 0, start: float = START) -> dict:
    """One position at a time, the whole account at `lev` x on each trade, in entry order (ties in a random order). Stuck under MIN_POS."""
    rng = np.random.default_rng(seed)
    X = T.assign(tie=rng.random(len(T))).sort_values(["t_in", "tie"], kind="stable")
    eq, peak, dd, free, n, worst = start, start, 0.0, np.datetime64("1970-01-01"), 0, 0.0
    for t_in, t_out, r, rf in zip(X.t_in.to_numpy("datetime64[ns]"), X.t_out.to_numpy("datetime64[ns]"), X.net.to_numpy(float), X.rf.to_numpy(float)):
        if t_in < free or eq < MIN_POS:
            continue
        ret = max(-1.0, lev * r * rf)
        eq *= 1 + ret
        worst = min(worst, ret)
        peak = max(peak, eq)
        dd = max(dd, 1 - eq / peak)
        free, n = t_out, n + 1
    yrs = (X.t_out.max() - X.t_in.min()) / pd.Timedelta(days=365.25) if len(X) else np.nan
    return dict(n=n, end=eq, mult=eq / start, cagr=(eq / start) ** (1 / yrs) - 1 if yrs and eq > 0 else -1.0, dd=dd, worst=worst, stuck=eq < MIN_POS)


def sized_account(T: pd.DataFrame, start: float, risk: float) -> dict:
    """How the rule is meant to be traded (added after the first run, descriptive, not part of the verdict): EVERY signal taken, each position risking `risk`
    of the BOOKED equity at its entry (rule 12: entry-sized, booked at the close, so an open runner never sizes the next trade); notional = risk / the stop
    distance; a position under the venue's $5 is skipped. Exits are booked before entries at the same instant."""
    ev = sorted([(t, 1, k) for k, t in enumerate(T.t_in.to_numpy("datetime64[ns]"))] + [(t, 0, k) for k, t in enumerate(T.t_out.to_numpy("datetime64[ns]"))])
    R, RF = T.net.to_numpy(float), T.rf.to_numpy(float)
    eq, peak, dd, open_, taken, skipped, gross = start, start, 0.0, {}, 0, 0, 0.0
    for _, kind, k in ev:
        if kind == 1:
            r_usd = risk * eq
            if eq <= 0 or r_usd / RF[k] < MIN_POS:
                skipped += 1
                continue
            open_[k] = (r_usd, r_usd / RF[k])
            taken += 1
            gross = max(gross, sum(v[1] for v in open_.values()) / eq)
        elif k in open_:
            eq += open_.pop(k)[0] * R[k]
            peak = max(peak, eq)
            dd = max(dd, 1 - eq / peak)
    yrs = (T.t_out.max() - T.t_in.min()) / pd.Timedelta(days=365.25)
    return dict(taken=taken, skipped=skipped, end=eq, cagr=(eq / start) ** (1 / yrs) - 1 if eq > 0 else -1.0, dd=dd, gross=gross)


def fmt(s) -> str:
    if s is None:
        return "-"
    return (f"n {s['n']:5d} on {s['days']:4d} days  day-vote {s['net']:+.3f}R (t {s['t']:+.2f})  excess {s['exc']:+.3f}R (t {s['t_exc']:+.2f})  "
            f"per-trade {s['pt']:+.3f}R  win {s['win'] * 100:.0f}% (random {s['bw'] * 100:.0f}%)")


def main():
    move_day_origin()
    U = universes()
    L = [f"backtest/rsi80_more.py, {pd.Timestamp.now():%Y-%m-%d %H:%M}; 4h RSI(14) up through 80 -> LONG, stop 4 ATR, target 4R, out at bar 24, 12bp + 1bp/8h, "
         f"rsi_ratio.py's own code; control = the same bracket from every coin-bar at the entry day x slot"]
    R = {}
    for name, folder in (("OLD", szm.PERPS), ("NEW-PERP", szm.PERPS), ("NEW-SPOT", szm.SPOT)):
        T, cells, acc = run(U[name], folder)
        b, w = baseline(acc)
        R[name] = dict(T=T, cells=cells, acc=acc, b=b, w=w, same=same_as_process(T, cells))
        L.append(f"{name}: {len(U[name])} coins, {len(T)} lead trades; lead_trades == rsi_ratio.process: {R[name]['same']}")
    d, k, n = cell_rows(R["OLD"]["cells"], (TFH, BI, SIDE, FLAG))
    tu = rr.half(d, n, k, R["OLD"]["b"], R["OLD"]["w"], d < cs.CUT_DAY)
    ho = rr.half(d, n, k, R["OLD"]["b"], R["OLD"]["w"], d >= cs.CUT_DAY)
    rep = (tu["n"] == LOGGED["tu"]["n"] and ho["n"] == LOGGED["ho"]["n"] and round(tu["pt"], 3) == LOGGED["tu"]["pt"] and round(ho["pt"], 3) == LOGGED["ho"]["pt"]
           and round(tu["net"], 3) == LOGGED["tu"]["net"] and round(ho["net"], 3) == LOGGED["ho"]["net"])
    L.append(f"\nOLD (top-40 perps, where the lead was found) - must reproduce rsi_ratio.txt line 412: {'REPRODUCED' if rep else 'NOT REPRODUCED'}")
    L.append(f"  tune     {fmt(tu)}")
    L.append(f"  holdout  {fmt(ho)}")
    if not rep:
        txt = "\n".join(L)
        LOG.write_text(txt + "\n", encoding="utf-8")
        print(txt)
        raise SystemExit("the frozen code does not reproduce the study: stop")
    for name in ("NEW-PERP", "NEW-SPOT"):
        d, k, n = cell_rows(R[name]["cells"], (TFH, BI, SIDE, FLAG))
        v = verdict(d, k, n, R[name]["b"], R[name]["w"])
        L.append(f"\n{name}: {fmt(v['whole'])}  MDE80 {v['mde']:+.2f}R")
        L.append(f"    first half {fmt(v['h1'])}")
        L.append(f"    second half {fmt(v['h2'])}")
    runs = [(cell_rows(R[nm]["cells"], (TFH, BI, SIDE, FLAG)), (R[nm]["b"], R[nm]["w"])) for nm in ("NEW-PERP", "NEW-SPOT")]
    day, key, net, base, bw = pooled(*runs)
    v = verdict(day, key, net, base, bw)
    L.append(f"\nNEW = both (THE CONFIRM SAMPLE): {fmt(v['whole'])}  MDE80 {v['mde']:+.2f}R")
    L.append(f"    first half {fmt(v['h1'])}")
    L.append(f"    second half {fmt(v['h2'])}")
    L.append(f"VERDICT on NEW: {'PASS' if v['ok'] else 'NO PASS'}")
    L.append("\nNEIGHBOURS on NEW (context, not judged): per-trade mean R, day-vote t, excess")
    for fl, s, g in NEIGH:
        bi = rr.BRACKETS.index((s, g))
        rs = [(cell_rows(R[nm]["cells"], (TFH, bi, SIDE, fl)), baseline(R[nm]["acc"], bi)) for nm in ("NEW-PERP", "NEW-SPOT")]
        x = verdict(*pooled(*rs))
        L.append(f"  4h {fl} long, stop {s} ATR, target {g}R: {fmt(x['whole'])}")
    L.append(f"\nTHE SMALL ACCOUNT: ${START:.0f}, one position at a time, the whole account on each trade (median of 5 tie orders); stuck under ${MIN_POS:.0f}")
    perps = pd.concat([R["OLD"]["T"], R["NEW-PERP"]["T"]], ignore_index=True)
    for nm, T in (("top-100 perps 2020-26 (OLD + NEW-PERP)", perps), ("NEW-PERP only", R["NEW-PERP"]["T"]), ("NEW-SPOT 2017-19", R["NEW-SPOT"]["T"])):
        for lev in (1.0, 2.0):
            A = [account(T, lev, s) for s in range(5)]
            med = sorted(A, key=lambda a: a["end"])[2]
            L.append(f"  {nm:<40} {lev:.0f}x: {med['n']:4d} trades, ${START:.0f} -> ${med['end']:,.2f} ({med['cagr'] * 100:+.0f}%/yr), deepest fall {med['dd'] * 100:.0f}%, "
                     f"worst trade {med['worst'] * 100:+.0f}%{' STUCK' if med['stuck'] else ''}   (5 orders: ${min(a['end'] for a in A):,.0f} .. ${max(a['end'] for a in A):,.0f})")
    pd.concat([R[nm]["T"].assign(src=nm) for nm in R], ignore_index=True).to_pickle(LOG.with_name("rsi80_more_trades.pkl"))
    L += sized_lines(perps, R["NEW-PERP"]["T"])
    txt = "\n".join(L)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


def sized_lines(perps: pd.DataFrame, newp: pd.DataFrame) -> list:
    L = ["\nTHE WAY IT IS MEANT TO BE TRADED (added after the first run, descriptive): every signal, each risking a fixed share of the booked equity, "
         f"positions under ${MIN_POS:.0f} skipped"]
    for nm, T in (("top-100 perps 2020-26", perps), ("NEW-PERP only", newp)):
        for risk in (0.01, 0.02):
            for start in (20.0, 50.0, 100.0, 300.0):
                a = sized_account(T, start, risk)
                L.append(f"  {nm:<22} risk {risk * 100:.0f}%  ${start:>4.0f} -> ${a['end']:>9,.2f} ({a['cagr'] * 100:+4.0f}%/yr)  taken {a['taken']:4d}, "
                         f"skipped under $5 {a['skipped']:4d}, deepest fall {a['dd'] * 100:3.0f}%, most open at once {a['gross']:.1f}x the account")
    return L


def real_funding_r(T: pd.DataFrame) -> np.ndarray:
    """The funding a LONG actually paid on each perp trade, in R (rule 10 - the study charged a flat 1bp / 8h, and this rule buys rallies, when funding runs
    hot): (cumulative funding at the exit - at the entry) / the entry price / the stop distance. capitulation_wide.funding_cum = rate x price summed over the
    settlements at or before each 1h bar's start, so the difference covers the settlements in (entry, exit]. NaN where the coin or the hours are missing."""
    out = np.full(len(T), np.nan)
    szm.point_at(szm.PERPS)
    for coin, g in T.groupby("coin"):
        hh = cw.hourly(coin)
        if hh is None:
            continue
        t = hh.time.to_numpy("datetime64[ns]")
        fc = cw.funding_cum(coin, t, hh)
        ti, to = g.t_in.to_numpy("datetime64[ns]"), g.t_out.to_numpy("datetime64[ns]")
        i, j = np.searchsorted(t, ti), np.searchsorted(t, to)
        ok = (i < len(t)) & (j < len(t))
        ok[ok] &= t[i[ok]] == ti[ok]
        e = np.where(ok, hh.open.to_numpy(float)[np.minimum(i, len(t) - 1)], np.nan)
        paid = np.where(ok, (fc[np.minimum(j, len(t) - 1)] - fc[np.minimum(i, len(t) - 1)]) / e, np.nan)
        out[g.index.to_numpy()] = paid / g.rf.to_numpy(float)
    return out


def flat_funding_r(T: pd.DataFrame) -> np.ndarray:
    """What the study charged: 1bp / 8h on longs for the hours held (candle_manage.cost_r), in R."""
    hours = (T.t_out - T.t_in) / pd.Timedelta(hours=1)
    return (cs.FUND_H * hours / T.rf).to_numpy(float)


def costs():
    """--costs (after the verdict, descriptive): the perp trades re-charged with the funding they really paid, then extra round-trip slippage of 10 / 30bp
    (coins ranked 41-100 cost more than 12bp to trade), and the sized accounts again. Spot paid no funding: its flat charge is refunded."""
    X = pd.read_pickle(LOG.with_name("rsi80_more_trades.pkl")).reset_index(drop=True)
    perp = X.src.isin(["OLD", "NEW-PERP"]).to_numpy()
    real = np.zeros(len(X))
    real[perp] = real_funding_r(X[perp].reset_index(drop=True))
    flat = flat_funding_r(X)
    X["net_real"] = X.net + flat - real
    L = [f"backtest/rsi80_more.py --costs, {pd.Timestamp.now():%Y-%m-%d %H:%M}; the same trades with the funding each perp trade really paid (spot: none)"]
    for nm in ("OLD", "NEW-PERP", "NEW-SPOT"):
        x = X[X.src == nm]
        m = np.isfinite(x.net_real)
        L.append(f"  {nm:<9} n {len(x):5d} (funding found for {m.sum()})  per-trade R: as studied {x.net[m].mean():+.3f}, real funding {x.net_real[m].mean():+.3f} "
                 f"(flat charge {np.mean(flat[x.index[m]]):.3f}R, real {np.mean(real[x.index[m]]):.3f}R a trade); "
                 + "  ".join(f"+{bp}bp slippage {(x.net_real[m] - bp / 1e4 / x.rf[m]).mean():+.3f}" for bp in (10, 30)))
    for bp in (0, 10, 30):
        L.append(f"\n  SIZED ACCOUNTS with real funding and +{bp}bp round-trip slippage (every signal, risk a share of the booked equity, under $5 skipped)")
        for nm, mask in (("top-100 perps 2020-26", perp), ("NEW-PERP only", (X.src == "NEW-PERP").to_numpy()), ("NEW-SPOT 2017-19", (X.src == "NEW-SPOT").to_numpy())):
            T = X[mask & np.isfinite(X.net_real)].copy()
            T["net"] = T.net_real - bp / 1e4 / T.rf
            T = T.reset_index(drop=True)
            for risk in (0.01, 0.02):
                for start in (50.0, 100.0, 300.0):
                    a = sized_account(T, start, risk)
                    L.append(f"    {nm:<22} risk {risk * 100:.0f}%  ${start:>4.0f} -> ${a['end']:>10,.2f} ({a['cagr'] * 100:+4.0f}%/yr)  taken {a['taken']:4d}, "
                             f"skipped {a['skipped']:4d}, deepest fall {a['dd'] * 100:3.0f}%, most open {a['gross']:.1f}x")
    txt = "\n".join(L)
    LOG.with_name("rsi80_more_costs.txt").write_text(txt + "\n", encoding="utf-8")
    print(txt)


def sized_only():
    """--sized: the sized accounts from the saved trades (no rebuild)."""
    X = pd.read_pickle(LOG.with_name("rsi80_more_trades.pkl"))
    perps = X[X.src.isin(["OLD", "NEW-PERP"])].reset_index(drop=True)
    print("\n".join(sized_lines(perps, X[X.src == "NEW-PERP"].reset_index(drop=True))))


if __name__ == "__main__" and "--costs" in sys.argv:
    costs()
elif __name__ == "__main__" and "--sized" in sys.argv:
    sized_only()
elif __name__ == "__main__":
    main()
