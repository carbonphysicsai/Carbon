"""Direct public discovery binds real fixture bytes and stays fail closed."""

from dataclasses import replace
from types import SimpleNamespace

import pytest
from b07a_fixtures import discovery_resources, strategy

from carbon import research
from carbon.challenge_kit.synthetic_linear_field_2d import (
    bundle_material,
    bundle_material_v3,
    bundle_material_v4,
    bundle_material_v5,
)
from carbon.development_session.profile import canonical, digest
from carbon.development_session.research_service import DirectFixtureDiscovery
from carbon.development_session.research_tools import (
    PREFIX,
    ResearchMinerTools,
    tools_for_sdk,
)
from carbon.resource_policy.refs import ResourceClassRef


def _direct():
    material = bundle_material()
    discovery = DirectFixtureDiscovery(material)
    service = research.LocalResearchService(
        research.DirectPublicResearchContext(discovery, discovery)
    )
    return material, discovery, service


def _call(service, operation, request):
    return service.call(
        research.ServiceCall(research.RESEARCH_NAMESPACE, operation, request)
    )


def test_direct_discovery_round_trips_actual_public_material():
    material, discovery, service = _direct()
    key = material["challenge_key"]
    info, manifest = discovery.info, discovery.manifest
    assert info.public_train_digest == material["construction_kit"]["train_digest"]
    assert info.train_case_ids == material["train_case_ids"]
    assert info.practice_case_ids == material["practice_case_ids"]
    assert manifest.challenge_info_digest == research.canonical_digest(info)
    assert manifest.supported_operations == (
        "get_challenge_info",
        "get_interaction_manifest",
    )
    for result in (info, manifest):
        assert (
            research.load_canonical(research.canonical_bytes(result), type(result))
            == result
        )
    assert (
        _call(
            service, "get_challenge_info", research.GetChallengeInfoRequest(key)
        ).result
        == info
    )
    assert (
        _call(
            service,
            "get_interaction_manifest",
            research.GetInteractionManifestRequest(key),
        ).result
        == manifest
    )
    with pytest.raises(ValueError):
        replace(manifest, supported_operations=research.SUPPORTED_OPERATIONS)


def test_direct_discovery_refuses_changed_material_at_use():
    material, discovery, service = _direct()
    key = material["challenge_key"]
    material["practice_inputs"][0, 0, 0, 0] += 1.0
    with pytest.raises(ValueError, match="registered fixture"):
        discovery.get_challenge_info(key)
    reply = _call(service, "get_challenge_info", research.GetChallengeInfoRequest(key))
    assert reply.status is research.ReplyStatus.ERROR
    assert reply.result.code is not None


def test_direct_discovery_rejects_unregistered_material_at_composition():
    material = bundle_material()
    material["practice_inputs"][0, 0, 0, 0] += 1.0
    with pytest.raises(ValueError, match="registered fixture"):
        DirectFixtureDiscovery(material)


def test_prospective_v3_discovery_binds_exact_graph_policy_and_worker_inputs():
    material = bundle_material_v3()
    discovery = DirectFixtureDiscovery(material)
    assert discovery.info.challenge_key.version == "1.1"
    assert discovery.manifest.construction_kit_digest == digest(
        canonical(material["construction_kit"])
    )
    assert discovery.manifest.supported_operations == (
        "get_challenge_info",
        "get_interaction_manifest",
    )
    for key, changed in (
        ("allowlist_bytes", bundle_material()["allowlist_bytes"]),
        ("allowlist_digest", bundle_material()["allowlist_digest"]),
        ("expected_output_shape", (1, 8, 8, 1)),
    ):
        altered = bundle_material_v3()
        altered[key] = changed
        with pytest.raises(ValueError, match="registered fixture"):
            DirectFixtureDiscovery(altered)
    altered = bundle_material_v3()
    altered["example"][0, 0, 0, 0] += 1
    with pytest.raises(ValueError, match="registered fixture"):
        DirectFixtureDiscovery(altered)


def test_task_enabled_direct_manifest_requires_prospective_trusted_composition():
    with pytest.raises(ValueError, match="prospective kit"):
        DirectFixtureDiscovery(bundle_material(), task_admission=True)
    discovery = DirectFixtureDiscovery(bundle_material_v3(), task_admission=True)
    assert (
        discovery.manifest.supported_operations
        == research.DIRECT_RECIPE_TASK_OPERATIONS
    )
    historical = replace(
        discovery.manifest,
        supported_operations=research.DIRECT_RECIPE_TASK_OPERATIONS,
    )
    old_wire = research.canonical_bytes(historical)
    assert (
        research.load_canonical(old_wire, research.DirectRecipeManifest) == historical
    )
    assert (
        research.canonical_bytes(
            research.load_canonical(old_wire, research.DirectRecipeManifest)
        )
        == old_wire
    )
    with pytest.raises(ValueError, match="trusted direct task composition"):
        research.DirectPublicResearchContext(discovery, discovery)


