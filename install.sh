#!/usr/bin/env bash
# wf-tools installer
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN="${HOME}/.local/bin"
CONFIG_DIR="${XDG_CONFIG_HOME:-${HOME}/.config}/wf-demos"

# ── Colors ────────────────────────────────────────────────────────────────
if [[ -t 1 ]]; then
    GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'
    BOLD='\033[1m'; NC='\033[0m'
else
    GREEN=''; YELLOW=''; BLUE=''; BOLD=''; NC=''
fi
info()    { echo -e "${BLUE}→${NC} $*"; }
success() { echo -e "${GREEN}✓${NC} $*"; }
warn()    { echo -e "${YELLOW}!${NC} $*"; }
header()  { echo -e "\n${BOLD}$*${NC}"; }
ask()     { echo -e "${BOLD}$1${NC}"; read -r -p "  → " "$2"; }

# ── Header ────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}╔══════════════════════════════╗${NC}"
echo -e "${BOLD}║       wf-tools installer      ║${NC}"
echo -e "${BOLD}╚══════════════════════════════╝${NC}"
echo ""

# ── 1. Dependencies ───────────────────────────────────────────────────────
header "Checking dependencies..."
missing=()
for dep in fzf python3 steam; do
    if command -v "$dep" &>/dev/null; then
        success "$dep"
    else
        warn "$dep — NOT FOUND"
        missing+=("$dep")
    fi
