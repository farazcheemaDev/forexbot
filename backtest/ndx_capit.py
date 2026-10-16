"""CRYPTO'S ONLY SURVIVING FAMILY, ON NASDAQ: BUY THE FORCED SELLING (2026-10-12)

THE USER (2026-10-12): "there must be something that we tried on crypto that should work on nasdaq specifically because
we have some clues of our own from his strategy - we dont need to copy him, we can make our own strategy from it".

What the repo knows, and what it rules in or out:
- His ENTRY clues as rules are dead (his_micro.py 18/18 cells, his_ta / his_1m / his_model, his_direction s36: his side
  is not in the price at any horizon). What is usable from him is the SHAPE of the trade: NASDAQ only, a small target,
  no stop, out fast - which only pays when the entry is a bounce that is likely to come.
- On crypto the only books that survived every test are the FORCED-FLOW bounces: capit2 (a coin down 10% in 24h, a limit
  2% under; all 4 bar phases), and the crash bids (resting buys under the market, sold at the close). Trend and
  indicator scalps died everywhere, NASDAQ included (cfd_scalp.py, cfd_bigtarget.py, forex.py's USTECm trend book).
- Equity indices have the same mechanism on the daily scale and a much longer record: after sharp falls, leveraged and
  volatility-targeting holders sell, and the index bounces (the "short-term reversal" of index returns; RSI(2) and
  IBS rules published 2004-2009). Never tested here. ^NDX daily, 1999-01 .. 2026-09 (Yahoo, 6,973 days): 27 years, four
  bear markets (2000-02, 2008, 2020, 2022).

SIGNALS on day i's close (long; the mirror short is reported as a control):
    capit_z2 / capit_z2.5   the day's return <= -2 / -2.5 x the prior 20 days' daily sd (capit2's "down 10% in 24h")
    rsi2_10 / rsi2_5        RSI(2) under 10 / 5
    ibs20                   the close in the bottom 20% of the day's range
    down3                   three down closes in a row
    bb_low                  the close under Bollinger(20, 2)
    crash_bid1 / 1.5        crypto's crash bid: on day i+1 a resting limit at close_i x (1 - m x ATR(14)%), m = 1 / 1.5;
                            filled if the low reaches it, at min(open, limit)
ENTRY   CLOSE (at the signal day's close - the CFD trades at 16:00 ET, the signal is known minutes before) or OPEN
        (the next day's open - strictly causal). The crash bids enter at their fill.
EXITS   X1  one day: the next close (an OPEN entry exits at that same day's close: no night held)
        X2  the first close above the 5-day average, at most 10 days (the published exit)
        X3  HIS shape: a +1 ATR(14) take-profit, NO stop, out at the close of day 10 (a target is not counted on a
            limit-entry day, whose high may come before the fill)
FILTER  none, or close > 200-day average (a bull-market gate)
COSTS   USTECm (mt5.symbol_info, 2026-10-12): spread 0.77bp a round trip; swap 2.27bp a night held (681.3 points a lot),
        each calendar night between entry and exit (a weekend = 3). One position at a time per cell. 1x.
CONTROL EVERY DAY entered under the same entry / exit / filter - the drift a dip-buyer gets for free. A cell's edge is its
        return PER DAY IN THE MARKET minus the control's.
SPLIT   tune = first 60% of days (to 2015-08), holdout = the rest; also 2010+ ("after publication").
PASS    net a trade > 0 with t >= 2 on BOTH halves, AND per day in the market above the control on both halves.

REGISTERED BEFORE THE RUN (2026-10-12)
    N1  Long dip-buys at the CLOSE (rsi2, ibs, capit, down3, bb_low) net +0.2..+0.6% a trade at 1x, win 60-75%; at
        least 5 long cells PASS.
    N2  Entering at the next OPEN loses most of it (the bounce is largely overnight): fewer than half of the close-entry
        passes survive with an open entry.
    N3  Crypto's crash bid fills rarely (under 10 a year at m = 1) and does not pass (t < 2 on at least one half).
    N4  The mirror shorts (sell the rallies) lose on both halves.
    N5  After publication (2010+) the passing cells earn at most half their 1999-2009 edge a trade.
    N6  The 200-day gate lowers the edge a trade (the biggest bounces come in bear markets) but cuts the worst fall.

RESULT (2026-10-11 21:00 UTC, logs/ndx_capit.txt / .csv; 6,973 days, tune < 2015-08)
    22 of 192 cells PASS - 21 long dip-buys and one short (rsi2_5 X1 gated, 53 trades: about what chance gives).
    - N1 RIGHT: long close-entry dip-buys net a median +0.43% a trade, won 73%; 12 PASS. The strongest, exit X2:
        rsi2_10  330 trades, 11.9 a year, won 70%, +0.95% a trade (tune +1.18% t +4.8 | holdout +0.57% t +3.5), 1x
                 CAGR +11.3%, worst fall 22%
        down3    330 trades, +1.02% (t +6.1 | +3.9), CAGR +12.4%, fall 22%
        bb_low   167 trades, 6 a year, +1.29% (t +4.4 | +4.2), CAGR +7.8%, fall 13%
        ibs20    864 trades, 31 a year, +0.39% (t +2.4 | +5.0), CAGR +11.8%, fall 58% (19% with the 200-day gate)
      Per day in the market every pass earns 3-6x the buy-every-day control on both halves.
    - N2 WRONG: 8 of the 12 close-entry passes also pass entering at the next OPEN - the bounce is not only overnight.
    - N3 WRONG: crypto's crash bid fills 33 times a year at 1 ATR under (NASDAQ dips that far intraday often); 0 pass.
    - N4 WRONG: shorts are mixed (41 of 96 negative on both halves), one passes.
    - N5 RIGHT: after publication (2010+) the passes earn a median 0.49 of their 1999-2009 edge - and are still positive.
    - N6 RIGHT: the 200-day gate lowers the edge a trade in 79% of long cells and the worst fall in 92%.
    Checked before belief in backtest/ndx_capit_check.py: robust on NASDAQ, weak on 5 other indices, and the worst
    trade went 20-26% against - read that file's RESULT before quoting any number here.

    python -m backtest.ndx_capit
"""
from __future__ import annotations

