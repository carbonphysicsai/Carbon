"""`carbon_challenges_v1__scoring_rules`: the agent can read a version's scoring
rules, machine-readable, from the one published block (owner, 2026-10-25: "make
sure the agent MCP can call the scoring rules and hypothesize with them").

One source: the tool cuts the block `describe` serves; the speed ceilings come
from one registered module that the grader's gate also reads. Nothing hidden
reaches the output."""

import asyncio
import json
import re
from pathlib import Path

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from carbon import challenge_registry as challenges
from carbon.challenge_registry import published_exam as pe
from carbon.challenge_registry import speed_gate
from carbon.miner_mcp import mcp_challenges
from carbon.miner_mcp.mcp_challenges import PREFIX, SCORING_RULES_SECTIONS

ROOT = Path(__file__).resolve().parents[2]
EVERYTHING = challenges.HostFacts(
    frozenset({"docker_cli", "trusted_worker_image", "jax", "optax"})
)
SERVED = pe.served()
WITHHELD = (
    "seed",
    "draw_id",
    "hidden_case",
    "private_metadata",
    "start point",
    "starting point",
    "custody",
    "pack_set",
    "extended region",
    "25 %",
)
NEW = ("f08-ribbed-bracket", "9.9")


def _server():
    from carbon.miner_mcp.open_tier import create_open_tier_server

    return create_open_tier_server(host_facts=lambda: EVERYTHING)


def _call(arguments):
    result = asyncio.run(_server().call_tool(PREFIX + "scoring_rules", arguments))
    assert not result.is_error
    return result.structured_content["payload"]


def test_the_tool_is_listed_and_read_only():
    tools = {t.name: t for t in asyncio.run(_server().list_tools())}
    tool = tools[PREFIX + "scoring_rules"]
    assert tool.annotations.read_only_hint is True


@pytest.mark.parametrize("key", SERVED)
def test_the_rules_are_the_published_block_cut_to_the_allow_list(key):
    rules = _call({"challenge_id": key[0], "version": key[1]})
    block = pe.for_version(*key)
    assert rules["schema"] == mcp_challenges.SCORING_RULES_SCHEMA
    assert (rules["challenge_id"], rules["version"]) == key
    assert rules["published_exam_schema"] == block["schema"]
    for section in SCORING_RULES_SECTIONS:
        if section in block:
            assert rules[section] == block[section], section
    assert set(rules) <= {
        "schema",
        "challenge_id",
        "version",
        "published_exam_schema",
        *SCORING_RULES_SECTIONS,
    }
    # The formula, the legs, the gates and the minimums are all there.
    assert rules["score"]["formula"] == "TOTAL = 0.5 * A + 0.5 * D"
    assert rules["gates"] and rules["minimums"]


def test_a_version_with_no_published_block_is_refused_with_a_next_step():
    with pytest.raises(ToolError) as refused:
        asyncio.run(
            _server().call_tool(
                PREFIX + "scoring_rules",
                {
                    "challenge_id": "battery-fastcharge-ageing-development-v1",
                    "version": "1.0",
                },
            )
        )
    assert "no_published_exam_for_version" in str(refused.value)
    assert "next_action=" in str(refused.value)


def test_an_unknown_version_is_refused_by_code():
    with pytest.raises(ToolError):
        asyncio.run(
            _server().call_tool(
                PREFIX + "scoring_rules",
                {"challenge_id": "no-such", "version": "0.0"},
            )
        )


def test_a_pool_graded_version_carries_the_speed_gate_and_the_search(monkeypatch):
    own = dict(pe._BY_VERSION[("f08-ribbed-bracket", "1.5")])
    own["score"] = pe.pool_score("accuracy")
    monkeypatch.setitem(pe._BY_VERSION, NEW, own)
    monkeypatch.setattr(pe, "_POOL_VERSIONS", frozenset({NEW}))
    described = {
        "challenge_id": NEW[0],
        "version": NEW[1],
        "published_exam": pe.for_version(*NEW),
    }
    rules = mcp_challenges.scoring_rules_view(described)
    assert rules["published_exam_schema"] == pe.SCHEMA_POOL
    gate = rules["speed_gate"]
    assert gate["ratio"] == speed_gate.RATIO == 500
    assert gate["ceiling_seconds_per_design"] == speed_gate.ceiling_seconds(NEW[0])
    assert gate["failure"] == "GATE_FAILED (speed)"
    assert rules["design_search"]["search"]["optimizer"].startswith("CMA-ES")
    assert [line["id"] for line in rules["how_you_are_tested"]][:3] == [
        "score",
        "inverse_design",
        "optimizer",
    ]
    # Owner constants that are not registered say so; none is invented.
    assert rules["design_search"]["search"]["query_budget"] == pe.NOT_REGISTERED
    text = json.dumps(rules).lower()
    for word in WITHHELD:
        assert word not in text, word


def test_the_ceilings_are_the_solver_time_over_500_from_one_module():
    for challenge_id, seconds in speed_gate.SOLVER_SECONDS_PER_DESIGN.items():
        assert speed_gate.ceiling_seconds(challenge_id) == round(seconds / 500, 2)
        assert pe._SPEED_CEILING_SECONDS[challenge_id] == speed_gate.ceiling_seconds(
            challenge_id
        )


def test_no_ceiling_number_is_written_anywhere_but_the_registered_module():
    numbers = [str(c) for c in speed_gate.ceilings().values()]
    pattern = re.compile(
        r"(?<![\d.])(" + "|".join(re.escape(n) for n in numbers) + r")\b"
    )
    offenders = []
    for path in sorted((ROOT / "carbon").rglob("*.py")):
        if path.name == "speed_gate.py":
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if pattern.search(line) and "second" in line.lower():
                offenders.append(f"{path.relative_to(ROOT)}:{number}")
    assert not offenders, offenders
