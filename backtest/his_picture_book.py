"""HIS NASDAQ TRADES ON THE 1-MINUTE CHART, AS HIS SCREEN SHOWED THEM - a picture book to LOOK at (2026-11-22)

THE USER (2026-11-22): "yes make the picture book" -> "you will notice yourself, not me". his_alt_charts.py showed he reads a plain
1-MINUTE chart and clicks about 14 s after a candle closes, so these pages draw exactly that, for every statement NASDAQ trade on a tick day:
  - 90 one-minute candles before his click plus the FORMING candle up to the click second (hatched), built from Exness USTECm ticks and
    shifted by that trade's basis (his fill minus the Exness mid at the click), so the price axis reads like his CapitalFX screen;
  - CME NQ volume underneath (closed minutes only - the forming minute's volume would be the future);
  - his entry (triangle, at his fill) and, greyed to the right, the next 10 minutes with his exit (x, at his exit price);
  - dotted lines: the day's 09:30 open and the session high / low up to the click.
The old logs/his_charts_*.png (2026-09-25) predate the winter clock fix (his_strategy s35) and use 5-minute bars before June; these do not.
Output: logs/his_picture_book/page_NN.png, 4 trades a page, in date order. Nothing is computed or claimed here - observations go to tests.

    python -m backtest.his_picture_book
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
from matplotlib.patches import Rectangle  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backtest.his_brooks import ohlc  # noqa: E402
from backtest.his_level_memory import TICKS  # noqa: E402
from backtest.his_wyckoff import cme_minutes  # noqa: E402

OUT = ROOT / "logs" / "his_picture_book"
BEFORE, AFTER, PER_PAGE = 90, 10, 4


def partial(ts, mid, a: float, b: float):
    i, j = np.searchsorted(ts, a, "left"), np.searchsorted(ts, b, "right")
    if j <= i:
        return None
    m = mid[i:j]
    return float(m[0]), float(m.max()), float(m.min()), float(m[-1])


def candle(ax, x, o, h, l, c, color, alpha=1.0, hatch=None, w=0.62):
    ax.plot([x, x], [l, h], color=color, lw=0.9, alpha=alpha, zorder=2)
    lo_, hi_ = min(o, c), max(o, c)
    ax.add_patch(Rectangle((x - w / 2, lo_), w, max(hi_ - lo_, 0.25), facecolor=color if hatch is None else "white",
                           edgecolor=color, hatch=hatch, alpha=alpha, lw=0.8, zorder=3))


def main():
    import backtest.his_tape as TP
    from backtest.his_race_curve import race2
    cache = pickle.loads(TICKS.read_bytes())
    x = TP.entries()
    rows = [r for r in x.itertuples() if r.d in cache and cache[r.d] is not None and 5 * 60 <= r.t <= 36_000 - AFTER * 60]
    days = sorted({r.d for r in rows})
    n_of = {d: len(ohlc(cache[d][0], cache[d][1])[1]) for d in days}
    cme = cme_minutes(days, n_of)
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("page_*.png"):
        old.unlink()
    pages = [rows[i:i + PER_PAGE] for i in range(0, len(rows), PER_PAGE)]
    for pg, chunk in enumerate(pages, 1):
        fig = plt.figure(figsize=(18, 11), dpi=110)
        gs = fig.add_gridspec(4, 2, height_ratios=[3, 0.8, 3, 0.8], hspace=0.32, wspace=0.12)
        for slot, r in enumerate(chunk):
            k = (pg - 1) * PER_PAGE + slot + 1
            ts, mid = cache[r.d][0], cache[r.d][1]
            o, h, l, c = ohlc(ts, mid)
            t = float(r.t)
            M = int(t // 60) - 1                                          # the last closed minute
            i_click = np.searchsorted(ts, t, side="right") - 1
            basis = float(r.open_price) - float(mid[i_click])              # his CapitalFX price minus the Exness mid
            exit_t = t + (pd.Timestamp(r.close_time) - pd.Timestamp(r.open_time)).total_seconds()
            pts = (float(r.close_price) - float(r.open_price)) * r.s
            race = race2(ts, mid, t, r.s, 600, 7, 7)
            row, col = divmod(slot, 2)
            ax = fig.add_subplot(gs[row * 2, col])
            axv = fig.add_subplot(gs[row * 2 + 1, col], sharex=ax)
            lo_m = max(M - BEFORE + 1, 0)                                  # the tick days start at 09:30
            for m in range(lo_m, M + 1):
                if np.isfinite(o[m]):
                    candle(ax, m, o[m] + basis, h[m] + basis, l[m] + basis, c[m] + basis, "#1a9850" if c[m] >= o[m] else "#d73027")
            fp = partial(ts, mid, 60.0 * (M + 1), t)
            if fp:
                candle(ax, M + 1, *(v + basis for v in fp), "#1a9850" if fp[3] >= fp[0] else "#d73027", hatch="////")
            for m in range(M + 1, min(M + 1 + AFTER, len(o))):                # the next 10 minutes, greyed (the forming one fully)
                if np.isfinite(o[m]):
                    candle(ax, m + 0.0, o[m] + basis, h[m] + basis, l[m] + basis, c[m] + basis, "#9e9e9e", alpha=0.35)
            ax.axvspan(M + 1 + (t % 60) / 60.0 - 0.5, M + 1 + AFTER + 0.5, color="#bdbdbd", alpha=0.12, zorder=0)
            xc = M + 1 + (t % 60) / 60.0 - 0.5
            ax.scatter([xc], [float(r.open_price)], marker="^" if r.s > 0 else "v", s=170, color="#2166ac" if r.s > 0 else "#762a83",
                       edgecolor="black", zorder=6)
            xe = M + 1 + (exit_t - 60.0 * (M + 1)) / 60.0 - 0.5
            if xe <= M + 1 + AFTER + 0.5:
                ax.scatter([xe], [float(r.close_price)], marker="x", s=120, color="black", zorder=6)
            day_open = float(mid[0]) + basis
            seg_h, seg_l = np.nanmax(h[:M + 1]) + basis, np.nanmin(l[:M + 1]) + basis
            for yv, lab in ((day_open, "09:30 open"), (seg_h, "session high"), (seg_l, "session low")):
                ax.axhline(yv, color="#636363", lw=0.8, ls=":", zorder=1)
                ax.text(lo_m - 0.5, yv, f" {lab}", fontsize=7, color="#636363", va="bottom", clip_on=True)
            vis = np.r_[l[lo_m:M + 1 + AFTER], h[lo_m:M + 1 + AFTER]] + basis
            vis = vis[np.isfinite(vis)]
            pad = max(3.0, 0.08 * (vis.max() - vis.min()))
            ylo, yhi = vis.min() - pad, vis.max() + pad
            ax.set_ylim(ylo, yhi)
            ax.set_xlim(lo_m - 1, M + AFTER + 2)
            v = cme[r.d][0] if r.d in cme else None
            if v is not None:
                axv.bar(range(lo_m, M + 1), v[lo_m:M + 1], width=0.62, color="#4d4d4d")
                axv.bar(range(M + 1, min(M + 1 + AFTER, len(v))), v[M + 1:M + 1 + AFTER], width=0.62, color="#bdbdbd")
            axv.set_yticks([])
            ticks = [m for m in range(lo_m, M + AFTER + 2) if m % 15 == 0]
            axv.set_xticks(ticks)
            axv.set_xticklabels([(pd.Timestamp("2000-01-01 09:30") + pd.Timedelta(minutes=m)).strftime("%H:%M") for m in ticks], fontsize=8)
            plt.setp(ax.get_xticklabels(), visible=False)
            ax.tick_params(axis="y", labelsize=8)
            ax.grid(axis="y", color="#f0f0f0", zorder=0)
            clock = (pd.Timestamp("2000-01-01 09:30") + pd.Timedelta(seconds=t)).strftime("%H:%M:%S")
            ax.set_title(f"#{k}  {r.d:%Y-%m-%d %a}  click {clock} New York  {'BUY' if r.s > 0 else 'SELL'}  "
                         f"exit {pts:+.2f} pts  (+-7 race {'won' if race == 1 else 'lost' if race == 0 else '-'})", fontsize=10, loc="left")
        fig.suptitle(f"His NASDAQ trades on the 1-minute chart (CapitalFX prices = Exness + that trade's basis)  -  page {pg} of {len(pages)}"
                     f"   |   hatched = the forming candle at his click; grey = after the click; x = his exit", fontsize=11)
        fig.savefig(OUT / f"page_{pg:02d}.png", bbox_inches="tight")
        plt.close(fig)
    print(f"{len(rows)} trades on {len(pages)} pages -> {OUT}")


if __name__ == "__main__":
    main()
