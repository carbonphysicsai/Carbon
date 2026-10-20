"""GRAPHITE-L4-STAGING-01 (R1), slice 2: the Level 4 stage tool.

Claims tested:
- only a Level 4 session's Constructor offers `graphite_level4_stage`; every
  other role and brief, and its manifest digest, is unchanged;
- Carbon reads the agent's one export through the miner door's `read_file`,
  in chunks, under a byte bound, and passes a refusal through unchanged;
- the stage admits an envelope as data through G0, G3 and G4 and keeps it by
  its submission digest; an envelope over the bound, malformed, or outside
  Level 4 is refused, typed, and nothing is kept;
- the tool's empty `task_id` returns the interface and the two commands.
"""

from __future__ import annotations

import asyncio
import base64
import gzip
import json
import types

import pytest

from carbon.agent_campaign.graphite import experiment as ex
from carbon.agent_campaign.graphite import miner_path, phase3
from carbon.agent_campaign.graphite.roles import (
    LEVEL4_STAGE,
    ROLES,
    TOOL_TEXT_V2,
    RoleName,
    study_role,
)
from carbon.development_session.research_tools import PREFIX


def test_only_a_level4_constructor_offers_the_stage_tool():
    plain = ROLES[RoleName.CONSTRUCTOR]
    staged = study_role(RoleName.CONSTRUCTOR, level4_stage=True)
    assert LEVEL4_STAGE not in plain.tools and LEVEL4_STAGE in staged.tools
    assert staged.manifest_digest(TOOL_TEXT_V2) != plain.manifest_digest(TOOL_TEXT_V2)
    assert study_role(RoleName.CONSTRUCTOR) is plain
    for name in RoleName:
        if name is not RoleName.CONSTRUCTOR:
            with pytest.raises(ValueError):
                study_role(name, level4_stage=True)
    with pytest.raises(ValueError):
        study_role(RoleName.CONSTRUCTOR, "SUBMISSION-RATE-STUDY-01", True)


class Door:
    """The miner door's `read_file` answers, from one workspace file."""

    def __init__(self, files, refuse=None):
        self.files, self.refuse, self.calls = files, refuse, []

    async def call(self, name, arguments, identity):
        self.calls.append((name, arguments, identity))
        if self.refuse is not None:
            return self.refuse
        args = json.loads(arguments["arguments_json"])
        body = self.files[args["name"]]
        chunk = body[args["offset"] : args["offset"] + args["count"]]
        return {
            "task": {"state": "SUCCEEDED"},
            "result": {
                "name": args["name"],
                "bytes": len(body),
                "offset": args["offset"],
                "content_utf8": None,
                "content_base64": base64.b64encode(chunk).decode(),
            },
        }


TASK = "rtsk_" + "a" * 64


