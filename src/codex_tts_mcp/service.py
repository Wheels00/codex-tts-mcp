from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path
from typing import Any

from .config import (
    DEFAULT_HELPER_LABEL,
    DEFAULT_MENUBAR_LABEL,
    DEFAULT_MUTE_STATE_PATH,
    DEFAULT_SETTINGS_PATH,
    DEFAULT_RATE,
    DEFAULT_SOCKET_PATH,
    DEFAULT_VOICE,
)
from .helper_client import HelperClientError, helper_health, helper_list_voices, helper_speak
from .logging_utils import setup_logging
from .macos_audio import list_voices_local, run_osascript_say, run_say
from .validation import validate_and_normalize, validate_rate, validate_voice

logger = setup_logging("codex_tts_mcp.service")
EMAIL_FIX_PATTERN = re.compile(r"\s*([@.])\s*")
CONTROL_CHARS_PATTERN = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]")
QUEUE_LOCK = threading.Lock()
QUEUE_TIMERS: dict[str, threading.Timer] = {}
QUEUE_PAYLOADS: dict[str, dict[str, Any]] = {}


def _as_int(value: Any, fallback: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _launchctl_helper_loaded(label: str) -> tuple[bool, str | None]:
    uid = str(os.getuid())
    if shutil.which("launchctl") is None:
        return False, "launchctl not found"
    proc = subprocess.run(
        ["launchctl", "print", f"gui/{uid}/{label}"], capture_output=True, text=True
    )
    if proc.returncode == 0:
        return True, None
    err = (proc.stderr or "").strip()
    return False, err or f"launchctl exit {proc.returncode}"


def _read_mute_state(state_path: Path = DEFAULT_MUTE_STATE_PATH) -> bool:
    if not state_path.exists():
        return False
    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return False
    return bool(data.get("muted", False)) if isinstance(data, dict) else False


def set_mute(
    muted: bool, state_path: Path = DEFAULT_MUTE_STATE_PATH
) -> dict[str, Any]:
    path = Path(state_path).expanduser()
    payload = {"muted": bool(muted)}
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(prefix=".tmp-mute-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle)
            handle.write("\n")
        os.replace(temp_path, path)
    except Exception as exc:  # noqa: BLE001
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        logger.error("tool=set_mute result=error err=%s", exc)
        return {"ok": False, "error": str(exc), "state_path": str(path)}
    logger.info("tool=set_mute result=ok muted=%s", bool(muted))
    return {"ok": True, "muted": bool(muted), "state_path": str(path), "error": None}


def get_mute_status(state_path: Path = DEFAULT_MUTE_STATE_PATH) -> dict[str, Any]:
    path = Path(state_path).expanduser()
    muted = _read_mute_state(path)
    return {"ok": True, "muted": muted, "state_path": str(path), "error": None}


def _read_speech_settings(
    settings_path: Path = DEFAULT_SETTINGS_PATH,
) -> dict[str, Any]:
    path = Path(settings_path).expanduser()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}
    if not isinstance(data, dict):
        return {}

    result: dict[str, Any] = {}
    voice = data.get("voice")
    if isinstance(voice, str):
        try:
            result["voice"] = validate_voice(voice)
        except ValueError:
            pass
    rate = data.get("rate")
    if rate is not None:
        try:
            result["rate"] = validate_rate(int(rate))
        except (TypeError, ValueError):
            pass
    return result


def _effective_default_voice_rate(settings_path: Path) -> tuple[str, int]:
    settings = _read_speech_settings(settings_path)
    raw_voice = settings.get("voice") or os.environ.get("CODEX_TTS_VOICE", DEFAULT_VOICE)
    raw_rate = settings.get("rate")
    if raw_rate is None:
        raw_rate = _as_int(os.environ.get("CODEX_TTS_RATE"), DEFAULT_RATE)

    try:
        voice = validate_voice(str(raw_voice))
    except ValueError:
        voice = DEFAULT_VOICE

    try:
        rate = validate_rate(int(raw_rate))
    except ValueError:
        rate = DEFAULT_RATE

    return voice, rate


def get_speech_settings(
    settings_path: Path = DEFAULT_SETTINGS_PATH,
) -> dict[str, Any]:
    path = Path(settings_path).expanduser()
    voice, rate = _effective_default_voice_rate(path)
    return {
        "ok": True,
        "voice": voice,
        "rate": rate,
        "settings_path": str(path),
        "error": None,
    }


def set_speech_settings(
    voice: str | None = None,
    rate: int | None = None,
    settings_path: Path = DEFAULT_SETTINGS_PATH,
) -> dict[str, Any]:
    path = Path(settings_path).expanduser()
    current = _read_speech_settings(path)

    if voice is None and rate is None:
        return {"ok": False, "error": "voice or rate must be provided"}

    next_voice = current.get("voice")
    next_rate = current.get("rate")

    try:
        if voice is not None:
            next_voice = validate_voice(voice)
        if rate is not None:
            next_rate = validate_rate(int(rate))
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}

    payload = {
        "voice": next_voice or _effective_default_voice_rate(path)[0],
        "rate": next_rate if next_rate is not None else _effective_default_voice_rate(path)[1],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(prefix=".tmp-settings-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle)
            handle.write("\n")
        os.replace(temp_path, path)
    except Exception as exc:  # noqa: BLE001
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        logger.error("tool=set_speech_settings result=error err=%s", exc)
        return {"ok": False, "error": str(exc), "settings_path": str(path)}

    logger.info(
        "tool=set_speech_settings result=ok voice=%s rate=%s",
        payload["voice"],
        payload["rate"],
    )
    return {
        "ok": True,
        "voice": payload["voice"],
        "rate": payload["rate"],
        "settings_path": str(path),
        "error": None,
    }


def _speak_now(
    text: str,
    voice: str | None,
    rate: int | None,
    interrupt: bool,
    prefix_codex: bool,
    socket_path: Path,
    mute_state_path: Path,
    settings_path: Path,
    check_mute: bool = True,
) -> dict[str, Any]:
    default_voice, default_rate = _effective_default_voice_rate(settings_path)
    selected_voice = voice or default_voice
    selected_rate = _as_int(rate, default_rate)

    try:
        args = validate_and_normalize(
            text=text,
            voice=selected_voice,
            rate=selected_rate,
            interrupt=interrupt,
            prefix_codex=prefix_codex,
        )
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "method": "validation",
            "spoken_text": "",
            "voice": selected_voice,
            "rate": selected_rate,
            "error": str(exc),
        }

    if check_mute and _read_mute_state(mute_state_path):
        logger.info("tool=speak method=muted result=ok")
        return {
            "ok": True,
            "method": "muted",
            "spoken_text": args.text,
            "voice": args.voice,
            "rate": args.rate,
            "error": None,
        }

    logger.info("tool=speak method=select text_len=%s", len(args.text))

    try:
        helper_res = helper_speak(
            socket_path=socket_path,
            text=args.text,
            voice=args.voice,
            rate=args.rate,
            interrupt=args.interrupt,
        )
        if helper_res.get("ok"):
            result = {
                "ok": True,
                "method": helper_res.get("method", "helper"),
                "spoken_text": args.text,
                "voice": args.voice,
                "rate": args.rate,
                "error": None,
            }
            logger.info("tool=speak method=%s result=ok", result["method"])
            return result
        helper_error = helper_res.get("error", "helper failed")
        logger.warning("tool=speak method=helper result=error err=%s", helper_error)
    except HelperClientError as exc:
        helper_error = str(exc)
        logger.warning("tool=speak method=helper result=error err=%s", helper_error)

    osa = run_osascript_say(args.text, args.voice, args.rate, args.interrupt)
    if osa.ok:
        logger.info("tool=speak method=osascript result=ok")
        return {
            "ok": True,
            "method": osa.method,
            "spoken_text": args.text,
            "voice": args.voice,
            "rate": args.rate,
            "error": None,
        }

    local = run_say(args.text, args.voice, args.rate, args.interrupt)
    if local.ok:
        logger.info("tool=speak method=say result=ok")
        return {
            "ok": True,
            "method": local.method,
            "spoken_text": args.text,
            "voice": args.voice,
            "rate": args.rate,
            "error": None,
        }

    error_msg = (
        f"helper: {helper_error}; osascript: {osa.error}; say: {local.error}"
    )
    logger.error("tool=speak result=error err=%s", error_msg)
    return {
        "ok": False,
        "method": "failed",
        "spoken_text": args.text,
        "voice": args.voice,
        "rate": args.rate,
        "error": error_msg,
    }


def _muted_response(
    text: str,
    voice: str | None,
    rate: int | None,
    interrupt: bool,
    prefix_codex: bool,
    settings_path: Path,
) -> dict[str, Any]:
    default_voice, default_rate = _effective_default_voice_rate(settings_path)
    selected_voice = voice or default_voice
    selected_rate = _as_int(rate, default_rate)

    try:
        args = validate_and_normalize(
            text=text,
            voice=selected_voice,
            rate=selected_rate,
            interrupt=interrupt,
            prefix_codex=prefix_codex,
        )
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "method": "validation",
            "spoken_text": "",
            "voice": selected_voice,
            "rate": selected_rate,
            "error": str(exc),
        }

    return {
        "ok": True,
        "method": "muted",
        "spoken_text": args.text,
        "voice": args.voice,
        "rate": args.rate,
        "error": None,
    }


