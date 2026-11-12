#!/bin/bash
# Start Reachy the greeter with the right settings, checking each part on the way.
#   ./scripts/start.sh        (from ~/Projects/reachy-mini; Ctrl+C stops everything)
# Optional in .env: REACHY_VOLUME=60
set -u
cd "$(dirname "$0")/.."
VOLUME=$(grep -E '^REACHY_VOLUME=' .env 2>/dev/null | cut -d= -f2)
VOLUME=${VOLUME:-60}
mkdir -p logs
ok()   { printf '  \033[32m✔\033[0m %s\n' "$1"; }
warn() { printf '  \033[33m!\033[0m %s\n' "$1"; }
fail() { printf '  \033[31m✘\033[0m %s\n' "$1"; exit 1; }

echo "Starting Reachy…"

# 1. Robot plugged in?
PORT=$(ls /dev/cu.usbmodem* 2>/dev/null | head -1)
[ -n "$PORT" ] || fail "Reachy's USB isn't connected. Plug it into the Mac and switch his power on."
ok "USB connected ($PORT)"

# 2. Stop anything left over from last time.
pkill -f greeter.main 2>/dev/null; pkill -f reachy-mini-daemon 2>/dev/null; sleep 2

# 3. Mic check before the daemon grabs the device. Total silence (-91 dB) = replug USB.
IDX=$(ffmpeg -hide_banner -f avfoundation -list_devices true -i "" 2>&1 | sed -n '/audio devices/,$p' \
      | grep "Reachy Mini Audio" | sed -E 's/.*\[([0-9]+)\] Reachy.*/\1/')
if [ -n "$IDX" ]; then
  LEVEL=$(ffmpeg -hide_banner -f avfoundation -i ":$IDX" -t 2 -af volumedetect -f null - 2>&1 \
          | grep max_volume | sed -E 's/.*max_volume: (-?[0-9.]+) dB/\1/')
  if [ "${LEVEL%%.*}" -le -90 ] 2>/dev/null; then
    fail "Reachy's mic is silent (${LEVEL} dB). Unplug his USB for 5 seconds, plug it back in, and run this again."
  fi
  ok "Mic hears sound (${LEVEL} dB)"
else
  warn "Couldn't find 'Reachy Mini Audio' to test the mic. Is the USB plugged in?"
fi

# 4. Daemon (motors + camera). First start after a reboot can take 2–4 minutes.
.venv/bin/reachy-mini-daemon -p "$PORT" --headless > daemon.log 2>&1 &
DAEMON=$!
# Stop process $1 politely; force it after 5 s if it hangs (the app sometimes does).
stop_pid() {
  kill "$1" 2>/dev/null || return 0
  for i in $(seq 10); do kill -0 "$1" 2>/dev/null || return 0; sleep 0.5; done
  kill -9 "$1" 2>/dev/null
}
cleanup() {
  echo; echo "Stopping Reachy…"
  [ -n "${APP:-}" ] && stop_pid "$APP"
  curl -s -m 3 -X POST localhost:8000/api/media/tracking/disable >/dev/null 2>&1
  stop_pid "$DAEMON"
  echo "Stopped. Safe to power off and unplug."
}
trap cleanup EXIT
trap 'exit 0' INT TERM
printf '  … waiting for the robot software (can take a few minutes)'
for i in $(seq 300); do
  grep -qE "No motors|Motor communication" daemon.log && { echo; fail "Motors not responding. Is Reachy's power switch on?"; }
  grep -q "Daemon started successfully" daemon.log && break
  kill -0 $DAEMON 2>/dev/null || { echo; fail "Robot software crashed. See daemon.log"; }
  sleep 1; [ $((i % 10)) -eq 0 ] && printf '.'
done
echo
grep -q "Daemon started successfully" daemon.log || fail "Robot software didn't start in 5 minutes. See daemon.log"
ok "Robot software running, motors on"

# 5. Camera shared with the app?
if .venv/bin/python -c "from reachy_mini.daemon.utils import is_local_camera_available as f; raise SystemExit(0 if f() else 1)"; then
  ok "Camera connected"
else
  fail "Robot software didn't connect to the camera. Press Ctrl+C and run this again."
fi

# 6. Speaker volume (resets every daemon start).
curl -s -X POST localhost:8000/api/volume/set -H 'Content-Type: application/json' -d "{\"volume\":$VOLUME}" >/dev/null \
  && ok "Speaker volume $VOLUME" || warn "Couldn't set the volume"

# 7. Reachy's app.
.venv/bin/python -m greeter.main > logs/greeter.log 2>&1 &
APP=$!
for i in $(seq 60); do
  grep -q "realtime connected" logs/greeter.log && break
  kill -0 $APP 2>/dev/null || fail "Reachy's app crashed. See logs/greeter.log"
  sleep 0.5
done
grep -q "Using LOCAL backend" logs/greeter.log || warn "App isn't using the camera directly. If he ignores people, restart this script."
grep -q "realtime connected" logs/greeter.log && ok "Voice connected" || warn "Voice not connected yet. Check OPENAI_API_KEY in .env"

EVENT=$(grep -E '^EVENT_NAME=' .env 2>/dev/null | cut -d= -f2-)
echo
echo "Reachy is ready for: ${EVENT:-OpenAI Dev Day}"
echo "Now reload the Luma scanner tab and check it says \"Express Mode On\"."
echo "Press Ctrl+C here to stop Reachy before powering him off."
wait $APP
