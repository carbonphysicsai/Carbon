"""F02's adapter for the shared physical dual pack and producer.

DEVELOPMENT only, exposed development bank (``physical_pack.development_bank``
for ``f02`` 2.0, Data Collection's pack ``a60298892``): never a hidden-exam or
paying claim.

The values are the Carbon Validator's registered F02 A/D packet
(F02_DUAL_PACKET_20261020), which follows
``docs/development/scorelab/four_challenge_design_fidelity_dev1.md`` (§5 f02,
§7 scales) like the other three dual packs: TOP = 0.5 A + 0.5 D, D = min(V, C)
with s_value 100 J and the margin and response components at 1 C each, an exact
paired repeat, and the gates ``finite_peak``, ``paired_repeat``,
``reference_acceptance`` and ``verified_pick`` (no F02 law is adopted, so none
gates). Each reference is a **rung envelope**: [min, max] over the three
accepted rungs, bound to the RR-04 judgement; an enclosing range, not a
probability interval. The coverage slots follow dev1 §2.3 from the references
alone. The spread is TRAIN40-v2's exact computed ``train_peak_std_c``.

A and D are the existing native cold-eight reduction
(``private_evaluation_source._f02_point_measurements``), called, never
reimplemented. A reference limitation leaves the evaluation unavailable, never
a candidate failure. The leg-minimum baseline is OWNER-LEG-MINIMUM-BEST-AGENT-01's
(KRR on TRAIN40-v2 as its placeholder), graded on the judge image in calibration
mode.
"""

from __future__ import annotations

import functools
import hashlib
import itertools
import math
import sys

from carbon.scoring import physical_dual_pack as physical

CHALLENGE = "f02"
VERSION = "2.0"
EVALUATION_VERSION = "f02-dual-development-bank-8-v1"
CASE_ID = "f02-development-bank-8"
#: Every registered Challenge version: its evaluation version and case id
#: (step-2 batch, STEP2_BATCH_VERSIONS_20261020: 2.1 serves allowlist v6 with no
#: step caps; measurement unchanged). No default version.
VERSIONS = {
    "2.0": (EVALUATION_VERSION, CASE_ID),
    "2.1": ("f02-dual-development-bank-8-v2", CASE_ID),
}
OUTPUT = {"quantity": "peak_top_c", "unit": "degC"}
FILES = ("f02_dual_pack.py",)
MINIMUM_LEGS = ("A", "D")
MANIFEST_NAME = physical.MANIFEST_NAME
bank_digest = physical.bank_digest
DEFINITION_SCHEMA = "carbon.scoring.f02-dual-definition.v1"
METHOD = "f02-cold-eight-dev1-rung-envelope"
PHYSICS_VERSION = "f02-cold-eight-summary-basis-20261020"
GATES = ("finite_peak", "paired_repeat", "reference_acceptance", "verified_pick")
RUNGS = ("primary", "mesh2", "dt0.5")
#: The bank's declared population decides how it is graded: the development
#: bank's eight registered actions, or a sealed exam batch
#: (OWNER-F02-F08-EXAM-DRAW-01; Validator, 2026-10-20: no response pairs, the
#: whole batch is the near block, and its own solver evidence is the receipt).
BANK_KINDS = {
    "REGISTERED_EIGHT_ACTION_SET_NOT_INDEPENDENT": "development",
    "SEALED_EXAM_BATCH_NEAR_LIMIT_S1": "sealed_batch",
}
SEALED_EVALUATION_VERSION = "f02-dual-sealed-batch-8-v1"
#: A sealed exam batch's evaluation version, per Challenge version.
SEALED_VERSIONS = {"2.1": SEALED_EVALUATION_VERSION}
ANALYTIC_ENERGY = "analytic:(peak_w-20)*on_time_s"
#: dev1 §7 DEVELOPMENT normalisation scales, not physical thresholds.
S_VALUE_J = 100.0
MARGIN_SCALE_C = 1.0
RESPONSE_SCALE_C = 1.0
_ADAPTER = sys.modules[__name__]
#: The leg-minimum baseline (OWNER-LEG-MINIMUM-BEST-AGENT-01): Carbon's best
#: agent-tested recipe by total on the calibration pack; until one exists, the
#: placeholder below. It is graded as a submitted recipe on the judge image
#: (``physical_dual_pack.baseline_minimums``), never rebuilt in process, and
#: never contends. A new best is a prospective recalibration.
BASELINE = {
    "decision": "OWNER-LEG-MINIMUM-BEST-AGENT-01",
    "placeholder": "kernel ridge on TRAIN40-v2",
}


