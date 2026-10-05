"""THE LIVE BOT RETRIES DECLINED SIGNALS; THE BACKTEST DROPS THEM. Which one is the book we measured?

Found 2026-10-05 by reconciling the engine with the live paper books (engine_vs_live.py): where both hold the same
trade, entry prices, units and R agree (median 0.0bp, R -0.004). The difference is WHICH trades exist. blend_paper.py
checks every key (coin x sleeve) on each closed bar: flat, close above the upper band (below the lower) and a free slot
-> enter. With 12 slots full it declines - and tries again on the NEXT bar, for as long as the coin stays outside its
band. So it enters LATE once a slot frees: in September the tight book entered ADA, LINK, ENA, NEAR and ARB 6-30 hours
after the engine, at higher prices, and still banked ~+280R on them. The backtest's allocator (graveyard_rescore.taken)
DROPS a declined trade for good, and the coin sits out that trade's whole life. Every %/month in this repo is the drop
book; the bot running is the retry book.

THIS FILE: one portfolio loop over time, 12 shared slots, the live bot's order (BOOK coin order, then 1h / 4h / 12h,
exits before entries on the same key), the SAME position rules as the engine (graveyard_rescore.walk for longs,
convex.run_uncapped trail_atr for shorts), single-position steppers started at any bar. Two allocators:
  drop    a declined signal occupies its key as a VIRTUAL trade until that trade would have exited (the engine's
          taken(), with the live order instead of random ties) - validated against taken() below
  retry   a declined signal leaves the key flat; it tries again on the next bar while the signal holds (blend_paper)
Configs: main, and the triple (tight + time stop 100 bars / 2R + 7 units). Entry-sized compounding, 1000h gate x0.25,
%/month with the hindsight haircut, both halves - the repo's standard measure (compounding.summarize).

FIRST RUN (kept for the record): drop and retry were run with ONE position per key, and drop did NOT reproduce the
engine's own allocator (main holdout +1.66 against taken()'s +4.43). A second structural difference was found: the
engine's longs and shorts are independent lists, so a key can hold a long runner AND shorts at once; the live bot
cannot. So the file now checks itself before comparing: A replays each key alone against walk()/run_uncapped()
trade by trade; B requires E0 (the engine's structure) to land on taken(); then E1-E3 switch ONE difference at a
time to arrive at the live bot. Nothing below is read until A and B pass.

REGISTERED PREDICTION (2026-10-05, before running): retry takes 3-6% more trades, almost all in bull runs; the late
entries earn less per trade than on-time ones but more than zero; the book's %/month moves by less than 0.5 on either
half, slightly UP on the tune half (2021's long runs) - so the published figures stand within noise.

    python -m backtest.slot_retry               # the checks and one (live-order) run of every variant
    python -m backtest.slot_retry --orderings   # 10 random orderings, each variant paired against E0
"""
from __future__ import annotations

import heapq
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import blend  # noqa: E402
from backtest.bull_boost import regimes  # noqa: E402
from backtest.causal_t0 import LATE  # noqa: E402
from backtest.compounding import curve, summarize  # noqa: E402
from backtest.funding_cost import _exit, _real, paid  # noqa: E402
from backtest.engine_variants import break_map  # noqa: E402
from backtest.graveyard_rescore import rows, taken  # noqa: E402
from backtest.pyramid import FEE_BP  # noqa: E402
from backtest.shortside import signals  # noqa: E402
from backtest.timeframes import resample  # noqa: E402
from bot.core.indicators import atr as atr_ind  # noqa: E402
from bot.strategies.base import Action  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RULES = ("1h", "4h", "12h")
DUR = {"1h": pd.Timedelta(hours=1), "4h": pd.Timedelta(hours=4), "12h": pd.Timedelta(hours=12)}
SLOTS = 12
BUY, SELL = int(Action.BUY), int(Action.SELL)   # 1 and 2 - SELL is NOT -1
FEE = FEE_BP / 1e4


