"""A practiced direct recipe freezes its exact source without legacy compilation."""

import asyncio
import json
from types import SimpleNamespace

import pytest
from test_miner_freeze_submit import prepared

from carbon.battery.construction_kit import construction_kit
from carbon.development_session import construction_recipe, research_campaign
from carbon.development_session.profile import canonical, digest


def _recipe(kit):
    return {
        "schema": construction_recipe.SCHEMA,
        "challenge": kit,
        "source": {"kind": "graph", "submission_digest": "sha256:" + "a" * 64},
        "procedure": {
            "entrypoint": None,
            "configuration": {"graph_parameters": {"width": 13}},
            "train_use": {"subset": "all"},
            "initial_state": None,
        },
        "output": {
            "format": "carbon.numeric-graph.v1",
            "interface_digest": kit["interface_digest"],
        },
    }


def _bundle_recipe(kit):
    recipe = _recipe(kit)
    recipe["source"] = {
        "kind": "bundle",
        "bundle_ref": {
            "schema": "carbon.library-bundle-ref.v1",
            "bundle_digest": "sha256:" + "b" * 64,
            "language": "python",
            "runtime_profile_id": "jax-cuda13-py311",
            "environment_digest": "sha256:" + "c" * 64,
        },
    }
    recipe["procedure"]["entrypoint"] = {"module": "candidate", "name": "build"}
    return recipe


def _campaign(tmp_path, monkeypatch, *, practiced=True):
    value, _ = prepared(tmp_path, monkeypatch, practiced=())
    kit = construction_kit()
    strategy = _recipe(kit)
    value.manifest.update(
        {
            "challenge": {"id": kit["id"], "version": kit["version"]},
            "construction_mode": "direct",
        }
    )
    (value.ledger.root / "campaign-manifest.json").write_bytes(
        canonical(value.manifest)
    )
    value.campaign = SimpleNamespace(
        construction_kit=lambda: kit,
        construction_reconstruct=lambda *args, **kwargs: None,
    )
    if practiced:
        body = canonical({"provenance": "BATTERY_PUBLIC_PRACTICE", "recipe": strategy})
        with value.ledger.db() as db:
            db.execute(
                "INSERT INTO research_results VALUES(?,?,?,?)",
                ("miner", "direct-practice", body, digest(body)),
            )
    return value, strategy


def test_direct_freeze_keeps_exact_recipe_and_source_bytes(tmp_path, monkeypatch):
    value, strategy = _campaign(tmp_path, monkeypatch)
    envelope = b'{"schema":"fixture-direct-envelope"}'
    monkeypatch.setattr(
        construction_recipe,
        "graph_envelope_from_workspace",
        lambda ledger, owner, recipe: envelope,
    )
    result = asyncio.run(
        research_campaign.freeze_candidate(
            value, strategy=strategy, reason="practice passed"
        )
    )
    folder = value.ledger.root / "epoch-1"
    selected = json.loads((folder / "selected-recipe.json").read_bytes())
    assert result == {"epoch": 1, "selection": selected}
    assert selected["schema"] == "carbon.direct-selected-recipe.v1"
    assert selected["strategy"] == strategy
    assert (
        selected["strategy_hash"]
        == construction_recipe.ConstructionRecipe.from_dict(strategy).digest
    )
    assert selected["source_envelope_digest"] == digest(envelope)
    assert selected["final_evidence"] is False
    assert "construction_level" not in selected
    assert "contract_digest" not in selected
    assert (folder / "direct-source-envelope.json").read_bytes() == envelope


