"""Fail-closed producer export adapters for the eight design-power families.

Data Collection owns the solved panel and its registrations. This module only
maps a complete, sealed producer export to the existing neutral task/power
inputs. It supplies no physical objective, limit, population or solve value.
"""

from __future__ import annotations

from carbon.design_search import (
    diversity,
    indexed,
    indexed_power,
    power,
    power_accumulation,
    reference_resolution,
    tasks,
)

EXPORT_SCHEMA = "carbon.design-search.solved-panel-export.v1"
DESIGN_BANK_SNAPSHOT_SCHEMA = "carbon.design-search.design-bank-snapshot.v1"
REPORT_SCHEMA = "carbon.design-search.panel-power-report.v1"
FAMILIES = (
    "battery-v3",
    "motor",
    "cooling-cell",
    "f02",
    "f06",
    "f08",
    "f13",
    "f17",
)


def seal_export(body):
    """Producer helper; sealing bytes does not qualify their references."""
    if type(body) is not dict or body.get("schema") != EXPORT_SCHEMA:
        raise tasks.TaskError("solved-panel export schema required")
    return {**body, "export_digest": tasks.digest(body)}


def seal_design_bank_snapshot(body):
    """Producer helper for records shaped like DesignBank question leaves."""
    if type(body) is not dict or body.get("schema") != DESIGN_BANK_SNAPSHOT_SCHEMA:
        raise tasks.TaskError("design-bank snapshot schema required")
    return {**body, "snapshot_digest": tasks.digest(body)}


def _from_design_bank_snapshot(snapshot):
    if (
        type(snapshot) is not dict
        or set(snapshot)
        not in (
            {
                "schema",
                "sealed",
                "family",
                "challenge_id",
                "exposure_unit",
                "exposure",
                "window_sampling",
                "cases",
                "laws",
                "snapshot_digest",
            },
            {
                "schema",
                "sealed",
                "family",
                "challenge_id",
                "exposure_unit",
                "exposure",
                "window_sampling",
                "cases",
                "laws",
                "snapshot_digest",
                "refinement_rule",
            },
        )
        or snapshot["schema"] != DESIGN_BANK_SNAPSHOT_SCHEMA
        or snapshot["sealed"] is not True
        or snapshot["snapshot_digest"]
        != tasks.digest(
            {key: value for key, value in snapshot.items() if key != "snapshot_digest"}
        )
        or type(snapshot["cases"]) is not list
        or type(snapshot["exposure"]) is not list
    ):
        raise tasks.TaskError("sealed design-bank snapshot required")
    questions = []
    for row in snapshot["cases"]:
        if (
            type(row) is not dict
            or set(row)
            not in (
                {
                    "case_id",
                    "inputs",
                    "reference",
                    "support_case",
                    "close_call",
                    "refinement_demand",
                },
                {
                    "case_id",
                    "inputs",
                    "reference",
                    "support_case",
                    "close_call",
                    "refinement_demand",
                    "settled",
                },
            )
            or type(row["inputs"]) is not dict
            or set(row["inputs"]) != {"task", "task_digest", "draw"}
            or type(row["inputs"]["task"]) is not dict
            or type(row["reference"]) is not dict
            or row["reference"].get("status") != "OK"
            or row["inputs"]["task_digest"] != row["inputs"]["task"].get("task_digest")
        ):
            raise tasks.TaskError("complete OK design-bank question required")
        reference = row["reference"]
        if set(reference) == {"status", "panel"}:
            panel = reference["panel"]
        elif set(reference) == {"status", "per_index"}:
            panel = reference["per_index"]
        else:
            raise tasks.TaskError("complete design-bank reference required")
        questions.append(
            {
                "case": row["case_id"],
                "support_case": row["support_case"],
                "task": row["inputs"]["task"],
                "reference": panel,
                "close_call": row["close_call"],
                "refinement_demand": row["refinement_demand"],
                **({"settled": row["settled"]} if "settled" in row else {}),
            }
        )
    exposure = []
    for row in snapshot["exposure"]:
        if type(row) is not dict or set(row) != {"case_id", "limit", "used"}:
            raise tasks.TaskError("design-bank exposure row required")
        exposure.append(
            {"case": row["case_id"], "limit": row["limit"], "used": row["used"]}
        )
    return seal_export(
        {
            "schema": EXPORT_SCHEMA,
            "sealed": True,
            "family": snapshot["family"],
            "challenge_id": snapshot["challenge_id"],
            "exposure_unit": snapshot["exposure_unit"],
            "exposure": exposure,
            "window_sampling": snapshot["window_sampling"],
            "questions": questions,
            "laws": snapshot["laws"],
            **(
                {"refinement_rule": snapshot["refinement_rule"]}
                if "refinement_rule" in snapshot
                else {}
            ),
        }
    )


