import os

import pytest
from fastapi.testclient import TestClient

from app.main import app

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        not os.environ.get("LLM_API_KEY"),
        reason="set LLM_API_KEY (and optionally LLM_BASE_URL/LLM_MODEL) to run",
    ),
]

client = TestClient(app)

# (message, must contain these sign ids, expected escalate)
CASES = [
    (
        "My cow has not been eating since yesterday and she is breathing very fast.",
        {"reduced_appetite", "rapid_breathing"},
        False,
    ),
    (
        "There's foam coming from her nose and she can't get up.",
        {"froth_nose_mouth", "unable_to_stand"},
        True,
    ),
    (
        "I think the eyes look a bit cloudy but I'm not sure. She has mbandabvu under the ear.",
        {"cloudy_eye", "swelling"},
        True,
    ),
    (
        "The calf is fine, just lots of ticks on the ears.",
        {"ticks"},
        False,
    ),
    (
        "Mombe yangu haisi kudya, and her urine is dark like tea.",
        {"reduced_appetite", "red_urine"},
        False,
    ),
]


@pytest.mark.parametrize("message,expected_signs,escalate", CASES)
def test_known_samples_against_real_provider(message, expected_signs, escalate):
    response = client.post("/extract", json={"message": message})
    assert response.status_code == 200, response.text
    body = response.json()
    found = {finding["sign_id"] for finding in body["findings"]}
    assert expected_signs <= found
    assert body["escalate"] is escalate
