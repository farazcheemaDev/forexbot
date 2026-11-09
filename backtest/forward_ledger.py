"""THE FORWARD LEDGER: leads registered on 2026-11-09, replayed on data that did not exist when they were found

THE USER (2026-11-09): "plan the farm" -> "yes, build it". The plan's arithmetic: a lead needs about 4 x its backtest years / its
backtest t^2 of forward data to reach t = 2 on its own (if the forward edge equals the backtest's; half the edge = 4x longer), so no
lead here can be CONFIRMED forward in under ~4-11 years. What a forward record can do sooner: reject a claim that is clearly wrong,
and show the record on the dashboard. Most leads need no live bot for that - their prices land in public history anyway - so this
file re-runs each lead's FROZEN rule (the study file's own functions, pinned by hash) on data after the registration instant, and
writes logs/leads/ledger.json for the dashboard's Leads tab.

THE LEADS (each value is per trade / per event, after the study's own costs)
  gold_nfp       Gold at the US payrolls release (NFP): resting stop orders 5bp above and below the mid 5 s before; the first to
                 trigger is the trade (1 s fill delay, filled at the first tick's ask / bid after it), the other level is its stop; out
                 after 2 hours. gold_news_ticks.straddle on Exness XAUUSDm TICKS (MT5 on the PC), times from ForexFactory.
                 CLAIM +11.1bp a trade (gold_news_ticks.py --rescore: NFP x = 5 with 10bp entry slip, t 2.45, 192 releases
                 2010-26, sd ~62.8bp); ~12 a year.
  nasdaq_ib_buy  NASDAQ 30-minute bars: a new 20-bar LOW, a big mother candle (>= 1 ATR14) and an inside baby (<= half its range);
                 buy-stop at the baby's high (live 4 bars), stop at the mother's low, target 2R, out after 24 hours.
                 inside_bar_break's mirror + bars30 + signals + trade_touch on HistData NSXUSD minute bars (1.27bp + 2bp stop slip).
                 CLAIM +0.079R a trade (inside_bar_break.py, long touch 2R look 20, 889 trades 2010-26, excess over random
                 entries t +2.34 / +3.01; sd 1.43R, 56 a year - from this file's --check).
  pre_fomc       Long NASDAQ from 24 hours before each FOMC statement to 5 minutes before it, 1.27bp (swap-free).
                 fx_daily_families.at on HistData NSXUSD closes, statement times from ForexFactory.
                 CLAIM +0.25% a trade (fx_daily_families.py D4, t 3.14, 128 statements 2010-26, sd ~0.90%); 8 a year.
  NOT HERE: the daily-zone shorts (sweep_zone_more: +0.44R, t 1.64 on their own top-40 coins = ~10 years forward, ~11 trades a
  year carried by a few crash days, and a replay needs the whole perp archive refreshed); the maker BTC -> DOGE model (its family
  is dead: passive_markout.py); the FOMC range break (8 a year, ~10 years). RSI-80, the crowd book, the Analyst sweet spot and the
  machine's books already run live; the Leads tab reads them from the feed.

REGISTERED 2026-11-08 ~22:45 UTC, BEFORE the forward window opens. FORWARD FROM 2026-11-09 00:00 UTC: an event counts only if its
ENTRY is at or after that instant, and only once its exit has happened (a trade still open is not scored).
LINES (the same for every lead)
  n < 5                                   -> TOO EARLY
  forward mean < CLAIM - 2 x sd / sqrt(n) -> DEAD: the forward record rejects the backtest claim (sd = the backtest's per-trade sd)
  forward t vs zero >= 2 and Holm-adjusted one-sided p < 0.05 across the ledger's 3 leads -> CONFIRMED
  otherwise KEEP RECORDING: 'on track' if the mean is at least half the claim, 'below the claim' if not.
  Years to CONFIRMED at the claimed edge: 4 x (sd / claim)^2 / events a year (printed beside each lead).
RULE PIN  REGISTRY_SHA256 covers the leads, the lines and the instant; RULE_SHA256 covers the source of every study function
          used and its constants. A replay whose rule hash differs from the pin reports RULE CHANGED and no numbers.
DATA      the study files are NOT touched: new HistData months go to strategy_analysis/data/forward/ and are added in memory;
          ForexFactory months to forward/ff_forward.csv; Exness ticks to gold_news_ticks' own per-event cache.

    python -m backtest.forward_ledger           (on the PC with MT5 open: refresh, replay, write logs/leads/ledger.json)
    python -m backtest.forward_ledger --check   (parity: each replay on its study's own window reproduces the study;
                                                 logs/forward_ledger_check.txt: 889 trades +0.0792R / 128 statements +0.250% t +3.14 /
                                                 8 of 8 2026 payroll releases equal to gold_news_ticks.csv)
"""
from __future__ import annotations

