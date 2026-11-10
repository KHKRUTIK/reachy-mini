"""Run the scan/debug server alone and print every /scan result (debug text goes to logs/scanner-debug.log)."""
import asyncio
from pathlib import Path

from greeter.server import make_app, start_server


async def main() -> None:
    q: asyncio.Queue = asyncio.Queue()
    await start_server(make_app(q, Path("logs/scanner-debug.log")), 8765)
    print("debug server on http://127.0.0.1:8765 — debug text -> logs/scanner-debug.log", flush=True)
    while True:
        print("SCAN", await q.get(), flush=True)


asyncio.run(main())
