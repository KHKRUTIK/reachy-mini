import pytest

from greeter.translator import TRANSLATOR_TOOLS, TranslatorState, build_translator_instructions, make_translator_handler


class FakeMoves:
    def __init__(self): self.turns = []
    async def turn_to(self, side): self.turns.append(side)


def make():
    state, moves, updates, sad = TranslatorState(), FakeMoves(), [], []
    async def act_sad(): sad.append(True)
    handler = make_translator_handler(state, moves, act_sad, updates.append)
    return state, moves, updates, sad, handler


def test_tools_offered():
    assert {t["name"] for t in TRANSLATOR_TOOLS} == {"turn_to", "set_language", "reset_languages", "act_sad"}


def test_instructions_are_translator_only():
    text = build_translator_instructions(TranslatorState())
    assert "gentleman" in text and "lady" in text and "turn_to" in text
    assert "Always speak English" not in text and "QR" not in text and "rate_outfit" not in text
    assert "not set up yet" in text


def test_instructions_include_known_languages():
    text = build_translator_instructions(TranslatorState(left="English", right="Spanish"))
    assert "left: English" in text and "right: Spanish" in text


async def test_set_language_stores_and_refreshes_instructions():
    state, _, updates, _, handle = make()
    out = await handle("set_language", {"side": "left", "language": "English"})
    assert state.left == "English" and out["ok"] is True
    assert "left: English" in updates[-1]
    await handle("set_language", {"side": "right", "language": "Spanish"})
    assert state.ready and "right: Spanish" in updates[-1]


async def test_turn_to_moves_and_reports_language():
    state, moves, _, _, handle = make()
    state.right = "Spanish"
    out = await handle("turn_to", {"side": "right"})
    assert moves.turns == ["right"] and out["facing"] == "right" and out["language"] == "Spanish"


async def test_reset_clears_languages():
    state, _, updates, _, handle = make()
    state.left, state.right = "English", "Spanish"
    await handle("reset_languages", {})
    assert state.left is None and state.right is None and "not set up yet" in updates[-1]


@pytest.mark.parametrize("args", [{"side": "up"}, {}])
async def test_bad_side_is_rejected(args):
    _, moves, _, _, handle = make()
    out = await handle("turn_to", args)
    assert "error" in out and moves.turns == []


async def test_act_sad_and_unknown_tool():
    _, _, _, sad, handle = make()
    assert (await handle("act_sad", {}))["ok"] is True and sad == [True]
    assert "error" in await handle("dance", {})
