"""HIS 26 CLEAN TRADES, DRAWN THE WAY HE SAW THEM - to be looked at by eye, trade by trade.

The user, 2026-09-26: "you are not looking correctly". §25-33 measured his moments against the moments around
them with features and models. This draws each clean trade (April on) as a chart a 1-minute trader reads:
  - on HIS BROKER'S price scale: his fills give the exact offset of his quotes from USTECm's mid on that day
    (the median over the day's trades of the average of entry-minus-mid and exit-minus-mid, which cancels his
    spread), so round numbers sit where he saw them;
  - top: 5-minute candles from 09:30 ET to 30 minutes after his entry;
  - bottom: 1-minute candles from 45 minutes before to 12 minutes after, rebuilt from ticks;
  - levels: yesterday's high / low / close, today's 09:30 open, the first-15-minute range, the day's high and
    low AT his click, and round 25 / 50 / 100 levels on his scale;
  - his entry (triangle, at his fill price and second) and exit (x).
Output: logs/his_look/NN.png. Nothing is computed or claimed here.

    python -m backtest.his_look
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.his_ta import candles  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
TICKS = ROOT / "strategy_analysis" / "data" / "ustec_tick_days.pkl"
OUT = ROOT / "logs" / "his_look"
GMT = 5.0


def at(ts, mid, t):
    return mid[max(np.searchsorted(ts, t, side="right") - 1, 0)]


def draw(ax, xs, B, lo, hi, w):
    for i in range(lo, hi):
        if i < 0 or i >= len(B["c"]):
            continue
        o, h, l, c = B["o"][i], B["h"][i], B["l"][i], B["c"][i]
        col = "#2a9d3a" if c >= o else "#d33"
        ax.vlines(xs(i), l, h, color=col, lw=0.8)
        ax.add_patch(plt.Rectangle((xs(i) - w / 2, min(o, c)), w, max(abs(c - o), 0.05), color=col))


def levels(ax, lv, x0, x1, ylo, yhi):
    for name, (y, st) in lv.items():
        if ylo <= y <= yhi:
            ax.hlines(y, x0, x1, colors=st[0], linestyles=st[1], lw=st[2])
            ax.text(x1, y, " " + name, va="center", fontsize=7, color=st[0])
    for step, lw, al in ((100, 1.0, 0.6), (50, 0.7, 0.45), (25, 0.5, 0.3)):
        for y in np.arange(np.ceil(ylo / step) * step, yhi, step):
            if step == 25 and y % 50 == 0 or step == 50 and y % 100 == 0:
                continue
            ax.hlines(y, x0, x1, colors="grey", linestyles=":", lw=lw, alpha=al)
            ax.text(x0, y, f"{y:.0f} ", va="center", ha="right", fontsize=6, color="grey")


def main():
    cache = pickle.loads(TICKS.read_bytes())
    tdays = sorted(d for d in cache if cache[d] is not None)
    x = pd.read_csv(ROOT / "strategy_analysis" / "statement_trades.csv", parse_dates=["open_time", "close_time"])
    x = x[x.symbol.str.startswith("NASDAQ")].copy()
    for c in ("open_time", "close_time"):
        x[c[:-5]] = (x[c] - pd.Timedelta(hours=GMT)).dt.tz_localize("UTC").dt.tz_convert("America/New_York").dt.tz_localize(None)
    x = x[x.open_time - pd.Timedelta(hours=GMT) >= "2026-04-01"].sort_values("open", kind="stable")
    x["d"] = x.open.dt.normalize()
    x["t"] = (x.open - x.d - pd.Timedelta(hours=9, minutes=30)).dt.total_seconds()
    x["tc"] = (x.close - x.d - pd.Timedelta(hours=9, minutes=30)).dt.total_seconds()
    x = x[x.d.isin(tdays) & (x.t > 0)]
    b = {}
    for d, g in x.groupby("d"):
        ts, mid, _ = cache[d]
        b[d] = np.median([((r.open_price - at(ts, mid, r.t)) + (r.close_price - at(ts, mid, r.tc))) / 2 for r in g.itertuples()])
    OUT.mkdir(parents=True, exist_ok=True)
    for n, r in enumerate(x.itertuples(), 1):
        ts, mid, _ = cache[r.d]
        bb = b[r.d]
        m = mid + bb
        B1, B5 = candles(ts, m, 60), candles(ts, m, 300)
        prev = [d for d in tdays if d < r.d]
        lv = {}
        if prev:
            pts, pm, _ = cache[prev[-1]]
            k = pts < 23400
            if k.any():
                lv.update(PDH=(pm[k].max() + bb, ("purple", "-", 1.2)), PDL=(pm[k].min() + bb, ("purple", "-", 1.2)),
                          PDC=(pm[k][-1] + bb, ("purple", "--", 0.9)))
        rth = ts < r.t
        lv["open"] = (m[0], ("black", "--", 0.9))
        o15 = ts < 900
        lv["OR15 H"], lv["OR15 L"] = (m[o15].max(), ("orange", "-", 1.0)), (m[o15].min(), ("orange", "-", 1.0))
        lv["HOD"], lv["LOD"] = (m[rth].max(), ("blue", "-.", 0.9)), (m[rth].min(), ("blue", "-.", 0.9))
        fig, (a1, a2) = plt.subplots(2, 1, figsize=(13, 10), gridspec_kw={"height_ratios": [1, 1.3]})
        k5 = int(r.t // 300)
        hi5 = min(len(B5["c"]), k5 + 7)
        draw(a1, lambda i: i, B5, 0, hi5, 0.6)
        seg = slice(0, hi5)
        y0, y1 = B5["l"][seg].min() - 10, B5["h"][seg].max() + 10
        levels(a1, lv, 0, hi5, y0, y1)
        a1.axvline(r.t / 300, color="k", lw=0.6, alpha=0.5)
        a1.set_ylim(y0, y1)
        a1.set_xticks(range(0, hi5, 6))
        a1.set_xticklabels([(pd.Timestamp("09:30") + pd.Timedelta(minutes=5 * i)).strftime("%H:%M") for i in range(0, hi5, 6)], fontsize=7)
        a1.set_title(f"#{n}  {r.open:%Y-%m-%d %H:%M:%S} ET  {r.side}  {(1 if r.side == 'BUY' else -1) * (r.close_price - r.open_price):+.2f} pts  "
                     f"${r.net:.2f}   (5-min, session to entry +30 min; his scale = USTECm mid {bb:+.2f})", fontsize=9)
        k1 = int(r.t // 60)
        lo1, hi1 = max(0, k1 - 45), min(len(B1["c"]), k1 + 13)
        draw(a2, lambda i: i - k1, B1, lo1, hi1, 0.6)
        y0, y1 = B1["l"][lo1:hi1].min() - 4, B1["h"][lo1:hi1].max() + 4
        levels(a2, lv, lo1 - k1, hi1 - k1, y0, y1)
        s = 1 if r.side == "BUY" else -1
        a2.plot((r.t - k1 * 60) / 60, r.open_price, marker="^" if s == 1 else "v", color="k", ms=11, zorder=5)
        a2.plot((r.tc - k1 * 60) / 60, r.close_price, marker="x", color="k", ms=10, mew=2, zorder=5)
        a2.set_ylim(y0, y1)
        a2.set_xlabel("minutes from his entry candle (0 = the candle he clicked in)", fontsize=8)
        a2.grid(axis="x", alpha=0.2)
        fig.tight_layout()
        fig.savefig(OUT / f"{n:02d}.png", dpi=80)
        plt.close(fig)
    print(f"{n} charts in {OUT}")


if __name__ == "__main__":
    main()
