"""King of the hill on a pack set (OWNER-FULL-EXAM-BANK-01, item 3b; the Validator
approved the draft): the evaluation key is the set key plus the batch packs, the
comparison logic is unchanged, and the baseline is graded on the same set.

All pairs are synthetic fixtures shaped like the stored per-batch private
evaluations; no model, solver or reference runs."""

import json
from copy import deepcopy

import pytest

from carbon.battery.pool_store import PoolStore, StateError
from carbon.challenge_validator import bank_promotion as bp
from carbon.challenge_validator import koth_registry
from carbon.challenge_validator.interface import digest

PIN = digest("registered source receipt")
STATE = digest("retained state")
SET_KEY = digest("pack set")
PACKS = [digest("pack one"), digest("pack two")]
V4_SCORING = "carbon.scoring.dual-benchmark-pack.v4"


def per_batch(pack, total=0.8, status=bp.SCORED, entry=None, **override):
    evidence = {
        "schema": bp.PAIRED_BINDING,
        "scope": "PRIVATE_OPERATOR_DEVELOPMENT",
        "status": "BOUND_DEVELOPMENT_ONLY",
        "official_score": False,
        "official_eligible": False,
        "challenge": "electric-motor-magnetics",
        "challenge_version": "1.0",
        "evaluation_version": "motor-dual-sealed-batch-30-v1",
        "evaluation_version_digest": digest("evaluation version"),
        "entry_id": entry or digest(["entry", pack]),
        "state_digest": STATE,
        "model_result_digest": digest(["model", pack]),
        "score_result_digest": digest(["score", pack]),
        "source_receipt_sha256": PIN,
        "dual_measurement_receipt_sha256": digest(["dual", pack]),
        "evaluation_pack_digest": pack,
        "score_compatibility": {
            "score_pack_digest": digest(["score pack", pack]),
            "scoring_version": V4_SCORING,
            "execution_profile_digest": digest(["profile", pack]),
        },
        "registration_digest": digest("registration"),
        "measurement_contract_digest": digest("contract"),
        "producer_digest": digest("producer"),
        "common_mask_digest": digest(["mask", pack]),
        "ordered_query_material_digest": digest(["query", pack]),
        "reference_rows_digest": digest(["rows", pack]),
        "reference_coverage_digest": digest(["coverage", pack]),
        "reference_coverage": {"RESOLVED": 30, "UNRESOLVED": 0, "FAILED_INFRA": 0},
        "inference_pair_sha256": digest(["pair", pack]),
        "model_p": {
            "score_status": status,
            "total_score": total if status == bp.SCORED else None,
        },
    }
    evidence.update(override)
    return {
        "schema": "carbon.challenge-validator.private-evaluation-cache.v1",
        "submission_id": "rtsk_a",
        "owner": {"hotkey": "hk", "request_digest": digest("request")},
        "recipe_digest": digest("recipe"),
        "evaluation_key": bp.private_evaluation_key(evidence),
        "evidence": evidence,
    }


def two(first=0.8, second=0.6, **override):
    return [per_batch(PACKS[0], first, **override), per_batch(PACKS[1], second)]


# --- the derived set binding ---------------------------------------------------------


def test_the_set_total_is_the_equal_weight_mean_of_the_batch_totals():
    evidence = bp.build_set_evidence(SET_KEY, two(0.8, 0.6))
    assert evidence["schema"] == bp.SET_BINDING
    assert evidence["model_p"] == {
        "score_status": bp.SCORED,
        "total_score": pytest.approx(0.7),
    }
    assert [b["evaluation_pack_digest"] for b in evidence["batches"]] == PACKS
    # The first batch's entry id: the baseline's own entry stays a leg-minimum source.
    assert evidence["entry_id"] == two()[0]["evidence"]["entry_id"]
    assert (
        evidence["official_score"] is False and evidence["official_eligible"] is False
    )


def test_a_gate_failure_on_any_batch_fails_the_set_with_no_total():
    bodies = [
        per_batch(PACKS[0], 0.9),
        per_batch(PACKS[1], status="MANDATORY_GATE_FAILED"),
    ]
    evidence = bp.build_set_evidence(SET_KEY, bodies)
    assert evidence["model_p"] == {
        "score_status": "MANDATORY_GATE_FAILED",
        "total_score": None,
    }


