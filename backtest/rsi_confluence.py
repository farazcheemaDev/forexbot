"""EXTREME RSI + A SECOND INDICATOR / SUPPORT-RESISTANCE - the user's "there must be a relationship" (2026-10-08).

THE USER: "what if below 20 we open and around 90 ... there must be a relationship between RSI and another indicator,
we can also use support and resistance levels."

THE HOLDOUT IS BEING MINED. This is the ~10th sweep of the 2024-04-07 .. holdout in two sessions (CLAUDE.md s2: "the
holdout is mined out"). A survivor here is a candidate for a forward paper tracker, nothing more; the bar is
Bonferroni over every configuration, not t > 2.

ENTRIES: RSI(14) crosses under X (10 / 15 / 20) -> LONG; crosses over 100-X (90 / 85 / 80) -> SHORT. Next-bar open.
CONFIRMATIONS at the signal bar (long meaning; shorts mirror), alone and in pairs (1 + 8 + 28 = 37 filters):
    sr          the close within 1 x ATR14 of the lowest low (highest high) of the 100 bars BEFORE the signal bar
    bb          the close outside Bollinger(20, 2)
    divergence  the signal bar's low under the lowest low of bars i-30..i-5 while RSI is above RSI at that low
    vol         volume > 3 x its 20-bar average (before the bar)
    htf         the higher timeframe's last CLOSED bar also has RSI(14) < 30 (> 70): 15m->1h, 1h->4h, 4h->1d
    stoch       stochastic %K(14) < 10 (> 90)
    trend       close above (below) its 200-bar EMA
    btc         BTC above (below) its 200-bar EMA on the same bars
EXITS (rsi_factors.py's, vectorised here and tested equal to rsi_factors.trade):
    tp2         +2% limit, no stop
    tp2_nw      +2%, or out at the next open once 24 bars have passed and the close is not in profit
    rsi50       out at the next open after RSI closes back through 50
    7-day cap; 12bp + funding; one trade at a time per coin; worst drawdown inside each trade recorded.
15m / 1h / 4h x BTC ETH SOL DOGE XRP, 2020-09 .. 2026-08; tune < 2024-04-07 <= holdout.
EDGE: pooled over the 5 coins, both halves positive, 30+ trades each, t > 4.3 (Bonferroni over ~2,000 configs);
WEAK: t > 2.4. Then the 5 best by TUNE average (100+ tune trades), judged on the holdout, 10,000 PKR on one coin.

REGISTERED BEFORE THE RUN (2026-10-08)
    - Extreme levels give fewer trades and higher win rates; long holdout averages within +-0.3% a trade; shorts
      negative.
    - No confirmation beats "no confirmation" on BOTH halves on average across configurations.
    - 0 EDGE.
    - The tune-picked 5 average at most +0.2% a trade on the holdout.

RESULT (2026-10-08, logs/rsi_confluence.txt, logs/rsi_confluence_configs.csv, logs/rsi_confluence_verify.txt)
    - tests: the vectorised exits equal rsi_factors.trade() on 1,500+ random trades; the higher-timeframe RSI and the
      confirmations are causal (two planted leaks caught).
    - Extreme RSI alone: longs at 4h RSI < 20 / 1h < 15 are positive on both halves (e.g. 4h < 20, tp2: 91% win,
      tune +0.63 / holdout +1.19%); shorts at RSI > 80/85/90 lose everywhere. Predicted "longs within +-0.3%": WRONG.
    - Confirmations vs none: stoch better on both halves in 17 of 24 pairs, sr 9/24, bb 11/36, divergence 0/6.
    - 19 EDGE / 62 WEAK of 409 configs (predicted 0 EDGE: WRONG per trade). --verify (by distinct day, 4 bar phases):
        CAPITULATION BUY - 4h, RSI(14) crosses under 20 AND volume > 3x its 20-bar average, +2% target, out after 24
        bars if not in profit: phases 0/60/120/180 min -> avg +1.61 / +1.00 / +0.91 / +1.30% a trade, every phase
        positive on BOTH halves, t by day 6.9 / 3.8 / 3.7 / 4.5, win 88-96%, every year 2020-2026 positive (2022
        +1.3%), every coin positive. Honest size ~+1.0% a trade (phase 0 was the one it was found on).
        The 1h variants fade with the phase (t 4.9 -> 1.3); 15m RSI < 10 is 55% five days; plain 4h RSI < 20 is weak.
    - 10,000 PKR on the capitulation buy, split over the 5 coins, 2020-09 .. 2026-03 (70-84 trades, ~13 a year):
      1x 11,589-12,515 | 2x 10,404-15,652 | 3x 11,799-19,561 | 5x 2,871-18,721 | 10x 0 on every phase. A trade's
      deepest dip reached 29-53%, which is what wipes the leveraged single-coin accounts.
    Reading: the one RSI rule here that survives the bar-phase, by-day and by-year checks - buying capitulation, the
    same family as the crash bids (doc 16) and the bear-breadth bounce (doc 13). It is real-looking but RARE, so on
    10,000 PKR it is a few percent a year at 1x, and leverage past ~3x meets the dips inside trades. Found in the
    ~10th sweep of this holdout: a forward paper record decides.

    python -m backtest.rsi_confluence
    python -m backtest.rsi_confluence --verify
"""
from __future__ import annotations

