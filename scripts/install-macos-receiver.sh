#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
label="com.yorguard.receiver"
plist="$HOME/Library/LaunchAgents/$label.plist"
api_base_url="${YORGUARD_API_BASE_URL:-https://gsw.tail8a6b99.ts.net:8443}"
mkdir -p "$(dirname "$plist")"

python_path="$(command -v python3)"
cat > "$plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$label</string>
  <key>ProgramArguments</key>
  <array>
    <string>$python_path</string>
    <string>$repo_root/scripts/yorguard-receiver.py</string>
    <string>--api-base-url</string><string>$api_base_url</string>
    <string>--watch</string><string>300</string>
    <string>--jobs</string>
  </array>
  <key>WorkingDirectory</key><string>$repo_root</string>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>$HOME/Library/Logs/YorGuard-receiver.log</string>
  <key>StandardErrorPath</key><string>$HOME/Library/Logs/YorGuard-receiver.error.log</string>
</dict>
</plist>
EOF

launchctl bootout "gui/$(id -u)" "$plist" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$plist"
launchctl kickstart -k "gui/$(id -u)/$label"
echo "YorGuard Mac receiver installed: $label"
