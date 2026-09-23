"""IS LOW CAPITAL AN ADVANTAGE? - testing the one claim doc 11 left standing.

THE THESIS THIS PUTS A NUMBER ON
    Doc 11 closed seven mechanism-based searches with one pattern: every real edge is priced
    within a second by co-located bots, competed to zero by the capital that found it, or too
    rare to separate from noise. Its conclusion was that what a small account can do better
    than a fund is hold what a fund cannot.

    That was stated as consolation. It is actually a TESTABLE claim, and nobody has tested it:
    if an edge exists that big capital cannot take, it must live in coins too small to absorb
    institutional size - and it must therefore get WEAKER as account size grows, in a way that
    is measurable rather than asserted.

    So: run the same cross-sectional momentum book inside volume TIERS, and charge a
    size-dependent impact cost, so the identical strategy can be scored at $200, $20k, $2M
    and $20M. If the edge is real and capacity-constrained, small tiers beat large ones at
    $200 and collapse by $2M. If the gross spread is NOT larger in small coins, the thesis is
    dead and "low capital is an advantage" is false for this strategy.

WHY THIS IS NOT MORE MINING
    It is not another parameter swept against the mined-out 2024-2026 holdout. It is a new
    CROSS-SECTION - the volume dimension - on the point-in-time survivorship-free universe,
    and its falsification condition is about the SHAPE across tiers, not about beating a
    number on one split. wide_book.py found that making the universe WIDER hurts, but wider
    mixes small coins in alongside large ones; it never isolated a tier and ranked within it.

THE COST MODEL, because this is where small-coin strategies actually die
    fee     12bp on the notional turned over, as everywhere else in this repo
    impact  the square-root law, impact = sigma_daily * sqrt(Q / ADV), charged on BOTH legs
            of every name that turns over. sigma is each coin's own trailing 30-day daily
            volatility, ADV its trailing 30-day dollar volume, Q the position size implied by
            the account. This is the standard Almgren/Barra form and it is the reason a $2M
            account cannot trade a $300k-volume coin: at 17% participation the impact is
            ~40x the fee.
    funding the ACTUAL rate both legs paid or received, from the archive.

REGISTERED PREDICTIONS (written before the first run, 2026-09-23)
    1. GROSS spread is LARGER in smaller-volume tiers. This is the size effect and it is
       well documented in equities; if it does not appear here the thesis dies immediately.
    2. At $200 the smallest tradable tier is the BEST net, because impact on an $18 clip is
       a rounding error even in a $300k-volume coin.
    3. By $2M the ordering REVERSES and only the top tier survives.
    4. The crossover - the account size at which tier choice flips - lands between $50k and
       $500k. That number is the deliverable: it says how long this edge lasts.
    5. The smallest tier will look best on gross and worst on t-stat, because it holds the
       fewest names and the most dead coins.

    python -m backtest.capacity_edge
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.market_neutral import NON_CRYPTO, btc_regime  # noqa: E402
from backtest.wide_book import DATA, MIN_AGE_D  # noqa: E402

FEE = 12.0 / 1e4
LOOK_D, HOLD_D, FRAC = 30, 7, 0.20        # wider decile: tiers are small, so 20% a side
MIN_NAMES = 10
ACCOUNTS = (200.0, 20_000.0, 200_000.0, 2_000_000.0, 20_000_000.0)
# rank bands within each month's eligible set, by PRIOR month dollar volume
TIERS = {"1-20 (mega)": (0, 20), "21-60 (large)": (20, 60),
         "61-120 (mid)": (60, 120), "121-250 (small)": (120, 250),
         "251+ (micro)": (250, 10_000)}


def load_panel():
    """close, dollar volume and daily funding for every perp, plus each coin's first day."""
    close, vol, fund, first = {}, {}, {}, {}
    for p in sorted(DATA.glob("*_1d.csv.gz")):
        s = p.name.split("_")[0]
        if s.endswith("USDT") and s[:-4] in NON_CRYPTO:
            continue                       # gold tokens and stables - see market_neutral
        try:
            d = pd.read_csv(p, parse_dates=["time"])
        except Exception:
            continue
        d = d[d.close > 0]
        if len(d) < 60:
            continue
        d = d[~d.time.duplicated()].set_index("time")
        close[s] = d["close"]
        vol[s] = d["qvol"]
        first[s] = d.index[0]
        f = DATA / f"{s}_funding.csv.gz"
        if f.exists():
            try:
                fr = pd.read_csv(f, parse_dates=["time"])
                fund[s] = fr.set_index("time")["rate"].resample("D").sum()
            except Exception:
                pass
    C = pd.DataFrame(close).sort_index()
    V = pd.DataFrame(vol).reindex(C.index)
    F = pd.DataFrame(fund).reindex(C.index).fillna(0.0)
    return C, V, F, pd.Series(first)


