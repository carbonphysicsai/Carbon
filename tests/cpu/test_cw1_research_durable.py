"""Synthetic lifecycle verification, never real agent or training evidence."""

from dataclasses import replace

import pytest
from b07b_fixtures import make_fixture

from carbon.research import (
    CancelResearchTaskRequest,
    GetResearchResultRequest,
    ResearchTaskProviderError,
    ResearchTaskState,
)
from carbon.research.durable import DurableResearchTaskProvider
from carbon.research.lifecycle import ReceiptFindingDefinition


def provider(root, fixture, requester="miner-one"):
    p = fixture.provider
    return DurableResearchTaskProvider(
        root=root,
        requester=requester,
        challenge_catalog_provider=p._catalog,
        manifest_provider=p._manifests,
        compilation_resolver=p._compiler,
        prior_resolver=p._priors,
        resource_resolver=p._resources,
        executor=p._executor,
        task_queue=p._queue,
        finding_definitions=tuple(
            ReceiptFindingDefinition(k, v) for k, v in p._findings.items()
        ),
        clock=p._clock,
        worker_implementation_digest=p._worker_digest,
        environment_digest=p._environment_digest,
    )


def test_restart_queued_terminal_poll_and_replay(tmp_path):
    f = make_fixture(tmp_path / "fixture")
    root = tmp_path / "tasks"
    p = provider(root, f)
    request = f.request()
    first = p.start_research_task(request)
    task = first.task.task_id
    poll = GetResearchResultRequest(request.challenge_key, task, 0)
    prior = p.get_research_result(poll)
    p.close()
    p = provider(root, f)
    assert p.get_research_result(poll) == prior
    assert not p.start_research_task(request).created
    assert p.queued_tasks() == (task,)
    completed = p.run_queued_task(task)
    assert completed.state is ResearchTaskState.SUCCEEDED
    p.close()
    p = provider(root, f)
    assert p.run_queued_task(task) == completed
    assert p.queued_tasks() == ()
    with pytest.raises(ResearchTaskProviderError):
        p.start_research_task(
            replace(
                request,
                task_spec=replace(
                    request.task_spec,
                    intervention_strategy={
                        **request.task_spec.intervention_strategy,
                        "parameters": {"fixture_sampling_level": 1},
                    },
                ),
            )
        )
    p.close()


def test_running_restart_never_dispatches_and_cancellation_survives(tmp_path):
    f = make_fixture(tmp_path / "fixture")
    root = tmp_path / "tasks"
    p = provider(root, f)
    request = f.request()
    task = p.start_research_task(request).task.task_id
    p._transition(p._tasks[task], ResearchTaskState.RUNNING)
    p.close()
    p = provider(root, f)
    assert p.queued_tasks() == ()
    with pytest.raises(ResearchTaskProviderError):
        p.run_queued_task(task)
    cancel = CancelResearchTaskRequest(
        request.challenge_key, task, "cancel-request-one"
    )
    assert (
        p.cancel_research_task(cancel).task.state is ResearchTaskState.CANCEL_REQUESTED
    )
    p.close()
    p = provider(root, f)
    assert (
        p.cancel_research_task(cancel).task.state is ResearchTaskState.CANCEL_REQUESTED
    )
    p.close()


def test_requester_binding_and_single_supervisor(tmp_path):
    f = make_fixture(tmp_path / "fixture")
    root = tmp_path / "tasks"
    p = provider(root, f)
    with pytest.raises(ValueError, match="already active"):
        provider(root, f)
    p.close()
    with pytest.raises(ValueError, match="binding changed"):
        provider(root, f, "miner-two")
