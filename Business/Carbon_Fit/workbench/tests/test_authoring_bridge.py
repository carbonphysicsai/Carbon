from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]
BRIDGE_PATH = ROOT / "Business/Carbon_Fit/workbench/tools/authoring_bridge.py"
SPEC = importlib.util.spec_from_file_location(
    "goal_workbench_authoring_bridge", BRIDGE_PATH
)
assert SPEC is not None and SPEC.loader is not None
bridge = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bridge)


def request(goal: str = "Dynamics", **changes: object) -> dict[str, object]:
    value: dict[str, object] = {
        "schema_version": bridge.REQUEST_SCHEMA,
        "request_id": "authoring-request-1",
        "job_id": "job-1",
        "design_id": "job-1-design-1",
        "design_revision": 1,
        "template_id": bridge.TEMPLATE,
        "requested_goal": goal,
        "intended_use": (
            "Evaluate the bounded public DEVELOPMENT Burgers template while "
            "retaining all qualification and launch limitations."
        ),
        "rights_scope": "SYNTHETIC_INTERNAL",
        "expected_semantics": {
            "physics_family": bridge.TEMPLATE,
            "active_goal": goal,
            "rights_scope": "SYNTHETIC_INTERNAL",
        },
        "compatibility": {
            "status": "EXACT_SUPPORTED" if goal == "Dynamics" else "EXTENSION_REQUIRED",
            "source_template": bridge.TEMPLATE,
            "gaps": (
                [] if goal == "Dynamics" else ["requested active goal is not Dynamics"]
            ),
        },
        "route": "LOCAL_FIXED_CLI",
        "authority": "DEVELOPMENT_REQUEST_ONLY",
    }
    value.update(changes)
    return value


def write_request(path: Path, value: dict[str, object]) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def test_exact_burgers_dynamics_round_trip_preserves_intent_and_bytes(
    tmp_path: Path,
) -> None:
    request_path = tmp_path / "request.json"
    write_request(request_path, request())

    result_path = bridge.compile_request(request_path, tmp_path / "result")
    first_bytes = result_path.read_bytes()
    result = json.loads(first_bytes)

    assert result["semantic_receipt"]["status"] == "INTENT_PRESERVED"
    assert result["proposal"]["challenge"]["primary_goal"] == "Dynamics"
    assert result["proposal"]["capabilities"] == {
        "archive_acknowledged": False,
        "network_authorized": False,
        "payout_authorized": False,
        "registered": False,
        "scientifically_qualified": False,
    }
    assert result["route"] == "LOCAL_FIXED_CLI"

    replay_path = bridge.compile_request(request_path, tmp_path / "result")
    assert replay_path.read_bytes() == first_bytes


def test_front_resolution_compiles_actual_dynamics_but_reports_mismatch(
    tmp_path: Path,
) -> None:
    request_path = tmp_path / "request.json"
    write_request(request_path, request("Front Resolution"))

    result = json.loads(
        bridge.compile_request(request_path, tmp_path / "result").read_bytes()
    )

    assert result["proposal"]["challenge"]["primary_goal"] == "Dynamics"
    assert result["proposal"]["evidence_boundary"]["source_goal"] == "Front Resolution"
    assert result["semantic_receipt"]["status"] == "INTENT_MISMATCH"
    assert result["semantic_receipt"]["mismatches"][0] == (
        "requested active goal Front Resolution emitted as Dynamics"
    )
    assert result["semantic_receipt"]["mismatches"][1] == (
        "workbench design has unresolved semantic bindings: "
        "requested active goal is not Dynamics"
    )


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"template_id": "customer_heat_transfer_v1"}, "template is unavailable"),
        ({"rights_scope": "CLIENT_RESTRICTED"}, "cannot relabel client"),
        ({"authority": "SCIENTIFICALLY_QUALIFIED"}, "authority promotion"),
    ],
)
def test_bridge_rejects_scope_rights_and_authority_substitution(
    tmp_path: Path, change: dict[str, object], message: str
) -> None:
    request_path = tmp_path / "request.json"
    write_request(request_path, request(**change))

    with pytest.raises(ValueError, match=message):
        bridge.compile_request(request_path, tmp_path / "result")


def test_bridge_rejects_duplicate_json_members_before_execution(tmp_path: Path) -> None:
    request_path = tmp_path / "request.json"
    request_path.write_text(
        '{"schema_version":"carbon.goal-workbench.authoring-request.v1",'
        '"schema_version":"carbon.goal-workbench.authoring-request.v1"}',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="duplicate JSON member"):
        bridge.compile_request(request_path, tmp_path / "result")


def test_bridge_rejects_unsafe_integer_and_excessive_nesting(tmp_path: Path) -> None:
    request_path = tmp_path / "request.json"
    unsafe = request()
    unsafe["expected_semantics"] = {"count": 9_007_199_254_740_992}
    write_request(request_path, unsafe)
    with pytest.raises(ValueError, match="unsafe for browser round trips"):
        bridge.compile_request(request_path, tmp_path / "unsafe")

    nested: object = "leaf"
    for _ in range(26):
        nested = {"next": nested}
    deep = request()
    deep["expected_semantics"] = nested
    write_request(request_path, deep)
    with pytest.raises(ValueError, match="nesting exceeds"):
        bridge.compile_request(request_path, tmp_path / "deep")


def test_existing_result_with_changed_request_fails_closed(tmp_path: Path) -> None:
    request_path = tmp_path / "request.json"
    output = tmp_path / "result"
    write_request(request_path, request())
    bridge.compile_request(request_path, output)
    write_request(request_path, request("Transport"))

    with pytest.raises(ValueError, match="authoring result conflict"):
        bridge.compile_request(request_path, output)
