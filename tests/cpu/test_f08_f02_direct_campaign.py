"""F08 (Ribbed Bracket) 1.4 and F02 (Burst Thermal) 2.3 direct campaigns, as
Motor's and Cooling's catalog campaigns: composed under each version's own key,
refused while the catalog is empty, a catalog or graph recipe practised through
the receiver's own build (injected here; its custody is the workers' own
tests'), frozen from that practice and submitted through the signed
construction receiver (stand-ins). Every unregistered value is HUMAN_INPUT and
fails closed where it is read."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import numpy as np
import pytest
from direct_catalog_stand_in import STAND_IN, inject
from test_lp_prod_research_tools import ledger

from carbon.challenge_kit import physical_material
from carbon.challenge_registry import campaigns, describe
from carbon.challenge_registry.campaigns import campaign_for, implemented_campaigns
from carbon.challenge_registry.direct import catalog_recipe, graph_recipe
from carbon.development_session import bundle_construction_worker as bundle_worker
from carbon.development_session import construction_recipe, direct_submission
from carbon.development_session import direct_graph_construction_worker as graph_worker
from carbon.development_session.research_campaign import OperationRefused
from carbon.direct_campaign import practice as direct_practice
from carbon.direct_campaign import research as direct_research
from carbon.direct_campaign.spec import F02, F08, HUMAN_INPUT

RECEIVER = "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY"
VERSIONS = [(F08, "1.4"), (F02, "2.3")]
IDS = ["f08-1.4", "f02-2.3"]
GRAPH_DIGEST = "sha256:" + "a" * 64


def _challenge(spec, version):
    return {"id": spec.challenge_id, "version": version}


def _module(spec, name):
    import importlib

    return importlib.import_module("carbon." + spec.prefix + "." + name)


# --- composition -------------------------------------------------------------


@pytest.mark.parametrize("spec, version", VERSIONS, ids=IDS)
def test_each_version_composes_its_own_campaign(spec, version):
    campaign = campaign_for(_challenge(spec, version))
    assert campaign.key.challenge_id == spec.challenge_id
    assert campaign.key.version == version
    assert campaign.construction_kit() == spec.public().construction_kit(
        spec.challenge_id, version
    )
    assert (
        campaign.feedback_schema == "carbon." + spec.prefix + ".permitted-feedback.v1"
    )
    assert campaign.practice_provenance == spec.prefix.upper() + "_PUBLIC_PRACTICE"
    assert callable(campaign.construction_reconstruct)
    assert campaign.construction_bundle_material()["challenge_key"] == campaign.key
    assert (campaign.key.challenge_id, version) in {
        (entry.challenge_id, entry.version) for entry, _ in implemented_campaigns()
    }
    # The id-level resolution has no Level-0 campaign to fall back to.
    assert spec.challenge_id not in campaigns._campaigns()


@pytest.mark.parametrize("spec, version", VERSIONS, ids=IDS)
def test_there_is_no_default_version(spec, version):
    contracts = _module(spec, "contracts")
    research = _module(spec, "research")
    with pytest.raises(TypeError):
        research.challenge_parts()
    for other in (None, "1.3", "2.2", "9.9"):
        with pytest.raises(ValueError, match="direct campaign version"):
            contracts.key_for(other)
    with pytest.raises(ValueError, match="no default version"):
        contracts.research_key()
    with pytest.raises(ValueError, match="direct campaign version"):
        getattr(campaigns, "_" + spec.prefix + "_direct")("1.3")


@pytest.mark.parametrize("spec, version", VERSIONS, ids=IDS)
def test_the_research_parts_are_keyed_by_the_version(spec, version):
    parts = _module(spec, "research").challenge_parts(version)
    assert parts.key == campaign_for(_challenge(spec, version)).key
    assert parts.measurements.challenge_key == parts.key
    for binding in parts.measurements.stratum_applicability:
        assert binding.stratum_ref.challenge_key == parts.key
    assert parts.contracts.key == parts.key
    assert parts.strategy_schema["schema"] == "carbon.backbone-catalog.served.v1"
    assert parts.scaffold_strategy["source"]["kind"] == "catalog"
    assert parts.practice_scope["challenge"] == _challenge(spec, version)
    # The key returns to none once built.
    with pytest.raises(ValueError, match="no default version"):
        _module(spec, "contracts").research_key()


@pytest.mark.parametrize("spec, version", VERSIONS, ids=IDS)
def test_the_contracts_take_the_registered_interface(spec, version):
    from carbon.direct_campaign import contracts

    interface = spec.public().interface_document(spec.challenge_id, version)
    with contracts.keyed(spec, contracts.key_for(spec, version)):
        physical, _candidate, training = contracts.authored_contracts(spec)
        sources = contracts.direct_sources(spec)
        limits = contracts.limits_document(spec)
    assert [f.field_id for f in physical.causal_inputs] == interface["input"]["names"]
    outputs = [f.field_id for f in physical.required_physical_quantities]
    assert outputs == interface["output"]["names"]
    assert training.to_ref().challenge_key.version == version
    digests = {selector: content for selector, _, _, content in sources}
    assert set(digests) == {"direct_adapter", "direct_catalog"}
    assert digests["direct_catalog"] == limits["backbone_catalog"]["digest"]
    # No Level-0 strategy compiles: direct recipes only.
    parts = _module(spec, "research").challenge_parts(version)
    with pytest.raises(contracts.DirectRecipesOnly):
        parts.recipe_compiler({"backbone": "direct_catalog"})
    with pytest.raises(contracts.DirectRecipesOnly):
        parts.contracts.compile({"backbone": "direct_catalog"})


@pytest.mark.parametrize("spec, version", VERSIONS, ids=IDS)
def test_the_launchpad_lists_the_version_generically(spec, version):
    from scripts.dev.miner_launchpad.construction_paths import for_challenges

    found = for_challenges()[spec.challenge_id]
    assert found["challenge"] == _challenge(spec, version)
    assert found["construction_kit"] == spec.public().construction_kit(
        spec.challenge_id, version
    )
    assert found["paths"][0]["reason"] == (
        "public_reconstruction_registered_host_readiness_unverified"
    )


# --- an empty catalog refuses to start --------------------------------------


@pytest.mark.parametrize("spec, version", VERSIONS, ids=IDS)
def test_an_empty_catalog_campaign_is_refused_before_anything_starts(
    spec, version, tmp_path
):
    campaign = campaign_for(_challenge(spec, version))
    args = SimpleNamespace(
        root=tmp_path,
        command="run",
        product=SimpleNamespace(runtime={"implementation": "x"}, agent="none"),
    )
    code = spec.prefix + "_catalog_empty"
    assert _module(spec, "campaign").CATALOG_EMPTY == code
    with pytest.raises(ValueError, match=code):
        asyncio.run(campaign.prepare(args, ledger=None, campaign=campaign))
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("spec, version", VERSIONS, ids=IDS)
def test_with_an_offered_entry_the_refusal_is_not_the_catalogs(
    spec, version, tmp_path, monkeypatch
):
    inject(monkeypatch, spec.challenge_id, version)
    campaign = campaign_for(_challenge(spec, version))
    args = SimpleNamespace(
        root=tmp_path,
        command="run",
        product=SimpleNamespace(runtime={"implementation": "x"}, agent="none"),
    )
    # Past the catalog check, the next refusal is the grant's.
    granted = SimpleNamespace(root=tmp_path, admission="a-grant")
    with pytest.raises(ValueError, match="never consumes a development grant"):
        asyncio.run(campaign.prepare(args, ledger=granted, campaign=campaign))


# --- practice: catalog and graph recipes ------------------------------------


def _rows(material):
    """Predicted rows of the interface's width, exactly float32-representable."""
    shape = material["expected_output_shape"]
    return (np.arange(np.prod(shape), dtype=np.float32).reshape(shape) / 4).tolist()


