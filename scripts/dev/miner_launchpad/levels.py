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
  Level 4, a target whose public `tools` do not take the staging envelope's
  signed parts (`level4_envelope_transport_unavailable`, S4). Where they do,
  the campaign sends the envelope's parts, then the candidate.
"""

from __future__ import annotations

import json
from pathlib import Path

CONSTRUCTION_ADMISSION = "construction_admission"
CAPTURE_SCHEMA = "carbon.launchpad.construction-admission.v1"
SELECTED_CAPTURE_SCHEMA = "carbon.launchpad.construction-admission.v2"
# The only prospective standalone test subject. The variant registry still
# authenticates its document and current registration before it is bound.
STANDALONE_GRAPH_V3 = (
    "sha256:ad15d6a8ef135a961f15dcb4a682e58ccdbdc7c99926de0f1ef6d5da4325cfa2"
)

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


def binding(manifest):
    """A frozen manifest's level binding, or None for a Level 0 campaign."""
    return _cl().binding(manifest)


def _selected_standalone(request, challenge, agent, cfg, *, recorded_target=None):
    """Exact registered DEVELOPMENT subject; a level hint grants nothing."""
    cl = _cl()
    from carbon.challenge_registry.campaigns import campaign_for
    from carbon.reconstruction.capability_registry import development_variant_document

    if (
        type(request.get("construction_variant_digest")) is not str
        or request["construction_variant_digest"] != STANDALONE_GRAPH_V3
        or agent != "graphite"
        or request.get("arm") is not None
        or request.get("construction_level") not in (None, 4)
        or (
            "construction_level" in request
            and type(request["construction_level"]) not in (int, type(None))
        )
    ):
        raise Rejected("construction_variant_invalid", 409)
    try:
        subject = development_variant_document(STANDALONE_GRAPH_V3)
    except RuntimeError:
        raise Rejected("construction_variant_invalid", 409) from None
    if (
        type(subject) is not dict
        or subject.get("challenge") != challenge.get("id")
        or subject.get("level") != 4
        or not campaign_for(challenge).construction_levels
    ):
        raise Rejected("construction_variant_invalid", 409)
    try:
        found = cl.resolve(challenge["id"], 4)
    except cl.LevelRefused as refused:
        raise _rejected(refused) from None
    if found is None or found["digest"] != STANDALONE_GRAPH_V3:
        raise Rejected("construction_variant_invalid", 409)
    target = _intake_url(cfg, challenge["id"]) if cfg is not None else recorded_target
    return cl.with_target(found, target)


def launch_binding(request, challenge, agent, cfg=None, *, legacy=False):
    """The level binding a launch names, or None for Level 0. Refused by
    closed code before the campaign is created. The binding carries the
    profile's intake for the Challenge (`target_intake`): the level's compile
    is spawned only while that target lists the variant's exact digest."""
    cl = _cl()
    level, arm = request.get("construction_level"), request.get("arm")
    if "construction_variant_digest" in request:
        if legacy:
            raise Rejected("launch_record_differs", 409)
        return _selected_standalone(request, challenge, agent, cfg)
    if not legacy and arm is None:
        if level is not None and (type(level) is not int or level not in cl.LEVELS):
            raise Rejected(cl.INVALID)
        from carbon.challenge_registry.campaigns import campaign_for

        if campaign_for(challenge).construction_levels:
            try:
                found = cl.resolve_composition(challenge["id"])
            except cl.LevelRefused as refused:
                raise _rejected(refused) from None
            if found is not None:
                target = _intake_url(cfg, challenge["id"]) if cfg is not None else None
                return cl.with_target(found, target)
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


def capture_binding(found, selector=None):
    """Writer-owned data beside the request; never a permitted request field."""
    if selector is not None:
        return {
            "schema": SELECTED_CAPTURE_SCHEMA,
            "binding": found,
            "selector": selector,
        }
    return {"schema": CAPTURE_SCHEMA, "binding": found}


def checked_capture(row, captured):
    """Distinguish genuine pre-S3 records from missing new-writer capture."""
    from carbon.development_session.profile import canonical, digest

    version = row.get("construction_binding_version", 0)
    pinned = row.get("construction_binding_digest")
    if type(version) is not int or version not in (0, 1, 2):
        raise Rejected("launch_record_differs", 409)
    if version == 0:
        if captured is not None or pinned is not None:
            raise Rejected("launch_record_differs", 409)
        return None
    expected = (
        {"schema", "binding"} if version == 1 else {"schema", "binding", "selector"}
    )
    schema = CAPTURE_SCHEMA if version == 1 else SELECTED_CAPTURE_SCHEMA
    if (
        type(captured) is not dict
        or set(captured) != expected
        or captured["schema"] != schema
        or type(pinned) is not str
        or (captured["binding"] is not None and type(captured["binding"]) is not dict)
        or (
            version == 2
            and (type(captured["selector"]) is not str or captured["binding"] is None)
        )
    ):
        raise Rejected("launch_record_differs", 409)
    try:
        matches = digest(canonical(captured)) == pinned
    except (TypeError, ValueError, UnicodeError):
        matches = False
    if not matches:
        raise Rejected("launch_record_differs", 409)
    return captured


