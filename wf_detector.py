#!/usr/bin/env python3
"""
Weapon detection for Warfork race demos.

Three detection methods (priority order):
  1. Map name heuristics — community naming conventions (rl/pg/gl/slick)
  2. BSP entity parsing — read weapon entities from map BSP in pk3 archives
  3. (Reserved) Demo binary protocol parsing — not yet implemented

Usage:
  from wf_detector import detect_weapons, detect_weapons_brief

  tags = detect_weapons("bug71_rl-wjfix")
  # → {"weapon": "rl", "tags": ["rl"], "source": "mapname"}

  tags = detect_weapons("darkie-strafe1")
  # → {"weapon": None, "tags": ["strafe", "slick"], "source": "mapname"}
"""
import re
import os
import struct
import zipfile
from pathlib import Path

# ── Constants ──────────────────────────────────────────────────────────────────

PREDEFINED_TAGS = ["rl", "pg", "gl", "slick", "strafe"]

WEAPON_TAGS = frozenset({"rl", "pg", "gl"})

WEAPON_ENTITY_MAP = {
    "weapon_rocketlauncher":  "rl",
    "weapon_grenadelauncher": "gl",
    "weapon_plasmagun":       "pg",
}

WEAPON_TAG_NAMES = {
    "rl": "Rocket Launcher",
    "pg": "Plasma Gun",
    "gl": "Grenade Launcher",
    "slick": "Slick/Strafe",
    "strafe": "Strafe Only",
}

# ── Map name patterns ──────────────────────────────────────────────────────────

MAP_PATTERNS = [
    (re.compile(r"(?:^|[-_])rl(?:[-_]|$)|[-_]rl$|rocket|^rl$", re.IGNORECASE),  "rl"),
    (re.compile(r"(?:^|[-_])pg(?:[-_]|$)|(?:^|[_-])pg$|plasma", re.IGNORECASE),   "pg"),
    (re.compile(r"(?:^|[-_])gl(?:[-_]|$)|(?:^|[_-])gl$|nade|grenade", re.IGNORECASE), "gl"),
    (re.compile(r"slick|sl1ck|s1ick", re.IGNORECASE),                             "slick"),
    (re.compile(r"strafe|bhop|bunny", re.IGNORECASE),                             "strafe"),
]

# ── BSP discovery paths ────────────────────────────────────────────────────────

_bsp_cache = {}  # mapname -> (pk3_path, bsp_path) or None after full scan
_bsp_scanned = False


def _warfork_data_dirs():
    """Return list of directories that may contain Warfork pk3 archives."""
    home = Path.home()
    dirs = []
    candidates = [
        home / ".local" / "share" / "warfork-2.1",
        home / ".local" / "share" / "warsow-2.1",
        home / ".local" / "share" / "Steam" / "steamapps" / "common" / "fvi",
        Path("/usr/share/warfork-2.1"),
        Path("/usr/share/warsow-2.1"),
        Path("C:/Program Files (x86)/Steam/steamapps/common/fvi"),
        Path("C:/Program Files/Steam/steamapps/common/fvi"),
    ]
    for d in candidates:
        if d.exists():
            dirs.append(d)
    return dirs


def _build_bsp_cache(search_dirs=None):
    """Scan all pk3 archives and build a cache of mapname -> (pk3_path, bsp_path)."""
    global _bsp_cache, _bsp_scanned
    if _bsp_scanned:
        return

    if search_dirs is None:
        search_dirs = _warfork_data_dirs()

    pk3_glob_patterns = [
        "downloads/racemod_2.1/*.pk3",
        "downloads__/racemod_2.1/*.pk3",
        "basewf/*.pk3",
        "racemod_2.1/*.pk3",
    ]

    for base in search_dirs:
        for pattern in pk3_glob_patterns:
            for pk3_path in sorted(base.glob(pattern)):
                try:
                    with zipfile.ZipFile(pk3_path, 'r') as zf:
                        for name in zf.namelist():
                            if name.startswith("maps/") and name.endswith(".bsp"):
                                bsp_stem = os.path.splitext(os.path.basename(name))[0]
                                key = bsp_stem.lower()
                                if key not in _bsp_cache:
                                    _bsp_cache[key] = (str(pk3_path), name)
                except Exception:
                    continue
    _bsp_scanned = True


def _find_pk3_for_map(mapname, search_dirs=None):
    """Search for a pk3 archive containing a BSP for the given map name.
    Uses a cache built on first call for fast subsequent lookups."""
    global _bsp_cache, _bsp_scanned
    key = mapname.lower()

    if key in _bsp_cache:
        return _bsp_cache[key]

    if not _bsp_scanned:
        _build_bsp_cache(search_dirs)

    return _bsp_cache.get(key, (None, None))


