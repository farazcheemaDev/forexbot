"""THE CLASSIC CANDLESTICK PATTERNS AS TRADING RULES, ON CRYPTO PERPS (2026-11-02)

The user asked "did we test candle chart patterns". The repo had tested them only at one NASDAQ trader's moments
(his_1m.py: 13 one-minute patterns, none survive Holm) and one daily hammer / burst screener (stockbee_crypto.py: -0.30%
a trade). Nobody had scanned the textbook patterns as stand-alone rules. This does it once, with every choice fixed here.

UNIVERSE   point-in-time top-40 perps by the PRIOR month's volume, dead coins in (wide_book.eligibility, stables and
           non-crypto dropped); Binance perp bars 2020 .. 2026-09 built from the 1h archive (capitulation_wide.hourly: a gap of
           more than 7 days is a halt, shorter archive holes are kept and every trade window is checked for contiguity).
BARS       1h, 4h, 1d (UTC). A bar counts only if all its hours exist.
PATTERNS   17, defined in pattern_flags() from open / high / low / close of the signal bar and the bars before it only. A
           "long body" is a body at least as big as the mean body of the previous 10 bars; "small" is a body <= 30% of the range;
           a doji is a body <= 10% of the range; the prior trend is the previous bar's close against the close 5 bars earlier.
             hammer, inverted hammer (after a decline) | hanging man, shooting star (after a rise) | bullish / bearish engulfing |
             piercing line / dark cloud cover | morning / evening star | three white soldiers / three black crows |
             bullish / bearish harami | doji after a decline / after a rise | inside bar (no textbook direction)
TRADE      the pattern is known at the signal bar's close; ENTER at the NEXT bar's open, EXIT at the close of the H-th bar
           after the signal (H = 1 or 5 bars: 1h/5h, 4h/20h, 1d/5d). No stop, no target, no tuning. One trade per coin at a time
           (a signal inside an open trade is skipped). Both sides are tested for every pattern: the textbook side (long for
           bullish patterns, short for bearish ones) and its mirror. 17 patterns x 2 sides x 3 bar sizes x 2 horizons = 204 cells.
COSTS      12bp round trip; longs also pay funding at 1bp per 8h, shorts receive nothing (conservative, as stockbee_crypto.py).
CONTROL    DAY x SLOT-matched baseline: for every entry day AND entry slot (the hour of the day the trade is entered, in bars of the
           bar size), the mean gross return of ALL point-in-time coin-bars entered then, same horizon. A pattern's excess is its
           gross return minus that baseline (on the side traded), so market-wide drift, bull / bear months and the time-of-day
           seasonality of the pattern's own clustering cancel.
           AMENDED 2026-11-02 after the first run: the control began as DAY-matched only. backtest/candle_scan_check.py showed that
           the cells which looked best (4h fades, excess +0.3..+0.6%) fall to -0.07..+0.06% once the slot is matched too - the
           patterns cluster in certain 4h slots that carry their own drift. The first run's log is kept in
           logs/candle_scan_daymatched_superseded.txt; its predictions K3, K4, K5 were scored on that flawed control. Means and t statistics give every ENTRY DAY one vote (the average of the day means,
           and the plain t of those day means), so a negative mean can never print a positive t and a crash day on which many
           coins signal together is one bet.
SPLIT      tune before 2024-08-29, holdout after (the repo's 60 / 40 cut). A half needs >= 100 trades on >= 30 days to count.
PASS       net > 0 with t >= 2 AND excess > 0 with t >= 2 on BOTH halves, and Holm < 0.05 over every sized cell (cell p = the
           larger one-sided p of its two halves' net t). Cells whose excess alone has t >= 2 on both halves are listed as
           INFORMATION (a real tilt that the fee eats), not as passes.

REGISTERED BEFORE THE FIRST RUN (2026-11-02; my prior that anything passes is under 5%)
  K1  No cell passes.
  K2  At most 10 of the 204 cells have net > 0 and t >= 2 on both halves (before the excess and Holm conditions).
  K3  Replication fails: of the cells whose excess has t >= 2 on the tune half, fewer than half have t >= 2 with the same sign
      on the holdout.
  K4  Strong candles reverse at the short horizons (the capitulation family): at 1h and 4h, more than half of the TEXTBOOK cells
      (which almost all trade WITH the last strong candle) have a NEGATIVE gross excess.
  K5  No cell with >= 200 trades on each half has a gross excess above +0.30% a trade on both halves.

    python -m backtest.candle_scan
"""
from __future__ import annotations

