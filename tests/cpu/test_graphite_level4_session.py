"""GRAPHITE-L4-STAGING-01 (R1), end to end on the CPU: a scripted Level 4
Constructor stages its lowered graph and proposes it.

Claims tested:
- a Level 4 brief offers the stage tool, and the session's role offers it;
- the stage reads the agent's export through the miner door, admits it and
  keeps it; the proposal naming its digest pins the documents in Carbon's
  expected record, writes the envelope beside itself, and the pod job carries
  the envelope; the scripted pod builds its record with the same documents.
Scripted model, scripted pods, a stand-in miner door: no live call, no spend.
"""

from __future__ import annotations

import base64
import gzip
import json

import graphite_phase3_fixtures as p3f
import pytest
from graphite_fixtures import RecordingMinerTools

from carbon.agent_campaign.graphite import experiment as ex
from carbon.agent_campaign.graphite import phase3
from carbon.agent_campaign.graphite.model import text, tool
from carbon.agent_campaign.graphite.roles import LEVEL4_STAGE

jax = pytest.importorskip("jax")
TASK = "rtsk_" + "b" * 64


class Door(RecordingMinerTools):
    """The miner door, holding one exported workspace file."""

    def __init__(self, name, body):
        super().__init__()
        self.name, self.body = name, body

    async def call(self, name, arguments, identity):
        if arguments.get("action") != "read_file":
            return await super().call(name, arguments, identity)
        self.calls.append((name, arguments, identity))
        args = json.loads(arguments["arguments_json"])
        assert args["name"] == self.name
        chunk = self.body[args["offset"] : args["offset"] + args["count"]]
        return {
            "result": {
                "bytes": len(self.body),
                "content_utf8": None,
                "content_base64": base64.b64encode(chunk).decode(),
            }
        }


@pytest.fixture(scope="module")
def lowered():
    from carbon.battery import level4 as battery
    from carbon.level4 import allowlist as allowlist_module
    from carbon.level4 import intake, staging, submission

    strategy = json.loads(json.dumps(p3f.BASELINE))
    manifest, files = battery.lower_recipe(
        strategy, allowlist_module.load(), max_bytes=intake.BOUNDS["document_bytes"]
    )
    envelope = staging.envelope(submission.canonical(manifest), files)
    packed = gzip.compress(json.dumps(envelope).encode(), mtime=0)
    graph = json.loads(json.dumps(strategy))
    graph["parameters"][battery.FIELD] = envelope["submission"]
    return strategy, graph, envelope["submission"], packed


def test_a_level4_constructor_stages_and_proposes_a_graph(tmp_path, lowered):
    from carbon.reconstruction import development_variants as dv

    strategy, graph, digest, packed = lowered
    variant = dv.variant(p3f.SCORING.challenge_id, 4)
    door = Door(TASK[-20:] + "-" + ex.LEVEL4_ENVELOPE_EXPORT, packed)
    script = [
        p3f.propose(strategy, "a plain recipe must not become an L4 bundle"),
        tool(LEVEL4_STAGE, {"strategy_json": json.dumps(strategy), "task_id": TASK}),
        p3f.propose(graph, "the baseline's own network, as a Level 4 graph"),
        text("DRY RUN: the scripted Constructor stops here."),
    ]
    pods = p3f.ScriptedPods(steps=p3f.steps(1.0, 0.9))
    graphite = p3f.provider(tmp_path, script, pods, miner=door)
    brief = phase3.session_brief(
        checkout_commit="1" * 40,
        budget=graphite.budget,
        literature=graphite.literature,
        scoring=p3f.SCORING,
        variant=variant,
        level_domain_text=True,
    )
    assert brief.level4_stage is True
    assert brief.document()["level4_stage"] is True
    control = p3f.controller(tmp_path, graphite)
    try:
        phase3.run_session(control, graphite, brief, 1, variant)
    finally:
        control.close()
    run = tmp_path / "graphite" / "runs" / p3f.run_id(1)
    events = (run / "events.jsonl").read_text()
    assert '"status":"LEVEL4_STAGED"' in events
    records = [
        json.loads(path.read_bytes())
        for path in (run / "experiment" / "proposals").glob("*/result.json")
    ]
    refused = [r for r in records if r["status"] == "REFUSED_UNREBUILDABLE"]
    assert len(refused) == 1
    assert refused[0]["reason_code"] == "level4_submission_required"
    assert refused[0]["scored"] is False
    assert len(pods.launched) == 2  # Only the baseline and staged graph dispatch.
    delivery = json.loads((run / "delivery.json").read_bytes())
    # The bundle carries the envelope, and rebuilds from itself alone.
    assert delivery["clean_rebuild"]["status"] == "REBUILT", delivery["clean_rebuild"]
    assert (run / "delivery" / "level4-envelope.json").is_file()
    proposals = sorted((run / "experiment" / "proposals").glob("*/expected.json"))
    carried = [p for p in proposals if (p.parent / "level4-envelope.json").is_file()]
    assert len(carried) == 1
    expected = json.loads(carried[0].read_bytes())
    assert "level4-manifest.json" in expected["staged"]
    jobs = [job for _, job in pods.launched if job.level4_envelope is not None]
    assert len(jobs) == 1
    assert jobs[0].strategy["parameters"]["composition_graphs"] == digest