def test_direct_bundle_freeze_keeps_exact_source_ref_without_graph_envelope(
    tmp_path, monkeypatch
):
    value, _ = _campaign(tmp_path, monkeypatch, practiced=False)
    strategy = _bundle_recipe(construction_kit())
    body = canonical({"provenance": "BATTERY_PUBLIC_PRACTICE", "recipe": strategy})
    with value.ledger.db() as db:
        db.execute(
            "INSERT INTO research_results VALUES(?,?,?,?)",
            ("miner", "direct-bundle-practice", body, digest(body)),
        )
    value.campaign.construction_bundle_material = lambda: None
    result = asyncio.run(
        research_campaign.freeze_candidate(
            value, strategy=strategy, reason="bundle practice passed"
        )
    )
    folder = value.ledger.root / "epoch-1"
    selected = json.loads((folder / "selected-recipe.json").read_bytes())
    assert result["selection"] == selected
    assert selected["schema"] == "carbon.direct-selected-recipe.v2"
    assert selected["strategy"] == strategy
    assert (
        selected["construction_source_digest"]
        == strategy["source"]["bundle_ref"]["bundle_digest"]
    )
    assert "source_envelope_digest" not in selected
    assert not (folder / "direct-source-envelope.json").exists()


def test_direct_bundle_freeze_requires_challenge_bundle_adapter(tmp_path, monkeypatch):
    value, _ = _campaign(tmp_path, monkeypatch, practiced=False)
    strategy = _bundle_recipe(construction_kit())
    body = canonical({"provenance": "BATTERY_PUBLIC_PRACTICE", "recipe": strategy})
    with value.ledger.db() as db:
        db.execute(
            "INSERT INTO research_results VALUES(?,?,?,?)",
            ("miner", "direct-bundle-practice", body, digest(body)),
        )
    with pytest.raises(
        research_campaign.OperationRefused, match="construction_reconstruction_unserved"
    ):
        asyncio.run(
            research_campaign.freeze_candidate(
                value, strategy=strategy, reason="adapter unavailable"
            )
        )
    assert not (value.ledger.root / "epoch-1" / "selected-recipe.json").exists()


def test_direct_freeze_requires_exact_practice_and_kit(tmp_path, monkeypatch):
    value, strategy = _campaign(tmp_path, monkeypatch, practiced=False)
    with pytest.raises(
        research_campaign.OperationRefused, match="practice_result_required"
    ):
        asyncio.run(
            research_campaign.freeze_candidate(value, strategy=strategy, reason="r")
        )
    assert not (value.ledger.root / "epoch-1" / "selected-recipe.json").exists()
    body = canonical({"provenance": "BATTERY_PUBLIC_PRACTICE", "recipe": strategy})
    with value.ledger.db() as db:
        db.execute(
            "INSERT INTO research_results VALUES(?,?,?,?)",
            ("miner", "direct-practice", body, digest(body)),
        )
    value.campaign.construction_kit = lambda: {
        **construction_kit(),
        "train_digest": "sha256:" + "0" * 64,
    }
    with pytest.raises(
        research_campaign.OperationRefused, match="construction_recipe_binding_mismatch"
    ):
        asyncio.run(
            research_campaign.freeze_candidate(value, strategy=strategy, reason="r")
        )
    assert not (value.ledger.root / "epoch-1" / "selected-recipe.json").exists()


def test_direct_freeze_rejects_legacy_host_directory(tmp_path, monkeypatch):
    value, strategy = _campaign(tmp_path, monkeypatch)
    with pytest.raises(
        research_campaign.OperationRefused,
        match="construction_source_from_workspace_required",
    ):
        asyncio.run(
            research_campaign.freeze_candidate(
                value,
                strategy=strategy,
                reason="r",
                level4_directory="host-path-must-not-enter-direct-mode",
            )
        )
    assert not (value.ledger.root / "epoch-1" / "selected-recipe.json").exists()


def test_direct_smoke_does_not_rewrite_recipe_through_legacy_hook(
    tmp_path, monkeypatch
):
    value, strategy = _campaign(tmp_path, monkeypatch)
    with pytest.raises(
        research_campaign.OperationRefused, match="smoke_practice_unavailable"
    ):
        asyncio.run(
            research_campaign.practice_recipe(
                value,
                strategy=strategy,
                hypothesis="direct graph",
                expected_effect="check worker",
                identity="direct-smoke",
                mode="smoke",
            )
        )
