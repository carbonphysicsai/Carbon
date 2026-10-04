"""Research tools as the model experiences them (LP-PROD-D).

Claims tested, each absence paired with the same check finding a presence:

- a workspace request whose values Carbon would refuse is refused before
  dispatch with a closed code, the field and the fix: nothing starts, no
  research-trial slot is charged, the requester's own text is not repeated,
  and the correction is registered text a door can verify;
- a resend of a request that already started a task is not refused for the
  workspace state its own run changed;
- the executor reads the same check, so a request that reaches it anyway
  completes as REQUEST_REFUSED, never as an infrastructure failure;
- through the standard MCP door, such a refusal arrives as a refusal that
  dispatched nothing (the door verifies it with `correction_parts`, W1);
- a run's result - CPU, Julia, local and remote GPU - returns stdout and
  stderr tails and, on a nonzero exit, the traceback with its first and last
  lines, each bounded as delivered;
- read_file keeps its historical shape and 4 KiB under the historical rule;
  under v2 it returns 8 KiB once, as text when it is text, and one maximal
  read fits beside the battery agent's real first request;
- capability requests, the roadmap and demand read the campaign's own
  Challenge registry, and Burgers' stays the default;
- an unserved practice backend is refused before dispatch, naming the
  backends this host serves;
- refusals name their tool and field; inspect_prior_alignment files a
  refusal, never a capability request;
- the versioned tools rule leaves the historical tools byte for byte and is
  read from the campaign's frozen run plan, as is the battery agent's
  research environment;
- the battery discovery document says what the tools take: an encoded
  arguments_json, check_design, the campaign's own freeze and submit steps,
  and examples that are designs as they stand.
"""

from __future__ import annotations

import asyncio
import base64
import json
from types import SimpleNamespace

import pytest

from carbon import research
from carbon.development_session import research_tools
from carbon.development_session.profile import canonical, digest
from carbon.development_session.research_ledger import VERSION, CampaignLedger
from carbon.development_session.research_service import make_research_service
from carbon.development_session.research_tools import (
    ARGUMENT_NORMALISATION,
    PREFIX,
    TOOLS,
    TOOLS_RULE,
    TOOLS_V2,
    ResearchMinerTools,
    campaign_argument_normalisation,
    frozen_argument_normalisation,
    registered_correction,
    task_correction,
    tools_for_sdk,
)
from carbon.miner_mcp.standard import AdapterFailure
from carbon.reconstruction import capability_registry as registry

BATTERY = registry.BATTERY_CHALLENGE
CAPABILITY = {
    "purpose": "p",
    "operation": "o",
    "hypothesis": "h",
    "public_evidence": "e",
    "reason": "missing_adapter",
    "expected_benefit": "b",
    "estimated_cost": "c",
    "minimal_safe_design": "d",
    "verification": "v",
}
SENTINEL = "REQUESTER-TEXT-SENTINEL-7f3a"


def ledger(path, *, ceilings=None, provider=None):
    """A frozen campaign ledger; `ceilings=None` is a miner with no budget."""
    path.mkdir(parents=True, exist_ok=True)
    value = CampaignLedger(path, clock=lambda: 1000)
    value.freeze(
        {
            "schema": VERSION,
            "ceilings": ceilings,
            "elapsed_seconds": None,
            "campaign_id": "test-only",
            "implementation": "fixture",
            "objective": "fixture",
            "sampling": "test-only",
            "control": "test-only",
            "selection": "test-only",
            "replica_policy": "one",
            "provider": provider or "test-only",
            "owner": "alice",
        }
    )
    return value


@pytest.fixture
def door(tmp_path):
    """The SDK over a real composition; no connection, so nothing can be
    dispatched: a refusal must come first."""
    sdk, meter, composition = sdk_for(tmp_path)
    try:
        yield sdk, meter, composition
    finally:
        composition.tasks.close()


def workspace(action, arguments):
    return {
        "kind": "workspace",
        "strategy_json": None,
        "action": action,
        "arguments_json": json.dumps(arguments),
        "hypothesis": "inspect the public inputs",
        "expected_effect": "a corrected request",
    }


def refused(sdk, meter, args, identity="lp-prod-d-refusal-0001"):
    """Call through the SDK and require a pre-dispatch refusal that started
    nothing and charged nothing."""
    result = asyncio.run(sdk.call(PREFIX + "start_research_task", args, identity))
    assert result["status"] == "REJECTED_BEFORE_DISPATCH", result
    assert result["authority_granted"] is False
    assert registered_correction(result), result
    assert "The tool: start_research_task." in result["correction"]
    assert SENTINEL not in canonical(result).decode()
    status = meter.status(owner="alice")
    assert status["used"]["research_trials"] == 0
    assert sdk.composition.tasks.started_task(sdk.challenge, identity) is None
    return result


# ---- 1. Workspace values are refused before dispatch, by field.


def test_check_design_given_a_discovery_example_with_its_verdict_is_named(door):
    sdk, meter, _ = door
    strategy = {
        "schema_version": "1.0",
        "challenge_id": BATTERY,
        "backbone": "mlp",
        "parameters": {"steps": 2000, "width": 64, "depth": 3},
    }
    # The old example shape: the verdict inside the design.
    result = refused(
        sdk,
        meter,
        workspace("check_design", {"design": {"strategy": strategy, "admission": {}}}),
    )
    assert result["correction_code"] == "check_design_shape"
    assert result["field"] == "arguments_json.design"
    assert "design.strategy" in result["correction"]
    # Specimen: the example as a design, as discovery now gives it, builds.
    request = sdk._request(
        "start_research_task",
        workspace("check_design", {"design": {"strategy": strategy}}),
        "lp-prod-d-design-ok-0001",
    )
    assert type(request.task_spec) is research.DevelopmentWorkspaceTaskSpecV1


@pytest.mark.parametrize(
    ("request_", "code", "field"),
    [
        (
            {k: v for k, v in CAPABILITY.items() if k != "purpose"},
            "capability_request_field_missing",
            "arguments_json.request.purpose",
        ),
        (
            {**CAPABILITY, SENTINEL: "x"},
            "capability_request_field_unexpected",
            "arguments_json.request",
        ),
        (
            {**CAPABILITY, "reason": SENTINEL},
            "capability_request_reason_unknown",
            "arguments_json.request.reason",
        ),
        # A reason that is not even a string is named as a reason too.
        (
            {**CAPABILITY, "reason": [SENTINEL]},
            "capability_request_reason_unknown",
            "arguments_json.request.reason",
        ),
        (
            {**CAPABILITY, "verification": ""},
            "capability_request_text_bounded",
            "arguments_json.request.verification",
        ),
        (
            {**CAPABILITY, "capability": SENTINEL},
            "capability_id_unknown",
            "arguments_json.request.capability",
        ),
        ([SENTINEL], "capability_request_object_required", "arguments_json.request"),
    ],
)
def test_capability_request_fields_and_reason_are_named(door, request_, code, field):
    sdk, meter, _ = door
    result = refused(sdk, meter, workspace("capability_request", {"request": request_}))
    assert (result["correction_code"], result["field"]) == (code, field)
    if code == "capability_request_reason_unknown":
        assert "missing_adapter" in result["correction"]
    # Filed as a refusal: nothing was asked for, so no demand is recorded.
    assert {n["kind"] for n in meter.status(owner="alice")["notes"]} == {"refusal"}


def test_public_material_outside_the_list_is_named_with_the_list(door):
    sdk, meter, _ = door
    result = refused(sdk, meter, workspace("public_material", {"name": SENTINEL}))
    assert result["correction_code"] == "public_material_unknown"
    assert result["field"] == "arguments_json.name"
    assert (
        "Allowed here: objective, capabilities, training_data, practice_data, "
        "reference_method." in result["correction"]
    )


