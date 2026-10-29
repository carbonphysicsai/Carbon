"""Each miner's own per-part feedback (OWNER-DOOR-LOOKUPS-AND-PART-FEEDBACK-01;
PART_FEEDBACK_GRANULARITY_20261029 sections 1, 2 and 4): the v4 Ladder document is
v3 plus ``parts`` (the A and D halves and each registered component, on the part step
with hysteresis), ``gates`` (pass or fail) and ``minimums_missed`` (names only); it is
built field by field from an allow-list; a Challenge serves it only after its custody
leak attack is registered; v1, v2 and v3 rows never change."""

from __future__ import annotations

import json
import os
from decimal import Decimal

import pytest

from carbon.challenge_validator import part_feedback
from carbon.challenge_validator.ladder_store import (
    LadderStore,
    LadderStoreRefused,
    checked,
)
from carbon.challenge_validator.ledger import AttemptLedger
from carbon.registry.model import ChallengeKey
from carbon.scoring import grade_feedback as gf

MOTOR = ChallengeKey("electric-motor-magnetics", "1.4")
GATES = ("native_motor_valid", "complete_fixed_coverage")
REGISTRY = {"A": ["acc_mean", "acc_worst"], "D": ["closeness", "honesty"]}
RECIPE = "sha256:" + "d" * 64
EXAM = "sha256:" + "e" * 64
SECRETS = (
    "per-case-secret",
    "case-id-77",
    "target-id-9",
    "draw-id-4",
    "picked-design-secret",
    "reference-secret",
    "pool-secret",
    "set-split-secret",
    "feasible-count-secret",
)


def _graded(a=0.62, d=0.41, comps=None, **extra):
    total = 0.5 * a + 0.5 * d
    return {
        "artifact_digest": "sha256:" + "a" * 64,
        "status": "SCORED_DEVELOPMENT_CANDIDATE",
        "score": total,
        "legs": {"A": a, "D": d},
        "gates": {g: "PASS" for g in GATES},
        "components": (
            {"acc_mean": 0.66, "acc_worst": 0.58, "closeness": 0.44, "honesty": 0.38}
            if comps is None
            else comps
        ),
        **extra,
    }


def _feedback(graded, **kwargs):
    arguments = {
        "best": None,
        "exam_version": "motor-exam-1",
        "gate_registry": GATES,
        "rebuild_noise": None,
        "recipe_digest": RECIPE,
        "epoch": 3,
        "leg_minimums": {"A": None, "D": None},
        "parts_registry": REGISTRY,
    }
    arguments.update(kwargs)
    return gf.ladder_feedback(graded, **arguments)


def _multiple(value, grid):
    return (Decimal(repr(value)) / Decimal(repr(grid))) % 1 == 0


# ---- the part step and the hysteresis (section 2) --------------------------


def test_the_part_step_is_never_finer_than_twice_the_total_step():
    assert gf.part_step(None) == 0.05
    assert gf.part_step(0.03) == pytest.approx(0.06)
    assert gf.part_step(0.2) == pytest.approx(0.4)
    for noise in (None, 0.0, 0.01, 0.02, 0.025, 0.5):
        assert gf.part_step(noise) >= 2 * gf.step(noise)


def test_a_part_is_floored_to_the_grid_and_moves_only_by_a_full_step():
    grid = 0.05
    assert gf.shown_part(0.52, None, grid) == 0.5
    # Within a step of what was shown: the shown value repeats, up or down.
    assert gf.shown_part(0.54, 0.5, grid) == 0.5
    assert gf.shown_part(0.46, 0.5, grid) == 0.5
    # A full step (exactly, in exact decimal arithmetic) moves it.
    assert gf.shown_part(0.55, 0.5, grid) == 0.55
    assert gf.shown_part(0.45, 0.5, grid) == 0.45
    assert gf.shown_part(0.44, 0.5, grid) == 0.4
    assert gf.shown_part(0.0, 0.1, grid) == 0.0


