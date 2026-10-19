"""Motor's dual evaluation pack documents and its private dual producer.

DEVELOPMENT only, exposed development bank (``physical_pack.development_bank``,
committed repository material): never a hidden-exam or paying claim.

Two halves, one source:

- ``pack_documents`` regenerates, from committed sources only, the documents
  Data Collection's pack pins for Motor: the public ``physics_contract`` (the
  committed applied physics document in the ``{version, definition}``
  envelope) and ``accuracy_definition`` (the producer's registered A/D
  definition and pin), and the private
  ``reference_rows``, ``solver_evidence``, ``score_pack`` and
  ``source_registration``. The score pack is the committed applied definition
  (MOTOR_APPLIED_SCORE_DEFINITION_20261018, sha256 b4ea72a5..., candidate
  ``base__A1__arithmetic__wd0p5::G1_BALANCED_BASELINE``) with its legs, gates,
  minima, weight and decision policy unchanged, bound to this producer's
  measurement basis. It is a new evaluation version; its results are not
  compared with the historical replay. No value is chosen here.
- ``produce`` reads one retained model's authenticated bank predictions and two
  fresh repeats, measures A and D (``motor_dual_measurement``) and returns the
  dual benchmark input for the shared ScoreEngine.
"""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path

CHALLENGE = "electric-motor-magnetics"
VERSION = "1.0"
#: The committed applied definition this pack reproduces (see module docstring).
SOURCE_DEFINITION_SHA256 = (
    "sha256:b4ea72a5cc251b9315705912c42d061971a31c07b6cc15a0365dd9a042d48a3c"
)
#: The historical G1 gate-policy measurement contract (the definition's identity
#: preimage); kept as lineage, not as this pack's measurement basis.
G1_MEASUREMENT_CONTRACT_SHA256 = (
    "sha256:8f374907064891b5a5d261d9d31d8c4159c69577e44daa6234ed83c79bd3f782"
)
#: MOTOR_APPLIED_SCORE_DEFINITION_20261018 "A", "D" and the acquisition
#: manifest's verification budget, verbatim.
_DEFINITION_VALUES = {
    "A_reducer": "minimum",
    "f0_scale": 0.17,
    "signed_margin_scale": 0.138419451631707,
    "signed_margin_cell": {"mean_torque_nm": 4.0, "ripple_fraction": 0.30},
    "D_scale": 0.01,
    "verification_budget": 1,
}
#: MOTOR_APPLIED_SCORE_DEFINITION_20261018 "applied_score_pack", verbatim, less
#: its two digests (re-derived for this basis by the shared registrar).
_APPLIED_PACK = {
    "challenge": CHALLENGE,
    "combination": "weighted_arithmetic_mean",
    "decision_policy": {
        "MISSED_OPPORTUNITY": {"eligible": False, "maximum_D": 0.0},
        "NONE_FEASIBLE": {"eligible": False, "maximum_D": 0.0},
        "VERIFIED_FEASIBLE": {"eligible": True, "maximum_D": 1.0},
    },
    "hard_gates": ["native_motor_valid", "complete_fixed_coverage"],
    "legs": {
        "A": {
            "components": [
                {
                    "metric": "robust_fidelity_benefit",
                    "scale": None,
                    "transform": "unit_benefit",
                    "unit": "1",
                    "weight": 1.0,
                }
            ],
            "minimum": 0.28108361796711556,
        },
        "D": {
            "components": [
                {
                    "metric": "verified_value_benefit",
                    "scale": None,
                    "transform": "unit_benefit",
                    "unit": "1",
                    "weight": 1.0,
                }
            ],
            "minimum": 0.3419193228890681,
        },
    },
    "schema": "carbon.scoring.dual-benchmark-pack.v4",
    "scope": "PUBLIC_DEVELOPMENT",
    "value_weight": 0.5,
}
#: The committed applied physics document (the old counted pack's
#: physics_contract.json), carried verbatim inside this pack's envelope.
APPLIED_PHYSICS_SHA256 = (
    "sha256:74e3f30ce38d997e3b7f74505d67981bedcf77de28235ea60bf43f26be9483fd"
)
PHYSICS_VERSION = "motor-applied-physics-contract-20261018"
EVALUATION_VERSION = "motor-dual-development-bank-90-v1"
CASE_ID = "motor-development-bank-90"
_PRODUCER_FILES = (
    "motor_dual_pack.py",
    "motor_dual_measurement.py",
    "private_evaluation_source.py",
    "inference_pair_evidence.py",
)


def _canonical(value):
    """Compact sorted JSON plus LF: the private evaluation source's own form."""
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
    ).encode("utf-8")


