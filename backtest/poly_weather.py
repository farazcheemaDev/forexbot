"""POLYMARKET DAILY-TEMPERATURE MARKETS vs FREE WEATHER FORECASTS - is there a mispricing to trade? (2026-10-10)

THE USER (2026-10-10) sent a reel of a "Grok agent" that turned $50 into "thousands" on Polymarket and, on its own
dashboard, nearly died at $11 before a "PIVOT -> WEATHER / NOAA". The claim worth testing is that one: Polymarket's
"Highest temperature in <city> on <date>?" markets (11 temperature buckets a day, ~14+ cities) are priced by casual
bettors and can be beaten by a free forecast. Tested on markets that have ALREADY RESOLVED - the winning bucket is the
truth, so nothing depends on the reel.

DATA (all public, no keys)
    Polymarket Gamma    every closed event tagged daily-temperature: city, date, the buckets, the winning bucket, the
                        resolution station (Wunderground, an airport, whole degrees)
    Polymarket CLOB     each bucket's YES price history; the price at the decision time T is the last point at or before T
    Open-Meteo          the "previous runs" archive: the temperature forecast as it stood ~1 day (previous_day1) and ~2
                        days (previous_day2) before each hour, at the station's coordinates, in its local time
DECISION TIMES (no look-ahead: every forecast hour used was issued before T)
    H0  local midnight at the START of the target day  - forecast: previous_day1 (runs from the day before)
    H1  local noon the DAY BEFORE                       - forecast: previous_day2 (runs from two days before)
MODEL  the station's daily max ~ Normal(forecast max + city bias, city spread); bias and spread fitted on that city's
       EARLIER resolved days only (walk-forward, >= 10 days of history), the truth being the winning bucket's middle
       (open-ended buckets are left out of the fit). Bucket probability = the Normal's mass over [lo - 0.5, hi + 0.5).
TESTS  on the LATER half of the dates (the earlier half only trains the model):
    calibration     of the market's own prices (normalised to sum to 1 across buckets), by price band
    skill           log loss and Brier of market vs model vs a 50/50 blend, per event
    trading         buy YES at price + 1c (slippage; NO trading fee assumed - if these markets charge one, it subtracts)
                    wherever the model is >= 8 points above the price (the reel's threshold) and >= 3 points (looser);
                    return per $1 staked

REGISTERED BEFORE ANY PRICE OR FORECAST WAS PULLED (2026-10-10, after seeing only event counts and one event's layout)
    W1  The market is close to calibrated: every price band's resolved-YES rate within 2 se of its average price, with at
        most a mild longshot bias (buckets under 10c resolve YES less often than priced).
    W2  The free forecast does NOT beat the market: on the later half the market's log loss is <= the model's at both
        decision times (bettors and bots read the same forecasts).
    W3  Buying where the model is >= 8 points above the price does not make money on the later half after 1c slippage:
        mean return per $1 within 2 se of zero, or negative.
The 22 cities (STATIONS below) were chosen for coverage across continents before any price was seen.

RESULT (2026-10-09 22:14 UTC, logs/poly_weather.txt; 4,782 resolved days, 4,488 scored 2026-02-26 .. 2026-10-09, 51,848
bucket price histories; later half from 2026-06-27)
    W2 RIGHT, by a wide margin: the market beats the free forecast in EVERY one of the 22 cities, at both decision times, on
       both halves. Later half, log loss of the winning bucket: market 1.269 / model 1.710 / 50-50 blend 1.390 at H0
       (market - model -0.441, se 0.019); 1.352 / 1.847 at H1. Blending in the model makes the market WORSE.
       PIPELINE CHECK (look-ahead, not tradable): fed the SAME-DAY forecast (f0), the model beats the market, 1.152 vs
       1.269 - so the code is sound; the day-old free forecast simply knows less than the traders.
    W1 RIGHT: close to calibrated, with a mild longshot bias - buckets priced 2-20c resolve YES 0.8-1.7 points less than
       priced (beyond 2 se), favourites at 50-65c +3.4 points (inside 2 se).
    W3 RIGHT: buying where the model is >= 8 points above the price LOSES -35% (H0) / -46% (H1) per $1 on the later half
       (5% / 4% hit rate on ~6c buckets): the "mispricings" a free forecast finds are the forecast's own errors.
    The longshot bias as a trade (sell = buy NO), band picked on the earlier half, read on the later: +0.2% (H0, 5-10c) /
       +1.2% (H1, 10-20c) per $1 at 1c slippage (se 0.6 / 0.9), -0.8% / 0.0% at 2c, worst day -26% / -24%; on the earlier
       half every band was within noise of zero. The edge is the size of the spread - a market maker's, not a taker's.
    Reading: the reel's "pivot to weather" is not supported by these markets - they are efficient against a free
    forecast. The one route left untested is a STATION-SPECIFIC forecast (NOAA's National Blend of Models / MOS, archived
    for US airports by the Iowa Environmental Mesonet) - the thing the market's best traders are likely already using.

    python -m backtest.poly_weather            (first run downloads and caches ~48k price histories; later runs offline)
"""
from __future__ import annotations

