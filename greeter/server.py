"""Local HTTP server that receives Luma scanner results from the Chrome extension."""
from __future__ import annotations

import asyncio
import time
from datetime import datetime
from pathlib import Path
from typing import Callable

from aiohttp import web

from greeter.checkin import ScanResult

_KINDS = {"success", "failure", "wrong_code", "already"}


def make_app(
    queue: asyncio.Queue[ScanResult],
    debug_log_path: Path,
    clock: Callable[[], float] = time.monotonic,
) -> web.Application:
    async def scan(request: web.Request) -> web.Response:
        try:
            body = await request.json()
        except ValueError:
            return web.json_response({"ok": False, "error": "bad json"}, status=400)
        kind = body.get("kind") if isinstance(body, dict) else None
        name = body.get("name") if isinstance(body, dict) else None
        if kind not in _KINDS or not (name is None or isinstance(name, str)):
            return web.json_response({"ok": False, "error": "bad scan"}, status=400)
        queue.put_nowait(ScanResult(kind, name, clock()))
        return web.json_response({"ok": True})

    async def debug(request: web.Request) -> web.Response:
        try:
            body = await request.json()
        except ValueError:
            return web.json_response({"ok": False}, status=400)
        text = str(body.get("text", "")) if isinstance(body, dict) else ""
        debug_log_path.parent.mkdir(parents=True, exist_ok=True)
        with debug_log_path.open("a", encoding="utf-8") as f:
            f.write(f"{datetime.now().isoformat(timespec='milliseconds')} {text}\n")
        return web.json_response({"ok": True})

    async def health(_: web.Request) -> web.Response:
        return web.json_response({"ok": True})

    app = web.Application()
    app.router.add_post("/scan", scan)
    app.router.add_post("/debug", debug)
    app.router.add_get("/health", health)
    return app


async def start_server(app: web.Application, port: int) -> web.AppRunner:
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "127.0.0.1", port).start()
    return runner
