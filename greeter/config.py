"""Runtime settings, read from the environment (.env)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class Settings:
    openai_api_key: str
    realtime_model: str = "gpt-realtime"
    voice: str = "marin"
    compliment_model: str = "gpt-4.1-mini"
    server_port: int = 8765
    daemon_url: str = "http://127.0.0.1:8000"
    event_url: str = "https://luma.com/event/evt-ZLcgMdLTqHF8bK3"


_OPTIONAL = {
    "REALTIME_MODEL": ("realtime_model", str),
    "REALTIME_VOICE": ("voice", str),
    "COMPLIMENT_MODEL": ("compliment_model", str),
    "GREETER_PORT": ("server_port", int),
    "DAEMON_URL": ("daemon_url", str),
    "EVENT_URL": ("event_url", str),
}


def load_settings(env: Mapping[str, str]) -> Settings:
    key = (env.get("OPENAI_API_KEY") or "").strip()
    if not key:
        raise ValueError("OPENAI_API_KEY is not set")
    overrides = {
        field: cast(env[name].strip())
        for name, (field, cast) in _OPTIONAL.items()
        if (env.get(name) or "").strip()
    }
    return Settings(openai_api_key=key, **overrides)
