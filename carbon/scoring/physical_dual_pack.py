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

The minimums are the registered baseline's own leg scores measured on that
platform (Validator, 2026-10-19). Two builds make them: a ``calibration`` pack
(no minimums, its own evaluation version) grades the registered baseline's
normal rebuild on the judge image; the per-image pack then takes that run's
bound legs as its minimums (``baseline_minimums``) and records the run as a
minimum source that never contends. The per-image pack's platform is never a
caller value: it is the calibration pack's, which grading verified against the
baseline run's retained ``inference_image_id`` (the binding exists only if that
check passed); a caller-supplied image that differs is refused. Before any run
no retained evidence exists, so the calibration pack's image is checked at its
first grading. Without either, a pack keeps the
adapter's historical registered minimums under its historical version.

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
import math
import os
import subprocess
import sys
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


#: Every BLAS/OpenMP pool a numpy build may use, pinned to one thread.
_SINGLE_THREAD = {
    name: "1"
    for name in (
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "VECLIB_MAXIMUM_THREADS",
        "NUMEXPR_NUM_THREADS",
    )
}
_CHILD = (
    "import importlib, json, sys\n"
    "sys.path.insert(0, sys.argv[1])\n"
    "module, name = sys.argv[2].split(':')\n"
    "kwargs = json.loads(sys.stdin.read())\n"
    "result = getattr(importlib.import_module(module), name)(**kwargs)\n"
    "sys.stdout.write(json.dumps(result, allow_nan=False))\n"
)


def single_threaded(target, **kwargs):
    """``module:function(**kwargs)`` run in a child Python whose BLAS and
    OpenMP pools are pinned to one thread from start-up (Validator,
    2026-10-20): linear algebra in a baseline must not depend on the host's
    core count. Arguments and result are JSON; floats round-trip exactly."""
    root = str(Path(__file__).resolve().parents[2])
    done = subprocess.run(
        [sys.executable, "-c", _CHILD, root, target],
        input=json.dumps(kwargs, allow_nan=False),
        capture_output=True,
        text=True,
        env={**os.environ, **_SINGLE_THREAD},
        check=False,
    )
    if done.returncode != 0:
        raise RuntimeError("single-threaded baseline failed: " + done.stderr[-2000:])
    return json.loads(done.stdout)


def producer_digest(adapter):
    """The producer's identity: the bytes of every file it executes, with
    CRLF read as LF (Validator, 2026-10-20), so a Windows checkout of the
    same commit has the same identity."""
    here = Path(__file__).parent
    names = sorted({*_SHARED_FILES, *adapter.FILES})
    return sha(
        canonical(
            {
                name: sha((here / name).read_bytes().replace(b"\r\n", b"\n"))
                for name in names
            }
        )
    )


def input_names(adapter):
    """The Challenge's ordered numeric input names (its adapter's own, or the
    physical public interface's)."""
    own = getattr(adapter, "input_names", None)
    if own is not None:
        return own()
    from carbon.challenge_kit import physical_public_train

    return physical_public_train.numeric_interface_document(adapter.CHALLENGE)[
        "input_names"
    ]


def reference_mask(bank):
    """Which bank rows carry a measured reference (``reference_present``,
    REFERENCE_PRESENT_MASK_INTERFACE_20261020), checked against the values.

    A bank without the key is all-present (Motor, Cooling, F02, F08). The mask
    is authoritative; an absent row's values are the NaN sentinel. A NaN in a
    present row, or a finite value in an absent one, refuses
    (``reference_invalid``): a reference is never filled or guessed.
    """
    references = bank["references"]
    mask = bank.get("reference_present")
    if mask is None:
        mask = (True,) * len(references)
    if type(mask) not in (tuple, list) or len(mask) != len(references):
        raise ValueError("reference_invalid")
    for present, row in zip(mask, references, strict=True):
        values = [float(v) for v in row]
        if type(present) is not bool or (
            all(math.isfinite(v) for v in values)
            if present is False
            else not all(math.isfinite(v) for v in values)
        ):
            raise ValueError("reference_invalid")
        if present is False and not all(math.isnan(v) for v in values):
            raise ValueError("reference_invalid")
    return tuple(mask)


def flat_references(bank):
    """The bank's references, flattened; an absent row is JSON null."""
    width = len(bank["references"][0])
    return [
        v
        for present, row in zip(reference_mask(bank), bank["references"], strict=True)
        for v in ([float(x) for x in row] if present else [None] * width)
    ]


