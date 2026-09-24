"""PAPER FORWARD TEST - THE CRASH BIDS (doc 16). PRE-REGISTERED.

Everything under PRE-REGISTERED is frozen. Changing it later and keeping the record would make
the test worthless.

WHAT THIS IS
    A $300 paper account that places resting buys under the price and sells them at the end of the
    hour - the rule doc 16 settled on - computed exactly, after each hour closes, from 1-minute
    candles. It places NO orders anywhere and needs no keys: Binance and Bitget public endpoints only.
      UNIVERSE  the top-40 USDT perps by the PRIOR calendar month's quote volume, listed >= 30 days,
                gold/fiat/stable perps excluded (mn_paper.py's own functions, TOP 40 of its list).
      BIDS      every hour, a buy 10% under the previous hour's close on each coin, 1/40 of the
                ledger's equity each. None on days BTC's 50-day label is BEAR (combo_paper.regime,
                the bear sleeve's label, known at the start of the day). Under $5 a bid is not placed.
      FILL      a 1-minute bar whose low goes 0.1% THROUGH the bid; the fill price is the lower of
                the bid and that minute's open (a gap opens below it).
      CAP       only the first 10 fills of the hour count; the rest are cancelled. Order = the
                minute of the fill, then the symbol alphabetically (a live bot sees fills in time
                order and cancels after the tenth; inside one minute the order is unknowable, so a
                fixed rule decides it).
      EXIT      the close of the hour's last minute. Costs per fill: 2bp maker in, 6bp taker out,
                30bp crash-hour slippage = 38bp (doc 15/16).
    Recorded beside it, not part of the rule: the same kept fills sold 120 minutes after the fill
    minute (doc 16 found it better on both halves, but only after looking), in its own $300 ledger.

TWO VENUES, ONE COIN LIST
    BINANCE  the venue the rule was found on: does the edge persist forward?
    BITGET   the venue the money would be on: does it exist there? The same 40 coins, mapped to
             Bitget's names (1000PEPEUSDT -> PEPEUSDT); a coin Bitget does not list is skipped there.
    Each venue has its own ledgers and its own prices, so the difference between them IS the venue.

WHAT IS DIFFERENT FROM THE BACKTEST, STATED SO IT CAN BE SUBTRACTED LATER
    1. 1-minute bars, not 5-minute: fills are ordered more finely for the cap.
    2. The universe is pre-filtered to the top 120 by 24h volume before the prior-month ranking
       (mn_paper.py caveat 1); the backtest ranked every perp.
    3. The +120 exit is the close of the 1-minute bar starting 120 minutes after the fill minute;
       the backtest used the 5-minute bar 120 minutes after the fill's 5-minute bar.

=============================== PRE-REGISTERED ===============================
FROZEN   top-40, bids 10% under the last close, 0.1% penetration, fill = min(bid, minute open),
         first 10 fills per hour, sold at the hour's close, 38bp per fill, 1/40 of equity per bid,
         $5 minimum, no bids on BEAR days, $300 start per ledger.
EXPECTED from the backtest on Binance (logs/wick_5m*.txt, the same rule; per KEPT fill after costs):
         last 2 years +1.05% (se 0.29), last 12 months +0.79% (se 0.38), 35-52 kept fills a month.
         Jan-Jun 2026 alone was NEGATIVE (-0.37% a fill); Jul-Sep 2026 +2.77%. A 6-month read has
         roughly 200-300 fills and a standard error near 0.6%, so it can only fail a dead edge.
H1  BITGET: the mean net return per kept fill (hour-close exit) is above zero.
H2  BINANCE: the same, above zero.
H3  Bitget has fewer fills than Binance BEFORE the cap (shallower wicks, doc 15; the replay found 35
    against 38 on 2025-10-10), and its mean per kept fill is not more than 0.5 points below Binance's.
H4  The worst hour's paper loss (every kept fill at its lowest price after the fill, summed, as a
    share of equity) never goes below -20% on either venue. The worst hour in six years, 2025-10-10
    21:00, reads -16.3% on Binance and -16.0% on Bitget on 1-minute bars (backtest/wick_replay.py;
    -15.8% on the backtest's 5-minute bars), so -20% means clearly worse than anything seen.
H5  The +120-minute ledger beats the hour-close ledger on both venues.
DECIDE AT  6 months from `started`, if Bitget has at least 60 kept fills; otherwise at 12 months.
         H1 false at 12 months = the crash bids are dropped. H4 false at any time = stop and report.
==============================================================================

    python wick_paper.py            run it (one process only)
    python wick_paper.py --status   read the book
    python wick_paper.py --once     process what is due, then exit (use --dir for a scratch copy)
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

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import combo_paper as cp  # noqa: E402  (regime: the bear sleeve's label, frozen there)
import mn_paper as mp  # noqa: E402     (universe functions)

START_EQ = 300.0
TOP_N = 40
BID_K = 0.10
PEN = 0.001
CAP_FILLS = 10
COST = 2e-4 + 6e-4 + 0.003
X_MIN = 120
MIN_ORDER = 5.0
CATCHUP_H = 72
H4_LIMIT = -0.20
POLL_S = 60
DELAY_S = 180                     # process an hour 3 minutes after it closes (final 1m candles)
HOUR_MS = 3_600_000
MIN_MS = 60_000
VENUES = ("bitget", "binance")
BG = "https://api.bitget.com/api/v2/mix/market"

P: dict = {}


def set_dir(d: Path):
    d.mkdir(parents=True, exist_ok=True)
    P.update(state=d / "wickp_state.json", log=d / "wick_paper.log", fills=d / "wickp_fills.csv",
             hours=d / "wickp_hours.csv", exits=d / "wickp_x120.csv", pid=d / "wick_paper.pid")
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


def ledger() -> dict:
    return dict(equity=START_EQ, eq120=START_EQ, peak=START_EQ, max_dd=0.0, kept=0, fills=0,
                sum_net=0.0, sum_net120=0.0, n120=0, worst_hour=0.0, worst_hour_at=None,
                skipped_small=0, missing=0, pending=[])


def fresh() -> dict:
    return dict(started=f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}", last_hour=None,
                universes={}, labels={}, bear_hours=0, hours=0, gaps=[],
                led={v: ledger() for v in VENUES})


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

def bitget_name(sym: str, listed: set) -> str | None:
    """Binance symbol -> Bitget's name for the same coin, or None if Bitget does not list it."""
    if sym in listed:
        return sym
    for pre in ("1000000", "1000"):
        if sym.startswith(pre) and sym[len(pre):] in listed:
            return sym[len(pre):]
        if pre + sym in listed:
            return pre + sym
    return None


