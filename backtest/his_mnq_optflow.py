"""MICRO NASDAQ FUTURES (RETAIL) AND NASDAQ FUTURES OPTIONS BEFORE HIS CLICKS (2026-11-22)

THE USER (2026-11-21): "there must be something that you are not looking at" -> after the three public sources never put next to his
clicks were listed (SPX 0DTE options, NASDAQ futures options, micro NASDAQ futures) -> "yes" to the quoted spend. SPX index options are
not in Databento's OPRA feed (symbology 422), so they cannot be tested here. The other two:
DATA   Databento GLBX.MDP3 `trades` with the aggressor side, for his 31 windows (his_tape.windows: 22 min before to 20 min after each
       statement NASDAQ entry, merged per day): MNQ.FUT parent (quoted $3.81, the user's yes 2026-11-21) and NQ.OPT parent (quoted
       ~$0); the CME NQ tape already cached by his_tape.py for the retail-vs-pro reading. Raw data in the git-ignored data folder.
SIGNALS  (his way > 0)  mnq_W: signed MNQ contracts (buyer-initiated minus seller-initiated) over W = 5 / 15 / 30 / 60 / 120 s before T,
         on the busiest outright MNQ contract of the window - the retail tape;
         opt_W: signed NQ options contracts over W = 30 / 60 / 120 / 300 s, bullish = a bought call or a sold put, bearish = a sold call
         or a bought put (aggressor side x call / put);
         div_W: retail against the pros - the NQ tape's sign over W = 30 / 60 / 120 s when the MNQ tape points the OTHER way (0 when
         they agree or either is flat).
TESTS    his_darkpool's three, unchanged: A his side vs the sign (binomial); B his moment's rank in its sitting (Wilcoxon); C the rule at
         the sittings' moments: trade with a top-quintile reading, +-7 race on the Exness mid, against the sittings' baseline; plus the
         unsigned rule (with / against the reading's own sign).
REGISTERED BEFORE ANY DATA IS FETCHED (2026-11-22)
  M1  A within 35-65% for every mnq and div feature. (75%)
  M2  The options are thin: under half his clicks have any NQ option trade in the 60 s before; A within 35-65% where they do. (75%)
  M3  C within 5 points of the baseline for every feature with >= 50 qualifying moments. (75%)
  LEAD LINE (his_darkpool's): A >= 75% with p < 0.01 or B >= 0.65 with p < 0.01, AND the rule beats the baseline by >= 10 points.

RESULT (2026-11-22, logs/his_mnq_optflow.txt): RULED OUT. Spent $3.81 of the Databento credit (MNQ; the quote checked again before the
  download) and $0.00 (NQ options). 2.4M MNQ trades on the busiest outright, 1,916 NQ option trades; 46 entries, 1,763 sitting moments,
  baseline 55.7%. His side vs the retail (MNQ) buy-minus-sell over 5-120 s: 39-59% (every p >= 0.18), ranks 0.45-0.54, rules 50-54%; vs
  the options (bought calls + sold puts minus the rest; 54% of his clicks had an option trade in the 60 s before) 47-62% (n 21-41),
  ranks 0.46-0.52, rules 52-58%; retail against the pros (div) 29-64% on 7-16 clicks, rules 52-55%. The lead line not hit. M1-M3
  'wrong' only at the edges of their bands (div_120s 29% on 7 clicks; options in 54% of clicks, not under half; two rules at 50%).

    python -m backtest.his_mnq_optflow
"""
from __future__ import annotations

import pickle
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import backtest.his_tape as TP  # noqa: E402
from backtest.his_race_curve import race2  # noqa: E402

LOG = ROOT / "logs" / "his_mnq_optflow.txt"
DATA = ROOT / "strategy_analysis" / "data"
MNQ_CACHE, OPT_CACHE = DATA / "mnq_trades_his.pkl", DATA / "nq_opt_trades_his.pkl"
APPROVED = {"MNQ.FUT": 3.81 * 1.05, "NQ.OPT": 0.10}          # the user's yes was for the quoted $3.81 (+5% rounding) and ~$0
W_MNQ, W_OPT, W_DIV = (5, 15, 30, 60, 120), (30, 60, 120, 300), (30, 60, 120)


