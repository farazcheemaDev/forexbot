"""BEARS THE BTC LABEL MISSES: altcoins falling while BTC holds (2026-10-23)

The user, 2026-10-23 (alts down for two weeks, BTC flat, both paper accounts -10..-12%, the bear sleeve idle): "can we do
something about it for bears like this". The sleeve (doc 13) switches on only when BTC's own 50-day trend is BEAR
(market_neutral.btc_regime). On 2026-10-19 only 8% of the top-60 sat above their 20-day average while BTC was above a
rising 50-day average - an ALT bear that label does not see.

ALT LABEL   btc_regime's rule on the equal-weight PIT top-40 alt index (breadth_trade.instruments, dead coins in): the
            index below its 50-day average AND the average down > 2% over 20 days, read a day late
DAY GROUPS  BTC-BEAR (the sleeve's days) / ALT-ONLY (alt bear, BTC not) - "bears like this" / the rest
TESTS
  1 how often ALT-ONLY happens, how long it lasts, what alts and BTC do in it
  2 THE SLEEVE ON ALT-ONLY DAYS - breadth20 (PIT top-60) long the bottom third / short the top third, 7-day ladder, entry
    a day late, 12bp + funding + 1bp/day (breadth_attack.run); thresholds (a) expanding over prior gated days, (b) the
    live sleeve's frozen 10.0% / 28.8%; on ALT-ONLY, on all ALT-bear days and on the UNION with BTC-bear. Alt index and
    top-10 basket. Controls: long / short the alt index on every ALT-ONLY day
  3 OUT OF SAMPLE - 2017-07..2019-12 spot (breadth_oos.py's panel), frozen 10.0% / 28.8%, no funding (spot)
  4 (--books) WHAT THE MACHINE'S BOOKS DO ON ALT-ONLY DAYS (all_books.machine_books, 10 orderings). Descriptive only:
    trend / daily / capit2 are booked at close, so this says where losses land, it is not a gate test (CLAUDE.md s3)
  5 (--defence) THE TREND BOOK'S LONGS x0.5 / x0 on ALT-bear days, decided at ENTRY, against the bet-smaller line on all
    4 bar phases x 10 orderings (trend_combos' machinery; its cached line is re-checked first)
REGISTERED BEFORE THE RUN (2026-10-23)
  P1 ALT-ONLY is 5-15% of days since 2020-03.
  P2 the sleeve on ALT-ONLY days does NOT pass both halves on the top-10 basket with either threshold (in-sample the rule
     lost in BTC-chop -14%/yr and BTC-bull -9%, doc 13 s3, and ALT-ONLY days are drawn from those).
  P3 the UNION gate's Sharpe is below the BTC-bear-only sleeve's on the top-10 basket.
  P4 shorting the alt index on every ALT-ONLY day loses on at least one half.
  P5 (part 4) the trend book is the biggest loser on ALT-ONLY days; MN is within +-1% a month of zero.
  P6 (part 5) neither gate beats the bet-smaller line on both halves in all 4 phases (G1 breadth failed one phase).

RESULT (2026-10-22, logs/alt_bear.txt, alt_bear_books.txt, alt_bear_defence.txt) - nothing to add; the machine already earns there.
  1 ALT-ONLY is 14.9% of days since 2020-03 (356), 36 episodes, median 8 days, longest 47; alts -4.4% / BTC -0.5% per 30
    days in them; 17 of 36 were followed by a BTC bear within 30 days. 570 of the 614 BTC-bear days are alt-bear too.
  2 The sleeve's rule on ALT-ONLY days LOSES: -9..-12%/yr, holdout -21..-33%, fall ~60%, both thresholds, both baskets. On
    all alt-bear days or the union with BTC-bear it is tune-only (holdout -3..-10%; union Sharpe 0.48 vs 1.20). Shorting
    the alt index on every ALT-ONLY day ~0 (-2.9%/yr), on every alt-bear day -18%/yr.
  3 Out of sample (2017-19 spot, frozen) the same ALT-ONLY rule made +22..+25%/yr - the sign flips between eras, as doc 13's
    chop placebo did (-14% in 2020-26, +7..+16% in 2017-19). Not a rule to run.
  4 On ALT-ONLY days the 7-book machine made +4.0% per 30 days: trend -9.1, MN +4.9, daily +4.2, capit2 +2.3, carry +0.4,
    bids +0.9 (booked-at-close caveat for trend / daily / capit2). The trend book is the loser, as in sideways months.
  5 Trend longs x0.5 on alt-bear days: below the bet-smaller line on the holdout in all 4 phases (-42..-107 points of CAGR at
    the same fall); no trend longs at all: fall 67% vs 50%, far below the line.
  P1-P4 and P6 RIGHT; P5 WRONG (MN +4.9% per 30 days, not ~0).
  Live, 2026-10-21 close (Binance, today's top-40 by volume - survivor-picked, a reading only): the big alts fell 10-18% in
  30 days (ETH -11, SOL -10, XRP -11, DOGE -18) while small coins pumped (QNT +207%, BTW +104%); the median-coin index sat
  6% under its 50-day average with the average still rising (+1.6% over 20 days) -> CHOP by this rule, not ALT-ONLY.

    python -m backtest.alt_bear             parts 1-3 -> logs/alt_bear.txt
    python -m backtest.alt_bear --books      part 4    -> logs/alt_bear_books.txt
    python -m backtest.alt_bear --defence    part 5    -> logs/alt_bear_defence.txt
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest import breadth_trade as bt  # noqa: E402
from backtest.breadth_attack import START, boot_t, breadth, ls_signal, run  # noqa: E402
from backtest.breadth_trade import half, instruments, stats  # noqa: E402
from backtest.carry_check import exact_funding  # noqa: E402
from backtest.market_neutral import btc_regime, load_panel  # noqa: E402

LOG = ROOT / "logs" / "alt_bear.txt"
LOW, HIGH = 0.100, 0.288


def trend_label(level: pd.Series) -> pd.Series:
    """btc_regime's rule on any level series, shifted so it is knowable."""
    ma = level.rolling(50).mean()
    sl = ma / ma.shift(20) - 1
    r = pd.Series("chop", index=level.index)
    r[(level > ma) & (sl > 0.02)] = "bull"
    r[(level < ma) & (sl < -0.02)] = "bear"
    return r.shift(1).ffill()


