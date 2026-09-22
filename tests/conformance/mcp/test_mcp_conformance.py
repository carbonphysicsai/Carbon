"""The conformance suite must accept a conforming server and reject broken ones.

A conformance suite that passes against a non-conforming server is worse than no
suite, because it manufactures confidence. These tests are the control pair:

* the positive control runs the suite against the real Carbon stdio server and
  requires a clean conformant verdict;
* each negative control runs it against a server that violates exactly one
  published requirement and requires that the *named* check for that
  requirement failed, not merely that something failed.

Nothing here qualifies a server. A conforming server is not a qualified one.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[3]
SUITE = Path(__file__).parent
STUBS = SUITE / "stubs"
RUNNER = SUITE / "conformance.mjs"

# A shape check is falsified by mutating its own expectation: if the real server
# still passes with the expectation inverted, the check is not reading what it
# claims to read. That is exactly how the leak check was vacuous.
MUTATION_CONTROLS = {
    "prefix": "catalogue_prefix_and_strict_schemas",
    "principal": "catalogue_rejects_caller_supplied_principal",
    "json_envelopes": "catalogue_uses_objects_not_json_envelopes",
    "encoded_accepted": "strict_inputs_reject_encoded_objects",
    "schema_claims_dispatch": "schema_rejection_precedes_dispatch",
    "impossible_code": "adapter_error_contract",
}

# Each stub violates one requirement and must fail that requirement's check.
NEGATIVE_CONTROLS = {
    "duplicate_dispatch": "operation_identity_replay_does_not_redispatch",
    "changed_input_accepted": "operation_identity_conflict_is_refused",
    "cancel_claims_release": "cancellation_is_a_request_not_a_release",
    "error_leaks_internals": "errors_do_not_leak_internals",
    "advertises_unperformable": "capability_discovery_is_performable",
    "loses_task_identity": "durable_identity_survives_reconnect",
}


def _node() -> str:
    node = os.environ.get("CARBON_MCP_CONFORMANCE_NODE") or shutil.which("node")
    installed = SUITE / "node_modules/@modelcontextprotocol/client"
    if not node or not installed.is_dir():
        reason = (
            "the MCP conformance runner requires Node >=20 and its locked client "
            "install: pnpm install --frozen-lockfile --ignore-scripts in "
            "tests/conformance/mcp"
        )
        if os.environ.get("CARBON_REQUIRE_MCP_CONFORMANCE") == "1":
            pytest.fail(reason)
        pytest.skip(reason)
    return node


def _run(launch: dict, *, mutate: str | None = None) -> tuple[int, dict]:
    """Run the suite against one endpoint and return its exit code and report."""
    environment = dict(os.environ)
    if mutate is not None:
        environment["CARBON_CONFORMANCE_MUTATE"] = mutate
    result = subprocess.run(
        [_node(), str(RUNNER), "--stdio", json.dumps(launch)],
        cwd=REPOSITORY,
        text=True,
        capture_output=True,
        timeout=300,
        check=False,
        env=environment,
    )
    if not result.stdout.strip():
        raise AssertionError(
            f"the runner produced no report (exit {result.returncode}): "
            f"{result.stderr[-600:]}"
        )
    return result.returncode, json.loads(result.stdout)


def _status(report: dict) -> dict[str, str]:
    return {check["id"]: check["status"] for check in report["checks"]}


def test_suite_accepts_the_real_server(tmp_path):
    """Positive control: the real Carbon stdio server is judged conformant."""
    code, report = _run(
        {
            "command": sys.executable,
            "args": [
                str(REPOSITORY / "tests/service/test_standard_mcp_stdio.py"),
                "--serve",
                str(tmp_path),
            ],
            "cwd": str(REPOSITORY),
        }
    )
    statuses = _status(report)
    failed = {name: value for name, value in statuses.items() if value != "PASS"}
    assert not failed, f"the real server was not judged conformant: {failed}"
    assert report["conformant"] is True
    assert report["summary"]["fail"] == 0
    # Undetermined is not conformance; the runner must have obtained evidence.
    assert report["summary"]["undetermined"] == 0
    assert code == 0
    assert (
        report["authority"]
        == "PROTOCOL_CONFORMANCE_ONLY_NOT_SECURITY_OR_SCIENTIFIC_QUALIFICATION"
    )


@pytest.mark.parametrize("stub,expected", sorted(NEGATIVE_CONTROLS.items()))
def test_suite_rejects_each_non_conforming_server(stub, expected):
    """Negative control: the named check for the violated requirement fails."""
    code, report = _run(
        {
            "command": sys.executable,
            "args": [str(STUBS / f"{stub}.py")],
            "cwd": str(REPOSITORY),
            "env": {"PYTHONPATH": str(STUBS), "PATH": os.environ.get("PATH", "")},
        }
    )
    statuses = _status(report)
    assert expected in statuses, f"the suite never ran the check {stub} should fail"
    assert statuses[expected] == "FAIL", (
        f"{stub} violates {expected} but the suite reported "
        f"{statuses[expected]}; the check does not detect its own requirement"
    )
    assert report["conformant"] is False
    assert code != 0, "a non-conforming server must produce a non-zero exit"


def test_every_stub_has_a_control_and_documents_its_violation():
    """No stub ships without a check that rejects it and a stated violation."""
    shipped = {
        path.stem
        for path in STUBS.glob("*.py")
        if path.stem not in {"scaffold", "__init__"}
    }
    assert shipped == set(NEGATIVE_CONTROLS), (
        "every stub must be bound to the check it proves: "
        f"unbound={sorted(shipped - set(NEGATIVE_CONTROLS))} "
        f"missing={sorted(set(NEGATIVE_CONTROLS) - shipped)}"
    )
    for stub in shipped:
        text = (STUBS / f"{stub}.py").read_text(encoding="utf-8")
        assert "VIOLATION:" in text, f"{stub} does not state its violation"
        assert (
            NEGATIVE_CONTROLS[stub] in text
        ), f"{stub} does not name the check it is meant to fail"


@pytest.mark.parametrize("mutation,expected", sorted(MUTATION_CONTROLS.items()))
def test_each_shape_check_discriminates(tmp_path, mutation, expected):
    """Inverting a shape check's expectation must make the real server fail it.

    A check that still passes with its expectation inverted is vacuous: it is
    not reading what it claims to read, and a PASS from it means nothing.
    """
    launch = {
        "command": sys.executable,
        "args": [
            str(REPOSITORY / "tests/service/test_standard_mcp_stdio.py"),
            "--serve",
            str(tmp_path),
        ],
        "cwd": str(REPOSITORY),
    }
    _, report = _run(launch, mutate=mutation)
    statuses = _status(report)
    assert statuses[expected] == "FAIL", (
        f"with expectation '{mutation}' inverted, {expected} still reported "
        f"{statuses[expected]}; the check does not discriminate and any PASS "
        "from it is vacuous"
    )


def test_controlled_checks_match_the_shipped_stubs(tmp_path):
    """The report's falsifiability claim must match the stubs that exist.

    The runner marks each check ``controlled`` or not. That claim is only worth
    anything if it tracks reality, so it is asserted against the stubs actually
    shipped rather than maintained by hand.
    """
    _, report = _run(
        {
            "command": sys.executable,
            "args": [
                str(REPOSITORY / "tests/service/test_standard_mcp_stdio.py"),
                "--serve",
                str(tmp_path),
            ],
            "cwd": str(REPOSITORY),
        }
    )
    by_stub = {c["id"] for c in report["checks"] if c["control"] == "stub"}
    assert by_stub == set(NEGATIVE_CONTROLS.values()), (
        "the runner's stub-controlled list drifted from the shipped stubs: "
        f"claimed={sorted(by_stub)} proven={sorted(set(NEGATIVE_CONTROLS.values()))}"
    )
    by_mutation = {c["id"] for c in report["checks"] if c["control"] == "mutation"}
    assert by_mutation == set(MUTATION_CONTROLS.values()), (
        "the runner's mutation-controlled list drifted from the mutations that "
        f"are exercised: claimed={sorted(by_mutation)} "
        f"exercised={sorted(set(MUTATION_CONTROLS.values()))}"
    )
    assert report["summary"]["controlled_by_stub"] == len(by_stub)
    assert report["summary"]["controlled_by_mutation"] == len(by_mutation)
    # Every check must carry a control; an uncontrolled check is a claim with
    # nothing behind it, and shipping one silently is the failure this suite
    # exists to prevent.
    assert report["summary"]["uncontrolled"] == 0, [
        c["id"] for c in report["checks"] if c["control"] == "none"
    ]


def test_the_conformance_lane_is_actually_wired():
    """A suite that ships but never runs manufactures the confidence it tests.

    The lane sits behind two nested environment conditions, either of which would
    silently disable it if a workflow changed. This asserts both the invocation
    and the conditions it depends on, so "required, not skipped" stays true.
    """
    ci = (REPOSITORY / "scripts/dev/ci.sh").read_text(encoding="utf-8")
    assert (
        "tests/conformance/mcp" in ci
    ), "scripts/dev/ci.sh does not run the conformance suite at all"
    assert "CARBON_REQUIRE_MCP_CONFORMANCE=1" in ci, (
        "the lane runs the suite without requiring it, so a missing client "
        "install would skip every control silently"
    )

    workflow = (REPOSITORY / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    # Condition one: the mcp dependency group, which gates the outer block.
    assert (
        'CARBON_UV_GROUPS: "chain archive science-jax mcp"' in workflow
    ), "the canonical job no longer requests the mcp group, so the lane is dead"
    # Condition two: the interoperability flag, which gates the inner block.
    assert (
        'CARBON_REQUIRE_TYPESCRIPT_INTEROP: "1"' in workflow
    ), "the canonical job no longer sets the flag the conformance lane sits behind"


def test_the_leak_stub_still_leaks_without_a_literal_host_path():
    """Satisfying the hygiene scanner must not defang the stub.

    The leak fixture assembles its host path at runtime because the delivery
    hygiene scanner cannot distinguish a deliberate fixture from a real slip.
    Both halves are asserted here: that the source carries no literal host path,
    so the scanner stays useful for genuine slips, and that the value it builds
    is still something the conformance leak check detects. Fixing only the first
    would quietly turn the negative control into a no-op.
    """
    import importlib.util
    import re

    source_path = STUBS / "error_leaks_internals.py"
    source = source_path.read_text(encoding="utf-8")
    assert not re.search(
        r"(?<![A-Za-z0-9_.-])/(?:Users|home)[\\/]+\w", source
    ), "the stub reintroduced a literal host path, which the hygiene scanner rejects"

    specification = importlib.util.spec_from_file_location(
        "conformance_leak_stub", source_path
    )
    module = importlib.util.module_from_spec(specification)
    sys.path.insert(0, str(STUBS))
    try:
        specification.loader.exec_module(module)
    finally:
        sys.path.remove(str(STUBS))

    # The same patterns the runner judges refusals against.
    assert re.search(
        r"/(?:home|Users|root|private|var/folders)/", module.LEAKED_PATH
    ), "the assembled path is no longer a detectable host-path leak"
    assert re.search(
        r"\b(Bearer|token|secret|password|api[_-]?key)\b\s*[:=]\s*\S+",
        module.LEAKED_CREDENTIAL,
    ), "the assembled credential is no longer a detectable credential leak"
