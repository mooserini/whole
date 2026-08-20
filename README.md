# Whole

Open local workstream memory. No toll booth.

Pieces rented the film. Whole owns it.

- **Store:** `~/.hermes/whole/` (historic trail, not current truth)
- **Spine stays human:** Apple Notes `Moosenberg Spine` + `USER.md` / `MEMORY.md` + Desktop dual-write
- **Clerk:** Apple on-device Foundation Models via `whole-clerk`
- **Film:** frontmost app + window title. No screen, no OCR, no clipboard
- **Build clerk:** `DEVELOPER_DIR=/Applications/Xcode-beta.app/Contents/Developer` (27.0). Do not flip `xcode-select`

## Collector

Do not start this from the gateway. Same KeepAlive rule as the kitchen board: **Tom loads it from Terminal.**

```bash
cd ~/Developer/whole
/usr/bin/python3 scripts/frontmost.py --once
./install-macos.sh          # LaunchAgent — Accessibility, not Screen Recording
./uninstall-macos.sh
```

Writes `~/.hermes/whole/trail.jsonl` only when the focused app/title pair changes. Deny list: `~/.hermes/whole/deny.txt`.

## Clerk

```bash
cd ~/Developer/whole
make run
.build/debug/whole-clerk --trail ~/.hermes/whole/trail.jsonl --json
```

Apple Foundation Models is the default, not a lock-in. The same clerk can use
Ollama, OpenRouter's free router, or any OpenAI-compatible endpoint:

```bash
# Apple Foundation Models — fully on-device
.build/debug/whole-clerk --trail ~/.hermes/whole/trail.jsonl --json

# Ollama — choose any locally installed model
.build/debug/whole-clerk --provider ollama --model qwen3.5:9b --trail ~/.hermes/whole/trail.jsonl --json

# OpenRouter — OPENROUTER_API_KEY stays in the environment
.build/debug/whole-clerk --provider openrouter --trail ~/.hermes/whole/trail.jsonl --json

# Any OpenAI-compatible service — key is read from WHOLE_API_KEY
.build/debug/whole-clerk --provider openai-compatible \
  --base-url https://example.test/v1 --model model-id \
  --trail ~/.hermes/whole/trail.jsonl --json
```

`openrouter/free` is the default OpenRouter model. It capability-filters the
free catalog for the request and then routes among eligible models; it is not a
promise that the most complex request receives the strongest free model.

## Laws

No Discord. No tailnet advertise. No fourth todo. No Pieces MCP. No 20GB debate engine. No Screen Recording for v1.