import json
import math
import re
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "strategy_analysis" / "data" / "poly_weather"
LOG = ROOT / "logs" / "poly_weather.txt"
GAMMA, CLOB = "https://gamma-api.polymarket.com", "https://clob.polymarket.com"
OM = "https://previous-runs-api.open-meteo.com/v1/forecast"

# station (the Wunderground code in each event's rules) -> latitude, longitude, timezone
STATIONS = {
    "NYC": ("KLGA", 40.7769, -73.8740, "America/New_York"), "London": ("EGLC", 51.5048, 0.0495, "Europe/London"),
    "Chicago": ("KORD", 41.9786, -87.9048, "America/Chicago"), "Dallas": ("KDAL", 32.8471, -96.8518, "America/Chicago"),
    "Atlanta": ("KATL", 33.6407, -84.4277, "America/New_York"), "Miami": ("KMIA", 25.7959, -80.2870, "America/New_York"),
    "Seattle": ("KSEA", 47.4502, -122.3088, "America/Los_Angeles"), "Toronto": ("CYYZ", 43.6777, -79.6248, "America/Toronto"),
    "Los Angeles": ("KLAX", 33.9416, -118.4085, "America/Los_Angeles"),
    "Denver": ("KBKF", 39.7017, -104.7517, "America/Denver"), "Houston": ("KHOU", 29.6454, -95.2789, "America/Chicago"),
    "Austin": ("KAUS", 30.1975, -97.6664, "America/Chicago"),
    "San Francisco": ("KSFO", 37.6213, -122.3790, "America/Los_Angeles"),
    "Buenos Aires": ("SAEZ", -34.8222, -58.5358, "America/Argentina/Buenos_Aires"),
    "Sao Paulo": ("SBGR", -23.4356, -46.4731, "America/Sao_Paulo"),
    "Wellington": ("NZWN", -41.3272, 174.8053, "Pacific/Auckland"), "Seoul": ("RKSI", 37.4602, 126.4407, "Asia/Seoul"),
    "Tokyo": ("RJTT", 35.5494, 139.7798, "Asia/Tokyo"), "Munich": ("EDDM", 48.3538, 11.7861, "Europe/Berlin"),
    "Madrid": ("LEMD", 40.4983, -3.5676, "Europe/Madrid"), "Singapore": ("WSSS", 1.3644, 103.9915, "Asia/Singapore"),
    "Shanghai": ("ZSPD", 31.1443, 121.8083, "Asia/Shanghai"),
}
MONTHS = {m: i for i, m in enumerate(["January", "February", "March", "April", "May", "June", "July", "August",
                                      "September", "October", "November", "December"], 1)}