def _flush_queue_key(
    queue_key: str, socket_path: Path, mute_state_path: Path, settings_path: Path
) -> dict[str, Any]:
    with QUEUE_LOCK:
        payload = QUEUE_PAYLOADS.pop(queue_key, None)
        timer = QUEUE_TIMERS.pop(queue_key, None)
    if timer is not None:
        timer.cancel()
    if payload is None:
        return {
            "ok": False,
            "method": "queue_flush",
            "error": f"no queued announcement for key={queue_key}",
        }
    return _speak_now(
        text=payload["text"],
        voice=payload["voice"],
        rate=payload["rate"],
        interrupt=payload["interrupt"],
        prefix_codex=payload["prefix_codex"],
        socket_path=socket_path,
        mute_state_path=mute_state_path,
        settings_path=settings_path,
    )


def _schedule_debounce(
    queue_key: str,
    payload: dict[str, Any],
    debounce_ms: int,
    socket_path: Path,
    mute_state_path: Path,
    settings_path: Path,
) -> None:
    def _timer_fire() -> None:
        try:
            _flush_queue_key(queue_key, socket_path, mute_state_path, settings_path)
        except Exception as exc:  # noqa: BLE001
            logger.error("tool=speak mode=debounce timer_error=%s", exc)

    with QUEUE_LOCK:
        prev = QUEUE_TIMERS.pop(queue_key, None)
        if prev is not None:
            prev.cancel()
        QUEUE_PAYLOADS[queue_key] = payload
        timer = threading.Timer(max(0.2, debounce_ms / 1000.0), _timer_fire)
        timer.daemon = True
        QUEUE_TIMERS[queue_key] = timer
        timer.start()


