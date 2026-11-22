"""WHAT THE NOVEMBER 2026 CRASH TEACHES - a post-mortem of the live paper record, checked against the backtest (2026-11-21)

THE USER (2026-11-21): "keep the paper bots running but can we learn something from these days". The final machine's main account
is $207.70 (-30.8%, 0.9th percentile) and fresh $164.59 (-45.1%) on 2026-11-20; BTC fell from $86.6k (09-21) to $58.4k; the day-45
line (doc 22 s3b, $261.30 on 2026-11-23) will not be met. Nothing in any bot changes here (code freeze, doc 22 s4). Read-only.

PART A - THE LIVE RECORD (copies of the VM's logs, Binance USD-M daily closes)
  A1  WHAT THE ACCOUNT HELD: the netted coin ledger rebuilt from combo_exec.csv (every dry order, the same netting a real account
      would do; coins Bitget does not list and orders under its $5 minimum are not in it), valued at each day's close: long, short
      and net exposure as a multiple of the live equity, before the crash (to 2026-11-09) and in it (2026-11-10..20). The NASDAQ
      dip-buy's QQQUSDT is shown apart from the crypto book.
  A2  HOW IT MOVED WITH THE MARKET: each account's daily live-equity return regressed on the equal-weight return of the alt market
      (the backtest's own point-in-time top-40, see PIT ALTS below), on BTC and on QQQ, before and during the crash.
  A3  THE MARKET-NEUTRAL BOOK LEG BY LEG: each weekly basket in combo_mn.csv held as fixed coins, equal weights per leg (the live
      book weights the names by the momentum / RSI halves; indicative), close of the bar before the rebalance to the close of the
      bar before the next one; the long names' own 30-day return at the rebalance ('how pumped the longs were').
PART B - NEW, OR THE BOOK'S KNOWN RISK? (the backtest's own data and engines)
  B1  The market-neutral blend (half 30-day momentum, half RSI(14), weekly, +50% short exit, 12bp turnover, funding; the copy of
      audit_mn_vol_screen.run below reproduces moderate_retests.scored_run exactly) on all 7 rebalance weekdays: long-leg and
      short-leg returns in CRASH weeks (a rebalance on a day BTC is >= 20% under its 60-day high and >= 15% down in 30 days - the
      2026-11-15 analogue rule) against all weeks, by half; and the long names' 30-day return at those rebalances.
  B2  The bear sleeve (breadth_trade.ladder, the live label = market_neutral.btc_regime's BEAR, fixed cut-offs 0.10 / 0.288,
      lag 1, the top-10 basket) over the first 5, 7 and 14 days after each time the label turns BEAR, against the live sleeve.
PART C - THE TWO LIVE PHASES AMONG THE BACKTEST'S OWN WINDOWS (added 2026-11-21, after Parts A and B had run)
  C1  THE LIVE STATE in the backtest's terms (works_map.build's definitions on Binance closes): the BTC label
      (market_neutral.btc_regime), the fuel share (runner_gate: share of the PIT top-40 alts up > 20% in 30 days, closes through
      the day before) with the backtest's own tercile cut-offs (news/fuel_bands.json, 2020-07..2026-09), the median alt's 30 days.
  C2  PHASE A = the October bleed (bars 2026-10-09..11-05, 28 days, BTC labelled bull then chop) and PHASE B = the crash (bars
      11-06..11-19, 14 days): the main account's live equity over each (dashboard curve, logs/dashboard/eq_main_h.csv) against
      the backtest machine's return over every window of the same length whose BTC move and alt-index move are each within a
      tolerance of the live phase's (+-5 / +-7 points; a wider +-8 / +-11 line beside it), pooled over the 10 slot orderings
      (all_books.machine_books via logs/daily_combos_cache/alt_bear_books.pkl, + works_map's news and NASDAQ dip-buy series:
      the 9 books the live bot runs, at its weights; trend GAINS shrunk 3x for hindsight, losses raw - so the backtest side is if
      anything flattered DOWN). Each book: the live dollars (booked + open, from the dashboard feed at 11-06 11:36 and 11-20 21:00
      UTC, so up to 21 hours off the daily bars) as a share of the phase's starting equity, against the same book in the matched
      windows.
PART D - IS capit2's MISSING CRASH PROFIT THE BOT OR THE MARKET? (added 2026-11-21, after Part C's second run showed the
  backtest machine making a median +23% in 42-day windows with main's market move, capit2 alone +9.7%, while live capit2 took
  3 trades): capit2's signal recomputed with the bot's own function (final_books.capit_signals) on Binance 4h bars of the
  point-in-time top-40, every closed 4h bar since 10-09, the limit fill and exits as capit2_poll runs them; and how many days
  the backtest's capit2 closed trades in the matched windows.
PIT ALTS: for each day d the top-40 by the PRIOR month's quote volume of the month holding d-1 (daily_live_vs_backtest.month_top,
  the wide_book.eligibility rule), BTC and non-crypto out; the backtest side uses the panel's own eligibility(40) the same way.
  Coins delisted from Binance since September are missing from the live side (it reads today's list).

REGISTERED BEFORE RUNNING (2026-11-21, after reading the live feed only; no backtest number below had been computed)
  L1  The main account was net LONG through the crash: average placeable net exposure >= +0.5x its equity over 11-10..11-20. (70%)
  L2  Its daily beta to the alt index is >= +0.3 in the crash and lower before it. (55%)
  L3  Live market-neutral: from the 10-30 basket on, the long leg lost more than the short leg made in >= 3 of 4 weeks, and the
      long names had risen >= +30% (median) in the 30 days before they were bought. (65%)
  L4  Backtest crash weeks: the long leg loses on average there too, and the short leg covers it (net >= 0) - so what is NEW
      live is the short leg not paying enough, not the long leg falling. (55%)
  L5  Backtest crash weeks: the long names' median 30-day run-up at the rebalance is SMALLER than live's. (60%)
  L6  Backtest sleeve: the first 14 days after a BEAR flip lose money in more than half of the flips. (40%)
REGISTERED 2026-11-21 AFTER PARTS A AND B HAD RUN, BEFORE ANY PART C NUMBER WAS COMPUTED
  L7  Phase A (the bleed): the main account's live result is under the 10th percentile of the matched backtest windows. (55%)
  L8  Phase B (the crash): the live result is under the matched windows' median (75%) and under their 10th percentile (45%).
  L9  Phase A by book: the live market-neutral and daily books are each under their matched 10th percentile; trend is not. (45%)
  L10 Phase A in the backtest's state terms: >= 60% of its days were fuel LOW with BTC labelled bull or chop - the machine's one
      known losing corner (works_map.py: BULL + fuel LOW) and its neighbour. (70%)

AMENDMENT (2026-11-21, after the first run; its log is kept as logs/crash_lessons_first_run.txt): (a) the ledger valuation left out
  QQQUSDT (a TradFi perp, not in klines_all's PERPETUAL list) - the NASDAQ dip-buy's ~1x long; now valued from its own klines and
  shown apart; (b) the alt index used November's top-40 for October's days too, a list ranked on October's volume (it knew
  October's hype coins): now the point-in-time list of each day's month (PIT ALTS); (c) A3 printed a basket struck after the last
  close (no closed bar) and counted it in L3. L1-L6 are scored on the corrected run; the first run's A1 / A3 numbers otherwise stand.
AMENDMENT 2 (2026-11-21, after Part C's first run): (a) its date check correlated the machine's SIGNED daily return with the alt
  index (+0.03 / -0.03 / -0.02 at lags -1 / 0 / +1) and printed 'NOT same-day' - an uninformative test, because the books bet both
  ways; it now uses the sleeve book's SIZE against the alt index's size on the sleeve's active days (same-day +0.55, a day off +0.04
  / +0.08; the whole machine +0.14 vs +0.04 / +0.01), which confirms the books are dated by the bar they earn on; (b) two
  DESCRIPTIVE rows were added: main's whole record (AB) and fresh's (F, its crowd book's -$27.81 at the 11-20 feed added back),
  because the A / B split by book falls at 2026-11-06 11:36 UTC, inside a violent micro-cap day (AIN -62%, AKE +130%), where a
  daily-marked book's open P&L is the day's intraday move (carry showed +$12.4 open there): the whole record has no inner boundary.
  The predictions are about A and B only and are scored as registered.
REGISTERED 2026-11-21 BEFORE PART D RAN (after Part C's second run)
  D1  The replay finds the same signals the live bot took (3: ADA and SOL on 11-14/15, FIL later) and no more: the bot's capit2
      is faithful, and this crash produced few capitulation signals - a slow grind, not a flush. (65%)
  D2  In the matched backtest windows, capit2 closed trades on >= 5 days in the median window (vs 2 live). (60%)

RESULT (2026-11-21, logs/crash_lessons.txt; the first run's log logs/crash_lessons_first_run.txt)
  * NOT A MARKET BET: main's placeable CRYPTO book was net SHORT throughout (-0.26x before 11-10, -0.11x in the crash; gross 1.6x /
    1.1x) beside a NASDAQ long (QQQ +0.42x / +0.28x); its daily beta to the PIT alt index was -0.01 over 33 days (+0.13 before,
    -0.28 in the crash); on the worst alt day (11-14, -11.1%) it made +2.3%. Fresh: crypto net +0.06x / -0.11x. The losses are
    in WHICH coins were held. L1, L2 wrong.
  * OUTSIDE THE BACKTEST OVER THE WHOLE RECORD (C2): main's 42 days (bars 10-09..11-19; BTC -24.2%, the alt index -28.7% - a 6th /
    10th percentile market) -24.9%, below every one of the 890 backtest windows with the same market move (15 start months;
    machine median +23.1%, 25% of them lost, worst -24.1%; the wider match 0.1th percentile). Fresh, crowd book taken out,
    34 days: -29.5% against a median +29.1%, also below all 680. Phase by phase it looked like 1 in 10: the October bleed
    (28 days, BTC -6.9%, alts -18.2%) -16.6% = 8.0th percentile (L7 right), the crash (14 days, BTC -18.5% = a 3rd-percentile
    fortnight) -10.0% = 10.0th (L8 half right). Two such phases back to back are not in the backtest.
  * THE GAP BY BOOK (whole record, live vs the matched windows' median, % of the $300 start): market-neutral -11.8 vs +5.1 (9th
    percentile; made in October, -12.7% = 3rd percentile of that phase), daily -11.7 vs -4.6 (8th), capit2 +0.7 vs +9.7 (16th),
    sleeve -5.0 vs +1.6 (0th), NASDAQ dip-buy -5.2 vs +1.3 (0th), bids -0.1 vs +1.3 (3rd); trend +0.3 vs -3.4 (76th: its shorts
    paid +8.5% of the account in the crash), carry +3.3 vs +1.0 (69th, then off at the $5 floor from 11-13). L9 wrong (daily 12th).
    The live by-book figures run to the 11-20 21:00 feed, a day past the windows (11-20: BTC -5.7%); the sleeve's -5.0 includes
    -4.2 points from that day (booked to the 11-19 close: -0.7). The 890 windows are overlapping cuts of ~15 distinct episodes.
  * capit2 IS FAITHFUL (D): the bot's own capit_signals on Binance 4h bars gives exactly the live bot's 3 trades (SOL, ADA, FIL at
    11-14 20:00, same limits, same exits); 11 RSI-under-20-on-volume hits in 257 bars, 5 with a 10% drop, one wave. D1 right.
    The backtest's capit2 also closed trades on a median 2 days a matched window (D2 wrong) - its crash waves paid more. This
    decline had fewer flush days: 4 days of -5% or worse on the alt index against a median 6 in the matched windows (10th 5),
    worst day -11.1% against a median -13.2%.
  * MARKET-NEUTRAL (A3, B1): the live long names fell more than the short names in 5 of 6 weeks (main); the first two baskets'
    longs had run up +134% / +110% in 30 days. In the backtest's 252 crash weeks (25 months) the blend loses too, -0.93%/wk, 61%
    of weeks, on both halves (-0.85 / -1.08) - but from the OTHER leg: last month's losers (the shorts) bounce +1.95%/wk (the
    textbook momentum crash), while the long names drift -0.52%/wk (L4 wrong). Crash weeks' longs had run up less (+13% median vs
    live +29%; L5 right); weeks with the most-pumped longs are on average BETTER (+1.47%/wk vs +1.23%). Switching MN off in BEAR
    weeks failed on 2026-10-08 (logs/mn_combos.txt).
  * THE SLEEVE (B2): the label turned BEAR on 11-16, with BTC already 25% under its 60-day high; with breadth at 1.7% it went long;
    -7.1% of the account in 5 days (with 11-20's -5.7% BTC day) = 3rd percentile of the backtest's 35 flips' first 5 days, worse
    than all 11 low-breadth flips (-3.5% .. +5.9%). Over 14 days the backtest's low-breadth flips made money 73% of the time
    (mean +1.9%; worst 2022-05-10, LUNA, -10.8%); 43% of all flips lose (L6 wrong).
  * THE STATE (C1): the record started at the top of an alt run - fuel HIGH (48% of the top-40 up > 20% in 30 days, median alt
    +10%) in the week of 10-09 - then MID, then LOW from 10-23; BTC bull to 10-22, chop to 11-15, bear from 11-16. Phase A was
    fuel LOW on 36% of days (L10 wrong): not the backtest's BULL + LOW corner, a hot alt market rolling over.
  Predictions: L5, L7, D1 right; L8 half; L1-L4, L6, L9, L10, D2 wrong - my prior that the account lost as a long bet was wrong.

    python -m backtest.crash_lessons <folder with the copied live logs> [--parts ABCD]
"""
from __future__ import annotations

