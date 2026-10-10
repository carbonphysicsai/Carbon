"""Proposed physical-case manifests and conservative reuse/cost accounting."""

import math
import re

from carbon.challenge_pipeline.onboarding import packet
from carbon.design_search import tasks

SCHEMA = "carbon.onboarding.panel-seed.v1"
PIN_KEYS = {"solver", "environment", "materials", "observer", "geometry_grammar"}


def coordinates(value):
    if type(value) is not dict or not value or len(value) > 40:
        raise packet.DraftError("bounded explicit coordinates required")
    for key, x in value.items():
        if type(key) is not str or not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_]{0,79}", key):
            raise packet.DraftError("coordinate name required")
        if type(x) in (int, float):
            if not math.isfinite(x):
                raise packet.DraftError("finite coordinates required")
        elif type(x) is not str or not x or len(x) > 200:
            raise packet.DraftError("numeric or named coordinates required")


def validate_seed(seed, challenge):
    if (
        type(seed) is not dict
        or set(seed)
        != {
            "schema",
            "challenge",
            "designs",
            "strata",
            "rungs",
            "pins",
            "cost_cpu_seconds",
        }
        or seed["schema"] != SCHEMA
        or seed["challenge"] != challenge
    ):
        raise packet.DraftError("closed matching panel seed required")
    for name in ("designs", "strata", "rungs"):
        rows = seed[name]
        if type(rows) is not list or not rows or len(rows) > 1000:
            raise packet.DraftError("bounded nonempty manifest lists required")
        ids = set()
        for row in rows:
            field = {"designs": "coordinates", "strata": "inputs", "rungs": "settings"}[
                name
            ]
            if (
                type(row) is not dict
                or set(row) != {"id", field}
                or type(row["id"]) is not str
                or row["id"] in ids
            ):
                raise packet.DraftError("unique explicit manifest rows required")
            if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,79}", str(row["id"])):
                raise packet.DraftError("planning id required")
            ids.add(row["id"])
            coordinates(row[field])
    if len(seed["designs"]) * len(seed["strata"]) * len(seed["rungs"]) > 10000:
        raise packet.DraftError("manifest expansion exceeds bound")
    pins = seed["pins"]
    if type(pins) is not dict or set(pins) != PIN_KEYS:
        raise packet.DraftError("complete physical/observer pins required")
    for value in pins.values():
        if value is not None:
            packet.text(value)
    costs = seed["cost_cpu_seconds"]
    if type(costs) is not dict or set(costs) - {r["id"] for r in seed["rungs"]}:
        raise packet.DraftError("costs must name proposed rungs")
    for value in costs.values():
        if (
            type(value) is not dict
            or set(value) != {"seconds", "basis"}
            or type(value["seconds"]) not in (int, float)
            or not math.isfinite(value["seconds"])
            or value["seconds"] <= 0
        ):
            raise packet.DraftError("positive finite CPU estimate with basis required")
        packet.text(value["basis"])
    rung_costs = {}
    for rung in seed["rungs"]:
        key = tasks.digest(rung["settings"])
        cost = costs.get(rung["id"], {}).get("seconds")
        if key in rung_costs and rung_costs[key] != cost:
            raise packet.DraftError(
                "identical rung settings cannot have conflicting costs"
            )
        rung_costs[key] = cost


