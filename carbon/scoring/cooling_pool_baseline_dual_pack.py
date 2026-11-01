"""Cooling 1.7: 1.6's material with the baseline's minimums graded the way miners are (COOLING_BASELINE_FAIRNESS_20261101).

Cooling 1.6's leg minimums came from `cooling_dual_pack.applied_pack`: the in-pack learned-krr-v1 baseline measured by the
sealed grid's OLD measure (untightened A, no A_gen, the sealed-grid D, only the native gates). Miners are graded by
`pool_exam.measure_pool` (A tightened by the version's a_multiplier, A_gen, the pool D, every gate), so a miner exactly as
accurate as the baseline could not reach the A minimum.

1.7 changes ONLY that. Its material (the TRAIN, the sealed cells and probes, the pools, the physics, the definition builder and
every measurement) is 1.6's. Its pack writer grades the SAME in-pack baseline (same TRAIN fit, same hyperparameters, now with
its predictions in the model's ENCODED space, as a miner's are) through `PoolVariant.measure` -> `pool_exam.measure_pool`
with the version's own a_multiplier, A_gen scales, pool targets and every gate (`InPackBaselineVariant.applied_pack`); the
baseline's A and D become the minimums, and its total the floor. The rule it implements: a Challenge's minimums are the
baseline's legs as graded by the SAME function and rows as miners, never a different metric.

A new module: 1.6's modules (and so its producer digest and every pack bound to it) are unchanged. DEVELOPMENT only: no
qualification, weight, reward or LIVE authority. The version's registration values (evaluation version, strict s_h, top-k,
balanced regions, U per region) come from the measurement and are not set here.
"""

from __future__ import annotations

import contextlib
import math
import sys
from pathlib import Path

from carbon.scoring import cooling_dual_pack as _cooling
from carbon.scoring import cooling_encoded_dual_pack as encoded
from carbon.scoring import cooling_hotspot_dual_pack as hotspot

CHALLENGE = encoded.CHALLENGE
VERSION = "1.7"
EVALUATION_VERSION = hotspot.EVALUATION_VERSION
CASE_ID = hotspot.CASE_ID
VERSIONS = {VERSION: (EVALUATION_VERSION, CASE_ID)}
#: The pool-graded evaluation version of 1.7 (a NEW version string: its minimums differ from 1.6's). Proposed.
POOL_VERSIONS = {VERSION: ("cooling-pool-sealed-v3", "cooling-sealed-pool-set")}
FILES = (*hotspot.FILES, "cooling_pool_baseline_dual_pack.py")

#: Where the minimums come from, for the pack's `leg_minimum_source` and the structural test.
MINIMUM_SOURCE = "pool_exam.measure_pool"


def definition(*, bank, train_raw, rule="baseline_legs"):
    return hotspot.definition(bank=bank, train_raw=train_raw, rule=rule)


