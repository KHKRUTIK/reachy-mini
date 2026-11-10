import asyncio

from greeter.speech import SpeechQueue


async def test_two_scans_are_spoken_in_order():
    spoken = []
    async def say(t):
        await asyncio.sleep(0.05)
        spoken.append(t)
    q = SpeechQueue(say)
    task = asyncio.create_task(q.run())
    await q.put("Welcome, Sam!")
    await q.put("Welcome, Ann!")
    await asyncio.sleep(0.2)
    task.cancel()
    assert spoken == ["Welcome, Sam!", "Welcome, Ann!"]


async def test_never_overlaps():
    active, peak = 0, 0
    async def say(t):
        nonlocal active, peak
        active += 1; peak = max(peak, active)
        await asyncio.sleep(0.02)
        active -= 1
    q = SpeechQueue(say)
    task = asyncio.create_task(q.run())
    for i in range(5):
        await q.put(str(i))
    await asyncio.sleep(0.2)
    task.cancel()
    assert peak == 1


async def test_failed_line_does_not_stop_queue():
    spoken = []
    async def say(t):
        if t == "bad":
            raise RuntimeError("tts failed")
        spoken.append(t)
    q = SpeechQueue(say)
    task = asyncio.create_task(q.run())
    await q.put("bad"); await q.put("good")
    await asyncio.sleep(0.05)
    task.cancel()
    assert spoken == ["good"]