done
if [[ ${#missing[@]} -gt 0 ]]; then
    echo ""
    echo "Missing dependencies: ${missing[*]}"
    echo "Install them and re-run this script."
    exit 1
fi

# ── 2. Warfork demos directory ────────────────────────────────────────────
header "Warfork demos directory"
DEFAULT_DEMO_DIR="${HOME}/.local/share/warfork-2.1/racemod_2.1/demos"
echo "  This is where Warfork stores recorded demo files."
echo "  Default: ${DEFAULT_DEMO_DIR}"
ask "Press Enter to use default, or type a custom path:" DEMO_DIR
DEMO_DIR="${DEMO_DIR:-$DEFAULT_DEMO_DIR}"
DEMO_DIR="${DEMO_DIR/#\~/$HOME}"          # expand leading ~
DEMO_DIR="${DEMO_DIR%/}"                   # strip trailing slash

# Derive the Warfork mod config dir from the demo dir (parent of demos/)
WF_CFG_DIR="$(dirname "$DEMO_DIR")"
WF_CFG="${WF_CFG_DIR}/autoexec.cfg"

# ── 3. Archive directory ──────────────────────────────────────────────────
header "Archive directory"
DEFAULT_ARCHIVE="${HOME}/demos"
echo "  Favorites and trash folders will be created here."
echo "  Default: ${DEFAULT_ARCHIVE}"
ask "Press Enter to use default, or type a custom path:" ARCHIVE_DIR
ARCHIVE_DIR="${ARCHIVE_DIR:-$DEFAULT_ARCHIVE}"
ARCHIVE_DIR="${ARCHIVE_DIR/#\~/$HOME}"
ARCHIVE_DIR="${ARCHIVE_DIR%/}"

# ── 4. Join keybinds ─────────────────────────────────────────────────────
header "Join keybinds"
echo "  These keys will STOP the current demo, join the server, and START"
echo "  recording a new slot. Enter comma-separated Warfork key names."
echo "  Common: 4, F3, ENTER, KP_INS, SPACE, MOUSE1 ..."
echo "  Default: 4,F3"
ask "Join keybinds:" JOIN_BINDS_RAW
JOIN_BINDS_RAW="${JOIN_BINDS_RAW:-4,F3}"

# ── 5. Practice mode keybinds ─────────────────────────────────────────────
header "Practice mode keybinds"
echo "  These keys will STOP the current demo and enter practice mode"
echo "  (no new recording started)."
echo "  Default: 1,F5,F11"
ask "Practice mode keybinds:" PM_BINDS_RAW
PM_BINDS_RAW="${PM_BINDS_RAW:-1,F5,F11}"

# ── 6. Confirm ────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}Summary${NC}"
echo "  Demo dir:     $DEMO_DIR"
echo "  Archive dir:  $ARCHIVE_DIR"
echo "  Join binds:   $JOIN_BINDS_RAW"
echo "  PM binds:     $PM_BINDS_RAW"
echo "  Config file:  $CONFIG_DIR/config"
echo "  Warfork cfg:  $WF_CFG"
echo ""
read -r -p "Continue? [Y/n] " go
[[ "${go:-y}" =~ ^[Nn] ]] && echo "Aborted." && exit 0

echo ""

# ── 7. Generate autoexec.cfg ──────────────────────────────────────────────
info "Generating autoexec.cfg..."

# Build bind lines from comma-separated input
build_bind_lines() {
    local raw="$1" action="$2"
    IFS=',' read -ra keys <<< "$raw"
    for k in "${keys[@]}"; do
        k="${k// /}"    # trim whitespace
        [[ -z "$k" ]] && continue
        echo "bind ${k}   \"${action}\""
    done
}

join_bind_lines="$(build_bind_lines "$JOIN_BINDS_RAW" "vstr dslot_cmd")"
pm_bind_lines="$(build_bind_lines "$PM_BINDS_RAW" "pm_stop")"

cfg_content="// ── wf-tools BEGIN ───────────────────────────────────────────────────────
// Demo auto-cycling — wf-tools system
// join keys  = stop current demo + join server + start new slot
// pm keys    = stop current demo + practice mode (no new recording)
// Slot counter resets to 0 each time Warfork starts.
// Manage with: wf-tools

set dslot_cmd \"demo_slot_0\"

alias demo_slot_0 \"stop; join; record run_00; set dslot_cmd demo_slot_1; echo ^2[wf-tools]^7 recording run_00\"
alias demo_slot_1 \"stop; join; record run_01; set dslot_cmd demo_slot_2; echo ^2[wf-tools]^7 recording run_01\"
alias demo_slot_2 \"stop; join; record run_02; set dslot_cmd demo_slot_3; echo ^2[wf-tools]^7 recording run_02\"
alias demo_slot_3 \"stop; join; record run_03; set dslot_cmd demo_slot_4; echo ^2[wf-tools]^7 recording run_03\"
alias demo_slot_4 \"stop; join; record run_04; set dslot_cmd demo_slot_5; echo ^2[wf-tools]^7 recording run_04\"
alias demo_slot_5 \"stop; join; record run_05; set dslot_cmd demo_slot_6; echo ^2[wf-tools]^7 recording run_05\"
alias demo_slot_6 \"stop; join; record run_06; set dslot_cmd demo_slot_7; echo ^2[wf-tools]^7 recording run_06\"
alias demo_slot_7 \"stop; join; record run_07; set dslot_cmd demo_slot_8; echo ^2[wf-tools]^7 recording run_07\"
alias demo_slot_8 \"stop; join; record run_08; set dslot_cmd demo_slot_9; echo ^2[wf-tools]^7 recording run_08\"
alias demo_slot_9 \"stop; join; record run_09; set dslot_cmd demo_slot_0; echo ^2[wf-tools]^7 recording run_09\"

alias pm_stop \"stop; practicemode\"

${join_bind_lines}
${pm_bind_lines}
// ── wf-tools END ─────────────────────────────────────────────────────────"

if [[ -f "$WF_CFG" ]]; then
    warn "Existing autoexec.cfg found."
    echo ""
    echo "  1) Overwrite   — replace entire file (old file backed up)"
     echo "  2) Merge       — insert/replace only the wf-tools block, keep the rest"
    echo "  3) Print only  — show generated config for manual merging"
    echo "  4) Skip"
    read -r -p "  → [1/2/3/4]: " cfg_choice
    case "${cfg_choice:-2}" in
        1)
            backup="${WF_CFG}.bak.$(date +%Y%m%d%H%M%S)"
            cp "$WF_CFG" "$backup"
            success "Backed up: $backup"
            mkdir -p "$WF_CFG_DIR"
            echo "$cfg_content" > "$WF_CFG"
            success "autoexec.cfg installed."
            ;;
        2)
            echo "$cfg_content" > /tmp/wf-tools-autoexec.cfg
            backup="${WF_CFG}.bak.$(date +%Y%m%d%H%M%S)"
            cp "$WF_CFG" "$backup"
            success "Backed up: $backup"
            python3 - "$WF_CFG" /tmp/wf-tools-autoexec.cfg <<'PYEOF'
import sys, re

existing_path = sys.argv[1]
new_block_path = sys.argv[2]

with open(existing_path) as f:
    existing = f.read()
with open(new_block_path) as f:
    new_block = f.read().rstrip('\n')

BEGIN = "// ── wf-tools BEGIN"
END   = "// ── wf-tools END"

if BEGIN in existing:
    # Replace the marked block (handles re-installs cleanly)
    result = re.sub(
        r'// ── wf-tools BEGIN.*?// ── wf-tools END[^\n]*',
        new_block,
        existing,
        flags=re.DOTALL
    )
elif 'set dslot_cmd' in existing or 'demo_slot_0' in existing:
    # Old install without markers — append new block, leave old one in place
    print("  Note: old wf-tools/wf-demos config found without markers. New block appended.")
    print("  Remove the old block manually if needed.")
    result = existing.rstrip('\n') + '\n\n' + new_block + '\n'
else:
    # Fresh file with other content — append
    result = existing.rstrip('\n') + '\n\n' + new_block + '\n'

with open(existing_path, 'w') as f:
    f.write(result)
PYEOF
            success "autoexec.cfg merged."
            ;;
        3)
            echo ""
            echo "──── generated wf-tools block ────"
            echo "$cfg_content"
            echo "──────────────────────────────────"
            echo "$cfg_content" > /tmp/wf-tools-autoexec.cfg
            info "Saved to /tmp/wf-tools-autoexec.cfg"
            ;;
        *)
            warn "Skipped autoexec.cfg."
            ;;
    esac