def load():
    C, F, first = load_panel()
    C.index = C.index.astype("datetime64[ns]")
    F.index = C.index
    ins = instruments(C, exact_funding(C.index, C.columns), first)
    lvl = (1 + ins["alt index (top-40)"][0].fillna(0.0)).cumprod()
    alt_reg = trend_label(lvl)
    btc_reg = btc_regime(C).reindex(C.index)
    return C, first, ins, alt_reg, btc_reg


def groups(alt_reg, btc_reg):
    bb = (btc_reg == "bear").astype(bool)
    ab = (alt_reg == "bear").astype(bool)
    return {"BTC-bear": bb, "ALT-ONLY": ab & ~bb, "ALT-bear": ab, "UNION": ab | bb}


def frozen(br, gate):
    return (gate & (br <= LOW)).astype(float) - (gate & (br >= HIGH)).astype(float)


def row(lab, x, pos):
    cagr, dd, ww, sh, inm = stats(x, pos)
    t, h = half(x)
    return (f"  {lab:<50}{cagr:>+7.1f}%{t:>+8.1f}%{h:>+8.1f}%{dd:>5.0f}%{ww:>+8.1f}%{sh:>7.2f}{inm:>6.0f}%"
            f"{boot_t(x):>+7.2f}"), (t, h, sh)