def test_notebook_kind_is_named_with_the_kinds(door):
    sdk, meter, _ = door
    result = refused(sdk, meter, workspace("notebook", {"kind": SENTINEL, "body": {}}))
    assert result["correction_code"] == "notebook_kind_unknown"
    assert "hypothesis, decision, notebook" in result["correction"]


def sdk_for(path, *, provider=None):
    """`door`'s SDK over a ledger whose run plan is `provider`."""
    meter = ledger(path / "ledger", provider=provider)
    composition = make_research_service(
        root=path / "tasks",
        ledger=meter,
        owner="alice",
        image=SimpleNamespace(),
        public_material=lambda *a: pytest.fail("refused request executed"),
        practice=lambda *a: pytest.fail("refused request executed"),
    )
    sdk = ResearchMinerTools(
        connection=None,
        wrapper=None,
        composition=composition,
        ledger=meter,
        owner="alice",
    )
    return sdk, meter, composition


@pytest.mark.parametrize(
    ("provider", "limit"),
    [(None, 4096), ({"agent": "autonomous", "research_tools": TOOLS_RULE}, 8192)],
)
def test_read_file_count_over_the_cap_is_named(tmp_path, provider, limit):
    """The historical rule keeps its 4 KiB; v2 reads 8 KiB. Either way the
    refusal names the field and the campaign's own maximum."""
    sdk, meter, composition = sdk_for(tmp_path, provider=provider)
    try:
        composition.executor.workspace.put("notes.txt", b"x")
        result = refused(
            sdk,
            meter,
            workspace(
                "read_file", {"name": "notes.txt", "offset": 0, "count": limit + 1}
            ),
        )
        assert (result["correction_code"], result["field"]) == (
            "read_file_range",
            "arguments_json.count",
        )
        assert "Allowed here: " + str(limit) + "." in result["correction"]
        # Specimen: the cap itself is accepted.
        sdk._request(
            "start_research_task",
            workspace("read_file", {"name": "notes.txt", "offset": 0, "count": limit}),
            "lp-prod-d-read-cap-0001",
        )
    finally:
        composition.tasks.close()


def test_a_missing_file_is_named_for_read_and_for_a_run(door):
    sdk, meter, _ = door
    result = refused(
        sdk,
        meter,
        workspace("read_file", {"name": "absent.txt", "offset": 0, "count": 1}),
    )
    assert (result["correction_code"], result["field"]) == (
        "workspace_file_missing",
        "arguments_json.name",
    )
    run = workspace(
        "run_python",
        {
            "source": "print(1)",
            "files": ["absent.txt"],
            "seconds": 60,
            "hypothesis": "h",
            "expected_effect": "e",
        },
    )
    result = refused(sdk, meter, run, "lp-prod-d-run-missing-0001")
    assert (result["correction_code"], result["field"]) == (
        "workspace_file_missing",
        "arguments_json.files",
    )


def test_a_stale_expected_digest_is_refused_and_explained(door):
    sdk, meter, composition = door
    current = composition.executor.workspace.put("notes.txt", b"version one")
    stale = workspace(
        "write_file",
        {
            "name": "notes.txt",
            "content_base64": base64.b64encode(b"version two").decode(),
            "expected_digest": None,
        },
    )
    result = refused(sdk, meter, stale)
    assert result["correction_code"] == "write_file_expected_digest_conflict"
    assert result["field"] == "arguments_json.expected_digest"
    assert "the digest the file has now" in result["correction"]
    assert "null when the file does not exist yet" in result["correction"]
    # Specimen: the current digest is accepted, and so is writing the bytes
    # the file already holds, whatever the guard says.
    fresh = json.loads(stale["arguments_json"])
    sdk._request(
        "start_research_task",
        workspace("write_file", {**fresh, "expected_digest": current}),
        "lp-prod-d-write-ok-0001",
    )
    same = {
        **fresh,
        "content_base64": base64.b64encode(b"version one").decode(),
    }
    sdk._request(
        "start_research_task",
        workspace("write_file", same),
        "lp-prod-d-write-same-0001",
    )


def test_a_resend_of_a_started_write_returns_its_task_not_a_refusal(door):
    """A write under one operation id starts; its own run changes the file.
    The same request resent under that id must not now be refused for the
    guard its own run moved: it is the started task, not a new request."""
    sdk, _, composition = door
    args = workspace(
        "write_file",
        {
            "name": "fresh.txt",
            "content_base64": base64.b64encode(b"first").decode(),
            "expected_digest": None,
        },
    )
    identity = "lp-prod-d-write-resend-0001"
    request = sdk._request("start_research_task", args, identity)
    task = composition.tasks.start_research_task(request).task
    done = composition.tasks.run_queued_task(task.task_id)
    assert done.state is research.ResearchTaskState.SUCCEEDED
    assert composition.executor.workspace.get("fresh.txt") == b"first"
    composition.executor.workspace.put(
        "fresh.txt", b"second", expected_digest=digest(b"first")
    )
    resent = sdk._request("start_research_task", args, identity)
    assert composition.tasks.start_research_task(resent).task.task_id == task.task_id
    # Specimen: under a new operation id the same values are refused.
    with pytest.raises(research_tools.TaskContractMismatch):
        sdk._request("start_research_task", args, "lp-prod-d-write-resend-0002")


def test_a_run_without_seconds_under_a_time_budget_is_named(tmp_path):
    meter = ledger(tmp_path / "ledger", ceilings={"numerical_milliseconds": 60_000})
    composition = make_research_service(
        root=tmp_path / "tasks",
        ledger=meter,
        owner="alice",
        image=SimpleNamespace(),
        public_material=lambda *a: None,
        practice=lambda *a: None,
    )
    sdk = ResearchMinerTools(
        connection=None,
        wrapper=None,
        composition=composition,
        ledger=meter,
        owner="alice",
    )
    try:
        run = {
            "source": "print(1)",
            "files": [],
            "hypothesis": "h",
            "expected_effect": "e",
        }
        result = refused(sdk, meter, workspace("run_python", run))
        assert (result["correction_code"], result["field"]) == (
            "run_seconds_required",
            "arguments_json.seconds",
        )
        # Specimen: with a wall allowance the same run builds.
        sdk._request(
            "start_research_task",
            workspace("run_python", {**run, "seconds": 30}),
            "lp-prod-d-seconds-ok-0001",
        )
    finally:
        composition.tasks.close()


def test_run_text_source_files_and_seconds_values_are_named(door):
    sdk, meter, _ = door
    base = {
        "source": "print(1)",
        "files": [],
        "seconds": 60,
        "hypothesis": "h",
        "expected_effect": "e",
    }
    for index, (change, code, field) in enumerate(
        [
            (
                {"hypothesis": ""},
                "run_hypothesis_required",
                "arguments_json.hypothesis",
            ),
            ({"source": ""}, "run_source_required", "arguments_json.source"),
            ({"files": "notes.txt"}, "run_files_invalid", "arguments_json.files"),
            ({"files": ["program.py"]}, "run_files_invalid", "arguments_json.files"),
            ({"seconds": 0}, "run_seconds_invalid", "arguments_json.seconds"),
            ({"device": "tpu"}, "device_choice_invalid", "arguments_json.device"),
        ]
    ):
        result = refused(
            sdk,
            meter,
            workspace("run_python", {**base, **change}),
            f"lp-prod-d-run-values-{index:04d}",
        )
        assert (result["correction_code"], result["field"]) == (code, field)


