"""ATTACKING ndx_capit.py's 22 PASSES BEFORE BELIEVING THEM (2026-10-12)

ndx_capit.py found the first NASDAQ result in this repo that passes both halves against a buy-every-day control: buying
^NDX after sharp down days (RSI(2) low, three down closes, a close under the lower Bollinger band, a 2-sd down day, a
close at the day's low) and selling on the first close above the 5-day average. The repo's rule: a good result is a
bug until shown otherwise. The checks, on the six signal families x close/open entry x exit X2 x gate none/200d:

    1  OTHER INDICES, rules frozen: S&P 500 (1999-), Dow (2003-), DAX (2003-), Nikkei (2003-), STOXX 50 (2007-), Yahoo
       daily, each split 60/40, NASDAQ's costs. A market property shows on all of them; a fit to NDX does not.
    2  PLATEAU on NDX (close entry, no gate): RSI(2) under 5/10/15/20/25; IBS under 0.10..0.30; 2/3/4/5 down closes;
       Bollinger 1.5/2/2.5 sd; a down day of 1.5/2/2.5/3 sd; the exit average 3/5/10 days x at most 5/10/20 days.
    3  RECENT YEARS: each candidate's net by year 2018-2026, and 2020+ / 2023+ (n, mean, t).
    4  EXNESS'S OWN PRICE: USTECm daily bars at the 16:00 ET cash close built from backtest/mt5_1m.py's 1m bars
       (2026-01 .. 2026-10) against ^NDX's closes - do the CFD's daily returns and the signal days agree?
    5  SIZE: the worst move against each trade before its exit (entry -> lowest low), and what it does to $221 at
       USTECm's minimum 0.05 lot (~$1,500 of NASDAQ at 30,000: ~6.8x).

REGISTERED BEFORE THE RUN (2026-10-12, after ndx_capit.py's result, before any of these checks)
    R1  The long X2 close-entry cells for rsi2_10, down3, bb_low and ibs20 are net positive on both halves on at least
        4 of the 5 other indices; at least half of all their other-index cells PASS the same rule.
    R2  No knife-edge: every neighbour setting of rsi2 / ibs / downN / bb / capit and every exit variant is net positive
        on both halves (close entry, no gate).
    R3  Since 2020 the candidates are positive with t >= 1.5; since 2023 positive but t < 2 (too few trades).
    R4  The CFD's cash-close daily returns correlate > 0.98 with ^NDX's, and the signals fire on >= 90% of the same days.
    R5  The worst move against a trade is 10-20% (2008 / 2020) for the ungated cells and under 10% gated; at 6.8x that
        is ruin for $221 on the ungated cells.

RESULT (2026-10-11 21:00 UTC, logs/ndx_capit_check.txt)
    - R1 WRONG, and it is the main caveat: frozen on five other indices, 3 of 120 cells pass (all on the S&P 500); the
      core cells are positive on both halves on 1 of 5 (S&P). Most cells elsewhere are positive overall but small
      (rsi2_10: S&P +0.33%, Dow +0.12%, DAX +0.15%, Nikkei +0.22%, STOXX +0.31% a trade) with t < 2, and the DAX and
      STOXX holdouts are ~0. NASDAQ's edge is 2-3x the others' even per unit of daily volatility. So: a NASDAQ effect
      (the most volatile index, and the one that rose most in 27 years) - not a law of every index.
    - R2 RIGHT: no knife-edge. RSI(2) under 5..25, IBS under 0.10..0.30, 2-5 down days, Bollinger 1.5-2.5, down days of
      1.5-3 sd, exits above the 3/5/10-day average within 5/10/20 days: all positive on both halves (36 settings).
    - R3 WRONG the good way: since 2020 every cell is positive with t >= 1.5 and since 2023 most have t >= 2 (rsi2_10 at
      the close: 47 trades, +1.09% a trade, t +4.8) - during NASDAQ's AI-era rise.
    - R4 WRONG by a hair: Exness USTECm at 16:00 ET tracks ^NDX (daily returns corr 0.9989, median gap 3.1bp) and the
      signals agree on 88-96% of their days (predicted >= 90%).
    - R5 WRONG: the worst move against a trade was 20-26% ungated (2000-01, 2008) and 14-25% gated (March 2000, when the
      200-day gate was still on); 95th percentile 6-10%, median 1-1.5%. At Exness's 0.05-lot minimum ($1,546 of NASDAQ,
      ~7x on $221) the worst trade costs 95-178% of the account: NOT tradable on $221 at Exness.
    - Found while sizing (read-only, ccxt): Bitget lists QQQ/USDT and NDX100/USDT perps (isRwa, $5 minimum, 6bp / 2bp,
      funding 0.0 at the check, 24/7 with thin weekends; QQQ ~$0.66M a day). The QQQ perp at 16:00 ET tracked ^NDX's
      close over 51 days: corr 0.9993, median gap 3.9bp. It can carry the rule at 1-2x on $221.
    Reading: buying NASDAQ's sharp down days and selling the first close above the 5-day average is the strongest
    NASDAQ result in the repo - 27 years, both halves, a smooth plateau, positive after publication and since 2020. It
    earns ~10-12% a year at 1x (in the market ~15-20% of days), not 10% a month, and its worst trade is a 20-26% fall.
    It did not generalise to other indices, so it rests on NASDAQ staying NASDAQ. Candidate for a forward paper record.

    python -m backtest.ndx_capit_check
"""
from __future__ import annotations