def guarded_fetch(cl, wins, symbol: str, path: Path) -> pd.DataFrame:
    """Fetch the windows not yet cached, only if the fresh quote is within the approved amount."""
    C = pickle.loads(path.read_bytes()) if path.exists() else {}
    need = [w for w in wins if (str(w[0]), str(w[1])) not in C]
    if need:
        q = sum(float(cl.metadata.get_cost(dataset="GLBX.MDP3", symbols=[symbol], schema="trades", stype_in="parent",
                                           start=a.isoformat() + "Z", end=b.isoformat() + "Z")) for a, b in need)
        print(f"  {symbol}: {len(need)} windows to fetch, quoted ${q:.2f} (approved up to ${APPROVED[symbol]:.2f})", flush=True)
        if q > APPROVED[symbol]:
            sys.exit(f"{symbol}: quote ${q:.2f} is above the approved amount - nothing fetched")
    for i, (a, b) in enumerate(need, 1):
        store = TP_call(cl.timeseries.get_range, dataset="GLBX.MDP3", symbols=[symbol], schema="trades", stype_in="parent",
                        start=a.isoformat() + "Z", end=b.isoformat() + "Z")
        df = store.to_df(map_symbols=True).reset_index()
        tcol = "ts_event" if "ts_event" in df.columns else df.columns[0]
        sym = df["symbol"].astype(str) if "symbol" in df.columns else df["instrument_id"].astype(str)
        C[(str(a), str(b))] = pd.DataFrame({
            "ns": pd.to_datetime(df[tcol], utc=True).dt.tz_localize(None).astype("datetime64[ns]").astype("int64").to_numpy(),
            "size": df["size"].to_numpy(np.int64), "aggr": np.where(df["side"] == "B", 1, np.where(df["side"] == "A", -1, 0)),
            "sym": sym.to_numpy(), "px": df["price"].to_numpy(float)})
        path.write_bytes(pickle.dumps(C))
        print(f"  {symbol}: fetched {i}/{len(need)} ({len(df):,} trades)", flush=True)
    return C


def TP_call(f, **k):
    from backtest.his_darkpool import call
    return call(f, **k)


def mnq_flow(C: dict) -> tuple:
    """Per window, the busiest outright MNQ contract (no calendar spreads); signed contracts, cumulated."""
    parts = []
    for key, d in C.items():
        out = d[~d.sym.str.contains("-")]
        if not len(out):
            continue
        top = out.groupby("sym")["size"].sum().idxmax()
        parts.append(out[out.sym == top])
    T = pd.concat(parts).sort_values("ns", kind="stable")
    return T.ns.to_numpy(), np.r_[0.0, np.cumsum(T["size"] * T.aggr)]


def opt_flow(C: dict) -> tuple:
    """Signed NQ option contracts: bought call / sold put = +, sold call / bought put = - (symbols like 'NQZ6 C26500')."""
    T = pd.concat(C.values()).sort_values("ns", kind="stable")
    cp = T.sym.str.extract(r"\s([CP])\d")[0]
    T = T[cp.notna()].copy()
    T["cp"] = np.where(cp[cp.notna()] == "C", 1, -1)
    return T.ns.to_numpy(), np.r_[0.0, np.cumsum(T["size"] * T.aggr * T.cp)], len(T)


