"""TAKE THE UNUSUAL PROFIT EARLY? - the daily book's pumps and the market-neutral basket's good weeks (2026-10-20)

The user, after the MN book was +$3.83 on 2026-10-19 and -$3.43 a day later, and BTW (held long by three books) ran
+46% then fell 19% in a day: "for unusual profits like the coin BTW we should take profit and exit early, because if they
return good they can bear fast". Two books hold such runs to a rule exit; neither has a take-profit:

PART A - THE DAILY BOOK (Bollinger(30, 1.5) breakouts on the PIT top-40, out under the 20-day mean, x0.5, 8 slots)
    TP +30% / +50% / +100%     a resting take-profit at the entry + X (filled inside the bar, at the open on a gap)
    PROTECT (+30%, 15%)         once a close is +30% over entry, out the next open after a close 15% under the best close
    PROTECT (+50%, 20%)         the same, armed at +50%, 20% from the best
    (daily_combos.gen's new cfg keys tp / ptrail; off by default - every earlier result unchanged)
PART B - THE MARKET-NEUTRAL BOOK (half 30-day momentum / half RSI(14) ranked, 10% each side, weekly, +50% short exit)
    TP +2 / +3 / +5 / +8%       the combined basket (both halves, funding to date) closed at the first daily close at or
                                above +X% of the book within its week; flat until the next rebalance (closing fee, and the
                                next week opens from flat)
    GIVE-BACK (+3% -> +1.5%)    armed at +3%, closed if it falls back to +1.5%
    paths rebuilt from mn_combos' own data; with the rule off they reproduce moderate_retests.scored_run (asserted)
JUDGED inside the 9-book machine (all_books.machine_books, 10 orderings; $300, 12 months; tune before 2024-08-29) and alone.
PASS: the machine's typical year >= the deployed rule's on BOTH halves, no deeper fall on either.

REGISTERED BEFORE THE RUN (2026-10-20)
    D1 no fixed take-profit improves the daily book on both halves (its edge IS the pumps: doc 02, daily_stack).
    D2 protect-the-profit improves at most one half.
    N1 no MN take-profit passes inside the machine.
    N2 the MN take-profits move the MN book's worst week by less than 2 points (bad weeks never reach the target).

RESULT (2026-10-20, logs/profit_take.txt) - DEAD both ways; D1 / D2 / N1 RIGHT, N2 WRONG (TP +2% softens the worst week).
    Both rebuilt books reproduce the deployed ones exactly (asserted). Machine typical year, tune / holdout ($3,927 /
    $9,416 deployed): daily TP +30% $3,672 / $6,271, +50% $3,620 / $7,007, +100% $3,635 / $8,050, PROTECT +30%/15%
    $3,495 / $7,276, +50%/20% $3,685 / $7,741 - falls unchanged. The early exits cut the pumps that KEPT going, which
    pay for the book. MN: TP +2% $3,614 / $5,665 (worst week -21.1% -> -15.6%), +3% $3,677 / $6,265, +5% $3,692 /
    $6,405, +8% $3,911 / $6,556, give-back +3% -> +1.5% $3,907 / $8,884. Hold-to-rule stays.

    python -m backtest.profit_take
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

LOG = ROOT / "logs" / "profit_take.txt"
DAILY_V = {"deployed (20-day mean)": {}, "TP +30%": dict(tp=0.30), "TP +50%": dict(tp=0.50), "TP +100%": dict(tp=1.00),
           "PROTECT +30% / 15%": dict(ptrail=(0.30, 0.15)), "PROTECT +50% / 20%": dict(ptrail=(0.50, 0.20))}
MN_V = {"deployed (hold the week)": None, "TP +2%": ("tp", 0.02), "TP +3%": ("tp", 0.03), "TP +5%": ("tp", 0.05),
        "TP +8%": ("tp", 0.08), "GIVE-BACK +3% -> +1.5%": ("gb", 0.03, 0.015)}


# ------------------------------------------------------------------ the MN book, day by day inside each week

def mn_weeks(score_mat, start, short_stop=0.5):
    """scored_run(score_mat, start, stop='short_only', short_stop) week by week, with the basket's daily path."""
    from backtest import mn_combos as m
    Dd = m.ohl()
    idx, X_, Fx, ff = Dd["idx"], Dd["X"], Dd["Fx"], Dd["ff"]
    hold, look, frac = 7, 30, 0.1
    out = []
    for i in range(look + 1 + start, len(idx) - hold - 1, hold):
        t0 = idx[i]
        ok = (Dd["Em"][Dd["months"][i]] & ((t0.value - Dd["fv"]) // 86_400_000_000_000 >= m.MIN_AGE_D)
              & np.isfinite(X_[i]) & np.isfinite(X_[i - look]))
        if ok.sum() < 20:
            continue
        cand = np.flatnonzero(ok)
        past = score_mat[i, cand]
        k = max(int(len(cand) * frac), 3)
        order = cand[np.argsort(np.where(np.isnan(past), np.inf, past), kind="stable")]
        sh, lo = order[:k], order[-k:]
        P = np.array([ff[i + d] / X_[i] - 1 for d in range(1, hold + 1)])          # [day, coin]
        stopped = {}
        for x in sh:
            lvl = X_[i, x] * (1 + short_stop)
            for dd in range(i + 1, i + hold + 1):
                if np.isfinite(Dd["Hi"][dd, x]) and Dd["Hi"][dd, x] >= lvl:
                    stopped[x] = (dd - i, max(Dd["Op"][dd, x], lvl) / X_[i, x] - 1)
                    break
        for x, (d0, r) in stopped.items():
            P[d0 - 1:, x] = r
        gross = 0.5 * P[:, lo].mean(axis=1) - 0.5 * P[:, sh].mean(axis=1)            # by day 1..hold
        F = np.cumsum(Fx[i + 1:i + hold + 1], axis=0)
        carry = 0.5 * (-F[:, lo].mean(axis=1)) + 0.5 * F[:, sh].mean(axis=1)
        out.append(dict(i=i, t_end=t0 + pd.Timedelta(days=hold), k=k, path=gross + carry,
                        L={Dd["cols"][x] for x in lo}, S={Dd["cols"][x] for x in sh}))
    return out


def mn_series(weeks_a, weeks_b, rule):
    """The combined book (half a / half b) per week, net of costs, booked at the week's end, under a take-profit rule."""
    from backtest import mn_combos as m
    pa = {w["i"]: w for w in weeks_a}
    pb = {w["i"]: w for w in weeks_b}
    prev = {"a": (set(), set()), "b": (set(), set())}
    rows = []
    for i in sorted(set(pa) & set(pb)):
        wa, wb = pa[i], pb[i]
        v = 0.5 * wa["path"] + 0.5 * wb["path"]
        d_exit = len(v)
        if rule is not None:
            if rule[0] == "tp":
                hit = np.flatnonzero(v[:-1] >= rule[1])
                d_exit = int(hit[0]) + 1 if len(hit) else d_exit
            else:
                armed = np.maximum.accumulate(v) >= rule[1]
                hit = np.flatnonzero(armed[:-1] & (v[:-1] <= rule[2]))
                d_exit = int(hit[0]) + 1 if len(hit) else d_exit
        net = v[d_exit - 1]
        cost = 0.0
        for key, w in (("a", wa), ("b", wb)):
            pl_, ps_ = prev[key]
            cost += 0.5 * m.FEE * min((len(w["L"] ^ pl_) + len(w["S"] ^ ps_)) / (4 * w["k"]), 1.0)
            if d_exit < len(v):                                   # closed early: pay the close, next week opens from flat
                cost += 0.5 * m.FEE * 0.5
                prev[key] = (set(), set())
            else:
                prev[key] = (w["L"], w["S"])
        rows.append((w["t_end"], net - cost, d_exit < len(v)))
    s = pd.Series([r[1] for r in rows], index=pd.DatetimeIndex([r[0] for r in rows])).groupby(level=0).sum()
    return s, float(np.mean([r[2] for r in rows]))


def score_mats():
    from backtest import mn_combos as m
    D = m.data()
    C = pd.DataFrame(D["X"])
    d = C.diff()
    up = d.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    rsi = (100 - 100 / (1 + up / dn.replace(0, np.nan))).to_numpy()
    mom = D["X"] / np.r_[np.full((30, D["X"].shape[1]), np.nan), D["X"][:-30]] - 1
    return mom, rsi


# ------------------------------------------------------------------ judging

def book_stats(r: pd.Series, cut):
    out = {}
    for half, x in (("tune", r[r.index < cut]), ("holdout", r[r.index >= cut])):
        c = (1 + x).cumprod()
        yrs = max((x.index[-1] - x.index[0]).days / 365.25, 0.25)
        out[half] = (c.iloc[-1] ** (1 / yrs) - 1, float((1 - c / c.cummax()).max()))
    return out


def main():
    from backtest import daily_combos as dc
    from backtest import machine_combos as mc
    from backtest.all_books import BOOKS, machine_books, ndx_dip, news_book
    from backtest.machine import CUT, summary
    from backtest.moderate_retests import scored_run
    M = machine_books()
    nw, nd = news_book(), ndx_dip()

    RUNNING = [b for b in BOOKS if b != "bids"]          # the running final bot has no crash desk (no --wick)

    def machine(col: str, series_by_seed: list) -> list:
        out = []
        for x, s in zip(M, series_by_seed):
            y = x[RUNNING].copy()
            y[col] = s.reindex(x.index).fillna(0.0)
            out.append(y.sum(axis=1) + nw.reindex(x.index).fillna(0.0) + nd.reindex(x.index).fillna(0.0))
        return out

    lines = [f"backtest/profit_take.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; the 9-book machine, $300, 12 months, "
             f"10 orderings; trend gains shrunk, the rest raw", "",
             "PART A - THE DAILY BOOK",
             f"   {'rule':<26}{'machine typ tune':>17}{'holdout':>9}{'fall':>8}{'worst mo':>10}{'   book alone CAGR tune':>24}"
             f"{'holdout':>9}{'  exits by the rule':>20}"]
    A = {}
    for name, extra in DAILY_V.items():
        T = {off: dc.gen(off, dict(dc.BASE, mean_n=20, **extra)) for off in dc.PHASES}
        ser = []
        for sd, x in zip(mc.SEEDS, M):
            off = dc.PHASES[sd % 3]
            s = 0.5 * dc.curve(T[off], dc.allocate(T[off], sd), off).pct_change()
            s = s.reindex(x.index).fillna(0.0)
            if not extra:
                assert np.allclose(s.to_numpy(), x["daily"].to_numpy(), atol=1e-12), "the deployed daily book is not reproduced"
            ser.append(s)
        daily = machine("daily", ser)
        st, sh = summary([x[x.index < CUT] for x in daily]), summary(daily, CUT)
        bs = [book_stats(s[s.ne(0).idxmax():], CUT) for s in ser]
        bt, bh = np.median([b["tune"][0] for b in bs]), np.median([b["holdout"][0] for b in bs])
        share = np.mean([(T[o].why.isin(["tp", "ptrail"])).mean() for o in T])
        A[name] = (st, sh)
        lines.append(f"   {name:<26}${st['typ']:>15,.0f} ${sh['typ']:>7,.0f}{st['dd']:>4.0f}/{sh['dd']:<3.0f}{st['wm']:>+5.0f}/{sh['wm']:<+4.0f}"
                     f"{bt * 100:>+21.0f}%{bh * 100:>+8.0f}%{share * 100:>17.0f}%")
        print(lines[-1], flush=True)
    mom, rsi = score_mats()
    lines += ["", "PART B - THE MARKET-NEUTRAL BOOK",
              f"   {'rule':<26}{'machine typ tune':>17}{'holdout':>9}{'fall':>8}{'worst mo':>10}{'   book alone CAGR tune':>24}"
              f"{'holdout':>9}{'worst wk':>9}{'  weeks closed early':>21}"]
    W = {}
    for o in sorted({sd % 7 for sd in mc.SEEDS}):
        W[o] = (mn_weeks(mom, o), mn_weeks(rsi, o))
        ref = (0.5 * scored_run(mom, start=o, stop="short_only", short_stop=0.5)).add(
            0.5 * scored_run(rsi, start=o, stop="short_only", short_stop=0.5), fill_value=0.0)
        mine, _ = mn_series(*W[o], None)
        a, b = mine.reindex(ref.index).fillna(0.0), ref
        assert np.allclose(a.to_numpy(), b.to_numpy(), atol=1e-10), f"MN weeks do not reproduce scored_run, start {o}"
    B = {}
    for name, rule in MN_V.items():
        ser, early, worst = [], [], []
        for sd, x in zip(mc.SEEDS, M):
            s, e = mn_series(*W[sd % 7], rule)
            ser.append(s.reindex(x.index).fillna(0.0))
            early.append(e)
            worst.append(s.min())
        if rule is None:
            for s, x in zip(ser, M):
                assert np.allclose(s.to_numpy(), x["mn_blend"].to_numpy(), atol=1e-10), "the deployed MN book is not reproduced"
        daily = machine("mn_blend", ser)
        st, sh = summary([x[x.index < CUT] for x in daily]), summary(daily, CUT)
        bs = [book_stats(s[s.ne(0).idxmax():], CUT) for s in ser]
        bt, bh = np.median([b["tune"][0] for b in bs]), np.median([b["holdout"][0] for b in bs])
        B[name] = (st, sh, float(np.median(worst)))
        lines.append(f"   {name:<26}${st['typ']:>15,.0f} ${sh['typ']:>7,.0f}{st['dd']:>4.0f}/{sh['dd']:<3.0f}{st['wm']:>+5.0f}/{sh['wm']:<+4.0f}"
                     f"{bt * 100:>+21.0f}%{bh * 100:>+8.0f}%{np.median(worst) * 100:>+8.1f}%{np.mean(early) * 100:>18.0f}%")
        print(lines[-1], flush=True)

    def passes(R, base, name):
        return all(R[name][h]["typ"] >= R[base][h]["typ"] and R[name][h]["dd"] <= R[base][h]["dd"] for h in (0, 1))
    Ad = {k: v for k, v in A.items()}
    a_pass = [n for n in A if n != "deployed (20-day mean)" and passes(Ad, "deployed (20-day mean)", n)]
    b_pass = [n for n in B if n != "deployed (hold the week)" and passes(B, "deployed (hold the week)", n)]
    both = lambda n, base, R: all(R[n][h]["typ"] > R[base][h]["typ"] for h in (0, 1))  # noqa: E731
    d1 = not any(both(n, "deployed (20-day mean)", A) for n in A if n.startswith("TP"))
    d2 = not any(both(n, "deployed (20-day mean)", A) for n in A if n.startswith("PROTECT"))
    n2 = all(abs(B[n][2] - B["deployed (hold the week)"][2]) < 0.02 for n in B)
    lines += ["", f"   PASSED (typical year >= deployed on both halves, no deeper fall): daily {a_pass or 'none'}; MN {b_pass or 'none'}",
              "", "REGISTERED PREDICTIONS",
              f"  D1 no fixed take-profit improves the daily book's machine on both halves -> {'RIGHT' if d1 else 'WRONG'}",
              f"  D2 protect-the-profit improves at most one half -> {'RIGHT' if d2 else 'WRONG'}",
              f"  N1 no MN take-profit passes -> {'RIGHT' if not b_pass else 'WRONG'} ({', '.join(b_pass) or 'none'})",
              f"  N2 MN worst week moves < 2 points: " + ", ".join(f"{n} {B[n][2] * 100:+.1f}%" for n in B)
              + f" -> {'RIGHT' if n2 else 'WRONG'}"]
    txt = "\n".join(lines)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
