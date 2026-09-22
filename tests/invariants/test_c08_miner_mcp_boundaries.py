"""C-08 composes source owners without acquiring their authority."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tests.invariants._import_analysis import direct_import_modules

pytestmark = pytest.mark.invariant

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "carbon" / "miner_mcp"


def _literal_exports() -> tuple[str, ...]:
    tree = ast.parse((PACKAGE / "__init__.py").read_text(encoding="utf-8"))
    declarations = [
        node
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "__all__"
            for target in node.targets
        )
    ]
    assert len(declarations) == 1
    exports = ast.literal_eval(declarations[0].value)
    assert isinstance(exports, tuple)
    return exports


def test_package_is_exact_and_exports_no_official_or_network_surface() -> None:
    miner_mcp_exports = _literal_exports()
    assert {path.name for path in PACKAGE.glob("*.py")} == {
        "__init__.py",
        "model.py",
        "research.py",
        "service.py",
        # C-CORE-02/v3 standard transports wrap the existing public service.
        # This does not change the historical package-root exports below.
        "standard.py",
        "standard_cli.py",
        "standard_server.py",
        "standard_http.py",
        "mcp_apps.py",
        "mcp_extensions.py",
        # Chain onboarding is the open tier: it carries no adapter, no campaign
        # and no ledger, and adds no official or network-writing surface. Its
        # chain access is read-only through an injected reader, and no function
        # in it signs or accepts key material. Listed explicitly because adding
        # a module to this package should be a deliberate act, which is what
        # this assertion is for.
        "mcp_onboarding.py",
        # The open-tier server mode. It composes existing surfaces rather than
        # adding one: the onboarding tools above, the published exam
        # environment, and - only once a campaign is attached - the tools the
        # standard server already builds. It creates no campaign and no ledger
        # of its own, and adds no official or network-writing capability.
        "open_tier.py",
        # Per-call records, the concurrency bound and the surface catalogue. It
        # adds no capability: it wraps the existing single call path, and the
        # records it builds structurally cannot contain a caller's arguments or
        # a caller-supplied identity. No official, network-writing or signing
        # surface is introduced.
        "serving.py",
        "mcp_skills.py",
        "store.py",
    }
    assert tuple(miner_mcp_exports) == (
        "AuthenticatedMcpResult",
        "AuthenticatedMinerMcpService",
        "BindMode",
        "MinerMcpCode",
        "MinerMcpFailure",
        "MinerMcpJournal",
    )
    assert not any(
        fragment in name
        for name in miner_mcp_exports
        for fragment in ("Archive", "Official", "Reward", "Score", "Weight")
    )


def test_source_owners_do_not_depend_on_c08_and_c08_has_no_lateral_authority() -> None:
    for owner in ("transport", "mcp", "execution", "orchestration", "fees"):
        for path in (ROOT / "carbon" / owner).glob("*.py"):
            assert "carbon.miner_mcp" not in path.read_text(encoding="utf-8")
    forbidden = (
        "carbon.archive",
        "carbon.chain.publisher",
        "carbon.evidence_archive",
        "carbon.frontier",
        "carbon.leaderboard",
        "carbon.qualification",
        "carbon.rewards",
        "carbon.scoring",
    )
    violations = []
    for path in PACKAGE.glob("*.py"):
        for module, line in direct_import_modules(ROOT, path):
            if any(
                module == namespace or module.startswith(namespace + ".")
                for namespace in forbidden
            ):
                violations.append(f"{path.name}:{line}:{module}")
    assert violations == []


def _forbidden_runtime_surface(path, tree):
    forbidden_roots = {
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
    for module, line in direct_import_modules(ROOT, path, tree=tree):
        # The reviewed HTTP factory parses the operator's HTTPS issuer/resource
        # identifiers. This exact symbol performs no request or listener work.
        syntax_only = (
            path == PACKAGE / "standard_http.py"
            and module == "urllib.parse"
            and any(
                isinstance(node, ast.ImportFrom)
                and node.lineno == line
                and node.level == 0
                and node.module == "urllib.parse"
                and len(node.names) == 1
                and node.names[0].name == "urlsplit"
                and node.names[0].asname is None
                for node in ast.walk(tree)
            )
        )
        if module.partition(".")[0] in forbidden_roots and not syntax_only:
            violations.append(f"{path.name}:{line}:{module}")
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in {"eval", "exec", "compile", "__import__"}
        ):
            violations.append(f"{path.name}:{node.lineno}:{node.func.id}")
    return violations


def test_c08_opens_no_listener_process_dynamic_code_or_pickle_surface() -> None:
    violations = [
        violation
        for path in PACKAGE.glob("*.py")
        for violation in _forbidden_runtime_surface(
            path, ast.parse(path.read_text(encoding="utf-8"))
        )
    ]
    assert violations == []


def test_core02_url_parser_exception_is_exact_and_has_no_network_authority():
    tree = ast.parse("from urllib.parse import urlsplit")
    assert _forbidden_runtime_surface(PACKAGE / "standard_http.py", tree) == []
    assert _forbidden_runtime_surface(PACKAGE / "standard_cli.py", tree)


@pytest.mark.parametrize(
    "source",
    [
        "from urllib.request import urlopen",
        "from urllib import request",
        "import urllib.parse",
        "from urllib.parse import *",
        "from urllib.parse import urlsplit, urljoin",
        "from urllib.parse import urlsplit as parser",
        "import subprocess",
        "import socket",
        "eval('untrusted')",
    ],
)
def test_core02_url_parser_exception_keeps_network_and_dynamic_execution_denied(source):
    assert _forbidden_runtime_surface(PACKAGE / "standard_http.py", ast.parse(source))


def test_c08_projection_contains_only_literal_false_eligibility() -> None:
    source = (PACKAGE / "model.py").read_text(encoding="utf-8")
    assert 'item is not False for item in copied["eligibility"].values()' in source
    for forbidden in (
        "ScoreResult(",
        "ArchiveAcknowledgement(",
        "SettlementObligation(",
        "WeightIntent(",
    ):
        assert forbidden not in source
