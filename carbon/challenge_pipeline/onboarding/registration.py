"""Exact proposed physical tuples and snapshot-scoped DC registration handoff.

No dispatch, solver, spend, adoption or hidden material capabilities.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import re
from pathlib import Path

from carbon.challenge_pipeline.onboarding import packet, panel
from carbon.design_search import tasks

INVENTORY = "carbon.development.solve-inventory-snapshot.v1"
OUTPUT = "carbon.onboarding.registration-handoff.v1"


def seal_inventory(body):
    body = json.loads(json.dumps(body, allow_nan=False))
    return {**body, "inventory_digest": tasks.digest(body)}


def inventory_rows(snapshot, challenge):
    required = {
        "schema",
        "challenge",
        "scope",
        "source_commit",
        "as_of_utc",
        "namespace",
        "rows",
        "inventory_digest",
    }
    if (
        type(snapshot) is not dict
        or set(snapshot) != required
        or snapshot["schema"] != INVENTORY
        or snapshot["challenge"] != challenge
        or snapshot["scope"] != "PUBLIC_DEVELOPMENT"
        or snapshot["inventory_digest"]
        != tasks.digest({k: v for k, v in snapshot.items() if k != "inventory_digest"})
        or not re.fullmatch(r"[0-9a-f]{40}", str(snapshot["source_commit"]))
    ):
        raise packet.DraftError("matched public inventory snapshot required")
    packet.text(snapshot["as_of_utc"])
    try:
        instant = datetime.datetime.fromisoformat(snapshot["as_of_utc"])
    except ValueError as error:
        raise packet.DraftError("inventory UTC snapshot time required") from error
    if instant.utcoffset() != datetime.timedelta(0):
        raise packet.DraftError("inventory UTC snapshot time required")
    packet.text(snapshot["namespace"])
    if type(snapshot["rows"]) is not list or len(snapshot["rows"]) > 10000:
        raise packet.DraftError("bounded complete namespace inventory required")
    output, seen = [], set()
    for row in snapshot["rows"]:
        if (
            type(row) is not dict
            or set(row) != {"identity", "state", "receipt", "body"}
            or row["state"] not in ("COMPLETED", "SCHEDULED")
            or row["identity"] in seen
            or row["identity"] != tasks.digest(row["body"])
        ):
            raise packet.DraftError("unique recomputable inventory identity required")
        body = row["body"]
        if (
            type(body) is not dict
            or set(body)
            != {"challenge", "coordinates", "inputs", "rung_settings", "pins"}
            or body["challenge"] != challenge
            or type(body["pins"]) is not dict
            or set(body["pins"]) != panel.PIN_KEYS
        ):
            raise packet.DraftError("complete matched inventory tuple required")
        for key in ("coordinates", "inputs", "rung_settings"):
            panel.coordinates(body[key])
        for pin in body["pins"].values():
            if pin is None or "HUMAN_INPUT" in packet.text(pin):
                raise packet.DraftError("inventory pins cannot be unknown")
        packet.text(row["receipt"])
        seen.add(row["identity"])
        output.append({k: row[k] for k in ("identity", "state", "receipt")})
    return output


def assemble(draft, seed, inventory=None):
    """Reuse #977: exact proposals are review material, not scientific approval."""
    seed = json.loads(json.dumps(seed, allow_nan=False))
    if draft["challenge"] not in ("cooling-cell", "f02"):
        raise packet.DraftError("ticket owns cooling-cell and f02 only")
    reuse = None if inventory is None else inventory_rows(inventory, draft["challenge"])
    generated = panel.generate(draft, seed=seed, reuse=reuse)
    result = {
        "schema": OUTPUT,
        "challenge": draft["challenge"],
        "seed_digest": generated["seed_digest"],
        "packet_digest": tasks.digest(draft),
        "registration_status": "HOLD_INPUTS",
        "adopted": False,
        "dispatch_authority": False,
        "inventory_digest": (
            None if inventory is None else inventory["inventory_digest"]
        ),
        "dedup_scope": (
            "UNKNOWN"
            if inventory is None
            else "DECLARED_PUBLIC_NAMESPACE_SNAPSHOT_ONLY"
        ),
        "inventory_as_of": None if inventory is None else inventory["as_of_utc"],
        "tuples": [],
        "new_cases": None,
        "completed": [],
        "scheduled": [],
        "cost": generated["cost"],
        "blockers": [],
    }
    designs = {r["id"]: r["coordinates"] for r in seed["designs"]}
    strata = {r["id"]: r["inputs"] for r in seed["strata"]}
    rungs = {r["id"]: r["settings"] for r in seed["rungs"]}
    for case in generated["cases"]:
        result["tuples"].append(
            {
                **case,
                "body": {
                    "challenge": draft["challenge"],
                    "coordinates": designs[case["design"]],
                    "inputs": strata[case["stratum"]],
                    "rung_settings": rungs[case["rung"]],
                    "pins": seed["pins"],
                },
            }
        )
    if inventory is None:
        result["blockers"].append(
            "DC public completed AND scheduled namespace inventory snapshot missing"
        )
        # The generator's without-reuse arithmetic is valid; remaining work isn't.
        result["cost"]["cpu_hours_if_reuse_accepted"] = None
    if any(r["physical_identity"] is None for r in result["tuples"]):
        result["blockers"].append(
            "complete exact physical/reference/observer/rung pins missing"
        )
    if any(
        not re.fullmatch(r"sha256:[0-9a-f]{64}", str(pin))
        for pin in seed["pins"].values()
    ):
        result["blockers"].append(
            "artifact-manifest SHA256 pins required; version labels alone are not exact pins"
        )
    if result["blockers"]:
        return result
    result["new_cases"] = []
    for row in result["tuples"]:
        state = row["reuse_recommendation"]
        result[
            {
                "COMPLETED": "completed",
                "SCHEDULED": "scheduled",
                "NO_MATCH": "new_cases",
            }[state]
        ].append(row)
    result["registration_status"] = "COMPLETE_FOR_DC_REGISTRATION_REVIEW_NOT_APPROVED"
    result["acceptance_still_required"] = [
        "scientific input/rung applicability",
        "DC reuse and snapshot completeness",
        "value-check and near-limit yield",
        "execution-stage permission and any resource/spend authority",
    ]
    return result


def _read(path, expected):
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise packet.DraftError("SHA256 byte identity required")
    if path.stat().st_size > packet.LIMIT:
        raise packet.DraftError("bounded pinned public input required")
    raw = path.read_bytes()
    if len(raw) > packet.LIMIT or hashlib.sha256(raw).hexdigest() != expected:
        raise packet.DraftError("bounded pinned public input required")
    return packet.read_json(path)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("packet", "seed", "inventory"):
        parser.add_argument("--" + key, type=Path, required=True)
        parser.add_argument("--" + key + "-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    result = assemble(
        _read(args.packet, args.packet_sha256),
        _read(args.seed, args.seed_sha256),
        _read(args.inventory, args.inventory_sha256),
    )
    result["input_byte_sha256"] = {
        key: getattr(args, key + "_sha256") for key in ("packet", "seed", "inventory")
    }
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(
            json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + "\n"
        )
    print(
        json.dumps(
            {
                "challenge": result["challenge"],
                "registration_status": result["registration_status"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
