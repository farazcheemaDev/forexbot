"""THE MARKET-REGIME DIAL - Coinbase premium + BTC momentum, applied to the bot.

WHERE THIS COMES FROM (btc_signals.py, logs/btc_signals.txt)
    Fourteen market-timing signals; none passed Holm on its own. The two NAMED IN ADVANCE as
    likeliest ("tsmom and cb_prem") were the two that held their predicted sign on BOTH halves
    for BOTH targets:
        cb_prem  Coinbase premium, 7d mean   BTC next week +2.11%/wk top-bottom (t 1.86)
                                              bot's long R +2.01R top-bottom (t 1.94)
        tsmom    sign-sum of BTC 7/28/90d     BTC next week +1.80%/wk (t 1.97)
                                              bot's long R +1.99R (t 2.03)
    Two weak signals that agree, chosen before the data, are worth combining. Nothing else from
    that table is used here - picking more of them after seeing the holdout columns would be
    fitting the table.

THE REGIME, fixed before this file ran
    BULL  tsmom >= +1  AND  Coinbase premium > 0     (momentum up, US spot buying)
    BEAR  tsmom <= -1  AND  Coinbase premium < 0     (momentum down, US spot selling)
    else  NEUTRAL.  Known at the start of each UTC day from data through the previous day.

TWO USES ON THE BOT (tight exit + time stop, corrected engine, entry-sized, 1000h gate kept)
    DIAL   long risk x M_bull in BULL, x M_bear in BEAR, x1 otherwise. The control that decides
           it (bull_boost.py's rule): a UNIFORM multiplier on every long that reaches the same
           drawdown. A dial is only worth anything if it beats simply betting more.
    STOP   "we know when to stop": when the regime turns BEAR, open longs trail at 5xATR (the
           tight exit's mechanics, same arm-after-switch-off rule), in ADDITION to the BTC 4h
           break that already tightens them.

REGISTERED PREDICTIONS (before running)
    1. DIAL x1.5 bull / x0.5 bear beats the drawdown-matched uniform control on BOTH halves, by
       +0.5 to +1.5 %/mo. (The 1000h gate already carries much of the bear information.)
    2. DIAL x2 bull / x1 bear raises return with more drawdown and still beats its control.
    3. STOP helps the worst month on both halves and costs < 0.5 %/mo.
    Caveat that travels: the two signals' holdout columns were seen before this file was
    written, so a both-halves win here is evidence, not proof. The forward books decide.

    python -m backtest.btc_dial
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import blend  # noqa: E402
from backtest.bear_side import sleeve_sided  # noqa: E402
from backtest.bull_boost import regimes  # noqa: E402
from backtest.causal_t0 import real_t0  # noqa: E402
from backtest.compounding import curve, summarize  # noqa: E402
from backtest.engine_variants import break_map, shorts_for  # noqa: E402
from backtest.funding_cost import charged, long_funding, short_funding  # noqa: E402
from backtest.graveyard_rescore import SEEDS, rows as book_rows, walk  # noqa: E402
from backtest.timeframes import resample  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
TS = (100, 2.0)


def regime():
    """Daily 'BULL' / 'BEAR' / 'NEUTRAL', known at 00:00 UTC of each day."""
    F = pd.read_csv(ROOT / "logs" / "btc_signals_features.csv.gz", index_col=0, parse_dates=True)
    bull = (F.tsmom >= 1) & (F.cb_prem > 0)
    bear = (F.tsmom <= -1) & (F.cb_prem < 0)
    s = pd.Series("NEUTRAL", index=F.index)
    s[bull.fillna(False).astype(bool)] = "BULL"
    s[bear.fillna(False).astype(bool)] = "BEAR"
    return s


def state_at(reg, t):
    t = pd.Timestamp(t)
    return reg.asof(t.normalize()) if t.normalize() >= reg.index[0] else "NEUTRAL"


def dial(rs, reg, m_bull, m_bear):
    return [dict(r, R=r["R"] * (m_bull if state_at(reg, r["t0"]) == "BULL" else
                                (m_bear if state_at(reg, r["t0"]) == "BEAR" else 1.0)))
            if r["side"] == "long" else r for r in rs]


def uniform(rs, m):
    return [dict(r, R=r["R"] * m) if r["side"] == "long" else r for r in rs]


def stop_rows(reg):
    """tight + time stop, where the tightening flag is BTC's 4h break OR a BEAR regime."""
    out = []
    bear_day = (reg == "BEAR")
    for rule in ("1h", "4h", "12h"):
        out += shorts_for(rule)
        for coin in blend.BOOK:
            d = blend.load(coin)
            if d is None:
                continue
            df = resample(d, rule)
            if len(df) < 300:
                continue
            br = break_map(df, rule)
            # the regime for a bar is the one in force when the bar ENDS (the trail is updated
            # at the bar end): known at 00:00 of that day, so causal
            ends = pd.DatetimeIndex(df["time"]) + pd.Timedelta(hours=1)
            bd = bear_day.reindex(pd.DatetimeIndex(ends.normalize()), method="ffill") \
                .fillna(False).to_numpy(bool)
            out += walk(df, rule, coin, tb=(br | bd), time_stop=TS)
    return charged(real_t0(short_funding(long_funding(out))))


