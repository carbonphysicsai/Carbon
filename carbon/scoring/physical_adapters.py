"""Which dual pack adapter scores a physical Challenge version.

Kept out of every producer's identity (``physical_dual_pack._SHARED_FILES``):
selecting an adapter measures nothing, so registering a new Challenge here
never re-versions, or unbinds the calibration packs of, the others. Each
adapter's own files and the shared core stay in its producer digest.
"""

from __future__ import annotations


def adapter(challenge, version):
    """The physical Challenge version's dual pack adapter, or None."""
    from carbon.scoring import (
        battery_dual_pack,
        cooling_dual_pack,
        f02_dual_pack,
        f08_dual_pack,
        motor_dual_pack,
    )

    if challenge == f08_dual_pack.CHALLENGE:
        return (
            f08_dual_pack.adapter(version=version)
            if version in f08_dual_pack.VERSIONS
            else None
        )
    if challenge == f02_dual_pack.CHALLENGE:
        return f02_dual_pack if version == f02_dual_pack.VERSION else None
    return {
        module.CHALLENGE: module
        for module in (motor_dual_pack, cooling_dual_pack, battery_dual_pack)
    }.get(challenge)
