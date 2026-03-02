#!/usr/bin/env zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
APP_DIR="$HOME/Library/Application Support/codex-tts-mcp"
SERVER_DIR="$APP_DIR/server"
BIN_DIR="$APP_DIR/bin"
LOG_DIR="$APP_DIR/logs"
SOCKET_PATH="${CODEX_TTS_SOCKET:-$APP_DIR/tts.sock}"
MUTE_STATE_PATH="${CODEX_TTS_MUTE_STATE:-$APP_DIR/mute_state.json}"
SETTINGS_PATH="${CODEX_TTS_SETTINGS_PATH:-$APP_DIR/speech_settings.json}"

HELPER_LABEL="com.codex.tts.helper"
MENUBAR_LABEL="com.codex.tts.menubar"
HELPER_PLIST="$HOME/Library/LaunchAgents/$HELPER_LABEL.plist"
MENUBAR_PLIST="$HOME/Library/LaunchAgents/$MENUBAR_LABEL.plist"
HELPER_LOG="$LOG_DIR/helper.log"
MENUBAR_LOG="$LOG_DIR/menubar.log"

mkdir -p "$APP_DIR" "$SERVER_DIR" "$BIN_DIR" "$LOG_DIR" "$HOME/Library/LaunchAgents"
chmod 700 "$APP_DIR"

launchctl bootout "gui/$(id -u)/$HELPER_LABEL" >/dev/null 2>&1 || true
launchctl bootout "gui/$(id -u)/$MENUBAR_LABEL" >/dev/null 2>&1 || true

rsync -a --delete "$ROOT_DIR/src/" "$SERVER_DIR/src/"
cp "$ROOT_DIR/pyproject.toml" "$SERVER_DIR/pyproject.toml"

python3 -m venv "$SERVER_DIR/.venv" >/dev/null
"$SERVER_DIR/.venv/bin/pip" install -q -e "$SERVER_DIR" >/dev/null

if ! command -v xcrun >/dev/null 2>&1; then
  echo "ERROR: xcrun not found; cannot build menu bar app" >&2
  exit 1
fi

if ! xcrun swiftc -O "$ROOT_DIR/scripts/codex_tts_menubar.swift" -o "$BIN_DIR/codex-tts-menubar" >/dev/null 2>&1; then
  echo "ERROR: failed to build menu bar app (swiftc)" >&2
  exit 1
fi
chmod +x "$BIN_DIR/codex-tts-menubar"

cat > "$HELPER_PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$HELPER_LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$SERVER_DIR/.venv/bin/python3</string>
    <string>$SERVER_DIR/src/codex_tts_mcp/helper_daemon.py</string>
    <string>--socket</string>
    <string>$SOCKET_PATH</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>$HELPER_LOG</string>
  <key>StandardErrorPath</key>
  <string>$HELPER_LOG</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PYTHONPATH</key>
    <string>$SERVER_DIR/src</string>
    <key>CODEX_TTS_SOCKET</key>
    <string>$SOCKET_PATH</string>
    <key>CODEX_TTS_MUTE_STATE</key>
    <string>$MUTE_STATE_PATH</string>
    <key>CODEX_TTS_SETTINGS_PATH</key>
    <string>$SETTINGS_PATH</string>
    <key>CODEX_TTS_VOICE</key>
    <string>Samantha</string>
    <key>CODEX_TTS_RATE</key>
    <string>190</string>
  </dict>
</dict>
</plist>
PLIST

cat > "$MENUBAR_PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$MENUBAR_LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$BIN_DIR/codex-tts-menubar</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>$MENUBAR_LOG</string>
  <key>StandardErrorPath</key>
  <string>$MENUBAR_LOG</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>CODEX_TTS_MUTE_STATE</key>
    <string>$MUTE_STATE_PATH</string>
    <key>CODEX_TTS_SETTINGS_PATH</key>
    <string>$SETTINGS_PATH</string>
    <key>CODEX_TTS_VOICE</key>
    <string>Samantha</string>
    <key>CODEX_TTS_RATE</key>
    <string>190</string>
  </dict>
</dict>
</plist>
PLIST

if ! launchctl bootstrap "gui/$(id -u)" "$HELPER_PLIST" >/dev/null 2>&1; then
  launchctl kickstart -k "gui/$(id -u)/$HELPER_LABEL" >/dev/null
else
  launchctl kickstart -k "gui/$(id -u)/$HELPER_LABEL" >/dev/null
fi

if ! launchctl bootstrap "gui/$(id -u)" "$MENUBAR_PLIST" >/dev/null 2>&1; then
  launchctl kickstart -k "gui/$(id -u)/$MENUBAR_LABEL" >/dev/null
else
  launchctl kickstart -k "gui/$(id -u)/$MENUBAR_LABEL" >/dev/null
fi

if [[ ! -S "$SOCKET_PATH" ]]; then
  echo "ERROR: helper socket not ready: $SOCKET_PATH" >&2
  exit 1
fi

if [[ ! -f "$MUTE_STATE_PATH" ]]; then
  printf '{"muted": false}\n' > "$MUTE_STATE_PATH"
fi
if [[ ! -f "$SETTINGS_PATH" ]]; then
  printf '{"voice": "Samantha", "rate": 190}\n' > "$SETTINGS_PATH"
fi

CODEX_CONFIG_PATH="${CODEX_CONFIG_PATH:-$HOME/.codex/config.toml}"
mkdir -p "$(dirname "$CODEX_CONFIG_PATH")"

python3 - "$CODEX_CONFIG_PATH" "$SERVER_DIR" "$SOCKET_PATH" "$MUTE_STATE_PATH" "$SETTINGS_PATH" <<'PY'
import re
import sys
from pathlib import Path

cfg_path = Path(sys.argv[1])
server_dir = sys.argv[2]
socket_path = sys.argv[3]
mute_state_path = sys.argv[4]
settings_path = sys.argv[5]

content = cfg_path.read_text(encoding="utf-8") if cfg_path.exists() else ""

def strip_section(text: str, section_name: str) -> str:
    pattern = re.compile(
        rf"(?ms)^\[{re.escape(section_name)}\]\n(?:^(?!\[).*\n?)*"
    )
    return pattern.sub("", text)

content = strip_section(content, "mcp_servers.codex_tts.env")
content = strip_section(content, "mcp_servers.codex_tts")
content = content.rstrip()

block = (
    f'[mcp_servers.codex_tts]\n'
    f'command = "{server_dir}/.venv/bin/python3"\n'
    f'args = ["{server_dir}/src/codex_tts_mcp/mcp_server.py"]\n'
    '\n'
    f'[mcp_servers.codex_tts.env]\n'
    f'PYTHONPATH = "{server_dir}/src"\n'
    f'CODEX_TTS_SOCKET = "{socket_path}"\n'
    f'CODEX_TTS_MUTE_STATE = "{mute_state_path}"\n'
    f'CODEX_TTS_SETTINGS_PATH = "{settings_path}"\n'
    'CODEX_TTS_VOICE = "Samantha"\n'
    'CODEX_TTS_RATE = "190"\n'
)

updated = f"{content}\n\n{block}" if content else block
cfg_path.write_text(updated, encoding="utf-8")
PY

python3 - "$CODEX_CONFIG_PATH" <<'PY'
import sys
import tomllib
from pathlib import Path

with Path(sys.argv[1]).open("rb") as handle:
    tomllib.load(handle)
PY

echo "SUCCESS: codex-tts installed with helper + menu bar mute"
echo "INFO: Codex config auto-registered at $CODEX_CONFIG_PATH"
