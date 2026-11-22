"""THE FAST DIRECTION OF THE WHOLE MARKET AS A FILTER ON THE ANALYST DESK'S CALLS (2026-11-21)

THE USER (2026-11-21), after the desk's longs lost 22 of 23 in the crash week: "there must be a way to look at the market as a whole -
sentiment or anything". Tested before: the SLOW market state (BTC's 50-day label, the alt 'fuel', the 30-day alt bleed) as a gate
(analyst_states.py: no gate improves; in money, calls with and against the state did the same), and every market-wide signal at once in
a model (combo_meta.py: 0 of 12). NOT tested: the FAST direction of the whole market - what it did over the last few days - which is
what would have said 'do not buy' in the crash week.
DATA   the desk's replay calls (analyst_states.load: crypto - BTC ETH SOL XRP BNB, 2022-02 .. 2026-09, scored on 1h bars, 12bp); the
       market at the day's open (closes through the day before): the point-in-time top-40 alt index (crash_lessons.backtest_alts: equal
       weight, BTC out), BTC's close, the Fear & Greed index (strategy_analysis/data/fear_greed.csv, the day before). Halves split
       2024-12-07 (the replay's own). A bet = the calls of one UTC day and one side (one market move settles them together).
THE FOUR GATES (each keeps longs only when the market leans up and shorts only when it leans down; the rest are dropped)
  F1 ALTS 3 DAYS    the alt index's return over the last 3 daily bars > 0
  F2 ALTS 7 DAYS    the same over the last 7 bars
  F3 BTC 7 DAYS     BTC's close above its close 7 days earlier
  F4 FEAR & GREED   the index the day before >= 50 (longs only) or < 50 (shorts only): trade WITH the crowd's mood
MEASURE in money: the kept calls' mean net R per bet minus the dropped calls' (Welch t over bets), per half; also the kept calls' own R.
VERDICT  HELPS = kept minus dropped > 0 on BOTH halves and Holm p < 0.05 over the 4 (p from the weaker half's t).
         PAYS  = HELPS and the kept calls earn > 0 R per bet with t >= 2 on both halves - only that would make the desk worth following.
REGISTERED BEFORE THE FIRST NUMBER (2026-11-21; my prior that any gate HELPS ~25%, PAYS ~5%)
  Q1  No gate PAYS.
  Q2  At most one gate HELPS.
  Q3  Each gate keeps 35-65% of the calls.
  Q4  On the live crash week (calls made 11-14 .. 11-20, crypto) F1 and F2 each drop at least 3 in 4 of the longs.

    python -m backtest.analyst_fast_market <the live calls.csv copied from the VM>
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

from backtest import candle_scan as cs  # noqa: E402
from backtest.analyst_states import SPLIT, bets, load, t_mean, welch_t  # noqa: E402

LOG = ROOT / "logs" / "analyst_fast_market.txt"
GATES = ("F1", "F2", "F3", "F4")
NAMES = {"F1": "alts 3 days", "F2": "alts 7 days", "F3": "BTC 7 days", "F4": "Fear & Greed"}


def features(alt: pd.Series, btc: pd.Series, fg: pd.Series) -> pd.DataFrame:
    """Known at the OPEN of each day d: bars through d-1 (a bar indexed d closes at d+1 00:00)."""
    la = np.log1p(alt)
    m = pd.DataFrame(index=alt.index)
    m["alt3"] = np.expm1(la.rolling(3, min_periods=3).sum()).shift(1)
    m["alt7"] = np.expm1(la.rolling(7, min_periods=7).sum()).shift(1)
    b = btc.reindex(alt.index)
    m["btc7"] = (b / b.shift(7) - 1).shift(1)
    m["fg"] = fg.reindex(alt.index).shift(1)
    return m


def keep(g: str, d: pd.DataFrame) -> pd.Series:
    up = {"F1": d.alt3 > 0, "F2": d.alt7 > 0, "F3": d.btc7 > 0, "F4": d.fg >= 50}[g]
    return ((d.side == "long") & up) | ((d.side == "short") & ~up)


def score(d: pd.DataFrame, k: pd.Series) -> dict:
    ba, bb = bets(d[k]), bets(d[~k])
    return dict(share=float(k.mean()), n=int(k.sum()), hit_k=float(d[k].win.mean()), rnd_k=float(d[k].base_p.mean()),
                Rk=float(ba.R.mean()), Rd=float(bb.R.mean()), diff=float(ba.R.mean() - bb.R.mean()),
                diff_t=welch_t(ba.R.to_numpy(), bb.R.to_numpy()), Rk_t=t_mean(ba.R.to_numpy()), bets=len(ba))


def fear_greed_live() -> pd.Series:
    """The public Fear & Greed history (alternative.me, no key) for the live week."""
    try:
        req = urllib.request.Request("https://api.alternative.me/fng/?limit=120&format=json", headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            js = json.loads(r.read())["data"]
        return pd.Series({pd.Timestamp(int(x["timestamp"]), unit="s").normalize(): float(x["value"]) for x in js}).sort_index()
    except Exception as e:  # noqa: BLE001
        print("  Fear & Greed history not fetched:", type(e).__name__)
        return pd.Series(dtype=float)


def live_week(path: Path, L: list) -> dict:
    """The gates applied to the desk's LIVE crypto calls made 11-14 .. 11-20 (descriptive: one week, one market move)."""
    from backtest.crash_lessons import closes, pit_alts
    from backtest.daily_live_vs_backtest import klines_all
    c = pd.read_csv(path)
    c["t"] = pd.to_datetime(c.made_utc)
    c = c[(c.t >= "2026-11-14") & (c.t < "2026-11-21") & ~c.symbol.isin(["XAUUSDT", "QQQUSDT"]) & c.r_net.notna()
          & (c.status != "open")].copy()
    c["day"] = c.t.dt.floor("D")
    c["win"] = (c.status == "WIN").astype(float)
    K = klines_all()
    C = closes(K["K"])
    PA = pit_alts(K["K"], C, "2026-09-25")
    m = features(PA.ret, C["BTCUSDT"], fear_greed_live())
    c = c.merge(m, left_on="day", right_index=True, how="left")
    out = {}
    L.append(f"LIVE CRASH WEEK (desk calls made 11-14 .. 11-20, crypto, closed: {len(c)}; all {c.r_net.sum():+.1f}R, longs "
             f"{c[c.side == 'long'].r_net.sum():+.1f}R in {int((c.side == 'long').sum())}, shorts {c[c.side == 'short'].r_net.sum():+.1f}R "
             f"in {int((c.side == 'short').sum())})")
    for g in GATES:
        if c[["alt3", "alt7", "btc7", "fg"][GATES.index(g)]].isna().all():
            L.append(f"   {g} {NAMES[g]:<13} no data")
            continue
        k = keep(g, c)
        lg = c.side == "long"
        drop_long = float((~k & lg).sum() / max(lg.sum(), 1))
        out[g] = drop_long
        L.append(f"   {g} {NAMES[g]:<13} kept {int(k.sum()):>2} calls {c[k].r_net.sum():+6.1f}R | dropped {int((~k).sum()):>2} "
                 f"{c[~k].r_net.sum():+6.1f}R | longs dropped {drop_long:.0%}")
    return out