import sys
from math import erfc, sqrt
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

LOG = ROOT / "logs" / "candle_scan.txt"
FEE = 12e-4
FUND_H = 1e-4 / 8.0                      # 1bp per 8h, charged on longs only
TFS = {"1h": 1, "4h": 4, "1d": 24}
HORIZONS = (1, 5)
LOOKBACK = 12                            # bars before the signal that the definitions may read (10-bar mean body, 6-bar trend)
D0 = np.datetime64("2019-01-01", "D")
CUT_DAY = int((np.datetime64("2024-08-29", "D") - D0) / np.timedelta64(1, "D"))
ND = int((np.datetime64("2027-01-01", "D") - D0) / np.timedelta64(1, "D"))
MIN_TRADES, MIN_DAYS = 100, 30

TEXTBOOK = {"HAMMER": 1, "INV_HAMMER": 1, "BULL_ENGULF": 1, "PIERCING": 1, "MORNING_STAR": 1, "THREE_WHITE": 1,
            "BULL_HARAMI": 1, "DOJI_DOWN": 1,
            "HANGING_MAN": -1, "SHOOTING_STAR": -1, "BEAR_ENGULF": -1, "DARK_CLOUD": -1, "EVENING_STAR": -1,
            "THREE_BLACK": -1, "BEAR_HARAMI": -1, "DOJI_UP": -1,
            "INSIDE_BAR": 0}


# ---------------------------------------------------------------- patterns

def _sh(x, k):
    """x shifted k bars later (value of the bar k before), NaN at the front."""
    out = np.full(len(x), np.nan)
    if k < len(x):
        out[k:] = x[:len(x) - k]
    return out


def _shb(b, k):
    out = np.zeros(len(b), bool)
    if k < len(b):
        out[k:] = b[:len(b) - k]
    return out


def pattern_flags(o, h, l, c):
    """{name: bool array}; flag[i] is True when the pattern ENDS on bar i. Reads bars i and earlier only."""
    o, h, l, c = (np.asarray(x, float) for x in (o, h, l, c))
    n = len(c)
    body, rng = np.abs(c - o), h - l
    green, red = c > o, c < o
    up, lw = h - np.maximum(o, c), np.minimum(o, c) - l
    with np.errstate(invalid="ignore", divide="ignore"):
        ab = pd.Series(body).rolling(10).mean().shift(1).to_numpy()
        longb = body >= ab                                       # NaN in the first bars -> False
        ok = rng > 0
        small = ok & (body <= 0.3 * rng)
        down5 = _sh(c, 1) < _sh(c, 6)
        up5 = _sh(c, 1) > _sh(c, 6)
        o1, c1, h1, l1, b1, r1 = (_sh(x, 1) for x in (o, c, h, l, body, rng))
        o2, c2, b2, r2 = (_sh(x, 2) for x in (o, c, body, rng))
        g1, rd1, g2, rd2 = _shb(green, 1), _shb(red, 1), _shb(green, 2), _shb(red, 2)
        lg1, lg2 = _shb(longb, 1), _shb(longb, 2)
        sm1 = _shb(small, 1)
        mid1, mid2 = (o1 + c1) / 2, (o2 + c2) / 2
        hammer_shape = ok & (lw >= 0.6 * rng) & small & (up <= 0.1 * rng)
        star_shape = ok & (up >= 0.6 * rng) & small & (lw <= 0.1 * rng)
        doji = ok & (body <= 0.1 * rng)
        f = {
            "HAMMER": hammer_shape & down5,
            "HANGING_MAN": hammer_shape & up5,
            "SHOOTING_STAR": star_shape & up5,
            "INV_HAMMER": star_shape & down5,
            "BULL_ENGULF": rd1 & green & (o <= c1) & (c >= o1) & (body > b1),
            "BEAR_ENGULF": g1 & red & (o >= c1) & (c <= o1) & (body > b1),
            "PIERCING": rd1 & lg1 & green & (o <= c1) & (c > mid1) & (c < o1),
            "DARK_CLOUD": g1 & lg1 & red & (o >= c1) & (c < mid1) & (c > o1),
            "MORNING_STAR": rd2 & lg2 & sm1 & (np.maximum(o1, c1) <= c2) & green & (c > mid2),
            "EVENING_STAR": g2 & lg2 & sm1 & (np.minimum(o1, c1) >= c2) & red & (c < mid2),
            "THREE_WHITE": green & g1 & g2 & (c > c1) & (c1 > c2) & (o >= o1) & (o <= c1) & (o1 >= o2) & (o1 <= c2)
                           & (body >= 0.5 * rng) & (b1 >= 0.5 * r1) & (b2 >= 0.5 * r2),
            "THREE_BLACK": red & rd1 & rd2 & (c < c1) & (c1 < c2) & (o <= o1) & (o >= c1) & (o1 <= o2) & (o1 >= c2)
                           & (body >= 0.5 * rng) & (b1 >= 0.5 * r1) & (b2 >= 0.5 * r2),
            "BULL_HARAMI": rd1 & lg1 & green & (o >= c1) & (c <= o1),
            "BEAR_HARAMI": g1 & lg1 & red & (o <= c1) & (c >= o1),
            "DOJI_DOWN": doji & down5,
            "DOJI_UP": doji & up5,
            "INSIDE_BAR": (h < h1) & (l > l1),
        }
    for k in f:
        f[k] = np.asarray(f[k], bool)
        f[k][:LOOKBACK] = False
    return f