import itertools
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest import ndx_capit as nc  # noqa: E402
from backtest import mt5_1m  # noqa: E402

LOG = ROOT / "logs" / "ndx_capit_check.txt"
DATA = ROOT / "strategy_analysis" / "data"
FAMS = ["capit_z2", "rsi2_10", "rsi2_5", "ibs20", "down3", "bb_low"]
OTHERS = {"S&P 500": "yf_GSPC.csv", "Dow": "yf_DJI.csv", "DAX": "yf_GDAXI.csv", "Nikkei": "yf_N225.csv",
          "STOXX 50": "yf_STOXX50E.csv"}
LOT_NOTIONAL = 0.05 * 30_000


def cells(P, L, split_i, fams=FAMS, entries=("close", "open"), gates=(False, True), **kw):
    rows = []
    for f, en, g in itertools.product(fams, entries, gates):
        tr = nc.run(P, L[f], 1, en, "X2", g, **kw)
        s = nc.summarise(tr, split_i, P["dates"])
        ctl = nc.summarise(nc.run(P, L["EVERY_DAY"], 1, en, "X2", g, **kw), split_i, P["dates"])
        if s is None:
            continue
        ok = (s["net_tu"] > 0) & (s["net_ho"] > 0) & (s["t_tu"] >= 2) & (s["t_ho"] >= 2) & (s["pd_tu"] > ctl["pd_tu"]) \
            & (s["pd_ho"] > ctl["pd_ho"])
        rows.append(dict(sig=f, entry=en, gate=g, n=s["n"], net=s["net"], net_tu=s["net_tu"], t_tu=s["t_tu"],
                         net_ho=s["net_ho"], t_ho=s["t_ho"], PASS=bool(ok), years=s["years"], cagr=s["cagr"], dd=s["dd"]))
    return pd.DataFrame(rows)


def line(r):
    return (f"    {r.sig:9} {r.entry:5} {'200d' if r.gate else '-':4} n {r.n:4} | net {r.net * 100:+.2f}% | tune {r.net_tu * 100:+.2f}% "
            f"(t {r.t_tu:+.1f}) | holdout {r.net_ho * 100:+.2f}% (t {r.t_ho:+.1f})" + ("  PASS" if r.PASS else ""))


