"""THE FINAL MACHINE'S EXTRA BOOKS - what `combo_bot.py --final` adds to the running combination (2026-10-09).

The running bot (machine v2: trend triple + market-neutral + bear sleeve + crash bids) plus everything that passed the
2026-10-08/09 tests, on ONE account, netted per coin by combo_bot's execution:
    MN BLEND   the market-neutral book ranked HALF by 30-day momentum (as before), HALF by daily RSI(14) - two baskets of
               0.5x each, summed per coin (backtest/mn_blend_rsi.py, moderate_retests.scored_run). The +50% short-leg
               exit (combo_bot.mn_squeeze_exits) applies to the blend as it did to the plain book.
    CARRY      funding carry at 0.5x: every 7 days, of the same PIT top-60, long the 20% with the LOWEST 7-day funding
               sum and short the 20% with the highest; the same +50% short-leg exit (kill_sweeps.py --carry,
               kill_followups.py: as an overlay it lifts the MN blend on both halves, correlation -0.01).
    DAILY      Bollinger(30, 1.5) on daily closes of the PIT top-40 -> buy at the next open; out at the next open after a
               close under the 20-DAY mean (family_machine.py: +8% / +13% over the 30-day exit inside the machine), or
               after 31 days. 8 slots of half the account (machine_combos.parts: "daily" = 0.5 x the 8-slot book).
    CAPIT2     the improved capitulation buy: a 4h close where RSI(14) crosses under 20 on > 2x its 20-bar quote volume,
               once >= 5 of the top-40 have done so within 24h, on a coin down >= 10% over those 24h -> a buy 2% under
               the signal close, live for the next 4h bar only and taken only once the price trades 0.3% THROUGH it
               (filled AT the limit from 1-minute lows since 2026-10-22: a resting order, as backtested - capit2_poll);
               +5% target, out once a close 24+ bars after the signal is not above the entry, 43-bar cap. 8 slots of
               the WHOLE account at 2x since 2026-10-16 (was half at 1x): backtest/capit2_lev.py (+20.0 / +29.9 %/yr
               tune / holdout vs +8.6 / +14.3 at 1x, fall 10 -> 12%) and final_capit2_lev.py (the machine's typical
               year $3,400 / $4,735 -> $4,098 / $5,494 on $300, worst month -30% unchanged). A position is closed at
               -49.4% ("liquidation_eq"), the loss the backtest booked as an isolated 2x liquidation.
    GROSS CAP  the WHOLE account is held under 10x gross: an order that would take it past is not sent. The trend
               book's own guard drops 9x -> 6.25x, because the other books could hold 3.75x at their peaks (MN 1 +
               carry 0.5 + sleeve 1 + bids 0.25 + daily 0.5 + capit2 0.5). Since capit2 went to 1.0 x 2x their peak is
               5.25x; the trend guard stays 6.25x as backtested (final_capit2_lev.py) and the account gate is RAISED to
               11.5x - the summed peaks - at the user's word (2026-10-16), so it refuses nothing the backtest took.
               Past ~10x an ~8% move against everything closes a real cross-margin account (CLAUDE.md s7): this is a
               paper setting. The backtest let the trend book reach 9x ON
               TOP of the overlays; backtest/final_machine.py's DEPLOYABLE line is this file's configuration.

WHAT THE BACKTEST SAYS (backtest/final_machine.py, logs/final_machine.txt; $300; trend gains shrunk for hindsight,
everything else raw; 10 orderings; BACKTEST ONLY):
    DEPLOYABLE, full size   typical year $3,400 (6 yrs) / $4,735 (last 2); median month +4.6% / +7.3%; ~4 in 10
                            months lose; worst month -30%; biggest fall 60% / 51%
    DEPLOYABLE x0.65        $1,806 / $2,297; median month +3.4% / +5.2%; worst month -20.4%; fall 44% / 36%
The trend book is a bull-market amplifier; the daily book was chosen after looking at the holdout and makes under half
on it what it makes on the tune half; the MN blend, the carry book and the 20-day exit are found in the ~10th sweep of a
mined holdout. Forward paper decides - this file is how it runs forward.

LIVE vs BACKTEST, stated so it can be subtracted later
    1. capit2's entry is a LIMIT in the backtest (filled at the limit whenever the bar traded 0.3% through it). Here the
       bot works in market orders: each 2-minute poll, if the live price is at or under limit x 0.997 the book buys at
       that price. Fewer fills (a dip between polls is missed), each slightly better. Its target is taken whenever the
       live price is at +5% - also inside the fill bar, which the backtest excluded only because bar data cannot order
       events; a target crossed between polls is taken at the next poll's price ("target_late").
    2. Same-day signals beyond the free slots are taken in volume order, not random order.
    3. Daily and capit2 positions are booked when they close (as the trend book is); MN and carry are marked daily.
    4. Funding is charged on every book: daily/capit2 at exit over (entry, exit], carry at each daily mark over
       (last mark, this mark] - half-open and bounded at both ends (mistake #15).
"""
from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd

import mn_paper as mp

