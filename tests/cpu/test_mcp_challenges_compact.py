"""`carbon_challenges_v1__describe` with compact=true (M1 E2E H19, part 3).

The full description was too large for the Hermes agent. compact=true returns
only what building a recipe needs, projected from the same public description;
the default answer stays the full one, unchanged.
"""

import asyncio
import json

import pytest

from carbon import challenge_registry as challenges
from carbon.miner_mcp import mcp_challenges
from carbon.miner_mcp.mcp_challenges import (
    COMPACT_SCHEMA,
    PREFIX,
    compact_description,
)

EVERYTHING = challenges.HostFacts(
    frozenset({"docker_cli", "trusted_worker_image", "jax", "optax"})
)
KEYS = {
    "schema",
    "challenge_id",
    "version",
    "title",
    "status",
    "interface",
    "backbones",
    "catalog_ids",
    "ready_recipe_kind",
    "ready_recipe",
    "source_kinds",
    "refusal_hints",
    "full_answer",
}
#: compact fits one small agent turn and is well under half the full answer,
#: for every version (measured 2026-10-22: 2.0-4.0 KB against 8.5-31 KB full,
#: ratios 0.07-0.37; Motor's catalog has since grown to 32 entries, 4.3 KB).
MAX_COMPACT_BYTES = 6144
MAX_RATIO = 0.4


def _describable():
    """Every registered (id, version) describe serves: from the registry,
    never a Challenge list written here."""
    served = []
    for entry in challenges.catalog(EVERYTHING)["challenges"]:
        try:
            challenges.describe(
                entry["challenge_id"], entry["version"], host=EVERYTHING
            )
        except challenges.ResolutionError:
            continue
        served.append((entry["challenge_id"], entry["version"]))
    return served


SERVED = _describable()


def _server():
    from carbon.miner_mcp.open_tier import create_open_tier_server

    return create_open_tier_server(host_facts=lambda: EVERYTHING)


def _call(server, arguments):
    result = asyncio.run(server.call_tool(PREFIX + "describe", arguments))
    assert not result.is_error
    return result.structured_content["payload"]


def test_every_launch_family_is_served():
    # The five launch families each have a describable version.
    ids = {challenge_id for challenge_id, _ in SERVED}
    assert len(ids) >= 5