def main():
    lines = [f"backtest/ndx_capit_check.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; exit X2 (first close above the "
             f"5-day average, at most 10 days) unless stated; 1x; NASDAQ CFD costs", ""]
    # 1 other indices
    lines.append("1. OTHER INDICES, rules frozen")
    core_pos, all_cells, all_pass = 0, 0, 0
    for nm, f in OTHERS.items():
        d, P, L, _ = nc.load(DATA / f)
        split_i = int(len(d) * nc.TUNE)
        R = cells(P, L, split_i)
        lines.append(f"  {nm} ({d.date.min():%Y} .. {d.date.max():%Y}, holdout from {pd.Timestamp(P['dates'][split_i]):%Y-%m}): "
                     f"{int(R.PASS.sum())} of {len(R)} PASS")
        for r in R.itertuples():
            lines.append(line(r))
        core = R[(R.entry == "close") & (~R.gate) & R.sig.isin(["rsi2_10", "down3", "bb_low", "ibs20"])]
        core_pos += int(((core.net_tu > 0) & (core.net_ho > 0)).all())
        all_cells += len(R)
        all_pass += int(R.PASS.sum())
    lines.append("")
    # 2 plateau
    d, P, L, _ = nc.load()
    split_i = int(len(d) * nc.TUNE)
    lines.append("2. PLATEAU on NDX (long, close entry, no gate): net a trade tune / holdout (t)")
    r, sd20, r2, ibs, c, sma20, sd_c = (P[k] for k in ("r", "sd20", "r2", "ibs", "c", "sma20", "sd_c"))
    warm = np.arange(len(c)) < 200
    fam = {}
    with np.errstate(invalid="ignore"):
        for th in (5, 10, 15, 20, 25):
            fam[f"rsi2<{th}"] = r2 < th
        for th in (0.10, 0.15, 0.20, 0.25, 0.30):
            fam[f"ibs<{th:.2f}"] = ibs < th
        dn = r < 0
        for k in (2, 3, 4, 5):
            m = np.ones(len(c), bool)
            for j in range(k):
                m &= np.r_[np.zeros(j, bool), dn[:len(dn) - j]]
            fam[f"down{k}"] = m
        for k in (1.5, 2.0, 2.5):
            fam[f"bb{k:g}"] = c < sma20 - k * sd_c
        for k in (1.5, 2.0, 2.5, 3.0):
            fam[f"z{k:g}"] = r <= -k * sd20
    fam = {k: np.nan_to_num(v, nan=0).astype(bool) & ~warm for k, v in fam.items()}
    plateau_ok = True
    for k, sig in fam.items():
        s = nc.summarise(nc.run(P, sig, 1, "close", "X2", False), split_i, P["dates"])
        ok = s["net_tu"] > 0 and s["net_ho"] > 0
        plateau_ok &= ok
        lines.append(f"  {k:9} n {s['n']:4} | {s['net_tu'] * 100:+.2f}% ({s['t_tu']:+.1f}) / {s['net_ho'] * 100:+.2f}% ({s['t_ho']:+.1f})"
                     + ("" if ok else "  <- not positive on both"))
    lines.append("  exit variants on rsi2<10 and down3 (close entry, no gate):")
    for sma, mh in itertools.product(("sma3", "sma5", "sma10"), (5, 10, 20)):
        parts = []
        for k in ("rsi2<10", "down3"):
            s = nc.summarise(nc.run(P, fam[k], 1, "close", "X2", False, sma=sma, maxh=mh), split_i, P["dates"])
            ok = s["net_tu"] > 0 and s["net_ho"] > 0
            plateau_ok &= ok
            parts.append(f"{k} {s['net_tu'] * 100:+.2f}% ({s['t_tu']:+.1f}) / {s['net_ho'] * 100:+.2f}% ({s['t_ho']:+.1f})")
        lines.append(f"    exit above {sma[3:]:>2}-day avg, max {mh:2} days: " + " | ".join(parts))
    lines.append("")
    # 3 recent years
    lines.append("3. RECENT YEARS on NDX (net % summed by year at 1x; 2020+ and 2023+ per trade)")
    R = cells(P, L, split_i)
    yrs = list(range(2018, 2027))
    lines.append(f"  {'cell':26}" + "".join(f"{y:>7}" for y in yrs) + "   2020+ n / mean / t     2023+ n / mean / t")
    r3 = []
    for rr in R.itertuples():
        tr = np.array(nc.run(P, L[rr.sig], 1, rr.entry, "X2", rr.gate), dtype=float)
        dts = pd.to_datetime(P["dates"][tr[:, 0].astype(int)])
        net = tr[:, 3]
        seg = []
        for y0 in (2020, 2023):
            x = net[dts.year >= y0]
            t = x.mean() / (x.std(ddof=1) / np.sqrt(len(x))) if len(x) > 2 else np.nan
            seg.append((len(x), x.mean(), t))
        r3.append((rr.sig, rr.entry, rr.gate, seg))
        lines.append(f"  {rr.sig:9} {rr.entry:5} {'200d' if rr.gate else '-':4}       " + "".join(
            f"{rr.years.get(y, 0) * 100:+7.1f}" for y in yrs) + "".join(
            f"   {n:3} / {m * 100:+.2f}% / {t:+.1f}" for n, m, t in seg))
    lines.append("")
    # 4 the CFD's own prices
    lines.append("4. EXNESS USTECm vs ^NDX at the 16:00 ET close (backtest/mt5_1m.py 1m bars)")
    m1 = mt5_1m.load("USTECm")
    ts = pd.to_datetime(m1.t, unit="ms").dt.tz_localize("UTC").dt.tz_convert("America/New_York")
    m1 = m1.assign(et=ts.dt.tz_localize(None))
    m1["day"] = m1.et.dt.normalize()
    sess = m1[(m1.et.dt.time >= pd.Timestamp("09:30").time()) & (m1.et.dt.time < pd.Timestamp("16:00").time())]
    cfd = sess.groupby("day").agg(o=("o", "first"), h=("h", "max"), l=("l", "min"), c=("c", "last"), n=("t", "size"))
    cfd = cfd[cfd.n >= 300]
    nd = d.set_index("date")[["open", "high", "low", "close"]]
    j = cfd.join(nd, how="inner")
    rc, rn = j.c.pct_change(), j.close.pct_change()
    ok = rc.notna() & rn.notna()
    corr = float(np.corrcoef(rc[ok], rn[ok])[0, 1])
    lines.append(f"  {len(j)} common days {j.index.min():%Y-%m-%d} .. {j.index.max():%Y-%m-%d}: daily return correlation {corr:.4f}, "
                 f"median |difference| {(rc - rn)[ok].abs().median() * 1e4:.1f}bp; basis (CFD / index - 1) median "
                 f"{(j.c / j.close - 1).median() * 100:+.2f}%")
    agree = []
    for nm_, fn in (("rsi2<10", lambda c_, h_, l_: nc.rsi(c_, 2) < 10),
                    ("ibs<0.2", lambda c_, h_, l_: (c_ - l_) / np.where(h_ > l_, h_ - l_, 1) < 0.2),
                    ("down3", lambda c_, h_, l_: np.r_[False, False, False, (np.diff(c_)[2:] < 0) & (np.diff(c_)[1:-1] < 0)
                                                       & (np.diff(c_)[:-2] < 0)])):
        a = fn(j.c.to_numpy(), j.h.to_numpy(), j.l.to_numpy())[20:]
        b = fn(j.close.to_numpy(), j.high.to_numpy(), j.low.to_numpy())[20:]
        both, either = int((a & b).sum()), int((a | b).sum())
        agree.append(both / either if either else np.nan)
        lines.append(f"    {nm_:8}: CFD fires {int(a.sum())} days, ^NDX {int(b.sum())}, both {both} ({both / max(either, 1) * 100:.0f}% of either)")
    lines.append("")
    # 5 the move against each trade, and $221
    lines.append(f"5. THE MOVE AGAINST EACH TRADE before its exit (entry -> lowest low), and $221 at the 0.05-lot minimum "
                 f"(${LOT_NOTIONAL:,.0f}, {LOT_NOTIONAL / 221:.1f}x)")
    worst = {}
    for rr in R.itertuples():
        tr = np.array(nc.run(P, L[rr.sig], 1, rr.entry, "X2", rr.gate, mae=True), dtype=float)
        mae = tr[:, 5]
        k = int(np.argmax(mae))
        worst[(rr.sig, rr.entry, rr.gate)] = mae.max()
        lines.append(f"  {rr.sig:9} {rr.entry:5} {'200d' if rr.gate else '-':4}: median {np.median(mae) * 100:4.1f}%, 95th "
                     f"{np.percentile(mae, 95) * 100:4.1f}%, worst {mae.max() * 100:4.1f}% ({pd.Timestamp(P['dates'][int(tr[k, 0])]):%Y-%m-%d}) "
                     f"-> on $221 at 0.05 lot: worst {mae.max() * LOT_NOTIONAL / 221 * 100:4.0f}% of the account | "
                     f"net a trade {tr[:, 3].mean() * LOT_NOTIONAL:+.2f}$")
    lines.append("")
    # predictions
    lines.append("REGISTERED PREDICTIONS")
    lines.append(f"  R1 core cells positive on both halves on {core_pos} of 5 other indices; other-index cells passing {all_pass} of "
                 f"{all_cells} -> {'RIGHT' if core_pos >= 4 and all_pass >= all_cells / 2 else 'WRONG'}")
    lines.append(f"  R2 every neighbour and exit variant positive on both halves: {plateau_ok} -> {'RIGHT' if plateau_ok else 'WRONG'}")
    ok20 = all(seg[0][1] > 0 and seg[0][2] >= 1.5 for *_, seg in r3)
    ok23 = all(seg[1][1] > 0 and seg[1][2] < 2 for *_, seg in r3)
    lines.append(f"  R3 since 2020 all positive with t >= 1.5: {ok20}; since 2023 all positive with t < 2: {ok23} -> "
                 f"{'RIGHT' if ok20 and ok23 else 'WRONG'}")
    lines.append(f"  R4 correlation {corr:.4f}, signal agreement {np.nanmin(agree) * 100:.0f}-{np.nanmax(agree) * 100:.0f}% -> "
                 f"{'RIGHT' if corr > 0.98 and np.nanmin(agree) >= 0.9 else 'WRONG'}")
    ung = [v for (s_, e_, g_), v in worst.items() if not g_]
    gat = [v for (s_, e_, g_), v in worst.items() if g_]
    lines.append(f"  R5 worst move: ungated {min(ung) * 100:.0f}-{max(ung) * 100:.0f}%, gated {min(gat) * 100:.0f}-{max(gat) * 100:.0f}% -> "
                 f"{'RIGHT' if 0.10 <= min(ung) and max(ung) <= 0.20 and max(gat) < 0.10 else 'WRONG'}")
    txt = "\n".join(lines)
    print(txt)
    LOG.write_text(txt + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
