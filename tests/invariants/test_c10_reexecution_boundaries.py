"""C-10 stays a DEVELOPMENT audit composition without judge authority."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from carbon.audit.model import LedgerReceiptRef
from carbon.reexecution.model import (
    ComparisonDisposition,
    ExecutionProvenance,
    ExecutionResourceObservation,
    ReexecutionOutcome,
    ResourceObservationState,
)
from tests.invariants._import_analysis import direct_import_modules

pytestmark = pytest.mark.invariant

ROOT = Path(__file__).resolve().parents[2]
FILES = tuple(sorted((ROOT / "carbon" / "reexecution").glob("*.py")))


def _sha(label: str) -> str:
    import hashlib

    return "sha256:" + hashlib.sha256(label.encode("ascii")).hexdigest()


def test_reexecution_modules_have_no_scoring_archive_network_or_reward_authority() -> (
    None
):
    forbidden = (
        "carbon.chain",
        "carbon.evidence_archive",
        "carbon.frontier",
        "carbon.leaderboard",
        "carbon.miner_mcp",
        "carbon.qualification",
        "carbon.rewards",
        "carbon.scoring",
        "carbon.transport",
    )
    violations = []
    for path in FILES:
        for module, line in direct_import_modules(ROOT, path):
            if any(
                module == namespace or module.startswith(namespace + ".")
                for namespace in forbidden
            ):
                violations.append(f"{path.name}:{line}:{module}")
    assert violations == []


def test_reexecution_modules_open_no_network_process_or_dynamic_code_surface() -> None:
    forbidden_roots = {
        "asyncio",
        "ctypes",
        "http",
        "multiprocessing",
        "pickle",
        "requests",
        "socket",
        "subprocess",
        "urllib",
    }
    violations = []
    for path in FILES:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for module, line in direct_import_modules(ROOT, path, tree=tree):
            if module.partition(".")[0] in forbidden_roots:
                violations.append(f"{path.name}:{line}:{module}")
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in {"eval", "exec", "compile", "__import__"}
            ):
                violations.append(f"{path.name}:{node.lineno}:{node.func.id}")
    assert violations == []


def test_every_outcome_authority_field_is_structurally_false() -> None:
    primary = ExecutionProvenance(
        "primary",
        "host",
        "administrators",
        _sha("hardware"),
        _sha("source"),
        _sha("image"),
        (_sha("primary-launch"),),
        (_sha("primary-scratch"),),
    )
    repeated = ExecutionProvenance(
        "reexecution",
        "host",
        "administrators",
        _sha("hardware"),
        _sha("source"),
        _sha("image"),
        (_sha("reexecution-launch"),),
        (_sha("reexecution-scratch"),),
    )
    resource = ExecutionResourceObservation(
        ResourceObservationState.UNAVAILABLE, 0.0, None, None, None, None, None
    )
    receipt = LedgerReceiptRef(1, "receipt", _sha("receipt"), _sha("entry"))
    outcome = ReexecutionOutcome(
        "c10-invariant",
        _sha("request"),
        ComparisonDisposition.EXACT_BYTES_AGREE_DEVELOPMENT,
        _sha("primary-account"),
        _sha("reexecution-account"),
        receipt,
        LedgerReceiptRef(2, "reexecution-receipt", _sha("receipt-2"), _sha("entry-2")),
        (),
        (_sha("shared"),),
        primary,
        repeated,
        resource,
        resource,
    )
    authority = outcome.document()["authority"]
    assert type(authority) is dict
    assert (
        authority["marker"] == "DEVELOPMENT_REEXECUTION_ONLY_NOT_SCIENTIFIC_RESOLUTION"
    )
    assert set(authority.values()) == {
        False,
        "DEVELOPMENT_REEXECUTION_ONLY_NOT_SCIENTIFIC_RESOLUTION",
    }
    source = "\n".join(path.read_text(encoding="utf-8") for path in FILES)
    for forbidden in (
        "ArchiveAcknowledgement(",
        "ScoreResult(",
        "SettlementObligation(",
        "WeightIntent(",
    ):
        assert forbidden not in source
