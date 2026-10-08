"""15-MINUTE BARS, LONG AND SHORT, ON 10,000 PKR - scalp_1m.py's test one timeframe up.

THE USER'S QUESTION (2026-10-08): "what about the 15 minute timeframe, both long and short?"

WHY IT COULD DIFFER FROM 1 MINUTE
    The fee is fixed per trade while the move grows with the bar: a 2xATR stop on 15m bars is several times wider than
    on 1m, so 12bp is a much smaller share of 1R. scalp_1m.py died mainly on that toll (0.98R / 0.50R a trade).

THE TEST (scalp_1m.py's machinery, reused - outcomes, rules, evaluate, odds_now's cells)
    Binance USDT-M perp 15m bars, BTC ETH SOL DOGE XRP, 2020-09 .. 2026-08 (data.binance.vision monthly archive,
    cached in strategy_analysis/data/min15/). Split 60/40 by time.
    Rules, each LONG and SHORT, signal at a closed bar, entry at the next open: rsi_rev, rsi_trend, rsi_mom, ema_cross,
    bb_rev, bb_break, donchian (scalp_1m.rules); btc_lead on the four alts; odds_now's 150 cells (RSI x move x range
    position x BTC above / below its 1000-hour mean).
    Exits: stop 2xATR14 = 1R, target 1R or 2R, timeout 60 bars (15 hours); pessimistic fills; funding charged.
    Costs: gross, maker 4bp (an upper bound - every limit fills), taker 12bp.
    EDGE: both halves net-positive and t > 4.3 (Bonferroni over every test); WEAK: the same with t > 2.4.
    10,000 PKR: the rule with the best TUNE-half net at each fee (200+ tune trades) and "any bar" are replayed on the
    holdout, the whole margin each trade, at 1/3/5/10/20/50x (a loss reaching 1/L - 0.5% liquidates).

REGISTERED BEFORE THE RUN (2026-10-08)
    - Fee toll: 12bp ~0.35R on BTC, ~0.15R on DOGE (1m: 0.98R / 0.50R).
    - Taker 12bp: 0 EDGE, at most 2 WEAK. Maker 4bp: 0 EDGE, at most 10 WEAK.
    - Gross edges of 1-5bp a trade exist, again mostly shorts.
    - The tune-best rule at 10x+ on the holdout: 10,000 PKR under 1,000 within 100 trades.

RESULT (2026-10-08, logs/scalp_15m.txt, logs/scalp_15m_tests.csv; holdout from 2024-04-07)
    - Fee toll at 15m: 12bp = 0.17R (BTC) / 0.13 (ETH) / 0.09 (SOL) / 0.10 (DOGE) / 0.12 (XRP) - predicted 0.35R BTC
      (WRONG, the stop is wider, 0.70%) and 0.15R DOGE (about right). A fifth to a tenth of the 1m toll.
    - Any bar: gross -0.025..+0.020% a trade, so taker -0.10..-0.14%, maker -0.02..-0.06%.
    - 980 tests per fee level: taker 27 net-positive both halves, 1 WEAK, 0 EDGE; maker 110 / 2 / 0; gross 270 / 16 /
      0 (154 of the 270 shorts). Predicted taker <= 2 WEAK and maker <= 10 WEAK, 0 EDGE: right.
    - The tune-best rule at both fees: SHORT DOGE when 15m RSI > 70, a strong rise, near the 50-bar high, BTC bull -
      tune +0.51 -> holdout +0.10% a trade at taker (176 trades in 2.4 years, ~1 every 5 days). 10,000 PKR on the
      holdout at taker: 1x 11,580 | 3x 13,019 | 5x 11,522 | 10x 2,729 | 20x gone after 36 trades | 50x after 2.
      Predicted 10x under 1,000 within 100 trades: WRONG at 10x (2,729), right at 20x and 50x.
    - Long every 15m bar on BTC at taker: 10,000 PKR under 1,000 after 89 trades at 10x (~10 days at 8.5 a day).
    Reading: the bigger bar shrinks the fee toll five- to tenfold and still nothing clears it with confidence; the one
    survivor (fading DOGE spikes in a bull) earned +0.10% a trade on the holdout, a fifth of what it showed before.

    python -m backtest.scalp_15m
"""
from __future__ import annotations

import io
import sys
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import odds_now as on  # noqa: E402
from backtest import scalp_1m as sc  # noqa: E402
from backtest.metrics_fetch import BASE, get  # noqa: E402

DIR = ROOT / "strategy_analysis" / "data" / "min15"
LOG = ROOT / "logs" / "scalp_15m.txt"
COINS = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "DOGEUSDT", "XRPUSDT")
MONTHS = [str(p) for p in pd.period_range("2020-09", "2026-08", freq="M")]
BAR_NS = 15 * 60 * 1_000_000_000
T_EDGE, T_WEAK = 4.3, 2.4
LEVS = (1, 3, 5, 10, 20, 50)
STAKE = 10_000.0


