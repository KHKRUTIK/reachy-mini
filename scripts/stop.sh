#!/bin/bash
# Stop Reachy cleanly (app, head tracking, robot software) before powering off / unplugging.
cd "$(dirname "$0")/.."
# Stop $1 (a pkill pattern) politely; force it after 5 s if it hangs.
stop() {
  pkill -f "$1" 2>/dev/null
  for i in $(seq 10); do pgrep -f "$1" >/dev/null || return 0; sleep 0.5; done
  pkill -9 -f "$1" 2>/dev/null; sleep 1
}
pkill -INT -f "scripts/start.sh" 2>/dev/null
stop greeter.main
curl -s -m 3 -X POST localhost:8000/api/media/tracking/disable >/dev/null 2>&1
stop reachy-mini-daemon
if pgrep -f "reachy-mini-daemon|greeter.main" >/dev/null; then echo "Still running — try again in a few seconds."; exit 1; fi
echo "Reachy is stopped. Safe to power off and unplug."
