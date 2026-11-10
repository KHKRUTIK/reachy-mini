from greeter.checkin import CheckinGate, ScanResult as R

def test_success_welcomes():
    assert CheckinGate().decide(R("success", "Sam Lee", 0)) == "welcome"

def test_failure_goes_to_front_desk():
    assert CheckinGate().decide(R("failure", None, 0)) == "front_desk"

def test_success_then_already_checked_in_same_name_is_ignored():
    g = CheckinGate()
    g.decide(R("success", "Sam Lee", 0))
    assert g.decide(R("failure", "sam lee", 5)) == "ignore"
    assert g.decide(R("success", "Sam Lee", 30)) == "ignore"

def test_same_name_after_window_is_handled_again():
    g = CheckinGate()
    g.decide(R("success", "Sam Lee", 0))
    assert g.decide(R("failure", "Sam Lee", 61)) == "front_desk"

def test_repeated_failure_within_15s_is_ignored():
    g = CheckinGate()
    assert g.decide(R("failure", "Ann", 0)) == "front_desk"
    assert g.decide(R("failure", "Ann", 10)) == "ignore"
    assert g.decide(R("failure", "Ann", 16)) == "front_desk"

def test_repeated_nameless_failure_within_15s_is_ignored():
    g = CheckinGate()
    assert g.decide(R("failure", None, 0)) == "front_desk"
    assert g.decide(R("failure", None, 3)) == "ignore"

def test_different_people_are_independent():
    g = CheckinGate()
    g.decide(R("success", "Sam Lee", 0))
    assert g.decide(R("success", "Ann Wu", 1)) == "welcome"
