from __future__ import annotations

import json
import socket
from pathlib import Path
from typing import Any


class HelperClientError(RuntimeError):
    pass


def _send_request(
    socket_path: Path, payload: dict[str, Any], timeout: float = 15.0
) -> dict[str, Any]:
    if not socket_path.exists():
        raise HelperClientError(f"helper socket not found: {socket_path}")

    data = (json.dumps(payload) + "\n").encode("utf-8")
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(timeout)
        client.connect(str(socket_path))
        client.sendall(data)

        chunks: list[bytes] = []
        while True:
            chunk = client.recv(4096)
            if not chunk:
                break
            chunks.append(chunk)
            if b"\n" in chunk:
                break

    if not chunks:
        raise HelperClientError("empty response from helper")

    response_raw = b"".join(chunks).split(b"\n", 1)[0]
    try:
        response = json.loads(response_raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise HelperClientError(f"invalid helper response: {exc}") from exc
    if not isinstance(response, dict):
        raise HelperClientError("invalid helper response type")
    return response


def helper_speak(
    socket_path: Path, text: str, voice: str, rate: int, interrupt: bool
) -> dict[str, Any]:
    # Speech is synchronous in helper; short texts can still take a few seconds.
    timeout = max(8.0, min(60.0, len(text) / 8.0))
    return _send_request(
        socket_path,
        {
            "action": "speak",
            "text": text,
            "voice": voice,
            "rate": rate,
            "interrupt": interrupt,
        },
        timeout=timeout,
    )


def helper_list_voices(socket_path: Path) -> dict[str, Any]:
    return _send_request(socket_path, {"action": "list_voices"})


def helper_health(socket_path: Path) -> dict[str, Any]:
    return _send_request(socket_path, {"action": "health"})
