# Whole

Open local workstream memory. No toll booth.

Pieces rented the film. Whole owns it.

- **Store:** `~/.hermes/whole/` (historic trail, not current truth)
- **Spine stays human:** Apple Notes `Moosenberg Spine` + `USER.md` / `MEMORY.md` + Desktop dual-write
- **Clerk:** Apple on-device Foundation Models via `whole-clerk`
- **Film:** frontmost app + window title. No screen, no OCR, no clipboard
- **Build clerk:** `DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer` (27.0). Do not flip `xcode-select`
- **Monitor:** the menu-bar eye in `WholeMonitor/` — green collecting, yellow
  watching, red offline. The pixel Whole should have had 20 days ago.

## Monitor

```bash
cd ~/Developer/whole/WholeMonitor
make contract-test   # must print CONTRACT OK against the live server
make build && make run
```

Frosted `.popover` glass (house theme, same as Config Guardian). More →
App Behavior holds the two login switches (monitor + collector). Spec by
Little Bird, contract layer rebuilt by Ara — see `WholeMonitor/README.md`.

## Collector

Do not start this from the gateway. Same KeepAlive rule as the kitchen board: **Tom loads it from Terminal.**

```bash
cd ~/Developer/whole
/usr/bin/python3 scripts/frontmost.py --once
./install-macos.sh          # LaunchAgent — Accessibility, not Screen Recording
./uninstall-macos.sh
make health                 # Read-only plist/launchd/process/trail/Accessibility check
```

Writes only when the focused app/title pair changes. Every observation passes
through credential/PII redaction before durable storage. The sanitized JSONL
journal is written and `fsync`ed first; SQLite is a best-effort shadow. A shadow
failure cannot cost the observation, and the next idempotent import repairs it:

- `~/.hermes/whole/whole.db` — SQLite shadow store (WAL, FTS5, provenance)
- `~/.hermes/whole/trail.jsonl` — sanitized recovery/import journal
- `~/.hermes/whole/deny.txt` — optional bundle/title deny rules

Existing historical JSONL is never rewritten. Import is idempotent:

```bash
make shadow
make report
make test
```

Segments are deterministic projections of events. Gaps up to 30 minutes are
counted as an active-time lower bound; longer gaps are `unknown`, never silently
called active or idle. Short same-app title→null→title flickers are excluded
from segments while the underlying observations remain available as receipts.

## Clerk

```bash
cd ~/Developer/whole
make run
.build/debug/whole-clerk --trail ~/.hermes/whole/trail.jsonl --json
```

OpenRouter's free router is the default, not a fallback. Apple on-device stays
available for offline use, alongside Ollama or any OpenAI-compatible endpoint
(Apple's macOS 27 guardrails have gotten twitchy about ordinary workstream
history — observed refusal: "May contain unsafe content"):

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

## Model Context Protocol (MCP) Server

Whole provides a native, zero-dependency MCP server (`scripts/whole_mcp.py`) supporting both stdio and HTTP/SSE transports.

### Local Stdio MCP (Hermes, Claude Code, Cursor)

```bash
cd ~/Developer/whole
make mcp
# or directly:
/usr/bin/python3 scripts/whole_mcp.py --stdio
```

### Tailnet / Remote HTTP-SSE Mode

Pieces OS was trapped on `127.0.0.1:39300`. Whole binds cleanly to Tailscale interfaces without port collisions:

```bash
cd ~/Developer/whole
make mcp-sse
# or custom host/port:
/usr/bin/python3 scripts/whole_mcp.py --sse --host 0.0.0.0 --port 39400
```

### Tools Exposed to Agents

1. **`whole_status`** — Integrity check, active time lower bound, event count, and redactions breakdown.
2. **`whole_health`** — Read-only runtime check for the plist, launchd registration, collector process, trail freshness, and Accessibility access.
3. **`whole_search`** — FTS5 search across past window titles and app context with optional `since_hours` limit.
4. **`whole_timeline`** — Active app segments and durations over a lookback window.
5. **`whole_recent_events`** — Chronological stream of recent sanitized observations.
6. **`whole_standup`** — Invokes Apple Foundation Models (or configured provider) to synthesize an on-demand workstream standup.

The HTTP `/health` endpoint uses the same runtime check. `/api/status` remains the archive/store report used by the dashboard.

## Laws

No Discord. No Pieces port overlap (39300). No fourth todo. No 20GB debate engine. No Screen Recording for v1.
