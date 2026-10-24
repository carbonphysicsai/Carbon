"""Calibration-grade tool (Validator ruling, option B; VALIDATOR_PROOF_RUN_SPEC_20261023).

Grades one *built artifact* (a pod build: recipe, trained state and a manifest,
``carbon.calibration-artifact.v1``) against a calibration pack's sealed query, inside
custody, and returns **aggregates only**. It exists so the proof run can compare the
scoring on floor / KRR / default / good models and on deliberately flawed controls
without forging the receipts the official path trusts.

What it does, in order:

1. ``load_artifact`` verifies the artifact directory against its ``SHA256SUMS`` and
   manifest, and (when pinned) against the named recipe digest, state digest, bundle
   digest, worker image and registered TRAIN digest; any mismatch refuses.
2. ``grade`` runs the inference step (injected ``infer``; ``worker_infer`` wraps the
   same ``_infer_state`` the official regrade uses: the C-03 worker on the judge
   image) on the sealed query, probes included, three times: the graded run and the
   two paired repeats.
3. Registered ``ctrl.*`` output transforms are applied to the in-custody predictions
   (graded run and repeats alike) before grading; nothing leaves custody.
4. The predictions are measured by the Challenge's adapter and scored by
   ``dual_score.score``, the calls ``physical_dual_pack.produce`` makes.
5. The output is aggregates only (``aggregates``): no per-case rows, probes,
   references, inputs or predictions.

This module never writes the official ledger, custody receipts or retention. Its
results belong to a calibration run and carry a calibration entry id of their own;
they are never evidence for an official grade.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path

ARTIFACT_SCHEMA = "carbon.calibration-artifact.v1"
RESULT_SCHEMA = "carbon.calibration-grade.v1"
FILES = ("recipe.json", "state.npz", "manifest.json")
MANIFEST_KEYS = frozenset(
    {
        "schema",
        "challenge_id",
        "version",
        "recipe_digest",
        "state_sha256",
        "bundle_ref",
        "bundle_sha256",
        "worker_image_digest",
        "parent_image_digest",
        "runtime",
        "gpu_model",
        "driver",
        "cuda",
        "train_sha256",
        "seed",
        "build_wall_s",
        "pod_id",
        "built_at",
    }
)
_HEX = frozenset("0123456789abcdef")
_DIGEST_RE = re.compile(r"sha256:[0-9a-f]{64}")


class CalibrationRefused(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _require(ok, code):
    if not ok:
        raise CalibrationRefused(code)


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _digest(value):
    bare = value[7:] if type(value) is str and value.startswith("sha256:") else value
    return type(bare) is str and len(bare) == 64 and set(bare) <= _HEX


@dataclass(frozen=True)
class Artifact:
    directory: Path
    recipe_bytes: bytes
    state_bytes: bytes
    manifest: dict

    @property
    def recipe_digest(self):
        return "sha256:" + _sha(self.recipe_bytes)

    @property
    def state_digest(self):
        return "sha256:" + _sha(self.state_bytes)

    @property
    def calibration_entry_id(self):
        """Names this build in the calibration store; never an official entry id."""
        return "sha256:" + _sha(
            b"calibration:" + (self.recipe_digest + self.state_digest).encode()
        )


def _read(directory, name):
    path = directory / name
    _require(
        path.is_file() and not path.is_symlink(), "calibration_artifact_file_missing"
    )
    return path.read_bytes()


def load_artifact(
    directory,
    *,
    challenge_id=None,
    recipe_digest=None,
    state_sha256=None,
    bundle_sha256=None,
    worker_image_digest=None,
    train_sha256=None,
):
    """The verified artifact in ``directory``. Every pin given must equal the
    manifest's; the manifest's own digests must equal the files'."""
    directory = Path(directory)
    _require(directory.is_dir() and not directory.is_symlink(), "calibration_artifact")
    raw = {name: _read(directory, name) for name in FILES}
    sums = {}
    for line in _read(directory, "SHA256SUMS").decode("utf-8").splitlines():
        parts = line.split()
        _require(len(parts) == 2 and parts[1] not in sums, "calibration_sums_format")
        sums[parts[1].lstrip("*")] = parts[0]
    _require(set(sums) == set(FILES), "calibration_sums_files")
    _require(
        all(_sha(raw[name]) == sums[name] for name in FILES), "calibration_sums_differ"
    )
    try:
        manifest = json.loads(raw["manifest.json"])
    except ValueError as exc:
        raise CalibrationRefused("calibration_manifest_malformed") from exc
    _require(
        type(manifest) is dict
        and set(manifest) == MANIFEST_KEYS
        and manifest["schema"] == ARTIFACT_SCHEMA,
        "calibration_manifest_shape",
    )
    artifact = Artifact(directory, raw["recipe.json"], raw["state.npz"], manifest)
    _require(
        manifest["recipe_digest"] == artifact.recipe_digest, "calibration_recipe_digest"
    )
    _require(
        manifest["state_sha256"] in (artifact.state_digest, _sha(raw["state.npz"])),
        "calibration_state_digest",
    )
    for field in ("worker_image_digest", "bundle_sha256", "train_sha256"):
        _require(_digest(manifest[field]), "calibration_manifest_" + field)
    for pinned, field, code in (
        (challenge_id, "challenge_id", "calibration_challenge"),
        (recipe_digest, "recipe_digest", "calibration_pin_recipe"),
        (state_sha256, "state_sha256", "calibration_pin_state"),
        (bundle_sha256, "bundle_sha256", "calibration_pin_bundle"),
        (worker_image_digest, "worker_image_digest", "calibration_pin_image"),
        (train_sha256, "train_sha256", "calibration_pin_train"),
    ):
        if pinned is not None:
            _require(manifest[field] == pinned, code)
    return artifact


