"""THE PAIR'S LAB - where does it lose, and what fixes it? (2026-10-08, goal: "see where we are losing gains ... test
every pain point")

THE PAIR (pair_books.py): half the account in the DAILY book (Bollinger(30,1.5) break on daily bars, out after a close
under the 30-day mean, 30-day cap) and half in the CAPITULATION book (4h RSI(14) cross under 20 + volume > 2x, >= 5
coins in 24h, +5% or out after 24 bars if not in profit). Point-in-time top-40, dead coins in, 12bp + funding, 1x.

This file holds the shared machinery (trades with exit times and context, accounts, metrics) and the DIAGNOSIS:
    a) each book's monthly contribution by market type (BTC 50-day trend: bull / chop / bear, market_neutral.btc_regime)
    b) idle capital: the share of days each half holds nothing, and its average use of its 8 slots
    c) signals skipped for full slots
    d) the daily book's losers: by market type at entry, and how they ended
    e) costs: fees + funding against the gross

REGISTERED BEFORE THE DIAGNOSIS: the daily book's losses are mostly in BEAR and CHOP months; the capitulation half holds
nothing on 80-90% of days (the largest leak); skipped signals and costs are minor.

RESULT (2026-10-08, logs/pair_lab_diagnosis.txt, logs/pair_lab_fixes.txt)
    DIAGNOSIS: the pair +52%/yr (tune +64 / holdout +38), fall 31%; average month bull +10.2%, chop +2.2%, bear -2.1%.
      - the CAPITULATION half is idle 95% of days (0.2 of 8 slots) - the biggest leak (predicted 80-90%: right).
      - the DAILY book skips 706 of 1,328 signals (slots full 42% of days) and the skipped ones are as good (+7.2%) -
        predicted "minor": WRONG, a big leak.
      - daily trades closed by the 30-day CAP averaged +70% (mean-exits -7%).
      - daily losses: 51% bull-entry, 34% chop, 15% bear - predicted mostly bear/chop: WRONG.
      - costs 1.6% of gross (minor, right).
    FIXES alone (10 orders, phase 0): cap 60 +56% (halves +55/+54), cap 90/none ~+50% (predicted +10..+30 points:
      WRONG); daily slots 12/16/24 -> +45/+39/+31% with falls 26/24/21% - less exposure, not a gain (WRONG); one shared
      pool 16/24/32 -> tune up, HOLDOUT DOWN (+25/+19/+12%) (WRONG); gate not-bear +51% fall 28%, BTC 1000h +52% fall
      25% (on one phase; across phases it cost the holdout, pair_full.py); + MN x0.5 +100%/yr, x1 +148% - checked in
      mn_capped.py (a few pumps carry 2026).

    python -m backtest.pair_lab
    python -m backtest.pair_lab --fixes
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest.capitulation_wide import funding_cum, hourly  # noqa: E402
from backtest.rsi_factors import prep  # noqa: E402
from backtest.tv_indicators import bars, indicators  # noqa: E402
from backtest.wide_book import eligibility  # noqa: E402

CACHE = ROOT / "logs" / "pair_lab_cache"
LOG = ROOT / "logs" / "pair_lab_diagnosis.txt"
HOLDOUT = pd.Timestamp("2024-04-07")
FEE = 0.0012
_H: dict = {}
_EL: dict = {}


def universe():
    if "el" not in _EL:
        _EL["el"] = eligibility(40)
    return _EL["el"]


def hourly_all():
    if not _H:
        for s in sorted(k for k, m in universe().items() if m):
            h = hourly(s)
            if h is not None:
                _H[s] = h
    return _H


def btc_regime_daily():
    """bull / chop / bear by day from BTC's 50-day trend, knowable (market_neutral.btc_regime on BTC alone)."""
    b = bars(hourly_all()["BTCUSDT"], "1d", 0).set_index("time").c
    ma = b.rolling(50).mean()
    slope = ma / ma.shift(20) - 1
    r = pd.Series("chop", index=b.index)
    r[(b > ma) & (slope > 0.02)] = "bull"
    r[(b < ma) & (slope < -0.02)] = "bear"
    return r.shift(1).ffill()


