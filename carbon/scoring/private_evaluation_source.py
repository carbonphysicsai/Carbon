"""Build a private v2 evaluation source receipt from trusted run originals.

The operator selects a retained Challenge pack and owns this call. The receipt
contains identities and digests only: no protected query bytes, reference
values, or participant-controlled label. Its caller stores the returned bytes
write-once and independently registers their digest for the ScoreLab binder.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path

from carbon.challenge_validator.evaluation_pack import (
    PRIVATE_ROLES,
    EvaluationPackSnapshot,
)
from carbon.registry.digest import is_sha256_digest
from carbon.scoring.benchmark_evidence import (
    BenchmarkRefused,
    physics_contract_identity,
)
from carbon.scoring.dual_score import DualScoreRefused, register_pack, score

PACK_SOURCE_SCHEMA = "carbon.scoring.private-evaluation-source.v2"
DUAL_MEASUREMENT_SCHEMA = "carbon.scoring.private-dual-measurement.v1"
#: A dual measurement whose repeat gate read a pinned source-free inference pair.
PAIRED_DUAL_MEASUREMENT_SCHEMA = "carbon.scoring.private-dual-measurement.v2"
DUAL_MEASUREMENT_CONTRACT_SCHEMA = "carbon.scoring.dual-measurement-contract.v1"
_REFERENCE_STATUS = frozenset({"RESOLVED", "UNRESOLVED", "FAILED_INFRA"})
_REQUIRED_PUBLIC_ROLES = frozenset(
    {"construction_kit", "interface", "train", "physics_contract"}
)
_MAX_RECEIPT_BYTES = 1024 * 1024


class PrivateEvaluationSourceRefused(ValueError):
    """The trusted source material is absent, inconsistent, or too large."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class PreparedPrivateEvaluationSource:
    raw: bytes
    sha256: str
    evaluation_pack_digest: str


@dataclass(frozen=True)
class PreparedPrivateDualMeasurement:
    raw: bytes
    sha256: str
    evaluation_pack_digest: str
    measured_model: dict


def produce_dual_benchmark_input(
    *,
    selected_pack: EvaluationPackSnapshot,
    public_root: Path,
    private_root: Path,
    entry: dict,
    trusted_job: dict,
    registration: dict,
    references: list[dict],
    graph_originals: dict,
    evaluation_source_receipt_raw: bytes,
) -> tuple[dict, dict, str]:
    """Run the fixed DEVELOPMENT cold-eight producer, or refuse unavailable roles.

    This hook consumes retained worker originals and source-owned pack roles.
    It executes no participant code, model, solver or configurable callback.
    Other Challenge adapters remain explicitly unavailable. A required repeat
    gate cannot be inferred from the one retained normal inference.
    """
    adapter = (
        _physical_adapter(entry.get("challenge"), entry.get("challenge_version"))
        if type(entry) is dict
        else None
    )
    if adapter is not None:
        try:
            from carbon.challenge_kit import physical_pack
            from carbon.scoring import physical_dual_pack

            bank = physical_pack.development_bank(
                adapter.CHALLENGE, entry.get("challenge_version")
            )
            names = physical_dual_pack.input_names(adapter)
        except (ImportError, ValueError) as exc:
            raise PrivateEvaluationSourceRefused(
                "dual_native_role_unavailable:development_bank"
            ) from exc
        return physical_dual_pack.produce(
            adapter,
            selected=selected_pack,
            public_root=public_root,
            private_root=private_root,
            entry=entry,
            job=trusted_job,
            registration=registration,
            references=references,
            originals=graph_originals,
            source_raw=evaluation_source_receipt_raw,
            bank=bank,
            interface_names=names,
        )
    if type(entry) is not dict or entry.get("challenge") != "f02":
        raise PrivateEvaluationSourceRefused("dual_measurement_producer_unavailable")
    return _produce_f02_cold(
        selected_pack,
        public_root,
        private_root,
        entry,
        trusted_job,
        registration,
        references,
        graph_originals,
        evaluation_source_receipt_raw,
    )


def _physical_adapter(challenge, version):
    """The physical Challenge version's dual pack adapter, or None
    (``physical_adapters``, outside every producer's identity)."""
    from carbon.scoring import physical_adapters

    return physical_adapters.adapter(challenge, version)


def produce_registered_dual_measurement(
    *,
    selected_pack: EvaluationPackSnapshot,
    public_root: Path,
    private_root: Path,
    entry: dict,
    trusted_job: dict,
    registration: dict,
    references: list[dict],
    graph_originals: dict,
    evaluation_source_receipt_raw: bytes,
) -> PreparedPrivateDualMeasurement:
    """Bind a fixed producer's output with the real source/pack receipt checks.

    The caller retains the resulting bytes and independently registers its
    SHA in owner custody. An unavailable producer leaves grading unavailable.
    """
    measured_model, benchmark, producer_digest = produce_dual_benchmark_input(
        selected_pack=selected_pack,
        public_root=public_root,
        private_root=private_root,
        entry=entry,
        trusted_job=trusted_job,
        registration=registration,
        references=references,
        graph_originals=graph_originals,
        evaluation_source_receipt_raw=evaluation_source_receipt_raw,
    )
    return build_dual_measurement_receipt(
        selected_pack=selected_pack,
        public_root=public_root,
        private_root=private_root,
        entry=entry,
        measured_model=measured_model,
        graph_originals=graph_originals,
        evaluation_source_receipt_raw=evaluation_source_receipt_raw,
        benchmark=benchmark,
        producer_digest=producer_digest,
    )


