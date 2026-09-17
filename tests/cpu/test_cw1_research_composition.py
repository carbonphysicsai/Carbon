"""Real D4 static composition; numerical/model execution deliberately absent."""

from types import SimpleNamespace

from carbon import research
from carbon.development_session.profile import CHALLENGE, canonical
from carbon.development_session.research_ledger import CampaignLedger
from carbon.development_session.research_service import make_research_service


def test_real_catalog_discovery_compilation_and_workspace(tmp_path):
    ledger = CampaignLedger(tmp_path / "ledger")
    c = make_research_service(
        root=tmp_path / "tasks",
        ledger=ledger,
        owner="engineering-miner",
        image=SimpleNamespace(),
        public_material=lambda name, workspace: {"public": name},
        practice=lambda *args: None,
    )

    def call(operation, request):
        return c.service.call(
            research.ServiceCall(research.RESEARCH_NAMESPACE, operation, request)
        )

    info = call("get_challenge_info", research.GetChallengeInfoRequest(CHALLENGE))
    assert info.status is research.ReplyStatus.OK
    assert info.result.instance_distribution_ref == c.population.to_ref()
    manifest = call(
        "get_interaction_manifest", research.GetInteractionManifestRequest(CHALLENGE)
    )
    assert manifest.status is research.ReplyStatus.OK
    scaffold = call(
        "get_mock_scaffold",
        research.GetMockScaffoldRequest(
            CHALLENGE, info.result.training_support_ref, None
        ),
    )
    assert scaffold.status is research.ReplyStatus.OK
    compiled = call(
        "compile_strategy",
        research.CompileStrategyRequest(
            CHALLENGE,
            scaffold.result.strategy_template,
            info.result.training_support_ref,
        ),
    )
    assert compiled.status is research.ReplyStatus.OK and compiled.result.accepted
    estimate = call(
        "inspect_resources",
        research.InspectResourcesRequest(
            CHALLENGE, scaffold.result.strategy_template, c.inspection.policy_ref
        ),
    )
    assert estimate.status is research.ReplyStatus.OK
    # No made-up runtime prediction is inferred from an empty static estimate.
    forecast = call(
        "forecast_resources",
        research.ForecastResourcesRequest(
            CHALLENGE, scaffold.result.strategy_template, c.inspection.policy_ref, 600
        ),
    )
    assert forecast.status is research.ReplyStatus.OK
    assert "SUPPORT:UNRESOLVED" in forecast.result.limitations
    start = research.StartResearchTaskRequest(
        CHALLENGE,
        "engineering-workspace-one",
        research.DevelopmentWorkspaceTaskSpecV1(
            "carbon.autoresearch.workspace.v1",
            "public_material",
            canonical({"name": "objective"}).decode(),
        ),
        info.result.training_support_ref,
        research.NoPriorSelector(),
        c.inspection.policy_ref,
        c.inspection.resource_class_ref,
        manifest.result.practice_scope_ref,
    )
    task = call("start_research_task", start)
    assert task.status is research.ReplyStatus.OK
    done = c.tasks.run_queued_task(task.result.task.task_id)
    assert done.state is research.ResearchTaskState.SUCCEEDED
    assert c.executor.public_result(done)["result"] == {"public": "objective"}
    assert ledger.status(owner="engineering-miner")["used"]["provider_attempts"] == 0
    c.tasks.close()
