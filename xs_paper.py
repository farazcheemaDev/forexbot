"""PAPER FORWARD TEST — market-neutral cross-sectional momentum. PRE-REGISTERED.

Everything below the line marked PRE-REGISTERED is fixed. Read it before looking
at any result; changing it later and keeping the accumulated record would make the
test worthless.

WHY PAPER AND NOT THE BITGET DEMO
    The Bitget demo venue offers exactly THREE contracts - SBTCSUSDT, SETHSUSDT,
    SXRPSUSDT (verified against /api/v2/mix/market/contracts?productType=
    SUSDT-FUTURES on 2026-09-12). A strategy that ranks 21 coins and trades the
    top 5 against the bottom 5 cannot exist on a 3-symbol venue. So this runs on
    live Binance public prices with simulated fills.

    That substitution is defensible HERE and would not have been for the maker
    bot. The maker strategy's whole open question was "does a resting limit order
    get filled", which only a real venue can answer - and the answer was 53%,
    which killed it. This strategy rebalances once a day with taker market orders
    in the 21 most liquid perps. Fill probability is ~1; the cost is fees plus a
    few bp of slippage, and fees are charged at Bitget's real 6bp taker rate.
    Slippage is NOT modelled, which makes this optimistic by an estimated 1-3bp
    per side. Stated so it can be subtracted later.

WHY A FORWARD TEST IS THE ONLY OPTION LEFT
    The 2025-04..2026-09 holdout is SPENT - two looks, logged in the contamination
    ledger. Two improvements measured on dev cannot be tested on it:
        dispersion gate p50   dev Sharpe 2.05 vs 1.26, fees 7.8 vs 12.9 %/yr
        index hedge k=5 h=8   dev MAR 1.94 vs 1.38, Sharpe 1.67 vs 1.26
    Only data that did not exist on 2026-09-12 can test those. This generates it.
    All three variants run SIMULTANEOUSLY on the same prices, so they are compared
    on identical data rather than across different periods.

WHAT IS ALREADY ESTABLISHED (do not re-derive from this test)
    dev  (21 coins, 39,748 h)  Sharpe +1.09  CAGR +34.7%/yr  beta -0.01
    MCPT (shared-index, 300 perms)               p < 0.01
    holdout (500 unseen days)  +12.6%/yr  Sharpe +0.62  t=+0.72  <- NOT significant
    same signal long-only, same holdout:  -7.3%/yr, 57% DD, beta +0.91

    The holdout t of +0.72 cannot reject zero. The strategy is a real effect by
    MCPT and by grid robustness (80% of 120 configs positive); its SIZE is not
    established. This test is about the size.

=============================== PRE-REGISTERED ===============================
H1  variant A (plain neutral L/S) earns a positive net return over the test.
H2  variant B (dispersion-gated) beats A on Sharpe, as dev predicted.
H3  variant C (index-hedged) beats A on MAR, as dev predicted.
H4  realised beta to the equal-weight universe stays within +/-0.25 for all three.

SUCCESS  A's Sharpe >= +0.5 with n >= 60 rebalances AND realised beta within
         +/-0.25. Anything less is a fail, including a positive return that came
         from beta rather than from the ranking.
DECIDE AT  n = 60 daily rebalances (~2 months). No verdict before then; a
         verdict read early is a verdict fitted to noise.
LEVERAGE  1.0x AND 3.0x, both recorded, as separate books on identical prices.

         AMENDED 2026-09-12 09:0x at the user's explicit instruction ("run it at
         3x leverage on the paper test"). The original registration said 1.0x
         only. The amendment is logged here rather than silently applied.

         1.0x is KEPT because it is the clean measurement of the effect, and
         because a levered record cannot be converted back into an unlevered one:
         compounding is path-dependent, eq *= (1 + L*r) per period, which is not
         (1 + r)^L. Neither series can be reconstructed from the other, so both
         are recorded rather than one being derived.

         3.0x does NOT improve the edge. Sharpe is leverage-invariant; 3x scales
         return and drawdown together and raises ruin probability. Expectation
         from the holdout: ~35%/yr with ~70% drawdowns, and a +10% month about
         35% of the time (vs 6% at 1x). It is the ruin tail that changes, which
         is why RUIN_AT below is enforced and logged.
==============================================================================

    python xs_paper.py              # run the loop
    python xs_paper.py --status     # print the record and stop
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
STATE = LOGS / "xsp_state.json"
MARKS = LOGS / "xsp_marks.csv"
REBAL = LOGS / "xsp_rebalances.csv"

# --- PRE-REGISTERED PARAMETERS ---------------------------------------------
COINS = ["BTCUSDT", "ETHUSDT", "XRPUSDT", "BNBUSDT", "ADAUSDT", "DOGEUSDT",
         "LINKUSDT", "LTCUSDT", "ATOMUSDT", "ETCUSDT", "XLMUSDT", "BCHUSDT",
         "TRXUSDT", "SOLUSDT", "DOTUSDT", "PAXGUSDT", "UNIUSDT", "AVAXUSDT",
         "NEARUSDT", "AAVEUSDT", "FILUSDT"]
LB = 168               # 1-week momentum lookback, in hours
HOLD_H = 24            # rebalance once a day
K = 5                  # top/bottom 5
TAKER_BP = 6.0         # Bitget taker, per side, charged on turnover
DISP_Q = 0.50          # variant B gate: spread above its own rolling median
# KNOWN DEVIATION FROM THE BACKTEST: the backtest took this median over a 90-day
# rolling window (2,160 h). Binance's kline endpoint caps at 1,000 bars, and 168
# of those go to the momentum lookback, so live the median is taken over ~830 h
# (~35 days) of spread history. A median is a stable statistic, so this should be
# a minor difference - but it IS a difference, and variant B's live numbers are
# therefore not a pure replication of the dev configuration.
DISP_WIN = 24 * 90
START_EQUITY = 10_000.0
VARIANTS = ("A_neutral", "B_dispersion", "C_idxhedge", "D_momsharpe", "E_mom720")

# Per-variant signal config. D and E were ADDED 2026-09-12 after backtest/
# xs_combine.py measured 14 sleeves on dev. They are here BECAUSE they were
# selected from a 14-way search and the holdout is spent - a forward test is the
# only honest way to judge them. Dev numbers, for later comparison:
#
#   A_neutral    mom_168h    Sharpe +0.95  MAR 0.82  DD 34.6%  fees 12.4%/yr
#                            ^ the only one MCPT-validated (p=0.0033)
#   B_dispersion disp_168h   Sharpe +1.71  MAR 0.98  DD 31.4%  fees  7.5%/yr
#   C_idxhedge   idxh_168h   Sharpe +1.05  MAR 1.02  DD 20.3%  fees  5.7%/yr
#   D_momsharpe  momsh_168h  Sharpe +1.64  MAR 2.05  DD 25.4%  fees 12.8%/yr
#   E_mom720     mom_720h    Sharpe +1.43  MAR 1.48  DD 31.0%  fees  6.2%/yr
#
# UPDATE 2026-09-12, after backtest/xs_wide.py tested the frozen sleeves on 58
# coins that took no part in any choice (see that file for why coins are a valid
# out-of-sample axis when the time holdout is spent):
#
#   D_momsharpe IS REFUTED. On the coins it was searched on it scored 1.64 vs
#   0.95 for A. On virgin coins it LOST TO A IN 6/6 cells (k=5/10/20 x 6/12bp).
#   It was a best-of-14 artifact. It stays in the run as a NEGATIVE CONTROL, and
#   this is now a pre-registered prediction, not a hope:
#       PREDICT: D underperforms A over the forward test.
#   If D instead beats A forward, the virgin-coin gate is not as reliable as the
#   dev/holdout gates and that is itself worth knowing.
#
#   E_mom720 IS THE SURVIVOR. It was the only sleeve positive in 6/6 virgin cells
#   at BOTH fee levels (Sharpe +0.59/+0.38/+0.47/+0.21/+0.47/+0.19), and it has
#       PREDICT: E >= A over the forward test.
#
# So the live ordering to expect is E >= A > D. The original dev ordering
# (B~D > E > C > A) is already known to be wrong about D.
VARIANT_CFG = {
    "A_neutral":    dict(lb=168, k=5, mode="ls",  rank_by="ret"),
    "B_dispersion": dict(lb=168, k=5, mode="ls",  rank_by="ret", disp=True),
    "C_idxhedge":   dict(lb=168, k=5, mode="idx", rank_by="ret"),
    "D_momsharpe":  dict(lb=168, k=5, mode="ls",  rank_by="sharpe"),
    "E_mom720":     dict(lb=720, k=5, mode="ls",  rank_by="ret"),
}
LEVERAGES = (1.0, 3.0)
# A book is dead below this fraction of starting equity. A real venue would very
# likely have liquidated a 3x book well before a 95% loss - maintenance margin
# bites far earlier - so treat this as the OUTER bound on survival, not a
# realistic stop. Its purpose is to stop a dead book from silently trading on
# with negative equity and polluting the Sharpe.
RUIN_AT = 0.05


def books() -> list[str]:
    return [f"{v}@{L:g}x" for v in VARIANTS for L in LEVERAGES]


def book_parts(b: str) -> tuple[str, float]:
    v, L = b.split("@")
    return v, float(L.rstrip("x"))
# ---------------------------------------------------------------------------

POLL_S = 300


def log(m: str):
    line = f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S} | {m}"
    print(line, flush=True)


def klines(sym: str, limit: int = 1000) -> pd.DataFrame | None:
    u = (f"https://api.binance.com/api/v3/klines?symbol={sym}"
         f"&interval=1h&limit={limit}")
    for a in range(3):
        try:
            r = json.load(urllib.request.urlopen(u, timeout=20))
            break
        except Exception:
            if a == 2:
                return None
            time.sleep(2)
    if not r:
        return None
    return pd.DataFrame({
        "t": pd.to_datetime([k[0] for k in r], unit="ms"),
        "close": [float(k[4]) for k in r]})


def funding_now(sym: str) -> float:
    """Latest settled funding rate. Long pays when positive."""
    u = f"https://fapi.binance.com/fapi/v1/fundingRate?symbol={sym}&limit=1"
    try:
        r = json.load(urllib.request.urlopen(u, timeout=15))
        return float(r[0]["fundingRate"]) if r else 0.0
    except Exception:
        return 0.0


def fresh_state() -> dict:
    # weights are per VARIANT, not per book: target weights are the strategy's
    # signal and do not depend on leverage. Leverage scales the exposure taken
    # against those same weights, so both books of a variant hold the same names.
    return {"equity": {b: START_EQUITY for b in books()},
            "weights": {v: {} for v in VARIANTS},
            "dead": [],
            "prev_px": {}, "last_rebal_h": None, "n_rebal": 0,
            "started": datetime.now(timezone.utc).isoformat()}


def load_state() -> dict:
    if STATE.exists():
        try:
            s = json.load(open(STATE))
            for key in fresh_state():
                s.setdefault(key, fresh_state()[key])
            # structure guard: the book set changed (e.g. a leverage was added),
            # so the saved equity keys no longer address the same books. Silently
            # carrying on would KeyError or, worse, mix two accounting schemes in
            # one equity series.
            missing = set(books()) - set(s.get("equity", {}))
            if missing:
                log(f"state has a different book set (missing {sorted(missing)}) "
                    f"— archiving and restarting the record")
                return None
            return s
        except Exception:
            log("state unreadable — starting fresh")
    return fresh_state()


def save_state(s: dict):
    json.dump(s, open(STATE, "w"), indent=1)


def archive_and_reset() -> dict:
    """Move the old record aside so a changed book set never mixes schemes."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    for f in (STATE, MARKS, REBAL):
        if f.exists():
            dest = f.with_name(f"{f.stem}.pre-{stamp}{f.suffix}")
            f.replace(dest)
            log(f"archived {f.name} -> {dest.name}")
    return fresh_state()