HDR = f"  {'':<50}{'CAGR':>8}{'TUNE/yr':>9}{'HOLD/yr':>9}{'DD':>6}{'worst wk':>9}{'Sharpe':>7}{'in mkt':>7}{'boot t':>7}"


def episodes(mask: pd.Series, gap=3):
    d = mask[mask].index
    out, s, e = [], None, None
    for t in d:
        if s is not None and (t - e).days <= gap + 1:
            e = t
        else:
            if s is not None:
                out.append((s, e))
            s = e = t
    if s is not None:
        out.append((s, e))
    return out


def main():
    C, first, ins, alt_reg, btc_reg = load()
    G = groups(alt_reg, btc_reg)
    alt, top10 = ins["alt index (top-40)"], ins["top-10 basket"]
    w = C.index >= START
    a_r, b_r = alt[0], ins["BTC"][0]
    L = [f"backtest/alt_bear.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; perp panel {C.index[w][0]:%Y-%m-%d} .. "
         f"{C.index[-1]:%Y-%m-%d}; ALT label = btc_regime's rule on the PIT top-40 alt index", "",
         "1. HOW OFTEN, AND WHAT HAPPENS IN IT (days since 2020-03; %/30 days, simple mean of daily returns x 30)"]
    rest = ~(G["BTC-bear"] | G["ALT-ONLY"])
    for lab, m in (("BTC-bear", G["BTC-bear"]), ("ALT-ONLY", G["ALT-ONLY"]), ("rest", rest)):
        m = m & w
        L.append(f"   {lab:<9} {int(m.sum()):>5} days ({m.sum() / w.sum() * 100:4.1f}%)   alt index {a_r[m].mean() * 3000:+6.2f}%   "
                 f"BTC {b_r[m].mean() * 3000:+6.2f}%")
    both = G["ALT-bear"] & G["BTC-bear"] & w
    L.append(f"   of the {int((G['BTC-bear'] & w).sum())} BTC-bear days, {int(both.sum())} are also ALT-bear")
    ep = episodes(G["ALT-ONLY"] & w)
    L += ["", f"   ALT-ONLY episodes (gaps <= 3 days merged): {len(ep)}; days median {np.median([(e - s).days + 1 for s, e in ep]):.0f}, "
          f"max {max((e - s).days + 1 for s, e in ep)}", f"   {'start':<12}{'end':<12}{'days':>5}{'alt index':>11}{'BTC':>9}"
          f"{'then BTC-bear?':>16}"]
    for s, e in ep:
        ar = (1 + a_r[s:e]).prod() - 1
        br_ = (1 + b_r[s:e]).prod() - 1
        nxt = G["BTC-bear"][e:e + pd.Timedelta(days=30)].any()
        L.append(f"   {s:%Y-%m-%d}  {e:%Y-%m-%d}  {(e - s).days + 1:>5}{ar * 100:>+10.1f}%{br_ * 100:>+8.1f}%"
                 f"{'yes, within 30d' if nxt else '':>16}")

    br = breadth(C, first, 20)
    L += ["", "2. THE SLEEVE'S RULE ON EACH DAY GROUP (lag 1, 7-day ladder, 12bp + funding + 1bp/day)", HDR]
    R = {}
    for gname in ("BTC-bear", "ALT-ONLY", "ALT-bear", "UNION"):
        g = G[gname]
        for tn, sig in (("expanding thirds", ls_signal(br, g)), ("frozen 10.0/28.8", frozen(br, g))):
            for iname, inst in (("alt index", alt), ("top-10", top10)):
                s, R[(gname, tn, iname)] = row(f"{gname:<9} {tn:<17} {iname}", *run(sig, inst))
                L.append(s)
        L.append("")
    L.append("   controls on ALT-ONLY days (alt index):")
    for lab, sig in (("long every ALT-ONLY day", G["ALT-ONLY"].astype(float)),
                     ("short every ALT-ONLY day", -G["ALT-ONLY"].astype(float)),
                     ("short every ALT-bear day", -G["ALT-bear"].astype(float))):
        s, R[("ctl", lab)] = row(lab, *run(sig, alt))
        L.append(s)
    exp_hist = br[G["ALT-ONLY"] & br.notna()]
    L.append(f"   breadth20 on ALT-ONLY days: thirds {exp_hist.quantile(1 / 3) * 100:.1f}% / {exp_hist.quantile(2 / 3) * 100:.1f}% "
             f"(BTC-bear days: 10.0% / 28.8%)")

    L += ["", "3. OUT OF SAMPLE, 2017-07..2019-12 spot, frozen 10.0/28.8, no funding (shorting alts was not possible then)"]
    L += oos()

    p2 = not any(R[("ALT-ONLY", tn, "top-10")][0] > 0 and R[("ALT-ONLY", tn, "top-10")][1] > 0
                 for tn in ("expanding thirds", "frozen 10.0/28.8"))
    p3 = R[("UNION", "expanding thirds", "top-10")][2] < R[("BTC-bear", "expanding thirds", "top-10")][2]
    sh = R[("ctl", "short every ALT-ONLY day")]
    share = (G["ALT-ONLY"] & w).sum() / w.sum()
    L += ["", "REGISTERED PREDICTIONS",
          f"  P1 ALT-ONLY 5-15% of days: {share * 100:.1f}% -> {'RIGHT' if 0.05 <= share <= 0.15 else 'WRONG'}",
          f"  P2 sleeve on ALT-ONLY does not pass both halves (top-10, either threshold) -> {'RIGHT' if p2 else 'WRONG'}",
          f"  P3 UNION Sharpe below BTC-bear's (top-10, expanding): {R[('UNION', 'expanding thirds', 'top-10')][2]:.2f} vs "
          f"{R[('BTC-bear', 'expanding thirds', 'top-10')][2]:.2f} -> {'RIGHT' if p3 else 'WRONG'}",
          f"  P4 short every ALT-ONLY day loses on a half: {sh[0]:+.1f} / {sh[1]:+.1f} -> {'RIGHT' if min(sh[:2]) < 0 else 'WRONG'}"]
    txt = "\n".join(L)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


