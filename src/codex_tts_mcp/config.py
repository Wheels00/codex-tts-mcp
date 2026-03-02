from __future__ import annotations

import os
from pathlib import Path

APP_DIR = Path(os.path.expanduser("~/Library/Application Support/codex-tts-mcp"))
DEFAULT_SOCKET_PATH = Path(
    os.environ.get("CODEX_TTS_SOCKET", str(APP_DIR / "tts.sock"))
)
DEFAULT_MUTE_STATE_PATH = Path(
    os.environ.get("CODEX_TTS_MUTE_STATE", str(APP_DIR / "mute_state.json"))
)
DEFAULT_HELPER_LABEL = os.environ.get("CODEX_TTS_HELPER_LABEL", "com.codex.tts.helper")
DEFAULT_MENUBAR_LABEL = os.environ.get(
    "CODEX_TTS_MENUBAR_LABEL", "com.codex.tts.menubar"
)
DEFAULT_VOICE = os.environ.get("CODEX_TTS_VOICE", "Samantha")
DEFAULT_RATE = int(os.environ.get("CODEX_TTS_RATE", "190"))
MAX_TEXT_LENGTH = int(os.environ.get("CODEX_TTS_MAX_TEXT", "500"))