class Key:
    def __init__(self, coin, rule, tight):
        df = resample(blend.load(coin), rule)
        self.coin, self.rule = coin, rule
        self.t = pd.DatetimeIndex(df["time"])
        self.o, self.h = df["open"].to_numpy(float), df["high"].to_numpy(float)
        self.lo, self.c = df["low"].to_numpy(float), df["close"].to_numpy(float)
        self.a = atr_ind(df, 14).to_numpy(float)
        self.sl = signals(df, "long", "all").to_numpy()
        self.ss = signals(df, "short", "all").to_numpy()
        self.tb = break_map(df, rule) if tight else None
        self.real = self.t - LATE[rule]          # a bar's REAL start: 4h/12h labels sit 3h/11h after it
        self.pos = {t: i for i, t in enumerate(self.real)}
        self.memo = {}

    def long_from(self, i, time_stop, mu):
        """graveyard_rescore.walk for ONE position entered at the open of bar i -> (exit bar, R, risk, unit bars)"""
        o, h, lo, c, a, tb = self.o, self.h, self.lo, self.c, self.a, self.tb
        r = blend.SL_MULT * a[i - 1]
        p = dict(stop=o[i] - r, best=o[i], ents=[o[i]], nxt=1, tight=False, barmed=(tb is None or not tb[i]))
        e0, ub = o[i], [i]
        for k in range(i, len(o)):
            if tb is not None and k > i:
                if not tb[k]:
                    p["barmed"] = True
                elif p["barmed"]:
                    p["tight"] = True
            if lo[k] <= p["stop"]:
                return k, (sum(p["stop"] - e for e in p["ents"]) - sum(FEE * e for e in p["ents"])) / r, r, ub
            if time_stop and k - i >= time_stop[0] and (c[k] - e0) / r < time_stop[1]:
                return k, (sum(c[k] - e for e in p["ents"]) - sum(FEE * e for e in p["ents"])) / r, r, ub
            if len(p["ents"]) < mu and (h[k] - e0) / r >= p["nxt"] * blend.ADD_EVERY:
                p["ents"].append(e0 + p["nxt"] * blend.ADD_EVERY * r); p["nxt"] += 1; ub.append(k)
            p["best"] = max(p["best"], h[k])
            m = 5.0 if p["tight"] else blend.LONG_TRAIL
            cand = p["best"] - m * a[k - 1]
            if (p["best"] - e0) / r >= blend.BE_AT:
                cand = max(cand, e0)
            p["stop"] = max(p["stop"], cand)
        k = len(o) - 1
        return k, (sum(c[k] - e for e in p["ents"]) - sum(FEE * e for e in p["ents"])) / r, r, ub

    def short_from(self, i):
        """convex.run_uncapped(mode='trail_atr', trail=SHORT_TRAIL, be_at=BE_AT) for ONE short entered at bar i"""
        o, h, lo, c, a = self.o, self.h, self.lo, self.c, self.a
        e, risk = o[i], blend.SL_MULT * a[i - 1]
        stop, best = e + risk, e
        for k in range(i, len(o)):
            if h[k] >= stop:
                return k, ((e - stop) - FEE * e) / risk, risk, [i]
            if k - i >= 2000:
                return k, ((e - c[k]) - FEE * e) / risk, risk, [i]
            best = min(best, lo[k])
            cand = best + blend.SHORT_TRAIL * a[k - 1]
            if (e - best) / risk >= blend.BE_AT:
                cand = min(cand, e)
            stop = min(stop, cand)
        k = len(o) - 1
        return k, ((e - c[k]) - FEE * e) / risk, risk, [i]

    def trade(self, i, side, time_stop, mu):
        """-> (exit bar, R charged with funding, R before funding) - funding_cost's own formulas: each unit pays the
        settlements from its own bar's real start to the middle of the exit bar; a short receives them"""
        if (i, side) not in self.memo:
            j, R, risk, ub = self.long_from(i, time_stop, mu) if side == "long" else self.short_from(i)
            t_exit = _exit(self.t[j], self.rule)
            got = sum(paid(self.coin, _real(self.t[u], self.rule), t_exit) for u in ub
                      if _real(self.t[u], self.rule) < t_exit)
            fund = (-got if side == "long" else got) / risk
            self.memo[(i, side)] = (j, R + fund, R)
        return self.memo[(i, side)]


