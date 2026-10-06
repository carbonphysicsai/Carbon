"""A ledger refusal is typed by whose limit it is (RESEARCH-BUDGET-REFUSAL-TYPING-01).

On 2026-10-05 a campaign whose own `research_trials` ceiling was used up got
its next practice tasks back as FAILED_INFRA / INTERNAL, which reads exactly
like a worker crash. These tests hold the fix:

- the ledger raises `LedgerRefusal`, a ValueError with the historical text,
  for each limit on its reserve path, with the dimension and counts;
- the durable task provider completes a task the campaign's own ceiling
  refused with outcome MINER_CEILING_REACHED and that record, never as an
  infrastructure failure; Carbon's service capacity stays infrastructure
  (RESOURCE_LIMIT); every other exception stays INTERNAL exactly as before;
- a miner who sets no ceiling on a dimension is never refused on it.

Synthetic fixtures only; no model, network or numerical evidence.
"""

from dataclasses import replace
from types import SimpleNamespace

import pytest
from b07b_fixtures import make_fixture
from test_product_campaign_ledger import (
    CHILDREN,
    HOTKEY,
    OWNER,
    SCOPE_DOCUMENT,
    manifest,
    snapshot,
)

from carbon import research
from carbon.agent_campaign.graphite.miner import budget
from carbon.development_session import research_loop
from carbon.development_session.chain_onboarding import PublicAddress, RegisteredMiner
from carbon.development_session.product_campaign import ProductLaunch, miner_budget
from carbon.development_session.profile import canonical
from carbon.development_session.research_control import (
    CampaignControl,
    CampaignDeadlineReached,
    DispatchStopped,
)
from carbon.development_session.research_ledger import (
    CARBON_SERVICE_CAPACITY,
    DIMENSIONS,
    MINER_CEILING_REACHED,
    NO_BUDGET,
    SERVICE_LIMITS,
    VERSION,
    CampaignLedger,
    LedgerRefusal,
    _caps,
)
from carbon.development_session.research_tasks import (
    CEILING_OUTCOME,
    PublicDevelopmentResearchTasks,
    PublicResearchExecutor,
)
from carbon.research.model import InfrastructureFailureClass

State = research.ResearchTaskState


def product(path, clock=None, **changes):
    path.mkdir(mode=0o700, exist_ok=True)
    ledger = CampaignLedger(path / "campaign", clock=clock or (lambda: 1000))
    ledger.generation = CampaignControl(ledger).acquire()
    ledger.freeze(manifest(**changes))
    return ledger


def reserve(ledger, identity, resources, *, settle=True):
    out = ledger.reserve(
        identity,
        owner=OWNER,
        phase="research",
        request={"id": identity},
        resources=resources,
    )
    if settle and out["dispatch"]:
        ledger.finish(
            identity,
            owner=OWNER,
            state="SUCCEEDED",
            actual=resources,
            result={"ok": True},
        )
    return out


# --- the ledger's typed refusal ----------------------------------------------


@pytest.mark.parametrize(
    "dimension,each",
    [
        ("research_trials", 1),
        ("provider_nanodollars", 400),
        ("provider_attempts", 1),
        ("epochs", 1),
    ],
)
def test_a_miner_ceiling_refusal_is_typed_with_its_counts(tmp_path, dimension, each):
    ledger = product(tmp_path, ceilings={dimension: 3 * each})
    for n in range(3):
        reserve(ledger, f"op-{n}", {dimension: each})
    with pytest.raises(LedgerRefusal) as refused:
        reserve(ledger, "op-3", {dimension: each})
    error = refused.value
    # The historical text and base type: every text reader reads as before.
    assert isinstance(error, ValueError)
    assert str(error) == "miner budget: " + dimension
    assert error.record() == {
        "code": MINER_CEILING_REACHED,
        "dimension": dimension,
        "basis": "miner_launch_budget",
        "used": 3 * each,
        "requested": each,
        "ceiling": 3 * each,
        "refused_at": "reservation",
    }
    # Nothing of the refused reservation was recorded.
    assert ledger.operation_state("op-3", owner=OWNER) is None


def test_retained_bytes_and_service_capacity_are_typed_apart(tmp_path):
    ledger = product(tmp_path, ceilings={"retained_bytes": 1024**2})
    with pytest.raises(LedgerRefusal) as stored:
        ledger.check_storage(1)
    assert str(stored.value) == "miner budget: retained_bytes"
    assert stored.value.code == MINER_CEILING_REACHED
    assert stored.value.refused_at == "storage_check"
    assert stored.value.ceiling == 1024**2

    other = product(tmp_path / "service")
    limit = SERVICE_LIMITS["reference_invocations"]
    reserve(other, "fill", {"reference_invocations": limit})
    with pytest.raises(LedgerRefusal) as capacity:
        reserve(other, "over", {"reference_invocations": 1})
    assert str(capacity.value) == "carbon service capacity: reference_invocations"
    assert capacity.value.code == CARBON_SERVICE_CAPACITY
    assert capacity.value.basis == "carbon_service"


