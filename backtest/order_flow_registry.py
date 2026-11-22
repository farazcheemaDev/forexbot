"""THE ORDER-FLOW PROJECT'S REGISTRY - hypotheses, success criteria, cost model, power and the mechanical judge (2026-10-30).

WHY THIS IS CODE. A criterion written in prose can be bent after the result is known ("the t was 2.9, close enough"). Here the hypotheses and their pass / fail
rules are DATA, `judge()` applies them mechanically to a results dictionary, and `REGISTRY_SHA256` pins the registry: tests/test_order_flow_registry.py fails if
a single registered number changes. To change a criterion on purpose you must (1) say why in AMENDMENTS below, with the date and what had already been seen, and
(2) update the digest. Anything amended after seeing data is reported as amended, never as registered.

REGISTERED 2026-10-30, BEFORE ANY ORDER-FLOW DATA FOR THE TEN PAIRS WAS RECORDED. The only data seen: DOGE (book_hist.py, order_flow_lab.py, window_lab.py on
2026-06-01) - so DOGE is NOT an unused pair for H-imb, and 2026-09-01 is unread.

THE COMMON DESIGN (applies to every hypothesis unless the spec says otherwise)
    Data       Bitget USDT-futures PUBLIC websocket channels `books` (diff stream) and `trade`, recorded by the Module 5 recorder; no keys, no orders.
    Pairs      TUNE pairs XRP SUI LINK WLD (thresholds and cut-offs are fitted here); TEST pairs DOGE SHIB ADA DOT (read once, never tuned on); CONTROLS BTC SOL
               (reported separately; their tick is 0.01-0.1bp, so a one-tick signal is expected to be worth nothing there).
    Days       UTC days. TUNE days = the first 10 recorded days; CONFIRM days = every later day up to the registered end (at least 30 more days). Thresholds are frozen
               after day 10. The confirm days are read ONCE per hypothesis, at the end.
    Samples    NON-OVERLAPPING: one decision every `horizon` seconds; one position at a time; t is the per-trade mean with errors CLUSTERED BY UTC DAY.
    Nulls      shifted-feature null: the feature moved circularly by a random lag of 3,600 s or more, 200 draws; p = (1 + #draws as extreme) / 201.
    Costs      fee per side from the account's own tier (default Bitget standard: taker 6bp, maker 2bp); TAKER round trip = 2 x taker fee + the spread at the decision
               + walking a $300 order through the recorded book; MAKER round trip = 2 x maker fee with the queue-aware fill model of book_hist.maker_fill (a missed
               fill is NO TRADE; filled-signal adverse selection counted); funding charged if a settlement falls inside the hold.
    Features   timestamped: a feature at decision time T uses only data stamped before T (tests/test_window_lab.py shows the failure this prevents). Depth in bp bands of
               the mid, never in level counts.
    Exits      a time exit at the horizon; no discretionary exit; a disaster stop at 5 x the pair's sigma_h.
    Strata     busy (12-16 UTC) vs the rest is REPORTED for every result; it is not tuned on.

SUCCESS CRITERIA (all must hold; encoded in judge())
    K1  statistics   honest t (day-clustered, per-trade mean of the gross move in the registered direction) >= the Bonferroni cut-off for the hypothesis' own cell count m,
                     AND shifted-null p < 0.01.
    K2  economics    mean GROSS move per trade >= 2 x the all-in round-trip cost of the registered execution style, AND mean NET > 0.
                     (H-exec instead: the mean saving per order >= 1bp.)
    K3  replication  net > 0 on at least 75% of the confirm days (and at least 20 confirm days), at least 200 confirm trades, and the SAME SIGN of the net on at least
                     3 of the 4 TEST pairs.
    K4  increment    (H-combo only) the combined state beats the best single-signal subset at matched trade frequency, paired difference by day, t >= 2.
    A hypothesis that fails any criterion is REJECTED for retail use on this venue; it is not retuned on the confirm days.

IF A HYPOTHESIS PASSES (the user's instruction, 2026-10-30: "if there's an edge in it, add it in the Analyst desk"): judge() returning True makes it a CANDIDATE for a forward paper
test in the Analyst-desk style, nothing more: its rules frozen and registered in a new docstring BEFORE its first live call, calls logged with their timestamp before any outcome,
fills simulated against the live book with the queue model, a review date and a kill rule, its own paper book, shown on the dashboard's Analyst tab. It never trades real money
and is never wired into the main machine (doc 22's code freeze, to 2027-04-09, stands). The existing hourly analyst.py cannot carry it: that desk polls hourly and scores on
1-minute bars, while these signals live at seconds to minutes and need the recorded live feed, so the candidate needs its own small engine feeding the same dashboard tab.

AMENDMENTS
    2026-10-30 (before ANY official order-flow data existed; found while building the recorder in Module 5): "a day" was never defined. A UTC day now counts as a tune or
        confirm day FOR A PAIR only if that pair has a ready book no staler than `book_fresh_ms` (2 s) in at least `min_day_coverage` (90%) of the day's seconds
        (orderflow.features.day_coverage). Days below that are excluded from the day counts of K3 and from the 10 tune days, and are listed in the report. Digest updated.

    python -m backtest.order_flow_registry     prints the registry, its digest and each hypothesis' cell count / cut-off
"""
from __future__ import annotations

