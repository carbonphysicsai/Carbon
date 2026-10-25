"""Motor discovery, derived from its executable registrations."""

from __future__ import annotations


def _verdict(strategy):
    from carbon.reconstruction.challenge_contracts import validate_for_challenge

    result = validate_for_challenge(strategy)
    return {
        "valid": result.ok,
        "issues": [{"code": issue.code, "path": issue.path} for issue in result.errors],
    }


def describe():
    from carbon.motor import domain, exam, population
    from carbon.motor.challenge import (
        CALIBRATION_PATH,
        CALIBRATION_SHA256,
        PRACTICE_CASES,
        PRACTICE_PATH,
        PRACTICE_SHA256,
        TRAIN_CASES,
        TRAIN_PATH,
        TRAIN_SHA256,
        interface_document,
    )
    from carbon.motor.contracts import implementation_digest
    from carbon.reconstruction.capability_registry import (
        MOTOR_CHALLENGE,
        MOTOR_LENGTH_CHOICES,
        MOTOR_LENGTHS,
        MOTOR_RIDGE_CHOICES,
        MOTOR_RIDGES,
        catalog_surfaces,
        contract,
        public_registry,
    )

    registered = contract(MOTOR_CHALLENGE)
    capabilities = public_registry(MOTOR_CHALLENGE)["capabilities"]
    rebuildable = [
        value for value in capabilities if value["status"] == "rebuildable_development"
    ]
    # What cannot be rebuilt here, each with its blocker, built as Battery's is
    # (BUG MOTOR_OBSERVATION_UNSUPPORTED_20261020: the agent's observation
    # counts these, and this description listed none).
    unsupported = [
        {
            "id": value["id"],
            "status": value["status"],
            "blocker": value["blocker"],
            "summary": value["summary"],
        }
        for value in capabilities
        if value["status"] != "rebuildable_development"
    ]
    controls = {
        name: {
            "group": group,
            "type": kind,
            "minimum_or_choices": list(low) if type(low) is tuple else low,
            "maximum": high,
            "default": default,
            "families": list(families) if families else None,
        }
        for name, (group, kind, low, high, default, families) in catalog_surfaces(
            MOTOR_CHALLENGE
        ).items()
    }
    scaffold = {
        "schema_version": "1.0",
        "challenge_id": MOTOR_CHALLENGE,
        "backbone": "kernel_ridge",
        "parameters": {"length": "length_4", "ridge": "ridge_1e_4"},
    }
    interface = interface_document()
    return {
        "identity": registered.identity,
        "contract_digest": registered.digest,
        "task": (
            "Predict the 60-angle electromagnetic torque curve over one "
            "15-degree rotor period for the registered two-dimensional "
            "surface-PM motor cross-section."
        ),
        "intended_use": (
            "Public DEVELOPMENT construction and practice only; not a three-"
            "dimensional end-effect, thermal, transient-drive, hardware or "
            "customer-acceptance model."
        ),
        "interface": {
            **interface,
            "conventions": (
                "millimetres, degrees, A/mm^2 and N.m; torque has 60 evenly "
                "spaced samples over the 15-degree periodic rotor sweep"
            ),
        },
        "public_material": {
            "names": [
                "objective",
                "capabilities",
                "training_data",
                "practice_data",
                "reference_method",
            ],
            "access": (
                "start_research_task kind=workspace action=public_material with "
                "arguments_json encoding one listed name"
            ),
            "train": {
                "path": TRAIN_PATH,
                "cases": TRAIN_CASES,
                "sha256": TRAIN_SHA256,
            },
            "practice": {
                "path": PRACTICE_PATH,
                "cases": PRACTICE_CASES,
                "sha256": PRACTICE_SHA256,
                "adaptively_seen": True,
            },
            "calibration": {
                "path": CALIBRATION_PATH,
                "sha256": CALIBRATION_SHA256,
            },
            "never_disclosed": [
                "the private 60-case pool or references",
                "counted decision-study reference artifacts",
                "future confirmation cases, seeds or metadata",
            ],
        },
        "reference": {
            "method": (
                "Gmsh mesh plus GetDP two-dimensional magnetostatic solve; "
                "Maxwell-stress torque over one rotor period"
            ),
            "image": "carbon-motor-reference:dev (pinned Dockerfile inputs)",
            "applicability": {
                "geometry": "domain.validity must return no reasons",
                "period_deg": domain.PERIOD_DEG,
                "angle_steps": domain.ANGLE_STEPS,
            },
            "construction_access": False,
        },
        "models": {
            "rebuildable": [
                {
                    "id": value["id"],
                    "selector": value["selector"],
                    "summary": value["summary"],
                }
                for value in rebuildable
                if value["id"].startswith("model_family.")
            ],
            "controls": controls,
            "choice_values": {
                "length": dict(zip(MOTOR_LENGTH_CHOICES, MOTOR_LENGTHS, strict=True)),
                "ridge": dict(zip(MOTOR_RIDGE_CHOICES, MOTOR_RIDGES, strict=True)),
            },
            "note": "Every listed control changes the deterministic KRR rebuild.",
        },
        "prediction_contract": {
            "per_case": interface["outputs"],
            "produced_by": (
                "Carbon reconstructs from the pinned public TRAIN records; a "
                "miner supplies neither predictions nor weights"
            ),
        },
        "execution": {
            "backend": "NumPy in the pinned Linux CPU isolated carrier",
            "worker_image": "the campaign's verified C-03 CPU worker image",
            "gpu_lane": False,
            "implementation_digest": implementation_digest(),
            "envelope": registered.document()["envelope"],
        },
        "limits": {
            "budget": "the campaign ledger; discovery charges nothing",
            "scope": "the registered Level-0 contract and public material only",
        },
        "workflow": {
            "validate": "check_design or compile_strategy; no charge",
            "practice": "rebuild on public TRAIN and score on public PRACTICE",
            "freeze": "the campaign freezes one practiced recipe",
            "submit": (
                "downstream Motor validator/scoring integration is a separate "
                "ticket and remains fail closed until registered"
            ),
        },
        "exam": {
            "gates": [gate.gate_id for gate in exam.GATES],
            "components": list(exam.COMPONENTS),
            "rule": "development normalized prediction error; lower is better",
            "qualification": False,
        },
        "feedback": {
            "practice": "aggregate public-practice components and typed gates",
            "evaluation": "not served by this construction ticket",
        },
        "examples": [{"strategy": scaffold}],
        "examples_admission": [_verdict(scaffold)],
        "unsupported": unsupported,
        "population": {
            "version": population.POPULATION_VERSION,
            "screen": "domain.validity returns no buildability reasons",
            "authority": "provisional DEVELOPMENT, not qualified",
        },
        "exclusion_scope": {
            "level_0": "declarative kernel-ridge settings only",
            "excluded": [
                "participant code or weights",
                "reference-solver reuse",
                "private, decision-study or confirmation evidence",
                "three-dimensional end effects, thermal and drive transients",
            ],
        },
    }


