"""Motor 1.6: 1.5's material with a new scoring (pick rule, region weighting, honesty scale) and the baseline's minimums
graded the way miners are (the Cooling 1.7 rule: a Challenge's minimums are the baseline's legs as graded by the SAME function and rows as miners).

Motor 1.5's leg minimums came from a retained baseline run graded under a calibration pack (`physical.baseline_minimums`). 1.6's
pack writer grades the registered learned-krr-v1 baseline (kernel ridge, length 4, ridge 1e-4, fitted on public TRAIN, one BLAS thread)
through `PoolVariant.measure` -> `pool_exam.measure_pool` over EVERY exam row (cells, probes and pool rows), with the version's own
a_multiplier, A_gen scales, pool targets and every gate (`InPackBaselineVariant.applied_pack`); the baseline's A and D become the leg
minimums. The pack may also carry ``baseline_floor_total`` (OWNER-EXAM-VALUE-PICKS-01, option B): the crown floor, a measured
number passed in by the writer (never typed here), refused below the minimums-derived total (`dual_score.register_pack`).

Same TRAIN, interface, physics, sealed cells and probes as 1.5; the definition binds the host registration digest of the version's
overlay entry (`version_overlay`). A new module: 1.5's pack is graded by 1.5's modules. DEVELOPMENT only: no qualification, weight,
reward or LIVE authority. The registration values (strict s_h, the extended-region U) come from measurement and are not set here.
"""

from __future__ import annotations

import contextlib
import math
import sys
from pathlib import Path

from carbon.scoring import motor_sealed_dual_pack as _sealed

CHALLENGE = _sealed.CHALLENGE
#: The definition field that binds the version's host registration digest.
REGISTRATION_KEY = "version_registration_digest"
VERSION = "1.6"
EVALUATION_VERSION = "motor-pool-sealed-v2"
CASE_ID = "motor-sealed-pool-set"
#: The pool-graded evaluation version of 1.6 (a NEW key: its scoring and minimums differ from 1.5's).
POOL_VERSIONS = {VERSION: (EVALUATION_VERSION, CASE_ID)}
VERSIONS = dict(POOL_VERSIONS)
#: 1.6's OWN producer identity covers the sealed grader and this module; 1.1-1.5 do not name this file.
FILES = (*_sealed.FILES, "motor_pool_baseline_dual_pack.py")

#: Where the minimums come from, for the pack's `leg_minimum_source` and the structural test.
MINIMUM_SOURCE = "pool_exam.measure_pool"
#: The honesty scale used ONLY while calibrating: the per-target error e does not depend on s_h, so any positive value gives
#: the same e list. It never reaches a pack.
CALIBRATION_PLACEHOLDER_S_H = 1.0
Refused = _sealed.Refused


def pool_baseline(*, bank_rows, sample_count):
    """``(outputs, call_seconds)``: the registered baseline's answers to EVERY exam row (cells, probes and pool rows), as
    Motor's torque curves, and ``sample_count`` single-design call timings. Fitted on public TRAIN with one BLAS thread.
    """
    from carbon.scoring import physical_dual_pack as physical

    cases = [row["inputs"] for row in bank_rows]
    done = physical.single_threaded(
        "carbon.scoring.motor_pool_baseline_dual_pack:_baseline_timed",
        cases=cases,
        sample_count=sample_count,
    )
    return done["outputs"], done["seconds"]