def btc_gate_daily(n=1000):
    """True while BTC's daily close is above its n-HOUR mean (n/24 days), knowable at the next day."""
    b = bars(hourly_all()["BTCUSDT"], "1d", 0).set_index("time").c
    return (b > b.rolling(max(int(n / 24), 2)).mean()).shift(1).fillna(False).astype(bool)


def daily_trades(off_h=0, exit_rule="mean", gate=None, k_trail=None, cap=30):
    """The daily book's trades: coin, t_in, t_out, net, worst, regime at entry, exit reason.
    exit_rule 'mean' (close under the 30-day mean) | 'trail' (k_trail x ATR from the best close) | 'mean_or_trail'.
    gate: None, or a daily boolean Series - new entries only on days it is True."""
    f = CACHE / (f"daily_{off_h}_{exit_rule}_{'none' if gate is None else gate.name}_{k_trail}_{cap}.pkl")
    if f.exists():
        return pd.read_pickle(f)
    reg = btc_regime_daily()
    rows = []
    for s, h in hourly_all().items():
        d = bars(h, "1d", off_h * 60)
        if len(d) < 120:
            continue
        P = prep(d, np.full(len(d), np.nan))
        fc = funding_cum(s, d.time.to_numpy(), h)
        ent, exs = indicators(P)["bb"]
        ent, exs = np.nan_to_num(ent).astype(bool), np.nan_to_num(exs).astype(bool)
        o, c, l, atr = P["o"], P["c"], P["l"], P["atr"]
        ym, t = d.time.dt.strftime("%Y-%m").to_numpy(), d.time.to_numpy()
        n = len(t)
        el = universe()[s]
        free = 0
        for i in np.flatnonzero(ent):
            if i < 60 or i < free or i + 3 >= n or ym[i] not in el:
                continue
            day = pd.Timestamp(t[i]).normalize()
            if gate is not None and not bool(gate.asof(day)):
                continue
            e = o[i + 1]
            j_end = min(i + 1 + cap, n - 2)
            best, j_exit, why = c[i + 1], None, "cap"
            for j in range(i + 1, j_end + 1):
                best = max(best, c[j])
                if exit_rule in ("mean", "mean_or_trail") and exs[j]:
                    j_exit, why = j, "mean"
                    break
                if exit_rule in ("trail", "mean_or_trail") and c[j] < best - k_trail * atr[j]:
                    j_exit, why = j, "trail"
                    break
            if j_exit is None:
                x, jo = c[j_end], j_end
            else:
                x, jo = o[j_exit + 1], j_exit + 1
            net = x / e - 1 - FEE - (fc[jo] - fc[i + 1]) / e
            worst = float(np.max(1 - l[i + 1:jo + 1] / e))
            rows.append((s, t[i + 1], t[min(jo, n - 1)], net, worst, reg.asof(day), why))
            free = jo
    T = pd.DataFrame(rows, columns=["coin", "t_in", "t_out", "net", "worst", "regime", "why"])
    T["t_in"], T["t_out"] = pd.to_datetime(T.t_in), pd.to_datetime(T.t_out)
    CACHE.mkdir(parents=True, exist_ok=True)
    T.to_pickle(f)
    return T


def capit_trades(off=0):
    C = pd.read_csv(ROOT / "logs" / "capitulation_exits_trades.csv", parse_dates=["t_in", "t_out"])
    C = C[(C.exit == "tp5_nw") & (C.off == off)].copy()
    reg = btc_regime_daily()
    C["regime"] = [reg.asof(t.normalize()) for t in C.t_in]
    return C


