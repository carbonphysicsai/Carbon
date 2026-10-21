"""F08 (Ribbed Bracket) 1.4 and F02 (Burst Thermal) 2.3 direct campaigns, as
Motor's and Cooling's catalog campaigns: composed under each version's own key,
refused while the catalog is empty, a catalog or graph recipe practised through
the receiver's own build (injected here; its custody is the workers' own
tests'), frozen from that practice and submitted through the signed
construction receiver (stand-ins). The owner-approved science facts
(LAUNCHPAD_F08_F02_SCIENCE_FACTS_20261021) are served as approved; every value
still unset is HUMAN_INPUT and fails closed where it is read."""

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
from carbon.direct_campaign import contracts as direct_contracts
from carbon.direct_campaign import facts as direct_facts
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
    # Static imports (code authority refuses an import name built at run time).
    from carbon.f02 import campaign as f02_campaign
    from carbon.f02 import catalog_practice as f02_catalog_practice
    from carbon.f02 import contracts as f02_contracts
    from carbon.f02 import research as f02_research
    from carbon.f08 import campaign as f08_campaign
    from carbon.f08 import catalog_practice as f08_catalog_practice
    from carbon.f08 import contracts as f08_contracts
    from carbon.f08 import research as f08_research

    return {
        ("f08", "campaign"): f08_campaign,
        ("f08", "catalog_practice"): f08_catalog_practice,
        ("f08", "contracts"): f08_contracts,
        ("f08", "research"): f08_research,
        ("f02", "campaign"): f02_campaign,
        ("f02", "catalog_practice"): f02_catalog_practice,
        ("f02", "contracts"): f02_contracts,
        ("f02", "research"): f02_research,
    }[(spec.prefix, name)]


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


# --- the approved facts, and HUMAN_INPUT failing closed where it is read -----

#: The approved copy of LAUNCHPAD_F08_F02_SCIENCE_FACTS_20261021.
APPROVED_SHA256 = "34a4f31c8b9ad950593a3fa0cb9a533d3c57c2ad25c0e919acecff1eaffb1095"
#: Each version's approved facts and clause labels, by canonical digest: a value
#: or label that moves is a new approval, not an edit.
FACTS_DIGESTS = {
    ("f08-ribbed-bracket", "1.4"): (
        "sha256:2c4993cd21e67ce6f992fbdd5a472e0f79e2abc7a152171cfb6894b60eb05532",
        "sha256:38767282f0d7b270df6007f3b33b2a5fa93e3a728349343c311bfffa5683cbf9",
    ),
    ("f02", "2.3"): (
        "sha256:70710a4f1a08904f37659304c842fe6725a4eacb90f7a330881cf0d2a46948a6",
        "sha256:cc5f5566fc859e7df26b3cb2b06786d98d4642f7d18fa500f394e8b17213290a",
    ),
}
#: Left HUMAN_INPUT: the approved file's LEAVE_HUMAN_INPUT fields, and the two
#: whose approved wording (structural facts only) contradicts this version's
#: registered-scale practice (`facts.STOPPED`).
LEFT = {
    "f08-ribbed-bracket": (
        "physical_invariant",
        "practice_reporting",
        "catalog_usage_text",
    ),
    "f02": (
        "physical_support",
        "physical_invariant",
        "practice_reporting",
        "catalog_usage_text",
    ),
}
TASKS = {
    "f08-ribbed-bracket": (
        "Predict the static tip compliance and, at each of three constant modal "
        "damping ratios (0.005, 0.01, 0.02), the largest tip dynamic compliance "
        "over 80-600 Hz and its frequency, for the registered clamped ribbed-plate "
        "bracket with a cable relief under a unit tip-pad force."
    ),
    "f02": (
        "Predict the maximum die-top temperature over a 120-second transient for "
        "one rectangular power burst (total power during the burst and its "
        "on-time, starting at 20 s on a 20 W base from a uniform 40 C start) in "
        "the registered three-layer die/TIM/copper stack with underside "
        "convective cooling."
    ),
}


def _fact(spec, version, name):
    return direct_facts.value(spec, version, name)


