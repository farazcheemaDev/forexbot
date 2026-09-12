"""POINT-IN-TIME UNIVERSE — removing the last look-ahead from the headline result.

THE BIAS THIS ATTACKS
    The +256.9%/yr (+11.18%/month) figure was measured on nine coins: BTC, ETH,
    XRP, SOL, BNB, DOGE, ADA, AVAX, LINK. Those are the nine biggest coins TODAY.
    SOL and AVAX barely traded in 2020; coins that WERE top-10 then and later faded
    are absent entirely. So the result partly benefits from knowing in advance which
    names would go on to matter - a look-ahead in UNIVERSE CONSTRUCTION rather than
    in the signal, which is why none of the earlier causality fixes caught it.

    It is the same error as survivorship, one level up: not "which coins survived"
    but "which coins got big".

WHAT THIS DOES
    Ranks every available coin - ALIVE plus the 203 DELISTED ones - by realised
    dollar volume in each month, then trades only the top N as ranked by the PRIOR
    month. The universe therefore changes over time and contains whatever was
    actually liquid at the time, including coins that later died.

    Two comparisons matter:
        FIXED today's top 9   the number quoted so far (has the look-ahead)
        POINT-IN-TIME top 9   what you could actually have traded
    The gap is the hindsight premium in the headline figure.

WHY THIS MATTERS MORE THAN IT SOUNDS
    Trend-following is especially exposed to it. A coin enters "today's top 9"
    BECAUSE it trended enormously at some point, and this strategy's entire return
    comes from catching large trends. Selecting the universe on the outcome the
    strategy is trying to capture is close to circular.

    Prediction registered before running: the point-in-time return will be
    materially lower. If it stays above ~10%/month the finding is robust; if it
    collapses toward buy-and-hold (~40%/yr) then the headline was mostly hindsight.

    python -m backtest.pit_universe
    python -m backtest.pit_universe --top 9 --slots 8
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.convex import run_uncapped  # noqa: E402
from backtest.pyramid import run_pyramid  # noqa: E402
from backtest.twoside import short_trades  # noqa: E402
from backtest.mass_search import fetch, gen_signals  # noqa: E402
from bot.strategies.base import Action  # noqa: E402

DATA = Path(__file__).resolve().parents[1] / "strategy_analysis" / "data"
DEAD = DATA / "dead"
FEE_BP = 12.0
FAM, PARAMS = "bb_break", (30, 1.5)
TRAIL = float(__import__("os").environ.get("PIT_TRAIL","12.0"))
# Stop distance was FROZEN at 2.0 in every test until 2026-09-12. It is the
# DRAWDOWN dial: on the fixed universe, 2x->83% DD, 4x->58%, 6x->39%. That
# matters more than return for a small account, because an account that falls
# below ~$25 can no longer place a minimum-size order and is finished.
SL_MULT = float(__import__("os").environ.get("PIT_SL","2.0"))
# PYRAMIDING: units per position, added every PIT_ADD R of advance. 1 = the
# original one-unit engine. Risk-matched comparisons must divide risk_pct by the
# unit count, or the extra size is just leverage rather than a structural gain.
UNITS = int(__import__("os").environ.get("PIT_UNITS","1"))
ADD_EVERY = float(__import__("os").environ.get("PIT_ADD","2.0"))
# SHORT SLEEVE. Asymmetric by necessity: longs improve out to a 20xATR trail,
# shorts peak at 3-5x and go NEGATIVE at 20x, because up-moves grind and crashes
# are fast. Ungated beat the 200h-MA regime filter on every metric, so no filter.
SHORT_ON = __import__("os").environ.get("PIT_SHORT","0") == "1"
SHORT_TRAIL = float(__import__("os").environ.get("PIT_STRAIL","5.0"))
MIN_BARS = 600
FIXED9 = ["BTCUSDT", "ETHUSDT", "XRPUSDT", "SOLUSDT", "BNBUSDT",
          "DOGEUSDT", "ADAUSDT", "AVAXUSDT", "LINKUSDT"]

# Ranking by dollar volume pulls STABLECOINS into the top of the list - BUSD
# appeared in the 2020-06 top nine. A trend strategy cannot work on an asset
# pinned to $1: there is no trend, and a near-zero ATR makes the fee toll in R
# terms enormous (toll = fee x price / 2xATR). Left in, they silently burn slots
# that the cap makes scarce, biasing the point-in-time result DOWNWARD for a
# reason no real trader would accept. Excluded as a class.
STABLES = {"BUSDUSDT", "USDCUSDT", "TUSDUSDT", "DAIUSDT", "FDUSDUSDT",
           "PAXUSDT", "USDPUSDT", "USDSUSDT", "SUSDUSDT", "GUSDUSDT",
           "EURUSDT", "AEURUSDT", "USTUSDT", "USDEUSDT", "XUSDUSDT",
           "USD1USDT", "FRAXUSDT", "LUSDUSDT"}


def cached_days(sym: str) -> int | None:
    """Which cached history length exists for this symbol, if any.

    fetch(sym, '1h', N) DOWNLOADS when N does not match a cached file. Asking for
    2400 days against a universe cached at 1500 turned this loader into ~85 fresh
    multi-hundred-request downloads, and because every print happens after loading,
    it looked like a hang for 15 minutes. Check the cache instead of guessing.
    """
    for n in (2400, 1500, 1000, 900):
        if (DATA / f"{sym}_1h_{n}d.json").exists():
            return n
    return None


def load_all(verbose: bool = True) -> dict[str, pd.DataFrame]:
    """Every coin we have: alive (spot cache) plus delisted (archive)."""
    frames = {}
    files = sorted(DEAD.glob("*_1h.csv.gz"))
    for i, f in enumerate(files, 1):
        try:
            d = pd.read_csv(f, parse_dates=["time"])
        except Exception:
            continue
        if len(d) >= MIN_BARS and "volume" in d.columns:
            frames[f.name.split("_")[0]] = d
        if verbose and i % 50 == 0:
            print(f"  loaded {i}/{len(files)} delisted...", flush=True)
    try:
        alive = json.load(open(DATA / "wide_universe.json"))
    except Exception:
        alive = FIXED9
    want = sorted(set(alive) | set(FIXED9))
    miss = []
    for s in want:
        n = cached_days(s)
        if n is None:
            miss.append(s)
            continue
        try:
            d = fetch(s, "1h", n)
        except Exception:
            continue
        if d is not None and len(d) >= MIN_BARS:
            frames[s] = d
    if verbose:
        print(f"  loaded {len(files)} delisted + {len(want)-len(miss)} live "
              f"(skipped {len(miss)} uncached to avoid a download storm)",
              flush=True)
    return frames


def monthly_volume(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Realised dollar volume per coin per month. The ranking input."""
    cols = {}
    for s, d in frames.items():
        if "volume" not in d.columns:
            continue
        dv = (d["close"] * d["volume"]).groupby(
            pd.DatetimeIndex(d["time"]).to_period("M")).sum()
        cols[s] = dv
    return pd.DataFrame(cols).sort_index()


