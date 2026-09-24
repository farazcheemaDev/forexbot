"""PAPER FORWARD TEST - THE COMBINATION (doc 14 section 8). PRE-REGISTERED.

Everything under PRE-REGISTERED is frozen. Changing it later and keeping the record would make
the test worthless.

WHAT THIS IS
    One $221 paper account running the three books doc 14 measured together, on ONE balance:
      TREND   the triple (tight exit + time stop + 7 units), exactly blend_paper.py's own code
              (blend_paper.cycle with triple=True), sized by the 21-DAY EQUITY ANCHOR: each new
              position risks 0.30% of min(account equity, its 21-day average) - so a boom is not
              bet at once (doc 14 section 3, the one fix of 56 that beat "just bet smaller").
              Its gross guard is 9x, not 10x, because the MN book below adds 1x of gross.
      MN      the market-neutral momentum book (doc 10, mn_paper.py's own functions) at 1x of
              the account: top-60 PIT perps, long the 30-day top decile / short the bottom,
              rebalanced every 7 days, real funding.
      SLEEVE  the bear-market breadth sleeve (doc 13) at 1x: only on days BTC's 50-day regime
              is BEAR, long a 5-coin basket when <= 10% of the top 60 are above their 20-day
              average, short it when >= 28.8% are; each day's decision is 1/7 of the book held
              7 days, entered the day after the signal; orders under $5 are skipped.
    Backtest of this exact mix (backtest/max_mix.py, logs/max_mix_pick.txt, trend gains shrunk
    for hindsight): $221 -> typical $1,210 a year over 2020-26 against $592 for the triple alone
    at the same risk; last 2 years $1,125 against $530, biggest fall 45% against 58%.

WHY A SEPARATE FILE
    blend_paper.py's seven books are verified by sha256 on every VM deploy and belong to that
    process. This file IMPORTS its functions and never writes its state: the trend book's trades
    go to logs/trades_combo_trend.csv, and its log lines to logs/combo_paper.log (both patched in
    this process only). mn_paper.py is used the same way.

WHAT IS DIFFERENT FROM THE BACKTEST, STATED SO IT CAN BE SUBTRACTED LATER
    1. The anchor averages the WHOLE account's daily equity; the backtest averaged the trend
       book's own. With the other books present this is the natural live version.
    2. The trend book starts FLAT today; the triple paper book forked from main with positions.
       So the two differ in what they hold for the first weeks.
    3. The MN and sleeve universes use mn_paper's pre-filter (top 120 by 24h volume, then top 60
       by the prior month's volume) - slightly pessimistic, see mn_paper.py caveat 1.
    4. Funding for MN and the sleeve is counted from the previous daily close + 1 ms, so each
       settlement is counted once. (mn_paper.py counts from the previous bar's OPEN, which
       appears to count a day's settlements twice - flagged separately, not changed there.)

=============================== PRE-REGISTERED ===============================
FROZEN   K_MN = 1.0, K_SLEEVE = 1.0, anchor 21 days, trend gross guard 9x, sleeve thresholds
         0.100 / 0.288, 7-day ladder, 5-coin basket, $5 minimum, 12bp round trip.
H1  After 6 months the combination's equity is above the triple paper book's growth over the
    same days (blend_state_triple.json, measured as a multiple of its value on this book's start).
H2  Its biggest fall over those 6 months is SMALLER than the triple book's.
H3  More of its months are up than the triple book's (backtest: 56% vs 39%).
H4  The three components' daily P&L are close to uncorrelated (|corr| < 0.3 each pair).
The sleeve is FLAT outside BEAR regimes; a 6-month window with no bear tests only TREND + MN,
and the verdict must say so.
DECIDE AT  6 months from `started`. No verdict earlier.
==============================================================================

    python combo_paper.py            run it (one process only)
    python combo_paper.py --status   read the book
    python combo_paper.py --once     one poll, then exit (use --dir for a scratch copy)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import blend_paper as bp  # noqa: E402
import mn_paper as mp  # noqa: E402

START_EQ = 221.0
K_MN = 1.0
K_SLEEVE = 1.0
ANCHOR_D = 21
TREND_LEV = 10.0 - K_MN
LOW, HIGH = 0.100, 0.288          # breadth20 terciles over every 2020-26 bear day (doc 13 section 5)
LADDER = 7
BASKET_N = 5
MIN_ORDER = 5.0
SIDE_FEE = 6.0 / 1e4              # 12bp round trip
REG_MA, REG_SLOPE_D, REG_TH = 50, 20, 0.02
POLL_S = 120
DAY_MS = 86_400_000

P: dict = {}                      # paths, set by set_dir()


def set_dir(d: Path):
    d.mkdir(parents=True, exist_ok=True)
    P.update(state=d / "combo_state.json", log=d / "combo_paper.log", marks=d / "combo_marks.csv",
             trend=d / "trades_combo_trend.csv", sleeve=d / "combo_sleeve.csv",
             mn=d / "combo_mn.csv", pid=d / "combo_paper.pid")
    # THIS PROCESS ONLY: the imported books write here, never into their own files
    bp.TRIPLE_TRADES = P["trend"]
    bp.LOGF = P["log"]
    bp.MAX_LEVERAGE = TREND_LEV
    mp.LOGF = P["log"]


def log(m: str):
    line = f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S} | {m}"
    print(line, flush=True)
    with open(P["log"], "a", encoding="utf-8") as f:
        f.write(line + "\n")


def append(path: Path, row: dict):
    new = not path.exists()
    with open(path, "a", encoding="utf-8", newline="") as f:
        if new:
            f.write(",".join(row) + "\n")
        f.write(",".join(str(v) for v in row.values()) + "\n")


def fresh() -> dict:
    return dict(started=f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}", equity=START_EQ,
                peak=START_EQ, max_dd=0.0, eq_hist=[], last_day=None, trend=bp.fresh(),
                mn=dict(weights={}, mark_px={}, base=0.0, last_rebal=None, n_rebal=0,
                        skipped_small=0),
                sleeve=dict(signals={}, hold={}, mark_px={}, skipped=0),
                last_fund_ms=None, cum=dict(trend=0.0, mn=0.0, sleeve=0.0, fees=0.0),
                triple_ref=None)


def load() -> dict:
    if P["state"].exists():
        try:
            s = json.loads(P["state"].read_text())
            for k, v in fresh().items():
                s.setdefault(k, v)
            return s
        except Exception:
            log("state unreadable - starting fresh")
    return fresh()


def save(st: dict):
    tmp = P["state"].with_suffix(".tmp")
    tmp.write_text(json.dumps(st, indent=1))
    os.replace(tmp, P["state"])


# ------------------------------------------------------------------ pure rules (tested offline)

def anchored(equity: float, eq_hist: list) -> float:
    """min(equity, mean of the last ANCHOR_D daily equity marks). Never above today's equity."""
    last = [e for _, e in eq_hist[-ANCHOR_D:]]
    return min(equity, float(np.mean(last))) if last else equity


