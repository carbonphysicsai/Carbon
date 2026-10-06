"""REF-RESOLVE-01: the reference-resolution policy v1 (DEVELOPMENT only).

A study opts in by reading standard references overlaid by settled ones
(`overlay`). A settled record is a refined solve, in the same pinned truth
image, of a case the standard reference left UNRESOLVED or failed. The same
contract band still applies when the study checks it, so a refined value
inside the band stays UNRESOLVED, and a failed refined solve changes nothing.
Original records are never altered. No frozen study is rescored.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path

POLICY = "ev4-dev-refined-v1"
SETTLED_NAME = "settled-references.jsonl"


def settled(path):
    """The OK refined records of a settled file (plain or .gz)."""
    body = Path(path).read_bytes()
    if str(path).endswith(".gz"):
        body = gzip.decompress(body)
    out = {}
    for line in body.decode().splitlines():
        if line.strip():
            record = json.loads(line)
            if record.get("refined") is True and record.get("status") == "OK":
                out[record["case_id"]] = record
    return out


def overlay(references, settled_records):
    """`references` with each settled case replaced by its refined record,
    stamped with the policy. A case the map does not hold is not added."""
    out = dict(references)
    for case_id, record in settled_records.items():
        if case_id in out:
            out[case_id] = {**record, "reference_policy": POLICY}
    return out