@pytest.mark.parametrize("status", ["FAILED_INFRA", "INDETERMINATE_EVIDENCE", "OTHER"])
def test_an_unmeasured_batch_refuses_never_a_partial_mean(status):
    bodies = [per_batch(PACKS[0], 0.9), per_batch(PACKS[1], status=status)]
    with pytest.raises(StateError, match="set_batch_not_measured"):
        bp.build_set_evidence(SET_KEY, bodies)


@pytest.mark.parametrize(
    "field,value",
    [
        ("challenge_version", "1.1"),
        ("evaluation_version", "motor-dual-sealed-batch-30-v2"),
        ("state_digest", digest("another model")),
        ("source_receipt_sha256", digest("another pin")),
    ],
)
def test_batches_of_different_models_or_exams_are_refused(field, value):
    bodies = [per_batch(PACKS[0]), per_batch(PACKS[1], **{field: value})]
    with pytest.raises(StateError, match="set_batches_disagree"):
        bp.build_set_evidence(SET_KEY, bodies)


def test_a_repeated_pack_an_empty_set_and_a_forged_body_are_refused():
    with pytest.raises(StateError, match="set_batches_disagree"):
        bp.build_set_evidence(SET_KEY, [per_batch(PACKS[0]), per_batch(PACKS[0])])
    with pytest.raises(StateError, match="set_evidence_invalid"):
        bp.build_set_evidence(SET_KEY, [])
    with pytest.raises(StateError, match="set_evidence_invalid"):
        bp.build_set_evidence("not-a-digest", two())
    forged = two()
    forged[0]["evaluation_key"] = digest("another key")
    with pytest.raises(StateError, match="set_batch_evidence_invalid"):
        bp.build_set_evidence(SET_KEY, forged)


def test_the_key_follows_the_set_and_its_packs_not_the_models_result():
    one = bp.private_evaluation_key(bp.build_set_evidence(SET_KEY, two(0.8, 0.6)))
    same_exam_other_total = bp.private_evaluation_key(
        bp.build_set_evidence(SET_KEY, two(0.4, 0.3))
    )
    # A contender and an incumbent on the same set meet under one key.
    assert one == same_exam_other_total
    # A rotated set (a new key) is a different key, as is a different pack list.
    assert one != bp.private_evaluation_key(
        bp.build_set_evidence(digest("rotated set"), two())
    )
    other_packs = [per_batch(PACKS[0]), per_batch(digest("pack three"))]
    assert one != bp.private_evaluation_key(bp.build_set_evidence(SET_KEY, other_packs))


# --- the comparison is unchanged -------------------------------------------------------


def comparator_for(bodies_evidence, noise=0.05, baseline=0.4, sources=()):
    return {
        "schema": bp.COMPARATOR_SCHEMA,
        "scope": "DEVELOPMENT",
        "challenge": "electric-motor-magnetics",
        "score_pack_digest": bodies_evidence["score_compatibility"][
            "score_pack_digest"
        ],
        "rebuild_noise": {"value": noise, "measurement_digest": digest("noise")},
        "ties": "incumbent_keeps",
        "minimum_source_entry_ids": list(sources),
        "baseline_total": baseline,
    }


def set_body(submission, first, second):
    evidence = bp.build_set_evidence(SET_KEY, two(first, second))
    return {
        "submission_id": submission,
        "evaluation_key": bp.private_evaluation_key(evidence),
        "evidence": evidence,
    }


def pair(candidate, incumbent):
    return {
        "scope": "PRIVATE_OPERATOR_DEVELOPMENT",
        "evaluation_key": candidate["evaluation_key"],
        "expected_incumbent": None if incumbent is None else incumbent["submission_id"],
        "candidate": candidate,
        "incumbent": incumbent,
    }


def test_a_set_contender_meets_the_incumbent_under_the_unchanged_rules():
    king = set_body("king", 0.8, 0.6)  # set total 0.7
    rule = comparator_for(king["evidence"])
    better = set_body("better", 0.9, 0.7)  # 0.8
    tie = set_body("tie", 0.74, 0.7)  # 0.72, within the 0.05 noise
    assert bp.compare_private_pair(pair(better, king), rule)["outcome"] == bp.CHALLENGER
    assert (
        bp.compare_private_pair(pair(tie, king), rule)["outcome"] == bp.INCUMBENT_KEEPS
    )
    first = bp.compare_private_pair(pair(better, None), rule)
    assert first["outcome"] == bp.FIRST_INCUMBENT