@pytest.mark.parametrize("spec, version", VERSIONS, ids=IDS)
def test_the_approved_facts_are_pinned_to_their_approval(spec, version):
    assert direct_facts.APPROVAL == {
        "record": "LAUNCHPAD_F08_F02_SCIENCE_FACTS_20261021",
        "sha256": APPROVED_SHA256,
    }
    key = (spec.challenge_id, version)
    values, labels = direct_facts.FACTS[key], direct_facts.LABELS[key]
    canonical, digest = direct_contracts.canonical, direct_contracts.digest
    assert (digest(canonical(values)), digest(canonical(labels))) == (
        FACTS_DIGESTS[key]
    )
    assert values["task"] == TASKS[spec.challenge_id]
    assert direct_facts.STOPPED == ("practice_reporting", "catalog_usage_text")
    left = {name for name, value in values.items() if value == HUMAN_INPUT}
    assert left == set(LEFT[spec.challenge_id])
    # Every value is text, and every filled clause has its approved label.
    assert all(type(value) is str for value in values.values())
    for name in set(labels):
        assert values[name.split(".")[0]] != HUMAN_INPUT
    for name in ("governing_job", "governing_law", "geometry_domain"):
        assert name in labels


@pytest.mark.parametrize("spec, version", VERSIONS, ids=IDS)
def test_the_approved_facts_are_served_and_the_rest_is_human_input(spec, version):
    from carbon.direct_campaign import contracts

    document = describe(spec.challenge_id, version)
    assert document["task"] == TASKS[spec.challenge_id]
    assert document["intended_use"] == _fact(spec, version, "intended_use")
    assert document["interface"]["conventions"] == _fact(
        spec, version, "interface_conventions"
    )
    assert document["exam"]["gates"] == document["exam"]["rule"] == HUMAN_INPUT
    assert document["exam"]["components"] == HUMAN_INPUT
    assert document["exam"]["qualification"] is False
    # Validator, 2026-10-21: practice reports aggregate errors on the
    # registered scale.
    assert document["feedback"]["practice"] == (
        "aggregate public-practice errors on the registered scale"
    )
    assert document["examples"] == [] and document["models"]["rebuildable"] == []
    with contracts.keyed(spec, contracts.key_for(spec, version)):
        objective = direct_research.objective(spec)
        profile = contracts.profile_document(spec)
        reference = direct_research.reference_method(spec)
    assert objective["task"] == TASKS[spec.challenge_id]
    for name in ("intended_use", "sampling_law"):
        assert objective[name] == _fact(spec, version, name) != HUMAN_INPUT
    assert objective["gates"] == objective["score"] == HUMAN_INPUT
    assert objective["practice_error_scale"] == direct_practice.error_scale(
        spec, version
    )
    for name in contracts.OWNER_FIELDS:
        assert profile[name] == _fact(spec, version, name) != HUMAN_INPUT
    assert reference["reference"] == _fact(spec, version, "reference_method")
    assert reference["quality"] == _fact(spec, version, "reference_quality")
    assert HUMAN_INPUT not in (reference["reference"], reference["quality"])
    parts = _module(spec, "research").challenge_parts(version)
    assert parts.score_document["score"] == HUMAN_INPUT
    # The catalog's usage text is held (`facts.STOPPED`).
    workspace = SimpleNamespace(put=lambda name, body: None)
    material = direct_research.DirectPublicMaterial(spec, version)
    assert material("catalog", workspace)["document"]["use"] == HUMAN_INPUT


def _authored(spec, version):
    """The version's authored contracts and research parts."""
    from carbon.direct_campaign import contracts

    with contracts.keyed(spec, contracts.key_for(spec, version)):
        physical, _candidate, training = contracts.authored_contracts(spec)
        population, sampling = direct_research.population_and_sampling(spec)
        measurement = direct_research.measurement_contract(spec)
    return physical, training, population, sampling, measurement