#: Motor's backbone-catalog version (OWNER-BACKBONE-CATALOG-01).
CATALOG_VERSION = "1.2"


def catalog_recipe(catalog_id=None, version=CATALOG_VERSION):
    """A ready catalog recipe: the version's kit, one catalog entry, its
    tested baseline settings (empty: unset settings keep the baseline's). With no
    id, a v2.* entry where the version offers one (every setting is the miner's),
    else `neuralop.FNO`."""
    from carbon.backbone_catalog import listing, served
    from carbon.challenge_kit import physical_public
    from carbon.reconstruction.capability_registry import MOTOR_CHALLENGE

    if catalog_id is None:
        catalog_id = listing.preferred(MOTOR_CHALLENGE, version) or "neuralop.FNO"
    kit = physical_public.construction_kit(MOTOR_CHALLENGE, version)
    item = listing.entry(catalog_id, MOTOR_CHALLENGE, version)
    return {
        "schema": "carbon.construction-recipe.v1",
        "challenge": kit,
        "source": {
            "kind": "catalog",
            "catalog_id": catalog_id,
            "catalog_digest": served.digest(MOTOR_CHALLENGE, version),
        },
        "procedure": {
            "entrypoint": None,
            "configuration": {},
            "train_use": {},
            "initial_state": None,
        },
        "output": {
            "format": item["output_format"],
            "interface_digest": kit["interface_digest"],
        },
    }