BANDS = [0, 0.02, 0.05, 0.10, 0.20, 0.35, 0.50, 0.65, 0.80, 0.95, 1.0001]


def get(url: str, tries: int = 4):
    for k in range(tries):
        try:
            rq = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
            with urllib.request.urlopen(rq, timeout=40) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if e.code in (400, 404, 422) or k == tries - 1:
                raise
        except Exception:
            if k == tries - 1:
                raise
        time.sleep(1.5 * (k + 1))


# ---------------------------------------------------------------- data

def events() -> list:
    """Every closed daily-temperature event (keyset pagination; offset paging stops at 2,100), cached."""
    f = CACHE / "events.json"
    if f.exists():
        return json.loads(f.read_text())
    CACHE.mkdir(parents=True, exist_ok=True)
    out, cur = [], None
    while True:
        url = f"{GAMMA}/events/keyset?tag_slug=daily-temperature&closed=true&limit=100" + (f"&after_cursor={cur}" if cur else "")
        r = get(url)
        out += r.get("events") or []
        cur = r.get("next_cursor")
        if not cur or not r.get("events"):
            break
        time.sleep(0.1)
    f.write_text(json.dumps(out))
    return out


def bucket(title: str):
    """'28-29°F' -> (28, 29); '13°C' -> (13, 13); '8°C or below' -> (-inf, 8); '38°F or higher' -> (38, inf); '-3°C'."""
    t = (title or "").replace("°", " ").replace("�", " ").strip()
    m = re.match(r"^(-?\d+)(?:-(-?\d+))?\s*[FC]?\s*(or below|or higher)?\s*$", t, flags=re.I)
    if not m:
        return None
    a = int(m.group(1))
    b = int(m.group(2)) if m.group(2) else a
    if m.group(3) and m.group(3).lower() == "or below":
        return (-np.inf, b)
    if m.group(3) and m.group(3).lower() == "or higher":
        return (a, np.inf)
    return (a, b)


def table() -> pd.DataFrame:
    """One row per (event, bucket) for the tested cities' daily HIGHS: city, date, unit, lo, hi, YES token, won."""
    rows = []
    for e in events():
        m = re.match(r"Highest temperature in (.+) on (\w+) (\d+)\?", e.get("title") or "")
        if not m or m.group(1) not in STATIONS or m.group(2) not in MONTHS:
            continue
        end = pd.Timestamp(e["endDate"])
        mon, day = MONTHS[m.group(2)], int(m.group(3))
        year = end.year - 1 if (mon == 12 and end.month == 1) else end.year
        date = pd.Timestamp(year=year, month=mon, day=day)
        mk = e.get("markets") or []
        start = pd.Timestamp(e.get("startDate") or e.get("creationDate") or pd.NaT)
        if pd.isna(start):                                      # some events carry neither: markets open ~2 days early
            start = pd.Timestamp(date).tz_localize("UTC") - pd.Timedelta(days=3)
        recs = []
        for x in mk:
            b = bucket(x.get("groupItemTitle"))
            try:
                fin = json.loads(x.get("outcomePrices") or "[]")
                tok = json.loads(x.get("clobTokenIds") or "[]")[0]
            except Exception:
                b = None
            if b is None or not fin:
                break
            g = (x.get("groupItemTitle") or "").upper()
            recs.append(dict(event=e["id"], city=m.group(1), date=date, unit="F" if "F" in g else "C", lo=b[0], hi=b[1],
                             token=tok, won=int(float(fin[0]) == 1.0), start=start, end=end,
                             volume=float(x.get("volume") or 0)))
        if len(recs) != len(mk) or sum(r["won"] for r in recs) != 1:
            continue                                            # an unparsed bucket, or no single winner: skip the day
        rows += recs
    return pd.DataFrame(rows)