# ---------------------------------------------------------------- trades

def valid_mask(t, step_ns, H):
    """True where a signal at bar i has LOOKBACK bars behind it and H bars ahead, all contiguous in time."""
    n = len(t)
    brk = np.r_[False, np.diff(np.asarray(t, "datetime64[ns]").astype("int64")) != step_ns]
    seg = np.cumsum(brk)
    i = np.arange(n)
    v = (i >= LOOKBACK) & (i + H < n)
    j0, j1 = np.clip(i - LOOKBACK, 0, n - 1), np.clip(i + H, 0, n - 1)
    return v & (seg[j0] == seg[j1])


def pick_trades(flag, valid, H):
    """Signal bars actually traded: one position per coin at a time. A trade from bar i holds bars i+1 .. i+H, so the next
    signal may come on bar i+H (its entry, the open of i+H+1, is after the exit)."""
    out, last = [], -1
    for i in np.flatnonzero(np.asarray(flag, bool) & np.asarray(valid, bool)):
        if i >= last:
            out.append(i)
            last = i + H
    return np.array(out, int)


def n_slots(tfh):
    return 24 // tfh


def slot_of(ent_t, tfh):
    """Which bar of the UTC day a trade is entered in (0 .. 24/tfh - 1)."""
    ent_t = np.asarray(ent_t, "datetime64[ns]")
    hr = ((ent_t.astype("datetime64[h]") - ent_t.astype("datetime64[D]").astype("datetime64[h]")) / np.timedelta64(1, "h")).astype(int)
    return hr // tfh


def day_index(t):
    return ((np.asarray(t, "datetime64[ns]").astype("datetime64[D]") - D0) / np.timedelta64(1, "D")).astype(int)


def trade_returns(o, c, idx, H):
    """Gross LONG return of trades signalled on bars idx: in at the NEXT bar's open, out at the close H bars after the signal."""
    idx = np.asarray(idx, int)
    return c[idx + H] / o[idx + 1] - 1


# ---------------------------------------------------------------- statistics

def day_mean_t(x, day):
    """(mean, t, number of days): every ENTRY DAY counts once. The mean is the average of the days' means and t is the plain
    t of those day means, so the sign of t is always the sign of the printed mean, and a crash day on which forty coins signal
    at once is one bet, not forty (a trade-weighted cluster t lets such a day dominate and shrinks its own standard error)."""
    x = np.asarray(x, float)
    if len(x) < 3:
        return (float(x.mean()) if len(x) else np.nan), np.nan, 0
    u, inv = np.unique(day, return_inverse=True)
    g = len(u)
    dm = np.bincount(inv, weights=x) / np.bincount(inv)
    m = float(dm.mean())
    if g < 3:
        return m, np.nan, g
    sd = float(dm.std(ddof=1))
    return m, (m / (sd / sqrt(g)) if sd > 0 else np.nan), g