def _sha(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _canonical(value: object) -> bytes:
    try:
        return (
            json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError, OverflowError, RecursionError) as exc:
        raise PrivateEvaluationSourceRefused("source_json") from exc


def build_pack_source_receipt(
    *,
    selected_pack: EvaluationPackSnapshot,
    entry: dict,
    trusted_job: dict,
    registration: dict,
    references: list,
    ordered_query_bytes: list[bytes],
    evaluation_version: str,
) -> PreparedPrivateEvaluationSource:
    """Prepare v2 bytes for one selected, frozen pack and registered case list.

    ``selected_pack`` must come from the operator's retained ``load_pack``
    result. The trusted caller must verify role bytes against the actual run
    using each role's existing validator before this function is called. This
    function checks used role availability, the TRAIN pin, and supplied
    original identities; it cannot attest caller custody or prove the other
    pack role relationships by itself. The task path retains ``raw`` and
    registers ``sha256`` independently.
    """
    if type(selected_pack) is not EvaluationPackSnapshot or not is_sha256_digest(
        selected_pack.manifest_digest
    ):
        raise PrivateEvaluationSourceRefused("selected_pack_missing")
    missing = selected_pack.missing_roles()
    if _REQUIRED_PUBLIC_ROLES.intersection(
        missing["public"]
    ) or PRIVATE_ROLES.intersection(missing["private"]):
        raise PrivateEvaluationSourceRefused("selected_pack_incomplete")
    if type(evaluation_version) is not str or not evaluation_version:
        raise PrivateEvaluationSourceRefused("evaluation_version_missing")
    if any(type(value) is not dict for value in (entry, trusted_job, registration)):
        raise PrivateEvaluationSourceRefused("source_identity")
    challenge = selected_pack.challenge_id
    version = selected_pack.challenge_version
    if (
        entry.get("challenge") != challenge
        or entry.get("challenge_version") != version
        or trusted_job.get("challenge") != challenge
        or trusted_job.get("challenge_version") != version
        or registration.get("challenge") != challenge
        or registration.get("job_digest") != trusted_job.get("job_digest")
        or registration.get("train_digest") != trusted_job.get("train_digest")
        or entry.get("train_digest") != trusted_job.get("train_digest")
        or entry.get("interface_digest") != trusted_job.get("interface_digest")
        or not is_sha256_digest(registration.get("registration_digest"))
        or not all(
            is_sha256_digest(value)
            for value in (
                entry.get("interface_digest"),
                entry.get("train_digest"),
                trusted_job.get("job_digest"),
            )
        )
    ):
        raise PrivateEvaluationSourceRefused("source_identity")
    if selected_pack.public["train"]["sha256"] != entry["train_digest"]:
        raise PrivateEvaluationSourceRefused("selected_pack_train_mismatch")
    try:
        physics = physics_contract_identity(trusted_job["physics_contract"])
    except (BenchmarkRefused, KeyError, TypeError, ValueError) as exc:
        raise PrivateEvaluationSourceRefused("physics_contract") from exc
    if registration.get("physics_contract") != trusted_job["physics_contract"]:
        raise PrivateEvaluationSourceRefused("physics_contract")
    cases = registration.get("cases")
    if (
        type(cases) is not list
        or not cases
        or type(references) is not list
        or type(ordered_query_bytes) is not list
        or len(cases) != len(references)
        or len(cases) != len(ordered_query_bytes)
    ):
        raise PrivateEvaluationSourceRefused("source_roster")
    source_cases = []
    seen = set()
    for case, reference, query in zip(
        cases, references, ordered_query_bytes, strict=True
    ):
        weight = case.get("weight") if type(case) is dict else None
        try:
            finite_weight = type(weight) in (int, float) and math.isfinite(weight)
        except (OverflowError, ValueError, TypeError):
            finite_weight = False
        if (
            type(case) is not dict
            or type(reference) is not dict
            or type(query) is not bytes
            or not query
            or type(case.get("id")) is not str
            or not case["id"]
            or case["id"] in seen
            or reference.get("id") != case["id"]
            or type(reference.get("status")) is not str
            or reference.get("status") not in _REFERENCE_STATUS
            or type(case.get("role")) is not str
            or not case["role"]
            or not finite_weight
        ):
            raise PrivateEvaluationSourceRefused("source_case")
        seen.add(case["id"])
        source_cases.append(
            {
                "id": case["id"],
                "role": case["role"],
                "weight": case["weight"],
                "query_sha256": _sha(query),
                "reference_row_sha256": _sha(_canonical(reference)),
                "reference_status": reference["status"],
            }
        )
    body = {
        "schema": PACK_SOURCE_SCHEMA,
        "challenge": challenge,
        "challenge_version": version,
        "evaluation_version": evaluation_version,
        "interface_digest": entry["interface_digest"],
        "train_digest": entry["train_digest"],
        "job_digest": trusted_job["job_digest"],
        "registration_digest": registration["registration_digest"],
        "physics_contract": physics,
        "cases": source_cases,
        "evaluation_pack_digest": selected_pack.manifest_digest,
    }
    raw = _canonical(body)
    if len(raw) > _MAX_RECEIPT_BYTES:
        raise PrivateEvaluationSourceRefused("source_receipt_too_large")
    return PreparedPrivateEvaluationSource(
        raw=raw,
        sha256=_sha(raw),
        evaluation_pack_digest=selected_pack.manifest_digest,
    )


def _parse_pack_source(raw: bytes) -> dict:
    if type(raw) is not bytes or not 0 < len(raw) <= _MAX_RECEIPT_BYTES:
        raise PrivateEvaluationSourceRefused("dual_source_bytes")

    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise PrivateEvaluationSourceRefused("dual_source_duplicate_key")
            value[key] = item
        return value

    def reject_constant(_value):
        raise PrivateEvaluationSourceRefused("dual_source_nonfinite")

    try:
        source = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=unique,
            parse_constant=reject_constant,
        )
    except PrivateEvaluationSourceRefused:
        raise
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise PrivateEvaluationSourceRefused("dual_source_json") from exc
    if (
        type(source) is not dict
        or source.get("schema") != PACK_SOURCE_SCHEMA
        or set(source)
        != {
            "schema",
            "challenge",
            "challenge_version",
            "evaluation_version",
            "interface_digest",
            "train_digest",
            "job_digest",
            "registration_digest",
            "physics_contract",
            "cases",
            "evaluation_pack_digest",
        }
        or _canonical(source) != raw
    ):
        raise PrivateEvaluationSourceRefused("dual_source_shape")
    return source


