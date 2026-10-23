"""Cold-plate discovery, derived from its executable registrations."""

from __future__ import annotations


def _verdict(strategy):
    from carbon.reconstruction.challenge_contracts import validate_for_challenge

    result = validate_for_challenge(strategy)
    return {
        "valid": result.ok,
        "issues": [{"code": issue.code, "path": issue.path} for issue in result.errors],
    }


def describe():
    from carbon.cold_plate import domain, exam, openfoam, population
    from carbon.cold_plate.challenge import (
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
    from carbon.cold_plate.contracts import implementation_digest
    from carbon.reconstruction.capability_registry import (
        COLD_PLATE_CHALLENGE,
        COLD_PLATE_LENGTH_CHOICES,
        COLD_PLATE_LENGTHS,
        COLD_PLATE_RIDGE_CHOICES,
        COLD_PLATE_RIDGES,
        catalog_surfaces,
        contract,
        public_registry,
    )

    registered = contract(COLD_PLATE_CHALLENGE)
    capabilities = public_registry(COLD_PLATE_CHALLENGE)["capabilities"]
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
            COLD_PLATE_CHALLENGE
        ).items()
    }
    scaffold = {
        "schema_version": "1.0",
        "challenge_id": COLD_PLATE_CHALLENGE,
        "backbone": "kernel_ridge",
        "parameters": {"length": "length_8", "ridge": "ridge_1e_6"},
    }
    interface = interface_document()
    return {
        "identity": registered.identity,
        "contract_digest": registered.digest,
        "task": (
            "Predict peak heated-face temperature, the 30-segment axial "
            "temperature profile and channel pressure drop for the registered "
            "steady periodic cold-plate cell."
        ),
        "intended_use": (
            "Public DEVELOPMENT construction and practice only; not a manifold, "
            "transient, product or customer-acceptance model."
        ),
        "interface": {
            **interface,
            "conventions": (
                "millimetres, litres/minute/kW, degrees C, watts and pascals; "
                "channels follow the 30 mm footprint"
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
                "counted decision-study CFD artifacts",
                "private-pool cases or references",
                "future confirmation cases, seeds or metadata",
            ],
        },
        "reference": {
            "method": "steady OpenFOAM periodic-cell conjugate heat transfer",
            "image": openfoam.IMAGE,
            "applicability": {
                "fluid_temperature_c": list(domain.PG25_VALID_C),
                "reynolds_max": domain.RE_LAMINAR_MAX,
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
                "length": dict(
                    zip(
                        COLD_PLATE_LENGTH_CHOICES,
                        COLD_PLATE_LENGTHS,
                        strict=True,
                    )
                ),
                "ridge": dict(
                    zip(
                        COLD_PLATE_RIDGE_CHOICES,
                        COLD_PLATE_RIDGES,
                        strict=True,
                    )
                ),
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
                "downstream cooling validator/scoring integration is a separate "
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
            "screen": dict(population.SCREEN),
            "authority": "provisional DEVELOPMENT, not qualified",
        },
        "exclusion_scope": {
            "level_0": "declarative kernel-ridge settings only",
            "excluded": [
                "participant code or weights",
                "reference-solver reuse",
                "private or counted evidence",
                "manifolds, transients and two-dimensional chiplet maps",
            ],
        },
    }


def catalog_recipe(catalog_id=None, *, version):
    """A ready catalog recipe for Cooling `version` (a catalog version; no
    default): the version's kit, one catalog entry (`catalog_id`, or the first
    the version offers), its tested baseline settings (empty: unset settings
    keep the baseline's).

    While the version's catalog is empty (no Cooling entry is tested yet) and
    no id is named, this is an unfilled template whose `catalog_id` and
    `output.format` are None: an explicit gap, never a recipe that runs. A
    named id the version does not offer is refused (`catalog_entry_unknown`).
    """
    from carbon.backbone_catalog import listing, served
    from carbon.backbone_catalog.entries import CatalogRefused
    from carbon.challenge_kit import physical_public
    from carbon.challenge_kit.served_versions import serves_catalog
    from carbon.reconstruction.capability_registry import COLD_PLATE_CHALLENGE

    if not serves_catalog(COLD_PLATE_CHALLENGE, version):
        raise ValueError("cooling catalog version required")
    kit = physical_public.construction_kit(COLD_PLATE_CHALLENGE, version)
    if catalog_id is None:
        offered = listing.entries(COLD_PLATE_CHALLENGE, version)
        item = offered[0] if offered else None
    else:
        item = listing.entry(catalog_id, COLD_PLATE_CHALLENGE, version)
        if item is None:
            raise CatalogRefused(
                "catalog_entry_unknown",
                f"{catalog_id!r} is not in this Challenge version's catalog",
            )
    return {
        "schema": "carbon.construction-recipe.v1",
        "challenge": kit,
        "source": {
            "kind": "catalog",
            "catalog_id": None if item is None else item["catalog_id"],
            "catalog_digest": served.digest(COLD_PLATE_CHALLENGE, version),
        },
        "procedure": {
            "entrypoint": None,
            "configuration": {},
            "train_use": {},
            "initial_state": None,
        },
        "output": {
            "format": None if item is None else item["output_format"],
            "interface_digest": kit["interface_digest"],
        },
    }


def describe_catalog(version):
    """Cooling's catalog version: Carbon's tested backbones by catalog id,
    built and judged as the Carbon bundle each names, on the direct recipe
    path (as Motor's `describe_catalog`)."""
    from carbon.backbone_catalog import served
    from carbon.cold_plate import domain, exam
    from carbon.cold_plate.challenge import (
        PRACTICE_CASES,
        PUBLIC_OUTPUTS,
        TRAIN_CASES,
        TRAIN_PATH,
        TRAIN_SHA256,
    )
    from carbon.reconstruction.capability_registry import (
        COLD_PLATE_CHALLENGE,
        public_registry,
    )
    from carbon.reconstruction.served_recipe_contract import registered

    contract = registered(COLD_PLATE_CHALLENGE, version)
    catalog = served.document(COLD_PLATE_CHALLENGE, version)
    capabilities = public_registry(COLD_PLATE_CHALLENGE)["capabilities"]
    # The Level 0 registry's unrebuildable capabilities. Neural operators
    # stay listed: only Carbon-tested ones are served, by catalog id
    # (Validator, 2026-10-20, Motor's rule).
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
    outputs = {name: list(value["shape"]) for name, value in PUBLIC_OUTPUTS.items()}
    return {
        "identity": "carbon.chip-cold-plate-catalog." + version,
        "contract_digest": contract.digest,
        "task": (
            "Predict peak heated-face temperature, the 30-segment axial "
            "temperature profile and channel pressure drop for the registered "
            "steady periodic cold-plate cell."
        ),
        "intended_use": (
            "Public DEVELOPMENT construction and practice only; not a manifold, "
            "transient, product or customer-acceptance model."
        ),
        "interface": {
            "inputs": list(domain.INPUTS),
            "outputs": outputs,
            "conventions": (
                "millimetres, litres/minute/kW, degrees C, watts and pascals; "
                "channels follow the 30 mm footprint"
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
                    "summary": "Carbon's tested " + entry["backbone"] + " bundle",
                }
                for catalog_id, entry in catalog["entries"].items()
            ],
            "catalog": catalog,
            "note": (
                "Choose a backbone by catalog_id; its settings are that "
                "bundle's own, defaulted to the tested baseline's."
                if catalog["entries"]
                else "No backbone is tested for this version yet: each Cooling "
                "entry needs its own Cooling pair-identity receipt, so nothing "
                "can be practised or submitted until one is added."
            ),
        },
        "prediction_contract": {
            "per_case": outputs,
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
        "examples": (
            [{"recipe": catalog_recipe(version=version)}] if catalog["entries"] else []
        ),
        "unsupported": unsupported,
        "exclusion_scope": {
            "catalog": "Carbon's tested bundles only; miner source stays closed",
            "excluded": [
                "participant code or weights",
                "reference-solver reuse",
                "private or counted evidence",
                "manifolds, transients and two-dimensional chiplet maps",
            ],
        },
    }