def account(books, lev=1.0, seed=0, pool=None, extra_daily=None):
    """books: {name: (trades, share, slots)}. Each book sizes a trade at equity x share / slots and holds at most
    `slots`. pool=(total_slots, cap_per_book): ONE shared pool instead - a trade takes equity / total_slots, any book,
    while open positions < total_slots (and that book < its cap). Liquidation from each trade's deepest dip.
    extra_daily: a daily return Series added on the account (an overlay such as the market-neutral book).
    Returns (daily equity curve, stats dict with skipped counts and idle shares)."""
    liq = 1 / lev - 0.005 - 0.0006
    rng = np.random.default_rng(seed)
    ev = []
    for nm, (T, share, slots) in books.items():
        for r in T.itertuples():
            ev.append((r.t_in, rng.random(), nm, r.t_out, r.net, r.worst))
    ev.sort(key=lambda x: (x[0], x[1]))
    eq, open_, pts, skipped, taken = 1.0, [], [], {nm: 0 for nm in books}, {nm: 0 for nm in books}
    for t_in, _, nm, t_out, net, worst in ev:
        for p in sorted([p for p in open_ if p[0] <= t_in], key=lambda p: p[0]):
            eq += p[1]
            pts.append((p[0], eq))
        open_ = [p for p in open_ if p[0] > t_in]
        if eq <= 0:
            break
        if pool is None:
            _, share, slots = books[nm]
            if sum(1 for p in open_ if p[2] == nm) >= slots:
                skipped[nm] += 1
                continue
            size = eq * share / slots
        else:
            total, cap = pool
            if len(open_) >= total or sum(1 for p in open_ if p[2] == nm) >= cap.get(nm, total):
                skipped[nm] += 1
                continue
            size = eq / total
        pnl = -size if worst >= liq else size * max(lev * net, -1.0)
        open_.append((t_out, pnl, nm, t_in))
        taken[nm] += 1
    for p in sorted(open_, key=lambda p: p[0]):
        eq += p[1]
        pts.append((p[0], eq))
    s = pd.Series([e for _, e in pts], index=pd.DatetimeIndex([t for t, _ in pts])).groupby(level=0).last()
    d = s.resample("D").last().ffill()
    start = min(x[0] for x in ev).normalize()
    d = pd.concat([pd.Series([1.0], index=[start]), d]).groupby(level=0).last().resample("D").last().ffill()
    if extra_daily is not None:
        r = d.pct_change().fillna(0.0) + extra_daily.reindex(d.index).fillna(0.0)
        d = (1 + r).cumprod()
    return d, dict(skipped=skipped, taken=taken)


def metrics(d, reg=None):
    yrs = (d.index[-1] - d.index[0]).days / 365
    cagr = d.iloc[-1] ** (1 / yrs) - 1 if d.iloc[-1] > 0 else -1.0
    mo = d.resample("ME").last().pct_change().dropna()
    tu = d[d.index < HOLDOUT]
    ho = d[d.index >= HOLDOUT]
    c_t = (tu.iloc[-1] / tu.iloc[0]) ** (365 / max((tu.index[-1] - tu.index[0]).days, 1)) - 1
    c_h = (ho.iloc[-1] / ho.iloc[0]) ** (365 / max((ho.index[-1] - ho.index[0]).days, 1)) - 1
    out = dict(cagr=cagr, tune=c_t, hold=c_h, dd=float((1 - d / d.cummax()).max()), up=(mo > 0).mean(),
               med=mo.median(), worst=mo.min(), p10=(mo >= 0.10).mean())
    if reg is not None:
        lab = reg.reindex(d.index).ffill().groupby(d.index.to_period("M")).agg(lambda x: x.value_counts().idxmax())
        mo.index = mo.index.to_period("M")
        for rg in ("bull", "chop", "bear"):
            m = mo[lab.reindex(mo.index) == rg]
            out[rg] = m.mean() if len(m) else np.nan
    return out