def append_csv(path: Path, row: dict):
    new = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as fh:
        if new:
            fh.write(",".join(row) + "\n")
        fh.write(",".join(str(row[k]) for k in row) + "\n")


def target_weights(closes: dict[str, pd.Series], variant: str,
                   spread_hist: pd.Series | None) -> dict[str, float] | None:
    """Same arithmetic as backtest/xs_momentum.weights, for one point in time."""
    cfg = VARIANT_CFG[variant]
    lb, k = cfg["lb"], cfg["k"]
    mom = {}
    for s, c in closes.items():
        if len(c) <= lb or not np.isfinite(c.iloc[-1]) or c.iloc[-1 - lb] <= 0:
            continue
        m = c.iloc[-1] / c.iloc[-1 - lb] - 1.0
        if cfg["rank_by"] == "sharpe":
            # divide by realised vol over the SAME window, matching
            # xs_momentum.weights: C.pct_change().rolling(lb).std()
            v = float(c.pct_change().iloc[-lb:].std(ddof=1))
            if not np.isfinite(v) or v <= 0:
                continue
            m = m / v
        mom[s] = float(m)
    if len(mom) < 2 * k:
        log(f"  [{variant}] only {len(mom)} coins with {lb}h history — skipping")
        return None
    order = sorted(mom, key=lambda s: mom[s])
    lo, hi = order[:k], order[-k:]

    if cfg.get("disp"):
        spread = float(np.mean([mom[s] for s in hi]) - np.mean([mom[s] for s in lo]))
        if spread_hist is None or len(spread_hist) < 24 * 30:
            log(f"  [{variant}] not enough spread history yet — flat")
            return {}
        th = float(spread_hist.quantile(DISP_Q))
        if spread < th:
            return {}                       # nothing worth paying the spread for
    w: dict[str, float] = {}
    if cfg["mode"] == "idx":
        for s in hi:
            w[s] = w.get(s, 0.0) + 0.5 / k
        for s in mom:                       # short an equal-weight index
            w[s] = w.get(s, 0.0) - 0.5 / len(mom)
    else:
        for s in hi:
            w[s] = w.get(s, 0.0) + 0.5 / k
        for s in lo:
            w[s] = w.get(s, 0.0) - 0.5 / k
    return w