def simulate(keys, mode, time_stop, mu, lanes="key", release="close", seed=None, pause=True):
    """-> list of dicts (t0 = REAL entry time, t1 = exit bar label, R charged with funding, side, late, coin, rule).
    lanes   "key"  - ONE position per coin x sleeve, long or short (blend_paper.py: st["open"][key])
            "side" - longs and shorts in separate lanes, so a key can hold both (the engine: walk() and run_uncapped()
                     give two independent trade lists that graveyard_rescore.taken() then allocates)
    release "close" - the live bot: an exit is handled when its bar CLOSES (label + 1h), and that key's next entry
                      check waits for its NEXT closed bar (blend_paper.py sets last_bar on the exit, then continues)
            "label" - taken(): a slot counts as free once the exit LABEL is <= the new trade's real t0, and walk()
                      may re-enter on the very next bar
    Slots are released from one global queue, so a slot frees at its own time whatever key owns it."""
    clock = sorted(set().union(*[set(k.real) for k in keys]))
    sides = ("long", "short")
    busy, heap, slots_used, out, waiting, cool, n = {}, [], 0, [], set(), {}, 0
    rng = None if seed is None else np.random.default_rng(seed)   # seed: a random key order at every step (ties)
    for T in clock:
        while heap and heap[0][0] <= T:
            _f, _n, lk = heapq.heappop(heap)
            if busy.pop(lk)["real"]:
                slots_used -= 1
            cool[lk] = _f                        # when it freed (the live bot then waits for the key's next bar)
        for k in (keys if rng is None else [keys[q] for q in rng.permutation(len(keys))]):
            i = k.pos.get(T)
            if i is None or i < 1:
                continue
            for lk in ([(k, s) for s in sides] if lanes == "side" else [(k, None)]):
                if lk in busy:
                    continue
                if release == "close" and pause and lk in cool and cool[lk] >= k.real[i]:
                    cool.pop(lk)                 # the bar whose close handled the exit: no entry check on it
                    continue
                want = lk[1]
                if want is None:
                    side = "long" if k.sl[i] == BUY else ("short" if k.ss[i] == SELL else None)
                else:
                    side = want if ((want == "long" and k.sl[i] == BUY) or (want == "short" and k.ss[i] == SELL)) else None
                if side is None or not (np.isfinite(k.a[i - 1]) and k.a[i - 1] > 0):
                    waiting.discard(lk)
                    continue
                j, Rc, _R = k.trade(i, side, time_stop, mu)
                free_at = k.t[j] + (pd.Timedelta(hours=1) if release == "close" else pd.Timedelta(0))
                if slots_used < SLOTS:
                    slots_used += 1
                    busy[lk] = dict(real=True)
                    out.append(dict(t0=k.real[i], t1=k.t[j], R=Rc, side=side, late=lk in waiting, coin=k.coin, rule=k.rule))
                    waiting.discard(lk)
                elif mode == "drop":
                    busy[lk] = dict(real=False)
                else:
                    waiting.add(lk)
                    continue
                n += 1
                heapq.heappush(heap, (free_at, n, lk))
    return out


