"""AT +20R, CAN WE TELL THE RUNNERS FROM THE REVERSALS? — the last exit question.

    python -m backtest.runner_id

WHY THIS IS THE ONLY VERSION LEFT
    backtest/giveback.py measured that a position peaking at +31R closes at -12.4R on the
    median, while a position peaking at +186R closes at +79.2R - and that at the moment
    both sit at +31R they are observationally identical. Nine exit rules keyed on R have
    failed for exactly that reason. It is an identification problem, not a tuning problem.

    So the question is no longer "what exit rule" but: **is there any FEATURE, knowable at
    the moment a position first crosses +20R, that separates the ones that go on to +100R
    from the ones that die?** If not, this closes permanently and the answer is "hold
    everything, keep 21% of peak, and that 21% is the strategy".

THE PRIZE, SO THE EFFORT IS CALIBRATED
    Of positions that reach +20R of peak, ~35% go on to +100R. The other ~65% close
    around -12R. Perfectly identifying them and closing the doomed ones at +20R would be
    worth roughly 365 x 32R = +11,700R against the book's lifetime +19,113R. That is the
    ceiling, and it is large - which is why this is worth one careful test even at a low
    prior.

FEATURES, DECLARED BEFORE LOOKING
    All measured AT the crossing bar, from data closed at or before it. Nothing about the
    position's future informs any of them.

      bars_held    bars since entry - how long it took to get here
      r_per_bar    +20R divided by bars_held - raw speed
      units        units held at the crossing (1-5)
      atr_ratio    ATR now / ATR at entry - is volatility expanding
      btc_bear     the deployed 1000h regime state (0/1)
      btc_30       BTC's own 30-bar return - is the whole market moving
      coin_30      the coin's 30-bar return
      ext_ma       price / its own 200-bar mean - how extended it already is
      tf           sleeve (1h / 4h / 12h) as a category, reported not tested

    Eight numeric features, so p-values are Holm-corrected across all eight, and the
    survivor is re-tested on a holdout split by date that never informed the ranking.

THE TRAP
    Positions that take LONGER to reach +20R have by construction had more bars in which
    the market could trend, and the biggest runners are in the biggest trends. So
    bars_held and btc_30 could separate for reasons that are about the market's state
    rather than the position's - which is fine if it is tradable, but it means the result
    is a regime statement, not a position statement. The by-year split says which.

REGISTERED PREDICTION (2026-09-21, before running)
    r_per_bar is the best candidate - a position that reached +20R fast is in a violent
    move and violent moves extend - and btc_30 second, because these coins move together
    and a market-wide trend is what carries a position to +186R. I expect at most one to
    survive Holm, and given this project's record (27 categories, 1 survivor) most likely
    none. If something DOES survive, expect it to be a regime feature rather than a
    position feature, which makes it a bet on identifying trends - something the gate
    already tries to do and does badly (41 flips in 80 months).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import blend  # noqa: E402
from backtest.pyramid import FEE_BP  # noqa: E402
from backtest.shortside import signals  # noqa: E402
from backtest.timeframes import resample  # noqa: E402
from bot.core.indicators import atr as atr_ind  # noqa: E402
from bot.strategies.base import Action  # noqa: E402

RULES = ["1h", "4h", "12h"]
CROSS_R, RUNNER_R = 20.0, 100.0
FEATS = ["bars_held", "r_per_bar", "units", "atr_ratio", "btc_bear",
         "btc_30", "coin_30", "ext_ma"]
rng = np.random.default_rng(613)


def btc_context():
    d = blend.load("BTCUSDT")
    c = pd.Series(d["close"].to_numpy(float), index=pd.DatetimeIndex(d["time"]))
    c = c[~c.index.duplicated()].sort_index()
    return pd.DataFrame({"px": c, "r30": c.pct_change(30),
                         "bear": (c < c.rolling(1000).mean()).shift(1)}).dropna()


def walk(df, sig, coin, rule, btc):
    """Deployed long pyramid, recording features at the FIRST crossing of +CROSS_R."""
    s = sig.to_numpy() if isinstance(sig, pd.Series) else np.asarray(sig)
    o = df["open"].to_numpy(float); h = df["high"].to_numpy(float)
    lo = df["low"].to_numpy(float); c = df["close"].to_numpy(float)
    a = atr_ind(df, 14).to_numpy(float)
    ma = pd.Series(c).rolling(200).mean().to_numpy()
    t = pd.DatetimeIndex(df["time"])
    fee = FEE_BP / 1e4
    out, pos = [], None
    for i in range(1, len(df)):
        if pos is None and s[i] == Action.BUY and np.isfinite(a[i-1]) and a[i-1] > 0:
            pos = dict(risk=blend.SL_MULT*a[i-1], stop=o[i]-blend.SL_MULT*a[i-1],
                       best=o[i], bar=i, ents=[o[i]], nxt=1, peak=0.0, feat=None)
        if pos is None:
            continue
        risk = pos["risk"]; e0 = pos["ents"][0]
        mark = sum(h[i] - e_ for e_ in pos["ents"]) / risk
        pos["peak"] = max(pos["peak"], mark)
        if pos["feat"] is None and mark >= CROSS_R:
            held = i - pos["bar"]
            try:
                bc = btc.asof(t[i])
                bb, b30 = float(bool(bc.bear)), float(bc.r30)
            except Exception:
                bb, b30 = 0.0, 0.0
            pos["feat"] = dict(
                bars_held=float(held),
                r_per_bar=CROSS_R / max(held, 1),
                units=float(len(pos["ents"])),
                atr_ratio=float(a[i] / a[pos["bar"]-1]) if a[pos["bar"]-1] > 0 else 1.0,
                btc_bear=bb, btc_30=b30,
                coin_30=float(c[i] / c[i-30] - 1) if i >= 30 else 0.0,
                ext_ma=float(c[i] / ma[i]) if np.isfinite(ma[i]) and ma[i] > 0 else 1.0,
                t=t[i], coin=coin, tf=rule)
        if lo[i] <= pos["stop"]:
            px = pos["stop"]
            r = (sum(px - e_ for e_ in pos["ents"])
                 - sum(fee * e_ for e_ in pos["ents"])) / risk
            if pos["feat"]:
                out.append({**pos["feat"], "peak": pos["peak"], "exit": r})
            pos = None
            continue
        if len(pos["ents"]) < blend.MAX_UNITS:
            if (h[i] - e0) / risk >= pos["nxt"] * blend.ADD_EVERY:
                pos["ents"].append(e0 + pos["nxt"]*blend.ADD_EVERY*risk)
                pos["nxt"] += 1
        pos["best"] = max(pos["best"], h[i])
        cand = pos["best"] - blend.LONG_TRAIL * a[i-1]
        if (pos["best"] - e0)/risk >= blend.BE_AT:
            cand = max(cand, e0)
        if cand > pos["stop"]:
            pos["stop"] = cand
    if pos is not None and pos["feat"]:
        px = c[-1]
        r = (sum(px - e_ for e_ in pos["ents"])
             - sum(fee * e_ for e_ in pos["ents"])) / pos["risk"]
        out.append({**pos["feat"], "peak": pos["peak"], "exit": r})
    return out


def perm_p(a, b, n=20000):
    obs = a.mean() - b.mean()
    allv = np.concatenate([a, b]); k = len(a); cnt = 0
    for _ in range(n):
        p = rng.permutation(allv)
        if abs(p[:k].mean() - p[k:].mean()) >= abs(obs):
            cnt += 1
    return obs, cnt / n


def holm(ps):
    o = np.argsort(ps); m = len(ps); out = np.empty(m); prev = 0.0
    for r, i in enumerate(o):
        prev = max(prev, min(1.0, (m-r)*ps[i])); out[i] = prev
    return out


def auc(pos, neg):
    """Probability a random runner scores above a random reversal."""
    allv = np.concatenate([pos, neg])
    ranks = pd.Series(allv).rank().to_numpy()
    n1, n0 = len(pos), len(neg)
    return (ranks[:n1].sum() - n1*(n1+1)/2) / (n1*n0)


def main():
    print(__doc__.split("REGISTERED PREDICTION")[0].rstrip())
    print("\nREGISTERED: r_per_bar best, btc_30 second; at most one survives Holm and")
    print("most likely none. If something survives expect a REGIME feature, which makes")
    print("it a trend-identification bet the gate already does badly.\n")

    btc = btc_context()
    rows = []
    for coin in blend.BOOK:
        d = blend.load(coin)
        if d is None:
            continue
        for rule in RULES:
            df = resample(d, rule)
            if len(df) < 400:
                continue
            rows += walk(df, signals(df, "long", "all"), coin, rule, btc)
    T = pd.DataFrame(rows)
    if len(T) < 60:
        raise SystemExit(f"only {len(T)} positions crossed +{CROSS_R:g}R")
    T["runner"] = T.peak >= RUNNER_R
    print(f"  {len(T):,} positions crossed +{CROSS_R:g}R, "
          f"{T.runner.sum()} ({100*T.runner.mean():.0f}%) went on to +{RUNNER_R:g}R")
    print(f"  runners close at {T[T.runner].exit.median():+.1f}R median, "
          f"the rest at {T[~T.runner].exit.median():+.1f}R")
    gap = (T[T.runner].exit.median() - CROSS_R)
    prize = (~T.runner).sum() * (CROSS_R - T[~T.runner].exit.median())
    print(f"  PRIZE with perfect foresight: closing the {int((~T.runner).sum())} "
          f"non-runners at +{CROSS_R:g}R is worth {prize:+,.0f}R\n")

    cut = T.t.sort_values().iloc[int(len(T)*0.6)]
    tr, te = T[T.t < cut], T[T.t >= cut]
    print(f"  ranking on {len(tr)} crossings before {cut:%Y-%m-%d}, "
          f"holding out {len(te)}\n")

    print("=" * 96)
    print(f"1. DOES ANY FEATURE SEPARATE RUNNERS FROM REVERSALS?  (tune window)")
    print("=" * 96)
    print(f"  {'feature':<14}{'runners':>11}{'others':>11}{'AUC':>8}{'p':>8}{'Holm':>8}")
    raw, cells = [], []
    for f in FEATS:
        a = tr[tr.runner][f].to_numpy(float)
        b = tr[~tr.runner][f].to_numpy(float)
        if len(a) < 15 or len(b) < 15:
            continue
        _o, p = perm_p(a, b)
        raw.append(p); cells.append((f, a.mean(), b.mean(), auc(a, b), p))
    hp = holm(np.array(raw)) if raw else []
    for (f, am, bm, ac, p), h in zip(cells, hp):
        star = " **" if h < .05 else (" *" if p < .05 else "")
        print(f"  {f:<14}{am:>+11.3f}{bm:>+11.3f}{ac:>8.3f}{p:>8.3f}{h:>8.3f}{star}")
    print("\n  AUC 0.50 = no separation. ** survives Holm across all 8.")

    surv = [c for c, h in zip(cells, hp) if h < .05]
    print("\n" + "=" * 96)
    print("2. HOLDOUT")
    print("=" * 96)
    if not surv:
        print("  Nothing survived Holm, so there is nothing to hold out.")
    else:
        for f, _am, _bm, _ac, _p in surv:
            a = te[te.runner][f].to_numpy(float)
            b = te[~te.runner][f].to_numpy(float)
            if len(a) < 10 or len(b) < 10:
                print(f"  {f:<14} holdout too thin ({len(a)}/{len(b)})")
                continue
            o, p = perm_p(a, b)
            print(f"  {f:<14} held-out diff {o:>+9.3f}  AUC {auc(a,b):.3f}  "
                  f"p {p:.3f}   {'HOLDS' if p < .05 else 'does NOT hold'}")

    print("\n" + "=" * 96)
    print("3. IS IT THE MARKET RATHER THAN THE POSITION? — runners by year")
    print("=" * 96)
    print(f"  {'year':<8}{'crossings':>11}{'runners':>10}{'rate':>8}")
    for y, g in T.groupby(T.t.dt.year):
        print(f"  {y:<8}{len(g):>11}{int(g.runner.sum()):>10}"
              f"{100*g.runner.mean():>7.0f}%")
    print("  If the runner rate is a year effect, no position-level feature can capture it.")

    print("\n" + "=" * 96)
    print("VERDICT")
    print("=" * 96)
    if not surv:
        print("  NOTHING SEPARATES THEM. At +20R a position that will die and a position")
        print("  that will reach +186R are indistinguishable on speed, units, volatility")
        print("  expansion, extension, regime, or market strength.")
        print(f"\n  So the {prize:+,.0f}R prize is unreachable, the 21% capture is the")
        print("  strategy rather than a defect, and this question is closed. Hold")
        print("  everything, keep 21%, and stop looking for an exit rule.")
    else:
        print(f"  {len(surv)} feature(s) survived Holm - see the holdout. Before acting,")
        print("  check section 3: a feature that is really a year effect will not repeat.")


if __name__ == "__main__":
    main()
