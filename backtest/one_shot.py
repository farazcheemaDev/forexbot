"""ONE TRADE AT HIGH LEVERAGE - what is the chance of good money, and do indicators and volume raise it?

THE USER'S QUESTION (2026-10-06)
    "if I sit one time and open a trade with high leverage there is a chance I can make good money by following
    indicators and volume and stuff."

THE BET, AS A TRADER WOULD PLACE IT
    One position, the whole stake as isolated margin, leverage L in {10, 20, 40}. Entry at the next 1m open after the
    signal. Exit at a profit of m x the stake (m = 1: double, 2: triple, 4: five times) or at LIQUIDATION, whichever
    the price reaches first; if neither within 3 days, closed at market.
      liquidation   price moves 1/L - 0.5% (maintenance) - 0.06% (the entry fee) against the entry
      target        price moves m/L + 0.12% (both fees) in favour
    A minute that touches both is read as liquidation. Binance USDT-M perp 1m bars, BTCUSDT and DOGEUSDT,
    2022-01 .. 2026-08, with volume and taker-buy volume (data.binance.vision, cached in
    strategy_analysis/data/min1/*_1m_vol.parquet). Split 60/40 by time.

    The fair-game benchmark: with no drift, P(target before liquidation) = liq / (liq + target).

THE ENTRIES
    random      30,000 random minutes per coin, each side
    oversold+vol   RSI14 < 25, volume > 3x its 60-min average, close in the bottom 10% of the 60-min range -> long;
                   mirror (RSI > 75, top 10%) -> short
    breakout+vol   close above the prior 60-min high with volume > 3x -> long; below the low -> short
    pullback       EMA200 > EMA1000 (1m) and RSI14 < 30 -> long; mirror -> short
    taker flow     last 15 min: taker-buy share of volume > 60%, volume > 2x, price up -> long; < 40%, down -> short
    btc confirms   DOGE only: oversold+vol or breakout+vol, AND BTC's last 15 min moved the same way
    A setup's signals are thinned to one per 60 minutes (one shot per event).

REGISTERED BEFORE THE RUN (2026-10-06)
    - Random, 40x: P(double before liquidation) ~42% (fair game 42.5%); P(5x) ~16%. Mean return on the stake
      -5% to -15% (the fees), at every leverage and target.
    - The setups: within ~4 points of random on the holdout; at most 1 of the 18 setup x side x coin lines beats
      random by > 4 points on BOTH halves (40x, double). Mean return on the stake negative for every setup.
    - Doc 02 already found volume anti-predictive in crypto (VSA, volume surge); expect nothing from it here.

RESULT (2026-10-06, logs/one_shot.txt, logs/one_shot.csv; holdout from 2024-10-19)
    - Random moment, 40x: P(double before liquidation) BTC 37-38%, DOGE 40-44% (fair game 42.5%); P(triple) 16-27%;
      P(5x) 4% (BTC) / 10% (DOGE) - under the fair 16% because a 10% move inside 3 days is rarer than a random walk
      with no cap would say. Average result on the stake -9% to -21% a shot. Predicted ~42% / ~16% / -5..-15%:
      right for double, too high for 5x, a little optimistic on the average.
    - 0 of 18 setup lines (40x, double) beat random by more than 4 points on both halves (predicted <= 1). The
      biggest gains are +1 to +1.6 points; the indicator+volume setups move the odds by about one point.
    - Every setup line has a negative average holdout result across leverage x target (100%). The single positive
      cell (20x, double, DOGE pullback short, +3%) is the best of 162 picked on the holdout itself.
    - At 10x a 3-day bet mostly expires before either side is reached (BTC: 5% double, the rest closed at market).
    Reading: one high-leverage shot is close to a fair coin flip with the fee taken out of every toss. Indicators
    and volume do not tilt it.

    --grid (logs/one_shot_grid.txt): with 30 days the odds sit on the fair-game line at every leverage from 20x;
    higher leverage = worse odds and a bigger average loss (10x -3%, 20x -7%, 40x -14%, 100x -44% of the stake a
    shot); 2-5x rarely moves far enough in 30 days. Splitting the stake changes the spread, never the average.
    Every registered prediction right.

    python -m backtest.one_shot
    python -m backtest.one_shot --grid     # every leverage 2-100x, targets, 3 vs 30 days, splitting the stake
"""
from __future__ import annotations