def prices(T: pd.DataFrame) -> dict:
    """Hourly YES price history per token over its event's life, cached in a JSON-lines file (resumable)."""
    f = CACHE / "prices.jsonl"
    have = {}
    if f.exists():
        for ln in f.read_text().splitlines():
            r = json.loads(ln)
            have[r["token"]] = r["h"]
    span = T.drop_duplicates("token").set_index("token")[["start", "end"]]
    todo = [t for t in span.index if t not in have]
    print(f"prices: {len(have)} cached, {len(todo)} to fetch", flush=True)

    def one(tok):
        try:
            s = int(span.at[tok, "start"].timestamp()) - 3600
            e = int(span.at[tok, "end"].timestamp()) + 86400
            h = get(f"{CLOB}/prices-history?market={tok}&startTs={s}&endTs={e}&fidelity=60").get("history", [])
            return tok, [[int(x["t"]), float(x["p"])] for x in h]
        except Exception:
            return tok, None
    if todo:
        with open(f, "a") as out, ThreadPoolExecutor(12) as pool:
            for i, (tok, h) in enumerate(pool.map(one, todo)):
                if h is not None:
                    out.write(json.dumps({"token": tok, "h": h}) + "\n")
                    have[tok] = h
                if (i + 1) % 2000 == 0:
                    out.flush()
                    print(f"  {i + 1}/{len(todo)} fetched", flush=True)
    return have


def forecasts(city: str, d0: pd.Timestamp, d1: pd.Timestamp, unit: str) -> pd.DataFrame:
    """Daily max of the hourly forecast as it stood 1 and 2 days before each hour, at the station, on local days."""
    f = CACHE / f"om_{city.replace(' ', '_')}.parquet"
    if f.exists():
        return pd.read_parquet(f)
    _, lat, lon, tz = STATIONS[city]
    parts, a = [], d0 - pd.Timedelta(days=1)
    while a <= d1:
        b = min(a + pd.Timedelta(days=90), d1 + pd.Timedelta(days=1))
        r = get(f"{OM}?latitude={lat}&longitude={lon}&hourly=temperature_2m,temperature_2m_previous_day1,"
                f"temperature_2m_previous_day2&start_date={a:%Y-%m-%d}&end_date={b:%Y-%m-%d}"
                f"&timezone={tz.replace('/', '%2F')}" + ("&temperature_unit=fahrenheit" if unit == "F" else ""))
        parts.append(pd.DataFrame(r["hourly"]))
        a = b + pd.Timedelta(days=1)
        time.sleep(0.3)
    h = pd.concat(parts)
    h["date"] = pd.to_datetime(h.time.str[:10])
    d = h.groupby("date").agg(f0=("temperature_2m", "max"), f1=("temperature_2m_previous_day1", "max"),
                              f2=("temperature_2m_previous_day2", "max"), n1=("temperature_2m_previous_day1", "count"),
                              n2=("temperature_2m_previous_day2", "count")).reset_index()
    d.to_parquet(f, index=False)
    return d


# ---------------------------------------------------------------- the test

def norm_cdf(x):
    return 0.5 * (1 + np.vectorize(math.erf)(np.asarray(x, float) / math.sqrt(2)))


def price_at(h: list, t_s: int) -> float:
    """The last hourly price at or before t_s (seconds); NaN if none."""
    if not h:
        return np.nan
    ts = np.fromiter((x[0] for x in h), np.int64)
    i = np.searchsorted(ts, t_s, "right") - 1
    return float(h[i][1]) if i >= 0 else np.nan


