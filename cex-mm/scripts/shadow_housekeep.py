#!/usr/bin/env python3
"""Delete old shadow-test run directories so the VM disk does not fill (about 0.5 GB a day).

A run directory is a direct child of artifacts/shadow/ named like scripts/shadow.sh names it
(`date -u +%Y%m%dT%H%M%SZ`, e.g. 20261006T161427Z). One is deleted when the newest mtime of the
directory and everything in it is older than --days (default 14). Never deleted: the run `current`
points to, a run whose *.pid files name a live process, a run that could not be fully scanned,
symlinks (never followed), and anything not named like a run. If `current` is missing, dangling, not a
symlink, or not pointing at a run directory in the shadow dir, nothing is deleted and the exit code is 2.

Dry run by default; --apply deletes. Deletion is permanent: copy runs off first (docs/VM.md).

    python3 scripts/shadow_housekeep.py                 # report only
    python3 scripts/shadow_housekeep.py --apply         # what cex-mm-shadow-housekeep.service runs
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import stat
import sys
import time
from pathlib import Path

DEFAULT_SHADOW = Path(__file__).resolve().parent.parent / "artifacts" / "shadow"
RUN_RE = re.compile(r"\d{8}T\d{6}Z", re.ASCII)
DAY = 86400.0


class Refuse(Exception):
    """A safety check failed: delete nothing (more)."""


def human(n: float) -> str:
    for unit in ("B", "KiB", "MiB", "GiB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TiB"


def resolve_current(shadow: Path) -> Path:
    """The run directory `current` points to. Refuse unless `current` is a symlink (as shadow.sh makes it)
    to a run-named directory directly in `shadow`; otherwise the live run is unknown."""
    cur = shadow / "current"
    if not os.path.lexists(cur):
        raise Refuse(f"{cur} is missing, so the live run cannot be identified")
    if not cur.is_symlink():
        raise Refuse(f"{cur} is not a symlink (shadow.sh makes one), so the live run cannot be identified")
    try:
        target = cur.resolve(strict=True)
    except (OSError, RuntimeError):
        raise Refuse(f"{cur} is dangling (-> {os.readlink(cur)})") from None
    if not target.is_dir() or target.parent != shadow or not RUN_RE.fullmatch(target.name):
        raise Refuse(f"{cur} resolves to {target}, which is not a run directory in {shadow}")
    return target


def check_deletable(shadow: Path, run: Path, current: Path) -> None:
    """Last check before rmtree: a real run directory directly inside `shadow` that is not `current`."""
    if run.is_symlink():
        raise Refuse(f"{run} is a symlink")
    if not RUN_RE.fullmatch(run.name):
        raise Refuse(f"{run} is not named like a run directory")
    real = run.resolve(strict=True)
    if real.parent != shadow or real != Path(os.path.abspath(run)):
        raise Refuse(f"{run} is not directly inside {shadow}")
    if not real.is_dir():
        raise Refuse(f"{run} is not a directory")
    if real == current or os.path.samefile(real, current):
        raise Refuse(f"{run} is the current run")


def scan(run: Path) -> tuple[float, int, list[str]]:
    """(newest mtime of the dir and anything under it, bytes in regular files, *.pid files). No symlinks followed."""
    newest = run.lstat().st_mtime
    size = 0
    pidfiles: list[str] = []
    errors: list[OSError] = []
    for dirpath, dirnames, filenames in os.walk(run, onerror=errors.append):
        for name in dirnames + filenames:
            path = os.path.join(dirpath, name)
            st = os.lstat(path)
            newest = max(newest, st.st_mtime)
            if stat.S_ISREG(st.st_mode):
                size += st.st_size
                if name.endswith(".pid"):
                    pidfiles.append(path)
    if errors:
        raise errors[0]
    return newest, size, pidfiles


def live_pids(pidfiles: list[str]) -> list[str]:
    """'<pid> <comm> (<file>)' for each pid file that names a running process. A reused pid also keeps the
    run (the safe side); the process name in the log shows when that happened."""
    live = []
    for path in pidfiles:
        try:
            with open(path, encoding="ascii", errors="replace") as f:
                text = f.read(64).strip()
        except OSError:
            continue
        if not (text.isascii() and text.isdigit()) or int(text) <= 0:  # kill(0) would signal our own group
            continue
        pid = int(text)
        try:
            os.kill(pid, 0)
        except PermissionError:
            pass  # exists, owned by another user
        except (OSError, OverflowError):
            continue
        try:
            comm = Path(f"/proc/{pid}/comm").read_text().strip()
        except OSError:
            comm = "?"
        live.append(f"{pid} {comm} ({os.path.basename(path)})")
    return live


def housekeep(shadow_dir: Path, days: int, apply: bool) -> int:
    if not shadow_dir.is_dir():
        raise Refuse(f"{shadow_dir} is not a directory")
    shadow = shadow_dir.resolve(strict=True)
    current = resolve_current(shadow)
    now = time.time()
    cutoff = now - days * DAY

    mode = "apply" if apply else "dry run, pass --apply to delete"
    print(f"shadow housekeep: {shadow}: delete runs older than {days} days ({mode})")
    usage = shutil.disk_usage(shadow)
    print(f"disk free before: {human(usage.free)} of {human(usage.total)}")

    runs = kept = removed = failed = 0
    removed_bytes = 0
    stop = None
    with os.scandir(shadow) as it:
        entries = sorted(it, key=lambda e: e.name)
    for entry in entries:
        name = entry.name
        if not RUN_RE.fullmatch(name):
            continue
        if entry.is_symlink():
            print(f"skip          {name}  symlink, not followed")
            continue
        if not entry.is_dir(follow_symlinks=False):
            print(f"skip          {name}  not a directory")
            continue
        runs += 1
        run = shadow / name
        try:
            newest, size, pidfiles = scan(run)
        except OSError as e:
            kept += 1
            print(f"keep          {name}  could not scan ({e})")
            continue
        if newest > now:  # kept below (newer than cutoff); say why instead of printing a negative age
            age = "newest file in the future (clock skew)"
        else:
            age = f"newest file {(now - newest) / DAY:.1f} days old"
        live = live_pids(pidfiles)
        if run == current:
            why = "current run"
        elif live:
            why = "live pid " + ", ".join(live)
        elif newest > cutoff:
            why = age
        else:
            why = None
        if why:
            kept += 1
            print(f"keep          {name}  {human(size):>10}  {why}")
            continue
        if not apply:
            removed += 1
            removed_bytes += size
            print(f"would-delete  {name}  {human(size):>10}  {age}")
            continue
        try:
            check_deletable(shadow, run, resolve_current(shadow))
        except Refuse as e:
            stop = str(e)
            break
        try:
            shutil.rmtree(run)
        except OSError as e:
            failed += 1
            print(f"FAILED        {name}  {human(size):>10}  {e}")
            continue
        removed += 1
        removed_bytes += size
        print(f"deleted       {name}  {human(size):>10}  {age}")

    verb = "deleted" if apply else "would delete"
    print(f"total: {runs} run dirs, kept {kept}, {verb} {removed} ({human(removed_bytes)})"
          + (f", {failed} failed" if failed else ""))
    usage = shutil.disk_usage(shadow)
    print(f"disk free after: {human(usage.free)} of {human(usage.total)}" + ("" if apply else " (dry run)"))
    if stop:
        print(f"shadow housekeep: stopped before deleting more: {stop}", file=sys.stderr)
        return 2
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    # Under systemd stdout is a pipe to journald and would be block-buffered: run lines would land late,
    # after stderr, or be lost if the oneshot is killed. Flush each line as it is printed.
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is not None:
        reconfigure(line_buffering=True)
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--days", type=int, default=14,
                    help="delete runs whose newest file is older than this many days (default 14, minimum 1)")
    ap.add_argument("--apply", action="store_true", help="actually delete (default: report only)")
    ap.add_argument("--shadow-dir", type=Path, default=DEFAULT_SHADOW, help=f"default {DEFAULT_SHADOW}")
    args = ap.parse_args(argv)
    if args.days < 1:
        ap.error("--days must be at least 1")
    try:
        return housekeep(args.shadow_dir, args.days, args.apply)
    except Refuse as e:
        print(f"shadow housekeep: refusing, nothing deleted: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
