"""The data kit's local scorer agrees with the official grade path
(KIT_LOCAL_SCORER_DESIGN_TE_20261103; Validator conditions A5, A6).

On a FIXTURE recipe (a small MLP, few steps) and a SYNTHETIC verify set (inputs
inside the public TRAIN box, truths from a fixed fake curve; no hidden, drawn or
verify-set values):

- the kit scorer's predictions are bit-equal to the official rebuild-and-infer
  path's (`reconstruct_and_infer_graph_public`, the isolated build and inference
  programs run by the test-only local runner, seed 0);
- its per-design gates equal `carbon.motor.exam` on the official predictions, and
  its accuracy-vs-U check equals the Motor kit's own verify comparison;
- a recipe the official intake refuses is refused with the SAME code and class;
- a wrong verify sha256 refuses; D, picks and regret are "not evaluated locally";
  the report names the pinned commit;
- the CLI, run in a fresh interpreter, reaches no evaluation-pack, pool-store,
  crown, sealed or custody module (the import closure, at run time).

Motor 1.7 is not registered on main yet: the test runs the latest served Motor
graph route v2 version, a parameter (`KEY`).
"""

from __future__ import annotations

import hashlib
import itertools
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from carbon.challenge_kit import local_scorer, physical_material
from carbon.development_session import direct_graph_construction_worker, graph_adapters
from carbon.development_session import physical_graph_adapter_v2 as adapter
from carbon.development_session.construction_recipe import (
    ConstructionRecipe,
    RecipeRefused,
)
from carbon.level4 import allowlist as allowlist_module

posix = pytest.mark.skipif(os.name != "posix", reason="isolated build programs")
ROOT = Path(__file__).resolve().parents[2]
MOTOR = "electric-motor-magnetics"
#: The latest served Motor graph route v2 version (Motor 1.7 once registered).
KEY = max(
    (key for key in adapter.SPECS if key[0] == MOTOR),
    key=lambda key: tuple(int(part) for part in key[1].split(".")),
)
STEPS = 8
#: Synthetic verify set: positions inside the public TRAIN box and a fixed fake
#: curve. Clearly not Carbon data.
FRACTIONS = (0.25, 0.5, 0.75)
FAKE_U = {"mean_torque_nm": 0.5, "ripple_fraction": 0.5}
FORBIDDEN = ("evaluation_pack", "pool_store", "crown", "sealed", "custody")

pytestmark = [posix]


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _x64():
    import contextlib

    if adapter.SPECS[KEY].dtype != "float64":
        return contextlib.nullcontext()
    import jax

    return jax.enable_x64(True)


def _graph(batch=8):
    """A small MLP graph of the version's interface (test_graph_route_v2's)."""
    pytest.importorskip("jax")
    import jax.numpy as jnp

    from carbon.level4 import graph, initializers, intake, submission
    from carbon.level4.tooling import through_bprime

    spec = adapter.SPECS[KEY]
    dtype = jnp.float64 if spec.dtype == "float64" else jnp.float32
    allowed = allowlist_module.Allowlist(adapter.served_allowlist_bytes(*KEY))
    width = 16

    def forward(w1, b1, w2, b2, x):
        return jnp.tanh(x @ w1 + b1) @ w2 + b2

    _, document, _ = through_bprime(
        forward,
        (
            jnp.zeros((spec.inputs, width), dtype),
            jnp.zeros((width,), dtype),
            jnp.zeros((width, spec.outputs), dtype),
            jnp.zeros((spec.outputs,), dtype),
            jnp.ones((batch, spec.inputs), dtype),
        ),
        role="forward",
        allowlist=allowed,
        input_names=[
            "params/0",
            "params/1",
            "params/2",
            "params/3",
            adapter.INPUT_NAME,
        ],
        max_bytes=intake.BOUNDS["document_bytes"],
    )

    def parameter(index, initializer, axes):
        return {
            "input": f"params/{index}",
            "initializer": initializer,
            "fan_in_axes": axes[0],
            "fan_out_axes": axes[1],
        }

    init_spec = {
        "schema": initializers.SCHEMA,
        "graph": graph.digest(document),
        "parameters": [
            parameter(0, "glorot_normal", ([0], [1])),
            parameter(1, "zeros", ([], [])),
            parameter(2, "glorot_normal", ([0], [1])),
            parameter(3, "zeros", ([], [])),
        ],
    }
    manifest, files = submission.build(
        challenge=spec.challenge_id,
        interface=adapter.graph_interface(spec).digest(),
        allowlist=allowed,
        forward=document,
        init_spec=init_spec,
    )
    return submission.canonical(manifest), files, submission.digest(manifest)