K_CARRY, K_DAILY, K_CAPIT2 = 0.5, 0.5, 1.0
CAPIT2_LEV = 2.0                  # 2026-10-16 (backtest/capit2_lev.py, final_capit2_lev.py): full share at 2x, user's OK
LIQ_EQ = 1 / CAPIT2_LEV - 0.0056  # the backtest's isolated liquidation: a capit2 position is closed at this loss
SLOTS, TOP_N = 8, 40
TREND_LEV = 6.25                  # 10 - the other books' 3.75x at their peaks (see the docstring)
GROSS_CAP = 14.5                  # the books' summed peaks: trend 6.25 + MN 1 + carry 0.5 + sleeve 1 + bids 0.25 + daily
                                  # 0.5 + capit2 2 (= 11.5, 2026-10-16, the user: "we can exceed the account cap") + news
                                  # 2 (10 trades x 2 legs x 1/10) + ndx 1 (2026-10-17, news_books.py). DRY / paper only;
                                  # reconsider before any real money (CLAUDE.md s7: ~10x is where an 8% move closes it)
EQUITY = 300.0                    # the paper account (dry / demo); final_machine.py's figures are on $300
CARRY_FRAC, CARRY_WIN_D = 0.20, 7
BB_N, BB_K, MEAN_N, CAP_D = 30, 1.5, 20, 31
LATE_MS = 3 * 3_600_000          # a daily-book BUY only within 3h of the close it was read on (see daily_books)
RSI_UNDER, VOL_X, BREADTH, DROP = 20.0, 2.0, 5, 0.10
LIMIT, THROUGH, TARGET, NW_BARS, CAP_BARS = 0.02, 0.003, 0.05, 24, 43
SIDE_FEE = 6.0 / 1e4
H4, DAY_MS = 14_400_000, 86_400_000
FAPI = mp.FAPI

MOM_TARGET = mp.target            # mn_paper's own momentum basket, captured BEFORE enable() replaces mp.target
_FETCH_ALL, _UNIVERSE = mp.fetch_all, mp.perp_universe
LAST: dict = {}                   # the last daily bars / universe combo_paper.daily fetched (see enable)


def log(m: str):
    import combo_paper as cp
    cp.log(m)


def fresh() -> dict:
    return dict(last_day=None, last_fund_ms=None, last_4h=None, uni40=[],
                carry=dict(weights={}, mark_px={}, base=0.0, last_rebal=None, n_rebal=0, skipped_small=0),
                daily=dict(open={}, taken=0), capit2=dict(open={}, pending={}, placed=0, filled=0, cancelled=0))


# ---------------------------------------------------------------- pure rules (tested offline)

def rsi(c: np.ndarray, n: int = 14) -> np.ndarray:
    """Wilder RSI on closes; 100 where there has been no down move."""
    d = np.r_[0.0, np.diff(np.asarray(c, float))]
    up = pd.Series(np.where(d > 0, d, 0.0)).ewm(alpha=1 / n, adjust=False).mean().to_numpy()
    dn = pd.Series(np.where(d < 0, -d, 0.0)).ewm(alpha=1 / n, adjust=False).mean().to_numpy()
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(dn > 0, 100 - 100 / (1 + up / dn), 100.0)


def ranked(score: dict, frac: float) -> dict:
    """Long the top `frac` by score, short the bottom; +-0.5/k each (gross 1.0). Needs 20 names, as mn_paper.target."""
    if len(score) < 20:
        return {}
    order = sorted(score, key=lambda s: (score[s], s))
    k = max(int(len(order) * frac), 3)
    w = {s: +0.5 / k for s in order[-k:]}
    w.update({s: -0.5 / k for s in order[:k]})
    return w


def rsi_target(bars: dict, elig: list) -> dict:
    """The RSI half of the MN blend: the same names mn_paper.target can rank (a close LOOK_D days ago), ranked by
    daily RSI(14) - high RSI long, low RSI short (moderate_retests.scored_run with the RSI matrix)."""
    sc = {}
    for s in elig:
        d = bars.get(s)
        if d is None or len(d) <= mp.LOOK_D:
            continue
        c = d.close.to_numpy(float)
        if c[-1 - mp.LOOK_D] > 0 and c[-1] > 0:
            sc[s] = float(rsi(c)[-1])
    return ranked(sc, mp.FRAC)


def mn_blend_target(bars: dict, elig: list) -> dict:
    """Half momentum, half RSI, summed per coin. Gross <= 1.0 (a coin in both baskets on the same side counts twice;
    on opposite sides it nets to zero and is dropped)."""
    m, r = MOM_TARGET(bars, elig), rsi_target(bars, elig)
    if not m or not r:
        return {}
    w = {s: 0.5 * m.get(s, 0.0) + 0.5 * r.get(s, 0.0) for s in set(m) | set(r)}
    return {s: x for s, x in w.items() if abs(x) > 1e-12}


def carry_target(f7: dict) -> dict:
    """Long the CARRY_FRAC with the LOWEST 7-day funding sum (shorts pay them), short the highest."""
    return ranked({s: -f for s, f in f7.items() if np.isfinite(f)}, CARRY_FRAC)


