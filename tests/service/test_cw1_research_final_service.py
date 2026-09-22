"""Real numerical fresh-profile source path with an explicitly synthetic chain.

Fixed engineering recipes and keys exercise composition only. They are not real
agent inference, public-testnet activity, or the owner-authorized campaign.
"""

import asyncio
import json
import math
import os
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from bittensor.keyfiles import Keypair

from carbon.chain import ChainContext, MetagraphSnapshot, Participant
from carbon.chain.sdk import BittensorReader
from carbon.development_comparison.acceptance import resolve_acceptance
from carbon.development_session import research_campaign
from carbon.development_session.research_campaign import final_epoch, frozen_seeds
from carbon.development_session.research_data import (
    PublicReferenceData,
    decode_public_case,
)
from carbon.development_session.research_generation import generate_roles
from carbon.development_session.research_ledger import (
    DEVELOPMENT_CEILINGS,
    DEVELOPMENT_ELAPSED_SECONDS,
    VERSION,
    CampaignLedger,
)
from carbon.development_session.research_profile import public_cases
from carbon.evaluation.enums import ReferenceFailureReason, ReferenceRunOutcome
from carbon.generators.burgers_dynamics import requested_times
from carbon.reconstruction.worker.docker_runtime import load_image_identity
from carbon.reexecution.store import ReexecutionJournal
from carbon.reference_runtime.model import (
    BurgersReferenceRole,
    build_reference_request,
    runtime_environment_digest,
)


def _bounded_failure_bytes(record):
    remaining = 2048

    def check(value, depth=0):
        nonlocal remaining
        remaining -= 1
        if remaining < 0 or depth > 8:
            raise ValueError("bounded engineering reference evidence required")
        if value is None or type(value) is bool:
            return
        if type(value) in (int, float) and math.isfinite(value):
            return
        if type(value) is str and len(value) <= 1024:
            return
        if type(value) in (list, tuple) and len(value) <= 128:
            for item in value:
                check(item, depth + 1)
            return
        if type(value) is dict and len(value) <= 64:
            for key, item in value.items():
                if type(key) is not str or len(key) > 128:
                    raise ValueError("bounded engineering evidence key required")
                check(item, depth + 1)
            return
        raise ValueError("bounded engineering reference evidence required")

    check(record)
    payload = json.dumps(record, sort_keys=True, allow_nan=False).encode("utf8")
    if len(payload) > 65536:
        raise ValueError("engineering reference evidence exceeds byte limit")
    return payload + b"\n"


def _observe_train_reference(execute, allowed, target):
    """Capture only this fixture's existing TRAIN requests; never change results."""

    def observed(request):
        result = execute(request)
        if (
            target is None
            or request.request_digest not in allowed
            or result.result.outcome is ReferenceRunOutcome.SUPPORTED
        ):
            return result
        try:
            record = {
                "schema": "carbon.c04.engineering-reference-failure.v1",
                "kind": "synthetic_public_train_reference_failure",
                "parent_id": allowed[request.request_digest],
                "request": request.document(),
                "request_digest": request.request_digest,
                "outcome": result.result.outcome.value,
                "failure_reason": result.result.failure_reason.value,
                "diagnostics": result.result.diagnostics,
                "image_id": result.image_id,
                "launch_digest": result.launch_digest,
                "snapshot_digest": result.snapshot_digest,
                "controls_digest": result.controls_digest,
                "controls": {
                    key: result.controls[key]
                    for key in ("cgroup_v2", "process", "container_id")
                    if key in result.controls
                },
                "resources": {
                    key: result.resources[key]
                    for key in ("cpu", "memory", "pids", "measurement_scope")
                    if key in result.resources
                },
                "timings": {
                    key: result.timings[key]
                    for key in (
                        "staging",
                        "create",
                        "numerical",
                        "export",
                        "cleanup",
                        "validation",
                        "total",
                    )
                    if key in result.timings
                },
                "candidate_judged": False,
                "reproduction": "exact request only; no redraw or retry authorized",
            }
            payload = _bounded_failure_bytes(record)
            path = Path(target)
            if path.is_symlink() or (
                path.exists() and path.stat().st_size + len(payload) > 1048576
            ):
                raise ValueError("bounded engineering trace file required")
            with path.open("ab") as stream:
                stream.write(payload)
        except (OSError, ValueError, TypeError, AttributeError, OverflowError):
            # Evidence failure must not replace the existing scientific failure.
            print(
                "Engineering TRAIN diagnostics unavailable; original outcome retained."
            )
        return result

    return observed


