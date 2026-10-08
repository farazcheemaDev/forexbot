"""MICRO_BOT, RE-MEASURED WITH ITS OWN SETTINGS - the odds behind "29.7% chance of $10 -> $50".

WHY
    micro_bot.py quotes its odds from microacct.py (2026-09-14): pooled single-unit R from the PRE-2026-09-23 engine
    (no funding), shuffled ONE TRADE AT A TIME (its own docstring: "real ruin is therefore ABOVE 70%"), with a
    synthetic 3x deflation. lottery_v2.py re-measured go-for-broke on the corrected engine but for the TRIPLE book,
    not micro_bot's rules. This replays micro_bot's own rules on real price paths, account-level.

MICRO_BOT AS WRITTEN (micro_bot.py, constants read from the module)
    1h bars; signal = the closed bar's close beyond Bollinger(30, 1.5) (ddof 0); long above, short below.
    ATR14 = simple mean of true range (longtrend_bot.atr). Stop 2 x ATR from the signal close = 1R.
    manage(): the entry bar is never judged; each later bar checks the stop set at the END of the previous bar, then
    the water mark moves (initial water = the signal bar's high / low), trail = water - 20 x ATR (longs) / + 5 x ATR
    (shorts) with the bar's ATR, breakeven once the water is 3R in profit. 1 unit, no pyramid, no regime gate.
    Size: notional = equity x 4% / stop fraction; under $5 it is RAISED to $5 (the floor overrides upward); skipped
    if notional > 10 x equity. At most 3 positions, one per coin. Stops opening once equity >= 5 x the start.
    The bot places NO stop order on the exchange: it sees the breach when the bar closes and sends a MARKET order.

THE REPLAY
    Entry filled at the next bar's open; the stop breach seen at bar t's close is filled at bar t+1's open (gaps and
    crash minutes included). Taker 6bp a side; funding per settlement held (Binance archive). Equity for sizing and
    for the target is MARK-TO-MARKET at the bar close (Bitget's account equity, which the bot reads).
    LIQUIDATION: every hour a position is open, the account at every open position's worst price of that hour
    (low for longs, high for shorts); if that is under 0.5% of open notional the account is closed out. RUIN = equity
    under $0.50, the margin for one $5 order at 10x.
      MICRO10  micro_bot's own 10 coins - chosen in 2026 among coins still listed: hindsight, OPTIMISTIC
      PIT12    the point-in-time top-12 by prior-month volume, dead coins included: the honest universe
    Windows: the first day of every month 2020-07 .. 2025-09, 12 months of entries, 2 orderings of same-hour signals.
    Stakes $10 (micro_bot's design) and $14.29 (4,000 PKR). Risk 4% (the bot), 2%, 1%.

REGISTERED BEFORE THE RUN (2026-10-06)
    - MICRO10, $10, 4%: P(reach 5x within 12 months) 10-20% (the bot quotes 29.7%); ended unable to trade or
      liquidated 40-70%.
    - PIT12 lower: 5-15%.
    - 2% beats 4% on P(5x).
    - At least one window is LIQUIDATED (market exits after the bar close meet crash hours).

RESULT (2026-10-06, logs/micro_honest.txt, logs/micro_honest.csv)
    - tests/test_micro_honest.py: the vectorised exits equal micro_bot.manage() bar by bar on 1,000+ random trades
      (a planted short-trail bug fails it). Data scan: the >3x bars are real events (2025-10-10 21:00, FTT 2022-11-08,
      ETH 2020-03-13), one KORU jump - no systematic glitches.
    - "Reached 5x" (MTM touch, the bot's own stop-opening rule) vs ENDED >= 5x after open positions close:
        MICRO10 $10 4% (the bot):  touched 42%, ENDED 29%, ruined 56%, liquidated 17%
        MICRO10 $14.29 4% / 2%:    ended 32% / 25%, ruined 47% / 17%
        PIT12   $14.29 4% / 2%:    ended 25% / 29%, ruined 53% / 36%, liquidated 29% / 18%
      Every touch ended >= 2x; a third to a half fell back under 5x.
    - The hits are real runs: AVAX 2021-01, SHIB 2021-10 and 2024-02, DOGE 2024-10/11; 20-50% of trades win, the
      top 3 trades are 50-100% of the profit (fat-tail capture, sized on mark-to-market equity).
    - By start year (4%): 2022 starts 8-12%, 2023 25-46%, 2024 62-71%; 2025 MICRO10 6% (94% ruined) vs PIT12 72% -
      the universe decides the year.
    - Predictions: P(5x) 10-20% WRONG (29% ended, 42% touched - the old 29.7% roughly survives); ruin 40-70% right;
      PIT12 lower WRONG (about equal); 2% beats 4% on P(5x) WRONG - a tie, but 2% cuts ruin by 20-30 points;
      at least one liquidation right (3-33% of windows).
    Not modelled: Bitget per-coin amount minimums (0.1 LTC ~ $8-10 forces more risk), slippage beyond the next open.

    python -m backtest.micro_honest
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import micro_bot as mb  # noqa: E402
import odds_now as on  # noqa: E402
from backtest.wide_book import eligibility  # noqa: E402

PERPS = ROOT / "strategy_analysis" / "data" / "perps"
LOG = ROOT / "logs" / "micro_honest.txt"
CSV = ROOT / "logs" / "micro_honest.csv"
H_NS = 3_600_000_000_000
T0 = pd.Timestamp("2020-01-01").value
TAKER = 0.0006
MAINT = 0.005
RUIN_EQ = mb.MIN_NOTIONAL / mb.MAX_LEVERAGE
STAKES = (10.0, 4000 / 280)
RISKS = (0.04, 0.02, 0.01)
SEEDS = (0, 1)
MONTHS = 12
PERP_NAME = {"SHIBUSDT": "1000SHIBUSDT"}


# ---------------------------------------------------------------- per coin

class Coin:
    def __init__(self, sym, t_from=None, t_to=None):
        f = PERPS / f"{PERP_NAME.get(sym, sym)}_1h.csv.gz"
        d = pd.read_csv(f, usecols=["time", "open", "high", "low", "close"])
        d["time"] = pd.to_datetime(d["time"]).astype("datetime64[ns]")
        d = d[d.close > 0].drop_duplicates("time").sort_values("time").reset_index(drop=True)
        if t_from is not None:                                  # keep warm-up before, room for exits after
            d = d[(d.time >= t_from - pd.Timedelta(days=30)) & (d.time <= t_to)].reset_index(drop=True)
        from backtest.capitulation_wide import halt_cut
        d = halt_cut(d)                       # 2026-10-09: > 7 days is a halt; shorter gaps are archive holes, kept
        self.sym = sym
        self.t = d.time.to_numpy("datetime64[ns]").astype(np.int64)
        self.o, self.h, self.l, self.c = (d[k].to_numpy(float) for k in ("open", "high", "low", "close"))
        df = pd.DataFrame(dict(high=self.h, low=self.l, close=self.c))
        from longtrend_bot import atr
        self.a = atr(df, mb.ATR_PERIOD).to_numpy(float)
        lo_b, up_b = mb.bands(df)
        lo_b, up_b = lo_b.to_numpy(float), up_b.to_numpy(float)
        ok = np.isfinite(up_b) & np.isfinite(lo_b) & np.isfinite(self.a) & (self.a > 0)
        self.sig = np.where(ok & (self.c > up_b), 1, np.where(ok & (self.c < lo_b), -1, 0)).astype(np.int8)
        self.fc = on.fund_by_bar(PERP_NAME.get(sym, sym), d.time, self.o)
        self.g = ((self.t - T0) // H_NS).astype(np.int64)        # global hour of each bar
        self.g0 = int(self.g[0]) if len(self.g) else 0
        self._paths = {}

    def local(self, g):
        """Local bar index of global hour g, or -1. Fast path when the bars have no hole before g."""
        k = g - self.g0
        if 0 <= k < len(self.g) and self.g[k] == g:
            return k
        k = int(np.searchsorted(self.g, g))
        return k if k < len(self.g) and self.g[k] == g else -1

    def path(self, i, d):
        """micro_bot.manage() from signal bar i: the bar t whose close sees the breach (exit fills at o[t+1]),
        or the last bar if the data ends first. Vectorised; tests/test_micro_honest.py checks it against manage()."""
        key = (i, d)
        if key in self._paths:
            return self._paths[key]
        n = len(self.c)
        px, risk = self.c[i], mb.SL_MULT * self.a[i]
        stop, water = px - d * risk, (self.h[i] if d > 0 else self.l[i])
        tm = mb.LONG_TRAIL if d > 0 else mb.SHORT_TRAIL
        s, out = i + 1, n - 2
        while s < n - 1:
            e = min(s + 2048, n - 1)
            if d > 0:
                hit = self.l[s:e] <= np.r_[stop, np.maximum.accumulate(
                    np.maximum(stop, self._cand(s, e, water, d, px, risk, tm)))[:-1]]
            else:
                hit = self.h[s:e] >= np.r_[stop, np.minimum.accumulate(
                    np.minimum(stop, self._cand(s, e, water, d, px, risk, tm)))[:-1]]
            if hit.any():
                out = s + int(np.argmax(hit))
                break
            cand = self._cand(s, e, water, d, px, risk, tm)
            stop = float(np.max(np.r_[stop, cand]) if d > 0 else np.min(np.r_[stop, cand]))
            water = float(max(water, self.h[s:e].max()) if d > 0 else min(water, self.l[s:e].min()))
            s = e
        self._paths[key] = out
        return out

    def _cand(self, s, e, water, d, px, risk, tm):
        if d > 0:
            w = np.maximum.accumulate(np.maximum(water, self.h[s:e]))
            cand = w - tm * self.a[s:e]
            return np.where((w - px) / risk >= mb.BE_AT_R, np.maximum(cand, px), cand)
        w = np.minimum.accumulate(np.minimum(water, self.l[s:e]))
        cand = w + tm * self.a[s:e]
        return np.where((px - w) / risk >= mb.BE_AT_R, np.minimum(cand, px), cand)


# ---------------------------------------------------------------- the account

def run(cands_at, g_start, g_end, stake, risk, seed, trades=None):
    """One window. cands_at(g) -> the coins that may open a position at global hour g. Returns a dict.
    trades (a list) receives one record per closed position: coin, side, entry hour, exit hour, P&L in $."""
    rng = np.random.default_rng(seed)
    cash, pos = stake, {}
    target, hit_at, peak_mtm, trough = stake * mb.TARGET_MULT, None, stake, stake
    liquidated = ruined = False
    taken = forced = 0
    g = g_start
    g_stop = g_end + 24 * 400                                   # manage open positions well past the window
    while g < g_stop:
        if not pos and (g >= g_end or ruined):
            break
        # exits whose market order fills at this hour's open
        for name in [k for k, p in pos.items() if p["g_exit"] == g]:
            p = pos.pop(name)
            cn = p["coin"]
            xo = cn.o[p["t"] + 1]
            fund = cn.fc[p["t"] + 1] - cn.fc[p["i"] + 1]
            pnl = p["d"] * p["size"] * (xo - p["fill"]) - TAKER * p["size"] * xo - p["d"] * p["size"] * fund
            if trades is not None:
                trades.append(dict(coin=cn.sym, d=p["d"], g_in=p["g_in"], g_out=g, pnl=pnl, eq_before=cash))
            cash += pnl
        # the hour itself: liquidation at every position's worst price
        if pos:
            worst, mtm, notional = cash, cash, 0.0
            for p in pos.values():
                cn, k = p["coin"], p["coin"].local(g)
                if k < 0:
                    continue
                w = cn.l[k] if p["d"] > 0 else cn.h[k]
                worst += p["d"] * p["size"] * (w - p["fill"])
                mtm += p["d"] * p["size"] * (cn.c[k] - p["fill"])
                notional += p["size"] * cn.c[k]
            if worst <= MAINT * notional:
                liquidated = ruined = True
                cash, pos = 0.0, {}
                break
        else:
            mtm = cash
        peak_mtm, trough = max(peak_mtm, mtm), min(trough, mtm)
        if hit_at is None and mtm >= target:
            hit_at = g
        if mtm < RUIN_EQ and not pos:
            ruined = True
        # entries on this hour's closed bar, filled at the next open
        if g < g_end and hit_at is None and not ruined:
            cands = list(cands_at(g))
            rng.shuffle(cands)
            for cn in cands:
                if len(pos) >= mb.MAX_POSITIONS:
                    break
                if cn.sym in pos:
                    continue
                i = cn.local(g)
                if i < 0 or i + 2 >= len(cn.c) or cn.sig[i] == 0:
                    continue
                d = int(cn.sig[i])
                px, rsk = cn.c[i], mb.SL_MULT * cn.a[i]
                notional = mtm * risk / (rsk / px)
                if notional < mb.MIN_NOTIONAL:
                    notional, forced = mb.MIN_NOTIONAL, forced + 1
                if notional > mtm * mb.MAX_LEVERAGE:
                    continue
                size = notional / px
                fill = cn.o[i + 1]
                cash -= TAKER * size * fill
                t = cn.path(i, d)
                pos[cn.sym] = dict(coin=cn, i=i, t=t, d=d, size=size, fill=fill, g_in=g + 1,
                                   g_exit=int(cn.g[min(t + 1, len(cn.g) - 1)]))
                taken += 1
        g += 1
    for p in pos.values():                                       # data ran out: close at the last close
        cn = p["coin"]
        cash += p["d"] * p["size"] * (cn.c[-1] - p["fill"])
    return dict(hit=hit_at is not None, days=(hit_at - g_start) / 24 if hit_at is not None else np.nan,
                end=max(cash, 0.0) / stake, peak=peak_mtm / stake, trough=trough, liq=liquidated,
                ruined=ruined or cash < RUIN_EQ, taken=taken, forced=forced / max(taken, 1))


# ---------------------------------------------------------------- main

def main():
    t_start = time.time()
    micro = {s: Coin(s) for s in mb.BOOK}
    el = eligibility(12)
    pit = {}
    for s, ms in el.items():
        if not ms or not (PERPS / f"{s}_1h.csv.gz").exists():
            continue
        lo = pd.Timestamp(min(ms) + "-01")
        hi = pd.Timestamp(max(ms) + "-01") + pd.DateOffset(months=15)
        try:
            c = Coin(s, lo, hi)
            if len(c.c) > 400:
                pit[s] = c
        except Exception:
            pass
    print(f"  data: {len(micro)} micro coins, {len(pit)} PIT coins ({time.time() - t_start:.0f}s)", flush=True)
    by_month: dict = {}
    for s, ms in el.items():
        if s in pit:
            for m in ms:
                by_month.setdefault(m, []).append(pit[s])
    month_cache: dict = {}

    def pit_cands(g):
        k = g // 24                                              # one lookup per day
        if k not in month_cache:
            month_cache[k] = by_month.get(pd.Timestamp(T0 + g * H_NS).strftime("%Y-%m"), [])
        return month_cache[k]

    micro_list = list(micro.values())

    starts = [s for s in pd.date_range("2020-07-01", "2025-09-01", freq="MS")]
    lines = [f"backtest/micro_honest.py, {pd.Timestamp.now():%Y-%m-%d %H:%M}; micro_bot's own rules on real 1h paths, "
             f"{len(starts)} monthly starts x {len(SEEDS)} orderings, 12 months of entries; exits at the next open after "
             f"the bar that breached; MTM equity; liquidation checked every hour; ruin = under ${RUIN_EQ:.2f}"]
    recs = []
    for uname, cands_at in (("MICRO10 (micro_bot's 10 coins - hindsight, optimistic)", lambda g: micro_list),
                            ("PIT12 (no hindsight - honest)", pit_cands)):
        lines.append(f"\n{uname}")
        lines.append(f"  {'stake':>7}{'risk':>6}{'reached 5x':>12}{'median days':>13}{'ended >=1x':>12}{'median end':>12}"
                     f"{'ruined':>8}{'liquidated':>12}{'trades':>8}{'size forced up':>16}")
        for stake in STAKES:
            for risk in RISKS:
                rs = []
                for st in starts:
                    gs = int((st.value - T0) // H_NS)
                    ge = int(((st + pd.DateOffset(months=MONTHS)).value - T0) // H_NS)
                    for sd in SEEDS:
                        r = run(cands_at, gs, ge, stake, risk, sd)
                        r.update(universe=uname[:7], stake=stake, risk=risk, start=st)
                        rs.append(r)
                d = pd.DataFrame(rs)
                recs.append(d)
                lines.append(f"  ${stake:>6.2f}{risk:>6.0%}{d.hit.mean():>12.0%}{d.days.median():>13.0f}"
                             f"{(d.end >= 1).mean():>12.0%}{d.end.median():>11.2f}x{d.ruined.mean():>8.0%}"
                             f"{d.liq.mean():>12.0%}{d.taken.median():>8.0f}{d.forced.mean():>16.0%}")
            print(f"  {uname[:7]} ${stake:.2f} done ({time.time() - t_start:.0f}s)", flush=True)
    allr = pd.concat(recs)
    allr.to_csv(CSV, index=False)
    lines.append("\nBY START YEAR at the bot's 4%: P(reached 5x) / P(ruined):")
    for (u, stake), g in allr[allr.risk == 0.04].groupby(["universe", "stake"]):
        cells = []
        for lab, m in (("2020-07..21-04", g.start < "2021-05-01"),
                       ("2021-05..12", (g.start >= "2021-05-01") & (g.start < "2022-01-01")),
                       ("2022", g.start.dt.year == 2022), ("2023", g.start.dt.year == 2023),
                       ("2024", g.start.dt.year == 2024), ("2025", g.start.dt.year == 2025)):
            x = g[m]
            cells.append(f"{lab} {x.hit.mean():.0%}/{x.ruined.mean():.0%}")
        lines.append(f"  {u} ${stake:.2f}: " + " | ".join(cells))
    txt = "\n".join(lines)
    print(txt)
    LOG.write_text(txt + "\n")
    print(f"\n-> {LOG} ({time.time() - t_start:.0f}s)")


if __name__ == "__main__":
    if "--pkr" in sys.argv:                                      # one stake in PKR, its own log files
        _pkr = float(sys.argv[sys.argv.index("--pkr") + 1])
        STAKES = (_pkr / 280,)
        LOG = ROOT / "logs" / f"micro_honest_{_pkr:.0f}pkr.txt"
        CSV = ROOT / "logs" / f"micro_honest_{_pkr:.0f}pkr.csv"
    main()