import csv
import json
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

LOG = ROOT / "logs" / "crash_lessons.txt"
CRASH0 = pd.Timestamp("2026-11-10")
TRADFI = {"QQQUSDT"}                       # TradFi perps the bot holds (the NASDAQ dip-buy): valued, but kept apart from crypto
MACH = ["trend", "mn_blend", "carry", "sleeve", "bids", "daily", "capit2", "news", "ndx_dip"]      # works_map.MACHINE
# The main account's two phases: live equity from the dashboard curve; each book's booked + open dollars (gross of fees) from
# the dashboard feed (dashboard_push.py --print): at 2026-11-06 11:36 UTC as quoted in CLAUDE.md s10's 2026-11-06 entry, and at
# 2026-11-20 21:00 UTC (copy in the session scratchpad, audit1121/feed.json); phase B = the second minus the first.
PHASES = {
    "A": dict(aid="main", name="the October bleed", first="2026-10-09", last="2026-11-05", feed="10-09 00:04 .. 11-06 11:36 UTC",
              books=dict(trend=-19.2, mn_blend=-38.2, carry=24.0, sleeve=0.0, bids=1.1, daily=-22.6, capit2=0.0, news=0.0,
                         ndx_dip=-5.6), e0_feed=300.00, e0_live=300.0),
    "B": dict(aid="main", name="the crash", first="2026-11-06", last="2026-11-19", feed="11-06 11:36 .. 11-20 21:00 UTC",
              books=dict(trend=20.16, mn_blend=2.68, carry=-14.09, sleeve=-14.88, bids=-1.52, daily=-12.50, capit2=2.02,
                         news=0.93, ndx_dip=-9.88), e0_feed=236.56, e0_live=None),
    # DESCRIPTIVE, added after Part C's first run (AMENDMENT 2): the whole record, no boundary inside it
    "AB": dict(aid="main", name="main's whole record so far", first="2026-10-09", last="2026-11-19", feed="10-09 00:04 .. 11-20 21:00 UTC",
               books=dict(trend=0.96, mn_blend=-35.52, carry=9.91, sleeve=-14.88, bids=-0.42, daily=-35.10, capit2=2.02, news=0.93,
                          ndx_dip=-15.48), e0_feed=300.00, e0_live=300.0),
    "F": dict(aid="fresh", name="fresh's whole record, its crowd book taken out (the backtest machine has none)", first="2026-10-17",
              last="2026-11-19", feed="10-17 01:15 .. 11-20 21:00 UTC",
              books=dict(trend=-13.95, mn_blend=-40.85, carry=16.27, sleeve=-11.40, bids=-0.35, daily=-34.66, capit2=1.90, news=0.85,
                         ndx_dip=-20.71), e0_feed=300.00, e0_live=300.0, add=27.81),        # the crowd book's -$27.81 (11-20 feed) added back
}
TOL = ((0.05, 0.07), (0.08, 0.11))         # (BTC, alt index) tolerance: primary, wider
OUT: list = []


def say(s=""):
    print(s, flush=True)
    OUT.append(s)