def test_a_run_reserves_only_the_names_its_own_carrier_stages(door):
    """Every run's carrier stages program.py; run_julia's stages program.jl
    too. So run_python may stage an own file named program.jl, as it always
    could, and run_julia may not."""
    from carbon.development_session.research_tasks import (
        WorkspaceRequestRefused,
        check_workspace_request,
    )

    sdk, _, composition = door
    composition.executor.workspace.put("program.jl", b"println(1)")
    run = {
        "source": "print(open('program.jl').read())",
        "files": ["program.jl"],
        "seconds": 60,
        "hypothesis": "h",
        "expected_effect": "e",
    }
    request = sdk._request(
        "start_research_task", workspace("run_python", run), "lp-prod-d-stage-0001"
    )
    assert request.task_spec.action == "run_python"
    with pytest.raises(WorkspaceRequestRefused) as refusal:
        check_workspace_request(composition.executor, "run_julia", run)
    assert (refusal.value.code, refusal.value.choices) == (
        "run_files_invalid",
        ("program.jl", "program.py"),
    )


def test_what_no_named_check_covers_still_names_the_tool(door, monkeypatch):
    """The catch-all refusal names the tool and the arguments as a whole,
    never the exception text behind it."""
    sdk, meter, _ = door

    def refusing(*args):
        raise TypeError("PRIVATE-CONSTRUCTOR-TEXT")

    monkeypatch.setattr(research, "DryValidateRequest", refusing)
    result = asyncio.run(
        sdk.call(
            PREFIX + "dry_validate", {"strategy_json": "{}"}, "lp-prod-d-catchall-0001"
        )
    )
    assert result["status"] == "REJECTED_BEFORE_DISPATCH"
    assert (result["correction_code"], result["field"]) == (
        "tool_value_invalid",
        "arguments",
    )
    assert "The tool: dry_validate." in result["correction"]
    assert registered_correction(result)
    assert "PRIVATE-CONSTRUCTOR-TEXT" not in canonical(result).decode()
    assert meter.status(owner="alice")["used"]["research_trials"] == 0


def test_an_oversized_arguments_object_is_named(door):
    sdk, meter, _ = door
    result = refused(
        sdk,
        meter,
        workspace(
            "write_file",
            {
                "name": "big.txt",
                "content_base64": base64.b64encode(b"x" * 12_000).decode(),
                "expected_digest": None,
            },
        ),
    )
    assert (result["correction_code"], result["field"]) == (
        "workspace_arguments_too_large",
        "arguments_json",
    )
    assert "../output" in result["correction"]


# ---- 6. An unserved practice backend is refused before dispatch.


def test_an_unserved_practice_backend_is_refused_naming_the_served_ones(tmp_path):
    meter = ledger(tmp_path / "ledger")
    asked = []

    class Practice:
        def backend_refusal(self, strategy):
            asked.append(strategy)
            return (
                None if strategy["parameters"].get("backend") != "pytorch" else ("jax",)
            )

        def __call__(self, *args):
            pytest.fail("refused practice executed")

    composition = make_research_service(
        root=tmp_path / "tasks",
        ledger=meter,
        owner="alice",
        image=SimpleNamespace(),
        public_material=lambda *a: None,
        practice=Practice(),
    )
    sdk = ResearchMinerTools(
        connection=None,
        wrapper=None,
        composition=composition,
        ledger=meter,
        owner="alice",
    )
    recipe = {
        "schema_version": "1.0",
        "challenge_id": BATTERY,
        "backbone": "mlp",
        "parameters": {"backend": "pytorch"},
    }
    args = {
        "kind": "practice",
        "strategy_json": canonical(recipe).decode(),
        "action": None,
        "arguments_json": None,
        "hypothesis": "h",
        "expected_effect": "e",
    }
    try:
        result = refused(sdk, meter, args)
        assert (result["correction_code"], result["field"]) == (
            "backend_not_served",
            "strategy_json",
        )
        assert "Allowed here: jax." in result["correction"]
        # Specimen: a served backend builds its practice request.
        recipe["parameters"]["backend"] = "jax"
        sdk._request(
            "start_research_task",
            {**args, "strategy_json": canonical(recipe).decode()},
            "lp-prod-d-practice-ok-0001",
        )
        assert len(asked) == 2
    finally:
        composition.tasks.close()


def test_battery_practice_names_the_backends_its_image_serves():
    from carbon.battery.research import BatteryPractice

    practice = object.__new__(BatteryPractice)
    practice.backends = ("jax",)
    strategy = {
        "schema_version": "1.0",
        "challenge_id": BATTERY,
        "backbone": "mlp",
        "parameters": {"steps": 32, "width": 8, "depth": 1, "backend": "pytorch"},
    }
    assert practice.backend_refusal(strategy) == ("jax",)
    strategy["parameters"]["backend"] = "jax"
    assert practice.backend_refusal(strategy) is None
    # A recipe that does not compile is the compiler's to name, not this.
    assert practice.backend_refusal({"backbone": "unknown"}) is None
    practice.backends = ("jax", "pytorch")
    strategy["parameters"]["backend"] = "pytorch"
    assert practice.backend_refusal(strategy) is None


# ---- 8. Refusals name their tool and field.


@pytest.mark.parametrize(
    ("name", "args", "code", "field"),
    [
        (PREFIX + SENTINEL, {}, "tool_unknown", "tool"),
        (PREFIX + "dry_validate", [], "tool_arguments_object_required", "arguments"),
        (PREFIX + "dry_validate", {}, "tool_field_missing", "strategy_json"),
        (
            PREFIX + "dry_validate",
            {"strategy_json": "{}", SENTINEL: 1},
            "tool_field_unexpected",
            "arguments",
        ),
        (
            PREFIX + "dry_validate",
            {"strategy_json": "[1]"},
            "json_object_required",
            "strategy_json",
        ),
        (
            PREFIX + "get_research_result",
            {"task_id": SENTINEL, "poll_sequence": 0},
            "task_id_invalid",
            "task_id",
        ),
        (
            PREFIX + "start_research_task",
            {
                **workspace("inventory", {}),
                "hypothesis": "x" * 2049,
            },
            "tool_text_bounded",
            "hypothesis",
        ),
        (
            PREFIX + "start_research_task",
            {**workspace("inventory", {}), "action": SENTINEL},
            "workspace_action_unknown",
            "action",
        ),
    ],
)
def test_a_refusal_names_its_tool_and_field(door, name, args, code, field):
    sdk, meter, _ = door
    result = asyncio.run(sdk.call(name, args, "lp-prod-d-named-0001"))
    assert result["status"] == "REJECTED_BEFORE_DISPATCH"
    assert (result["correction_code"], result["field"]) == (code, field)
    assert registered_correction(result)
    operation = name.removeprefix(PREFIX)
    if operation in research_tools.FIELDS:
        assert "The tool: " + operation + "." in result["correction"]
    assert SENTINEL not in canonical(result).decode()
    assert meter.status(owner="alice")["used"]["research_trials"] == 0


def test_registered_correction_refuses_text_carbon_did_not_write():
    good = {
        "correction_code": "read_file_range",
        "field": "arguments_json.count",
        "correction": research_tools.task_correction(
            "read_file_range", "arguments_json.count", None, tool="start_research_task"
        ),
    }
    assert registered_correction(good)
    assert not registered_correction({**good, "correction": "private message"})
    assert not registered_correction({**good, "field": SENTINEL})
    assert not registered_correction({**good, "correction_code": SENTINEL})
    listed = {
        **good,
        "correction_code": "public_material_unknown",
        "field": "arguments_json.name",
        "correction": research_tools.task_correction(
            "public_material_unknown",
            "arguments_json.name",
            None,
            choices=("objective",),
        ),
    }
    assert registered_correction(listed)
    assert not registered_correction(
        {
            **listed,
            "correction": listed["correction"].replace("objective.", "objective b."),
        }
    )
    # A value that looks like a choice but is on no closed list (a private
    # identifier, say) is not one Carbon may list (W1).
    unlisted = research_tools.task_correction(
        "public_material_unknown", "arguments_json.name", None, choices=("a",)
    )
    assert not registered_correction({**listed, "correction": unlisted})
    with pytest.raises(TypeError):
        research_tools.TaskContractMismatch("read_file_range", SENTINEL)
    with pytest.raises(TypeError):
        research_tools.TaskContractMismatch(
            "public_material_unknown", "arguments_json.name", ("not a choice!",)
        )