def replay_check(keys, time_stop, mu, tight):
    """CHECK A: each key stepped alone with no slots must reproduce the engine's own trade lists exactly"""
    from backtest.convex import run_uncapped
    from backtest.graveyard_rescore import walk
    n_eng = n_mine = n_same = 0
    for k in keys:
        df = resample(blend.load(k.coin), k.rule)
        eng = walk(df, k.rule, k.coin, tb=(break_map(df, k.rule) if tight else None),
                   **({"time_stop": time_stop, "max_units": mu} if time_stop else {}))
        mine, i = [], 1
        while i < len(k.t):                       # walk(): after an exit at bar j the earliest entry is bar j + 1
            if k.sl[i] == BUY and np.isfinite(k.a[i - 1]) and k.a[i - 1] > 0:
                j, _Rc, R = k.trade(i, "long", time_stop, mu)
                mine.append((k.t[i], k.t[j], round(R, 6)))
                i = j + 1
            else:
                i += 1
        e = {(pd.Timestamp(x["t0"]), pd.Timestamp(x["t1"]), round(x["R"], 6)) for x in eng}
        m = set(mine)
        n_eng += len(e); n_mine += len(m); n_same += len(e & m)
        sig = signals(df, "short", "all")
        R_s, idx, bars, _d = run_uncapped(df, sig, sl_mult=blend.SL_MULT, fee_bp=blend.FEE_BP, mode="trail_atr",
                                          trail=blend.SHORT_TRAIL, be_at=blend.BE_AT)
        es = {(k.t[int(i_) - int(b)], k.t[int(i_)], round(float(r_), 6)) for r_, i_, b in zip(R_s, idx, bars)}
        ms, i = set(), 1
        while i < len(k.t):                       # run_uncapped(): likewise; a short still open at the end is not recorded
            if k.ss[i] == SELL and np.isfinite(k.a[i - 1]) and k.a[i - 1] > 0:
                j, _Rc, R = k.trade(i, "short", time_stop, mu)
                if j < len(k.t) - 1:
                    ms.add((k.t[i], k.t[j], round(R, 6)))
                i = j + 1
            else:
                i += 1
        n_eng += len(es); n_mine += len(ms); n_same += len(es & ms)
    return n_eng, n_mine, n_same


def measure(tr, bear, cut):
    res = {}
    for half, sel in (("tune", lambda x: x["t0"] < cut), ("hold", lambda x: x["t0"] >= cut)):
        lst = [(pd.Timestamp(x["t0"]), pd.Timestamp(x["t1"]),
                x["R"] * blend.RISK / 100.0 * (blend.REGIME_MULT if bool(bear.asof(x["t0"])) else 1.0)) for x in tr if sel(x)]
        hpm, _raw, dd, _fin = summarize(curve(lst, "entry_sized"))
        res[half] = (hpm, dd, len(lst), sum(x["R"] for x in tr if sel(x)))
    return res


