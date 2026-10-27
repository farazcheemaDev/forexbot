"""THE YEARS WITHOUT HINDSIGHT - the main account's machine, year by year, with its trend book on coins chosen at the time (2026-10-27)

THE USER (2026-10-27): "re-run the yearly numbers with the trend book trading coins chosen point-in-time (no hindsight list), so I
can see what the current setup would really have made each year".
WHY: the machine's yearly backtest (backtest/all_books.py - the series the dashboard judges the live account against) trades its trend
book on blend.BOOK, 12 alts picked in 2026 knowing they became big, and shrinks that book's gains 3x as a rough correction. That book
made 51% of 2021 and 84% of 2024 on a fixed $300. Every other book already picks its coins point-in-time.
HERE the trend book trades, each month, the 12 most-traded ALTS by the PRIOR month's quote volume (perp archive, dead coins included,
wide_book's 30-day minimum age). BTC, ETH, stablecoins, metals, oil and stock tokens are left out because the live list holds none
(SPXUSDT = the SPX6900 memecoin and DIAUSDT = the DIA oracle token are crypto and stay in). Today's rules, unchanged: the triple (tight
exit, time stop under +2R after 100 bars, 7 units), funding per unit, real entry times (lottery_v2.pit_units), simulated by
dd_fixes.sim as final_machine.trend_capped does it - 12 slots, guard 6.25x, the 21-day anchor, x0.25 while BTC is under its 1000h
average. NO hindsight shrink: a point-in-time universe needs none (CLAUDE.md rule 5; the asymmetry would flatter the shrunk side).
Every other book is all_books.machine_books' own. A year's number = profit on a FIXED $300 (daily returns summed, no compounding),
the median of the 10 orderings; the books' medians do not add exactly to the total's.
LINES
    HINDSIGHT   all_books as published (blend.BOOK, gains shrunk)
    PIT ALTS    the coins swapped, nothing else
    PIT ALTS + CLOSE   and a slot frees / P&L books when the exit bar CLOSES (label + 1h), as the bot does (mistake #17) - THE HONEST LINE
    PIT TOP-12  lottery_v2's universe (BTC, ETH, gold ... included), slot at the close - a sensitivity line
CHECK (run first): the 12 hindsight coins through THIS pipeline (perp archive data, every month eligible, gains shrunk the same way,
    slot at the label) against all_books' trend book. Registered tolerance: 2020-26 total within 15%, the same sign every year.

REGISTERED BEFORE THE RUN (2026-10-27)
    Y1 The PIT trend book's 2024 is under half the hindsight book's +$1,863 (SUI, ENA and WLD made the hindsight 2024).
    Y2 Its 2021 is at least the hindsight book's +$1,217 (the 2021 alt bull ran in the most-traded coins, and nothing is shrunk).
    Y3 It loses money in 2022, as the hindsight book did (-$125).
    Y4 The whole machine's 2020-26 fixed-$300 profit on the honest line is 20-50% under the published +$8,400 ($4,200-$6,720).
    Y5 On the honest line every calendar year is still positive for the whole machine.
    Y6 Freeing the slot at the bar close cuts the PIT trend book's 2020-26 total by 5-20%.

RESULT (2026-10-27 18:31 UTC, logs/pit_years.txt) - the TOTAL survives the coin swap; WHICH YEARS made it does not.
    CHECK passed: the 12 hindsight coins through this pipeline +$4,468 vs all_books' +$4,282 over 2020-26, same sign every year
    (yearly gaps up to ~$230 from the data source and funding treatment).
    Trend book, fixed $300, hindsight (shrunk) -> PIT alts at the close: 2020 +342 -> +216, 2021 +1,217 -> +1,703, 2022 -125 -> -16,
    2023 +344 -> +510, 2024 +1,863 -> +470, 2025 +315 -> +1,334, 2026 +290 -> +212; 2020-26 +4,282 -> +4,545. Whole machine
    +8,385 -> +8,645 (2020 +723, 2021 +2,939, 2022 +365, 2023 +915, 2024 +834, 2025 +2,228, 2026 to Sep +566), every year positive.
    The 3x hindsight shrink happened to land near the point-in-time total; it moved 2024's money (SUI / ENA / WLD) that a 2024 trader
    would not have had, and the point-in-time book made 2025 instead - mostly ONE coin: MYX (the 2025-09 squeeze, in the alt top 12
    only 2025-09 / 10) = 76% of 2025's winning long R; without it the trend book's 2025 is +639 and the machine's +1,558
    (2020-26 machine +7,977). Slot at the bar close vs the label, PAIRED: +$10 +- 185, 6/10 - no difference in this book.
    Y1, Y2, Y3, Y5 right; Y4 WRONG (I expected 20-50% less; it is ~the same), Y6 WRONG (no measurable cost, not a 5-20% cut).
    STILL A BACKTEST: the other 8 books were chosen on these same years, the engine is not the live bot's position model (CLAUDE.md
    2026-10-06: one position per key, retry, a one-bar pause - not modelled here), no capacity limit, and the live record (main -15%
    in 18 days, ~8th percentile of its band) is the measurement that counts.

    python -m backtest.pit_years            (~10 min the first time: caches the per-coin rows in logs/daily_combos_cache/)
"""
from __future__ import annotations