def test_a_set_contender_must_beat_the_baseline_graded_on_the_same_set():
    weak = set_body("weak", 0.45, 0.4)  # 0.425, not beyond baseline 0.4 + noise 0.05
    rule = comparator_for(weak["evidence"], baseline=0.4, noise=0.05)
    assert bp.compare_private_pair(pair(weak, None), rule)["outcome"] == bp.NO_WINNER


def test_the_baseline_entry_of_a_set_never_contends():
    baseline = set_body("baseline", 0.9, 0.9)
    rule = comparator_for(
        baseline["evidence"], sources=[baseline["evidence"]["entry_id"]]
    )
    result = bp.compare_private_pair(pair(baseline, None), rule)
    assert result["reason"] == "leg_minimum_source_not_a_contender"


def test_a_comparator_for_another_set_is_not_for_this_evaluation():
    body = set_body("c", 0.9, 0.7)
    rule = comparator_for(body["evidence"])
    rule["score_pack_digest"] = digest("another set's packs")
    with pytest.raises(StateError, match="comparator_not_for_this_evaluation"):
        bp.compare_private_pair(pair(body, None), rule)


# --- the baseline on the same set ---------------------------------------------------------


def score_pack(pack, a, d, weight=0.5):
    return {
        "pack_digest": digest(["score pack", pack]),
        "legs": {"A": {"minimum": a}, "D": {"minimum": d}},
        "value_weight": weight,
        "combination": "weighted_arithmetic_mean",
    }


def accuracy(*entries):
    return {"leg_minimum_source": {"entry_ids": list(entries)}}


