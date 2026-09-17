"""Synthetic protocol/lifecycle checks; no model-backed inference evidence."""

from dataclasses import replace
from types import SimpleNamespace

import pytest
from b07b_fixtures import make_fixture

from carbon import research
from carbon.development_session.profile import canonical
from carbon.development_session.research_ledger import CampaignLedger
from carbon.development_session.research_tasks import (
    PublicDevelopmentResearchTasks,
    PublicResearchExecutor,
)


def compose(tmp_path):
    fixture = make_fixture(tmp_path / "fixtures")
    p = fixture.provider
    ledger = CampaignLedger(tmp_path / "ledger")
    executor = PublicResearchExecutor(
        ledger=ledger,
        owner="test-miner",
        image=SimpleNamespace(),
        public_material=lambda name, workspace: {
            "name": name,
            "scope": "SYNTHETIC_ENGINEERING_TEST",
        },
        practice=lambda *args: (_ for _ in ()).throw(AssertionError("not practice")),
    )
    provider = PublicDevelopmentResearchTasks(
        root=tmp_path / "tasks",
        requester="test-miner",
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


def request(fixture, action, args, index=0):
    return replace(
        fixture.request(),
        idempotency_key="workspace-request-" + str(index),
        task_spec=research.DevelopmentWorkspaceTaskSpecV1(
            "carbon.autoresearch.workspace.v1", action, canonical(args).decode()
        ),
    )


def test_workspace_reuses_start_result_lifecycle_and_has_no_recipe(tmp_path):
    f, p, e = compose(tmp_path)
    req = request(
        f, "notebook", {"kind": "hypothesis", "body": {"hypothesis": "test statement"}}
    )
    assert (
        research.load_canonical(
            research.canonical_bytes(req), research.StartResearchTaskRequest
        )
        == req
    )
    with pytest.raises(research.ResearchTaskProviderError):
        f.provider.start_research_task(req)
    task = p.start_research_task(req).task
    assert task.immutable_bindings.strategy_bindings == ()
    done = p.run_queued_task(task.task_id)
    assert done.state is research.ResearchTaskState.SUCCEEDED
    result = e.public_result(done)
    assert result["result"] == {"retained": True}
    assert not result["official_eligible"]
    assert (
        p.get_experiment_record(task.task_id).evidence_class
        is research.ResearchEvidenceClass.STRUCTURAL_ONLY
    )
    assert len(e.ledger.status(owner="test-miner")["notes"]) == 1
    p.close()


def test_protected_material_request_cannot_reach_data_provider(tmp_path):
    f, p, e = compose(tmp_path)
    req = request(f, "public_material", {"name": "final-epoch-1"})
    task = p.start_research_task(req).task
    done = p.run_queued_task(task.task_id)
    assert done.state is research.ResearchTaskState.FAILED_INFRA
    assert e.public_result(done) is None
    p.close()


def test_owned_files_roundtrip_and_closed_arguments(tmp_path):
    f, p, e = compose(tmp_path)
    for index, (action, args) in enumerate(
        [
            (
                "write_file",
                {
                    "name": "notes.txt",
                    "content_base64": "cHVibGlj",
                    "expected_digest": None,
                },
            ),
            ("read_file", {"name": "notes.txt", "offset": 0, "count": 100}),
        ]
    ):
        task = p.start_research_task(request(f, action, args, index)).task
        done = p.run_queued_task(task.task_id)
        assert done.state is research.ResearchTaskState.SUCCEEDED
    assert e.public_result(done)["result"]["content_base64"] == "cHVibGlj"
    req = request(f, "inventory", {"path": "/controller"}, 3)
    task = p.start_research_task(req).task
    assert (
        p.run_queued_task(task.task_id).state is research.ResearchTaskState.FAILED_INFRA
    )
    p.close()


@pytest.mark.parametrize(
    "version,action",
    [
        ("carbon.autoresearch.workspace.v2", "inventory"),
        ("carbon.autoresearch.workspace.v1", "publish_weights"),
    ],
)
def test_workspace_version_and_actions_are_closed(version, action):
    with pytest.raises(ValueError):
        research.DevelopmentWorkspaceTaskSpecV1(version, action, "{}")
