"""Input guardrails — PII and toxic language detection.

ponytail: local regex checks. Replace with guardrails hub validators
(ToxicLanguage + DetectPII) when GUARDRAILS_TOKEN is set.
See: guardrails hub install hub://guardrails/toxic_language
"""

import re

TOXIC_PATTERNS = [
    r"\b(pakyu|putangina|tangina|ulol|gago|bobo|tarantado|lintik)\b",
    r"\b(fuck|shit|asshole|bastard|bitch|dick|cunt)\b",
]

PII_PATTERNS = [
    (r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b", "credit card"),
    (r"\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b", "SSN"),
    (r"\b09\d{2}[-\s]?\d{3}[-\s]?\d{4}\b", "PH mobile number"),
    (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "email"),
]


def check_input(text: str) -> tuple[bool, str | None]:
    """Returns (passed, reason_if_blocked)."""
    text_lower = text.lower()

    for pattern in TOXIC_PATTERNS:
        if m := re.search(pattern, text_lower):
            return False, f"Toxic language detected: '{m.group()}'"

    for pattern, label in PII_PATTERNS:
        if m := re.search(pattern, text):
            return False, f"PII detected ({label}): '{m.group()}'"

    return True, None
