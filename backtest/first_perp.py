"""THE ONE EVENT EDGE THAT PASSED A PLACEBO, REOPENED: a coin's FIRST Binance perp.

WHAT IS ALREADY KNOWN (doc 02, "The lead: an OLD coin getting its first Binance perp")
    Short a coin that had traded on Binance SPOT for >60 days, at the open of day 7 of its
    new perp, hold 30 days, stop +50%, with an equal-dollar BTC long as hedge: +10.3% per
    pair, t +3.06 across months, a placebo pass (entering at day 60-540 earns nothing) and a
    dose-response (longer prior spot history, bigger effect). Mechanism: Miller's short-sale
    constraint - while nobody can short a coin its price reflects only the optimists; a perp
    lets the pessimists in. It was shelved because Binance ran out of spot-first coins: the
    last one was May 2025.

WHY IT MAY NOT HAVE RUN OUT
    The mechanism does not need Binance SPOT history - it needs a coin that traded for a
    long time WITHOUT a deep short market. Since 2024 Binance has listed perps for hundreds
    of tokens that traded for months on DEXs and small exchanges first (VIRTUAL, FARTCOIN,
    MOODENG ...). MEXC and Gate list nearly everything at launch, so their first candle is a
    free proxy for "first traded anywhere". The counter-argument is real and is the
    registered prediction: many of these coins already had perps on Bybit / OKX / Hyperliquid
    before Binance, so the constraint was partly lifted before the event, and the effect
    should be SMALLER than the original.

CLASSES (by prior trading history at the perp's first day)
    OLD_BN     Binance spot >= 60 days before (the original definition - reproduced as a guard)
    OLD_OTHER  no such Binance spot, but MEXC/Gate spot >= 60 days before  <- the new test
    NEW        < 60 days anywhere (control: fresh tokens, doc 02 says new-listing shorts are dead)

TRADE (identical to the original)
    Short at the open of perp day 7, hold 30 days, stop +50% on daily highs; long BTC perp,
    same dollars, same days. 12bp per leg; actual funding on both legs.
    PLACEBO: the same coins entered at day 60 / 120 / 180 - no listing, same everything else.
    t-statistics are across calendar months (events cluster in listing waves).

REGISTERED PREDICTIONS (before any OLD_OTHER number exists)
    1. OLD_BN reproduces roughly the original: +8% to +12% per pair.
    2. OLD_OTHER: same sign, smaller: +3% to +6% per pair, t 1.5-2.5; placebo ~0.
    3. Dose-response inside OLD_OTHER: 365+ days of prior history beats 60-180.
    4. NEW: ~0 (doc 02).
    OLD_OTHER counts as ALIVE only if its day-7 mean beats its own placebo in BOTH halves.

    python -m backtest.first_perp
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ROOT = Path(__file__).resolve().parents[1]
PERPS = ROOT / "strategy_analysis" / "data" / "perps"
FIRST = ROOT / "strategy_analysis" / "data" / "first_trade.json"
FEE = 12 / 1e4
ENTER, HOLD, STOP = 7, 30, 0.50
PLACEBO_DAYS = (60, 120, 180)


def _get(u):
    for a in range(4):
        try:
            return json.load(urllib.request.urlopen(urllib.request.Request(
                u, headers={"User-Agent": "Mozilla/5.0"}), timeout=30))
        except urllib.error.HTTPError as e:
            if e.code in (400, 404):
                return None
            time.sleep(1 + a)
        except Exception:
            time.sleep(1 + a)
    return None


def base_of(sym):
    b = sym[:-4] if sym.endswith("USDT") else sym
    return re.sub(r"^(1000000|100000|10000|1000|1M)(?=[A-Z])", "", b)


def first_trade(base):
    """Earliest daily candle on MEXC or Gate spot (X/USDT), as a date string, or None."""
    best = None
    m = _get(f"https://api.mexc.com/api/v3/klines?symbol={base}USDT&interval=1M&limit=1000")
    if m:
        t0 = pd.to_datetime(m[0][0], unit="ms")
        d = _get(f"https://api.mexc.com/api/v3/klines?symbol={base}USDT&interval=1d"
                 f"&startTime={int(t0.value // 10**6)}&endTime={int((t0 + pd.Timedelta(days=62)).value // 10**6)}&limit=100")
        if d:
            best = pd.to_datetime(d[0][0], unit="ms")
        else:
            best = t0
    g = _get(f"https://api.gateio.ws/api/v4/spot/candlesticks?currency_pair={base}_USDT"
             f"&interval=30d&limit=1000")
    if g:
        t0 = pd.to_datetime(int(g[0][0]), unit="s")
        d = _get(f"https://api.gateio.ws/api/v4/spot/candlesticks?currency_pair={base}_USDT"
                 f"&interval=1d&from={int(t0.timestamp())}&to={int((t0 + pd.Timedelta(days=62)).timestamp())}")
        gt = pd.to_datetime(int(d[0][0]), unit="s") if d else t0
        best = gt if best is None else min(best, gt)
    return None if best is None else best.strftime("%Y-%m-%d")


def first_trades(syms):
    from concurrent.futures import ThreadPoolExecutor
    cache = json.load(open(FIRST)) if FIRST.exists() else {}
    todo = sorted({base_of(s) for s in syms} - set(cache))
    with ThreadPoolExecutor(8) as ex:
        for k, (b, v) in enumerate(zip(todo, ex.map(first_trade, todo))):
            cache[b] = v
            if k % 50 == 0:
                json.dump(cache, open(FIRST, "w")); print(f"  first-trade fetch {k}/{len(todo)}", flush=True)
    json.dump(cache, open(FIRST, "w"))
    return cache


def load_daily(sym):
    d = pd.read_csv(PERPS / f"{sym}_1d.csv.gz", parse_dates=["time"])
    d = d[d.close > 0].reset_index(drop=True)
    gap = d.time.diff().dt.days.fillna(1)
    if (gap > 7).any():                                   # first continuous episode only
        d = d.iloc[:int(np.argmax(gap.values > 7))].reset_index(drop=True)
    f = PERPS / f"{sym}_funding.csv.gz"
    fr = pd.read_csv(f, parse_dates=["time"]) if f.exists() else pd.DataFrame(columns=["time", "rate"])
    return d, fr


def leg(d, fr, i, hold, side, stop=None):
    """side -1 short / +1 long from the open of day i for `hold` days (stop on the short
    only). Returns (exit index, return incl. funding and one leg of fees) or None."""
    if i >= len(d):
        return None
    e = float(d.open.iloc[i])
    last = min(i + hold, len(d)) - 1
    j, x = last, float(d.close.iloc[last])
    if side < 0 and stop:
        hi = d.high.to_numpy(float)
        for k in range(i, last + 1):
            if hi[k] >= e * (1 + stop):
                j, x = k, max(e * (1 + stop), float(d.open.iloc[k])) if k > i else e * (1 + stop)
                break
    t0, t1 = d.time.iloc[i], d.time.iloc[j] + pd.Timedelta(days=1)
    f = fr[(fr.time > t0) & (fr.time <= t1)]
    fund = -side * float(f.rate.sum())                    # a long pays +rate
    return j, side * (x / e - 1) + fund - FEE


def pair(sym, day, D, btc):
    d, fr = D[sym]
    got = leg(d, fr, day, HOLD, -1, STOP)
    if got is None:
        return None
    j, r_short = got
    t0, t1 = d.time.iloc[day], d.time.iloc[j]
    bd, bfr = btc
    i0 = bd.index[bd.time == t0]
    if not len(i0):
        return None
    hold_b = int((t1 - t0).days) + 1
    gb = leg(bd, bfr, int(i0[0]), hold_b, +1)
    if gb is None:
        return None
    return dict(t0=t0, pair=r_short + gb[1], short=r_short, btc=gb[1])


def month_t(t, x):
    s = pd.Series(np.asarray(x, float), index=pd.DatetimeIndex(t)).groupby(pd.DatetimeIndex(t).to_period("M")).mean()
    return float(s.mean() / (s.std(ddof=1) / np.sqrt(len(s)))) if len(s) > 2 and s.std() > 0 else np.nan


def main():
    uni = json.load(open(PERPS / "universe.json"))
    meta = {m["sym"]: m for m in uni}
    syms = [s for s, m in meta.items() if m.get("ok", True) and (PERPS / f"{s}_1d.csv.gz").exists()
            and "first" in m and "2020-02-01" <= m["first"] <= "2026-08-10"]
    print(f"{len(syms)} perps listed 2020-02 .. 2026-08; fetching first-trade dates (cached)...")
    ft = first_trades(syms)
    D = {s: load_daily(s) for s in syms + ["BTCUSDT"]}
    btc = D["BTCUSDT"]
    rows = []
    for s in syms:
        if s == "BTCUSDT":
            continue
        d, _ = D[s]
        if len(d) < ENTER + 5:
            continue
        first = d.time.iloc[0]
        bn = meta[s].get("spot_first")
        bn_t = pd.Timestamp(bn + "-01") if bn else None
        other = ft.get(base_of(s))
        other_t = pd.Timestamp(other) if other else None
        if bn_t is not None and (first - bn_t).days >= 60:
            cls, prior = "OLD_BN", (first - bn_t).days
        elif other_t is not None and (first - other_t).days >= 60:
            cls, prior = "OLD_OTHER", (first - other_t).days
        else:
            cls, prior = "NEW", 0
        rec = dict(sym=s, cls=cls, prior=prior, first=first)
        p = pair(s, ENTER, D, btc)
        if p is None:
            continue
        rec.update(p)
        for pd_ in PLACEBO_DAYS:
            q = pair(s, pd_, D, btc)
            rec[f"pl{pd_}"] = q["pair"] if q else np.nan
        rows.append(rec)
    R = pd.DataFrame(rows)
    cut = R.first.quantile(0.6)
    print(f"\n{len(R)} events | tune < {cut:%Y-%m-%d} <= holdout | pair = short coin + long BTC, "
          f"12bp/leg, funding both legs\n")
    print(f"  {'class':<11}{'n':>5}{'pair mean':>11}{'median':>9}{'t(mo)':>7}{'win':>6}"
          f"{'short leg':>11}{'pl d60':>8}{'pl d120':>9}{'pl d180':>9}{'TUNE':>8}{'HOLD':>8}")
    for cls in ("OLD_BN", "OLD_OTHER", "NEW"):
        k = R[R.cls == cls]
        if len(k) < 5:
            continue
        tu = k.first < cut
        print(f"  {cls:<11}{len(k):>5}{k.pair.mean()*100:>+10.1f}%{k.pair.median()*100:>+8.1f}%"
              f"{month_t(k.t0, k.pair):>+7.2f}{(k.pair > 0).mean()*100:>5.0f}%"
              f"{k.short.mean()*100:>+10.1f}%" + "".join(
                  f"{k[f'pl{p}'].mean()*100:>+8.1f}%" for p in PLACEBO_DAYS) +
              f"{k.pair[tu].mean()*100:>+7.1f}%{k.pair[~tu].mean()*100:>+7.1f}%")
    k = R[R.cls == "OLD_OTHER"]
    if len(k):
        print("\n  OLD_OTHER dose-response by prior history, and by listing year:")
        for lab, m in (("60-180d", (k.prior < 180)), ("180-365d", (k.prior >= 180) & (k.prior < 365)),
                       ("365d+", k.prior >= 365)):
            if m.sum():
                print(f"    {lab:<10} n {int(m.sum()):>4}  pair {k.pair[m].mean()*100:+.1f}%  "
                      f"placebo d60 {k.pl60[m].mean()*100:+.1f}%")
        print("    " + "  ".join(f"{y}: {v.mean()*100:+.1f}% (n{len(v)})"
                                 for y, v in k.pair.groupby(k.first.dt.year)))
    R.to_csv(ROOT / "logs" / "first_perp_events.csv", index=False)


if __name__ == "__main__":
    main()