def speak(
    text: str,
    voice: str | None = None,
    rate: int | None = None,
    interrupt: bool = False,
    prefix_codex: bool = False,
    socket_path: Path = DEFAULT_SOCKET_PATH,
    mute_state_path: Path = DEFAULT_MUTE_STATE_PATH,
    settings_path: Path = DEFAULT_SETTINGS_PATH,
    queue_mode: str = "immediate",
    queue_key: str = "default",
    debounce_ms: int | None = None,
) -> dict[str, Any]:
    mode = (queue_mode or "immediate").strip().lower()
    key = (queue_key or "default").strip()
    if not key:
        key = "default"
    if len(key) > 64:
        return {"ok": False, "method": "validation", "error": "queue_key too long"}

    if mode not in {"immediate", "debounce", "flush"}:
        return {"ok": False, "method": "validation", "error": "invalid queue_mode"}

    if _read_mute_state(mute_state_path):
        # Fast-path: no helper call/queue scheduling when muted.
        with QUEUE_LOCK:
            pending = QUEUE_TIMERS.pop(key, None)
            if pending is not None:
                pending.cancel()
            QUEUE_PAYLOADS.pop(key, None)
        return _muted_response(text, voice, rate, interrupt, prefix_codex, settings_path)

    if mode == "flush":
        if text and text.strip():
            with QUEUE_LOCK:
                pending = QUEUE_TIMERS.pop(key, None)
                if pending is not None:
                    pending.cancel()
                QUEUE_PAYLOADS.pop(key, None)
            return _speak_now(
                text=text,
                voice=voice,
                rate=rate,
                interrupt=interrupt,
                prefix_codex=prefix_codex,
                socket_path=socket_path,
                mute_state_path=mute_state_path,
                settings_path=settings_path,
                check_mute=False,
            )
        return _flush_queue_key(key, socket_path, mute_state_path, settings_path)

    if mode == "debounce":
        ms = _as_int(
            debounce_ms, _as_int(os.environ.get("CODEX_TTS_DEBOUNCE_MS"), 15000)
        )
        if ms < 200 or ms > 300000:
            return {
                "ok": False,
                "method": "validation",
                "error": "debounce_ms must be between 200 and 300000",
            }
        payload = {
            "text": text,
            "voice": voice,
            "rate": rate,
            "interrupt": interrupt,
            "prefix_codex": prefix_codex,
        }
        _schedule_debounce(
            key, payload, ms, socket_path, mute_state_path, settings_path
        )
        default_voice, default_rate = _effective_default_voice_rate(settings_path)
        logger.info("tool=speak mode=debounce key=%s ms=%s queued=1", key, ms)
        return {
            "ok": True,
            "method": "debounced_queue",
            "queued": True,
            "queue_key": key,
            "debounce_ms": ms,
            "spoken_text": "",
            "voice": voice or default_voice,
            "rate": _as_int(rate, default_rate),
            "error": None,
        }

    return _speak_now(
        text=text,
        voice=voice,
        rate=rate,
        interrupt=interrupt,
        prefix_codex=prefix_codex,
        socket_path=socket_path,
        mute_state_path=mute_state_path,
        settings_path=settings_path,
        check_mute=False,
    )


