"""The door's chain reader turns an uncollected failure of the SDK's session task (bittensor 11.1 `RpcSession._run`,
task "rpc-session") into ONE typed line, never a Traceback (Deploy-B / release-impl-B staging drills F1 / F3 / R7,
7 Nov: "Task exception was never retrieved" on an HTTP 429 refusal and on the own node being down, while the door kept
serving). Anything else keeps asyncio's default report. Fake exception types only; no network.
"""

from __future__ import annotations

import asyncio
import gc
import logging

import pytest

from carbon.chain import sdk


def _transport_error(name, module="bittensor._transport.errors"):
    return type(name, (Exception,), {"__module__": module})


MaxRetriesExceeded = _transport_error("MaxRetriesExceeded")
RpcPolicyRejection = _transport_error("RpcPolicyRejection")
InvalidStatus = _transport_error("InvalidStatus", "websockets.exceptions")


def _orphan(loop, failure, name):
    """A task that fails and is never awaited, then freed: what the SDK's session task does on a failed dial."""

    async def run():
        raise failure

    async def main():
        task = asyncio.get_running_loop().create_task(run(), name=name)
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        assert task.done()
        del task

    loop.run_until_complete(main())
    gc.collect()


@pytest.fixture
def loop():
    loop = asyncio.new_event_loop()
    loop.set_exception_handler(sdk.session_exception_handler)
    yield loop
    loop.close()


@pytest.mark.parametrize(
    "failure",
    [
        MaxRetriesExceeded("could not connect to any endpoint: [Errno 111]"),
        RpcPolicyRejection("RPC endpoint rate limited this source (HTTP 429)"),
        InvalidStatus("server rejected WebSocket connection: HTTP 429"),
        ConnectionRefusedError(111, "Connect call failed"),
        TimeoutError(),
    ],
)
def test_a_freed_session_task_failure_is_one_typed_line(loop, caplog, failure):
    caplog.set_level(logging.DEBUG)
    _orphan(loop, failure, sdk.SESSION_TASK)
    lines = [r.getMessage() for r in caplog.records]
    assert lines == [f"chain_session_error kind={type(failure).__name__}"]
    assert not any("never retrieved" in line for line in lines)
    assert all(r.exc_info is None for r in caplog.records)  # no Traceback


def test_a_carbon_bug_in_the_session_task_keeps_its_traceback(loop, caplog):
    caplog.set_level(logging.DEBUG)
    _orphan(loop, KeyError("a bug, not the chain"), sdk.SESSION_TASK)
    assert any("never retrieved" in r.getMessage() for r in caplog.records)
    assert not any("chain_session_error" in r.getMessage() for r in caplog.records)


def test_another_tasks_transport_failure_keeps_its_traceback(loop, caplog):
    caplog.set_level(logging.DEBUG)
    _orphan(loop, MaxRetriesExceeded("x"), "some-other-task")
    assert any("never retrieved" in r.getMessage() for r in caplog.records)
    assert not any("chain_session_error" in r.getMessage() for r in caplog.records)


def test_the_door_reader_loop_carries_the_handler():
    reader = sdk.PersistentBittensorReader()
    loop = reader._ensure_loop()
    assert loop.get_exception_handler() is sdk.session_exception_handler
    assert reader._ensure_loop() is loop  # one loop for the reader's life


def test_the_session_task_name_is_the_sdks():
    """Pinned to bittensor 11.1's `RpcSession._run` task name (a later SDK must re-check it)."""
    assert sdk.SDK_VERSION == "11.1.0" and sdk.SESSION_TASK == "rpc-session"


def test_the_installed_sdk_names_its_session_task_so():
    """The installed SDK (canonical environment) creates its connection task under exactly this name. The orphan itself
    appears only when an OPEN connection drops and the SDK re-dials in the background (drills F1 / F3 / R7), which the
    staging drill rerun shows end to end."""
    pytest.importorskip("bittensor")
    import inspect

    from bittensor._transport import rpc

    assert f'create_task(self._run(), name="{sdk.SESSION_TASK}")' in inspect.getsource(
        rpc
    )
