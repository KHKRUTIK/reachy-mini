# Reachy Greeter — Design

**Date:** 2026-11-10
**Event:** "Codex Community Meetup | Melbourne — Physical AI & Robotics edition", Saturday 21 Nov 2026, 10:00 am – 2:00 pm AEDT, presented by MLAI. Luma event `evt-ZLcgMdLTqHF8bK3`.
**Hardware:** Reachy Mini Lite (USB + external power) connected to the host's MacBook. SDK `reachy-mini` 1.14.0 installed at `~/Projects/reachy-mini/.venv`. Daemon is started with `reachy-mini-daemon -p /dev/cu.usbmodem5AF71339921`.

## Intent

Reachy Mini sits at the event's front desk as a greeter. Guests hold up the QR code from their Luma ticket. Reachy checks them in **in Luma** and greets them by first name in a bright, friendly voice. After that, guests can chat with Reachy and ask it about the event.

Checking in on Luma matters for more than headcount. The event offers $100 in Codex credits and $50 in OpenAI API credits to eligible guests who check in, and the door team relies on Luma's checked-in list.

## Goals

1. **Check-in in Luma without the Luma API.** The host doesn't want to use the API. Research also found that the API needs Luma Plus and documents no endpoint for checking guests in.
2. **Greet by first name:** "Welcome, {FirstName}! MLAI welcomes you to the OpenAI Dev Day!" Use that exact wording ("OpenAI Dev Day" is the host's choice, even though the Luma page uses a different event name), in a bright, friendly tone, with expressive head and antenna movement.
3. **Conversation:** guests can talk to Reachy by voice, and it answers questions about the event using the content of the Luma event page.
4. **Prompt new arrivals:** when a new person steps up and hasn't checked in, Reachy asks them to show the QR code from their Luma ticket.
5. **Failed scans:** when a scan doesn't end in a successful check-in (pending approval, not registered, already checked in, unreadable or anything else), Reachy says kindly that it couldn't check them in and asks them to find a host at the front desk. It doesn't try to explain why.
6. **Clothing compliment (when relevant):** at the moment of a successful check-in, Reachy takes one snapshot. On the Mac, it finds the guest's face and crops it out, keeping only the area from the shoulders down, and sends only that crop to OpenAI. If something stands out, such as "love the Japanese design on your shirt", Reachy adds a short compliment after the welcome. If nothing stands out, it says nothing extra. Compliments are only about clothing and accessories, never bodies, looks or anything personal. Snapshots are never saved.
7. **Everything uses Reachy's camera.** The host was firm about this: "otherwise it's not cool". No phone or second webcam for scanning.

## Anti-goals (failure even if everything technically works)

- **Talking over people.** Reachy must stop speaking at once when someone starts talking, keep replies to one or two sentences, avoid reacting to background chatter, and leave a short pause after a greeting.
- **Greeting the wrong person.** Reachy only says a name immediately after Luma's scanner confirms a check-in for that name. It never guesses names and never uses face recognition. Greetings are queued one at a time, so two scans close together can't swap names. Anything else gets a nameless "Hi".

## Non-goals

- Using the Luma public API or Luma's undocumented internal web API with session cookies. Both are explicitly out.
- Face recognition or storing guests' faces or other biometric data.
- Sending images that include guests' faces to any cloud service. The Pollen app's general "camera/vision" tool, which sends frames to the model, is **turned off**. The only image sent anywhere is the face-free crop described in goal 6.
- Using a separate phone or webcam for the Luma scanner.
- Registering, approving or editing guests.
- A screen-based UI for guests. Interaction is by voice and movement only.

## Decided architecture

These choices were agreed with the host:

1. **Luma's own web scanner does the check-in.** The scanner page is `https://luma.com/check-in/evt-ZLcgMdLTqHF8bK3/scan`. It is open in Chrome on the Mac, logged in as the host, with **Reachy Mini Camera** selected as its camera and **Express Mode** on, so it checks guests in as soon as it reads a code. The host has confirmed that the scanner opens and shows Reachy's camera feed.
2. **A Chrome extension connects the scanner to Reachy.** A small extension, which we write and load unpacked, watches the scanner tab. When the scanner shows a result, the extension reads the result type (success or something else) and the guest's name, then sends an event to the Reachy app on localhost. This link is what's missing today: the host tried the scanner before, and Reachy had no idea a check-in had happened.
3. **The voice comes from OpenAI realtime voice** (`gpt-realtime`), built on Pollen Robotics' [reachy_mini_conversation_app](https://github.com/pollen-robotics/reachy_mini_conversation_app) with its OpenAI backend. That app already handles realtime voice, the camera, head tracking and expressive movement. We add the check-in greeting, the failure handling, the new-arrival prompt and the event knowledge.
4. **Event knowledge comes from the Luma event page.** It's fetched before the event or when the app starts, and given to the model as context. The model is told to answer only from that context, say "ask a host at the front desk" when it doesn't know, and keep answers short.
5. **Backup: the CSV and "Reachy pass" emails** (suggested by the host). If the extension can't reliably read names from the scanner, export the guest CSV. It includes a check-in QR URL with ticket keys, plus names. Optionally, send each guest a "Reachy pass" email with that QR code. Luma accepts ticket keys, and the Reachy app can then match the code it sees to a name locally. The catch is that the CSV doesn't include people who register after it's exported. This backup is only needed if the extension approach fails during testing.

## Known facts from research

- Luma QR codes contain `https://luma.com/check-in/{event-id}?pk={key}`. Guests' emailed tickets carry **guest keys** (`g-…`). The CSV export carries **ticket keys**, which are shorter. Both are valid for check-in, but they don't match each other.
- An ordinary phone camera app does not check guests in. Luma's scanner (web or app) does.
- macOS normally lets Chrome and the Reachy app use Reachy's camera at the same time. **Test this first.** If the Reachy daemon's media pipeline locks the camera, the decided backup is for the Reachy app to own Reachy's camera and republish its frames as a virtual camera (for example OBS Virtual Camera via `pyvirtualcam`). Chrome then selects that virtual camera for the Luma scanner, so scanning still happens through Reachy's eyes.
- Event page content currently available: the agenda (10:00 welcome, 10:15–1:00 build time, 1:00–1:45 demos), hosts (Callum Holt, Dr Sam Donegan, Advita Velury, Alan Philip), speaker Martin Kemka, bring a laptop and charger, the credits offer, and registration needs approval. The venue address only appears after registration.

## Calls made by the designer (not discussed with the host; easy to change)

- **Repeat results are ignored.** Express Mode may re-read a ticket that's still being held up. Any result for the same guest name within 60 seconds of their welcome is ignored, so a guest never hears "please see a host" right after "Welcome, Sam!".
- **Check-ins take priority over chat.** A scan result cuts into any conversation in progress. Reachy stops, greets the new guest, and keeps chat short. The event is small (about 14 going and 5 pending), so queueing scans is not a concern. Hosts may also scan with their phones, and those check-ins won't reach Reachy, which is expected.
- **QR prompt wording.** Without face recognition, Reachy can't tell new guests from returning ones, so the prompt is worded to work for both: "Hi! If you haven't checked in yet, just show me the QR code on your Luma ticket." It's only said after a face has been present for about 4 seconds with no scan, and at most once every 30 seconds.
- **No offline mode.** If the venue internet fails, both the Luma scanner and the voice stop working, and hosts check guests in manually. Bringing a phone hotspot is recommended.

## Left to the builder

- How the extension detects a result: DOM mutation observer, polling or anything else, plus the selectors it uses, how it pulls out the first name, and the message format and transport (HTTP POST or WebSocket to localhost).
- Whether to fork, vendor or extend the Pollen conversation app, and how to add the greeting and failure handling to its control flow, such as injecting a forced utterance through the realtime session or using a separate TTS call in the same voice.
- How to detect a new arrival and how long to wait before prompting (face detection, how long the face is present, a cooldown so the same person isn't prompted twice).
- Turn-taking settings (VAD sensitivity, barge-in, response length limits), tuned to meet the anti-goals.
- How the robot moves for the greeting and the failure response.
- A dry-run plan: test end to end with a real test registration well before 21 Nov.

## Success

On the day, a guest holds up their ticket, Luma's count goes up by one, and within about two seconds Reachy turns to them and says "Welcome, {FirstName}! MLAI welcomes you to the OpenAI Dev Day!" Failed scans send people to the front desk. Reachy can answer basic event questions, never talks over anyone, and never uses the wrong name.
