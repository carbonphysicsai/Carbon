"""M4 Layer B: the pool versions' single-design call timing reaches the grade (Validator, GPU_REBUILD_RULINGS 8).

The receiver draws the timed rows under a custody key (HMAC, domain tag carbon.speed-sample/1, pool set id,
submission id), runs the derived single-call program in the inference container after the graded inference, and keeps
the receipt as a host-private side file the producer reads. Anything missing is UNAVAILABLE (Carbon's gap).
"""

from __future__ import annotations

import hashlib
import hmac
import json
from types import SimpleNamespace

import numpy as np
import pytest

from carbon.challenge_validator import lean_recipe_retention as retention
from carbon.development_session import (
    bundle_construction_worker,
    construction_recipe,
    single_call_timing,
)
from carbon.scoring import pool_exam

KEY = bytes(range(32))
SET_ID = "sha256:" + "5" * 64
SUBMISSION = "task-0001"
POOL_ROWS = 40


def _bank():
    """A canonical bank: 6 cells, 4 probes, POOL_ROWS pool rows, distinct inputs."""
    rng = np.random.default_rng(3)
    inputs = rng.random((6 + 4 + POOL_ROWS, 3))
    cohorts = (
        ["cell"] * 6 + ["probe_response"] * 4 + [pool_exam.POOL_COHORT] * POOL_ROWS
    )
    return {"inputs": inputs, "cohorts": cohorts, "pool": {"set_digest": SET_ID}}


# --- the seed and the draw ----------------------------------------------------------------------


def test_the_grading_host_holds_k_speed_and_the_seed_derives_from_it():
    """K_speed = HMAC(copy key, 'carbon.speed-key/1' 0x00 set id); seed = HMAC(K_speed, 'carbon.speed-sample/1'
    0x00 submission id): the grading host never holds the copy key, and one grade's seed reveals neither key.
    """
    copy_key = bytes(range(32, 64))
    k_speed = hmac.new(
        copy_key,
        b"\x00".join([b"carbon.speed-key/1", SET_ID.encode()]),
        hashlib.sha256,
    ).digest()
    assert single_call_timing.speed_key(copy_key, SET_ID) == k_speed
    expected = hmac.new(
        k_speed,
        b"\x00".join([b"carbon.speed-sample/1", SUBMISSION.encode()]),
        hashlib.sha256,
    ).digest()
    assert single_call_timing.sample_seed(k_speed, SUBMISSION) == expected
    # another set, copy key or submission draws another key or seed: no reuse across grades
    assert single_call_timing.speed_key(copy_key, "sha256:" + "6" * 64) != k_speed
    assert single_call_timing.speed_key(bytes(32), SET_ID) != k_speed
    assert single_call_timing.sample_seed(k_speed, "task-0002") != expected
    assert single_call_timing.sample_seed(bytes(32), SUBMISSION) != expected


@pytest.mark.parametrize(
    "args",
    [
        (b"short", SUBMISSION),
        ("not bytes", SUBMISSION),
        (KEY, ""),
        (KEY, 3),
    ],
)
def test_a_weak_or_malformed_seed_input_is_refused(args):
    with pytest.raises(single_call_timing.SingleCallRefused):
        single_call_timing.sample_seed(*args)


@pytest.mark.parametrize(
    "args", [(b"short", SET_ID), (KEY[:8], SET_ID), (KEY, ""), (KEY, 3), ("k", SET_ID)]
)
def test_a_weak_or_malformed_key_derivation_input_is_refused(args):
    with pytest.raises(single_call_timing.SingleCallRefused):
        single_call_timing.speed_key(*args)


