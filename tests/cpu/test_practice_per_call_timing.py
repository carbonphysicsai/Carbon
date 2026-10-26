"""The practice speed figure: the batched average is relabelled, and the timed
child also reports one single-design call per practice row (Validator
V8_RULINGS section 10).

A batched average over the public rows can be flattered by amortising a per-call
fixed cost or by recognising known rows. The practice figure is therefore
labelled "batched average over the public practice rows (not the exam's measure)"
and carries the per-call median and maximum beside it. The per-call timings come
from a derived timed-only program; the frozen inference programs are untouched.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from test_bundle_construction_worker import _binding, _recipe, _stage

from carbon.development_session.bundle_construction_worker import (
    BUILD_PROGRAM,
    INFER_PROGRAM,
    _digest,
    _per_call_ok,
    _stage_bundle_modules,
    _tensors,
    timed_program,
)
from carbon.level4 import allowlist
from carbon.scoring import practice_speed


def _build(tmp_path, x):
    library = tmp_path / "installed-library"
    candidate = library / "candidate"
    candidate.mkdir(parents=True)
    (candidate / "__init__.py").write_text("")
    (candidate / "build.py").write_text(
        "import numpy as np\n"
        "import jax.numpy as jnp\n"
        "def build(train_inputs, train_targets, *, seed, configuration, train_use):\n"
        "    scale = np.float32(np.sum(train_targets * train_inputs) / np.sum(train_inputs ** 2))\n"
        "    return {'framework': 'jax', 'apply': lambda x: x * jnp.asarray(scale), 'parameters': []}\n"
    )
    train = _tensors(inputs=x, targets=3 * x)
    example = _tensors(inputs=x)
    recipe = _recipe(_digest(train))
    binding = _binding(recipe)
    allowed = allowlist.load(Path(allowlist.PATH).with_name("allowlist_v2.json"))
    files, modules = _stage_bundle_modules(binding, training=True)
    files.update(
        {
            "recipe.json": recipe.canonical_bytes,
            "train.npz": train,
            "example.npz": example,
            "allowlist.json": allowed.raw,
            "control.json": json.dumps(
                {
                    "recipe_digest": recipe.digest,
                    "bundle_ref": recipe.to_dict()["source"]["bundle_ref"],
                    "binding": binding,
                    "codec_modules": modules,
                    "example_digest": _digest(example),
                    "allowlist_digest": allowed.digest,
                    "seed": 7,
                },
                sort_keys=True,
            ).encode(),
        }
    )
    work = _stage(tmp_path / "build", files)
    built = subprocess.run(
        [sys.executable, "-c", BUILD_PROGRAM],
        cwd=work,
        env={**os.environ, "PYTHONPATH": str(library)},
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert built.returncode == 0, built.stderr
    return recipe, binding, allowed, (work.parent / "output/state.npz").read_bytes()


def _measured(tmp_path, recipe, binding, allowed, state, rows):
    requested = _tensors(inputs=rows)
    files, modules = _stage_bundle_modules(binding, training=False)
    files.update(
        {
            "recipe.json": recipe.canonical_bytes,
            "state.npz": state,
            "inputs.npz": requested,
            "allowlist.json": allowed.raw,
            "control.json": json.dumps(
                {
                    "recipe_digest": recipe.digest,
                    "binding": binding,
                    "codec_modules": modules,
                    "state_digest": _digest(state),
                    "inputs_digest": _digest(requested),
                    "allowlist_digest": allowed.digest,
                    "expected_output_shape": list(rows.shape),
                    "measure_query": True,
                    "per_case": False,
                },
                sort_keys=True,
            ).encode(),
        }
    )
    work = _stage(tmp_path / "timed", files)
    run = subprocess.run(
        [sys.executable, "-c", timed_program(INFER_PROGRAM)],
        cwd=work,
        env={k: v for k, v in os.environ.items() if k != "PYTHONPATH"},
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    return run, work.parent / "output"


def test_the_timed_program_is_derived_and_the_frozen_one_is_untouched():
    derived = timed_program(INFER_PROGRAM)
    assert derived != INFER_PROGRAM and "per_call_s" in derived
    assert "per_call_s" not in INFER_PROGRAM
    compile(derived, "timed", "exec")
    # A program without the measurement anchors (Battery's own) is unchanged.
    assert timed_program("print(1)") == "print(1)"


@pytest.mark.parametrize("count", [2, 5])
def test_the_timed_child_reports_one_call_per_practice_row(tmp_path, count):
    declared = np.asarray([[1.0, 2.0], [3.0, 4.0]], dtype=np.float32)
    recipe, binding, allowed, state = _build(tmp_path, declared)
    rows = np.arange(2 * count, dtype=np.float32).reshape(count, 2) + 1
    # The host times a query no larger than the declared batch (Validator (b)).
    rows = rows[: len(declared)]
    run, output = _measured(tmp_path, recipe, binding, allowed, state, rows)
    assert run.returncode == 0, run.stderr[-2000:]
    np.testing.assert_allclose(
        json.loads((output / "predictions.json").read_bytes()), 3 * rows
    )
    measurement = json.loads((output / "receipt.json").read_bytes())["measurement"]
    per_call = measurement["per_call_s"]
    assert len(per_call) == len(rows) and _per_call_ok(per_call, len(rows))
    block = practice_speed.from_receipt(
        "cooling", {"measurement": measurement}, designs=len(rows)
    )
    assert block["per_call_rows"] == len(rows)
    assert block["figure"] == practice_speed.FIGURE
    assert block["per_call_median_seconds"] <= block["per_call_max_seconds"]


@pytest.mark.parametrize(
    "value,rows,ok",
    [
        (None, 3, True),
        ([], 3, True),
        ([0.1, 0.2], 3, True),
        ([0.1] * 4, 3, False),
        ([0.1, 0.0], 3, False),
        ([0.1, float("nan")], 3, False),
        ([0.1, "x"], 3, False),
        ("x", 3, False),
    ],
)
def test_the_host_checks_the_per_call_list(value, rows, ok):
    assert _per_call_ok(value, rows) is ok


def _receipt(per_call, rows=4):
    return {
        "measurement": {
            "timing_s": {"preprocess": 0.1, "inference": 0.3, "postprocess": 0.1},
            "input_shape": [rows, 2],
            "per_call_s": per_call,
        }
    }


def test_the_figure_is_relabelled_and_carries_the_median_and_the_max():
    block = practice_speed.from_receipt(
        "cooling", _receipt([0.4, 0.1, 0.2, 5.0]), designs=4
    )
    assert block["figure"] == (
        "batched average over the public practice rows (not the exam's measure)"
    )
    assert block["per_call_median_seconds"] == pytest.approx(0.3)
    assert block["per_call_max_seconds"] == 5.0 and block["per_call_rows"] == 4
    # A fast batched average does not hide a slow single call.
    assert block["within_ceiling"] is True
    assert (
        block["per_call_within_ceiling"] is False
        or block["per_call_median_seconds"] <= block["ceiling_seconds_per_design"]
    )


def test_no_per_call_timings_leave_the_batched_figure_as_it_was():
    block = practice_speed.from_receipt("cooling", _receipt(None), designs=4)
    assert "per_call_median_seconds" not in block and "per_call_rows" not in block
    block = practice_speed.from_receipt("cooling", _receipt([]), designs=4)
    assert "per_call_median_seconds" not in block


def test_the_page_projection_passes_the_new_fields_with_carbons_own_text():
    from scripts.dev.miner_launchpad import campaign_view

    block = practice_speed.from_receipt(
        "cooling", _receipt([0.1, 0.2, 0.3, 0.4]), designs=4
    )
    shown = campaign_view.speed_result({**block, "figure": "attacker text"})
    assert shown["figure"] == practice_speed.FIGURE
    assert shown["per_call_median_seconds"] == pytest.approx(0.25)
    assert shown["per_call_max_seconds"] == 0.4 and shown["per_call_rows"] == 4
    assert type(shown["per_call_within_ceiling"]) is bool


@pytest.mark.parametrize(
    "measure,practice,derived",
    [(False, False, False), (True, False, False), (True, True, True)],
)
def test_only_a_practice_timed_child_gets_the_derived_program(
    measure, practice, derived
):
    """The paired / saved-bundle measured queries keep the frozen program."""
    from test_bundle_construction_worker import _recipe

    from carbon.development_session.bundle_construction_worker import _infer_state

    seen = []

    def runner(ledger, **kwargs):
        seen.append(kwargs["source"])
        raise RuntimeError("stop after the program is chosen")

    recipe = _recipe("sha256:" + "a" * 64)
    allowed = allowlist.load(Path(allowlist.PATH).with_name("allowlist_v2.json"))
    with pytest.raises(RuntimeError):
        _infer_state(
            None,
            owner="o",
            identity="i",
            inference_image=None,
            recipe=recipe,
            binding=_binding(recipe),
            state=b"state",
            state_digest="sha256:" + "b" * 64,
            inputs=np.zeros((2, 2), dtype=np.float32),
            expected_output_shape=(2, 2),
            allowlist_bytes=allowed.raw,
            measure_query=measure,
            per_case=not measure,
            runner=runner,
            **({"practice_timing": True} if practice else {}),
        )
    assert (seen[0] != INFER_PROGRAM) is derived
    assert (seen[0] == timed_program(INFER_PROGRAM)) is derived