def _plain(entry, challenge_id):
    registered = entry["task"]
    if (
        type(registered) is not dict
        or registered.get("schema") != tasks.RUNNABLE_SCHEMA
    ):
        raise tasks.TaskError("registered plain design task required")
    tasks._verify_task_digest(registered)
    if registered["identity"]["challenge"] != challenge_id:
        raise tasks.TaskError("panel task Challenge identity differs")
    panel = power._panel(entry["reference"], registered)
    if "settled" in entry:
        truth = reference_resolution.assessed(registered, panel, entry["settled"])
        state, winner = reference_resolution.state_and_winner(registered, truth)
    else:
        truth = tasks.assess(registered, panel, reference=True)
        resolved = all(row["feasible"] is not None for row in truth.values())
        state = tasks.reference_state(registered, truth) if resolved else "UNRESOLVED"
        winner = tasks.select(registered, truth) if resolved else None
    return (
        state,
        winner,
        "power_cases",
    )


def _indexed(entry, challenge_id):
    registered = entry["task"]
    indexed.validate_indexed(registered)
    if registered["identity"]["challenge"] != challenge_id:
        raise tasks.TaskError("indexed panel Challenge identity differs")
    panels = indexed_power._panels(entry["reference"], registered)
    state, winner = indexed_power._state_and_winner(
        registered, panels, settled=entry.get("settled")
    )
    return state, winner, "indexed_power_cases"


def _battery_v3(entry, challenge_id):
    return _indexed(entry, challenge_id)


def _motor(entry, challenge_id):
    return _plain(entry, challenge_id)


def _cooling_cell(entry, challenge_id):
    return _plain(entry, challenge_id)


def _f02(entry, challenge_id):
    # The registered buyer decision may be a plain burst or an indexed
    # scenario schedule. Its task, never the adapter, chooses that grammar.
    if entry["task"].get("schema") == tasks.INDEXED_SCHEMA:
        return _indexed(entry, challenge_id)
    return _plain(entry, challenge_id)


def _f06(entry, challenge_id):
    return _plain(entry, challenge_id)


def _f08(entry, challenge_id):
    return _plain(entry, challenge_id)


def _f13(entry, challenge_id):
    return _plain(entry, challenge_id)


def _f17(entry, challenge_id):
    return _plain(entry, challenge_id)


_ADAPTERS = {
    "battery-v3": _battery_v3,
    "motor": _motor,
    "cooling-cell": _cooling_cell,
    "f02": _f02,
    "f06": _f06,
    "f08": _f08,
    "f13": _f13,
    "f17": _f17,
}