def _fake(material, calls, rows=None):
    def fake(ledger_, **kwargs):
        calls.append(kwargs)
        state = "sha256:" + "5" * 64
        return SimpleNamespace(
            build=SimpleNamespace(state_digest=state),
            inference=SimpleNamespace(
                state_digest=state,
                predictions=_rows(material) if rows is None else rows,
            ),
        )

    return fake


def _practice(spec, version, tmp_path):
    parent = SimpleNamespace(image_id="sha256:" + "7" * 64)
    resolved = []
    item = _module(spec, "catalog_practice").__dict__[
        spec.prefix.upper() + "DirectPractice"
    ](
        ledger=ledger(tmp_path / "ledger"),
        owner="alice",
        parent=parent,
        cache_root=tmp_path / "cache",
        version=version,
        resolver=lambda ref: resolved.append(ref) or SimpleNamespace(bundle_ref=ref),
        parents=SimpleNamespace(for_bundle=lambda _ref: parent),
    )
    return item, resolved


@pytest.mark.parametrize("spec, version", VERSIONS, ids=IDS)
def test_a_catalog_recipe_runs_as_its_bundle_on_the_exposed_bank(
    spec, version, tmp_path, monkeypatch
):
    inject(monkeypatch, spec.challenge_id, version)
    material = physical_material.bundle_material(spec.challenge_id, version)
    calls = []
    monkeypatch.setattr(
        bundle_worker, "reconstruct_and_infer_public", _fake(material, calls)
    )
    item, resolved = _practice(spec, version, tmp_path)
    recipe = catalog_recipe(spec, STAND_IN, version=version)
    result = item(spec.prefix + "-catalog-0001", recipe)
    (call,) = calls
    assert call["seed"] == 0
    assert call["recipe"].to_dict()["source"]["kind"] == "bundle"
    assert call["inference_image"] is item.parent
    assert call["construction_parent"] is item.parent
    assert resolved[0].bundle_digest == (
        call["recipe"].to_dict()["source"]["bundle_ref"]["bundle_digest"]
    )
    kit = material["construction_kit"]
    assert call["challenge_binding"] == {
        "challenge_id": kit["id"],
        "challenge_version": kit["version"],
        "train_digest": kit["train_digest"],
        "interface_digest": kit["interface_digest"],
        "construction_limits_digest": kit["construction_limits_digest"],
    }
    assert np.array_equal(call["inputs"], material["practice_inputs"])
    assert call["inputs"].dtype == np.float32
    assert call["expected_output_dtype"] == "<f4"
    assert call["expected_output_shape"] == material["expected_output_shape"]
    assert result["provenance"] == spec.practice_provenance
    assert result["source_kind"] == "catalog" and result["catalog_id"] == STAND_IN
    assert result["recipe"] == recipe
    assert result["official_eligible"] is False and result["final_exam"] is False


