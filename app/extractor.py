import json
import logging
import re
from collections.abc import Callable

from pydantic import ValidationError

from .schemas import Finding
from .signs import SIGN_ORDER, SIGNS

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You extract clinical signs from messages that farmers send about their cattle.

Return ONLY a JSON object of this shape:
{"findings": [{"sign_id": "...", "value": "yes|no|not_sure", "quote": "..."}]}

Allowed sign_id values and meanings:
- reduced_appetite: eating less, or has stopped eating or grazing
- weakness: dull, weak, lying down more than usual
- swelling: a lump below the ear, under the jaw, or in front of the shoulder; farmers may call it mbandabvu
- rapid_breathing: breathing fast while resting
- cloudy_eye: the eye looks white, grey or milky
- froth_nose_mouth: foam or froth from the nose or mouth
- red_urine: urine that is red, brown, or the colour of strong tea
- unable_to_stand: cannot get up or stay standing
- ticks: ticks can be seen on the animal

Rules:
1. Only include a sign the message actually mentions. Never add a sign because it often occurs with another sign. Return {"findings": []} if none are mentioned.
2. value is "yes" when the message states the sign, "no" only when the message explicitly denies it (for example "no foam"), and "not_sure" when the farmer expresses doubt about that sign.
3. quote must be an exact, verbatim substring copied from the message that supports the finding. Do not translate, correct or paraphrase it.
4. Messages may mix English with Shona or Ndebele. Understand phrases such as "haisi kudya" (not eating) and "mbandabvu" (swelling).
5. Never output a sign_id that is not in the list above.
6. Output JSON only, with no markdown fences or explanation.

Example: "The calf is fine, just lots of ticks on the ears."
{"findings": [{"sign_id": "ticks", "value": "yes", "quote": "lots of ticks on the ears"}]}"""

_FENCE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL)
_VALUE_RANK = {"yes": 2, "not_sure": 1, "no": 0}


class ExtractionError(RuntimeError):
    """The LLM response was not a usable findings payload."""


def build_messages(message: str) -> list[dict]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": message},
    ]


def _normalise(text: str) -> str:
    return " ".join(text.split()).casefold()


def parse_output(raw: str, message: str) -> list[Finding]:
    """Keep only valid, mentioned, deduplicated findings from the model."""
    cleaned = _FENCE.sub(r"\1", raw).strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ExtractionError("LLM did not return valid JSON") from exc

    if not isinstance(data, dict) or not isinstance(data.get("findings"), list):
        raise ExtractionError("LLM output is missing a findings list")

    normalised_message = _normalise(message)
    kept: dict[str, Finding] = {}

    for item in data["findings"]:
        try:
            finding = Finding.model_validate(item)
        except ValidationError:
            logger.warning("dropped malformed or unknown finding: %r", item)
            continue

        quote = _normalise(finding.quote)
        if not quote or quote not in normalised_message:
            logger.warning("dropped finding with unsupported quote: %s", finding.sign_id)
            continue

        previous = kept.get(finding.sign_id)
        if previous is None or _VALUE_RANK[finding.value] > _VALUE_RANK[previous.value]:
            kept[finding.sign_id] = finding

    return [kept[sign_id] for sign_id in SIGN_ORDER if sign_id in kept]


def extract(message: str, llm: Callable[[list[dict]], str]) -> list[Finding]:
    return parse_output(llm(build_messages(message)), message)
