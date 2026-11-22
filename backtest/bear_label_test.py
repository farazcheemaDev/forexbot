"""FASTER BEAR LABELS FOR THE BREADTH SLEEVE - read-only, nothing in any bot changes (2026-10-30).

The user, 2026-10-30: BTC is down, "clearly a bear market", and the bear sleeve (doc 13, combo_paper.py SLEEVE) did not switch on.
Why: the sleeve's switch is btc_regime's BEAR = BTC's close under its 50-DAY average AND that average down more than 2% over 20 days.
On 2026-10-29's close BTC was 4.8% under the average, but the average was still RISING 1.5%, so the label read CHOP and the sleeve
held nothing, while breadth20 was already at 8.3% (under its 10% line). doc 13 s5 tested the label only coarsely (30/50/100-day
averages x slope 0/-2/-5%: 6 of 6 positive on both halves for 30 and 50 days) and the bot's own 1000h gate as 'bear' earned more
(+34% alt) with a 45-54% drawdown. This file asks the question properly and does NOT change anything.

THE TEST
    Everything of the live sleeve except the label (backtest/breadth_trade.py's engine: 7-day ladder of daily tranches, entered a
    day after the signal (lag 1), long when breadth20 <= 0.10 and short when >= 0.288 - the bot's fixed cut-offs, 12bp round trip,
    exact funding, 1bp/day basket rebalancing), on the alt index (top-40, not buildable at $221) and the top-10 basket (buildable).
    Labels: close under an N-day average, N in {20, 30, 42, 50} (42 ~ the bot's 1000h gate, 41.7 days), x the average's 20-day
    slope: none / below 0 / below -2%.  (50-day, -2%) is the LIVE label: the baseline. 12 cells, all printed, none picked.
    Tune < 2024-08-29 <= holdout, as everywhere in this repo. Thresholds are NOT re-fitted per label - that is what would run.
    Four checks on every faster label: both halves, the 'extra days' book alone (days the faster label is BEAR and the live one is
    not), the matched-risk control (the live sleeve scaled to the SAME drawdown - 'just bet more'), and its neighbours.

REGISTERED BEFORE ANY OF THE 12 CELLS WAS RUN (2026-10-30; I had seen only the old log: live label, alt index, lag 1, expanding
terciles: +27.0% CAGR, tune +31.0 / hold +18.7, fall 20%, worst week -9.5%, in market 25% - and doc 13's label table)
    B0  The live label reproduces the old figures: alt index CAGR +22..+32%, fall 15-25%, in market 22-28% of days.
    F1  Looser labels sit in the market more: (30d, <0) in market 35-50% of days, (20d, none) 45-65%.
    F2  NO faster label is a candidate. A CANDIDATE needs ALL of: CAGR above the live label's on BOTH halves AND Sharpe not below
        it; fall no more than 5 points above and worst week no more than 5 points below the live label's; the same on the top-10
        basket; above the matched-risk live sleeve on the holdout; and one neighbouring cell passing the first two as well.
        My probability that at least one passes: 25%. The likely pattern: the tune half (2020-22 bear years) gains, the holdout loses.
    F3  The 'extra days' book alone has a LOWER Sharpe than the live label's sleeve on the alt index for every faster label that
        adds >= 5 points of in-market time (the strict label matters: doc 13 s3).
    F4  Today (the 2026-10-29 close): the 1000h-like labels (42d none, 50d none) and the 20-30d labels with slope < 0 read BEAR; the
        live 50d / -2% label does not; (30d, -2%) is still CHOP.
    F5  Wherever a faster label out-earns the live one on a half, the live sleeve scaled to the same fall earns at least as much on
        the holdout (more return that is just more risk).
    If none passes the sleeve's label stays as it is, and the answer to 'why is it off in a fall like this' is: because the falls
    that paid were the persistent ones, and a label fast enough to catch today also catches every 4% drop.

    ADDED AFTER THE FIRST RUN (post-hoc, and flagged as such): the first run found NO candidate, and the live label topped the grid on
    fall and Sharpe. The fixed 0.10 / 0.288 cut-offs are terciles of the 50-day label's OWN bear days, which can favour it, so the
    same 12 cells are re-run with each label's own causal cut-offs (bottom / top third of breadth20 over that label's PRIOR bear
    days, >= 60 of them, as breadth_trade.py does). Prediction written before that second run: R1 still no candidate (70%); the
    live label's lead narrows but it stays within 2 points of the best CAGR on the alt index.

    python -m backtest.bear_label_test          writes logs/bear_label_test.txt
"""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