def monthly_volume(V):
    """Dollar volume per coin per calendar month, computed ONCE.

    The first version of this file recomputed it inside the period loop for every tier AND
    every account size - 25x redundant, and it did not finish in ten minutes. The eligible
    set, the momentum and the forward returns depend only on the TIER; only the cost depends
    on the account. So the book is built once per tier and priced afterwards."""
    m = V.resample("ME").sum()
    m.index = m.index.strftime("%Y-%m")
    return m


def build(C, V, F, first, lo, hi, MV, sigma, adv):
    """One tier's weekly book, account-independent. Records what each rebalance TURNED OVER
    along with that name's ADV and volatility, so any account size can be priced later.

    Selection reads only the past: volume rank from the PRIOR calendar month, momentum from
    the trailing LOOK_D days. A coin that stops trading mid-hold exits at its last print -
    market_neutral.py's convention, and how Binance settles a delisted perp."""
    idx = C.index
    months = list(MV.index)
    rows, prev = [], set()
    for i in range(LOOK_D + 1, len(idx) - HOLD_D, HOLD_D):
        t0 = idx[i]
        pm = (pd.Timestamp(t0.strftime("%Y-%m") + "-01")
              - pd.Timedelta(days=1)).strftime("%Y-%m")
        if pm not in MV.index:
            continue
        vol = MV.loc[pm]
        age_ok = (t0 - first).dt.days >= MIN_AGE_D
        live = C.iloc[i].notna() & C.iloc[i - LOOK_D].notna()
        cand = vol[(vol > 0) & age_ok.reindex(vol.index).fillna(False)
                   & live.reindex(vol.index).fillna(False)]
        if len(cand) < MIN_NAMES:
            continue
        tier = list(cand.sort_values(ascending=False).index[lo:hi])
        if len(tier) < MIN_NAMES:
            continue
        mom = (C.iloc[i][tier] / C.iloc[i - LOOK_D][tier] - 1).dropna()
        if len(mom) < MIN_NAMES:
            continue
        order = list(mom.sort_values().index)
        k = max(int(len(order) * FRAC), 3)
        shorts, longs = order[:k], order[-k:]
        both = set(longs) | set(shorts)
        win = C.iloc[i:i + HOLD_D + 1]
        fwd = {s: (float(win[s].dropna().iloc[-1]) if win[s].notna().any()
                   else float(C[s].iat[i])) / float(C[s].iat[i]) - 1 for s in both}
        fnd = {s: float(F[s].iloc[i:i + HOLD_D].sum()) if s in F.columns else 0.0
               for s in both}
        lr = float(np.mean([fwd[s] for s in longs]))
        sr = float(np.mean([fwd[s] for s in shorts]))
        lf = float(np.mean([fnd[s] for s in longs]))
        sf = float(np.mean([fnd[s] for s in shorts]))
        turned = [(float(adv[s].get(t0, np.nan)), float(sigma[s].get(t0, np.nan)))
                  for s in (both ^ prev)]
        rows.append(dict(t=t0, gross=0.5 * lr - 0.5 * sr,
                         carry=0.5 * (-lf) + 0.5 * sf, k=k, n=len(tier),
                         turned=turned,
                         med_adv=float(np.nanmedian([adv[s].get(t0, np.nan) for s in both]))))
        prev = both
    return pd.DataFrame(rows)