def _sha(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def producer_digest():
    """This producer's identity: the bytes of every file it executes."""
    here = Path(__file__).parent
    return _sha(
        _canonical({name: _sha((here / name).read_bytes()) for name in _PRODUCER_FILES})
    )


def bank_rows(bank):
    """Data Collection's bank as measurement rows, in its declared order."""
    rows = []
    for case_id, cohort, record, inputs in zip(
        bank["case_ids"],
        bank["cohorts"],
        bank["reference_records"],
        bank["inputs"],
        strict=True,
    ):
        row = {"case_id": case_id, "cohort": cohort, "record": record}
        if cohort.startswith("decision_"):
            # decision-<design>-<condition>; design order is the objective's.
            row["design_id"] = case_id.split("-")[1]
        row["inputs_vector"] = [float(v) for v in inputs]
        rows.append(row)
    return rows


def bank_digest(bank):
    """Pin of the bank's rows: identities, cohorts, inputs and native records."""
    return _sha(
        _canonical(
            {
                "case_ids": list(bank["case_ids"]),
                "cohorts": list(bank["cohorts"]),
                "inputs": [[float(v) for v in row] for row in bank["inputs"]],
                "records": list(bank["reference_records"]),
            }
        )
    )


def _identities(bank, physics_digest):
    """The registered reference identity: which solvers and counted evidence
    produced the bank's references, and the physics scope they apply to."""
    from carbon.scoring import benchmark_evidence as bench

    images = sorted(
        {record.get("image") or "" for record in bank["reference_records"]} - {""}
    )
    return {
        "solver_digest": _sha(_canonical({"reference_images": images})),
        "fidelity_digest": _sha(_canonical({"bank": bank_digest(bank)})),
        "applicability_digest": physics_digest,
        "evidence_kind": bench.ENGINEERING_REFERENCE,
    }


def pack_documents(
    *,
    bank,
    applied_physics_raw,
    interface_raw,
    train_raw,
    limits_sha256,
    objective_sha256,
):
    """Every Motor document this producer owns, as exact bytes by role name.

    ``bank`` is ``physical_pack.development_bank(CHALLENGE, VERSION)``;
    ``applied_physics_raw`` the committed applied Motor physics document
    (MOTOR_APPLIED_PHYSICS_CONTRACT_20261018), which the emitted
    ``physics_contract`` role carries verbatim as its definition, under the
    ``{version, definition}`` envelope retention and the ScoreEngine bind;
    ``interface_raw`` and ``train_raw``
    the pack's public interface and TRAIN role bytes; the two digests are the
    pack's public important-limit and design-objective role pins.
    """
    from carbon.scoring import benchmark_evidence as bench
    from carbon.scoring import dual_score
    from carbon.scoring.private_evaluation_source import (
        DUAL_MEASUREMENT_CONTRACT_SCHEMA,
    )

    if _sha(applied_physics_raw) != APPLIED_PHYSICS_SHA256:
        raise ValueError("motor applied physics document differs")
    physics = {
        "version": PHYSICS_VERSION,
        "definition": json.loads(applied_physics_raw),
    }
    physics_digest = bench.physics_contract_identity(physics)["definition_digest"]
    definition = {
        "schema": "carbon.scoring.motor-dual-accuracy.v1",
        "method": "motor-applied-g1-dual-from-predictions.v1",
        "challenge": {"id": CHALLENGE, "version": VERSION},
        "scope": "PUBLIC_DEVELOPMENT_EXPOSED_BANK",
        "producer_digest": producer_digest(),
        "train_digest": _sha(train_raw),
        "bank_digest": bank_digest(bank),
        "source_definition_sha256": SOURCE_DEFINITION_SHA256,
        "g1_measurement_contract_sha256": G1_MEASUREMENT_CONTRACT_SHA256,
        "losses": [
            "practice30_mean_f0",
            "pilot_ordinary8_mean_f0",
            "pilot_difficult4_mean_f0",
            "old_v2_48_mean_f0",
            "old_v2_worst_geometry_mean_f0",
            "old_v2_representative32_mean_f0",
            "old_v2_boundary16_mean_f0",
            "old_v2_median_dimensionless_signed_margin_error",
        ],
        "cohort_counts": {
            "practice": 30,
            "pilot_ordinary": 8,
            "pilot_difficult": 4,
            "decision_representative": 32,
            "decision_boundary_stress": 16,
        },
        **_DEFINITION_VALUES,
    }
    accuracy_raw = _canonical(definition)
    basis = {
        "schema": DUAL_MEASUREMENT_CONTRACT_SCHEMA,
        "producer_digest": definition["producer_digest"],
        "accuracy_definition_sha256": _sha(accuracy_raw),
        "important_limit_definition_sha256": limits_sha256,
        "design_objective_sha256": objective_sha256,
    }
    pack = dual_score.register_pack(
        {
            **_APPLIED_PACK,
            "physics_contract_digest": physics_digest,
            "measurement_contract_digest": _sha(_canonical(basis)),
        }
    )
    identity = _identities(bank, physics_digest)
    n, width = len(bank["case_ids"]), len(bank["references"][0])
    trusted_job = {
        "challenge": CHALLENGE,
        "challenge_version": VERSION,
        "interface_digest": _sha(interface_raw),
        "train_digest": _sha(train_raw),
        "physics_contract": physics,
    }
    trusted_job["job_digest"] = _sha(_canonical(trusted_job))
    registration = bench.register(
        {
            "schema": bench.SCHEMA_V3,
            "scope": "PUBLIC_DEVELOPMENT",
            "challenge": CHALLENGE,
            "job_digest": trusted_job["job_digest"],
            "train_digest": trusted_job["train_digest"],
            "physics_contract": physics,
            "output": {
                "quantity": "torque_nm",
                "unit": "N.m",
                "size": n * width,
                "shape": [n, width],
                "metric": "mean_absolute_error",
            },
            "reference": identity,
            "cases": [{"id": CASE_ID, "role": "P", "weight": 1.0}],
            "mandatory_gates": list(_APPLIED_PACK["hard_gates"]),
            "timing_profile": {
                "basis": "ready_input_to_comparable_output",
                "model_device": "carbon-c03-docker-cpu",
                "solver_device": "recorded-per-reference-record",
                "batch_size": n,
                "query_unit": "complete_batch",
                "input_shape": [n, len(bank["inputs"][0])],
            },
        }
    )
    reference_row = {
        "id": CASE_ID,
        "status": "RESOLVED",
        "outputs": [float(v) for row in bank["references"] for v in row],
        "elapsed_s": float(sum(float(r["wall_s"]) for r in bank["reference_records"])),
        "source": "MEASURED_ENGINEERING_REFERENCE_RUN",
        "solver_digest": identity["solver_digest"],
        "fidelity_digest": identity["fidelity_digest"],
        "applicability_digest": identity["applicability_digest"],
        "physics_contract_digest": physics_digest,
        "peak_memory_bytes": None,
    }
    return {
        "physics_contract": _canonical(physics),
        "accuracy_definition": accuracy_raw,
        "reference_rows": _canonical([reference_row]),
        "solver_evidence": _canonical(identity),
        "score_pack": _canonical(pack),
        "source_registration": _canonical(
            {
                "schema": "carbon.challenge-evaluation-source-registration.v1",
                "evaluation_version": EVALUATION_VERSION,
                "trusted_job": trusted_job,
                "benchmark_registration": registration,
            }
        ),
    }


def _train_records(train_raw):
    import numpy as np

    with np.load(io.BytesIO(train_raw), allow_pickle=False) as data:
        targets = np.asarray(data["targets"], dtype=float)
    return [
        {"status": "OK", "outputs": {"torque_nm": [float(v) for v in row]}}
        for row in targets
    ]


def produce(
    *,
    selected,
    public_root,
    private_root,
    entry,
    job,
    registration,
    references,
    originals,
    source_raw,
    bank,
    interface_names,
):
    """The Motor dual benchmark input for one retained model, or a typed refusal."""
    from carbon.scoring import bundle_benchmark_core as bundle
    from carbon.scoring import motor_dual_measurement as mdm
    from carbon.scoring import private_evaluation_source as source_module
    from carbon.scoring.dual_score import score

    refused = source_module.PrivateEvaluationSourceRefused
    require = source_module._producer_require
    roles = {}
    for audience, names, root in (
        (
            "public",
            ("accuracy_definition", "important_limit_definition", "design_objective"),
            public_root,
        ),
        ("private", ("score_pack",), private_root),
    ):
        for name in names:
            try:
                roles[name] = selected.read_json_role(
                    root, audience, name, max_bytes=1024 * 1024
                )
            except ValueError as exc:
                raise refused("dual_native_role_unavailable:" + name) from exc
    try:
        train_raw = selected.read_role(
            public_root, "public", "train", max_bytes=16 * 1024**2
        )
        case_bank = selected.read_role(
            private_root, "private", "case_bank", max_bytes=16 * 1024**2
        )
    except ValueError as exc:
        raise refused("dual_native_role_unavailable:train_or_case_bank") from exc
    definition = roles["accuracy_definition"]
    identity = producer_digest()
    try:
        mdm.validate_definition(
            {
                k: definition.get(k)
                for k in (
                    "schema",
                    "method",
                    "losses",
                    "A_reducer",
                    "f0_scale",
                    "signed_margin_scale",
                    "signed_margin_cell",
                    "D_scale",
                    "verification_budget",
                    "cohort_counts",
                )
            }
        )
    except mdm.MotorMeasurementRefused as exc:
        raise refused("dual_native_definition_method") from exc
    require(
        definition.get("producer_digest") == identity
        and definition.get("train_digest")
        == entry.get("train_digest")
        == _sha(train_raw)
        and definition.get("bank_digest") == bank_digest(bank),
        "dual_native_producer_or_train_binding",
    )
    import numpy as np

    from carbon.development_session.bundle_construction_worker import _tensors

    require(
        case_bank == _tensors(inputs=np.array(bank["inputs"]))
        and _sha(case_bank) == entry.get("roles", {}).get("inputs", {}).get("sha256"),
        "dual_native_source_mapping",
    )
    source = source_module._parse_pack_source(source_raw)
    require(
        type(source.get("cases")) is list
        and len(source["cases"]) == 1
        and type(references) is list
        and len(references) == 1
        and len(registration.get("cases", [])) == 1,
        "dual_native_complete_batch_required",
    )
    require(
        source["evaluation_pack_digest"] == selected.manifest_digest
        and source["registration_digest"] == registration.get("registration_digest")
        and source["cases"][0]["query_sha256"] == _sha(case_bank)
        and source["cases"][0]["reference_row_sha256"]
        == _sha(_canonical(references[0]))
        and source["cases"][0]["reference_status"] == references[0].get("status"),
        "dual_native_source_original_binding",
    )
    for field in ("challenge", "challenge_version", "interface_digest", "train_digest"):
        require(
            source.get(field) == entry.get(field) == job.get(field),
            "dual_native_identity",
        )
    if references[0].get("status") != "RESOLVED":
        raise refused(
            "dual_native_reference_infra"
            if references[0].get("status") == "FAILED_INFRA"
            else "dual_native_reference_unresolved"
        )
    require(
        references[0].get("outputs")
        == [float(v) for row in bank["references"] for v in row],
        "dual_native_reference_flat_binding",
    )
    receipt, worker, values, inference = source_module._authenticated_graph_outputs(
        entry, registration, originals
    )
    n, width = len(bank["case_ids"]), len(bank["references"][0])
    require(
        len(values) == n * width
        and inference["receipt"]["measurement"]["output_shape"] == [n, width],
        "dual_native_tensor_shape",
    )
    repeats = source_module.read_inference_repeats(
        originals, receipt=receipt, worker=worker
    )
    require(all(len(r) == n * width for r in repeats), "dual_repeat_evidence_shape")

    def rows_of(flat):
        return [list(flat[i * width : (i + 1) * width]) for i in range(n)]

    bank_measure_rows = [
        {
            **{k: v for k, v in row.items() if k != "inputs_vector"},
            "inputs": dict(zip(interface_names, row["inputs_vector"], strict=True)),
        }
        for row in bank_rows(bank)
    ]
    try:
        measured = mdm.measure(
            bank=bank_measure_rows,
            outputs=rows_of(values),
            repeats=[rows_of(r) for r in repeats],
            definition=definition,
            limits=roles["important_limit_definition"],
            objective=roles["design_objective"],
            train=_train_records(train_raw),
        )
    except mdm.MotorMeasurementRefused as exc:
        raise refused("dual_native_" + exc.code) from exc
    pack = roles["score_pack"]
    gates = list(pack.get("hard_gates", []))
    require(
        gates == registration["mandatory_gates"] == list(_APPLIED_PACK["hard_gates"]),
        "dual_native_gate_contract",
    )

    def leg(value):
        if value is None:
            return {"status": "CANDIDATE_INVALID", "value": None, "unit": "1"}
        return {"status": "RESOLVED", "value": value, "unit": "1"}

    benchmark = {
        "schema": "carbon.scoring.dual-benchmark-input.v1",
        "scope": pack["scope"],
        "challenge": CHALLENGE,
        "physics_contract_digest": pack["physics_contract_digest"],
        "measurement_contract_digest": pack["measurement_contract_digest"],
        "population_role": source["cases"][0]["role"],
        "common_mask_digest": _sha(_canonical(source["cases"])),
        "models": [
            {
                "artifact_digest": entry["entry_id"],
                "gates": {
                    k: ("PASS" if measured["gates"][k] else "FAIL") for k in gates
                },
                "measurements": {
                    "robust_fidelity_benefit": leg(measured["A"]),
                    "verified_value_benefit": leg(measured["D"]),
                },
                "decision_outcome": measured["decision_outcome"],
            }
        ],
    }
    score(benchmark, pack)
    native_gates = {k: measured["gates"][k] for k in gates}
    model = bundle.measurement_from_saved_inference(
        entry, registration, inference, gates=native_gates
    )
    return model, benchmark, identity
