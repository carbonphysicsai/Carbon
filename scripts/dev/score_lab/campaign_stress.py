"""Named analytic toy stress scenarios with explicit patch assumptions."""

from __future__ import annotations

import copy

from . import campaign_sweep, physics
from .core import LabRefused, canonical_sha

SCHEMA = "carbon.dev.score-lab-stress-scenarios.v1"


def configs(base, scenarios):
    physics.validate_config(base)
    if (
        not isinstance(scenarios, dict)
        or scenarios.get("schema") != SCHEMA
        or not isinstance(scenarios.get("scenarios"), list)
        or not scenarios["scenarios"]
    ):
        raise LabRefused("stress_scenarios_schema")
    seen = set()
    for scenario in scenarios["scenarios"]:
        if (
            not isinstance(scenario, dict)
            or set(scenario) != {"id", "edits", "limit"}
            or type(scenario["id"]) is not str
            or not scenario["id"]
            or scenario["id"] in seen
            or not isinstance(scenario["edits"], dict)
            or not scenario["edits"]
            or type(scenario["limit"]) is not str
            or not scenario["limit"]
        ):
            raise LabRefused("stress_scenario")
        seen.add(scenario["id"])
        config = copy.deepcopy(base)
        for path, value in scenario["edits"].items():
            node, key = campaign_sweep._target(config, path)
            node[key] = copy.deepcopy(value)
        try:
            physics.validate_config(config)
        except LabRefused:
            raise LabRefused("stress_config_invalid") from None
        yield scenario["id"], scenario["limit"], config


def evaluate(base, scenarios, specs, digest, *, component_spec=None):
    rows = []
    for name, limit, config in configs(base, scenarios):
        measured = physics.evaluate(
            config, specs, digest, component_spec=component_spec
        )
        rows.append(
            {
                "id": name,
                "limit": limit,
                "config_sha256": canonical_sha(config),
                "measured_rows": measured["measured_rows"],
                "rows": measured["rows"],
            }
        )
    return {
        "schema": "carbon.dev.score-lab-stress-results.v1",
        "scope": "SYNTHETIC_DEVELOPMENT",
        "base_config_sha256": canonical_sha(base),
        "scenarios_sha256": canonical_sha(scenarios),
        "candidates_sha256": digest,
        "component_spec_sha256": (
            canonical_sha(component_spec) if component_spec is not None else None
        ),
        "rows": rows,
        "selection": None,
    }
