#!/usr/bin/env python3
"""
wf-tools — Warfork demo archive + map favorites CLI (Windows)
https://github.com/mikul-/wf-tools

Run setup first:  python wf-tools.py --setup
Then:             python wf-tools.py
Or via launcher:  wf-tools.bat
"""
import os
import re
import sys
import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

# ── Constants ──────────────────────────────────────────────────────────────────
APPID   = 671610
WF_MOD  = "racemod_2.1"
TAIL_SIZE = 32768


# ── Config ─────────────────────────────────────────────────────────────────────
def _get_documents_folder():
    """Return the real Documents folder via the Windows Shell API (handles relocated/renamed folders)."""
    try:
        import ctypes, ctypes.wintypes
        buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
        ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buf)  # CSIDL_PERSONAL = 5
        p = Path(buf.value)
        if p.exists():
            return p
    except Exception:
        pass
    home = Path.home()
    for sub in ("Documents", "My Documents"):
        d = home / sub
        if d.exists():
            return d
    return home / "Documents"


def _default_demo_dir():
    return _get_documents_folder() / "My Games" / "Warfork 2.1" / WF_MOD / "demos"


def _default_archive_dir():
    return _get_documents_folder() / "wf-demos"


def _config_path():
    appdata = os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))
    return Path(appdata) / "wf-demos" / "config"


def load_config():
    cfg = {
        "DEMO_DIR":    str(_default_demo_dir()),
        "ARCHIVE_DIR": str(_default_archive_dir()),
        "APPID":       str(APPID),
        "WF_MOD":      WF_MOD,
    }
    path = _config_path()
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                cfg[k.strip()] = v.strip()
    return cfg


# ── Demo parser ────────────────────────────────────────────────────────────────
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
    match = re.search(rb'\\name\\([^\\"\x00]+)', data)
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


def fmt_duration(secs_str):
    try:
        s = int(float(secs_str))
    except (ValueError, TypeError):
        return "?m??s"
    return f"{s // 60}m{s % 60:02d}s"


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


def get_demo_info(path):
    path = Path(path)
    info       = parse_header(path)
    mapname    = info.get("mapname") or path.stem
    duration   = fmt_duration(info.get("duration", "0"))
    date       = fmt_date(info.get("localtime", "0"), fallback_path=path)
    race_time  = find_finish_time(path)
    player     = find_player_name(path) or "unknown"
    time_disp  = race_time if race_time else f"~{duration}"
    return {
        "filename":   path.name,
        "path":       path,
        "mapname":    mapname,
        "time_disp":  time_disp,
        "date":       date,
        "race_time":  race_time or "",
        "player":     player,
    }


