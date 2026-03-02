# AI-Exposed MCP Tools (codex-tts)

This document is the AI-facing contract for the `codex-tts` MCP server.

## Core Principle

`SPEAK` is pass-through text.
- The server speaks exactly the `text` value provided.
- No automatic prefix or suffix is added.
- Phrase/rule policy (what to say, when to say it) belongs in skills, not in the MCP server.

## Tool: `speak`

Purpose:
- Audible speech with helper-first reliability, optional queueing, mute awareness.

Parameters:
- `text: string` required
- `voice: string` optional
- `rate: int` optional
- `interrupt: bool` optional
- `prefix_codex: bool` optional (deprecated; ignored)
- `queue_mode: "immediate"|"debounce"|"flush"` optional
- `queue_key: string` optional
- `debounce_ms: int` optional

Behavior:
- If muted, returns success with `method="muted"` and does not play audio.
- If `voice/rate` omitted, uses shared settings (`speech_settings.json`).
- `debounce` coalesces intermediate messages.
- `flush` emits the final message once for a queue key.

Returns:
- `{ ok, method, spoken_text, voice, rate, error? }`

## Tool: `set_mute`

Purpose:
- Enable/disable speech globally.

Parameters:
- `muted: bool`

Returns:
- `{ ok, muted, state_path, error? }`

## Tool: `get_mute_status`

Purpose:
- Read current global mute state.

Returns:
- `{ ok, muted, state_path, error? }`

## Tool: `set_speech_settings`

Purpose:
- Set default voice/rate used by `speak` when omitted.

Parameters:
- `voice: string` optional
- `rate: int` optional

Returns:
- `{ ok, voice, rate, settings_path, error? }`

## Tool: `get_speech_settings`

Purpose:
- Read effective default speech settings.

Returns:
- `{ ok, voice, rate, settings_path, error? }`

## Tool: `list_voices`

Purpose:
- Return available macOS voices.

Returns:
- `{ ok, voices, method, error? }`

## Tool: `healthcheck`

Purpose:
- Diagnostics for helper, menu bar launch agent, mute/settings, and voices.

Returns:
- `{ ok, audio, helper, launchagent, menubar_launchagent, mute, speech_settings, diagnostics }`

## Tool: `update_vocabulary`

Purpose:
- Update dictation vocabulary in both local dictionary and iCloud candidate TSV.

Parameters:
- `terms: string[]`

Returns:
- `{ ok, added_local, added_synced, normalized_terms, local_dict_path, sync_tsv_path, error? }`
