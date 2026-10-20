"""DOES A PUBLIC SIGNAL CHANNEL CALL HIS TRADES? (2026-10-20, his_strategy.md s72)

His direction is in no market data (s1-s71). The best-fitting unseen source is a live signal feed. news/signal_channels.py
downloaded the 2026 history of 18 public NASDAQ / gold signal channels on Telegram (found by probing ~350 names from the
VM). This matches their calls to his 89 entries (48 NASDAQ, 41 gold; his_clock_exits.trades(), corrected clock, UTC).

    a CALL   a message naming the instrument (NASDAQ: NAS100 / US100 / NASDAQ / USTEC / NDX; gold: XAUUSD / XAU / GOLD) and
             a side (the first BUY / LONG or SELL / SHORT in it)
    a MATCH  a call on his instrument from 10 minutes before his entry to 1 minute after; same side or not
    chance   his entries moved to the same time of day on random other days (+-1..14 days), 300 times: how often the
             channel matches as many - a channel that posts all day matches some entries by luck
REGISTERED BEFORE THE RUN (2026-10-20)
    P1 no channel has a same-side call within 10 minutes before more than 5 of his 89 entries.
    P2 no channel's same-side matches beat chance at p < 0.01 after Holm over the 18 channels.

RESULT (2026-10-20, logs/his_signals.txt) - no public channel calls his trades; P1 / P2 RIGHT.
    ~32,000 messages from the 18 channels: 0 of his 89 entries had a call on his instrument in the 10 minutes before (any
    side). The public NASDAQ-signal space barely exists - even "US100_signals" posts gold, NASDAQ_FREE_SIGNALS posts only
    "VIP signal on" and account-management pitches; 39 NASDAQ calls in all. Gold calls are plentiful (7,000+), and his
    gold burst of 37 entries on 2026-02-02 (05:51-06:39 UTC) had no channel call within 51 minutes. Checked for a
    parsing / timestamp bug: messages parse, times are UTC seconds. If his source is a signal feed, it is not one of these
    public channels - a private or paid one cannot be tested from outside.

    python -m backtest.his_signals
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DATA = ROOT / "strategy_analysis" / "data" / "news" / "tg_signals"
LOG = ROOT / "logs" / "his_signals.txt"
INSTR = {"NASDAQ": re.compile(r"NAS\s?100|US\s?100|NASDAQ|USTEC|\bNDX\b|\bNQ\b", re.I),
         "GOLD": re.compile(r"XAU|GOLD", re.I)}
SIDE = re.compile(r"\b(BUY|LONG|SELL|SHORT)\b", re.I)
PRE, POST = 600, 60


def calls(ch: str) -> pd.DataFrame:
    rows = []
    p = DATA / f"{ch}.jsonl"
    if not p.exists():
        return pd.DataFrame(columns=["ts", "kind", "side"])
    seen = set()
    for line in p.open(encoding="utf-8"):
        try:
            r = json.loads(line)
        except Exception:
            continue
        if "id" not in r or r["id"] in seen:
            continue
        seen.add(r["id"])
        txt = r.get("text") or ""
        m = SIDE.search(txt)
        if not m:
            continue
        side = 1 if m.group(1).upper() in ("BUY", "LONG") else -1
        for kind, rx in INSTR.items():
            if rx.search(txt):
                rows.append((float(r["ts"]), kind, side))
    return pd.DataFrame(rows, columns=["ts", "kind", "side"])


def index(C: pd.DataFrame) -> dict:
    """Sorted call times per (instrument, side) and per instrument - for searchsorted."""
    out = {}
    for kind in INSTR:
        x = C[C.kind == kind]
        out[(kind, None)] = np.sort(x.ts.to_numpy())
        for s in (1, -1):
            out[(kind, s)] = np.sort(x[x.side == s].ts.to_numpy())
    return out


def match(I: dict, H: pd.DataFrame, shift: np.ndarray | None = None) -> tuple:
    t = H.t.to_numpy() + (0 if shift is None else shift)
    same = anys = 0
    for kind in INSTR:
        m = (H.kind == kind).to_numpy()
        for s in (1, -1):
            mm = m & (H.s.to_numpy() == s)
            a = I[(kind, s)]
            if len(a):
                same += int((np.searchsorted(a, t[mm] + POST, "right") - np.searchsorted(a, t[mm] - PRE, "left") > 0).sum())
        a = I[(kind, None)]
        if len(a):
            anys += int((np.searchsorted(a, t[m] + POST, "right") - np.searchsorted(a, t[m] - PRE, "left") > 0).sum())
    return same, anys


def main():
    from backtest.his_clock_exits import trades
    from news.signal_channels import CHANNELS
    T = trades()
    H = pd.DataFrame({"t": [e.timestamp() for e in pd.to_datetime(T.entry).dt.tz_localize("UTC")], "kind": T.kind, "s": T.s})
    rng = np.random.default_rng(20261020)
    shifts = [rng.choice(np.r_[-14:-0, 1:15], size=len(H)) * 86400.0 for _ in range(300)]
    lines = [f"backtest/his_signals.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; his {len(H)} entries "
             f"({(H.kind == 'NASDAQ').sum()} NASDAQ, {(H.kind == 'GOLD').sum()} gold) vs 18 public Telegram signal channels; "
             f"a match = a call on his instrument {PRE // 60} min before .. {POST // 60} min after his entry", "",
             f"   {'channel':<22}{'msgs':>7}{'calls NAS/GOLD':>16}{'span':>25}{'any':>6}{'same side':>11}{'chance':>9}{'p':>7}"]
    res = []
    for ch in CHANNELS:
        p = DATA / f"{ch}.jsonl"
        nmsg = sum(1 for _ in p.open(encoding="utf-8")) if p.exists() else 0
        C = calls(ch)
        if C.empty:
            lines.append(f"   {ch:<22}{nmsg:>7}{'0 / 0':>16}")
            res.append((ch, 0, 0, 0.0, 1.0))
            continue
        I = index(C)
        same, anys = match(I, H)
        null = np.array([match(I, H, sh)[0] for sh in shifts])
        pv = (1 + (null >= same).sum()) / (1 + len(null))
        span = f"{pd.to_datetime(C.ts.min(), unit='s'):%Y-%m-%d}..{pd.to_datetime(C.ts.max(), unit='s'):%Y-%m-%d}"
        lines.append(f"   {ch:<22}{nmsg:>7}{(C.kind == 'NASDAQ').sum():>8} / {(C.kind == 'GOLD').sum():<6}{span:>25}{anys:>6}"
                     f"{same:>11}{null.mean():>9.1f}{pv:>7.3f}")
        res.append((ch, same, anys, null.mean(), pv))
    ps = np.array([r[4] for r in res])
    o = np.argsort(ps)
    holm = np.empty_like(ps)
    run = 0.0
    for k, i in enumerate(o):
        run = max(run, (len(ps) - k) * ps[i])
        holm[i] = min(run, 1.0)
    best = max(res, key=lambda r: r[1])
    p1 = best[1] <= 5
    p2 = not (holm < 0.01).any()
    lines += ["", f"   most same-side matches: {best[0]} with {best[1]} of {len(H)} entries (chance {best[3]:.1f})",
              f"   smallest Holm p: {holm.min():.3f} ({res[int(np.argmin(holm))][0]})", "",
              "REGISTERED PREDICTIONS",
              f"  P1 no channel same-side within 10 min before more than 5 entries: best {best[1]} -> {'RIGHT' if p1 else 'WRONG'}",
              f"  P2 no channel beats chance at Holm p < 0.01 -> {'RIGHT' if p2 else 'WRONG'}"]
    txt = "\n".join(lines)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
