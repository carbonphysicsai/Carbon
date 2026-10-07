"""TRAINING-BUDGET-01 slice 2a: the study harness core.

Fake rebuilds on two synthetic Challenges (the DoD's end-to-end run on two
adapters' plans), with the gates, the ledger, the released image and the
confirmation set's single use.
"""

from __future__ import annotations

import json

import pytest

from carbon.training_budget import sheet as sheets
from carbon.training_budget import study as st

IMAGE = "ghcr.io/carbonphysicsai/carbon-c03-worker@sha256:" + "cd" * 32
RELEASE = {
    "schema": st.RELEASE_SCHEMA,
    "release_tag": "worker-images-v1",
    "repository": "ghcr.io/carbonphysicsai/carbon-c03-worker",
    "registry_digest": "sha256:" + "cd" * 32,
    "reference": IMAGE,
}
SETTINGS = {
    "steps": {"default": 100, "integer": True},
    "width": {"default": 32, "integer": True},
}


def sheet_for(challenge, **changes):
    document = {
        "schema": sheets.SCHEMA,
        "challenge_id": challenge,
        "challenge_version": "v1",
        "gpu_model": "example-gpu",
        "image_digest": IMAGE,
        "spend_ceiling": 10,
        "study_seed_root": {"held_by": "producer", "commitment": "sha256:" + "ab" * 32},
        "study_contract_ranges": {"steps": [16, 800], "width": [8, 128]},
        "rebuild_time_target": 600,
        "memory_ceiling": 8_000_000_000,
        "study_time_limit": 3600,
        "seeds_per_setting": 3,
        "study_recipes": [{"steps": 100, "width": 32}, {"steps": 200, "width": 16}],
        "generation_ceiling": 3200,
        "minimum_panel_size": 3,
        "target_utilization": 0.5,
        "gpu_ceiling": 8,
        "expected_participation": 32,
    }
    document.update(changes)
    return sheets.parse(document, challenge)


def fake_executor(*, drift=frozenset(), fail=None):
    """A deterministic rebuild: digests follow the recipe and seed, except
    for groups listed in `drift`."""
    calls = []

    def run(run, seed):
        calls.append(run.run_id)
        if fail is not None and fail(run):
            raise fail.error
        salt = run.note if run.group in drift else ""
        body = json.dumps([run.parameters, seed, salt], sort_keys=True)
        return {
            "identity": {
                "recipe_digest": st.digest(run.parameters),
                "settings": run.parameters,
                "seed": seed,
                "image_digest": IMAGE,
                "backend": "jax",
                "gpu_model": "example-gpu",
                "driver_version": "x",
                "cuda_version": "y",
            },
            "time": {"compile_s": 1.0, "train_s": 2.0, "wall_s": 3.0},
            "resources": {"peak_memory_bytes": 1, "steps_completed": 1},
            "training": {"final_loss": 0.1},
            "score": {
                "exam_score": 0.5,
                "key_region_score": 0.5,
                "gates": {},
                "error_components": {},
                "key_region_cases": 10,
            },
            "determinism": {
                "weight_digest": st.digest(body),
                "prediction_digest": st.digest(body + "p"),
            },
        }

    run.calls = calls
    return run


def study(tmp_path, challenge="synthetic-one", **changes):
    root = tmp_path / challenge
    return st.Study(root, sheet_for(challenge, **changes), RELEASE)


def phase_a(s):
    recipes = s.sheet.get("study_recipes")
    return s.plan("A", st.plan_a(recipes, {"steps": 800, "width": 128}))


@pytest.mark.parametrize("challenge", ["synthetic-one", "synthetic-two"])
def test_a_study_runs_end_to_end_on_any_challenge(tmp_path, challenge):
    s = study(tmp_path, challenge)
    executor = fake_executor()
    s.execute(phase_a(s), executor, cost=lambda run: {"F0_steps": 1})
    assert s.apply_r1()["result"] == "PASS"
    ranges = s.sheet.get("study_contract_ranges")
    b = s.plan("B", st.plan_b(s.sheet.get("study_recipes"), SETTINGS, ranges, 3))
    s.execute(b, executor)
    assert {r["phase"] for r in s.records()} == {"A", "B"}
    assert all(r["state"] == "COMPLETED" for r in s.records())
    events = [e["event"] for e in s.journal()]
    assert events == ["opened", "planned", "r1", "planned"]