def test_a_grid_edge_cannot_be_flipped_by_a_tiny_change():
    grid = 0.05
    shown = gf.shown_part(0.5501, 0.5, grid)
    assert shown == 0.55
    # Plain rounding would drop back to 0.5 at 0.5499; hysteresis repeats 0.55.
    assert gf.shown_part(0.5499, shown, grid) == 0.55
    assert gf.shown_part(0.5501, shown, grid) == 0.55
    # Only a real regression of a full step shows.
    assert gf.shown_part(0.4999, shown, grid) == 0.45


def test_a_non_finite_part_is_refused():
    for bad in (float("nan"), float("inf"), None, "0.5"):
        with pytest.raises(gf.LadderFeedbackRefused):
            gf.shown_part(bad, None, 0.05)
    with pytest.raises(gf.LadderFeedbackRefused):
        gf.shown_part(0.5, float("nan"), 0.05)


# ---- each status's shape (section 1) ----------------------------------------


def test_a_result_that_counts_shows_total_parts_and_gates():
    document = _feedback(_graded())
    assert set(document) == gf.FIELDS_V4
    assert document["schema"] == gf.SCHEMA_V4
    assert document["status"] == "IMPROVED"
    assert document["total"] == 0.5  # the v3 rule: floored to the 0.02 step
    assert document["parts"] == {
        "A": 0.6,
        "D": 0.4,
        "components": {
            "acc_mean": 0.65,
            "acc_worst": 0.55,
            "closeness": 0.4,
            "honesty": 0.35,
        },
    }
    assert document["gates"] == {g: "pass" for g in GATES}
    assert document["minimums_missed"] == [] and document["gate_names"] == []
    for value in (
        document["parts"]["A"],
        document["parts"]["D"],
        *document["parts"]["components"].values(),
    ):
        assert _multiple(value, 0.05)


def test_no_improvement_keeps_the_ladder_total_but_the_parts_follow_their_own_rule():
    first = _feedback(_graded())
    again = _feedback(
        _graded(a=0.625, d=0.41),
        best=first,
        parts_state=first["parts"],
    )
    assert again["status"] == "NO_IMPROVEMENT"
    assert again["total"] == first["total"]
    # 0.625 is within one part step of the shown 0.6: it repeats.
    assert again["parts"]["A"] == 0.6
    assert again["gates"] == {g: "pass" for g in GATES}


def test_a_failed_gate_shows_the_gates_and_no_number():
    graded = _graded()
    graded.update(
        status="MANDATORY_GATE_FAILED",
        gates={"native_motor_valid": "PASS", "complete_fixed_coverage": "FAIL"},
    )
    document = _feedback(graded)
    assert set(document) == gf.FIELDS_V4
    assert document["status"] == "GATE_FAILED"
    assert document["total"] is None and document["parts"] is None
    assert document["gates"] == {
        "native_motor_valid": "pass",
        "complete_fixed_coverage": "fail",
    }
    assert document["gate_names"] == ["complete_fixed_coverage"]
    assert document["minimums_missed"] == []


def test_a_result_that_does_not_count_shows_its_reason_and_the_leg_name_only():
    graded = _graded(a=0.1)
    graded["status"] = "REQUIRED_LEG_MINIMUM_FAILED"
    document = _feedback(graded, leg_minimums={"A": 0.3, "D": None})
    assert set(document) == gf.FIELDS_V4_NOT_SCORED
    assert document["status"] == "NOT_SCORED"
    assert document["reason"] == "LEG_MINIMUM_FAILED" and document["leg"] == "A"
    assert document["minimums_missed"] == ["A"]
    assert document["total"] is None and document["parts"] is None
    assert document["gates"] is None and document["gate_names"] == []
    # No number or margin anywhere in it.
    assert "0.3" not in json.dumps(document) and "0.1" not in json.dumps(document)
    other = _graded()
    other["status"] = "FAILED_INFRA"
    document = _feedback(other)
    assert document["reason"] == "FAILED_INFRA" and document["leg"] is None
    assert document["minimums_missed"] == []


# ---- the allow-list (section 1, never shown) -------------------------------


