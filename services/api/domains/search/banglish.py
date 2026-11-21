"""Deterministic, deliberately conservative Banglish normalization."""

import json
import re
import unicodedata
from pathlib import Path

NORMALIZATION_VERSION = "banglish-nfc-v1"
_DICTIONARY = json.loads(
    (Path(__file__).with_name("data") / "banglish_dictionary.json").read_text(encoding="utf-8")
)
_WORDS = re.compile(r"\b[A-Za-z]+\b")
_SPACE = re.compile(r"\s+")
_PUNCT_SPACE = re.compile(r"\s*([,.;:!?])\s*")


def normalize_banglish(value: str) -> str:
    """Normalize known romanized Bangla variants, retaining protected terms verbatim."""
    value = unicodedata.normalize("NFC", value)

    def replace(match: re.Match[str]) -> str:
        word = match.group(0)
        canonical = _DICTIONARY.get(word.casefold())
        return canonical if canonical is not None else word

    value = _WORDS.sub(replace, value)
    value = _PUNCT_SPACE.sub(r"\1 ", value)
    return _SPACE.sub(" ", value).strip(" \t\r\n,.;:")
