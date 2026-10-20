"""Public roles of the normal-construction DEVELOPMENT evaluation pack.

The receiver binds an opted-in pack to the construction material at every use:
its construction kit, interface and physics contract must equal the material's
documents and its train role must equal the material's TRAIN bytes. This module
builds those roles from the same source-owned functions the construction path
uses (``physical_public``), plus exact reviewed contract bytes, so the two can
only agree.

Private roles stay HUMAN_INPUT unless ``--exposed-development-bank`` is given.
That option binds the already-committed, exposed DEVELOPMENT decision bank
(48 queries each for Motor and Cooling, their counted GetDP/OpenFOAM references
and completion record) as
case_bank, reference_rows and solver_evidence. It moves no protected material
and makes no hidden-exam claim. The score pack and source registration remain
HUMAN_INPUT for their producer.

    python -m carbon.challenge_kit.physical_pack ROOT \
        --challenge electric-motor-magnetics [--exposed-development-bank]
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from carbon.cold_plate import challenge as cooling
from carbon.motor import challenge as motor

from . import (
    battery_pack,
    f02_public,
    f02_train,
    f08_public,
    f08_train,
    physical_public,
    physical_public_train,
)

_DATA = Path(__file__).with_name("data")
_REPOSITORY = Path(__file__).resolve().parents[2]
PACK_SCHEMA = "carbon.challenge-evaluation-pack.v1"
UNAVAILABLE = "HUMAN_INPUT"
#: Exact reviewed bytes per public role, with their pinned sha256. The Motor
#: physics and accuracy contracts are the scorer's own (their hashes equal the
#: ScoreEngine physics_contract_digest and measurement_contract_digest);
#: the limit and objective documents are the reviewed counted-pack role inputs.
_ROLE_FILES = {
    motor.CHALLENGE.challenge_id: {
        "physics_contract": (
            "motor-applied-physics-contract-20261018.json",
            "74e3f30ce38d997e3b7f74505d67981bedcf77de28235ea60bf43f26be9483fd",
        ),
        "accuracy_definition": (
            "motor-applied-g1-measurement-contract-20261018.json",
            "8f374907064891b5a5d261d9d31d8c4159c69577e44daa6234ed83c79bd3f782",
        ),
        "important_limit_definition": (
            "motor-important-limit-definition-20261018.json",
            "3b532c6ef1b5c0ab02b692f16d2b565840fd77d75c71e92b44c0f11d32e0ef44",
        ),
        "design_objective": (
            "motor-design-objective-20261018.json",
            "cfc30f1e6b32415a6fa613413d94baf32efc23063d8b1aed71bd31a24bbe46c3",
        ),
    },
    # Cooling's physics and accuracy documents are generated with its score
    # pack by the scoring producer; until they are bound they stay HUMAN_INPUT.
    cooling.CHALLENGE.challenge_id: {
        "important_limit_definition": (
            "cooling-important-limit-definition-20261018.json",
            "443fc3f5b3fb3b6983b77d697ae25e6e91178e4028a1f70b33fe8f7500ccac97",
        ),
        "design_objective": (
            "cooling-design-objective-20261018.json",
            "864a325aeaa45d3348a69a3b3587d83dd2a9f2106383a74eb488992c77d2c259",
        ),
    },
}
#: The pack version of every registered (Challenge, version), named
#: explicitly; there is no default. Step-2 batch (STEP2_BATCH_VERSIONS_20261020):
#: Motor 1.1, Cooling 1.1, F08 1.2, F02 2.1 and Battery 2.0 are new versions
#: whose exam content is unchanged apart from the version binding (Battery 2.0
#: adds its v2 material rows). Existing versions keep their pack versions.
PACK_VERSIONS = {
    (motor.CHALLENGE.challenge_id, "1.0"): "motor-normal-construction-development-1",
    (motor.CHALLENGE.challenge_id, "1.1"): "motor-normal-construction-development-2",
    (
        cooling.CHALLENGE.challenge_id,
        "1.0",
    ): "cooling-normal-construction-development-1",
    (
        cooling.CHALLENGE.challenge_id,
        "1.1",
    ): "cooling-normal-construction-development-2",
    (battery_pack.CHALLENGE_ID, "1.0"): battery_pack.PACK_VERSION,
    (battery_pack.CHALLENGE_ID, "2.0"): "battery-normal-construction-development-3",
    (f08_train.CHALLENGE_ID, "1.0"): "f08-normal-construction-development-1",
    (f08_train.CHALLENGE_ID, "1.1"): "f08-normal-construction-development-2",
    (f08_train.CHALLENGE_ID, "1.2"): "f08-normal-construction-development-3",
    (f02_train.CHALLENGE_ID, "2.0"): "f02-normal-construction-development-2",
    (f02_train.CHALLENGE_ID, "2.1"): "f02-normal-construction-development-3",
}
#: F02's eight registered cold actions (the scoring producer's
#: `_F02_ACTIONS`), judged B10 ACCEPTED_FOR_DEVELOPMENT_BANK by RR-PACKS-04's
#: plan rejudge under F02-SCIENCE-VALUES-01. Each reference is the primary
#: rung; mesh2 and dt0.5 are its convergence rungs.
F02_ACTIONS = {
    "cool-rect-low": (80, 5),
    "cool-rect-middle": (110, 10),
    "cool-rect-short-high": (140, 5),
    "cool-rect-long-high": (140, 20),
    **{f"cool-rect-near-{power}w": (power, 5) for power in (84, 85, 86, 87)},
}
_F02_JUDGEMENT = (
    f02_train.EVIDENCE + "/rr04-judgement.json",
    "f7cc8c877e25a14658997f484377beffe91f971db2f3ba565393c18343bfdf1a",
)
#: RR-PACKS-04's bulk ledger for the same plan: each primary's measured solve
#: wall time (FINISHED, exit 0, COMPLETED) for the solver-speed benchmark.
_F02_LEDGER = (
    f02_train.EVIDENCE + "/rr04-convergence-ledger.jsonl",
    "f0b33758961b9eb0ccd23155cc05ed1f9d5c550e905064a4118308057d6e4a1b",
)
F02_DECISION_COVERAGE = "RANKING_AND_FEASIBILITY_STRADDLE"
F02_POPULATION = "REGISTERED_EIGHT_ACTION_SET_NOT_INDEPENDENT"
_F02_RUNGS = ("primary", "mesh2", "dt0.5")
#: F08's first accepted decision references (RR-PACKS-03, Validator-reviewed
#: 2026-10-19): eight TRAIN-informed near-feasible geometries at h = 1.7 mm.
_F08_OBSERVED = (
    "docs/development/evidence/f08-near-feasible-public-pilot-20261019/observed.json",
    "09055d8b4b6da9494d520b9e39d12fd5ad005ed6d3413d5f865df3ff684a2723",
)
_F08_ENVIRONMENT = (
    "docs/development/evidence/f08-near-feasible-public-pilot-20261019/pod-environment.json",
    "44ae8c80996e4c7e7fef27a26016ddfbbe125ad2287ff68ba70e4f9793037637",
)
_F08_REFERENCE_RUNG = "h1.7"
#: Validator ruling: every F08 reference is feasible, so D tests ranking only.
F08_DECISION_COVERAGE = "RANKING_ONLY_NO_FEASIBILITY_BOUNDARY"
F08_POPULATION = "TRAIN_INFORMED_LOCAL_NEIGHBOURHOOD_NOT_INDEPENDENT"
#: F08 1.1's exam (RR-PACKS-07 ladder; Validator-approved 2026-10-20): eight
#: pilot-0000 lattice neighbours at h = 1.7 mm, 4 safe and 4 unsafe at the
#: 0.15 mm/N dynamic limit, smallest margin 0.00286 mm/N (about 95x its
#: h2.25 - h1.7 reference error and 22x the TRAIN h3 shift).
_F08_LADDER_DIR = "docs/development/evidence/f08-near-limit-public-20261020"
_F08_LADDER_OBSERVED = (
    _F08_LADDER_DIR + "/ladder-observed.json",
    "26aef1d5f33a29e42c9f208b4b88220bffd488a2d68e9be73d0c93c9c13b03e9",
)
_F08_LADDER_ENVIRONMENT = (
    _F08_LADDER_DIR + "/rr07-pod-environment.json",
    "5c16f95d2c5db972d50757e493f0218ce5a7c50adb52764d4e4449d053cac463",
)
_F08_LADDER_ACTIONS = (
    _F08_LADDER_DIR + "/ladder-actions.json",
    "9b9b3534e51f4351793ba43ae4f78d6c8dc4b4a07a4092732c1cbf73d365ef2b",
)
F08_LADDER_DECISION_COVERAGE = "RANKING_AND_FEASIBILITY_STRADDLE"
F08_LADDER_POPULATION = "PILOT_LATTICE_LADDER_AT_THE_LIMIT_NOT_INDEPENDENT"
#: Per F08 version: (observed, environment, case-id prefix, cohort, coverage,
#: population, pack version).
_F08_EXAMS = {
    "1.0": (
        _F08_OBSERVED,
        _F08_ENVIRONMENT,
        None,
        "decision_near_feasible",
        F08_DECISION_COVERAGE,
        F08_POPULATION,
        "f08-normal-construction-development-1",
    ),
    "1.1": (
        _F08_LADDER_OBSERVED,
        _F08_LADDER_ENVIRONMENT,
        "ladder",
        "decision_near_limit",
        F08_LADDER_DECISION_COVERAGE,
        F08_LADDER_POPULATION,
        "f08-normal-construction-development-2",
    ),
    # 1.2: 1.1's ladder bank and TRAIN v2, unchanged; only the binding differs.
    "1.2": (
        _F08_LADDER_OBSERVED,
        _F08_LADDER_ENVIRONMENT,
        "ladder",
        "decision_near_limit",
        F08_LADDER_DECISION_COVERAGE,
        F08_LADDER_POPULATION,
        "f08-normal-construction-development-3",
    ),
}
_F08_BRIEF = (
    "docs/development/challenge_pipeline/onboarding-runs/generated/f08/brief.json",
    "2c15f096f43b02a4da4b1455d4c629d8979ad1319c8efb61afb141674f682330",
)
PUBLIC_ROLES = (
    "construction_kit",
    "interface",
    "train",
    "physics_contract",
    "accuracy_definition",
    "important_limit_definition",
    "design_objective",
)
PRIVATE_ROLES = ("case_bank", "reference_rows", "solver_evidence", "score_pack")
#: The exposed DEVELOPMENT decision bank, committed in the repository, pinned.
_BANKS = {
    motor.CHALLENGE.challenge_id: {
        "study": (
            "docs/development/studies/MOTOR_SYNTHETIC_DECISION_V2.json",
            "cf00f2bbbfe8cd0adad7d668d921fa2e0f24d97353d7391885d88b4d0139e56d",
        ),
        "references": (
            "docs/development/evidence/track-b-replay/motor-counted-v2.json",
            "186ca2eae8cebb1b5b2cf253c4df70eb9de0b168900f24dd714d2ce87cc17714",
        ),
        "completion": (
            "docs/development/evidence/motor-decision-counted-v2/completion.json",
            "4662e9679ce3e2a7b7c3e3e357ca04d0546e3909b6dc11e8c241d538a0331f56",
        ),
        "condition_key": "condition_id",
        # The applied Motor score definition (b4ea72a5) takes A as the minimum
        # of benefits over three cohorts, so the bank carries all three, in
        # this order: public PRACTICE, the twelve selected pilot cases (in the
        # acquisition manifest's order), then the old-V2 decision cells.
        "practice": (
            "docs/development/evidence/motor-pools-v1/practice.jsonl",
            "0466627106bdcf8495b96a93ea89e5d5270ad845171d6770bac2b2d9922dd247",
        ),
        "pilot": (
            "docs/development/evidence/motor-pilot-v1/records.jsonl",
            "930174906f58390114a40312572f52998115e571f3495be028e7fa265c6f3cfb",
        ),
        #: MOTOR_DUAL_TRANSFER_ACQUISITION_MANIFEST_20261018 pilot_case_ids.
        "pilot_case_ids": (
            "difficult-1-deep-saturation",
            "difficult-2-sharpest-cogging",
            "difficult-3-weakest-field",
            "difficult-4-field-weakening",
            "ordinary-1",
            "ordinary-2",
            "ordinary-3",
            "ordinary-4",
            "ordinary-5",
            "ordinary-6",
            "ordinary-7",
            "ordinary-8",
        ),
    },
    cooling.CHALLENGE.challenge_id: {
        "study": (
            "docs/development/studies/AI_ACCELERATOR_COOLING_SYNTHETIC_V1.json",
            "607e5fe659607659fbd5131dc2049c3c2ebcbfd1d984d796b503dfa74378d04b",
        ),
        "references": (
            "docs/development/evidence/track-b-replay/ai-cooling-counted-v1.json",
            "cf48e003d4be45c11283bdb76c5bdecc98fd9fbd05c1df0166a5195e5d88f2bf",
        ),
        "completion": (
            "docs/development/evidence/ai-cooling-counted-v1/completion.json",
            "697a510bd15ab0f350c7ea16dd4d62f7f6826db8eff1176cc1ad1f8c0025054d",
        ),
        "condition_key": "scenario_id",
    },
}


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _files(challenge_id: str, version: str) -> dict:
    if challenge_id == battery_pack.CHALLENGE_ID:
        battery_pack._check(version)
        return {}
    if challenge_id == f08_train.CHALLENGE_ID:
        f08_public.construction_kit(challenge_id, version)  # refuses unknown
        return {}
    if challenge_id == f02_train.CHALLENGE_ID:
        f02_public.construction_kit(challenge_id, version)  # refuses unknown
        return {}
    if challenge_id not in _ROLE_FILES:
        raise ValueError("no normal-construction pack for this Challenge")
    physical_public.construction_kit(challenge_id, version)  # refuses unknown versions
    return _ROLE_FILES[challenge_id]


def _role_file(challenge_id: str, version: str, role: str) -> bytes:
    name, pinned = _files(challenge_id, version)[role]
    raw = (_DATA / name).read_bytes()
    if hashlib.sha256(raw).hexdigest() != pinned:
        raise ValueError(f"pinned {role} bytes differ")
    return raw


#: The scorer binds a physics contract only as ``{version, definition}``
#: (``benchmark_evidence.physics_contract_identity``); the pinned document is
#: carried verbatim as the definition under this version.
_PHYSICS_VERSIONS = {
    motor.CHALLENGE.challenge_id: "motor-applied-physics-contract-20261018",
}


def physics_contract(challenge_id: str, version: str) -> dict | None:
    """The Challenge's versioned physics contract for the construction material
    and the pack to carry, or None while it is not bound."""
    if challenge_id == f02_train.CHALLENGE_ID:
        _files(challenge_id, version)
        # F02 adopts no law; its summary basis is the scoring producer's.
        from carbon.scoring import f02_dual_pack

        return f02_dual_pack.physics_contract()
    if challenge_id == f08_train.CHALLENGE_ID:
        _files(challenge_id, version)
        # F08's physics contract is the scoring producer's source binding.
        from carbon.scoring import f08_dual_pack

        return f08_dual_pack.physics_contract()
    if challenge_id == cooling.CHALLENGE.challenge_id:
        _files(challenge_id, version)
        # Cooling's physics contract is the scoring producer's exact native
        # source binding; the pack and the construction material carry it.
        from carbon.scoring import cooling_dual_pack

        return cooling_dual_pack.physics_contract()
    if "physics_contract" not in _files(challenge_id, version):
        return None
    return {
        "version": _PHYSICS_VERSIONS[challenge_id],
        "definition": json.loads(_role_file(challenge_id, version, "physics_contract")),
    }


def public_roles(challenge_id: str, version: str) -> dict[str, bytes]:
    """Every bound public role's exact bytes; an unbound role is absent here
    and HUMAN_INPUT in the manifest. Nothing is defaulted or inferred."""
    if challenge_id == battery_pack.CHALLENGE_ID:
        return battery_pack.public_roles(version)
    if challenge_id == f02_train.CHALLENGE_ID:
        return _f02_public_roles(challenge_id, version)
    if challenge_id == f08_train.CHALLENGE_ID:
        brief = _pinned_repository_file(_F08_BRIEF)
        brief_text = brief.decode("utf-8")
        if not all(v in brief_text for v in ("0.45 kg", "0.03 mm/N", "0.15 mm/N")):
            raise ValueError("F08 brief no longer states the registered limits")
        identity = {"id": challenge_id, "version": version}
        coverage, population = _F08_EXAMS[version][4:6]
        sources = [
            {"path": _F08_BRIEF[0], "sha256": _F08_BRIEF[1]},
            {"path": "carbon/challenge_pipeline/structures_readiness.py",
             "symbol": "feasibility verdict limits"},
        ]  # fmt: skip
        return {
            "construction_kit": _canonical(
                f08_public.construction_kit(challenge_id, version)
            ),
            "interface": _canonical(
                f08_public.interface_document(challenge_id, version)
            ),
            "train": f08_train.load_public_train(version)["train"],
            "physics_contract": _canonical(physics_contract(challenge_id, version)),
            "important_limit_definition": _canonical(
                {
                    "schema": "carbon.f08.important-limit-definition.v1",
                    "challenge": identity,
                    "constraints": {
                        "mass_kg_max": 0.45,
                        "static_tip_mm_per_n_max": 0.03,
                        "dynamic_tip_mm_per_n_max": 0.15,
                    },
                    "inclusive_boundaries": True,
                    "mass_role": "analytic CAD mass; feasibility only, not a learned target",
                    "decision_coverage": coverage,
                    "population": population,
                    "sources": sources,
                    **_f08_limit_extras(version),
                }
            ),
            "design_objective": _canonical(
                {
                    "schema": "carbon.f08.design-objective.v1",
                    "challenge": identity,
                    "sense": "minimize",
                    "quantity": "worst_dynamic_mm_per_n",
                    "definition": "worst-band TIP dynamic compliance over all damping; "
                    "probe is diagnostic only",
                    "decision_coverage": coverage,
                    "sources": sources,
                }
            ),
        }
    roles = {
        "construction_kit": _canonical(
            physical_public.construction_kit(challenge_id, version)
        ),
        "interface": _canonical(
            physical_public.interface_document(challenge_id, version)
        ),
        "train": physical_public_train.load_public_train(challenge_id)["train"],
    }
    for role in _files(challenge_id, version):
        roles[role] = _role_file(challenge_id, version, role)
    physics = physics_contract(challenge_id, version)
    if physics is not None:
        roles["physics_contract"] = _canonical(physics)
    return roles


def _bank_file(challenge_id: str, name: str) -> bytes:
    path, pinned = _BANKS[challenge_id][name]
    raw = (_REPOSITORY / path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != pinned:
        raise ValueError(f"pinned development bank {name} differs")
    return raw


def development_bank(challenge_id: str, version: str) -> dict:
    """The exposed DEVELOPMENT bank, in a fixed declared order and cohorts.

    Motor: 30 PRACTICE, 12 selected pilot cases, then the 48 old-V2 decision
    cells (design-then-condition). Cooling: its 48 decision cells. Each row's
    cohort is returned so the score producer evaluates exactly its registered
    cohorts.

    ``inputs`` rows follow the numeric interface's input names and dtype;
    ``references`` are the counted solver outputs for the same rows, laid out by
    the interface's target slices, in native units with no transform. The
    construction material's practice inputs/reference must be these arrays, so
    the scored query equals the pack's case bank byte for byte.
    """
    _files(challenge_id, version)
    if challenge_id == battery_pack.CHALLENGE_ID:
        return battery_pack.development_bank(version)
    if challenge_id == f08_train.CHALLENGE_ID:
        return _f08_bank(challenge_id, version)
    if challenge_id == f02_train.CHALLENGE_ID:
        return _f02_bank(challenge_id, version)
    if challenge_id not in _BANKS:
        raise ValueError("no development bank for this Challenge")
    study = json.loads(_bank_file(challenge_id, "study"))
    interface = physical_public_train.numeric_interface_document(challenge_id)
    names, slices = interface["input_names"], interface["target_slices"]
    width = max(end for _, end in slices.values())
    condition_key = _BANKS[challenge_id]["condition_key"]
    solved = {
        case["case_id"]: case
        for case in json.loads(_bank_file(challenge_id, "references"))["cases"]
    }
    case_ids, rows, references, records, cohorts = [], [], [], [], []
    entries = []
    spec = _BANKS[challenge_id]
    if "practice" in spec:
        for line in _bank_file(challenge_id, "practice").decode("utf-8").splitlines():
            if line.strip():
                record = json.loads(line)
                entries.append(
                    ("practice", record["case_id"], record["inputs"], record)
                )
        pilot = {}
        for line in _bank_file(challenge_id, "pilot").decode("utf-8").splitlines():
            if line.strip():
                record = json.loads(line)
                pilot[record["case_id"]] = record
        for case_id in spec["pilot_case_ids"]:
            record = pilot.get(case_id)
            if record is None:
                raise ValueError(f"{case_id} has no pilot record")
            cohort = {"ordinary": "pilot_ordinary", "corner": "pilot_difficult"}
            entries.append((cohort[record["kind"]], case_id, record["inputs"], record))
    for design in study["designs"]:
        for condition in study["conditions"]:
            case_id = f"decision-{design['design_id']}-{condition[condition_key]}"
            record = solved.get(case_id)
            if record is None:
                raise ValueError(f"{case_id} has no reference")
            values = {**design["values"], **condition["values"]}
            group = condition["group"].lower()
            entries.append((f"decision_{group}", case_id, values, record))
    for cohort, case_id, values, record in entries:
        if record.get("status") != "OK":
            raise ValueError(f"{case_id} has no accepted reference")
        case_ids.append(case_id)
        cohorts.append(cohort)
        rows.append([float(values[name]) for name in names])
        target = [0.0] * width
        for name, (start, end) in slices.items():
            value = record["outputs"][name]
            value = value if type(value) is list else [value]
            if len(value) != end - start:
                raise ValueError(f"{case_id} {name} shape differs")
            target[start:end] = [float(v) for v in value]
        references.append(target)
        records.append(record)
    inputs = np.asarray(rows, dtype="<f8")
    targets = np.asarray(references, dtype="<f8")
    if (
        len(set(case_ids)) != len(case_ids)
        or sum(c.startswith("decision_") for c in cohorts) != len(solved)
        or inputs.shape != (len(case_ids), len(names))
        or targets.shape != (len(case_ids), width)
        or not np.isfinite(inputs).all()
        or not np.isfinite(targets).all()
    ):
        raise ValueError("development bank tensor differs")
    inputs.setflags(write=False)
    targets.setflags(write=False)
    return {
        "case_ids": tuple(case_ids),
        "cohorts": tuple(cohorts),
        "inputs": inputs,
        "references": targets,
        "reference_records": records,
        "solver_evidence": _bank_file(challenge_id, "completion"),
    }


def _pinned_repository_file(path_and_sha: tuple[str, str]) -> bytes:
    path, pinned = path_and_sha
    raw = (_REPOSITORY / path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != pinned:
        raise ValueError(f"pinned {path} differs")
    return raw


def _f08_limit_extras(version: str) -> dict:
    """1.1's limit statement: the exam straddles the dynamic limit, and the
    TRAIN mesh reads slightly lower than the exam truth there."""
    if version == "1.0":
        return {}
    return {
        "exam_straddle": {
            "limit": "dynamic_tip_mm_per_n_max",
            "safe": 4,
            "unsafe": 4,
            "smallest_margin_mm_per_n": 0.00286,
            "largest_reference_error_mm_per_n": 3.4e-5,
        },
        "train_mesh": dict(f08_train.TRAIN_MESH_STATEMENT),
    }


def _f08_refuse_train_overlap(inputs, version: str) -> None:
    """No exam action may be a TRAIN action (Validator condition on 1.1):
    exact equality of the six inputs, both sides in the interface's float32,
    the dtype a model receives them in."""
    train = f08_train.load_public_train(version)["inputs"]
    seen = {tuple(row) for row in np.asarray(train, dtype=inputs.dtype).tolist()}
    if any(tuple(row) in seen for row in inputs.tolist()):
        raise ValueError("F08 exam action is a TRAIN action")


def _f08_bank(challenge_id: str, version: str) -> dict:
    """F08's accepted references, laid out by the interface's named slices."""
    interface = f08_public.interface_document(challenge_id, version)
    names = interface["input"]["names"]
    slices = interface["output"]["named_slices"]
    width = max(end for _, end in slices.values())
    observed_pin, environment_pin, prefix, cohort, coverage, population, _ = _F08_EXAMS[
        version
    ]
    observed_raw = _pinned_repository_file(observed_pin)
    observed = json.loads(observed_raw)
    environment = json.loads(_pinned_repository_file(environment_pin))
    geometries = sorted(observed["convergence"])
    if prefix is not None:
        # The ladder was run under the pilot's geometry names; its rows must be
        # exactly the frozen ladder actions, in order.
        actions = json.loads(_pinned_repository_file(_F08_LADDER_ACTIONS))["actions"]
        if geometries != [f"pilot-{k:04d}" for k in range(len(actions))] or any(
            observed["cases"][g]["case"] != a
            for g, a in zip(geometries, actions, strict=True)
        ):
            raise ValueError("F08 ladder rows differ from the frozen actions")
    case_ids, rows, references, records = [], [], [], []
    for geometry in geometries:
        verdict = observed["convergence"][geometry]
        case = observed["cases"].get(f"{geometry}-{_F08_REFERENCE_RUNG}")
        if (
            case is None
            or verdict.get("asymptotic_ok") is not True
            or any(r.get("verdict") != "PASS" for r in verdict["rungs"].values())
            or case["mode_ladder"]["verdict"] != "PASS"
            or case["cost"]["outcome"] != "COMPLETED"
        ):
            raise ValueError(f"{geometry} has no accepted reference")
        damping = case["damping"]
        values = {"static_tip_mm_per_n": case["static_tip_mm_per_n"]}
        for zeta, tag in (
            ("zeta_0.005", "z005"),
            ("zeta_0.01", "z010"),
            ("zeta_0.02", "z020"),
        ):
            values[f"peak_tip_{tag}_mm_per_n"] = damping[zeta]["worst_mm_per_n"]
            values[f"peak_frequency_{tag}_hz"] = damping[zeta]["worst_hz"]
        target = [0.0] * width
        for name, (start, end) in slices.items():
            target[start:end] = [float(values[name])]
        case_id = geometry if prefix is None else f"{prefix}-{geometry[-1]}"
        case_ids.append(case_id)
        rows.append([float(observed["cases"][geometry]["case"][n]) for n in names])
        references.append(target)
        records.append(
            {
                "status": "OK",
                "case_id": case_id,
                "design_id": case_id,
                "reference_rung_h_mm": case["h_mm"],
                "wall_s": case["cost"]["wall_s"],
                "image": {
                    "kind": environment["kind"],
                    "solvers": environment["solvers"],
                },
                "cad_mass_kg": case["cad_mass_kg"],
                "observed": {
                    k: case[k]
                    for k in (
                        "static_tip_mm_per_n",
                        "worst_dynamic_mm_per_n",
                        "mass_kg",
                        "modes",
                        "mode_ladder",
                        "in_band_modes_hz",
                    )
                },
                "damping": {
                    zeta: {k: damping[zeta][k] for k in ("worst_mm_per_n", "worst_hz")}
                    for zeta in damping
                },
                "convergence": verdict,
            }
        )
    dtype = interface["train_dtype"]
    inputs = np.asarray(rows, dtype=dtype)
    targets = np.asarray(references, dtype=dtype)
    if (
        inputs.shape != (len(case_ids), len(names))
        or targets.shape != (len(case_ids), width)
        or not np.isfinite(inputs).all()
        or not np.isfinite(targets).all()
    ):
        raise ValueError("F08 bank tensor differs")
    if version != "1.0":
        _f08_refuse_train_overlap(inputs, version)
    inputs.setflags(write=False)
    targets.setflags(write=False)
    return {
        "case_ids": tuple(case_ids),
        "cohorts": (cohort,) * len(case_ids),
        "inputs": inputs,
        "references": targets,
        "reference_records": records,
        "solver_evidence": observed_raw,
        "decision_coverage": coverage,
        "population": population,
    }


def _f02_public_roles(challenge_id: str, version: str) -> dict[str, bytes]:
    """F02's public roles. The accuracy definition and the Design policy and
    scales are scoring authority, so they stay HUMAN_INPUT here; the decided
    TRAIN spread is carried by the TRAIN provenance and the kit's limits."""
    _files(challenge_id, version)
    identity = {"id": challenge_id, "version": version}
    sources = [
        {"path": "scripts/dev/reference_packages/elmer/f02_menu.py",
         "symbol": "existing bounds (95 C)"},
        {"path": ".agent/decisions/2026-10-19-OWNER-F02-TRAIN40-V2-01.md"},
    ]  # fmt: skip
    return {
        "construction_kit": _canonical(
            f02_public.construction_kit(challenge_id, version)
        ),
        "interface": _canonical(f02_public.interface_document(challenge_id, version)),
        "train": f02_train.load_public_train(version)["train"],
        "physics_contract": _canonical(physics_contract(challenge_id, version)),
        "important_limit_definition": _canonical(
            {
                "schema": "carbon.f02.important-limit-definition.v1",
                "challenge": identity,
                "context": dict(f02_train.CONTEXT),
                "constraints": {"peak_top_c_max": f02_train.LIMIT_C},
                "inclusive_boundaries": True,
                "decision_coverage": F02_DECISION_COVERAGE,
                "population": F02_POPULATION,
                "train_peak_std_c": dict(
                    f02_train.load_public_train(version)["provenance"][
                        "train_peak_std_c"
                    ]
                ),
                "sources": sources,
            }
        ),
        "design_objective": _canonical(
            {
                "schema": "carbon.f02.design-objective.v1",
                "challenge": identity,
                "sense": "maximize",
                "quantity": "extra_energy_j",
                "definition": "analytic (peak_w - 20) * on_time_s of a schedule whose "
                "peak top temperature is within the limit",
                "decision_coverage": F02_DECISION_COVERAGE,
                "design_policy_and_scales": UNAVAILABLE,
                "sources": sources,
            }
        ),
    }