@pytest.mark.parametrize("spec, version", VERSIONS, ids=IDS)
def test_a_graph_recipe_runs_through_carbons_graph_adapter(
    spec, version, tmp_path, monkeypatch
):
    from carbon.development_session import physical_graph_adapter as adapter

    material = physical_material.bundle_material(spec.challenge_id, version)
    calls, envelopes = [], []
    monkeypatch.setattr(
        graph_worker, "reconstruct_and_infer_graph_public", _fake(material, calls)
    )
    monkeypatch.setattr(
        construction_recipe,
        "graph_envelope_from_workspace",
        lambda ledger_, owner, recipe: envelopes.append(recipe) or b"{}",
    )
    item, _ = _practice(spec, version, tmp_path)
    recipe = graph_recipe(spec, GRAPH_DIGEST, version=version)
    result = item(spec.prefix + "-graph-0001", recipe)
    (call,) = calls
    assert call["adapter_id"] == adapter.spec_for(spec.challenge_id, version).adapter_id
    assert call["image"] is item.parent and call["seed"] == 0
    assert call["source_envelope"] == b"{}"
    assert envelopes[0].to_dict() == recipe
    assert np.array_equal(call["inputs"], material["practice_inputs"])
    assert call["allowlist_bytes"] == adapter.served_allowlist_bytes(
        spec.challenge_id, version
    )
    assert result["source_kind"] == "graph"
    assert result["provenance"] == spec.practice_provenance
    assert result["backend"]["adapter"] == call["adapter_id"]


@pytest.mark.parametrize("spec, version", VERSIONS, ids=IDS)
def test_a_graph_recipe_outside_the_adapter_is_refused_before_anything_runs(
    spec, version, tmp_path, monkeypatch
):
    from carbon.development_session.construction_recipe import RecipeRefused

    calls = []
    monkeypatch.setattr(
        graph_worker,
        "reconstruct_and_infer_graph_public",
        lambda *a, **k: calls.append(k),
    )
    item, _ = _practice(spec, version, tmp_path)
    recipe = graph_recipe(
        spec, GRAPH_DIGEST, version=version, training={"batch_size": 10**6}
    )
    with pytest.raises(RecipeRefused, match=spec.prefix + "_graph_"):
        item(spec.prefix + "-graph-0002", recipe)
    assert calls == []


