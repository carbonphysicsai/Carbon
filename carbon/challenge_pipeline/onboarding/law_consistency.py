"""Source-bound packet projections versus law JSON; no semantic approval."""

import argparse
import json
import math
import re
from pathlib import Path

from carbon.challenge_pipeline.onboarding import packet

SCHEMA = "carbon.onboarding.packet-law-bindings.v1"
FACETS = {
    "objective",
    "hard_limits",
    "observer_scope",
    "P",
    "Q",
    "w",
    "boundary",
    "NONE_FEASIBLE",
}


def pointer(document, path):
    if (
        type(path) is not str
        or not re.fullmatch(r"/(?:[A-Za-z0-9_~/-]{1,300})", path)
        or path.count("/") > 12
    ):
        raise packet.DraftError("bounded explicit law JSON pointer required")
    current = document
    for raw in path[1:].split("/"):
        key = raw.replace("~1", "/").replace("~0", "~")
        if type(current) is dict and key in current:
            current = current[key]
        elif type(current) is list and key.isdigit() and int(key) < len(current):
            current = current[int(key)]
        else:
            return False, None
    return True, current


def json_value(value, depth=0):
    if depth > 10:
        raise packet.DraftError("bounded typed packet projection required")
    if value is None or type(value) in (str, bool, int):
        if type(value) is str and len(value) > 8000:
            raise packet.DraftError("projection text bounded")
        return
    if type(value) is float and math.isfinite(value):
        return
    if type(value) not in (dict, list) or len(value) > 100:
        raise packet.DraftError("finite closed JSON projection required")
    if type(value) is dict and any(type(k) is not str for k in value):
        raise packet.DraftError("projection keys required")
    for item in value.values() if type(value) is dict else value:
        json_value(item, depth + 1)


def differences(expected, actual, path):
    # Numeric int/float representations are equivalent; bool never equals 1.
    numeric = type(expected) in (int, float) and type(actual) in (int, float)
    if not numeric and type(expected) is not type(actual):
        return [
            {
                "pointer": path,
                "packet_expected": expected,
                "law_actual": actual,
                "state": "TYPE_MISMATCH",
            }
        ]
    if type(expected) is dict:
        result = []
        for key in sorted(set(expected) | set(actual)):
            child = path + "/" + key.replace("~", "~0").replace("/", "~1")
            if key not in expected or key not in actual:
                result.append(
                    {
                        "pointer": child,
                        "packet_expected": expected.get(key),
                        "law_actual": actual.get(key),
                        "state": (
                            "EXTRA_LAW_FIELD"
                            if key not in expected
                            else "MISSING_LAW_FIELD"
                        ),
                    }
                )
            else:
                result.extend(differences(expected[key], actual[key], child))
        return result
    if type(expected) is list:
        if len(expected) != len(actual):
            return [
                {
                    "pointer": path,
                    "packet_expected": expected,
                    "law_actual": actual,
                    "state": "LENGTH_MISMATCH",
                }
            ]
        return [
            item
            for i, (left, right) in enumerate(zip(expected, actual, strict=True))
            for item in differences(left, right, path + "/" + str(i))
        ]
    return (
        []
        if expected == actual
        else [
            {
                "pointer": path,
                "packet_expected": expected,
                "law_actual": actual,
                "state": "VALUE_MISMATCH",
            }
        ]
    )


def validate(manifest):
    if (
        type(manifest) is not dict
        or set(manifest) != {"schema", "challenge", "law", "checks"}
        or manifest["schema"] != SCHEMA
        or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,79}", str(manifest["challenge"]))
        or type(manifest["law"]) is not dict
        or set(manifest["law"]) != {"path", "sha256", "schema"}
        or type(manifest["checks"]) is not list
        or not 1 <= len(manifest["checks"]) <= 200
    ):
        raise packet.DraftError("closed packet-law bindings required")
    ids = set()
    for row in manifest["checks"]:
        if (
            type(row) is not dict
            or set(row)
            != {"id", "facet", "packet_value", "packet_source", "law_pointer"}
            or row["facet"] not in FACETS
            or type(row["id"]) is not str
            or row["id"] in ids
        ):
            raise packet.DraftError("unique eight-facet binding required")
        packet.text(row["id"])
        ids.add(row["id"])
        json_value(row["packet_value"])
        pointer({}, row["law_pointer"])
        if type(row["packet_source"]) is not dict or set(row["packet_source"]) != {
            "path",
            "sha256",
            "excerpt",
        }:
            raise packet.DraftError("retained packet clause required")


def read_source(root, path):
    if any(
        v in path.lower() for v in ("hidden", "protected", "secret", "ev5", "journal")
    ):
        raise packet.DraftError("public packet/law source required")
    return packet.source_path(root, path)


def check(root, manifest):
    validate(manifest)
    spec = manifest["law"]
    file = read_source(root, spec["path"])
    raw = file.read_bytes()
    law = packet.read_json(file)
    law_state = (
        "PIN_MATCH"
        if packet.digest(raw) == spec["sha256"] and law.get("schema") == spec["schema"]
        else "LAW_PIN_OR_SCHEMA_CHANGED"
    )
    rows = []
    for row in manifest["checks"]:
        try:
            read_source(root, row["packet_source"]["path"])
            packet.verify_sources([row["packet_source"]], root)
            source_state = "VERIFIED_EXCERPT_BYTES_NOT_ENTAILMENT"
        except (packet.DraftError, OSError, UnicodeError):
            source_state = "SOURCE_MISSING_STALE_OR_CHANGED"
        present, actual = pointer(law, row["law_pointer"])
        delta = (
            differences(row["packet_value"], actual, row["law_pointer"])
            if present
            else [
                {
                    "pointer": row["law_pointer"],
                    "packet_expected": row["packet_value"],
                    "law_actual": None,
                    "state": "MISSING_LAW_FIELD",
                }
            ]
        )
        state = (
            "UNRESOLVED_SOURCE"
            if source_state != "VERIFIED_EXCERPT_BYTES_NOT_ENTAILMENT"
            or law_state != "PIN_MATCH"
            else "CONTRADICTED" if delta else "CONSISTENT_PROJECTION"
        )
        rows.append(
            {
                **row,
                "source_state": source_state,
                "law_present": present,
                "law_actual": actual,
                "state": state,
                "diff": delta,
            }
        )
    missing = sorted(FACETS - {row["facet"] for row in rows})
    return {
        "schema": "carbon.onboarding.law-consistency-report.v1",
        "challenge": manifest["challenge"],
        "law_source": {
            **spec,
            "observed_sha256": packet.digest(raw),
            "state": law_state,
        },
        "checks": rows,
        "unbound_facets": missing,
        "checks_examined": len(rows),
        "checklist_clear": not missing
        and all(r["state"] == "CONSISTENT_PROJECTION" for r in rows),
        "authority_granted": False,
        "basis": "Source bytes and reviewed typed packet projections only, not automatic NLP entailment or owner/science approval. Missing facets remain open; explicit null is not a missing JSON field. No packet/law input is changed.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--bindings", required=True)
    parser.add_argument("--report-only", action="store_true")
    args = parser.parse_args()
    try:
        result = check(
            args.root, packet.read_json(read_source(args.root, args.bindings))
        )
    except (packet.DraftError, OSError) as exc:
        parser.exit(2, "law consistency refused: " + str(exc) + "\n")
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0 if args.report_only or result["checklist_clear"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
