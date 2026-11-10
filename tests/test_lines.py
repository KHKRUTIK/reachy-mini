import pytest
from greeter.lines import first_name, welcome_line, FRONT_DESK_LINE, QR_PROMPT_LINE

@pytest.mark.parametrize("raw,expected", [
    ("Sarah Chen", "Sarah"),
    ("  sarah chen ", "Sarah"),
    ("SARAH", "Sarah"),
    ("Dr Sam Donegan", "Sam"),
    ("Dr. Sam Donegan", "Sam"),
    ("Prof Jane Doe", "Jane"),
    ("Mary-Kate Olsen", "Mary-Kate"),
    ("李伟", "李伟"),
    ("", None),
    (None, None),
    ("sam@example.com", None),
])
def test_first_name_cases(raw, expected):
    assert first_name(raw) == expected

def test_welcome_line_with_name():
    assert welcome_line("Sarah Chen") == "Welcome, Sarah! MLAI welcomes you to the OpenAI Dev Day!"

def test_welcome_line_without_name():
    assert welcome_line(None) == "Welcome! MLAI welcomes you to the OpenAI Dev Day!"

def test_fixed_lines():
    assert FRONT_DESK_LINE == "Hmm, I couldn't check you in. Please find a host at the front desk and they'll sort you out!"
    assert QR_PROMPT_LINE == "Hi! If you haven't checked in yet, just show me the QR code on your Luma ticket."

def test_wrong_code_line():
    from greeter.lines import WRONG_CODE_LINE
    assert WRONG_CODE_LINE == "Ooh, that's the event link! Open your ticket instead, the one with your name under the QR code."

def test_welcome_back_line():
    from greeter.lines import welcome_back_line
    assert welcome_back_line("Alan Philip") == "Welcome back, Alan! You've already checked in, so take a seat whenever you're ready."
    assert welcome_back_line(None) == "Welcome back! You've already checked in, so take a seat whenever you're ready."


def test_all_set_line():
    from greeter.lines import all_set_line
    assert all_set_line("Luis Saso") == "You're all checked in, Luis! Take a seat whenever you're ready."
    assert all_set_line(None) == "You're all checked in! Take a seat whenever you're ready."
