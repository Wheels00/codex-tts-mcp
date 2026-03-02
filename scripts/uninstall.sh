#!/usr/bin/env zsh
set -euo pipefail

APP_DIR="$HOME/Library/Application Support/codex-tts-mcp"
SOCKET_PATH="${CODEX_TTS_SOCKET:-$APP_DIR/tts.sock}"
MUTE_STATE_PATH="${CODEX_TTS_MUTE_STATE:-$APP_DIR/mute_state.json}"
SETTINGS_PATH="${CODEX_TTS_SETTINGS_PATH:-$APP_DIR/speech_settings.json}"

HELPER_LABEL="com.codex.tts.helper"
MENUBAR_LABEL="com.codex.tts.menubar"
HELPER_PLIST="$HOME/Library/LaunchAgents/$HELPER_LABEL.plist"
MENUBAR_PLIST="$HOME/Library/LaunchAgents/$MENUBAR_LABEL.plist"

launchctl bootout "gui/$(id -u)/$HELPER_LABEL" >/dev/null 2>&1 || true
launchctl bootout "gui/$(id -u)/$MENUBAR_LABEL" >/dev/null 2>&1 || true

rm -f "$HELPER_PLIST" "$MENUBAR_PLIST" "$SOCKET_PATH" "$MUTE_STATE_PATH" "$SETTINGS_PATH"
rm -rf "$APP_DIR/server" "$APP_DIR/bin"

CODEX_CONFIG_PATH="${CODEX_CONFIG_PATH:-$HOME/.codex/config.toml}"
if [[ -f "$CODEX_CONFIG_PATH" ]]; then
  python3 - "$CODEX_CONFIG_PATH" <<'PY'
import re
import sys
from pathlib import Path

cfg_path = Path(sys.argv[1])
content = cfg_path.read_text(encoding="utf-8")

def strip_section(text: str, section_name: str) -> str:
    pattern = re.compile(
        rf"(?ms)^\[{re.escape(section_name)}\]\n(?:^(?!\[).*\n?)*"
    )
    return pattern.sub("", text)

content = strip_section(content, "mcp_servers.codex_tts.env")
content = strip_section(content, "mcp_servers.codex_tts")
cfg_path.write_text(content.rstrip() + "\n", encoding="utf-8")
PY
fi

echo "SUCCESS: codex tts helper + menu bar mute removed"