# ── UI helpers ─────────────────────────────────────────────────────────────────
def pick(items, prompt="Select", label_fn=str):
    """Numbered picker. Returns selected item or None on cancel/empty."""
    if not items:
        return None
    for i, item in enumerate(items, 1):
        print(f"  {i:>3}.  {label_fn(item)}")
    print()
    try:
        raw = input(f"{prompt} [1-{len(items)}, q=cancel]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return None
    if raw in ("q", ""):
        return None
    try:
        idx = int(raw) - 1
        if 0 <= idx < len(items):
            return items[idx]
    except ValueError:
        pass
    print("Invalid selection.")
    return None


def confirm(prompt):
    try:
        return input(f"{prompt} [y/N]: ").strip().lower() == "y"
    except (EOFError, KeyboardInterrupt):
        return False


def _copy_to_clipboard(text):
    if sys.platform == "win32":
        result = subprocess.run(["clip"], input=text, text=True, capture_output=True)
        if result.returncode == 0:
            print(f"  Copied to clipboard: {text}")
        else:
            print(f"  Clipboard copy failed. Map name: {text}")
        return
    for cmd, args in [
        ("wl-copy", []),
        ("xclip", ["-selection", "clipboard"]),
        ("xsel", ["-b"]),
    ]:
        if shutil.which(cmd):
            result = subprocess.run([cmd, *args], input=text, text=True, capture_output=True)
            if result.returncode == 0:
                print(f"  Copied to clipboard: {text}")
                return
    print(f"  No clipboard tool found. Map name: {text}")


def sanitize(name):
    return re.sub(r"[^a-zA-Z0-9_-]", "_", name)


def make_filename(info, ext):
    player  = sanitize(info["player"])
    mapname = sanitize(info["mapname"])
    dt      = info["date"].replace("-", "")
    prefix  = f"{player}_{mapname}" if player else mapname
    if info["race_time"]:
        return f"{prefix}_{info['race_time']}_{dt}{ext}"
    return f"{prefix}_{dt}{ext}"


def demo_label(info):
    return f"{info['filename']:<22}  {info['mapname']:<34}  {info['time_disp']:<12}  {info['date']}"


# ── Steam ──────────────────────────────────────────────────────────────────────
def find_steam():
    if sys.platform == "win32":
        try:
            import winreg
            for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
                for sub in (r"SOFTWARE\WOW6432Node\Valve\Steam", r"SOFTWARE\Valve\Steam"):
                    try:
                        key = winreg.OpenKey(root, sub)
                        path, _ = winreg.QueryValueEx(key, "InstallPath")
                        exe = Path(path) / "steam.exe"
                        if exe.exists():
                            return exe
                    except (FileNotFoundError, OSError):
                        continue
        except ImportError:
            pass
    for candidate in (
        Path("C:/Program Files (x86)/Steam/steam.exe"),
        Path("C:/Program Files/Steam/steam.exe"),
    ):
        if candidate.exists():
            return candidate
    return None


def launch_demo(demo_dir, src_path, appid, mod):
    ext = "".join(src_path.suffixes)
    tmp = demo_dir / f"play_tmp{ext}"
    shutil.copy2(src_path, tmp)
    steam = find_steam()
    if steam is None:
        print("Steam not found. Copy the demo manually to your demos folder and launch it from the game.")
        return
    subprocess.Popen([str(steam), "-applaunch", str(appid), "+set", "fs_game", mod, "+demo", "play_tmp"])
    print(f"Playing: {src_path.name}")


# ── Commands ───────────────────────────────────────────────────────────────────
def cmd_save(demo_dir, favorites):
    demos = sorted(demo_dir.glob("run_*.wfdz*"))
    if not demos:
        print(f"\nNo run_*.wfdz* demos found in:\n  {demo_dir}")
        print("Join a race server to start recording.")
        return

    infos = [get_demo_info(d) for d in demos]
    favorites.mkdir(parents=True, exist_ok=True)

    print("\n── Rolling buffer ──────────────────────────────────────────────────")
    print(f"  {'slot':<22}  {'map':<34}  {'time':<12}  recorded")
    print()
    info = pick(infos, prompt="Save demo", label_fn=demo_label)
    if info is None:
        return

    ext  = "".join(info["path"].suffixes)
    dest = favorites / make_filename(info, ext)

    if dest.exists():
        print(f"Already exists: {dest.name}")
        if not confirm("Overwrite?"):
            return

    shutil.copy2(info["path"], dest)
    print(f"Saved: {dest}")


def cmd_list(demo_dir, favorites, trash, appid, mod):
    while True:
        favs = sorted(favorites.glob("*.wfdz*"))
        if not favs:
            print(f"\nNo favorites in {favorites}")
            return

        infos = [get_demo_info(f) for f in favs]

        print("\n── Favorites ───────────────────────────────────────────────────────")
        print(f"  {'file':<22}  {'map':<34}  {'time':<12}  recorded")
        print()
        info = pick(infos, prompt="Select demo", label_fn=demo_label)
        if info is None:
            return

        print(f"\n  {info['filename']}")
        print("    1. Play")
        print("    2. Move to trash")
        print("    q. Back")
        try:
            action = input("  Action: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return

        if action == "1":
            launch_demo(demo_dir, info["path"], appid, mod)
            return
        elif action == "2":
            trash.mkdir(parents=True, exist_ok=True)
            shutil.move(str(info["path"]), trash / info["filename"])
            print(f"Moved to trash: {info['filename']}")


def cmd_play(demo_dir, name, appid, mod):
    stem = re.sub(r"\.wfdz.*$", "", name)
    matches = list(demo_dir.glob(f"{stem}.wfdz*"))
    if not matches:
        print(f"Demo not found: {demo_dir / stem}.wfdz*")
        sys.exit(1)
    launch_demo(demo_dir, matches[0], appid, mod)


def cmd_clear_temp(trash):
    files = sorted(trash.glob("*.wfdz*"))
    if not files:
        print("Trash is empty.")
        return
    print("Trash contents:")
    for f in files:
        print(f"  {f.name}")
    print()
    if confirm(f"Permanently delete {len(files)} file(s)?"):
        for f in files:
            f.unlink()
        print("Trash cleared.")


# ── Map favorites ──────────────────────────────────────────────────────────────
MAP_PREDEFINED = ["rl", "pg", "gl", "slick", "strafe"]

try:
    from wf_detector import suggest_tags as _auto_suggest_weapons
except ImportError:
    _auto_suggest_weapons = None


def _load_maps(archive_dir):
    path = Path(archive_dir) / "maps.json"
    if path.exists():
        try:
            with open(path, "r") as f:
                data = json.load(f)
            return data.get("maps", []), path
        except (json.JSONDecodeError, IOError):
            pass
    return [], path


def _save_maps(maps, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump({"maps": maps}, f, indent=2)
        f.write("\n")


def _find_map(maps, name):
    for i, m in enumerate(maps):
        if m["name"] == name:
            return i, m
    return None, None


def _auto_suggest(mapname):
    if _auto_suggest_weapons is not None:
        return _auto_suggest_weapons(mapname)

    suggested = set()
    MAP_AUTO_DETECT = [
        (re.compile(r"rl|rocket", re.IGNORECASE), "rl"),
        (re.compile(r"\bpg\b|plasma", re.IGNORECASE), "pg"),
        (re.compile(r"\bgl\b|nade|grenade", re.IGNORECASE), "gl"),
        (re.compile(r"slick|sl1ck|s1ick", re.IGNORECASE), "slick"),
    ]
    for pattern, tag in MAP_AUTO_DETECT:
        if pattern.search(mapname):
            suggested.add(tag)
    if not suggested:
        suggested.add("strafe")
    return sorted(suggested)


def _tag_prompt(mapname, current_tags=None):
    tags = set(current_tags) if current_tags else set(_auto_suggest(mapname))

    while True:
        print(f"\n  Map: {mapname}")
        print(f"  Current tags: {', '.join(sorted(tags)) if tags else '(none)'}")
        print()
        print("  Predefined tags (toggle with number):")
        for i, tag in enumerate(MAP_PREDEFINED, 1):
            mark = "x" if tag in tags else " "
            print(f"    {i}. [{mark}] {tag}")
        print()
        print("  Commands:")
        print("    <number>  — toggle predefined tag")
        print("    +<tag>    — add custom tag")
        print("    -<tag>    — remove tag")
        print("    =/enter   — done, save")
        print("    q         — cancel")
        try:
            raw = input("\n  > ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return None

        if raw in ("", "="):
            if tags:
                return sorted(tags)
            print("  At least one tag is required.")
            continue

        if raw.lower() == "q":
            return None

        if raw.startswith("+"):
            tag = raw[1:].strip().lower()
            if tag:
                tags.add(tag)
            continue

        if raw.startswith("-"):
            tag = raw[1:].strip().lower()
            tags.discard(tag)
            continue

        try:
            idx = int(raw) - 1
            if 0 <= idx < len(MAP_PREDEFINED):
                tag = MAP_PREDEFINED[idx]
                if tag in tags:
                    tags.discard(tag)
                else:
                    tags.add(tag)
                continue
        except ValueError:
            pass

        print("  Invalid input.")


def cmd_maps_save(demo_dir, archive_dir):
    demos = sorted(Path(demo_dir).glob("run_*.wfdz*"))
    if not demos:
        print(f"\nNo run_*.wfdz* demos found in:\n  {demo_dir}")
        print("Join a race server to start recording.")
        return

    infos = [get_demo_info(d) for d in demos]

    print("\n── Rolling buffer ──────────────────────────────────────────────────")
    print(f"  {'':>3}  {'map':<40}")
    print()
    info = pick(infos, prompt="Save map from demo",
                label_fn=lambda i: f"{i['mapname']:<40}")
    if info is None:
        return

    mapname = info["mapname"]
    maps, path = _load_maps(archive_dir)

    _, existing = _find_map(maps, mapname)
    if existing:
        print(f"\n  '{mapname}' is already in favorites with tags: {', '.join(existing['tags'])}")
        if not confirm("  Edit tags?"):
            return
        tags = _tag_prompt(mapname, existing["tags"])
    else:
        tags = _tag_prompt(mapname)

    if tags is None:
        print("  Cancelled.")
        return

    if existing:
        existing["tags"] = tags
        print(f"\n  Updated '{mapname}' tags: {', '.join(tags)}")
    else:
        maps.append({
            "name": mapname,
            "tags": tags,
            "date_added": datetime.now().strftime("%Y-%m-%d"),
        })
        maps.sort(key=lambda m: m["name"])
        print(f"\n  Added '{mapname}' with tags: {', '.join(tags)}")

    _save_maps(maps, path)


def cmd_maps_list(archive_dir):
    while True:
        maps, _ = _load_maps(archive_dir)
        if not maps:
            print("\nNo maps in favorites.")
            return

        filter_options = ["all", "rl", "pg", "gl", "slick", "strafe", ".. back"]
        print("\n── Filter by tag ───────────────────────────────────────────────────")
        tag_choice = pick(filter_options, prompt="Filter", label_fn=str)
        if tag_choice is None or tag_choice == ".. back":
            return

        filtered = maps
        if tag_choice != "all":
            filtered = [m for m in maps if tag_choice in m["tags"]]

        if not filtered:
            print("\nNo maps match that tag.")
            try:
                input("Press Enter to continue...")
            except (EOFError, KeyboardInterrupt):
                pass
            continue

        def map_label(m):
            return f"{m['name']:<40} - {', '.join(m['tags'])}"

        print(f"\n── Maps ({tag_choice}) ──────────────────────────────────────────────────")
        info = pick(filtered, prompt="Select map", label_fn=map_label)
        if info is None:
            continue

        print(f"\n  {info['name']}")
        print("    1. Copy map name to clipboard")
        print("    2. Edit tags")
        print("    3. Remove from favorites")
        print("    q. Back")
        try:
            action = input("  Action: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            continue

        if action == "1":
            _copy_to_clipboard(info["name"])
        elif action == "2":
            new_tags = _tag_prompt(info["name"], info["tags"])
            if new_tags is None:
                print("  Cancelled.")
                continue
            info["tags"] = new_tags
            _save_maps(maps, _load_maps(archive_dir)[1])
            print(f"\n  Updated '{info['name']}' tags: {', '.join(new_tags)}")
        elif action == "3":
            if confirm(f"  Remove '{info['name']}'?"):
                maps.remove(info)
                maps_path = _load_maps(archive_dir)[1]
                _save_maps(maps, maps_path)
                print(f"  Removed '{info['name']}'.")


def cmd_maps_menu(demo_dir, archive_dir):
    options = ["list favorites", "save map to favorites", ".. back"]
    print("\n── Maps ────────────────────────────────────────────────────────────")
    choice = pick(options, prompt="Choose", label_fn=str)
    if choice == "list favorites":
        cmd_maps_list(archive_dir)
    elif choice == "save map to favorites":
        cmd_maps_save(demo_dir, archive_dir)


def cmd_menu(demo_dir, favorites, trash, archive_dir, appid, mod):
    while True:
        options = ["demos", "maps"]
        print("\n── wf-tools ────────────────────────────────────────────────────────")
        choice = pick(options, prompt="Choose", label_fn=str)
        if choice is None:
            return
        if choice == "demos":
            _cmd_demos_menu(demo_dir, favorites, trash, appid, mod)
        elif choice == "maps":
            cmd_maps_menu(demo_dir, archive_dir)


def _cmd_demos_menu(demo_dir, favorites, trash, appid, mod):
    options = ["save", "list favorites", "clear temp", ".. back"]
    print("\n── Demos ───────────────────────────────────────────────────────────")
    choice = pick(options, prompt="Choose", label_fn=str)
    if choice == "save":
        cmd_save(demo_dir, favorites)
    elif choice == "list favorites":
        cmd_list(demo_dir, favorites, trash, appid, mod)
    elif choice == "clear temp":
        cmd_clear_temp(trash)


# ── Setup wizard ───────────────────────────────────────────────────────────────
AUTOEXEC_BLOCK = """\
// ── wf-demos BEGIN ─────────────────────────────────────────────────────
// Demo auto-cycling — wf-demos system
// join keys  = stop current demo + join server + start new slot
// pm keys    = stop current demo + practice mode (no new recording)
// Slot counter resets to 0 each time Warfork starts.
// Manage demos with: wf-demos

set dslot_cmd "demo_slot_0"

alias demo_slot_0 "stop; join; record run_00; set dslot_cmd demo_slot_1; echo ^2[wf-demos]^7 recording run_00"
alias demo_slot_1 "stop; join; record run_01; set dslot_cmd demo_slot_2; echo ^2[wf-demos]^7 recording run_01"
alias demo_slot_2 "stop; join; record run_02; set dslot_cmd demo_slot_3; echo ^2[wf-demos]^7 recording run_02"
alias demo_slot_3 "stop; join; record run_03; set dslot_cmd demo_slot_4; echo ^2[wf-demos]^7 recording run_03"
alias demo_slot_4 "stop; join; record run_04; set dslot_cmd demo_slot_5; echo ^2[wf-demos]^7 recording run_04"
alias demo_slot_5 "stop; join; record run_05; set dslot_cmd demo_slot_6; echo ^2[wf-demos]^7 recording run_05"
alias demo_slot_6 "stop; join; record run_06; set dslot_cmd demo_slot_7; echo ^2[wf-demos]^7 recording run_06"
alias demo_slot_7 "stop; join; record run_07; set dslot_cmd demo_slot_8; echo ^2[wf-demos]^7 recording run_07"
alias demo_slot_8 "stop; join; record run_08; set dslot_cmd demo_slot_9; echo ^2[wf-demos]^7 recording run_08"
alias demo_slot_9 "stop; join; record run_09; set dslot_cmd demo_slot_0; echo ^2[wf-demos]^7 recording run_09"

alias pm_stop "stop; practicemode"

{join_binds}
{pm_binds}
// ── wf-demos END ───────────────────────────────────────────────────────"""


def _build_binds(raw, action):
    lines = []
    for key in raw.split(","):
        key = key.strip()
        if key:
            lines.append(f'bind {key}   "{action}"')
    return "\n".join(lines)


def _merge_autoexec(cfg_path, block):
    BEGIN = "// ── wf-demos BEGIN"
    END   = "// ── wf-demos END"
    existing = cfg_path.read_text(encoding="utf-8", errors="replace") if cfg_path.exists() else ""
    if BEGIN in existing:
        result = re.sub(
            r"// ── wf-demos BEGIN.*?// ── wf-demos END[^\n]*",
            block,
            existing,
            flags=re.DOTALL,
        )
    else:
        result = existing.rstrip("\n") + ("\n\n" if existing else "") + block + "\n"
    cfg_path.write_text(result, encoding="utf-8")


def cmd_setup():
    print("\n╔══════════════════════════════╗")
    print("║    wf-tools setup (Windows)   ║")
    print("╚══════════════════════════════╝\n")

    def ask(prompt, default):
        try:
            val = input(f"{prompt}\n  [{default}]: ").strip()
        except (EOFError, KeyboardInterrupt):
            sys.exit(0)
        return val or default

    # 1. Demo dir
    print("── Warfork demos directory ─────────────────────────────────────────")
    print("   Where Warfork stores recorded demo files.")
    demo_dir = Path(ask("Demo directory", str(_default_demo_dir())))

    # 2. Archive dir
    print("\n── Archive directory ────────────────────────────────────────────────")
    print("   favorites/ and trash/ will be created here.")
    archive_dir = Path(ask("Archive directory", str(_default_archive_dir())))

    # 3. Join binds
    print("\n── Join keybinds ────────────────────────────────────────────────────")
    print("   Keys that stop the demo, join the server, and start a new slot.")
    print("   Comma-separated Warfork key names (e.g. 4, F3, ENTER).")
    join_raw = ask("Join keybinds", "4,F3")

    # 4. PM binds
    print("\n── Practice mode keybinds ───────────────────────────────────────────")
    print("   Keys that stop the demo and enter practice mode (no recording).")
    pm_raw = ask("Practice mode keybinds", "1,F5,F11")

    # Summary
    cfg_file  = demo_dir.parent / "autoexec.cfg"
    print(f"\n── Summary ──────────────────────────────────────────────────────────")
    print(f"  Demo dir:     {demo_dir}")
    print(f"  Archive dir:  {archive_dir}")
    print(f"  Join binds:   {join_raw}")
    print(f"  PM binds:     {pm_raw}")
    print(f"  Warfork cfg:  {cfg_file}")
    if not confirm("\nContinue?"):
        print("Aborted.")
        return

    # Write autoexec.cfg
    block = AUTOEXEC_BLOCK.format(
        join_binds=_build_binds(join_raw, "vstr dslot_cmd"),
        pm_binds=_build_binds(pm_raw, "pm_stop"),
    )
    cfg_file.parent.mkdir(parents=True, exist_ok=True)
    if cfg_file.exists():
        print(f"\nExisting autoexec.cfg found: {cfg_file}")
        print("  1. Merge  (insert/replace wf-demos block, keep the rest)")
        print("  2. Print  (show the block for manual copy-paste)")
        print("  3. Skip")
        try:
            choice = input("  [1/2/3]: ").strip()
        except (EOFError, KeyboardInterrupt):
            choice = "3"
        if choice == "1":
            _merge_autoexec(cfg_file, block)
            print(f"Merged: {cfg_file}")
        elif choice == "2":
            print("\n──── wf-demos autoexec block ────")
            print(block)
            print("─────────────────────────────────")
        else:
            print("Skipped autoexec.cfg.")
    else:
        cfg_file.write_text(block + "\n", encoding="utf-8")
        print(f"Written: {cfg_file}")

    # Write config
    config_path = _config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        f"# wf-demos config — edit as needed\n"
        f"DEMO_DIR={demo_dir}\n"
        f"ARCHIVE_DIR={archive_dir}\n"
        f"APPID={APPID}\n"
        f"WF_MOD={WF_MOD}\n",
        encoding="utf-8",
    )
    print(f"Config:  {config_path}")

    # Create archive dirs
    (archive_dir / "favorites").mkdir(parents=True, exist_ok=True)
    (archive_dir / "trash").mkdir(parents=True, exist_ok=True)
    print(f"Created: {archive_dir / 'favorites'}")
    print(f"Created: {archive_dir / 'trash'}")

    print("\nDone! Launch Warfork and press your join bind to start recording.")
    print("Run  wf-tools.bat  (or  python wf-tools.py)  to manage demos.\n")


# ── Entry point ────────────────────────────────────────────────────────────────
def main():
    args = sys.argv[1:]

    if args and args[0] in ("--setup", "setup"):
        cmd_setup()
        return

    if args and args[0] in ("-h", "--help", "help"):
        print(__doc__)
        print("Commands:")
        print("  (none) / menu    interactive menu (demos / maps)")
        print("  save             pick a rolling buffer slot → save to favorites")
        print("  list             browse favorites (play or trash)")
        print("  play <slot>      play a slot directly (e.g. run_05)")
        print("  clear-temp       permanently delete trashed demos")
        print("  maps-save        pick a demo → save map name + tags to maps.json")
        print("  maps-list        browse map favorites (filter by tag)")
        print("  --setup          run the setup wizard")
        return

    cfg       = load_config()
    demo_dir  = Path(cfg["DEMO_DIR"])
    archive   = Path(cfg["ARCHIVE_DIR"])
    favorites = archive / "favorites"
    trash     = archive / "trash"
    appid     = int(cfg.get("APPID", APPID))
    mod       = cfg.get("WF_MOD", WF_MOD)

    if not demo_dir.exists():
        print(f"Demo directory not found: {demo_dir}")
        print("Run setup first:  python wf-tools.py --setup")
        sys.exit(1)

    cmd = args[0] if args else "menu"

    if cmd == "save":
        cmd_save(demo_dir, favorites)
    elif cmd == "list":
        cmd_list(demo_dir, favorites, trash, appid, mod)
    elif cmd == "play":
        if len(args) < 2:
            print("Usage: wf-tools play <slot>  (e.g. run_05)")
            sys.exit(1)
        cmd_play(demo_dir, args[1], appid, mod)
    elif cmd == "clear-temp":
        cmd_clear_temp(trash)
    elif cmd in ("menu", ""):
        cmd_menu(demo_dir, favorites, trash, archive, appid, mod)
    elif cmd == "maps-save":
        cmd_maps_save(demo_dir, archive)
    elif cmd == "maps-list":
        cmd_maps_list(archive)
    else:
        print(f"Unknown command: {cmd}")
        print("Run  python wf-tools.py --help  for usage.")
        sys.exit(1)


if __name__ == "__main__":
    main()
