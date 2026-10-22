"""F02 (Burst Thermal)'s research key and research contracts.

F02 (Burst Thermal) 2.3 is a direct-recipe-only version: its contracts are the shared
direct campaign's (`carbon.direct_campaign.contracts`), bound to F02 (Burst Thermal)'s spec.
The key in force is F02 (Burst Thermal)'s own (`keyed`); there is no default version.
"""

from __future__ import annotations

from carbon.direct_campaign import contracts as _shared
from carbon.direct_campaign import spec as _spec

SPEC = _spec.F02
CHALLENGE_ID = SPEC.challenge_id


def research_key():
    return _spec.research_key(SPEC)


def keyed(key):
    return _spec.keyed(SPEC, key)


def key_for(version):
    return _spec.key_for(SPEC, version)


def f02_contracts(version):
    return _shared.direct_contracts(SPEC, version)