def test_the_draw_is_over_the_pool_rows_and_survives_a_copy_reorder():
    bank = _bank()
    seed = single_call_timing.sample_seed(KEY, SUBMISSION)
    canonical_order = single_call_timing.delivered_indices(bank, bank["inputs"], seed)
    pool = {i for i, c in enumerate(bank["cohorts"]) if c == pool_exam.POOL_COHORT}
    assert len(canonical_order) == single_call_timing.SAMPLE
    assert set(canonical_order) <= pool and canonical_order == sorted(canonical_order)
    # a validator copy reorders the rows: the same ROWS are timed, found at their delivered positions
    order = np.random.default_rng(9).permutation(len(bank["inputs"]))
    delivered = bank["inputs"][order]
    found = single_call_timing.delivered_indices(bank, delivered, seed)
    assert {tuple(delivered[i]) for i in found} == {
        tuple(bank["inputs"][i]) for i in canonical_order
    }
    # another submission draws other rows
    other = single_call_timing.delivered_indices(
        bank, bank["inputs"], single_call_timing.sample_seed(KEY, "task-0002")
    )
    assert other != canonical_order


def test_a_drawn_row_missing_or_repeated_in_the_delivered_query_is_refused():
    bank = _bank()
    seed = single_call_timing.sample_seed(KEY, SUBMISSION)
    wanted = single_call_timing.delivered_indices(bank, bank["inputs"], seed)
    missing = np.delete(bank["inputs"], wanted[0], axis=0)
    with pytest.raises(
        single_call_timing.SingleCallRefused, match="not_in_the_delivered"
    ):
        single_call_timing.delivered_indices(bank, missing, seed)
    repeated = np.vstack([bank["inputs"], bank["inputs"][wanted[0]]])
    with pytest.raises(
        single_call_timing.SingleCallRefused, match="not_in_the_delivered"
    ):
        single_call_timing.delivered_indices(bank, repeated, seed)
    with pytest.raises(single_call_timing.SingleCallRefused):
        single_call_timing.delivered_indices(bank, bank["inputs"][:, :2], seed)
    small = {**bank, "cohorts": ["cell"] * len(bank["inputs"])}
    with pytest.raises(single_call_timing.SingleCallRefused, match="smaller"):
        single_call_timing.delivered_indices(small, bank["inputs"], seed)


# --- the side file ------------------------------------------------------------------------------


def _side(**change):
    document = single_call_timing.side_file(
        indices=list(range(20)),
        warmup_digest="sha256:" + "7" * 64,
        call_s=[0.01 + i / 1000 for i in range(20)],
        outputs_match=True,
        operation="operation-" + "0" * 64,
    )
    return {**document, **change}


def test_the_side_file_reads_back_its_seconds_and_the_outputs_verdict():
    raw = json.dumps(_side()).encode()
    seconds, match = single_call_timing.read_side_file(raw)
    assert seconds == _side()["call_s"] and match is True


@pytest.mark.parametrize(
    "change",
    [
        {"call_s": [0.01] * 19},
        {"call_s": [0.01] * 19 + [0.0]},
        {"call_s": [0.01] * 19 + [float("inf")]},
        {"schema": "other"},
        {"scope": "BATCHED"},
        {"outputs_match_graded": "yes"},
        {"indices": [1, 2]},
    ],
)
def test_a_malformed_side_file_is_refused(change):
    raw = json.dumps(_side(**change)).encode()
    with pytest.raises(single_call_timing.SingleCallRefused):
        single_call_timing.read_side_file(raw)
    for bad in (None, b"not json", b"[]"):
        with pytest.raises(single_call_timing.SingleCallRefused):
            single_call_timing.read_side_file(bad)


# --- the grade reads it ---------------------------------------------------------------------------


def test_timed_calls_that_answered_differently_fail_the_speed_gate_on_the_candidate():
    from test_pool_exam import FAST, grade

    assert grade(speed=FAST)["gates"][pool_exam.SPEED_GATE] is True
    wrong = grade(speed=FAST, speed_outputs_match=False)
    assert wrong["gates"][pool_exam.SPEED_GATE] is False
    assert wrong["pool"]["speed"]["outputs_differ"] is True


