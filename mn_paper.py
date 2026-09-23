"""PAPER FORWARD TEST - the market-neutral book from backtest/market_neutral.py. PRE-REGISTERED.

Everything under PRE-REGISTERED is frozen. Read it before looking at a single result;
changing it later and keeping the accumulated record would make this test worthless.

WHY THIS EXISTS
    backtest/market_neutral.py found the first thing in this project that is genuinely
    uncorrelated with the deployed trend book: correlation +0.092 over 337 overlapping
    weeks, Sharpe 1.16, and a 75/25 mix that LOWERS drawdown while taking the weekly win
    rate from 32% to 53% (backtest/combine.py, doc 10).

    It is a backtest. The holdout it was measured against is mined out (CLAUDE.md), so the
    only evidence that can still move the question is data that did not exist when the
    result was found. This generates that data.

WHY IT IS A SEPARATE FILE AND NOT A FIFTH BOOK INSIDE blend_paper.py
    blend_paper.py runs four books off one 12-coin hourly signal engine, and its main book
    is verified byte-identical at every step. This book shares nothing with it: a 60-coin
    point-in-time universe, daily bars, weekly rebalancing, dollar-neutral baskets, and
    funding as a first-class return source. Bolting it on would risk the one book whose
    integrity matters most, for no gain.

    It is ALSO not a modification of xs_paper.py. That file is a pre-registered test of a
    21-coin daily-rebalanced book with its own frozen parameters and its own accumulated
    record; editing it to today's config would void that record. Different config, new file.

WHAT IS DIFFERENT FROM THE BACKTEST, STATED SO IT CAN BE SUBTRACTED LATER
    1. UNIVERSE PRE-FILTER. The backtest ranked the point-in-time top 60 by the prior
       calendar month's volume out of all 855 perps, including the 339 now dead. Live, that
       would be ~500 daily-kline requests per refresh. Instead the candidate set is the top
       120 by 24h quote volume (one /ticker/24hr call), and the top 60 by PRIOR MONTH's
       volume is taken from within it. Direction of the bias: it can only drop a coin whose
       volume has recently collapsed, and collapsed-volume coins are disproportionately
       SHORT candidates - so this makes the test slightly PESSIMISTIC, not optimistic.
    2. NO SLIPPAGE. 12bp is charged on turnover, matching the backtest. Real taker slippage
       in the 60 most liquid perps is a few bp per side on $18 clips; not modelled.
    3. FILLS ASSUMED. Marks and rebalances use daily closes. At $18 a position that is
       realistic, but no order has been placed, here or anywhere.

=============================== PRE-REGISTERED ===============================
H1  Net return over the test is positive.
H2  Realised correlation with blend_paper's main book stays below +0.30, as the backtest's
    +0.092 predicts. This is the claim that actually matters - the return is secondary to
    whether the two books are independent.
H3  The book earns in a BTC bear as well as a bull, though the backtest says a bear will be
    roughly breakeven (+0.244%/wk) and that its bear return is FUNDING, not momentum: the
    momentum spread's gross return was negative in bears in every variant tested.

SUCCESS  n >= 26 rebalances (6 months) with net > 0 AND realised correlation to the main
         book < +0.30. A positive return at high correlation is a FAIL - it would mean this
         is the trend book wearing a different hat, which is the one thing it must not be.
DECIDE AT  n = 26 rebalances. No verdict earlier; a verdict read early is fitted to noise.
UNIVERSE  gold-backed and fiat/stable perps excluded by category (NON_CRYPTO), decided
         before the first mark. This also improves the backtest (+1.130% -> +1.222%/wk),
         which is disclosed rather than presented as the reason.
NO LEVERAGE  gross 1.0x only. The backtest's Sharpe is what justifies this book; levering it
         is a separate decision that needs its own evidence.
==============================================================================

    python mn_paper.py            run it
    python mn_paper.py --status   read the book
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
LOGS = ROOT / "logs"
LOGS.mkdir(exist_ok=True)
STATE = LOGS / "mnp_state.json"
MARKS = LOGS / "mnp_marks.csv"
REBAL = LOGS / "mnp_rebalances.csv"
LOGF = LOGS / "mn_paper.log"
PIDF = LOGS / "mn_paper.pid"

# ----------------------------- frozen parameters -----------------------------
FAPI = "https://fapi.binance.com"
START_EQ = 221.0          # same as the other paper books, so they are directly comparable
TOP_N = 60                # point-in-time universe size (backtest: PIT top-60)
CAND_N = 120              # candidate pool by 24h volume, see caveat 1 above
LOOK_D = 30               # momentum lookback in days
HOLD_D = 7                # rebalance period in days
FRAC = 0.10               # decile each side -> k = max(int(60*0.10), 3) = 6 per side
MIN_AGE_D = 30            # a coin must have been listed this long to be eligible
FEE_BP = 12.0             # charged on turnover; see cost() for how turnover is defined
RUIN_AT = 0.10            # close the book below this fraction of start
POLL_S = 900              # 15 min. The book only moves on a new daily close; this keeps
                          # the state file's mtime fresh so health.py sees a pulse.
NEED_BARS = LOOK_D + 45   # 30d momentum + a prior calendar month of volume + margin

# Excluded by CATEGORY - see backtest.market_neutral.NON_CRYPTO for the full argument and
# for the disclosure that this also improves the backtest. Matched on the exact base asset,
# because a substring filter deletes VETUSDT ("TUSD") and UBUSDT ("BUSD").
#
# Found by RUNNING this file: the very first basket it built shorted PAXG and XAUT together,
# which is two of six short slots on one claim on physical gold. Decided before any record
# accumulated, which is the only honest moment to decide it.
NON_CRYPTO = {"PAXG", "XAUT", "EUR", "GBP", "AEUR", "USDC", "TUSD", "BUSD", "FDUSD",
              "USDP", "DAI", "USD1", "USDE", "SUSDE"}


def log(m: str):
    line = f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S} | {m}"
    print(line, flush=True)
    with open(LOGF, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def get(url: str, tries: int = 3):
    for a in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=20) as r:
                return json.loads(r.read().decode())
        except Exception as e:
            if a == tries - 1:
                raise
            time.sleep(1.5 * (a + 1))
            _ = e
    return None


# ------------------------------- market data --------------------------------
def perp_universe() -> tuple[list[str], dict[str, float]]:
    """Currently listed USDT perpetuals, and each one's minimum order notional.

    A LIVE listing is point-in-time by construction - it is exactly the set tradable today,
    with no survivorship question. The survivorship problem in the BACKTEST was the opposite
    one: reconstructing a past universe without the coins that have since died."""
    info = get(f"{FAPI}/fapi/v1/exchangeInfo")
    syms, floors = [], {}
    for s in info.get("symbols", []):
        if (s.get("contractType") != "PERPETUAL" or s.get("status") != "TRADING"
                or s.get("quoteAsset") != "USDT"):
            continue
        n = s["symbol"]
        if n.startswith("BTCDOM") or "_" in n or n[:-4] in NON_CRYPTO:
            continue
        mn = 5.0
        for f in s.get("filters", []):
            if f.get("filterType") == "MIN_NOTIONAL":
                mn = float(f.get("notional", f.get("minNotional", 5.0)))
        syms.append(n)
        floors[n] = mn
    return syms, floors


def candidates(syms: list[str]) -> list[str]:
    """Top CAND_N by 24h quote volume, in ONE request. See caveat 1."""
    t = get(f"{FAPI}/fapi/v1/ticker/24hr")
    v = {r["symbol"]: float(r.get("quoteVolume", 0.0)) for r in t
         if r.get("symbol") in set(syms)}
    return sorted(v, key=lambda s: -v[s])[:CAND_N]


def daily(sym: str, limit: int = NEED_BARS) -> pd.DataFrame | None:
    """Daily klines. Drops the CURRENT, still-forming bar - a signal computed on a
    partial bar is a signal read from the future of that bar."""
    try:
        k = get(f"{FAPI}/fapi/v1/klines?symbol={sym}&interval=1d&limit={limit}")
    except Exception:
        return None
    if not k or len(k) < 2:
        return None
    d = pd.DataFrame(k, columns=["t", "o", "h", "l", "c", "v", "T", "q",
                                 "n", "tb", "tq", "ig"])
    d = pd.DataFrame({"time": pd.to_datetime(d.t.astype("int64"), unit="ms"),
                      "close": d.c.astype(float), "qvol": d.q.astype(float)})
    return d.iloc[:-1].reset_index(drop=True)          # last bar is still open


def funding_since(sym: str, since_ms: int) -> float:
    """Sum of funding rates settled since `since_ms`. Positive = longs paid shorts."""
    try:
        r = get(f"{FAPI}/fapi/v1/fundingRate?symbol={sym}&startTime={since_ms}&limit=100")
    except Exception:
        return 0.0
    return float(sum(float(x["fundingRate"]) for x in (r or [])))


# --------------------------------- the book ---------------------------------
def eligible(bars: dict[str, pd.DataFrame], month: str) -> list[str]:
    """Top TOP_N by the PRIOR calendar month's quote volume, listed >= MIN_AGE_D, with a
    close today and LOOK_D days ago.

    Selection reads only the past. The backtest version of this function once required a
    price at the END of the holding period, which silently excluded every coin delisted
    mid-hold - the exact coins the short leg exists for (CLAUDE.md, doc 10)."""
    prev = (pd.Timestamp(month + "-01") - pd.Timedelta(days=1)).strftime("%Y-%m")
    vol = {}
    for s, d in bars.items():
        if d is None or len(d) < LOOK_D + 2:
            continue
        age = (d.time.iloc[-1] - d.time.iloc[0]).days
        if age < MIN_AGE_D:
            continue
        m = d[d.time.dt.strftime("%Y-%m") == prev]
        if not len(m):
            continue
        vol[s] = float(m.qvol.sum())
    return sorted(vol, key=lambda s: -vol[s])[:TOP_N]


def target(bars: dict[str, pd.DataFrame], elig: list[str]) -> dict[str, float]:
    """Long top decile / short bottom decile by LOOK_D-day return. Equal dollars each side,
    gross 1.0x: longs sum to +0.5 of the account, shorts to -0.5."""
    mom = {}
    for s in elig:
        d = bars.get(s)
        if d is None or len(d) <= LOOK_D:
            continue
        a, b = float(d.close.iloc[-1 - LOOK_D]), float(d.close.iloc[-1])
        if a > 0 and b > 0:
            mom[s] = b / a - 1.0
    if len(mom) < 20:
        return {}
    order = sorted(mom, key=lambda s: mom[s])
    k = max(int(len(order) * FRAC), 3)
    w = {}
    for s in order[-k:]:
        w[s] = +0.5 / k
    for s in order[:k]:
        w[s] = -0.5 / k
    return w


def cost(old: dict, new: dict) -> float:
    """Fee on turnover. sum|dw| is 2.0 for a full replacement of the book, and the backtest
    charges FEE_BP once for a full replacement, so the divisor is 2."""
    keys = set(old) | set(new)
    gross = sum(abs(new.get(s, 0.0) - old.get(s, 0.0)) for s in keys)
    return FEE_BP / 1e4 * gross / 2.0


# --------------------------------- plumbing ---------------------------------
def fresh() -> dict:
    return dict(started=f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}",
                equity=START_EQ, weights={}, mark_px={}, last_bar=None, last_rebal=None,
                last_fund_ms=None, n_rebal=0, n_marks=0, dead=False,
                cum_gross=0.0, cum_fund=0.0, cum_cost=0.0, skipped_small=0)


def load() -> dict | None:
    if not STATE.exists():
        return None
    try:
        return json.loads(STATE.read_text())
    except Exception:
        return None


def save(st: dict):
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(st, indent=1))
    os.replace(tmp, STATE)


def append(path: Path, row: dict):
    new = not path.exists()
    with open(path, "a", encoding="utf-8", newline="") as f:
        if new:
            f.write(",".join(row) + "\n")
        f.write(",".join(str(v) for v in row.values()) + "\n")


def single_instance():
    """One book, one process. Two processes sharing a state file would each overwrite the
    other's equity and the record would be silently meaningless."""
    if PIDF.exists():
        try:
            old = int(PIDF.read_text().strip())
        except Exception:
            old = None
        if old and old != os.getpid():
            import subprocess
            r = subprocess.run(["powershell", "-NoProfile", "-Command",
                                f"(Get-Process -Id {old} -ErrorAction SilentlyContinue)"
                                f".ProcessName"], capture_output=True, text=True)
            if "python" in (r.stdout or "").lower():
                log(f"another mn_paper is already running (pid {old}). Exiting.")
                sys.exit(1)
    PIDF.write_text(str(os.getpid()))


