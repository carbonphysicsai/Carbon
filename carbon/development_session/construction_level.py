"""A campaign's construction level: bound at launch, compiled, frozen, served.

LAUNCHPAD-LEVELS-01 S2 and S3 (OWNER-LADDER-THROUGH-LAUNCHPAD-01). One
generic mechanism for every Challenge with registered development variants;
no level and no Challenge has code of its own here.

- **The binding.** A launch at level N >= 1 (and an optional `arm`) binds the
  level's current registered variant, read from the variant registry as data
  (`capability_registry.development_variant_registry`, each document checked
  against its pinned digest). The campaign manifest freezes it under
  `construction_level`: `{level, arm, variant, digest, scope}`. Level 0 binds
  nothing: the campaign is what it was.
- **The compile.** A level campaign's recipes compile with
  `development_variants.compile_development`, in a child process
  (`carbon.reconstruction.development_level_cli`): no miner surface imports
  the variant module. Practice then trains the recipe's Level 0 base (the
  recipe less the fields the variant widens), and its result says so
  (`practice_label`): the widened values are checked against the variant's
  bounds and reconstructed by Carbon, never trained in practice.
- **The freeze.** The frozen record's `contract_digest` is the variant's
  digest. The commitment digest is `{challenge, contract_digest,
  strategy_hash}` (`daemon.commitment_digest`), so it binds the level with no
  schema change.
- **The target.** A level's recipe is sent only to an intake whose public
  facts list its variant in `served_contracts` (`{level, variant, digest}`),
  matched by registry version name and confirmed by digest. While the field
  is absent, every level above 0 is refused `level_not_served_by_target`.

Every refusal is a `LevelRefused` with a closed code.
"""

from __future__ import annotations

import functools
import json
import subprocess
import sys
from pathlib import Path

MANIFEST_KEY = "construction_level"
SCOPE = "DEVELOPMENT"
#: The levels a launch may name (the ladder's 0-5); 0 binds nothing.
LEVELS = range(6)
LEVEL4 = 4
CLI_MODULE = "carbon.reconstruction.development_level_cli"
#: How long the child process may take (it imports the numerical stack).
CLI_TIMEOUT_SECONDS = 600

NOT_REGISTERED = "level_not_registered"
NOT_SERVED = "level_not_served_by_target"
INVALID = "construction_level_invalid"
ARM_INVALID = "construction_level_arm_invalid"
NEEDS_OWN_SELECTION = "construction_level_needs_own_selection"
NOT_OFFERED = "construction_level_not_offered_for_challenge"
COMPILE_UNAVAILABLE = "level_compile_unavailable"
LEVEL4_DIRECTORY_REQUIRED = "level4_directory_required"
LEVEL4_DIRECTORY_NOT_FOR_LEVEL = "level4_directory_needs_level4"
LEVEL4_TRANSPORT_UNAVAILABLE = "level4_envelope_transport_unavailable"
#: Where a Level 4 candidate's staging envelope is kept, beside its frozen
#: record, exactly as `staging.envelope` answered it.
LEVEL4_ENVELOPE = "level4-envelope.json"
PRACTICE_NOTE = (
    "Practice at a construction level trains the recipe's Level 0 base: the "
    "level's widened values are checked against its registered variant and "
    "reconstructed by Carbon, not trained in practice. Only the validator's "
    "rebuild runs the level."
)


class LevelRefused(ValueError):
    """A construction-level choice or use refused; `code` is closed."""

    def __init__(self, code, issues=()):
        super().__init__(code)
        self.code, self.issues = code, list(issues)


# ---- The binding, from registry data.


def _document_digest(document):
    from carbon.reconstruction import expansion_record

    return expansion_record.digest_of(document)