def daily_entry(c: np.ndarray) -> bool:
    """A close above Bollinger(30, 1.5), on a coin with 60 days of history (daily_combos.gen skips i < 60)."""
    if len(c) < 61:
        return False
    w = c[-BB_N:]
    return bool(c[-1] > w.mean() + BB_K * w.std(ddof=0))


def daily_exit(c: np.ndarray) -> bool:
    return len(c) >= MEAN_N and bool(c[-1] < c[-MEAN_N:].mean())


def capit_hits(d: pd.DataFrame) -> list:
    """Bar times (ms) where RSI(14) crossed under RSI_UNDER on quote volume > VOL_X x its prior 20-bar average."""
    if len(d) < 60:
        return []
    c, q = d.c.to_numpy(float), d.q.to_numpy(float)
    r = rsi(c)
    qa = pd.Series(q).rolling(20).mean().shift(1).to_numpy()
    with np.errstate(invalid="ignore"):
        hit = np.r_[False, (r[:-1] >= RSI_UNDER) & (r[1:] < RSI_UNDER)] & (q > VOL_X * qa)
    return [int(d.t.iloc[i]) for i in np.flatnonzero(hit)]


def capit_signals(d4: dict, last4: int) -> tuple:
    """(signals {coin: (signal close, 24h drop)}, breadth) at the 4h bar opening at last4: coins whose RSI crossed
    under 20 on volume at that bar, down >= DROP over 6 bars, while >= BREADTH coins did so within the last 6 bars."""
    hits = {s: capit_hits(d) for s, d in d4.items()}
    breadth = sorted(s for s, h in hits.items() if any(t >= last4 - 5 * H4 for t in h))
    out = {}
    if len(breadth) < BREADTH:
        return out, breadth
    for s, h in hits.items():
        if last4 not in h:
            continue
        d = d4[s]
        i = np.flatnonzero(d.t.to_numpy() == last4)
        if not len(i) or i[0] < 6:
            continue
        c = d.c.to_numpy(float)
        dr = c[i[0]] / c[i[0] - 6] - 1
        if dr <= -DROP:
            out[s] = (float(c[i[0]]), float(dr))
    return out, breadth


def gross_gate(orders: list, actual: dict, prices: dict, equity: float, cap: float = GROSS_CAP):
    """The account-level 10x guard. Reductions and closes always go and are counted first; an open or add is sent
    only while the account's gross notional, with it, stays under cap x equity. Returns (allowed, refused)."""
    gross = sum(abs(q) * (prices.get(s) or 0.0) for s, q in actual.items())
    gross -= sum(q * (prices.get(s) or 0.0) for s, _, q, red, _ in orders if red)
    ok, no = [], []
    for o in orders:
        s, _, q, red, _ = o
        if red:
            ok.append(o)
            continue
        n = q * (prices.get(s) or 0.0)
        if gross + n > cap * equity:
            no.append(o)
        else:
            gross += n
            ok.append(o)
    return ok, no


def is_late(day: str, clock_ms=None) -> bool:
    """More than LATE_MS since the daily close that opens `day`?"""
    now = clock_ms if clock_ms is not None else datetime.now(timezone.utc).timestamp() * 1000
    return now - pd.Timestamp(day).timestamp() * 1000 > LATE_MS


def rebase(book: dict, prices: dict) -> int:
    """A basket rebalanced LATE is entered at the live price, not at the close it was ranked on: marking it from that
    close would book a day of moves it never held. The first VM run did - its MN and carry baskets were set at 23:53
    and marked from 00:00 the day before, -$6.90 (2.3%) on day 1. Re-marks the basket at the live prices (the ones the
    ledger trades at); coins with no live price keep the close. Returns how many were re-marked."""
    n = 0
    for s in book["weights"]:
        if prices.get(s):
            book["mark_px"][s] = float(prices[s])
            n += 1
    return n


def targets(st: dict) -> dict:
    """Signed coin quantities the extra books hold, by Binance symbol."""
    fin, out = st.get("fin"), {}
    if not fin:
        return out
    for s, q in st.get("exec", {}).get("carry_qty", {}).items():
        out[s] = out.get(s, 0.0) + q
    for b in ("daily", "capit2"):
        for s, p in fin[b]["open"].items():
            out[s] = out.get(s, 0.0) + p["qty"]
    import news_books as nbk                       # the news and NASDAQ-dip books (2026-10-17)
    for s, q in nbk.targets(st).items():
        out[s] = out.get(s, 0.0) + q
    return out


# ---------------------------------------------------------------- data (Binance public, as the backtests)

def funding_sum(sym: str, start_ms: int, end_ms: int) -> float:
    """Funding rates settled in (start_ms, end_ms] - half-open and bounded at BOTH ends (mistake #15)."""
    if not start_ms or end_ms <= start_ms:
        return 0.0
    try:
        r = mp.get(f"{FAPI}/fapi/v1/fundingRate?symbol={sym}&startTime={start_ms + 1}&endTime={end_ms}&limit=1000")
    except Exception:
        return 0.0
    return float(sum(float(x["fundingRate"]) for x in (r or []) if start_ms < int(x["fundingTime"]) <= end_ms))


