#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import threading
import time
from pathlib import Path
from typing import Any

from codex_tts_mcp.config import DEFAULT_RATE, DEFAULT_SOCKET_PATH, DEFAULT_VOICE
from codex_tts_mcp.logging_utils import setup_logging
from codex_tts_mcp.macos_audio import list_voices_local, run_say
from codex_tts_mcp.validation import validate_and_normalize

logger = setup_logging("codex_tts_mcp.helper")
SHUTDOWN = threading.Event()
SPEAK_LOCK = threading.Lock()


def _safe_unlink(path: Path) -> None:
    try:
        if path.exists() or path.is_socket():
            path.unlink()
    except FileNotFoundError:
        pass


def _response(ok: bool, method: str, **kwargs: Any) -> dict[str, Any]:
    data = {"ok": ok, "method": method}
    data.update(kwargs)
    return data


def _handle_request(payload: dict[str, Any]) -> dict[str, Any]:
    action = payload.get("action")
    if action == "speak":
        try:
            args = validate_and_normalize(
                text=str(payload.get("text", "")),
                voice=str(payload.get("voice", DEFAULT_VOICE)),
                rate=int(payload.get("rate", DEFAULT_RATE)),
                interrupt=bool(payload.get("interrupt", False)),
                prefix_codex=False,
            )
        except Exception as exc:  # noqa: BLE001
            return _response(False, "helper", error=f"validation failed: {exc}")

        wait_start = time.monotonic()
        with SPEAK_LOCK:
            wait_ms = int((time.monotonic() - wait_start) * 1000)
            result = run_say(
                text=args.text,
                voice=args.voice,
                rate=args.rate,
                interrupt=args.interrupt,
            )
        if result.ok:
            return _response(
                True,
                "helper_launchagent_say",
                spoken_text=args.text,
                voice=args.voice,
                rate=args.rate,
                wait_ms=wait_ms,
            )
        return _response(
            False,
            "helper_launchagent_say",
            error=result.error,
            wait_ms=wait_ms,
        )

    if action == "list_voices":
        voices = list_voices_local()
        return _response(True, "helper_launchagent_say", voices=voices)

    if action == "health":
        voices = list_voices_local()
        return _response(
            True,
            "helper_launchagent_say",
            pid=os.getpid(),
            uid=os.getuid(),
            voices_count=len(voices),
            sample_voices=voices[:5],
        )

    return _response(False, "helper", error=f"unknown action: {action}")


def _client_thread(conn: socket.socket) -> None:
    with conn:
        try:
            raw = conn.recv(65536)
            if not raw:
                return
            line = raw.split(b"\n", 1)[0]
            payload = json.loads(line.decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("request must be a JSON object")
            response = _handle_request(payload)
            conn.sendall((json.dumps(response) + "\n").encode("utf-8"))
            logger.info(
                "action=%s method=%s ok=%s",
                payload.get("action"),
                response.get("method"),
                response.get("ok"),
            )
        except Exception as exc:  # noqa: BLE001
            err = _response(False, "helper", error=str(exc))
            conn.sendall((json.dumps(err) + "\n").encode("utf-8"))
            logger.error("request_error=%s", exc)


def _install_signal_handlers() -> None:
    def _handler(signum: int, _frame: Any) -> None:
        logger.info("signal=%s shutting_down=1", signum)
        SHUTDOWN.set()

    signal.signal(signal.SIGTERM, _handler)
    signal.signal(signal.SIGINT, _handler)


def serve(socket_path: Path) -> None:
    socket_path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(socket_path.parent, 0o700)
    _safe_unlink(socket_path)

    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
        server.bind(str(socket_path))
        os.chmod(socket_path, 0o600)
        server.listen(8)
        server.settimeout(1.0)

        logger.info("helper_started socket=%s pid=%s", socket_path, os.getpid())
        while not SHUTDOWN.is_set():
            try:
                conn, _ = server.accept()
            except socket.timeout:
                continue
            thread = threading.Thread(target=_client_thread, args=(conn,), daemon=True)
            thread.start()

    _safe_unlink(socket_path)
    logger.info("helper_stopped socket=%s", socket_path)


def main() -> int:
    parser = argparse.ArgumentParser(description="codex tts helper daemon")
    parser.add_argument(
        "--socket",
        default=str(DEFAULT_SOCKET_PATH),
        help="Unix socket path",
    )
    args = parser.parse_args()

    _install_signal_handlers()
    serve(Path(args.socket).expanduser())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
