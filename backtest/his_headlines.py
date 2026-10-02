"""DOES HE TRADE LIVE HEADLINES? - Benzinga's wire (Alpaca News API) around his clicks.

WHY (his_strategy.md s36-s37)
    At his click he knows which way the next 1-5 minutes go (s36). It is not in price, the futures tape (s37), the
    scheduled calendar, Fed speakers or Trump's posts (s28-s29). One recordable candidate is left besides the book: an
    UNSCHEDULED headline - news that breaks with no calendar slot. Alpaca's free News API serves Benzinga's wire back
    to 2015 with publication timestamps, ~130 stories a day.

    Its limit, stated before the test: Benzinga is a news WIRE, mostly company stories. A scalper on live news more
    likely watches a SQUAWK (one-line macro headlines on terminals, or X accounts reposting them in seconds), whose
    archives are paid. A null here rules out the wire, not every feed. A positive result would be decisive.

DATA
    GET data.alpaca.markets/v1beta1/news, every story (no symbol filter) from 70 min before his first entry to 25 min
    after his last, on each day he traded NASDAQ. Keys from APCA_API_KEY_ID / APCA_API_SECRET_KEY (environment, or the
    user-scope store if the shell predates them) - never printed, passed or logged. Headlines are cached under
    strategy_analysis/data/ (git-ignored: Benzinga's text is licensed); only counts and rates are committed.

AT EACH MOMENT T (his entries, and the same-sitting moments: whole-minute offsets within 20 min, same second)
    n_w     stories published in (T - w, T], w = 1 / 3 / 5 / 10 min
    macro_w the same, counting only stories whose headline matches a market-wide word list (Fed, rates, CPI, jobs,
            tariff, Trump, China, yields, recession, ...), or tagged QQQ / SPY / the eight mega-caps

TESTS
    1. TIMING  - more stories just before his click than before the sitting's other moments? (rank vs 0.50, Holm)
    2. DIRECTION - the market-wide stories in the 10 min before each entry, written out WITHOUT his side, to be labelled
       bullish / bearish for NASDAQ blind, then joined to his side. (--label-file; second step)

REGISTERED PREDICTIONS (2026-10-02, before any headline is fetched)
    1. Every n_w and macro_w ranks 0.45-0.55 at his moments; nothing survives Holm. The wire is not his trigger.
    2. Blind-labelled direction agrees with his side 40-60% of the time.

    python -m backtest.his_headlines            fetch, then test 1, and write the blind label sheet
"""
from __future__ import annotations

import json
import os
import pickle
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.his_tape import entries  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "strategy_analysis" / "data" / "benzinga_his_days.pkl"
SHEET = ROOT / "strategy_analysis" / "data" / "his_headlines_blind.csv"
URL = "https://data.alpaca.markets/v1beta1/news"
W = (60, 180, 300, 600)
MACRO = re.compile(r"\b(fed|fomc|powell|rate|rates|yield|yields|treasur|cpi|ppi|inflation|jobs|payroll|unemploy|"
                   r"gdp|recession|tariff|trump|china|beijing|white house|sanction|war|iran|israel|russia|ukraine|"
                   r"opec|oil|nasdaq|s&p|dow|stocks|futures|market|selloff|rally|crash|default|debt ceiling|"
                   r"shutdown|bessent|treasury)\b", re.I)
BIG = {"QQQ", "SPY", "NVDA", "MSFT", "AAPL", "AMZN", "GOOGL", "GOOG", "META", "AVGO", "TSLA"}


def creds():
    names = ("APCA_API_KEY_ID", "APCA_API_SECRET_KEY")
    if sys.platform == "win32" and not all(os.environ.get(n) for n in names):
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
                for n in names:
                    if not os.environ.get(n):
                        os.environ[n] = winreg.QueryValueEx(k, n)[0]
        except OSError:
            pass
    if not all(os.environ.get(n) for n in names):
        sys.exit("APCA_API_KEY_ID / APCA_API_SECRET_KEY are not set in the user environment.")
    return {"APCA-API-KEY-ID": os.environ[names[0]], "APCA-API-SECRET-KEY": os.environ[names[1]]}


def fetch_window(h, a: pd.Timestamp, b: pd.Timestamp) -> list:
    out, token = [], None
    while True:
        q = {"start": a.strftime("%Y-%m-%dT%H:%M:%SZ"), "end": b.strftime("%Y-%m-%dT%H:%M:%SZ"),
             "limit": 50, "sort": "asc", "include_content": "false"}
        if token:
            q["page_token"] = token
        req = urllib.request.Request(URL + "?" + urllib.parse.urlencode(q), headers=h)
        with urllib.request.urlopen(req, timeout=30) as r:
            js = json.loads(r.read())
        for n in js.get("news", []):
            out.append(dict(t=pd.Timestamp(n["created_at"]).tz_convert("UTC").tz_localize(None),
                            headline=n.get("headline", ""), symbols=tuple(n.get("symbols") or ())))
        token = js.get("next_page_token")
        if not token:
            return out
        time.sleep(0.35)                                   # 200 calls a minute on the free plan