def test_a_sequence_aggregate_refusal_is_typed(tmp_path):
    """A sequence can fit child by child and not as a whole; its aggregate
    refusal keeps its own text and carries the same record."""
    ledger = product(tmp_path, ceilings={"reference_invocations": 3})
    with pytest.raises(LedgerRefusal) as refused:
        ledger.reserve_sequence(
            "sequence", owner=OWNER, scope=SCOPE_DOCUMENT, children=CHILDREN
        )
    assert (
        str(refused.value) == "miner budget, sequence aggregate: reference_invocations"
    )
    assert (refused.value.used, refused.value.requested, refused.value.ceiling) == (
        0,
        4,
        3,
    )


def test_elapsed_time_is_typed_but_a_regressed_clock_is_not(tmp_path):
    """The ledger's own time check (an uncontrolled campaign reaches it)."""
    clock = [1000.0]
    ledger = product(
        tmp_path, clock=lambda: clock[0], schema=VERSION, elapsed_seconds=60
    )
    reserve(ledger, "first", {"research_trials": 1})
    clock[0] = 1061.0
    with pytest.raises(LedgerRefusal) as late:
        reserve(ledger, "late", {"research_trials": 1})
    assert str(late.value) == "campaign elapsed-time exhausted or clock regressed"
    assert (
        late.value.dimension,
        late.value.ceiling,
        late.value.used,
        late.value.basis,
    ) == ("elapsed_seconds", 60, 61, "development_campaign")
    clock[0] = 999.0
    with pytest.raises(ValueError, match="clock regressed") as regressed:
        reserve(ledger, "back", {"research_trials": 1})
    assert type(regressed.value) is ValueError


def test_campaign_controls_deadline_carries_the_same_typed_record(tmp_path):
    """A controlled campaign meets its time first in campaign control's
    checkpoint: still a DispatchStopped with its historical text."""
    clock = [1000.0]
    ledger = product(tmp_path, clock=lambda: clock[0], elapsed_seconds=60)
    reserve(ledger, "first", {"research_trials": 1})
    clock[0] = 1070.0
    with pytest.raises(DispatchStopped) as stopped:
        reserve(ledger, "late", {"research_trials": 1})
    assert type(stopped.value) is CampaignDeadlineReached
    assert str(stopped.value) == "original campaign deadline reached"
    assert stopped.value.refusal.record() == {
        "code": MINER_CEILING_REACHED,
        "dimension": "elapsed_seconds",
        "basis": "miner_launch_budget",
        "used": 70,
        "requested": 0,
        "ceiling": 60,
        "refused_at": "reservation",
    }


def test_text_readers_still_read_the_typed_refusal():
    """The research loop's and Graphite's readers accepted only an exact
    ValueError; they read the typed refusal exactly as they read it."""
    typed = LedgerRefusal(
        "miner budget: provider_attempts",
        code=MINER_CEILING_REACHED,
        dimension="provider_attempts",
    )
    stop = research_loop.miner_ceiling(typed, reserving=True)
    assert (stop.code, stop.dimension) == (MINER_CEILING_REACHED, "provider_attempts")
    assert budget.reserve_limit(typed) == "provider_attempts"
    timed = LedgerRefusal(
        "campaign elapsed-time exhausted or clock regressed",
        code=MINER_CEILING_REACHED,
        dimension="elapsed_seconds",
    )
    assert budget.reserve_limit(timed) == "elapsed_seconds"


# --- a miner who sets no ceiling is never refused on it ----------------------


@pytest.mark.parametrize("spelling", ["absent", "null", "no budget"])
def test_a_dimension_the_miner_left_unset_never_refuses(tmp_path, spelling):
    """Every dimension a miner may leave unset admits far past every
    development figure. Carbon's own service capacity (reference_*) is the
    only bound, and it is reported as Carbon's, never as the miner's."""
    if spelling == "no budget":
        budget_set = miner_budget(None)
        assert budget_set == {}
    elif spelling == "null":
        budget_set = miner_budget({"ceilings": dict.fromkeys(DIMENSIONS)})
    else:
        budget_set = miner_budget({"ceilings": {}})
    ledger = product(tmp_path, **budget_set)
    # Unset and null both read as NO_BUDGET; nothing supplies a number.
    assert all(cap is NO_BUDGET for cap in _caps(manifest(**budget_set)).values())
    assert "elapsed_seconds" not in budget_set
    big = {
        "epochs": 1000,
        "research_trials": 1000,
        "final_replicas": 1000,
        "provider_attempts": 1000,
        "provider_nanodollars": 10**15,
        "numerical_milliseconds": 10**9,
        "retained_bytes": 10**13,
    }
    for dimension, amount in big.items():
        for n in range(3):
            reserve(ledger, f"{dimension}-{n}", {dimension: amount})
    for dimension, service in SERVICE_LIMITS.items():
        reserve(ledger, dimension, {dimension: service})
    assert ledger.status(owner=OWNER)["used"]["research_trials"] == 3000