class F02MeasurementRefused(ValueError):
    """The bank, definition or predictions cannot support the measurement."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


Refused = F02MeasurementRefused


def _require(ok, code):
    if not ok:
        raise F02MeasurementRefused(code)


def _limit_c():
    from carbon.challenge_kit import f02_train

    return f02_train.LIMIT_C


@functools.cache
def _judgement_sha256():
    from carbon.challenge_kit import physical_pack

    return "sha256:" + physical_pack._F02_JUDGEMENT[1]


def input_names():
    from carbon.challenge_kit import f02_public

    return list(f02_public.interface_document(CHALLENGE, VERSION)["input"]["names"])


def physics_contract():
    """F02's summary physics basis, enveloped. No F02 law is adopted
    (PHYSICS-CONTRACT-01), so it carries none; the limit is the pack's
    important-limit role, which the measurement basis pins."""
    from carbon.challenge_kit import f02_public, f02_train

    interface = f02_public.interface_document(CHALLENGE, VERSION)
    return {
        "version": PHYSICS_VERSION,
        "definition": {
            "challenge": CHALLENGE,
            "inputs": dict(
                zip(
                    interface["input"]["names"],
                    interface["input"]["units"],
                    strict=True,
                )
            ),
            "targets": dict(
                zip(
                    interface["output"]["names"],
                    interface["output"]["units"],
                    strict=True,
                )
            ),
            "context": dict(f02_train.CONTEXT),
            "extra_energy": "analytic (peak_w - 20) * on_time_s; no learned credit",
            "adopted_laws": [],
        },
    }


def bank_kind(bank):
    """``development`` or ``sealed_batch``, from the bank's own population."""
    kind = BANK_KINDS.get(bank.get("population")) if type(bank) is dict else None
    _require(kind is not None, "f02_bank_kind_unregistered")
    return kind


def receipt_of(bank, kind):
    """The reference interval's receipt: RR-04's judgement for the development
    bank, the sealed batch's own family evidence for a sealed bank."""
    if kind == "development":
        return _judgement_sha256()
    evidence = bank.get("solver_evidence")
    _require(type(evidence) is bytes and evidence, "f02_sealed_evidence_unavailable")
    return "sha256:" + hashlib.sha256(evidence).hexdigest()


def _schedules(bank_rows):
    return {
        row["case_id"]: (
            row["record"]["action"]["peak_w"],
            row["record"]["action"]["on_time_s"],
        )
        for row in bank_rows
    }


def _ids(bank_rows):
    ids = [row["case_id"] for row in bank_rows]
    _require(ids == sorted(ids) and len(ids) == 8, "f02_bank_order")
    return ids


def reference(bank_rows, receipt):
    """The rich reference over the bank: each action's peak and margin as a
    rung envelope bound to ``receipt`` (``receipt_of``), and its analytic
    objective."""
    limit = _limit_c()
    cases, actions = {}, {}
    for row in bank_rows:
        record = row["record"]
        rungs = record.get("rung_peaks_c", {})
        _require(
            record.get("status") == "OK"
            and set(rungs) == set(RUNGS)
            and all(type(v) is float and math.isfinite(v) for v in rungs.values())
            and record.get("convergence", {}).get("pass") is True,
            "f02_reference_record",
        )
        peak, low, high = rungs["primary"], min(rungs.values()), max(rungs.values())
        _require(len({v <= limit for v in rungs.values()}) == 1, "f02_reference_side")
        action = record["action"]
        cases[row["case_id"]] = {
            "peak_top_c": {
                "status": "RESOLVED",
                "value": peak,
                "unit": "C",
                "interval": {
                    "lower": low,
                    "upper": high,
                    "unit": "C",
                    "receipt": receipt,
                },
            },
            "thermal_margin_c": {
                "status": "RESOLVED",
                "value": limit - peak,
                "unit": "C",
                "interval": {
                    "lower": limit - high,
                    "upper": limit - low,
                    "unit": "C",
                    "receipt": receipt,
                },
            },
        }
        energy = (action["peak_w"] - 20) * action["on_time_s"]
        actions[row["case_id"]] = {
            "feasibility": "FEASIBLE" if peak <= limit else "INFEASIBLE",
            # Analytic and exact: its accepted interval is the point itself.
            "objective": {
                "status": "RESOLVED",
                "value": energy,
                "unit": "J",
                "interval": {
                    "lower": energy,
                    "upper": energy,
                    "unit": "J",
                    "receipt": ANALYTIC_ENERGY,
                },
            },
        }
    return {"cases": cases, "actions": actions}