def _f02_bank(challenge_id: str, version: str) -> dict:
    """F02's eight accepted primaries, laid out by the interface."""
    interface = f02_public.interface_document(challenge_id, version)
    names = interface["input"]["names"]
    slices = interface["output"]["named_slices"]
    width = max(end for _, end in slices.values())
    raw = _pinned_repository_file(_F02_JUDGEMENT)
    judgement = json.loads(raw)
    acceptance = judgement.get("family_acceptance", {})
    if (
        judgement.get("schema") != "carbon.f02-readiness.judgement.v1"
        or acceptance.get("status") != "ACCEPTED_FOR_DEVELOPMENT_BANK"
        or acceptance.get("primaries_passing") != acceptance.get("primaries")
        or acceptance.get("baseline_checks_passing")
        != acceptance.get("baseline_checks_expected")
    ):
        raise ValueError("F02 judgement is not an accepted development bank")
    observables, rungs = judgement["observables"], judgement["rung_comparisons"]
    finished = {}
    for line in _pinned_repository_file(_F02_LEDGER).decode("utf-8").splitlines():
        event = json.loads(line)
        if event.get("event") == "FINISHED":
            if event.get("case") in finished:
                raise ValueError("F02 ledger repeats a case")
            finished[event.get("case")] = event
    case_ids, rows, references, records = [], [], [], []
    for case_id in sorted(F02_ACTIONS):
        power, on_time = F02_ACTIONS[case_id]
        compared = rungs.get(case_id, {})
        values = {r: observables.get(f"{case_id}-{r}", {}) for r in _F02_RUNGS}
        peaks = [values[r].get("peak_top_c") for r in _F02_RUNGS]
        if (
            compared.get("pass") is not True
            or not all(type(v) is float and np.isfinite(v) for v in peaks)
            or compared.get("primary_peak_c") != peaks[0]
            or len({v <= f02_train.LIMIT_C for v in peaks}) != 1
        ):
            raise ValueError(f"{case_id} has no accepted reference")
        primary = values["primary"]
        energy = primary.get("extra_energy_j")
        # The observer sums the energy in floating point (2399.9999999999995).
        if type(energy) is not float or not np.isclose(
            energy, (power - 20) * on_time, rtol=1e-12, atol=0.0
        ):
            raise ValueError(f"{case_id} action differs from its registered schedule")
        solve = finished.get(case_id + "-primary", {})
        wall_s = solve.get("wall_s")
        if (
            solve.get("outcome") != "COMPLETED"
            or solve.get("exit") != 0
            or solve.get("reservation") != "primary"
            or solve.get("image_pin") != judgement["image"]
            or type(wall_s) is not float
            or not wall_s > 0
        ):
            raise ValueError(f"{case_id} has no measured primary solve")
        target = [0.0] * width
        target[slice(*slices["peak_top_c"])] = [peaks[0]]
        case_ids.append(case_id)
        rows.append([float({"peak_w": power, "on_time_s": on_time}[n]) for n in names])
        references.append(target)
        records.append(
            {
                "status": "OK",
                "case_id": case_id,
                "design_id": case_id,
                "action": {"peak_w": power, "on_time_s": on_time},
                "context": dict(f02_train.CONTEXT),
                "image": judgement["image"],
                "wall_s": wall_s,
                "observed": {
                    k: primary[k]
                    for k in (
                        "peak_top_c",
                        "extra_energy_j",
                        "first_95c_crossing_s",
                        "peak_time_s",
                        "recovery_s",
                    )
                },
                "rung_peaks_c": dict(zip(_F02_RUNGS, peaks, strict=True)),
                "convergence": compared,
            }
        )
    dtype = interface["train_dtype"]
    inputs = np.asarray(rows, dtype=dtype)
    targets = np.asarray(references, dtype=dtype)
    if inputs.shape != (8, len(names)) or targets.shape != (8, width):
        raise ValueError("F02 bank tensor differs")
    train = f02_train.load_public_train(version)["inputs"]
    seen = {tuple(row) for row in np.asarray(train, dtype=inputs.dtype).tolist()}
    if any(tuple(row) in seen for row in inputs.tolist()):
        raise ValueError("F02 exam action is a TRAIN action")
    inputs.setflags(write=False)
    targets.setflags(write=False)
    return {
        "case_ids": tuple(case_ids),
        "cohorts": ("decision_cold_eight",) * len(case_ids),
        "inputs": inputs,
        "references": targets,
        "reference_records": records,
        "solver_evidence": raw,
        "decision_coverage": F02_DECISION_COVERAGE,
        "population": F02_POPULATION,
    }


