"""An interrupted campaign keeps why, privately, without its message.

Found in the live battery journey (Launchpad H, 2026-09-29): manual practice
ended INTERRUPTED with nothing recorded anywhere, and the cause
(TRANSPORT_CONFLICT) took a reproduction to find.
"""

import json
import stat

from test_miner_operation_idempotency import RECIPE, settle

from carbon.transport.models import TransportCode, TransportFailure
from scripts.dev.miner_launchpad.journey_fixture import (
    journey_host,
    register_fixture_challenge,
)
from scripts.dev.miner_launchpad.operations import perform
from scripts.dev.miner_launchpad.runner import record_interruption


class Leaky(RuntimeError):
    code = "PROVIDER_REFUSED"


def test_type_and_code_are_kept_and_the_message_is_not(tmp_path):
    exc = Leaky("response body with SECRET-SENTINEL")
    # Specimen: the sentinel is in what the exception carries.
    assert "SECRET-SENTINEL" in str(exc)
    record_interruption(tmp_path, "operation", exc)
    record_interruption(tmp_path, "run", TransportFailure(TransportCode.CONFLICT))
    path = tmp_path / "interruptions.jsonl"
    text = path.read_text()
    assert "SECRET-SENTINEL" not in text
    first, second = (json.loads(line) for line in text.splitlines())
    assert first["error_type"].endswith("Leaky") and first["code"] == "PROVIDER_REFUSED"
    assert second["code"] == TransportCode.CONFLICT.value
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_an_interrupted_operation_records_its_cause(tmp_path, monkeypatch):
    from carbon.development_session import research_campaign

    named = register_fixture_challenge(monkeypatch.setattr)
    tmp_path.chmod(0o700)
    host = journey_host(tmp_path, patch=monkeypatch.setattr, historical_launch=True)
    launched = perform(
        host,
        "launch",
        {**named, "agent": "none", "idempotency_key": "launch-key-0000001"},
    )
    assert settle(host, launched["id"])["state"] == "READY"

    async def refused(*args, **kwargs):
        raise TransportFailure(TransportCode.CONFLICT)

    monkeypatch.setattr(research_campaign, "practice_recipe", refused)
    perform(
        host,
        "practice",
        {
            "campaign": launched["id"],
            "strategy": RECIPE,
            "hypothesis": "record the cause",
            "idempotency_key": "practice-key-00001",
        },
    )
    view = settle(host, launched["id"])
    assert view["state"] == "INTERRUPTED"
    root = next(p for p in tmp_path.rglob("interruptions.jsonl"))
    entry = json.loads(root.read_text().splitlines()[-1])
    assert entry["stage"] == "operation"
    assert entry["code"] == TransportCode.CONFLICT.value


def test_an_untyped_failure_says_where_carbon_raised_it_and_nothing_else(tmp_path):
    """BUG MOTOR_RUN_INTERRUPTED_CANDIDATE_20261020: a bare ValueError with
    code null took a second rehearsal to place. The record now names the
    innermost Carbon frame: code identifiers, never the message."""
    from carbon.motor.campaign import research_runtime

    try:
        research_runtime(
            {"SECRET-SENTINEL": 1}, implementation=None, images=[], julia_image=None
        )
    except ValueError as exc:
        assert "SECRET-SENTINEL" in str(exc)  # specimen
        record_interruption(tmp_path, "run", exc)
    entry = json.loads((tmp_path / "interruptions.jsonl").read_text())
    assert entry["error_type"] == "builtins.ValueError" and entry["code"] is None
    module, function, line = entry["raised_at"].split(":")
    assert (module, function) == ("carbon.motor.campaign", "research_runtime")
    assert line.isdigit()
    assert "SECRET-SENTINEL" not in json.dumps(entry)


def test_a_failure_outside_carbon_has_no_raise_site(tmp_path):
    record_interruption(tmp_path, "run", ValueError("no traceback"))
    entry = json.loads((tmp_path / "interruptions.jsonl").read_text())
    assert entry["raised_at"] is None
