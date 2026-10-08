"""The demo fixture, and one document through both doors (RSURF-D1, D7).

- `carbon_campaign_view` over MCP and its browser route return the same
  document, and a note posted through either is in the view the other reads.
- The fixture refuses every operation that starts work, opens no ledger and
  is labelled SYNTHETIC_FIXTURE everywhere; nothing under `carbon` imports it.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from scripts.dev.miner_launchpad.controller import Rejected

ROOT = Path(__file__).resolve().parents[2]


def _fixture():
    from scripts.dev.miner_launchpad.research_fixture import FixtureRunner

    return FixtureRunner(clock=lambda: 1_790_000_000.0)


def test_mcp_and_http_return_the_same_campaign_view(tmp_path):
    import threading

    from test_miner_launchpad import auth, request

    from carbon.miner_mcp.mcp_operations import PREFIX, make_operation_tools
    from scripts.dev.miner_launchpad import controller
    from scripts.dev.miner_launchpad.research_fixture import CAMPAIGN

    host = _fixture()
    server = controller.Server(
        controller.Controller(tmp_path / "r.sqlite3"),
        "x" * 40,
        port=0,
        research_runner=host,
    )
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        tools = {t.name: t for t in make_operation_tools(host)}
        for body in (
            {"campaign": CAMPAIGN},
            {
                "campaign": CAMPAIGN,
                "experiment": "fixture-run-03",
                "practice_case": host.view.case_ids()[5],
            },
        ):
            code, _, content = request(
                server, "/api/v1/operations/campaign_view", "POST", body, auth()
            )
            via_mcp = asyncio.run(tools[PREFIX + "campaign_view"].fn(**body))
            assert code == 200
            assert json.loads(content) == via_mcp.payload
            assert via_mcp.official_eligible is False
        selected = via_mcp.payload["per_case"]["selected"]
        assert selected["case_id"] == host.view.case_ids()[5]
        # A note posted through one door is in the view the other reads.
        code, _, _ = request(
            server,
            "/api/v1/operations/note",
            "POST",
            {
                "campaign": CAMPAIGN,
                "note_kind": "hypothesis",
                "note": "from the browser",
            },
            auth(),
        )
        assert code == 200
        asyncio.run(
            tools[PREFIX + "note"].fn(
                campaign=CAMPAIGN, note_kind="plan", note="from an agent"
            )
        )
        texts = [e["text"] for e in host.view_document()["journal"]["entries"]]
        assert texts[:2] == ["from an agent", "from the browser"]
    finally:
        server.shutdown()
        server.server_close()


def test_the_fixture_cannot_start_work_or_reach_a_ledger():
    from scripts.dev.miner_launchpad.operations import OPERATIONS, perform
    from scripts.dev.miner_launchpad.research_fixture import CAMPAIGN, EVIDENCE

    host = _fixture()
    for name, op in OPERATIONS.items():
        if not op.admits_work and name not in ("halt",):
            continue
        request = {field: "x" for field in op.required}
        request.update(
            {
                "campaign": CAMPAIGN,
                "agent": "none",
                "action": "stop",
                "idempotency_key": "k" * 20,
            }
        )
        request = {k: v for k, v in request.items() if k in op.required | op.optional}
        with pytest.raises(Rejected) as refused:
            perform(host, name, request)
        assert refused.value.code == "fixture_read_only", name
    with pytest.raises(Rejected):
        host.control(CAMPAIGN, "resume")
    doc = host.view_document()
    assert doc["fixture"] is True and doc["labels"]["evidence"] == EVIDENCE
    assert doc["campaign"]["id"].startswith("fixture-")
    assert not any(c["available"] for c in doc["controls"])
    assert doc["official_eligible"] is False
    assert host.preflight()["available"] is False
    for item in host.recent():
        assert item["mode"] == EVIDENCE and item["official_eligible"] is False
    # Nothing under `carbon` can import it: it is outside the package.
    found = subprocess.run(
        ["grep", "-rl", "research_fixture", str(ROOT / "carbon")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert found.stdout == ""


def test_the_fixture_draws_the_whole_surface():
    doc = _fixture().view_document()
    assert {c["id"] for c in doc["charts"]} == {
        "components",
        "trend_score",
        "trend_components",
        "learning_curve",
    }
    assert doc["per_case"]["status"] == "AVAILABLE"
    assert [s["state"] for s in doc["stages"]] == ["done", "current", "done", "done"]
    assert doc["candidates"] and doc["outcomes"] and doc["journal"]["entries"]
    # Filled from the fixture Challenge's ladder data (LAUNCHPAD-LEVELS-01
    # S1): the campaign's own level, never inferred.
    from scripts.dev.miner_launchpad.ladder_view import construction_slot

    slot = doc["contract"]["construction_level"]
    assert slot == construction_slot(doc["contract"]["challenge"]["id"])
    assert slot["level"] == 0 and slot["status"] == "DEFINED"