@pytest.mark.parametrize("spec, version", VERSIONS, ids=IDS)
@pytest.mark.parametrize("bad", ["not_float32", "wrong_width", "nonfinite"])
def test_outputs_must_be_finite_float32_rows_of_the_interface(
    spec, version, bad, tmp_path, monkeypatch
):
    material = physical_material.bundle_material(spec.challenge_id, version)
    rows = np.asarray(_rows(material), dtype=np.float64)
    if bad == "not_float32":
        rows[0, 0] = 0.1  # not exactly representable in float32
    elif bad == "wrong_width":
        rows = rows[:, :-1] if rows.shape[1] > 1 else np.hstack([rows, rows])
    else:
        rows[0, 0] = np.inf
    monkeypatch.setattr(
        graph_worker,
        "reconstruct_and_infer_graph_public",
        _fake(material, [], rows.tolist()),
    )
    monkeypatch.setattr(
        construction_recipe, "graph_envelope_from_workspace", lambda *a: b"{}"
    )
    item, _ = _practice(spec, version, tmp_path)
    with pytest.raises(ValueError, match=spec.prefix + "_practice_output_invalid"):
        item(
            spec.prefix + "-graph-0003",
            graph_recipe(spec, GRAPH_DIGEST, version=version),
        )


@pytest.mark.parametrize("spec, version", VERSIONS, ids=IDS)
def test_a_level0_strategy_and_the_empty_template_are_not_recipes(
    spec, version, tmp_path, monkeypatch
):
    calls = []
    monkeypatch.setattr(
        bundle_worker, "reconstruct_and_infer_public", lambda *a, **k: calls.append(k)
    )
    item, _ = _practice(spec, version, tmp_path)
    with pytest.raises(ValueError):
        item("x-0001", {"schema_version": "1.0", "backbone": "direct_catalog"})
    template = catalog_recipe(spec, version=version)
    assert template["source"]["catalog_id"] is None
    with pytest.raises(ValueError):
        item("x-0002", template)
    assert item.installed() == () and calls == []


# --- freeze -------------------------------------------------------------------


@pytest.mark.parametrize("spec, version", VERSIONS, ids=IDS)
def test_a_practice_record_supports_a_freeze(spec, version, tmp_path, monkeypatch):
    from carbon.development_session.profile import canonical, digest
    from carbon.development_session.research_campaign import trial_supports_selection
    from carbon.development_session.research_tasks import PublicResearchExecutor

    material = physical_material.bundle_material(spec.challenge_id, version)
    monkeypatch.setattr(
        graph_worker, "reconstruct_and_infer_graph_public", _fake(material, [])
    )
    monkeypatch.setattr(
        construction_recipe, "graph_envelope_from_workspace", lambda *a: b"{}"
    )
    item, _ = _practice(spec, version, tmp_path)
    recipe = graph_recipe(spec, GRAPH_DIGEST, version=version)
    result = item(spec.prefix + "-graph-0004", recipe)
    meter = item.ledger
    PublicResearchExecutor(
        ledger=meter, owner="alice", image=None, public_material=None, practice=None
    )
    assert not trial_supports_selection(meter, "alice", recipe)
    body = canonical(result)
    with meter.db() as db:
        db.execute(
            "INSERT OR REPLACE INTO research_results VALUES(?,?,?,?)",
            ("alice", spec.prefix + "-graph-0004", body, digest(body)),
        )
    assert trial_supports_selection(meter, "alice", recipe)
    assert not trial_supports_selection(meter, "other", recipe)


@pytest.mark.parametrize("spec, version", VERSIONS, ids=IDS)
def test_the_freeze_records_a_catalog_and_a_graph_recipe(
    spec, version, tmp_path, monkeypatch
):
    from carbon.development_session.research_campaign import direct_candidate_record

    inject(monkeypatch, spec.challenge_id, version)
    monkeypatch.setattr(
        construction_recipe,
        "graph_envelope_from_workspace",
        lambda *a: b'{"graph": "envelope"}',
    )
    prepared = SimpleNamespace(
        ledger=SimpleNamespace(root=tmp_path),
        owner="alice",
        campaign=campaign_for(_challenge(spec, version)),
    )
    catalog = catalog_recipe(spec, STAND_IN, version=version)
    record, envelope = direct_candidate_record(prepared, catalog, "practised", False)
    assert record["strategy"] == catalog and envelope is None
    graph = graph_recipe(spec, GRAPH_DIGEST, version=version)
    record, envelope = direct_candidate_record(prepared, graph, "practised", False)
    assert record["strategy"] == graph and envelope == b'{"graph": "envelope"}'


# --- submit -------------------------------------------------------------------


