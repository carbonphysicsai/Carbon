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
