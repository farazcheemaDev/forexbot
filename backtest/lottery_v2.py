"""GO-FOR-BROKE ON 4,000 PKR - lottery.py re-run with what was learned after it.

WHY AGAIN
    The user (2026-10-06): "I don't want small gains." The only route in this repo to a big multiple with a positive
    average is the trend book's edge at high risk on a small account (micro_bot.py's idea). lottery.py (2026-09-24)
    measured it on the corrected engine, but three things came later:
      1. mistake #17 (2026-10-06): its allocator freed a slot - and banked the P&L - at the exit bar's LABEL, up to
         an hour before the exit happened (flattered the trend book 1.3-1.6 %/mo on the tune half);
      2. it ran the 5-unit book; the product's trend book is the triple (7 units);
      3. its 10x guard checked new positions only. At 2-4% risk a single 7-unit position can need 9x on its own, so
         the guard on ADDS (blend_paper.py refuses them) decides what is tradeable at all.
    And it did not test the user's actual stake: 4,000 PKR = $14.29 at 280 PKR/$.

THE SIMULATION
    Positions: the triple (tight exit, time stop below +2R after 100 bars, 7 units), funding per unit, real entry
    times. Every long is split into its units (entry level e0 + 2kR, known when its add bar closes); each unit's own
    R is exact (triple_capped.py's decomposition, asserted to reproduce the position's R).
      BOOK12  the 12 deployed coins - picked WITH HINDSIGHT, so OPTIMISTIC (no clean way to deflate a probability)
              Bitget's per-coin minimum (logs/bitget_book_mins.json: $5, and e.g. 1 whole LINK)
      PIT12   the point-in-time top-12 perps by prior-month volume, dead coins included - the HONEST one
              flat $5 minimum (per-coin amount minimums unknown for 400+ coins - slightly optimistic)
    Account: entry-sized (dollars per R fixed from realised equity at entry), 12 slots, 1000h gate (x0.25 in bear);
    a unit is refused if under the minimum, or if open notional + the unit would pass 10x realised equity
    (entries AND adds); a slot frees and P&L banks when the exit bar CLOSES (label + 1h). Ruin = equity under 10%
    of the start. Windows: the first day of every month 2020-07 .. , over 6 and 12 months, 2 orderings; positions
    opened inside the window run to their exit. Overlapping windows: historical frequencies, not independent draws.

CHECK (run first, printed): with release at the LABEL, no minimum and no ruin, the account reproduces
    triple_capped.simulate's equity path on the same rows and ordering.

REGISTERED BEFORE THE RUN (2026-10-06)
    - The slot fix and the add guard cut lottery.py's odds by roughly a third.
    - PIT12 at $14.29: best P(>= 5x in 12 months) 10-20%, at 2-4% risk, with ruin 30-60%.
    - $14.29 is far worse than $221 at low risk (most units under $5) and closer at high risk.
    - Every risk level's P(>= 5x) beats the 40x one-shot's 4-17% only if ruin is accepted at a similar rate.

RESULT (2026-10-06, logs/lottery_v2.txt, logs/lottery_v2_detail.txt)
    - CHECK: release at the label, no floor -> triple_capped.simulate reproduced to 0.00 on every day. PIT rows at 5
      units reproduce lottery._pit_coin's positions and R exactly (SOL, DOGE, LUNA).
    - PIT12 (honest), 4,000 PKR, 12 months: 1% risk a unit -> >=5x 23%, >=10x 16%, ruin 0%; 2% -> >=5x 29%,
      >=10x 22%, >=20x 18%, ruin 6%; 4% -> >=5x 13%, ruin 33%. 70-75% of units refused (under $5). Median ~1.0x.
      $221 at 0.3%: >=5x 31%, median 2.84x, ruin 0%. Predicted 10-20% with ruin 30-60%: WRONG - better odds, far
      less "ruin" - which is why --detail exists.
    - --detail: "ruin" at -90% hides the real failure. 35% (1%) / 49% (2%) of accounts fell under $5 at some point,
      where a unit rarely clears Bitget's minimum: stuck, in practice. Booking only what closed by month 12 costs
      ~2 points (PIT) / ~5-7 points (BOOK12).
    - The odds are WHICH YEAR YOU START IN. PIT12 2%: starts 2020-07..2021-04 >=5x 75% (median x204); 2021-05..12 0%;
      2022 0%; 2023 0% (median x0.21, every account under $5); 2024 62% (median x7.1); 2025 33%. Predicted >= 70% of
      the >=10x from pre-2021-05 starts: WRONG for PIT (50-54%; late 2024 made the rest), right for BOOK12 at 2%.
      Predicted 2022+ starts <= 10%: WRONG - 2024 starts 62%.
    Reading: the only route in this repo to a big multiple with a positive average. It pays when a strong alt bull
    falls inside your year and bleeds otherwise, and nothing measured here says in advance which year it is.

    python -m backtest.lottery_v2
    python -m backtest.lottery_v2 --detail     # by start year, booked at month 12, ever under $5
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest import blend  # noqa: E402
from backtest import lottery as lt  # noqa: E402
from backtest import triple_capped as tc  # noqa: E402
from backtest.bull_boost import regimes  # noqa: E402
from backtest.causal_t0 import LATE  # noqa: E402
from backtest.convex import run_uncapped  # noqa: E402
from backtest.engine_variants import break_map  # noqa: E402
from backtest.graveyard_rescore import walk  # noqa: E402
from backtest.pyramid import FEE_BP  # noqa: E402
from backtest.shortside import signals  # noqa: E402
from backtest.timeframes import resample  # noqa: E402
from backtest.wide_book import eligibility  # noqa: E402
from bot.core.indicators import atr as atr_ind  # noqa: E402

LOG = ROOT / "logs" / "lottery_v2.txt"
DETAIL_LOG = ROOT / "logs" / "lottery_v2_detail.txt"
PKR = 280.0
CAPS = (4000 / PKR, 221.0)
RISKS = (0.003, 0.01, 0.02, 0.04)
HORIZONS = (6, 12)
SEEDS = (0, 1)
LEV = 10.0
RUIN = 0.10
HOUR = 3_600_000_000_000
FEE = FEE_BP / 1e4
TS = (100, 2.0)
UNITS = 7


# ---------------------------------------------------------------- PIT rows, split into units

def pit_units(sym, months):
    """lottery._pit_coin with the triple (7 units) and every long split into units with exact per-unit R."""
    f = lt.PERPS / f"{sym}_1h.csv.gz"
    if not f.exists():
        return []
    d = pd.read_csv(f, usecols=["time", "open", "high", "low", "close", "qvol"]).rename(columns={"qvol": "volume"})
    d["time"] = pd.to_datetime(d["time"]).astype("datetime64[ns]")
    d = d[d.close > 0].drop_duplicates("time").sort_values("time").reset_index(drop=True)
    gap = d.time.diff().dt.total_seconds().fillna(3600) / 3600
    if (gap > 48).any():
        d = d.iloc[:int(np.argmax(gap.values > 48))].reset_index(drop=True)
    if len(d) < 600:
        return []
    fu = pd.read_csv(lt.PERPS / f"{sym}_funding.csv.gz")
    fu["time"] = pd.to_datetime(fu["time"]).dt.floor("h").astype("datetime64[ns]")
    fu = fu.groupby("time", as_index=False)["rate"].sum()
    fts = fu["time"].astype("int64").to_numpy()
    px1 = pd.Series(d["open"].to_numpy(float), index=d["time"])
    fpx = px1.reindex(px1.index.union(pd.DatetimeIndex(fts))).ffill().reindex(pd.DatetimeIndex(fts)).to_numpy()
    cs = np.r_[0.0, np.cumsum(np.nan_to_num(fu["rate"].to_numpy(float) * fpx))]

    def paid(a, b):
        """Sum of rate x price over settlements with a < s <= b (ns) - what a long pays."""
        return cs[np.searchsorted(fts, b, side="right")] - cs[np.searchsorted(fts, a, side="right")]

    out = []
    for rule in lt.RULES:
        df = resample(d, rule)
        if len(df) < 300:
            continue
        late = LATE[rule].value
        mid = (pd.Timedelta(hours=1) - pd.Timedelta(hours=int(rule[:-1])) / 2).value
        tb = break_map(df, rule)
        topen = df["time"].to_numpy()
        for r in walk(df, rule, sym, tb=tb, time_stop=TS, max_units=UNITS):
            t0l = pd.Timestamp(r["t0"]).value
            if pd.Timestamp(r["t0"]).strftime("%Y-%m") not in months:
                continue
            e0 = float(df["open"].to_numpy()[np.searchsorted(topen, r["t0"])])
            risk = r["sf"] * e0
            if not np.isfinite(r["R"]) or risk <= 0:
                continue
            n = len(r["adds"])
            ue = [e0 + k * blend.ADD_EVERY * risk for k in range(n)]
            x = (r["R"] + (1 + FEE) * sum(ue) / risk) * risk / n          # solve the exit price
            t_exit = pd.Timestamp(r["t1"]).value + mid
            ut, uR = [], []
            for k, ta in enumerate(r["adds"]):
                start = t0l - late if k == 0 else pd.Timestamp(ta).value - late
                known = t0l - late if k == 0 else pd.Timestamp(ta).value + HOUR     # add bar closed
                fund = paid(start, t_exit) if start < t_exit else 0.0
                uR.append((x - ue[k]) / risk - FEE * ue[k] / risk - fund / risk)
                ut.append(known)
            uR = np.clip(np.array(uR), -60, 5000)
            out.append(dict(t0=t0l - late, t1=pd.Timestamp(r["t1"]).value, side="long", uR=uR, ut=ut, ue=ue,
                            risk=risk, coin=sym))
        a = atr_ind(df, 14).to_numpy(float)
        o = df["open"].to_numpy(float)
        R, idx, bars, _d = run_uncapped(df, signals(df, "short", "all"), sl_mult=blend.SL_MULT,
                                        fee_bp=blend.FEE_BP, mode="trail_atr", trail=blend.SHORT_TRAIL,
                                        be_at=blend.BE_AT)
        for rr, i, b in zip(R, idx, bars):
            j = max(int(i) - int(b), 0)
            if j < 1 or pd.Timestamp(topen[j]).strftime("%Y-%m") not in months:
                continue
            risk = blend.SL_MULT * a[j - 1]
            if not np.isfinite(risk) or risk <= 0 or risk / o[j] < 0.001:
                continue
            t0 = pd.Timestamp(topen[j]).value - late
            got = paid(t0, pd.Timestamp(topen[int(i)]).value + mid)
            out.append(dict(t0=t0, t1=pd.Timestamp(topen[int(i)]).value, side="short",
                            uR=np.clip(np.array([float(rr) + got / risk]), -60, 5000), ut=[t0], ue=[o[j]],
                            risk=risk, coin=sym))
    return out


def pit_rows():
    elig = eligibility(12)
    rows = []
    for s, m in elig.items():
        if m:
            rows += pit_units(s, m)
    rows.sort(key=lambda z: z["t0"])
    return rows


# ---------------------------------------------------------------- the account

def events_for(rows, lo, hi, seed, release):
    """Sorted (time, kind, pos, unit) for positions with t0 in [lo, hi). kind 0 = close, 1 = entry/add,
    2 = a close at its own entry instant (must follow the entry). release 'close' = exit bar close (label + 1h)."""
    t0s = np.fromiter((r["t0"] for r in rows), np.int64, len(rows))
    a, b = np.searchsorted(t0s, lo), np.searchsorted(t0s, hi)
    sel = rows[a:b]
    tie = np.random.default_rng(seed).random(len(sel))
    o = [sel[i] for i in sorted(range(len(sel)), key=lambda i: (sel[i]["t0"], tie[i]))]
    ev = []
    for j, r in enumerate(o):
        ev.append((r["t0"], 1, j, 0))
        for k in range(1, len(r["ut"])):
            ev.append((max(r["ut"][k], r["t0"]), 1, j, k))
        tc_ = r["t1"] + (HOUR if release == "close" else 0)
        ev.append((tc_, 0 if tc_ > r["t0"] else 2, j, -1))
    ev.sort(key=lambda e: (e[0], e[1]))
    return o, ev


def account(o, ev, bear_ns, bear_v, cap, risk, floor, ruin=True, lev=LEV, slots=12, t_end=None, extra=None):
    """Returns (end multiple, peak multiple, ruined, refused share of units, curve points).
    extra (a dict) receives: 'at_end' = realised multiple at t_end (closes after it not yet booked),
    'trough' = lowest realised equity in dollars."""
    eq, peak = cap, cap
    trough, at_end = cap, None
    state, gross_by = {}, {}
    gross, open_n, refused, placed = 0.0, 0, 0, 0
    ruined = False
    pts = []
    for t, kind, j, k in ev:
        if t_end is not None and at_end is None and t > t_end:
            at_end = eq / cap
        r = o[j]
        if kind in (0, 2):
            s = state.pop(j, None)
            if s is None:
                continue
            open_n -= 1
            gross -= gross_by.pop(j)
            eq = max(eq + s["dpr"] * float(r["uR"][s["units"]].sum()), 0.0)
            peak = max(peak, eq)
            trough = min(trough, eq)
            pts.append((t, eq))
            if ruin and eq < cap * RUIN:
                ruined = True
                break
            continue
        if k == 0:
            if open_n >= slots:
                continue
            ib = bear_v[max(np.searchsorted(bear_ns, t, side="right") - 1, 0)]
            dpr = risk * (blend.REGIME_MULT if ib else 1.0) * eq
            s = dict(dpr=dpr, units=[])
        else:
            s = state.get(j)
            if s is None:
                continue
        coins = s["dpr"] / r["risk"]
        notional = coins * r["ue"][k]
        if notional < floor(r["coin"], r["ue"][k], coins) or gross + notional > lev * eq:
            refused += 1
            continue
        placed += 1
        s["units"].append(k)
        gross += notional
        if k == 0:
            state[j] = s
            open_n += 1
            gross_by[j] = notional
        else:
            gross_by[j] += notional
    if not ruined:
        for j, s in sorted(state.items(), key=lambda kv: o[kv[0]]["t1"]):      # unreachable: every pos closes
            eq = max(eq + s["dpr"] * float(o[j]["uR"][s["units"]].sum()), 0.0)
    if extra is not None:
        extra["at_end"] = (eq / cap) if at_end is None else at_end
        extra["trough"] = trough
    return eq / cap, peak / cap, ruined, refused / max(refused + placed, 1), pts


def book_floor():
    mins = json.load(open(ROOT / "logs" / "bitget_book_mins.json"))

    def floor(coin, px, coins):
        m = mins.get(coin.replace("USDT", ""))
        if m is None:
            return 5.0
        return 5.0 if coins >= m["amin"] else np.inf                          # under 1 LINK: refused
    return floor


def flat_floor(coin, px, coins):
    return 5.0


def check(book, bear_ns, bear_v):
    """Release at the label, no minimum, no ruin, unit cap 1.0: must match triple_capped.simulate's path."""
    lo, hi = book[0]["t0"], book[-1]["t0"] + 1
    o, ev = events_for(book, lo, hi, 0, "label")
    _e, _p, _r, _f, pts = account(o, ev, bear_ns, bear_v, 1.0, blend.RISK / 100.0,
                                  lambda c, p, n: 0.0, ruin=False)
    mine = pd.Series([p[1] for p in pts], index=pd.to_datetime([p[0] for p in pts])).resample("D").last().ffill()
    ref, _b, _t = tc.simulate(book, bear_ns, bear_v, 0)
    gap = float((mine.reindex(ref.index).ffill() - ref).abs().max())
    return mine.iloc[-1], ref.iloc[-1], gap