def trades_for(df: pd.DataFrame) -> list[tuple]:
    sig = gen_signals(df, FAM, PARAMS)
    if sig is None or int((sig != Action.HOLD).sum()) == 0:
        return []
    sig = sig.where(sig != Action.SELL, Action.HOLD)      # long only
    if UNITS > 1:
        R, idx, _u, bars = run_pyramid(df, sig, sl_mult=SL_MULT, trail=TRAIL,
                                       max_units=UNITS, add_every=ADD_EVERY,
                                       fee_bp=FEE_BP)
    else:
        R, idx, bars, _D = run_uncapped(df, sig, sl_mult=SL_MULT, fee_bp=FEE_BP,
                                        mode="trail_atr", trail=TRAIL,
                                        close_at_end="stop")
    t = df["time"].to_numpy()
    out = []
    for r, ix, nb in zip(R, idx, bars):
        ei = max(int(ix) - int(nb), 0)
        out.append((t[ei], t[int(ix)], float(r)))
    if SHORT_ON:
        # shorts share the same slots, so they compete with longs rather than
        # adding exposure on top - otherwise the comparison is just more risk
        out += [(a, b, r) for a, b, r, _s in
                short_trades(df, "all", SHORT_TRAIL)]
        out.sort(key=lambda x: x[0])
    return out


