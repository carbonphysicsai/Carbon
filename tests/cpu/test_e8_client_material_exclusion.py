"""E8: no Workbench client material reaches the subnet or the public assistant.

Owner decision (counsel brief v1, 8.1 item 2; owner decision record E1-E9,
23 September 2026): absolute exclusion, no opt-in, no configuration flag. In an
engineering brief the parameters are the secret, so sanitising either leaves the
secret in or leaves nothing worth computing, and subnet miners are pseudonymous,
global and uncontracted, so no agreement or deletion promise can follow the data.

These tests assert the absence of a route rather than the presence of a check.
Each one plants a sentinel in every client-controlled field, drives the real
route, and then searches everything that crossed the boundary, byte for byte.
Each absence is paired with a specimen showing the sentinel really was in the
material that went in, so a search that stopped matching fails instead of
passing quietly.

The two routes that exist, and why they cannot carry client material:

* Study route (Workbench -> ``WorkbenchScience`` -> research campaign). The
  only numerical input allowed to cross must equal the one granted public
  definition exactly, so a client parameter cannot pass that comparison, and
  the research call is built from a fixed material name and a digest. To
  reintroduce a route a caller would have to change that equality in the
  scientific contract of ``WorkbenchScience``, and the sentinel test fails.
* Authoring route (Workbench design -> ``authoring_bridge`` -> Challenge
  proposal). The compiled input is built from source-owned constants, the
  closed goal enum and a digest-derived identifier. The design's text,
  including its identifiers, is never read into it. Reintroducing a route means
  reading a request field into ``compile_request``'s input, and the sentinel test
  fails.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "tests/cpu")]

SENTINEL = "E8SENTINEL7Q3"
CLIENT_SCHEMA_PREFIXES = (
    "carbon.client-intake.",
    "carbon.private-team-intake.",
    "carbon.public-workbench.",
    "carbon.goal-workbench.workspace.",
    "carbon.goal-workbench.design.",
    "carbon.goal-workbench.team-",
    "carbon.goal-workbench.client-",
    "carbon.goal-workbench.internal-execution-brief",
)


def _everything(root: Path) -> bytes:
    """Every byte under ``root``, with SQLite databases read row by row."""
    out = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix in {".sqlite3", ".db"}:
            with sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True) as db:
                for (table,) in db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall():
                    for row in db.execute(f'SELECT * FROM "{table}"'):
                        out.append(repr(row).encode())
        else:
            out.append(path.read_bytes())
    return b"\n".join(out)


def _study(tmp_path, monkeypatch):
    from test_workbench_science import configured

    from carbon.scientific_tasks.workbench import (
        REQUEST,
        TEMPLATE,
        RegisteredWorkbenchDraft,
        wire_digest,
    )

    service, _request, records, _ledger, _executions, _calls, composition = configured(
        tmp_path, monkeypatch
    )
    owner = service.adapter.principal
    physical = asyncio.run(service.capabilities())["physical"]
    scope = {
        key: f"{SENTINEL} client {key}"
        for key in (
            "inputs",
            "outputs",
            "units",
            "geometry",
            "conditions",
            "regime",
            "exclusions",
            "query_workload",
            "reference_equation",
            "reference_method",
        )
    }
    scope.update(
        physics_family=TEMPLATE,
        requested_goal="Dynamics",
        rights_scope="SYNTHETIC_INTERNAL",
    )
    job, design = f"job-{SENTINEL}", f"design-{SENTINEL}"
    records.clear()
    records[(owner, job, design, 1)] = RegisteredWorkbenchDraft(
        owner, job, design, 1, 1, scope, physical, "SYNTHETIC_INTERNAL"
    )
    binding = {
        "job_id": job,
        "design_id": design,
        "design_revision": 1,
        "physical_sha256": wire_digest(
            {"template_id": TEMPLATE, "physical": physical, "draft_scope": scope}
        ),
    }
    request = {
        "schema": REQUEST,
        "operation_id": "study-" + wire_digest(binding),
        "action": "REFERENCE_FEASIBILITY",
        "binding": binding,
        "template_id": TEMPLATE,
        "physical": physical,
        "draft_scope": scope,
        "rights_scope": "SYNTHETIC_INTERNAL",
    }
    crossed = []
    call = service.adapter.call

    async def recording(tool_request):
        crossed.append(repr(tool_request))
        return await call(tool_request)

    monkeypatch.setattr(service.adapter, "call", recording)
    return service, request, crossed, composition


def test_client_text_in_every_study_field_crosses_nothing_to_the_research_service(
    tmp_path, monkeypatch
):
    service, request, crossed, composition = _study(tmp_path, monkeypatch)
    try:
        # Specimen: the sentinel is really in the material that went in.
        assert SENTINEL in json.dumps(request)
        result = asyncio.run(service.call("start", request))
        assert result["status"] == "COMPLETE"
        for action in ("status", "result"):
            asyncio.run(service.call(action, request))
    finally:
        composition.tasks.close()
    assert crossed, "the study route was exercised"
    assert all(SENTINEL not in item for item in crossed), crossed
    # And nothing the research side persisted holds it: the campaign ledger, the
    # task store and the worker scratch, read in full.
    for persisted in (
        _everything(tmp_path / "campaign"),
        _everything(tmp_path / "tasks"),
    ):
        assert persisted, "the research side persisted something to search"
        assert SENTINEL.encode() not in persisted


def test_a_client_parameter_cannot_cross_as_the_physical_definition(
    tmp_path, monkeypatch
):
    service, request, crossed, composition = _study(tmp_path, monkeypatch)
    try:
        client = json.loads(json.dumps(request))
        client["physical"]["viscosity"] = 0.0123456789
        with pytest.raises((ValueError, PermissionError)):
            asyncio.run(service.call("start", client))
        assert crossed == []
        # Specimen: the unmodified public definition does cross.
        asyncio.run(service.call("start", request))
        assert crossed
    finally:
        composition.tasks.close()


def _bridge():
    path = ROOT / "Business/Carbon_Fit/workbench/tools/authoring_bridge.py"
    spec = importlib.util.spec_from_file_location("e8_authoring_bridge", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_client_text_in_an_authoring_request_never_reaches_the_challenge_proposal(
    tmp_path,
):
    bridge = _bridge()
    request = {
        "schema_version": bridge.REQUEST_SCHEMA,
        "request_id": f"request-{SENTINEL}",
        "job_id": f"job-{SENTINEL}",
        "design_id": f"design-{SENTINEL}",
        "design_revision": 1,
        "template_id": bridge.TEMPLATE,
        "requested_goal": "Dynamics",
        "intended_use": f"{SENTINEL} viscosity 0.0123456789 and the client's "
        "confidential operating envelope, stated in their own words.",
        "rights_scope": "SYNTHETIC_INTERNAL",
        "expected_semantics": {
            "physics_family": bridge.TEMPLATE,
            "active_goal": "Dynamics",
            "rights_scope": "SYNTHETIC_INTERNAL",
        },
        "compatibility": {
            "status": "EXACT_SUPPORTED",
            "source_template": bridge.TEMPLATE,
            "gaps": [],
        },
        "route": "LOCAL_FIXED_CLI",
        "authority": "DEVELOPMENT_REQUEST_ONLY",
    }
    request_path = tmp_path / "request.json"
    request_path.write_text(json.dumps(request))
    # Specimen: the sentinel is in the request the bridge was given.
    assert SENTINEL.encode() in request_path.read_bytes()
    output = tmp_path / "out"
    bridge.compile_request(request_path, output)
    native_input = (output / "native-input.json").read_bytes()
    proposal = _everything(output / "native-output")
    assert native_input and proposal, "the bridge compiled a proposal"
    for crossed in (native_input, proposal):
        assert SENTINEL.encode() not in crossed
        assert b"0.0123456789" not in crossed
    assert json.loads(native_input)["intended_use"] == bridge.TEMPLATE_INTENDED_USE


def _mentions(root: Path, suffixes) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for path in sorted(root.rglob("*")):
        if path.suffix not in suffixes or not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        hits = [prefix for prefix in CLIENT_SCHEMA_PREFIXES if prefix in text]
        if hits:
            found[str(path.relative_to(ROOT))] = hits
    return found


# The one client-intake identifier the public assistant accepts. It is the
# Pilot Designer's guidance context: what a visitor types into the public site
# themselves, before Carbon has received anything. Whether E8 extends to that
# pre-receipt text is recorded as an open owner question under GOAL-WORKBENCH-15;
# it is named here so that it cannot widen without this test changing.
ASSISTANT_ALLOWED = {
    "website/ask-carbon/worker/core.mjs": ["carbon.client-intake."],
}


def test_no_subnet_or_assistant_code_names_a_client_record_format():
    subnet = _mentions(ROOT / "carbon", {".py"}) | _mentions(
        ROOT / "scripts", {".py", ".sh"}
    )
    assistant = _mentions(ROOT / "website/ask-carbon/worker", {".mjs", ".js"}) | (
        _mentions(ROOT / "website/ask-carbon/public", {".mjs", ".js"})
    )
    assert subnet == {}
    assert assistant == ASSISTANT_ALLOWED
    # Specimen: the same scan finds the formats where client records live.
    workbench = _mentions(ROOT / "Business/Carbon_Fit/workbench/src", {".js"})
    assert "Business/Carbon_Fit/workbench/src/intake.js" in workbench
    receiver = _mentions(ROOT / "Business/Carbon_Fit/workbench/tools", {".cjs"})
    assert "Business/Carbon_Fit/workbench/tools/team_intake_store.cjs" in receiver
