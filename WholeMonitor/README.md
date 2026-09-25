# WholeMonitor

A SwiftUI menu bar extra that monitors your local Whole workstream daemon.
Green means collecting, yellow means watching, red means offline — never be
in the dark about Whole again (it sat offline Sep 10–24 with no witness).

Designed by Little Bird, rebuilt by Ara against the live API contract
(see Origin below).

## Why

Whole was offline from September 10-24 without anyone noticing because there was no ambient status indicator. This fixes that.

## Features

- **Ambient status icon** in the macOS menu bar: green (collecting), yellow (watching — running, nothing new), red (offline), gray (checking)
- **Left-click popover** showing live stats: total observations, active time, privacy boundary counts, last check timestamp
- **Right-click menu** with quick actions: Open Dashboard, Restart Collector, Refresh, Open Whole Folder, Quit
- **Auto-polls** `localhost:39400/health` and `/api/status` every 30 seconds
- **Never leaves you in the dark** again

## Build

Shipped Xcode 27 owns this build. No `.xcodeproj` — plain `swiftc` via Makefile:

```bash
cd ~/Developer/whole/WholeMonitor
make contract-test   # decodes the LIVE server; must print CONTRACT OK
make build           # app bundle + ad-hoc sign
make run             # open it; look at the menu bar
```

The app is a `LSUIElement` (no dock icon, no menu bar). It lives entirely in the status bar.

## Configuration

If Whole runs on a non-standard port, edit `HealthChecker.swift`:
```swift
private let baseURL = "http://127.0.0.1:39400"
```

## Note

The "Restart" action runs `./install-macos.sh` in `~/Developer/whole`
(the real collector restart — there is no `make install-macos` target).
Adjust `StatusBarManager.swift` if your path differs.

## Origin

Spec + first source by Little Bird (`~/.hermes/attachments/`). Ara rebuilt
`Models.swift` with `CodingKeys` for the real nested snake_case API (the
original aimed at a flat camelCase schema that doesn't exist and would have
read permanent red), fixed `NSStatusBar.system`, `executableURL`, and the
restart path, and added the `make contract-test` gate. Credit shared.
