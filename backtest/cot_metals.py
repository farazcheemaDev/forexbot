"""WHICH SIDE IS CROWDED, AND DOES THE CROWD'S SIDE TELL YOU WHAT HAPPENS NEXT? CFTC DISAGGREGATED POSITIONS ON PLATINUM, PALLADIUM, GOLD, SILVER, COPPER (2026-10-28)

THE USER (2026-10-28, with a screenshot of the CFTC Disaggregated report for 2026-10-20 - palladium and platinum - and CME's Final Settlements page):
"make futures positional data from it, compute and correlate both and say how to test; the tool must tell me on which side of the market there will be an
imbalance, and beforehand". The screenshot's own numbers: PALLADIUM open interest 25,696, managed money 5,385 long / 17,528 short = 68% of the open interest
short (net short 47% of it); PLATINUM open interest 73,635, managed money 17,786 long / 11,171 short.
WHAT THIS TESTS (CFTC side only - see the CME note below): the weekly Disaggregated report (futures + options combined, free from CFTC's public API,
2006-06 on) for the five metal markets: managed-money net position as a share of open interest and its trailing 3-year percentile (how crowded, which side),
swap dealers' net share (the counterparties), and the 4-week change in managed-money net (is the crowd still building). Each signal is read at the REPORT
date (a Tuesday), which becomes public on Friday 15:30 New York; the first trade is the CLOSE of the first trading day after that Friday (Monday), held
20 trading days (4 weeks). Prices: the physical-metal ETFs PPLT / PALL / GLD / SLV (no roll gaps) and CPER for copper (a futures fund), the futures
(PL=F ...) as a cross-check. 12bp round trip is charged on every trade (rule 1 - far more than a futures desk pays).
CME SIDE - NOT BACKTESTABLE: CME's free settlement feed (the page behind 'Final Settlements') keeps only the LAST 5 TRADE DATES per product (checked in the
browser pane 2026-10-28: its TradeDate list has 5 entries; any older date returns empty); delivery notices (Issues and Stops) are PDFs, and the year-to-date
file covers one year; the history behind both is CME DataMine (paid). CME blocks scripts (403); a real browser can read it. So the CME numbers can only be
RECORDED from today (strategy_analysis/data/cme_snap/) and tested later - this file says so rather than pretend.
THE TEST (per market and signal, primary horizon 4 weeks only; Holm over the 15 cells):
  S1  crowd rank        trailing-3-year percentile of managed-money net / open interest. REGISTERED DIRECTION: contrarian - a crowded SHORT (low rank) is followed by a
                        RISE, a crowded LONG by a fall (IC negative).
  S2  swap-dealer rank  the same for swap dealers' net share. REGISTERED DIRECTION: positive (dealers take the other side of the crowd).
  S3  crowd change      4-week change in managed-money net / open interest. REGISTERED DIRECTION: positive (the crowd is trend-following; it keeps pushing).
  statistic  Spearman IC of the signal with the 20-day forward log return; whole span, tune half (first 60% of weeks) and holdout half; significance by a
             CIRCULAR-SHIFT null (the return series shifted by a random 52+ weeks keeps its overlap and autocorrelation) - 5,000 shifts, one-sided in the
             registered direction; the bucket view (rank <= 0.10 / >= 0.90) = mean forward return, hit rate, n, and the same shift test.
  PASS       whole-span shift p < 0.05 in the registered direction, the same (registered) sign of IC on both halves, and - for S1 / S2 - the holdout's two extreme buckets ordered
             as registered (S1: crowded-short bucket above crowded-long bucket; S2: the reverse).
             A cell that passes is a lead, not a book (rule 9 and the mined-holdout rule): it would still need a forward record.
REGISTERED BEFORE THE FIRST RUN (2026-10-28; nothing but the 2026-10-20 snapshot above has been looked at)
  P1  At most 1 of the 15 cells passes. (Prior: cot_shapiro.py / cot_shapiro_more.py / fx_tff.py on legacy and TFF data found nothing; this is the first time
      on the Disaggregated categories and on platinum / palladium.)
  P2  Palladium: after a crowded-short reading (rank <= 0.10) the next 4 weeks average UP, but not distinguishably from palladium's all-weeks average (p > 0.05).
  P3  Pooled over the five metals the contrarian IC of S1 is within +-0.05 of zero.
  P4  S3 (positioning momentum) has the registered sign in at least 3 of 5 markets, each |IC| < 0.10.
  P5  ETF prices versus front-month futures prices change no verdict.
  P6  The tool's verdict for palladium today (rank, crowded side) is NO LEAN - the crowd is extreme, and extremes have been uninformative.

    python -m backtest.cot_metals            the test (downloads and caches the CFTC reports and the prices)
    python -m backtest.cot_metals --now      only the readout of the latest report with its history (what positioning_lean.py prints)
Writes logs/cot_metals.txt.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "strategy_analysis" / "data" / "cot_metals"
OUT = ROOT / "logs" / "cot_metals.txt"
DS = "kh3c-gbw2"                                   # Disaggregated, futures and options combined (the screenshot's report)
MARKETS = {
    "PL": dict(name="Platinum", code="076651", etf="PPLT", fut="PL=F"),
    "PA": dict(name="Palladium", code="075651", etf="PALL", fut="PA=F"),
    "GC": dict(name="Gold", code="088691", etf="GLD", fut="GC=F"),
    "SI": dict(name="Silver", code="084691", etf="SLV", fut="SI=F"),
    "HG": dict(name="Copper", code="085692", etf="CPER", fut="HG=F"),
}
H = 20                                              # trading days held (4 weeks)
WIN, MIN_N = 156, 104                               # the crowd rank: the last 3 years of weeks, at least 2 to start
COST = 12e-4
SHIFTS = 5000
LINES: list = []


def say(s: str = ""):
    print(s, flush=True)
    LINES.append(s)


# ------------------------------------------------------------------ data

def _get(url: str):
    for k in range(3):
        try:
            return json.load(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=90))
        except Exception:  # noqa: BLE001
            if k == 2:
                raise
            time.sleep(2 + 3 * k)


def cot_frame(code: str, fresh_hours: float = 6.0, ds: str = DS) -> pd.DataFrame:
    DATA.mkdir(parents=True, exist_ok=True)
    p = DATA / (f"cot_{code}.json" if ds == DS else f"cot_{ds}_{code}.json")
    if p.exists() and time.time() - p.stat().st_mtime < fresh_hours * 3600:
        rows = json.loads(p.read_text())
    else:
        q = urllib.parse.urlencode({"$where": f"cftc_contract_market_code='{code}'", "$limit": 5000, "$order": "report_date_as_yyyy_mm_dd"})
        rows = _get(f"https://publicreporting.cftc.gov/resource/{ds}.json?{q}")
        p.write_text(json.dumps(rows))
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["report_date_as_yyyy_mm_dd"].str[:10])
    num = ["open_interest_all", "m_money_positions_long_all", "m_money_positions_short_all", "swap_positions_long_all", "swap__positions_short_all",
           "conc_net_le_4_tdr_long_all", "conc_net_le_4_tdr_short_all", "traders_m_money_long_all", "traders_m_money_short_all"]
    for c in num:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.sort_values("date").drop_duplicates("date").set_index("date")
    oi = df["open_interest_all"].replace(0, np.nan)
    out = pd.DataFrame(index=df.index)
    out["oi"] = oi
    out["mm_long"], out["mm_short"] = df["m_money_positions_long_all"], df["m_money_positions_short_all"]
    out["mm_net"] = (out["mm_long"] - out["mm_short"]) / oi                       # managed money, net, as a share of open interest
    out["sw_net"] = (df["swap_positions_long_all"] - df["swap__positions_short_all"]) / oi
    out["d4"] = out["mm_net"].diff(4)
    out["top4_long"], out["top4_short"] = df["conc_net_le_4_tdr_long_all"], df["conc_net_le_4_tdr_short_all"]
    out["n_mm_short"] = df["traders_m_money_short_all"]
    return out


def prices(sym: str) -> pd.Series:
    DATA.mkdir(parents=True, exist_ok=True)
    p = DATA / f"px_{sym.replace('=', '_')}.json"
    if p.exists() and time.time() - p.stat().st_mtime < 6 * 3600:
        j = json.loads(p.read_text())
    else:
        u = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(sym)}?period1=0&period2={int(time.time())}&interval=1d"
        r = _get(u)["chart"]["result"][0]
        j = dict(ts=r["timestamp"], c=r["indicators"]["adjclose"][0]["adjclose"])
        p.write_text(json.dumps(j))
    s = pd.Series(j["c"], index=pd.to_datetime(j["ts"], unit="s").normalize(), dtype=float).dropna()
    return s[~s.index.duplicated(keep="last")].sort_index()


def causal_rank(x: np.ndarray, win: int = WIN, min_n: int = MIN_N) -> np.ndarray:
    """Today's value's percentile among the last `win` weeks INCLUDING today (nothing after it is read)."""
    out = np.full(len(x), np.nan)
    for i in range(len(x)):
        w = x[max(0, i - win + 1):i + 1]
        w = w[~np.isnan(w)]
        if len(w) >= min_n and not np.isnan(x[i]):
            out[i] = (w <= x[i]).mean()
    return out


def fwd_returns(report_dates, px: pd.Series, h: int = H) -> np.ndarray:
    """Log return from the CLOSE of the first trading day after the Friday release (report date + 3 days) to h trading days later."""
    idx = px.index.values.astype("datetime64[D]")
    v = px.values
    out = np.full(len(report_dates), np.nan)
    for k, d in enumerate(report_dates):
        i = int(np.searchsorted(idx, np.datetime64(d.date()) + np.timedelta64(3, "D"), side="right"))
        if i + h < len(v) and v[i] > 0 and v[i + h] > 0:
            out[k] = np.log(v[i + h] / v[i]) - COST
    return out


def build(code_key: str, source: str = "etf") -> pd.DataFrame:
    m = MARKETS[code_key]
    f = cot_frame(m["code"])
    px = prices(m["etf"] if source == "etf" else m["fut"])
    f["rank_mm"] = causal_rank(f["mm_net"].values)
    f["rank_sw"] = causal_rank(f["sw_net"].values)
    f["fwd"] = fwd_returns(f.index, px)
    return f


# ------------------------------------------------------------------ statistics

def spearman(x: np.ndarray, y: np.ndarray) -> float:
    ok = ~(np.isnan(x) | np.isnan(y))
    if ok.sum() < 30:
        return float("nan")
    return float(np.corrcoef(pd.Series(x[ok]).rank().values, pd.Series(y[ok]).rank().values)[0, 1])


def shift_null(x: np.ndarray, y: np.ndarray, stat, rng: np.random.Generator, n: int = SHIFTS) -> np.ndarray:
    k = len(y)
    vals = np.empty(n)
    for i in range(n):
        s = int(rng.integers(52, max(53, k - 52)))
        vals[i] = stat(x, np.roll(y, s))
    return vals


def p_one_sided(obs: float, null: np.ndarray, sign: int) -> float:
    """sign +1: the registered direction is positive. Fraction of shifted values at least as extreme in that direction."""
    null = null[~np.isnan(null)]
    if np.isnan(obs) or not len(null):
        return float("nan")
    return float(((null >= obs).mean() if sign > 0 else (null <= obs).mean()))


SIGNALS = {"S1": ("rank_mm", -1, "crowd rank (contrarian)"), "S2": ("rank_sw", +1, "swap-dealer rank"), "S3": ("d4", +1, "crowd change (momentum)")}


def bucket_stat(rank: np.ndarray, y: np.ndarray, lo: float, hi: float) -> tuple:
    m = (rank >= lo) & (rank <= hi) & ~np.isnan(y)
    return (float(np.mean(y[m])) if m.any() else float("nan"), float(np.mean(y[m] > 0)) if m.any() else float("nan"), int(m.sum()))


def run_market(key: str, source: str, rng) -> dict:
    f = build(key, source)
    ok = f["fwd"].notna() & f["rank_mm"].notna()
    d = f[ok]
    n = len(d)
    cut = d.index[int(n * 0.6)]
    res = dict(key=key, n=n, first=str(d.index[0].date()), last=str(d.index[-1].date()), cells={})
    y_all = f["fwd"].values
    for sk, (col, sign, _lab) in SIGNALS.items():
        x_all = f[col].values
        valid = ~np.isnan(x_all)
        tune = (f.index < cut) & valid
        hold = (f.index >= cut) & valid
        ic, ic_t, ic_h = spearman(x_all, y_all), spearman(np.where(tune, x_all, np.nan), y_all), spearman(np.where(hold, x_all, np.nan), y_all)
        null = shift_null(x_all, y_all, spearman, rng)
        cell = dict(ic=ic, ic_tune=ic_t, ic_hold=ic_h, p=p_one_sided(ic, null, sign), sign=sign)
        if sk in ("S1", "S2"):                                         # the extreme buckets: the side the registered direction says goes UP / DOWN
            lo_b, hi_b = bucket_stat(x_all, y_all, 0.0, 0.10), bucket_stat(x_all, y_all, 0.90, 1.0)
            cell.update(low=lo_b, high=hi_b)
            xh = np.where(hold, x_all, np.nan)
            cell["low_hold"], cell["high_hold"] = bucket_stat(xh, y_all, 0.0, 0.10), bucket_stat(xh, y_all, 0.90, 1.0)
            nl = shift_null(x_all, y_all, lambda a, b: bucket_stat(a, b, 0.0, 0.10)[0], rng, 2000)
            nh = shift_null(x_all, y_all, lambda a, b: bucket_stat(a, b, 0.90, 1.0)[0], rng, 2000)
            cell["p_low_up"], cell["p_high_down"] = p_one_sided(lo_b[0], nl, +1), p_one_sided(hi_b[0], nh, -1)
            cell["base"] = float(np.nanmean(y_all))
        res["cells"][sk] = cell
    res["frame"] = f
    return res


def passes(sk: str, c: dict) -> bool:
    if not (c["p"] < 0.05 and np.sign(c["ic_tune"]) == np.sign(c["ic_hold"]) == c["sign"]):
        return False
    if sk == "S3":
        return True
    if sk == "S1":                                                     # contrarian: the crowded-short bucket must beat the crowded-long bucket in the holdout
        return bool(c["low_hold"][0] > c["high_hold"][0])
    return bool(c["high_hold"][0] > c["low_hold"][0])                  # S2: the dealers-long bucket must beat the dealers-short bucket


# ------------------------------------------------------------------ the readout

def bucket_table(f: pd.DataFrame, col: str) -> list:
    rows, x, y = [], f[col].values, f["fwd"].values
    cut = f.index[int(len(f) * 0.6)]
    for lab, lo, hi in (("<= 10th", 0, 0.10), ("10-25", 0.10, 0.25), ("25-75", 0.25, 0.75), ("75-90", 0.75, 0.90), (">= 90th", 0.90, 1.0)):
        m, h, n = bucket_stat(x, y, lo, hi)
        mt = bucket_stat(np.where(f.index < cut, x, np.nan), y, lo, hi)
        mh = bucket_stat(np.where(f.index >= cut, x, np.nan), y, lo, hi)
        rows.append((lab, n, m, h, mt[0], mh[0]))
    return rows


def readout(source: str = "etf", out=print) -> list:
    """The latest report, per market: which side is crowded, how extreme, and what followed the same reading in the past (with its two halves)."""
    res = []
    for key, m in MARKETS.items():
        f = build(key, source)
        last = f.iloc[-1]
        d = f.index[-1]
        known = f.dropna(subset=["fwd", "rank_mm"])
        side = "SHORT" if last["mm_net"] < 0 else "LONG"
        crowd = abs(last["mm_net"]) * 100
        out(f"{m['name'].upper():<10} report {d.date()}  managed money net {last['mm_net'] * 100:+.0f}% of open interest ({side} side), 3-year rank {last['rank_mm'] * 100:.0f}th, "
            f"4-week change {last['d4'] * 100:+.1f} points; swap dealers net {last['sw_net'] * 100:+.0f}%; {int(last['n_mm_short'])} MM traders short, top-4 hold {last['top4_short']:.0f}% of OI short")
        tab = bucket_table(known, "rank_mm")
        cur = "<= 10th" if last["rank_mm"] <= 0.10 else ">= 90th" if last["rank_mm"] >= 0.90 else "10-25" if last["rank_mm"] <= 0.25 else "75-90" if last["rank_mm"] >= 0.75 else "25-75"
        for lab, n, mean, hit, mt, mh in tab:
            mark = "  <-- today" if lab == cur else ""
            out(f"    rank {lab:>8}: {n:4d} weeks, next 4 weeks avg {mean * 100:+5.2f}% (up {hit * 100:3.0f}%)  tune {mt * 100:+5.2f}%  holdout {mh * 100:+5.2f}%{mark}")
        res.append(dict(key=key, date=str(d.date()), mm_net=float(last["mm_net"]), rank=float(last["rank_mm"]), side=side, crowd=float(crowd), bucket=cur, table=tab))
    return res


def main():
    now_only = "--now" in sys.argv
    say(f"CFTC DISAGGREGATED POSITIONS x PRICES - metals - {time.strftime('%Y-%m-%d %H:%M', time.gmtime())} UTC")
    if now_only:
        readout(out=say)
        return
    rng = np.random.default_rng(20261028)
    allres = {}
    for source in ("etf", "fut"):
        say(f"\n=== PRICES: {'physical-metal ETFs (PPLT PALL GLD SLV CPER)' if source == 'etf' else 'front-month futures (PL=F PA=F GC=F SI=F HG=F), roll gaps included'} ===")
        say("market      weeks  span                        S1 crowd rank (contrarian)             S2 swap rank (+)        S3 crowd change (+)")
        say("                                               IC all / tune / hold    p      lowest10% / highest10%       IC all / tune / hold   p    IC all / tune / hold   p")
        npass = 0
        for key in MARKETS:
            r = run_market(key, source, rng)
            allres[(source, key)] = r
            c1, c2, c3 = r["cells"]["S1"], r["cells"]["S2"], r["cells"]["S3"]
            ps = [passes(sk, r["cells"][sk]) for sk in ("S1", "S2", "S3")]
            npass += sum(ps)
            say(f"{MARKETS[key]['name']:<10} {r['n']:5d}  {r['first']}..{r['last']}   {c1['ic']:+.3f} {c1['ic_tune']:+.3f} {c1['ic_hold']:+.3f}  p {c1['p']:.3f}   "
                f"{c1['low'][0] * 100:+5.1f}% (n{c1['low'][2]:3d}) / {c1['high'][0] * 100:+5.1f}% (n{c1['high'][2]:3d})   "
                f"{c2['ic']:+.3f} {c2['ic_tune']:+.3f} {c2['ic_hold']:+.3f} p {c2['p']:.3f}   {c3['ic']:+.3f} {c3['ic_tune']:+.3f} {c3['ic_hold']:+.3f} p {c3['p']:.3f}   "
                f"{'PASS: ' + ','.join(sk for sk, ok in zip(('S1', 'S2', 'S3'), ps) if ok) if any(ps) else 'no cell passes'}")
        say(f"  cells passing the registered rule: {npass} of 15")
        # Holm over the 15 cells on the whole-span p
        ps_all = sorted((allres[(source, k)]["cells"][sk]["p"], k, sk) for k in MARKETS for sk in ("S1", "S2", "S3"))
        holm = [(p, k, sk, p * (15 - i)) for i, (p, k, sk) in enumerate(ps_all)]
        say("  smallest p-values (Holm-adjusted): " + ", ".join(f"{k}/{sk} p {p:.3f} (adj {min(1.0, a):.2f})" for p, k, sk, a in holm[:4]))
        pooled = np.nanmean([allres[(source, k)]["cells"]["S1"]["ic"] for k in MARKETS])
        say(f"  P3 pooled contrarian IC of S1 over the five markets: {pooled:+.3f}")
        s3 = [allres[(source, k)]["cells"]["S3"]["ic"] for k in MARKETS]
        say(f"  P4 S3 momentum IC by market: " + " ".join(f"{MARKETS[k]['name'][:3]} {v:+.3f}" for k, v in zip(MARKETS, s3)) + f"  -> positive in {sum(v > 0 for v in s3)} of 5")
        pa = allres[(source, 'PA')]["cells"]["S1"]
        say(f"  P2 palladium: crowded-short bucket (rank <= 10th) next 4 weeks avg {pa['low'][0] * 100:+.2f}% (n {pa['low'][2]}, up {pa['low'][1] * 100:.0f}%) vs all weeks {pa['base'] * 100:+.2f}%; "
            f"one-sided p of 'goes up more than chance' {pa['p_low_up']:.3f}; crowded-long bucket {pa['high'][0] * 100:+.2f}% (n {pa['high'][2]}), p of 'falls more' {pa['p_high_down']:.3f}")
    verdicts = {}
    for key in MARKETS:
        c = allres[("etf", key)]["cells"]
        s1, s2, s3 = (passes("S1", c["S1"]), passes("S2", c["S2"]), passes("S3", c["S3"]))
        why = f"S1 crowd rank IC {c['S1']['ic']:+.3f} (tune {c['S1']['ic_tune']:+.3f}, holdout {c['S1']['ic_hold']:+.3f}), shift p {c['S1']['p']:.2f}"
        if s1:
            text = "LEAN (contrarian): a crowded short has been followed by a rise and a crowded long by a fall - " + why
        elif s3:
            text = "WEAK LEAN (momentum): the crowd's 4-week change has continued - " + why
        else:
            text = "NO LEAN: the registered signals did not pass - " + why
        verdicts[key] = dict(verdict=text, S1=s1, S2=s2, S3=s3, ic=c["S1"]["ic"], p=c["S1"]["p"])
    (ROOT / "logs" / "cot_metals.json").write_text(json.dumps(verdicts, indent=1))
    say("\n=== THE TOOL'S READOUT TODAY (ETF prices) ===")
    res = readout("etf", say)
    pa = [r for r in res if r["key"] == "PA"][0]
    say(f"\nP6 palladium today: rank {pa['rank'] * 100:.0f}th, {pa['side']} side crowded at {pa['crowd']:.0f}% of open interest, bucket {pa['bucket']}.")
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text("\n".join(LINES) + "\n", encoding="utf-8")
    say(f"wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