# ---- 9. inspect_prior_alignment files a refusal, not demand.


def test_prior_alignment_is_journalled_as_a_refusal(door, monkeypatch):
    sdk, meter, _ = door

    async def registration():
        return SimpleNamespace(snapshot_id="snapshot")

    async def supervised(*args, **kwargs):
        return {}

    monkeypatch.setattr(research_tools, "message", lambda *a, **k: {})
    monkeypatch.setattr(
        research_tools,
        "BittensorMessageSigner",
        lambda key: SimpleNamespace(sign=lambda body, **k: {}),
    )
    sdk.connection = SimpleNamespace(
        check_registration=registration,
        chain_context=None,
        miner_key=None,
        publisher=None,
    )
    sdk.wrapper = SimpleNamespace(supervised_call=supervised)
    result = asyncio.run(
        sdk.call(
            PREFIX + "inspect_prior_alignment",
            {"strategy_json": "{}"},
            "lp-prod-d-prior-0001",
        )
    )
    assert result["status"] == "UNAVAILABLE"
    kinds = [n["kind"] for n in meter.status(owner="alice")["notes"]]
    assert kinds == ["refusal"]
    assert "capability_request" not in kinds


# ---- 1 (executor). A request that reaches the executor is refused typed.


def test_a_refused_request_that_reaches_the_executor_completes_typed(door):
    """A raw protocol client skips the SDK; the executor's own check refuses
    it with the same code, never as an infrastructure failure, and the write
    does not happen."""
    sdk, meter, composition = door
    composition.executor.workspace.put("notes.txt", b"held")
    spec = research.DevelopmentWorkspaceTaskSpecV1(
        "carbon.autoresearch.workspace.v1",
        "write_file",
        canonical(
            {
                "name": "notes.txt",
                "content_base64": base64.b64encode(b"other").decode(),
                "expected_digest": None,
            }
        ).decode(),
    )
    request = sdk._request(
        "start_research_task",
        workspace("inventory", {}),
        "lp-prod-d-raw-0001",
    )
    from dataclasses import replace

    raw = replace(request, task_spec=spec)
    task = composition.tasks.start_research_task(raw).task
    done = composition.tasks.run_queued_task(task.task_id)
    assert done.state is research.ResearchTaskState.SUCCEEDED
    result = composition.executor.public_result(done)["result"]
    assert result["outcome"] == "REQUEST_REFUSED"
    assert result["correction_code"] == "write_file_expected_digest_conflict"
    assert result["nothing_ran"] is True and result["trial_charged"] is False
    assert composition.executor.workspace.get("notes.txt") == b"held"
    assert meter.status(owner="alice")["used"]["research_trials"] == 0


# ---- 2. Run output and read_file.


def _operation(ledger_, name, *, stdout=b"", stderr=b""):
    folder = ledger_.root / name
    folder.mkdir()
    (folder / "stdout.txt").write_bytes(stdout)
    (folder / "stderr.txt").write_bytes(stderr)
    return name


def test_program_output_returns_bounded_tails_and_the_traceback(tmp_path):
    from carbon.development_session.research_carrier import (
        OUTPUT_TAIL_BYTES,
        program_output,
    )

    meter = CampaignLedger(tmp_path)
    noise = b"progress line\n" * 1000
    traceback = (
        b"Traceback (most recent call last):\n"
        b'  File "/input/program.py", line 3, in <module>\n'
        b"ZeroDivisionError: division by zero\n"
    )
    name = _operation(
        meter,
        "operation-a",
        stdout=noise + b"loss=0.25\n",
        stderr=noise + traceback + b"\xff\xfe",
    )
    output = program_output(meter, name, observation="NONZERO_EXIT")
    assert output["stdout_tail"].endswith("loss=0.25\n")
    assert len(canonical(output["stdout_tail"])) - 2 <= OUTPUT_TAIL_BYTES
    assert output["traceback"].startswith("Traceback (most recent call last):")
    assert "ZeroDivisionError" in output["traceback"]
    # Bytes that are not UTF-8 are replaced, never an error.
    assert output["stderr_tail"].endswith("��")
    # Specimen: a successful run has no traceback field; a missing kept file
    # is None, and a name that is a path - or anything but a run's own
    # operation folder - is never read.
    assert "traceback" not in program_output(meter, name)
    assert program_output(meter, "operation-absent")["stdout_tail"] is None
    (meter.root / "stdout.txt").write_bytes(b"the ledger root's own file")
    for path in ("../operation-a", "..", ".", "", "operation-a/..", "stdout.txt"):
        assert program_output(meter, path) == {
            "stdout_tail": None,
            "stderr_tail": None,
        }, path


def delivered(text):
    """A text field's size as a result delivers it: JSON, escaped."""
    return len(canonical(text)) - 2


def test_each_output_field_is_bounded_as_the_result_delivers_it(tmp_path):
    """Bytes that are not UTF-8 become U+FFFD and control characters are
    escaped, each six bytes of JSON: a tail is cut to fit as delivered, not
    as read, so 4 KiB read never reaches the model as 24 KiB."""
    from carbon.development_session.research_carrier import (
        OUTPUT_TAIL_BYTES,
        program_output,
    )

    meter = CampaignLedger(tmp_path)
    name = _operation(
        meter,
        "operation-escaped",
        stdout=b"\xff" * 10_000,
        stderr=b"Traceback (most recent call last):\n" + b"\x1b[31m!" * 3000,
    )
    output = program_output(meter, name, observation="NONZERO_EXIT")
    # Full to within one escaped character (six bytes), never over.
    for key in ("stdout_tail", "stderr_tail"):
        assert OUTPUT_TAIL_BYTES - 6 < delivered(output[key]) <= OUTPUT_TAIL_BYTES
    assert set(output["stdout_tail"]) == {"�"}
    # A long traceback keeps both ends and a note, within the same bound.
    assert OUTPUT_TAIL_BYTES // 2 < delivered(output["traceback"]) <= OUTPUT_TAIL_BYTES
    # Specimen: plain text keeps exactly its last 4096 bytes.
    plain = _operation(meter, "operation-plain", stdout=b"x" * 10_000)
    assert program_output(meter, plain)["stdout_tail"] == "x" * OUTPUT_TAIL_BYTES