def replay_binding(request, challenge, agent, cfg, captured):
    """An exact admitted binding; historical records retain their old route."""
    cl = _cl()
    if captured is None:
        return launch_binding(request, challenge, agent, cfg, legacy=True)
    frozen = captured["binding"]
    if captured["schema"] == SELECTED_CAPTURE_SCHEMA:
        if request.get("construction_variant_digest") != captured["selector"]:
            raise Rejected("launch_record_differs", 409)
        try:
            expected = _selected_standalone(
                request,
                challenge,
                agent,
                cfg,
                recorded_target=(
                    frozen.get("target_intake") if type(frozen) is dict else None
                ),
            )
        except Rejected:
            raise Rejected("launch_record_differs", 409) from None
        if json.dumps(expected, sort_keys=True) != json.dumps(frozen, sort_keys=True):
            raise Rejected("launch_record_differs", 409)
        return expected
    if "construction_variant_digest" in request:
        raise Rejected("launch_record_differs", 409)
    if frozen is None:
        return None
    try:
        if (
            type(frozen.get("digest")) is not str
            or frozen.get("challenge") != challenge["id"]
        ):
            raise Rejected("launch_record_differs", 409)
        if frozen.get("kind") == cl.COMPOSITION:
            if request.get("arm") is not None:
                raise Rejected("launch_record_differs", 409)
            found = cl.resolve_composition(challenge["id"], frozen.get("digest"))
        else:
            found = cl.resolve(
                challenge["id"], request.get("construction_level"), request.get("arm")
            )
        target = (
            _intake_url(cfg, challenge["id"])
            if cfg is not None
            else frozen.get("target_intake")
        )
        expected = cl.with_target(found, target)
        if json.dumps(expected, sort_keys=True) != json.dumps(frozen, sort_keys=True):
            raise Rejected("launch_record_differs", 409)
        return expected
    except (cl.LevelRefused, KeyError, TypeError, ValueError):
        raise Rejected("launch_record_differs", 409) from None


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
        captured = checked_capture(row, recorded.get(CONSTRUCTION_ADMISSION))
        if captured is not None:
            return replay_binding(
                recorded,
                {"id": challenge, "version": recorded.get("challenge_version")},
                recorded.get("agent"),
                cfg,
                captured,
            )
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


def require_served(cfg, manifest, read=None, *, record=None):
    """Before anything is signed for a level campaign's commit or submit:
    `level_not_registered` when its frozen variant is no longer its level's
    current one, `level_not_served_by_target` when the target intake's
    `served_contracts` do not list it (while it publishes none, every level
    above 0), and `level4_envelope_transport_unavailable` for Level 4 when
    the target lists no envelope part tools (fail closed; where it lists
    them the campaign sends the envelope in signed parts first). A Level 0
    campaign is not checked here."""
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
    graph = found["level"] == cl.LEVEL4
    if found.get("kind") == cl.COMPOSITION:
        if record is None:
            raise Rejected("freeze_a_candidate_first", 409)
        frozen = record.get("construction_level")
        if (
            record.get("contract_digest") != found["digest"]
            or type(frozen) is not dict
            or frozen.get("digest") != found["digest"]
            or frozen.get("kind") != cl.COMPOSITION
        ):
            raise _rejected(cl.LevelRefused(cl.NOT_REGISTERED))
        try:
            cl.checks_current(found, record["strategy"])
        except cl.LevelRefused as refused:
            raise _rejected(refused) from None
        parameters = (record.get("strategy") or {}).get("parameters")
        if type(parameters) is not dict:
            raise _rejected(cl.LevelRefused("level_strategy_refused"))
        graph = "composition_graphs" in parameters
    if graph and not _takes_level4_parts(manifest["challenge"], facts):
        raise _rejected(cl.LevelRefused(cl.LEVEL4_TRANSPORT_UNAVAILABLE))


def _takes_level4_parts(challenge, facts):
    """Whether the target intake takes Level 4 envelope parts, read through
    the Challenge's campaign (`ChallengeCampaign.level4_parts`) so this door
    names no Challenge. A Challenge without that transport, or one that does
    not resolve, takes none (fail closed)."""
    from carbon.challenge_registry.campaigns import campaign_for_id

    try:
        carries = campaign_for_id(challenge["id"]).level4_parts
    except Exception:  # noqa: BLE001 - unresolved is never carried (fail closed)
        return False
    return carries is not None and bool(carries(facts))


def campaign_slot(found, base_slot):
    """The Contract view's `construction_level` for a level campaign: its
    level, variant and DEVELOPMENT label over the ladder's own slot."""
    if found is None:
        return base_slot
    if found.get("kind") == _cl().COMPOSITION:
        return {
            "kind": _cl().COMPOSITION,
            "level": None,
            "status": "DEFINED",
            "audience": "DEVELOPMENT",
            "variant": {"name": found["variant"], "digest": found["digest"]},
            "basis": "Your recipes use this registered construction contract. Carbon describes each recipe's changes when it compiles it. Practice trains the base recipe; the validator rebuilds the full construction. The receiving validator must explicitly list this contract.",
            **{k: v for k, v in base_slot.items() if k == "ladder"},
        }
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