def price(book, account):
    """Charge one account size against a prebuilt tier book.

    Each name carries weight 0.5/k of the account regardless of size, so the FEE per rebalance
    is size-invariant and only IMPACT scales - which is the whole point of the exercise.
    Impact uses the square-root law, sigma * sqrt(Q/ADV), charged on each name that turned."""
    if book is None or not len(book):
        return None
    out = book.copy()
    fees, imps = [], []
    for _i, r in book.iterrows():
        w = 0.5 / max(r["k"], 1)
        per_pos = account * w
        fee = FEE * w * len(r["turned"])
        imp = 0.0
        for a, sg in r["turned"]:
            if np.isfinite(a) and a > 0 and np.isfinite(sg):
                imp += sg * np.sqrt(min(per_pos / a, 1.0)) * w
        fees.append(fee); imps.append(imp)
    out["fee"] = fees
    out["imp"] = imps
    out["net"] = out.gross + out.carry - out.fee - out.imp
    return out


def trailing(C, V):
    """30-day trailing daily volatility and dollar ADV per coin, as {sym: {date: value}}."""
    r = C.pct_change()
    sig = r.rolling(30).std()
    a = V.rolling(30).mean()
    return ({s: sig[s].dropna().to_dict() for s in C.columns},
            {s: a[s].dropna().to_dict() for s in C.columns})


def line(lab, df, extra=""):
    if df is None or len(df) < 20:
        print(f"  {lab:<18} too few periods")
        return
    per_yr = 365 / HOLD_D
    m, sd = df.net.mean(), df.net.std(ddof=1)
    sh = m / sd * np.sqrt(per_yr) if sd else np.nan
    t = m / (sd / np.sqrt(len(df))) if sd else np.nan
    print(f"  {lab:<18}{len(df):>5}{m*100:>+9.3f}%{((1+m)**per_yr-1)*100:>+9.0f}%"
          f"{sh:>7.2f}{t:>7.2f}{df.gross.mean()*100:>+9.3f}%{df.carry.mean()*100:>+8.3f}%"
          f"{df.fee.mean()*100:>+7.3f}%{df.imp.mean()*100:>+8.3f}%{extra}")


def split_check(books, reg):
    """The one result nobody predicted: ranks 21-60 beat the mega caps. Does it survive?

    Tune/holdout as everywhere else in this repo (first 60% / last 40% of rebalances), plus the
    PAIRED weekly difference against the mega tier on the SAME weeks, which is the statistic
    that matters - the two tiers share the market, so their difference has far less variance
    than either alone."""
    print()
    print("DOES 21-60 BEAT 1-20, OR IS IT ONE SAMPLE? (gross, account-independent)")
    print(f"  {'tier':<18}{'TUNE/wk':>10}{'t':>7}{'HOLD/wk':>10}{'t':>7}{'ALL/wk':>10}{'t':>7}")
    for lab, b in books.items():
        if b is None or len(b) < 40:
            continue
        cut = b.t.iloc[int(len(b) * 0.6)]
        cells = ""
        for sl in (b[b.t < cut], b[b.t >= cut], b):
            g = sl.gross + sl.carry
            t = g.mean() / (g.std(ddof=1) / len(g) ** 0.5) if g.std(ddof=1) else float("nan")
            cells += f"{g.mean()*100:>+9.3f}%{t:>7.2f}"
        print(f"  {lab:<18}{cells}")

    mega = books["1-20 (mega)"]
    print()
    print("PAIRED vs the mega tier, same weeks (gross+carry). This is the real test.")
    print(f"  {'tier':<18}{'weeks':>7}{'diff/wk':>10}{'t':>7}{'TUNE':>9}{'HOLD':>9}"
          f"{'  verdict':>12}")
    for lab, b in books.items():
        if lab == "1-20 (mega)" or b is None or len(b) < 40:
            continue
        j = pd.merge(b[["t", "gross", "carry"]], mega[["t", "gross", "carry"]],
                     on="t", suffixes=("", "_m"))
        if len(j) < 40:
            continue
        d = (j.gross + j.carry) - (j.gross_m + j.carry_m)
        cut = j.t.iloc[int(len(j) * 0.6)]
        dt = d[(j.t < cut).to_numpy()]
        dh = d[(j.t >= cut).to_numpy()]
        t = d.mean() / (d.std(ddof=1) / len(d) ** 0.5)
        ok = "BOTH HALVES" if dt.mean() > 0 and dh.mean() > 0 and abs(t) > 2 else (
            "both halves, weak t" if dt.mean() > 0 and dh.mean() > 0 else "one half only")
        print(f"  {lab:<18}{len(j):>7}{d.mean()*100:>+9.3f}%{t:>7.2f}"
              f"{dt.mean()*100:>+8.3f}%{dh.mean()*100:>+8.3f}%  {ok}")
    print()
    print("  Registered bar: positive on BOTH halves AND |t| > 2 on the paired difference.")
    print("  Anything less is a sample, not a finding.")