def test_nothing_on_the_never_shown_list_can_appear_even_when_planted():
    planted = {
        "per_case": {"case-id-77": 0.123456789},
        "case_ids": ["case-id-77"],
        "target_ids": ["target-id-9"],
        "draw_ids": ["draw-id-4"],
        "picked_design": "picked-design-secret",
        "reference_values": [0.987654321],
        "pool": "pool-secret",
        "set_split": {"set_a": 0.7, "set_b": 0.3, "note": "set-split-secret"},
        "feasible_targets": "feasible-count-secret",
        "measured_legs_before_outcome_policy": {"A": 0.123456789, "D": 0.987654321},
        "decision_outcome": "VERIFIED_FEASIBLE",
        "per-case-secret": 1,
    }
    graded = _graded(
        comps={
            "acc_mean": 0.66,
            "acc_worst": 0.58,
            "closeness": 0.44,
            "honesty": 0.38,
            "unregistered_metric": 0.7777777,
            "per-case-secret": 0.1234567,
        },
        **planted,
    )
    document = _feedback(graded)
    assert set(document) == gf.FIELDS_V4
    assert set(document["parts"]["components"]) == set(REGISTRY["A"] + REGISTRY["D"])
    text = json.dumps(document)
    for secret in SECRETS + ("unregistered_metric", "0.123456789", "0.987654321"):
        assert secret not in text, secret
    assert "0.7777777" not in text and "0.66" not in text  # no unrounded value
    # The same on a failed gate and on a result that does not count.
    failed = {**graded, "status": "MANDATORY_GATE_FAILED"}
    failed["gates"] = {g: "FAIL" for g in GATES}
    for variant in (failed, {**graded, "status": "FAILED_INFRA"}):
        shown = json.dumps(_feedback(variant))
        for secret in SECRETS + ("unregistered_metric",):
            assert secret not in shown, secret


def test_a_registered_component_the_result_does_not_carry_is_not_shown():
    document = _feedback(_graded(comps={"acc_mean": 0.66}))
    assert document["parts"]["components"] == {"acc_mean": 0.65}
    # A set-level aggregate carries only the halves: the components are empty.
    document = _feedback({**_graded(), "components": None})
    assert document["parts"]["components"] == {}
    assert document["parts"]["A"] == 0.6 and document["parts"]["D"] == 0.4


@pytest.mark.parametrize(
    "bad",
    [
        None,
        {"A": ["x"]},
        {"A": ["x"], "D": ["y"], "E": ["z"]},
        {"A": ["x", "x"], "D": ["y"]},
        {"A": [1], "D": ["y"]},
        {"A": "x", "D": ["y"]},
    ],
)
def test_an_unregistered_or_malformed_registry_is_refused(bad):
    if bad is None:
        document = _feedback(_graded(), parts_registry=None)
        assert document["schema"] == gf.SCHEMA_V3  # no registry: v3, unchanged
        return
    with pytest.raises(gf.LadderFeedbackRefused):
        _feedback(_graded(), parts_registry=bad)


def test_v4_refuses_what_it_cannot_show_safely():
    with pytest.raises(gf.LadderFeedbackRefused):  # names no submission
        _feedback(_graded(), recipe_digest=None, epoch=None)
    with pytest.raises(gf.LadderFeedbackRefused):  # a gate outside the registry
        _feedback(_graded(), gate_registry=("native_motor_valid",))
    with pytest.raises(gf.LadderFeedbackRefused):  # a gate missing from the result
        _feedback(_graded(), gate_registry=(*GATES, "another_gate"))
    scored = _graded()
    scored["gates"]["native_motor_valid"] = "FAIL"
    with pytest.raises(gf.LadderFeedbackRefused):  # scored with a failed gate
        _feedback(scored)
    odd = _graded()
    odd["gates"]["native_motor_valid"] = "CANDIDATE_INVALID"
    with pytest.raises(gf.LadderFeedbackRefused):
        _feedback(odd)
    no_legs = _graded()
    del no_legs["legs"]
    with pytest.raises(gf.LadderFeedbackRefused):
        _feedback(no_legs)


