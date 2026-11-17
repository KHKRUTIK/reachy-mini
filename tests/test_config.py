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


def test_event_name_defaults_and_overrides():
    from greeter.config import load_settings
    assert load_settings({"OPENAI_API_KEY": "k"}).event_name == "OpenAI Dev Day"
    assert load_settings({"OPENAI_API_KEY": "k", "EVENT_NAME": "Victor AI Showcase"}).event_name == "Victor AI Showcase"


def test_mode_defaults_to_greeter_and_accepts_translator():
    assert load_settings({"OPENAI_API_KEY": "k"}).mode == "greeter"
    assert load_settings({"OPENAI_API_KEY": "k", "REACHY_MODE": "Translator"}).mode == "translator"


def test_unknown_mode_is_rejected():
    with pytest.raises(ValueError, match="REACHY_MODE"):
        load_settings({"OPENAI_API_KEY": "k", "REACHY_MODE": "dancer"})