def build_dual_measurement_receipt(
    *,
    selected_pack: EvaluationPackSnapshot,
    public_root: Path,
    private_root: Path,
    entry: dict,
    measured_model: dict,
    graph_originals: dict,
    evaluation_source_receipt_raw: bytes,
    benchmark: dict,
    producer_digest: str,
) -> PreparedPrivateDualMeasurement:
    """Pin a trusted producer's DEVELOPMENT A/D measurements to saved originals.

    The Carbon-owned caller must run the selected producer and independently
    register this receipt's SHA. This pure builder checks identities and exact
    pack bytes; it cannot attest producer execution or scientific adequacy.
    The private binder verifies the saved query, reference, model and worker
    originals before the shared scoring core may consume ``benchmark``.
    """
    if type(selected_pack) is not EvaluationPackSnapshot or not is_sha256_digest(
        selected_pack.manifest_digest
    ):
        raise PrivateEvaluationSourceRefused("selected_pack_missing")
    source = _parse_pack_source(evaluation_source_receipt_raw)
    if source["evaluation_pack_digest"] != selected_pack.manifest_digest:
        raise PrivateEvaluationSourceRefused("dual_pack_mismatch")
    missing = selected_pack.missing_roles()
    if (
        any(
            role in missing["public"]
            for role in (
                "accuracy_definition",
                "important_limit_definition",
                "design_objective",
            )
        )
        or "score_pack" in missing["private"]
    ):
        raise PrivateEvaluationSourceRefused("dual_pack_incomplete")
    if (
        type(entry) is not dict
        or type(measured_model) is not dict
        or type(benchmark) is not dict
        or graded_original_keys(graph_originals) is None
        or not all(
            type(graph_originals[key]) is bytes and graph_originals[key]
            for key in graded_original_keys(graph_originals)
            | {"inference_pair_raw"} & set(graph_originals)
        )
        or (
            "inference_pair_raw" in graph_originals
            and _sha(graph_originals["inference_pair_raw"])
            != graph_originals["inference_pair_sha256"]
        )
        or not is_sha256_digest(producer_digest)
        or not is_sha256_digest(entry.get("entry_id"))
        or not is_sha256_digest(entry.get("state_digest"))
        or entry.get("challenge") != source["challenge"]
        or entry.get("challenge_version") != source["challenge_version"]
        or entry.get("interface_digest") != source["interface_digest"]
        or entry.get("train_digest") != source["train_digest"]
        or measured_model.get("entry_id") != entry["entry_id"]
        or measured_model.get("state_digest") != entry["state_digest"]
        or selected_pack.challenge_id != source["challenge"]
        or selected_pack.challenge_version != source["challenge_version"]
    ):
        raise PrivateEvaluationSourceRefused("dual_model_identity")
    try:
        accuracy = selected_pack.read_json_role(
            public_root, "public", "accuracy_definition", max_bytes=1024 * 1024
        )
        limits = selected_pack.read_json_role(
            public_root,
            "public",
            "important_limit_definition",
            max_bytes=1024 * 1024,
        )
        design = selected_pack.read_json_role(
            public_root, "public", "design_objective", max_bytes=1024 * 1024
        )
        pack_body = selected_pack.read_json_role(
            private_root, "private", "score_pack", max_bytes=1024 * 1024
        )
    except ValueError as exc:
        raise PrivateEvaluationSourceRefused("dual_pack_role") from exc
    if (
        type(accuracy) is not dict
        or type(limits) is not dict
        or type(design) is not dict
        or accuracy.get("producer_digest") != producer_digest
    ):
        raise PrivateEvaluationSourceRefused("dual_producer_pin")
    basis = {
        "schema": DUAL_MEASUREMENT_CONTRACT_SCHEMA,
        "producer_digest": producer_digest,
        "accuracy_definition_sha256": selected_pack.public["accuracy_definition"][
            "sha256"
        ],
        "important_limit_definition_sha256": selected_pack.public[
            "important_limit_definition"
        ]["sha256"],
        "design_objective_sha256": selected_pack.public["design_objective"]["sha256"],
    }
    contract_digest = _sha(_canonical(basis))
    if type(pack_body) is not dict or "pack_digest" not in pack_body:
        raise PrivateEvaluationSourceRefused("dual_score_pack")
    try:
        pack = register_pack(
            {key: value for key, value in pack_body.items() if key != "pack_digest"}
        )
    except DualScoreRefused as exc:
        raise PrivateEvaluationSourceRefused("dual_score_pack") from exc
    if (
        pack != pack_body
        or pack["measurement_contract_digest"] != contract_digest
        or pack["challenge"] != source["challenge"]
        or type(source["physics_contract"]) is not dict
        or pack["physics_contract_digest"]
        != source["physics_contract"].get("definition_digest")
    ):
        raise PrivateEvaluationSourceRefused("dual_score_pack_binding")
    cases = source.get("cases")
    if (
        type(cases) is not list
        or len(cases) != 1
        or type(cases[0]) is not dict
        or cases[0].get("role") not in {"P", "Q"}
        or benchmark.get("common_mask_digest") != _sha(_canonical(cases))
        or benchmark.get("population_role") != cases[0]["role"]
        or type(benchmark.get("models")) is not list
        or len(benchmark["models"]) != 1
        or type(benchmark["models"][0]) is not dict
        or benchmark["models"][0].get("artifact_digest") != entry["entry_id"]
    ):
        raise PrivateEvaluationSourceRefused("dual_common_mask")
    try:
        score(benchmark, pack)
    except DualScoreRefused as exc:
        raise PrivateEvaluationSourceRefused("dual_benchmark") from exc
    detached_measured_model = json.loads(_canonical(measured_model))
    paired = "inference_pair_raw" in graph_originals
    body = {
        "schema": PAIRED_DUAL_MEASUREMENT_SCHEMA if paired else DUAL_MEASUREMENT_SCHEMA,
        "source_receipt_sha256": _sha(evaluation_source_receipt_raw),
        "evaluation_pack_digest": selected_pack.manifest_digest,
        "score_pack_digest": pack["pack_digest"],
        "measurement_contract": basis,
        "measurement_contract_digest": contract_digest,
        "producer_digest": producer_digest,
        "entry_id": entry["entry_id"],
        "state_digest": entry["state_digest"],
        "measured_model_sha256": _sha(_canonical(detached_measured_model)),
        "inference_receipt_sha256": _sha(graph_originals["inference_receipt_raw"]),
        # The graded run's trusted worker evidence: the graph worker-evidence
        # file, or a bundle's canonical served-task evidence.
        "worker_evidence_sha256": _sha(
            graph_originals.get("worker_evidence_raw")
            or graph_originals["bundle_evidence_raw"]
        ),
        **(
            {"inference_pair_sha256": graph_originals["inference_pair_sha256"]}
            if paired
            else {}
        ),
        "benchmark": benchmark,
    }
    raw = _canonical(body)
    if len(raw) > _MAX_RECEIPT_BYTES:
        raise PrivateEvaluationSourceRefused("dual_receipt_too_large")
    return PreparedPrivateDualMeasurement(
        raw, _sha(raw), selected_pack.manifest_digest, detached_measured_model
    )