def simulate(frames, allowed_by_month, slots, risk_pct):
    """Portfolio pass, only entering a coin ELIGIBLE in the entry month."""
    allt = []
    for s, df in frames.items():
        for t_in, t_out, r in trades_for(df):
            allt.append((t_in, t_out, r, s))
    if not allt:
        return None
    allt.sort(key=lambda x: x[0])
    eq, curve, times, open_until = 1.0, [], [], []
    taken = skipped = ineligible = 0
    ruined = False
    f = risk_pct / 100.0
    for t_in, t_out, r, s in allt:
        if allowed_by_month is not None:
            per = pd.Timestamp(t_in).to_period("M")
            ok = allowed_by_month.get(per)
            if ok is None or s not in ok:
                ineligible += 1
                continue
        open_until = [u for u in open_until if u > t_in]
        if len(open_until) >= slots:
            skipped += 1
            continue
        open_until.append(t_out)
        taken += 1
        if not ruined:
            eq *= (1 + r * f)
            if eq <= 1e-9:
                eq, ruined = 0.0, True
        curve.append(eq); times.append(t_out)
    if taken < 30:
        return None
    cur = np.asarray(curve)
    peak = np.maximum.accumulate(np.maximum(cur, 1e-12))
    dd = float((1 - cur / peak).max() * 100)
    ts = pd.DatetimeIndex(times)
    yrs = max((ts[-1] - ts[0]).days / 365.25, 1e-9)
    cagr = (max(cur[-1], 0.0) ** (1 / yrs) - 1) * 100 if not ruined else -100.0
    mo = pd.Series(cur, index=ts).resample("30D").last().pct_change().dropna() * 100
    if ruined:
        mo = mo.iloc[:0]
    return dict(taken=taken, skipped=skipped, ineligible=ineligible,
                cagr=float(cagr), dd=dd, ruined=ruined,
                mar=float(cagr / dd) if dd > 0.5 else 0.0,
                mo_med=float(mo.median()) if len(mo) else float("nan"),
                mo_over10=float((mo > 10).mean() * 100) if len(mo) else float("nan"),
                per_month=(((1 + cagr / 100) ** (1 / 12) - 1) * 100
                           if cagr > -100 else -100.0))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=9)
    ap.add_argument("--slots", type=int, default=8)
    ap.add_argument("--start", default="2020-06",
                    help="first month to trade. REQUIRED for a fair test: the "
                         "dead-coin archive reaches back to 2017 while the live "
                         "caches begin 2020-02, so before then the point-in-time "
                         "universe can ONLY contain coins that later died - an "
                         "artifact of what was loaded, not of what was liquid. "
                         "BTC does not even appear before 2020-05.")
    args = ap.parse_args()
    start_per = pd.Period(args.start, freq="M")

    frames = load_all()
    dead_n = sum(1 for f in DEAD.glob("*_1h.csv.gz"))
    print(f"POINT-IN-TIME UNIVERSE   {len(frames)} coins loaded "
          f"({dead_n} delisted files on disk)")
    print(f"  {FAM}{PARAMS} 1h | LONG ONLY | trail {TRAIL}xATR | "
          f"{args.slots} slots | fee {FEE_BP}bp")

    vol = monthly_volume(frames)
    # eligible = top N by PRIOR month's dollar volume. shift(1) is the causality:
    # this month's ranking is not known until this month ends.
    ranked = vol.shift(1)
    allowed = {}
    for per, row in ranked.iterrows():
        if per < start_per:
            continue                  # see --start: pre-2020 is a coverage artifact
        r = row.dropna()
        r = r[~r.index.isin(STABLES)]        # see STABLES: cannot trend
        if len(r) >= args.top:
            allowed[per] = set(r.nlargest(args.top).index)
    # pandas Period does not accept strftime-style format specs; str() on a
    # monthly Period already yields "2020-08".
    if allowed:
        print(f"  {len(allowed)} months with a full top-{args.top} ranking "
              f"({min(allowed)} .. {max(allowed)})")

    # how much does the universe actually churn?
    if allowed:
        keys = sorted(allowed)
        names = set()
        for k in keys:
            names |= allowed[k]
        print(f"  {len(names)} distinct coins appeared in the point-in-time "
              f"top-{args.top} over time")
        overlap = len(set(FIXED9) & names)
        print(f"  {overlap}/{len(FIXED9)} of today's fixed nine ever appear in it")
        first, last = allowed[keys[0]], allowed[keys[-1]]
        print(f"  first month: {', '.join(sorted(s[:-4] for s in first))}")
        print(f"  last  month: {', '.join(sorted(s[:-4] for s in last))}\n")

    print("=" * 104)
    print(f"{'universe':<28} {'risk':>6} {'taken':>7} {'skip':>6} {'inelig':>7} "
          f"{'CAGR':>9} {'DD':>7} {'MAR':>6} {'/month':>8} {'mo>10%':>7}")
    fixed_frames = {s: frames[s] for s in FIXED9 if s in frames}
    # Restrict FIXED to the SAME months as point-in-time. Letting it trade the
    # whole history while point-in-time starts in 2020-06 would compare two
    # different periods and the "hindsight premium" would partly just be the
    # 2020-21 bull run that only one of them saw.
    fixed_allowed = {per: set(FIXED9) for per in allowed}
    for rk in (0.5, 1.0):
        d = simulate(fixed_frames, fixed_allowed, args.slots, rk)
        if d:
            print(f"{'FIXED todays top 9':<28} {rk:>5.2f}% {d['taken']:>7} "
                  f"{d['skipped']:>6} {d['ineligible']:>7} {d['cagr']:>+8.1f}% "
                  f"{d['dd']:>6.1f}% {d['mar']:>+6.2f} {d['per_month']:>+7.2f}% "
                  f"{d['mo_over10']:>6.1f}%")
    for rk in (0.5, 1.0):
        d = simulate(frames, allowed, args.slots, rk)
        if d:
            print(f"{'POINT-IN-TIME top '+str(args.top):<28} {rk:>5.2f}% "
                  f"{d['taken']:>7} {d['skipped']:>6} {d['ineligible']:>7} "
                  f"{d['cagr']:>+8.1f}% {d['dd']:>6.1f}% {d['mar']:>+6.2f} "
                  f"{d['per_month']:>+7.2f}% {d['mo_over10']:>6.1f}%")

    print("\nThe gap between the two rows is the HINDSIGHT PREMIUM in the headline "
          "figure.")
    print("Prediction registered before running: point-in-time is materially "
          "lower. If it\nholds above ~10%/month the finding is robust; if it "
          "falls toward buy-and-hold\n(~40%/yr) the headline was mostly knowing "
          "which coins would get big.")


if __name__ == "__main__":
    main()
