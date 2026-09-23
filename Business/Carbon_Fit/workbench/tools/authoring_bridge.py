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
import math
import subprocess
import sys
from pathlib import Path

from carbon.authoring import goals

REQUEST_SCHEMA = "carbon.goal-workbench.authoring-request.v1"
RESULT_SCHEMA = "carbon.goal-workbench.authoring-result.v1"
TEMPLATE = "periodic_viscous_burgers_1d_v1"
GOALS = frozenset(("Dynamics", "Transport", "Front Resolution", "Dissipation"))

# E8: nothing typed into the Workbench reaches a Challenge proposal. A proposal
# is what the subnet is eventually shown, and a Workbench design can hold
# client material, so the compiled input is built only from source-owned
# constants, the closed goal enum, and an identifier derived by digest. The
# design's own text, including its ids, is never read into it.
#
# This is not a sanitiser and must not become one. In an engineering brief the
# parameters are the secret, so filtering either leaves the secret in or leaves
# nothing worth compiling, and an opt-in would invite exactly the pressure it
# exists to resist. The owner closed that question (counsel brief v1, 8.1 item
# 2): absolute exclusion, no opt-in, no flag. Reopening it is an owner decision
# taken with counsel, not a change to this function.
TEMPLATE_INTENDED_USE = (
    "Demonstrate exact technical expressibility for the public DEVELOPMENT "
    "Burgers Dynamics profile without scientific suitability, customer-use, "
    "rights, qualification, or launch claims."
)


def _opaque_challenge_id(request: dict[str, object]) -> str:
    identity = json.dumps(
        [request["job_id"], request["design_id"], request["design_revision"]],
        separators=(",", ":"),
    )
    return "workbench-" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]


MAX_BYTES = 1_048_576
MAX_DEPTH = 24
MAX_COLLECTION = 256
MAX_SAFE_INTEGER = 9_007_199_254_740_991


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
    _bounded(value)
    return value