def fill_of(bars: list, prev: float):
    """bars: the hour's 60 one-minute bars [t, o, h, l, c]. Returns (minute, fill, low_after, exit)
    for a bid BID_K under prev, or None. A touch does not fill a queued order: the low must go PEN
    through the bid."""
    bid = prev * (1 - BID_K)
    for j, (_, o, h, low, c) in enumerate(bars):
        if low < bid * (1 - PEN):
            f = min(bid, o)
            low_after = min(b[3] for b in bars[j:]) / f - 1
            return j, f, low_after, bars[-1][4]
    return None


def cap(fills: list) -> list:
    """The first CAP_FILLS fills of the hour by minute, then symbol. fills: dicts with minute, sym."""
    return sorted(fills, key=lambda x: (x["minute"], x["sym"]))[:CAP_FILLS]


def net(exit_px: float, fill: float) -> float:
    return exit_px / fill - 1 - COST


# ------------------------------------------------------------------ market data

def _get(url: str):
    for a in range(3):
        try:
            with urllib.request.urlopen(url, timeout=20) as r:
                return json.loads(r.read().decode())
        except Exception:
            if a == 2:
                return None
            time.sleep(1.5 * (a + 1))


def minutes(venue: str, sym: str, t0: int, n: int) -> list | None:
    """n one-minute bars starting at t0 (ms), as [t, o, h, l, c]; None unless ALL n are there."""
    if venue == "binance":
        d = _get(f"{mp.FAPI}/fapi/v1/klines?symbol={sym}&interval=1m&startTime={t0}&limit={n}")
        rows = [[int(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4])] for r in (d or [])]
    else:
        rows = []
        for ep in ("candles", "history-candles"):
            d = _get(f"{BG}/{ep}?symbol={sym}&productType=USDT-FUTURES&granularity=1m"
                     f"&startTime={t0 - 5 * MIN_MS}&endTime={t0 + n * MIN_MS}&limit=200")
            rows = [[int(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4])]
                    for r in ((d or {}).get("data") or [])]
            if rows:
                break
    want = {t0 + k * MIN_MS for k in range(n)}
    got = {r[0]: r for r in rows if r[0] in want}
    if len(got) != n:
        return None
    return [got[t] for t in sorted(got)]


def bitget_listed() -> set:
    d = _get(f"{BG}/contracts?productType=USDT-FUTURES")
    return {x["symbol"] for x in ((d or {}).get("data") or []) if x.get("symbolStatus") == "normal"}


def universe(month: str) -> list:
    """Raises rather than store a short list: a failed fetch must not become a month's universe."""
    syms, _ = mp.perp_universe()
    bars = mp.fetch_all(mp.candidates(syms))
    out = mp.eligible(bars, month)[:TOP_N]
    if len(out) < TOP_N:
        raise RuntimeError(f"universe {month}: only {len(out)} coins - retrying next poll")
    return out


