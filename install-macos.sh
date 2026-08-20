#!/bin/bash
# Load Whole frontmost collector as a user LaunchAgent.
# Run from Terminal, not the gateway. Do not start this from README.
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
LABEL="com.moosenberg.whole-frontmost"
PLIST="$HOME/Library/LaunchAgents/${LABEL}.plist"
GUI="gui/$(id -u)"
STORE="${WHOLE_STORE:-$HOME/.hermes/whole}"
SCRIPT="$DIR/scripts/frontmost.py"
# /usr/bin/python3 is an Xcode stub. With Xcode.app 26.6 unlicensed it
# exits 69 from launchd. Pin the Command Line Tools interpreter.
PY="/Library/Developer/CommandLineTools/usr/bin/python3"
if [[ ! -x "$PY" ]]; then
  echo "missing $PY — install CLT 27, do not point this at Xcode.app" >&2
  exit 1
fi

mkdir -p "$HOME/Library/LaunchAgents" "$STORE"

cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${LABEL}</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>DEVELOPER_DIR</key>
    <string>/Library/Developer/CommandLineTools</string>
  </dict>
  <key>ProgramArguments</key>
  <array>
    <string>${PY}</string>
    <string>${SCRIPT}</string>
    <string>--store</string>
    <string>${STORE}</string>
    <string>--interval</string>
    <string>8</string>
  </array>
  <key>WorkingDirectory</key>
  <string>${DIR}</string>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>ProcessType</key>
  <string>Background</string>
  <key>StandardOutPath</key>
  <string>${STORE}/frontmost.log</string>
  <key>StandardErrorPath</key>
  <string>${STORE}/frontmost.log</string>
</dict>
</plist>
EOF

launchctl bootout "$GUI/$LABEL" 2>/dev/null || true
launchctl bootstrap "$GUI" "$PLIST"
launchctl enable "$GUI/$LABEL" 2>/dev/null || true
sleep 0.3
echo "loaded $LABEL"
echo "trail: $STORE/trail.jsonl"
echo "log:   $STORE/frontmost.log"
echo
echo "Permission: Accessibility for /usr/bin/osascript (and python3 if prompted)."
echo "Not Screen Recording. No OCR."
echo "revoke: $DIR/uninstall-macos.sh"