# ------------------------------------------------------------------ prices
def closes(K: dict) -> pd.DataFrame:
    """Binance daily closes, one column a symbol, indexed by the bar's OPEN day (the close is the price at the next 00:00 UTC)."""
    cols = {}
    for s, d in K.items():
        cols[s] = pd.Series(d.c.to_numpy(float), index=pd.to_datetime(d.t, unit="ms").dt.normalize())
    return pd.DataFrame(cols).sort_index()


def tradfi_closes() -> pd.DataFrame:
    """The TradFi perps' daily closes (QQQUSDT is not in klines_all's PERPETUAL list), the same convention as closes()."""
    from backtest.daily_live_vs_backtest import FAPI, get
    cols = {}
    for s in sorted(TRADFI):
        k = (get(f"{FAPI}/fapi/v1/klines?symbol={s}&interval=1d&limit=400") or [])[:-1]       # the forming bar dropped
        if k:
            cols[s] = pd.Series([float(x[4]) for x in k], index=pd.to_datetime([int(x[0]) for x in k], unit="ms").normalize())
    return pd.DataFrame(cols)


def binance_sym(bitget: str, cols) -> str | None:
    """The ledger's Bitget name ('PEPE/USDT:USDT') -> a Binance column and the unit scale (Binance 1000PEPE = 1,000 PEPE)."""
    base = bitget.split("/")[0]
    for cand, scale in ((base + "USDT", 1.0), ("1000" + base + "USDT", 1000.0), (base.replace("1000", "", 1) + "USDT", 1 / 1000.0)):
        if cand in cols:
            return cand, scale
    if base == "RAY" and "RAYSOLUSDT" in cols:
        return "RAYSOLUSDT", 1.0
    if base.startswith("1M") and "1000" + base[2:] + "USDT" in cols:
        return "1000" + base[2:] + "USDT", 1 / 1000.0
    return None


def pit_alts(K: dict, C: pd.DataFrame, since: str) -> pd.DataFrame:
    """The live alt market on the backtest's definitions (PIT ALTS in the docstring): for each day d, the members of the month
    holding d-1; ret = their equal-weight return over bar d, alt30 = their median 30-day return and fuel = the share up > 20%,
    both from closes through d-1 (works_map.alt_median_30, runner_gate.runner_state)."""
    from backtest.daily_live_vs_backtest import month_top
    from backtest.market_neutral import NON_CRYPTO
    tops, rows = {}, {}
    for d in C.index[C.index >= pd.Timestamp(since)]:
        p, p31 = d - pd.Timedelta(days=1), d - pd.Timedelta(days=31)
        if p not in C.index or p31 not in C.index:
            continue
        mon = f"{p:%Y-%m}"
        if mon not in tops:
            tops[mon] = [s for s in month_top(K, mon, 40) if s != "BTCUSDT" and s[:-4] not in NON_CRYPTO and s in C.columns]
        mem = tops[mon]
        r1 = (C.loc[d, mem] / C.loc[p, mem] - 1).dropna()
        r30 = (C.loc[p, mem] / C.loc[p31, mem] - 1).dropna()
        rows[d] = dict(ret=float(r1.mean()), alt30=float(r30.median()), fuel=float((r30 > 0.20).mean()), n=len(r1))
    return pd.DataFrame(rows).T


# ------------------------------------------------------------------ A1: the ledger
def ledger_exposure(folder: Path, acct: str, C: pd.DataFrame, eq_day: pd.Series) -> pd.DataFrame:
    rows = list(csv.DictReader(open(folder / acct / "combo_exec.csv", newline="")))
    pos: dict = {}
    by_day = {}
    days = sorted({r["ts"][:10] for r in rows})
    i = 0
    rows.sort(key=lambda r: r["ts"])
    for day in pd.date_range(days[0], C.index[-1], freq="D"):
        dkey = f"{day:%Y-%m-%d}"
        while i < len(rows) and rows[i]["ts"][:10] <= dkey:
            r = rows[i]
            q = float(r["qty"] or 0.0)
            pos[r["symbol"]] = pos.get(r["symbol"], 0.0) + (q if r["side"] == "buy" else -q)
            i += 1
        lng = sht = tf = 0.0
        for s, q in pos.items():
            if abs(q) < 1e-12:
                continue
            m = binance_sym(s, C.columns)
            if m is None or day not in C.index:
                continue
            px = C.at[day, m[0]]
            if not np.isfinite(px):
                continue
            v = q * px / m[1]
            if m[0] in TRADFI:
                tf += v
            elif v > 0:
                lng += v
            else:
                sht -= v
        by_day[day] = (lng, sht, tf)
    df = pd.DataFrame(by_day, index=["long", "short", "tradfi"]).T
    df["equity"] = eq_day.reindex(df.index).ffill()
    df["net_x"] = (df["long"] - df["short"]) / df["equity"]
    df["gross_x"] = (df["long"] + df["short"]) / df["equity"]
    df["tradfi_x"] = df["tradfi"] / df["equity"]
    return df


def unmapped(folder: Path, acct: str, cols) -> dict:
    """Open ledger coins with no Binance price column (they would silently drop out of A1)."""
    pos: dict = {}
    for r in csv.DictReader(open(folder / acct / "combo_exec.csv", newline="")):
        q = float(r["qty"] or 0.0)
        pos[r["symbol"]] = pos.get(r["symbol"], 0.0) + (q if r["side"] == "buy" else -q)
    return {s: q for s, q in pos.items() if abs(q) > 1e-12 and binance_sym(s, cols) is None}


def live_equity_by_day(folder: Path, acct: str, aid: str) -> pd.Series:
    """The live equity at each UTC day's end: the dashboard's hourly curve (live = booked + open) where it exists, the bot's
    booked daily marks before it."""
    h = pd.read_csv(folder / "dashboard" / f"eq_{aid}_h.csv", header=None, names=["t", "e"])
    s = pd.Series(h.e.to_numpy(float), index=pd.to_datetime(h.t, unit="s")).groupby(lambda x: x.normalize()).last()
    st = json.loads((folder / acct / "combo_state.json").read_text())
    hist = pd.Series({pd.Timestamp(d) - pd.Timedelta(days=1): e for d, e in st.get("eq_hist") or []}, dtype=float)
    hist = hist[hist.index < s.index[0]]
    return pd.concat([hist, s]).sort_index()


# ------------------------------------------------------------------ A3: the live market-neutral legs
def live_mn_legs(folder: Path, acct: str, C: pd.DataFrame) -> pd.DataFrame:
    out = []
    rows = list(csv.DictReader(open(folder / acct / "combo_mn.csv", newline="")))
    for k, r in enumerate(rows):
        d = pd.Timestamp(r["day"])
        t0 = d - pd.Timedelta(days=1)                              # the bar the basket was struck on
        t1 = (pd.Timestamp(rows[k + 1]["day"]) if k + 1 < len(rows) else C.index[-1] + pd.Timedelta(days=1)) - pd.Timedelta(days=1)
        t1 = min(t1, C.index[-1])
        if t1 <= t0:                                               # struck after the last close: nothing to measure yet
            continue
        legs = {}
        for side, names in (("long", r["longs"].split()), ("short", r["shorts"].split())):
            rets, pumps = [], []
            for nm in names:
                s = nm + "USDT" if nm + "USDT" in C.columns else nm
                if s not in C.columns:
                    continue
                p0, p1 = C.at[t0, s] if t0 in C.index else np.nan, C.at[t1, s] if t1 in C.index else np.nan
                p30 = C.at[t0 - pd.Timedelta(days=30), s] if t0 - pd.Timedelta(days=30) in C.index else np.nan
                if np.isfinite(p0) and np.isfinite(p1):
                    r_ = p1 / p0 - 1
                    if side == "short":
                        r_ = min(r_, 0.5)                          # the +50% short exit, at its level
                    rets.append(r_)
                if np.isfinite(p0) and np.isfinite(p30):
                    pumps.append(p0 / p30 - 1)
            legs[side] = (float(np.mean(rets)) if rets else np.nan, float(np.median(pumps)) if pumps else np.nan, len(rets))
        out.append(dict(day=r["day"], t0=t0, to=f"{t1:%m-%d}", long=legs["long"][0], short=legs["short"][0],
                        net=0.5 * legs["long"][0] - 0.5 * legs["short"][0], long_pump=legs["long"][1], short_pump=legs["short"][1],
                        n=(legs["long"][2], legs["short"][2])))
    return pd.DataFrame(out)