def main():
    bear = regimes()[1000]
    out = []
    for name, tight, time_stop, mu in (("main", False, None, blend.MAX_UNITS), ("triple", True, (100, 2.0), 7)):
        keys = [Key(c, r, tight) for c in blend.BOOK if blend.load(c) is not None for r in RULES]
        keys = [k for k in keys if len(k.t) >= 300]
        ne, nm, ns = replay_check(keys, time_stop, mu, tight)
        out.append(f"\n{name.upper()} ({len(keys)} keys)")
        out.append(f"  CHECK A, each key alone with no slots: engine trades {ne}, this file's {nm}, identical {ns} "
                   f"({ns / max(ne, 1) * 100:.1f}%)")
        V = {"E0 engine-equivalent: lanes per side, drop, slot frees at the exit LABEL": ("drop", "side", "label"),
             "E1 + one position per key": ("drop", "key", "label"),
             "E2 + slot frees at the exit bar's CLOSE": ("drop", "key", "close"),
             "E3 + RETRY = the live bot": ("retry", "key", "close"),
             "E4 retry, lanes per side": ("retry", "side", "label")}
        runs = {lab: simulate(keys, *a[:1], time_stop, mu, lanes=a[1], release=a[2]) for lab, a in V.items()}
        allt = sorted(x["t0"] for x in runs["E3 + RETRY = the live bot"])
        cut = allt[int(len(allt) * 0.6)]
        # CHECK B: the engine's own allocator on the engine's own trades (10 random tie orders) - E0 must land on it
        rs = rows(tight=tight, **({"time_stop": time_stop, "max_units": mu} if name == "triple" else {}))
        eng = []
        for half, kw in (("tune", dict(t_to=cut)), ("hold", dict(t_from=cut))):
            v = [summarize(curve(taken(rs, bear, sd, **kw), "entry_sized"))[0] for sd in range(10)]
            eng.append((np.median(v), np.min(v), np.max(v)))
        Rt = runs["E3 + RETRY = the live bot"]
        late = [x for x in Rt if x["late"]]
        out.append(f"  halves split {cut:%Y-%m-%d}")
        out.append(f"  {'allocator':<74}{'trades':>8}{'sum R':>10}{'tune %/mo':>11}{'hold %/mo':>11}{'tune DD':>9}{'hold DD':>9}")
        out.append(f"  {'CHECK B: engine taken(), 10 random tie orders (median; range)':<74}{'':>8}{'':>10}{eng[0][0]:>+10.2f}%"
                   f"{eng[1][0]:>+10.2f}%   tune {eng[0][1]:+.2f}..{eng[0][2]:+.2f}, hold {eng[1][1]:+.2f}..{eng[1][2]:+.2f}")
        for lab, tr in runs.items():
            m = measure(tr, bear, cut)
            out.append(f"  {lab:<74}{len(tr):>8}{sum(x['R'] for x in tr):>+10.1f}{m['tune'][0]:>+10.2f}%{m['hold'][0]:>+10.2f}%"
                       f"{m['tune'][1]:>8.0f}%{m['hold'][1]:>8.0f}%")
        out.append(f"  late entries (retried after a decline): {len(late)} ({len(late)/len(Rt)*100:.1f}% of trades), "
                   f"sum {sum(x['R'] for x in late):+.1f}R, mean {np.mean([x['R'] for x in late]) if late else 0:+.2f}R a trade "
                   f"(on-time trades {np.mean([x['R'] for x in Rt if not x['late']]):+.2f}R); longs {sum(x['side'] == 'long' for x in late)}")
        if late:
            top = sorted(late, key=lambda x: -x["R"])[:5]
            out.append("  biggest late entries: " + "; ".join(f"{x['coin']} {x['rule']} {x['t0']:%Y-%m-%d} {x['R']:+.0f}R" for x in top))
    txt = "\n".join(out)
    print(txt)
    (ROOT / "logs" / "slot_retry.txt").write_text(txt, encoding="utf-8")


def orderings(n_seeds=10):
    """The single-ordering gaps above are within the engine's own ordering spread (main holdout +3.00..+4.95), so the
    variants are re-run on n random orderings and PAIRED against E0 on the same seed (CLAUDE.md, 'comparing medians').
    REGISTERED PREDICTION (2026-10-06, before this run): the live structure (E3) trails the engine structure (E0) by 1-2
    %/mo on the holdout and by about 0 on the tune half."""
    bear = regimes()[1000]
    out = []
    V = {"E1 one position per key": ("drop", "key", "label"),
         "E2 + exit handled at the bar close, one-bar pause": ("drop", "key", "close"),
         "E3 + RETRY = the live bot": ("retry", "key", "close")}
    for name, tight, time_stop, mu in (("main", False, None, blend.MAX_UNITS), ("triple", True, (100, 2.0), 7)):
        keys = [Key(c, r, tight) for c in blend.BOOK if blend.load(c) is not None for r in RULES]
        keys = [k for k in keys if len(k.t) >= 300]
        base = {sd: simulate(keys, "drop", time_stop, mu, lanes="side", release="label", seed=sd) for sd in range(n_seeds)}
        allt = sorted(x["t0"] for x in base[0])
        cut = allt[int(len(allt) * 0.6)]
        b = {sd: measure(base[sd], bear, cut) for sd in base}
        out.append(f"\n{name.upper()} - {n_seeds} random orderings, halves split {cut:%Y-%m-%d}; E0 (the engine's structure) "
                   f"tune {np.mean([b[sd]['tune'][0] for sd in b]):+.2f}%, hold {np.mean([b[sd]['hold'][0] for sd in b]):+.2f}%/mo "
                   f"(DD {np.mean([b[sd]['tune'][1] for sd in b]):.0f}% / {np.mean([b[sd]['hold'][1] for sd in b]):.0f}%)")
        out.append(f"  {'variant, paired against E0 on the same ordering':<52}{'tune %/mo':>24}{'hold %/mo':>24}{'tune DD':>9}{'hold DD':>9}")
        for lab, a in V.items():
            d_t, d_h, dd_t, dd_h = [], [], [], []
            for sd in range(n_seeds):
                m = measure(simulate(keys, a[0], time_stop, mu, lanes=a[1], release=a[2], seed=sd), bear, cut)
                d_t.append(m["tune"][0] - b[sd]["tune"][0]); d_h.append(m["hold"][0] - b[sd]["hold"][0])
                dd_t.append(m["tune"][1]); dd_h.append(m["hold"][1])
            f = lambda d: f"{np.mean(d):+.2f} +- {np.std(d, ddof=1) / np.sqrt(len(d)):.2f} ({int(np.sum(np.array(d) > 0))}/{len(d)} up)"  # noqa: E731
            out.append(f"  {lab:<52}{f(d_t):>24}{f(d_h):>24}{np.mean(dd_t):>8.0f}%{np.mean(dd_h):>8.0f}%")
    txt = "\n".join(out)
    print(txt)
    (ROOT / "logs" / "slot_retry_orderings.txt").write_text(txt, encoding="utf-8")


