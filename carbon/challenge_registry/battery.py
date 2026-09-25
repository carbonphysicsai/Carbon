"""The battery Challenge's description, derived from what Carbon executes."""

from __future__ import annotations


def _versions():
    from importlib.metadata import PackageNotFoundError, version

    found = {}
    for name in ("jax", "jaxlib", "optax", "numpy"):
        try:
            found[name] = version(name)
        except PackageNotFoundError:
            found[name] = None
    return found


def _verdict(strategy):
    from carbon.reconstruction.challenge_contracts import validate_for_challenge

    result = validate_for_challenge(strategy)
    return {
        "valid": not result.errors,
        "issues": [{"code": i.code, "path": i.path} for i in result.errors],
    }


def describe():
    from carbon.battery import exam
    from carbon.battery.challenge import (
        OCV_TABLE_SHA256,
        TRAIN_V1_CASES,
        TRAIN_V1_SHA256,
    )
    from carbon.battery.contracts import battery_contracts
    from carbon.battery.practice import (
        FEEDBACK_SCHEMA,
        PRACTICE_CASES,
        PRACTICE_SOURCE_SHA256,
    )
    from carbon.battery.research import (
        EVALUATION_FEEDBACK_FIELDS,
        PRACTICE_SECONDS,
        SCAFFOLD,
        SCREENING_FEEDBACK_FIELDS,
        BatteryPublicMaterial,
        objective,
        reference_method,
    )
    from carbon.development_session.research_workspace import (
        MAX_FILE_BYTES,
        MAX_FILES,
        MAX_WORKSPACE_BYTES,
    )
    from carbon.reconstruction.capability_registry import (
        BATTERY_CHALLENGE,
        catalog_surfaces,
        contract,
        public_registry,
    )

    registered = contract(BATTERY_CHALLENGE)
    capabilities = public_registry(BATTERY_CHALLENGE)["capabilities"]
    rebuildable = [c for c in capabilities if c["status"] == "rebuildable_development"]
    unsupported = [
        {
            "id": c["id"],
            "status": c["status"],
            "blocker": c["blocker"],
            "summary": c["summary"],
        }
        for c in capabilities
        if c["status"] != "rebuildable_development"
    ]
    controls = {
        name: {
            "group": group,
            "type": kind,
            "minimum_or_choices": low,
            "maximum": high,
            "default": default,
            "families": list(families) if families else None,
        }
        for name, (group, kind, low, high, default, families) in catalog_surfaces(
            BATTERY_CHALLENGE
        ).items()
    }
    knn = {
        "schema_version": "1.0",
        "challenge_id": BATTERY_CHALLENGE,
        "backbone": "knn",
        "parameters": {"neighbours": 8},
    }
    task = objective()
    return {
        "identity": registered.identity,
        "contract_digest": registered.digest,
        "task": task["task"],
        "intended_use": task["intended_use"],
        "interface": {
            "inputs": task["inputs"],
            "outputs": task["outputs"],
            "conventions": task["conventions"],
        },
        "public_material": {
            "names": list(BatteryPublicMaterial.NAMES),
            "access": (
                "start_research_task kind=workspace action=public_material "
                'arguments={"name": ...}'
            ),
            "train": {
                "version": "v1",
                "cases": TRAIN_V1_CASES,
                "sha256": TRAIN_V1_SHA256,
            },
            "practice": {
                "cases": PRACTICE_CASES,
                "source_sha256": PRACTICE_SOURCE_SHA256,
                "adaptively_seen": True,
            },
            "ocv_table": {"sha256": OCV_TABLE_SHA256},
            "never_disclosed": [
                "private evaluation cases, inputs or references before reveal",
                "seeds, private roots or duplicate maps",
                "per-case evaluation errors",
            ],
        },
        "reference": reference_method(),
        "models": {
            "rebuildable": [
                {"id": c["id"], "selector": c["selector"], "summary": c["summary"]}
                for c in rebuildable
                if c["id"].startswith("model_family.")
            ],
            "controls": controls,
            "note": (
                "Only controls that change what Carbon rebuilds are listed; "
                "every one reaches the executed recipe."
            ),
        },
        "prediction_contract": {
            "per_case": {
                "voltage_v": "121 floats",
                "temperature_c": "121 floats",
                "plating_margin_v": "one float",
                "capacity_ah": "4 floats (cycles 1, 10, 20, 30)",
            },
            "produced_by": (
                "Carbon, by rebuilding the recipe; a miner never uploads "
                "predictions or weights for evaluation"
            ),
        },
        "execution": {
            "backend": "JAX (CPU) through Carbon's battery recipes",
            "environment_pin": battery_contracts()
            .assembly.environment_pins[0]
            .content_digest,
            "host_versions": _versions(),
            "envelope": registered.document()["envelope"],
        },
        "limits": {
            "practice_worker_seconds": PRACTICE_SECONDS,
            "practice_charge": {"research_trials": 1},
            "run_python_seconds": [40, 600],
            "workspace": {
                "max_file_bytes": MAX_FILE_BYTES,
                "max_files": MAX_FILES,
                "max_total_bytes": MAX_WORKSPACE_BYTES,
            },
            "budget": "the campaign's own ledger; discovery charges nothing",
        },
        "workflow": {
            "validate": "dry_validate / compile_strategy (charges nothing)",
            "estimate": "inspect_resources / forecast_resources (static, uncalibrated)",
            "practice": (
                "start_research_task kind=practice; feedback " + FEEDBACK_SCHEMA
            ),
            "progress": "get_research_result; cancel_research_task",
            "freeze": "freeze_candidate needs a completed practice of the same recipe",
            "submit": (
                "submit: a signed battery_submit reaches the validator daemon, "
                "which rebuilds the frozen recipe with Carbon's seed in its "
                "reconstruction worker and screens it on the whole active "
                "private pool; a nominee faces a fresh finalist comparison"
            ),
        },
        "exam": {
            "gates": [g.gate_id for g in exam.GATES],
            "components": list(exam.COMPONENTS),
            "rule": task["rule"],
        },
        "feedback": {
            "practice": FEEDBACK_SCHEMA,
            "evaluation_fields": list(EVALUATION_FEEDBACK_FIELDS),
            "screening_fields": list(SCREENING_FEEDBACK_FIELDS),
        },
        "examples": [
            {"strategy": SCAFFOLD, "admission": _verdict(SCAFFOLD)},
            {"strategy": knn, "admission": _verdict(knn)},
        ],
        "unsupported": unsupported,
        "authority": (
            "DEVELOPMENT, non-paying; no reward, frontier, qualification or "
            "chain authority"
        ),
    }
