#!/usr/bin/env python3
"""
wf-rename — Rename all Warfork demos in a folder using header metadata.

Usage:
    python wf-rename.py [folder]          preview renames (dry run)
    python wf-rename.py [folder] --apply  actually rename the files

Naming format:
    player_mapname_Xm00.000s_YYYYMMDD.wfdz22   (when race finish time found)
    player_mapname_YYYYMMDD.wfdz22              (fallback: no finish time)

If [folder] is omitted, the current directory is used.
"""
import os
import re
import sys
from datetime import datetime
from pathlib import Path

TAIL_SIZE = 32768


def parse_header(path):
    try:
        with open(path, "rb") as f:
            data = f.read(512)
    except (IOError, OSError):
        return {}
    start = data.find(b"hostname\x00")
    if start == -1:
        return {}
    result, pos = {}, start
    while pos < len(data):
        nk = data.find(b"\x00", pos)
        if nk <= pos:
            break
        key = data[pos:nk].decode("latin-1", errors="replace")
        pos = nk + 1
        nv = data.find(b"\x00", pos)
        if nv == -1:
            break
        val = data[pos:nv].decode("latin-1", errors="replace")
        result[key] = val
        pos = nv + 1
        if pos < len(data) and data[pos:pos+1] == b"\x00":
            break
    return result


def find_player_name(path):
    try:
        with open(path, "rb") as f:
            data = f.read(65536)
    except (IOError, OSError):
        return None
    match = re.search(rb"\\name\\([^\\\"\\x00]+)", data)
    if not match:
        return None
    name = match.group(1).decode("latin-1", errors="replace")
    return re.sub(r"\^.", "", name)


def find_finish_time(path):
    try:
        with open(path, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(-min(TAIL_SIZE, size), 2)
            tail = f.read()
    except (IOError, OSError):
        return None
    tail_clean = re.sub(rb"\^.", b"", tail)
    match = re.search(rb"End: (\d{2}:\d{2}\.\d{3})", tail_clean)
    if not match:
        return None
    time_str = match.group(1).decode("ascii")
    m = re.match(r"(\d+):(\d{2})\.(\d{3})", time_str)
    if not m:
        return None
    mins, secs, ms = int(m.group(1)), int(m.group(2)), m.group(3)
    return f"{mins}m{secs:02d}.{ms}s"


def fmt_date(ts_str, fallback_path=None):
    try:
        ts = int(ts_str)
        if ts > 0:
            return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
    except (ValueError, TypeError, OSError):
        pass
    if fallback_path:
        try:
            return datetime.fromtimestamp(Path(fallback_path).stat().st_mtime).strftime("%Y-%m-%d")
        except OSError:
            pass
    return "unknown"


def sanitize(name):
    return re.sub(r"[^a-zA-Z0-9_-]", "_", name)


def make_filename(path):
    path = Path(path)
    ext = "".join(path.suffixes)
    info = parse_header(path)
    mapname    = sanitize(info.get("mapname") or path.stem)
    date       = fmt_date(info.get("localtime", "0"), fallback_path=path)
    race_time  = find_finish_time(path)
    player     = sanitize(find_player_name(path) or "unknown")
    dt         = date.replace("-", "")
    prefix     = f"{player}_{mapname}" if player else mapname
    if race_time:
        return f"{prefix}_{race_time}_{dt}{ext}"
    return f"{prefix}_{dt}{ext}"


def main():
    args = sys.argv[1:]
    apply = "--apply" in args
    args  = [a for a in args if a != "--apply"]

    folder = Path(args[0]) if args else Path(".")
    if not folder.is_dir():
        print(f"Error: not a directory: {folder}", file=sys.stderr)
        sys.exit(1)

    demos = sorted(folder.glob("*.wfdz*"))
    if not demos:
        print(f"No .wfdz* files found in {folder.resolve()}")
        sys.exit(0)

    if not apply:
        print(f"Dry run — {len(demos)} demo(s) in {folder.resolve()}")
        print("Run with --apply to rename.\n")

    conflicts, renamed, skipped = 0, 0, 0

    for src in demos:
        new_name = make_filename(src)
        dst = src.parent / new_name
        if src.name == new_name:
            print(f"  skip  {src.name}  (already named correctly)")
            skipped += 1
            continue
        if dst.exists():
            print(f"  CONFLICT  {src.name}  →  {new_name}  (target exists, skipping)")
            conflicts += 1
            continue
        print(f"  {'rename' if apply else 'would rename'}  {src.name}  →  {new_name}")
        if apply:
            src.rename(dst)
            renamed += 1

    print()
    if apply:
        print(f"Done: {renamed} renamed, {skipped} skipped, {conflicts} conflict(s).")
    else:
        print(f"Preview: {len(demos) - skipped - conflicts} would rename, {skipped} already correct, {conflicts} conflict(s).")


if __name__ == "__main__":
    main()
