"""THE v2 '$20 ORDER BOOK BOT' BRACKETS (4/4, 6/6, 8/8, 12/12 bp, 120 s) FROM RANDOM ENTRIES (a baseline, not a strategy test).

WHY
    The remediation spec (Downloads/orderbook_bot_20usd_v2_remediation_spec.md) replaces the first spec's +0.25% / -0.35% bracket with
    symmetric brackets of 4, 6, 8 and 12 bp over 90-120 s and asks for a pass bar of 'more than +4.5 bp gross a trade'. CLAUDE.md s2: a signal is
    judged against a RANDOM entry with the same bracket. This file prices that bracket with Hyperliquid's published base fees
    (maker 1.5 bp, taker 4.5 bp; the target exit is a maker, the stop is a taker, the entry is a maker).

METHOD
    Same as backtest/spec_bracket_baseline.py but 2 one-minute bars (120 s) and four symmetric brackets. LIMIT: a 1-minute bar cannot say which of
    a +8 bp and a -8 bp level was touched first when both were, so every cell is shown with the tie as a STOP (pessimistic) and as HALF AND HALF.
    Timeouts: exit as a maker (3 bp round trip, the spec's 90 s scratch - optimistic) or as a taker (6 bp - the 120 s forced exit - pessimistic).
    No spread, no fill selection (the real entry fills only when price comes to it, and those fills were the signal's failures in
    book_hist.py), no slippage. Binance perp bars, DOGE and BTC, 2022-01..2026-08.

PREDICTED BEFORE RUNNING (2026-11-06): break-even target-first share among decided trades 91% / 80% / 74% / 67% for 4 / 6 / 8 / 12 bp (arithmetic:
    a win nets tp - 3 bp, a stop costs sl + 6 bp); random entries lose 3-6 bp a trade at every bracket; the wider the bracket the smaller the loss.
RESULT (logs/spec_v2_bracket_baseline.txt): see the log; the docstring is updated with it below.
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
N = 2                                  # 120 s = two one-minute bars
MAKER, TAKER = 1.5, 4.5                # bp, Hyperliquid base rates (tier 0)
BRACKETS = (4.0, 6.0, 8.0, 12.0)


def load(sym):
    d = pd.read_parquet(ROOT / "strategy_analysis" / "data" / "min1" / f"{sym}USDT_1m.parquet").sort_values("time").reset_index(drop=True)
    return d.rename(columns={"time": "t", "o": "open", "h": "high", "l": "low", "c": "close"})[["t", "open", "high", "low", "close"]]


def outcomes(h, l, c, side, tp_bp, sl_bp, n=N):
    """(code per entry, return at timeout in bp): +1 target first, -1 stop first, 2 both touched in the same first bar (a tie), 0 timeout."""
    m = len(c) - n
    c0 = c[:m]
    code = np.zeros(m, int)
    done = np.zeros(m, bool)
    for k in range(1, n + 1):
        hk, lk = h[k:k + m], l[k:k + m]
        if side == "long":
            tp, sl = hk >= c0 * (1 + tp_bp / 1e4), lk <= c0 * (1 - sl_bp / 1e4)
        else:
            tp, sl = lk <= c0 * (1 - tp_bp / 1e4), hk >= c0 * (1 + sl_bp / 1e4)
        new_tie = tp & sl & ~done
        new_tp = tp & ~sl & ~done
        new_sl = sl & ~tp & ~done
        code[new_tie], code[new_tp], code[new_sl] = 2, 1, -1
        done |= new_tie | new_tp | new_sl
    ret = (c[n:n + m] / c0 - 1) * 1e4 * (1 if side == "long" else -1)
    return code, ret


def ev(code, ret, tp_bp, sl_bp, tie, to_maker):
    p_tp, p_sl, p_tie, p_to = (code == 1).mean(), (code == -1).mean(), (code == 2).mean(), (code == 0).mean()
    if tie == "half":
        p_tp, p_sl = p_tp + p_tie / 2, p_sl + p_tie / 2
    else:
        p_sl += p_tie
    to_cost = 2 * MAKER if to_maker else MAKER + TAKER
    mean_to = ret[code == 0].mean() if (code == 0).any() else 0.0
    return p_tp * (tp_bp - 2 * MAKER) + p_sl * (-(sl_bp + MAKER + TAKER)) + p_to * (mean_to - to_cost), p_tp, p_sl, p_tie, p_to


def selftest():
    # entry close 100.00; bar1 high 100.10 (+10 bp) low 99.99 -> a +8 bp target is touched first; a flat second bar
    h = np.array([100.0, 100.10, 100.0, 100.0]); l = np.array([100.0, 99.99, 100.0, 100.0]); c = np.array([100.0, 100.05, 100.0, 100.0])
    code, _ = outcomes(h, l, c, "long", 8.0, 8.0)
    assert code[0] == 1, code
    # both +8 bp and -8 bp touched inside one bar -> a tie
    h2 = np.array([100.0, 100.10, 100.0, 100.0]); l2 = np.array([100.0, 99.90, 100.0, 100.0])
    code2, _ = outcomes(h2, l2, c, "long", 8.0, 8.0)
    assert code2[0] == 2, code2
    # nothing touched in two bars -> timeout, return measured at the second bar's close
    h3 = np.array([100.0, 100.02, 100.03, 100.0]); l3 = np.array([100.0, 99.98, 99.97, 100.0]); c3 = np.array([100.0, 100.01, 100.02, 100.0])
    code3, ret3 = outcomes(h3, l3, c3, "long", 8.0, 8.0)
    assert code3[0] == 0 and abs(ret3[0] - 2.0) < 1e-9, (code3, ret3)
    # the arithmetic of the fees: a win nets tp - 3, a stop costs sl + 6
    code4 = np.array([1, -1]); ret4 = np.array([0.0, 0.0])
    e, *_ = ev(code4, ret4, 8.0, 8.0, "stop", True)
    assert abs(e - (0.5 * 5.0 + 0.5 * -14.0)) < 1e-9, e


def main():
    selftest()
    L = [f"backtest/spec_v2_bracket_baseline.py; random entries, 120 s (2 one-minute bars), Hyperliquid base fees (maker {MAKER} bp, taker {TAKER} bp)",
         "break-even target-first share among DECIDED trades = (sl + 6) / ((sl + 6) + (tp - 3)):"
         + ", ".join(f" {b:.0f} bp {(b + 6) / ((b + 6) + (b - 3)):.0%}" for b in BRACKETS)]
    for sym in ("DOGE", "BTC"):
        d = load(sym)
        h, l, c = (d[k].to_numpy(float) for k in ("high", "low", "close"))
        L += ["", f"{sym}: {len(d):,} one-minute bars {d.t.iloc[0]:%Y-%m-%d} .. {d.t.iloc[-1]:%Y-%m-%d}",
              f"  {'bracket':>8}{'side':>6}{'target':>8}{'stop':>7}{'tie':>6}{'timeout':>9}{'target share':>13}{'EV tie=stop, taker exit':>25}{'tie=half, maker exit':>22}"]
        for b in BRACKETS:
            for side in ("long", "short"):
                code, ret = outcomes(h, l, c, side, b, b)
                pess, p_tp, p_sl, p_tie, p_to = ev(code, ret, b, b, "stop", False)
                opt, q_tp, q_sl, *_ = ev(code, ret, b, b, "half", True)
                dec = (code == 1).mean() / max((code == 1).mean() + (code == -1).mean() + (code == 2).mean() / 2, 1e-12)
                L.append(f"  {b:>5.0f}/{b:<2.0f}{side:>6}{(code == 1).mean():>8.1%}{(code == -1).mean():>7.1%}{p_tie:>6.1%}{p_to:>9.1%}"
                         f"{dec:>13.0%}{pess:>+22.2f} bp{opt:>+19.2f} bp")
    txt = "\n".join(L)
    print(txt)
    (ROOT / "logs" / "spec_v2_bracket_baseline.txt").write_text(txt + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
