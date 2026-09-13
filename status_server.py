"""READ-ONLY STATUS PAGE — so results can be checked remotely after deployment.

WHAT IT EXPOSES
    A single JSON document built from the bots' own state files and trade CSVs:
    equity, open positions, closed-trade stats, and the counters that matter for a
    small account (orders skipped for the exchange minimum, entries declined for
    lack of margin or slots).

WHAT IT DOES NOT EXPOSE, BY CONSTRUCTION
    * no API keys - it never reads the environment, only files under logs/
    * no order placement, no writes of any kind. Every handler is GET-only and the
      only filesystem access is reading a fixed list of known paths.
    * nothing from the real-money config. Paper state files only unless --include-demo
      is passed.

SECURITY NOTES, because this binds a public port on a cloud box
    * Oracle's default security list blocks inbound ports. You must open the port
      deliberately, which is the right default.
    * Bind to 0.0.0.0 only if you want it reachable; use 127.0.0.1 plus an SSH
      tunnel if you would rather not expose it at all.
    * Set STATUS_TOKEN and the page requires ?t=<token>. Without it, anyone who
      finds the IP can read your paper equity curve. That is not catastrophic, but
      it is yours.

    python status_server.py --port 8080
    curl http://<vm-ip>:8080/            -> JSON summary
    curl http://<vm-ip>:8080/?t=SECRET   -> when STATUS_TOKEN is set
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
LOGS = ROOT / "logs"
TOKEN = os.getenv("STATUS_TOKEN", "")

# fixed allow-list of readable files. Nothing outside this is ever opened.
SOURCES = {
    # THE VALIDATED CONFIGURATION — $221, 12 coins, 1h+4h+12h. Listed first because
    # it is the one whose numbers mean anything; the others are older
    # single-timeframe tests kept for comparison.
    "blend_paper": dict(state=LOGS / "blend_state.json",
                        trades=LOGS / "trades_blend.csv",
                        log=LOGS / "blend_paper.log"),
    # Polymarket calibration forward test. No state file — the CSV of snapshots IS
    # the state, and it is served as `trades` so the same reader handles it.
    "poly_forward": dict(state=LOGS / "poly_snapshots.csv",
                         trades=LOGS / "poly_snapshots.csv",
                         log=LOGS / "poly_forward.log"),
    "longtrend_paper": dict(state=LOGS / "ltp_state.json",
                            trades=LOGS / "trades_ltpaper.csv",
                            log=LOGS / "longtrend_paper.log"),
    "xs_paper": dict(state=LOGS / "xsp_state.json",
                     trades=LOGS / "xsp_rebalances.csv",
                     log=LOGS / "xs_paper.log"),
    "vsa_forward": dict(state=LOGS / "vsaf_state.json",
                        trades=LOGS / "vsaf_trades.csv",
                        log=LOGS / "vsa_forward.log"),
}
DEMO = {"longtrend_demo": dict(state=LOGS / "longtrend_state.json",
                               trades=LOGS / "trades_longtrend.csv",
                               log=LOGS / "longtrend.log")}


def tail(p: Path, n: int = 12) -> list[str]:
    try:
        with open(p, encoding="utf-8", errors="replace") as f:
            return [ln.rstrip("\n") for ln in f.readlines()[-n:]]
    except Exception:
        return []


def trade_stats(p: Path) -> dict:
    try:
        rows = [ln.strip().split(",") for ln in
                open(p, encoding="utf-8").read().strip().splitlines()]
    except Exception:
        return {"closed": 0}
    if len(rows) < 2:
        return {"closed": 0}
    hdr, body = rows[0], rows[1:]
    out = {"closed": len(body)}
    if "R" in hdr:
        i = hdr.index("R")
        rs = []
        for r in body:
            try:
                rs.append(float(r[i]))
            except (ValueError, IndexError):
                pass
        if rs:
            wins = [x for x in rs if x > 0]
            out.update(mean_R=round(sum(rs) / len(rs), 4),
                       total_R=round(sum(rs), 2),
                       win_pct=round(len(wins) / len(rs) * 100, 1),
                       best_R=round(max(rs), 2), worst_R=round(min(rs), 2))
    return out


def snapshot(include_demo: bool) -> dict:
    srcs = dict(SOURCES)
    if include_demo:
        srcs.update(DEMO)
    out = {"generated_utc": f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}",
           "bots": {}}
    for name, paths in srcs.items():
        entry: dict = {}
        try:
            st = json.load(open(paths["state"]))
            # only fields that are safe and useful; never dump the whole state
            for k in ("equity", "started", "taken", "declined", "too_small",
                      "no_margin", "n_rebal"):
                if k in st:
                    entry[k] = st[k]
            op = st.get("open", {})
            entry["open_positions"] = len(op) if isinstance(op, dict) else 0
            entry["open_symbols"] = sorted(op)[:12] if isinstance(op, dict) else []
        except Exception as e:
            entry["state"] = f"unavailable ({type(e).__name__})"
        entry["trades"] = trade_stats(paths["trades"])
        entry["recent_log"] = tail(paths["log"], 10)
        out["bots"][name] = entry
    return out


class Handler(BaseHTTPRequestHandler):
    include_demo = False

    def _deny(self, code: int, msg: str):
        body = json.dumps({"error": msg}).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        if TOKEN:
            got = parse_qs(u.query).get("t", [""])[0]
            if got != TOKEN:
                self._deny(403, "STATUS_TOKEN required as ?t=")
                return
        try:
            body = json.dumps(snapshot(self.include_demo),
                              indent=1).encode("utf-8")
        except Exception as e:
            self._deny(500, f"{type(e).__name__}: {e}")
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    # every other verb is refused - this service is read-only
    def do_POST(self):
        self._deny(405, "read-only")

    do_PUT = do_DELETE = do_PATCH = do_POST

    def log_message(self, fmt, *a):
        pass            # don't spam the journal with every poll


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--bind", default="0.0.0.0",
                    help="127.0.0.1 to keep it local (use an SSH tunnel)")
    ap.add_argument("--include-demo", action="store_true",
                    help="also report the Bitget demo bot")
    args = ap.parse_args()
    Handler.include_demo = args.include_demo
    print(f"status server on {args.bind}:{args.port}  "
          f"token={'SET' if TOKEN else 'NONE (open to anyone who finds the IP)'}",
          flush=True)
    ThreadingHTTPServer((args.bind, args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