def test_a_launch_records_only_the_budget_the_miner_set():
    """The product launch carries the miner's budget exactly, or none: no
    Carbon figure is supplied for a dimension they left unset."""
    miner = RegisteredMiner(snapshot(HOTKEY), PublicAddress(HOTKEY))
    runtime = {"implementation": "fixture", "images": []}

    def launch(value):
        return ProductLaunch(
            "cmp-fixture", "alice", miner, runtime, miner_budget(value), agent="none"
        ).manifest_fields()

    budget_keys = {"ceilings", "elapsed_seconds", "final_reserve"}
    assert not budget_keys & set(launch(None))
    assert launch({"ceilings": {"research_trials": 3}})["ceilings"] == {
        "research_trials": 3
    }
    assert "elapsed_seconds" not in launch({"ceilings": {"research_trials": 3}})


# --- the durable task provider types the refusal -----------------------------


def compose(tmp_path, ledger, material):
    fixture = make_fixture(tmp_path / "fixtures")
    p = fixture.provider
    executor = PublicResearchExecutor(
        ledger=ledger,
        owner=OWNER,
        image=SimpleNamespace(),
        public_material=material,
        practice=lambda *args: (_ for _ in ()).throw(AssertionError("not practice")),
    )
    provider = PublicDevelopmentResearchTasks(
        root=tmp_path / "tasks",
        requester=OWNER,
        challenge_catalog_provider=p._catalog,
        manifest_provider=p._manifests,
        compilation_resolver=p._compiler,
        prior_resolver=p._priors,
        resource_resolver=p._resources,
        executor=executor,
        task_queue=p._queue,
        clock=p._clock,
        worker_implementation_digest=p._worker_digest,
        environment_digest=p._environment_digest,
    )
    executor.request_resolver = provider.request_for_execution
    return fixture, provider, executor


def run(fixture, provider, index):
    req = replace(
        fixture.request(),
        idempotency_key="budget-typing-task-" + str(index),
        task_spec=research.DevelopmentWorkspaceTaskSpecV1(
            "carbon.autoresearch.workspace.v1",
            "public_material",
            canonical({"name": "objective"}).decode(),
        ),
    )
    task = provider.start_research_task(req).task
    return provider.run_queued_task(task.task_id)


def charging(ledger, resources):
    """A material service that reserves on the campaign ledger, as a practice
    does, so the ledger's own refusal crosses the real executor path."""
    count = [0]

    def material(name, workspace):
        count[0] += 1
        reserve(ledger, f"work-{count[0]}", resources)
        return {"name": name, "scope": "SYNTHETIC_ENGINEERING_TEST"}

    return material


@pytest.mark.parametrize(
    "dimension,each", [("research_trials", 1), ("provider_nanodollars", 7)]
)
def test_a_task_refused_by_the_miners_ceiling_is_typed_not_infra(
    tmp_path, dimension, each
):
    ledger = product(tmp_path, ceilings={dimension: each})
    f, p, e = compose(tmp_path, ledger, charging(ledger, {dimension: each}))
    assert run(f, p, 0).state is State.SUCCEEDED
    done = run(f, p, 1)
    assert done.state is State.SUCCEEDED
    assert done.terminal_receipt.infrastructure_failure_class is None
    result = e.public_result(done)["result"]
    assert result["outcome"] == CEILING_OUTCOME
    assert (result["code"], result["dimension"], result["basis"]) == (
        MINER_CEILING_REACHED,
        dimension,
        "miner_launch_budget",
    )
    assert (result["used"], result["requested"], result["ceiling"]) == (
        each,
        each,
        each,
    )
    assert result["authority_granted"] is False
    # The correction says whose ceiling it is and the launch field to raise.
    assert "ceiling you set yourself" in result["correction"]
    assert "set at launch in budget.ceilings." + dimension in result["correction"]
    assert "Carbon sets no ceiling of its own" in result["correction"]
    # The refused reservation recorded nothing.
    assert ledger.operation_state("work-2", owner=OWNER) is None
    p.close()