def _baseline_timed(*, cases, sample_count):
    """Runs in the single-threaded child: the baseline of ``cases``, and one single-row prediction time for each of
    ``sample_count`` evenly spaced cases."""
    import time

    from carbon.motor import recipes
    from carbon.motor.challenge import PublicMaterial
    from carbon.scoring import motor_dual_pack

    spec = motor_dual_pack.BASELINE
    model = recipes.build(
        spec["model"],
        {"length": spec["length"], "ridge": spec["ridge"]},
        PublicMaterial.load(Path(__file__).resolve().parents[2]).train,
    )
    outputs = [[float(v) for v in model.predict(c)["torque_nm"]] for c in cases]
    step = max(1, len(cases) // sample_count)
    seconds = []
    for case in cases[::step][:sample_count]:
        start = time.perf_counter()
        model.predict(case)
        seconds.append(max(time.perf_counter() - start, 1e-9))
    return {"outputs": outputs, "seconds": seconds}


def _pool_version():
    from carbon.scoring import pool_version

    return pool_version


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
    """`registered_policies` with an unregistered honesty scale read as the placeholder: the calibration build runs BEFORE
    s_h exists (it is derived from this very measurement). Every other constant stays the version's own and must be registered.
    """
    import json
    import tempfile

    pv = _pool_version()
    real = pv.registered_policies

    def policies(challenge_id, version, *, path=pv.CONSTANTS):
        try:
            return real(challenge_id, version, path=path)
        except pv.PoolConstantsNotRegistered:
            document = json.loads(Path(path).read_bytes())
            entry = document["versions"][f"{challenge_id} {version}"]
            if entry["honesty"]["scale"] != pv.HUMAN_INPUT:
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
        raise Refused("motor_calibration_errors_unusable")
    median = statistics.median(errors)
    return {
        "schema": "carbon.motor.calibration-report.v1",
        "targets": len(errors),
        "e_list_sha256": hashlib.sha256(
            json.dumps([repr(float(e)) for e in errors]).encode()
        ).hexdigest(),
        "median_e": median,
        "strict_s_h_proposal": 0.25 * median,
    }


class InPackBaselineVariant(_pool_version().PoolVariant):
    """Motor 1.6's sealed adapter: a `PoolVariant` whose pack takes its leg minimums from the in-pack baseline graded the way
    miners are. ``bank`` (the carried bank, holding the pool material) is set by `write_sealed_pack`; only the pack's
    ``applied_pack`` differs from `PoolVariant`'s, so grading a model is the version's ordinary `measure`.
    """

    IN_PACK_BASELINE = True
    bank = None
    #: True for the calibration build: s_h is not registered yet (see `_calibration_policies`).
    calibrating = False
    calibration = None
    #: The crown floor (option B), a MEASURED number set by the writer; None leaves the pack exactly as without one.
    baseline_floor_total = None

    def definition(self, *, bank, train_raw):
        """The version's definition plus its host registration digest (`version_overlay`): the definition is hashed into
        the measurement contract, so a changed registration entry is another pack identity.
        """
        return {
            **super().definition(bank=bank, train_raw=train_raw),
            REGISTRATION_KEY: self._registration_digest(),
        }

    def validate_definition(self, definition):
        if definition.get(REGISTRATION_KEY) != self._registration_digest():
            raise Refused("motor_registration_digest")
        return super().validate_definition(
            {k: v for k, v in definition.items() if k != REGISTRATION_KEY}
        )

    def _registration_digest(self):
        from carbon.challenge_kit import version_overlay

        return version_overlay.entry_digest(CHALLENGE, self.VERSION)

    def applied_pack(self, *, bank_rows, **kwargs):
        from carbon.scoring import dual_score, pool_exam

        pv = _pool_version()
        applied = super().applied_pack(bank_rows=bank_rows, **kwargs)
        if type(self.bank) is not dict or pv.POOL_KEY not in self.bank:
            raise Refused("motor_pool_material_missing")
        names = kwargs["names"]
        outputs, call_seconds = pool_baseline(
            bank_rows=bank_rows, sample_count=pool_exam.SPEED_SAMPLE
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
            raise Refused("motor_in_pack_baseline_fails:" + ",".join(failed))
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
            raise Refused("motor_in_pack_baseline_not_scored")
        out = {
            **free,
            "legs": {
                leg: {**body, "minimum": row["legs"][leg]}
                for leg, body in free["legs"].items()
            },
        }
        if self.baseline_floor_total is not None and not self.calibrating:
            out["baseline_floor_total"] = self.baseline_floor_total
        return out


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


def write_sealed_pack(
    root, bank, *, version=VERSION, baseline_floor_total=None, **platform
):
    """The final build: the baseline's legs graded as miners are become the minimums; ``baseline_floor_total`` (a measured
    number, or None) is the crown floor."""
    return _write(
        root,
        bank,
        version=version,
        adapter=None,
        baseline_floor_total=baseline_floor_total,
        **platform,
    )


def calibrate(root, bank, *, version=VERSION, **platform):
    """The CALIBRATION build (custody): writes the minimum-free calibration pack of ``root`` and returns ONLY the report
    (`calibration_report`): target count, the digest of the baseline's per-target e list, its median, and the strict s_h
    proposal 0.25 x median. The version's s_h is then registered with that measurement's digest, and the final build
    regrades the baseline at that s_h, whose legs become the minimums."""
    chosen = sealed_adapter(version)
    chosen.calibrating = True
    _write(root, bank, version=version, adapter=chosen, calibration=True, **platform)
    return chosen.calibration


def _write(root, bank, *, version, adapter, baseline_floor_total=None, **platform):
    from carbon.challenge_kit import motor_sealed_pack
    from carbon.scoring import sealed_pack_writer

    chosen = sealed_adapter(version) if adapter is None else adapter
    if chosen is not None:
        chosen.bank = bank  # the pool material the in-pack baseline is graded on
        chosen.baseline_floor_total = baseline_floor_total
        if platform.get("calibration"):
            chosen.calibrating = True  # s_h is derived from this very measurement
    return sealed_pack_writer.write(
        chosen,
        motor_sealed_pack,
        root,
        bank,
        challenge=CHALLENGE,
        version=version,
        is_sealed_bank=_sealed.is_pool_bank,
        refusal=Refused("motor_bank_population"),
        pack_suffix=_sealed.PACK_SUFFIX,
        **platform,
    )


def producer_digest():
    from carbon.scoring import physical_dual_pack as physical

    return physical.producer_digest(_SELF)


def pack_documents(**kwargs):
    from carbon.scoring import physical_dual_pack as physical

    return physical.pack_documents(_SELF, **kwargs)


def produce(**kwargs):
    from carbon.scoring import physical_dual_pack as physical

    return physical.produce(_SELF, **kwargs)


def __getattr__(name):
    return getattr(_sealed, name)


_SELF = sys.modules[__name__]