# ------------------------------------------------------------------ B1: the backtest MN legs in crash weeks
def backtest_mn_legs():
    from backtest import mn_combos as m
    from backtest import moderate_retests as mr
    HOLD, LOOK, FRAC = 7, 30, 0.1
    Dd = m.ohl()
    idx, X_, Fx, ff = Dd["idx"], Dd["X"], Dd["Fx"], Dd["ff"]
    Cm = pd.DataFrame(X_)
    dlt = Cm.diff()
    up = dlt.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    dn = (-dlt.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    RSI = (100 - 100 / (1 + up / dn.replace(0, np.nan))).to_numpy()
    MOM = X_ / np.r_[np.full((30, X_.shape[1]), np.nan), X_[:-30]] - 1

    def run(score_mat, start=0):
        rows, pl_, ps_ = [], set(), set()
        for i in range(LOOK + 1 + start, len(idx) - HOLD - 1, HOLD):
            t0 = idx[i]
            ok = (Dd["Em"][Dd["months"][i]] & ((t0.value - Dd["fv"]) // 86_400_000_000_000 >= m.MIN_AGE_D)
                  & np.isfinite(X_[i]) & np.isfinite(X_[i - LOOK]))
            if ok.sum() < 20:
                continue
            cand = np.flatnonzero(ok)
            past = score_mat[i, cand]
            k = max(int(len(cand) * FRAC), 3)
            order = cand[np.argsort(np.where(np.isnan(past), np.inf, past), kind="stable")]
            sh, lo = order[:k], order[-k:]
            fwd = (ff[i + HOLD] / X_[i] - 1).copy()
            for x in sh:
                lvl = X_[i, x] * 1.5
                for dd in range(i + 1, i + HOLD + 1):
                    if np.isfinite(Dd["Hi"][dd, x]) and Dd["Hi"][dd, x] >= lvl:
                        fwd[x] = max(Dd["Op"][dd, x], lvl) / X_[i, x] - 1
                        break
            fnd = Fx[i + 1:i + HOLD + 1].sum(axis=0)
            gl, gs = 0.5 * fwd[lo].mean(), -0.5 * fwd[sh].mean()
            carry = 0.5 * (-fnd[lo].mean()) + 0.5 * fnd[sh].mean()
            L_, S_ = {Dd["cols"][x] for x in lo}, {Dd["cols"][x] for x in sh}
            cost = m.FEE * min((len(L_ ^ pl_) + len(S_ ^ ps_)) / (4 * k), 1.0)
            pl_, ps_ = L_, S_
            pump_lo = float(np.nanmedian(MOM[i, lo]))
            rows.append((t0, gl + gs + carry - cost, gl, gs, pump_lo))
        return pd.DataFrame(rows, columns=["t0", "net", "long", "short", "pump"]).set_index("t0")

    a = run(MOM, 0)
    b = mr.scored_run(MOM, start=0, stop="short_only", short_stop=0.5)
    shifted = a["net"].copy()
    shifted.index = shifted.index + pd.Timedelta(days=HOLD)
    assert np.allclose(shifted.to_numpy(), b.reindex(shifted.index).to_numpy(), atol=1e-12), "parity with scored_run failed"
    weeks = []
    for st in range(7):
        x, y = run(MOM, st), run(RSI, st)
        z = x.join(y, lsuffix="_m", rsuffix="_r", how="inner")
        weeks.append(pd.DataFrame({"net": 0.5 * (z.net_m + z.net_r), "long": 0.5 * (z.long_m + z.long_r),
                                   "short": 0.5 * (z.short_m + z.short_r), "pump": z[["pump_m", "pump_r"]].mean(axis=1),
                                   "start": st}, index=z.index))
    return pd.concat(weeks), Dd


def crash_days(btc: pd.Series) -> pd.Series:
    dd60 = btc / btc.rolling(60).max() - 1
    r30 = btc / btc.shift(30) - 1
    return (dd60 <= -0.20) & (r30 <= -0.15)


# ------------------------------------------------------------------ B2: the sleeve after a BEAR flip
def backtest_sleeve_after_flip():
    from backtest.bear_label_test import LIVE, label, signal
    from backtest.breadth_trade import instruments, ladder
    from backtest.carry_check import exact_funding
    from backtest.market_neutral import btc_regime, load_panel
    Cp, F, first = load_panel()
    Cp.index = Cp.index.astype("datetime64[ns]")
    feat = pd.read_csv(ROOT / "logs" / "regime_signals_features.csv.gz", index_col=0, parse_dates=True)
    feat.index = feat.index.astype("datetime64[ns]")
    br = feat["breadth20"].reindex(Cp.index)
    Fx = exact_funding(Cp.index, Cp.columns)
    ins = instruments(Cp, Fx, first)
    btc = Cp["BTCUSDT"].dropna()
    bear = label(btc, *LIVE).reindex(Cp.index).fillna(False)
    assert (bear.to_numpy() == (btc_regime(Cp).reindex(Cp.index) == "bear").to_numpy()).all(), "label != btc_regime"
    ret, fund, rebal = ins["top-10 basket"]
    x, pos = ladder(signal(bear, br), ret, fund, rebal, 1)
    b = bear.to_numpy(bool)
    flips = [Cp.index[i] for i in range(1, len(b)) if b[i] and not b[i - 1]]
    rows = []
    for f in flips:
        for n in (5, 7, 14):
            w = x[(x.index >= f) & (x.index < f + pd.Timedelta(days=n))]
            mkt = ret[(ret.index >= f) & (ret.index < f + pd.Timedelta(days=n))]
            rows.append(dict(flip=f, days=n, sleeve=float((1 + w).prod() - 1), basket=float((1 + mkt).prod() - 1),
                             breadth=float(br.get(f, np.nan)), in_mkt=float(pos.reindex(w.index).abs().mean())))
    return pd.DataFrame(rows), Cp


# ------------------------------------------------------------------ C: the live phases among the backtest's windows
def backtest_alts():
    """The backtest's alt index on the same definitions: the equal-weight return over bar d of the panel's PIT top-40 (BTC and
    non-crypto out, members at d-1, as works_map.alt_median_30 / runner_gate pick them), and BTC's close."""
    from backtest.market_neutral import drop_non_crypto, load_panel
    from backtest.regime_signals import member_mask
    from backtest.wide_book import eligibility
    Cp, _, first = load_panel()
    Cp.index = Cp.index.astype("datetime64[ns]")
    X = Cp.to_numpy(float)
    mem = member_mask(Cp, first, drop_non_crypto(eligibility(40))) & np.isfinite(X)
    mem[:, list(Cp.columns).index("BTCUSDT")] = False
    r = np.full(len(Cp), np.nan)
    for d in range(1, len(Cp)):
        m = mem[d - 1] & np.isfinite(X[d]) & np.isfinite(X[d - 1])
        if m.sum() >= 8:
            r[d] = float(np.mean(X[d, m] / X[d - 1, m] - 1))
    return pd.Series(r, index=Cp.index), Cp["BTCUSDT"]


def machine_frames() -> list:
    """The 9-book machine, one frame per slot ordering: all_books.machine_books' 7 books + works_map's news and NASDAQ series."""
    M = pickle.loads((ROOT / "logs" / "daily_combos_cache" / "alt_bear_books.pkl").read_bytes())
    S = pickle.loads((ROOT / "logs" / "works_map_series.pkl").read_bytes())["S"]
    out = []
    for x in M:
        x = x.copy()
        for b in ("news", "ndx_dip"):
            x[b] = S[b].reindex(x.index).fillna(0.0)
        out.append(x[MACH].asfreq("D"))
    return out


def windows(frames: list, n: int, alt_r: pd.Series, btc: pd.Series) -> pd.DataFrame:
    """Every n-day window (ending on each day) of each ordering: the machine compounded, each book summed (share of the account),
    BTC close to close and the alt index compounded over the same bars."""
    la = np.log1p(alt_r)
    out = []
    for k, x in enumerate(frames):
        mach = np.log1p(x.sum(axis=1, min_count=len(MACH)))
        R = pd.DataFrame({"machine": np.expm1(mach.rolling(n, min_periods=n).sum())}, index=x.index)
        for b in MACH:
            R[b] = x[b].rolling(n, min_periods=n).sum()
        R["alt"] = np.expm1(la.reindex(x.index).rolling(n, min_periods=n).sum())
        b_ = btc.reindex(x.index)
        R["btc"] = b_ / b_.shift(n) - 1
        R["order"] = k
        out.append(R.dropna())
    return pd.concat(out)


def pctl(sample, v) -> float:
    s = np.asarray(sample, float)
    s = s[np.isfinite(s)]
    return float((s < v).mean() * 100) if len(s) else float("nan")


def part_c(folder: Path, C: pd.DataFrame, PA: pd.DataFrame, res: dict):
    from backtest.market_neutral import btc_regime
    say("")
    say("=== C1 the live market in the backtest's state terms (BTC label, fuel = share of the PIT top-40 alts up > 20% in 30 days, "
        "the median alt's 30 days)")
    q = json.loads((ROOT / "news" / "fuel_bands.json").read_text())["q"]["runners"]
    lo, hi = q[33], q[67]
    lab = btc_regime(C).reindex(PA.index)
    own = pd.read_csv(folder / "combo_bot_dry_final" / "combo_marks.csv", index_col=0, parse_dates=True)["regime"]
    both = own.index.intersection(lab.dropna().index)
    agree = (lab.reindex(both) == own.reindex(both)).mean()
    fuel_state = pd.Series(np.where(PA.fuel < lo, "LOW", np.where(PA.fuel > hi, "HIGH", "MID")), index=PA.index)
    say(f"  fuel cut-offs from news/fuel_bands.json: LOW < {lo:.3f}, HIGH > {hi:.3f}; the BTC label on Binance closes agrees with "
        f"the bot's own logged label on {agree:.0%} of the {len(both)} days both have")
    btc = C["BTCUSDT"]
    say("  week of     BTC label        fuel share (state)   median alt 30d   alt index   BTC     ")
    for w0 in pd.date_range("2026-10-09", PA.index[-1], freq="7D"):
        part = PA[(PA.index >= w0) & (PA.index < w0 + pd.Timedelta(days=7))]
        if not len(part):
            continue
        labs = lab.reindex(part.index).value_counts()
        fs = fuel_state.reindex(part.index).value_counts()
        b0, b1 = btc.get(part.index[0] - pd.Timedelta(days=1), np.nan), btc.get(part.index[-1], np.nan)
        say(f"  {w0:%m-%d}      {' '.join(f'{k} {v}' for k, v in labs.items()):<16} {part.fuel.mean():5.1%} "
            f"({' '.join(f'{k} {v}' for k, v in fs.items()):<12})  {part.alt30.iloc[-1]:+6.1%}        "
            f"{float((1 + part.ret).prod() - 1):+6.1%}    {b1 / b0 - 1:+6.1%}")
    pa = PA[(PA.index >= PHASES["A"]["first"]) & (PA.index <= PHASES["A"]["last"])]
    corner = ((fuel_state.reindex(pa.index) == "LOW") & lab.reindex(pa.index).isin(["bull", "chop"])).mean()
    res["L10"] = corner
    say(f"  phase A ({PHASES['A']['first']}..{PHASES['A']['last']}): fuel LOW with BTC bull or chop on {corner:.0%} of days "
        f"(LOW on {(fuel_state.reindex(pa.index) == 'LOW').mean():.0%}, MID {(fuel_state.reindex(pa.index) == 'MID').mean():.0%}, "
        f"HIGH {(fuel_state.reindex(pa.index) == 'HIGH').mean():.0%})")

    say("")
    say("=== C2 the main account's two phases against the backtest machine over windows with the same market move")
    say("  backtest: 9 books at the live weights, 10 slot orderings pooled, trend gains shrunk 3x (losses raw); market = BTC close "
        "to close and the PIT top-40 alt index (equal weight, daily), the same construction on both sides")
    alt_bt, btc_bt = backtest_alts()
    frames = machine_frames()
    sl = sum(f["sleeve"] for f in frames) / len(frames)
    nz = sl[sl.abs() > 1e-9]
    cors = {L: float(pd.concat([nz.abs(), alt_bt.shift(L).abs()], axis=1).dropna().corr().iloc[0, 1]) for L in (-1, 0, 1)}
    say("  date alignment check, corr(|sleeve book on day d|, |alt index on day d-L|) on the sleeve's active days: "
        + "  ".join(f"L {L:+d} {c:+.3f}" for L, c in cors.items())
        + ("  -> same-day is the largest: the books are dated by the bar they earn on" if max(cors, key=cors.get) == 0
           else "  ** NOT same-day: dates may be shifted **"))
    eqs = {aid: live_equity_by_day(folder, acct, aid) for acct, aid in (("combo_bot_dry_final", "main"),
                                                                         ("combo_bot_dry_final_fresh", "fresh"))}
    for ph, P in PHASES.items():
        eq = eqs[P["aid"]]
        first, last = pd.Timestamp(P["first"]), pd.Timestamp(P["last"])
        n = (last - first).days + 1
        e0 = P["e0_live"] if P["e0_live"] is not None else float(eq.get(first - pd.Timedelta(days=1)))
        e1 = float(eq.get(last)) + P.get("add", 0.0)
        live = e1 / e0 - 1
        part = PA[(PA.index >= first) & (PA.index <= last)]
        alt_live = float((1 + part.ret).prod() - 1)
        btc_live = float(btc[last] / btc[first - pd.Timedelta(days=1)] - 1)
        R = windows(frames, n, alt_bt, btc_bt)
        say("")
        say(f"  PHASE {ph} = {P['name']}, bars {first:%m-%d}..{last:%m-%d} ({n} days): {P['aid']} ${e0:.2f} -> ${e1:.2f} = {live:+.1%} "
            f"(live equity, dashboard curve{'; the crowd book loss added back' if P.get('add') else ''}); BTC {btc_live:+.1%}, alt index "
            f"{alt_live:+.1%}, median alt 30d at the end {part.alt30.iloc[-1]:+.1%}")
        say(f"    how unusual the MARKET was: BTC's move is the {pctl(R.btc, btc_live):.0f}th percentile and the alt index's the "
            f"{pctl(R.alt, alt_live):.0f}th of all {n}-day windows 2020-26; the machine over ALL windows: median "
            f"{R.machine.median():+.1%}, live at the {pctl(R.machine, live):.1f}th percentile")
        for (tb, ta), tag in zip(TOL, ("primary", "wider")):
            Mt = R[(R.btc - btc_live).abs().le(tb) & (R.alt - alt_live).abs().le(ta)]
            if not len(Mt):
                say(f"    {tag}: no backtest window within BTC +-{tb:.0%} and alts +-{ta:.0%}")
                continue
            starts = (Mt.index - pd.Timedelta(days=n - 1)).strftime("%Y-%m")
            mo = sorted(set(starts))
            pc = pctl(Mt.machine, live)
            res[f"{ph}_{tag}"] = (pc, float(Mt.machine.median()), float(Mt.machine.quantile(0.1)))
            say(f"    {tag} match (BTC +-{tb:.0%}, alts +-{ta:.0%}): {len(Mt)} windows ({len(Mt) / 10:.0f} a slot ordering), "
                f"{len(mo)} start months; machine median {Mt.machine.median():+.1%}, 10th {Mt.machine.quantile(0.1):+.1%}, "
                f"worst {Mt.machine.min():+.1%}, best {Mt.machine.max():+.1%}; share of windows that lost {(Mt.machine < 0).mean():.0%}; "
                f"LIVE {live:+.1%} = {pc:.1f}th percentile")
            if tag == "primary":
                say(f"      start months: {' '.join(mo)}")
                say(f"      by book (% of the starting account; live = feed {P['feed']}, ${P['e0_feed']:.2f} at its start):")
                say(f"      {'book':<10}{'live':>9}{'bt 10th':>10}{'bt median':>11}{'bt 90th':>10}{'live pctile':>13}")
                for b in MACH:
                    lv = P["books"][b] / P["e0_feed"]
                    p_ = pctl(Mt[b], lv)
                    res[f"{ph}_{b}"] = p_
                    say(f"      {b:<10}{lv:>+8.1%}{Mt[b].quantile(0.1):>+10.1%}{Mt[b].median():>+11.1%}{Mt[b].quantile(0.9):>+10.1%}"
                        f"{p_:>12.0f}th")
                for mo_ in mo:
                    sub = Mt[starts == mo_]
                    say(f"        {mo_}: {len(sub):>3} windows  machine median {sub.machine.median():+6.1%}  btc {sub.btc.median():+6.1%} "
                        f"alts {sub.alt.median():+6.1%}  trend {sub.trend.median():+5.1%}  mn {sub.mn_blend.median():+5.1%}  "
                        f"daily {sub.daily.median():+5.1%}  sleeve {sub.sleeve.median():+5.1%}")
        res[f"{ph}_live"] = live


# ------------------------------------------------------------------ D: capit2's rule replayed on the live weeks
def capit2_replay(K: dict, since: str = "2026-10-09") -> tuple:
    """capit2's signal exactly as the bot computes it (final_books.capit_signals on the last 150 closed 4h bars of each coin,
    as final_books.bars4h serves them) on the point-in-time top-40 of each bar's month, every closed 4h bar since `since`;
    the limit (2% under the signal close, live for the next bar only, taken once a low trades 0.3% through) and the exits on
    4h bars as capit2_poll runs them (+5% target from bars opening after the fill, out at a close 24+ bars after the signal
    that is not above the entry, 43-bar cap), 12bp round trip, funding not charged. Also counts what each condition let through."""
    import final_books as fb
    from backtest.daily_live_vs_backtest import FAPI, get, month_top
    t0 = int(pd.Timestamp(since).timestamp() * 1000)
    uni = {m: month_top(K, m, 40) for m in ("2026-10", "2026-11")}
    B = {}
    for s in sorted(set(uni["2026-10"]) | set(uni["2026-11"])):
        k = get(f"{FAPI}/fapi/v1/klines?symbol={s}&interval=4h&limit=500") or []
        if k:
            d = pd.DataFrame([[int(x[0]), float(x[1]), float(x[2]), float(x[3]), float(x[4]), float(x[7])] for x in k],
                             columns=["t", "o", "h", "l", "c", "q"])
            B[s] = d[d.t + fb.H4 <= pd.Timestamp.now(tz="UTC").value // 10**6].reset_index(drop=True)
    last = max(int(d.t.iloc[-1]) for d in B.values())
    sig_rows, waves, coin_hits, big_drops = [], 0, 0, 0
    for t in range(t0, last + 1, fb.H4):
        mon = f"{pd.Timestamp(t, unit='ms'):%Y-%m}"
        d4 = {}
        for s in uni.get(mon, []):
            d = B.get(s)
            if d is None:
                continue
            d = d[d.t <= t].tail(150)
            if len(d) and int(d.t.iloc[-1]) == t:
                d4[s] = d.reset_index(drop=True)
        sig, breadth = fb.capit_signals(d4, t)
        hits_now = [s for s, d in d4.items() if t in fb.capit_hits(d)]
        coin_hits += len(hits_now)
        for s in hits_now:
            c = d4[s].c.to_numpy(float)
            big_drops += int(len(c) > 6 and c[-1] / c[-7] - 1 <= -fb.DROP)
        waves += int(len(breadth) >= fb.BREADTH)
        for s, (c, dr) in sig.items():
            sig_rows.append(dict(t=pd.Timestamp(t, unit="ms"), coin=s, close=c, drop=dr, breadth=len(breadth)))
    trades = []
    for r in sig_rows:
        d = B[r["coin"]]
        i = int(np.flatnonzero(d.t.to_numpy() == int(r["t"].value // 10**6))[0])
        lim = r["close"] * (1 - fb.LIMIT)
        row = dict(r, lim=lim, filled=False, exit=np.nan, why="", ret=np.nan)
        if i + 1 < len(d) and d.l.iloc[i + 1] <= lim * (1 - fb.THROUGH):
            row["filled"] = True
            for k in range(1, len(d) - i):
                j = i + k
                if k >= 2 and d.h.iloc[j] >= lim * (1 + fb.TARGET):
                    row.update(exit=lim * (1 + fb.TARGET), why="target")
                    break
                if k >= fb.NW_BARS and d.c.iloc[j] <= lim:
                    row.update(exit=d.c.iloc[j], why="not_working")
                    break
                if k >= fb.CAP_BARS:
                    row.update(exit=d.c.iloc[j], why="cap")
                    break
            if np.isfinite(row["exit"]):
                row["ret"] = row["exit"] / lim - 1 - 0.0012
            else:
                row.update(exit=d.c.iloc[-1], why="open", ret=d.c.iloc[-1] / lim - 1 - 0.0012)
        trades.append(row)
    n_bars = (last - t0) // fb.H4 + 1
    return pd.DataFrame(trades), dict(bars=n_bars, waves=waves, coin_hits=coin_hits, big_drops=big_drops, last=last)


def backtest_capit2_counts(n: int, btc_live: float, alt_live: float) -> pd.Series:
    """How many capit2 trades the backtest machine closed in n-day windows matched to the live market move (the same
    match as C2): days with a non-zero capit2 return per window, mean over the slot orderings (a proxy for trades)."""
    alt_bt, btc_bt = backtest_alts()
    frames = machine_frames()
    out = []
    for x in frames:
        nzd = (x["capit2"].abs() > 1e-12).astype(float).rolling(n, min_periods=n).sum()
        R = windows([x], n, alt_bt, btc_bt)
        Mt = R[(R.btc - btc_live).abs().le(TOL[0][0]) & (R.alt - alt_live).abs().le(TOL[0][1])]
        out.append(nzd.reindex(Mt.index))
    return pd.concat(out)


def part_d(K: dict, folder: Path, res: dict):
    say("")
    say("=== D capit2 - the book the backtest leans on in crashes - its rule replayed on the live weeks with the bot's own code "
        "(final_books.capit_signals on Binance 4h bars of the point-in-time top-40)")
    T, info = capit2_replay(K)
    live = pd.read_csv(folder / "combo_bot_dry_final" / "combo_final_trades.csv")
    live = live[live.book == "capit2"]
    say(f"  {info['bars']} closed 4h bars from 10-09 to {pd.Timestamp(info['last'], unit='ms'):%m-%d %H:%M}: a coin's RSI crossed "
        f"under 20 on > 2x volume {info['coin_hits']} times; {info['big_drops']} of those with the coin down >= 10% over 24h; "
        f"bars inside a wave (>= 5 of the 40 within 24h): {info['waves']}; SIGNALS (all three together): {len(T)}")
    for r in T.itertuples():
        say(f"   {r.t:%m-%d %H:%M} {r.coin:<12} drop {r.drop:+.0%} breadth {r.breadth:>2}  limit {r.lim:.6g}  "
            + (f"filled -> {r.why} {r.ret:+.1%}" if r.filled else "not filled"))
    say(f"  the live bot (main, combo_final_trades.csv): {len(live)} capit2 trades - " + "  ".join(
        f"{r.symbol} entry {r.entry:.6g} -> {r.why} {r.ret:+.1%}" for r in live.itertuples()))
    filled = T[T.filled]
    res["D"] = (len(T), len(filled), len(live))
    say(f"  replay: {len(T)} signals, {len(filled)} filled, mean {filled.ret.mean():+.1%} a trade" if len(filled) else
        f"  replay: {len(T)} signals, none filled")
    # HOW THE DECLINE CAME (descriptive, added after D's first run): flush days in the live 42 days vs the matched windows
    alt_bt, btc_bt = backtest_alts()
    R = windows(machine_frames()[:1], 42, alt_bt, btc_bt)                 # the market columns are the same in every ordering
    Mt = R[(R.btc + 0.242).abs().le(TOL[0][0]) & (R.alt + 0.287).abs().le(TOL[0][1])]
    worst = alt_bt.rolling(42, min_periods=42).min().reindex(Mt.index)
    n5 = (alt_bt <= -0.05).astype(float).rolling(42, min_periods=42).sum().reindex(Mt.index)
    PAl = res["PA"].ret[(res["PA"].index >= "2026-10-09") & (res["PA"].index <= "2026-11-19")]
    say(f"  how the decline came (post hoc): live 42 days - worst alt-index day {PAl.min():+.1%}, days of -5% or worse "
        f"{int((PAl <= -0.05).sum())}; the {len(Mt)} matched backtest windows - worst day median {worst.median():+.1%} (live at the "
        f"{pctl(worst, PAl.min()):.0f}th percentile, i.e. milder than most), days of -5% or worse median {n5.median():.0f} "
        f"(10th {n5.quantile(0.1):.0f}, 90th {n5.quantile(0.9):.0f})")
    cnt = backtest_capit2_counts(42, -0.242, -0.287)
    res["D2"] = float(cnt.median())
    say(f"  the backtest machine in the 42-day windows matched to main's whole record (C2's AB match): capit2 closed trades on a "
        f"median {cnt.median():.0f} days a window (10th {cnt.quantile(0.1):.0f}, 90th {cnt.quantile(0.9):.0f}); live: "
        f"{live.ts.str[:10].nunique()} days")


def main():
    folder = Path(sys.argv[1]) if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else ROOT / "logs"
    parts = sys.argv[sys.argv.index("--parts") + 1] if "--parts" in sys.argv else "ABCD"
    from backtest.daily_live_vs_backtest import klines_all
    D = klines_all()
    C = closes(D["K"])
    TF = tradfi_closes()
    C = C.join(TF, how="left")
    for s in TF.columns:
        C[s] = C[s].ffill()                       # a TradFi perp may not print a bar every calendar day
    say(f"backtest/crash_lessons.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; parts {parts}; live logs from {folder.name}; "
        f"Binance daily closes to {C.index[-1]:%Y-%m-%d} (the bar opened that day); TradFi closes: "
        f"{', '.join(TF.columns) if len(TF.columns) else 'NONE - QQQ is missing from A1'}")
    PA = pit_alts(D["K"], C, "2026-09-25")
    alt_ret = PA["ret"]
    res: dict = {"PA": PA}
    btc_ret = C["BTCUSDT"].pct_change(fill_method=None)
    qqq_ret = C["QQQUSDT"].pct_change(fill_method=None) if "QQQUSDT" in C else pd.Series(dtype=float)
    say(f"alt index = equal-weight daily return of the point-in-time top-40 (each day's month, BTC out, {int(PA.n.median())} coins); "
        f"bars 10-09..{C.index[-1]:%m-%d}: alts {float((1 + alt_ret[alt_ret.index >= '2026-10-09']).prod() - 1):+.1%}, "
        f"BTC {C['BTCUSDT'].iloc[-1] / C.at[pd.Timestamp('2026-10-08'), 'BTCUSDT'] - 1:+.1%}; the median alt's 30 days at the "
        f"last close {PA.alt30.iloc[-1]:+.1%}")

    if "A" in parts:
        for acct, aid in (("combo_bot_dry_final", "main"), ("combo_bot_dry_final_fresh", "fresh")):
            eq = live_equity_by_day(folder, acct, aid)
            ex = ledger_exposure(folder, acct, C, eq)
            say("")
            um = unmapped(folder, acct, C.columns)
            say(f"=== A1 {aid.upper()}: what the netted account held (placeable ledger, x live equity; the replay equals the bot's own "
                f"exec.virtual_pos coin for coin; unpriced: {um or 'none'})")
            pre, cr = ex[ex.index < CRASH0], ex[ex.index >= CRASH0]
            for nm, part in (("before 11-10", pre), ("11-10 .. now", cr)):
                say(f"  {nm:<14} crypto long {part.long.mean():5.0f}$  short {part.short.mean():5.0f}$  net {part.net_x.mean():+.2f}x  "
                    f"gross {part.gross_x.mean():.2f}x  | QQQ {part.tradfi_x.mean():+.2f}x  (days {len(part)})")
                res[f"{aid}_net_{'pre' if nm.startswith('b') else 'crash'}"] = float(part.net_x.mean())
            say("  crypto net by day in the crash: " + "  ".join(f"{d:%m-%d} {r.net_x:+.2f}x" for d, r in cr.iterrows()))
            r = eq[eq.index >= pd.Timestamp("2026-10-17")].pct_change().dropna()      # the live (booked + open) curve only
            df = pd.DataFrame({"acct": r, "alt": alt_ret.reindex(r.index), "btc": btc_ret.reindex(r.index),
                               "qqq": qqq_ret.reindex(r.index)}).dropna(subset=["acct", "alt", "btc"])
            say(f"=== A2 {aid.upper()}: daily live-equity return vs the alt index, BTC and QQQ (OLS slope, one factor at a time)")
            for nm, part in (("before 11-10", df[df.index < CRASH0]), ("11-10 .. now", df[df.index >= CRASH0]), ("all", df)):
                if len(part) < 5:
                    continue
                ba = np.polyfit(part.alt, part.acct, 1)[0]
                bb = np.polyfit(part.btc, part.acct, 1)[0]
                qq = part.dropna(subset=["qqq"])
                bq = np.polyfit(qq.qqq, qq.acct, 1)[0] if len(qq) >= 5 and qq.qqq.std() > 0 else np.nan
                ca = np.corrcoef(part.alt, part.acct)[0, 1]
                res[f"{aid}_beta_{nm[:3]}"] = float(ba)
                say(f"  {nm:<14} n {len(part):>2}  beta to alts {ba:+.2f} (corr {ca:+.2f})  to BTC {bb:+.2f}  to QQQ {bq:+.2f}  "
                    f"account {float((1 + part.acct).prod() - 1):+.1%}  alts {float((1 + part.alt).prod() - 1):+.1%}  "
                    f"BTC {float((1 + part.btc).prod() - 1):+.1%}")
            worst = df.nsmallest(5, "alt")
            say("  the 5 worst alt days: " + "  ".join(f"{d:%m-%d} alts {w.alt:+.1%} acct {w.acct:+.1%}" for d, w in worst.iterrows()))

        say("")
        say("=== A3 the live market-neutral book, leg by leg (fixed coins, equal weight per leg, +50% short exit at its level)")
        live_crash = crash_days(C["BTCUSDT"].dropna())
        LG = {}
        for acct, aid in (("combo_bot_dry_final", "main"), ("combo_bot_dry_final_fresh", "fresh")):
            lg = live_mn_legs(folder, acct, C)
            lg["crash"] = [bool(live_crash.get(t, False)) for t in lg.t0]
            LG[aid] = lg
            say(f"  {aid}: basket   to      long leg   short leg   net (0.5L - 0.5S)   longs' 30d run-up   shorts' 30d   crash week")
            for _, w in lg.iterrows():
                say(f"   {w.day} -> {w.to}   {w.long:+8.1%}   {w.short:+8.1%}      {w.net:+8.1%}            {w.long_pump:+8.0%}"
                    f"         {w.short_pump:+6.0%}       {'yes' if w.crash else ''}")
            late = lg[lg.day >= "2026-10-30"]
            k = int(((0.5 * late.long) < (0.5 * late.short)).sum())
            res[f"{aid}_L3"] = (k, len(late), float(late.long_pump.median()))
            say(f"   from the 10-30/10-31 basket on (closed weeks only): the long names fell more than the short names in {k} of "
                f"{len(late)} weeks; their longs' median run-up {late.long_pump.median():+.0%} (all baskets {lg.long_pump.median():+.0%})")
        res["LG"] = LG

    if "B" in parts:
        say("")
        say("=== B1 the backtest market-neutral blend (7 rebalance weekdays): the long names' and the short names' average weekly price "
            "return (the book gains when the SHORT names fall), crash weeks vs all weeks")
        W, Dd = backtest_mn_legs()
        btc_bt = pd.Series(Dd["X"][:, list(Dd["cols"]).index("BTCUSDT")], index=Dd["idx"])
        cd = crash_days(btc_bt)
        W["crash"] = cd.reindex(W.index).fillna(False).to_numpy(bool)
        from backtest.pair_lab import HOLDOUT
        say(f"  parity: the copied run() reproduces moderate_retests.scored_run exactly; split {HOLDOUT:%Y-%m-%d}")
        for nm, part in (("all weeks", W), ("crash weeks", W[W.crash]), ("crash, tune", W[W.crash & (W.index < HOLDOUT)]),
                         ("crash, holdout", W[W.crash & (W.index >= HOLDOUT)]), ("non-crash", W[~W.crash])):
            say(f"  {nm:<16} n {len(part):>4}  long names {part.long.mean() * 2:+7.2%}/wk  short names {-part.short.mean() * 2:+7.2%}/wk  "
                f"net {part.net.mean():+6.2%}/wk  ({(part.net < 0).mean():.0%} negative)  longs' 30d run-up median "
                f"{part.pump.median():+.0%}")
        cw = W[W.crash]
        res["B1_crash"] = (float(cw.long.mean() * 2), float(-cw.short.mean() * 2), float(cw.net.mean()), float(cw.pump.median()))
        say(f"  crash-week net, quantiles: 5th {cw.net.quantile(0.05):+.2%}  10th {cw.net.quantile(0.10):+.2%}  25th "
            f"{cw.net.quantile(0.25):+.2%}  median {cw.net.median():+.2%}  75th {cw.net.quantile(0.75):+.2%}")
        if "LG" in res:
            for aid, lg in res["LG"].items():
                for _, w in lg[lg.crash].iterrows():
                    say(f"    live {aid} {w.day}: net {w.net:+.2%} = {pctl(cw.net, w.net):.0f}th percentile of backtest crash weeks "
                        f"(longs {w.long:+.1%}: {pctl(cw.long * 2, w.long):.0f}th; shorts {w.short:+.1%}: "
                        f"{pctl(-cw.short * 2, w.short):.0f}th)")
        mon = sorted({f"{t:%Y-%m}" for t in cw.index})
        say(f"  crash weeks fall in {len(mon)} months: {' '.join(mon)}")
        hi = W[W.crash & (W.pump >= cw.pump.quantile(0.75))]
        say(f"  crash weeks whose longs had run up the MOST (top quarter, run-up >= {cw.pump.quantile(0.75):+.0%}): n {len(hi)} "
            f"long names {hi.long.mean() * 2:+.2%}/wk  short names {-hi.short.mean() * 2:+.2%}/wk  net {hi.net.mean():+.2%}/wk")
        allhi = W[W.pump >= W.pump.quantile(0.9)]
        say(f"  ALL weeks whose longs had run up the most (top 10%, >= {W.pump.quantile(0.9):+.0%}): n {len(allhi)} net "
            f"{allhi.net.mean():+.2%}/wk (tune {allhi[allhi.index < HOLDOUT].net.mean():+.2%}, holdout "
            f"{allhi[allhi.index >= HOLDOUT].net.mean():+.2%}) vs the rest {W[W.pump < W.pump.quantile(0.9)].net.mean():+.2%}/wk")

        say("")
        say("=== B2 the bear sleeve after the label turns BEAR (backtest, top-10 basket, whole-account returns)")
        S, Cp = backtest_sleeve_after_flip()
        for n in (5, 7, 14):
            part = S[S.days == n]
            low = part[part.breadth <= 0.10]
            res[f"B2_{n}"] = (float((part.sleeve < 0).mean()), float(part.sleeve.mean()), float((low.sleeve < 0).mean()))
            say(f"  first {n:>2} days: {len(part)} flips, sleeve mean {part.sleeve.mean():+.1%} median {part.sleeve.median():+.1%}, "
                f"lost money in {(part.sleeve < 0).mean():.0%}; flips with breadth already <= 10%: {len(low)}, sleeve mean "
                f"{low.sleeve.mean():+.1%}, lost in {(low.sleeve < 0).mean():.0%}; the basket itself mean {part.basket.mean():+.1%}")
        say("  each flip (14 days): " + "  ".join(f"{r.flip:%Y-%m-%d} br {r.breadth:.2f} sleeve {r.sleeve:+.1%} basket {r.basket:+.1%}"
                                                 for r in S[S.days == 14].itertuples()))
        low5 = S[(S.days == 5) & (S.breadth <= 0.10)]
        say("  low-breadth flips, first 5 days (the live sleeve's age at the feed): " + "  ".join(
            f"{r.flip:%Y-%m-%d} {r.sleeve:+.1%}" for r in low5.itertuples()))
        mk = pd.read_csv(folder / "combo_bot_dry_final" / "combo_marks.csv", index_col=0, parse_dates=True)
        sl = mk[mk.regime == "bear"]
        if len(sl):
            e_flip = float(mk.equity[mk.index < sl.index[0]].iloc[-1])
            say(f"  LIVE main sleeve since its flip ({sl.index[0]:%Y-%m-%d}): booked marks " + "  ".join(
                f"{d:%m-%d} {v:+.2f}" for d, v in sl.sleeve.items()) + f"  (cumulative $, equity ${e_flip:.2f} the day before); "
                f"with the open part at the 11-20 21:00 feed: -$14.88 = {-14.88 / e_flip:+.1%} of that equity in 5 days "
                f"= the {pctl(S[S.days == 5].sleeve, -14.88 / e_flip):.0f}th percentile of backtest flips' first 5 days")

    if "C" in parts:
        part_c(folder, C, PA, res)

    if "D" in parts:
        part_d(D["K"], folder, res)

    # ---------------- the registered predictions, scored
    say("")
    say("=== PREDICTIONS (registered in the docstring; L1-L6 before any number, L7-L10 after A and B, before C)")
    if "A" in parts:
        say(f"  L1 main net LONG >= +0.5x in the crash: crypto net {res['main_net_crash']:+.2f}x -> "
            f"{'RIGHT' if res['main_net_crash'] >= 0.5 else 'WRONG'} (QQQ held apart, above)")
        b_pre, b_cr = res.get("main_beta_bef", np.nan), res.get("main_beta_11-", np.nan)
        say(f"  L2 beta to alts >= +0.3 in the crash and lower before: {b_cr:+.2f} in the crash, {b_pre:+.2f} before -> "
            f"{'RIGHT' if b_cr >= 0.3 and b_pre < b_cr else 'WRONG'}")
        k, nw, pump = res["main_L3"]
        say(f"  L3 long names fell more in >= 3 of 4 weeks from 10-30, longs' run-up >= +30%: {k} of {nw}, run-up {pump:+.0%} -> "
            f"{'RIGHT' if k >= 3 and pump >= 0.30 else 'WRONG'}")
    if "B" in parts:
        lw, sw, nt, pp = res["B1_crash"]
        say(f"  L4 backtest crash weeks: long names fall AND the book nets >= 0: long names {lw:+.2%}/wk, net {nt:+.2%}/wk -> "
            f"{'RIGHT' if lw < 0 and nt >= 0 else 'WRONG'} (the short names {sw:+.2%}/wk)")
        if "A" in parts:
            live_pump = float(pd.concat([res['LG'][a].long_pump for a in res['LG']]).median())
            say(f"  L5 backtest crash weeks' longs ran up LESS than live's: {pp:+.0%} vs live {live_pump:+.0%} (all live baskets) -> "
                f"{'RIGHT' if pp < live_pump else 'WRONG'}")
        lost14 = res["B2_14"][0]
        say(f"  L6 sleeve's first 14 days lose in > half of flips: {lost14:.0%} -> {'RIGHT' if lost14 > 0.5 else 'WRONG'}")
    if "C" in parts:
        pa = res.get("A_primary")
        pb = res.get("B_primary")
        if pa:
            say(f"  L7 phase A under the matched 10th percentile: {pa[0]:.1f}th -> {'RIGHT' if pa[0] < 10 else 'WRONG'}")
        if pb:
            say(f"  L8 phase B under the matched median: {pb[0]:.1f}th -> {'RIGHT' if pb[0] < 50 else 'WRONG'}; under the 10th: "
                f"{'RIGHT' if pb[0] < 10 else 'WRONG'}")
        if pa:
            mn_, dl_, tr_ = res["A_mn_blend"], res["A_daily"], res["A_trend"]
            say(f"  L9 phase A: MN {mn_:.0f}th, daily {dl_:.0f}th under the 10th, trend {tr_:.0f}th not -> "
                f"{'RIGHT' if mn_ < 10 and dl_ < 10 and tr_ >= 10 else 'WRONG'}")
        say(f"  L10 phase A fuel LOW with BTC bull / chop on >= 60% of days: {res['L10']:.0%} -> "
            f"{'RIGHT' if res['L10'] >= 0.6 else 'WRONG'}")
    if "D" in parts and "D" in res:
        n_sig, n_fill, n_live = res["D"]
        say(f"  D1 the replay finds the live bot's signals and no more: replay {n_sig} signals ({n_fill} filled) vs live {n_live} -> "
            f"{'RIGHT' if n_sig == n_live else 'WRONG'}")
        if "D2" in res:
            say(f"  D2 backtest capit2 closed trades on >= 5 days in the median matched window: {res['D2']:.0f} -> "
                f"{'RIGHT' if res['D2'] >= 5 else 'WRONG'}")
    if parts == "ABCD":
        LOG.write_text("\n".join(OUT) + "\n", encoding="utf-8")
    else:
        (ROOT / "logs" / f"crash_lessons_{parts}.txt").write_text("\n".join(OUT) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