def adapt_export(export):
    """Build sealed neutral power inputs from a producer-owned solved panel."""
    if type(export) is dict and export.get("schema") == DESIGN_BANK_SNAPSHOT_SCHEMA:
        export = _from_design_bank_snapshot(export)
    if (
        type(export) is not dict
        or set(export)
        not in (
            {
                "schema",
                "sealed",
                "family",
                "challenge_id",
                "exposure_unit",
                "exposure",
                "window_sampling",
                "questions",
                "laws",
                "export_digest",
            },
            {
                "schema",
                "sealed",
                "family",
                "challenge_id",
                "exposure_unit",
                "exposure",
                "window_sampling",
                "questions",
                "laws",
                "export_digest",
                "refinement_rule",
            },
        )
        or export["schema"] != EXPORT_SCHEMA
        or export["sealed"] is not True
        or export["family"] not in FAMILIES
        or type(export["challenge_id"]) is not str
        or not export["challenge_id"]
        or export["exposure_unit"] != power_accumulation.EXPOSURE_UNIT
        or type(export["questions"]) is not list
        or not export["questions"]
        or type(export["laws"]) is not list
        or not export["laws"]
        or export["export_digest"]
        != tasks.digest({k: v for k, v in export.items() if k != "export_digest"})
    ):
        raise tasks.TaskError("sealed registered solved-panel export required")
    if "refinement_rule" in export:
        reference_resolution.validate_rule(export["refinement_rule"])
    cases = []
    rows = []
    known_good = []
    mode = None
    seen = set()
    for entry in export["questions"]:
        if (
            type(entry) is not dict
            or set(entry)
            != (
                {
                    "case",
                    "support_case",
                    "task",
                    "reference",
                    "close_call",
                    "refinement_demand",
                }
                | ({"settled"} if "refinement_rule" in export else set())
            )
            or type(entry["case"]) is not str
            or not entry["case"]
            or entry["case"] in seen
            or type(entry["support_case"]) is not str
            or not entry["support_case"]
            or type(entry["close_call"]) is not bool
            or type(entry["refinement_demand"]) is not bool
            or type(entry["task"]) is not dict
        ):
            raise tasks.TaskError("complete producer question required")
        seen.add(entry["case"])
        state, winner, current_mode = _ADAPTERS[export["family"]](
            entry, export["challenge_id"]
        )
        if mode is None:
            mode = current_mode
        elif mode != current_mode:
            raise tasks.TaskError("one producer export must use one decision type")
        cases.append(
            {
                "case": entry["case"],
                "state": state,
                "winner": winner,
                "close_call": entry["close_call"],
                "refinement_demand": entry["refinement_demand"],
            }
        )
        rows.append(
            {
                "case": entry["case"],
                "support_case": entry["support_case"],
                "task": entry["task"],
                "reference": entry["reference"],
                **({"settled": entry["settled"]} if "settled" in entry else {}),
            }
        )
        known_good.append({"case": entry["case"], "predictions": entry["reference"]})
    bank = diversity.seal_bank(
        {
            "schema": diversity.BANK_SCHEMA,
            "sealed": True,
            "exposure_unit": export["exposure_unit"],
            "case_exposure": export["exposure"],
            "window_sampling": export["window_sampling"],
            "cases": cases,
            mode: rows,
            **(
                {"refinement_rule": export["refinement_rule"]}
                if "refinement_rule" in export
                else {}
            ),
        }
    )
    laws = {}
    for law in export["laws"]:
        if type(law) is not dict or law.get("kind") in laws:
            raise tasks.TaskError("one law per registered kind required")
        diversity.diversity_report(bank, law)
        laws[law["kind"]] = law
    if len({law["batch_size"] for law in laws.values()}) != 1:
        raise tasks.TaskError("panel laws need the same batch size")
    return (
        bank,
        laws.get("grid"),
        laws.get("continuous"),
        power.register_good_predictor(known_good),
    )


def panel_power_report(
    export,
    control_registration,
    accumulation,
    *,
    alpha,
    power_target,
    simulation_seed,
    replicates,
    max_questions,
):
    """Return only family identity and neutral aggregate power diagnostics."""
    bank, grid, continuous, good = adapt_export(export)
    result = power.power_report(
        bank,
        grid,
        continuous,
        control_registration,
        good,
        alpha=alpha,
        power_target=power_target,
        simulation_seed=simulation_seed,
        replicates=replicates,
        max_questions=max_questions,
        accumulation=accumulation,
    )
    return {
        "schema": REPORT_SCHEMA,
        "material": "DEVELOPMENT",
        "family": export["family"],
        "power": result,
        "claims": {"power_qualified": False, "score_use_approved": False},
    }