def cell_stats(day, gross, base, side, hours, mask, key=None):
    """One half of one cell. net = side * gross - costs; excess = side * (gross - the baseline at the trade's key), where the key
    is the entry day x slot (or just the day when key is None)."""
    key = day if key is None else key
    day, gross, key = day[mask], gross[mask], key[mask]
    b = base[key]
    keep = np.isfinite(b) & np.isfinite(gross)
    day, gross, b = day[keep], gross[keep], b[keep]
    if len(gross) < 3:
        return None
    cost = FEE + (FUND_H * hours if side > 0 else 0.0)
    net, t_net, days = day_mean_t(side * gross - cost, day)
    exc, t_exc, _ = day_mean_t(side * (gross - b), day)
    return dict(n=len(gross), days=days, net=net, t=t_net, exc=exc, t_exc=t_exc, win=float((side * gross - cost > 0).mean()))


def p_one_sided(t):
    return 1.0 if t is None or not np.isfinite(t) else 0.5 * erfc(t / sqrt(2))


def holm(ps):
    """Holm-adjusted p for a list of p-values, returned in the input order."""
    order = np.argsort(ps, kind="stable")
    out = np.empty(len(ps))
    run = 0.0
    for r, i in enumerate(order):
        run = max(run, min(1.0, ps[i] * (len(ps) - r)))
        out[i] = run
    return out


def sized(s):
    return s is not None and s["n"] >= MIN_TRADES and s["days"] >= MIN_DAYS


def passes(tu, ho, holm_p):
    if not (sized(tu) and sized(ho)):
        return False
    return all(s["net"] > 0 and s["t"] >= 2 and s["exc"] > 0 and s["t_exc"] >= 2 for s in (tu, ho)) and holm_p < 0.05


def information(tu, ho):
    return sized(tu) and sized(ho) and all(s["exc"] > 0 and s["t_exc"] >= 2 for s in (tu, ho))


# ---------------------------------------------------------------- data

def to_tf(h, hours):
    """Bars of `hours` hours from the 1h frame; a bar is kept only when all its hours exist."""
    if hours == 1:
        d = h[["time", "open", "high", "low", "close"]].copy()
        d.columns = ["time", "o", "h", "l", "c"]
        return d.reset_index(drop=True)
    g = h.set_index("time").resample(f"{hours}h")
    out = pd.DataFrame({"o": g["open"].first(), "h": g["high"].max(), "l": g["low"].min(), "c": g["close"].last(),
                        "n": g["close"].count()})
    return out[out.n == hours].drop(columns="n").reset_index()


def process(d, elig_months, tfh, cells, base_sum, base_cnt, counts):
    """Add one coin's trades (all patterns, both horizons) and its baseline to the accumulators."""
    n = len(d)
    if n < 60:
        return
    t = d["time"].to_numpy("datetime64[ns]")
    o, h, l, c = (d[k].to_numpy(float) for k in ("o", "h", "l", "c"))
    fl = pattern_flags(o, h, l, c)
    member = np.isin(t.astype("datetime64[M]"), elig_months)
    step = tfh * 3600 * 10 ** 9
    S = n_slots(tfh)
    for H in HORIZONS:
        valid = valid_mask(t, step, H) & member & (o > 0) & (c > 0)
        allv = np.flatnonzero(valid)
        if not len(allv):
            continue
        g_all = trade_returns(o, c, allv, H)
        ok = np.isfinite(g_all)
        ent = t[allv + 1]
        ky = day_index(ent) * S + slot_of(ent, tfh)
        base_sum[(tfh, H)] += np.bincount(ky[ok], weights=g_all[ok], minlength=ND * S)
        base_cnt[(tfh, H)] += np.bincount(ky[ok], minlength=ND * S)
        for name, f in fl.items():
            pk = pick_trades(f, valid, H)
            if H == HORIZONS[0]:
                counts[(tfh, name)] = counts.get((tfh, name), 0) + int((f & valid).sum())
            if not len(pk):
                continue
            g = trade_returns(o, c, pk, H)
            good = np.isfinite(g)
            ee = t[pk + 1]
            dd = day_index(ee)
            cells.setdefault((tfh, H, name), []).append((dd[good], (dd * S + slot_of(ee, tfh))[good], g[good]))


def run_universe():
    from backtest.capitulation_wide import hourly
    from backtest.market_neutral import drop_non_crypto
    from backtest.wide_book import eligibility
    elig = drop_non_crypto(eligibility(40))
    coins = sorted(s for s in elig if elig[s] and s.endswith("USDT"))
    cells = {tfh: {} for tfh in TFS.values()}
    base_sum = {(tfh, H): np.zeros(ND * n_slots(tfh)) for tfh in TFS.values() for H in HORIZONS}
    base_cnt = {(tfh, H): np.zeros(ND * n_slots(tfh)) for tfh in TFS.values() for H in HORIZONS}
    counts, used = {}, 0
    for sym in coins:
        h = hourly(sym)
        if h is None:
            continue
        em = np.array(sorted(elig[sym]), dtype="datetime64[M]")
        used += 1
        for tfh in TFS.values():
            process(to_tf(h, tfh), em, tfh, cells[tfh], base_sum, base_cnt, counts)
    return coins, used, cells, base_sum, base_cnt, counts


