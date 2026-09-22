"""What the research server needs before a real client depends on it.

Per-call records, a concurrency bound, a queue deadline, refusals a client can
branch on, a versioned surface catalogue, and a caller identity that comes from
the campaign rather than from the call.

Two properties get the most attention here, because both are the kind that look
fine until they are not.

The first is that a record cannot contain the miner's work. Not by convention -
`call_record` has no parameter for arguments, so no call site can pass one.
Asserted on the signature, so a future edit that adds one fails here rather than
in a log file someone reads a year later.

The second is that the per-call budget does not cancel a running call.
Cancelling an in-flight `adapter.call` would abandon a ledger reservation whose
outcome nobody knows, which is the `requires_reconciliation` state the campaign
model exists to prevent - so a transport timeout would manufacture the failure
it was added to contain. The test proves the call still finishes.
"""

import asyncio
import inspect
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_standard_mcp_adapter import make_adapter

from carbon.miner_mcp import serving
from carbon.miner_mcp.standard import (
    AdapterCode,
    AdapterFailure,
    ResearchToolResult,
)
from carbon.miner_mcp.standard_server import PREFIX, _create_server

OPERATION_ID = "external-operation-0001"
HYPOTHESIS = "a hypothesis the miner would not want written to a log"


def build(*, capacity=None, answer=None):
    """A server whose adapter answers however a test needs it to."""
    records = []
    _sdk, adapter = make_adapter()

    async def call(request):
        if answer is not None:
            return await answer(request)
        return ResearchToolResult(
            operation=request.operation,
            operation_id=request.operation_id,
            payload={"status": "OK"},
            requires_reconciliation=False,
            official_eligible=False,
        )

    adapter.call = call
    server = _create_server(adapter, capacity=capacity, record_sink=records.append)
    return server, records


def invoke(server, operation="get_challenge_info", **arguments):
    return asyncio.run(
        server.call_tool(
            PREFIX + operation, {"operation_id": OPERATION_ID, **arguments}
        )
    )


# --- records -----------------------------------------------------------------


def test_a_successful_call_is_recorded():
    server, records = build()
    invoke(server)

    assert len(records) == 1
    record = records[0]
    assert record["schema"] == serving.SCHEMA
    assert record["operation"] == "get_challenge_info"
    assert record["outcome"] == "OK"
    assert record["principal"] == "alice"
    assert record["duration_ms"] >= 0


def test_call_record_has_no_parameter_for_arguments():
    """Absent, not omitted.

    A convention of not passing the arguments is a convention someone breaks.
    There is no parameter to pass them to, so breaking it means changing this
    signature, which fails here.
    """
    parameters = set(inspect.signature(serving.call_record).parameters)
    assert parameters == {
        "operation",
        "principal",
        "operation_id",
        "outcome",
        "duration_ms",
        "reason",
    }
    for forbidden in ("arguments", "payload", "strategy", "hypothesis", "request"):
        assert forbidden not in parameters


def test_a_miners_work_never_reaches_a_record():
    """The reason arguments are excluded, stated as the property it protects.

    A research argument carries the miner's hypothesis, their strategy and their
    file contents. That is what they came here to keep.
    """
    server, records = build()
    invoke(
        server,
        operation="start_research_task",
        kind="workspace",
        strategy=None,
        action="inventory",
        arguments={"secret_parameter": 12345},
        hypothesis=HYPOTHESIS,
        expected_effect="something measurable",
    )

    rendered = json.dumps(records)
    assert HYPOTHESIS not in rendered
    assert "secret_parameter" not in rendered
    assert "12345" not in rendered
    assert records[0]["arguments"] == "NOT_RECORDED"


def test_the_operation_id_is_recorded_only_as_a_digest():
    """Retries still correlate; no caller-controlled bytes are stored."""
    server, records = build()
    invoke(server)
    invoke(server)

    assert OPERATION_ID not in json.dumps(records)
    assert records[0]["operation_digest"] == records[1]["operation_digest"]
    assert records[0]["operation_digest"] != serving.operation_digest("different")