def main():
    C, V, F, first = load_panel()
    print(f"panel: {C.shape[1]} perps (gold/stables dropped), "
          f"{C.index[0]:%Y-%m} .. {C.index[-1]:%Y-%m}")
    sigma, adv = trailing(C, V)
    MV = monthly_volume(V)
    reg = btc_regime(C)
    hdr = (f"  {'tier':<18}{'n':>5}{'net/wk':>10}{'ann':>9}{'Sharpe':>7}{'t':>7}"
           f"{'gross':>10}{'carry':>8}{'fee':>7}{'impact':>8}")

    books = {}
    print()
    print("building each tier once (account-independent)...")
    for lab, (lo, hi) in TIERS.items():
        books[lab] = build(C, V, F, first, lo, hi, MV, sigma, adv)
        b = books[lab]
        print(f"  {lab:<18}{len(b) if b is not None else 0:>5} rebalances, "
              f"{int(b.n.median()) if b is not None and len(b) else 0} names, "
              f"{int(b.k.median()) if b is not None and len(b) else 0} a side")

    store = {}
    for acct in ACCOUNTS:
        print()
        print(f"ACCOUNT ${acct:,.0f}")
        print(hdr)
        for lab in TIERS:
            d = price(books[lab], acct)
            store[(acct, lab)] = d
            med = d.med_adv.median() if d is not None and len(d) else float("nan")
            line(lab, d, f"   ADV ${med/1e6:,.1f}M" if np.isfinite(med) else "")

    print()
    print("WHERE THE EDGE LIVES, net %/wk by tier and account size")
    print(f"  {'tier':<18}" + "".join(f"{f'${a:,.0f}':>14}" for a in ACCOUNTS))
    for lab in TIERS:
        cells = []
        for a in ACCOUNTS:
            d = store.get((a, lab))
            cells.append(f"{d.net.mean()*100:>+13.3f}%" if d is not None and len(d) >= 20
                         else f"{'-':>14}")
        print(f"  {lab:<18}" + "".join(cells))

    print()
    print("BY REGIME at $200 (the account that matters here)")
    print(f"  {'tier':<18}{'bull':>10}{'bear':>10}{'chop':>10}")
    for lab in TIERS:
        d = store.get((200.0, lab))
        if d is None or not len(d):
            continue
        r = pd.Series([reg.asof(t) if t >= reg.index[0] else "chop" for t in d.t])
        cells = "".join(f"{d.net[(r == k).to_numpy()].mean()*100:>+9.3f}%"
                        for k in ("bull", "bear", "chop"))
        print(f"  {lab:<18}{cells}")

    print()
    split_check(books, reg)

    print("  The claim under test: small tiers win at $200 and lose by $2M. If the GROSS")
    print("  column is not larger in small tiers, low capital is not an advantage here and")
    print("  the thesis is dead regardless of what the net column says.")


if __name__ == "__main__":
    main()