def evaluate(cells, base_sum, base_cnt):
    """All cells -> list of dict rows with tune / hold stats."""
    rows = []
    for tfh in TFS.values():
        for H in HORIZONS:
            with np.errstate(invalid="ignore", divide="ignore"):
                base = np.where(base_cnt[(tfh, H)] > 0, base_sum[(tfh, H)] / np.maximum(base_cnt[(tfh, H)], 1), np.nan)
            for name in TEXTBOOK:
                parts = cells[tfh].get((tfh, H, name))
                if not parts:
                    continue
                day = np.concatenate([p[0] for p in parts])
                key = np.concatenate([p[1] for p in parts])
                gross = np.concatenate([p[2] for p in parts])
                for side in (1, -1):
                    tu = cell_stats(day, gross, base, side, H * tfh, day < CUT_DAY, key)
                    ho = cell_stats(day, gross, base, side, H * tfh, day >= CUT_DAY, key)
                    rows.append(dict(tf=tfh, H=H, pat=name, side=side, text=TEXTBOOK[name] == side, tu=tu, ho=ho))
    cand = [r for r in rows if sized(r["tu"]) and sized(r["ho"])]
    ps = [max(p_one_sided(r["tu"]["t"]), p_one_sided(r["ho"]["t"])) for r in cand]
    adj = holm(ps) if ps else []
    for r in rows:
        r["holm"] = 1.0
    for r, a in zip(cand, adj):
        r["holm"] = float(a)
    for r in rows:
        r["pass"] = passes(r["tu"], r["ho"], r["holm"])
        r["info"] = information(r["tu"], r["ho"])
    return rows


# ---------------------------------------------------------------- report

TFN = {1: "1h", 4: "4h", 24: "1d"}


def fmt(s):
    if s is None:
        return "  -  "
    return f"n{s['n']:6d} net{s['net'] * 100:+6.2f}% t{s['t']:+5.1f} exc{s['exc'] * 100:+6.2f}% t{s['t_exc']:+5.1f}"


def score(rows):
    cand = [r for r in rows if sized(r["tu"]) and sized(r["ho"])]
    passed = [r for r in rows if r["pass"]]
    both_net = [r for r in cand if all(r[k]["net"] > 0 and r[k]["t"] >= 2 for k in ("tu", "ho"))]
    tune_exc = [r for r in cand if r["tu"]["t_exc"] >= 2]
    repl = [r for r in tune_exc if r["ho"]["t_exc"] >= 2]
    short_text = [r for r in cand if r["text"] and r["tf"] in (1, 4)]
    neg = [r for r in short_text if (r["tu"]["exc"] * r["tu"]["n"] + r["ho"]["exc"] * r["ho"]["n"]) < 0]
    big = [r for r in rows if sized(r["tu"]) and sized(r["ho"]) and r["tu"]["n"] >= 200 and r["ho"]["n"] >= 200
           and min(r["tu"]["exc"], r["ho"]["exc"]) > 0.003]
    return dict(
        cells=len(rows), sized=len(cand), passed=passed, both_net=both_net, tune_exc=tune_exc, repl=repl,
        k1=len(passed) == 0, k2=len(both_net) <= 10,
        k3=(len(tune_exc) == 0 or len(repl) < 0.5 * len(tune_exc)),
        k4=(len(short_text) > 0 and len(neg) > 0.5 * len(short_text)), neg=len(neg), short_text=len(short_text),
        k5=len(big) == 0, big=big)