# Fixed source implementation; this is not a user-selected module registry.
_F02_METHOD = "f02-cold-eight-rich-design.v1"
_F02_ACTIONS = {
    "cool-rect-low": (80, 5),
    "cool-rect-middle": (110, 10),
    "cool-rect-short-high": (140, 5),
    "cool-rect-long-high": (140, 20),
    **{f"cool-rect-near-{power}w": (power, 5) for power in (84, 85, 86, 87)},
}


def _producer_require(ok, code):
    if not ok:
        raise PrivateEvaluationSourceRefused(code)


_GRADED_ORIGINALS = frozenset({"inference_receipt_raw", "worker_evidence_raw"})
#: A bundle (Torch/JAX export) source keeps no worker-evidence file; its trusted
#: inference evidence comes from the served task, canonicalised by retention.
_BUNDLE_ORIGINALS = frozenset(
    {"inference_receipt_raw", "predictions_raw", "bundle_evidence_raw"}
)
BUNDLE_EVIDENCE_SCHEMA = "carbon.lean-recipe.bundle-inference-evidence.v1"
_BUNDLE_EVIDENCE_FIELDS = frozenset(
    {
        "schema",
        "inference_operation",
        "inference_image_id",
        "state_digest",
        "predictions_digest",
    }
)


def graded_original_keys(originals):
    """The graded run's original key set (graph or bundle), or None."""
    if type(originals) is not dict:
        return None
    keys = set(originals) - _PAIR_ORIGINALS - {"timed_query"}
    for graded in (_GRADED_ORIGINALS, _BUNDLE_ORIGINALS):
        if keys == graded:
            return graded
    return None


_PAIR_ORIGINALS = frozenset({"inference_pair_raw", "inference_pair_sha256"})
REPEAT_RULE_SCHEMA = "carbon.paired-repeat-rule.v1"
#: The repeat evidence the grader holds: the same full input tensor, fresh runs.
REPEAT_PLACEMENT = "across_runs_same_position"
_EPS = {"float32": 2.0**-23, "float64": 2.0**-52}


def query_measurement(entry, registration, originals, receipt):
    """Shapes and dtypes of the authenticated query: the graded receipt's own
    measurement, or, for an unmeasured per-case graded receipt, its pinned
    batched timed query's (same model, state and inputs)."""
    from carbon.scoring import bundle_benchmark_core as bundle

    if "measurement" in receipt:
        return receipt["measurement"]
    try:
        return bundle.timed_query_receipt(
            entry, registration, originals.get("timed_query")
        )["measurement"]
    except bundle.BundleBenchmarkRefused as exc:
        raise PrivateEvaluationSourceRefused("dual_native_inference_binding") from exc


def read_inference_repeats(
    originals, *, receipt, worker, measurement=None, procedure="batched_measured"
):
    """The two fresh repeat runs of the graded model: Platform's pinned
    source-free pair, bound to the graded run's recipe, state, inputs, image
    and shapes, and independent of the graded operation. Missing or
    inconsistent pair evidence is typed unavailable, never a candidate verdict.
    """
    from carbon.scoring import inference_pair_evidence as pair_reader

    if not _PAIR_ORIGINALS <= set(originals):
        raise PrivateEvaluationSourceRefused("dual_repeat_evidence_unavailable")
    if procedure == "per_case" and (
        receipt.get("schema") != "carbon.development.bundle-inference.v1"
    ):
        # An identical-procedure repeat needs a per-case graded run.
        raise PrivateEvaluationSourceRefused("dual_repeat_procedure")
    measured = measurement or receipt.get("measurement") or {}
    raw, pin = originals["inference_pair_raw"], originals["inference_pair_sha256"]
    try:
        envelope = json.loads(raw)
        phases = [envelope[name] for name in ("primary", "repeat")]
        expected = {
            "recipe_digest": receipt["recipe_digest"],
            "state_digest": receipt["state_digest"],
            "inputs_digest": receipt["inputs_digest"],
            "inference_image_id": worker["inference_image_id"],
            "operation_ids": [p["worker_operation"] for p in phases],
            "ledger_identities": [p["accounting"]["ledger_identity"] for p in phases],
            "controls_digests": [p["controls_digest"] for p in phases],
            "input_shape": measured["input_shape"],
            "output_shape": measured["output_shape"],
            "input_dtype": measured["input_dtype"],
            "output_dtype": measured["output_dtype"],
        }
        pair = pair_reader.read_inference_pair(
            raw, registered_sha256=pin, expected=expected, procedure=procedure
        )
    except pair_reader.PairEvidenceRefused as exc:
        raise PrivateEvaluationSourceRefused(
            "dual_repeat_evidence_unavailable:" + exc.code
        ) from exc
    except (KeyError, TypeError, ValueError, UnicodeError) as exc:
        raise PrivateEvaluationSourceRefused(
            "dual_repeat_evidence_unavailable"
        ) from exc
    _producer_require(
        worker.get("inference_operation") not in expected["operation_ids"],
        "dual_repeat_not_independent",
    )
    return [list(run) for run in pair.outputs]


