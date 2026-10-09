"""Construction levels at the Launchpad's doors (LAUNCHPAD-LEVELS-01 S2, S3).

One table entry each for launch, practice, freeze, commit and submit
(`operations.OPERATIONS`), so the browser and MCP doors refuse and accept
alike. Every rule is the generic mechanism's
(`carbon.development_session.construction_level`); this module only turns
its refusals into the doors' `Rejected` and reads the target intake's public
facts. It names no Challenge and imports no variant module.

- **Launch** at `construction_level: N` (and `arm`) binds the level's current
  registered variant (`launch_binding`); level 0 binds nothing.
- **Practice and freeze** compile at the level first (`checked_strategy`,
  `checked_freeze`), so a refusal is answered at once by its closed code.
- **Submit and commit** refuse, before anything is signed, a binding no
  longer registered (`level_not_registered`) and a target whose
  `served_contracts` do not list it (`level_not_served_by_target`), and, for
  Level 4, every send while no intake carries the staging envelope
  (`level4_envelope_transport_unavailable`).
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.dev.miner_launchpad.controller import Rejected


def _cl():
    from carbon.development_session import construction_level

    return construction_level


def _rejected(refused, status=409):
    from scripts.dev.miner_launchpad.supervisor import next_action

    step = next_action(refused.code)
    detail = [
        i.get("code")
        for i in getattr(refused, "issues", ())
        if type(i) is dict and type(i.get("code")) is str
    ]
    if detail:
        step += " Reason: " + ", ".join(detail[:6]) + "."
    # A `Rejected` carrying its own next step (`runner.stepped`).
    error = Rejected(refused.code, status)
    error.next_step = step
    return error


def launch_binding(request, challenge, agent, cfg=None):
    """The level binding a launch names, or None for Level 0. Refused by
    closed code before the campaign is created. The binding carries the
    profile's intake for the Challenge (`target_intake`): the level's compile
    is spawned only while that target lists the variant's exact digest."""
    cl = _cl()
    level, arm = request.get("construction_level"), request.get("arm")
    if level is None and arm is None:
        return None
    if level is None:
        raise Rejected(cl.INVALID)
    try:
        found = cl.resolve(challenge["id"], level, arm)
    except cl.LevelRefused as refused:
        raise _rejected(refused) from None
    if found is None:
        return None
    if agent != "none":
        raise Rejected(cl.NEEDS_OWN_SELECTION, 409)
    from carbon.challenge_registry.campaigns import campaign_for

    if not campaign_for(challenge).construction_levels:
        raise Rejected(cl.NOT_OFFERED, 409)
    target = _intake_url(cfg, challenge["id"]) if cfg is not None else None
    return cl.with_target(found, target)


def campaign_binding(row, cfg=None):
    """An admitted campaign's level binding: its frozen manifest's, or,
    before the manifest is written, the one its launch record names."""
    cl = _cl()
    root = Path(row["root"])
    path = root / "campaign-manifest.json"
    if path.exists():
        return cl.binding(json.loads(path.read_bytes()))
    stored = row.get("launch_request") if hasattr(row, "get") else None
    if stored is None:
        return None
    try:
        recorded = json.loads(stored)
        challenge = recorded.get("challenge")
        level = recorded.get("construction_level")
    except (TypeError, ValueError, AttributeError):
        return None
    if level is None:
        return None
    try:
        found = cl.resolve(challenge, level, recorded.get("arm"))
    except cl.LevelRefused as refused:
        raise _rejected(refused) from None
    target = _intake_url(cfg, challenge) if cfg is not None else None
    return cl.with_target(found, target)


def checked_strategy(found, strategy):
    """`strategy`'s Level 0 base, after the level's compile admits it; the
    strategy itself at Level 0. What check-design is then asked about."""
    if found is None:
        return strategy
    cl = _cl()
    try:
        compiled = cl.compile_strategy(found, strategy)
    except cl.LevelRefused as refused:
        raise _rejected(refused) from None
    return cl.base_strategy(strategy, compiled["widened_fields"])


def checked_freeze(found, strategy, level4_directory):
    """Every level refusal the freeze would meet, before it is dispatched."""
    cl = _cl()
    try:
        cl.check_freeze(found, strategy, level4_directory)
    except cl.LevelRefused as refused:
        raise _rejected(refused) from None


def _intake_url(cfg, challenge_id):
    from scripts.dev.miner_launchpad.runner import intakes

    return intakes(cfg).get(challenge_id)


def read_facts(cfg, challenge, read=None):
    """The target intake's public facts for `challenge`, through its
    campaign's own check (chain and Challenge), or None with no intake."""
    url = _intake_url(cfg, challenge["id"])
    if url is None:
        return None
    if read is None:
        from carbon.challenge_registry.campaigns import campaign_for

        read = campaign_for(challenge).intake_check
        if read is None:
            return None
    return read(url)


def require_served(cfg, manifest, read=None):
    """Before anything is signed for a level campaign's commit or submit:
    `level_not_registered` when its frozen variant is no longer its level's
    current one, `level_not_served_by_target` when the target intake's
    `served_contracts` do not list it (while it publishes none, every level
    above 0), and `level4_envelope_transport_unavailable` for Level 4. A
    Level 0 campaign is not checked here."""
    cl = _cl()
    found = cl.binding(manifest)
    if found is None:
        return
    try:
        cl.still_registered(found)
    except cl.LevelRefused as refused:
        raise _rejected(refused) from None
    try:
        facts = read_facts(cfg, manifest["challenge"], read)
    except Exception:  # noqa: BLE001 - unread is never served (fail closed)
        raise Rejected("intake_unreachable", 503) from None
    if facts is None or not cl.lists(facts, found):
        raise _rejected(cl.LevelRefused(cl.NOT_SERVED))
    if found["level"] == cl.LEVEL4:
        raise _rejected(cl.LevelRefused(cl.LEVEL4_TRANSPORT_UNAVAILABLE))


def campaign_slot(found, base_slot):
    """The Contract view's `construction_level` for a level campaign: its
    level, variant and DEVELOPMENT label over the ladder's own slot."""
    if found is None:
        return base_slot
    return {
        **{k: v for k, v in base_slot.items() if k in ("ladder",)},
        "level": found["level"],
        "status": "DEFINED",
        "audience": "DEVELOPMENT",
        "arm": found.get("arm"),
        "variant": {"name": found["variant"], "digest": found["digest"]},
        "basis": (
            "Your campaign was launched at this construction level: its recipes "
            "compile under the level's registered development variant, frozen "
            "by digest, and practice trains the recipe's Level 0 base. It is "
            "DEVELOPMENT: only a validator whose served_contracts list the "
            "variant receives it."
        ),
    }