def regime(closes: np.ndarray) -> str:
    """market_neutral.btc_regime on the LAST closed bar: bull / bear / chop from BTC's 50-day
    average and its 20-day slope. `closes` ends with yesterday's close, so the label is the
    one btc_regime (shifted a day) gives for today."""
    if len(closes) < REG_MA + REG_SLOPE_D:
        return "chop"
    ma = pd.Series(closes).rolling(REG_MA).mean().to_numpy()
    slope = ma[-1] / ma[-1 - REG_SLOPE_D] - 1
    if closes[-1] > ma[-1] and slope > REG_TH:
        return "bull"
    if closes[-1] < ma[-1] and slope < -REG_TH:
        return "bear"
    return "chop"


def breadth20(bars: dict, elig: list) -> float:
    """share of the eligible coins whose last close is above their own 20-day average."""
    up = n = 0
    for s in elig:
        d = bars.get(s)
        if d is None or len(d) < 20:
            continue
        c = d.close.to_numpy(float)
        n += 1
        up += int(c[-1] > c[-20:].mean())
    return up / n if n else float("nan")


def signal(reg: str, br: float) -> int:
    if reg != "bear" or not np.isfinite(br):
        return 0
    return 1 if br <= LOW else (-1 if br >= HIGH else 0)


def ladder_pos(signals: dict, today: str) -> float:
    """The position held TODAY: the mean of the previous LADDER days' decisions, today's own
    decision excluded (it is entered the day after it is made). Missing days count as 0."""
    t = pd.Timestamp(today)
    return sum(signals.get(f"{t - pd.Timedelta(days=k):%Y-%m-%d}", 0) for k in range(1, LADDER + 1)) / LADDER