def main():
    coins, used, cells, base_sum, base_cnt, counts = run_universe()
    rows = evaluate(cells, base_sum, base_cnt)
    sc = score(rows)
    L = [f"backtest/candle_scan.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; {used} of {len(coins)} PIT-top-40 perps with data; "
         f"tune < 2024-08-29; 12bp + 1bp/8h on longs; entry = next bar's open; control = entry day x slot", ""]
    L.append("BASELINE (every PIT coin-bar, long, gross per trade; tune / holdout)")
    for tfh in TFS.values():
        for H in HORIZONS:
            S = n_slots(tfh)
            s, n = base_sum[(tfh, H)].reshape(ND, S).sum(1), base_cnt[(tfh, H)].reshape(ND, S).sum(1)
            a, b = slice(0, CUT_DAY), slice(CUT_DAY, ND)
            L.append(f"  {TFN[tfh]} H{H}: {s[a].sum() / max(n[a].sum(), 1) * 100:+.3f}% / {s[b].sum() / max(n[b].sum(), 1) * 100:+.3f}%   "
                     f"({int(n.sum()):,} coin-bars)")
    L += ["", "SIGNALS (pattern ends on a PIT bar, any horizon-1 valid bar), by bar size: " + "; ".join(
        f"{TFN[tfh]} " + ",".join(f"{k.lower()} {counts.get((tfh, k), 0)}" for k in ("BULL_ENGULF", "HAMMER", "INSIDE_BAR")) for tfh in TFS.values()), ""]
    L.append(f"{'cell':<30}{'side':<7}  {'TUNE':<56}{'HOLDOUT':<56}holm")
    for r in sorted(rows, key=lambda r: (r["tf"], r["H"], r["pat"], -r["side"])):
        tag = "PASS" if r["pass"] else ("info" if r["info"] else "")
        L.append(f"{TFN[r['tf']] + ' H' + str(r['H']) + ' ' + r['pat']:<30}{('book' if r['text'] else 'mirror') + ('L' if r['side'] > 0 else 'S'):<7}  "
                 f"{fmt(r['tu']):<56}{fmt(r['ho']):<56}{r['holm']:.2f} {tag}")
    L += ["", f"cells {sc['cells']} ({sc['sized']} sized: >= {MIN_TRADES} trades on >= {MIN_DAYS} days in each half)",
          f"PASS: {len(sc['passed'])}   net>0 & t>=2 on both halves: {len(sc['both_net'])}   "
          f"excess t>=2 on tune: {len(sc['tune_exc'])}, kept on holdout: {len(sc['repl'])}"]
    info = [r for r in rows if r["info"]]
    L.append(f"INFORMATION (excess t>=2 on both halves, fee not covered): {len(info)}")
    for r in sorted(info, key=lambda r: -min(r['tu']['t_exc'], r['ho']['t_exc']))[:15]:
        L.append(f"   {TFN[r['tf']]} H{r['H']} {r['pat']} {'long' if r['side'] > 0 else 'short'}  excess {r['tu']['exc'] * 100:+.2f}% / {r['ho']['exc'] * 100:+.2f}%  "
                 f"net {r['tu']['net'] * 100:+.2f}% / {r['ho']['net'] * 100:+.2f}%")
    best = sorted([r for r in rows if sized(r['tu']) and sized(r['ho'])], key=lambda r: -min(r['tu']['net'], r['ho']['net']))[:8]
    L += ["", "BEST CELLS by the worse half's net per trade:"]
    for r in best:
        L.append(f"   {TFN[r['tf']]} H{r['H']} {r['pat']} {'long' if r['side'] > 0 else 'short'} ({'textbook' if r['text'] else 'mirror'})  "
                 f"net {r['tu']['net'] * 100:+.2f}% / {r['ho']['net'] * 100:+.2f}%  t {r['tu']['t']:+.1f} / {r['ho']['t']:+.1f}  holm {r['holm']:.2f}")
    L += ["", "REGISTERED PREDICTIONS",
          f"  K1 no cell passes -> {'RIGHT' if sc['k1'] else 'WRONG'} ({len(sc['passed'])} passed)",
          f"  K2 at most 10 cells net>0 & t>=2 on both halves -> {'RIGHT' if sc['k2'] else 'WRONG'} ({len(sc['both_net'])})",
          f"  K3 fewer than half of the tune-half excess cells replicate -> {'RIGHT' if sc['k3'] else 'WRONG'} ({len(sc['repl'])} of {len(sc['tune_exc'])})",
          f"  K4 more than half of the 1h / 4h textbook cells have negative gross excess -> {'RIGHT' if sc['k4'] else 'WRONG'} ({sc['neg']} of {sc['short_text']})",
          f"  K5 no cell with >= 200 trades per half has excess > +0.30% on both halves -> {'RIGHT' if sc['k5'] else 'WRONG'} ({len(sc['big'])})"]
    txt = "\n".join(L)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
