"""THE NASDAQ DIP-BUY, AND HIS "JOIN THE MOVE AFTER A PAUSE", ON FOREX, GOLD AND SILVER (2026-10-12)

THE USER (2026-10-12): "copying his signals its not the way to go - we can take something from the research we did on
him and our strategies we developed or failed on crypto which can work on forex".

What is carried over, and why:
- crypto's surviving family is buying FORCED moves (capit2, crash bids); on NASDAQ the daily version passed 27 years
  (ndx_capit.py: buy a sharp down day, out at the first close above the 5-day average) - but did not carry to other
  stock indices (ndx_capit_check.py). Forex has no upward drift, so here BOTH directions are traded: buy sharp down days
  and SELL sharp up days.
- his clue that IS usable: he joins a young move right after a short pause against it (his_strategy.md s18-19), and
  that clue never got a test at the daily scale. Its daily form is the TREND GATE: buy the dips only while the close is
  above its 200-day average, sell the rallies only while it is below.
- his trade shape: a quick target, NO stop (exit X3).

MARKETS  EURUSD GBPUSD USDJPY AUDUSD NZDUSD USDCAD USDCHF on two histories:
           YAHOO daily 2003/2006 .. 2026-09 (bad highs / lows clipped to the open/close)
           EXNESS's own prices, daily bars (New York 17:00 close) built from the MT5 1h cache, 2020-02/03 .. 2026-09/10
         gold and silver on Exness's prices only (Yahoo's futures bars are 12% / 25% flat - unusable for IBS / ATR)
SIGNALS  ndx_capit.py's six, mirrored for shorts: a 2-sd day, RSI(2) < 10 / < 5 (> 90 / > 95), IBS < 0.2 (> 0.8), three
         closes the same way, a close beyond Bollinger(20, 2)
ENTRY / EXIT / GATE / CONTROL / PASS   as ndx_capit.py: close or next open; X1 one day, X2 first close back past the
         5-day average (max 10 days), X3 +1 ATR target with no stop (max 10 days); gate none / trend; EVERY_DAY control
         per side; PASS = net > 0 with t >= 2 on both halves (60/40 by date) and above the control per day in the market
COSTS    Exness (mt5.symbol_info 2026-10-12, quotes at the Sunday open; spreads set at or above the tick medians of
         backtest/mt5_1m.py): round-trip spread bp, and the swap of the side held each night (Exness: 0 on one side,
         a charge on the other - no positive carry on these)

REGISTERED BEFORE THE RUN (2026-10-12)
    G1  Forex on Yahoo 2003-2026: under 2% of cells pass, and no signal family passes on more than 2 of the 7 pairs.
    G2  The trend gate (his pause, daily) beats the ungated cell's net a trade in over half of the forex cells, but
        none of the gated forex cells passes on more than 2 pairs.
    G3  Gold (Exness 2020-2026): long dip-buys pass in at least 3 cells (a rising, volatile market, like NASDAQ); no
        gold short passes.
    G4  Silver: nothing passes.
    G5  Every forex cell that passes on Yahoo is net positive on both halves of Exness's 2020-2026 prices as well.

RESULT (2026-10-11 21:20 UTC, logs/fx_capit.txt / .csv; 2,304 cells)
    - ON EXNESS'S OWN PRICES (2020-2026): 1 of 1,296 cells passes - GBPUSD buy-the-dip at the open in an uptrend, 14
      trades (chance gives ~1). Forex majors' median cell nets -0.05..+0.09% a trade either side; gold's long dip-buys
      +0.03% (G3 WRONG: nothing passes even through gold's 2024-26 rise); silver nothing (G4 RIGHT). The trend gate (his
      "join the move after a pause", daily) is no better than ungated: better in 55% of cells, at ~0 either way.
    - ON YAHOO (2003-2026): 80 cells "pass", 79 of them IBS at the close, at t up to +25 and 80-95% wins - A DATA BUG,
      not an edge (G1 / G2 / G5 WRONG). Yahoo's forex daily bars are not internally consistent: the open sits a median
      26-30bp from the previous close (Exness: 1.1-1.6bp - forex trades continuously), and after a close in the bottom
      fifth of the range the next close was higher 92-95% of the time (Exness, same years: 49-50%). Its bar dated D
      also matches Exness's day D-1 (daily-return correlation 0.948 at a one-day shift, 0.05 unshifted). Only 11 of the
      80 are even positive on Exness, all at t <= 1.6. New trap in CLAUDE.md s3. (fx_anomalies' T8 read these closes:
      re-checked in fx_t8_exness.py - its kill stands.)
    Reading: the daily dip / rally trade that passed on NASDAQ does not exist on forex, gold or silver at Exness's
    prices, in either direction, with or without the trend. Forex's short-horizon moves carry no bounce to buy.

    python -m backtest.fx_capit
"""
from __future__ import annotations

import itertools
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest import ndx_capit as nc  # noqa: E402

