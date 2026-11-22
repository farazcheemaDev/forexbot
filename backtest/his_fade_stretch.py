"""Does the NASDAQ trader fade a STRETCHED 1-2 hour move? (2026-11-13)

WHY: on 2026-11-12 (his newest statement) he sold NASDAQ at 09:38 UTC near the top of a +90-point run that began at 09:00, and bought gold at
09:47 UTC after a -43 run from 07:00 bottomed at 09:10 - both look like fading the last hour or two at its extreme. his_direction.py tested
following / fading the prior move at 15 s - 30 min (no lean, 44-59%) and his_day_extreme.py the DAY's high / low (wrong). The 1-2 hour
horizon and the position inside the last 1-2 hours' range were never tested. Outside data only (Exness ticks via MT5, 2026-01 on).

MEASURES at his entry second t, sign-aligned to HIS side (+ = the prior move went his way, i.e. he FOLLOWED it):
  r60, r120     mid(t) - mid(t - 60 / 120 min)
  pos120        where mid(t) sits in the last 120 minutes' mid range, 0 = the end AGAINST his side (bottom for a sell, top for a buy) ..
                1 = the end his side fades (top for a sell, bottom for a buy). Fading the stretch => pos120 near 1.
CONTROL: the same measures at 40 moments of the same day, 30-180 min from his entry, same side (his_local.py's idea). Each entry gets a rank
(0..1) of its value among its controls; 0.5 = ordinary. Wilcoxon over entries.
CLOCK: statement times are UTC+4 before 2026-03-29 (his_strategy s35), UTC+5 from then on, and UTC+5 on 2026-11-12 (s74).

REGISTERED BEFORE THE RUN (2026-11-13)
  F1  NASDAQ pos120 rank > 0.5 (he sells high in the 2-hour range / buys low), p < 0.05.                              (30%)
  F2  NASDAQ r60 / r120 rank < 0.5 (he fades the 1-2 hour move), p < 0.05 for either.                                 (25%)
  F3  Gold shows the same as NASDAQ for pos120 (same sign of rank - 0.5).                                            (50%)
  F4  Whatever F1 shows, the FADE side as a rule (sell the top quarter of the 2-hour range, buy the bottom quarter) on random NASDAQ moments
      loses after the spread (+-7 race on the mid, entry at the bid / ask).                                          (85%)

RESULT (2026-11-13, logs/his_fade_stretch.txt) - NASDAQ: NO fade of the 1-2 hour stretch; gold: yes, but gold has no edge. F3, F4 right; F1, F2 wrong.
  NASDAQ (53 entries incl. the 7 new): pos120 rank 0.545 (p 0.26), r60 0.480 (p 0.55), r120 0.426 (p 0.10); 36% of entries in the faded quarter
  of the 2-hour range; followed the 1-hour move 51%. The three 2026-11-12 sells ranked 0.93-0.97 (near the top) - that day, not his habit.
  Gold (43): pos120 rank 0.661 (p 0.002), r120 0.367 (p 0.005) - he buys low / sells high in the 2-hour range, but 37 of 41 statement gold trades
  are one 48-minute sitting, so the entries are not independent and the p values overstate; his gold race record is 51%.
  As a rule, fading the stretch (pos120 >= 0.75) on random NASDAQ moments of his days wins the +-7 race 37.9% after the spread (n 1,074).
  Same session, a ticket-counter check (no file; the 20 open tickets of his_open_tickets.py): the broker's order rate in the minutes right after
  his entries (median 3.6 a minute, 20 windows) is not above other windows of his sittings (median 5.0, 51); at the same clock hours 6.3 vs 4.8
  (11 vs 34 windows, not significant) - no sign of a crowd entering with him, on a sample too small to exclude one.

    python -m backtest.his_fade_stretch
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / "logs" / "his_fade_stretch.txt"
CHANGE = pd.Timestamp("2026-03-29")
NEW = [("NASDAQ Dec", "SELL", "2026-11-12 14:38:38"), ("NASDAQ Dec", "SELL", "2026-11-12 14:44:57"), ("GOLD", "BUY", "2026-11-12 14:47:05"),
       ("NASDAQ Dec", "SELL", "2026-11-12 15:00:57"), ("GOLD", "BUY", "2026-11-12 15:02:55")]
RNG = np.random.default_rng(7)


def entries() -> pd.DataFrame:
    x = pd.read_csv(ROOT / "strategy_analysis" / "statement_trades.csv")[["symbol", "side", "open_time"]]
    n = pd.read_csv(ROOT / "logs" / "his_new_trades.csv")
    n = pd.DataFrame({"symbol": "NASDAQ Dec", "side": n.side, "open_time": n.date + " " + n.open})
    x = pd.concat([x, n, pd.DataFrame(NEW, columns=["symbol", "side", "open_time"])], ignore_index=True).drop_duplicates()
    x["local"] = pd.to_datetime(x.open_time)
    x["utc"] = x.local - pd.to_timedelta(np.where(x.local < CHANGE, 4, 5), unit="h")
    x["mk"] = np.where(x.symbol.str.startswith("NASDAQ"), "USTECm", np.where(x.symbol == "GOLD", "XAUUSDm", ""))
    x["s"] = np.where(x.side.str.upper().str.startswith("B"), 1, -1)
    return x[x.mk != ""].sort_values("utc", kind="stable").reset_index(drop=True)


def ticks(mt5, sym, a, b):
    tk = mt5.copy_ticks_range(sym, a.tz_localize("UTC").to_pydatetime(), b.tz_localize("UTC").to_pydatetime(), mt5.COPY_TICKS_ALL)
    if tk is None or len(tk) < 100:
        return None
    return pd.DataFrame({"t": pd.to_datetime(tk["time_msc"], unit="ms"), "bid": tk["bid"], "ask": tk["ask"]})


def measure(sec_t: np.ndarray, mid: np.ndarray, t: pd.Timestamp, s: int):
    """r60, r120, pos120 at t for side s from a 1-second mid series (sec_t sorted, datetime64)."""
    def at(x):
        i = np.searchsorted(sec_t, np.datetime64(x), "right") - 1
        return mid[i] if i >= 0 else np.nan
    m0 = at(t)
    a = np.searchsorted(sec_t, np.datetime64(t - pd.Timedelta(minutes=120)))
    b = np.searchsorted(sec_t, np.datetime64(t), "right")
    w = mid[a:b]
    if len(w) < 600 or not np.isfinite(m0):
        return None
    lo, hi = w.min(), w.max()
    pos = (m0 - lo) / (hi - lo) if hi > lo else 0.5
    pos_fade = pos if s == -1 else 1 - pos                  # 1 = at the end his side fades
    return s * (m0 - at(t - pd.Timedelta(minutes=60))), s * (m0 - at(t - pd.Timedelta(minutes=120))), pos_fade


def race(tb: pd.DataFrame, t: pd.Timestamp, s: int, k: float = 7.0) -> float:
    i = np.searchsorted(tb.t.values, np.datetime64(t), "right") - 1
    if i < 0:
        return np.nan
    e = tb.ask.values[i] if s == 1 else tb.bid.values[i]
    path = s * ((tb.bid.values[i:] if s == 1 else tb.ask.values[i:]) - e)
    up, dn = np.flatnonzero(path >= k), np.flatnonzero(path <= -k)
    if not len(up) and not len(dn):
        return np.nan
    return 1.0 if len(up) and (not len(dn) or up[0] < dn[0]) else 0.0


def main():
    import MetaTrader5 as mt5
    assert mt5.initialize(), mt5.last_error()
    X = entries()
    rows, fade_rule = [], []
    for day, g in X.groupby([X.utc.dt.date, X.mk]):
        d0, mk = pd.Timestamp(day[0]), day[1]
        tb = ticks(mt5, mk, d0 - pd.Timedelta(hours=3), d0 + pd.Timedelta(hours=27))
        if tb is None:
            continue
        sec = tb.set_index("t")[["bid", "ask"]].resample("1s").last().dropna()
        st, mid = sec.index.values, ((sec.bid + sec.ask) / 2).to_numpy()
        for r in g.itertuples():
            me = measure(st, mid, r.utc, r.s)
            if me is None:
                continue
            ctl = []
            for _ in range(200):
                off = pd.Timedelta(minutes=float(RNG.uniform(30, 180))) * (1 if RNG.random() < 0.5 else -1)
                c = measure(st, mid, r.utc + off, r.s)
                if c is not None:
                    ctl.append(c)
                if len(ctl) >= 40:
                    break
            if len(ctl) < 20:
                continue
            C = np.array(ctl)
            rk = [(np.sum(C[:, j] < me[j]) + 0.5 * np.sum(C[:, j] == me[j])) / len(C) for j in range(3)]
            rows.append(dict(mk=mk, utc=r.utc, s=r.s, r60=me[0], r120=me[1], pos=me[2], rk60=rk[0], rk120=rk[1], rkpos=rk[2], new=r.utc > pd.Timestamp("2026-10-01")))
        if mk == "USTECm":                                    # F4: the fade rule at random moments of the same day
            for _ in range(60):
                t = d0 + pd.Timedelta(seconds=float(RNG.uniform(3 * 3600, 21 * 3600)))
                for s in (1, -1):
                    me = measure(st, mid, t, s)
                    if me is not None and me[2] >= 0.75:
                        fade_rule.append(race(tb, t, s))
    mt5.shutdown()
    R = pd.DataFrame(rows)
    L = [f"backtest/his_fade_stretch.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; entries measured {len(R)} (NASDAQ {int((R.mk == 'USTECm').sum())}, "
         f"gold {int((R.mk == 'XAUUSDm').sum())}); 40 same-day controls each, 30-180 min away, same side", ""]
    P = {}
    for mk, g in R.groupby("mk"):
        L.append(f"{mk}  n {len(g)}  (new since Oct: {int(g.new.sum())})")
        for c, lab in (("rk60", "r60  (1h move, rank; < 0.5 = he fades it)"), ("rk120", "r120 (2h move, rank)"), ("rkpos", "pos120 (rank; > 0.5 = at the faded end)")):
            v = g[c].to_numpy()
            p = stats.wilcoxon(v - 0.5).pvalue if len(v) > 5 else np.nan
            P[(mk, c)] = (v.mean(), p)
            L.append(f"  {lab:<44} mean rank {v.mean():.3f}  median {np.median(v):.3f}  Wilcoxon p {p:.3f}   new trades: {', '.join(f'{z:.2f}' for z in g[g.new][c])}")
        L.append(f"  raw: his entries pos120 mean {g.pos.mean():.2f} (0 = end against him, 1 = faded end); in the faded quarter (>= 0.75): {(g.pos >= 0.75).mean() * 100:.0f}%;"
                 f" r60 his way (followed) {(g.r60 > 0).mean() * 100:.0f}%")
    fr = np.array([v for v in fade_rule if np.isfinite(v)])
    L += ["", f"F4  the fade rule on random NASDAQ moments of his days (pos120 >= 0.75, the faded side, +-7 race at bid / ask): n {len(fr)}, won {fr.mean() * 100:.1f}% "
          "(break-even 50%)"]
    nq = lambda c: P.get(("USTECm", c), (np.nan, np.nan))
    gd = P.get(("XAUUSDm", "rkpos"), (np.nan, np.nan))
    L += ["", "PREDICTIONS",
          f"  F1 NASDAQ pos120 rank > 0.5, p < 0.05 ({nq('rkpos')[0]:.3f}, p {nq('rkpos')[1]:.3f}) -> {'RIGHT' if nq('rkpos')[0] > 0.5 and nq('rkpos')[1] < 0.05 else 'WRONG'}",
          f"  F2 NASDAQ fades r60 / r120 ({nq('rk60')[0]:.3f} p {nq('rk60')[1]:.3f}; {nq('rk120')[0]:.3f} p {nq('rk120')[1]:.3f}) -> "
          f"{'RIGHT' if min((nq(c)[1] if nq(c)[0] < 0.5 else 1) for c in ('rk60', 'rk120')) < 0.05 else 'WRONG'}",
          f"  F3 gold pos120 same sign as NASDAQ ({gd[0] - 0.5:+.3f} vs {nq('rkpos')[0] - 0.5:+.3f}) -> {'RIGHT' if np.sign(gd[0] - 0.5) == np.sign(nq('rkpos')[0] - 0.5) else 'WRONG'}",
          f"  F4 the fade rule loses after the spread ({fr.mean() * 100:.1f}% < 50%) -> {'RIGHT' if fr.mean() < 0.5 else 'WRONG'}"]
    txt = "\n".join(L)
    LOG.write_text(txt + "\n", encoding="utf-8")
    R.to_csv(ROOT / "logs" / "his_fade_stretch_rows.csv", index=False)
    print(txt)


if __name__ == "__main__":
    sys.exit(main())
