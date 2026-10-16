"""DOES HE TRADE THE HEADLINE WIRE? Fast headline channels against the second of each of his clicks (2026-10-12)

THE USER (2026-10-12): "yes run the headline test - find yourself first which you think matches his time". His edge is
real and not in any price data (his_strategy.md s36-48: right 38 of 43 on the next 1-5 minutes; his two newest trades
saw +7 points within 1-2 s of the click). The one information channel never tested is the LIVE HEADLINE WIRE (s36 lists
it). Retail squawk / headline services post to public Telegram channels with second-level timestamps.

CHANNELS (public Telegram web previews, t.me/s/<name>; reachable from the VM, not from this PC - the VM only READS a
          public page and prints it back over ssh; nothing is written there)
    FinancialJuice, WalterBloomberg, breakingmarketnews, marketfeed - the four fast market-headline channels found live with
    history back to January 2026 (probed 2026-10-12; FirstSquawk, LiveSquawk, ForexLive, Newsquawk, zerohedge: no channel).
CLICKS   his 46 NASDAQ trades from the statement (2026-01-02 .. 2026-09-14, his_clock_check.to_utc: UTC+4 winter, +5
          summer) + the 2 of 2026-10-08 from the latest statement (his_strategy.md s48) = 48; his 41 GOLD trades as a second
          set. Times to the second.
CONTROL  moments of the SAME sittings: every 30 s within 20 minutes of any of his clicks, at least 60 s from all of them.
MEASURE  the share of clicks / control moments with at least one headline in the 15 s (and 60 s) BEFORE; and the
          headlines' text in the minute before each click, for reading against his side.

REGISTERED BEFORE THE RUN (2026-10-12)
    HL1  If he trades the wire, a headline precedes his clicks far more often than the control moments: >= 2x the
         control's share within 15 s on at least one channel, binomial p < 0.01.
    HL2  My expectation (s28-29 found nothing in scheduled news or posts): NO channel reaches 2x; his clicks are preceded
         by a headline within 15 s at 0.7-1.5x the control rate on every channel.

    python -m backtest.his_headlines --fetch     (pulls the windows through the VM; cached in strategy_analysis/data/headlines/)
    python -m backtest.his_headlines             (the analysis)

RESULT (2026-10-12 14:20 UTC, logs/his_headlines.txt; 3 of 4 channels - marketfeed's windows were still downloading;
FinancialJuice 367, WalterBloomberg 239, breakingmarketnews 306 headlines in his 35 sittings)
    - HL1: NOT SHOWN - he does not click on headlines. In the 15 s before his 48 NASDAQ clicks a headline appeared on 4.2%
      (FinancialJuice) / 0% (WalterBloomberg) / 2.1% (breakingmarketnews) of them, against 4.2 / 2.3 / 2.9% of same-sitting
      moments - 1.00x, 0.00x, 0.72x. His 41 gold clicks: fewer headlines than the control on every channel.
    - The 60 s window looked different on first reading - NASDAQ 33% vs 19% on any channel (1.78x, p 0.012; FinancialJuice
      2.15x, p 0.004) - but that is WHEN he trades, not what he reads: 12 of his 48 NASDAQ clicks fall in minutes :00-:04 of
      the hour (25% vs 8% by chance), when scheduled numbers and settlements are posted. Against control moments matched to
      his minute-of-hour mix (a check added after the first reading): 60 s 1.48x, 15 s 0.48x.
    - The headlines in the minute before his clicks do not carry his side: a Trump Q&A, a crypto fear index, Fitch on oil, a
      Brent settlement, a Kuwaiti soldier, an EU commissioner on spreads - before winning BUYs and SELLs alike.
    - HL2 WRONG only in letter (WalterBloomberg 0.00x, under the 0.7 floor, on 0 of 89 clicks).
    ADDED 2026-10-12 14:46 UTC with all four channels (marketfeed's 1,664 headlines in): 15 s before his 89 clicks 0.56-0.88x
    the control on every channel (any channel 0.82x); 60 s 1.15-1.24x, none significant (p >= 0.11). Unchanged.
    Reading: the live headline wire - the last public source named in s36 - is not where his direction comes from. New fact:
    a quarter of his NASDAQ entries come in the first five minutes of an hour.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from math import comb
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest.his_clock_check import to_utc  # noqa: E402

CACHE = ROOT / "strategy_analysis" / "data" / "headlines"
LOG = ROOT / "logs" / "his_headlines.txt"
CHANNELS = ["FinancialJuice", "WalterBloomberg", "breakingmarketnews", "marketfeed"]
PAD = 1500                                                     # seconds of headlines kept around each sitting

VM_SCRIPT = r'''
import json, re, sys, time, urllib.request, html
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
from datetime import datetime
def page(ch, before=None):
    u = "https://t.me/s/%s" % ch + ("?before=%d" % before if before else "")
    for k in range(3):
        try:
            h = urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=20).read().decode("utf-8", "replace")
            break
        except Exception:
            time.sleep(2 + 2 * k); h = ""
    out = []
    for blk in re.split(r'<div class="tgme_widget_message_wrap', h)[1:]:
        m_id = re.search(r'data-post="[^/]+/(\d+)"', blk)
        m_t = re.search(r'<time datetime="([^"]+)"', blk)
        if not (m_id and m_t):
            continue
        txt = re.search(r'<div class="tgme_widget_message_text[^>]*>(.*?)</div>', blk, re.S)
        t = re.sub(r"<br\s*/?>", " ", txt.group(1)) if txt else ""
        t = html.unescape(re.sub(r"<[^>]+>", "", t)).strip()
        ts = datetime.fromisoformat(m_t.group(1)).timestamp()
        out.append((int(m_id.group(1)), ts, t[:300]))
    time.sleep(0.35)
    return out
def span(ch):
    p = page(ch)
    return p[-1][0], p[-1][1]
def find_id(ch, target, hi_id, hi_t):
    lo_id, lo_t = 1, None
    a, b = 1, hi_id
    ta, tb = None, hi_t
    for _ in range(40):
        if b - a <= 20:
            break
        if ta is None:
            mid = (a + b) // 2
        else:
            mid = int(a + (b - a) * (target - ta) / max(tb - ta, 1))
            mid = min(max(mid, a + 10), b - 10)
        p = page(ch, before=mid + 1)
        if not p:
            a = mid; continue
        t_mid = p[-1][1]
        if t_mid < target:
            a, ta = p[-1][0], t_mid
        else:
            b, tb = p[0][0], p[0][1]
    return b
targets = json.loads(sys.stdin.readline())
for ch in targets["channels"]:
    hi_id, hi_t = span(ch)
    for (t0, t1) in targets["windows"]:
        idx = find_id(ch, t1, hi_id, hi_t) + 25
        got, guard = [], 0
        while guard < 400:
            guard += 1
            p = page(ch, before=idx)
            if not p:
                break
            got += p
            if p[0][1] < t0:
                break
            idx = p[0][0]
        for (i, ts, tx) in got:
            if t0 <= ts <= t1:
                print(json.dumps({"ch": ch, "id": i, "ts": ts, "text": tx}), flush=True)
        print(json.dumps({"ch": ch, "window": [t0, t1], "n": len(got)}), file=sys.stderr, flush=True)
'''


def clicks() -> pd.DataFrame:
    x = pd.read_csv(ROOT / "strategy_analysis" / "statement_trades.csv", parse_dates=["open_time"])
    rows = []
    for kind, pref in (("NASDAQ", "NASDAQ"), ("GOLD", "GOLD")):
        g = x[x.symbol.str.startswith(pref)]
        u = to_utc(g.open_time, 4.0, 5.0)
        for t, s, pnl in zip(u, g.side, g.net):
            if t >= pd.Timestamp("2026-01-01"):
                rows.append(dict(kind=kind, utc=pd.Timestamp(t), side=s, net=pnl))
    new = ROOT / "strategy_analysis" / "his_statement_2026-10_trades.csv"
    if new.exists():
        n = pd.read_csv(new)
        for r in n.itertuples():
            t = pd.to_datetime(r.open_time, format="%d-%m-%Y %H:%M:%S") - pd.Timedelta(hours=5)
            if t > pd.Timestamp("2026-10-01") and str(r.symbol).startswith("NASDAQ"):
                rows.append(dict(kind="NASDAQ", utc=t, side=r.side, net=float(str(r.net).replace(",", ""))))
    out = pd.DataFrame(rows).sort_values("utc", kind="stable").reset_index(drop=True)
    out["utc"] = pd.to_datetime(out.utc).astype("datetime64[ns]")      # ns, so int64 // 10**9 is seconds (CLAUDE.md s3)
    return out


def windows(C: pd.DataFrame):
    ts = np.sort((C.utc.astype("int64") // 10**9).to_numpy())
    out, a, b = [], ts[0] - PAD, ts[0] + PAD
    for t in ts[1:]:
        if t - PAD <= b:
            b = t + PAD
        else:
            out.append((int(a), int(b)))
            a, b = t - PAD, t + PAD
    out.append((int(a), int(b)))
    return out


def run_vm(channels, wins, out_path: Path, err_path: Path):
    """run VM_SCRIPT on the VM (python3, stdlib only) with the targets written into it; it only READS public t.me pages
    and prints JSON lines back - nothing is written on the VM. Appends to both files (resumable)."""
    script = VM_SCRIPT.replace("targets = json.loads(sys.stdin.readline())",
                               "targets = " + repr({"channels": channels, "windows": wins}))
    with open(out_path, "a", encoding="utf-8") as fo, open(err_path, "a", encoding="utf-8") as fe:
        subprocess.run(["ssh", "-o", "ConnectTimeout=20", "-o", "ServerAliveInterval=30", "-o", "ServerAliveCountMax=6",
                        "forexbot-vm", "python3 -"], input=script, text=True, stdout=fo, stderr=fe, timeout=4 * 3600)


def done_windows(err_path: Path) -> set:
    """(channel, window start) pairs already fetched, from the progress log (a first run lost its link after 27)."""
    out = set()
    if err_path.exists():
        for l in open(err_path, encoding="utf-8"):
            if l.startswith("{"):
                d = json.loads(l)
                out.add((d["ch"], int(d["window"][0])))
    return out


def fetch(test: bool = False):
    C = clicks()
    W = windows(C)
    CACHE.mkdir(parents=True, exist_ok=True)
    out, err = CACHE / ("test.jsonl" if test else "headlines.jsonl"), CACHE / "fetch_progress.txt"
    if test:
        run_vm(CHANNELS[:1], W[-1:], out, err)
        return
    for attempt in range(6):
        done = done_windows(err)
        todo = {ch: [w for w in W if (ch, w[0]) not in done] for ch in CHANNELS}
        left = sum(len(v) for v in todo.values())
        print(f"{len(C)} clicks, {len(W)} sittings; {left} channel-windows left (attempt {attempt + 1})", flush=True)
        if not left:
            break
        for ch, wins in todo.items():
            if wins:
                run_vm([ch], wins, out, err)
    n = sum(1 for _ in open(out, encoding="utf-8"))
    print(f"stored {n} headlines in {out.name}")


def binom_p(k, n, p0):
    """one-sided P(X >= k) for X ~ Bin(n, p0)."""
    return float(sum(comb(n, i) * p0 ** i * (1 - p0) ** (n - i) for i in range(k, n + 1)))


def analyse():
    C = clicks()
    H = pd.read_json(CACHE / "headlines.jsonl", lines=True)
    lines = [f"backtest/his_headlines.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; {len(C)} clicks "
             f"({(C.kind == 'NASDAQ').sum()} NASDAQ, {(C.kind == 'GOLD').sum()} gold) in {len(windows(C))} sittings; "
             f"headlines in the windows: " + ", ".join(f"{c} {int((H.ch == c).sum())}" for c in CHANNELS), ""]
    clk = (C.utc.astype("int64") // 10**9).to_numpy()
    ctrl = []
    for t in clk:
        for off in range(-1200, 1201, 30):
            u = t + off
            if np.min(np.abs(clk - u)) >= 60:
                ctrl.append(u)
    ctrl = np.unique(np.array(ctrl))
    res = {}
    for kind in ("NASDAQ", "GOLD", "ALL"):
        ck = clk if kind == "ALL" else (C[C.kind == kind].utc.astype("int64") // 10**9).to_numpy()
        lines.append(f"{kind} clicks ({len(ck)}) vs {len(ctrl)} same-sitting moments: share with >= 1 headline in the window BEFORE")
        for ch in CHANNELS + ["any"]:
            hts = np.sort(H.ts.to_numpy() if ch == "any" else H[H.ch == ch].ts.to_numpy())
            row = f"  {ch:20}"
            for w in (15, 60):
                def share(xs):
                    a = np.searchsorted(hts, xs - w, "left")
                    b = np.searchsorted(hts, xs, "left")
                    return (b - a) > 0
                sc, so = share(ck), share(ctrl)
                k, n, p0 = int(sc.sum()), len(sc), max(so.mean(), 1e-6)
                pv = binom_p(k, n, p0)
                res[(kind, ch, w)] = (sc.mean(), so.mean(), pv)
                row += f" | {w:2d}s: his {sc.mean() * 100:5.1f}% vs {so.mean() * 100:5.1f}% ({sc.mean() / p0:4.2f}x, p {pv:.3f})"
            lines.append(row)
        lines.append("")
    lines.append("HEADLINES IN THE 60 s BEFORE EACH NASDAQ CLICK (his side, result $; s before the click, channel: text)")
    for r in C[C.kind == "NASDAQ"].itertuples():
        t = int(r.utc.value // 10**9)
        h = H[(H.ts >= t - 60) & (H.ts < t)].sort_values("ts")
        lines.append(f"  {r.utc:%Y-%m-%d %H:%M:%S} UTC {r.side:4} {r.net:+8.2f}" + ("" if len(h) else "   (none)"))
        for x in h.itertuples():
            lines.append(f"      -{t - x.ts:4.0f}s {x.ch[:12]:12} {x.text[:110]}")
    lines.append("")
    best = max(((v[0] / max(v[1], 1e-6), k) for k, v in res.items() if k[0] == "ALL" and k[2] == 15 and k[1] != "any"))
    hl1 = any(v[0] >= 2 * v[1] and v[2] < 0.01 for k, v in res.items() if k[2] == 15 and k[1] != "any")
    lines.append("REGISTERED PREDICTIONS")
    lines.append(f"  HL1 a channel at >= 2x the control within 15 s with p < 0.01: {'YES' if hl1 else 'no'} -> "
                 f"{'he trades the wire' if hl1 else 'not shown'}")
    ratios = [v[0] / max(v[1], 1e-6) for k, v in res.items() if k[0] == "ALL" and k[2] == 15 and k[1] != "any"]
    lines.append(f"  HL2 every channel within 0.7-1.5x at 15 s: " + ", ".join(f"{r:.2f}" for r in ratios) +
                 f" -> {'RIGHT' if all(0.7 <= r <= 1.5 for r in ratios) else 'WRONG'}; best {best[1][1]} {best[0]:.2f}x")
    txt = "\n".join(lines)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt.encode("ascii", "replace").decode())


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--fetch", action="store_true")
    ap.add_argument("--test", action="store_true")
    a = ap.parse_args()
    if a.fetch or a.test:
        fetch(test=a.test)
    else:
        analyse()
