# Discovery notes (Task 1) — 2026-11-10

## Daemon with media
- Command: `.venv/bin/reachy-mini-daemon -p /dev/cu.usbmodem5AF71339921 --headless`. Media works out of the box on macOS, with no extra GStreamer install.
- **On the first start, GStreamer scans its plugin registry, which takes about 2–4 minutes before the API answers.** Later starts are fast. Do one start well before doors open on event day.
- Status reports `camera_specs_name: "lite"` and `no_media: false`. Playback uses CoreAudio device "Reachy Mini Audio".
- SDK (`ReachyMini()`, default LOCAL backend): `media.get_frame()` returns `(1080, 1920, 3)` BGR. Audio in and out are both **16000 Hz, 2 channels**.

## Camera sharing — PASS
- The Luma scanner in Chrome (Reachy Mini Camera, 1920x1080) stayed live while the daemon owned the camera, and a Python client got frames at the same time (confirmed by the host on 2026-11-10). **Task 1b (virtual camera) is not needed.**

## QR scanning findings (from the host's tests)
- The camera has a fixed focus. Close-up codes are too blurry to decode, even with an offline zxing decoder.
- A 13 Pro Max at about arm's length scanned and checked in. An iPhone 12 and a small Android did not.
- Ticket QR codes contain `https://luma.com/check-in/evt-ZLcgMdLTqHF8bK3?pk=g-…`.
- A failed scan logs `FetchError: That guest was not found on this event.` from an `api.luma.com/event/…` call.

## Test guest
- **Michael** (the host's test registration) is the test guest for all check-in tests. Undo his check-in after each test.