def coverage_cases(bank_rows):
    """dev1 §2.3: the closest resolved nonnegative and negative thermal margins,
    from references only (stable id tie break)."""
    limit = _limit_c()
    margins = {
        row["case_id"]: limit - row["record"]["rung_peaks_c"]["primary"]
        for row in bank_rows
    }
    sides = {}
    for side, keep in (
        ("nonnegative", lambda m: m >= 0),
        ("negative", lambda m: m < 0),
    ):
        pool = sorted((abs(m), k) for k, m in margins.items() if keep(m))
        _require(pool, "f02_coverage_side_missing")
        sides[side] = pool[0][1]
    return sides


def policy(bank_rows, kind):
    """The registered Design policy (dev1 §5 f02, §7 scales). A sealed batch
    registers no response pairs (margin and decision only)."""
    ids = _ids(bank_rows)
    near = [f"cool-rect-near-{power}w" for power in (84, 85, 86, 87)]
    _require(kind in BANK_KINDS.values(), "f02_bank_kind_unregistered")
    sides = coverage_cases(bank_rows)
    return {
        "id": "f02-cold-eight-dev1-v1",
        "case_ids": ids,
        "action_ids": ids,
        "quantities": {
            "peak_top_c": {"unit": "C", "learned": True},
            "thermal_margin_c": {"unit": "C", "learned": True},
            "extra_energy_j": {"unit": "J", "learned": False},
        },
        "objective": {
            "quantity": "extra_energy_j",
            "unit": "J",
            "direction": "MAXIMIZE",
            "scale": {"value": S_VALUE_J, "unit": "J"},
            "learned": False,
            # Analytic energy: no equivalence width is invented.
            "equivalence": {"value": 0.0, "unit": "J"},
        },
        "components": [
            {
                "id": "margin",
                "kind": "margin",
                "quantity": "thermal_margin_c",
                "unit": "C",
                "scale": {"value": MARGIN_SCALE_C, "unit": "C"},
                "cases": ids,
                "pairs": [],
            },
            *(
                []
                if kind == "sealed_batch"
                else [
                    {
                        "id": "response",
                        "kind": "response",
                        "quantity": "peak_top_c",
                        "unit": "C",
                        "scale": {"value": RESPONSE_SCALE_C, "unit": "C"},
                        "cases": [],
                        "pairs": [list(pair) for pair in itertools.pairwise(near)],
                    }
                ]
            ),
        ],
        "coverage_slots": [
            {
                "id": "margin-" + side,
                "component": "margin",
                "case_id": case,
                "side": side,
                "max_distance": {"value": MARGIN_SCALE_C, "unit": "C"},
                "structural_na_receipt": None,
            }
            for side, case in sides.items()
        ],
    }


def definition(*, bank, train_raw):
    """F02's registered accuracy definition fields (the shared module adds the
    producer, TRAIN and bank pins)."""
    from carbon.challenge_kit import f02_train

    rows = physical.bank_rows(bank, input_names())
    kind = bank_kind(bank)
    return {
        "schema": DEFINITION_SCHEMA,
        "method": METHOD,
        "bank_kind": kind,
        "train_peak_std_c": f02_train.load_public_train(VERSION)["train_peak_std_c"],
        "maximum_c": _limit_c(),
        "policy": policy(rows, kind),
        "reference_interval": {
            "kind": "rung_envelope",
            "rungs": list(RUNGS),
            "receipt": receipt_of(bank, kind),
        },
        "paired_repeat_procedure": "per_case",
        "paired_repeat": {
            "procedure": "per_case",
            "tolerance_ulp": 0,
            "floor": 0,
            "placement": "across_runs_same_position",
        },
    }


def validate_definition(definition):
    from carbon.challenge_kit import f02_train

    _require(
        type(definition) is dict
        and definition.get("schema") == DEFINITION_SCHEMA
        and definition.get("method") == METHOD
        and definition.get("train_peak_std_c")
        == f02_train.load_public_train(VERSION)["train_peak_std_c"]
        and definition.get("maximum_c") == _limit_c()
        and type(definition.get("policy")) is dict
        and definition.get("bank_kind") in BANK_KINDS.values()
        and type(definition.get("reference_interval")) is dict
        and set(definition["reference_interval"]) == {"kind", "rungs", "receipt"}
        and definition["reference_interval"]["kind"] == "rung_envelope"
        and definition["reference_interval"]["rungs"] == list(RUNGS)
        and (
            definition["reference_interval"]["receipt"] == _judgement_sha256()
            if definition.get("bank_kind") == "development"
            else type(definition["reference_interval"]["receipt"]) is str
            and len(definition["reference_interval"]["receipt"]) == 71
            and definition["reference_interval"]["receipt"].startswith("sha256:")
        )
        and definition.get("paired_repeat")
        == {
            "procedure": "per_case",
            "tolerance_ulp": 0,
            "floor": 0,
            "placement": "across_runs_same_position",
        },
        "f02_definition",
    )
    validate_policy(definition["policy"])


