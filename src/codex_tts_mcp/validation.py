from __future__ import annotations

import re
from dataclasses import dataclass

from .config import MAX_TEXT_LENGTH

VOICE_PATTERN = re.compile(r"^[A-Za-z0-9 _'()-]{1,64}$")
CONTROL_CHARS_PATTERN = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]")


@dataclass(frozen=True)
class ValidatedSpeakArgs:
    text: str
    voice: str
    rate: int
    interrupt: bool
    prefix_codex: bool


def ensure_prefix_codex(text: str, enabled: bool) -> str:
    stripped = text.strip()
    if not enabled:
        return stripped
    if stripped.lower().startswith("codex "):
        return stripped
    if stripped.lower() == "codex":
        return "codex"
    return f"codex {stripped}" if stripped else "codex"


def sanitize_text(text: str) -> str:
    cleaned = CONTROL_CHARS_PATTERN.sub(" ", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def validate_voice(voice: str) -> str:
    value = voice.strip()
    if not value:
        raise ValueError("voice cannot be empty")
    if not VOICE_PATTERN.match(value):
        raise ValueError("voice contains unsupported characters")
    return value


def validate_rate(rate: int) -> int:
    if rate < 80 or rate > 400:
        raise ValueError("rate must be between 80 and 400")
    return rate


def validate_and_normalize(
    text: str,
    voice: str,
    rate: int,
    interrupt: bool,
    prefix_codex: bool,
) -> ValidatedSpeakArgs:
    if not isinstance(text, str):
        raise ValueError("text must be a string")
    if len(text) > MAX_TEXT_LENGTH:
        raise ValueError(f"text exceeds max length ({MAX_TEXT_LENGTH})")

    cleaned = sanitize_text(text)
    if not cleaned:
        raise ValueError("text cannot be empty")

    spoken = ensure_prefix_codex(cleaned, prefix_codex)
    if len(spoken) > MAX_TEXT_LENGTH + 6:
        raise ValueError("text too long after prefix handling")

    return ValidatedSpeakArgs(
        text=spoken,
        voice=validate_voice(voice),
        rate=validate_rate(int(rate)),
        interrupt=bool(interrupt),
        prefix_codex=bool(prefix_codex),
    )

