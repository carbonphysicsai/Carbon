"""scripts/dev/sealed_exam/pool_e2e.py reads the receiver's evidence of one pool-graded submission and says whether
the chain is consistent (synthetic files; nothing here is a grade)."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from carbon.development_session import single_call_timing
from carbon.scoring import pool_exam

MOTOR = "electric-motor-magnetics"


def _tool():
    path = Path(__file__).resolve().parents[2] / "scripts/dev/sealed_exam/pool_e2e.py"
    spec = importlib.util.spec_from_file_location("pool_e2e_script", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sha(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _evidence(tmp_path, *, call_s=0.5, match=True, verdict="PASS", bound=True):
    pack = tmp_path / "pack"
    (pack / "private").mkdir(parents=True)
    gates = ["finite", "paired_repeat", pool_exam.PHYSICS_GATE, pool_exam.SPEED_GATE]
    (pack / "private/score_pack.json").write_text(json.dumps({"hard_gates": gates}))
    manifest = json.dumps(
        {"private": {"score_pack": {"path": "private/score_pack.json"}}}
    )
    (pack / "evaluation-pack.json").write_text(manifest)
    digest = _sha(manifest.encode())
    eval_dir = tmp_path / "eval"
    eval_dir.mkdir()
    measurement = {
        "evaluation_pack_digest": digest if bound else "sha256:" + "0" * 64,
        "producer_digest": "sha256:" + "1" * 64,
        "benchmark": {
            "models": [
                {
                    "gates": {
                        "finite": "PASS",
                        "paired_repeat": "PASS",
                        pool_exam.PHYSICS_GATE: "PASS",
                        pool_exam.SPEED_GATE: verdict,
                    },
                    "measurements": {
                        "robust_fidelity_benefit": {"status": "RESOLVED", "value": 0.6},
                        "verified_value_benefit": {"status": "RESOLVED", "value": 0.4},
                    },
                    "decision_outcome": "POOL",
                }
            ]
        },
    }
    (eval_dir / "dual-measurement.json").write_text(json.dumps(measurement))
    (eval_dir / "inference-pair.json").write_text("{}")
    side = single_call_timing.side_file(
        indices=list(range(20)),
        warmup_digest="sha256:" + "2" * 64,
        call_s=[call_s] * 20,
        outputs_match=match,
        operation="operation-" + "3" * 64,
    )
    (eval_dir / "single-call.json").write_text(json.dumps(side))
    return eval_dir, pack


def test_a_consistent_submission_reports_its_scores_and_speed(tmp_path):
    eval_dir, pack = _evidence(tmp_path)
    record = _tool().verify(eval_dir, pack, MOTOR, "1.5")
    assert record["verdict"] == "CONSISTENT" and record["problems"] == []
    assert record["bound_to_this_pack"] is True
    assert record["A"] == 0.6 and record["D"] == 0.4
    assert record["total"] == pytest.approx(0.5)
    assert record["speed"]["calls"] == 20 and record["speed"]["median_within_ceiling"]
    assert record["speed_gate_matches_the_side_file"] is True
    assert set(record["pool_gates_in_the_pack"]) == {
        pool_exam.PHYSICS_GATE,
        pool_exam.SPEED_GATE,
    }
    # digests and verdicts only: no row, input, truth or seed
    assert all(v.startswith("sha256:") for v in record["files"].values())


def test_a_slow_model_with_a_pass_verdict_is_inconsistent(tmp_path):
    eval_dir, pack = _evidence(tmp_path, call_s=99.0, verdict="PASS")
    record = _tool().verify(eval_dir, pack, MOTOR, "1.5")
    assert record["verdict"] == "INCONSISTENT"
    assert "speed_verdict_differs_from_the_side_file" in record["problems"]
    # a slow model the receiver failed is the consistent case
    failed = _tool().verify(
        *_evidence(tmp_path / "again", call_s=99.0, verdict="FAIL"), MOTOR, "1.5"
    )
    assert failed["verdict"] == "CONSISTENT"
    assert failed["speed"]["median_within_ceiling"] is False


def test_each_break_in_the_chain_is_named(tmp_path):
    tool = _tool()
    unbound = tool.verify(*_evidence(tmp_path / "a", bound=False), MOTOR, "1.5")
    assert "measurement_not_bound_to_this_pack" in unbound["problems"]
    differing = tool.verify(
        *_evidence(tmp_path / "b", match=False, verdict="PASS"), MOTOR, "1.5"
    )
    assert "speed_verdict_differs_from_the_side_file" in differing["problems"]
    eval_dir, pack = _evidence(tmp_path / "c")
    (eval_dir / "single-call.json").unlink()
    absent = tool.verify(eval_dir, pack, MOTOR, "1.5")
    assert "missing:single-call.json" in absent["problems"]
    (eval_dir / "single-call.json").write_text("{}")
    bad = tool.verify(eval_dir, pack, MOTOR, "1.5")
    assert any(p.startswith("single_call:") for p in bad["problems"])


def test_a_pack_that_is_not_pool_graded_is_named(tmp_path):
    eval_dir, pack = _evidence(tmp_path)
    (pack / "private/score_pack.json").write_text(
        json.dumps({"hard_gates": ["finite"]})
    )
    record = _tool().verify(eval_dir, pack, MOTOR, "1.5")
    assert "pack_is_not_pool_graded" in record["problems"]


def test_the_command_prints_the_record_and_exits_nonzero_when_inconsistent(
    tmp_path, capsys
):
    tool = _tool()
    good = _evidence(tmp_path / "g")
    argv = [
        "verify",
        "--eval-dir",
        str(good[0]),
        "--pack-root",
        str(good[1]),
        "--challenge-id",
        MOTOR,
        "--version",
        "1.5",
    ]
    assert tool.main(argv) == 0
    assert json.loads(capsys.readouterr().out)["verdict"] == "CONSISTENT"
    bad = _evidence(tmp_path / "b", bound=False)
    argv[2], argv[4] = str(bad[0]), str(bad[1])
    assert tool.main(argv) == 3


# --- the rebuild facts: which device built the state, and that the grade ran on the CPU image ----------------


def _artifacts(tmp_path, **change):
    folder = tmp_path / "artifacts"
    folder.mkdir()
    evidence = {
        "build_device": "GPU",
        "build_image_id": "sha256:" + "6" * 64,
        "inference_image_id": "sha256:" + "7" * 64,
        "state_digest": "sha256:" + "8" * 64,
    }
    evidence.update(change)
    evidence = {k: v for k, v in evidence.items() if v is not None}
    (folder / "worker-evidence.json").write_text(json.dumps(evidence))
    return folder


def _with_state(eval_dir, image="sha256:" + "7" * 64, state="sha256:" + "8" * 64):
    measurement = json.loads((eval_dir / "dual-measurement.json").read_text())
    measurement["state_digest"] = state
    (eval_dir / "dual-measurement.json").write_text(json.dumps(measurement))
    (eval_dir / "inference-pair.json").write_text(
        json.dumps({"inference_image_id": image})
    )


def test_a_gpu_rebuilt_state_graded_on_the_cpu_image_is_consistent(tmp_path):
    eval_dir, pack = _evidence(tmp_path)
    _with_state(eval_dir)
    record = _tool().verify(
        eval_dir, pack, MOTOR, "1.5", _artifacts(tmp_path), expect_gpu=True
    )
    assert record["verdict"] == "CONSISTENT", record["problems"]
    assert record["rebuild"]["build_device"] == "GPU"
    assert (
        record["rebuild"]["build_image_id"] != record["rebuild"]["inference_image_id"]
    )


@pytest.mark.parametrize(
    ("change", "problem"),
    [
        (
            {
                "build_device": "CPU",
                "build_image_id": None,
                "gpu_lane_note": "graph_gpu_rebuild_not_repeatable",
            },
            "rebuild_not_on_the_gpu:graph_gpu_rebuild_not_repeatable",
        ),
        (
            {"inference_image_id": "sha256:" + "6" * 64},
            "the_grade_ran_on_the_gpu_build_image",
        ),
        (
            {"state_digest": "sha256:" + "9" * 64},
            "state_digest_differs_between_the_build_and_the_grade",
        ),
    ],
)
def test_each_break_in_the_gpu_rebuild_chain_is_named(tmp_path, change, problem):
    eval_dir, pack = _evidence(tmp_path)
    _with_state(eval_dir, image=change.get("inference_image_id", "sha256:" + "7" * 64))
    record = _tool().verify(
        eval_dir, pack, MOTOR, "1.5", _artifacts(tmp_path, **change), expect_gpu=True
    )
    assert problem in record["problems"] and record["verdict"] == "INCONSISTENT"


def test_a_repeat_pair_on_another_image_and_a_missing_artifact_are_named(tmp_path):
    eval_dir, pack = _evidence(tmp_path / "a")
    _with_state(eval_dir, image="sha256:" + "5" * 64)
    record = _tool().verify(eval_dir, pack, MOTOR, "1.5", _artifacts(tmp_path / "a"))
    assert "repeat_pair_ran_on_another_image_than_the_grade" in record["problems"]
    eval_dir, pack = _evidence(tmp_path / "b")
    empty = tmp_path / "b" / "none"
    empty.mkdir()
    record = _tool().verify(eval_dir, pack, MOTOR, "1.5", empty)
    assert "missing:worker-evidence.json" in record["problems"]
    # without the artifacts dir nothing changes; asking for the GPU without it is a named problem
    eval_dir, pack = _evidence(tmp_path / "c")
    plain = _tool().verify(eval_dir, pack, MOTOR, "1.5")
    assert "rebuild" not in plain and plain["verdict"] == "CONSISTENT"
    asked = _tool().verify(eval_dir, pack, MOTOR, "1.5", expect_gpu=True)
    assert "expect_gpu_needs_the_artifacts_dir" in asked["problems"]