@pytest.mark.parametrize("spec, version", VERSIONS, ids=IDS)
def test_each_filled_clause_carries_its_approved_label_and_text(spec, version):
    from carbon.direct_campaign import contracts

    physical, training, population, sampling, measurement = _authored(spec, version)
    labels = direct_facts.LABELS[(spec.challenge_id, version)]
    assert physical.governing_job_ref.object_id == labels["governing_job"]
    assert [r.object_id for r in physical.governing_law_refs] == [
        labels["governing_law"]
    ]
    assert physical.geometry_domain_ref.object_id == labels["geometry_domain"]
    for field in physical.causal_inputs + physical.required_physical_quantities:
        assert field.geometry_binding.value.object_id == labels["geometry_domain"]
    assert physical.operating_envelope_ref.object_id == labels["operating_envelope"]
    time = physical.time_contract
    assert time.endpoint_inclusion_semantic_ref.object_id == labels["time_semantics"]
    assert training.rights_profile_ref.object_id == "public_synthetic"
    assert population.rights_profile_ref.object_id == "public_synthetic_cases"
    support = population.support_contract
    assert support.boundary_semantics_ref.object_id == labels["support_boundary"]
    assert support.membership_decision_ref.object_id == labels["membership_decision"]
    law = population.law_semantics.payload
    assert law.base_measure_ref.object_id == labels["base_measure"]
    assert law.law_ref.object_id == labels["probability_law"]
    fidelity = sampling.reference_fidelity_allocation_binding.value
    assert fidelity.object_id == labels["reference_fidelity"]
    assert [r.object_id for r in measurement.known_limitation_refs] == [
        labels["known_limitation"]
    ]
    # A filled clause's digest binds its approved text beside the profile.
    with contracts.keyed(spec, contracts.key_for(spec, version)):
        profile = contracts.profile_document(spec)
    text = _fact(spec, version, "governing_job")
    assert physical.governing_job_ref.content_digest == contracts.digest(
        contracts.canonical(
            {"clause": labels["governing_job"], "profile": profile, "statement": text}
        )
    )
    # Held (STOPPED) clauses keep their human_input_* labels.
    reporting = sampling.intended_estimand_or_reporting_ref
    assert reporting.object_id == "human_input_practice_reporting"


@pytest.mark.parametrize("spec, version", VERSIONS, ids=IDS)
def test_the_leave_clauses_keep_their_human_input_labels(spec, version):
    _, training, population, _, _ = _authored(spec, version)
    invariants = [r.object_id for r in training.physical_invariant_refs]
    assert invariants == ["human_input_physical_invariant"]
    supports = (
        training.membership_contract.physical_support_ref.object_id,
        population.support_contract.physical_support_ref.object_id,
    )
    if spec is F02:
        assert supports == ("human_input_physical_support",) * 2
    else:
        label = direct_facts.LABELS[(spec.challenge_id, version)]["physical_support"]
        assert supports == (label, label)
        assert label == "linear_clamped_synthetic_material_reference_support"


@pytest.mark.parametrize("spec, version", VERSIONS, ids=IDS)
def test_time_stays_steady_with_the_approved_time_semantics(spec, version):
    from carbon.authoring.model import TimeMode

    physical, *_ = _authored(spec, version)
    time = physical.time_contract
    # Validator, 2026-10-21: STEADY is kept (the interface has no time
    # coordinate); F02's clauses are relabelled so it reads as a transient
    # burst summarised as its window maximum.
    assert time.mode is TimeMode.STEADY
    assert time.time_coordinate_binding.is_bound is False
    reason = time.time_coordinate_binding.value.object_id
    endpoints = time.endpoint_inclusion_semantic_ref.object_id
    if spec is F02:
        assert reason == "time_maximum_over_registered_window"
        assert endpoints == "transient_burst_summarised_as_window_maximum"
    else:
        assert reason == "interface_has_no_time_coordinate"
        assert endpoints == "static_and_frequency_domain_no_time_coordinate"
    assert time.horizon_binding.value.object_id == "interface_has_no_time_horizon"


def _graph_practice(spec, version, tmp_path, monkeypatch, rows=None):
    material = physical_material.bundle_material(spec.challenge_id, version)
    monkeypatch.setattr(
        graph_worker,
        "reconstruct_and_infer_graph_public",
        _fake(material, [], rows=rows),
    )
    monkeypatch.setattr(
        construction_recipe, "graph_envelope_from_workspace", lambda *a: b"{}"
    )
    item, _ = _practice(spec, version, tmp_path)
    result = item("x-0003", graph_recipe(spec, GRAPH_DIGEST, version=version))
    return material, result


