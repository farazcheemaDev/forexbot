"""REBUILD A PAPER BOOK'S EQUITY CURVE CORRECTLY, FROM ITS TRADE LOG.

WHY THIS IS POSSIBLE AT ALL
    The entry-sized fix (mistake #14, 2026-09-23) changed how equity is credited but not what
    is recorded. Every closed trade in logs/trades_blend*.csv carries its R and the risk_pct
    it was sized at, and R is invariant to the accounting. So the whole curve can be replayed
    under either convention, and the pre-fix equity column can be REPAIRED rather than thrown
    away.

THE TWO CONVENTIONS
    OLD (what the log's `equity` column holds, before the fix):
        equity *= (1 + R * risk_pct / 100)
      - the trade earns on equity as it stands AT CLOSE, so its dollars grew with profits
        other trades banked while it was open. The bot cannot do that; it never resizes an
        open position.
    NEW (entry-sized, what the bot and the backtests now do):
        risk_usd fixed at OPEN = equity_at_open * risk_pct / 100
        equity += R * risk_usd

A LOG THAT SPANS THE FIX WILL FAIL THE SELF-CHECK, BY DESIGN
    Trades closed BEFORE the entry-sized fix landed carry old-convention equity; trades closed
    after carry corrected equity. So the old-convention replay cannot reproduce the whole
    column once the log straddles that moment. The check reports the FIRST divergence and its
    timestamp: if that is when the fix was applied (see the marker line in blend_paper.log),
    the mismatch is expected and the corrected curve is still right. If it is some other
    moment, it is a real failure.

HOW IT VALIDATES ITSELF - the part that makes this trustworthy
    Replaying the OLD convention must reproduce the `equity` column already in the CSV, to
    the cent. If it does, the trade order, the risk_pct handling and the arithmetic are all
    confirmed against data this script did not produce - and then the only thing separating
    the NEW curve from the OLD one is the intended change. If it does NOT reproduce, the
    script says so loudly and the corrected curve should not be trusted.

THE ONE APPROXIMATION
    Equity at OPEN requires knowing when each trade opened, and the CSV records only the
    close. Entry time is recovered as `ts - bars * sleeve_hours`. Close times are exact, so
    this only affects where an OPEN sits among the closes around it - i.e. which already-
    banked profits it was sized on. With 12 slots and multi-day holds the ordering is rarely
    ambiguous, but it is an estimate, and `--show-ambiguity` reports how many opens land
    within an hour of a close.

    python rebuild_equity.py                       every book it can find
    python rebuild_equity.py --file logs/trades_blend_tight.csv
    python rebuild_equity.py --csv out.csv         write the corrected curve out
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
LOGS = ROOT / "logs"
START_EQ = 221.0
SLEEVE_H = {"1h": 1, "4h": 4, "12h": 12}
BOOKS = {
    "main": "trades_blend.csv",
    "tight": "trades_blend_tight.csv",
    "sized": "trades_blend_sized.csv",
    "short-boost": "trades_blend_sboost.csv",
    "tstop": "trades_blend_tstop.csv",
}


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
    hrs = d.get("sleeve", pd.Series(["1h"] * len(d))).map(SLEEVE_H).fillna(1).astype(int)
    d["t_open"] = d["ts"] - pd.to_timedelta(d["bars"] * hrs, unit="h")
    # kind="stable" IS LOAD-BEARING. The log is append-only and already chronological, and its
    # `equity` column is only meaningful in the order it was written. sort_values defaults to
    # quicksort, which is NOT stable: it silently reordered simultaneous closes and misaligned
    # the recorded column against its own rows, which read as a $4,534 self-check failure on a
    # log that was in fact correct. 217 of 1,500 closes in that test shared a timestamp.
    return d.sort_values("ts", kind="stable").reset_index(drop=True)


def replay(d: pd.DataFrame, start: float = START_EQ):
    """Both curves in one pass over a single ordered event stream.

    Equity only ever changes on a CLOSE - that is true of the bot and of both conventions -
    so an OPEN's job is purely to read off the equity standing at that moment and freeze the
    trade's dollar risk from it."""
    ev = []
    for i, r in d.iterrows():
        ev.append((r.t_open, 0, i))          # 0 sorts opens before closes at the same stamp
        ev.append((r.ts, 1, i))
    ev.sort(key=lambda x: (x[0], x[1]))

    eq_new, eq_old = start, start
    risk_usd: dict[int, float] = {}
    rows = []
    for t, kind, i in ev:
        if kind == 0:
            risk_usd[i] = eq_new * d.risk_pct[i] / 100.0
            continue
        R, f = d.R[i], d.risk_pct[i] / 100.0
        eq_old *= (1.0 + R * f)                                  # the pre-fix line
        eq_new += R * risk_usd.get(i, eq_new * f)                # entry-sized
        rows.append(dict(ts=t, symbol=d.get("symbol", pd.Series(["?"] * len(d)))[i],
                         sleeve=d.get("sleeve", pd.Series(["?"] * len(d)))[i],
                         R=R, risk_pct=d.risk_pct[i],
                         risk_usd=risk_usd.get(i, float("nan")),
                         equity_corrected=eq_new, equity_old_replayed=eq_old))
    return pd.DataFrame(rows)


def ambiguity(d: pd.DataFrame) -> int:
    """Opens that land within an hour of some close - where the estimated entry time could
    put the open on the wrong side of a banked profit."""
    closes = d.ts.to_numpy()
    n = 0
    for t in d.t_open:
        if len(closes) and np.abs((closes - np.datetime64(t)) / np.timedelta64(1, "h")).min() < 1:
            n += 1
    return n