def bank_rows(bank, interface_names):
    """Data Collection's bank as measurement rows, in its declared order. A
    row without a measured reference carries ``reference`` None: it never
    enters a measure as truth."""
    rows = []
    for case_id, cohort, record, inputs, reference, present in zip(
        bank["case_ids"],
        bank["cohorts"],
        bank["reference_records"],
        bank["inputs"],
        bank["references"],
        reference_mask(bank),
        strict=True,
    ):
        row = {
            "case_id": case_id,
            "cohort": cohort,
            "record": record,
            "inputs": dict(
                zip(interface_names, (float(v) for v in inputs), strict=True)
            ),
            "reference": [float(v) for v in reference] if present else None,
            "reference_present": present,
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
                # Only a masked bank adds the mask, so unmasked digests stay.
                **(
                    {"reference_present": list(reference_mask(bank))}
                    if "reference_present" in bank
                    else {}
                ),
            }
        )
    )


def _identities(bank, physics_digest):
    """The registered reference identity: which solvers and counted evidence
    produced the bank's references, and the physics scope they apply to."""
    from carbon.scoring import benchmark_evidence as bench

    images = sorted(
        {
            (image if type(image) is str else canonical(image).decode("utf-8").strip())
            for record in bank["reference_records"]
            if (image := record.get("image"))
        }
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


BASELINE_ROLE = "BASELINE_LEG_MINIMUM_SOURCE_NOT_A_CONTENDER"


class Variant:
    """One adapter for another version of its Challenge: its own ``VERSION``,
    evaluation version and case id; measurement and producer files are the
    adapter module's own."""

    def __init__(self, module, version, evaluation_version, case_id):
        self._module = module
        self.VERSION = version
        self.EVALUATION_VERSION = evaluation_version
        self.CASE_ID = case_id

    def pack_documents(self, **kwargs):
        return pack_documents(self, **kwargs)

    def write_development_pack(self, root, **platform):
        return write_development_pack(self, root, **platform)

    def produce(self, **kwargs):
        return produce(self, **kwargs)

    def __getattr__(self, name):
        return getattr(self._module, name)


def versioned(module, version):
    """The adapter for exactly ``version`` of ``module``'s Challenge, or None.
    ``module.VERSIONS`` maps each registered version to its evaluation version
    and case id; there is no default version."""
    entry = module.VERSIONS.get(version) if type(version) is str else None
    if entry is None:
        return None
    evaluation_version, case_id = entry
    if version == module.VERSION:
        return module
    return Variant(module, version, evaluation_version, case_id)


def _evaluation_version(adapter, platform, minimums):
    if minimums is None:
        return adapter.EVALUATION_VERSION
    image = platform["inference_image_id"][7:19]
    mode = "calibration" if minimums == "calibration" else "judge"
    return f"{adapter.EVALUATION_VERSION}-{mode}-{image}"


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
    minimums=None,
):
    """Every document the producer owns for one Challenge, as exact bytes.

    ``bank`` is ``physical_pack.development_bank``; ``physics`` the pack's
    physics contract in its ``{version, definition}`` envelope; the raw bytes
    are the pack's public interface, TRAIN, important-limit and
    design-objective roles; ``platform`` is ``leg_minimum_platform(...)``.
    ``minimums`` is None (the adapter's historical registered minimums),
    ``"calibration"`` (none) or ``baseline_minimums(...)``.
    """
    from carbon.scoring import benchmark_evidence as bench
    from carbon.scoring import dual_score
    from carbon.scoring.private_evaluation_source import (
        DUAL_MEASUREMENT_CONTRACT_SCHEMA,
    )

    physics_digest = bench.physics_contract_identity(physics)["definition_digest"]
    names = input_names(adapter)
    definition = {
        **adapter.definition(bank=bank, train_raw=train_raw),
        "challenge": {"id": adapter.CHALLENGE, "version": adapter.VERSION},
        "scope": "PUBLIC_DEVELOPMENT_EXPOSED_BANK",
        "producer_digest": producer_digest(adapter),
        "train_digest": sha(train_raw),
        "bank_digest": bank_digest(bank),
        "leg_minimum_platform": leg_minimum_platform(**platform),
    }
    if minimums == "calibration":
        definition["leg_minimum_mode"] = "calibration"
    elif minimums is not None:
        definition["leg_minimum_mode"] = "baseline_run"
        definition["leg_minimum_source"] = minimums["source"]
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
    if minimums is not None:
        applied = {
            **applied,
            "legs": {
                leg: {
                    **body,
                    "minimum": (
                        minimums["legs"][leg]
                        if minimums != "calibration" and leg in adapter.MINIMUM_LEGS
                        else None
                    ),
                }
                for leg, body in applied["legs"].items()
            },
        }
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
        "outputs": flat_references(bank),
        # Only a masked bank adds the mask, so unmasked reference rows stay.
        **(
            {"reference_present": list(reference_mask(bank))}
            if not all(reference_mask(bank))
            else {}
        ),
        # The measured solves only: a row without a reference has no wall time.
        "elapsed_s": float(
            sum(
                float(r["wall_s"])
                for r, present in zip(
                    bank["reference_records"], reference_mask(bank), strict=True
                )
                if present
            )
        ),
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
                "evaluation_version": _evaluation_version(adapter, platform, minimums),
                "trusted_job": trusted_job,
                "benchmark_registration": registration,
            }
        ),
    }