def test_the_producer_asks_the_side_file_and_a_missing_one_is_unavailable_not_a_score():
    from carbon.scoring import private_evaluation_source as pes

    # the source function carries the side file to the producer without touching the graded originals
    parameters = pes.produce_registered_dual_measurement.__code__.co_varnames
    assert "single_call_raw" in parameters


# --- the receiver's stage ---------------------------------------------------------------------------


@pytest.fixture
def stage(tmp_path, monkeypatch):
    """The receiver's `_single_call_raw` with the container, the pack and the ledger stubbed."""
    bank = _bank()
    delivered = bank["inputs"][
        np.random.default_rng(11).permutation(len(bank["inputs"]))
    ]
    seed = single_call_timing.sample_seed(KEY, SUBMISSION)
    indices = single_call_timing.delivered_indices(bank, delivered, seed)
    material = {
        "construction_kit": {
            "id": "c",
            "version": "1.5",
            "train_digest": "sha256:" + "1" * 64,
            "interface_digest": "sha256:" + "2" * 64,
            "construction_limits_digest": "sha256:" + "3" * 64,
        },
        "construction_limits_document": {
            "reconstruction_resource_policy": {
                "inference_wall_seconds_max": 60,
                "total_reconstruction_wall_seconds_max": 120,
            }
        },
        "interface_document": {},
        "practice_inputs": delivered,
        "expected_output_shape": (len(delivered), 1),
        "allowlist_bytes": b"{}",
    }
    private_dir = tmp_path / "private"
    private_dir.mkdir()
    calls = []

    def fake_infer(ledger, **kwargs):
        calls.append(kwargs)
        control = kwargs["single_call"]
        assert control["indices"] == indices  # the stage is told exactly the drawn rows
        return SimpleNamespace(
            receipt={
                "single_call": {
                    "scope": single_call_timing.SCOPE,
                    "indices": control["indices"],
                    "warmup_digest": "sha256:" + "8" * 64,
                    "call_s": [0.02] * single_call_timing.SAMPLE,
                }
            },
            predictions=[[float(i)] for i in control["indices"]],
            worker_operation="operation-" + "9" * 64,
        )

    monkeypatch.setattr(bundle_construction_worker, "_infer_state", fake_infer)
    monkeypatch.setattr(
        construction_recipe.ConstructionRecipe, "from_dict", staticmethod(lambda d: d)
    )
    monkeypatch.setattr(retention, "output_dtype", lambda _interface: "float64")
    monkeypatch.setattr(
        retention, "_private_evaluation_directory", lambda *_: private_dir
    )
    from carbon.challenge_kit import physical_pack
    from carbon.scoring import sealed_batch_source

    monkeypatch.setattr(
        sealed_batch_source,
        "resolve",
        lambda **_: (bank, SimpleNamespace(POOL_GRADED=True)),
    )
    monkeypatch.setattr(
        physical_pack, "development_bank", lambda *_: {"inputs": bank["inputs"][:3]}
    )
    adapter = SimpleNamespace(
        owner=lambda _id: "owner",
        _provider=lambda _owner: SimpleNamespace(
            ledger=object(),
            inference_image=object(),
            inference_accelerator=None,
            _requests={SUBMISSION: SimpleNamespace(recipe={"r": 1})},
        ),
        discovery=SimpleNamespace(
            _material=material,
            evaluation_pack_snapshot=SimpleNamespace(
                manifest_digest="sha256:" + "4" * 64
            ),
            evaluation_pack_private_root=tmp_path,
        ),
        challenge_id="c",
        challenge_version="1.5",
        speed_sample_key=KEY,
        copy_hotkey=None,
    )
    graded = [[float(i)] for i in range(len(delivered))]
    artifacts = {
        "state.npz": b"state",
        "predictions.json": json.dumps(graded).encode(),
    }
    return SimpleNamespace(
        adapter=adapter,
        artifacts=artifacts,
        indices=indices,
        calls=calls,
        private_dir=private_dir,
        result={"entry_id": "e"},
        graded=graded,
        bank=bank,
    )