def taken(rs, bear, seed, t_from=None, t_to=None):
    rng = np.random.default_rng(seed)
    tie = rng.random(len(rs))
    o = [rs[i] for i in sorted(range(len(rs)), key=lambda i: (rs[i]["t0"], tie[i]))]
    opens, out = [], []
    for r in o:
        if (t_from is not None and r["t0"] < t_from) or (t_to is not None and r["t0"] >= t_to):
            continue
        opens = [u for u in opens if u > r["t0"]]
        if len(opens) >= 12:
            continue
        opens.append(r["t1"])
        f = blend.RISK / 100.0 * (blend.REGIME_MULT if bool(bear.asof(r["t0"])) else 1.0)
        out.append((pd.Timestamp(r["t0"]), pd.Timestamp(r["t1"]), r["R"] * f))
    return out


def score(rs, bear, cut):
    res = {}
    for half, kw in (("tune", dict(t_to=cut)), ("hold", dict(t_from=cut))):
        v = []
        for sd in SEEDS:
            c = curve(taken(rs, bear, sd, **kw), "entry_sized")
            hpm, _r, dd, _f = summarize(c)
            v.append((hpm, dd, float(c.resample("ME").last().pct_change().min() * 100)))
        res[half] = np.array(v)
    return res


def main():
    bear = regimes()[1000]
    ts = pd.DatetimeIndex(sorted(x[0] for x in sleeve_sided("1h")[0]))
    cut = ts[int(len(ts) * 0.6)]
    reg = regime()
    print("regime share of days since 2020-02: " + "  ".join(
        f"{k} {v*100:.0f}%" for k, v in reg[reg.index >= "2020-02-01"].value_counts(normalize=True).items()))
    base = book_rows(tight=True, time_stop=TS)
    L = [r for r in base if r["side"] == "long"]
    st = pd.Series([state_at(reg, r["t0"]) for r in L])
    R = pd.Series([r["R"] for r in L])
    print("bot's long R by regime at entry: " + "  ".join(
        f"{k}: n {int((st == k).sum())} mean {R[st == k].clip(-25, 100).mean():+.2f}R (capped)"
        for k in ("BULL", "NEUTRAL", "BEAR")))

    B = score(base, bear, cut)
    print(f"\nentry-sized, 1000h gate kept, {len(SEEDS)} paired orderings | %/mo = CAGR/3, DD/worst raw")
    print(f"  {'variant':<40}{'TUNE':>7}{'DD':>5}{'HOLD':>7}{'DD':>5}{'worst':>7}"
          f"{'d TUNE':>13}{'d HOLD':>13}")

    def show(lab, R_, ref=B):
        dt = R_["tune"][:, 0] - ref["tune"][:, 0]; dh = R_["hold"][:, 0] - ref["hold"][:, 0]
        print(f"  {lab:<40}{R_['tune'][:,0].mean():>+6.2f}%{R_['tune'][:,1].mean():>4.0f}%"
              f"{R_['hold'][:,0].mean():>+6.2f}%{R_['hold'][:,1].mean():>4.0f}%{R_['hold'][:,2].mean():>+6.1f}%"
              f"{dt.mean():>+7.2f}+-{dt.std(ddof=1)/np.sqrt(len(dt)):.2f}"
              f"{dh.mean():>+7.2f}+-{dh.std(ddof=1)/np.sqrt(len(dh)):.2f}")
        return R_

    show("tight + time stop (base)", B)
    res = {}
    for mb, mr in ((1.5, 0.5), (2.0, 1.0), (2.0, 0.5)):
        res[(mb, mr)] = show(f"DIAL long x{mb} bull / x{mr} bear", score(dial(base, reg, mb, mr), bear, cut))
    print("\n  drawdown-matched uniform controls (every long x m):")
    ctrl = {}
    for m in (0.8, 1.0, 1.2, 1.4, 1.6, 1.8):
        ctrl[m] = show(f"UNIFORM long x{m}", score(uniform(base, m), bear, cut))

    def matched(Rd):
        """interpolate the uniform control's return at the dial's drawdown, per half"""
        out = []
        for half in ("tune", "hold"):
            ms = sorted(ctrl)
            dds = np.array([ctrl[m][half][:, 1].mean() for m in ms])
            rets = np.array([ctrl[m][half][:, 0].mean() for m in ms])
            o = np.argsort(dds)
            out.append(float(np.interp(Rd[half][:, 1].mean(), dds[o], rets[o])))
        return out

    print("\n  THE TEST - dial vs a uniform bet at the SAME drawdown:")
    for k, Rd in res.items():
        mt, mh = matched(Rd)
        print(f"    x{k[0]} bull / x{k[1]} bear: tune {Rd['tune'][:,0].mean():+.2f} vs uniform {mt:+.2f} "
              f"({Rd['tune'][:,0].mean() - mt:+.2f}) | hold {Rd['hold'][:,0].mean():+.2f} vs uniform "
              f"{mh:+.2f} ({Rd['hold'][:,0].mean() - mh:+.2f})")

    print("\n  STOP: tighten open longs when the regime turns BEAR (on top of the BTC 4h break):")
    show("tight + time stop + BEAR tighten", score(stop_rows(reg), bear, cut))


