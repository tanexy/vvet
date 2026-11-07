from typing import Literal

SignId = Literal[
    "reduced_appetite",
    "weakness",
    "swelling",
    "rapid_breathing",
    "cloudy_eye",
    "froth_nose_mouth",
    "red_urine",
    "unable_to_stand",
    "ticks",
]

# Insertion order is the order findings are returned in.
SIGNS: dict[str, str] = {
    "reduced_appetite": "eating less, or has stopped eating or grazing",
    "weakness": "dull, weak, lying down more than usual",
    "swelling": "a lump below the ear, under the jaw, or in front of the shoulder; also called mbandabvu",
    "rapid_breathing": "breathing fast while resting",
    "cloudy_eye": "the eye looks white, grey or milky",
    "froth_nose_mouth": "foam or froth from the nose or mouth",
    "red_urine": "urine that is red, brown, or the colour of strong tea",
    "unable_to_stand": "cannot get up or stay standing",
    "ticks": "ticks can be seen on the animal",
}

SIGN_ORDER: list[str] = list(SIGNS)

URGENT_SIGNS: frozenset[str] = frozenset(
    {"froth_nose_mouth", "unable_to_stand", "cloudy_eye"}
)
