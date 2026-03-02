# codex-tts-mcp

Reliable macOS MCP server for audible TTS from agent contexts, with queue-aware announcements, vocabulary sync tools, and a menu bar mute toggle.

## Features

- Helper-first speech path for GUI-session audio reliability:
  1. LaunchAgent helper (`say` in logged-in user session)
  2. `osascript` fallback
  3. direct `say` fallback
- Queue-aware announcements (`immediate`, `debounce`, `flush`)
- Global mute state shared by MCP + menu bar app
- Vocabulary update tool for:
  - `~/Library/Spelling/LocalDictionary`
  - iCloud candidate replacements TSV
- LaunchAgent-backed menu bar toggle: `CodexTTS:On` / `CodexTTS:Mute`

## File tree

```text
.
├── README.md
├── pyproject.toml
├── scripts
│   ├── codex_tts_menubar.swift
│   ├── install.sh
│   ├── print_codex_config.sh
│   └── uninstall.sh
├── src
│   └── codex_tts_mcp
│       ├── __init__.py
│       ├── config.py
│       ├── helper_client.py
│       ├── helper_daemon.py
│       ├── logging_utils.py
│       ├── macos_audio.py
│       ├── mcp_server.py
│       ├── service.py
│       └── validation.py
└── tests
    ├── test_integration_helper_path.py
    ├── test_mute.py
    ├── test_speak_queue.py
    ├── test_validation.py
    └── test_vocab_update.py
```

## Setup (one command)

```bash
cd /path/to/codex-tts-mcp
chmod +x scripts/install.sh scripts/uninstall.sh scripts/print_codex_config.sh
./scripts/install.sh
```

Install script actions:
- Deploys runtime to `~/Library/Application Support/codex-tts-mcp/server`
- Installs/starts helper LaunchAgent
- Builds/installs/starts menu bar mute app LaunchAgent
- Auto-registers `mcp_servers.codex_tts` into `~/.codex/config.toml`

## Register with Codex Desktop

No manual paste is required by default. `install.sh` writes/updates the Codex MCP config automatically.

Optional: inspect the generated block:
```bash
./scripts/print_codex_config.sh
```

## MCP tools

- `speak(text, voice?, rate?, interrupt?, prefix_codex?, queue_mode?, queue_key?, debounce_ms?)`
- `list_voices()`
- `healthcheck()`
- `set_mute(muted)`
- `get_mute_status()`
- `update_vocabulary(terms)`

### Queue pattern for multi-task runs

1. Intermediate completions:
- `queue_mode="debounce"`, shared `queue_key`
2. Final completion:
- `queue_mode="flush"`, same `queue_key`

This gives one final spoken summary instead of one per subtask.

## Menu bar mute

- Menu bar item title shows current state:
  - `CodexTTS:On`
  - `CodexTTS:Mute`
- Toggle mute from menu item.
- MCP `speak` returns `method="muted"` when mute is on.

## Share with Claire (GitHub)

### Publish

```bash
git init
git add .
git commit -m "Initial codex-tts-mcp"
git branch -M main
git remote add origin git@github.com:<you>/codex-tts-mcp.git
git push -u origin main
```

### Claire setup

```bash
git clone git@github.com:<you>/codex-tts-mcp.git
cd codex-tts-mcp
./scripts/install.sh
```
Then she restarts Codex Desktop.

## Tests

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -q
```

## Troubleshooting

- Helper missing:
```bash
launchctl print "gui/$(id -u)/com.codex.tts.helper"
```
- Menu bar app missing:
```bash
launchctl print "gui/$(id -u)/com.codex.tts.menubar"
```
- Socket missing:
```bash
ls -l "$HOME/Library/Application Support/codex-tts-mcp/tts.sock"
```

## Uninstall

```bash
./scripts/uninstall.sh
```