import itertools
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import odds_now as on  # noqa: E402
from backtest import scalp_15m as s15  # noqa: E402
from backtest.rsi_factors import bars, play, prep  # noqa: E402
from backtest.rsi_only import FEE, TFS, rsi14  # noqa: E402

LOG = ROOT / "logs" / "rsi_confluence.txt"
COINS = s15.COINS
HOLDOUT = pd.Timestamp("2024-04-07")
LEVELS = (20, 15, 10)
EXITS = ("tp2", "tp2_nw", "rsi50")
CONFS = ("sr", "bb", "divergence", "vol", "htf", "stoch", "trend", "btc")
HTF = {"15m": 4, "1h": 16, "4h": 96}            # higher timeframe in 15m bars
T_EDGE, T_WEAK = 4.3, 2.4


def outcome(i, side, ex, P, fc, cap):
    """Vectorised rsi_factors.trade(i, side, prof, fac, ...) for (tp2, none), (tp2, not_working), (rsi50, none).
    Returns (bar after which the next signal may come, net, worst)."""
    o, h, l, c, r = P["o"], P["h"], P["l"], P["c"], P["r"]
    n = len(c)
    e = o[i + 1]
    j_end = min(i + 1 + cap, n - 2)
    js = np.arange(i + 1, j_end + 1)
    adv = (1 - l[i + 1:j_end + 1] / e) if side > 0 else (h[i + 1:j_end + 1] / e - 1)
    cum_worst = np.maximum.accumulate(adv)
    exits = []                                                           # (bar index j, kind)
    if ex in ("tp2", "tp2_nw"):
        tp = (h[i + 1:j_end + 1] >= e * 1.02) if side > 0 else (l[i + 1:j_end + 1] <= e * 0.98)
        if tp.any():
            exits.append((int(js[np.argmax(tp)]), "tp"))
    if ex == "tp2_nw":
        cl = c[i + 1:j_end + 1]
        nw = ((js - i) >= 24) & ((cl <= e) if side > 0 else (cl >= e))
        if nw.any():
            exits.append((int(js[np.argmax(nw)]), "close"))
    if ex == "rsi50":
        rr = r[i + 1:j_end + 1]
        hit = (rr >= 50) if side > 0 else (rr <= 50)
        if hit.any():
            exits.append((int(js[np.argmax(hit)]), "close"))
    if exits:
        j, kind = min(exits, key=lambda x: (x[0], 0 if x[1] == "tp" else 1))   # same bar: the target (intrabar) first
        worst = float(cum_worst[j - (i + 1)])
        if kind == "tp":
            return j, 0.02 - FEE - side * (fc[j] - fc[i + 1]) / e, worst
        x = o[j + 1]
        return j + 1, side * (x / e - 1) - FEE - side * (fc[j + 1] - fc[i + 1]) / e, worst
    return j_end, side * (c[j_end] / e - 1) - FEE - side * (fc[j_end] - fc[i + 1]) / e, float(cum_worst[-1])


