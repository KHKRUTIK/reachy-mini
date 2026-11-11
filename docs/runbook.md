# Reachy greeter — event-day runbook

Event: Codex Community Meetup | Melbourne (Reachy says "OpenAI Dev Day"), Sat 21 Nov 2026, doors 10:00.
Everything runs on the host MacBook with Reachy plugged in by USB **and** its own power adapter.

## Setup (allow 15 minutes, finish by 9:30)

1. **Power on Reachy.** Plug in the power adapter, switch it on, and connect the USB cable to the Mac. Bring a **phone hotspot** in case the venue Wi-Fi fails.
2. **Start the daemon** in a terminal and leave it open:
   ```
   cd ~/Projects/reachy-mini && .venv/bin/reachy-mini-daemon -p /dev/cu.usbmodem5AF71339921 --headless
   ```
   The first start after a reboot can take **2–4 minutes**. Check it with
   `curl -s localhost:8000/api/daemon/status`, which should show `"state":"running"`.
   If you see "No motors detected", the power is off. Switch it on and restart the daemon.
3. **Set the volume:**
   `curl -X POST localhost:8000/api/volume/set -H 'Content-Type: application/json' -d '{"volume":60}'`
4. **Open the scanner in Chrome:** `https://luma.com/check-in/evt-ZLcgMdLTqHF8bK3/scan`
   - Camera: **Reachy Mini Camera**.
   - Check that **Reachy Greeter Bridge** is enabled in `chrome://extensions`.
   - The extension picks **Express** in the Scan Options popup by itself. The header must say **"Express Mode On"**. If it doesn't, choose Express yourself.
5. **Start Reachy's app** in a second terminal:
   ```
   cd ~/Projects/reachy-mini && .venv/bin/python -m greeter.main
   ```
   It's ready when you see `realtime connected (gpt-realtime)`.
6. **Test scan:** scan the test guest **Michael**. You should hear "Welcome, Michael!…". Then **undo Michael's check-in** in the guest list.
7. Place the "hold your QR here" marker about an arm's length in front of Reachy.

## During the event

- **Reachy says "the Luma scanner isn't in Express mode":** the scanner tab was reloaded. Choose Express in the popup.
- **A ticket won't scan:** ask the guest to turn their phone brightness up, open the **ticket** (with their name under the QR code), not the event page, and hold it still at about arm's length. Otherwise, check them in from the guest list.
- **Stop Reachy:** press Ctrl+C in the app terminal, or run `pkill -f greeter.main`. This also stops the head following faces.
- **Restart Reachy:** run the step 5 command again.

## Troubleshooting

| Symptom | Check |
|---|---|
| Luma checks people in but Reachy says nothing | Is the app running? `curl -s localhost:8765/health` should return `{"ok": true}`. Is the extension enabled? Reload it in `chrome://extensions`, then reload the scanner tab. |
| No voice at all | Check `OPENAI_API_KEY` in `~/Projects/reachy-mini/.env`, look for `realtime connected` in the app terminal, and check the volume (step 3). |
| Head stuck or not moving, "Motor communication error" | Check the power. Then restart the daemon (step 2) and the app (step 5). |
| Reachy only talks when someone scans: he ignores people walking up, won't chat, and gives no compliments | The daemon didn't connect to the camera when it started. Check with `grep -c "cannot reach the camera" ~/Projects/reachy-mini/daemon.log`: any number above 0 means the camera feed is missing. Also, at startup the app log shows `Using WebRTC backend` instead of `Using LOCAL backend`. Fix: stop the app, restart the daemon (step 2), start the app (step 5), then reload the scanner tab and check Express Mode is on. |
| Head keeps following faces after stopping | `curl -X POST localhost:8000/api/media/tracking/disable` |
| Camera busy or black in Chrome | Close other apps using the camera and reload the scanner tab. Chrome and the daemon can share the camera. |

## What Reachy says

| Situation | Line |
|---|---|
| New check-in | "Welcome, {First}! MLAI welcomes you to the OpenAI Dev Day!" followed by a compliment: a unique detail if he can spot one, otherwise the colour or style ("That black shirt looks great on you!"), or "And can I just say, you're looking great today!" if he can't see the outfit |
| Re-scan 10–60 s after the welcome | "You're all checked in, {First}! Take a seat whenever you're ready." |
| Already checked in (later) | "Welcome back, {First}! You've already checked in, so take a seat whenever you're ready." |
| Event-page QR instead of the ticket | "Ooh, that's the event link! Open your ticket instead, the one with your name under the QR code." |
| Any other failure | "Hmm, I couldn't check you in. Please find a host at the front desk and they'll sort you out!" |
| Someone waiting without scanning (max once a minute) | "Hi! If you haven't checked in yet, just show me the QR code on your Luma ticket." |