def paired_repeat_verdict(originals, *, receipt, worker, outputs, rule, quantity_of):
    """The `paired_repeat` gate: the graded run and two fresh repeats agree.

    `outputs` are the graded run's authenticated flat outputs; the repeats are
    Platform's pinned source-free pair of the same model, image and inputs.
    The tolerance is only the Challenge's own registered rule (`rule`, from its
    important-limit definition), never another Challenge's figure. Missing
    evidence or rule is typed unavailable, never a candidate verdict.
    """
    if not _PAIR_ORIGINALS <= set(originals):
        raise PrivateEvaluationSourceRefused("dual_repeat_evidence_unavailable")
    dtype = (receipt.get("measurement") or {}).get("output_dtype")
    _producer_require(
        type(rule) is dict
        and rule.get("schema") == REPEAT_RULE_SCHEMA
        and rule.get("status") == "REGISTERED"
        and rule.get("comparison") == "abs_diff_le_ulp_scaled"
        and type(rule.get("placements")) is list
        and REPEAT_PLACEMENT in rule["placements"]
        and rule.get("dtype") == dtype
        and dtype in _EPS
        and type(rule.get("floor")) in (int, float)
        and math.isfinite(rule["floor"])
        and rule["floor"] > 0
        and type(rule.get("tolerance_ulp")) is dict
        and set(rule["tolerance_ulp"]) == set(map(quantity_of, range(len(outputs))))
        and all(
            type(k) in (int, float) and math.isfinite(k) and k >= 0
            for k in rule["tolerance_ulp"].values()
        ),
        "dual_repeat_rule_unregistered",
    )
    repeats = read_inference_repeats(originals, receipt=receipt, worker=worker)
    runs = [list(outputs), *repeats]
    _producer_require(
        all(len(run) == len(outputs) for run in runs), "dual_repeat_evidence_shape"
    )
    eps, floor = _EPS[dtype], rule["floor"]
    for i in range(len(runs)):
        for j in range(i + 1, len(runs)):
            for index, (a, b) in enumerate(zip(runs[i], runs[j], strict=True)):
                k = rule["tolerance_ulp"][quantity_of(index)]
                if not abs(a - b) <= k * eps * max(floor, abs(a)):
                    return False
    return True


def _f02_point_measurements(predictions, reference, policy, train_std_c, ceiling_c):
    """Existing native cold-eight A and rich Design over source-owned points.

    No default scales or source acceptance are chosen here. This returns a
    deterministic selection derived from predictions, not a saved commitment.
    Analytic extra energy has no learned-fidelity credit.
    """
    from carbon.scoring import design_fidelity

    ids = sorted(_F02_ACTIONS)
    _producer_require(
        type(policy) is dict
        and type(policy.get("objective")) is dict
        and type(policy.get("components")) is list,
        "dual_f02_policy_mapping",
    )
    _producer_require(
        type(predictions) is list
        and len(predictions) == 8
        and all(type(v) in (int, float) and math.isfinite(v) for v in predictions)
        and type(train_std_c) in (int, float)
        and math.isfinite(train_std_c)
        and train_std_c > 0
        and type(ceiling_c) in (int, float)
        and math.isfinite(ceiling_c),
        "dual_f02_numeric_input",
    )
    _producer_require(
        policy.get("case_ids") == ids
        and policy.get("action_ids") == ids
        and policy.get("objective", {}).get("quantity") == "extra_energy_j"
        and policy["objective"].get("unit") == "J"
        and policy["objective"].get("direction") == "MAXIMIZE"
        and policy["objective"].get("learned") is False,
        "dual_f02_policy_mapping",
    )
    _producer_require(
        type(reference) is dict
        and set(reference) == {"cases", "actions"}
        and type(reference["cases"]) is dict
        and type(reference["actions"]) is dict
        and set(reference["cases"]) == set(ids)
        and set(reference["actions"]) == set(ids),
        "dual_f02_reference_roster",
    )
    _producer_require(
        policy["quantities"]
        == {
            "peak_top_c": {"unit": "C", "learned": True},
            "thermal_margin_c": {"unit": "C", "learned": True},
            "extra_energy_j": {"unit": "J", "learned": False},
        },
        "dual_f02_quantity_credit",
    )
    try:
        design_fidelity.validate_policy(policy)
    except design_fidelity.ReductionRefused as exc:
        raise PrivateEvaluationSourceRefused("dual_f02_policy_mapping") from exc
    components = policy["components"]
    _producer_require(len(components) == 2, "dual_f02_critical_components")
    by_kind = {c["kind"]: c for c in components}
    _producer_require(
        set(by_kind) == {"margin", "response"}
        and by_kind["margin"]["quantity"] == "thermal_margin_c"
        and by_kind["margin"]["cases"] == ids
        and by_kind["response"]["quantity"] == "peak_top_c"
        and by_kind["response"]["pairs"]
        == [
            [f"cool-rect-near-{power}w", f"cool-rect-near-{power+1}w"]
            for power in (84, 85, 86)
        ],
        "dual_f02_critical_components",
    )
    points, actions, errors = {}, {}, []
    for key, prediction in zip(ids, predictions, strict=True):
        row = reference["cases"][key]
        _producer_require(type(row) is dict, "dual_f02_reference_shape")
        peak = design_fidelity.reference_atom(row.get("peak_top_c"), "C")
        margin = design_fidelity.reference_atom(row.get("thermal_margin_c"), "C")
        if "REFERENCE_INFRA" in (peak["reason"], margin["reason"]):
            raise PrivateEvaluationSourceRefused("dual_native_reference_infra")
        _producer_require(
            peak["point"] is not None and margin["point"] is not None,
            "dual_native_reference_unresolved",
        )
        _producer_require(
            margin["point"] == ceiling_c - peak["point"],
            "dual_f02_reference_margin_binding",
        )
        if peak["interval"] is not None or margin["interval"] is not None:
            _producer_require(
                peak["interval"] is not None
                and margin["interval"]
                == [ceiling_c - peak["interval"][1], ceiling_c - peak["interval"][0]],
                "dual_f02_reference_interval_binding",
            )
        energy = (_F02_ACTIONS[key][0] - 20) * _F02_ACTIONS[key][1]
        action = reference["actions"][key]
        _producer_require(
            type(action) is dict
            and action.get("feasibility") in ("FEASIBLE", "INFEASIBLE"),
            "dual_native_reference_unresolved",
        )
        _producer_require(
            (action["feasibility"] == "FEASIBLE") == (peak["point"] <= ceiling_c),
            "dual_f02_reference_verdict_binding",
        )
        objective = design_fidelity.reference_atom(action.get("objective"), "J")
        _producer_require(
            objective["point"] == energy, "dual_f02_analytic_objective_binding"
        )
        errors.append(abs(prediction - peak["point"]) / train_std_c)
        points[key] = {
            "peak_top_c": {"value": prediction, "unit": "C"},
            "thermal_margin_c": {"value": ceiling_c - prediction, "unit": "C"},
        }
        actions[key] = {"objective": {"value": energy, "unit": "J"}}
    feasible = [
        key for key, value in zip(ids, predictions, strict=True) if value <= ceiling_c
    ]
    pick = (
        min(feasible, key=lambda k: (-actions[k]["objective"]["value"], k))
        if feasible
        else None
    )
    near = [error for key, error in zip(ids, errors, strict=True) if "-near-" in key]
    _producer_require(
        all(math.isfinite(v) for v in errors), "dual_native_candidate_numeric_overflow"
    )
    # Divide before summing so large finite forecasts do not overflow the sum.
    loss = max(
        math.fsum(v / 8 for v in errors), math.fsum(v / 4 for v in near), max(errors)
    )
    _producer_require(math.isfinite(loss), "dual_f02_derived_nonfinite")
    model = {
        "artifact_digest": "f02-native-point-reduction",
        "cases": points,
        "actions": actions,
        "selected_action": pick,
    }
    try:
        reduction = design_fidelity.reduce_design(policy, reference, [model])["models"][
            0
        ]
    except ArithmeticError as exc:
        raise PrivateEvaluationSourceRefused(
            "dual_native_candidate_numeric_overflow"
        ) from exc
    return {
        "A": 1 / (1 + loss),
        "model": model,
        "reduction": reduction,
        "selection_basis": "DERIVED_FROZEN_PREDICTION_SELECTION",
    }