def spread_series(closes: dict[str, pd.Series], lb: int | None = None,
                  k: int | None = None) -> pd.Series:
    """Historical top-k-minus-bottom-k momentum spread, for the dispersion gate.

    Defaults to the dispersion variant's own lb/k rather than the module globals,
    so the threshold is built from the same ranking the gate is applied to.
    """
    bc = VARIANT_CFG["B_dispersion"]
    lb = lb if lb is not None else bc["lb"]
    k = k if k is not None else bc["k"]
    df = pd.DataFrame(closes).dropna(how="all")
    if len(df) <= lb + 10:
        return pd.Series(dtype=float)
    m = (df / df.shift(lb) - 1.0).to_numpy(dtype=float)
    hi_s = np.sort(np.where(np.isnan(m), -np.inf, m), axis=1)
    lo_s = np.sort(np.where(np.isnan(m), np.inf, m), axis=1)
    sp = hi_s[:, -k:].mean(axis=1) - lo_s[:, :k].mean(axis=1)
    return pd.Series(sp, index=df.index).replace([np.inf, -np.inf], np.nan).dropna()


def status(st: dict):
    print(f"\nXS PAPER FORWARD TEST — started {st.get('started','?')}")
    print(f"rebalances: {st['n_rebal']}  (verdict at 60)\n")
    if MARKS.exists():
        d = pd.read_csv(MARKS)
        print(f"{'book':<18} {'equity':>10} {'ret%':>8} {'Sharpe':>8} "
              f"{'maxDD%':>8} {'beta':>7}  {'':<6}")
        for b in books():
            col = f"eq_{b}"
            if col not in d or len(d) < 3:
                continue
            e = d[col].astype(float)
            r = e.pct_change().dropna()
            sh = (r.mean() / r.std(ddof=1) * np.sqrt(24 * 365.25)
                  if len(r) > 10 and r.std(ddof=1) > 0 else 0.0)
            dd = float((1 - e / e.cummax()).max() * 100)
            bt = 0.0
            if "mkt_ret" in d and len(r) > 20:
                mk = d["mkt_ret"].astype(float).iloc[1:len(r) + 1].to_numpy()
                if np.nanstd(mk) > 0:
                    bt = float(np.cov(r.to_numpy(), mk)[0, 1] / np.var(mk))
            flag = "RUINED" if b in st.get("dead", []) else ""
            print(f"{b:<18} {e.iloc[-1]:>10.2f} "
                  f"{(e.iloc[-1]/START_EQUITY-1)*100:>+8.2f} {sh:>+8.2f} "
                  f"{dd:>8.2f} {bt:>+7.2f}  {flag:<6}")
        print("\nSharpe is leverage-invariant by construction — the 1x and 3x rows "
              "of a\nvariant should agree on Sharpe and differ ~3x on return and "
              "drawdown.\nIf they disagree on Sharpe, something is wrong with the "
              "book accounting.")
    print()


