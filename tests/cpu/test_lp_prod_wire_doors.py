"""W1: handoffs between the Launchpad production slices, wired
(OWNER-LAUNCHPAD-PROD-01).

Claims tested, each refusal paired with the same check passing:

- B<-D: every correction the research SDK's one builder can make crosses the
  standard MCP door, in object terms, for any research operation; the door
  verifies a correction with the builder's own rule, so a listed value on no
  closed list, a correction naming another tool, or text the builder did not
  make is never forwarded;
- B<->C: both doors read one catalog of next steps (`supervisor.NEXT_ACTIONS`)
  and the MCP door adds only the field to correct, so one code reads the same
  next step whichever door a miner uses;
- G->C: every closed code a submission through a validator intake can end
  with has its own next step in that catalog, never the fallback.

Fixtures only; no chain, provider, RunPod or network call.
"""

from __future__ import annotations

import asyncio
import io
import json
import sys
import urllib.error
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_lp_prod_mcp_door import real_sdk, run
from test_standard_mcp_adapter import make_adapter, workspace

from carbon import research
from carbon.development_session import research_tools
from carbon.development_session.research_tools import (
    PREFIX,
    TASK_CORRECTIONS,
    ResearchMinerTools,
    TaskContractMismatch,
    correction_choices,
    correction_parts,
    registered_correction,
    task_correction,
)
from carbon.miner_mcp import standard
from carbon.miner_mcp.standard import AdapterCode, AdapterFailure
from scripts.dev.miner_launchpad import supervisor as supervision

#: A value shaped like a choice (`research_tools._CHOICE`) that is on no
#: closed list: what a private identifier would look like.
UNLISTED = "hidden-case-0042"
#: Fields the builder may name, of each kind (`research_tools.registered_field`).
NAMED_FIELDS = ("strategy_json", "arguments_json", "arguments_json.name", "arguments")


def rejected(code, field, *, choices=(), tool=None, held=None):
    """A REJECTED_BEFORE_DISPATCH record as the SDK returns one."""
    return {
        "status": "REJECTED_BEFORE_DISPATCH",
        "reason": "contract_incompatibility",
        "detail": "Request rejected before dispatch",
        "authority_granted": False,
        "correction_code": code,
        "field": field,
        "correction": task_correction(code, field, held, choices=choices, tool=tool),
    }


# ---- B<-D: corrections cross the door, verified by the builder's rule.


def test_every_correction_the_builder_can_make_crosses_the_door():
    """The blocker: a correction naming its tool or listing its choices was
    INVALID_RESULT 'may have dispatched'. Every code, field kind, listed
    choice, tool and null variant the builder makes now crosses, restated in
    the object wire's terms."""
    crossed = 0
    for code in TASK_CORRECTIONS:
        listed = tuple(sorted(correction_choices(code)))
        for field in NAMED_FIELDS:
            for operation in ("start_research_task", "dry_validate"):
                for tool in (None, operation):
                    for held in (None, "null"):
                        record = rejected(
                            code, field, choices=listed, tool=tool, held=held
                        )
                        assert registered_correction(record)
                        payload, reconcile = standard._result(operation, record)
                        assert reconcile is False
                        assert payload["correction_code"] == code
                        assert payload["field"] == standard.object_wording(field)
                        text = payload["correction"]
                        assert "_json" not in text + payload["field"], text
                        assert "JSON string" not in text, text
                        assert "encoded as a string" not in text, text
                        if listed:
                            assert "Allowed here: " + ", ".join(listed) in text
                        crossed += 1
    assert crossed == len(TASK_CORRECTIONS) * len(NAMED_FIELDS) * 8


def test_a_listed_value_on_no_closed_list_never_crosses_the_door():
    good = rejected(
        "public_material_unknown", "arguments_json.name", choices=("objective",)
    )
    assert standard._result("start_research_task", good)[0]["correction_code"]
    forged = rejected(
        "public_material_unknown", "arguments_json.name", choices=(UNLISTED,)
    )
    assert correction_parts(forged) is None
    with pytest.raises(AdapterFailure) as refused:
        standard._result("start_research_task", forged)
    assert refused.value.code is AdapterCode.INVALID_RESULT
    assert UNLISTED not in str(refused.value)


def test_a_correction_naming_another_tool_never_crosses_the_door():
    own = rejected("tool_value_invalid", "arguments", tool="dry_validate")
    assert standard._result("dry_validate", own)[0]["correction_code"]
    with pytest.raises(AdapterFailure, match="INVALID_RESULT"):
        standard._result("start_research_task", own)


