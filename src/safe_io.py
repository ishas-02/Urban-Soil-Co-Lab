"""
safe_io.py — one shared, NFS-safe way to write files on the soil-data volume.

WHY THIS EXISTS
---------------
All five apps AND the hourly SharePoint sync write to the same shared
NetApp (NFS, RWX) volume. Before this module, most writers did a plain
`df.to_csv(path)` or `open(path, "w")`. That has two failure modes:

  1. Torn / partial files — a reader (another app, or the sync job
     uploading to SharePoint) can see a half-written file.
  2. Lost updates — two pods read the same file, each adds its rows,
     and the second write silently erases the first one's rows.

This module fixes both:

  * `data_lock()`     — ONE lock for the whole data volume, shared by every
                        pod. Writers hold it only for the read-modify-write
                        (milliseconds to ~2 s), never for network calls.
  * `atomic_write_*`  — write to a temp file in the same folder, fsync,
                        then os.replace(). Readers see either the old file
                        or the new file, never a mix.

HOW THE LOCK WORKS (and why not fcntl/flock)
--------------------------------------------
POSIX/flock locks over NFS depend on the NFS lock manager being configured
correctly on every node — not something we control on UB CaaS. Creating a
directory with os.mkdir() is atomic on NFS on every version, so we use a
lock DIRECTORY: whoever creates it holds the lock; deleting it releases it.

  * Re-entrant inside one thread (a function holding the lock can call
    another function that also takes it — e.g. xrf-tech save → reconcile).
  * Stale-lock recovery: if a pod is killed while holding the lock, the
    directory is left behind. Any lock older than STALE_SECONDS is broken
    automatically.
  * If the lock can't be taken within WAIT_SECONDS, LockTimeout is raised
    with a plain-English message; nothing has been written at that point,
    so the user can simply click Save again.

The lock directory contains NO files, so the SharePoint sync (which only
walks files) never uploads it. sync_sharepoint.py also excludes `.locks/`
and `.tmp_*` explicitly.
"""
from __future__ import annotations

import contextlib
import csv
import io
import json
import os
import socket
import tempfile
import threading
import time
from pathlib import Path

# ── Settings ──────────────────────────────────────────────────────────────
WAIT_SECONDS = float(os.environ.get("SOIL_LOCK_WAIT", "30"))     # max wait to acquire
STALE_SECONDS = float(os.environ.get("SOIL_LOCK_STALE", "120"))  # break locks older than this
POLL_SECONDS = 0.1
TMP_PREFIX = ".tmp_"                  # sync_sharepoint.py excludes this prefix


def _data_dir() -> Path:
    """The shared volume root. Same resolution order as paths.py."""
    env = os.environ.get("SOIL_DATA_DIR")
    if env:
        return Path(env)
    return Path(__file__).resolve().parent.parent / "data"


def lock_path() -> Path:
    return _data_dir() / ".locks" / "data.lock"


class LockTimeout(RuntimeError):
    """Raised when another save is still running after WAIT_SECONDS."""


# ── The lock ──────────────────────────────────────────────────────────────
_local = threading.local()  # per-thread re-entrancy depth


def _try_break_stale(lp: Path) -> None:
    try:
        age = time.time() - lp.stat().st_mtime
    except FileNotFoundError:
        return
    if age > STALE_SECONDS:
        try:
            os.rmdir(lp)
            print(f"[safe_io] broke stale lock ({age:.0f}s old) on {socket.gethostname()}",
                  flush=True)
        except OSError:
            pass  # someone else broke/re-took it first — fine


@contextlib.contextmanager
def data_lock(wait: float | None = None):
    """Hold the single cross-pod write lock for the data volume.

    Usage:
        with data_lock():
            df = read(...)
            ...modify...
            atomic_write_csv(df, path)
    """
    depth = getattr(_local, "depth", 0)
    if depth > 0:                       # already held by this thread
        _local.depth = depth + 1
        try:
            yield
        finally:
            _local.depth -= 1
        return

    lp = lock_path()
    lp.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + (WAIT_SECONDS if wait is None else wait)
    while True:
        try:
            os.mkdir(lp)                # atomic on NFS
            break
        except FileExistsError:
            _try_break_stale(lp)
            if time.monotonic() >= deadline:
                raise LockTimeout(
                    "Another save is still in progress on the shared data volume. "
                    "Nothing was written — please wait a few seconds and click Save again."
                )
            time.sleep(POLL_SECONDS)

    _local.depth = 1
    try:
        yield
    finally:
        _local.depth = 0
        try:
            os.rmdir(lp)
        except OSError:
            pass


# ── Atomic writers ────────────────────────────────────────────────────────
def atomic_write_bytes(data: bytes, path: str | os.PathLike) -> None:
    """Write bytes so readers never see a partial file."""
    path = os.fspath(path)
    d = os.path.dirname(path) or "."
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=TMP_PREFIX, dir=d)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.remove(tmp)
        raise


def atomic_write_text(text: str, path: str | os.PathLike, encoding: str = "utf-8") -> None:
    atomic_write_bytes(text.encode(encoding), path)


def atomic_write_csv(df, path: str | os.PathLike, **to_csv_kwargs) -> None:
    """Atomic replacement for df.to_csv(path, index=False)."""
    to_csv_kwargs.setdefault("index", False)
    buf = io.StringIO()
    df.to_csv(buf, **to_csv_kwargs)
    atomic_write_text(buf.getvalue(), path)


def atomic_write_json(obj, path: str | os.PathLike, **json_kwargs) -> None:
    json_kwargs.setdefault("indent", 2)
    json_kwargs.setdefault("ensure_ascii", False)
    atomic_write_text(json.dumps(obj, **json_kwargs), path)


def atomic_write_csv_rows(header: list[str], rows, path: str | os.PathLike) -> None:
    """Atomic writer for plain csv.writer-style rows."""
    buf = io.StringIO(newline="")
    w = csv.writer(buf)
    w.writerow(header)
    for r in rows:
        w.writerow(r)
    atomic_write_text(buf.getvalue(), path)