def describe_catalog(version=CATALOG_VERSION):
    """Motor's catalog version: Carbon's tested backbones by catalog id, built
    and judged as the Carbon bundle each names, on the direct recipe path."""
    from carbon.backbone_catalog import listing as catalog_listing
    from carbon.backbone_catalog import served
    from carbon.motor import domain, exam
    from carbon.motor.challenge import (
        PRACTICE_CASES,
        TRAIN_CASES,
        TRAIN_PATH,
        TRAIN_SHA256,
    )
    from carbon.reconstruction.capability_registry import (
        MOTOR_CHALLENGE,
        public_registry,
    )
    from carbon.reconstruction.served_recipe_contract import registered

    contract = registered(MOTOR_CHALLENGE, version)
    catalog = served.document(MOTOR_CHALLENGE, version)
    capabilities = public_registry(MOTOR_CHALLENGE)["capabilities"]
    # The Level 0 registry's unrebuildable capabilities. Neural operators
    # stay listed: only Carbon-tested ones are served, by catalog id
    # (Validator, 2026-10-20).
    unsupported = [
        {
            "id": value["id"],
            "status": value["status"],
            "blocker": (
                "only Carbon-tested ones, by catalog id; miner-authored "
                "neural operators are not rebuildable"
                if value["id"] == "model_family.neural_operator"
                else value["blocker"]
            ),
            "summary": value["summary"],
        }
        for value in capabilities
        if value["status"] != "rebuildable_development"
    ]
    return {
        "identity": "carbon.electric-motor-magnetics-catalog." + version,
        "contract_digest": contract.digest,
        "task": (
            "Predict the 60-angle electromagnetic torque curve over one "
            "15-degree rotor period for the registered two-dimensional "
            "surface-PM motor cross-section."
        ),
        "intended_use": (
            "Public DEVELOPMENT construction and practice only; not a three-"
            "dimensional end-effect, thermal, transient-drive, hardware or "
            "customer-acceptance model."
        ),
        "interface": {
            "inputs": list(domain.INPUTS),
            "outputs": {"torque_nm": [domain.ANGLE_STEPS]},
            "conventions": (
                "millimetres, degrees, A/mm^2 and N.m; torque has 60 evenly "
                "spaced samples over the 15-degree periodic rotor sweep"
            ),
        },
        "public_material": {
            "names": [
                "objective",
                "capabilities",
                "training_data",
                "practice_data",
                "reference_method",
                "catalog",
                "construction_kit",
                "scaffold_recipe",
            ],
            "access": (
                "start_research_task kind=workspace action=public_material with "
                "arguments_json encoding one listed name"
            ),
            "train": {"path": TRAIN_PATH, "cases": TRAIN_CASES, "sha256": TRAIN_SHA256},
            "practice": {"cases": PRACTICE_CASES, "adaptively_seen": True},
        },
        "models": {
            "rebuildable": [
                {
                    "id": "catalog." + catalog_id,
                    "selector": catalog_id,
                    "summary": catalog_listing.summary(
                        catalog_id, entry["backbone"], MOTOR_CHALLENGE, version
                    ),
                }
                for catalog_id, entry in catalog["entries"].items()
            ],
            "catalog": catalog,
            "note": (
                "Choose a backbone by catalog_id; its settings are that "
                "bundle's own, defaulted to the tested baseline's."
            ),
        },
        "prediction_contract": {
            "per_case": {"torque_nm": [domain.ANGLE_STEPS]},
            "produced_by": (
                "Carbon builds the named tested bundle on the pinned public "
                "TRAIN; a miner supplies neither code, predictions nor weights"
            ),
        },
        "execution": {
            "backend": "PyTorch in the pinned Linux CPU isolated C-03 worker",
            "worker_image": "the campaign's verified C-03 PyTorch CPU worker image",
            "gpu_lane": False,
            "recipe": "carbon.construction-recipe.v1, source kind catalog",
        },
        "limits": {
            "budget": "the campaign ledger; discovery charges nothing",
            "training": "the rebuild's wall time is the only training limit",
        },
        "workflow": {
            "validate": "the recipe door refuses an unknown entry or setting by code",
            "practice": "Carbon builds the bundle on public TRAIN, scores public PRACTICE",
            "freeze": "the campaign freezes one practised recipe",
            "submit": "the signed construction receiver rebuilds and judges it",
        },
        "exam": {
            "gates": [gate.gate_id for gate in exam.GATES],
            "components": list(exam.COMPONENTS),
            "rule": "development normalized prediction error; lower is better",
            "qualification": False,
        },
        "feedback": {
            "practice": "aggregate public-practice components and typed gates",
            "evaluation": "the receiver's judged feedback",
        },
        "examples": [{"recipe": catalog_recipe(version=version)}],
        "unsupported": unsupported,
        "exclusion_scope": {
            "catalog": "Carbon's tested bundles only; miner source stays closed",
            "excluded": [
                "participant code or weights",
                "reference-solver reuse",
                "private, decision-study or confirmation evidence",
                "three-dimensional end effects, thermal and drive transients",
            ],
        },
    }
