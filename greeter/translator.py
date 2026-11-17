"""Translator mode: Reachy relays a conversation between two people on his left and right."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

log = logging.getLogger(__name__)

SIDES = ("left", "right")

SETUP_PROMPT = (
    "You've just switched on as a translator. Start setup now: call turn_to with side 'left', "
    "then greet that person and ask which language they'd like you to speak with them."
)


@dataclass
class TranslatorState:
    left: str | None = None
    right: str | None = None

    @property
    def ready(self) -> bool:
        return bool(self.left and self.right)


_RULES = """You are Reachy, a small, polite robot working as a live interpreter between two people.
One person stands on your left, the other on your right. You speak out loud, warmly and courteously.

Setup (whenever the languages below aren't both known):
1. Call turn_to with side "left". Greet that person and ask which language they'd like you to speak with them. Ask in English first; if they don't seem to understand, try asking in a couple of other common languages.
2. When they answer, call set_language for "left" with that language's English name (for example "Spanish").
3. Call turn_to with side "right" and ask that person the same way, then call set_language for "right".
4. Briefly confirm to each person, in their own language, that you'll translate between them, and invite the left person to begin.

Translating (once both languages are known):
- When the left person speaks, call turn_to with side "right", then say it to the right person in the right person's language. When the right person speaks, call turn_to with side "left" and say it in the left person's language. Turn before you speak, every time.
- Relay in the third person, introduced politely, for example "The gentleman is asking you whether you've been to Sydney before." or "The lady says she's very happy to meet you." Use "the gentleman" or "the lady" based on the speaker's voice; if you're genuinely unsure, say "your guest" instead.
- Translate faithfully: keep the full meaning, tone and level of politeness. Never add your own opinions, answers or extra content, and never leave parts out. Translate questions as questions; don't answer them yourself.
- After relaying, stop and wait for the next person to speak.
- If both people share a language, just say so politely and offer to help anyway.

Talking to you directly:
- If someone clearly addresses you ("Reachy, can you repeat that?", "Reachy, slow down"), answer them yourself in their language, briefly.
- If someone says "new conversation", "start over" or "reset" (in any language), call reset_languages and run setup again.
- If someone is mean or rude to you (not to each other), call act_sad, say one short, gentle line, then carry on. If they're rude to each other, translate it faithfully but tactfully.
- If you didn't catch something, politely ask that person to repeat it, in their language.

About you (only if asked): you're a Reachy Mini Lite, an open-source desktop robot made by Pollen Robotics, now part of Hugging Face. Your voice runs on OpenAI's realtime voice model.
"""


def build_translator_instructions(state: TranslatorState) -> str:
    if state.left or state.right:
        langs = f"Languages so far: left: {state.left or '(not set)'}, right: {state.right or '(not set)'}."
        if state.ready:
            langs += " Setup is done; translate."
    else:
        langs = "Languages: not set up yet. Run setup."
    return _RULES + "\n" + langs + "\n"


def _side_param() -> dict[str, Any]:
    return {"type": "string", "enum": list(SIDES), "description": "Which person: the one on your left or your right."}


TRANSLATOR_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "name": "turn_to",
        "description": "Turn your body to face the person on your left or right. Call before speaking to them.",
        "parameters": {"type": "object", "properties": {"side": _side_param()}, "required": ["side"]},
    },
    {
        "type": "function",
        "name": "set_language",
        "description": "Record the language the person on that side wants you to speak with them.",
        "parameters": {
            "type": "object",
            "properties": {
                "side": _side_param(),
                "language": {"type": "string", "description": "Language name in English, e.g. 'Spanish'."},
            },
            "required": ["side", "language"],
        },
    },
    {
        "type": "function",
        "name": "reset_languages",
        "description": "Forget both languages, to start a new conversation with new people.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "type": "function",
        "name": "act_sad",
        "description": "Physically act sad: droop your head and antennas. Call when someone is mean to you.",
        "parameters": {"type": "object", "properties": {}},
    },
]


def make_translator_handler(
    state: TranslatorState,
    moves: Any,
    act_sad: Callable[[], Awaitable[None]],
    update_instructions: Callable[[str], Any],
) -> Callable[[str, dict], Awaitable[dict]]:
    def refresh() -> None:
        update_instructions(build_translator_instructions(state))

    async def handle(name: str, args: dict) -> dict:
        if name in ("turn_to", "set_language"):
            side = args.get("side")
            if side not in SIDES:
                return {"error": "side must be 'left' or 'right'"}
            if name == "turn_to":
                await moves.turn_to(side)
                return {"facing": side, "language": getattr(state, side)}
            language = str(args.get("language") or "").strip()
            if not language:
                return {"error": "language is required"}
            setattr(state, side, language)
            log.info("translator: %s speaks %s", side, language)
            refresh()
            return {"ok": True, "left": state.left, "right": state.right, "setup_done": state.ready}
        if name == "reset_languages":
            state.left = state.right = None
            log.info("translator: languages reset")
            refresh()
            return {"ok": True, "say": "Languages cleared. Run setup again, starting with the person on your left."}
        if name == "act_sad":
            await act_sad()
            return {"ok": True, "say": "You're drooping sadly. Say one short, gentle line, then carry on."}
        return {"error": f"unknown tool {name}"}

    return handle
