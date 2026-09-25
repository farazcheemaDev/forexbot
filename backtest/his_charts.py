"""HIS NASDAQ TRADES, DRAWN ON THE REAL CHART - to be LOOKED AT, not measured.

The user, 2026-09-25: "don't you see the charts yourself by cross-checking dates and prices? Also,
other than charts he relies on news." his_strategy.md s15-22 aligned his 46 NASDAQ trades to USTECm
bars (GMT+5 confirmed) and MEASURED ten features against controls - nothing separated his entries.
Nobody drew the charts and read them. This does:
  - every NASDAQ trade in the statement, 1-minute bars where the file has them (2026-06 on),
    5-minute bars before that; window 90 minutes before his entry to 30 minutes after his exit;
  - his entry (triangle) and exit (x) at HIS fill prices, shifted by the futures-vs-CFD basis
    (the median of fill minus bar close over that contract month, so each mark sits where he was
    actually filled relative to the candle);
  - the US cash open (09:30 ET), the prior day's high and low, round 50-point levels, and tick
    volume underneath (news arrives as a volume burst).
Output: logs/his_charts_NN.png, six trades a page, in date order; nothing is computed or claimed here.

    python -m backtest.his_charts
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "strategy_analysis" / "data"
GMT = 5.0


def load(fname):
    d = pd.DataFrame(json.load(open(DATA / fname)))
    d["t"] = pd.to_datetime(d["t"], unit="ms")
    return d.set_index("t").sort_index()


def trades():
    x = pd.read_csv(ROOT / "strategy_analysis" / "statement_trades.csv", parse_dates=["open_time", "close_time"])
    x = x[x.symbol.str.startswith("NASDAQ")].copy()
    x["o_utc"] = x.open_time - pd.Timedelta(hours=GMT)
    x["c_utc"] = x.close_time - pd.Timedelta(hours=GMT)
    x["contract"] = x.symbol.str.split().str[1]
    x["pts"] = np.where(x.side == "BUY", x.close_price - x.open_price, x.open_price - x.close_price)
    return x.sort_values("o_utc").reset_index(drop=True)


def et(ts):
    """UTC -> New York time, DST-aware."""
    return pd.Timestamp(ts).tz_localize("UTC").tz_convert("America/New_York").tz_localize(None)


def main():
    m1, m5 = load("USTECm_1m_400d.json"), load("USTECm_5m_2400d.json")
    T = trades()
    # basis per contract: his fill minus the CFD close of the minute he filled in (5m bar if no 1m)
    bas = []
    for r in T.itertuples():
        src = m1 if r.o_utc >= m1.index[0] else m5
        i = src.index.searchsorted(r.o_utc, side="right") - 1
        bas.append(r.open_price - src.c.iloc[i] if i >= 0 else np.nan)
    T["basis"] = bas
    # PER TRADE, not per contract: a futures basis decays to zero at expiry (~200 pts in January for
    # the March contract), so one number per contract put the marks 100-200 pts off the candles. The
    # entry mark is pinned to the CFD close of his entry minute; the EXIT mark then shows whether his
    # points match what the chart did - a check on the timezone, not an assumption.
    T["basis_c"] = T["basis"]
    daily = m5.c.resample("D").agg(["max", "min"])
    per = 6
    for page in range(0, len(T), per):
        fig, axes = plt.subplots(per, 1, figsize=(14, 4.2 * per))
        for ax, r in zip(axes, T.iloc[page:page + per].itertuples()):
            src, tf = (m1, "1m") if r.o_utc >= m1.index[0] else (m5, "5m")
            a, b = r.o_utc - pd.Timedelta(minutes=90), r.c_utc + pd.Timedelta(minutes=30)
            g = src[(src.index >= a) & (src.index <= b)]
            if not len(g):
                ax.set_title(f"{r.o_utc:%Y-%m-%d} no bars"); continue
            x = np.arange(len(g))
            up = g.c >= g.o
            w = 0.6
            ax.vlines(x, g.l, g.h, color="#555", lw=0.6)
            ax.bar(x[up], (g.c - g.o)[up], w, g.o[up], color="#2a9d5c")
            ax.bar(x[~up], (g.c - g.o)[~up], w, g.o[~up], color="#d1495b")
            pos = lambda t: np.searchsorted(g.index.values, np.datetime64(t)) - 0.5  # noqa: E731
            ei, xi = pos(r.o_utc), pos(r.c_utc)
            e_px, x_px = r.open_price - r.basis_c, r.close_price - r.basis_c
            col = "#1f6feb" if r.side == "BUY" else "#b8860b"
            ax.plot([ei], [e_px], marker="^" if r.side == "BUY" else "v", ms=12, color=col, mec="k", zorder=5)
            ax.plot([xi], [x_px], marker="X", ms=10, color=col, mec="k", zorder=5)
            day = g.index[0].normalize() - pd.Timedelta(days=1)
            while day not in daily.index or not np.isfinite(daily.loc[day, "max"]):
                day -= pd.Timedelta(days=1)
                if day < daily.index[0]:
                    break
            if day in daily.index:
                for v, lab in ((daily.loc[day, "max"], "prior-day high"), (daily.loc[day, "min"], "prior-day low")):
                    if g.l.min() - 30 < v < g.h.max() + 30:
                        ax.axhline(v, color="purple", ls=":", lw=1); ax.text(0, v, lab, fontsize=7, color="purple")
            for lvl in np.arange(np.floor(g.l.min() / 50) * 50, g.h.max() + 50, 50):
                if g.l.min() - 5 < lvl < g.h.max() + 5:
                    ax.axhline(lvl, color="#bbb", lw=0.5)
            for k, t in enumerate(g.index):
                e = et(t)
                if e.hour == 9 and e.minute == 30:
                    ax.axvline(k, color="k", ls="--", lw=0.8); ax.text(k, g.h.max(), " 09:30 ET open", fontsize=7)
            vx = ax.twinx()
            vx.bar(x, g.v, 0.8, color="#999", alpha=0.25)
            vx.set_ylim(0, g.v.max() * 4); vx.set_yticks([])
            ticks = x[:: max(len(x) // 10, 1)]
            ax.set_xticks(ticks); ax.set_xticklabels([f"{et(g.index[k]):%H:%M}" for k in ticks], fontsize=7)
            ax.set_title(f"#{r.Index + 1}  {et(r.o_utc):%a %Y-%m-%d %H:%M:%S} ET  {r.side} {r.lots} lots  "
                         f"{r.pts:+.2f} pts in {(r.c_utc - r.o_utc).total_seconds() / 60:.1f} min  "
                         f"net ${r.net:+.2f}   [{tf} bars, basis {r.basis_c:+.1f}]", fontsize=9)
        fig.tight_layout()
        out = ROOT / "logs" / f"his_charts_{page // per + 1:02d}.png"
        fig.savefig(out, dpi=70); plt.close(fig)
        print("wrote", out.relative_to(ROOT))


if __name__ == "__main__":
    main()