@pytest.mark.parametrize("spec, version", VERSIONS, ids=IDS)
def test_practice_reports_aggregates_on_the_registered_scale_and_no_per_case_value(
    spec, version, tmp_path, monkeypatch
):
    material, result = _graph_practice(spec, version, tmp_path, monkeypatch)
    summary = result["summary"]
    assert summary["status"] == "aggregate_on_registered_scale"
    assert summary["error_scale"] == direct_practice.error_scale(spec, version)
    assert summary["score"] == summary["aggregate_error"] > 0
    assert list(summary["components"]) == list(direct_practice.COMPONENTS[spec.prefix])
    assert summary["cases"] == summary["n_cases"] == summary["n_scored"]
    assert summary["cases"] == len(material["practice_case_ids"])
    # Only aggregates: one number per component, no list, no case id.
    assert all(type(v) is float for v in summary["components"].values())
    text = json.dumps(result)
    for case_id in material["practice_case_ids"]:
        assert case_id not in text
    # The research view shows aggregates only, lower is better.
    view = campaign_for(_challenge(spec, version)).research_view()
    assert view.per_case.allowed is False and view.reference is None
    assert [k for k, _ in view.components] == list(summary["components"])
    assert view.direction == "lower_is_better"
    assert view.learning_curve["basis"] == HUMAN_INPUT


def test_f02_practice_is_on_train_peak_std_c_with_the_registered_reduction(
    tmp_path, monkeypatch
):
    from carbon.challenge_kit import f02_train, physical_pack

    # The exact computed spread, recomputed from the pinned rows (6.701 recorded).
    scale = f02_train.load_public_train("2.3")["train_peak_std_c"]
    assert scale == 6.701245845436587 and round(scale, 3) == 6.701
    bank = physical_pack.development_bank("f02", "2.3")
    # 1 C high on the four ordinary actions, 2 C high on the four near-limit
    # ones (float32 outputs), against each action's primary rung.
    rows = [
        [
            float(
                np.float32(
                    record["rung_peaks_c"]["primary"]
                    + (2.0 if "-near-" in case_id else 1.0)
                )
            )
        ]
        for case_id, record in zip(
            bank["case_ids"], bank["reference_records"], strict=True
        )
    ]
    _, result = _graph_practice(F02, "2.3", tmp_path, monkeypatch, rows=rows)
    summary = result["summary"]
    # By hand: mean 1.5 / 6.701245845436587, near-limit mean and worst
    # 2 / 6.701245845436587; the aggregate is their maximum.
    assert summary["components"] == pytest.approx(
        {"mean": 0.22383897, "near_mean": 0.29845197, "worst": 0.29845197},
        abs=1e-6,
    )
    assert summary["aggregate_error"] == pytest.approx(0.29845197, abs=1e-6)
    assert summary["error_scale"]["scales"]["peak_top_c"]["value"] == scale