def main():
    t_start = time.time()
    b = regimes()[1000]
    bear_ns = pd.DatetimeIndex(b.index).as_unit("ns").asi8
    bear_v = b.to_numpy().astype(bool)
    book = tc.build(tight=True, time_stop=TS, max_units=UNITS)
    print(f"  BOOK12 triple: {len(book):,} positions ({time.time() - t_start:.0f}s)", flush=True)
    m_end, r_end, gap = check(book, bear_ns, bear_v)
    lines = [f"backtest/lottery_v2.py, {pd.Timestamp.now():%Y-%m-%d %H:%M}",
             f"CHECK vs triple_capped.simulate (label release, no floor): end {m_end:.6f} vs {r_end:.6f}, "
             f"max daily gap {gap:.2e} -> {'MATCH' if gap < 1e-9 else 'MISMATCH'}"]
    print(lines[-1], flush=True)
    if gap >= 1e-9:
        LOG.write_text("\n".join(lines) + "\n")
        raise SystemExit("the account does not reproduce triple_capped - not reporting odds")
    pit = pit_rows()
    print(f"  PIT12 triple: {len(pit):,} positions ({time.time() - t_start:.0f}s)", flush=True)
    data_end = pd.Timestamp("2026-09-01")
    universes = (("PIT12 - no hindsight, the honest one", pit, flat_floor),
                 ("BOOK12 - hindsight coins, OPTIMISTIC", book, book_floor()))
    for name, rows, floor in universes:
        lines.append(f"\n{name}: {len(rows):,} positions | triple, entry-sized, 10x guard on entries AND adds, "
                     f"slot freed at the exit bar's close, ruin = -90%")
        for H in HORIZONS:
            starts = [s for s in pd.date_range("2020-07-01", data_end, freq="MS")
                      if s + pd.DateOffset(months=H) <= data_end]
            evs = {(s, sd): events_for(rows, s.value, (s + pd.DateOffset(months=H)).value, sd, "close")
                   for s in starts for sd in SEEDS}
            lines.append(f"\n  within {H} months ({len(starts)} monthly starts x {len(SEEDS)} orderings):")
            lines.append(f"  {'start':>8}{'risk/unit':>10}{'median x':>10}{'>=2x':>7}{'>=5x':>7}{'>=10x':>7}"
                         f"{'>=20x':>7}{'touch 5x':>10}{'RUINED':>8}{'ended < start':>15}{'units refused':>15}")
            for cap in CAPS:
                for risk in RISKS:
                    res = np.array([account(*evs[k], bear_ns, bear_v, cap, risk, floor)[:4] for k in evs], float)
                    e, p, ru, rf = res.T
                    lines.append(f"  ${cap:>7.2f}{risk * 100:>9.1f}%{np.median(e):>9.2f}x{(e >= 2).mean():>7.0%}"
                                 f"{(e >= 5).mean():>7.0%}{(e >= 10).mean():>7.0%}{(e >= 20).mean():>7.0%}"
                                 f"{(p >= 5).mean():>10.0%}{ru.mean():>8.0%}{(e < 1).mean():>15.0%}{rf.mean():>15.0%}")
                lines.append("")
            print(f"  {name[:6]} {H}m done ({time.time() - t_start:.0f}s)", flush=True)
    txt = "\n".join(lines)
    print(txt)
    LOG.write_text(txt + "\n")
    print(f"\n-> {LOG} ({time.time() - t_start:.0f}s)")