def test_an_elapsed_refusal_names_the_launch_field(tmp_path):
    clock = [1000.0]
    ledger = product(tmp_path, clock=lambda: clock[0], elapsed_seconds=60)
    f, p, e = compose(tmp_path, ledger, charging(ledger, {"research_trials": 1}))
    assert run(f, p, 0).state is State.SUCCEEDED  # starts the campaign's clock
    clock[0] = 2000.0
    done = run(f, p, 1)
    assert done.state is State.SUCCEEDED
    result = e.public_result(done)["result"]
    assert result["dimension"] == "elapsed_seconds"
    assert "budget.elapsed_seconds" in result["correction"]
    p.close()


def test_service_capacity_stays_infrastructure_typed_resource_limit(tmp_path):
    ledger = product(tmp_path)
    limit = SERVICE_LIMITS["reference_trajectories"]
    f, p, _e = compose(
        tmp_path, ledger, charging(ledger, {"reference_trajectories": limit})
    )
    assert run(f, p, 0).state is State.SUCCEEDED
    done = run(f, p, 1)
    assert done.state is State.FAILED_INFRA
    assert (
        done.terminal_receipt.infrastructure_failure_class
        is InfrastructureFailureClass.RESOURCE_LIMIT
    )
    p.close()


@pytest.mark.parametrize(
    "error",
    [
        RuntimeError("worker crashed"),
        OSError("disk"),
        # The ledger's text without the ledger's type is not its refusal.
        ValueError("miner budget: research_trials"),
    ],
)
def test_a_genuine_executor_exception_stays_internal(tmp_path, error):
    ledger = product(tmp_path)

    def material(name, workspace):
        raise error

    f, p, _e = compose(tmp_path, ledger, material)
    done = run(f, p, 0)
    assert done.state is State.FAILED_INFRA
    assert (
        done.terminal_receipt.infrastructure_failure_class
        is InfrastructureFailureClass.INTERNAL
    )
    p.close()


def test_a_failing_refusal_hook_keeps_internal_and_never_retries(tmp_path):
    ledger = product(tmp_path, ceilings={"research_trials": 0})
    calls = []
    inner = charging(ledger, {"research_trials": 1})

    def material(name, workspace):
        calls.append(name)
        return inner(name, workspace)

    f, p, e = compose(tmp_path, ledger, material)
    e.refusal_outcome = lambda attempt, error: (_ for _ in ()).throw(KeyError("x"))
    done = run(f, p, 0)
    assert done.state is State.FAILED_INFRA
    assert (
        done.terminal_receipt.infrastructure_failure_class
        is InfrastructureFailureClass.INTERNAL
    )
    # The durable provider never re-executes an uncertain attempt.
    assert calls == ["objective"]
    p.close()


def test_a_hook_reply_of_another_type_keeps_internal(tmp_path):
    ledger = product(tmp_path, ceilings={"research_trials": 0})
    f, p, e = compose(tmp_path, ledger, charging(ledger, {"research_trials": 1}))
    e.refusal_outcome = lambda attempt, error: {"outcome": "SUCCEEDED"}
    done = run(f, p, 0)
    assert done.state is State.FAILED_INFRA
    assert (
        done.terminal_receipt.infrastructure_failure_class
        is InfrastructureFailureClass.INTERNAL
    )
    p.close()


def test_the_executor_types_only_the_ledgers_refusal(tmp_path):
    """`refusal_outcome` declines (None) every exception that is not the
    ledger's typed refusal, the ledger's text in a plain ValueError
    included."""
    ledger = product(tmp_path)
    _f, p, e = compose(tmp_path, ledger, charging(ledger, {}))
    attempt = SimpleNamespace(task_id=SimpleNamespace(value="never-stored"))
    for error in (
        RuntimeError("worker crashed"),
        ValueError("miner budget: research_trials"),
        DispatchStopped("dispatch fenced by campaign control"),
    ):
        assert e.refusal_outcome(attempt, error) is None
    p.close()


def test_retained_receipts_and_results_read_unchanged(tmp_path):
    """A task that ended before this fix - FAILED_INFRA / INTERNAL, or a
    result with no ceiling fields - reads back exactly after a restart."""
    ledger = product(tmp_path)
    crashed = [True]

    def material(name, workspace):
        if crashed[0]:
            raise RuntimeError("historical crash")
        return {"name": name}

    f, p, e = compose(tmp_path, ledger, material)
    failed = run(f, p, 0)
    crashed[0] = False
    ok = run(f, p, 1)
    before = (failed, ok, e.public_result(ok))
    p.close()
    _f2, p2, e2 = compose(tmp_path, ledger, material)
    views = {t: p2._view(p2._tasks[t]) for t in (failed.task_id, ok.task_id)}
    assert views[failed.task_id] == before[0]
    assert views[ok.task_id] == before[1]
    assert e2.public_result(views[ok.task_id]) == before[2]
    assert "outcome" not in before[2]["result"]
    p2.close()
