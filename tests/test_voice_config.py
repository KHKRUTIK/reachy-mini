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