def test_the_sdk_lists_only_values_on_the_codes_closed_list():
    """The producer and the door read one rule (`correction_choices`)."""
    named = TaskContractMismatch(
        "public_material_unknown", "arguments_json.name", ("objective",)
    )
    assert named.choices == ("objective",)
    with pytest.raises(TypeError):
        TaskContractMismatch(
            "public_material_unknown", "arguments_json.name", (UNLISTED,)
        )
    # A code that lists nothing lists nothing.
    assert correction_choices("workspace_field_missing") == frozenset()
    with pytest.raises(TypeError):
        TaskContractMismatch("workspace_field_missing", "arguments_json", ("x",))


def test_the_closed_lists_hold_every_value_a_producer_lists():
    from carbon.development_session import gpu_code_cell
    from carbon.development_session.advection_research import PublicAdvectionMaterial
    from carbon.development_session.battery_gpu import BACKENDS
    from carbon.development_session.julia_depot import ENVIRONMENTS
    from carbon.development_session.julia_envelope import JuliaEnvelopeMaterial
    from carbon.development_session.julia_research import JuliaPublicMaterial
    from carbon.development_session.research_tasks import (
        NOTEBOOK_KINDS,
        READ_FILE_MAX_BYTES,
        public_material_names,
        reserved_stage_names,
    )

    materials = correction_choices("public_material_unknown")
    for service in (
        None,
        object.__new__(JuliaPublicMaterial),
        object.__new__(PublicAdvectionMaterial),
        object.__new__(JuliaEnvelopeMaterial),
    ):
        assert set(public_material_names(service)) <= materials
    # Battery's practice hosts serve JAX, and PyTorch where the image has it.
    assert set(BACKENDS) | {"jax", "pytorch"} <= correction_choices(
        "backend_not_served"
    )
    assert {str(n) for n in READ_FILE_MAX_BYTES.values()} == correction_choices(
        "read_file_range"
    )
    assert set(NOTEBOOK_KINDS) == correction_choices("notebook_kind_unknown")
    assert set(ENVIRONMENTS) == correction_choices("julia_environment_unknown")
    stages = correction_choices("run_files_invalid")
    for action in ("run_python", "run_julia"):
        assert reserved_stage_names(action) <= stages
    assert gpu_code_cell.WRAPPED in stages


def test_a_named_and_listed_correction_reaches_an_mcp_client(monkeypatch):
    from carbon.miner_mcp.standard_server import _create_server

    _, adapter = make_adapter()

    async def refuse(self, name, args, identity, **kwargs):
        # The SDK's own builder, as `_call` reaches it for a value refusal.
        return ResearchMinerTools.rejected(
            SimpleNamespace(_journal=lambda kind, body: None),
            "start_research_task",
            args,
            identity,
            correction="public_material_unknown",
            field="arguments_json.name",
            choices=("objective", "capabilities"),
            tool="start_research_task",
        )

    monkeypatch.setattr(ResearchMinerTools, "call", refuse)
    server = _create_server(adapter)
    result = asyncio.run(
        server.call_tool(
            PREFIX + "start_research_task",
            {
                **workspace("public_material", {"name": "nothing-public"}),
                "operation_id": "w1-listed-correction-0001",
            },
        )
    )
    assert not result.is_error, result.content
    payload = result.structured_content["payload"]
    assert payload["status"] == "REJECTED_BEFORE_DISPATCH"
    assert payload["correction_code"] == "public_material_unknown"
    assert payload["field"] == "arguments.name"
    assert "Allowed here: objective, capabilities." in payload["correction"]
    assert "The tool: start_research_task." in payload["correction"]
    assert "nothing-public" not in json.dumps(payload)
    assert result.structured_content["requires_reconciliation"] is False


def test_a_correction_of_another_research_operation_reaches_the_client(
    tmp_path, monkeypatch
):
    """Not only start_research_task: the real SDK's catch-all names the tool
    it refused, and the door forwards it as a refusal that started nothing."""

    def refusing(*args):
        raise TypeError("PRIVATE-CONSTRUCTOR-TEXT")

    monkeypatch.setattr(research, "DryValidateRequest", refusing)
    _, adapter, meter = real_sdk(tmp_path)
    result = run(
        adapter, "dry_validate", {"strategy": {"backbone": "knn", "parameters": {}}}
    )
    payload = result.payload
    assert payload["status"] == "REJECTED_BEFORE_DISPATCH"
    assert (payload["correction_code"], payload["field"]) == (
        "tool_value_invalid",
        "arguments",
    )
    assert "The tool: dry_validate." in payload["correction"]
    assert "PRIVATE" not in json.dumps(payload)
    assert result.requires_reconciliation is False
    assert meter.status(owner="alice")["used"]["research_trials"] == 0


