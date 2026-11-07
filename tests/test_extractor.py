import json

import pytest

from app.extractor import ExtractionError, parse_output


def payload(*findings: dict) -> str:
    return json.dumps({"findings": list(findings)})


def test_keeps_only_allowed_sign_ids():
    raw = payload(
        {"sign_id": "ticks", "value": "yes", "quote": "ticks"},
        {"sign_id": "hair_loss", "value": "yes", "quote": "ticks"},
    )
    findings = parse_output(raw, "ticks on the ears")
    assert [f.sign_id for f in findings] == ["ticks"]


def test_drops_invalid_value():
    raw = payload({"sign_id": "ticks", "value": "maybe", "quote": "ticks"})
    assert parse_output(raw, "ticks on the ears") == []


def test_drops_quote_not_in_message():
    raw = payload({"sign_id": "froth_nose_mouth", "value": "yes", "quote": "foam from the mouth"})
    assert parse_output(raw, "She is eating well") == []


def test_accepts_quote_with_different_case_and_spacing():
    raw = payload({"sign_id": "ticks", "value": "yes", "quote": "  LOTS   of ticks "})
    findings = parse_output(raw, "there are lots of ticks on her")
    assert findings[0].quote == "  LOTS   of ticks "


def test_drops_blank_quote():
    raw = payload({"sign_id": "ticks", "value": "yes", "quote": "   "})
    assert parse_output(raw, "ticks on the ears") == []


def test_deduplicates_keeping_strongest_value():
    raw = payload(
        {"sign_id": "ticks", "value": "not_sure", "quote": "ticks"},
        {"sign_id": "ticks", "value": "yes", "quote": "ticks"},
        {"sign_id": "ticks", "value": "no", "quote": "ticks"},
    )
    findings = parse_output(raw, "ticks on the ears")
    assert len(findings) == 1
    assert findings[0].value == "yes"


def test_returns_catalogue_order():
    raw = payload(
        {"sign_id": "ticks", "value": "yes", "quote": "ticks"},
        {"sign_id": "reduced_appetite", "value": "yes", "quote": "not eating"},
    )
    findings = parse_output(raw, "not eating, ticks")
    assert [f.sign_id for f in findings] == ["reduced_appetite", "ticks"]


def test_accepts_markdown_fenced_json():
    raw = '```json\n{"findings": [{"sign_id": "ticks", "value": "yes", "quote": "ticks"}]}\n```'
    findings = parse_output(raw, "ticks")
    assert findings[0].sign_id == "ticks"


def test_empty_findings_is_valid():
    assert parse_output('{"findings": []}', "the calf is fine") == []


@pytest.mark.parametrize(
    "raw",
    [
        "not json",
        '{"findings": "ticks"}',
        '{"signs": []}',
        '["ticks"]',
    ],
)
def test_bad_shape_raises(raw):
    with pytest.raises(ExtractionError):
        parse_output(raw, "ticks")