def main_stop():
    """Just the STOP variant (the first run's DIAL table is in logs/btc_dial.txt)."""
    bear = regimes()[1000]
    ts = pd.DatetimeIndex(sorted(x[0] for x in sleeve_sided("1h")[0]))
    cut = ts[int(len(ts) * 0.6)]
    reg = regime()
    B = score(book_rows(tight=True, time_stop=TS), bear, cut)
    S = score(stop_rows(reg), bear, cut)
    for lab, R_ in (("tight + time stop (base)", B), ("  + tighten on BEAR regime", S)):
        print(f"  {lab:<34} tune {R_['tune'][:,0].mean():+.2f}% DD {R_['tune'][:,1].mean():.0f}% "
              f"worst {R_['tune'][:,2].mean():+.1f}% | hold {R_['hold'][:,0].mean():+.2f}% "
              f"DD {R_['hold'][:,1].mean():.0f}% worst {R_['hold'][:,2].mean():+.1f}%")
    for half in ("tune", "hold"):
        d = S[half][:, 0] - B[half][:, 0]
        print(f"  paired {half}: {d.mean():+.2f} +- {d.std(ddof=1)/np.sqrt(len(d)):.2f} %/mo")


if __name__ == "__main__" and "--stop" in sys.argv:
    main_stop()
elif __name__ == "__main__":
    main()
