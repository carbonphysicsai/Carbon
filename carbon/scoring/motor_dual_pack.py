"""Motor's dual evaluation pack documents and its private dual producer.

DEVELOPMENT only, exposed development bank (``physical_pack.development_bank``,
committed repository material): never a hidden-exam or paying claim.

Two halves, one source:

- ``pack_documents`` regenerates, from committed sources only, the documents
  Data Collection's pack pins for Motor: the public ``accuracy_definition``
  (the producer's registered A/D definition and pin), and the private
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

import functools
import hashlib
import io
import json
import re
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
#: The committed applied definition's file (sha256 SOURCE_DEFINITION_SHA256).
DEFINITION_FILE = (
    Path(__file__).resolve().parents[1]
    / "challenge_kit/data/motor-applied-score-definition-20261018.json"
)
#: MOTOR_DUAL_TRANSFER_ACQUISITION_MANIFEST_20261018: the source of the
#: verification budget, the one value the applied definition does not hold.
ACQUISITION_MANIFEST_SHA256 = (
    "sha256:9e32f3a3b233ca81e84475a715319a6c24ec48296560d460563fa28bdad76a53"
)
ACQUISITION_MANIFEST_FILE = DEFINITION_FILE.with_name(
    "motor-dual-transfer-acquisition-manifest-20261018.json"
)
_SIGNED_MARGIN_CELL = re.compile(
    r"max\(abs\(mean_margin_error_nm\)/([0-9]+(?:\.[0-9]+)?),"
    r"abs\(ripple_margin_error_fraction\)/([0-9]+(?:\.[0-9]+)?)\)"
)


@functools.cache
def applied_definition():
    """The committed applied definition, read only at its pinned bytes."""
    raw = DEFINITION_FILE.read_bytes()
    if _sha(raw) != SOURCE_DEFINITION_SHA256:
        raise ValueError("motor applied score definition differs from its pin")
    return json.loads(raw)


@functools.cache
def _verification_budget():
    raw = ACQUISITION_MANIFEST_FILE.read_bytes()
    if _sha(raw) != ACQUISITION_MANIFEST_SHA256:
        raise ValueError("motor acquisition manifest differs from its pin")
    budget = json.loads(raw)["verification_budget"]
    if type(budget) is not int or budget < 1:
        raise ValueError("motor acquisition manifest budget differs")
    return budget


def _definition_values():
    """The definition's "A" and "D" values, verbatim; no value is chosen here."""
    a, d = applied_definition()["A"], applied_definition()["D"]
    cell = _SIGNED_MARGIN_CELL.fullmatch(a["signed_margin_cell"])
    if (
        a["reducer"] != "minimum of eight unit benefits"
        or a["benefit"] != "1/(1+loss/scale)"
        or cell is None
        or d["benefit"] != f"1/(1+verified_regret/{d['scale']})"
    ):
        raise ValueError("motor applied score definition form differs")
    return {
        "losses": list(a["losses"]),
        "A_reducer": "minimum",
        "f0_scale": a["f0_scale"],
        "signed_margin_scale": a["signed_margin_scale"],
        "signed_margin_cell": {
            "mean_torque_nm": float(cell.group(1)),
            "ripple_fraction": float(cell.group(2)),
        },
        "D_scale": d["scale"],
        "verification_budget": _verification_budget(),
    }


def _applied_pack():
    """The definition's "applied_score_pack" less its three digests, which the
    shared registrar re-derives for this pack's physics and measurement basis."""
    pack = applied_definition()["applied_score_pack"]
    return {
        k: v
        for k, v in pack.items()
        if k
        not in ("pack_digest", "physics_contract_digest", "measurement_contract_digest")
    }


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
    physics,
    interface_raw,
    train_raw,
    limits_sha256,
    objective_sha256,
):
    """Every Motor document this producer owns, as exact bytes by role name.

    ``bank`` is ``physical_pack.development_bank(CHALLENGE, VERSION)``;
    ``physics`` the pack's own physics contract
    (``physical_pack.physics_contract``: the committed applied document inside
    the ``{version, definition}`` envelope retention and the ScoreEngine bind);
    ``interface_raw`` and ``train_raw``
    the pack's public interface and TRAIN role bytes; the two digests are the
    pack's public important-limit and design-objective role pins.
    """
    from carbon.scoring import benchmark_evidence as bench
    from carbon.scoring import dual_score
    from carbon.scoring.private_evaluation_source import (
        DUAL_MEASUREMENT_CONTRACT_SCHEMA,
    )

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
        "cohort_counts": {
            "practice": 30,
            "pilot_ordinary": 8,
            "pilot_difficult": 4,
            "decision_representative": 32,
            "decision_boundary_stress": 16,
        },
        **_definition_values(),
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
            **_applied_pack(),
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
            "mandatory_gates": list(_applied_pack()["hard_gates"]),
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


MANIFEST_NAME = "evaluation-pack.json"


def write_development_pack(root):
    """Write the complete Motor DEVELOPMENT pack under a new, empty ``root``.

    Data Collection's ``physical_pack`` writes the public roles and the exposed
    bank; this producer's documents replace accuracy_definition,
    reference_rows and solver_evidence and add score_pack and
    source_registration. ``root`` serves as the pack, public and private root;
    the draft manifest is ``root / MANIFEST_NAME``, which the receiver seals.
    """
    from carbon.challenge_kit import physical_pack

    physics = physical_pack.physics_contract(CHALLENGE, VERSION)
    if type(physics) is not dict or set(physics) != {"version", "definition"}:
        raise ValueError(
            "motor pack physics role is not in its {version, definition} envelope"
        )
    root = Path(root)
    manifest_path = physical_pack.write_public_pack(
        root, CHALLENGE, VERSION, exposed_development_bank=True
    )
    public = physical_pack.public_roles(CHALLENGE, VERSION)
    documents = pack_documents(
        bank=physical_pack.development_bank(CHALLENGE, VERSION),
        physics=physics,
        interface_raw=public["interface"],
        train_raw=public["train"],
        limits_sha256=_sha(public["important_limit_definition"]),
        objective_sha256=_sha(public["design_objective"]),
    )
    draft = json.loads(manifest_path.read_bytes())
    for role, body in documents.items():
        scope = "public" if role == "accuracy_definition" else "private"
        name = f"{scope}/{role}.json"
        (root / name).write_bytes(body)
        draft[scope][role] = {"path": name}
    manifest_path.write_bytes(_canonical(draft))
    if manifest_path.name != MANIFEST_NAME:
        raise ValueError("motor pack manifest name differs")
    return manifest_path


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
    measurement = source_module.query_measurement(
        entry, registration, originals, receipt
    )
    require(
        len(values) == n * width and measurement["output_shape"] == [n, width],
        "dual_native_tensor_shape",
    )
    repeats = source_module.read_inference_repeats(
        originals, receipt=receipt, worker=worker, measurement=measurement
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
        gates == registration["mandatory_gates"] == list(_applied_pack()["hard_gates"]),
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
        entry,
        registration,
        inference,
        gates=native_gates,
        timed_query=originals.get("timed_query"),
    )
    return model, benchmark, identity


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(
        description="Write the complete Motor DEVELOPMENT evaluation pack."
    )
    parser.add_argument("root", type=Path, help="new or empty pack directory")
    args = parser.parse_args(argv)
    print(write_development_pack(args.root.resolve()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
