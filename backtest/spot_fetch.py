"""BINANCE SPOT 2017-08 .. 2019-12 - the years the machine never saw, in the perps folder's format (2026-10-16)

The user, after final_confidence.py: "there must be a way that gives us a good confidence percentage - nobody can wait
this much". Every book was built and tuned on Binance perps (2019-09 on, most coins 2020+). Binance SPOT archives start
2017-08 and cover the 2017 top and the 2018 bear (-85%): two unseen years for an out-of-sample run of the FROZEN machine.
Downloads every */USDT spot pair's monthly 1d and 1h klines from data.binance.vision (public, free, no account) for
2017-08 .. 2019-12 into strategy_analysis/data/spot1719/ as SYM_1d.csv.gz / SYM_1h.csv.gz (time, open, high, low, close,
qvol) - the exact layout wide_book.eligibility and capitulation_wide.hourly read. No funding files (spot): the books'
funding cost reads as zero here, stated wherever a result is quoted. Stable / fiat / gold pairs are skipped
(market_neutral.NON_CRYPTO), and so are leveraged tokens (BULL / BEAR / UP / DOWN).

    python -m backtest.spot_fetch
"""
from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest.market_neutral import NON_CRYPTO  # noqa: E402
from backtest.perp_fetch import list_prefix, read_zip  # noqa: E402

OUT = ROOT / "strategy_analysis" / "data" / "spot1719"
MONTHS = [f"{y}-{m:02d}" for y in (2017, 2018, 2019) for m in range(1, 13) if f"{y}-{m:02d}" >= "2017-08"]
LEVERAGED = ("UPUSDT", "DOWNUSDT", "BULLUSDT", "BEARUSDT")


def symbols():
    dirs = list_prefix("data/spot/monthly/klines/", dirs=True)
    out = []
    for d in dirs:
        s = d.rstrip("/").split("/")[-1]
        if not s.endswith("USDT") or s.endswith(LEVERAGED) or s[:-4] in NON_CRYPTO:
            continue
        out.append(s)
    return sorted(out)


def one(sym):
    done = all((OUT / f"{sym}_{tf}.csv.gz").exists() for tf in ("1d", "1h"))
    if done or (OUT / f"{sym}.none").exists():
        return sym, "cached"
    got = {}
    for tf in ("1d", "1h"):
        keys = [k for k in list_prefix(f"data/spot/monthly/klines/{sym}/{tf}/") if k.split(f"-{tf}-")[1][:7] in MONTHS]
        rows = []
        for k in keys:
            r = read_zip(k)
            if r:
                rows += [(int(x[0]), float(x[1]), float(x[2]), float(x[3]), float(x[4]), float(x[7])) for x in r]
        if not rows:
            break
        d = pd.DataFrame(rows, columns=["t", "open", "high", "low", "close", "qvol"])
        d = d.drop_duplicates("t").sort_values("t").reset_index(drop=True)
        d.insert(0, "time", pd.to_datetime(d.pop("t"), unit="ms"))
        got[tf] = d
    if len(got) < 2:
        (OUT / f"{sym}.none").write_text("no 2017-08..2019-12 spot klines\n")
        return sym, "none"
    for tf, d in got.items():
        d.to_csv(OUT / f"{sym}_{tf}.csv.gz", index=False, compression="gzip")
    return sym, f"{len(got['1d'])} days"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    syms = symbols()
    print(f"{len(syms)} USDT spot pairs listed; fetching 2017-08 .. 2019-12", flush=True)
    n = 0
    with ThreadPoolExecutor(8) as ex:
        for s, msg in ex.map(one, syms):
            n += 1
            if msg not in ("none", "cached"):
                print(f"  {n}/{len(syms)} {s}: {msg}", flush=True)
    have = sorted(p.name.split("_")[0] for p in OUT.glob("*_1d.csv.gz"))
    print(f"done: {len(have)} coins with 2017-2019 spot data", flush=True)


if __name__ == "__main__":
    main()
