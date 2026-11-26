"""Which versions the code's own tables serve: no registry row is ever read for one of them (owner G-LEAD-61).

It holds no registry and loads none, so a site that serves a code-served version (the public-TRAIN loader) can tell
without importing the exam registry.
"""

from __future__ import annotations

#: The host-overlay versions the code's own tables serve. Closed: a later version is a registry row, never a new name
#: here. Every version of the worker image's registry is code-served too
#: (`code_serves`).
CODE_SERVED_OVERLAY = frozenset(
    {
        ("chip-cold-plate", "1.7"),
        ("chip-cold-plate", "1.8"),
        ("electric-motor-magnetics", "1.6"),
        ("electric-motor-magnetics", "1.8"),
    }
)


def code_serves(challenge_id: str, version: str) -> bool:
    """Whether the code's own tables serve the version (a build row for it is refused)."""
    from carbon.challenge_kit import version_overlay

    key = (challenge_id, version)
    return key in CODE_SERVED_OVERLAY or not version_overlay.is_overlay(*key)