def _recipe(configuration, digest):
    return ConstructionRecipe.from_dict(
        graph_adapters.graph_recipe(*KEY, digest, configuration=configuration)
    )


def _local_runner():
    count = itertools.count()

    def runner(ledger, *, source, files, output_validator, **_kwargs):
        name = f"operation-{next(count):064x}"
        home = ledger.root / name
        work = home / "workspace"
        work.mkdir(parents=True)
        (home / "output").mkdir()
        for filename, body in files.items():
            (work / filename).write_bytes(body)
        done = subprocess.run(
            [sys.executable, "-c", source],
            cwd=work,
            env={**os.environ, "JAX_PLATFORMS": "cpu"},
            capture_output=True,
            text=True,
            timeout=900,
            check=False,
        )
        assert done.returncode == 0, done.stderr[-4000:]
        snapshot = home / "snapshot"
        (home / "output").rename(snapshot)
        output_validator(snapshot)
        return {
            "operation": name,
            "files": {
                path.name: "sha256:" + _sha(path.read_bytes())
                for path in snapshot.iterdir()
            },
        }

    return runner


def _image():
    from carbon.reconstruction.worker.model import WorkerImageIdentity

    return WorkerImageIdentity(*(("sha256:" + "a" * 64,) * 8))


def _verify_set():
    """A synthetic verify set: TRAIN-box positions, a fixed fake curve."""
    import io

    material = local_scorer.public_train(*KEY)
    with np.load(io.BytesIO(material["train"]), allow_pickle=False) as archive:
        inputs = archive["inputs"]
    low, high = inputs.min(axis=0), inputs.max(axis=0)
    names = material["input_names"]
    from carbon.motor.domain import ANGLE_STEPS

    # the truth is a torque curve (a 240-wide Motor 1.8 row's torque slice is what every Motor check reads)
    fake = [0.5 + 0.001 * i for i in range(ANGLE_STEPS)]
    designs = [
        {
            "case_id": f"synthetic-{index}",
            "inputs": {
                name: float(low[j] + fraction * (high[j] - low[j]))
                for j, name in enumerate(names)
            },
            "truth": {"torque_nm": fake},
        }
        for index, fraction in enumerate(FRACTIONS)
    ]
    document = {"u": FAKE_U, "designs": designs}
    raw = json.dumps(document, sort_keys=True).encode("utf-8")
    query = np.asarray(
        [[d["inputs"][n] for n in names] for d in designs],
        dtype=adapter.SPECS[KEY].dtype,
    )
    return raw, document, query


def _official(tmp_path, recipe, raw_manifest, files, query):
    """The official rebuild-and-infer path: the isolated programs, seed 0."""
    from carbon.development_session.profile import canonical
    from carbon.level4 import staging

    spec = adapter.SPECS[KEY]
    material = physical_material.bundle_material(*KEY)
    kit = material["construction_kit"]
    return direct_graph_construction_worker.reconstruct_and_infer_graph_public(
        SimpleNamespace(root=tmp_path),
        owner="test",
        identity="test",
        image=_image(),
        recipe=recipe,
        challenge_binding={
            "challenge_id": kit["id"],
            "challenge_version": kit["version"],
            "train_digest": kit["train_digest"],
            "interface_digest": kit["interface_digest"],
            "construction_limits_digest": kit["construction_limits_digest"],
        },
        limits_document=material["construction_limits_document"],
        source_envelope=canonical(staging.envelope(raw_manifest, files)),
        train=material["train"],
        inputs=np.ascontiguousarray(query),
        expected_output_shape=(len(query), spec.outputs),
        allowlist_bytes=adapter.served_allowlist_bytes(*KEY),
        seed=0,
        runner=_local_runner(),
        adapter_id=spec.adapter_id,
    )