def test_a_long_traceback_keeps_its_first_and_last_lines(tmp_path):
    """Julia's error message opens its block; Python's exception closes it.
    A traceback longer than the bound keeps both ends, with what was left
    out counted between them."""
    from carbon.development_session.research_carrier import (
        OUTPUT_TAIL_BYTES,
        program_output,
    )

    meter = CampaignLedger(tmp_path)
    frames = b"".join(
        b"  [%d] step(u::Vector{Float64}, p::NamedTuple)\n"
        b"    @ Main /input/program.jl:%d\n" % (index, index)
        for index in range(200)
    )
    julia = (
        b"   Resolving package versions...\n"
        b"ERROR: LoadError: DimensionMismatch: arrays could not be broadcast "
        b"to a common size\nStacktrace:\n"
        + frames
        + b"in expression starting at /input/program.jl:12\n"
    )
    assert len(julia) > 2 * OUTPUT_TAIL_BYTES
    output = program_output(
        meter,
        _operation(meter, "operation-julia", stderr=julia),
        observation="NONZERO_EXIT",
    )
    trace = output["traceback"]
    assert trace.startswith("ERROR: LoadError: DimensionMismatch")
    assert trace.endswith("in expression starting at /input/program.jl:12\n")
    assert "characters left out by Carbon" in trace
    assert delivered(trace) <= OUTPUT_TAIL_BYTES
    # Why the start is kept: the stderr tail alone has lost the message.
    assert "DimensionMismatch" not in output["stderr_tail"]
    python = (
        b"Traceback (most recent call last):\n"
        + b'  File "/input/program.py", line 9, in f\n    return f()\n' * 400
        + b"RecursionError: maximum recursion depth exceeded\n"
    )
    trace = program_output(
        meter,
        _operation(meter, "operation-python", stderr=python),
        observation="NONZERO_EXIT",
    )["traceback"]
    assert trace.startswith("Traceback (most recent call last):")
    assert trace.endswith("RecursionError: maximum recursion depth exceeded\n")
    assert delivered(trace) <= OUTPUT_TAIL_BYTES
    # Specimen: a traceback that fits is returned whole.
    short = b"ERROR: LoadError: UndefVarError: `x` not defined\nStacktrace:\n"
    assert (
        program_output(
            meter,
            _operation(meter, "operation-short", stderr=b"warning\n" + short),
            observation="NONZERO_EXIT",
        )["traceback"]
        == short.decode()
    )


def test_a_run_result_carries_its_output_and_a_failure_its_traceback(
    tmp_path, monkeypatch
):
    from carbon.development_session import research_tasks
    from carbon.development_session.research_carrier import (
        MINER_FAILURE_SCHEMA,
        MinerProgramFailure,
    )

    meter = CampaignLedger(tmp_path / "ledger")
    executor = research_tasks.PublicResearchExecutor(
        ledger=meter,
        owner="alice",
        image=SimpleNamespace(),
        public_material=lambda *a: None,
        practice=lambda *a: None,
    )
    name = _operation(
        meter,
        "operation-run",
        stdout=b"hello\n",
        stderr=b"Traceback (most recent call last):\nValueError: bad\n",
    )
    (meter.root / name / "snapshot").mkdir()
    spec = SimpleNamespace(
        action="run_python",
        arguments_json=canonical(
            {
                "source": "print(1)",
                "files": [],
                "hypothesis": "h",
                "expected_effect": "e",
            }
        ).decode(),
    )
    monkeypatch.setattr(
        research_tasks, "run_script", lambda *a, **k: {"operation": name, "files": {}}
    )
    result = executor._workspace_action(spec, "rtsk_" + "1" * 64)
    assert result["program_output"]["stdout_tail"] == "hello\n"
    assert "traceback" not in result["program_output"]

    from carbon.reconstruction.worker.model import WorkerCode

    def failing(*a, **k):
        raise MinerProgramFailure(
            {
                "schema": MINER_FAILURE_SCHEMA,
                "operation": name,
                "failure_code": WorkerCode.RUNTIME.value,
                "observation": "NONZERO_EXIT",
            }
        )

    monkeypatch.setattr(research_tasks, "run_script", failing)
    result = executor._workspace_action(spec, "rtsk_" + "2" * 64)
    assert result["outcome"] == "MINER_PROGRAM_FAILED"
    assert result["program_output"]["traceback"].endswith("ValueError: bad\n")


def test_a_run_julia_result_carries_its_output_and_its_error(tmp_path, monkeypatch):
    """run_julia on cpu returns what the program printed exactly as run_python
    does, and a failed run its Julia error from its first line."""
    from carbon.development_session import julia_analysis, research_tasks
    from carbon.development_session.research_carrier import (
        MINER_FAILURE_SCHEMA,
        MinerProgramFailure,
    )
    from carbon.reconstruction.worker.model import WorkerCode

    meter = CampaignLedger(tmp_path / "ledger")
    executor = research_tasks.PublicResearchExecutor(
        ledger=meter,
        owner="alice",
        image=SimpleNamespace(),
        public_material=lambda *a: None,
        practice=lambda *a: None,
    )
    # Admitting authored Julia is its own grant (test_authored_julia); only
    # what a run returns is under test here.
    executor.julia_image = SimpleNamespace(image_id="sha256:" + "7" * 64)
    error = b"ERROR: LoadError: UndefVarError: `x` not defined\nStacktrace:\n"
    name = _operation(meter, "operation-jl", stdout=b"loss 0.5\n", stderr=error)
    (meter.root / name / "snapshot").mkdir()
    spec = SimpleNamespace(
        action="run_julia",
        arguments_json=canonical(
            {
                "source": "println(1)",
                "files": [],
                "seconds": 60,
                "hypothesis": "h",
                "expected_effect": "e",
            }
        ).decode(),
    )
    ran = []

    def run_julia(ledger_, **kwargs):
        ran.append(kwargs)
        return {"operation": name, "files": {}}

    monkeypatch.setattr(julia_analysis, "run_julia", run_julia)
    result = executor._workspace_action(spec, "rtsk_" + "7" * 64)
    assert ran[0]["image"] is executor.julia_image
    assert result["program_output"] == {
        "stdout_tail": "loss 0.5\n",
        "stderr_tail": error.decode(),
    }

    def failing(ledger_, **kwargs):
        raise MinerProgramFailure(
            {
                "schema": MINER_FAILURE_SCHEMA,
                "operation": name,
                "failure_code": WorkerCode.RUNTIME.value,
                "observation": "NONZERO_EXIT",
            }
        )

    monkeypatch.setattr(julia_analysis, "run_julia", failing)
    failed = executor._workspace_action(spec, "rtsk_" + "8" * 64)
    assert failed["outcome"] == "MINER_PROGRAM_FAILED"
    assert failed["program_output"]["traceback"] == error.decode()


@pytest.mark.parametrize("rule", [None, TOOLS_RULE])
def test_read_file_returns_its_rules_encoding(tmp_path, rule):
    """The historical rule's read is exactly what it was: base64 alone, at
    most 4 KiB. v2 reads 8 KiB and returns the bytes once: text as text,
    anything else - or text that escapes larger than its base64 - as base64."""
    from carbon.development_session.research_tasks import (
        READ_FILE_MAX_BYTES,
        PublicResearchExecutor,
    )

    assert set(READ_FILE_MAX_BYTES) == {None, *research_tools.TOOLS_RULES}
    provider = None if rule is None else {"agent": "autonomous", "research_tools": rule}
    executor = PublicResearchExecutor(
        ledger=ledger(tmp_path / "ledger", provider=provider),
        owner="alice",
        image=SimpleNamespace(),
        public_material=lambda *a: None,
        practice=lambda *a: None,
    )
    limit = READ_FILE_MAX_BYTES[rule]
    files = {
        "notes.txt": b"loss = 0.25\n" * 2000,
        "accents.txt": ("é" * 8000).encode(),
        "data.bin": bytes(range(256)) * 64,
    }
    for name, body in files.items():
        executor.workspace.put(name, body)

    def read(name, offset, count):
        spec = SimpleNamespace(
            action="read_file",
            arguments_json=canonical(
                {"count": count, "name": name, "offset": offset}
            ).decode(),
        )
        return executor._workspace_action(spec, "rtsk_" + "3" * 64)

    with pytest.raises(ValueError, match="bounded byte range"):
        read("notes.txt", 0, limit + 1)
    text = read("notes.txt", 0, limit)
    if rule is None:
        assert limit == 4096
        assert set(text) == {"name", "digest", "bytes", "offset", "content_base64"}
        assert base64.b64decode(text["content_base64"]) == files["notes.txt"][:limit]
        return
    assert text["content_utf8"] == files["notes.txt"][:limit].decode()
    assert text["content_base64"] is None
    # Not UTF-8 (bytes, or a cut through a character), or text that escapes
    # to six bytes a character: base64, once.
    for name, offset in (("data.bin", 0), ("accents.txt", 1), ("accents.txt", 0)):
        value = read(name, offset, limit)
        assert value["content_utf8"] is None, name
        assert (
            base64.b64decode(value["content_base64"])
            == files[name][offset : offset + limit]
        )


