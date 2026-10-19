"""One dual evaluation pack and private dual producer for physical Challenges.

DEVELOPMENT only, exposed development bank (``physical_pack.development_bank``,
committed repository material): never a hidden-exam or paying claim.

A Challenge adapter module (``motor_dual_pack``, ``cooling_dual_pack``) owns
only what is Challenge-specific: its registered accuracy definition, applied
score pack, TRAIN records and measurement. Everything else is here, once:

- ``pack_documents`` regenerates, from committed sources only, the documents
  the pack pins for the Challenge: the public ``accuracy_definition`` and the
  private ``reference_rows``, ``solver_evidence``, ``score_pack`` and
  ``source_registration`` (one complete-batch v3 case over the bank).
- ``write_development_pack`` writes the complete pack the receiver seals.
- ``produce`` reads one retained model's authenticated bank predictions and two
  fresh repeats, has the adapter measure A and D, and returns the dual
  benchmark input for the shared ScoreEngine.

Leg minimums are bound to one grading platform (Validator, 2026-10-19): the
accuracy definition records the judge inference image and device class they
belong to, and ``produce`` refuses a model graded on any other image with
``leg_minimum_platform_mismatch`` (unavailable evidence, never a candidate
fail). Cross-platform drift is a different evaluation; a new judge image means
recomputed minimums under a new evaluation version.

Adapter interface: ``CHALLENGE``, ``VERSION``, ``CASE_ID``,
``EVALUATION_VERSION``, ``OUTPUT`` ({quantity, unit}), ``FILES`` (its
executed files), ``Refused`` (exception with ``code``),
``definition(bank, train_raw)``, ``validate_definition(definition)``,
``applied_pack(...)``, ``measure(...)``, ``physics_contract()`` (or None when
the pack's physics role is owned elsewhere).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

MANIFEST_NAME = "evaluation-pack.json"
DEVICE_CLASS = "carbon-c03-docker-cpu"
METRICS = {"A": "robust_fidelity_benefit", "D": "verified_value_benefit"}
_SHARED_FILES = (
    "physical_dual_pack.py",
    "private_evaluation_source.py",
    "inference_pair_evidence.py",
)


def canonical(value):
    """Compact sorted JSON plus LF: the private evaluation source's own form."""
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
    ).encode("utf-8")