@pytest.mark.parametrize(
    "record",
    [
        {"bad": float("nan")},
        {"bad": "x" * 1025},
        {str(index): "x" * 1024 for index in range(64)},
        {"bad": [[[[[[[[[0]]]]]]]]]},
        {"bad": object()},
    ],
)
def test_engineering_reference_evidence_bounds(record):
    with pytest.raises(ValueError):
        _bounded_failure_bytes(record)


def test_engineering_reference_failure_trace_preserves_result_and_public_binding(
    tmp_path,
    capsys,
):
    target = tmp_path / "trace.jsonl"
    request = SimpleNamespace(
        request_digest="request", document=lambda: {"query": [1.0]}
    )
    result = SimpleNamespace(
        result=SimpleNamespace(
            outcome=ReferenceRunOutcome.NUMERICAL_FAILURE,
            failure_reason=ReferenceFailureReason.NUMERICAL_NONCONVERGENCE,
            diagnostics=(("method", "fixed"),),
        ),
        image_id="image",
        launch_digest="launch",
        snapshot_digest="snapshot",
        controls_digest="controls",
        controls={"container_id": "container", "secret": "excluded"},
        resources={"memory": {"events": {"oom": 0}}, "secret": "excluded"},
        timings={"cleanup": 0.5, "secret": "excluded"},
    )
    observed = _observe_train_reference(
        lambda value: result, {"request": "parent"}, target
    )
    assert observed(request) is result
    record = json.loads(target.read_bytes())
    assert record["request"] == request.document()
    assert record["parent_id"] == "parent"
    assert record["outcome"] == "NUMERICAL_FAILURE"
    assert record["candidate_judged"] is False
    assert b"excluded" not in target.read_bytes()
    before = target.read_bytes()
    assert _observe_train_reference(lambda value: result, {}, target)(request) is result
    assert target.read_bytes() == before
    # Downstream retains its original non-SUPPORTED reference failure.
    with pytest.raises(ValueError, match="reference failure; candidate not judged"):
        if observed(request).result.outcome is not ReferenceRunOutcome.SUPPORTED:
            raise ValueError("reference failure; candidate not judged")
    result.result.diagnostics = (("message", "x" * 1025),)
    before = target.read_bytes()
    assert observed(request) is result
    assert target.read_bytes() == before
    assert "original outcome retained" in capsys.readouterr().out
    result.result.outcome = ReferenceRunOutcome.SUPPORTED
    assert observed(request) is result
    assert target.read_bytes() == before
    original_error = RuntimeError("existing controller failure")

    def failed(value):
        raise original_error

    with pytest.raises(RuntimeError) as failure:
        _observe_train_reference(failed, {"request": "parent"}, target)(request)
    assert failure.value is original_error