def resolve(challenge, level, arm=None, *, directory=None):
    """The binding for a launch at `level` (and `arm`): the level's current
    registered variant, its document checked against its pinned digest. None
    for level 0. `LevelRefused(level_not_registered)` when no current variant
    is registered for it."""
    from carbon.reconstruction.capability_registry import (
        DEVELOPMENT_VARIANT_DIR,
        development_variant_registry,
    )

    if type(level) is not int or type(level) is bool or level not in LEVELS:
        raise LevelRefused(INVALID)
    if arm is not None and (type(arm) is not str or not arm or len(arm) > 32):
        raise LevelRefused(ARM_INVALID)
    if level == 0:
        if arm is not None:
            raise LevelRefused(NOT_REGISTERED)
        return None
    folder = Path(DEVELOPMENT_VARIANT_DIR if directory is None else directory)
    try:
        registry = development_variant_registry(folder)
    except RuntimeError:
        raise LevelRefused(NOT_REGISTERED) from None
    found = [
        entry
        for entry in registry["current"]
        if entry["challenge"] == challenge
        and entry["level"] == level
        and entry.get("arm") == arm
    ]
    if len(found) != 1:
        raise LevelRefused(NOT_REGISTERED)
    name = found[0]["version"]
    pinned = registry["versions"][name]
    try:
        document = json.loads((folder / f"{name}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise LevelRefused(NOT_REGISTERED) from None
    if (
        _document_digest(document) != pinned
        or document.get("level") != level
        or document.get("challenge") != challenge
    ):
        raise LevelRefused(NOT_REGISTERED)
    return {
        "level": level,
        "arm": arm,
        "variant": name,
        "digest": pinned,
        "scope": SCOPE,
        "challenge": challenge,
    }


def binding(manifest):
    """A frozen manifest's level binding, or None for a Level 0 campaign."""
    found = (manifest or {}).get(MANIFEST_KEY) if type(manifest) is dict else None
    return found if type(found) is dict else None


def still_registered(found, *, directory=None):
    """`level_not_registered` unless the frozen binding is still its level's
    current registered variant, by name and digest."""
    current = resolve(
        found["challenge"], found["level"], found.get("arm"), directory=directory
    )
    if (current["variant"], current["digest"]) != (found["variant"], found["digest"]):
        raise LevelRefused(NOT_REGISTERED)
    return current


# ---- The target's public facts.


def served_contracts(facts):
    """The intake's `served_contracts`, or None while it publishes none."""
    found = facts.get("served_contracts") if type(facts) is dict else None
    return found if type(found) is list else None


def lists(facts, found):
    """Whether the intake's facts list this binding's variant: the entry for
    its level names its registry version, and its digest is the binding's."""
    for entry in served_contracts(facts) or ():
        if (
            type(entry) is dict
            and entry.get("level") == found["level"]
            and entry.get("variant") == found["variant"]
            and entry.get("digest") == found["digest"]
        ):
            return True
    return False


def lists_digest(facts, digest):
    """Whether the intake's facts list `digest` among the variants it serves
    above level 0 (the send path's check, by the frozen record's digest)."""
    for entry in served_contracts(facts) or ():
        if (
            type(entry) is dict
            and type(entry.get("level")) is int
            and entry["level"] >= 1
            and type(entry.get("variant")) is str
            and entry.get("digest") == digest
        ):
            return True
    return False


def check_served(facts, found):
    """`level_not_served_by_target` unless the target lists the binding."""
    if found is not None and not lists(facts, found):
        raise LevelRefused(NOT_SERVED)


def deployment_level(facts):
    """The target's own level: the lowest it lists, or None while it lists
    none. Every level above it is DEVELOPMENT."""
    levels = [
        entry["level"]
        for entry in served_contracts(facts) or ()
        if type(entry) is dict
        and type(entry.get("level")) is int
        and type(entry.get("level")) is not bool
    ]
    return min(levels) if levels else None


# ---- The compile, in its own process.


def _run(request):
    """One answer from the development door's level CLI, or
    `level_compile_unavailable` when it could not answer."""
    try:
        done = subprocess.run(
            [sys.executable, "-m", CLI_MODULE],
            input=json.dumps(request, sort_keys=True),
            capture_output=True,
            text=True,
            timeout=CLI_TIMEOUT_SECONDS,
            check=False,
            cwd=str(Path(__file__).resolve().parents[2]),
        )
        lines = [line for line in done.stdout.splitlines() if line.strip()]
        value = json.loads(lines[-1]) if lines else None
    except (OSError, subprocess.SubprocessError, ValueError):
        value = None
    return checked(value)


def checked(value):
    """The level CLI's answer, or its refusal raised as `LevelRefused`."""
    if type(value) is not dict or type(value.get("ok")) is not bool:
        raise LevelRefused(COMPILE_UNAVAILABLE)
    if not value["ok"]:
        code = value.get("code")
        raise LevelRefused(
            code if type(code) is str else COMPILE_UNAVAILABLE,
            value.get("issues") or (),
        )
    return value


#: The child-process call; tests substitute a fixture.
RUN = _run


@functools.lru_cache(maxsize=64)
def _compiled(key):
    request = json.loads(key)
    return json.dumps(RUN(request), sort_keys=True)


def compile_strategy(found, strategy):
    """The level's compile of `strategy` (`compile_development`, in its own
    process), checked to be the frozen binding's variant."""
    if type(strategy) is not dict:
        raise LevelRefused("level_strategy_refused")
    key = json.dumps(
        {
            "op": "compile",
            "challenge": found["challenge"],
            "level": found["level"],
            "arm": found.get("arm"),
            "strategy": strategy,
        },
        sort_keys=True,
    )
    value = json.loads(_compiled(key))
    if (value.get("variant"), value.get("variant_digest")) != (
        found["variant"],
        found["digest"],
    ):
        raise LevelRefused(NOT_REGISTERED)
    return value


def base_strategy(strategy, widened_fields):
    """The recipe less the fields its level widens: its Level 0 base."""
    parameters = strategy.get("parameters")
    if type(parameters) is not dict:
        return dict(strategy)
    return {
        **strategy,
        "parameters": {
            k: v for k, v in parameters.items() if k not in set(widened_fields)
        },
    }


def level_compiler(found, base_compiler):
    """A recipe compiler for a level campaign: the level's compile first,
    then `base_compiler` over the recipe's Level 0 base. A level refusal is
    raised as `LevelRefused`."""

    def compile_at_level(strategy):
        value = compile_strategy(found, strategy)
        return base_compiler(base_strategy(strategy, value["widened_fields"]))

    compile_at_level.construction_level = dict(found)
    return compile_at_level


def practice_label(found):
    """What a practice result at a level carries beside its score."""
    return {
        "level": found["level"],
        "arm": found.get("arm"),
        "variant": found["variant"],
        "digest": found["digest"],
        "scope": SCOPE,
        "widened_trained": False,
        "note": PRACTICE_NOTE,
    }


# ---- The freeze and the commitment.


def level4_check(found, strategy, directory):
    """A Level 4 submission lowered on the miner's machine, checked against
    the frozen Level 4 variant before freeze; answers its staging envelope."""
    if found["level"] != LEVEL4:
        raise LevelRefused(LEVEL4_DIRECTORY_NOT_FOR_LEVEL)
    if type(directory) is not str or not directory:
        raise LevelRefused(LEVEL4_DIRECTORY_REQUIRED)
    value = RUN(
        {
            "op": "level4",
            "challenge": found["challenge"],
            "level": found["level"],
            "arm": found.get("arm"),
            "strategy": strategy,
            "directory": directory,
        }
    )
    if value.get("variant_digest") != found["digest"]:
        raise LevelRefused(NOT_REGISTERED)
    return value["envelope"]


def check_freeze(found, strategy, level4_directory=None):
    """Every level refusal a freeze of `strategy` would meet, before anything
    is written: the level's compile, and for Level 4 its lowered submission.
    Answers `(compiled, envelope or None)`."""
    if found is None:
        if level4_directory is not None:
            raise LevelRefused(LEVEL4_DIRECTORY_NOT_FOR_LEVEL)
        return None, None
    value = compile_strategy(found, strategy)
    envelope = None
    if found["level"] == LEVEL4 or level4_directory is not None:
        envelope = level4_check(found, strategy, level4_directory)
    return value, envelope


def candidate_record(found, strategy, reason, used_feedback, compiled):
    """The frozen-candidate record at a level, in the shape
    `research_loop.candidate_record` writes: the variant's digest as its
    `contract_digest`, and the level binding beside it."""
    if type(reason) is not str or not 1 <= len(reason) <= 4096:
        raise ValueError("a bounded selection reason is required")
    if type(used_feedback) is not bool:
        raise ValueError("used_feedback is a Boolean")
    return {
        "status": "SELECTED",
        "strategy": strategy,
        "reason": reason,
        "used_feedback": used_feedback,
        "strategy_hash": compiled["strategy_hash"],
        "construction_plan_digest": compiled["construction_plan_digest"],
        "reconstruction_profile_digest": compiled["recipe_digest"],
        "contract_digest": found["digest"],
        MANIFEST_KEY: {**practice_label(found), "development": compiled["development"]},
        "final_evidence": False,
    }


def commitment_fields(record):
    """What a level candidate commits, `(challenge, contract_digest,
    strategy_hash)`: its Challenge, the variant's digest it was frozen under,
    and the strategy hash the level's compile gives it (recomputed, never
    read back from the record). The Challenge's own commitment function
    digests them."""
    frozen = record[MANIFEST_KEY]
    strategy = record["strategy"]
    found = {
        "challenge": strategy["challenge_id"],
        "level": frozen["level"],
        "arm": frozen.get("arm"),
        "variant": frozen["variant"],
        "digest": record["contract_digest"],
    }
    if frozen["digest"] != record["contract_digest"]:
        raise ValueError("the frozen level binding differs from its record")
    value = compile_strategy(found, strategy)
    return (
        strategy["challenge_id"],
        record["contract_digest"],
        value["commitment_strategy_hash"],
    )


def write_envelope(folder, envelope):
    """Keep a Level 4 candidate's envelope beside its frozen record: the
    JSON `staging.envelope` answered, written once (the same bytes again are
    accepted, so a retried freeze is not refused); the submission's bytes are
    base64 as read from the miner's directory and never re-serialized."""
    from carbon.development_session.data import write_once
    from carbon.development_session.profile import canonical

    path = Path(folder) / LEVEL4_ENVELOPE
    body = canonical(envelope)
    if path.exists() and path.read_bytes() == body:
        return
    write_once(path, body)


def read_envelope(folder, record):
    """The frozen Level 4 envelope, checked (`staging.from_envelope`) to be
    the submission the record's strategy names. Answers it unchanged."""
    from carbon.level4 import graph, staging

    path = Path(folder) / LEVEL4_ENVELOPE
    if not path.exists():
        raise LevelRefused(LEVEL4_DIRECTORY_REQUIRED)
    envelope = json.loads(path.read_bytes())
    try:
        digest, _raw, _files = staging.from_envelope(envelope)
    except graph.GraphRefused as refused:
        raise LevelRefused(
            "level4_submission_refused", [{"code": refused.code}]
        ) from None
    parameters = record["strategy"].get("parameters") or {}
    if digest not in parameters.values():
        raise LevelRefused("level4_submission_not_in_strategy")
    return envelope
