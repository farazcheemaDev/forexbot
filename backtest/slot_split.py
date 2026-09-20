"""SHOULD LONGS AND SHORTS SHARE ONE SLOT CAP? — the last structural asymmetry.

    python -m backtest.slot_split

THE OBSERVATION
    The deployed config has ONE cap of 12 slots, filled first-come-first-served across
    both directions. Measured over the whole sample:

        shorts are 64% of all sleeve trades   (10,108 of 15,736)
        shorts contribute +529R in total      longs contribute +19,113R

    So the majority of slots go to the side that produces almost none of the profit.
    Live, the bot declines about seven signals for every one it takes, which means the
    cap binds constantly and the question of WHO gets the slot is not academic.

    This is different from backtest/bear_side.py. That changed how BIG each trade is.
    This changes WHICH trades are taken at all.

WHAT IS TESTED
    Separate caps per side, as (long slots, short slots). Rows that sum to 12 hold total
    exposure fixed and only move the split; rows above 12 add exposure and are marked, so
    a win there is not confused with a better split.

        shared 12           the deployed allocator, one queue, no reservation
        2/10 ... 10/2       the same 12 slots, divided
        12/12               separate caps, both full - MORE total exposure
        8/8                 16 total - more exposure, balanced

    Everything else is held at the deployed settings: 1h+4h+12h sleeves, 0.30% per unit,
    the symmetric 0.25 bear gate. One variable moves.

ACCOUNTING
    Equity is compounded by CLOSE DATE, not trade order. backtest/bear_date.py showed the
    open-order convention (mistake #6) overstates the deployed holdout return by 31% and
    manufactured a drawdown improvement that was not there, and it distorts most when the
    long/short mix changes - which is exactly what this test changes. Close-date is also
    imperfect (a twenty-week trade books its whole P&L on one day) so drawdowns are read
    as comparisons, not levels.

REGISTERED PREDICTION (2026-09-20, before running)
    Reserving slots for longs will beat the shared cap, and clearly. Shorts take 64% of
    the slots and produce 2.7% of the R, so every short that occupies a slot a long could
    have used is close to a pure loss of opportunity. I expect the best split to sit
    around 8-10 long against 2-4 short, with return rising as long slots rise and the
    drawdown getting WORSE as the short hedge thins out.

    The prediction that would surprise me: shared-12 winning. That would mean the
    first-come queue is already allocating well and the 64/2.7 imbalance is illusory -
    which could happen if the declined longs simply re-signal a few bars later, making
    the slot they lost costless.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import blend  # noqa: E402
from backtest.bear_side import all_trades, sleeve_sided  # noqa: E402

SPLITS = [("shared 12 (deployed)", None, None),
          ("2 long / 10 short", 2, 10),
          ("4 long / 8 short", 4, 8),
          ("6 long / 6 short", 6, 6),
          ("8 long / 4 short", 8, 4),
          ("10 long / 2 short", 10, 2),
          ("12 long / 0 short", 12, 0),
          ("8/8 = 16 total (MORE)", 8, 8),
          ("12/12 = 24 total (MORE)", 12, 12)]
SHARED = 12


def run(tr, lslots, sslots, mult=(0.25, 0.25), t_from=None, t_to=None):
    """Separate caps when lslots/sslots are given; one shared queue when they are None."""
    bear = blend.btc_bear()
    lm, sm = mult
    f0 = blend.RISK / 100.0
    shared, ol, os_ = [], [], []
    rows, taken = [], {"long": 0, "short": 0}
    declined = {"long": 0, "short": 0}
    for a_, b_, r, _rule, _c, side in tr:
        if t_from is not None and a_ < t_from:
            continue
        if t_to is not None and a_ >= t_to:
            continue
        if lslots is None:
            shared = [u for u in shared if u > a_]
            if len(shared) >= SHARED:
                declined[side] += 1
                continue
        else:
            ol = [u for u in ol if u > a_]
            os_ = [u for u in os_ if u > a_]
            cap = lslots if side == "long" else sslots
            cur = ol if side == "long" else os_
            if len(cur) >= cap:
                declined[side] += 1
                continue
        try:
            ib = bool(bear.asof(a_))
        except Exception:
            ib = False
        f = f0 * ((lm if side == "long" else sm) if ib else 1.0)
        if f <= 0:
            continue
        if lslots is None:
            shared.append(b_)
        elif side == "long":
            ol.append(b_)
        else:
            os_.append(b_)
        taken[side] += 1
        rows.append((pd.Timestamp(b_), r * f))
    if len(rows) < 30:
        return None
    s = pd.Series([x[1] for x in rows], index=pd.DatetimeIndex([x[0] for x in rows]))
    daily = s.resample("D").sum()
    cur_ = np.cumprod(1.0 + daily.values)
    pk = np.maximum.accumulate(np.maximum(cur_, 1e-12))
    dd = float((1 - cur_ / pk).max() * 100)
    yrs = max((daily.index[-1] - daily.index[0]).days / 365.25, 1e-9)
    cagr = (max(cur_[-1], 1e-12) ** (1 / yrs) - 1) * 100
    mon = daily.resample("ME").sum()
    return dict(hpm=((1 + (cagr / blend.HINDSIGHT) / 100) ** (1 / 12) - 1) * 100,
                dd=dd, taken=taken, declined=declined,
                worst=float(mon.min() * 100), win=float((mon > 0).mean() * 100),
                n=len(rows))


def main():
    print(__doc__.split("REGISTERED PREDICTION")[0].rstrip())
    print("\nREGISTERED: reserving slots for longs beats the shared cap clearly - shorts")
    print("take 64% of slots for 2.7% of the R. Best split around 8-10 long / 2-4 short,")
    print("with drawdown getting WORSE as the short hedge thins. Shared-12 winning would")
    print("mean declined longs simply re-signal later, making the lost slot costless.\n")

    tr, _stops = all_trades()
    ts_all = pd.DatetimeIndex(sorted(x[0] for x in sleeve_sided("1h")[0]))
    cut = ts_all[int(len(ts_all) * 0.6)]
    print(f"  {len(tr):,} sleeve trades, split at {cut.date()}, "
          f"compounded by CLOSE DATE\n")

    print("=" * 104)
    print("1. THE SPLIT, AT THE DEPLOYED 0.25/0.25 BEAR GATE")
    print("=" * 104)
    print(f"  {'split':<24}| {'TUNE /mo':>9}{'DD':>7} | {'HOLD /mo':>9}{'DD':>7}"
          f"{'worst mo':>10}{'win%':>6} | {'L taken':>8}{'S taken':>8}")
    res = {}
    for lab, ls, ss in SPLITS:
        a = run(tr, ls, ss, t_to=cut)
        b = run(tr, ls, ss, t_from=cut)
        if not (a and b):
            print(f"  {lab:<24}  too few trades")
            continue
        res[lab] = (a, b)
        print(f"  {lab:<24}|{a['hpm']:>+9.2f}%{a['dd']:>6.1f}% |{b['hpm']:>+9.2f}%"
              f"{b['dd']:>6.1f}%{b['worst']:>+9.1f}%{b['win']:>5.0f}% |"
              f"{b['taken']['long']:>8,}{b['taken']['short']:>8,}")
    print("\n  rows marked MORE add total exposure, so a win there is not a better split.")

    print("\n" + "=" * 104)
    print("2. DOES THE BEST SPLIT STACK WITH THE 3x SHORT MULTIPLIER?")
    print("=" * 104)
    base = res.get("shared 12 (deployed)")
    cands = [(k, v) for k, v in res.items() if "MORE" not in k]
    best = max(cands, key=lambda kv: kv[1][1]["hpm"])
    print(f"  best same-exposure split on the holdout: {best[0]}\n")
    print(f"  {'configuration':<40}| {'HOLD /mo':>9}{'DD':>7}{'worst mo':>10}{'win%':>6}")
    combos = [("shared 12, gate 0.25/0.25 (deployed)", None, None, (0.25, 0.25)),
              ("shared 12, gate 0.25/3.00", None, None, (0.25, 3.00))]
    ls, ss = next((l, s) for k, l, s in
                  [(x[0], x[1], x[2]) for x in SPLITS] if k == best[0])
    combos += [(f"{best[0]}, gate 0.25/0.25", ls, ss, (0.25, 0.25)),
               (f"{best[0]}, gate 0.25/3.00", ls, ss, (0.25, 3.00))]
    for lab, l_, s_, m in combos:
        b = run(tr, l_, s_, mult=m, t_from=cut)
        if not b:
            continue
        print(f"  {lab:<40}|{b['hpm']:>+9.2f}%{b['dd']:>6.1f}%"
              f"{b['worst']:>+9.1f}%{b['win']:>5.0f}%")

    print("\n" + "=" * 104)
    print("VERDICT")
    print("=" * 104)
    if not base:
        print("  no baseline")
        return
    bt, bh = base
    win = [k for k, (a, b) in res.items()
           if "MORE" not in k and b["hpm"] > bh["hpm"] and a["hpm"] > bt["hpm"]]
    if not win:
        print("  THE SHARED QUEUE WINS. No same-exposure split beats it on both halves,")
        print("  which means a long that loses a slot to a short is not losing much -")
        print("  it re-signals later. The 64%-of-slots-for-2.7%-of-R imbalance is real")
        print("  as an accounting fact and costless as an allocation fact.")
    else:
        print(f"  BEATS THE SHARED QUEUE on both halves: {', '.join(win)}")
        print("  This changes WHICH trades are taken, so re-check it on the")
        print("  point-in-time universe before it goes anywhere near the live config.")


if __name__ == "__main__":
    main()