def rebalance(hold: dict, want: dict, min_order: float = MIN_ORDER):
    """Move holdings toward want. A change under min_order is skipped, except a full close.
    Returns (new holdings, traded notional, skipped count)."""
    new, traded, skipped = dict(hold), 0.0, 0
    for s in set(hold) | set(want):
        cur, w = hold.get(s, 0.0), want.get(s, 0.0)
        if abs(w - cur) < 1e-9:
            continue
        if abs(w - cur) < min_order and not (w == 0.0 and cur != 0.0):
            skipped += 1
            continue
        traded += abs(w - cur)
        if w == 0.0:
            new.pop(s, None)
        else:
            new[s] = w
    return new, traded, skipped


# ------------------------------------------------------------------ the books

def trend_poll(st: dict, regime_cache: dict, brk_cache: dict):
    tr = st["trend"]
    base = anchored(st["equity"], st["eq_hist"])
    tr["equity"] = base                          # sizing AND the guard read this
    breaks = bp.btc_breaks(brk_cache)
    bear = bp.btc_bear(regime_cache)
    bp.cycle(tr, regime_cache, {}, tight=True, tstop=True, units7=True, triple=True,
             breaks=breaks, bear=bear)
    pnl = tr["equity"] - base                    # realised exits only (entry-sized R x risk_usd)
    if abs(pnl) > 1e-12:
        st["equity"] += pnl
        st["cum"]["trend"] += pnl
        log(f"TREND closed P&L {pnl:+.2f} -> account {st['equity']:.2f}")