def htf_rsi(d, k_htf, k_tf):
    """RSI(14) of the higher timeframe's last CLOSED bar at each bar's close."""
    hb = bars_from(d, k_htf // k_tf)
    r = rsi14(hb.c.to_numpy(float))
    close_hb = hb.time.to_numpy("datetime64[ns]") + np.timedelta64(15 * k_htf, "m")
    close_b = d.time.to_numpy("datetime64[ns]") + np.timedelta64(15 * k_tf, "m")
    k = np.searchsorted(close_hb, close_b, side="right") - 1
    return np.where(k >= 0, r[np.clip(k, 0, None)], np.nan)


def bars_from(d, m):
    g = d.set_index("time").resample(f"{int((d.time.iloc[1] - d.time.iloc[0]).total_seconds() // 60) * m}min")
    out = pd.DataFrame({"o": g["o"].first(), "h": g["h"].max(), "l": g["l"].min(), "c": g["c"].last(),
                        "n": g["c"].count()})
    return out[out.n == m].drop(columns="n").reset_index()


def confirmations(i, side, P, htf, btc_ema):
    o, h, l, c, r, v, atr = P["o"], P["h"], P["l"], P["c"], P["r"], P["v"], P["atr"]
    out = {}
    lo100, hi100 = (l[max(i - 100, 0):i].min(), h[max(i - 100, 0):i].max()) if i >= 100 else (np.nan, np.nan)
    out["sr"] = abs(c[i] - (lo100 if side > 0 else hi100)) <= atr[i]
    seg = c[max(i - 19, 0):i + 1]
    mid, sd = seg.mean(), seg.std()
    out["bb"] = (c[i] < mid - 2 * sd) if side > 0 else (c[i] > mid + 2 * sd)
    a, b = i - 30, i - 4
    if a >= 0:
        ref = (a + int(np.argmin(l[a:b]))) if side > 0 else (a + int(np.argmax(h[a:b])))
        out["divergence"] = ((l[i] < l[ref]) and (r[i] > r[ref])) if side > 0 else ((h[i] > h[ref]) and (r[i] < r[ref]))
    else:
        out["divergence"] = False
    va = v[max(i - 20, 0):i].mean() if i > 0 else np.nan
    out["vol"] = bool(np.isfinite(va) and v[i] > 3 * va)
    out["htf"] = bool(np.isfinite(htf[i]) and ((htf[i] < 30) if side > 0 else (htf[i] > 70)))
    lo14, hi14 = l[max(i - 13, 0):i + 1].min(), h[max(i - 13, 0):i + 1].max()
    k = 100 * (c[i] - lo14) / (hi14 - lo14) if hi14 > lo14 else 50.0
    out["stoch"] = (k < 10) if side > 0 else (k > 90)
    out["trend"] = (c[i] > P["ema200"][i]) if side > 0 else (c[i] < P["ema200"][i])
    out["btc"] = bool(np.isfinite(btc_ema[i]) and ((P["btc"][i] > btc_ema[i]) if side > 0 else (P["btc"][i] < btc_ema[i])))
    return out


def main():
    t0 = time.time()
    filters = [()] + [(c,) for c in CONFS] + list(itertools.combinations(CONFS, 2))
    rows = []
    for tf, k in TFS.items():
        cap = 7 * 96 // k
        btc = bars("BTCUSDT", k)
        btc_s = pd.Series(btc.c.to_numpy(float), index=btc.time)
        for sym in COINS:
            d = bars(sym, k)
            P = prep(d, btc_s.reindex(d.time).to_numpy(float))
            btc_ema = pd.Series(P["btc"]).ewm(span=200, adjust=False).mean().to_numpy()
            htf = htf_rsi(d, HTF[tf], k)
            fc = on.fund_by_bar(sym, d.time, P["o"])
            t = d.time.to_numpy()
            r = P["r"]
            for side in (1, -1):
                for X in LEVELS:
                    lv = X if side > 0 else 100 - X
                    sig = (np.r_[False, (r[:-1] >= lv) & (r[1:] < lv)] if side > 0
                           else np.r_[False, (r[:-1] <= lv) & (r[1:] > lv)])
                    sig[:250] = False
                    cand = [i for i in np.flatnonzero(sig) if i + 2 < len(r)]
                    if not cand:
                        continue
                    conf = {i: confirmations(i, side, P, htf, btc_ema) for i in cand}
                    res = {ex: {i: outcome(i, side, ex, P, fc, cap) for i in cand} for ex in EXITS}
                    for flt in filters:
                        sel = [i for i in cand if all(conf[i][c_] for c_ in flt)]
                        for ex in EXITS:
                            free = 0
                            for i in sel:
                                if i < free:
                                    continue
                                j, net, worst = res[ex][i]
                                rows.append((tf, sym, "long" if side > 0 else "short", X, "+".join(flt) or "none",
                                             ex, t[i + 1], net, worst))
                                free = j + 1
        print(f"  {tf} done ({time.time() - t0:.0f}s)", flush=True)
    A = pd.DataFrame(rows, columns=["tf", "coin", "side", "X", "filter", "exit", "t", "net", "worst"])
    A["t"] = pd.to_datetime(A["t"])
    A.to_csv(ROOT / "logs" / "rsi_confluence_trades.csv.gz", index=False, compression="gzip")
    keys = ["tf", "side", "X", "filter", "exit"]
    S = []
    for kk, g in A.groupby(keys, sort=False):
        x = g.net.to_numpy()
        tu, ho = g[g.t < HOLDOUT].net, g[g.t >= HOLDOUT].net
        tstat = x.mean() / (x.std(ddof=1) / np.sqrt(len(x))) if len(x) > 2 and x.std() > 0 else np.nan
        S.append(dict(zip(keys, kk), n=len(g), win=np.mean(x > 0), avg=x.mean(), t=tstat, worst=x.min(),
                      n_t=len(tu), tune=tu.mean() if len(tu) else np.nan, n_h=len(ho), hold=ho.mean() if len(ho) else np.nan))
    S = pd.DataFrame(S)
    both = (S.n_t >= 30) & (S.n_h >= 30) & (S.tune > 0) & (S.hold > 0)
    S["level"] = np.where(both & (S.t > T_EDGE), "EDGE", np.where(both & (S.t > T_WEAK), "WEAK", "-"))
    S.to_csv(ROOT / "logs" / "rsi_confluence_configs.csv", index=False)

    lines = [f"backtest/rsi_confluence.py, {pd.Timestamp.now():%Y-%m-%d %H:%M}; {len(S):,} configurations (5 coins "
             f"pooled); tune < {HOLDOUT:%Y-%m-%d} <= holdout; EDGE t > {T_EDGE}", ""]
    lines.append("1. EXTREME RSI ALONE (no confirmation): trades | win | avg | worst | tune | holdout")
    for r_ in S[S["filter"] == "none"].itertuples():
        lines.append(f"  {r_.tf:>3} {r_.side:5} RSI {('<' if r_.side == 'long' else '>')}{r_.X if r_.side == 'long' else 100 - r_.X:<3}"
                     f" {r_.exit:7} {r_.n:>6} {r_.win:>5.0%} {r_.avg * 100:>+7.2f}% {r_.worst * 100:>+7.1f}% "
                     f"{r_.tune * 100:>+7.2f}% {r_.hold * 100:>+7.2f}% (n {r_.n_h})")
    lines.append("\n2. EACH CONFIRMATION ALONE vs NO CONFIRMATION, same tf/side/level/exit (average difference per trade, "
                 "tune / holdout; configs with 30+ trades in each half on both sides of the comparison):")
    base = S[S["filter"] == "none"].set_index(["tf", "side", "X", "exit"])
    for c_ in CONFS:
        g = S[S["filter"] == c_].set_index(["tf", "side", "X", "exit"]).join(base, rsuffix="_b", how="inner")
        g = g[(g.n_t >= 30) & (g.n_h >= 30) & (g.n_t_b >= 30) & (g.n_h_b >= 30)]
        if g.empty:
            lines.append(f"  {c_:11}: too few trades")
            continue
        dt, dh = (g.tune - g.tune_b), (g.hold - g.hold_b)
        lines.append(f"  {c_:11}: {len(g):>3} pairs, tune {dt.mean() * 100:+.2f}%, holdout {dh.mean() * 100:+.2f}%, better on both "
                     f"halves in {int(((dt > 0) & (dh > 0)).sum())} of {len(g)}")
    lines.append(f"\n3. EDGE {int((S.level == 'EDGE').sum())}, WEAK {int((S.level == 'WEAK').sum())} of "
                 f"{int(((S.n_t >= 30) & (S.n_h >= 30)).sum())} configs with 30+ trades in each half:")
    for r_ in S[S.level != "-"].sort_values("t", ascending=False).head(10).itertuples():
        lines.append(f"    {r_.level} {r_.tf:>3} {r_.side:5} X{r_.X} {r_.filter:22} {r_.exit:7} n {r_.n:>4} win {r_.win:.0%} "
                     f"avg {r_.avg * 100:+.2f}% (t {r_.t:+.1f}) tune {r_.tune * 100:+.2f} / hold {r_.hold * 100:+.2f} "
                     f"worst {r_.worst * 100:+.1f}%")
    lines.append("\n4. PICKED ON THE TUNE HALF (best tune average, 100+ tune trades), judged on the holdout:")
    pick = S[S.n_t >= 100].sort_values("tune", ascending=False).head(5)
    for r_ in pick.itertuples():
        g = A[(A.tf == r_.tf) & (A.side == r_.side) & (A.X == r_.X) & (A["filter"] == r_.filter) & (A.exit == r_.exit)
              & (A.t >= HOLDOUT)].sort_values("t", kind="stable")
        lines.append(f"    {r_.tf:>3} {r_.side:5} X{r_.X} {r_.filter:22} {r_.exit:7} tune {r_.tune * 100:+.2f}% (n {r_.n_t}) -> "
                     f"holdout {r_.hold * 100:+.2f}% (n {r_.n_h}, win {np.mean(g.net > 0) if len(g) else np.nan:.0%})")
        for lev in (1, 3, 5):
            ends = [play(x.net.to_numpy(), x.worst.to_numpy(), lev) for _, x in g.groupby("coin")]
            lines.append(f"        10,000 PKR on ONE coin, {lev}x: " + ", ".join(f"{e:,.0f}" for e in ends)
                         + f"  ({', '.join(sorted(g.coin.unique()))})")
    lines.append(f"\n  average of the 5 picks on the holdout: {pick.hold.mean() * 100:+.2f}% a trade (tune {pick.tune.mean() * 100:+.2f}%)")
    txt = "\n".join(lines)
    print(txt)
    LOG.write_text(txt + "\n")
    print(f"\n-> {LOG} ({time.time() - t0:.0f}s)")


VERIFY = (("4h", 1, 20, ("vol",), "tp2_nw"), ("4h", 1, 20, (), "tp2"), ("1h", 1, 20, ("htf", "stoch"), "tp2_nw"),
          ("1h", 1, 20, ("stoch",), "tp2_nw"), ("15m", 1, 10, (), "rsi50"))


def bars_off(sym, k, offset_min):
    """bars() with the bar grid shifted by offset_min minutes (the bar-phase check)."""
    d = s15.load(sym)
    if k == 1:
        return d.reset_index(drop=True)
    g = d.set_index("time").resample(f"{15 * k}min", offset=f"{offset_min}min")
    out = pd.DataFrame({"o": g["o"].first(), "h": g["h"].max(), "l": g["l"].min(), "c": g["c"].last(),
                        "v": g["v"].sum(), "n": g["c"].count()})
    return out[out.n == k].drop(columns="n").reset_index()


def collect(tf, offset, side, X, flt, ex):
    """The trades of ONE configuration on all 5 coins, on a bar grid shifted by `offset` minutes."""
    k = TFS[tf]
    cap = 7 * 96 // k
    btc = bars_off("BTCUSDT", k, offset)
    btc_s = pd.Series(btc.c.to_numpy(float), index=btc.time)
    rows = []
    for sym in COINS:
        d = bars_off(sym, k, offset)
        P = prep(d, btc_s.reindex(d.time).to_numpy(float))
        btc_ema = pd.Series(P["btc"]).ewm(span=200, adjust=False).mean().to_numpy()
        htf = htf_rsi(d, HTF[tf], k)
        fc = on.fund_by_bar(sym, d.time, P["o"])
        t, r = d.time.to_numpy(), P["r"]
        lv = X if side > 0 else 100 - X
        sig = np.r_[False, (r[:-1] >= lv) & (r[1:] < lv)] if side > 0 else np.r_[False, (r[:-1] <= lv) & (r[1:] > lv)]
        sig[:250] = False
        free = 0
        for i in np.flatnonzero(sig):
            if i < free or i + 2 >= len(r):
                continue
            cf = confirmations(i, side, P, htf, btc_ema)
            if not all(cf[c_] for c_ in flt):
                continue
            j, net, worst = outcome(i, side, ex, P, fc, cap)
            rows.append((sym, t[i + 1], net, worst))
            free = j + 1
    return pd.DataFrame(rows, columns=["coin", "t", "net", "worst"]).assign(t=lambda x: pd.to_datetime(x.t))


def verify():
    """AFTER main() found 19 'EDGE' configurations. Registered before running (2026-10-08): the capitulation buy
    (4h, RSI < 20 + volume spike, tp2_nw) survives all 4 bar phases with a positive holdout; counted by DISTINCT DAY
    its t falls to 3-6 (from 9.4 per trade); it is positive in 2022 too."""
    lines = [f"backtest/rsi_confluence.py --verify, {pd.Timestamp.now():%Y-%m-%d %H:%M} (after main; predictions in the "
             f"docstring)", ""]
    phases = {"4h": (0, 60, 120, 180), "1h": (0, 15, 30, 45), "15m": (0,)}
    for tf, side, X, flt, ex in VERIFY:
        name = f"{tf} {'long' if side > 0 else 'short'} RSI<{X} {'+'.join(flt) or 'none'} {ex}"
        lines.append(name)
        for off in phases[tf]:
            T = collect(tf, off, side, X, flt, ex)
            if T.empty:
                lines.append(f"  phase +{off}min: no trades")
                continue
            day = T.t.dt.floor("D")
            per_day = T.groupby(day).net.mean()                     # one number per distinct day
            td = per_day.mean() / (per_day.std(ddof=1) / np.sqrt(len(per_day))) if len(per_day) > 2 else np.nan
            tu, ho = T[T.t < HOLDOUT].net, T[T.t >= HOLDOUT].net
            yrs = " ".join(f"{y}:{T[T.t.dt.year == y].net.mean() * 100:+.1f}%({(T.t.dt.year == y).sum()})"
                           for y in range(2020, 2027) if (T.t.dt.year == y).any())
            lines.append(f"  phase +{off:>3}min: {len(T)} trades on {len(per_day)} distinct days, win {np.mean(T.net > 0):.0%}, "
                         f"avg {T.net.mean() * 100:+.2f}%, t by day {td:+.1f}, tune {tu.mean() * 100:+.2f}% (n {len(tu)}) / "
                         f"holdout {ho.mean() * 100:+.2f}% (n {len(ho)}), worst {T.net.min() * 100:+.1f}%")
            if off == 0:
                top = per_day.sort_values(ascending=False)
                lines.append(f"      by year (avg, trades): {yrs}")
                lines.append(f"      best 5 days carry {top.head(5).sum() / max(per_day.sum(), 1e-12):.0%} of the day-sum; "
                             f"per coin: " + ", ".join(f"{c[:-4]} {g.net.mean() * 100:+.2f}%({len(g)})" for c, g in T.groupby("coin")))
        lines.append("")
    txt = "\n".join(lines)
    print(txt)
    (ROOT / "logs" / "rsi_confluence_verify.txt").write_text(txt + "\n")


if __name__ == "__main__":
    verify() if "--verify" in sys.argv else main()