def oos():
    from backtest import breadth_oos as bo
    C, V, first = bo.panel()
    X = C.to_numpy(float)
    ff = pd.DataFrame(X).ffill().to_numpy()
    m60 = bo.members(C, V, first, 60)
    ma = C.rolling(20, min_periods=20).mean().to_numpy()
    ok = np.isfinite(ma) & m60
    cnt = ok.sum(1)
    br = pd.Series(((X > ma) & ok).sum(1) / np.where(cnt >= 10, cnt, np.nan), index=C.index).shift(1)
    ins = {}
    for lab, n in (("alt index", 40), ("top-10", 10)):
        m = bo.members(C, V, first, n)
        r = np.full(len(C), np.nan)
        for d in range(1, len(C)):
            mem = m[d - 1]
            if mem.sum() >= min(8, n):
                r[d] = np.nanmean(ff[d, mem] / X[d - 1, mem] - 1)
        ins[lab] = (pd.Series(r, index=C.index), pd.Series(0.0, index=C.index), bt.REBAL_BP)
    alt_reg = trend_label((1 + ins["alt index"][0].fillna(0.0)).cumprod())
    btc_reg = btc_regime(C.rename(columns={"BTC": "BTCUSDT"})).reindex(C.index)
    G = groups(alt_reg, btc_reg)
    win = C.index <= bo.END
    out = [f"   days: BTC-bear {int((G['BTC-bear'] & win).sum())}, ALT-ONLY {int((G['ALT-ONLY'] & win).sum())} of {int(win.sum())}",
           f"   {'':<40}{'CAGR':>8}{'DD':>6}{'in mkt':>7}   2018    2019"]
    for gname in ("BTC-bear", "ALT-ONLY", "UNION"):
        for iname, inst in ins.items():
            x, pos = bt.ladder(frozen(br, G[gname]), *inst, lag=1)
            xw, pw = x[win], pos[win]
            cagr, dd, _, _, inm = bt.stats(xw, pw)
            y = lambda yr: ((1 + x[x.index.year == yr]).prod() - 1) * 100  # noqa: E731
            out.append(f"   {gname + ' ' + iname:<40}{cagr:>+7.1f}%{dd:>5.0f}%{inm:>6.0f}%  {y(2018):+6.1f}% {y(2019):+6.1f}%")
    return out


