"""Reachy greeter: python -m greeter.main"""
from __future__ import annotations

import asyncio
import logging
import os
import signal
import time
from pathlib import Path

import cv2
import httpx
from openai import AsyncOpenAI
from reachy_mini import ReachyMini
from reachy_mini.vision.face_detector import FaceDetector

from greeter.arrival import ArrivalPrompter
from greeter.checkin import CheckinGate, ScanResult
from greeter.compliment import crop_below_face, rate_outfit, suggest_compliment
from greeter.config import Settings, load_settings
from greeter.event_info import build_instructions, fetch_event_text
from greeter.greeter import Greeter
from greeter.robot import Moves
from greeter.server import make_app, start_server
from greeter.speech import SpeechQueue
from greeter.tools import TOOLS, make_tool_handler, rate_fit
from greeter.voice import RealtimeVoice

ROOT = Path(__file__).resolve().parent.parent
log = logging.getLogger("greeter")


def load_dotenv(path: Path) -> dict[str, str]:
    env = dict(os.environ)
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    return env


async def face_loop(settings: Settings, greeter: Greeter, voice: RealtimeVoice) -> None:
    url = f"{settings.daemon_url}/api/media/tracking/face"
    async with httpx.AsyncClient(timeout=1.0) as client:
        while True:
            try:
                data = (await client.get(url)).json()
                present = bool(data.get("face_target", {}).get("detected"))
            except (httpx.HTTPError, ValueError):
                present = False
            voice.set_listening(present)  # only listen to someone facing Reachy
            await greeter.handle_face(present, time.monotonic())
            await asyncio.sleep(0.2)


async def scan_loop(queue: asyncio.Queue[ScanResult], greeter: Greeter) -> None:
    while True:
        await greeter.handle_scan(await queue.get())


async def amain() -> None:
    settings = load_settings(load_dotenv(ROOT / ".env"))
    event_text = await fetch_event_text(settings.event_url, ROOT / "data" / "event_info.md")
    extra = (ROOT / "data" / "event_extra.md")
    instructions = build_instructions(event_text, extra.read_text() if extra.exists() else "")

    with ReachyMini() as mini:
        async with httpx.AsyncClient(timeout=3.0) as client:
            await client.post(f"{settings.daemon_url}/api/media/tracking/enable")

        detector = FaceDetector()
        openai_client = AsyncOpenAI(api_key=settings.openai_api_key)

        async def get_compliment() -> str | None:
            frame = mini.media.get_frame()  # in memory only, never saved
            if frame is None:
                log.info("compliment: no camera frame")
                return None
            crop = crop_below_face(frame, await asyncio.to_thread(detector.detect, frame))
            if crop is None:
                log.info("compliment: no face found or too little clothing in view; nothing sent")
                return None
            ok, jpeg = cv2.imencode(".jpg", crop, [cv2.IMWRITE_JPEG_QUALITY, 80])
            return await suggest_compliment(openai_client, settings.compliment_model, jpeg.tobytes()) if ok else None

        async def rate_current_fit() -> dict:
            out = await rate_fit(
                mini.media.get_frame,  # in memory only, never saved
                detector.detect,
                lambda jpeg: rate_outfit(openai_client, settings.compliment_model, jpeg),
            )
            log.info("rate_outfit -> %s", "rating" if "rating" in out else out["say"][:40])
            return out

        greeter_ref: list[Greeter] = []

        async def act_sad() -> None:
            await greeter_ref[0].act_sad()

        voice = RealtimeVoice(settings, mini, instructions, TOOLS, make_tool_handler(rate_current_fit, act_sad))
        speech = SpeechQueue(voice.say_exact)
        greeter = Greeter(speech, Moves(mini, settings.daemon_url), CheckinGate(), ArrivalPrompter(), get_compliment)
        greeter_ref.append(greeter)
        greeter.conversation_active = lambda: voice.active_within(10.0)

        scans: asyncio.Queue[ScanResult] = asyncio.Queue()
        runner = await start_server(make_app(scans, ROOT / "logs" / "scanner-debug.log"), settings.server_port)
        log.info("greeter ready on http://127.0.0.1:%d", settings.server_port)
        try:
            await asyncio.gather(
                voice.run(), speech.run(), scan_loop(scans, greeter), face_loop(settings, greeter, voice)
            )
        finally:
            await runner.cleanup()
            # Leave the robot still: stop the daemon's head tracking we turned on at startup.
            try:
                async with httpx.AsyncClient(timeout=3.0) as client:
                    await client.post(f"{settings.daemon_url}/api/media/tracking/disable")
            except httpx.HTTPError:
                log.warning("could not disable head tracking on exit")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    for noisy in ("httpx", "zeroconf", "aiohttp.access"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    # Treat `pkill` (SIGTERM) like Ctrl+C so cleanup runs and head tracking is switched off.
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    try:
        asyncio.run(amain())
    except KeyboardInterrupt:
        log.info("greeter stopped")


if __name__ == "__main__":
    main()
