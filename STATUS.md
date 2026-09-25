# Whole: Status

Snapshot of where Whole stands. Written from a read-through of the repo (11 commits, last 2026-08-26), not from a fresh test run. README.md stays the how-to; this file is the honest map of what exists and what doesn't.

## Shape

Three pieces, one rule: the sanitized JSONL journal is the source of truth, everything else is a projection that can be rebuilt.

    frontmost.py  ->  trail.jsonl (redacted, fsync'd)  ->  whole_store.py  ->  whole.db (SQLite, WAL, FTS5)
      collector          recovery journal                    idempotent import       events / segments / redactions
                                                                                          |
                                       whole_mcp.py (stdio + HTTP/SSE)  <-----------------+
                                       whole-clerk (Swift, standup synthesis) reads the trail directly

| Piece | Lives in | Size | Job |
|---|---|---|---|
| Collector | `scripts/frontmost.py` | ~230 lines | Poll frontmost app + window title every 8s, write only on change, redact before storage |
| Store | `scripts/whole_store.py` | ~590 lines | Import JSONL into SQLite, build `seg-v2` segments, FTS5 search, report |
| Health | `scripts/whole_health.py` | ~250 lines | Read-only check: plist, launchd, process, trail freshness, Accessibility |
| MCP server | `scripts/whole_mcp.py` | ~1230 lines | Six tools over stdio or HTTP/SSE, plus `/health`, `/api/status` and the dashboard |
| Clerk | `Sources/whole-clerk/` | ~450 lines Swift | Turn a trail into a standup via Apple Foundation Models, Ollama, OpenRouter or any OpenAI-compatible endpoint |

## Working (evidenced by code and tests in the repo)

- Collector with LaunchAgent install/uninstall, pinned to the Command Line Tools python on purpose (the Xcode stub exits 69 under launchd).
- Redaction before durable storage, with a bundle/title deny list (`deny.txt.example` covers password managers).
- Journal-first durability: SQLite failure cannot lose an observation, and the next import repairs it.
- Deterministic segments with an explicit `unknown` state for gaps over 30 minutes.
- MCP tools: `whole_status`, `whole_health`, `whole_search`, `whole_timeline`, `whole_recent_events`, `whole_standup`.
- Provider-agnostic clerk with request/response and configuration tests.
- Python tests for store, MCP and health; Swift tests for the clerk.

## Unfinished

Only items I could tell from the repo. Anything marked (unverified) is a question, not a finding.

- **Clerk reads the trail, not the store.** `whole-clerk` takes `--trail` JSONL and never touches `whole.db`, so the FTS index and segments do nothing for standups yet.
- **Swift package targets macOS 26 and needs Xcode 27 beta** (`DEVELOPER_DIR` is hardcoded in the Makefile). Fine for one machine, a wall for anyone else.
- **`make mcp-sse` binds `0.0.0.0:39400`.** The README frames this as Tailscale-only, but the bind is all interfaces. Whether the server authenticates requests is (unverified).
- **No tests run in this review.** Whether `make test` is green today is (unverified).
- **Two hardcoded paths** (`/Library/Developer/CommandLineTools/usr/bin/python3` and `Xcode-beta.app`) mean install scripts fail fast off this setup.
- **Docs drift:** the README says "Tom loads it from Terminal" and the store path is described as "historic trail, not current truth". Neither is explained in the repo.
- **No schema migration story.** `schema_meta` exists, and I found no migration code (unverified beyond a grep).
- **Retention is undefined.** Nothing I found prunes `trail.jsonl` or the database.

## Laws (from the README)

No Discord. No port 39300 overlap. No fourth todo. No 20GB debate engine. No Screen Recording for v1.

## Candidate next steps (curiosity-ordered, not a roadmap)

1. Let the clerk read segments from `whole.db` instead of raw JSONL.
2. Decide whether the SSE server should be loopback plus Tailscale only, and write that down.
3. Add a retention rule for the journal.
4. Run `make test` and record the result here.

## Fixed 2026-09-25 — dashboard honesty pass
- Collector Daemon card was hardcoded `RUNNING` in static HTML; it now renders
  the real three-state result (`running` / `idle` / `down`) from
  `whole_health.health_report` via a new `collector` block on `/api/status`.
  Change-only semantics respected: loaded-but-quiet reads IDLE, not DOWN.
- "Live Trail" header badge follows the same state (Live / Quiet / Down).
- Privacy Boundary sub-line now reports `residual_sensitive_fields` instead of
  always claiming zero leaked.
- Standup panel no longer spins on "Loading..." forever when the clerk fails;
  it surfaces the failure text. (Observed 2026-09-25: Apple Foundation Models
  refused the trail with "May contain unsafe content" — the on-device
  guardrail tripped on his own workstream history.)

## 2026-09-25 — clerk provider selection
- `/api/standup` now accepts {"provider": "apple"|"ollama"|"openrouter"|"openai-compatible", "model"?}
  (unknown providers fall back to openrouter). Dashboard header has a provider
  <select>, persisted in localStorage; clerk panel subtitle follows it.
- `openrouter` uses the `openrouter/free` router by default. Needs
  OPENROUTER_API_KEY (or WHOLE_API_KEY) in the dashboard server environment.
  Suggested: ~/.hermes/whole/env (chmod 600), sourced at server start.

## 2026-09-25 — openrouter/free becomes the default clerk
- Bare `--json` / `{}` standup / unknown-provider fallback now resolve to
  `openrouter` (`openrouter/free` router), not `apple`. Apple on-device stays
  one flag away (`--provider apple`) for offline use.
- Reason: macOS 27's shipped guardrails refuse ordinary workstream history
  ("May contain unsafe content"); the beta Tom built against was looser.
  Nineteen free routers beat one nervous bouncer.

## 2026-09-25 — monitoring gap: collector was dark Sep 10 → Sep 24
- Whole sat offline ~Sep 10 until ~8h before this session and nothing told
  Tom. The dashboard IS the monitor, but a dead server serves no dashboard —
  without a GUI pixel or a push notification, darkness is silent.
- Deferred per Tom (document-only, no build tonight). Options on the table:
  (a) menu-bar monitor in the hermes-health-monitor pattern (Sep 10),
  polling /health + collector freshness; (b) Hermes cron check that nudges
  Tom when the collector goes quiet; (c) dashboard self-check banner.
- Evidence to calibrate against: trail gap 2026-09-10 → 2026-09-24 in
  ~/.hermes/whole/trail.jsonl; `unknown_gap_seconds` in /api/status.

## 2026-09-25 — off the beta: Xcode 27 shipped is the toolchain
- Verified live: only /Applications/Xcode.app exists (27.0, 27A266a),
  xcode-select points at it. No Xcode-beta on this machine.
- `whole_mcp.py` clerk-spawn DEVELOPER_DIR pointed at the ghost
  `Xcode-beta.app` path; now `Xcode.app`. Makefile comment corrected
  (it still claimed Xcode.app was 26.6).
- Left alone on purpose: `whole_mcp.py.pre-honesty-fix` (frozen backup),
  fixture trail's Aug-19 Xcode-beta window titles (fake history), and the
  beta-era review quotes above (history).

## 2026-09-25 — clerk lenient decode + Xcode path fix
- whole-clerk now salvages the outermost {...} span when a provider ignores
  response_format=json_object and wraps the standup in prose (common on the
  OpenRouter free router, which rotates models). Pure-prose responses still
  surface as an honest error.
- Makefile/README DEVELOPER_DIR updated: Xcode-beta.app no longer exists;
  Xcode.app (27.0, 27A266a) builds the clerk fine.
