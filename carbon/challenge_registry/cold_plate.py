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