# --- the caller identity comes from the campaign, not the call ---------------


def test_a_principal_cannot_be_supplied_by_a_caller():
    """Section 9 case 7, enforced by construction rather than by checking.

    `BoundPrincipal` takes an adapter, and the adapter re-verifies its owner
    binding on the way. A string is not a weaker path to the same value, it is a
    refusal that names the mistake rather than a bare AttributeError from the
    generic branch.
    """
    with pytest.raises(TypeError, match="not\n?.*from a caller-supplied identity"):
        serving.BoundPrincipal("alice")


def test_a_record_refuses_a_raw_string_even_when_the_value_is_correct():
    """The check that tells whether construction-enforcement was achieved.

    Nothing is wrong with this value. It is refused because it did not come
    through validation, which is exactly what a check at the point of use cannot
    establish.
    """
    _sdk, adapter = make_adapter()
    genuine = str(serving.BoundPrincipal(adapter))
    assert genuine == "alice"

    with pytest.raises(TypeError, match="requires a BoundPrincipal"):
        serving.call_record(
            "get_prior",
            principal=genuine,
            operation_id=OPERATION_ID,
            outcome="OK",
            duration_ms=1,
        )


def test_the_recorded_principal_tracks_the_campaign_owner():
    _sdk, adapter = make_adapter(owner="bob")
    assert serving.BoundPrincipal(adapter) == "bob"


# --- refusals ----------------------------------------------------------------


def test_a_refusal_carries_a_stable_slug_and_the_next_step():
    from mcp.server.mcpserver.exceptions import ToolError

    async def refuse(_request):
        raise AdapterFailure(
            AdapterCode.OPERATIONAL_STOP, dispatch_may_have_occurred=False
        )

    server, records = build(answer=refuse)
    with pytest.raises(ToolError) as raised:
        invoke(server)

    message = str(raised.value)
    assert "OPERATIONAL_STOP" in message
    assert "dispatch_may_have_occurred=false" in message
    assert "next_action=" in message
    assert serving.NEXT_ACTION["OPERATIONAL_STOP"] in message

    assert records[0]["outcome"] == "REFUSED"
    assert records[0]["reason"] == "OPERATIONAL_STOP"


def test_every_refusal_slug_has_a_next_action():
    """A slug without a next step tells a client what happened and not what now."""
    for code in AdapterCode:
        assert serving.NEXT_ACTION[code.value].strip()


def test_a_refusal_never_carries_a_provider_message():
    """Fixed text per slug: provider text is how internal detail reaches a wire."""
    for action in serving.NEXT_ACTION.values():
        assert "Traceback" not in action and "Error:" not in action


# --- capacity ----------------------------------------------------------------


def test_the_queue_deadline_refuses_without_dispatching():
    """The only point at which a deadline can refuse safely.

    Nothing has been reserved yet, so a refusal costs the caller a retry and
    leaves no reservation whose outcome nobody knows.
    """
    from mcp.server.mcpserver.exceptions import ToolError

    started = asyncio.Event()
    dispatched = []

    async def slow(request):
        dispatched.append(request.operation)
        started.set()
        await asyncio.sleep(5)

    capacity = serving.Capacity(limit=1, queue_deadline=0.05, budget=900)
    server, records = build(capacity=capacity, answer=slow)

    async def scenario():
        first = asyncio.create_task(
            server.call_tool(PREFIX + "get_prior", {"operation_id": OPERATION_ID})
        )
        await started.wait()
        with pytest.raises(ToolError) as raised:
            await server.call_tool(
                PREFIX + "get_prior", {"operation_id": "second-operation-000002"}
            )
        first.cancel()
        return str(raised.value)

    message = asyncio.run(scenario())
    assert "CAPACITY_UNAVAILABLE" in message
    assert "dispatch_may_have_occurred=false" in message
    assert len(dispatched) == 1, "the refused call was never dispatched"

    refused = [r for r in records if r["outcome"] == "CAPACITY_UNAVAILABLE"]
    assert len(refused) == 1 and refused[0]["duration_ms"] == 0


