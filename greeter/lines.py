"""Exact lines Reachy speaks, and first-name extraction."""
from __future__ import annotations

FRONT_DESK_LINE = "Hmm, I couldn't check you in. Please find a host at the front desk and they'll sort you out!"
QR_PROMPT_LINE = "Hi! If you haven't checked in yet, just show me the QR code on your Luma ticket."

_HONORIFICS = {"dr", "mr", "mrs", "ms", "mx", "prof"}


def first_name(full_name: str | None) -> str | None:
    if not full_name or "@" in full_name:
        return None
    tokens = full_name.split()
    if tokens and tokens[0].rstrip(".").lower() in _HONORIFICS:
        tokens = tokens[1:]
    if not tokens:
        return None
    token = tokens[0]
    if token.isascii() and (token.isupper() or token.islower()):
        token = token.capitalize()
    return token


def welcome_line(full_name: str | None) -> str:
    name = first_name(full_name)
    greeting = f"Welcome, {name}!" if name else "Welcome!"
    return f"{greeting} MLAI welcomes you to the OpenAI Dev Day!"