DATA = ROOT / "strategy_analysis" / "data"
LOG = ROOT / "logs" / "fx_capit.txt"
TMP = ROOT / "strategy_analysis" / "data" / "fx_capit_daily"
#            spread bp RT, swap bp a night LONG, SHORT (negative = you pay)
COSTS = {"EURUSD": (1.0, -0.51, 0.00), "GBPUSD": (1.0, -0.17, -0.04), "USDJPY": (1.0, 0.00, -0.88),
         "AUDUSD": (1.3, 0.00, -0.27), "NZDUSD": (2.5, -0.64, 0.00), "USDCAD": (1.2, 0.00, -0.81),
         "USDCHF": (1.6, 0.00, -1.25), "XAUUSD": (1.0, -1.25, 0.00), "XAGUSD": (9.5, -1.21, 0.00)}
YAHOO = {"EURUSD": "yf_EURUSD_X.csv", "GBPUSD": "yf_GBPUSD_X.csv", "USDJPY": "yf_JPY_X.csv", "AUDUSD": "yf_AUDUSD_X.csv",
         "NZDUSD": "yf_NZDUSD_X.csv", "USDCAD": "yf_CAD_X.csv", "USDCHF": "yf_CHF_X.csv"}
FAMS = ["capit_z2", "rsi2_10", "rsi2_5", "ibs20", "down3", "bb_low"]
FX = list(YAHOO)


def yahoo_csv(sym):
    """Yahoo daily with impossible bars clipped (high below the open/close etc.), written to a temp CSV nc.load reads."""
    d = pd.read_csv(DATA / YAHOO[sym], parse_dates=["Date"]).dropna()
    d = d[(d.Close > 0) & (d.Open > 0)]
    d["High"] = d[["Open", "High", "Close"]].max(axis=1)
    d["Low"] = d[["Open", "Low", "Close"]].min(axis=1)
    TMP.mkdir(parents=True, exist_ok=True)
    p = TMP / f"yahoo_{sym}.csv"
    d.to_csv(p, index=False)
    return p


def exness_csv(sym):
    """Daily bars from Exness's MT5 1h cache, closing at 17:00 New York (the forex day)."""
    h = pd.DataFrame(json.load(open(DATA / f"{sym}m_1h_2400d.json")))
    ny = pd.to_datetime(h.t, unit="ms").dt.tz_localize("UTC").dt.tz_convert("America/New_York").dt.tz_localize(None)
    day = (ny + pd.Timedelta(hours=7)).dt.normalize()                 # 17:00 NY -> next day's label
    g = h.assign(day=day).groupby("day")
    d = pd.DataFrame({"Open": g.o.first(), "High": g.h.max(), "Low": g.l.min(), "Close": g.c.last(), "n": g.size()})
    d = d[d.n >= 12].drop(columns="n").reset_index().rename(columns={"day": "Date"})
    TMP.mkdir(parents=True, exist_ok=True)
    p = TMP / f"exness_{sym}.csv"
    d.to_csv(p, index=False)
    return p


def market(sym, path, src):
    d, P, L, S = nc.load(path)
    split_i = int(len(d) * nc.TUNE)
    sp, sw_l, sw_s = COSTS[sym]
    nc.SPREAD = sp / 1e4
    rows = []
    for side_nm, en, ex, gate in itertools.product(("long", "short"), ("close", "open"), ("X1", "X2", "X3"), (False, True)):
        side = 1 if side_nm == "long" else -1
        nc.SWAP = -(sw_l if side > 0 else sw_s) / 1e4
        ctl = nc.summarise(nc.run(P, (L if side > 0 else S)["EVERY_DAY"], side, en, ex, gate), split_i, P["dates"])
        for f in FAMS:
            s = nc.summarise(nc.run(P, (L if side > 0 else S)[f], side, en, ex, gate), split_i, P["dates"])
            if s is None or ctl is None:
                continue
            ok = (s["net_tu"] > 0) & (s["net_ho"] > 0) & (s["t_tu"] >= 2) & (s["t_ho"] >= 2) & (s["pd_tu"] > ctl["pd_tu"]) \
                & (s["pd_ho"] > ctl["pd_ho"])
            rows.append(dict(src=src, sym=sym, side=side_nm, sig=f, entry=en, exit=ex, gate=gate, n=s["n"], per_yr=s["per_yr"],
                             win=s["win"], net=s["net"], net_tu=s["net_tu"], t_tu=s["t_tu"], net_ho=s["net_ho"], t_ho=s["t_ho"],
                             cagr=s["cagr"], dd=s["dd"], PASS=bool(ok), span=f"{d.date.min():%Y-%m} .. {d.date.max():%Y-%m}"))
    return pd.DataFrame(rows)


