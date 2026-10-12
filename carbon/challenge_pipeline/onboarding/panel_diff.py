"""Self-contained PUBLIC_DEVELOPMENT tuple/reuse diff, never a dispatcher."""

import argparse
import itertools
import json
import re
from copy import deepcopy
from pathlib import Path

from carbon.challenge_pipeline.onboarding import packet, panel
from carbon.design_search import tasks

BODY_KEYS = {"challenge", "coordinates", "inputs", "rung_settings", "pins"}
SCHEMA = "carbon.onboarding.public-reuse-inventory.v1"


def body(family, design, condition, rung, pins):
    return deepcopy(
        {
            "challenge": family,
            "coordinates": design,
            "inputs": condition,
            "rung_settings": rung,
            "pins": pins,
        }
    )


def pins_complete(pins):
    return all(
        type(v) is str and re.fullmatch(r"sha256:[0-9a-f]{64}", v)
        for v in pins.values()
    )


def inventory_check(inventory, family):
    if (
        type(inventory) is not dict
        or set(inventory)
        != {"schema", "challenge", "scope", "coverage", "basis", "records"}
        or inventory["schema"] != SCHEMA
        or inventory["challenge"] != family
        or inventory["scope"] != "PUBLIC_DEVELOPMENT"
        or inventory["coverage"] not in {"COMPLETE_FOR_REQUESTED_PINS", "PARTIAL"}
        or type(inventory["records"]) is not list
        or len(inventory["records"]) > 10000
    ):
        raise packet.DraftError("closed matching public inventory required")
    packet.text(inventory["basis"])
    index = {}
    for row in inventory["records"]:
        if (
            type(row) is not dict
            or set(row) != {"tuple", "state", "receipt"}
            or row["state"] not in {"COMPLETED", "SCHEDULED"}
            or type(row["tuple"]) is not dict
            or set(row["tuple"]) != BODY_KEYS
            or row["tuple"]["challenge"] != family
        ):
            raise packet.DraftError("full matching tuple and receipt required")
        packet.text(row["receipt"])
        for field in ("coordinates", "inputs", "rung_settings"):
            panel.coordinates(row["tuple"][field])
        pins = row["tuple"]["pins"]
        if (
            type(pins) is not dict
            or set(pins) != panel.PIN_KEYS
            or not pins_complete(pins)
        ):
            raise packet.DraftError("inventory requires full immutable pins")
        identity = tasks.digest(row["tuple"])
        records = index.setdefault(identity, [])
        if any(
            r["state"] == row["state"] and r["receipt"] == row["receipt"]
            for r in records
        ):
            raise packet.DraftError("duplicate inventory receipt")
        records.append(row)
    return index


def generate(draft, *, seed=None, inventory=None):
    old = panel.generate(draft, seed=seed)
    output = {
        "schema": "carbon.onboarding.panel-registration-diff.v1",
        "challenge": draft["challenge"],
        "maturity": "PREPARATION_ONLY",
        "basis": {
            "panel_generator": old["schema"],
            "inventory_digest": (
                tasks.digest(inventory) if inventory is not None else None
            ),
        },
        "registration_input_ready": False,
        "registration_adopted": False,
        "execution_authorized": False,
        "reuse_verified_by_tool": False,
        "tuples": [],
        "new": [],
        "completed": [],
        "scheduled": [],
        "unseen": [],
        "conflicts": [],
        "missing_pins": sorted(panel.PIN_KEYS),
        "unused_inventory_identities": None,
        "cost": {"cpu_hours_new_only": None, "eur": None, "basis": "UNKNOWN"},
        "held_closed": "DC verifies inventory receipts and adopts registration; science support, image availability, reference acceptance and exact grant remain independent. No solver/spend or exposure renewal.",
    }
    index = (
        inventory_check(inventory, draft["challenge"]) if inventory is not None else {}
    )
    if seed is None:
        output["basis"]["case_count"] = None
        return output
    output["missing_pins"] = [
        key for key, value in seed["pins"].items() if not pins_complete({key: value})
    ]
    lookup = {}
    for d, c, r in itertools.product(seed["designs"], seed["strata"], seed["rungs"]):
        physical = body(
            draft["challenge"],
            d["coordinates"],
            c["inputs"],
            r["settings"],
            seed["pins"],
        )
        identity = tasks.digest(physical)
        alias = {"design": d["id"], "stratum": c["id"], "rung": r["id"]}
        if identity in lookup:
            lookup[identity]["aliases"].append(alias)
            continue
        receipts = index.get(identity, []) if not output["missing_pins"] else []
        states = {row["state"] for row in receipts}
        category = (
            "conflicts"
            if len(states) > 1
            else (
                "completed"
                if states == {"COMPLETED"}
                else (
                    "scheduled"
                    if states == {"SCHEDULED"}
                    else (
                        "new"
                        if inventory is not None
                        and inventory["coverage"] == "COMPLETE_FOR_REQUESTED_PINS"
                        and not output["missing_pins"]
                        else "unseen"
                    )
                )
            )
        )
        entry = {
            "physical_identity": identity if not output["missing_pins"] else None,
            "proposal_digest": identity,
            "tuple": physical,
            "aliases": [alias],
            "reuse_state": category.upper(),
            "receipts": [row["receipt"] for row in receipts],
        }
        lookup[identity] = entry
        output["tuples"].append(entry)
        output[category].append(identity)
    output["basis"].update(
        seed_digest=tasks.digest(seed),
        requested_aliases=len(seed["designs"])
        * len(seed["strata"])
        * len(seed["rungs"]),
        case_count=len(lookup),
        inventory_coverage=(
            inventory["coverage"] if inventory is not None else "UNKNOWN_NO_INDEX"
        ),
        inventory_basis=inventory["basis"] if inventory is not None else None,
    )
    output["unused_inventory_identities"] = len(set(index) - set(lookup))
    output["registration_input_ready"] = (
        not output["missing_pins"] and not output["conflicts"] and not output["unseen"]
    )
    if output["registration_input_ready"]:
        costs = seed["cost_cpu_seconds"]
        rungs = [lookup[i]["aliases"][0]["rung"] for i in output["new"]]
        if all(r in costs for r in rungs):
            output["cost"].update(
                cpu_hours_new_only=sum(costs[r]["seconds"] for r in rungs) / 3600,
                basis="DECLARED_CPU_ESTIMATES_NOT_MEASURED_BY_TOOL_OR_BILLED_WALL; REUSE_REQUIRES_DC_ACCEPTANCE",
            )
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--brief", required=True)
    parser.add_argument("--seed")
    parser.add_argument("--inventory")
    parser.add_argument("--report-only", action="store_true")
    args = parser.parse_args()
    try:

        def read(name):
            if any(
                word in name.lower()
                for word in ("ev5", "journal", "hidden", "protected", "secret")
            ):
                raise packet.DraftError("explicit public source required")
            return packet.read_json(packet.source_path(args.root, name))

        draft = packet.generate(read(args.brief), args.root)
        report = generate(
            draft,
            seed=read(args.seed) if args.seed else None,
            inventory=read(args.inventory) if args.inventory else None,
        )
    except packet.DraftError as exc:
        parser.exit(2, str(exc) + "\n")
    print(json.dumps(report, indent=2, allow_nan=False))
    return 0 if args.report_only or report["registration_input_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
