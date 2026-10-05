"""Attack adapters: one per Challenge and construction level
(OWNER-GRAPHITE-ATTACKER-01).

The attack engine (`carbon.agent_campaign.attack`) is Challenge-neutral.
Everything specific to one Challenge at one construction level lives in one
module here, which exposes `ADAPTER`: its contract, the eight shared Track A
checks as attack families (each with an attack example and a valid control,
controls split trained/held-out and versioned), Carbon's own oracle, Carbon's
rebuild with typed refusals, the higher-level families it declares NOT_RUN,
and the session surface a Graphite session needs.

`BUILTIN` names each adapter by `(challenge_id, level)`. Importing this
package registers every one of them in the core's registry
(`attack.adapter.ADAPTERS`), which imports this package the first time it is
read. `load` returns one adapter.

An adapter grants nothing: grants, ceilings, stage gates and the construction
contract keep their own authority. No miner edition or Launchpad module may
import this package (`tests/invariants/test_attack_store_unreachable.py`).
"""

from __future__ import annotations

import importlib
import importlib.util


def _core_present():
    try:
        spec = importlib.util.find_spec("carbon.agent_campaign.attack.adapter")
    except ModuleNotFoundError:
        return False
    return spec is not None


# Only an absent core is tolerated (before the neutral core merges). A core
# that is present but fails to import raises here instead of being skipped.
if _core_present():
    from carbon.agent_campaign.attack import adapter as _core
else:  # pragma: no cover - only before the neutral core merges
    _core = None

#: Every adapter Carbon ships, by `(challenge_id, construction level)`.
BUILTIN = {
    (
        "battery-fastcharge-ageing-development-v1",
        0,
    ): "carbon.agent_campaign.attack.adapters.battery",
    (
        "battery-fastcharge-ageing-development-v1",
        1,
    ): "carbon.agent_campaign.attack.adapters.battery_level1",
    ("chip-cold-plate", 0): "carbon.agent_campaign.attack.adapters.cooling",
    ("electric-motor-magnetics", 0): "carbon.agent_campaign.attack.adapters.motor",
}


class AdapterNotRegistered(LookupError):
    """No adapter is registered for that Challenge at that level."""


def _module_adapter(challenge_id, level):
    name = BUILTIN.get((challenge_id, level))
    if name is None:
        raise AdapterNotRegistered(f"{challenge_id}@level-{level}")
    adapter = importlib.import_module(name).ADAPTER
    if (adapter.challenge_id, adapter.level) != (challenge_id, level):
        raise AdapterNotRegistered(f"{challenge_id}@level-{level}: identity mismatch")
    return adapter


def _register_builtins():
    """Register every built-in adapter in the core's registry, once."""
    if _core is None:
        return
    for key in BUILTIN:
        if key not in _core.ADAPTERS:
            _core.register(_module_adapter(*key))


def load(challenge_id, level):
    """The adapter for `challenge_id` at construction `level`."""
    if _core is not None and (challenge_id, level) in _core.ADAPTERS:
        return _core.ADAPTERS[(challenge_id, level)]
    return _module_adapter(challenge_id, level)


def registered():
    """`(challenge_id, level)` pairs with a built-in adapter, sorted."""
    return sorted(BUILTIN)


_register_builtins()