# ---------------------------------- cycle -----------------------------------
def fetch_all(syms: list[str]) -> dict[str, pd.DataFrame]:
    out = {}
    for s in syms:
        d = daily(s)
        if d is not None and len(d) >= LOOK_D + 2:
            out[s] = d
        time.sleep(0.05)                      # pace it; the limit is 2400 weight/min
    return out


def cycle(st: dict):
    syms, floors = perp_universe()
    cand = candidates(syms)
    bars = fetch_all(cand)
    if len(bars) < 30:
        log(f"only {len(bars)} usable symbols - skipping this cycle")
        return
    ref = max((d.time.iloc[-1] for d in bars.values()))
    bar = pd.Timestamp(ref)
    key = f"{bar:%Y-%m-%d}"
    if st["last_bar"] == key:
        log(f"bar {key} already processed | equity {st['equity']:.2f} | "
            f"{len(st['weights'])} positions | rebal {st['n_rebal']}")
        return

    # ---- 1. mark the book on the new daily close ----------------------------
    w = st["weights"]
    if w and st["mark_px"]:
        rets, missing = {}, []
        for s, x in w.items():
            d = bars.get(s)
            p0 = st["mark_px"].get(s)
            if d is None or not p0:
                missing.append(s)
                continue
            rets[s] = float(d.close.iloc[-1]) / float(p0) - 1.0
        gross = sum(w[s] * rets[s] for s in rets)
        since = st.get("last_fund_ms") or int(bar.timestamp() * 1000) - 86400_000
        fnd = {s: funding_since(s, since) for s in w}
        # a long PAYS a positive funding rate, a short RECEIVES it
        carry = sum(-w[s] * fnd.get(s, 0.0) for s in w)
        st["equity"] *= (1.0 + gross + carry)
        st["cum_gross"] += gross
        st["cum_fund"] += carry
        st["n_marks"] += 1
        if missing:
            # A held coin with no fresh bar has been DELISTED or halted. Its last mark is
            # the fair exit (Binance settles a delisted perp near mark) - the same
            # convention the backtest uses. Drop it and log it; never silently ignore.
            log(f"    no fresh bar for {', '.join(missing)} - exiting at last mark")
            for s in missing:
                w.pop(s, None)
        append(MARKS, {"ts": f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}", "bar": key,
                       "gross": f"{gross:.8f}", "funding": f"{carry:.8f}",
                       "equity": f"{st['equity']:.4f}", "n": len(rets)})
        log(f"MARK {key} | gross {gross*100:+.3f}% funding {carry*100:+.3f}% "
            f"-> equity {st['equity']:.2f}")
        if st["equity"] <= RUIN_AT * START_EQ and not st["dead"]:
            st["dead"] = True
            log(f"RUINED - equity {st['equity']:.2f} <= {RUIN_AT:.0%} of start. Book closed.")
    st["last_bar"] = key
    st["last_fund_ms"] = int(bar.timestamp() * 1000)
    st["mark_px"] = {s: float(d.close.iloc[-1]) for s, d in bars.items()}
    if st["dead"]:
        return

    # ---- 2. rebalance every HOLD_D days ------------------------------------
    last = st.get("last_rebal")
    due = last is None or (bar - pd.Timestamp(last)).days >= HOLD_D
    if not due:
        nxt = HOLD_D - (bar - pd.Timestamp(last)).days
        log(f"  holding | {len(w)} positions | next rebalance in {nxt}d")
        return

    elig = eligible(bars, f"{bar:%Y-%m}")
    tgt = target(bars, elig)
    if not tgt:
        log(f"  no target basket (only {len(elig)} eligible) - staying as is")
        return

    # ---- 3. the venue minimum, enforced rather than assumed -----------------
    # doc 10 predicted this would be where the book breaks on a small account. Measure it.
    per = st["equity"] * 0.5 / max(len([x for x in tgt.values() if x > 0]), 1)
    small = [s for s in tgt if per < floors.get(s, 5.0)]
    if small:
        st["skipped_small"] += len(small)
        log(f"  ${per:.2f}/position is below the minimum for {len(small)} names "
            f"({', '.join(small[:4])}) - dropping them")
        for s in small:
            tgt.pop(s, None)
        if not tgt:
            log("  entire basket rejected by the venue minimum - book is flat")

    c = cost(w, tgt)
    st["equity"] *= (1.0 - c)
    st["cum_cost"] += c
    st["weights"] = tgt
    st["last_rebal"] = key
    st["n_rebal"] += 1
    longs = sorted([s for s, x in tgt.items() if x > 0])
    shorts = sorted([s for s, x in tgt.items() if x < 0])
    append(REBAL, {"ts": f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}", "bar": key,
                   "n_elig": len(elig), "n_long": len(longs), "n_short": len(shorts),
                   "cost_bp": f"{c*1e4:.2f}", "per_pos": f"{per:.2f}",
                   "equity": f"{st['equity']:.4f}"})
    log(f"REBALANCE #{st['n_rebal']} | {len(elig)} eligible | cost {c*1e4:.1f}bp | "
        f"${per:.2f}/position | equity {st['equity']:.2f}")
    log(f"    LONG  {', '.join(s.replace('USDT', '') for s in longs)}")
    log(f"    SHORT {', '.join(s.replace('USDT', '') for s in shorts)}")