def pause_fix(n_seeds=10):
    """--orderings (logs/slot_retry_orderings.txt) found the live structure 1-2 %/mo under the engine's, and the largest
    single step was the ONE-BAR PAUSE: blend_paper.cycle sets last_bar when it books an exit and then `continue`s, so the
    key's entry check for that same closed bar never runs and the earliest re-entry is one bar later than walk()'s.
    THE FIX TESTED: the live bot exactly as it is (E3) against the same bot with only the pause removed (E3b: an exit
    at a bar's close may be followed by an entry check on that same close). Paired on 10 random orderings.
    REGISTERED PREDICTION (2026-10-06, before this run): removing the pause adds +1 to +2 %/mo on the holdout and about
    +0.5 on the tune half; E3b still trails E0 (the engine's structure) by 0.5-1 %/mo."""
    bear = regimes()[1000]
    out = []
    for name, tight, time_stop, mu in (("main", False, None, blend.MAX_UNITS), ("triple", True, (100, 2.0), 7)):
        keys = [Key(c, r, tight) for c in blend.BOOK if blend.load(c) is not None for r in RULES]
        keys = [k for k in keys if len(k.t) >= 300]
        res = {v: {} for v in ("E0", "E3", "E3b")}
        cut = None
        for sd in range(n_seeds):
            e0 = simulate(keys, "drop", time_stop, mu, lanes="side", release="label", seed=sd)
            if cut is None:
                allt = sorted(x["t0"] for x in e0)
                cut = allt[int(len(allt) * 0.6)]
            res["E0"][sd] = measure(e0, bear, cut)
            res["E3"][sd] = measure(simulate(keys, "retry", time_stop, mu, release="close", seed=sd), bear, cut)
            res["E3b"][sd] = measure(simulate(keys, "retry", time_stop, mu, release="close", seed=sd, pause=False), bear, cut)
        def pair(a, b, h):
            d = np.array([res[a][sd][h][0] - res[b][sd][h][0] for sd in range(n_seeds)])
            return f"{d.mean():+.2f} +- {d.std(ddof=1) / np.sqrt(len(d)):.2f} ({int((d > 0).sum())}/{len(d)} up)"
        mean = lambda v, h, q: np.mean([res[v][sd][h][q] for sd in range(n_seeds)])  # noqa: E731
        out.append(f"\n{name.upper()} - {n_seeds} random orderings, halves split {cut:%Y-%m-%d}")
        for v, lab in (("E0", "E0 the engine's structure (every backtest)"), ("E3", "E3 the live bot as built"),
                       ("E3b", "E3b the live bot, pause removed")):
            out.append(f"  {lab:<44} tune {mean(v, 'tune', 0):+6.2f}%  hold {mean(v, 'hold', 0):+6.2f}%/mo   "
                       f"DD {mean(v, 'tune', 1):.0f}% / {mean(v, 'hold', 1):.0f}%")
        out.append(f"  THE FIX, E3b - E3 (paired):   tune {pair('E3b', 'E3', 'tune')}   hold {pair('E3b', 'E3', 'hold')}")
        out.append(f"  what is left, E3b - E0:        tune {pair('E3b', 'E0', 'tune')}   hold {pair('E3b', 'E0', 'hold')}")
    txt = "\n".join(out)
    print(txt)
    (ROOT / "logs" / "slot_retry_pause.txt").write_text(txt, encoding="utf-8")