def list_voices(socket_path: Path = DEFAULT_SOCKET_PATH) -> dict[str, Any]:
    logger.info("tool=list_voices")
    try:
        res = helper_list_voices(socket_path)
        if res.get("ok"):
            return {
                "ok": True,
                "voices": res.get("voices", []),
                "method": res.get("method", "helper"),
            }
    except HelperClientError:
        pass

    voices = list_voices_local()
    return {
        "ok": bool(voices),
        "voices": voices,
        "method": "say_local",
        "error": None if voices else "no voices available",
    }


def healthcheck(socket_path: Path = DEFAULT_SOCKET_PATH) -> dict[str, Any]:
    logger.info("tool=healthcheck")
    helper_ok = False
    helper_error = None
    helper_diag: dict[str, Any] = {}

    if socket_path.exists():
        try:
            helper_diag = helper_health(socket_path)
            helper_ok = bool(helper_diag.get("ok"))
        except HelperClientError as exc:
            helper_error = str(exc)
    else:
        helper_error = f"socket not found: {socket_path}"

    loaded, launchctl_error = _launchctl_helper_loaded(DEFAULT_HELPER_LABEL)
    menubar_loaded, menubar_error = _launchctl_helper_loaded(DEFAULT_MENUBAR_LABEL)
    mute = get_mute_status()
    speech_settings = get_speech_settings()
    default_voice = speech_settings.get("voice", DEFAULT_VOICE)
    default_rate = _as_int(speech_settings.get("rate"), DEFAULT_RATE)
    voices = list_voices_local()

    diagnostics = []
    if not loaded:
        diagnostics.append(
            "LaunchAgent is not loaded. Run scripts/install.sh and log in to GUI session."
        )
    if not socket_path.exists():
        diagnostics.append("Helper socket missing. Verify helper daemon startup and socket path.")
    if helper_error:
        diagnostics.append(f"Helper unreachable: {helper_error}")
    if not voices:
        diagnostics.append("No macOS voices detected (`say -v ?` failed).")
    if not menubar_loaded:
        diagnostics.append(
            "Menu bar mute app is not loaded. Run scripts/install.sh to install/start it."
        )

    ok = loaded and socket_path.exists() and (helper_ok or helper_error is None)

    return {
        "ok": ok,
        "audio": {
            "say_binary": shutil.which("say") is not None,
            "voices_count": len(voices),
            "default_voice": default_voice,
            "default_rate": default_rate,
        },
        "helper": {
            "label": DEFAULT_HELPER_LABEL,
            "socket_path": str(socket_path),
            "socket_exists": socket_path.exists(),
            "reachable": helper_ok,
            "error": helper_error,
            "details": helper_diag,
        },
        "launchagent": {
            "loaded": loaded,
            "error": launchctl_error,
        },
        "menubar_launchagent": {
            "loaded": menubar_loaded,
            "error": menubar_error,
        },
        "mute": mute,
        "speech_settings": speech_settings,
        "diagnostics": diagnostics,
    }