def bars4h(sym: str, now_ms: int, limit: int = 150) -> "pd.DataFrame | None":
    """Closed 4h klines (t = bar open, ms; o h l c; q = quote volume)."""
    try:
        k = mp.get(f"{FAPI}/fapi/v1/klines?symbol={sym}&interval=4h&limit={limit}")
    except Exception:
        return None
    if not k:
        return None
    d = pd.DataFrame([[int(x[0]), float(x[1]), float(x[2]), float(x[3]), float(x[4]), float(x[7])] for x in k],
                     columns=["t", "o", "h", "l", "c", "q"])
    return d[d.t + H4 <= now_ms].reset_index(drop=True)


def enable(cp):
    """Install the final configuration in THIS PROCESS: the MN book ranks by the blend, and combo_paper.daily's bars
    are remembered so the extra books read the same data without fetching it twice. combo_paper.py is not edited."""
    def remember(fn, key):
        def w(*a, **k):
            r = fn(*a, **k)
            LAST[key] = r
            return r
        return w
    cp.mp.target = mn_blend_target
    cp.mp.fetch_all = remember(_FETCH_ALL, "bars")
    cp.mp.perp_universe = remember(_UNIVERSE, "universe")
    cp.mp.candidates = month_pool
    cp.bp.atr = wilder_atr
    cp.bp.manage = manage_bt
    cp.bp.MAX_LEVERAGE = TREND_LEV
    cp.START_EQ = EQUITY                     # status reads its change from the $300 this account starts with
    _CP[0] = cp


_CP: list = [None]
_CANDIDATES = mp.candidates


def wilder_atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    """THE BACKTEST'S ATR (bot.core.indicators.atr: Wilder's smoothing, alpha 1/n) for the trend book's stops.
    blend_paper.atr is a 14-bar SIMPLE mean, so the live stops and trails were not the backtest's: replaying the
    final machine's first 13 days with the live formula and trail bar reproduced 37 of 37 live trend exits, with the
    backtest's only 32 - all 5 misses shorts, whose 5xATR trail is the tightest (backtest/live_check.py, 2026-10-22)."""
    from bot.core.indicators import atr as _wilder
    return _wilder(df, n)


def manage_bt(st, key, rec, bar, hi, lo, a, **kw):
    """blend_paper.manage with the BACKTEST's trail bar: walk() / the short trail move the stop off the ATR of the bar
    BEFORE the one being judged (a[k-1]); blend_paper passes the bar just closed (a[k]). The ATR of the previous call is
    kept on the position (a_bt, saved with the state); on a position's first bar it is the entry's own ATR (risk /
    SL_MULT), which is what the backtest uses there too."""
    import blend_paper as bp
    prev = rec.get("a_bt")
    if prev is None:
        prev = rec["risk"] / bp.SL_MULT if rec.get("risk") else a
    rec["a_bt"] = a
    return _ORIG_MANAGE(st, key, rec, bar, hi, lo, prev, **kw)


def _orig_manage():
    import blend_paper as bp
    return bp.manage


_ORIG_MANAGE = _orig_manage()


def month_pool(syms: list, fetch=None, now=None) -> list:
    """THE BACKTEST'S UNIVERSE, live (2026-10-22, backtest/live_check.py). mn_paper picks its candidate pool as the top
    CAND_N perps by TODAY's 24h volume (its caveat 1), so the universe changed day to day: a coin whose volume surged
    joined the daily book a day late (IOST, 10-22), and the MN baskets shared only 67-89% of their names with the
    backtest's. The backtest ranks EVERY perp by the PRIOR calendar month's quote volume and keeps that list for the
    month (wide_book.eligibility). This does the same: once a month, every listed USDT perp's daily bars, the top CAND_N
    by last month's quote volume (listed >= MIN_AGE_D), saved beside the state and reused all month; mp.eligible then
    takes the top 60 / 40 from it as before. If under 90% of the perps can be read, today falls back to the 24h pool
    (logged) and the month is tried again on the next call. Only the process that called enable() uses it."""
    import json
    import time as _t
    now = now or datetime.now(timezone.utc)
    month = f"{now:%Y-%m}"
    prev = (pd.Timestamp(month + "-01") - pd.Timedelta(days=1)).strftime("%Y-%m")
    cp = _CP[0]
    f = cp.P["state"].parent / "month_pool.json" if cp is not None and cp.P.get("state") else None
    saved = {}
    if f is not None and f.exists():
        try:
            saved = json.loads(f.read_text())
        except Exception:  # noqa: BLE001
            saved = {}
    if month not in saved:
        vol, ok = {}, 0
        for s in syms:
            d = (fetch or mp.daily)(s, limit=mp.NEED_BARS)
            if d is not None and len(d):
                ok += 1
                age = (d.time.iloc[-1] - d.time.iloc[0]).days
                m = d[d.time.dt.strftime("%Y-%m") == prev]
                if age >= mp.MIN_AGE_D and len(m):
                    vol[s] = float(m.qvol.sum())
            if fetch is None:
                _t.sleep(0.05)
        if ok < 0.9 * len(syms):
            log(f"UNIVERSE {month}: read {ok} of {len(syms)} perps - today uses the 24h-volume pool, retrying next call")
            return _CANDIDATES(syms)
        saved = {month: sorted(vol, key=lambda s: -vol[s])[:mp.CAND_N]}
        if f is not None:
            f.write_text(json.dumps(saved))
        log(f"UNIVERSE {month}: top {len(saved[month])} of {ok} perps by {prev} quote volume (the backtest's rule), "
            f"fixed for the month")
    listed = set(syms)
    return [s for s in saved[month] if s in listed]


