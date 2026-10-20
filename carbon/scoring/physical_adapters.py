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


def register(module):
    """Make a validator-side adapter selectable (idempotent)."""
    known = _REGISTERED.get(module.CHALLENGE)
    if known is not None and known is not module:
        raise ValueError("a different adapter is registered for this Challenge")
    _REGISTERED[module.CHALLENGE] = module
    return module


def adapter(challenge, version):
    """The physical Challenge version's dual pack adapter, or None."""
    from carbon.scoring import (
        cooling_dual_pack,
        f02_dual_pack,
        f08_dual_pack,
        motor_dual_pack,
    )

    if challenge == f02_dual_pack.CHALLENGE:
        return f02_dual_pack if version == f02_dual_pack.VERSION else None
    if challenge == f08_dual_pack.CHALLENGE:
        return (
            f08_dual_pack.adapter(version=version)
            if version in f08_dual_pack.VERSIONS
            else None
        )
    registered = _REGISTERED.get(challenge)
    if registered is not None:
        return registered if version == registered.VERSION else None
    return {
        module.CHALLENGE: module for module in (motor_dual_pack, cooling_dual_pack)
    }.get(challenge)
