"""The version key of the host-side registries (the Lead's ruling, 13 Nov: Motor 1.8 must not move 1.5's live values).

`koth_rebuild_noise.json` (rebuild noise and control) and `crown_average.json` (N and margin_N) were keyed by Challenge id
alone, so every version of a Challenge shared one value. A registered entry may now also be keyed
``"<challenge id> <version>"``. A lookup reads that key FIRST and falls back to the bare Challenge id, so:

- every registry as committed (bare ids only) reads exactly as before, for every version;
- a version with its own entry decides on its own measurement, and no other version's value moves.

Which version a lookup means: the one named in the call, else the version this receiver serves (`serve`, set once at start
from the receiver's material, as `crown_hold.install` does: a receiver serves one Challenge version), else none (the bare
id). A served version applies only to its own Challenge.
"""

from __future__ import annotations

#: ``(challenge_id, version)`` this process serves, or None.
SERVED = None


def serve(challenge_id, version):
    """Name the version this process serves (None, None clears it)."""
    global SERVED
    if challenge_id is None and version is None:
        SERVED = None
        return
    if not all(type(x) is str and x and " " not in x for x in (challenge_id, version)):
        raise ValueError("served_version_invalid")
    SERVED = (challenge_id, version)


def keys(challenge_id, version=None):
    """The registry keys to read, in order: ``"<id> <version>"`` when a version applies, then the bare id."""
    if version is None and SERVED is not None and SERVED[0] == challenge_id:
        version = SERVED[1]
    if version is None:
        return (challenge_id,)
    return (f"{challenge_id} {version}", challenge_id)


def known_key(key, known):
    """Whether a registry key is a registered Challenge id, or a registered id and one version (no space in either)."""
    if key in known:
        return True
    challenge, _, version = key.partition(" ")
    return challenge in known and bool(version) and " " not in version


def find(table, challenge_id, version=None):
    """The first entry of ``table`` under `keys`, or None."""
    for key in keys(challenge_id, version):
        if key in table:
            return table[key]
    return None
