"""RSI ONLY, THE WAY PEOPLE TRADE IT - why "I used to make money with just RSI" and the backtests disagree.

THE USER (2026-10-08): "you are missing something ... it can't be possible, I used to make more even only using RSI."
Every earlier test here used a 2xATR stop. The common retail RSI trade has NO stop: buy the RSI dip, take a small
profit or sell when RSI recovers. That wins most trades - so it feels like it works - and loses rarely but big. This
measures exactly that, with the win rate, the average, the worst trade and the YEAR beside each other.

THE RULES (RSI 14, Wilder; Binance USDT-M perp bars; BTC ETH SOL DOGE XRP; 2020-09 .. 2026-08)
    Timeframes 15m (strategy_analysis/data/min15), 1h and 4h (resampled from the 15m bars).
    LONG: RSI crosses DOWN through L (L = 30 or 25) at a bar's close -> buy at the next open.
    SHORT (mirror): RSI crosses UP through 100 - L -> sell at the next open.
    Exits (first one hit):
      rsi50     RSI back through 50 at a close -> out at the next open
      rsi70     RSI back through 70 (short: 30) at a close -> out at the next open
      tp1       take profit +1% (a limit at the price), NO stop
      tp2       take profit +2%, NO stop
      tp2_sl4   take profit +2%, stop -4% (a minute bar touching both reads as the stop; a gap fills at the open)
    Every trade closes at market 7 days after entry if nothing else hit. One trade at a time per coin.
    Costs: 12bp round trip and every funding settlement held. Worst drawdown inside each trade recorded (for
    liquidation at leverage L: the drawdown reaches 1/L - 0.5% - 0.06%).
    Years 2020-09..12 / 2021 / 2022 / 2023 / 2024 / 2025-26; 10,000 PKR at 1/3/5/10x, the whole margin each trade.

REGISTERED BEFORE THE RUN (2026-10-08)
    - The no-stop exits (tp1, tp2, rsi50) win 70-90% of trades on every coin and timeframe.
    - Their average net trade on 2024-04 .. is about zero or negative.
    - Longs make their money in 2021 and 2024 and give it back in 2022.
    - Worst single long trade -20% to -60% on the alts without a stop.
    - At 5x and above the no-stop versions are liquidated, in 2022 and on 2025-10-10.

RESULT (2026-10-08, logs/rsi_only.txt, logs/rsi_only_trades.csv)
    - No-stop RSI longs win 76-95% of trades on every timeframe (predicted 70-90%: right, a little higher).
    - The classic long (cross under 30, +2%, no stop), all coins and timeframes, by year: 2020 +145% (sum of trade
      returns), 2021 +558%, 2022 -737%, 2023 +421%, 2024 -24%, 2025-26 -639%. Win rate 78-90% in EVERY year,
      including the losing ones. Predicted "money in 2021 and 2024, given back in 2022": 2021/2022 right, 2024 wrong
      (flat), 2023 not predicted (+421%), 2025-26 the biggest loss.
    - Since 2024-04-07, 10,000 PKR all-in on that classic rule: 1x ends 2,019-8,851 on 14 of 15 coin x timeframe cells
      (XRP 4h 14,615); 3x is wiped on 12 of 15; 5x and 10x on all 15 (predicted: right). Worst long trade -17% to
      -55%, deepest dip inside a trade up to 68% (DOGE 15m).
    - Shorts without a stop are destroyed (worst trades past -100%: liquidation). With the 4% stop every variant is
      negative in nearly every year.
    - One recent exception, found among 60 variants (so selection-prone): 4h longs at RSI < 25 averaged +0.2 to +1.5%
      a trade since 2024-04 (~60-80 trades pooled over 5 coins).
    Reading: the user's experience is real - dip-buying RSI with a small target and no stop made money in 2020, 2021
    and 2023 while winning ~90% of trades. The same rule lost in 2022 and 2025-26 while STILL winning ~80% of trades.
    The win rate never warns you; the year decides.

    python -m backtest.rsi_only
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import odds_now as on  # noqa: E402
from backtest import scalp_15m as s15  # noqa: E402

LOG = ROOT / "logs" / "rsi_only.txt"
COINS = s15.COINS
TFS = {"15m": 1, "1h": 4, "4h": 16}                 # 15m bars per bar
LEVELS = (30, 25)
EXITS = ("rsi50", "rsi70", "tp1", "tp2", "tp2_sl4")
FEE = 0.0012
MAINT = 0.005
LEVS = (1, 3, 5, 10)
STAKE = 10_000.0
YEARS = (("2020", "2020-09-01", "2021-01-01"), ("2021", "2021-01-01", "2022-01-01"), ("2022", "2022-01-01", "2023-01-01"),
         ("2023", "2023-01-01", "2024-01-01"), ("2024", "2024-01-01", "2025-01-01"), ("2025-26", "2025-01-01", "2027-01-01"))
HOLDOUT = pd.Timestamp("2024-04-07")                # scalp_15m's split, for the "recent" column


def bars(sym, k):
    d = s15.load(sym)
    if k == 1:
        return d.reset_index(drop=True)
    g = d.set_index("time").resample(f"{15 * k}min")
    out = pd.DataFrame({"o": g["o"].first(), "h": g["h"].max(), "l": g["l"].min(), "c": g["c"].last(),
                        "n": g["c"].count()})
    return out[out.n == k].drop(columns="n").reset_index()


def rsi14(c):
    d = np.r_[0.0, np.diff(c)]
    up = pd.Series(np.where(d > 0, d, 0.0)).ewm(alpha=1 / 14, adjust=False).mean().to_numpy()
    dn = pd.Series(np.where(d < 0, -d, 0.0)).ewm(alpha=1 / 14, adjust=False).mean().to_numpy()
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(dn > 0, 100 - 100 / (1 + up / dn), 100.0)


def trade(i, side, ex, o, h, l, c, r, fc, cap, lvl):
    """One trade from signal bar i. Returns (exit bar index j - the bar whose open or intrabar price closes it -,
    net return, worst drawdown inside the trade). side +1 long, -1 short."""
    n = len(c)
    e = o[i + 1]
    tp = {"tp1": 0.01, "tp2": 0.02, "tp2_sl4": 0.02}.get(ex)
    sl = 0.04 if ex == "tp2_sl4" else None
    lvl_out = {"rsi50": 50.0, "rsi70": 70.0 if side > 0 else 30.0}.get(ex)
    worst = 0.0
    j_end = min(i + 1 + cap, n - 2)
    for j in range(i + 1, j_end + 1):
        adv = (1 - l[j] / e) if side > 0 else (h[j] / e - 1)
        fav_hit = tp is not None and ((h[j] >= e * (1 + tp)) if side > 0 else (l[j] <= e * (1 - tp)))
        sl_hit = sl is not None and adv >= sl
        if sl_hit:
            fill = min(o[j], e * (1 - sl)) if side > 0 else max(o[j], e * (1 + sl))
            worst = max(worst, adv)
            return j, side * (fill / e - 1) - FEE - side * (fc[j] - fc[i + 1]) / e, worst
        worst = max(worst, adv)
        if fav_hit:
            return j, tp - FEE - side * (fc[j] - fc[i + 1]) / e, worst
        if lvl_out is not None and ((r[j] >= lvl_out) if side > 0 else (r[j] <= lvl_out)):
            x = o[j + 1]
            return j + 1, side * (x / e - 1) - FEE - side * (fc[j + 1] - fc[i + 1]) / e, worst
    x = c[j_end]
    return j_end, side * (x / e - 1) - FEE - side * (fc[j_end] - fc[i + 1]) / e, worst


def run(d, fc, side, L, ex, cap):
    o, h, l, c = (d[k].to_numpy(float) for k in "ohlc")
    r = rsi14(c)
    lv = L if side > 0 else 100 - L
    sig = (np.r_[False, (r[:-1] >= lv) & (r[1:] < lv)] if side > 0 else np.r_[False, (r[:-1] <= lv) & (r[1:] > lv)])
    sig[:100] = False
    t = d.time.to_numpy()
    out, free = [], 0
    for i in np.flatnonzero(sig):
        if i < free or i + 2 >= len(c):
            continue
        j, net, worst = trade(i, side, ex, o, h, l, c, r, fc, cap, L)
        out.append((t[i + 1], net, worst))
        free = j + 1
    return pd.DataFrame(out, columns=["t", "net", "worst"])


def play(net, worst, lev):
    liq = 1 / lev - MAINT - FEE / 2
    eq = STAKE
    for x, w in zip(net, worst):
        eq = 0.0 if w >= liq else eq * max(0.0, 1 + lev * x)
        if eq <= 0:
            break
    return eq


def main():
    t0 = time.time()
    lines = [f"backtest/rsi_only.py, {pd.Timestamp.now():%Y-%m-%d %H:%M}; RSI(14) cross under 30 / 25 (shorts: over 70 / "
             f"75), next-open entry, 12bp + funding, one trade at a time per coin, 7-day cap", ""]
    rows = []
    for tf, k in TFS.items():
        cap = 7 * 96 // k
        for sym in COINS:
            d = bars(sym, k)
            fc = on.fund_by_bar(sym, d.time, d.o.to_numpy(float))
            for side in (1, -1):
                for L in LEVELS:
                    for ex in EXITS:
                        T = run(d, fc, side, L, ex, cap)
                        if len(T) == 0:
                            continue
                        T = T.assign(tf=tf, coin=sym, side="long" if side > 0 else "short", L=L, exit=ex)
                        rows.append(T)
        print(f"  {tf} done ({time.time() - t0:.0f}s)", flush=True)
    A = pd.concat(rows, ignore_index=True)
    A["t"] = pd.to_datetime(A["t"])
    A.to_csv(ROOT / "logs" / "rsi_only_trades.csv", index=False)

    lines.append("1. EVERY VARIANT, pooled over the 5 coins: win rate | average net per trade | worst trade | average per "
                 "trade by year | since 2024-04-07")
    hdr = "  ".join(f"{y:>7}" for y, _, _ in YEARS)
    lines.append(f"  {'tf':>3} {'side':>5} {'RSI':>3} {'exit':>8} {'trades':>7} {'win':>5} {'avg':>7} {'worst':>7} | {hdr} | recent")
    for (tf, side, L, ex), g in A.groupby(["tf", "side", "L", "exit"], sort=False):
        yrs = "  ".join(f"{g[(g.t >= a) & (g.t < b)].net.mean() * 100:>+6.2f}%" if ((g.t >= a) & (g.t < b)).any() else
                        f"{'-':>7}" for _, a, b in YEARS)
        rec = g[g.t >= HOLDOUT].net
        lines.append(f"  {tf:>3} {side:>5} {L:>3} {ex:>8} {len(g):>7} {np.mean(g.net > 0):>5.0%} {g.net.mean() * 100:>+6.2f}% "
                     f"{g.net.min() * 100:>+6.1f}% | {yrs} | {rec.mean() * 100:+.2f}%")
    lines.append("\n2. THE CLASSIC 'buy RSI < 30, take +2%, no stop', per coin, since 2024-04-07, 10,000 PKR all-in:")
    for tf in TFS:
        for sym in COINS:
            g = A[(A.tf == tf) & (A.coin == sym) & (A.side == "long") & (A.L == 30) & (A.exit == "tp2") & (A.t >= HOLDOUT)]
            if g.empty:
                continue
            cells = " | ".join(f"{lev}x {play(g.net.to_numpy(), g.worst.to_numpy(), lev):>10,.0f}" for lev in LEVS)
            lines.append(f"  {tf:>3} {sym:9} {len(g):>4} trades, win {np.mean(g.net > 0):.0%}, avg {g.net.mean() * 100:+.2f}%, "
                         f"worst {g.net.min() * 100:+.1f}%, deepest dip inside a trade {g.worst.max() * 100:.0f}% -> {cells}")
    lines.append("\n3. WHEN THE CLASSIC RSI LONG (L 30, tp2, no stop) MADE ITS MONEY, all coins and timeframes:")
    g = A[(A.side == "long") & (A.L == 30) & (A.exit == "tp2")]
    for y, a, b in YEARS:
        x = g[(g.t >= a) & (g.t < b)]
        lines.append(f"  {y:>7}: {len(x):>5} trades, win {np.mean(x.net > 0):.0%}, sum of trade returns {x.net.sum() * 100:+8.1f}% "
                     f"(average {x.net.mean() * 100:+.2f}%), worst {x.net.min() * 100:+.1f}%")
    txt = "\n".join(lines)
    print(txt)
    LOG.write_text(txt + "\n")
    print(f"\n-> {LOG} ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
