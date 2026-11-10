import asyncio

from greeter.checkin import ScanResult
from greeter.server import make_app


async def test_scan_enqueues(aiohttp_client, tmp_path):
    q = asyncio.Queue()
    c = await aiohttp_client(make_app(q, tmp_path / "d.log", clock=lambda: 7.0))
    r = await c.post("/scan", json={"kind": "success", "name": "Sam Lee"})
    assert r.status == 200 and await r.json() == {"ok": True}
    assert q.get_nowait() == ScanResult("success", "Sam Lee", 7.0)


async def test_null_name_allowed(aiohttp_client, tmp_path):
    q = asyncio.Queue()
    c = await aiohttp_client(make_app(q, tmp_path / "d.log", clock=lambda: 1.0))
    r = await c.post("/scan", json={"kind": "failure", "name": None})
    assert r.status == 200 and q.get_nowait() == ScanResult("failure", None, 1.0)


async def test_bad_kind_rejected(aiohttp_client, tmp_path):
    q = asyncio.Queue()
    c = await aiohttp_client(make_app(q, tmp_path / "d.log"))
    assert (await c.post("/scan", json={"kind": "maybe"})).status == 400 and q.empty()


async def test_bad_json_rejected(aiohttp_client, tmp_path):
    q = asyncio.Queue()
    c = await aiohttp_client(make_app(q, tmp_path / "d.log"))
    r = await c.post("/scan", data="not json", headers={"Content-Type": "application/json"})
    assert r.status == 400 and q.empty()


async def test_debug_appends(aiohttp_client, tmp_path):
    c = await aiohttp_client(make_app(asyncio.Queue(), tmp_path / "d.log"))
    await c.post("/debug", json={"text": "Checked in Sam"})
    assert "Checked in Sam" in (tmp_path / "d.log").read_text()


async def test_health(aiohttp_client, tmp_path):
    c = await aiohttp_client(make_app(asyncio.Queue(), tmp_path / "d.log"))
    r = await c.get("/health")
    assert r.status == 200 and await r.json() == {"ok": True}


async def test_wrong_code_accepted(aiohttp_client, tmp_path):
    q = asyncio.Queue()
    c = await aiohttp_client(make_app(q, tmp_path / "d.log", clock=lambda: 2.0))
    r = await c.post("/scan", json={"kind": "wrong_code", "name": None})
    assert r.status == 200 and q.get_nowait() == ScanResult("wrong_code", None, 2.0)


async def test_already_accepted(aiohttp_client, tmp_path):
    q = asyncio.Queue()
    c = await aiohttp_client(make_app(q, tmp_path / "d.log", clock=lambda: 3.0))
    r = await c.post("/scan", json={"kind": "already", "name": "Sam"})
    assert r.status == 200 and q.get_nowait() == ScanResult("already", "Sam", 3.0)