# ---------------------------------------------------------------- the books

def _book(st, key, pnl, fee):
    st["equity"] += pnl - fee
    cum = st.setdefault("cum", {})
    cum[key] = cum.get(key, 0.0) + pnl
    cum["fees"] = cum.get("fees", 0.0) + fee


def _open(st, book, s, px, extra, now_ms):
    fin = st["fin"]
    if len(fin[book]["open"]) >= SLOTS or s in fin[book]["open"] or not px:
        return False
    k = K_DAILY if book == "daily" else K_CAPIT2 * CAPIT2_LEV
    usd = k * st["equity"] / SLOTS
    fin[book]["open"][s] = dict(qty=usd / px, entry=px, t_ms=now_ms, **extra)
    _book(st, book, 0.0, usd * SIDE_FEE)
    return True


def _close(st, book, s, px, why, now_ms, fund=funding_sum, rec=None):
    p = st["fin"][book]["open"].pop(s)
    f = fund(s, p["t_ms"], now_ms)
    pnl = p["qty"] * (px - p["entry"]) - p["qty"] * p["entry"] * f
    fee = p["qty"] * px * SIDE_FEE
    _book(st, book, pnl, fee)
    ret = px / p["entry"] - 1 - 2 * SIDE_FEE - f
    log(f"{book.upper()} CLOSE {s} at {px:.6g} ({why}): {ret:+.2%} net, P&L {pnl - fee:+.2f} -> account {st['equity']:.2f}")
    if rec:
        rec(dict(ts=f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}", book=book, symbol=s, entry=f"{p['entry']:.8g}",
                 exit=f"{px:.8g}", ret=f"{ret:.5f}", pnl=f"{pnl - fee:.4f}", why=why, equity=f"{st['equity']:.4f}"))
    return ret