def main():
    from scipy.stats import wilcoxon
    x = entries()
    h = creds()
    C = pickle.loads(CACHE.read_bytes()) if CACHE.exists() else {}
    for d, g in x.groupby(x.utc.dt.normalize()):
        key = str(d.date())
        if key in C:
            continue
        a, b = g.utc.min() - pd.Timedelta(minutes=70), g.utc.max() + pd.Timedelta(minutes=25)
        C[key] = fetch_window(h, a, b)
        print(f"  {key}: {len(C[key])} stories", flush=True)
        CACHE.write_bytes(pickle.dumps(C))
    N = pd.DataFrame([n for v in C.values() for n in v]).drop_duplicates(subset=["t", "headline"])
    N["macro"] = N.headline.str.contains(MACRO) | N.symbols.map(lambda s: bool(BIG & set(s)))
    tn = N.t.to_numpy("datetime64[ns]")
    tm = N[N.macro].t.to_numpy("datetime64[ns]")

    def count(arr, T, w):
        return int(np.searchsorted(arr, T, side="right") - np.searchsorted(arr, T - np.timedelta64(w, "s"),
                                                                            side="right"))

    ranks = {f"{k}{w}": [] for k in ("n", "macro") for w in W}
    hits = {f"{k}{w}": [0, 0, 0, 0] for k in ("n", "macro") for w in W}     # his_any, his_n, near_any, near_n
    for r in x.itertuples():
        T0 = np.datetime64(r.utc.to_datetime64(), "ns")
        others = x[x.d == r.d].utc.to_numpy("datetime64[ns]")
        near = [T0 + np.timedelta64(60 * m, "s") for m in list(range(-20, 0)) + list(range(1, 21))]
        near = [t for t in near if np.min(np.abs((others - t).astype("timedelta64[s]").astype(int))) >= 60]
        for k, arr in (("n", tn), ("macro", tm)):
            for w in W:
                hv = count(arr, T0, w)
                nv = np.array([count(arr, t, w) for t in near])
                ranks[f"{k}{w}"].append((nv < hv).mean() + 0.5 * (nv == hv).mean())
                c = hits[f"{k}{w}"]
                c[0] += hv > 0; c[1] += 1; c[2] += int((nv > 0).sum()); c[3] += len(nv)
    out = [f"Benzinga via Alpaca: {len(N):,} stories on {len(C)} trading days ({int(N.macro.sum()):,} market-wide); "
           f"{len(x)} entries vs the same-sitting moments (headlines stay local - only counts are committed)",
           "\n1. TIMING - stories published just before his click vs before the sitting's other moments",
           f"  {'count':>10}{'his: any':>10}{'nearby: any':>13}{'rank':>7}{'p':>8}"]
    ps = {}
    for k, v in ranks.items():
        v = np.array(v)
        ps[k] = wilcoxon(v - 0.5).pvalue if np.any(v != 0.5) else 1.0
    order = sorted(ps, key=ps.get)
    holm = {k: min(1.0, max(ps[j] * (len(ps) - i) for i, j in enumerate(order[:order.index(k) + 1]))) for k in ps}
    for k in ranks:
        c = hits[k]
        out.append(f"  {k:>10}{c[0] / c[1]:>9.0%}{c[2] / c[3]:>12.0%}{np.mean(ranks[k]):>8.2f}{ps[k]:>8.3f}"
                   f"   Holm {holm[k]:.3f}")
    # the blind sheet for test 2: market-wide stories in the 10 minutes before each entry, his side NOT written
    rows = []
    for i, r in enumerate(x.itertuples()):
        m = N[N.macro & (N.t > r.utc - pd.Timedelta(minutes=10)) & (N.t <= r.utc)]
        for s in m.itertuples():
            rows.append(dict(entry=i, minutes_before=round((r.utc - s.t).total_seconds() / 60, 1),
                             headline=s.headline, label=""))
    pd.DataFrame(rows).to_csv(SHEET, index=False)
    out.append(f"\n2. DIRECTION - {len(rows)} market-wide stories in the 10 min before {len({r['entry'] for r in rows})} "
               f"entries written blind to {SHEET.name} (local) for labelling")
    txt = "\n".join(out)
    print(txt)
    (ROOT / "logs" / "his_headlines.txt").write_text(txt, encoding="utf-8")


if __name__ == "__main__":
    main()
