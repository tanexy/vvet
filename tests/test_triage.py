import pytest

from app.schemas import Finding
from app.triage import decide_escalation


def finding(sign_id: str, value: str = "yes") -> Finding:
    return Finding(sign_id=sign_id, value=value, quote="x")


@pytest.mark.parametrize("sign_id", ["froth_nose_mouth", "unable_to_stand", "cloudy_eye"])
@pytest.mark.parametrize("value", ["yes", "not_sure"])
def test_urgent_sign_escalates(sign_id, value):
    escalate, reason = decide_escalation([finding(sign_id, value)])
    assert escalate is True
    assert sign_id in reason
    assert value in reason


@pytest.mark.parametrize("sign_id", ["froth_nose_mouth", "unable_to_stand", "cloudy_eye"])
def test_explicit_no_does_not_escalate(sign_id):
    escalate, reason = decide_escalation([finding(sign_id, "no")])
    assert escalate is False
    assert reason == "No escalation signs reported."


def test_non_urgent_signs_do_not_escalate():
    findings = [finding("weakness"), finding("ticks"), finding("red_urine")]
    assert decide_escalation(findings) == (False, "No escalation signs reported.")


def test_empty_findings_do_not_escalate():
    assert decide_escalation([]) == (False, "No escalation signs reported.")


def test_all_triggers_are_named_in_reason():
    findings = [finding("froth_nose_mouth"), finding("unable_to_stand", "not_sure")]
    escalate, reason = decide_escalation(findings)
    assert escalate is True
    assert "froth_nose_mouth (yes)" in reason
    assert "unable_to_stand (not_sure)" in reason