def daily(st: dict):
    """Once per new daily close: mark MN and the sleeve, record equity, rebalance both."""
    syms, floors = mp.perp_universe()
    cand = mp.candidates(syms)
    bars = mp.fetch_all(cand)
    btc = mp.daily("BTCUSDT", limit=120)
    if len(bars) < 30 or btc is None or len(btc) < REG_MA + REG_SLOPE_D:
        log(f"daily: data incomplete ({len(bars)} symbols) - retry next poll")
        return
    day = f"{btc.time.iloc[-1] + pd.Timedelta(days=1):%Y-%m-%d}"   # the day now starting
    if st["last_day"] == day:
        return
    now_ms = int((btc.time.iloc[-1] + pd.Timedelta(days=1)).timestamp() * 1000)
    since = st["last_fund_ms"]
    closes = {s: float(d.close.iloc[-1]) for s, d in bars.items()}

    def fund(s):
        return mp.funding_since(s, since + 1) if since else 0.0

    # 1. mark the MN book (weights are fractions of its base, gross 1.0 at k = 1)
    mn = st["mn"]
    if mn["weights"] and mn["mark_px"]:
        pnl, gone = 0.0, []
        for s, w in mn["weights"].items():
            p0 = mn["mark_px"].get(s)
            if s not in closes or not p0:
                gone.append(s); continue
            pnl += mn["base"] * (w * (closes[s] / p0 - 1) - w * fund(s))
        for s in gone:
            mn["weights"].pop(s, None)
        st["equity"] += pnl; st["cum"]["mn"] += pnl
        if gone:
            log(f"MN: no fresh bar for {', '.join(gone)} - exited at last mark")
    # 2. mark the sleeve (signed dollar notionals)
    sl = st["sleeve"]
    if sl["hold"]:
        pnl, gone = 0.0, []
        for s, n in list(sl["hold"].items()):
            p0 = sl["mark_px"].get(s)
            if s not in closes or not p0:
                gone.append(s); sl["hold"].pop(s); continue
            r = closes[s] / p0 - 1
            pnl += n * r - n * fund(s)
            sl["hold"][s] = n * (1 + r)
        st["equity"] += pnl; st["cum"]["sleeve"] += pnl
        if gone:
            log(f"SLEEVE: no fresh bar for {', '.join(gone)} - exited at last mark")
    # 3. record the day's equity (the anchor and the verdict read this)
    st["eq_hist"].append([day, round(st["equity"], 6)])
    st["eq_hist"] = st["eq_hist"][-90:]
    st["peak"] = max(st["peak"], st["equity"])
    st["max_dd"] = max(st["max_dd"], 1 - st["equity"] / st["peak"])

    elig = mp.eligible(bars, f"{pd.Timestamp(day):%Y-%m}")
    # 4. MN rebalance every mp.HOLD_D days
    due = mn["last_rebal"] is None or (pd.Timestamp(day) - pd.Timestamp(mn["last_rebal"])).days >= mp.HOLD_D
    if due:
        tgt = mp.target(bars, elig)
        if tgt:
            per = K_MN * st["equity"] * 0.5 / max(sum(1 for x in tgt.values() if x > 0), 1)
            small = [s for s in tgt if per < floors.get(s, 5.0)]
            for s in small:
                tgt.pop(s)
            mn["skipped_small"] += len(small)
            c = mp.cost(mn["weights"], tgt) * K_MN * st["equity"]
            st["equity"] -= c; st["cum"]["fees"] += c
            mn.update(weights=tgt, base=K_MN * st["equity"], last_rebal=day, n_rebal=mn["n_rebal"] + 1)
            append(P["mn"], dict(day=day, n_elig=len(elig), longs=" ".join(s[:-4] for s, x in tgt.items() if x > 0),
                                 shorts=" ".join(s[:-4] for s, x in tgt.items() if x < 0),
                                 fee=f"{c:.4f}", equity=f"{st['equity']:.4f}"))
            log(f"MN REBALANCE #{mn['n_rebal']} | ${per:.2f}/position | fee ${c:.3f}")
    mn["mark_px"] = {s: closes[s] for s in mn["weights"] if s in closes}
    # 5. the sleeve: today's decision, then today's position from the previous 7 decisions
    reg = regime(btc.close.to_numpy(float))
    br = breadth20(bars, elig)
    s_today = signal(reg, br)
    sl["signals"][day] = s_today
    sl["signals"] = {k: v for k, v in sl["signals"].items()
                     if pd.Timestamp(k) > pd.Timestamp(day) - pd.Timedelta(days=30)}
    pos = ladder_pos(sl["signals"], day)
    basket = [s for s in elig if s in closes][:BASKET_N]
    want = {s: pos * K_SLEEVE * st["equity"] / len(basket) for s in basket} if pos and basket else {}
    new, traded, skipped = rebalance(sl["hold"], want)
    fee = traded * SIDE_FEE
    st["equity"] -= fee; st["cum"]["fees"] += fee
    sl["hold"], sl["skipped"] = new, sl["skipped"] + skipped
    sl["mark_px"] = {s: closes[s] for s in sl["hold"] if s in closes}
    st["last_fund_ms"] = now_ms
    st["last_day"] = day
    append(P["sleeve"], dict(day=day, regime=reg, breadth20=f"{br:.3f}", signal=s_today,
                             position=f"{pos:+.3f}", n_hold=len(sl["hold"]), traded=f"{traded:.2f}",
                             skipped=skipped, equity=f"{st['equity']:.4f}"))
    append(P["marks"], dict(day=day, equity=f"{st['equity']:.4f}", trend=f"{st['cum']['trend']:.4f}",
                            mn=f"{st['cum']['mn']:.4f}", sleeve=f"{st['cum']['sleeve']:.4f}",
                            fees=f"{st['cum']['fees']:.4f}", anchored=f"{anchored(st['equity'], st['eq_hist']):.4f}",
                            trend_open=len(st["trend"]["open"]), regime=reg, breadth20=f"{br:.3f}"))
    log(f"DAY {day} | account ${st['equity']:.2f} (max fall {st['max_dd']*100:.1f}%) | BTC regime {reg}, "
        f"breadth20 {br:.1%} -> sleeve signal {s_today:+d}, position {pos:+.2f} | "
        f"trend {len(st['trend']['open'])} open | MN {len(mn['weights'])} names")