import hashlib
import json
from statistics import NormalDist

ND = NormalDist()

TUNE_PAIRS = ["XRPUSDT", "SUIUSDT", "LINKUSDT", "WLDUSDT"]
TEST_PAIRS = ["DOGEUSDT", "SHIBUSDT", "ADAUSDT", "DOTUSDT"]
CONTROL_PAIRS = ["BTCUSDT", "SOLUSDT"]

REGISTRY = {
    "common": {
        "tune_days": 10, "min_day_coverage": 0.9, "book_fresh_ms": 2000, "min_confirm_days": 20, "min_confirm_trades": 200, "positive_day_fraction": 0.75, "same_sign_test_pairs": 3,
        "shift_null_p": 0.01, "shift_min_s": 3600, "shift_draws": 200, "bonferroni_alpha": 0.05,
        "fee_bp": {"taker_per_side": 6.0, "maker_per_side": 2.0}, "order_usd": 300, "disaster_stop_sigma": 5.0,
        "tune_pairs": TUNE_PAIRS, "test_pairs": TEST_PAIRS, "control_pairs": CONTROL_PAIRS,
        "lookbacks_s": [1, 5, 30, 60, 300], "horizons_s": [30, 60, 300],
    },
    "H-imb": {
        "claim": "Band imbalance of the book, smoothed over a lookback, predicts the mid move over the next horizon in the signalled direction.",
        "features": ["imb1", "band5"], "lookbacks_s": [1, 5, 30], "horizons_s": [30, 60, 300], "pairs": "alts pooled, feature ranked within pair",
        "signal": "long at rank >= 0.90, short at rank <= 0.10 (cut-offs from the tune days)", "cells": 18, "execution": ["taker", "maker"],
        "criteria": ["K1", "K2", "K3"], "prior_K1": 0.70, "prior_K2": 0.03,
    },
    "H-flow": {
        "claim": "Taker-flow share over a lookback ending BEFORE the decision second predicts the move over the next horizon.",
        "features": ["flow_share_known"], "lookbacks_s": [1, 5, 30, 60, 300], "horizons_s": [30, 60, 300], "pairs": "alts pooled",
        "signal": "long at rank >= 0.90, short at rank <= 0.10", "cells": 15, "execution": ["taker", "maker"],
        "criteria": ["K1", "K2", "K3"], "prior_K1": 0.15, "prior_K2": 0.01,
    },
    "H-approach": {
        "claim": "When the opposing best price comes within 3bp of a wall at least 30 s old that has not shrunk over the last 10 s, price is less likely to trade through "
                 "it within the horizon than it is through a matched level of ordinary size at the same distance; trading the bounce pays after costs.",
        "features": ["wall_age_ge_30s_not_shrinking"], "approach_bp": 3, "wall": "size >= max(5 x median of the 10 nearest levels, 0.5 x the pair's median 1-minute "
        "traded dollars on the tune days)", "horizons_s": [60, 300], "pairs": "alts pooled", "signal": "enter away from the wall at the approach, stop one tick beyond the wall",
        "cells": 2, "execution": ["taker", "maker"], "criteria": ["K1", "K2", "K3"], "prior_K1": 0.30, "prior_K2": 0.03,
    },
    "H-combo": {
        "claim": "When imb1 rank, the known 30 s flow share and a no-pulled-wall state all agree, the move over the next horizon is larger than for the best single signal "
                 "at the same trade frequency.",
        "features": ["imb1_rank", "flow_share_known_30s", "no_wall_pulled_last_10s"], "horizons_s": [60, 300], "pairs": "alts pooled",
        "signal": "all three on the same side (top / bottom decile for imb1; flow and wall rules fixed from Module 2)", "cells": 2, "execution": ["taker", "maker"],
        "criteria": ["K1", "K2", "K3", "K4"], "prior_K1": 0.30, "prior_K2": 0.03, "prior_K4": 0.15,
    },
    "H-exec": {
        "claim": "Delaying a marketable order of one of the slower books by up to 30 s while imb1 is against it lowers its expected cost versus sending it at once.",
        "features": ["imb1_at_order_time"], "horizons_s": [30], "adverse_rank": [0.2, 0.1], "pairs": "the orders the paper books actually generate (their own timestamps)",
        "signal": "if imb1 is adverse (its rank on the side behind us is at or below `adverse_rank`) wait up to 30 s for it to normalise, then send; compare with sending at "
                  "the decision second",
        "cells": 2, "execution": ["taker"], "criteria": ["K1", "K2e", "K3"], "prior_K1": 0.25, "prior_K2": 0.20,
        "K2e": "mean saving per order >= 1bp versus sending at the decision second",
    },
}

REGISTRY_SHA256 = "56fda3b12599d48edf0c3a67fe33679ff3b858b72d679d3644d52e7fbf19e698"


