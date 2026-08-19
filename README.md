# WHOLE

Open local workstream memory. No toll booth.

Pieces rented the film. WHOLE owns it.

- **Store:** `~/.hermes/whole/` (historic trail, not current truth)
- **Spine stays human:** Apple Notes `Moosenberg Spine` + `USER.md` / `MEMORY.md` + Desktop dual-write
- **Clerk:** Apple on-device Foundation Models via `whole-clerk`. Proven 2026-08-19 on a 10-event fixture.
- **Build:** `DEVELOPER_DIR=/Applications/Xcode-beta.app/Contents/Developer` (27.0). `/Applications/Xcode.app` is 26.6 — do not use it for this, do not flip `xcode-select`.
- **Not yet:** collector / launchd. Tom loads that from Terminal when we write it.

## Clerk

```bash
cd ~/Developer/whole
make run
make json
.build/debug/whole-clerk --trail ~/.hermes/whole/trail.jsonl --json
```

Needs Apple Intelligence. Context is ~4096 tokens; the clerk slices newest events that fit.

## Laws

No Discord. No tailnet advertise. No fourth todo. No Pieces MCP. No 20GB debate engine.
