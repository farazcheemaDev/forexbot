"""THE VALIDATED CRYPTO CONFIG, AND HIS LEVEL FADE, ON REAL FOREX / METALS / INDEX BARS.

    python -m backtest.forex

WHY THIS IS NOW POSSIBLE
    Every result in this project came from crypto, because forex intraday history was
    believed to be limited to 30-60 days. fx_fetch.py disproved that: the already
    installed Exness MT5 terminal holds 6.6 years of H1 and 4.2 years of M15. Two things
    that were previously untestable are now testable:

      A  the DEPLOYED configuration - bb_break(30,1.5), 20xATR trail, BE@3R - on
         instruments it has never seen. A genuine out-of-universe test, not another
         sweep of the same six years of crypto.

      B  HIS strategy. strategy_analysis/his_strategy.md section 8 names the blocker
         outright: "Free NQ 5m history = only 60 days. Robust validation needs
         months/years." His primary instrument is NASDAQ (USTECm on this broker) and his
         secondary is gold. Both now have a year or more of 5m bars.

THE COST THAT DOES NOT EXIST IN CRYPTO, AND DOMINATES HERE
    Crypto perps paid this project money to hold positions - funding carry was +5-8%/yr.
    Forex and CFDs charge it, and the charge is large relative to the spread:

        symbol     round-trip spread      swap on a LONG        held 2 weeks
        XAUUSDm             1.22 bp        1.25 bp/night          ~18 bp
        USTECm              0.77 bp        2.04 bp/night          ~29 bp
        EURUSDm             1.39 bp        0.49 bp/night           ~7 bp

    A 20xATR trail holds for WEEKS. So swap is 15-35x the spread for this strategy, and
    a backtest that charges only the spread is not wrong by a rounding error - it is
    wrong by the entire edge. Measured live from mt5.symbol_info (swap_mode=POINTS).

    Charged PER TRADE from the bars each trade was actually open, not as an average,
    because holding time and profitability are correlated: winners run and losers are
    stopped, so an average would tax the winners too little.

REGISTERED PREDICTIONS, BEFORE RUNNING (2026-09-14)
    A1  The trend config is WEAKER on FX majors than on crypto, probably dead. Majors
        are the most efficient market that exists and mean-revert around policy anchors;
        the edge was always "crypto grinds up and crashes down".
    A2  GOLD is the one that might survive - it trended hard 2020-2026 - but swap on
        longs will take most of it, and the 2020-2026 window flatters gold specifically.
    A3  Indices (USTECm/US30m) look attractive and will fail on swap, being the most
        expensive to hold of everything here.
    B1  His level fade FAILS AGAIN, now on years instead of 60 days. It came in at
        PF ~1.0 on NQ and 0.46-0.85 across crypto. More data usually kills a marginal
        strategy rather than rescuing it.
    B2  If any part of B survives it will be the SESSION FILTER, not the level logic -
        his 13:00-15:00 ET window is the most specific and least fittable claim in the
        whole reverse-engineering.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.convex import run_uncapped                    # noqa: E402
from backtest.mass_search import fetch, gen_signals         # noqa: E402
from backtest.rtest import run_r                            # noqa: E402
from bot.strategies.base import Action                      # noqa: E402
from bot.strategies.level_fade import LevelFade             # noqa: E402

# Measured 2026-09-14 from mt5.symbol_info(): spread in points x point size, and
# swap_long in POINTS per lot per night. spread_bp is ROUND TRIP.
#                  spread_bp  swap_bp_per_night
COSTS = {
    "XAUUSDm": (1.22, 1.25),
    "XAGUSDm": (9.52, 1.33),
    "EURUSDm": (1.39, 0.49),
    "GBPUSDm": (1.48, 0.49),
    "USDJPYm": (1.29, 0.49),
    "USTECm":  (0.77, 2.04),
    "US30m":   (0.38, 1.83),
}
BAR_H = {"5m": 5 / 60, "15m": 0.25, "1h": 1.0, "4h": 4.0, "1d": 24.0}
DAYS = 2400
HOLDOUT = 0.60          # first 60% is in-sample, last 40% is the holdout


def atr_series(df, n=14):
    h, l, c = df["high"], df["low"], df["close"]
    pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return tr.rolling(n).mean()


def swap_R(df, R, idx, bars, tf, swap_bp_night, sl_mult):
    """Swap cost of each trade, expressed in R so it can be subtracted from R.

    R is in units of risk, and risk = sl_mult x ATR at entry. So a cost quoted as a
    fraction of PRICE has to be divided by (risk / price) to become R. Using each
    trade's OWN entry ATR rather than a median matters: ATR varies 3-4x across these
    samples, and the same dollar of swap is a very different number of R in a calm
    market than a violent one.
    """
    a = atr_series(df).to_numpy()
    px = df["close"].to_numpy()
    nights = np.asarray(bars) * BAR_H[tf] / 24.0
    ent = np.asarray(idx) - np.asarray(bars)
    ent = np.clip(ent - 1, 0, len(a) - 1)       # ATR is the one from BEFORE entry
    risk_frac = sl_mult * a[ent] / px[ent]      # risk as a fraction of price
    cost_frac = (swap_bp_night / 10000.0) * nights
    with np.errstate(divide="ignore", invalid="ignore"):
        out = np.where(risk_frac > 0, cost_frac / risk_frac, 0.0)
    return np.nan_to_num(out)


def summarise(R, label, width=30):
    if len(R) == 0:
        return f"  {label:<{width}}{'no trades':>9}"
    win = 100 * (R > 0).mean()
    pf_g, pf_l = R[R > 0].sum(), -R[R < 0].sum()
    pf = pf_g / pf_l if pf_l > 0 else float("inf")
    return (f"  {label:<{width}}{len(R):>7}{R.mean():>9.3f}{win:>7.1f}"
            f"{pf:>7.2f}{R.sum():>9.1f}")


HDR = f"  {'':<30}{'n':>7}{'meanR':>9}{'win%':>7}{'PF':>7}{'totalR':>9}"


# ---------------------------------------------------------------------------
def test_a():
    print("=" * 100)
    print("A. THE DEPLOYED CONFIG ON INSTRUMENTS IT HAS NEVER SEEN")
    print("   bb_break(30,1.5) | 20xATR trail | BE@3R | sl 2xATR   (blend_paper.py)")
    print("=" * 100)
    print("   Showing spread-only FIRST and spread+swap SECOND, so the size of the")
    print("   holding cost is visible rather than asserted.\n")
    rows = []
    for sym in ("XAUUSDm", "XAGUSDm", "EURUSDm", "GBPUSDm", "USDJPYm",
                "USTECm", "US30m"):
        sp, sw = COSTS[sym]
        for tf in ("1h", "4h"):
            try:
                df = fetch(sym, tf, DAYS)
            except Exception as e:
                print(f"  {sym} {tf}: no data ({type(e).__name__})")
                continue
            if len(df) < 2000:
                print(f"  {sym:<9}{tf:<4} only {len(df)} bars, skipped")
                continue
            sig = gen_signals(df, "bb_break", (30, 1.5))
            R, idx, bars, _d = run_uncapped(df, sig, sl_mult=2.0, mode="trail_atr",
                                            trail=20.0, be_at=3.0, fee_bp=sp)
            if len(R) == 0:
                print(f"  {sym:<9}{tf:<4} no trades")
                continue
            Rs = R - swap_R(df, R, idx, bars, tf, sw, 2.0)
            med_days = np.median(np.asarray(bars)) * BAR_H[tf] / 24.0
            print(HDR if not rows else "", end="" if rows else "\n")
            print(summarise(R, f"{sym} {tf}  spread only"))
            print(summarise(Rs, f"{sym} {tf}  + swap ({med_days:.1f}d median hold)"))
            rows.append((sym, tf, R, Rs, idx, bars, df, sp, sw))
    return rows


def test_a_holdout(rows):
    print("\n" + "=" * 100)
    print("A2. THE SAME, SPLIT IN TIME — first 60% in-sample, last 40% HELD OUT")
    print("=" * 100)
    print("   A config chosen on crypto cannot be 'fitted' to forex, so this is not a")
    print("   fitting check. It asks whether any forex result is STABLE or came from")
    print("   one era - the failure mode that made 2021 carry 40% of the crypto book.\n")
    print(f"  {'':<30}{'IS meanR':>10}{'OOS meanR':>11}{'IS n':>7}{'OOS n':>7}"
          f"{'verdict':>12}")
    for sym, tf, _R, Rs, idx, bars, df, _sp, _sw in rows:
        cut = int(len(df) * HOLDOUT)
        ent = np.asarray(idx) - np.asarray(bars)
        is_m = ent < cut
        if is_m.sum() < 8 or (~is_m).sum() < 8:
            print(f"  {sym + ' ' + tf:<30}{'too few trades in one half':>40}")
            continue
        a, b = Rs[is_m].mean(), Rs[~is_m].mean()
        # FOUR cases, not three. The first version had no branch for "negative
        # in-sample, positive out-of-sample" and labelled gold - the loudest result
        # in the table - "dead both". Same incomplete-enumeration bug as the one
        # fixed in backtest/poly_fast.py the same day: the cases I expected were
        # handled and the one I did not expect fell through to a wrong default.
        if a > 0 and b > 0:
            v = "HOLDS"
        elif a > 0 >= b:
            v = "dies OOS"
        elif b > 0 >= a:
            # Profitable ONLY in the recent half. Not evidence of an edge - evidence
            # of one regime. On gold that regime is the 2024-2026 bull market, the
            # exact inflation already flagged in the docs for the first gold result.
            v = "ONE REGIME"
        else:
            v = "dead both"
        print(f"  {sym + ' ' + tf:<30}{a:>10.3f}{b:>11.3f}{is_m.sum():>7}"
              f"{(~is_m).sum():>7}{v:>12}")


# ---------------------------------------------------------------------------
def test_b():
    print("\n" + "=" * 100)
    print("B. HIS LEVEL FADE — on years of data instead of 60 days")
    print("=" * 100)
    print("   His profile: 30s-4min holds, 5-18 point targets, ~70-90% win rate, cuts")
    print("   losers small. That is a TIGHT STOP AND SMALL TARGET, so run_r (fixed")
    print("   stop/target) is the right engine here, not the trail engine in part A.")
    print("   Level step per his doc: 25 points on NASDAQ. Gold is scaled to the same")
    print("   FRACTION of price, because a fixed 25 means nothing across instruments.\n")
    for sym, tf in (("USTECm", "5m"), ("USTECm", "15m"),
                    ("XAUUSDm", "5m"), ("XAUUSDm", "15m")):
        try:
            df = fetch(sym, tf, DAYS)
        except Exception as e:
            print(f"  {sym} {tf}: no data ({type(e).__name__})")
            continue
        if len(df) < 3000:
            print(f"  {sym:<9}{tf:<4} only {len(df)} bars, skipped")
            continue
        sp, _sw = COSTS[sym]
        px = float(df["close"].median())
        # 25 points on a ~29,000 NASDAQ is 8.6bp of price. Hold that fraction.
        step = 25.0 if sym.startswith("USTEC") else round(px * 25.0 / 29000.0, 2)
        prox = step * 0.32                      # his 8pt proximity on a 25pt step
        print(f"  --- {sym} {tf}   {len(df):,} bars   "
              f"{df['time'].min():%Y-%m-%d} -> {df['time'].max():%Y-%m-%d}   "
              f"level step {step} / prox {prox:.2f}")
        print(HDR)
        lf = LevelFade(round_step=step, prox=prox, rsi_period=14,
                       rsi_hi=68.0, rsi_lo=32.0, use_prior_day=True)
        sig = lf.signals(df)
        # his exits: target ~1.5x the stop, both small. sl 1xATR keeps losers small.
        for sl, tp, lab in ((1.0, 1.5, "sl1.0 tp1.5"), (1.0, 1.0, "sl1.0 tp1.0"),
                            (0.75, 1.5, "sl0.75 tp1.5")):
            R, _ = run_r(df, sig, sl_mult=sl, tp_mult=tp, fee_bp=sp)
            print(summarise(R, f"level fade  {lab}"))
        # B2: the session filter alone, on the SAME signal, is the separable claim
        h = df["time"].dt.hour
        for lo, hi, lab in ((17, 20, "13-15 ET (his window)"), (13, 16, "09-12 ET"),
                            (0, 24, "all hours")):
            m = (h >= lo) & (h < hi) if lo < hi else pd.Series(True, index=df.index)
            s2 = sig.where(m, Action.HOLD)
            R, _ = run_r(df, s2, sl_mult=1.0, tp_mult=1.5, fee_bp=sp)
            print(summarise(R, f"  session {lab}"))
        print()


def main():
    print(__doc__.split("REGISTERED PREDICTIONS")[0].rstrip())
    print("\nREGISTERED PREDICTIONS (in the file, written before running):")
    print("  A: trend config weaker on FX, gold the only hope, indices die on swap.")
    print("  B: his level fade fails again; if anything survives it is the SESSION")
    print("     window, not the level logic.\n")
    rows = test_a()
    if rows:
        test_a_holdout(rows)
    test_b()
    print("=" * 100)
    print("Server clock is UTC+0 on Exness-MT5Trial16, so bar hours ARE UTC.")
    print("13:00-15:00 ET = 17:00-20:00 UTC in summer (EDT, UTC-4). Winter shifts it")
    print("an hour; not corrected here, so treat the session rows as +/-1h.")


if __name__ == "__main__":
    main()
