"""Illustrative synthetic-text masking, NOT production-safe PAN or account masking.

Real handling requires context-specific policies, Luhn/issuer checks and human review.
These functions are deliberately not advertised as complete banking-data protection.
"""

import re

OTP_PATTERN = re.compile(r"\b(OTP|one[- ]time password|ওটিপি)\s*[:= -]*\d{4,8}\b", re.I)
PAN_PATTERN = re.compile(r"\b(?:\d[ -]?){13,19}\b")


def mask_text(value: str) -> str:
    value = OTP_PATTERN.sub("[OTP]", value)
    value = PAN_PATTERN.sub("[POSSIBLE_CARD_NUMBER]", value)
    return value
