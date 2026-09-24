"""BEAR AND CHOP - six strategies the graveyard has not tested, for the days the trend book
earns nothing. Tests 1-4 are described here; 5 (shorting BTC/ETH below the gate) and 6
(funding carry) have their own docstrings below and were added during the run. Results and
verdicts: docs/02-what-failed.md, "six strategies for BEAR and CHOP markets" - all dead.

    python -m backtest.bear_chop [1 2 3 4 5 6]      (logs/bear_chop_1.txt, _2, _34, _6)

WHY
    regime_and_liq.py (logs/regime_and_liq.txt): the trend book makes +23%/mo (main) to +47%/mo
    (triple) in BULL months and ~0 in BEAR (581 days) and CHOP (948 days). 63% of days earn
    nothing. Doc 10's market-neutral momentum book already earns in chop (+1.18%/wk) and breaks
    even in bears on funding carry. This file looks for anything that earns where both are weak.

WHAT THE GRAVEYARD ALREADY KILLED (not re-tested here)
    short_families.py   17 indicator families short, 1h/4h/12h, PIT top-40 with dead coins,
                        bear-gated: no family beats RANDOM short entries.
    shortside.py        short trails 3-20xATR and short pyramids on the 12-coin book: shorts
                        best tight, negative wide.
    bear_shorts.py      new-listing shorts, pump fades (22/24 cells negative), shorting the
                        weakest coins (-0.37%/wk in bear weeks; shorting EVERYTHING +0.05%).
    bear_alpha.py       long BTC / short alts dispersion: dead.
    grid_bot.py, mean reversion x7, funding carry, funding_xs.py: dead.

THE FOUR TESTS (all on the point-in-time universe with the dead coins - no 3x haircut applies,
because nothing here was chosen with hindsight; the trend book's regime figures above ARE
haircut, which flatters it against these, so read the comparison with that asymmetry in mind)

  1. CROSS-SECTIONAL SHORT-TERM REVERSAL, market-neutral. PIT top-60. Long the 1/3/7-day
     losers, short the winners, hold 1/3/7 days, 12bp on measured turnover, actual funding.
     Ranked on the entry close (lag 0) AND one day earlier (lag 1), because a reversal ranked
     and traded on the same close partly measures the close print itself.
     market_neutral.py only tested 30/90-day lookbacks, where the sign is momentum.

  2. PAIRS TRADING (cointegration stat-arb). Never tested on crypto here (pairs_test.py was
     NASDAQ vs gold). Each month: PIT top-30, every pair, Engle-Granger on 180 days of log
     closes, keep the 10 most mean-reverting (DF t < -3, half-life 1-30 days, each coin in at
     most 2 pairs). Trade the next month: enter at |z| > 2, exit at z = 0, stop at |z| > 4,
     forced out at month end. Signal on a close, filled at the NEXT close. 12bp round trip on
     both legs, both legs' funding, a delisted leg exits at its last print.

  3. DAILY TREND SHORTS WITH PYRAMIDS, bear-gated, PIT top-40 with dead coins. The one cell
     short_families (1h-12h, one unit) and shortside (12 survivors) left open: daily bars, the
     coins that died, and adds. Close below BB(30, 1.5) -> short at the next open, stop 2xATR,
     trail 3/5/10xATR, adds every 2R up to 1/3/5 units, breakeven at 3R. Fills pessimistic: an
     add and a stop on the same bar are both assumed to happen, add first. Funding charged.
     THE CONTROL DECIDES IT: random short entries on the same coins, same days, same gate,
     same exits, at the signal's density, 10 seeds.

  4. MEAN REVERSION ONLY IN CHOP (and, separately, only in bear). Seven reversal families died
     ungated. Gated to the regime where reversal should work: close outside BB(20, 2) -> fade
     it at the next open, exit at the 20-day mean, stop 2xATR, out after 10 bars. Against
     random entries with the same direction mix, gate and exits.

REGIME: market_neutral.btc_regime (BTC vs its 50-day average and that average's 20-day slope,
shifted a day) - the same labels as regime_and_liq.py, so the rows line up.
HOLDOUT: from 2024-08-29, ts[int(len(ts) * 0.6)] of the deployed book (triple_capped.py).

REGISTERED PREDICTIONS (written 2026-09-24, before any of this was run)
  1. 1-day reversal is gross-positive at lag 0, loses more than half of it at lag 1, and is
     net-NEGATIVE after turnover at every 1-day hold. 7-day lookbacks are momentum (reversal
     negative). Best case: a 3-day cell positive in chop only. Verdict expected: dead.
  2. Pairs: small positive gross in chop, negative in bull (alts trend apart), net ~0 on the
     holdout. Most "cointegrated" pairs break within the month. Verdict expected: dead.
  3. Daily shorts earn in bears in raw R (2022 carries it) but do NOT beat random entries by a
     margin that survives across months. Pyramids raise signal and random alike. Dead as an
     edge; at most a restatement of "short beta pays in 2022".
  4. Chop-gated mean reversion does not beat random entries; net negative after fees. The bear
     gate (buying capitulation) is worse. Dead.
  If ANY of these survives both halves and its random control, the next move is to look for
  the bug that made it survive.

    python -m backtest.bear_chop
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.market_neutral import btc_regime, drop_non_crypto, load_panel, run  # noqa: E402
from backtest.wide_book import DATA, MIN_AGE_D, eligibility  # noqa: E402

FEE = 12.0 / 1e4
CUT = pd.Timestamp("2024-08-29")
SEEDS = tuple(range(10))
REGS = ("bull", "bear", "chop")


# ------------------------------------------------------------------ shared reporting

def tag(df, reg, tcol="t"):
    df = df.copy()
    df["regime"] = [reg.asof(t) if t >= reg.index[0] else "chop" for t in df[tcol]]
    df["half"] = np.where(df[tcol] < CUT, "tune", "hold")
    return df


def per_month(x, col, days_per_row):
    """mean of `col` per row, scaled to a 30.4-day month."""
    return x[col].mean() * 30.4 / days_per_row * 100 if len(x) else np.nan


# ------------------------------------------------------------------ 1. XS reversal

def fast_run(C, F, first, elig, look=30, hold=7, frac=0.1, min_names=20, lag=0, score=None,
             fshift=0):
    """market_neutral.run, vectorised over coins (the original loops over ~800 columns per
    period and a 1-day hold takes minutes per cell). SAME rules, including its quirk that a
    coin must be finite at i and i-look but is RANKED on j=i-lag, where a NaN ranks last (top).
    Checked against run() to 1e-12 in main() before anything is reported."""
    idx = C.index
    X = C.to_numpy(float)
    Fx = F.reindex(columns=C.columns).fillna(0.0).to_numpy(float)
    cols = list(C.columns)
    months = idx.strftime("%Y-%m")
    fvals = np.array([pd.Timestamp(first[s]).value for s in cols])
    Em = {m: np.array([m in elig.get(s, ()) for s in cols]) for m in sorted(set(months))}
    # last finite price at or before each row, per coin (the delisted-exit rule)
    ffill = pd.DataFrame(X).ffill().to_numpy()
    rows, prev_long, prev_short = [], set(), set()
    for i in range(look + 1, len(idx) - hold - fshift, hold):
        t0 = idx[i]
        ok = (Em[months[i]] & ((t0.value - fvals) // 86_400_000_000_000 >= MIN_AGE_D)
              & np.isfinite(X[i]) & np.isfinite(X[i - look]))
        if ok.sum() < min_names:
            continue
        j = i - lag
        cand = np.flatnonzero(ok)
        # score (test 6): any T x N matrix whose row j is known at close j; long the highest
        past = X[j, cand] / X[j - look, cand] - 1 if score is None else score[j, cand]
        k = max(int(len(cand) * frac), 3)
        order = cand[np.argsort(np.where(np.isnan(past), np.inf, past), kind="stable")]
        shorts, longs = order[:k], order[-k:]
        exitp = ffill[i + hold]
        fwd = exitp / X[i] - 1
        # fshift=0 is market_neutral.run's convention: days i..i+hold-1. But the book is held
        # from close i (00:00 of day i+1) to close i+hold, i.e. over days i+1..i+hold, so run()
        # credits the day BEFORE entry and misses the last one. Harmless-ish for a price rank;
        # look-ahead for a FUNDING rank, whose top names were picked for paying on day i.
        fnd = Fx[i + fshift:i + hold + fshift].sum(axis=0)
        lr, sr = fwd[longs].mean(), fwd[shorts].mean()
        lf, sf = fnd[longs].mean(), fnd[shorts].mean()
        gross = 0.5 * lr - 0.5 * sr
        carry = 0.5 * (-lf) + 0.5 * sf
        L_, S_ = {cols[x] for x in longs}, {cols[x] for x in shorts}
        turn = (len(L_ ^ prev_long) + len(S_ ^ prev_short)) / (2 * k * 2)
        cost = FEE * min(turn, 1.0)
        prev_long, prev_short = L_, S_
        rows.append(dict(t=t0, net=gross + carry - cost, gross=gross, carry=carry,
                         cost=cost, n=int(ok.sum()), long_ret=lr, short_ret=sr))
    return pd.DataFrame(rows)


def reversal(C, F, first, elig, look, hold, lag):
    """market_neutral.run is long-winners/short-losers. Reversal is the same baskets flipped:
    gross and carry change sign, turnover and cost do not."""
    df = fast_run(C, F, first, elig, look=look, hold=hold, lag=lag)
    df["gross"], df["carry"] = -df.gross, -df.carry
    df["net"] = df.gross + df.carry - df.cost
    return df


def test_reversal(C, F, first, reg):
    elig = drop_non_crypto(eligibility(60))
    print("\n=== 1. CROSS-SECTIONAL SHORT-TERM REVERSAL, market-neutral, PIT top-60, 1x gross")
    print("    %/month of the whole account (period mean x 30.4/hold). lag 1 = ranked a day before entry\n")
    print(f"  {'look':>4}{'hold':>5}{'lag':>4}{'net':>8}{'gross':>8}{'cost':>7}{'carry':>7}"
          f"{'TUNE':>8}{'HOLD':>8}{'bull':>8}{'bear':>8}{'chop':>8}")
    out = {}
    for look in (1, 3, 7):
        for hold in (1, 3, 7):
            for lag in (0, 1):
                d = tag(reversal(C, F, first, elig, look, hold, lag), reg)
                pm = lambda x, c="net": per_month(x, c, hold)  # noqa: E731
                out[(look, hold, lag)] = d
                print(f"  {look:>4}{hold:>5}{lag:>4}{pm(d):>+7.2f}%{pm(d, 'gross'):>+7.2f}%"
                      f"{-pm(d, 'cost'):>+6.2f}%{pm(d, 'carry'):>+6.2f}%"
                      f"{pm(d[d.half == 'tune']):>+7.2f}%{pm(d[d.half == 'hold']):>+7.2f}%"
                      + "".join(f"{pm(d[d.regime == r]):>+7.2f}%" for r in REGS))
    # the reference: doc 10's momentum book on the same report
    m = tag(fast_run(C, F, first, elig, look=30, hold=7), reg)
    pm = lambda x: per_month(x, "net", 7)  # noqa: E731
    print(f"\n  reference, doc 10 MOMENTUM (30d look, 7d hold): {pm(m):+.2f}%/mo | tune {pm(m[m.half == 'tune']):+.2f}"
          f" hold {pm(m[m.half == 'hold']):+.2f} | " + "  ".join(f"{r} {pm(m[m.regime == r]):+.2f}" for r in REGS))
    return out


# ------------------------------------------------------------------ 2. pairs

def df_stat(e):
    """Dickey-Fuller t on a residual series (no lags, no constant: e has mean 0) and half-life."""
    de, el = np.diff(e), e[:-1]
    den = (el * el).sum()
    phi = (de * el).sum() / den
    resid = de - phi * el
    se = np.sqrt((resid * resid).sum() / (len(de) - 2) / den)
    hl = -np.log(2) / np.log1p(phi) if -1 < phi < 0 else np.inf
    return phi / se, hl


def form_pairs(L, i, coins, win=180, k=10, per_coin=2, t_max=-3.0, hl_rng=(1, 30)):
    X = L[coins].iloc[i - win:i].to_numpy(float)       # closes up to i-1: formation is past-only
    cand = []
    for a in range(len(coins)):
        for b in range(a + 1, len(coins)):
            la, lb = X[:, a], X[:, b]
            vb = lb.var()
            if vb <= 0:
                continue
            beta = ((la - la.mean()) * (lb - lb.mean())).mean() / vb
            if beta <= 0.2:
                continue
            alpha = la.mean() - beta * lb.mean()
            e = la - alpha - beta * lb
            t, hl = df_stat(e)
            if t < t_max and hl_rng[0] <= hl <= hl_rng[1]:
                cand.append((t, coins[a], coins[b], alpha, beta, e.std()))
    cand.sort()
    used, picked = {}, []
    for c in cand:
        if used.get(c[1], 0) < per_coin and used.get(c[2], 0) < per_coin:
            picked.append(c)
            used[c[1]] = used.get(c[1], 0) + 1
            used[c[2]] = used.get(c[2], 0) + 1
        if len(picked) == k:
            break
    return picked


def pairs_book(C, F, first, elig, lag=1, z_in=2.0, z_out=0.0, z_stop=4.0, win=180, k=10):
    L = np.log(C)
    idx = C.index
    month_starts = [i for i in range(win + 1, len(idx)) if idx[i].day == 1]
    daily = pd.Series(0.0, index=idx)
    trades = []
    for mi, i in enumerate(month_starts):
        end = month_starts[mi + 1] if mi + 1 < len(month_starts) else len(idx) - 1
        m = idx[i].strftime("%Y-%m")
        coins = [s for s in C.columns if m in elig.get(s, ())
                 and (idx[i] - first[s]).days >= max(MIN_AGE_D, win)
                 and np.isfinite(C[s].iloc[i - win:i]).all()]
        if len(coins) < 10:
            continue
        for _t, A, B, al, be, sd in form_pairs(L, i, coins, win=win, k=k):
            wa, wb = 1 / (1 + be), be / (1 + be)
            ca, cb = C[A].to_numpy(float), C[B].to_numpy(float)
            fa = F[A].to_numpy(float) if A in F else np.zeros(len(idx))
            fb = F[B].to_numpy(float) if B in F else np.zeros(len(idx))
            z = (np.log(ca) - al - be * np.log(cb)) / sd
            pos, want, t_in, acc = 0, 0, None, 0.0
            # day d: decide on z[d]; the decision is FILLED at close d+lag. The position held
            # over (d, d+1] is whatever was filled at or before close d.
            pend = []                                            # (fill_day, new_pos, why)
            for d in range(i, len(idx) - 1):
                # the trading month is over and the month-end exit has been filled
                if d + 1 > end and pos == 0 and not pend:
                    break
                for p in [p for p in pend if p[0] == d]:
                    if pos != 0 and p[1] == 0:
                        daily.iat[d] -= FEE / 2 * (1 / k)
                        trades.append(dict(t0=idx[t_in], t1=idx[d], ret=acc - FEE, why=p[2], A=A, B=B))
                    if pos == 0 and p[1] != 0:
                        daily.iat[d] -= FEE / 2 * (1 / k)
                        t_in, acc = d, 0.0
                    pos = p[1]
                pend = [p for p in pend if p[0] > d]
                # a leg that stopped trading: out at its last print, nothing more
                if not (np.isfinite(ca[d + 1]) and np.isfinite(cb[d + 1])):
                    if pos != 0:
                        daily.iat[d] -= FEE / 2 * (1 / k)
                        trades.append(dict(t0=idx[t_in], t1=idx[d], ret=acc - FEE, why="dead", A=A, B=B))
                    pos = 0
                    break
                if pos != 0:
                    ra, rb = ca[d + 1] / ca[d] - 1, cb[d + 1] / cb[d] - 1
                    r = pos * (wa * ra - wb * rb) + pos * (-wa * fa[d + 1] + wb * fb[d + 1])
                    daily.iat[d + 1] += r / k
                    acc += r
                # decisions on close d+1 (known then), filled at d+1+lag
                zz = z[d + 1]
                last = d + 1 >= end - 1                          # final close of the month
                target = pos if not pend else pend[-1][1]
                if target == 0 and not last:
                    if zz > z_in:
                        want = -1
                    elif zz < -z_in:
                        want = 1
                    else:
                        want = 0
                    if want:
                        pend.append((d + 1 + lag, want, "in"))
                elif target != 0:
                    why = ("stop" if abs(zz) > z_stop else "revert" if target * zz >= -z_out
                           else "month end" if last else None)
                    if why:
                        pend.append((d + 1 + lag, 0, why))
            # only reachable when the DATA ends with a position open (the last month)
            if pos != 0:
                daily.iat[len(idx) - 1] -= FEE / 2 * (1 / k)
                trades.append(dict(t0=idx[t_in], t1=idx[-1], ret=acc - FEE, why="end", A=A, B=B))
    first_day = idx[month_starts[0]]
    tr = pd.DataFrame(trades)
    # GUARD: the account's daily P&L and the trade list are built separately; they must agree
    assert abs(daily.sum() - tr.ret.sum() / k) < 1e-9, (daily.sum(), tr.ret.sum() / k)
    return daily[daily.index >= first_day], tr


def test_pairs(C, F, first, reg):
    elig = drop_non_crypto(eligibility(30))
    print("\n=== 2. PAIRS / COINTEGRATION STAT-ARB, PIT top-30, 10 pairs, each 1/10 of the account")
    print("    %/month = mean daily account return x 30.4\n")
    print(f"  {'variant':<34}{'ALL':>8}{'TUNE':>8}{'HOLD':>8}{'bull':>8}{'bear':>8}{'chop':>8}"
          f"{'trades':>8}{'win':>6}{'stops':>7}")
    res = {}
    for lab, kw in (("fill next close (primary)", dict(lag=1)),
                    ("fill same close (flattering)", dict(lag=0)),
                    ("entry 2.5, next close", dict(lag=1, z_in=2.5)),
                    ("365-day formation, next close", dict(lag=1, win=365))):
        daily, tr = pairs_book(C, F, first, elig, **kw)
        d = tag(pd.DataFrame(dict(t=daily.index, net=daily.to_numpy())), reg)
        pm = lambda x: per_month(x, "net", 1)  # noqa: E731
        win = (tr.ret > 0).mean() * 100 if len(tr) else np.nan
        stops = (tr.why == "stop").mean() * 100 if len(tr) else np.nan
        print(f"  {lab:<34}{pm(d):>+7.2f}%{pm(d[d.half == 'tune']):>+7.2f}%{pm(d[d.half == 'hold']):>+7.2f}%"
              + "".join(f"{pm(d[d.regime == r]):>+7.2f}%" for r in REGS)
              + f"{len(tr):>8}{win:>5.0f}%{stops:>6.0f}%")
        res[lab] = (d, tr)
    d, tr = res["fill next close (primary)"]
    if len(tr):
        print("\n  primary, by exit reason (mean trade return, net of 12bp):")
        for why, g in tr.groupby("why"):
            print(f"    {why:<10} n {len(g):>5}  mean {g.ret.mean()*100:>+6.2f}%  win {(g.ret > 0).mean()*100:>4.0f}%")
        print("  primary, by year (%/mo):  " + "  ".join(
            f"{y} {per_month(d[d.t.dt.year == y], 'net', 1):+.2f}" for y in sorted(d.t.dt.year.unique())))
    return res


# ------------------------------------------------------------------ daily OHLC for 3 and 4

def load_ohlc(syms):
    out = {}
    for s in syms:
        p = DATA / f"{s}_1d.csv.gz"
        if not p.exists():
            continue
        d = pd.read_csv(p)
        d["time"] = pd.to_datetime(d["time"]).astype("datetime64[ns]")
        d = d[d.close > 0].drop_duplicates("time").reset_index(drop=True)
        if len(d) >= 60:
            out[s] = d
    return out


def atr(d, n=14):
    if id(d) in _ATR:
        return _ATR[id(d)]
    h, lo, c = d.high.to_numpy(float), d.low.to_numpy(float), d.close.to_numpy(float)
    pc = np.r_[np.nan, c[:-1]]
    tr = np.nanmax(np.c_[h - lo, np.abs(h - pc), np.abs(lo - pc)], axis=1)
    _ATR[id(d)] = pd.Series(tr).ewm(alpha=1 / n, adjust=False, min_periods=n).mean().to_numpy()
    return _ATR[id(d)]


_GATE, _ATR = {}, {}


def gate_days(d, first_t, elig, reg, gate, key=None):
    """bool per bar: may a NEW position open at this bar's open? PIT-eligible, old enough, and
    the BTC regime label for that day (already shifted a day in btc_regime) equals `gate`."""
    if key is not None and (key, gate) in _GATE:
        return _GATE[(key, gate)]
    t = d.time
    m = t.dt.strftime("%Y-%m").to_numpy()
    ok_m = np.array([x in elig for x in m])
    age = ((t - first_t).dt.days >= MIN_AGE_D).to_numpy()
    rg = reg.reindex(pd.DatetimeIndex(t), method="ffill").to_numpy()
    g = ok_m & age & (rg == gate)
    if key is not None:
        _GATE[(key, gate)] = g
    return g


# ------------------------------------------------------------------ 3. daily shorts + pyramid

def short_walk(d, fund, entries, trail, units, add_every=2.0, be_at=3.0):
    """entries: bool per bar, 'open a short at this bar's open'. Pessimistic: on each bar an
    add at its level is taken BEFORE the stop is checked, so a bar that tags both books the
    add's loss. Stop fills at max(stop, open)."""
    o, h, lo, c = (d[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    a = atr(d)
    t = d.time.to_numpy()
    out = []
    i, n = 1, len(d)
    cand = np.flatnonzero(entries)
    ci = 0
    while ci < len(cand):
        i = cand[ci]
        if i < 1 or not (np.isfinite(a[i - 1]) and a[i - 1] > 0):
            ci += 1; continue
        r = 2.0 * a[i - 1]
        e0 = o[i]; ents = [e0]; stop = e0 + r; best = e0; nxt = 1; fR = 0.0
        j = i
        while True:
            # adds first (pessimistic), at their level, if this bar traded down to it
            while len(ents) < units and (e0 - lo[j]) / r >= nxt * add_every:
                ents.append(e0 - nxt * add_every * r); nxt += 1
            if h[j] >= stop:
                x = max(stop, o[j]); break
            if j == n - 1:
                x = c[j]; break                       # data ends: delisted or today
            # funding for holding into the next day: a short RECEIVES positive funding
            fR += fund[j + 1] * c[j] * len(ents) / r
            best = min(best, lo[j])
            cs = best + trail * a[j]
            if (e0 - best) / r >= be_at:
                cs = min(cs, e0)
            stop = min(stop, cs)
            j += 1
        R = sum(e - x for e in ents) / r - FEE * sum(ents) / r + fR
        out.append(dict(t0=pd.Timestamp(t[i]), t1=pd.Timestamp(t[j]), R=float(R), units=len(ents)))
        ci = np.searchsorted(cand, j + 1)            # flat again from the bar after the exit
    return out


def trade_walk(fn, D, Fd, first, elig, reg, gate, sig_fn, rng=None, dens=None, **kw):
    """Run fn over every coin. sig_fn(d) -> bool signal on each bar's close (entry next open).
    With rng: random entries at probability dens on gated bars, instead of the signal."""
    rows = []
    n_sig = n_gate = 0
    for s, d in D.items():
        g = gate_days(d, first[s], elig.get(s, set()), reg, gate, key=s)
        if rng is None:
            sig = np.r_[False, sig_fn(d)[:-1]] & g            # signal on close i-1, act at open i
        else:
            sig = (rng.random(len(d)) < dens) & g
        n_sig += int(sig.sum()); n_gate += int(g.sum())
        fund = Fd[s].reindex(pd.DatetimeIndex(d.time)).fillna(0.0).to_numpy() if s in Fd else np.zeros(len(d))
        for tr in fn(d, fund, sig, **kw) if fn is short_walk else fn(d, fund, sig, rng=rng, **kw):
            tr["coin"] = s
            rows.append(tr)
    return pd.DataFrame(rows), n_sig, n_gate


def bb_short_sig(d, p=30, k=1.5):
    c = d.close
    return (c < c.rolling(p).mean() - k * c.rolling(p).std(ddof=0)).to_numpy()


def month_paired(sig, rnd):
    """mean R per month, signal minus random (random pooled over seeds); t across months."""
    a = sig.groupby(sig.t0.dt.to_period("M")).R.mean()
    b = rnd.groupby(rnd.t0.dt.to_period("M")).R.mean()
    x = (a - b).dropna()
    return x.mean(), (x.mean() / x.std(ddof=1) * np.sqrt(len(x)) if len(x) > 2 else np.nan), len(x)


def summarize_R(tr, lab, months):
    if tr.empty:
        return f"  {lab:<32} no trades"
    tu, ho = tr[tr.t0 < CUT], tr[tr.t0 >= CUT]
    # %/mo at the deployed 0.30% risk per unit, no compounding, no slot cap: a screening number
    per = tr.R.sum() * 0.30 / months
    return (f"  {lab:<32}{len(tr):>6}{tr.R.mean():>+8.3f}{tu.R.mean() if len(tu) else np.nan:>+8.3f}"
            f"{ho.R.mean() if len(ho) else np.nan:>+8.3f}{(tr.R > 0).mean()*100:>6.0f}%{per:>+8.2f}%")


def test_shorts(D, Fd, first, reg):
    elig = drop_non_crypto(eligibility(40))
    bear_months = reg[reg == "bear"].index.to_period("M").nunique()
    print("\n=== 3. DAILY TREND SHORTS, bear-gated, PIT top-40 incl. dead coins, vs RANDOM entries")
    print(f"    R per trade net of 12bp and funding. %/mo = total R x 0.30% / {bear_months} months with a bear day"
          " (screening only: no slots, no compounding)\n")
    print(f"  {'config':<32}{'n':>6}{'meanR':>8}{'TUNE':>8}{'HOLD':>8}{'win':>7}{'%/mo':>9}"
          f"{'   sig-rand/mo (t, months)':>28}")
    res = {}
    for trail in (3.0, 5.0, 10.0):
        for units in (1, 3, 5):
            kw = dict(trail=trail, units=units)
            sig, ns, ng = trade_walk(short_walk, D, Fd, first, elig, reg, "bear", bb_short_sig, **kw)
            dens = ns / max(ng, 1)
            rnd = pd.concat([trade_walk(short_walk, D, Fd, first, elig, reg, "bear", None,
                                        rng=np.random.default_rng(sd), dens=dens, **kw)[0]
                             for sd in SEEDS], ignore_index=True)
            diff, t, nm = month_paired(sig, rnd)
            lab = f"trail {trail:g}x, {units} unit{'s' if units > 1 else ''}"
            print(summarize_R(sig, lab, bear_months) + f"{diff:>+12.3f}R  (t {t:+.2f}, {nm})")
            print(summarize_R(rnd.assign(R=rnd.R), "   random (10 seeds pooled)", bear_months * len(SEEDS)))
            res[(trail, units)] = (sig, rnd)
    # by year for the deployed short exit (5x, 1 unit) and the pyramid (5x, 5 units)
    for key in ((5.0, 1), (5.0, 5)):
        sig, rnd = res[key]
        print(f"\n  by year, trail {key[0]:g}x {key[1]} units - signal R total / random R total per seed:")
        print("   " + "  ".join(f"{y}: {sig[sig.t0.dt.year == y].R.sum():+.0f} / "
                                f"{rnd[rnd.t0.dt.year == y].R.sum() / len(SEEDS):+.0f}"
                                for y in sorted(sig.t0.dt.year.unique())))
    return res


# ------------------------------------------------------------------ 4. gated mean reversion

def mr_walk(d, fund, entries, rng=None, p=20, k=2.0, max_bars=10, dirs=None):
    """Fade a close outside BB(p, k) at the next open: long below, short above. Exit at the
    close that crosses back over the p-day mean, a 2xATR stop (fill max/min(stop, open)), or
    after max_bars. With rng, the direction is drawn with the signal's long share (dirs)."""
    o, h, lo, c = (d[x].to_numpy(float) for x in ("open", "high", "low", "close"))
    a = atr(d)
    t = d.time.to_numpy()
    ma = d.close.rolling(p).mean().to_numpy()
    sd = d.close.rolling(p).std(ddof=0).to_numpy()
    out, n = [], len(d)
    cand = np.flatnonzero(entries)
    ci = 0
    while ci < len(cand):
        i = cand[ci]
        if not (np.isfinite(a[i - 1]) and a[i - 1] > 0 and np.isfinite(ma[i - 1])):
            ci += 1; continue
        if rng is None:
            side = 1 if c[i - 1] < ma[i - 1] - k * sd[i - 1] else -1
        else:
            side = 1 if rng.random() < dirs else -1
        r = 2.0 * a[i - 1]
        e = o[i]; stop = e - side * r; fR = 0.0
        j = i
        while True:
            if (side == 1 and lo[j] <= stop) or (side == -1 and h[j] >= stop):
                x = min(stop, o[j]) if side == 1 else max(stop, o[j]); break
            if side * (c[j] - ma[j]) >= 0 or j - i + 1 >= max_bars or j == n - 1:
                x = c[j]; break
            fR -= side * fund[j + 1] * c[j] / r           # longs pay positive funding
            j += 1
        R = side * (x - e) / r - FEE * e / r + fR
        out.append(dict(t0=pd.Timestamp(t[i]), t1=pd.Timestamp(t[j]), R=float(R), side=side))
        ci = np.searchsorted(cand, j + 1)
    return out


def test_mr(D, Fd, first, reg):
    elig = drop_non_crypto(eligibility(40))
    print("\n=== 4. MEAN REVERSION GATED TO ONE REGIME, PIT top-40, fade BB(20, 2), exit at the mean")
    print(f"  {'config':<32}{'n':>6}{'meanR':>8}{'TUNE':>8}{'HOLD':>8}{'win':>7}{'%/mo':>9}"
          f"{'   sig-rand/mo (t, months)':>28}")

    def sig_fn(d, p=20, k=2.0):
        c = d.close
        m, s = c.rolling(p).mean(), c.rolling(p).std(ddof=0)
        return ((c < m - k * s) | (c > m + k * s)).to_numpy()

    res = {}
    for gate in ("chop", "bear", "bull"):
        months = reg[reg == gate].index.to_period("M").nunique()
        sig, ns, ng = trade_walk(mr_walk, D, Fd, first, elig, reg, gate, sig_fn)
        dens = ns / max(ng, 1)
        dirs = (sig.side == 1).mean() if len(sig) else 0.5
        rnd = pd.concat([trade_walk(mr_walk, D, Fd, first, elig, reg, gate, None,
                                    rng=np.random.default_rng(sd), dens=dens, dirs=dirs)[0]
                         for sd in SEEDS], ignore_index=True)
        diff, t, nm = month_paired(sig, rnd)
        print(summarize_R(sig, f"{gate}-gated fade", months) + f"{diff:>+12.3f}R  (t {t:+.2f}, {nm})")
        print(summarize_R(rnd, "   random (10 seeds pooled)", months * len(SEEDS)))
        for sd_, g in sig.groupby("side"):
            print(f"      {'longs' if sd_ == 1 else 'shorts'}: n {len(g)}, mean {g.R.mean():+.3f}R")
        res[gate] = (sig, rnd)
    return res


# ------------------------------------------------------------------ 6. funding carry by regime

def test_carry(C, F, first, reg):
    """Doc 10's momentum book earns in bears ONLY through funding (+0.437%/wk carry against a
    -0.132%/wk momentum spread). Isolate the carry: each week, on the PIT top-60, SHORT the
    decile with the highest trailing funding and LONG the lowest, equal dollars. funding_xs.py
    tested this on a narrow survivor universe at 8-72h holds (18 of 18 cells negative); never
    weekly, never on the dead-coin universe, never by regime.

    REGISTERED PREDICTION (2026-09-24, before running): carry is positive in every regime
    (~+0.3%/wk). The price leg depends on the regime: a crowded long unwinds DOWN, so
    shorting the highest-funding coins helps in bears, and hurts in bulls, where those are
    the coins being chased higher. Net: positive in bear, negative in bull, below the
    momentum book in chop. Worth having only if its bear row beats the momentum book's
    +0.24%/wk."""
    elig = drop_non_crypto(eligibility(60))
    Fx = F.reindex(columns=C.columns).fillna(0.0)
    print("\n=== 6. FUNDING CARRY, market-neutral: short highest trailing funding, long lowest, PIT top-60")
    print("    funding credited over the days actually held (i+1..i+hold); '[run() dates]' rows use")
    print("    market_neutral.run's one-day-early window, to show what that offset is worth")
    print(f"  {'rank on':<38}{'net':>8}{'gross':>8}{'carry':>8}{'cost':>7}{'TUNE':>8}{'HOLD':>8}"
          f"{'bull':>8}{'bear':>8}{'chop':>8}   (%/week)")

    def show(lab, d):
        pw = lambda x, c="net": x[c].mean() * 100 if len(x) else np.nan  # noqa: E731
        print(f"  {lab:<38}{pw(d):>+7.3f}%{pw(d, 'gross'):>+7.3f}%{pw(d, 'carry'):>+7.3f}%"
              f"{-pw(d, 'cost'):>+6.3f}%{pw(d[d.half == 'tune']):>+7.3f}%{pw(d[d.half == 'hold']):>+7.3f}%"
              + "".join(f"{pw(d[d.regime == r]):>+7.3f}%" for r in REGS))
    for lab, win in (("7-day funding sum", 7), ("30-day funding sum", 30)):
        # row j = funding summed over days j-win+1..j; settlements on day j are all at or
        # before 16:00 of day j, known by close j (= 00:00 of day j+1)
        score = -Fx.rolling(win, min_periods=win).sum().to_numpy()
        for fs in (1, 0):
            d = tag(fast_run(C, F, first, elig, look=1, hold=7, score=score, fshift=fs), reg)
            show(f"{lab}{'' if fs else ' [run() dates]'}", d)
            if fs:
                print("     by year: " + "  ".join(f"{y}: {d[d.t.dt.year == y].net.mean()*100:+.2f}"
                                                 for y in sorted(d.t.dt.year.unique())))
    for fs in (1, 0):
        m = tag(fast_run(C, F, first, elig, look=30, hold=7, fshift=fs), reg)
        show(f"30d MOMENTUM (doc 10){'' if fs else ' [run() dates]'}", m)


# ------------------------------------------------------------------ 5. BTC/ETH short on the gate

def test_major_short(C, F, reg):
    """The short side of the bot's own gate, traded on BTC and ETH directly: short while the
    coin's close is below its 42-day (~1000h) average, flat otherwise. Decided on close t-1,
    held over day t. 6bp per side, actual funding (a short receives positive funding).
    btc_timing.py found long-above/flat-below the best BTC timing rule (Sharpe 1.12); its
    'long BULL / short BEAR' row lost Sharpe, so the prior on this short leg is poor."""
    print("\n=== 5. SHORT BTC / ETH WHILE BELOW THEIR OWN 1000h (42-day) AVERAGE, 1x, flat otherwise")
    print(f"  {'book':<30}{'CAGR':>8}{'DD':>6}{'Sharpe':>8}{'TUNE/yr':>9}{'HOLD/yr':>9}"
          f"{'bull':>8}{'bear':>8}{'chop':>8}   by year")
    for coin in ("BTCUSDT", "ETHUSDT"):
        c = C[coin].dropna()
        f = F[coin].reindex(c.index).fillna(0.0)
        r = c.pct_change().fillna(0.0)
        below = (c < c.rolling(42).mean()).shift(1, fill_value=False).astype(bool)
        rg = reg.reindex(c.index, method="ffill").fillna("chop")
        for lab, pos in ((f"{coin[:3]} short below / flat", -below.astype(float)),
                         (f"{coin[:3]} long above / flat", (~below).astype(float)),
                         (f"{coin[:3]} long above / short below", np.where(below, -1.0, 1.0))):
            pos = pd.Series(pos, index=c.index).where(c.rolling(42).mean().shift(1).notna(), 0.0)
            chg = pos.diff().abs().fillna(pos.abs())
            net = pos * r - pos * f - chg * FEE / 2
            eq = (1 + net).cumprod()
            yrs = len(net) / 365.0
            cagr = (eq.iloc[-1] ** (1 / yrs) - 1) * 100
            dd = (1 - eq / eq.cummax()).max() * 100
            sh = net.mean() / net.std(ddof=1) * np.sqrt(365)

            def ann(x):
                return ((1 + x).prod() ** (365 / max(len(x), 1)) - 1) * 100
            yr = "  ".join(f"{y % 100:02d}:{((1 + net[net.index.year == y]).prod() - 1) * 100:+.0f}"
                           for y in sorted(set(net.index.year)))
            print(f"  {lab:<30}{cagr:>+7.0f}%{dd:>5.0f}%{sh:>8.2f}{ann(net[net.index < CUT]):>+8.0f}%"
                  f"{ann(net[net.index >= CUT]):>+8.0f}%"
                  + "".join(f"{ann(net[rg == g]):>+7.0f}%" for g in REGS) + f"   {yr}")


def main(which=("1", "2", "3", "4", "5", "6")):
    C, F, first = load_panel()
    C.index = C.index.astype("datetime64[ns]")
    F.index = C.index
    reg = btc_regime(C)
    print(f"panel: {C.shape[1]} perps, {C.index[0]:%Y-%m} .. {C.index[-1]:%Y-%m} | holdout from {CUT:%Y-%m-%d}")
    print("regime days: " + "  ".join(f"{k} {int(v)}" for k, v in reg.value_counts().items()))
    print("reference, trend book by regime (%/mo, 3x haircut, logs/regime_and_liq.txt): "
          "main bull +23.05 bear +0.26 chop -0.16 | triple bull +47.19 bear -0.74 chop +0.20")
    if "1" in which:
        # GUARD: the vectorised engine must reproduce market_neutral.run before it is used
        elig = drop_non_crypto(eligibility(60))
        for look, hold, lag in ((30, 7, 0), (1, 7, 1)):
            a = run(C, F, first, elig, look=look, hold=hold, lag=lag)
            b = fast_run(C, F, first, elig, look=look, hold=hold, lag=lag)
            assert len(a) == len(b) and np.allclose(a[["net", "gross", "carry", "cost"]].to_numpy(),
                                                    b[["net", "gross", "carry", "cost"]].to_numpy(),
                                                    atol=1e-12), (look, hold, lag)
        print("guard: fast_run reproduces market_neutral.run (30/7/0 and 1/7/1) to 1e-12")
        test_reversal(C, F, first, reg)
    if "2" in which:
        test_pairs(C, F, first, reg)
    if "3" in which or "4" in which:
        syms = {s for s, ms in drop_non_crypto(eligibility(40)).items() if ms}
        D = load_ohlc(sorted(syms))
        first_ns = pd.Series({s: pd.Timestamp(first[s]).as_unit("ns") if s in first
                              else D[s].time.iloc[0] for s in D})
        print(f"\ndaily OHLC loaded for {len(D)} coins that were ever PIT top-40")
        if "3" in which:
            test_shorts(D, F, first_ns, reg)
        if "4" in which:
            test_mr(D, F, first_ns, reg)
    if "5" in which:
        test_major_short(C, F, reg)
    if "6" in which:
        test_carry(C, F, first, reg)


if __name__ == "__main__":
    main(tuple(sys.argv[1:]) or ("1", "2", "3", "4", "5", "6"))
