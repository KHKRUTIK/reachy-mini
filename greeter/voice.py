"""OpenAI realtime voice for Reachy: mic -> model -> speaker, with exact forced lines and barge-in."""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import time
import uuid
from typing import Any, Awaitable, Callable

import numpy as np
from openai import AsyncOpenAI

from greeter.audio import float_to_pcm16, pcm16_to_float, resample, to_mono
from greeter.config import Settings

log = logging.getLogger(__name__)

MODEL_RATE = 24000
FORCED_PREFIX = "Say exactly this, brightly and warmly, and nothing else: "

ToolHandler = Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]]


def build_session_config(settings: Settings, instructions: str, tools: list[dict]) -> dict[str, Any]:
    config: dict[str, Any] = {
        "type": "realtime",
        "instructions": instructions,
        "output_modalities": ["audio"],
        "max_output_tokens": 200,
        "audio": {
            "input": {
                "format": {"type": "audio/pcm", "rate": MODEL_RATE},
                "transcription": {"model": "gpt-4o-transcribe"},
                "turn_detection": {
                    "type": "server_vad",
                    "interrupt_response": True,
                    "create_response": True,
                    "silence_duration_ms": 600,
                },
            },
            "output": {
                "format": {"type": "audio/pcm", "rate": MODEL_RATE},
                "voice": settings.voice,
            },
        },
        "tools": tools,
    }
    if tools:
        config["tool_choice"] = "auto"
    return config


def forced_response(text: str, tag: str) -> dict[str, Any]:
    return {
        "conversation": "none",
        "instructions": FORCED_PREFIX + text,
        "metadata": {"tag": tag},
        "output_modalities": ["audio"],
        "input": [],
    }


class RealtimeVoice:
    """Owns the realtime session. Mic audio is only sent while ``set_listening(True)``."""

    def __init__(
        self,
        settings: Settings,
        mini: Any,
        instructions: str,
        tools: list[dict] | None = None,
        tool_handler: ToolHandler | None = None,
    ) -> None:
        self._settings = settings
        self._mini = mini
        self._instructions = instructions
        self._tools = tools or []
        self._tool_handler = tool_handler
        self._conn: Any = None
        self._connected = asyncio.Event()
        self._listening = False
        self._forced_active = False
        self._forced_waiters: dict[str, asyncio.Future] = {}
        self._discarded: set[str] = set()
        self._current_response: str | None = None
        self._playback_end = 0.0
        self._in_rate = mini.media.get_input_audio_samplerate()
        self._out_rate = mini.media.get_output_audio_samplerate()

    # ---- public API -------------------------------------------------------------------

    def set_listening(self, enabled: bool) -> None:
        self._listening = enabled

    async def say_exact(self, text: str, timeout_s: float = 20.0) -> None:
        """Speak ``text`` verbatim (out-of-band), interrupting any chat, and wait until it has played."""
        await self._connected.wait()
        await self._interrupt()
        tag = uuid.uuid4().hex
        done = asyncio.get_running_loop().create_future()
        self._forced_waiters[tag] = done
        self._forced_active = True
        try:
            await self._conn.response.create(response=forced_response(text, tag))
            await asyncio.wait_for(done, timeout_s)
            await self._wait_playback()
        except asyncio.TimeoutError:
            log.warning("forced line timed out: %r", text)
        finally:
            self._forced_waiters.pop(tag, None)
            self._forced_active = False

    async def run(self) -> None:
        """Connect and keep the session alive, reconnecting with backoff."""
        client = AsyncOpenAI(api_key=self._settings.openai_api_key)
        backoff = 1.0
        while True:
            try:
                async with client.realtime.connect(model=self._settings.realtime_model) as conn:
                    self._conn = conn
                    await conn.session.update(
                        session=build_session_config(self._settings, self._instructions, self._tools)
                    )
                    self._connected.set()
                    log.info("realtime connected (%s)", self._settings.realtime_model)
                    backoff = 1.0
                    await asyncio.gather(self._mic_loop(), self._event_loop())
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("realtime session dropped; reconnecting in %.0fs", backoff)
            finally:
                self._connected.clear()
                self._conn = None
                for fut in self._forced_waiters.values():
                    if not fut.done():
                        fut.set_result(None)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30.0)

    # ---- internals --------------------------------------------------------------------

    async def _mic_loop(self) -> None:
        media = self._mini.media
        media.start_recording()
        while True:
            sample = await asyncio.to_thread(media.get_audio_sample)
            if sample is None or len(sample) == 0:
                await asyncio.sleep(0.01)
                continue
            if not self._listening or self._forced_active:
                continue
            pcm = float_to_pcm16(resample(to_mono(sample), self._in_rate, MODEL_RATE))
            await self._conn.input_audio_buffer.append(audio=base64.b64encode(pcm).decode("ascii"))

    async def _event_loop(self) -> None:
        self._mini.media.start_playing()
        async for event in self._conn:
            t = event.type
            if t == "input_audio_buffer.speech_started" and not self._forced_active:
                self._flush_playback()
            elif t == "response.created":
                self._current_response = event.response.id
            elif t == "response.output_audio.delta":
                if event.response_id in self._discarded:
                    continue
                self._play(base64.b64decode(event.delta))
            elif t == "response.done":
                self._on_response_done(event.response)
            elif t == "response.function_call_arguments.done":
                asyncio.create_task(self._run_tool(event.call_id, event.name, event.arguments))
            elif t == "error":
                log.warning("realtime error: %s", getattr(event, "error", event))

    def _on_response_done(self, response: Any) -> None:
        if self._current_response == response.id:
            self._current_response = None
        tag = (getattr(response, "metadata", None) or {}).get("tag")
        fut = self._forced_waiters.get(tag) if tag else None
        if fut and not fut.done():
            fut.set_result(None)

    async def _run_tool(self, call_id: str, name: str, arguments: str) -> None:
        try:
            args = json.loads(arguments or "{}")
            result = await self._tool_handler(name, args) if self._tool_handler else {"error": "no tools"}
        except Exception as e:
            log.exception("tool %s failed", name)
            result = {"error": str(e)}
        await self._conn.conversation.item.create(
            item={"type": "function_call_output", "call_id": call_id, "output": json.dumps(result)}
        )
        await self._conn.response.create()

    async def _interrupt(self) -> None:
        if self._current_response:
            self._discarded.add(self._current_response)
            try:
                await self._conn.response.cancel(response_id=self._current_response)
            except Exception:
                pass
            self._current_response = None
        self._flush_playback()

    def _flush_playback(self) -> None:
        try:
            self._mini.media.audio.clear_player()
        except Exception:
            log.debug("clear_player unavailable", exc_info=True)
        self._playback_end = time.monotonic()

    def _play(self, pcm: bytes) -> None:
        samples = resample(pcm16_to_float(pcm), MODEL_RATE, self._out_rate)
        self._mini.media.push_audio_sample(np.asarray(samples, dtype=np.float32))
        now = time.monotonic()
        self._playback_end = max(self._playback_end, now) + len(samples) / self._out_rate

    async def _wait_playback(self) -> None:
        remaining = self._playback_end - time.monotonic()
        if remaining > 0:
            await asyncio.sleep(remaining + 0.2)