def main():
    parts = []
    for sym in FX:
        parts.append(market(sym, yahoo_csv(sym), "yahoo"))
    for sym in FX + ["XAUUSD", "XAGUSD"]:
        parts.append(market(sym, exness_csv(sym), "exness"))
    R = pd.concat(parts, ignore_index=True)
    R.to_csv(ROOT / "logs" / "fx_capit.csv", index=False)
    lines = [f"backtest/fx_capit.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; ndx_capit's dip / rally rules on forex, gold "
             f"and silver, both sides, Exness costs; {len(R)} cells", ""]
    lines.append("BY MARKET: cells passing | median net a trade, ungated / trend-gated (all cells of that market)")
    for (src, sym), g in R.groupby(["src", "sym"], sort=False):
        lines.append(f"  {src:6} {sym} {g.span.iloc[0]}: {int(g.PASS.sum()):3} of {len(g)} pass | net median ungated "
                     f"{g[~g.gate].net.median() * 100:+.3f}%, gated {g[g.gate].net.median() * 100:+.3f}% | long "
                     f"{g[g.side == 'long'].net.median() * 100:+.3f}%, short {g[g.side == 'short'].net.median() * 100:+.3f}%")
    lines.append("")
    lines.append("EVERY PASS (net % a trade at 1x)")
    for r in R[R.PASS].sort_values(["src", "sym", "t_ho"], ascending=[True, True, False]).itertuples():
        other = R[(R.src != r.src) & (R.sym == r.sym) & (R.side == r.side) & (R.sig == r.sig) & (R.entry == r.entry)
                  & (R.exit == r.exit) & (R.gate == r.gate)]
        o = (f" | on {other.src.iloc[0]}: {other.net_tu.iloc[0] * 100:+.2f}% / {other.net_ho.iloc[0] * 100:+.2f}%"
             if len(other) else "")
        lines.append(f"  {r.src:6} {r.sym} {r.side:5} {r.sig:9} {r.entry:5} {r.exit} {'trend' if r.gate else '-':5} n {r.n:4} "
                     f"({r.per_yr:.1f}/yr) won {r.win * 100:.0f}% | net {r.net * 100:+.2f}% | tune {r.net_tu * 100:+.2f}% "
                     f"(t {r.t_tu:+.1f}) holdout {r.net_ho * 100:+.2f}% (t {r.t_ho:+.1f}) | CAGR {r.cagr * 100:+.1f}% fall "
                     f"{r.dd * 100:.0f}%{o}")
    lines.append("")
    fxy = R[(R.src == "yahoo")]
    share = fxy.PASS.mean()
    fam_pairs = fxy[fxy.PASS].groupby(["side", "sig", "entry", "exit", "gate"]).sym.nunique()
    lines.append("REGISTERED PREDICTIONS")
    lines.append(f"  G1 forex on Yahoo: {int(fxy.PASS.sum())} of {len(fxy)} cells pass ({share * 100:.1f}%); most pairs for one cell: "
                 f"{int(fam_pairs.max()) if len(fam_pairs) else 0} -> {'RIGHT' if share < 0.02 and (fam_pairs.max() if len(fam_pairs) else 0) <= 2 else 'WRONG'}")
    k = ["src", "sym", "side", "sig", "entry", "exit"]
    j = fxy[~fxy.gate].set_index(k).net.to_frame("u").join(fxy[fxy.gate].set_index(k).net.rename("g"), how="inner")
    gp = fxy[fxy.gate & fxy.PASS].groupby(["side", "sig", "entry", "exit"]).sym.nunique()
    lines.append(f"  G2 trend gate better a trade in {(j.g > j.u).mean() * 100:.0f}% of forex cells; most pairs for one gated passing "
                 f"cell: {int(gp.max()) if len(gp) else 0} -> {'RIGHT' if (j.g > j.u).mean() > 0.5 and (gp.max() if len(gp) else 0) <= 2 else 'WRONG'}")
    au = R[(R.sym == "XAUUSD")]
    lines.append(f"  G3 gold: long passes {int(au[au.side == 'long'].PASS.sum())}, short passes {int(au[au.side == 'short'].PASS.sum())} -> "
                 f"{'RIGHT' if au[au.side == 'long'].PASS.sum() >= 3 and not au[au.side == 'short'].PASS.any() else 'WRONG'}")
    ag = R[(R.sym == "XAGUSD")]
    lines.append(f"  G4 silver: {int(ag.PASS.sum())} pass -> {'RIGHT' if not ag.PASS.any() else 'WRONG'}")
    ex = R[R.src == "exness"].set_index(k[1:] + ["gate"])
    yp = fxy[fxy.PASS]
    held = [(ex.loc[tuple(r[c] for c in k[1:] + ["gate"])].net_tu > 0) and (ex.loc[tuple(r[c] for c in k[1:] + ["gate"])].net_ho > 0)
            for _, r in yp.iterrows() if tuple(r[c] for c in k[1:] + ["gate"]) in ex.index]
    lines.append(f"  G5 Yahoo passes positive on both halves of Exness 2020-2026: {sum(held)} of {len(held)} -> "
                 f"{'RIGHT' if held and all(held) else ('NOT DECIDABLE' if not held else 'WRONG')}")
    txt = "\n".join(lines)
    print(txt)
    LOG.write_text(txt + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