def baseline_minimums(adapter, binding_raw, *, calibration_documents):
    """The per-image leg minimums: the registered baseline's bound legs from
    its graded run under exactly this producer's calibration pack.

    ``binding_raw`` is the run's retained private-evaluation binding; the
    calibration documents are recomputed for the same platform, so a binding
    from any other pack, producer, measurement or image is refused.
    """
    calibration = json.loads(calibration_documents["score_pack"])
    definition = json.loads(calibration_documents["accuracy_definition"])
    try:
        bound = json.loads(binding_raw)
        row = bound["scoring"]["models"][0]
        ok = (
            bound.get("status") == "BOUND_DEVELOPMENT_ONLY"
            and bound.get("official_score") is False
            and bound.get("measurement_contract_digest")
            == calibration["measurement_contract_digest"]
            and bound.get("producer_digest") == definition["producer_digest"]
            and bound.get("score_result_digest") == sha(canonical(bound["scoring"]))
            and len(bound["scoring"]["models"]) == 1
            and row["status"] == "SCORED_DEVELOPMENT_CANDIDATE"
            and row["artifact_digest"] == bound["entry_id"]
            and all(type(row["legs"][leg]) is float for leg in ("A", "D"))
        )
    except (KeyError, TypeError, ValueError, IndexError) as exc:
        raise ValueError("baseline binding is not a scored calibration run") from exc
    if not ok:
        raise ValueError("baseline binding is not a scored calibration run")
    return {
        "legs": {leg: row["legs"][leg] for leg in ("A", "D")},
        "source": {
            "role": BASELINE_ROLE,
            "binding_sha256": sha(binding_raw),
            "entry_id": bound["entry_id"],
            "state_digest": bound["state_digest"],
            "score_result_digest": bound["score_result_digest"],
            "calibration_measurement_contract_digest": calibration[
                "measurement_contract_digest"
            ],
            **definition["leg_minimum_platform"],
        },
    }


def minimum_source_entry_ids(accuracy_definition):
    """The entries that set a pack's leg minimums and so never contend: the
    KOTH comparator's ``minimum_source_entry_ids`` for this pack."""
    source = (accuracy_definition or {}).get("leg_minimum_source")
    if source is None:
        return []
    if type(source) is not dict or source.get("role") != BASELINE_ROLE:
        raise ValueError("leg minimum source is malformed")
    return [source["entry_id"]]