def label(day: str) -> str:
    """The BTC label for `day`, from Binance daily closes up to the day before (combo_paper.regime).
    Raises rather than guess: an unknown label must not become a day with bids."""
    d = mp.daily("BTCUSDT", limit=150)
    closes = None if d is None else d[d.time < day].close.to_numpy(float)
    if closes is None or len(closes) < cp.REG_MA + cp.REG_SLOPE_D:
        raise RuntimeError(f"BTC daily closes unavailable for {day} - retrying next poll")
    return cp.regime(closes)


# ------------------------------------------------------------------ the book

def process_hour(st: dict, H: int, fetch=minutes, listed=None):
    """One closed hour [H, H + 1h). Bids from the previous close; kept fills sold at this hour's close."""
    ts = datetime.fromtimestamp(H / 1000, timezone.utc)
    month, day, hour = f"{ts:%Y-%m}", f"{ts:%Y-%m-%d}", f"{ts:%Y-%m-%d %H:00}"
    if month not in st["universes"]:
        st["universes"][month] = universe(month)
        log(f"UNIVERSE {month}: {len(st['universes'][month])} coins - "
            f"{' '.join(s[:-4] for s in st['universes'][month])}")
    if day not in st["labels"]:
        st["labels"][day] = label(day)
        log(f"DAY {day}: BTC label {st['labels'][day].upper()}"
            f"{' - no bids today' if st['labels'][day] == 'bear' else ''}")
    st["hours"] += 1
    if st["labels"][day] == "bear":
        st["bear_hours"] += 1
        for v in VENUES:
            append(P["hours"], dict(hour=hour, venue=v, bear=1, coins=0, fills=0, kept=0, pnl="0",
                                    paper_loss="0", equity=f"{st['led'][v]['equity']:.4f}",
                                    eq120=f"{st['led'][v]['eq120']:.4f}"))
        return
    coins = st["universes"][month]
    for v in VENUES:
        L = st["led"][v]
        size, size120 = L["equity"] / TOP_N, L["eq120"] / TOP_N
        if size < MIN_ORDER:
            L["skipped_small"] += 1
            continue
        found, n_coins = [], 0
        for s in coins:
            name = s if v == "binance" else (bitget_name(s, listed) if listed is not None else s)
            if name is None:
                continue
            bars = fetch(v, name, H - MIN_MS, 61)
            if bars is None:
                L["missing"] += 1
                continue
            n_coins += 1
            prev, hour_bars = bars[0][4], bars[1:]
            r = fill_of(hour_bars, prev)
            if r:
                j, f, low_after, exit_px = r
                found.append(dict(sym=name, minute=j, prev=prev, fill=f, low_after=low_after,
                                  exit=exit_px, t_fill=hour_bars[j][0]))
            time.sleep(0.03)
        kept = cap(found)
        keep_ids = {id(x) for x in kept}
        pnl = sum(size * net(x["exit"], x["fill"]) for x in kept)
        paper = sum(size * x["low_after"] for x in kept) / L["equity"]
        for rank, x in enumerate(sorted(found, key=lambda y: (y["minute"], y["sym"]))):
            k = id(x) in keep_ids
            append(P["fills"], dict(hour=hour, venue=v, sym=x["sym"], minute=x["minute"], rank=rank + 1,
                                    kept=int(k), prev=x["prev"], bid=f"{x['prev'] * (1 - BID_K):.10g}",
                                    fill=f"{x['fill']:.10g}", low_after=f"{x['low_after']:.5f}",
                                    exit=x["exit"], net=f"{net(x['exit'], x['fill']):.5f}",
                                    size=f"{size:.4f}" if k else "0"))
            if k:
                L["kept"] += 1
                L["sum_net"] += net(x["exit"], x["fill"])
                L["pending"].append(dict(sym=x["sym"], hour=hour, t_exit=x["t_fill"] + X_MIN * MIN_MS,
                                         fill=x["fill"], size=size120))
        L["fills"] += len(found)
        L["equity"] += pnl
        L["peak"] = max(L["peak"], L["equity"])
        L["max_dd"] = max(L["max_dd"], 1 - L["equity"] / L["peak"])
        if paper < L["worst_hour"]:
            L["worst_hour"], L["worst_hour_at"] = paper, hour
        append(P["hours"], dict(hour=hour, venue=v, bear=0, coins=n_coins, fills=len(found), kept=len(kept),
                                pnl=f"{pnl:.4f}", paper_loss=f"{paper:.5f}", equity=f"{L['equity']:.4f}",
                                eq120=f"{L['eq120']:.4f}"))
        if found:
            log(f"{hour} {v.upper():<7} {len(found)} filled, {len(kept)} kept: "
                f"{' '.join(x['sym'][:-4] for x in kept)} | P&L ${pnl:+.2f} -> ${L['equity']:.2f} | "
                f"in-hour paper loss {paper * 100:+.1f}%")
        if paper < H4_LIMIT:
            log(f"H4 BREACH on {v}: in-hour paper loss {paper * 100:.1f}% at {hour} - STOP AND REPORT")


