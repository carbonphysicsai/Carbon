"""Strict model, schema, and B-05 pilot-manifest acceptance for B-01H."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

from agent_pack.executors.hoh.executors import ScriptedExecutor
from agent_pack.executors.hoh.models import PacketValidationError, RequirementStatus
from agent_pack.executors.hoh.validation import (
    validate_iteration_evidence,
    validate_requirements_manifest,
    validate_run_manifest,
)
from tests.cpu.hoh_support import make_repository, run_manifest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
HOH_ROOT = REPOSITORY_ROOT / "agent_pack" / "executors" / "hoh"


def test_required_status_set_is_closed() -> None:
    assert {item.value for item in RequirementStatus} == {
        "UNTESTED",
        "VERIFIED",
        "FAILED",
        "BLOCKED_HUMAN",
        "BLOCKED_INFRA",
        "OUT_OF_SCOPE",
    }


def test_every_versioned_schema_is_strict_json() -> None:
    schemas = sorted((HOH_ROOT / "schemas").glob("*.schema.json"))
    assert {path.name for path in schemas} == {
        "controller_state.schema.json",
        "developer_result.schema.json",
        "iteration_evidence.schema.json",
        "iteration_plan.schema.json",
        "requirements_manifest.schema.json",
        "run_manifest.schema.json",
    }
    for path in schemas:
        value = json.loads(path.read_text(encoding="utf-8"))
        assert value["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert value["additionalProperties"] is False


def _dod_bullets(ticket: str) -> list[str]:
    body = ticket.split("## Definition of Done\n", 1)[1].split("\n## Human input", 1)[0]
    bullets: list[str] = []
    current: list[str] = []
    for line in body.splitlines():
        if line.startswith("- [ ] "):
            if current:
                bullets.append(" ".join(current))
            current = [line.removeprefix("- [ ] ").strip()]
        elif current and (line.startswith("      ") or not line.strip()):
            if line.strip():
                current.append(line.strip())
        elif current:
            bullets.append(" ".join(current))
            current = []
    if current:
        bullets.append(" ".join(current))
    # Markdown source wrapping can split a lexical hyphen (for example,
    # ``read-`` / ``only``). Compare the semantic checklist text while still
    # binding the byte-exact ticket separately through SHA-256 and git blob.
    return [re.sub(r"-\s+", "-", re.sub(r"\s+", " ", item)).strip() for item in bullets]


def test_b05_manifest_binds_exact_ticket_and_unchanged_dod() -> None:
    manifest_path = HOH_ROOT / "manifests" / "b05.requirements.v1.json"
    manifest = validate_requirements_manifest(
        json.loads(manifest_path.read_text(encoding="utf-8"))
    )
    ticket_path = REPOSITORY_ROOT / manifest["ticket"]["path"]
    ticket = ticket_path.read_text(encoding="utf-8")
    digest = __import__("hashlib").sha256(ticket_path.read_bytes()).hexdigest()
    assert digest == manifest["ticket"]["sha256"]
    blob = subprocess.run(
        ["git", "rev-parse", f"HEAD:{manifest['ticket']['path']}"],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert blob == manifest["ticket"]["git_blob"]
    assert [item["id"] for item in manifest["requirements"]] == [
        f"B05-D{index:02d}" for index in range(1, 12)
    ]
    assert [item["exact_text"] for item in manifest["requirements"]] == _dod_bullets(
        ticket
    )


def test_unsupported_verified_claim_is_rejected() -> None:
    evidence = {
        "schema_version": "1.0",
        "packet_type": "iteration_evidence",
        "run_id": "run-one",
        "iteration": 1,
        "bindings": {
            "authority_commit": "a" * 40,
            "authority_tree": "b" * 40,
            "ticket_sha256": "c" * 64,
            "requirements_sha256": "d" * 64,
            "candidate_head": "e" * 40,
            "candidate_tree": "f" * 40,
            "tester_profile_digest": "1" * 64,
        },
        "results": [
            {
                "requirement_id": "REQ-001",
                "status": "VERIFIED",
                "evidence": [],
                "reason": "Model assertion only.",
            }
        ],
        "context_requests": [],
        "summary": "Unsupported assertion.",
    }
    with pytest.raises(PacketValidationError, match="no accepted evidence"):
        validate_iteration_evidence(evidence, {"REQ-001"})


def test_unknown_packet_fields_fail_closed() -> None:
    path = HOH_ROOT / "manifests" / "b05.requirements.v1.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["scientifically_qualified"] = True
    with pytest.raises(PacketValidationError, match="extra"):
        validate_requirements_manifest(manifest)


def test_run_manifest_rejects_unsafe_worktree_ref(tmp_path: Path) -> None:
    repository, requirements = make_repository(tmp_path)
    manifest = run_manifest(repository, requirements, ScriptedExecutor({}))
    manifest["developer_worktree_ref"] = "refs/heads/main@{1}"

    with pytest.raises(PacketValidationError, match="exact local branch ref"):
        validate_run_manifest(manifest)
