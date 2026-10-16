"""THE TRADER'S MONTHLY TARGET ON OUR MACHINE - stop for the month at +10% (2026-10-16)

The user: "I want at least 10 percent - monthly; test the stop at 10% idea". His_monthly_target.py: the NASDAQ trader
trades to ~10% a month and stops. Applied to the final machine at the ACCOUNT level: once the month-to-date return
reaches +T, the account goes flat (every position closed at that day's equity) and stays out until the month ends.
Variants: T = +10% / +15% / +20%; a monthly STOP at -10% (flat for the rest of the month); both together.
DATA   --in : the deployed final machine 2020-2026 (final_confidence.parts(), capit2 1.0 x 2x), 10 orderings
       --oos: the frozen machine on Binance spot 2017-08..2019-12 (oos1719.py's combined book), 10 orderings - a
              separate process, because oos1719 re-points the data folders of the engines it imports
LIMIT  the books' series are booked partly at trade closes, so "flat at that day's equity" ignores open profit not yet
       booked: the rule is applied to what the account shows, as a person following it would see a realised balance.
REPORTED  average / median month, months >= +10%, losing months, months <= -10%, CAGR, the biggest fall.

REGISTERED BEFORE THE RUN (2026-10-16)
    1. The +10% target LOWERS the average month on both data sets (the +30% months pay for the losing ones).
    2. It raises the share of months that end at or near +10% only slightly, and losing months stay >= 40%.
    3. The -10% monthly stop lowers the average month as well (trend books recover inside the month).

RESULT (2026-10-16, logs/month_target.txt / month_target_oos.txt) - avg month / median / months >= +10% / losing /
    CAGR / fall:
    IN SAMPLE  no rule +41.9% / +7.6% / 46% / 36% / +1373% / 56% | stop at +10% +13.0% / +11.0% / 61% / 30% / +199% / 50%
               +10% and -10% +7.6% / +10.1% / 51% / 44% / +76% / 46%
    OOS 17-19  no rule +8.7% / 0.0% / 28% / 49% / +88% / 48%    | stop at +10% +5.1% / 0.0% / 37% / 46% / +53% / 42%
               +10% and -10% +5.4% / 0.0% / 37% / 46% / +58% / 33%
    The target makes +10% months more common (28 -> 37% out of sample) and costs ~40% of the yearly return; nearly half
    the months still lose out of sample. A -10% monthly stop locks in months that would have recovered (months <= -10%
    16 -> 40% in sample). Predictions: 1 right; 2 right out of sample, wrong in sample (61% of months reach +10%, losing
    30%); 3 right in sample, wrong out of sample (+8.7 -> +9.0%).

    python -m backtest.month_target --in
    python -m backtest.month_target --oos
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

RULES = {"no rule": (None, None), "stop at +10%": (0.10, None), "stop at +15%": (0.15, None), "stop at +20%": (0.20, None),
         "stop at -10%": (None, -0.10), "+10% and -10%": (0.10, -0.10)}


def apply(r, up, dn):
    """Daily returns -> daily returns with the month's trading stopped once month-to-date hits up (or dn)."""
    out = r.to_numpy(dtype=float).copy()
    m = r.index.to_period("M")
    mtd, cur, stopped = 1.0, None, False
    for i in range(len(out)):
        if m[i] != cur:
            cur, mtd, stopped = m[i], 1.0, False
        if stopped:
            out[i] = 0.0
            continue
        mtd *= 1 + out[i]
        if (up is not None and mtd - 1 >= up) or (dn is not None and mtd - 1 <= dn):
            stopped = True
    return pd.Series(out, index=r.index)


def report(xs, label):
    lines = [f"  {label}", f"    {'rule':<16}{'avg month':>10}{'median':>8}{'>= +10%':>9}{'losing':>8}{'<= -10%':>9}{'CAGR':>8}{'fall':>6}"]
    for nm, (up, dn) in RULES.items():
        mo, cg, fl = [], [], []
        for x in xs:
            y = apply(x.fillna(0.0), up, dn)
            c = (1 + y).cumprod()
            me = c.resample("ME").last()
            mo.append((me / me.shift(1).fillna(1.0) - 1).to_numpy()[1:])
            yrs = (c.index[-1] - c.index[0]).days / 365.25
            cg.append(c.iloc[-1] ** (1 / yrs) - 1 if c.iloc[-1] > 0 else -1)
            fl.append(float((1 - c / c.cummax()).max()))
        a = np.concatenate(mo)
        lines.append(f"    {nm:<16}{a.mean() * 100:>+9.1f}%{np.median(a) * 100:>+7.1f}%{(a >= 0.0999).mean() * 100:>8.0f}%"
                     f"{(a < 0).mean() * 100:>7.0f}%{(a <= -0.10).mean() * 100:>8.0f}%{np.median(cg) * 100:>+7.0f}%{np.median(fl) * 100:>5.0f}%")
    return lines


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--in"
    if mode == "--oos":
        import backtest.oos1719 as O
        got = []
        orig = O.stats
        O.stats = lambda r: (got.append(r), orig(r))[1]
        O.LOG = ROOT / "logs" / "oos1719_rerun_for_month_target.txt"
        O.main()
        xs = [x[(x.index >= O.START) & (x.index <= O.END)] for x in got[-10:]]       # COMBINED is scored last
        lines = report(xs, "OUT OF SAMPLE: frozen machine on Binance spot 2017-08 .. 2019-12")
    else:
        from backtest.final_confidence import parts
        xs = [s + mi for s, mi in parts()]
        lines = report(xs, "IN SAMPLE: the deployed final machine 2020-2026 (capit2 1.0 x 2x)")
    log = ROOT / "logs" / f"month_target{'_oos' if mode == '--oos' else ''}.txt"
    txt = "\n".join([f"backtest/month_target.py {mode}, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; 10 orderings", ""] + lines)
    log.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
