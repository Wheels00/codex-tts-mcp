#!/usr/bin/env python3
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from codex_tts_mcp.service import (
    get_speech_settings,
    get_mute_status,
    healthcheck,
    list_voices,
    set_mute,
    set_speech_settings,
    speak,
    update_vocabulary,
)

mcp = FastMCP("codex-tts")


@mcp.tool(name="speak")
def speak_tool(
    text: str,
    voice: str | None = None,
    rate: int | None = None,
    interrupt: bool = False,
    prefix_codex: bool = False,
    queue_mode: str = "immediate",
    queue_key: str = "default",
    debounce_ms: int | None = None,
) -> dict:
    """Speak text audibly on macOS with helper-first reliability and optional queueing."""
    return speak(
        text=text,
        voice=voice,
        rate=rate,
        interrupt=interrupt,
        prefix_codex=prefix_codex,
        queue_mode=queue_mode,
        queue_key=queue_key,
        debounce_ms=debounce_ms,
    )


@mcp.tool(name="list_voices")
def list_voices_tool() -> dict:
    """List available speech voices."""
    return list_voices()


@mcp.tool(name="healthcheck")
def healthcheck_tool() -> dict:
    """Return helper/audio diagnostics and actionable health information."""
    return healthcheck()


@mcp.tool(name="update_vocabulary")
def update_vocabulary_tool(terms: list[str]) -> dict:
    """Update Mac local dictionary and iCloud-synced text replacement candidate list."""
    return update_vocabulary(terms=terms)


@mcp.tool(name="set_mute")
def set_mute_tool(muted: bool) -> dict:
    """Mute/unmute all speech output from this MCP server."""
    return set_mute(muted=muted)


@mcp.tool(name="get_mute_status")
def get_mute_status_tool() -> dict:
    """Get current mute status used by speak and the menu bar helper."""
    return get_mute_status()


@mcp.tool(name="set_speech_settings")
def set_speech_settings_tool(
    voice: str | None = None, rate: int | None = None
) -> dict:
    """Set default voice/rate used by speak when not explicitly provided."""
    return set_speech_settings(voice=voice, rate=rate)


@mcp.tool(name="get_speech_settings")
def get_speech_settings_tool() -> dict:
    """Get effective default voice/rate and settings file path."""
    return get_speech_settings()


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