def release_check(n_seeds=10):
    """--pause (logs/slot_retry_pause.txt) showed the one-bar pause is NOT the cause (removing it: main +0.54 / -0.14,
    triple +0.04 / +0.27, all inside ~1 se), so the large step from E1 to E2 must be its other half: WHEN A SLOT FREES.
    walk() records an exit at the LABEL of the bar the stop is hit in - for 1h bars the bar's OPEN - and taken() frees
    that slot for any trade whose real entry is >= that label. So at the open of an hour the allocator already 'knows'
    that a position will be stopped out later in that hour, and lets a new trade take its slot. A LOOK-AHEAD in the
    allocator itself (4h/12h labels sit 1h before the bar closes, so there it bites only on exits in a bar's last hour).
    THE TEST: E0 against E0 with ONE change - the slot frees when the exit bar CLOSES (the earliest time an exit judged
    on a closed bar is known). Lanes per side, drop, no pause: the engine in every other respect. Paired, 10 orderings.
    REGISTERED PREDICTION (2026-10-06, before this run): causal release costs the engine -1 to -2.5 %/mo on the holdout
    and -0.5 to -1 on the tune half, i.e. the allocator's look-ahead is most of the gap to the live bot."""
    bear = regimes()[1000]
    out = []
    for name, tight, time_stop, mu in (("main", False, None, blend.MAX_UNITS), ("triple", True, (100, 2.0), 7)):
        keys = [Key(c, r, tight) for c in blend.BOOK if blend.load(c) is not None for r in RULES]
        keys = [k for k in keys if len(k.t) >= 300]
        A, B, cut = {}, {}, None
        for sd in range(n_seeds):
            a = simulate(keys, "drop", time_stop, mu, lanes="side", release="label", seed=sd)
            if cut is None:
                allt = sorted(x["t0"] for x in a)
                cut = allt[int(len(allt) * 0.6)]
            A[sd] = measure(a, bear, cut)
            B[sd] = measure(simulate(keys, "drop", time_stop, mu, lanes="side", release="close", seed=sd, pause=False),
                            bear, cut)
        out.append(f"\n{name.upper()} - {n_seeds} random orderings, halves split {cut:%Y-%m-%d}")
        for lab, X in (("E0 the engine (slot frees at the exit LABEL)", A), ("the engine, slot frees at the exit bar CLOSE", B)):
            out.append(f"  {lab:<48} tune {np.mean([X[s]['tune'][0] for s in X]):+6.2f}%  hold "
                       f"{np.mean([X[s]['hold'][0] for s in X]):+6.2f}%/mo   DD {np.mean([X[s]['tune'][1] for s in X]):.0f}% / "
                       f"{np.mean([X[s]['hold'][1] for s in X]):.0f}%")
        for h in ("tune", "hold"):
            d = np.array([B[s][h][0] - A[s][h][0] for s in range(n_seeds)])
            out.append(f"  causal release - engine, {h}: {d.mean():+.2f} +- {d.std(ddof=1) / np.sqrt(len(d)):.2f} "
                       f"({int((d > 0).sum())}/{len(d)} up)")
    txt = "\n".join(out)
    print(txt)
    (ROOT / "logs" / "slot_release.txt").write_text(txt, encoding="utf-8")


if __name__ == "__main__":
    if "--orderings" in sys.argv:
        orderings()
    elif "--pause" in sys.argv:
        pause_fix()
    elif "--release" in sys.argv:
        release_check()
    else:
        main()