def generate(draft, *, seed=None, reuse=None):
    packet.validate_packet(draft)
    result = {
        "schema": "carbon.onboarding.panel-draft.v1",
        "challenge": draft["challenge"],
        "maturity": "DRAFT_ONLY",
        "registration_status": "PROPOSED_NOT_DISPATCHABLE",
        "buyer_decision": draft["fields"]["decision"],
        "strata_basis": draft["fields"]["strata"],
        "designs": None,
        "strata": None,
        "cases": [],
        "case_count": None,
        "boundary_designs": {
            "status": "HUMAN_INPUT",
            "recommendation": "Register physical-coordinate brackets near each hard limit in every stratum; at least 5 settled feasible AND 5 settled infeasible within TWO accepted refinement bands; no guaranteed yield, no widening",
            "intervals_and_frontier_results": "NOT_DEMONSTRATED",
        },
        "value_measures": [
            "complete feasible answer",
            "both-side contested boundaries",
            "buyer-unit margin spread",
            "best/equivalent answer changes",
            "cheap-baseline decision regret",
            "CPU/wall/memory/failures",
        ],
        "reuse_check": {
            "status": "UNKNOWN_NO_INDEX",
            "completed_matches": 0,
            "scheduled_matches": 0,
        },
        "cost": {
            "status": "UNKNOWN",
            "cpu_hours_if_reuse_accepted": None,
            "cpu_hours_without_reuse": None,
            "billed_node_hours": None,
            "eur": None,
            "omitted": [
                "failures",
                "setup",
                "witnesses",
                "new frontier actions",
                "storage",
                "tax",
                "retained verification",
            ],
        },
        "held_closed": "No solver, bank draw, hidden data, registration adoption or spend; DC accepts geometry/pins/reuse before execution",
    }
    if seed is None:
        return result
    validate_seed(seed, draft["challenge"])
    complete = all(
        v is not None and "HUMAN_INPUT" not in v for v in seed["pins"].values()
    )
    reuse_index = {}
    if reuse is not None:
        if type(reuse) is not list or len(reuse) > 10000:
            raise packet.DraftError("bounded reuse index required")
        for row in reuse:
            if (
                type(row) is not dict
                or set(row) != {"identity", "state", "receipt"}
                or row["state"] not in {"COMPLETED", "SCHEDULED"}
                or not re.fullmatch(r"sha256:[0-9a-f]{64}", str(row["identity"]))
                or row["identity"] in reuse_index
            ):
                raise packet.DraftError(
                    "unique full identity and retained receipt required"
                )
            packet.text(row["receipt"])
            reuse_index[row["identity"]] = row
        result["reuse_check"][
            "status"
        ] = "RECEIPT_DECLARED_MATCHES_REQUIRE_DC_ACCEPTANCE"
    seen = set()
    for design in seed["designs"]:
        for stratum in seed["strata"]:
            for rung in seed["rungs"]:
                body = {
                    "challenge": draft["challenge"],
                    "coordinates": design["coordinates"],
                    "inputs": stratum["inputs"],
                    "rung_settings": rung["settings"],
                    "pins": seed["pins"],
                }
                proposal_id = tasks.digest(body)
                if proposal_id in seen:
                    continue
                seen.add(proposal_id)
                identity = proposal_id if complete else None
                match = reuse_index.get(identity)
                state = (
                    match["state"]
                    if match
                    else "NO_MATCH" if reuse is not None and complete else "UNKNOWN"
                )
                if match:
                    counter = (
                        "completed_matches"
                        if state == "COMPLETED"
                        else "scheduled_matches"
                    )
                    result["reuse_check"][counter] += 1
                result["cases"].append(
                    {
                        "proposal_digest": proposal_id,
                        "physical_identity": identity,
                        "design": design["id"],
                        "stratum": stratum["id"],
                        "rung": rung["id"],
                        "reuse_recommendation": state,
                        "receipt": match["receipt"] if match else None,
                    }
                )
    result["designs"] = seed["designs"]
    result["strata"] = seed["strata"]
    result["seed_digest"] = tasks.digest(seed)
    result["rungs"] = seed["rungs"]
    result["pins"] = seed["pins"]
    result["case_count"] = len(result["cases"])
    if all(r["id"] in seed["cost_cpu_seconds"] for r in seed["rungs"]):
        seconds = seed["cost_cpu_seconds"]
        total = sum(seconds[r["rung"]]["seconds"] for r in result["cases"])
        new = sum(
            seconds[r["rung"]]["seconds"]
            for r in result["cases"]
            if r["reuse_recommendation"] not in {"COMPLETED", "SCHEDULED"}
        )
        result["cost"].update(
            {
                "status": "PLANNING_ASSUMPTIONS_NOT_MEASURED_BY_TOOL",
                "cpu_hours_without_reuse": total / 3600,
                "cpu_hours_if_reuse_accepted": new / 3600,
                "per_rung_basis": seconds,
            }
        )
    return result