import hashlib
import inspect
import json
import sys
import time
from math import sqrt
from pathlib import Path
from statistics import NormalDist

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest import fx_daily_families as fdf  # noqa: E402
from backtest import gold_news_ticks as gnt  # noqa: E402
from backtest import inside_bar_break as ibb  # noqa: E402

FWD = ROOT / "strategy_analysis" / "data" / "forward"
LEDGER = ROOT / "logs" / "leads" / "ledger.json"
LOG = ROOT / "logs" / "forward_ledger.txt"
FORWARD_FROM_MS = 1794182400000                    # 2026-11-09 00:00 UTC
REGISTERED = "2026-11-08 22:45 UTC"
N_MIN = 5
GOLD_X, GOLD_LAT = 5, 1.0
IB_K, IB_LOOK = 2, 20
FOMC_COST = 1.27e-4
NFP_NAME, FOMC_NAME = "Non-Farm Employment Change", "FOMC Statement"
LEADS = {
    "gold_nfp": dict(name="Gold payrolls straddle", unit="bp", claim=11.1, sd=62.8, per_year=12.0,
                     what="At each US payrolls release: stop orders 5bp above and below gold's price; the first to trigger is the "
                          "trade, the other level its stop; out after 2 hours.",
                     claim_src="gold_news_ticks.py --rescore: +11.1bp a trade, t 2.45, 192 releases 2010-26",
                     data="Exness gold ticks (MT5 on the PC)"),
    "nasdaq_ib_buy": dict(name="NASDAQ inside-bar buy", unit="R", claim=0.079, sd=1.43, per_year=56.0,
                          what="30-minute NASDAQ: a new low, a big candle and a small one inside it; buy when the small one's high "
                               "breaks, stop at the big one's low, target 2R, out after 24 hours.",
                          claim_src="inside_bar_break.py: +0.079R a trade, 889 trades 2010-26, beats random entries t +2.3 / +3.0",
                          data="HistData NASDAQ minute bars (monthly)"),
    "pre_fomc": dict(name="NASDAQ before the Fed", unit="%", claim=0.25, sd=0.90, per_year=8.0,
                     what="Long NASDAQ from 24 hours before each Fed (FOMC) statement until 5 minutes before it.",
                     claim_src="fx_daily_families.py D4: +0.25% a trade, t 3.14, 128 statements 2010-26",
                     data="HistData NASDAQ minute bars + ForexFactory's Fed times"),
}
REGISTRY_SHA256 = "61abd5758000d696e9b6008fc4265963d957dcfcb65eb2c73afc82e538f3ccdf"
RULE_SHA256 = "00862ed40a3731deac660f191d92696cd2ff5a912098cec30d1785f3efb886f6"


# ---------------------------------------------------------------- pins