def digest(reg=None) -> str:
    return hashlib.sha256(json.dumps(REGISTRY if reg is None else reg, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


# ------------------------------------------------------------------ the arithmetic the criteria use

def cut_t(m: int, alpha: float = 0.05) -> float:
    """Two-sided Bonferroni cut-off for m registered cells."""
    return ND.inv_cdf(1 - alpha / (2 * m))


def round_trip_cost_bp(style: str, spread_bp: float, fee_taker_bp: float = 6.0, fee_maker_bp: float = 2.0, slip_bp: float = 0.0) -> float:
    """All-in round-trip cost in bp of notional (before funding). taker: two taker fees + crossing the spread once (half on each side) + slippage on both legs;
    maker: two maker fees (adverse selection is a property of WHICH signals fill, measured by the fill simulation, not a constant); mixed: a maker entry, a taker exit."""
    if style == "taker":
        return 2 * fee_taker_bp + spread_bp + 2 * slip_bp
    if style == "maker":
        return 2 * fee_maker_bp
    if style == "mixed":
        return fee_maker_bp + fee_taker_bp + spread_bp / 2 + slip_bp
    raise ValueError(style)


def trades_needed(mu_bp: float, sd_bp: float, alpha: float = 0.05, power: float = 0.80) -> int:
    """Independent trades needed to detect a true mean `mu` per trade with per-trade sd `sd` at the given two-sided alpha and power."""
    z = ND.inv_cdf(1 - alpha / 2) + ND.inv_cdf(power)
    return int(-(-(z * sd_bp / mu_bp) ** 2 // 1))


def null_max_abs_t(k: int, q: float = 0.5) -> float:
    """The q-quantile of the largest |t| among k independent standard-normal tests: what pure noise reaches when you search k cells."""
    target = q ** (1.0 / k)                                                     # P(|Z| <= x) for one cell
    return ND.inv_cdf(0.5 + target / 2)


# ------------------------------------------------------------------ the judge

def judge(hid: str, r: dict, reg=None):
    """Apply a hypothesis' registered criteria to a results dict. Returns (passed, [(criterion, ok, detail), ...]).
    r: t (honest, day-clustered), p_shift, gross_bp, net_bp, cost_bp, n_trades, n_days, day_pos_frac, same_sign_pairs, increment_t (H-combo), saving_bp (H-exec)."""
    reg = REGISTRY if reg is None else reg
    h, c = reg[hid], reg["common"]
    rows = []
    cut = cut_t(h["cells"], c["bonferroni_alpha"])
    for k in h["criteria"]:
        if k == "K1":
            ok = r["t"] >= cut and r["p_shift"] < c["shift_null_p"]
            rows.append((k, ok, f"t {r['t']:.2f} vs cut {cut:.2f} ({h['cells']} cells); shifted-null p {r['p_shift']:.3f} vs {c['shift_null_p']}"))
        elif k == "K2":
            ok = r["gross_bp"] >= 2 * r["cost_bp"] and r["net_bp"] > 0
            rows.append((k, ok, f"gross {r['gross_bp']:.2f}bp vs 2 x cost {2 * r['cost_bp']:.2f}bp; net {r['net_bp']:.2f}bp"))
        elif k == "K2e":
            ok = r["saving_bp"] >= 1.0
            rows.append((k, ok, f"saving {r['saving_bp']:.2f}bp vs 1.00bp"))
        elif k == "K3":
            ok = (r["n_days"] >= c["min_confirm_days"] and r["n_trades"] >= c["min_confirm_trades"] and r["day_pos_frac"] >= c["positive_day_fraction"]
                  and r["same_sign_pairs"] >= c["same_sign_test_pairs"])
            rows.append((k, ok, f"{r['n_days']} days (min {c['min_confirm_days']}), {r['n_trades']} trades (min {c['min_confirm_trades']}), positive on "
                                f"{r['day_pos_frac'] * 100:.0f}% of days (min {c['positive_day_fraction'] * 100:.0f}%), same sign on {r['same_sign_pairs']} of 4 test pairs "
                                f"(min {c['same_sign_test_pairs']})"))
        elif k == "K4":
            ok = r["increment_t"] >= 2.0
            rows.append((k, ok, f"increment over the best single signal t {r['increment_t']:.2f} vs 2.00"))
        else:
            raise KeyError(k)
    return all(ok for _, ok, _ in rows), rows


def main():
    print("REGISTRY_SHA256 =", digest())
    c = REGISTRY["common"]
    for hid, h in REGISTRY.items():
        if hid == "common":
            continue
        print(f"{hid:11s} cells {h['cells']:3d}  Bonferroni cut |t| >= {cut_t(h['cells'], c['bonferroni_alpha']):.2f}   criteria {','.join(h['criteria'])}   "
              f"priors K1 {h['prior_K1']:.2f}, economics {h.get('prior_K2', 0):.2f}")
    print("noise reaches (median of the largest |t|):", ", ".join(f"{k} cells {null_max_abs_t(k):.2f}" for k in (1, 15, 18, 100, 1000)))


if __name__ == "__main__":
    main()