def test_f08_practice_is_on_dev1_section_7_scales_with_its_aggregation(
    tmp_path, monkeypatch
):
    material = physical_material.bundle_material("f08-ribbed-bracket", "1.4")
    names = material["interface_document"]["output"]["names"]
    # Static 0.0003 mm/N high (0.1 of 0.003), each dynamic tip 0.003 mm/N high
    # (0.2 of 0.015), each peak frequency 5 Hz high (0.5 of 10 Hz), and one
    # case's first peak frequency 20 Hz high (2.0 of 10 Hz).
    offset = {
        name: (
            0.0003
            if name.startswith("static")
            else 0.003 if name.startswith("peak_tip") else 5.0
        )
        for name in names
    }
    rows = []
    for i, reference in enumerate(material["practice_reference"].tolist()):
        row = [r + offset[name] for r, name in zip(reference, names, strict=True)]
        if i == 0:
            row[names.index("peak_frequency_z005_hz")] = reference[2] + 20.0
        rows.append([float(np.float32(v)) for v in row])
    _, result = _graph_practice(F08, "1.4", tmp_path, monkeypatch, rows=rows)
    summary = result["summary"]
    # By hand: margin mean (8 x 0.1 + 24 x 0.2) / 32 = 0.175, worst 0.2;
    # resonance mean (2.0 + 23 x 0.5) / 24 = 0.5625, worst 2.0; the aggregate
    # is the worst over quantity and case, 2.0.
    assert summary["components"] == pytest.approx(
        {
            "margin_mean": 0.175,
            "margin_worst": 0.2,
            "resonance_mean": 0.5625,
            "resonance_worst": 2.0,
        },
        abs=1e-5,
    )
    assert summary["aggregate_error"] == pytest.approx(2.0, abs=1e-5)
    scales = summary["error_scale"]["scales"]
    assert {n: scales[n]["value"] for n in names} == {
        "static_tip_mm_per_n": 0.003,
        "peak_tip_z005_mm_per_n": 0.015,
        "peak_frequency_z005_hz": 10.0,
        "peak_tip_z010_mm_per_n": 0.015,
        "peak_frequency_z010_hz": 10.0,
        "peak_tip_z020_mm_per_n": 0.015,
        "peak_frequency_z020_hz": 10.0,
    }
    assert summary["error_scale"]["reference"] == "POINT_ESTIMATE_DIAGNOSTIC"


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


@pytest.mark.parametrize(("spec", "version"), VERSIONS, ids=IDS)
@pytest.mark.parametrize("name", direct_contracts.OWNER_FIELDS)
def test_a_set_profile_field_reads_its_approved_value(spec, version, name):
    # The five owner/Validator fields carry the approved facts and read
    # through `profile_value` (and `fact_value`).
    from carbon.direct_campaign.spec import key_for, keyed

    with keyed(spec, key_for(spec, version)):
        value = direct_contracts.profile_value(spec, name)
        assert value == direct_contracts.fact_value(spec, name)
    assert value == _fact(spec, version, name) != HUMAN_INPUT
    assert type(value) is str and value


@pytest.mark.parametrize(
    ("spec", "version", "name"),
    [
        (spec, version, name)
        for spec, version in VERSIONS
        for name in LEFT[spec.challenge_id]
    ],
)
def test_an_unset_fact_is_refused_never_read_as_a_value(spec, version, name):
    # The approved file's LEAVE_HUMAN_INPUT fields (and the STOPPED ones) stay
    # HUMAN_INPUT: reading one refuses (as agent_campaign.grant refuses an
    # unset grant value).
    from carbon.direct_campaign.spec import key_for, keyed

    with keyed(spec, key_for(spec, version)):
        assert name not in direct_contracts.profile_document(spec)
        with pytest.raises(direct_contracts.ProfileValueMissing) as refused:
            direct_contracts.fact_value(spec, name)
    assert refused.value.code == "direct_profile_value_missing"
    assert refused.value.field == name


@pytest.mark.parametrize(("spec", "version"), VERSIONS, ids=IDS)
def test_an_unset_profile_field_is_still_refused(spec, version, monkeypatch):
    # Were a profile fact unset again, `profile_value` refuses it.
    from carbon.direct_campaign.spec import key_for, keyed

    key = (spec.challenge_id, version)
    unset = {**direct_facts.FACTS[key], "governing_law": HUMAN_INPUT}
    monkeypatch.setitem(direct_facts.FACTS, key, unset)
    direct_contracts._profile.cache_clear()
    try:
        with keyed(spec, key_for(spec, version)):
            assert direct_contracts.profile_document(spec)["governing_law"] == (
                HUMAN_INPUT
            )
            with pytest.raises(direct_contracts.ProfileValueMissing) as refused:
                direct_contracts.profile_value(spec, "governing_law")
    finally:
        monkeypatch.undo()
        direct_contracts._profile.cache_clear()
    assert refused.value.code == "direct_profile_value_missing"


@pytest.mark.parametrize("unset", [None, "HUMAN_INPUT", "TODO", ""])
def test_every_unset_spelling_is_refused(unset):
    assert unset in direct_contracts.UNSET