def _prepared(tmp_path, args, recipe, epoch=1):
    folder = tmp_path / f"epoch-{epoch}"
    folder.mkdir(parents=True)
    (folder / "selected-recipe.json").write_text(json.dumps({"strategy": recipe}))
    connection = SimpleNamespace(miner_key=object(), chain_context=object())
    return SimpleNamespace(
        ledger=SimpleNamespace(root=tmp_path),
        owner="alice",
        args=args,
        sdk=SimpleNamespace(connection=connection),
    )


def _args(spec):
    return SimpleNamespace(
        intakes={spec.challenge_id: "http://127.0.0.1:8769"},
        receivers={spec.challenge_id: RECEIVER},
    )


@pytest.mark.parametrize("spec, version", VERSIONS, ids=IDS)
def test_a_frozen_recipe_is_submitted_and_its_judgement_kept(
    spec, version, tmp_path, monkeypatch
):
    from carbon.reconstruction.served_recipe_contract import registered

    sent, kept = [], []
    monkeypatch.setattr(
        direct_submission,
        "submit_and_wait",
        lambda url, key, **kw: sent.append((url, kw)) or {"state": "RECONSTRUCTED"},
    )
    monkeypatch.setattr(
        direct_submission,
        "read_exam_feedback",
        lambda url, key, **kw: {"best": None, "latest": None},
    )
    monkeypatch.setattr(
        _module(spec, "campaign"),
        "record_verdict",
        lambda ledger, owner, epoch, feedback: kept.append(feedback),
    )
    recipe = graph_recipe(spec, GRAPH_DIGEST, version=version)
    prepared = _prepared(tmp_path, _args(spec), recipe)
    campaign = campaign_for(_challenge(spec, version))
    feedback = asyncio.run(campaign.evaluate(prepared, 1, recipe))
    ((url, kw),) = sent
    assert url == "http://127.0.0.1:8769" and kw["receiver"] == RECEIVER
    assert kw["recipe"].to_dict() == recipe
    assert kw["contract_digest"] == registered(spec.challenge_id, version).digest
    assert feedback["schema"] == spec.feedback_schema
    assert feedback["challenge"] == _challenge(spec, version)
    assert feedback["result"] == {"state": "RECONSTRUCTED"} and kept == [feedback]


@pytest.mark.parametrize("spec, version", VERSIONS, ids=IDS)
def test_a_changed_frozen_candidate_is_not_submitted(
    spec, version, tmp_path, monkeypatch
):
    sent = []
    monkeypatch.setattr(
        direct_submission, "submit_and_wait", lambda *a, **k: sent.append(k)
    )
    recipe = graph_recipe(spec, GRAPH_DIGEST, version=version)
    prepared = _prepared(tmp_path, _args(spec), recipe)
    other = graph_recipe(spec, "sha256:" + "b" * 64, version=version)
    with pytest.raises(ValueError, match="differs from the frozen candidate"):
        asyncio.run(
            campaign_for(_challenge(spec, version)).evaluate(prepared, 1, other)
        )
    assert sent == []


@pytest.mark.parametrize("spec, version", VERSIONS, ids=IDS)
@pytest.mark.parametrize(
    "raised, code",
    [
        (direct_submission.DirectConstructionPending("rtsk_1"), "evaluation_queued"),
        (
            direct_submission.DirectIntakeRefusal(
                "construction_intake_changed_since_submission"
            ),
            "construction_intake_changed_since_submission",
        ),
        (OSError("down"), "construction_intake_unavailable"),
    ],
)
def test_a_submit_that_does_not_finish_is_refused_by_its_code(
    spec, version, raised, code, tmp_path, monkeypatch
):
    def fail(*a, **k):
        raise raised

    monkeypatch.setattr(direct_submission, "submit_and_wait", fail)
    recipe = graph_recipe(spec, GRAPH_DIGEST, version=version)
    prepared = _prepared(tmp_path, _args(spec), recipe)
    with pytest.raises(OperationRefused, match=code):
        asyncio.run(
            campaign_for(_challenge(spec, version)).evaluate(prepared, 1, recipe)
        )


@pytest.mark.parametrize("spec, version", VERSIONS, ids=IDS)
def test_without_a_receiver_the_submit_is_unconfigured(spec, version, tmp_path):
    recipe = graph_recipe(spec, GRAPH_DIGEST, version=version)
    prepared = _prepared(tmp_path, SimpleNamespace(intakes={}, receivers={}), recipe)
    with pytest.raises(OperationRefused, match="construction_intake_unconfigured"):
        asyncio.run(
            campaign_for(_challenge(spec, version)).evaluate(prepared, 1, recipe)
        )


