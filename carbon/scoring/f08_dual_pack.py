"""F08's adapter for the shared physical dual pack and producer.

DEVELOPMENT only, exposed accepted-reference bank (eight TRAIN-informed
near-feasible geometries, Validator-reviewed 2026-10-19): never a hidden-exam
or paying claim. Ported from the summary dual F08 packet
(OPTIMIZER_F08_SUMMARY_DUAL_PACKET_20261018, sha256 4e07322f...) and
regenerated from committed sources; no operator output is copied.

- The physics contract is the packet's summary physics basis (targets,
  damping set, frequency band, objective; its limits are the pack's
  important-limit role) in the ``{version, definition}`` envelope.
- The accuracy definition carries the packet's measurement (``D_scale`` 0.01
  mm/N, the 80-600 Hz band, exact-equality paired repeat) with the repeat as
  the identical per-case procedure (Validator, 2026-10-19).
- Leg minimums follow the common rule (the registered baseline's A and D,
  ``krr_length2_ridge1e-4``); the packet's own no-D-minimum rule is the
  separately versioned DEVELOPMENT variant. Both are reported; adoption is
  the owner's.
- Each Challenge version has its own evaluation version (its own bank key):
  1.0, the accepted bank, where every reference is feasible so D tests ranking
  only (``RANKING_ONLY_NO_FEASIBILITY_BOUNDARY``); and 1.1, the near-limit
  ladder, which straddles the dynamic limit (4 safe / 4 unsafe,
  ``RANKING_AND_FEASIBILITY_STRADDLE``), so an infeasible pick is seen: it is
  not verified, fails ``verified_pick_feasible`` and scores D = 0. The same
  measurement serves both; feasibility comes from each reference.
"""

from __future__ import annotations

import io
import sys

from carbon.scoring import f08_dual_measurement as fdm
from carbon.scoring import physical_dual_pack as physical

CHALLENGE = "f08-ribbed-bracket"
VERSION = "1.0"
CASE_ID = "f08-accepted-bank-8"
EVALUATION_VERSION = "f08-dual-accepted-bank-8-v1"
OUTPUT = {
    "quantity": "f08_summary[static_tip,3x(peak_tip,peak_frequency)]",
    "unit": "mm/N,Hz",
}
FILES = ("f08_dual_pack.py", "f08_dual_measurement.py")
MINIMUM_LEGS = ("A", "D")
Refused = fdm.F08MeasurementRefused
validate_definition = fdm.validate_definition
_ADAPTER = sys.modules[__name__]
#: The packet this adapter ports, committed byte-identical as data:
#: carbon/challenge_kit/data/optimizer-f08-summary-dual-packet-20261018.py.txt
#: (never imported or executed; a test checks the values below).
SOURCE_SCRIPT_SHA256 = (
    "sha256:4e07322fb21541ad4b2feb47935862ca43937f048c552f7514e68bc3054d1bfa"
)
PHYSICS_VERSION = "f08-summary-dual-physics-binding-20261018"
#: The packet's measurement values, verbatim: D = 1/(1+regret/D_scale);
#: the 80-600 Hz tip-peak band; exact-equality paired repeat; its baseline.
_MEASUREMENT = {
    "D_scale_mm_per_n": 0.01,
    "frequency_band_hz": [80, 600],
    "paired_repeat_rule": "exact_equality",
    "baseline": {"model": "kernel_ridge", "length": 2.0, "ridge": 1e-4},
}
_TIPS = ("peak_tip_z005_mm_per_n", "peak_tip_z010_mm_per_n", "peak_tip_z020_mm_per_n")
_FREQUENCIES = (
    "peak_frequency_z005_hz",
    "peak_frequency_z010_hz",
    "peak_frequency_z020_hz",
)
#: Per Challenge version: its evaluation version and its bank's case id.
VERSIONS = {
    "1.0": (EVALUATION_VERSION, CASE_ID),
    "1.1": ("f08-dual-near-limit-bank-8-v1", "f08-near-limit-bank-8"),
}
LEG_MINIMUM_RULES = {
    "baseline_legs": (
        "",
        ("The common rule: the registered baseline's A and D are the leg " "minimums."),
    ),
    "baseline_a_no_d_minimum": (
        "-no-d-minimum",
        (
            "The packet's rule, a DEVELOPMENT comparison variant: the baseline's "
            "A is the A minimum and D has no minimum (never copy a perfect "
            "baseline D into an eligibility cutoff). Not adopted."
        ),
    ),
}