def daily_books(st: dict, prices: dict, rec=None, fund=funding_sum, fetch=None, clock_ms=None):
    """Once per new daily close, right after combo_paper.daily has run: mark and rebalance the carry book, then the
    daily Bollinger book's exits and entries (at the live price, which is the next open).

    LATE START: the backtest buys at the open right after the signal close. A process that starts (or comes back)
    hours later would buy that old signal at today's price - the first dry run did, PUMP 10.7% under the close it was
    read on, 24 hours late. So BUYS are taken only within LATE_MS of the close; exits always go (late is still out)."""
    fin = st["fin"]
    day = st["last_day"]
    if not day or fin["last_day"] == day:
        return
    now_ms = int(pd.Timestamp(day).timestamp() * 1000)
    bars = LAST.get("bars")
    bar_day = pd.Timestamp(day) - pd.Timedelta(days=1)
    if not bars or max(d.time.iloc[-1] for d in bars.values()) != bar_day:
        syms, _ = mp.perp_universe()
        bars = (fetch or mp.fetch_all)(mp.candidates(syms))
    syms, floors = LAST.get("universe") or mp.perp_universe()
    closes = {s: float(d.close.iloc[-1]) for s, d in bars.items() if d.time.iloc[-1] == bar_day}
    held = sorted((set(fin["carry"]["weights"]) | set(fin["daily"]["open"])) - set(closes))
    if held:
        closes.update(mp.held_closes(held, syms, bar_day))
    elig = mp.eligible(bars, f"{pd.Timestamp(day):%Y-%m}")
    late = is_late(day, clock_ms)
    # ---- CARRY: mark, then rebalance every 7 days
    cr, ex = fin["carry"], st.setdefault("exec", {})
    since = fin["last_fund_ms"]
    if cr["weights"] and cr["mark_px"]:
        pnl, gone = 0.0, []
        for s, w in cr["weights"].items():
            p0 = cr["mark_px"].get(s)
            if s not in closes or not p0:
                gone.append(s)
                continue
            pnl += cr["base"] * (w * (closes[s] / p0 - 1) - w * fund(s, since, now_ms))
        for s in gone:
            cr["weights"].pop(s, None)
        _book(st, "carry", pnl, 0.0)
        if gone:
            log(f"CARRY: no fresh bar for {', '.join(gone)} - exited at last mark")
    due = cr["last_rebal"] is None or (pd.Timestamp(day) - pd.Timestamp(cr["last_rebal"])).days >= mp.HOLD_D
    if due:
        f7 = {s: fund(s, now_ms - CARRY_WIN_D * DAY_MS, now_ms) for s in elig}
        tgt = carry_target(f7)
        if tgt:
            per = K_CARRY * st["equity"] * 0.5 / max(sum(1 for x in tgt.values() if x > 0), 1)
            small = [s for s in tgt if per < floors.get(s, 5.0)]
            for s in small:
                tgt.pop(s)
            cr["skipped_small"] += len(small)
            c = mp.cost(cr["weights"], tgt) * K_CARRY * st["equity"]
            _book(st, "carry", 0.0, c)
            cr.update(weights=tgt, base=K_CARRY * st["equity"], last_rebal=day, n_rebal=cr["n_rebal"] + 1)
            cr["mark_px"] = {s: closes[s] for s in tgt if s in closes}
            if late:
                rebase(cr, prices)
            ex["carry_qty"] = {s: w * cr["base"] / cr["mark_px"][s] for s, w in tgt.items() if s in cr["mark_px"]}
            log(f"CARRY REBALANCE #{cr['n_rebal']} | long {' '.join(s[:-4] for s, x in tgt.items() if x > 0)} | short "
                f"{' '.join(s[:-4] for s, x in tgt.items() if x < 0)} | ${per:.2f}/position | fee ${c:.3f}")
    if not (due and late):
        cr["mark_px"] = {s: closes[s] for s in cr["weights"] if s in closes}
    ex["carry_qty"] = {s: q for s, q in ex.get("carry_qty", {}).items() if s in cr["weights"]}
    fin["last_fund_ms"] = now_ms
    # ---- DAILY: exits on yesterday's close, then entries, both at the live price (= the next open)
    uni = elig[:TOP_N]
    fin["uni40"] = uni
    db = fin["daily"]
    for s in list(db["open"]):
        d = bars.get(s)
        if d is None or d.time.iloc[-1] != bar_day:
            d = mp.daily(s, limit=40)
        if d is None or not len(d) or d.time.iloc[-1] != bar_day:
            continue                                         # no fresh close (halted): hold, judge tomorrow
        age = (now_ms - db["open"][s]["t_ms"]) / DAY_MS
        why = "mean20" if daily_exit(d.close.to_numpy(float)) else ("cap" if age >= CAP_D else None)
        if why and prices.get(s):
            _close(st, "daily", s, prices[s], why, now_ms, fund, rec)
    if late:
        log(f"DAILY: {day}'s close was read more than {LATE_MS // 3_600_000}h after it - no buys today (exits only)")
    for s in [] if late else uni:
        d = bars.get(s)
        if s in db["open"] or d is None or d.time.iloc[-1] != bar_day or not daily_entry(d.close.to_numpy(float)):
            continue
        if _open(st, "daily", s, prices.get(s), {}, now_ms):
            db["taken"] += 1
            log(f"DAILY BUY {s} at {prices[s]:.6g} (close {d.close.iloc[-1]:.6g} above Bollinger(30, 1.5)); out after "
                f"a close under the 20-day mean")
    fin["last_day"] = day


def bars1m(sym: str, start_ms: int, end_ms: int) -> "pd.DataFrame | None":
    """Closed 1-minute klines opening in [start_ms, end_ms) (t = bar open, ms; l = low); None if they cannot be read."""
    try:
        k = mp.get(f"{FAPI}/fapi/v1/klines?symbol={sym}&interval=1m&startTime={start_ms}&endTime={end_ms - 1}&limit=1000")
    except Exception:
        return None
    if k is None:
        return None
    d = pd.DataFrame([[int(x[0]), float(x[3])] for x in k], columns=["t", "l"])
    return d[d.t + 60_000 <= end_ms].reset_index(drop=True)


