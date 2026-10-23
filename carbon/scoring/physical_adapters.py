"""Which dual pack adapter scores a physical Challenge version.

Kept out of every producer's identity (``physical_dual_pack._SHARED_FILES``):
selecting an adapter measures nothing, so registering a new Challenge here
never re-versions, or unbinds the calibration packs of, the others. Each
adapter's own files and the shared core stay in its producer digest.

Two kinds of adapter. Motor, Cooling, F02 and F08 are named here. An adapter whose
pinned value modules reach code no miner surface may import (Battery's reach
its panel's attack harness, OWNER-GRAPHITE-ATTACKER-01) is not imported here
at all: validator-only code ``register``s it before grading, so a process
that never runs the validator's retention never loads it.
"""

from __future__ import annotations

#: Challenge id -> adapter module, registered by validator-only code.
_REGISTERED = {}


def _static():
    """The statically named adapters, by Challenge id (F08 and F02 choose a
    version-specific adapter)."""
    from carbon.scoring import (
        cooling_dual_pack,
        cooling_encoded_dual_pack,
        f02_dual_pack,
        f08_dual_pack,
        motor_dual_pack,
    )
    from carbon.scoring import physical_dual_pack as physical

    # Exactly the registered version, never a default (an unknown version is
    # None: the evaluation is unavailable).
    return {
        motor_dual_pack.CHALLENGE: lambda version: physical.versioned(
            motor_dual_pack, version
        ),
        # Cooling 1.3's law-safe encoding has its own adapter module, so the
        # 1.0-1.2 producer identity (and every pack bound to it) is unchanged.
        cooling_dual_pack.CHALLENGE: lambda version: (
            physical.versioned(cooling_encoded_dual_pack, version)
            if version in cooling_encoded_dual_pack.VERSIONS
            else physical.versioned(cooling_dual_pack, version)
        ),
        f08_dual_pack.CHALLENGE: lambda version: (
            f08_dual_pack.adapter(version=version)
            if version in f08_dual_pack.VERSIONS
            else None
        ),
        f02_dual_pack.CHALLENGE: lambda version: physical.versioned(
            f02_dual_pack, version
        ),
    }


def register(module):
    """Make a validator-side adapter selectable (idempotent). A statically
    named Challenge, or a different adapter already registered, refuses: no
    registration can shadow another adapter."""
    if module.CHALLENGE in _static():
        raise ValueError("a statically named Challenge cannot be registered")
    known = _REGISTERED.get(module.CHALLENGE)
    if known is not None and known is not module:
        raise ValueError("a different adapter is registered for this Challenge")
    _REGISTERED[module.CHALLENGE] = module
    return module


def adapter(challenge, version):
    """The physical Challenge version's dual pack adapter, or None
    (statically named Challenges first, then validator-registered ones)."""
    static = _static().get(challenge)
    if static is not None:
        return static(version)
    registered = _REGISTERED.get(challenge)
    if registered is None:
        return None
    from carbon.scoring import physical_dual_pack as physical

    return physical.versioned(registered, version)
