"""ONE COMMAND THAT ANSWERS "IS THE BOT WORKING?" — without the trap that got me before.

    python health.py                 check everything on this machine
    python health.py --vm 1.2.3.4    also read the status page on the VM
    python health.py --log poly      dump the tail of one bot's log

WHY THIS FILE EXISTS
    On 2026-09-12 I started a SECOND copy of a bot against the same demo account.
    Cause, recorded in longtrend_bot.acquire_lock: I checked what was running with
    `wmic | grep`, wmic WRAPS long command lines so the bot fell across a line break
    and looked absent, and I then read its between-bar silence as death. Two weak
    signals agreed and produced a confident wrong conclusion.

    So this checks THREE INDEPENDENT THINGS and reports them separately. They can
    disagree, and when they do that disagreement is the information.

        1. PROCESS   is a process alive whose command line names this script?
                     By pid from the bot's own lock file, cross-checked against the
                     command line so a recycled pid cannot pass.

        2. HEARTBEAT is the file the bot touches EVERY CYCLE fresh?
                     Deliberately NOT the log. The bots log once per closed BAR -
                     a 12h sleeve is silent for 12h while working perfectly - but
                     they call save_state() every poll. State mtime is the pulse;
                     the log is the diary.

        3. PROGRESS  are the counters moving?
                     A bot can be alive and healthy and still take no trades for
                     days. That is not a fault, so it is reported apart from the
                     verdict rather than folded into it.

    ALIVE + FRESH            = working
    ALIVE + STALE            = WEDGED. Worse than dead: it holds the lock, so a
                               restart refuses, and it is not managing open trades.
    DEAD  + STALE            = dead. Restart it.
    can't see it + FRESH     = trust the files, not the process list. This is the
                               exact direction the 2026-09-12 mistake went.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LOGS = ROOT / "logs"
H = 3600

# ---------------------------------------------------------------------------
# THE REGISTRY.
#
# `beat` is the file written EVERY CYCLE, and `beat_max` is its poll interval with
# room for one missed pass plus a slow exchange call. These come from the source,
# not from taste:
#
#   blend_paper.POLL_S    = 120   -> save_state every 2 min
#   longtrend_bot.POLL_S  =  60   -> every 1 min
#   xs_paper.POLL_S       = 300   -> every 5 min
#   poly_forward.RESOLVE_EVERY_H = 3  -> writes the log every 3h; the CSV only when
#                                        a market is new, so the LOG is the pulse
#                                        for this one and the CSV is progress.
# ---------------------------------------------------------------------------
BOTS = [
    dict(key="poly", label="Polymarket forward test", match="poly_forward.py",
         pidfile=LOGS / "poly_forward.pid", where="local",
         beat=LOGS / "poly_forward.log", beat_max=3.5 * H,
         log=LOGS / "poly_forward.log", rows=LOGS / "poly_snapshots.csv",
         note="records prices only - no keys, no orders, no funds"),

    dict(key="blend", label="$221 blend - THE validated strategy", match="blend_paper.py",
         pidfile=None, where="vm",
         beat=LOGS / "blend_state.json", beat_max=6 * 60,
         log=LOGS / "blend_paper.log", state=LOGS / "blend_state.json",
         note="paper. Lives on the Azure VM; absent here is correct."),

    dict(key="demo", label="Bitget DEMO order-path test", match="longtrend_bot.py",
         pidfile=LOGS / "longtrend_demo.pid", where="local",
         beat=LOGS / "longtrend_state.json", beat_max=5 * 60,
         log=LOGS / "longtrend.log", state=LOGS / "longtrend_state.json",
         note="places REAL orders on the DEMO account. One instance only, ever."),

    dict(key="micro", label="$10 micro bot", match="micro_bot.py",
         pidfile=LOGS / "micro_bot.pid", where="off",
         beat=LOGS / "micro_state.json", beat_max=5 * 60,
         log=LOGS / "micro_bot.log", state=LOGS / "micro_state.json",
         note="ALLOW_REAL=False. Not meant to be running."),

    dict(key="ltp", label="longtrend paper (older single-timeframe)", match="longtrend_paper.py",
         pidfile=LOGS / "longtrend_paper.pid", where="off",
         beat=LOGS / "ltp_state.json", beat_max=6 * 60,
         log=LOGS / "longtrend_paper.log", state=LOGS / "ltp_state.json",
         note="superseded by the blend. Kept for comparison."),

    dict(key="mnp", label="market-neutral paper book (5th book)", match="mn_paper.py",
         pidfile=LOGS / "mn_paper.pid", where="local",
         beat=LOGS / "mnp_state.json", beat_max=45 * 60,
         log=LOGS / "mn_paper.log", state=LOGS / "mnp_state.json",
         rows=LOGS / "mnp_rebalances.csv",
         note="paper. Marks once a DAY and rebalances weekly - a quiet log is normal."),

    dict(key="xsp", label="cross-sectional paper (older)", match="xs_paper.py",
         pidfile=LOGS / "xs_paper.pid", where="off",
         beat=LOGS / "xsp_state.json", beat_max=12 * 60,
         log=LOGS / "xs_paper.log", state=LOGS / "xsp_state.json",
         note="superseded. Kept for comparison."),
]


# ---------------------------------------------------------------------------
def procs() -> dict[int, str]:
    """{pid: command line} for every python process.

    PowerShell's Get-CimInstance, NOT wmic: wmic wraps long command lines at the
    console width, which is what made a running bot look absent and caused the
    duplicate-instance incident this file is built to prevent.
    """
    if platform.system() == "Windows":
        cmd = ["powershell", "-NoProfile", "-NonInteractive", "-Command",
               "Get-CimInstance Win32_Process -Filter \"Name LIKE 'python%'\" | "
               "Select-Object ProcessId,CommandLine | ConvertTo-Json -Compress"]
    else:
        cmd = ["ps", "-eo", "pid=,args="]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=30).stdout
    except Exception:
        return {}
    if platform.system() != "Windows":
        res = {}
        for ln in out.splitlines():
            ln = ln.strip()
            if not ln:
                continue
            pid, _, args = ln.partition(" ")
            try:
                res[int(pid)] = args
            except ValueError:
                pass
        return res
    try:
        data = json.loads(out) if out.strip() else []
    except json.JSONDecodeError:
        return {}
    if isinstance(data, dict):          # ConvertTo-Json emits a bare object for n=1
        data = [data]
    return {int(d["ProcessId"]): (d.get("CommandLine") or "")
            for d in data if d.get("ProcessId")}


def age(p: Path) -> float | None:
    try:
        return time.time() - p.stat().st_mtime
    except OSError:
        return None


def human(s: float | None) -> str:
    if s is None:
        return "never"
    if s < 90:
        return f"{s:.0f}s ago"
    if s < 90 * 60:
        return f"{s / 60:.0f}m ago"
    if s < 48 * H:
        return f"{s / H:.1f}h ago"
    return f"{s / 86400:.1f}d ago"


def rowcount(p: Path) -> int | None:
    try:
        with open(p, encoding="utf-8", errors="replace") as f:
            return max(sum(1 for _ in f) - 1, 0)
    except OSError:
        return None


def read_state(p: Path | None) -> dict:
    if not p:
        return {}
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return {}


def tail(p: Path, n: int) -> list[str]:
    try:
        with open(p, encoding="utf-8", errors="replace") as f:
            return [ln.rstrip("\n") for ln in f.readlines()[-n:]]
    except OSError:
        return []


# ---------------------------------------------------------------------------
def check(bot: dict, live: dict[int, str]) -> dict:
    """Three signals, reported separately. The verdict is derived last."""
    # --- 1. process, by pid file cross-checked against the command line -----
    pid, why = None, ""
    pf = bot.get("pidfile")
    if pf and pf.exists():
        try:
            claimed = int(pf.read_text().strip())
        except (ValueError, OSError):
            claimed = None
        if claimed in live:
            # A pid can be REUSED by an unrelated process after a crash. Without
            # this substring check a stale lock file plus any python process would
            # read as "alive".
            if bot["match"].split(".")[0] in live[claimed]:
                pid, why = claimed, f"pid {claimed}, command line matches"
            else:
                why = f"pid {claimed} is alive but is NOT this bot (recycled pid)"
        elif claimed:
            why = f"lock file claims pid {claimed}, which is gone (stale lock)"
    if pid is None:
        # Fall back to scanning command lines: a bot started without a lock file,
        # or restarted by the Startup launcher under a different pid.
        hits = [q for q, c in live.items() if bot["match"] in c]
        if hits:
            pid = hits[0]
            why = (f"pid {hits[0]} found by command line"
                   + (" (lock file did not point here)" if pf and pf.exists() else ""))
            if len(hits) > 1:
                why += f"  ** {len(hits)} COPIES RUNNING **"
        elif not why:
            why = "no process found"

    # --- 2. heartbeat: the file touched every cycle, not the log -------------
    a = age(bot["beat"])
    fresh = a is not None and a <= bot["beat_max"]

    # --- 3. progress ---------------------------------------------------------
    prog = []
    st = read_state(bot.get("state"))
    if st:
        # xs_paper keeps `equity` as a per-symbol dict, everything else as a float.
        if isinstance(st.get("equity"), (int, float)):
            prog.append(f"equity {st['equity']:.2f}")
        op = st.get("open")
        if isinstance(op, dict):
            prog.append(f"{len(op)} open")
        # mn_paper holds a dollar-neutral basket, not "open positions". xs_paper ALSO has
        # a "weights" key, but its values are per-variant DICTS - hence the numeric guard.
        wt = st.get("weights")
        if isinstance(wt, dict) and wt and all(
                isinstance(v, (int, float)) for v in wt.values()):
            prog.append(f"{sum(1 for v in wt.values() if v > 0)}L/"
                        f"{sum(1 for v in wt.values() if v < 0)}S")
        if "n_rebal" in st:
            prog.append(f"rebal {st['n_rebal']}")
        for k, lab in (("taken", "taken"), ("declined", "declined"),
                       ("too_small", "too small")):
            if k in st:
                prog.append(f"{lab} {st[k]}")
    if bot.get("rows"):
        n = rowcount(bot["rows"])
        if n is not None:
            prog.append(f"{n:,} rows recorded")

    # --- verdict -------------------------------------------------------------
    dup = "COPIES RUNNING" in why
    if dup:
        verdict, colour = "TWO COPIES", "bad"
    elif bot["where"] == "off":
        verdict, colour = ("RUNNING (not expected)", "warn") if pid else ("off", "idle")
    elif bot["where"] == "vm":
        verdict, colour = ("RUNNING HERE TOO", "warn") if pid else ("on the VM", "idle")
    elif pid and fresh:
        verdict, colour = "OK", "good"
    elif pid and not fresh:
        verdict, colour = "WEDGED", "bad"
    elif not pid and fresh:
        verdict, colour = "PROBABLY OK", "warn"
    else:
        verdict, colour = "DEAD", "bad"
    return dict(pid=pid, why=why, age=a, fresh=fresh, prog=prog,
                verdict=verdict, colour=colour)


MARK = {"good": "OK  ", "bad": "FAIL", "warn": "?   ", "idle": "--  "}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vm", metavar="HOST[:PORT]",
                    help="also read the status page on the VM (default port 8080)")
    ap.add_argument("--token", default=os.getenv("STATUS_TOKEN", ""),
                    help="STATUS_TOKEN if the VM status page is protected")
    ap.add_argument("--log", metavar="KEY",
                    help="print the tail of one bot's log: " +
                         ", ".join(b["key"] for b in BOTS))
    ap.add_argument("--lines", type=int, default=25)
    args = ap.parse_args()

    if args.log:
        m = [b for b in BOTS if b["key"] == args.log]
        if not m:
            print(f"unknown key {args.log!r}. "
                  f"one of: {', '.join(b['key'] for b in BOTS)}")
            return 2
        p = m[0]["log"]
        print(f"==== {p}  ({human(age(p))}) ====")
        print("\n".join(tail(p, args.lines)) or "(empty)")
        return 0

    print(f"HEALTH CHECK  {time.strftime('%Y-%m-%d %H:%M:%S')}  on "
          f"{platform.node()}\n")
    live = procs()
    if not live:
        print("  ! could not list processes. Heartbeat freshness still decides below.\n")

    results = []
    for bot in BOTS:
        r = check(bot, live)
        results.append((bot, r))
        print(f"[{MARK[r['colour']]}] {bot['label']}")
        print(f"        process    {r['why']}")
        if bot["where"] == "vm" and not r["pid"]:
            # The local copy of this state file is a LEFTOVER from when the bot ran
            # here. Printing a freshness limit against it would invite exactly the
            # wrong conclusion: the running copy is on the VM and writes its own.
            print(f"        heartbeat  n/a here - local {bot['beat'].name} is a "
                  f"leftover ({human(r['age'])}). Use --vm for the real one.")
        else:
            print(f"        heartbeat  {bot['beat'].name} written {human(r['age'])}"
                  f"   (must be under {human(bot['beat_max'])[:-4].strip()})")
        if r["prog"]:
            print(f"        progress   {' | '.join(r['prog'])}")
        print(f"        verdict    {r['verdict']}   - {bot['note']}")
        print()

    # ---- what to actually do about it --------------------------------------
    print("=" * 78)
    bad = [(b, r) for b, r in results if r["colour"] == "bad"]
    warn = [(b, r) for b, r in results if r["colour"] == "warn"]
    if not bad and not warn:
        print("Nothing needs attention.")
    for b, r in bad:
        if r["verdict"] == "TWO COPIES":
            print(f"! {b['label']}: TWO COPIES RUNNING. Kill all but one NOW - "
                  f"duplicate instances double every order.")
        elif r["verdict"] == "WEDGED":
            print(f"! {b['label']}: process alive but not writing. It holds the "
                  f"lock, so a restart will refuse. Kill pid {r['pid']}, then start it.")
        else:
            print(f"! {b['label']}: not running. Start it - see docs/04-operations.md.")
    for b, r in warn:
        if r["verdict"] == "PROBABLY OK":
            print(f"? {b['label']}: files are fresh but the process list did not show "
                  f"it. Trust the files; do NOT start a second copy.")
        else:
            print(f"? {b['label']}: {r['verdict']}. Expected '{b['where']}'.")

    # ---- the VM, which this machine cannot see any other way ----------------
    if args.vm:
        host = args.vm if ":" in args.vm else f"{args.vm}:8080"
        url = f"http://{host}/" + (f"?t={args.token}" if args.token else "")
        print("\n" + "=" * 78)
        print(f"VM STATUS PAGE  {host}")
        try:
            with urllib.request.urlopen(url, timeout=20) as resp:
                doc = json.load(resp)
        except urllib.error.HTTPError as e:
            print(f"  HTTP {e.code} - {'STATUS_TOKEN needed (pass --token)' if e.code == 403 else e.reason}")
            return 1
        except Exception as e:
            print(f"  unreachable: {type(e).__name__}: {e}")
            print("  Either the status server is down, or inbound TCP 8080 is not "
                  "open in the Azure NSG.")
            return 1
        print(f"  generated {doc.get('generated_utc')} UTC")
        for name, e in doc.get("bots", {}).items():
            t = e.get("trades", {})
            bits = [f"equity {e['equity']:.2f}"] if "equity" in e else []
            if "open_positions" in e:
                bits.append(f"{e['open_positions']} open")
            if t.get("closed"):
                bits.append(f"{t['closed']} closed, win {t.get('win_pct','?')}%, "
                            f"total {t.get('total_R','?')}R")
            print(f"  {name:<18} {' | '.join(bits) or 'no data'}")
            for ln in e.get("recent_log", [])[-2:]:
                print(f"      {ln[:110]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