def test_phase_b_sweeps_one_setting_from_below_default_to_the_study_top():
    runs = st.plan_b([{"steps": 100, "width": 32}], SETTINGS, {"steps": [16, 800]}, 1)
    assert [r.parameters["steps"] for r in runs] == [50, 100, 200, 400, 800]
    assert all(r.parameters["width"] == 32 for r in runs)


def test_nothing_after_a_runs_before_r1_passes(tmp_path):
    s = study(tmp_path)
    with pytest.raises(st.StudyRefused) as refused:
        s.plan("B", [])
    assert refused.value.code == "study_r1_not_applied"
    s.execute(phase_a(s), fake_executor(drift={"pair:largest"}))
    result = s.apply_r1()
    assert result["result"] == "FAIL" and result["mismatches"] == ["pair:largest"]
    with pytest.raises(st.StudyRefused) as refused:
        s.plan("B", [])
    assert refused.value.code == "study_stopped_by_r1"


def test_r1_holds_the_shared_gpu_runs_to_their_lone_twin(tmp_path):
    s = study(tmp_path)
    s.execute(phase_a(s), fake_executor(drift={"shared:study-0"}))
    result = s.apply_r1()
    assert result["result"] == "FAIL" and "shared:study-0" in result["mismatches"]


def test_d_e_h_wait_for_the_frozen_limit_and_d_uses_the_confirmation_once(tmp_path):
    s = study(tmp_path)
    executor = fake_executor()
    s.execute(phase_a(s), executor)
    s.apply_r1()
    top = {f"r{i}": {1: {"steps": 100 * i}, 4: {"steps": 400 * i}} for i in range(1, 5)}
    with pytest.raises(st.StudyRefused) as refused:
        s.plan("D", st.plan_d(top, 1.0))
    assert refused.value.code == "study_limit_not_frozen"
    with pytest.raises(st.StudyRefused):
        s.open_confirmation()
    s.freeze_limit(1.0e12, "F4_flops", "owner")
    d = s.plan("D", st.plan_d(top, 1.0e12))
    with pytest.raises(st.StudyRefused) as refused:
        s.execute(d, executor)
    assert refused.value.code == "study_confirmation_sealed"
    s.open_confirmation()
    s.execute(d, executor)
    assert len([r for r in s.records() if r["phase"] == "D"]) == 4 * 2 * 5
    with pytest.raises(st.StudyRefused) as refused:
        s.open_confirmation()
    assert refused.value.code == "study_confirmation_already_used"


def test_confirmation_runs_are_refused_outside_phase_d(tmp_path):
    s = study(tmp_path)
    run = st.Run("A", "x", {"steps": 1}, 0, evaluation="confirmation")
    with pytest.raises(st.StudyRefused) as refused:
        s.plan("A", [run])
    assert refused.value.code == "study_confirmation_only_in_phase_d"


def test_a_finished_run_is_never_repeated(tmp_path):
    s = study(tmp_path)
    executor = fake_executor()
    runs = phase_a(s)
    s.execute(runs, executor)
    first = len(executor.calls)
    assert s.execute(runs, executor) == [] and len(executor.calls) == first


def test_a_crash_leaves_a_reservation_that_is_reconciled_then_retried(tmp_path):
    s = study(tmp_path)
    runs = phase_a(s)
    target = runs[0]
    reserved = s.root / "reserved" / f"{target.run_id}.0.json"
    reserved.write_bytes(st.canonical({"run": target.document(), "attempt": 0}))
    with pytest.raises(st.StudyRefused) as refused:
        s.execute(runs, fake_executor())
    assert refused.value.code == "study_unresolved_runs"
    s.reconcile(f"{target.run_id}.0")
    s.execute(runs, fake_executor())
    states = {
        r["attempt"]: r["state"] for r in s.records() if r["run_id"] == target.run_id
    }
    assert states == {0: "FAILED_INFRA", 1: "COMPLETED"}


class Infrastructure(RuntimeError):
    candidate = False
    code = "worker_infrastructure"


