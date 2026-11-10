from greeter.arrival import ArrivalPrompter

def run(p, frames):  # frames: list of (t, present)
    return [t for t, present in frames if p.update(present, t)]

def test_prompts_after_dwell():
    p = ArrivalPrompter()
    assert run(p, [(t / 2, True) for t in range(0, 12)]) == [4.0]

def test_scan_during_visit_suppresses_prompt():
    p = ArrivalPrompter()
    p.update(True, 0); p.note_scan(2)
    assert run(p, [(t, True) for t in range(3, 10)]) == []

def test_flicker_under_1s_does_not_reset_dwell():
    p = ArrivalPrompter(flicker_s=1.0)
    frames = [(0, True), (1, True), (2, False), (2.5, True), (3, True), (4, True)]
    assert run(p, frames) == [4]

def test_long_absence_starts_new_visit():
    p = ArrivalPrompter(cooldown_s=0, flicker_s=1.0)
    assert run(p, [(0, True), (1, True), (2, False), (3.5, True), (5, True), (7.5, True)]) == [7.5]

def test_cooldown_between_visits():
    p = ArrivalPrompter(cooldown_s=30.0, flicker_s=1.0)
    assert run(p, [(0, True), (4, True)]) == [4]
    assert run(p, [(6, False), (10, True), (14, True)]) == []  # only 10 s since the last prompt
    assert run(p, [(40, False), (45, True), (49, True)]) == [49]

def test_one_prompt_per_visit():
    p = ArrivalPrompter(cooldown_s=0)
    assert run(p, [(t, True) for t in range(0, 20)]) == [4]

def test_no_face_never_prompts():
    p = ArrivalPrompter()
    assert run(p, [(t, False) for t in range(0, 20)]) == []


def test_defaults_tolerate_5s_absence_and_60s_cooldown():
    p = ArrivalPrompter()
    assert run(p, [(0, True), (4, True)]) == [4]
    # gone 4 s: still the same visit -> no second prompt
    assert run(p, [(5, False), (9, True), (15, True)]) == []
    # gone 10 s: new visit, but only 41 s since last prompt -> wait for the cooldown
    assert run(p, [(20, False), (30, True), (34, True), (44, True), (64, True)]) == [64]


def test_can_prompt_false_holds_prompt_without_consuming_it():
    p = ArrivalPrompter()
    assert p.update(True, 0) is False
    assert p.update(True, 5, can_prompt=False) is False
    assert p.update(True, 6) is True


def test_any_recent_scan_blocks_prompt_for_60s():
    p = ArrivalPrompter()
    p.note_scan(0)                      # someone else scanned, no face visit yet
    assert run(p, [(10, True), (20, True), (59, True)]) == []
    assert run(p, [(70, False), (80, True), (84, True)]) == [84]