def _parse_bsp_entities(pk3_path, bsp_path):
    """Parse the entity lump from a BSP file inside a pk3 archive.
    Returns a list of dicts with entity key-value pairs."""
    try:
        with zipfile.ZipFile(pk3_path, 'r') as zf:
            data = zf.read(bsp_path)
    except Exception:
        return []

    if len(data) < 20:
        return []

    try:
        ent_off = struct.unpack_from('<I', data, 8)[0]
        ent_len = struct.unpack_from('<I', data, 12)[0]
    except struct.error:
        return []

    if ent_off <= 0 or ent_len <= 0 or ent_off + ent_len > len(data):
        return []

    ent_data = data[ent_off:ent_off + ent_len]
    ent_text = ent_data.decode('latin-1', errors='replace')

    entities = []
    for match in re.finditer(r'\{\s*((?:"[^"]*"\s*"[^"]*"\s*)+)\}', ent_text):
        kv_block = match.group(1)
        kv = dict(re.findall(r'"([^"]*)"\s*"([^"]*)"', kv_block))
        if 'classname' in kv:
            entities.append(kv)
    return entities


# ── Public API ─────────────────────────────────────────────────────────────────

def detect_weapons_from_mapname(mapname):
    """Detect weapon tags from map name using community naming conventions.

    Returns dict: {"tags": [...], "weapon": "rl"|"pg"|"gl"|None, "source": "mapname"}
    """
    tags = set()
    weapon_tag = None

    for pattern, tag in MAP_PATTERNS:
        if pattern.search(mapname):
            tags.add(tag)
            if tag in WEAPON_TAGS:
                weapon_tag = tag

    if not tags:
        tags.add("strafe")

    return {
        "tags": sorted(tags),
        "weapon": weapon_tag,
        "source": "mapname",
    }


def detect_weapons_from_bsp(mapname, search_dirs=None):
    """Detect weapon tags by parsing weapon entities from the map's BSP file.

    Searches for pk3 archives containing the map BSP and extracts weapon entities.
    Returns empty result if BSP is not found or has no weapon entities.

    Returns dict: {"weapon": "rl"|"pg"|"gl"|None, "source": "bsp"}
    """
    pk3_path, bsp_path = _find_pk3_for_map(mapname, search_dirs)
    if pk3_path is None:
        return {"weapon": None, "source": "bsp"}

    entities = _parse_bsp_entities(pk3_path, bsp_path)
    if not entities:
        return {"weapon": None, "source": "bsp"}

    for entity in entities:
        classname = entity.get("classname", "")
        tag = WEAPON_ENTITY_MAP.get(classname)
        if tag:
            return {"weapon": tag, "source": "bsp"}

    return {"weapon": None, "source": "bsp"}


def detect_weapons(mapname, search_dirs=None):
    """Detect weapon tags using all available methods.

    Priority:
      1. Map name heuristics — base tags (rl/pg/gl/slick/strafe)
      2. BSP entity detection — overrides weapon tag when BSP has weapon entities

    Returns dict: {"tags": [...], "weapon": "rl"|"pg"|"gl"|None, "source": "mapname"|"bsp"}
    """
    name_result = detect_weapons_from_mapname(mapname)
    bsp_result = detect_weapons_from_bsp(mapname, search_dirs)

    if bsp_result["weapon"] is not None:
        tags = set(name_result["tags"])
        tags.discard(name_result.get("weapon", ""))
        if bsp_result["weapon"] not in WEAPON_TAGS:
            tags.discard(bsp_result["weapon"])
        tags.add(bsp_result["weapon"])
        return {
            "tags": sorted(tags),
            "weapon": bsp_result["weapon"],
            "source": "bsp",
        }

    return name_result


def detect_weapons_brief(mapname, search_dirs=None):
    """Return just the sorted list of weapon tags (most common use case)."""
    return detect_weapons(mapname, search_dirs)["tags"]


def suggest_tags(mapname, search_dirs=None):
    """Fast tag suggestion from map name only (for interactive prompts).
    Returns a sorted list of tag strings. Does NOT use BSP scanning."""
    return detect_weapons_from_mapname(mapname)["tags"]


# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    import sys
    if len(sys.argv) < 2:
        print("Usage: wf-detector <mapname> [--brief] [--source]", file=sys.stderr)
        print("Detects weapon tags for a Warfork race map.", file=sys.stderr)
        sys.exit(1)

    mapname = sys.argv[1]
    brief = "--brief" in sys.argv
    show_source = "--source" in sys.argv

    result = detect_weapons(mapname)

    if brief:
        print(", ".join(result["tags"]))
    else:
        print(f"Map:       {mapname}")
        print(f"Tags:      {', '.join(result['tags'])}")
        if result["weapon"]:
            print(f"Weapon:    {WEAPON_TAG_NAMES.get(result['weapon'], result['weapon'])} ({result['weapon']})")
        else:
            print(f"Weapon:    none (strafe-only)")
        if show_source:
            print(f"Source:    {result['source']}")


if __name__ == "__main__":
    main()
