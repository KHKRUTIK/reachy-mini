#!/bin/bash
# Stop Reachy cleanly (app, head tracking, robot software) before powering off / unplugging.
cd "$(dirname "$0")/.."
pkill -INT -f "scripts/start.sh" 2>/dev/null
pkill -f greeter.main 2>/dev/null
sleep 2
curl -s -X POST localhost:8000/api/media/tracking/disable >/dev/null 2>&1
pkill -f reachy-mini-daemon 2>/dev/null
for i in $(seq 20); do pgrep -f "reachy-mini-daemon|greeter.main" >/dev/null || break; sleep 0.5; done
if pgrep -f "reachy-mini-daemon|greeter.main" >/dev/null; then echo "Still running — try again in a few seconds."; exit 1; fi
echo "Reachy is stopped. Safe to power off and unplug."
