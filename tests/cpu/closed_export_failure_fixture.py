"""Test-only allowlisted CI projection; never upload the private worker record."""

import json
import re


def closed_export_failure(operation):
    unknown = {
        "observed_exec_exit": None,
        "observation_status": "UNKNOWN",
        "export_deadline_reached": None,
    }
    try:
        path = operation / "private-export-failure-evidence.json"
        if (
            operation.is_symlink()
            or path.is_symlink()
            or not path.is_file()
            or not 0 < path.stat().st_size <= 4096
        ):
            return unknown
        with path.open("rb") as stream:
            raw = stream.read(4097)
        if len(raw) > 4096:
            return unknown
        record = json.loads(raw)
        if (
            type(record) is not dict
            or record.get("schema") != "carbon.autoresearch.export-failure-evidence.v1"
            or type(record.get("launch_digest")) is not str
            or re.fullmatch(r"sha256:[0-9a-f]{64}", record["launch_digest"]) is None
            or operation.name != "operation-" + record["launch_digest"][7:]
        ):
            return unknown
        code = record.get("observed_exec_exit")
        deadline = record.get("export_deadline_reached")
        observation = record.get("observation")
        if (
            (code is not None and (type(code) is not int or not 0 <= code <= 255))
            or type(deadline) is not bool
            or type(observation) is not dict
            or observation.get("status") not in ("OBSERVED", "UNKNOWN")
        ):
            return unknown
        return {
            "observed_exec_exit": code,
            "observation_status": observation["status"],
            "export_deadline_reached": deadline,
        }
    except (OSError, ValueError, TypeError, KeyError, RecursionError):
        return unknown