def _authenticated_graph_outputs(entry, registration, originals):
    """`(receipt, worker, flat outputs, inference)` of the graded run, read from
    the retained graph or bundle originals and authenticated against the
    custody entry before any native value is reduced."""
    import base64
    import binascii

    from carbon.scoring import bundle_benchmark_core as bundle

    keys = graded_original_keys(originals)
    _producer_require(keys is not None, "dual_native_originals")
    if keys == _BUNDLE_ORIGINALS:
        return _authenticated_bundle_outputs(entry, registration, originals)
    graded_originals = {k: originals[k] for k in _GRADED_ORIGINALS}
    try:
        receipt = bundle._parse_graph_original(
            originals["inference_receipt_raw"], "graph_inference_receipt"
        )
        worker = bundle._parse_graph_original(
            originals["worker_evidence_raw"], "graph_worker_evidence"
        )
        encoded = worker.get("predictions_raw_base64")
        raw = base64.b64decode(encoded.encode("ascii"), validate=True)
        _producer_require(
            base64.b64encode(raw).decode("ascii") == encoded,
            "dual_native_prediction_encoding",
        )
        tensor = bundle._parse_graph_original(
            raw, "graph_predictions", object_required=False
        )
        inference = {
            "recipe_digest": receipt["recipe_digest"],
            "state_digest": receipt["state_digest"],
            "predictions_digest": receipt["predictions_digest"],
            "predictions": tensor,
            "worker_operation": worker["inference_operation"],
            "receipt": receipt,
            **graded_originals,
        }
        # Authenticate originals before reducing native values. These bools are
        # placeholders only for authentication, never emitted as gate verdicts.
        authenticated = bundle.measurement_from_saved_inference(
            entry,
            registration,
            inference,
            gates={name: False for name in registration["mandatory_gates"]},
            # A per-case graded graph reads timing only from its timed query.
            timed_query=originals.get("timed_query"),
        )
    except (
        bundle.BundleBenchmarkRefused,
        KeyError,
        TypeError,
        ValueError,
        AttributeError,
        UnicodeError,
        binascii.Error,
    ) as exc:
        raise PrivateEvaluationSourceRefused("dual_native_inference_binding") from exc
    return receipt, worker, authenticated["cases"][0]["outputs"], inference


def _authenticated_bundle_outputs(entry, registration, originals):
    """The bundle case of `_authenticated_graph_outputs`: the retained
    inference receipt and predictions, bound to the custody entry, and the
    served task's trusted inference evidence."""
    from carbon.scoring import bundle_benchmark_core as bundle

    try:
        receipt = bundle._parse_graph_original(
            originals["inference_receipt_raw"], "bundle_inference_receipt"
        )
        evidence = bundle._parse_graph_original(
            originals["bundle_evidence_raw"], "bundle_inference_evidence"
        )
        predictions = bundle._parse_graph_original(
            originals["predictions_raw"], "bundle_predictions", object_required=False
        )
        _producer_require(
            set(evidence) == _BUNDLE_EVIDENCE_FIELDS
            and evidence["schema"] == BUNDLE_EVIDENCE_SCHEMA
            and evidence["state_digest"] == entry.get("state_digest")
            and evidence["predictions_digest"] == entry.get("prediction_digest")
            and _sha(originals["predictions_raw"]) == entry.get("prediction_digest")
            and is_sha256_digest(evidence["inference_image_id"])
            and bundle.retained_bundle_receipt(
                entry, originals["inference_receipt_raw"]
            )
            and (
                "timed_query" not in originals
                or bundle.retained_bundle_receipt(
                    entry, originals["timed_query"].get("receipt_raw")
                )
            ),
            "dual_native_bundle_binding",
        )
        inference = {
            "recipe_digest": entry["recipe_digest"],
            "state_digest": entry["state_digest"],
            "predictions_digest": entry["prediction_digest"],
            "predictions": predictions,
            "worker_operation": evidence["inference_operation"],
            "receipt": receipt,
        }
        authenticated = bundle.measurement_from_saved_inference(
            entry,
            registration,
            inference,
            gates={name: False for name in registration["mandatory_gates"]},
            timed_query=originals.get("timed_query"),
        )
    except (
        bundle.BundleBenchmarkRefused,
        KeyError,
        TypeError,
        ValueError,
        AttributeError,
        UnicodeError,
    ) as exc:
        raise PrivateEvaluationSourceRefused("dual_native_inference_binding") from exc
    return receipt, evidence, authenticated["cases"][0]["outputs"], inference