def _normalize_vocab_term(value: str) -> str:
    cleaned = CONTROL_CHARS_PATTERN.sub(" ", value)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if "@" in cleaned:
        cleaned = EMAIL_FIX_PATTERN.sub(r"\1", cleaned.lower()).replace(" ", "")
    return cleaned


def _read_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    try:
        return path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []


def _write_lines(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(prefix=".tmp-vocab-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            for line in lines:
                if line:
                    handle.write(line)
                    handle.write("\n")
        os.replace(temp_path, path)
    except Exception:  # noqa: BLE001
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise


def _dedupe_keep_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def update_vocabulary(
    terms: list[str],
    local_dict_path: Path | None = None,
    sync_tsv_path: Path | None = None,
) -> dict[str, Any]:
    local_path = Path(
        local_dict_path
        or os.environ.get(
            "CODEX_VOCAB_LOCAL_DICT", "~/Library/Spelling/LocalDictionary"
        )
    ).expanduser()
    sync_path = Path(
        sync_tsv_path
        or os.environ.get(
            "CODEX_VOCAB_SYNC_TSV",
            "~/Library/Mobile Documents/com~apple~CloudDocs/CodexVocabulary/text_replacements_candidates.tsv",
        )
    ).expanduser()

    if not isinstance(terms, list) or not terms:
        return {"ok": False, "error": "terms must be a non-empty list of strings"}
    if len(terms) > 200:
        return {"ok": False, "error": "too many terms (max 200)"}

    normalized: list[str] = []
    for term in terms:
        if not isinstance(term, str):
            return {"ok": False, "error": "all terms must be strings"}
        value = _normalize_vocab_term(term)
        if not value:
            continue
        if len(value) > 254:
            return {"ok": False, "error": f"term too long: {value[:32]}..."}
        normalized.append(value)

    normalized = _dedupe_keep_order(normalized)
    if not normalized:
        return {"ok": False, "error": "no valid terms after normalization"}

    logger.info("tool=update_vocabulary terms=%s", len(normalized))

    local_existing = _read_lines(local_path)
    local_merged = _dedupe_keep_order(local_existing + normalized)
    local_added = len(local_merged) - len(_dedupe_keep_order(local_existing))

    sync_existing = [line.replace("\\t", "\t") for line in _read_lines(sync_path)]
    sync_pairs = [f"{term}\t{term}" for term in normalized]
    sync_merged = _dedupe_keep_order(sync_existing + sync_pairs)
    sync_added = len(sync_merged) - len(_dedupe_keep_order(sync_existing))

    try:
        _write_lines(local_path, local_merged)
        _write_lines(sync_path, sync_merged)
    except Exception as exc:  # noqa: BLE001
        logger.error("tool=update_vocabulary result=error err=%s", exc)
        return {"ok": False, "error": str(exc)}

    result = {
        "ok": True,
        "added_local": local_added,
        "added_synced": sync_added,
        "normalized_terms": normalized,
        "local_dict_path": str(local_path),
        "sync_tsv_path": str(sync_path),
    }
    logger.info(
        "tool=update_vocabulary result=ok local_added=%s sync_added=%s",
        local_added,
        sync_added,
    )
    return result