# ---- 3. Each Challenge's registry, Burgers' by default.


def test_roadmap_capability_requests_and_demand_read_the_challenge(tmp_path):
    from carbon.development_session.capability_demand import (
        DemandStore,
        demanded,
        public_roadmap,
        wanted_ids,
    )
    from carbon.development_session.design_check import check_design
    from carbon.development_session.research_workspace import (
        capability_request_refusal,
    )

    battery = public_roadmap(None, BATTERY)
    ids = [
        item["id"]
        for section in ("available", "roadmap", "not_planned")
        for item in battery[section]
    ]
    assert sorted(ids) == sorted(
        c.capability_id for c in registry.contract(BATTERY).capabilities
    )
    assert battery["challenge"] == {"id": BATTERY, "version": "1.0"}
    # Burgers' roadmap is the default and keeps its historical form.
    assert public_roadmap() == public_roadmap(None, registry.BURGERS_CHALLENGE)
    assert "challenge" not in public_roadmap()
    burgers_ids = set(registry._BY_ID[registry.BURGERS_CHALLENGE])
    registered = sorted(set(registry._BY_ID[BATTERY]) - burgers_ids)
    assert registered, "an id battery registers and Burgers does not"
    request = {**CAPABILITY, "capability": registered[0]}
    assert capability_request_refusal(request, BATTERY) is None
    assert capability_request_refusal(request)[0] == "capability_id_unknown"
    # Research-only for battery, not for Burgers: counted only as battery's.
    only_battery = sorted(wanted_ids(BATTERY) - wanted_ids(None))
    assert only_battery
    demand = DemandStore(tmp_path / "demand.sqlite")
    assert (
        demand.record("miner", only_battery[:1], challenge=BATTERY) == only_battery[:1]
    )
    assert demand.record("miner", only_battery[:1]) == []
    # A battery design's verdict counts toward battery only.
    verdict = check_design(
        {
            "strategy": {
                "schema_version": "1.0",
                "challenge_id": BATTERY,
                "backbone": "mlp",
                "parameters": {},
            },
            "capabilities": only_battery[:1],
        }
    )
    assert demanded(verdict, BATTERY)[0] == only_battery[:1]
    assert demanded(verdict)[0] == []
    # A design naming an unknown Challenge names no ids, and is unrecognized.
    unknown = check_design(
        {
            "strategy": {
                "schema_version": "1.0",
                "challenge_id": SENTINEL,
                "backbone": "mlp",
                "parameters": {},
            }
        }
    )
    assert demanded(unknown, BATTERY) == ([], True)


def test_the_battery_composition_names_its_challenge():
    from carbon.battery import research as battery_research

    source = __import__("inspect").getsource(
        battery_research.make_battery_research_service
    )
    assert "composition.executor.challenge = BATTERY_CHALLENGE" in source
    from carbon.development_session.research_tasks import PublicResearchExecutor

    assert PublicResearchExecutor.challenge is None


# ---- Tools rule: historical tools unchanged, v2 read from the frozen plan.


def test_the_historical_tools_are_unchanged_and_v2_changes_text_only():
    # Graphite's roles digest these; a resumed campaign compares its plan.
    assert digest(canonical(TOOLS)) == HISTORICAL_TOOLS_DIGEST
    assert [t["name"] for t in TOOLS_V2] == [t["name"] for t in TOOLS]
    assert [t["parameters"] for t in TOOLS_V2] == [t["parameters"] for t in TOOLS]
    start = next(t for t in TOOLS_V2 if t["name"] == PREFIX + "start_research_task")
    text = start["description"]
    from carbon.development_session.research_tasks import READ_FILE_MAX_BYTES

    for phrase in (
        "device?: cpu (the default) or gpu",
        "../output",
        "program_output",
        "content_utf8",
        "count: 1 to " + str(READ_FILE_MAX_BYTES[TOOLS_RULE]) + "}",
        "stays in your context",
        "spends one research-trial slot",
        "expected_digest is the file's current digest",
        "REJECTED_BEFORE_DISPATCH",
        "nothing to poll",
    ):
        assert phrase in text, phrase


def test_tools_for_sdk_reads_the_rule_the_campaign_froze(tmp_path):
    assert tools_for_sdk(SimpleNamespace()) is TOOLS
    plain = SimpleNamespace(ledger=ledger(tmp_path / "plain"))
    assert tools_for_sdk(plain) is TOOLS
    frozen = SimpleNamespace(
        ledger=ledger(
            tmp_path / "v2",
            provider={"agent": "autonomous", "research_tools": TOOLS_RULE},
        )
    )
    assert tools_for_sdk(frozen) is TOOLS_V2
    assert tools_for_sdk(frozen, rule=None) is TOOLS
    unknown = SimpleNamespace(
        ledger=ledger(tmp_path / "unknown", provider={"research_tools": SENTINEL})
    )
    with pytest.raises(ValueError, match="unknown research tools rule"):
        tools_for_sdk(unknown)


def test_the_v2_julia_text_says_each_run_spends_a_slot():
    julia = research_tools._JULIA[TOOLS_RULE]
    assert "Each run_julia spends one research-trial slot" in julia
    assert "device=gpu runs only in current" in julia
    # The historical text is kept exactly.
    assert "spends" not in research_tools._JULIA[None]


def test_the_v2_surface_names_nothing_of_burgers():
    from test_agent_challenge_neutrality import burgers_terms

    surface = canonical([TOOLS_V2, research_tools._JULIA[TOOLS_RULE]]).decode()
    assert burgers_terms(surface) == []


# ---- 4/6. The battery agent's research environment, under the rule.


def gpu_worker():
    """A pinned GPU worker identity (its lock is the GPU profile's)."""
    from carbon.reconstruction.accelerators import GPU_PROFILE
    from carbon.reconstruction.worker.model import WorkerImageIdentity

    value = "sha256:" + "9" * 64
    return WorkerImageIdentity(
        image_id=value,
        config_digest=value,
        source_tree_digest="sha256:" + "a" * 64,
        wheel_digest="sha256:" + "b" * 64,
        lock_digest=GPU_PROFILE.environment_lock_digest,
        base_image_digest="sha256:" + "1" * 64,
        build_recipe_digest="sha256:" + "d" * 64,
        entrypoint_digest="sha256:" + "e" * 64,
    )


def battery_composition(path, provider, *, gpu_image=None, remote=None):
    """A real battery composition (`battery.campaign.compose`) over a frozen
    ledger whose run plan is `provider`. Only the authenticated gateway it
    wraps is a stand-in: nothing here is signed or dispatched."""
    from carbon.battery import campaign

    meter = ledger(path, provider=provider)
    context = object()
    gateway = SimpleNamespace(
        context=context,
        receiver="receiver",
        adapter=None,
        verifier=None,
        journal=SimpleNamespace(context=context),
        clock_ns=lambda: 0,
    )
    composition, _wrapper = campaign.compose(
        ledger=meter,
        owner="alice",
        image=SimpleNamespace(image_id="fixture-cpu", lock_digest=None),
        analysis=SimpleNamespace(image_id="fixture-analysis"),
        connection=SimpleNamespace(service=SimpleNamespace(gateway=gateway)),
        runner=lambda *a, **k: pytest.fail("practice ran"),
        backend={"kind": "TEST_ONLY"},
        gpu_image=gpu_image,
        remote=remote,
    )
    with meter.db() as db:
        row = db.execute("SELECT manifest FROM campaign WHERE id=1").fetchone()
    prepared = SimpleNamespace(manifest=json.loads(row[0]), composition=composition)
    return meter, composition, prepared


