from greeter.config import Settings
from greeter.voice import build_session_config, forced_response

S = Settings(openai_api_key="sk-x", voice="marin")


def test_session_uses_24k_pcm_both_ways():
    c = build_session_config(S, "be nice", [])
    assert c["audio"]["input"]["format"] == {"type": "audio/pcm", "rate": 24000}
    assert c["audio"]["output"]["format"] == {"type": "audio/pcm", "rate": 24000}


def test_session_barge_in_and_short_answers():
    c = build_session_config(S, "be nice", [])
    vad = c["audio"]["input"]["turn_detection"]
    assert vad["type"] == "server_vad" and vad["interrupt_response"] is True
    assert vad["silence_duration_ms"] == 600
    assert c["max_output_tokens"] == 200


def test_session_voice_instructions_and_tools():
    tool = {"type": "function", "name": "find_guest", "parameters": {"type": "object", "properties": {}}}
    c = build_session_config(S, "be nice", [tool])
    assert c["audio"]["output"]["voice"] == "marin"
    assert c["instructions"] == "be nice"
    assert c["tools"] == [tool] and c["tool_choice"] == "auto"


def test_session_without_tools_omits_tool_choice():
    assert "tool_choice" not in build_session_config(S, "x", [])


def test_forced_response_is_out_of_band_and_exact():
    r = forced_response("Welcome, Sam!", tag="t1")
    assert r["conversation"] == "none"
    assert r["metadata"] == {"tag": "t1"}
    assert r["instructions"].endswith("Welcome, Sam!")
    assert "exactly" in r["instructions"]
    assert r["output_modalities"] == ["audio"]


class _Media:
    def get_input_audio_samplerate(self): return 16000
    def get_output_audio_samplerate(self): return 16000


class _Mini:
    media = _Media()


def test_conversation_activity_window():
    from greeter.voice import RealtimeVoice
    v = RealtimeVoice(S, _Mini(), "x")
    assert v.active_within(10.0, now=100.0) is False
    v.note_activity(now=95.0)
    assert v.active_within(10.0, now=100.0) is True
    assert v.active_within(10.0, now=106.0) is False


async def test_session_ends_when_event_loop_ends_and_mic_is_cancelled():
    import asyncio
    from greeter.voice import RealtimeVoice
    v = RealtimeVoice(S, _Mini(), "x")
    mic_cancelled = asyncio.Event()
    async def mic():
        try:
            await asyncio.sleep(3600)
        except asyncio.CancelledError:
            mic_cancelled.set()
            raise
    async def events():
        return  # server closed the socket cleanly
    v._mic_loop, v._event_loop = mic, events
    await asyncio.wait_for(v._run_session(), 1.0)
    assert mic_cancelled.is_set()


async def test_say_exact_gives_up_when_not_connected():
    import asyncio
    from greeter.voice import RealtimeVoice
    v = RealtimeVoice(S, _Mini(), "x")
    await asyncio.wait_for(v.say_exact("hi", connect_timeout_s=0.05), 1.0)  # must not hang
