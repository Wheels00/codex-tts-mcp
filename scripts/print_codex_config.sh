#!/usr/bin/env zsh
set -euo pipefail

APP_DIR="$HOME/Library/Application Support/codex-tts-mcp"
SERVER_DIR="$APP_DIR/server"
SOCKET_PATH="${CODEX_TTS_SOCKET:-$APP_DIR/tts.sock}"
MUTE_STATE_PATH="${CODEX_TTS_MUTE_STATE:-$APP_DIR/mute_state.json}"
SETTINGS_PATH="${CODEX_TTS_SETTINGS_PATH:-$APP_DIR/speech_settings.json}"

cat <<CFG
[mcp_servers.codex_tts]
command = "$SERVER_DIR/.venv/bin/python3"
args = ["$SERVER_DIR/src/codex_tts_mcp/mcp_server.py"]

[mcp_servers.codex_tts.env]
PYTHONPATH = "$SERVER_DIR/src"
CODEX_TTS_SOCKET = "$SOCKET_PATH"
CODEX_TTS_MUTE_STATE = "$MUTE_STATE_PATH"
CODEX_TTS_SETTINGS_PATH = "$SETTINGS_PATH"
CODEX_TTS_VOICE = "Samantha"
CODEX_TTS_RATE = "190"
CFG
