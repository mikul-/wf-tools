# wf-tools

Demo recording, archive, and map-favorites tool for [Warfork](https://store.steampowered.com/app/671610/Warfork/) race runs.

Built on top of [wf-demos](https://github.com/mikul-/wf-demos) — adds map favorites with tag-based filtering alongside the existing demo management features.

- **Linux** — `wf-tools` (bash), interactive picker powered by `fzf`
- **Windows** — `wf-demos.py` / `wf-demos.bat` (Python), numbered terminal menu

## Features

### Demos (from wf-demos)

- **Auto-recording** — demos start automatically every time you press your join key
- **10-slot rolling buffer** — slots cycle `run_00` → `run_09` → `run_00`, overwriting the oldest
- **Favorites archive** — save good runs with auto-generated names (`player_mapname_Xm00s_YYYYMMDD.wfdz22`)
- **Safe deletion** — trash folder instead of instant delete; `clear-temp` to confirm permanent removal
- **In-game feedback** — Warfork console echoes which slot is being recorded

### Maps (new in wf-tools)

- **Map favorites** — save map names and tags from any demo in your rolling buffer
- **Tag system** — tag maps by weapon type: `rl` (rocket launcher), `pg` (plasma gun), `gl` (grenade launcher), `slick`, `strafe`, plus custom tags
- **Auto-tagging** — tags are auto-suggested based on map name heuristics, always confirmed interactively
- **Filter by tag** — browse maps filtered by weapon type or custom tag
- **Persistent storage** — map data saved to `maps.json` in your archive directory

---

## Contact

**Discord:** [discord.gg/WpukHzTZVR](https://discord.gg/WpukHzTZVR) — join for support, questions, or to share runs.

---

## Requirements

### Linux

| Dependency | Arch/CachyOS | Ubuntu/Debian |
|-----------|--------------|---------------|
| [fzf](https://github.com/junegunn/fzf) | `paru -S fzf` | `apt install fzf` |
| Python 3 | pre-installed | pre-installed |
| bash 4+ | pre-installed | pre-installed |
| Steam + Warfork | `paru -S steam` | `apt install steam` |

### Windows

| Dependency | Notes |
|-----------|-------|
| Python 3.8+ | [python.org](https://www.python.org/downloads/) — tick "Add Python to PATH" |
| Steam + Warfork | [Steam page](https://store.steampowered.com/app/671610/Warfork/) |

No `fzf` needed — the Windows version uses a built-in numbered menu.

---

## Install

### Linux

```bash
git clone https://github.com/mikul-/wf-tools.git
cd wf-tools
bash install.sh
```

The installer will ask you:
- **Warfork demos directory** — where Warfork stores `.wfdz*` files (default auto-detected)
- **Archive directory** — where to keep `favorites/`, `trash/`, and `maps.json` (default: `~/demos`)
- **Join keybinds** — keys that join the server and start a new recording slot (e.g. `4,F3`)
- **Practice mode keybinds** — keys that stop recording but don't start a new slot (e.g. `1,F5`)

It then installs `~/.local/bin/wf-tools`, `~/.local/bin/wf-demo-info`, and `~/.local/bin/wf-maps`, writes `~/.config/wf-demos/config`, and generates a custom `autoexec.cfg` for your Warfork mod directory. A legacy `wf-demos` symlink is also created for compatibility.

### Windows

```
git clone https://github.com/mikul-/wf-tools.git
cd wf-tools
python wf-demos.py --setup
```

Or download the zip and run `wf-demos.bat` (which calls `python wf-demos.py`).

---

## Usage

### Linux

```
wf-tools                  interactive menu (demos / maps)
wf-tools demos-save       fzf-pick a run from the rolling buffer → save to favorites
wf-tools demos-list       browse favorites  (Enter = play,  Ctrl-D = move to trash)
wf-tools play run_05      play a rolling buffer slot directly
wf-tools clear-temp       permanently delete all files in trash/
wf-tools maps-list        browse map favorites (filter by tag, edit/remove)
wf-tools maps-save        pick a demo → save map name + tags to maps.json
```

### Menu structure

```
wf-tools
├── demos
│   ├── save demo
│   ├── list favorites   (Enter=play, Ctrl-D=trash)
│   └── clear temp
│   └── .. back
└── maps
    ├── list favorites    (filter by tag → edit tags / remove)
    └── save map to favorites
    └── .. back
```

### Maps workflow

1. Run `wf-tools` → pick **maps** → **save map to favorites**
2. A list of your rolling-buffer demos appears — pick one
3. Map name is extracted from the demo header and tags are auto-suggested
4. Interactive tag prompt lets you:
   - Toggle predefined tags by number (`1`-`5`)
   - Add custom tags with `+tagname`
   - Remove tags with `-tagname`
   - Press Enter or `=` when done
5. Map is saved to `maps.json`

To browse: **maps** → **list favorites** → filter by tag (`all`, `rl`, `pg`, `gl`, `slick`, `strafe`, `.. back`) → pick a map → edit tags or remove.

### Windows

```
wf-demos.bat                    interactive menu
wf-demos.bat save               numbered list of rolling buffer → pick to save
wf-demos.bat list               numbered list of favorites → pick to play or trash
wf-demos.bat play run_05        play a rolling buffer slot directly
wf-demos.bat clear-temp         permanently delete all files in trash\
```

Or call Python directly: `python wf-demos.py [command]`

---

## How the auto-recording works

The setup/installer drops an `autoexec.cfg` into your Warfork mod directory. It sets up a 10-alias chain and overrides your join/practice-mode binds:

**Join key** (`4` by default):
```
stop; join; record run_XX; (advance slot counter)
```

**Practice mode key** (`1`, `F5` by default):
```
stop; practicemode
```

The slot counter (`run_00` … `run_09`) advances each join and resets to `run_00` when Warfork starts. Oldest demos are silently overwritten.

---

## Configuration

Edit the config file directly to change paths without re-running setup.

**Linux** — `~/.config/wf-demos/config`:
```bash
DEMO_DIR="${HOME}/.local/share/warfork-2.1/racemod_2.1/demos"
ARCHIVE_DIR="${HOME}/demos"
APPID=671610
WF_MOD=racemod_2.1
```

**Windows** — `%APPDATA%\wf-demos\config`:
```
DEMO_DIR=C:\Users\you\Documents\My Games\Warfork 2.1\racemod_2.1\demos
ARCHIVE_DIR=C:\Users\you\Documents\wf-demos
APPID=671610
WF_MOD=racemod_2.1
```

### Map data format (`maps.json`)

```json
{
  "maps": [
    {
      "name": "wf-race-rl-temple",
      "tags": ["rl", "hard"],
      "date_added": "2026-08-05"
    }
  ]
}
```

---

## Tags

### Predefined tags

| Tag | Description |
|-----|-------------|
| `rl` | Rocket launcher maps |
| `pg` | Plasma gun maps |
| `gl` | Grenade launcher maps |
| `slick` | Slick/surf maps |
| `strafe` | Pure strafe/defrag maps (default) |

### Auto-detection

Tags are auto-suggested based on patterns in the map name:

| Pattern | Suggested tag |
|---------|---------------|
| `rl`, `rocket` | rl |
| `pg`, `plasma` | pg |
| `gl`, `nade`, `grenade` | gl |
| `slick`, `sl1ck`, `s1ick` | slick |
| none matched | strafe |

You always get to confirm or edit tags before saving. Custom tags (e.g. `hard`, `fun`, `beginner`) can be added with `+tagname` in the tag prompt.

---

## File layout

### Linux

| Path | Purpose |
|------|---------|
| `~/.local/bin/wf-tools` | Main CLI |
| `~/.local/bin/wf-demos` | Legacy symlink → wf-tools |
| `~/.local/bin/wf-demo-info` | Demo header parser (Python) |
| `~/.local/bin/wf-maps` | Map favorites manager (Python) |
| `~/.config/wf-demos/config` | User config |
| `~/demos/favorites/` | Saved demos |
| `~/demos/trash/` | Trashed demos (pending `clear-temp`) |
| `~/demos/maps.json` | Map favorites data |

### Windows

| Path | Purpose |
|------|---------|
| `wf-demos.py` | Main CLI (run from repo folder) |
| `wf-demos.bat` | Launcher — calls `python wf-demos.py %*` |
| `%APPDATA%\wf-demos\config` | User config |
| `Documents\wf-demos\favorites\` | Saved demos |
| `Documents\wf-demos\trash\` | Trashed demos |

---

## wf-rename — bulk rename existing demos

`wf-rename.py` is a standalone script that reads the header of every `.wfdz*` file in a folder and renames them to the standard format:

```
player_mapname_Xm00.000s_YYYYMMDD.wfdz22   (when race finish time is in the demo)
player_mapname_YYYYMMDD.wfdz22             (fallback)
```

```
python wf-rename.py [folder]          preview what would be renamed
python wf-rename.py [folder] --apply  actually rename the files
```

---

## Uninstall

**Linux:**
```bash
rm ~/.local/bin/wf-tools ~/.local/bin/wf-demos ~/.local/bin/wf-demo-info ~/.local/bin/wf-maps
rm -rf ~/.config/wf-demos
# optionally keep your saved demos and maps.json:
# rm -rf ~/demos
```

Remove the `wf-tools` block from your `autoexec.cfg` to restore your original binds.

---

## Notes

- Demo playback launches Warfork via `steam -applaunch` (Linux) or via the registry-detected `steam.exe` (Windows). Steam must be running.
- The qfusion engine auto-prepends `demos/` to demo names — do not include it yourself.
- Warfork demo extensions look like `.wfdz22`; the version number may vary. The glob `*.wfdz*` handles all versions.
- The demo header parser reads the first 512 bytes of each file to extract map name, duration, and timestamp — no external libraries required.
- On Windows, if Steam is not found automatically, you'll be prompted to copy the demo manually and launch it from within the game.
- Map favorites and demo favorites are separate — `maps.json` stores map metadata only, not demo files.