def input_names(version=VERSION):
    from carbon.challenge_kit import f08_public

    return list(f08_public.interface_document(CHALLENGE, version)["input"]["names"])


def _targets(version=VERSION):
    from carbon.challenge_kit import f08_public

    return list(f08_public.interface_document(CHALLENGE, version)["output"]["names"])


def physics_contract():
    """The packet's summary physics basis, enveloped. Its limits are the pack's
    important-limit role, which the measurement basis pins, so this contract
    does not repeat them (and reads no pack role)."""
    return {
        "version": PHYSICS_VERSION,
        "definition": {
            "challenge": CHALLENGE,
            "input_units": "mm",
            "targets": _targets(),
            "mass": "analytic CAD mass; feasibility only, not a learned target",
            "zetas": ["zeta_0.005", "zeta_0.01", "zeta_0.02"],
            "band_hz": _MEASUREMENT["frequency_band_hz"],
            "objective": "min worst TIP peak, probe diagnostic only",
        },
    }


def definition(*, bank, train_raw, rule="baseline_legs", version=VERSION):
    """F08's registered accuracy definition fields (the shared module adds the
    producer, TRAIN, bank and platform pins)."""
    return {
        "schema": fdm.DEFINITION_SCHEMA,
        "method": fdm.METHOD,
        "source_script_sha256": SOURCE_SCRIPT_SHA256,
        "targets": _targets(version),
        "tip_targets": list(_TIPS),
        "frequency_targets": list(_FREQUENCIES),
        "static_target": "static_tip_mm_per_n",
        "A_reducer": "minimum",
        "geometry_count": len(bank["case_ids"]),
        "decision_coverage": bank.get("decision_coverage"),
        "leg_minimum_rule": rule,
        "leg_minimum_note": LEG_MINIMUM_RULES[rule][1],
        "paired_repeat_procedure": "per_case",
        **_MEASUREMENT,
    }


def _train_targets(train_raw):
    import numpy as np

    with np.load(io.BytesIO(train_raw), allow_pickle=False) as data:
        return [[float(v) for v in row] for row in np.asarray(data["targets"])]


def measure(
    *, bank_rows, outputs, repeats, definition, limits, objective, train_raw, names
):
    return fdm.measure(
        bank=bank_rows,
        outputs=outputs,
        repeats=repeats,
        definition=definition,
        limits=limits,
        train=_train_targets(train_raw),
    )


def _baseline_outputs(bank_rows, train_raw, names):
    """The packet's registered baseline (KRR, length 2, ridge 1e-4) rebuilt
    from public TRAIN, on the bank, with its linear algebra pinned to one
    thread."""
    import base64

    return physical.single_threaded(
        "carbon.scoring.f08_dual_pack:_baseline_here",
        cases=[row["inputs"] for row in bank_rows],
        train_b64=base64.b64encode(train_raw).decode("ascii"),
        names=list(names),
    )


def _baseline_here(*, cases, train_b64, names):
    import base64

    import numpy as np

    from carbon import learned_baseline
    from carbon.challenge_kit import f08_train
    from carbon.challenge_pipeline import structures_readiness

    # The registered geometry bounds (the packet's BOUNDS, the same values).
    bounds = dict(zip(f08_train.FIELDS, structures_readiness.BOUNDS, strict=True))
    train_raw = base64.b64decode(train_b64)
    with np.load(io.BytesIO(train_raw), allow_pickle=False) as data:
        inputs = np.asarray(data["inputs"], dtype=float)
        targets = np.asarray(data["targets"], dtype=float)
    train_rows = [dict(zip(names, row, strict=True)) for row in inputs]
    spec = _MEASUREMENT["baseline"]
    model = learned_baseline.KernelRidge(
        learned_baseline.scale(train_rows, names, bounds),
        targets,
        spec["length"],
        spec["ridge"],
    )
    predicted = model.predict(learned_baseline.scale(cases, names, bounds))
    return [[float(v) for v in row] for row in predicted]


