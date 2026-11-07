import json

import pytest
from fastapi.testclient import TestClient

from app.llm import LLMError
from app.main import app, get_llm

client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.clear()


def use_llm(payload) -> None:
    text = payload if isinstance(payload, str) else json.dumps(payload)
    app.dependency_overrides[get_llm] = lambda: (lambda messages: text)


SAMPLES = [
    (
        "My cow has not been eating since yesterday and she is breathing very fast.",
        {
            "findings": [
                {"sign_id": "reduced_appetite", "value": "yes", "quote": "has not been eating"},
                {"sign_id": "rapid_breathing", "value": "yes", "quote": "breathing very fast"},
            ]
        },
        False,
        {"reduced_appetite": "yes", "rapid_breathing": "yes"},
    ),
    (
        "There's foam coming from her nose and she can't get up.",
        {
            "findings": [
                {"sign_id": "froth_nose_mouth", "value": "yes", "quote": "foam coming from her nose"},
                {"sign_id": "unable_to_stand", "value": "yes", "quote": "can't get up"},
            ]
        },
        True,
        {"froth_nose_mouth": "yes", "unable_to_stand": "yes"},
    ),
    (
        "I think the eyes look a bit cloudy but I'm not sure. She has mbandabvu under the ear.",
        {
            "findings": [
                {
                    "sign_id": "cloudy_eye",
                    "value": "not_sure",
                    "quote": "eyes look a bit cloudy but I'm not sure",
                },
                {"sign_id": "swelling", "value": "yes", "quote": "mbandabvu under the ear"},
            ]
        },
        True,
        {"cloudy_eye": "not_sure", "swelling": "yes"},
    ),
    (
        "The calf is fine, just lots of ticks on the ears.",
        {"findings": [{"sign_id": "ticks", "value": "yes", "quote": "lots of ticks on the ears"}]},
        False,
        {"ticks": "yes"},
    ),
    (
        "Mombe yangu haisi kudya, and her urine is dark like tea.",
        {
            "findings": [
                {"sign_id": "reduced_appetite", "value": "yes", "quote": "haisi kudya"},
                {"sign_id": "red_urine", "value": "yes", "quote": "urine is dark like tea"},
            ]
        },
        False,
        {"reduced_appetite": "yes", "red_urine": "yes"},
    ),
]


@pytest.mark.parametrize("message,payload,escalate,expected", SAMPLES)
def test_sample_messages(message, payload, escalate, expected):
    use_llm(payload)
    response = client.post("/extract", json={"message": message})
    assert response.status_code == 200

    body = response.json()
    assert {f["sign_id"]: f["value"] for f in body["findings"]} == expected
    assert body["escalate"] is escalate
    assert body["reason"]
    for item in body["findings"]:
        assert item["quote"] in message


def test_unknown_sign_is_filtered_end_to_end():
    use_llm(
        {
            "findings": [
                {"sign_id": "ticks", "value": "yes", "quote": "ticks"},
                {"sign_id": "broken_leg", "value": "yes", "quote": "ticks"},
            ]
        }
    )
    response = client.post("/extract", json={"message": "lots of ticks"})
    assert response.status_code == 200
    assert [f["sign_id"] for f in response.json()["findings"]] == ["ticks"]


def test_llm_failure_returns_502():
    def boom(messages):
        raise LLMError("LLM request failed")

    app.dependency_overrides[get_llm] = lambda: boom
    response = client.post("/extract", json={"message": "ticks"})
    assert response.status_code == 502
    assert response.json()["detail"] == "LLM request failed"


def test_malformed_llm_json_returns_502():
    use_llm("I think the cow has ticks.")
    response = client.post("/extract", json={"message": "ticks"})
    assert response.status_code == 502


@pytest.mark.parametrize("body", [{}, {"message": ""}, {"message": "   "}])
def test_blank_or_missing_message_returns_422(body):
    response = client.post("/extract", json=body)
    assert response.status_code == 422


def test_no_findings_is_valid():
    use_llm({"findings": []})
    response = client.post("/extract", json={"message": "The calf is fine."})
    assert response.status_code == 200
    assert response.json() == {
        "findings": [],
        "escalate": False,
        "reason": "No escalation signs reported.",
    }
