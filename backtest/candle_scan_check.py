"""POST-HOC ROBUSTNESS OF THE CANDLE-SCAN CELLS THAT KEPT THEIR EXCESS (2026-11-02)

backtest/candle_scan.py (204 cells, logs/candle_scan.txt): nothing passed Holm, but my predictions K3, K4 and K5 were wrong -
27 cells kept an excess over the date-matched baseline with t >= 2 on both halves, and 8 big cells had more than +0.30% on both.
The biggest, with tens of thousands of trades, are FADES of strong candles: 4h bullish engulfing sold / bearish engulfing bought
and held 20h, 4h bearish harami sold, 4h doji after a rise sold, 1h three black crows bought. Every one of them was picked
AFTER seeing the scan, so whatever survives here is a CANDIDATE for a forward test, not a result. This file looks for the bug
that could have made them look good:

  S  SLOT-MATCHED CONTROL. The scan's baseline is the entry DAY's mean; if a pattern clusters in certain 4h slots and those
     slots have their own drift, the excess is seasonality. Here the baseline is the mean of the same day AND the same entry slot.
  Y  BY YEAR. Net and excess for each calendar year (the scan only had two halves).
  C  COST STRESS. 25bp round trip instead of 12bp (crash-hour slippage on a fade that buys falling coins).
  D  DAYS. The same cell with its 10 best days removed (one bet per day, so a handful of crashes cannot carry it).
  N  COINS. Share of coins (>= 100 trades) with positive excess and the biggest coin's share of the positive total.

REGISTERED NOW, AFTER THE SCAN AND BEFORE THIS RUN (my reading: the cross-sectional short-term reversal that crypto is known
for, so I expect it to survive S and D and to lose ground in the years of one-way markets):
  S1  the slot-matched excess keeps at least half of the day-matched excess in each half for the 4h cells.
  Y1  the sign of the excess is the same in at least 5 of the 7 calendar years (2020 .. 2026) for the 4h H5 cells.
  C1  at 25bp the 4h H5 cells are still net positive on both halves; the 1h THREE_BLACK cell is not.
  D1  removing the 10 best days leaves the excess positive on both halves for every cell.
  N1  more than 60% of coins have positive excess and no coin supplies more than 15% of the positive total.

    python -m backtest.candle_scan_check
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest import candle_scan as cs  # noqa: E402

LOG = ROOT / "logs" / "candle_scan_check.txt"
CELLS = [(1, 1, "THREE_BLACK", 1), (1, 1, "THREE_WHITE", -1), (1, 5, "DOJI_UP", -1),
         (4, 5, "BULL_ENGULF", -1), (4, 5, "BEAR_ENGULF", 1), (4, 5, "BEAR_HARAMI", -1), (4, 5, "DOJI_UP", -1),
         (4, 1, "HANGING_MAN", -1)]
SLOTS = {1: 24, 4: 6, 24: 1}
FEE_STRESS = 25e-4


def slot_of(ent_t, tfh):
    hr = ((ent_t.astype("datetime64[h]") - ent_t.astype("datetime64[D]").astype("datetime64[h]")) / np.timedelta64(1, "h")).astype(int)
    return hr // tfh


def collect():
    from backtest.capitulation_wide import hourly
    from backtest.market_neutral import drop_non_crypto
    from backtest.wide_book import eligibility
    elig = drop_non_crypto(eligibility(40))
    coins = sorted(s for s in elig if elig[s] and s.endswith("USDT"))
    need = sorted({(tfh, H) for tfh, H, _, _ in CELLS})
    bsum = {k: np.zeros(cs.ND * SLOTS[k[0]]) for k in need}
    bcnt = {k: np.zeros(cs.ND * SLOTS[k[0]]) for k in need}
    trades = {(tfh, H, pat): [] for tfh, H, pat, _ in CELLS}
    for ci, sym in enumerate(coins):
        h = hourly(sym)
        if h is None:
            continue
        em = np.array(sorted(elig[sym]), dtype="datetime64[M]")
        for tfh in sorted({k[0] for k in need}):
            d = cs.to_tf(h, tfh)
            if len(d) < 60:
                continue
            t = d["time"].to_numpy("datetime64[ns]")
            o, hi, lo, c = (d[k].to_numpy(float) for k in ("o", "h", "l", "c"))
            fl = cs.pattern_flags(o, hi, lo, c)
            member = np.isin(t.astype("datetime64[M]"), em)
            step = tfh * 3600 * 10 ** 9
            for (tf2, H) in need:
                if tf2 != tfh:
                    continue
                valid = cs.valid_mask(t, step, H) & member & (o > 0) & (c > 0)
                allv = np.flatnonzero(valid)
                if not len(allv):
                    continue
                g = cs.trade_returns(o, c, allv, H)
                ok = np.isfinite(g)
                ent = t[allv + 1]
                key = cs.day_index(ent) * SLOTS[tfh] + slot_of(ent, tfh)
                bsum[(tfh, H)] += np.bincount(key[ok], weights=g[ok], minlength=cs.ND * SLOTS[tfh])
                bcnt[(tfh, H)] += np.bincount(key[ok], minlength=cs.ND * SLOTS[tfh])
                for (a, b, pat, _) in CELLS:
                    if (a, b) != (tfh, H):
                        continue
                    pk = cs.pick_trades(fl[pat], valid, H)
                    if not len(pk):
                        continue
                    gg = cs.trade_returns(o, c, pk, H)
                    ee = t[pk + 1]
                    good = np.isfinite(gg)
                    trades[(tfh, H, pat)].append((cs.day_index(ee)[good], slot_of(ee, tfh)[good], np.full(good.sum(), ci), gg[good]))
    return coins, bsum, bcnt, trades


def baselines(bsum, bcnt, tfh, H):
    S = SLOTS[tfh]
    s, n = bsum[(tfh, H)].reshape(cs.ND, S), bcnt[(tfh, H)].reshape(cs.ND, S)
    with np.errstate(invalid="ignore", divide="ignore"):
        by_slot = np.where(n > 0, s / np.maximum(n, 1), np.nan)
        by_day = np.where(n.sum(1) > 0, s.sum(1) / np.maximum(n.sum(1), 1), np.nan)
    return by_day, by_slot


def halves(day, x, ok):
    out = []
    for m in (day < cs.CUT_DAY, day >= cs.CUT_DAY):
        k = m & ok
        mean, t, g = cs.day_mean_t(x[k], day[k]) if k.sum() > 2 else (np.nan, np.nan, 0)
        out.append((mean, t, int(k.sum())))
    return out


def fmt2(h):
    return f"{h[0][0] * 100:+6.2f}% t{h[0][1]:+5.1f} / {h[1][0] * 100:+6.2f}% t{h[1][1]:+5.1f}"


def main():
    coins, bsum, bcnt, trades = collect()
    L = [f"backtest/candle_scan_check.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; {len(coins)} PIT coins; tune < 2024-08-29; "
         f"POST-HOC checks of cells picked from candle_scan.txt", ""]
    res = {}
    for tfh, H, pat, side in CELLS:
        parts = trades[(tfh, H, pat)]
        day = np.concatenate([p[0] for p in parts])
        slot = np.concatenate([p[1] for p in parts])
        coin = np.concatenate([p[2] for p in parts])
        gross = np.concatenate([p[3] for p in parts])
        by_day, by_slot = baselines(bsum, bcnt, tfh, H)
        b_day, b_slot = by_day[day], by_slot[day, slot]
        hours = H * tfh
        cost = cs.FEE + (cs.FUND_H * hours if side > 0 else 0.0)
        cost2 = FEE_STRESS + (cs.FUND_H * hours if side > 0 else 0.0)
        ok = np.isfinite(b_day) & np.isfinite(b_slot) & np.isfinite(gross)
        net = side * gross - cost
        exc_d = side * (gross - b_day)
        exc_s = side * (gross - b_slot)
        r = dict(net=halves(day, net, ok), exc_day=halves(day, exc_d, ok), exc_slot=halves(day, exc_s, ok),
                 net25=halves(day, side * gross - cost2, ok))
        # years
        yrs = (cs.D0 + day.astype("timedelta64[D]")).astype("datetime64[Y]").astype(int) + 1970
        r["years"] = {}
        for y in range(2020, 2027):
            k = ok & (yrs == y)
            if k.sum() > 30:
                r["years"][y] = (cs.day_mean_t(net[k], day[k])[0], cs.day_mean_t(exc_d[k], day[k])[0], int(k.sum()))
        # best 10 days removed
        u, inv = np.unique(day[ok], return_inverse=True)
        dm = np.bincount(inv, weights=exc_d[ok]) / np.bincount(inv)
        drop = set(u[np.argsort(-dm)[:10]].tolist())
        keep = ok & ~np.isin(day, list(drop))
        r["drop10"] = halves(day, exc_d, keep)
        # coins
        cm = {}
        for ci in np.unique(coin[ok]):
            k = ok & (coin == ci)
            if k.sum() >= 100:
                cm[ci] = exc_d[k].mean() * k.sum()
        pos = [v for v in cm.values() if v > 0]
        r["coins"] = (len(cm), sum(1 for v in cm.values() if v > 0), (max(pos) / sum(pos) if pos else np.nan))
        res[(tfh, H, pat, side)] = r
        L.append(f"{cs.TFN[tfh]} H{H} {pat} {'long' if side > 0 else 'short'}   trades {len(gross):,}")
        L.append(f"   net 12bp      tune/hold  {fmt2(r['net'])}")
        L.append(f"   net 25bp      tune/hold  {fmt2(r['net25'])}")
        L.append(f"   excess (day)  tune/hold  {fmt2(r['exc_day'])}")
        L.append(f"   excess (slot) tune/hold  {fmt2(r['exc_slot'])}")
        L.append(f"   excess, 10 best days out {fmt2(r['drop10'])}")
        L.append("   by year  net / excess:  " + "  ".join(f"{y}:{v[0] * 100:+.2f}/{v[1] * 100:+.2f}" for y, v in r["years"].items()))
        L.append(f"   coins {r['coins'][0]}, positive excess {r['coins'][1]}, biggest coin = {r['coins'][2] * 100:.0f}% of the positive total")
        L.append("")
    four = [k for k in res if k[0] == 4 and k[1] == 5]
    s1 = all(min(res[k]["exc_slot"][i][0] / res[k]["exc_day"][i][0] for i in (0, 1)) >= 0.5 for k in res if k[0] == 4)
    y1 = all(sum(1 for v in res[k]["years"].values() if v[1] > 0) >= 5 for k in four)
    c1a = all(all(res[k]["net25"][i][0] > 0 for i in (0, 1)) for k in four)
    c1b = not all(res[(1, 1, "THREE_BLACK", 1)]["net25"][i][0] > 0 for i in (0, 1))
    d1 = all(all(res[k]["drop10"][i][0] > 0 for i in (0, 1)) for k in res)
    n1 = all(res[k]["coins"][1] / max(res[k]["coins"][0], 1) > 0.6 and res[k]["coins"][2] <= 0.15 for k in res)
    L += ["REGISTERED (post-hoc cells)",
          f"  S1 slot-matched excess keeps >= half of the day-matched excess (4h cells) -> {'RIGHT' if s1 else 'WRONG'}",
          f"  Y1 excess positive in >= 5 of 7 years (4h H5 cells) -> {'RIGHT' if y1 else 'WRONG'}",
          f"  C1 at 25bp the 4h H5 cells stay net positive on both halves ({'yes' if c1a else 'no'}); the 1h THREE_BLACK cell does not ({'right' if c1b else 'wrong'}) -> {'RIGHT' if (c1a and c1b) else 'WRONG'}",
          f"  D1 excess positive on both halves with the 10 best days removed (every cell) -> {'RIGHT' if d1 else 'WRONG'}",
          f"  N1 > 60% of coins positive and no coin over 15% of the positive total (every cell) -> {'RIGHT' if n1 else 'WRONG'}"]
    txt = "\n".join(L)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