@pytest.mark.parametrize("spec, version", VERSIONS, ids=IDS)
def test_the_agent_sees_the_controls_and_how_to_submit(spec, version):
    campaign = campaign_for(_challenge(spec, version))
    prepared = SimpleNamespace(
        manifest={"provider": {"agent": "graphite"}},
        composition=SimpleNamespace(
            executor=SimpleNamespace(
                practice=SimpleNamespace(backends=("torch_cpu", "jax")),
                julia_image=None,
            )
        ),
    )
    observation = campaign.observation(prepared, 1, None)
    assert observation["scaffold_recipe"] == catalog_recipe(spec, version=version)
    assert observation["graph_recipe_template"] == graph_recipe(spec, version=version)
    assert observation["unsupported_capabilities"]["count"] == 1
    assert "signed construction receiver" in observation["instructions"]


# --- HUMAN_INPUT fails closed where it is read -------------------------------


@pytest.mark.parametrize("spec, version", VERSIONS, ids=IDS)
def test_unregistered_values_are_human_input(spec, version):
    from carbon.direct_campaign import contracts

    document = describe(spec.challenge_id, version)
    assert document["task"] == document["intended_use"] == HUMAN_INPUT
    assert document["exam"]["gates"] == document["exam"]["rule"] == HUMAN_INPUT
    assert document["exam"]["qualification"] is False
    assert document["feedback"]["practice"] == HUMAN_INPUT
    assert document["examples"] == [] and document["models"]["rebuildable"] == []
    with contracts.keyed(spec, contracts.key_for(spec, version)):
        objective = direct_research.objective(spec)
        profile = contracts.profile_document(spec)
        reference = direct_research.reference_method(spec)
    for name in ("task", "intended_use", "sampling_law", "gates", "score"):
        assert objective[name] == HUMAN_INPUT
    assert objective["practice_error_scale"] == HUMAN_INPUT
    for name in ("physical_scope", "governing_law", "geometry_domain"):
        assert profile[name] == HUMAN_INPUT
    assert reference["reference"] == reference["quality"] == HUMAN_INPUT
    parts = _module(spec, "research").challenge_parts(version)
    assert parts.score_document["score"] == HUMAN_INPUT


@pytest.mark.parametrize("spec, version", VERSIONS, ids=IDS)
def test_practice_reports_no_error_and_no_per_case_value(
    spec, version, tmp_path, monkeypatch
):
    material = physical_material.bundle_material(spec.challenge_id, version)
    monkeypatch.setattr(
        graph_worker, "reconstruct_and_infer_graph_public", _fake(material, [])
    )
    monkeypatch.setattr(
        construction_recipe, "graph_envelope_from_workspace", lambda *a: b"{}"
    )
    item, _ = _practice(spec, version, tmp_path)
    result = item("x-0003", graph_recipe(spec, GRAPH_DIGEST, version=version))
    assert result["summary"]["aggregate_error"] is None
    assert (
        result["summary"]["error_scale"] == direct_practice.ERROR_SCALE == HUMAN_INPUT
    )
    assert result["summary"]["cases"] == len(material["practice_case_ids"])
    text = json.dumps(result)
    for case_id in material["practice_case_ids"]:
        assert case_id not in text
    # The research view shows aggregates only and declares no component.
    view = campaign_for(_challenge(spec, version)).research_view()
    assert view.per_case.allowed is False
    assert view.components == () and view.reference is None


@pytest.mark.parametrize("spec, version", VERSIONS, ids=IDS)
def test_the_public_material_serves_no_label(spec, version):
    stored = {}
    workspace = SimpleNamespace(put=lambda name, body: stored.__setitem__(name, body))
    material = _module(spec, "research").__dict__[
        spec.prefix.upper() + "PublicMaterial"
    ](version)
    from carbon.development_session.research_tasks import public_material_names

    assert set(public_material_names(material)) == set(direct_research.NAMES)
    practice = material("practice_data", workspace)["document"]
    assert practice["labels"] == HUMAN_INPUT
    bank = physical_material.bundle_material(spec.challenge_id, version)
    assert practice["cases"] == len(bank["practice_case_ids"])
    for name in direct_research.NAMES:
        material(name, workspace)
    text = b"".join(v for k, v in stored.items() if k.endswith(".json")).decode()
    assert not any(case_id in text for case_id in bank["practice_case_ids"])
    with pytest.raises(ValueError, match="allowlist"):
        material("private_bank", workspace)