def capit2_poll(st: dict, prices: dict, now_ms: int, rec=None, fund=funding_sum, get4=bars4h, get1m=bars1m):
    """Every poll: targets on the live price, limits on the minutes since the last poll; on a new closed 4h bar, the
    bar-based exits and new signals.

    THE LIMIT RESTS (2026-10-22, backtest/capit2_exec.py): a 2-minute poll at market misses the fastest wick-and-bounce
    fills, which are the best trades (94% won), and earned +1.76% a signal against the backtested resting limit's +2.15%.
    So a limit is filled AT the limit as soon as any closed 1-minute low since the last check traded 0.3% through it,
    as the backtest fills it; only if the minutes cannot be read does the poll's live price decide (filled at that
    price, as before). In dry mode this is the ledger of a resting post-only order. A REAL account needs that order on
    the venue itself (wick_live.py's machinery) - not built: ALLOW_REAL is False."""
    fin = st["fin"]
    cb = fin["capit2"]
    for s, p in list(cb["open"].items()):                    # target, on the live price
        px = prices.get(s)
        if px and px >= p["entry"] * (1 + TARGET):
            _close(st, "capit2", s, px, "target", now_ms, fund, rec)
        elif px and px <= p["entry"] * (1 - LIQ_EQ):         # at 2x the backtest lost this slot's margin here
            _close(st, "capit2", s, px, "liquidation_eq", now_ms, fund, rec)
    for s, r in list(cb["pending"].items()):                 # limits: resting for the bar after the signal bar
        px = prices.get(s)
        live_end = r["signal_t"] + 2 * H4
        seen = r.get("seen", r["signal_t"] + H4)
        end = min(now_ms, live_end)
        m1 = get1m(s, seen, end) if end > seen else None
        hit = None
        if m1 is not None:
            if len(m1):
                r["seen"] = int(m1.t.iloc[-1]) + 60_000
            th = m1[m1.l <= r["lim"] * (1 - THROUGH)]
            if len(th):
                hit = (r["lim"], int(th.t.iloc[0]) + 60_000)
        elif now_ms < live_end and px and px <= r["lim"] * (1 - THROUGH):
            hit = (px, now_ms)
        if hit:
            cb["pending"].pop(s)
            if _open(st, "capit2", s, hit[0], dict(signal_t=r["signal_t"]), hit[1]):
                cb["filled"] += 1
                log(f"CAPIT2 BUY {s} at {hit[0]:.6g} (limit {r['lim']:.6g}, traded through); target "
                    f"{hit[0] * (1 + TARGET):.6g}")
            else:
                log(f"CAPIT2 {s} traded through its limit but all {SLOTS} slots are full - not taken")
        elif now_ms >= live_end:
            cb["pending"].pop(s)
            cb["cancelled"] += 1
            log(f"CAPIT2 limit {s} {r['lim']:.6g} not reached in its bar - cancelled")
    last4 = (now_ms // H4) * H4 - H4                         # the last CLOSED 4h bar's open
    if last4 == fin["last_4h"]:
        return
    want = sorted(set(fin["uni40"]) | set(cb["open"]))
    d4 = {}
    for s in want:
        d = get4(s, now_ms)
        if d is not None and len(d):
            d4[s] = d
    if not d4 or max(int(d.t.iloc[-1]) for d in d4.values()) < last4:
        return                                               # the bar is not served yet: retry next poll
    for s, p in list(cb["open"].items()):                    # closed-bar exits, in the backtest's order
        d = d4.get(s)
        if d is None or not prices.get(s):
            continue
        after = d[d.t > p["signal_t"]].reset_index(drop=True)
        if not len(after):
            continue
        k = np.arange(1, len(after) + 1)
        since_fill = after[after.t >= p["t_ms"]]            # bars that opened after the fill
        if len(since_fill) and since_fill.h.max() >= p["entry"] * (1 + TARGET):
            why = "target_late"
        elif ((k >= NW_BARS) & (after.c.to_numpy() <= p["entry"])).any():
            why = "not_working"
        elif k[-1] >= CAP_BARS:
            why = "cap"
        else:
            continue
        _close(st, "capit2", s, prices[s], why, now_ms, fund, rec)
    sig, breadth = capit_signals({s: d4[s] for s in fin["uni40"] if s in d4}, last4)
    for s, (c, dr) in sig.items():
        if s in cb["open"] or s in cb["pending"]:
            continue
        cb["pending"][s] = dict(lim=c * (1 - LIMIT), signal_t=last4)
        cb["placed"] += 1
        log(f"CAPIT2 SIGNAL {s}: {len(breadth)} coins capitulated in 24h, down {dr:.0%}; buys at or under "
            f"{c * (1 - LIMIT) * (1 - THROUGH):.6g} until this bar closes")
    fin["last_4h"] = last4


def bids_poll(st: dict, now_ms: int, rec=None, fetch=None, listed_fn=None, label_fn=None, universe_fn=None,
              per_call: int = 3) -> int:
    """THE CRASH BIDS as a paper ledger inside this account (2026-10-22). Every backtest the final machine is judged
    against counts them (final_machine.py's DEPLOYABLE line, all_books.py, machine_fixes.py: +15% / +7% of the typical
    year, tune / holdout, 10 of 10 orderings), but the running dry bot had no desk - and wick_live's dry desk places
    no fills. So each closed hour, 3 minutes after it closes: wick_paper.py's rule on Bitget's 1-minute candles - a bid
    10% under the previous close on each of the top-40 (1/40 of THIS account's equity each), filled once the low trades
    0.1% through it, the first 10 fills of the hour kept, sold at the hour's close; none on BEAR days; costs
    wick_paper.COST. Booked straight into the account (book "bids"); a real account needs combo_bot --wick instead.
    Starts from the hour it is first called (no back-fill); catches up at most wick_paper.CATCHUP_H hours, `per_call`
    an hour-poll so a long outage does not stall the other books (40 candle reads an hour). A failed
    label or universe read leaves the hour for the next poll. Returns the hours processed."""
    import wick_paper as wp
    fetch = fetch or wp.minutes
    b = st["fin"].setdefault("bids", dict(last_h=None, hours=0, bear_hours=0, fills=0, kept=0, labels={}, universes={},
                                          listed=None))
    due = (now_ms - wp.DELAY_S * 1000) // wp.HOUR_MS * wp.HOUR_MS - wp.HOUR_MS     # the last hour closed 3+ min ago
    if b["last_h"] is None:
        b["last_h"] = due
        log(f"BIDS: crash-bid ledger on from the hour after {datetime.fromtimestamp(due / 1000, timezone.utc):%Y-%m-%d %H:00}")
        return 0
    hours = list(range(max(b["last_h"] + wp.HOUR_MS, due - (wp.CATCHUP_H - 1) * wp.HOUR_MS), due + 1, wp.HOUR_MS))[:per_call]
    done = 0
    for H in hours:
        ts = datetime.fromtimestamp(H / 1000, timezone.utc)
        month, day, hour = f"{ts:%Y-%m}", f"{ts:%Y-%m-%d}", f"{ts:%Y-%m-%d %H:00}"
        try:
            if day not in b["labels"]:
                b["labels"] = {day: (label_fn or wp.label)(day)}
            if b["labels"][day] == "bear":
                b["bear_hours"] += 1
                b["last_h"], done = H, done + 1
                continue
            if month not in b["universes"]:
                b["universes"] = {month: list((universe_fn or wp.universe)(month))}
                b["listed"] = sorted((listed_fn or wp.bitget_listed)())
        except Exception as e:  # noqa: BLE001 - an unread label / universe: try this hour again next poll
            log(f"BIDS {hour}: {str(e)[:120]} - retrying next poll")
            break
        size = st["equity"] / wp.TOP_N
        found = []
        if size >= wp.MIN_ORDER:
            listed = set(b["listed"] or [])
            for s in b["universes"][month]:
                name = wp.bitget_name(s, listed) if listed else s
                if name is None:
                    continue
                bars = fetch("bitget", name, H - wp.MIN_MS, 61)
                if bars is None:
                    continue
                r = wp.fill_of(bars[1:], bars[0][4])
                if r:
                    j, f, _, exit_px = r
                    found.append(dict(sym=name, minute=j, fill=f, exit=exit_px))
        kept = wp.cap(found)
        for x in kept:
            gross = size * (x["exit"] / x["fill"] - 1)
            _book(st, "bids", gross, size * wp.COST)
            if rec:
                rec(dict(ts=f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}", book="bids", symbol=x["sym"],
                         entry=f"{x['fill']:.8g}", exit=f"{x['exit']:.8g}", ret=f"{wp.net(x['exit'], x['fill']):.5f}",
                         pnl=f"{gross - size * wp.COST:.4f}", why="hour_close", equity=f"{st['equity']:.4f}"))
        if found:
            log(f"BIDS {hour}: {len(found)} filled, {len(kept)} kept ({' '.join(x['sym'][:-4] for x in kept)}) -> "
                f"account {st['equity']:.2f}")
        b["hours"] += 1
        b["fills"] += len(found)
        b["kept"] += len(kept)
        b["last_h"], done = H, done + 1
    return done