import pickle
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

LOG = ROOT / "logs" / "pit_years.txt"
ROWS = ROOT / "logs" / "daily_combos_cache" / "pit_years_rows.pkl"
YEARS = range(2020, 2027)
STAKE = 300.0
HOUR = 3_600_000_000_000
TOP = 12
NOT_CRYPTO = {"BTC", "ETH", "USDC", "PAXG", "XAUT", "XAU", "XAG", "XPT", "XPD", "CL", "BZ", "NATGAS", "COPPER", "AAPL", "AMD", "AMZN",
              "AVGO", "BABA", "COIN", "CRCL", "GME", "GOOGL", "HOOD", "INTC", "IWM", "META", "MSFT", "MSTR", "NFLX", "NVDA", "ORCL",
              "PLTR", "QQQ", "SPY", "TSLA"}
PUBLISHED = 8400.0                                  # all_books, the 7 years' totals on a fixed $300 (2026-10-27 reply)


class Every:
    """A month set that holds every month: rows are built once per coin and filtered per universe afterwards."""
    def __contains__(self, m):
        return True


def coin_rows(sym: str) -> list:
    """lottery_v2.pit_units for one coin on every month, rule by rule, each row tagged with its rule and its signal bar's month."""
    from backtest import lottery as lt
    from backtest import lottery_v2 as L2
    from backtest.causal_t0 import LATE
    out = []
    try:
        for rule in ("1h", "4h", "12h"):
            lt.RULES = (rule,)
            late = LATE[rule].value
            for r in L2.pit_units(sym, Every()):
                r["rule"] = rule
                r["m"] = pd.Timestamp(r["t0"] + late).strftime("%Y-%m")       # pit_units filters on this month
                out.append(r)
    except FileNotFoundError:
        return []
    return out


def eligibility(top_n: int, keep) -> dict:
    """wide_book.eligibility with a filter on the symbols allowed to compete."""
    from backtest.wide_book import DATA, MIN_AGE_D
    vols, first = {}, {}
    for p in DATA.glob("*_1d.csv.gz"):
        s = p.name.split("_")[0]
        if not keep(s):
            continue
        try:
            d = pd.read_csv(p, parse_dates=["time"])
        except Exception:                           # noqa: BLE001 - as wide_book: an unreadable file is skipped
            continue
        if len(d) < 5:
            continue
        first[s] = d.time.iloc[0]
        vols[s] = d.set_index("time")["qvol"].resample("ME").sum()
    V = pd.DataFrame(vols).fillna(0.0)
    elig = {s: set() for s in V.columns}
    for i in range(1, len(V.index)):
        cur = V.index[i]
        mstart = cur.to_period("M").start_time
        ok = [s for s in V.columns if (mstart - first[s]).days >= MIN_AGE_D]
        for s in V.loc[V.index[i - 1], ok].sort_values(ascending=False).index[:top_n]:
            elig[s].add(cur.strftime("%Y-%m"))
    return elig


def is_alt(s: str) -> bool:
    return s.endswith("USDT") and s[:-4] not in NOT_CRYPTO


def select(rows_by: dict, elig: dict, close: bool) -> list:
    """The universe's rows in dd_fixes.sim's form; close=True frees the slot and books the P&L at the exit bar's close."""
    out = []
    for s, months in elig.items():
        for r in rows_by.get(s, []):
            if r["m"] not in months:
                continue
            t1 = r["t1"] + (HOUR if close else 0)
            n = len(r["uR"])
            out.append(dict(t0=r["t0"], t1=t1, side=r["side"], uR=np.asarray(r["uR"], float), ut=list(r["ut"]), ue=list(r["ue"]),
                            uc=[t1] * n, risk=r["risk"], coin=s, rule=r["rule"]))
    out.sort(key=lambda z: z["t0"])
    return out


