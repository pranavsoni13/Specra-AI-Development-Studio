from __future__ import annotations

import re
from typing import Iterable

AUTH_TERMS = (
    "authentication", "auth", "authenticate", "authenticated", "login",
    "log in", "sign in", "sign up", "signup", "password", "credentials",
    "authorization", "authorisation", "access control", "identity provider",
    "identity management", "jwt", "oauth", "user account", "user accounts",
)
AUTH_PATTERN = r"(?:authentication|auth|authenticate|authenticated|login|log\s+in|sign\s*in|sign\s*up|signup|passwords?|credentials|authorization|authorisation|access\s+control|identity\s+provider|identity\s+management|user\s+accounts?|jwt|oauth)"
AUTH_RE = re.compile(rf"\b{AUTH_PATTERN}\b", re.IGNORECASE)
NEGATION_BEFORE_RE = re.compile(
    rf"\b(?:no|without|avoid|exclude|prohibit(?:ed)?|forbid(?:den)?)\b(?:\s+[a-z]+){{0,5}}\s+{AUTH_PATTERN}\b",
    re.IGNORECASE,
)
NEGATION_COMMAND_RE = re.compile(
    rf"\b(?:do\s+not|don['’]?t|does\s+not|doesn['’]?t|must\s+not|should\s+not|will\s+not|won['’]?t|never)\b.{{0,100}}\b{AUTH_PATTERN}\b",
    re.IGNORECASE,
)
NEGATION_AFTER_RE = re.compile(
    rf"\b{AUTH_PATTERN}\b.{{0,50}}\b(?:not\s+(?:required|needed|allowed|permitted)|unnecessary|prohibited|forbidden|disabled|excluded)\b",
    re.IGNORECASE,
)


def _segments(text: str) -> Iterable[str]:
    return (
        segment.strip()
        for segment in re.split(r"[\n;.!?]+", text)
        if segment.strip()
    )


def _is_negated(segment: str) -> bool:
    if not AUTH_RE.search(segment):
        return False
    return any(pattern.search(segment) for pattern in (
        NEGATION_BEFORE_RE, NEGATION_COMMAND_RE, NEGATION_AFTER_RE
    ))


def authentication_policy(requirements) -> tuple[bool, bool]:
    """Return (authentication_required, authentication_prohibited).

    Explicit prohibition takes precedence over incidental keyword mentions.
    """
    sources = [
        requirements.objective,
        *requirements.functional_requirements,
        *requirements.non_functional_requirements,
        *requirements.constraints,
    ]
    prohibited = any(
        _is_negated(segment)
        for source in sources
        for segment in _segments(source)
    )
    required = any(
        AUTH_RE.search(segment) and not _is_negated(segment)
        for source in sources
        for segment in _segments(source)
    )
    if prohibited:
        required = False
    return required, prohibited