def build(T: pd.DataFrame, P: dict, fcols: dict | None = None) -> pd.DataFrame:
    """Per (event, bucket, horizon): market price, model probability, outcome. fcols overrides which forecast each
    horizon uses - only for the pipeline check (f0 = the same-day forecast, i.e. LOOK-AHEAD)."""
    fcols = fcols or {"H0": ("f1", "n1"), "H1": ("f2", "n2")}
    out = []
    for city, C in T.groupby("city"):
        tz, unit = STATIONS[city][3], C.unit.iloc[0]
        F = forecasts(city, C.date.min(), C.date.max(), unit).set_index("date")
        days = C.drop_duplicates("event").sort_values("date", kind="stable")
        hist = {"H0": [], "H1": []}                         # (date, residual) of earlier days, per horizon
        for _, ev in days.iterrows():
            rows = C[C.event == ev.event].sort_values("lo", kind="stable")
            win = rows[rows.won == 1].iloc[0]
            local0 = pd.Timestamp(ev.date).tz_localize(tz)
            for hz, t_loc in (("H0", local0), ("H1", local0 - pd.Timedelta(hours=12))):
                if hz not in fcols:
                    continue
                fcol, ncol = fcols[hz]
                t_s = int(t_loc.tz_convert("UTC").timestamp())
                fc = F[fcol].get(ev.date, np.nan) if ev.date in F.index and F[ncol].get(ev.date, 0) >= 20 else np.nan
                prior = [r for d, r in hist[hz] if d < ev.date][-60:]
                p = np.array([price_at(P.get(tok), t_s) for tok in rows.token])
                if np.isfinite(fc) and len(prior) >= 10 and t_s > int(ev.start.timestamp()) and np.isfinite(p).sum() >= len(p) - 1:
                    bias = float(np.mean(prior))
                    sd = max(float(np.std(prior, ddof=1)), 0.6 if unit == "C" else 1.0)
                    mu = fc + bias
                    lo = np.where(np.isfinite(rows.lo), rows.lo - 0.5, -np.inf)
                    hi = np.where(np.isfinite(rows.hi), rows.hi + 0.5, np.inf)
                    pm = norm_cdf((hi - mu) / sd) - norm_cdf((lo - mu) / sd)
                    pp = np.where(np.isfinite(p), p, 0.0)
                    q = pp / pp.sum() if pp.sum() > 0 else np.full(len(pp), np.nan)
                    for k, (_, r) in enumerate(rows.iterrows()):
                        out.append(dict(event=ev.event, city=city, date=ev.date, hz=hz, lo=r.lo, hi=r.hi, won=r.won,
                                        price=p[k], q=q[k], model=pm[k], fc=fc, mu=mu, sd=sd, volume=r.volume))
                if np.isfinite(fc) and np.isfinite(win.lo) and np.isfinite(win.hi):
                    hist[hz].append((ev.date, (win.lo + win.hi) / 2 - fc))
    return pd.DataFrame(out)


def scores(B: pd.DataFrame, lines: list, label: str):
    for hz, G in B.groupby("hz"):
        ev = G.groupby("event")
        def ll(col):
            w = G[G.won == 1].set_index("event")[col].clip(1e-3, 1)
            return -np.log(w)
        mk, md = ll("q"), ll("model")
        bl = -np.log((0.5 * G[G.won == 1].set_index("event").q + 0.5 * G[G.won == 1].set_index("event").model).clip(1e-3, 1))
        d = (mk - md).dropna()
        bri = ev.apply(lambda g: pd.Series({"mkt": ((g.q - g.won) ** 2).sum(), "mod": ((g.model - g.won) ** 2).sum()}))
        lines.append(f"  {label} {hz}: {len(mk)} days | log loss market {mk.mean():.3f}, model {md.mean():.3f}, blend {bl.mean():.3f} "
                     f"| market - model {d.mean():+.3f} (se {d.std(ddof=1) / np.sqrt(len(d)):.3f}; > 0 = model better) "
                     f"| Brier market {bri.mkt.mean():.3f}, model {bri['mod'].mean():.3f} | winner priced >= 50c: "
                     f"{(G[G.won == 1].price >= 0.5).mean() * 100:.0f}%")