def test_the_set_baseline_is_the_equal_weight_mean_of_the_batch_baselines(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(
        "carbon.scoring.physical_dual_pack.minimum_source_entry_ids",
        lambda definition: definition["leg_minimum_source"]["entry_ids"],
    )
    path = tmp_path / "noise.json"
    path.write_text(json.dumps({"schema": koth_registry.SCHEMA, "challenges": {}}))
    e1, e2 = digest("baseline one"), digest("baseline two")
    rule = koth_registry.comparator_for_set(
        "electric-motor-magnetics",
        [score_pack(PACKS[0], 0.2, 0.4), score_pack(PACKS[1], 0.4, 0.6)],
        [accuracy(e1), accuracy(e1, e2)],
        path=path,
    )
    assert rule["baseline_total"] == pytest.approx((0.3 + 0.5) / 2)
    assert rule["minimum_source_entry_ids"] == sorted({e1, e2})
    # The set's score digest is its packs', whatever their order.
    flipped = koth_registry.comparator_for_set(
        "electric-motor-magnetics",
        [score_pack(PACKS[1], 0.4, 0.6), score_pack(PACKS[0], 0.2, 0.4)],
        [accuracy(e1, e2), accuracy(e1)],
        path=path,
    )
    assert flipped["score_pack_digest"] == rule["score_pack_digest"]
    # One batch without leg minimums: the baseline floor is unregistered.
    missing = koth_registry.comparator_for_set(
        "electric-motor-magnetics",
        [score_pack(PACKS[0], 0.2, 0.4), score_pack(PACKS[1], None, None)],
        [accuracy(e1), accuracy(e2)],
        path=path,
    )
    assert missing["baseline_total"] is None
    with pytest.raises(ValueError):
        koth_registry.comparator_for_set("electric-motor-magnetics", [], [], path=path)


# --- the pool store files a set evaluation from stored batch evaluations ---------------------


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(
        PoolStore,
        "_private_model",
        staticmethod(
            lambda db, submission_id, evidence, recipe_digest: {
                "hotkey": "hk",
                "request_digest": digest("request"),
            }
        ),
    )
    return PoolStore(tmp_path / "pool.sqlite", clock=lambda: 123.0)


def seed(store, bodies):
    for body in bodies:
        key = body["evaluation_key"]
        op = store._bank_operation("private_evaluation.v1", body["submission_id"], key)
        with store.transaction() as db:
            db.execute(
                "INSERT INTO operations VALUES(?,?,?,?)",
                (
                    op,
                    "private_evaluation.v1",
                    "BOUND_DEVELOPMENT_ONLY",
                    json.dumps(body, sort_keys=True, separators=(",", ":")),
                ),
            )


def test_the_store_files_a_set_evaluation_derived_from_the_stored_batches(store):
    seed(store, two(0.8, 0.6))
    promotion = bp.BankPromotion(store, registered_source_receipt_sha256=PIN)
    filed = promotion.retain_set("rtsk_a", SET_KEY, PACKS)
    assert filed["evidence"]["schema"] == bp.SET_BINDING
    assert filed["evidence"]["model_p"]["total_score"] == pytest.approx(0.7)
    assert filed["evaluation_key"] == bp.private_evaluation_key(filed["evidence"])
    # Filing again is idempotent, and the pair lookup finds it under the set key.
    assert promotion.retain_set("rtsk_a", SET_KEY, PACKS) == filed
    found = promotion.private_pair("rtsk_a", filed["evaluation_key"])
    assert found["candidate"]["evidence"]["schema"] == bp.SET_BINDING
    assert found["incumbent"] is None


def test_a_missing_batch_evaluation_files_nothing(store):
    seed(store, [per_batch(PACKS[0], 0.8)])
    promotion = bp.BankPromotion(store, registered_source_receipt_sha256=PIN)
    with pytest.raises(StateError, match="set_batch_evaluation_missing"):
        promotion.retain_set("rtsk_a", SET_KEY, PACKS)


def test_an_infrastructure_batch_files_nothing(store):
    seed(store, [per_batch(PACKS[0], 0.8), per_batch(PACKS[1], status="FAILED_INFRA")])
    promotion = bp.BankPromotion(store, registered_source_receipt_sha256=PIN)
    with pytest.raises(StateError, match="set_batch_not_measured"):
        promotion.retain_set("rtsk_a", SET_KEY, PACKS)


def test_a_batch_evaluation_under_another_pin_is_refused(store):
    seed(store, two())
    other = bp.BankPromotion(
        store, registered_source_receipt_sha256=digest("other pin")
    )
    with pytest.raises(StateError, match="evaluation_source_changed"):
        other.retain_set("rtsk_a", SET_KEY, PACKS)


def test_a_batch_stored_for_another_submission_is_not_used(store):
    bodies = two()
    for body in bodies:
        body["submission_id"] = "rtsk_other"
    seed(store, bodies)
    promotion = bp.BankPromotion(store, registered_source_receipt_sha256=PIN)
    with pytest.raises(StateError, match="set_batch_evaluation_missing"):
        promotion.retain_set("rtsk_a", SET_KEY, PACKS)


def test_two_stored_evaluations_of_one_batch_pack_are_ambiguous(store):
    first = per_batch(PACKS[0], 0.8)
    second = per_batch(
        PACKS[0],
        0.7,
        score_compatibility={
            **deepcopy(first["evidence"]["score_compatibility"]),
            "execution_profile_digest": digest("another profile"),
        },
    )
    seed(store, [first, second, per_batch(PACKS[1], 0.6)])
    promotion = bp.BankPromotion(store, registered_source_receipt_sha256=PIN)
    with pytest.raises(StateError, match="set_batch_evaluation_missing"):
        promotion.retain_set("rtsk_a", SET_KEY, PACKS)


def test_a_set_of_unequal_sized_batches_is_refused():
    small = per_batch(PACKS[0])
    big = per_batch(
        PACKS[1],
        reference_coverage={"RESOLVED": 40, "UNRESOLVED": 0, "FAILED_INFRA": 0},
    )
    with pytest.raises(bp.StateError, match="set_batches_disagree"):
        bp.build_set_evidence(SET_KEY, [small, big])


def test_the_set_evidence_carries_each_batchs_case_count():
    evidence = bp.build_set_evidence(SET_KEY, two())
    assert [b["case_count"] for b in evidence["batches"]] == [30, 30]
    forged = {
        **evidence,
        "batches": [
            {**evidence["batches"][0], "case_count": 31},
            evidence["batches"][1],
        ],
    }
    with pytest.raises(bp.StateError):
        bp.private_evaluation_key(forged)
