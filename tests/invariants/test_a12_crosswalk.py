"""Machine-auditable coverage and anti-greenwashing checks for A12."""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Any

import pytest

pytestmark = pytest.mark.invariant

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SUITE_ROOT = Path(__file__).resolve().parent
CROSSWALK_PATH = SUITE_ROOT / "a12_crosswalk.json"
EXPECTED_IDS = tuple(f"A12-R{index}" for index in range(1, 13))
EXPECTED_TITLES = (
    "No seed leakage",
    "Practice isolation",
    "Pinned evaluation",
    "Disclosure allow-list",
    "LIVE requires qualification",
    "Execution isolation",
    "Infra ≠ science",
    "Determinism",
    "No placeholder LIVE",
    "No silent rescore",
    "Forbidden score inputs",
    "Practice is useful without revealing the realized exam",
)
EXPECTED_CONTRACTS = (
    (
        "No seed leakage. Official seeds, derived seeds, draw IDs, or reversible "
        "identifiers never appear in EvaluationCard, leaderboard, MCP outputs, or "
        "miner-visible logs."
    ),
    (
        "Practice isolation. Nominal practice/research execution never accesses "
        "official packs, official entropy/seeds, or protected exam data."
    ),
    (
        "Pinned evaluation. Every scored submission is bound to immutable challenge / "
        "generator / Score Pack / backend (container digest) versions."
    ),
    (
        "Disclosure allow-list. InternalResult / Model Card fields are never returned "
        "on miner-facing APIs unless explicitly allow-listed for the disclosure tier."
    ),
    (
        "LIVE requires qualification. LIVE challenges require a complete signed "
        "human qualification manifest for that exact challenge version (not merely "
        "non-null YAML)."
    ),
    (
        "Execution isolation. Miner-supplied strategies run under enforced compute, "
        "network, filesystem, and wall-clock limits. Strategy execution isolation is "
        "a P0 security invariant (implementation may live in ops docs; requirement is "
        "here)."
    ),
    (
        "Infra ≠ science. Infrastructure failures (OOM policy kill, node death, queue "
        "loss) are never scored as scientific / physics failures and never grant "
        "emissions."
    ),
    (
        "Determinism. Re-running an identical official evaluation under identical "
        "versions, seeds, and limits is deterministic within documented tolerances."
    ),
    (
        "No placeholder LIVE. Placeholder, fixture, or mock values never enter LIVE "
        "configuration or emission weights."
    ),
    (
        "No silent rescore. Historical evaluation records are never silently "
        "reinterpreted under newer packs; new pack ⇒ new scoring_version for future "
        "runs only."
    ),
    (
        "Forbidden score inputs. Prior similarity/alignment, `estimate`, resource "
        "forecasts, practice/`light_*` metrics, research information value, exam fee, "
        "and mock metrics never enter `S_combined` / Yuma weights."
    ),
    (
        "Practice is useful without revealing the realized exam. Carbon measures "
        "leakage as incremental ability to infer protected official cases, realized "
        "stress composition, exact margins, or unresolved ordering after controlling "
        "for physics performance on evaluator-held shadow cases sampled from the "
        "declared distribution. Transferable rank improvement can reflect better "
        "physics and is not itself a leak. Practice remains declared-incomplete and "
        "outside official lifecycle, score, and scheduling authority."
    ),
)
EXPECTED_PROOF_KINDS = (
    "behavioral+structural-negative",
    "behavioral+structural-negative",
    "behavioral",
    "behavioral+structural-negative",
    "behavioral",
    "structural-negative",
    "behavioral",
    "behavioral",
    "behavioral+structural-negative",
    "behavioral",
    "behavioral",
    "structural-negative",
)
EXPECTED_CEILINGS = (
    (
        "Synthetic in-process projection evidence only; no deployed transport, "
        "adaptive leakage, security, or production qualification."
    ),
    (
        "No nominal practice execution backend exists; mock, fixture, scaffold, "
        "and estimate boundaries do not prove practice quality or security."
    ),
    (
        "Exact fixture identity and pin enforcement only; no production backend, "
        "container enforcement, LIVE, science, or security qualification."
    ),
    (
        "Bounded in-process disclosure types only; no transport, authentication, "
        "network, gateway, or production security claim."
    ),
    (
        "Structural exact-version gate evidence only; scientific acceptance, "
        "signature verification, signer identity, and key custody remain human-owned."
    ),
    (
        "Negative fail-closed absence proof only; no sandbox, workload isolation, "
        "SECURITY_QUALIFIED, or PRODUCTION_QUALIFIED claim."
    ),
    (
        "Typed fixture-only infrastructure classification, retry/refund, and "
        "FAILED_INFRA separation only; named real infrastructure failures and "
        "production operations are not integration-tested here."
    ),
    (
        "Exact pinned-fixture reproducibility only; A12 chooses no scientific "
        "tolerance and claims no production reproducibility."
    ),
    (
        "Fixture and placeholder rejection only; no frontier, product, receipt, "
        "treasury, settlement, chain, weight, or emission types are created."
    ),
    (
        "Bounded process-local insert-only history only; no production-qualified "
        "durable store or migration policy."
    ),
    (
        "Closed fixture A5 input boundary and fee separation only; no Yuma or "
        "production-weight implementation."
    ),
    (
        "Declared-incomplete, non-executing absence proof only; no usefulness, "
        "leakage, shadow-case, scientific-adequacy, score, lifecycle, or scheduling "
        "claim."
    ),
)
EXPECTED_INFRASTRUCTURE_TESTS = (
    "tests/invariants/test_a12_crosswalk.py::test_a12_crosswalk_has_exact_order_and_authority",
    "tests/invariants/test_a12_crosswalk.py::test_a12_crosswalk_resolves_all_dedicated_and_owner_nodes",
    "tests/invariants/test_a12_crosswalk.py::test_a12_suite_has_no_unmapped_or_greenwashing_tests",
    "tests/invariants/test_a12_crosswalk.py::test_a12_crosswalk_canonical_containment_rejects_aliases",
    "tests/invariants/test_a12_entrypoint.py::test_invariant_entrypoint_accepts_marked_passing_test",
    "tests/invariants/test_a12_entrypoint.py::test_invariant_entrypoint_propagates_marked_failure",
    "tests/invariants/test_a12_entrypoint.py::test_invariant_entrypoint_fails_when_target_is_missing",
    "tests/invariants/test_a12_entrypoint.py::test_invariant_entrypoint_fails_when_target_is_empty",
    "tests/invariants/test_a12_entrypoint.py::test_invariant_entrypoint_fails_when_only_tests_are_unmarked",
    "tests/invariants/test_a12_entrypoint.py::test_invariant_entrypoint_fails_when_zero_marker_matches",
    "tests/invariants/test_a12_entrypoint.py::test_invariant_entrypoint_fails_when_collection_is_completely_deselected",
    "tests/invariants/test_a12_entrypoint.py::test_invariant_entrypoint_real_guard_fails_partial_deselection",
    "tests/invariants/test_a12_entrypoint.py::test_invariant_entrypoint_real_guard_fails_runtime_skip",
    "tests/invariants/test_a12_entrypoint.py::test_invariant_entrypoint_real_guard_fails_expected_xfail",
    "tests/invariants/test_a12_entrypoint.py::test_invariant_entrypoint_real_guard_fails_non_strict_xpass",
    "tests/invariants/test_a12_entrypoint.py::test_invariant_entrypoint_real_guard_fails_collection_time_module_skip",
)
ROW_KEYS = {
    "id",
    "title",
    "contract",
    "dedicated_tests",
    "supporting_owner_tests",
    "proof_kind",
    "ceiling",
}