# ---------------------------------------------------------------- controls


def _probe_records(bank):
    return [
        (i, record["probe"])
        for i, (cohort, record) in enumerate(
            zip(bank["cohorts"], bank["reference_records"], strict=True)
        )
        if cohort == "probe_response" and type(record) is dict and "probe" in record
    ]


def _number(params, name):
    value = params.get(name)
    _require(
        type(value) in (int, float) and math.isfinite(value),
        "control_param:" + name,
    )
    return float(value)


def _invert_response(rows, bank, params):
    """C-trend: every response probe's plus/minus outputs reflected about its base,
    y' = 2 y_base - y, so the trend between cases is reversed while every base (and
    every graded cell) is untouched."""
    from carbon.scoring import probe_design

    out = [list(r) for r in rows]
    for group in probe_design.groups(_probe_records(bank)):
        base = rows[group["base"]]
        for pair in group["dims"].values():
            for i in pair:
                out[i] = [2 * b - v for b, v in zip(base, rows[i], strict=True)]
    return out


def _law_rows(bank, name):
    from carbon.scoring import probe_design

    return [law for _, law in probe_design.law_pairs(_probe_records(bank), name)]


def _shift_law(name, columns):
    def apply(rows, bank, params):
        shift = _number(params, "shift")
        out = [list(r) for r in rows]
        for i in _law_rows(bank, name):
            for c in columns(len(out[i])):
                out[i][c] += shift
        return out

    return apply


def _scale_law(name):
    def apply(rows, bank, params):
        factor = _number(params, "factor")
        out = [list(r) for r in rows]
        for i in _law_rows(bank, name):
            out[i] = [v * factor for v in out[i]]
        return out

    return apply


#: F08 output order (``f08_train.TARGETS``): the zeta 0.01 and 0.02 peak tips.
_F08_TIPS = (3, 5)


def _zeta_independent(rows, bank, params):
    """C-law (F08): every geometry's zeta 0.01 and 0.02 peaks made independent of the
    damping scaling by an alternating relative error of ``relative``."""
    relative = _number(params, "relative")
    out = [list(r) for r in rows]
    for i, row in enumerate(out):
        for k, column in enumerate(_F08_TIPS):
            row[column] *= 1 + relative * (1 if (i + k) % 2 == 0 else -1)
    return out