def diagnose():
    reg = btc_regime_daily()
    D = daily_trades()
    C = capit_trades(0)
    lines = [f"backtest/pair_lab.py (diagnosis), {pd.Timestamp.now():%Y-%m-%d %H:%M}; the pair: daily book + capitulation book "
             f"(phase 0), half each, 8 slots each, 1x, 10 same-day orders", ""]
    res = [account({"daily": (D, 0.5, 8), "capit": (C, 0.5, 8)}, seed=sd) for sd in range(10)]
    m = pd.DataFrame([metrics(d, reg) for d, _ in res]).median()
    lines.append(f"THE PAIR: {m.cagr * 100:+.0f}%/yr (tune {m.tune * 100:+.0f} / holdout {m.hold * 100:+.0f}), fall {m.dd:.0%}, months up "
                 f"{m.up:.0%}, median month {m.med * 100:+.1f}%; average month by market: bull {m.bull * 100:+.1f}%, chop "
                 f"{m.chop * 100:+.1f}%, bear {m.bear * 100:+.1f}%")
    days = reg.groupby(reg).size()
    lines.append(f"  days by market type: {days.to_dict()}")
    # a) each book alone, by market type
    lines.append("\na) EACH BOOK ALONE (its half, the other half in cash), average month by market type:")
    for nm, T in (("daily", D), ("capit", C)):
        mm = pd.DataFrame([metrics(account({nm: (T, 0.5, 8)}, seed=sd)[0], reg) for sd in range(10)]).median()
        lines.append(f"  {nm:6}: {mm.cagr * 100:+.0f}%/yr; bull {mm.bull * 100:+.1f}%, chop {mm.chop * 100:+.1f}%, bear {mm.bear * 100:+.1f}% "
                     f"a month; months up {mm.up:.0%}")
    # b) idle capital
    lines.append("\nb) IDLE CAPITAL: share of days each book holds nothing, average slots in use (of 8):")
    span = pd.date_range(min(D.t_in.min(), C.t_in.min()).normalize(), max(D.t_out.max(), C.t_out.max()).normalize(), freq="D")
    for nm, T in (("daily", D), ("capit", C)):
        use = np.zeros(len(span))
        for r in T.itertuples():
            a, b = span.searchsorted(r.t_in.normalize()), span.searchsorted(r.t_out.normalize())
            use[a:b] += 1
        use = np.minimum(use, 8)
        lines.append(f"  {nm:6}: idle {np.mean(use == 0):.0%} of days, average {use.mean():.1f} of 8 slots, full (8) {np.mean(use >= 8):.0%} of days")
    # c) skipped
    sk = pd.DataFrame([r[1]["skipped"] for r in res]).median()
    tk = pd.DataFrame([r[1]["taken"] for r in res]).median()
    lines.append(f"\nc) SIGNALS SKIPPED (slots full), median of 10 orders: daily {sk['daily']:.0f} of {sk['daily'] + tk['daily']:.0f}, "
                 f"capit {sk['capit']:.0f} of {sk['capit'] + tk['capit']:.0f}")
    lines.append(f"   skipped daily trades averaged (all daily trades): {D.net.mean() * 100:+.2f}% a trade")
    # d) the daily book's trades by market type and exit reason
    lines.append("\nd) DAILY BOOK TRADES by market type at entry (n, win, avg, share of all losses):")
    loss = D.net.clip(upper=0).sum()
    for rg, g in D.groupby("regime"):
        lines.append(f"  {rg:5}: {len(g):5} trades, win {np.mean(g.net > 0):.0%}, avg {g.net.mean() * 100:+.2f}%, "
                     f"{g.net.clip(upper=0).sum() / loss:.0%} of all losses, {g.net.clip(lower=0).sum() / D.net.clip(lower=0).sum():.0%} of all gains")
    for why, g in D.groupby("why"):
        lines.append(f"  exit {why:5}: {len(g):5} trades, avg {g.net.mean() * 100:+.2f}%")
    lines.append("  CAPITULATION trades by market type: " + ", ".join(
        f"{rg} {len(g)} avg {g.net.mean() * 100:+.2f}%" for rg, g in C.groupby("regime")))
    # e) costs
    fees = 0.0012 * len(D)
    lines.append(f"\ne) COSTS on the daily book: fees {fees * 100:.0f} trade-% (12bp x {len(D)}) against a gross of "
                 f"{(D.net.sum() + fees) * 100:.0f} trade-% ({fees / (D.net.sum() + fees):.1%} of gross)")
    txt = "\n".join(lines)
    print(txt)
    LOG.write_text(txt + "\n")