def _bounded(value: object, depth: int = 0) -> None:
    if depth > MAX_DEPTH:
        raise ValueError("request nesting exceeds the closed bridge limit")
    if value is None or type(value) is bool:
        return
    if type(value) is str:
        if len(value) > 8_000:
            raise ValueError("request string exceeds the closed bridge limit")
        return
    if type(value) is int:
        if abs(value) > MAX_SAFE_INTEGER:
            raise ValueError("request integer is unsafe for browser round trips")
        return
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError("request number is nonfinite")
        return
    if type(value) is list:
        if len(value) > MAX_COLLECTION:
            raise ValueError("request collection exceeds the closed bridge limit")
        for item in value:
            _bounded(item, depth + 1)
        return
    if type(value) is dict:
        if len(value) > MAX_COLLECTION:
            raise ValueError("request object exceeds the closed bridge limit")
        for item in value.values():
            _bounded(item, depth + 1)
        return
    raise ValueError("request contains an unsupported value")


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
    if not all(
        type(value) is dict for value in (challenge, boundary, capabilities, physical)
    ):
        raise ValueError("native proposal lacks required semantic sections")
    reports = proposal.get("goal_reports")
    active_goal_count = (
        sum(
            type(item) is dict and item.get("activation") == "PRIMARY_CHALLENGE"
            for item in reports
        )
        if type(reports) is list and reports
        else challenge.get("competition_count")  # type: ignore[union-attr]
    )
    measurement = proposal.get("measurement_proposal")
    training = proposal.get("training_adapter")
    emitted = {
        "physical_law": physical,
        "active_goal": challenge.get("primary_goal"),  # type: ignore[union-attr]
        "source_goal": boundary.get("source_goal"),  # type: ignore[union-attr]
        "active_goal_count": active_goal_count,
        "measurement": measurement if type(measurement) is dict else {},
        "score": (
            proposal.get("score_proposal")
            if type(proposal.get("score_proposal")) is dict
            else {}
        ),
        "sampling": (
            proposal.get("plans") if type(proposal.get("plans")) is dict else {}
        ),
        "references": (
            proposal.get("reference_candidates")
            if type(proposal.get("reference_candidates")) is list
            else []
        ),
        "query_contract": {
            "candidate_payload_allow_list": (
                training.get(  # type: ignore[union-attr]
                    "candidate_payload_allow_list", []
                )
                if type(training) is dict
                else []
            ),
            "point_query_rule": (
                measurement.get("point_query_rule", "")  # type: ignore[union-attr]
                if type(measurement) is dict
                else ""
            ),
        },
        "capabilities": capabilities,
    }
    mismatches: list[str] = []
    if request["template_id"] != TEMPLATE:
        mismatches.append("physics template unsupported")
    if request["requested_goal"] != emitted["active_goal"]:
        mismatches.append(
            f"requested active goal {request['requested_goal']} emitted as {emitted['active_goal']}"
        )
    if emitted["active_goal_count"] != 1:
        mismatches.append("active goal count changed")
    compatibility = request["compatibility"]
    if compatibility.get("status") != "EXACT_SUPPORTED":  # type: ignore[union-attr]
        gaps = compatibility.get("gaps", [])  # type: ignore[union-attr]
        if type(gaps) is not list:
            gaps = []
        mismatches.append(
            "workbench design has unresolved semantic bindings: "
            + "; ".join(str(item) for item in gaps)
        )
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
    challenge_id = _opaque_challenge_id(request)
    native_input = goals.supported_burgers_development_intake(
        requested_goal=str(request["requested_goal"]),
        challenge_id=challenge_id,
        title=f"Workbench design {challenge_id}",
        intended_use=TEMPLATE_INTENDED_USE,
    )
    input_bytes = _canonical(native_input)
    input_digest = _sha(input_bytes)
    source_revision = (
        "carbon.authoring.goals-sha256:"
        + hashlib.sha256(Path(goals.__file__).read_bytes()).hexdigest()
        + ";profile:"
        + goals.GOAL_AUTHORING_PROFILE
    )
    input_path = output_directory / "native-input.json"
    native_output = output_directory / "native-output"
    proposal_path = native_output / "proposal.json"
    target = output_directory / "workbench-authoring-result.json"
    if target.exists():
        if target.is_symlink() or input_path.is_symlink() or proposal_path.is_symlink():
            raise ValueError("authoring result conflict")
        try:
            existing = json.loads(
                target.read_text(encoding="utf-8"), object_pairs_hook=_pairs
            )
            existing_proposal_bytes = proposal_path.read_bytes()
            existing_proposal = json.loads(
                existing_proposal_bytes, object_pairs_hook=_pairs
            )
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            raise ValueError("authoring result conflict") from exc
        expected_fields = {
            "schema_version",
            "request_id",
            "job_id",
            "design_id",
            "design_revision",
            "input_digest",
            "proposal_digest",
            "proposal",
            "cli_result",
            "semantic_receipt",
            "source_revision",
            "route",
        }
        if type(existing) is not dict or set(existing) != expected_fields:
            raise ValueError("authoring result conflict")
        proposal_digest = existing.get("proposal_digest")
        try:
            expected_receipt = semantic_receipt(
                request, existing_proposal, str(proposal_digest), input_digest
            )
        except ValueError as exc:
            raise ValueError("authoring result conflict") from exc
        try:
            association = (
                existing.get("schema_version") == RESULT_SCHEMA
                and existing.get("request_id") == request["request_id"]
                and existing.get("job_id") == request["job_id"]
                and existing.get("design_id") == request["design_id"]
                and existing.get("design_revision") == request["design_revision"]
                and existing.get("input_digest") == input_digest
                and existing.get("source_revision") == source_revision
                and existing.get("route") == "LOCAL_FIXED_CLI"
                and existing.get("proposal") == existing_proposal
                and existing.get("semantic_receipt") == expected_receipt
                and input_path.read_bytes() == input_bytes
                and _sha(goals.PROPOSAL_DOMAIN + existing_proposal_bytes)
                == proposal_digest
            )
        except OSError as exc:
            raise ValueError("authoring result conflict") from exc
        if not association:
            raise ValueError("authoring result conflict")
        return target
    input_path.write_bytes(input_bytes)
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
    proposal_bytes = proposal_path.read_bytes()
    proposal = json.loads(proposal_bytes)
    proposal_digest = _string(
        cli_result.get("content_digest"), "proposal digest", minimum=8
    )
    if _sha(goals.PROPOSAL_DOMAIN + proposal_bytes) != proposal_digest:
        raise ValueError("native proposal digest mismatch")
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
        "source_revision": source_revision,
        "route": "LOCAL_FIXED_CLI",
    }
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
