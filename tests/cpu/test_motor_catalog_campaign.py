"""Motor 1.2, the backbone-catalog campaign (OWNER-BACKBONE-CATALOG-01):
composed under its own key, its catalog discoverable, its frozen recipe
submitted to the signed construction receiver and judged there."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest

from carbon.challenge_registry.campaigns import campaign_for
from carbon.challenge_registry.motor import catalog_recipe
from carbon.development_session import direct_submission
from carbon.development_session.research_campaign import OperationRefused
from carbon.motor.research import MotorCatalogMaterial, MotorPublicMaterial

MOTOR = "electric-motor-magnetics"
RECEIVER = "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY"


def test_each_motor_version_has_its_own_campaign():
    old = campaign_for({"id": MOTOR, "version": "1.0"})
    new = campaign_for({"id": MOTOR, "version": "1.2"})
    assert old.key.version == "1.0" and old.construction_kit is None
    assert new.key.version == "1.2"
    assert new.construction_kit()["version"] == "1.2"
    assert new.feedback_schema == "carbon.motor.permitted-feedback.v1"


def test_the_catalog_and_its_kit_are_public_material_on_1_2_only(tmp_path):
    from carbon.development_session.research_tasks import public_material_names

    assert "catalog" in public_material_names(MotorCatalogMaterial("."))
    assert "catalog" not in public_material_names(MotorPublicMaterial("."))
    stored = {}
    workspace = SimpleNamespace(put=lambda name, body: stored.__setitem__(name, body))
    reply = MotorCatalogMaterial(".")("catalog", workspace)
    assert reply["document"]["ready_recipe"] == catalog_recipe()
    assert set(reply["document"]["entries"]) >= {"neuralop.FNO", "transolver"}


def _prepared(tmp_path, args, epoch=1):
    folder = tmp_path / f"epoch-{epoch}"
    folder.mkdir(parents=True)
    recipe = catalog_recipe("neuralop.FNO")
    (folder / "selected-recipe.json").write_text(json.dumps({"strategy": recipe}))
    connection = SimpleNamespace(miner_key=object(), chain_context=object())
    ledger = SimpleNamespace(root=tmp_path)
    return (
        SimpleNamespace(
            ledger=ledger,
            owner="alice",
            args=args,
            sdk=SimpleNamespace(connection=connection),
        ),
        recipe,
    )


def test_a_frozen_catalog_recipe_is_submitted_and_its_judgement_kept(
    tmp_path, monkeypatch
):
    from carbon.motor import campaign as motor

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
        motor,
        "record_verdict",
        lambda ledger, owner, epoch, feedback: kept.append(feedback),
    )
    args = SimpleNamespace(
        intakes={MOTOR: "http://127.0.0.1:8769"}, receivers={MOTOR: RECEIVER}
    )
    prepared, recipe = _prepared(tmp_path, args)
    campaign = campaign_for({"id": MOTOR, "version": "1.2"})
    feedback = asyncio.run(campaign.evaluate(prepared, 1, recipe))
    ((url, kw),) = sent
    assert url == "http://127.0.0.1:8769" and kw["receiver"] == RECEIVER
    assert kw["recipe"].to_dict() == recipe
    assert feedback["result"] == {"state": "RECONSTRUCTED"} and kept == [feedback]


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
    def fail(*a, **k):
        raise raised

    monkeypatch.setattr(direct_submission, "submit_and_wait", fail)
    args = SimpleNamespace(
        intakes={MOTOR: "http://127.0.0.1:8769"}, receivers={MOTOR: RECEIVER}
    )
    prepared, recipe = _prepared(tmp_path, args)
    campaign = campaign_for({"id": MOTOR, "version": "1.2"})
    with pytest.raises(OperationRefused, match=code):
        asyncio.run(campaign.evaluate(prepared, 1, recipe))


def test_without_a_receiver_the_submit_is_unconfigured_and_1_0_stays_closed(tmp_path):
    prepared, recipe = _prepared(tmp_path, SimpleNamespace(intakes={}, receivers={}))
    with pytest.raises(OperationRefused, match="construction_intake_unconfigured"):
        asyncio.run(
            campaign_for({"id": MOTOR, "version": "1.2"}).evaluate(prepared, 1, recipe)
        )
    with pytest.raises(OperationRefused, match="motor_validator_not_served"):
        asyncio.run(
            campaign_for({"id": MOTOR, "version": "1.0"}).evaluate(prepared, 1, recipe)
        )


def test_1_2_keeps_neural_operators_unsupported_but_for_carbons_tested_ones():
    from carbon.challenge_registry import describe

    listed = {c["id"]: c for c in describe(MOTOR, "1.2")["unsupported"]}
    assert len(listed) == 5
    assert listed["model_family.neural_operator"]["blocker"] == (
        "only Carbon-tested ones, by catalog id; miner-authored neural operators are not rebuildable"
    )


def test_1_2_is_graded_by_1_1s_evaluation_versions():
    # The scoring adapter's 1.2 entry (1.1's dev bank v3) is the Motor 1.2
    # adapter's own (ScoreLab, tests/cpu/test_step2_adapter_versions.py).
    from carbon.challenge_kit import motor_sealed_pack, physical_pack
    from carbon.challenge_validator import motor_sealed

    assert (
        physical_pack.PACK_VERSIONS[MOTOR, "1.2"]
        == "motor-normal-construction-development-3"
    )
    assert motor_sealed.EVALUATION_VERSION == "motor-dual-sealed-batch-30-v1"
    assert "1.2" in motor_sealed.SERVED_VERSIONS
    # 1.2 passes the version check (then the bogus document is refused as such).
    with pytest.raises(motor_sealed_pack.SealedPackRefused) as refused:
        motor_sealed_pack.sealed_bank({}, [], version="1.2")
    assert refused.value.code == "motor_sealed_document_malformed"
    with pytest.raises(motor_sealed_pack.SealedPackRefused) as refused:
        motor_sealed_pack.sealed_bank({}, [], version="9.9")  # 1.3 is served (v7)
    assert refused.value.code == "motor_sealed_version"
    assert "1.3" in motor_sealed.SERVED_VERSIONS