def pool_baseline(*, bank_rows, names, sample_count):
    """``(outputs, call_seconds)``: the in-pack learned-krr-v1 baseline's answers to EVERY exam row (cells, probes and pool
    rows), in the model's encoded space, and ``sample_count`` single-design call timings.

    The fit is `cooling_dual_pack`'s (public native TRAIN, the study's length and ridge, single-threaded as 1.6's baseline
    is), so 1.6 and 1.7 share one baseline model. The answers are encoded the way a miner's are (slot 0 a raw peak excess,
    slot 31 a raw pressure) so the pool measurement decodes them as it decodes a miner's. The timings are measured: each is
    one single-row prediction of the already-fitted model."""
    import time

    import numpy as np

    from carbon import learned_baseline
    from carbon.cold_plate import domain
    from carbon.cold_plate.output_encoding import encode_targets

    train = _cooling._train_records(encoded._native_train(), names)
    native = _cooling._baseline_outputs(bank_rows, train)
    outputs = encode_targets(np.asarray(native, dtype=float)).tolist()

    import json

    spec = json.loads((_cooling._ROOT / _cooling.STUDY_CONFIG).read_bytes())["models"][
        "learned-krr-v1"
    ]
    x = learned_baseline.scale(
        [r["inputs"] for r in train], domain.INPUTS, domain.INPUT_BOUNDS
    )
    targets = []
    for row in train:
        inlet = row["inputs"]["inlet_c"]
        out = row["outputs"]
        targets.append(
            [np.log(out["peak_c"] - inlet)]
            + [np.log(v - inlet) for v in out["profile_c"]]
            + [np.log(out["pressure_drop_pa"])]
        )
    krr = learned_baseline.KernelRidge(
        x, np.asarray(targets), spec["length"], spec["ridge"]
    )
    cases = [row["inputs"] for row in bank_rows]
    step = max(1, len(cases) // sample_count)
    seconds = []
    for case in cases[::step][:sample_count]:
        scaled = learned_baseline.scale([case], domain.INPUTS, domain.INPUT_BOUNDS)
        start = time.perf_counter()
        krr.predict(scaled)
        seconds.append(max(time.perf_counter() - start, 1e-9))
    return outputs, seconds


def _pool_version():
    from carbon.scoring import pool_version

    return pool_version


#: The honesty scale used ONLY while calibrating: the per-target error e does not depend on s_h, so any positive value gives
#: the same e list. It never reaches a pack.
CALIBRATION_PLACEHOLDER_S_H = 1.0


@contextlib.contextmanager
def _recording_target_errors(errors):
    """Append every graded target's error e (in grading order) to ``errors`` while it runs; restored on exit."""
    from carbon.scoring import pool_grader

    real = pool_grader.grade_set

    def grade_set(specs, predict, optimizer, honesty):
        grade = real(specs, predict, optimizer, honesty)
        errors.extend(t.e for t in grade.targets)
        return grade

    pool_grader.grade_set = grade_set
    try:
        yield
    finally:
        pool_grader.grade_set = real


@contextlib.contextmanager
def _calibration_policies():
    """`registered_policies` of this version with an unregistered honesty scale read as the placeholder: the calibration
    build runs BEFORE s_h exists (it is derived from this very measurement). Every other constant stays the version's own
    and must be registered."""
    import json

    pv = _pool_version()
    real = pv.registered_policies

    def policies(challenge_id, version, *, path=pv.CONSTANTS):
        try:
            return real(challenge_id, version, path=path)
        except pv.PoolConstantsNotRegistered:
            document = json.loads(Path(path).read_bytes())
            entry = document["versions"][f"{challenge_id} {version}"]
            scale = entry["honesty"]["scale"]
            if scale != pv.HUMAN_INPUT:
                raise
            patched = {
                **document,
                "versions": {
                    **document["versions"],
                    f"{challenge_id} {version}": {
                        **entry,
                        "honesty": {
                            **entry["honesty"],
                            "scale": CALIBRATION_PLACEHOLDER_S_H,
                        },
                    },
                },
            }
            import tempfile

            with tempfile.TemporaryDirectory() as directory:
                alias = Path(directory) / "pool_constants.json"
                alias.write_text(json.dumps(patched))
                return real(challenge_id, version, path=alias)

    pv.registered_policies = policies
    try:
        yield
    finally:
        pv.registered_policies = real


def calibration_report(errors):
    """The ONLY thing a calibration build may output: how many targets, the digest of their error list and its median, and the
    proposed strict honesty scale (0.25 x the median, the new-version rule). Per-target values never leave custody.
    """
    import hashlib
    import json
    import statistics

    if not errors or not all(isinstance(e, float) and math.isfinite(e) for e in errors):
        raise _cooling.Refused("cooling_calibration_errors_unusable")
    median = statistics.median(errors)
    return {
        "schema": "carbon.cooling.calibration-report.v1",
        "targets": len(errors),
        "e_list_sha256": hashlib.sha256(
            json.dumps([repr(float(e)) for e in errors]).encode()
        ).hexdigest(),
        "median_e": median,
        "strict_s_h_proposal": 0.25 * median,
    }


class InPackBaselineVariant(_pool_version().PoolVariant):
    """Cooling 1.7's sealed adapter: a `PoolVariant` whose pack takes its leg minimums from the in-pack baseline graded the
    way miners are. ``bank`` (the carried bank, holding the pool material) is set by `write_sealed_pack`; only the pack's
    ``applied_pack`` differs from `PoolVariant`'s, so grading a model is the version's ordinary `measure`.
    """

    IN_PACK_BASELINE = True
    bank = None
    #: True for the calibration build: s_h is not registered yet, so the baseline's per-target e is read with a placeholder
    #: scale (e does not depend on it) and `calibration` receives the report.
    calibrating = False
    calibration = None

    def applied_pack(self, *, bank_rows, **kwargs):
        from carbon.scoring import dual_score, pool_exam

        pv = _pool_version()
        applied = super().applied_pack(bank_rows=bank_rows, **kwargs)
        if type(self.bank) is not dict or pv.POOL_KEY not in self.bank:
            raise _cooling.Refused("cooling_pool_material_missing")
        names = kwargs["names"]
        outputs, call_seconds = pool_baseline(
            bank_rows=bank_rows, names=names, sample_count=pool_exam.SPEED_SAMPLE
        )
        # The SAME function and rows as a miner's grade: PoolVariant.measure -> pool_exam.measure_pool.
        errors = []
        with (
            _recording_target_errors(errors),
            _calibration_policies() if self.calibrating else contextlib.nullcontext(),
        ):
            measured = self.measure(
                bank_rows=bank_rows,
                outputs=outputs,
                repeats=[outputs, outputs],
                definition={
                    **kwargs["definition"],
                    pv.POOL_KEY: self.bank[pv.POOL_KEY],
                },
                limits=kwargs["limits"],
                objective=kwargs["objective"],
                train_raw=kwargs["train_raw"],
                names=names,
                speed_call_seconds=call_seconds,
                speed_outputs_match=True,
            )
        if self.calibrating:
            self.calibration = calibration_report(errors)
        gates = applied["hard_gates"]
        failed = sorted(k for k in gates if not measured["gates"][k])
        if failed:
            raise _cooling.Refused("cooling_in_pack_baseline_fails:" + ",".join(failed))
        free = {
            **applied,
            "legs": {
                leg: {**body, "minimum": None} for leg, body in applied["legs"].items()
            },
        }
        provisional = "sha256:" + "0" * 64
        pack = dual_score.register_pack(
            {
                **free,
                "physics_contract_digest": provisional,
                "measurement_contract_digest": provisional,
            }
        )
        from carbon.scoring import physical_dual_pack as physical

        row = dual_score.score(
            {
                "schema": dual_score.INPUT_SCHEMA,
                "scope": free["scope"],
                "challenge": CHALLENGE,
                "physics_contract_digest": provisional,
                "measurement_contract_digest": provisional,
                "population_role": "P",
                "common_mask_digest": provisional,
                "models": [
                    {
                        "artifact_digest": provisional,
                        "gates": {k: "PASS" for k in gates},
                        "measurements": {
                            physical.METRICS[leg]: {
                                "status": "RESOLVED",
                                "value": measured[leg],
                                "unit": "1",
                            }
                            for leg in ("A", "D")
                        },
                        "decision_outcome": measured["decision_outcome"],
                    }
                ],
            },
            pack,
        )["models"][0]
        if row["status"] != "SCORED_DEVELOPMENT_CANDIDATE":
            raise _cooling.Refused("cooling_in_pack_baseline_not_scored")
        return {
            **free,
            "legs": {
                leg: {**body, "minimum": row["legs"][leg]}
                for leg, body in free["legs"].items()
            },
        }


def sealed_adapter(version):
    if type(version) is not str or version not in POOL_VERSIONS:
        return None
    evaluation, case_id = POOL_VERSIONS[version]
    pv = _pool_version()
    return InPackBaselineVariant(
        _SELF,
        version,
        evaluation,
        case_id,
        kind=pv.KINDS[CHALLENGE],
        challenge_id=CHALLENGE,
    )


def write_sealed_pack(root, bank, *, version=VERSION, **platform):
    return _write(root, bank, version=version, adapter=None, **platform)


def calibrate(root, bank, *, version=VERSION, **platform):
    """The CALIBRATION build (custody): writes the minimum-free calibration pack of ``root`` and returns ONLY the report
    (`calibration_report`): target count, the digest of the baseline's per-target e list, its median, and the strict s_h
    proposal 0.25 x median. The version's s_h is then registered with that measurement's digest, and the final build
    regrades the baseline at that s_h, whose legs become the minimums."""
    chosen = sealed_adapter(version)
    chosen.calibrating = True
    _write(root, bank, version=version, adapter=chosen, calibration=True, **platform)
    return chosen.calibration


def _write(root, bank, *, version, adapter, **platform):
    from carbon.challenge_kit import cooling_sealed_pack
    from carbon.scoring import sealed_pack_writer

    chosen = sealed_adapter(version) if adapter is None else adapter
    if chosen is not None:
        chosen.bank = bank  # the pool material the in-pack baseline is graded on
    return sealed_pack_writer.write(
        chosen,
        cooling_sealed_pack,
        root,
        bank,
        challenge=CHALLENGE,
        version=version,
        is_sealed_bank=encoded.is_pool_bank,
        refusal=encoded.Refused("cooling_bank_population"),
        pack_suffix=encoded.PACK_SUFFIX,
        **platform,
    )


def producer_digest():
    from carbon.scoring import physical_dual_pack as physical

    return physical.producer_digest(_SELF)


def adapter(rule="baseline_legs"):
    if rule != "baseline_legs":
        raise ValueError("Cooling 1.7 serves the baseline_legs rule")
    return _SELF


def pack_documents(**kwargs):
    from carbon.scoring import physical_dual_pack as physical

    return physical.pack_documents(_SELF, **kwargs)


def write_development_pack(root, **platform):
    from carbon.scoring import physical_dual_pack as physical

    return physical.write_development_pack(_SELF, root, **platform)


def produce(**kwargs):
    from carbon.scoring import physical_dual_pack as physical

    return physical.produce(_SELF, **kwargs)


def __getattr__(name):
    return getattr(hotspot, name)


_SELF = sys.modules[__name__]
