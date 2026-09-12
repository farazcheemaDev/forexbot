"""Adaptive allocation layer — the 'relearning' mechanism.

TWO INDEPENDENT GATES, because they protect against different failure modes:

1. STATISTICAL CUT ("this strategy has stopped working")
   Needs MIN_TRADES before it will judge anything. With few trades noise
   dominates, and a naive adaptive layer thrashes - cutting good strategies
   after a couple of unlucky trades. Patience is correct here.

2. RISK CUT / CIRCUIT BREAKER ("this strategy is killing us, stop it NOW")
   Fires at ANY sample size. This exists because gate 1's patience is
   dangerous on its own: at 3% risk per trade, waiting for 20 trades before
   acting means allowing a -60% account drawdown first. Whether that loss was
   bad luck or a dead edge is a question you ask AFTER you've stopped the
   bleeding, not before. Sample size does not invalidate a risk control.

   It LATCHES. Once tripped a strategy stays off until a human resets it
   (reset_breaker / the bots' --reset-breakers flag). A breaker that silently
   re-closes itself is not a breaker.

Design principle learned from testing: adaptation's value is as an IMMUNE
SYSTEM (cut what's dead), not a return booster. Backtest showed adaptive
~matched knowing-the-best-in-advance and clearly beat running everything.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

LOGS = Path(__file__).resolve().parents[2] / "logs"

# --- gate 1: statistical -----------------------------------------------------
MIN_TRADES = 20        # never judge a strategy on fewer than this
LOOKBACK = 30          # evaluate over the most recent N trades
CUT_BELOW = 0.0        # deactivate if mean R over lookback is below this
REVIVE_ABOVE = 0.05    # reactivate only once clearly positive again (hysteresis)

# --- gate 2: risk / circuit breaker -----------------------------------------
# RESTORED to safe values 2026-09-12. These were temporarily set to 30.0/12 for a
# demo-aggressive overnight run; leaving them there while real funds are in play
# would allow a 30% account drawdown before the breaker acts.
#
# At the strategy's own 0.5% risk per trade these are not tight: a 10% breaker
# needs 20 consecutive full stop-outs to trip, and the measured loss streak
# distribution at a 24% win rate makes 6 in a row ordinary - which is why the
# streak gate is a WARNING mechanism and the drawdown gate is the real control.
MAX_DD_PCT = 10.0
MAX_LOSS_STREAK = 6


@dataclass
class Verdict:
    active: bool
    n: int
    mean_r: float
    reason: str
    dd_pct: float = 0.0        # peak-to-trough drawdown in account %
    net_pct: float = 0.0       # cumulative account % contributed
    streak: int = 0            # current consecutive-loss run
    tripped: bool = False      # the RISK gate fired (latching)


def _read_rs(sid: str) -> list[float]:
    f = LOGS / f"trades_{sid}.csv"
    if not f.exists():
        return []
    out = []
    with open(f, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            try:
                out.append(float(row["R"]))
            except (KeyError, ValueError, TypeError):
                pass
    return out


def risk_stats(rs: list[float], risk_pct: float) -> tuple[float, float, int]:
    """(drawdown %, net %, loss streak) in ACCOUNT percent terms.

    R is scale-free; R * risk_pct converts it to account impact. The peak
    starts at 0, so a strategy that only ever loses trips on its losses and one
    that gives back gains trips on the giveback - one rule covers both.
    """
    peak = cum = dd = 0.0
    streak = 0
    for r in rs:
        cum += r * risk_pct
        peak = max(peak, cum)
        dd = max(dd, peak - cum)
        streak = streak + 1 if r < 0 else 0
    return dd, cum, streak


def evaluate(sid: str, currently_active: bool = True,
             risk_pct: float | None = None, tripped: bool = False) -> Verdict:
    """Decide whether a strategy should keep trading.

    risk_pct: account % risked per trade. Required for the circuit breaker -
              without it only the statistical gate runs.
    tripped:  the latched breaker state from the caller's saved state.
    """
    rs = _read_rs(sid)
    n = len(rs)
    dd = net = 0.0
    streak = 0
    if risk_pct:
        dd, net, streak = risk_stats(rs, risk_pct)

    def V(active, reason, trip=False):
        window = rs[-LOOKBACK:] if n else []
        mean = sum(window) / len(window) if window else 0.0
        return Verdict(active, n, mean, reason, dd, net, streak, trip)

    # --- gate 2 first: a risk control outranks a statistical opinion --------
    if risk_pct:
        if tripped:
            return V(False, f"breaker LATCHED (dd {dd:.1f}% of account) - "
                            f"needs a manual reset", trip=True)
        if dd >= MAX_DD_PCT:
            return V(False, f"CIRCUIT BREAKER: drawdown {dd:.1f}% of account "
                            f">= {MAX_DD_PCT}% after only {n} trades", trip=True)
        if streak >= MAX_LOSS_STREAK:
            return V(False, f"CIRCUIT BREAKER: {streak} consecutive losses "
                            f">= {MAX_LOSS_STREAK}", trip=True)

    # --- gate 1: statistical -----------------------------------------------
    if n < MIN_TRADES:
        return V(True, f"sample too small ({n}/{MIN_TRADES}) - staying active")
    window = rs[-LOOKBACK:]
    mean_r = sum(window) / len(window)
    if currently_active:
        if mean_r < CUT_BELOW:
            return V(False, f"DEACTIVATED: mean R {mean_r:+.3f} over last {len(window)}")
        return V(True, f"active: mean R {mean_r:+.3f}")
    # currently inactive -> require a clearly positive stretch to come back
    if mean_r > REVIVE_ABOVE:
        return V(True, f"REACTIVATED: mean R {mean_r:+.3f} over last {len(window)}")
    return V(False, f"still inactive: mean R {mean_r:+.3f}")


def _risk_of(risk_pcts, sid: str) -> float | None:
    if risk_pcts is None:
        return None
    if isinstance(risk_pcts, dict):
        return risk_pcts.get(sid)
    return float(risk_pcts)


def refresh(state: dict, strategy_ids: list[str], log_fn,
            risk_pcts: dict[str, float] | float | None = None) -> dict:
    """Update {sid: active} in place, logging transitions. Returns the map.

    risk_pcts: per-strategy (dict) or shared (float) account % risked per
               trade. Pass it to arm the circuit breaker.
    """
    flags = state.setdefault("_active", {sid: True for sid in strategy_ids})
    trips = state.setdefault("_tripped", {})
    for sid in strategy_ids:
        was = flags.get(sid, True)
        v = evaluate(sid, was, _risk_of(risk_pcts, sid), bool(trips.get(sid)))
        if v.tripped and not trips.get(sid):
            log_fn(f"[BREAKER] {sid}: {v.reason}")
            log_fn(f"[BREAKER] {sid}: LATCHED OFF - manual reset required "
                   f"(net {v.net_pct:+.1f}% of account over {v.n} trades)")
            trips[sid] = True
        elif v.active != was:
            log_fn(f"[adaptive] {sid}: {v.reason}")
        flags[sid] = v.active
    return flags


def reset_breaker(state: dict, sid: str | None = None) -> list[str]:
    """Manually close the breaker again. sid=None resets all. Returns what was
    reset. This is deliberately a human action - see module docstring."""
    trips = state.setdefault("_tripped", {})
    done = [k for k in trips if (sid is None or k == sid) and trips[k]]
    for k in done:
        trips[k] = False
        state.setdefault("_active", {})[k] = True
    return done