import itertools
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DATA = ROOT / "strategy_analysis" / "data" / "yf_NDX.csv"
LOG = ROOT / "logs" / "ndx_capit.txt"
SPREAD, SWAP = 0.77e-4, 2.27e-4
TUNE = 0.60
MAXH = 10


def rsi(c, n):
    d = np.r_[0.0, np.diff(c)]
    up = pd.Series(np.where(d > 0, d, 0.0)).ewm(alpha=1 / n, adjust=False).mean().to_numpy()
    dn = pd.Series(np.where(d < 0, -d, 0.0)).ewm(alpha=1 / n, adjust=False).mean().to_numpy()
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(dn > 0, 100 - 100 / (1 + up / dn), 100.0)


def load(path=DATA):
    d = pd.read_csv(path, parse_dates=["Date"]).rename(columns=str.lower).sort_values("date", kind="stable")
    d = d.dropna().reset_index(drop=True)
    o, h, l, c = (d[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    r = np.r_[np.nan, c[1:] / c[:-1] - 1]
    sd20 = pd.Series(r).rolling(20).std().shift(1).to_numpy()            # known before day i
    pc = np.r_[c[0], c[:-1]]
    tr = np.maximum(h - l, np.maximum(abs(h - pc), abs(l - pc)))
    atr = pd.Series(tr).rolling(14).mean().to_numpy() / c                  # as a fraction, at day i's close
    sma5 = pd.Series(c).rolling(5).mean().to_numpy()
    sma20 = pd.Series(c).rolling(20).mean().to_numpy()
    sd_c = pd.Series(c).rolling(20).std(ddof=0).to_numpy()
    sma200 = pd.Series(c).rolling(200).mean().to_numpy()
    r2 = rsi(c, 2)
    ibs = np.where(h > l, (c - l) / np.where(h > l, h - l, 1), 0.5)
    dn = r < 0
    down3 = dn & np.r_[False, dn[:-1]] & np.r_[False, False, dn[:-2]]
    up3 = (r > 0) & np.r_[False, r[:-1] > 0] & np.r_[False, False, r[:-2] > 0]
    with np.errstate(invalid="ignore"):
        L = {"capit_z2": r <= -2 * sd20, "capit_z2.5": r <= -2.5 * sd20, "rsi2_10": r2 < 10, "rsi2_5": r2 < 5,
             "ibs20": ibs < 0.2, "down3": down3, "bb_low": c < sma20 - 2 * sd_c,
             "EVERY_DAY": np.ones(len(c), bool)}
        S = {"capit_z2": r >= 2 * sd20, "capit_z2.5": r >= 2.5 * sd20, "rsi2_10": r2 > 90, "rsi2_5": r2 > 95,
             "ibs20": ibs > 0.8, "down3": up3, "bb_low": c > sma20 + 2 * sd_c, "EVERY_DAY": np.ones(len(c), bool)}
    warm = np.arange(len(c)) < 200
    for k in L:
        L[k] = np.nan_to_num(L[k], nan=0).astype(bool) & ~warm
        S[k] = np.nan_to_num(S[k], nan=0).astype(bool) & ~warm
    bull = np.nan_to_num(c > sma200, nan=0).astype(bool)
    P = dict(o=o, h=h, l=l, c=c, atr=atr, sma5=sma5, bull=bull, dates=d.date.to_numpy(), r=r, sd20=sd20, r2=r2, ibs=ibs,
             sma20=sma20, sd_c=sd_c, sma3=pd.Series(c).rolling(3).mean().to_numpy(),
             sma10=pd.Series(c).rolling(10).mean().to_numpy())
    return d, P, L, S


def nights(dates, a, b):
    return int((pd.Timestamp(dates[b]) - pd.Timestamp(dates[a])).days)


def run(P, sig, side, entry, exit_, gate, limit_m=None, sma="sma5", maxh=MAXH, mae=False):
    """one position at a time: list of (entry_idx, exit_idx, gross, net, days_in_market[, worst adverse move])."""
    o, h, l, c, atr, bull, dates = (P[k] for k in ("o", "h", "l", "c", "atr", "bull", "dates"))
    sma5 = P[sma]
    n = len(c)
    out, free = [], -1
    for i in np.flatnonzero(sig):
        if i <= free or i + 1 >= n:
            continue
        if gate and not (bull[i] if side > 0 else not bull[i]):
            continue
        if not np.isfinite(atr[i]):
            continue
        if limit_m is not None:                                         # crash bid on day i+1
            j = i + 1
            lim = c[i] * (1 - side * limit_m * atr[i])
            if (side > 0 and l[j] > lim) or (side < 0 and h[j] < lim):
                continue
            e = min(o[j], lim) if side > 0 else max(o[j], lim)
            ej, same_day_target = j, False
        elif entry == "close":
            e, ej, same_day_target = c[i], i, False
        else:
            j = i + 1
            e, ej, same_day_target = o[j], j, True
        tgt = e * (1 + side * atr[i])
        at_close = entry == "close" and limit_m is None
        first = ej + 1 if at_close else ej                 # first day whose CLOSE can be the exit
        first_tgt = ej if same_day_target else ej + 1      # first day whose HIGH / LOW can hit the target
        if first >= n:
            continue
        k, x = None, None
        if exit_ == "X1":
            k, x = first, c[first]
        else:
            last = min(ej + maxh, n - 1)
            if last < first:
                continue
            for m in range(first, last + 1):
                if exit_ == "X3" and m >= first_tgt and ((side > 0 and h[m] >= tgt) or (side < 0 and l[m] <= tgt)):
                    gap = m > ej and ((side > 0 and o[m] >= tgt) or (side < 0 and o[m] <= tgt))
                    k, x = m, (o[m] if gap else tgt)
                    break
                if exit_ == "X2" and ((side > 0 and c[m] > sma5[m]) or (side < 0 and c[m] < sma5[m])):
                    k, x = m, c[m]
                    break
            if k is None:
                k, x = last, c[last]
        gross = side * (x / e - 1)
        nts = nights(dates, ej, k)
        net = gross - SPREAD - SWAP * nts
        rec = (i, k, gross, net, max(k - ej, 0) + (0 if entry == "close" and limit_m is None else 1))
        if mae:
            lo_ = l[first:k + 1].min() if side > 0 else h[first:k + 1].max()
            if not at_close:
                lo_ = min(lo_, l[ej]) if side > 0 else max(lo_, h[ej])
            rec += (max(0.0, -side * (lo_ / e - 1)),)
        out.append(rec)
        free = k
    return out


def summarise(tr, split_i, dates):
    if not tr:
        return None
    a = np.array(tr, dtype=float)
    i0, net, days = a[:, 0], a[:, 3], np.maximum(a[:, 4], 1)
    res = {"n": len(a), "win": float((net > 0).mean()), "net": float(net.mean()), "per_day": float(net.sum() / days.sum())}
    yrs = (pd.Timestamp(dates[-1]) - pd.Timestamp(dates[0])).days / 365.25
    res["per_yr"] = len(a) / yrs
    eq = np.cumprod(1 + net)
    res["dd"] = float(1 - (eq / np.maximum.accumulate(eq)).min())
    res["cagr"] = float(eq[-1] ** (1 / yrs) - 1)
    for nm, m in (("tu", i0 < split_i), ("ho", i0 >= split_i)):
        x = net[m]
        res[f"n_{nm}"] = int(m.sum())
        res[f"net_{nm}"] = float(x.mean()) if len(x) else np.nan
        res[f"t_{nm}"] = float(x.mean() / (x.std(ddof=1) / np.sqrt(len(x)))) if len(x) > 2 and x.std(ddof=1) > 0 else np.nan
        res[f"pd_{nm}"] = float(x.sum() / days[m].sum()) if m.any() else np.nan
    for nm, (a_, b_) in (("pre10", ("1999", "2010")), ("post10", ("2010", "2027"))):
        dd_ = pd.to_datetime(dates[i0.astype(int)])
        m = (dd_ >= a_) & (dd_ < b_)
        res[f"net_{nm}"] = float(net[m].mean()) if m.any() else np.nan
    yr = pd.Series(net, index=pd.to_datetime(dates[i0.astype(int)]).year).groupby(level=0).sum()
    res["years"] = yr
    return res


def main():
    d, P, L, S = load()
    dates = P["dates"]
    split_i = int(len(d) * TUNE)
    lines = [f"backtest/ndx_capit.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; ^NDX daily {d.date.min():%Y-%m-%d} .. "
             f"{d.date.max():%Y-%m-%d} ({len(d)} days); tune < {pd.Timestamp(dates[split_i]):%Y-%m-%d} <= holdout; 1x; costs "
             f"spread {SPREAD * 1e4:.2f}bp + swap {SWAP * 1e4:.2f}bp a night", ""]
    rows = []
    cells = list(itertools.product(("long", "short"), [k for k in L], ("close", "open"), ("X1", "X2", "X3"), (False, True)))
    cells += list(itertools.product(("long", "short"), ["crash_bid1", "crash_bid1.5"], ("limit",), ("X1", "X2", "X3"), (False, True)))
    for side_nm, name, entry, ex, gate in cells:
        side = 1 if side_nm == "long" else -1
        if name.startswith("crash_bid"):
            m = float(name.replace("crash_bid", ""))
            sig = L["EVERY_DAY"]
            tr = run(P, sig, side, "limit", ex, gate, limit_m=m)
        else:
            sig = (L if side > 0 else S)[name]
            tr = run(P, sig, side, entry, ex, gate)
        s = summarise(tr, split_i, dates)
        if s is None:
            continue
        rows.append(dict(side=side_nm, sig=name, entry=entry, exit=ex, gate=gate, **{k: v for k, v in s.items() if k != "years"},
                         years=s["years"]))
    R = pd.DataFrame(rows)
    base = R[R.sig == "EVERY_DAY"].set_index(["side", "entry", "exit", "gate"])
    def ctl(r, col):
        key = (r.side, r.entry if r.entry != "limit" else "open", r.exit, r.gate)
        return base[col].get(key, np.nan)
    for nm in ("tu", "ho"):
        R[f"ctl_{nm}"] = R.apply(lambda r: ctl(r, f"pd_{nm}"), axis=1)
    R["PASS"] = (R.net_tu > 0) & (R.net_ho > 0) & (R.t_tu >= 2) & (R.t_ho >= 2) & (R.pd_tu > R.ctl_tu) & (R.pd_ho > R.ctl_ho) \
        & (R.sig != "EVERY_DAY")
    hdr = (f"  {'side':5} {'signal':12} {'entry':5} {'exit':4} {'gate':5} {'n':>5} {'/yr':>5} {'win':>4} {'net/tr':>7} "
           f"{'tune':>7} {'t':>5} {'hold':>7} {'t':>5} {'/day-ctl tu':>11} {'ho':>7} {'<2010':>7} {'2010+':>7} {'CAGR':>6} {'fall':>5}")
    for side_nm in ("long", "short"):
        lines.append(f"{side_nm.upper()} CELLS (net % a trade at 1x; '/day-ctl' = net per day in the market minus EVERY_DAY's, %)")
        lines.append(hdr)
        for r in R[R.side == side_nm].itertuples():
            lines.append(f"  {r.side:5} {r.sig:12} {r.entry:5} {r.exit:4} {'200d' if r.gate else '-':5} {r.n:5} {r.per_yr:5.1f} "
                         f"{r.win * 100:3.0f}% {r.net * 100:+6.2f}% {r.net_tu * 100:+6.2f}% {r.t_tu:+5.1f} {r.net_ho * 100:+6.2f}% "
                         f"{r.t_ho:+5.1f} {(r.pd_tu - r.ctl_tu) * 100:+10.3f} {(r.pd_ho - r.ctl_ho) * 100:+7.3f} "
                         f"{r.net_pre10 * 100:+6.2f}% {r.net_post10 * 100:+6.2f}% {r.cagr * 100:+5.1f}% {r.dd * 100:4.0f}%"
                         + ("  PASS" if r.PASS else ""))
        lines.append("")
    P_ = R[R.PASS]
    lines.append(f"PASSES: {len(P_)} of {int((R.sig != 'EVERY_DAY').sum())} cells")
    for r in P_.sort_values("t_ho", ascending=False).itertuples():
        yrs = r.years
        lines.append(f"  {r.side} {r.sig} {r.entry} {r.exit} {'200d' if r.gate else '-'}: {r.n} trades, {r.per_yr:.1f}/yr, win "
                     f"{r.win * 100:.0f}%, net {r.net * 100:+.2f}% a trade; worst year {yrs.min() * 100:+.1f}% ({yrs.idxmin()}), "
                     f"2008 {yrs.get(2008, 0) * 100:+.1f}%, 2020 {yrs.get(2020, 0) * 100:+.1f}%, 2022 {yrs.get(2022, 0) * 100:+.1f}%, "
                     f"years up {(yrs > 0).mean() * 100:.0f}%")
    lines.append("")
    # registered predictions
    lc = R[(R.side == "long") & (R.entry == "close") & R.sig.isin(["capit_z2", "capit_z2.5", "rsi2_10", "rsi2_5", "ibs20", "down3", "bb_low"])]
    lp = lc[lc.PASS]
    lines.append(f"N1 long close-entry dip-buys: median net {lc.net.median() * 100:+.2f}% a trade, median win {lc.win.median() * 100:.0f}%, "
                 f"{len(lp)} PASS -> {'RIGHT' if len(lp) >= 5 and 0.002 <= lc.net.median() <= 0.006 else 'WRONG'}")
    keys = set(zip(lp.sig, lp.exit, lp.gate))
    lo = R[(R.side == "long") & (R.entry == "open") & R.PASS]
    surv = sum((s, e, g) in keys for s, e, g in zip(lo.sig, lo.exit, lo.gate))
    lines.append(f"N2 of {len(keys)} close-entry passes, {surv} also pass with the next OPEN -> "
                 f"{'RIGHT' if len(keys) and surv < len(keys) / 2 else ('WRONG' if len(keys) else 'NOT DECIDABLE')}")
    cb = R[(R.side == "long") & R.sig.str.startswith("crash_bid")]
    cb1 = cb[(cb.sig == "crash_bid1") & (cb.exit == "X1") & (~cb.gate)]
    lines.append(f"N3 crash bid m=1: {cb1.per_yr.iloc[0] if len(cb1) else np.nan:.1f} fills a year; crash-bid cells passing: "
                 f"{int(cb.PASS.sum())} -> {'RIGHT' if len(cb1) and cb1.per_yr.iloc[0] < 10 and not cb.PASS.any() else 'WRONG'}")
    sh = R[(R.side == "short") & (R.sig != "EVERY_DAY")]
    lines.append(f"N4 shorts negative on both halves: {int(((sh.net_tu < 0) & (sh.net_ho < 0)).sum())} of {len(sh)} cells; "
                 f"any short PASS: {int(sh.PASS.sum())} -> {'RIGHT' if not sh.PASS.any() and ((sh.net_tu < 0) & (sh.net_ho < 0)).mean() > 0.5 else 'WRONG'}")
    if len(P_):
        ratio = (P_.net_post10 / P_.net_pre10)
        lines.append(f"N5 passing cells, 2010+ edge / 1999-2009 edge: median {ratio.median():.2f} -> {'RIGHT' if ratio.median() <= 0.5 else 'WRONG'}")
    g0 = R[(R.side == "long") & (R.sig != "EVERY_DAY") & ~R.gate].set_index(["sig", "entry", "exit"])
    g1 = R[(R.side == "long") & (R.sig != "EVERY_DAY") & R.gate].set_index(["sig", "entry", "exit"])
    j = g0.join(g1, lsuffix="_0", rsuffix="_1", how="inner")
    lines.append(f"N6 the 200-day gate: edge a trade lower in {(j.net_1 < j.net_0).mean() * 100:.0f}% of long cells, worst fall lower in "
                 f"{(j.dd_1 < j.dd_0).mean() * 100:.0f}% -> {'RIGHT' if (j.net_1 < j.net_0).mean() > 0.5 and (j.dd_1 < j.dd_0).mean() > 0.5 else 'WRONG'}")
    txt = "\n".join(lines)
    print(txt)
    LOG.write_text(txt + "\n", encoding="utf-8")
    R.drop(columns="years").to_csv(ROOT / "logs" / "ndx_capit.csv", index=False)


if __name__ == "__main__":
    main()
