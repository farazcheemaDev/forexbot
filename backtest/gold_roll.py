"""GOLD: DOES MANAGED MONEY'S PENDING ROLL MOVE THE CALENDAR SPREAD BEFORE FIRST NOTICE? CME OPEN INTEREST BY CONTRACT MONTH x CFTC POSITIONS (2026-10-28)

THE USER (2026-10-28): "gold first" - after backtest/cot_metals.py found no price lean in the CFTC positions alone, and positioning_lean.py said the side that MUST trade at
first notice is knowable but its effect on the price is untested because CME's free feed keeps 5 days. This is that test for gold, on Databento's CME Globex `statistics`
(daily settlement price and open interest for every gold futures month, 2010-06 .. 2026-10-26; pulled 2026-10-28 for $1.01 with the user's go-ahead) and the CFTC
Disaggregated FUTURES-ONLY reports.
THE MECHANISM UNDER TEST. Managed money cannot take delivery, so its net futures position in the delivery month M has to be rolled or closed before first notice day F
(the last trading day of the month before M). A net LONG crowd SELLS M and BUYS the next even month N; a net SHORT crowd BUYS M and SELLS N. That pushes M down
relative to N when the crowd is long (the spread N - M widens) and M up relative to N when the crowd is short (narrows). The OUTRIGHT price need not move at all.
CYCLES  every even delivery month (Feb Apr Jun Aug Oct Dec) of 2010..2026 with data from 20 trading days before F: about 95 cycles. Active month M = the contract with the
  most open interest at t0 = 20 trading days before F; N = the next even month; F = the last trading day (in the data) of the previous month.
  FEATURE (read at t0, known): roll share = managed money's net FUTURES lots (the CFTC report public by the Friday before t0: report date + 3 days < t0) / open interest in M at t0.
  OUTCOMES: dS = change in the spread S = (settle_N - settle_M) / settle_M, in percent, from t0 to F; r = log return of M's settle from t0 to F (the outright);
  stay = M's open interest at F / at t0 (how much had not rolled).
  TRADE VIEW  buy the spread (long N, short M) when the crowd is net long, sell it when net short, from t0's settle to F's; P&L in dollars per 100-ounce spread, $30 charged
  per round trip (a listed calendar spread's tick is $10; more than it costs); t over cycles; tune = the first 60% of cycles, holdout the rest.
REGISTERED BEFORE THE FIRST RUN (2026-10-28; the data seen so far: one week of October 2026 and the CME snapshot of 2026-10-27)
  G1  stay: by F at most 40% of M's open interest remains in every cycle (the roll is mechanical and nearly complete); roll share is unrelated to stay (|IC| < 0.2).
  G2  dS vs roll share has the registered POSITIVE sign (IC > 0; a long crowd widens N - M) - I put 65% on the sign - but is NOT significant at 0.05 (permutation, one-sided).
  G3  The outright r over the same 20 days has no relation to roll share: |IC| < 0.2, p > 0.05.
  G4  The spread trade (direction = the crowd's side) has an average P&L under $30 a cycle after costs and is not positive on both halves.
  G5  Mean dS is positive (contango keeps carrying: M converges to spot while N holds the carry), and does not depend on the crowd's sign by more than 0.05 points.
PASS (a lead, not a book): permutation one-sided p < 0.05 for dS, the same sign of IC on both halves, and the spread trade positive on both halves after $30.

    python -m backtest.gold_roll            build the daily panel from the DBN file (cached) and run the test
    python -m backtest.gold_roll --now      today's gold reading: days to first notice, roll share, and what history says
Writes logs/gold_roll.txt and logs/gold_roll.json.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backtest import cot_metals as cm  # noqa: E402

DBN = ROOT / "strategy_analysis" / "data" / "cme_stats" / "GC_statistics_2010-06_2026-10.dbn.zst"
PANEL = ROOT / "strategy_analysis" / "data" / "cme_stats" / "GC_panel.pkl"
OUT_TXT, OUT_JSON = ROOT / "logs" / "gold_roll.txt", ROOT / "logs" / "gold_roll.json"
CODE = "088691"
FUT_ONLY = "72hh-3qpy"                               # Disaggregated, futures only
CODES = "FGHJKMNQUVXZ"                               # the futures month codes, January .. December
WINDOW = 20                                          # trading days before first notice
EVEN = (2, 4, 6, 8, 10, 12)
SPREAD_COST = 30.0                                   # dollars per 100-ounce spread, round trip
PERMS = 20000
LINES: list = []


def say(s: str = ""):
    print(s, flush=True)
    LINES.append(s)


# ------------------------------------------------------------------ the daily panel

def parse_contract(symbol: str, trade_date: pd.Timestamp) -> tuple:
    """'GCZ6' traded on a given day -> (year, month): the year digit resolved to the one in [trade year, trade year + 9]."""
    m = CODES.index(symbol[2]) + 1
    digit = int(symbol[3:])
    y = trade_date.year + ((digit - trade_date.year) % 10)
    return y, m


def build_panel() -> pd.DataFrame:
    """One row per (trade date, contract month): settle, open interest, cleared volume - the LAST update of each day (final settlement, final open interest)."""
    if PANEL.exists() and PANEL.stat().st_mtime > DBN.stat().st_mtime:
        return pd.read_pickle(PANEL)
    import databento as db
    store = db.DBNStore.from_file(str(DBN))
    keep = []
    for chunk in store.to_df(count=2_000_000):
        chunk = chunk[chunk["stat_type"].isin([3, 6, 9])]
        chunk = chunk[~chunk["symbol"].str.contains("-")]
        keep.append(chunk.reset_index()[["ts_event", "ts_ref", "symbol", "stat_type", "price", "quantity"]])
    df = pd.concat(keep, ignore_index=True)
    df = df.sort_values("ts_event", kind="stable").drop_duplicates(["ts_ref", "symbol", "stat_type"], keep="last")
    df["date"] = pd.to_datetime(df["ts_ref"]).dt.tz_localize(None).dt.normalize()
    settle = df[df.stat_type == 3].pivot(index=["date", "symbol"], columns="stat_type", values="price")[3].rename("settle")
    oi = df[df.stat_type == 9].pivot(index=["date", "symbol"], columns="stat_type", values="quantity")[9].rename("oi")
    vol = df[df.stat_type == 6].pivot(index=["date", "symbol"], columns="stat_type", values="quantity")[6].rename("vol")
    p = pd.concat([settle, oi, vol], axis=1).reset_index()
    p = p[p["symbol"].str.fullmatch(r"GC[FGHJKMNQUVXZ]\d+")]
    ym = [parse_contract(s, d) for s, d in zip(p["symbol"], p["date"])]
    p["cy"], p["cm"] = [a for a, _ in ym], [b for _, b in ym]
    p.to_pickle(PANEL)
    return p


# ------------------------------------------------------------------ cycles

def cycles(panel: pd.DataFrame) -> pd.DataFrame:
    days = pd.DatetimeIndex(np.sort(panel["date"].unique()))
    by_day = {d: g.set_index(["cy", "cm"]) for d, g in panel.groupby("date")}
    fut = cm.cot_frame(CODE, ds=FUT_ONLY)
    rows = []
    for y in range(2010, 2027):
        for m in EVEN:
            prev_y, prev_m = (y - 1, 12) if m == 1 else (y, m - 1)
            in_prev = days[(days.year == prev_y) & (days.month == prev_m)]
            if not len(in_prev):
                continue
            F = in_prev[-1]
            i = days.get_loc(F)
            if i - WINDOW < 0 or F >= days[-1]:
                continue
            t0 = days[i - WINDOW]
            g0, gF = by_day.get(t0), by_day.get(F)
            if g0 is None or gF is None or (y, m) not in g0.index or (y, m) not in gF.index:
                continue
            ny, nm = (y + (m == 12), 2 if m == 12 else m + 2)
            if (ny, nm) not in g0.index or (ny, nm) not in gF.index:
                continue
            oi_all = float(g0["oi"].sum())
            if g0.loc[(y, m), "oi"] < 0.25 * oi_all:               # M must be the active month at t0 (largest OI), not a thin one
                continue
            if g0["oi"].idxmax() != (y, m):
                continue
            s0M, s0N, sFM, sFN = (float(g0.loc[(y, m), "settle"]), float(g0.loc[(ny, nm), "settle"]), float(gF.loc[(y, m), "settle"]), float(gF.loc[(ny, nm), "settle"]))
            avail = fut[(fut.index + pd.Timedelta(days=3)) < pd.Timestamp(t0)]
            if not len(avail):
                continue
            last = avail.iloc[-1]
            net_lots = float(last["mm_long"] - last["mm_short"])
            oi0 = float(g0.loc[(y, m), "oi"])
            rows.append(dict(month=f"{y}-{m:02d}", t0=str(pd.Timestamp(t0).date()), F=str(pd.Timestamp(F).date()), report=str(avail.index[-1].date()), net_lots=net_lots,
                             roll_share=net_lots / oi0, mm_net_pct=float(last["mm_net"]), oi_M=oi0, oi_all=oi_all, share_M=oi0 / oi_all,
                             S0=(s0N - s0M) / s0M * 100, SF=(sFN - sFM) / sFM * 100, dS=((sFN - sFM) / sFM - (s0N - s0M) / s0M) * 100,
                             dS_usd=((sFN - sFM) - (s0N - s0M)) * 100, r=float(np.log(sFM / s0M)), stay=float(gF.loc[(y, m), "oi"]) / oi0,
                             price0=s0M))
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ statistics

def spearman(x, y) -> float:
    ok = ~(np.isnan(x) | np.isnan(y))
    if ok.sum() < 8:
        return float("nan")
    return float(np.corrcoef(pd.Series(x[ok]).rank().values, pd.Series(y[ok]).rank().values)[0, 1])


def perm_p(x, y, obs: float, sign: int, rng, n: int = PERMS) -> float:
    ok = ~(np.isnan(x) | np.isnan(y))
    xr, yr = pd.Series(x[ok]).rank().values, y[ok]
    vals = np.empty(n)
    for k in range(n):
        vals[k] = np.corrcoef(xr, pd.Series(rng.permutation(yr)).rank().values)[0, 1]
    return float((vals >= obs).mean() if sign > 0 else (vals <= obs).mean())


def run(c: pd.DataFrame, rng) -> dict:
    x = c["roll_share"].values
    cut = int(len(c) * 0.6)
    res = dict(n=len(c), first=c["month"].iloc[0], last=c["month"].iloc[-1])
    res["stay_max"], res["stay_med"] = float(c["stay"].max()), float(c["stay"].median())
    res["ic_stay"] = spearman(x, c["stay"].values)
    ic = spearman(x, c["dS"].values)
    res["dS"] = dict(ic=ic, tune=spearman(x[:cut], c["dS"].values[:cut]), hold=spearman(x[cut:], c["dS"].values[cut:]), p=perm_p(x, c["dS"].values, ic, +1, rng),
                     mean=float(c["dS"].mean()), mean_long=float(c.loc[c.roll_share > 0, "dS"].mean()), mean_short=float(c.loc[c.roll_share < 0, "dS"].mean()),
                     n_long=int((c.roll_share > 0).sum()), n_short=int((c.roll_share < 0).sum()))
    ic_r = spearman(x, c["r"].values)
    res["r"] = dict(ic=ic_r, p=perm_p(x, c["r"].values, ic_r, +1, rng), mean=float(c["r"].mean()))
    d = np.where(c["roll_share"].values > 0, 1.0, -1.0)
    pnl = d * c["dS_usd"].values - SPREAD_COST
    res["trade"] = dict(mean=float(pnl.mean()), t=float(pnl.mean() / (pnl.std(ddof=1) / np.sqrt(len(pnl)))), hit=float((pnl > 0).mean()), tune=float(pnl[:cut].mean()),
                        hold=float(pnl[cut:].mean()), n=len(pnl))
    return res


def verdict(res: dict) -> str:
    d, t = res["dS"], res["trade"]
    ok = d["p"] < 0.05 and np.sign(d["tune"]) == np.sign(d["hold"]) == 1 and t["tune"] > 0 and t["hold"] > 0
    return "LEAD: the spread moves with the crowd's pending roll" if ok else "NO LEAD: the spread does not reliably move with managed money's pending roll"


# ------------------------------------------------------------------ main

def main():
    if "--now" in sys.argv:
        say("(--now needs the cycle table; run the full test first)")
        return
    say(f"GOLD ROLL TEST - CME open interest by month x CFTC managed money - {pd.Timestamp.utcnow():%Y-%m-%d %H:%M} UTC")
    panel = build_panel()
    say(f"panel: {len(panel):,} contract-days, {panel['date'].nunique():,} trading days {panel['date'].min().date()} .. {panel['date'].max().date()}, {panel['symbol'].nunique()} contracts")
    # sanity: the day the CME web snapshot covers (2026-10-26 total open interest 401,077 = the sum over the outright months)
    chk = panel[panel["date"] == pd.Timestamp("2026-10-26")]
    say(f"check vs the CME page: 2026-10-26 total open interest {chk['oi'].sum():,.0f} (CME's own total 401,077); GCZ6 settle {chk.loc[chk.symbol == 'GCZ6', 'settle'].iloc[0]:.1f}")
    c = cycles(panel)
    say(f"{len(c)} cycles, {c['month'].iloc[0]} .. {c['month'].iloc[-1]}; roll share (managed money net futures lots / the delivery month's open interest) from {c['roll_share'].min():+.2f} to {c['roll_share'].max():+.2f}, "
        f"median {c['roll_share'].median():+.2f}; {int((c.roll_share > 0).sum())} cycles net long, {int((c.roll_share < 0).sum())} net short")
    rng = np.random.default_rng(20261028)
    res = run(c, rng)
    d, t, r = res["dS"], res["trade"], res["r"]
    say("\nG1  open interest still in the delivery month at first notice (share of its t0 level): median %.0f%%, worst cycle %.0f%%; IC with roll share %+.2f"
        % (res["stay_med"] * 100, res["stay_max"] * 100, res["ic_stay"]))
    say(f"G2  spread change t0 -> F (N - M, % of price): IC with roll share {d['ic']:+.3f} (tune {d['tune']:+.3f}, holdout {d['hold']:+.3f}), one-sided permutation p {d['p']:.3f}")
    say(f"G5  mean spread change {d['mean']:+.3f} points; net-long cycles ({d['n_long']}) {d['mean_long']:+.3f}, net-short cycles ({d['n_short']}) {d['mean_short']:+.3f}")
    say(f"G3  outright return over the same days: IC with roll share {r['ic']:+.3f}, p {r['p']:.3f}, mean {r['mean'] * 100:+.2f}%")
    say(f"G4  spread trade in the crowd's direction, ${SPREAD_COST:.0f} charged: mean {t['mean']:+.1f} $/cycle (t {t['t']:+.2f}, hit {t['hit'] * 100:.0f}%), tune {t['tune']:+.1f}, holdout {t['hold']:+.1f}")
    v = verdict(res)
    say(f"\nVERDICT: {v}")
    OUT_TXT.parent.mkdir(exist_ok=True)
    OUT_TXT.write_text("\n".join(LINES) + "\n", encoding="utf-8")
    OUT_JSON.write_text(json.dumps(dict(result=res, verdict=v, cycles=c.to_dict("records")), default=float, indent=1))
    say(f"wrote {OUT_TXT.relative_to(ROOT)} and {OUT_JSON.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