def test_the_battery_observation_states_the_gpu_lane_and_practice_backends(tmp_path):
    """Read from a real composition, so a renamed attribute fails here rather
    than reading as "cpu only"."""
    from carbon.battery import campaign

    def observed(path, rule, **lane):
        provider = {"agent": "autonomous"}
        if rule is not None:
            provider["research_tools"] = rule
        _, composition, prepared = battery_composition(path, provider, **lane)
        try:
            return campaign.agent_observation(prepared, 1, None)
        finally:
            composition.tasks.close()

    assert "research_environment" not in observed(tmp_path / "historical", None)
    cpu = observed(tmp_path / "cpu", TOOLS_RULE)["research_environment"]
    assert cpu["gpu_lane"] is None
    assert cpu["code_cell_devices"] == (
        "cpu only: this campaign was launched without a GPU lane, so "
        "run_python takes device=cpu (the default)"
    )
    assert cpu["practice_backends"] == ["jax"]
    assert (cpu["practice_device"], cpu["authored_julia"]) == ("cpu", False)
    local = observed(tmp_path / "gpu", TOOLS_RULE, gpu_image=gpu_worker())[
        "research_environment"
    ]
    assert local["gpu_lane"]["kind"] == "local_gpu"
    assert local["practice_device"] == "gpu"
    assert local["code_cell_devices"] == (
        "cpu (the default) or gpu: run_python takes device=gpu on the lane above"
    )
    remote = observed(
        tmp_path / "remote",
        TOOLS_RULE,
        gpu_image=gpu_worker(),
        remote=SimpleNamespace(
            transport=SimpleNamespace(name="ssh-docker", sandboxed=True)
        ),
    )["research_environment"]
    assert remote["gpu_lane"]["kind"] == "remote_gpu"
    assert remote["gpu_lane"]["actions"] == ["run_python"]


def test_the_code_cell_sentence_never_offers_more_than_the_lane_runs():
    """The sentence and the lane's own description agree: a remote lane runs
    run_python only, and run_julia is named only with authored Julia."""
    from carbon.battery.campaign import _code_cell_devices
    from carbon.development_session.gpu_code_cell import GpuLane

    local = GpuLane(image=gpu_worker()).describe()
    remote = GpuLane(
        image=gpu_worker(),
        remote=SimpleNamespace(transport=SimpleNamespace(name="x", sandboxed=True)),
    ).describe()
    assert _code_cell_devices(local, True) == (
        "cpu (the default) or gpu: run_python and run_julia take device=gpu on "
        "the lane above, run_julia in the lane's julia_environments only"
    )
    assert _code_cell_devices(remote, True) == (
        "cpu (the default) or gpu: run_python takes device=gpu on the lane "
        "above; run_julia runs on cpu only"
    )
    assert _code_cell_devices(None, True).endswith(
        "run_python and run_julia take device=cpu (the default)"
    )


def test_one_maximal_read_fits_beside_the_battery_agents_first_request(tmp_path):
    """A read as large as the v2 tool allows, done as the first call, must
    not end the epoch at the context admission ceiling.

    Built from the real battery composition, run plan, observation, prompt and
    tools, and the reply envelope the SDK returns as the model sees it
    (`research_loop.model_view`), carried in the history as a JSON string.
    Counted with no token anchor - every byte a token - which is the bound
    research_loop applies before a turn reports its tokens. The worst cases
    are text one third quotes (escaped twice, yet no larger than base64 once
    escaped, so it stays text) and bytes that come back as base64.
    """
    from carbon.battery import campaign
    from carbon.battery.challenge import CHALLENGE
    from carbon.development_session import miner_guidance
    from carbon.development_session.model_provider import DEFAULT_SELECTION
    from carbon.development_session.research_agent import CONTEXT_RESERVE_TOKENS
    from carbon.development_session.research_agent_policy import (
        AUTONOMOUS,
        STOP_TOOL,
        prompt_for,
    )
    from carbon.development_session.research_loop import SELECTION_TOOL, model_view
    from carbon.development_session.research_tasks import READ_FILE_MAX_BYTES

    # Fixture ceilings only: a battery plan needs finite ones to be built.
    plan = campaign.provider_plan(
        "autonomous",
        {"ceilings": {"provider_attempts": 96, "provider_nanodollars": 10**10}},
    )
    plan["research_tools"] = TOOLS_RULE
    meter, composition, prepared = battery_composition(tmp_path, plan)
    sdk = ResearchMinerTools(
        connection=None,
        wrapper=None,
        composition=composition,
        ledger=meter,
        owner="alice",
    )
    history = [
        {
            "role": "user",
            "content": canonical(
                campaign.agent_observation(prepared, 1, None)
            ).decode(),
        }
    ]
    request = {
        "model": DEFAULT_SELECTION.model_id,
        "instructions": prompt_for(AUTONOMOUS, CHALLENGE),
        "input": history,
        "tools": tools_for_sdk(sdk)
        + [SELECTION_TOOL, STOP_TOOL, miner_guidance.REPLY_TOOL],
        "parallel_tool_calls": False,
        "store": False,
        "max_output_tokens": DEFAULT_SELECTION.settings.max_output_tokens,
        "reasoning": {"effort": "low"},
    }
    # The campaign froze v2, so its agent is offered the v2 text.
    assert tools_for_sdk(sdk) is TOOLS_V2
    bound = DEFAULT_SELECTION.settings.max_input_tokens - CONTEXT_RESERVE_TOKENS
    limit = READ_FILE_MAX_BYTES[TOOLS_RULE]
    contents = {
        "plain.txt": (b"loss = 0.123456, step = 42\n" * 1000, "content_utf8"),
        "quotes.txt": (b'ab"' * 4000, "content_utf8"),
        "binary.bin": (bytes(range(256)) * 64, "content_base64"),
        "control.txt": (bytes(range(1, 32)) * 1000, "content_base64"),
    }
    try:
        for number, (name, (body, encoding)) in enumerate(contents.items()):
            assert len(body) >= limit
            composition.executor.workspace.put(name, body)
            args = workspace("read_file", {"count": limit, "name": name, "offset": 0})
            start = sdk._request(
                "start_research_task", args, f"lp-prod-d-maximal-{number:04d}"
            )
            reply = composition.service.call(
                research.ServiceCall(
                    research.RESEARCH_NAMESPACE, "start_research_task", start
                )
            )
            done = composition.tasks.run_queued_task(reply.result.task.task_id)
            envelope = {
                "protocol": research.RESEARCH_NAMESPACE,
                "operation": "start_research_task",
                "reply": research_tools.public_wire(reply),
                "terminal_task": research_tools.public_wire(done),
                "public_result": composition.executor.public_result(done),
                "requires_reconciliation": False,
            }
            result = envelope["public_result"]["result"]
            assert result[encoding] is not None, name
            call = {
                "type": "function_call",
                "id": "fc_" + "0" * 48,
                "call_id": "call_" + "0" * 24,
                "name": PREFIX + "start_research_task",
                "arguments": json.dumps(args),
                "status": "completed",
            }
            output = {
                "type": "function_call_output",
                "call_id": call["call_id"],
                "output": canonical(model_view(envelope)).decode(),
            }
            after = canonical({**request, "input": [*history, call, output]})
            assert len(after) <= bound, (name, len(after), bound)
    finally:
        composition.tasks.close()


# ---- 1 (door). A value refusal crosses the standard MCP door as refused.


