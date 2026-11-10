# Reachy Greeter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reachy Mini greets guests by first name when Luma's web scanner checks them in through Reachy's camera, gives an optional clothing compliment, prompts new arrivals to show their QR code, sends failed scans to the front desk, and chats about the event using OpenAI realtime voice.

**Architecture:** The Luma web scanner (Chrome, Express Mode, using Reachy's camera) does the real check-in. An unpacked Chrome extension reads each scan result from the page and POSTs it to a local Python app (`greeter/`). That app owns the conversation (OpenAI realtime over WebSocket, with audio through the Reachy SDK media API), decides what to say using pure, tested policy objects, and drives head and antenna moves. The daemon's built-in face tracking provides face presence and makes the head follow faces.

**Tech Stack:** Python 3.12 (`.venv`), `reachy-mini` 1.14.0 SDK and daemon, `openai` (realtime and vision), `aiohttp` (local server), `httpx`, `numpy`, `opencv-python-headless`, `pytest` and `pytest-asyncio`. The Chrome extension uses Manifest V3 with plain JS and is tested with `node --test` (Node 24).

**Spec:** `docs/superpowers/specs/2026-11-10-reachy-greeter-design.md`

## Global Constraints

- Welcome line, exact: `Welcome, {FirstName}! MLAI welcomes you to the OpenAI Dev Day!`. Use a bright, friendly tone.
- Failure line: `Hmm, I couldn't check you in. Please find a host at the front desk and they'll sort you out!`
- QR prompt line: `Hi! If you haven't checked in yet, just show me the QR code on your Luma ticket.`
- No Luma API, public or internal. Luma check-in happens only through Luma's own web scanner in Express Mode.
- No face recognition. No saved images. No frame containing a face is ever sent to a cloud service. The only image that leaves the Mac is the shoulders-down crop for the compliment. If no face is detected in the snapshot, send nothing.
- Never say a name unless it came from a scanner success result received in the last few seconds.
- The local server binds to `127.0.0.1` only.
- Realtime model `gpt-realtime`. Every model name and the voice are set in `.env`, never hard-coded in logic.
- Repeat window: ignore any result for a name welcomed less than 60 s ago. QR prompt: the face must be present for at least 4 s with no scan, and prompts are at least 30 s apart.
- The event is on 21 Nov 2026. The end-to-end dry run (Task 9) must pass before 19 Nov.

## Review Focus

1. **The scanner re-reads a ticket that's still being held up.** Expect one welcome and no front-desk line. Covered by `test_success_then_already_checked_in_same_name_is_ignored` (Task 3).
2. **Two different guests scan within a second.** Expect both welcomes, in order and never overlapping, each with its own name. Covered by `test_two_scans_are_spoken_in_order` (Task 8).
3. **Odd names from Luma**, such as `"  sarah chen "`, `"Dr Sam Donegan"`, `"SARAH"`, `"李伟"`, `""` or an email address used as a name. Expect a sensible first name, or the nameless welcome. Covered by `test_first_name_cases` (Task 2).
4. **The snapshot has a face the detector misses**, or the crop would include part of a face. Expect nothing to be sent. Covered by `test_crop_returns_none_without_face` and `test_crop_starts_below_chin` (Task 6).
5. **A brief face flicker**, where the detector drops out for under 1 s. Expect the dwell timer not to reset, so no prompt storm and no missed prompt. Covered by `test_flicker_under_1s_does_not_reset_dwell` (Task 4).

---

### Task 1: Discovery — camera sharing and a real test ticket (with the host)

This task is manual and needs the host present. It settles the two unknowns everything else depends on.

**Files:**
- Create: `docs/superpowers/notes/2026-11-discovery.md`

- [ ] **Step 1: Start the daemon with media enabled**

Run: `.venv/bin/reachy-mini-daemon -p /dev/cu.usbmodem5AF71339921 --headless` (no `--no-media`).
Expected: the log shows the media server started with the camera open. If it fails because GStreamer (`gi`) is missing, follow the SDK's macOS media install instructions and record the steps in the notes.

- [ ] **Step 2: Check that a Python client receives frames**

Run: `.venv/bin/python -c "from reachy_mini import ReachyMini; m=ReachyMini(); import time; time.sleep(2); f=m.media.get_frame(); print(None if f is None else f.shape)"`
Expected: a shape like `(720, 1280, 3)`.

- [ ] **Step 3: Check that Chrome and the daemon share the camera**

Leave the daemon running and open `https://luma.com/check-in/evt-ZLcgMdLTqHF8bK3/scan` with **Reachy Mini Camera** selected. Run Step 2 again.
Expected: Chrome shows live video **and** Step 2 still prints a shape. Record pass or fail in the notes. **If it fails, do Task 1b before Task 6.**

- [ ] **Step 4: Register a test guest**

The host registers a second email on the event, approves it, and keeps the ticket email open on a phone.

- [ ] **Step 5: Commit the notes**

```bash
git add docs/superpowers/notes/2026-11-discovery.md
git commit -m "docs: record camera-sharing discovery results"
```

### Task 1b (only if Task 1 Step 3 failed): Virtual camera relay

**Files:**
- Create: `greeter/camera_relay.py`
- Test: manual

**Interfaces:**
- Produces: `run_camera_relay(mini: ReachyMini, fps: int = 15) -> None` (blocking). It republishes `mini.media.get_frame()` to a virtual camera.

- [ ] **Step 1:** Install OBS (`brew install --cask obs`), start its Virtual Camera once so macOS registers it, then `uv pip install --python .venv/bin/python pyvirtualcam`.
- [ ] **Step 2:** Implement `run_camera_relay` using `pyvirtualcam.Camera(width, height, fps, fmt=PixelFormat.BGR)`, with the size taken from the first frame.
- [ ] **Step 3:** Run it, select **OBS Virtual Camera** in the Luma scanner, and confirm Chrome shows Reachy's view while Task 1 Step 2 still gets frames.
- [ ] **Step 4:** Commit with `feat: relay Reachy camera to a virtual camera for the Luma scanner`.

### Task 2: Project scaffold, settings, and spoken lines

**Files:**
- Create: `requirements.txt`, `.env.example`, `greeter/__init__.py`, `greeter/config.py`, `greeter/lines.py`, `tests/__init__.py`, `tests/test_lines.py`, `tests/test_config.py`, `pytest.ini`
- Modify: `.gitignore` (add `.env`, `logs/`, `data/event_info.md`)

**Interfaces:**
- Produces:
  - `greeter.config.Settings`, a frozen dataclass: `openai_api_key: str`, `realtime_model: str = "gpt-realtime"`, `voice: str = "marin"`, `compliment_model: str = "gpt-4.1-mini"`, `server_port: int = 8765`, `daemon_url: str = "http://127.0.0.1:8000"`, `event_url: str = "https://luma.com/event/evt-ZLcgMdLTqHF8bK3"`
  - `greeter.config.load_settings(env: Mapping[str, str]) -> Settings`, which raises `ValueError("OPENAI_API_KEY is not set")` when the key is missing or blank. Env names: `OPENAI_API_KEY`, `REALTIME_MODEL`, `REALTIME_VOICE`, `COMPLIMENT_MODEL`, `GREETER_PORT`, `DAEMON_URL`, `EVENT_URL`.
  - `greeter.lines.first_name(full_name: str | None) -> str | None`
  - `greeter.lines.welcome_line(full_name: str | None) -> str`
  - `greeter.lines.FRONT_DESK_LINE: str`, `greeter.lines.QR_PROMPT_LINE: str` (exact text from Global Constraints)

- [ ] **Step 1: Install dependencies**

`requirements.txt`: `openai>=2.28`, `aiohttp>=3.10`, `httpx>=0.27`, `opencv-python-headless>=4.10`, `pytest>=8`, `pytest-asyncio>=0.24`. `pytest.ini` sets `asyncio_mode = auto` and `testpaths = tests`.
Run: `uv pip install --python .venv/bin/python -r requirements.txt`
Expected: it installs with no resolver conflicts against `reachy-mini`.

- [ ] **Step 2: Write the failing tests**

```python
# tests/test_lines.py
import pytest
from greeter.lines import first_name, welcome_line, FRONT_DESK_LINE, QR_PROMPT_LINE

@pytest.mark.parametrize("raw,expected", [
    ("Sarah Chen", "Sarah"),
    ("  sarah chen ", "Sarah"),
    ("SARAH", "Sarah"),
    ("Dr Sam Donegan", "Sam"),
    ("Dr. Sam Donegan", "Sam"),
    ("Prof Jane Doe", "Jane"),
    ("Mary-Kate Olsen", "Mary-Kate"),
    ("李伟", "李伟"),
    ("", None),
    (None, None),
    ("sam@example.com", None),
])
def test_first_name_cases(raw, expected):
    assert first_name(raw) == expected

def test_welcome_line_with_name():
    assert welcome_line("Sarah Chen") == "Welcome, Sarah! MLAI welcomes you to the OpenAI Dev Day!"

def test_welcome_line_without_name():
    assert welcome_line(None) == "Welcome! MLAI welcomes you to the OpenAI Dev Day!"

def test_fixed_lines():
    assert FRONT_DESK_LINE == "Hmm, I couldn't check you in. Please find a host at the front desk and they'll sort you out!"
    assert QR_PROMPT_LINE == "Hi! If you haven't checked in yet, just show me the QR code on your Luma ticket."
```

```python
# tests/test_config.py
import pytest
from greeter.config import load_settings

def test_missing_key_raises():
    with pytest.raises(ValueError, match="OPENAI_API_KEY is not set"):
        load_settings({})

def test_defaults_and_overrides():
    s = load_settings({"OPENAI_API_KEY": "sk-x", "GREETER_PORT": "9000"})
    assert s.realtime_model == "gpt-realtime" and s.server_port == 9000
```

- [ ] **Step 3: Run the tests and check they fail**

Run: `.venv/bin/python -m pytest tests/test_lines.py tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: greeter`.

- [ ] **Step 4: Implement `greeter/config.py` and `greeter/lines.py`**

`first_name`: strip whitespace. Return `None` for an empty value or anything containing `@`. Drop a leading honorific from `{dr, mr, mrs, ms, mx, prof}`, with or without a trailing `.`, case-insensitive. Take the first whitespace-separated token. If the token `isascii()` and is entirely upper- or lowercase, capitalise it (`str.capitalize`); otherwise keep it as written. Hyphens are preserved: `"mary-kate"` → `"Mary-kate"` is acceptable, but `"Mary-Kate"` must stay unchanged. `.env.example` lists every env name with a comment.

- [ ] **Step 5: Run the tests and check they pass**

Run: `.venv/bin/python -m pytest tests/test_lines.py tests/test_config.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add requirements.txt .env.example .gitignore pytest.ini greeter tests
git commit -m "feat: greeter scaffold, settings and spoken lines"
```

### Task 3: Check-in gate (what to say for each scan result)

**Files:**
- Create: `greeter/checkin.py`, `tests/test_checkin.py`

**Interfaces:**
- Produces:
  - `ScanResult`, a frozen dataclass: `kind: Literal["success", "failure"]`, `name: str | None`, `at: float` (monotonic seconds)
  - `CheckinGate(repeat_window_s: float = 60.0, failure_repeat_s: float = 15.0)`
  - `CheckinGate.decide(r: ScanResult) -> Literal["welcome", "front_desk", "ignore"]`

- [ ] **Step 1: Write the failing tests**

```python
from greeter.checkin import CheckinGate, ScanResult as R

def test_success_welcomes():
    assert CheckinGate().decide(R("success", "Sam Lee", 0)) == "welcome"

def test_failure_goes_to_front_desk():
    assert CheckinGate().decide(R("failure", None, 0)) == "front_desk"

def test_success_then_already_checked_in_same_name_is_ignored():
    g = CheckinGate()
    g.decide(R("success", "Sam Lee", 0))
    assert g.decide(R("failure", "sam lee", 5)) == "ignore"
    assert g.decide(R("success", "Sam Lee", 30)) == "ignore"

def test_same_name_after_window_is_handled_again():
    g = CheckinGate()
    g.decide(R("success", "Sam Lee", 0))
    assert g.decide(R("failure", "Sam Lee", 61)) == "front_desk"

def test_repeated_failure_within_15s_is_ignored():
    g = CheckinGate()
    assert g.decide(R("failure", "Ann", 0)) == "front_desk"
    assert g.decide(R("failure", "Ann", 10)) == "ignore"
    assert g.decide(R("failure", "Ann", 16)) == "front_desk"

def test_different_people_are_independent():
    g = CheckinGate()
    g.decide(R("success", "Sam Lee", 0))
    assert g.decide(R("success", "Ann Wu", 1)) == "welcome"
```

- [ ] **Step 2: Run the tests and check they fail**

Run: `.venv/bin/python -m pytest tests/test_checkin.py -v`
Expected: FAIL with an import error.

- [ ] **Step 3: Implement `CheckinGate`**

Compare names with `casefold().strip()`. Keep a dict mapping name to last welcome time, plus a dict mapping name (or `None`) to last front-desk time. Prune entries older than the windows on each call.

- [ ] **Step 4: Run the tests and check they pass**

Run: `.venv/bin/python -m pytest tests/test_checkin.py -v`
Expected: PASS.

- [ ] **Step 5: Commit** with `feat: check-in gate with repeat suppression`.

### Task 4: Arrival prompter (when to ask for the QR code)

**Files:**
- Create: `greeter/arrival.py`, `tests/test_arrival.py`

**Interfaces:**
- Produces: `ArrivalPrompter(dwell_s=4.0, cooldown_s=30.0, flicker_s=1.0)` with `update(face_present: bool, now: float) -> bool` (True means say `QR_PROMPT_LINE` now) and `note_scan(now: float) -> None`.

Rules: a "visit" starts when a face appears after more than `flicker_s` of absence. Measure absence from the first `False` sample to the next `True` sample. Prompt at most once per visit, and only if the face has been present for at least `dwell_s` since the visit started, there has been no scan since the visit started, and the last prompt was at least `cooldown_s` ago.

- [ ] **Step 1: Write the failing tests**

```python
from greeter.arrival import ArrivalPrompter

def run(p, frames):  # frames: list of (t, present)
    return [t for t, present in frames if p.update(present, t)]

def test_prompts_after_dwell():
    p = ArrivalPrompter()
    assert run(p, [(t / 2, True) for t in range(0, 12)]) == [4.0]

def test_scan_during_visit_suppresses_prompt():
    p = ArrivalPrompter()
    p.update(True, 0); p.note_scan(2)
    assert run(p, [(t, True) for t in range(3, 10)]) == []

def test_flicker_under_1s_does_not_reset_dwell():
    p = ArrivalPrompter()
    frames = [(0, True), (1, True), (2, False), (2.5, True), (3, True), (4, True)]
    assert run(p, frames) == [4]

def test_cooldown_between_visits():
    p = ArrivalPrompter()
    assert run(p, [(0, True), (4, True)]) == [4]
    assert run(p, [(6, False), (10, True), (14, True)]) == []  # only 10 s since the last prompt
    assert run(p, [(40, False), (45, True), (49, True)]) == [49]

def test_one_prompt_per_visit():
    p = ArrivalPrompter(cooldown_s=0)
    assert run(p, [(t, True) for t in range(0, 20)]) == [4]
```

- [ ] **Step 2: Run the tests and check they fail**

Run: `.venv/bin/python -m pytest tests/test_arrival.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `ArrivalPrompter`.**

- [ ] **Step 4: Run the tests and check they pass**

Run: `.venv/bin/python -m pytest tests/test_arrival.py -v`
Expected: PASS.

- [ ] **Step 5: Commit** with `feat: arrival prompter with dwell, flicker tolerance and cooldown`.

### Task 5: Local scan-result server

**Files:**
- Create: `greeter/server.py`, `tests/test_server.py`

**Interfaces:**
- Consumes: `ScanResult` (Task 3).
- Produces: `make_app(queue: asyncio.Queue[ScanResult], debug_log_path: Path, clock: Callable[[], float] = time.monotonic) -> aiohttp.web.Application`, with these routes:
  - `POST /scan` takes the JSON `{"kind": "success" | "failure", "name": str | null}`. It enqueues `ScanResult(kind, name, clock())` and returns `{"ok": true}`. Bad JSON or an unknown `kind` returns 400 and enqueues nothing.
  - `POST /debug` takes `{"text": str}`, appends a timestamped line to `debug_log_path` and returns `{"ok": true}`.
  - `GET /health` returns `{"ok": true}`.
- Produces: `async def start_server(app, port: int) -> web.AppRunner`, bound to `127.0.0.1`.

- [ ] **Step 1: Write the failing tests** (using the `aiohttp_client` fixture from `pytest-aiohttp`; add `pytest-aiohttp>=1.0` to `requirements.txt` and install it)

```python
async def test_scan_enqueues(aiohttp_client, tmp_path):
    q = asyncio.Queue()
    c = await aiohttp_client(make_app(q, tmp_path / "d.log", clock=lambda: 7.0))
    r = await c.post("/scan", json={"kind": "success", "name": "Sam Lee"})
    assert r.status == 200 and q.get_nowait() == ScanResult("success", "Sam Lee", 7.0)

async def test_bad_kind_rejected(aiohttp_client, tmp_path):
    q = asyncio.Queue()
    c = await aiohttp_client(make_app(q, tmp_path / "d.log"))
    assert (await c.post("/scan", json={"kind": "maybe"})).status == 400 and q.empty()

async def test_debug_appends(aiohttp_client, tmp_path):
    c = await aiohttp_client(make_app(asyncio.Queue(), tmp_path / "d.log"))
    await c.post("/debug", json={"text": "Checked in Sam"})
    assert "Checked in Sam" in (tmp_path / "d.log").read_text()
```

- [ ] **Step 2: Run the tests and check they fail**

Run: `.venv/bin/python -m pytest tests/test_server.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `make_app` and `start_server`.**

- [ ] **Step 4: Run the tests and check they pass**

Run: `.venv/bin/python -m pytest tests/test_server.py -v`
Expected: PASS.

- [ ] **Step 5: Commit** with `feat: local scan-result server`.

### Task 6: Chrome extension — capture the scanner's results, then report them

Do this with the host and the test ticket from Task 1.

**Files:**
- Create: `extension/manifest.json`, `extension/background.js`, `extension/content.js`, `extension/parse.js`, `extension/parse.test.mjs`, `extension/fixtures/*.txt`
- Create: `scripts/run_debug_server.py`, a 10-line script that runs `make_app` on port 8765 and prints `/scan` and `/debug` hits.

**Interfaces:**
- Consumes: `POST http://127.0.0.1:8765/scan` and `/debug` (Task 5).
- Produces: `parseScanText(text: string) -> {kind: "success" | "failure", name: string | null} | null` in `extension/parse.js`, written as an ES module that is also attached to `globalThis` for the content script. It returns `null` when the text isn't a scan result.

- [ ] **Step 1: Write the recorder**

`manifest.json` (MV3): `content_scripts` matches `https://luma.com/check-in/*/scan*` and runs `parse.js` then `content.js`. `host_permissions` is `["http://127.0.0.1:8765/*"]`. The background is a service worker, `background.js`. `content.js` uses a `MutationObserver` on `document.body` with `{childList: true, subtree: true, characterData: true}`. For each added or changed element's `innerText` (trimmed, non-empty, at most 500 characters, de-duplicated within 2 s), it calls `chrome.runtime.sendMessage({type: "debug", text})`. `background.js` relays `debug` to `/debug` and `scan` to `/scan` with `fetch` (POST, JSON). The relay goes through the background worker because Chrome blocks pages from reaching localhost.

- [ ] **Step 2: Capture real results**

Install the extension (`chrome://extensions` → Developer mode → Load unpacked → `extension/`) and run `scripts/run_debug_server.py`. With Express Mode on, scan: (a) the test ticket, which should succeed; (b) the same ticket again (already checked in); (c) a pending guest, if one is available; (d) a random non-Luma QR code. Copy the text logged for each into `extension/fixtures/success.txt`, `already.txt`, `pending.txt` and `invalid.txt`. Then **undo the test check-in** in Luma's guest list so the numbers on the day are correct.

- [ ] **Step 3: Write the failing parser tests** in `extension/parse.test.mjs` using `node:test`. Each fixture maps to its expected result: `success.txt` → `{kind: "success", name: "<test guest's name exactly as shown>"}`, `already.txt` → `kind: "failure"`, `pending.txt` → `kind: "failure"`, `invalid.txt` → `kind: "failure"`. Also check that an unrelated string such as `"14 Going"` → `null`.

- [ ] **Step 4: Run the tests and check they fail**

Run: `node --test extension/`
Expected: FAIL.

- [ ] **Step 5: Implement `parseScanText`** from the phrasing observed in the fixtures. Treat anything that looks like a result but isn't a clear success as `failure`.

- [ ] **Step 6: Run the tests and check they pass**

Run: `node --test extension/`
Expected: PASS.

- [ ] **Step 7: Switch content.js to report mode.** It calls `parseScanText` on each captured text and sends `{type: "scan", ...}` for non-null results. Keep the debug relay behind `const DEBUG = false`. Reload the extension and rescan the test ticket.
Expected: the debug server prints one `/scan` success with the right name. Undo the check-in in Luma again.

- [ ] **Step 8: Commit** with `feat: Chrome extension relaying Luma scanner results to Reachy`.

### Task 7: Event knowledge and session instructions

**Files:**
- Create: `greeter/event_info.py`, `tests/test_event_info.py`, `data/event_extra.md` (the host fills in the venue address, Wi-Fi details and anything else not on the Luma page)

**Interfaces:**
- Produces:
  - `html_to_text(html: str) -> str`: visible text only (drops `script`, `style` and `noscript`), with whitespace collapsed. Uses the stdlib `html.parser`.
  - `async def fetch_event_text(url: str, cache_path: Path) -> str`: fetches with `httpx` and writes the cache. If the network fails, it returns the cached text, or raises if there is no cache.
  - `build_instructions(event_text: str, extra_text: str) -> str`

- [ ] **Step 1: Write the failing tests**

```python
def test_html_to_text_drops_scripts():
    assert html_to_text("<p>Hi</p><script>x=1</script><p>there</p>") == "Hi there"

def test_instructions_contain_rules_and_facts():
    s = build_instructions("Build time 10:15", "Wi-Fi: MLAI-guest")
    for must in ["Reachy", "MLAI", "one or two sentences", "front desk", "Build time 10:15", "Wi-Fi: MLAI-guest"]:
        assert must in s

async def test_fetch_falls_back_to_cache(tmp_path, monkeypatch): ...  # make httpx raise ConnectError; the cache contains "cached"; assert "cached" is returned
```

- [ ] **Step 2: Run the tests and check they fail**

Run: `.venv/bin/python -m pytest tests/test_event_info.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement the functions.** `build_instructions` says Reachy is MLAI's friendly robot greeter at the OpenAI Dev Day. Answers are one or two sentences. Reachy only uses the event facts below, and when it doesn't know, it says to ask a host at the front desk. It never guesses anyone's name, never comments on people's appearance unless the app explicitly asks for a compliment, and stays bright and warm. The event text and extra text are appended under headings.

- [ ] **Step 4: Run the tests and check they pass**

Run: `.venv/bin/python -m pytest tests/test_event_info.py -v`
Expected: PASS.

- [ ] **Step 5: Commit** with `feat: event knowledge and session instructions`.

### Task 8: Compliment crop and the speech queue

**Files:**
- Create: `greeter/compliment.py`, `greeter/speech.py`, `tests/test_compliment.py`, `tests/test_speech.py`

**Interfaces:**
- Consumes: `reachy_mini.vision.face_detector.FaceDetector` and `Face` (with `bbox` as `(x, y, w, h)` in pixels; confirm whether the SDK uses x/y/w/h or x1/y1/x2/y2 and adapt).
- Produces:
  - `crop_below_face(frame: np.ndarray, faces: list[Face]) -> np.ndarray | None`: uses the largest face. The crop's top is `face_bottom + 0.15 * face_h` and runs to the bottom of the frame. Horizontally it spans `face_center_x ± 1.5 * face_w`, clamped to the frame. Returns `None` when there are no faces, or when the crop is under 80 px tall.
  - `async def suggest_compliment(client: AsyncOpenAI, model: str, crop_jpeg: bytes, timeout_s: float = 4.0) -> str | None`: sends one image with the prompt *"This photo shows a person's clothing from the shoulders down. If there is a genuinely distinctive, positive detail about their clothing or accessories (a design, pattern, colour, slogan, accessory), reply with ONE short, warm compliment of at most 12 words, addressed to them as 'you'. Never mention body, face, age, weight, or anything personal. If nothing stands out, reply exactly NONE."* Returns `None` for `NONE`, an empty reply, a timeout or any error.
  - `SpeechQueue(say: Callable[[str], Awaitable[None]])` with `async put(text: str) -> None` and `async run() -> None`. It speaks items strictly one at a time, in the order they were added.

- [ ] **Step 1: Write the failing tests**

```python
def test_crop_returns_none_without_face():
    assert crop_below_face(np.zeros((720, 1280, 3), np.uint8), []) is None

def test_crop_starts_below_chin():
    f = Face(bbox=(600, 100, 100, 120), right_eye=(0, 0), left_eye=(0, 0), nose=(0, 0))
    crop = crop_below_face(np.zeros((720, 1280, 3), np.uint8), [f])
    assert crop is not None and crop.shape[0] == 720 - int(100 + 120 + 0.15 * 120)

async def test_suggest_returns_none_for_NONE(): ...  # fake client replying "NONE" → None
async def test_suggest_returns_none_on_timeout(): ...  # fake client that sleeps 10 s, timeout_s=0.1 → None

async def test_two_scans_are_spoken_in_order():
    spoken = []
    async def say(t): await asyncio.sleep(0.05); spoken.append(t)
    q = SpeechQueue(say); task = asyncio.create_task(q.run())
    await q.put("Welcome, Sam!"); await q.put("Welcome, Ann!")
    await asyncio.sleep(0.2); task.cancel()
    assert spoken == ["Welcome, Sam!", "Welcome, Ann!"]
```

- [ ] **Step 2: Run the tests and check they fail**

Run: `.venv/bin/python -m pytest tests/test_compliment.py tests/test_speech.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement the functions.** `suggest_compliment` uses the Responses API with an `input_image` given as a base64 data URL.

- [ ] **Step 4: Run the tests and check they pass**

Run: `.venv/bin/python -m pytest tests/test_compliment.py tests/test_speech.py -v`
Expected: PASS.

- [ ] **Step 5: Commit** with `feat: face-free compliment crop and ordered speech queue`.

### Task 9: Realtime voice, robot moves, main loop, and the end-to-end dry run

**Files:**
- Create: `greeter/audio.py`, `greeter/voice.py`, `greeter/robot.py`, `greeter/main.py`, `tests/test_audio.py`, `docs/runbook.md`
- Reference: `vendor/old_openai_realtime.py` and `vendor/reachy_mini_conversation_app/src/reachy_mini_conversation_app/huggingface_realtime.py`, for the realtime event loop, server VAD and barge-in handling.

**Interfaces:**
- Consumes: everything above.
- Produces:
  - `greeter.audio.float_to_pcm16(x: np.ndarray) -> bytes`, `pcm16_to_float(b: bytes) -> np.ndarray`, `resample(x: np.ndarray, src_hz: int, dst_hz: int) -> np.ndarray` (linear, mono) and `to_mono(x: np.ndarray) -> np.ndarray`
  - `greeter.voice.RealtimeVoice(settings, mini, instructions: str)` with:
    - `async run()`: connects with `AsyncOpenAI().realtime.connect(model=settings.realtime_model)` and sends `session.update` (audio in and out as PCM16 at 24 kHz, `server_vad` with `interrupt_response=True`, `silence_duration_ms=600`, voice from settings, `max_output_tokens=200`). It then runs mic-send, event-receive and playback loops.
    - `set_listening(enabled: bool)`: mic audio is only sent while enabled.
    - `async say_exact(text: str)`: cancels any active response, flushes local playback, and sends `response.create` with `instructions="Say exactly this, brightly and warmly, and nothing else: " + text` and `conversation="none"`. It waits for that response to finish.
  - `greeter.robot.Moves(mini)` with `async welcome()` (antennas up and wiggle, small nod), `async front_desk()` (gentle head tilt, antennas down) and `async perk_up()` (small antenna lift). Each runs SDK `goto_target` calls in `asyncio.to_thread` and finishes in 1.5 s or less.
  - `greeter.main.main()`, the entry point, run as `python -m greeter.main`.

- [ ] **Step 1: Write the failing audio tests**

`resample` of a 1 kHz sine from 16 000 → 24 000 Hz keeps its length ratio within ±1 sample and its peak frequency within ±20 Hz. `pcm16_to_float(float_to_pcm16(x))` round-trips within 1/32767. Values outside [-1, 1] are clipped, not wrapped.

- [ ] **Step 2: Run the tests and check they fail**

Run: `.venv/bin/python -m pytest tests/test_audio.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `greeter/audio.py`.**

- [ ] **Step 4: Run the tests and check they pass**

Run: `.venv/bin/python -m pytest tests/test_audio.py -v`
Expected: PASS.

- [ ] **Step 5: Implement `voice.py`, `robot.py` and `main.py`**

`main` loads the settings and `.env`. It opens `ReachyMini(media_backend="local")` and calls `POST {daemon_url}/api/media/tracking/enable` so the head follows faces. It fetches the event text and builds the instructions, then starts the server (Task 5), `RealtimeVoice`, a `SpeechQueue` whose `say` is `voice.say_exact`, and these two loops:
- **Face loop, 5 Hz:** calls `GET {daemon_url}/api/media/tracking/face` and calls `voice.set_listening(face_detected)` (the face-present gate against background chatter). It feeds `ArrivalPrompter.update`, and on True runs `perk_up()` and queues `QR_PROMPT_LINE`.
- **Scan loop:** for each `ScanResult`, calls `ArrivalPrompter.note_scan`, then `CheckinGate.decide`:
  - `welcome`: grab `mini.media.get_frame()` immediately, start `suggest_compliment` on the crop as a background task, run `welcome()` and queue `welcome_line(name)`. If the compliment arrives within 4 s of the scan, queue it straight after; otherwise drop it.
  - `front_desk`: run `front_desk()` and queue `FRONT_DESK_LINE`.
  - `ignore`: do nothing.

Frames are never written to disk.

- [ ] **Step 6: Run a manual voice smoke test**

Start the daemon with media, then run `.venv/bin/python -m greeter.main`. Face Reachy and ask "What time do demos start?"
Expected: a one- or two-sentence answer that mentions 1:00 pm. Talk over Reachy while it answers.
Expected: it stops within about 0.5 s. Turn away and talk.
Expected: no reply. If Reachy interrupts itself because its mic hears its own speaker, call `set_listening(False)` while playback is active, then re-test.

- [ ] **Step 7: Run the end-to-end dry run with the host**

With the scanner open (Express Mode, Reachy's camera) and the extension loaded, show the test ticket.
Expected: Luma's checked-in count goes up by 1, and within about 2 s Reachy says "Welcome, {First}! MLAI welcomes you to the OpenAI Dev Day!". A compliment follows if the shirt is distinctive. Keep holding the ticket up for 10 s.
Expected: nothing more is said. Show a random QR code.
Expected: the front-desk line, said once. Stand in front of Reachy for 5 s without scanning.
Expected: the QR prompt, said once. Undo the test check-in in Luma afterwards.

- [ ] **Step 8: Write `docs/runbook.md`**

Write an event-day checklist covering: power on → start the daemon (exact command) → open the scanner, select the camera and turn on Express Mode → check the extension is loaded → run `python -m greeter.main` → do a test scan with the test ticket and undo it → bring a hotspot. Add a troubleshooting section: no greeting (check `GET http://127.0.0.1:8765/health` and the extension's service-worker console), no voice (check `OPENAI_API_KEY`), and camera busy (Task 1b).

- [ ] **Step 9: Commit** with `feat: realtime voice, moves and main loop; event-day runbook`.
