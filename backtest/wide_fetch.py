"""Download a wide crypto universe for the 100-coin cross-sectional test.

Picks the top N USDT perpetuals by 24h volume, keeps those that also have a SPOT
history (the existing pipeline and all prior results use spot klines, so mixing
sources would make the new numbers incomparable), and caches each via
mass_search.fetch.

LIQUIDITY NOTE: at rank ~120 a coin does ~$12M/day. That is ample for $50-500 of
capital but the spread is far wider than BTC's, so 6bp/side is optimistic for the
tail of this list. Everything downstream runs a 12bp sensitivity for that reason.

    python -m backtest.wide_fetch --n 120 --days 1500
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

# Windows console is cp1252 here. Binance lists perps with Chinese names
# (牛来USDT, 龙虾USDT, ...), and printing one killed a 90-minute download at coin
# 7 of 120 - the crash was in the ERROR HANDLER, not the fetch. A logging call
# must never be able to abort a long job.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.mass_search import DATA, fetch  # noqa: E402

SYMS = DATA / "wide_universe.json"


def top_perps(n: int) -> list[str]:
    t = json.load(urllib.request.urlopen(
        "https://fapi.binance.com/fapi/v1/ticker/24hr", timeout=30))
    ex = json.load(urllib.request.urlopen(
        "https://fapi.binance.com/fapi/v1/exchangeInfo", timeout=30))
    live = {s["symbol"] for s in ex["symbols"]
            if s.get("status") == "TRADING" and s.get("quoteAsset") == "USDT"
            and s.get("contractType") == "PERPETUAL"}
    # Drop non-ASCII symbols BEFORE slicing to n. An HTTP request line must be
    # ASCII-encodable (http.client does request.encode('ascii')), so these can
    # never be fetched - and they are perp-only meme listings with no spot
    # history regardless. Filtering first means n usable symbols, not n-4.
    rows = sorted(((float(x["quoteVolume"]), x["symbol"]) for x in t
                   if x["symbol"] in live and x["symbol"].isascii()),
                  reverse=True)
    return [s for _, s in rows[:n]]


def demultiplied(sym: str) -> str | None:
    """Map a 1000x perp contract to its spot pair: 1000SHIBUSDT -> SHIBUSDT.

    Binance quotes very-low-priced coins as 1000x or 1000000x perp contracts, but
    spot lists them plainly. Without this mapping SHIB, PEPE, BONK and FLOKI - all
    high-volume names - are dropped for a NAMING mismatch rather than for any lack
    of data. The multiplier is a contract convention; it cancels out of a return
    and therefore out of a ranking, so the spot series is the right substitute.
    """
    for p in ("1000000", "1000"):
        if sym.startswith(p) and len(sym) > len(p):
            return sym[len(p):]
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=120)
    ap.add_argument("--days", type=int, default=1500)
    ap.add_argument("--min-bars", type=int, default=9000)
    ap.add_argument("--supplement", action="store_true",
                    help="add spot equivalents of 1000x perp contracts to an "
                         "existing wide_universe.json")
    args = ap.parse_args()

    if args.supplement:
        have = set(json.load(open(SYMS))) if SYMS.exists() else set()
        added = []
        for s in top_perps(args.n):
            alt = demultiplied(s)
            if not alt or alt in have:
                continue
            try:
                d = fetch(alt, "1h", args.days)
            except Exception:
                print(f"  {s:16} -> {alt:14} no spot history", flush=True)
                continue
            if len(d) < args.min_bars:
                print(f"  {s:16} -> {alt:14} only {len(d):,} bars - skip",
                      flush=True)
                continue
            have.add(alt); added.append(alt)
            print(f"  {s:16} -> {alt:14} {len(d):>6,} bars  "
                  f"{d.time.min():%Y-%m-%d}", flush=True)
        json.dump(sorted(have), open(SYMS, "w"), indent=1)
        print(f"\nadded {len(added)}: {', '.join(added) or '(none)'}")
        print(f"universe now {len(have)} coins")
        return

    cands = top_perps(args.n)
    print(f"{len(cands)} candidate perps by volume; need >={args.min_bars} "
          f"hourly bars of SPOT history\n", flush=True)
    good, short, missing = [], [], []
    for i, s in enumerate(cands, 1):
        try:
            d = fetch(s, "1h", args.days)
        except Exception as e:
            missing.append(s)
            print(f"  {i:>3}/{len(cands)} {s:14} no spot history "
                  f"({type(e).__name__})", flush=True)
            continue
        n = len(d)
        if n < args.min_bars:
            short.append((s, n))
            print(f"  {i:>3}/{len(cands)} {s:14} only {n:>6,} bars - skip",
                  flush=True)
            continue
        good.append(s)
        print(f"  {i:>3}/{len(cands)} {s:14} {n:>6,} bars  "
              f"{d.time.min():%Y-%m-%d}", flush=True)

    json.dump(good, open(SYMS, "w"), indent=1)
    print(f"\nKEPT {len(good)} coins  (too short {len(short)}, "
          f"no spot data {len(missing)})")
    print(f"written to {SYMS}")


if __name__ == "__main__":
    main()