def test_v4_direct_task_discovery_registers_exact_allowlist_without_rewriting_v3():
    v3 = DirectFixtureDiscovery(bundle_material_v3(), task_admission=True)
    v4 = DirectFixtureDiscovery(bundle_material_v4(), task_admission=True)
    assert v3.info.challenge_key.version == "1.1"
    assert v4.info.challenge_key.version == "1.2"
    assert v3.manifest.construction_kit_digest != v4.manifest.construction_kit_digest
    assert v4.manifest.supported_operations == research.DIRECT_RECIPE_TASK_OPERATIONS
    altered = bundle_material_v4()
    altered["allowlist_bytes"] = bundle_material_v3()["allowlist_bytes"]
    with pytest.raises(ValueError, match="registered fixture"):
        DirectFixtureDiscovery(altered, task_admission=True)


def test_v5_direct_task_discovery_binds_new_policy_and_keeps_v4():
    v4 = DirectFixtureDiscovery(bundle_material_v4(), task_admission=True)
    v5 = DirectFixtureDiscovery(bundle_material_v5(), task_admission=True)
    assert v4.info.challenge_key.version == "1.2"
    assert v5.info.challenge_key.version == "1.3"
    assert v4.manifest.construction_kit_digest != v5.manifest.construction_kit_digest
    assert v4.manifest.supported_operations == research.DIRECT_RECIPE_TASK_OPERATIONS
    assert (
        v5.manifest.supported_operations
        == research.DIRECT_RECIPE_SOURCE_TASK_OPERATIONS
    )
    assert v4.graph_adapter_for(v4.info.challenge_key) is None
    assert (
        v5.graph_adapter_for(v5.info.challenge_key)
        == "synthetic-linear-field-2d-public-jax-graph-v1"
    )
    altered = bundle_material_v5()
    altered["allowlist_bytes"] = bundle_material_v4()["allowlist_bytes"]
    with pytest.raises(ValueError, match="registered fixture"):
        DirectFixtureDiscovery(altered, task_admission=True)
    altered = bundle_material_v5()
    altered["construction_limits_document"]["graph_training_adapter"][
        "id"
    ] += "-changed"
    altered["construction_kit"]["construction_limits_digest"] = digest(
        canonical(altered["construction_limits_document"])
    )
    with pytest.raises(ValueError, match="registered fixture"):
        DirectFixtureDiscovery(altered, task_admission=True)


def test_direct_service_refuses_legacy_task_compile_and_prior():
    material, _discovery, service = _direct()
    assert not service.binds_research_task_provider(None)
    key = material["challenge_key"]
    historical_info, historical = discovery_resources()
    old_training = replace(historical_info.training_support_ref, challenge_key=key)
    requests = (
        (
            "compile_strategy",
            research.CompileStrategyRequest(key, strategy(), old_training),
        ),
        ("get_prior", research.GetPriorRequest(key, research.NoPriorSelector())),
        (
            "start_research_task",
            research.StartResearchTaskRequest(
                key,
                "direct-attempt-closed-1",
                research.DevelopmentWorkspaceTaskSpecV1(
                    "carbon.autoresearch.workspace.v1", "inventory", "{}"
                ),
                old_training,
                research.NoPriorSelector(),
                replace(historical.resource_policy_ref, challenge_key=key),
                ResourceClassRef(
                    key,
                    "direct_fixture_cpu",
                    "1.0",
                    content_digest=research.canonical_digest(historical),
                ),
                None,
            ),
        ),
    )
    for operation, request in requests:
        reply = _call(service, operation, request)
        assert reply.status is research.ReplyStatus.ERROR
        assert (
            reply.result.code
            is research.ResearchServiceErrorCode.CAPABILITY_UNAVAILABLE
        )


def test_historical_manifest_bytes_and_operations_unchanged():
    _info, historical = discovery_resources()
    assert historical.schema_version == "2.0"
    assert historical.supported_operations == research.SUPPORTED_OPERATIONS
    assert (
        research.load_canonical(
            research.canonical_bytes(historical), research.InteractionManifest
        )
        == historical
    )


def test_direct_sdk_and_mcp_offer_only_discovery_tools():
    _material, discovery, _service = _direct()
    sdk = ResearchMinerTools(
        connection=object(),
        wrapper=object(),
        composition=SimpleNamespace(
            discovery=discovery,
            executor=SimpleNamespace(owner="fixture-miner", julia_image=None),
        ),
        ledger=None,
        owner="fixture-miner",
    )
    expected = {PREFIX + operation for operation in research.DIRECT_RECIPE_OPERATIONS}
    assert {tool["name"] for tool in tools_for_sdk(sdk, rule=None)} == expected
    sdk.composition.executor.julia_image = object()
    assert {tool["name"] for tool in tools_for_sdk(sdk, rule=None)} == expected
    pytest.importorskip("mcp")
    from carbon.miner_mcp.standard import ResearchToolAdapter

    assert {
        tool["name"]
        for tool in ResearchToolAdapter(sdk, principal="fixture-miner").sdk_tools
    } == expected
