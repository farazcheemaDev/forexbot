"""THE VALIDATED CONFIGURATION, LIVE ON PAPER — $221, 12 coins, three timeframes.

WHY THIS FILE EXISTS AND NOT A BITGET DEMO BOT
    Bitget's demo lists exactly THREE contracts (SBTC, SETH, SXRP). The validated
    strategy needs twelve, and three coins was measured at +3.98%/month against the
    twelve-coin blend's ~+12%. A Bitget demo run therefore cannot test this strategy
    at all - it can only test the ORDER PLUMBING, which longtrend_bot.py already does.

    Second reason: the $221 floor is a MEXC number. On Bitget's $5-per-order minimum
    the same book needs $585 (binding coin ENA, whose 12h stop is 14.84% wide). At
    $221 on Bitget most signals would be rejected for size, which is a test of the
    venue, not of the strategy.

    So: live Binance prices, simulated fills, MEXC's real per-coin minimums.

THE CONFIGURATION, AND WHERE EACH PIECE WAS VALIDATED
    universe    12 cheap-but-reputable alts        backtest/cheap_wide.py
    sleeves     1h + 4h + 12h, sharing 8 slots     backtest/blend.py
                   monthly correlation 1h vs 4h = +0.178; the blend turns 2022 from
                   -217% (long only) to +64%
    entry       close beyond the Bollinger band (30, 1.5)
    stop        2 x ATR(14) of that sleeve's own bars = 1R
    long exit   20 x ATR trail, 5-unit pyramid adding every 2R
    short exit  5 x ATR trail, ONE unit            backtest/shortside.py
                   shorts are a HEDGE, not a profit source: -0.036R standalone under
                   a strict fill, yet they cut drawdown 78.5% -> 68.9% and RAISE
                   compounded return, because less drawdown means less volatility drag
    breakeven   stop to entry once +3R             backtest/ddcontrol.py
                   12 of 12 cells reduced drawdown; both risk levels peaked at 3R
    regime      risk x0.25 while BTC < its 200h average    backtest/opt200.py
                   the only one of 26 cells that survived the holdout on all three of
                   return, drawdown and capital floor
    risk        0.30% of equity per unit
    expectation ~+12%/month full history, ~+8%/month on the last two years, 57.7% DD

    PLAN AGAINST +8%. The strategy made 40% of its lifetime profit in 2021 and was
    close to flat through 2025-2026 (2.5% of profit on 30% of trades). A month of
    this proves the machinery, not the return.

WHAT IS SIMULATED AND WHAT IS NOT
    Fills at the bar close, 12bp round trip. Slippage is NOT modelled. The per-coin
    MEXC minimum IS enforced and every rejection is counted - that count is the honest
    measure of whether $221 is enough.

    The trail advances ONCE PER CLOSED BAR and is checked from the following bar,
    which is exactly how a bar-close bot behaves: during a bar its stop sits at the
    previous bar's level. (backtest/strictfill.py models a continuously-updating trail
    instead and is therefore over-pessimistic for this implementation; it was run as a
    robustness check and the result survived it.)

A SECOND BOOK, "TIGHT", RUNS BESIDE IT (added 2026-09-22) - backtest/btc_exit.py
    Same signals, same sizing, same slots, its own state and trades files. The ONLY
    difference: when BTC's own 4h trend breaks - a 4h close below (highest close since
    the last break - 5 x ATR(14)) - every open long in the tight book switches from the
    20xATR trail to 5xATR. Over 5 tie-break orderings and 22 neighbouring settings this
    cut drawdown in nearly every case (58% -> ~36%, worst month -37% -> -21%) with
    total R at or above deployed; the monthly-return effect was split between halves,
    which is why it runs on paper beside the deployed rules instead of replacing them.

    It FORKS from the main book the first time it runs - identical open positions and
    equity - so from that moment the two books differ by the rule alone.

    The BTC trigger uses Wilder ATR (bot.core.indicators) to match the backtest. Note the
    coin trails in this file use a simple-average ATR, as they always have; the backtest
    used Wilder for those too. Same in both books, so the comparison is unaffected.

A THIRD BOOK, "SIZED" (2026-09-22), and a FOURTH, "SHORT-BOOST" (2026-09-23)
    SIZED scales each new LONG's risk by a frozen runner-probability model, mean 1, so it
    carries no more total risk - it moves risk to higher-runner-odds signals.
    SHORT-BOOST scales a SHORT's risk x5 when BTC's 4h trail is broken at its entry: those
    shorts earned +0.481R against +0.043R for all other shorts over 84 break episodes
    (backtest/vol_target.py). Every short it takes records whether it was boosted, so the
    per-trade effect is readable before the equity gap separates.

A FIFTH BOOK, "TSTOP" (2026-09-23) - backtest/graveyard_rescore.py
    The tight book PLUS a time stop: close a LONG still under +2R after 100 bars of its own
    sleeve. Found by re-scoring the graveyard on the corrected engine (causal entry times,
    funding charged, entry-sized compounding) - the funding fix is not neutral between
    variants, because rules that shorten long holds were never credited with the funding
    they save.

    READ ITS EVIDENCE THE WAY DOC 01 READS THE 1000h GATE. Against MAIN it clears both
    halves (+2.50 +- 0.29 tune, +4.34 +- 0.48 holdout). Against TIGHT alone - the book it
    forks beside - the RETURN gain is holdout-only (-0.37 tune, +2.36 holdout), which is the
    mined-split signature. The WORST MONTH improves on both halves in the same direction
    (+8.4 points tune, +13.1 holdout), and that is the part to trust.

    Mechanism: a long still under +2R after 100 bars is dead money that keeps paying funding.

A SIXTH BOOK, "UNITS" (2026-09-24) - backtest/pyramid_params.py
    The tight book PLUS a 6th and 7th pyramid unit. MAX_UNITS=5 was never swept on the corrected
    engine and it leaves return on the table: 7 units beats 5 on BOTH halves, on ALL FOUR bar
    grids, 10/10 orderings, t +14 to +33, and it holds at $100 capital with no rise in venue
    rejections - units 6-7 are the same notional as unit 1.

    IT IS NOT LEVERAGE, which is the objection to check first. Matched on return, reaching
    7-unit performance with 5 units needs 0.42% risk and costs 8 more points of drawdown (64%
    against 56%) and more gross leverage (7.2x against 6.3x). The mechanism is pyramid.py's
    original one: units 6 and 7 are only added once a trade is +10R and +12R up, by which point
    the breakeven stop sits above entry, so they carry the upside and almost none of the
    downside. Raising risk instead adds size to the four trades in five that stop at -1R.

    7 and not 10: ten earns more but its MAXIMUM gross leverage reaches 10.3x, past where
    lev_test.py found liquidation destructive. Cost of seven: drawdown 50% -> 56%.

    All seven books share one process and one set of klines. The MAIN book is saved before any
    extra book runs and each extra book's errors are caught, so none of them can cost the
    main book a cycle.

    python blend_paper.py            live loop (all seven books)
    python blend_paper.py --status   report and exit (all seven books)
    python blend_paper.py --once     one cycle and exit
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
LOGS = ROOT / "logs"; LOGS.mkdir(exist_ok=True)
STATE = LOGS / "blend_state.json"
TRADES = LOGS / "trades_blend.csv"
LOGF = LOGS / "blend_paper.log"
TIGHT_STATE = LOGS / "blend_state_tight.json"
TIGHT_TRADES = LOGS / "trades_blend_tight.csv"
SIZED_STATE = LOGS / "blend_state_sized.json"
SIZED_TRADES = LOGS / "trades_blend_sized.csv"
SBOOST_STATE = LOGS / "blend_state_sboost.json"
SBOOST_TRADES = LOGS / "trades_blend_sboost.csv"
TRIPLE_STATE = LOGS / "blend_state_triple.json"
TRIPLE_TRADES = LOGS / "trades_blend_triple.csv"
UNITS_STATE = LOGS / "blend_state_units.json"
UNITS_TRADES = LOGS / "trades_blend_units.csv"
TSTOP_STATE = LOGS / "blend_state_tstop.json"
TSTOP_TRADES = LOGS / "trades_blend_tstop.csv"
# Shorts entered while BTC's 4h trail is broken earned +0.481R against +0.043R for all other
# shorts over 84 break episodes (backtest/vol_target.py). x5 is the safe end of the
# executable x5-x8 range; above x8 the book's MAX gross leverage breaks 10x. Every short
# trade in this book records whether it was boosted, so the per-trade effect can be read
# live without waiting for the equity gap to separate.
SBOOST_MULT = 5.0
BTC_TRAIL_K = 5.0                # BTC 4h trend break: close < best close - 5 x ATR(14)
TIGHT_TRAIL = 5.0               # the tight book's long trail once BTC has broken
# The TSTOP book = tight + a time stop. Close a LONG that is still under TSTOP_R after
# TSTOP_BARS bars of its own sleeve: 100 bars is ~4 days on 1h and ~50 days on 12h.
# Validated in backtest/graveyard_rescore.py on the corrected engine (causal entry times,
# funding charged, entry-sized compounding, 10 paired orderings). Against MAIN it clears
# both halves (+2.50 +- 0.29 tune, +4.34 +- 0.48 holdout). Against TIGHT alone - the book
# it actually forks from - the return gain is HOLDOUT ONLY (-0.37 tune, +2.36 holdout),
# which is the mined-split signature. What shows up on BOTH halves is the worst month:
# +8.4 points better on tune, +13.1 on holdout. That is the part to trust, and the reason
# this runs forward as paper instead of changing the live config.
# Mechanism: a long still under +2R after 100 bars is dead money that keeps paying funding.
# The UNITS book = tight + a seventh unit. backtest/pyramid_params.py swept the pyramid on the
# corrected engine and found MAX_UNITS=5 leaves return on the table: 7 units beats 5 on BOTH
# halves, on ALL FOUR bar grids, 10/10 orderings, t +14 to +33, and it holds at $100 capital with
# no rise in venue rejections because units 6-7 are the same notional as unit 1.
# It is NOT leverage: matched on return, reaching 7-unit performance with 5 units needs 0.42%
# risk and costs 8 more points of drawdown (64% vs 56%) and more gross leverage (7.2x vs 6.3x).
# The mechanism is pyramid.py's original one - units 6 and 7 are only added once a trade is
# +10R and +12R up, by which point the breakeven stop sits above entry, so they carry the upside
# and almost none of the downside.
# 7 and not 10: ten earns more but its MAXIMUM gross leverage reaches 10.3x, past where
# lev_test.py found liquidation destructive. Seven runs 6.3x p99 / 7.8x max.
# Cost: drawdown 50% -> 56%. Better-than-leverage, not free.
UNITS_MAX = 7
TSTOP_BARS = 100
TSTOP_R = 2.0

# ---- FROZEN runner-probability model for the SIZED book (backtest/runner_leverage.py) ----
# A position-only logistic model (holdout AUC 0.591), fit on all 5,628 historical long
# positions on 2026-09-22 and FROZEN here so the live period is genuinely out-of-sample and
# the VM needs no sklearn - it is plain arithmetic. It scales each LONG's risk by its
# runner-probability rank, mean held ~1, so the book takes no more total risk than the main
# book; it only moves risk from low-runner-odds signals to high ones. Shorts are unsized.
RS_FEATS = ["atr_expand", "ext_ma", "coin_30", "coin_90", "brk", "vsurge"]
RS_MEAN = [0.974199, 0.958253, 0.022061, -0.040916, 0.425946, 2.130552]
RS_STD = [0.237615, 0.074175, 0.044986, 0.088802, 0.472907, 3.003655]
RS_COEF = [0.164832, 0.27414, -0.031434, -0.1998, -0.003506, -0.095652]
RS_INTERCEPT = -0.027948
RS_ZPCT = [0.0, 2.5, 5.0, 7.5, 10.0, 12.5, 15.0, 17.5, 20.0, 22.5, 25.0, 27.5, 30.0, 32.5,
           35.0, 37.5, 40.0, 42.5, 45.0, 47.5, 50.0, 52.5, 55.0, 57.5, 60.0, 62.5, 65.0,
           67.5, 70.0, 72.5, 75.0, 77.5, 80.0, 82.5, 85.0, 87.5, 90.0, 92.5, 95.0, 97.5, 100.0]
RS_ZGRID = [-1.98484, -0.59592, -0.44112, -0.34636, -0.29868, -0.26563, -0.23227, -0.20818,
            -0.18541, -0.16607, -0.14899, -0.13185, -0.11537, -0.0998, -0.08513, -0.07283,
            -0.05971, -0.04618, -0.03505, -0.02367, -0.012, -0.00139, 0.01047, 0.02164,
            0.03304, 0.0454, 0.05788, 0.07083, 0.08363, 0.09693, 0.1096, 0.12567, 0.14466,
            0.16243, 0.18188, 0.20518, 0.23092, 0.26519, 0.3151, 0.41144, 2.38501]
RS_SPREAD = 0.9                 # +-90% tilt around the median-runner-odds signal
RS_CLIP = (0.10, 1.90)

START_EQ = 221.0
RISK_PCT = 0.30                  # per unit
# 12, not 8. Slots were swept at 8/12/16 while the regime gate was still 200h; after
# the gate moved to 1000h the sweep was re-run and 12 wins in the RECENT regime:
#   2026+, 0.30%/unit:   8 slots -> +1.05%/mo, 47.4% DD, floor $178
#                       12 slots -> +2.20%/mo, 55.0% DD, floor $208
# Return and return-per-drawdown both improve, so this is not simply more risk. The
# live bot corroborated it before the test: declined(slots) hit 9 in the first 24h,
# i.e. the book was generating signals it had no room to take.
#
# WHAT THIS COSTS: the capital floor rises $178 -> $208 against $221 of capital - a 6%
# margin, the thinnest in this configuration. Raising slots again (16) pushes the floor
# past $221 and is not affordable.
SLOTS = 12                       # shared across every coin AND every timeframe
FEE_BP = 12.0
BB_PERIOD, BB_STD = 30, 1.5
ATR_PERIOD = 14
SL_MULT = 2.0
LONG_TRAIL, SHORT_TRAIL = 20.0, 5.0
MAX_UNITS, ADD_EVERY_R = 5, 2.0
BE_AT_R = 3.0
# 1000h (42 days), NOT 200h. A 200-hour (8.5 day) average was being used to detect
# multi-year regimes, and it fires on ordinary pullbacks inside uptrends - exactly
# when a trend book should be at FULL size. backtest/regime_blend.py, out of sample:
#   200h  -> +6.31%/mo, 57.0% DD, MAR 1.33
#   1000h -> +10.66%/mo, 41.7% DD, MAR 3.07
# Changing this REQUIRES klines_deep(): Binance caps a request at 1000 bars.
REGIME_MA, REGIME_MULT = 1000, 0.25
MAX_LEVERAGE = 10.0
POLL_S = 120
SLEEVES = ("1h", "4h", "12h")
BARS_NEEDED = 900                # 12h resample needs ~(30+14)*12 = 528 hours; margin

BOOK = ["XRPUSDT", "SUIUSDT", "ADAUSDT", "LINKUSDT", "AVAXUSDT", "LTCUSDT",
        "ENAUSDT", "SHIBUSDT", "WLDUSDT", "NEARUSDT", "DOTUSDT", "ARBUSDT"]
# MEXC minimum order value in USDT, measured 2026-09-13 by backtest/venue_floor.py.
# These move with price - a step of 1 contract costs whatever the contract costs - so
# re-measure before trusting them with real funds.
MIN_ORDER = {"XRPUSDT": 1.338, "SUIUSDT": 0.708, "ADAUSDT": 0.203,
             "LINKUSDT": 1.130, "AVAXUSDT": 0.729, "LTCUSDT": 0.535,
             "ENAUSDT": 1.388, "SHIBUSDT": 0.005, "WLDUSDT": 0.388,
             "NEARUSDT": 2.282, "DOTUSDT": 0.100, "ARBUSDT": 0.137}


def log(m: str):
    line = f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S} | {m}"
    print(line, flush=True)
    with open(LOGF, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def klines(symbol: str, limit: int = BARS_NEEDED) -> pd.DataFrame | None:
    """Binance 1h closes. Signals come from Binance because it has the deepest
    history and the paper book is priced consistently with the backtests."""
    u = (f"https://api.binance.com/api/v3/klines?symbol={symbol}"
         f"&interval=1h&limit={limit}")
    for attempt in range(3):
        try:
            raw = json.load(urllib.request.urlopen(u, timeout=25))
            break
        except Exception as e:
            if attempt == 2:
                log(f"[{symbol}] klines failed: {type(e).__name__}: {str(e)[:80]}")
                return None
            time.sleep(2)
    d = pd.DataFrame(raw, columns=["t", "open", "high", "low", "close", "volume",
                                   "ct", "qv", "n", "tb", "tq", "ig"])
    for c in ("open", "high", "low", "close", "volume"):
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d["time"] = pd.to_datetime(d["t"], unit="ms")
    return d[["time", "open", "high", "low", "close", "volume"]].dropna()


def resample(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    """1h -> 4h/12h. OHLC aggregation must be first/max/min/last; taking `last` for
    `high` would silently disable every stop and trail check."""
    if rule == "1h":
        return df.reset_index(drop=True)
    d = df.set_index("time")
    out = d.resample(rule, label="right", closed="right").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last",
         "volume": "sum"}).dropna()
    return out.reset_index()


def atr(df: pd.DataFrame, n: int = ATR_PERIOD) -> pd.Series:
    h, lo, c = df["high"], df["low"], df["close"].shift(1)
    tr = pd.concat([h - lo, (h - c).abs(), (lo - c).abs()], axis=1).max(axis=1)
    return tr.rolling(n).mean()


def bands(df: pd.DataFrame):
    c = df["close"]
    ma = c.rolling(BB_PERIOD).mean()
    sd = c.rolling(BB_PERIOD).std(ddof=0)
    return ma - BB_STD * sd, ma + BB_STD * sd


def fresh() -> dict:
    return {"equity": START_EQ, "open": {}, "last_bar": {}, "hb": {},
            "taken": 0, "taken_long": 0, "taken_short": 0, "declined": 0,
            "too_small": 0, "no_margin": 0,
            "started": datetime.now(timezone.utc).isoformat()}


def load_state(path: Path = STATE) -> dict:
    if path.exists():
        try:
            s = json.load(open(path))
            for k, v in fresh().items():
                s.setdefault(k, v)
            return s
        except Exception:
            log(f"state unreadable ({path.name}) — starting fresh")
    return fresh()


def save_state(s: dict, path: Path = STATE):
    tmp = path.with_suffix(".tmp")
    json.dump(s, open(tmp, "w"), indent=1)
    tmp.replace(path)                 # atomic, so a kill mid-write cannot corrupt it


def rec_trade(row: dict, path: Path = TRADES):
    new = not path.exists()
    with open(path, "a", encoding="utf-8") as f:
        if new:
            f.write(",".join(row) + "\n")
        f.write(",".join(str(v) for v in row.values()) + "\n")



def klines_deep(symbol: str, need: int) -> "pd.DataFrame | None":
    """Binance caps klines at 1000 bars per request; the 1000h regime MA needs more.
    Pages BACKWARDS with endTime and dedupes on open time.

    DELIBERATELY SEPARATE FROM klines(). klines() runs for every coin on every poll -
    the hot path - while this runs once per bar for one symbol. A bug in here cannot
    reach coin signals.

    WHY THIS FUNCTION HAD TO EXIST AT ALL: REGIME_MA went 200 -> 1000 on 2026-09-14,
    and the guard below is `len(d) < REGIME_MA + 2`. Left on the old 300-bar fetch,
    that guard would have been true forever, the function would have returned the
    cached default of False, and THE REGIME GATE WOULD HAVE SILENTLY TURNED ITSELF OFF
    while every log line still claimed it was armed.
    """
    rows: dict = {}
    end = None
    for _ in range(6):
        u = (f"https://api.binance.com/api/v3/klines?symbol={symbol}"
             f"&interval=1h&limit=1000")
        if end is not None:
            u += f"&endTime={end}"
        try:
            raw = json.load(urllib.request.urlopen(u, timeout=25))
        except Exception as e:
            log(f"[{symbol}] deep klines failed: {type(e).__name__}: {str(e)[:70]}")
            break
        if not raw:
            break
        for k in raw:
            rows[int(k[0])] = k
        if len(rows) >= need:
            break
        end = int(raw[0][0]) - 1
    if len(rows) < need:
        return None
    raw = [rows[t] for t in sorted(rows)]
    d = pd.DataFrame(raw, columns=["t", "open", "high", "low", "close", "volume",
                                   "ct", "qv", "n", "tb", "tq", "ig"])
    for c in ("open", "high", "low", "close", "volume"):
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d["time"] = pd.to_datetime(d["t"], unit="ms")
    return d[["time", "open", "high", "low", "close",
              "volume"]].reset_index(drop=True)

def btc_bear(cache: dict) -> bool:
    """True while BTC's last CLOSED 1h bar is below its REGIME_MA-hour average. Cached
    per bar so one poll does not fetch BTC twelve times."""
    d = klines_deep("BTCUSDT", REGIME_MA + 100)
    if d is None or len(d) < REGIME_MA + 2:
        return cache.get("bear", False)
    closed = d.iloc[:-1]
    ma = closed["close"].rolling(REGIME_MA).mean().iloc[-1]
    bear = bool(closed["close"].iloc[-1] < ma) if np.isfinite(ma) else False
    cache["bear"] = bear
    return bear


def _ns(x):
    """Nanosecond resolution on pandas 2 (kline times arrive as datetime64[ms]); a no-op
    on pandas 1, where everything is already nanoseconds and as_unit does not exist."""
    return x.as_unit("ns") if hasattr(x, "as_unit") else x


def btc_breaks(cache: dict) -> "pd.Series | None":
    """BTC 4h trend-break flags for the TIGHT book, indexed like backtest/btc_exit.py:
    4h bars resampled from closed 1h bars, Wilder ATR(14), and a trailing reference that
    tracks the highest close since the last break. Recomputed once per closed BTC hour.

    Returns None if BTC history is unavailable; the tight book then treats the trigger
    as OFF, which makes it behave exactly like the main book - the safe failure."""
    d = klines_deep("BTCUSDT", 4000)
    if d is None or len(d) < 500:
        return cache.get("breaks")
    closed = d.iloc[:-1]
    key = str(closed["time"].iloc[-1])
    if cache.get("breaks_key") == key:
        return cache.get("breaks")
    b = resample(closed, "4h")
    c = b["close"].to_numpy(float)
    prev = np.roll(c, 1); prev[0] = np.nan
    tr = np.nanmax(np.vstack([b["high"] - b["low"], np.abs(b["high"] - prev),
                              np.abs(b["low"] - prev)]), axis=0)
    a = pd.Series(tr).ewm(alpha=1 / ATR_PERIOD, adjust=False).mean().to_numpy()
    best, flags = -np.inf, []
    for px, at in zip(c, a):
        best = max(best, px)
        broke = bool(np.isfinite(at) and px < best - BTC_TRAIL_K * at)
        flags.append(broke)
        if broke:
            best = px
    # nanosecond index: the kline times are datetime64[ms], and asof() with a
    # clock timestamp (ns) raises "Cannot losslessly convert units" otherwise
    s = pd.Series(flags, index=_ns(pd.DatetimeIndex(b["time"])))
    cache["breaks"], cache["breaks_key"] = s, key
    return s


def trig_at(breaks: "pd.Series | None", t) -> bool:
    """Was the most recent BTC 4h bar at or before t a trend break?"""
    if breaks is None or not len(breaks):
        return False
    t = _ns(pd.Timestamp(t))
    if t < breaks.index[0]:
        return False
    return bool(breaks.asof(t))


def bar_start(rule: str, bar_time) -> pd.Timestamp:
    """Start of a sleeve's bar as btc_exit.py defines it: 1h bars carry their open time;
    resampled bars carry their right edge, so their start is one rule earlier."""
    t = pd.Timestamp(bar_time)
    return t if rule == "1h" else t - pd.Timedelta(rule)


def runner_features(closed: pd.DataFrame, a_now: float, up_b: float):
    """The six frozen-model features at a long entry, from bars closed at/before it.
    Matches backtest/entry_runner.py exactly. Returns None if history is too short."""
    if len(closed) < 200:
        return None
    c = closed["close"].to_numpy(float); v = closed["volume"].to_numpy(float)
    a_ser = atr(closed).to_numpy(float)
    a_avg = np.nanmean(a_ser[-60:])
    v_avg = np.nanmean(v[-21:-1]) if len(v) >= 21 else np.nan
    ma200 = np.nanmean(c[-200:])
    return {
        "atr_expand": a_now / a_avg if a_avg and a_avg > 0 else 1.0,
        "ext_ma": c[-1] / ma200 if ma200 and ma200 > 0 else 1.0,
        "coin_30": c[-1] / c[-31] - 1 if len(c) >= 31 else 0.0,
        "coin_90": c[-1] / c[-91] - 1 if len(c) >= 91 else 0.0,
        "brk": (c[-1] - up_b) / a_now if a_now > 0 else 0.0,
        "vsurge": v[-1] / v_avg if v_avg and v_avg > 0 else 1.0}


def size_factor(feats: "dict | None") -> float:
    """Risk multiplier for a long from its runner-probability rank. 1.0 (neutral) if the
    features are unavailable, so a missing value can never quietly up-size a trade."""
    if feats is None:
        return 1.0
    z = RS_INTERCEPT
    for k, mu, sd, co in zip(RS_FEATS, RS_MEAN, RS_STD, RS_COEF):
        z += co * ((float(feats[k]) - mu) / sd if sd else 0.0)
    pct = float(np.interp(z, RS_ZGRID, RS_ZPCT)) / 100.0
    return float(np.clip(1.0 + RS_SPREAD * (pct - 0.5) * 2, *RS_CLIP))


def manage(st, key, rec, bar, hi, lo, a, tstop=False, cl=None, max_units=None):
    """One position against the bar that just closed.

    ORDER MATTERS. The stop is checked FIRST, against the level it已 held during this
    bar - the level set at the END of the previous bar. Only then does the trail
    advance off this bar's extreme. That is how a bar-close bot behaves and it is the
    convention every backtest in this project uses.
    """
    d = 1 if rec["side"] == "long" else -1
    # the entry bar's own extremes predate the position; never judge a stop on them
    if rec.get("entry_bar") == bar:
        return None
    rec["bars"] += 1
    breached = (lo <= rec["stop"]) if d == 1 else (hi >= rec["stop"])
    if breached:
        return rec["stop"]
    # TIME STOP - the tstop book only, and LONGS only, exactly as graveyard_rescore.walk
    # applies it: after the stop check and BEFORE any pyramid add, measured from the FIRST
    # entry, and filled at this bar's close. Shorts are untouched; the backtest never
    # applied it to them, so neither does this.
    if tstop and d == 1 and cl is not None and rec["bars"] >= TSTOP_BARS \
            and (cl - rec["entry"]) / rec["risk"] < TSTOP_R:
        log(f"[{key}] TIME STOP - {rec['bars']}b held, still "
            f"{(cl - rec['entry']) / rec['risk']:+.2f}R (< {TSTOP_R:g}R)")
        return cl
    # water mark, then trail, then the breakeven floor
    rec["water"] = (max(rec["water"], hi) if d == 1 else min(rec["water"], lo))
    gain_r = (rec["water"] - rec["entry"]) * d / rec["risk"]
    mu = MAX_UNITS if max_units is None else max_units
    if d > 0 and rec["units"] < mu:
        if gain_r >= rec["next_add"] * ADD_EVERY_R:
            used = sum(r.get("notional", 0) * r.get("units", 1)
                       for r in st["open"].values())
            if used + rec["notional"] <= st["equity"] * MAX_LEVERAGE:
                rec["units"] += 1
                rec.setdefault("adds", []).append(
                    rec["entry"] + (rec["units"] - 1) * ADD_EVERY_R * rec["risk"])
                rec["next_add"] += 1
                log(f"[{key}] PYRAMID unit {rec['units']}/{mu} at "
                    f"+{gain_r:.1f}R")
            elif not rec.get("lev_warned"):
                rec["lev_warned"] = True
                log(f"[{key}] PYRAMID BLOCKED at unit {rec['units']} — no margin")
    tm = LONG_TRAIL if d > 0 else SHORT_TRAIL
    if d > 0 and rec.get("tight"):
        tm = TIGHT_TRAIL                   # tight book only: BTC's 4h trend has broken
    cand = rec["water"] - d * tm * a
    if gain_r >= BE_AT_R:
        cand = max(cand, rec["entry"]) if d > 0 else min(cand, rec["entry"])
    if (cand > rec["stop"]) if d > 0 else (cand < rec["stop"]):
        rec["stop"] = cand
    return None


def cycle(st: dict, regime_cache: dict, kc: "dict | None" = None,
          tight: bool = False, breaks: "pd.Series | None" = None,
          bear: "bool | None" = None, sized: bool = False, sboost: bool = False,
          tstop: bool = False, units7: bool = False, triple: bool = False):
    """One pass over every coin and sleeve for ONE book.

    kc shares this poll's klines between the books, so the extra books add no API calls
    and all books always see the same bars; bear is passed in for the same reason.
    tight=True applies the BTC-break rule to open longs. sized=True scales each long's risk
    by the frozen runner-probability model. sboost=True scales a SHORT's risk by SBOOST_MULT
    when BTC's 4h trail is broken at its entry. tstop=True adds the time stop and is
    always passed WITH tight=True, because that book is tight + time stop. The main book
    sets none of them, so its behaviour is unchanged."""
    fee = FEE_BP / 1e4
    if bear is None:
        bear = btc_bear(regime_cache)
    # tstop is tested FIRST: that book also sets tight=True, so testing tight first
    # would file its trades in the tight book's CSV and label its logs as tight.
    # triple FIRST: it sets tstop and units7 too, and inferring the book from the
    # flags would file its trades in the units book's CSV.
    tag = ("3|" if triple else "U|" if units7 else "X|" if tstop else "T|" if tight
           else "S|" if sized else "B|" if sboost else "")
    trades_path = (TRIPLE_TRADES if triple else UNITS_TRADES if units7 else
                   TSTOP_TRADES if tstop else
                   TIGHT_TRADES if tight else
                   SIZED_TRADES if sized else SBOOST_TRADES if sboost else TRADES)
    kc = {} if kc is None else kc
    for base in BOOK:
        if base not in kc:
            kc[base] = klines(base)
        raw = kc[base]
        if raw is None or len(raw) < BARS_NEEDED // 2:
            continue
        for rule in SLEEVES:
            df = resample(raw, rule)
            if len(df) < BB_PERIOD + ATR_PERIOD + 5:
                continue
            closed = df.iloc[:-1]                  # never the forming bar
            bar = str(closed["time"].iloc[-1])
            key = f"{base}:{rule}"
            lkey = tag + key                       # log label only; state keys unchanged
            a = float(atr(closed).iloc[-1])
            px = float(closed["close"].iloc[-1])
            hi = float(closed["high"].iloc[-1])
            lo = float(closed["low"].iloc[-1])
            if not np.isfinite(a) or a <= 0:
                continue
            rec = st["open"].get(key)

            if rec:
                if st["last_bar"].get(key) == bar:
                    continue                       # once per closed bar, not per poll
                st["last_bar"][key] = bar
                if tight and rec["side"] == "long":
                    # btc_exit.py's rule, bar for bar: a break already on at entry does
                    # not count until it has switched off; after that, any break tightens
                    # the trail for good. Never on the entry bar itself.
                    on = trig_at(breaks, bar_start(rule, closed["time"].iloc[-1]))
                    if not on:
                        rec["armed"] = True
                    if on and rec.get("armed") and rec.get("entry_bar") != bar \
                            and not rec.get("tight"):
                        rec["tight"] = True
                        log(f"[{lkey}] BTC 4h trend broke -> trail {LONG_TRAIL:.0f}x -> "
                            f"{TIGHT_TRAIL:.0f}xATR ({rec.get('units', 1)}u)")
                exit_px = manage(st, lkey, rec, bar, hi, lo, a, tstop=tstop, cl=px,
                                 max_units=UNITS_MAX if units7 else None)
                if exit_px is None:
                    st["open"][key] = rec
                    continue
                d = 1 if rec["side"] == "long" else -1
                entries = [rec["entry"]] + rec.get("adds", [])
                R = sum((exit_px - e) * d - fee * e for e in entries) / rec["risk"]
                # ENTRY-SIZED, fixed 2026-09-23 (mistake #14, backtest/compounding.py).
                # A position's dollar risk is set at OPEN (risk_usd below) and does NOT grow
                # with profits other trades bank while it is open, because the bot never
                # resizes an open position. Crediting R as a FRACTION of equity at CLOSE did
                # let it grow, which roughly doubled every monthly figure in this repo.
                # Legacy positions opened before this fix carry no risk_usd; fall back to
                # the old behaviour for those rather than crash, and say so in the log.
                rusd = rec.get("risk_usd")
                if rusd is None:
                    rusd = st["equity"] * rec["risk_used"] / 100.0
                    log(f"[{lkey}] pre-fix position, no risk_usd - sizing off equity at "
                        f"close (old behaviour) for this one trade")
                st["equity"] += R * rusd
                log(f"[{lkey}] EXIT {rec['side']} R={R:+.2f} "
                    f"({rec.get('units',1)}u, {rec['bars']}b"
                    f"{', tightened' if rec.get('tight') else ''}) "
                    f"equity {st['equity']:.2f}")
                row = dict(
                    ts=f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}",
                    symbol=base, sleeve=rule, side=rec["side"],
                    entry=f"{rec['entry']:.8f}", exit=f"{exit_px:.8f}",
                    units=rec.get("units", 1), R=f"{R:+.4f}", bars=rec["bars"],
                    risk_pct=f"{rec['risk_used']:.3f}",
                    equity=f"{st['equity']:.2f}")
                if tight:
                    row["tightened"] = int(bool(rec.get("tight")))
                if sized:
                    row["size_fac"] = rec.get("size_fac", 1.0)
                if sboost:
                    row["boosted"] = rec.get("boosted", 0)
                rec_trade(row, trades_path)
                st["open"].pop(key, None)
                continue

            if st["last_bar"].get(key) == bar:
                continue
            st["last_bar"][key] = bar
            lo_b, up_b = bands(closed)
            if not (np.isfinite(up_b.iloc[-1]) and np.isfinite(lo_b.iloc[-1])):
                continue
            go_long = px > up_b.iloc[-1]
            go_short = px < lo_b.iloc[-1]
            if not (go_long or go_short):
                continue
            side = "long" if go_long else "short"
            d = 1 if go_long else -1
            if len(st["open"]) >= SLOTS:
                st["declined"] += 1
                if not tight:                      # the main book already says it
                    log(f"[{lkey}] {side.upper()} DECLINED — {SLOTS} slots full "
                        f"({st['declined']} so far)")
                continue
            # REGIME GATE: quarter risk while BTC is below its 200h average. Stored on
            # the position, because the risk that sized it is the risk that must be
            # used when it closes - reading the gate again at exit would apply a
            # different fraction to the same trade.
            risk_used = RISK_PCT * (REGIME_MULT if bear else 1.0)
            size_fac = 1.0
            if sized and d > 0:
                size_fac = size_factor(runner_features(closed, a, up_b.iloc[-1]))
                risk_used *= size_fac                # scales risk AND notional AND P&L
            boosted = 0
            if sboost and d < 0:
                # entry is at this bar's close = the start of the next bar, the same
                # convention the tight book's arming uses
                nxt = pd.Timestamp(closed["time"].iloc[-1]) + \
                    (pd.Timedelta(hours=1) if rule == "1h" else pd.Timedelta(0))
                if trig_at(breaks, nxt):
                    boosted = 1
                    size_fac = SBOOST_MULT
                    risk_used *= SBOOST_MULT
            risk = SL_MULT * a
            risk_usd = st["equity"] * risk_used / 100.0
            notional = risk_usd / (risk / px) if px > 0 else 0.0
            used = sum(r.get("notional", 0) * r.get("units", 1)
                       for r in st["open"].values())
            if used + notional > st["equity"] * MAX_LEVERAGE:
                st["no_margin"] += 1
                log(f"[{lkey}] {side.upper()} SKIPPED — no margin "
                    f"({st['no_margin']} so far)")
                continue
            floor = MIN_ORDER.get(base, 5.0)
            if notional < floor:
                st["too_small"] += 1
                log(f"[{lkey}] {side.upper()} SKIPPED — unit ${notional:.3f} below "
                    f"the ${floor:.3f} MEXC minimum (equity ${st['equity']:.2f}, "
                    f"stop {risk/px*100:.2f}%). {st['too_small']} so far")
                continue
            st["open"][key] = dict(side=side, entry=px, risk=risk,
                                   stop=px - d * risk,
                                   water=(hi if d > 0 else lo), bars=0, units=1,
                                   next_add=1, notional=notional,
                                   risk_used=risk_used, risk_usd=risk_usd,
                                   entry_bar=bar)
            if sized:
                st["open"][key]["size_fac"] = round(size_fac, 3)
            if sboost:
                st["open"][key]["boosted"] = boosted
            if tight and d > 0:
                # entry is at this bar's close = the start of the next bar
                nxt = pd.Timestamp(closed["time"].iloc[-1]) + \
                    (pd.Timedelta(hours=1) if rule == "1h" else pd.Timedelta(0))
                st["open"][key]["armed"] = not trig_at(breaks, nxt)
            st["taken"] += 1
            st[f"taken_{side}"] += 1
            log(f"[{lkey}] {side.upper()} @{px:.8g} stop {px-d*risk:.8g} "
                f"trail {LONG_TRAIL if d>0 else SHORT_TRAIL:.0f}xATR "
                f"unit ${notional:.2f} risk {risk_used:.3f}%"
                f"{f' size x{size_fac:.2f}' if sized and d > 0 else ''}"
                f"{f' BOOSTED x{SBOOST_MULT:.0f} (BTC trail broken)' if boosted else ''}"
                f"{' [BTC BEAR]' if bear else ''} "
                f"({len(st['open'])}/{SLOTS} slots, trade #{st['taken']})")


def status(st: dict, kc: "dict | None" = None):
    print(f"\nBLEND PAPER — {len(BOOK)} coins x {len(SLEEVES)} timeframes, "
          f"{SLOTS} shared slots")
    print(f"started {st.get('started','?')}")
    print(f"config: bb({BB_PERIOD},{BB_STD}) | long {LONG_TRAIL:.0f}xATR x{MAX_UNITS}u"
          f" | short {SHORT_TRAIL:.0f}xATR x1u | BE@{BE_AT_R:.0f}R | "
          f"risk {RISK_PCT}%/unit, x{REGIME_MULT} in BTC bear")
    eq = st["equity"]
    print(f"\nequity (realised) {eq:.2f}  ({eq/START_EQ*100-100:+.2f}%  "
          f"from ${START_EQ:.0f})")
    # Realised equity alone misleads while the book holds runners: losers stop out fast and get
    # banked, winners stay open for weeks and contribute nothing to the printed number. Over
    # the first 35 closed trades that made the record read -1.03R a trade while the profit sat
    # in 12 open positions at +4R to +8R peaks.
    try:
        u, sf, n, miss = mark_to_market(st, kc)
        print(f"equity (marked)   {eq + u:.2f}   = realised {eq:.2f} {u:+.2f} open, "
              f"at current prices")
        print(f"equity (floor)    {eq + sf:.2f}   if every open stop were hit right now"
              f"   [{n} priced{f', {miss} UNPRICED' if miss else ''}]")
    except Exception as e:
        print(f"equity (marked)   unavailable ({type(e).__name__})")
    print(f"entries {st['taken']} ({st.get('taken_long',0)}L/"
          f"{st.get('taken_short',0)}S)  declined(slots) {st['declined']}  "
          f"skipped(min order) {st.get('too_small',0)}  "
          f"skipped(margin) {st.get('no_margin',0)}")
    if st.get("too_small", 0) > max(st["taken"], 1):
        print("  >> the minimum order rejects more signals than it accepts:")
        print(f"     ${START_EQ:.0f} is too small for this config. That is the")
        print("     finding, not a bug.")
    print(f"open {len(st['open'])}/{SLOTS}")
    for k, r in sorted(st["open"].items()):
        print(f"  {k:<18} {r['side']:<5} entry {r['entry']:.6g} "
              f"stop {r['stop']:.6g} {r.get('units',1)}u {r['bars']}b")
    if TRADES.exists():
        d = pd.read_csv(TRADES)
        rs = pd.to_numeric(d["R"], errors="coerce").dropna()
        if len(rs):
            print(f"\nclosed {len(rs)}  mean R {rs.mean():+.3f}  total {rs.sum():+.2f}R"
                  f"  win {(rs>0).mean()*100:.0f}%  best {rs.max():+.2f}  "
                  f"worst {rs.min():+.2f}")
            for col in ("side", "sleeve"):
                if col in d.columns:
                    for v, g in d.groupby(col):
                        gr = pd.to_numeric(g["R"], errors="coerce").dropna()
                        if len(gr):
                            print(f"    {col:<7} {str(v):<6} n={len(gr):<4} "
                                  f"mean R {gr.mean():+.3f}  total {gr.sum():+.2f}R")
    print("\nexpect ~+8%/month and a LOSING month more often than not. 4 of 5 trades")
    print("lose; a handful of months carry the year. Any read under ~30 closed")
    print("trades is noise.\n")


def mark_to_market(st: dict, kc: "dict | None" = None):
    """What the open book is WORTH now, and the floor if every stop were hit.

    Equity moves only on CLOSES (entry-sized, mistake #14), so a book holding running winners
    reads far below its value: losers stop out fast and get banked, winners stay open for weeks
    and contribute nothing to the printed number. Over the first 35 closed trades that made the
    realised record look like -1.03R a trade while the profit sat in the 12 open positions.

    Returns (unrealised_now, unrealised_at_stops, n_priced, n_unpriced)."""
    kc = {} if kc is None else kc
    now = stop = 0.0
    priced = unpriced = 0
    for key, r in st["open"].items():
        base = key.split(":")[0]
        if base not in kc:
            kc[base] = klines(base, 3)
        d = kc[base]
        if d is None or not len(d):
            unpriced += 1
            continue
        px = float(d["close"].iloc[-1])
        sgn = 1 if r["side"] == "long" else -1
        entries = [r["entry"]] + r.get("adds", [])
        # dollars per price-unit = one unit's dollar risk / its price risk
        rusd = r.get("risk_usd") or st["equity"] * r.get("risk_used", RISK_PCT) / 100.0
        per = rusd / max(r["risk"], 1e-12)
        now += sum((px - e) * sgn for e in entries) * per
        stop += sum((r["stop"] - e) * sgn for e in entries) * per
        priced += 1
    return now, stop, priced, unpriced


def compare_books(name: str, bst: dict, st: dict, kc: "dict | None" = None):
    """Three-line comparison of a forked book against main: realised, marked and floor.

    All five books hold the same twelve coins, so ONE kline cache serves every call - pass the
    same dict through or this costs 60 requests instead of 12.

    Realised alone will understate every one of these books the moment they diverge, for the
    same reason it understates main: it moves on closes, and a book that holds its winners
    longer banks less sooner. The FLOOR is the honest comparison between exit rules, because it
    is what each book cannot fall below without a gap - and exit rules are exactly what tight,
    tstop and short-boost change."""
    kc = {} if kc is None else kc
    eq, meq = bst["equity"], st["equity"]
    print(f"  realised  {name} {eq:.2f}   main {meq:.2f}   difference {eq - meq:+.2f}")
    try:
        bu, bf, _bn, bmiss = mark_to_market(bst, kc)
        mu, mf, _mn, _mm = mark_to_market(st, kc)
        print(f"  marked    {name} {eq + bu:.2f}   main {meq + mu:.2f}   "
              f"difference {(eq + bu) - (meq + mu):+.2f}")
        print(f"  floor     {name} {eq + bf:.2f}   main {meq + mf:.2f}   "
              f"difference {(eq + bf) - (meq + mf):+.2f}"
              f"{f'   [{bmiss} UNPRICED]' if bmiss else ''}")
    except Exception as e:
        print(f"  marked/floor unavailable ({type(e).__name__})")


def status_tight(st: dict, tst: dict, kc: "dict | None" = None):
    """The TIGHT book next to the main one. Both forked from the same state, so the
    difference between them is the BTC-break rule and nothing else."""
    if not tst:
        print("TIGHT book: not started yet (it forks from this book on the first cycle)\n")
        return
    print(f"TIGHT BOOK - same signals; long trail {LONG_TRAIL:.0f}x -> {TIGHT_TRAIL:.0f}xATR "
          f"once BTC's 4h trend breaks ({BTC_TRAIL_K:.0f}xATR)")
    print(f"forked from the main book {tst.get('forked', '?')}")
    compare_books("tight", tst, st, kc)
    n_t = sum(1 for r in tst["open"].values() if r.get("tight"))
    print(f"  open {len(tst['open'])}/{SLOTS}, of which {n_t} on the tightened trail")
    for k, r in sorted(tst["open"].items()):
        m = st["open"].get(k)
        same = "same as main" if m and abs(m["stop"] - r["stop"]) < 1e-12 else \
            (f"main stop {m['stop']:.6g}" if m else "not open in main")
        print(f"    {k:<18} {r['side']:<5} stop {r['stop']:.6g} {r.get('units', 1)}u"
              f"{'  TIGHT' if r.get('tight') else ''}  ({same})")
    if TIGHT_TRADES.exists():
        d = pd.read_csv(TIGHT_TRADES)
        rs = pd.to_numeric(d["R"], errors="coerce").dropna()
        if len(rs):
            print(f"  closed since fork {len(rs)}  total {rs.sum():+.2f}R  "
                  f"win {(rs > 0).mean()*100:.0f}%")
    print("  A difference only appears after BTC breaks its 4h trend; until then the")
    print("  two books are identical by construction.\n")


def status_sized(st: dict, sst: dict, kc: "dict | None" = None):
    """The SIZED book next to the main one. Same signals; each new long's risk is scaled
    by its runner-probability (frozen model, mean 1), so it earns more per correct big
    winner without taking more total risk."""
    if not sst:
        print("SIZED book: not started yet (it forks from this book on the first cycle)\n")
        return
    print(f"SIZED BOOK - each long's risk x its runner-probability (frozen model, mean 1)")
    print(f"forked from the main book {sst.get('forked', '?')}")
    compare_books("sized", sst, st, kc)
    longs = [r for r in sst["open"].values() if r["side"] == "long"]
    facs = [r.get("size_fac", 1.0) for r in longs]
    print(f"  open {len(sst['open'])}/{SLOTS}; long size factors "
          f"{'min %.2f  mean %.2f  max %.2f' % (min(facs), sum(facs)/len(facs), max(facs)) if facs else 'n/a'}")
    for k, r in sorted(sst["open"].items()):
        print(f"    {k:<18} {r['side']:<5} stop {r['stop']:.6g} {r.get('units', 1)}u"
              f"{'  x%.2f' % r.get('size_fac', 1.0) if r['side'] == 'long' else ''}")
    if SIZED_TRADES.exists():
        d = pd.read_csv(SIZED_TRADES)
        rs = pd.to_numeric(d["R"], errors="coerce").dropna()
        if len(rs):
            print(f"  closed since fork {len(rs)}  total {rs.sum():+.2f}R  "
                  f"win {(rs > 0).mean()*100:.0f}%")
    print("  Books diverge as new longs are opened at non-1 sizes; a size <1 can fall")
    print("  below the MEXC minimum and be skipped - that interaction is the thing to watch.\n")


def fork_tight(st: dict, breaks) -> dict:
    """Start the tight book as an exact copy of the main book. Positions already open
    are armed only if no break is on right now - btc_exit.py's rule for a signal that
    was already on when the position began."""
    t = json.loads(json.dumps(st))
    t["forked"] = datetime.now(timezone.utc).isoformat()
    on = trig_at(breaks, pd.Timestamp.now(tz="UTC").tz_localize(None))
    for r in t["open"].values():
        if r["side"] == "long":
            r["armed"], r["tight"] = (not on), False
    return t


def status_sboost(st: dict, bst: dict, kc: "dict | None" = None):
    """The SHORT-BOOST book. Only shorts entered while BTC's 4h trail is broken differ, so
    the per-TRADE comparison in its trades file is the real evidence, not the equity gap."""
    if not bst:
        print("SHORT-BOOST book: not started yet (forks from the main book on the first cycle)\n")
        return
    print(f"SHORT-BOOST BOOK - a short's risk x{SBOOST_MULT:.0f} when BTC's 4h trail is broken")
    print(f"forked from the main book {bst.get('forked', '?')}")
    compare_books("boost", bst, st, kc)
    nb = sum(1 for r in bst["open"].values() if r.get("boosted"))
    print(f"  open {len(bst['open'])}/{SLOTS}, of which {nb} boosted shorts")
    if SBOOST_TRADES.exists():
        d = pd.read_csv(SBOOST_TRADES)
        d["R"] = pd.to_numeric(d["R"], errors="coerce")
        sh = d[(d["side"] == "short") & d["R"].notna()]
        if len(sh):
            flag = pd.to_numeric(sh.get("boosted", 0), errors="coerce").fillna(0)
            b, u = sh[flag == 1], sh[flag != 1]
            print(f"  shorts closed {len(sh)}: {len(b)} boosted, {len(u)} not")
            if len(b):
                print(f"    boosted mean R {b['R'].mean():+.3f} | un-boosted "
                      f"{u['R'].mean():+.3f}   (backtest said +0.481 vs +0.043)")
            else:
                print("    no boosted short has closed yet - that is the number to watch")
    print("  BTC's trail breaks roughly every two weeks, and only a short opened in that")
    print("  window is boosted - so expect long stretches with no difference at all.\n")


def fork_sized(st: dict) -> dict:
    """Start the sized book as an exact copy of the main book. Positions already open keep
    their sizes (size_fac 1.0) - only NEW longs after the fork are sized, so the two books
    diverge purely through the sizing rule going forward."""
    t = json.loads(json.dumps(st))
    t["forked"] = datetime.now(timezone.utc).isoformat()
    for r in t["open"].values():
        r.setdefault("size_fac", 1.0)
    return t


def fork_sboost(st: dict) -> dict:
    """Start the short-boost book as an exact copy of main; open shorts keep boosted=0, so
    only NEW shorts opened during a BTC break differ."""
    t = json.loads(json.dumps(st))
    t["forked"] = datetime.now(timezone.utc).isoformat()
    for r in t["open"].values():
        r.setdefault("boosted", 0)
    return t


def fork_triple(st: dict, breaks) -> dict:
    """Start the TRIPLE book - tight + time stop + 7 units - as a copy of the main book.

    With tight (#2), tight+timestop (#5), tight+units (#6) and this (#7) all running from the
    same ancestor, the four form a 2x2 factorial over {time stop, 7 units} on the tight base.
    That reads both main effects AND their interaction forward, which no single book can. The
    backtest says the interaction is positive: units adds +1.07%/mo on tight alone and +1.54 on
    tight + time stop (backtest/units_on_tstop.py)."""
    t = json.loads(json.dumps(st))
    t["forked"] = datetime.now(timezone.utc).isoformat()
    on = trig_at(breaks, pd.Timestamp.now(tz="UTC").tz_localize(None))
    for r in t["open"].values():
        if r["side"] == "long":
            r["armed"], r["tight"] = (not on), False
    return t


def status_triple(st: dict, rst: dict, kc: "dict | None" = None):
    """The TRIPLE book - the best configuration the backtests have produced, on paper."""
    if not rst:
        print("TRIPLE book: not started yet (forks from main on the first cycle)")
        print()
        return
    print(f"TRIPLE BOOK - tight exit + time stop (+{TSTOP_R:g}R/{TSTOP_BARS}b) + "
          f"{UNITS_MAX} pyramid units")
    print(f"forked from the main book {rst.get('forked', '?')}")
    compare_books("triple", rst, st, kc)
    deep = sum(1 for r in rst["open"].values() if r.get("units", 1) > MAX_UNITS)
    old = sum(1 for r in rst["open"].values()
              if r["side"] == "long" and r.get("bars", 0) >= TSTOP_BARS)
    print(f"  open {len(rst['open'])}/{SLOTS}, {deep} past {MAX_UNITS} units, "
          f"{old} long(s) old enough for the time stop")
    n = 0
    if TRIPLE_TRADES.exists():
        try:
            n = sum(1 for _ in open(TRIPLE_TRADES)) - 1
        except Exception:
            n = 0
    print(f"  {n} closed trades in {TRIPLE_TRADES.name}")
    print("  Backtest: +8.89%/mo tune, +10.76% holdout, against main's +4.88/+4.88 - the best")
    print("  config measured. Cost: drawdown 44->48% tune, 45->51% holdout against TSTOP alone.")
    print()


def fork_units(st: dict, breaks) -> dict:
    """Start the UNITS book (tight + a 7th unit) as an exact copy of the main book.

    Arming follows fork_tight exactly. Positions already open keep their unit counts, so a
    position sitting at 5 units when the fork happens can now add a 6th and 7th if it keeps
    running - which is correct: the rule is about how far a winner is allowed to go, and an
    inherited winner is still a winner."""
    t = json.loads(json.dumps(st))
    t["forked"] = datetime.now(timezone.utc).isoformat()
    on = trig_at(breaks, pd.Timestamp.now(tz="UTC").tz_localize(None))
    for r in t["open"].values():
        if r["side"] == "long":
            r["armed"], r["tight"] = (not on), False
    return t


def status_units(st: dict, ust: dict, kc: "dict | None" = None):
    """The UNITS book. Its evidence is per-TRADE: how many positions reach 6 or 7 units and what
    those units earn. The equity gap needs a runner to close before it says anything."""
    if not ust:
        print("UNITS book: not started yet (forks from main on the first cycle)")
        print()
        return
    print(f"UNITS BOOK - tight exit PLUS the pyramid runs to {UNITS_MAX} units, not {MAX_UNITS}")
    print(f"forked from the main book {ust.get('forked', '?')}")
    compare_books("units", ust, st, kc)
    deep = [(k, r) for k, r in ust["open"].items() if r.get("units", 1) > MAX_UNITS]
    longs = [(k, r) for k, r in ust["open"].items() if r["side"] == "long"]
    print(f"  open {len(ust['open'])}/{SLOTS}, {len(longs)} long, "
          f"{len(deep)} already past {MAX_UNITS} units")
    for k, r in sorted(deep):
        risk = r.get("risk", 0.0) or 1e-9
        print(f"    {k:<18} {r.get('units', 1)}u  peak "
              f"{(r.get('water', r['entry']) - r['entry']) / risk:>+5.1f}R")
    n = 0
    if UNITS_TRADES.exists():
        try:
            n = sum(1 for _ in open(UNITS_TRADES)) - 1
        except Exception:
            n = 0
    print(f"  {n} closed trades recorded in {UNITS_TRADES.name}")
    print("  A position only reaches unit 6 at +10R, so the first divergence needs a runner.")
    print()


def fork_tstop(st: dict, breaks) -> dict:
    """Start the TSTOP book (tight + time stop) as an exact copy of the main book.

    It forks from MAIN, not from the tight book, for the same reason every other book does:
    one common ancestor means every pair of books is comparable, and tight-vs-tstop is still
    readable because tight forked from the same place.

    Two things are inherited deliberately. The BTC-break arming follows fork_tight exactly -
    a break already on at the fork does not count until it has switched off. And the open
    positions keep the `bars` they have ALREADY accumulated in the main book, so a long that
    has been sitting for 300 bars is eligible for the time stop immediately rather than
    getting a free 100-bar reprieve for having been inherited. Resetting bars to 0 would
    quietly suppress the rule on exactly the stale positions it exists to close."""
    t = json.loads(json.dumps(st))
    t["forked"] = datetime.now(timezone.utc).isoformat()
    on = trig_at(breaks, pd.Timestamp.now(tz="UTC").tz_localize(None))
    for r in t["open"].values():
        if r["side"] == "long":
            r["armed"], r["tight"] = (not on), False
    return t


def status_tstop(st: dict, xst: dict, kc: "dict | None" = None):
    """The TSTOP book. Its evidence is the WORST MONTH and the drawdown, not the return -
    the return gain was holdout-only against tight alone (see TSTOP_BARS above)."""
    if not xst:
        print("TSTOP book: not started yet (forks from main on the first cycle)")
        print()
        return
    print(f"TSTOP BOOK - tight exit PLUS: close a long still under +{TSTOP_R:g}R after "
          f"{TSTOP_BARS} bars")
    print(f"forked from the main book {xst.get('forked', '?')}")
    compare_books("tstop", xst, st, kc)
    longs = [(k, r) for k, r in xst["open"].items() if r["side"] == "long"]
    print(f"  open {len(xst['open'])}/{SLOTS}, {len(longs)} long")
    # Show the PEAK R, because age alone reads as danger and is not. Units only accumulate
    # every ADD_EVERY_R, so a 5-unit position has been at least +8R and is a runner, not dead
    # money. The rule closes positions that are old AND went nowhere.
    #
    # The decision itself uses the CURRENT close, which this report cannot see without a
    # price fetch - so a runner that has retraced below +2R after 100 bars WOULD be closed.
    # Peak R tells you how far a position would have to give back to get there.
    for k, r in sorted(longs):
        px = r.get("entry", 0.0)
        age = r.get("bars", 0)
        risk = r.get("risk", 0.0) or 1e-9
        peak = (r.get("water", px) - px) / risk
        if age < TSTOP_BARS:
            flag = f"  too young by {TSTOP_BARS - age}b"
        elif peak < TSTOP_R:
            flag = "  <- AT RISK: old and never reached +2R"
        else:
            flag = f"  safe unless it gives back to +{TSTOP_R:g}R"
        print(f"    {k:<18} {age:>4}b  entry {px:<12.6g} {r.get('units', 1)}u  "
              f"peak {peak:>+6.1f}R{flag}")
    n = 0
    if TSTOP_TRADES.exists():
        try:
            n = sum(1 for _ in open(TSTOP_TRADES)) - 1
        except Exception:
            n = 0
    print(f"  {n} closed trades recorded in {TSTOP_TRADES.name}")
    print("  The backtest says to watch the WORST MONTH and the drawdown here, not the")
    print("  return: against tight alone the return gain was holdout-only, while the")
    print("  worst-month improvement showed on both halves.")
    print()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--once", action="store_true")
    args = ap.parse_args()
    st = load_state()
    tst = load_state(TIGHT_STATE) if TIGHT_STATE.exists() else None
    sst = load_state(SIZED_STATE) if SIZED_STATE.exists() else None
    bst = load_state(SBOOST_STATE) if SBOOST_STATE.exists() else None
    xst = load_state(TSTOP_STATE) if TSTOP_STATE.exists() else None
    ust = load_state(UNITS_STATE) if UNITS_STATE.exists() else None
    rst = load_state(TRIPLE_STATE) if TRIPLE_STATE.exists() else None
    if args.status:
        sc: dict = {}    # ONE kline cache for all five books, not 60 requests
        status(st, sc); status_tight(st, tst, sc); status_sized(st, sst, sc)
        status_sboost(st, bst, sc); status_tstop(st, xst, sc)
        status_units(st, ust, sc); status_triple(st, rst, sc); return
    log("=" * 78)
    log(f"BLEND PAPER — ${START_EQ:.0f}, {len(BOOK)} coins x {len(SLEEVES)} "
        f"timeframes, {SLOTS} shared slots")
    log(f"  sleeves {', '.join(SLEEVES)} | bb({BB_PERIOD},{BB_STD}) | "
        f"long {LONG_TRAIL:.0f}xATR x{MAX_UNITS}u every {ADD_EVERY_R}R | "
        f"short {SHORT_TRAIL:.0f}xATR x1u")
    log(f"  breakeven at +{BE_AT_R:.0f}R | risk {RISK_PCT}%/unit, "
        f"x{REGIME_MULT} while BTC < {REGIME_MA}h average")
    log(f"  per-coin MEXC minimum enforced | fee {FEE_BP}bp | simulated fills")
    log("  expectation ~+8%/month on recent data, 57.7% drawdown. PLAN AGAINST +8%,")
    log("  not the +12% full-history figure — 2021 carried 40% of lifetime profit.")
    log("  shorts are a HEDGE (-0.036R standalone); they earn their place by cutting")
    log("  drawdown, which raises compounded return.")
    log(f"  TIGHT book beside it: long trail -> {TIGHT_TRAIL:.0f}xATR once BTC's 4h trend "
        f"breaks ({BTC_TRAIL_K:.0f}xATR). {'resuming' if tst else 'forks on first cycle'}")
    log(f"  SIZED book beside it: each long's risk x its runner-probability (frozen model, "
        f"mean 1). {'resuming' if sst else 'forks on first cycle'}")
    log(f"  SHORT-BOOST book beside it: short risk x{SBOOST_MULT:.0f} while BTC's 4h trail "
        f"is broken. {'resuming' if bst else 'forks on first cycle'}")
    regime_cache: dict = {}
    brk_cache: dict = {}

    def one_poll():
        nonlocal tst, sst, bst, xst, ust, rst
        kc: dict = {}
        bear = btc_bear(regime_cache)
        # the MAIN book first, saved before the extra books are touched, so nothing in
        # their paths can cost the main book a cycle
        cycle(st, regime_cache, kc, bear=bear)
        save_state(st)
        try:
            breaks = btc_breaks(brk_cache)
            if tst is None:
                tst = fork_tight(st, breaks)
                log(f"TIGHT book forked from main: equity {tst['equity']:.2f}, "
                    f"{len(tst['open'])} open, BTC break on now: "
                    f"{trig_at(breaks, pd.Timestamp.now(tz='UTC').tz_localize(None))}")
            cycle(tst, regime_cache, kc, tight=True, breaks=breaks, bear=bear)
            save_state(tst, TIGHT_STATE)
        except Exception as e:
            log(f"TIGHT book error (main book unaffected): {type(e).__name__}: "
                f"{str(e)[:160]}")
        try:
            if sst is None:
                sst = fork_sized(st)
                log(f"SIZED book forked from main: equity {sst['equity']:.2f}, "
                    f"{len(sst['open'])} open")
            cycle(sst, regime_cache, kc, sized=True, bear=bear)
            save_state(sst, SIZED_STATE)
        except Exception as e:
            log(f"SIZED book error (main book unaffected): {type(e).__name__}: "
                f"{str(e)[:160]}")
        try:
            breaks = btc_breaks(brk_cache)
            if bst is None:
                bst = fork_sboost(st)
                log(f"SHORT-BOOST book forked from main: equity {bst['equity']:.2f}, "
                    f"{len(bst['open'])} open")
            cycle(bst, regime_cache, kc, sboost=True, breaks=breaks, bear=bear)
            save_state(bst, SBOOST_STATE)
        except Exception as e:
            log(f"SHORT-BOOST book error (main book unaffected): {type(e).__name__}: "
                f"{str(e)[:160]}")
        try:
            breaks = btc_breaks(brk_cache)
            if xst is None:
                xst = fork_tstop(st, breaks)
                stale = sum(1 for r in xst["open"].values()
                            if r["side"] == "long" and r.get("bars", 0) >= TSTOP_BARS)
                log(f"TSTOP book forked from main: equity {xst['equity']:.2f}, "
                    f"{len(xst['open'])} open, {stale} long(s) already past "
                    f"{TSTOP_BARS} bars and so eligible immediately")
            cycle(xst, regime_cache, kc, tight=True, tstop=True, breaks=breaks, bear=bear)
            save_state(xst, TSTOP_STATE)
        except Exception as e:
            log(f"TSTOP book error (main book unaffected): {type(e).__name__}: "
                f"{str(e)[:160]}")
        try:
            breaks = btc_breaks(brk_cache)
            if ust is None:
                ust = fork_units(st, breaks)
                log(f"UNITS book forked from main: equity {ust['equity']:.2f}, "
                    f"{len(ust['open'])} open, pyramid to {UNITS_MAX} units")
            cycle(ust, regime_cache, kc, tight=True, units7=True, breaks=breaks, bear=bear)
            save_state(ust, UNITS_STATE)
        except Exception as e:
            log(f"UNITS book error (main book unaffected): {type(e).__name__}: "
                f"{str(e)[:160]}")
        try:
            breaks = btc_breaks(brk_cache)
            if rst is None:
                rst = fork_triple(st, breaks)
                log(f"TRIPLE book forked from main: equity {rst['equity']:.2f}, "
                    f"{len(rst['open'])} open, tight + time stop + {UNITS_MAX} units")
            cycle(rst, regime_cache, kc, tight=True, tstop=True, units7=True, triple=True,
                  breaks=breaks, bear=bear)
            save_state(rst, TRIPLE_STATE)
        except Exception as e:
            log(f"TRIPLE book error (main book unaffected): {type(e).__name__}: "
                f"{str(e)[:160]}")

    if args.once:
        one_poll()
        sc: dict = {}    # ONE kline cache for all five books, not 60 requests
        status(st, sc); status_tight(st, tst, sc); status_sized(st, sst, sc)
        status_sboost(st, bst, sc); status_tstop(st, xst, sc)
        status_units(st, ust, sc); status_triple(st, rst, sc); return
    while True:
        try:
            one_poll()
            newest = max(st["last_bar"].values(), default=None)
            if newest and st["hb"].get("logged") != newest:
                st["hb"]["logged"] = newest
                log(f"alive | bar {newest} | equity {st['equity']:.2f} | "
                    f"{len(st['open'])}/{SLOTS} slots | taken {st['taken']} "
                    f"({st.get('taken_long',0)}L/{st.get('taken_short',0)}S) | "
                    f"declined {st['declined']} | too small {st.get('too_small',0)}"
                    + (f" | TIGHT {tst['equity']:.2f}" if tst else "")
                    + (f" | SIZED {sst['equity']:.2f}" if sst else "")
                    + (f" | BOOST {bst['equity']:.2f}" if bst else ""))
                save_state(st)
        except KeyboardInterrupt:
            log("stopped"); save_state(st); return
        except Exception as e:
            log(f"cycle error: {type(e).__name__}: {str(e)[:200]}")
        time.sleep(POLL_S)


if __name__ == "__main__":
    main()