def mn_daily():
    """The repo's market-neutral book (doc 10), daily return at 1x, as machine.py builds it."""
    f = CACHE / "mn_daily.pkl"
    if f.exists():
        return pd.read_pickle(f)
    from backtest.bear_chop import fast_run
    from backtest.carry_check import exact_funding
    from backtest.market_neutral import drop_non_crypto, load_panel
    C, F, first = load_panel()
    C.index = C.index.astype("datetime64[ns]")
    Fx = exact_funding(C.index, C.columns)
    mn = fast_run(C, Fx, first, drop_non_crypto(eligibility(60)), look=30, hold=7, fshift=1)
    s = pd.Series(mn.net.to_numpy(), index=pd.DatetimeIndex(mn.t) + pd.Timedelta(days=7)).groupby(level=0).sum()
    CACHE.mkdir(parents=True, exist_ok=True)
    s.to_pickle(f)
    return s


def fixes():
    """Each pain point's fix, alone, against the pair - median of 10 same-day orders.
    REGISTERED BEFORE RUNNING (2026-10-08):
      F1 cap 60 / 90 / none: +10..+30 points of CAGR, a similar fall.
      F2 daily slots 12 / 16 / 24 (half the account still): higher CAGR AND a smaller fall.
      F3 one shared pool (24 / 32 slots, capitulation at most 8): a clear CAGR gain over fixed halves.
      F4 daily entries gated to non-bear (BTC 50d trend) / BTC above its 1000h mean: a little less CAGR, a little less fall.
      F5 the market-neutral book as an overlay (0.5x / 1x): better bear and chop months, a smaller fall.
      F6 1.5x leverage on the best structure: more CAGR, the fall rises but no wipe-out."""
    reg = btc_regime_daily()
    C = capit_trades(0)
    D = daily_trades()
    mn = mn_daily()
    lines = [f"backtest/pair_lab.py --fixes, {pd.Timestamp.now():%Y-%m-%d %H:%M}; median of 10 same-day orders; CAGR (tune / "
             f"holdout), worst fall, months up, median month, worst month; average month in bull / chop / bear", ""]

    def show(lab, books, **kw):
        ms = pd.DataFrame([metrics(account(books, seed=sd, **kw)[0], reg) for sd in range(10)]).median()
        lines.append(f"  {lab:46} {ms.cagr * 100:+5.0f}%/yr ({ms.tune * 100:+4.0f}/{ms.hold * 100:+4.0f}) fall {ms.dd:4.0%} up {ms.up:4.0%} "
                     f"med {ms.med * 100:+5.1f}% worst {ms.worst * 100:+4.0f}% | bull {ms.bull * 100:+5.1f} chop {ms.chop * 100:+5.1f} "
                     f"bear {ms.bear * 100:+5.1f}")
        print(lines[-1], flush=True)
        return ms

    show("THE PAIR (base: cap 30, 8+8 slots, halves)", {"daily": (D, 0.5, 8), "capit": (C, 0.5, 8)})
    lines.append("F1 the 30-day cap:")
    for cap in (60, 90, 365):
        show(f"  cap {cap}", {"daily": (daily_trades(cap=cap), 0.5, 8), "capit": (C, 0.5, 8)})
    lines.append("F2 daily slots (half the account each):")
    for sl in (12, 16, 24):
        show(f"  daily slots {sl}", {"daily": (D, 0.5, sl), "capit": (C, 0.5, 8)})
    lines.append("F3 one shared pool:")
    for tot in (16, 24, 32):
        show(f"  pool {tot} slots, capit <= 8", {"daily": (D, 1, tot), "capit": (C, 1, tot)}, pool=(tot, {"capit": 8}))
    lines.append("F4 gating the daily entries:")
    g1 = (reg != "bear").rename("notbear")
    g2 = btc_gate_daily(1000).rename("btc1000")
    for g in (g1, g2):
        show(f"  daily gated {g.name}", {"daily": (daily_trades(gate=g), 0.5, 8), "capit": (C, 0.5, 8)})
    lines.append("F5 the market-neutral book as an overlay:")
    for w in (0.5, 1.0):
        show(f"  + MN x{w}", {"daily": (D, 0.5, 8), "capit": (C, 0.5, 8)}, extra_daily=w * mn)
    txt = "\n".join(lines)
    (ROOT / "logs" / "pair_lab_fixes.txt").write_text(txt + "\n")


if __name__ == "__main__":
    fixes() if "--fixes" in sys.argv else diagnose()