def trend_series(rows: list, shrink: bool = False) -> dict:
    """{seed: daily return} exactly as final_machine.trend_capped(6.25) builds it."""
    import backtest.dd_fixes as Dd
    from backtest import machine_combos as mc
    from backtest.bull_boost import regimes
    from backtest.worst_month import TCACHE
    cache = pickle.loads(TCACHE.read_bytes()) if shrink else None
    bear = regimes()[1000]
    bn, bv = pd.DatetimeIndex(bear.index).as_unit("ns").asi8, bear.to_numpy(bool)
    out = {}
    for sd in mc.SEEDS:
        r = Dd.sim(rows, bn, bv, sd, lev=6.25, size_fn=Dd.anchor(21)).pct_change().fillna(0.0)
        if shrink:
            s = cache[("shrink", sd)]
            r = pd.Series(np.where(r > 0, s * r, r), index=r.index)
        out[sd] = r
    return out


def by_year(series: dict, idx_by_seed: dict) -> np.ndarray:
    """orderings x years: profit on a fixed $300."""
    return np.array([[series[sd].reindex(idx_by_seed[sd]).fillna(0.0)[lambda x: x.index.year == y].sum() * STAKE for y in YEARS]
                     for sd in sorted(series)])


def main():
    t_start = time.time()
    from backtest import blend
    from backtest.all_books import machine_books, ndx_dip, news_book
    from backtest.final_machine import trend_capped
    from backtest.wide_book import eligibility as wide_elig

    alts = eligibility(TOP, is_alt)
    top12 = wide_elig(TOP)
    book = {("1000SHIBUSDT" if c == "SHIBUSDT" else c): Every() for c in blend.BOOK}
    need = sorted({s for e in (alts, top12) for s, m in e.items() if m} | set(book))
    if ROWS.exists():
        rows_by = pickle.loads(ROWS.read_bytes())
    else:
        rows_by = {}
    todo = [s for s in need if s not in rows_by]
    if todo:
        with ProcessPoolExecutor(max_workers=6) as ex:
            for s, rs in zip(todo, ex.map(coin_rows, todo, chunksize=2)):
                rows_by[s] = rs
        ROWS.write_bytes(pickle.dumps(rows_by))
    print(f"rows for {len(need)} coins ({sum(len(v) for v in rows_by.values()):,} positions), {time.time() - t_start:.0f}s", flush=True)

    M = machine_books()
    idx = {sd: x.index for sd, x in zip(sorted(trend_capped(6.25)), M)}
    news_all, ndx_all = news_book(), ndx_dip()
    print(f"machine books built, {time.time() - t_start:.0f}s", flush=True)

    hind = by_year(trend_capped(6.25), idx)
    check = by_year(trend_series(select(rows_by, book, close=False), shrink=True), idx)
    lines = {
        "PIT ALTS": by_year(trend_series(select(rows_by, alts, close=False)), idx),
        "PIT ALTS + CLOSE": by_year(trend_series(select(rows_by, alts, close=True)), idx),
        "PIT TOP-12 + CLOSE": by_year(trend_series(select(rows_by, top12, close=True)), idx),
    }
    # added after the first run (2026-10-27 18:20 UTC), which showed MYX alone = 76% of the winning long R in 2025
    no_myx = {s: m for s, m in alts.items() if s != "MYXUSDT"}
    lines["PIT ALTS + CLOSE, NO MYX"] = by_year(trend_series(select(rows_by, no_myx, close=True)), idx)
    others = np.array([[(x.drop(columns="trend").sum(axis=1) + news_all.reindex(x.index).fillna(0.0)
                         + ndx_all.reindex(x.index).fillna(0.0))[lambda s: s.index.year == y].sum() * STAKE for y in YEARS] for x in M])

    med = lambda a: np.median(a, axis=0)  # noqa: E731
    fmt = lambda v: "".join(f"{x:>+9,.0f}" for x in v)  # noqa: E731
    head = f"{'':34}" + "".join(f"{y:>9}" for y in YEARS) + f"{'2020-26':>10}"
    L = [f"backtest/pit_years.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; the main account's machine, profit a year on a FIXED $300 "
         f"(no compounding), median of 10 orderings; {M[0].index[0]:%Y-%m-%d} .. {M[0].index[-1]:%Y-%m-%d} (2020 from Feb, 2026 to Sep)", ""]
    L += ["CHECK - the 12 hindsight coins through this pipeline vs all_books' trend book (both shrunk, slot at the label)", head]
    L.append(f"  {'all_books trend (published)':32}" + fmt(med(hind)) + f"{np.median(hind.sum(axis=1)):>+10,.0f}")
    L.append(f"  {'this pipeline, same 12 coins':32}" + fmt(med(check)) + f"{np.median(check.sum(axis=1)):>+10,.0f}")
    ok_tot = abs(np.median(check.sum(axis=1)) / np.median(hind.sum(axis=1)) - 1) <= 0.15
    ok_sign = bool(np.all(np.sign(med(check)) == np.sign(med(hind))))
    L.append(f"  total within 15%: {ok_tot}; same sign every year: {ok_sign}")
    L += ["", "THE TREND BOOK ALONE", head]
    L.append(f"  {'HINDSIGHT (published, shrunk)':32}" + fmt(med(hind)) + f"{np.median(hind.sum(axis=1)):>+10,.0f}")
    for k, a in lines.items():
        L.append(f"  {k:32}" + fmt(med(a)) + f"{np.median(a.sum(axis=1)):>+10,.0f}")
    L += ["", "THE WHOLE MACHINE (trend + the 8 other books, unchanged)", head]
    tots = {"HINDSIGHT (published)": hind + others}
    tots.update({k: a + others for k, a in lines.items()})
    for k, a in tots.items():
        L.append(f"  {k:32}" + fmt(med(a)) + f"{np.median(a.sum(axis=1)):>+10,.0f}")
    hon = tots["PIT ALTS + CLOSE"]
    L.append(f"  range of the honest line over the 10 orderings, by year: "
             + ", ".join(f"{y} {a:+,.0f}..{b:+,.0f}" for y, a, b in zip(YEARS, hon.min(axis=0), hon.max(axis=0))))
    L.append(f"  the other 8 books alone: " + fmt(med(others)) + f"  total {np.median(others.sum(axis=1)):+,.0f}")
    dd = (lines["PIT ALTS + CLOSE"] - lines["PIT ALTS"]).sum(axis=1)
    L.append(f"  slot at the close minus at the label, PAIRED on each ordering (trend, 2020-26): mean {dd.mean():+,.0f} "
             f"se {dd.std(ddof=1) / np.sqrt(len(dd)):,.0f}, the close better in {int((dd > 0).sum())}/10")

    tr, trc = med(lines["PIT ALTS"]), med(lines["PIT ALTS + CLOSE"])
    h = med(hind)
    tot_h = float(np.median(hon.sum(axis=1)))
    cut = 1 - np.median(lines["PIT ALTS + CLOSE"].sum(axis=1)) / np.median(lines["PIT ALTS"].sum(axis=1))
    L += ["", "REGISTERED PREDICTIONS",
          f"  Y1 PIT trend 2024 under half of +$1,863: {trc[4]:+,.0f} -> {'RIGHT' if trc[4] < h[4] / 2 else 'WRONG'}",
          f"  Y2 PIT trend 2021 >= hindsight +$1,217: {trc[1]:+,.0f} -> {'RIGHT' if trc[1] >= h[1] else 'WRONG'}",
          f"  Y3 PIT trend loses in 2022: {trc[2]:+,.0f} -> {'RIGHT' if trc[2] < 0 else 'WRONG'}",
          f"  Y4 machine 2020-26 on the honest line $4,200-$6,720: {tot_h:+,.0f} -> {'RIGHT' if 4200 <= tot_h <= 6720 else 'WRONG'}",
          f"  Y5 every year positive on the honest line: {', '.join(f'{x:+,.0f}' for x in med(hon))} -> "
          f"{'RIGHT' if np.all(med(hon) > 0) else 'WRONG'}",
          f"  Y6 slot at the close cuts the PIT trend total 5-20%: {cut * 100:.1f}% -> {'RIGHT' if 0.05 <= cut <= 0.20 else 'WRONG'}",
          "", f"coins in the PIT alts universe over the span: {sum(1 for m in alts.values() if m)}; run {time.time() - t_start:.0f}s"]
    LOG.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
