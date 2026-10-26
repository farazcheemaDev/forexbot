"""THE NASDAQ DIP-BUY ON EVERYTHING ELSE BINANCE LISTS AS A TRADFI PERP (2026-10-26)

THE USER (2026-10-26): "find hidden clue if any that can increase our profit and try forex market again".
What is running: news_books.ndx_poll - QQQ bought when RSI(2) < 10 at the US close, out at the first close above the
5-day average (max 10 days), 1x. It is the best live book on the main account (+5.87 USD on one trade) and the one
forex-side candidate that passed both halves (ndx_capit.py: +0.95% a trade). ndx_capit_check.py found it WEAK on the other
equity INDICES (3 of 120 cells). Never tested: the same frozen rule on single stocks, sector/country ETFs and commodity
ETFs - the ~80 series in strategy_analysis/data/tradfi (Yahoo daily, adjusted), all listed by Binance as perps (same
account, same 5 USD minimum, percentage fees - the low-capital route that Exness lots are not).

THE RULE - frozen (news_books.ndx_poll), NOT swept: long at the close when RSI(2) (Wilder, ewm alpha 1/2) < 10; out at the
first later close above the mean of the last 5 closes, or on the 10th day. One position per series. 1x.
COSTS  12bp round trip + funding 3bp per calendar day held on the long (tradfi.py: 1bp/8h, conservative).
CONTROL  the same entry/exit machinery entered on the first free day (every day): a signal's edge is its net return PER DAY
        IN THE MARKET against that control, on the same series and split.
SPLIT  tune = before 2015-08-01 (ndx_capit.py's 60% date), holdout = after. Also 2010+.
t-STAT  by ENTRY DATE (trades of different names that start the same day are averaged first: crashes make them one bet).
SURVIVORSHIP  the series are today's listed, famous names (tradfi.py GROUP_B is flagged as hindsight). Read single stocks
        as an UPPER bound: a pass is a lead, a fail is a clean kill.

REGISTERED BEFORE THE FIRST RUN (2026-10-26)
  D1  Broad ETFs (SPY, QQQ, EWJ, EWY): QQQ reproduces ndx_capit-like numbers; SPY is weaker (ndx_capit_check). At most 2 of
      the 4 pass both halves (net > 0, t >= 2 by entry date).
  D2  Single stocks pooled (survivor-biased, so flattering): net a trade at most +0.5% and per-day-in-market edge over the
      control below 2x on at least one half. FAMILY FAIL.
  D3  Commodity/metal ETFs (GLD SLV PPLT PALL CPER USO BNO UNG): no pass on both halves.
  D4  Fewer than 15% of the individual series pass both halves with >= 20 trades a half (chance gives ~5-10%).
  D5  After 2010 the pooled edge is at most half its pre-2010 size.
KILL LINE  the family is dead if pooled single stocks + ETFs are <= 0 net on the holdout, or the per-day edge over the
        control is < 2x on either half. LEAD (never a pass, survivorship): t >= 2 by entry date on both halves AND
        per-day edge >= 2x control on both AND positive after 2010.

    python -m backtest.stock_dip
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
DATA = ROOT / "strategy_analysis" / "data" / "tradfi"
FEE = 12.0 / 1e4
FUND_DAY = 3.0 / 1e4
RSI_MAX, MAXD, SPLIT = 10.0, 10, pd.Timestamp("2015-08-01")
BROAD = ["SPY", "QQQ", "EWJ", "EWY"]
COMMOD = ["GLD", "SLV", "PPLT", "PALL", "CPER", "USO", "BNO", "UNG"]


def load(sym: str) -> pd.Series:
    d = pd.read_csv(DATA / f"{sym}_1d.csv", parse_dates=["time"]).dropna(subset=["close"])
    return d.set_index("time")["close"].astype(float)


def rsi2(c: pd.Series) -> pd.Series:
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=0.5, adjust=False).mean()
    dn = (-d).clip(lower=0).ewm(alpha=0.5, adjust=False).mean()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))


def trades(c: pd.Series, control: bool = False, fund: float = FUND_DAY) -> pd.DataFrame:
    """Sequential non-overlapping long trades. Entry: the close of a signal day (or any free day for the control)."""
    v, idx = c.to_numpy(), c.index
    sig = np.ones(len(c), bool) if control else (rsi2(c).to_numpy() < RSI_MAX)
    sma5 = c.rolling(5).mean().to_numpy()
    out, i = [], 30
    while i < len(v) - 1:
        if not sig[i]:
            i += 1
            continue
        j = i + 1
        while j < len(v) - 1 and not (v[j] > sma5[j] or j - i >= MAXD):
            j += 1
        cal = (idx[j] - idx[i]).days
        out.append((idx[i], idx[j], v[j] / v[i] - 1 - FEE - fund * cal, j - i))
        i = j + 1 if control else j      # a signal can fire on the exit day itself; the next trade starts after it
    return pd.DataFrame(out, columns=["t0", "t1", "net", "days"])


def stats(tr: pd.DataFrame, ctl: pd.DataFrame | None = None) -> dict:
    if not len(tr):
        return dict(n=0)
    g = tr.groupby("t0")["net"].mean()                        # one bet per entry date
    t = g.mean() / (g.std(ddof=1) / np.sqrt(len(g))) if len(g) > 2 and g.std(ddof=1) > 0 else float("nan")
    pdm = tr["net"].sum() / tr["days"].sum()
    out = dict(n=len(tr), dates=len(g), net=tr["net"].mean(), win=(tr["net"] > 0).mean(), t=t, perday=pdm)
    if ctl is not None and len(ctl):
        out["ctl_perday"] = ctl["net"].sum() / ctl["days"].sum()
    return out


def fmt(s: dict) -> str:
    if not s.get("n"):
        return "no trades"
    cd = s.get("ctl_perday")
    ratio = (s["perday"] / cd) if cd and cd > 0 else float("nan")
    return (f"n {s['n']:5d} ({s['dates']:4d} dates) net {s['net'] * 100:+6.2f}% win {s['win'] * 100:3.0f}% "
            f"t {s['t']:+5.1f} | per day {s['perday'] * 1e4:+6.1f}bp vs ctl {(cd or 0) * 1e4:+5.1f}bp (x{ratio:4.1f})")


def split(df: pd.DataFrame, part: str) -> pd.DataFrame:
    if part == "tune":
        return df[df.t0 < SPLIT]
    if part == "hold":
        return df[df.t0 >= SPLIT]
    if part == "2010+":
        return df[df.t0 >= pd.Timestamp("2010-01-01")]
    return df


def pooled(names: list, store: dict, label: str) -> dict:
    res = {}
    print(f"\n== {label} ({len(names)} series)")
    for part in ("all", "tune", "hold", "2010+"):
        tr = pd.concat([split(store[n][0], part).assign(sym=n) for n in names if n in store], ignore_index=True)
        ct = pd.concat([split(store[n][1], part) for n in names if n in store], ignore_index=True)
        s = stats(tr, ct)
        res[part] = s
        print(f"  {part:6s} {fmt(s)}")
    return res


def both_halves(store: dict, s: str):
    tu = stats(split(store[s][0], "tune"), split(store[s][1], "tune"))
    ho = stats(split(store[s][0], "hold"), split(store[s][1], "hold"))
    return tu, ho


def main():
    syms = sorted(p.name[:-7] for p in DATA.glob("*_1d.csv"))
    store = {}
    for s in syms:
        c = load(s)
        store[s] = (trades(c), trades(c, control=True))
    stocks = [s for s in syms if s not in BROAD + COMMOD]
    print(f"rule: RSI(2) < {RSI_MAX:g} at the close, out > 5-day mean or day {MAXD}; costs 12bp + {FUND_DAY * 1e4:g}bp/day; "
          f"tune < {SPLIT.date()}")
    for label, names in (("D1  broad ETFs, one by one", BROAD), ("D3  commodities, one by one", COMMOD)):
        print(f"\n== {label}")
        npass = 0
        for s in names:
            tu, ho = both_halves(store, s)
            ok = all(x.get("n", 0) >= 20 and x["net"] > 0 and x["t"] >= 2 for x in (tu, ho))
            npass += ok
            print(f"  {s:5s} tune {fmt(tu)}\n        hold {fmt(ho)}   {'PASS' if ok else '-'}")
        print(f"  {npass} of {len(names)} pass both halves")
    pooled(BROAD, store, "BROAD ETFs pooled")
    pooled(COMMOD, store, "COMMODITY / METAL ETFs pooled")
    pooled(stocks, store, "SINGLE STOCKS pooled (survivor-biased upper bound)")
    ok_n, tested = 0, 0
    for s in stocks:
        tu, ho = both_halves(store, s)
        if tu.get("n", 0) >= 20 and ho.get("n", 0) >= 20:
            tested += 1
            ok_n += all(x["net"] > 0 and x["t"] >= 2 for x in (tu, ho))
    print(f"\n== D4  single stocks passing both halves (>= 20 trades a half): {ok_n} of {tested} = {ok_n / max(tested, 1) * 100:.0f}%")
    allp = pooled(syms, store, "EVERYTHING pooled")
    print("\n== VERDICT LINES")
    ho = allp["hold"]

    def ratio(r):
        c = r.get("ctl_perday", 0)
        if c <= 0:                       # the control loses after costs: any positive per-day return is "above 2x"
            return float("inf") if r["perday"] > 0 else float("nan")
        return r["perday"] / c

    dead = ho["net"] <= 0 or not (ratio(allp["tune"]) >= 2 and ratio(ho) >= 2)
    lead = (allp["tune"]["t"] >= 2 and ho["t"] >= 2 and ratio(allp["tune"]) >= 2 and ratio(ho) >= 2
            and allp["2010+"]["net"] > 0)
    print(f"  everything pooled: holdout net {ho['net'] * 100:+.2f}%, per-day edge x{ratio(allp['tune']):.1f} / x{ratio(ho):.1f} "
          f"-> {'DEAD' if dead else ('LEAD' if lead else 'NEITHER')}")
    allt = pd.concat([store[s][0] for s in syms])
    pre, post = allt[allt.t0 < pd.Timestamp("2010-01-01")], allt[allt.t0 >= pd.Timestamp("2010-01-01")]
    print(f"  D5: pre-2010 net {pre['net'].mean() * 100:+.2f}% ({len(pre)} trades) vs 2010+ {post['net'].mean() * 100:+.2f}% ({len(post)})")


if __name__ == "__main__":
    main()