@pytest.mark.parametrize(("challenge_id", "version"), SERVED)
def test_compact_is_a_small_projection_of_the_full_answer(
    challenge_id, version, tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    server = _server()
    full = _call(server, {"challenge_id": challenge_id, "version": version})
    compact = _call(
        server, {"challenge_id": challenge_id, "version": version, "compact": True}
    )
    full_bytes = len(json.dumps(full, sort_keys=True))
    compact_bytes = len(json.dumps(compact, sort_keys=True))
    ratio = compact_bytes / full_bytes
    print(f"{challenge_id}@{version}: full {full_bytes} compact {compact_bytes}")
    assert compact_bytes <= MAX_COMPACT_BYTES, (challenge_id, version, compact_bytes)
    assert ratio <= MAX_RATIO, (challenge_id, version, ratio)

    assert KEYS <= set(compact)
    assert compact["schema"] == COMPACT_SCHEMA
    assert (compact["challenge_id"], compact["version"]) == (challenge_id, version)
    reasons = compact.get("reasons", {})
    # An item the version lacks is null with its reason, never dropped.
    for key in ("backbones", "catalog_ids", "ready_recipe", "source_kinds"):
        assert compact[key] is not None or reasons.get(key), key

    # Interface names are the full answer's own.
    names = full["interface"]
    for side in ("inputs", "outputs"):
        assert compact["interface"][side] == list(names[side])

    # The ready recipe is the full answer's first ready example, byte for
    # byte: an unfilled graph template (graph route v2) is not one.
    ready = [
        next(iter(example.items()))
        for example in full["examples"]
        if not mcp_challenges._template(*next(iter(example.items())))
    ]
    if not ready:
        # No ready example: a graph template's reason names the digest to
        # fill; a version publishing none (Battery 2.2 until an entry is
        # receipted) says so.
        assert compact["ready_recipe"] is None
        assert ("submission_digest" in reasons["ready_recipe"]) == bool(
            full.get("examples")
        )
        return
    kind, document = ready[0]
    assert compact["ready_recipe_kind"] == kind
    assert compact["ready_recipe"] == document
    catalog = full["models"].get("catalog")
    if catalog is not None:
        assert compact["catalog_ids"] == sorted(catalog["entries"])
        assert document["source"]["catalog_id"] in compact["catalog_ids"]
        assert document["source"]["kind"] in compact["source_kinds"]
    else:
        assert compact["catalog_ids"] is None

    # Every hint is a registered code with registered text.
    assert compact["refusal_hints"]
    for hint in compact["refusal_hints"]:
        assert hint["codes"] and all(isinstance(c, str) for c in hint["codes"])
        assert isinstance(hint["fix"], str) and hint["fix"]

    # Nothing beyond the public full answer: the projection reads only it, and
    # the hidden-material words the registry tests forbid stay absent.
    assert compact_description(full) == compact
    text = json.dumps(compact).lower()
    for word in ("seed_root", "hidden_case", "private_metadata", "draw_id"):
        assert word not in text


@pytest.mark.parametrize(("challenge_id", "version"), SERVED)
def test_the_ready_recipe_binds(challenge_id, version):
    from carbon.development_session.research_service import (
        construction_recipe_issues,
    )
    from carbon.registry import ChallengeKey

    compact = compact_description(
        challenges.describe(challenge_id, version, host=EVERYTHING)
    )
    if compact["ready_recipe"] is None:
        # No ready example yet (graph template only, or none): stated, not
        # silently absent.
        assert compact["reasons"]["ready_recipe"]
        return
    if compact["ready_recipe_kind"] != "recipe":
        pytest.skip("a Level 0 strategy version; admitted by examples_admission")
    key = ChallengeKey(challenge_id, version)
    assert construction_recipe_issues(compact["ready_recipe"], key) == ()


def test_hints_are_the_registered_texts():
    from carbon.construction.compiler import _ISSUE_MESSAGES
    from carbon.development_session.research_service import (
        _RECIPE_ISSUE_PATH,
        RECIPE_ISSUE_DEFAULT,
        RECIPE_ISSUE_TEXT,
    )
    from carbon.development_session.research_tools import TASK_CORRECTIONS

    registered = {
        **{c: t for c, t in TASK_CORRECTIONS.items()},
        **{
            c: RECIPE_ISSUE_TEXT.get(c, RECIPE_ISSUE_DEFAULT)
            for c in _RECIPE_ISSUE_PATH
        },
        "construction_recipe_malformed": RECIPE_ISSUE_DEFAULT,
        **_ISSUE_MESSAGES,
    }
    for challenge_id, version in SERVED:
        compact = compact_description(
            challenges.describe(challenge_id, version, host=EVERYTHING)
        )
        for hint in compact["refusal_hints"]:
            for code in hint["codes"]:
                assert registered[code] == hint["fix"], code


def test_the_default_answer_is_unchanged(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = _server()
    for challenge_id, version in SERVED:
        direct = challenges.describe(challenge_id, version, host=EVERYTHING)
        omitted = _call(server, {"challenge_id": challenge_id, "version": version})
        false = _call(
            server,
            {"challenge_id": challenge_id, "version": version, "compact": False},
        )
        assert json.dumps(omitted, sort_keys=True) == json.dumps(direct, sort_keys=True)
        assert false == omitted


def test_the_schema_offers_compact_as_optional():
    from carbon.miner_mcp.mcp_challenges import make_challenge_tools

    (tool,) = [t for t in make_challenge_tools() if t.name == PREFIX + "describe"]
    schema = tool.parameters
    assert schema["properties"]["compact"]["default"] is False
    assert "compact" not in schema.get("required", [])
    assert "compact" in tool.description