def calibration(B: pd.DataFrame, lines: list, hz: str):
    G = B[(B.hz == hz) & B.price.notna()]
    lines.append(f"  {hz}: band | buckets | avg price | resolved YES | gap (se)")
    for a, b in zip(BANDS[:-1], BANDS[1:]):
        g = G[(G.price >= a) & (G.price < b)]
        if len(g) < 30:
            continue
        r = g.won.mean()
        se = np.sqrt(max(r * (1 - r), 1e-4) / len(g))
        lines.append(f"    {a:.2f}-{min(b, 1):.2f} {len(g):6} | {g.price.mean():.3f} | {r:.3f} | {r - g.price.mean():+.3f} ({se:.3f})"
                     + ("  *" if abs(r - g.price.mean()) > 2 * se else ""))


def trades(B: pd.DataFrame, lines: list, label: str):
    for hz, G in B.groupby("hz"):
        G = G[G.price.notna()]
        for thr in (0.03, 0.08, 0.15):
            for side in ("YES", "NO"):
                if side == "YES":
                    s = G[G.model - G.price >= thr]
                    cost = (s.price + 0.01).clip(upper=0.99)
                    ret = s.won / cost - 1
                else:
                    s = G[G.price - G.model >= thr]
                    cost = (1 - s.price + 0.01).clip(upper=0.99)
                    ret = (1 - s.won) / cost - 1
                if len(ret) < 10:
                    continue
                daily = ret.groupby(s.event).mean()
                lines.append(f"  {label} {hz} {side:3} edge >= {thr:.2f}: {len(ret):5} bets on {s.event.nunique():4} days, "
                             f"hit {((s.won == 1) if side == 'YES' else (s.won == 0)).mean() * 100:3.0f}%, avg price "
                             f"{(s.price if side == 'YES' else 1 - s.price).mean():.2f} | return per $1 {ret.mean() * 100:+6.1f}% "
                             f"(se by day {daily.std(ddof=1) / np.sqrt(len(daily)) * 100:4.1f}) | days up "
                             f"{(daily > 0).mean() * 100:3.0f}%")


def main():
    T = table()
    print(f"{len(T)} bucket rows, {T.event.nunique()} days, {T.city.nunique()} cities", flush=True)
    P = prices(T)
    B = build(T, P)
    B.to_parquet(CACHE / "scored.parquet", index=False)
    cut = B.date.sort_values().iloc[len(B) // 2]
    lines = [f"backtest/poly_weather.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; {T.event.nunique()} resolved days in "
             f"{T.city.nunique()} cities, {B.event.nunique()} scored ({B.date.min():%Y-%m-%d} .. {B.date.max():%Y-%m-%d}); "
             f"later half from {cut:%Y-%m-%d}; prices hourly (Polymarket CLOB), forecasts Open-Meteo previous runs", ""]
    late, early = B[B.date >= cut], B[B.date < cut]
    lines.append("SKILL (log loss of the winning bucket per day; lower is better)")
    scores(early, lines, "earlier half")
    scores(late, lines, "LATER half  ")
    lines.append("")
    lines.append("CALIBRATION of the market's raw prices (LATER half)")
    for hz in ("H0", "H1"):
        calibration(late, lines, hz)
    lines.append("")
    lines.append("TRADING (buy at price + 1c, no fee assumed; return per $1 staked)")
    trades(early, lines, "earlier half")
    trades(late, lines, "LATER half  ")
    lines.append("")
    lines.append("BY CITY, LATER half, H0: log loss market - model (> 0 = model better)")
    for city, G in late[late.hz == "H0"].groupby("city"):
        w = G[G.won == 1]
        d = (-np.log(w.q.clip(1e-3, 1)) + np.log(w.model.clip(1e-3, 1)))
        lines.append(f"  {city:14} {len(w):4} days  {d.mean():+.3f} (se {d.std(ddof=1) / np.sqrt(len(d)):.3f}), forecast sd {G.sd.median():.2f}")
    txt = "\n".join(lines)
    print(txt)
    LOG.write_text(txt + "\n", encoding="utf-8")


if __name__ == "__main__":
    if "--events" in sys.argv:
        print(len(events()), "events")
    else:
        main()
