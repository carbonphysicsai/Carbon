"""Acceptance is explicit real-cell metadata, never execution or science."""

import asyncio
import copy
import json
import threading
from pathlib import Path

import pytest
import yaml
from test_miner_launchpad import auth, request
from test_miner_operations_doors import SpyHost

from carbon.miner_mcp import mcp_operations, mcp_setup
from scripts.dev.launchpad_acceptance import release_check as acceptance
from scripts.dev.miner_launchpad import controller

ROOT = Path(__file__).resolve().parents[2]
REVISION = "a" * 40


def record(root, cell="I1", result="PASS", **changes):
    """Synthetic public cell under tmp_path only; never real acceptance."""
    document = {
        "schema": acceptance.SCHEMA,
        "cell": cell,
        "date": "2026-01-01",
        "revision": REVISION,
        "machine_kind": "engineering fixture only",
        "result": result,
        "refusal_code": None,
        "evidence": {"source": "fixture-only-no-real-acceptance"},
        "within_cap": True,
        "actor": "engineering fixture only",
        **changes,
    }
    folder = root / acceptance.EVIDENCE / "launchpad-acceptance-2026-01-01/cells"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{cell}-{document.get('attempt', 0)}-{result}.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def test_default_and_successful_availability_are_untested(tmp_path):
    cells = acceptance.load_cells(tmp_path)
    payload = {
        "official_eligible": False,
        "score": {"gate": "PASS", "value": 1.0},
        "inference": [{"id": "engy-chat", "available": True, "verified": True}],
    }
    original = copy.deepcopy(payload)
    shown = acceptance.project(payload, cells=cells)
    assert shown["inference"][0]["acceptance"]["status"] == "UNTESTED"
    assert shown["score"] == payload["score"]
    assert not shown["official_eligible"]
    assert payload == original


def test_pass_is_bound_to_original_named_cell_revision_and_allowlist(tmp_path):
    path = record(tmp_path, evidence={"secret": "NEVER_PROJECT", "source": "fixture"})
    cells = acceptance.load_cells(tmp_path)
    status = acceptance.choice("inference", "engy-chat", cells=cells)
    assert status["status"] == "TESTED"
    assert status["cell"] == "I1" and status["revision"] == REVISION
    assert status["scope"] == "NAMED_CELL_REVISION_ONLY"
    assert status["evidence"] == path.relative_to(tmp_path).as_posix()
    assert "NEVER_PROJECT" not in json.dumps(status)
    assert "current_release_tested" not in status
    assert acceptance.choice("inference", "chutes", cells=cells)["status"] == "UNTESTED"


@pytest.mark.parametrize("result", ["FAIL", "BLOCKED"])
def test_newer_nonpass_revokes_older_pass(tmp_path, result):
    record(tmp_path)
    record(tmp_path, result=result, date="2026-01-02", revision="b" * 40)
    status = acceptance.load_cells(tmp_path).status("I1")
    assert status["status"] == "UNTESTED"
    assert status["result"] == result and status["revision"] == "b" * 40


def test_historical_attempts_keep_failure_then_named_pass(tmp_path):
    record(tmp_path, "F01", "FAIL", attempt=1)
    record(tmp_path, "F01", "PASS", attempt=2)
    cells = acceptance.load_cells(tmp_path)
    assert cells.status("F01")["status"] == "TESTED"
    assert cells.status("F01")["revision"] == REVISION
    # Install evidence never covers compute, an agent or an inference choice.
    assert (
        acceptance.choice("compute", "this-machine-cpu", cells=cells)["status"]
        == "UNTESTED"
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"revision": None},
        {"revision": "short"},
        {"within_cap": "true"},
        {"result": "TESTED"},
        {"attempt": True},
        {"date": "yesterday"},
    ],
)
def test_malformed_evidence_cannot_hide_behind_an_old_pass(tmp_path, changes):
    record(tmp_path)
    path = record(tmp_path, "I2", **changes)
    assert path.is_file()
    cells = acceptance.load_cells(tmp_path)
    assert cells.status("I1")["status"] == "UNTESTED"
    assert cells.status("I1")["reason"] == "EVIDENCE_UNUSABLE"


def test_equal_latest_conflicting_records_are_not_selected_by_filename(tmp_path):
    record(tmp_path, result="PASS")
    record(tmp_path, result="FAIL")
    assert acceptance.load_cells(tmp_path).status("I1")["status"] == "UNTESTED"


def test_actual_nonpass_record_keeps_its_result_when_outside_cap(tmp_path):
    record(tmp_path, result="FAIL", within_cap=False)
    status = acceptance.load_cells(tmp_path).status("I1")
    assert status["result"] == "FAIL" and status["status"] == "UNTESTED"