def _run(stage_fixture, **change):
    return retention._single_call_raw(
        stage_fixture.adapter,
        SUBMISSION,
        stage_fixture.result,
        stage_fixture.artifacts,
        {"state_digest": "sha256:" + "a" * 64},
        None,
        **change,
    )


def test_the_receiver_keeps_the_per_call_seconds_as_a_write_once_side_file(stage):
    raw = _run(stage)
    seconds, match = single_call_timing.read_side_file(raw)
    assert seconds == [0.02] * 20 and match is True
    assert (stage.private_dir / "single-call.json").read_bytes() == raw
    # a retry reads the retained bytes and never replays the stage
    assert _run(stage) == raw and len(stage.calls) == 1
    # the container is told indices and the public warm-up, never the key or the seed
    sent = stage.calls[0]
    assert sorted(sent["single_call"]) == ["indices", "warmup"]
    assert KEY.hex() not in json.dumps(raw.decode())


def test_the_stage_runs_on_the_derived_program_and_the_delivered_rows(stage):
    _run(stage)
    sent = stage.calls[0]
    assert sent["program"] == single_call_timing.program(
        bundle_construction_worker.INFER_PROGRAM
    )
    assert sent["expected_output_shape"] == (20, 1)
    assert np.array_equal(
        sent["inputs"], stage.adapter.discovery._material["practice_inputs"]
    )
    assert sent["single_call"]["warmup"].shape == (1, 3)


def test_timed_answers_that_differ_from_the_graded_run_are_recorded_for_the_gate(stage):
    stage.artifacts["predictions.json"] = json.dumps(
        [[v[0] + 1.0] for v in stage.graded]
    ).encode()
    _, match = single_call_timing.read_side_file(_run(stage))
    assert match is False


@pytest.mark.parametrize("key", [None, b"short", "text"])
def test_a_receiver_without_a_speed_key_leaves_the_grade_unavailable(stage, key):
    stage.adapter.speed_sample_key = key
    with pytest.raises(
        retention.RetentionUnavailable, match="single_call_key_unavailable"
    ):
        _run(stage)
    assert stage.calls == [] and not (stage.private_dir / "single-call.json").exists()


def test_a_pack_that_is_not_pool_graded_is_not_timed(stage, monkeypatch):
    from carbon.scoring import sealed_batch_source

    monkeypatch.setattr(
        sealed_batch_source, "resolve", lambda **_: (stage.bank, SimpleNamespace())
    )
    with pytest.raises(retention.RetentionUnavailable, match="not_pool_graded"):
        _run(stage)


def test_a_stage_that_stops_is_unavailable_never_a_pass(stage, monkeypatch):
    def stops(*_args, **_kwargs):
        raise construction_recipe.RecipeRefused("direct_inference_failed")

    monkeypatch.setattr(bundle_construction_worker, "_infer_state", stops)
    with pytest.raises(
        retention.RetentionUnavailable, match="single_call_stage_incomplete"
    ):
        _run(stage)
    assert not (stage.private_dir / "single-call.json").exists()


# --- the receiver's configuration -------------------------------------------------------------------


def test_the_speed_key_file_is_an_exact_private_regular_file_of_enough_bytes(tmp_path):
    from carbon.challenge_validator import direct_receiver

    good = tmp_path / "speed.key"
    good.write_bytes(KEY)
    good.chmod(0o600)
    assert direct_receiver.read_speed_sample_key(str(good)) == KEY
    for name, content, mode in (
        ("short.key", b"x" * 16, 0o600),
        ("open.key", KEY, 0o644),
        ("huge.key", b"x" * 5000, 0o600),
    ):
        path = tmp_path / name
        path.write_bytes(content)
        path.chmod(mode)
        with pytest.raises(ValueError, match="private speed sample key"):
            direct_receiver.read_speed_sample_key(str(path))
    link = tmp_path / "link.key"
    link.symlink_to(good)
    for bad in (str(link), "relative.key", str(tmp_path / "missing.key"), None, 3):
        with pytest.raises(ValueError, match="private speed sample key"):
            direct_receiver.read_speed_sample_key(bad)
    assert direct_receiver._speed_key({}) is None
    assert direct_receiver._speed_key({"speed_sample_key_file": str(good)}) == KEY
    assert "speed_sample_key_file" in direct_receiver._OPTIONAL_FIELDS


