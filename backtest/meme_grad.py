"""SOLANA MEMECOINS - buying pump.fun graduations, measured on every coin including the dead.

THE IDEA PEOPLE TRADE
    A pump.fun coin that fills its bonding curve "graduates" to a real AMM pool
    (PumpSwap). Graduation is the moment most "memecoin bots" buy: the coin has proven
    enough demand to fill the curve, and the famous 100x stories start here.

WHY THIS IS HARD TO TEST HONESTLY
    Every screenshot is survivorship. Most graduates die within hours. The only honest
    sample is ALL graduates in a window, taken from a list that does not know which ones
    will live. pump.fun's API lists graduated coins newest-first but pages only ~1,050
    deep, which is the last ~24 hours - so this is one day of the lottery, drawn in full.
    Longer horizons need the forward collector (meme_collector.py).

WHAT COUNTS AS A GRADUATION
    In 2026 pump.fun marks many coins "complete" that never filled a curve (one had a pool
    worth $2.82). A real graduation opens a pool at roughly $20k-$300k market value. Only
    those are kept, and the number filtered out is printed.

WHAT IS MEASURED, PER COIN
    Minute candles of the PumpSwap pool from GeckoTerminal (free, 30 calls/min). The first
    candle is the graduation minute. Entry at the CLOSE of minute 1, 5 or 15 after it -
    sniper bots buy inside the graduation block, so minute 1 is already optimistic for a
    home setup. Exit at the last trade at or before +15m, +1h, +6h, +12h.
    Costs: 2% round trip (0.25% pool fee each way, priority fee, slippage on a thin pool);
    a 5% stress column, because memecoin pools get sandwiched.

    A dead pool has a price but no buyers: any exit worth under 5% of entry is booked at
    -100%.

THE NUMBER THAT MATTERS
    Equal money in every graduate - that is what a bot buying graduations earns. The mean
    of a lottery is driven by a few tickets, so the table shows the median, the win rate,
    how much of the total comes from the top 1% of coins, and a bootstrap interval.

    python -m backtest.meme_grad
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

OUT = Path(__file__).resolve().parents[1] / "strategy_analysis" / "data" / "meme"
PF = ("https://frontend-api-v3.pump.fun/coins?limit=50&sort=created_timestamp&order=DESC"
      "&includeNsfw=true&complete=true&offset={}")
GT = "https://api.geckoterminal.com/api/v2/networks/solana/pools/{}/ohlcv/minute?aggregate=1&limit=1000&currency=usd"
PF_H = {"User-Agent": "Mozilla/5.0", "Accept": "application/json",
        "Origin": "https://pump.fun", "Referer": "https://pump.fun/"}
SUPPLY = 1e9                                 # pump.fun tokens: 1e15 raw, 6 decimals
MCAP_LO, MCAP_HI = 20_000, 300_000
ENTRIES = (1, 5, 15)
EXITS = {"15m": 15, "1h": 60, "6h": 360, "12h": 720}
COST, STRESS = 0.02, 0.05


class Throttled(Exception):
    """Raised when a rate limit never cleared. Callers must NOT cache anything on it -
    an early version stored these as empty candle lists, i.e. as coins with no trades."""


def get(u, headers, tries=8, pause=6):
    for a in range(tries):
        try:
            return json.loads(urllib.request.urlopen(
                urllib.request.Request(u, headers=headers), timeout=40).read())
        except Exception as e:
            if "429" in str(e) or "timed out" in str(e):
                time.sleep(pause * (a + 1)); continue      # back off harder each time
            if "404" in str(e):
                return None
            if a == tries - 1:
                raise
            time.sleep(2)
    raise Throttled(u[:80])


def graduates():
    """Every coin pump.fun lists as graduated, newest first, as deep as it pages."""
    f = OUT / f"graduates_{time.strftime('%Y%m%d')}.json"
    if f.exists():
        return json.load(open(f))
    OUT.mkdir(parents=True, exist_ok=True)
    out, off = [], 0
    while True:
        d = get(PF.format(off), PF_H)
        if not d:
            break
        out += [{k: c.get(k) for k in ("mint", "symbol", "created_timestamp",
                                        "pump_swap_pool", "pool_address",
                                        "total_supply", "program", "mayhem_state")}
                for c in d]
        off += 50
        time.sleep(1.5)
    json.dump(out, open(f, "w"))
    return out


def candles(pool):
    """All minute candles of a pool (paging back to its first), cached, oldest first."""
    f = OUT / "ohlcv" / f"{pool}.json"
    if f.exists():
        return json.load(open(f))
    f.parent.mkdir(parents=True, exist_ok=True)
    rows, before = [], None
    for _ in range(4):
        u = GT.format(pool) + (f"&before_timestamp={before}" if before else "")
        d = get(u, {"User-Agent": "Mozilla/5.0"}, pause=10)
        time.sleep(6.5)                       # GT's real free limit is well under 30/min
        L = (((d or {}).get("data") or {}).get("attributes") or {}).get("ohlcv_list") or []
        if not L:
            break
        rows += L
        if len(L) < 1000:
            break
        before = L[-1][0]
    rows = sorted({r[0]: r for r in rows}.values())
    json.dump(rows, open(f, "w"))
    return rows


def outcome(rows):
    """Returns for each entry/exit, or None if not a real graduation."""
    if len(rows) < 2:
        return None
    t = np.array([r[0] for r in rows], dtype=np.int64)
    o, c = np.array([r[1] for r in rows]), np.array([r[4] for r in rows])
    mcap0 = o[0] * SUPPLY
    res = {"t0": int(t[0]), "mcap0": float(mcap0),
           "peak_x": float(np.max([r[2] for r in rows]) / o[0])}
    if not (MCAP_LO <= mcap0 <= MCAP_HI):
        return res | {"real": False}
    res["real"] = True
    # DATA GLITCH: a pool whose price jumps 50x+ inside its first hour and sits there on
    # dust volume (one showed a $160M "market value" one minute after a $47k open) is an
    # indexing error, not a trade anyone got. Flagged and excluded from every table.
    h = np.array([r[2] for r in rows])
    first_hr = t <= t[0] + 3600
    res["glitch"] = bool(h[first_hr].max() > 50 * o[0])
    now = time.time()
    for en in ENTRIES:
        te = t[0] + 60 * en
        k = np.searchsorted(t, te, side="right") - 1
        e = c[k]                                 # last trade at or before entry time
        for xn, xm in EXITS.items():
            tx = te + 60 * xm
            if tx > now - 120:
                continue                         # not enough time has passed yet
            j = np.searchsorted(t, tx, side="right") - 1
            x = c[j]
            r = x / e - 1
            res[f"e{en}_{xn}"] = -1.0 if x < 0.05 * e else float(r)
    # WAIT FOR PROOF: buy only coins still worth at least their graduation price after
    # `wait`, then hold. The patient version of the same bet.
    for wait, holds in ((60, (360, 720)), (360, (720,))):
        tw = t[0] + 60 * wait
        if tw > now - 120:
            continue
        k = np.searchsorted(t, tw, side="right") - 1
        e = c[k]
        alive = (e >= o[0]) and (t[-1] >= tw - 1800)   # above opening AND still trading
        res[f"alive_{wait}"] = bool(alive)
        if not alive:
            continue
        for hm in holds:
            tx = tw + 60 * hm
            if tx > now - 120:
                continue
            j = np.searchsorted(t, tx, side="right") - 1
            x = c[j]
            res[f"w{wait}_h{hm}"] = -1.0 if x < 0.05 * e else float(x / e - 1)
    return res


def boot_ci(x, reps=5000):
    rng = np.random.default_rng(1)
    m = rng.choice(x, size=(reps, len(x))).mean(1)
    return np.percentile(m, [2.5, 97.5])


def main():
    g = graduates()
    print(f"pump.fun lists {len(g)} graduated coins, "
          f"{pd.to_datetime(min(c['created_timestamp'] for c in g), unit='ms'):%m-%d %H:%M} .. "
          f"{pd.to_datetime(max(c['created_timestamp'] for c in g), unit='ms'):%m-%d %H:%M} "
          f"UTC (created)", flush=True)
    # RANDOM order: if the run is cut short, what has been fetched is still an unbiased
    # sample of the day's graduates rather than the newest (or oldest) slice of it
    g = list(g)
    np.random.default_rng(0).shuffle(g)
    only_cached = "--cached" in sys.argv
    res = []
    for k, c in enumerate(g):
        pool = c.get("pump_swap_pool") or c.get("pool_address")
        if not pool:
            continue
        if only_cached and not (OUT / "ohlcv" / f"{pool}.json").exists():
            continue
        try:
            r = outcome(candles(pool))
        except Throttled:
            time.sleep(60)
            continue
        except Exception:
            r = None
        if r:
            res.append(r | {"mint": c["mint"], "symbol": c.get("symbol")})
        if (k + 1) % 100 == 0:
            print(f"  {k + 1}/{len(g)} pools fetched", flush=True)
    R = pd.DataFrame(res)
    R.to_pickle(OUT / "grad_outcomes.pkl")
    real = R[R.real]
    print(f"\n{len(R)} pools with candles; {len(real)} REAL graduations (opening market "
          f"value ${MCAP_LO/1e3:.0f}k-${MCAP_HI/1e3:.0f}k); {len(R) - len(real)} filtered")
    print(f"  opening market value, median ${real.mcap0.median():,.0f}")
    print(f"  best price ever reached vs opening: median {real.peak_x.median():.2f}x, "
          f"{(real.peak_x >= 2).mean()*100:.0f}% ever doubled, "
          f"{(real.peak_x >= 10).mean()*100:.1f}% ever 10x")
    print(f"\nBUY EVERY REAL GRADUATION, equal money each. Net of {COST*100:.0f}% "
          f"[{STRESS*100:.0f}% stress]")
    print(f"  {'entry':<9}{'exit':<6}{'n':>5}{'mean':>9}{'stress':>8}{'95% CI of mean':>20}"
          f"{'median':>9}{'win':>6}{'lost>90%':>9}{'top1% share':>12}")
    for en in ENTRIES:
        for xn in EXITS:
            k = f"e{en}_{xn}"
            if k not in real:
                continue
            x = real[k].dropna().to_numpy()
            if len(x) < 30:
                continue
            net = x - COST
            lo, hi = boot_ci(net)
            top = np.sort(net)[::-1][:max(1, len(net) // 100)]
            share = top.sum() / net[net > 0].sum() * 100 if (net > 0).any() else 0
            print(f"  +{en:>2} min  {xn:<6}{len(x):>5}{net.mean()*100:>+8.1f}%"
                  f"{(x.mean()-STRESS)*100:>+7.1f}%   [{lo*100:+6.1f}%, {hi*100:+6.1f}%]"
                  f"{np.median(net)*100:>+8.1f}%{(net > 0).mean()*100:>5.0f}%"
                  f"{(x <= -0.9).mean()*100:>8.0f}%{share:>11.0f}%")
    print("\nWAIT FOR PROOF: buy only coins still above their graduation price, then hold")
    for wait, hold in ((60, 360), (60, 720), (360, 720)):
        a, k = f"alive_{wait}", f"w{wait}_h{hold}"
        if a not in real or k not in real:
            continue
        base = real[a].notna().sum()
        x = real[k].dropna().to_numpy()
        if len(x) < 10:
            print(f"  wait {wait//60}h: only {len(x)} survivors with a full hold - too few")
            continue
        net = x - COST
        lo, hi = boot_ci(net)
        print(f"  wait {wait//60}h, hold {hold//60}h: {len(x)} of {base} coins qualified "
              f"({len(x)/max(base,1)*100:.0f}%); mean {net.mean()*100:+.1f}% "
              f"[{lo*100:+.1f}%, {hi*100:+.1f}%], median {np.median(net)*100:+.1f}%, "
              f"win {(net > 0).mean()*100:.0f}%, lost>90% {(x <= -0.9).mean()*100:.0f}%")


if __name__ == "__main__":
    main()
