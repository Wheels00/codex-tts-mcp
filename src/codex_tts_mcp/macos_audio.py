from __future__ import annotations

import shlex
import shutil
import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class SpeakExecutionResult:
    ok: bool
    method: str
    error: str | None = None


def _run_command(args: list[str]) -> tuple[int, str]:
    proc = subprocess.run(args, capture_output=True, text=True)
    stderr = (proc.stderr or "").strip()
    return proc.returncode, stderr


def run_say(text: str, voice: str, rate: int, interrupt: bool = False) -> SpeakExecutionResult:
    if shutil.which("say") is None:
        return SpeakExecutionResult(ok=False, method="say", error="say binary not found")
    if interrupt and shutil.which("killall") is not None:
        subprocess.run(["killall", "say"], capture_output=True, text=True)

    rc, stderr = _run_command(["say", "-v", voice, "-r", str(rate), text])
    if rc == 0:
        return SpeakExecutionResult(ok=True, method="say")
    return SpeakExecutionResult(ok=False, method="say", error=stderr or f"say exited {rc}")


def run_osascript_say(
    text: str, voice: str, rate: int, interrupt: bool = False
) -> SpeakExecutionResult:
    if shutil.which("osascript") is None:
        return SpeakExecutionResult(
            ok=False, method="osascript", error="osascript binary not found"
        )

    if interrupt and shutil.which("killall") is not None:
        subprocess.run(["killall", "say"], capture_output=True, text=True)

    escaped_text = text.replace('"', '\\"')
    escaped_voice = voice.replace('"', "")
    script = f'say "{escaped_text}" using "{escaped_voice}" speaking rate {rate}'
    rc, stderr = _run_command(["osascript", "-e", script])
    if rc == 0:
        return SpeakExecutionResult(ok=True, method="osascript")
    return SpeakExecutionResult(
        ok=False, method="osascript", error=stderr or f"osascript exited {rc}"
    )


def list_voices_local() -> list[str]:
    if shutil.which("say") is None:
        return []
    proc = subprocess.run(["say", "-v", "?"], capture_output=True, text=True)
    if proc.returncode != 0:
        return []
    voices = []
    for line in proc.stdout.splitlines():
        if not line.strip():
            continue
        # Output format starts with voice name column.
        voices.append(line.split(maxsplit=1)[0])
    return voices

