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
    p = ArrivalPrompter()
    frames = [(0, True), (1, True), (2, False), (2.5, True), (3, True), (4, True)]
    assert run(p, frames) == [4]

def test_long_absence_starts_new_visit():
    p = ArrivalPrompter(cooldown_s=0)
    assert run(p, [(0, True), (1, True), (2, False), (3.5, True), (5, True), (7.5, True)]) == [7.5]

def test_cooldown_between_visits():
    p = ArrivalPrompter()
    assert run(p, [(0, True), (4, True)]) == [4]
    assert run(p, [(6, False), (10, True), (14, True)]) == []  # only 10 s since the last prompt
    assert run(p, [(40, False), (45, True), (49, True)]) == [49]

def test_one_prompt_per_visit():
    p = ArrivalPrompter(cooldown_s=0)
    assert run(p, [(t, True) for t in range(0, 20)]) == [4]

def test_no_face_never_prompts():
    p = ArrivalPrompter()
    assert run(p, [(t, False) for t in range(0, 20)]) == []