# ---- the store: serving, state, own hotkey, old rows ----------------------


@pytest.fixture
def store(tmp_path):
    root = tmp_path / "receiver"
    root.mkdir(mode=0o700)
    os.chmod(root, 0o700)
    return LadderStore(AttemptLedger(root / "attempts.sqlite3"))


def _record(store, graded, hotkey="5Miner", *, parts=True, exam=EXAM, epoch=3):
    return store.record(
        hotkey,
        MOTOR,
        exam,
        graded,
        exam_version="motor-exam-1",
        gates=GATES,
        rebuild_noise=None,
        recipe_digest=RECIPE,
        epoch=epoch,
        leg_minimums={"A": None, "D": None},
        parts_registry=REGISTRY if parts else None,
    )


def test_a_v4_document_is_stored_served_and_checked(store):
    shown = _record(store, _graded())
    served = store.served("5Miner", MOTOR, EXAM)
    assert served["latest"] == shown == served["best"]
    assert checked(shown, latest=True) == shown
    assert set(served["latest"]) == gf.FIELDS_V4


def test_the_hysteresis_state_is_kept_per_hotkey_and_exam(store):
    first = _record(store, _graded(a=0.62))  # A shows 0.6
    second = _record(store, _graded(a=0.64))  # within a step: repeats
    assert first["parts"]["A"] == second["parts"]["A"] == 0.6
    third = _record(store, _graded(a=0.66))  # a full step from the shown 0.6
    assert third["parts"]["A"] == 0.65
    # A failed gate shows no parts and leaves the state as it was.
    failed = _graded()
    failed.update(status="MANDATORY_GATE_FAILED", gates={g: "FAIL" for g in GATES})
    assert _record(store, failed)["parts"] is None
    fourth = _record(store, _graded(a=0.67))
    assert fourth["parts"]["A"] == 0.65
    # Another hotkey, and another exam, start their own state.
    other = _record(store, _graded(a=0.67), hotkey="5Other")
    assert other["parts"]["A"] == 0.65  # its own first value, floored
    fresh = _record(store, _graded(a=0.64), exam="sha256:" + "f" * 64)
    assert fresh["parts"]["A"] == 0.6


def test_a_miner_reads_only_their_own_documents(store):
    _record(store, _graded(a=0.9, d=0.9), hotkey="5Strong")
    assert store.served("5Weak", MOTOR, EXAM) == {"best": None, "latest": None}
    own = store.served("5Strong", MOTOR, EXAM)["latest"]
    assert own["parts"]["A"] == 0.9


def test_older_documents_are_unchanged_and_still_served(store):
    old = _record(store, _graded(), hotkey="5Old", parts=False)
    assert old["schema"] == gf.SCHEMA_V3 and "parts" not in old
    served = store.served("5Old", MOTOR, EXAM)
    assert served["latest"] == old and set(old) == gf.FIELDS_V3
    # A v4 miner beside it is unaffected, and a v2 document still checks.
    assert _record(store, _graded(), hotkey="5New")["schema"] == gf.SCHEMA_V4
    v2 = gf.ladder_feedback(
        _graded(),
        best=None,
        exam_version="motor-exam-1",
        gate_registry=GATES,
        rebuild_noise=None,
    )
    assert set(v2) == gf.FIELDS and checked(v2, latest=True) == v2