def test_the_budget_records_an_overrun_and_does_not_cancel_the_call():
    """The most important decision in this module, asserted rather than trusted.

    Cancelling an in-flight call would abandon a ledger reservation whose
    outcome nobody knows - the reconciliation-required state the campaign model
    exists to prevent. So the call finishes and the overrun is recorded.
    """
    finished = []

    async def slow(request):
        await asyncio.sleep(0.05)
        finished.append(request.operation)
        return ResearchToolResult(
            operation=request.operation,
            operation_id=request.operation_id,
            payload={"status": "OK"},
            requires_reconciliation=False,
            official_eligible=False,
        )

    capacity = serving.Capacity(limit=2, queue_deadline=5, budget=0.001)
    server, records = build(capacity=capacity, answer=slow)
    invoke(server, operation="get_prior")

    assert finished == ["get_prior"], "the call was cancelled to meet a budget"
    assert records[0]["outcome"] == "OVERRAN"


def test_a_concurrency_bound_below_one_is_refused():
    with pytest.raises(ValueError):
        serving.Capacity(limit=0)


def test_capacity_is_released_after_a_refusal():
    """A refused call must not permanently consume a slot."""
    from mcp.server.mcpserver.exceptions import ToolError

    async def refuse(_request):
        raise AdapterFailure(
            AdapterCode.INVALID_ARGUMENT, dispatch_may_have_occurred=False
        )

    capacity = serving.Capacity(limit=1, queue_deadline=0.05, budget=900)
    server, _records = build(capacity=capacity, answer=refuse)

    for _attempt in range(3):
        with pytest.raises(ToolError) as raised:
            invoke(server, operation="get_prior")
        assert "INVALID_ARGUMENT" in str(raised.value)


# --- the versioned catalogue -------------------------------------------------


def catalogue_of(server):
    return json.loads(
        asyncio.run(server.read_resource(serving.CATALOGUE_URI))[0].content
    )


def test_the_catalogue_describes_the_surface_and_its_version():
    server, _records = build()
    catalogue = catalogue_of(server)

    assert catalogue["schema"] == serving.CATALOGUE
    assert catalogue["sdk_version"] == "2.2.0"
    assert PREFIX + "get_prior" in catalogue["operations"]
    assert serving.CATALOGUE_URI in catalogue["resources"]
    assert catalogue["official_eligible"] is False


def test_the_catalogue_publishes_the_bounds_a_client_must_plan_around():
    server, _records = build()
    limits = catalogue_of(server)["limits"]

    assert limits["max_concurrent_calls"] == serving.MAX_CONCURRENT_CALLS
    assert limits["queue_deadline_seconds"] == serving.QUEUE_DEADLINE_SECONDS
    assert limits["call_budget_enforcement"] == "RECORDED_NOT_CANCELLED"
    assert "reconciliation" in limits["call_budget_note"]


def test_the_catalogue_states_that_arguments_are_not_recorded():
    """A miner should be able to read what is kept about them, not infer it."""
    server, _records = build()
    records = catalogue_of(server)["records"]
    assert records["arguments_recorded"] is False
    assert records["schema"] == serving.SCHEMA


def test_the_catalogue_publishes_every_refusal_slug():
    server, _records = build()
    refusals = catalogue_of(server)["refusals"]
    for code in AdapterCode:
        assert refusals[code.value]["next_action"]
    assert refusals["CAPACITY_UNAVAILABLE"]["next_action"]


def test_the_catalogue_is_separate_from_the_scientific_capabilities():
    """A surface change and a science change must be distinguishable."""
    server, _records = build()
    from carbon.miner_mcp.standard_server import CAPABILITIES_URI

    assert serving.CATALOGUE_URI != CAPABILITIES_URI
    capabilities = json.loads(
        asyncio.run(server.read_resource(CAPABILITIES_URI))[0].content
    )
    assert capabilities != catalogue_of(server)