def settle_x120(st: dict, now_ms: int, fetch=minutes):
    """Sell the +120-minute ledger's fills whose exit minute has closed."""
    for v in VENUES:
        L = st["led"][v]
        keep = []
        for p in L["pending"]:
            if p["t_exit"] + MIN_MS + DELAY_S * 1000 > now_ms:
                keep.append(p); continue
            b = fetch(v, p["sym"], p["t_exit"], 1)
            if b is None:
                if now_ms - p["t_exit"] < 24 * HOUR_MS:
                    keep.append(p); continue
                log(f"x120 {v} {p['sym']} {p['hour']}: no bar a day later - left out of the record")
                continue
            r = net(b[0][4], p["fill"])
            L["eq120"] += p["size"] * r
            L["sum_net120"] += r
            L["n120"] += 1
            append(P["exits"], dict(hour=p["hour"], venue=v, sym=p["sym"], exit=b[0][4], net=f"{r:.5f}",
                                    eq120=f"{L['eq120']:.4f}"))
        L["pending"] = keep


def due_hours(st: dict, now_ms: int) -> list:
    """Closed hours not yet processed. A gap longer than CATCHUP_H is recorded and skipped."""
    last_closed = (now_ms - DELAY_S * 1000) // HOUR_MS * HOUR_MS - HOUR_MS
    if st["last_hour"] is None:
        return [last_closed]
    nxt = st["last_hour"] + HOUR_MS
    if last_closed - nxt >= CATCHUP_H * HOUR_MS:
        st["gaps"].append([nxt, last_closed - CATCHUP_H * HOUR_MS])
        log(f"GAP: {(last_closed - nxt) // HOUR_MS} hours missed; the oldest beyond {CATCHUP_H}h are not replayed")
        nxt = last_closed - (CATCHUP_H - 1) * HOUR_MS
    return list(range(nxt, last_closed + 1, HOUR_MS))


def status(st: dict):
    days = (datetime.now(timezone.utc) - datetime.strptime(st["started"], "%Y-%m-%d %H:%M:%S")
            .replace(tzinfo=timezone.utc)).days
    print(f"\nCRASH-BID PAPER BOOK (pre-registered, doc 16; day {days} of ~182, verdict needs 60 Bitget fills)")
    print(f"  started {st['started']} UTC | hours processed {st['hours']} ({st['bear_hours']} on BEAR days, no bids)"
          f" | gaps {len(st['gaps'])}")
    for v in VENUES:
        L = st["led"][v]
        m = L["sum_net"] / L["kept"] * 100 if L["kept"] else float("nan")
        m2 = L["sum_net120"] / L["n120"] * 100 if L["n120"] else float("nan")
        print(f"  {v.upper():<8} hour-close ledger ${L['equity']:,.2f} ({(L['equity'] / START_EQ - 1) * 100:+.2f}%), "
              f"biggest fall {L['max_dd'] * 100:.1f}% | kept fills {L['kept']} of {L['fills']}, "
              f"mean {m:+.2f}% each (expected ~+0.8 to +1.0)")
        print(f"  {'':<8} +120-minute ledger ${L['eq120']:,.2f}, mean {m2:+.2f}% on {L['n120']} "
              f"({len(L['pending'])} still open) | worst in-hour paper loss {L['worst_hour'] * 100:+.1f}%"
              f"{' at ' + L['worst_hour_at'] if L['worst_hour_at'] else ''} (limit {H4_LIMIT * 100:.0f}%)")
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
                log(f"another wick_paper is already running (pid {old}). Exiting.")
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
    log("CRASH-BID PAPER BOOK - top-40, bids 10% under, no bids on BEAR days, first 10 fills per hour, "
        "sold at the hour's close; Bitget and Binance, $300 each")
    log(f"  PRE-REGISTERED: verdict at 6 months from {st['started']}. Places NO orders anywhere.")
    listed = None
    while True:
        try:
            now_ms = int(time.time() * 1000)
            hours = due_hours(st, now_ms)
            if hours:
                listed = bitget_listed() or listed
                if not listed:
                    raise RuntimeError("Bitget contract list unavailable")
            for H in hours:
                snap = json.dumps(st)            # an hour is booked whole or not at all
                try:
                    process_hour(st, H, listed=listed)
                except Exception:
                    st.clear(); st.update(json.loads(snap))
                    raise
                st["last_hour"] = H
                save(st)
            settle_x120(st, now_ms)
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