def test_a_tampered_v4_document_is_refused():
    good = _feedback(_graded())
    assert checked(good) == good
    for mutate in (
        lambda d: d.update(case_ids=["c1"]),
        lambda d: d["parts"].update(per_case=[0.1]),
        lambda d: d["parts"].update(A=1.2),
        lambda d: d["parts"]["components"].update(x="0.5"),
        lambda d: d.update(gates={"g": "PASS"}),
        lambda d: d.update(gates=None),
        lambda d: d.update(parts=None),
        lambda d: d.update(minimums_missed=[0.1]),
        lambda d: d.update(gate_names=["g"]),
        lambda d: d.update(total=None),
    ):
        bad = json.loads(json.dumps(good))
        mutate(bad)
        with pytest.raises(LadderStoreRefused):
            checked(bad)
    failed = _graded()
    failed.update(status="MANDATORY_GATE_FAILED", gates={g: "FAIL" for g in GATES})
    shown = _feedback(failed)
    assert checked(shown, latest=True) == shown
    with pytest.raises(LadderStoreRefused):  # a failed gate carries no number
        checked({**shown, "total": 0.5}, latest=True)
    infra = _graded()
    infra["status"] = "FAILED_INFRA"
    shown = _feedback(infra)
    assert checked(shown, latest=True) == shown
    with pytest.raises(LadderStoreRefused):  # a result that does not count has no gates
        checked({**shown, "gates": {"g": "pass"}}, latest=True)


# ---- when a Challenge serves v4 (section 3) -------------------------------


def test_no_challenge_serves_v4_until_its_attack_is_registered(tmp_path):
    assert part_feedback.served("electric-motor-magnetics", "motor-exam-1") is False
    path = tmp_path / "attacks.json"
    path.write_text(
        json.dumps(
            {
                "schema": part_feedback.SCHEMA,
                "challenges": {
                    "electric-motor-magnetics@motor-exam-1": {
                        "attack_digest": "sha256:" + "9" * 64
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    assert part_feedback.served("electric-motor-magnetics", "motor-exam-1", path=path)
    assert not part_feedback.served(
        "electric-motor-magnetics", "motor-exam-2", path=path
    )
    assert not part_feedback.served("f02", "motor-exam-1", path=path)
    for bad in (
        {"schema": "x", "challenges": {}},
        {
            "schema": part_feedback.SCHEMA,
            "challenges": {"nobar": {"attack_digest": "x"}},
        },
        {
            "schema": part_feedback.SCHEMA,
            "challenges": {"a@b": {"attack_digest": "short"}},
        },
        {"schema": part_feedback.SCHEMA, "challenges": {}, "extra": 1},
    ):
        path.write_text(json.dumps(bad), encoding="utf-8")
        with pytest.raises(part_feedback.RegistryInvalid):
            part_feedback.served("a", "b", path=path)


def test_the_registry_names_a_packs_components_in_order_and_nothing_else():
    pack = {
        "secret": "per-case-secret",
        "legs": {
            "A": {
                "minimum": None,
                "components": [
                    {"metric": "acc_mean", "weight": 0.5},
                    {"metric": "acc_worst", "weight": 0.5},
                ],
            },
            "D": {"minimum": 0.2, "components": [{"metric": "closeness", "weight": 1}]},
        },
    }
    assert part_feedback.parts_registry(pack) == {
        "A": ["acc_mean", "acc_worst"],
        "D": ["closeness"],
    }
    with pytest.raises(part_feedback.RegistryInvalid):
        part_feedback.parts_registry({"legs": {"A": {"components": []}}})


# ---- the page's reader ------------------------------------------------------


def test_the_miner_page_reads_the_allow_listed_parts_only():
    from scripts.dev.miner_launchpad.projection import _part_feedback

    document = _feedback(_graded())
    shown = _part_feedback(document)
    assert shown["parts"]["A"] == 0.6 and shown["parts"]["D"] == 0.4
    assert shown["gates"] == {g: "pass" for g in GATES}
    assert shown["minimums_missed"] == []
    assert _part_feedback({**document, "schema": gf.SCHEMA_V3}) == {}
    hostile = json.loads(json.dumps(document))
    hostile["parts"]["components"]["bad name!"] = 0.5
    hostile["parts"]["components"]["big"] = 7
    hostile["gates"]["g"] = "maybe"
    hostile["minimums_missed"] = ["A", 3, "not ok!"]
    clean = _part_feedback(hostile)
    assert "bad name!" not in clean["parts"]["components"]
    assert "big" not in clean["parts"]["components"]
    assert "g" not in clean["gates"]
    assert clean["minimums_missed"] == ["A"]