# ---- B<->C: one catalog of next steps for both doors.


def test_the_mcp_doors_refusal_is_the_catalogs_step_for_every_code():
    from carbon.miner_mcp.mcp_operations import ATTACHMENT_REFUSALS, _attachment_refusal
    from scripts.dev.miner_launchpad.operations import (
        FIELDS as REQUEST_FIELDS,
    )
    from scripts.dev.miner_launchpad.operations import (
        REFUSAL_FIELDS,
        refusal,
    )

    # Every code this door names a field for, and every attachment refusal,
    # has its own step in the catalog; every field named is a request field.
    assert set(REFUSAL_FIELDS) <= set(supervision.NEXT_ACTIONS)
    assert ATTACHMENT_REFUSALS <= set(supervision.NEXT_ACTIONS)
    assert set(REFUSAL_FIELDS.values()) <= set(REQUEST_FIELDS)
    for code, step in supervision.NEXT_ACTIONS.items():
        body = refusal(code)
        assert body["next_step"] == step, code
        assert body.get("field") == REFUSAL_FIELDS.get(code), code
    for code in ATTACHMENT_REFUSALS:
        assert json.loads(_attachment_refusal(code)) == refusal(code)
    # A code the catalog does not name is still answered, with its fallback.
    assert refusal("a_code_from_a_later_slice") == {
        "error": "a_code_from_a_later_slice",
        "next_step": supervision.FALLBACK_ACTION,
    }


def test_the_catalog_names_only_closed_codes_with_fixed_steps():
    for code, step in supervision.NEXT_ACTIONS.items():
        assert supervision._CODE.fullmatch(code), code
        assert type(step) is str and step.strip() == step and step.endswith("."), code
    assert supervision.catalog()["next_actions"] == supervision.NEXT_ACTIONS


# ---- G->C: an intake's refusal reaches the miner with its own next step.


def intake_codes():
    """Every closed code a submission through a validator intake can end with:
    the intake's and its transport's (`intake_client.REFUSALS`, which
    `campaign.intake_code` maps everything else into), the outcome classes
    `campaign` names, and the refusal before any intake is configured."""
    from carbon.battery import campaign, intake_client

    return (
        set(intake_client.REFUSALS)
        | campaign.INTAKE_QUEUED
        | campaign.INTAKE_UNAVAILABLE
        | {"evaluation_unavailable"}
    )


def test_every_closed_code_an_intake_submission_reports_has_its_own_step():
    codes = intake_codes()
    missing = sorted(code for code in codes if code not in supervision.NEXT_ACTIONS)
    assert not missing, missing
    for code in codes:
        entry = supervision.refusal(code, operation="submit")
        # Kept as the closed code it is, never folded into operation_refused.
        assert entry["code"] == code
        assert entry["next_action"] == supervision.NEXT_ACTIONS[code]
        assert entry["next_action"] != supervision.FALLBACK_ACTION


def test_the_intake_path_reports_only_codes_in_that_set():
    """`campaign.intake_code` and `_failure_code` close the set the test above
    covers: an unknown answer, a transport failure and a signer that did not
    sign each land on a listed code."""
    from carbon.battery import campaign
    from carbon.battery.intake_client import IntakeMismatch
    from carbon.chain.external_signer import SignerCode, SignerFailure

    codes = intake_codes()
    assert campaign.intake_code("http_502") == "intake_answer_unrecognised"
    assert campaign.intake_code("AUTH_STALE") == "AUTH_STALE"

    def http_error(body):
        return urllib.error.HTTPError(
            "http://127.0.0.1:9/carbon/v1/intake", 429, "refused", {}, io.BytesIO(body)
        )

    failures = {
        SignerFailure(next(iter(SignerCode))): "signer_unavailable",
        IntakeMismatch("not a battery intake"): "intake_mismatch",
        ConnectionRefusedError(): "intake_unreachable",
        http_error(b'{"refused": "rate"}'): "rate",
        http_error(b'{"refused": "a-new-code"}'): "intake_answer_unrecognised",
        http_error(b"<html>Bad Gateway</html>"): "intake_unreachable",
        KeyError("snapshot"): "intake_answer_unrecognised",
    }
    for failure, code in failures.items():
        assert campaign._failure_code(failure) == code
        assert code in codes


def test_the_door_verifies_with_the_builders_own_rule():
    """The door imports the builder's verifier rather than holding its own."""
    assert standard.correction_parts is research_tools.correction_parts