def triple_ref() -> float | None:
    f = P["state"].parent / "blend_state_triple.json"
    if not f.exists():
        f = ROOT / "logs" / "blend_state_triple.json"
    try:
        return float(json.loads(f.read_text())["equity"])
    except Exception:
        return None


def status(st: dict):
    eq = st["equity"]
    days = (datetime.now(timezone.utc) - pd.Timestamp(st["started"]).tz_localize("UTC")).days
    print(f"\nCOMBINATION PAPER BOOK (pre-registered, verdict at 6 months; day {days} of ~182)")
    print(f"  started   {st['started']} UTC")
    print(f"  account   ${eq:,.2f}  ({(eq / START_EQ - 1) * 100:+.2f}% from ${START_EQ:g}),"
          f" biggest fall so far {st['max_dd'] * 100:.1f}%")
    c = st["cum"]
    print(f"  made by   trend ${c['trend']:+.2f} | market-neutral ${c['mn']:+.2f} | "
          f"bear sleeve ${c['sleeve']:+.2f} | fees ${-c['fees']:+.2f}")
    print(f"  trend     {len(st['trend']['open'])} open, {st['trend']['taken']} taken, sized on "
          f"${anchored(eq, st['eq_hist']):.2f} (21-day anchor)")
    mn = st["mn"]
    print(f"  MN        {mn['n_rebal']} rebalances, last {mn['last_rebal']}, {len(mn['weights'])} names")
    sl = st["sleeve"]
    last = sorted(sl["signals"].items())[-1] if sl["signals"] else None
    print(f"  sleeve    last decision {last}, holding {len(sl['hold'])} coins "
          f"(${sum(sl['hold'].values()):+.2f} net), {sl['skipped']} orders skipped under $5")
    ref = triple_ref()
    if st.get("triple_ref") and ref:
        print(f"  vs triple paper book over the same days: combo x{eq / START_EQ:.3f} | triple "
              f"x{ref / st['triple_ref']:.3f}")
    print()


def single_instance():
    if P["pid"].exists():
        try:
            old = int(P["pid"].read_text().strip())
        except Exception:
            old = None
        if old and old != os.getpid():
            if os.name == "nt":
                # NEVER os.kill here: on Windows os.kill(pid, 0) TERMINATES that process.
                # Ask PowerShell, read-only, whether the pid is a python process.
                import subprocess
                r = subprocess.run(["powershell", "-NoProfile", "-Command",
                                    f"(Get-Process -Id {old} -ErrorAction SilentlyContinue).ProcessName"],
                                   capture_output=True, text=True)
                alive = "python" in (r.stdout or "").lower()
            else:
                try:
                    os.kill(old, 0)              # POSIX: signal 0 only checks existence
                    alive = True
                except OSError:
                    alive = False
            if alive:
                log(f"another combo_paper is already running (pid {old}). Exiting.")
                sys.exit(1)
    P["pid"].write_text(str(os.getpid()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--dir", default=str(ROOT / "logs"), help="state/log directory (scratch for tests)")
    args = ap.parse_args()
    set_dir(Path(args.dir))
    st = load()
    if args.status:
        status(st); return
    single_instance()
    if st.get("triple_ref") is None:
        st["triple_ref"] = triple_ref()
    log("COMBINATION PAPER BOOK - trend (triple + 21d anchor, 9x guard) + market-neutral 1x "
        "+ bear breadth sleeve 1x, one $221 account")
    log(f"  PRE-REGISTERED: verdict at 6 months from {st['started']}. Places NO orders anywhere.")
    regime_cache, brk_cache = {}, {}
    while True:
        try:
            today = f"{datetime.now(timezone.utc):%Y-%m-%d}"
            if st["last_day"] != today:
                daily(st)
                save(st)
            trend_poll(st, regime_cache, brk_cache)
            save(st)
        except KeyboardInterrupt:
            save(st); log("stopped"); return
        except Exception as e:
            log(f"poll error: {type(e).__name__}: {str(e)[:200]}")
        if args.once:
            return
        time.sleep(POLL_S)


if __name__ == "__main__":
    main()