def status(st: dict):
    eq = st["equity"]
    print(f"\nMARKET-NEUTRAL PAPER BOOK  (pre-registered, verdict at 26 rebalances)")
    print(f"  started        {st['started']} UTC")
    print(f"  equity         ${eq:,.2f}   ({(eq/START_EQ - 1)*100:+.2f}% from ${START_EQ:g})")
    print(f"  rebalances     {st['n_rebal']} of 26 needed for a verdict")
    print(f"  daily marks    {st['n_marks']}")
    print(f"  last bar       {st['last_bar']}    last rebalance {st['last_rebal']}")
    if st["dead"]:
        print("  STATUS         RUINED - book closed")
    print(f"\n  return decomposition, summed over the test")
    print(f"    momentum spread {st['cum_gross']*100:+8.3f}%")
    print(f"    funding carry   {st['cum_fund']*100:+8.3f}%   "
          f"(the backtest says this IS the bear-market edge)")
    print(f"    fees           {-st['cum_cost']*100:+8.3f}%")
    if st["skipped_small"]:
        print(f"    names dropped for being below the venue minimum: {st['skipped_small']}")
    w = st["weights"]
    if w:
        lg = sorted([s for s, x in w.items() if x > 0])
        sh = sorted([s for s, x in w.items() if x < 0])
        per = eq * 0.5 / max(len(lg), 1)
        print(f"\n  {len(lg)} long / {len(sh)} short, ${per:.2f} each, gross 1.0x")
        print(f"    LONG  {', '.join(s.replace('USDT', '') for s in lg)}")
        print(f"    SHORT {', '.join(s.replace('USDT', '') for s in sh)}")
    else:
        print("\n  flat - no basket yet")
    print()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--once", action="store_true", help="one cycle, then exit")
    args = ap.parse_args()
    st = load() or fresh()
    if args.status:
        status(st)
        return
    single_instance()
    log("MARKET-NEUTRAL PAPER BOOK - forward test of backtest/market_neutral.py")
    log(f"  PIT top-{TOP_N} of the top-{CAND_N} by 24h volume | {LOOK_D}d momentum | "
        f"rebalance every {HOLD_D}d")
    log(f"  decile each side, gross 1.0x, ${START_EQ:g} start, {FEE_BP:g}bp on turnover, "
        f"real funding")
    log(f"  PRE-REGISTERED: verdict at 26 rebalances (now {st['n_rebal']}). Success needs "
        f"net > 0 AND correlation to the main book < +0.30.")
    while True:
        try:
            cycle(st)
            save(st)
        except KeyboardInterrupt:
            log("stopped")
            save(st)
            return
        except Exception as e:
            log(f"cycle error: {type(e).__name__}: {str(e)[:200]}")
        if args.once:
            return
        time.sleep(POLL_S)


if __name__ == "__main__":
    main()
