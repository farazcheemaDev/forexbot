"""Maker (limit-order) execution, simulated honestly.

WHY THIS MATTERS MORE THAN ANY SIGNAL WE TESTED
-----------------------------------------------
On untouched crypto data the momentum edge breaks even at 6-8.5bp round trip.
Bitget charges ~12bp round trip taker and ~4bp maker. Every test I ran, and all
three live bots, used MARKET orders — i.e. the wrong side of breakeven. The sign
of the edge is decided by execution, not by the signal.

WHAT A HONEST MAKER SIMULATION MUST INCLUDE
-------------------------------------------
Lowering the fee from 12bp to 4bp does NOT hand you the same trades at a
discount. A resting limit order:

  1. NON-FILL — price never comes to you, so you miss the trade entirely. If the
     trades you miss are disproportionately the winners (price ran away), the fee
     saving is worthless.
  2. ADVERSE SELECTION — you only fill when price moves AGAINST your direction
     first. So every fill is, by construction, entered after a move the wrong
     way. This is captured automatically here: we fill at the limit and then let
     the actual subsequent path decide the outcome.
  3. ASYMMETRIC EXIT COSTS — a take-profit is a resting limit (maker), but a
     stop-loss is a market/stop order (taker). So a winner pays maker+maker and
     a loser pays maker+taker. Modelled separately.
  4. RISK MEASURED FROM THE FILL — stop and target are placed relative to the
     actual fill price, as a real bot does, so R stays comparable.

No look-ahead: the offset and the stop distance both come from ATR[i-1], and
fill detection only asks whether the market reached a price we had already
posted.

    python -m backtest.maker_r
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bot.core.indicators import atr as atr_ind  # noqa: E402
from bot.strategies.base import Action  # noqa: E402

# Bitget USDT-perp, per side
MAKER_BP, TAKER_BP = 2.0, 6.0


def run_maker(df: pd.DataFrame, sig: pd.Series, sl_mult: float = 2.0,
              tp_mult: float = 3.0, offset_atr: float = 0.25,
              wait_bars: int = 3, maker_bp: float = MAKER_BP,
              taker_bp: float = TAKER_BP, atr_period: int = 14,
              taker_entry: bool = False) -> dict:
    """Simulate limit-order entries. Returns R array, fill rate, and diagnostics.

    offset_atr: how far BELOW market (for a buy) to post the limit, in ATR units.
                0.0 posts at the open — fills almost always but captures no edge.
    wait_bars:  bars to leave the order resting before cancelling.
    taker_entry: if True, ignore offset/wait and market-in (the baseline).
    """
    s = sig.to_numpy() if isinstance(sig, pd.Series) else np.asarray(sig)
    o = df["open"].to_numpy(float)
    h = df["high"].to_numpy(float)
    lo = df["low"].to_numpy(float)
    a = atr_ind(df, atr_period).to_numpy(float)
    n = len(df)
    mk, tk = maker_bp / 10000.0, taker_bp / 10000.0

    Rs, exit_idx = [], []
    signals = fills = 0
    pos = None          # (d, entry, risk, stop, targ)
    i = 1
    while i < n:
        if pos is None and s[i] != Action.HOLD and np.isfinite(a[i - 1]) and a[i - 1] > 0:
            signals += 1
            d = 1 if s[i] == Action.BUY else -1
            risk_ref = sl_mult * a[i - 1]

            if taker_entry:
                entry, fill_bar = o[i], i
            else:
                limit = o[i] - d * offset_atr * a[i - 1]
                entry, fill_bar = None, None
                for j in range(i, min(i + wait_bars, n)):
                    reached = (lo[j] <= limit) if d == 1 else (h[j] >= limit)
                    if reached:
                        entry, fill_bar = limit, j
                        break
                if entry is None:                 # never came to us - trade missed
                    i += 1
                    continue
            fills += 1
            risk = sl_mult * a[i - 1]
            pos = (d, entry, risk, entry - d * risk, entry + d * tp_mult * a[i - 1])
            i = fill_bar                          # exits may occur on the fill bar

        if pos is not None:
            d, e, risk, stop, targ = pos
            hit_sl = (lo[i] <= stop) if d == 1 else (h[i] >= stop)
            hit_tp = (h[i] >= targ) if d == 1 else (lo[i] <= targ)
            px, exit_is_taker = ((stop, True) if hit_sl else
                                 ((targ, False) if hit_tp else (None, True)))
            if px is not None:
                entry_cost = (tk if taker_entry else mk) * e
                exit_cost = (tk if exit_is_taker else mk) * abs(px)
                R = (px - e) * d / risk - (entry_cost + exit_cost) / risk
                Rs.append(R); exit_idx.append(i)
                pos = None
        i += 1

    R = np.asarray(Rs)
    return dict(R=R, idx=np.asarray(exit_idx, dtype=int),
                signals=signals, fills=fills,
                fill_rate=(fills / signals if signals else 0.0),
                n=len(R), meanR=float(R.mean()) if len(R) else 0.0,
                sumR=float(R.sum()) if len(R) else 0.0,
                win=float((R > 0).mean()) if len(R) else 0.0)


def main():
    from backtest.holdout_sweep import ASSETS, USED_DAYS, signals_for
    from backtest.mass_search import FILTERS, fetch

    CFGS = [("bb_break", (30, 1.5), "none"),
            ("rsi_mom", (7, 40, 60), "none"),
            ("roc_mom", (10, 1.0), "none")]

    print("MAKER vs TAKER on UNTOUCHED crypto data (holdout window, 9 assets)")
    print(f"Bitget: maker {MAKER_BP}bp/side, taker {TAKER_BP}bp/side")
    print("sumR/yr is the metric that matters: fewer trades at higher meanR may "
          "still harvest less.\n")

    data = {}
    for a in ASSETS:
        try:
            d = fetch(a, "1h", 2400)
        except Exception:
            continue
        cut = d.time.iloc[-1] - pd.Timedelta(days=USED_DAYS)
        hold = d[d.time < cut].reset_index(drop=True)
        if len(hold) >= 3000:
            data[a] = hold
    yrs = np.mean([len(d) / 24 / 365.25 for d in data.values()])
    print(f"{len(data)} assets, ~{yrs:.2f} years each\n")

    for fam, p, filt in CFGS:
        print(f"--- {fam}{p} ---")
        print(f"{'execution':28} {'fill%':>6} {'trades':>7} {'meanR':>8} "
              f"{'win%':>6} {'sumR/yr':>8}")
        runs = [("TAKER market (baseline)", dict(taker_entry=True))]
        for off in (0.10, 0.25, 0.50):
            for wait in (2, 4):
                runs.append((f"MAKER off={off:.2f}ATR wait={wait}",
                             dict(offset_atr=off, wait_bars=wait)))
        for label, kw in runs:
            allR, sig_t, fil_t = [], 0, 0
            for a, d in data.items():
                s = FILTERS[filt](d, signals_for(d, fam, p))
                r = run_maker(d, s, **kw)
                allR.append(r["R"]); sig_t += r["signals"]; fil_t += r["fills"]
            R = np.concatenate([x for x in allR if len(x)])
            fr = fil_t / sig_t if sig_t else 0
            print(f"{label:28} {fr*100:>6.1f} {len(R):>7} {R.mean():>+8.4f} "
                  f"{(R>0).mean()*100:>6.1f} {R.sum()/(yrs*len(data)):>+8.2f}")
        print()


if __name__ == "__main__":
    main()
