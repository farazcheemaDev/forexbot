"""BUY THE DIP / SELL THE RIP - ONLY WHEN THE MARKET IS CHOPPY (2026-10-18)

The sideways-gap search (chop_gap.py, chop_switch.py). Mean reversion is the textbook sideways-market trade and has died
here every time (doc 20: bear_chop.py's reversal and gated mean reversion; doc 02: rsi_only.py - the retail RSI trade
wins 76-95% of trades in every year and loses the money in trending years). What killed it is TRENDS. Never tried: gate it
by a measured CHOP METER - Kaufman's efficiency ratio (ER = |net move| / sum of daily moves; low = going nowhere), the
meter that made chop_switch.py's G4 the one interesting trend gate.

    universe   point-in-time top-40 perps by the prior month's volume (dead coins in), crypto only; daily closes
    signal     at a coin's close: below its 20-day mean by 2 standard deviations -> LONG; above by 2 -> SHORT
    exits      back to the 20-day mean, or 10 days, or 10% against (all at a close)
    fill       the NEXT day's close (no same-bar fill); fees 12bp round trip; funding charged on the side held
    book       up to 10 positions at 1/10 of equity each, 1x, first signals first (ties by volume rank)
    gates      NONE | MARKET (BTC's 30-day ER < 0.25, the day before) | COIN (the coin's own 20-day ER < 0.30) | BOTH
    halves     tune before 2024-08-29, holdout after; by BTC regime month (market_neutral.btc_regime)
REGISTERED BEFORE THE RUN (2026-10-18)
    R1 ungated, it loses on both halves (doc 20).
    R2 no gate makes it positive on BOTH halves after fees.
    R3 in sideways months the BOTH-gated book's average month is above the ungated one's (the gate does what it says),
       whatever its sign.

RESULT (2026-10-18, logs/chop_revert.txt) - DEAD; R1 / R2 / R3 RIGHT. Ungated -54% / -41% a year (tune / holdout);
the chop meter halves the loss (BOTH: -13% / -21%) and still loses in sideways months (-2.0% average). Coins stretched 2
standard deviations keep going - the daily BREAKOUT book is the other side of this trade. Positions' direction checked.
rsi_chop.py adds RSI signals (sig='rsi14' / 'rsi2') to run().

    python -m backtest.chop_revert
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

LOG = ROOT / "logs" / "chop_revert.txt"
CUT = pd.Timestamp("2024-08-29")
N_MEAN, K_SD, MAX_DAYS, STOP, SLOTS, FEE = 20, 2.0, 10, 0.10, 10, 12e-4


def data():
    from backtest.market_neutral import btc_regime, drop_non_crypto, load_panel
    from backtest.wide_book import eligibility
    C, F, first = load_panel()
    elig = drop_non_crypto(eligibility(40))
    b = C["BTCUSDT"]
    er_btc = ((b - b.shift(30)).abs() / b.diff().abs().rolling(30).sum()).shift(1)
    er_coin = (C - C.shift(N_MEAN)).abs() / C.diff().abs().rolling(N_MEAN).sum()
    return C, F, elig, er_btc, er_coin, btc_regime(C)


def rsi(C: pd.DataFrame, n: int) -> pd.DataFrame:
    """Wilder's RSI on daily closes."""
    d = C.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))


def run(C, F, elig, er_btc, er_coin, gate: str, sig: str = "z") -> pd.Series:
    """The book's daily return (on equity, 1x, 10 slots). sig 'z' = 2 standard deviations from the 20-day mean, out at
    the mean; 'rsi14' = RSI(14) under 30 / over 70, out when it crosses 50; 'rsi2' = RSI(2) under 10 / over 90, same exit."""
    mu, sd = C.rolling(N_MEAN).mean(), C.rolling(N_MEAN).std()
    z = (C - mu) / sd
    if sig != "z":
        n, lo = (14, 30.0) if sig == "rsi14" else (2, 10.0)
        R = rsi(C, n)
        # beyond the thresholds: |z| >= K_SD, ranked by how far RSI is from 50; inside them: 0 (no signal)
        z = pd.DataFrame(np.where(R < lo, -(K_SD + (50 - R) / 50), np.where(R > 100 - lo, K_SD + (R - 50) / 50, 0.0)),
                         index=C.index, columns=C.columns).where(R.notna())
    Rv = rsi(C, 14 if sig == "rsi14" else 2).to_numpy() if sig != "z" else None
    idx, cols = C.index, list(C.columns)
    month = idx.strftime("%Y-%m")
    pos: dict = {}                                           # coin -> (side, entry px, entry i)
    pending: dict = {}                                       # coin -> side, filled at the next close
    out = np.zeros(len(idx))
    Cv, Zv, Mv, Fv = C.to_numpy(), z.to_numpy(), mu.to_numpy(), F.to_numpy()
    ERc = er_coin.to_numpy()
    col = {c: j for j, c in enumerate(cols)}
    for i in range(N_MEAN + 31, len(idx)):
        day = 0.0
        # 1. fill yesterday's signals at today's close (no P&L today for them)
        for c, side in list(pending.items()):
            px = Cv[i, col[c]]
            if np.isfinite(px) and len(pos) < SLOTS and c not in pos:
                pos[c] = (side, px, i)
                day -= FEE / 2 / SLOTS
        pending = {}
        # 2. mark and exit open positions on today's close
        for c, (side, e, i0) in list(pos.items()):
            j = col[c]
            p0, p1 = Cv[i - 1, j], Cv[i, j]
            if i0 == i:
                continue
            if not (np.isfinite(p0) and np.isfinite(p1)):
                pos.pop(c)                                   # no price: out at the last mark
                day -= FEE / 2 / SLOTS
                continue
            day += side * (p1 / p0 - 1) / SLOTS - side * Fv[i, j] / SLOTS
            if Rv is None:
                back = (side > 0 and p1 >= Mv[i, j]) or (side < 0 and p1 <= Mv[i, j])
            else:                                            # RSI back through 50
                back = (side > 0 and Rv[i, j] >= 50) or (side < 0 and Rv[i, j] <= 50)
            if back or i - i0 >= MAX_DAYS or side * (p1 / e - 1) <= -STOP:
                pos.pop(c)
                day -= FEE / 2 / SLOTS
        out[i] = day
        # 3. today's signals, filled tomorrow
        if gate in ("MARKET", "BOTH"):
            v = er_btc.iloc[i]
            if not (v == v and v < 0.25):
                continue
        free = SLOTS - len(pos)
        if free <= 0:
            continue
        cands = []
        for c in cols:
            if c in pos or month[i] not in elig.get(c, ()):
                continue
            j = col[c]
            zz = Zv[i, j]
            if not np.isfinite(zz) or abs(zz) < K_SD:
                continue
            if gate in ("COIN", "BOTH") and not (ERc[i, j] == ERc[i, j] and ERc[i, j] < 0.30):
                continue
            cands.append((-abs(zz), c, -1 if zz > 0 else 1))
        for _, c, side in sorted(cands)[:free]:
            pending[c] = side
    return pd.Series(out, index=idx)