def _crosswalk() -> dict[str, Any]:
    value = json.loads(CROSSWALK_PATH.read_text(encoding="utf-8"))
    assert type(value) is dict
    return value


def _test_functions(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
    }


def _has_module_invariant_marker(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(
            isinstance(target, ast.Name) and target.id == "pytestmark"
            for target in node.targets
        ):
            continue
        value = node.value
        return (
            isinstance(value, ast.Attribute)
            and value.attr == "invariant"
            and isinstance(value.value, ast.Attribute)
            and value.value.attr == "mark"
            and isinstance(value.value.value, ast.Name)
            and value.value.value.id == "pytest"
        )
    return False


def _node_parts(node_id: str) -> tuple[Path, str]:
    path_text, separator, function_name = node_id.partition("::")
    assert separator == "::" and function_name.startswith("test_")
    relative_path = Path(path_text)
    assert not relative_path.is_absolute()
    assert relative_path.as_posix() == path_text
    path = REPOSITORY_ROOT / relative_path
    return path, function_name


def _canonical_contained_file(candidate: Path, allowed_root: Path) -> Path:
    resolved_root = allowed_root.resolve(strict=True)
    resolved_candidate = candidate.resolve(strict=True)
    assert resolved_candidate.is_relative_to(resolved_root)
    assert candidate == resolved_candidate
    assert resolved_candidate.is_file()
    return resolved_candidate


def _suite_nodes() -> set[str]:
    nodes: set[str] = set()
    for path in sorted(SUITE_ROOT.glob("test_*.py")):
        relative = path.relative_to(REPOSITORY_ROOT).as_posix()
        nodes.update(f"{relative}::{name}" for name in _test_functions(path))
    return nodes


def _authority_contracts() -> tuple[str, ...]:
    path = REPOSITORY_ROOT / "Design_Specs/Build_Out.md"
    lines = path.read_text(encoding="utf-8").splitlines()
    start = lines.index("## 2. Cross-cutting invariants (never violate)")
    paragraphs: list[str] = []
    current: list[str] = []
    for line in lines[start + 1 :]:
        if line == "---":
            break
        match = re.match(r"^(\d+)\.\s+(.*)$", line)
        if match is not None:
            if current:
                paragraphs.append(" ".join(current))
            assert int(match.group(1)) == len(paragraphs) + 1
            current = [match.group(2)]
        elif current and line.startswith("   "):
            current.append(line.strip())
        elif current:
            assert not line.strip()
    if current:
        paragraphs.append(" ".join(current))
    return tuple(
        " ".join(paragraph.replace("**", "").split()) for paragraph in paragraphs
    )


def _qualified_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _qualified_name(node.value)
        return None if parent is None else f"{parent}.{node.attr}"
    return None


def test_a12_crosswalk_has_exact_order_and_authority() -> None:
    crosswalk = _crosswalk()
    assert set(crosswalk) == {
        "schema_version",
        "authority",
        "rows",
        "infrastructure_tests",
    }
    assert crosswalk["schema_version"] == "1.0"
    assert crosswalk["authority"] == "Design_Specs/Build_Out.md section 2"
    rows = crosswalk["rows"]
    assert type(rows) is list and len(rows) == 12
    assert tuple(row["id"] for row in rows) == EXPECTED_IDS
    assert tuple(row["title"] for row in rows) == EXPECTED_TITLES
    assert tuple(row["contract"] for row in rows) == EXPECTED_CONTRACTS
    assert tuple(row["proof_kind"] for row in rows) == EXPECTED_PROOF_KINDS
    assert tuple(row["ceiling"] for row in rows) == EXPECTED_CEILINGS
    assert _authority_contracts() == EXPECTED_CONTRACTS
    for row in rows:
        assert type(row) is dict and set(row) == ROW_KEYS
        assert row["proof_kind"] in {
            "behavioral",
            "structural-negative",
            "behavioral+structural-negative",
        }
        assert type(row["ceiling"]) is str and row["ceiling"]
        assert type(row["dedicated_tests"]) is list and row["dedicated_tests"]
        assert (
            type(row["supporting_owner_tests"]) is list
            and row["supporting_owner_tests"]
        )

    infrastructure = crosswalk["infrastructure_tests"]
    assert type(infrastructure) is list
    assert tuple(infrastructure) == EXPECTED_INFRASTRUCTURE_TESTS
    assert len(infrastructure) == len(set(infrastructure))
    for node_id in infrastructure:
        path, function_name = _node_parts(node_id)
        resolved_path = _canonical_contained_file(path, SUITE_ROOT)
        assert function_name in _test_functions(resolved_path)
        assert _has_module_invariant_marker(resolved_path)


def test_a12_crosswalk_resolves_all_dedicated_and_owner_nodes() -> None:
    rows = _crosswalk()["rows"]
    dedicated: list[str] = []
    for row in rows:
        dedicated.extend(row["dedicated_tests"])
        for node_id in row["dedicated_tests"]:
            path, function_name = _node_parts(node_id)
            resolved_path = _canonical_contained_file(path, SUITE_ROOT)
            assert resolved_path.parent == SUITE_ROOT.resolve(strict=True)
            assert function_name in _test_functions(resolved_path)
            assert _has_module_invariant_marker(resolved_path)
        for node_id in row["supporting_owner_tests"]:
            path, function_name = _node_parts(node_id)
            resolved_path = _canonical_contained_file(
                path, REPOSITORY_ROOT / "tests/cpu"
            )
            assert function_name in _test_functions(resolved_path)

    assert len(dedicated) == len(set(dedicated)) == 12
    assert set(dedicated).issubset(_suite_nodes())


def test_a12_suite_has_no_unmapped_or_greenwashing_tests() -> None:
    crosswalk = _crosswalk()
    rows = crosswalk["rows"]
    dedicated = {node_id for row in rows for node_id in row["dedicated_tests"]}
    infrastructure = set(crosswalk["infrastructure_tests"])
    assert _suite_nodes() == dedicated | infrastructure
    assert dedicated.isdisjoint(infrastructure)

    prohibited_calls = {
        "pytest.skip",
        "pytest.xfail",
        "object.__new__",
        "object.__setattr__",
    }
    prohibited_markers = {
        "pytest.mark.skip",
        "pytest.mark.skipif",
        "pytest.mark.xfail",
    }
    for path in sorted(SUITE_ROOT.glob("*.py")):
        if path.name.startswith("test_"):
            assert _has_module_invariant_marker(path)
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                assert _qualified_name(node.func) not in prohibited_calls
            if isinstance(node, ast.Attribute):
                assert _qualified_name(node) not in prohibited_markers
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                assert all(
                    _qualified_name(decorator) not in prohibited_markers
                    for decorator in node.decorator_list
                )
                assert all(argument.arg != "monkeypatch" for argument in node.args.args)
            if isinstance(node, ast.Import):
                assert all(
                    not alias.name.startswith("tests.cpu") for alias in node.names
                )
                for alias in node.names:
                    if alias.name == "pytest":
                        assert alias.asname in (None, "pytest")
            if isinstance(node, ast.ImportFrom):
                assert node.module is None or not node.module.startswith("tests.cpu")
                if node.module == "pytest":
                    assert all(
                        alias.name not in {"mark", "skip", "skipif", "xfail"}
                        for alias in node.names
                    )

    guard_functions = _test_functions(SUITE_ROOT / "conftest.py")
    assert not guard_functions
    guard_tree = ast.parse(
        SUITE_ROOT.joinpath("conftest.py").read_text(encoding="utf-8")
    )
    guard_hooks = {
        node.name
        for node in guard_tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert {
        "pytest_deselected",
        "pytest_collectreport",
        "pytest_runtest_logreport",
        "pytest_sessionfinish",
    }.issubset(guard_hooks)


def test_a12_crosswalk_canonical_containment_rejects_aliases(
    tmp_path: Path,
) -> None:
    allowed_root = tmp_path / "allowed"
    outside_root = tmp_path / "outside"
    allowed_root.mkdir()
    outside_root.mkdir()

    canonical_file = allowed_root / "test_inside.py"
    outside_file = outside_root / "test_outside.py"
    canonical_file.write_text("def test_inside():\n    pass\n", encoding="utf-8")
    outside_file.write_text("def test_outside():\n    pass\n", encoding="utf-8")

    assert _canonical_contained_file(canonical_file, allowed_root) == (
        canonical_file.resolve(strict=True)
    )

    outside_traversal = allowed_root / ".." / "outside" / outside_file.name
    with pytest.raises(AssertionError):
        _canonical_contained_file(outside_traversal, allowed_root)

    symlink_escape = allowed_root / "test_symlink_escape.py"
    symlink_escape.symlink_to(outside_file)
    with pytest.raises(AssertionError):
        _canonical_contained_file(symlink_escape, allowed_root)

    nested = allowed_root / "nested"
    nested.mkdir()
    inside_traversal = nested / ".." / canonical_file.name
    with pytest.raises(AssertionError):
        _canonical_contained_file(inside_traversal, allowed_root)

    with pytest.raises(AssertionError):
        _node_parts("tests/./cpu/test_example.py::test_example")