class Candidate(RuntimeError):
    candidate = True
    code = "reconstruction_failed"


@pytest.mark.parametrize(
    ("error", "state"),
    [(Infrastructure(), "FAILED_INFRA"), (Candidate(), "FAILED_CANDIDATE")],
)
def test_infrastructure_failure_is_never_a_candidate_failure(tmp_path, error, state):
    s = study(tmp_path)
    runs = phase_a(s)

    def fail(run):
        return run is runs[0]

    fail.error = error
    s.execute(runs, fake_executor(fail=fail))
    record = next(r for r in s.records() if r["run_id"] == runs[0].run_id)
    assert record["state"] == state and record["failure"] == error.code
    retried = s.execute(runs, fake_executor())
    assert (len(retried) == 1) is (state == "FAILED_INFRA")


def test_an_incomplete_record_is_refused(tmp_path):
    s = study(tmp_path)
    executor = fake_executor()

    def partial(run, seed):
        groups = executor(run, seed)
        del groups["determinism"]["prediction_digest"]
        return groups

    with pytest.raises(st.StudyRefused) as refused:
        s.execute(phase_a(s), partial)
    assert refused.value.code == "study_record_incomplete"


@pytest.mark.parametrize(
    "release",
    [
        {**RELEASE, "reference": IMAGE.replace("cd", "ef")},
        {**RELEASE, "release_tag": "latest"},
        {**RELEASE, "schema": "other"},
        None,
    ],
)
def test_the_study_runs_on_a_released_image_only(tmp_path, release):
    with pytest.raises(st.StudyRefused) as refused:
        st.Study(tmp_path / "s", sheet_for("synthetic-one"), release)
    assert refused.value.code == "study_image_not_released"


def test_the_study_root_is_owner_only_and_outside_the_repository(tmp_path):
    shared = tmp_path / "shared"
    shared.mkdir(mode=0o755)
    shared.chmod(0o755)
    with pytest.raises(st.StudyRefused) as refused:
        st.Study(shared, sheet_for("synthetic-one"), RELEASE)
    assert refused.value.code == "study_root_not_owner_only"


def test_an_unset_sheet_value_refuses_its_phase(tmp_path):
    s = study(tmp_path, minimum_panel_size=None)
    s.execute(phase_a(s), fake_executor())
    s.apply_r1()
    s.freeze_limit(1.0, "F4_flops", "owner")
    with pytest.raises(sheets.SheetIncomplete):
        s.plan("H", [])


def test_plans_for_the_remaining_phases():
    assert (
        len(st.plan_c({(1, "longer"): {"steps": 100}, (4, "wider"): {"width": 64}}, 3))
        == 6
    )
    e = st.plan_e({"steps": 800}, 1.0, back_to_back=3)
    assert [r.concurrency for r in e] == [1, 1, 1, 2, 2, 4, 4, 4, 4]
    assert len(st.plan_f({"microbatches": {"microbatches": 8}}, 3)) == 3
    sizes = st.train_sizes(400, sheets.DEFAULT_TRAIN_SIZE_LADDER, 1600)
    assert sizes == [100, 200, 400, 800, 1600]
    g = st.plan_g({"a": {}, "b": {}, "c": {}}, sizes, 3)
    assert len(g) == 3 * 5 * 3 and {r.train_size for r in g} == set(sizes)
    h = st.plan_h({"a": {}, "b": {}, "c": {}}, 3, lambda p, f: {**p, "budget": f})
    assert len(h) == 3 * len(st.SCREENING_FRACTIONS) * st.SCREENING_SEEDS
    with pytest.raises(st.StudyRefused):
        st.plan_h({"a": {}}, 3, lambda p, f: p)


def test_reconstruction_seeds_repeat_within_a_pair_and_differ_across_seeds():
    a = st.Run("A", "r", {"steps": 1}, 0, note="repeat 0")
    b = st.Run("A", "r", {"steps": 1}, 0, note="repeat 1")
    c = st.Run("B", "r", {"steps": 1}, 1)
    assert a.run_id != b.run_id
    assert st.reconstruction_seed("x", a) == st.reconstruction_seed("x", b)
    assert st.reconstruction_seed("x", a) != st.reconstruction_seed("x", c)