def stats(r: pd.Series) -> tuple:
    r = r[r.index >= r.ne(0).idxmax()] if r.ne(0).any() else r
    if len(r) < 30:
        return (np.nan,) * 3
    c = (1 + r).cumprod()
    yrs = len(r) / 365.0
    return c.iloc[-1] ** (1 / yrs) - 1, float((1 - c / c.cummax()).max()), r.mean() / r.std() * np.sqrt(365) if r.std() else np.nan


def main():
    C, F, elig, er_btc, er_coin, reg = data()
    lab = reg.groupby(reg.index.to_period("M")).agg(lambda s: s.value_counts().idxmax())
    lines = [f"backtest/chop_revert.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; PIT top-40, daily closes, "
             f"{C.index[0]:%Y-%m-%d} .. {C.index[-1]:%Y-%m-%d}; z {K_SD} of a {N_MEAN}-day mean, out at the mean / "
             f"{MAX_DAYS} days / {STOP:.0%} stop; next-close fill; 12bp + funding; 10 slots, 1x", "",
             f"   {'gate':<8}{'tune CAGR':>11}{'fall':>6}{'Sharpe':>7}{'hold CAGR':>11}{'fall':>6}{'Sharpe':>7}"
             f"{'  avg month: bull':>18}{'chop':>8}{'bear':>8}{'  days in market':>17}"]
    res = {}
    for gate in ("NONE", "MARKET", "COIN", "BOTH"):
        r = run(C, F, elig, er_btc, er_coin, gate)
        tu, ho = stats(r[r.index < CUT]), stats(r[r.index >= CUT])
        m = (1 + r).groupby(r.index.to_period("M")).prod() - 1
        mr = pd.DataFrame({"m": m, "reg": lab.reindex(m.index)}).dropna()
        av = {g: mr[mr.reg == g].m.mean() for g in ("bull", "chop", "bear")}
        res[gate] = (tu, ho, av)
        lines.append(f"   {gate:<8}{tu[0] * 100:>+10.1f}%{tu[1] * 100:>5.0f}%{tu[2]:>7.2f}{ho[0] * 100:>+10.1f}%"
                     f"{ho[1] * 100:>5.0f}%{ho[2]:>7.2f}{av['bull'] * 100:>+15.2f}%{av['chop'] * 100:>+7.2f}%"
                     f"{av['bear'] * 100:>+7.2f}%{(r != 0).mean() * 100:>14.0f}%")
        print(lines[-1], flush=True)
    r1 = res["NONE"][0][0] < 0 and res["NONE"][1][0] < 0
    pos2 = [g for g in res if res[g][0][0] > 0 and res[g][1][0] > 0]
    r3 = res["BOTH"][2]["chop"] > res["NONE"][2]["chop"]
    lines += ["", "REGISTERED PREDICTIONS",
              f"  R1 ungated loses on both halves ({res['NONE'][0][0] * 100:+.1f}% / {res['NONE'][1][0] * 100:+.1f}%) -> "
              f"{'RIGHT' if r1 else 'WRONG'}",
              f"  R2 no gate positive on both halves -> {'RIGHT' if not pos2 else 'WRONG'} ({', '.join(pos2) or 'none'})",
              f"  R3 BOTH-gated sideways average month {res['BOTH'][2]['chop'] * 100:+.2f}% above ungated "
              f"{res['NONE'][2]['chop'] * 100:+.2f}% -> {'RIGHT' if r3 else 'WRONG'}"]
    txt = "\n".join(lines)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