def test_the_export_is_read_through_the_door_in_chunks_under_a_bound():
    body = bytes(range(256)) * 100  # 25,600 bytes: seven reads at the 4096-byte chunk
    door = Door({TASK[-20:] + "-" + ex.LEVEL4_ENVELOPE_EXPORT: body})
    got = asyncio.run(
        miner_path.read_export(
            door, TASK, ex.LEVEL4_ENVELOPE_EXPORT, "turn-3", max_bytes=1 << 20
        )
    )
    assert got == body and len(door.calls) == -(-len(body) // miner_path.READ_CHUNK)
    name, arguments, identity = door.calls[0]
    assert name == PREFIX + "start_research_task"
    assert arguments["kind"] == "workspace" and arguments["action"] == "read_file"
    assert identity == "turn-3-l4read-0"
    over = asyncio.run(
        miner_path.read_export(
            door, TASK, ex.LEVEL4_ENVELOPE_EXPORT, "turn-3", max_bytes=1000
        )
    )
    assert over["reason_code"] == "level4_envelope_over_bound"
    refusal = {
        "status": "REJECTED_BEFORE_DISPATCH",
        "reason_code": "workspace_file_missing",
    }
    passed = asyncio.run(
        miner_path.read_export(
            Door({}, refuse=refusal), TASK, ex.LEVEL4_ENVELOPE_EXPORT, "t", max_bytes=10
        )
    )
    assert passed == refusal
    short = asyncio.run(miner_path.read_export(door, "x", "y", "t", max_bytes=10))
    assert short["reason_code"] == "level4_task_id_required"


class CheckedDoor(Door):
    """The miner door's `read_file`, with the door's own request check run on every read (the same
    `check_workspace_request` the live door runs), under the research tools rule a campaign froze.
    """

    def __init__(self, files, ledger=None):
        super().__init__(files)
        self.executor = types.SimpleNamespace(ledger=ledger)

    async def call(self, name, arguments, identity):
        from carbon.development_session.research_tasks import (
            WorkspaceRequestRefused,
            check_workspace_request,
        )

        args = json.loads(arguments["arguments_json"])
        try:
            check_workspace_request(
                self.executor, arguments["action"], args, state=False
            )
        except WorkspaceRequestRefused as refused:
            return {
                "status": "REJECTED_BEFORE_DISPATCH",
                "reason_code": refused.code,
                "field": refused.field,
            }
        return await super().call(name, arguments, identity)


def test_every_read_passes_the_doors_own_request_check_under_every_frozen_rule():
    """Lane G (2026-10-12): the chunk was 8192 and a campaign on the v1 tools rule (limit 4096) refused every read with
    `read_file_range` on `arguments_json.count`, so no Level 4 submission was ever staged.
    """
    from carbon.development_session.research_tasks import READ_FILE_MAX_BYTES

    assert miner_path.READ_CHUNK <= min(READ_FILE_MAX_BYTES.values())
    body = bytes(range(256)) * 100
    door = CheckedDoor({TASK[-20:] + "-" + ex.LEVEL4_ENVELOPE_EXPORT: body})
    got = asyncio.run(
        miner_path.read_export(
            door, TASK, ex.LEVEL4_ENVELOPE_EXPORT, "turn-4", max_bytes=1 << 20
        )
    )
    assert got == body
    assert all(json.loads(c[1]["arguments_json"])["count"] <= 4096 for c in door.calls)


def test_a_chunk_above_the_frozen_limit_is_what_the_door_refused(monkeypatch):
    monkeypatch.setattr(miner_path, "READ_CHUNK", 8192)
    door = CheckedDoor({TASK[-20:] + "-" + ex.LEVEL4_ENVELOPE_EXPORT: b"x" * 9000})
    got = asyncio.run(
        miner_path.read_export(
            door, TASK, ex.LEVEL4_ENVELOPE_EXPORT, "turn-5", max_bytes=1 << 20
        )
    )
    assert got["reason_code"] == "read_file_range"
    assert got["field"] == "arguments_json.count"


# -- the stage, as data ---------------------------------------------------------------------
jax = pytest.importorskip("jax")


@pytest.fixture(scope="module")
def lowered():
    from carbon.battery import level4 as battery
    from carbon.battery import level4_lowering as battery_lowering
    from carbon.level4 import allowlist as allowlist_module
    from carbon.level4 import intake, staging, submission

    strategy = battery.level0_strategies()["scaffold_mlp"]
    manifest, files = battery_lowering.lower_recipe(
        strategy, allowlist_module.load(), max_bytes=intake.BOUNDS["document_bytes"]
    )
    envelope = staging.envelope(submission.canonical(manifest), files)
    packed = gzip.compress(json.dumps(envelope).encode(), mtime=0)
    return json.loads(json.dumps(strategy)), envelope["submission"], packed


def _experiment(tmp_path, *, level=4, limit=None):
    from carbon.reconstruction import development_variants as dv

    variant = dv.variant("battery-fastcharge-ageing-development-v1", 4)
    holder = types.SimpleNamespace(root=tmp_path, development_variant=variant)
    holder.level4_variant_bounds = lambda: (
        json.loads(variant.widened[0].bounds_json) if level == 4 else None
    )
    holder.level4_envelope_limit = lambda: (
        limit if limit is not None else ex.Experiment.level4_envelope_limit(holder)
    )
    return holder


def test_an_admitted_envelope_is_kept_by_its_submission_digest(tmp_path, lowered):
    strategy, digest, packed = lowered
    holder = _experiment(tmp_path)
    reply = ex.Experiment.level4_stage(holder, strategy, packed)
    assert reply["status"] == "LEVEL4_STAGED" and reply["submission"] == digest
    assert reply["gates"] == ["G0", "G3", "G4"] and reply["authority_granted"] is False
    kept = ex.Experiment.level4_staged(holder, digest)
    assert json.loads(kept)["submission"] == digest
    assert (tmp_path / "level4").stat().st_mode & 0o077 == 0


def test_over_bound_malformed_or_off_level_envelopes_are_refused(tmp_path, lowered):
    strategy, digest, packed = lowered
    small = ex.Experiment.level4_stage(
        _experiment(tmp_path, limit=100), strategy, packed
    )
    assert small["reason_code"] == "level4_envelope_over_bound"
    bad = ex.Experiment.level4_stage(_experiment(tmp_path), strategy, b"not gzip")
    assert bad["reason_code"] == "level4_envelope_malformed"
    off = ex.Experiment.level4_stage(_experiment(tmp_path, level=3), strategy, packed)
    assert off["reason_code"] == "level4_stage_not_at_level_4"
    assert ex.Experiment.level4_staged(_experiment(tmp_path), digest) is None


def test_the_tool_returns_the_interface_and_refuses_malformed_arguments(
    tmp_path, lowered
):
    strategy, _digest, _packed = lowered
    holder = _experiment(tmp_path)
    holder.level4_interface = lambda s: ex.Experiment.level4_interface(holder, s)
    tools = phase3.Phase3Tools(experiment=holder, miner=None)
    reply = asyncio.run(
        tools.call(
            LEVEL4_STAGE, {"strategy_json": json.dumps(strategy), "task_id": ""}, "t1"
        )
    )
    assert reply["status"] == "LEVEL4_INTERFACE" and reply["batch"] > 0
    assert reply["interface"].startswith("sha256:")
    assert reply["commands"][1].endswith("/scratch/output/" + ex.LEVEL4_ENVELOPE_EXPORT)
    bad = asyncio.run(tools.call(LEVEL4_STAGE, {"strategy_json": "{}"}, "t2"))
    assert bad["reason_code"] == "level4_stage_arguments_malformed"
    no_door = asyncio.run(
        tools.call(
            LEVEL4_STAGE, {"strategy_json": json.dumps(strategy), "task_id": TASK}, "t3"
        )
    )
    assert no_door["reason_code"] == "miner_path_not_attached"


def test_a_staged_graph_submission_gets_through_the_door_and_is_kept(tmp_path, lowered):
    """The whole stage call, zero spend: the agent's exported envelope is read through the door's own request check
    (the v1 rule's 4096-byte limit), admitted, and kept by its submission digest."""
    strategy, digest, packed = lowered
    holder = _experiment(tmp_path)
    holder.level4_stage = lambda s, p: ex.Experiment.level4_stage(holder, s, p)
    door = CheckedDoor({TASK[-20:] + "-" + ex.LEVEL4_ENVELOPE_EXPORT: packed})
    tools = phase3.Phase3Tools(experiment=holder, miner=door)
    reply = asyncio.run(
        tools.call(
            LEVEL4_STAGE, {"strategy_json": json.dumps(strategy), "task_id": TASK}, "t4"
        )
    )
    assert reply["status"] == "LEVEL4_STAGED" and reply["submission"] == digest
    assert door.calls and all(c[1]["action"] == "read_file" for c in door.calls)
    assert (
        json.loads(ex.Experiment.level4_staged(holder, digest))["submission"] == digest
    )