def cycle(st: dict):
    need = max(c["lb"] for c in VARIANT_CFG.values()) + 5
    closes: dict[str, pd.Series] = {}
    for s in COINS:
        d = klines(s, 1000)
        if d is None or len(d) < need:
            continue
        closes[s] = d.set_index("t")["close"]
    if len(closes) < 2 * K:
        log(f"only {len(closes)}/{len(COINS)} coins fetched — skipping cycle")
        return

    # last CLOSED hourly bar: Binance's final row is the bar still forming
    px = {s: float(c.iloc[-2]) for s, c in closes.items()}
    closed = {s: c.iloc[:-1] for s, c in closes.items()}
    bar_h = max(c.index[-1] for c in closed.values())

    # ---- mark to market on price moves since the last cycle -----------------
    prev = st["prev_px"]
    rets = {s: px[s] / prev[s] - 1.0 for s in px if s in prev and prev[s] > 0}
    mkt = float(np.mean(list(rets.values()))) if rets else 0.0
    settle = bar_h.hour % 8 == 0          # funding lands at 00/08/16 UTC
    fr = {s: funding_now(s) for s in px} if settle else {}
    row = {"ts": f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}",
           "bar": f"{bar_h:%Y-%m-%d %H:%M}", "mkt_ret": f"{mkt:.8f}"}
    for b in books():
        v, lev = book_parts(b)
        w = st["weights"][v]
        pnl = sum(w.get(s, 0.0) * rets.get(s, 0.0) for s in w) if rets else 0.0
        fund = sum(w.get(s, 0.0) * fr.get(s, 0.0) for s in w) if settle else 0.0
        if b not in st["dead"]:
            st["equity"][b] *= (1.0 + lev * (pnl - fund))
            if st["equity"][b] <= RUIN_AT * START_EQUITY:
                st["equity"][b] = max(st["equity"][b], 0.0)
                st["dead"].append(b)
                log(f"[{b}] RUINED — equity {st['equity'][b]:.2f} "
                    f"(<= {RUIN_AT:.0%} of start). Book closed, no further trades.")
        row[f"eq_{b}"] = f"{st['equity'][b]:.4f}"
    st["prev_px"] = px
    if rets:
        append_csv(MARKS, row)

    # ---- rebalance once every HOLD_H hours ---------------------------------
    key = f"{bar_h:%Y-%m-%d %H}"
    last = st.get("last_rebal_h")
    due = last is None or (bar_h - pd.Timestamp(last)).total_seconds() >= HOLD_H * 3600
    if not due:
        log(f"bar {key} | mkt {mkt*100:+.2f}% | " +
            " ".join(f"{b.split('_')[0]}{b.split('@')[1]}={st['equity'][b]:.0f}"
                     for b in books()))
        return

    sh = spread_series(closed)
    for v in VARIANTS:
        tgt = target_weights(closed, v, sh)
        if tgt is None:
            continue
        old = st["weights"][v]
        turn = sum(abs(tgt.get(s, 0.0) - old.get(s, 0.0))
                   for s in set(tgt) | set(old))
        cost = turn * TAKER_BP / 1e4
        st["weights"][v] = tgt
        longs = sorted([s for s, x in tgt.items() if x > 1e-9],
                       key=lambda s: -tgt[s])
        shorts = sorted([s for s, x in tgt.items() if x < -1e-9],
                        key=lambda s: tgt[s])
        # turnover is on GROSS NOTIONAL, so a 3x book pays 3x the fees. Leverage
        # multiplies the cost drag exactly as it multiplies the return.
        for L in LEVERAGES:
            b = f"{v}@{L:g}x"
            if b in st["dead"]:
                continue
            st["equity"][b] *= (1.0 - L * cost)
            append_csv(REBAL, {"ts": f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}",
                               "bar": key, "book": b,
                               "turnover": f"{turn:.4f}",
                               "cost_bp": f"{L*cost*1e4:.2f}",
                               "equity": f"{st['equity'][b]:.4f}",
                               "n_long": len(longs), "n_short": len(shorts)})
        eqs = " ".join(f"{L:g}x={st['equity'][f'{v}@{L:g}x']:.0f}"
                       for L in LEVERAGES)
        log(f"[{v}] REBAL turn={turn:.3f} cost={cost*1e4:.1f}bp/1x | {eqs}")
        if longs:
            log(f"    LONG  {', '.join(s.replace('USDT','') for s in longs[:6])}")
        if shorts:
            log(f"    SHORT {', '.join(s.replace('USDT','') for s in shorts[:6])}"
                + (f" (+{len(shorts)-6} more)" if len(shorts) > 6 else ""))
        if not tgt:
            log("    FLAT (gate closed)")
    st["last_rebal_h"] = str(bar_h)
    st["n_rebal"] += 1
    log(f"rebalance #{st['n_rebal']} done (verdict at 60)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--status", action="store_true")
    args = ap.parse_args()
    st = load_state() or archive_and_reset()
    if args.status:
        status(st)
        return
    log("XS PAPER FORWARD TEST — market-neutral cross-sectional momentum")
    log(f"  {len(COINS)} coins | hold={HOLD_H}h k={K} | taker {TAKER_BP}bp/side")
    for v, c in VARIANT_CFG.items():
        log(f"    {v:<14} lb={c['lb']:>4}h rank={c['rank_by']:<6} "
            f"mode={c['mode']}" + ("  +dispersion gate" if c.get("disp") else ""))
    log(f"  {len(books())} books: {', '.join(VARIANTS)} x "
        f"{'/'.join(f'{L:g}x' for L in LEVERAGES)} — all on identical prices")
    log(f"  ruin threshold {RUIN_AT:.0%} of start; fees scale with leverage")
    log(f"  PRE-REGISTERED: verdict at 60 rebalances, currently {st['n_rebal']}")
    while True:
        try:
            cycle(st)
            save_state(st)
        except KeyboardInterrupt:
            log("stopped"); save_state(st); return
        except Exception as e:
            log(f"cycle error: {type(e).__name__}: {str(e)[:200]}")
        time.sleep(POLL_S)


if __name__ == "__main__":
    main()
