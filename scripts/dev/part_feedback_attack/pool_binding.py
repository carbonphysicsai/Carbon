"""The custody binding of the part-feedback leak attack for a POOL-GRADED Challenge version (Motor 1.5 first).

``attack.py run --binding pool_binding:make`` loads this. It grades a PERTURBED model on the sealed exam and on a fresh draw by the
SAME calls the receiver and `calibration_grade` use; it adds no scoring of its own:

    calibration_grade_run.prepare / resolve_bank / _roles / graded_definition      (the pack as the receiver reads it)
    calibration_grade.grade(infer=...)  ->  adapter.measure (pool_version.PoolVariant.measure -> pool_exam.measure_pool,
                                            motor_sealed_dual_pack.measure) -> dual_score.score

**A perturbation of a model.** The model is the RETAINED baseline's predictions (theta = 0: the king-free baseline, graded under the
judge pack) plus a smooth, low-dimensional output field: for every exam row ``x`` (the pool lookup is exact-input, so the change is a
pure function of the INPUT ROW, never of its position)

    rows(x) = base(x) + amplitude * column_scale * sum_k theta_k * cos(w_k . z(x) + b_k),   z = (x - mu) / sd

with ``w_k``, ``b_k`` drawn once from ``field_seed`` and ``mu``, ``sd`` fixed from the SEALED bank's inputs (so a design that appears
in both sets is perturbed identically). ``column_scale`` is each output column's standard deviation over the sealed baseline. Nothing
about a case enters the output. The field, its seed and its amplitude are NUMERICAL settings in the config, recorded in the digest.

**The fresh set** is graded like-for-like, as a POOL SET of the same Challenge version: a second pack root in the same format as the
sealed pack (the fresh QA-passed designs, solved in custody, packaged with the same tools), read by the same loader. The custody
operator builds it; this module only reads it and refuses a pack of another Challenge, version or output width.

CONFIG (JSON, custody; the path is ``CARBON_LEAK_BINDING_CONFIG`` or the ``make(config_path=...)`` argument):

    {"challenge": "electric-motor-magnetics", "version": "1.5", "dim": 8, "amplitude": ..., "field_seed": ...,
     "copy_hotkey": "<the validator's own hotkey>",
     "sealed": {"pack_root": "...", "baseline_predictions": "..."},
     "fresh":  {"pack_root": "...", "baseline_predictions": "..."}}

``copy_hotkey`` is REQUIRED (no default): a sealed pack in the store is graded in the canonical form of the validator's signed copy
(``.copies/<digest>/``), exactly as the receiver does; read without it the same baseline grades differently and is not scored
(found at the first custody check). Both sets use it, and it is in the config and so in the digest.

``baseline_predictions`` is a file holding the baseline's predictions for that set in bank order: the retained
``worker-evidence.json`` (``predictions_raw_base64``: n x width in the interface dtype) or ``{"rows": [[...], ...]}``. The amplitude is
required (no default): it is a numerical setting the operator chooses and the Validator receipts with the digest.

    python3 pool_binding.py check  --config CFG.json    # theta = 0 on both sets: status, total, and the baseline_total difference
    python3 pool_binding.py digest --config CFG.json    # the binding digest the Validator receipts before the run

The output of ``check`` and ``digest`` is aggregates only: no row, no case id, no prediction.
"""

from __future__ import annotations

import base64
import hashlib
import json
import math
import os
import random
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SCHEMA = "carbon.part-feedback.pool-binding.v1"
ENV_CONFIG = "CARBON_LEAK_BINDING_CONFIG"
PLACEHOLDER_GATE = (
    "speed"  # calibration_grade drops it from the aggregates; so does this binding
)