def books():
    from backtest.all_books import BOOKS, machine_books
    C, first, ins, alt_reg, btc_reg = load()
    G = groups(alt_reg, btc_reg)
    f = ROOT / "logs" / "daily_combos_cache" / "alt_bear_books.pkl"
    M = pickle.loads(f.read_bytes()) if f.exists() else machine_books()
    f.write_bytes(pickle.dumps(M))
    lab0 = pd.Series("rest", index=C.index)
    lab0[G["ALT-ONLY"]] = "ALT-ONLY"
    lab0[G["BTC-bear"]] = "BTC-bear"
    tab = []
    for x in M:                                    # orderings can differ by a calendar day (all_books.py s10 note)
        lab = lab0.reindex(x.index, method="ffill")
        keep = (x.index >= START) & (x.index <= C.index[-1])
        x = x[keep].copy()
        x["MACHINE"] = x[BOOKS].sum(axis=1)
        tab.append(x.groupby(lab[keep]).mean() * 3000)
    T = sum(tab) / len(tab)
    n = lab[keep].value_counts()
    L = [f"backtest/alt_bear.py --books, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; all_books.machine_books, 10 orderings; "
         f"mean %/30 days of each book by day group (trend gains shrunk, the rest raw). DESCRIPTIVE: trend / daily / capit2 "
         f"are booked at close", "", f"   {'group':<10}{'days':>6}" + "".join(f"{b:>10}" for b in BOOKS + ["MACHINE"])]
    for g in ("BTC-bear", "ALT-ONLY", "rest"):
        L.append(f"   {g:<10}{int(n.get(g, 0)):>6}" + "".join(f"{T.loc[g, b]:>+9.2f}%" for b in BOOKS + ["MACHINE"]))
    a = T.loc["ALT-ONLY"]
    p5 = a[BOOKS].idxmin() == "trend" and abs(a["mn_blend"]) <= 1.0
    L += ["", f"  P5 trend the biggest loser on ALT-ONLY days, MN within +-1%/30d: worst {a[BOOKS].idxmin()} {a[BOOKS].min():+.2f}%, "
          f"MN {a['mn_blend']:+.2f}% -> {'RIGHT' if p5 else 'WRONG'}"]
    txt = "\n".join(L)
    (ROOT / "logs" / "alt_bear_books.txt").write_text(txt + "\n", encoding="utf-8")
    print(txt)


