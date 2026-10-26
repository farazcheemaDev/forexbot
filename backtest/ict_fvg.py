"""ICT FAIR VALUE GAPS AS A RETEST TRADE: THE SKE-Labs ict-smart-money/fair-value-gaps SKILL, TESTED AGAINST A MATCHED CONTROL (2026-10-27)

The skill (SKE-Labs/agent-trading-skills, skills/ict-smart-money/fair-value-gaps) gives a three-candle definition and says to
test it, expire zones, count unfilled ones, and never call gaps magnets. Never tested here as a trade (his_ta.py asked whether
smart-money concepts mark HIS entries; sweep_reclaim.py tested the ICT sweep). This asks the plain question: is a retest of a fair
value gap a better place to buy / sell than a random pullback with the same stop and target?
RULE (bullish; bearish mirrors)  candle 1 = bar i-2, candle 2 = bar i-1 (the impulse), candle 3 = bar i.
  FVG     low[i] > high[i-2] AND bar i-1 closes up with a body >= 1.0 x ATR(14) AND the gap (low[i] - high[i-2]) >= 0.25 x ATR.
          Zone = [high[i-2], low[i]]. Formed and known at the CLOSE of bar i.
  ENTRY   a resting limit at the zone's upper edge (low[i]); active for the next 24 bars; filled when a bar's low reaches it (at
          the limit, or at the open if the bar opens below it); zones never touched in 24 bars are counted, not dropped.
  STOP    zone bottom less 0.1 x ATR; if a fill bar also reaches the stop the trade is a stop-out (pessimistic).
  TARGET  the impulse's high = max(high[i-1], high[i]); EXIT otherwise 24 bars after the fill at the close.
CONTROL (matched) for every FVG a pullback limit at a RANDOM bar with the same ATR-normalised geometry (depth below the close, stop
  distance, target distance, expiry) - 3 draws per FVG. If gap location carries information, the real zones beat it.
MARKETS  crypto 1h: BTC ETH SOL XRP BNB ADA DOGE LINK (Binance perp, 2020-02..2026-09, strategy_analysis/data/*_1h_2400d.json), cost 12bp
         round trip; NASDAQ 5-minute bars inside the cash session (HistData NSXUSD, 2010-11..2026-09), cost 1.27bp.
SPLIT    tune = first 60% of the bars in time. t by entry date (trades on the same day are averaged).

REGISTERED BEFORE THE FIRST RUN (2026-10-27)
  F1  The FVG does not beat its matched control by 0.2% a trade or more on BOTH halves, in the crypto basket or on NASDAQ.
  F2  No FVG set (crypto longs, crypto shorts, NASDAQ longs, NASDAQ shorts) has a positive net with t >= 2 on both halves.
  F3  The touch rate of FVG zones within 24 bars is within 10 points of the control's (zones are not magnets beyond ordinary pullbacks).
PASS    an FVG set positive with t >= 2 on both halves AND beating its control by >= 0.2% on both halves. Otherwise none.

    python -m backtest.ict_fvg
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
DATA = ROOT / "strategy_analysis" / "data"
LOG = ROOT / "logs" / "ict_fvg.txt"
EXP, HOLD = 24, 24
COINS = ["BTC", "ETH", "SOL", "XRP", "BNB", "ADA", "DOGE", "LINK"]


def atr(h, l, c, n=14):
    tr = np.maximum(h - l, np.maximum(np.abs(h - np.r_[c[0], c[:-1]]), np.abs(l - np.r_[c[0], c[:-1]])))
    return pd.Series(tr).ewm(alpha=1 / n, adjust=False).mean().to_numpy()


def find_fvgs(o, h, l, c, a, dirn):
    """Bar indices i where a (dirn=+1 bullish / -1 bearish) FVG completes, with zone edges."""
    out = []
    for i in range(20, len(c)):
        if dirn > 0:
            ok = l[i] > h[i - 2] and c[i - 1] > o[i - 1] and (c[i - 1] - o[i - 1]) >= a[i - 1] and (l[i] - h[i - 2]) >= 0.25 * a[i - 1]
            if ok:
                out.append((i, l[i], h[i - 2], max(h[i - 1], h[i])))
        else:
            ok = h[i] < l[i - 2] and c[i - 1] < o[i - 1] and (o[i - 1] - c[i - 1]) >= a[i - 1] and (l[i - 2] - h[i]) >= 0.25 * a[i - 1]
            if ok:
                out.append((i, h[i], l[i - 2], min(l[i - 1], l[i])))
    return out


def run_zone(o, h, l, c, a, i, top, bottom, target, dirn, cost):
    """Resting limit at `top` for EXP bars after bar i. Returns (touched, net or None)."""
    n = len(c)
    stop = bottom - dirn * 0.1 * a[i]
    for j in range(i + 1, min(i + EXP, n - 1) + 1):
        hit = (l[j] <= top) if dirn > 0 else (h[j] >= top)
        if not hit:
            continue
        e = min(top, o[j]) if dirn > 0 else max(top, o[j])
        # the fill bar itself
        if (dirn > 0 and l[j] <= stop) or (dirn < 0 and h[j] >= stop):
            x = stop
            return True, dirn * (x / e - 1) - cost
        for k in range(j + 1, min(j + HOLD, n - 1) + 1):
            if (dirn > 0 and l[k] <= stop) or (dirn < 0 and h[k] >= stop):
                x = min(stop, o[k]) if dirn > 0 else max(stop, o[k])
                return True, dirn * (x / e - 1) - cost
            if (dirn > 0 and h[k] >= target) or (dirn < 0 and l[k] <= target):
                x = target
                return True, dirn * (x / e - 1) - cost
        x = c[min(j + HOLD, n - 1)]
        return True, dirn * (x / e - 1) - cost
    return False, None


def tstat(x):
    x = np.asarray(x, float)
    return x.mean() / (x.std(ddof=1) / np.sqrt(len(x))) if len(x) > 2 and x.std(ddof=1) > 0 else np.nan


def process(o, h, l, c, idx, cost, rng, label):
    a = atr(h, l, c)
    n = len(c)
    rows = []
    for dirn in (1, -1):
        for (i, top, bottom, target) in find_fvgs(o, h, l, c, a, dirn):
            touched, net = run_zone(o, h, l, c, a, i, top, bottom, target, dirn, cost)
            rows.append((idx[i], "FVG", dirn, touched, net))
            # matched controls: same ATR-normalised geometry at random bars
            depth = (c[i] - top) / a[i] * dirn            # how far the limit sits below (above) the close, in ATR
            sd = (top - bottom) * dirn / a[i]
            td = (target - top) * dirn / a[i]
            for _ in range(3):
                j = int(rng.integers(20, n - EXP - HOLD - 2))
                t2 = c[j] - dirn * depth * a[j]
                b2 = t2 - dirn * sd * a[j]
                g2 = t2 + dirn * td * a[j]
                if depth <= 0 or sd <= 0 or td <= 0:
                    continue
                tc, nc = run_zone(o, h, l, c, a, j, t2, b2, g2, dirn, cost)
                rows.append((idx[j], "CTL", dirn, tc, nc))
    return pd.DataFrame(rows, columns=["t", "kind", "dir", "touched", "net"])


def summarize(df, cut, L, label):
    L.append(f"== {label}")
    res = {}
    for d, dn in ((1, "longs"), (-1, "shorts"), (0, "both")):
        sub = df if d == 0 else df[df.dir == d]
        row = {}
        for kind in ("FVG", "CTL"):
            s = sub[sub.kind == kind]
            filled = s[s.touched]
            for hn, m in (("tune", filled.t < cut), ("hold", filled.t >= cut)):
                f = filled[m]
                g = f.groupby(f.t.dt.normalize()).net.mean() if len(f) else pd.Series(dtype=float)
                row[(kind, hn)] = (len(f), f.net.mean() if len(f) else np.nan, tstat(g) if len(g) > 2 else np.nan)
            row[(kind, "touch")] = s.touched.mean() if len(s) else np.nan
        res[dn] = row
        L.append(f"  {dn:6} FVG touch {row[('FVG', 'touch')] * 100:4.0f}% | tune n {row[('FVG', 'tune')][0]:5d} net {row[('FVG', 'tune')][1] * 100:+6.2f}% t {row[('FVG', 'tune')][2]:+5.1f}"
                 f" | hold n {row[('FVG', 'hold')][0]:5d} net {row[('FVG', 'hold')][1] * 100:+6.2f}% t {row[('FVG', 'hold')][2]:+5.1f}"
                 f"   || CTL touch {row[('CTL', 'touch')] * 100:4.0f}% | tune {row[('CTL', 'tune')][1] * 100:+6.2f}% | hold {row[('CTL', 'hold')][1] * 100:+6.2f}%")
    return res


def main():
    rng = np.random.default_rng(9)
    L = [f"backtest/ict_fvg.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; FVG = 3-candle gap, strong impulse, retest limit, 24-bar expiry; "
         f"control = same ATR-geometry at random bars (3 per FVG)", ""]
    # crypto 1h
    parts = []
    for sym in COINS:
        rows = json.load(open(DATA / f"{sym}USDT_1h_2400d.json"))
        d = pd.DataFrame(rows)
        idx = pd.to_datetime(d.t, unit="ms")
        o, h, l, c = (d[k].to_numpy(float) for k in "ohlc")
        parts.append(process(o, h, l, c, idx, 12e-4, rng, sym))
    cr = pd.concat(parts, ignore_index=True)
    cut_c = cr.t.sort_values().iloc[int(len(cr) * 0.6)]
    rc = summarize(cr, cut_c, L, f"CRYPTO 1h, 8 coins, split {cut_c:%Y-%m-%d}")
    # NASDAQ 5m inside sessions
    from backtest.fx_intraday_pub import INSTR, SLIP, session
    A, dates, prev = session("NASDAQ")
    cost = (INSTR["NASDAQ"][4] + SLIP) / 1e4
    Lm = A["l"].shape[1]
    k5 = Lm // 5
    sh = lambda X, f: f(X[:, :k5 * 5].reshape(len(dates), k5, 5), axis=2)   # noqa: E731
    O5, H5, L5, C5 = A["o"][:, :k5 * 5:5], sh(A["h"], np.max), sh(A["l"], np.min), A["c"][:, 4:k5 * 5:5]
    parts = []
    for i in range(len(dates)):
        t = pd.date_range(dates[i] + pd.Timedelta(hours=9, minutes=30), periods=k5, freq="5min")
        parts.append(process(O5[i], H5[i], L5[i], C5[i], t, cost, rng, "NASDAQ"))
    nq = pd.concat([p for p in parts if len(p)], ignore_index=True)
    nq["t"] = pd.to_datetime(nq["t"])
    cut_n = dates[int(len(dates) * 0.6)]
    rn = summarize(nq, cut_n, L, f"NASDAQ 5m (cash session, zones form and die inside a day), split {cut_n:%Y-%m-%d}")
    # predictions
    def edge(res, d):
        r = res[d]
        return [r[("FVG", h)][1] - r[("CTL", h)][1] for h in ("tune", "hold")]

    f1 = not any(all(e >= 0.002 for e in edge(res, d)) for res in (rc, rn) for d in ("longs", "shorts", "both"))
    passes = []
    for nm, res in (("crypto", rc), ("NASDAQ", rn)):
        for d in ("longs", "shorts"):
            r = res[d]
            if all(r[("FVG", h)][1] > 0 and r[("FVG", h)][2] >= 2 for h in ("tune", "hold")) and all(e >= 0.002 for e in edge(res, d)):
                passes.append(f"{nm} {d}")
    f2 = not any(all(res[d][("FVG", h)][1] > 0 and res[d][("FVG", h)][2] >= 2 for h in ("tune", "hold")) for res in (rc, rn) for d in ("longs", "shorts"))
    f3 = all(abs(res["both"][("FVG", "touch")] - res["both"][("CTL", "touch")]) <= 0.10 for res in (rc, rn))
    L += ["", f"  PASS: {passes or 'none'}", "", "REGISTERED PREDICTIONS",
          f"  F1 FVG does not beat its control by >= 0.2% on both halves anywhere -> {'RIGHT' if f1 else 'WRONG'}",
          f"  F2 no FVG set positive with t >= 2 on both halves -> {'RIGHT' if f2 else 'WRONG'}",
          f"  F3 touch rates within 10 points of the control's (crypto {rc['both'][('FVG', 'touch')] * 100:.0f} vs {rc['both'][('CTL', 'touch')] * 100:.0f}; "
          f"NASDAQ {rn['both'][('FVG', 'touch')] * 100:.0f} vs {rn['both'][('CTL', 'touch')] * 100:.0f}) -> {'RIGHT' if f3 else 'WRONG'}"]
    txt = "\n".join(L)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