def _calibration_platform(adapter, calibration_root, binding_raw, inputs):
    """The platform of the calibration pack the baseline was graded under,
    and its recomputed documents, or a refusal.

    The pack directory must seal to the binding's ``evaluation_pack_digest`` and
    hold exactly this producer's calibration documents for its own recorded
    platform."""
    from carbon.challenge_validator.evaluation_pack import prepare_pack

    calibration_root = Path(calibration_root)
    sealed = prepare_pack(
        calibration_root,
        MANIFEST_NAME,
        public_root=calibration_root,
        private_root=calibration_root,
        challenge_id=adapter.CHALLENGE,
        challenge_version=adapter.VERSION,
    ).snapshot
    try:
        bound = json.loads(binding_raw)
    except ValueError as exc:
        raise ValueError("baseline binding is not a scored calibration run") from exc
    if type(bound) is not dict or bound.get("evaluation_pack_digest") != (
        sealed.manifest_digest
    ):
        raise ValueError("baseline binding was not graded under this calibration pack")
    draft = json.loads((calibration_root / MANIFEST_NAME).read_bytes())
    stored = {
        role: (calibration_root / draft[scope][role]["path"]).read_bytes()
        for scope, role in (
            ("public", "accuracy_definition"),
            ("private", "score_pack"),
        )
    }
    platform = json.loads(stored["accuracy_definition"]).get("leg_minimum_platform")
    if type(platform) is not dict:
        raise ValueError("calibration pack records no grading platform")
    documents = pack_documents(
        adapter,
        minimums="calibration",
        **{**inputs, "platform": leg_minimum_platform(**platform)},
    )
    if any(documents[role] != stored[role] for role in stored):
        raise ValueError("calibration pack is not this producer's calibration")
    return platform, documents


