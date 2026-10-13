"""GRAPHITE-L4-STARTER-01: a known-good Level 4 starter that reaches LEVEL4_STAGED and a proposal, at zero spend.

The lane G rerun of 2026-10-13 spent all 19 model calls learning the spec format and never staged. Claims tested:
- the stage tool's interface reply carries the spec contract, the steps, a starter spec and a complete `run_python`
  arguments object, and the docs page is exactly that starter;
- the object passes the door's own request check, and running its source (the reply's own commands, with the export path
  moved under a temporary directory) lowers the starter and packs an envelope with the registered tooling;
- that envelope is read through the door's own `read_file` check, staged (LEVEL4_STAGED) and then accepted by the
  proposal side (`_level4_documents(required=True)`) without `level4_submission_required` or `..._not_staged`;
- the brief sentence and the tool text point at the starter, and the missing-field correction says how to fix it.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import types
from pathlib import Path

import pytest
from test_graphite_level4_stage import TASK, CheckedDoor, _experiment

from carbon.agent_campaign.graphite import experiment as ex
from carbon.agent_campaign.graphite import level4_starter, phase3
from carbon.agent_campaign.graphite.roles import LEVEL4_STAGE, LEVEL4_STAGE_TOOL
from carbon.development_session import research_tasks, research_tools

jax = pytest.importorskip("jax")

REPOSITORY = Path(__file__).resolve().parents[2]
PAGE = REPOSITORY / "docs/development/graphite/level4/STARTER.md"


def _strategy():
    from carbon.battery import level4 as battery

    return json.loads(json.dumps(battery.level0_strategies()["scaffold_mlp"]))


def _holder(tmp_path):
    holder = _experiment(tmp_path)
    holder.level4_interface = lambda s: ex.Experiment.level4_interface(holder, s)
    holder.level4_stage = lambda s, p: ex.Experiment.level4_stage(holder, s, p)
    holder.level4_staged = lambda d: ex.Experiment.level4_staged(holder, d)
    return holder


def _reply(tmp_path):
    holder = _holder(tmp_path)
    tools = phase3.Phase3Tools(experiment=holder, miner=None)
    reply = asyncio.run(
        tools.call(
            LEVEL4_STAGE,
            {"strategy_json": json.dumps(_strategy()), "task_id": ""},
            "t1",
        )
    )
    return holder, reply


def test_the_interface_reply_carries_the_starter_and_the_page_is_the_same_starter(
    tmp_path,
):
    _unused, reply = _reply(tmp_path)
    assert reply["status"] == "LEVEL4_INTERFACE" and reply["authority_granted"] is False
    assert reply["spec_contract"] == level4_starter.SPEC_CONTRACT
    assert reply["workflow"] == list(level4_starter.WORKFLOW)
    assert (
        "FRAMEWORK" in reply["example_spec"] and "def forward" in reply["example_spec"]
    )
    assert reply["inputs"] and reply["outputs"] and reply["batch"] > 0
    run = reply["example_run_python"]
    assert set(run) == {"source", "files", "seconds", "hypothesis", "expected_effect"}
    page = PAGE.read_text(encoding="utf-8")
    fence = "`" * 3
    spec_block = page.split(fence + "python\n", 1)[1].split(fence, 1)[0]
    assert spec_block == reply["example_spec"]
    for step in level4_starter.WORKFLOW:
        assert step in page


def test_the_example_object_passes_the_doors_own_request_check(tmp_path):
    _unused, reply = _reply(tmp_path)
    executor = types.SimpleNamespace(ledger=None)
    research_tasks.check_workspace_request(
        executor, "run_python", reply["example_run_python"], state=False
    )
    missing = dict(reply["example_run_python"])
    del missing["expected_effect"]
    with pytest.raises(research_tasks.WorkspaceRequestRefused) as refused:
        research_tasks.check_workspace_request(
            executor, "run_python", missing, state=False
        )
    assert refused.value.code == "workspace_field_missing" or "expected_effect" in str(
        refused.value.field
    )


def test_the_starter_call_as_the_page_words_it_passes_the_miner_door(tmp_path):
    """Regression (2026-10-13 L4 dry run): step 2 put hypothesis and
    expected_effect only inside arguments_json, and the door refused the call
    before dispatch. The door takes them at the top level and again inside the
    run_python object; the call the page spells out must pass the door's own
    argument check, and the call the old page described must not."""
    from carbon.miner_mcp import standard

    _unused, reply = _reply(tmp_path)
    run = reply["example_run_python"]
    call = {
        "kind": "workspace",
        "strategy": None,
        "action": "run_python",
        "arguments": run,
        "hypothesis": run["hypothesis"],
        "expected_effect": run["expected_effect"],
    }
    args = standard._arguments("start_research_task", call)
    assert json.loads(args["arguments_json"]) == run
    assert args["hypothesis"] == run["hypothesis"] and args["strategy_json"] is None
    old = {k: v for k, v in call.items() if k not in ("hypothesis", "expected_effect")}
    with pytest.raises(standard.AdapterFailure):
        standard._arguments("start_research_task", old)
    page = PAGE.read_text(encoding="utf-8")
    assert "again at the top level of the call" in page
    assert "inside it)" not in page
    for step in level4_starter.WORKFLOW:
        assert "inside it)" not in step
    # Where the id is (an agent had to scan the reply for "rtsk_"): the start
    # reply's task view, the same record get_research_result returns.
    assert "result.task.task_id.value" in level4_starter.WORKFLOW[1]
    assert "`result.task.task_id.value`" in page


def test_the_starter_lowers_stages_and_reaches_a_proposal(tmp_path):
    holder, reply = _reply(tmp_path)
    work = tmp_path / "sandbox"
    work.mkdir()
    export = tmp_path / ex.LEVEL4_ENVELOPE_EXPORT
    source = reply["example_run_python"]["source"].replace(
        "/scratch/output/" + ex.LEVEL4_ENVELOPE_EXPORT, str(export)
    )
    assert str(export) in source
    done = subprocess.run(
        [sys.executable, "-c", source],
        check=False,
        cwd=work,
        env={"PYTHONPATH": str(REPOSITORY), "JAX_PLATFORMS": "cpu", "PATH": ""},
        capture_output=True,
        text=True,
    )
    assert done.returncode == 0, done.stderr[-800:]
    assert export.is_file()
    # The stage tool reads that one export through the door's own read_file check (the v1 rule's 4096-byte limit).
    door = CheckedDoor(
        {TASK[-20:] + "-" + ex.LEVEL4_ENVELOPE_EXPORT: export.read_bytes()}
    )
    tools = phase3.Phase3Tools(experiment=holder, miner=door)
    staged = asyncio.run(
        tools.call(
            LEVEL4_STAGE,
            {"strategy_json": json.dumps(_strategy()), "task_id": TASK},
            "t2",
        )
    )
    assert staged["status"] == "LEVEL4_STAGED" and staged["gates"] == ["G0", "G3", "G4"]
    digest = staged["submission"]
    assert digest.startswith("sha256:") and door.calls
    # The proposal side: the recipe carries the digest and is accepted up to the pod (no refusal code).
    proposal = _strategy()
    proposal["parameters"]["composition_graphs"] = digest
    holder.level4_staged = lambda d: ex.Experiment.level4_staged(holder, d)
    folder = tmp_path / "proposal"
    folder.mkdir()
    documents = ex.Experiment._level4_documents(holder, folder, proposal, required=True)
    assert documents is not None
    # And without the digest the proposal is refused, as the lane G run was.
    with pytest.raises(ex.Unrebuildable, match="level4_submission_required"):
        ex.Experiment._level4_documents(holder, tmp_path, _strategy(), required=True)


def test_the_brief_and_the_tool_text_point_at_the_starter():
    assert "example_run_python" in LEVEL4_STAGE_TOOL["description"]
    assert "known-good" in LEVEL4_STAGE_TOOL["description"]
    source = (REPOSITORY / "carbon/agent_campaign/graphite/phase3.py").read_text(
        encoding="utf-8"
    )
    assert "carries a known-good example_spec" in source


def test_the_missing_field_correction_says_how_to_fix_it():
    text = research_tools.task_correction(
        "workspace_field_missing",
        "arguments_json.expected_effect",
        None,
        tool="start_research_task",
    )
    assert "named below" in text and "inside arguments_json" in text
    assert text.endswith(
        "The field that broke the contract: arguments_json.expected_effect. The tool: start_research_task."
    )
    # The one-line example is a real run_python object: it carries every field the action requires.
    example = json.loads(text.split("for example: ", 1)[1].split("}.", 1)[0] + "}")
    required, _optional = research_tasks.workspace_fields("run_python")
    assert set(example) >= required