def registry_digest() -> str:
    blob = json.dumps(dict(leads=LEADS, forward_from=FORWARD_FROM_MS, n_min=N_MIN, gold=(GOLD_X, GOLD_LAT), ib=(IB_K, IB_LOOK),
                           fomc_cost=FOMC_COST, names=(NFP_NAME, FOMC_NAME)), sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()


def rule_digest() -> str:
    """The source of every study function the replays call, and the constants they read."""
    src = [inspect.getsource(f) for f in (gnt.at_or_after, gnt.straddle, ibb.mirror, ibb.bars30, ibb.signals, ibb.trade_touch,
                                           ibb.manage, fdf.at)]
    const = repr((gnt.EXIT_S, ibb.LOOK, ibb.BIG, ibb.BABY, ibb.WAIT, ibb.HOLD_MIN, ibb.STOP_SLIP, ibb.COST["NSXUSD"], ibb.SLOT, ibb.MIN))
    return hashlib.sha256(("\n".join(src) + const).encode()).hexdigest()


# ---------------------------------------------------------------- replays (pure: data in, trades out)

def replay_gold(times_s, fetch_ticks, since_ms, now_s):
    """One trade per release at or after since_ms whose 2-hour exit has passed; [dict(t ms, value bp, note)]."""
    out = []
    for t0 in sorted(set(float(x) for x in times_s)):
        if t0 * 1000 < since_ms or t0 + gnt.EXIT_S + 120 > now_s:
            continue
        tk = fetch_ticks(t0)
        if tk is None:
            continue
        ts, bid, ask = tk
        r = gnt.straddle(ts, bid, ask, t0, GOLD_X, GOLD_LAT)
        if r is None:
            continue
        note = f"{'long' if r['side'] > 0 else 'short'}, fill {r['slip_bp']:+.1f}bp past the level{', stopped' if r['stopped'] else ''}"
        out.append(dict(t=int(t0 * 1000), value=float(r["net_bp"]), note=note))
    return out


def replay_ib(t, o, h, l, c, since_ms):  # noqa: E741
    """Every buy-side TOUCH trade (target 2R, look 20) whose entry minute is at or after since_ms and whose 24 hours are complete."""
    T_, O_, H_, L_, C_ = ibb.mirror(t, o, h, l, c)
    bars = ibb.bars30(T_, O_, H_, L_, C_)
    bs = bars[0]
    jb, Sx, Lx = ibb.signals(*bars, look=IB_LOOK)
    costf = ibb.COST["NSXUSD"] / 1e4
    out = []
    for j, s_, l_ in zip(jb, Sx, Lx):
        tr = ibb.trade_touch(T_, O_, H_, L_, C_, bs[j], s_, l_, IB_K, costf)
        if tr is None:
            continue
        r, rf, mm = tr
        if T_[mm] < since_ms or T_[mm] + ibb.HOLD_MIN * ibb.MIN > T_[-1]:
            continue
        out.append(dict(t=int(T_[mm]), value=float(r), note=f"stop {rf * 100:.2f}% below the entry"))
    return out


def replay_fomc(t, c, times_s, since_ms):
    """Long from 24 h before each statement to 5 min before; % after FOMC_COST. Entry (24 h before) must be at or after since_ms."""
    out = []
    for st in sorted(set(float(x) for x in times_s)):
        e0, e1 = int((st - 86400) * 1000), int((st - 300) * 1000)
        if e0 < since_ms or len(t) == 0 or t[-1] < e1 or t[0] > e0:
            continue
        a, b = fdf.at(t, c, np.array([e0])), fdf.at(t, c, np.array([e1]))
        if not (np.isfinite(a[0]) and np.isfinite(b[0])):
            continue
        out.append(dict(t=e0, value=float((b[0] / a[0] - 1 - FOMC_COST) * 100), note=""))
    return out


# ---------------------------------------------------------------- the lines

def judge(values, claim, sd, n_min=N_MIN):
    """Per-lead numbers and status before the family correction ('CONFIRMED?' is settled by holm_confirm)."""
    v = np.asarray(values, float)
    n = len(v)
    d = dict(n=n, mean=float(v.mean()) if n else None, t=None, p=None, dead_line=None)
    if n < n_min:
        d["status"] = "too early"
        return d
    s = float(v.std(ddof=1)) if n > 1 else 0.0
    d["t"] = float(v.mean() / (s / sqrt(n))) if s > 0 else (float("inf") if v.mean() > 0 else float("-inf"))
    d["p"] = 1 - NormalDist().cdf(d["t"]) if np.isfinite(d["t"]) else (0.0 if d["t"] > 0 else 1.0)
    d["dead_line"] = claim - 2 * sd / sqrt(n)
    if d["mean"] < d["dead_line"]:
        d["status"] = "dead"
    else:
        d["status"] = "on track" if d["mean"] >= claim / 2 else "below the claim"
    return d


def holm_confirm(results: dict) -> dict:
    """CONFIRMED where t >= 2 and the Holm-adjusted one-sided p over every lead that has a p is < 0.05 (dead ones stay dead)."""
    ks = [k for k, r in results.items() if r.get("p") is not None]
    ps = sorted((results[k]["p"], k) for k in ks)
    m, run = len(ps), 0.0
    for i, (p, k) in enumerate(ps):
        run = max(run, min(1.0, (m - i) * p))
        results[k]["p_holm"] = run
        if results[k]["status"] != "dead" and results[k]["t"] >= 2 and run < 0.05:
            results[k]["status"] = "confirmed"
    return results


def years_to_confirm(claim, sd, per_year):
    return 4 * (sd / claim) ** 2 / per_year


# ---------------------------------------------------------------- data (PC only)

def ff_month_names(since_ms, now_ms):
    a = pd.Timestamp(since_ms, unit="ms").to_period("M")
    b = pd.Timestamp(now_ms, unit="ms").to_period("M") + 1
    return [p.strftime("%b.%Y").lower() for p in pd.period_range(a, b, freq="M")]


def refresh_calendar(since_ms, now_ms):
    from backtest import ff_calendar as ffc
    FWD.mkdir(parents=True, exist_ok=True)
    f = FWD / "ff_forward.csv"
    old = pd.read_csv(f, parse_dates=["utc"], keep_default_na=False) if f.exists() else pd.DataFrame()
    rows = []
    for m in ff_month_names(since_ms, now_ms):
        try:
            rows += [dict(r, month=m) for r in ffc.fetch_month(m)]
            time.sleep(2)
        except Exception as e:  # noqa: BLE001 - keep what was cached for that month
            print(f"ForexFactory {m}: {type(e).__name__}", flush=True)
            if len(old):
                rows += old[old.month == m].to_dict("records")
    d = pd.DataFrame(rows)
    if len(d):
        d.to_csv(f, index=False)
    return d


def epoch_s(x) -> list:
    """Seconds since 1970 for anything pandas reads as a UTC time. Forced to ns first: pandas 3 parses strings to [us], and
    int64 // 10**9 on microseconds put every date in 1970 (first --check run: 0 Fed statements found)."""
    s = pd.to_datetime(pd.Series(list(x)), utc=True, format="ISO8601")
    return [int(v) for v in s.dt.as_unit("ns").astype("int64") // 10**9]


def event_times(cal: pd.DataFrame, name: str):
    if cal is None or not len(cal):
        return []
    x = cal[(cal.currency == "USD") & (cal.name == name)]
    return sorted(set(epoch_s(x.utc)))


def refresh_histdata(pair: str, now_ms: int):
    """New full or partial months after the study file's last bar, kept in forward/<pair>_fwd.parquet (study file untouched)."""
    from backtest import histdata_1m as hd
    FWD.mkdir(parents=True, exist_ok=True)
    base = pd.read_parquet(ibb.HD / f"{pair}.parquet", columns=["t"])
    last = int(base.t.max())
    f = FWD / f"{pair}_fwd.parquet"
    have = pd.read_parquet(f) if f.exists() else pd.DataFrame(columns=["t", "o", "h", "l", "c"])
    # from the last bar's OWN month: HistData months are New York months, so the study file's last bar (Sep 30 23:58 New York)
    # is stamped 2026-10-01 UTC, and starting one month later skipped all of October (first real run, 2026-11-08)
    a = pd.Timestamp(last, unit="ms").to_period("M")
    b = pd.Timestamp(now_ms, unit="ms").to_period("M")
    parts = [have]
    for p in pd.period_range(a, b, freq="M") if a <= b else []:
        try:
            parts.append(hd.parse(hd.fetch_zip(pair, p.year, p.month)))
            time.sleep(2)
        except Exception as e:  # noqa: BLE001 - a month not published yet
            print(f"HistData {pair} {p}: {type(e).__name__}", flush=True)
    d = pd.concat(parts).astype({"t": "int64"}).sort_values("t", kind="stable").drop_duplicates("t", keep="last")
    d = d[d.t > last]
    d.to_parquet(f, index=False)
    return d


def minutes(pair: str):
    d = pd.read_parquet(ibb.HD / f"{pair}.parquet")
    f = FWD / f"{pair}_fwd.parquet"
    if f.exists():
        d = pd.concat([d, pd.read_parquet(f)])
    d = d.sort_values("t", kind="stable").drop_duplicates("t", keep="last")
    return [d[k].to_numpy(np.int64) if k == "t" else d[k].to_numpy(float) for k in ("t", "o", "h", "l", "c")]


# ---------------------------------------------------------------- run

def summarise(trades: dict, rule_ok: bool) -> dict:
    res = {}
    for k, lead in LEADS.items():
        if not rule_ok:
            res[k] = dict(n=0, mean=None, t=None, p=None, status="RULE CHANGED")
            continue
        res[k] = judge([x["value"] for x in trades.get(k, [])], lead["claim"], lead["sd"])
    return holm_confirm(res)


def ledger_json(trades: dict, res: dict, now_ms: int, data: dict) -> dict:
    out = []
    for k, lead in LEADS.items():
        r = res[k]
        out.append(dict(id=k, **{f: lead[f] for f in ("name", "unit", "claim", "sd", "per_year", "what", "claim_src", "data")},
                        years=round(years_to_confirm(lead["claim"], lead["sd"], lead["per_year"]), 1),
                        n=r["n"], mean=r["mean"], t=r["t"], p_holm=r.get("p_holm"), dead_line=r.get("dead_line"), status=r["status"],
                        events=[dict(t=x["t"], value=round(x["value"], 4), note=x.get("note", "")) for x in trades.get(k, [])][-30:][::-1]))
    return dict(generated=int(now_ms // 1000), forward_from=FORWARD_FROM_MS // 1000, registered=REGISTERED, n_min=N_MIN,
                registry_ok=registry_digest() == REGISTRY_SHA256, rule_ok=rule_digest() == RULE_SHA256, data=data, leads=out)


def main():
    now_ms = int(time.time() * 1000)
    rule_ok = rule_digest() == RULE_SHA256
    assert registry_digest() == REGISTRY_SHA256, "the registry was edited after it was pinned"
    cal = refresh_calendar(FORWARD_FROM_MS, now_ms)
    refresh_histdata("NSXUSD", now_ms)
    t, o, h, l, c = minutes("NSXUSD")  # noqa: E741
    trades = {"nasdaq_ib_buy": replay_ib(t, o, h, l, c, FORWARD_FROM_MS),
              "pre_fomc": replay_fomc(t, c, event_times(cal, FOMC_NAME), FORWARD_FROM_MS)}
    import MetaTrader5 as mt5
    nfp = event_times(cal, NFP_NAME)
    mt5_ok = mt5.initialize()
    try:
        if mt5_ok:
            mt5.symbol_select(gnt.SYM, True)
            trades["gold_nfp"] = replay_gold(nfp, lambda t0: gnt.fetch(mt5, pd.Timestamp(t0, unit="s", tz="UTC")), FORWARD_FROM_MS,
                                             now_ms / 1000)
    finally:
        if mt5_ok:
            mt5.shutdown()
    res = summarise(trades, rule_ok)
    data = dict(nasdaq_minutes_to=int(t[-1] // 1000), calendar_months=sorted(set(cal.month)) if len(cal) else [], mt5=bool(mt5_ok),
                next_nfp=next((int(x) for x in nfp if x * 1000 > now_ms), None),
                next_fomc=next((int(x) for x in event_times(cal, FOMC_NAME) if x * 1000 > now_ms), None))
    J = ledger_json(trades, res, now_ms, data)
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(json.dumps(J, indent=1), encoding="utf-8")
    L = [f"backtest/forward_ledger.py, {pd.Timestamp(now_ms, unit='ms'):%Y-%m-%d %H:%M} UTC; forward from {pd.Timestamp(FORWARD_FROM_MS, unit='ms')} UTC; "
         f"rule pin {'OK' if rule_ok else 'CHANGED'}; NASDAQ minutes to {pd.Timestamp(int(t[-1]), unit='ms')}; MT5 {'on' if mt5_ok else 'OFF (gold not replayed)'}"]
    for x in J["leads"]:
        mean = "  -  " if x["mean"] is None else f"{x['mean']:+.3f}"
        L.append(f"  {x['name']:<26} n {x['n']:>3}  mean {mean} {x['unit']:<2}  claim {x['claim']:+} {x['unit']}  "
                 f"status {x['status']:<16} years to confirm at the claim ~{x['years']}")
    txt = "\n".join(L)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


def check():
    """Parity: each replay on its study's own window reproduces the study's logged numbers."""
    from backtest import fx_macro_data as md
    ff = md.load("ff_2007_2026.csv")
    usd = ff[ff.currency == "USD"].copy()
    usd["utc"] = pd.to_datetime(usd.utc)
    L = []
    t, o, h, l, c = (np.asarray(x) for x in ibb.load("NSXUSD"))  # noqa: E741
    ib = replay_ib(t, o, h, l, c, 0)
    v = np.array([x["value"] for x in ib])
    yrs = (t[-1] - t[0]) / (365.25 * 86400000)
    L.append(f"nasdaq_ib_buy: n {len(v)} (study 889), mean {v.mean():+.4f}R (study +0.0789), sd {v.std(ddof=1):.3f}R, "
             f"{len(v) / yrs:.1f} a year")
    tc = t
    st = pd.to_datetime(usd[usd.name == FOMC_NAME].utc)
    st = st[st > pd.Timestamp(tc[0], unit="ms") + pd.Timedelta(days=2)]
    fo = replay_fomc(tc, c, epoch_s(st), 0)
    w = np.array([x["value"] for x in fo])
    L.append(f"pre_fomc: n {len(w)} (study 128), mean {w.mean():+.3f}% (study +0.25), t {w.mean() / (w.std(ddof=1) / sqrt(len(w))):+.2f} "
             f"(study +3.14), sd {w.std(ddof=1):.3f}%")
    ref = pd.read_csv(ROOT / "logs" / "gold_news_ticks.csv")
    ref = ref[(ref.ev == "NFP") & (ref.x == GOLD_X) & (ref.lat == GOLD_LAT)]
    times = sorted(epoch_s(ref.t))

    def ticks(t0):
        from datetime import datetime, timezone
        f = gnt.CACHE / f"{gnt.SYM}_{datetime.fromtimestamp(t0, timezone.utc):%Y%m%d_%H%M%S}_2h.pkl"
        import pickle
        return pickle.loads(f.read_bytes()) if f.exists() else None

    g = replay_gold(times, ticks, 0, time.time())
    mine = np.array([x["value"] for x in g])
    L.append(f"gold_nfp: {len(g)} of {len(ref)} logged 2026 releases replayed from the tick cache; values equal to the log: "
             f"{len(g) == len(ref) and bool(np.allclose(mine, ref.net_bp.to_numpy(float)))}")
    txt = "\n".join([f"backtest/forward_ledger.py --check, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC"] + L)
    (ROOT / "logs" / "forward_ledger_check.txt").write_text(txt + "\n", encoding="utf-8")
    print(txt)
    return txt


if __name__ == "__main__":
    if "--check" in sys.argv:
        check()
    elif "--digest" in sys.argv:
        print("REGISTRY_SHA256 =", registry_digest())
        print("RULE_SHA256 =", rule_digest())
    else:
        main()