LOG = ROOT / "logs" / "bear_label_test.txt"
LOW, HIGH = 0.100, 0.288                    # combo_paper.py's fixed cut-offs
MA_LENS = (20, 30, 42, 50)
SLOPES = (None, 0.0, -0.02)                 # None = price under the average only; else the average's change over SLOPE_D days
SLOPE_D = 20
LIVE = (50, -0.02)
START = pd.Timestamp("2020-03-01")
CUT = pd.Timestamp("2024-08-29")


# ------------------------------------------------------------------ the label, and what the sleeve does with it
def label(closes: pd.Series, ma_len: int, slope_th) -> pd.Series:
    """True on days the label is BEAR, knowable the day it is used: computed from closes through the day BEFORE (shift 1, as
    market_neutral.btc_regime does). slope_th None = close under the average only."""
    ma = closes.rolling(ma_len).mean()
    cond = closes < ma
    if slope_th is not None:
        cond = cond & ((ma / ma.shift(SLOPE_D) - 1) < slope_th)
    return cond.astype(float).shift(1).fillna(0.0).astype(bool)


def signal(bear: pd.Series, br: pd.Series) -> pd.Series:
    """The sleeve's decision each day: +1 long when BEAR and breadth <= LOW, -1 short when BEAR and breadth >= HIGH, else 0."""
    b = bear.to_numpy(bool)
    x = br.reindex(bear.index).to_numpy(float)
    out = np.where(b & (x <= LOW), 1.0, np.where(b & (x >= HIGH), -1.0, 0.0))
    return pd.Series(out, index=bear.index)


def signal_expanding(bear: pd.Series, br: pd.Series, min_prior: int = 60) -> pd.Series:
    """Same decision with the cut-offs read from the label's OWN history: bottom / top third of breadth20 over the bear days BEFORE
    today (>= min_prior of them). Causal: today's breadth is added to the history only after today's decision."""
    b = bear.to_numpy(bool)
    x = br.reindex(bear.index).to_numpy(float)
    out = np.zeros(len(b))
    hist: list = []
    for d in range(len(b)):
        if b[d] and len(hist) >= min_prior and np.isfinite(x[d]):
            lo, hi = np.quantile(hist, [1 / 3, 2 / 3])
            out[d] = 1.0 if x[d] <= lo else (-1.0 if x[d] >= hi else 0.0)
        if b[d] and np.isfinite(x[d]):
            hist.append(x[d])
    return pd.Series(out, index=bear.index)


def dd_of(x: pd.Series, k: float = 1.0) -> float:
    eq = (1 + k * x).cumprod()
    return float((1 - eq / eq.cummax()).max() * 100)


def match_k(x: pd.Series, target_dd: float) -> float:
    """The multiple k of the book's daily returns whose compounded fall equals target_dd (bisection; fall rises with k)."""
    lo, hi = 0.05, 8.0
    if dd_of(x, hi) < target_dd:
        return hi
    for _ in range(60):
        mid = (lo + hi) / 2
        if dd_of(x, mid) < target_dd:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def judge(cell: dict, live: dict, matched_hold: float) -> dict:
    """The registered candidate rule for ONE instrument. cell / live: dicts with tune, hold, sharpe, dd, ww.
    matched_hold = the live sleeve's holdout %/yr when scaled to this cell's full-sample fall."""
    a = cell["tune"] > live["tune"] and cell["hold"] > live["hold"]
    b = cell["sharpe"] >= live["sharpe"]
    c = cell["dd"] <= live["dd"] + 5 and cell["ww"] >= live["ww"] - 5
    d = cell["hold"] > matched_hold
    return dict(both_halves=a, sharpe=b, risk=c, beats_matched=d, ok=bool(a and b and c and d))