else
    mkdir -p "$WF_CFG_DIR"
    echo "$cfg_content" > "$WF_CFG"
    success "autoexec.cfg installed to $WF_CFG"
fi

# ── 8. Write config file ──────────────────────────────────────────────────
info "Writing config file..."
mkdir -p "$CONFIG_DIR"
cat > "$CONFIG_DIR/config" <<EOF
# wf-tools configuration
# Generated by install.sh — edit as needed

# Directory where Warfork stores recorded demo files
DEMO_DIR="${DEMO_DIR}"

# Root directory for favorites/ and trash/
ARCHIVE_DIR="${ARCHIVE_DIR}"

# Steam App ID (671610 = Warfork)
APPID=671610

# Warfork mod directory name
WF_MOD=racemod_2.1
EOF
success "Config written to $CONFIG_DIR/config"

# ── 9. Create archive dirs ────────────────────────────────────────────────
info "Creating archive directories..."
mkdir -p "${ARCHIVE_DIR}/favorites" "${ARCHIVE_DIR}/trash"
success "Created: ${ARCHIVE_DIR}/favorites"
success "Created: ${ARCHIVE_DIR}/trash"

# ── 10. Install scripts ───────────────────────────────────────────────────
info "Installing scripts to $BIN ..."
mkdir -p "$BIN"

cp "$SCRIPT_DIR/wf-tools"      "$BIN/wf-tools"
cp "$SCRIPT_DIR/wf-demo-info"  "$BIN/wf-demo-info"
cp "$SCRIPT_DIR/wf-maps"       "$BIN/wf-maps"
cp "$SCRIPT_DIR/wf-detector.py" "$BIN/wf-detector.py"
chmod +x "$BIN/wf-tools" "$BIN/wf-demo-info" "$BIN/wf-maps"
success "Installed: $BIN/wf-tools"
success "Installed: $BIN/wf-demo-info"
success "Installed: $BIN/wf-maps"
success "Installed: $BIN/wf-detector.py"

# Also install legacy wf-demos symlink
ln -sf "$BIN/wf-tools" "$BIN/wf-demos" 2>/dev/null || true
success "Linked: $BIN/wf-demos → wf-tools"

# ── 11. Remove old fish function if present ───────────────────────────────
FISH_FN="${HOME}/.config/fish/functions/wf-demos.fish"
if [[ -f "$FISH_FN" ]]; then
    warn "Found old fish function — removing (superseded by shell script)."
    rm "$FISH_FN"
    success "Removed: $FISH_FN"
fi

# ── 12. PATH check ────────────────────────────────────────────────────────
if ! echo "$PATH" | grep -q "${BIN}"; then
    echo ""
    warn "$BIN is not in your PATH."
    echo "  Add this to your shell config:"
    echo "    bash/zsh:  export PATH=\"\$HOME/.local/bin:\$PATH\""
    echo "    fish:      fish_add_path ~/.local/bin"
fi

# ── Done ──────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}${BOLD}Installation complete!${NC}"
echo ""
echo "  wf-tools              — open menu"
echo "  wf-demos              — also works (links to wf-tools)"
echo "  wf-tools demos-save   — save a run to favorites"
echo "  wf-tools demos-list   — browse favorites (Enter=play, Ctrl-D=trash)"
echo "  wf-tools play run_05  — play a rolling buffer slot directly"
echo "  wf-tools clear-temp   — permanently delete trashed demos"
echo "  wf-tools maps-list    — browse map favorites (filter by tag)"
echo "  wf-tools maps-save    — pick demo → save map name + tags"
echo ""
echo "Map data: $ARCHIVE_DIR/maps.json"
echo "Launch Warfork and press your join bind to start recording!"
echo ""
