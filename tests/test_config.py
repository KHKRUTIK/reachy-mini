import pytest
from greeter.config import load_settings

def test_missing_key_raises():
    with pytest.raises(ValueError, match="OPENAI_API_KEY is not set"):
        load_settings({})

def test_blank_key_raises():
    with pytest.raises(ValueError, match="OPENAI_API_KEY is not set"):
        load_settings({"OPENAI_API_KEY": "   "})

def test_defaults_and_overrides():
    s = load_settings({"OPENAI_API_KEY": "sk-x", "GREETER_PORT": "9000"})
    assert s.realtime_model == "gpt-realtime" and s.server_port == 9000
    assert s.event_url == "https://luma.com/event/evt-ZLcgMdLTqHF8bK3"