def carry_squeeze_exits(st: dict, prices: dict, short_exit: float = 0.50, rec=None) -> list:
    """The carry book's short-leg exit (kill_sweeps.py --carry used +50%): as combo_bot.mn_squeeze_exits - a short
    whose live price is 50% above the price the book opened it at is dropped until the next rebalance."""
    fin = st.get("fin")
    if not fin:
        return []
    cr, ex = fin["carry"], st.setdefault("exec", {})
    qty, out = ex.get("carry_qty", {}), []
    for s, w in list(cr["weights"].items()):
        q, px = qty.get(s), prices.get(s)
        if w >= 0 or not q or not px or not cr["base"]:
            continue
        opened = w * cr["base"] / q
        if px < opened * (1 + short_exit):
            continue
        mark = cr["mark_px"].get(s, opened)
        pnl = cr["base"] * w * (px / mark - 1)
        _book(st, "carry", pnl, abs(q) * px * SIDE_FEE)
        cr["weights"].pop(s, None)
        cr["mark_px"].pop(s, None)
        qty.pop(s, None)
        log(f"CARRY EXIT {s}: short opened at {opened:.6g}, live {px:.6g} ({px / opened - 1:+.0%}) - dropped until the "
            f"next rebalance (P&L since the last mark {pnl:+.2f})")
        if rec:
            rec(dict(ts=f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}", book="carry", symbol=s, entry=f"{opened:.8g}",
                     exit=f"{px:.8g}", ret=f"{-(px / opened - 1):.5f}", pnl=f"{pnl:.4f}", why="short_exit",
                     equity=f"{st['equity']:.4f}"))
        out.append(s)
    return out


def status(st: dict):
    fin, c = st.get("fin"), st.get("cum", {})
    if not fin:
        return
    cr, db, cb = fin["carry"], fin["daily"], fin["capit2"]
    print(f"  FINAL BOOKS  carry ${c.get('carry', 0):+.2f} | daily ${c.get('daily', 0):+.2f} | capit2 ${c.get('capit2', 0):+.2f}"
          f"   (trend guard {TREND_LEV}x, account cap {GROSS_CAP:g}x)")
    print(f"    carry   {cr['n_rebal']} rebalances, last {cr['last_rebal']}, {len(cr['weights'])} names")
    print(f"    daily   {len(db['open'])} open ({', '.join(s[:-4] for s in db['open'])}), {db['taken']} taken")
    print(f"    capit2  {len(cb['open'])} open, {len(cb['pending'])} pending, limits filled {cb['filled']} of {cb['placed']}"
          f" ({cb['cancelled']} cancelled)")
    import news_books as nbk
    nbk.status(st)