def _development_private_roles(challenge_id: str, version: str) -> dict[str, bytes]:
    from carbon.development_session.bundle_construction_worker import _tensors

    bank = development_bank(challenge_id, version)
    roles = {
        "case_bank": _tensors(inputs=np.array(bank["inputs"])),
        "reference_rows": _canonical(
            [
                {"row": i, "case_id": case_id, "cohort": cohort, "record": record}
                for i, (case_id, cohort, record) in enumerate(
                    zip(
                        bank["case_ids"],
                        bank["cohorts"],
                        bank["reference_records"],
                        strict=True,
                    )
                )
            ]
        ),
    }
    if bank["solver_evidence"] is not None:
        roles["solver_evidence"] = bank["solver_evidence"]
    return roles


def write_public_pack(
    root: Path,
    challenge_id: str,
    version: str,
    *,
    exposed_development_bank: bool = False,
) -> Path:
    """Write the public roles and a draft manifest; returns the manifest path.

    Private roles are HUMAN_INPUT, or, with ``exposed_development_bank``, the
    committed exposed bank for case_bank, reference_rows and solver_evidence.
    ``evaluation_pack.prepare_pack`` seals the draft. The directory must be new
    or empty, so an earlier pack is never overwritten.
    """
    root = Path(root)
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    if any(root.iterdir()):
        raise ValueError("pack directory must be empty")
    public = {}
    for role, body in sorted(public_roles(challenge_id, version).items()):
        name = f"public/{role}.{'npz' if role == 'train' else 'json'}"
        (root / "public").mkdir(mode=0o700, exist_ok=True)
        (root / name).write_bytes(body)
        public[role] = {"path": name}
    public.update({role: UNAVAILABLE for role in PUBLIC_ROLES if role not in public})
    private = {role: UNAVAILABLE for role in PRIVATE_ROLES}
    if (challenge_id, version) not in PACK_VERSIONS:
        raise ValueError("no pack version registered for this Challenge version")
    pack_version = PACK_VERSIONS[(challenge_id, version)]
    if exposed_development_bank:
        (root / "private").mkdir(mode=0o700)
        for role, body in _development_private_roles(challenge_id, version).items():
            name = f"private/{role}.{'npz' if role == 'case_bank' else 'json'}"
            (root / name).write_bytes(body)
            private[role] = {"path": name}
        pack_version += "-exposed-bank"
    manifest = {
        "schema": PACK_SCHEMA,
        "challenge": {"id": challenge_id, "version": version},
        "pack_version": pack_version,
        "public": public,
        "private": private,
    }
    path = root / "evaluation-pack.json"
    path.write_bytes(_canonical(manifest))
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("root", type=Path)
    parser.add_argument("--challenge", required=True)
    parser.add_argument("--exposed-development-bank", action="store_true")
    # Every pack names its Challenge version: there is no default version.
    parser.add_argument("--version", required=True)
    args = parser.parse_args(argv)
    if (args.challenge, args.version) not in PACK_VERSIONS:
        parser.error("no pack registered for this Challenge version")
    path = write_public_pack(
        args.root,
        args.challenge,
        args.version,
        exposed_development_bank=args.exposed_development_bank,
    )
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
