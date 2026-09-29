"""REBUILD A PAPER BOOK'S EQUITY CURVE CORRECTLY, FROM ITS TRADE LOG.

WHY THIS IS POSSIBLE AT ALL
    The entry-sized fix (mistake #14, 2026-09-23) changed how equity is credited but not what
    is recorded. Every closed trade in logs/trades_blend*.csv carries its R and the risk_pct
    it was sized at, and R is invariant to the accounting. So the whole curve can be replayed
    under either convention, and the recorded equity column can be REPAIRED rather than thrown
    away.

THE TWO CONVENTIONS
    OLD (legacy):  a position opened BEFORE the fix carries no risk_usd, so blend_paper.py
        still credits it as  equity += R * (equity AT CLOSE) * risk_pct / 100. When several
        such positions close in one poll, each is scaled up by the one before it.
    NEW (entry-sized, what the bot and the backtests now do):
        risk_usd fixed at OPEN = equity_at_open * risk_pct / 100
        equity += R * risk_usd

    The legacy path did not stop at the fix: every position that was ALREADY OPEN then kept
    using it until it closed, and the forked books inherited those positions. On 2026-09-28 eight
    of them closed in two polls and the triple book's recorded equity went $209.68 -> $883.52;
    entry-sized, the same 548R is worth ~$555. This script is how that was measured.

HOW IT VALIDATES ITSELF - the part that makes this trustworthy
    It replays the log AS THE BOT RECORDED IT - legacy for positions opened before the fix
    (the ENTRY-SIZED FIX APPLIED marker in blend_paper.log), entry-sized after - and that
    replay must reproduce the log's own `equity` column row by row, to the cent. If it does,
    the event order, the entry times, the fork start and the arithmetic are all confirmed
    against data this script did not produce, and the only thing separating the CORRECTED
    curve from the recorded one is the intended change.

    Reproducing it needs the bot's order INSIDE a poll: blend_paper.cycle walks BOOK coin by
    coin and each coin's sleeves in order, closing or opening as it goes, so a position opened
    mid-poll is sized on the closes before it and not the ones after. Checked on the triple's
    real 2026-09-28 rows: SHIB opened between LTC's and WLD's closes at $322.99, WLD between
    ENA's and NEAR's at $609.18, ARB after NEAR's at $883.52 (tests/test_rebuild_equity.py).

FORKED BOOKS
    tight / sized / short-boost / tstop / units / triple each started as a COPY of the main
    book (its equity and its open positions) at the moment in their state file's `forked`.
    Their own CSV starts there. So each is replayed as main's closes up to the fork plus its
    own closes after, which is its true history. Without the state file it falls back to its
    own trades from $221 and says so.

THE ONE APPROXIMATION
    The CSV records only the close. Entry time is recovered as `ts - bars * sleeve_hours`,
    floored to the hour: a bar is acted on by the first poll after it closes, so the entry and
    exit polls sit the same few seconds after their hours. A process outage undercounts `bars`
    and puts the open too late - the self-check catches that as a mismatch.

    python rebuild_equity.py                       every book it can find, one line each
    python rebuild_equity.py --detail              the long report per book
    python rebuild_equity.py --file logs/trades_blend_tight.csv
    python rebuild_equity.py --csv out.csv         write the corrected curve(s) out
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from blend_paper import BOOK, SLEEVES  # noqa: E402  the order cycle() walks inside a poll

LOGS = ROOT / "logs"
START_EQ = 221.0
SLEEVE_H = {"1h": 1, "4h": 4, "12h": 12}
MARKER = "ENTRY-SIZED FIX APPLIED"
BOOKS = {                          # name: (trades log, state file holding `forked`)
    "main": ("trades_blend.csv", None),
    "tight": ("trades_blend_tight.csv", "blend_state_tight.json"),
    "sized": ("trades_blend_sized.csv", "blend_state_sized.json"),
    "short-boost": ("trades_blend_sboost.csv", "blend_state_sboost.json"),
    "tstop": ("trades_blend_tstop.csv", "blend_state_tstop.json"),
    "units": ("trades_blend_units.csv", "blend_state_units.json"),
    "triple": ("trades_blend_triple.csv", "blend_state_triple.json"),
}


def _utc(t) -> pd.Timestamp:
    t = pd.Timestamp(t)
    return t.tz_convert(None) if t.tzinfo is not None else t


def load(path: Path) -> pd.DataFrame:
    d = pd.read_csv(path)
    need = {"ts", "R", "risk_pct", "bars"}
    missing = need - set(d.columns)
    if missing:
        raise SystemExit(f"{path.name} is missing {sorted(missing)} - not a blend trade log")
    d["ts"] = pd.to_datetime(d["ts"])
    d["R"] = d["R"].astype(float)
    d["risk_pct"] = d["risk_pct"].astype(float)
    d["bars"] = d["bars"].astype(int)
    if "sleeve" not in d:
        d["sleeve"] = "1h"
    if "symbol" not in d:
        d["symbol"] = "?"
    hrs = d["sleeve"].map(SLEEVE_H).fillna(1).astype(int)
    d["t_open"] = d["ts"] - pd.to_timedelta(d["bars"] * hrs, unit="h")
    d["kidx"] = d["symbol"].map({s: i for i, s in enumerate(BOOK)}).fillna(len(BOOK)).astype(int)
    d["sidx"] = d["sleeve"].map({s: i for i, s in enumerate(SLEEVES)}).fillna(0).astype(int)
    d["own"] = True
    # kind="stable" IS LOAD-BEARING: the log is append-only, and simultaneous closes must keep
    # the order they were written in (quicksort once misaligned the equity column, $4,534).
    return d.sort_values("ts", kind="stable").reset_index(drop=True)


def fork_time(state: Path) -> pd.Timestamp | None:
    try:
        f = json.loads(state.read_text()).get("forked")
    except Exception:
        return None
    return _utc(f) if f else None


def fix_time(logf: Path) -> pd.Timestamp | None:
    """When the entry-sized fix went live on this box: the marker line patch_entry_sized.sh
    wrote into blend_paper.log. A position opened before it has no risk_usd."""
    if not logf.exists():
        return None
    with open(logf, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if MARKER in line:
                m = re.match(r"(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ)", line)
                if m:
                    return _utc(m.group(1))
    return None


def book_frame(name: str, logs: Path = LOGS) -> tuple[pd.DataFrame, str | None]:
    """The book's whole history: for a forked book, main's closes up to the fork, then its own."""
    fn, sfile = BOOKS[name]
    d = load(logs / fn)
    if sfile is None:
        return d, None
    ft = fork_time(logs / sfile)
    mp = logs / BOOKS["main"][0]
    if ft is None or not mp.exists():
        return d, "no fork time/main log: replayed from $221 on its own trades, NOT its true start"
    m = load(mp)
    m = m[m.ts <= ft].copy()
    m["own"] = False
    return pd.concat([m, d], ignore_index=True), None


def replay(d: pd.DataFrame, start: float = START_EQ, fix: pd.Timestamp | None = None
           ) -> pd.DataFrame:
    """Two curves in one pass over the bot's own event order.

    equity_bot        what blend_paper.py recorded: legacy (sized at close) for positions opened
                      before `fix`, entry-sized after. fix=None means every position is legacy,
                      i.e. the whole log predates the fix.
    equity_corrected  every position entry-sized.

    Events are ordered (hour, coin in BOOK order, sleeve, close-before-open), which is the order
    cycle() acts in. Equity changes only on a close; an open only reads it."""
    n = len(d)
    R, f = d.R.to_numpy(float), d.risk_pct.to_numpy(float) / 100.0
    k, s = d.kidx.to_numpy(int), d.sidx.to_numpy(int)
    h_open = d.t_open.dt.floor("h").to_numpy()
    h_close = d.ts.dt.floor("h").to_numpy()
    legacy = (d.t_open < fix).to_numpy() if fix is not None else np.ones(n, bool)
    ev = [(h_open[i], k[i], s[i], 1, i) for i in range(n)] + \
         [(h_close[i], k[i], s[i], 0, i) for i in range(n)]
    ev.sort(key=lambda e: e[:4])
    eq_bot = eq_new = float(start)
    ru_bot: dict[int, float] = {}
    ru_new: dict[int, float] = {}
    rec = d["equity"].astype(float).to_numpy() if "equity" in d else np.full(n, np.nan)
    rows = []
    for _, _, _, kind, i in ev:
        if kind == 1:
            ru_bot[i], ru_new[i] = eq_bot * f[i], eq_new * f[i]
            continue
        eq_bot += R[i] * (eq_bot * f[i] if legacy[i] else ru_bot.get(i, eq_bot * f[i]))
        eq_new += R[i] * ru_new.get(i, eq_new * f[i])
        rows.append(dict(ts=d.ts[i], symbol=d.symbol[i], sleeve=d.sleeve[i], R=R[i],
                         risk_pct=f[i] * 100, legacy=bool(legacy[i]), own=bool(d.own[i]),
                         risk_usd=ru_new.get(i, np.nan), equity_recorded=rec[i],
                         equity_bot=eq_bot, equity_corrected=eq_new))
    return pd.DataFrame(rows)


def check(c: pd.DataFrame) -> tuple[bool | None, float, pd.Timestamp | None]:
    """Row by row on the book's OWN rows: does the as-recorded replay reproduce the log?
    Tolerance: the log rounds to the cent, R to 4 places, risk_pct to 3 (the sized book)."""
    o = c[c.own & c.equity_recorded.notna()]
    if not len(o):
        return None, 0.0, None
    diff = (o.equity_bot - o.equity_recorded).abs()
    tol = np.maximum(0.02, o.equity_recorded.abs() * 5e-4)
    bad = diff > tol
    return (not bad.any()), float(diff.max()), (o.ts[bad].iloc[0] if bad.any() else None)


def growth_since(path: Path, t0, start: float = START_EQ) -> tuple[float, int]:
    """The multiple a book starting FLAT at t0 with `start` would show on the trades this log
    OPENED at or after t0 - entry-sized, compounded by close date. Closed trades only.
    combo_paper.py's fair H1 yardstick (the triple forked with positions it had not earned)."""
    d = load(path)
    d = d[d.t_open >= _utc(t0)].reset_index(drop=True)
    if not len(d):
        return 1.0, 0
    return float(replay(d, start).equity_corrected.iloc[-1]) / start, len(d)


