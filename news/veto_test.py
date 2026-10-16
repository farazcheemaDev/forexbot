"""SENTIMENT ENGINE, phase E1: would a NEWS VETO have improved the bot's books? (2026-10-16, docs/25)

news/impact.py found coin-specific events after which the coin fell against BTC for days (monitoring tag, launchpool /
seed-tag tokens, Binance adding a token to Margin / Futures, delistings). The final machine's daily Bollinger book and
capit2 buy coins of the PIT top-40 - exactly where new and weak tokens appear. The rule tested here:
    VETO  do not open a long in a coin if a NEGATIVE-type event named that coin in the N days before the entry
          (N = 3 / 7 / 14 / 30). Negative types are fixed in advance from the impact table's TUNE half only:
          NEG below (types whose tune-half 72h mean was <= -200bp).
BOOKS  the daily book (20-day-mean exit, final_books DAILY) and capit2 (coin -10% + limit -2%), 8 slots, their own
       allocators and 10 orderings x phases, as in final_machine.py. Trades before the news history starts are kept
       (they cannot be vetoed) - the comparison is only fair from the first event onward, so it is reported from there.
REPORTED  how many trades a veto removes, their average return vs the rest, and each book's CAGR / fall with and
          without the veto, tune and holdout (by time, the impact table's own cut).

REGISTERED BEFORE THE RUN (2026-10-16)
    V1 the vetoed trades average at least 2 points worse than the kept ones, in the daily book.
    V2 the veto raises the daily book's CAGR on BOTH halves for N = 7 and 14; changes capit2 by < 2 points a year
       (capit2 buys crashes, rarely a newly listed token).
    V3 under 10% of the daily book's trades are vetoed (the effect is a tail cut, not a different book).

    python -m news.veto_test
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest import capit_combos as cc  # noqa: E402
from backtest import daily_combos as dc  # noqa: E402
from backtest import machine_combos as mc  # noqa: E402

EV = ROOT / "strategy_analysis" / "data" / "news" / "events.parquet"
LOG = ROOT / "logs" / "news_veto_test.txt"
NEG = ("monitoring_tag", "delist", "delist_futures", "launchpool", "seed_tag", "adds_products", "list_futures")
NS = (3, 7, 14, 30)


def flags(T, E, n_days):
    """True for trades whose coin had a NEG event in (entry - n_days, entry]."""
    ev = {}
    for r in E.itertuples():
        for c in r.coins.split(","):
            if c:
                ev.setdefault(c, []).append(pd.Timestamp(r.t).value)
    ev = {c: np.sort(np.array(v)) for c, v in ev.items()}
    tin = T.t_in.to_numpy("datetime64[ns]").astype("int64")
    out = np.zeros(len(T), bool)
    for i, (c, t) in enumerate(zip(T.coin.to_numpy(), tin)):
        v = ev.get(c)
        if v is None:
            continue
        j = np.searchsorted(v, t, "right")
        out[i] = j > 0 and t - v[j - 1] <= n_days * 86400 * 10**9
    return out


def cagr(c):
    c = c.dropna()
    yrs = (c.index[-1] - c.index[0]).days / 365.25
    return (c.iloc[-1] / c.iloc[0]) ** (1 / yrs) - 1 if c.iloc[-1] > 0 and yrs > 0.2 else np.nan


def main():
    E = pd.read_parquet(EV)
    E = E[E.etype.isin(NEG) & (E.coins != "")]
    start = pd.Timestamp(E.t.min())
    cut = pd.read_parquet(EV).t.sort_values().iloc[int(len(pd.read_parquet(EV)) * 0.6)]
    books = {"daily": {off: dc.gen(off, dict(dc.BASE, mean_n=20)) for off in dc.PHASES},
             "capit2": {off: cc.gen(off, dict(cc.BASE, **mc.CAPIT_BETTER)) for off in cc.PHASES}}
    lines = [f"news/veto_test.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; {len(E):,} negative coin events "
             f"({', '.join(NEG)}) from {start:%Y-%m-%d}; tune/holdout cut {cut:%Y-%m-%d}; 10 orderings", ""]
    R = {}
    for bk, Ts in books.items():
        lines.append(f"  {bk.upper()} BOOK")
        for n in NS:
            vet_r, keep_r, share = [], [], []
            res = {"base": {"tune": [], "hold": []}, "veto": {"tune": [], "hold": []}}
            for sd in mc.SEEDS:
                off = (dc.PHASES[sd % 3] if bk == "daily" else cc.PHASES[sd % 4])
                T = Ts[off]
                T = T[T.t_in >= start].reset_index(drop=True)
                f = flags(T, E, n)
                vet_r += list(T.net[f])
                keep_r += list(T.net[~f])
                share.append(f.mean())
                for lab, TT in (("base", T), ("veto", T[~f].reset_index(drop=True))):
                    if bk == "daily":
                        c = dc.curve(TT, dc.allocate(TT, sd), off)
                    else:
                        c = cc.curve(TT, dc.allocate(TT.assign(units=None), sd, 2.0))
                    c = c[c.index >= start]
                    res[lab]["tune"].append(cagr(c[c.index < cut]))
                    res[lab]["hold"].append(cagr(c[c.index >= cut]))
            m = {k: {h: float(np.nanmedian(v[h])) for h in v} for k, v in res.items()}
            R[(bk, n)] = dict(vet=np.mean(vet_r) if vet_r else np.nan, keep=np.mean(keep_r), share=np.mean(share), **m)
            r = R[(bk, n)]
            lines.append(f"    N {n:>2} days: vetoed {r['share'] * 100:4.1f}% of trades, their average {r['vet'] * 100:+6.2f}% vs kept "
                         f"{r['keep'] * 100:+5.2f}% | CAGR tune {m['base']['tune'] * 100:+5.0f}% -> {m['veto']['tune'] * 100:+5.0f}%, "
                         f"holdout {m['base']['hold'] * 100:+5.0f}% -> {m['veto']['hold'] * 100:+5.0f}%")
        lines.append("")
    d7, d14 = R[("daily", 7)], R[("daily", 14)]
    v1 = d7["vet"] <= d7["keep"] - 0.02
    v2 = all(d["veto"][h] > d["base"][h] for d in (d7, d14) for h in ("tune", "hold")) and \
        all(abs(R[("capit2", n)]["veto"][h] - R[("capit2", n)]["base"][h]) < 0.02 for n in (7, 14) for h in ("tune", "hold"))
    v3 = d14["share"] < 0.10
    lines += ["REGISTERED PREDICTIONS",
              f"  V1 vetoed daily trades >= 2 points worse (N 7): {d7['vet'] * 100:+.2f}% vs {d7['keep'] * 100:+.2f}% -> {'RIGHT' if v1 else 'WRONG'}",
              f"  V2 daily CAGR up on both halves at N 7 and 14, capit2 within 2 points -> {'RIGHT' if v2 else 'WRONG'}",
              f"  V3 under 10% of daily trades vetoed (N 14): {d14['share'] * 100:.1f}% -> {'RIGHT' if v3 else 'WRONG'}"]
    txt = "\n".join(lines)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
