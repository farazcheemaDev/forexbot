"""SEC FILINGS BEFORE HIS CLICKS - does an 8-K (or any filing) by a NASDAQ mega-cap land just before he trades? (2026-10-16)

A pasted write-up: "he scrapes SEC EDGAR / press wires and trades the raw 8-K 15-45 s before the headline channels".
EDGAR's own acceptance time of every filing (data.sec.gov submissions API, free, to the second) for the 8 biggest NASDAQ
stocks (AAPL MSFT NVDA AMZN GOOGL META AVGO TSLA), against his NASDAQ clicks (corrected clock) and his sittings' moments.
The API labels the time 'Z'; it is tested both as UTC and as New York time, in case the label is wrong.

REGISTERED BEFORE THE RUN (2026-10-16): no excess - the share of his clicks with a filing in the 120 s before is within
2x of the sittings' moments (mega-cap 8-Ks during the session are rare, and his moves are ordinary-paced, not news jumps).

RESULT (2026-10-16, logs/his_sec_filings.txt) - RULED OUT. 1,177 filings by the 8 mega-caps since 2025-12-15 (79 8-Ks):
    NONE was accepted within 10 minutes before any of his 46 NASDAQ clicks - or near any of his sittings' 1,840 moments -
    whichever way the time label is read. Their filings come mostly after the close (16:00-23:00 New York); a mega-cap
    8-K inside the session is rare and never fell in one of his sittings.

    python -m backtest.his_sec_filings
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import backtest.his_tape as TP  # noqa: E402

LOG = ROOT / "logs" / "his_sec_filings.txt"
CIK = {"AAPL": 320193, "MSFT": 789019, "NVDA": 1045810, "AMZN": 1018724, "GOOGL": 1652044, "META": 1326801,
       "AVGO": 1730168, "TSLA": 1318605}


def filings():
    rows = []
    for tk, cik in CIK.items():
        req = urllib.request.Request(f"https://data.sec.gov/submissions/CIK{cik:010d}.json",
                                     headers={"User-Agent": "forexbot-research/1.0 research-script"})
        r = json.loads(urllib.request.urlopen(req, timeout=30).read())["filings"]["recent"]
        for f, a in zip(r["form"], r["acceptanceDateTime"]):
            rows.append((tk, f, pd.Timestamp(a).tz_localize(None)))
        time.sleep(0.3)
    F = pd.DataFrame(rows, columns=["tk", "form", "t"])
    return F[F.t >= "2025-12-15"]


def main():
    from scipy.stats import binomtest
    F = filings()
    x = TP.entries()
    his = x.utc.to_numpy()
    near = np.array([u + pd.Timedelta(minutes=m) for u in x.utc for m in list(range(-20, 0)) + list(range(1, 21))])
    out = [f"backtest/his_sec_filings.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; {len(F)} filings by 8 mega-caps since "
           f"2025-12-15 ({(F.form == '8-K').sum()} 8-Ks); {len(his)} NASDAQ clicks, {len(near)} sitting moments", ""]
    for label, shift in (("label read as UTC", 0), ("label read as New York time", None)):
        ft = F.t if shift == 0 else F.t.dt.tz_localize("America/New_York", ambiguous="NaT", nonexistent="NaT").dt.tz_convert("UTC").dt.tz_localize(None)
        for forms, name in ((None, "any form"), (["8-K", "8-K/A"], "8-K only")):
            t = np.sort((ft if forms is None else ft[F.form.isin(forms)]).dropna().to_numpy().astype("datetime64[ns]"))
            for w in (30, 120, 600):
                def share(ts):
                    ts = pd.to_datetime(ts).to_numpy().astype("datetime64[ns]")
                    a = np.searchsorted(t, ts - np.timedelta64(w, "s"), "left")
                    b = np.searchsorted(t, ts, "right")
                    return (b - a) > 0
                sh, sn = share(his), share(near)
                p = binomtest(int(sh.sum()), len(sh), max(sn.mean(), 1e-6)).pvalue
                out.append(f"  {label:<28} {name:<9} {w:>4} s before: his {int(sh.sum())} of {len(sh)} ({sh.mean() * 100:.1f}%) vs "
                           f"sittings {sn.mean() * 100:.2f}% (p {p:.2f})")
    hits = []
    for u in x.utc:
        m = F[(F.t >= u - pd.Timedelta(minutes=10)) & (F.t <= u)]
        if len(m):
            hits.append(f"{u} UTC: " + ", ".join(f"{r.tk} {r.form} {r.t:%H:%M:%S}" for r in m.itertuples()))
    out += ["", "his clicks with any filing (label as UTC) in the 10 minutes before:"] + (["  " + h for h in hits] or ["  none"])
    txt = "\n".join(out)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
