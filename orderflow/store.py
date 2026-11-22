"""Raw storage for the order-flow recorder (Module 5).

PRINCIPLE: STORE THE RAW MESSAGES, COMPUTE EVERYTHING OFFLINE. If a feature definition turns out to be wrong, the recording can still be re-read; if only features were
stored, it could not. One line per websocket frame:  <local receive time in ns> TAB <the frame exactly as received>.

LAYOUT: <root>/<pair>/<YYYY-MM-DD>_<HH>.log.gz, one file per pair per UTC hour of the LOCAL RECEIVE time. A file is a gzip stream flushed with Z_SYNC_FLUSH every few
seconds, so a crash (or a power cut) loses at most those seconds and everything before them stays readable even though the gzip trailer was never written.
"""
from __future__ import annotations

import gzip
import json
import time
import zlib
from datetime import datetime, timezone
from pathlib import Path


def hour_key(recv_ns: int) -> str:
    return datetime.fromtimestamp(recv_ns / 1e9, tz=timezone.utc).strftime("%Y-%m-%d_%H")


class RawWriter:
    """Appends frames for ONE pair; rotates to a new file at each UTC hour boundary."""

    def __init__(self, root: Path, name: str, level: int = 3, flush_every_s: float = 5.0, on_rotate=None):
        self.on_rotate = on_rotate                                 # called with recv_ns when a file is opened; may return a frame to write FIRST (a checkpoint)
        self.dir = Path(root) / name
        self.dir.mkdir(parents=True, exist_ok=True)
        self.level, self.flush_every_s = level, flush_every_s
        self.key = None
        self.f = None
        self.last_flush = time.monotonic()
        self.raw_bytes = 0
        self.frames = 0

    def write(self, recv_ns: int, raw) -> None:
        k = hour_key(recv_ns)
        if k != self.key:
            self.close()
            self.f = gzip.GzipFile(self.dir / f"{k}.log.gz", "ab", compresslevel=self.level)    # append: a restart in the same hour adds a new gzip member
            self.key = k
            first = self.on_rotate(recv_ns) if self.on_rotate else None
            if first:
                line0 = f"{recv_ns}\t{first}\n".encode("utf-8")
                self.f.write(line0)
                self.raw_bytes += len(line0)
                self.frames += 1
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        line = f"{recv_ns}\t{raw.replace(chr(10), ' ')}\n".encode("utf-8")
        self.f.write(line)
        self.raw_bytes += len(line)
        self.frames += 1
        if time.monotonic() - self.last_flush >= self.flush_every_s:
            self.flush()

    def flush(self) -> None:
        if self.f is not None:
            self.f.flush(zlib.Z_SYNC_FLUSH)
        self.last_flush = time.monotonic()

    def close(self) -> None:
        if self.f is not None:
            self.f.close()
            self.f = None
            self.key = None

    def disk_bytes(self) -> int:
        return sum(p.stat().st_size for p in self.dir.glob("*.log.gz"))


class EventLog:
    """Everything that is not a market message: connects, disconnects, gaps, audits, clock probes. One JSON object per line, plain text."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, kind: str, **fields) -> None:
        rec = {"t_ns": time.time_ns(), "type": kind, **fields}
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, separators=(",", ":")) + "\n")

    def read(self) -> list:
        if not self.path.exists():
            return []
        out = []
        with open(self.path, encoding="utf-8") as f:
            for line in f:
                try:
                    out.append(json.loads(line))
                except ValueError:
                    pass                                                    # a torn last line after a crash
        return out


def iter_raw(root: Path, name: str, since: str = None):
    """Yield (recv_ns, raw_frame) for one pair in file order (hour by hour); `since` = 'YYYY-MM-DD_HH' skips earlier hours (each hourly file opens with a checkpoint, so a
    book can be rebuilt from the file alone). A file that ends without its gzip trailer (a crash) yields everything flushed before it."""
    for path in sorted((Path(root) / name).glob("*.log.gz")):
        if since and path.name.split(".")[0] < since:
            continue
        try:
            with gzip.open(path, "rt", encoding="utf-8") as f:
                for line in f:
                    t, _, raw = line.rstrip("\n").partition("\t")
                    if raw:
                        yield int(t), raw
        except (EOFError, OSError, zlib.error):
            continue                                                        # ended mid-stream: what was read is kept