def validate_policy(policy):
    """The Design policy as design_fidelity registers it, and every case a
    component names is a case of the bank (a pair naming an absent case
    would otherwise pass silently and leave its component empty)."""
    from carbon.scoring import design_fidelity

    try:
        design_fidelity.validate_policy(policy)
    except design_fidelity.ReductionRefused as exc:
        raise F02MeasurementRefused("f02_policy_invalid") from exc
    cases = set(policy["case_ids"])
    for component in policy["components"]:
        named = set(component["cases"]) | {
            c for pair in component["pairs"] for c in pair
        }
        _require(named <= cases, "f02_policy_case_absent")


def applied_pack(**_):
    """The packet's dual pack: 0.5 A + 0.5 D and the four native gates."""
    from carbon.scoring import dual_score

    return {
        "schema": dual_score.PACK_SCHEMA,
        "scope": "PUBLIC_DEVELOPMENT",
        "challenge": CHALLENGE,
        "hard_gates": list(GATES),
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


def baseline_outputs(cases):
    """The baseline is graded as a submitted recipe on the judge image, not
    rebuilt here: refuse, never substitute."""
    raise Refused("f02_baseline_graded_not_rebuilt")


def measure(
    *, bank_rows, outputs, repeats, definition, limits, objective, train_raw, names
):
    """A, D and the four gates for one model's predictions on the bank."""
    from carbon.scoring import private_evaluation_source as source

    validate_definition(definition)
    kind = definition["bank_kind"]
    _require(policy(bank_rows, kind) == definition["policy"], "f02_policy_binding")
    _require(all(len(row) == 1 for row in outputs), "f02_output_width")
    values = [row[0] for row in outputs]
    repeated = len(repeats) == 2 and all(r == outputs for r in repeats)
    truth = reference(bank_rows, definition["reference_interval"]["receipt"])
    if not all(type(v) in (int, float) and math.isfinite(v) for v in values):
        # A nonfinite peak is the candidate's own gate failure.
        return {
            "A": None,
            "D": None,
            "gates": {
                "finite_peak": False,
                "paired_repeat": repeated,
                "reference_acceptance": True,
                "verified_pick": False,
            },
            "decision_outcome": "MISSED_OPPORTUNITY",
            "selected_action": None,
            "reduction": None,
        }
    native = source._f02_point_measurements(
        values,
        truth,
        definition["policy"],
        definition["train_peak_std_c"],
        definition["maximum_c"],
        schedules=_schedules(bank_rows) if kind == "sealed_batch" else None,
    )
    reduction = native["reduction"]
    # A reference limitation is never a candidate verdict.
    _require(
        not reduction["reference_limitations"],
        "f02_reference_limited:" + ",".join(reduction["reference_limitations"]),
    )
    verified = reduction["candidate_selection_outcome"] == "VERIFIED_FEASIBLE"
    outcome = "VERIFIED_FEASIBLE" if verified else "MISSED_OPPORTUNITY"
    if all(a["feasibility"] == "INFEASIBLE" for a in truth["actions"].values()):
        outcome = "NONE_FEASIBLE"
    return {
        "A": native["A"],
        "D": reduction["registered_D"],
        "gates": {
            "finite_peak": True,
            "paired_repeat": repeated,
            # The bank holds only B10-accepted rung-compared references.
            "reference_acceptance": True,
            "verified_pick": verified,
        },
        "decision_outcome": outcome,
        "selected_action": native["model"]["selected_action"],
        "reduction": reduction,
    }


def sealed_adapter(version):
    """This adapter for a sealed exam batch of Challenge ``version``: its own
    evaluation version (``SEALED_EVALUATION_VERSION``); grading reads the
    bank kind from the definition, so measurement is this module's. None for
    an unregistered version (no default)."""
    if type(version) is not str or version not in SEALED_VERSIONS:
        return None
    return physical.Variant(_ADAPTER, version, SEALED_VERSIONS[version], CASE_ID)


def producer_digest():
    return physical.producer_digest(_ADAPTER)


def pack_documents(**kwargs):
    return physical.pack_documents(_ADAPTER, **kwargs)


def write_development_pack(root, **platform):
    return physical.write_development_pack(_ADAPTER, root, **platform)


def produce(**kwargs):
    return physical.produce(_ADAPTER, **kwargs)


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(
        description="Write the complete F02 DEVELOPMENT evaluation pack."
    )
    physical.add_builder_arguments(parser)
    args = parser.parse_args(argv)
    print(write_development_pack(args.root.resolve(), **physical.builder_options(args)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
