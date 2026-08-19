# WHOLE

Open local workstream memory. No toll booth.

Pieces rented the film. WHOLE owns it.

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

## Laws

No Discord. No tailnet advertise. No fourth todo. No Pieces MCP. No 20GB debate engine. No Screen Recording for v1.
