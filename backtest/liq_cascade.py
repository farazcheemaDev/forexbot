"""LIQUIDATION CASCADES — the only edge here with a non-informational mechanism.

WHY THIS IS A DIFFERENT CATEGORY
--------------------------------
Eight strategies tested today. Every one tried to predict price from price (or from
a fee), found a few basis points, and died against a 4-12bp cost floor.

A liquidation is different in kind. When a leveraged position is force-closed, the
exchange sells REGARDLESS of value - the seller has no choice and no opinion. That
move is, by construction, not information. Whoever takes the other side is being
paid to provide liquidity to a distressed counterparty, which is one of the few
genuinely structural edges in any market.

Crucially, it is CAPACITY-LIMITED: a cascade lasts seconds to minutes and absorbs
thousands of dollars, not millions. That makes it exactly the territory a $50
account can reach and a fund cannot - the asymmetry we spent all day
mis-classifying as a handicap.

HOW WE SEE LIQUIDATIONS WITHOUT A LIQUIDATION FEED
--------------------------------------------------
Binance killed the historical forceOrders endpoint (404). But OPEN INTEREST is
published historically, and OI is the number of contracts outstanding:

    price moves + OI FALLS   -> positions are being CLOSED  -> forced / deleveraging
    price moves + OI RISES   -> positions are being OPENED  -> voluntary / new money

That distinction is the whole experiment, and it is invisible on a candle chart.

THE 2x2, TESTED AS A MECHANISM NOT A FITTED RULE
------------------------------------------------
                     price DOWN                    price UP
    OI DOWN   long liquidations (forced sell)   short squeeze (forced buy)
              -> expect REVERSION up            -> expect REVERSION down
    OI UP     new shorts (voluntary)            new longs (voluntary)
              -> expect continuation/nothing    -> expect continuation/nothing

All four quadrants are measured. If only the forced ones revert, that is the
mechanism showing up. If all four behave alike, there is no mechanism and any
single profitable cell is a fitted artefact.

    python -m backtest.liq_cascade
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

CACHE = Path(__file__).resolve().parents[1] / "strategy_analysis" / "data"
CACHE.mkdir(parents=True, exist_ok=True)

COINS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT", "DOGEUSDT",
         "ADAUSDT", "AVAXUSDT", "LINKUSDT", "DOTUSDT", "ARBUSDT", "OPUSDT",
         "APTUSDT", "SUIUSDT", "LTCUSDT", "NEARUSDT"]
PERIOD = "5m"
PAGES = 18          # 18 x 500 = 9000 rows ~= 31 days, the endpoint's limit


def _get(u):
    for _ in range(3):
        try:
            return json.load(urllib.request.urlopen(u, timeout=25))
        except Exception:
            time.sleep(1.0)
    return None


def oi_hist(sym: str) -> pd.DataFrame | None:
    f = CACHE / f"oi_{sym}_{PERIOD}.csv"
    if f.exists():
        return pd.read_csv(f, parse_dates=["t"])
    rows, end = [], int(time.time() * 1000)
    for _ in range(PAGES):
        r = _get(f"https://fapi.binance.com/futures/data/openInterestHist?"
                 f"symbol={sym}&period={PERIOD}&limit=500&endTime={end}")
        if not r:
            break
        rows = r + rows
        end = int(r[0]["timestamp"]) - 1
        time.sleep(0.25)
    if not rows:
        return None
    d = pd.DataFrame([{"t": pd.to_datetime(int(x["timestamp"]), unit="ms"),
                       "oi": float(x["sumOpenInterest"]),
                       "oiv": float(x["sumOpenInterestValue"])} for x in rows])
    d = d.drop_duplicates("t").sort_values("t").reset_index(drop=True)
    d.to_csv(f, index=False)
    return d


def klines(sym: str) -> pd.DataFrame | None:
    f = CACHE / f"k5m_{sym}.csv"
    if f.exists():
        return pd.read_csv(f, parse_dates=["t"])
    rows, end = [], int(time.time() * 1000)
    for _ in range(10):
        r = _get(f"https://fapi.binance.com/fapi/v1/klines?symbol={sym}"
                 f"&interval={PERIOD}&limit=1000&endTime={end}")
        if not r:
            break
        rows = r + rows
        end = int(r[0][0]) - 1
        time.sleep(0.2)
    if not rows:
        return None
    d = pd.DataFrame([{"t": pd.to_datetime(k[0], unit="ms"), "open": float(k[1]),
                       "high": float(k[2]), "low": float(k[3]),
                       "close": float(k[4]), "vol": float(k[5])} for k in rows])
    d = d.drop_duplicates("t").sort_values("t").reset_index(drop=True)
    d.to_csv(f, index=False)
    return d


def build() -> pd.DataFrame:
    out = []
    for s in COINS:
        oi = oi_hist(s)
        kl = klines(s)
        if oi is None or kl is None or len(oi) < 2000 or len(kl) < 2000:
            print(f"  {s}: insufficient ({0 if oi is None else len(oi)} oi, "
                  f"{0 if kl is None else len(kl)} kl)")
            continue
        d = kl.merge(oi, on="t", how="inner").sort_values("t").reset_index(drop=True)
        if len(d) < 2000:
            continue
        d["sym"] = s
        d["ret"] = np.log(d.close).diff()                 # this bar's move
        d["fwd1"] = np.log(d.close).diff().shift(-1)      # next bar
        d["fwd3"] = (np.log(d.close).shift(-3) - np.log(d.close))
        d["fwd6"] = (np.log(d.close).shift(-6) - np.log(d.close))
        d["doi"] = d.oi.pct_change()                      # OI change
        # normalise both by their own recent scale so coins are comparable
        d["ret_z"] = d.ret / d.ret.rolling(288).std()
        d["doi_z"] = d.doi / d.doi.rolling(288).std()
        out.append(d)
        print(f"  {s:9} {len(d):>5} aligned 5m bars")
    return pd.concat(out, ignore_index=True).dropna(
        subset=["ret_z", "doi_z", "fwd1", "fwd3", "fwd6"])


def main():
    print("Fetching open interest + 5m klines (cached after first run)...")
    D = build()
    span = (D.t.max() - D.t.min()).days
    print(f"\n  {len(D):,} observations, {D.sym.nunique()} coins, {span} days\n")

    print("=" * 84)
    print("THE 2x2 MECHANISM TEST — forced moves should revert, voluntary ones should not")
    print("=" * 84)
    BIG = 2.0        # |z| threshold for 'a big move' / 'a big OI change'
    cells = {
        "OI DOWN + price DOWN  (long liqs, forced sell)":
            (D.doi_z < -BIG) & (D.ret_z < -BIG),
        "OI DOWN + price UP    (short squeeze, forced buy)":
            (D.doi_z < -BIG) & (D.ret_z > BIG),
        "OI UP   + price DOWN  (new shorts, voluntary)":
            (D.doi_z > BIG) & (D.ret_z < -BIG),
        "OI UP   + price UP    (new longs, voluntary)":
            (D.doi_z > BIG) & (D.ret_z > BIG),
    }
    print(f"{'quadrant':52} {'n':>6} {'fwd1 bp':>9} {'fwd3 bp':>9} {'fwd6 bp':>9}")
    res = {}
    for name, m in cells.items():
        g = D[m]
        if len(g) < 30:
            print(f"{name:52} {len(g):>6}  too few")
            continue
        r1, r3, r6 = (g.fwd1.mean() * 1e4, g.fwd3.mean() * 1e4, g.fwd6.mean() * 1e4)
        se1 = g.fwd1.std() / np.sqrt(len(g)) * 1e4
        res[name] = (len(g), r1, se1, r3, r6)
        print(f"{name:52} {len(g):>6} {r1:>+9.2f} {r3:>+9.2f} {r6:>+9.2f}")
    base = D.fwd1.mean() * 1e4
    print(f"\n  baseline (all bars) fwd1 = {base:+.2f}bp")

    print(f"\n{'quadrant':52} {'fwd1 bp':>9} {'se':>7} {'t':>7}")
    for name, (n, r1, se1, r3, r6) in res.items():
        print(f"{name:52} {r1:>+9.2f} {se1:>7.2f} {r1/se1 if se1 else 0:>+7.2f}")

    print("\n" + "=" * 84)
    print("IS IT A MECHANISM? forced cells should revert AGAINST the move,")
    print("voluntary cells should not. Check the signs.")
    print("=" * 84)
    fd = res.get("OI DOWN + price DOWN  (long liqs, forced sell)")
    fu = res.get("OI DOWN + price UP    (short squeeze, forced buy)")
    vd = res.get("OI UP   + price DOWN  (new shorts, voluntary)")
    vu = res.get("OI UP   + price UP    (new longs, voluntary)")
    if fd and fu:
        rev = (fd[1] > 0) and (fu[1] < 0)
        print(f"  forced-sell reverts UP?    {fd[1]:+.2f}bp  {'YES' if fd[1]>0 else 'no'}")
        print(f"  forced-buy reverts DOWN?   {fu[1]:+.2f}bp  {'YES' if fu[1]<0 else 'no'}")
        if vd and vu:
            print(f"  voluntary-down continues?  {vd[1]:+.2f}bp")
            print(f"  voluntary-up continues?    {vu[1]:+.2f}bp")
        print(f"\n  -> {'MECHANISM PRESENT: only the forced moves revert' if rev else 'no clean mechanism in the signs'}")
        # the number that decides everything
        edge = (abs(fd[1]) + abs(fu[1])) / 2
        print(f"\n  average reversion after a forced move = {edge:.2f}bp over 1 bar")
        for name, c in (("taker round trip", 12.0), ("maker round trip", 4.0)):
            print(f"    vs {name:20} {c:>5.1f}bp  -> "
                  f"{'CLEARS COST' if edge > c else 'below cost'}")


if __name__ == "__main__":
    main()