def test_a_value_refusal_crosses_the_standard_mcp_door_as_refused(door):
    """Nothing started, so the door must say so: a refusal with its code,
    field and fix, not an invalid result that may have dispatched. The door
    verifies it with the builder's own rule (`correction_parts`, W1); until
    then this was a strict xfail against slice B's door."""
    from carbon.miner_mcp.standard import (
        AdapterCode,
        ResearchToolAdapter,
        ResearchToolRequest,
    )

    sdk, meter, _ = door
    adapter = ResearchToolAdapter(sdk, principal="alice")
    operation_id = "lp-prod-d-door-refusal-0001"
    try:
        result = asyncio.run(
            adapter.call(
                ResearchToolRequest(
                    "start_research_task",
                    operation_id,
                    {
                        "kind": "workspace",
                        "strategy": None,
                        "action": "read_file",
                        "arguments": {"name": "absent.txt", "offset": 0, "count": 1},
                        "hypothesis": "read my notes",
                        "expected_effect": "their content",
                    },
                )
            )
        )
    except AdapterFailure as failure:
        # What the door must stop doing: call a refusal that dispatched
        # nothing an invalid result that may have dispatched.
        assert failure.code is AdapterCode.INVALID_RESULT, failure.code
        assert meter.status(owner="alice")["used"]["research_trials"] == 0
        raise
    payload = result.payload
    assert payload["status"] == "REJECTED_BEFORE_DISPATCH"
    assert payload["correction_code"] == "workspace_file_missing"
    assert payload["field"].endswith(".name")
    assert "No file of that name" in payload["correction"]
    assert result.requires_reconciliation is False
    assert meter.status(owner="alice")["used"]["research_trials"] == 0
    assert sdk.composition.tasks.started_task(sdk.challenge, operation_id) is None


# ---- 7. The battery discovery document.


def test_the_battery_discovery_says_what_the_tools_take():
    from carbon import challenge_registry as challenges
    from carbon.development_session.design_check import check_design

    described = challenges.describe(
        BATTERY,
        "1.0",
        host=challenges.HostFacts(
            frozenset({"docker_cli", "trusted_worker_image", "jax", "optax"})
        ),
    )
    access = described["public_material"]["access"]
    assert 'arguments_json="{\\"name\\":\\"objective\\"}"' in access
    workflow = described["workflow"]
    assert workflow["validate"].startswith("check_design")
    for step in ("freeze", "submit"):
        assert "not a research tool" in workflow[step]
    text = json.dumps(workflow)
    assert "freeze_candidate" not in text and "battery_submit" not in text
    assert "returns once its task has finished" in workflow["progress"]
    assert "practice_backends" in described["execution"]
    # Every example is a design check_design takes as is.
    for example in described["examples"]:
        assert check_design(example)["verdict"] == "submittable"


# ---- 8. Argument normalisation, frozen with a new plan (LP-PROD-FIX-01).
#
# Smoke run 382c4276: Graphite's Planner sent strategy_json as the string
# "null" on kind=workspace, was told three ways to send JSON null, and never
# did. A campaign that freezes `ARGUMENT_NORMALISATION` reads that one value
# as JSON null; a campaign frozen before it refuses it exactly as before.

#: A Graphite plan as a new launch freezes it, and one frozen before the rule.
NORMALISING = {
    "agent": "graphite",
    "research_tools": TOOLS_RULE,
    "argument_normalisation": ARGUMENT_NORMALISATION,
}
FROZEN_BEFORE = {"agent": "graphite", "research_tools": TOOLS_RULE}


def null_strategy(action, arguments):
    """A workspace request whose strategy_json is the string "null"."""
    return {**workspace(action, arguments), "strategy_json": "null"}


def test_a_workspace_null_string_runs_under_the_frozen_rule(tmp_path):
    sdk, _meter, composition = sdk_for(tmp_path, provider=NORMALISING)
    try:
        sent = null_strategy("inventory", {})
        identity = "lp-prod-fix-null-0001"
        request = sdk._request("start_research_task", sent, identity)
        # The request JSON null builds, byte for byte; what was sent is kept.
        assert research.canonical_bytes(request) == research.canonical_bytes(
            sdk._request("start_research_task", workspace("inventory", {}), identity)
        )
        assert sent["strategy_json"] == "null"
        task = composition.tasks.start_research_task(request).task
        done = composition.tasks.run_queued_task(task.task_id)
        assert done.state is research.ResearchTaskState.SUCCEEDED
    finally:
        composition.tasks.close()


@pytest.mark.parametrize("provider", [None, "test-only", FROZEN_BEFORE])
def test_a_campaign_frozen_before_the_rule_refuses_null_as_before(tmp_path, provider):
    """No plan, a plan that is not an object, and a v2 plan frozen before
    the rule: each refuses as the historical code did, the same record."""
    sdk, meter, composition = sdk_for(tmp_path, provider=provider)
    try:
        assert campaign_argument_normalisation(meter) is None
        sent = null_strategy("inventory", {})
        result = refused(sdk, meter, sent)
        assert (result["correction_code"], result["field"]) == (
            "workspace_recipe_forbidden",
            "strategy_json",
        )
        assert result["correction"] == task_correction(
            "workspace_recipe_forbidden",
            "strategy_json",
            "null",
            tool="start_research_task",
        )
        # A resend under the same operation id is answered the same.
        assert refused(sdk, meter, sent) == result
    finally:
        composition.tasks.close()


@pytest.mark.parametrize(
    ("args", "code", "field"),
    [
        # kind=practice needs a recipe: "null" is still refused.
        (
            {
                "kind": "practice",
                "strategy_json": "null",
                "action": None,
                "arguments_json": None,
            },
            "practice_recipe_required",
            "strategy_json",
        ),
        (
            {
                "kind": "practice",
                "strategy_json": json.dumps({"backbone": "knn"}),
                "action": None,
                "arguments_json": "null",
            },
            "practice_recipe_required",
            "arguments_json",
        ),
        # A workspace arguments_json is required: null is never its value,
        # so "null" is not read as one.
        (
            {
                "kind": "workspace",
                "strategy_json": "null",
                "action": "inventory",
                "arguments_json": "null",
            },
            "json_object_required",
            "arguments_json",
        ),
    ],
)
def test_the_rule_normalises_nothing_else(tmp_path, args, code, field):
    sdk, meter, composition = sdk_for(tmp_path, provider=NORMALISING)
    try:
        sent = {
            **args,
            "hypothesis": "inspect the public inputs",
            "expected_effect": "a corrected request",
        }
        result = refused(sdk, meter, sent)
        assert (result["correction_code"], result["field"]) == (code, field)
    finally:
        composition.tasks.close()


def test_the_rule_is_read_from_the_frozen_plan_and_changes_no_tool(tmp_path):
    assert frozen_argument_normalisation({"provider": NORMALISING}) == (
        ARGUMENT_NORMALISATION
    )
    for manifest in ({}, {"provider": "test-only"}, {"provider": FROZEN_BEFORE}):
        assert frozen_argument_normalisation(manifest) is None
    with pytest.raises(ValueError, match="unknown argument normalisation rule"):
        frozen_argument_normalisation({"provider": {"argument_normalisation": "v9"}})
    # The tools a campaign is offered are the ones it froze, byte for byte,
    # with or without the rule: the rule changes no description or schema.
    for name, provider in (("new", NORMALISING), ("before", FROZEN_BEFORE)):
        sdk = SimpleNamespace(ledger=ledger(tmp_path / name, provider=provider))
        assert tools_for_sdk(sdk) is TOOLS_V2
    assert digest(canonical(TOOLS)) == HISTORICAL_TOOLS_DIGEST


#: canonical(TOOLS) as origin/main had it before LP-PROD-D; pinned so a
#: description change cannot slip into the frozen tools unnoticed.
HISTORICAL_TOOLS_DIGEST = (
    "sha256:1666c0e6eb1334b1d99e48a9ce9495327c7616878829bc141cca43497b329edc"
)