def detail():
    """Where the big multiples come from, for 4,000 PKR over 12 months.

    Registered before running (2026-10-06, after main()'s PIT12 read 29% >= 5x at 2% risk, above the 10-20%
    predicted): the >= 10x outcomes come mostly from starts before 2021-05 (the 2021 bull) - at least 70% of them;
    starts from 2022 on reach 5x in 10% or fewer; booking only what has CLOSED by the 12th month lowers P(>= 5x)
    by 3 points or more; and the share of accounts that ever fall under $5 (where a unit rarely clears Bitget's
    minimum - stuck in practice) is far above main()'s ruin column."""
    b = regimes()[1000]
    bear_ns = pd.DatetimeIndex(b.index).as_unit("ns").asi8
    bear_v = b.to_numpy().astype(bool)
    cap = CAPS[0]
    data_end = pd.Timestamp("2026-09-01")
    starts = [s for s in pd.date_range("2020-07-01", data_end, freq="MS") if s + pd.DateOffset(months=12) <= data_end]
    lines = [f"backtest/lottery_v2.py --detail, {pd.Timestamp.now():%Y-%m-%d %H:%M}; ${cap:.2f} (4,000 PKR), "
             f"12 months, {len(starts)} starts x {len(SEEDS)} orderings"]
    for name, rows, floor in (("PIT12 (honest)", pit_rows(), flat_floor),
                              ("BOOK12 (hindsight)", tc.build(tight=True, time_stop=TS, max_units=UNITS), book_floor())):
        for risk in (0.01, 0.02):
            recs = []
            for st in starts:
                end = st + pd.DateOffset(months=12)
                for sd in SEEDS:
                    o, ev = events_for(rows, st.value, end.value, sd, "close")
                    ex = {}
                    e, pk, ru, rf, _ = account(o, ev, bear_ns, bear_v, cap, risk, floor, t_end=end.value, extra=ex)
                    recs.append(dict(start=st, end=e, at_end=ex["at_end"], stuck=ex["trough"] < 5.0, ruined=ru))
            d = pd.DataFrame(recs)
            big = d[d.end >= 10]
            lines.append(f"\n{name}, {risk:.0%} risk per unit:")
            lines.append(f"  run to exit: >=5x {(d.end >= 5).mean():.0%}, >=10x {(d.end >= 10).mean():.0%} | booked by "
                         f"month 12: >=5x {(d.at_end >= 5).mean():.0%}, >=10x {(d.at_end >= 10).mean():.0%} | ever under "
                         f"$5 {d.stuck.mean():.0%} | ruined {d.ruined.mean():.0%}")
            lines.append(f"  >=10x outcomes that started before 2021-05: {(big.start < '2021-05-01').mean():.0%} "
                         f"of {len(big)}")
            for lab, m in (("starts 2020-07 .. 2021-04", d.start < "2021-05-01"),
                           ("starts 2021-05 .. 2021-12", (d.start >= "2021-05-01") & (d.start < "2022-01-01")),
                           ("starts 2022", d.start.dt.year == 2022), ("starts 2023", d.start.dt.year == 2023),
                           ("starts 2024", d.start.dt.year == 2024), ("starts 2025", d.start.dt.year == 2025)):
                g = d[m]
                if len(g):
                    lines.append(f"    {lab:26}: n {len(g):>3}, median {g.end.median():5.2f}x, >=2x {(g.end >= 2).mean():4.0%}, "
                                 f">=5x {(g.end >= 5).mean():4.0%} (booked by month 12 {(g.at_end >= 5).mean():4.0%}), "
                                 f"ever under $5 {g.stuck.mean():4.0%}, ended below start {(g.end < 1).mean():4.0%}")
    txt = "\n".join(lines)
    print(txt)
    DETAIL_LOG.write_text(txt + "\n")


if __name__ == "__main__":
    if "--pkr" in sys.argv:                                      # one stake in PKR, its own log files
        _pkr = float(sys.argv[sys.argv.index("--pkr") + 1])
        CAPS = (_pkr / PKR,)
        LOG = ROOT / "logs" / f"lottery_v2_{_pkr:.0f}pkr.txt"
        DETAIL_LOG = ROOT / "logs" / f"lottery_v2_detail_{_pkr:.0f}pkr.txt"
    detail() if "--detail" in sys.argv else main()