import io
import sys
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import odds_now as on  # noqa: E402
from backtest.metrics_fetch import BASE, get  # noqa: E402
from backtest.scalp_1m import DIR, MONTHS, ema  # noqa: E402

LOG = ROOT / "logs" / "one_shot.txt"
LEVS = (10, 20, 40)
MULTS = (1, 2, 4)
FEE = 0.0012
MAINT = 0.005
CAP = 3 * 1440
N_RANDOM = 30_000
THIN = 60


def one_month(sym, m):
    raw = get(f"{BASE}/data/futures/um/monthly/klines/{sym}/1m/{sym}-1m-{m}.zip")
    z = zipfile.ZipFile(io.BytesIO(raw))
    d = pd.read_csv(z.open(z.namelist()[0]), header=None, usecols=[0, 1, 2, 3, 4, 5, 9])
    d = d[pd.to_numeric(d[0], errors="coerce").notna()].astype(float)
    d.columns = ["t", "o", "h", "l", "c", "v", "tbv"]
    t = d["t"].to_numpy(np.int64)
    d["t"] = np.where(t > 10 ** 14, t // 1000, t)
    return d


def load(sym):
    f = DIR / f"{sym}_1m_vol.parquet"
    if f.exists():
        return pd.read_parquet(f)
    DIR.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(8) as ex:
        parts = list(ex.map(lambda m: one_month(sym, m), MONTHS))
    d = pd.concat(parts).drop_duplicates("t").sort_values("t", kind="stable").reset_index(drop=True)
    d.insert(0, "time", pd.to_datetime(d.pop("t"), unit="ms").astype("datetime64[ns]"))
    if len(d) < 0.9 * len(MONTHS) * 30 * 1440:
        raise SystemExit(f"{sym}: only {len(d):,} bars - incomplete download")
    d.to_parquet(f)
    return d


def levels():
    """(L, m) -> (liquidation distance, target distance) as fractions of the entry price."""
    return {(L, m): (1 / L - MAINT - FEE / 2, m / L + FEE) for L in LEVS for m in MULTS}


def shot(i, side, o, h, l, c, lv, cap=CAP):
    """Stake multiple for every (L, m) for one entry at signal bar i. 1+m on target, 0 on liquidation, else the
    position closed at the cap. Pessimistic: a minute touching both is liquidation."""
    a, b = i + 1, min(i + 1 + cap, len(c))
    e = o[a]
    up = np.maximum.accumulate(h[a:b]) / e - 1             # best move so far, non-decreasing
    dn = 1 - np.minimum.accumulate(l[a:b]) / e              # worst move so far, non-decreasing
    fav, adv = (up, dn) if side > 0 else (dn, up)
    last = side * (c[b - 1] / e - 1)
    out = {}
    for (L, m), (dl, dt) in lv.items():
        jl = np.searchsorted(adv, dl, side="left")          # first minute adverse >= dl
        jt = np.searchsorted(fav, dt, side="left")
        n = len(fav)
        if jl < n and jl <= jt:
            out[(L, m)] = 0.0
        elif jt < n:
            out[(L, m)] = 1.0 + m
        else:
            out[(L, m)] = max(0.0, 1 + L * last - L * FEE)
    return out


def thin(idx, gap=THIN):
    keep, nxt = [], -1
    for i in idx:
        if i >= nxt:
            keep.append(i)
            nxt = i + gap
    return np.array(keep, np.int64)


def setups(d, btc=None):
    o, h, l, c, v, tbv = (d[k].to_numpy(float) for k in ("o", "h", "l", "c", "v", "tbv"))
    rsi = on.features(o, h, l, c)["rsi"]
    vavg = pd.Series(v).rolling(60).mean().shift(1).to_numpy()
    spike3, spike2 = v > 3 * vavg, v > 2 * vavg
    hi60 = pd.Series(h).rolling(60).max().shift(1).to_numpy()
    lo60 = pd.Series(l).rolling(60).min().shift(1).to_numpy()
    rng_hi, rng_lo = pd.Series(h).rolling(60).max().to_numpy(), pd.Series(l).rolling(60).min().to_numpy()
    loc = (c - rng_lo) / (rng_hi - rng_lo)
    e200, e1000 = ema(c, 200), ema(c, 1000)
    v15 = pd.Series(v).rolling(15).sum().to_numpy()
    share = pd.Series(tbv).rolling(15).sum().to_numpy() / v15
    v15avg = pd.Series(v).rolling(240).mean().shift(15).to_numpy() * 15
    r15 = c / np.r_[np.full(15, np.nan), c[:-15]] - 1
    s = {
        "oversold+vol": ((rsi < 25) & spike3 & (loc < 0.1), (rsi > 75) & spike3 & (loc > 0.9)),
        "breakout+vol": ((c > hi60) & spike3, (c < lo60) & spike3),
        "pullback": ((e200 > e1000) & (rsi < 30), (e200 < e1000) & (rsi > 70)),
        "taker flow": ((share > 0.6) & (v15 > 2 * v15avg) & (r15 > 0), (share < 0.4) & (v15 > 2 * v15avg) & (r15 < 0)),
    }
    if btc is not None:
        b15 = btc / np.r_[np.full(15, np.nan), btc[:-15]] - 1
        s["btc confirms"] = ((s["oversold+vol"][0] | s["breakout+vol"][0]) & (b15 > 0),
                             (s["oversold+vol"][1] | s["breakout+vol"][1]) & (b15 < 0))
    return s


def summarise(res, tune):
    """res: (n, LEVS x MULTS) stake multiples. Per (L, m): P(target), mean stake multiple - overall and per half."""
    out = {}
    for j, key in enumerate(levels()):
        x = res[:, j]
        m = key[1]
        out[key] = dict(p=(x == 1 + m).mean(), ev=x.mean() - 1, p_t=(x[tune] == 1 + m).mean(),
                        p_h=(x[~tune] == 1 + m).mean(), ev_h=x[~tune].mean() - 1, n=len(x), n_h=int((~tune).sum()))
    return out


def main():
    t0 = time.time()
    lv = levels()
    keys = list(lv)
    data = {s: load(s) for s in ("BTCUSDT", "DOGEUSDT")}
    print(f"  data ready ({time.time() - t0:.0f}s)", flush=True)
    btc_c = pd.Series(data["BTCUSDT"].c.to_numpy(float), index=data["BTCUSDT"].time)
    split = np.sort(data["BTCUSDT"].time.to_numpy())[int(len(data["BTCUSDT"]) * 0.6)]
    lines = [f"backtest/one_shot.py, {pd.Timestamp.now():%Y-%m-%d %H:%M}; holdout from {pd.Timestamp(split):%Y-%m-%d}",
             "", "Fair-game odds (no drift): P(target before liquidation) = liq / (liq + target)"]
    for (L, m), (dl, dt) in lv.items():
        lines.append(f"  {L:>2}x, stake x{1 + m}: liquidation {dl:.2%} away, target {dt:.2%} away -> {dl / (dl + dt):.1%}")
    table = []
    for coin, d in data.items():
        o, h, l, c = (d[k].to_numpy(float) for k in "ohlc")
        times = d.time.to_numpy()
        n = len(d)
        last_ok = n - CAP - 2
        rng = np.random.default_rng(7 if coin == "BTCUSDT" else 8)
        S = setups(d, btc_c.reindex(d.time).to_numpy(float) if coin == "DOGEUSDT" else None)
        rand = np.sort(rng.choice(np.arange(1500, last_ok), N_RANDOM, replace=False))
        groups = [("random", "long", rand), ("random", "short", rand)]
        for nm, (lg, sh) in S.items():
            for side, sig in (("long", lg), ("short", sh)):
                idx = np.flatnonzero(np.nan_to_num(sig).astype(bool))
                idx = thin(idx[(idx > 1500) & (idx < last_ok)])
                groups.append((nm, side, idx))
        for nm, side, idx in groups:
            sgn = 1 if side == "long" else -1
            res = np.array([[r[k] for k in keys] for r in (shot(i, sgn, o, h, l, c, lv) for i in idx)])
            if len(res) == 0:
                continue
            tune = times[idx] < split
            for (L, m), sm in summarise(res, tune).items():
                table.append(dict(coin=coin, setup=nm, side=side, L=L, m=m, **sm))
        print(f"  {coin} done ({time.time() - t0:.0f}s)", flush=True)
    T = pd.DataFrame(table)
    T.to_csv(ROOT / "logs" / "one_shot.csv", index=False)

    lines.append("\nRANDOM MOMENT - P(target before liquidation) | average result on the stake (all / holdout):")
    for (coin, side), g in T[T.setup == "random"].groupby(["coin", "side"], sort=False):
        cells = "  ".join(f"{r.L}x x{1 + r.m}: {r.p:.1%} | {r.ev:+.0%}" for r in g.itertuples())
        lines.append(f"  {coin:8} {side:5} {cells}")
    lines.append("\nSETUPS vs RANDOM at 40x, target = DOUBLE the stake (tune / holdout P, then holdout average result):")
    base = T[(T.setup == "random") & (T.L == 40) & (T.m == 1)].set_index(["coin", "side"])
    beats = 0
    for r in T[(T.setup != "random") & (T.L == 40) & (T.m == 1)].itertuples():
        b = base.loc[(r.coin, r.side)]
        dt_, dh_ = r.p_t - b.p_t, r.p_h - b.p_h
        flag = dt_ > 0.04 and dh_ > 0.04
        beats += flag
        lines.append(f"  {r.coin:8} {r.setup:13} {r.side:5} n {r.n:>5}: P(double) {r.p_t:.1%} / {r.p_h:.1%} vs random "
                     f"{b.p_t:.1%} / {b.p_h:.1%} ({dt_:+.1%} / {dh_:+.1%}){'  <- beats by >4pts both halves' if flag else ''}"
                     f"; holdout avg on stake {r.ev_h:+.0%}")
    n_lines = len(T[(T.setup != "random") & (T.L == 40) & (T.m == 1)])
    lines.append(f"\n  {beats} of {n_lines} setup lines beat random by more than 4 points on both halves")
    lines.append("\nBEST SETUP LINE PER TARGET (holdout), any leverage - P(target) and average result on the stake:")
    for (L, m), g in T[T.setup != "random"].groupby(["L", "m"]):
        r = g.sort_values("p_h", ascending=False).iloc[0]
        b = T[(T.setup == "random") & (T.coin == r.coin) & (T.side == r.side) & (T.L == L) & (T.m == m)].iloc[0]
        lines.append(f"  {L:>2}x x{1 + m}: {r.coin} {r.setup} {r.side}: {r.p_h:.1%} (random {b.p_h:.1%}), "
                     f"avg on stake {r.ev_h:+.0%}, n {r.n_h}")
    neg = (T[T.setup != "random"].groupby(["coin", "setup", "side"]).ev_h.mean() < 0).mean()
    lines.append(f"\n  share of setup lines with a NEGATIVE average holdout result (mean over L x target): {neg:.0%}")
    txt = "\n".join(lines)
    print(txt)
    LOG.write_text(txt + "\n")
    print(f"\n-> {LOG} ({time.time() - t0:.0f}s)")


GRID_LEVS = (2, 3, 5, 10, 20, 30, 40, 50, 75, 100)
GRID_MULTS = (0.5, 1, 2, 4)
HORIZONS = {"3 days": 3 * 1440, "30 days": 30 * 1440}
N_GRID = 6000
SPLITS = (1, 2, 4, 10)


def grid():
    """Every leverage x target x horizon from random moments (setups moved the odds ~1 point in main(), so they are
    left out), and what splitting the stake into k equal shots does.

    Registered before running (2026-10-06): for the same target, HIGHER leverage gives WORSE odds - maintenance and
    fees are a bigger share of a smaller distance. Fair-game P(double): 2x ~49.6%, 40x 42.5%, 100x ~28%. Average
    result on the stake gets more negative with leverage (roughly -L x 0.12% plus the maintenance gap). Splitting the
    stake into k shots leaves the average unchanged and narrows the spread: P(at least double the total) falls,
    P(lose everything) falls."""
    t0 = time.time()
    lv = {(L, m): (1 / L - MAINT - FEE / 2, m / L + FEE) for L in GRID_LEVS for m in GRID_MULTS}
    keys = list(lv)
    lines = [f"backtest/one_shot.py --grid, {pd.Timestamp.now():%Y-%m-%d %H:%M}; random moments 2022-01 .. 2026-08, "
             f"{N_GRID:,} per coin, long and short averaged; liquidation = 1/L - 0.5% - 0.06%", ""]
    outcomes = {}
    for coin in ("BTCUSDT", "DOGEUSDT"):
        d = load(coin)
        o, h, l, c = (d[k].to_numpy(float) for k in "ohlc")
        for hz, cap in HORIZONS.items():
            rng = np.random.default_rng(11)
            idx = np.sort(rng.choice(np.arange(1500, len(c) - cap - 2), N_GRID, replace=False))
            res = np.array([[r[k] for k in keys] for side in (1, -1)
                            for r in (shot(i, side, o, h, l, c, lv, cap) for i in idx)])
            outcomes[(coin, hz)] = res
            lines.append(f"{coin}, held up to {hz}:")
            lines.append(f"  {'lev':>4} | {'lose all':>8} | {'+50%':>6} | {'double':>6} {'(fair)':>7} | {'triple':>6} | "
                         f"{'5x':>5} | {'avg result, aiming to double':>28} | {'expired':>7}")
            for L in GRID_LEVS:
                col = {m: res[:, keys.index((L, m))] for m in GRID_MULTS}
                dl, dt = lv[(L, 1)]
                x2 = col[1]
                lines.append(f"  {L:>3}x | {np.mean(x2 == 0):>8.1%} | {np.mean(col[0.5] == 1.5):>6.1%} | "
                             f"{np.mean(x2 == 2):>6.1%} {dl / (dl + dt):>7.1%} | {np.mean(col[2] == 3):>6.1%} | "
                             f"{np.mean(col[4] == 5):>5.1%} | {x2.mean() - 1:>+28.1%} | "
                             f"{np.mean((x2 != 0) & (x2 != 2)):>7.1%}")
            lines.append("")
        print(f"  {coin} done ({time.time() - t0:.0f}s)", flush=True)

    lines.append("SPLITTING THE STAKE into k equal shots, one after another, each aiming to double (drawn from the "
                 "measured outcomes above, 20,000 draws):")
    rng = np.random.default_rng(5)
    for coin, hz, L in (("BTCUSDT", "3 days", 40), ("DOGEUSDT", "3 days", 40), ("BTCUSDT", "30 days", 10),
                        ("DOGEUSDT", "30 days", 10), ("DOGEUSDT", "3 days", 100)):
        x = outcomes[(coin, hz)][:, keys.index((L, 1))]
        cells = []
        for k in SPLITS:
            tot = rng.choice(x, size=(20000, k)).mean(1)          # final / starting stake
            cells.append(f"k={k}: lose all {np.mean(tot == 0):.0%}, end below start {np.mean(tot < 1):.0%}, "
                         f"at least double {np.mean(tot >= 2):.0%}, average {tot.mean() - 1:+.0%}")
        lines.append(f"  {coin} {L}x {hz}:  " + " | ".join(cells))
    txt = "\n".join(lines)
    print(txt)
    (ROOT / "logs" / "one_shot_grid.txt").write_text(txt + "\n")
    print(f"\n-> logs/one_shot_grid.txt ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    grid() if "--grid" in sys.argv else main()
