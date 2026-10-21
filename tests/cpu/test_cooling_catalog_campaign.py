"""Cooling 1.2, the backbone-catalog campaign (OWNER-BACKBONE-CATALOG-01, as Motor
1.2/1.3): composed under its own key, its catalog discoverable, its frozen recipe
submitted to the signed construction receiver and judged there. Cooling's
catalog is empty until a Cooling entry is tested; where a test needs one, a
stand-in is injected (`cooling_catalog_stand_in`)."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest
from cooling_catalog_stand_in import STAND_IN, empty, inject

from carbon.backbone_catalog import served
from carbon.challenge_kit import physical_public
from carbon.challenge_registry.campaigns import campaign_for
from carbon.challenge_registry.cold_plate import catalog_recipe
from carbon.cold_plate.research import ColdPlatePublicMaterial, CoolingCatalogMaterial
from carbon.development_session import direct_submission
from carbon.development_session.research_campaign import OperationRefused

COOLING = "chip-cold-plate"
RECEIVER = "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY"


def test_each_cooling_version_has_its_own_campaign():
    old = campaign_for({"id": COOLING, "version": "1.0"})
    new = campaign_for({"id": COOLING, "version": "1.2"})
    assert old.key.version == "1.0" and old.construction_kit is None
    assert new.key.version == "1.2"
    assert new.construction_kit() == physical_public.construction_kit(COOLING, "1.2")
    assert new.feedback_schema == "carbon.cold-plate.permitted-feedback.v1"
    # Practice keeps Cooling's provenance, so a practised recipe can freeze.
    assert new.practice_provenance == old.practice_provenance
    assert new.practice_provenance == "COLD_PLATE_PUBLIC_PRACTICE"
    with pytest.raises(ValueError, match="cooling catalog version"):
        from carbon.challenge_registry import campaigns

        campaigns._cold_plate_catalog("1.1")


def test_cooling_1_2s_limits_bind_its_catalog_and_1_1_keeps_its_bytes():
    limits = physical_public.construction_limits_document(COOLING, "1.2")
    assert limits["backbone_catalog"] == {
        "schema": served.SCHEMA,
        "digest": served.digest(COOLING, "1.2"),
    }
    assert "backbone_catalog" not in physical_public.construction_limits_document(
        COOLING, "1.1"
    )


def test_the_catalog_and_its_kit_are_public_material_on_1_2_only(monkeypatch):
    from carbon.development_session.research_tasks import public_material_names

    empty(monkeypatch)

    assert "catalog" in public_material_names(CoolingCatalogMaterial(".", "1.2"))
    assert "catalog" not in public_material_names(ColdPlatePublicMaterial("."))
    with pytest.raises(ValueError, match="cooling catalog version"):
        CoolingCatalogMaterial(".", "1.0")
    stored = {}
    workspace = SimpleNamespace(put=lambda name, body: stored.__setitem__(name, body))
    reply = CoolingCatalogMaterial(".", "1.2")("catalog", workspace)
    # With no entry offered: no entry and an unfilled ready recipe.
    assert reply["document"]["entries"] == {}
    assert reply["document"]["ready_recipe"]["source"]["catalog_id"] is None
    kit = CoolingCatalogMaterial(".", "1.2")("construction_kit", workspace)
    assert kit["document"] == physical_public.construction_kit(COOLING, "1.2")
    assert set(stored) == {
        "cold-plate-catalog.json",
        "cold-plate-construction_kit.json",
    }


def test_an_offered_entry_is_served_by_the_catalog_material(monkeypatch):
    inject(monkeypatch)
    workspace = SimpleNamespace(put=lambda name, body: None)
    reply = CoolingCatalogMaterial(".", "1.2")("catalog", workspace)
    assert set(reply["document"]["entries"]) == {STAND_IN}
    assert reply["document"]["ready_recipe"] == catalog_recipe(version="1.2")
    assert reply["document"]["ready_recipe"]["source"]["catalog_id"] == STAND_IN
    assert reply["document"]["catalog_digest"] == served.digest(COOLING, "1.2")


def test_a_named_entry_the_version_does_not_offer_is_refused():
    from carbon.backbone_catalog.entries import CatalogRefused

    with pytest.raises(CatalogRefused) as refused:
        catalog_recipe("neuralop.FNO", version="1.2")  # a Motor entry
    assert refused.value.code == "catalog_entry_unknown"
    for version in ("1.0", "1.1"):
        with pytest.raises(ValueError, match="cooling catalog version"):
            catalog_recipe(version=version)


def test_an_empty_catalog_campaign_is_refused_before_anything_starts(
    tmp_path, monkeypatch
):
    empty(monkeypatch)
    campaign = campaign_for({"id": COOLING, "version": "1.2"})
    args = SimpleNamespace(
        root=tmp_path,
        command="run",
        product=SimpleNamespace(runtime={"implementation": "x"}, agent="none"),
    )
    ledger = SimpleNamespace(root=tmp_path, admission=None)
    with pytest.raises(ValueError, match="cooling_catalog_empty"):
        asyncio.run(campaign.prepare(args, ledger=ledger, campaign=campaign))
    assert list(tmp_path.iterdir()) == []


def _prepared(tmp_path, args, recipe, epoch=1):
    folder = tmp_path / f"epoch-{epoch}"
    folder.mkdir(parents=True)
    (folder / "selected-recipe.json").write_text(json.dumps({"strategy": recipe}))
    connection = SimpleNamespace(miner_key=object(), chain_context=object())
    ledger = SimpleNamespace(root=tmp_path)
    return SimpleNamespace(
        ledger=ledger,
        owner="alice",
        args=args,
        sdk=SimpleNamespace(connection=connection),
    )


def test_a_frozen_catalog_recipe_is_submitted_and_its_judgement_kept(
    tmp_path, monkeypatch
):
    from carbon.cold_plate import campaign as cold_plate
    from carbon.reconstruction.served_recipe_contract import registered

    inject(monkeypatch)
    sent = []
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
    kept = []
    monkeypatch.setattr(
        cold_plate,
        "record_verdict",
        lambda ledger, owner, epoch, feedback: kept.append(feedback),
    )
    args = SimpleNamespace(
        intakes={COOLING: "http://127.0.0.1:8769"}, receivers={COOLING: RECEIVER}
    )
    recipe = catalog_recipe(STAND_IN, version="1.2")
    prepared = _prepared(tmp_path, args, recipe)
    campaign = campaign_for({"id": COOLING, "version": "1.2"})
    feedback = asyncio.run(campaign.evaluate(prepared, 1, recipe))
    ((url, kw),) = sent
    assert url == "http://127.0.0.1:8769" and kw["receiver"] == RECEIVER
    assert kw["recipe"].to_dict() == recipe
    assert kw["contract_digest"] == registered(COOLING, "1.2").digest
    assert feedback["challenge"] == {"id": COOLING, "version": "1.2"}
    assert feedback["result"] == {"state": "RECONSTRUCTED"} and kept == [feedback]


def test_a_changed_frozen_candidate_is_not_submitted(tmp_path, monkeypatch):
    inject(monkeypatch)
    sent = []
    monkeypatch.setattr(
        direct_submission, "submit_and_wait", lambda *a, **k: sent.append(k)
    )
    args = SimpleNamespace(
        intakes={COOLING: "http://127.0.0.1:8769"}, receivers={COOLING: RECEIVER}
    )
    recipe = catalog_recipe(STAND_IN, version="1.2")
    prepared = _prepared(tmp_path, args, recipe)
    other = {**recipe, "procedure": {**recipe["procedure"], "configuration": {"x": 1}}}
    with pytest.raises(ValueError, match="differs from the frozen candidate"):
        asyncio.run(
            campaign_for({"id": COOLING, "version": "1.2"}).evaluate(prepared, 1, other)
        )
    assert sent == []


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
    tmp_path, monkeypatch, raised, code
):
    inject(monkeypatch)

    def fail(*a, **k):
        raise raised

    monkeypatch.setattr(direct_submission, "submit_and_wait", fail)
    args = SimpleNamespace(
        intakes={COOLING: "http://127.0.0.1:8769"}, receivers={COOLING: RECEIVER}
    )
    recipe = catalog_recipe(STAND_IN, version="1.2")
    prepared = _prepared(tmp_path, args, recipe)
    campaign = campaign_for({"id": COOLING, "version": "1.2"})
    with pytest.raises(OperationRefused, match=code):
        asyncio.run(campaign.evaluate(prepared, 1, recipe))


def test_without_a_receiver_the_submit_is_unconfigured_and_1_0_stays_closed(
    tmp_path, monkeypatch
):
    inject(monkeypatch)
    recipe = catalog_recipe(STAND_IN, version="1.2")
    prepared = _prepared(tmp_path, SimpleNamespace(intakes={}, receivers={}), recipe)
    with pytest.raises(OperationRefused, match="construction_intake_unconfigured"):
        asyncio.run(
            campaign_for({"id": COOLING, "version": "1.2"}).evaluate(
                prepared, 1, recipe
            )
        )
    with pytest.raises(OperationRefused, match="cooling_validator_not_served"):
        asyncio.run(
            campaign_for({"id": COOLING, "version": "1.0"}).evaluate(
                prepared, 1, recipe
            )
        )


def test_1_2_keeps_neural_operators_unsupported_but_for_carbons_tested_ones():
    from carbon.challenge_registry import describe

    listed = {c["id"]: c for c in describe(COOLING, "1.2")["unsupported"]}
    assert len(listed) == len(describe(COOLING, "1.0")["unsupported"]) == 5
    assert listed["model_family.neural_operator"]["blocker"] == (
        "only Carbon-tested ones, by catalog id; miner-authored neural operators are not rebuildable"
    )


def test_the_description_lists_no_example_until_an_entry_is_offered(monkeypatch):
    from carbon.challenge_registry import describe

    empty(monkeypatch)
    nothing = describe(COOLING, "1.2")
    assert nothing["examples"] == [] and nothing["models"]["rebuildable"] == []
    assert "No backbone is tested" in nothing["models"]["note"]
    inject(monkeypatch)
    offered = describe(COOLING, "1.2")
    (example,) = offered["examples"]
    assert example["recipe"]["source"]["catalog_id"] == STAND_IN
    assert [m["selector"] for m in offered["models"]["rebuildable"]] == [STAND_IN]


def test_the_agent_sees_the_catalog_control_and_how_to_submit():
    from carbon.challenge_registry import describe

    campaign = campaign_for({"id": COOLING, "version": "1.2"})
    practice = SimpleNamespace(backends=("torch_cpu",))
    prepared = SimpleNamespace(
        manifest={"provider": {"agent": "graphite"}},
        composition=SimpleNamespace(
            executor=SimpleNamespace(practice=practice, julia_image=None)
        ),
    )
    observation = campaign.observation(prepared, 1, None)
    assert observation["scaffold_recipe"] == catalog_recipe(version="1.2")
    assert observation["unsupported_capabilities"]["count"] == len(
        describe(COOLING, "1.2")["unsupported"]
    )
    assert "signed construction receiver" in observation["instructions"]
    old = campaign_for({"id": COOLING, "version": "1.0"}).observation(prepared, 1, None)
    assert old["instructions"].endswith(
        "Submission evaluation remains unavailable until its adapter is registered."
    )


def test_cooling_1_2_offers_its_five_cooling_tested_entries():
    # The real manifest: the five Torch builds resized to Cooling's 32 outputs,
    # each with its own Cooling pair-identity receipt (Test Lead,
    # PAIR_IDENTITY_COOLING_CATALOG_20261020), offered on Cooling 1.2 only.
    from carbon.backbone_catalog import listing

    offered = {e["catalog_id"]: e for e in listing.entries(COOLING, "1.2")}
    assert set(offered) == {
        "cooling.neuralop.FNO",
        "cooling.neuralop.TFNO",
        "cooling.neuralop.UQNO",
        "cooling.physicsnemo.FullyConnected",
        "cooling.transolver",
    }
    for item in offered.values():
        assert item["challenges"] == [{"id": COOLING, "version": "1.2"}]
        assert item["settings_schema"] == "carbon-candidate-levers-cooling-v1"
