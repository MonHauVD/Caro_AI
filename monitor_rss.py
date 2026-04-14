#!/usr/bin/env python3
"""Lightweight RSS monitor for a process tree on Linux.

This script is standalone and does not touch game code. It reads /proc to:
- monitor one PID (plus all descendants), or
- auto-detect a PID by command keyword.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import os
import signal
import time
from collections import defaultdict, deque


def _read_int(path: str) -> int | None:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return int(f.read().strip())
    except (OSError, ValueError):
        return None


def rss_kb_of_pid(pid: int) -> int:
    """Return RSS in KB of a PID, 0 if process is missing/unreadable."""
    status_path = f"/proc/{pid}/status"
    try:
        with open(status_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    parts = line.split()
                    if len(parts) >= 2 and parts[1].isdigit():
                        return int(parts[1])
    except OSError:
        return 0
    return 0


def build_ppid_index() -> dict[int, list[int]]:
    """Build parent->children map from /proc."""
    tree: dict[int, list[int]] = defaultdict(list)
    for name in os.listdir("/proc"):
        if not name.isdigit():
            continue
        pid = int(name)
        ppid = _read_int(f"/proc/{pid}/stat")
        if ppid is None:
            # Fallback via /proc/<pid>/status if /stat parse is unavailable.
            try:
                with open(f"/proc/{pid}/status", "r", encoding="utf-8") as f:
                    for line in f:
                        if line.startswith("PPid:"):
                            ppid = int(line.split()[1])
                            break
            except (OSError, ValueError, IndexError):
                ppid = None
        if ppid is not None:
            tree[ppid].append(pid)
    return tree


def descendants_of(root_pid: int, tree: dict[int, list[int]]) -> set[int]:
    """Return root + all descendants currently visible in /proc."""
    seen: set[int] = set()
    q: deque[int] = deque([root_pid])
    while q:
        pid = q.popleft()
        if pid in seen:
            continue
        seen.add(pid)
        for child in tree.get(pid, []):
            if child not in seen:
                q.append(child)
    return seen


def total_rss_kb(root_pid: int) -> tuple[int, int]:
    """Return (total_rss_kb, process_count) for root process tree."""
    tree = build_ppid_index()
    pids = descendants_of(root_pid, tree)
    total = 0
    alive = 0
    for pid in pids:
        rss = rss_kb_of_pid(pid)
        if rss > 0:
            alive += 1
        total += rss
    return total, alive


def pid_exists(pid: int) -> bool:
    return os.path.isdir(f"/proc/{pid}")


def cmdline_of(pid: int) -> str:
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as f:
            raw = f.read().replace(b"\x00", b" ").strip()
            return raw.decode("utf-8", errors="replace")
    except OSError:
        return ""


def find_pid_by_keyword(keyword: str) -> int | None:
    """Find first PID whose cmdline contains keyword, prefer latest start time."""
    candidates: list[tuple[int, int]] = []
    for name in os.listdir("/proc"):
        if not name.isdigit():
            continue
        pid = int(name)
        cmd = cmdline_of(pid)
        if keyword in cmd:
            stat_starttime = _read_starttime_ticks(pid)
            if stat_starttime is not None:
                candidates.append((stat_starttime, pid))
    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][1]


def _read_starttime_ticks(pid: int) -> int | None:
    # /proc/<pid>/stat field #22 (1-indexed), but comm can contain spaces.
    try:
        with open(f"/proc/{pid}/stat", "r", encoding="utf-8") as f:
            s = f.read().strip()
    except OSError:
        return None
    rp = s.rfind(")")
    if rp < 0 or rp + 2 >= len(s):
        return None
    tail = s[rp + 2 :].split()
    if len(tail) < 20:
        return None
    try:
        return int(tail[19])
    except ValueError:
        return None


def format_mib(kb: int) -> str:
    return f"{kb / 1024:.1f} MiB"


def main() -> int:
    parser = argparse.ArgumentParser(description="Monitor RSS of a process tree.")
    parser.add_argument("--pid", type=int, help="Root PID to monitor.")
    parser.add_argument(
        "--find",
        type=str,
        help="Find PID by command keyword (example: 'python main.py --mode benchmark').",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=2.0,
        help="Sampling interval in seconds (default: 2.0).",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=0.0,
        help="Stop after N seconds (0 means run until Ctrl+C/process exits).",
    )
    parser.add_argument(
        "--csv",
        type=str,
        default="",
        help="Optional CSV output file path.",
    )
    args = parser.parse_args()

    if args.pid is None and not args.find:
        parser.error("Provide --pid or --find.")
    if args.pid is not None and args.find:
        parser.error("Use either --pid or --find, not both.")
    if args.interval <= 0:
        parser.error("--interval must be > 0.")

    root_pid = args.pid
    if root_pid is None:
        root_pid = find_pid_by_keyword(args.find)
        if root_pid is None:
            print(f"[rss] cannot find PID with keyword: {args.find!r}")
            return 2
        print(f"[rss] found PID {root_pid} for keyword: {args.find!r}")

    if not pid_exists(root_pid):
        print(f"[rss] PID {root_pid} does not exist.")
        return 2

    stop = False

    def _handle_sigint(_sig, _frame):
        nonlocal stop
        stop = True

    signal.signal(signal.SIGINT, _handle_sigint)

    start = time.time()
    peak_kb = 0
    csv_writer = None
    csv_file = None

    if args.csv:
        csv_file = open(args.csv, "w", newline="", encoding="utf-8")
        csv_writer = csv.writer(csv_file)
        csv_writer.writerow(
            ["timestamp", "elapsed_sec", "root_pid", "proc_count", "rss_kb", "rss_mib"]
        )

    try:
        while not stop:
            if not pid_exists(root_pid):
                print(f"[rss] PID {root_pid} exited.")
                break

            total_kb, count = total_rss_kb(root_pid)
            peak_kb = max(peak_kb, total_kb)
            now = dt.datetime.now().isoformat(timespec="seconds")
            elapsed = time.time() - start

            line = (
                f"{now} | elapsed={elapsed:7.1f}s | procs={count:3d} | "
                f"rss={format_mib(total_kb):>10} | peak={format_mib(peak_kb):>10}"
            )
            print(line)

            if csv_writer is not None:
                csv_writer.writerow(
                    [now, f"{elapsed:.3f}", root_pid, count, total_kb, f"{total_kb / 1024:.3f}"]
                )
                csv_file.flush()

            if args.duration > 0 and elapsed >= args.duration:
                break
            time.sleep(args.interval)
    finally:
        if csv_file is not None:
            csv_file.close()

    print(f"[rss] done. peak RSS(tree) = {format_mib(peak_kb)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
