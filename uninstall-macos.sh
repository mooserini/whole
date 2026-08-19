#!/bin/bash
set -euo pipefail
LABEL="com.moosenberg.whole-frontmost"
GUI="gui/$(id -u)"
PLIST="$HOME/Library/LaunchAgents/${LABEL}.plist"
launchctl bootout "$GUI/$LABEL" 2>/dev/null || true
rm -f "$PLIST"
echo "unloaded $LABEL — film stops. trail.jsonl stays."