def _pick_wrong_margins(rows, bank, params):
    """C-pick: the reference's own outputs with the named output columns perturbed
    by the default model's measured margin error (``errors``: column -> error). The
    artifact's predictions are not used for the exam cells; the unreferenced private
    probe rows keep them (a probe has no reference)."""
    errors = params.get("errors")
    _require(type(errors) is dict and errors, "control_param:errors")
    present = bank.get("reference_present") or (True,) * len(rows)
    out = []
    for i, ref in enumerate(bank["references"]):
        if not present[i]:
            out.append(list(rows[i]))
            continue
        row = [float(v) for v in ref]
        for column, error in errors.items():
            _require(
                type(column) is str
                and column.isdigit()
                and int(column) < len(row)
                and type(error) in (int, float)
                and math.isfinite(error),
                "control_param:errors",
            )
            row[int(column)] += float(error) * (1 if i % 2 == 0 else -1)
        out.append(row)
    return out


def _train_mean(rows, bank, params):
    """The floor: every row (probes included) is the public TRAIN mean of the outputs, a
    deterministic constant. The model's predictions are not read at all, only the shape
    of the query. The mean is over the output columns the grader MEASURES: for an
    interface whose rows are encoded and decoded by the adapter (Cooling 1.3/1.4), it
    is the native TRAIN mean, encoded so that the adapter's decode returns exactly that
    mean; for any other interface it is the public TRAIN's own column mean. A TRAIN
    whose width differs from the rows refuses (fail closed, never approximated)."""
    import io

    import numpy as np

    raw = params.get("_train_raw")
    _require(type(raw) is bytes, "control_train_required")
    native = getattr(params.get("_adapter"), "_native_train", None)
    if native is not None:
        raw = native()
        _require(type(raw) is bytes, "control_train_required")
    with np.load(io.BytesIO(raw), allow_pickle=False) as data:
        targets = np.asarray(data["targets"], dtype=float)
    _require(targets.ndim == 2 and len(targets) > 0, "control_train_shape")
    mean = targets.mean(axis=0)
    _require(bool(np.all(np.isfinite(mean))), "control_train_finite")
    if native is not None:
        from carbon.cold_plate import output_encoding

        try:
            mean = output_encoding.encode_targets(mean[None, :])[0]
        except ValueError as exc:
            raise CalibrationRefused("control_train_encode") from exc
    mean = [float(v) for v in mean]
    _require(all(len(row) == len(mean) for row in rows), "control_train_width")
    return [list(mean) for _ in rows]


#: Controls that read the public TRAIN (passed by the tool, never by the caller).
TRAIN_CONTROLS = frozenset({"ctrl.train_mean"})

#: name -> (the leg it moves, challenges it applies to, transform, required params).
CONTROLS = {
    "ctrl.train_mean": ("total", None, _train_mean, ()),
    "ctrl.invert_response": ("A_response", None, _invert_response, ()),
    "ctrl.pick_wrong_margins": ("D", None, _pick_wrong_margins, ("errors",)),
    "ctrl.zeta_independent": ("A_law", ("f08",), _zeta_independent, ("relative",)),
    "ctrl.nonaffine_power": (
        "A_law",
        ("f02",),
        _shift_law("affine_up", lambda width: range(width)),
        ("shift",),
    ),
    "ctrl.nonlinear_current": (
        "A_law",
        ("motor",),
        _scale_law("j_up"),
        ("factor",),
    ),
    # Cooling: the peak and the 30 profile segments are columns 0..30 (the pressure
    # drop is 31), as ``cooling_physics`` reads them.
    "ctrl.inlet_shift_broken": (
        "A_law",
        ("cooling",),
        _shift_law("inlet_shift", lambda width: range(31)),
        ("shift",),
    ),
}


