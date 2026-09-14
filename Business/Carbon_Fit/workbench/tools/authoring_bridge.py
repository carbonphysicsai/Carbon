#!/usr/bin/env python3
"""Closed local bridge from one workbench design request to C-AUTH1's CLI.

The bridge serializes only the source-owned public Burgers DEVELOPMENT intake,
invokes ``python -m carbon.authoring compile-goal`` with a fixed argument list,
and returns original bytes plus a semantic receipt. It cannot compile arbitrary
code, qualify science, register, submit, run a solver, or launch a Challenge.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from carbon.authoring import goals

REQUEST_SCHEMA = "carbon.goal-workbench.authoring-request.v1"
RESULT_SCHEMA = "carbon.goal-workbench.authoring-result.v1"
TEMPLATE = "periodic_viscous_burgers_1d_v1"
GOALS = frozenset(("Dynamics", "Transport", "Front Resolution", "Dissipation"))
MAX_BYTES = 1_048_576


def _pairs(values: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in values:
        if key in result or key in {"__proto__", "prototype", "constructor"}:
            raise ValueError("invalid or duplicate JSON member")
        result[key] = value
    return result


def _load(path: Path) -> dict[str, object]:
    raw = path.read_bytes()
    if not raw or len(raw) > MAX_BYTES:
        raise ValueError("request size is outside the closed bridge limit")
    value = json.loads(
        raw.decode("utf-8"),
        object_pairs_hook=_pairs,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")),
    )
    if type(value) is not dict:
        raise ValueError("request must be an object")
    return value


def _string(value: object, label: str, *, minimum: int = 0) -> str:
    if type(value) is not str or len(value) < minimum or len(value) > 8_000:
        raise ValueError(f"invalid {label}")
    return value


def _request(value: dict[str, object]) -> dict[str, object]:
    expected = {
        "schema_version",
        "request_id",
        "job_id",
        "design_id",
        "design_revision",
        "template_id",
        "requested_goal",
        "intended_use",
        "rights_scope",
        "expected_semantics",
        "compatibility",
        "route",
        "authority",
    }
    if set(value) != expected or value.get("schema_version") != REQUEST_SCHEMA:
        raise ValueError("unsupported authoring request")
    for field in ("request_id", "job_id", "design_id"):
        text = _string(value[field], field, minimum=1)
        if not all(char.isalnum() or char in "._:-" for char in text):
            raise ValueError(f"invalid {field}")
    if type(value["design_revision"]) is not int or value["design_revision"] < 1:
        raise ValueError("invalid design revision")
    if value["template_id"] != TEMPLATE:
        raise ValueError("source-owned template is unavailable")
    if value["requested_goal"] not in GOALS:
        raise ValueError("source-owned goal label is unavailable")
    if value["rights_scope"] != "SYNTHETIC_INTERNAL":
        raise ValueError("bridge cannot relabel client or third-party rights")
    if value["route"] != "LOCAL_FIXED_CLI":
        raise ValueError("request is not routed to the fixed local CLI")
    if value["authority"] != "DEVELOPMENT_REQUEST_ONLY":
        raise ValueError("request attempts authority promotion")
    _string(value["intended_use"], "intended use", minimum=40)
    if type(value["expected_semantics"]) is not dict:
        raise ValueError("expected semantics must be an object")
    if type(value["compatibility"]) is not dict:
        raise ValueError("compatibility must be an object")
    return value


def _canonical(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def _sha(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def semantic_receipt(
    request: dict[str, object],
    proposal: dict[str, object],
    proposal_digest: str,
    input_digest: str,
) -> dict[str, object]:
    challenge = proposal.get("challenge")
    boundary = proposal.get("evidence_boundary")
    capabilities = proposal.get("capabilities")
    physical = proposal.get("physical_contract")
    if not all(type(value) is dict for value in (challenge, boundary, capabilities, physical)):
        raise ValueError("native proposal lacks required semantic sections")
    emitted = {
        "physics_family": physical.get("physical_scope"),  # type: ignore[union-attr]
        "active_goal": challenge.get("primary_goal"),  # type: ignore[union-attr]
        "source_goal": boundary.get("source_goal"),  # type: ignore[union-attr]
        "competition_count": challenge.get("competition_count"),  # type: ignore[union-attr]
        "capabilities": capabilities,
    }
    mismatches: list[str] = []
    if request["template_id"] != TEMPLATE:
        mismatches.append("physics template unsupported")
    if request["requested_goal"] != emitted["active_goal"]:
        mismatches.append(
            f"requested active goal {request['requested_goal']} emitted as {emitted['active_goal']}"
        )
    if emitted["competition_count"] != 1:
        mismatches.append("competition count changed")
    if any(value is not False for value in capabilities.values()):  # type: ignore[union-attr]
        mismatches.append("authority flags unexpectedly enabled")
    return {
        "schema_version": "carbon.goal-workbench.semantic-receipt.v1",
        "request_id": request["request_id"],
        "job_id": request["job_id"],
        "design_id": request["design_id"],
        "design_revision": request["design_revision"],
        "input_digest": input_digest,
        "proposal_digest": proposal_digest,
        "expected": request["expected_semantics"],
        "emitted": emitted,
        "mismatches": mismatches,
        "status": "INTENT_MISMATCH" if mismatches else "INTENT_PRESERVED",
        "qualification": "NOT_QUALIFIED",
        "launch": "NOT_LAUNCHED",
    }


def compile_request(request_path: Path, output_directory: Path) -> Path:
    request = _request(_load(request_path))
    output_directory.mkdir(parents=True, exist_ok=True)
    if output_directory.is_symlink() or not output_directory.is_dir():
        raise ValueError("invalid output directory")
    native_input = goals.supported_burgers_development_intake(
        requested_goal=str(request["requested_goal"]),
        challenge_id=str(request["design_id"]),
        title=f"Workbench design {request['design_id']}",
        intended_use=str(request["intended_use"]),
    )
    input_bytes = _canonical(native_input)
    input_path = output_directory / "native-input.json"
    input_path.write_bytes(input_bytes)
    native_output = output_directory / "native-output"
    command = [
        sys.executable,
        "-m",
        "carbon.authoring",
        "compile-goal",
        str(input_path),
        str(native_output),
    ]
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        raise ValueError("source-owned authoring CLI rejected the bounded request")
    cli_result = json.loads(completed.stdout)
    proposal_path = native_output / "proposal.json"
    proposal_bytes = proposal_path.read_bytes()
    proposal = json.loads(proposal_bytes)
    proposal_digest = _string(cli_result.get("content_digest"), "proposal digest", minimum=8)
    if _sha(goals.PROPOSAL_DOMAIN + proposal_bytes) != proposal_digest:
        raise ValueError("native proposal digest mismatch")
    input_digest = _sha(input_bytes)
    result = {
        "schema_version": RESULT_SCHEMA,
        "request_id": request["request_id"],
        "job_id": request["job_id"],
        "design_id": request["design_id"],
        "design_revision": request["design_revision"],
        "input_digest": input_digest,
        "proposal_digest": proposal_digest,
        "proposal": proposal,
        "cli_result": cli_result,
        "semantic_receipt": semantic_receipt(
            request, proposal, proposal_digest, input_digest
        ),
        "source_revision": (
            "carbon.authoring.goals-sha256:"
            + hashlib.sha256(Path(goals.__file__).read_bytes()).hexdigest()
            + ";profile:"
            + goals.GOAL_AUTHORING_PROFILE
        ),
        "route": "LOCAL_FIXED_CLI",
    }
    target = output_directory / "workbench-authoring-result.json"
    encoded = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if target.exists() and target.read_text(encoding="utf-8") != encoded:
        raise ValueError("authoring result conflict")
    target.write_text(encoded, encoding="utf-8")
    return target


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("request", type=Path)
    parser.add_argument("output_directory", type=Path)
    args = parser.parse_args()
    print(compile_request(args.request, args.output_directory))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