def main():
    from scipy.stats import binomtest, wilcoxon
    warnings.filterwarnings("ignore")
    x = TP.entries()
    wins = TP.windows(x)
    cl = TP.client()
    Cm = guarded_fetch(cl, wins, "MNQ.FUT", MNQ_CACHE)
    Co = guarded_fetch(cl, wins, "NQ.OPT", OPT_CACHE)
    m_ns, m_cum = mnq_flow(Cm)
    o_ns, o_cum, n_opt = opt_flow(Co)
    nq_ok = TP.CACHE.exists() and all((str(a), str(b)) in pickle.loads(TP.CACHE.read_bytes()) for a, b in wins)
    if nq_ok:
        NQ = TP.fetch(cl, wins)                                        # cached: nothing is downloaded (checked above)
        n_ns, n_cum = NQ.ns.to_numpy(), np.r_[0.0, np.cumsum(NQ["size"] * NQ.aggr)]
    ticks = pickle.loads(TP.TICKS.read_bytes())

    def window_sum(ns, cum, at, w):
        return cum[np.searchsorted(ns, at, "right")] - cum[np.searchsorted(ns, at - w * 10**9, "right")]

    rows = []
    for r in x.itertuples():
        day = ticks.get(r.d)
        if day is None:
            continue
        ts, mid, _ = day
        base = (r.d + pd.Timedelta(hours=9, minutes=30)).tz_localize("America/New_York").tz_convert("UTC").tz_localize(None).value
        others = x[x.d == r.d].t.to_numpy()
        starts = [("his", r.t)] + [("near", r.t + 60 * m) for m in list(range(-20, 0)) + list(range(1, 21))
                                   if np.min(np.abs(others - (r.t + 60 * m))) >= 60]
        for who, t in starts:
            at = base + int(t * 1e9)
            f = {f"mnq_{w}s": r.s * window_sum(m_ns, m_cum, at, w) for w in W_MNQ}
            f.update({f"opt_{w}s": r.s * window_sum(o_ns, o_cum, at, w) for w in W_OPT})
            if nq_ok:
                for w in W_DIV:
                    a_, b_ = window_sum(m_ns, m_cum, at, w), window_sum(n_ns, n_cum, at, w)
                    f[f"div_{w}s"] = r.s * np.sign(b_) if np.sign(a_) * np.sign(b_) < 0 else 0.0
            rows.append(dict(entry=r.Index, who=who, s=r.s, up=race2(ts, mid, t, 1, 600, 7, 7), **f))
    D = pd.DataFrame(rows)
    H, N = D[D.who == "his"], D[D.who == "near"]
    nb = N.dropna(subset=["up"])
    base = np.where(nb.s > 0, nb.up, 1 - nb.up).mean()
    opt60_cov = float((H["opt_60s"] != 0).mean())
    out = [f"backtest/his_mnq_optflow.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; {len(wins)} windows; MNQ trades on the busiest outright "
           f"{len(m_ns):,}; NQ option trades {n_opt:,}; NQ tape for the divergence: {'yes' if nq_ok else 'NO (not cached - skipped)'}; "
           f"{len(H)} of his entries, {len(N)} sitting moments", f"baseline: his side at the sittings' moments wins {base * 100:.1f}%; "
           f"his clicks with any NQ option trade in the 60 s before: {opt60_cov:.0%}", "",
           f"  {'feature':>10}{'agree':>8}{'p':>8}{'rank':>8}{'p':>8}{'rule':>8}{'n':>6}"]
    res = {}
    for k in [c for c in D.columns if c.startswith(("mnq_", "opt_", "div_"))]:
        v = H[k][H[k] != 0]
        ag = (v > 0).mean() if len(v) else np.nan
        pa = binomtest(int((v > 0).sum()), len(v), 0.5).pvalue if len(v) else np.nan
        rk = []
        for _, g in D.groupby("entry"):
            h, n = g[g.who == "his"], g[g.who == "near"]
            if len(h) and len(n) >= 10:
                rk.append((n[k] < h[k].iat[0]).mean() + 0.5 * (n[k] == h[k].iat[0]).mean())
        pb = wilcoxon(np.array(rk) - 0.5).pvalue if len(rk) > 5 and np.any(np.array(rk) != 0.5) else np.nan
        hi = nb[(nb[k] >= nb[k].quantile(0.8)) & (nb[k] > 0)]
        rule = np.where(hi.s > 0, hi.up, 1 - hi.up).mean() if len(hi) else np.nan
        raw = nb[k] * nb.s
        big = nb[(raw.abs() >= raw.abs().quantile(0.8)) & (raw != 0)]
        rb = big[k] * big.s
        w_with = np.where(rb > 0, big.up, 1 - big.up).mean() if len(big) else np.nan
        res[k] = (ag, pa, float(np.mean(rk)) if rk else np.nan, pb, rule, len(hi), len(v))
        out.append(f"  {k:>10}{ag * 100:>7.0f}%{pa:>8.3f}{res[k][2]:>8.2f}{pb:>8.3f}{rule * 100:>7.0f}%{len(hi):>6}"
                   f"   (n {len(v)}; any side: WITH the reading {w_with * 100:.0f}%, AGAINST {100 - w_with * 100:.0f}% of {len(big)})")
    lead = [k for k, v in res.items() if ((v[0] >= 0.75 and v[1] < 0.01) or (v[2] >= 0.65 and v[3] < 0.01)) and v[4] - base >= 0.10]
    m1 = [v[0] for k, v in res.items() if k.startswith(("mnq_", "div_")) and np.isfinite(v[0])]
    m2 = [v[0] for k, v in res.items() if k.startswith("opt_") and np.isfinite(v[0]) and v[6] >= 10]
    m3 = [v[4] for v in res.values() if np.isfinite(v[4]) and v[5] >= 50]
    ok = lambda b: "RIGHT" if b else "WRONG"  # noqa: E731
    out += ["", "REGISTERED PREDICTIONS",
            f"  M1 mnq / div agreement within 35-65%: {min(m1) * 100:.0f}..{max(m1) * 100:.0f}% -> {ok(min(m1) >= 0.35 and max(m1) <= 0.65)}",
            f"  M2 options thin (< half his clicks with a trade in 60 s: {opt60_cov:.0%}) and agreement 35-65% where present"
            + (f" ({min(m2) * 100:.0f}..{max(m2) * 100:.0f}%)" if m2 else " (too few)")
            + f" -> {ok(opt60_cov < 0.5 and all(0.35 <= a <= 0.65 for a in m2))}",
            f"  M3 rules within 5 points of {base * 100:.0f}%: " + (f"{min(m3) * 100:.0f}..{max(m3) * 100:.0f}%" if m3 else "none qualified")
            + f" -> {ok(all(abs(c - base) <= 0.05 for c in m3))}",
            f"  LEAD LINE: {', '.join(lead) if lead else 'not hit'}"]
    txt = "\n".join(out)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
