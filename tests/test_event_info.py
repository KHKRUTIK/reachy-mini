import httpx
import pytest

from greeter.event_info import build_instructions, fetch_event_text, html_to_text


def test_html_to_text_drops_scripts():
    assert html_to_text("<p>Hi</p><script>x=1</script><p>there</p>") == "Hi there"


def test_html_to_text_drops_styles_and_collapses_whitespace():
    assert html_to_text("<style>p{}</style><h1>  Build\n time </h1><noscript>no</noscript>") == "Build time"


def test_instructions_contain_rules_and_facts():
    s = build_instructions("Build time 10:15", "Wi-Fi: MLAI-guest")
    for must in ["Reachy", "MLAI", "one or two sentences", "front desk", "Build time 10:15", "Wi-Fi: MLAI-guest"]:
        assert must in s


def test_instructions_forbid_guessing_names():
    assert "never guess" in build_instructions("x", "").lower()


async def test_fetch_writes_cache(tmp_path, monkeypatch):
    async def fake_get(self, url, **kw):
        return httpx.Response(200, text="<p>Demos at 1pm</p>", request=httpx.Request("GET", url))
    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    cache = tmp_path / "event_info.md"
    assert await fetch_event_text("https://luma.com/x", cache) == "Demos at 1pm"
    assert cache.read_text() == "Demos at 1pm"


async def test_fetch_falls_back_to_cache(tmp_path, monkeypatch):
    async def boom(self, url, **kw):
        raise httpx.ConnectError("offline")
    monkeypatch.setattr(httpx.AsyncClient, "get", boom)
    cache = tmp_path / "event_info.md"
    cache.write_text("cached")
    assert await fetch_event_text("https://luma.com/x", cache) == "cached"


async def test_fetch_without_cache_raises(tmp_path, monkeypatch):
    async def boom(self, url, **kw):
        raise httpx.ConnectError("offline")
    monkeypatch.setattr(httpx.AsyncClient, "get", boom)
    with pytest.raises(httpx.ConnectError):
        await fetch_event_text("https://luma.com/x", tmp_path / "none.md")


def test_instructions_include_robot_self_knowledge():
    text = build_instructions("event", "")
    for fact in ("Reachy Mini Lite", "Pollen Robotics", "Hugging Face", "antennas", "rate", "can't walk"):
        assert fact in text