def test_duplicate_json_fields_and_symlinks_are_refused(tmp_path):
    path = record(tmp_path)
    raw = path.read_text()
    path.write_text(raw.replace('"result": "PASS"', '"result":"FAIL","result":"PASS"'))
    assert not acceptance.load_cells(tmp_path).usable
    path.unlink()
    target = tmp_path / "outside.json"
    target.write_text(raw)
    path.symlink_to(target)
    assert not acceptance.load_cells(tmp_path).usable


def test_deferred_levels_and_bootstrap_hold_do_not_change_availability(tmp_path):
    cells = acceptance.load_cells(tmp_path)
    payload = {"types": [{"type": "graph", "availability": "available"}]}
    shown = acceptance.project(payload, cells=cells)
    assert shown["types"][0]["availability"] == "available"
    status = shown["types"][0]["acceptance"]
    assert status["status"] == "UNTESTED" and status["result"] == "BLOCKED"
    assert "FIRST_REAL_F12" in status["reason"]
    assert (
        acceptance.choice("bootstrap", "publisher", cells=cells)["result"] == "BLOCKED"
    )


def test_choice_projection_covers_guides_snippets_and_new_options(tmp_path):
    record(tmp_path, "A4")
    record(tmp_path, "C6")
    payload = {
        "agent": [{"id": "own-agent", "connect": {"clients": [{"id": "codex"}]}}],
        "compute": [
            {
                "id": "remote-machine",
                "guides": {
                    "cards": [
                        {"id": "vast", "transport": "ssh-container"},
                        {"id": "new-provider"},
                    ]
                },
            }
        ],
    }
    cells = acceptance.load_cells(tmp_path)
    shown = acceptance.project(payload, cells=cells)
    assert shown["agent"][0]["connect"]["clients"][0]["acceptance"]["cell"] == "A4"
    cards = shown["compute"][0]["guides"]["cards"]
    assert cards[0]["acceptance"]["cell"] == "C6"
    assert cards[1]["acceptance"]["status"] == "UNTESTED"
    acceptance.check_labels(shown, cells=cells)
    cards[1]["acceptance"]["status"] = "TESTED"
    with pytest.raises(ValueError, match="unsupported"):
        acceptance.check_labels(shown, cells=cells)


def test_release_check_refuses_missing_labels_and_forged_revision(tmp_path):
    cells = acceptance.load_cells(tmp_path)
    raw = {"inference": [{"id": "engy-chat"}]}
    with pytest.raises(ValueError):
        acceptance.check_labels(raw, cells=cells)
    record(tmp_path)
    cells = acceptance.load_cells(tmp_path)
    shown = acceptance.project(raw, cells=cells)
    acceptance.check_labels(shown, cells=cells)
    shown["inference"][0]["acceptance"]["revision"] = "f" * 40
    with pytest.raises(ValueError):
        acceptance.check_labels(shown, cells=cells)


def test_both_real_doors_share_metadata_and_keep_closed_mcp_status(tmp_path):
    host = SpyHost()
    server = controller.Server(
        controller.Controller(tmp_path / "controller.sqlite3"),
        "x" * 40,
        port=0,
        research_runner=host,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        code, _, raw = request(server, "/api/v1/operations/options", "POST", {}, auth())
        tool = {t.name: t for t in mcp_operations.make_operation_tools(SpyHost())}[
            "carbon_options"
        ]
        result = asyncio.run(tool.fn())
        assert code == 200 and json.loads(raw) == result.payload
        assert result.acceptance_status == "UNTESTED"
        assert result.acceptance_choices == result.payload["acceptance_choices"]
        assert type(result).model_json_schema()["properties"]["acceptance_choices"][
            "additionalProperties"
        ]["enum"] == ["UNTESTED", "TESTED"]
        assert type(result).model_json_schema()["properties"]["acceptance_status"][
            "enum"
        ] == ["UNTESTED", "TESTED"]
        assert mcp_setup._models()[2].model_json_schema()["properties"][
            "acceptance_status"
        ]["enum"] == ["UNTESTED", "TESTED"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_rehearsal_wires_check_before_existing_release_build():
    workflow = yaml.safe_load(
        (ROOT / ".github/workflows/release-rehearsal.yml").read_text()
    )
    steps = workflow["jobs"]["rehearse"]["steps"]
    check = next(
        i
        for i, step in enumerate(steps)
        if "launchpad_acceptance.release_check" in step.get("run", "")
    )
    build = next(
        i
        for i, step in enumerate(steps)
        if "release_parent_rehearsal.sh" in step.get("run", "")
    )
    assert check < build and not steps[check].get("continue-on-error", False)


def test_both_browser_panes_render_acceptance_separately_from_readiness():
    app = (ROOT / "scripts/dev/miner_launchpad/app.js").read_text()
    pane = (ROOT / "scripts/dev/miner_launchpad/research_view.js").read_text()
    assert "function acceptanceText(item)" in app
    assert 'return "Untested"' in app
    assert 'value.scope === "NAMED_CELL_REVISION_ONLY"' in app
    assert "acceptanceText(client)" in app and "acceptanceText(change)" in app
    assert "CC.acceptanceText(acceptance)" in pane