def test_real_fresh_final_sources_compare_and_resume_without_redispatch(
    tmp_path, monkeypatch
):
    ledger = CampaignLedger(tmp_path / "engineering-fresh-final")
    owner = "synthetic-engineering-owner"
    ledger.freeze(
        {
            "schema": VERSION,
            "ceilings": DEVELOPMENT_CEILINGS,
            "elapsed_seconds": DEVELOPMENT_ELAPSED_SECONDS,
            **{
                name: owner
                for name in (
                    "campaign_id",
                    "implementation",
                    "objective",
                    "sampling",
                    "control",
                    "selection",
                    "replica_policy",
                    "provider",
                    "owner",
                )
            },
        }
    )
    manifest = Path(os.environ["CARBON_C03_IMAGE_MANIFEST"])
    image = load_image_identity(manifest)
    miner = Keypair.create_from_uri("//Alice")
    publisher = Keypair.create_from_uri("//Bob")
    context = ChainContext(
        "testnet", "ws://127.0.0.1:1", "synthetic-d4", "0x" + "2" * 64, 567
    )
    sequence = 100

    async def capture(self, requested):
        nonlocal sequence
        sequence += 1
        assert requested == context
        return MetagraphSnapshot(
            context,
            sequence,
            "0x" + f"{sequence:064x}",
            time.time_ns() // 1_000_000,
            (
                Participant(0, publisher.ss58_address, "synthetic-owner", 1),
                Participant(1, miner.ss58_address, "synthetic-miner", 2),
            ),
        )

    monkeypatch.setattr(BittensorReader, "capture", capture)
    strategy = {
        "schema_version": "1.0",
        "challenge_id": "burgers-dynamics-v1",
        "backbone": "fno",
        "parameters": {
            "steps": 2,
            "width": 4,
            "depth": 1,
            "n_modes": 4,
            "enforce_mean": True,
        },
    }
    monkeypatch.setattr(research_campaign, "CONTROL", strategy)
    previous = os.umask(0o077)
    try:
        seeds = frozen_seeds(ledger.root)
        roles = generate_roles(ledger, owner=owner, image=image)
        data = PublicReferenceData(
            ledger=ledger, owner=owner, image=image, role_root=roles
        )
        allowed = {}
        for value in public_cases(roles, "research-train"):
            case = decode_public_case(value)
            request = build_reference_request(
                case,
                BurgersReferenceRole.CANDIDATE_PRIMARY,
                output_points=64,
                requested_times=requested_times(case, 4),
                environment_digest=runtime_environment_digest(),
            )
            allowed[request.request_digest] = case.parent_id
        monkeypatch.setattr(
            data.controller,
            "execute",
            _observe_train_reference(
                data.controller.execute,
                allowed,
                os.environ.get("CARBON_C03_TRACE_PATH"),
            ),
        )
        args = SimpleNamespace(
            image_manifest=manifest,
            quarantine_journal=ledger.root / "quarantine.sqlite3",
        )
        # Explicit engineering lifecycle fixture; production readers never
        # manufacture an absent operator quarantine journal.
        ReexecutionJournal(args.quarantine_journal)
        config = SimpleNamespace(
            context=context, publisher_hotkey=publisher.ss58_address
        )

        async def run():
            return await final_epoch(
                args,
                ledger,
                owner,
                1,
                strategy,
                seeds,
                roles,
                data,
                image,
                miner,
                config,
            )

        feedback, ref = asyncio.run(run())
        result = resolve_acceptance(ref)
        assert result["schema"].endswith(".v2") and result["prospective"]
        assert (
            not result["official_eligible"]
            and not result["network_eligible"]
            and not result["paying"]
        )
        assert result["baseline"]["authenticated_hotkey"] == miner.ss58_address
        assert len(result["measurements"]["sources"]) == 2
        assert all(len(rows) == 72 for rows in result["measurements"]["sources"])
        assert len(result["measurements"]["reference_checks"]) == 24
        before = ledger.status(owner=owner)["used"]
        assert before["provider_attempts"] == before["research_trials"] == 0
        assert before["final_replicas"] == 6
        assert (
            before["reference_invocations"] == before["reference_trajectories"] == 144
        )
        assert asyncio.run(run()) == (feedback, ref)
        assert ledger.status(owner=owner)["used"] == before
        rendered = json.dumps(feedback)
        for private in (
            str(ledger.root),
            "case_digest",
            "solution_path",
            "seed",
            "private-role",
        ):
            assert private not in rendered
    finally:
        os.umask(previous)