def _produce_f02_cold(
    selected,
    public_root,
    private_root,
    entry,
    job,
    registration,
    references,
    originals,
    source_raw,
):

    from carbon.scoring import bundle_benchmark_core as bundle

    _producer_require(type(selected) is EvaluationPackSnapshot, "selected_pack_missing")
    roles = {}
    for audience, names, root in (
        (
            "public",
            ("accuracy_definition", "important_limit_definition", "design_objective"),
            public_root,
        ),
        (
            "private",
            ("case_bank", "reference_rows", "solver_evidence", "score_pack"),
            private_root,
        ),
    ):
        for name in names:
            try:
                roles[name] = selected.read_json_role(
                    root, audience, name, max_bytes=1024 * 1024
                )
            except ValueError as exc:
                raise PrivateEvaluationSourceRefused(
                    "dual_native_role_unavailable:" + name
                ) from exc
    accuracy, limits, design = (
        roles[k]
        for k in (
            "accuracy_definition",
            "important_limit_definition",
            "design_objective",
        )
    )
    _producer_require(
        all(type(v) is dict for v in (accuracy, limits, design)),
        "dual_native_definition_shape",
    )
    _producer_require(
        all(v.get("method") == _F02_METHOD for v in (accuracy, limits, design))
        and accuracy.get("schema") == "carbon.scoring.f02-cold-accuracy.v1"
        and limits.get("schema") == "carbon.scoring.f02-cold-limits.v1"
        and design.get("schema") == "carbon.scoring.f02-cold-design.v1",
        "dual_native_definition_method",
    )
    _producer_require(limits.get("maximum_c") == 95, "dual_f02_fixed_cold_limit")
    identity = _sha(Path(__file__).read_bytes())
    _producer_require(
        accuracy.get("producer_digest") == identity
        and accuracy.get("train_digest") == entry.get("train_digest"),
        "dual_native_producer_or_train_binding",
    )
    source = _parse_pack_source(source_raw)
    _producer_require(
        type(source.get("cases")) is list
        and len(source["cases"]) == 1
        and type(source["cases"][0]) is dict,
        "dual_native_complete_batch_required",
    )
    _producer_require(
        type(references) is list
        and len(references) == 1
        and type(registration) is dict
        and len(registration.get("cases", [])) == 1,
        "dual_native_complete_batch_required",
    )
    case_bank = roles["case_bank"]
    truth = roles["solver_evidence"]
    ids = sorted(_F02_ACTIONS)
    _producer_require(
        type(case_bank) is dict
        and case_bank.get("schema") == "carbon.scoring.f02-cold-case-bank.v1"
        and case_bank.get("context")
        == {
            "coolant_c": 30,
            "h_w_m2_k": 2500,
            "initial_c": 40,
            "left_source_fraction": 0.5,
            "waveform": "rectangular",
        }
        and case_bank.get("action_ids") == ids
        and case_bank.get("actions") == {k: list(v) for k, v in _F02_ACTIONS.items()}
        and case_bank.get("inputs_digest")
        == entry.get("roles", {}).get("inputs", {}).get("sha256")
        and type(truth) is dict
        and truth.get("schema") == "carbon.scoring.f02-cold-reference.v1"
        and is_sha256_digest(truth.get("source_acceptance_digest"))
        and roles["reference_rows"] == references,
        "dual_native_source_mapping",
    )
    _producer_require(
        source["evaluation_pack_digest"] == selected.manifest_digest
        and source["registration_digest"] == registration.get("registration_digest")
        and source["cases"][0]["query_sha256"] == case_bank["inputs_digest"]
        and source["cases"][0]["reference_row_sha256"]
        == _sha(_canonical(references[0]))
        and source["cases"][0]["reference_status"] == references[0].get("status"),
        "dual_native_source_original_binding",
    )
    for field in ("challenge", "challenge_version", "interface_digest", "train_digest"):
        _producer_require(
            source.get(field) == entry.get(field) == job.get(field),
            "dual_native_identity",
        )
    acceptance = truth.get("source_acceptance")
    _producer_require(
        type(acceptance) is dict
        and truth["source_acceptance_digest"] == _sha(_canonical(acceptance)),
        "dual_native_acceptance_unavailable",
    )
    judgement = acceptance.get("judgement")
    _producer_require(
        type(judgement) is dict
        and judgement.get("schema") == "carbon.f02-readiness.judgement.v1",
        "dual_native_acceptance_unavailable",
    )
    family = judgement.get("family_acceptance", {})
    _producer_require(
        type(family) is dict
        and family.get("status") == "ACCEPTED_FOR_DEVELOPMENT_BANK"
        and type(family.get("primaries")) is int
        and family["primaries"] > 0
        and family.get("primaries_passing") == family["primaries"]
        and family.get("baseline_checks_passing")
        == family.get("baseline_checks_expected")
        == 12,
        "dual_native_acceptance_unavailable",
    )
    _producer_require(
        is_sha256_digest(acceptance.get("manifest_sha256"))
        and acceptance.get("bands_sha256") == limits.get("bands_sha256")
        and is_sha256_digest(acceptance.get("bands_sha256")),
        "dual_native_acceptance_binding",
    )
    _producer_require(
        selected.challenge_id == source["challenge"]
        and selected.challenge_version == source["challenge_version"]
        and selected.public["train"]["sha256"] == entry["train_digest"]
        and source["job_digest"]
        == job.get("job_digest")
        == registration.get("job_digest"),
        "dual_native_identity",
    )
    try:
        physics = physics_contract_identity(job["physics_contract"])
    except (BenchmarkRefused, KeyError, TypeError, ValueError) as exc:
        raise PrivateEvaluationSourceRefused("dual_native_physics_binding") from exc
    _producer_require(
        source["physics_contract"] == physics, "dual_native_physics_binding"
    )
    reference = truth.get("rich_reference")
    _producer_require(type(reference) is dict, "dual_native_reference_unavailable")
    if references[0].get("status") != "RESOLVED":
        raise PrivateEvaluationSourceRefused(
            "dual_native_reference_infra"
            if references[0].get("status") == "FAILED_INFRA"
            else "dual_native_reference_unresolved"
        )
    _producer_require(
        references[0].get("outputs")
        == [
            reference.get("cases", {}).get(k, {}).get("peak_top_c", {}).get("value")
            for k in ids
        ],
        "dual_native_reference_flat_binding",
    )
    for key in ids:
        primary = (
            reference.get("cases", {}).get(key, {}).get("peak_top_c", {}).get("value")
        )
        observables = judgement.get("observables", {})
        values = [
            observables.get(key + "-" + suffix, {}).get("peak_top_c")
            for suffix in ("primary", "mesh2", "dt0.5")
        ]
        _producer_require(
            all(type(v) in (int, float) and math.isfinite(v) for v in values)
            and values[0] == primary
            and judgement.get("rung_comparisons", {}).get(key, {}).get("pass") is True
            and len({v <= limits.get("maximum_c") for v in values}) == 1,
            "dual_native_reference_unresolved",
        )
    receipt, worker, values, inference = _authenticated_graph_outputs(
        entry, registration, originals
    )
    _producer_require(
        inference["receipt"]["measurement"]["output_shape"] == [8, 1]
        and inference["receipt"]["measurement"]["input_shape"] == [8, 2],
        "dual_native_tensor_shape",
    )
    native = _f02_point_measurements(
        values,
        reference,
        design.get("policy"),
        accuracy.get("train_peak_std_c"),
        limits.get("maximum_c"),
    )
    gates = limits.get("mandatory_gates")
    _producer_require(
        type(gates) is list
        and gates == registration["mandatory_gates"]
        and set(gates)
        == {"finite_peak", "paired_repeat", "reference_acceptance", "verified_pick"},
        "dual_native_gate_contract",
    )
    # The graded run plus Platform's two fresh repeats, under f02's own rule.
    repeated = paired_repeat_verdict(
        originals,
        receipt=receipt,
        worker=worker,
        outputs=values,
        rule=limits.get("paired_repeat"),
        quantity_of=lambda _index: "peak_top_c",
    )
    reduction = native["reduction"]
    unsafe = reduction["candidate_selection_outcome"] == "SELECTED_PROVEN_INFEASIBLE"
    verified = reduction["candidate_selection_outcome"] == "VERIFIED_FEASIBLE"
    native_gates = {
        name: (
            verified
            if name == "verified_pick"
            else repeated if name == "paired_repeat" else True
        )
        for name in gates
    }
    measured = bundle.measurement_from_saved_inference(
        entry, registration, inference, gates=native_gates
    )
    pack = roles["score_pack"]
    basis = {
        "schema": DUAL_MEASUREMENT_CONTRACT_SCHEMA,
        "producer_digest": identity,
        **{
            name + "_sha256": selected.public[name]["sha256"]
            for name in (
                "accuracy_definition",
                "important_limit_definition",
                "design_objective",
            )
        },
    }
    _producer_require(
        type(pack) is dict
        and pack.get("scope") == "PUBLIC_DEVELOPMENT"
        and pack.get("value_weight") == 0.5
        and pack.get("measurement_contract_digest") == _sha(_canonical(basis))
        and pack.get("hard_gates") == gates,
        "dual_native_score_pack",
    )
    _producer_require(
        [c["metric"] for c in pack["legs"]["A"]["components"]]
        == ["peak_physics_benefit"]
        and [c["metric"] for c in pack["legs"]["D"]["components"]]
        == ["rich_design_benefit"],
        "dual_native_score_metrics",
    )
    d = reduction["registered_D"]
    state = "RESOLVED" if d is not None else "REFERENCE_UNRESOLVED"
    outcome = "VERIFIED_FEASIBLE" if verified else "MISSED_OPPORTUNITY"
    if all(v["feasibility"] == "INFEASIBLE" for v in reference["actions"].values()):
        outcome = "NONE_FEASIBLE"
    benchmark = {
        "schema": "carbon.scoring.dual-benchmark-input.v1",
        "scope": pack["scope"],
        "challenge": "f02",
        "physics_contract_digest": pack["physics_contract_digest"],
        "measurement_contract_digest": pack["measurement_contract_digest"],
        "population_role": source["cases"][0]["role"],
        "common_mask_digest": _sha(_canonical(source["cases"])),
        "models": [
            {
                "artifact_digest": entry["entry_id"],
                "gates": {
                    k: ("PASS" if v else "FAIL") for k, v in native_gates.items()
                },
                "measurements": {
                    "peak_physics_benefit": {
                        "status": "RESOLVED",
                        "value": native["A"],
                        "unit": "1",
                    },
                    "rich_design_benefit": {"status": state, "value": d, "unit": "1"},
                },
                "decision_outcome": outcome,
            }
        ],
    }
    _producer_require(
        not unsafe or "FAIL" in benchmark["models"][0]["gates"].values(),
        "dual_native_unsafe_gate_missing",
    )
    score(benchmark, pack)
    return measured, benchmark, identity