def one_month(sym, m):
    raw = get(f"{BASE}/data/futures/um/monthly/klines/{sym}/15m/{sym}-15m-{m}.zip")
    z = zipfile.ZipFile(io.BytesIO(raw))
    d = pd.read_csv(z.open(z.namelist()[0]), header=None, usecols=[0, 1, 2, 3, 4, 5])
    d = d[pd.to_numeric(d[0], errors="coerce").notna()].astype(float)
    d.columns = ["t", "o", "h", "l", "c", "v"]
    t = d["t"].to_numpy(np.int64)
    d["t"] = np.where(t > 10 ** 14, t // 1000, t)
    return d


def load(sym):
    DIR.mkdir(parents=True, exist_ok=True)
    f = DIR / f"{sym}_15m.parquet"
    if f.exists():
        return pd.read_parquet(f)
    with ThreadPoolExecutor(8) as ex:
        parts = list(ex.map(lambda m: one_month(sym, m), MONTHS))
    d = pd.concat(parts).drop_duplicates("t").sort_values("t", kind="stable").reset_index(drop=True)
    d.insert(0, "time", pd.to_datetime(d.pop("t"), unit="ms").astype("datetime64[ns]"))
    if len(d) < 0.9 * len(MONTHS) * 30 * 96:
        raise SystemExit(f"{sym}: only {len(d):,} 15m bars - incomplete download")
    d.to_parquet(f)
    return d


def valid_mask(d):
    """No window (features back WARMUP bars, outcome forward HOLD bars) may cross a missing bar or a >50% jump."""
    t = d.time.to_numpy("datetime64[ns]").astype(np.int64)
    o, c = d.o.to_numpy(float), d.c.to_numpy(float)
    bad = np.zeros(len(d), bool)
    bad[1:] = (np.diff(t) != BAR_NS) | (np.abs(np.log(o[1:] / c[:-1])) > np.log(1.5))
    cb = np.r_[0, np.cumsum(bad)]
    i = np.arange(len(d))
    lo, hi = np.maximum(i - on.WARMUP + 1, 0), np.minimum(i + sc.HOLD + 1, len(d) - 1)
    return (cb[hi + 1] - cb[lo]) == 0


def path(net_pct, lev):
    """10,000 PKR, whole margin each trade. Returns end PKR and the trade it went under 1,000 (or None)."""
    eq, under = STAKE, None
    liq = 100.0 / lev - 0.5
    for k, x in enumerate(net_pct):
        eq = 0.0 if -x >= liq else eq * max(0.0, 1 + lev * x / 100)
        if under is None and eq < 1000:
            under = k + 1
        if eq <= 0:
            break
    return eq, under


def main():
    t0 = time.time()
    data = {s: load(s) for s in COINS}
    print(f"  data ready ({time.time() - t0:.0f}s)", flush=True)
    btc = data["BTCUSDT"]
    split = np.sort(btc.time.to_numpy())[int(len(btc) * 0.6)]
    ma = pd.Series(btc.c.to_numpy(float)).rolling(4000).mean().to_numpy()          # 1000 hours of 15m bars
    btc_bull = pd.Series(np.where(np.isfinite(ma), (btc.c.to_numpy() > ma).astype(float), np.nan), index=btc.time)
    btc_close = pd.Series(btc.c.to_numpy(float), index=btc.time)
    lines = [f"backtest/scalp_15m.py, {pd.Timestamp.now():%Y-%m-%d %H:%M}; holdout from {pd.Timestamp(split):%Y-%m-%d}; "
             f"stop 2xATR, targets 1R/2R, timeout {sc.HOLD} bars ({sc.HOLD * 15 / 60:.0f}h)", ""]
    results, store = [], {}
    for coin, d in data.items():
        f = on.features(d.o, d.h, d.l, d.c)
        oc = sc.outcomes(d, coin, f["atr"])
        ok = valid_mask(d) & f["ok"]
        times = d.time.to_numpy("datetime64[ns]")
        tbar = times.astype(np.int64) // BAR_NS                    # bar units, so 'held' (bars) adds correctly
        days = times.astype("datetime64[D]")
        stop_pct = on.STOP_ATR * f["atr"] / d.o.shift(-1).to_numpy(float) * 100
        med = np.nanmedian(stop_pct[ok])
        lines.append(f"{coin}: {len(d):,} bars; stop median {med:.3f}% -> 12bp = {0.12 / med:.2f}R, 4bp = {0.04 / med:.2f}R")
        bull = btc_bull.reindex(d.time).to_numpy(float)
        rl = sc.rules(d, f, btc_close.reindex(d.time).to_numpy(float) if coin != "BTCUSDT" else None)
        tests = [(nm, si, sig) for nm, (lg, sh) in rl.items() for si, sig in (("long", lg), ("short", sh))]
        tests += [("any bar", "long", np.ones(len(d), bool)), ("any bar", "short", np.ones(len(d), bool))]
        key = (f["rsi_b"].astype(np.int64) * 100 + f["mom_b"] * 10 + f["loc_b"]) * 2 + np.nan_to_num(bull).astype(np.int64)
        cell_ok = ok & np.isfinite(bull)
        for k_ in np.unique(key[cell_ok]):
            sig = cell_ok & (key == k_)
            if sig.sum() < 200:
                continue
            r_, m_, l_, b_ = k_ // 200, (k_ // 20) % 10, (k_ // 2) % 10, k_ % 2
            nm = f"cell RSI {on.RSI_NAMES[r_]}, {on.MOM_NAMES[m_]}, {on.LOC_NAMES[l_]}, BTC {'bull' if b_ else 'bear'}"
            tests += [(nm, "long", sig), (nm, "short", sig)]
        for nm, side, sig in tests:
            for k in sc.KS:
                o_k = oc[(side, k)]
                idx = sc.take(tbar, sig & ok & np.isfinite(o_k["pct"]), np.nan_to_num(o_k["held"], nan=1))
                if len(idx) < 60:
                    continue
                results += sc.evaluate(nm, coin, side, k, idx, o_k, times, days, split)
                store[(nm, coin, side, k)] = (times[idx], o_k["pct"][idx])
        print(f"  {coin} done ({time.time() - t0:.0f}s)", flush=True)

    R = pd.DataFrame(results)
    R["level"] = np.where(R.level.isin(["EDGE", "WEAK", "pos"]) & (R.t > T_EDGE), "EDGE",
                          np.where(R.level.isin(["EDGE", "WEAK", "pos"]) & (R.t > T_WEAK), "WEAK", R.level))
    R.to_csv(ROOT / "logs" / "scalp_15m_tests.csv", index=False)
    real = R[R.rule != "any bar"]
    lines.append(f"\n{real.groupby('fee').size().iloc[0]} tests per fee level (EDGE t > {T_EDGE}, WEAK t > {T_WEAK}, "
                 f"both halves net-positive for either)")
    lines.append("\nANY BAR (the coin flip), mean % of position per trade, 1R target:")
    for r in R[(R.rule == "any bar") & (R.k == 1)].itertuples():
        lines.append(f"  {r.coin:8} {r.side:5} {r.fee:10}: {r.mean:+.4f}%  (target first {r.p_tp:.1%}, n {r.n})")
    lines.append("\nCOUNTS:")
    for fee in sc.FEES:
        g = real[real.fee == fee]
        lines.append(f"  {fee:10}: {(g.level != '-').sum():4} net-positive both halves, {(g.level == 'WEAK').sum():3} WEAK, "
                     f"{(g.level == 'EDGE').sum():3} EDGE, of {len(g)}; long / short among the passes: "
                     f"{(g[g.level != '-'].side == 'long').sum()} / {(g[g.level != '-'].side == 'short').sum()}")
    for fee in sc.FEES:
        top = real[(real.fee == fee) & real.level.isin(["WEAK", "EDGE"])].sort_values("t", ascending=False).head(8)
        for r in top.itertuples():
            lines.append(f"    {r.level} [{fee}] {r.coin} {r.side} {r.k}R {r.rule}: {r.mean:+.4f}% (t {r.t:+.1f}), "
                         f"tune {r.tune:+.4f} / hold {r.hold:+.4f}, n {r.n}")

    lines.append(f"\n10,000 PKR ON THE HOLDOUT - the best TUNE-half rule at each fee, and 'any bar' long:")
    for fee_name, fee in sc.FEES.items():
        if fee == 0.0:
            continue
        g = real[(real.fee == fee_name) & (real.n_tune >= 200)].sort_values("tune", ascending=False)
        picks = [g.iloc[0], g[g.side == "short"].iloc[0]]
        picks.append(R[(R.rule == "any bar") & (R.fee == fee_name) & (R.coin == "BTCUSDT") & (R.side == "long")
                       & (R.k == 1)].iloc[0])
        for pk in picks:
            tt, gp = store[(pk.rule, pk.coin, pk.side, pk.k)]
            hold = gp[tt >= split] - fee * 100
            span = (tt[-1] - tt[tt >= split][0]) / np.timedelta64(1, "D") if len(hold) else 0
            lines.append(f"  [{fee_name}] {pk.coin} {pk.side} {pk.k}R {pk.rule}: tune {pk.tune:+.4f}%/trade -> holdout "
                         f"{hold.mean():+.4f}%/trade over {len(hold)} trades (~{len(hold) / max(span, 1):.1f} a day)")
            cells = []
            for lev in LEVS:
                end, under = path(hold, lev)
                cells.append(f"{lev}x {end:,.0f}" + (f" (<1k after {under})" if under else ""))
            lines.append("      10,000 PKR -> " + " | ".join(cells))
    txt = "\n".join(lines)
    print(txt)
    LOG.write_text(txt + "\n")
    print(f"\n-> {LOG} ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
