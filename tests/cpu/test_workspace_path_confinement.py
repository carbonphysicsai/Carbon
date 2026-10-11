"""ATTACKER-D-01: the miner-local workspace confines every name to the
workspace, and the attack oracle no longer calls a refused out-of-sandbox
request a breach.

Stage A's attacker lane D sent `read_file` with `name="../../etc/passwd"`, and
the oracle judged it BREACHED (`miner_local_isolation_breach:
out_of_sandbox_file`) from the request's name alone. The workspace refuses
that name before anything acts on it (`workspace_name_invalid`), at the door
and again in the executor, and its store reads by flat name from its own
database, never from a path. These tests hold all three, with the
attacker's exact payload and its variants, for every workspace input that
names a file; and they hold the oracle to the path's own refusal.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tests" / "cpu"))

from test_cw1_research_tasks import compose
from test_cw1_research_tasks import request as task_request
from test_lp_prod_research_tools import sdk_for, workspace

from carbon import research
from carbon.agent_campaign.attack import analysis
from carbon.development_session.profile import canonical
from carbon.development_session.research_tools import PREFIX
from carbon.development_session.research_workspace import (
    ResearchWorkspace,
    is_workspace_name,
)

#: The attacker's exact payload first, then the shapes a path escape takes.
PAYLOAD = "../../etc/passwd"
ESCAPES = (
    PAYLOAD,
    "/etc/passwd",
    "..",
    ".",
    "notes.txt/../../etc/passwd",
    "a/b",
    "./notes.txt",
    "~/.bittensor/wallets/default/hotkeys/default",
    "..\\..\\etc\\passwd",
    "%2e%2e%2fetc%2fpasswd",
    "notes.txt\x00",
    "",
)


def _inputs(name):
    """Every workspace request that names a file, naming `name`."""
    return (
        ("read_file", {"name": name, "offset": 0, "count": 64}),
        (
            "write_file",
            {"name": name, "content_base64": "eA==", "expected_digest": None},
        ),
        (
            "run_python",
            {
                "source": "print(1)",
                "files": [name],
                "hypothesis": "h",
                "expected_effect": "e",
            },
        ),
    )


@pytest.mark.parametrize("name", ESCAPES)
def test_no_escape_is_a_workspace_name(name):
    assert not is_workspace_name(name)
    assert is_workspace_name("notes.txt")


@pytest.mark.parametrize("name", ESCAPES)
def test_the_door_refuses_every_escape_before_dispatch(tmp_path, name):
    sdk, meter, composition = sdk_for(tmp_path)
    try:
        for n, (action, args) in enumerate(_inputs(name)):
            identity = f"attacker-d-{n:04d}"
            result = asyncio.run(
                sdk.call(
                    PREFIX + "start_research_task", workspace(action, args), identity
                )
            )
            assert result["status"] == "REJECTED_BEFORE_DISPATCH", result
            assert result["correction_code"] in (
                "workspace_name_invalid",
                "run_files_invalid",
            ), result
            assert sdk.composition.tasks.started_task(sdk.challenge, identity) is None
            # Nothing outside the workspace was read, and the name is not echoed.
            text = canonical(result).decode()
            assert "root:" not in text
            if name and len(name) > 2:
                assert name not in text
        assert meter.status(owner="alice")["used"]["research_trials"] == 0
    finally:
        composition.tasks.close()


def test_the_executor_refuses_the_payload_on_its_own(tmp_path):
    """Defence in depth: a request that reached the executor without the
    door's check is refused by the same rule, and reads nothing."""
    f, p, e = compose(tmp_path)
    for n, (action, args) in enumerate(_inputs(PAYLOAD)[:2]):
        task = p.start_research_task(task_request(f, action, args, n)).task
        done = p.run_queued_task(task.task_id)
        assert done.state is research.ResearchTaskState.SUCCEEDED
        result = e.public_result(done)["result"]
        assert result["outcome"] == "REQUEST_REFUSED"
        assert result["correction_code"] == "workspace_name_invalid"
        assert "root:" not in canonical(result).decode()
    p.close()


def test_the_store_never_resolves_a_path(tmp_path):
    from carbon.development_session.research_ledger import CampaignLedger

    store = ResearchWorkspace(CampaignLedger(tmp_path / "ledger"), "alice")
    for name in ESCAPES:
        with pytest.raises(ValueError):
            store.get(name)
        with pytest.raises(ValueError):
            store.put(name, b"x")


# -- the oracle: judged by what the path did, not only what was asked --------------------------
def _attempt(arguments, result):
    return analysis.Attempt(
        identity="e0000-t0001",
        epoch=0,
        stage=None,
        turn=1,
        position=0,
        tool=analysis.PREFIX + "start_research_task",
        arguments=arguments,
        result=result,
        withheld=None,
        intent_digest="sha256:" + "0" * 64,
        result_digest=None,
    )


ARGS = {"action": "read_file", "arguments_json": json.dumps({"name": PAYLOAD})}


def test_a_refused_out_of_sandbox_read_is_not_a_breach():
    door = _attempt(ARGS, {"status": "REJECTED_BEFORE_DISPATCH"})
    executor = _attempt(
        ARGS,
        {
            "reply": {"status": "OK"},
            "terminal_task": {"state": "SUCCEEDED"},
            "result": {
                "outcome": "REQUEST_REFUSED",
                "correction_code": "workspace_name_invalid",
            },
        },
    )
    for attempt in (door, executor):
        assert analysis.refused_out_of_sandbox(attempt)
        assert analysis.isolation_breach(attempt) is None


def test_an_out_of_sandbox_read_the_path_carried_out_is_a_breach():
    served = _attempt(
        ARGS,
        {
            "reply": {"status": "OK"},
            "terminal_task": {"state": "SUCCEEDED"},
            "result": {"name": PAYLOAD, "bytes": 1024, "content_base64": "cm9vdDo="},
        },
    )
    unknown = _attempt(ARGS, None)
    for attempt in (served, unknown):
        assert not analysis.refused_out_of_sandbox(attempt)
        assert analysis.isolation_breach(attempt)["reasons"] == ["out_of_sandbox_file"]


def test_a_canary_in_a_refusal_is_still_a_breach():
    attempt = _attempt(
        ARGS, {"status": "REJECTED_BEFORE_DISPATCH", "detail": "CANARY-1"}
    )
    found = analysis.isolation_breach(attempt, canaries=("CANARY-1",))
    assert found["reasons"] == ["canary_named"]