def config_digest(run_config):
    """The digest a controlled run is pinned to: ``sha256:`` over the canonical JSON of
    its run config (the controls and the rule their magnitudes were set by)."""
    return "sha256:" + _sha(
        json.dumps(
            run_config, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    )


def _require_config(control, run_config, digest):
    """A control runs only under a run config, fixed before grading, that names it
    with exactly its parameters and hashes to the digest the caller was given."""
    _require(
        type(run_config) is dict
        and type(digest) is str
        and _DIGEST_RE.fullmatch(digest) is not None,
        "control_run_config_required",
    )
    _require(config_digest(run_config) == digest, "control_run_config_digest")
    listed = run_config.get("controls")
    _require(
        type(listed) is list
        and any(
            type(c) is dict
            and c.get("name") == control["name"]
            and c.get("params", {}) == control.get("params", {})
            for c in listed
        ),
        "control_run_config_mismatch",
    )


def apply_control(control, rows, bank, challenge, train_raw=None, adapter=None):
    """``rows`` (a list of rows, probes included) transformed by one registered
    control: ``{"name": ..., "params": {...}}``."""
    _require(type(control) is dict and set(control) <= {"name", "params"}, "control")
    name = control.get("name")
    _require(name in CONTROLS, "control_unregistered")
    _leg, challenges, transform, required = CONTROLS[name]
    _require(challenges is None or challenge in challenges, "control_challenge:" + name)
    params = control.get("params", {})
    _require(
        type(params) is dict and all(k in params for k in required),
        "control_params:" + name,
    )
    if name in TRAIN_CONTROLS:
        params = {**params, "_train_raw": train_raw, "_adapter": adapter}
    out = transform(rows, bank, params)
    _require(
        len(out) == len(rows) and all(len(a) == len(b) for a, b in zip(out, rows)),
        "control_shape",
    )
    return out


# --------------------------------------------------------------- aggregates


def _aggregate(value, depth=0):
    """Scalars, small dicts of aggregates and lists of names: never a list of numbers
    (a per-case row), so nothing per case can pass through."""
    if value is None or type(value) in (bool, int, float, str):
        return value
    if type(value) is dict and depth < 3:
        return {str(k): _aggregate(v, depth + 1) for k, v in sorted(value.items())}
    if type(value) is list and all(type(v) is str for v in value):
        return sorted(value)
    return None


def aggregates(measured, total, *, entry_id, control=None, challenge=None):
    document = {
        "schema": RESULT_SCHEMA,
        "calibration_entry_id": entry_id,
        "challenge": challenge,
        "control": control["name"] if control else None,
        "A": measured.get("A"),
        "A_legs": _aggregate(measured.get("A_legs")),
        "D": measured.get("D"),
        "D_parts": _aggregate(measured.get("design_fidelity")),
        "total": total,
        "gates": {k: bool(v) for k, v in sorted(measured["gates"].items())},
        "physics_half": _aggregate(measured.get("physics_half")),
        "decision_outcome": measured.get("decision_outcome"),
    }
    return document


# -------------------------------------------------------------------- grade


def worker_infer(
    *,
    ledger,
    owner,
    identity,
    inference_image,
    recipe,
    binding,
    state,
    state_digest,
    expected_output_shape,
    expected_output_dtype,
    allowlist_bytes,
    seconds,
    accelerator=None,
    runner=None,
):
    """``infer(inputs) -> rows`` over the same inference step the official regrade
    uses (``bundle_construction_worker._infer_state``: the C-03 worker on the judge
    image, the same sandbox and limits). ``ledger`` is the calibration run's own,
    never the official one."""
    from carbon.development_session import bundle_construction_worker as worker

    def infer(inputs):
        result = worker._infer_state(
            ledger,
            owner=owner,
            identity=identity,
            inference_image=inference_image,
            recipe=recipe,
            binding=binding,
            state=state,
            state_digest=state_digest,
            inputs=inputs,
            expected_output_shape=(len(inputs), *expected_output_shape[1:]),
            expected_output_dtype=expected_output_dtype,
            allowlist_bytes=allowlist_bytes,
            seconds=seconds,
            accelerator=accelerator,
            runner=runner,
        )
        return [[float(v) for v in row] for row in result.predictions]

    return infer


def grade(
    *,
    adapter,
    bank,
    pack,
    definition,
    limits,
    objective,
    train_raw,
    interface_names,
    infer,
    artifact=None,
    entry_id=None,
    control=None,
    challenge=None,
    population_role="P",
    run_config=None,
    run_config_digest=None,
):
    """Aggregates for one model on the calibration pack's sealed bank.

    ``infer(inputs)`` returns the model's rows for the bank's inputs (called three
    times: the graded run and the two paired repeats); with ``ctrl.pick_wrong_margins``
    the artifact's predictions are not used. ``pack`` is the pack's ``score_pack``."""
    import numpy as np

    from carbon.scoring.dual_score import score
    from carbon.scoring.physical_dual_pack import METRICS, bank_rows

    _require(artifact is not None or entry_id is not None, "calibration_entry")
    entry_id = entry_id or artifact.calibration_entry_id
    if control is not None:
        _require_config(control, run_config, run_config_digest)
    inputs = np.array(bank["inputs"])
    runs = [infer(inputs) for _ in range(3)]
    if control is not None:
        runs = [
            apply_control(
                control, r, bank, challenge, train_raw=train_raw, adapter=adapter
            )
            for r in runs
        ]
    graded, repeats = runs[0], runs[1:]
    try:
        measured = adapter.measure(
            bank_rows=bank_rows(bank, interface_names),
            outputs=graded,
            repeats=repeats,
            definition=definition,
            limits=limits,
            objective=objective,
            train_raw=train_raw,
            names=interface_names,
        )
    except adapter.Refused as exc:
        raise CalibrationRefused("dual_native_" + exc.code) from exc
    gates = list(pack.get("hard_gates", []))
    _require(gates == list(measured["gates"]), "dual_native_gate_contract")

    def leg(value):
        if value is None:
            return {"status": "CANDIDATE_INVALID", "value": None, "unit": "1"}
        return {"status": "RESOLVED", "value": value, "unit": "1"}

    benchmark = {
        "schema": "carbon.scoring.dual-benchmark-input.v1",
        "scope": pack["scope"],
        "challenge": adapter.CHALLENGE,
        "physics_contract_digest": pack["physics_contract_digest"],
        "measurement_contract_digest": pack["measurement_contract_digest"],
        "population_role": population_role,
        "common_mask_digest": "sha256:"
        + _sha(json.dumps(list(bank["case_ids"]), separators=(",", ":")).encode()),
        "models": [
            {
                "artifact_digest": entry_id,
                "gates": {
                    k: ("PASS" if measured["gates"][k] else "FAIL") for k in gates
                },
                "measurements": {
                    METRICS["A"]: leg(measured["A"]),
                    METRICS["D"]: leg(measured["D"]),
                },
                "decision_outcome": measured["decision_outcome"],
            }
        ],
    }
    total = score(benchmark, pack)["models"][0]["score"]
    document = aggregates(
        measured,
        total,
        entry_id=entry_id,
        control=control,
        challenge=challenge or adapter.CHALLENGE,
    )
    if control is not None:
        document["run_config_digest"] = run_config_digest
    return document


def leg_delta(graded, controlled):
    """What a control moved: the controlled run's A legs, A, D and total minus the
    uncontrolled run's (numbers only), so a control's collateral on another leg (the
    F08 zeta control also moves A_acc a little) is reported beside the leg it targets.
    """

    def numbers(document):
        flat = {f"A_legs.{k}": v for k, v in (document.get("A_legs") or {}).items()}
        flat.update({k: document.get(k) for k in ("A", "D", "total")})
        return flat

    before, after = numbers(graded), numbers(controlled)
    return {
        k: after[k] - before[k]
        for k in sorted(before)
        if type(before[k]) in (int, float) and type(after.get(k)) in (int, float)
    }


__all__ = [
    "ARTIFACT_SCHEMA",
    "CONTROLS",
    "RESULT_SCHEMA",
    "Artifact",
    "CalibrationRefused",
    "aggregates",
    "apply_control",
    "config_digest",
    "grade",
    "leg_delta",
    "load_artifact",
    "worker_infer",
]