def sha(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def producer_digest(adapter):
    """The producer's identity: the bytes of every file it executes."""
    here = Path(__file__).parent
    names = sorted({*_SHARED_FILES, *adapter.FILES})
    return sha(canonical({name: sha((here / name).read_bytes()) for name in names}))


def bank_rows(bank, interface_names):
    """Data Collection's bank as measurement rows, in its declared order."""
    rows = []
    for case_id, cohort, record, inputs in zip(
        bank["case_ids"],
        bank["cohorts"],
        bank["reference_records"],
        bank["inputs"],
        strict=True,
    ):
        row = {
            "case_id": case_id,
            "cohort": cohort,
            "record": record,
            "inputs": dict(
                zip(interface_names, (float(v) for v in inputs), strict=True)
            ),
        }
        if cohort.startswith("decision_"):
            # decision-<design>-<condition>; design order is the objective's.
            row["design_id"] = record.get("design_id") or case_id.split("-")[1]
            if "condition_id" in record:
                row["condition_id"] = record["condition_id"]
        rows.append(row)
    return rows


def bank_digest(bank):
    """Pin of the bank's rows: identities, cohorts, inputs and native records."""
    return sha(
        canonical(
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
        "solver_digest": sha(canonical({"reference_images": images})),
        "fidelity_digest": sha(canonical({"bank": bank_digest(bank)})),
        "applicability_digest": physics_digest,
        "evidence_kind": bench.ENGINEERING_REFERENCE,
    }


def leg_minimum_platform(inference_image_id, device_class=DEVICE_CLASS):
    """The grading platform the pack's leg minimums belong to."""
    from carbon.registry.digest import is_sha256_digest

    if not is_sha256_digest(inference_image_id) or not (
        type(device_class) is str and device_class
    ):
        raise ValueError("leg-minimum platform requires an image digest and device")
    return {"inference_image_id": inference_image_id, "device_class": device_class}


def pack_documents(
    adapter,
    *,
    bank,
    physics,
    interface_raw,
    train_raw,
    limits_raw,
    objective_raw,
    platform,
):
    """Every document the producer owns for one Challenge, as exact bytes.

    ``bank`` is ``physical_pack.development_bank``; ``physics`` the pack's
    physics contract in its ``{version, definition}`` envelope; the raw bytes
    are the pack's public interface, TRAIN, important-limit and
    design-objective roles; ``platform`` is ``leg_minimum_platform(...)``.
    """
    from carbon.challenge_kit import physical_public_train
    from carbon.scoring import benchmark_evidence as bench
    from carbon.scoring import dual_score
    from carbon.scoring.private_evaluation_source import (
        DUAL_MEASUREMENT_CONTRACT_SCHEMA,
    )

    physics_digest = bench.physics_contract_identity(physics)["definition_digest"]
    names = physical_public_train.numeric_interface_document(adapter.CHALLENGE)[
        "input_names"
    ]
    definition = {
        **adapter.definition(bank=bank, train_raw=train_raw),
        "challenge": {"id": adapter.CHALLENGE, "version": adapter.VERSION},
        "scope": "PUBLIC_DEVELOPMENT_EXPOSED_BANK",
        "producer_digest": producer_digest(adapter),
        "train_digest": sha(train_raw),
        "bank_digest": bank_digest(bank),
        "leg_minimum_platform": leg_minimum_platform(**platform),
    }
    adapter.validate_definition(definition)
    accuracy_raw = canonical(definition)
    basis = {
        "schema": DUAL_MEASUREMENT_CONTRACT_SCHEMA,
        "producer_digest": definition["producer_digest"],
        "accuracy_definition_sha256": sha(accuracy_raw),
        "important_limit_definition_sha256": sha(limits_raw),
        "design_objective_sha256": sha(objective_raw),
    }
    applied = adapter.applied_pack(
        bank_rows=bank_rows(bank, names),
        definition=definition,
        limits=json.loads(limits_raw),
        objective=json.loads(objective_raw),
        train_raw=train_raw,
        names=names,
    )
    pack = dual_score.register_pack(
        {
            **applied,
            "physics_contract_digest": physics_digest,
            "measurement_contract_digest": sha(canonical(basis)),
        }
    )
    identity = _identities(bank, physics_digest)
    n, width = len(bank["case_ids"]), len(bank["references"][0])
    trusted_job = {
        "challenge": adapter.CHALLENGE,
        "challenge_version": adapter.VERSION,
        "interface_digest": sha(interface_raw),
        "train_digest": sha(train_raw),
        "physics_contract": physics,
    }
    trusted_job["job_digest"] = sha(canonical(trusted_job))
    registration = bench.register(
        {
            "schema": bench.SCHEMA_V3,
            "scope": "PUBLIC_DEVELOPMENT",
            "challenge": adapter.CHALLENGE,
            "job_digest": trusted_job["job_digest"],
            "train_digest": trusted_job["train_digest"],
            "physics_contract": physics,
            "output": {
                **adapter.OUTPUT,
                "size": n * width,
                "shape": [n, width],
                "metric": "mean_absolute_error",
            },
            "reference": identity,
            "cases": [{"id": adapter.CASE_ID, "role": "P", "weight": 1.0}],
            "mandatory_gates": list(applied["hard_gates"]),
            "timing_profile": {
                "basis": "ready_input_to_comparable_output",
                "model_device": definition["leg_minimum_platform"]["device_class"],
                "solver_device": "recorded-per-reference-record",
                "batch_size": n,
                "query_unit": "complete_batch",
                "input_shape": [n, len(bank["inputs"][0])],
            },
        }
    )
    reference_row = {
        "id": adapter.CASE_ID,
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
        "reference_rows": canonical([reference_row]),
        "solver_evidence": canonical(identity),
        "score_pack": canonical(pack),
        "source_registration": canonical(
            {
                "schema": "carbon.challenge-evaluation-source-registration.v1",
                "evaluation_version": adapter.EVALUATION_VERSION,
                "trusted_job": trusted_job,
                "benchmark_registration": registration,
            }
        ),
    }


def write_development_pack(
    adapter, root, *, inference_image_id, device_class=DEVICE_CLASS
):
    """Write the Challenge's complete DEVELOPMENT pack under a new, empty ``root``.

    Data Collection's ``physical_pack`` writes the public roles and the exposed
    bank; this producer's documents replace accuracy_definition,
    reference_rows and solver_evidence and add score_pack and
    source_registration. ``root`` serves as the pack, public and private root;
    the draft manifest is ``root / MANIFEST_NAME``, which the receiver seals.
    The pack's physics role is the receiver material's own; it must be in its
    ``{version, definition}`` envelope (and equal the adapter's generated
    contract when the adapter generates it).
    """
    from carbon.challenge_kit import physical_pack

    physics = physical_pack.physics_contract(adapter.CHALLENGE, adapter.VERSION)
    if type(physics) is not dict or set(physics) != {"version", "definition"}:
        raise ValueError(
            "pack physics role is not in its {version, definition} envelope"
        )
    generated = adapter.physics_contract()
    if generated is not None and generated != physics:
        raise ValueError("pack physics role differs from the generated contract")
    root = Path(root)
    manifest_path = physical_pack.write_public_pack(
        root, adapter.CHALLENGE, adapter.VERSION, exposed_development_bank=True
    )
    public = physical_pack.public_roles(adapter.CHALLENGE, adapter.VERSION)
    documents = pack_documents(
        adapter,
        bank=physical_pack.development_bank(adapter.CHALLENGE, adapter.VERSION),
        physics=physics,
        interface_raw=public["interface"],
        train_raw=public["train"],
        limits_raw=public["important_limit_definition"],
        objective_raw=public["design_objective"],
        platform=leg_minimum_platform(inference_image_id, device_class),
    )
    draft = json.loads(manifest_path.read_bytes())
    for role, body in documents.items():
        scope = "public" if role == "accuracy_definition" else "private"
        name = f"{scope}/{role}.json"
        (root / name).write_bytes(body)
        draft[scope][role] = {"path": name}
    manifest_path.write_bytes(canonical(draft))
    if manifest_path.name != MANIFEST_NAME:
        raise ValueError("pack manifest name differs")
    return manifest_path


def produce(
    adapter,
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
    """The dual benchmark input for one retained model, or a typed refusal."""
    import numpy as np

    from carbon.development_session.bundle_construction_worker import _tensors
    from carbon.scoring import bundle_benchmark_core as bundle
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
    identity = producer_digest(adapter)
    try:
        adapter.validate_definition(definition)
    except adapter.Refused as exc:
        raise refused("dual_native_definition_method") from exc
    require(
        definition.get("producer_digest") == identity
        and definition.get("train_digest")
        == entry.get("train_digest")
        == sha(train_raw)
        and definition.get("bank_digest") == bank_digest(bank),
        "dual_native_producer_or_train_binding",
    )
    require(
        case_bank == _tensors(inputs=np.array(bank["inputs"]))
        and sha(case_bank) == entry.get("roles", {}).get("inputs", {}).get("sha256"),
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
        and source["cases"][0]["query_sha256"] == sha(case_bank)
        and source["cases"][0]["reference_row_sha256"] == sha(canonical(references[0]))
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
    platform = definition.get("leg_minimum_platform")
    if (
        type(platform) is not dict
        or platform.get("inference_image_id") != worker.get("inference_image_id")
        or platform.get("device_class")
        != registration.get("timing_profile", {}).get("model_device")
    ):
        raise refused("leg_minimum_platform_mismatch")
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

    try:
        measured = adapter.measure(
            bank_rows=bank_rows(bank, interface_names),
            outputs=rows_of(values),
            repeats=[rows_of(r) for r in repeats],
            definition=definition,
            limits=roles["important_limit_definition"],
            objective=roles["design_objective"],
            train_raw=train_raw,
            names=interface_names,
        )
    except adapter.Refused as exc:
        raise refused("dual_native_" + exc.code) from exc
    pack = roles["score_pack"]
    gates = list(pack.get("hard_gates", []))
    require(
        gates == registration["mandatory_gates"] == list(measured["gates"]),
        "dual_native_gate_contract",
    )

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
        "population_role": source["cases"][0]["role"],
        "common_mask_digest": sha(canonical(source["cases"])),
        "models": [
            {
                "artifact_digest": entry["entry_id"],
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
    score(benchmark, pack)
    model = bundle.measurement_from_saved_inference(
        entry,
        registration,
        inference,
        gates={k: measured["gates"][k] for k in gates},
        timed_query=originals.get("timed_query"),
    )
    return model, benchmark, identity