def write_development_pack(
    adapter,
    root,
    *,
    inference_image_id=None,
    device_class=None,
    calibration=False,
    baseline_binding_raw=None,
    calibration_pack_root=None,
):
    """Write the Challenge's complete DEVELOPMENT pack under a new, empty ``root``.

    Data Collection's ``physical_pack`` writes the public roles and the exposed
    bank; this producer's documents replace accuracy_definition,
    reference_rows and solver_evidence and add score_pack and
    source_registration. ``root`` serves as the pack, public and private root;
    the draft manifest is ``root / MANIFEST_NAME``, which the receiver seals.
    The pack's physics role is the receiver material's own; it must be in its
    ``{version, definition}`` envelope (and equal the adapter's generated
    contract when the adapter generates it). ``calibration`` writes the
    minimum-free calibration pack for ``inference_image_id``;
    ``baseline_binding_raw`` with ``calibration_pack_root`` writes the per-image
    pack from the baseline's graded calibration run, its platform derived from
    that run (a differing ``inference_image_id`` or ``device_class`` refuses).
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
    inputs = {
        "bank": physical_pack.development_bank(adapter.CHALLENGE, adapter.VERSION),
        "physics": physics,
        "interface_raw": public["interface"],
        "train_raw": public["train"],
        "limits_raw": public["important_limit_definition"],
        "objective_raw": public["design_objective"],
    }
    if calibration and baseline_binding_raw is not None:
        raise ValueError("a calibration pack takes no baseline binding")
    if calibration and getattr(adapter, "CALIBRATION_ADAPTER", adapter) is not adapter:
        raise ValueError("calibrate with the default adapter")
    minimums = "calibration" if calibration else None
    if baseline_binding_raw is not None:
        if calibration_pack_root is None:
            raise ValueError("a baseline binding needs its calibration pack")
        platform, calibration_documents = _calibration_platform(
            getattr(adapter, "CALIBRATION_ADAPTER", adapter),
            calibration_pack_root,
            baseline_binding_raw,
            inputs,
        )
        if (
            inference_image_id is not None
            and inference_image_id != platform["inference_image_id"]
        ) or (device_class is not None and device_class != platform["device_class"]):
            raise ValueError("inference platform differs from the baseline run's")
        minimums = baseline_minimums(
            adapter,
            baseline_binding_raw,
            calibration_documents=calibration_documents,
        )
    else:
        platform = leg_minimum_platform(
            inference_image_id, device_class or DEVICE_CLASS
        )
    documents = pack_documents(adapter, minimums=minimums, platform=platform, **inputs)
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


def add_builder_arguments(parser):
    parser.add_argument("root", type=Path, help="new or empty pack directory")
    parser.add_argument(
        "--inference-image",
        help=(
            "sha256 digest of the judge inference image the leg minimums belong "
            "to: the inference_image_id retention records for tasks graded by "
            "this receiver (its bundle or worker evidence). Required except with "
            "--baseline-binding, which derives it from the baseline run and "
            "refuses a differing value"
        ),
    )
    parser.add_argument("--device-class", default=None)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--calibration",
        action="store_true",
        help="write the minimum-free calibration pack for the baseline run",
    )
    mode.add_argument(
        "--baseline-binding",
        type=Path,
        help=(
            "the registered baseline's private-evaluation-binding.json from its "
            "graded calibration run; writes the per-image pack"
        ),
    )
    parser.add_argument(
        "--calibration-pack",
        type=Path,
        help="the calibration pack directory the baseline was graded under",
    )


def builder_options(args):
    return {
        "inference_image_id": args.inference_image,
        "device_class": args.device_class,
        "calibration": args.calibration,
        "baseline_binding_raw": (
            args.baseline_binding.read_bytes() if args.baseline_binding else None
        ),
        "calibration_pack_root": args.calibration_pack,
    }


def _inputs(
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
    """Validate one retained model's evidence against the selected pack and gather what
    the measurement takes, or a typed refusal."""
    import numpy as np

    from carbon.development_session.bundle_construction_worker import _tensors
    from carbon.scoring import private_evaluation_source as source_module

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
        references[0].get("outputs") == flat_references(bank),
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
        originals,
        receipt=receipt,
        worker=worker,
        measurement=measurement,
        procedure=definition.get("paired_repeat_procedure", "batched_measured"),
    )
    require(all(len(r) == n * width for r in repeats), "dual_repeat_evidence_shape")

    return {
        "refused": refused,
        "require": require,
        "roles": roles,
        "definition": definition,
        "train_raw": train_raw,
        "source": source,
        "values": values,
        "repeats": repeats,
        "inference": inference,
        "n": n,
        "width": width,
        "identity": identity,
    }


def _timed_agreement(timed_query, graded_total, step, total_of, rows_of, size, refused):
    """The timed batched query's outputs, scored through the same adapter, must
    land within ``step`` of the graded total (Validator, 2026-10-20). Outputs
    that cannot be read or scored disagree; a graded run with no total (a
    failed gate) has no speed to protect."""
    if graded_total is None:
        return
    if type(step) not in (int, float) or not math.isfinite(step) or step <= 0:
        raise refused("timed_query_step_unavailable")
    raw = timed_query.get("predictions_raw") if type(timed_query) is dict else None
    try:
        flat = _flat_values(json.loads(raw))
        if len(flat) != size:
            raise ValueError("timed query shape")
        timed_total = total_of(rows_of(flat))
    except (TypeError, ValueError, KeyError) as exc:
        raise refused("timed_query_disagrees") from exc
    if timed_total is None or not abs(timed_total - graded_total) < step:
        raise refused("timed_query_disagrees")


def _flat_values(value):
    if type(value) is list:
        return [v for item in value for v in _flat_values(item)]
    if type(value) in (int, float) and math.isfinite(value):
        return [float(value)]
    raise ValueError("timed query value")


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
    timing_step,
):
    """The dual benchmark input for one retained model, or a typed refusal.

    ``timing_step`` is the Ladder step, max(eta, the registered rebuild noise):
    a separately timed batched query must score within it of the graded run,
    or the whole evaluation refuses (``timed_query_disagrees``), so speed is
    never measured on outputs that were not graded."""
    from carbon.scoring import bundle_benchmark_core as bundle
    from carbon.scoring.dual_score import score

    ctx = _inputs(
        adapter,
        selected=selected,
        public_root=public_root,
        private_root=private_root,
        entry=entry,
        job=job,
        registration=registration,
        references=references,
        originals=originals,
        source_raw=source_raw,
        bank=bank,
        interface_names=interface_names,
    )
    refused, require = ctx["refused"], ctx["require"]
    roles = ctx["roles"]
    definition, train_raw, source = ctx["definition"], ctx["train_raw"], ctx["source"]
    values, repeats, inference = ctx["values"], ctx["repeats"], ctx["inference"]
    n, width, identity = ctx["n"], ctx["width"], ctx["identity"]

    def rows_of(flat):
        return [list(flat[i * width : (i + 1) * width]) for i in range(n)]

    pack = roles["score_pack"]
    gates = list(pack.get("hard_gates", []))

    def leg(value):
        if value is None:
            return {"status": "CANDIDATE_INVALID", "value": None, "unit": "1"}
        return {"status": "RESOLVED", "value": value, "unit": "1"}

    def benchmark_of(outputs, repeat_rows):
        """One set of outputs measured by this adapter and reduced to the
        dual benchmark input, the graded run's or the timed run's alike."""
        try:
            measured = adapter.measure(
                bank_rows=bank_rows(bank, interface_names),
                outputs=outputs,
                repeats=repeat_rows,
                definition=definition,
                limits=roles["important_limit_definition"],
                objective=roles["design_objective"],
                train_raw=train_raw,
                names=interface_names,
            )
        except adapter.Refused as exc:
            raise refused("dual_native_" + exc.code) from exc
        require(
            gates == registration["mandatory_gates"] == list(measured["gates"]),
            "dual_native_gate_contract",
        )
        return measured, {
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

    graded_rows = rows_of(values)
    measured, benchmark = benchmark_of(graded_rows, [rows_of(r) for r in repeats])
    graded_total = score(benchmark, pack)["models"][0]["score"]
    timed_query = originals.get("timed_query")
    if timed_query is not None:
        _timed_agreement(
            timed_query,
            graded_total,
            timing_step,
            lambda timed_rows: score(
                benchmark_of(timed_rows, [timed_rows, timed_rows])[1], pack
            )["models"][0]["score"],
            rows_of,
            n * width,
            refused,
        )
    model = bundle.measurement_from_saved_inference(
        entry,
        registration,
        inference,
        gates={k: measured["gates"][k] for k in gates},
        timed_query=originals.get("timed_query"),
    )
    return model, benchmark, identity


def bootstrap_total_se(
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
    exam_key,
    resamples=200,
):
    """Standard error of one retained model's exam total: a case bootstrap.

    The bank's rows are resampled with replacement (inside each cohort, which the adapters'
    measurements require), the model's saved outputs and its two repeats are taken for the
    same rows, the total is recomputed through the adapter's own ``measure`` and the pack's
    score, and the SE is the standard deviation of the totals. The seed is the first 8
    bytes of the exam key. A resample the adapter cannot measure makes the whole SE
    unavailable for this Challenge (a typed refusal), never an estimate from fewer.
    """
    import numpy as np

    from carbon.scoring.dual_score import score

    ctx = _inputs(
        adapter,
        selected=selected,
        public_root=public_root,
        private_root=private_root,
        entry=entry,
        job=job,
        registration=registration,
        references=references,
        originals=originals,
        source_raw=source_raw,
        bank=bank,
        interface_names=interface_names,
    )
    refused, definition, source = ctx["refused"], ctx["definition"], ctx["source"]
    roles, n, width = ctx["roles"], ctx["n"], ctx["width"]
    if type(exam_key) is not str or not exam_key.startswith("sha256:"):
        raise refused("bootstrap_exam_key_invalid")
    try:
        seed = int.from_bytes(bytes.fromhex(exam_key[7:])[:8], "big")
    except ValueError:
        raise refused("bootstrap_exam_key_invalid") from None
    rows = bank_rows(bank, interface_names)

    def rows_of(flat):
        return [list(flat[i * width : (i + 1) * width]) for i in range(n)]

    outputs = rows_of(ctx["values"])
    repeats = [rows_of(r) for r in ctx["repeats"]]
    by_cohort = {}
    for index, row in enumerate(rows):
        by_cohort.setdefault(row["cohort"], []).append(index)
    pack, totals = roles["score_pack"], []
    generator = np.random.Generator(np.random.PCG64(seed))
    for _ in range(resamples):
        order = []
        for indexes in by_cohort.values():
            order.extend(
                int(i)
                for i in generator.choice(indexes, size=len(indexes), replace=True)
            )
        try:
            measured = adapter.measure(
                bank_rows=[rows[i] for i in order],
                outputs=[outputs[i] for i in order],
                repeats=[[repeat[i] for i in order] for repeat in repeats],
                definition=definition,
                limits=roles["important_limit_definition"],
                objective=roles["design_objective"],
                train_raw=ctx["train_raw"],
                names=interface_names,
            )
        except adapter.Refused as exc:
            raise refused("bootstrap_unmeasurable:" + exc.code) from exc
        gates = list(pack.get("hard_gates", []))
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
                        METRICS["A"]: _leg(measured["A"]),
                        METRICS["D"]: _leg(measured["D"]),
                    },
                    "decision_outcome": measured["decision_outcome"],
                }
            ],
        }
        total = score(benchmark, pack)["models"][0]["score"]
        if type(total) not in (int, float) or not math.isfinite(total):
            raise refused("bootstrap_total_unscored")
        totals.append(float(total))
    return float(np.std(np.asarray(totals), ddof=1)) if len(totals) > 1 else 0.0


def _leg(value):
    if value is None:
        return {"status": "CANDIDATE_INVALID", "value": None, "unit": "1"}
    return {"status": "RESOLVED", "value": value, "unit": "1"}