class BindingRefused(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _need(ok, code):
    if not ok:
        raise BindingRefused(code)


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


# ---------------------------------------------------------------- config


TOP_KEYS = frozenset(
    {
        "challenge",
        "version",
        "dim",
        "amplitude",
        "field_seed",
        "copy_hotkey",
        "catalog_recipe_digest",
        "sealed",
        "fresh",
    }
)
SIDE_REQUIRED = frozenset({"pack_root", "baseline_predictions"})
SIDE_PINS = frozenset({"baseline_recipe_digest", "baseline_state_digest"})
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")


def load_config(path):
    """The validated config. ANY key it does not know is refused, at the top level and in each side: a setting that is silently
    ignored (a pin put in the wrong place) is worse than no setting."""
    document = json.loads(Path(path).read_bytes())
    _need(type(document) is dict, "config_shape")
    unknown = sorted(set(document) - TOP_KEYS)
    _need(not unknown, f"config_unknown_key:{unknown[0] if unknown else ''}")
    for key in ("challenge", "version"):
        _need(type(document.get(key)) is str and document[key], f"config_{key}")
    _need(type(document.get("dim")) is int and 1 <= document["dim"] <= 64, "config_dim")
    amplitude = document.get("amplitude")
    _need(
        type(amplitude) in (int, float) and math.isfinite(amplitude) and amplitude > 0,
        "config_amplitude_required",
    )
    _need(type(document.get("field_seed")) is int, "config_field_seed")
    _need(
        type(document.get("copy_hotkey")) is str and document["copy_hotkey"],
        "config_copy_hotkey_required",
    )
    # the link from the catalog recipe to the recipe that was built from it (attested from the task's receiver record)
    _need(
        type(document.get("catalog_recipe_digest")) is str
        and _DIGEST.fullmatch(document["catalog_recipe_digest"]),
        "config_catalog_recipe_digest_required",
    )
    for side in ("sealed", "fresh"):
        entry = document.get(side)
        _need(type(entry) is dict, f"config_{side}")
        extra = sorted(set(entry) - SIDE_REQUIRED - SIDE_PINS)
        _need(not extra, f"config_{side}_unknown_key:{extra[0] if extra else ''}")
        _need(SIDE_REQUIRED <= set(entry), f"config_{side}")
        _need(all(type(v) is str and v for v in entry.values()), f"config_{side}")
        for pin in SIDE_PINS & set(entry):
            _need(_DIGEST.fullmatch(entry[pin]), f"config_{side}_{pin}")
    return document


def inputs_digest(bank_inputs, dtype):
    """The digest of a bank's inputs the way the receiver computes it for the inference pair
    (``paired_inference``: ``_digest(_tensors(inputs=rows))``, the ``.npz`` bytes of the rows in the interface dtype).
    """
    import numpy as np

    from carbon.development_session.bundle_construction_worker import _digest, _tensors

    return _digest(_tensors(inputs=np.asarray(bank_inputs, dtype=np.dtype(dtype))))


def _pair_predictions(
    document, expected_inputs_digest, expected_recipe_digest, expected_state_digest=None
):
    """The ``primary`` predictions of a retained ``inference-pair.json`` (``carbon.source-free-inference-pair.v1``), refused unless
    the primary and the repeat are BIT-FOR-BIT the same bytes, each equals its recorded sha256, the pair was run on exactly this
    set's bank inputs, and (when pinned) was run by the pinned recipe. Returns ``(rows, summary)``.
    """
    _need(
        document.get("schema") == "carbon.source-free-inference-pair.v1", "pair_schema"
    )
    _need(expected_inputs_digest is not None, "pair_needs_inputs_digest")
    _need(
        document.get("inputs_digest") == expected_inputs_digest,
        "pair_inputs_digest_differs",
    )
    if expected_recipe_digest is not None:
        _need(
            document.get("recipe_digest") == expected_recipe_digest,
            "pair_recipe_digest_differs",
        )
    if expected_state_digest is not None:
        _need(
            document.get("state_digest") == expected_state_digest,
            "pair_state_digest_differs",
        )
    raw = {}
    for phase in ("primary", "repeat"):
        try:
            original = document[phase]["originals"]["predictions.json"]
            body = base64.b64decode(original["raw_base64"], validate=True)
            recorded = original["sha256"]
        except (KeyError, TypeError, ValueError) as exc:
            raise BindingRefused(f"pair_{phase}_unreadable") from exc
        _need(recorded == "sha256:" + _sha(body), f"pair_{phase}_changed")
        raw[phase] = body
    _need(raw["primary"] == raw["repeat"], "pair_primary_differs_from_repeat")
    summary = {
        "recipe_digest": document.get("recipe_digest"),
        "state_digest": document.get("state_digest"),
        "inputs_digest": document["inputs_digest"],
        "predictions_sha256": "sha256:" + _sha(raw["primary"]),
    }
    try:
        rows = json.loads(raw["primary"])
    except ValueError as exc:
        raise BindingRefused("pair_primary_unreadable") from exc
    return rows, summary


def read_baseline(
    path,
    rows,
    width,
    dtype,
    *,
    inputs_digest=None,
    recipe_digest=None,
    state_digest=None,
):
    """``(values, pair_summary_or_None)``: the baseline's predictions as ``rows x width`` floats from the retained worker evidence,
    ``{"rows": ...}``, or the retained ``inference-pair.json`` (the primary, after the checks of `_pair_predictions`). A recipe or
    state pin on a file that is NOT an inference pair cannot be checked and is refused, never ignored.
    """
    import numpy as np

    document = json.loads(Path(path).read_bytes())
    _need(type(document) is dict, "baseline_predictions_shape")
    summary = None
    if "primary" in document or "repeat" in document:
        listed, summary = _pair_predictions(
            document, inputs_digest, recipe_digest, state_digest
        )
        values = np.asarray(listed, dtype=float)
        _need(values.shape == (rows, width), "baseline_predictions_size")
    else:
        _need(
            recipe_digest is None and state_digest is None,
            "baseline_pin_unverifiable",
        )
        if "predictions_raw_base64" in document:
            flat = np.frombuffer(
                base64.b64decode(document["predictions_raw_base64"]),
                dtype=np.dtype(dtype),
            )
            _need(flat.size == rows * width, "baseline_predictions_size")
            values = flat.reshape(rows, width).astype(float)
        elif "rows" in document:
            values = np.asarray(document["rows"], dtype=float)
            _need(values.shape == (rows, width), "baseline_predictions_size")
        else:
            raise BindingRefused("baseline_predictions_format")
    _need(bool(np.all(np.isfinite(values))), "baseline_predictions_finite")
    return values, summary


def load_predictions(path, rows, width, dtype, **checks):
    """The predictions of `read_baseline`, without the pair summary."""
    return read_baseline(path, rows, width, dtype, **checks)[0]


def pair_summary(path):
    """For a retained inference-pair file: the recipe, state and inputs digests it records (None for any other format)."""
    document = json.loads(Path(path).read_bytes())
    if type(document) is dict and "primary" in document:
        return {
            k: document.get(k)
            for k in ("recipe_digest", "state_digest", "inputs_digest")
        }
    return None


# ---------------------------------------------------------------- the perturbation field


class Field:
    """The fixed smooth output field. ``delta(inputs, theta)`` is a pure function of each input row."""

    def __init__(self, *, dim, amplitude, seed, mu, sd, column_scale):
        import numpy as np

        rng = random.Random(f"pool-binding-field:{seed}:{dim}")
        width = len(mu)
        self.weights = np.array(
            [[rng.gauss(0.0, 1.0) for _ in range(width)] for _ in range(dim)]
        )
        self.phases = np.array([rng.uniform(0.0, 2.0 * math.pi) for _ in range(dim)])
        self.mu, self.sd = np.asarray(mu, float), np.asarray(sd, float)
        self.column_scale = np.asarray(column_scale, float)
        self.amplitude, self.dim = float(amplitude), dim

    def basis(self, inputs):
        import numpy as np

        z = (np.asarray(inputs, float) - self.mu) / self.sd
        return np.cos(z @ self.weights.T + self.phases)  # rows x dim

    def delta(self, inputs, theta):
        import numpy as np

        _need(len(theta) == self.dim, "theta_dimension")
        field = self.basis(inputs) @ np.asarray(theta, float)  # rows
        return self.amplitude * field[:, None] * self.column_scale[None, :]


# ---------------------------------------------------------------- one graded set


class GradedSet:
    """One set's context: the bank, adapter and roles as the calibration tool reads them, and the baseline rows."""

    def __init__(
        self,
        *,
        bank,
        adapter,
        roles,
        names,
        base_rows,
        challenge,
        graded,
        baseline_pair=None,
    ):
        self.bank, self.adapter, self.roles, self.names = bank, adapter, roles, names
        self.base_rows, self.challenge, self.graded = base_rows, challenge, graded
        self.baseline_pair = (
            baseline_pair  # the retained pair's recorded digests, or None
        )


def _status_and_values(aggregates, pack):
    """``(status, total, legs, gates, reason)`` from calibration_grade's aggregates. A result COUNTS only when A, D and the total
    are finite AND every hard gate (but the calibration's speed placeholder) passes: a miner whose model fails a gate is not
    scored, and neither is a perturbed model here (``reason`` is ``gate:<name>`` for the first failed gate, sorted, or ``gate_missing:<name>`` for a registered gate the aggregates do not carry).
    """
    gates = {
        k: bool(v)
        for k, v in (aggregates.get("gates") or {}).items()
        if k != PLACEHOLDER_GATE
    }
    a, d, total = aggregates.get("A"), aggregates.get("D"), aggregates.get("total")
    finite = all(type(v) in (int, float) and math.isfinite(v) for v in (a, d, total))
    # every registered hard gate must be PRESENT: an absent gate never passes silently
    missing = sorted(
        g
        for g in pack.get("hard_gates", [])
        if g != PLACEHOLDER_GATE and g not in gates
    )
    if missing:
        return (
            "NOT_SCORED",
            total,
            {"A": a, "D": d},
            gates,
            "gate_missing:" + missing[0],
        )
    failed = sorted(k for k, ok in gates.items() if not ok)
    if failed:
        return "NOT_SCORED", total, {"A": a, "D": d}, gates, "gate:" + failed[0]
    if not finite:
        return "NOT_SCORED", total, {"A": a, "D": d}, gates, None
    return "SCORED", total, {"A": a, "D": d}, gates, None


def _components(pack, aggregates):
    """The registered component metrics' values. A leg with ONE registered component is that component (its value is the leg's);
    a leg with several is read from the aggregates by name, and refused when they are not there (never guessed).
    """
    out = {}
    legs = {"A": aggregates.get("A"), "D": aggregates.get("D")}
    named = {}
    for key in ("A_legs", "D_parts"):
        if type(aggregates.get(key)) is dict:
            named.update(aggregates[key])
    for leg, value in legs.items():
        metrics = [c["metric"] for c in pack["legs"][leg]["components"]]
        if len(metrics) == 1:
            out[metrics[0]] = value
            continue
        for metric in metrics:
            _need(
                type(named.get(metric)) in (int, float),
                f"component_values_unavailable:{metric}",
            )
            out[metric] = named[metric]
    return out


class PoolBinding:
    """The binding `attack.py` loads: ``dim``, ``parts_registry()``, ``gate_names()``, ``grade(theta, which)``."""

    def __init__(self, config, sets, field):
        self.config, self.sets, self.field = config, sets, field
        self.dim = field.dim
        self._pack = sets["sealed"].roles["score_pack"]

    def parts_registry(self):
        return {
            leg: tuple(c["metric"] for c in self._pack["legs"][leg]["components"])
            for leg in ("A", "D")
        }

    def gate_names(self):
        return tuple(
            g for g in self._pack.get("hard_gates", []) if g != PLACEHOLDER_GATE
        )

    def rows(self, theta, which):
        """The perturbed model's predictions on one set: the baseline plus the field, as plain lists."""
        graded = self.sets[which]
        delta = self.field.delta(graded.bank["inputs"], theta)
        return (graded.base_rows + delta).tolist()

    def grade(self, theta, which):
        graded = self.sets[which]
        rows = self.rows(theta, which)
        entry = "sha256:" + _sha(
            _canonical([which, [round(float(t), 12) for t in theta]])
        )
        try:
            aggregates = graded.graded(
                infer=lambda _inputs: rows,
                entry_id=entry,
            )
        except _refusal_types() as refusal:
            if not str(getattr(refusal, "code", "")).startswith("dual_native_"):
                raise  # a missing pool, an unreadable role...: the binding is broken, not the model
            return {"status": "NOT_SCORED", "reason": refusal.code}
        status, total, legs, gates, reason = _status_and_values(aggregates, self._pack)
        if status != "SCORED":
            return {"status": status, **({"reason": reason} if reason else {})}
        return {
            "status": status,
            "total": float(total),
            "legs": {k: float(v) for k, v in legs.items()},
            "components": {
                k: float(v) for k, v in _components(self._pack, aggregates).items()
            },
            "gates": gates,
        }


def _refusal_types():
    from carbon.challenge_validator import calibration_grade as cg

    return (cg.CalibrationRefused,)


# ---------------------------------------------------------------- custody loading


#: `copy_package.receive`'s refusals that mean "this pack carries no copy batch for this hotkey".
COPY_MISSING = frozenset(
    {"copy_header_missing", "copy_header_mismatch", "copy_hotkey_missing"}
)
COPY_INVALID = frozenset(
    {
        "copy_header_malformed",
        "copy_batch_malformed",
        "copy_digest_mismatch",
        "canonical_digest_mismatch",
        "copy_challenge_unregistered",
    }
)


def _copy_refusal(refusal):
    """The binding's refusal for a copy-package failure: a pack with no copy batch for the configured hotkey is
    ``copy_batch_missing`` (never read in the non-canonical form instead); a copy that does not verify is
    ``copy_batch_invalid:<code>``. Any other refusal is the caller's own and is returned unchanged.
    """
    code = getattr(refusal, "code", "")
    if code in COPY_MISSING:
        return BindingRefused("copy_batch_missing")
    if code in COPY_INVALID:
        return BindingRefused(f"copy_batch_invalid:{code}")
    return refusal


def _load_set(spec, config, mu_sd=None):
    """One set from a pack root, with the receiver's own loaders. Returns the `GradedSet` and the bank inputs."""
    import numpy as np

    from carbon.challenge_kit import physical_material
    from carbon.challenge_kit.interface_dtype import output_dtype
    from carbon.challenge_validator import calibration_grade as cg
    from carbon.challenge_validator import calibration_grade_run as run

    challenge, version = config["challenge"], config["version"]
    pack_root = Path(spec["pack_root"])
    snapshot = run.prepare(pack_root, challenge, version)
    try:
        bank, adapter, names = run.resolve_bank(
            snapshot, pack_root, challenge, version, config["copy_hotkey"]
        )
    except cg.CalibrationRefused as refusal:
        raise _copy_refusal(refusal) from refusal
    _need(getattr(adapter, "POOL_GRADED", False), "set_is_not_pool_graded")
    roles = run._roles(snapshot, pack_root)
    material = physical_material.bundle_material(challenge, version)
    width = tuple(material["expected_output_shape"])[1:]
    _need(len(width) == 1, "output_width")
    dtype = output_dtype(material["interface_document"])
    base, pair = read_baseline(
        spec["baseline_predictions"],
        len(bank["inputs"]),
        width[0],
        dtype,
        # the receiver's inputs are the retained query in the practice inputs' dtype
        inputs_digest=inputs_digest(bank["inputs"], material["practice_inputs"].dtype),
        recipe_digest=spec.get("baseline_recipe_digest"),
        state_digest=spec.get("baseline_state_digest"),
    )
    definition = run.graded_definition(adapter, bank, roles["definition"])

    def graded(*, infer, entry_id):
        return cg.grade(
            adapter=adapter,
            bank=bank,
            pack=roles["score_pack"],
            definition=definition,
            limits=roles["limits"],
            objective=roles["objective"],
            train_raw=roles["train"],
            interface_names=names,
            infer=infer,
            entry_id=entry_id,
            challenge=adapter.CHALLENGE,
        )

    return (
        GradedSet(
            bank=bank,
            adapter=adapter,
            roles=roles,
            names=names,
            base_rows=base,
            challenge=challenge,
            graded=graded,
            baseline_pair=pair,
        ),
        np.asarray(bank["inputs"], float),
        snapshot,
    )


def like_for_like(sealed_pack, fresh_pack):
    """Refuse a fresh set that is not graded by the same FORMULA as the sealed one: the same hard gates, the same combination and
    value weight, and the same components (metric, transform, scale, weight) in the same legs. The leg MINIMUMS may differ (they
    are each pack's own baseline); everything that turns measurements into a total may not.
    """
    for field in ("hard_gates", "combination", "value_weight"):
        _need(
            sealed_pack.get(field) == fresh_pack.get(field),
            f"fresh_pack_differs:{field}",
        )
    for leg in ("A", "D"):
        _need(
            sealed_pack["legs"][leg]["components"]
            == fresh_pack["legs"][leg]["components"],
            f"fresh_pack_differs:legs.{leg}.components",
        )
    _need(
        sealed_pack.get("decision_policy") == fresh_pack.get("decision_policy"),
        "fresh_pack_differs:decision_policy",
    )


def role_digests(graded):
    """The sha256 of each role a set is graded with (the JSON roles canonical, the TRAIN bytes as they are)."""
    roles = graded.roles
    out = {
        name: "sha256:" + _sha(_canonical(roles[name]))
        for name in ("definition", "limits", "objective")
    }
    out["train"] = "sha256:" + _sha(roles["train"])
    return out


def same_grading_material(sealed, fresh):
    """Refuse a fresh set graded with anything but the sealed set's own accuracy definition, important limits, design objective and
    TRAIN (byte-identical), by the same adapter class and version. Only the BANK (and the pack's leg minimums) may differ.
    """
    a, b = role_digests(sealed), role_digests(fresh)
    for name in a:
        _need(a[name] == b[name], f"fresh_differs:{name}")

    def identity(graded):
        adapter = graded.adapter
        return (
            type(adapter).__module__,
            type(adapter).__qualname__,
            getattr(adapter, "VERSION", None),
            getattr(adapter, "CHALLENGE", None),
        )

    _need(identity(sealed) == identity(fresh), "fresh_differs:adapter")


def same_trained_state(sealed, fresh):
    """The fresh set's baseline must come from the SAME trained state as the sealed set's (a rebuild would add training noise to
    the gap): when either baseline is a retained inference pair, both must be, with equal recipe and state digests.
    """
    if sealed.baseline_pair is None and fresh.baseline_pair is None:
        return
    _need(
        sealed.baseline_pair is not None and fresh.baseline_pair is not None,
        "fresh_baseline_not_a_pair",
    )
    for field in ("recipe_digest", "state_digest"):
        _need(
            sealed.baseline_pair[field] == fresh.baseline_pair[field],
            f"fresh_pair_differs:{field}",
        )


def build(config, *, loader=_load_set):
    """The binding for a config. ``loader`` is replaceable so the plumbing is tested without a custody pack."""

    sealed, inputs, sealed_snapshot = loader(config["sealed"], config)
    fresh, _, fresh_snapshot = loader(config["fresh"], config)
    like_for_like(sealed.roles["score_pack"], fresh.roles["score_pack"])
    same_grading_material(sealed, fresh)
    same_trained_state(sealed, fresh)
    mu = inputs.mean(axis=0)
    sd = inputs.std(axis=0)
    sd[sd == 0] = 1.0
    scale = sealed.base_rows.std(axis=0)
    scale[scale == 0] = 1.0
    field = Field(
        dim=config["dim"],
        amplitude=config["amplitude"],
        seed=config["field_seed"],
        mu=mu,
        sd=sd,
        column_scale=scale,
    )
    binding = PoolBinding(config, {"sealed": sealed, "fresh": fresh}, field)
    binding.snapshots = {"sealed": sealed_snapshot, "fresh": fresh_snapshot}
    return binding


def make(config_path=None):
    """The factory `attack.py --binding pool_binding:make` calls. Refuses off the pinned CPU kernels, like the receiver."""
    from carbon.challenge_validator import cpu_pin

    try:
        cpu_pin.require()
    except cpu_pin.CpuPinRefused as refused:
        raise BindingRefused("cpu_pin_" + str(refused)[:60]) from refused
    path = config_path or os.environ.get(ENV_CONFIG)
    _need(path, "config_path_required")
    return build(load_config(path))


# ---------------------------------------------------------------- check and digest (aggregates only)


def check(binding):
    """theta = 0 on both sets: status and total, and (sealed) the difference from the pack's baseline total."""
    from carbon.challenge_validator import koth_registry

    zero = [0.0] * binding.dim
    out = {"schema": SCHEMA}
    for which in ("sealed", "fresh"):
        graded = binding.grade(zero, which)
        out[which] = {"status": graded["status"], "total": graded.get("total")}
    baseline = koth_registry.baseline_total(binding.sets["sealed"].roles["score_pack"])
    out["baseline_total"] = baseline
    total = out["sealed"]["total"]
    out["sealed_minus_baseline_total"] = (
        None if total is None or baseline is None else total - baseline
    )
    return out


def binding_digest(config_path, binding=None):
    """What the Validator receipts: the module, the config, the baseline-prediction files and the two packs' manifest digests."""
    config = load_config(config_path)
    document = {
        "schema": SCHEMA,
        "module_sha256": _sha(Path(__file__).read_bytes().replace(b"\r\n", b"\n")),
        "config_sha256": _sha(_canonical(config)),
        "copy_hotkey": config["copy_hotkey"],
        "catalog_recipe_digest": config["catalog_recipe_digest"],
        "baseline_predictions_sha256": {
            side: _sha(Path(config[side]["baseline_predictions"]).read_bytes())
            for side in ("sealed", "fresh")
        },
    }
    pairs = {
        side: pair_summary(config[side]["baseline_predictions"])
        for side in ("sealed", "fresh")
    }
    if any(pairs.values()):
        document["baseline_pairs"] = pairs
    if binding is not None:
        document["pack_manifest_digests"] = {
            side: binding.snapshots[side].manifest_digest
            for side in ("sealed", "fresh")
        }
        document["role_digests"] = {
            side: role_digests(binding.sets[side]) for side in ("sealed", "fresh")
        }
        document["leg_minimums"] = {
            side: {
                leg: binding.sets[side].roles["score_pack"]["legs"][leg]["minimum"]
                for leg in ("A", "D")
            }
            for side in ("sealed", "fresh")
        }
        document["score_pack_digests"] = {
            side: binding.sets[side].roles["score_pack"].get("pack_digest")
            for side in ("sealed", "fresh")
        }
    document["binding_digest"] = "sha256:" + _sha(_canonical(document))
    return document


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=("check", "digest"))
    parser.add_argument("--config", required=True)
    args = parser.parse_args(argv)
    binding = make(args.config)
    if args.command == "check":
        print(json.dumps(check(binding), sort_keys=True))
    else:
        print(json.dumps(binding_digest(args.config, binding), sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