def _motor_kit():
    """The Motor data kit's own module (kits/motor/kit.py), loaded from its file."""
    import importlib.util

    path = ROOT / "kits" / "motor" / "kit.py"
    spec = importlib.util.spec_from_file_location("_motor_data_kit", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _recipe_bytes(recipe):
    return json.dumps(recipe.to_dict(), sort_keys=True).encode("utf-8")


@pytest.fixture(scope="module")
def agreed(tmp_path_factory):
    verify_raw, verify_doc, query = _verify_set()
    with _x64():
        raw_manifest, files, digest = _graph()
        recipe = _recipe({"training": {"steps": STEPS}}, digest)
        official = _official(
            tmp_path_factory.mktemp("official"), recipe, raw_manifest, files, query
        )
        report = local_scorer.score(
            _recipe_bytes(recipe),
            raw_manifest,
            files,
            verify_raw,
            _sha(verify_raw),
            timing_calls=3,
        )
    whole = np.asarray(official.inference.predictions, dtype=adapter.SPECS[KEY].dtype)
    return SimpleNamespace(
        official=whole,
        # The torque curve every Motor check reads from an official row: the whole row, or the torque slice of a
        # 240-wide Motor 1.8 row (its public split, `carbon.motor.row18`, which the grade also uses).
        official_torque=np.asarray(
            [local_scorer.motor_torque(row) for row in whole],
            dtype=adapter.SPECS[KEY].dtype,
        ),
        report=report,
        verify_raw=verify_raw,
        verify_doc=verify_doc,
        raw_manifest=raw_manifest,
        files=files,
        recipe=recipe,
    )


def test_the_kit_scorer_s_predictions_are_bit_equal_to_the_official_path(agreed):
    report = agreed.report
    assert report["admission"]["state"] == "ADMITTED"
    assert report["seed"] == 0
    kit = np.asarray(
        [row["prediction"]["torque_nm"] for row in report["designs"]],
        dtype=adapter.SPECS[KEY].dtype,
    )
    assert kit.shape == agreed.official_torque.shape
    assert kit.tobytes() == np.ascontiguousarray(agreed.official_torque).tobytes()
    # the WHOLE official row (every slice of a 240-wide one) is bit-equal through the report's predictions sha256
    assert agreed.official.shape == (len(FRACTIONS), adapter.SPECS[KEY].outputs)
    assert report["predictions_sha256"] == _sha(
        np.ascontiguousarray(agreed.official).tobytes()
    )


def test_gates_and_the_verify_check_equal_the_official_exam_on_official_predictions(
    agreed,
):
    from carbon.motor import exam

    motor_kit = _motor_kit()
    rows = agreed.report["designs"]
    for row, curve in zip(rows, agreed.official_torque):
        verdict = exam.evaluate_case(
            {"torque_nm": [float(v) for v in curve]}, {"status": "OK"}
        )
        assert row["gates"] == verdict["gates"]
        assert row["gates"] == exam.gates({"torque_nm": [float(v) for v in curve]})
        assert row["state"] == verdict["state"]
    records = [
        {
            "case_id": design["case_id"],
            "status": "OK",
            "outputs": {"torque_nm": [float(v) for v in curve]},
        }
        for design, curve in zip(agreed.verify_doc["designs"], agreed.official_torque)
    ]
    kit_verify = motor_kit.verify_compare(agreed.verify_doc, records)
    for row, theirs in zip(rows, kit_verify["designs"]):
        assert row["case_id"] == theirs["case_id"]
        assert row["accuracy_vs_u"]["within_u"] is theirs["pass"]
    aggregate = agreed.report["aggregate"]
    assert aggregate["n_designs"] == len(FRACTIONS)
    assert aggregate["n_gate_failed"] == sum(
        r["state"] == exam.GATE_FAILED for r in rows
    )
    assert aggregate["accuracy_vs_u"]["n_within_u"] == sum(
        theirs["pass"] for theirs in kit_verify["designs"]
    )


def test_the_report_names_the_budget_not_evaluated_parts_timing_and_the_commit(
    agreed,
):
    report = agreed.report
    budget = report["information_budget"]
    assert type(budget["counted_bytes"]) is int and budget["counted_bytes"] > 0
    if type(budget["cap_bytes"]) is int:
        assert budget["counted_bytes"] <= budget["cap_bytes"]
    hidden = report["not_evaluated_locally"]
    for name in ("D", "picks", "regret", "pool_score", "official_speed_gate"):
        assert hidden[name]["status"] == "not evaluated locally"
    assert report["local_timing"]["label"] == "local estimate, not the official gate"
    code = report["code"]
    assert set(local_scorer.CODE_MODULES) == set(code["modules_sha256"])
    head = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    if head.returncode == 0:
        assert code["commit"] == head.stdout.strip()
    # No path of this machine in the report.
    assert str(ROOT) not in json.dumps(report)


def _official_refusal(tmp_path, recipe, raw_manifest, files, query):
    try:
        _official(tmp_path, recipe, raw_manifest, files, query)
    except direct_graph_construction_worker.GraphConstructionDecision as decision:
        return decision.state, decision.detail_code
    except RecipeRefused as error:
        return None, error.code
    raise AssertionError("the official path admitted the fixture")


#: Refusal fixtures from test_graph_route_v2's keep list: a candidate refusal and a
#: Carbon gap.
REFUSALS = [
    {
        "training": {"steps": STEPS},
        "output_weights": [0.0] * adapter.SPECS[KEY].outputs,
    },
    {"training": {"steps": STEPS, "h1_weight": 1.0}},
]


@pytest.mark.parametrize("configuration", REFUSALS)
def test_a_recipe_the_official_intake_refuses_is_refused_with_the_same_code(
    configuration, tmp_path
):
    verify_raw, _doc, query = _verify_set()
    with _x64():
        raw_manifest, files, digest = _graph()
        recipe = _recipe(configuration, digest)
        state, code = _official_refusal(tmp_path, recipe, raw_manifest, files, query)
        report = local_scorer.score(
            _recipe_bytes(recipe), raw_manifest, files, verify_raw, _sha(verify_raw)
        )
    assert report["admission"]["detail_code"] == code
    assert report["admission"]["state"] in ("REFUSED", "UNRESOLVED")
    if state is not None:
        assert report["admission"]["state"] == state
    assert "designs" not in report and "aggregate" not in report


def test_a_wrong_verify_sha256_refuses(agreed):
    with pytest.raises(local_scorer.ScorerRefused):
        local_scorer.score(
            _recipe_bytes(agreed.recipe),
            agreed.raw_manifest,
            agreed.files,
            agreed.verify_raw,
            "0" * 64,
        )


def test_the_cli_agrees_and_its_run_time_import_closure_is_clean(agreed, tmp_path):
    from carbon.level4 import staging

    submission = tmp_path / "submission"
    staging.write_directory(submission, agreed.raw_manifest, agreed.files)
    (tmp_path / "recipe.json").write_bytes(_recipe_bytes(agreed.recipe))
    (tmp_path / "verify.json").write_bytes(agreed.verify_raw)
    out = tmp_path / "score.json"
    argv = [
        "score",
        "--recipe",
        str(tmp_path / "recipe.json"),
        "--submission-dir",
        str(submission),
        "--verify",
        str(tmp_path / "verify.json"),
        "--verify-sha256",
        _sha(agreed.verify_raw),
        "--out",
        str(out),
        "--timing-calls",
        "2",
    ]
    program = (
        "import json, sys\n"
        f"sys.path.insert(0, {str(ROOT)!r})\n"
        "from carbon.challenge_kit import local_scorer\n"
        f"rc = local_scorer.main({argv!r})\n"
        f"bad = sorted(m for m in sys.modules if any(b in m for b in {FORBIDDEN!r}))\n"
        "print(json.dumps({'rc': rc, 'bad': bad}))\n"
    )
    done = subprocess.run(
        [sys.executable, "-I", "-c", program],
        cwd=tmp_path,
        env={**os.environ, "JAX_PLATFORMS": "cpu"},
        capture_output=True,
        text=True,
        timeout=900,
        check=False,
    )
    assert done.returncode == 0, done.stderr[-4000:]
    result = json.loads(done.stdout.strip().splitlines()[-1])
    assert result == {"rc": 0, "bad": []}
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["predictions_sha256"] == agreed.report["predictions_sha256"]
    assert str(tmp_path) not in out.read_text(encoding="utf-8")


def test_a_motor_check_reads_the_torque_slice_of_a_1_8_row():
    from carbon.motor import exam

    torque = [2.0 + 0.001 * k for k in range(60)]
    row = torque + [0.01] * 180
    assert local_scorer.motor_torque(row) == torque
    assert local_scorer.motor_torque(torque) == torque  # a 60-angle row as it is
    design = {"case_id": "d", "truth": {"torque_nm": torque}}
    whole = local_scorer._motor_design(design, row, None)
    assert whole["prediction"] == {"torque_nm": torque}
    assert whole["state"] == exam.SCORABLE
    # a row that is neither is left as it is: Motor's own schema gate fails it
    broken = local_scorer._motor_design(design, row[:-1], None)
    assert broken["gates"]["schema_finite"] == exam.FAIL
