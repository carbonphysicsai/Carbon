"""Offline links to existing owner code-verification acceptance, never qualification.

Only registered public repository files are read. Export consumers supply the
same committed bytes through their existing source reader, without discovery.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path

SCHEMA = "carbon.code-verification.acceptance-link.v1"
DIRECTORY = "docs/development/challenge_pipeline/code-verification/acceptance-links"
LINKS = {"battery-v3": "pybamm.json", "motor": "getdp.json", "f02": "elmer-heat.json"}
DECISION_ID = "OWNER-CODE-VERIFICATION-ACCEPT-01"
DECISION_PATH = ".agent/decisions/2026-10-11-OWNER-CODE-VERIFICATION-ACCEPT-01.md"
ROOT = Path(__file__).resolve().parents[2]


class AcceptanceRefused(ValueError):
    """Missing or mismatched acceptance is unavailable, never a new verdict."""


def digest(value):
    """The canonical JSON identity used by the historical MMS checker."""
    return (
        "sha256:"
        + hashlib.sha256(
            json.dumps(
                value, sort_keys=True, separators=(",", ":"), allow_nan=False
            ).encode()
        ).hexdigest()
    )


def byte_digest(value):
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _digest(value):
    if type(value) is not str or not re.fullmatch(r"sha256:[0-9a-f]{64}", value):
        raise AcceptanceRefused("acceptance_digest_required")
    return value


def _closed(value, fields):
    if type(value) is not dict or set(value) != set(fields):
        raise AcceptanceRefused("acceptance_link_schema")


def _read_regular(root, path):
    target = root / path
    if any(parent.is_symlink() for parent in [target, *target.parents]):
        raise AcceptanceRefused("acceptance_regular_file_required")
    return target.read_bytes()


def validate_acceptance(link, *, family, image_digest, criteria_digest, files):
    """Bind the link to decision, criteria and result bytes from one snapshot.

    This validates registered document identity. It does not attest the custody
    of disclosed cases, rerun a solver, or establish reference adequacy.
    """
    _closed(
        link,
        {
            "schema",
            "scope",
            "solver",
            "family",
            "image_digest",
            "criteria_digest",
            "criteria_path",
            "decision",
            "evidence",
            "conditions",
        },
    )
    if (
        link["schema"] != SCHEMA
        or link["scope"] != "DEVELOPMENT_CODE_VERIFICATION"
        or type(family) is not str
        or family not in LINKS
        or link["family"] != family
    ):
        raise AcceptanceRefused("acceptance_scope_or_family")
    if _digest(link["image_digest"]) != _digest(image_digest):
        raise AcceptanceRefused("acceptance_image_mismatch")
    if _digest(link["criteria_digest"]) != _digest(criteria_digest):
        raise AcceptanceRefused("acceptance_criteria_mismatch")
    decision = link["decision"]
    _closed(decision, {"id", "path", "sha256"})
    if decision["id"] != DECISION_ID or decision["path"] != DECISION_PATH:
        raise AcceptanceRefused("acceptance_decision_required")
    evidence = link["evidence"]
    if type(evidence) is not list or not evidence:
        raise AcceptanceRefused("acceptance_evidence_required")
    for item in [decision, *evidence]:
        if item is not decision:
            _closed(item, {"path", "sha256"})
        data = files.get(item["path"])
        if type(data) is not bytes or byte_digest(data) != _digest(item["sha256"]):
            raise AcceptanceRefused("acceptance_source_mismatch")
        if item is not decision:
            try:
                result = json.loads(data)
                expected_schema = (
                    "carbon.reference-package.mms.v1"
                    if family == "f02"
                    else "carbon.code-verification.result.v1"
                )
                if result.get("schema") != expected_schema:
                    raise AcceptanceRefused("acceptance_evidence_result_required")
                if result.get("image_digest", result.get("image")) != image_digest:
                    raise AcceptanceRefused("acceptance_evidence_image_mismatch")
                if family != "f02" and result.get("criteria_digest") != criteria_digest:
                    raise AcceptanceRefused("acceptance_evidence_criteria_mismatch")
                if family != "f02" and result.get("family") != family:
                    raise AcceptanceRefused("acceptance_evidence_family_mismatch")
            except (TypeError, ValueError, AttributeError) as error:
                if isinstance(error, AcceptanceRefused):
                    raise
                raise AcceptanceRefused("acceptance_evidence_malformed") from error
    criteria_bytes = files.get(link["criteria_path"])
    if type(criteria_bytes) is not bytes:
        raise AcceptanceRefused("acceptance_criteria_unavailable")
    try:
        criteria = json.loads(criteria_bytes)
        if digest(criteria) != criteria_digest or criteria["family"] != family:
            raise AcceptanceRefused("acceptance_criteria_mismatch")
        conditions = link["conditions"]
        expected = {"t_end": 0.375} if family == "f02" else {}
        if conditions != expected or (conditions and criteria.get("t_end") != 0.375):
            raise AcceptanceRefused("acceptance_condition_mismatch")
    except (KeyError, TypeError, ValueError) as error:
        if isinstance(error, AcceptanceRefused):
            raise
        raise AcceptanceRefused("acceptance_criteria_malformed") from error
    return {
        "schema": SCHEMA,
        "scope": link["scope"],
        "family": family,
        "image_digest": image_digest,
        "criteria_digest": criteria_digest,
        "link_digest": digest(link),
        "decision": {
            "decision_id": decision["id"],
            "path": decision["path"],
            "sha256": decision["sha256"],
        },
        "conditions": copy.deepcopy(conditions),
    }


def load_acceptance(family, image_digest, criteria_digest, *, root=ROOT):
    """Read a closed registry of public files; a repin needs a new link."""
    if type(family) is not str or family not in LINKS:
        raise AcceptanceRefused("acceptance_link_unavailable")
    try:
        link = json.loads(_read_regular(root, DIRECTORY + "/" + LINKS[family]))
        paths = [
            DECISION_PATH,
            link["criteria_path"],
            *[item["path"] for item in link["evidence"]],
        ]
        files = {}
        for path in paths:
            # The committed registry is trusted configuration, but may only
            # name the acceptance decision or public MMS evidence/criteria.
            if (
                type(path) is not str
                or ".." in path
                or "\\" in path
                or re.search(r"hidden|sealed|protected|private", path, re.IGNORECASE)
                or not (
                    path == DECISION_PATH
                    or path.startswith(
                        (
                            "docs/development/evidence/battery-feasibility-02/code-verification/",
                            "docs/development/evidence/motor-feasibility-02/code-verification/",
                            "docs/development/evidence/reference-packages-01/elmer-mms-heat",
                            DIRECTORY + "/",
                        )
                    )
                )
            ):
                raise AcceptanceRefused("acceptance_public_path_required")
            files[path] = _read_regular(root, path)
        return validate_acceptance(
            link,
            family=family,
            image_digest=image_digest,
            criteria_digest=criteria_digest,
            files=files,
        )
    except (OSError, KeyError, TypeError, ValueError) as error:
        if isinstance(error, AcceptanceRefused):
            raise
        raise AcceptanceRefused("acceptance_link_unavailable") from error