def defence():
    import backtest.dd_fixes as D
    from backtest import trend_combos as TC
    from backtest.bar_phase import rows_for_phase
    from backtest.bull_boost import regimes
    _, _, _, alt_reg, _ = load()
    ab = (alt_reg == "bear").astype(bool)
    an, av = pd.DatetimeIndex(ab.index).as_unit("ns").asi8, ab.to_numpy(bool)   # row D is known at D 00:00 UTC

    def gate(k):
        def fn(r, t, ctx):
            if r["side"] != "long":
                return 1.0
            tn = pd.Timestamp(t).value if not isinstance(t, (int, np.integer)) else int(t)
            i = np.searchsorted(an, tn, side="right") - 1
            return k if (i >= 0 and av[i]) else 1.0
        return fn

    line = pickle.loads((ROOT / "logs" / "daily_combos_cache" / "trend_combos.pkl").read_bytes())
    f = ROOT / "logs" / "daily_combos_cache" / "alt_bear_defence.pkl"
    res = pickle.loads(f.read_bytes()) if f.exists() else {}
    bear = regimes()[1000]
    bn, bv = pd.DatetimeIndex(bear.index).as_unit("ns").asi8, bear.to_numpy(bool)
    KS = {"A05": 0.5, "A0": 0.0}
    for ph in TC.PHASES:
        if all((ph, k, sd) in res for k in KS for sd in TC.SEEDS):
            continue
        trows = D.decompose(rows_for_phase(ph, tight=True, time_stop=(100, 2.0), max_units=7))
        if ph == 0 and "check" not in res:
            chk = TC.stats(D.sim(trows, bn, bv, 0, lev=9.0, size_fn=D.anchor(21), g=1.0))
            gap = max(abs(chk[k] - line[(0, "g1.0", 0)][k]) for k in chk)
            assert gap < 1e-9, f"trend_combos' cached line is stale (gap {gap})"
            res["check"] = gap
        for sd in TC.SEEDS:
            for k, mult in KS.items():
                res[(ph, k, sd)] = TC.stats(D.sim(trows, bn, bv, sd, lev=9.0, size_fn=D.anchor(21), gate_fn=gate(mult)))
            print(f"  phase {ph} ordering {sd} done", flush=True)
        f.write_bytes(pickle.dumps(res))

    def agg(src, ph, k, key):
        return np.mean([src[(ph, k, sd)][key] for sd in TC.SEEDS])

    L = [f"backtest/alt_bear.py --defence, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; the triple, RAW, 4 bar phases x 10 "
         f"orderings; holdout from {TC.HOLDOUT:%Y-%m-%d} (trend_combos' split); cached line re-checked (gap {res['check']:.1e})",
         f"   ALT-bear days in the panel: {ab.mean() * 100:.0f}%", ""]
    passes = 0
    for k, nm in (("A05", "trend longs x0.5 on ALT-bear days"), ("A0", "no trend longs on ALT-bear days")):
        cells, ok = [], True
        for ph in TC.PHASES:
            pts = sorted((agg(line, ph, f"g{g}", "fall"), agg(line, ph, f"g{g}", "tune"), agg(line, ph, f"g{g}", "hold")) for g in TC.GS)
            fa = agg(res, ph, k, "fall")
            dt = agg(res, ph, k, "tune") - np.interp(fa, [a for a, _, _ in pts], [b for _, b, _ in pts])
            dh = agg(res, ph, k, "hold") - np.interp(fa, [a for a, _, _ in pts], [c for _, _, c in pts])
            ok = ok and dt > 0 and dh > 0
            cells.append(f"{dt * 100:+.0f}/{dh * 100:+.0f}")
        passes += ok
        L.append(f"  {nm:<36} tune {np.mean([agg(res, p, k, 'tune') for p in TC.PHASES]) * 100:+.0f}% hold "
                 f"{np.mean([agg(res, p, k, 'hold') for p in TC.PHASES]) * 100:+.0f}% fall "
                 f"{np.mean([agg(res, p, k, 'fall') for p in TC.PHASES]) * 100:.0f}% | vs line by phase {'  '.join(cells)} -> "
                 f"{'PASS' if ok else 'fail'}")
    base = [np.mean([agg(line, p, 'g1.0', key) for p in TC.PHASES]) for key in ('tune', 'hold', 'fall')]
    L.append(f"  {'base (x1.0)':<36} tune {base[0] * 100:+.0f}% hold {base[1] * 100:+.0f}% fall {base[2] * 100:.0f}%")
    L += ["", f"  P6 neither gate passes in all 4 phases -> {'RIGHT' if passes == 0 else 'WRONG'} ({passes} pass)"]
    txt = "\n".join(L)
    (ROOT / "logs" / "alt_bear_defence.txt").write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    if "--books" in sys.argv:
        books()
    elif "--defence" in sys.argv:
        defence()
    else:
        main()