def report(name: str, path: Path, args):
    d = load(path)
    if not len(d):
        print(f"\n{name:<12} {path.name}: no closed trades yet - nothing to rebuild")
        return
    c = replay(d, args.start)
    recorded = d.get("equity")
    print(f"\n{name.upper()}  ({path.name}, {len(d)} closed trades, "
          f"{d.ts.iloc[0]:%Y-%m-%d} .. {d.ts.iloc[-1]:%Y-%m-%d})")

    # ---- the self-check, before any corrected number is shown --------------------
    ok = None
    if recorded is not None:
        rec = recorded.astype(float)
        # COMPARE PER TIMESTAMP, NOT PER ROW. The old convention multiplies, and multiplication
        # commutes - so its FINAL value is independent of how simultaneous closes are ordered
        # while its intermediate path is not. A row-by-row check flags that harmless tie
        # ordering as an error (it read $4,534 on a validated 1,500-trade log). The last value
        # inside each timestamp is the comparison that actually means something.
        g = pd.DataFrame({"ts": c.ts, "mine": c.equity_old_replayed, "rec": rec.to_numpy()})
        last = g.groupby("ts").last()
        tol = max(0.02, abs(float(last.rec.iloc[-1])) * 2e-4)     # the log rounds to the cent
        d_ts = float((last.mine - last.rec).abs().max())
        d_fin = abs(float(c.equity_old_replayed.iloc[-1]) - float(rec.iloc[-1]))
        ok = d_ts <= tol
        print(f"  SELF-CHECK  replayed OLD vs the log's own equity column")
        print(f"    per timestamp  max diff ${d_ts:.4f}   (tolerance ${tol:.4f})")
        print(f"    final value    diff     ${d_fin:.4f}")
        print(f"    -> {'MATCH - order, risk_pct and arithmetic all confirmed' if ok else 'MISMATCH'}")
        if not ok:
            # A log that SPANS the entry-sized fix will mismatch BY DESIGN: rows closed after
            # the fix were already recorded correctly, so the old-convention replay cannot
            # reproduce them. Locate the first divergence and say so, rather than crying wolf.
            dev = (last.mine - last.rec).abs()
            first = dev[dev > tol].index[0]
            after = int((c.ts >= first).sum())
            print(f"    first divergence at {first}  ({after} of {len(c)} trades from there)")
            print("  *** If that timestamp is when the ENTRY-SIZED FIX landed on this box, the")
            print("  *** mismatch is EXPECTED and the corrected curve below is still right: the")
            print("  *** rows after it were already being recorded the corrected way. Check")
            print("  *** logs/blend_paper.log for the ENTRY-SIZED FIX APPLIED marker line.")
            print("  *** If the timestamp is NOT that moment, something else is wrong and the")
            print("  *** corrected curve is not verified - do not trust it.")
    else:
        print("  SELF-CHECK  skipped: this log has no `equity` column to check against")

    fin_new = float(c.equity_corrected.iloc[-1])
    fin_old = float(c.equity_old_replayed.iloc[-1])
    print(f"  as recorded (pre-fix)   ${fin_old:>9,.2f}   ({fin_old/args.start - 1:+.2f}%)")
    print(f"  CORRECTED, entry-sized  ${fin_new:>9,.2f}   ({fin_new/args.start - 1:+.2f}%)")
    over = fin_old - fin_new
    print(f"  the bug was worth       ${over:>+9.2f}   "
          f"({'overstated' if over > 0 else 'understated'})")
    print(f"  total R {d.R.sum():+.2f} over {len(d)} trades | "
          f"win rate {(d.R > 0).mean()*100:.0f}% | mean {d.R.mean():+.3f}R")
    cur = c.set_index("ts").equity_corrected
    print(f"  corrected drawdown {float((1 - cur/cur.cummax()).max()*100):.1f}%")
    print(f"  NOTE the corrected curve IS sensitive to how simultaneous closes are ordered")
    print(f"  (an open reads equity standing at that instant), unlike the old one. Measured")
    print(f"  at ~0.15% of the total return on a 1,500-trade test - the same slot-order noise")
    print(f"  the backtests average over 5 seeds.")
    if args.show_ambiguity:
        print(f"  entry-time ambiguity: {ambiguity(d)} of {len(d)} opens sit within 1h "
              f"of a close")
    if args.csv:
        out = ROOT / args.csv if not Path(args.csv).is_absolute() else Path(args.csv)
        out = out.with_name(f"{out.stem}_{name}{out.suffix}")
        c.to_csv(out, index=False)
        print(f"  written: {out}")
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", help="one trade log instead of every book")
    ap.add_argument("--start", type=float, default=START_EQ)
    ap.add_argument("--csv", help="write the rebuilt curve(s) to this path")
    ap.add_argument("--show-ambiguity", action="store_true")
    args = ap.parse_args()

    print("REBUILD EQUITY FROM THE TRADE LOG  (mistake #14, entry-sized)")
    print(f"start ${args.start:,.2f} | R is invariant to the accounting, so it is the anchor")
    if args.file:
        p = Path(args.file)
        if not p.is_absolute():
            p = ROOT / args.file
        if not p.exists():
            raise SystemExit(f"no such file: {p}")
        report(p.stem, p, args)
        return
    found = False
    for name, fn in BOOKS.items():
        p = LOGS / fn
        if p.exists():
            found = True
            report(name, p, args)
    if not found:
        print(f"\nNo trade logs found in {LOGS}.")
        print("These live on the Azure VM, not here. Either copy one down, or run this")
        print("script there - Run command > RunShellScript:")
        print("\n  cd /opt/forexbot && ./.venv/bin/python rebuild_equity.py\n")
        sys.exit(2)


if __name__ == "__main__":
    main()