# --- GPU-5: the sealed path with a GPU rebuild (rebuild on the GPU, grade on the CPU) ------------------------


def _gpu_lane_provider(stage):
    """The stage fixture's provider, now with a graph GPU lane configured (a GPU-built state)."""
    provider = stage.adapter._provider("owner")
    provider.graph_gpu_image = SimpleNamespace(image_id="sha256:" + "6" * 64)
    provider.graph_gpu_ops = frozenset({"matmul"})
    return provider


def test_a_gpu_built_state_is_timed_and_graded_on_the_cpu_inference_image(
    stage, monkeypatch
):
    """The single-call stage of a pool grade runs in the receiver's CPU inference image with no accelerator even
    when the graph lane builds on a GPU worker: the state passes by digest and the speed is the grading CPU's.
    """
    provider = _gpu_lane_provider(stage)
    monkeypatch.setattr(stage.adapter, "_provider", lambda _owner: provider)
    _run(stage)
    sent = stage.calls[0]
    assert sent["inference_image"] is provider.inference_image
    assert sent["inference_image"] is not provider.graph_gpu_image
    assert sent["accelerator"] is None
    assert sent["state_digest"] == "sha256:" + "a" * 64


def test_a_receiver_whose_inference_image_is_a_gpu_worker_has_no_official_pool_speed(
    stage, monkeypatch
):
    provider = stage.adapter._provider("owner")
    provider.inference_accelerator = "MINER_GPU"
    monkeypatch.setattr(stage.adapter, "_provider", lambda _owner: provider)
    with pytest.raises(
        retention.RetentionUnavailable, match="single_call_needs_the_cpu_grading_image"
    ):
        _run(stage)
    assert stage.calls == [] and not (stage.private_dir / "single-call.json").exists()


def test_prepare_records_the_graph_gpu_lane_or_refuses_half_of_it(tmp_path):
    from carbon.challenge_validator import direct_receiver, receiver_setup

    manifest = tmp_path / "gpu-image.json"
    ops = tmp_path / "gpu-ops.json"
    manifest.write_text("{}")
    ops.write_text("{}")
    # the argument pair is validated before anything is written
    for kwargs in (
        {"graph_gpu_image_manifest": manifest},
        {"graph_gpu_ops": ops},
    ):
        with pytest.raises(receiver_setup.SetupRefused) as refused:
            receiver_setup.prepare(
                installed_state=tmp_path / "i",
                receiver_state=tmp_path / "r",
                challenge={"id": "x", "version": "1"},
                hotkey="h",
                **kwargs,
            )
        assert refused.value.code == "graph_gpu_lane_incomplete"
    with pytest.raises(receiver_setup.SetupRefused) as refused:
        receiver_setup.prepare(
            installed_state=tmp_path / "i",
            receiver_state=tmp_path / "r",
            challenge={"id": "x", "version": "1"},
            hotkey="h",
            graph_gpu_image_manifest=tmp_path / "missing.json",
            graph_gpu_ops=ops,
        )
    assert refused.value.code == "graph_gpu_lane_file_invalid"
    assert not (tmp_path / "r").exists()
    # the receiver accepts exactly the two fields together
    assert {
        "graph_gpu_image_manifest",
        "graph_gpu_ops",
    } <= direct_receiver._OPTIONAL_FIELDS
