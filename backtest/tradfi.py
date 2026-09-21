"""THE DEPLOYED STRATEGY ON BINANCE'S TRADFI PERPS - more independent bets for the same book.

WHY THIS, AND WHY NOW
    The crypto book's ceiling is correlation: 12 coins at mean pairwise correlation 0.63
    are ~1.5 independent bets (corr_alloc.py). More coins cannot fix that. Different
    MARKETS can. Silver alone showed a monthly correlation of -0.042 with the blend.

    Binance futures now lists 199 TradFi perps on the same account, same code, same $5
    minimum: gold, silver, platinum, palladium, copper, WTI, Brent, natural gas, SPY, QQQ,
    country ETFs and ~150 single stocks. None of it existed when forex.py ran on Exness.

WHAT IS TESTED
    The deployed rules unchanged: bb_break(30, 1.5), long pyramid 5 units every 2R with a
    20xATR trail, short 1 unit on a 5xATR trail, breakeven at 3R. On DAILY bars, because
    the perps are months old and the underlyings have 15-20 years of daily history, which
    covers 2008, 2011, 2015, 2020 and 2022. Daily sits closest to the 12h sleeve.

    Group A - commodities and index ETFs. A classic managed-futures list, chosen before
              looking, so no selection on outcome. ETFs rather than Yahoo's continuous
              futures, because continuous futures are not roll-adjusted (a CL or NG roll
              shows up as a fake price jump) and the ETF price already carries the roll
              cost a long perp pays through funding.
    Group B - the single stocks Binance lists. FLAGGED AS HINDSIGHT: Binance listed them
              BECAUSE they are famous now, which is the same selection-on-outcome that put
              a 3x premium into the crypto book. Read B as an upper bound.

WHAT IS CHARGED, conservatively
    12bp round trip per unit, and 1bp per 8h of funding on every LONG unit for every day
    held (~11%/yr, about 3x silver's measured rate). Shorts are charged fees only.
    GAP FILLS: a stop that the market opens through fills at the OPEN, not at the stop.
    run_pyramid fills at the stop price, which is fine for 24/7 crypto and wrong for
    anything with an overnight or weekend close.

    python -m backtest.tradfi
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.shortside import signals  # noqa: E402
from bot.core.indicators import atr as atr_ind  # noqa: E402

CACHE = Path(__file__).resolve().parents[1] / "strategy_analysis" / "data" / "tradfi"
FEE = 12.0 / 1e4
FUND_PER_DAY = 3 * 1.0 / 1e4          # 1bp per 8h, charged to longs
SL, LTRAIL, STRAIL, UNITS, ADD, BE = 2.0, 20.0, 5.0, 5, 2.0, 3.0

GROUP_A = {"GLD": "gold", "SLV": "silver", "PPLT": "platinum", "PALL": "palladium",
           "CPER": "copper", "USO": "WTI crude", "BNO": "Brent", "UNG": "natural gas",
           "SPY": "S&P 500", "QQQ": "Nasdaq 100", "EWY": "Korea", "EWJ": "Japan"}
GROUP_B = ["NVDA", "TSLA", "AAPL", "MSFT", "META", "GOOGL", "AMZN", "AMD", "AVGO", "TSM",
           "MU", "INTC", "ORCL", "PLTR", "COIN", "MSTR", "HOOD", "QCOM", "CSCO", "DIS",
           "UBER", "WMT", "JPM", "V", "HD", "BABA", "IBM", "LLY", "NVO", "AMAT", "CRM",
           "CRWD", "DELL", "ARM", "MRVL", "RKLB", "ASTS", "NOK", "PYPL", "BRK-B"]


def load(tk):
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / f"{tk}_1d.csv"
    if f.exists():
        d = pd.read_csv(f, parse_dates=["time"])
    else:
        import yfinance as yf
        raw = yf.download(tk, period="max", interval="1d", auto_adjust=True,
                          progress=False, threads=False)
        if raw is None or raw.empty:
            return None
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = raw.columns.get_level_values(0)
        d = raw.reset_index().rename(columns={"Date": "time", "Open": "open",
                                              "High": "high", "Low": "low",
                                              "Close": "close", "Volume": "volume"})
        d = d[["time", "open", "high", "low", "close", "volume"]].dropna()
        d.to_csv(f, index=False)
    d = d[d.time >= "2005-01-01"].reset_index(drop=True)
    return d if len(d) > 400 else None


def simulate(df):
    """Long pyramid + short trail with GAP-AWARE stop fills. Returns a DataFrame of
    positions: entry time, exit time, side, R (per unit-1 risk, all units, net)."""
    o, h, l, c = (df[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    t = df["time"].to_numpy()
    a = atr_ind(df, 14).to_numpy(float)
    out = []
    for side in ("long", "short"):
        s = signals(df, side, "all").to_numpy()
        d = 1 if side == "long" else -1
        want = 1                                  # Action.BUY for long, SELL for short
        if side == "short":
            want = 2
        pos = None
        for i in range(1, len(df)):
            if pos is None and s[i] == want and np.isfinite(a[i - 1]) and a[i - 1] > 0:
                r = SL * a[i - 1]
                pos = dict(r=r, stop=o[i] - d * r, best=o[i], bar=i, ent=[o[i]], nxt=1,
                           held=[i])
            if pos is None:
                continue
            r = pos["r"]
            hit = (l[i] <= pos["stop"]) if d > 0 else (h[i] >= pos["stop"])
            if hit:
                gap = (o[i] < pos["stop"]) if d > 0 else (o[i] > pos["stop"])
                px = o[i] if (gap and i > pos["bar"]) else pos["stop"]
                R = sum(d * (px - e) for e in pos["ent"]) / r
                R -= sum(FEE * e for e in pos["ent"]) / r
                if d > 0:
                    R -= sum(FUND_PER_DAY * e * (i - b) for e, b in
                             zip(pos["ent"], pos["held"])) / r
                out.append((t[pos["bar"]], t[i], side, R, len(pos["ent"])))
                pos = None
                continue
            if d > 0 and len(pos["ent"]) < UNITS:
                if (h[i] - pos["ent"][0]) / r >= pos["nxt"] * ADD:
                    pos["ent"].append(pos["ent"][0] + pos["nxt"] * ADD * r)
                    pos["held"].append(i)
                    pos["nxt"] += 1
            if d > 0:
                pos["best"] = max(pos["best"], h[i])
                cand = pos["best"] - LTRAIL * a[i - 1]
                if (pos["best"] - pos["ent"][0]) / r >= BE:
                    cand = max(cand, pos["ent"][0])
                pos["stop"] = max(pos["stop"], cand)
            else:
                pos["best"] = min(pos["best"], l[i])
                cand = pos["best"] + STRAIL * a[i - 1]
                if (pos["ent"][0] - pos["best"]) / r >= BE:
                    cand = min(cand, pos["ent"][0])
                pos["stop"] = min(pos["stop"], cand)
        if pos is not None:
            px = c[-1]
            R = sum(d * (px - e) for e in pos["ent"]) / pos["r"]
            out.append((t[pos["bar"]], t[-1], side, R, len(pos["ent"])))
    return pd.DataFrame(out, columns=["t0", "t1", "side", "R", "units"])


def stats(R):
    R = np.asarray(R)
    if len(R) < 5:
        return None
    w, lz = R[R > 0].sum(), -R[R < 0].sum()
    return dict(n=len(R), mean=R.mean(), pf=w / lz if lz > 0 else np.inf)


def asset_table(names, label):
    print(f"\n  {label}")
    print(f"  {'':<22}{'from':>6}{'pos':>6}{'meanR':>8}{'PF':>6} |{'first 60%':>10}"
          f"{'last 40%':>10} |{'long R':>8}{'short R':>8}  verdict")
    rows, trades = [], {}
    for tk, nm in names.items():
        df = load(tk)
        if df is None:
            print(f"  {tk:<6}{nm:<16} no data"); continue
        tr = simulate(df)
        if len(tr) < 10:
            continue
        cut = df.time.iloc[int(len(df) * 0.6)]
        a, b = tr[tr.t0 < cut], tr[tr.t0 >= cut]
        s, sa, sb = stats(tr.R), stats(a.R), stats(b.R)
        L, S = tr[tr.side == "long"].R.mean(), tr[tr.side == "short"].R.mean()
        ok = sa and sb and sa["mean"] > 0 and sb["mean"] > 0
        v = "HOLDS" if ok else ("dies OOS" if sa and sa["mean"] > 0 else
                                ("one regime" if sb and sb["mean"] > 0 else "dead"))
        print(f"  {tk:<6}{nm:<16}{df.time.iloc[0].year:>6}{s['n']:>6}{s['mean']:>+8.3f}"
              f"{s['pf']:>6.2f} |{sa['mean'] if sa else np.nan:>+10.3f}"
              f"{sb['mean'] if sb else np.nan:>+10.3f} |{L:>+8.3f}{S:>+8.3f}  {v}")
        rows.append((tk, s["mean"], ok))
        trades[tk] = tr
    held = sum(1 for r in rows if r[2])
    print(f"  -> {held} of {len(rows)} hold in both halves; "
          f"{sum(1 for r in rows if r[1] > 0)} positive overall")
    return trades


def monthly(tr, risk=0.30):
    s = pd.Series(tr.R.to_numpy() * risk / 100, index=pd.DatetimeIndex(tr.t1))
    return s.resample("ME").sum()


def blend_monthly():
    """The deployed crypto blend by close date, same allocator as escalate.evaluate."""
    from backtest import blend, escalate
    rows = escalate.build()
    bear = blend.btc_bear()
    f0 = blend.RISK / 100.0
    opens, out = [], []
    for a_, b_, row, side in rows:
        opens = [u for u in opens if u > a_]
        if len(opens) >= 12:
            continue
        opens.append(b_)
        try: ib = bool(bear.asof(a_))
        except Exception: ib = False
        f = f0 * (blend.REGIME_MULT if ib else 1.0)
        r = float(row.sum()) if side == "long" else float(row[0])
        out.append((pd.Timestamp(b_), r * f))
    s = pd.Series([x[1] for x in out], index=pd.DatetimeIndex([x[0] for x in out]))
    return s.resample("ME").sum()


def book(trades, slots, risk=0.30, t_from=None):
    """Shared-slot allocator across all assets, compounded by close date."""
    allr = pd.concat([tr.assign(tk=k) for k, tr in trades.items()]).sort_values("t0")
    opens, out = [], []
    for t0, t1, R in zip(allr.t0, allr.t1, allr.R):
        if t_from is not None and t0 < t_from:
            continue
        opens = [u for u in opens if u > t0]
        if len(opens) >= slots:
            continue
        opens.append(t1)
        out.append((pd.Timestamp(t1), R * risk / 100))
    s = pd.Series([x[1] for x in out], index=pd.DatetimeIndex([x[0] for x in out]))
    return s.resample("ME").sum()


def curve_stats(m):
    cur = np.cumprod(np.maximum(1 + m.values, 0))
    pk = np.maximum.accumulate(np.maximum(cur, 1e-12))
    yrs = max(len(m) / 12, 0.1)
    return dict(mo=((max(cur[-1], 1e-12)) ** (1 / (yrs * 12)) - 1) * 100,
                dd=float((1 - cur / pk).max() * 100), up=float((m > 0).mean() * 100))


def main():
    print("DEPLOYED RULES ON TRADFI UNDERLYINGS, DAILY BARS, gap-aware fills, "
          "12bp + 1bp/8h funding on longs")
    A = asset_table(GROUP_A, "GROUP A - commodities and index ETFs (chosen before looking)")
    B = asset_table({k: "" for k in GROUP_B},
                    "GROUP B - single stocks Binance lists (HINDSIGHT: listed because famous)")

    print("\n" + "=" * 100)
    print("DOES IT ADD INDEPENDENT BETS?  monthly correlation with the crypto blend, and "
          "within group A")
    print("=" * 100)
    cm = blend_monthly()
    ma = {k: monthly(v) for k, v in A.items()}
    M = pd.DataFrame(ma).fillna(0.0)
    both = M.join(cm.rename("CRYPTO"), how="inner")
    print(f"  overlap {len(both)} months ({both.index[0]:%Y-%m} .. {both.index[-1]:%Y-%m})")
    print("  corr with crypto blend: " + "  ".join(
        f"{k} {both[k].corr(both['CRYPTO']):+.2f}" for k in M.columns))
    C = M[M.index >= "2012-01-01"].corr().values
    off = C[np.triu_indices_from(C, 1)]
    k = len(M.columns)
    eff = k / (1 + (k - 1) * np.nanmean(off))
    print(f"  group A: mean pairwise corr {np.nanmean(off):+.2f} -> ~{eff:.1f} effective "
          f"bets of {k}   (crypto: 0.63 -> 1.5 of 12)")

    print("\n  group A as its own book, 8 shared slots, 0.30%/unit (full history):")
    ga = book(A, 8)
    s = curve_stats(ga[ga.index >= "2008-01-01"])
    print(f"    {s['mo']:+.2f}%/mo compounded, max DD {s['dd']:.0f}%, {s['up']:.0f}% of "
          f"months up")
    for y in range(2008, 2027):
        x = ga[ga.index.year == y]
        if len(x):
            print(f"      {y}: {x.sum()*100:+6.1f}%", end="")
            if y % 4 == 3:
                print()
    print()

    print("\n  COMBINED with the crypto blend over the overlap (monthly sums, no rebalancing "
          "subtleties):")
    j = pd.DataFrame({"crypto": cm, "A": ga}).dropna()
    for lab, w in (("crypto only", (1, 0)), ("crypto + group A", (1, 1)),
                   ("crypto + group A x2 risk", (1, 2))):
        m = j["crypto"] * w[0] + j["A"] * w[1]
        s = curve_stats(m)
        print(f"    {lab:<28} {s['mo']:+6.2f}%/mo  max DD {s['dd']:5.1f}%  "
              f"months up {s['up']:.0f}%")
    print("  (crypto figures here are raw - no 3x hindsight haircut - so compare the rows "
          "with each other, not with doc 00)")


if __name__ == "__main__":
    main()