# ------------------------------------------------------------------ today's reading and the flip date
def today_table(closes_closed: np.ndarray, flat_price: float):
    """For each label: BEAR today? and how many more daily closes at flat_price until it is BEAR (None = not in 80 days)."""
    out = {}
    for n in MA_LENS:
        for s in SLOPES:
            def is_bear(arr):
                S = pd.Series(arr)
                ma = S.rolling(n).mean()
                ok = S.iloc[-1] < ma.iloc[-1]
                if s is not None:
                    ok = ok and (ma.iloc[-1] / ma.iloc[-1 - SLOPE_D] - 1) < s
                return bool(ok)
            now = is_bear(closes_closed)
            arr, days = closes_closed.copy(), None
            if not now:
                for d in range(1, 81):
                    arr = np.append(arr, flat_price)
                    if is_bear(arr):
                        days = d
                        break
            out[(n, s)] = (now, days)
    return out


# ------------------------------------------------------------------ the run
def main():
    from backtest.breadth_trade import half, instruments, ladder, stats
    from backtest.carry_check import exact_funding
    from backtest.market_neutral import btc_regime, load_panel

    C, F, first = load_panel()
    C.index = C.index.astype("datetime64[ns]")
    F.index = C.index
    feat = pd.read_csv(ROOT / "logs" / "regime_signals_features.csv.gz", index_col=0, parse_dates=True)
    feat.index = feat.index.astype("datetime64[ns]")
    br = feat["breadth20"].reindex(C.index)
    Fx = exact_funding(C.index, C.columns)
    ins = instruments(C, Fx, first)
    btc = C["BTCUSDT"].dropna()

    # the live label must be exactly btc_regime's BEAR: the baseline is the thing that runs
    live_bear = label(btc, *LIVE).reindex(C.index).fillna(False)
    ref = (btc_regime(C).reindex(C.index) == "bear")
    assert (live_bear.to_numpy() == ref.to_numpy()).all(), "live label does not reproduce market_neutral.btc_regime"

    bears = {(n, s): label(btc, n, s).reindex(C.index).fillna(False) for n in MA_LENS for s in SLOPES}
    lines = [f"backtest/bear_label_test.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; panel {C.index[0]:%Y-%m-%d} .. "
             f"{C.index[-1]:%Y-%m-%d}; live label reproduces btc_regime on all {len(C)} days; cut-offs {LOW} / {HIGH} fixed, lag 1, "
             f"7-day ladder; returns on the whole account, from {START:%Y-%m-%d}", ""]
    def grid(sigfun, title):
        lines.append(title)
        lines.append('')
        res = {}
        for iname in ("alt index (top-40)", "top-10 basket"):
            ret, fund, rebal = ins[iname]
            lines.append(f"=== {iname}")
            lines.append(f"  {'label':<14}{'bear days':>10}{'CAGR':>8}{'TUNE/yr':>9}{'HOLD/yr':>9}{'DD':>6}{'worst wk':>10}{'Sharpe':>8}"
                         f"{'in mkt':>8}  | extra-days book alone: CAGR   Sharpe  in mkt")
            books = {}
            for key, bear in bears.items():
                sg = sigfun(bear)
                x, pos = ladder(sg, ret, fund, rebal, 1)
                x = x[x.index >= START]
                pos = pos.reindex(x.index)
                cagr, dd, ww, sh, inm = stats(x, pos)
                t, h = half(x)
                books[key] = dict(x=x, cagr=cagr, tune=t, hold=h, dd=dd, ww=ww, sharpe=sh, inm=inm, days=int(bear[bear.index >= START].sum()))
            lv = books[LIVE]
            for key, bk in books.items():
                n, s = key
                name = f"{n}d {'none' if s is None else f'{s * 100:+.0f}%'}" + ("  LIVE" if key == LIVE else "")
                if key != LIVE:
                    extra = bears[key] & ~bears[LIVE]
                    xe, pe = ladder(sigfun(extra), ret, fund, rebal, 1)
                    xe = xe[xe.index >= START]
                    ce, _, _, she, ime = stats(xe, pe.reindex(xe.index))
                    bk["extra"] = (ce, she, ime)
                    tail = f"  | {ce:+7.1f}%  {she:6.2f}  {ime:4.0f}%"
                else:
                    tail = ""
                lines.append(f"  {name:<14}{bk['days']:>10}{bk['cagr']:>+7.1f}%{bk['tune']:>+8.1f}%{bk['hold']:>+8.1f}%{bk['dd']:>5.0f}%"
                             f"{bk['ww']:>+9.1f}%{bk['sharpe']:>8.2f}{bk['inm']:>7.0f}%{tail}")
            res[iname] = books
            lines.append("")
        lines.append("MATCHED-RISK CONTROL - the LIVE sleeve scaled to the SAME full-sample fall as each faster label; "
                     "a label only matters if it beats this on the holdout:")
        cand = []
        for iname, books in res.items():
            lv = books[LIVE]
            for key, bk in books.items():
                if key == LIVE:
                    continue
                k = match_k(lv["x"], bk["dd"])
                xk = lv["x"] * k
                t, h = half(xk)
                j = judge(bk, lv, h)
                bk["judge"], bk["k"], bk["matched"] = j, k, (t, h)
                n, s = key
                lines.append(f"  {iname[:9]:<10}{n}d {'none' if s is None else f'{s * 100:+.0f}%':<6}: live x{k:4.2f} -> tune {t:+6.1f}% hold {h:+6.1f}% "
                             f"(this label tune {bk['tune']:+6.1f}% hold {bk['hold']:+6.1f}%)  both halves above live: {j['both_halves']}, "
                             f"Sharpe: {j['sharpe']}, risk within 5 pts: {j['risk']}, beats matched on holdout: {j['beats_matched']}")
        lines.append("")
        # candidate = passes judge on BOTH instruments, plus one neighbour passing the first two checks
        passing = [key for key in res["alt index (top-40)"] if key != LIVE
                   and all(res[i][key]["judge"]["ok"] for i in res)]
        def adj(a, b):
            return (a[0] == b[0] and abs(SLOPES.index(a[1]) - SLOPES.index(b[1])) == 1) or \
                   (a[1] == b[1] and abs(MA_LENS.index(a[0]) - MA_LENS.index(b[0])) == 1)
        weak = [key for key in res["alt index (top-40)"] if key != LIVE
                and all(res[i][key]["judge"]["both_halves"] and res[i][key]["judge"]["sharpe"] for i in res)]
        final = [k for k in passing if any(adj(k, w) for w in weak if w != k)]
        lines.append(f"CANDIDATES (all of: both halves + Sharpe + risk + matched-risk, on both instruments, and a neighbour passing "
                     f"both halves + Sharpe): {[f'{n}d/{s}' for n, s in final] or 'NONE'}")
        lines.append(f"  passing every check on both instruments but without a passing neighbour: "
                     f"{[f'{n}d/{s}' for n, s in passing if (n, s) not in final] or 'none'}")

    grid(lambda b: signal(b, br), '######## 1. THE REGISTERED TEST - fixed cut-offs 0.10 / 0.288, as the live sleeve runs')
    lines.append('')
    grid(lambda b: signal_expanding(b, br), '######## 2. POST-HOC ROBUSTNESS (added after run 1) - each label with its OWN causal expanding terciles')
    lines.append('')
    # today
    try:
        k = json.loads(urllib.request.urlopen("https://fapi.binance.com/fapi/v1/klines?symbol=BTCUSDT&interval=1d&limit=200", timeout=20).read())
        closed = np.array([float(r[4]) for r in k[:-1]])
        tdy = today_table(closed, 77000.0)
        d0 = pd.to_datetime(k[-2][0], unit="ms")
        lines.append("")
        lines.append(f"TODAY (label read the day after the {d0:%Y-%m-%d} close of ${closed[-1]:,.0f}; flip = further daily closes at $77,000 flat):")
        for (n, s), (now, days) in tdy.items():
            lines.append(f"  {n}d {'none' if s is None else f'{s * 100:+.0f}%':<6}: {'BEAR' if now else 'not bear'}"
                         + ("" if now else f", flips after {days} more closes" if days else ", no flip within 80 days at that price")
                         + ("   <- LIVE" if (n, s) == LIVE else ""))
    except Exception as e:  # offline: the back-test above stands on its own
        lines.append(f"\nTODAY: not read ({str(e)[:80]})")
    txt = "\n".join(lines)
    print(txt)
    LOG.write_text(txt + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