def summarise(name: str, d: pd.DataFrame, note: str | None, fix, start: float) -> dict:
    c = replay(d, start, fix)
    ok, dmax, first = check(c)
    o = c[c.own]
    return dict(name=name, c=c, ok=ok, dmax=dmax, first=first, note=note, n=len(o),
                n_legacy=int(o.legacy.sum()),
                recorded=float(o.equity_recorded.iloc[-1]) if len(o) else np.nan,
                corrected=float(c.equity_corrected.iloc[-1]) if len(c) else start)


def detail(r: dict, args):
    o = r["c"][r["c"].own]
    print(f"\n{r['name'].upper()}  ({r['n']} closed trades, {r['n_legacy']} sized the legacy way)")
    if r["note"]:
        print(f"  NOTE {r['note']}")
    print(f"  recorded   ${r['recorded']:>10,.2f}")
    print(f"  CORRECTED  ${r['corrected']:>10,.2f}   ({r['corrected'] / args.start - 1:+.1%})")
    print(f"  total R {o.R.sum():+.2f} | win rate {(o.R > 0).mean() * 100:.0f}% | "
          f"mean {o.R.mean():+.3f}R")
    cur = r["c"].equity_corrected
    print(f"  corrected drawdown {float((1 - cur / cur.cummax()).max() * 100):.1f}%")
    big = o[o.legacy].nlargest(5, "R")
    if len(big):
        print("  biggest legacy closes: " + ", ".join(
            f"{x.symbol[:-4]} {x.R:+.0f}R" for x in big.itertuples()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", help="one trade log instead of every book")
    ap.add_argument("--start", type=float, default=START_EQ)
    ap.add_argument("--fix-time", help="override the ENTRY-SIZED FIX marker time (UTC)")
    ap.add_argument("--detail", action="store_true")
    ap.add_argument("--csv", help="write the rebuilt curve(s) to this path")
    ap.add_argument("--show-ambiguity", action="store_true", help=argparse.SUPPRESS)  # old flag
    args = ap.parse_args()

    fix = _utc(args.fix_time) if args.fix_time else fix_time(LOGS / "blend_paper.log")
    print("EQUITY REBUILT FROM THE TRADE LOGS (entry-sized; R is the anchor)")
    print(f"fix live from {fix if fix is not None else 'UNKNOWN - every position treated as legacy'}")
    if args.file:
        p = Path(args.file)
        p = p if p.is_absolute() else ROOT / p
        if not p.exists():
            raise SystemExit(f"no such file: {p}")
        todo = [(p.stem, load(p), "single file: replayed from --start")]
    else:
        todo = [(n, *book_frame(n)) for n, (fn, _) in BOOKS.items() if (LOGS / fn).exists()]
    if not todo:
        print(f"\nNo trade logs in {LOGS}. They live on the Azure VM:")
        print("  cd /opt/forexbot && ./.venv/bin/python rebuild_equity.py")
        sys.exit(2)
    res = [summarise(n, d, note, fix, args.start) for n, d, note in todo if len(d)]
    print(f"\n{'book':<12}{'trades':>7}{'legacy':>7}{'recorded':>11}{'CORRECTED':>11}"
          f"{'overstated':>12}  self-check")
    for r in res:
        chk = ("-" if r["ok"] is None else f"MATCH ${r['dmax']:.2f}" if r["ok"]
               else f"MISMATCH from {r['first']:%m-%d %H:%M}")
        print(f"{r['name']:<12}{r['n']:>7}{r['n_legacy']:>7}{r['recorded']:>11.2f}"
              f"{r['corrected']:>11.2f}{r['recorded'] - r['corrected']:>+12.2f}  {chk}"
              + ("  *" if r["note"] else ""))
    if any(r["note"] for r in res):
        print("* " + next(r["note"] for r in res if r["note"]))
    if any(r["ok"] is False for r in res):
        print("MISMATCH = the replay could not reproduce that book's log. Its CORRECTED figure")
        print("is NOT verified. Run --detail --file on it, or check the fix time.")
    print("Compare books by CORRECTED (or by R), never by recorded equity.")
    for r in res:
        if args.detail:
            detail(r, args)
        if args.csv:
            out = Path(args.csv)
            out = (out if out.is_absolute() else ROOT / out)
            out = out.with_name(f"{out.stem}_{r['name']}{out.suffix}")
            r["c"].to_csv(out, index=False)
            print(f"written: {out}")


if __name__ == "__main__":
    main()