def applied_pack(*, bank_rows, definition, limits, objective, train_raw, names):
    """The packet's dual pack; leg minimums follow the definition's rule from
    the rebuilt baseline when it scores as a development candidate."""
    from carbon.scoring import dual_score

    body = {
        "schema": dual_score.PACK_SCHEMA,
        "scope": "PUBLIC_DEVELOPMENT",
        "challenge": CHALLENGE,
        "hard_gates": list(fdm.GATES),
        "legs": {
            leg: {
                "components": [
                    {
                        "metric": physical.METRICS[leg],
                        "unit": "1",
                        "transform": "unit_benefit",
                        "scale": None,
                        "weight": 1.0,
                    }
                ],
                "minimum": None,
            }
            for leg in ("A", "D")
        },
        "value_weight": 0.5,
        "combination": "weighted_arithmetic_mean",
        "decision_policy": {
            "VERIFIED_FEASIBLE": {"eligible": True, "maximum_D": 1.0},
            "MISSED_OPPORTUNITY": {"eligible": False, "maximum_D": 0.0},
            "NONE_FEASIBLE": {"eligible": False, "maximum_D": 0.0},
        },
    }
    baseline = _baseline_outputs(bank_rows, train_raw, names)
    measured = measure(
        bank_rows=bank_rows,
        outputs=baseline,
        repeats=[baseline, baseline],
        definition=definition,
        limits=limits,
        objective=objective,
        train_raw=train_raw,
        names=names,
    )
    rule = definition.get("leg_minimum_rule")
    if rule not in LEG_MINIMUM_RULES:
        raise Refused("f08_leg_minimum_rule")
    scorable = (
        all(measured["gates"].values())
        and measured["decision_outcome"] == "VERIFIED_FEASIBLE"
        and measured["A"] is not None
    )
    if scorable:
        for leg in ("A", "D") if rule == "baseline_legs" else ("A",):
            body["legs"][leg]["minimum"] = measured[leg]
    return body


class _Variant:
    """This adapter for another Challenge version or leg-minimum rule: its own
    evaluation version, case id and definition; everything else (measurement,
    producer files) is the default adapter's."""

    def __init__(self, rule, version):
        self.rule = rule
        self.VERSION = version
        evaluation_version, self.CASE_ID = VERSIONS[version]
        self.EVALUATION_VERSION = evaluation_version + LEG_MINIMUM_RULES[rule][0]
        self.MINIMUM_LEGS = ("A", "D") if rule == "baseline_legs" else ("A",)
        # The calibration run is graded under the default rule's calibration
        # pack for the same Challenge version; its legs serve every rule.
        self.CALIBRATION_ADAPTER = (
            self if rule == "baseline_legs" else adapter(version=version)
        )

    def definition(self, **kwargs):
        return definition(**kwargs, rule=self.rule, version=self.VERSION)

    def input_names(self):
        return input_names(self.VERSION)

    # This variant's own entry points, so its version and rule are never lost
    # to the module-level (1.0, default-rule) functions.
    def pack_documents(self, **kwargs):
        return physical.pack_documents(self, **kwargs)

    def write_development_pack(self, root, **platform):
        return physical.write_development_pack(self, root, **platform)

    def produce(self, **kwargs):
        return physical.produce(self, **kwargs)

    def __getattr__(self, name):
        return getattr(_ADAPTER, name)


def adapter(rule="baseline_legs", version=VERSION):
    if rule not in LEG_MINIMUM_RULES or version not in VERSIONS:
        raise ValueError("unknown F08 leg-minimum rule or Challenge version")
    if rule == "baseline_legs" and version == VERSION:
        return _ADAPTER
    return _Variant(rule, version)


def producer_digest():
    return physical.producer_digest(_ADAPTER)


def pack_documents(*, rule="baseline_legs", version=VERSION, **kwargs):
    return physical.pack_documents(adapter(rule, version), **kwargs)


def write_development_pack(root, rule="baseline_legs", version=VERSION, **platform):
    return physical.write_development_pack(adapter(rule, version), root, **platform)


def produce(version=VERSION, **kwargs):
    return physical.produce(adapter(version=version), **kwargs)


def main(argv=None):
    import argparse
    from pathlib import Path

    parser = argparse.ArgumentParser(
        description="Write the complete F08 DEVELOPMENT evaluation pack."
    )
    physical.add_builder_arguments(parser)
    parser.add_argument(
        "--leg-minimum-rule", choices=sorted(LEG_MINIMUM_RULES), default="baseline_legs"
    )
    parser.add_argument(
        "--challenge-version", choices=sorted(VERSIONS), default=VERSION
    )
    args = parser.parse_args(argv)
    print(
        write_development_pack(
            Path(args.root).resolve(),
            args.leg_minimum_rule,
            args.challenge_version,
            **physical.builder_options(args),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