def main():
    from backtest.crash_lessons import backtest_alts
    d = load()
    alt, btc = backtest_alts()
    fg = pd.read_csv(ROOT / "strategy_analysis" / "data" / "fear_greed.csv", parse_dates=["date"]).set_index("date").v.sort_index()
    fg.index = pd.DatetimeIndex(fg.index).as_unit("ns")
    m = features(alt, btc, fg)
    m.index = pd.DatetimeIndex(m.index).as_unit("ns")
    d = d.drop(columns=[c for c in d.columns if c.startswith("key_")]).assign(day_ns=d.day.astype("datetime64[ns]"))
    d = d.merge(m, left_on="day_ns", right_index=True, how="left").dropna(subset=["alt3", "alt7", "btc7", "fg"])
    halves = {"tune": d.t < SPLIT, "hold": d.t >= SPLIT}
    L = [f"backtest/analyst_fast_market.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; the desk's replay calls (crypto) x the market's "
         f"FAST direction at the day's open; {len(d)} calls {d.t.min():%Y-%m-%d} .. {d.t.max():%Y-%m-%d}; halves split {SPLIT.date()}; "
         f"a bet = same day + side; money measure = net R per bet", ""]
    for h, msk in halves.items():
        b = bets(d[msk])
        L.append(f"ALL CALLS {h}: {int(msk.sum())} calls, hit {d[msk].win.mean():.1%} vs random {d[msk].base_p.mean():.1%}, "
                 f"R per bet {b.R.mean():+.3f} ({len(b)} bets)")
    L += ["", f"   {'gate':<17}{'half':>5}{'kept':>6}{'hit':>6}{'rnd':>6}{'kept R/bet':>11}{'t':>6}{'dropped R/bet':>14}{'kept-dropped':>13}{'t':>6}"]
    res, p = {}, {}
    for g in GATES:
        res[g] = {}
        for h, msk in halves.items():
            s = res[g][h] = score(d[msk], keep(g, d[msk]))
            L.append(f"   {g + ' ' + NAMES[g]:<17}{h:>5}{s['share']:>6.0%}{s['hit_k']:>6.1%}{s['rnd_k']:>6.1%}{s['Rk']:>+11.3f}"
                     f"{s['Rk_t']:>+6.1f}{s['Rd']:>+14.3f}{s['diff']:>+13.3f}{s['diff_t']:>+6.1f}")
        p[g] = cs.p_one_sided(np.nan_to_num(min(res[g]["tune"]["diff_t"], res[g]["hold"]["diff_t"]), nan=-10.0))
    hp = dict(zip(GATES, cs.holm([p[g] for g in GATES])))
    helps = {g: all(res[g][h]["diff"] > 0 for h in halves) and hp[g] < 0.05 for g in GATES}
    pays = {g: helps[g] and all(res[g][h]["Rk"] > 0 and res[g][h]["Rk_t"] >= 2 for h in halves) for g in GATES}
    L += ["", "   Holm p (kept minus dropped, weaker half): " + ", ".join(f"{g} {hp[g]:.3f}" for g in GATES),
          "   HELPS: " + (", ".join(g for g in GATES if helps[g]) or "none") + "   PAYS: " + (", ".join(g for g in GATES if pays[g]) or "none"), ""]
    lw = live_week(Path(sys.argv[1]), L) if len(sys.argv) > 1 else {}
    share = {g: (res[g]["tune"]["n"] + res[g]["hold"]["n"]) / len(d) for g in GATES}
    ok = lambda b: "RIGHT" if b else "WRONG"  # noqa: E731
    L += ["", "REGISTERED PREDICTIONS",
          f"  Q1 no gate pays -> {ok(not any(pays.values()))}",
          f"  Q2 at most one gate helps -> {ok(sum(helps.values()) <= 1)} ({sum(helps.values())})",
          f"  Q3 each gate keeps 35-65% -> {ok(all(0.35 <= v <= 0.65 for v in share.values()))} ("
          + ", ".join(f"{g} {v:.0%}" for g, v in share.items()) + ")"]
    if lw:
        L.append(f"  Q4 F1 and F2 drop >= 75% of the live week's longs -> {ok(lw.get('F1', 0) >= 0.75 and lw.get('F2', 0) >= 0.75)} "
                 f"(F1 {lw.get('F1', float('nan')):.0%}, F2 {lw.get('F2', float('nan')):.0%})")
    txt = "\n".join(L)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
